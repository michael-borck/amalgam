"""
Tests for the analysis CLI entry points.

These are smoke tests, not behavioural tests: their job is to make sure the
scripts actually run and produce the output the README promises.

The most valuable one here is the standalone-module check. Every module in
scripts/analysis/ has a `__main__` demo block, and those blocks used to crash
with `ImportError: attempted relative import with no known parent package`
because the relative imports had no package context when run directly. The bug
was live in the repo and only surfaced because someone tried running the demo.
"""

import contextlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SCRIPTS_DIR.parent

ANALYSIS_MODULES = [
    "analysis/rod_sag.py",
    "analysis/frame_sizing.py",
    "analysis/acceleration.py",
]


@contextlib.contextmanager
def _temporary_repo():
    """Copy scripts/ and cad/ into a temp dir so writes don't hit the worktree.

    Some scripts (wizard.py) write cad/config.py. Tests must not overwrite a
    developer's local build config, so those runs happen against a throwaway copy.
    """
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        shutil.copytree(SCRIPTS_DIR, repo / "scripts")
        cad_src = REPO_ROOT / "cad"
        if cad_src.exists():
            shutil.copytree(
                cad_src,
                repo / "cad",
                ignore=shutil.ignore_patterns(
                    "exports", "calibration", "__pycache__", ".venv", ".*"
                ),
            )
        # wizard.py reads cad/config.py; ensure one exists for the copy to work.
        if not (repo / "cad" / "config.py").exists():
            example = repo / "cad" / "config.py.example"
            if example.exists():
                shutil.copy(example, repo / "cad" / "config.py")
        yield repo


class TestStandaloneModuleExecution:
    """`python scripts/analysis/<module>.py` must work.

    Regression guard for the relative-import crash in the `__main__` blocks.
    """

    @pytest.mark.parametrize(
        "module", ANALYSIS_MODULES, ids=[Path(m).stem for m in ANALYSIS_MODULES]
    )
    def test_module_runs_standalone(self, module):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / module)],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0, (
            f"{module} failed when run directly:\n{result.stderr}"
        )
        assert "ImportError" not in result.stderr, (
            f"{module} hit a relative-import error:\n{result.stderr}"
        )
        assert result.stdout.strip(), f"{module} produced no output"


class TestAnalyzeCLI:
    """The analysis CLI documented in the README.

    analyze.py --quick reads no config.py (its defaults are hardcoded to the
    reference spec), so these run against the real worktree safely.
    """

    def _run_quick(self):
        return subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "analyze.py"), "--quick"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=REPO_ROOT,
        )

    def test_quick_mode_runs(self):
        result = self._run_quick()
        assert result.returncode == 0, result.stderr
        assert "Reference Spec" in result.stdout

    def test_quick_mode_reports_dual_rods(self):
        """The reference spec must report the ADR-021 dual-rod config."""
        result = self._run_quick()
        assert result.returncode == 0, result.stderr
        assert "DUAL_VERTICAL" in result.stdout
        assert "2x M8" in result.stdout

    def test_verdict_is_derived_not_asserted(self):
        """A hardcoded 'well-engineered' string would hide spec drift.

        The output must contain a deflection number so the verdict is visibly
        traceable to a calculation.
        """
        result = self._run_quick()
        assert "Rod deflection:" in result.stdout
        assert "mm (" in result.stdout  # deflection followed by its verdict

    def test_quick_mode_matches_reference_spec_numbers(self):
        """Pin the documented reference spec: 220 bed, dual 8mm, 0.0156mm."""
        result = self._run_quick()
        assert "Bed: 220x220mm" in result.stdout
        assert "0.0156mm" in result.stdout


class TestWhatIfCLI:
    """whatif.py reads cad/config.py, so run against a temp copy."""

    def _run(self, flag):
        with _temporary_repo() as repo:
            return subprocess.run(
                [sys.executable, str(repo / "scripts" / "whatif.py"), flag],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=repo,
            )

    def test_compare_rods_runs(self):
        result = self._run("--compare-rods")
        assert result.returncode == 0, result.stderr
        assert "Rod Config" in result.stdout
        assert "DUAL_VERTICAL" in result.stdout

    def test_compare_beds_runs(self):
        result = self._run("--compare-beds")
        assert result.returncode == 0, result.stderr


class TestWizardCLI:
    def test_quick_mode_runs(self):
        """--quick exercises the full wizard flow with reference defaults.

        The wizard writes cad/config.py when run, so run it against a temporary
        copy of the repo rather than the working tree. (In CI, config.py is
        gitignored and absent anyway.)
        """
        with _temporary_repo() as repo:
            result = subprocess.run(
                [sys.executable, str(repo / "scripts" / "wizard.py"), "--quick"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=repo,
            )
            assert result.returncode == 0, result.stderr
            assert "DUAL_VERTICAL" in result.stdout

    def test_quick_mode_generates_config_with_rod_config(self):
        """The generated config must carry SMOOTH_ROD_CONFIG.

        config_builder.py previously omitted this key, so wizard-generated
        configs silently lost the ADR-021 rod mounting.
        """
        with _temporary_repo() as repo:
            result = subprocess.run(
                [sys.executable, str(repo / "scripts" / "wizard.py"), "--quick"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=repo,
            )
            assert result.returncode == 0, result.stderr

            generated = repo / "cad" / "config.py"
            assert generated.exists(), "wizard did not write cad/config.py"
            content = generated.read_text()
            assert "SMOOTH_ROD_CONFIG" in content
            assert "DUAL_VERTICAL" in content


class TestHelpFlags:
    """`--help` should work without touching config.py or stdin."""

    @pytest.mark.parametrize(
        "script", ["analyze.py", "whatif.py", "wizard.py", "build.py"]
    )
    def test_help_flag(self, script):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / script), "--help"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0, result.stderr
        assert "usage" in result.stdout.lower()