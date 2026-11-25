"""
Verification tests for the rewritten M10 Scaffold corner brackets.

Each test asserts a physical property -- a rod fits, material is where it
should be, the part is one solid. No rendering required.

Covers:
  - THROUGH_BORE corners (bottom: bed weight + Z-screw thrust)
  - JAM_NUT corners (top: lightly loaded, clean finish)
  - Motorized corner with integrated NEMA17 (Triple-Z)
  - MDF squaring jig (ADR-011)
"""

import math
import sys
from pathlib import Path

import pytest

CAD_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAD_DIR))

from amalgam.lib.corner import (  # noqa: E402
    Anchoring,
    make_mdf_squaring_jig,
    make_motorized_corner,
    make_standard_corner,
    NEMA17_BOLT_SPACING,
)
from amalgam.lib.verify import (  # noqa: E402
    M10_FIT_DIA,
    assert_min_wall_thickness,
    assert_mirror_symmetry,
    assert_no_self_intersection,
    assert_point_empty,
    assert_point_solid,
    assert_rod_passes_through,
    assert_single_solid,
)

CORNER = 50.0
WALL = 5.0
OFFSET = CORNER / 2 - WALL  # 20mm

# Rod axes: (axis, centre) for the four passages
PASSAGES = [
    ("X", (0, OFFSET, 0)),
    ("X", (0, -OFFSET, 0)),
    ("Y", (OFFSET, 0, 0)),
    ("Y", (-OFFSET, 0, 0)),
]


def _rod_endpoints(axis, centre, length=CORNER):
    """Endpoints of a rod travelling along `axis` through `centre`."""
    idx = {"X": 0, "Y": 1}[axis]
    start = [0, 0, 0]
    end = [0, 0, 0]
    start[idx] = -length
    end[idx] = length
    for i in range(3):
        start[i] += centre[i]
        end[i] += centre[i]
    return tuple(start), tuple(end)


class TestThroughBoreCorner:
    """Bottom corners: strongest anchoring, rod passes fully through."""

    @pytest.fixture(scope="class")
    def corner(self):
        return make_standard_corner(CORNER, M10_FIT_DIA, WALL, Anchoring.THROUGH_BORE)

    def test_single_solid(self, corner):
        assert_single_solid(corner, "corner through-bore")

    def test_valid_geometry(self, corner):
        assert_no_self_intersection(corner, "corner through-bore")

    @pytest.mark.parametrize("axis,centre", PASSAGES)
    def test_rod_axis_is_hollow(self, corner, axis, centre):
        assert_point_empty(corner, centre, f"{axis} rod axis at {centre}")

    @pytest.mark.parametrize("axis,centre", PASSAGES)
    def test_m10_rod_fits(self, corner, axis, centre):
        start, end = _rod_endpoints(axis, centre)
        assert_rod_passes_through(corner, start, end, M10_FIT_DIA, f"M10 {axis} rod")

    def test_structure_is_solid_between_rods(self, corner):
        """Centre must be solid -- this is the load path."""
        assert_point_solid(corner, (0, 0, 0), "corner centre")

    @pytest.mark.parametrize("axis,centre", PASSAGES)
    def test_material_between_rods(self, corner, axis, centre):
        """There must be material separating the two parallel rods.

        A rod bore at +/-OFFSET with a 5.25mm radius spans 14.75..25.25mm, so
        the strip between the two bores is solid. If it were hollow the two
        rods would share a wall with nothing holding them apart.
        """
        probe = list(centre)
        probe[{"X": 1, "Y": 0}[axis]] = 0.0  # midway between the two rods
        assert_point_solid(corner, tuple(probe), f"material between {axis} rods")

    def test_symmetric_x(self, corner):
        assert_mirror_symmetry(corner, "x", "corner through-bore")

    def test_symmetric_y(self, corner):
        assert_mirror_symmetry(corner, "y", "corner through-bore")

    def test_bore_is_not_oversize_for_m10(self, corner):
        """A 10.5mm bore must not pass a 12mm rod (guards the old M12 default)."""
        axis, centre = PASSAGES[0]
        start, end = _rod_endpoints(axis, centre)
        # This SHOULD fail; if it passes, the bore is too wide.
        with pytest.raises(Exception):
            assert_rod_passes_through(corner, start, end, 12.0, "oversize rod")

    def test_volume_is_reasonable(self, corner):
        """Rough sanity: 4 bores out of a 125k mm^3 cube."""
        removed = CORNER**3 - corner.volume
        assert 15_000 < removed < 30_000, f"removed {removed:.0f}mm^3 is out of range"


class TestJamNutCorner:
    """Top corners: blind bores, rod does not protrude."""

    @pytest.fixture(scope="class")
    def corner(self):
        return make_standard_corner(CORNER, M10_FIT_DIA, WALL, Anchoring.JAM_NUT)

    def test_single_solid(self, corner):
        assert_single_solid(corner, "corner jam-nut")

    def test_valid_geometry(self, corner):
        assert_no_self_intersection(corner, "corner jam-nut")

    @pytest.mark.parametrize("axis,centre", PASSAGES)
    def test_bore_open_at_both_faces(self, corner, axis, centre):
        """A rod inserted from either face must seat in the blind bore."""
        idx = {"X": 0, "Y": 1}[axis]
        for sign in (-1, 1):
            probe = list(centre)
            probe[idx] = sign * (CORNER / 2 - 3.0)
            assert_point_empty(corner, tuple(probe), f"{axis} bore mouth")

    @pytest.mark.parametrize("axis,centre", PASSAGES)
    def test_solid_core_stops_blind_bores(self, corner, axis, centre):
        """Blind bores must not meet -- a core keeps the bracket one solid."""
        assert_point_solid(corner, centre, f"{axis} passage core")

    def test_centre_is_solid(self, corner):
        assert_point_solid(corner, (0, 0, 0), "corner centre")

    def test_symmetric_x(self, corner):
        assert_mirror_symmetry(corner, "x", "corner jam-nut")

    def test_symmetric_y(self, corner):
        assert_mirror_symmetry(corner, "y", "corner jam-nut")

    def test_less_material_removed_than_through_bore(self, corner):
        """Blind bores remove less than through bores -- sanity check."""
        through = make_standard_corner(CORNER, M10_FIT_DIA, WALL, Anchoring.THROUGH_BORE)
        assert corner.volume > through.volume, (
            "jam-nut corner removed more material than through-bore; "
            "blind bores should be shallower"
        )


class TestCornerValidation:
    """Invalid parameters must raise, not silently produce bad geometry."""

    def test_rejects_bad_anchoring(self):
        with pytest.raises(ValueError, match="anchoring"):
            make_standard_corner(anchoring="WEDGED_IN")

    def test_rejects_undersize_bore(self):
        """A bore at or below nominal diameter would crush the rod thread."""
        with pytest.raises(ValueError, match="rod_fit_dia"):
            make_standard_corner(rod_fit_dia=9.0)

    def test_rejects_rod_at_exactly_nominal(self):
        with pytest.raises(ValueError, match="rod_fit_dia"):
            make_standard_corner(rod_fit_dia=10.0)


class TestMotorizedCorner:
    """Triple-Z corners with an integrated NEMA17 mount."""

    @pytest.fixture(scope="class")
    def corner(self):
        return make_motorized_corner(
            CORNER, M10_FIT_DIA, WALL, Anchoring.THROUGH_BORE
        )

    def test_single_solid(self, corner):
        assert_single_solid(corner, "motorized corner")

    def test_valid_geometry(self, corner):
        assert_no_self_intersection(corner, "motorized corner")

    @pytest.mark.parametrize("axis,centre", PASSAGES)
    def test_rod_axes_still_hollow(self, corner, axis, centre):
        """Adding the motor mount must not block a rod passage."""
        assert_point_empty(corner, centre, f"motorized corner {axis} rod at {centre}")

    @pytest.mark.parametrize("axis,centre", PASSAGES)
    def test_rods_still_fit(self, corner, axis, centre):
        start, end = _rod_endpoints(axis, centre)
        assert_rod_passes_through(
            corner, start, end, M10_FIT_DIA, f"motorized M10 {axis} rod"
        )

    def test_nema17_shaft_clearance(self, corner):
        """An 11mm motor shaft must clear the mount centre."""
        assert_point_empty(corner, (0, 0, -CORNER / 2 + 1.0), "NEMA17 shaft bore")

    def test_nema17_bolt_holes_all_present(self, corner):
        """All four NEMA17 holes -- the old code drilled only three."""
        half = NEMA17_BOLT_SPACING / 2
        z = -CORNER / 2 + 1.0
        for a, b in [(half, half), (-half, half), (half, -half), (-half, -half)]:
            assert_point_empty(corner, (a, b, z), f"NEMA17 bolt hole at ({a},{b})")

    def test_minimum_wall_thickness(self, corner):
        assert_min_wall_thickness(corner, 3.0, "motorized corner")


class TestMdfSquaringJig:
    """ADR-011: MDF jig that holds the bottom rods at a true right angle."""

    @pytest.fixture(scope="class")
    def jig(self):
        return make_mdf_squaring_jig()

    def test_is_single_solid(self, jig):
        assert_single_solid(jig, "squaring jig")

    def test_valid_geometry(self, jig):
        assert_no_self_intersection(jig, "squaring jig")

    def test_rod_seats_exist_at_all_four_corners(self, jig):
        """One rod seat per corner, on the uprights."""
        sx, sy = 330 / 2 + 20 / 2, 340 / 2 + 20 / 2
        for x in (-sx, sx):
            for y in (-sy, sy):
                probe = (x, y, 18 + 120 * 0.5)
                assert_point_empty(jig, probe, f"jig rod seat at ({x},{y})")

    def test_spans_the_skeleton(self, jig):
        bb = jig.bounding_box()
        assert (bb.max.X - bb.min.X) >= 330
        assert (bb.max.Y - bb.min.Y) >= 340

    def test_base_plate_is_present(self, jig):
        assert_point_solid(jig, (0, 0, 9), "jig base plate centre")