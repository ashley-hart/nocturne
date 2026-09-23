"""Online level streaming: platforms are generated just above the camera.

Instead of building the whole tower when a level starts, the streamer keeps
a *frontier* (the highest main-path platform) a fixed distance above the top
of the screen. Each frame the game reports where the camera is; whenever the
frontier drops inside that lookahead band the streamer asks the director for
a target difficulty (from live telemetry) and generates the next platforms.
So the jumps the player meets were shaped by how they played moments ago.

Pure Python: returns Platform/Gem data; the game turns them into tiles/Rubies.
"""
from __future__ import annotations

import math
import random

from .levelgen import (TILE_SIZE, INTERIOR_MIN_X, INTERIOR_MAX_X, ChunkGenerator,
                       Gem, JumpModel, PlacementContext, Platform, clamp, lerp)

FINAL_AREA_HEIGHT = 10     # rows under the ceiling reserved for the exit
# Exit platform spans to try: widest first, then most central (the old
# 'final' platform type was columns 3..12).
_CENTRE = (INTERIOR_MIN_X + INTERIOR_MAX_X) / 2
FINAL_SPANS = sorted(
    ((x0, x0 + w - 1) for w in range(5, 11)
     for x0 in range(INTERIOR_MIN_X, INTERIOR_MAX_X - w + 2)),
    key=lambda s: (-(s[1] - s[0]), abs((s[0] + s[1]) / 2 - _CENTRE)))


class OnlineLevelStreamer:
    def __init__(self, generator=None, director=None, telemetry=None,
                 lookahead_px=128, seed=None):
        self.rng = random.Random(seed)
        self.generator = generator or ChunkGenerator(JumpModel(), self.rng)
        self.generator.rng = self.rng
        self.director = director
        self.telemetry = telemetry
        self.lookahead_px = lookahead_px
        self.ctx = None

    # -- setup ---------------------------------------------------------------
    def reset(self, top_row, required_gems, gem_chance=0.75, difficulty_offset=0.0,
              start_row=18, start_gem=(100, 272), seed=None):
        """Prepare a new level whose ceiling starts at ``top_row``."""
        if seed is not None:
            self.rng.seed(seed)
        self.top_row = top_row
        self.final_row = top_row + FINAL_AREA_HEIGHT
        self.required_gems = required_gems
        self.gem_chance = gem_chance
        self.difficulty_offset = difficulty_offset
        self.ctx = PlacementContext()
        self.tile_index = {}
        self.gems = {}
        self.collected = set()
        self.path = []
        self.pattern = None
        self.step = 0
        self.target = None
        self.breather = False
        self.finished = False
        self.exit_platform = None
        self.exit_door_pos = None
        self.prefilled = False
        self.onscreen_spawns = 0
        self.relaxed_exit = False
        self.chunks = []
        self._pending = []
        if self.director:
            self.director.reset()

        floor = Platform(pid=0, x0=INTERIOR_MIN_X, x1=INTERIOR_MAX_X, y=start_row,
                         index=0, pattern="floor")
        self.ctx.platforms.append(floor)
        self._register(floor)
        if start_gem:
            self._add_gem(floor, Gem(self.generator.new_gid(), *start_gem, "start", 0))
        self.frontier = floor
        self._pending.append(floor)
        if self.telemetry:
            self.telemetry.path_lookup = self.path_platform

    # -- queries -------------------------------------------------------------
    def path_platform(self, index):
        return self.path[index] if 0 <= index < len(self.path) else None

    def platform_at(self, tx, ty):
        return self.tile_index.get((tx, ty))

    def platform_under(self, left_px, right_px, bottom_px):
        """Platform directly under a rect's feet (checks centre then edges)."""
        ty = int(bottom_px // TILE_SIZE)
        for x in ((left_px + right_px) / 2, left_px, right_px - 1):
            p = self.platform_at(int(x // TILE_SIZE), ty)
            if p is not None:
                return p
        return None

    def gems_ahead(self, feet_px):
        return sum(1 for g in self.gems.values()
                   if g.gid not in self.collected and g.y < feet_px)

    def on_gem_collected(self, gid):
        self.collected.add(gid)

    # -- streaming -----------------------------------------------------------
    def update(self, view_top_px, player_feet_px=None):
        """Generate everything needed up to ``lookahead_px`` above the view.

        Returns the platforms created since the last call (gems attached).
        """
        feet = player_feet_px if player_feet_px is not None else view_top_px
        limit_row = math.floor((view_top_px - self.lookahead_px) / TILE_SIZE)
        new = self._pending
        self._pending = []
        while not self.finished and self.frontier.y > limit_row:
            new.extend(self._advance(feet))
        if self.prefilled:
            for p in new:
                if (p.y + 1) * TILE_SIZE > view_top_px:
                    self.onscreen_spawns += 1
        self.prefilled = True
        return new

    def generate_all(self):
        """Generate the whole level at once (for previews/tests)."""
        out = []
        while not self.finished:
            out.extend(self.update(-10**9))
        return out

    def _advance(self, feet_px):
        gen = self.generator
        if self.frontier.y <= self.final_row + 4:
            return self._place_final(feet_px)

        if self.pattern is None or self.step >= self.pattern.steps:
            self._start_chunk()

        res = gen.place_step(self.ctx, self.frontier, self.pattern, self.step,
                             self.target, self.final_row + 2)
        if res is None:
            return self._place_final(feet_px)
        cand, assessment = res
        platform = gen.commit(self.ctx, self.frontier, cand, assessment,
                              self.pattern.name, self.target)
        self.pattern.advance(self.frontier, platform)
        self.step += 1
        created = [platform]
        if self._wants_gem(platform, feet_px):
            created += gen.place_gem(self.ctx, self.frontier, platform, assessment,
                                     self.target, getattr(self.pattern, "arc_gem_bias", 0.0),
                                     min_y=self.final_row)
        self._accept_path(platform)
        for p in created:
            if p is not platform:
                self._register(p)
            for g in p.gems:
                self._track_gem(g)
        return created

    def _start_chunk(self):
        if self.director and self.telemetry:
            self.target, self.breather, reasons = self.director.next_target(
                self.telemetry.summary(), self.difficulty_offset)
        else:
            self.target = clamp(0.35 + self.difficulty_offset, 0.0, 1.0)
            self.breather, reasons = False, {}
        self.pattern = self.generator.choose_pattern(self.target, rest=self.breather)(self.rng, self.frontier)
        self.step = 0
        chunk = {"from_index": self.frontier.index, "row": self.frontier.y,
                 "pattern": self.pattern.name, "steps": self.pattern.steps,
                 "target": round(self.target, 3), "breather": self.breather, **reasons}
        self.chunks.append(chunk)
        if self.telemetry:
            self.telemetry.log("chunk", **chunk)

    def _accept_path(self, platform):
        platform.index = len(self.path)
        self._register(platform)
        self.frontier = platform

    def _register(self, platform):
        if platform.on_path and (not self.path or self.path[-1] is not platform):
            if platform.index == len(self.path):
                self.path.append(platform)
        for t in platform.tiles():
            self.tile_index[t] = platform

    # -- gems ----------------------------------------------------------------
    def _add_gem(self, platform, gem):
        platform.gems.append(gem)
        self._track_gem(gem)

    def _track_gem(self, gem):
        if gem.gid in self.gems:
            return
        self.gems[gem.gid] = gem
        if self.telemetry:
            self.telemetry.on_gem_spawned(gem)

    def _wants_gem(self, platform, feet_px):
        """Gem economy: keep enough gems ahead of the player to hit the goal.

        Outside of that guarantee, gems appear with the level's base chance.
        The safety buffer shrinks as the player's skill grows.
        """
        skill = self.telemetry.skill.rating if self.telemetry else 0.3
        need_left = self.required_gems - len(self.collected)
        ahead = self.gems_ahead(feet_px)
        rows_left = max(0, platform.y - self.final_row)
        climbed = len(self.path) - 1
        avg_rise = (self.path[0].y - platform.y) / (climbed + 1) if climbed >= 1 else 3.5
        platforms_left = max(1.0, rows_left / clamp(avg_rise, 2.0, 9.0))
        buffer = lerp(3, 1, clamp(skill, 0, 1))
        if need_left + buffer - ahead >= platforms_left * 0.8:
            return True
        return self.rng.random() < self.gem_chance

    # -- exit ----------------------------------------------------------------
    def _final_candidate(self, anchor, ctx=None):
        # The door is 3 rows tall and the ceiling ends at top_row - 1.
        min_y = self.top_row + 3
        for y in range(anchor.y - 1, min_y - 1, -1):
            for x0, x1 in FINAL_SPANS:
                res = self.generator.evaluate(ctx or self.ctx, anchor, x0, x1, y, min_y)
                if res is not None:
                    return res
        return None

    def _place_final(self, feet_px):
        gen = self.generator
        created = []
        res = self._final_candidate(self.frontier)
        tries = 0
        while res is None and tries < 3:
            # Need an approach ledge from which the exit platform is reachable.
            approach = gen.place_step(
                self.ctx, self.frontier, gen.choose_pattern(0.0, rest=True)(self.rng, self.frontier),
                0, 0.2, self.top_row + 7,
                accept=lambda c: self._final_candidate(c) is not None)
            if approach is None:
                approach = gen.exhaustive(self.ctx, self.frontier, 0.2, self.top_row + 7,
                                          accept=lambda c: self._final_candidate(c) is not None)
            if approach is None:
                break
            p = gen.commit(self.ctx, self.frontier, *approach, "approach", 0.2)
            self._accept_path(p)
            created.append(p)
            res = self._final_candidate(self.frontier)
            tries += 1
        if res is None:
            # Last resort: only respect the frontier and the jump onto it.
            self.relaxed_exit = True
            last = [c for c in self.ctx.corridors if c[1][1] == self.frontier.pid]
            res = self._final_candidate(self.frontier, PlacementContext([self.frontier], last))
        if res is None:
            raise RuntimeError("level generation could not reach the exit")

        final = gen.commit(self.ctx, self.frontier, *res, "final", self.target or 0.0)
        self._accept_path(final)
        created.append(final)
        # Validation guarantee: the level always contains enough gems.
        shortfall = self.required_gems - len(self.gems)
        for col in range(final.x0, final.x1 + 1)[:max(0, shortfall)]:
            gx, gy = final.gem_slot(col)
            self._add_gem(final, Gem(gen.new_gid(), gx, gy, "bonus", final.pid))
        for p in created:
            for g in p.gems:
                self._track_gem(g)
        mx, my = final.gem_slot()
        self.exit_platform = final
        self.exit_door_pos = (mx - TILE_SIZE, my - TILE_SIZE * 2)
        self.finished = True
        return created
