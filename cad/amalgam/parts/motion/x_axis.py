"""
X-Axis motion parts (Scaffold path, dual 8mm smooth rods).

Generates the gantry beam, carriage, and end plates. All geometry is verified
before export by cad/tests/test_motion.py.
"""

import sys

from amalgam.lib.export import export_part
from amalgam.lib.motion import (
    BEARING_BORE_DIA,
    SMOOTH_ROD_DIA,
    XAxisGeometry,
    make_x_carriage,
    make_x_end_plate,
    make_x_gantry_beam,
)
from amalgam.lib.verify import (
    assert_no_self_intersection,
    assert_point_empty,
    assert_point_solid,
    assert_single_solid,
)

try:
    from config import *
except ImportError:
    print("ERROR: config.py not found")
    print("")
    print("Please run: ./configure.py")
    print("")
    sys.exit(1)


def build_volume(name: str) -> float:
    """
    Read a build-volume dimension from config.

    The wizard writes lowercase keys (`{"x": 220}`) while config.py.example
    uses uppercase (`{"X": 220}`). Accept either so part scripts work with a
    generated config and with the example.
    """
    vol = globals().get("BUILD_VOLUME", {}) or {}
    for key in (name, name.lower(), name.upper()):
        if key in vol:
            return float(vol[key])
    # Fall back to explicit bed dimensions, then the reference spec.
    bed = globals().get(f"BED_SIZE_{name.upper()}")
    if bed:
        return float(bed)
    return 220.0


def _verify(part, name, hollow_points, solid_points):
    assert_single_solid(part, name)
    assert_no_self_intersection(part, name)
    for p in hollow_points:
        assert_point_empty(part, p, f"{name}: clearance at {p}")
    for p in solid_points:
        assert_point_solid(part, p, f"{name}: material at {p}")


def main():
    print("Generating X-Axis motion parts (dual 8mm, ADR-021)...")

    rod_spacing = 30.0  # vertical stack distance
    beam_length = build_volume("X") + 100

    geom = XAxisGeometry(
        rod_spacing=rod_spacing,
        beam_length=beam_length,
    )

    rods = [(0.0, 0.0, rod_spacing / 2), (0.0, 0.0, -rod_spacing / 2)]

    # --- Gantry beam ---
    beam = make_x_gantry_beam(geom)
    # Rod runs along X through bores that cross the beam; sample at centre.
    _verify(
        beam,
        "x_gantry_beam",
        hollow_points=[(0, 0, rz) for rz in (rod_spacing / 2, -rod_spacing / 2)],
        solid_points=[(0, 0, 0)],  # web between the two rods is solid
    )
    print(f"\n  x_gantry_beam  ({beam_length:.0f}mm span)")
    print(f"    volume: {beam.volume:.0f} mm^3")
    export_part(beam, "x_gantry_beam")

    # --- Carriage ---
    carriage = make_x_carriage(geom)
    _verify(
        carriage,
        "x_carriage",
        hollow_points=[(0, 0, rz) for rz in (rod_spacing / 2, -rod_spacing / 2)],
        solid_points=[],
    )
    print(f"\n  x_carriage")
    print(f"    rod spacing: {rod_spacing:.0f}mm (vertical stack)")
    print(f"    bearing bore: {BEARING_BORE_DIA:.1f}mm for {SMOOTH_ROD_DIA:.0f}mm rod")
    print(f"    volume: {carriage.volume:.0f} mm^3")
    export_part(carriage, "x_carriage")

    # --- End plates (pair) ---
    plate = make_x_end_plate(geom)
    _verify(
        plate,
        "x_end_plate",
        hollow_points=[(0, 0, rz) for rz in (rod_spacing / 2, -rod_spacing / 2)],
        solid_points=[],
    )
    print(f"\n  x_end_plate  (x2)")
    print(f"    volume: {plate.volume:.0f} mm^3")
    export_part(plate, "x_end_plate")

    print("\nX-Axis parts complete!")
    print("  1x x_gantry_beam")
    print("  1x x_carriage")
    print("  2x x_end_plate")
    return True


if __name__ == "__main__":
    main()