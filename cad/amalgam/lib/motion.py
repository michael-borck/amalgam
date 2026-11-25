"""
X-Axis motion parts for the Scaffold path (ADR-021, ADR-022).

Motion system: dual 8mm smooth rods, vertically stacked ~30mm apart, running
along X. LM8UU linear bearings carry the carriage.

Three parts are produced:

  x_gantry_beam     Rigid beam spanning the X axis, carrying the stacked rods
                    at their bearings. Bolts to the top of the frame corners.
  x_carriage        The "plough" that rides both rods and carries the toolhead.
                    Needs no motion relative to the rods -- it IS the bearing
                    housing (a RepRap Mendel homage).
  x_end_plate       Captures rod ends at each gantry side.

Geometry notes:
  - Rod spacing is the vertical stack distance (30mm), so the carriage has two
    bearing bores offset in Z.
  - Bearing bores are 8mm + clearance. LM8UU bore is nominally 8mm; a printed
    housing is typically opened up slightly for fit, hence 8.2mm.
  - Everything is verified before export by cad/tests/test_motion.py.
"""

from build123d import *

# Linear bearing and rod dimensions
SMOOTH_ROD_DIA = 8.0
ROD_CLEARANCE = 0.2  # printed housing bores are opened slightly for fit
BEARING_BORE_DIA = SMOOTH_ROD_DIA + ROD_CLEARANCE

LM8UU_LENGTH = 24.0  # standard LM8UU body length
LM8UU_WIDTH = 13.0  # across the housing
LM8UU_MOUNT_PITCH = 36.0  # centre distance between mounting slots

NEMA17_MOUNT_PITCH = 31.0
NEMA17_SHAFT_DIA = 5.0
BELT_PITCH = 9.0  # GT2


def _axis_cylinder(axis: str, radius: float, length: float, center):
    """Cylinder oriented along `axis`, then translated to `center`."""
    if axis == "X":
        cyl = Cylinder(radius, length).rotate(Axis.Y, 90)
    elif axis == "Y":
        cyl = Cylinder(radius, length).rotate(Axis.X, 90)
    elif axis == "Z":
        cyl = Cylinder(radius, length)
    else:
        raise ValueError(axis)
    return cyl.moved(Location(tuple(center)))


class XAxisGeometry:
    """Shared geometry parameters for the X axis."""

    def __init__(
        self,
        rod_spacing: float = 30.0,
        beam_length: float = 320.0,
        beam_width: float = 45.0,
        beam_height: float = 12.0,
        carriage_length: float = 70.0,
        carriage_width: float = 50.0,
        carriage_height: float = 20.0,
    ):
        self.rod_spacing = rod_spacing
        self.beam_length = beam_length
        self.beam_width = beam_width
        self.beam_height = beam_height
        self.carriage_length = carriage_length
        self.carriage_width = carriage_width
        self.carriage_height = carriage_height

        # Rod centres are symmetric about the origin, offset in Z (vertical
        # stacking -- ADR-021). The rods run along X.
        self.rods = [
            (0.0, 0.0, rod_spacing / 2),
            (0.0, 0.0, -rod_spacing / 2),
        ]


def make_x_gantry_beam(geom: XAxisGeometry):
    """
    Rigid X-axis beam that carries both smooth rods.

    The beam runs along X. Rod bores are through-holes in Z so the rods drop
    in from above and are clamped by printed caps (rod ends captured).
    """
    g = geom
    beam = Box(g.beam_length, g.beam_width, g.beam_height)

    # Rod bores: vertical (Z) holes, offset in Z by the stacking distance.
    # They pass through the beam thickness so rods seat in the channel.
    for rz in (g.rod_spacing / 2, -g.rod_spacing / 2):
        # Bore runs along Y (across the beam width) so the rod lies across it.
        beam -= _axis_cylinder("Y", SMOOTH_ROD_DIA / 2, g.beam_width * 2, (0, 0, rz))

    # Belt channel: a groove along X on one edge for the GT2 belt.
    belt_channel = Box(
        g.beam_length - 20.0,
        10.0,
        6.0,
    ).moved(Location((0, g.beam_width / 2 - 5.0, 0)))
    beam -= belt_channel

    return beam


def make_x_carriage(geom: XAxisGeometry):
    """
    X-axis carriage riding both stacked rods.

    Two bearing housings, offset in Z by the rod spacing. The toolhead bolts
    on top. This is the RepRap Mendel "plough" arrangement: the carriage IS the
    bearing block, which keeps the assembly short and stiff.
    """
    g = geom

    # Overall body spans the full stacked rod pair plus mounting flanges.
    body_h = g.rod_spacing + 34.0
    carriage = Box(g.carriage_length, g.carriage_width, body_h)
    carriage = carriage.moved(Location((0, 0, 0)))

    # Bearing bores: rods run along X, so bores run along X.
    for rz in (g.rod_spacing / 2, -g.rod_spacing / 2):
        carriage -= _axis_cylinder(
            "X", BEARING_BORE_DIA / 2, g.carriage_length * 2, (0, 0, rz)
        )

    # Lighten the middle while keeping the bearing bosses solid.
    pocket = Box(
        g.carriage_length - 30.0,
        g.carriage_width - 16.0,
        body_h - 20.0,
    )
    carriage -= pocket

    # Toolhead mount: four M3 holes on a 31mm NEMA-like pattern on top face.
    top_z = body_h / 2
    half = 15.5
    for dx in (-half, half):
        for dy in (-half, half):
            centre = (dx, dy, top_z - 3.0)
            carriage -= _axis_cylinder("Z", 1.7, 10.0, centre)

    return carriage


def make_x_end_plate(geom: XAxisGeometry):
    """
    End plate that captures rod ends at each gantry side.

    Bolts to the gantry beam and to the frame corner. Rod is captured by a
    through-bore with a set-screw hole clamping it axially.
    """
    g = geom
    plate_h = g.rod_spacing + 30.0
    plate = Box(10.0, g.beam_width, plate_h)
    plate = plate.moved(Location((0, 0, 0)))

    # Rod bores run along X (rods pass through into the gantry).
    for rz in (g.rod_spacing / 2, -g.rod_spacing / 2):
        plate -= _axis_cylinder("X", SMOOTH_ROD_DIA / 2, 20.0, (0, 0, rz))

    # Set-screw holes (M3) to lock each rod axially -- approach from +Y face.
    for rz in (g.rod_spacing / 2, -g.rod_spacing / 2):
        centre = (0, g.beam_width / 2 - 5.0, rz)
        plate -= _axis_cylinder("Y", 1.5, 10.0, centre)

    # Frame bolt pattern (M10 rods pass outside this plate via the corner).
    for dy in (-g.beam_width / 2 + 6.0, g.beam_width / 2 - 6.0):
        centre = (0, dy, 0)
        plate -= _axis_cylinder("X", 2.6, 20.0, centre)

    return plate