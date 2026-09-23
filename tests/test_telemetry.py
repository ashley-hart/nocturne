import json
import os
import tempfile
import unittest

from scripts.director import DifficultyDirector
from scripts.levelgen import Platform
from scripts.telemetry import SkillModel, Telemetry


def plat(index, y, difficulty=0.5, jumps=1):
    return Platform(pid=index, x0=1, x1=4, y=y, index=index,
                    difficulty=difficulty, jumps_required=jumps)


class SkillModelTest(unittest.TestCase):
    def test_expected_is_half_at_own_rating(self):
        m = SkillModel(rating=0.4)
        self.assertAlmostEqual(m.expected(0.4), 0.5)
        self.assertGreater(m.expected(0.1), 0.9)

    def test_surprises_move_rating_more(self):
        m = SkillModel(rating=0.4)
        hard_win = m.update(0.8, 1.0)
        m.rating = 0.4
        easy_win = m.update(0.1, 1.0)
        self.assertGreater(hard_win, easy_win)


class TelemetryTest(unittest.TestCase):
    def setUp(self):
        self.path = [plat(0, 18, 0.0), plat(1, 14, 0.3), plat(2, 10, 0.7), plat(3, 6, 0.4)]
        self.t = Telemetry(initial_skill=0.4)
        self.t.path_lookup = lambda i: self.path[i] if i < len(self.path) else None
        self.t.start_level(1, 6, 60, 18, -30)
        self.t.on_land(self.path[0])

    def jump_to(self, platform, jumps=1):
        for i in range(jumps):
            self.t.on_jump(airborne=i > 0)
        return self.t.on_land(platform)

    def test_advance_raises_skill(self):
        before = self.t.skill.rating
        self.assertEqual(self.jump_to(self.path[1]), "advance")
        self.assertGreater(self.t.skill.rating, before)
        self.assertEqual(self.t.current_index, 1)

    def test_fall_is_charged_to_attempted_jump(self):
        self.jump_to(self.path[1])
        self.jump_to(self.path[2], jumps=2)
        before = self.t.skill.rating
        self.assertEqual(self.jump_to(self.path[1], jumps=3), "fall")
        self.assertLess(self.t.skill.rating, before)
        fall = [e for e in self.t.events if e["type"] == "fall"][-1]
        self.assertEqual(fall["difficulty"], 0.4)  # the jump from 2 to 3
        self.assertEqual(self.t.stats["rows_fallen"], 4)

    def test_spending_all_jumps_and_landing_back_is_a_failed_attempt(self):
        before = self.t.skill.rating
        self.assertEqual(self.jump_to(self.path[0], jumps=3), "fail")
        self.assertLess(self.t.skill.rating, before)
        self.assertEqual(self.jump_to(self.path[0], jumps=1), "stay")

    def test_wasted_jumps_give_partial_credit(self):
        clean = Telemetry(initial_skill=0.4)
        clean.on_jump(False)
        clean.on_land(self.path[1])
        sloppy = Telemetry(initial_skill=0.4)
        for i in range(3):
            sloppy.on_jump(i > 0)
        sloppy.on_land(self.path[1])
        self.assertGreater(clean.skill.rating, sloppy.skill.rating)

    def test_gems_and_pace(self):
        class G:
            def __init__(self, gid, y):
                self.gid, self.y = gid, y
        self.t.on_gem_spawned(G(1, 260))
        self.t.on_gem_spawned(G(2, -100))
        self.t.tick(10.0, 250, grounded=True, moving=False)
        self.t.on_gem_collected(1)
        s = self.t.summary()
        self.assertEqual(s["gem_collection_rate"], 1.0)  # 1 passed, 1 collected
        self.assertGreater(s["progress"], 0)
        self.assertLess(s["pace"], 1.0)  # slow climb for 10s

    def test_timeout_lowers_skill_and_save(self):
        before = self.t.skill.rating
        self.t.end_level("timeout", 0.0)
        self.assertLess(self.t.skill.rating, before)
        with tempfile.TemporaryDirectory() as d:
            path = self.t.save(d)
            with open(path) as f:
                data = json.load(f)
        self.assertEqual(data["levels"][0]["outcome"], "timeout")
        self.assertTrue(os.path.basename(path).startswith("session_"))


class DirectorTest(unittest.TestCase):
    def summary(self, skill, **kw):
        base = {"skill": skill, "skill_scale": 8.0, "pace": 1.0, "time_frac": 0.5,
                "fail_streak": 0}
        base.update(kw)
        return base

    def test_targets_the_success_rate(self):
        d = DifficultyDirector(target_success=0.75, breather_every=0)
        target, _, _ = d.next_target(self.summary(0.5))
        p = SkillModel(rating=0.5).expected(target)
        self.assertAlmostEqual(p, 0.75, places=2)

    def test_struggling_player_gets_easier_jumps(self):
        d = DifficultyDirector(breather_every=0, max_step_down=1, max_step_up=1)
        normal, _, _ = d.next_target(self.summary(0.5))
        d.reset()
        streak, _, _ = d.next_target(self.summary(0.5, fail_streak=3))
        d.reset()
        behind, _, _ = d.next_target(self.summary(0.5, pace=0.5))
        self.assertLess(streak, normal)
        self.assertLess(behind, normal)

    def test_rate_limited_and_breathers(self):
        d = DifficultyDirector(breather_every=3, max_step_up=0.1)
        t1, b1, _ = d.next_target(self.summary(0.2))
        t2, b2, _ = d.next_target(self.summary(0.9))
        self.assertAlmostEqual(t2 - t1, 0.1)
        _, b3, _ = d.next_target(self.summary(0.9))
        self.assertEqual((b1, b2, b3), (False, False, True))


if __name__ == "__main__":
    unittest.main()
