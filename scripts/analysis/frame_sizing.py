"""
Frame Sizing Calculator for Amalgam

Reports the frame a given bed needs. The frame size and the M10 rod lengths
come from amalgam.lib.layout, which derives them from what has to fit: the
gantry's travel, the bed's travel and the stack of parts under the bed. This
module adds the smooth-rod spans used for the sag calculation.
"""

import sys
from dataclasses import dataclass
from pathlib import Path

# The layout is plain Python, so the stdlib-only analysis tools can use it.
CAD_DIR = Path(__file__).resolve().parents[2] / "cad"
if str(CAD_DIR) not in sys.path:
    sys.path.insert(0, str(CAD_DIR))

from amalgam.lib.layout import (  # noqa: E402
    LayoutConfig,
    build_layout,
    builder_skeleton,
)


@dataclass
class FrameSizeResult:
    """Result of frame size calculation."""

    bed_x: float  # mm
    bed_y: float  # mm
    build_z: float  # mm

    # Frame dimensions (mm), from amalgam.lib.layout
    frame_x: float  # between the left and right uprights
    frame_y: float  # between the front and back uprights
    frame_z: float  # between the bottom and top X rods

    # M10 rod lengths to cut (mm), rounded up to 5 mm
    rod_x_length: float  # the 4 rods running left to right
    rod_y_length: float  # the 4 rods running front to back
    rod_z_length: float  # the 4 uprights

    # Smooth rod spans
    x_span: float  # mm (unsupported span for X gantry)
    y_span: float  # mm (unsupported span for Y rods)

    notes: list[str]


# Spans used for the sag calculation (mm). These are physics inputs and are
# kept as published in ADR-021, so its deflection numbers do not move. The
# frame itself is sized by amalgam.lib.layout, not by these.
CLEARANCES = {
    "x_motor": 60,  # X span = bed + this (220 + 60 = 280mm, ADR-021)
    "y_carriage": 50,  # Y span = bed + this
}


def calculate_frame_size(
    bed_x: float,
    bed_y: float,
    build_z: float,
    extruder_type: str = "PITAN",
    triple_z: bool = True,
) -> FrameSizeResult:
    """
    Calculate required frame dimensions from bed size.

    Args:
        bed_x: Heated bed X dimension in mm (e.g., 235)
        bed_y: Heated bed Y dimension in mm (e.g., 235)
        build_z: Desired Z build height in mm (e.g., 250)
        extruder_type: Recorded for the caller. The frame size does not
            depend on it; the layout assumes one toolhead envelope.
        triple_z: Whether using Triple-Z (affects the notes)

    Returns:
        FrameSizeResult with all calculated dimensions
    """
    notes = []

    # Frame size and M10 rod lengths come from the layout, which derives them
    # from what has to fit.
    layout_config = LayoutConfig(bed_x=bed_x, bed_y=bed_y, build_z=build_z)
    layout = build_layout(layout_config, skeleton=builder_skeleton(layout_config))
    cut = layout.cut_list()
    frame_x = layout.skeleton_x
    frame_y = layout.skeleton_y
    frame_z = layout.skeleton_z
    rod_x_length = cut["bottom_front_x"]
    rod_y_length = cut["bottom_left_y"]
    rod_z_length = cut["vertical_front_left"]

    # Calculate smooth rod spans
    # X span is roughly bed width + motor clearance
    x_span = bed_x + CLEARANCES["x_motor"]

    # Y span is bed depth + carriage travel
    y_span = bed_y + CLEARANCES["y_carriage"]

    # Add notes about the configuration
    x_supported = layout.skeleton_x - layout_config.x_end_width
    if x_supported > x_span:
        notes.append(
            f"NOTE: the frame's X rods support {x_supported:.0f}mm; "
            f"sag is calculated on a {x_span:.0f}mm span"
        )

    if triple_z:
        notes.append("Triple-Z: Z motors at front corners + back center")
    else:
        notes.append("Belted-Z: Single motor, belt drives all Z points")

    # Standard rod length recommendations
    if rod_x_length <= 500 and rod_y_length <= 500 and rod_z_length <= 500:
        notes.append("All rods can be cut from 1m stock (cut in half)")
    else:
        notes.append("Some rods require longer stock than 500mm")

    # Span warnings
    if x_span > 300:
        notes.append(f"WARNING: X span ({x_span}mm) is long - consider M10 rods")
    if y_span > 350:
        notes.append(f"WARNING: Y span ({y_span}mm) is long - verify rod stiffness")

    return FrameSizeResult(
        bed_x=bed_x,
        bed_y=bed_y,
        build_z=build_z,
        frame_x=frame_x,
        frame_y=frame_y,
        frame_z=frame_z,
        rod_x_length=rod_x_length,
        rod_y_length=rod_y_length,
        rod_z_length=rod_z_length,
        x_span=x_span,
        y_span=y_span,
        notes=notes,
    )


# Common bed sizes
COMMON_BEDS = {
    "ender3": (235, 235, "Ender 3 / CR-10 Mini"),
    "prusa_mk3": (250, 210, "Prusa MK3/MK3S"),
    "mk3_dual": (200, 200, "MK3 Dual (recommended for M8 rods)"),
    "ender5": (220, 220, "Ender 5"),
    "voron_v0": (120, 120, "Voron V0"),
    "custom_300": (300, 300, "Large custom"),
}


def suggest_bed_for_rods(
    rod_diameter: float,
    max_acceptable_sag: float = 0.035,
    rod_count: int = 1,
) -> list[tuple[str, float, float, str]]:
    """
    Suggest appropriate bed sizes for a given rod diameter.

    Args:
        rod_diameter: Smooth rod diameter in mm
        max_acceptable_sag: Maximum acceptable deflection in mm
        rod_count: Number of parallel rods sharing the load (ADR-021)

    Returns:
        List of (bed_name, x, y, description) tuples that work with this rod
    """
    if __package__:
        from .rod_sag import calculate_rod_sag, get_extruder_mass
    else:  # running as a script (python scripts/analysis/frame_sizing.py)
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from analysis.rod_sag import calculate_rod_sag, get_extruder_mass

    suitable = []
    pitan_mass = get_extruder_mass("PITAN")

    for name, (x, y, desc) in COMMON_BEDS.items():
        # Calculate frame size to get span
        frame = calculate_frame_size(x, y, 250)

        # Check rod sag at this span
        sag = calculate_rod_sag(
            rod_diameter, frame.x_span, pitan_mass, rod_count=rod_count
        )

        if sag.deflection <= max_acceptable_sag:
            suitable.append((name, x, y, desc))

    return suitable


if __name__ == "__main__":
    # Example usage
    print("Frame Sizing Example")
    print("=" * 50)

    # Calculate for Ender 3 bed with Pitan
    result = calculate_frame_size(
        bed_x=235,
        bed_y=235,
        build_z=250,
        extruder_type="PITAN",
        triple_z=True,
    )

    print(f"\nBed size: {result.bed_x} x {result.bed_y} mm")
    print(f"Build height: {result.build_z} mm")
    print(f"\nFrame dimensions (internal):")
    print(f"  X: {result.frame_x} mm")
    print(f"  Y: {result.frame_y} mm")
    print(f"  Z: {result.frame_z} mm")
    print(f"\nRod lengths needed:")
    print(f"  X rods: {result.rod_x_length} mm")
    print(f"  Y rods: {result.rod_y_length} mm")
    print(f"  Z rods: {result.rod_z_length} mm")
    print(f"\nSmooth rod spans:")
    print(f"  X span: {result.x_span} mm")
    print(f"  Y span: {result.y_span} mm")
    print(f"\nNotes:")
    for note in result.notes:
        print(f"  - {note}")
