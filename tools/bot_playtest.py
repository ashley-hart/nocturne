"""Headless bot playtest: drives the real Game loop to check generated jumps
are clearable with the actual Player physics, and exercises the telemetry ->
director -> streamer loop end to end.

    python tools/bot_playtest.py --levels 20 --skill 0.9

The bot walks to the best take-off point, jumps toward the next main-path
platform and fires air jumps at the apex until it is high enough. It ignores
gems off the main path, so it measures *reachability*, not score. ``--skill``
pins the telemetry rating (and so the difficulty the director asks for); use
``--adaptive`` to let it evolve instead.

``--true-skill S`` turns the bot into a synthetic player of skill S: before
each jump it botches with probability sigmoid((difficulty - S) * 10) by
mashing all its jumps at once. With ``--adaptive`` you can watch the
telemetry's skill estimate (and the difficulty) converge toward S.
"""
import math
import argparse
import os
import random
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import pygame  # noqa: E402

from scripts.levelgen import TILE_SIZE, jump_geometry  # noqa: E402


def load_game_class():
    # game.py launches the menu at import time; take everything before that.
    src = open(os.path.join(ROOT, "game.py")).read().split("retval = MainMenu().run()")[0]
    ns = {"__name__": "bloodgems_game"}
    exec(compile(src, "game.py", "exec"), ns)

    class _Screen:
        def __init__(self, *a, **k):
            pass

        def run(self):
            return "retry"

    ns["WinScreen"] = _Screen
    ns["MainMenu"] = _Screen
    return ns["Game"]


class FixedClock:
    def tick(self, fps=60):
        return 1000 / 60


class Bot:
    def __init__(self, game, rng, true_skill=None):
        self.g = game
        self.rng = rng
        self.true_skill = true_skill
        self.botch = False
        self.standing_on = None

    def act(self):
        """Set movement for this frame; return 'jump', 'cut' or None."""
        g, p = self.g, self.g.player
        tel, st = g.telemetry, g.streamer
        tgt = st.path_platform(tel.current_index + 1)
        r = p.rect()
        grounded = p.air_time <= 4
        if grounded:
            # plan from the platform actually underfoot (may be a gem branch)
            self.standing_on = st.platform_under(r.left, r.right, r.bottom)
        cur = self.standing_on or st.path_platform(tel.current_index)
        if cur is None:
            return None
        if tgt is None:  # on the exit platform: walk to the door
            door = g.zones[0].rect if g.zones else r
            self._move(1 if door.centerx > r.centerx + 2 else -1 if door.centerx < r.centerx - 2 else 0)
            return None
        geo = jump_geometry(cur, tgt)
        if geo is None:
            return None
        b_top = tgt.y * TILE_SIZE
        b_left, b_right = tgt.x0 * TILE_SIZE, (tgt.x1 + 1) * TILE_SIZE

        if grounded:
            # take off from the edge nearest b, but never from underneath it
            if geo.direction > 0:
                spot = min((cur.x1 + 1) * TILE_SIZE - r.width, b_left - r.width - 1)
            else:
                spot = max(cur.x0 * TILE_SIZE, b_right + 1)
            if r.x != spot:
                self._move(1 if spot > r.x else -1)
                return None
            self._move(0 if geo.sidestep else geo.direction)
            if self.true_skill is not None:
                p_fail = 1 / (1 + math.exp(-(tgt.difficulty - self.true_skill) * 10))
                self.botch = self.rng.random() < p_fail
            return "jump"

        # airborne
        if self.botch:
            # panic: mash every jump straight away, wasting them
            self._move(geo.direction)
            return "jump" if p.jumps else None
        over = r.right > b_left + 2 and r.left < b_right - 2
        under = r.right > b_left and r.left < b_right and r.bottom > b_top
        if under:
            # below b and beneath it: step out from under it first
            self._move(-1 if r.centerx < (b_left + b_right) / 2 else 1)
        elif r.bottom > b_top - 1:
            # not above b's surface yet: close in on its side but stop when
            # touching, or the engine nudges us under the corner (head bonk)
            if r.right <= b_left:
                self._move(1 if r.right < b_left - 1 else 0)
            else:
                self._move(-1 if r.left > b_right + 1 else 0)
        elif not over:
            self._move(1 if b_left + (b_right - b_left) / 2 > r.centerx else -1)
        else:
            self._move(0)
        # Air-jump only once we stop rising and are (about to be) below the
        # target surface: a low arc that climbs only as high as needed.
        rising = p.velocity[1] < 0
        if not rising and not under and p.jumps and r.bottom > b_top - 3:
            return "jump"
        # Jump-cut once over b and comfortably above it, so we don't
        # overshoot into whatever is above the landing.
        if rising and over and r.bottom < b_top - 20:
            return "cut"
        return None

    def _move(self, d):
        self.g.movement[0] = d < 0
        self.g.movement[1] = d > 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--levels", type=int, default=10)
    ap.add_argument("--skill", type=float, default=None, help="pin skill rating")
    ap.add_argument("--adaptive", action="store_true", help="let skill evolve")
    ap.add_argument("--true-skill", type=float, default=None,
                    help="make the bot a synthetic player of this skill (0..1)")
    ap.add_argument("--max-seconds", type=float, default=90.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    Game = load_game_class()
    import builtins
    real_print = builtins.print
    builtins.print = lambda *a, **k: None  # silence the game's debug prints
    game = Game()
    game.clock = FixedClock()
    game.save_telemetry = lambda: None
    game.advance_level = lambda: None  # stay on the tower we are measuring
    rng = random.Random(args.seed)
    bot = Bot(game, rng, args.true_skill)

    results = []
    state = {"frames": 0, "level_runs": 0}
    pinned = args.skill if not args.adaptive else None

    def start_run():
        if pinned is not None:
            game.telemetry.skill.rating = pinned
        game.streamer.rng.seed(rng.randrange(1 << 30))
        game.generate_level(1)
        state["frames"] = 0

    def finish(reached):
        st, tel = game.streamer, game.telemetry
        path = [p for p in st.path if p.index > 0]
        results.append({
            "reached": reached,
            "platforms": len(path),
            "mean_difficulty": sum(p.difficulty for p in path) / max(1, len(path)),
            "max_jumps": max((p.jumps_required for p in path), default=0),
            "falls": tel.stats["falls"],
            "skill": tel.skill.rating,
            "seconds": state["frames"] / 60,
        })
        if not args.quiet:
            r = results[-1]
            real_print(f"run {len(results):3d}: {'REACHED' if reached else 'stuck  '} "
                       f"platforms={r['platforms']:2d} mean_d={r['mean_difficulty']:.2f} "
                       f"max_jumps={r['max_jumps']} falls={r['falls']:2d} "
                       f"skill={r['skill']:.2f} t={r['seconds']:.1f}s")

    def events():
        state["frames"] += 1
        game.level_timer = 999  # measure reachability, not the clock
        if pinned is not None:
            game.telemetry.skill.rating = pinned
        st = game.streamer
        if st.finished and game.telemetry.current_index == st.exit_platform.index:
            finish(True)
        elif state["frames"] > args.max_seconds * 60:
            finish(False)
        else:
            action = bot.act()
            if action == "jump":
                return [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)]
            if action == "cut":
                return [pygame.event.Event(pygame.KEYUP, key=pygame.K_SPACE)]
            return []
        if len(results) >= args.levels:
            raise SystemExit
        start_run()
        return []

    pygame.event.get = events
    start_run()
    try:
        game.run()
    except SystemExit:
        pass
    builtins.print = real_print
    reached = sum(r["reached"] for r in results)
    n = len(results)
    print(f"\nreached exit in {reached}/{n} runs; "
          f"mean jump difficulty {sum(r['mean_difficulty'] for r in results) / n:.2f}; "
          f"final skill {game.telemetry.skill.rating:.2f}; "
          f"on-screen spawns {game.streamer.onscreen_spawns}")
    return 0 if reached == n else 1


if __name__ == "__main__":
    sys.exit(main())
