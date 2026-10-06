#!/usr/bin/env python3
"""Host tests for range_bench_ctl.py — pure helpers, BoardCtl, FakeBoard.

HS-1a: airtime, N-regime, VirtualClock.
HS-3:  BoardCtl (via BoardSerial), FakeBoard double, port resolution,
       open/close/cmd/query/stat/reboot simulation.

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


# ---------------------------------------------------------------------------
# HS-1b: matrix cells + T0 stop schedule + freq gate
# ---------------------------------------------------------------------------

class MatrixCellTests(unittest.TestCase):
    """make_cell / build_matrix_cells — cells v1 (plan §3, grill B2, M4)."""

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
        cells = m.build_matrix_cells(
            make_args(matrix=["sf7"], anchor=False), [])
        self.assertEqual(len(cells), 1)

    def test_explicit_length_respected(self):
        # single-shot CSV rows carry the actual payload length
        self.assertEqual(m.make_cell("flrc650", 1000, length=255)["len_bytes"],
                         255)
        self.assertEqual(m.make_cell("flrc650", 1000)["len_bytes"], 51)

    def test_edge_regime_from_prior_rows(self):
        rows = [dict(mod=k, len="51", per_ci_hi="5.0")
                for k in m.MATRIX_KEYS]
        cells = m.build_matrix_cells(
            make_args(matrix=m.MATRIX_KEYS), rows)
        self.assertEqual([c["n"] for c in cells],
                         [1000, 1000, 1000, 1000, 10000])

    def test_expected_s_formula(self):
        c = m.make_cell("sf7", 100)
        self.assertAlmostEqual(
            c["expected_s"],
            100 * (m.airtime_s("sf7", 51) + 1000 / 1e6))

    def test_lf_flrc_cells_flagged_pending_b2(self):
        # grill B2: LF-FLRC unproven on this module until the HW-B2 smoke
        for key in ("flrc650", "flrc2600"):
            cell = m.make_cell(key, 1000)
            self.assertEqual(cell["feasible"], "pending", key)
            self.assertEqual(cell["band"], "lf", key)

    def test_lora_cells_feasible_ok(self):
        for key in ("sf7", "sf12"):
            cell = m.make_cell(key, 1000)
            self.assertEqual(cell["feasible"], "ok", key)
            self.assertEqual(cell["band"], "lf", key)

    def test_hf_cells_listed_but_not_in_default_matrix(self):
        for key in m.HF_KEYS:
            self.assertIn(key, m.MOD_DEFS)
            self.assertNotIn(key, m.MATRIX_KEYS)
            self.assertEqual(m.MOD_DEFS[key]["band"], "hf")

    def test_hf_cell_excluded_from_v1_matrix(self):
        with self.assertRaises(ValueError) as cm:
            m.build_matrix_cells(
                make_args(matrix=["hf_flrc2600"], anchor=False), [])
        self.assertIn("HF", str(cm.exception))

    def test_unknown_mod_rejected(self):
        with self.assertRaises(ValueError):
            m.build_matrix_cells(
                make_args(matrix=["wcdma"], anchor=False), [])


class ScheduleTests(unittest.TestCase):
    """parse_t0 / build_stop_schedule (T0 + margin, rx_lead, guard, settle)."""

    def _cells(self):
        return m.build_matrix_cells(
            make_args(matrix=["flrc650", "sf7"]), [])

    def test_first_start_is_t0_plus_margin(self):
        cells = self._cells()
        t0 = m.parse_t0("2026-08-30 14:05:00")
        sched = m.build_stop_schedule(cells, t0, t0_margin_s=120, guard_s=20)
        self.assertEqual(sched[0]["start"], t0 + 120)

    def test_rx_arm_leads_start_by_rx_lead(self):
        cells = self._cells()
        t0 = 1_700_000_000.0
        sched = m.build_stop_schedule(cells, t0, 120, 20, rx_lead_s=30)
        for entry in sched:
            self.assertEqual(entry["rx_arm"], entry["start"] - 30)

    def test_monotonic_ordering(self):
        cells = self._cells()
        t0 = m.parse_t0("2026-08-30 14:05:00")
        sched = m.build_stop_schedule(cells, t0, 120, 20, rx_lead_s=10)
        starts = [e["start"] for e in sched]
        arms = [e["rx_arm"] for e in sched]
        self.assertTrue(all(b > a for a, b in zip(starts, starts[1:])))
        self.assertTrue(all(b > a for a, b in zip(arms, arms[1:])))

    def test_spacing_covers_expected_guard_settle(self):
        cells = self._cells()
        t0 = m.parse_t0("2026-08-30 14:05:00")
        sched = m.build_stop_schedule(cells, t0, 120, 20)
        self.assertGreaterEqual(sched[1]["start"] - sched[0]["start"],
                                cells[0]["expected_s"] + 20 + 5)  # settle=5

    def test_keys_follow_cell_order(self):
        cells = self._cells()
        sched = m.build_stop_schedule(cells, 0.0, 0, 0)
        self.assertEqual([e["key"] for e in sched],
                         [c["key"] for c in cells])

    def test_parse_t0_formats(self):
        self.assertEqual(m.parse_t0("2026-08-30 14:05:00"),
                         m.parse_t0("2026-08-30T14:05:00"))
        with self.assertRaises(ValueError):
            m.parse_t0("tomorrow")

    def test_fmt_offset(self):
        t0 = 1_700_000_000
        self.assertEqual(m.fmt_offset(t0 + 3661, t0), "T0+01:01:01")
        # negative offsets clamp to zero (never print T0-…)
        self.assertEqual(m.fmt_offset(t0 - 5, t0), "T0+00:00:00")

    def test_fmt_hms(self):
        self.assertEqual(m.fmt_hms(125), "02:05")


class FreqGateTests(unittest.TestCase):
    """freq_gate — EU SRD 863-870 MHz hard clamp v1 (plan §1, §5)."""

    def test_eu_default_accepts_868(self):
        ok, msg = m.freq_gate(868000000)
        self.assertTrue(ok)
        self.assertEqual(msg, "")

    def test_band_edges_accepted(self):
        for hz in (863000000, 870000000):
            ok, _ = m.freq_gate(hz)
            self.assertTrue(ok, hz)

    def test_below_band_rejected(self):
        ok, msg = m.freq_gate(862999999)
        self.assertFalse(ok)
        self.assertIn("863-870", msg)

    def test_above_band_rejected(self):
        ok, msg = m.freq_gate(870000001)
        self.assertFalse(ok)

    def test_hf_2g4_rejected_v1(self):
        # HF cells are listed in MOD_DEFS but the 2.4 GHz path is out of
        # scope v1 — the gate must reject it
        ok, msg = m.freq_gate(2400000000)
        self.assertFalse(ok)
        self.assertIn("863-870", msg)

    def test_915_rejected_no_override_path(self):
        # unlike E80, v1 has no --band-override: hard clamp only
        ok, msg = m.freq_gate(915000000)
        self.assertFalse(ok)
        self.assertIn("no override", msg)


# ---------------------------------------------------------------------------
# HS-3: FakeBoard + BoardCtl tests (protocol §1 simulation, no hardware)
# ---------------------------------------------------------------------------

class FakeBoardTests(unittest.TestCase):
    """FakeBoard implements the §1 console protocol for offline tests."""

    def _make(self, side="tx", role="NONE"):
        world = {side: {"role": role, "freq": 868000000, "mod": "FLRC",
                         "br": 650000, "dbm": 10, "n": 100, "len": 51,
                         "gap_us": 5000, "power_outdoor": False,
                         "state": "IDLE", "sent": 0, "sent_ok": 0,
                         "rx": 0, "crc_err": 0}}
        return m.FakeBoard("/dev/ttyUSB3" if side == "tx" else "/dev/ttyUSB4",
                           world), world

    def test_id_query_returns_id_prefix(self):
        fb, _ = self._make("tx", "NONE")
        reply = fb.query("ID?")
        self.assertTrue(reply.startswith("ID "))
        self.assertIn("role=NONE", reply)

    def test_role_tx(self):
        fb, w = self._make("tx", "NONE")
        reply = fb.cmd("ROLE TX")
        self.assertEqual(w["tx"]["role"], "TX")
        self.assertTrue(reply.startswith("OK ROLE TX"))

    def test_role_rx(self):
        fb, w = self._make("rx", "NONE")
        reply = fb.cmd("ROLE RX")
        self.assertEqual(w["rx"]["role"], "RX")
        self.assertTrue(reply.startswith("OK ROLE RX"))

    def test_role_none_re_inhibits(self):
        fb, w = self._make("tx", "TX")
        reply = fb.cmd("ROLE NONE")
        self.assertEqual(w["tx"]["role"], "NONE")
        self.assertTrue(reply.startswith("OK ROLE NONE"))

    def test_mod_flrc_valid(self):
        fb, w = self._make("tx", "TX")
        reply = fb.cmd("MOD FLRC 650")
        self.assertIn("OK MOD FLRC", reply)
        self.assertIn("br_hz=650000", reply)
        self.assertEqual(w["tx"]["mod"], "FLRC")

    def test_mod_flrc_invalid_bitrate(self):
        fb, _ = self._make("tx", "TX")
        with self.assertRaises(RuntimeError) as cm:
            fb.cmd("MOD FLRC 999")
        self.assertIn("ERR RANGE", str(cm.exception))

    def test_mod_lora_valid(self):
        fb, w = self._make("tx", "TX")
        reply = fb.cmd("MOD LORA 7 125")
        self.assertIn("OK MOD LORA", reply)
        self.assertIn("sf=7", reply)
        self.assertEqual(w["tx"]["mod"], "LORA")

    def test_mod_lora_sf_out_of_range(self):
        fb, _ = self._make("tx", "TX")
        with self.assertRaises(RuntimeError) as cm:
            fb.cmd("MOD LORA 4 125")
        self.assertIn("ERR RANGE", str(cm.exception))

    def test_freq_valid(self):
        fb, w = self._make("tx", "TX")
        reply = fb.cmd("FREQ 868000000")
        self.assertEqual(w["tx"]["freq"], 868000000)
        self.assertTrue(reply.startswith("OK FREQ"))

    def test_freq_out_of_eu_band(self):
        fb, _ = self._make("tx", "TX")
        with self.assertRaises(RuntimeError) as cm:
            fb.cmd("FREQ 2400000000")
        self.assertIn("ERR RANGE", str(cm.exception))

    def test_pa_indoor_cap(self):
        fb, w = self._make("tx", "TX")
        reply = fb.cmd("PA 10")
        self.assertEqual(w["tx"]["dbm"], 10)
        self.assertTrue(reply.startswith("OK PA"))

    def test_pa_above_indoor_cap_without_unlock(self):
        fb, _ = self._make("tx", "TX")
        with self.assertRaises(RuntimeError) as cm:
            fb.cmd("PA 14")
        self.assertIn("ERR POWER-LOCKED", str(cm.exception))

    def test_pa_above_indoor_cap_with_unlock(self):
        fb, w = self._make("tx", "TX")
        fb.cmd("POWER MODE OUTDOOR 2026")
        w["tx"]["power_outdoor"] = True
        reply = fb.cmd("PA 14")
        self.assertEqual(w["tx"]["dbm"], 14)
        self.assertTrue(reply.startswith("OK PA"))

    def test_pa_out_of_range(self):
        fb, _ = self._make("tx", "TX")
        with self.assertRaises(RuntimeError) as cm:
            fb.cmd("PA 30")
        self.assertIn("ERR RANGE", str(cm.exception))

    def test_len_valid(self):
        fb, w = self._make("tx", "TX")
        reply = fb.cmd("LEN 51")
        self.assertEqual(w["tx"]["len"], 51)
        self.assertTrue(reply.startswith("OK LEN"))

    def test_len_out_of_range(self):
        fb, _ = self._make("tx", "TX")
        with self.assertRaises(RuntimeError) as cm:
            fb.cmd("LEN 5")
        self.assertIn("ERR RANGE", str(cm.exception))

    def test_n_valid(self):
        fb, w = self._make("tx", "TX")
        reply = fb.cmd("N 1000")
        self.assertEqual(w["tx"]["n"], 1000)
        self.assertTrue(reply.startswith("OK N"))

    def test_gap_valid(self):
        fb, w = self._make("tx", "TX")
        reply = fb.cmd("GAP 5000")
        self.assertEqual(w["tx"]["gap_us"], 5000)
        self.assertTrue(reply.startswith("OK GAP"))

    def test_start_without_role_inhibited(self):
        fb, _ = self._make("tx", "NONE")
        with self.assertRaises(RuntimeError) as cm:
            fb.cmd("START")
        self.assertIn("ERR INHIBITED", str(cm.exception))

    def test_start_with_role_tx(self):
        fb, w = self._make("tx", "TX")
        reply = fb.cmd("START")
        self.assertTrue(reply.startswith("OK START"))

    def test_start_rx(self):
        fb, w = self._make("rx", "RX")
        reply = fb.cmd("START")
        self.assertTrue(reply.startswith("OK START RX"))

    def test_stop(self):
        fb, _ = self._make("tx", "TX")
        reply = fb.cmd("STOP")
        self.assertTrue(reply.startswith("OK STOP"))

    def test_stat_returns_stat_prefix(self):
        fb, w = self._make("tx", "TX")
        w["tx"]["sent"] = 100
        w["tx"]["sent_ok"] = 100
        reply = fb.stat()
        self.assertTrue(reply.startswith("STAT "))
        self.assertIn("sent=100", reply)

    def test_power_mode_outdoor_correct_pin(self):
        fb, w = self._make("tx", "TX")
        reply = fb.cmd("POWER MODE OUTDOOR 2026")
        self.assertTrue(reply.startswith("OK POWER"))
        self.assertTrue(w["tx"]["power_outdoor"])

    def test_power_mode_outdoor_wrong_pin(self):
        fb, _ = self._make("tx", "TX")
        with self.assertRaises(RuntimeError) as cm:
            fb.cmd("POWER MODE OUTDOOR 1234")
        self.assertIn("ERR ARG", str(cm.exception))

    def test_help(self):
        fb, _ = self._make("tx", "NONE")
        reply = fb.query("HELP")
        self.assertTrue(reply.startswith("OK HELP") or
                        reply.startswith("HELP"))

    def test_unknown_command_err(self):
        fb, _ = self._make("tx", "NONE")
        with self.assertRaises(RuntimeError) as cm:
            fb.cmd("FOOBAR")
        self.assertIn("ERR UNKNOWN", str(cm.exception))

    def test_drain_does_not_crash(self):
        fb, _ = self._make("tx", "NONE")
        fb.drain()

    def test_close_logs(self):
        fb, _ = self._make("tx", "NONE")
        fb.close()
        self.assertIn("CLOSE", fb.log)

    def test_reboot(self):
        fb, w = self._make("tx", "TX")
        reply = fb.cmd("REBOOT")
        self.assertTrue(reply.startswith("OK REBOOT"))
        self.assertEqual(w["tx"]["role"], "NONE")

    def test_cmd_case_insensitive(self):
        fb, w = self._make("tx", "NONE")
        reply = fb.cmd("role tx")
        self.assertEqual(w["tx"]["role"], "TX")
        self.assertTrue(reply.startswith("OK ROLE TX"))


class PortResolutionTests(unittest.TestCase):
    """resolve_port() maps /dev/serial/by-id paths and falls back to raw."""

    def test_pico_by_id_path(self):
        path = ("ID range-host v1 role=NONE tx_inhibited=1")
        # resolve_port should accept by-id paths and return them as-is
        resolved = m.resolve_port(
            "/dev/serial/by-id/usb-Raspberry_Pi_Pico_E663977F242D-if00")
        self.assertEqual(resolved,
                         "/dev/serial/by-id/usb-Raspberry_Pi_Pico_E663977F242D-if00")

    def test_raw_dev_path_passthrough(self):
        resolved = m.resolve_port("/dev/ttyACM0")
        self.assertEqual(resolved, "/dev/ttyACM0")


class BoardCtlTests(unittest.TestCase):
    """BoardCtl wraps a board (FakeBoard or BoardSerial) with protocol §1
    conveniences: drain boot banner, ID? handshake with role check,
    cmd/query/stat wrappers, and reboot.
    """

    def _make_ctl(self, side="tx", role="NONE"):
        world = {side: {"role": role, "freq": 868000000, "mod": "FLRC",
                         "br": 650000, "dbm": 10, "n": 100, "len": 51,
                         "gap_us": 5000, "power_outdoor": False,
                         "state": "IDLE", "sent": 0, "sent_ok": 0,
                         "rx": 0, "crc_err": 0}}
        board = m.FakeBoard(
            "/dev/ttyUSB3" if side == "tx" else "/dev/ttyUSB4", world)
        ctl = m.BoardCtl(board)
        return ctl, board, world

    def test_open_drains_and_handshakes(self):
        ctl, board, _ = self._make_ctl("tx", "NONE")
        # open() drains boot banner + sends ID? and checks role field
        info = ctl.open()
        self.assertIn("ID", info)
        self.assertEqual(info["role"], "NONE")
        self.assertIn("ID?", board.log)

    def test_open_checks_expected_role(self):
        ctl, board, _ = self._make_ctl("tx", "TX")
        info = ctl.open(expected_role="TX")
        self.assertEqual(info["role"], "TX")

    def test_open_wrong_role_raises(self):
        ctl, board, _ = self._make_ctl("tx", "NONE")
        with self.assertRaises(RuntimeError) as cm:
            ctl.open(expected_role="TX")
        self.assertIn("role", str(cm.exception))

    def test_cmd_sends_and_returns_reply(self):
        ctl, _, _ = self._make_ctl("tx", "TX")
        reply = ctl.cmd("ROLE RX")
        self.assertTrue(reply.startswith("OK ROLE RX"))

    def test_cmd_err_raises_runtime_error(self):
        ctl, _, _ = self._make_ctl("tx", "NONE")
        with self.assertRaises(RuntimeError):
            ctl.cmd("START")  # INHIBITED

    def test_query_returns_matching_prefix(self):
        ctl, _, _ = self._make_ctl("tx", "NONE")
        reply = ctl.query("ID?")
        self.assertTrue(reply.startswith("ID "))

    def test_stat_returns_parsed_dict(self):
        ctl, board, world = self._make_ctl("tx", "TX")
        world["tx"]["sent"] = 50
        world["tx"]["sent_ok"] = 50
        result = ctl.stat()
        self.assertIsInstance(result, str)
        self.assertTrue(result.startswith("STAT "))

    def test_close_calls_board_close(self):
        ctl, board, _ = self._make_ctl("tx", "NONE")
        ctl.close()
        self.assertIn("CLOSE", board.log)

    def test_reboot_sends_reboot_and_re_handshakes(self):
        ctl, board, world = self._make_ctl("tx", "TX")
        ctl.reboot()
        self.assertIn("REBOOT", board.log)
        # After reboot, role should be NONE (board reset)
        self.assertEqual(world["tx"]["role"], "NONE")
        # Should have re-handshaked (second ID?)
        id_count = board.log.count("ID?")
        self.assertGreaterEqual(id_count, 2)

    def test_cmd_no_expect_ok_for_stop_on_error(self):
        """cmd(expect_ok=False) returns ERR replies instead of raising."""
        ctl, _, _ = self._make_ctl("tx", "NONE")
        reply = ctl.cmd("START", expect_ok=False)
        self.assertTrue(reply.startswith("ERR"))

    def test_full_session_simulation(self):
        """Simulate a full TX session: open → config → start → stop → close."""
        ctl, board, world = self._make_ctl("tx", "NONE")
        ctl.open()
        ctl.cmd("ROLE TX")
        ctl.cmd("FREQ 868000000")
        ctl.cmd("MOD FLRC 650")
        ctl.cmd("PA 10")
        ctl.cmd("LEN 51")
        ctl.cmd("N 100")
        ctl.cmd("GAP 5000")
        ctl.cmd("START")
        ctl.cmd("STOP")
        ctl.close()
        # Verify command sequence was sent
        self.assertIn("ROLE TX", board.log)
        self.assertIn("FREQ 868000000", board.log)
        self.assertIn("MOD FLRC 650", board.log)
        self.assertIn("START", board.log)
        self.assertIn("STOP", board.log)
        self.assertIn("CLOSE", board.log)


if __name__ == "__main__":
    unittest.main()