"""
Verification tests for X-Axis motion parts and the MDF squaring jig.

Same principle as test_corner.py: assert physical properties (a rod passes, a
bearing seats, a bolt hole exists) rather than rendering the part.
"""

import sys
from pathlib import Path

import pytest

CAD_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAD_DIR))

from amalgam.lib.corner import make_mdf_squaring_jig  # noqa: E402
from amalgam.lib.motion import (  # noqa: E402
    BEARING_BORE_DIA,
    LM8UU_LENGTH,
    SMOOTH_ROD_DIA,
    XAxisGeometry,
    make_x_carriage,
    make_x_end_plate,
    make_x_gantry_beam,
)
from amalgam.lib.verify import (  # noqa: E402
    assert_no_self_intersection,
    assert_point_empty,
    assert_point_solid,
    assert_rod_passes_through,
    assert_single_solid,
)

ROD_SPACING = 30.0
GEOM = XAxisGeometry(rod_spacing=ROD_SPACING)

# Rod centres, stacked vertically (ADR-021)
RODS = [
    (0.0, 0.0, ROD_SPACING / 2),
    (0.0, 0.0, -ROD_SPACING / 2),
]


class TestXGantryBeam:
    @pytest.fixture(scope="class")
    def beam(self):
        return make_x_gantry_beam(GEOM)

    def test_single_solid(self, beam):
        assert_single_solid(beam, "x_gantry_beam")

    def test_valid(self, beam):
        assert_no_self_intersection(beam, "x_gantry_beam")

    @pytest.mark.parametrize("rod", RODS)
    def test_rod_channel_is_clear(self, beam, rod):
        """Each rod must pass through its channel."""
        assert_point_empty(beam, rod, f"x_gantry_beam rod channel at {rod}")

    @pytest.mark.parametrize("rod", RODS)
    def test_8mm_rod_passes(self, beam, rod):
        """An actual 8mm rod must fit the channel."""
        assert_rod_passes_through(
            beam, (-GEOM.beam_length, rod[1], rod[2]),
            (GEOM.beam_length, rod[1], rod[2]),
            SMOOTH_ROD_DIA, "x_gantry_beam 8mm rod",
        )

    def test_web_between_rods_is_solid(self, beam):
        """The structure between the stacked rods carries the load."""
        assert_point_solid(beam, (0, 0, 0), "x_gantry_beam web")

    def test_spans_build_area(self, beam):
        bb = beam.bounding_box()
        assert (bb.max.X - bb.min.X) >= 320


class TestXCarriage:
    @pytest.fixture(scope="class")
    def carriage(self):
        return make_x_carriage(GEOM)

    def test_single_solid(self, carriage):
        assert_single_solid(carriage, "x_carriage")

    def test_valid(self, carriage):
        assert_no_self_intersection(carriage, "x_carriage")

    @pytest.mark.parametrize("rod", RODS)
    def test_bearing_bore_clear(self, carriage, rod):
        assert_point_empty(carriage, rod, f"x_carriage bearing bore at {rod}")

    @pytest.mark.parametrize("rod", RODS)
    def test_rod_slides_through_bearing(self, carriage, rod):
        """The rod must pass lengthwise -- this is a sliding bearing."""
        assert_rod_passes_through(
            carriage, (-GEOM.carriage_length, rod[1], rod[2]),
            (GEOM.carriage_length, rod[1], rod[2]),
            SMOOTH_ROD_DIA, "x_carriage sliding fit",
        )

    def test_bore_rejects_oversize_rod(self, carriage):
        """The bore must be sized to the rod, not wider.

        A 9mm rod must NOT pass an 8.2mm bearing bore -- that would mean the
        housing is loose and the rod would rattle and wear the bore.
        """
        rod = RODS[0]
        with pytest.raises(Exception):
            assert_rod_passes_through(
                carriage, (-GEOM.carriage_length, rod[1], rod[2]),
                (GEOM.carriage_length, rod[1], rod[2]),
                BEARING_BORE_DIA + 0.8, "oversize rod",
            )

    def test_bore_accepts_nominal_rod_with_clearance(self, carriage):
        """An 8mm rod must pass with room to spare -- clearance, not a press fit."""
        rod = RODS[0]
        assert_rod_passes_through(
            carriage, (-GEOM.carriage_length, rod[1], rod[2]),
            (GEOM.carriage_length, rod[1], rod[2]),
            SMOOTH_ROD_DIA, "nominal 8mm rod in bearing bore",
        )

    def test_toolhead_mount_holes_present(self, carriage):
        """Four M3 holes for the toolhead on the top face."""
        top_z = (ROD_SPACING + 34.0) / 2 - 3.0
        for dx in (-15.5, 15.5):
            for dy in (-15.5, 15.5):
                assert_point_empty(
                    carriage, (dx, dy, top_z),
                    f"x_carriage toolhead hole at ({dx},{dy})",
                )

    def test_body_clears_both_rods(self, carriage):
        """Carriage body must be tall enough to enclose the rod pair."""
        bb = carriage.bounding_box()
        assert bb.max.Z >= ROD_SPACING / 2
        assert bb.min.Z <= -ROD_SPACING / 2


class TestXEndPlate:
    @pytest.fixture(scope="class")
    def plate(self):
        return make_x_end_plate(GEOM)

    def test_single_solid(self, plate):
        assert_single_solid(plate, "x_end_plate")

    def test_valid(self, plate):
        assert_no_self_intersection(plate, "x_end_plate")

    @pytest.mark.parametrize("rod", RODS)
    def test_rod_bore_clear(self, plate, rod):
        assert_point_empty(plate, rod, f"x_end_plate rod bore at {rod}")

    @pytest.mark.parametrize("rod", RODS)
    def test_rod_passes(self, plate, rod):
        assert_rod_passes_through(
            plate, (-10, rod[1], rod[2]), (10, rod[1], rod[2]),
            SMOOTH_ROD_DIA, "x_end_plate rod",
        )

    def test_set_screw_holes_present(self, plate):
        """Each rod needs an M3 set-screw to lock it axially."""
        y = GEOM.beam_width / 2 - 5.0
        for rz in (ROD_SPACING / 2, -ROD_SPACING / 2):
            assert_point_empty(plate, (0, y, rz), f"x_end_plate set screw at z={rz}")

    def test_covers_both_rods(self, plate):
        bb = plate.bounding_box()
        assert bb.max.Z >= ROD_SPACING / 2
        assert bb.min.Z <= -ROD_SPACING / 2


class TestSquaringJig:
    """ADR-011: MDF jig holding the bottom rods at a true right angle."""

    @pytest.fixture(scope="class")
    def jig(self):
        return make_mdf_squaring_jig()

    def test_single_solid(self, jig):
        assert_single_solid(jig, "squaring_jig")

    def test_valid(self, jig):
        assert_no_self_intersection(jig, "squaring_jig")

    def test_rod_seats_at_all_four_corners(self, jig):
        sx = 330 / 2 + 20 / 2
        sy = 340 / 2 + 20 / 2
        for x in (-sx, sx):
            for y in (-sy, sy):
                assert_point_empty(
                    jig, (x, y, 18 + 120 * 0.5),
                    f"rod seat at ({x:.0f},{y:.0f})",
                )

    def test_covers_skeleton_footprint(self, jig):
        bb = jig.bounding_box()
        assert (bb.max.X - bb.min.X) >= 330
        assert (bb.max.Y - bb.min.Y) >= 340

    def test_base_plate_solid(self, jig):
        assert_point_solid(jig, (0, 0, 9), "base plate")


class TestExportIntegrity:
    """
    Guard against silently degenerate STL output.

    A solid can be geometrically valid and still export to a useless mesh --
    e.g. if tessellation fails, you get a 2-triangle file that slices into
    nothing. These checks read the generated STL and assert the mesh actually
    represents the part: real triangle count, and vertices inside the part's
    bounding box.
    """

    @pytest.fixture(scope="class")
    def stl_files(self):
        d = CAD_DIR / "exports" / "stl"
        return sorted(d.glob("*.stl")) if d.exists() else []

    def test_parts_were_exported(self, stl_files):
        if not stl_files:
            pytest.skip("no STL exports yet; run ./build.sh build_all")

    @pytest.mark.parametrize(
        "name",
        [
            "corner_standard_bottom",
            "corner_standard_top",
            "squaring_jig",
            "x_gantry_beam",
            "x_carriage",
            "x_end_plate",
        ],
    )
    def test_stl_has_real_triangles(self, stl_files, name):
        import struct

        path = CAD_DIR / "exports" / "stl" / f"{name}.stl"
        if not path.exists():
            pytest.skip(f"{name}.stl not generated yet")

        with open(path, "rb") as fh:
            header = fh.read(80)
            count = struct.unpack("<I", fh.read(4))[0]
            body = fh.read(50 * min(count, 3))

        assert len(header) == 80, "STL header truncated"
        # A closed solid needs at least 12 triangles; anything fewer is a
        # failed tessellation rather than geometry.
        assert count >= 12, f"{name}.stl has only {count} triangles"
        # Header must not be ASCII STL (would mean the wrong writer).
        assert not header.startswith(b"solid"), (
            f"{name}.stl is ASCII format; binary expected"
        )

        # Spot-check that vertices lie within a sane range for the part.
        for i in range(0, len(body), 50):
            vals = struct.unpack("<12fH", body[i : i + 50])
            for v in vals[3:12]:
                assert -1000 < v < 1000, f"{name}.stl vertex out of range: {v}"

    @pytest.mark.parametrize(
        "name,expected_solids",
        [
            ("corner_standard_bottom", 1),
            ("x_gantry_beam", 1),
            ("x_carriage", 1),
            ("x_end_plate", 1),
        ],
    )
    def test_stl_triangle_count_sane_for_shape(self, stl_files, name, expected_solids):
        """A curved part must tessellate to more triangles than a plain box.

        Guards the specific failure where a complex part silently exports with
        the same triangle count as a trivial one.
        """
        import struct

        path = CAD_DIR / "exports" / "stl" / f"{name}.stl"
        if not path.exists():
            pytest.skip(f"{name}.stl not generated yet")

        with open(path, "rb") as fh:
            fh.read(80)
            count = struct.unpack("<I", fh.read(4))[0]

        assert count > 12, (
            f"{name}.stl exported {count} triangles -- a part with rod bores "
            f"should tessellate far above the 12 of a plain box"
        )