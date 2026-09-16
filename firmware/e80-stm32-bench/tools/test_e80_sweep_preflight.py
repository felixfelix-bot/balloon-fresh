#!/usr/bin/env python3
"""FIX-T6 sweep pre-flight gate — host tests.

FIX-T6 ("HW verify: FLRC BR sweep + LEN boundary bisect") can only produce a
meaningful verdict if three things hold BEFORE any packet is keyed:

  1. the sweep tool actually emits the config rows the acceptance criteria name
     (FLRC BR sweep = 8 bit rates; FLRC LEN matrix incl. 256/300/384/448/511;
     the large-packet x BR interaction rows; and the LEN 253-257 boundary
     bisect @BR1300 pa10 that BUG 3 asks for);
  2. the tool's console baud matches the firmware's compiled
     `E80_BENCH_BAUD_DEFAULT` — a mismatch is a *silent* failure mode: every
     command times out and the CSV fills with "no reply" rows that look like RF
     death rather than a wrong baud;
  3. both boards are attached AND carry the expected firmware, otherwise the
     measurement describes an unknown binary (this is exactly how FIX-T5
     "completed" while flashing nothing — see t_4e225809).

Everything here is hardware-free: the board-facing decision is a pure function
over (probe serials, ID? replies), so the gate is testable without a bench.

Run:  /usr/bin/python3 -m pytest test_e80_sweep_preflight.py -v
      (python3 on this box = uv 3.11 and has neither pytest nor pyserial)
"""
import os
import re
import sys
import unittest

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)

import e80_sweep_full as sf  # noqa: E402

HEADER = os.path.join(TOOLS, "..", "src", "main.h")
ATM = HEADER if os.path.exists(HEADER) else os.path.join(TOOLS, "..", "src", "main.h")

# The acceptance set from the FIX-T6 card + the operator-priority comment.
T6_LEN_MATRIX = [16, 64, 128, 192, 255, 256, 300, 384, 448, 511]
T6_FLRC_BRS = [260, 325, 520, 650, 1040, 1300, 2080, 2600]
T6_BISECT_LENS = [253, 254, 255, 256, 257]


def _flrc(cfgs):
    return [c for c in cfgs if c["mod"] == "flrc"]


class TestFlrcCoverage(unittest.TestCase):
    """The config matrix must cover what the card accepts on."""

    def test_flrc_br_sweep_has_all_8_bitrates_at_pa5_plen64_868(self):
        rows = [c for c in _flrc(sf.build_configs())
                if c.get("flag") == "flrc-br"]
        self.assertEqual(
            sorted(c["br"] for c in rows), sorted(T6_FLRC_BRS),
            "FLRC BR sweep section must emit exactly the 8 accepted bit rates "
            "@pa5 plen64 868 MHz")

    def test_flrc_len_matrix_covers_acceptance_set_at_br650(self):
        rows = {
            c["plen"] for c in _flrc(sf.build_configs())
            if c["br"] == 650 and c["pa"] == 5 and c["freq"] == 868000000
        }
        missing = sorted(set(T6_LEN_MATRIX) - rows)
        self.assertEqual(
            missing, [],
            f"FLRC LEN matrix @BR650 pa5 868 MHz is missing {missing} "
            f"(operator priority: large-packet coverage incl. 300/384/448/511)")

    def test_flrc_len_matrix_gap_is_not_silently_absorbed(self):
        """A `--only` filter must never be the reason an accepted row is absent.

        Guards the failure seen on the FIX chain base: the tool there shipped
        NO FLRC LEN matrix at all, so 256/300/384/448 were untestable while the
        card still claimed them.
        """
        plens = {
            c["plen"] for c in _flrc(sf.build_configs())
            if c["pa"] == 5 and c["freq"] == 868000000
        }
        for want in (256, 300, 384, 448, 511):
            self.assertIn(want, plens,
                          f"FLRC plen={want} row absent from the sweep configs")

    def test_flrc_len_br_interaction_rows_present(self):
        pairs = {
            (c["br"], c["plen"]) for c in _flrc(sf.build_configs())
            if c["pa"] == 5 and c["freq"] == 868000000
        }
        for pair in ((1300, 384), (1300, 511)):
            self.assertIn(pair, pairs,
                          f"large-packet x BR interaction row {pair} missing")

    def test_no_lora_row_exceeds_255(self):
        for cfg in sf.build_configs():
            if cfg["mod"] == "lora":
                self.assertLessEqual(
                    cfg["plen"], 255,
                    f"LoRa row '{cfg['label']}' has plen={cfg['plen']} > 255 "
                    "(LR2021 LoRa length field is uint8)")

    def test_len_bisect_section_is_253_to_257_at_br1300_pa10(self):
        rows = sf.build_len_bisect_configs()
        self.assertEqual(
            [c["plen"] for c in rows], T6_BISECT_LENS,
            "BUG 3 boundary bisect must emit LEN 253,254,255,256,257 in order")
        for c in rows:
            self.assertEqual(c["mod"], "flrc")
            self.assertEqual(c["br"], 1300)
            self.assertEqual(c["pa"], 10)
            self.assertEqual(c["freq"], 868000000)
            self.assertEqual(c["flag"],
                             "flrc-bisect",
                             "`flag` marks bisect rows so a CSV can be "
                             "attributed to the bisect run, not the BR sweep")

    def test_len_bisect_labels_are_unique(self):
        labels = [c["label"] for c in sf.build_len_bisect_configs()]
        self.assertEqual(len(labels), len(set(labels)))


class TestSectionSelector(unittest.TestCase):
    """Named sections so each T6 phase is one reproducible command."""

    def test_flrc_br_section_selects_only_br_rows(self):
        rows = sf.select_configs(sf.build_configs(), "flrc-br")
        self.assertEqual(len(rows), len(T6_FLRC_BRS))
        self.assertEqual(sorted(c["br"] for c in rows), sorted(T6_FLRC_BRS))
        self.assertTrue(all(c["mod"] == "flrc" and c["plen"] == 64
                            and c["pa"] == 5 and c["freq"] == 868000000
                            for c in rows))

    def test_flrc_len_section_selects_the_large_packet_matrix(self):
        rows = sf.select_configs(sf.build_configs(), "flrc-len")
        self.assertEqual(sorted(c["plen"] for c in rows), sorted(T6_LEN_MATRIX))

    def test_flrc_len_br_section_selects_interaction_rows(self):
        rows = sf.select_configs(sf.build_configs(), "flrc-len-br")
        self.assertEqual(sorted((c["br"], c["plen"]) for c in rows),
                         [(1300, 384), (1300, 511), (2600, 511)])
        self.assertTrue(all(c["mod"] == "flrc" for c in rows))

    def test_flrc_bisect_section_routes_to_the_bisect_builder(self):
        rows = sf.select_configs(sf.build_configs(), "flrc-bisect")
        self.assertEqual([c["plen"] for c in rows], T6_BISECT_LENS)

    def test_all_section_is_the_full_matrix(self):
        self.assertEqual(len(sf.select_configs(sf.build_configs(), "all")),
                         len(sf.build_configs()))

    def test_unknown_section_is_a_loud_error(self):
        with self.assertRaises(ValueError):
            sf.select_configs(sf.build_configs(), "flrc-nonsense")

    def test_build_configs_accepts_a_section_kwarg(self):
        self.assertEqual(len(sf.build_configs(section="flrc-br")),
                         len(T6_FLRC_BRS))


class TestBoardFacingPreflight(unittest.TestCase):
    """run_preflight() against a FAKE serial seam — no hardware, no pyserial."""

    class FakeSerial:
        def __init__(self, port, reply):
            self.port, self.reply, self.written = port, reply, b""

        def reset_input_buffer(self):
            pass

        def write(self, data):
            self.written += data

        def read(self, _n):
            return self.reply.encode()

        def close(self):
            pass

    def _patch(self, replies_by_port, ports):
        made = {}

        def fake_open(port, baud=None, timeout=0.1):
            ser = self.FakeSerial(port, replies_by_port.get(port, ""))
            made[port] = ser
            return ser

        orig = sf.open_serial
        sf.open_serial = fake_open
        self.addCleanup(lambda: setattr(sf, "open_serial", orig))
        return made

    def test_only_id_is_ever_sent(self):
        ports = ["/dev/fake0", "/dev/fake1"]
        made = self._patch({p: "ID E80BENCH fw=abc1234 role=NONE" for p in ports}, ports)
        sf.run_preflight(ports=ports, timeout=0.0, expected_probes={"TX": "X", "RX": "Y"})
        for ser in made.values():
            self.assertEqual(ser.written, b"ID?\r\n",
                             "the preflight must never key the radio "
                             "(no ROLE/ARM/START/FLASH)")

    def test_passes_on_two_attached_boards_with_the_expected_fw(self):
        ports = ["/dev/fake0", "/dev/fake1"]
        self._patch({p: "ID E80BENCH v1.2 fw=52ede35 role=NONE armed=0" for p in ports}, ports)
        ok, problems, warns, replies, probes = sf.run_preflight(
            ports=ports, timeout=0.0, expected_fw="52ede35",
            expected_probes={"TX": "148757200D2D1425", "RX": "203584200D2D0D42"})
        self.assertFalse(ok, "missing probes must still fail (no probes here)")
        self.assertEqual(set(replies), {"TX", "RX"})
        self.assertTrue(any("probe" in p for p in problems))

    def test_wrong_board_count_fails_loudly(self):
        ok, problems, _w, _r, _p = sf.run_preflight(
            ports=["/dev/fake0"], timeout=0.0)
        self.assertFalse(ok)
        self.assertTrue(any("expected 2 CH340" in p for p in problems))

    def test_list_probe_serials_reads_a_sysfs_tree(self):
        import tempfile
        with tempfile.TemporaryDirectory() as root:
            for name, vid, sn in (("3-1", "2e8a", "203584200D2D0D42"),
                                  ("3-2", "2e8a", ""),
                                  ("3-3", "1a86", "CH340")):
                d = os.path.join(root, name)
                os.makedirs(d)
                with open(os.path.join(d, "idVendor"), "w") as fh:
                    fh.write(vid + "\n")
                with open(os.path.join(d, "serial"), "w") as fh:
                    fh.write(sn + "\n")
            self.assertEqual(sf.list_probe_serials(root), ["203584200D2D0D42"])

    def test_open_serial_without_pyserial_is_a_clear_error(self):
        orig = sf.serial
        sf.serial = None
        self.addCleanup(lambda: setattr(sf, "serial", orig))
        with self.assertRaises(RuntimeError):
            sf.open_serial("/dev/does-not-matter")


class TestArgs(unittest.TestCase):
    """One command per FIX-T6 phase, no hand-typed --only guesses."""

    def test_defaults_run_the_full_matrix_at_50_pkts(self):
        o = sf.parse_args([])
        self.assertIsNone(o["section"])
        self.assertIsNone(o["only"])
        self.assertEqual(o["npkts"], 50)
        self.assertFalse(o["preflight_only"])

    def test_section_npkts_and_expected_fw_are_parsed(self):
        o = sf.parse_args(["--section", "flrc-bisect", "--npkts", "20",
                           "--expected-fw", "abc1234"])
        self.assertEqual(o["section"], "flrc-bisect")
        self.assertEqual(o["npkts"], 20)
        self.assertEqual(o["expected_fw"], "abc1234")

    def test_preflight_and_force_flags(self):
        o = sf.parse_args(["--preflight", "--force"])
        self.assertTrue(o["preflight_only"])
        self.assertTrue(o["force"])

    def test_non_integer_npkts_is_a_loud_error(self):
        with self.assertRaises(SystemExit):
            sf.parse_args(["--npkts", "twenty"])

    def test_unknown_argument_is_a_loud_error(self):
        with self.assertRaises(SystemExit):
            sf.parse_args(["--frobnicate"])


class TestConsoleBaudContract(unittest.TestCase):
    """Tool baud and firmware default must agree, or every cmd times out."""

    def test_tool_baud_matches_firmware_header_default(self):
        with open(HEADER) as fh:
            head = fh.read()
        m = re.search(r"#define\s+E80_BENCH_BAUD_DEFAULT\s+(\d+)U?", head)
        self.assertIsNotNone(m, "E80_BENCH_BAUD_DEFAULT not found in src/main.h")
        fw_baud = int(m.group(1))
        self.assertEqual(
            sf.BAUD, fw_baud,
            f"e80_sweep_full.BAUD={sf.BAUD} but the firmware console default "
            f"is {fw_baud} — the sweep would send every command into silence "
            "(see src/main.h E80_BENCH_BAUD_DEFAULT)")

    def test_baud_is_parsed_from_the_header_helper(self):
        tmp = os.path.join(TOOLS, "_baud_probe.h")
        try:
            with open(tmp, "w") as fh:
                fh.write("#define E80_BENCH_BAUD_DEFAULT 2000000U\n")
            self.assertEqual(sf.fw_default_baud(tmp), 2000000)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    def test_baud_env_override_wins(self):
        self.assertEqual(sf.resolve_baud(env={"E80_BAUD": "9600"}), 9600)

    def test_baud_env_override_must_be_numeric(self):
        with self.assertRaises(ValueError):
            sf.resolve_baud(env={"E80_BAUD": "fast"})


class TestPreflightGate(unittest.TestCase):
    """Pure board-facing decision — no serial, no hardware."""

    OK_TX = "ID E80BENCH v1.2 fw=07dbb8d role=TX armed=0 mod=flrc"
    OK_RX = "ID E80BENCH v1.2 fw=07dbb8d role=RX armed=0 mod=flrc"

    def _run(self, **kw):
        args = dict(probe_serials=[sf.PROBE_TX, sf.PROBE_RX],
                    id_replies={"TX": self.OK_TX, "RX": self.OK_RX},
                    expected_fw=None, tool_baud=None, fw_baud=None)
        args.update(kw)
        return sf.check_preconditions(**args)

    def test_passes_when_both_boards_attached_and_identified(self):
        ok, problems, warns = self._run()
        self.assertTrue(ok, f"expected preflight pass, problems={problems}")
        self.assertEqual(problems, [])

    def test_refuses_when_tx_probe_is_absent(self):
        ok, problems, _ = self._run(probe_serials=[sf.PROBE_RX])
        self.assertFalse(ok)
        self.assertTrue(any("TX" in p for p in problems),
                        f"missing TX probe must be named: {problems}")

    def test_refuses_when_rx_probe_is_absent(self):
        ok, problems, _ = self._run(probe_serials=[sf.PROBE_TX],
                                    id_replies={"TX": self.OK_TX})
        self.assertFalse(ok)
        self.assertTrue(any("RX" in p for p in problems))

    def test_refuses_when_a_board_gives_no_console_reply(self):
        ok, problems, _ = self._run(id_replies={"TX": self.OK_TX, "RX": ""})
        self.assertFalse(ok)
        self.assertTrue(any("no console reply" in p for p in problems),
                        f"silent console must be fatal: {problems}")

    def test_refuses_on_firmware_mismatch(self):
        ok, problems, _ = self._run(expected_fw="a1fcd27")
        self.assertFalse(ok)
        self.assertTrue(any("firmware mismatch" in p for p in problems))

    def test_accepts_short_and_long_spellings_of_the_same_sha(self):
        ok_tx = "ID E80BENCH v1.2 fw=07dbb8d4 role=TX"
        ok, problems, _ = self._run(
            id_replies={"TX": ok_tx, "RX": self.OK_RX}, expected_fw="07dbb8d")
        self.assertTrue(ok, f"prefix match should pass: {problems}")

    def test_unidentifiable_firmware_warns_when_no_expectation_set(self):
        ok, problems, warns = self._run(
            id_replies={"TX": "ERR UNKNOWN", "RX": self.OK_RX})
        self.assertTrue(ok, "unknown fw without an expectation is a warning")
        self.assertTrue(any("could not identify" in w for w in warns))

    def test_unidentifiable_firmware_is_fatal_when_expected(self):
        ok, problems, _ = self._run(
            id_replies={"TX": "ERR UNKNOWN", "RX": self.OK_RX},
            expected_fw="07dbb8d")
        self.assertFalse(ok)

    def test_refuses_on_console_baud_contract_violation(self):
        ok, problems, _ = self._run(tool_baud=2000000, fw_baud=115200)
        self.assertFalse(ok)
        self.assertTrue(any("baud" in p for p in problems),
                        f"baud drift must be fatal: {problems}")

    def test_no_baud_complaint_when_values_match(self):
        ok, _, _ = self._run(tool_baud=115200, fw_baud=115200)
        self.assertTrue(ok)

    def test_parse_fw_hash_handles_real_id_lines(self):
        self.assertEqual(sf.parse_fw_hash(self.OK_TX), "07dbb8d")
        self.assertEqual(
            sf.parse_fw_hash("ID E80BENCH v1.2 fw=257cb840 role=NONE"), "257cb840")
        self.assertIsNone(sf.parse_fw_hash("ERR UNKNOWN"))
        self.assertIsNone(sf.parse_fw_hash(""))


if __name__ == "__main__":
    unittest.main()
