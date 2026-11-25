"""
Regression tests pinning the rod-sag physics to the documented ADRs.

Two classes of drift are guarded against here:

1. The analysis code previously modelled only single rods while the docs
   specified dual rods, reporting the reference machine as ~1.7x stiffer than it
   really is. A missing 1/N term is now covered by TestDualRodRelationship and
   TestCompareRodOptions.

2. ADR-021 originally claimed dual 8mm deflects LESS than single 10mm. That was
   inverted: stiffness scales with d^4, so 2 x 8^4 = 8192 < 10^4 = 10000, making
   dual-8 81.9% as stiff and ~22% MORE deflected at every span. The tests assert
   the corrected relationship so the bad claim cannot creep back into the docs
   or the code.

Both failure modes produced reassuring wrong answers rather than errors, which is
why they needed pinning.
"""

import math

import pytest

from analysis.rod_sag import (
    calculate_second_moment,
    calculate_rod_sag,
    compare_rod_options,
    rods_for_config,
    ROD_CONFIGS,
)

# Physics constants from ADR-021 / the beam equation
E_STEEL = 200e9  # Pa
GRAVITY = 9.81  # m/s^2


def beam_deflection(rod_dia_mm, span_mm, mass_g, rod_count=1):
    """Independent reference implementation of delta = F*L^3 / (N*48*E*I).

    Deliberately written from the formula rather than by calling the code under
    test, so it can catch an error in that code.
    """
    d = rod_dia_mm / 1000
    L = span_mm / 1000
    mass_kg = mass_g / 1000
    I = math.pi * d**4 / 64
    force = mass_kg * GRAVITY
    return (force * L**3) / (rod_count * 48 * E_STEEL * I) * 1000


class TestADR021ReferenceTable:
    """The deflection table published in ADR-021 must stay reproducible."""

    # (label, rod_diameter, rod_count, documented deflection mm)
    TABLE = [
        ("Single 8mm", 8.0, 1, 0.066),
        ("Single 10mm", 10.0, 1, 0.027),
        ("Dual 8mm", 8.0, 2, 0.033),
    ]

    @pytest.mark.parametrize(
        "label,rod_dia,rod_count,documented",
        TABLE,
        ids=[t[0] for t in TABLE],
    )
    def test_matches_documented_deflection(self, label, rod_dia, rod_count, documented):
        result = calculate_rod_sag(rod_dia, 360, 280, rod_count=rod_count)
        # Docs round to 3dp; allow half of the last documented digit.
        assert result.deflection == pytest.approx(documented, abs=0.0005), (
            f"{label} deflection drifted from ADR-021"
        )

    @pytest.mark.parametrize(
        "label,rod_dia,rod_count,documented",
        TABLE,
        ids=[t[0] for t in TABLE],
    )
    def test_matches_independent_beam_calc(
        self, label, rod_dia, rod_count, documented
    ):
        result = calculate_rod_sag(rod_dia, 360, 280, rod_count=rod_count)
        expected = beam_deflection(rod_dia, 360, 280, rod_count)
        assert result.deflection == pytest.approx(expected, abs=1e-4), (
            f"{label} disagrees with delta = FL^3/(N*48EI)"
        )


class TestDualRodRelationship:
    """The documented ADR-021 relationship: dual-8 is 81.9% as stiff as single-10.

    An earlier revision of ADR-021 claimed dual 8mm deflects LESS than a single
    10mm. That is backwards -- stiffness scales with d^4, so 2 x 8^4 < 10^4 and
    dual-8 deflects ~22% MORE at every span. These tests pin the correct
    relationship so the inverted claim cannot creep back in.
    """

    # Stiffness ratio: dual-8 is 81.9% as stiff as single-10.
    STIFFNESS_RATIO = (2 * 8**4) / (10**4)  # 0.8192
    # Deflection is inversely proportional to stiffness, so dual-8 deflects
    # 1 / 0.8192 = 1.2206x as much -- i.e. ~22% more.
    DEFLECTION_RATIO = 1 / STIFFNESS_RATIO  # 1.2206

    @pytest.mark.parametrize("span", [250, 280, 300, 330, 360])
    def test_dual_8_deflects_more_than_single_10(self, span):
        """The load-bearing correction: dual-8 is the softer option."""
        dual_8 = calculate_rod_sag(8.0, span, 280, rod_count=2)
        single_10 = calculate_rod_sag(10.0, span, 280, rod_count=1)

        assert dual_8.deflection > single_10.deflection, (
            f"At {span}mm span dual-8 must deflect MORE than single-10 "
            f"(it is 81.9% as stiff). Got dual-8={dual_8.deflection:.4f}mm, "
            f"single-10={single_10.deflection:.4f}mm"
        )

    @pytest.mark.parametrize("span", [250, 280, 300, 330, 360])
    def test_deflection_ratio_is_constant_at_every_span(self, span):
        """2*8^4/10^4 is span-independent, so the ratio must be constant."""
        dual_8 = calculate_rod_sag(8.0, span, 280, rod_count=2)
        single_10 = calculate_rod_sag(10.0, span, 280, rod_count=1)

        assert dual_8.deflection / single_10.deflection == pytest.approx(
            self.DEFLECTION_RATIO, rel=1e-2
        )

    def test_stiffness_ratio_is_81_9_percent(self):
        assert self.STIFFNESS_RATIO == pytest.approx(0.8192, abs=1e-4)
        assert self.DEFLECTION_RATIO == pytest.approx(1.2206, abs=1e-3)

    def test_no_span_makes_dual_8_stiffer_than_single_10(self):
        """The stiffness ratio is < 1 for every possible span; guard it."""
        assert self.STIFFNESS_RATIO < 1.0
        for span in range(100, 601, 20):
            dual_8 = calculate_rod_sag(8.0, span, 280, rod_count=2)
            single_10 = calculate_rod_sag(10.0, span, 280, rod_count=1)
            assert dual_8.deflection > single_10.deflection

    def test_dual_8_halves_deflection_vs_single_8(self):
        """The genuine benefit of dual-8: halving vs single 8mm."""
        single = calculate_rod_sag(8.0, 300, 280, rod_count=1)
        dual = calculate_rod_sag(8.0, 300, 280, rod_count=2)
        assert dual.deflection == pytest.approx(single.deflection / 2, abs=1e-4)

    def test_dual_8_rescues_single_8(self):
        """Dual-8 is what makes 8mm rods viable at all."""
        single = calculate_rod_sag(8.0, 360, 280, rod_count=1)
        dual = calculate_rod_sag(8.0, 360, 280, rod_count=2)
        assert single.verdict == "excessive"
        assert dual.verdict in ("acceptable", "good", "excellent")

    def test_rod_count_scales_deflection_inversely(self):
        """N rods must give exactly 1/N the deflection."""
        baseline = calculate_rod_sag(8.0, 300, 280, rod_count=1)
        for n in (1, 2, 4):
            result = calculate_rod_sag(8.0, 300, 280, rod_count=n)
            assert result.deflection == pytest.approx(
                baseline.deflection / n, abs=1e-4
            ), f"rod_count={n} did not scale deflection by 1/{n}"

    def test_adding_a_rod_never_increases_deflection(self):
        for span in (250, 300, 360):
            single = calculate_rod_sag(8.0, span, 280, rod_count=1)
            dual = calculate_rod_sag(8.0, span, 280, rod_count=2)
            assert dual.deflection <= single.deflection

    def test_both_configs_pass_at_reference_bed(self):
        """The cost argument only holds if both clear the quality threshold."""
        # 220mm bed -> 280mm X span (see ADR-024 / frame_sizing.py)
        dual_8 = calculate_rod_sag(8.0, 280, 280, rod_count=2)
        single_10 = calculate_rod_sag(10.0, 280, 280, rod_count=1)

        assert dual_8.deflection == pytest.approx(0.0156, abs=5e-4)
        assert dual_8.verdict in ("excellent", "good")
        assert single_10.deflection == pytest.approx(0.0128, abs=5e-4)
        assert single_10.verdict in ("excellent", "good")

    def test_configs_diverge_toward_threshold_at_larger_spans(self):
        """Beyond the reference bed the gap becomes material (ADR-021 caveat)."""
        dual_8 = calculate_rod_sag(8.0, 330, 280, rod_count=2)
        single_10 = calculate_rod_sag(10.0, 330, 280, rod_count=1)

        assert dual_8.deflection == pytest.approx(0.0256, abs=5e-4)
        assert single_10.deflection == pytest.approx(0.0209, abs=5e-4)
        assert single_10.verdict == "good"
        assert dual_8.verdict == "acceptable"


class TestRodsForConfig:
    """Mapping SMOOTH_ROD_CONFIG strings to rod counts."""

    @pytest.mark.parametrize(
        "config,expected",
        [
            ("DUAL_VERTICAL", 2),
            ("DUAL", 2),
            ("DUAL_HORIZONTAL", 2),
            ("SINGLE", 1),
            ("dual_vertical", 2),  # case insensitive
            ("single", 1),
        ],
    )
    def test_known_configs(self, config, expected):
        assert rods_for_config(config) == expected

    def test_none_defaults_to_single(self):
        """Backwards compatible: absent config means single-rod (old behaviour)."""
        assert rods_for_config(None) == 1

    def test_empty_string_defaults_to_single(self):
        assert rods_for_config("") == 1

    def test_unknown_config_defaults_to_single(self):
        """An unrecognised value must not silently halve deflection."""
        assert rods_for_config("TRIPLE_TRIANGLE") == 1

    def test_all_mapped_configs_are_positive(self):
        for name, count in ROD_CONFIGS.items():
            assert count >= 1, f"{name} maps to invalid rod count {count}"


class TestBeamTheory:
    """The underlying physics, independent of rod count."""

    def test_second_moment_known_value(self):
        # I = pi * d^4 / 64 for a 10mm rod, in m^4
        expected = math.pi * (0.010**4) / 64
        assert calculate_second_moment(10.0) == pytest.approx(expected, rel=1e-9)

    def test_stiffness_goes_as_d_fourth(self):
        """I scales with d^4, so deflection must drop 16x from M8 to M16."""
        m8 = calculate_rod_sag(8.0, 300, 280, rod_count=1)
        m16 = calculate_rod_sag(16.0, 300, 280, rod_count=1)
        assert m8.deflection / m16.deflection == pytest.approx(16, rel=0.01)

    def test_deflection_goes_as_span_cubed(self):
        short = calculate_rod_sag(8.0, 200, 280, rod_count=1)
        long = calculate_rod_sag(8.0, 400, 280, rod_count=1)
        assert long.deflection / short.deflection == pytest.approx(8, rel=0.01)

    def test_deflection_goes_as_mass(self):
        light = calculate_rod_sag(8.0, 300, 140, rod_count=1)
        heavy = calculate_rod_sag(8.0, 300, 560, rod_count=1)
        assert heavy.deflection / light.deflection == pytest.approx(4, rel=0.01)

    def test_zero_mass_gives_zero_deflection(self):
        assert calculate_rod_sag(8.0, 300, 0, rod_count=1).deflection == 0.0


class TestValidation:
    """Guards against invalid input silently producing wrong physics."""

    def test_zero_rods_raises(self):
        """rod_count=0 would divide by zero and report infinite stiffness."""
        with pytest.raises(ValueError, match="rod_count"):
            calculate_rod_sag(8.0, 300, 280, rod_count=0)

    def test_negative_rods_raises(self):
        with pytest.raises(ValueError, match="rod_count"):
            calculate_rod_sag(8.0, 300, 280, rod_count=-1)


class TestCompareRodOptions:
    def test_propagates_rod_count(self):
        """The comparison helper must not silently revert to single-rod."""
        dual = compare_rod_options(300, 280, rod_sizes=[8.0], rod_count=2)
        single = compare_rod_options(300, 280, rod_sizes=[8.0], rod_count=1)

        assert dual[0].deflection == pytest.approx(single[0].deflection / 2, abs=1e-4)

    def test_preserves_rod_count_in_results(self):
        results = compare_rod_options(300, 280, rod_sizes=[8.0, 10.0], rod_count=2)
        assert all(r.rod_count == 2 for r in results)