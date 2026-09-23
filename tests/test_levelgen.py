import unittest

from scripts.levelgen import (INTERIOR_MAX_X, INTERIOR_MIN_X, MIN_STACK_SPACING,
                              TILE_SIZE, JumpModel, Platform, assess_jump,
                              columns_overlap, rects_intersect)
from scripts.streaming import OnlineLevelStreamer


def level(seed, top=-60, offset=0.0, gems=8):
    s = OnlineLevelStreamer(seed=seed)
    s.reset(top_row=top, required_gems=gems, difficulty_offset=offset)
    s.generate_all()
    return s


class JumpModelTest(unittest.TestCase):
    def setUp(self):
        self.m = JumpModel()

    def test_each_air_jump_adds_height(self):
        a1, a2, a3 = (self.m.apex(n) for n in (1, 2, 3))
        self.assertAlmostEqual(a1, 78, delta=2)
        self.assertGreater(a2, a1 * 1.9)
        self.assertGreater(a3, a2 * 1.4)

    def test_min_jumps(self):
        self.assertEqual(self.m.min_jumps(10, 2 * TILE_SIZE), 1)
        self.assertEqual(self.m.min_jumps(10, 7 * TILE_SIZE), 2)
        self.assertEqual(self.m.min_jumps(10, 12 * TILE_SIZE), 3)
        self.assertIsNone(self.m.min_jumps(10, 20 * TILE_SIZE))
        self.assertIsNone(self.m.min_jumps(400, 0))  # too far sideways

    def test_matches_player_class(self):
        try:
            import pygame  # noqa: F401
            from scripts.entities import Player
        except ImportError:
            self.skipTest("pygame not installed")
        m = JumpModel.from_player(Player)
        self.assertEqual(m.jump_velocity, -Player.JUMP_HEIGHT)
        self.assertEqual(m.fall_gravity, Player.FALL_GRAVITY)
        self.assertEqual(m.max_jumps, Player.NUM_JUMPS)


class AssessJumpTest(unittest.TestCase):
    def setUp(self):
        self.m = JumpModel()

    def test_platform_entirely_under_target_is_unreachable(self):
        a = Platform(0, 5, 7, 10, 0)
        b = Platform(1, 4, 8, 5, 1)
        self.assertIsNone(assess_jump(self.m, a, b))

    def test_harder_jumps_score_higher(self):
        a = Platform(0, 1, 4, 10, 0)
        easy = assess_jump(self.m, a, Platform(1, 6, 10, 8, 1))
        far = assess_jump(self.m, a, Platform(1, 11, 14, 8, 1))
        narrow = assess_jump(self.m, a, Platform(1, 6, 6, 8, 1))
        high = assess_jump(self.m, a, Platform(1, 6, 10, 1, 1))
        for harder in (far, narrow, high):
            self.assertGreater(harder.difficulty, easy.difficulty)
        self.assertGreater(high.jumps_required, easy.jumps_required)


class GeneratedLevelTest(unittest.TestCase):
    """Properties every generated tower must have, across many seeds."""

    SEEDS = range(40)
    OFFSETS = (-0.3, 0.1, 0.6)

    def levels(self):
        for seed in self.SEEDS:
            for off in self.OFFSETS:
                yield seed, off, level(seed, offset=off)

    def test_every_main_path_jump_is_reachable_and_unobstructed(self):
        m = JumpModel()
        for seed, off, s in self.levels():
            for a, b in zip(s.path, s.path[1:]):
                res = assess_jump(m, a, b)
                self.assertIsNotNone(res, f"seed={seed} off={off} {a} -> {b}")
                for p in s.ctx.platforms:
                    if p.pid in (a.pid, b.pid):
                        continue
                    self.assertFalse(
                        rects_intersect((p.x0, p.x1, p.y, p.y), res.geometry.corridor),
                        f"seed={seed} off={off}: {p} blocks {a} -> {b}")

    def test_platforms_in_bounds_and_spaced(self):
        for seed, off, s in self.levels():
            ps = s.ctx.platforms
            for i, p in enumerate(ps):
                self.assertGreaterEqual(p.x0, INTERIOR_MIN_X)
                self.assertLessEqual(p.x1, INTERIOR_MAX_X)
                for q in ps[i + 1:]:
                    if columns_overlap(p, q, margin=1):
                        self.assertGreaterEqual(abs(p.y - q.y), MIN_STACK_SPACING,
                                                f"seed={seed} {p} {q}")

    def test_exit_and_gem_requirements(self):
        for seed, off, s in self.levels():
            self.assertTrue(s.finished)
            self.assertIs(s.path[-1], s.exit_platform)
            self.assertGreaterEqual(s.exit_platform.y, s.top_row + 3)
            self.assertGreaterEqual(len(s.gems), s.required_gems)
            self.assertFalse(s.relaxed_exit, f"seed={seed} off={off}")

    def test_difficulty_follows_target(self):
        def mean_d(off):
            ds = [p.difficulty for seed in self.SEEDS
                  for p in level(seed, offset=off).path[1:-1]]
            return sum(ds) / len(ds)
        easy, mid, hard = mean_d(-0.3), mean_d(0.1), mean_d(0.6)
        self.assertLess(easy, mid)
        self.assertLess(mid, hard)

    def test_deterministic_for_a_seed(self):
        a = [(p.x0, p.x1, p.y) for p in level(7).ctx.platforms]
        b = [(p.x0, p.x1, p.y) for p in level(7).ctx.platforms]
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
