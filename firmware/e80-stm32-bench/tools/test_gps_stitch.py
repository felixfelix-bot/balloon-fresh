#!/usr/bin/env python3
"""Tests for gps_stitch.py harmonized format support (T17-T22).

Covers:
  T17  Stitch harmonized PKT file with GPX — output has GPS fields populated
  T18  Stitch legacy CSV (backward compat)
  T19  Auto-detect harmonized format
  T20  Auto-detect legacy format
  T21  Missing --t0-epoch for harmonized raises error
  T22  GPS gap warning (nearest point 60s away still populates fields)
"""
import os
import sys
import tempfile

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from gps_stitch import (  # noqa: E402
    GpsPoint,
    load_rx_log,
    stitch_harmonized,
    write_harmonized_output,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pkt(ts_ms=1000, seq=0, **overrides):
    """Build a sample harmonized PKT dict."""
    d = {
        "session_id": 1, "config_id": 1, "replicate": 1, "seq": seq,
        "ts_ms": ts_ms,
        "rssi_dbm": -70.0, "snr_db": 8.0, "crc_ok": 1, "bit_err": 0,
        "bytes_bad": 0,
        "freq_hz": 868000000, "mod": "LORA", "sf": 7, "bw_khz": 125,
        "cr": 5, "power_dbm": 10, "pkt_size": 64,
        "gps_fix": 0, "gps_lat": 0.0, "gps_lon": 0.0,
        "gps_alt": 0.0, "gps_sats": 0, "gps_hdop": 0.0,
    }
    d.update(overrides)
    return d


def _write_harmonized_rx(path, pkts):
    """Write PKT lines to a file."""
    from e80_bench_ctl import format_pkt_line
    with open(path, "w") as f:
        for p in pkts:
            f.write(format_pkt_line(p) + "\n")


def _write_legacy_rx(path, rows):
    """Write a legacy 16-column CSV."""
    cols = ["session", "config", "pkt_idx", "ts_ms", "rssi_dbm", "snr_db",
            "crc_ok", "bit_err", "freq_hz", "mod", "sf_or_br", "bw",
            "pa_dbm", "len", "pcrc16", "captured_ts"]
    with open(path, "w", newline="") as f:
        import csv
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            w.writerow([r.get(c, "") for c in cols])


# ---------------------------------------------------------------------------
# T17: Stitch harmonized PKT file with GPS track
# ---------------------------------------------------------------------------

def test_t17_stitch_harmonized_with_gps(tmp_path):
    """T17: Stitch harmonized PKT file — output has GPS fields populated."""
    t0_epoch = 1724438400.0  # fixed epoch
    pkts = [_make_pkt(ts_ms=0, seq=0), _make_pkt(ts_ms=10000, seq=1)]
    rx_path = str(tmp_path / "rx-log.csv")
    _write_harmonized_rx(rx_path, pkts)

    # GPS point at ts_ms=0 (epoch = t0_epoch)
    gps_pts = [GpsPoint(t0_epoch, 52.0, 4.0, 10.0, "2024-08-23T20:00:00Z")]

    rx_rows, fmt = load_rx_log(rx_path)
    assert fmt == "harmonized"
    assert len(rx_rows) == 2

    result = stitch_harmonized(rx_rows, gps_pts, t0_epoch)
    assert len(result) == 2
    # First packet (ts_ms=0) → epoch = t0_epoch → exact match
    assert result[0]["gps_fix"] == 1
    assert result[0]["gps_lat"] == 52.0
    assert result[0]["gps_lon"] == 4.0
    assert result[0]["gps_alt"] == 10.0
    # Second packet (ts_ms=10000) → epoch = t0_epoch + 10s → 10s gap
    assert result[1]["gps_fix"] == 1  # within default 30s max_gap

    # Write and verify output
    out_path = str(tmp_path / "out.csv")
    write_harmonized_output(result, out_path)
    with open(out_path) as f:
        lines = f.read().splitlines()
    assert len(lines) >= 2
    for ln in lines[:2]:
        assert ln.startswith("PKT,")
    # GPS fields should be non-zero in the first PKT line
    parts = lines[0].split(",")
    assert parts[18] == "1"  # gps_fix=1
    assert parts[19] == "52.0"  # gps_lat


# ---------------------------------------------------------------------------
# T18: Stitch legacy CSV (backward compat)
# ---------------------------------------------------------------------------

def test_t18_stitch_legacy_csv(tmp_path):
    """T18: Legacy CSV — load_rx_log returns (rows, 'legacy')."""
    rows = [{"session": 1, "config": 1, "pkt_idx": 0, "ts_ms": 1000,
             "rssi_dbm": -70, "snr_db": 8, "crc_ok": 1, "bit_err": 0,
             "freq_hz": 868000000, "mod": "LORA", "sf_or_br": 7, "bw": 125,
             "pa_dbm": 10, "len": 64, "pcrc16": 12345,
             "captured_ts": "2024-08-23T20:00:01"}]
    rx_path = str(tmp_path / "rx-legacy.csv")
    _write_legacy_rx(rx_path, rows)

    rx_rows, fmt = load_rx_log(rx_path)
    assert fmt == "legacy"
    assert len(rx_rows) == 1
    assert rx_rows[0]["session"] == "1"  # DictReader returns strings


# ---------------------------------------------------------------------------
# T19: Auto-detect harmonized format
# ---------------------------------------------------------------------------

def test_t19_auto_detect_harmonized(tmp_path):
    """T19: PKT-prefixed file auto-detected as harmonized."""
    rx_path = str(tmp_path / "rx.csv")
    _write_harmonized_rx(rx_path, [_make_pkt()])
    _, fmt = load_rx_log(rx_path)
    assert fmt == "harmonized"


# ---------------------------------------------------------------------------
# T20: Auto-detect legacy format
# ---------------------------------------------------------------------------

def test_t20_auto_detect_legacy(tmp_path):
    """T20: CSV with header row auto-detected as legacy."""
    rx_path = str(tmp_path / "rx-legacy.csv")
    _write_legacy_rx(rx_path, [{"session": 1, "config": 1, "pkt_idx": 0,
                                "ts_ms": 1000, "rssi_dbm": -70, "snr_db": 8,
                                "crc_ok": 1, "bit_err": 0,
                                "freq_hz": 868000000, "mod": "LORA",
                                "sf_or_br": 7, "bw": 125, "pa_dbm": 10,
                                "len": 64, "pcrc16": 0,
                                "captured_ts": "2024-08-23T20:00:00"}])
    _, fmt = load_rx_log(rx_path)
    assert fmt == "legacy"


# ---------------------------------------------------------------------------
# T21: Missing --t0-epoch for harmonized raises error
# ---------------------------------------------------------------------------

def test_t21_missing_t0_epoch_raises():
    """T21: stitch_harmonized with t0_epoch=None raises ValueError."""
    pkts = [_make_pkt()]
    gps_pts = [GpsPoint(1724438400.0, 52.0, 4.0, 10.0)]
    with pytest.raises(ValueError, match="--t0-epoch"):
        stitch_harmonized(pkts, gps_pts, t0_epoch=None)


# ---------------------------------------------------------------------------
# T22: GPS gap warning (60s away — fields still populated)
# ---------------------------------------------------------------------------

def test_t22_gps_gap_warning(tmp_path):
    """T22: GPS track 60s from nearest packet — warning printed, fields populated."""
    t0_epoch = 1724438400.0
    pkts = [_make_pkt(ts_ms=0, seq=0)]
    # GPS point 60s before the packet (epoch - 60)
    gps_pts = [GpsPoint(t0_epoch - 60.0, 52.0, 4.0, 10.0,
                        "2024-08-23T19:59:00Z")]
    result = stitch_harmonized(pkts, gps_pts, t0_epoch, max_gap_s=30.0)
    # GPS fields should still be populated (warning, not skip)
    assert result[0]["gps_fix"] == 1
    assert result[0]["gps_lat"] == 52.0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
