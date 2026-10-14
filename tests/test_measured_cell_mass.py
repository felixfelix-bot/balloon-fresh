"""Acceptance tests for the MEASURED cell masses (operator scales, 2026-10-14).

The repo records these readings in `docs/analysis/MEASURED-MASSES.md`, but the
first commit that landed them (062cb6da) added only a COMMENT block to
`wing_mass_model.py` -- `cell_mass_g()` kept returning the retired Si-density
estimate (0.5006 / 1.4951 g). These tests bind the model to the measurements so
the record and the arithmetic cannot drift apart again.

Readings: two balances -- 0.01 g for the 10-piece piles, 0.01 mg for singles.
Singles are the reference; the 10-piece mean is the cross-check (<2 %).
"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
MODEL = ROOT / "docs/analysis/wing_mass_model.py"

# operator readings, 2026-10-14
SINGLE = {"large": 1.382, "small": 0.440}
TENPACK = {"large": (10, 14.04), "small": (10, 4.462)}
OUTLINE_MM = {"large": (78.55, 38.90), "small": (52.07, 19.65)}
# the retired Si-density estimates this replaces
SI_EST = {"large": 1.4951, "small": 0.5006}


@pytest.fixture(scope="module")
def model():
    spec = importlib.util.spec_from_file_location("wing_mass_model", MODEL)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("key", ["large", "small"])
def test_cell_mass_is_the_measured_single_part_reading(model, key):
    """The reference reading is the single part (0.01 mg balance)."""
    assert model.cell_mass_g(key) == pytest.approx(SINGLE[key], abs=1e-9)


@pytest.mark.parametrize("key", ["large", "small"])
def test_measured_value_is_not_the_retired_si_estimate(model, key):
    """Regression: 062cb6da left cell_mass_g() returning the Si estimate."""
    assert model.cell_mass_g(key) != pytest.approx(SI_EST[key], rel=1e-6)


@pytest.mark.parametrize("key", ["large", "small"])
def test_single_and_tenpiece_routes_agree_within_two_percent(model, key):
    """The two weighing routes are an independent cross-check."""
    n, total = TENPACK[key]
    assert abs(model.cell_mass_g(key) - total / n) / (total / n) < 0.02


@pytest.mark.parametrize("key", ["large", "small"])
def test_model_exposes_the_measured_constants(model, key):
    """The constants must exist and match -- the block used to be inert."""
    assert model.MEASURED_CELL_G[key] == pytest.approx(SINGLE[key], abs=1e-9)
    n, total = TENPACK[key]
    assert model.MEASURED_CELL_10PACK_G[key] == pytest.approx(total / n, abs=1e-9)


def test_balloon_constant_is_recorded(model):
    assert model.MEASURED_BALLOON_G == pytest.approx(46.84, abs=1e-9)


def test_the_two_sizes_share_one_areal_density(model):
    """One cell technology, two cut sizes: areal densities within 10 %."""
    def areal(key):
        l, w = OUTLINE_MM[key]
        return model.cell_mass_g(key) / (l * w * 0.01)

    assert 0.9 < areal("large") / areal("small") < 1.1


def test_unknown_cell_size_is_rejected(model):
    with pytest.raises(KeyError):
        model.cell_mass_g("nonexistent")


def test_wing_total_uses_the_measured_mass(model):
    """3 cells in series per wing -> a wing carries 3x the measured cell."""
    assert 3 * model.cell_mass_g("small") == pytest.approx(3 * SINGLE["small"], abs=1e-9)


def test_module_is_executable_script():
    """The shebang must stay line 1 (062cb6da put the comment block above it)."""
    first = MODEL.read_text().splitlines()[0]
    assert first.startswith("#!"), f"shebang is not line 1: {first!r}"
