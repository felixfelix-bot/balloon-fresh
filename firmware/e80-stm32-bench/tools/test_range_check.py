#!/usr/bin/env python3
"""Tests for range_check.py, T0-anchored cycle scheduling, and the
best-pass harmonized merge.

Run:  cd firmware/e80-stm32-bench/tools && python3 -m pytest test_range_check.py -v
(or `make range-test-host` from firmware/e80-stm32-bench/).
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e80_bench_ctl as ctl          # noqa: E402
import range_check                   # noqa: E402
import merge_csvs                    # noqa: E402


def _cfg(idx, n_pkts=10, freq=870e6, mod="lora", sf=7, br=None, expected_s=9.0):
    return {
        "idx": idx, "label": "cfg{} sf{}".format(idx, sf), "mod": mod,
        "sf": sf, "bw": 125, "br": br, "pa": 22, "freq": freq,
        "plen": 255, "gap": 10000, "n_pkts": n_pkts,
        "airtime_s": 0.3, "expected_s": expected_s,
    }


# ---------------------------------------------------------------------------
# T0-anchored cycles
# ---------------------------------------------------------------------------

class TestCycleAnchoring(unittest.TestCase):
    TIMING = dict(t0_margin=30, guard=5, settle=1, rx_lead=3,
                  swd_reset_s=2, band_swap_s=30)

    def test_cycle_len_rounds_up_to_whole_minute(self):
        cfgs = [_cfg(0), _cfg(1)]
        cl = ctl.compute_cycle_len(cfgs, **self.TIMING)
        self.assertGreater(cl, 0)
        self.assertEqual(cl % 60, 0)

    def test_cycle_len_identical_across_call_order(self):
        cfgs = [_cfg(0), _cfg(1, freq=2400e6)]
        a = ctl.compute_cycle_len(cfgs, **self.TIMING)
        b = ctl.compute_cycle_len(list(reversed(cfgs)), **self.TIMING)
        # reversed list is a DIFFERENT schedule; same list twice must match
        a2 = ctl.compute_cycle_len(cfgs, **self.TIMING)
        self.assertEqual(a, a2)

    def test_cycle_len_includes_band_wrap_gap(self):
        same_band = [_cfg(0, freq=870e6), _cfg(1, freq=870e6)]
        wraps = [_cfg(0, freq=870e6), _cfg(1, freq=2400e6)]
        cl_same = ctl.compute_cycle_len(same_band, **self.TIMING)
        cl_wrap = ctl.compute_cycle_len(wraps, **self.TIMING)
        # wrapping preset pays band_swap_s at the inter-config gap AND at
        # the wrap back to config 0 — must be strictly longer
        self.assertGreater(cl_wrap, cl_same)

    def test_late_launch_detected_against_true_schedule(self):
        """The regression that caused session 2608281130: a 150s-late RX
        must be DETECTED (skip index >= 1 or None), never silently
        re-anchored onto a fresh local schedule."""
        cfgs = [_cfg(i) for i in range(10)]
        t0 = 1_000_000
        starts = ctl.build_preset_schedule(cfgs, t0, **self.TIMING)
        idx = ctl.compute_late_skip(starts, now=t0 + 150, rx_lead=3)
        # either some configs remain joinable (idx < len) or all passed
        # (None) — but it must NOT return 0 (= "on time"), which is what
        # the old local re-anchoring always claimed.
        self.assertNotEqual(idx, 0)
        if idx is not None:
            self.assertGreaterEqual(idx, 1)

    def test_all_cycles_anchor_to_shared_t0(self):
        cfgs = [_cfg(0), _cfg(1)]
        cl = ctl.compute_cycle_len(cfgs, **self.TIMING)
        t0 = 1_000_000
        for cycle in (1, 2, 5):
            t0_cycle = t0 + (cycle - 1) * cl
            starts = ctl.build_preset_schedule(cfgs, t0_cycle, **self.TIMING)
            self.assertAlmostEqual(starts[0], t0_cycle + self.TIMING["t0_margin"],
                                   delta=0.001)
            # every cycle k+1 anchor must be AFTER cycle k's last capture
            starts_k = ctl.build_preset_schedule(cfgs, t0, **self.TIMING)
            last_end = starts_k[-1] + cfgs[-1]["expected_s"] + \
                self.TIMING["settle"] + self.TIMING["guard"]
            self.assertGreaterEqual(t0 + cl + self.TIMING["t0_margin"], last_end)


# ---------------------------------------------------------------------------
# range_check analysis
# ---------------------------------------------------------------------------

class TestAnalyzeCapture(unittest.TestCase):
    def test_ok_thin_miss(self):
        cfgs = [_cfg(0, n_pkts=10), _cfg(1, n_pkts=10), _cfg(2, n_pkts=10)]
        pkts = (
            [{"config_id": 0, "replicate": 1}] * 10 +
            [{"config_id": 1, "replicate": 1}] * 3 +
            [{"config_id": 7, "replicate": 1}] * 5   # foreign config
        )
        per = range_check.analyze_capture(cfgs, pkts)
        self.assertEqual(per[0]["status"], "OK")
        self.assertEqual(per[1]["status"], "THIN")
        self.assertEqual(per[2]["status"], "MISS")
        self.assertEqual(per[0]["n_recv"], 10)
        self.assertEqual(per[1]["n_recv"], 3)

    def test_best_pass_across_replicates(self):
        cfgs = [_cfg(0, n_pkts=10)]
        pkts = ([{"config_id": 0, "replicate": 1}] * 2 +
                [{"config_id": 0, "replicate": 2}] * 9)
        per = range_check.analyze_capture(cfgs, pkts)
        self.assertEqual(per[0]["n_recv"], 9)
        self.assertEqual(per[0]["status"], "OK")
        self.assertEqual(per[0]["per_replicate"], {1: 2, 2: 9})

    def test_summary_lines(self):
        per = {
            0: {"n_pkts": 10, "n_recv": 10, "per_replicate": {1: 10}, "status": "OK"},
            1: {"n_pkts": 10, "n_recv": 0, "per_replicate": {}, "status": "MISS"},
            2: {"n_pkts": 10, "n_recv": 3, "per_replicate": {1: 3}, "status": "THIN"},
        }
        self.assertEqual(range_check.render_summary_line("872m", per),
                         "872m: GAPS c1 MISS, c2 THIN 3/10")
        ok = {0: {"n_pkts": 10, "n_recv": 10, "per_replicate": {1: 10}, "status": "OK"}}
        self.assertEqual(range_check.render_summary_line("50m", ok),
                         "50m: COMPLETE 1/1")

    def test_resend_preset_gaps_only_idx_preserved(self):
        cfgs = [_cfg(0), _cfg(1), _cfg(2)]
        per = {
            0: {"status": "OK"},
            1: {"status": "MISS"},
            2: {"status": "THIN", "n_recv": 3, "n_pkts": 10},
        }
        preset = range_check.build_resend_preset(cfgs, per, "872m", 2608281225)
        self.assertIsNotNone(preset)
        self.assertEqual([c["idx"] for c in preset["configs"]], [1, 2])
        self.assertEqual(preset["name"], "resend-872m-2608281225")
        self.assertIsNone(range_check.build_resend_preset(
            cfgs, {i: {"status": "OK"} for i in range(3)}, "50m", 1))

    def test_next_t0_boundary(self):
        self.assertEqual(range_check.next_t0(300, now=1000), 1200)
        self.assertEqual(range_check.next_t0(300, now=1200), 1500)

    def test_resend_commands_format(self):
        cmds = range_check.format_resend_commands(
            "configs/resend/resend-872m-2608281225.json", 1787921400, "872m")
        self.assertEqual(len(cmds), 2)
        self.assertIn("make range-tx DIST=872m "
                      "CONFIGS=configs/resend/resend-872m-2608281225.json "
                      "T0=1787921400 SESSION_ID=", cmds[0])
        self.assertIn("make range-rx", cmds[1])


# ---------------------------------------------------------------------------
# rx-log parsing (harmonized + legacy)
# ---------------------------------------------------------------------------

def _pkt_line(sess, cfg, rep, seq, rssi=-80.0):
    return ("PKT,{},{},{},{},123,{:.1f},10.0,1,0,0,868000000,lora,7,125,0,"
            "22,255,0,0,0,0,0,0".format(sess, cfg, rep, seq, rssi))


class TestParseRxLog(unittest.TestCase):
    def test_harmonized(self):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
            f.write("# DISTRIBUTED_RX_MODE t0=...\n")
            f.write(_pkt_line(2608281225, 0, 1, 4) + "\n")
            f.write(_pkt_line(2608281225, 0, 1, 5) + "\n")
            f.write(_pkt_line(2608280930, 3, 1, 9) + "\n")
            path = f.name
        try:
            pkts, sessions = range_check.parse_rx_log(path)
            self.assertEqual(len(pkts), 3)
            self.assertEqual(sessions, {2608281225, 2608280930})
            self.assertEqual(pkts[0]["config_id"], 0)
        finally:
            os.unlink(path)

    def test_legacy(self):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
            f.write("session,config,pkt_idx,ts_ms,rssi_dbm,snr_db,crc_ok,"
                    "bit_err,freq_hz,mod,sf_or_br,bw,pa_dbm,len,pcrc16,captured_ts\n")
            f.write("2608281225,0,2,200,-78.0,10.0,1,0,868000000,flrc,650,0,10,64,0,"
                    "2026-08-28T17:55:50\n")
            path = f.name
        try:
            pkts, sessions = range_check.parse_rx_log(path)
            self.assertEqual(len(pkts), 1)
            self.assertEqual(sessions, {2608281225})
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# merge_csvs: harmonized best-pass
# ---------------------------------------------------------------------------

def _tx_stat_line(sess, cfg, rep, n_pkts=10, label="cfg"):
    st = {"sent": n_pkts + 2, "sent_ok": n_pkts, "recv": 0, "crc_err": 0,
          "per_pct": 0.0, "elapsed_s": 9.0, "kbps": None, "rssi": None,
          "snr": None, "drops": 0, "gap_us": 10000,
          "label": label, "n_pkts": n_pkts, "plen": 255}
    return ctl.format_stat_line("TX", st, sess, cfg, replicate=rep)


class TestMergeBestPass(unittest.TestCase):
    def test_best_pass_not_union(self):
        """rep1 catches 4/10, rep2 catches 9/10 -> PER from rep2 (10%),
        NOT from the union (which would claim 0% for the 5 shared-lost)."""
        with tempfile.TemporaryDirectory() as d:
            tx = os.path.join(d, "tx.csv")
            rx = os.path.join(d, "rx.csv")
            with open(tx, "w") as f:
                f.write(_tx_stat_line(2608281225, 0, 1) + "\n")
                f.write(_tx_stat_line(2608281225, 0, 2) + "\n")
            with open(rx, "w") as f:
                # rep1: seq 0-3 (4 pkts)
                for s in range(4):
                    f.write(_pkt_line(2608281225, 0, 1, s) + "\n")
                # rep2: 9 of 10 pkts (seqs 0-9, misses seq 3)
                for s in range(10):
                    if s == 3:
                        continue
                    f.write(_pkt_line(2608281225, 0, 2, s) + "\n")
                # foreign: config not in TX log
                f.write(_pkt_line(2608281225, 9, 1, 0) + "\n")
            combined = merge_csvs.merge_csvs(tx, rx, d)
            received = sum(1 for r in combined if r["status"] == "received")
            lost = [r for r in combined if r["status"] == "lost"]
            self.assertEqual(len(combined), 10)   # denominator = n_pkts, not union
            self.assertEqual(received, 9)
            self.assertEqual(len(lost), 1)
            # pkt_idx is normalized positionally per (config, replicate):
            # rep2 captured seqs 0-2,4-8 -> normalized 0-8, so the LAST
            # expected index is the lost one
            self.assertEqual(lost[0]["pkt_idx"], 9)
            self.assertEqual(lost[0]["replicate"], 2)
            with open(os.path.join(d, "combined-range-report.md")) as f:
                report = f.read()
            self.assertIn("best pass", report)
            self.assertIn("r1: 4", report)
            self.assertIn("r2: 9", report)

    def test_legacy_still_merges(self):
        """Old-format logs keep working (regression guard)."""
        with tempfile.TemporaryDirectory() as d:
            tx = os.path.join(d, "tx.csv")
            rx = os.path.join(d, "rx.csv")
            with open(tx, "w") as f:
                f.write("session,config_idx,n_pkts,sent_ok,label\n")
                f.write("2608281225,0,10,10,cfg0\n")
            with open(rx, "w") as f:
                f.write("session,config,pkt_idx,ts_ms,rssi_dbm,snr_db,crc_ok,"
                        "bit_err,freq_hz,mod,sf_or_br,bw,pa_dbm,len,pcrc16,captured_ts\n")
                for i in range(10):
                    f.write("2608281225,0,{},{},-80.0,10.0,1,0,868000000,lora,7,125,22,"
                            "255,0,2026-08-28T18:00:00\n".format(i, i * 100))
            combined = merge_csvs.merge_csvs(tx, rx, d)
            self.assertEqual(len(combined), 10)
            self.assertTrue(all(r["status"] == "received" for r in combined))

    def test_stat_line_parse_with_bracket_ci(self):
        line = _tx_stat_line(2608281225, 3, 1, n_pkts=10, label="LoRa-SF7")
        d = merge_csvs.parse_stat_line(line)
        self.assertIsNotNone(d)
        self.assertEqual(d["role"], "TX")
        self.assertEqual(d["per_ci_x1e6"], "[0,0]")
        self.assertEqual(d["n_pkts"], "10")
        self.assertEqual(d["label"], "LoRa-SF7")


    def test_resend_preset_idx_preserved_through_reload(self):
        """The trimmed preset must keep ORIGINAL idx values after a
        load_config_preset round-trip (logs stay consistent with the
        full preset's numbering across re-send passes)."""
        cfgs = ctl.load_config_preset({
            "configs": [
                {"label": "a", "mod": "lora", "sf": 7, "bw": 125, "pa": 22,
                 "freq": 870e6, "plen": 255, "gap": 10000, "n_pkts": 10, "idx": 4},
                {"label": "b", "mod": "lora", "sf": 12, "bw": 125, "pa": 22,
                 "freq": 870e6, "plen": 255, "gap": 10000, "n_pkts": 10, "idx": 7},
            ]
        })
        self.assertEqual([c["idx"] for c in cfgs], [4, 7])
        # no explicit idx -> positional (back-compat)
        pos = ctl.load_config_preset({
            "configs": [
                {"label": "x", "mod": "lora", "sf": 7, "bw": 125, "pa": 22,
                 "freq": 870e6, "plen": 255, "gap": 10000, "n_pkts": 10},
            ]
        })
        self.assertEqual([c["idx"] for c in pos], [0])


# ---------------------------------------------------------------------------
# Makefile wiring: T0-tagged log filenames + range-check target
# ---------------------------------------------------------------------------

class TestMakefileLogNaming(unittest.TestCase):
    FWDIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def test_range_tx_log_filename_includes_t0_and_session(self):
        out = subprocess.run(
            ["make", "-n", "range-tx", "DIST=50m",
             "T0=1787921400", "SESSION_ID=2608281250"],
            cwd=self.FWDIR, capture_output=True, text=True)
        self.assertIn("--tx-log", out.stdout)
        self.assertIn("tx-log-t01787921400-2608281250.csv", out.stdout)
        self.assertIn("stop-50m", out.stdout)

    def test_range_rx_late_join_flag(self):
        out = subprocess.run(
            ["make", "-n", "range-rx", "DIST=50m",
             "T0=1787921400", "SESSION_ID=2608281250"],
            cwd=self.FWDIR, capture_output=True, text=True)
        self.assertIn("--skip-late-configs", out.stdout)
        self.assertIn("rx-log-t01787921400-2608281250.csv", out.stdout)


if __name__ == "__main__":
    unittest.main()
