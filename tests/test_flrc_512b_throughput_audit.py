"""Host tests for tools/flrc_512b_throughput_audit.py — no hardware required.

These pin the arithmetic that settles the "2.6 Mbps at 512 B" claim:

  * the goodput ceiling at BR2600 is strictly below the air rate for every legal
    payload length, under every model;
  * 512 B is not a legal length at all (511 B is the driver maximum);
  * the repo's published 2540/2570 kbps ceiling is an *uncoded* bound, and the
    firmware's actual CR 3/4 configuration lowers the real ceiling to ~1910 kbps
    at 511 B — which is what the docs must quote from now on.

If someone later "improves" the model, these tests say which numbers the docs
depend on.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
TOOL = REPO / "tools" / "flrc_512b_throughput_audit.py"

pytestmark = pytest.mark.unit


def _load():
    spec = importlib.util.spec_from_file_location("flrc_512b_audit", TOOL)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # Register before exec so @dataclass-style annotation lookups resolve.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


M = _load()

ALL_MODELS = (M.MODEL_AUDIT, M.MODEL_AUDIT_CRC)


# ── the on-air models ───────────────────────────────────────────────────────

def test_airtime_is_monotonic_in_payload():
    assert all(M.airtime_s(p, **M.MODEL_AUDIT_CRC) < M.airtime_s(p + 1, **M.MODEL_AUDIT_CRC)
               for p in range(6, 511))


def test_audit_model_reproduces_the_repo_numbers():
    # docs/lr2021-flrc-24ghz-datasheet-audit-2026-07-26.md:80 — 0.803 ms / 2540 kbps
    assert M.airtime_s(255, **M.MODEL_AUDIT) == pytest.approx(0.803e-3, abs=2e-6)
    assert M.goodput_ceiling_kbps(255, **M.MODEL_AUDIT) == pytest.approx(2540, abs=2)


def test_audit_model_reproduces_the_card_numbers():
    # card t_6b68897c quotes 2570 kbps at 511 B
    assert M.goodput_ceiling_kbps(511, **M.MODEL_AUDIT) == pytest.approx(2570, abs=2)


def test_audit_crc_model_airtime():
    # 16 b preamble + 32 b sync + (511 + 2) * 8 at 2600 kbps
    assert M.airtime_s(511, **M.MODEL_AUDIT_CRC) == pytest.approx(1.5969e-3, abs=2e-6)


def test_fw_cr34_model_matches_the_driver_numerator():
    """The shipped config is CR 3/4 (src/radio_bench.c:55), so the driver's
    numerator charges ceil(12 * n_coded / 9) for the coded field."""
    assert M.FW_CR_DEN == 9
    assert M.fw_airtime_s(511) == pytest.approx(2.1404e-3, abs=1e-6)
    assert M.fw_goodput_ceiling_kbps(511) == pytest.approx(1910.0, abs=1.5)
    assert M.fw_goodput_ceiling_kbps(255) == pytest.approx(1871.1, abs=1.5)
    assert M.fw_goodput_ceiling_kbps(127) == pytest.approx(1798.2, abs=1.5)


def test_fw_cr34_cross_checks_the_repo_on_air_figure():
    """full-sweep-report-20260821-175612.md computes 1921.8 kbps on air for
    BR2600 L511 @ CR3/4 from the sweep data; the independent numerator model
    must agree to within 1 %."""
    assert M.fw_goodput_ceiling_kbps(511) == pytest.approx(1921.8, rel=0.01)


def test_cr34_is_a_third_more_airtime_than_uncoded():
    assert (M.fw_airtime_s(255) / M.airtime_s(255, **M.MODEL_AUDIT_CRC)
            == pytest.approx(4 / 3, abs=0.02))


def test_uncoded_model_overstates_the_real_ceiling():
    """The card's 2570 kbps is not just optimistic vs 2600 — it is >33 % above
    what the shipped CR 3/4 configuration can deliver at the same payload."""
    assert M.goodput_ceiling_kbps(511, **M.MODEL_AUDIT) / M.fw_goodput_ceiling_kbps(511) > 1.33


# ── the verdict: goodput can never reach the air rate ───────────────────────

@pytest.mark.parametrize("model", ALL_MODELS)
def test_every_ceiling_is_below_the_2600_air_rate(model):
    for payload in range(6, 512):
        assert M.goodput_ceiling_kbps(payload, **model) < 2600.0


def test_fw_cr34_ceiling_is_below_the_air_rate_for_every_legal_payload():
    for payload in range(6, 512):
        assert M.fw_goodput_ceiling_kbps(payload) < 2600.0


def test_goodput_never_exceeds_the_air_rate():
    for payload in (255, 511):
        for model in ALL_MODELS:
            assert M.goodput_ceiling_kbps(payload, **model) <= M.FLRC_BR_2600_KBPS
        assert M.fw_goodput_ceiling_kbps(payload) <= M.FLRC_BR_2600_KBPS


def test_511b_ceiling_is_above_255b_but_not_double():
    """Payload size helps, but the air time grows with it — not a 2x lever."""
    lo = M.fw_goodput_ceiling_kbps(255)
    hi = M.fw_goodput_ceiling_kbps(511)
    assert hi > lo
    assert hi < 1.05 * lo  # 1910.0 vs 1871.1 -> +2.1 %


# ── the evidence audit ──────────────────────────────────────────────────────

def test_512_bytes_was_never_measured_on_disk():
    rep = M.build_report(str(REPO))
    assert 512 not in rep["flrc_payloads_ever_measured"]
    assert 512 in rep["payload_sizes_never_measured"]


def test_511_bytes_was_measured_and_delivered():
    rep = M.build_report(str(REPO))
    assert 511 in rep["flrc_payloads_ever_measured"]
    rows = [r for r in rep["flrc_rows_payload_ge_255"] if r["plen"] == 511]
    assert rows, "expected 511 B FLRC rows in the on-disk sweeps"
    for row in rows:
        assert row["rx"] > 0, f"{row['file']}: {row['label']} received nothing"
        assert row["bit_err"] == 0, f"{row['file']}: PRBS bit errors at {row['label']}"
    # the L511 delivery result exists at the top FLRC bit rate specifically
    assert any(r["br"] == "2600" and r["plen"] == 511 for r in rows), \
        "expected a BR2600 L511 row — that is the row the 2.6 Mbps claim rests on"


def test_511b_rows_are_868mhz_not_2440mhz():
    """The card asked for 2440 MHz; the on-disk 511 B evidence is 868 MHz.
    Pin it, so a doc that silently claims a 2.4 GHz 511 B run is caught."""
    rep = M.build_report(str(REPO))
    freqs = {r["freq"] for r in rep["flrc_rows_payload_ge_255"] if r["plen"] == 511}
    assert freqs == {"868000000"}, f"unexpected L511 frequencies: {sorted(freqs)}"


def test_report_flags_511_as_legal_and_512_as_illegal():
    rep = M.build_report(str(REPO))
    assert rep["radio_lib_flrc_max"]["value"] == 511
    caps = rep["firmware_capability"]
    assert caps["e80_firmware_clamp"]["token_found"]
    assert caps["driver_pld_len_range"]["token_found"]
    assert caps["driver_cr_scaled_numerator"]["token_found"]
    assert caps["fw_flrc_cr_3_4"]["token_found"], \
        "firmware no longer ships CR 3/4 — re-derive the ceiling numbers before " \
        "trusting any doc that quotes the CR-3/4 model"


# ── the 511 B bound must resolve inside the checkout (CI portability) ───────

def test_flrc_max_resolves_without_a_radiolib_checkout_next_to_the_repo():
    """Regression pin for the red `Tests` workflow on main (2026-10-09/10).

    The old probe looked only at `../RadioLib` and `~/repos/RadioLib` — paths
    that do not exist on a GitHub Actions runner — so `value` was None in CI and
    `test_report_flags_511_as_legal_and_512_as_illegal` failed on every push
    (runs 37992095474, 37988348046, 37946525396, 37946322065). The bound must be
    readable from the repository itself, with the external checkout advisory.
    """
    got = M.build_report(str(REPO))["radio_lib_flrc_max"]
    assert got["value"] == 511
    assert not Path(got["path"]).is_absolute(), got["path"]
    # same checkout, external RadioLib probing disabled -> still 511
    assert M.flrc_max_payload(str(REPO), external_radiolib=False)["value"] == 511


def test_flrc_max_records_every_in_repo_source_it_agrees_with():
    got = M.flrc_max_payload(str(REPO), external_radiolib=False)
    found = {k: v for k, v in got["sources"].items() if v}
    assert found, "no in-repo FLRC max source resolved"
    assert all(v["value"] == 511 for v in found.values()), found
    # the firmware's own named constant and the vendor driver's documented
    # range are two independent in-repo layers and must both answer 511
    assert {"fw_bench_start_len_max_flrc", "lr20xx_driver_pld_len_range"} <= set(found)
    # nothing in the external probe may override an in-repo value
    assert got["external_radiolib"]["present"] in (True, False)


def test_verdict_names_the_air_rate_not_goodput():
    rep = M.build_report(str(REPO))
    assert rep["verdict"]["512b_measured"] is False
    assert rep["verdict"]["511b_measured"] is True
    assert "AIR RATE" in rep["verdict"]["i_or_ii"].upper()
    # the (ii) branch is answered explicitly: the old ceiling model was wrong
    # optimistically, so fixing it makes 2.6 Mbps less reachable, not more
    assert "optimistic" in rep["verdict"]["part_ii_note"].lower()
    assert rep["verdict"]["511b_needs_sustained_run"] is True


def test_selftest_passes():
    assert M.selftest() == 0
