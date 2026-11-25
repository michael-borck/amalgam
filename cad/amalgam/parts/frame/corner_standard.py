"""
Amalgam Standard Corner Bracket (Scaffold path)

A corner bracket for the M10 threaded-rod skeleton described in ADR-001 and
ADR-025. Two variants are produced:

  corner_standard_bottom  THROUGH_BORE -- rod passes fully through, nuts on the
                           far side. Strongest clamping, used on the bottom
                           corners which carry bed weight and Z-screw thrust.

  corner_standard_top     JAM_NUT -- blind bores from both faces with a jam nut
                           pocket on each. The rod does not protrude, so there
                           is nothing to snag and rod length errors do not
                           matter. Used on the top corners, which are lightly
                           loaded.

All geometry is verified by cad/tests/test_corner.py before export.
"""

import sys

from amalgam.lib.corner import (
    Anchoring,
    make_standard_corner,
)
from amalgam.lib.export import export_part
from amalgam.lib.verify import (
    assert_mirror_symmetry,
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
    print("This will create config.py with your build parameters")
    print("")
    sys.exit(1)


def _verify(corner, anchoring):
    """
    Run geometric checks before exporting.

    A bracket that fails these is worse than no bracket at all -- it looks
    plausible but will not hold a rod, or will fail under load.
    """
    assert_single_solid(corner, f"corner_standard_{anchoring.lower()}")
    assert_no_self_intersection(corner, f"corner_standard_{anchoring.lower()}")
    assert_mirror_symmetry(corner, "x", f"corner_standard_{anchoring.lower()}")
    assert_mirror_symmetry(corner, "y", f"corner_standard_{anchoring.lower()}")

    offset = CORNER_SIZE / 2 - WALL_THICKNESS
    half = CORNER_SIZE / 2

    # A rod passage is identified by the coordinate that is NON-zero: the rod
    # runs along the other axis. For (0, 20, 0) the rod travels along X, so the
    # bore must be probed by varying x.
    passages = [
        ("X", (0, offset, 0)),
        ("X", (0, -offset, 0)),
        ("Y", (offset, 0, 0)),
        ("Y", (-offset, 0, 0)),
    ]

    if anchoring == Anchoring.THROUGH_BORE:
        for _, p in passages:
            assert_point_empty(corner, p, f"rod axis at {p}")
    else:
        # Blind bores: hollow at each face along the rod axis, solid at the core.
        for axis, p in passages:
            idx = 0 if axis == "X" else 1
            for sign in (-1, 1):
                probe = list(p)
                probe[idx] = sign * (half - 3.0)
                assert_point_empty(corner, tuple(probe), f"bore mouth at {p}")
            assert_point_solid(corner, p, f"solid core at {p}")


def build_corner(anchoring):
    """Build and verify one corner variant."""
    corner = make_standard_corner(
        corner_size=CORNER_SIZE,
        rod_fit_dia=M10_FIT_DIA,
        wall_thickness=WALL_THICKNESS,
        anchoring=anchoring,
        jam_nut_pocket_depth=JAM_NUT_ACCESS_DIA / 2,
    )
    _verify(corner, anchoring)
    return corner


def main():
    print("Generating Standard Corners (Scaffold / M10 threaded rod)...")

    for anchoring, name in [
        (Anchoring.THROUGH_BORE, "corner_standard_bottom"),
        (Anchoring.JAM_NUT, "corner_standard_top"),
    ]:
        print(f"\n  {name} ({anchoring})")
        corner = build_corner(anchoring)

        print(f"    verified: single solid, valid, symmetric, rod passages clear")
        print(f"    volume: {corner.volume:.0f} mm^3")

        export_part(corner, name)

    print("\nStandard corners complete!")
    print("  4x corner_standard_bottom  (frame bottom, through-bore)")
    print("  4x corner_standard_top     (frame top, jam nut)")
    return True


if __name__ == "__main__":
    main()