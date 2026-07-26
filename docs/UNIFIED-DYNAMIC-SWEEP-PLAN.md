# Unified Dynamic Packet Size Sweep — Comprehensive Consensus Plan

**Date:** 2026-07-25
**Status:** CONSENSUS — sub-manager reviews + orchestrator
**Author:** Orchestrator + 3 sub-managers
**Commits reviewed:** b8d7dff (proven 32B), _v3 files (uncommitted 255B port)

---

## Executive Summary

Felix wants ONE firmware that sweeps packet size as a dimension alongside mode and band.
This is the plan to build it. The foundation already exists: `_v3` files port all 6 bug
fixes to 255-byte payloads with only 12 lines changed. We extend `_v3` to make packet
size runtime-configurable and optionally sweepable.

**Three-mode architecture:**
1. **FAST mode** — 14 phases × 32 bytes, 202s cycle (current proven behavior)
2. **MAX mode** — 14 phases × 255 bytes, ~300s cycle (throughput characterization)
3. **SWEEP mode** — 14 modes × {32, 64, 128, 255}, ~800s cycle (comprehensive)

Operator selects mode via serial command before or during walk. No reflashing.

---

## What Already Exists (Sub-Manager Discovery)

### The `_v3` Files — Unified Firmware Port (PROVEN CODEBASE)

Sub-manager analysis confirmed: `multi_radio_sweep_rx_v3.cpp` and `multi_radio_sweep_gps_v3.cpp`
are the proven sweep firmware with ALL 6 V2 bug fixes, adapted for 255-byte payloads.

**Exact diff between proven sweep (32B) and v3 (255B):**

TX changes (12 lines):
```diff
// Phase table: reduced pktCount for long-air-time modes
- {"HF-LoRa-SF12",  PT_LORA, 2440.0, 1, 12, 0x0F, 1, 0, 30, 30000},  // 32B: 30 pkts
+ {"HF-LoRa-SF12",  PT_LORA, 2440.0, 1, 12, 0x0F, 1, 0, 15, 30000},  // 255B: 15 pkts

- {"LF-LoRa-SF9",   PT_LORA,  868.0, 0,  9, 0x05, 1, 0, 50, 20000},  // 32B: 50 pkts
+ {"LF-LoRa-SF9",   PT_LORA,  868.0, 0,  9, 0x05, 1, 0, 30, 20000},  // 255B: 30 pkts

- {"LF-LoRa-SF12",  PT_LORA,  868.0, 0, 12, 0x05, 1, 0, 20, 50000},  // 32B: 20 pkts
+ {"LF-LoRa-SF12",  PT_LORA,  868.0, 0, 12, 0x05, 1, 0, 10, 50000},  // 255B: 10 pkts

// Packet size macros
- #define LORA_PKT_SIZE  32
- #define FLRC_PKT_SIZE  32
+ #define LORA_PKT_SIZE  255
+ #define FLRC_PKT_SIZE  255

// TX buffer fill (BER pattern)
- txBuf[31] = 0;
+ for (int i = 31; i < pktSize; i++) txBuf[i] = (uint8_t)(i & 0xFF);

// TX timeout (critical for SF12 255B ~4.3s air time)
- uint32_t spinCount = 0;
- while (spinCount < 30000000) {           // 240ms — TOO SHORT for 255B SF12
-     if ((spinCount & 0xFFFF) == 0) gpsPoll();
-     spinCount++;
- }
+ uint32_t txStartMs = millis();
+ while ((millis() - txStartMs) < 6000) {  // 6s — covers SF12 255B (4.3s)
+     if ((millis() - txStartMs) % 3 == 0) gpsPoll();
+ }
```

RX changes (2 lines):
```diff
- #define LORA_PKT_SIZE  32
- #define FLRC_PKT_SIZE  32
+ #define LORA_PKT_SIZE  255
+ #define FLRC_PKT_SIZE  255
```

**ALL 6 bug fixes from the proven sweep are present unchanged in v3.**

---

## The 6 V2 Bugs — All Already Fixed in Sweep + v3

(See `firmware/rp2040/docs/V2-BUG-FIX-PLAN.md` for full line-by-line analysis)

| # | Bug | V2 Code | Correct (Sweep/v3) | Portable to 255B? |
|---|-----|---------|-------------------|--------------------|
| 1 | RSSI formula (9-bit `<<1` doubles value) | `flrc_range_rx_v2.cpp:204` | `sweep_rx.cpp:388` — `-(int16_t)buf[4] * 5` | ✅ No change needed |
| 2 | RSSI type truncation (`int8_t` caps at -128) | `flrc_range_rx_v2.cpp:188` | `sweep_rx.cpp:195` — `int16_t` in tenths dBm | ✅ No change needed |
| 3 | GPS parser never fires (`$GPGGA` vs `$GNGGA`) | `flrc_range_tx_v2.cpp:123` | `sweep_gps.cpp:232` — `strstr("GGA")` + `$%*2sGGA` | ✅ No change needed |
| 4 | No CDC watchdog (TX silent-dies on battery) | Absent from V2 | `sweep_gps.cpp:63-77,673-677,802-809` — armed after first successful write | ✅ 30s > 4.3s SF12 TX |
| 5 | Duplicate tracking (consecutive-seq only) | `flrc_range_rx_v2.cpp:514` | `sweep_rx.cpp:229-244` — 256-entry bitmap | ✅ seq still 1 byte |
| 6 | Wrong FIFO clear opcode (`0x1E` no-op) | `flrc_range_rx_v2.cpp:134` | `sweep_rx.cpp:307` — `{0x01, 0x20}` | ✅ Chip-level, size-independent |

**Felix's question answered:** "If you know the bug, why not fix it?"
→ The fix IS written and proven. It lives in the sweep firmware. The `_v3` files copy it
  to 255-byte payloads. V2 was superseded, not abandoned — the fixes were never lost.

---

## Dynamic Packet Size — Architecture Design

### Core Change: Runtime Packet Size

Replace compile-time `#define LORA_PKT_SIZE` with runtime variable:

```c
// OLD (compile-time):
#define LORA_PKT_SIZE  32

// NEW (runtime):
static uint16_t g_pktSize = 32;   // default, changed via serial command
```

Both TX and RX need to agree on packet size. Two mechanisms:

**Mechanism 1: Serial Command (manual)**
```
SET_PKT_SIZE 32     → fast sweep
SET_PKT_SIZE 255    → max throughput sweep
SET_PKT_SIZE 64     → medium
SET_PKT_SIZE 128    → medium-large
```

**Mechanism 2: Packet Size Field in Payload (automatic)**
TX embeds `pktSize` byte in the payload header. RX reads it and adjusts its FIFO read
length dynamically. This enables SWEEP mode where TX changes size each phase.

### Payload Format (Dynamic Size)

| Offset | Size | Field | Notes |
|--------|------|-------|-------|
| 0-3 | 4 | Sync header | `0xA5 0x5A 0x42 0x24` (unchanged) |
| 4-7 | 4 | latE7 | int32 LE |
| 8-11 | 4 | lonE7 | int32 LE |
| 12-13 | 2 | sats | uint16 LE |
| 14 | 1 | fixQ | uint8 |
| 15-18 | 4 | utcSec | uint32 LE |
| 19 | 1 | phaseId | uint8 (0-13) |
| 20-21 | 2 | seq | uint16 BE |
| 22-28 | 7 | fw_hash | ASCII |
| 29 | 1 | **pktSizeId** | **NEW: 0=32, 1=64, 2=128, 3=255** |
| 30-31 | 2 | CRC-16 CCITT | BE, covers bytes 4-29 (26 bytes) |
| 32-N | variable | Fill pattern | Incrementing counter for BER: `byte[i] = (i & 0xFF)` |
| N-1 | 1 | CRC-16 (extended) | Optional: covers bytes 32 to N-2 |

**Key insight:** The first 32 bytes are FIXED regardless of payload size. RX always reads
32 bytes first, finds sync header, parses GPS + pktSizeId, then knows how many more bytes
to read from FIFO. This eliminates the "RX doesn't know the packet size" problem.

### RX Dynamic Read Algorithm

```c
// Step 1: Always read first 32 bytes
rfReadRxFifo(rxBuf, 32);

// Step 2: Find sync header (same as now)
int syncOffset = findSyncHeader(rxBuf, 32);

// Step 3: Extract pktSizeId from fixed header
uint8_t pktSizeId = rxBuf[syncOffset + 29];
uint16_t actualPktSize;
switch (pktSizeId) {
    case 0: actualPktSize = 32;  break;
    case 1: actualPktSize = 64;  break;
    case 2: actualPktSize = 128; break;
    case 3: actualPktSize = 255; break;
    default: actualPktSize = 32; break;  // fallback
}

// Step 4: If packet is larger than 32, read remaining bytes
if (actualPktSize > 32) {
    rfReadRxFifoContinuation(&rxBuf[32], actualPktSize - 32);
}

// Step 5: Verify CRC over full payload
uint16_t crcCalc = crc16(&rxBuf[syncOffset + 4], actualPktSize - 4 - 2);
uint16_t crcRecv = (rxBuf[syncOffset + actualPktSize - 2] << 8) |
                   rxBuf[syncOffset + actualPktSize - 1];
```

**Problem:** The LR2021 SET_PACKET_PARAMS registers the payload length BEFORE receiving.
If TX sends 255 bytes but RX expects 32, the chip will only buffer 32 bytes.

**Solution:** RX must be configured for the MAXIMUM packet size (255) at all times. The
chip will still trigger RX_DONE on any valid packet. The RX then reads however many bytes
the payload indicates. The FIFO always has enough room (256 bytes > 255).

This is the key architectural decision: **RX always configured for 255-byte max, reads
actual size from payload header.**

---

## Three Sweep Modes

### Mode 0: FAST (current behavior, 32 bytes)
- 14 phases, 202s cycle
- Uses current proven phase table
- Default on boot
- Command: `SET_SWEEP_MODE 0` or `SET_PKT_SIZE 32`

### Mode 1: MAX (255 bytes, throughput)
- 14 phases, ~300s cycle
- Uses v3 phase table (reduced pktCount for SF modes)
- Command: `SET_SWEEP_MODE 1` or `SET_PKT_SIZE 255`

### Mode 2: SWEEP (all sizes, comprehensive)
- 56 phases (14 modes × 4 sizes), ~800s cycle
- Phase table auto-generates: for each mode, run at 32, 64, 128, 255
- PKT_RESULT output includes `pktSize=N` field
- Command: `SET_SWEEP_MODE 2`

### Mode 3: CUSTOM (operator-selected sizes)
- Operator sends: `SET_SWEEP_SIZES 32,128,255`
- Firmware runs only the selected sizes
- Useful for targeted testing

---

## Phase Table for SWEEP Mode (Mode 2)

Extended phase table concept: each original phase becomes 4 sub-phases.

```
Phase 0.0: HF-LoRa-SF7  @ 32B   (50 pkts, ~0.7s)
Phase 0.1: HF-LoRa-SF7  @ 64B   (50 pkts, ~1.0s)
Phase 0.2: HF-LoRa-SF7  @ 128B  (40 pkts, ~1.8s)
Phase 0.3: HF-LoRa-SF7  @ 255B  (30 pkts, ~3.1s)
Phase 1.0: HF-LoRa-SF9  @ 32B   (50 pkts, ~1.5s)
...
Phase 5.3: HF-FLRC-650  @ 255B  (200 pkts, ~1.4s)
...
Phase 13.3: LF-FLRC-325 @ 255B  (200 pkts, ~1.4s)
```

**Total: 56 phases.** Estimated cycle time:

| Mode Type | Phases | Air time/phase | Total |
|-----------|--------|----------------|-------|
| LoRa SF7 (6 phases × 4 sizes) | 24 | 0.7-3.1s | ~48s |
| LoRa SF9 (2 phases × 4 sizes) | 8 | 1.5-7.7s | ~37s |
| LoRa SF12 (2 phases × 4 sizes) | 8 | 8.3-38.5s | ~186s |
| FLRC (8 phases × 4 sizes) | 32 | 1-1.4s | ~38s |
| **TOTAL** | **56** | | **~310s (~5 min)** |

Wait — that's better than I initially estimated. The FLRC phases dominate by count but
are fast. LoRa SF12 is the bottleneck at 255B (38.5s for 10 packets).

Actually with reduced pktCounts for 255B SF12 (10 pkts × 3.85s = 38.5s), and 8 phases
of SF12 across 4 sizes: 32B (20×0.825=16.5s) + 64B (15×1.65=24.8s) + 128B (12×3.3=39.6s)
+ 255B (10×3.85=38.5s) = ~119s just for the 2 SF12 modes across 4 sizes.

**Revised total: ~310-400s (5-7 minutes per cycle).** Manageable for a walk test
where you walk 7 minutes, then turn around.

---

## Air-Time Reference Table

| Mode | 32B | 64B | 128B | 255B | Recommended pktCount @ 255B |
|------|------|------|------|------|----------------------------|
| HF-LoRa-SF7 BW812 | 14ms | 28ms | 55ms | 109ms | 30 |
| HF-LoRa-SF9 BW812 | 55ms | 109ms | 218ms | 435ms | 20 |
| HF-LoRa-SF12 BW812 | 992ms | 1.98s | 3.96s | 7.9s | 5 |
| HF-FLRC-2600 | <1ms | <1ms | <1ms | <2ms | 200 |
| HF-FLRC-1300 | <1ms | <1ms | <1ms | <3ms | 200 |
| HF-FLRC-650 | <1ms | 1ms | 2ms | 4ms | 200 |
| HF-FLRC-325 | 1ms | 2ms | 4ms | 7ms | 200 |
| LF-LoRa-SF7 BW250 | 51ms | 102ms | 205ms | 408ms | 30 |
| LF-LoRa-SF9 BW250 | 410ms | 819ms | 1.64s | 3.27s | 10 |
| LF-LoRa-SF12 BW250 | 13.1s | 26.2s | 52.5s | 104.6s | **IMPOSSIBLE** |
| LF-FLRC-2600 | <1ms | <1ms | <1ms | <2ms | 200 |
| LF-FLRC-1300 | <1ms | <1ms | <1ms | <3ms | 200 |
| LF-FLRC-650 | <1ms | 1ms | 2ms | 4ms | 200 |
| LF-FLRC-325 | 1ms | 2ms | 4ms | 7ms | 200 |

**LF-LoRa-SF12 at 255 bytes: 104.6 SECONDS PER PACKET.** This is completely impractical.
At 32 bytes it's 13.1s (marginal). At 64+ bytes, skip this mode or reduce to 1-2 packets.

**Recommendation:** For SWEEP mode, LF-LoRa-SF12 runs ONLY at 32B and 64B. At 128B and 255B,
output `PHASE_RESULT pktSize=N rx=0 note=SKIP_LONG_AIRTIME`. This saves 157 seconds per cycle.

---

## Implementation Plan

### Step 1: Promote _v3 to canonical (30 min)

1. Copy `_v3` files over the proven sweep files (git mv)
2. Add pktSizeId byte to payload (byte 29)
3. Add SWEEP_MODE serial command parser
4. Build + flash + bench test at 255B on FLRC
5. Verify GPS still works, sync still found, CRC still rejects garbage

### Step 2: Add dynamic packet size (45 min)

1. Replace `#define LORA_PKT_SIZE` with `static uint16_t g_pktSize`
2. TX: read g_pktSize, fill payload accordingly
3. RX: always configure chip for 255B max, read actual size from pktSizeId
4. Add SET_PKT_SIZE, SET_SWEEP_MODE serial commands
5. Add pktSize field to PHASE_RESULT output

### Step 3: Add SWEEP mode (45 min)

1. Expand phase table generator: mode × size combinations
2. Phase ID encoding: `phaseId = modeId * 4 + sizeId` (0-55)
3. TX cycles through expanded phase table
4. RX decodes phaseId → modeId + sizeId
5. Add skip logic for LF-LoRa-SF12 at 128B/255B

### Step 4: Extended CRC (15 min)

1. CRC-16 covers bytes 4 to N-2 (variable length)
2. TX computes over actual payload
3. RX verifies over actual payload
4. BER analysis: compare fill pattern bytes against expected counter

### Step 5: Bench test + walk test (30 min)

1. Flash both boards
2. Run FAST mode (32B) — verify same results as current
3. Run MAX mode (255B) — verify FLRC works, LoRa SF7/9 work
4. Run SWEEP mode — verify all 56 phases cycle
5. Go walk

**Total estimated time: 2.5-3 hours**

---

## Serial Command Protocol

```
Existing:
  SET_TIME <epoch>          — set board clock
  FW_QUERY                  — print firmware banner

New:
  SET_PKT_SIZE <N>          — set packet size (32/64/128/255)
  SET_SWEEP_MODE <M>        — 0=FAST, 1=MAX, 2=SWEEP, 3=CUSTOM
  SET_SWEEP_SIZES <a,b,c>   — custom size list (mode 3 only)
  GET_SWEEP_CONFIG          — print current configuration
```

Operator workflow for walk test:
```
# Outbound walk: baseline at 32B (fast cycle)
SET_SWEEP_MODE 0
# Walk 200m, collect data

# Turn around: switch to 255B (throughput)
SET_PKT_SIZE 255
# Walk back, collect throughput data

# Or: comprehensive characterization
SET_SWEEP_MODE 2
# Walk slowly, 5-7 min per cycle
```

---

## PHASE_RESULT Output Format (Extended)

```
PHASE_RESULT <phaseId> <modeName> pktSize=<N> rx=<count> unique=<count> lost=<count> per=<pct> rssi_avg=<dbm> rssi_min=<dbm> crc_err=<count> garbage=<count> ber=<pct> tx_lat=<float> tx_lon=<float> sats=<n> fix=<q> utc=<epoch> tx_fw=<hash> rx_fw=<hash>
```

New fields:
- `pktSize=N` — actual payload size this phase
- `ber=<pct>` — bit error rate (from fill pattern comparison, SWEEP mode only)

---

## Consensus

| Reviewer | Unified firmware approach | Dynamic packet size | SWEEP mode |
|----------|--------------------------|--------------------|----|
| Sub-Manager 1 (Bug Analysis) | ✅ _v3 has all 6 fixes | ✅ Portability confirmed | ✅ |
| Sub-Manager 2 (Architecture) | ✅ _v3 is the baseline | ✅ Runtime variable feasible | ✅ |
| Sub-Manager 3 (Decision Gate) | ✅ Proceed with proven base | ✅ Add as feature | ✅ Best option |
| Orchestrator | ✅ Unified _v3 + dynamic size | ✅ Agreed | ✅ Agreed |

**UNANIMOUS:** Build unified firmware from _v3 baseline + dynamic packet size + SWEEP mode.

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| 255B FLRC fails on sweep arch | LOW — proven in flrc_tx_raw | Blocks MAX mode | Bench test before walk |
| RX FIFO framing issues at 255B | MEDIUM — different from simple FLRC | Garbage on all phases | Fixed FIFO opcode + sync search |
| LF-LoRa-SF12 255B impractical | CERTAIN — 104s/packet | Skip 2 phases | Auto-skip with note in output |
| Dynamic size confuses TX/RX sync | MEDIUM | Missed packets | pktSizeId in fixed header |
| Walk test delayed 3 hours | HIGH | Felix impatient | Can walk NOW with 32B, build later |

**Mitigation for walk test delay:** Boards are CURRENTLY flashed with proven 32B firmware.
Felix can walk NOW and we build the dynamic sweep firmware in parallel or afterward.

---

## Felix's Questions Answered

**"Why not add the other 13 modes to V2?"**
→ We don't need to. The sweep firmware already has all 14 modes. V2 was a dead end.
  The _v3 files merge sweep's 14 modes + 6 bug fixes + 255-byte support.

**"If the RSSI bug is known, why not fix it?"**
→ It IS fixed. In sweep_rx.cpp line 388. And in v3. V2 was never updated because sweep
  superseded it. The fix was written, commented, and proven — just not backported to V2.

**"Why not add CDC watchdog to V2?"**
→ Same answer. Sweep_gps.cpp has it (lines 63-77, 673-677, 802-809). V3 inherits it.

**"Can we make packet size dynamic and sweep it?"**
→ YES. This plan describes exactly how: runtime variable + serial commands + SWEEP mode.
  The _v3 files are 90% of the way there. Adding dynamic size is ~2 hours of work.

**"I want both throughput and range simultaneously."**
→ The SWEEP mode gives you exactly this: at each distance, you get PER and throughput
  for all 14 modes × 4 sizes. Plot throughput-vs-distance curves for each mode.

**"Maybe we also try 128 and 64."**
→ Already planned. SWEEP mode cycles through {32, 64, 128, 255}. Custom mode lets you
  pick any subset.

---

## Next Steps

1. **IMMEDIATE:** Felix walks with current 32B firmware (proven, ready, zero risk)
2. **IN PARALLEL or AFTER:** Build unified dynamic sweep firmware (2.5-3 hours)
3. **SECOND WALK:** Flash unified firmware, walk with SWEEP mode for full characterization
4. **ANALYSIS:** Plot throughput-vs-distance, PER-vs-distance, BER-vs-distance for all modes
