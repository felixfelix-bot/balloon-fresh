#!/usr/bin/env python3
"""TDD tests for --prime-discard N feature in e80_bench_ctl.py.

Tests the three pure helper functions that implement the prime-discard
warmup-packet logic before the implementation is written.

Run:  python3 -m pytest test_prime_discard.py -v
"""
import argparse
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import e80_bench_ctl as m  # noqa: E402


# --------------------------------------------------------------------------- #
# Pure helpers: compute_tx_total, discard_prime_pkts, adjust_stat_for_prime
# --------------------------------------------------------------------------- #

class TestComputeTxTotal(unittest.TestCase):
    """compute_tx_total(n_pkts, prime_discard) → the N value for the
    firmware START command (TX sends n_pkts + prime_discard total)."""

    def test_adds_prime(self):
        self.assertEqual(m.compute_tx_total(100, 2), 102)

    def test_zero_prime(self):
        self.assertEqual(m.compute_tx_total(100, 0), 100)

    def test_default_prime(self):
        self.assertEqual(m.compute_tx_total(1000, 2), 1002)

    def test_large_prime(self):
        self.assertEqual(m.compute_tx_total(10, 5), 15)


class TestDiscardPrimePkts(unittest.TestCase):
    """discard_prime_pkts(pkts, prime_discard) → removes the first
    prime_discard packets (by pkt_idx) from the parsed PKT list."""

    def _pkts(self, indices):
        return [{"pkt_idx": i, "rssi_dbm": -80.0 + i} for i in indices]

    def test_default_discards_two(self):
        pkts = self._pkts(range(5))
        result = m.discard_prime_pkts(pkts, 2)
        self.assertEqual(len(result), 3)
        self.assertEqual([p["pkt_idx"] for p in result], [2, 3, 4])

    def test_zero_prime_returns_all(self):
        pkts = self._pkts(range(5))
        result = m.discard_prime_pkts(pkts, 0)
        self.assertEqual(len(result), 5)

    def test_empty_list(self):
        self.assertEqual(m.discard_prime_pkts([], 2), [])

    def test_all_dropped(self):
        """More prime than packets → empty result."""
        pkts = self._pkts(range(3))
        result = m.discard_prime_pkts(pkts, 5)
        self.assertEqual(len(result), 0)

    def test_non_sequential_idx_with_losses(self):
        """Some prime packets were lost (TX sent 0..4, prime_discard=2,
        RX only received 1, 3, 4). Only pkt_idx < 2 should be discarded."""
        pkts = self._pkts([1, 3, 4])
        result = m.discard_prime_pkts(pkts, 2)
        self.assertEqual(len(result), 2)
        self.assertEqual([p["pkt_idx"] for p in result], [3, 4])

    def test_missing_pkt_idx_defaults_to_zero(self):
        """If pkt_idx key is missing, treat it as 0 → eligible fordiscard."""
        pkts = [{"pkt_idx": 0}, {"rssi_dbm": -70}, {"pkt_idx": 5}]
        result = m.discard_prime_pkts(pkts, 2)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["pkt_idx"], 5)

    def test_preserves_packet_data(self):
        """Non-pkt_idx fields of the measured packets are preserved."""
        pkts = [
            {"pkt_idx": 0, "rssi_dbm": -90.0, "snr_db": 5.0},
            {"pkt_idx": 1, "rssi_dbm": -85.0, "snr_db": 7.0},
            {"pkt_idx": 2, "rssi_dbm": -80.0, "snr_db": 10.0},
        ]
        result = m.discard_prime_pkts(pkts, 2)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["rssi_dbm"], -80.0)
        self.assertEqual(result[0]["snr_db"], 10.0)


class TestAdjustStatForPrime(unittest.TestCase):
    """adjust_stat_for_prime(stat, prime_discard) → subtracts
    prime_discard from stat['recv'] (clamped at 0) so PER is based on
    measured packets only."""

    def test_subtracts_prime(self):
        stat = {"recv": 102, "sent": 100, "per_pct": 0.0}
        m.adjust_stat_for_prime(stat, 2)
        self.assertEqual(stat["recv"], 100)

    def test_zero_prime_noop(self):
        stat = {"recv": 100}
        m.adjust_stat_for_prime(stat, 0)
        self.assertEqual(stat["recv"], 100)

    def test_no_recv_key(self):
        """Missing recv key → treated as 0, clamped to 0."""
        stat = {}
        m.adjust_stat_for_prime(stat, 2)
        self.assertEqual(stat.get("recv"), 0)

    def test_more_prime_than_recv(self):
        """recv < prime_discard → clamped to 0."""
        stat = {"recv": 1}
        m.adjust_stat_for_prime(stat, 5)
        self.assertEqual(stat["recv"], 0)

    def test_negative_recv_clamped(self):
        stat = {"recv": 0}
        m.adjust_stat_for_prime(stat, 2)
        self.assertEqual(stat["recv"], 0)


# --------------------------------------------------------------------------- #
# Integration: build_script uses prime-adjusted N in START command
# --------------------------------------------------------------------------- #

def make_args(**kw):
    """argparse.Namespace with prime_discard included."""
    base = dict(
        tx="/dev/ttyUSB3", rx="/dev/ttyUSB4", freq=915000000, n=1000,
        length=255, gap_us=5000, dbm=22, dry_run=False,
        matrix=["flrc650", "flrc2600", "sf7", "sf12"], anchor=True,
        csv=None, band_override=True, site="siteA", stop="S3", dist_m="200",
        repeat=2, gps_tx="52.01,4.04", gps_rx="52.02,4.01", h_tx="1.5",
        h_rx="1.5", ground="grass", weather="12C clear", t0=None,
        t0_margin=120, guard=20, rx_lead=10, settle=2, skip_fw_check=True,
        mode=None, configs=None, port=None, probe=None, session_id=None,
        tx_log="tx-log.csv", rx_log="rx-log.csv",
        skip_late_configs=False,
        prime_discard=2,
    )
    base.update(kw)
    return argparse.Namespace(**base)


class TestBuildScriptWithPrime(unittest.TestCase):
    """build_script() START commands reflect prime_discard."""

    def test_start_n_includes_prime(self):
        tx, rx = m.build_script(make_args(n=1000, prime_discard=2))
        # Both TX and RX START should use N=1002
        tx_start = [c for c in tx if c.startswith("START")]
        rx_start = [c for c in rx if c.startswith("START")]
        self.assertEqual(len(tx_start), 1)
        self.assertEqual(len(rx_start), 1)
        self.assertIn("N=1002", tx_start[0])
        self.assertIn("N=1002", rx_start[0])

    def test_start_n_zero_prime(self):
        tx, rx = m.build_script(make_args(n=500, prime_discard=0))
        tx_start = [c for c in tx if c.startswith("START")]
        self.assertIn("N=500", tx_start[0])

    def test_start_n_custom_prime(self):
        tx, rx = m.build_script(make_args(n=100, prime_discard=5))
        tx_start = [c for c in tx if c.startswith("START")]
        self.assertIn("N=105", tx_start[0])


# --------------------------------------------------------------------------- #
# Integration: dry-run output shows prime-adjusted N
# --------------------------------------------------------------------------- #

class TestDryRunPrimeInOutput(unittest.TestCase):
    """Dry-run matrix output includes prime-adjusted START N."""

    def _main(self, argv):
        import contextlib
        import io
        old_argv = sys.argv
        sys.argv = ["e80_bench_ctl.py"] + argv
        buf, err = io.StringIO(), io.StringIO()
        code = 0
        try:
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
                m.main()
        except SystemExit as e:
            if isinstance(e.code, str):
                err.write(e.code + "\n")
                code = 1
            else:
                code = e.code or 0
        finally:
            sys.argv = old_argv
        return code, buf.getvalue() + err.getvalue()

    def test_dry_run_shows_prime_adjusted_n(self):
        with tempfile.TemporaryDirectory() as d:
            csv_path = os.path.join(d, "camp.csv")
            code, out = self._main([
                "--dry-run", "--matrix", "flrc650",
                "--csv", csv_path, "--site", "s", "--stop", "S1",
                "--dist-m", "10", "--repeat", "1",
                "--freq", "868000000", "--dbm", "10",
                "--t0", "2026-08-30 14:05:00",
                "--prime-discard", "2",
            ])
            self.assertEqual(code, 0)
            # N=10000, prime_discard=2 → START N=10002
            self.assertIn("N=10002", out)

    def test_dry_run_zero_prime(self):
        with tempfile.TemporaryDirectory() as d:
            csv_path = os.path.join(d, "camp.csv")
            code, out = self._main([
                "--dry-run", "--matrix", "flrc650",
                "--csv", csv_path, "--site", "s", "--stop", "S1",
                "--dist-m", "10", "--repeat", "1",
                "--freq", "868000000", "--dbm", "10",
                "--t0", "2026-08-30 14:05:00",
                "--prime-discard", "0",
            ])
            self.assertEqual(code, 0)
            self.assertIn("START N=10000", out)


# --------------------------------------------------------------------------- #
# Integration: RxLogWriter only gets measured packets after discard
# --------------------------------------------------------------------------- #

class TestRxLogPrimeDiscard(unittest.TestCase):
    """End-to-end: discard_prime_pkts → RxLogWriter only logs measured pkts."""

    def test_only_measured_pkts_logged(self):
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "rx-log.csv")
        log = m.RxLogWriter(path)

        # Simulated: TX sent 5 pkts (3 measured + 2 prime), all received
        raw_pkts = [
            {"session": 1, "config": 0, "pkt_idx": i, "ts_ms": i * 100,
             "rssi_dbm": -80.0 + i, "snr_db": 10.0, "crc_ok": 1, "bit_err": 0,
             "freq_hz": 868000000, "mod": "flrc", "sf_or_br": 650, "bw": 0,
             "pa_dbm": 10, "len": 64, "pcrc16": 0}
            for i in range(5)
        ]
        # Discard 2 prime
        measured = m.discard_prime_pkts(raw_pkts, 2)
        self.assertEqual(len(measured), 3)

        for p in measured:
            log.pkt_row(
                session=p["session"], config=p["config"],
                pkt_idx=p["pkt_idx"], ts_ms=p["ts_ms"],
                rssi_dbm=p["rssi_dbm"], snr_db=p["snr_db"],
                crc_ok=p["crc_ok"], bit_err=p["bit_err"],
                freq_hz=p["freq_hz"], mod=p["mod"],
                sf_or_br=p["sf_or_br"], bw=p["bw"],
                pa_dbm=p["pa_dbm"], len=p["len"], pcrc16=p["pcrc16"],
            )

        import csv
        with open(path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        self.assertEqual(len(rows), 3)
        self.assertEqual(int(rows[0]["pkt_idx"]), 2)  # first measured
        self.assertEqual(int(rows[2]["pkt_idx"]), 4)


if __name__ == "__main__":
    unittest.main()
