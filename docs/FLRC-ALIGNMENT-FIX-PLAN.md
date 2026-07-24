# FLRC Byte Alignment Fix Plan — Comprehensive

> Created: 2026-07-24
> Status: Planning
> Owner: Orchestrator (balloon-hermes)
> Worktree: ~/worktrees/balloon-range-tests/

## Problem Statement

FLRC packets decode correctly for the first 1-3 packets per phase, then byte
alignment drifts. GPS payloads become garbage (lat=-131, lon=133, sats=60665).
CRC falsely passes. LoRa phases see zero packets (phase desync).

Walk test proved FLRC range is excellent (-55 dBm at 5.7km). The ONLY blocker
to usable data is this alignment + sync issue.

## Current State (commit 9b740aa)

Already implemented:
- ✅ Sync header (0xA5 0x5A 0x42 0x24) in TX bytes 0-3
- ✅ RX dynamic sync header scan (searches buffer for 4-byte pattern)
- ✅ App-layer CRC-16 (CCITT 0x1021) over GPS payload
- ✅ rfClearRxFifo() called after every packet
- ✅ GPS range sanity check (|lat|>90 rejected)

Still broken:
- ❌ FLRC_PKT_SIZE=255 but real payload is ~31 bytes. RX reads 255 from FIFO,
  gets chip framing overhead mixed with our payload. Sync header offset VARIES
  per packet.
- ❌ No way to know actual payload length from chip. Fixed read of 255 bytes
  includes garbage past the real payload.
- ❌ LoRa phase desync: TX uses GPS UTC, RX uses SET_TIME laptop epoch. Clocks
  drift >202s apart, phases never align.
- ❌ CRC bytes at fixed offset (29-30 in TX) but RX reads from gpsOff+25/+26
  where gpsOff varies with sync header offset. If sync header found at
  different offset, CRC bytes are read from wrong location → false pass.

## Root Cause Analysis

### RC1: Variable FIFO framing offset (PRIMARY)

The LR2021 chip prepends its own bytes to the FIFO:
- Preamble bytes (configurable, typically 8-32 for FLRC)
- Sync word (2-5 bytes)
- Variable-length header

When RX reads 255 bytes from FIFO, the payload does NOT start at byte 0.
The offset varies because:
- Different sync word configurations per mode (LoRa vs FLRC)
- Chip may add status bytes at the end
- FIFO pointer may not reset to zero between reads

Walk evidence: FLRC first bytes = 92 103 250 144 (NOT 0xA5 0x5A).
LoRa first bytes = 38 98 16 153 (different framing).

### RC2: No payload length query

LR2021 has a register that reports actual received payload length.
We never read it. We blindly read 255 bytes regardless.

### RC3: Clock domain split

TX: phase = unixTime % 202s, where unixTime comes from GPS RMC.
RX: phase = unixTime % 202s, where unixTime comes from SET_TIME (laptop).

GPS epoch and laptop epoch differ by 1-10 seconds (NTP vs GPS).
Over a 202s cycle, 5s offset means TX is in phase 3 while RX is in phase 5.
FLRC phases are 8s each — a 5s offset means they barely overlap.
LoRa phases are 15-50s — a 5s offset still catches some, but 10s+ kills it.

### RC4: CRC offset depends on sync header offset

TX puts CRC at bytes 29-30 (absolute).
RX reads CRC from gpsOff+25 and gpsOff+26 where gpsOff = syncOffset + 4.
If syncOffset=0: reads bytes 29-30 ✓
If syncOffset=3: reads bytes 32-33 ✗ (false pass/fail)

---

## Fix Plan — 5 Phases

### Phase A: Variable Payload Length + Fixed TX Size [range-tests]

**Goal:** RX reads exactly the bytes TX sent, no more, no less.

**Steps:**

A1. Reduce FLRC_PKT_SIZE from 255 to 32 bytes.
    - TX only fills bytes 0-30 with real data. Bytes 31-254 are filler.
    - Sending 255 bytes wastes airtime and confuses the FIFO.
    - FLRC at 2600 kbps: 32 bytes = 0.1ms airtime. Plenty of margin.
    - Set `#define FLRC_PKT_SIZE 32` in both TX and RX.

A2. Reduce LORA_PKT_SIZE from 127 to 32 bytes.
    - Same reasoning. LoRa SF7: 32 bytes = ~1ms. SF12: ~1s. Still fine.

A3. TX: pad bytes 0-30 only. Set pktSize=32 for ALL modes.
    - Remove the `for (i=19; i<pktSize; i++) txBuf[i] = i ^ 0xA5` filler loop.
    - Bytes 31 is zero-padded.

A4. RX: read only 32 bytes from FIFO.
    - `rfReadRxFifo(rxBuf, 32)` regardless of mode.
    - Sync header search only needs to scan 10 positions max (32 - 22).

A5. Build + verify both compile clean.

**Deliverables:** Source changes in multi_radio_sweep_gps.cpp + multi_radio_sweep_rx.cpp.
Commit: `fix: reduce packet size to 32 bytes — eliminate FIFO framing ambiguity`

---

### Phase B: Sync Header Self-Healing [range-tests]

**Goal:** If sync header is at wrong offset, fix the offset for future packets.

**Steps:**

B1. Track last known good syncOffset per mode.
    - `int8_t lastSyncOffset[14]` initialized to -1.
    - When sync found at offset N, store lastSyncOffset[currentPhase] = N.
    - Next packet: try expected offset FIRST, fall back to scan.

B2. If sync not found at ANY offset for 3 consecutive packets:
    - Log "SYNC_LOST phase=N" and reset lastSyncOffset[currentPhase] = -1.
    - This indicates the chip framing has changed (phase switch, re-init).
    - Full scan resumes until sync re-established.

B3. CRC offset fix:
    - CRC is at FIXED absolute position in TX: bytes 29-30.
    - RX must read CRC from `syncOffset + 25` and `syncOffset + 26`.
    - This is ALREADY correct IF syncOffset is found correctly.
    - Add assertion: if CRC passes but GPS values are out of range, log as
      "CRC_FALSE_POS" to catch remaining edge cases.

B4. Build + verify.

**Deliverables:** Source changes in multi_radio_sweep_rx.cpp.
Commit: `fix: sync header self-healing + tracking per-mode offset`

---

### Phase C: Phase Synchronization — GPS Primary [range-tests]

**Goal:** TX and RX stay phase-synced for the entire walk without laptop.

**Steps:**

C1. RX: add GPS NMEA parser (copy from TX firmware).
    - RX already has GPS hardware connected? If not, this is hardware work.
    - If RX has no GPS module: SKIP this phase, use SET_TIME with periodic
      resync every 60s from laptop.

C2. RX: compute phase from GPS UTC every loop() iteration:
    ```cpp
    if (gps.hasUnixTime) {
        currentPhase = computePhaseFromUTC(gps.unixTime);
    } else if (hasLaptopTime()) {
        currentPhase = computePhaseFromUTC(getUtcNow());
    }
    ```

C3. TX: already uses GPS UTC. No change needed.

C4. SET_TIME: send every 60s during capture to resync laptop fallback.
    - Already implemented in capture script.

**Decision point:** Does RX board have a GPS module connected?
- If YES: implement C1-C2. Full GPS sync.
- If NO: implement C4 only. Periodic SET_TIME resync. Accept ±5s drift.
         This means LoRa phases may still miss. FLRC will work (8s slots).

**Deliverables:** Source changes in multi_radio_sweep_rx.cpp.
Commit: `fix: GPS primary clock for phase sync`

---

### Phase D: Board Lock Hardening [speed-tests]

**Goal:** Sub-managers cannot flash boards or read serial without lock.

**Already done (commit 35b292c):**
- ✅ chmod 000/666 on lock acquire/release
- ✅ picotool/openocd PATH shims
- ✅ FLASH-QUEUE.md coordination protocol
- ✅ pio-flash.sh fixed lock check

**Remaining:**

D1. Test chmod logic with a board connected.
    - Acquire lock, verify another process gets EACCES.
    - Release lock, verify access restored.

D2. Add board-lock-check cron monitor:
    - Every 5 min: log who holds the lock, detect stale locks.
    - Alert if lock held >2h without activity.

D3. Update all AGENTS.md files with mandatory lock procedure:
    - range-tests/AGENTS.md
    - speed-tests/AGENTS.md
    - Add: "MUST use pio-flash.sh wrapper. Raw `pio run -t upload` = BANNED."

**Deliverables:** Testing results + AGENTS.md updates.
Commit: `fix: board lock hardening — tested + documented`

---

### Phase E: Walk Test Protocol [range-tests]

**Goal:** Systematic pre-flight checks before any outdoor test.

**Steps:**

E1. Create tools/pre_flight_check.sh:
    ```bash
    #!/bin/bash
    # Pre-flight checklist before walk test
    # Usage: ./pre_flight_check.sh <tx_port> <rx_port> <expected_build>
    
    echo "[1/6] TX board alive?"
    echo "[2/6] RX board alive?"
    echo "[3/6] TX FW build matches expected?"
    echo "[4/6] RX FW build matches expected?"
    echo "[5/6] TX GPS locked? (sats > 4)"
    echo "[6/6] RX receiving TX packets?"
    ```

E2. Create tools/walk_capture.sh:
    - Dual capture: ACM0 (USB) + ACM1 (bridge) simultaneously
    - Auto-reconnect on CDC dropout
    - Timestamp in filenames: walk-buildN-tx-vs-buildM-rx-DATE.txt
    - Kill old captures before starting (prevent competition)

E3. Update WALK-AROUND-TEST-GUIDE.md with new checklist.

**Deliverables:** Scripts + updated guide.
Commit: `feat: walk test protocol — pre-flight checks + dual capture`

---

## Phase Dependency Graph

```
Phase A (pkt size) ──┐
                     ├──► Phase B (sync heal) ──► Phase C (phase sync)
                     │                                    │
Phase D (lock) ──────┘ (independent)                      │
                                                          ▼
                                                   Phase E (walk protocol)
```

- A and D can run in PARALLEL (different tracks, no dependency)
- B depends on A (need correct pkt size before testing sync)
- C depends on B (need aligned packets before testing phase sync)
- E depends on C (need working firmware before walk protocol matters)

## Assignment

| Phase | Track | Effort | Blocks |
|-------|-------|--------|--------|
| A | range-tests | 30min | B, C |
| B | range-tests | 45min | C |
| C | range-tests | 1h | E |
| D | speed-tests | 30min | — |
| E | range-tests | 30min | — |

**Parallel start:** A (range-tests) + D (speed-tests) immediately.
**After A+B:** C (range-tests).
**After C:** E (range-tests).

Total critical path: A → B → C → E = ~3h.
D runs in parallel, finishes in 30min.

## Verification Criteria

After all phases complete, run this test:
1. Flash TX + RX with new firmware (same build)
2. verify_board.sh on both — build ID matches
3. Capture 5 minutes at 1m range
4. Check: 0% garbage packets, GPS lat/lon correct on ALL modes
5. Check: LoRa packets received (phase sync working)
6. Check: CRC failures < 5%
7. If pass → ready for next walk test

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Reducing pkt size to 32 breaks LoRa SF12 | SF12 at 32 bytes = ~1s airtime. Within 50s slot. Safe. |
| RX has no GPS module | Phase C uses SET_TIME fallback. LoRa may still miss. |
| Chip framing offset changes per re-init | Phase B self-healing tracks offset per mode. |
| Sub-managers still bypass lock | Phase D chmod 000 physically blocks. Cron monitor detects. |
