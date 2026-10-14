"""Acceptance tests for the MEASURED cell masses (operator scale, 2026-10-14).

Locks in that `wing_mass_model.cell_mass_g()` returns the operator's weighed
values, not the bare-silicon area x thickness x density estimate it used to
compute (which was ~1.8x light because it ignored metallisation, busbars and
encapsulant).

Raw readings: docs/analysis/MEASURED-MASSES-2026-10-14.md
"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
MODEL = ROOT / "docs/analysis/wing_mass_model.py"

# Operator readings, 2026-10-14 (tier: user-measured). 10-pack means are the
# values the model must use; the singles are carried for the agreement check.
PACK = {"large": (10, 14.04), "small": (10, 4.462)}
SINGLE = {"large": 1.382, "small": 0.440}
OUTLINE_MM = {"large": (78.55, 38.90), "small": (52.07, 19.65)}


@pytest.fixture(scope="module")
def model():
    spec = importlib.util.spec_from_file_location("wing_mass_model", MODEL)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("key", ["large", "small"])
def test_cell_mass_is_the_measured_pack_mean(model, key):
    """The model must return the measured value, not a silicon estimate."""
    n, total = PACK[key]
    assert model.cell_mass_g(key) == pytest.approx(total / n, abs=1e-9)


@pytest.mark.parametrize("key", ["large", "small"])
def test_measured_value_agrees_with_the_single_part_reading(model, key):
    """The 10-pack mean and the single-part reading must agree within 5 %."""
    single = SINGLE[key]
    assert abs(model.cell_mass_g(key) - single) / single < 0.05


@pytest.mark.parametrize("key", ["large", "small"])
def test_model_no_longer_returns_the_bare_silicon_estimate(model, key):
    """Regression: the old AREA x t x rho_Si estimate must NOT be what ships.

    Measured vs the superseded geometric estimate:
        large  1.4040 g measured vs 1.4951 g modelled  (-6.1 %)
        small  0.4462 g measured vs 0.5006 g modelled  (-10.9 %)
    Direction is deliberately NOT asserted: the estimate is purely geometric,
    so it cannot know the real part's metallisation and encapsulant -- it was
    light for one size and heavy for the other. Only "not the old formula" is
    the contract.
    """
    l, w = OUTLINE_MM[key]
    area_cm2 = l * w * 0.01
    old = area_cm2 * (0.21 * 0.1) * model.SI_DENSITY   # the superseded formula
    assert model.cell_mass_g(key) != pytest.approx(old, rel=1e-6)


def test_the_two_sizes_share_one_areal_density(model):
    """One cell technology cut to two sizes: areal densities within 10 %."""
    def areal(key):
        l, w = OUTLINE_MM[key]
        return model.cell_mass_g(key) / (l * w * 0.01)

    ratio = areal("large") / areal("small")
    assert 0.9 < ratio < 1.1


def test_unknown_cell_size_is_rejected(model):
    with pytest.raises(KeyError):
        model.cell_mass_g("nonexistent")


def test_wing_totals_use_the_measured_mass(model):
    """3 cells in series per wing, so a wing carries 3x the measured cell."""
    n, total = PACK["small"]
    assert 3 * model.cell_mass_g("small") == pytest.approx(3 * total / n, abs=1e-9)
