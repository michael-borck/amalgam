#!/usr/bin/env python3
"""
Export config.py values to Quarto variables format.

Usage:
    python scripts/export_config.py > docs/_variables.yml
    python scripts/export_config.py --config cad/config.py.example
    python scripts/export_config.py --tier 3    # Tier-specific

This generates a YAML file that Quarto can use for conditional content
and variable substitution in documentation.

Frame dimensions and rod lengths are calculated from the build volume by
analysis.frame_sizing, the same module scripts/analyze.py uses. The published
docs/_variables.yml is the export of cad/config.py.example, and
scripts/tests/test_export_config.py checks that it stays that way.
"""

import sys
from pathlib import Path

# Add scripts directory to path
scripts_path = Path(__file__).parent
sys.path.insert(0, str(scripts_path))

DEFAULT_CONFIG = scripts_path.parent / "cad" / "config.py"


def get_config_values(config_path: Path) -> dict:
    """Load a config file and extract values."""
    if not config_path.exists():
        print(f"Error: {config_path} not found", file=sys.stderr)
        print("Run 'python scripts/wizard.py' first", file=sys.stderr)
        sys.exit(1)

    config_globals = {}
    try:
        exec(config_path.read_text(), config_globals)
    except Exception as e:
        print(f"Error reading {config_path.name}: {e}", file=sys.stderr)
        sys.exit(1)

    return {
        k: v for k, v in config_globals.items()
        if not k.startswith("_") and not callable(v)
    }


def require(config: dict, key: str):
    """Return config[key], or stop. The guides print it, so it has no default."""
    if key not in config:
        print(f"Error: {key} is not defined in the config", file=sys.stderr)
        print(
            "The guides print this value, so it cannot be defaulted.", file=sys.stderr
        )
        sys.exit(1)
    return config[key]


def export_quarto_variables(config_path: Path):
    """Export config values as Quarto variables."""
    from analysis.frame_sizing import calculate_frame_size

    config = get_config_values(config_path)

    # Get build volume, keyed "X", "Y" and "Z"
    build_volume = {k.upper(): v for k, v in require(config, "BUILD_VOLUME").items()}
    missing = [axis for axis in ("X", "Y", "Z") if axis not in build_volume]
    if missing:
        print(f"Error: BUILD_VOLUME has no {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)
    bed_x, bed_y, build_z = (build_volume[axis] for axis in ("X", "Y", "Z"))

    z_configuration = config.get("Z_CONFIGURATION", "triple")
    triple_z = bool(config.get("TRIPLE_Z", z_configuration == "triple"))
    extruder_type = config.get("EXTRUDER_TYPE", "PITAN")

    frame = calculate_frame_size(
        bed_x,
        bed_y,
        build_z,
        extruder_type=extruder_type,
        triple_z=triple_z,
    )

    # Build the variables dict
    variables = {
        # Bed/build volume
        "bed_x": bed_x,
        "bed_y": bed_y,
        "build_z": build_z,

        # Rods
        "smooth_rod_dia": require(config, "SMOOTH_ROD_DIA"),
        "m10_nominal": config.get("M10_NOMINAL_DIA", 10.0),
        "lumpy_factor": config.get("LUMPY_FACTOR", 0.5),

        # Extruder
        "extruder_type": extruder_type,
        "extruder_mass": config.get("EXTRUDER_MASS", 280),

        # Board
        "primary_board": config.get("PRIMARY_BOARD", "MKS_SKIPR"),
        "total_drivers": config.get("TOTAL_DRIVERS", 6),

        # Tier and Z config
        "tier": config.get("BUILD_TIER", 3),
        "z_config": "triple" if triple_z else "belt",
        "has_canbus": config.get("HAS_CANBUS", True),

        # Frame dimensions: between the uprights, then the M10 rods to cut
        "frame_x": frame.frame_x,
        "frame_y": frame.frame_y,
        "frame_z": frame.frame_z,
        "rod_x_length": frame.rod_x_length,
        "rod_y_length": frame.rod_y_length,
        "rod_z_length": frame.rod_z_length,
        "x_span": frame.x_span,
        "y_span": frame.y_span,

        # Hotend
        "hotend_type": config.get("HOTEND_TYPE", "E3D_V6_CLONE"),
        "groovemount_dia": config.get("GROOVEMOUNT_DIA", 16.0),

        # Brand palette
        "brand_body_color": config.get("BRAND_BODY_COLOR", "#4A4A4A"),
        "brand_accent_color": config.get("BRAND_ACCENT_COLOR", "#FFFFFF"),
        "brand_base_color": config.get("BRAND_BASE_COLOR", "#1A1A1A"),

        # Logo pad
        "logo_pad_enabled": config.get("LOGO_PAD_ENABLED", True),
        "logo_pad_diameter": config.get("LOGO_PAD_DIAMETER", 18.0),
        "logo_pad_height": config.get("LOGO_PAD_HEIGHT", 0.5),

        # Texture recommendations
        "fuzzy_skin_recommended": config.get("FUZZY_SKIN_RECOMMENDED", True),
        "fuzzy_skin_point_distance": config.get("FUZZY_SKIN_POINT_DISTANCE", 0.3),
        "fuzzy_skin_thickness": config.get("FUZZY_SKIN_THICKNESS", 0.2),
    }

    # Add derived values
    tier = variables["tier"]
    tier_names = {
        0: "Klipper Only",
        1: "Single Donor",
        2: "Dual Donor",
        3: "Reference Spec",
        4: "Buy Everything",
    }
    variables["tier_name"] = tier_names.get(tier, f"Tier {tier}")

    variables["z_type_desc"] = "Triple Independent Z" if triple_z else "Belt-Driven Z"

    # Output as YAML
    try:
        source = config_path.resolve().relative_to(scripts_path.resolve().parent)
    except ValueError:
        source = config_path.name
    print(f"# Auto-generated from {source} by scripts/export_config.py")
    print(
        "# Regenerate: python scripts/export_config.py --config <config> "
        "> docs/_variables.yml"
    )
    print("")

    for key, value in variables.items():
        if isinstance(value, bool):
            print(f"{key}: {'true' if value else 'false'}")
        elif isinstance(value, str):
            # Quote strings
            print(f'{key}: "{value}"')
        elif isinstance(value, (int, float)):
            # Whole numbers print without a trailing .0
            print(f"{key}: {int(value) if float(value).is_integer() else value}")
        elif isinstance(value, list):
            # Format lists
            print(f"{key}:")
            for item in value:
                print(f'  - "{item}"')
        else:
            print(f'{key}: "{value}"')


def export_tier_config(tier: int):
    """Export tier-specific configuration."""

    tier_configs = {
        0: {
            "tier_name": "Tier 0: Klipper Only",
            "tier_desc": "Flash Klipper on existing printer",
            "klipper_host": "Laptop/RPi/Zero2W",
            "mcu": "Donor board",
            "z_system": "Keep donor Z system",
            "cost_estimate": "$0",
        },
        1: {
            "tier_name": "Tier 1: Single Donor",
            "tier_desc": "One donor printer, belt-driven Z",
            "klipper_host": "Laptop/RPi/Zero2W",
            "mcu": "Donor board",
            "z_system": "Belted Single-Z",
            "cost_estimate": "~$80 AUD",
        },
        2: {
            "tier_name": "Tier 2: Dual Donor",
            "tier_desc": "Two donors, Triple-Z, multi-MCU",
            "klipper_host": "Laptop/RPi/Zero2W",
            "mcu": "Multi-MCU (2 donor boards)",
            "z_system": "Triple-Z Independent",
            "cost_estimate": "~$200 AUD",
        },
        3: {
            "tier_name": "Tier 3: Reference Spec",
            "tier_desc": "MKS SKIPR, Triple-Z, CAN bus ready",
            "klipper_host": "Integrated (SKIPR)",
            "mcu": "MKS SKIPR",
            "z_system": "Triple-Z Independent",
            "cost_estimate": "~$270 AUD",
        },
    }

    if tier not in tier_configs:
        print(f"Error: Unknown tier {tier}", file=sys.stderr)
        sys.exit(1)

    print(f"# Tier {tier} Configuration")
    for key, value in tier_configs[tier].items():
        print(f'{key}: "{value}"')


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Export config.py to Quarto variables")
    parser.add_argument("--tier", type=int, choices=[0, 1, 2, 3],
                        help="Export tier-specific config")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG,
                        help="Config file to export (default: cad/config.py)")
    args = parser.parse_args()

    if args.tier is not None:
        export_tier_config(args.tier)
    else:
        export_quarto_variables(args.config)
