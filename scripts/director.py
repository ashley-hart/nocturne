"""Difficulty director: turns telemetry into a target jump difficulty.

The skill rating is the difficulty a player clears half the time, so the
director aims *below* it, at jumps the player should clear with probability
``target_success`` (inverting the rating's logistic curve):

target = skill - logit(target_success) / scale
       + pace adjustment              (behind the clock -> ease off)
       - fail-streak relief           (repeated falls -> ease off quickly)
       + level offset                 (later levels lean harder)
then a breather every few chunks, and a rate limit so changes are felt
gradually (easing off is allowed to happen faster than ramping up).
"""
from __future__ import annotations

import math

from .levelgen import clamp


class DifficultyDirector:
    def __init__(self, target_success=0.75, max_step_up=0.12, max_step_down=0.2,
                 breather_every=5, breather_drop=0.25, min_difficulty=0.05,
                 max_difficulty=0.95):
        self.target_success = target_success
        self.max_step_up = max_step_up
        self.max_step_down = max_step_down
        self.breather_every = breather_every
        self.breather_drop = breather_drop
        self.min_difficulty = min_difficulty
        self.max_difficulty = max_difficulty
        self.reset()

    def reset(self):
        self.last = None
        self.chunks = 0
        self.history = []

    def next_target(self, summary, level_offset=0.0):
        """Return (target_difficulty, is_breather, reasons)."""
        reasons = {"skill": round(summary["skill"], 3)}
        p = self.target_success
        challenge = -math.log(p / (1 - p)) / summary.get("skill_scale", 8.0)
        raw = summary["skill"] + challenge + level_offset

        if summary.get("time_frac", 0) > 0.1:
            pace_adj = clamp((summary["pace"] - 1.0) * 0.2, -0.2, 0.1)
            raw += pace_adj
            reasons["pace"] = round(pace_adj, 3)

        streak = summary.get("fail_streak", 0)
        if streak >= 2:
            relief = 0.08 * (streak - 1)
            raw -= relief
            reasons["relief"] = round(-relief, 3)

        breather = self.breather_every > 0 and self.chunks % self.breather_every == self.breather_every - 1
        if breather:
            raw -= self.breather_drop
            reasons["breather"] = -self.breather_drop

        raw = clamp(raw, self.min_difficulty, self.max_difficulty)
        if self.last is not None and not breather:
            raw = clamp(raw, self.last - self.max_step_down, self.last + self.max_step_up)
        if not breather:
            self.last = raw
        self.chunks += 1
        self.history.append({"chunk": self.chunks, "target": round(raw, 3), **reasons})
        return raw, breather, reasons
