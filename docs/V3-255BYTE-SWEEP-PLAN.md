# V3 Firmware Plan — 255-Byte Sweep Across All 14 Modes

**Date:** 2025-07-25
**Status:** DRAFT — pending sub-manager validation
**Goal:** Maximum throughput AND range characterization simultaneously

---

## Operator's Core Question

> "What's the maximum throughput we can achieve at a really long range?
> And how much range can we get without compromising throughput?"

This requires **255-byte packets** across **all 14 radio modes** — giving us
PER (range metric) AND throughput (kbps metric) at every distance point.

---

## Design Decision: Build V3, Not Fix V2

V2 was a clean-room rewrite that re-introduced bugs already fixed in sweep.
Instead of patching V2, **V3 = proven sweep + 255-byte extension**.

This means every proven component stays untouched:
- GPS parser (talker-ID agnostic, handles $GNGGA)
- CDC watchdog (arms after first write, safe for battery)
- RSSI formula (int16_t in tenths of dBm, correct 9-bit assembly)
- Duplicate tracking (256-bit bitmap, order-independent)
- FIFO clear (opcode 0x20, correct)
- Phase sync (SET_TIME bootstrap + GPS primary)
- All 3 alignment fixes from commit 9b740aa

Only packet size and payload layout change.

---

## Concern-by-Concern Resolution

### 1. "Why not add all 14 modes to V2?"

**Answer:** V3 does exactly this. It uses the sweep phase table (14 phases,
202s cycle) with 255-byte packets instead of 32-byte. No reflash between tests.

### 2. "RSSI formula is buggy — fix it"

**Answer:** Already fixed in sweep. V2 used a wrong formula (9-bit <<1 doubling).
V3 inherits sweep's proven formula:
```cpp
// FLRC: GET_FLRC_PACKET_STATUS, correct 9-bit assembly
return -(int16_t)buf[4] * 5;  // tenths of dBm
// LoRa: GET_LORA_PACKET_STATUS
return -(int16_t)buf[2] * 5;  // tenths of dBm
```

### 3. "RSSI type truncation — fix it"

**Answer:** V2 used int8_t (caps at -128). Sweep uses int16_t in tenths of dBm
(range: -3276.7 to 0.0). V3 keeps int16_t.

### 4. "GPS parser never fires — fix it"

**Answer:** V2 used `strncmp("$GPGGA")` but M10 module outputs `$GNGGA`.
Sweep uses `strstr("GGA")` which is talker-ID agnostic. V3 keeps sweep's parser.

### 5. "No CDC watchdog — add it"

**Answer:** V2 had none. Sweep has a watchdog that:
- Arms only after first successful USB CDC write
- Triggers hardware reboot if CDC dies 30s after arming
- Won't reboot-loop when USB unplugged (walk test battery mode)
V3 keeps sweep's watchdog.

### 6. "Duplicate tracking misses out-of-order packets — fix it"

**Answer:** V2 compared seq to lastSeq (only catches consecutive dups).
Sweep uses a 256-bit bitmap (`seenSeq[256]`) — marks each received sequence
number, counts unique at phase end. Order-independent. V3 keeps bitmap.

### 7. "255 bytes tests throughput not range"

**Answer:** It tests BOTH. At each distance point we measure:
- PER (packet error rate) — range/link-budget metric
- Effective throughput (kbps) — capacity metric
- RSSI (dBm) — signal strength metric

The operator wants the throughput-range product: "how much bandwidth
survives at distance X?" 255-byte packets answer this directly. 32-byte
packets only answer "can a tiny packet survive?" — less useful for
balloon mesh network design.

---

## Implementation: V3 Changes (from proven sweep)

### Change 1: Packet Size (4 lines)

```cpp
// SWEEP (proven):
#define LORA_PKT_SIZE  32
#define FLRC_PKT_SIZE  32

// V3:
#define LORA_PKT_SIZE  255
#define FLRC_PKT_SIZE  255
```

### Change 2: Extended Payload Layout

Current 32-byte packet uses bytes 0-30 (sync + GPS + CRC + hash).
V3 extends to 255 bytes:

```
[0-3]     sync header (0xA5 0x5A 0x42 0x24) — unchanged
[4-7]     latE7 (int32 LE) — unchanged
[8-11]    lonE7 (int32 LE) — unchanged
[12-13]   sats (uint16 LE) — unchanged
[14]      fixQ (uint8) — unchanged
[15-18]   utcSec (uint32 LE) — unchanged
[19]      phaseId (uint8) — unchanged
[20-21]   seq (uint16 BE) — unchanged
[22-28]   fw_hash (7 ASCII chars) — unchanged
[29-30]   CRC-16 (uint16 BE) over [4-28] — unchanged
[31-254]  EXTENDED PAYLOAD — known fill pattern for BER analysis
```

The fill pattern `[31-254]` allows bit-error-rate analysis: RX can compare
received bytes against expected pattern to count bit errors per packet.

### Change 3: TX Spin Timeout (1 line, CRITICAL)

```cpp
// SWEEP (proven, 32 bytes):
uint32_t spinCount = 0;
while (spinCount < 30000000) {  // ~1.9s at 125MHz
    // ... check TX_DONE
    spinCount++;
}

// V3 (255 bytes):
uint32_t txStartMs = millis();
while ((millis() - txStartMs) < 5000) {  // 5s timeout for SF12
    // ... check TX_DONE
}
```

SF12 at 255 bytes takes ~3.85s per packet. Old 1.9s timeout would skip.

### Change 4: Phase Table Adjustments

| Phase | Old (32B) | V3 (255B) | Air Time | Change |
|-------|-----------|-----------|----------|--------|
| HF-LoRa-SF7 | 50pkt/15s | 50pkt/15s | 62ms | None |
| HF-LoRa-SF9 | 50pkt/15s | 50pkt/15s | 192ms | None |
| HF-LoRa-SF12 | 30pkt/30s | 15pkt/30s | 1.19s | Halve pktCount |
| HF-FLRC-2600 | 200pkt/8s | 200pkt/8s | 0.78ms | None |
| HF-FLRC-1300 | 200pkt/8s | 200pkt/8s | 1.6ms | None |
| HF-FLRC-650 | 200pkt/8s | 200pkt/8s | 3.1ms | None |
| HF-FLRC-325 | 200pkt/8s | 200pkt/8s | 6.3ms | None |
| LF-LoRa-SF7 | 50pkt/8s | 50pkt/8s | 200ms | None |
| LF-LoRa-SF9 | 50pkt/20s | 30pkt/20s | 625ms | Reduce pktCount |
| LF-LoRa-SF12 | 20pkt/50s | 10pkt/50s | 3.85s | Halve pktCount |
| LF-FLRC-2600 | 200pkt/8s | 200pkt/8s | 0.78ms | None |
| LF-FLRC-1300 | 200pkt/8s | 200pkt/8s | 1.6ms | None |
| LF-FLRC-650 | 200pkt/8s | 200pkt/8s | 3.1ms | None |
| LF-FLRC-325 | 200pkt/8s | 200pkt/8s | 6.3ms | None |

Estimated cycle: ~200s (same as current 202s).

### Change 5: RX Sync Search Loop Bounds

```cpp
// SWEEP (32 bytes): search up to pktSize-31 = 1
for (int i = 0; i <= (int)pktSize - 31; i++) {

// V3 (255 bytes): search up to pktSize-31 = 224
for (int i = 0; i <= (int)pktSize - 31; i++) {
// Same formula, larger range. Chip framing offset typically <10 bytes.
}
```

### What Does NOT Change

- SPI helpers (all proven)
- GPS NMEA parser
- CDC watchdog
- RSSI readers
- Phase computation algorithm
- CRC-16 (CCITT 0x1021)
- Firmware hash embedding
- FIFO clear opcode (0x20)
- Hardware sync word (0x12 0xAD 0x10 0x1B)
- Pin assignments
- Serial output format (PHASE_RESULT etc)

---

## RX Enhancement: BER Analysis

V3 RX can count bit errors in the extended payload:

```cpp
// After sync header + CRC pass, check fill pattern bytes [31-254]
uint16_t bitErrors = 0;
for (int i = 31; i < pktSize; i++) {
    uint8_t expected = (uint8_t)(i & 0xFF);
    uint8_t xor = rxBuf[dataOff + i] ^ expected;
    bitErrors += __builtin_popcount(xor);
}
// Report: BER = bitErrors / (224 * 8) per packet
```

This gives per-packet BER data — far more granular than PER alone.
Combined with throughput measurement, this is the complete range
characterization tool Felix wants.

---

## Effort Estimate

- Code changes: ~50 lines across TX and RX
- Testing: flash both boards, verify 1 FLRC phase + 1 LoRa phase
- Total: 2-3 hours including testing

---

## Walk Test Readiness

After V3 is built and bench-tested:
1. Flash V3 to both boards
2. SET_TIME sync both boards
3. Walk with 255-byte sweep running
4. Capture: PER + throughput + RSSI + BER for all 14 modes
5. One walk = complete characterization

No reflashing. No multiple walks. All modes, all metrics, one pass.
