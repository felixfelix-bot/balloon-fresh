"""Host tests for the LR2021 console parsing + the audit safety contract.

NO HARDWARE and NO pyserial: this imports only lr2021_parse (pure) and reads the
audit scripts as text. Run with any pytest interpreter, e.g.
  /opt/miniconda/bin/python -m pytest tools/lr2021/test_lr2021_audit.py -q
"""
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from lr2021_parse import (  # noqa: E402
    DEFAULT_CHANNELS_HZ,
    DR_TO_SF,
    EXTRA_CHANNELS_HZ,
    PIN,
    accepted,
    parse_id,
    parse_stat,
)

# A real ID? response captured from fw=5fa7912 on 2026-10-14 (see docs/analysis).
ID_LINE = (
    "ID E80BENCH v1.2 fw=5fa7912 role=RX armed=0 mod=flrc br=650000 "
    "freq=869850000 band=863-870MHz pa=22 pcap=+22dBm(OUTDOOR) chip=1.24 "
    "radio=awake boot=jump-ok quiet=0 buf=0"
)
STAT_LINE = (
    "STAT role=RX sent=0 sent_ok=0 rx=200 crc_err=14 per_x1e6=0 "
    "per_ci_x1e6=[0,18846] elapsed_s=2268.7 kbps=0 rssi_avg_dbm=-37.5 "
    "rssi_min_dbm=-40.5 rssi_max_dbm=-35.5 snr_avg_db=0.0 cr=1 session=0 "
    "config=7 replicate=0 drops=0 gap_us=5000 buf=0"
)


class TestParseId:
    def test_extracts_the_documented_fields(self):
        d = parse_id(ID_LINE)
        assert d["board"] == "E80BENCH"
        assert d["fw_version"] == "v1.2"
        assert d["fw"] == "5fa7912"
        assert d["role"] == "RX"
        assert d["bitrate_bps"] == "650000"
        assert d["freq_hz"] == "869850000"
        assert d["chip"] == "1.24"

    def test_band_flag_survives_the_override_form(self):
        line = ID_LINE.replace("band=863-870MHz", "band=OVERRIDE(410-2483MHz)")
        assert parse_id(line)["band"] == "OVERRIDE(410-2483MHz)"

    def test_partial_line_does_not_crash(self):
        assert parse_id("ID E80BENCH v1.2 fw=abc")["board"] == "E80BENCH"

    def test_garbage_yields_empty_dict(self):
        assert parse_id("(no response)") == {}

    def test_none_is_tolerated(self):
        assert parse_id(None) == {}


class TestParseStat:
    def test_extracts_key_value_pairs(self):
        d = parse_stat(STAT_LINE)
        assert d["rx"] == "200"
        assert d["crc_err"] == "14"
        assert d["rssi_avg_dbm"] == "-37.5"

    def test_role_only_stat(self):
        assert parse_stat("STAT role=RX")["role"] == "RX"


class TestAccepted:
    def test_ok_and_id_responses_are_accepted(self):
        assert accepted("OK FREQ 868100000")
        assert accepted("ID E80BENCH v1.2")

    def test_err_is_rejected(self):
        assert not accepted("ERR SYNTAX")
        assert not accepted("ERR ARG")

    def test_empty_and_none_are_rejected(self):
        assert not accepted("")
        assert not accepted(None)


class TestLoRaWANPlan:
    def test_dr_map_is_the_eu868_scheme(self):
        assert DR_TO_SF == {0: 12, 1: 11, 2: 10, 3: 9, 4: 8, 5: 7}

    def test_plan_contains_exactly_the_three_join_channels(self):
        assert DEFAULT_CHANNELS_HZ == [868100000, 868300000, 868500000]

    def test_sub_band_is_the_200khz_raster(self):
        assert EXTRA_CHANNELS_HZ == [
            867100000, 867300000, 867500000, 867700000, 867900000]

    def test_override_pin_matches_the_firmware_constant(self):
        assert PIN == "2026"


def _send_lines(filename):
    """The set of console strings the script ACTUALLY sends.

    Matches send calls only (cmd("..."), cmd(f"...")), never docstring prose --
    a comment saying "never send ARM TX" must not trip the contract.
    """
    text = (HERE / filename).read_text()
    return re.findall(r'cmd\(\s*f?"([^"]*)"', text)


class TestSafetyContract:
    """The audit must never transmit. Pinned against the SEND CALLS."""

    def test_audit_never_sends_arm_tx(self):
        assert not [c for c in _send_lines("e80_lr2021_audit.py")
                    if c.startswith("ARM TX")]

    def test_audit_never_sends_role_tx(self):
        assert not [c for c in _send_lines("e80_lr2021_audit.py")
                    if c.startswith("ROLE TX")]

    def test_audit_never_sends_start(self):
        assert not [c for c in _send_lines("e80_lr2021_audit.py")
                    if c.startswith("START")]

    def test_audit_does_not_send_prbs9(self):
        assert not [c for c in _send_lines("e80_lr2021_audit.py")
                    if c.startswith("PRBS9")]

    def test_lorawan_audit_never_transmits(self):
        sent = _send_lines("e80_lorawan_plan_audit.py")
        for forbidden in ("ARM TX", "ROLE TX", "START", "PRBS9"):
            assert not [c for c in sent if c.startswith(forbidden)], forbidden

    def test_send_line_extractor_actually_finds_calls(self):
        # counter-test: if the extractor returned nothing, every test above
        # would pass vacuously.
        assert len(_send_lines("e80_lorawan_plan_audit.py")) > 5
