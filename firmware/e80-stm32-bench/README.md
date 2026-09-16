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

## Bench Protocol Limits & Radio Notes

Reference notes for the packet-length limits, the FLRC RX match mode, the
FLRC SNR convention, the `pcrc16` field and the two `drops=` counters.
Everything below is grounded in this tree — `src/` and
`third_party/Radio/lr20xx_driver/` — with the source location cited for each
claim. Corrections/expansions belong in the same commit as the code they
describe (this section is a Gate-3 deliverable, not a scratch pad).

### Payload length: LoRa 255 B (hard), FLRC 511 B (legal)

| Modulation | Max payload | Where the ceiling comes from |
|---|---|---|
| LoRa | **255 B** | `pld_len_in_bytes` is a **`uint8_t`** in the LR20xx driver — `third_party/Radio/lr20xx_driver/inc/lr20xx_radio_lora_types.h:247` |
| FLRC | **511 B** | `pld_len_in_bytes` is a **`uint16_t`** documented as range `[6:511]` — `third_party/Radio/lr20xx_driver/inc/lr20xx_radio_flrc_types.h:210` |

LoRa's 255 B is therefore the **silicon/driver** ceiling, not a bench policy:
`LEN=511` in LoRa is not "slow", it is unrepresentable in the packet-params
struct. FLRC has no wall at 256 B — 511 B is a legal FLRC frame and is the
payload the throughput work targets.

Both boards answer an over-cap `START` with the same ERR string and refuse
before keying the radio — the TX gate is on `main` (`src/bench.c:786-790`);
the identical RX-side gate (shared predicate + shared string) is on branch
`fix/t2-rx-start-len-gate` (69dfd17):

```
ERR LEN (MAX 255 LORA / 511 FLRC)
```

Host tooling must apply the same per-modulation cap **before** it sends
`START`. A host that reads and ignores the ERR reply converts an invalid
config into a long silent stall that looks exactly like RF death.

### FLRC RX match mode is Match123 (`MATCH_SYNCWORD_1_OR_2_OR_3`)

The FLRC RX match mode must stay
`LR20XX_RADIO_FLRC_RX_MATCH_SYNCWORD_1_OR_2_OR_3` ("Match123"). With a 32-bit
sync word, Match1 (`RX_MATCH_SYNCWORD_1`) leaks sync bytes into the payload:
packets still demodulate, but the chip CRC fails 100 % of the time — the
failure signature that made FLRC look dead while LoRa on the same rig worked.

Both independent references for this configuration use Match123:

- the RadioLib LR2021 module, and
- `balloon-range-tests` commit `9b740aa` (raw FLRC config byte `0x7C`; its
  Match1 predecessor `0x4C` produced the same failure family).

Do not "simplify" this field back to Match1, and do not drop the golden-byte
host tests that pin the FLRC `SetPacketParams` wire bytes — opcode `0x0249`,
6 bytes, with `byte[3] = crc_type | header_type<<2 | match_sync_word<<3 |
tx_syncword<<6`, so Match123 with CRC on is `0x7D` and the range-tests raw
config `0x7C` is that same frame with CRC off. Those tests
(`tests/test_radio_bench_cfg.c`) currently live on branch
`fix/t3-flrc-match123` (a1fcd27) and are not on `main` yet; keep them in
whatever lands the Match123 change, so a silent regression in the packet
params fails a host test instead of a field run.

### SNR is 0.0 in FLRC — by design

The LR2021 provides no FLRC SNR estimate. The bench reports **0.0** rather
than a stale or invented number (`src/radio_bench.c` — both the IRQ path and
the poll path comment it as "FLRC has no SNR estimate"), and the host decodes
`snr_db = snr_qdb / 4` (`src/bench_pkt.c`). A `snr_db = 0.0` row in an FLRC
capture is expected data, not a measurement failure: judge FLRC link quality
on RSSI, `crc_ok` and the PRBS15 `bit_err`. Only LoRa rows carry a real SNR.

### `pcrc16` semantics

`pcrc16` is the trailing field of the `PKT` line and is the
**CRC-16/CCITT-FALSE over the received payload bytes**
(`src/bench.c` RX path; format contract in `src/bench_pkt.h`). It is **0**
when the chip CRC failed, because no payload is read on a CRC failure.

Two consequences for analysis:

- a row with `crc_ok=0` carries `pcrc16=0` and therefore no payload
  information — filter on `crc_ok` before treating `pcrc16` as evidence;
- `pcrc16` is an **application-layer** check stacked on the radio CRC, so it
  is the integrity path if the chip CRC is ever disabled
  (`crc_type = CRC_OFF`) and integrity is carried by the app layer instead
  (payload CRC + PRBS15 `bit_err`).

### Watching `drops=`

Two different counters are both printed as `drops=`, each an absolute count
since boot:

| Command | Counter | Meaning |
|---|---|---|
| `STAT` | `radio_bench_evt_drops()` | Radio **event-mailbox** overwrites — the superloop did not consume an event before the next arrived. |
| `BUF STATUS` | `buf_drops()` | RX **buffer** drops while staging a loaded frame. |

Check `STAT drops=` on every measured run: a nonzero value means the firmware
missed a radio event and that run's PER / `bit_err` numbers are not
trustworthy. Console pressure is worst at the largest payload (511 B on a
115200-baud console), so a `LEN=511` row reporting `drops>0` should be re-run
with the inter-packet gap doubled and **both** runs recorded.