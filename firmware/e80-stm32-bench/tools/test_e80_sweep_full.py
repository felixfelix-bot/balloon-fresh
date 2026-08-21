#!/usr/bin/env python3
"""Host tests for e80_sweep_full.py — task FIX-T1 (TDD: written RED first).

Covers three behaviors from docs/rca-fix-plan-20260821.md BUG 1:
  1. run_config() validates the START reply: anything not starting with
     'OK START' (e.g. firmware 'ERR LEN (MAX 255 LORA / 511 FLRC)') must be
     written into the row's error= field and returned IMMEDIATELY — no
     drain_lines() burst wait (the old ~90 s stall on a refused config).
  2. build_configs() never emits a LoRa row with plen > 255 (firmware cap:
     255 B in LoRa, 511 B only in FLRC).
  3. build_configs() has an FLRC LEN sweep section @ BR650 pa5 868 MHz
     covering plen 16..511 (L511 is legal in FLRC).

No serial hardware needed: module IO (swd_reset/cmd/readline/drain_lines)
is monkeypatched with a firmware-model fake.

Run:  python3 -m unittest test_e80_sweep_full -v   (from tools/)
      python3 tools/test_e80_sweep_full.py
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import e80_sweep_full as m  # noqa: E402


class FakeSer:
    """Minimal pyserial stand-in for run_config's tx/rx board objects."""

    def __init__(self, name):
        self.name = name
        self.port = "/dev/fake-" + name
        self.written = []

    def write(self, b):
        self.written.append(bytes(b))

    def reset_input_buffer(self):
        pass

    def read(self, n=1):
        return b""

    def close(self):
        pass


def fake_cmd(ser, line, timeout=5.0):
    """Firmware reply model for every console line run_config() sends."""
    if line == "ID?":
        return "ID E80BENCH v1.0 fw=test123 role=TX chip=2.1"
    if line.startswith("SESSION") or line.startswith("CONFIG"):
        return "OK"
    if line.startswith("MOD"):
        return "OK MOD"
    if line.startswith("PA"):
        return "OK PA"
    if line.startswith("FREQ"):
        return "OK FREQ"
    if line == "ROLE RX":
        return "OK ROLE RX"
    if line == "ROLE TX":
        return "OK ROLE TX"
    if line == "ARM TX":
        return "OK ARMED"
    if line == "STAT?":
        return "STAT role=RX sent=0 sent_ok=0 rx=0 crc_err=0 per_x1e6=0"
    raise AssertionError("FakeBoard: unhandled console line {!r}".format(line))


def run_config_scripted(start_reply, tx_lines, rx_lines):
    """run_config() against fakes; returns (result, drain_calls, tx_ser)."""
    tx, rx = FakeSer("tx"), FakeSer("rx")
    drain_calls = []

    def fake_drain(ser, seconds):
        drain_calls.append((ser.name, seconds))
        return list(tx_lines if ser.name == "tx" else rx_lines)

    def fake_readline(ser, timeout=3.0):
        return start_reply

    with mock.patch.object(m, "swd_reset", lambda probe: None), \
         mock.patch.object(m, "cmd", fake_cmd), \
         mock.patch.object(m, "readline", fake_readline), \
         mock.patch.object(m, "drain_lines", fake_drain):
        cfg = dict(mod="flrc", br=650, pa=5, freq=868000000,
                   plen=511, gap=10000, label="FLRC 650k pa5 L511")
        r = m.run_config(3, cfg, tx, rx, 2608, "/dev/a", "/dev/b")
    return r, drain_calls, tx


class StartReplyValidationTests(unittest.TestCase):
    """FIX-T1 #1: START reply must be validated; ERR fails fast."""

    def test_err_len_reply_fails_fast_no_stall(self):
        r, drain_calls, tx = run_config_scripted(
            "ERR LEN (MAX 255 LORA / 511 FLRC)", tx_lines=[], rx_lines=[])
        # error text lands in the row (SUMMARY 'error' column)
        self.assertIn("ERR LEN", r.get("error", ""), r)
        self.assertIn("ERR LEN", r.get("start_reply", ""), r)
        # returned immediately: NO burst wait was started
        self.assertEqual(drain_calls, [], "drain_lines must not run on ERR")
        self.assertFalse(r["tx_done"])
        self.assertEqual(r["rx_pkts"], 0)
        self.assertEqual(r["pkts"], [])
        # row still carries the config identity for the CSV
        self.assertEqual(r["idx"], 3)
        self.assertEqual(r["plen"], 511)
        self.assertEqual(r["label"], "FLRC 650k pa5 L511")
        # START was actually sent to the TX board
        self.assertTrue(any(b.startswith(b"START ") for b in tx.written), tx.written)

    def test_none_reply_fails_fast(self):
        r, drain_calls, _ = run_config_scripted(None, tx_lines=[], rx_lines=[])
        self.assertTrue(r.get("error"), "no-reply must set error text")
        self.assertEqual(drain_calls, [], "drain_lines must not run on no reply")

    def test_other_err_reply_fails_fast(self):
        r, drain_calls, _ = run_config_scripted(
            "ERR NOT ARMED (SEND 'ARM TX')", tx_lines=[], rx_lines=[])
        self.assertIn("ERR NOT ARMED", r.get("error", ""), r)
        self.assertEqual(drain_calls, [])

    def test_ok_start_reply_still_runs_burst(self):
        # Happy path guard: valid reply must NOT be rejected.
        r, drain_calls, _ = run_config_scripted(
            "OK START n=50 len=511 gap_us=10000 src=PRBS",
            tx_lines=["OK START n=50 len=511 gap_us=10000 src=PRBS", "TX DONE"],
            rx_lines=[])
        self.assertEqual(r.get("error", ""), r)
        self.assertTrue(r["tx_done"], r)
        self.assertTrue(drain_calls, "burst wait must run on OK START")


class BuildConfigsTests(unittest.TestCase):
    """FIX-T1 #2/#3: LoRa LEN capped at 255; FLRC LEN section 16..511."""

    def test_no_lora_row_exceeds_255(self):
        bad = [(c["label"], c["plen"]) for c in m.build_configs()
               if c["mod"] == "lora" and c["plen"] > 255]
        self.assertEqual(bad, [], "LoRa rows over the 255 B fw cap: %r" % bad)

    def test_flrc_len_section_covers_16_to_511(self):
        rows = [c for c in m.build_configs()
                if c["mod"] == "flrc" and c["br"] == 650 and c["pa"] == 5]
        lens = sorted({c["plen"] for c in rows})
        self.assertEqual(lens, [16, 64, 128, 255, 511], rows)
        self.assertTrue(all(c["freq"] == 868000000 for c in rows), rows)

    def test_flrc_l511_row_exists(self):
        row = [c for c in m.build_configs()
               if c["mod"] == "flrc" and c["plen"] == 511]
        self.assertEqual(len(row), 1, row)
        self.assertIn("L511", row[0]["label"])

    def test_lora_len_section_still_covers_legal_lengths(self):
        # Capping must not remove legal rows: 16/128/255 (64 is in the matrix).
        lens = {c["plen"] for c in m.build_configs()
                if c["mod"] == "lora" and c.get("sf") == 8
                and c["bw"] == 125 and c["pa"] == 10
                and c["label"].startswith("SF8 BW125 PA10 L")}
        self.assertTrue({16, 128, 255} <= lens, lens)

    def test_summary_error_is_last_column(self):
        # The error= column the fail-fast path writes into must exist.
        self.assertEqual(m.SUMMARY_FIELDS[-1], "error")


if __name__ == "__main__":
    unittest.main(verbosity=2)
