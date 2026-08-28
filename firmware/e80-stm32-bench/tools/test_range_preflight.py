#!/usr/bin/env python3
"""test_range_preflight.py — host-side fail-fast + sync-hygiene guards.

Covers the 2026-08-28 live-field-incident hardening (NO firmware changes):

  1. PREFLIGHT at banner time (before the countdown): open the port, send
     ID?, require a reply; when the preset has any cfg pa>10 require
     'pcap=' in the ID? output — fail in seconds, not at GO after the
     3-minute T0 wait.
  2. T0-past guard: T0 < now+60s hard-errors at banner
     ("T0 in past — recompute or pass explicit T0"); no countdown, no launch.
  3. Session collision guard: an existing logs/s<SESSION>-t0<OTHER>/ dir
     with OTHER != T0 hard-errors, naming both dirs.
  4. POWER MODE OUTDOOR timeout: retry once after 2 s, then error text
     listing the causes (console wedged / old fw missing pcap= / wrong port).
  5. range_check.py: rx-log and tx-log t0 (filename/header) must match —
     error loudly when they differ.

Run:  python3 -m pytest tools/test_range_preflight.py -v
"""
import argparse
import contextlib
import io
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS_DIR)

import e80_bench_ctl as m          # noqa: E402
import range_check as rc           # noqa: E402

E80_DIR = os.path.dirname(TOOLS_DIR)

T0_FUTURE = int(time.time()) + 600       # comfortably in the future
T0_PAST = int(time.time()) - 3600        # an hour ago

PRESET_HI_PA = {  # outdoor preset — needs POWER MODE OUTDOOR + pcap in ID?
    "name": "preflight-hi",
    "configs": [
        {"label": "flrc-hi", "mod": "flrc", "br": 650, "sf": None,
         "bw": None, "pa": 22, "freq": 868000000, "plen": 255,
         "gap": 1000, "n_pkts": 10},
    ],
}
PRESET_LO_PA = {  # indoor preset — pa<=10, no pcap requirement
    "name": "preflight-lo",
    "configs": [
        {"label": "flrc-lo", "mod": "flrc", "br": 650, "sf": None,
         "bw": None, "pa": 10, "freq": 868000000, "plen": 255,
         "gap": 1000, "n_pkts": 10},
    ],
}

ID_WITH_PCAP = ("ID E80BENCH v1.0 fw=abc1234 role=TX band=863-870MHz "
                "pa=22 pcap=+10dBm chip=2.1")
ID_WITHOUT_PCAP = ("ID E80BENCH v1.0 fw=abc1234 role=TX band=863-870MHz "
                   "pa=22 chip=2.1")   # old fw, pre-d788c72


def make_range_args(**kw):
    """argparse.Namespace with every field the distributed modes touch."""
    base = dict(
        mode="tx", configs=PRESET_HI_PA, port="/dev/ttyUSB3", probe="PX123",
        tx_log="tx-log.csv", rx_log="rx-log.csv", session_id=2608282100,
        loop=1, t0=str(T0_FUTURE), t0_margin=30, guard=5, rx_lead=3,
        settle=1, swd_reset_s=2, band_swap_s=30, skip_fw_check=True,
        no_swd_reset=True, skip_late_configs=False, prime_discard=2,
        format="harmonized",
    )
    base.update(kw)
    return argparse.Namespace(**base)


class FakeClock:
    """Virtual wall clock — time.time/time.sleep patched onto m.time."""

    def __init__(self, start):
        self.t = float(start)
        self.sleeps = []

    def time(self):
        return self.t

    def sleep(self, d):
        d = max(0.0, d)
        self.t += d
        self.sleeps.append(d)
        return None


class FakeSer:
    """serial port stand-in: reads block-then-timeout, advancing the clock."""

    def __init__(self, clock):
        self.clock = clock
        self.written = []

    def read(self, n=2048):
        self.clock.sleep(0.05)     # emulate read timeout
        return b""

    def write(self, b):
        self.written.append(b)

    def close(self):
        pass


class RangeBoard:
    """Firmware stand-in for the distributed range modes (TX and RX).

    id_reply=None models a wedged console (no reply to ID?).
    power_failures=N models N consecutive POWER MODE OUTDOOR timeouts.
    """

    def __init__(self, port, id_reply=ID_WITH_PCAP, power_failures=0,
                 clock=None):
        self.port = port
        self.id_reply = id_reply
        self.power_failures = power_failures
        self.clock = clock or FakeClock(time.time())
        self.ser = FakeSer(self.clock)
        self.log = []

    # --- console API used by the tool ---
    def drain(self, quiet=0.4):
        pass

    def close(self):
        self.log.append("CLOSE")

    def cmd(self, line, expect_ok=True, timeout=15.0):
        self.log.append(line)
        if line.startswith("POWER MODE OUTDOOR"):
            if self.power_failures > 0:
                self.power_failures -= 1
                raise RuntimeError(
                    "{}: timeout waiting for reply to '{}'".format(self.port, line))
            return "OK POWER MODE OUTDOOR PIN 2026 ACCEPTED"
        return "OK " + line.split()[0]

    def query(self, line, prefixes=("OK", "ERR", "STAT", "ID"), timeout=15.0):
        self.log.append(line)
        if line == "ID?":
            if self.id_reply is None:
                raise RuntimeError(
                    "{}: timeout waiting for reply to 'ID?'".format(self.port))
            return self.id_reply
        return "OK"

    def stat(self):
        return ("STAT role=TX sent=99999 sent_ok=99999 rx=0 crc_err=0 "
                "per_x1e6=0 elapsed_s=1.0 kbps=64 rssi_avg_dbm=0.0 "
                "snr_avg_db=0.0 drops=0")


# ---------------------------------------------------------------------------
# 1. PREFLIGHT at banner time — ID? reply required, pcap= when pa>10
# ---------------------------------------------------------------------------

class IdPreflightTests(unittest.TestCase):
    """id_preflight() unit behavior (no run-mode wiring)."""

    def test_requires_id_reply(self):
        board = RangeBoard("/dev/ttyUSB3", id_reply=None)
        with self.assertRaises(RuntimeError) as cm:
            m.id_preflight(board, PRESET_HI_PA["configs"], board.port)
        msg = str(cm.exception)
        self.assertIn("PREFLIGHT", msg)
        self.assertIn("ID?", msg)

    def test_requires_pcap_when_preset_has_pa_above_10(self):
        board = RangeBoard("/dev/ttyUSB3", id_reply=ID_WITHOUT_PCAP)
        with self.assertRaises(RuntimeError) as cm:
            m.id_preflight(board, PRESET_HI_PA["configs"], board.port)
        msg = str(cm.exception)
        self.assertIn("PREFLIGHT", msg)
        self.assertIn("pcap=", msg)

    def test_ok_with_pcap_when_pa_above_10(self):
        board = RangeBoard("/dev/ttyUSB3", id_reply=ID_WITH_PCAP)
        reply = m.id_preflight(board, PRESET_HI_PA["configs"], board.port)
        self.assertEqual(reply, ID_WITH_PCAP)

    def test_ok_without_pcap_when_pa_lte_10(self):
        board = RangeBoard("/dev/ttyUSB3", id_reply=ID_WITHOUT_PCAP)
        reply = m.id_preflight(board, PRESET_LO_PA["configs"], board.port)
        self.assertEqual(reply, ID_WITHOUT_PCAP)

    def test_short_timeout_budget(self):
        """The fail-fast budget is seconds, not the 15 s console default."""
        board = RangeBoard("/dev/ttyUSB3", id_reply=None)
        seen = {}

        def query(line, prefixes=("OK", "ERR", "STAT", "ID"), timeout=15.0):
            seen["timeout"] = timeout
            raise RuntimeError("timeout")

        board.query = query
        with self.assertRaises(RuntimeError):
            m.id_preflight(board, PRESET_LO_PA["configs"], board.port)
        self.assertLessEqual(seen["timeout"], 10.0)


class RunTxModePreflightTests(unittest.TestCase):
    """run_tx_mode() runs the ID? preflight before any countdown/launch."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.tx_log = os.path.join(self.dir.name, "tx-log.csv")

    def tearDown(self):
        self.dir.cleanup()

    def _run(self, board, args=None, clock=None):
        clock = clock or FakeClock(time.time())
        board.clock = clock
        board.ser = FakeSer(clock)
        args = args or make_range_args(
            configs=PRESET_LO_PA, tx_log=self.tx_log)
        made = []

        def board_cls(port):
            b = board
            b.port = port
            made.append(port)
            return b

        buf = io.StringIO()
        with mock.patch.object(m.time, "time", clock.time), \
             mock.patch.object(m.time, "sleep", clock.sleep), \
             contextlib.redirect_stdout(buf):
            m.run_tx_mode(args, board_cls=board_cls)
        return made, buf.getvalue()

    def test_wedged_console_fails_fast_before_any_launch(self):
        board = RangeBoard("/dev/ttyUSB3", id_reply=None)
        with self.assertRaises(RuntimeError) as cm:
            self._run(board)
        self.assertIn("PREFLIGHT", str(cm.exception))
        # Nothing beyond ID? (and the pre-open STOP housekeeping) was sent —
        # no SESSION/CONFIG/MOD/ARM/START, i.e. no launch attempt at all.
        self.assertIn("ID?", board.log)
        for forbidden in ("SESSION", "CONFIG", "ARM TX", "START"):
            self.assertNotIn(forbidden, board.log,
                             "launch command sent despite preflight failure")

    def test_old_fw_without_pcap_fails_fast_with_hi_pa_preset(self):
        board = RangeBoard("/dev/ttyUSB3", id_reply=ID_WITHOUT_PCAP)
        args = make_range_args(configs=PRESET_HI_PA, tx_log=self.tx_log)
        with self.assertRaises(RuntimeError) as cm:
            self._run(board, args=args)
        self.assertIn("pcap=", str(cm.exception))
        self.assertNotIn("START", board.log)

    def test_happy_path_preflight_precedes_session_commands(self):
        board = RangeBoard("/dev/ttyUSB3", id_reply=ID_WITH_PCAP)
        clock = FakeClock(time.time())
        made, out = self._run(board, args=make_range_args(
            configs=PRESET_HI_PA, tx_log=self.tx_log), clock=clock)
        self.assertEqual(made, ["/dev/ttyUSB3"])
        self.assertIn("RANGE PREFLIGHT", out)
        self.assertIn("[PREFLIGHT]", out)
        self.assertLess(board.log.index("ID?"),
                        board.log.index("SESSION 2608282100"))
        # the run completed through the schedule (virtual clock)
        self.assertTrue(any(ln.startswith("START") for ln in board.log))
        self.assertTrue(os.path.exists(self.tx_log))


class RunRxModePreflightTests(unittest.TestCase):
    """run_rx_mode() runs the ID? preflight before any countdown/launch."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.rx_log = os.path.join(self.dir.name, "rx-log.csv")

    def tearDown(self):
        self.dir.cleanup()

    def _run(self, board, args=None):
        clock = FakeClock(time.time())
        board.clock = clock
        board.ser = FakeSer(clock)
        args = args or make_range_args(
            mode="rx", configs=PRESET_LO_PA, rx_log=self.rx_log)
        buf = io.StringIO()
        with mock.patch.object(m.time, "time", clock.time), \
             mock.patch.object(m.time, "sleep", clock.sleep), \
             contextlib.redirect_stdout(buf):
            m.run_rx_mode(args, board_cls=lambda port: board)
        return buf.getvalue()

    def test_wedged_console_fails_fast_before_any_launch(self):
        board = RangeBoard("/dev/ttyUSB4", id_reply=None)
        with self.assertRaises(RuntimeError) as cm:
            self._run(board)
        self.assertIn("PREFLIGHT", str(cm.exception))
        self.assertNotIn("START", board.log)
        self.assertNotIn("SESSION", board.log)

    def test_happy_path_preflight_precedes_session_commands(self):
        board = RangeBoard("/dev/ttyUSB4", id_reply=ID_WITH_PCAP)
        out = self._run(board, args=make_range_args(
            mode="rx", configs=PRESET_HI_PA, rx_log=self.rx_log))
        self.assertIn("RANGE PREFLIGHT", out)
        self.assertLess(board.log.index("ID?"),
                        board.log.index("SESSION 2608282100"))
        self.assertTrue(os.path.exists(self.rx_log))


class DryRunRehearsalTests(unittest.TestCase):
    """dry_run_preset() rehearses the launch-time guards in its output."""

    def _dry_run(self, preset):
        args = make_range_args(configs=preset, t0=str(T0_FUTURE))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            m.dry_run_preset(args)
        return buf.getvalue()

    def test_dry_run_shows_preflight_for_hi_pa(self):
        out = self._dry_run(PRESET_HI_PA)
        self.assertIn("PREFLIGHT", out)
        self.assertIn("pcap=", out)
        self.assertIn("ID?", out)

    def test_dry_run_shows_preflight_without_pcap_req_for_lo_pa(self):
        out = self._dry_run(PRESET_LO_PA)
        self.assertIn("PREFLIGHT", out)
        self.assertIn("ID?", out)
        self.assertNotIn("pcap= required", out)


# ---------------------------------------------------------------------------
# 2. T0-past guard: T0 < now+60s hard-errors at banner — no countdown/launch
# ---------------------------------------------------------------------------

class T0PastGuardTests(unittest.TestCase):
    """check_t0_future() pure behavior."""

    def test_rejects_t0_in_past(self):
        now = 1750000000
        ok, msg = m.check_t0_future(now - 64, now)
        self.assertFalse(ok)
        self.assertIn("T0 in past", msg)
        self.assertIn("recompute or pass explicit T0", msg)

    def test_rejects_t0_too_soon(self):
        # 30 s ahead is still inside the 60 s minimum lead — the countdown
        # must not start (incident (b): banner printed "T0 in -64s" and
        # still launched).
        now = 1750000000
        ok, msg = m.check_t0_future(now + 30, now)
        self.assertFalse(ok)
        self.assertIn("T0 in past", msg)

    def test_accepts_t0_with_enough_lead(self):
        now = 1750000000
        ok, msg = m.check_t0_future(now + 60, now)
        self.assertTrue(ok, msg)
        ok, _ = m.check_t0_future(now + 600, now)
        self.assertTrue(ok)


class RunModeT0GuardTests(unittest.TestCase):
    """run_tx_mode/run_rx_mode hard-error on past T0 before any launch."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.dir.cleanup()

    def _args(self, mode, log):
        kw = dict(configs=PRESET_LO_PA, t0=str(T0_PAST))
        if mode == "tx":
            kw["tx_log"] = log
        else:
            kw.update(mode="rx", rx_log=log)
        return make_range_args(**kw)

    def _assert_no_launch(self, board, made, log_path):
        self.assertEqual(made, [])          # board never opened
        self.assertEqual(board.log, [])
        self.assertFalse(os.path.exists(log_path))

    def test_tx_mode_t0_past_hard_errors_before_open(self):
        board = RangeBoard("/dev/ttyUSB3")
        made = []

        def board_cls(port):
            made.append(port)
            return board

        with self.assertRaises(SystemExit) as cm:
            with contextlib.redirect_stdout(io.StringIO()):
                m.run_tx_mode(self._args("tx", os.path.join(self.dir.name, "t.csv")),
                              board_cls=board_cls)
        self.assertIn("T0 in past", str(cm.exception))
        self.assertIn("recompute or pass explicit T0", str(cm.exception))
        self._assert_no_launch(board, made, os.path.join(self.dir.name, "t.csv"))

    def test_rx_mode_t0_past_hard_errors_before_open(self):
        board = RangeBoard("/dev/ttyUSB4")
        made = []

        def board_cls(port):
            made.append(port)
            return board

        with self.assertRaises(SystemExit) as cm:
            with contextlib.redirect_stdout(io.StringIO()):
                m.run_rx_mode(self._args("rx", os.path.join(self.dir.name, "r.csv")),
                              board_cls=board_cls)
        self.assertIn("T0 in past", str(cm.exception))
        self._assert_no_launch(board, made, os.path.join(self.dir.name, "r.csv"))


class MainT0GuardCLITests(unittest.TestCase):
    """CLI-level: --mode tx with a past T0 exits non-zero with the message."""

    def test_cli_t0_past_exits_with_message(self):
        import subprocess
        r = subprocess.run(
            [sys.executable, os.path.join(TOOLS_DIR, "e80_bench_ctl.py"),
             "--mode", "tx", "--t0", str(T0_PAST),
             "--session-id", "2608282100",
             "--configs", os.path.join(os.path.dirname(TOOLS_DIR),
                                       "..", "..", "configs",
                                       "envelope-4cfg-max.json")],
            capture_output=True, text=True, cwd=TOOLS_DIR, timeout=60)
        self.assertNotEqual(r.returncode, 0)
        combined = r.stdout + r.stderr
        self.assertIn("T0 in past", combined)
        self.assertIn("recompute or pass explicit T0", combined)


class MakefileT0GuardTests(unittest.TestCase):
    """make range-tx/range-rx hard-error on a stale past T0= before countdown."""

    FWDIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _make(self, target):
        import subprocess
        return subprocess.run(["make", target, "T0=1000000000",
                               "SESSION_ID=2608282100"],
                              capture_output=True, text=True,
                              cwd=self.FWDIR, timeout=60)

    def test_range_tx_stale_t0_fails_before_launch(self):
        r = self._make("range-tx")
        self.assertNotEqual(r.returncode, 0)
        out = r.stdout + r.stderr
        self.assertIn("T0 in past", out)

    def test_range_rx_stale_t0_fails_before_launch(self):
        r = self._make("range-rx")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("T0 in past", r.stdout + r.stderr)


class DryRunT0GuardRehearsalTests(unittest.TestCase):
    def test_dry_run_shows_t0_guard(self):
        args = make_range_args(configs=PRESET_LO_PA, t0=str(T0_FUTURE))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            m.dry_run_preset(args)
        out = buf.getvalue()
        self.assertIn("T0 guard", out)
        self.assertIn("60", out)
        # dry-run itself must NOT hard-error on a near/past T0 (no launch)
        args2 = make_range_args(configs=PRESET_LO_PA, t0=str(T0_PAST))
        buf2 = io.StringIO()
        with contextlib.redirect_stdout(buf2):
            self.assertEqual(m.dry_run_preset(args2), 0)


# ---------------------------------------------------------------------------
# 3. Session collision guard: existing logs/s<SESSION>-t0<OTHER>/ with
#    OTHER != T0 hard-errors at startup, naming BOTH dirs.
# ---------------------------------------------------------------------------

class FindSessionCollisionsTests(unittest.TestCase):
    """find_session_collisions() pure behavior (tempdir logs root)."""

    SESSION = 2608282100

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = self.dir.name

    def tearDown(self):
        self.dir.cleanup()

    def _mk(self, name):
        os.makedirs(os.path.join(self.root, name), exist_ok=True)
        return name

    def test_detects_existing_dir_with_different_t0(self):
        old = self._mk("s{}-t0{}".format(self.SESSION, T0_PAST))
        coll = m.find_session_collisions(self.SESSION, T0_FUTURE,
                                         logs_root=self.root)
        self.assertEqual(len(coll), 1)
        self.assertEqual(coll[0][0], old)
        self.assertEqual(coll[0][1], T0_PAST)

    def test_same_t0_is_not_a_collision(self):
        self._mk("s{}-t0{}".format(self.SESSION, T0_FUTURE))
        coll = m.find_session_collisions(self.SESSION, T0_FUTURE,
                                         logs_root=self.root)
        self.assertEqual(coll, [])

    def test_different_session_is_ignored(self):
        self._mk("s{}-t0{}".format(self.SESSION + 1, T0_PAST))
        coll = m.find_session_collisions(self.SESSION, T0_FUTURE,
                                         logs_root=self.root)
        self.assertEqual(coll, [])

    def test_missing_logs_root_is_empty(self):
        coll = m.find_session_collisions(
            self.SESSION, T0_FUTURE,
            logs_root=os.path.join(self.root, "nope"))
        self.assertEqual(coll, [])

    def test_non_digit_t0_suffix_ignored(self):
        self._mk("s{}-t0abc".format(self.SESSION))
        self._mk("s{}-t0{}-junk".format(self.SESSION, T0_PAST))
        coll = m.find_session_collisions(self.SESSION, T0_FUTURE,
                                         logs_root=self.root)
        self.assertEqual(coll, [])

    def test_multiple_collisions_all_reported(self):
        a = self._mk("s{}-t0{}".format(self.SESSION, T0_PAST))
        b = self._mk("s{}-t0{}".format(self.SESSION, T0_PAST - 999))
        coll = m.find_session_collisions(self.SESSION, T0_FUTURE,
                                         logs_root=self.root)
        self.assertEqual(sorted(c[0] for c in coll), sorted([a, b]))


class DefaultLogsRootTests(unittest.TestCase):

    def test_absolute_path_ending_in_logs(self):
        root = m.default_logs_root()
        self.assertTrue(os.path.isabs(root))
        self.assertEqual(os.path.basename(root), "logs")

    def test_matches_resolve_log_path_parent(self):
        # default_logs_root() must be exactly where resolve_log_path()
        # puts session dirs — otherwise the guard scans the wrong place.
        session, t0 = 2608282100, 1750000000
        p = m.resolve_log_path("tx-log.csv", True, session, t0, "tx")
        self.assertEqual(
            m.default_logs_root(),
            os.path.dirname(os.path.dirname(p)))
        # and the session dir it builds sits under default_logs_root()
        self.assertTrue(p.startswith(m.default_logs_root() + os.sep))


class MainSessionCollisionGuardTests(unittest.TestCase):
    """main() hard-errors before makedirs when the session id is already
    on disk with a different t0 — naming BOTH dirs."""

    SESSION = 2608282100
    OTHER_T0 = T0_PAST

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.old_dir = "s{}-t0{}".format(self.SESSION, self.OTHER_T0)
        os.makedirs(os.path.join(self.dir.name, self.old_dir))
        self.configs = os.path.join(E80_DIR, "..", "..", "configs",
                                    "envelope-4cfg-max.json")

    def tearDown(self):
        self.dir.cleanup()

    def _main(self, t0):
        argv = ["e80_bench_ctl.py", "--mode", "tx",
                "--configs", self.configs,
                "--session-id", str(self.SESSION),
                "--t0", str(t0),
                "--port", "/dev/ttyUSB9"]
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.object(m, "default_logs_root",
                               return_value=self.dir.name), \
             contextlib.redirect_stdout(io.StringIO()) as out, \
             contextlib.redirect_stderr(io.StringIO()) as err:
            m.main()
        return out.getvalue(), err.getvalue()

    def test_collision_hard_errors_naming_both_dirs(self):
        with self.assertRaises(SystemExit) as cm:
            self._main(T0_FUTURE)
        self.assertNotEqual(cm.exception.code, 0)
        msg = str(cm.exception)
        self.assertIn("session collision", msg)
        self.assertIn(self.old_dir, msg)                      # existing dir
        self.assertIn("s{}-t0{}".format(self.SESSION, T0_FUTURE), msg)  # new dir
        self.assertIn("--session-id", msg)

    def test_matching_t0_passes_the_guard(self):
        # same session + same t0 (e.g. RX joining a TX already on disk) is
        # the normal distributed flow — must NOT trip the guard. Route into
        # dry-run so no hardware is touched after the guard passes.
        argv = ["e80_bench_ctl.py", "--mode", "tx",
                "--configs", self.configs,
                "--session-id", str(self.SESSION),
                "--t0", str(self.OTHER_T0), "--dry-run"]
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.object(m, "default_logs_root",
                               return_value=self.dir.name), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(m.main(), 0)


class DryRunSessionCollisionRehearsalTests(unittest.TestCase):

    SESSION = 2608282100

    def test_dry_run_rehearses_the_guard(self):
        args = make_range_args(configs=PRESET_LO_PA, t0=str(T0_FUTURE))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            m.dry_run_preset(args)
        out = buf.getvalue()
        self.assertIn("Session guard", out)
        self.assertIn("--session-id", out)

    def test_dry_run_warns_but_exits_0_on_real_collision(self):
        with tempfile.TemporaryDirectory() as root:
            old = "s{}-t0{}".format(self.SESSION, T0_PAST)
            os.makedirs(os.path.join(root, old))
            args = make_range_args(configs=PRESET_LO_PA, t0=str(T0_FUTURE))
            buf = io.StringIO()
            with mock.patch.object(m, "default_logs_root",
                                   return_value=root), \
                 contextlib.redirect_stdout(buf):
                rc = m.dry_run_preset(args)
            self.assertEqual(rc, 0)
            self.assertIn("WARNING", buf.getvalue())
            self.assertIn(old, buf.getvalue())


if __name__ == "__main__":
    unittest.main()
