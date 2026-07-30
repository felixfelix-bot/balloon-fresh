# E-Hash Relay Binary Encoding Specification

**Status:** Phase A (ADR-025) — Proposed
**Date:** 2026-07-29
**Related:** [ADR-025](../../docs/adr/025-e-hash-relay-transport-layer.md), [SPEC.md §4](SPEC.md) (Fragmentation Layer)

## 1. Overview

This specification defines the binary wire encoding for the four e-hash relay
L7 message types introduced in ADR-025 §1:

| Message Type      | Opcode | Direction          | Delivery    | Typical Size |
|-------------------|--------|--------------------|-------------|--------------|
| `EHASH_TEMPLATE`  | 0x10   | Downlink (proxy → balloon → miner) | Broadcast | 55–823 B  |
| `EHASH_NONCE`     | 0x11   | Uplink (miner → balloon → proxy)   | Unicast   | 21 B (fixed) |
| `EHASH_RESULT`    | 0x12   | Downlink (proxy → balloon → miner) | Unicast   | 7 B (fixed)  |
| `EHASH_CREDIT`    | 0x13   | Downlink (proxy → balloon → miner) | Unicast   | 16 B (fixed) |

These messages ride the existing L3–L6 stack (fragmentation → FIPS encryption →
TDMA scheduling → LR2021 radio). **No changes to L1–L6.**

### 1.1 Byte Order

- All multi-byte integer fields are encoded **little-endian** (matching the
  ESP32-C3 native byte order and SPEC.md §4.2 CRC convention).
- Hash fields (`prevhash`, `merkle_branch` hashes) are **opaque 32-byte blobs**
  stored in the raw internal byte order received from the stratum proxy. The
  proxy is responsible for any hex-display ↔ binary byte-order conversion.

### 1.2 L7 Envelope

Each L7 message is wrapped in a 1-byte type tag before being passed to the L3
fragmentation layer:

```
+--------+-----------------------+
| type   | payload (N bytes)     |
| (1 B)  | (message-specific)    |
+--------+-----------------------+
```

The `type` byte carries the opcode (0x10–0x13). The L7 dispatcher reads this
byte to select the decoder, then passes the remaining payload (starting at
offset 0 = protocol version for TEMPLATE/NONCE) to the type-specific decode
function. The **entire** envelope (type + payload) is treated as a single blob
by L3 fragmentation.

---

## 2. EHASH_TEMPLATE (0x10) — Binary Block Template

**Direction:** Downlink (broadcast to all ground stations).
**Purpose:** Binary-packed stratum `mining.notify` fields.

### 2.1 Field Layout

| Offset         | Size     | Type     | Field                  | Description                              |
|----------------|----------|----------|------------------------|------------------------------------------|
| 0              | 1        | uint8    | `version`              | Protocol version (always `0x01`)         |
| 1              | 4        | uint32   | `job_id`               | Job ID assigned by e-hash proxy          |
| 5              | 32       | uint8[32]| `prevhash`             | Previous block header hash (raw bytes)   |
| 37             | 4        | uint32   | `btc_version`          | Bitcoin block version field              |
| 41             | 4        | uint32   | `nbits`                | Difficulty target (encoded compact form) |
| 45             | 4        | uint32   | `ntime`                | BTC network time (`0` = use current time)|
| 49             | 2        | uint16   | `coinbase1_len`        | Length of `coinbase1` (`N`)              |
| 51             | N        | uint8[N] | `coinbase1`            | Coinbase transaction part 1 (~20–40 B)   |
| 51+N           | 2        | uint16   | `coinbase2_len`        | Length of `coinbase2` (`M`)              |
| 53+N           | M        | uint8[M] | `coinbase2`            | Coinbase transaction part 2 (~20–40 B)   |
| 53+N+M         | 1        | uint8    | `merkle_branch_count`  | Number of merkle hashes (`K`)            |
| 54+N+M         | 32×K     | uint8[]  | `merkle_branches`      | `K` merkle branch hashes, 32 B each      |
| 54+N+M+32K     | 1        | uint8    | `clean_jobs`           | Boolean: `1` = flush old jobs, `0` = append |

**Total payload size:** `55 + N + M + 32·K` bytes
(where `55` = 1+4+32+4+4+4+2+2+1+1 = all fixed fields including the two
length fields and `merkle_branch_count`/`clean_jobs`).

### 2.2 Size Analysis

| Scenario                         | N  | M  | K  | Payload | + type | Fragments |
|----------------------------------|----|----|----|---------|--------|-----------|
| Minimal (empty coinbase, K=0)    | 0  | 0  | 0  | 55 B    | 56 B   | 1         |
| Typical small pool (K=2)         | 20 | 20 | 2  | 155 B   | 156 B  | 1         |
| ADR estimate (~120–200 B)        | 30 | 30 | 3  | 211 B   | 212 B  | 1         |
| Medium pool (K=8)                | 30 | 30 | 8  | 371 B   | 372 B  | 2         |
| Large pool (K=12)                | 40 | 40 | 12 | 511 B   | 512 B  | 3         |
| Maximum (N=M=128, K=16)          | 128| 128| 16 | 823 B   | 824 B  | 4         |

> **ADR-025 §Payload Size Fit** states templates are "~120–200 bytes, fits in
> 1–2 fragments." This holds for pools with ≤4 merkle branches and typical
> coinbase sizes. Larger pools require 2–4 fragments — still well within the
> L3 ceiling (~15 KB).

---

## 3. EHASH_NONCE (0x11) — Binary Nonce Submission

**Direction:** Uplink (ground station → balloon → e-hash proxy).
**Purpose:** Binary-packed stratum `mining.submit` fields.
**Size:** 21 bytes (fixed).

### 3.1 Field Layout

| Offset | Size | Type   | Field        | Description                                    |
|--------|------|--------|--------------|------------------------------------------------|
| 0      | 1    | uint8  | `version`    | Protocol version (always `0x01`)               |
| 1      | 4    | uint32 | `job_id`     | Job ID (must match a received TEMPLATE)        |
| 5      | 4    | uint32 | `worker_id`  | Ground station ID (uint16 station ID, zero-padded to 4 B) |
| 9      | 4    | uint32 | `extranonce2`| Ground-assigned extranonce2 value              |
| 13     | 4    | uint32 | `ntime`      | nTime field used by the miner                  |
| 17     | 4    | uint32 | `nonce`      | The nonce found by the ASIC                    |

**Total payload size:** 21 bytes.

> The `worker_id` field occupies 4 bytes on the wire but carries a uint16
> station ID (range 0–65535). The upper 2 bytes are zero-padded. This padding
> permits future expansion to a 32-bit identifier without breaking the format.

---

## 4. EHASH_RESULT (0x12) — Share Accepted/Rejected

**Direction:** Downlink (e-hash proxy → balloon → ground station).
**Purpose:** Response to a nonce submission — whether the share was accepted by the pool.
**Size:** 7 bytes (fixed).

### 4.1 Field Layout

| Offset | Size | Type   | Field        | Description                                    |
|--------|------|--------|--------------|------------------------------------------------|
| 0      | 4    | uint32 | `job_id`     | Job ID this result refers to                   |
| 4      | 1    | uint8  | `accepted`   | Boolean: `1` = share accepted, `0` = rejected  |
| 5      | 2    | uint16 | `error_code` | Stratum error code (`0` = no error)            |

**Total payload size:** 7 bytes.

### 4.2 Error Codes

Standard stratum V1 error codes are used:

| Code | Meaning                        |
|------|--------------------------------|
| 0    | No error (accepted or other reason) |
| 21   | Job not found                  |
| 22   | Duplicate share                |
| 23   | Low difficulty share           |
| 24   | Unauthorized worker            |
| 25   | Not subscribed                 |

---

## 5. EHASH_CREDIT (0x13) — Credit Balance Update

**Direction:** Downlink (e-hash proxy → balloon → ground station).
**Purpose:** Notify the ground station of its current e-hash (Ecash) balance and reward rate.
**Size:** 16 bytes (fixed).

### 5.1 Field Layout

| Offset | Size | Type   | Field              | Description                                       |
|--------|------|--------|--------------------|---------------------------------------------------|
| 0      | 4    | uint32 | `station_id`       | Ground station ID (matches `worker_id` in NONCE)  |
| 4      | 8    | uint64 | `balance`          | Current e-hash token balance (in satoshis)         |
| 12     | 4    | uint32 | `block_reward_rate`| Reward rate per accepted share (satoshis/share)   |

**Total payload size:** 16 bytes.

---

## 6. Fragmentation Mapping (L3)

All four message types are fragmented by the existing L3 fragment layer
(SPEC.md §4). No fragmentation logic is specific to e-hash — the L7 envelope
(type + payload) is passed to `mesh_adapter_send()` as an opaque blob.

### 6.1 Fragment Header (SPEC.md §4.1 — recap)

```
Offset  Size  Field            Description
0       2     block_id         Block identifier (CRC-derived)
2       1     frag_index       Fragment index (0 = first)
3       1     original_count   Number of original (non-redundant) fragments
4       2     crc16            CRC-16/CCITT of header + payload
6       N     payload          Fragment payload data
```

- **Header size:** 6 bytes.
- **Max payload per fragment:** 242 bytes.
- **Max on-wire frame:** 6 + 242 = 248 bytes.
- **CRC-16/CCITT:** polynomial 0x1021, init 0xFFFF, stored little-endian.

### 6.2 Fragment Count by Message Type

| Message Type    | Payload Range  | + type byte | Fragments Needed |
|-----------------|----------------|-------------|------------------|
| `EHASH_NONCE`   | 21 B (fixed)   | 22 B        | 1                |
| `EHASH_RESULT`  | 7 B (fixed)    | 8 B         | 1                |
| `EHASH_CREDIT`  | 16 B (fixed)   | 17 B        | 1                |
| `EHASH_TEMPLATE`| 55–823 B       | 56–824 B    | 1–4              |

Fragment count for TEMPLATE: `ceil((1 + 55 + N + M + 32·K) / 242)`.

### 6.3 Fragmentation Rules

1. **Single-fragment messages** (NONCE, RESULT, CREDIT, small TEMPLATE):
   - `frag_index = 0`, `original_count = 1`.
   - Payload = full L7 envelope (type + message payload).
   - Sent as one frame.

2. **Multi-fragment messages** (large TEMPLATE):
   - L7 envelope is split into `ceil(total / 242)` chunks.
   - Each chunk gets its own fragment header.
   - `frag_index` increments from 0; `original_count` = total chunks.
   - Optional erasure-coded redundant fragments appended (SPEC.md §5).

3. **Erasure coding** (SPEC.md §5): For downlink broadcast templates, the
   balloon MAY add redundancy fragments (PRBS23-XOR) to improve delivery
   reliability. Recommended: 1 redundant fragment per 3 originals.

4. **Reassembly**: Ground station collects fragments by `block_id`, reassembles
   when all `original_count` fragments arrive (or erasure-decodes from
   redundant fragments), strips the 1-byte type tag, dispatches to the
   appropriate decoder.

---

## 7. Worked Examples

### 7.1 EHASH_NONCE (21 bytes)

A ground station with station ID 0x0042 (66) submits a nonce for job 0x00000001.

| Offset | Hex (LE)                     | Field         | Value         |
|--------|------------------------------|---------------|---------------|
| 0      | `01`                         | version       | 0x01          |
| 1      | `01 00 00 00`               | job_id        | 1             |
| 5      | `42 00 00 00`               | worker_id     | 0x0042 (66)   |
| 9      | `78 56 34 12`               | extranonce2   | 0x12345678    |
| 13     | `61 BC 0D 67`               | ntime         | 0x670DBC61    |
| 17     | `EF CD AB 89`               | nonce         | 0x89ABCDEF    |

**Full hex (21 bytes):**
```
01 01 00 00 00 42 00 00 00 78 56 34 12 61 BC 0D
67 EF CD AB 89
```

L7 envelope (22 bytes, type-prefixed): `11 01 01 00 00 00 42 00 00 00 78 56 34 12 61 BC 0D 67 EF CD AB 89`
→ **1 fragment**, payload 22 B.

### 7.2 EHASH_TEMPLATE (155 bytes, K=2)

Job 1, broadcast to all ground stations. Coinbase1 = 20 B, Coinbase2 = 16 B,
2 merkle branches.

| Offset | Hex (abbreviated)            | Field              | Value / Notes          |
|--------|-------------------------------|--------------------|------------------------|
| 0      | `01`                          | version            | 0x01                   |
| 1      | `01 00 00 00`                | job_id             | 1                      |
| 5      | `00 11 22 33 …` (32 B)       | prevhash           | sample 32-byte hash    |
| 37     | `00 00 20 00`                | btc_version        | 0x20000000             |
| 41     | `FF FF 00 1D`                | nbits              | 0x1D00FFFF             |
| 45     | `00 00 00 00`                | ntime              | 0 (use current)        |
| 49     | `14 00`                       | coinbase1_len      | 20                     |
| 51     | `46 65 6C 69 …` (20 B)       | coinbase1          | tx script part 1       |
| 71     | `10 00`                       | coinbase2_len      | 16                     |
| 73     | `AF 1D 6E 3B …` (16 B)       | coinbase2          | tx script part 2       |
| 89     | `02`                          | merkle_branch_count| 2                      |
| 90     | `AA BB CC …` (64 B)          | merkle_branches    | 2 × 32-byte hashes     |
| 154    | `01`                          | clean_jobs         | true (flush old)       |

**Total:** 155 bytes (1 + 4 + 32 + 4 + 4 + 4 + 2 + 20 + 2 + 16 + 1 + 64 + 1).
L7 envelope: 156 bytes (type `10` + payload).
→ **1 fragment** (156 ≤ 242 B payload limit).

**Partial hex dump (first 51 bytes — fixed header + coinbase1_len):**
```
10  01  01 00 00 00
    00 11 22 33 44 55 66 77 88 99 AA BB CC DD EE FF
    01 23 45 67 89 AB CD EF FE DC BA 98 76 54 32 10
    23 45 67 89 AB CD EF 01 23 45 67 89 AB CD EF 01
    00 00 20 00  FF FF 00 1D  00 00 00 00
    14 00
```

### 7.3 EHASH_RESULT (7 bytes)

Job 1, share accepted, no error.

| Offset | Hex (LE)       | Field      | Value |
|--------|----------------|------------|-------|
| 0      | `01 00 00 00`  | job_id     | 1     |
| 4      | `01`           | accepted   | true  |
| 5      | `00 00`        | error_code | 0     |

**Full hex:** `01 00 00 00 01 00 00`
L7 envelope (8 bytes): `12 01 00 00 00 01 00 00`
→ **1 fragment**.

### 7.4 EHASH_CREDIT (16 bytes)

Station 66 has a balance of 50,000,000 satoshis (0.5 BTC), reward rate 500 sats/share.

| Offset | Hex (LE)                     | Field              | Value      |
|--------|------------------------------|--------------------|------------|
| 0      | `42 00 00 00`               | station_id         | 66         |
| 4      | `00 C2 EB 07 00 00 00 00`   | balance            | 50000000   |
| 12     | `F4 01 00 00`               | block_reward_rate  | 500        |

**Full hex:** `42 00 00 00 00 C2 EB 07 00 00 00 00 F4 01 00 00`
L7 envelope (17 bytes): `13 42 00 00 00 00 C2 EB 07 00 00 00 00 F4 01 00 00`
→ **1 fragment**.

---

## 8. Encoding/Decoding Responsibilities

| Component        | Encode (TX)                          | Decode (RX)                          |
|------------------|--------------------------------------|--------------------------------------|
| E-hash proxy     | TEMPLATE, RESULT, CREDIT → binary    | NONCE → stratum `mining.submit` JSON |
| Balloon (relay)  | Pass-through (no encode/decode of payload) | Pass-through                    |
| Ground station   | NONCE → binary                       | TEMPLATE → stratum `mining.notify` JSON; RESULT → `mining.submit` response |

The balloon is a **pure transport node**. It fragments and forwards the binary
payload without parsing message fields (ADR-025 invariant #1: balloon never hashes).

---

## 9. Open Items (Future Phases)

- **Phase B**: Ground station stratum-bridge prototype will implement
  `ehash_template_decode` → JSON `mining.notify` and JSON `mining.submit` →
  `ehash_nonce_encode`.
- **Phase C**: Balloon relay module validates `job_id` consistency and gates
  template delivery on positive e-hash balance (no payload field parsing).
- **Template encryption** (ADR-025 O3): If adopted, a per-session key layer
  will be added between the L7 envelope and L3 fragmentation. The binary
  encoding defined here remains the inner plaintext format.
