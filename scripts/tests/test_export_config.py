"""
Tests for scripts/export_config.py and docs/_variables.yml.

docs/_variables.yml feeds the {{< var ... >}} shortcodes in the build guides,
so whatever it holds is what the website prints. It once carried a 235mm bed
and 0 for every frame dimension: the exporter read config keys that no longer
existed and fell back to those numbers without a word.

The analysis tests are stdlib-only, so these parse the exporter's flat
"key: value" output by hand instead of pulling in PyYAML.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPORTER = REPO_ROOT / "scripts" / "export_config.py"
EXAMPLE_CONFIG = REPO_ROOT / "cad" / "config.py.example"
PUBLISHED_VARIABLES = REPO_ROOT / "docs" / "_variables.yml"

DIMENSIONS = (
    "bed_x",
    "bed_y",
    "build_z",
    "frame_x",
    "frame_y",
    "frame_z",
    "rod_x_length",
    "rod_y_length",
    "rod_z_length",
    "x_span",
    "y_span",
)


def export(config):
    return subprocess.run(
        [sys.executable, str(EXPORTER), "--config", str(config)],
        capture_output=True,
        text=True,
        timeout=60,
    )


def values_from(yaml_text):
    """Read the flat key: value lines the exporter writes."""
    values = {}
    for line in yaml_text.splitlines():
        if line and not line.startswith("#") and ": " in line:
            key, value = line.split(": ", 1)
            values[key] = value.strip('"')
    return values


class TestExport:
    def test_published_variables_are_the_reference_config(self):
        result = export(EXAMPLE_CONFIG)
        assert result.returncode == 0, result.stderr
        assert result.stdout == PUBLISHED_VARIABLES.read_text()

    def test_every_dimension_is_set(self):
        values = values_from(export(EXAMPLE_CONFIG).stdout)
        for key in DIMENSIONS:
            assert float(values[key]) > 0, f"{key} is {values.get(key)!r}"

    def test_bed_comes_from_the_config(self, tmp_path):
        config = tmp_path / "config.py"
        config.write_text(
            'BUILD_VOLUME = {"X": 200, "Y": 200, "Z": 200}\nSMOOTH_ROD_DIA = 8.0\n'
        )
        values = values_from(export(config).stdout)
        assert (values["bed_x"], values["bed_y"], values["build_z"]) == (
            "200",
            "200",
            "200",
        )


class TestBrokenConfig:
    def test_missing_config_file(self):
        result = export(REPO_ROOT / "cad" / "no-such-config.py")
        assert result.returncode != 0
        assert result.stdout == ""

    def test_config_without_build_volume(self, tmp_path):
        config = tmp_path / "config.py"
        config.write_text("SMOOTH_ROD_DIA = 8.0\n")
        result = export(config)
        assert result.returncode != 0
        assert "BUILD_VOLUME" in result.stderr
        assert result.stdout == ""
