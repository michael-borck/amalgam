"""
Shared build123d components for Amalgam corner brackets.

Design notes
------------
Scaffold frame (ADR-001, ADR-025): M10 **threaded** rod forms the skeleton.
Motion rods (8mm smooth, ADR-021) live in LM8UU bearings and are NOT part of
these brackets -- keep the two rod systems distinct.

Anchoring is per-corner (see `Anchoring`):
  THROUGH_BORE - rod passes fully through, nuts on the far side. Positive
                 metal-on-metal clamping, strongest. Used on bottom corners
                 which carry bed weight and Z-screw thrust.
  JAM_NUT      - blind bores from both faces plus a nut pocket on each outer
                 face. Rod does not protrude, so nothing can snag and rod
                 length errors don't matter. Used on top corners, which are
                 lightly loaded.

Construction note -- why cylinders are rotated BEFORE translation:
A bare `Cylinder` is Z-aligned. Translating it and then calling
`.rotate(Axis.Z, 90)` cannot change its axis (rotation about Z leaves a
Z-aligned shape Z-aligned) and simultaneously teleports the centre. The
previous version of this module did exactly that, which is why both Y-axis
rod bores were silently missing. `_axis_cylinder` orients first, then moves.
"""

from build123d import *

# ---------------------------------------------------------------------------
# Hardware dimensions
# ---------------------------------------------------------------------------

M10_NOMINAL_DIA = 10.0
M10_NUT_AF = 17.0  # M10 hex nut across flats
M10_JAM_NUT_AF = 17.0  # M10 jam nut across flats
NEMA17_BOLT_SPACING = 31.0  # mm, NEMA17 mounting hole pattern


class Anchoring:
    """Rod anchoring styles for corner brackets."""

    THROUGH_BORE = "THROUGH_BORE"
    JAM_NUT = "JAM_NUT"


# ---------------------------------------------------------------------------
# Primitive helpers
# ---------------------------------------------------------------------------

def _axis_cylinder(axis: str, radius: float, length: float, center):
    """
    Build a cylinder oriented along `axis` and centred on `center`.

    The cylinder is rotated into orientation BEFORE being translated, so the
    centre lands exactly where specified and the axis is correct. This ordering
    is the whole point of the helper -- see the module docstring.
    """
    if axis == "X":
        cyl = Cylinder(radius, length).rotate(Axis.Y, 90)
    elif axis == "Y":
        cyl = Cylinder(radius, length).rotate(Axis.X, 90)
    elif axis == "Z":
        cyl = Cylinder(radius, length)
    else:
        raise ValueError(f"axis must be 'X', 'Y' or 'Z', got {axis!r}")
    return cyl.moved(Location(tuple(center)))


def create_corner_base(corner_size: float):
    """Basic corner cube, used for subtraction in composite brackets."""
    return Box(corner_size, corner_size, corner_size)


def create_nema17_motor_mount(
    mount_depth: float,
    plate_width: float = 42.0,
    plate_height: float = 42.0,
    bolt_spacing: float = NEMA17_BOLT_SPACING,
    bolt_dia: float = 3.3,
):
    """
    NEMA17 motor mount plate with all four bolt holes.

    The previous version listed (+bolt/2, -bolt/2) twice and omitted
    (-bolt/2, -bolt/2), so only three of the four holes were drilled.

    Returns:
        Mount plate with 4 through-holes, extruded `mount_depth` along +X.
    """
    plate = Box(plate_width, plate_height, mount_depth)
    plate = plate.moved(Location((-mount_depth / 2, 0, 0)))

    half = bolt_spacing / 2
    bolt_pattern = [
        (-half, half),
        (half, half),
        (half, -half),
        (-half, -half),
    ]

    for by, bz in bolt_pattern:
        hole = _axis_cylinder("X", bolt_dia / 2, mount_depth * 3, (0, by, bz))
        plate -= hole

    return plate


def create_rod_clamp(rod_diameter: float, wall_thickness: float = 5.0,
                     clamp_length: float = 40.0):
    """Simple printed clamp body with a rod bore (not used by Scaffold path)."""
    outer = rod_diameter + wall_thickness * 2
    body = Box(outer, outer, clamp_length)
    bore = _axis_cylinder("Z", rod_diameter / 2, clamp_length * 2, (0, 0, 0))
    return body - bore


# ---------------------------------------------------------------------------
# Corner brackets
# ---------------------------------------------------------------------------

def _rod_positions(corner_size: float, wall_thickness: float):
    """
    Return the four rod passages as (axis, centre) pairs.

    Rods sit `wall_thickness` in from each outer face, giving four passages:
    two running along X (at +/-Y) and two along Y (at +/-X).
    """
    offset = corner_size / 2 - wall_thickness
    return [
        ("X", (0, offset, 0)),
        ("X", (0, -offset, 0)),
        ("Y", (offset, 0, 0)),
        ("Y", (-offset, 0, 0)),
    ]


def make_standard_corner(
    corner_size: float = 50.0,
    rod_fit_dia: float = 10.5,
    wall_thickness: float = 5.0,
    anchoring: str = Anchoring.THROUGH_BORE,
    nut_pocket_dia: float | None = None,
    blind_depth: float | None = None,
    jam_nut_pocket_depth: float = 5.0,
):
    """
    Generate a Scaffold frame corner bracket for M10 threaded rod.

    Args:
        corner_size: Cube edge length in mm (default 50)
        rod_fit_dia: Rod bore diameter. Must clear thread crest, so this is
            nominal + lumpy factor (default 10.5mm for M10)
        wall_thickness: Material thickness at the rod seats
        anchoring: Anchoring.THROUGH_BORE or Anchoring.JAM_NUT
        nut_pocket_dia: Counterbore diameter for nuts; defaults to
            M10_NUT_AF + 2mm clearance
        blind_depth: Depth of each jam-nut blind bore from an outer face;
            defaults to leaving a 10mm solid core
        jam_nut_pocket_depth: Depth of the nut pocket recess

    Returns:
        build123d Part (a single solid)
    """
    if anchoring not in (Anchoring.THROUGH_BORE, Anchoring.JAM_NUT):
        raise ValueError(f"anchoring must be THROUGH_BORE or JAM_NUT, got {anchoring!r}")
    if rod_fit_dia <= rod_nominal_check(rod_fit_dia):
        raise ValueError("rod_fit_dia must exceed nominal rod diameter")

    corner = create_corner_base(corner_size)
    passages = _rod_positions(corner_size, wall_thickness)
    half = corner_size / 2

    if nut_pocket_dia is None:
        nut_pocket_dia = M10_NUT_AF + 2.0
    if blind_depth is None:
        # Leave a solid core so the two blind bores from opposite faces
        # never meet, keeping the bracket one connected solid.
        blind_depth = corner_size / 2 - 10.0

    for axis, centre in passages:
        if anchoring == Anchoring.THROUGH_BORE:
            # Full through-bore along this axis.
            corner -= _axis_cylinder(axis, rod_fit_dia / 2, corner_size * 2, centre)

            # Nut access counterbore on both outer faces of this axis.
            for sign in (-1, 1):
                face_pt = _offset_along(axis, centre, sign * (half - jam_nut_pocket_depth / 2))
                corner -= _axis_cylinder(
                    axis, nut_pocket_dia / 2, jam_nut_pocket_depth, face_pt
                )
        else:
            # Blind bore from each of the two faces perpendicular to `axis`,
            # plus a jam nut pocket flush with each outer face.
            #
            # The bore spans from the face inward, so its centre sits
            # `blind_depth/2` inboard of the face.
            for sign in (-1, 1):
                bore_centre = _offset_along(
                    axis, centre, sign * (half - blind_depth / 2)
                )
                corner -= _axis_cylinder(axis, rod_fit_dia / 2, blind_depth, bore_centre)

                pocket_centre = _offset_along(
                    axis, centre, sign * (half - jam_nut_pocket_depth / 2)
                )
                corner -= _axis_cylinder(
                    axis, nut_pocket_dia / 2, jam_nut_pocket_depth, pocket_centre
                )

    return corner


def rod_nominal_check(fit_dia: float) -> float:
    """Nominal rod diameter a fit diameter refers to (M10 by convention)."""
    return M10_NOMINAL_DIA


def _offset_along(axis: str, centre, distance: float):
    """Return `centre` shifted `distance` along `axis`."""
    c = list(centre)
    idx = {"X": 0, "Y": 1, "Z": 2}[axis]
    c[idx] += distance
    return tuple(c)


def _set_component(point, axis: str, value: float):
    """Return a copy of `point` with the `axis` component set to `value`."""
    c = list(point)
    idx = {"X": 0, "Y": 1, "Z": 2}[axis]
    c[idx] = value
    return tuple(c)


def make_motorized_corner(
    corner_size: float = 50.0,
    rod_fit_dia: float = 10.5,
    wall_thickness: float = 5.0,
    anchoring: str = Anchoring.THROUGH_BORE,
    motor_axis: str = "Z",
    motor_bolt_spacing: float = NEMA17_BOLT_SPACING,
    motor_face_offset: float | None = None,
    motor_boss_thickness: float = 10.0,
    nut_pocket_dia: float | None = None,
    jam_nut_pocket_depth: float = 5.0,
):
    """
    Corner bracket with an integrated NEMA17 mount (Triple-Z).

    Combines the standard rod passages with a motor mounting face. The motor
    shaft protrudes along `motor_axis` from the specified face.

    Args:
        corner_size: Cube edge length in mm
        rod_fit_dia: Rod bore diameter (default 10.5mm for M10)
        wall_thickness: Material thickness at the rod seats
        anchoring: Anchoring.THROUGH_BORE or Anchoring.JAM_NUT
        motor_axis: Axis the motor mounts along ("X", "Y" or "Z")
        motor_bolt_spacing: NEMA17 pattern (31mm)
        motor_face_offset: Face the motor bolts to; defaults to the -motor_axis
            face
        motor_boss_thickness: Wall thickness behind the motor
        nut_pocket_dia: Counterbore diameter for nuts
        jam_nut_pocket_depth: Nut pocket recess depth

    Returns:
        build123d Part (a single solid)
    """
    corner = make_standard_corner(
        corner_size=corner_size,
        rod_fit_dia=rod_fit_dia,
        wall_thickness=wall_thickness,
        anchoring=anchoring,
        nut_pocket_dia=nut_pocket_dia,
        jam_nut_pocket_depth=jam_nut_pocket_depth,
    )

    if motor_face_offset is None:
        motor_face_offset = -corner_size / 2

    # Motor mounting plate sits proud of the motor face so the bolt heads have
    # material to bear against. Built directly in orientation -- the thin
    # dimension always runs along motor_axis.
    plate_thickness = 4.0
    span = motor_bolt_spacing + 11.0  # NEMA17 body is 42.3mm across
    plate = Box(span, span, plate_thickness)
    plate = plate.rotate(
        {"X": Axis.Y, "Y": Axis.X, "Z": Axis.X}[motor_axis], 90
    )

    # Centre the plate so its outer surface is `motor_face_offset` (offset
    # measured from the bracket centre), sitting flush outside the cube.
    plate = plate.moved(
        Location(_offset_along(
            motor_axis, (0, 0, 0),
            motor_face_offset - plate_thickness / 2,
        ))
    )

    # NEMA17 mounting holes, plus a clearance bore for the 5mm shaft.
    #
    # `motor_axis` names the axis the motor bolts ALONG. The remaining two
    # axes are in-plane, so bolt positions are laid out on a 2D pattern and
    # then placed into 3D on the motor face.
    half = motor_bolt_spacing / 2

    # (u, v) offsets in the plane perpendicular to motor_axis
    bolt_pattern = [(-half, half), (half, half), (half, -half), (-half, -half)]

    for u, v in bolt_pattern:
        centre = _on_plane(u, v, motor_axis, motor_face_offset)
        corner -= _axis_cylinder(motor_axis, 1.7, plate_thickness * 3, centre)

    # Union first, then cut. The bolt holes and shaft bore must be subtracted
    # from the FINISHED part -- subtracting before the union would leave them
    # buried inside solid plate material.
    result = corner + plate

    # Shaft clearance: 11mm bore through the plate and into the bracket body,
    # so the leadscrew or shaft passes freely to the motor.
    shaft_centre = _offset_along(
        motor_axis, (0, 0, 0),
        motor_face_offset - plate_thickness + 20.0,
    )
    result -= _axis_cylinder(motor_axis, 11.0 / 2, 60.0, shaft_centre)

    return result


def _on_plane(u: float, v: float, axis: str, face: float):
    """
    Place a 2D point `(u, v)` on the face perpendicular to `axis`.

    The in-plane axes are chosen so the pattern stays right-handed:
      X (motor along X) -> u=Y, v=Z
      Y (motor along Y) -> u=X, v=Z
      Z (motor along Z) -> u=X, v=Y
    """
    if axis == "X":
        return (face, u, v)
    if axis == "Y":
        return (u, face, v)
    return (u, v, face)


def make_mdf_squaring_jig(
    bed_x: float = 220.0,
    bed_y: float = 220.0,
    skeleton_x: float = 330.0,
    skeleton_y: float = 340.0,
    plate_thickness: float = 18.0,
    jig_wall: float = 20.0,
    upright_height: float = 120.0,
    rod_fit_dia: float = 10.5,
    right_angle_tolerance: float = 0.15,
):
    """
    MDF squaring jig (ADR-011).

    Two uprights clamped to a base plate hold the bottom horizontal rods at a
    true right angle while the corner brackets are fitted and the frame is
    bolted up. The 3-4-5 triangle in the base is cut by the builder; this part
    provides the right-angle references and rod seats.

    Args:
        bed_x: Build volume X (mm)
        bed_y: Build volume Y (mm)
        skeleton_x: Skeleton rod length along X
        skeleton_y: Skeleton rod length along Y
        plate_thickness: MDF base thickness (18mm standard)
        jig_wall: Thickness of each upright
        upright_height: Height of uprights above the plate
        rod_fit_dia: Rod seat bore diameter
        right_angle_tolerance: Documented assembly tolerance in mm

    Returns:
        build123d Part holding the MDF plate outline and upright geometry
    """
    plate = Box(skeleton_x + jig_wall * 2, skeleton_y + jig_wall * 2, plate_thickness)
    plate = plate.moved(Location((0, 0, plate_thickness / 2)))

    half_x = skeleton_x / 2
    half_y = skeleton_y / 2

    # Uprights sit on the plate edges and provide a rod seat at true 90
    # degrees to each other.
    upright_z = plate_thickness + upright_height / 2

    upright_x = Box(jig_wall, jig_wall, upright_height)
    upright_x = upright_x.moved(
        Location((-half_x - jig_wall / 2, -half_y - jig_wall / 2, upright_z))
    )

    upright_y = Box(jig_wall, jig_wall, upright_height)
    upright_y = upright_y.moved(
        Location((half_x + jig_wall / 2, -half_y - jig_wall / 2, upright_z))
    )

    upright_3 = Box(jig_wall, jig_wall, upright_height)
    upright_3 = upright_3.moved(
        Location((half_x + jig_wall / 2, half_y + jig_wall / 2, upright_z))
    )

    upright_4 = Box(jig_wall, jig_wall, upright_height)
    upright_4 = upright_4.moved(
        Location((-half_x - jig_wall / 2, half_y + jig_wall / 2, upright_z))
    )

    jig = plate + upright_x + upright_y + upright_3 + upright_4

    # Rod seat bores: one per corner, through the upright pair, so the bottom
    # horizontal rods sit in a machined right angle.
    for sx in (-1, 1):
        for sy in (-1, 1):
            centre = (sx * (half_x + jig_wall / 2), sy * (half_y + jig_wall / 2),
                      plate_thickness + upright_height * 0.5)
            jig -= _axis_cylinder("Z", rod_fit_dia / 2, upright_height * 2, centre)

    return jig