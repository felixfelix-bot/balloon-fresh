#!/usr/bin/env python3
"""Host tests for lr2021_bw_codes.py — BW-1 single-source BW table parser.

The parser reads firmware/rp2040/src/lr2021_bw_codes.h (the X-macro
LR2021_BW_TABLE) at runtime, so firmware and host scripts literally share one
source of truth. These tests pin that table against the ground truth
extracted from the vendored Semtech lr20xx_driver (read-only):

  ~/repos/balloon-e80bench/firmware/e80-stm32-bench/third_party/Radio/
    lr20xx_driver/inc/lr20xx_radio_lora_types.h   L93-111 (enum wire codes)
    lr20xx_driver/src/lr20xx_radio_lora.c         L485-542 (get_bw_in_hz)

Run:  python3 -m pytest tools/test_lr2021_bw_codes.py -q
      python3 -m unittest tools.test_lr2021_bw_codes -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lr2021_bw_codes as m  # noqa: E402


# Ground truth copied verbatim from vendored lr20xx_driver, ordered by code.
GROUND_TRUTH = [
    # (code, hz, khz_label)
    (0x00, 7812, 7),      # BW_7    7.8125 kHz
    (0x01, 15625, 15),    # BW_15   15.625 kHz
    (0x02, 31250, 31),    # BW_31   31.25 kHz
    (0x03, 62500, 62),    # BW_62   62.5 kHz
    (0x04, 125000, 125),  # BW_125
    (0x05, 250000, 250),  # BW_250
    (0x06, 500000, 500),  # BW_500
    (0x07, 1000000, 1000),  # BW_1000
    (0x08, 10417, 10),    # BW_10   10.417 kHz
    (0x09, 20833, 20),    # BW_20   20.833 kHz
    (0x0A, 41667, 41),    # BW_41   41.67 kHz
    (0x0B, 83340, 83),    # BW_83   83.34 kHz
    (0x0C, 101563, 101),  # BW_101  101.5625 kHz
    (0x0D, 203000, 203),  # BW_203
    (0x0E, 406000, 406),  # BW_406
    (0x0F, 812000, 812),  # BW_812
]


class TableIntegrityTests(unittest.TestCase):
    def test_header_exists_and_parses(self):
        rows = m.load_bw_table()
        self.assertGreater(len(rows), 0)

    def test_sixteen_unique_contiguous_codes(self):
        codes = sorted(r.code for r in m.load_bw_table())
        self.assertEqual(codes, list(range(16)))  # 0x00..0x0F exactly

    def test_hz_unique_nonzero(self):
        hzs = [r.hz for r in m.load_bw_table()]
        self.assertEqual(len(set(hzs)), len(hzs))
        self.assertTrue(all(hz > 0 for hz in hzs))


class GroundTruthTests(unittest.TestCase):
    """Every row must equal the vendored Semtech lr20xx_driver values."""

    def test_all_rows_match_driver(self):
        rows = {(r.code, r.hz, r.khz_label) for r in m.load_bw_table()}
        for code, hz, khz in GROUND_TRUTH:
            self.assertIn((code, hz, khz), rows,
                          f"missing/incorrect row for code {code:#04x}")

    def test_bench_critical_rows(self):
        # LF path (868 MHz): 125/250 kHz. HF path (2.4 GHz): 812 kHz wide-BW.
        self.assertEqual(m.code_to_hz(0x04), 125000)
        self.assertEqual(m.code_to_hz(0x05), 250000)
        self.assertEqual(m.code_to_hz(0x0F), 812000)
        self.assertEqual(m.khz_to_code(812), 0x0F)
        self.assertEqual(m.khz_to_code(250), 0x05)


class MappingTests(unittest.TestCase):
    def test_roundtrip_khz_code_hz(self):
        for r in m.load_bw_table():
            self.assertEqual(m.khz_to_code(r.khz_label), r.code)
            self.assertEqual(m.code_to_hz(r.code), r.hz)
            self.assertEqual(m.hz_to_code(r.hz), r.code)

    def test_invalid_code(self):
        self.assertEqual(m.code_to_hz(0x10), None)
        self.assertEqual(m.code_to_hz(0xFF), None)
        self.assertEqual(m.code_to_hz(256), None)

    def test_invalid_hz(self):
        self.assertEqual(m.hz_to_code(0), None)
        self.assertEqual(m.hz_to_code(124000), None)   # near-miss must miss
        self.assertEqual(m.hz_to_code(203125), None)   # datasheet nominal ≠ driver Hz
        self.assertEqual(m.hz_to_code(8_000_000), None)

    def test_invalid_khz_label(self):
        self.assertEqual(m.khz_to_code(0), None)
        self.assertEqual(m.khz_to_code(300), None)
        self.assertEqual(m.khz_to_code(600), None)


if __name__ == "__main__":
    unittest.main()
