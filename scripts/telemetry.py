"""Player telemetry for Bloodgems.

Records gameplay events (jumps, landings, falls, gems, level results) and
turns them into performance metrics the difficulty director can act on.

The central metric is a skill *rating* on the same 0..1 scale as the level
generator's jump difficulty. Every jump the player attempts is treated like
an Elo match between the player and that jump: clearing a hard jump raises
the rating a lot, falling off an easy one lowers it a lot. Because the
generator measures every jump it places, the rating means "the difficulty of
jump this player clears about half the time".

Pure Python (no pygame) so it can be unit tested and driven by simulations.
"""
from __future__ import annotations

import json
import math
import os
import time
from collections import deque


def _sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))


class SkillModel:
    """Elo-style rating on the jump-difficulty scale."""

    def __init__(self, rating=0.3, scale=8.0, learning_rate=0.1, lo=0.0, hi=1.0):
        self.rating = rating
        self.scale = scale
        self.learning_rate = learning_rate
        self.lo, self.hi = lo, hi

    def expected(self, difficulty):
        """Probability the player clears a jump of this difficulty."""
        return _sigmoid((self.rating - difficulty) * self.scale)

    def update(self, difficulty, outcome, weight=1.0):
        """outcome in [0, 1]: 1 clean success, 0 failure. Returns the delta."""
        delta = self.learning_rate * weight * (outcome - self.expected(difficulty))
        self.rating = min(self.hi, max(self.lo, self.rating + delta))
        return delta

    def nudge(self, amount):
        self.rating = min(self.hi, max(self.lo, self.rating + amount))


class Telemetry:
    """Collects events for a play session and summarises performance.

    The game calls the ``on_*`` hooks; ``summary()`` returns the metrics.
    ``path_lookup(index)`` (set by the level streamer) maps a main-path index
    to its Platform so a fall can be charged to the jump that was attempted.
    """

    def __init__(self, initial_skill=0.3, window=8, max_jumps=3):
        self.skill = SkillModel(rating=initial_skill)
        self.window = window
        self.max_jumps = max_jumps
        self.path_lookup = None
        self.session_start = time.time()
        self.events = []
        self.levels = []
        self.level = None
        self._recent = deque(maxlen=window)       # attempt outcomes (0..1)
        self._recent_eff = deque(maxlen=window)   # required / used jumps
        self._reset_level_state()

    # -- lifecycle -----------------------------------------------------------
    def _reset_level_state(self):
        self.t = 0.0
        self.current_index = 0
        self.max_index = 0
        self.current_platform = None
        self.jumps_this_air = 0
        self.airborne = False
        self.fail_streak = 0
        self.gems_spawned = {}  # gid -> y px
        self.gems_collected = set()
        self.best_feet_px = None
        self.stats = {
            "jumps": 0, "air_jumps": 0, "landings": 0, "advances": 0,
            "falls": 0, "rows_fallen": 0, "failed_attempts": 0,
            "gems": 0, "idle_time": 0.0, "air_time": 0.0,
        }

    def start_level(self, level, required_gems, time_limit, start_row, exit_row,
                    tile_size=16):
        if self.level is not None and self.level.get("outcome") is None:
            self.end_level("abandoned", 0.0)
        self._reset_level_state()
        self.tile_size = tile_size
        self.level = {
            "level": level, "required_gems": required_gems,
            "time_limit": time_limit, "start_row": start_row,
            "exit_row": exit_row, "skill_start": self.skill.rating,
            "outcome": None,
        }
        self._log("level_start", level=level, required_gems=required_gems,
                  time_limit=time_limit)

    def end_level(self, outcome, time_left):
        """outcome: 'win' | 'timeout' | 'abandoned'."""
        if self.level is None:
            return
        if outcome == "timeout":
            self.skill.nudge(-0.08)
        elif outcome == "win":
            self.skill.nudge(0.04 * self.time_left_frac(time_left))
        self.level.update(outcome=outcome, time_left=round(time_left, 2),
                          skill_end=self.skill.rating, stats=dict(self.stats),
                          metrics=self.summary())
        self._log("level_end", outcome=outcome, time_left=round(time_left, 2))
        self.levels.append(self.level)
        self.level = dict(self.level)  # keep reading params, but it's closed

    # -- per-frame -----------------------------------------------------------
    def tick(self, dt, feet_px, grounded, moving):
        self.t += dt
        if self.best_feet_px is None or feet_px < self.best_feet_px:
            self.best_feet_px = feet_px
        if grounded and not moving:
            self.stats["idle_time"] += dt
        if not grounded:
            self.stats["air_time"] += dt

    # -- events --------------------------------------------------------------
    def on_jump(self, airborne):
        self.stats["jumps"] += 1
        self.jumps_this_air += 1
        if airborne:
            self.stats["air_jumps"] += 1
        self._log("jump", air=airborne)

    def on_takeoff(self):
        """Left the ground (jumped or walked off an edge)."""
        self.airborne = True

    def on_land(self, platform):
        """Landed on ``platform`` (a levelgen.Platform) or None if unknown.

        Returns what the landing meant: 'advance' | 'fall' | 'fail' | 'stay'.
        """
        self.stats["landings"] += 1
        used = self.jumps_this_air
        self.jumps_this_air = 0
        self.airborne = False
        if platform is None:
            return "stay"
        idx = platform.index
        result = "stay"
        if idx > self.current_index:
            skipped = idx - self.current_index - 1
            required = max(1, platform.jumps_required)
            wasted = max(0, used - required)
            outcome = max(0.4, 1.0 - 0.15 * wasted)
            difficulty = min(1.0, platform.difficulty + 0.08 * skipped)
            delta = self.skill.update(difficulty, outcome)
            self._recent.append(outcome)
            if used:
                self._recent_eff.append(min(1.0, required / used))
            self.stats["advances"] += 1
            self.fail_streak = 0
            result = "advance"
            self._log("advance", index=idx, difficulty=round(difficulty, 3),
                      jumps=used, delta=round(delta, 4))
        elif idx < self.current_index:
            attempted = self._attempted_difficulty()
            delta = self.skill.update(attempted, 0.0)
            rows = platform.y - self.current_platform.y if self.current_platform else 0
            self._recent.append(0.0)
            self.stats["falls"] += 1
            self.stats["rows_fallen"] += max(0, rows)
            self.fail_streak += 1
            result = "fall"
            self._log("fall", index=idx, from_index=self.current_index, rows=rows,
                      difficulty=round(attempted, 3), delta=round(delta, 4))
        elif used >= self.max_jumps and platform.on_path:
            # Spent every jump and came straight back down: a failed attempt.
            attempted = self._attempted_difficulty()
            delta = self.skill.update(attempted, 0.0, weight=0.5)
            self._recent.append(0.25)
            self.stats["failed_attempts"] += 1
            self.fail_streak += 1
            result = "fail"
            self._log("failed_attempt", index=idx, difficulty=round(attempted, 3),
                      delta=round(delta, 4))
        self.max_index = max(self.max_index, idx)
        self.current_index = idx
        self.current_platform = platform
        return result

    def _attempted_difficulty(self):
        if self.path_lookup:
            nxt = self.path_lookup(self.current_index + 1)
            if nxt is not None:
                return nxt.difficulty
        return self.skill.rating

    def on_gem_spawned(self, gem):
        self.gems_spawned[gem.gid] = gem.y

    def on_gem_collected(self, gem_id):
        self.stats["gems"] += 1
        if gem_id is not None:
            self.gems_collected.add(gem_id)
        self._log("gem", gid=gem_id)

    # -- metrics -------------------------------------------------------------
    def time_left_frac(self, time_left):
        limit = (self.level or {}).get("time_limit") or 1
        return max(0.0, min(1.0, time_left / limit))

    def progress(self):
        """Fraction of the tower climbed (by best height reached)."""
        if not self.level or self.best_feet_px is None:
            return 0.0
        ts = getattr(self, "tile_size", 16)
        start = self.level["start_row"] * ts
        goal = self.level["exit_row"] * ts
        if start == goal:
            return 0.0
        return max(0.0, min(1.0, (start - self.best_feet_px) / (start - goal)))

    def gems_passed(self):
        """Gems the player has climbed past (below their best height)."""
        if self.best_feet_px is None:
            return 0
        return sum(1 for y in self.gems_spawned.values() if y > self.best_feet_px)

    def summary(self):
        lvl = self.level or {}
        limit = lvl.get("time_limit") or 1
        time_frac = min(1.0, self.t / limit)
        progress = self.progress()
        need = lvl.get("required_gems") or 0
        gem_progress = min(1.0, self.stats["gems"] / need) if need else 1.0
        # Pace > 1: ahead of what's needed to finish in time.
        overall = min(progress, 0.5 * (progress + gem_progress))
        pace = overall / time_frac if time_frac > 0.05 else 1.0
        passed = self.gems_passed()
        return {
            "skill": self.skill.rating,
            "skill_scale": self.skill.scale,
            "success_rate": (sum(self._recent) / len(self._recent)) if self._recent else None,
            "jump_efficiency": (sum(self._recent_eff) / len(self._recent_eff)) if self._recent_eff else None,
            "fall_rate": self.stats["falls"] / max(1, self.stats["falls"] + self.stats["advances"]),
            "fail_streak": self.fail_streak,
            "progress": progress,
            "gem_progress": gem_progress,
            "gem_collection_rate": (len(self.gems_collected & set(self.gems_spawned)) / passed) if passed else None,
            "time_frac": time_frac,
            "pace": pace,
            "idle_frac": self.stats["idle_time"] / self.t if self.t else 0.0,
        }

    # -- logging -------------------------------------------------------------
    def _log(self, kind, **data):
        self.events.append({"t": round(self.t, 3), "level": (self.level or {}).get("level"),
                            "type": kind, "skill": round(self.skill.rating, 4), **data})

    def log(self, kind, **data):
        """Public hook for other systems (e.g. the director) to annotate the log."""
        self._log(kind, **data)

    def to_dict(self):
        return {"session_start": self.session_start, "skill": self.skill.rating,
                "levels": self.levels, "events": self.events}

    def save(self, directory="telemetry"):
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, time.strftime("session_%Y%m%d_%H%M%S.json",
                                                     time.localtime(self.session_start)))
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=1, default=str)
        return path
