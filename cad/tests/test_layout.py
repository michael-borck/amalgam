"""
Tests for the frame layout (amalgam.lib.layout).

Two kinds of test live here.

The first kind checks the reference layout against what the machine has to
do: nothing collides, the bed and the gantry reach their full travel, every
bracket joins three rods.

The second kind proves each check can fail. Every check in layout.CHECKS is
given a deliberately broken layout and must report a problem. A check that
cannot fail is not a check, and two earlier checks in this repo passed
everything while detecting nothing.
"""

import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

CAD_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAD_DIR))

from amalgam.lib import layout as L  # noqa: E402


# ---------------------------------------------------------------------------
# The geometry helpers, against answers worked out by hand
# ---------------------------------------------------------------------------
class TestGeometryHelpers:
    def test_perpendicular_lines(self):
        d = L.segment_distance((-10, 0, 0), (10, 0, 0), (0, -10, 5), (0, 10, 5))
        assert d == pytest.approx(5.0)

    def test_parallel_lines(self):
        d = L.segment_distance((0, 0, 0), (100, 0, 0), (0, 0, 10), (100, 0, 10))
        assert d == pytest.approx(10.0)

    def test_end_to_end(self):
        # Closest points are the ends (10,0,0) and (20,3,4)
        d = L.segment_distance((0, 0, 0), (10, 0, 0), (20, 3, 4), (30, 3, 4))
        assert d == pytest.approx(125**0.5)

    def test_closest_points_are_on_both_segments(self):
        pa, pb = L.closest_points((-10, 0, 0), (10, 0, 0), (0, -10, 5), (0, 10, 5))
        assert pa == pytest.approx((0, 0, 0))
        assert pb == pytest.approx((0, 0, 5))

    def test_rod_gap_meets_a_flat_end(self):
        # A vertical rod ending at z=10 under a horizontal rod at z=18.25.
        # The end is flat, so only the horizontal rod's radius is taken off.
        vertical = L.Rod("v", "frame", 10.0, (0, 0, 0), (0, 0, 10))
        horizontal = L.Rod("h", "motion", 8.0, (-50, 0, 18.25), (50, 0, 18.25))
        assert L.rod_gap(vertical, horizontal) == pytest.approx(4.25)

    def test_rod_gap_side_to_side(self):
        a = L.Rod("a", "frame", 10.0, (0, 0, 0), (100, 0, 0))
        b = L.Rod("b", "frame", 10.0, (0, 20, 0), (100, 20, 0))
        assert L.rod_gap(a, b) == pytest.approx(10.0)

    def test_rod_gap_never_negative(self):
        a = L.Rod("a", "frame", 10.0, (0, 0, 0), (100, 0, 0))
        b = L.Rod("b", "frame", 10.0, (50, -20, 0), (50, 20, 0))
        assert L.rod_gap(a, b) == 0.0

    def test_box_gap_overlapping_is_zero(self):
        a = L.Box((0, 0, 0), (10, 10, 10))
        b = L.Box((5, 5, 5), (15, 15, 15))
        assert a.gap(b) == 0.0

    def test_box_gap_separated(self):
        a = L.Box((0, 0, 0), (10, 10, 10))
        b = L.Box((12, 13, 10), (20, 20, 20))
        assert a.gap(b) == pytest.approx(13**0.5)

    def test_segment_through_box(self):
        box = L.Box((-5, -5, -5), (5, 5, 5))
        assert box.hits_segment((-20, 0, 0), (20, 0, 0))
        assert not box.hits_segment((-20, 0, 6), (20, 0, 6))
        assert not box.hits_segment((-20, 0, 0), (-6, 0, 0))


# ---------------------------------------------------------------------------
# The reference layout
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def lay():
    """The reference layout, with builder-friendly frame dimensions."""
    return L.build_layout(skeleton=L.builder_skeleton())


class TestReferenceLayout:
    def test_no_problems(self, lay):
        assert lay.problems() == []

    def test_smallest_frame_also_has_no_problems(self):
        assert L.build_layout().problems() == []

    def test_rod_count(self, lay):
        assert len(lay.rods_of("frame")) == 12  # 4 uprights, 8 horizontal
        assert len(lay.rods_of("motion")) == 6  # 2 X rods, 4 Y rods
        assert len(lay.rods_of("z_screw")) == 3
        assert len(lay.rods_of("z_guide")) == 2
        assert len(lay.blocks) == 8

    def test_names_match_positions(self, lay):
        """front_left is at -X and -Y. An earlier version swapped these."""
        signs = {
            "vertical_front_left": (-1, -1),
            "vertical_front_right": (1, -1),
            "vertical_back_left": (-1, 1),
            "vertical_back_right": (1, 1),
        }
        for name, (sx, sy) in signs.items():
            x, y, _ = lay.rod(name).start
            assert (x * sx > 0) and (y * sy > 0), f"{name} is at x={x}, y={y}"

    def test_every_block_joins_the_three_rods_of_its_corner(self, lay):
        for block in lay.blocks:
            level, front_back, left_right = block.name.split("_")
            assert block.rods == (
                f"{level}_{front_back}_x",
                f"{level}_{left_right}_y",
                f"vertical_{front_back}_{left_right}",
            )

    def test_offset_method_at_every_corner(self, lay):
        """tractor_01: no two of the three rods at a corner touch."""
        c = lay.config
        for block in lay.blocks:
            for i, na in enumerate(block.rods):
                for nb in block.rods[i + 1 :]:
                    gap = L.rod_gap(lay.rod(na), lay.rod(nb))
                    assert gap >= c.min_clearance, f"{na} and {nb} leave {gap:.2f} mm"

    def test_top_block_is_the_bottom_block_turned_over(self, lay):
        """One bracket body serves all eight corners. The bottom one adds a flange."""
        flange = lay.config.flange_thickness
        for corner in ("front_left", "front_right", "back_left", "back_right"):
            bottom = lay.block(f"bottom_{corner}").box.size
            top = lay.block(f"top_{corner}").box.size
            assert bottom[:2] == pytest.approx(top[:2])
            assert bottom[2] - flange == pytest.approx(top[2])

    def test_nozzle_covers_the_whole_bed(self, lay):
        c = lay.config
        nozzle_front = lay.gantry_front - c.nozzle_y_offset
        nozzle_back = lay.gantry_back - c.nozzle_y_offset
        assert nozzle_front == pytest.approx(lay.bed_center_y - c.bed_y / 2)
        assert nozzle_back == pytest.approx(lay.bed_center_y + c.bed_y / 2)

    def test_z_travel_is_at_least_the_build_height(self, lay):
        assert lay.z_travel >= lay.config.build_z

    def test_leadscrews_sit_outside_the_bed(self, lay):
        c = lay.config
        positions = lay.screw_xy
        assert positions["z_screw_back_centre"][0] == 0.0
        for name, (x, y) in positions.items():
            rod = lay.rod(name)
            assert (
                lay.bed_box().gap(rod.box()) + rod.diameter / 2 >= c.z_screw_bed_gap
            ), name

    def test_builder_rounding_never_shrinks_the_frame(self):
        least = L.minimum_skeleton()
        rounded = L.builder_skeleton()
        for have, need in zip(rounded, least):
            assert have >= need
            assert have % 5 == 0

    def test_cut_list_rounds_up_and_never_down(self, lay):
        for rod in lay.rods:
            cut = lay.cut_list()[rod.name]
            assert cut >= rod.length
            assert cut - rod.length < 5.0

    def test_reference_numbers(self, lay):
        """The reference table. If a change to an assumption moves these,
        update them deliberately: they are what the docs and configs quote."""
        assert L.minimum_skeleton() == pytest.approx((325.0, 353.5, 245.25))
        assert L.builder_skeleton() == (325.0, 355.0, 250.0)
        cut = lay.cut_list()
        # Hand-derived: X rod = frame + 2 x (outer block 31.75 + overhang 15)
        assert cut["bottom_front_x"] == pytest.approx(420.0)
        assert cut["bottom_left_y"] == pytest.approx(450.0)
        assert cut["vertical_front_left"] == pytest.approx(355.0)
        assert cut["x_motion_lower"] == pytest.approx(340.0)
        assert cut["y_motion_lower_left"] == pytest.approx(375.0)
        assert cut["z_guide_left"] == pytest.approx(335.0)
        assert cut["z_screw_back_centre"] == pytest.approx(245.0)
        assert lay.bed_lowest == pytest.approx(117.0)
        assert lay.z_travel == pytest.approx(224.75)


def test_layout_needs_no_cad_library():
    """The analysis tools are stdlib only and import this module."""
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]); "
        "import amalgam.lib.layout; "
        "assert 'build123d' not in sys.modules, 'layout pulled in build123d'"
    )
    result = subprocess.run(
        [sys.executable, "-c", code, str(CAD_DIR)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr


# ---------------------------------------------------------------------------
# Every check must be able to fail
# ---------------------------------------------------------------------------
def _one_rod_short(layout):
    """Shorten one X rod so it only reaches one bracket."""
    rod = layout.rod("bottom_front_x")
    shortened = replace(rod, start=(0.0, rod.start[1], rod.start[2]))
    return replace(
        layout, rods=tuple(shortened if r.name == rod.name else r for r in layout.rods)
    )


BROKEN = {
    L.CHECK_ROD_CLEARANCE: lambda: L.build_layout(
        replace(L.LayoutConfig(), rod_offset=0.0)
    ),
    L.CHECK_CORNER_JOINTS: lambda: _one_rod_short(L.build_layout()),
    # A nozzle 80 mm in front of the X rods pushes the bed forward into the
    # Z guide rods.
    L.CHECK_BED_PATH: lambda: L.build_layout(
        replace(L.LayoutConfig(), nozzle_y_offset=80.0)
    ),
    L.CHECK_X_TRAVEL: lambda: L.build_layout(skeleton=(300.0, 355.0, 250.0)),
    L.CHECK_Y_TRAVEL: lambda: L.build_layout(skeleton=(325.0, 330.0, 250.0)),
    L.CHECK_Z_TRAVEL: lambda: L.build_layout(skeleton=(325.0, 355.0, 200.0)),
    L.CHECK_GANTRY_SWEEP: lambda: L.build_layout(
        replace(L.LayoutConfig(), y_end_margin=-60.0)
    ),
    L.CHECK_GANTRY_BEARINGS: lambda: L.build_layout(
        replace(L.LayoutConfig(), x_rod_lift=30.0)
    ),
    L.CHECK_PRINTABLE: lambda: L.build_layout(
        replace(L.LayoutConfig(), rod_offset=250.0)
    ),
}


class TestEachCheckCanFail:
    def test_every_check_has_a_broken_layout(self):
        assert set(BROKEN) == set(L.CHECKS)

    @pytest.mark.parametrize("check", L.CHECKS)
    def test_check_reports_its_broken_layout(self, check):
        problems = BROKEN[check]().problems()
        reported = {p.check for p in problems}
        assert check in reported, (
            f"{check} passed a layout that should fail it. Reported: {sorted(reported)}"
        )

    def test_gantry_lift_clears_the_vertical_rods_top_nut(self):
        """A low cradle puts the Y motion rod onto the upright's top nut."""
        cfg = replace(L.LayoutConfig(), gantry_lift=10.0)
        reported = {p.check for p in L.build_layout(cfg).problems()}
        assert L.CHECK_GANTRY_BEARINGS in reported

    def test_bed_bigger_than_its_frame_is_reported(self):
        """A 320 x 320 bed in the frame sized for 220 runs into the brackets."""
        oversized = replace(L.LayoutConfig(), bed_x=320.0, bed_y=320.0)
        layout = L.build_layout(oversized, skeleton=L.builder_skeleton())
        reported = {p.check for p in layout.problems()}
        assert L.CHECK_BED_PATH in reported

    def test_guide_supports_are_what_the_gantry_can_hit(self):
        """The frame is below the gantry, so only the guide rod tops can be
        in its way. With no end margin the gantry runs into them."""
        cfg = replace(L.LayoutConfig(), y_end_margin=0.0)
        layout = L.build_layout(cfg)
        reported = {p.check for p in layout.problems()}
        assert L.CHECK_GANTRY_SWEEP in reported


# ---------------------------------------------------------------------------
# The same layout as real solids, in the geometry kernel
# ---------------------------------------------------------------------------
class TestKernelAgreement:
    """The checks above use hand-written segment and box maths. These use
    OCCT, so a mistake in that maths cannot hide here."""

    @pytest.fixture(scope="class")
    def lay(self):
        return L.build_layout(skeleton=L.builder_skeleton())

    @staticmethod
    def solid(rod):
        from build123d import Cylinder, Plane, Vector

        mid = tuple((a + b) / 2 for a, b in zip(rod.start, rod.end))
        direction = Vector(*(b - a for a, b in zip(rod.start, rod.end)))
        return Plane(origin=mid, z_dir=direction) * Cylinder(
            rod.diameter / 2, rod.length
        )

    @staticmethod
    def overlap(a, b):
        hit = a.intersect(b)
        return 0.0 if hit is None else hit.volume

    @classmethod
    def joined_volume(cls, rods):
        """Volume of all the rods fused into one solid.

        If any two rods overlap, the overlap is counted once here but twice
        in the sum of the separate volumes, so the two stop agreeing.
        """
        solids = [cls.solid(rod) for rod in rods]
        separate = sum(s.volume for s in solids)
        joined = solids[0].fuse(*solids[1:]).volume
        return separate, joined

    def test_no_two_rods_overlap(self, lay):
        separate, joined = self.joined_volume(lay.rods)
        assert joined == pytest.approx(separate, rel=1e-6)

    def test_kernel_check_catches_touching_rods(self):
        """With no offset the upright runs into the X rod."""
        bad = L.build_layout(replace(L.LayoutConfig(), rod_offset=0.0))
        separate, joined = self.joined_volume(bad.rods)
        assert joined < separate - 1.0, "the kernel check passed touching rods"

    def test_bed_clears_the_frame_through_its_travel(self, lay):
        from build123d import Box, Location

        box = lay.bed_box()
        size = box.size
        bed = Box(*size).moved(
            Location(tuple((a + b) / 2 for a, b in zip(box.lo, box.hi)))
        )
        for block in lay.blocks:
            assert self.overlap(bed, self.solid_of_box(block.box)) == 0.0, block.name
        for rod in lay.rods_of("frame"):
            assert self.overlap(bed, self.solid(rod)) == 0.0, rod.name

    def test_kernel_check_catches_a_bed_in_the_brackets(self):
        from build123d import Box, Location

        oversized = replace(L.LayoutConfig(), bed_x=320.0, bed_y=320.0)
        bad = L.build_layout(oversized, skeleton=L.builder_skeleton())
        box = bad.bed_box()
        bed = Box(*box.size).moved(
            Location(tuple((a + b) / 2 for a, b in zip(box.lo, box.hi)))
        )
        hits = [
            block.name
            for block in bad.blocks
            if self.overlap(bed, self.solid_of_box(block.box)) > 1.0
        ]
        assert hits, "the kernel check passed a bed that runs into the brackets"

    @staticmethod
    def solid_of_box(box):
        from build123d import Box, Location

        centre = tuple((a + b) / 2 for a, b in zip(box.lo, box.hi))
        return Box(*box.size).moved(Location(centre))


# ---------------------------------------------------------------------------
# The example config quotes the layout
# ---------------------------------------------------------------------------
class TestExampleConfigFollowsLayout:
    @pytest.fixture(scope="class")
    def example(self):
        namespace: dict = {}
        text = (CAD_DIR / "config.py.example").read_text()
        exec(compile(text, "config.py.example", "exec"), namespace)
        return namespace

    def test_skeleton_matches(self, example):
        vol = example["BUILD_VOLUME"]
        cfg = L.LayoutConfig(bed_x=vol["X"], bed_y=vol["Y"], build_z=vol["Z"])
        assert L.builder_skeleton(cfg) == pytest.approx(
            (example["SKELETON_X"], example["SKELETON_Y"], example["SKELETON_Z"])
        )

    def test_z_travel_matches(self, example):
        vol = example["BUILD_VOLUME"]
        cfg = L.LayoutConfig(bed_x=vol["X"], bed_y=vol["Y"], build_z=vol["Z"])
        layout = L.build_layout(cfg, skeleton=L.builder_skeleton(cfg))
        assert example["Z_TRAVEL_MAX"] == pytest.approx(layout.z_travel)
