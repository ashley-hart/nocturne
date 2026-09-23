import unittest

from scripts.director import DifficultyDirector
from scripts.levelgen import TILE_SIZE
from scripts.streaming import OnlineLevelStreamer
from scripts.telemetry import Telemetry


def climb(seed, offset=0.0, step_px=4):
    """Scroll the camera up the tower like a player climbing."""
    tel = Telemetry()
    s = OnlineLevelStreamer(director=DifficultyDirector(), telemetry=tel, seed=seed)
    s.reset(top_row=-60, required_gems=8, difficulty_offset=offset)
    tel.start_level(1, 8, 60, 18, -50)
    view = 0
    first = s.update(view, 280)
    batches = []
    while not s.finished:
        view -= step_px
        batches.append((view, s.update(view, view + 250)))
    return s, first, batches


class StreamingTest(unittest.TestCase):
    def test_prefill_covers_first_screen_only(self):
        s = OnlineLevelStreamer(seed=1)
        s.reset(top_row=-60, required_gems=8)
        first = s.update(0, 280)
        rows = [p.y for p in first]
        self.assertIn(18, rows)  # the floor comes first
        self.assertFalse(s.finished)
        # generated up to about one lookahead above the first screen, no more
        top = min(rows)
        self.assertLessEqual(top, -s.lookahead_px // TILE_SIZE + 1)
        self.assertGreater(top, -s.lookahead_px // TILE_SIZE - 12)

    def test_new_platforms_always_spawn_offscreen(self):
        for seed in range(15):
            s, _, batches = climb(seed)
            self.assertEqual(s.onscreen_spawns, 0)
            for view, new in batches:
                for p in new:
                    self.assertLess((p.y + 1) * TILE_SIZE, view,
                                    f"seed {seed}: {p} spawned inside view {view}")

    def test_generation_is_incremental(self):
        _, _, batches = climb(3)
        nonempty = [b for _, b in batches if b]
        self.assertGreater(len(nonempty), 3)

    def test_director_consulted_per_chunk_with_live_skill(self):
        tel = Telemetry(initial_skill=0.9)
        s = OnlineLevelStreamer(director=DifficultyDirector(breather_every=0),
                                telemetry=tel, seed=4)
        s.reset(top_row=-60, required_gems=8)
        tel.start_level(1, 8, 60, 18, -50)
        s.update(0, 280)
        high = s.target
        tel.skill.rating = 0.1  # player is suddenly struggling
        view = 0
        while s.target >= high and not s.finished:
            view -= 4
            s.update(view, view + 250)
        self.assertLess(s.target, high)

    def test_platform_lookup(self):
        s, _, _ = climb(2)
        p = s.path[3]
        self.assertIs(s.platform_at(p.x0, p.y), p)
        self.assertIs(s.platform_under(p.x0 * 16, p.x0 * 16 + 8, p.y * 16), p)
        self.assertIs(s.path_platform(3), p)
        self.assertIsNone(s.path_platform(len(s.path)))


if __name__ == "__main__":
    unittest.main()
