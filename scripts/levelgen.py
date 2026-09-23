"""Pure procedural level generation for Bloodgems.

Nothing in this module touches pygame: it works purely in tile coordinates
and produces plain data (``Platform`` and ``Gem``) that the game turns into
tiles and Ruby objects. That keeps it testable headlessly and lets tools
(``tools/preview_level.py``) run without a display.

Main pieces:

* ``JumpModel``     - a frame-accurate replica of the Player's jump physics
                      used to decide what is reachable.
* ``assess_jump``   - measures how hard it is to get from platform A to B.
* ``PATTERNS``      - jump configurations (staircase, zigzag, leap, ...).
* ``ChunkGenerator`` - places platforms/gems one at a time, generating
                       candidates from a pattern and keeping the valid one
                       whose measured difficulty is closest to a target.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

TILE_SIZE = 16
# The tower walls occupy columns -1, 0, 15 and 16 (see Tilemap.level_init),
# so platforms may use columns 1..14.
INTERIOR_MIN_X = 1
INTERIOR_MAX_X = 14
PLAYER_WIDTH = 8
PLAYER_HEIGHT = 15
# Platforms sharing (or touching) columns must be at least this many rows
# apart so the player can stand between them.
MIN_STACK_SPACING = 3
GEM_SIZE = 16


def lerp(a, b, t):
    return a + (b - a) * t


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

@dataclass
class Gem:
    gid: int
    x: float  # top-left in world pixels, same convention as Ruby
    y: float
    kind: str  # 'ledge' | 'arc' | 'branch' | 'bonus' | 'start'
    platform_id: int


@dataclass
class Platform:
    pid: int
    x0: int  # first column (inclusive)
    x1: int  # last column (inclusive)
    y: int   # tile row of the platform surface
    index: int  # position along the main path (branches share their anchor's)
    on_path: bool = True
    pattern: str = "start"
    difficulty: float = 0.0  # measured difficulty of the jump INTO this platform
    jumps_required: int = 0
    target: float | None = None  # difficulty the director asked for
    arrival_dir: int = 0  # +1/-1: direction the player travels to reach it
    gems: list[Gem] = field(default_factory=list)

    @property
    def width(self):
        return self.x1 - self.x0 + 1

    def tiles(self):
        for x in range(self.x0, self.x1 + 1):
            yield x, self.y

    def gem_slot(self, column=None):
        """Top-left pixel position for a gem resting on this platform."""
        if column is None:
            cx = (self.x0 + self.x1 + 1) * TILE_SIZE / 2
            return cx - GEM_SIZE / 2, (self.y - 1) * TILE_SIZE
        return column * TILE_SIZE, (self.y - 1) * TILE_SIZE

    def to_dict(self):
        return {
            "pid": self.pid, "x0": self.x0, "x1": self.x1, "y": self.y,
            "index": self.index, "on_path": self.on_path, "pattern": self.pattern,
            "difficulty": round(self.difficulty, 3),
            "jumps_required": self.jumps_required,
            "target": None if self.target is None else round(self.target, 3),
            "gems": [g.kind for g in self.gems],
        }


# ---------------------------------------------------------------------------
# Physics
# ---------------------------------------------------------------------------

class JumpModel:
    """Frame-by-frame replica of ``Player`` jump physics.

    For n = 1..max_jumps we simulate a jump where every air jump is fired at
    the apex (the strategy that maximises height and airtime), recording the
    height of the player's feet above the take-off surface each frame. Since
    horizontal speed is constant and freely controllable, after ``t`` frames
    the player can be anywhere within ``t * move_speed`` pixels sideways, so
    a target is reachable when the curve is at or above it at some frame
    after the horizontal distance has been covered.
    """

    def __init__(self, jump_velocity=3.9, gravity_step=0.1, fall_gravity=4.0,
                 terminal_velocity=5.0, move_speed=1.0, max_jumps=3, fps=60,
                 max_frames=600, min_margin_px=6):
        self.jump_velocity = jump_velocity
        self.gravity_step = gravity_step
        self.fall_gravity = fall_gravity
        self.terminal_velocity = terminal_velocity
        self.move_speed = move_speed
        self.max_jumps = max_jumps
        self.fps = fps
        self.max_frames = max_frames
        # A jump only counts as reachable if it clears by this much, so the
        # generator never relies on pixel-perfect execution.
        self.min_margin_px = min_margin_px
        self.curves = {n: self._simulate(n) for n in range(1, max_jumps + 1)}
        self._suffix_max = {n: self._suffix(c) for n, c in self.curves.items()}

    @classmethod
    def from_player(cls, player_cls, **kwargs):
        return cls(jump_velocity=-player_cls.JUMP_HEIGHT,
                   fall_gravity=player_cls.FALL_GRAVITY,
                   max_jumps=player_cls.NUM_JUMPS, **kwargs)

    def _simulate(self, n_jumps):
        # Mirrors PhysicsEntity.update followed by Player.update.
        vy = -self.jump_velocity
        y = 0.0
        air_jumps = n_jumps - 1
        heights = []
        for _ in range(self.max_frames):
            y += vy
            vy = min(self.terminal_velocity, vy + self.gravity_step)
            if vy > 0:
                vy += (vy * self.fall_gravity) / self.fps
            if air_jumps and vy >= 0:
                vy = -self.jump_velocity
                air_jumps -= 1
            heights.append(-y)
            if -y < -TILE_SIZE * 40:
                break
        return heights

    @staticmethod
    def _suffix(curve):
        out = list(curve)
        for i in range(len(out) - 2, -1, -1):
            out[i] = max(out[i], out[i + 1])
        return out

    def apex(self, n_jumps):
        return max(self.curves[n_jumps])

    def best_height_after(self, n_jumps, frames):
        sm = self._suffix_max[n_jumps]
        if frames >= len(sm):
            return -math.inf
        return sm[max(0, frames)]

    def height_margin(self, dx_px, dy_px, n_jumps):
        frames = math.ceil(max(0.0, dx_px) / self.move_speed)
        return self.best_height_after(n_jumps, frames) - dy_px

    def min_jumps(self, dx_px, dy_px):
        for n in range(1, self.max_jumps + 1):
            if self.height_margin(dx_px, dy_px, n) >= self.min_margin_px:
                return n
        return None

    def max_rise_tiles(self, n_jumps=None):
        return int(self.apex(n_jumps or self.max_jumps) // TILE_SIZE)


# ---------------------------------------------------------------------------
# Jump assessment
# ---------------------------------------------------------------------------

@dataclass
class JumpGeometry:
    dx_px: float
    dy_px: float
    gap_tiles: int
    sidestep: bool  # B hangs over A, player must step out from under it
    direction: int  # +1 right, -1 left
    corridor: tuple  # (x0, x1, y0, y1) tiles that must stay clear


def columns_overlap(a, b, margin=0):
    return a.x0 - margin <= b.x1 and b.x0 - margin <= a.x1


# Rows of headroom one full jump needs (its apex plus the player's height).
SINGLE_JUMP_HEADROOM = 6
# Rows kept clear above a landing reached by a steep multi-jump climb (the
# player can jump-cut on arrival).
LANDING_HEADROOM = 3
# Gaps at least this wide make multi-jump leaps travel while hopping at the
# landing's height, so they need a full jump of headroom above it.
WIDE_GAP_TILES = 3


def jump_geometry(a, b):
    """Horizontal/vertical distance the player must cover to go from a to b."""
    dy_px = (a.y - b.y) * TILE_SIZE + 1
    # Conservative corridor top; assess_jump refines it once it knows how
    # many jumps are needed (see corridor_top).
    top = min(a.y, b.y) - SINGLE_JUMP_HEADROOM
    if columns_overlap(a, b):
        if a.y - b.y < MIN_STACK_SPACING:
            return None
        left_free = b.x0 - a.x0
        right_free = a.x1 - b.x1
        if max(left_free, right_free) < 1:
            return None  # a is entirely underneath b
        if left_free >= right_free:
            corridor = (b.x0 - 1, b.x0 - 1, top, a.y - 1)
            direction = 1
        else:
            corridor = (b.x1 + 1, b.x1 + 1, top, a.y - 1)
            direction = -1
        return JumpGeometry(PLAYER_WIDTH + 2, dy_px, 0, True, direction, corridor)
    if b.x0 > a.x1:
        gap = b.x0 - a.x1 - 1
        corridor = (a.x1, b.x0, top, max(a.y, b.y) - 1)
        direction = 1
    else:
        gap = a.x0 - b.x1 - 1
        corridor = (b.x1, a.x0, top, max(a.y, b.y) - 1)
        direction = -1
    # Conservative: no credit for the player overhanging either edge.
    # With no gap column the take-off edge sits right under b's corner, so
    # the player has to rise alongside b first - as awkward as a sidestep.
    return JumpGeometry(gap * TILE_SIZE + 2, dy_px, gap, gap == 0 and dy_px > TILE_SIZE,
                        direction, corridor)


def corridor_top(a, b, geo, jumps):
    """Highest row the a->b flight can reach, which must stay clear.

    A single jump never rises more than one jump above take-off. Multi-jump
    leaps across a wide gap hop along at about the landing's height, so need
    a full jump of headroom above it; steep multi-jump climbs only need a
    little room to arrive (jump-cut).
    """
    if jumps <= 1:
        return a.y - SINGLE_JUMP_HEADROOM
    if geo.gap_tiles >= WIDE_GAP_TILES:
        return min(a.y, b.y) - SINGLE_JUMP_HEADROOM
    return min(a.y - SINGLE_JUMP_HEADROOM, b.y - LANDING_HEADROOM)


@dataclass
class JumpAssessment:
    jumps_required: int
    difficulty: float
    margin_px: float
    geometry: JumpGeometry
    features: dict


def assess_jump(model, a, b):
    """Return a JumpAssessment for a->b, or None if b can't be reached.

    Difficulty in [0, 1] blends four physically grounded features:
      * jumps  - how many of the player's jumps are needed (less spare = harder)
      * slack  - how much height is left over with that many jumps
      * width  - how narrow the landing is
      * reach  - how far sideways the player must travel (time in the air)
    plus a small penalty when the player must step out from under b.
    """
    geo = jump_geometry(a, b)
    if geo is None:
        return None
    n = model.min_jumps(geo.dx_px, geo.dy_px)
    if n is None:
        return None
    margin = model.height_margin(geo.dx_px, geo.dy_px, n)
    c = geo.corridor
    geo.corridor = (c[0], c[1], corridor_top(a, b, geo, n), c[3])
    features = {
        "jumps": (n - 1) / max(1, model.max_jumps - 1),
        "slack": 1.0 - clamp(margin / (TILE_SIZE * 3), 0.0, 1.0),
        "width": clamp((5 - b.width) / 4, 0.0, 1.0),
        "reach": clamp(geo.dx_px / (TILE_SIZE * 8), 0.0, 1.0),
    }
    d = (0.35 * features["jumps"] + 0.20 * features["slack"]
         + 0.25 * features["width"] + 0.20 * features["reach"])
    if geo.sidestep:
        d += 0.08
    return JumpAssessment(n, clamp(d, 0.0, 1.0), margin, geo, features)


# ---------------------------------------------------------------------------
# Jump configurations
# ---------------------------------------------------------------------------

def _room(prev, direction):
    """Free columns beside prev in the given direction."""
    return INTERIOR_MAX_X - prev.x1 if direction > 0 else prev.x0 - INTERIOR_MIN_X


def _rint(rng, lo, hi):
    lo, hi = int(round(lo)), int(round(hi))
    if hi < lo:
        lo, hi = hi, lo
    return rng.randint(lo, hi)


def _toward_open_side(prev):
    centre = (prev.x0 + prev.x1) / 2
    return 1 if centre < (INTERIOR_MIN_X + INTERIOR_MAX_X) / 2 else -1


def _momentum(prev, room=4):
    """Keep travelling the way the player arrived at prev (don't double back
    over the gap just crossed) if there's room; otherwise head for open space."""
    d = getattr(prev, "arrival_dir", 0)
    if d > 0 and INTERIOR_MAX_X - prev.x1 >= room:
        return 1
    if d < 0 and prev.x0 - INTERIOR_MIN_X >= room:
        return -1
    return _toward_open_side(prev)


class Pattern:
    """A jump configuration: proposes the next platform given the previous.

    Proposals only express the pattern's *shape*; the generator samples many
    of them and keeps the valid one closest to the target difficulty.
    """
    name = "pattern"
    min_steps, max_steps = 1, 1

    def __init__(self, rng, prev):
        self.rng = rng
        self.steps = rng.randint(self.min_steps, self.max_steps)

    @staticmethod
    def weight(d):
        return 1.0

    def propose(self, prev, step, d):
        raise NotImplementedError

    def advance(self, prev, placed):
        """Called after a step is placed so stateful patterns can update."""


class Staircase(Pattern):
    """Short hops stepping steadily sideways and up."""
    name = "staircase"
    min_steps, max_steps = 3, 4

    def __init__(self, rng, prev):
        super().__init__(rng, prev)
        self.dir = _momentum(prev)

    @staticmethod
    def weight(d):
        return 1.2 - 0.7 * d

    def propose(self, prev, step, d):
        r = self.rng
        w = _rint(r, lerp(4, 2, d), lerp(6, 3, d))
        dy = _rint(r, 2, lerp(3, 6, d))
        gap = _rint(r, 1, lerp(2, 4, d))
        if _room(prev, self.dir) < gap + w:
            self.dir = -self.dir  # hit a wall: turn around
        x0 = prev.x1 + 1 + gap if self.dir > 0 else prev.x0 - gap - w
        return x0, x0 + w - 1, prev.y - dy

    def advance(self, prev, placed):
        # bounce off the walls
        if placed.x1 >= INTERIOR_MAX_X - 1:
            self.dir = -1
        elif placed.x0 <= INTERIOR_MIN_X + 1:
            self.dir = 1


class Zigzag(Pattern):
    """Wall-hugging ledges alternating between the two sides of the tower."""
    name = "zigzag"
    min_steps, max_steps = 3, 4

    def __init__(self, rng, prev):
        super().__init__(rng, prev)
        self.side = _toward_open_side(prev)

    def propose(self, prev, step, d):
        r = self.rng
        w = _rint(r, lerp(5, 2, d), lerp(6, 3, d))
        dy = _rint(r, lerp(2, 3, d), lerp(4, 8, d))
        if self.side > 0:
            return INTERIOR_MAX_X - w + 1, INTERIOR_MAX_X, prev.y - dy
        return INTERIOR_MIN_X, INTERIOR_MIN_X + w - 1, prev.y - dy

    def advance(self, prev, placed):
        self.side = -self.side


class Leap(Pattern):
    """A long sideways leap across the tower, often with a gem mid-air."""
    name = "leap"
    arc_gem_bias = 0.6

    @staticmethod
    def weight(d):
        return 0.2 + 0.8 * d

    def propose(self, prev, step, d):
        r = self.rng
        w = _rint(r, lerp(4, 1, d), lerp(5, 3, d))
        dy = _rint(r, 0, lerp(2, 7, d))
        if _toward_open_side(prev) > 0:
            x0 = _rint(r, prev.x1 + 3, INTERIOR_MAX_X - w + 1)
        else:
            x0 = _rint(r, INTERIOR_MIN_X, prev.x0 - 2 - w)
        return x0, x0 + w - 1, prev.y - dy


class Chimney(Pattern):
    """Tall climb up narrow ledges near one wall - needs air jumps."""
    name = "chimney"
    min_steps, max_steps = 3, 4

    def __init__(self, rng, prev):
        super().__init__(rng, prev)
        self.side = rng.choice((-1, 1))
        self.inner = False

    @staticmethod
    def weight(d):
        return max(0.0, d - 0.25) * 1.4

    def propose(self, prev, step, d):
        r = self.rng
        w = _rint(r, 1, lerp(3, 2, d))
        dy = _rint(r, lerp(3, 5, d), lerp(5, 9, d))
        offset = _rint(r, 3, 5) if self.inner else 0
        if self.side < 0:
            x0 = INTERIOR_MIN_X + offset
        else:
            x0 = INTERIOR_MAX_X - w + 1 - offset
        return x0, x0 + w - 1, prev.y - dy

    def advance(self, prev, placed):
        self.inner = not self.inner


class SteppingStones(Pattern):
    """Tiny stones strung sideways with little height gain."""
    name = "stones"
    min_steps, max_steps = 3, 4

    def __init__(self, rng, prev):
        super().__init__(rng, prev)
        self.dir = _momentum(prev)

    @staticmethod
    def weight(d):
        return 0.3 + 0.6 * d

    def propose(self, prev, step, d):
        r = self.rng
        w = _rint(r, 1, lerp(3, 2, d))
        dy = _rint(r, 1, 3)
        gap = _rint(r, lerp(1, 2, d), lerp(2, 5, d))
        if _room(prev, self.dir) < gap + w:
            self.dir = -self.dir
        x0 = prev.x1 + 1 + gap if self.dir > 0 else prev.x0 - gap - w
        return x0, x0 + w - 1, prev.y - dy

    def advance(self, prev, placed):
        if placed.x1 >= INTERIOR_MAX_X - 2:
            self.dir = -1
        elif placed.x0 <= INTERIOR_MIN_X + 2:
            self.dir = 1


class Rest(Pattern):
    """A wide, easy ledge - used for breathers and the final approach."""
    name = "rest"

    @staticmethod
    def weight(d):
        return max(0.0, 0.8 - d) + 0.1

    def propose(self, prev, step, d):
        r = self.rng
        w = _rint(r, 4, 7)
        dy = _rint(r, 2, 4)
        x0 = _rint(r, INTERIOR_MIN_X, INTERIOR_MAX_X - w + 1)
        return x0, x0 + w - 1, prev.y - dy


PATTERNS = {p.name: p for p in (Staircase, Zigzag, Leap, Chimney, SteppingStones, Rest)}


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

@dataclass
class PlacementContext:
    """Everything already in the level that new platforms must respect."""
    platforms: list = field(default_factory=list)
    corridors: list = field(default_factory=list)  # (rect, (pid_a, pid_b))

    def nearby(self, y, rows=14):
        return [p for p in self.platforms if abs(p.y - y) <= rows]


def rects_intersect(r1, r2):
    return r1[0] <= r2[1] and r2[0] <= r1[1] and r1[2] <= r2[3] and r2[2] <= r1[3]


class ChunkGenerator:
    """Places platforms one at a time toward a target difficulty.

    It never touches pygame; the caller owns the level state
    (``PlacementContext``) and turns the returned platforms into tiles.
    """

    def __init__(self, model=None, rng=None, candidates=20):
        self.model = model or JumpModel()
        self.rng = rng or random.Random()
        self.candidates = candidates
        self._next_pid = 1
        self._next_gid = 1

    # -- ids ---------------------------------------------------------------
    def new_pid(self):
        pid, self._next_pid = self._next_pid, self._next_pid + 1
        return pid

    def new_gid(self):
        gid, self._next_gid = self._next_gid, self._next_gid + 1
        return gid

    # -- validation --------------------------------------------------------
    def fits(self, ctx, cand, min_y):
        """Hard constraints: in bounds, spaced, not blocking any jump path."""
        if cand.x0 < INTERIOR_MIN_X or cand.x1 > INTERIOR_MAX_X or cand.x1 < cand.x0:
            return False
        if cand.y < min_y:
            return False
        for p in ctx.nearby(cand.y):
            if columns_overlap(p, cand, margin=1) and abs(p.y - cand.y) < MIN_STACK_SPACING:
                return False
        rect = (cand.x0, cand.x1, cand.y, cand.y)
        for crect, _ in ctx.corridors:
            if rects_intersect(rect, crect):
                return False
        return True

    def path_is_clear(self, ctx, a, b, geo):
        """No existing platform (other than a/b) sits in the a->b corridor."""
        for p in ctx.nearby(b.y):
            if p.pid in (a.pid, b.pid):
                continue
            if rects_intersect((p.x0, p.x1, p.y, p.y), geo.corridor):
                return False
        return True

    def evaluate(self, ctx, anchor, x0, x1, y, min_y):
        cand = Platform(pid=-1, x0=x0, x1=x1, y=y, index=anchor.index + 1)
        if not self.fits(ctx, cand, min_y):
            return None
        a = assess_jump(self.model, anchor, cand)
        if a is None or not self.path_is_clear(ctx, anchor, cand, a.geometry):
            return None
        return cand, a

    # -- placement ---------------------------------------------------------
    def choose_pattern(self, d, rest=False):
        if rest:
            return PATTERNS["rest"]
        names = list(PATTERNS)
        weights = [max(0.0, PATTERNS[n].weight(d)) for n in names]
        return PATTERNS[self.rng.choices(names, weights=weights)[0]]

    def place_step(self, ctx, anchor, pattern, step, target, min_y, accept=None):
        """Pick the pattern candidate whose difficulty is closest to target."""
        best, best_score = None, math.inf
        for _ in range(self.candidates):
            x0, x1, y = pattern.propose(anchor, step, target)
            res = self.evaluate(ctx, anchor, x0, x1, y, min_y)
            if res is None or (accept and not accept(res[0])):
                continue
            score = abs(res[1].difficulty - target) + self.rng.random() * 0.02
            if score < best_score:
                best, best_score = res, score
        if best is None:
            best = self.exhaustive(ctx, anchor, target, min_y, accept)
        return best

    def exhaustive(self, ctx, anchor, target, min_y, accept=None):
        """Fallback: brute-force every small platform above the anchor."""
        best, best_score = None, math.inf
        max_dy = self.model.max_rise_tiles()
        for dy in range(1, max_dy + 1):
            for w in range(2, 7):
                for x0 in range(INTERIOR_MIN_X, INTERIOR_MAX_X - w + 2):
                    res = self.evaluate(ctx, anchor, x0, x0 + w - 1, anchor.y - dy, min_y)
                    if res is None or (accept and not accept(res[0])):
                        continue
                    score = abs(res[1].difficulty - target)
                    if score < best_score:
                        best, best_score = res, score
        return best

    def commit(self, ctx, anchor, cand, assessment, pattern_name, target):
        cand.pid = self.new_pid()
        cand.pattern = pattern_name
        cand.difficulty = assessment.difficulty
        cand.jumps_required = assessment.jumps_required
        cand.arrival_dir = assessment.geometry.direction
        cand.target = target
        ctx.platforms.append(cand)
        ctx.corridors.append((assessment.geometry.corridor, (anchor.pid, cand.pid)))
        # Keep only the recent past; platforms far below can't interfere.
        if len(ctx.corridors) > 40:
            del ctx.corridors[:-40]
        return cand

    # -- gems --------------------------------------------------------------
    def place_gem(self, ctx, anchor, platform, assessment, target, arc_bias=0.0,
                  min_y=-10**6):
        """Put a gem on the platform, mid-jump (arc) or on a side branch.

        Riskier placements become more likely as difficulty rises.
        Returns the list of platforms created (a branch, if any).
        """
        r = self.rng
        geo = assessment.geometry
        arc_ok = (not geo.sidestep and geo.gap_tiles >= 2
                  and assessment.jumps_required < self.model.max_jumps)
        if arc_ok and r.random() < clamp(0.15 + 0.5 * target + arc_bias, 0, 0.9):
            gem = self._arc_gem(anchor, platform, geo)
            if gem is not None:
                platform.gems.append(gem)
                return []
        if r.random() < 0.1 + 0.25 * target:
            branch = self._branch(ctx, platform, target, min_y)
            if branch is not None:
                gx, gy = branch.gem_slot()
                branch.gems.append(Gem(self.new_gid(), gx, gy, "branch", branch.pid))
                return [branch]
        gx, gy = platform.gem_slot()
        platform.gems.append(Gem(self.new_gid(), gx, gy, "ledge", platform.pid))
        return []

    def _arc_gem(self, a, b, geo):
        # Centre of the gap, two rows above the higher surface.
        if geo.direction > 0:
            cols = (a.x1 + 1, b.x0 - 1)
        else:
            cols = (b.x1 + 1, a.x0 - 1)
        cx = (cols[0] + cols[1] + 1) * TILE_SIZE / 2
        row = min(a.y, b.y) - 2
        # Must be reachable from a with a jump to spare to finish onto b.
        dx = abs(cx - (a.x1 + 1 if geo.direction > 0 else a.x0) * TILE_SIZE)
        dy = (a.y - (row + 1)) * TILE_SIZE - PLAYER_HEIGHT + 2
        n = self.model.min_jumps(dx, dy)
        if n is None or n >= self.model.max_jumps:
            return None
        return Gem(self.new_gid(), cx - GEM_SIZE / 2, row * TILE_SIZE, "arc", b.pid)

    def _branch(self, ctx, anchor, target, min_y):
        """A small off-path ledge reachable from anchor (a tempting detour)."""
        best = None
        for _ in range(self.candidates):
            w = self.rng.randint(1, 3)
            dy = self.rng.randint(1, 4)
            x0 = self.rng.randint(INTERIOR_MIN_X, INTERIOR_MAX_X - w + 1)
            res = self.evaluate(ctx, anchor, x0, x0 + w - 1, anchor.y - dy, min_y)
            if res is None:
                continue
            if best is None or abs(res[1].difficulty - target) < abs(best[1].difficulty - target):
                best = res
        if best is None:
            return None
        cand, a = best
        cand.index = anchor.index
        cand.on_path = False
        return self.commit(ctx, anchor, cand, a, "branch", target)


# ---------------------------------------------------------------------------
# Helpers for tools/tests
# ---------------------------------------------------------------------------

def render_ascii(platforms, top_row, bottom_row=19, gems=True):
    """Tiny text view of a tower: '#' platform, '*' gem, '|' walls."""
    grid = {}
    for p in platforms:
        ch = "=" if p.on_path else "-"
        for x, y in p.tiles():
            grid[(x, y)] = ch
        if gems:
            for g in p.gems:
                grid[(int((g.x + GEM_SIZE / 2) // TILE_SIZE), int(g.y // TILE_SIZE))] = "*"
    lines = []
    for y in range(top_row, bottom_row + 1):
        row = "".join(grid.get((x, y), " ") for x in range(INTERIOR_MIN_X, INTERIOR_MAX_X + 1))
        lines.append(f"{y:5d} |{row}|")
    return "\n".join(lines)
