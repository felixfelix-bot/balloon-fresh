# E80 STM32 Bench Firmware

LoRa/FLRC benchmark firmware for the STM32-based E80 rig.

> **📋 [E80 Range Test Operator Guide](docs/RANGE-TEST-GUIDE.md)** —
> complete self-contained guide for running distributed range tests
> (hardware setup, flashing, TX/RX, data merging, GPS stitching,
> troubleshooting). Start here if you're new to the E80 bench.

## PRBS15 BER Test Pattern

The E80 bench firmware uses **PRBS15** (Pseudo-Random Bit Sequence, degree 15) as
the common BER (Bit Error Rate) test pattern. This implementation is ported from
and cross-compatible with the C3 (ESP32-C3) reference implementation in the
`balloon-fresh` repository.

### Algorithm

**Polynomial:** x^15 + x^14 + 1 (Galois LFSR, taps at bits 14 and 13)

**LFSR direction:** Left-shift. On each step, the new bit is computed as:

```
newbit = (state >> 14) XOR (state >> 13)
state  = ((state << 1) | newbit) & 0x7FFF   (15-bit mask)
```

**Byte assembly:** MSB-first. Each byte is assembled from 8 consecutive LFSR
output bits, most-significant bit first.

### Seed Derivation

The LFSR state is seeded from the packet sequence number:

```c
uint16_t state = (uint16_t)(seq ^ 0x5A5A) | 1;
```

The XOR with `0x5A5A` provides per-packet decorrelation, and the `| 1` ensures
the state is never zero (which would stall a Galois LFSR).

### Payload Format

Each bench payload consists of:

| Offset | Size | Field |
|--------|------|-------|
| 0 | 4 bytes | Sequence number, big-endian |
| 4 | N-4 bytes | PRBS15 pseudo-random fill |

The 4-byte big-endian sequence header is C3-compatible and allows the receiver
to extract the sequence number, regenerate the expected PRBS15 stream, and
verify payload integrity.

### API

#### `prbs15_fill(uint8_t *buf, size_t len, uint32_t seed)`

Generates `len` bytes of pseudo-random data into `buf`, seeded by the given
sequence number. Uses the Galois LFSR described above.

#### `prbs15_verify(const uint8_t *buf, size_t len, uint32_t seed, uint16_t *out_bytes_bad)`

Regenerates the expected PRBS15 stream from `seed`, XORs it with the received
buffer, and counts:

- **Bit errors:** total number of differing bits, computed via `__builtin_popcount()`
  on each XOR diff byte.
- **Corrupted bytes:** number of bytes with at least one bit error.

Returns `bit_errors` (uint16_t). If `out_bytes_bad` is non-NULL, writes the
corrupted-byte count to it.

### PKT Output

The bench `PKT` output line now includes real BER measurements:

| Field | Index | Description |
|-------|-------|-------------|
| `bit_err` | 9 | Total bit errors (from PRBS15 verify) |
| `bytes_bad` | 10 | Number of corrupted bytes |

Previously these fields were hardcoded to 0. They now reflect actual PRBS15
verification results.

### Cross-Rig Compatibility

The E80 (STM32) PRBS15 implementation is identical to the C3 (ESP32-C3)
reference implementation in `balloon-fresh/mesh-stack/flrc-bench-espidf/`.
Both use the same polynomial, seed derivation, LFSR direction, and byte
assembly, enabling direct cross-platform BER comparison.

Cross-platform verification: `tests/test_prbs15_cross.py` (11 tests) validates
the algorithm against known test vectors in pure Python.

### Flash Impact

| Metric | Value |
|--------|-------|
| PRBS15 code size | ~300 bytes |
| Total `.text` section | 24,328 bytes |
| Flash budget (limit) | 35,840 bytes |
| Utilization | 67.9% |

The PRBS15 implementation adds minimal flash overhead, well within the
firmware size budget.