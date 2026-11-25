"""
MDF Squaring Jig (ADR-011).

The jig holds the bottom horizontal rods of the Scaffold frame at a true right
angle while the corner brackets are fitted. Without it, frame squareness comes
down to how carefully you cut the rods -- which is not good enough for a
220mm build volume.

Export produces the jig geometry. The base plate is cut from MDF by the
builder; this part is the printable guide that locates the rod seats and the
uprights. See docs/adr/011-laminated-plinth.md.
"""

import sys

from amalgam.lib.corner import make_mdf_squaring_jig
from amalgam.lib.export import export_part
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
    """Read a build-volume dimension, accepting either key casing."""
    vol = globals().get("BUILD_VOLUME", {}) or {}
    for key in (name, name.lower(), name.upper()):
        if key in vol:
            return float(vol[key])
    bed = globals().get(f"BED_SIZE_{name.upper()}")
    if bed:
        return float(bed)
    return 220.0


def main():
    print("Generating MDF Squaring Jig (ADR-011)...")

    bed_x = build_volume("X")
    bed_y = build_volume("Y")

    # The jig must span the full skeleton, not just the bed.
    skeleton_x = globals().get("SKELETON_X", bed_x + 110.0)
    skeleton_y = globals().get("SKELETON_Y", bed_y + 120.0)

    jig = make_mdf_squaring_jig(
        bed_x=bed_x,
        bed_y=bed_y,
        skeleton_x=skeleton_x,
        skeleton_y=skeleton_y,
    )

    assert_single_solid(jig, "squaring_jig")
    assert_no_self_intersection(jig, "squaring_jig")

    # Rod seats at each corner must be clear.
    sx = skeleton_x / 2 + 20 / 2
    sy = skeleton_y / 2 + 20 / 2
    for x in (-sx, sx):
        for y in (-sy, sy):
            assert_point_empty(jig, (x, y, 18 + 120 * 0.5),
                               f"rod seat at ({x:.0f},{y:.0f})")

    assert_point_solid(jig, (0, 0, 9), "base plate")

    bb = jig.bounding_box()
    print(f"\n  squaring_jig")
    print(f"    skeleton span: {skeleton_x:.0f} x {skeleton_y:.0f} mm")
    print(f"    jig footprint: {bb.max.X - bb.min.X:.0f} x {bb.max.Y - bb.min.Y:.0f} mm")
    print(f"    volume: {jig.volume:.0f} mm^3")
    print(f"    verified: single solid, 4 rod seats clear, base solid")

    export_part(jig, "squaring_jig")

    print("\nSquaring jig complete!")
    print("  1x squaring_jig  (print as a guide, or use as a layout template)")
    print(f"  MDF base: {skeleton_x + 60:.0f} x {skeleton_y + 60:.0f} x 18mm sheet")
    return True


if __name__ == "__main__":
    main()