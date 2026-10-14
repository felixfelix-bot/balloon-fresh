"""Acceptance tests for the float-altitude model (balloon_altitude_vs_payload.py).

The model's job is to turn a payload mass into a float altitude for the Yokohama
32-inch sphere. These tests pin the physics and the inputs, and they pin the
CLAIMS the docs make about the result — so a later edit cannot quietly change the
altitude while the prose stays the same.
"""
import importlib.util
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
MODEL = ROOT / "docs/analysis/balloon_altitude_vs_payload.py"
DOC = ROOT / "docs/analysis/BALLOON-VOLUME-AND-ALTITUDE.md"
CSV = ROOT / "docs/analysis/out/balloon_altitude_vs_payload.csv"
PNG = ROOT / "docs/analysis/out/balloon_altitude_vs_payload.png"


@pytest.fixture(scope="module")
def m():
    spec = importlib.util.spec_from_file_location("alt_model", MODEL)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------- atmosphere
def test_isa_matches_the_repo_density_table(m):
    """The repo's ISA table is in kg/m3, which equals g/L numerically.

    Tolerance is 1 % because the repo table is a COARSE rounded transcription
    (its 10 km entry is 0.4135 where a continuous ISA gives 0.4127). This test
    is here to catch a unit blunder (a factor of 1000), not to re-derive ISA.
    """
    for km, rho_kgm3 in ((0, 1.2250), (10, 0.4135), (11, 0.3639),
                         (12, 0.3119), (14, 0.2279)):
        got = m.atmosphere(km * 1000.0)[2]
        assert got == pytest.approx(rho_kgm3, rel=0.01), f"{km} km"


def test_atmosphere_offset_moves_temperature_not_the_lapse_rate(m):
    t_cold = m.atmosphere(0.0, -15.0)[0]
    t_warm = m.atmosphere(0.0, +15.0)[0]
    assert t_warm - t_cold == pytest.approx(30.0, abs=1e-9)


# ---------------------------------------------------------------- geometry
def test_volume_derivations_agree_with_the_sources(m):
    """281 L geometric at 32 in; ~277 L at the community's 100 in circumference."""
    assert m.volume_L_from_diameter_in(32.0) == pytest.approx(281.2, abs=0.5)
    assert m.volume_L_from_circumference_in(100.0) == pytest.approx(276.7, abs=0.5)


# ---------------------------------------------------------------- validation
@pytest.mark.parametrize("payload_g,community_km", [(7.0, 13.5), (28.0, 10.3), (40.0, 10.0)])
def test_model_reproduces_real_flights(m, payload_g, community_km):
    """Against three logged flights on this envelope. Loose bound on purpose:
    the community figures are rounded and the flights were not at ISA."""
    got = m.solve(payload_g, m.volume_L_from_circumference_in(100.0), "He")["alt_m"] / 1000.0
    assert abs(got - community_km) < 2.0, f"{payload_g} g: model {got:.2f} vs {community_km}"


# ---------------------------------------------------------------- physics
def test_heavier_payload_floats_lower(m):
    """Monotonic: more mass needs denser air."""
    prev = 1e9
    for p in range(0, 61, 5):
        a = m.altitude_km(float(p), "nominal")
        assert a < prev, f"altitude did not fall at {p} g"
        prev = a


def test_float_altitude_is_independent_of_free_lift(m):
    """The float level is set by M_dry and V_full; the fill only decides whether
    the envelope reaches full volume. This is the model's central claim."""
    a3 = m.solve(57.0, 270.0, "He", free_lift_g=3.0)["alt_m"]
    a15 = m.solve(57.0, 270.0, "He", free_lift_g=15.0)["alt_m"]
    assert a3 == pytest.approx(a15, abs=1.0)      # within a metre


def test_float_altitude_does_depend_on_volume(m):
    a250 = m.solve(57.0, 250.0, "He")["alt_m"]
    a281 = m.solve(57.0, 281.0, "He")["alt_m"]
    assert a281 > a250 + 500.0                    # at least half a km apart


def test_hydrogen_floats_higher_than_helium(m):
    he = m.solve(57.0, 270.0, "He")["alt_m"]
    h2 = m.solve(57.0, 270.0, "H2")["alt_m"]
    assert h2 > he


def test_envelope_is_underfilled_at_launch_in_the_nominal_case(m):
    """A superpressure balloon launches PARTLY filled — that is the normal,
    safe state. If this ever reads >1.0 the model has been filled to taut on
    the ground, which is not how these are flown."""
    r = m.solve(57.0, 270.0, "He")
    assert r["fill_frac"] < 1.0
    assert r["taut_before_float"] is True


def test_unreachable_altitude_reports_nan_not_a_wrong_number(m):
    """A payload too heavy to float must not silently return a plausible km."""
    # 900 g payload on a 270 L envelope cannot float at any altitude
    r = m.solve(900.0, 270.0, "He")
    assert math.isnan(r["alt_m"]) or r["alt_m"] < 0.0


# ---------------------------------------------------------------- outputs
def test_outputs_exist(m):
    assert CSV.is_file(), "run the script to regenerate the CSV"
    assert PNG.is_file(), "run the script to regenerate the figure"


def test_csv_carries_every_case_and_the_physics_columns(m):
    header = CSV.read_text().splitlines()[0]
    for col in ("payload_g", "total_mass_g", "case", "volume_L", "gas",
                "altitude_km", "fill_frac", "gas_mass_g"):
        assert col in header, f"CSV lost the {col} column"
    body = CSV.read_text().splitlines()[1:]
    assert len(body) >= 3 * 20
    for case in ("worst", "nominal", "best"):
        assert any(case in line for line in body)


# ---------------------------------------------------------------- doc claims
def test_doc_records_the_volume_finding_and_its_sources(m):
    text = DOC.read_text()
    for needle in ("281", "276.7", "270", "Yokohama"):
        assert needle in text, f"the doc does not state {needle!r}"


def test_doc_states_our_payload_altitude(m):
    """The doc must carry the number the model produces for our payload."""
    text = DOC.read_text()
    nominal = m.altitude_km(57.0, "nominal")
    assert f"{nominal:.1f}" in text or f"{nominal:.2f}" in text, \
        f"doc does not quote the modelled {nominal:.2f} km for 57 g"


def test_doc_does_not_adopt_the_ai_free_lift_band(m):
    """A pasted AI answer suggested 10-15 g free lift. The repo's sourced band is
    5-8 g and rejects >8 g as a burst risk. The doc must not carry 10-15 g as
    our own guidance."""
    text = DOC.read_text().lower()
    assert "10–15 g" not in text and "10-15 g" not in text, \
        "the doc adopted the unverified 10-15 g free-lift band"
