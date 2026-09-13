#!/usr/bin/env python3
"""Host tests for e80_bench_ctl.py — pure functions, CSV, gates, dry-run and a
FakeBoard-driven matrix run (no serial hardware; plan §5 offline surface).

Run:  python3 -m unittest test_e80_bench_ctl -v
"""
import argparse
import contextlib
import io
import json
import os
import re
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import e80_bench_ctl as m  # noqa: E402


def make_args(**kw):
    """argparse.Namespace with every field the tool touches."""
    base = dict(
        tx="/dev/ttyUSB3", rx="/dev/ttyUSB4", freq=915000000, n=1000,
        length=255, gap_us=5000, dbm=22, dry_run=False,
        matrix=["flrc650", "flrc2600", "sf7", "sf12"], anchor=True,
        csv=None, band_override=True, site="siteA", stop="S3", dist_m="200",
        repeat=2, gps_tx="52.01,4.04", gps_rx="52.02,4.01", h_tx="1.5",
        h_rx="1.5", ground="grass", weather="12C clear", t0=None,
        t0_margin=30, guard=20, rx_lead=10, settle=2, skip_fw_check=True,
        # Distributed / preset-mode fields
        mode=None, configs=None, port=None, probe=None, session_id=None,
        tx_log="tx-log.csv", rx_log="rx-log.csv",
        skip_late_configs=False,
        prime_discard=2,
        # Runner fields (existing tests never reached them; GO wiring does)
        swd_reset_s=2, band_swap_s=30,
        sync="boundary", armed_file=None, armed_out=None,
    )
    base.update(kw)
    return argparse.Namespace(**base)


class FakeBoard:
    """Stateful firmware stand-in: one shared world dict per (port) side."""

    def __init__(self, port, world):
        self.port = port
        self.world = world            # {'tx': {...}, 'rx': {...}}
        self.side = "tx" if "ttyUSB3" in port else "rx"
        self.log = []

    # console API used by the tool
    def drain(self):
        pass

    def close(self):
        self.log.append("CLOSE")

    def cmd(self, line, expect_ok=True, timeout=15.0):
        return self._reply(line, expect_ok)

    def query(self, line, prefixes=("OK", "ERR", "STAT", "ID"), timeout=15.0):
        return self._reply(line, True)

    def stat(self):
        return self._reply("STAT?", True)

    # firmware model
    def _reply(self, line, expect_ok):
        self.log.append(line)
        w = self.world[self.side]
        if line == "ID?":
            band = "OVERRIDE" if w.get("band_override") else "863-870MHz"
            pcap = "+22dBm(OUTDOOR)" if w.get("power_outdoor") else "+10dBm"
            role = {"tx": "TX", "rx": "RX"}[self.side]
            return ("ID E80BENCH v1.0 role={} armed=1 mod=flrc br=650000 "
                    "freq={} band={} pa=22 pcap={} chip=2.1 radio=awake"
                    .format(role, w["freq"], band, pcap))
        if line == "STAT?":
            n = w["n"]
            if self.side == "tx":
                return ("STAT role=TX sent={} sent_ok={} rx=0 crc_err=0 "
                        "per_x1e6=0 elapsed_s=42.0 kbps=64 rssi_avg_dbm=0.0 "
                        "snr_avg_db=0.0 drops=0".format(n, n))
            rx = w.get("rx_ok", n - 3)
            return ("STAT role=RX sent=0 sent_ok=0 rx={} crc_err=1 "
                    "per_x1e6=300 per_ci_x1e6=[100,900] elapsed_s=42.5 "
                    "kbps=63 rssi_avg_dbm=-87.5 snr_avg_db=9.8 drops=0"
                    .format(rx))
        if line.startswith("BAND OVERRIDE"):
            assert line == "BAND OVERRIDE 2026", line
            w["band_override"] = True
            return "OK BAND OVERRIDE PIN 2026 ACCEPTED"
        if line.startswith("POWER MODE OUTDOOR"):
            assert line == "POWER MODE OUTDOOR 2026", line
            w["power_outdoor"] = True
            return "OK POWER MODE OUTDOOR PIN 2026 ACCEPTED"
        if line.startswith("FREQ"):
            hz = int(line.split()[1])
            lo, hi = (410000000, 2483500000) if w.get("band_override") \
                else (863000000, 870000000)
            if not lo <= hz <= hi:
                reply = "ERR BAND (EU SRD 863-870MHZ ONLY)"
                if expect_ok:
                    raise RuntimeError("{} rejected '{}': {}".format(self.port, line, reply))
                return reply
            w["freq"] = hz
            return "OK FREQ {}".format(hz)
        if line == "ROLE TX":
            w["role"] = "tx"
            return "OK ROLE TX (TX INHIBITED - SEND 'ARM TX' TO ENABLE)"
        if line == "ROLE RX":
            w["role"] = "rx"
            return "OK ROLE RX (CONTINUOUS)"
        if line == "ROLE NONE":
            w["role"] = "none"
            return "OK ROLE NONE (RADIO ASLEEP)"
        if line == "ARM TX":
            return "OK ARMED (TX ENABLED)"
        if line.startswith("MOD"):
            return "OK MOD"
        if line.startswith("PA"):
            if not w.get("power_outdoor") and int(line.split()[1]) > 10:
                reply = "ERR RANGE (INDOOR CAP 0-10 DBM)"
                if expect_ok:
                    raise RuntimeError("{} rejected '{}': {}".format(self.port, line, reply))
                return reply
            return "OK PA {} DBM".format(line.split()[1])
        if line.startswith("START"):
            return "OK START"
        if line == "STOP":
            return "OK STOP (RADIO ASLEEP)"
        raise AssertionError("FakeBoard: unhandled line {!r}".format(line))


class VirtualClock:
    def __init__(self, t0):
        self.t = float(t0)

    def now(self):
        return self.t

    def sleep(self, d):
        self.t += max(0.0, d)


class AirtimeTests(unittest.TestCase):
    def test_plan_table_51b(self):
        # plan §3: 0.7 ms / 0.2 ms / 0.1 s / 2.5 s for 51 B
        self.assertTrue(0.0006 <= m.airtime_s("flrc650", 51) <= 0.0010)
        self.assertTrue(0.00015 <= m.airtime_s("flrc2600", 51) <= 0.0004)
        self.assertTrue(0.090 <= m.airtime_s("sf7", 51) <= 0.120)
        self.assertTrue(2.2 <= m.airtime_s("sf12", 51) <= 2.8)

    def test_anchor_255b_flrc650(self):
        self.assertTrue(0.0029 <= m.airtime_s("flrc650", 255) <= 0.0036)

    def test_unknown_mod_raises(self):
        with self.assertRaises(ValueError):
            m.airtime_s("fsk", 51)


class NRegimeTests(unittest.TestCase):
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
        self.assertEqual(m.n_for_mod("sf7", rows), 10000)  # no sf7 row -> S0 rule


class MatrixCellTests(unittest.TestCase):
    def test_default_matrix_plus_anchor(self):
        cells = m.build_matrix_cells(make_args(matrix=m.MATRIX_KEYS), [])
        self.assertEqual([c["key"] for c in cells],
                         ["flrc650", "flrc2600", "sf7", "sf12", "flrc650"])
        self.assertEqual([c["len_bytes"] for c in cells],
                         [51, 51, 51, 51, 255])
        self.assertEqual([c["gap_us"] for c in cells],
                         [5000, 5000, 1000, 1000, 5000])
        self.assertEqual([c["n"] for c in cells],
                         [10000, 10000, 10000, 1000, 10000])
        self.assertTrue(cells[-1]["anchor"])
        self.assertFalse(cells[0]["anchor"])

    def test_no_anchor(self):
        cells = m.build_matrix_cells(make_args(matrix=["sf7"], anchor=False), [])
        self.assertEqual(len(cells), 1)

    def test_explicit_length_respected(self):
        # single-shot CSV rows carry the actual payload length
        self.assertEqual(m.make_cell("flrc650", 1000, length=255)["len_bytes"], 255)
        self.assertEqual(m.make_cell("flrc650", 1000)["len_bytes"], 51)

    def test_edge_regime_from_prior_rows(self):
        rows = [dict(mod=k, len="51", per_ci_hi="5.0") for k in m.MATRIX_KEYS]
        cells = m.build_matrix_cells(make_args(), rows)
        self.assertEqual([c["n"] for c in cells],
                         [1000, 1000, 1000, 1000, 10000])


class ScheduleTests(unittest.TestCase):
    def test_monotonic_with_margin_and_guard(self):
        cells = m.build_matrix_cells(make_args(matrix=["flrc650", "sf7"]), [])
        t0 = m.parse_t0("2026-08-30 14:05:00")
        starts = m.build_stop_schedule(cells, t0, t0_margin_s=120, guard_s=20)
        self.assertEqual(starts[0], t0 + 120)
        self.assertTrue(all(b > a for a, b in zip(starts, starts[1:])))
        self.assertGreaterEqual(starts[1] - starts[0],
                                cells[0]["expected_s"] + 20)

    def test_parse_t0_formats(self):
        # Space-separator with seconds (primary documented format)
        self.assertEqual(m.parse_t0("2026-08-30 14:05:00"),
                         m.parse_t0("2026-08-30 14:05"))
        # Epoch integer (timezone-safe, used for distributed tests)
        epoch = m.parse_t0("2026-08-30 14:05:00")
        self.assertEqual(m.parse_t0(str(int(epoch))), epoch)
        with self.assertRaises(ValueError):
            m.parse_t0("tomorrow")


class LateSkipTests(unittest.TestCase):
    """Tests for compute_late_skip() + apply_late_skip() — the launch-lateness
    guard added per docs/timing-tolerance-analysis.md §6.

    These functions replace the previous silent-desync behaviour of
    wait_until() (which no-ops on past timestamps) with a clear abort by
    default, or an optional explicit recovery via --skip-late-configs.

    All tests use synthetic schedules so they're independent of wall-clock
    time (compute_late_skip is a pure function — no time.time()).
    """

    def _synthetic_schedule(self):
        """4-config preset schedule with starts at offsets
        120, 220, 320, 420 (relative to T0)."""
        t0 = 1000
        starts = [t0 + 120, t0 + 220, t0 + 320, t0 + 420]
        cfgs = [
            {"label": "cfg0"},
            {"label": "cfg1"},
            {"label": "cfg2"},
            {"label": "cfg3"},
        ]
        return t0, starts, cfgs

    # ---------- compute_late_skip pure function ----------

    def test_on_time_returns_zero(self):
        """Well-before-time launch → no skip needed (returns 0)."""
        t0, starts, _ = self._synthetic_schedule()
        self.assertEqual(
            m.compute_late_skip(starts, now=t0 + 10, rx_lead=0),
            0,
            "On-time launch must return index 0 (no skip needed)",
        )

    def test_late_launch_skips_past_starts(self):
        """Launched well past cfg 0 + cfg 1 → returns the next future index."""
        t0, starts, _ = self._synthetic_schedule()
        # now = T0+250: cfg 0 (1120) past, cfg 1 (1220) past, cfg 2 (1320)
        # future. min_ahead_s=5 → (1320 - 0) >= 1255? Yes → returns 2.
        self.assertEqual(
            m.compute_late_skip(starts, now=t0 + 250, rx_lead=0),
            2,
        )

    def test_all_past_returns_none(self):
        """When even the last config's arm point is in the past → None
        (operator must re-T0)."""
        t0, starts, _ = self._synthetic_schedule()
        self.assertIsNone(
            m.compute_late_skip(starts, now=t0 + 9999, rx_lead=0),
        )

    def test_rx_lead_subtraction(self):
        """RX uses rx_lead: each effective arm point is `start - rx_lead`.
        A start that would be a valid join-point for TX (rx_lead=0) may be
        too-late-to-arm for RX (rx_lead=10) — must skip one extra. Need
        a `now` value where the only difference between TX and RX is the
        skip count, demonstrating that rx_lead is correctly subtracted."""
        t0, starts, _ = self._synthetic_schedule()
        # starts = [1120, 1220, 1320, 1420], min_ahead_s=5 (default)
        # Pick now = T0+310 = 1310 → earliest acceptable arm point = 1315:
        #   TX (rx_lead=0): starts[2]=1320 >= 1315 → returns 2
        #   RX (rx_lead=10): starts[2]-10=1310 < 1315 → must skip;
        #                    starts[3]-10=1410 >= 1315 → returns 3
        self.assertEqual(
            m.compute_late_skip(starts, now=t0 + 310, rx_lead=0),
            2,
        )
        self.assertEqual(
            m.compute_late_skip(starts, now=t0 + 310, rx_lead=10),
            3,
        )

    def test_min_ahead_s_prevents_racing_init(self):
        """Without min_ahead_s, a start 1s in the future would be returned
        but the local machine can't possibly board-open + configure in time.
        With min_ahead_s=5, must skip to the next future start."""
        t0, starts, _ = self._synthetic_schedule()
        # now = T0 + 318; for TX (rx_lead=0): start T0+320 is only 2s in the
        # future (< min_ahead_s=5), so must be skipped.
        self.assertEqual(
            m.compute_late_skip(starts, now=t0 + 318, rx_lead=0,
                                min_ahead_s=5.0),
            3,
            "start 2 is only 2s ahead — below min_ahead_s=5, must skip to 3",
        )
        # With min_ahead_s=1 (tight), start 2 (2s ahead) is acceptable.
        self.assertEqual(
            m.compute_late_skip(starts, now=t0 + 318, rx_lead=0,
                                min_ahead_s=1.0),
            2,
        )

    # ---------- apply_late_skip wrapper (calls sys.exit on abort) ----------

    def test_apply_late_skip_on_time_no_mutation(self):
        """On-time launch returns the same lists unchanged."""
        _, starts, cfgs = self._synthetic_schedule()
        c, s = m.apply_late_skip(cfgs, starts, now=1010, rx_lead=0,
                                 mode_label="TX")
        self.assertEqual(c, cfgs)
        self.assertEqual(s, starts)

    def test_apply_late_skip_aborts_when_not_skipping(self):
        """Late launch without --skip-late-configs raises SystemExit with an
        actionable message."""
        t0, starts, cfgs = self._synthetic_schedule()
        with self.assertRaises(SystemExit) as cm:
            m.apply_late_skip(cfgs, starts, now=t0 + 250, rx_lead=0,
                              skip_late=False, mode_label="TX")
        msg = str(cm.exception)
        self.assertIn("TX", msg)
        self.assertIn("configs 0..1", msg)
        self.assertIn("--skip-late-configs", msg)
        self.assertIn("cfg2", msg)

    def test_apply_late_skip_recovers_when_skip_late(self):
        """--skip-late-configs slices cfgs/starts to the first future start
        and prints a [LATE] notice."""
        t0, starts, cfgs = self._synthetic_schedule()
        # Capture stdout for the [LATE] notice
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            c, s = m.apply_late_skip(cfgs, starts, now=t0 + 250,
                                     rx_lead=0, skip_late=True,
                                     mode_label="TX")
        self.assertEqual(len(c), 2, "Should recover cfg 2 and cfg 3")
        self.assertEqual(c[0]["label"], "cfg2")
        self.assertEqual(c[1]["label"], "cfg3")
        self.assertEqual(s[0], starts[2])
        notice = buf.getvalue()
        self.assertIn("[LATE - TX]", notice)
        self.assertIn("Skip", notice)
        self.assertIn("cfg2", notice)

    def test_apply_late_skip_all_past_aborts_with_reT0(self):
        """When all starts are in the past, abort with a re-T0 message
        even if --skip-late-configs is set (nothing to skip to)."""
        t0, starts, cfgs = self._synthetic_schedule()
        with self.assertRaises(SystemExit) as cm:
            m.apply_late_skip(cfgs, starts, now=t0 + 9999, rx_lead=0,
                              skip_late=True, mode_label="RX")
        msg = str(cm.exception)
        self.assertIn("RX", msg)
        self.assertIn("Re-set T0", msg)

    # ---------- End-to-end: against real build_preset_schedule ----------

    def test_integration_with_real_preset_schedule(self):
        """Smoke test the helper against the real production schedule
        builder, to confirm the contract is honoured (start - rx_lead >=
        now + min_ahead_s, indices into the cfgs list line up)."""

        class MockArgs:
            t0 = 1747000000  # arbitrary epoch ts
            t0_margin = 120
            guard = 20
            rx_lead = 10
            settle = 2
            swd_reset_s = 10

        # Build a minimal synthetic preset (2 configs, distinct mod/sf so
        # they trigger _mod_params_changed; expected_s ~ 30 and 60 each).
        cfgs = [
            {"label": "f650", "mod": "flrc", "sf": None, "br": 650,
             "bw": None, "pa": 10, "freq": 868000000, "plen": 51,
             "gap": 5000, "n_pkts": 100, "airtime_s": 0.001,
             "expected_s": 30.0, "idx": 0},
            {"label": "sf7", "mod": "lora", "sf": 7, "br": None,
             "bw": 125, "pa": 10, "freq": 868000000, "plen": 51,
             "gap": 1000, "n_pkts": 100, "airtime_s": 0.06,
             "expected_s": 60.0, "idx": 1},
        ]
        starts = m.build_preset_schedule(
            cfgs, MockArgs.t0,
            t0_margin=MockArgs.t0_margin, guard=MockArgs.guard,
            settle=MockArgs.settle, rx_lead=MockArgs.rx_lead,
            swd_reset_s=MockArgs.swd_reset_s,
        )
        # Sanity: starts[0] = T0 + 120
        self.assertEqual(starts[0], MockArgs.t0 + 120)
        # starts[1] = starts[0] + 30(expected) + 2(settle) + 20(guard)
        #           + 10(rx_lead) + 10(extra: swd_reset_s, since flrc->lora
        #                          is a mod change) = starts[0] + 72
        self.assertEqual(starts[1], starts[0] + 72)

        # On-time: now < T0+120-10-5
        self.assertEqual(
            m.compute_late_skip(starts, now=MockArgs.t0 + 100,
                                rx_lead=10),
            0,
        )

        # Late: now falls between starts[0] and starts[1] (past cfg 0,
        # in time for cfg 1 with rx_lead room).
        late_now = starts[0] + 40  # 40s after cfg 0 started
        self.assertEqual(
            m.compute_late_skip(starts, now=late_now, rx_lead=10),
            1,
        )


class FreqGateTests(unittest.TestCase):
    def test_eu_default(self):
        ok, _ = m.freq_gate(868000000, False)
        self.assertTrue(ok)
        ok, msg = m.freq_gate(915000000, False)
        self.assertFalse(ok)
        self.assertIn("--band-override", msg)

    def test_override_window(self):
        # Override window is the full LR2021 dual-band range 410-2483.5 MHz
        # (sub-GHz LF + 2.4 GHz HF path), matching E80_BENCH_OVERRIDE_*_HZ.
        for hz in (410000000, 868000000, 915000000, 960000000,
                   961000000, 2400000000, 2483500000):
            ok, _ = m.freq_gate(hz, True)
            self.assertTrue(ok, hz)
        for hz in (409000000, 2484000000):
            ok, _ = m.freq_gate(hz, True)
            self.assertFalse(ok, hz)


class ParseStatTests(unittest.TestCase):
    FW_TX = ("STAT role=TX sent=10000 sent_ok=10000 rx=0 crc_err=0 "
             "per_x1e6=0 elapsed_s=82.4 kbps=210 rssi_avg_dbm=0.0 "
             "snr_avg_db=0.0 drops=0")
    FW_RX = ("STAT role=RX sent=0 sent_ok=0 rx=9970 crc_err=3 per_x1e6=3000 "
             "per_ci_x1e6=[19000,33000] elapsed_s=42.5 kbps=63 "
             "rssi_avg_dbm=-87.5 snr_avg_db=9.8 drops=0")

    def test_firmware_tx_line(self):
        s = m.parse_stat(self.FW_TX)
        self.assertEqual(s["sent"], 10000)
        self.assertEqual(s["sent_ok"], 10000)
        self.assertEqual(s["recv"], 0)
        self.assertIsNone(s["per_ci_lo_pct"])

    def test_firmware_rx_line(self):
        s = m.parse_stat(self.FW_RX)
        self.assertEqual(s["recv"], 9970)
        self.assertEqual(s["crc_err"], 3)
        self.assertAlmostEqual(s["per_pct"], 0.3)
        self.assertAlmostEqual(s["per_ci_lo_pct"], 1.9)
        self.assertAlmostEqual(s["per_ci_hi_pct"], 3.3)
        self.assertEqual(s["rssi"], -87.5)
        self.assertEqual(s["snr"], 9.8)
        self.assertEqual(s["kbps"], 63)
        self.assertEqual(s["elapsed_s"], 42.5)
        self.assertEqual(s["drops"], 0)

    def test_legacy_shape_tolerated(self):
        s = m.parse_stat("OK STAT sent=100 recv=99 per=1.0 rssi=-90 snr=8 "
                         "per_ci_lo=0.4 per_ci_hi=2.2 kbps=42")
        self.assertEqual(s["sent"], 100)
        self.assertEqual(s["recv"], 99)
        self.assertAlmostEqual(s["per_pct"], 1.0)
        self.assertAlmostEqual(s["per_ci_hi_pct"], 2.2)

    def test_die_temp_field_parsed(self):
        """die_temp= on the STAT line is parsed into the normalized dict."""
        s = m.parse_stat(self.FW_RX + " die_temp=4096")
        self.assertEqual(s["die_temp"], 4096)

    def test_die_temp_absent_defaults_none(self):
        """No die_temp= field -> die_temp is None (not 0)."""
        s = m.parse_stat(self.FW_RX)
        self.assertIsNone(s["die_temp"])


class ParseTempLineTests(unittest.TestCase):
    """TEMP,<ts_ms>,<die_temp_raw> line parser (LR2021 VBE die temp)."""

    def test_parses_valid_line(self):
        d = m.parse_temp_line("TEMP,123456,4096")
        self.assertEqual(d["ts_ms"], 123456)
        self.assertEqual(d["die_temp_raw"], 4096)

    def test_returns_none_for_non_temp_line(self):
        self.assertIsNone(m.parse_temp_line("PKT,1,0,1,2,100,-70,8,1,0,0,868000000,LORA,7,125,5,10,64,0,0,0,0,0,0"))
        self.assertIsNone(m.parse_temp_line("STAT role=RX sent=0"))
        self.assertIsNone(m.parse_temp_line(""))

    def test_returns_none_for_malformed_temp(self):
        self.assertIsNone(m.parse_temp_line("TEMP,123456"))
        self.assertIsNone(m.parse_temp_line("TEMP,abc,4096"))
        self.assertIsNone(m.parse_temp_line("TEMP,123456,xyz"))

    def test_raw_to_celsius_conversion(self):
        """Host-side °C conversion of the raw 13-bit VBE value.

        Formula (lr20xx_system.h): T°C = (raw/8192 * Vana - Vbe25) *
        1000/VbeSlope + 25, with Vana=1.35, Vbe25=0.7295, VbeSlope=-1.7.
        """
        # raw=4096 -> (4096/8192*1.35 - 0.7295) * 1000/-1.7 + 25
        #          = (0.675 - 0.7295) * -588.235 + 25 = 57.06
        c = m.die_temp_raw_to_celsius(4096)
        self.assertAlmostEqual(c, 57.06, places=1)


class ParseTempLineExtendedTests(unittest.TestCase):
    """Extended TEMP line (e80-interp-logging): adds applied offset, curve
    version/params, supply voltage, GPS alt/temp and GS-synced epoch to the
    base TEMP,<ts_ms>,<die_temp_raw> line. Backward compatible: the base
    fields still parse, new fields default to None when absent."""

    EXT = ("TEMP,123456,4096,1200,3,2000,25000,3300,1500,12,1788877000000")

    def test_parses_extended_fields(self):
        d = m.parse_temp_line(self.EXT)
        self.assertEqual(d["ts_ms"], 123456)
        self.assertEqual(d["die_temp_raw"], 4096)
        self.assertEqual(d["offset_hz"], 1200)
        self.assertEqual(d["curve_ver"], 3)
        self.assertEqual(d["k_mhz_per_c"], 2000)
        self.assertEqual(d["t0_mc"], 25000)
        self.assertEqual(d["vcc_mv"], 3300)
        self.assertEqual(d["gps_alt_m"], 1500)
        self.assertEqual(d["gps_temp_c"], 12)
        self.assertEqual(d["sync_epoch_ms"], 1788877000000)

    def test_base_line_defaults_new_fields_none(self):
        d = m.parse_temp_line("TEMP,123456,4096")
        self.assertEqual(d["ts_ms"], 123456)
        self.assertEqual(d["die_temp_raw"], 4096)
        self.assertIsNone(d["offset_hz"])
        self.assertIsNone(d["curve_ver"])
        self.assertIsNone(d["k_mhz_per_c"])
        self.assertIsNone(d["t0_mc"])
        self.assertIsNone(d["vcc_mv"])
        self.assertIsNone(d["gps_alt_m"])
        self.assertIsNone(d["gps_temp_c"])
        self.assertIsNone(d["sync_epoch_ms"])

    def test_partial_extended_line(self):
        # offset present, rest absent
        d = m.parse_temp_line("TEMP,123456,4096,1200")
        self.assertEqual(d["offset_hz"], 1200)
        self.assertIsNone(d["curve_ver"])

    def test_malformed_extended_still_none(self):
        self.assertIsNone(m.parse_temp_line("TEMP,123456,4096,abc"))
        self.assertIsNone(m.parse_temp_line("TEMP,123456,4096,1200,3,xyz"))


class ParseGsObsLineTests(unittest.TestCase):
    """GS-side observation line (e80-interp-logging): the ground station logs
    its measured frequency offset, RSSI, balloon-synced timestamp, its own
    reference status, ambient temp and position/velocity (for Doppler
    correction). Format:
    GSOBS,<ts_ms>,<measured_offset_hz>,<rssi_dbm>,<gs_ref_stable>,
    <gs_ambient_c>,<gs_lat>,<gs_lon>,<gs_alt_m>,<gs_vx>,<gs_vy>,<gs_vz>"""

    OBS = "GSOBS,123456,25,-87.5,1,22.5,52.01,4.04,1.5,0.0,0.0,0.0"

    def test_parses_valid_gs_obs(self):
        d = m.parse_gs_obs_line(self.OBS)
        self.assertEqual(d["ts_ms"], 123456)
        self.assertEqual(d["measured_offset_hz"], 25)
        self.assertEqual(d["rssi_dbm"], -87.5)
        self.assertTrue(d["gs_ref_stable"])
        self.assertEqual(d["gs_ambient_c"], 22.5)
        self.assertEqual(d["gs_lat"], 52.01)
        self.assertEqual(d["gs_lon"], 4.04)
        self.assertEqual(d["gs_alt_m"], 1.5)
        self.assertEqual(d["gs_vx"], 0.0)
        self.assertEqual(d["gs_vy"], 0.0)
        self.assertEqual(d["gs_vz"], 0.0)

    def test_returns_none_for_non_gs_obs(self):
        self.assertIsNone(m.parse_gs_obs_line("TEMP,123456,4096"))
        self.assertIsNone(m.parse_gs_obs_line("PKT,1,0,1,2,100,-70,8,1,0,0,868000000,LORA,7,125,5,10,64,0,0,0,0,0,0"))
        self.assertIsNone(m.parse_gs_obs_line(""))

    def test_returns_none_for_malformed_gs_obs(self):
        self.assertIsNone(m.parse_gs_obs_line("GSOBS,123456"))
        self.assertIsNone(m.parse_gs_obs_line("GSOBS,abc,25,-87.5,1,22.5,52.01,4.04,1.5,0,0,0"))
        self.assertIsNone(m.parse_gs_obs_line("GSOBS,123456,25,-87.5,1,22.5,52.01,4.04,1.5,0,0"))

    def test_ref_stable_false(self):
        d = m.parse_gs_obs_line("GSOBS,123456,25,-87.5,0,22.5,52.01,4.04,1.5,0.0,0.0,0.0")
        self.assertFalse(d["gs_ref_stable"])


class FormatGsObsLineTests(unittest.TestCase):
    """Inverse of parse_gs_obs_line — helpers the GS tooling uses to emit the
    line (Doppler correction needs position/velocity + ref status)."""

    def test_round_trip(self):
        d = m.parse_gs_obs_line(self.OBS)
        ln = m.format_gs_obs_line(d)
        # parse back: must be identical (float formatting stable)
        self.assertEqual(m.parse_gs_obs_line(ln), d)

    def test_format_ref_stable_false(self):
        d = m.parse_gs_obs_line("GSOBS,123456,25,-87.5,0,22.5,52.01,4.04,1.5,0.0,0.0,0.0")
        ln = m.format_gs_obs_line(d)
        self.assertTrue(ln.startswith("GSOBS,"))
        self.assertIn(",0,", ln)  # gs_ref_stable=0 preserved

    OBS = "GSOBS,123456,25,-87.5,1,22.5,52.01,4.04,1.5,0.0,0.0,0.0"


class CsvLogTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "camp.csv")

    def tearDown(self):
        self.dir.cleanup()

    def test_header_written_once(self):
        log = m.CsvLog(self.path)
        log2 = m.CsvLog(self.path)   # append-only: no duplicate header
        with open(self.path) as f:
            lines = f.read().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0].split(","), m.CSV_COLUMNS)
        self.assertEqual(len(m.CSV_COLUMNS), 19)

    def test_meta_and_row_roundtrip(self):
        args = make_args(csv=self.path)
        log = m.CsvLog(self.path)
        log.stop_meta(args, id_tx="ID ... band=OVERRIDE", id_rx="ID ...",
                      t0_str="2026-08-30T14:05:00")
        cell = m.make_cell("flrc650", 10000)
        rx_stat = m.parse_stat(ParseStatTests.FW_RX)
        tx_stat = m.parse_stat(ParseStatTests.FW_TX)
        row = log.cell_row(args, cell, rx_stat, tx_stat, ts="2026-08-30T14:07:33")
        with open(self.path) as f:
            lines = [ln.rstrip("\n") for ln in f]
        self.assertTrue(lines[1].startswith("# STOP site=siteA stop=S3 dist_m=200"))
        self.assertTrue(any(ln.startswith("# gps_tx=52.01,4.04") for ln in lines))
        self.assertTrue(any(ln.startswith("# id_tx: ID ... band=OVERRIDE") for ln in lines))
        data = [ln for ln in lines if not ln.startswith("#") and ln != lines[0]]
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0].split(",")[0:9],
                         ["siteA", "S3", "200", "2", "flrc650", "51", "22",
                          "915000000", "10000"])
        toks = data[0].split(",")
        self.assertEqual(toks[10], "9970")          # recv
        self.assertEqual(toks[11], "0.300000")      # per pct
        self.assertEqual(toks[12], "1.900000")
        self.assertEqual(toks[13], "3.300000")
        self.assertEqual(toks[14], "-87.5")
        self.assertEqual(toks[18], "2026-08-30T14:07:33")

    def test_read_prior_rows_feeds_n_regime(self):
        args = make_args(csv=self.path)
        log = m.CsvLog(self.path)
        cell = m.make_cell("sf7", 1000)
        rx_stat = m.parse_stat(ParseStatTests.FW_RX)
        tx_stat = m.parse_stat(ParseStatTests.FW_TX)
        log.cell_row(args, cell, rx_stat, tx_stat)
        rows = m.read_prior_rows(self.path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(m.n_for_mod("sf7", rows), 1000)   # ci_hi 3.3% > 2%

    def test_abort_comment(self):
        log = m.CsvLog(self.path)
        log.abort("KeyboardInterrupt: ")
        with open(self.path) as f:
            self.assertIn("# ABORT", f.read())


class ScriptBuilderTests(unittest.TestCase):
    def test_single_shot_default_kept(self):
        tx, rx = m.build_script(make_args(matrix=None, band_override=False,
                                          dbm=10, freq=868000000,
                                          prime_discard=0))
        self.assertNotIn("BAND OVERRIDE 2026", tx)
        self.assertEqual(tx[0], "ID?")
        self.assertIn("ARM TX", tx)
        self.assertIn("START N=1000 LEN=255 GAP=5000", tx)

    def test_single_shot_unlock_prelude(self):
        tx, _ = m.build_script(make_args(matrix=None, prime_discard=0))
        i_band, i_freq = tx.index("BAND OVERRIDE 2026"), tx.index("FREQ 915000000")
        i_pow = tx.index("POWER MODE OUTDOOR 2026")
        self.assertTrue(i_band < i_freq and i_pow < i_freq)


class DryRunTests(unittest.TestCase):
    def _main(self, argv):
        old_argv = sys.argv
        sys.argv = ["e80_bench_ctl.py"] + argv
        buf, err = io.StringIO(), io.StringIO()
        code = 0
        try:
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
                m.main()
        except SystemExit as e:
            if isinstance(e.code, str):      # sys.exit("msg") -> stderr text
                err.write(e.code + "\n")
                code = 1
            else:
                code = e.code or 0
        finally:
            sys.argv = old_argv
        return code, buf.getvalue() + err.getvalue()

    def test_full_matrix_dry_run(self):
        with tempfile.TemporaryDirectory() as d:
            csv_path = os.path.join(d, "camp.csv")
            code, out = self._main([
                "--dry-run", "--matrix", "flrc650,flrc2600,sf7,sf12",
                "--csv", csv_path, "--site", "siteA", "--stop", "S3",
                "--dist-m", "200", "--repeat", "2",
                "--freq", "915000000", "--dbm", "22", "--band-override",
                "--t0", "2026-08-30 14:05:00",
                "--prime-discard", "0"])
            self.assertEqual(code, 0)
            for needle in ("cell 1 FLRC-650 N=10000 LEN=51",
                           "cell 4 LoRa-SF12 N=1000",
                           "cell 5 FLRC-650 N=10000 LEN=255",
                           "BAND OVERRIDE 2026",
                           "POWER MODE OUTDOOR 2026",
                           "MOD loRa 12 125",
                           "START N=1000 LEN=51 GAP=1000",
                           "START N=10000 LEN=255 GAP=5000",
                           "T0+00:00:30",           # margin 30 s
                           "ROLE NONE",
                           "SF12 time cap"):
                self.assertIn(needle, out, needle)
            self.assertFalse(os.path.exists(csv_path))  # dry-run writes nothing

    def test_bad_matrix_token_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            code, out = self._main([
                "--dry-run", "--matrix", "flrc650,fsk", "--freq", "915000000",
                "--band-override", "--csv", os.path.join(d, "c.csv")])
            self.assertNotEqual(code, 0)
            self.assertIn("unknown --matrix entry(ies) fsk", out)

    def test_freq_gate_rejects_915_without_override(self):
        code, out = self._main(["--dry-run", "--freq", "915000000"])
        self.assertNotEqual(code, 0)
        self.assertIn("--band-override", out)


class MatrixLiveTests(unittest.TestCase):
    """run_matrix() against FakeBoard + VirtualClock — no serial hardware."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.csv_path = os.path.join(self.dir.name, "camp.csv")

    def tearDown(self):
        self.dir.cleanup()

    def _run(self, world=None, **kw):
        world = world or {"tx": {"freq": 868000000, "n": 10000},
                          "rx": {"freq": 868000000, "n": 10000}}
        boards = {}

        def board_cls(port):
            b = FakeBoard(port, world)
            boards[port] = b
            return b

        t0 = m.parse_t0("2026-08-30 14:05:00")
        clock = VirtualClock(t0 - 60)
        args = make_args(csv=self.csv_path, matrix=["flrc650", "sf7"],
                         anchor=True, t0="2026-08-30 14:05:00",
                         prime_discard=0, **kw)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            m.run_matrix(args, board_cls=board_cls,
                         sleep_fn=clock.sleep, now_fn=clock.now)
        return boards, world, clock

    def test_happy_path_915_band_override(self):
        boards, world, clock = self._run()
        tx, rx = boards["/dev/ttyUSB3"], boards["/dev/ttyUSB4"]

        # unlock order: BAND/POWER before FREQ; ROLE TX before ARM TX
        txlog = tx.log
        self.assertLess(txlog.index("BAND OVERRIDE 2026"),
                        txlog.index("FREQ 915000000"))
        self.assertLess(txlog.index("POWER MODE OUTDOOR 2026"),
                        txlog.index("FREQ 915000000"))
        self.assertLess(txlog.index("ROLE TX"), txlog.index("ARM TX"))
        self.assertLess(txlog.index("ARM TX"), txlog.index("FREQ 915000000"))

        # per-cell scripts: RX arms before TX starts
        self.assertIn("START N=10000 LEN=51 GAP=5000", rx.log)
        self.assertIn("MOD flrc 650 22", tx.log)
        self.assertIn("MOD loRa 7 125", tx.log)
        self.assertIn("PA 22", tx.log)
        self.assertIn("START N=10000 LEN=51 GAP=5000", tx.log)
        self.assertIn("START N=10000 LEN=51 GAP=1000", tx.log)   # sf7 @ 10^4
        self.assertIn("START N=10000 LEN=255 GAP=5000", tx.log)  # anchor

        # schedule respected: first START no earlier than T0+margin
        # (virtual clock started 60 s before T0)
        # teardown: ROLE NONE on both
        self.assertEqual(tx.log[-2], "ROLE NONE")
        self.assertEqual(rx.log[-2], "ROLE NONE")

        with open(self.csv_path) as f:
            lines = [ln.rstrip("\n") for ln in f]
        self.assertEqual(lines[0].split(","), m.CSV_COLUMNS)
        meta = [ln for ln in lines if ln.startswith("#")]
        self.assertTrue(any("id_tx: ID E80BENCH" in ln and "band=OVERRIDE" in ln
                            for ln in meta))
        data = [ln for ln in lines[1:] if not ln.startswith("#")]
        self.assertEqual(len(data), 3)          # flrc650 + sf7 + anchor
        row1 = data[0].split(",")
        self.assertEqual(row1[4], "flrc650")
        self.assertEqual(row1[9], "10000")      # sent = TX sent_ok
        self.assertEqual(row1[10], "9997")      # recv = RX rx_ok (n-3)
        self.assertEqual(row1[11], "0.030000")
        anchor = data[2].split(",")
        self.assertEqual(anchor[4], "flrc650+anchor")
        self.assertEqual(anchor[5], "255")

    def test_gate_verification_failure_aborts(self):
        # Boards whose ID? never reports OVERRIDE acceptance -> preflight
        # RuntimeError, STOP + ROLE NONE attempted, CSV gains an ABORT row,
        # no cells run. RX opens first, so only the RX board is ever opened.
        world = {"tx": {"freq": 868000000, "n": 100},
                 "rx": {"freq": 868000000, "n": 100}}
        boards = {}

        def board_cls(port):
            b = FakeBoard(port, world)
            boards[port] = b
            return b

        orig = FakeBoard._reply

        def stuck(self, line, expect_ok):
            r = orig(self, line, expect_ok)
            if line == "ID?":
                r = r.replace("band=OVERRIDE", "band=863-870MHz")
            return r

        FakeBoard._reply = stuck
        t0 = m.parse_t0("2026-08-30 14:05:00")
        clock = VirtualClock(t0 - 60)
        args = make_args(csv=self.csv_path, matrix=["flrc650"],
                         anchor=False, t0="2026-08-30 14:05:00",
                         prime_discard=0)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(RuntimeError) as cm:
                    m.run_matrix(args, board_cls=board_cls,
                                 sleep_fn=clock.sleep, now_fn=clock.now)
            self.assertIn("BAND gate not accepted", str(cm.exception))
        finally:
            FakeBoard._reply = orig
        rx = boards["/dev/ttyUSB4"]
        self.assertIn("STOP", rx.log)
        self.assertIn("ROLE NONE", rx.log)
        self.assertNotIn("MOD flrc 650 22", rx.log)   # no cell ran
        with open(self.csv_path) as f:
            self.assertIn("# ABORT", f.read())

    def test_no_tx_without_band_override_at_915(self):
        # FakeBoard firmware model rejects FREQ 915 when not overridden; the
        # tool must issue the unlock first, so this run succeeds end-to-end.
        boards, world, _ = self._run(band_override=True)
        self.assertIn("BAND OVERRIDE 2026", boards["/dev/ttyUSB4"].log)


# ---------------------------------------------------------------------------
# _detect_board_for_mode — fallback loud-fail (never silently pick ch340[0])
# ---------------------------------------------------------------------------

class TestDetectBoardForModeFallback(unittest.TestCase):
    """When e80_detect cannot be imported, the manual-CH340 fallback must
    STILL loud-fail on multiple ports instead of picking the first one.

    The 9209aaf desk crash was exactly this: both tx and rx grabbed the same
    CH340 port. The fallback must print override commands, never ch340[0].
    """

    def _force_import_failure(self):
        """Make `import e80_detect` fail inside _detect_board_for_mode."""
        real_import = __builtins__["__import__"]

        def fake_import(name, *a, **kw):
            if name == "e80_detect":
                raise ImportError("simulated: e80_detect unavailable")
            return real_import(name, *a, **kw)

        return mock.patch("builtins.__import__", side_effect=fake_import)

    def test_multiple_ch340_loud_fails_with_override_commands(self):
        with self._force_import_failure(), \
             mock.patch("glob.glob", return_value=["/dev/ttyUSB0", "/dev/ttyUSB1"]), \
             mock.patch("subprocess.run") as mock_run, \
             mock.patch.object(m.sys, "exit") as mock_exit:
            mock_run.return_value = FakeSubprocessResult(stdout="ID_VENDOR_ID=1a86\nID_MODEL=CH340\n")
            m._detect_board_for_mode("tx", None, None)
        # sys.exit must be called (not return a port)
        mock_exit.assert_called_once()
        msg = mock_exit.call_args[0][0]
        self.assertIn("Multiple CH340 ports", msg)
        self.assertIn("make tx PORT=", msg)
        self.assertIn("PROBE=", msg)

    def test_single_ch340_still_returns_port(self):
        """Single-board behavior unchanged: one CH340 → return it."""
        with self._force_import_failure(), \
             mock.patch("glob.glob", return_value=["/dev/ttyUSB0"]), \
             mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = FakeSubprocessResult(stdout="ID_VENDOR_ID=1a86\nID_MODEL=CH340\n")
            port, probe = m._detect_board_for_mode("tx", None, None)
        self.assertEqual(port, "/dev/ttyUSB0")


class FakeSubprocessResult:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


# ===========================================================================
# GO MODE — derived-T0 sync (--sync cvm, ADR-range-sync-cvm.md §2.1 / §3)
#
# Stage 1 (task E80-CVM-P2): T0 is derived from the ARMED message instead of
# a 5-minute clock boundary; a GO-window guard replaces the legacy T0-past
# guard; rx_lead is clamped to >= 5 s; waits are anchored to a monotonic
# deadline captured when the ARMED is accepted; the session id comes from the
# ARMED and the log dir is s<sid>-go<t0>.
# ===========================================================================

GO_SESSION = "2609130435a3f"          # %y%m%d%H%M + 3-hex nonce


def _armed_dict(t_ready, session_id=GO_SESSION, stop="50m", created_at=None,
                preset_hash="abc123def456", seq=1, author="cafe"):
    """One ARMED object exactly as the RX publishes it (and relays by hand)."""
    return {
        "type": "ARMED",
        "session_id": session_id,
        "stop": stop,
        "t_ready_utc": int(t_ready),
        "preset_hash": preset_hash,
        "seq": seq,
        "created_at": int(created_at if created_at is not None else time.time()),
        "author": author,
    }


class ImmediateBus:
    """cvm_sync bus stand-in: fans pre-loaded events out on subscribe()."""

    def __init__(self, messages=()):
        self.messages = list(messages)
        self.published = []

    async def subscribe(self, handler):
        for msg in self.messages:
            await handler(msg)

    async def publish(self, event):
        self.published.append(event)


class FailingBus(ImmediateBus):
    """ImmediateBus whose publish() raises — relay pool unreachable.

    The STARTED notice is best-effort: radio capture must never depend on
    the CVM message layer, so a publish failure is a loud warning only.
    """

    async def publish(self, event):
        raise RuntimeError("relay pool unreachable")


class GoT0DerivationTests(unittest.TestCase):
    """T0 = armed["t_ready_utc"] + 30 s (cvm_sync.T0_MARGIN) — no boundary wait."""

    def test_t0_is_t_ready_plus_30(self):
        armed = _armed_dict(1_780_000_000)
        anchor = m.GoAnchor(armed, wall_at_event=1_780_000_000.0,
                            mono_at_event=500.0)
        self.assertEqual(anchor.t0_epoch, 1_780_000_030)
        self.assertEqual(anchor.t_ready_utc, 1_780_000_000)

    def test_derivation_matches_cvm_sync_compute_t0(self):
        armed = _armed_dict(1_780_000_123)
        anchor = m.GoAnchor(armed, wall_at_event=0.0, mono_at_event=0.0)
        self.assertEqual(anchor.t0_epoch, m.cvm.compute_t0(armed))
        self.assertEqual(anchor.t0_epoch, int(1_780_000_123 + m.cvm.T0_MARGIN))

    def test_no_clock_boundary_snapping(self):
        # t_ready is deliberately NOT near a 5-minute boundary: GO mode must
        # never round T0 up to the next boundary (that wait is the thing the
        # ARMED-derived T0 replaces).
        t_ready = 1_780_000_001
        anchor = m.GoAnchor(_armed_dict(t_ready), float(t_ready), 0.0)
        self.assertEqual(anchor.t0_epoch, t_ready + 30)
        self.assertNotEqual(anchor.t0_epoch % 300, 0)
        next_boundary = (t_ready // 300 + 1) * 300
        self.assertNotEqual(anchor.t0_epoch, next_boundary)

    def test_session_id_comes_from_armed_never_from_t0(self):
        armed = _armed_dict(1_780_000_000, session_id="2609130435a3f")
        anchor = m.GoAnchor(armed, 1_780_000_000.0, 500.0)
        self.assertEqual(anchor.session_id, "2609130435a3f")
        self.assertIsInstance(anchor.session_id, str)
        self.assertEqual(len(anchor.session_id), 13)     # yymmddhhmm + 3-hex
        # must NOT be the legacy %y%m%d%H%M int of the derived T0
        legacy = int(time.strftime("%y%m%d%H%M", time.gmtime(anchor.t0_epoch)))
        self.assertNotEqual(anchor.session_id, str(legacy))

    def test_deadline_is_a_monotonic_anchor(self):
        armed = _armed_dict(1_780_000_000)
        anchor = m.GoAnchor(armed, wall_at_event=1_779_999_990.0,
                            mono_at_event=500.0)
        # 40 s of wall time remained when the ARMED was accepted
        self.assertEqual(anchor.deadline_mono, 540.0)
        self.assertEqual(anchor.remaining_s(520.0), 20.0)
        # wall schedule instants map onto the monotonic timeline
        self.assertEqual(anchor.mono_target(anchor.t0_epoch), 540.0)
        self.assertEqual(anchor.mono_target(anchor.t0_epoch + 30), 570.0)

    def test_wall_now_mirrors_the_monotonic_anchor(self):
        anchor = m.GoAnchor(_armed_dict(1_780_000_000), 1_779_999_990.0, 500.0)
        self.assertEqual(anchor.wall_now(510.0), 1_780_000_000.0)


class GoWindowGuardTests(unittest.TestCase):
    """Pure GO-window guard: refuse when remaining-to-T0 < GO rx_lead (5 s)."""

    T0 = 1_780_000_030

    def test_accepts_when_remaining_equals_the_minimum(self):
        ok, msg = m.go_window_ok(self.T0, now_mono=1_005.0, deadline_mono=1_010.0)
        self.assertTrue(ok)
        self.assertEqual(msg, "")

    def test_accepts_with_full_30s_margin(self):
        # a freshly accepted ARMED always clears the guard
        armed = _armed_dict(1_780_000_000)
        anchor = m.GoAnchor(armed, 1_780_000_000.0, 500.0)
        ok, msg = m.go_window_ok(anchor.t0_epoch, now_mono=500.0,
                                 deadline_mono=anchor.deadline_mono)
        self.assertTrue(ok)
        self.assertEqual(msg, "")

    def test_refuses_when_remaining_below_the_minimum(self):
        # 26 s after the RX armed (30 s margin, 4 s left) — window expired
        ok, msg = m.go_window_ok(self.T0, now_mono=1_006.0, deadline_mono=1_010.0)
        self.assertFalse(ok)
        self.assertIn("GO window expired", msg)
        self.assertIn("26s ago", msg)          # seconds since the RX armed
        self.assertIn("Re-arm the RX", msg)
        self.assertIn(time.strftime("%Y-%m-%dT%H:%M:%S",
                                    time.localtime(self.T0)), msg)

    def test_refuses_after_t0_has_passed(self):
        ok, msg = m.go_window_ok(self.T0, now_mono=1_020.0, deadline_mono=1_010.0)
        self.assertFalse(ok)
        self.assertIn("40s ago", msg)

    def test_minimum_lead_is_the_go_rx_lead(self):
        self.assertEqual(m.GO_MODE_RX_LEAD_MIN, 5)
        # remaining of exactly 4.99 s is refused, 5.0 s accepted
        ok_lo, _ = m.go_window_ok(self.T0, 1_005.01, 1_010.0)
        ok_hi, _ = m.go_window_ok(self.T0, 1_005.0, 1_010.0)
        self.assertFalse(ok_lo)
        self.assertTrue(ok_hi)

    def test_wall_clock_step_does_not_move_the_guard(self):
        """An NTP step mid-pass must not shift a side: the decision is made
        against the monotonic deadline, so a +300 s wall jump is invisible."""
        t_ready = 1_780_000_000
        anchor = m.GoAnchor(_armed_dict(t_ready), wall_at_event=float(t_ready),
                            mono_at_event=500.0)
        mono_now = 510.0                     # 10 s of real elapsed time
        ok, msg = m.go_window_ok(anchor.t0_epoch, mono_now, anchor.deadline_mono)
        self.assertTrue(ok)
        self.assertEqual(msg, "")
        # the same instant, read off a stepped wall clock, would refuse
        stepped_wall_now = float(t_ready) + 310.0
        self.assertLess(anchor.t0_epoch - stepped_wall_now,
                        m.GO_MODE_RX_LEAD_MIN)
        # the monotonic translation is identical before/after the step
        self.assertEqual(m.mono_deadline(anchor.t0_epoch, float(t_ready), 500.0),
                         anchor.deadline_mono)
        self.assertEqual(anchor.mono_target(anchor.t0_epoch), anchor.deadline_mono)
        self.assertEqual(anchor.wall_now(mono_now), float(t_ready) + 10.0)


class GoRxLeadClampTests(unittest.TestCase):
    """GO mode arms RX >= 5 s early; boundary/manual-T0 mode is unchanged."""

    def test_clamped_up_in_go_mode(self):
        self.assertEqual(m.go_rx_lead(3, m.SYNC_CVM, None), 5)
        self.assertEqual(m.go_rx_lead(0, m.SYNC_CVM, None), 5)
        self.assertEqual(m.go_rx_lead(1, m.SYNC_CVM, None), 5)

    def test_never_lowered(self):
        self.assertEqual(m.go_rx_lead(8, m.SYNC_CVM, None), 8)
        self.assertEqual(m.go_rx_lead(30, m.SYNC_CVM, None), 30)

    def test_boundary_mode_unchanged(self):
        self.assertEqual(m.go_rx_lead(3, m.SYNC_BOUNDARY, None), 3)
        self.assertEqual(m.go_rx_lead(3, m.SYNC_BOUNDARY, 1_780_000_030), 3)

    def test_manual_t0_with_sync_cvm_is_legacy(self):
        # explicit --t0 always wins → untouched legacy rx_lead
        self.assertEqual(m.go_rx_lead(3, m.SYNC_CVM, 1_780_000_030), 3)


class GoLogPathTests(unittest.TestCase):
    """GO-mode default log dir: logs/s<sid>-go<t0>/<role>-log.csv."""

    def test_rx_go_dir_naming(self):
        p = m.resolve_log_path("rx-log.csv", True, GO_SESSION, 1_780_000_030,
                               "rx", repo_root="/tmp/repo", go=True)
        self.assertEqual(
            p, "/tmp/repo/logs/s2609130435a3f-go1780000030/rx-log.csv")

    def test_tx_go_dir_naming(self):
        p = m.resolve_log_path("tx-log.csv", True, GO_SESSION, 1_780_000_030,
                               "tx", repo_root="/tmp/repo", go=True)
        self.assertEqual(
            p, "/tmp/repo/logs/s2609130435a3f-go1780000030/tx-log.csv")
        self.assertNotIn("-t0", p)

    def test_legacy_t0_dir_untouched(self):
        p = m.resolve_log_path("tx-log.csv", True, 2609130435, 1_780_000_030,
                               "tx", repo_root="/tmp/repo")
        self.assertEqual(
            p, "/tmp/repo/logs/s2609130435-t01780000030/tx-log.csv")

    def test_explicit_path_always_wins(self):
        self.assertEqual(
            m.resolve_log_path("/elsewhere/rx.csv", False, GO_SESSION,
                               1_780_000_030, "rx", go=True),
            "/elsewhere/rx.csv")


class GoArmedSeamTests:
    """ARMED input seam (--armed-file / bus) — plain pytest class, tmp_path."""

    def test_armed_file_roundtrip(self, tmp_path):
        path = tmp_path / "armed.json"
        path.write_text(json.dumps(_armed_dict(1_780_000_000)))
        armed = m.load_armed_file(str(path))
        assert armed["session_id"] == GO_SESSION
        assert armed["type"] == "ARMED"

    def test_armed_file_freshness_is_relaxed(self):
        now = int(time.time())
        stale = _armed_dict(now + 60, created_at=now - 600)   # hand-relayed
        ok_strict, reason = m.cvm.validate_armed(stale, now=now)
        assert not ok_strict, "strict freshness must reject the stale ARMED"
        assert "skew" in reason
        ok_relaxed, reason2 = m.validate_armed_relaxed(stale)
        assert ok_relaxed, reason2

    def test_relaxed_validation_still_structural(self):
        broken = {"type": "ARMED", "session_id": GO_SESSION, "stop": "50m",
                  "seq": 1}                                   # no t_ready/preset
        ok, reason = m.validate_armed_relaxed(broken)
        assert not ok
        assert reason
        assert m.validate_armed_relaxed({"type": "VERDICT"})[0] is False

    def test_write_armed_out_roundtrip(self, tmp_path):
        p = tmp_path / "run" / "armed.json"
        armed = _armed_dict(1_780_000_000)
        m.write_armed_out(str(p), armed)
        assert json.loads(p.read_text()) == armed

    def test_preset_hash_is_stable_and_sensitive(self):
        a = [{"mod": "flrc", "br": 650, "plen": 51}]
        b = [{"mod": "flrc", "br": 650, "plen": 51}]
        c = [{"mod": "flrc", "br": 2600, "plen": 51}]
        assert m.preset_hash(a) == m.preset_hash(b)
        assert m.preset_hash(a) != m.preset_hash(c)

    def test_bus_seam_returns_the_accepted_armed(self):
        armed = _armed_dict(int(time.time()) + 30, created_at=int(time.time()))
        got = m.wait_for_armed_on_bus(ImmediateBus([armed]), timeout_s=2.0)
        assert got == armed

    def test_bus_seam_ignores_a_stale_armed(self):
        stale = _armed_dict(int(time.time()) + 30,
                            created_at=int(time.time()) - 600)
        got = m.wait_for_armed_on_bus(ImmediateBus([stale]), timeout_s=0.3)
        assert got is None

    def test_rx_generated_armed_is_valid_and_rx_authoritative(self):
        cfgs = [{"mod": "flrc", "br": 650, "plen": 51, "label": "FLRC-650"}]
        armed = m.build_go_armed(cfgs, GO_SESSION, "50m", 1_780_000_000)
        ok, reason = m.cvm.validate_armed(armed, now=1_780_000_000)
        assert ok, reason
        assert armed["session_id"] == GO_SESSION
        assert armed["preset_hash"] == m.preset_hash(cfgs)
        assert armed["seq"] >= 1
        assert m.cvm.compute_t0(armed) == 1_780_000_030


class GoWiringTests(unittest.TestCase):
    """run_tx_mode/run_rx_mode must consume the GO anchor (clamp + monotonic)."""

    class _AbortLaunch(KeyboardInterrupt):
        pass

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.cfgs = [{"mod": "flrc", "br": 650, "plen": 51, "n_pkts": 10,
                      "pa": 10, "freq": 868000000, "gap": 5000,
                      "label": "FLRC-650"}]
        self.seen = {}

    def tearDown(self):
        self.dir.cleanup()

    def _anchor(self, t_ready=None):
        t_ready = int(time.time()) + 120 if t_ready is None else t_ready
        return m.GoAnchor(_armed_dict(t_ready), wall_at_event=float(t_ready),
                          mono_at_event=500.0)

    def _spy_schedule(self):
        seen = self.seen

        def spy_cycle(cfgs, t0_margin=120, guard=20, settle=2.0, rx_lead=0,
                      swd_reset_s=0, band_swap_s=0):
            seen["cycle_rx_lead"] = rx_lead
            return 600

        def spy_apply(cfgs, starts, now, rx_lead, min_ahead_s=5.0,
                      skip_late=False, mode_label=""):
            seen["rx_lead"] = rx_lead
            seen["starts"] = list(starts)
            seen["mode_label"] = mode_label
            raise GoWiringTests._AbortLaunch()

        return spy_cycle, spy_apply

    def _board_cls(self):
        class StubBoard:
            def __init__(self, port):
                self.port = port
                self.log = []

            def drain(self, quiet=0.4):
                pass

            def close(self):
                self.log.append("CLOSE")

            def cmd(self, line, expect_ok=True, timeout=15.0):
                self.log.append(line)
                return "OK " + line.split()[0]

            def query(self, line, prefixes=(), timeout=15.0):
                self.log.append(line)
                return "ID E80BENCH role=RX band=863-870MHz"

            def stat(self):
                return "STAT role=RX recv=0"

        return StubBoard

    def _run(self, mode, anchor=None, rx_lead=3, sync=None, t0=None):
        spy_cycle, spy_apply = self._spy_schedule()
        args = make_args(
            mode=mode, configs=self.cfgs, session_id=GO_SESSION,
            t0=t0 if t0 is not None else str(self._anchor().t0_epoch),
            sync=sync if sync is not None else m.SYNC_BOUNDARY,
            rx_lead=rx_lead, skip_fw_check=True, loop=1,
            format="harmonized", no_swd_reset=True, skip_late_configs=True,
            prime_discard=0, probe="PX1", port="/dev/ttyUSB9",
            tx_log=os.path.join(self.dir.name, "tx.csv"),
            rx_log=os.path.join(self.dir.name, "rx.csv"))
        buf = io.StringIO()
        with mock.patch.object(m, "_detect_board_for_mode",
                               return_value=("/dev/ttyUSB9", "PX1")), \
             mock.patch.object(m, "id_preflight", lambda *a, **k: "ID"), \
             mock.patch.object(m, "compute_cycle_len", side_effect=spy_cycle), \
             mock.patch.object(m, "apply_late_skip", side_effect=spy_apply), \
             contextlib.redirect_stdout(buf):
            if mode == "tx":
                rc = m.run_tx_mode(args, board_cls=self._board_cls(),
                                   go_anchor=anchor)
            else:
                rc = m.run_rx_mode(args, board_cls=self._board_cls(),
                                   go_anchor=anchor)
        return rc, buf.getvalue()

    def test_rx_mode_uses_go_lead_and_derived_t0(self):
        anchor = self._anchor()
        rc, out = self._run("rx", anchor=anchor, rx_lead=3, sync=m.SYNC_CVM)
        self.assertEqual(rc, 0)
        self.assertEqual(self.seen["cycle_rx_lead"], 5)   # clamp reached cycle_len
        self.assertEqual(self.seen["rx_lead"], 5)         # and the late-skip guard
        self.assertEqual(self.seen["starts"][0],
                         anchor.t0_epoch + 30)            # T0 + t0_margin
        self.assertIn("GO MODE", out)
        self.assertIn(anchor.session_id, out)

    def test_tx_mode_cycle_len_uses_the_same_go_lead(self):
        # cycle_len must be identical on both sides or the cycles desync
        anchor = self._anchor()
        rc, out = self._run("tx", anchor=anchor, rx_lead=3, sync=m.SYNC_CVM)
        self.assertEqual(rc, 0)
        self.assertEqual(self.seen["cycle_rx_lead"], 5)
        self.assertIn("GO MODE", out)

    def test_boundary_mode_leads_unchanged(self):
        t0 = int(time.time()) + 600
        rc, out = self._run("rx", anchor=None, rx_lead=3, t0=str(t0))
        self.assertEqual(rc, 0)
        self.assertEqual(self.seen["cycle_rx_lead"], 3)
        self.assertEqual(self.seen["rx_lead"], 3)
        self.assertEqual(self.seen["starts"][0], t0 + 30)
        self.assertNotIn("GO MODE", out)


class GoMainWiringTests(unittest.TestCase):
    """main() GO-mode routing: derivation, override precedence, loud refusals."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.preset = os.path.join(self.dir.name, "preset.json")
        with open(self.preset, "w") as f:
            json.dump({"configs": [{"mod": "flrc", "br": 650, "plen": 51,
                                    "n_pkts": 10, "pa": 10, "freq": 868000000,
                                    "gap": 5000, "label": "FLRC-650"}]}, f)

    def tearDown(self):
        self.dir.cleanup()

    def _armed_file(self, t_ready, name="armed.json", **kw):
        p = os.path.join(self.dir.name, name)
        with open(p, "w") as f:
            json.dump(_armed_dict(t_ready, **kw), f)
        return p

    def _main(self, argv, bus=None):
        captured = {}

        def fake_run(args, board_cls=None, go_anchor=None):
            captured["args"] = args
            captured["anchor"] = go_anchor
            captured["runs"] = captured.get("runs", 0) + 1
            return 0

        old_argv = sys.argv
        sys.argv = ["e80_bench_ctl.py"] + argv
        buf, err = io.StringIO(), io.StringIO()
        code = 0
        try:
            with mock.patch.object(m, "run_tx_mode", side_effect=fake_run), \
                 mock.patch.object(m, "run_rx_mode", side_effect=fake_run), \
                 mock.patch("os.makedirs"), \
                 contextlib.redirect_stdout(buf), \
                 contextlib.redirect_stderr(err):
                try:
                    code = m.main(bus=bus)
                except SystemExit as e:
                    if isinstance(e.code, str):
                        err.write(str(e.code) + "\n")
                        code = 1
                    else:
                        code = e.code or 0
        finally:
            sys.argv = old_argv
        return code, buf.getvalue() + err.getvalue(), captured

    def test_go_mode_derives_t0_and_session_from_armed_file(self):
        t_ready = int(time.time()) + 60
        argv = ["--mode", "rx", "--sync", "cvm",
                "--armed-file", self._armed_file(t_ready),
                "--configs", self.preset]
        code, out, cap = self._main(argv)
        self.assertEqual(code, 0)
        self.assertIn("args", cap)
        args = cap["args"]
        self.assertEqual(args.session_id, GO_SESSION)      # from ARMED, not T0
        self.assertEqual(args.t0, str(t_ready + 30))       # derived T0
        self.assertEqual(args.rx_lead, 5)                  # GO clamp
        self.assertIsNotNone(cap["anchor"])
        self.assertEqual(cap["anchor"].source, "file")
        self.assertEqual(cap["anchor"].t0_epoch, t_ready + 30)
        # default log dir switches to the GO scheme
        self.assertEqual(
            os.path.basename(os.path.dirname(args.rx_log)),
            "s{}-go{}".format(GO_SESSION, t_ready + 30))
        self.assertTrue(args.rx_log.startswith(
            m.default_logs_root() + os.sep))
        # absolute wall T0 stays visible for log correlation / GPS stitch
        self.assertIn("GO MODE", out)
        self.assertIn(GO_SESSION, out)
        self.assertIn("t0={}".format(t_ready + 30), out)

    def test_go_mode_rejects_explicit_session_id(self):
        t_ready = int(time.time()) + 60
        argv = ["--mode", "rx", "--sync", "cvm",
                "--armed-file", self._armed_file(t_ready),
                "--session-id", "2609130435", "--configs", self.preset]
        code, out, cap = self._main(argv)
        self.assertNotEqual(code, 0)
        self.assertIn("session_id comes from ARMED in GO mode", out)
        self.assertNotIn("args", cap)          # refused before any launch

    def test_go_mode_refuses_an_expired_go_window(self):
        t_ready = int(time.time()) - 60        # armed a minute ago
        argv = ["--mode", "tx", "--sync", "cvm",
                "--armed-file", self._armed_file(t_ready),
                "--configs", self.preset]
        code, out, cap = self._main(argv)
        self.assertNotEqual(code, 0)
        self.assertIn("GO window expired", out)
        self.assertIn("Re-arm the RX", out)
        self.assertNotIn("args", cap)

    def test_manual_t0_wins_over_sync_cvm(self):
        t0 = int(time.time()) + 300
        argv = ["--mode", "rx", "--sync", "cvm", "--t0", str(t0),
                "--session-id", "1234", "--configs", self.preset]
        code, out, cap = self._main(argv)
        self.assertEqual(code, 0)
        args = cap["args"]
        self.assertEqual(args.t0, str(t0))
        self.assertEqual(args.session_id, 1234)            # int, legacy flag
        self.assertIsNone(cap["anchor"])                   # legacy path
        self.assertEqual(args.rx_lead, 3)                  # no GO clamp
        # legacy s<sid>-t0<epoch> log scheme preserved
        self.assertEqual(os.path.basename(os.path.dirname(args.rx_log)),
                         "s1234-t0{}".format(t0))

    def test_boundary_default_is_legacy(self):
        t0 = int(time.time()) + 300
        for extra in ([], ["--sync", "boundary"]):
            argv = ["--mode", "tx", "--t0", str(t0), "--session-id", "42",
                    "--configs", self.preset] + extra
            code, out, cap = self._main(argv)
            self.assertEqual(code, 0, out)
            self.assertIsNone(cap["anchor"])
            self.assertEqual(cap["args"].session_id, 42)
            self.assertEqual(os.path.basename(
                os.path.dirname(cap["args"].tx_log)), "s42-t0{}".format(t0))

    # ------------------------------------------------------------------
    # Split-brain guard: a TX start always echoes a LIVE RX session id and
    # announces itself with a STARTED notice. There is no code path where
    # TX starts without echoing a live RX session id.
    # ------------------------------------------------------------------

    def test_legacy_tx_refuses_a_start_without_an_echoed_session_id(self):
        """A manual TX start with no --session-id is refused loudly.

        main() used to silently invent one (%y%m%d%H%M); the RX stayed on
        its own session and the analysis reported a false MISS/LOGGING GAP
        with no warning — the split-brain failure mode.
        """
        t0 = int(time.time()) + 300
        argv = ["--mode", "tx", "--t0", str(t0), "--configs", self.preset]
        code, out, cap = self._main(argv)
        self.assertNotEqual(code, 0)
        self.assertIn("split brain", out.lower())
        self.assertIn("--session-id", out)
        self.assertIn("RX", out)               # echo the RX banner value
        self.assertNotIn("runs", cap)          # refused before any launch

    def test_legacy_tx_dry_run_without_session_id_is_not_refused(self):
        t0 = int(time.time()) + 300
        argv = ["--mode", "tx", "--t0", str(t0), "--configs", self.preset,
                "--dry-run"]
        code, out, cap = self._main(argv)
        self.assertEqual(code, 0, out)
        self.assertNotIn("split brain", out.lower())

    def test_legacy_tx_writes_started_json_next_to_tx_log(self):
        t0 = int(time.time()) + 300
        tx_log = os.path.join(self.dir.name, "tx-log.csv")
        argv = ["--mode", "tx", "--t0", str(t0), "--session-id", "2609130435",
                "--configs", self.preset, "--tx-log", tx_log]
        # Scope the session-collision scan to the temp dir: the real
        # <repo>/logs can hold an s2609130435-t0<other>/ dir from an earlier
        # manual CLI run (this test's session id is a fixed echo).
        with mock.patch.object(m, "default_logs_root",
                               return_value=self.dir.name):
            code, out, cap = self._main(argv)
        self.assertEqual(code, 0, out)
        self.assertEqual(cap["runs"], 1)
        path = os.path.join(self.dir.name, "started.json")
        self.assertTrue(os.path.exists(path), out)
        with open(path) as f:
            notice = json.load(f)
        self.assertEqual(notice["type"], "STARTED")
        self.assertEqual(notice["session_id"], "2609130435")   # echoed, not made up
        self.assertEqual(notice["t0"], t0)
        self.assertEqual(notice["t_ready_utc"], t0 - int(m.T0_MARGIN))
        self.assertEqual(notice["role"], "tx")
        self.assertEqual(notice["preset_hash"],
                         m.preset_hash(m.load_config_preset(self.preset)))
        self.assertIn("STARTED", out)
        self.assertIn(path, out)               # absolute artefact path
        self.assertIn("relay", out.lower())    # Signal fallback instruction

    def test_go_tx_publishes_started_on_the_bus_with_the_armed_session(self):
        t_ready = int(time.time()) + 60
        bus = ImmediateBus([_armed_dict(t_ready)])
        argv = ["--mode", "tx", "--sync", "cvm", "--configs", self.preset]
        code, out, cap = self._main(argv, bus=bus)
        self.assertEqual(code, 0, out)
        self.assertEqual(cap["runs"], 1)
        started = [msg for msg in bus.published if msg.get("type") == "STARTED"]
        self.assertEqual(len(started), 1, bus.published)
        self.assertEqual(started[0]["session_id"], GO_SESSION)
        self.assertEqual(started[0]["session_id"], cap["anchor"].session_id)
        self.assertEqual(started[0]["t0"], t_ready + 30)
        self.assertEqual(started[0]["t_ready_utc"], t_ready)
        self.assertEqual(started[0]["role"], "tx")
        self.assertIn("STARTED", out)
        self.assertIn(GO_SESSION, out)
        self.assertIn("published", out)

    def test_started_publish_failure_is_a_loud_warning_not_a_stop(self):
        t_ready = int(time.time()) + 60
        bus = FailingBus([_armed_dict(t_ready)])
        argv = ["--mode", "tx", "--sync", "cvm", "--configs", self.preset]
        code, out, cap = self._main(argv, bus=bus)
        self.assertEqual(code, 0, out)
        self.assertEqual(cap["runs"], 1)       # radio capture still ran
        self.assertIn("WARNING", out)
        self.assertIn("STARTED", out)

    def test_build_started_notice_defaults_stop_and_derives_the_fields(self):
        args = argparse.Namespace(stop=None, t0="1789000000",
                                  session_id="2609130435")
        notice = m.build_started_notice(args, [{"mod": "flrc"}])
        self.assertEqual(notice["type"], "STARTED")
        self.assertEqual(notice["stop"], "?")
        self.assertEqual(notice["session_id"], "2609130435")
        self.assertEqual(notice["t0"], 1789000000)
        self.assertEqual(notice["t_ready_utc"], 1789000000 - int(m.T0_MARGIN))
        self.assertEqual(notice["role"], "tx")
        self.assertTrue(notice["preset_hash"])

    def test_go_rx_without_armed_file_generates_and_writes_armed_out(self):
        out_path = os.path.join(self.dir.name, "armed-out.json")
        argv = ["--mode", "rx", "--sync", "cvm", "--configs", self.preset,
                "--armed-out", out_path, "--stop", "50m"]
        code, out, cap = self._main(argv)
        self.assertEqual(code, 0)
        self.assertEqual(cap["anchor"].source, "generate")
        self.assertTrue(os.path.exists(out_path))
        with open(out_path) as f:
            written = json.load(f)
        self.assertEqual(written["type"], "ARMED")
        self.assertEqual(written["session_id"], cap["args"].session_id)
        self.assertEqual(written["stop"], "50m")
        self.assertTrue(written["preset_hash"])
        # session id format: %y%m%d%H%M + 3-hex nonce, never T0-derived
        self.assertRegex(written["session_id"], r"^[0-9]{10}[0-9a-f]{3}$")

    def test_go_tx_without_an_armed_source_hard_errors(self):
        argv = ["--mode", "tx", "--sync", "cvm", "--configs", self.preset]
        code, out, cap = self._main(argv)
        self.assertNotEqual(code, 0)
        self.assertIn("--armed-file", out)
        self.assertIn("ARMED", out)
        # no live RX session was echoed → no STARTED may be emitted at all
        self.assertNotIn("STARTED", out)
        self.assertNotIn("runs", cap)

    def test_go_tx_uses_the_bus_seam(self):
        t_ready = int(time.time()) + 60
        bus = ImmediateBus([_armed_dict(t_ready)])
        argv = ["--mode", "tx", "--sync", "cvm", "--configs", self.preset]
        code, out, cap = self._main(argv, bus=bus)
        self.assertEqual(code, 0)
        self.assertEqual(cap["anchor"].source, "bus")
        self.assertEqual(cap["anchor"].session_id, GO_SESSION)
        self.assertEqual(cap["anchor"].t0_epoch, t_ready + 30)

    def test_go_dry_run_needs_no_t0(self):
        t_ready = int(time.time()) + 60
        argv = ["--mode", "rx", "--sync", "cvm", "--dry-run",
                "--armed-file", self._armed_file(t_ready),
                "--configs", self.preset]
        code, out, cap = self._main(argv)
        self.assertEqual(code, 0)
        self.assertIn("DRY RUN", out)
        self.assertIn("FLRC-650", out)
        self.assertIn("t0={}".format(t_ready + 30), out)


    # --- a --dry-run writes NO run artefacts -----------------------------

    def _run_main(self, argv, bus=None):
        """main() with the REAL artefact-writing path (no runner/fs mocks).

        A --dry-run GO RX returns before any board or countdown is touched, so
        this exercises the write itself rather than a mocked stand-in.
        """
        old_argv = sys.argv
        sys.argv = ["e80_bench_ctl.py"] + argv
        buf, err = io.StringIO(), io.StringIO()
        code = 0
        try:
            with contextlib.redirect_stdout(buf), \
                 contextlib.redirect_stderr(err):
                code = m.main(bus=bus)
        except SystemExit as e:
            if isinstance(e.code, str):
                err.write(str(e.code) + "\n")
                code = 1
            else:
                code = e.code or 0
        finally:
            sys.argv = old_argv
        return code, buf.getvalue() + err.getvalue()

    def test_go_rx_dry_run_writes_no_armed_out_file(self):
        # the --armed-out write used to sit ABOVE the --dry-run gate, so a
        # rehearsal left a real ARMED artefact behind for a run that never
        # happened (and its logs/s<sid>-go<t0>/ dir with it).
        out_path = os.path.join(self.dir.name, "armed-dry-run.json")
        argv = ["--mode", "rx", "--sync", "cvm", "--dry-run",
                "--configs", self.preset, "--stop", "50m",
                "--armed-out", out_path]
        code, out = self._run_main(argv)
        self.assertEqual(code, 0, out)
        self.assertIn("DRY RUN", out)
        self.assertIn("ARMED not written", out)
        self.assertFalse(os.path.exists(out_path),
                         "a --dry-run must not create the ARMED artefact")

    def test_go_rx_dry_run_creates_no_log_dir_either(self):
        # default --armed-out is <rx-log dir>/armed.json — INSIDE the per-run
        # logs/s<sid>-go<t0>/ dir. Creating it from a dry run made the next
        # live launch trip the session-collision guard on a dir no run wrote.
        argv = ["--mode", "rx", "--sync", "cvm", "--dry-run",
                "--configs", self.preset, "--stop", "50m"]
        code, out = self._run_main(argv)
        self.assertEqual(code, 0, out)
        m_dry = re.search(r"ARMED not written \((.+?)\)", out)
        self.assertIsNotNone(m_dry, out)
        path = m_dry.group(1)
        self.assertFalse(os.path.exists(path), path)
        self.assertFalse(
            os.path.exists(os.path.dirname(path)),
            "dry run created the run's log dir: {}".format(
                os.path.dirname(path)))


class GoBoardSessionTests(unittest.TestCase):
    """The board session a GO run sends to the firmware.

    src/bench_cmd.c parses `SESSION <id>` with bench_parse_u32 and PKT lines
    echo it with console_put_u32, so a GO session id (10 digits + 3-hex nonce)
    can never be carried on the wire. The board gets the numeric projection;
    the full id stays at the message/join layer (ARMED, log-dir name, banner).
    """

    def test_numeric_session_passes_through(self):
        self.assertEqual(m.board_session_id(2609130435), 2609130435)
        self.assertEqual(m.board_session_id("2609130435"), 2609130435)

    def test_go_session_projects_to_its_digit_prefix(self):
        self.assertEqual(m.board_session_id("2609130435a3f"), 2609130435)

    def test_projection_fits_a_u32(self):
        self.assertLess(m.board_session_id("2609130435a3f"), 2 ** 32)

    def test_same_minute_arms_share_one_board_session(self):
        # Documents the constraint the ARMED nonce exists to work around: two
        # arms inside one minute are the SAME board session on the wire.
        self.assertEqual(m.board_session_id("2609130435a3f"),
                         m.board_session_id("2609130435b71"))

    def test_unprojectable_session_is_none(self):
        self.assertIsNone(m.board_session_id("bench-a"))
        self.assertIsNone(m.board_session_id(None))
        self.assertIsNone(m.board_session_id(""))

    def test_session_command_uses_the_projection(self):
        self.assertEqual(m.session_command("2609130435a3f"),
                         "SESSION 2609130435")
        self.assertEqual(m.session_command(42), "SESSION 42")

    def test_session_command_refuses_an_unprojectable_id(self):
        with self.assertRaises(SystemExit):
            m.session_command("bench-a")

    def test_parse_pkt_line_keeps_a_non_numeric_session(self):
        # Regression: int(p[1]) killed the whole row (ValueError -> None), so
        # every config of such a log read as MISS with no warning.
        line = ",".join(["PKT", "2609130435a3f"] + [str(i) for i in range(2, 24)])
        p = m.parse_pkt_line(line)
        self.assertIsNotNone(p)
        self.assertEqual(p["session_id"], "2609130435a3f")

    def test_wire_session_id_is_what_the_logs_carry(self):
        # Every row a run writes (PKT + STAT, both sides) must use the wire
        # spelling, or range_check/merge_csvs compare a u32 against the full
        # GO id and report a false LOGGING GAP / an all-MISS merge.
        self.assertEqual(m.wire_session_id("2609130435a3f"), 2609130435)
        self.assertEqual(m.wire_session_id(2609130435), 2609130435)
        self.assertEqual(m.wire_session_id("bench-a"), "bench-a")


# The --mode CLI timing-knob defaults (main()'s argparse): the GO fingerprint
# hashes them, so a hand-built ARMED in a test must use the same values.
CLI_KNOBS = {"t0_margin": 30.0, "guard": 5.0, "settle": 1.0, "rx_lead": 3.0,
             "swd_reset_s": 2.0, "band_swap_s": 30.0}


def preset_knobs_hash(preset_path, knobs=None):
    """preset_hash() of a preset FILE + a knob set (default: the CLI defaults)."""
    return m.preset_hash(m.load_config_preset(preset_path),
                         CLI_KNOBS if knobs is None else knobs)


class RecordingAnchor(m.GoAnchor):
    """GoAnchor that records every mono_target(ts) instant (white-box spy).

    Used to pin that a capture/poll window is bounded by the ANCHOR (monotonic
    image of the window end) instead of a bare time.time() deadline.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.targets = []

    def mono_target(self, ts):
        self.targets.append(float(ts))
        return super().mono_target(ts)


class GoFingerprintTests(unittest.TestCase):
    """Blocker 4: preset_hash is compared, and covers the schedule knobs.

    ADR §2.1: the ARMED carries `preset_hash` and both sides must match. The
    knobs that feed compute_cycle_len / build_preset_schedule must be inside
    the fingerprint too, or the two operators can run different timing and
    re-anchor apart from cycle 2 on with no detection.
    """

    CFGS = [{"mod": "flrc", "br": 650, "plen": 51, "n_pkts": 10, "pa": 10,
             "freq": 868000000, "gap": 5000, "label": "FLRC-650"}]

    def test_preset_hash_without_knobs_is_unchanged(self):
        # legacy callers / docs keep the preset-only digest
        self.assertEqual(m.preset_hash(self.CFGS),
                         m.preset_hash(json.loads(json.dumps(self.CFGS))))
        self.assertNotEqual(m.preset_hash(self.CFGS),
                            m.preset_hash(self.CFGS, CLI_KNOBS))

    def test_schedule_knobs_covers_every_cycle_len_knob(self):
        knobs = m.schedule_knobs(make_args())
        self.assertEqual(set(knobs), {"t0_margin", "guard", "settle",
                                      "rx_lead", "swd_reset_s", "band_swap_s"})
        # every knob that compute_cycle_len / build_preset_schedule consume
        self.assertEqual(knobs["guard"], 20.0)
        self.assertEqual(knobs["rx_lead"], 10.0)

    def test_fingerprint_is_stable_and_knob_sensitive(self):
        base = m.schedule_knobs(make_args())
        self.assertEqual(m.preset_hash(self.CFGS, base),
                         m.preset_hash(self.CFGS, dict(base)))
        for knob, value in (("guard", 35.0), ("settle", 9.0),
                            ("t0_margin", 130.0), ("rx_lead", 12.0),
                            ("swd_reset_s", 7.0), ("band_swap_s", 45.0)):
            tweaked = dict(base, **{knob: value})
            self.assertNotEqual(m.preset_hash(self.CFGS, base),
                                m.preset_hash(self.CFGS, tweaked), knob)

    def test_generated_armed_fingerprints_the_knobs(self):
        args = make_args(mode="rx", stop="50m")
        armed, src, _wall, _mono = m.acquire_armed_for_go(args, self.CFGS, None)
        self.assertEqual(src, "generate")
        self.assertEqual(armed["preset_hash"],
                         m.preset_hash(self.CFGS, m.schedule_knobs(args)))
        other, _s, _w, _mo = m.acquire_armed_for_go(
            make_args(mode="rx", stop="50m", guard=20), self.CFGS, None)
        self.assertNotEqual(armed["preset_hash"], other["preset_hash"])


class GoFingerprintCompareTests(unittest.TestCase):
    """acquire_armed_for_go() refuses an ARMED built for another preset/knobs."""

    CFGS = GoFingerprintTests.CFGS

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.dir.cleanup()

    def _armed_file(self, preset_hash, t_ready=None, **kw):
        p = os.path.join(self.dir.name, "armed.json")
        with open(p, "w") as f:
            json.dump(_armed_dict(
                int(t_ready if t_ready is not None else time.time() + 30),
                preset_hash=preset_hash, **kw), f)
        return p

    def _args(self, path, **kw):
        return make_args(mode="tx", sync=m.SYNC_CVM, armed_file=path,
                         configs=self.CFGS, stop="50m", **kw)

    def _refusal(self, args, bus=None):
        """Run acquire_armed_for_go and return the SystemExit message."""
        with self.assertRaises(SystemExit) as exc:
            m.acquire_armed_for_go(args, self.CFGS, bus)
        return str(exc.exception.code if exc.exception.code else "")

    def test_matching_fingerprint_is_accepted(self):
        path = self._armed_file(
            m.preset_hash(self.CFGS, m.schedule_knobs(make_args())))
        armed, src, _w, _mo = m.acquire_armed_for_go(
            self._args(path), self.CFGS, None)
        self.assertEqual(src, "file")
        self.assertEqual(armed["session_id"], GO_SESSION)

    def test_another_preset_is_refused(self):
        # the reviewer's repro: preset_hash=deadbeefcafe with a stop-50m preset
        # passed every check and walked the two sides apart from cycle 2 on.
        path = self._armed_file("deadbeefcafe")
        msg = self._refusal(self._args(path))
        self.assertIn("deadbeefcafe", msg)
        self.assertIn("preset", msg.lower())
        self.assertIn("ARMED", msg)

    def test_another_knob_set_is_refused(self):
        # same preset, different --guard: cycle_len differs (240s vs 480s), so
        # every cycle from 2 on re-anchors to a different t0_cycle.
        path = self._armed_file(
            m.preset_hash(self.CFGS, dict(CLI_KNOBS, guard=20.0)))
        msg = self._refusal(self._args(path))
        self.assertIn("guard", msg)
        self.assertIn("20", msg)

    def test_bus_armed_from_another_knob_set_is_refused(self):
        armed = _armed_dict(int(time.time()) + 30,
                            preset_hash=m.preset_hash(
                                self.CFGS, dict(CLI_KNOBS, settle=9.0)))
        msg = self._refusal(self._args(None), bus=ImmediateBus([armed]))
        self.assertIn("settle", msg)


class GoAnchorBoundWaitTests(unittest.TestCase):
    """Blocker 5: every GO-mode capture/poll window is bounded by the anchor.

    A bare time.time() deadline ends the RX capture early on a forward NTP
    step (silently fewer packets -> false THIN/MISS) and stretches it on a
    backward step (past the next config's arm point, so the burst is captured
    under the previous config header).
    """

    def test_monotonic_deadline_closes_and_opens_the_window(self):
        self.assertTrue(m.poll_left(100.0, None, mono_fn=lambda: 99.9))
        self.assertFalse(m.poll_left(100.0, None, mono_fn=lambda: 100.0))

    def test_forward_wall_step_does_not_close_a_monotonic_window(self):
        # the wall clock jumped +1e6 s; the monotonic deadline is untouched
        self.assertTrue(m.poll_left(600.0, None, mono_fn=lambda: 599.0,
                                    wall_fn=lambda: 1_000_000.0))
        # the same instant read off the wall clock would have ended it
        self.assertFalse(m.poll_left(None, 500.0, wall_fn=lambda: 1_000_000.0))

    def test_legacy_wall_deadline_unchanged(self):
        self.assertTrue(m.poll_left(None, 100.0, wall_fn=lambda: 99.0))
        self.assertFalse(m.poll_left(None, 100.0, wall_fn=lambda: 100.0))


class GoWaitBoundsTests(unittest.TestCase):
    """White-box: run_rx_mode/run_tx_mode hand the ANCHOR the window end."""

    class _AbortCycle(KeyboardInterrupt):
        pass

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        # ONE config + a clearly non-zero expected_s: with one config the only
        # mono_target() calls today are the arm instant and the config start,
        # so the capture/poll bound is unambiguous (no next-config arm instant
        # can coincidentally equal the window end).
        self.cfgs = [{"mod": "flrc", "br": 650, "plen": 51, "n_pkts": 100,
                      "pa": 10, "freq": 868000000, "gap": 5000, "label": "A"}]
        self.seen = {}

    def tearDown(self):
        self.dir.cleanup()

    def _anchor(self):
        """An anchor whose whole timeline is already past → every wait is a
        no-op, so the test measures WHICH bound is used, not real sleeping."""
        t_ready = int(time.time()) - 130          # T0 = now - 100 s
        return RecordingAnchor(_armed_dict(t_ready), wall_at_event=float(t_ready),
                               mono_at_event=time.monotonic() - 500.0)

    def _board_cls(self):
        class StubSerial:
            def read(self, n=0):
                return b""

            def close(self):
                pass

        class StubBoard:
            def __init__(self, port):
                self.port = port
                self.ser = StubSerial()
                self.log = []

            def drain(self, quiet=0.4):
                pass

            def close(self):
                self.log.append("CLOSE")

            def cmd(self, line, expect_ok=True, timeout=15.0):
                self.log.append(line)
                return "OK " + line.split()[0]

            def query(self, line, prefixes=(), timeout=15.0):
                self.log.append(line)
                return "ID E80BENCH role=RX band=863-870MHz"

            def stat(self):
                # sent_ok == n_pkts so the TX completion poll ends on the first
                # read (this test measures the BOUND, not the fw timing).
                return ("STAT role=TX sent=100 sent_ok=100 rx=0 crc_err=0 "
                        "per_x1e6=0 elapsed_s=1.0 kbps=1 rssi_avg_dbm=0.0 "
                        "snr_avg_db=0.0 drops=0")

        return StubBoard

    def _run(self, mode, anchor):
        calls = {"n": 0}

        def spy_apply(cfgs, starts, now, rx_lead, min_ahead_s=5.0,
                      skip_late=False, mode_label=""):
            calls["n"] += 1
            if calls["n"] == 1:
                self.seen["starts"] = list(starts)
                return cfgs, starts
            raise GoWaitBoundsTests._AbortCycle()

        args = make_args(
            mode=mode, configs=self.cfgs, session_id=GO_SESSION,
            t0=str(anchor.t0_epoch), sync=m.SYNC_CVM, stop="50m", rx_lead=3,
            settle=0, guard=0, skip_fw_check=True, loop=1,
            format="harmonized", no_swd_reset=True, skip_late_configs=True,
            prime_discard=0, probe="PX1", port="/dev/ttyUSB9",
            tx_log=os.path.join(self.dir.name, "tx.csv"),
            rx_log=os.path.join(self.dir.name, "rx.csv"))
        buf = io.StringIO()
        with mock.patch.object(m, "_detect_board_for_mode",
                               return_value=("/dev/ttyUSB9", "PX1")), \
             mock.patch.object(m, "id_preflight", lambda *a, **k: "ID"), \
             mock.patch.object(m, "apply_late_skip", side_effect=spy_apply), \
             contextlib.redirect_stdout(buf):
            fn = m.run_tx_mode if mode == "tx" else m.run_rx_mode
            rc = fn(args, board_cls=self._board_cls(), go_anchor=anchor)
        return rc, args

    def test_rx_capture_window_is_bounded_by_the_anchor(self):
        anchor = self._anchor()
        rc, args = self._run("rx", anchor)
        self.assertEqual(rc, 0)
        loaded = m.load_config_preset(self.cfgs)
        start = self.seen["starts"][0]
        capture_end = start + loaded[0]["expected_s"] + args.settle + args.guard
        self.assertIn(capture_end, anchor.targets,
                      "RX capture window must end on the anchor's monotonic "
                      "image of start+capture_duration: {}".format(anchor.targets))

    def test_tx_stat_poll_is_bounded_by_the_anchor(self):
        anchor = self._anchor()
        rc, args = self._run("tx", anchor)
        self.assertEqual(rc, 0)
        loaded = m.load_config_preset(self.cfgs)
        start = self.seen["starts"][0]
        poll_end = start + loaded[0]["expected_s"] + 120
        self.assertIn(poll_end, anchor.targets,
                      "TX stat poll must end on the anchor, not time.time(): "
                      "{}".format(anchor.targets))

    def test_go_banners_carry_the_stop_token(self):
        # blocker 3: the GO session dir has no stop-<dist> level, so the stop
        # token in the banner is what lets range_check verify the log.
        anchor = self._anchor()
        for mode in ("rx", "tx"):
            rc, args = self._run(mode, anchor)
            self.assertEqual(rc, 0)
            path = args.rx_log if mode == "rx" else args.tx_log
            with open(path) as f:
                header = f.read()
            self.assertIn("stop=50m", header, (mode, header))
            self.assertIn("GO_MODE", header, (mode, header))


if __name__ == "__main__":
    unittest.main()
