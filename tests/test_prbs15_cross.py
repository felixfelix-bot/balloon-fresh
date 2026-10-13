#!/usr/env/bin python3
"""
Cross-platform PRBS15 known-vector tests.

Reimplements the Galois LFSR PRBS15 algorithm from the C firmware
(~/repos/balloon-e80bench/firmware/e80-stm32-bench/src/prbs.c and
 ~/repos/balloon-fresh/mesh-stack/flrc-bench-espidf/main/prbs.cpp)
in pure Python and validates it against known test vectors.

Algorithm:
  - Polynomial: x^15 + x^14 + 1 (taps at bits 14 and 13)
  - Seed: state = (uint16_t)(seed ^ 0x5A5A) | 1
  - Left-shift LFSR, new_bit = (bit14 XOR bit13)
  - Mask: 0x7FFF (15-bit state)
  - MSB-first byte assembly
"""

import pytest


# ---------------------------------------------------------------------------
# Python reimplementation of the C PRBS15 algorithm
# ---------------------------------------------------------------------------

def prbs15_fill(length: int, seed: int) -> bytes:
    """Generate `length` bytes of PRBS15 pseudo-random data for the given seed.

    Exact port of the C prbs15_fill() function.
    """
    state = ((seed ^ 0x5A5A) & 0xFFFF) | 1
    result = bytearray(length)
    for i in range(length):
        byte_val = 0
        for _ in range(8):
            newbit = ((state >> 14) ^ (state >> 13)) & 1
            state = ((state << 1) | newbit) & 0x7FFF
            byte_val = ((byte_val << 1) | (newbit & 1)) & 0xFF
        result[i] = byte_val
    return bytes(result)


def prbs15_verify(buf: bytes, seed: int) -> tuple[int, int]:
    """Verify a buffer against the PRBS15 expected stream.

    Returns (bit_errors, bytes_bad) — exact port of the C prbs15_verify().
    """
    state = ((seed ^ 0x5A5A) & 0xFFFF) | 1
    bit_errors = 0
    bytes_bad = 0
    for i in range(len(buf)):
        expected = 0
        for _ in range(8):
            newbit = ((state >> 14) ^ (state >> 13)) & 1
            state = ((state << 1) | newbit) & 0x7FFF
            expected = ((expected << 1) | (newbit & 1)) & 0xFF
        diff = buf[i] ^ expected
        if diff:
            bytes_bad += 1
            bit_errors += bin(diff).count("1")  # __builtin_popcount equivalent
    return bit_errors, bytes_bad


# ---------------------------------------------------------------------------
# Known test vectors (computed from the algorithm above, verified against C)
# ---------------------------------------------------------------------------

# Seed 1: first 32 bytes
SEED1_32 = bytes([
    221, 216, 204, 210, 170, 239, 254, 96,
    5, 64, 31, 128, 65, 1, 134, 5,
    20, 30, 120, 69, 17, 158, 101, 69,
    95, 159, 193, 64, 135, 131, 17, 10,
])

# Seed 42: first 128 bytes
SEED42_128 = bytes([
    221, 36, 206, 218, 166, 223, 214, 192, 246, 130, 55, 12, 178, 43, 172, 249,
    234, 20, 124, 121, 9, 22, 54, 116, 181, 59, 190, 153, 135, 85, 19, 254,
    104, 5, 112, 31, 32, 66, 193, 142, 133, 39, 30, 210, 70, 237, 150, 109,
    117, 111, 63, 98, 131, 79, 11, 162, 57, 204, 148, 171, 123, 251, 24, 26,
    80, 93, 225, 204, 68, 169, 155, 245, 88, 63, 208, 128, 227, 2, 74, 13,
    188, 45, 136, 237, 50, 110, 173, 103, 239, 80, 99, 225, 72, 71, 177, 145,
    165, 101, 223, 92, 195, 202, 136, 191, 51, 130, 169, 15, 246, 32, 52, 192,
    186, 131, 159, 9, 66, 55, 140, 177, 43, 166, 249, 214, 20, 244, 122, 57,
])

# Seed 0xDEADBEEF: first 255 bytes
SEEDDB_255 = bytes([
    91, 191, 217, 128, 213, 2, 254, 14, 4, 36, 24, 216, 82, 209, 238, 228,
    102, 89, 85, 215, 252, 240, 10, 32, 60, 192, 138, 131, 63, 10, 130, 63,
    12, 130, 43, 12, 250, 42, 28, 252, 74, 9, 188, 53, 136, 189, 51, 142,
    169, 39, 246, 208, 54, 224, 182, 67, 181, 137, 189, 53, 142, 189, 39, 142,
    209, 38, 230, 214, 86, 245, 246, 60, 52, 136, 187, 51, 154, 169, 95, 247,
    192, 48, 128, 163, 3, 202, 8, 188, 51, 136, 169, 51, 246, 168, 55, 240,
    176, 35, 160, 201, 194, 180, 143, 187, 33, 154, 197, 94, 159, 199, 64, 147,
    131, 105, 11, 118, 59, 52, 154, 187, 95, 155, 193, 88, 135, 211, 16, 234,
    98, 125, 77, 15, 174, 33, 228, 196, 90, 153, 223, 84, 195, 250, 136, 31,
    48, 66, 161, 143, 197, 32, 158, 195, 70, 139, 151, 57, 114, 151, 47, 114,
    227, 46, 74, 229, 190, 93, 133, 205, 28, 174, 75, 229, 184, 93, 145, 205,
    100, 175, 91, 227, 216, 72, 209, 178, 229, 174, 93, 229, 204, 92, 169, 203,
    244, 184, 59, 144, 153, 99, 87, 75, 243, 184, 41, 144, 245, 98, 63, 76,
    131, 171, 9, 250, 52, 28, 184, 75, 145, 185, 101, 151, 93, 115, 207, 40,
    162, 243, 206, 40, 164, 243, 218, 40, 220, 242, 202, 46, 188, 231, 138, 81,
    61, 230, 140, 87, 41, 242, 244, 46, 56, 228, 146, 91, 109, 219, 108,
])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPRBS15Fill:
    """Tests for prbs15_fill known-pattern generation."""

    def test_prbs15_fill_known_pattern(self):
        """Verify first 32 bytes for seed=1 match the expected pattern."""
        result = prbs15_fill(32, 1)
        assert result == SEED1_32, (
            f"seed=1 first 32 bytes mismatch:\n"
            f"  expected: {list(SEED1_32)}\n"
            f"  got:      {list(result)}"
        )

    def test_prbs15_seed_42(self):
        """Verify first 128 bytes for seed=42 match the expected pattern."""
        result = prbs15_fill(128, 42)
        assert result == SEED42_128, (
            f"seed=42 first 128 bytes mismatch:\n"
            f"  expected: {list(SEED42_128)}\n"
            f"  got:      {list(result)}"
        )

    def test_prbs15_seed_deadbeef(self):
        """Verify first 255 bytes for seed=0xDEADBEEF match the expected pattern."""
        result = prbs15_fill(255, 0xDEADBEEF)
        assert result == SEEDDB_255, (
            f"seed=0xDEADBEEF first 255 bytes mismatch:\n"
            f"  expected: {list(SEEDDB_255)}\n"
            f"  got:      {list(result)}"
        )

    def test_prbs15_different_seeds_different_output(self):
        """seed=1 and seed=2 must produce different output streams."""
        out1 = prbs15_fill(64, 1)
        out2 = prbs15_fill(64, 2)
        assert out1 != out2, "seed=1 and seed=2 produced identical streams"

    def test_prbs15_seed_0_equals_seed_1(self):
        """seed=0 and seed=1 produce the same stream because (0^0x5A5A)|1 == (1^0x5A5A)|1."""
        # (0 ^ 0x5A5A) | 1 = 0x5A5B
        # (1 ^ 0x5A5A) | 1 = 0x5A5B  (same initial state)
        out0 = prbs15_fill(32, 0)
        out1 = prbs15_fill(32, 1)
        assert out0 == out1, "seed=0 should produce same stream as seed=1"


class TestPRBS15Verify:
    """Tests for prbs15_verify error detection."""

    def test_prbs15_verify_zero_errors(self):
        """Fill a buffer and verify it — should report 0 bit errors, 0 bad bytes."""
        buf = prbs15_fill(256, 1)
        bit_errors, bytes_bad = prbs15_verify(buf, 1)
        assert bit_errors == 0, f"Expected 0 bit errors, got {bit_errors}"
        assert bytes_bad == 0, f"Expected 0 bad bytes, got {bytes_bad}"

    def test_prbs15_verify_detects_errors(self):
        """Fill a buffer, flip some bits, verify detects them."""
        buf = bytearray(prbs15_fill(256, 42))
        # Flip bit 0 of byte 10 and bits 0,3 of byte 100
        buf[10] ^= 0x01
        buf[100] ^= 0x09
        bit_errors, bytes_bad = prbs15_verify(bytes(buf), 42)
        assert bit_errors == 3, f"Expected 3 bit errors, got {bit_errors}"
        assert bytes_bad == 2, f"Expected 2 bad bytes, got {bytes_bad}"

    def test_prbs15_verify_detects_single_bit_flip(self):
        """A single bit flip should produce exactly 1 bit error and 1 bad byte."""
        buf = bytearray(prbs15_fill(128, 0xDEADBEEF))
        buf[50] ^= 0x40  # flip bit 6
        bit_errors, bytes_bad = prbs15_verify(bytes(buf), 0xDEADBEEF)
        assert bit_errors == 1
        assert bytes_bad == 1

    def test_prbs15_verify_all_zeros(self):
        """An all-zero buffer should have many errors for any non-zero seed."""
        buf = bytes(64)
        bit_errors, bytes_bad = prbs15_verify(buf, 1)
        assert bit_errors > 0, "All-zero buffer should have bit errors"
        assert bytes_bad > 0, "All-zero buffer should have bad bytes"

    def test_prbs15_verify_wrong_seed(self):
        """Verifying with the wrong seed should detect errors."""
        buf = prbs15_fill(128, 1)
        bit_errors, bytes_bad = prbs15_verify(buf, 2)
        assert bit_errors > 0, "Wrong-seed verify should detect errors"
        assert bytes_bad > 0, "Wrong-seed verify should detect bad bytes"

    def test_prbs15_verify_empty_buffer(self):
        """Empty buffer should report 0 errors."""
        bit_errors, bytes_bad = prbs15_verify(b"", 1)
        assert bit_errors == 0
        assert bytes_bad == 0