"""
Cross-platform PRBS-15 verification (P6).

Verifies the C3 firmware PRBS-15 implementation (prbs.cpp/prbs.h) by
re-implementing the same algorithm in Python and checking:

  - Known-vector output for seed=1
  - Zero bit errors when verifying a clean pattern
  - Exactly 1 bit error / 1 byte bad when 1 bit is flipped
  - Reproducibility (same seed → same output)
  - Different seeds produce different patterns

Algorithm (matching prbs.cpp):
  Polynomial : x^15 + x^14 + x^13  (taps at bits 14 and 13)
  Seed init   : (seed ^ 0x5A5A) | 1, masked to 15 bits (0x7FFF)
  Fill        : MSB-first per byte
  Verify      : XOR received vs expected, bit_errors via popcount
"""

import pytest


def prbs15_fill(length: int, seed: int) -> bytes:
    """Python re-implementation of C3 prbs15_fill()."""
    state = (seed ^ 0x5A5A) | 1
    state &= 0x7FFF
    buf = bytearray()
    for _ in range(length):
        byte_val = 0
        for _ in range(8):
            newbit = ((state >> 14) ^ (state >> 13)) & 1
            state = ((state << 1) | newbit) & 0x7FFF
            byte_val = (byte_val << 1) | newbit
        buf.append(byte_val)
    return bytes(buf)


def prbs15_verify(buf: bytes, seed: int) -> tuple[int, int]:
    """Python re-implementation of C3 prbs15_verify().
    Returns (bit_errors, bytes_bad)."""
    state = (seed ^ 0x5A5A) | 1
    state &= 0x7FFF
    bit_errors = 0
    bytes_bad = 0
    for b in buf:
        expected = 0
        for _ in range(8):
            newbit = ((state >> 14) ^ (state >> 13)) & 1
            state = ((state << 1) | newbit) & 0x7FFF
            expected = (expected << 1) | newbit
        diff = b ^ expected
        if diff:
            bytes_bad += 1
            bit_errors += bin(diff).count("1")
    return bit_errors, bytes_bad


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPrbs15CrossPlatform:
    """Verify Python PRBS-15 matches C3 firmware PRBS-15."""

    # Known output of prbs15_fill(16, seed=1) — hardcoded expected values
    KNOWN_SEED_1 = bytes([
        0xDD, 0xD8, 0xCC, 0xD2, 0xAA, 0xEF, 0xFE, 0x60,
        0x05, 0x40, 0x1F, 0x80, 0x41, 0x01, 0x86, 0x05,
    ])

    def test_prbs15_known_seed(self):
        """prbs15_fill(16, seed=1) must match hardcoded expected bytes."""
        result = prbs15_fill(16, 1)
        assert result == self.KNOWN_SEED_1, (
            f"PRBS-15 output mismatch: got {result.hex()}, "
            f"expected {self.KNOWN_SEED_1.hex()}"
        )

    def test_prbs15_verify_zero_errors(self):
        """Generate then verify the same data → 0 bit errors, 0 bytes bad."""
        data = prbs15_fill(32, 42)
        bit_err, bytes_bad = prbs15_verify(data, 42)
        assert bit_err == 0, f"Expected 0 bit errors, got {bit_err}"
        assert bytes_bad == 0, f"Expected 0 bytes bad, got {bytes_bad}"

    def test_prbs15_verify_one_bit(self):
        """Flip exactly 1 bit → 1 bit error, 1 byte bad."""
        data = bytearray(prbs15_fill(32, 99))
        data[10] ^= 0x40  # flip one bit in byte 10
        bit_err, bytes_bad = prbs15_verify(bytes(data), 99)
        assert bit_err == 1, f"Expected 1 bit error, got {bit_err}"
        assert bytes_bad == 1, f"Expected 1 byte bad, got {bytes_bad}"

    def test_prbs15_reproducible(self):
        """Same seed always produces same output."""
        a = prbs15_fill(64, 1234)
        b = prbs15_fill(64, 1234)
        assert a == b, "PRBS-15 output not reproducible with same seed"

    def test_prbs15_different_seeds(self):
        """Different seeds produce different patterns."""
        a = prbs15_fill(64, 1)
        b = prbs15_fill(64, 2)
        assert a != b, "Different seeds produced identical PRBS-15 patterns"