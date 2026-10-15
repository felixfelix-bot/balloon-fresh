"""Acceptance tests for the wing-release tradeoff arithmetic.

Locks the numbers in docs/analysis/wing-release-electrical-contacts.md. The
load-bearing claims are:

1. holding force is small (tens of mN), so FORCE is not what kills the idea;
2. NdFeB flux INCREASES at -60 C, i.e. the temperature coefficient works
   against a release;
3. the static hold draw is 3-4 ORDERS above the 100 uW night budget;
4. pulse energy is CHEAP (sub-Joule), so the hold -- not the shot -- is the
   disqualifier;
5. copper is ~1600x more conductive than nylon and melts ~4x hotter, so a
   nichrome element sized for nylon cannot sever a conductor;
6. the array is one series string with bypass DNP, so ONE open contact kills
   all four wings.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

MODEL = Path(__file__).resolve().parent.parent / "docs/analysis/wing_release_electrical.py"


@pytest.fixture(scope="module")
def m() -> ModuleType:
    spec = importlib.util.spec_from_file_location("wing_release_electrical", MODEL)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- 1. holding force is not the problem -------------------------------------
def test_holding_force_is_tens_of_millinewtons(m: ModuleType) -> None:
    """3.2 g at 1 g = ~31 mN; even x10 shock x1.5 margin stays under 0.5 N."""
    w = m.M_WING_KG * m.G
    assert 0.030 < w < 0.033
    design = w * m.SHOCK_G * m.DESIGN_MARGIN
    assert 0.40 < design < 0.55, "one wing's design holding force"
    assert design < 1.0, "a sub-Newton hold: force is not the constraint"


# --- 2. the temperature coefficient works against a release -------------------
def test_ndfeb_flux_increases_in_the_cold(m: ModuleType) -> None:
    """A release must become EASIER in the cold; for NdFeB it becomes harder."""
    factor = 1.0 + m.NDFEB_TEMPCO_K * (m.COLD_C - m.WARM_C)
    assert factor > 1.0, "flux must rise as it cools"
    assert 1.05 < factor < 1.12, f"expected ~+8.8 %, got {(factor-1)*100:+.1f} %"


# --- 3. static hold vs the night budget --------------------------------------
def test_static_hold_is_orders_above_the_night_budget(m: ModuleType) -> None:
    """ADR-036 gives 100 uW. Every active-hold class must be far above it."""
    budget = m.NIGHT_BUDGET_W
    active = {k: v for k, v in m.HOLD_CLASSES_W.items() if v > 0}
    assert active, "the table must contain active-hold classes"
    for name, p in active.items():
        ratio = p / budget
        assert ratio > 100, f"{name} must be >100x the night budget (got {ratio:.0f}x)"
    # and the worst offender is 3-4 orders, not 2
    assert max(active.values()) / budget > 1000


def test_passive_hold_has_no_static_penalty(m: ModuleType) -> None:
    assert m.HOLD_CLASSES_W["passive magnetic hold"] == 0.0


# --- 4. the shot is cheap; the hold is not -----------------------------------
def test_release_pulse_is_sub_joule_versus_the_nichrome_cut(m: ModuleType) -> None:
    """Nichrome needs 2.59 J; every realistic solenoid pulse is far less."""
    for ms, p in m.PULSES:
        j = p * ms / 1000.0
        assert j < m.NICHROME_CUT_J, f"{ms} ms @ {p} W must beat the nichrome cut"
    biggest = max(p * ms / 1000.0 for ms, p in m.PULSES)
    assert biggest < 0.20, "even the largest pulse stays well under a Joule"


# --- 5. nylon vs copper ------------------------------------------------------
def test_copper_is_far_harder_to_sever_than_nylon(m: ModuleType) -> None:
    """Both the melt point and the conductivity separate the two jobs."""
    assert m.COPPER_MELT_C / m.NYLON_MELT_C > 4.0, "melt-point ratio"
    assert m.COPPER_K / m.NYLON_K > 1000.0, "conductivity ratio ~1600x"


# --- 6. the topology claim is the decisive one -------------------------------
def test_main_prints_the_series_string_conclusion(
    m: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    """The reproduce command in the doc must work and state the decisive claim."""
    m.main()
    out = capsys.readouterr().out
    assert "series" in out.lower(), "main() must state the topology"
    assert "0 W" in out, "main() must state the open-string outcome"
    assert "100.0 %" in out, "one open contact costs the whole array"


def test_script_output_is_deterministic(
    m: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    """Two runs must agree: this is the doc's reproduce path, not a random draw."""
    m.main()
    first = capsys.readouterr().out
    m.main()
    second = capsys.readouterr().out
    assert first == second
    assert len(first) > 1500, "the report must actually be printed"
