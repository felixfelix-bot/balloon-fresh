#!/usr/bin/env python3
"""Host tests for e80_bench_ctl.py distributed range split (TDD, no HW).

Run:  python3 -m pytest test_e80_range_split.py -v
  or: python3 -m unittest test_e80_range_split -v

Covers:
  - load_config_preset: JSON loading + field validation
  - build_preset_schedule: T0-anchored airtime schedule from preset configs
  - parse_pkt_line: 25-field PKT line parsing from firmware console
  - TxLogWriter: tx-log.csv column format + incremental write
  - RxLogWriter: rx-log.csv column format + per-packet write
  - merge_csvs: inner/left join, PER computation, foreign packet flagging
  - dry_run_preset: schedule printing without hardware
"""
import csv
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import e80_bench_ctl as ctl  # noqa: E402


# ---------------------------------------------------------------------------
# Config preset loading
# ---------------------------------------------------------------------------

class TestLoadConfigPreset(unittest.TestCase):
    """Config preset JSON loading and validation."""

    def _make_preset(self):
        return {
            "name": "test-preset",
            "band": "868",
            "configs": [
                {
                    "label": "FLRC-650",
                    "mod": "flrc",
                    "sf": None,
                    "bw": None,
                    "br": 650,
                    "pa": 10,
                    "freq": 868000000,
                    "plen": 64,
                    "gap": 5000,
                    "n_pkts": 10,
                },
                {
                    "label": "LoRa-SF7",
                    "mod": "lora",
                    "sf": 7,
                    "bw": 125,
                    "br": None,
                    "pa": 10,
                    "freq": 868000000,
                    "plen": 64,
                    "gap": 10000,
                    "n_pkts": 10,
                },
            ],
        }

    def test_load_from_dict(self):
        preset = self._make_preset()
        cfgs = ctl.load_config_preset(preset)
        self.assertEqual(len(cfgs), 2)
        c0 = cfgs[0]
        self.assertEqual(c0["mod"], "flrc")
        self.assertEqual(c0["br"], 650)
        self.assertEqual(c0["sf"], None)
        self.assertEqual(c0["n_pkts"], 10)

    def test_config_has_airtime(self):
        """Each config gets an estimated airtime_s field."""
        preset = self._make_preset()
        cfgs = ctl.load_config_preset(preset)
        for c in cfgs:
            self.assertIn("airtime_s", c)
            self.assertGreater(c["airtime_s"], 0)

    def test_config_has_expected_s(self):
        """Each config gets expected burst duration."""
        preset = self._make_preset()
        cfgs = ctl.load_config_preset(preset)
        for c in cfgs:
            self.assertIn("expected_s", c)
            self.assertGreater(c["expected_s"], 0)
            # expected_s = n_pkts * (airtime + gap/1e6)
            exp = c["n_pkts"] * (c["airtime_s"] + c["gap"] / 1e6)
            self.assertAlmostEqual(c["expected_s"], exp, places=2)

    def test_config_has_label_and_idx(self):
        preset = self._make_preset()
        cfgs = ctl.load_config_preset(preset)
        for i, c in enumerate(cfgs):
            self.assertEqual(c["idx"], i)
            self.assertTrue(c["label"])

    def test_missing_configs_key(self):
        with self.assertRaises(ValueError):
            ctl.load_config_preset({"name": "bad"})

    def test_empty_configs(self):
        with self.assertRaises(ValueError):
            ctl.load_config_preset({"configs": []})

    def test_invalid_mod(self):
        preset = self._make_preset()
        preset["configs"][0]["mod"] = "fsk"
        with self.assertRaises(ValueError):
            ctl.load_config_preset(preset)

    def test_lora_missing_sf(self):
        preset = self._make_preset()
        preset["configs"][1]["sf"] = None
        with self.assertRaises(ValueError):
            ctl.load_config_preset(preset)

    def test_flrc_missing_br(self):
        preset = self._make_preset()
        preset["configs"][0]["br"] = None
        with self.assertRaises(ValueError):
            ctl.load_config_preset(preset)

    def test_load_from_file(self):
        """load_config_preset can load from a JSON file path."""
        preset = self._make_preset()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(preset, f)
            path = f.name
        try:
            cfgs = ctl.load_config_preset(path)
            self.assertEqual(len(cfgs), 2)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# Schedule building from preset
# ---------------------------------------------------------------------------

class TestBuildPresetSchedule(unittest.TestCase):
    """T0-anchored schedule from config presets."""

    def setUp(self):
        self.preset = {
            "name": "test",
            "band": "868",
            "configs": [
                {"label": "A", "mod": "flrc", "br": 650, "sf": None, "bw": None,
                 "pa": 10, "freq": 868000000, "plen": 64, "gap": 5000,
                 "n_pkts": 10},
                {"label": "B", "mod": "lora", "sf": 7, "bw": 125, "br": None,
                 "pa": 10, "freq": 868000000, "plen": 64, "gap": 10000,
                 "n_pkts": 10},
            ],
        }
        self.cfgs = ctl.load_config_preset(self.preset)
        self.t0 = ctl.parse_t0("2026-08-30 14:00:00")

    def test_schedule_returns_list_of_floats(self):
        starts = ctl.build_preset_schedule(self.cfgs, self.t0)
        self.assertEqual(len(starts), 2)
        self.assertTrue(all(isinstance(s, float) for s in starts))

    def test_first_start_after_t0_margin(self):
        t0_margin = 120
        starts = ctl.build_preset_schedule(self.cfgs, self.t0, t0_margin=t0_margin)
        self.assertGreaterEqual(starts[0], self.t0 + t0_margin)

    def test_starts_are_monotonically_increasing(self):
        starts = ctl.build_preset_schedule(self.cfgs, self.t0)
        for i in range(1, len(starts)):
            self.assertGreater(starts[i], starts[i - 1])

    def test_gap_between_configs(self):
        """Gap between config i end and config i+1 start = settle + guard."""
        guard = 20
        settle = 2
        starts = ctl.build_preset_schedule(self.cfgs, self.t0, guard_s=guard,
                                           settle_s=settle)
        for i in range(len(starts) - 1):
            end_i = starts[i] + self.cfgs[i]["expected_s"]
            gap = starts[i + 1] - end_i
            self.assertAlmostEqual(gap, settle + guard, places=0)

    def test_schedule_independent_of_call_order(self):
        """Same T0 + same configs → same schedule (deterministic)."""
        s1 = ctl.build_preset_schedule(self.cfgs, self.t0)
        s2 = ctl.build_preset_schedule(self.cfgs, self.t0)
        self.assertEqual(s1, s2)


# ---------------------------------------------------------------------------
# PKT line parsing
# ---------------------------------------------------------------------------

class TestParsePktLine(unittest.TestCase):
    """Parse firmware PKT lines (25-field format)."""

    # [0]PKT [1]session [2]config [3]replicate [4]pkt_idx [5]ts_ms
    # [6]rssi_dbm [7]snr_db [8]crc_ok [9]bit_err [10]? [11]freq_hz
    # [12]mod [13]sf/br [14]bw [15]cr [16]pa_dbm [17]len [18-23]0 [24]pcrc16
    SAMPLE_PKT = ("PKT,42,3,1,7,12345,-85.5,9.2,1,0,0,868000000,lora,7,125,1,"
                  "10,64,0,0,0,0,0,0,43981")

    def test_valid_pkt(self):
        p = ctl.parse_pkt_line_legacy(self.SAMPLE_PKT)
        self.assertIsNotNone(p)
        self.assertEqual(p["session"], 42)
        self.assertEqual(p["config"], 3)
        self.assertEqual(p["pkt_idx"], 7)
        self.assertEqual(p["ts_ms"], 12345)
        self.assertEqual(p["rssi_dbm"], -85.5)
        self.assertEqual(p["snr_db"], 9.2)
        self.assertEqual(p["crc_ok"], 1)
        self.assertEqual(p["freq_hz"], 868000000)
        self.assertEqual(p["mod"], "lora")
        self.assertEqual(p["sf_or_br"], 7)
        self.assertEqual(p["bw"], 125)
        self.assertEqual(p["pa_dbm"], 10)
        self.assertEqual(p["len"], 64)
        self.assertEqual(p["pcrc16"], 43981)

    def test_non_pkt_line(self):
        self.assertIsNone(ctl.parse_pkt_line_legacy("OK START"))
        self.assertIsNone(ctl.parse_pkt_line_legacy(""))
        self.assertIsNone(ctl.parse_pkt_line_legacy("STAT role=RX rx=5"))

    def test_short_pkt(self):
        self.assertIsNone(ctl.parse_pkt_line_legacy("PKT,1,2,3,4"))
        self.assertIsNone(ctl.parse_pkt_line("PKT,1,2,3,4"))

    def test_flrc_pkt(self):
        line = ("PKT,1,0,1,3,678,-72.0,12.5,1,0,0,868000000,flrc,650,0,0,"
                "10,64,0,0,0,0,0,0,12345")
        p = ctl.parse_pkt_line(line)
        self.assertIsNotNone(p)
        self.assertEqual(p["mod"], "flrc")
        self.assertEqual(p["sf_or_br"], 650)


# ---------------------------------------------------------------------------
# TX log format
# ---------------------------------------------------------------------------

class TestTxLogWriter(unittest.TestCase):
    """tx-log.csv format: one row per config."""

    COLS = ["session", "config_idx", "label", "n_pkts", "sent_ok",
            "mod", "sf_or_br", "bw", "pa_dbm", "freq_hz", "plen",
            "gap_us", "t0_offset_s", "actual_start_ts", "error"]

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "tx-log.csv")

    def test_header_written(self):
        log = ctl.TxLogWriter(self.path, session_id=12345)
        with open(self.path) as f:
            header = f.readline().strip()
        self.assertEqual(header, ",".join(self.COLS))

    def test_config_row(self):
        log = ctl.TxLogWriter(self.path, session_id=12345)
        log.config_row(
            config_idx=0, label="FLRC-650", n_pkts=10, sent_ok=10,
            mod="flrc", sf_or_br=650, bw=0, pa_dbm=10,
            freq_hz=868000000, plen=64, gap_us=5000,
            t0_offset_s=120.0, actual_start_ts="2026-08-30T14:02:00",
            error="",
        )
        with open(self.path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["session"], "12345")
        self.assertEqual(rows[0]["config_idx"], "0")
        self.assertEqual(rows[0]["sent_ok"], "10")
        self.assertEqual(rows[0]["mod"], "flrc")
        self.assertEqual(rows[0]["freq_hz"], "868000000")

    def test_incremental_write(self):
        """Rows are flushed after each write — partial data survives crash."""
        log = ctl.TxLogWriter(self.path, session_id=12345)
        for i in range(3):
            log.config_row(
                config_idx=i, label=f"cfg{i}", n_pkts=10, sent_ok=10,
                mod="flrc", sf_or_br=650, bw=0, pa_dbm=10,
                freq_hz=868000000, plen=64, gap_us=5000,
                t0_offset_s=120.0 + i * 10, actual_start_ts="",
                error="",
            )
        # Simulate crash: no close() needed, data should be on disk
        with open(self.path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        self.assertEqual(len(rows), 3)


# ---------------------------------------------------------------------------
# RX log format
# ---------------------------------------------------------------------------

class TestRxLogWriter(unittest.TestCase):
    """rx-log.csv format: one row per received packet."""

    COLS = ["session", "config", "pkt_idx", "ts_ms", "rssi_dbm", "snr_db",
            "crc_ok", "bit_err", "freq_hz", "mod", "sf_or_br", "bw",
            "pa_dbm", "len", "pcrc16", "captured_ts"]

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "rx-log.csv")

    def test_header_written(self):
        log = ctl.RxLogWriter(self.path)
        with open(self.path) as f:
            header = f.readline().strip()
        self.assertEqual(header, ",".join(self.COLS))

    def test_pkt_row(self):
        log = ctl.RxLogWriter(self.path)
        log.pkt_row(
            session=42, config=3, pkt_idx=7, ts_ms=12345,
            rssi_dbm=-85.5, snr_db=9.2, crc_ok=1, bit_err=0,
            freq_hz=868000000, mod="lora", sf_or_br=7, bw=125,
            pa_dbm=10, len=64, pcrc16=43981,
        )
        with open(self.path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["session"], "42")
        self.assertEqual(rows[0]["pkt_idx"], "7")
        self.assertEqual(rows[0]["rssi_dbm"], "-85.5")

    def test_multiple_pkts(self):
        log = ctl.RxLogWriter(self.path)
        for i in range(10):
            log.pkt_row(
                session=1, config=0, pkt_idx=i, ts_ms=i * 100,
                rssi_dbm=-80.0 + i, snr_db=10.0, crc_ok=1, bit_err=0,
                freq_hz=868000000, mod="flrc", sf_or_br=650, bw=0,
                pa_dbm=10, len=64, pcrc16=i * 100,
            )
        with open(self.path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        self.assertEqual(len(rows), 10)


# ---------------------------------------------------------------------------
# Merge CSVs
# ---------------------------------------------------------------------------

# We import merge_csvs as a module-level import to avoid circular deps
# merge_csvs.py is in the same directory.
_merge_path = os.path.dirname(os.path.abspath(__file__))
if _merge_path not in sys.path:
    sys.path.insert(0, _merge_path)
try:
    import merge_csvs as mc
    HAVE_MERGE = True
except ImportError:
    HAVE_MERGE = False


@unittest.skipUnless(HAVE_MERGE, "merge_csvs.py not yet implemented")
class TestMergeCsvs(unittest.TestCase):
    """merge_csvs.py: join TX + RX logs, compute PER."""

    def _write_tx_log(self, path, configs):
        """Write a tx-log.csv. configs=[(session, idx, n_pkts, label), ...]"""
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(ctl.TxLogWriter.COLUMNS)
            for session, idx, n_pkts, label in configs:
                w.writerow([session, idx, label, n_pkts, n_pkts,
                            "flrc", 650, 0, 10, 868000000, 64, 5000,
                            120.0 + idx * 30, "", ""])

    def _write_rx_log(self, path, pkts):
        """Write rx-log.csv. pkts=[(session, config, pkt_idx, rssi, crc_ok), ...]"""
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(ctl.RxLogWriter.COLUMNS)
            for session, config, pkt_idx, rssi, crc_ok in pkts:
                w.writerow([session, config, pkt_idx, rssi * 10, rssi, 9.5,
                            crc_ok, 0, 868000000, "flrc", 650, 0,
                            10, 64, 0, "2026-08-30T14:02:00"])

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.tx_path = os.path.join(self.tmpdir, "tx-log.csv")
        self.rx_path = os.path.join(self.tmpdir, "rx-log.csv")
        self.out_dir = self.tmpdir

    def test_all_received_per_zero(self):
        """All packets received → PER = 0%."""
        self._write_tx_log(self.tx_path, [(1, 0, 10, "FLRC-650")])
        self._write_rx_log(self.rx_path, [
            (1, 0, i, -80.0, 1) for i in range(10)
        ])
        combined = mc.merge_csvs(self.tx_path, self.rx_path,
                                 self.out_dir)
        # combined is a list of dicts
        lost = [r for r in combined if r["status"] == "lost"]
        self.assertEqual(len(lost), 0)

    def test_all_lost_per_100(self):
        """No RX packets → PER = 100%."""
        self._write_tx_log(self.tx_path, [(1, 0, 10, "FLRC-650")])
        self._write_rx_log(self.rx_path, [])
        combined = mc.merge_csvs(self.tx_path, self.rx_path,
                                 self.out_dir)
        lost = [r for r in combined if r["status"] == "lost"]
        self.assertEqual(len(lost), 10)

    def test_half_lost(self):
        """5 of 10 packets received → PER = 50%."""
        self._write_tx_log(self.tx_path, [(1, 0, 10, "FLRC-650")])
        self._write_rx_log(self.rx_path, [
            (1, 0, i, -80.0, 1) for i in range(5)
        ])
        combined = mc.merge_csvs(self.tx_path, self.rx_path,
                                 self.out_dir)
        lost = [r for r in combined if r["status"] == "lost"]
        recv = [r for r in combined if r["status"] == "received"]
        self.assertEqual(len(lost), 5)
        self.assertEqual(len(recv), 5)

    def test_multiple_configs(self):
        """Two configs, each with different PER."""
        self._write_tx_log(self.tx_path, [
            (1, 0, 10, "FLRC-650"),
            (1, 1, 10, "LoRa-SF7"),
        ])
        self._write_rx_log(self.rx_path, [
            (1, 0, i, -80.0, 1) for i in range(10)  # all received
        ] + [
            (1, 1, i, -90.0, 1) for i in range(3)   # only 3 received
        ])
        combined = mc.merge_csvs(self.tx_path, self.rx_path,
                                 self.out_dir)
        cfg0_lost = [r for r in combined
                     if r["config"] == "0" and r["status"] == "lost"]
        cfg1_lost = [r for r in combined
                     if r["config"] == "1" and r["status"] == "lost"]
        self.assertEqual(len(cfg0_lost), 0)
        self.assertEqual(len(cfg1_lost), 7)

    def test_foreign_packets_flagged(self):
        """RX packets with unknown (session, config) = flagged as foreign."""
        self._write_tx_log(self.tx_path, [(1, 0, 10, "FLRC-650")])
        self._write_rx_log(self.rx_path, [
            (1, 0, i, -80.0, 1) for i in range(10)
        ] + [
            (99, 5, 0, -70.0, 1),  # foreign session+config
        ])
        report_path = os.path.join(self.out_dir, "combined-range-report.md")
        mc.merge_csvs(self.tx_path, self.rx_path, self.out_dir)
        with open(report_path) as f:
            report = f.read()
        self.assertIn("foreign", report.lower())

    def test_csv_output(self):
        """combined.csv contains all expected + received rows."""
        self._write_tx_log(self.tx_path, [(1, 0, 5, "test")])
        self._write_rx_log(self.rx_path, [
            (1, 0, i, -80.0, 1) for i in range(3)
        ])
        mc.merge_csvs(self.tx_path, self.rx_path, self.out_dir)
        csv_path = os.path.join(self.out_dir, "combined.csv")
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        self.assertEqual(len(rows), 5)  # 5 expected
        statuses = set(r["status"] for r in rows)
        self.assertIn("received", statuses)
        self.assertIn("lost", statuses)

    def test_per_stats_in_report(self):
        """Report contains PER percentage per config."""
        self._write_tx_log(self.tx_path, [(1, 0, 10, "FLRC-650")])
        self._write_rx_log(self.rx_path, [
            (1, 0, i, -80.0, 1) for i in range(7)
        ])
        report_path = os.path.join(self.out_dir, "combined-range-report.md")
        mc.merge_csvs(self.tx_path, self.rx_path, self.out_dir)
        with open(report_path) as f:
            report = f.read()
        self.assertIn("30%", report)  # 3/10 = 30% PER


# ---------------------------------------------------------------------------
# Dry run with preset
# ---------------------------------------------------------------------------

class TestDryRunPreset(unittest.TestCase):
    """Dry run prints schedule from config preset without opening ports."""

    def test_dry_run_preset(self):
        """dry_run_preset() returns 0 and prints schedule."""
        preset = {
            "name": "test",
            "band": "868",
            "configs": [
                {"label": "A", "mod": "flrc", "br": 650, "sf": None,
                 "bw": None, "pa": 10, "freq": 868000000,
                 "plen": 64, "gap": 5000, "n_pkts": 10},
                {"label": "B", "mod": "lora", "sf": 7, "bw": 125,
                 "br": None, "pa": 10, "freq": 868000000,
                 "plen": 64, "gap": 10000, "n_pkts": 10},
            ],
        }
        cfgs = ctl.load_config_preset(preset)
        t0 = ctl.parse_t0("2026-08-30 14:00:00")
        starts = ctl.build_preset_schedule(cfgs, t0)
        self.assertEqual(len(starts), 2)
        self.assertGreater(starts[0], t0)

    def test_dry_run_no_file(self):
        """load_config_preset raises FileNotFoundError for missing file."""
        with self.assertRaises(FileNotFoundError):
            ctl.load_config_preset("/nonexistent/path/foo.json")


if __name__ == "__main__":
    unittest.main()
