"""Print generated towers as ASCII, side by side, at different difficulties.

    python tools/preview_level.py                 # easy / medium / hard
    python tools/preview_level.py --seed 4 --difficulty 0.2 0.8 --top -40

'=' main path  '-' gem side-branch  '*' gem
The rightmost columns list each main-path jump's measured difficulty,
jumps required and the pattern that produced it.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.levelgen import render_ascii  # noqa: E402
from scripts.streaming import OnlineLevelStreamer  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--top", type=int, default=-40, help="level_height (ceiling row)")
    ap.add_argument("--difficulty", type=float, nargs="+", default=[0.1, 0.4, 0.8])
    ap.add_argument("--gems", type=int, default=6)
    args = ap.parse_args()

    columns = []
    for d in args.difficulty:
        s = OnlineLevelStreamer(seed=args.seed)
        # Without a director the streamer targets 0.35 + offset.
        s.reset(top_row=args.top, required_gems=args.gems, difficulty_offset=d - 0.35)
        s.generate_all()
        notes = {p.y: f"{p.difficulty:.2f} {p.jumps_required}J {p.pattern}" for p in s.path[1:]}
        lines = render_ascii(s.ctx.platforms, args.top).splitlines()
        rows = range(args.top, 20)
        path = [p for p in s.path[1:-1]]
        mean = sum(p.difficulty for p in path) / max(1, len(path))
        header = f"target {d:.2f}  mean {mean:.2f}  gems {len(s.gems)}"
        columns.append([header] + [f"{ln}  {notes.get(r, ''):<18}" for ln, r in zip(lines, rows)])

    width = max(len(x) for col in columns for x in col)
    for row in zip(*columns):
        print("   ".join(x.ljust(width) for x in row))


if __name__ == "__main__":
    main()
