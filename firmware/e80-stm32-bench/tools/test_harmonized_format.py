#!/usr/bin/env python3
"""Tests for the harmonized 23-field PKT+STAT format.

Covers:
  T1-T8   parse_pkt_line() tests
  T9-T10  format_pkt_line() tests
  T11-T12 format_stat_line() tests
  T13-T16 HarmonizedRxLogWriter / HarmonizedTxLogWriter tests
  T17-T24 gps_stitch.py harmonized support (see test_gps_stitch.py)
"""
import os
import sys
import tempfile

import pytest

# Make e80_bench_ctl importable
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from e80_bench_ctl import (  # noqa: E402
    PKT_FIELD_ORDER,
    HarmonizedRxLogWriter,
    HarmonizedTxLogWriter,
    format_pkt_line,
    format_stat_line,
    parse_pkt_line,
    parse_pkt_line_legacy,
)


# ---------------------------------------------------------------------------
# T1-T8: parse_pkt_line()
# ---------------------------------------------------------------------------

def test_t1_valid_23_field_pkt_line():
    """T1: Valid 23-field PKT line parses all fields with harmonized names."""
    line = "PKT,42,7,1,0,123456,-24.0,0.0,1,0,0,868000000,FLRC,8,0,3,10,64,0,0,0,0,0,0"
    d = parse_pkt_line(line)
    assert d is not None, "Expected dict, got None"
    assert d["session_id"] == 42
    assert d["config_id"] == 7
    assert d["replicate"] == 1
    assert d["seq"] == 0
    assert d["ts_ms"] == 123456
    assert d["rssi_dbm"] == -24.0
    assert d["snr_db"] == 0.0
    assert d["crc_ok"] == 1
    assert d["bit_err"] == 0
    assert d["bytes_bad"] == 0
    assert d["freq_hz"] == 868000000
    assert d["mod"] == "FLRC"
    assert d["sf"] == 8
    assert d["bw_khz"] == 0
    assert d["cr"] == 3
    assert d["power_dbm"] == 10
    assert d["pkt_size"] == 64
    assert d["gps_fix"] == 0
    assert d["gps_lat"] == 0.0
    assert d["gps_lon"] == 0.0
    assert d["gps_alt"] == 0.0
    assert d["gps_sats"] == 0
    assert d["gps_hdop"] == 0.0


def test_t2_lora_pkt_line():
    """T2: LoRa PKT line with sf, bw_khz, cr, bytes_bad parsed correctly."""
    line = "PKT,42,3,1,5,344300,-80.0,7.5,1,12,2,868000000,LORA,7,125,5,10,64,0,0.0,0.0,0.0,0,0.0"
    d = parse_pkt_line(line)
    assert d is not None
    assert d["mod"] == "LORA"
    assert d["sf"] == 7
    assert d["bw_khz"] == 125
    assert d["cr"] == 5
    assert d["bytes_bad"] == 2
    assert d["bit_err"] == 12
    assert d["seq"] == 5
    assert d["replicate"] == 1


def test_t3_short_line_returns_none():
    """T3: Short line (too few fields) returns None."""
    assert parse_pkt_line("PKT,42,7,1,0") is None


def test_t4_non_pkt_line_returns_none():
    """T4: Non-PKT line returns None."""
    assert parse_pkt_line("STAT,role=RX,sent=100") is None


def test_t5_empty_line_returns_none():
    """T5: Empty line returns None."""
    assert parse_pkt_line("") is None
    assert parse_pkt_line("   ") is None


def test_t6_garbled_rssi_returns_none():
    """T6: Garbled RSSI (non-numeric) returns None."""
    line = "PKT,42,7,1,0,123,abc,0.0,1,0,0,868M,FLRC,8,0,3,10,64,0,0,0,0,0,0"
    assert parse_pkt_line(line) is None


def test_t7_negative_rssi_and_snr():
    """T7: Negative RSSI and SNR parsed correctly."""
    line = "PKT,42,7,1,0,123,-120.5,-15.0,0,128,10,868000000,LORA,12,125,8,10,64,0,0,0,0,0,0"
    d = parse_pkt_line(line)
    assert d is not None
    assert d["rssi_dbm"] == -120.5
    assert d["snr_db"] == -15.0
    assert d["crc_ok"] == 0
    assert d["bit_err"] == 128


def test_t8_real_firmware_line():
    """T8: Real firmware output from bench_pkt.c test — all fields parsed."""
    # Mirrors what bench_pkt_format() produces for a LoRa test packet.
    # Note: firmware emits integer RSSI/SNR (not floats) — field order is:
    # PKT,session,config,replicate,seq,ts_ms,rssi,snr,crc_ok,bit_err,bytes_bad,
    #    freq,mod,sf,bw_khz,cr,power,pkt_size,gps_fix,gps_lat,gps_lon,gps_alt,
    #    gps_sats,gps_hdop
    line = "PKT,42,7,3,1234,123456,-50,7,1,0,0,868000000,LORA,7,125,5,10,64,0,0,0,0,0,0,0"
    d = parse_pkt_line(line)
    assert d is not None
    assert d["session_id"] == 42
    assert d["config_id"] == 7
    assert d["replicate"] == 3
    assert d["seq"] == 1234
    assert d["ts_ms"] == 123456
    assert d["rssi_dbm"] == -50.0
    assert d["snr_db"] == 7.0
    assert d["crc_ok"] == 1
    assert d["freq_hz"] == 868000000
    assert d["mod"] == "LORA"
    assert d["sf"] == 7
    assert d["bw_khz"] == 125
    assert d["cr"] == 5
    assert d["power_dbm"] == 10
    assert d["pkt_size"] == 64


# ---------------------------------------------------------------------------
# T9-T10: format_pkt_line()
# ---------------------------------------------------------------------------

def test_t9_round_trip_parse_format_parse():
    """T9: Parse → format → parse round-trip yields identical dicts."""
    original = "PKT,42,7,1,0,123456,-24.0,0.0,1,0,0,868000000,FLRC,8,0,3,10,64,0,0,0,0,0,0"
    d1 = parse_pkt_line(original)
    assert d1 is not None
    formatted = format_pkt_line(d1)
    d2 = parse_pkt_line(formatted)
    assert d2 is not None
    # Compare key by key (parse produces typed values; format produces strings
    # that parse back to the same typed values)
    for key in PKT_FIELD_ORDER:
        assert d1[key] == d2[key], "Mismatch on {}: {} vs {}".format(
            key, d1[key], d2[key])


def test_t10_gps_fields_populated():
    """T10: GPS fields populated in the dict appear in the formatted line."""
    d = {
        "session_id": 1, "config_id": 1, "replicate": 1, "seq": 1, "ts_ms": 1000,
        "rssi_dbm": -70.0, "snr_db": 8.0, "crc_ok": 1, "bit_err": 0, "bytes_bad": 0,
        "freq_hz": 868000000, "mod": "LORA", "sf": 7, "bw_khz": 125, "cr": 5,
        "power_dbm": 10, "pkt_size": 64,
        "gps_fix": 1, "gps_lat": 52.0, "gps_lon": 4.0,
        "gps_alt": 10.0, "gps_sats": 8, "gps_hdop": 1.2,
    }
    line = format_pkt_line(d)
    assert line.startswith("PKT,")
    # GPS fields should appear near the end of the line: 1,52.0,4.0,10.0,8,1.2
    parts = line.split(",")
    assert parts[18] == "1"   # gps_fix
    assert parts[19] == "52.0"  # gps_lat
    assert parts[20] == "4.0"  # gps_lon
    assert parts[21] == "10.0"  # gps_alt
    assert parts[22] == "8"   # gps_sats
    assert parts[23] == "1.2"  # gps_hdop


# ---------------------------------------------------------------------------
# T11-T12: format_stat_line()
# ---------------------------------------------------------------------------

def test_t11_rx_stat_line():
    """T11: RX STAT line starts with STAT,role=RX and contains key fields."""
    stat = {
        "sent": 100, "sent_ok": 100, "recv": 98, "crc_err": 2,
        "per_pct": 2.0, "elapsed_s": 10.5, "kbps": 50.0,
        "rssi": -80.0, "snr": 7.5, "drops": 0, "gap_us": 1000,
    }
    line = format_stat_line("RX", stat, session=42, config=7, replicate=1)
    assert line.startswith("STAT,role=RX")
    assert "sent=100" in line
    assert "sent_ok=100" in line
    assert "rx=98" in line
    assert "crc_err=2" in line
    assert "session=42" in line
    assert "config=7" in line
    assert "replicate=1" in line


def test_t12_tx_stat_line():
    """T12: TX STAT line starts with STAT,role=TX."""
    stat = {
        "sent": 1000, "sent_ok": 999, "recv": 0, "crc_err": 0,
        "per_pct": 0.0, "elapsed_s": 30.0, "kbps": 100.0,
        "rssi": None, "snr": None, "drops": 0, "gap_us": 5000,
    }
    line = format_stat_line("TX", stat, session=42, config=3, replicate=1)
    assert line.startswith("STAT,role=TX")
    assert "sent=1000" in line
    assert "sent_ok=999" in line
    assert "session=42" in line
    assert "config=3" in line


# ---------------------------------------------------------------------------
# T13-T16: HarmonizedRxLogWriter / HarmonizedTxLogWriter
# ---------------------------------------------------------------------------

def _sample_pkt(seq=0, **overrides):
    """Build a sample parsed PKT dict for writer tests."""
    d = {
        "session_id": 1, "config_id": 1, "replicate": 1, "seq": seq, "ts_ms": 1000 + seq,
        "rssi_dbm": -70.0, "snr_db": 8.0, "crc_ok": 1, "bit_err": 0, "bytes_bad": 0,
        "freq_hz": 868000000, "mod": "LORA", "sf": 7, "bw_khz": 125, "cr": 5,
        "power_dbm": 10, "pkt_size": 64,
        "gps_fix": 0, "gps_lat": 0.0, "gps_lon": 0.0,
        "gps_alt": 0.0, "gps_sats": 0, "gps_hdop": 0.0,
    }
    d.update(overrides)
    return d


def test_t13_rx_writer_writes_pkt_lines(tmp_path):
    """T13: HarmonizedRxLogWriter writes 5 PKT lines to file."""
    path = str(tmp_path / "rx-log.csv")
    log = HarmonizedRxLogWriter(path)
    for i in range(5):
        log.pkt_line(_sample_pkt(seq=i))
    with open(path) as f:
        lines = f.read().splitlines()
    assert len(lines) == 5
    for ln in lines:
        assert ln.startswith("PKT,")


def test_t14_rx_writer_stat_after_pkts(tmp_path):
    """T14: After PKT lines, the writer emits a STAT line."""
    path = str(tmp_path / "rx-log.csv")
    log = HarmonizedRxLogWriter(path)
    log.pkt_line(_sample_pkt(seq=0))
    log.pkt_line(_sample_pkt(seq=1))
    stat = {"sent": 10, "sent_ok": 10, "recv": 9, "crc_err": 1,
            "per_pct": 10.0, "elapsed_s": 5.0, "kbps": 50.0,
            "rssi": -80.0, "snr": 7.0, "drops": 0, "gap_us": 1000}
    log.stat_line("RX", stat, session=1, config=1, replicate=1)
    with open(path) as f:
        lines = f.read().splitlines()
    assert len(lines) == 3
    assert lines[0].startswith("PKT,")
    assert lines[1].startswith("PKT,")
    assert lines[2].startswith("STAT,role=RX")


def test_t15_rx_writer_comment_lines(tmp_path):
    """T15: Comment lines are preserved in the output file."""
    path = str(tmp_path / "rx-log.csv")
    log = HarmonizedRxLogWriter(path)
    log.comment("SESSION_START t0=2026-08-24T12:00:00")
    log.pkt_line(_sample_pkt(seq=0))
    with open(path) as f:
        lines = f.read().splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("# ")
    assert "SESSION_START" in lines[0]
    assert lines[1].startswith("PKT,")


def test_t16_tx_writer_writes_stat_role_tx(tmp_path):
    """T16: HarmonizedTxLogWriter writes only STAT and comment lines."""
    path = str(tmp_path / "tx-log.csv")
    log = HarmonizedTxLogWriter(path, session_id=42)
    log.comment("DISTRIBUTED_TX_MODE session=42")
    stat = {"sent": 1000, "sent_ok": 999, "recv": 0, "crc_err": 0,
            "per_pct": 0.0, "elapsed_s": 30.0, "kbps": 100.0,
            "rssi": None, "snr": None, "drops": 0, "gap_us": 5000}
    log.stat_line(config_idx=7, stat_dict=stat, replicate=1)
    with open(path) as f:
        lines = f.read().splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("# ")
    assert lines[1].startswith("STAT,role=TX")
    assert "session=42" in lines[1]
    assert "config=7" in lines[1]


# ---------------------------------------------------------------------------
# Bonus: legacy parser still works (backward compat)
# ---------------------------------------------------------------------------

def test_legacy_parser_still_works():
    """The old parse_pkt_line is preserved as parse_pkt_line_legacy."""
    # Firmware emits the harmonized 23-field format; legacy parser
    # only extracts a subset, but it should not crash.
    line = "PKT,42,7,1,0,123456,-24.0,0.0,1,0,0,868000000,FLRC,8,0,3,10,64,0,0,0,0,0,0"
    d = parse_pkt_line_legacy(line)
    assert d is not None
    assert d["session"] == 42
    assert d["config"] == 7
    assert d["pkt_idx"] == 0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
