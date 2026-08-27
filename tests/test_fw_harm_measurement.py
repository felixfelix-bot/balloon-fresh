"""Tests for fw_harm_measurement.py — summary stats, field validation, seq continuity, RSSI.

Tests the pure-function logic without serial port access:
- Summary statistics computation from sample PKT lines
- Field count validation (rejects lines with wrong field count)
- Seq continuity checker (detects gaps, duplicates)
- RSSI statistics (min/max/mean/stddev)
"""

import os
import sys

import pytest

# ── sys.path manipulation to import from tools/ ────────────────────────────
_TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

from fw_harm_measurement import (
    compute_stats,
    check_seq_continuity,
    check_ts_monotonic,
    validate_field_count,
    compute_summary_stats,
)
from pkt_parser import parse_pkt_line


# ── Sample PKT lines ────────────────────────────────────────────────────────

SAMPLE_PKT_LINES = [
    # seq 1-5, CRC OK, RSSI -80 to -85, FLRC
    "PKT,sess1,cfg-A,0,1,100,-80,0,1,0,0,868000000,FLRC,0,0,1,10,64,0,0,0,0,0,0",
    "PKT,sess1,cfg-A,0,2,200,-82,0,1,0,0,868000000,FLRC,0,0,1,10,64,0,0,0,0,0,0",
    "PKT,sess1,cfg-A,0,3,300,-83,0,1,0,0,868000000,FLRC,0,0,1,10,64,0,0,0,0,0,0",
    "PKT,sess1,cfg-A,0,4,400,-84,0,1,0,0,868000000,FLRC,0,0,1,10,64,0,0,0,0,0,0",
    "PKT,sess1,cfg-A,0,5,500,-85,0,1,0,0,868000000,FLRC,0,0,1,10,64,0,0,0,0,0,0",
    # seq 7 (gap: 6 missing), CRC FAIL, RSSI -90
    "PKT,sess1,cfg-A,0,7,600,-90,0,0,0,0,868000000,FLRC,0,0,1,10,64,0,0,0,0,0,0",
    # seq 7 again (duplicate)
    "PKT,sess1,cfg-A,0,7,600,-90,0,0,0,0,868000000,FLRC,0,0,1,10,64,0,0,0,0,0,0",
    # seq 8, CRC OK, LoRa with SNR
    "PKT,sess1,cfg-A,0,8,700,-75,12,1,0,0,868000000,LORA,7,125,5,10,64,0,0,0,0,0,0",
    # Different config_id
    "PKT,sess1,cfg-B,0,1,100,-70,0,1,0,0,868000000,FLRC,0,0,1,10,64,0,0,0,0,0,0",
    "PKT,sess1,cfg-B,0,2,200,-72,0,1,0,0,868000000,FLRC,0,0,1,10,64,0,0,0,0,0,0",
]


def make_sample_packets():
    """Parse SAMPLE_PKT_LINES into dicts for testing."""
    return [p for p in (parse_pkt_line(l) for l in SAMPLE_PKT_LINES) if p is not None]


# ── Tests: Field count validation ──────────────────────────────────────────

class TestFieldCountValidation:
    def test_valid_23_field_line(self):
        """A line with exactly 23 fields passes validation."""
        line = "PKT,sess,cfg,0,1,100,-80,0,1,0,0,868000000,FLRC,0,0,1,10,64,0,0,0,0,0,0"
        assert validate_field_count(line) is True

    def test_too_few_fields_rejected(self):
        """Lines with fewer than 23 fields are rejected."""
        line = "PKT,sess,cfg,0,1,100,-80"
        assert validate_field_count(line) is False

    def test_too_many_fields_rejected(self):
        """Lines with more than 23 fields are rejected."""
        line = "PKT,sess,cfg,0,1,100,-80,0,1,0,0,868000000,FLRC,0,0,1,10,64,0,0,0,0,0,0,extra"
        assert validate_field_count(line) is False

    def test_non_pkt_line_rejected(self):
        """Non-PKT lines are rejected."""
        assert validate_field_count("CONFIG_START,sess,cfg,0") is False
        assert validate_field_count("") is False
        assert validate_field_count("SOME_OTHER_LINE,1,2,3") is False

    def test_exact_23_boundary(self):
        """Exactly 23 fields is valid, 22 and 24 are not."""
        base = ",".join(str(i) for i in range(23))
        assert validate_field_count(f"PKT,{base}") is True

        too_few = ",".join(str(i) for i in range(22))
        assert validate_field_count(f"PKT,{too_few}") is False

        too_many = ",".join(str(i) for i in range(24))
        assert validate_field_count(f"PKT,{too_many}") is False


# ── Tests: RSSI statistics ─────────────────────────────────────────────────

class TestRSSIStats:
    def test_basic_stats(self):
        """compute_stats returns min/max/mean/std for RSSI values."""
        values = [-80, -82, -83, -84, -85]
        stats = compute_stats(values)
        assert stats["count"] == 5
        assert stats["min"] == -85
        assert stats["max"] == -80
        assert stats["mean"] == pytest.approx(-82.8, abs=0.01)
        assert stats["std"] > 0

    def test_single_value(self):
        """Single value has std=0."""
        stats = compute_stats([-80])
        assert stats["count"] == 1
        assert stats["min"] == -80
        assert stats["max"] == -80
        assert stats["mean"] == -80.0
        assert stats["std"] == 0.0

    def test_empty_list(self):
        """Empty list returns None for all stats."""
        stats = compute_stats([])
        assert stats["count"] == 0
        assert stats["min"] is None
        assert stats["max"] is None
        assert stats["mean"] is None
        assert stats["std"] is None

    def test_rssi_from_summary(self):
        """RSSI stats in summary match expected from sample packets."""
        packets = make_sample_packets()
        summary = compute_summary_stats(packets, [])
        rssi = summary["rssi"]
        # Sample has: -80, -82, -83, -84, -85, -90, -90, -75, -70, -72
        assert rssi["count"] == 10
        assert rssi["min"] == -90
        assert rssi["max"] == -70
        # Mean = (-80-82-83-84-85-90-90-75-70-72) / 10 = -811 / 10 = -81.1
        assert rssi["mean"] == pytest.approx(-81.1, abs=0.01)

    def test_std_dev_value(self):
        """Standard deviation is computed correctly."""
        values = [-80, -80, -80, -80]
        stats = compute_stats(values)
        assert stats["std"] == 0.0

        values2 = [-70, -90]
        stats2 = compute_stats(values2)
        # Sample std (n-1 denominator): sqrt(((-70+80)^2 + (-90+80)^2) / 1)
        # = sqrt(100 + 100) = sqrt(200) ≈ 14.14
        assert stats2["std"] == pytest.approx(14.14, abs=0.1)


# ── Tests: Seq continuity ───────────────────────────────────────────────────

class TestSeqContinuity:
    def test_perfect_sequence(self):
        """No gaps, no duplicates = monotonic."""
        seqs = [1, 2, 3, 4, 5]
        result = check_seq_continuity(seqs)
        assert result["total"] == 5
        assert result["gaps"] == []
        assert result["duplicates"] == 0
        assert result["monotonic"] is True
        assert result["min_seq"] == 1
        assert result["max_seq"] == 5
        assert result["expected_count"] == 5
        assert result["missing_count"] == 0

    def test_gap_detected(self):
        """Gaps in sequence are detected."""
        seqs = [1, 2, 4, 5]  # 3 is missing
        result = check_seq_continuity(seqs)
        assert len(result["gaps"]) == 1
        assert result["gaps"][0] == (2, 4)
        assert result["monotonic"] is False
        assert result["missing_count"] == 1

    def test_duplicate_detected(self):
        """Duplicate sequence numbers are detected."""
        seqs = [1, 2, 2, 3]
        result = check_seq_continuity(seqs)
        assert result["duplicates"] == 1
        assert result["monotonic"] is False

    def test_multiple_gaps(self):
        """Multiple gaps are all detected."""
        seqs = [1, 3, 5, 7]
        result = check_seq_continuity(seqs)
        assert len(result["gaps"]) == 3
        assert result["missing_count"] == 3  # 2,4,6 missing

    def test_empty_sequence(self):
        """Empty sequence returns safe defaults."""
        result = check_seq_continuity([])
        assert result["total"] == 0
        assert result["gaps"] == []
        assert result["duplicates"] == 0
        assert result["monotonic"] is True
        assert result["min_seq"] is None
        assert result["max_seq"] is None

    def test_single_value(self):
        """Single seq value: no gaps, no dups, monotonic."""
        result = check_seq_continuity([42])
        assert result["total"] == 1
        assert result["gaps"] == []
        assert result["duplicates"] == 0
        assert result["monotonic"] is True
        assert result["min_seq"] == 42
        assert result["max_seq"] == 42

    def test_out_of_order(self):
        """Out-of-order sequences are not monotonic."""
        seqs = [1, 3, 2, 4]
        result = check_seq_continuity(seqs)
        assert result["monotonic"] is False

    def test_from_sample_packets(self):
        """Seq continuity from the sample packets has gap and duplicates."""
        packets = make_sample_packets()
        seqs = [p["seq"] for p in packets]
        result = check_seq_continuity(seqs)
        # seqs: 1,2,3,4,5,7,7,8,1,2
        # Duplicates: seq 7 appears twice, seq 1 appears twice (cfg-A + cfg-B), seq 2 twice
        assert result["duplicates"] == 3  # seq 1, 2, 7 each have a duplicate
        assert len(result["gaps"]) >= 1  # gap at 5->7

    def test_large_seq_numbers(self):
        """uint32 sequence numbers work correctly."""
        seqs = [4294967290, 4294967291, 4294967292, 4294967293]
        result = check_seq_continuity(seqs)
        assert result["monotonic"] is True
        assert result["min_seq"] == 4294967290
        assert result["max_seq"] == 4294967293
        assert result["expected_count"] == 4
        assert result["missing_count"] == 0


# ── Tests: ts_ms monotonic check ───────────────────────────────────────────

class TestTsMonotonic:
    def test_monotonic_increasing(self):
        """Increasing timestamps are monotonic."""
        result = check_ts_monotonic([100, 200, 300, 400, 500])
        assert result["monotonic"] is True
        assert result["violations"] == 0

    def test_non_monotonic(self):
        """Decreasing timestamps are flagged."""
        result = check_ts_monotonic([100, 200, 150, 300])
        assert result["monotonic"] is False
        assert result["violations"] == 1

    def test_equal_values_ok(self):
        """Equal timestamps are OK (non-decreasing)."""
        result = check_ts_monotonic([100, 100, 200, 200])
        assert result["monotonic"] is True
        assert result["violations"] == 0

    def test_empty(self):
        """Empty list is trivially monotonic."""
        result = check_ts_monotonic([])
        assert result["monotonic"] is True
        assert result["violations"] == 0


# ── Tests: Summary statistics computation ──────────────────────────────────

class TestSummaryStats:
    def test_total_packets(self):
        """Total packet count matches."""
        packets = make_sample_packets()
        summary = compute_summary_stats(packets, [])
        assert summary["total_packets"] == len(packets)

    def test_crc_counts(self):
        """CRC OK and fail counts are correct."""
        packets = make_sample_packets()
        summary = compute_summary_stats(packets, [])
        # 8 CRC OK, 2 CRC fail (2 duplicate seq 7 lines)
        assert summary["crc"]["ok_count"] == 8
        assert summary["crc"]["fail_count"] == 2
        assert summary["crc"]["ok_pct"] == 80.0
        assert summary["crc"]["fail_pct"] == 20.0

    def test_bad_field_count(self):
        """Lines with wrong field count are tracked."""
        packets = make_sample_packets()
        bad_lines = [
            "PKT,too,few,fields",
            "PKT,also,bad",
        ]
        summary = compute_summary_stats(packets, bad_lines)
        assert summary["bad_field_count_lines"] == 2
        assert summary["field_count_ok"] is False
        assert summary["total_raw_lines"] == len(packets) + 2

    def test_field_count_ok_when_all_valid(self):
        """No bad field count lines = field_count_ok True."""
        packets = make_sample_packets()
        summary = compute_summary_stats(packets, [])
        assert summary["field_count_ok"] is True

    def test_config_ids(self):
        """Unique config_ids are detected."""
        packets = make_sample_packets()
        summary = compute_summary_stats(packets, [])
        assert summary["unique_config_count"] == 2
        assert "cfg-A" in summary["config_ids"]
        assert "cfg-B" in summary["config_ids"]

    def test_mod_types(self):
        """Modulation types are detected."""
        packets = make_sample_packets()
        summary = compute_summary_stats(packets, [])
        assert "FLRC" in summary["mod_types"]
        assert "LORA" in summary["mod_types"]

    def test_snr_stats_lora_only(self):
        """SNR stats only include non-zero values (LoRa)."""
        packets = make_sample_packets()
        summary = compute_summary_stats(packets, [])
        # Only the LoRa packet has snr_db=12, rest are 0 (FLRC)
        assert summary["snr"]["count"] == 1
        assert summary["snr"]["min"] == 12
        assert summary["snr"]["max"] == 12
        assert summary["snr"]["mean"] == 12.0

    def test_per_config_breakdown(self):
        """Per-config_id breakdown is computed when multiple configs exist."""
        packets = make_sample_packets()
        summary = compute_summary_stats(packets, [])
        assert "per_config_breakdown" in summary
        assert "cfg-A" in summary["per_config_breakdown"]
        assert "cfg-B" in summary["per_config_breakdown"]
        cfg_a = summary["per_config_breakdown"]["cfg-A"]
        assert cfg_a["total"] == 8  # 8 packets with cfg-A
        cfg_b = summary["per_config_breakdown"]["cfg-B"]
        assert cfg_b["total"] == 2  # 2 packets with cfg-B

    def test_no_per_config_when_single(self):
        """No per-config breakdown when only one config_id."""
        # All same config
        packets = [parse_pkt_line(l) for l in [
            "PKT,sess,cfg-X,0,1,100,-80,0,1,0,0,868000000,FLRC,0,0,1,10,64,0,0,0,0,0,0",
            "PKT,sess,cfg-X,0,2,200,-82,0,1,0,0,868000000,FLRC,0,0,1,10,64,0,0,0,0,0,0",
        ]]
        packets = [p for p in packets if p is not None]
        summary = compute_summary_stats(packets, [])
        assert summary["unique_config_count"] == 1
        assert summary["per_config_breakdown"] == {}

    def test_empty_packets(self):
        """Empty packet list produces zeroed summary."""
        summary = compute_summary_stats([], [])
        assert summary["total_packets"] == 0
        assert summary["crc"]["ok_count"] == 0
        assert summary["crc"]["fail_count"] == 0
        assert summary["crc"]["ok_pct"] == 0.0
        assert summary["rssi"]["count"] == 0
        assert summary["snr"]["count"] == 0
        assert summary["seq_continuity"]["total"] == 0
        assert summary["field_count_ok"] is True

    def test_prbs_summary_present(self):
        """Summary includes PRBS bit error statistics."""
        packets = [parse_pkt_line(l) for l in [
            "PKT,sess,cfg-A,0,1,100,-80,5,1,12,3,868000000,LORA,7,125,5,10,64,0,0,0,0,0,0",
            "PKT,sess,cfg-A,0,2,200,-82,6,1,0,0,868000000,LORA,7,125,5,10,64,0,0,0,0,0,0",
            "PKT,sess,cfg-A,0,3,300,-90,0,0,0,0,868000000,LORA,7,125,5,10,64,0,0,0,0,0,0",
            "PKT,sess,cfg-A,0,4,400,-75,8,1,45,10,868000000,LORA,7,125,5,10,64,0,0,0,0,0,0",
        ]]
        packets = [p for p in packets if p is not None]
        summary = compute_summary_stats(packets, [])
        assert "prbs" in summary
        prbs = summary["prbs"]
        assert prbs["total_bit_errors"] == 57  # 12 + 0 + 0 + 45
        assert prbs["total_bytes_bad"] == 13    # 3 + 0 + 0 + 10
        assert prbs["packets_with_errors"] == 2  # 2 packets have bit_err > 0
        assert prbs["packets_with_errors_pct"] == 50.0  # 2 out of 4

    def test_prbs_summary_empty(self):
        """Empty packet list has zeroed PRBS stats."""
        summary = compute_summary_stats([], [])
        assert "prbs" in summary
        assert summary["prbs"]["total_bit_errors"] == 0
        assert summary["prbs"]["total_bytes_bad"] == 0
        assert summary["prbs"]["packets_with_errors"] == 0

    def test_prbs_summary_crc_ok_only(self):
        """CRC-OK bit errors exclude CRC-failed packets."""
        packets = [parse_pkt_line(l) for l in [
            "PKT,sess,cfg-A,0,1,100,-80,5,1,12,3,868000000,LORA,7,125,5,10,64,0,0,0,0,0,0",
            "PKT,sess,cfg-A,0,2,200,-82,0,0,0,0,868000000,LORA,7,125,5,10,64,0,0,0,0,0,0",
        ]]
        packets = [p for p in packets if p is not None]
        summary = compute_summary_stats(packets, [])
        prbs = summary["prbs"]
        # Only the first packet has crc_ok=1 and bit_err=12
        assert prbs["crc_ok_bit_errors"] == 12
        assert prbs["crc_ok_bytes_bad"] == 3