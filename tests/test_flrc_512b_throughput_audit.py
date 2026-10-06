"""Host tests for tools/flrc_512b_throughput_audit.py — no hardware required.

These pin the arithmetic that settles the "2.6 Mbps at 512 B" claim: the goodput
ceiling at 2600 kbps FLRC is strictly below the air rate for every legal payload
length, and 512 B is not a legal length at all. If someone later "improves" the
model, these tests say which numbers the docs depend on.
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


# ── the on-air model ────────────────────────────────────────────────────────

def test_airtime_is_monotonic_in_payload():
    assert all(M.airtime_s(p, **M.MODEL_DRIVER) < M.airtime_s(p + 1, **M.MODEL_DRIVER)
               for p in range(6, 511))


def test_audit_model_reproduces_the_repo_numbers():
    # docs/lr2021-flrc-24ghz-datasheet-audit-2026-07-26.md:80 — 0.803 ms / 2540 kbps
    assert M.airtime_s(255, **M.MODEL_AUDIT) == pytest.approx(0.803e-3, abs=2e-6)
    assert M.goodput_ceiling_kbps(255, **M.MODEL_AUDIT) == pytest.approx(2540, abs=2)


def test_audit_model_reproduces_the_card_numbers():
    # card t_6b68897c quotes 2570 kbps at 511 B
    assert M.goodput_ceiling_kbps(511, **M.MODEL_AUDIT) == pytest.approx(2570, abs=2)


def test_driver_model_reproduces_measured_airtime():
    # 511 B, 32 b preamble, 4 B sync, 2 B CRC at 2600 kbps -> ~1.603 ms
    assert M.airtime_s(511, **M.MODEL_DRIVER) == pytest.approx(1.603e-3, abs=2e-6)


# ── the verdict: goodput can never reach the air rate ───────────────────────

@pytest.mark.parametrize("model", [M.MODEL_AUDIT, M.MODEL_DRIVER])
def test_every_ceiling_is_below_the_2600_air_rate(model):
    for payload in range(6, 512):
        assert M.goodput_ceiling_kbps(payload, **model) < 2600.0


def test_goodput_never_exceeds_the_air_rate():
    for payload in (255, 511):
        for model in (M.MODEL_AUDIT, M.MODEL_DRIVER):
            assert M.goodput_ceiling_kbps(payload, **model) <= M.FLRC_BR_2600_KBPS


def test_511b_ceiling_is_above_255b_but_not_double():
    """Payload size helps, but the air time grows with it — not a 2x lever."""
    lo = M.goodput_ceiling_kbps(255, **M.MODEL_DRIVER)
    hi = M.goodput_ceiling_kbps(511, **M.MODEL_DRIVER)
    assert hi > lo
    assert hi < 1.05 * lo  # measured: 2550.1 vs 2501.9 -> +1.9 %


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


def test_report_flags_511_as_legal_and_512_as_illegal():
    rep = M.build_report(str(REPO))
    assert rep["radio_lib_flrc_max"]["value"] == 511
    assert rep["firmware_capability"]["e80_firmware_clamp"]["token_found"]


def test_verdict_names_the_air_rate_not_goodput():
    rep = M.build_report(str(REPO))
    assert rep["verdict"]["512b_measured"] is False
    assert rep["verdict"]["511b_measured"] is True
    assert "AIR RATE" in rep["verdict"]["i_or_ii"].upper()


def test_selftest_passes():
    assert M.selftest() == 0
