"""Tests for the measured-mass force window.

The point of this script is that the design lower bound is PROPORTIONAL to the
wing mass, and the repo's 3.2 g is an estimate. These tests pin:

1. the proportionality (double the mass, double the force);
2. the sensitivity the estimate costs (3.2 -> 5.0 g is +56 %);
3. the CLI contract (no args = estimate with a warning; args = measured);
4. that the contact-resistance budget crosses its stated threshold.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

MODEL = Path(__file__).resolve().parent.parent / "docs/analysis/wing_release_force_window.py"


@pytest.fixture(scope="module")
def m() -> ModuleType:
    spec = importlib.util.spec_from_file_location("wing_release_force_window", MODEL)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_lower_bound_is_proportional_to_mass(m: ModuleType) -> None:
    """Double the wing mass -> double every force in the window."""
    a = m.window(3.0)
    b = m.window(6.0)
    for x, y in zip(a, b):
        assert y == pytest.approx(2 * x, rel=1e-9)


def test_force_values_match_the_handover_table(m: ModuleType) -> None:
    """The numbers quoted in MEASUREMENT-REQUEST-WING-RELEASE.md section 1."""
    base, shock, design = m.window(3.2)
    assert base == pytest.approx(31.4, abs=0.1)
    assert shock == pytest.approx(313.8, abs=0.1)
    assert design == pytest.approx(470.7, abs=0.1)

    _, _, d5 = m.window(5.0)
    assert d5 == pytest.approx(735.5, abs=0.1)


def test_estimate_understates_the_window_by_more_than_half(m: ModuleType) -> None:
    """If a wing is 5 g not 3.2 g, the lower bound rises ~56 %.

    This is the whole reason measurement A exists: the design hinges on a
    number nobody has weighed.
    """
    _, _, est = m.window(m.WING_MASS_ESTIMATE_G)
    _, _, real = m.window(5.0)
    assert real / est > 1.5, f"expected >50 % rise, got {(real/est - 1)*100:.0f} %"


def test_no_argument_uses_the_estimate_and_says_so(
    m: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    """Silently adopting the estimate would be the bug this guards."""
    rc = m.main(["prog"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "ESTIMATE" in out, "the default must be labelled an estimate"
    assert f"{m.WING_MASS_ESTIMATE_G}" in out


def test_measured_argument_replaces_the_estimate(
    m: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = m.main(["prog", "4.15"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "MEASURED" in out
    assert "610.5" in out, "4.15 g -> 610.5 mN lower bound"


def test_two_wings_report_the_spread(
    m: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    """Build repeatability is a first-class output, not a hidden detail."""
    rc = m.main(["prog", "4.15", "4.22"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "spread" in out.lower()
    assert "1.7 %" in out or "1.6 %" in out


def test_bad_argument_is_rejected(m: ModuleType) -> None:
    assert m.main(["prog", "heavy"]) == 2


def test_contact_budget_prints_the_stated_threshold(
    m: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    m.main(["prog", "3.2"])
    out = capsys.readouterr().out
    assert "100 mohm" in out or "100 m" in out
    # the 100 mohm row must show the 0.67 % figure quoted in the request doc
    assert "0.67%" in out


def test_harvest_current_matches_the_adr(m: ModuleType) -> None:
    """400 mA is the per-wing daytime figure from ADR-046 s2.3."""
    assert m.I_HARVEST_A == pytest.approx(0.4)
    assert m.V_STACK == pytest.approx(6.0)
    assert m.P_HARVEST_W == pytest.approx(2.4)
