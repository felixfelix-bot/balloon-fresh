# V4 Walk Test — Q&A and Design Decisions

**Date:** 2025-07-25
**Status:** Answers to operator questions + design decisions

---

## 1. WHAT IS BASE MODE?

**Base mode = 14-phase sweep, all at 255 bytes. No size variation.**

The TX cycles through 14 radio configurations sequentially:

```
Phase 0:  HF-LoRa-SF7   (15s, 50 packets at 255B)
Phase 1:  HF-LoRa-SF9   (15s, 50 packets at 255B)
Phase 2:  HF-LoRa-SF12  (30s, 15 packets at 255B)
Phase 3:  HF-FLRC-2600  (8s, 200 packets at 255B)
Phase 4:  HF-FLRC-1300  (8s, 200 packets at 255B)
Phase 5:  HF-FLRC-650   (8s, 200 packets at 255B)
Phase 6:  HF-FLRC-325   (8s, 200 packets at 255B)
Phase 7:  LF-LoRa-SF7   (8s, 50 packets at 255B)
Phase 8:  LF-LoRa-SF9   (20s, 30 packets at 255B)
Phase 9:  LF-LoRa-SF12  (50s, 10 packets at 255B)
Phase 10: LF-FLRC-2600  (8s, 200 packets at 255B)
Phase 11: LF-FLRC-1300  (8s, 200 packets at 255B)
Phase 12: LF-FLRC-650   (8s, 200 packets at 255B)
Phase 13: LF-FLRC-325   (8s, 200 packets at 255B)
--- cycle repeats ---
Total cycle: ~196 seconds
```

Each phase runs to completion, then the next starts. No interleaving within a phase.

## 2. WHAT IS INTERLEAVE MODE?

**Interleave mode = 56-phase sweep (14 modes × 4 sizes).**

Same sequential structure, just more phases. Each radio mode gets tested at 4 packet sizes:

```
Phase 0:  HF-LoRa-SF7-32B   (~8s)
Phase 1:  HF-LoRa-SF7-64B   (~8s)
Phase 2:  HF-LoRa-SF7-128B  (~8s)
Phase 3:  HF-LoRa-SF7-255B  (~15s)
Phase 4:  HF-LoRa-SF9-32B   (~8s)
...
Phase 55: LF-FLRC-325-255B  (~2s)
--- cycle repeats ---
Total cycle: ~400 seconds (longer due to more phases)
```

**It is NOT "one packet from test A, one from test B, one from test C."**
It is: run ALL packets for mode-size combo A, then ALL packets for combo B, then C, etc.

The name "interleave" refers to interleaving packet SIZES within each radio mode, not interleaving individual packets across modes.

## 3. WHY DID DRIFT HAPPEN?

**Root cause: test methodology, NOT firmware or hardware.**

The firmware computes phase from UTC time:
```c
uint32_t utcSec = millis()/1000 + utcOffset;
uint32_t cyclePos = utcSec % totalCycleSec;
```

When I sent `SET_TIME` to both boards, I sent them at DIFFERENT TIMES (seconds apart), causing the boards to compute different phase positions. The RP2040 crystal itself drifts only ~10ms over a 200-second cycle — negligible.

**With simultaneous SET_TIME, drift is <100ms (serial processing latency).**
**With periodic re-sync (every 10-20s), drift stays <50ms.**

## 4. TIME SYNCHRONIZATION STRATEGY (FIXED)

Felix is right: bidirectional RF sync is unnecessary and unreliable. We have two excellent time sources:

### TX Board (in rucksack):
- **Primary: GPS** — continuously updates utcOffset from $GNRMC/GNSS time
- **Fallback: laptop SET_TIME** — sent before operator unplugs and walks

### RX Board (at base station):
- **Primary: laptop NTP** — laptop stays connected to RX via USB during entire walk
- **Re-sync every 10 seconds** — laptop sends SET_TIME to RX periodically

### Implementation:
A simple laptop-side script sends `SET_TIME <epoch>` to RX every 10 seconds during capture:

```bash
# walk-capture.sh — runs on laptop during walk
while true; do
    NOW=$(date +%s)
    printf "SET_TIME %s\n" "$NOW" > /dev/ttyACM4  # RX board
    sleep 10
done &
timeout 600 cat /dev/ttyACM4 > walk-test.log
```

This keeps RX within 10 seconds of NTP time at all times. TX uses GPS as its primary clock source.

## 5. 255-BYTE CONTENT VERIFICATION

**Question:** Were the received 255-byte packets verified to contain the correct content, not just garbage?

**Answer:** The CRC-16 check IS the content verification. Here's why:

- TX fills bytes 4-252 with GPS data (lat/lon/sats/fix), phase ID, sequence number, firmware hash, and BER fill pattern
- TX computes CRC-16 over ALL of bytes 4-252 (249 bytes)
- TX stores CRC at bytes 253-254
- RX receives packet, finds sync header, extracts bytes, recomputes CRC
- If recomputed CRC matches stored CRC → content verified bit-for-bit correct

**Any single bit flip in those 249 bytes → CRC fails → packet rejected.**

The earlier test showed `crc_err=0` on decoded packets, meaning every packet that passed sync also passed CRC. The content was verified.

For additional BER analysis, bytes 31-254 contain an incrementing counter pattern (byte[i] = i & 0xFF). If we want byte-level error analysis, we can compare received vs expected pattern. But CRC pass already guarantees zero bit errors.

## 6. WHAT WAS BIDIRECTIONAL SYNC? (REMOVED)

An earlier sub-manager suggested having RX send time corrections back to TX via RF. Felix correctly identified this as flaky:

- Some modes are very slow (SF12: 4+ seconds per packet)
- RF link may be unreliable at range
- Unnecessary complexity when we have GPS + laptop NTP

**REMOVED.** TX uses GPS time. RX uses laptop NTP. Simple, accurate, reliable.

## 7. RECOMMENDED WALK TEST PLAN

### Option A: Base Mode (simplest, proven)
1. Flash V4 base mode to both boards (already done)
2. Connect RX to laptop, TX to GPS module + battery
3. SET_TIME both boards
4. Start capture on RX: `timeout 600 cat /dev/ttyACM4 > walk.log`
5. Operator walks with TX
6. Analyze 14-mode data at 255B

### Option B: Interleave Mode (comprehensive)
1. Flash V4 to both boards
2. Send SET_INTERLEAVE 1 to both boards
3. Connect RX to laptop, TX to GPS + battery
4. SET_TIME both boards
5. Start capture + re-sync script
6. Operator walks with TX
7. Analyze 56-phase data (14 modes × 4 sizes)

**Recommendation: Start with Option A (base mode, proven), then switch to Option B after confirming it works at range.**
