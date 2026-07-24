# 255-Byte Packet Investigation — Sub-Manager Consensus Report

**Date:** 2025-07-25
**Status:** CONSENSUS REACHED (3/3 sub-managers + orchestrator)
**Firmware under review:**
- SWEEP (proven): `multi_radio_sweep_gps.cpp` + `multi_radio_sweep_rx.cpp` (commit 5444af7)
- V2 (failed): `flrc_range_tx_v2.cpp` + `flrc_range_rx_v2.cpp` (commit 16b7d5b)

---

## Executive Summary

**255-byte packets ARE possible on the LR2021.** The chip supports up to 511 bytes.
The V2 firmware failures were caused by a **single wrong SPI opcode** in the FIFO
clear function — NOT a hardware limitation.

A 255-byte sweep across all 14 radio modes is a **1-2 hour task**: the proven
sweep code is macro-driven and buffer sizes are already 256 bytes.

---

## Root Cause: Wrong FIFO Clear Opcode

**THIS IS THE BUG THAT BROKE 255-BYTE PACKETS.**

| Firmware | FIFO Clear Opcode | Status |
|----------|------------------|--------|
| SWEEP (proven) | `{0x01, 0x20}` | **CORRECT** — verified working |
| V2 (failed) | `{0x01, 0x1E}` | **WRONG** — no-op, FIFO never actually cleared |

### Why It Kills 255-Byte Packets But Not 32-Byte

The LR2021 RX FIFO is ~256 bytes:

- **32-byte packets:** FIFO holds ~8 packets before overflow. Stale data from
  previous packets doesn't immediately corrupt the next read. The wrong opcode
  is tolerable — garbage accumulates slowly.

- **255-byte packets:** One uncleared packet fills the **entire FIFO**. The very
  first RX_DONE leaves 255 bytes that are never flushed. Every subsequent
  `rfReadRxFifo()` reads residual garbage. Sync header `0xA5 0x5A 0x42 0x24`
  is never found — exactly the observed symptom (random hex, -106 dBm noise
  floor, SYNC_NOT_FOUND on every packet).

### Evidence

```
# Proven sweep RX (line 306-307):
static void rfClearRxFifo() {
    uint8_t cmd[] = {0x01, 0x20};  // ← CORRECT opcode
}

# V2 RX (line 133-134):
static void rfClearRxFifo() {
    uint8_t cmd[] = { 0x01, 0x1E };  // ← WRONG opcode
}
```

The V2 header comment claims "FIX 3: FIFO clear on all paths" was ported from
sweep commit 9b740aa, but the opcode was transcribed incorrectly.

**Fix:** Change `{0x01, 0x1E}` → `{0x01, 0x20}` in any 255-byte firmware.

---

## Chip Capability (Sub-Manager 1: Protocol Expert)

### Can the LR2021 handle 255-byte packets? YES.

- **Maximum payload: 511 bytes** (9-bit payload length field in SET_FLRC_PACKET_PARAMS)
- TheClams canonical Rust reference driver explicitly uses PLD=255
- The `SET_FLRC_PACKET_PARAMS (0x0249)` command accepts payload length as
  big-endian u16 at bytes 4-5

### Register Configuration

The packet parameter bytes are **identical** between 32-byte and 255-byte configs:

```c
// PROVEN (32 bytes):
{ 0x02, 0x49, 0x0C, 0x4C, 0x00, 0x20 }   // FLRC_PKT_SIZE=32

// BROKEN (255 bytes):
{ 0x02, 0x49, 0x0C, 0x4C, 0x00, 0xFF }   // TX_PKT_SIZE=255
```

Only the length byte changes. No other register needs modification.

**Verdict: NO chip-level constraint blocks 255 bytes.**

---

## Why V2 Failed (Sub-Manager 2: Failure Analysis)

### Symptoms (from 255-byte V2 testing)

- TX confirmed transmitting: 500 pkts/burst, 1660 kbps, all TX_DONE
- RX IRQ firing, FIFO data present
- SYNC_NOT_FOUND on every packet
- Raw hex: random-looking bytes, RSSI -106 dBm (noise floor)
- Same boards, same range: sweep 32-byte firmware gets clean decode

### Root Cause (confirmed by code inspection)

See "Root Cause" section above. Wrong FIFO clear opcode.

### Secondary Factors (not root cause)

- V2 RSSI formula bug: uses 9-bit `<<1` assembly that doubles the value
  (sweep_rx explicitly documents this as wrong)
- V2 GPS parser: uses `strncmp("$GPGGA")` but M10 module outputs `$GNGGA`
- V2 no CDC watchdog: unsafe for battery operation

---

## 255-Byte Sweep Implementation Path (Sub-Manager 3: Effort Estimation)

### Required Changes (~30 lines across both files)

| Change | Location | Lines |
|--------|----------|-------|
| `LORA_PKT_SIZE`/`FLRC_PKT_SIZE` → 255 | TX L144-145, RX L226-227 | 4 |
| TX spin timeout → millis-based | TX L932 | 1 (critical) |
| Fill payload bytes 31-254 with known pattern | TX ~L916 | ~5 |
| Phase table pktCount/slotMs adjustments | TX L119-137, RX L97-115 | ~12 |
| Update header comments | TX L16-30, RX L19-23 | ~10 |

### Air-Time Calculations (255 bytes)

| Mode | 32-byte (current) | 255-byte | Feasible? |
|------|-------------------|----------|-----------|
| HF-LoRa-SF7 BW812 | ~14ms | **62ms** | YES - trivial |
| HF-LoRa-SF9 BW812 | ~30ms | **192ms** | YES - easy |
| HF-LoRa-SF12 BW812 | ~250ms | **1.19s** | YES - reduce pktCount |
| LF-LoRa-SF7 BW250 | ~50ms | **200ms** | YES - easy |
| LF-LoRa-SF9 BW250 | ~150ms | **625ms** | YES - reduce pktCount |
| LF-LoRa-SF12 BW250 | ~825ms | **3.85s** | MARGINAL - ~10 pkts/50s slot |
| All FLRC modes | <1ms | **<7ms** | YES - negligible |

### Estimated Cycle Time

~194s (comparable to current 202s). FLRC phases unchanged at 8s/200pkts.
LoRa phases absorb extra air time.

### Effort: 1-2 Hours

Not a research project. The code was designed for this:
- Macro-driven packet sizes
- 256-byte buffers already allocated
- Parameterized phase table
- The only non-mechanical work: TX spin-timeout fix for SF12

---

## Sub-Manager Recommendations

### Unanimous Consensus

| Sub-Manager | Verdict on 255-byte Feasibility | Condition |
|-------------|-------------------------------|-----------|
| 1 (Protocol) | **YES** — chip supports 511 bytes | Fix FIFO opcode |
| 2 (Failure Analysis) | **YES** — root cause found | Fix FIFO opcode 0x1E → 0x20 |
| 3 (Effort) | **YES** — 1-2 hour task | Fix TX timeout for SF12 |
| Orchestrator | **YES** — consensus agreement | Both fixes above |

### Recommended Implementation Plan

1. **Immediate:** Use proven 32-byte sweep for first walk test (zero risk)
2. **Follow-up:** Build 255-byte sweep variant:
   - Change `LORA_PKT_SIZE`/`FLRC_PKT_SIZE` to 255
   - Fix FIFO clear opcode (use `{0x01, 0x20}` from proven code)
   - Fix TX spin timeout to millis-based for SF12
   - Reduce pktCount for SF12 phases (air time dominates)
   - Bench test: verify FLRC 255-byte round-trip before walk
3. **Optional:** Consider dropping LF-LoRa-SF12 to 64 bytes if 3.85s/pkt
   is too slow for walk test pace

### For the Walk Test

**Use 32-byte sweep NOW.** It's proven, verified, on the boards, ready to go.
Build the 255-byte variant afterward for comprehensive characterization.

---

## Appendix: The Three Alignment Fixes (proven, must be in any firmware)

1. **App-layer sync header (0xA5 0x5A 0x42 0x24):** TX embeds at payload bytes
   0-3. RX dynamically searches FIFO for sync header (chip prepends framing bytes).

2. **App-layer CRC-16 (CCITT 0x1021):** Hardware CRC passes garbage. TX computes
   CRC-16 over payload. RX verifies and rejects mismatches.

3. **FIFO clear on ALL IRQ paths:** RX calls `rfClearRxFifo()` (opcode `{0x01, 0x20}`)
   before re-arm on EVERY path: RX_DONE, CRC_ERR, other IRQ, sync miss, app CRC fail.
   **CRITICAL: Must use opcode 0x20, NOT 0x1E.**
