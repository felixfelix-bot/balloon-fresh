#!/usr/bin/env python3
"""Host tests for tools/balloon_sweep.py — cross-family sweep tool (HARM-T2).

Pure host-side replay of golden console transcripts per
docs/BENCH-CONSOLE-SPEC.md v1.0. NO serial hardware required.

Golden transcript provenance (tests/golden/):

  e80-flrc-session.txt
      PKT lines are byte-exact output of the REAL E80 firmware formatter
      (firmware/e80-stm32-bench/src/bench_pkt.c @ buf/t5a-rx-pcrc16,
      host-compiled), with field values from the recorded sweep
      full-sweep-pkts-20260821-175612.csv (session 2608211756).
      OK*/CONFIG_START/TX-stat reply strings are byte-exact per the
      firmware console_put sequences in src/bench.c; the trailing STAT
      line follows the current bench.c STAT shape (incl. session=/cr=
      echo) with illustrative counters.
  e80-lora-24col.txt
      VERBATIM real recorded lines from docs/E80-PRBS-VERIFY-2026-08-20.md
      (24-column PKT rows + real boot-banner ID, fw 17a6417, no buf= key).
  e80-stat-recorded.txt
      VERBATIM firmware-recorded STAT lines from the e80_bench_ctl test
      suite constants FW_TX/FW_RX (10k-packet session, older STAT shape).
  crossboard-ids.txt
      Spec §2.1-format ID? replies for ESP32BENCH / RP2040BENCH (boards
      land with HARM-T4/T5) + a full-key E80BENCH line.

Run:  python3 -m pytest tools/test_balloon_sweep.py -q
"""
import csv
import importlib
import io
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GOLDEN = os.path.join(ROOT, "tests", "golden")
E80_TOOLS = os.path.join(ROOT, "firmware", "e80-stm32-bench", "tools")

sys.path.insert(0, HERE)

import balloon_sweep as bs  # noqa: E402


def golden_lines(name):
    with open(os.path.join(GOLDEN, name), encoding="utf-8") as f:
        return [ln.rstrip("\n") for ln in f if ln.strip()]


def replay_file(name):
    return bs.replay(golden_lines(name))


class Pkt25ColRealFormatterTests(unittest.TestCase):
    """Spec §3: 25-column PKT rows incl. pcrc16 (field 24), real lines."""

    def test_three_good_rows_parse(self):
        r = replay_file("e80-flrc-session.txt")
        self.assertIsNotNone(r)
        pkts = [p for p in r["pkts"] if p["crc_ok"] == 1]
        self.assertEqual(len(pkts), 3)
        p0, p1, p511 = pkts
        self.assertEqual(p0["session"], 2608211756)
        self.assertEqual(p0["config"], 0)
        self.assertEqual(p0["replicate"], 1)
        self.assertEqual(p0["idx"], 0)          # TX seq -> pkt_idx
        self.assertEqual(p0["ts_ms"], 3299)
        self.assertAlmostEqual(p0["rssi"], -71.0)
        self.assertEqual(p0["mod"], "FLRC")
        self.assertEqual(p0["pa"], 5)
        self.assertEqual(p0["pkt_len"], 16)
        self.assertEqual(p0["pcrc16"], 44973)   # real CRC-16/CCITT-FALSE
        self.assertEqual(p1["pcrc16"], 60110)
        self.assertEqual(p511["config"], 1)
        self.assertEqual(p511["pkt_len"], 511)
        self.assertEqual(p511["pcrc16"], 7686)

    def test_crc_fail_row_zero_pcrc16(self):
        """Spec §3: CRC-fail row keeps seq=0 len=0 pcrc16=0, RSSI live."""
        r = replay_file("e80-flrc-session.txt")
        bad = [p for p in r["pkts"] if p["crc_ok"] == 0]
        self.assertEqual(len(bad), 1)
        b = bad[0]
        self.assertEqual(b["idx"], 0)
        self.assertEqual(b["pkt_len"], 0)
        self.assertEqual(b["pcrc16"], 0)
        self.assertAlmostEqual(b["rssi"], -71.0)


class Pkt24ColToleranceTests(unittest.TestCase):
    """Spec §3: hosts accept 24-col rows (pcrc16 absent)."""

    def test_real_24col_rows_parse(self):
        r = replay_file("e80-lora-24col.txt")
        pkts = r["pkts"]
        self.assertEqual(len(pkts), 2)
        p0 = pkts[0]
        self.assertEqual(p0["idx"], 55)
        self.assertEqual(p0["ts_ms"], 65505)
        self.assertAlmostEqual(p0["rssi"], -37.0)
        self.assertAlmostEqual(p0["snr"], 15.0)
        self.assertEqual(p0["mod"], "LORA")
        self.assertEqual(p0["sf"], 8)
        self.assertEqual(p0["bw"], 125)
        self.assertEqual(p0["pkt_len"], 64)
        self.assertIsNone(p0["pcrc16"])      # 24-col: no pcrc16 field

    def test_legacy_id_line_without_buf(self):
        """Real recorded boot ID (older fw): no buf= key, still parses."""
        d = bs.parse_id_line(
            "ID E80BENCH v1.2 fw=17a6417 role=NONE armed=0 mod=lora sf=8 "
            "bw=125000 freq=868000000 band=863-870MHz pa=10 pcap=+10dBm "
            "chip=1.24 radio=asleep boot=jump-ok")
        self.assertIsNotNone(d)
        self.assertEqual(d["tag"], "E80BENCH")
        self.assertEqual(d["version"], "v1.2")
        self.assertEqual(d["fw"], "17a6417")
        self.assertEqual(d["role"], "NONE")
        self.assertEqual(d["armed"], 0)
        self.assertEqual(d["mod"], "lora")
        self.assertEqual(d["sf"], 8)
        self.assertEqual(d["bw"], 125000)
        self.assertEqual(d["freq"], 868000000)
        self.assertEqual(d["band"], "863-870MHz")
        self.assertEqual(d["pa"], 10)
        self.assertEqual(d["pcap"], "+10dBm")
        self.assertEqual(d["chip"], "1.24")
        self.assertEqual(d["radio"], "asleep")
        self.assertIsNone(d.get("buf"))


class StatParseTests(unittest.TestCase):
    """Spec §2.10 STAT — both recorded (old) and current shapes."""

    def test_recorded_rx_line(self):
        r = replay_file("e80-stat-recorded.txt")
        stats = r["stats"]
        self.assertEqual(len(stats), 2)
        rx = stats[1]
        self.assertEqual(rx["role"], "RX")
        self.assertEqual(rx["sent"], 0)
        self.assertEqual(rx["rx"], 9970)
        self.assertEqual(rx["crc_err"], 3)
        self.assertEqual(rx["per_x1e6"], 3000)
        self.assertEqual(rx["per_ci_lo_x1e6"], 19000)
        self.assertEqual(rx["per_ci_hi_x1e6"], 33000)
        self.assertAlmostEqual(rx["elapsed_s"], 42.5)
        self.assertAlmostEqual(rx["rssi_avg_dbm"], -87.5)
        self.assertAlmostEqual(rx["snr_avg_db"], 9.8)
        self.assertEqual(rx["drops"], 0)

    def test_recorded_tx_line(self):
        d = bs.parse_stat(
            "STAT role=TX sent=10000 sent_ok=10000 rx=0 crc_err=0 "
            "per_x1e6=0 elapsed_s=82.4 kbps=210 rssi_avg_dbm=0.0 "
            "snr_avg_db=0.0 drops=0")
        self.assertEqual(d["role"], "TX")
        self.assertEqual(d["sent"], 10000)
        self.assertEqual(d["sent_ok"], 10000)
        self.assertEqual(d["recv"], 0)

    def test_current_shape_session_echo(self):
        """Current bench.c STAT: session/config/replicate/cr/gap_us/buf."""
        r = replay_file("e80-flrc-session.txt")
        self.assertTrue(r["stats"])
        s = r["stats"][-1]
        self.assertEqual(s["role"], "RX")
        self.assertEqual(s["session"], 2608211756)
        self.assertEqual(s["config"], 1)
        self.assertEqual(s["replicate"], 1)
        self.assertEqual(s["cr"], 1)
        self.assertEqual(s["gap_us"], 0)
        self.assertEqual(s["buf"], 0)


class UnknownLinesIgnoredTests(unittest.TestCase):
    """Spec §1: hosts MUST ignore unrecognized lines (forward compat)."""

    def test_noise_does_not_break_replay(self):
        lines = golden_lines("e80-flrc-session.txt")
        noisy = lines + [
            "NOTE: some future firmware annotation",
            "DBG reg=0x1e whatever",
            "",
            "ID E80BENCH v1.2 fw=88a00cf role=RX armed=0 mod=flrc br=650000",
        ]
        r = bs.replay(noisy)
        self.assertEqual(len(r["pkts"]), 4)
        # parsers are individually None-safe on garbage
        self.assertIsNone(bs.parse_pkt("PKT,1,2"))
        self.assertIsNone(bs.parse_pkt("NKT,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18"))
        self.assertIsNone(bs.parse_id_line("OK ROLE RX (CONTINUOUS)"))
        self.assertEqual(bs.parse_stat("STAT"), {})


class IdHandshakeAutoDetectTests(unittest.TestCase):
    """Spec §2.1/§10: ID? reply -> board tag -> family (auto-detect)."""

    def test_all_three_tags(self):
        for line in golden_lines("crossboard-ids.txt"):
            d = bs.parse_id_line(line)
            self.assertIsNotNone(d, line)
            fam = bs.detect_family(line)
            self.assertIn(fam, ("e80", "esp32", "rp2040"), line)
            self.assertEqual(d["tag"], bs.DRIVERS[fam].tag)
            self.assertEqual(fam, bs.family_for_tag(d["tag"]))
        # flrc ID keys: br not sf/bw
        d = bs.parse_id_line(golden_lines("crossboard-ids.txt")[0])
        self.assertEqual(d["mod"], "flrc")
        self.assertEqual(d["br"], 650000)
        self.assertEqual(d["freq"], 868000000)
        self.assertEqual(d["buf"], 4096)


class FreqPlanTests(unittest.TestCase):
    """Spec §9: per-board frequency plan + intersection for pairs."""

    def test_per_board_bands(self):
        self.assertTrue(bs.freq_ok("E80BENCH", 868000000))
        self.assertTrue(bs.freq_ok("E80BENCH", 863000000))
        self.assertTrue(bs.freq_ok("E80BENCH", 870000000))
        self.assertFalse(bs.freq_ok("E80BENCH", 872000000))
        self.assertFalse(bs.freq_ok("E80BENCH", 2440000000))   # no 2G4
        self.assertTrue(bs.freq_ok("ESP32BENCH", 868000000))
        self.assertTrue(bs.freq_ok("ESP32BENCH", 2400000000))
        self.assertTrue(bs.freq_ok("ESP32BENCH", 2480000000))
        self.assertFalse(bs.freq_ok("ESP32BENCH", 2483500000))
        self.assertFalse(bs.freq_ok("ESP32BENCH", 872000000))
        self.assertTrue(bs.freq_ok("RP2040BENCH", 868000000))
        self.assertTrue(bs.freq_ok("RP2040BENCH", 2440000000))  # point band
        self.assertFalse(bs.freq_ok("RP2040BENCH", 2450000000))
        self.assertFalse(bs.freq_ok("RP2040BENCH", 2480000000))
        self.assertFalse(bs.freq_ok("ESP32BENCH", 915000000))   # no US band

    def test_pair_intersection(self):
        self.assertTrue(bs.freq_pair_ok("E80BENCH", "ESP32BENCH", 868000000))
        self.assertFalse(bs.freq_pair_ok("E80BENCH", "RP2040BENCH", 2440000000))
        self.assertTrue(bs.freq_pair_ok("ESP32BENCH", "RP2040BENCH", 2440000000))
        self.assertFalse(bs.freq_pair_ok("ESP32BENCH", "RP2040BENCH", 2480000000))
        self.assertFalse(bs.freq_pair_ok("E80BENCH", "ESP32BENCH", 915000000))


class LenCapAndGapTests(unittest.TestCase):
    """Spec §6 LEN caps + §7 GAP>=40ms for LEN>256 (host-side enforcement)."""

    def test_len_caps(self):
        errs = bs.validate_config(
            dict(mod="lora", plen=300, gap=40000, freq=868000000),
            "E80BENCH", "E80BENCH")
        self.assertTrue(any("LEN" in e for e in errs))
        errs = bs.validate_config(
            dict(mod="flrc", plen=512, gap=40000, freq=868000000),
            "E80BENCH", "E80BENCH")
        self.assertTrue(any("LEN" in e for e in errs))
        self.assertEqual(bs.validate_config(
            dict(mod="lora", plen=255, gap=10000, freq=868000000),
            "E80BENCH", "E80BENCH"), [])
        self.assertEqual(bs.validate_config(
            dict(mod="flrc", plen=511, gap=40000, freq=868000000),
            "E80BENCH", "E80BENCH"), [])

    def test_gap_rule(self):
        errs = bs.validate_config(
            dict(mod="flrc", plen=511, gap=39000, freq=868000000),
            "E80BENCH", "E80BENCH")
        self.assertTrue(any("GAP" in e for e in errs))
        self.assertEqual(bs.validate_config(
            dict(mod="flrc", plen=511, gap=40000, freq=868000000),
            "E80BENCH", "E80BENCH"), [])
        self.assertEqual(bs.validate_config(
            dict(mod="flrc", plen=256, gap=10000, freq=868000000),
            "E80BENCH", "E80BENCH"), [])   # 256 is NOT >256
        errs = bs.validate_config(
            dict(mod="flrc", plen=300, gap=10000, freq=868000000),
            "E80BENCH", "E80BENCH")
        self.assertTrue(any("GAP" in e for e in errs))

    def test_freq_validated_against_both_boards(self):
        errs = bs.validate_config(
            dict(mod="flrc", plen=16, gap=10000, freq=2440000000),
            "E80BENCH", "RP2040BENCH")
        self.assertTrue(any("FREQ" in e for e in errs))


class PairPlannerTests(unittest.TestCase):
    """Cross-board pair planner: refuse bad pairs BEFORE hardware."""

    def test_refuses_non_intersecting_pair(self):
        cfgs = [dict(mod="flrc", plen=16, gap=10000, freq=2440000000,
                     label="bad")]
        with self.assertRaises(bs.ConfigError) as cm:
            bs.plan_pairs("e80", "rp2040", configs=cfgs, session_id=2608211756)
        self.assertIn("FREQ", str(cm.exception))

    def test_refuses_len_and_gap_violations(self):
        cfgs = [dict(mod="lora", plen=300, gap=40000, freq=868000000,
                     label="too-long")]
        with self.assertRaises(bs.ConfigError):
            bs.plan_pairs("e80", "esp32", configs=cfgs, session_id=1)

    def test_valid_cross_board_pair_same_session(self):
        cfgs = [dict(mod="flrc", plen=16, gap=10000, freq=868000000,
                     label="ok")]
        plan = bs.plan_pairs("e80", "esp32", configs=cfgs, session_id=2608211756)
        self.assertEqual(plan.tx_family, "e80")
        self.assertEqual(plan.rx_family, "esp32")
        self.assertEqual(plan.session_id, 2608211756)
        self.assertEqual(len(plan.configs), 1)
        # drivers resolve for both families
        self.assertEqual(bs.DRIVERS[plan.tx_family].tag, "E80BENCH")
        self.assertEqual(bs.DRIVERS[plan.rx_family].tag, "ESP32BENCH")

    def test_unknown_family_rejected(self):
        with self.assertRaises(bs.ConfigError):
            bs.plan_pairs("e80", "nope", session_id=1)

    def test_auto_session_id_shape(self):
        plan = bs.plan_pairs("e80", "e80", configs=[], session_id=None)
        sid = plan.session_id
        self.assertIsInstance(sid, int)
        self.assertEqual(len(str(sid)), 10)   # yymmddHHMM


class DriverSurfaceTests(unittest.TestCase):
    """BoardDriver surface: 3 families registered, tags per spec §10."""

    def test_registry(self):
        self.assertEqual(set(bs.DRIVERS), {"e80", "esp32", "rp2040"})
        tags = {d.tag for d in bs.DRIVERS.values()}
        self.assertEqual(tags, {"E80BENCH", "ESP32BENCH", "RP2040BENCH"})
        for fam, drv in bs.DRIVERS.items():
            self.assertEqual(drv.family, fam)
            for meth in ("detect_ports", "reset", "open"):
                self.assertTrue(callable(getattr(drv, meth)), (fam, meth))


class E80ParityTests(unittest.TestCase):
    """Matrices + CSV emission identical to e80_sweep_full (spec §11.6)."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, E80_TOOLS)
        cls.e80 = importlib.import_module("e80_sweep_full")

    def test_build_configs_identical(self):
        self.assertEqual(bs.build_configs(), self.e80.build_configs())

    def test_field_headers_identical(self):
        self.assertEqual(bs.SUMMARY_FIELDS, self.e80.SUMMARY_FIELDS)
        self.assertEqual(bs.PKT_FIELDS, self.e80.PKT_FIELDS)


class CsvJoinabilityTests(unittest.TestCase):
    """Golden replay -> CSV rows; join on (session, config, pkt_idx)."""

    def test_rows_join_with_stat_on_session_config(self):
        r = replay_file("e80-flrc-session.txt")
        rows = [bs.pkt_row({"idx": 0, "label": "FLRC 650k pa5 L16"}, p)
                for p in r["pkts"]]
        self.assertEqual(len(rows), 4)
        w = io.StringIO()
        wr = csv.writer(w)
        wr.writerow(bs.PKT_FIELDS)
        for row in rows:
            wr.writerow(row)
        rd = list(csv.reader(io.StringIO(w.getvalue())))
        self.assertEqual(rd[0], bs.PKT_FIELDS)
        body = rd[1:]
        # every PKT row joins to a known (session, config) block
        keys = {(int(r_[3]), int(r_[4])) for r_ in body}   # session, config
        self.assertTrue(keys <= {(2608211756, 0), (2608211756, 1)})
        # cross-board join key: STAT session == PKT session
        stat = r["stats"][-1]
        self.assertEqual(stat["session"], 2608211756)
        self.assertIn((stat["session"], stat["config"]), keys)
        # pkt_idx strictly increasing within a config block over OK rows
        # (spec S3: CRC-fail rows carry seq=0 and stay out of the sequence)
        seen = {}
        for r_ in body:
            key = (int(r_[3]), int(r_[4]))
            pkt_idx, crc_ok = int(r_[2]), int(r_[9])
            if crc_ok == 1:
                if key in seen:
                    self.assertGreater(pkt_idx, seen[key])
                seen[key] = pkt_idx
            else:
                self.assertEqual(pkt_idx, 0)   # spec S3: CRC-fail -> seq 0
        # row values round-trip: session/config/pkt_idx/ts/pcrc16 present
        first = dict(zip(bs.PKT_FIELDS, body[0]))
        self.assertEqual(first["session"], "2608211756")
        self.assertEqual(first["config"], "0")
        self.assertEqual(first["pkt_idx"], "0")
        self.assertEqual(first["pcrc16"], "44973")


class ConfigStartTests(unittest.TestCase):
    """CONFIG_START async marker parses (config, replicate, ts_ms)."""

    def test_parse(self):
        d = bs.parse_config_start("CONFIG_START,1,1,60100")
        self.assertEqual(d, {"config": 1, "replicate": 1, "ts_ms": 60100})
        r = replay_file("e80-flrc-session.txt")
        self.assertEqual(len(r["config_starts"]), 2)


if __name__ == "__main__":
    unittest.main()
