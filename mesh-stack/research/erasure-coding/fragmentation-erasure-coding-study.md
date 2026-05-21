# Fragmentation & Erasure Coding Study

**Date**: 2026-05-21
**Status**: Research complete, implementation pending

## TL;DR

For our unidirectional balloon telemetry and mesh transport over LoRa:

| Use Case | Recommended Approach | RAM | Overhead |
|----------|---------------------|-----|----------|
| **Tracker telemetry (28 bytes)** | No fragmentation needed | 0 | 0 |
| **Tracker encoder (fountain)** | Wirehair | ~137 KB (34% ESP32-C3 RAM) | ~2% |
| **Mesh relay (encode + decode)** | Semtech PRBS23-XOR | ~1 KB | ~20-50% |
| **Fallback if RAM tight** | Custom XOR Fountain | ~1.5 KB | ~5-15% |

## 1. Fragmentation Libraries Assessed

### 1.1 LoRaMesher (C++, ESP32)

- **Repo**: https://github.com/LoRaMesher/LoRaMesher
- **Fragmentation**: **NOT IMPLEMENTED**. Explicitly listed as unimplemented in `IMPLEMENTATION_STATUS.md`.
- Max single-frame payload: 232 bytes (SF7), 41 bytes (SF10).
- `DataMessage::Create()` simply fails if payload exceeds frame limit.
- A 2026 academic paper describes fragmentation but is not yet in the open-source code.
- **Verdict**: Not usable for fragmentation. Routing layer may still be useful.

### 1.2 SCHC — RFC 8724 (IETF Standard)

- **Spec**: RFC 8724 (SCHC: Static Context Header Compression and Fragmentation)
- **C impl**: libschc (https://github.com/imec-idlab/libschc) — GPL-3.0
- **Python impl**: OpenSCHC (https://github.com/openschc/openschc) — MIT

**Three fragmentation modes:**

| Mode | ACKs Required | Use Case |
|------|--------------|----------|
| **No-ACK** | No | Unidirectional links (our balloon TX) |
| ACK-Always | Yes, every window | High reliability bidirectional |
| ACK-on-Error | Yes, only on failure | Efficient bidirectional |

**No-ACK mode details:**
- Fire-and-forget: sender transmits all fragments sequentially
- No windows, no bitmaps, no roundtrips
- Last fragment carries CRC-32 (RCS) for integrity
- If any fragment lost: RCS fails, entire packet discarded
- **This is the only mode that works for our balloon TX without ACKs**

**Fragment header format (No-ACK):**
```
| RuleID (R bits) | DTag (T bits) | FCN (N bits) | Payload | Padding |
```
- Regular fragment: ~1 byte header
- All-1 (last) fragment: ~5 bytes header (includes CRC-32 RCS)

**libschc memory**: ~3.5 KB static RAM for fragmentation subsystem.

**Verdict**: No-ACK mode architecture is good reference. But GPL-3.0 license is problematic. No-ACK has no recovery — if any fragment lost, entire packet lost. We need erasure coding ON TOP of fragmentation, not just fragmentation alone.

### 1.3 Semtech PRBS23-XOR (LoRaWAN FUOTA)

- **Source**: LoRaMac-node `src/apps/LoRaMac/common/LmHandler/packages/FragDecoder.c`
- **Also in**: ARMmbed/mbed-lorawan-frag-lib (archived)
- **Algorithm**: Systematic XOR-based erasure code with PRBS23-generated sparse parity matrix

**How it works:**
1. First N fragments = original data (systematic)
2. Redundant fragments = XOR of selected original fragments
3. Parity matrix generated deterministically by PRBS23 LFSR (seeded from fragment index)
4. Decoder uses Gaussian elimination on binary matrix to recover missing fragments
5. Any N received fragments recover full data (MDS-like property)

**Key properties:**
- **Pure XOR operations** — no GF(256) arithmetic, no lookup tables
- **Deterministic** — encoder and decoder generate same parity matrix from fragment index
- **Battle-tested** — used in LoRaWAN FUOTA deployments worldwide
- **~200 lines of C** in `FragDecoder.c` + `FragDecoder.h`
- **No LoRaWAN dependency** — the FEC core is completely standalone

**API (decoder side):**
```c
void FragDecoderInit(uint16_t fragNb, uint8_t fragSize, FragDecoderCallbacks_t *cb);
int32_t FragDecoderProcess(uint16_t fragCounter, uint8_t *rawData);
FragDecoderStatus_t FragDecoderGetStatus(void);
```

**Memory for our use case (50 frags × 242 bytes × 25 redundant):**
```
((25/8)+1)*25 + 50*2 + 50 + 242 + 25*3 ≈ 550 bytes
```

**Encoder must be written** — the library only provides the decoder. Encoding is straightforward:
```c
void EncodeRedundancyFragment(uint16_t redundancyIndex, uint16_t fragNb,
                               uint8_t fragSize, uint8_t *dataBuffer,
                               uint8_t *outputFragment) {
    uint8_t matrixRow[(fragNb >> 3) + 1];
    FragGetParityMatrixRow(redundancyIndex, fragNb, matrixRow);
    memset(outputFragment, 0, fragSize);
    for (int i = 0; i < fragNb; i++) {
        if (GetParity(i, matrixRow) == 1) {
            XorDataLine(outputFragment, &dataBuffer[i * fragSize], fragSize);
        }
    }
}
```

**Verdict**: **Best option for mesh relay** (encode + decode on balloon). Tiny RAM, proven, simple. Must write our own encoder (~50 lines).

### 1.4 Stop-and-Wait ARQ (not recommended)

The approach suggested by web search AI results (send fragment, wait for ACK, retry) is **wrong for our use case**:
- At 300 km range, ACK roundtrip adds latency per fragment
- Balloon can't RX during TX TDMA slot — wastes precious airtime
- With 30% packet loss, cascading retries compound badly
- **This is why we planned fountain codes — zero ACKs needed**

## 2. Erasure Coding Libraries Assessed

### 2.1 Wirehair (Recommended for tracker encoder)

- **Repo**: https://github.com/catid/wirehair
- **Author**: Christopher A. Taylor (catid)
- **License**: BSD-3-Clause (fully permissive)
- **Language**: C/C++ (C API, C++ internals)

**Algorithm**: Non-MDS fountain code. Hybrid peeling + Gaussian elimination over GF(2) and GF(256).
- Systematic: first N blocks are original data
- Unlimited repair blocks: generate as many as needed
- `wirehair_decoder_becomes_encoder()`: relay can re-encode without reinitializing

**API:**
```c
wirehair_init();                                          // One-time init
WirehairCodec wirehair_encoder_create(msg, bytes, blockSize);
WirehairResult wirehair_encode(encoder, blockId, outBuf); // Generate one block
WirehairCodec wirehair_decoder_create(bytes, blockSize);
WirehairResult wirehair_decode(decoder, blockId, data, len);
WirehairResult wirehair_recover(decoder, outBuf, bytes);
void wirehair_free(codec);
```

**Overhead**: ~2% extra fragments beyond N (average overhead ~0.02 fragments)

**Benchmarks (3 GHz PC reference → ESP32-C3 estimate at 80 MHz):**

| N (blocks) | PC encode/create | PC encode/block | ESP32-C3 estimate create | ESP32-C3 estimate/block |
|------------|-----------------|----------------|--------------------------|-------------------------|
| 9 (our case) | ~13 µs | ~0 µs | ~1-2 ms | ~5-20 µs |
| 32 | 41 µs | ~0 µs | ~4 ms | ~5-20 µs |

**CRITICAL: Memory footprint (the elephant in the room):**

| Component | Size |
|-----------|------|
| GF256_MUL_TABLE[256×256] | 64 KB |
| GF256_DIV_TABLE[256×256] | 64 KB |
| Other GF256 tables | ~6 KB |
| **Total GF256 context** | **~134 KB** |
| Encoder codec state (N=9) | ~3.5 KB |
| **Total encoder** | **~137 KB (34% of 400 KB ESP32-C3 RAM)** |

For mesh relay (encode + decode): ~275 KB = 69% of RAM. Too much.

**RISC-V compatibility**: No explicit ESP32 or RISC-V support. Falls into scalar `GF256_TARGET_MOBILE` path. Needs minor `#ifdef` additions for RISC-V detection. Would be a first ESP32 port.

**Mitigations for 134 KB GF256 tables:**
1. Free GF256 context after encoding (only encode once per TDMA slot)
2. Replace full MUL/DIV tables with log/exp tables (~2 KB) — slower but tiny
3. Implement minimal GF(256) multiply using polynomial directly (no tables)

**Verdict**: Best fountain code for tracker (encoder only). RAM is tight but feasible if WiFi/BT disabled (~60-80 KB saved). Must benchmark on actual hardware.

### 2.2 CM256 (Reed-Solomon MDS)

- **Repo**: https://github.com/catid/cm256
- **License**: BSD-3-Clause
- **Type**: Block erasure code (NOT fountain — fixed repair block count)
- **RAM**: Same ~134 KB GF256 tables as Wirehair
- **Verdict**: MDS property is nice, but fixed repair blocks are a limitation for varying loss. No advantage over Wirehair for our use case.

### 2.3 Leopard-RS (O(N log N) Reed-Solomon)

- **Repo**: https://github.com/catid/leopard
- **Requires**: SSSE3/AVX2 (x86) or NEON (ARM). No RISC-V.
- **Verdict**: Not compatible with ESP32-C3 (RISC-V).

### 2.4 RaptorQ (RFC 6330)

- **Repo**: https://github.com/cberner/raptorq
- **Language**: Rust only. No C API.
- **Verdict**: Consider for ground station (Rust on PC/SBC). Not usable on ESP32-C3 firmware.

### 2.5 Custom XOR Fountain (Recommended fallback)

A minimal fountain code optimized for tiny N (2-20) and tiny payloads on MCUs:
- Encode: XOR random subsets of data blocks (coefficients from PRNG seed)
- Decode: Gaussian elimination over GF(2) (just XOR operations)
- No GF(256) tables needed
- Fountain property: unlimited repair blocks

**Memory (k=9, blockSize=120):**
- Received block storage: 9 × 120 = 1,080 bytes
- Binary matrix for GE: 9 × 9 / 8 ≈ 11 bytes
- Coefficient storage: 9 bytes per received block
- **Total: ~1.2 KB**

**Speed on ESP32-C3:**
- Encode one parity block: ~27 µs
- Decode (full GE): ~200 µs

**Trade-off**: ~5-15% overhead penalty vs Wirehair's ~2%. But runs anywhere with <2 KB RAM.

### 2.6 Simple Repetition Coding

- Send each fragment N times
- N=2: 100% overhead, P(frag survives) = 1 - 0.3² = 91%, P(all 9 survive) = 42% (unacceptable)
- N=3: 200% overhead, P(frag survives) = 97.3%, P(all 9 survive) = 78%
- **Verdict**: Too wasteful for LoRa airtime. Emergency fallback only.

## 3. Comparison Table

| Attribute | Wirehair | Semtech PRBS23-XOR | CM256 | Custom XOR Fountain | SCHC No-ACK |
|-----------|----------|--------------------|-------|---------------------|-------------|
| **Type** | Fountain | Systematic XOR | Block RS | Fountain | Frag only (no EC) |
| **RAM** | ~137 KB | ~0.5 KB | ~135 KB | ~1.5 KB | ~3.5 KB |
| **Overhead** | ~2% | 20-50% | 0% (MDS) | ~5-15% | 0% (no recovery) |
| **Unlimited repair** | Yes | No | No | Yes | N/A |
| **Fountain (no ACK)** | Yes | No | No | Yes | Yes (but no EC) |
| **License** | BSD-3 | BSD-like (Semtech) | BSD-3 | DIY | GPL-3.0 (libschc) |
| **Language** | C/C++ | C | C/C++ | DIY (C) | C (libschc) |
| **ESP32-C3** | Yes (scalar) | Yes | Yes (scalar) | Yes | Yes |
| **Code size** | ~2000 lines | ~200 lines | ~500 lines | ~200 lines | ~1400 lines |
| **GF256 tables** | Yes (134 KB) | No | Yes (134 KB) | No | No |
| **Proven in prod** | Yes | Yes (FUOTA) | Yes | No | Yes (LoRaWAN) |

## 4. Recommended Architecture

### Layer 3: Erasure-Coded Fragmentation

```
┌─────────────────────────────────────────────────┐
│ Application payload (telemetry batch / Nostr)    │
└──────────────────────┬──────────────────────────┘
                       │
          ┌────────────▼────────────┐
          │ Erasure Coding Encoder   │
          │ Wirehair / PRBS23-XOR    │
          │ Input: full payload      │
          │ Output: N+R coded blocks │
          └────────────┬────────────┘
                       │
          ┌────────────▼────────────┐
          │ Fragment Header + CRC    │
          │ block_id + frag_idx + k  │
          │ + CRC-16 per fragment    │
          └────────────┬────────────┘
                       │
          ┌────────────▼────────────┐
          │ LoRa PHY (RadioLib)      │
          │ Max 242 bytes per frame  │
          └─────────────────────────┘
```

### Fragment Header Format (Proposed)

```
Byte 0-1:  block_id (uint16_t)      — unique per message
Byte 2:    frag_index (uint8_t)     — 0..N+R-1
Byte 3:    original_count (uint8_t) — N (data blocks)
Byte 4-5:  CRC-16/CCITT             — per-fragment integrity
Byte 6+:   payload (up to 236 bytes at SF7, less at higher SF)
```

Total header: 6 bytes. Max payload per fragment: 236 bytes (SF7), 45 bytes (SF10).

### For Tracker Telemetry (28 bytes)

No fragmentation needed at any SF. Single LoRa frame. No erasure coding.
Future: batch 10 telemetry packets (280 bytes) → 2 fragments + erasure coding.

### For Mesh Transport (up to 2 KB Nostr events)

1. Split into 120-byte blocks → N = ceil(2000/120) = 17 blocks
2. Erasure-encode: Wirehair → 17 + ~3 = 20 coded blocks (tracker)
3. Or: PRBS23-XOR → 17 + 8 = 25 coded blocks (mesh relay)
4. Blast all blocks in TDMA slot burst
5. Receiver collects any N blocks → decode → reassemble

## 5. Implementation Tasks

- [ ] Port Wirehair to ESP-IDF as component (`tracker/firmware/components/wirehair/`)
- [ ] Add RISC-V detection to `gf256.h` (treat like `GF256_TARGET_MOBILE`)
- [ ] Benchmark Wirehair on ESP32-C3 (actual RAM usage, encode time)
- [ ] Implement Semtech PRBS23-XOR encoder (~50 lines C)
- [ ] Create `tracker/firmware/components/frag/` with fragment header + CRC
- [ ] Integration test: encode → fragment → LoRa TX → RX → defragment → decode
- [ ] If Wirehair RAM too tight: implement custom XOR Fountain fallback
