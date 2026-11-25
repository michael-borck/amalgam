"""
Frame layout: where every rod, motor and bracket of the Scaffold frame sits.

This module is the single source of truth for positions. Part scripts and
tests read it instead of inventing coordinates, so a part can be checked
against the parts around it. It is plain Python with no build123d import,
so the analysis tools can use it too.

Coordinates
-----------
Origin is the centre of the frame footprint, on top of the MDF.
+X is right, +Y is back, +Z is up. The front of the printer is -Y.

What the dimensions mean
-----------------------
skeleton_x  distance between the left and right vertical rods
skeleton_y  distance between the front and back vertical rods
skeleton_z  distance between the bottom and top X rods

How the frame is sized
----------------------
`minimum_skeleton` derives each dimension from what has to fit: the gantry's
travel, the bed's travel, and the stack of parts under and over the bed.
Every assumption is a named field of LayoutConfig, so changing one changes the
frame. `build_layout` then places every rod from the chosen dimensions, and
`problems()` reports anything that no longer fits.

Design intent: adjustment over accuracy
--------------------------------------
This frame is for people building with a hacksaw and a donor printer, so
nothing may depend on a part being made exactly right:

* Every rod passes through its bracket and is set by nuts, so a position is
  adjusted after printing rather than printed in.
* At a corner the three rods are offset from each other (tractor_01, the
  RepRap Darwin "offset method"), so none touches another and each is
  clamped on its own.
* The bed is carried on three leadscrews (ADR-005) and guided by two smooth
  rods (ADR-021). The screws only drive. The rods only guide.
* The XY gantry rides on top of the frame (ADR-023) and the X motor sits on
  the gantry, so nothing hangs outboard of the frame's sides.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

Vec3 = tuple[float, float, float]

FRONT, BACK = -1.0, 1.0
LEFT, RIGHT = -1.0, 1.0

CORNERS = (
    ("front_left", FRONT, LEFT),
    ("front_right", FRONT, RIGHT),
    ("back_left", BACK, LEFT),
    ("back_right", BACK, RIGHT),
)


# ---------------------------------------------------------------------------
# Small geometry helpers, all in plain tuples so no CAD library is needed
# ---------------------------------------------------------------------------
def _add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _mul(a: Vec3, s: float) -> Vec3:
    return (a[0] * s, a[1] * s, a[2] * s)


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _clamp01(v: float) -> float:
    return 0.0 if v < 0.0 else 1.0 if v > 1.0 else v


def ceil_to(value: float, step: float) -> float:
    """Round up to a multiple of `step`, such as a rod length a builder can cut."""
    return math.ceil(value / step - 1e-9) * step


def closest_points(p1: Vec3, q1: Vec3, p2: Vec3, q2: Vec3) -> tuple[Vec3, Vec3]:
    """
    Closest points on two line segments.

    This is the standard closest-point test for segments, from Ericson's
    "Real-Time Collision Detection". It is used both to measure how close two
    rods come and to find where a rod passes through its bracket.
    """
    a, b, _, _ = _closest(p1, q1, p2, q2)
    return a, b


def _closest(p1: Vec3, q1: Vec3, p2: Vec3, q2: Vec3) -> tuple[Vec3, Vec3, float, float]:
    """Closest points, with where they lie along each segment (0=start, 1=end)."""
    d1, d2, r = _sub(q1, p1), _sub(q2, p2), _sub(p1, p2)
    a, e, f = _dot(d1, d1), _dot(d2, d2), _dot(d2, r)
    tiny = 1e-12
    if a <= tiny and e <= tiny:
        s = t = 0.0
    elif a <= tiny:
        s, t = 0.0, _clamp01(f / e)
    else:
        c = _dot(d1, r)
        if e <= tiny:
            t, s = 0.0, _clamp01(-c / a)
        else:
            b = _dot(d1, d2)
            denom = a * e - b * b
            s = _clamp01((b * f - c * e) / denom) if denom > tiny else 0.0
            t = (b * s + f) / e
            if t < 0.0:
                t, s = 0.0, _clamp01(-c / a)
            elif t > 1.0:
                t, s = 1.0, _clamp01((b - c) / a)
    return _add(p1, _mul(d1, s)), _add(p2, _mul(d2, t)), s, t


def segment_distance(p1: Vec3, q1: Vec3, p2: Vec3, q2: Vec3) -> float:
    a, b = closest_points(p1, q1, p2, q2)
    return math.dist(a, b)


def rod_gap(a: "Rod", b: "Rod") -> float:
    """
    Surface-to-surface gap between two rods, 0 when they overlap.

    A rod only loses its radius where the other rod meets its side. Where the
    other rod meets its flat end it loses nothing, which is why the top of a
    vertical rod can sit closer under a horizontal rod than a side can.
    """
    pa, pb, s, t = _closest(a.start, a.end, b.start, b.end)
    gap = math.dist(pa, pb)
    if not _meets_flat_end(a, s, _sub(pb, pa)):
        gap -= a.diameter / 2
    if not _meets_flat_end(b, t, _sub(pa, pb)):
        gap -= b.diameter / 2
    return max(gap, 0.0)


def _meets_flat_end(rod: "Rod", where: float, between: Vec3) -> bool:
    """
    True when the other rod meets this rod's end rather than its side.

    Both must hold: the closest point is one of the rod's ends, and the way
    in runs along the rod's axis. Parallel rods report their ends as closest
    points too, but they meet side to side, which is why the direction is
    checked as well.
    """
    if 1e-9 < where < 1 - 1e-9:
        return False
    axis = _sub(rod.end, rod.start)
    length, approach = math.hypot(*axis), math.hypot(*between)
    if length < 1e-9 or approach < 1e-9:
        return True
    return abs(_dot(axis, between)) / (length * approach) > 0.999


@dataclass(frozen=True)
class Box:
    """An axis-aligned box, given by its low and high corners."""

    lo: Vec3
    hi: Vec3

    @property
    def size(self) -> Vec3:
        return _sub(self.hi, self.lo)

    def gap(self, other: "Box") -> float:
        """Distance between two boxes, 0 when they overlap or touch."""
        deltas = []
        for i in range(3):
            if self.hi[i] < other.lo[i]:
                deltas.append(other.lo[i] - self.hi[i])
            elif other.hi[i] < self.lo[i]:
                deltas.append(self.lo[i] - other.hi[i])
        return math.hypot(*deltas) if deltas else 0.0

    def hits_segment(self, p: Vec3, q: Vec3) -> bool:
        """True when the segment from p to q passes through the box."""
        t0, t1 = 0.0, 1.0
        for i in range(3):
            d = q[i] - p[i]
            if abs(d) < 1e-12:
                if p[i] < self.lo[i] or p[i] > self.hi[i]:
                    return False
                continue
            ta, tb = (self.lo[i] - p[i]) / d, (self.hi[i] - p[i]) / d
            if ta > tb:
                ta, tb = tb, ta
            t0, t1 = max(t0, ta), min(t1, tb)
            if t0 > t1:
                return False
        return True


@dataclass(frozen=True)
class Rod:
    """A straight rod, described by its centreline."""

    name: str
    kind: str  # "frame", "motion", "z_guide" or "z_screw"
    diameter: float
    start: Vec3
    end: Vec3
    note: str = ""

    @property
    def length(self) -> float:
        return math.dist(self.start, self.end)

    @property
    def axis(self) -> str:
        d = _sub(self.end, self.start)
        return "XYZ"[max(range(3), key=lambda i: abs(d[i]))]

    def box(self) -> Box:
        r = self.diameter / 2
        return Box(
            tuple(min(a, b) - r for a, b in zip(self.start, self.end)),
            tuple(max(a, b) + r for a, b in zip(self.start, self.end)),
        )


@dataclass(frozen=True)
class CornerBlock:
    """The envelope of one printed corner bracket."""

    name: str
    rods: tuple[str, ...]
    box: Box


@dataclass(frozen=True)
class Problem:
    check: str
    message: str


# ---------------------------------------------------------------------------
# Assumptions
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LayoutConfig:
    """
    Every assumption behind the layout, in millimetres.

    The defaults are the reference spec. Fields cite the decision record
    behind them where there is one. Fields marked "assumed" are engineering
    estimates to be confirmed against real hardware or a printed part.
    """

    # Build volume. ADR-024 reference.
    bed_x: float = 220.0
    bed_y: float = 220.0
    build_z: float = 220.0

    # Frame rod, M10 threaded (ADR-001).
    rod_dia: float = 10.0
    rod_fit_dia: float = 10.5  # bore diameter, nominal + lumpy factor

    # Corner joint, the offset method (tractor_01).
    rod_offset: float = (
        20.0  # plan distance from the vertical rod to each horizontal rod
    )
    layer_step: float = 20.0  # height between the X rod and the Y rod at a corner
    wall: float = 6.5  # material wanted between a bore and the outside of a block
    nut_seat: float = 11.0  # clear radius around a bore for an M10 washer and nut
    flange_thickness: float = 15.0  # base-anchor flange under each bottom block
    rod_overhang: float = 15.0  # thread past a block for nut, washer and a stub
    plinth_thickness: float = 36.0  # ADR-011, two 18 mm boards
    min_clearance: float = 3.0

    # XY gantry on top of the frame (ADR-021, ADR-023, tractor_02).
    motion_rod_dia: float = 8.0
    rod_stack: float = 30.0  # vertical spacing of a stacked rod pair, ADR-021
    bearing_od: float = 15.0  # LM8UU outside diameter
    x_rod_lift: float = 50.0  # X rod stack centre above the Y rod stack centre, assumed
    x_end_width: float = 25.0  # X-end block thickness along X, assumed
    x_rod_insertion: float = 20.0  # X rod inside its end block, assumed
    x_end_length: float = 70.0  # X-end block length along Y: two LM8UU per rod, assumed
    x_carriage_length: float = 70.0  # the plough along X: two LM8LUU per rod, assumed
    travel_end_margin: float = 5.0  # bearing to end block at the ends of travel
    y_end_margin: float = 15.0  # X-end block to corner block at the ends of travel
    bed_block_gap: float = 15.0  # bed plate to corner block
    gantry_lift: float = 35.0  # lower Y motion rod above the top X rod, assumed
    y_rod_end: float = 10.0  # Y motion rod past the corner blocks, assumed
    nozzle_below_rods: float = 35.0  # nozzle tip below the X rod axes, assumed
    nozzle_y_offset: float = 30.0  # nozzle in front of the X rod plane, assumed
    toolhead_front_reach: float = 45.0  # toolhead in front of the X rod plane, assumed
    toolhead_back_reach: float = 35.0  # toolhead behind the X rod plane, assumed
    gantry_underside: float = 5.0  # lowest gantry part above the nozzle tip, assumed

    # Z system: three leadscrews (ADR-005) and two guide rods (ADR-021).
    z_motor_height: float = 48.0  # NEMA17 body, assumed
    z_coupler_height: float = 25.0  # shaft coupler, assumed
    z_nut_above_coupler: float = 10.0  # nut never comes closer than this to the coupler
    z_nut_housing: float = 10.0
    spider_arm_height: float = 12.0
    bed_carrier: float = 6.0  # printed plate under the heater
    bed_plate: float = 3.0  # aluminium heater plate
    bed_surface: float = 3.0  # glass
    z_screw_bed_gap: float = 15.0  # leadscrew axis outside the bed plate
    z_screw_top_margin: float = 10.0  # screw past the nut with the bed at its highest
    z_screw_dia: float = 8.0
    guide_rod_dia: float = 8.0
    guide_rod_inset: float = 50.0  # guide rods in from the bed's side edges, assumed
    puck_half: float = 15.0  # half the height of a clamp puck, assumed
    guide_bearing_below_surface: float = (
        12.0  # top of the bed's guide bearings, assumed
    )
    guide_top_margin: float = 5.0


# ---------------------------------------------------------------------------
# Sizing
# ---------------------------------------------------------------------------
def block_inboard(c: LayoutConfig) -> float:
    """From the vertical rod's axis to the block's inner face."""
    return c.rod_fit_dia / 2 + c.wall


def block_outboard(c: LayoutConfig) -> float:
    """From the vertical rod's axis to the block's outer face."""
    return max(c.rod_offset + c.nut_seat, c.rod_offset + c.rod_fit_dia / 2 + c.wall)


def bed_lowest(c: LayoutConfig) -> float:
    """Bed surface at Z=0, above the plinth: everything stacked under the bed."""
    return (
        c.z_motor_height
        + c.z_coupler_height
        + c.z_nut_above_coupler
        + c.z_nut_housing
        + c.spider_arm_height
        + c.bed_carrier
        + c.bed_plate
        + c.bed_surface
    )


def gantry_reach(c: LayoutConfig) -> tuple[float, float]:
    """How far the gantry extends in front of, and behind, the X rod plane."""
    return (
        max(c.x_end_length / 2, c.toolhead_front_reach),
        max(c.x_end_length / 2, c.toolhead_back_reach),
    )


def minimum_skeleton(
    config: Optional[LayoutConfig] = None,
) -> tuple[float, float, float]:
    """
    The smallest frame that fits everything, as (x, y, z).

    These are exact values. `builder_skeleton` rounds them up for builders.
    """
    c = config or LayoutConfig()
    b_in = block_inboard(c)
    reach_front, reach_back = gantry_reach(c)

    min_x = max(
        c.bed_x + c.x_carriage_length + 2 * c.travel_end_margin + c.x_end_width,
        c.bed_x + 2 * (c.bed_block_gap + b_in),
    )
    min_y = c.bed_y + reach_front + reach_back + 2 * c.y_end_margin + 2 * b_in

    # Height of the nozzle above the top X rod: cradle, Y rod stack, the X
    # rod lift, then down to the nozzle.
    nozzle_above_top = (
        c.gantry_lift + c.rod_stack / 2 + c.x_rod_lift - c.nozzle_below_rods
    )
    min_z = bed_lowest(c) + c.build_z - nozzle_above_top - (c.flange_thickness + b_in)
    return min_x, min_y, min_z


def builder_skeleton(
    config: Optional[LayoutConfig] = None, step: float = 5.0
) -> tuple[float, float, float]:
    """`minimum_skeleton` rounded up to a multiple of `step`."""
    return tuple(ceil_to(v, step) for v in minimum_skeleton(config))  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FrameLayout:
    config: LayoutConfig
    skeleton_x: float
    skeleton_y: float
    skeleton_z: float
    bed_center_y: float
    rods: tuple[Rod, ...]
    blocks: tuple[CornerBlock, ...]

    # Heights above the plinth
    z_bottom_x: float
    z_bottom_y: float
    z_top_x: float
    z_top_y: float
    y_rod_low: float
    y_rod_high: float
    x_rod_low: float
    x_rod_high: float
    bed_lowest: float
    bed_first: float
    gantry_front: float  # X rod plane with the nozzle over the front of the bed
    gantry_back: float  # X rod plane with the nozzle over the back of the bed

    def rod(self, name: str) -> Rod:
        for rod in self.rods:
            if rod.name == name:
                return rod
        raise KeyError(name)

    def block(self, name: str) -> CornerBlock:
        for block in self.blocks:
            if block.name == name:
                return block
        raise KeyError(name)

    def rods_of(self, kind: str) -> tuple[Rod, ...]:
        return tuple(r for r in self.rods if r.kind == kind)

    # -- key positions -----------------------------------------------------
    @property
    def hx(self) -> float:
        return self.skeleton_x / 2

    @property
    def hy(self) -> float:
        return self.skeleton_y / 2

    @property
    def inner_front(self) -> float:
        """Y of the front corner blocks' inner faces."""
        return -self.hy + block_inboard(self.config)

    @property
    def inner_back(self) -> float:
        return self.hy - block_inboard(self.config)

    @property
    def front_reach(self) -> float:
        return gantry_reach(self.config)[0]

    @property
    def back_reach(self) -> float:
        return gantry_reach(self.config)[1]

    @property
    def z_travel(self) -> float:
        return self.bed_first - self.bed_lowest

    @property
    def guide_inboard(self) -> float:
        """Guide rods sit this far inboard of the front X rods' plane."""
        c = self.config
        return c.rod_fit_dia / 2 + c.guide_rod_dia / 2 + c.wall

    @property
    def guide_rod_y(self) -> float:
        return -(self.hy + self.config.rod_offset - self.guide_inboard)

    @property
    def guide_rod_x(self) -> float:
        return self.config.bed_x / 2 - self.config.guide_rod_inset

    @property
    def screw_xy(self) -> dict[str, tuple[float, float]]:
        c = self.config
        fx = c.bed_x / 2 + c.z_screw_bed_gap
        fy = self.bed_center_y - c.bed_y / 2 - c.z_screw_bed_gap
        by = self.bed_center_y + c.bed_y / 2 + c.z_screw_bed_gap
        return {
            "z_screw_front_left": (-fx, fy),
            "z_screw_front_right": (fx, fy),
            "z_screw_back_centre": (0.0, by),
        }

    def bed_box(self) -> Box:
        """The bed plate through its whole travel, including what is under it."""
        c = self.config
        return Box(
            (
                -c.bed_x / 2,
                self.bed_center_y - c.bed_y / 2,
                self.bed_lowest - c.bed_surface - c.bed_plate - c.bed_carrier,
            ),
            (c.bed_x / 2, self.bed_center_y + c.bed_y / 2, self.bed_first),
        )

    def gantry_sweep(self) -> Box:
        """Everything the moving gantry passes through."""
        c = self.config
        return Box(
            (
                -self.hx - c.x_end_width / 2,
                self.gantry_front - self.front_reach,
                self.bed_first + c.gantry_underside,
            ),
            (
                self.hx + c.x_end_width / 2,
                self.gantry_back + self.back_reach,
                self.y_rod_high + c.x_rod_lift + c.rod_stack,
            ),
        )

    def guide_supports(self) -> tuple[Box, ...]:
        """
        Where the top of each Z guide rod is held.

        The bed's guide bearings reach nearly to the first layer, so the
        supports holding the tops of the guide rods reach into the height
        the gantry moves through. They are the only fixed parts that do,
        and they have to stay clear of its path.
        """
        c = self.config
        z_lo = self.bed_first - c.guide_bearing_below_surface + c.guide_top_margin
        out = []
        for rod in self.rods_of("z_guide"):
            x, y = rod.start[0], rod.start[1]
            out.append(
                Box(
                    (x - c.puck_half, y - c.puck_half, z_lo),
                    (x + c.puck_half, y + c.puck_half, z_lo + 2 * c.puck_half),
                )
            )
        return tuple(out)

    # -- cut list and stack ------------------------------------------------
    def cut_list(self, step: float = 5.0) -> dict[str, float]:
        """Rod cut lengths rounded up to `step`, keyed by rod name."""
        return {rod.name: ceil_to(rod.length, step) for rod in self.rods}

    def stack_up(self) -> list[tuple[str, float]]:
        """What sits under the bed at Z=0, and the running total."""
        c = self.config
        terms = [
            ("Z motor body", c.z_motor_height),
            ("shaft coupler", c.z_coupler_height),
            ("nut clear of coupler", c.z_nut_above_coupler),
            ("lead nut housing", c.z_nut_housing),
            ("spider arm", c.spider_arm_height),
            ("bed carrier", c.bed_carrier),
            ("heater plate", c.bed_plate),
            ("bed surface", c.bed_surface),
        ]
        out, total = [], 0.0
        for label, value in terms:
            total += value
            out.append((label, total))
        return out

    # -- checks ------------------------------------------------------------
    def problems(self) -> list[Problem]:
        out: list[Problem] = []
        for check in CHECKS:
            out.extend(getattr(self, "_check_" + check)())
        return out

    def _say(self, check: str, message: str) -> list[Problem]:
        return [Problem(check, message)]

    def _check_rod_clearance(self) -> list[Problem]:
        """No two rods may touch. Space left for material between them."""
        c = self.config
        out = []
        for i, a in enumerate(self.rods):
            for b in self.rods[i + 1 :]:
                gap = rod_gap(a, b)
                if gap < c.min_clearance - 1e-6:
                    out.append(
                        Problem(
                            CHECK_ROD_CLEARANCE,
                            f"{a.name} and {b.name} leave {gap:.2f} mm, need {c.min_clearance:.0f}",
                        )
                    )
        return out

    def _check_corner_joints(self) -> list[Problem]:
        """Each bracket joins three rods, and the joint happens inside it."""
        out = []
        for block in self.blocks:
            names = block.rods
            if len(names) != 3:
                out += self._say(
                    CHECK_CORNER_JOINTS, f"{block.name} joins {len(names)} rods, not 3"
                )
                continue
            for i, na in enumerate(names):
                for nb in names[i + 1 :]:
                    a, b = self.rod(na), self.rod(nb)
                    pa, pb = closest_points(a.start, a.end, b.start, b.end)
                    for point in (pa, pb):
                        if not block.box.hits_segment(point, point):
                            out += self._say(
                                CHECK_CORNER_JOINTS,
                                f"{na} and {nb} come closest outside {block.name}",
                            )
        for rod in self.rods:
            if rod.kind != "frame":
                continue
            n = sum(block.box.hits_segment(rod.start, rod.end) for block in self.blocks)
            if n != 2:
                out += self._say(
                    CHECK_CORNER_JOINTS,
                    f"{rod.name} passes through {n} brackets, need 2",
                )
        return out

    def _check_bed_path(self) -> list[Problem]:
        """The bed plate clears the frame and the Z parts through its whole travel."""
        c = self.config
        bed = self.bed_box()
        out = []
        for block in self.blocks:
            gap = bed.gap(block.box)
            if gap < c.bed_block_gap - 1e-6:
                out += self._say(
                    CHECK_BED_PATH,
                    f"bed is {gap:.1f} mm from {block.name}, need {c.bed_block_gap:.0f}",
                )
        for rod in self.rods:
            if rod.kind == "frame":
                gap = bed.gap(rod.box())
                if gap < c.min_clearance - 1e-6:
                    out += self._say(
                        CHECK_BED_PATH,
                        f"bed is {gap:.1f} mm from {rod.name}, need {c.min_clearance:.0f}",
                    )
            elif rod.kind in ("z_guide", "z_screw"):
                # The gap is stated from the rod's axis, so add its radius back.
                axis_gap = bed.gap(rod.box()) + rod.diameter / 2
                need = c.z_screw_bed_gap
                if axis_gap < need - 1e-6:
                    out += self._say(
                        CHECK_BED_PATH,
                        f"bed plate is {axis_gap:.1f} mm from the {rod.name} axis, need {need:.0f}",
                    )
        return out

    def _check_x_travel(self) -> list[Problem]:
        """The X rods carry the plough over the full bed width."""
        c = self.config
        have = self.skeleton_x - c.x_end_width
        need = c.bed_x + c.x_carriage_length + 2 * c.travel_end_margin
        out = []
        if have < need - 1e-6:
            out += self._say(
                CHECK_X_TRAVEL, f"X rods support {have:.1f} mm, need {need:.1f}"
            )
        if c.x_rod_insertion > c.x_end_width:
            out += self._say(
                CHECK_X_TRAVEL, "X rod insertion is longer than the end block"
            )
        return out

    def _check_y_travel(self) -> list[Problem]:
        """The X-end blocks clear the corner blocks at both ends of travel."""
        c = self.config
        out = []
        front = self.gantry_front - self.front_reach - self.inner_front
        back = self.inner_back - (self.gantry_back + self.back_reach)
        if front < c.y_end_margin - 1e-6:
            out += self._say(
                CHECK_Y_TRAVEL,
                f"gantry comes within {front:.1f} mm of the front blocks, need {c.y_end_margin:.0f}",
            )
        if back < c.y_end_margin - 1e-6:
            out += self._say(
                CHECK_Y_TRAVEL,
                f"gantry comes within {back:.1f} mm of the back blocks, need {c.y_end_margin:.0f}",
            )
        return out

    def _check_z_travel(self) -> list[Problem]:
        c = self.config
        if self.z_travel < c.build_z - 1e-6:
            return self._say(
                CHECK_Z_TRAVEL,
                f"bed travels {self.z_travel:.1f} mm, need {c.build_z:.0f}",
            )
        return []

    def _check_gantry_sweep(self) -> list[Problem]:
        """
        Nothing fixed may stand in the volume the gantry moves through.

        The frame rods and brackets are all below the gantry, so they pass
        this without effort. The tops of the Z guide rods are what it is
        really for.
        """
        c = self.config
        sweep = self.gantry_sweep()
        out = []
        fixed = [(b.name, b.box) for b in self.blocks]
        fixed += [(r.name, r.box()) for r in self.rods if r.kind == "frame"]
        fixed += [
            (f"{rod.name} top support", box)
            for rod, box in zip(self.rods_of("z_guide"), self.guide_supports())
        ]
        for name, box in fixed:
            gap = sweep.gap(box)
            if gap < c.min_clearance - 1e-6:
                out += self._say(
                    CHECK_GANTRY_SWEEP,
                    f"gantry sweep is {gap:.1f} mm from {name}, need {c.min_clearance:.0f}",
                )
        return out

    def _check_gantry_bearings(self) -> list[Problem]:
        """The X rods sit outside the Y bearings, and the Y rods clear the
        nuts on top of the vertical rods."""
        c = self.config
        out = []
        wall = (c.x_rod_lift - c.rod_stack) - c.bearing_od / 2 - c.motion_rod_dia / 2
        if wall < c.wall - 1e-6:
            out += self._say(
                CHECK_GANTRY_BEARINGS,
                f"X rods leave {wall:.1f} mm of block above the Y bearings, need {c.wall:.1f}",
            )
        for rod in self.rods_of("motion"):
            if rod.name.startswith("y_motion_lower"):
                vertical_top = self.z_top_x + block_inboard(c) + c.rod_overhang
                clear = rod.start[2] - rod.diameter / 2 - vertical_top
                if clear < c.min_clearance - 1e-6:
                    out += self._say(
                        CHECK_GANTRY_BEARINGS,
                        f"{rod.name} is {clear:.1f} mm above the vertical rods' top nuts, need {c.min_clearance:.0f}",
                    )
        return out

    def _check_printable(self) -> list[Problem]:
        """The brackets fit on a donor printer's bed."""
        c = self.config
        out = []
        for block in self.blocks:
            sx, sy, _ = block.box.size
            if sx > c.bed_x or sy > c.bed_y:
                out += self._say(
                    CHECK_PRINTABLE,
                    f"{block.name} is {sx:.0f} x {sy:.0f} mm, too big for the bed",
                )
        return out

    # -- reporting ---------------------------------------------------------
    def summary(self) -> str:
        """The layout as a table, for builders and for review."""
        c = self.config
        cut = self.cut_list()
        least = minimum_skeleton(c)
        lines = [
            f"Frame, between vertical rods: {self.skeleton_x:.1f} x {self.skeleton_y:.1f} mm",
            f"Frame height, bottom to top X rod: {self.skeleton_z:.1f} mm",
            f"Smallest that fits: {least[0]:.1f} x {least[1]:.1f} x {least[2]:.1f} mm",
            "",
            "M10 RODS  name                       axis  length  cut   from            to",
        ]
        for rod in self.rods:
            if rod.kind != "frame":
                continue
            s, e = rod.start, rod.end
            lines.append(
                f"          {rod.name:<26} {rod.axis}     {rod.length:6.1f} {cut[rod.name]:5.0f}  "
                f"({s[0]:6.1f},{s[1]:6.1f},{s[2]:6.1f}) ({e[0]:6.1f},{e[1]:6.1f},{e[2]:6.1f})"
            )
        lines += [
            "",
            "SMOOTH RODS AND LEADSCREWS  name                   length   cut   position",
        ]
        for rod in self.rods:
            if rod.kind == "frame":
                continue
            s = rod.start
            lines.append(
                f"          {rod.name:<26} {rod.length:6.1f} {cut[rod.name]:5.0f}  "
                f"x={s[0]:6.1f} y={s[1]:6.1f} z {min(s[2], rod.end[2]):6.1f}..{max(s[2], rod.end[2]):6.1f}"
            )
        lines += [
            "",
            "POSITIONS",
            f"  bed centre              x=   0.0  y={self.bed_center_y:6.1f}",
            f"  bed surface, Z=0        z={self.bed_lowest:6.1f}  above the plinth",
            f"  bed surface, first layer z={self.bed_first:6.1f}",
            f"  X-rod plane, travel      y={self.gantry_front:6.1f} .. {self.gantry_back:6.1f}",
            f"  Y motion rods            x=+/-{self.hx:5.1f}  z={self.y_rod_low:6.1f} and {self.y_rod_high:6.1f}",
            f"  X motion rods            z={self.x_rod_low:6.1f} and {self.x_rod_high:6.1f}",
            f"  Z guide rods             x=+/-{self.guide_rod_x:5.1f}  y={self.guide_rod_y:6.1f}",
        ]
        for name, (x, y) in self.screw_xy.items():
            lines.append(f"  {name:<24} x={x:6.1f}  y={y:6.1f}")
        lines += ["", "STACK UNDER THE BED AT Z=0"]
        for label, total in self.stack_up():
            lines.append(f"  {label:<24} {total:6.1f}")
        return "\n".join(lines)


CHECK_ROD_CLEARANCE = "rod_clearance"
CHECK_CORNER_JOINTS = "corner_joints"
CHECK_BED_PATH = "bed_path"
CHECK_X_TRAVEL = "x_travel"
CHECK_Y_TRAVEL = "y_travel"
CHECK_Z_TRAVEL = "z_travel"
CHECK_GANTRY_SWEEP = "gantry_sweep"
CHECK_GANTRY_BEARINGS = "gantry_bearings"
CHECK_PRINTABLE = "printable"

CHECKS = (
    CHECK_ROD_CLEARANCE,
    CHECK_CORNER_JOINTS,
    CHECK_BED_PATH,
    CHECK_X_TRAVEL,
    CHECK_Y_TRAVEL,
    CHECK_Z_TRAVEL,
    CHECK_GANTRY_SWEEP,
    CHECK_GANTRY_BEARINGS,
    CHECK_PRINTABLE,
)


def build_layout(
    config: Optional[LayoutConfig] = None,
    skeleton: Optional[tuple[float, float, float]] = None,
) -> FrameLayout:
    """
    Place every rod from the frame dimensions.

    Args:
        config: the assumptions. Defaults to the reference spec.
        skeleton: (x, y, z) frame dimensions. Defaults to the smallest frame
            that fits, so a default layout has no problems by construction.
    """
    c = config or LayoutConfig()
    b_in = block_inboard(c)
    b_out = block_outboard(c)
    sx, sy, sz = skeleton if skeleton is not None else minimum_skeleton(c)
    hx, hy = sx / 2, sy / 2

    # Heights, from the plinth up.
    z_bottom_x = c.flange_thickness + b_in
    z_bottom_y = z_bottom_x + c.layer_step
    z_top_x = z_bottom_x + sz
    z_top_y = z_top_x - c.layer_step
    y_rod_low = z_top_x + c.gantry_lift
    y_rod_high = y_rod_low + c.rod_stack
    y_rod_mid = (y_rod_low + y_rod_high) / 2
    x_rod_low = y_rod_mid + c.x_rod_lift - c.rod_stack / 2
    x_rod_high = x_rod_low + c.rod_stack
    bed_first = (x_rod_low + x_rod_high) / 2 - c.nozzle_below_rods
    lowest = bed_lowest(c)

    # Depth: put the gantry's travel where it clears both pairs of blocks.
    inner_front, inner_back = -hy + b_in, hy - b_in
    reach_front, reach_back = gantry_reach(c)
    room = (inner_back - c.y_end_margin - reach_back) - (
        inner_front + c.y_end_margin + reach_front
    )
    gantry_front = (
        inner_front + c.y_end_margin + reach_front + max(room - c.bed_y, 0.0) / 2
    )
    gantry_back = gantry_front + c.bed_y
    # The nozzle is in front of the X rod plane, so the bed sits further
    # forward than the middle of the X rods' own travel.
    bed_center_y = gantry_front + c.bed_y / 2 - c.nozzle_y_offset

    # Frame rods.
    ox = hx + b_out + c.rod_overhang
    oy = hy + b_out + c.rod_overhang
    rods: list[Rod] = []
    for level, zx, zy in (
        ("bottom", z_bottom_x, z_bottom_y),
        ("top", z_top_x, z_top_y),
    ):
        for side, s in (("front", FRONT), ("back", BACK)):
            rods.append(
                Rod(
                    f"{level}_{side}_x",
                    "frame",
                    c.rod_dia,
                    (-ox, s * (hy + c.rod_offset), zx),
                    (ox, s * (hy + c.rod_offset), zx),
                    f"{level.title()} X rod",
                )
            )
        for side, s in (("left", LEFT), ("right", RIGHT)):
            rods.append(
                Rod(
                    f"{level}_{side}_y",
                    "frame",
                    c.rod_dia,
                    (s * (hx + c.rod_offset), -oy, zy),
                    (s * (hx + c.rod_offset), oy, zy),
                    f"{level.title()} Y rod",
                )
            )
    top_of_vertical = z_top_x + b_in + c.rod_overhang
    for corner, y_sign, x_sign in CORNERS:
        rods.append(
            Rod(
                f"vertical_{corner}",
                "frame",
                c.rod_dia,
                (x_sign * hx, y_sign * hy, -(c.plinth_thickness + c.rod_overhang)),
                (x_sign * hx, y_sign * hy, top_of_vertical),
                "Corner upright, through the plinth",
            )
        )

    # Corner blocks. Each joins the vertical rod with the X rod and the Y
    # rod that share its corner. The bottom block starts on the plinth; the
    # top block is the bottom one turned over.
    blocks: list[CornerBlock] = []
    for corner, y_sign, x_sign in CORNERS:
        front_back, left_right = corner.split("_")
        x_lo, x_hi = sorted((x_sign * (hx + b_out), x_sign * (hx - b_in)))
        y_lo, y_hi = sorted((y_sign * (hy + b_out), y_sign * (hy - b_in)))
        for level, z_lo, z_hi in (
            ("bottom", 0.0, z_bottom_y + b_in),
            ("top", z_top_y - b_in, z_top_x + b_in),
        ):
            blocks.append(
                CornerBlock(
                    f"{level}_{corner}",
                    (
                        f"{level}_{front_back}_x",
                        f"{level}_{left_right}_y",
                        f"vertical_{corner}",
                    ),
                    Box((x_lo, y_lo, z_lo), (x_hi, y_hi, z_hi)),
                )
            )

    # Gantry, drawn with the nozzle over the centre of the bed. The whole
    # gantry moves in Y; the plough moves in X.
    x_rod_end = hx - c.x_end_width / 2 + c.x_rod_insertion
    gantry_mid = bed_center_y + c.nozzle_y_offset
    for level, z in (("lower", x_rod_low), ("upper", x_rod_high)):
        rods.append(
            Rod(
                f"x_motion_{level}",
                "motion",
                c.motion_rod_dia,
                (-x_rod_end, gantry_mid, z),
                (x_rod_end, gantry_mid, z),
                "Moves in Y with the gantry",
            )
        )
    y_end = hy + c.y_rod_end
    for hand, s in (("left", LEFT), ("right", RIGHT)):
        for level, z in (("lower", y_rod_low), ("upper", y_rod_high)):
            rods.append(
                Rod(
                    f"y_motion_{level}_{hand}",
                    "motion",
                    c.motion_rod_dia,
                    (s * hx, -y_end, z),
                    (s * hx, y_end, z),
                    "Fixed. Carries an X-end block",
                )
            )

    # Z system. The screws sit just outside the bed plate; the guide rods
    # hang between the two front X rods, inboard of their plane.
    screw_bottom = c.z_motor_height + c.z_coupler_height
    nut_top_first = bed_first - (
        c.bed_surface
        + c.bed_plate
        + c.bed_carrier
        + c.spider_arm_height
        + c.z_nut_housing
    )
    screw_top = nut_top_first + c.z_screw_top_margin
    fx = c.bed_x / 2 + c.z_screw_bed_gap
    front_screw_y = bed_center_y - c.bed_y / 2 - c.z_screw_bed_gap
    back_screw_y = bed_center_y + c.bed_y / 2 + c.z_screw_bed_gap
    for name, x, y in (
        ("z_screw_front_left", -fx, front_screw_y),
        ("z_screw_front_right", fx, front_screw_y),
        ("z_screw_back_centre", 0.0, back_screw_y),
    ):
        rods.append(
            Rod(
                name,
                "z_screw",
                c.z_screw_dia,
                (x, y, screw_bottom),
                (x, y, screw_top),
                "Driven by a motor on a puck on the plinth",
            )
        )

    guide_x = c.bed_x / 2 - c.guide_rod_inset
    guide_y = -(hy + c.rod_offset - (c.rod_fit_dia / 2 + c.guide_rod_dia / 2 + c.wall))
    guide_lo = z_bottom_x - c.puck_half
    guide_hi = bed_first + c.guide_top_margin
    for hand, s in (("left", LEFT), ("right", RIGHT)):
        rods.append(
            Rod(
                f"z_guide_{hand}",
                "z_guide",
                c.guide_rod_dia,
                (s * guide_x, guide_y, guide_lo),
                (s * guide_x, guide_y, guide_hi),
                "Guides the bed. Held by pucks on the front X rods",
            )
        )

    return FrameLayout(
        config=c,
        skeleton_x=sx,
        skeleton_y=sy,
        skeleton_z=sz,
        bed_center_y=bed_center_y,
        rods=tuple(rods),
        blocks=tuple(blocks),
        z_bottom_x=z_bottom_x,
        z_bottom_y=z_bottom_y,
        z_top_x=z_top_x,
        z_top_y=z_top_y,
        y_rod_low=y_rod_low,
        y_rod_high=y_rod_high,
        x_rod_low=x_rod_low,
        x_rod_high=x_rod_high,
        bed_lowest=lowest,
        bed_first=bed_first,
        gantry_front=gantry_front,
        gantry_back=gantry_back,
    )
