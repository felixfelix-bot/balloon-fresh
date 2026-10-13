#!/usr/bin/env python3
"""Golden CRC-16/CCITT-FALSE vectors, Python side (task BUF-T1).

The SAME three vectors are pinned in the C host tests
(firmware/e80-stm32-bench/tests/test_buffer.c): C and Python must agree.
The host loader tool (computes the CRC for 'BUF LOAD <n> <crc16_hex>' before
streaming the payload) uses this exact algorithm.

Run:  python3 -m unittest test_crc16_golden -v     (from tools/)
      python3 tools/test_crc16_golden.py
"""

import unittest

# Golden constants - shared C <-> Python (do not change one side alone).
CRC_CHECK_123456789 = 0x29B1  # canonical check value of CRC-16/CCITT-FALSE
CRC_64_ZEROS = 0xD6DA
CRC_4096_INCREMENTING = 0x0F69
CRC_ABCD = 0xBFFA


def crc16_ccitt_false(data: bytes) -> int:
    """Bitwise CRC-16/CCITT-FALSE: poly 0x1021, init 0xFFFF, no reflection,
    no xor-out. Matches the firmware's ~40-byte implementation."""
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


class TestGoldenVectors(unittest.TestCase):
    def test_check_value(self):
        self.assertEqual(crc16_ccitt_false(b"123456789"), CRC_CHECK_123456789)

    def test_64_zero_bytes(self):
        self.assertEqual(crc16_ccitt_false(bytes(64)), CRC_64_ZEROS)

    def test_4096_incrementing_bytes(self):
        data = bytes(i & 0xFF for i in range(4096))
        self.assertEqual(crc16_ccitt_false(data), CRC_4096_INCREMENTING)

    def test_empty_input_is_init_value(self):
        self.assertEqual(crc16_ccitt_false(b""), 0xFFFF)

    def test_abcd(self):
        # Used by the console framing tests (tests/test_console_binary.c).
        self.assertEqual(crc16_ccitt_false(b"ABCD"), CRC_ABCD)

    def test_known_digest_is_stable(self):
        # Guard against accidental edits of the constants themselves.
        self.assertEqual(CRC_CHECK_123456789, 0x29B1)
        self.assertEqual(CRC_64_ZEROS, 0xD6DA)
        self.assertEqual(CRC_4096_INCREMENTING, 0x0F69)


if __name__ == "__main__":
    unittest.main(verbosity=2)
