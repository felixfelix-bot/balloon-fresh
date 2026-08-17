#!/usr/bin/env python3
"""Host tests for range_bench_ctl.py — pure helpers: airtime, N-regime,
VirtualClock (HS-1a scope).

Run:  python3 -m pytest tools/test_range_bench_ctl.py -q
      python3 -m unittest tools.test_range_bench_ctl -v
"""
import argparse
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import range_bench_ctl as m  # noqa: E402


def make_args(**kw):
    """argparse.Namespace with every field the tool touches."""
    base = dict(
        tx_port=None, rx_port=None, matrix=None, anchor=True,
        csv=None, t0=None, dry_run=False, rx_lead=10,
        i_trust_clock=False,
        freq=868000000, dbm=10, n=1000, length=255, gap_us=5000,
        site="?", stop="?", dist_m="?", repeat=1,
    )
    base.update(kw)
    return argparse.Namespace(**base)


class VirtualClockTests(unittest.TestCase):
    """VirtualClock — deterministic time source for schedule tests."""

    def test_initial_now(self):
        clk = m.VirtualClock(1700000000.0)
        self.assertEqual(clk.now(), 1700000000.0)

    def test_sleep_advances_time(self):
        clk = m.VirtualClock(100.0)
        clk.sleep(5.0)
        self.assertAlmostEqual(clk.now(), 105.0)

    def test_sleep_zero(self):
        clk = m.VirtualClock(42.0)
        clk.sleep(0.0)
        self.assertEqual(clk.now(), 42.0)

    def test_multiple_sleeps_accumulate(self):
        clk = m.VirtualClock(0.0)
        clk.sleep(1.5)
        clk.sleep(2.5)
        self.assertAlmostEqual(clk.now(), 4.0)


class AirtimeTests(unittest.TestCase):
    """Airtime estimates for FLRC and LoRa modulations (plan §3 table)."""

    def test_flrc650_51b_plan_range(self):
        # plan §3: ~0.7 ms for 51 B at FLRC-650
        t = m.airtime_s("flrc650", 51)
        self.assertTrue(0.0006 <= t <= 0.0010, "got {:.6f}".format(t))

    def test_flrc2600_51b_plan_range(self):
        # plan §3: ~0.2 ms for 51 B at FLRC-2600
        t = m.airtime_s("flrc2600", 51)
        self.assertTrue(0.00015 <= t <= 0.0004, "got {:.6f}".format(t))

    def test_sf7_51b_plan_range(self):
        # plan §3: ~0.1 s for 51 B at SF7/BW125k
        t = m.airtime_s("sf7", 51)
        self.assertTrue(0.090 <= t <= 0.120, "got {:.6f}".format(t))

    def test_sf12_51b_plan_range(self):
        # plan §3: ~2.5 s for 51 B at SF12/BW125k
        t = m.airtime_s("sf12", 51)
        self.assertTrue(2.2 <= t <= 2.8, "got {:.6f}".format(t))

    def test_anchor_255b_flrc650(self):
        t = m.airtime_s("flrc650", 255)
        self.assertTrue(0.0029 <= t <= 0.0036, "got {:.6f}".format(t))

    def test_flrc_airtime_scales_with_length(self):
        t51 = m.airtime_s("flrc650", 51)
        t255 = m.airtime_s("flrc650", 255)
        self.assertTrue(t255 > t51)

    def test_lora_sf12_longer_than_sf7(self):
        self.assertTrue(m.airtime_s("sf12", 51) > m.airtime_s("sf7", 51))

    def test_unknown_mod_raises(self):
        with self.assertRaises(ValueError):
            m.airtime_s("fsk", 51)


class NRegimeTests(unittest.TestCase):
    """N-regime rule: 10^4 if prev ci_hi <= 2%, else 10^3. SF12 capped at 10^3."""

    def test_no_prior_rows_is_s0_rule(self):
        self.assertEqual(m.n_for_mod("flrc650", []), 10000)

    def test_ci_hi_le_2pct_gives_1e4(self):
        rows = [dict(mod="flrc650", len="51", per_ci_hi="1.500000")]
        self.assertEqual(m.n_for_mod("flrc650", rows), 10000)

    def test_ci_hi_gt_2pct_gives_1e3(self):
        rows = [dict(mod="flrc650", len="51", per_ci_hi="5.000000")]
        self.assertEqual(m.n_for_mod("flrc650", rows), 1000)

    def test_sf12_capped_always(self):
        rows = [dict(mod="sf12", len="51", per_ci_hi="0.100000")]
        self.assertEqual(m.n_for_mod("sf12", rows), 1000)
        self.assertEqual(m.n_for_mod("sf12", []), 1000)

    def test_anchor_len255_rows_ignored(self):
        rows = [dict(mod="flrc650", len="255", per_ci_hi="0.100000"),
                dict(mod="flrc650", len="51", per_ci_hi="9.000000")]
        self.assertEqual(m.n_for_mod("flrc650", rows), 1000)

    def test_latest_row_wins(self):
        rows = [dict(mod="sf7", len="51", per_ci_hi="9.000000"),
                dict(mod="sf7", len="51", per_ci_hi="0.500000")]
        self.assertEqual(m.n_for_mod("sf7", rows), 10000)

    def test_other_mods_do_not_leak(self):
        rows = [dict(mod="flrc2600", len="51", per_ci_hi="0.100000")]
        self.assertEqual(m.n_for_mod("sf7", rows), 10000)

    def test_nan_ci_hi_treated_as_no_prior(self):
        rows = [dict(mod="flrc650", len="51", per_ci_hi="")]
        self.assertEqual(m.n_for_mod("flrc650", rows), 10000)


if __name__ == "__main__":
    unittest.main()