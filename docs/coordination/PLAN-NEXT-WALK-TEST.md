# PLAN: Next Walk Test — Comprehensive Fix & Validation Pipeline

**Created:** 2026-07-24
**Status:** READY FOR DISPATCH
**Author:** Felix (orchestrator)
**Related:** PLAN-FIRMWARE-INTEGRITY.md, PLAN-FLRC-ALIGNMENT-FIX.md, WALK-TEST-POSTMORTEM.md

## WHAT HAPPENED (Summary)

The 2026-07-24 walk test (5.7km, 57 min) produced 256 FLRC packets with 100% garbage payloads. Six root causes were identified in the postmortem. Code fixes have been written and committed but NOT yet tested on hardware. This plan covers: (A) verifying the fixes work, (B) infrastructure for future data quality, (C) the next walk test protocol.

## CURRENT STATE OF FIXES

| Bug | Fix | Code Committed | Built | Hardware Tested |
|-----|-----|:-:|:-:|:-:|
| F1: Firmware mismatch | Git hash in packets + boot banner + flash guard | 4fb6b9c | YES | NO |
| F2: FLRC byte alignment | Dynamic sync header search + FIFO clear | 9b740aa | YES | NO |
| F3: CRC false positive | App-layer CRC-16 (CCITT) in TX+RX | 9b740aa | YES | NO |
| F4: LoRa phase desync | Pending hardware testing | — | — | — |
| F5: RX USB dropout | ESP32 bridge failover (already works) | — | — | YES |
| F6: Lock bypass | udev chmod + pio guard shim | ef60a51 | N/A | NO |

**Everything builds clean. Nothing has been flashed or tested on hardware yet.**

---

## PHASE OVERVIEW

```
PHASE 1 (range-tests)     → Flash + bench-test firmware fixes
PHASE 2 (speed-tests)     → Deploy board lock enforcement + install udev rules
PHASE 3 (range-tests)     → 1-meter indoor validation test
PHASE 4 (orchestrator)    → Capture script + metadata infrastructure
PHASE 5 (operator + all)  → Walk test execution
PHASE 6 (range-tests)     → Post-walk analysis + plots
```

---

## PHASE 1: Flash + Bench-Test Firmware Fixes

**Assigned to:** range-tests
**Depends on:** Phase 2 complete (boards locked, enforcement active)
**Effort:** 45 min
**Blocks:** Phase 3

### Tasks

1. Acquire both board locks:
   ```
   BALLOON_TRACK=range-tests python3 tools/balloon-board-lock.py acquire both --purpose "firmware fix validation"
   ```

2. Flash TX (F242D) from commit 9b740aa:
   ```
   cd firmware/rp2040
   pio run -e rp2040-sweep-gps-tx -t upload --upload-port /dev/balloon-tx
   ```

3. Flash RX (8332) from SAME commit:
   ```
   pio run -e rp2040-sweep-rx -t upload --upload-port /dev/balloon-rx
   ```

4. Verify boot banners match:
   ```
   # Send FW_QUERY to each board, read response
   echo "FW_QUERY" > /dev/balloon-tx; timeout 3 cat /dev/balloon-tx
   echo "FW_QUERY" > /dev/balloon-rx; timeout 3 cat /dev/balloon-rx
   # Both must print: FW_BOOT hash=<same_hash> tag=TX0/RX0 built=<time>
   ```

5. Record to FLASH-MANIFEST.csv

6. Bench test — place TX+RX 1m apart, capture 2 minutes:
   ```
   python3 scripts/sweep_capture.py --port /dev/balloon-rx --distance 1 --env indoor --cycles 1
   ```

7. Verify in capture output:
   - FLRC_RAW32 shows 0xA5 0x5A 0x42 0x24 at some offset (NOT byte 0)
   - SYNC_NOT_FOUND count should be low
   - Valid GPS in PKT lines (lat~32.6, lon~-16.9, sats 6-31)
   - APP_CRC_FAIL count should be 0
   - tx_fw hash matches rx_fw hash in PHASE_RESULT

8. Report: PASS or FAIL with evidence. If FAIL, document which check failed and raw byte dumps.

### Deliverables
- Capture file in data/bench-test-<commit>/
- FLASH-MANIFEST.csv updated
- Status report: PASS/FAIL per check

---

## PHASE 2: Board Lock Enforcement

**Assigned to:** speed-tests
**Depends on:** Nothing (can run immediately)
**Effort:** 30 min
**Blocks:** Phase 1 (boards must be safe to flash)

### Tasks

1. Install udev rules for stable symlinks:
   ```
   sudo cp tools/99-balloon-boards.rules /etc/udev/rules.d/
   sudo udevadm control --reload-rules
   sudo udevadm trigger
   # Verify: ls -la /dev/balloon-tx /dev/balloon-rx
   ```

2. Test balloon-board-lock.py with chmod enforcement:
   ```
   # Acquire lock
   BALLOON_TRACK=speed-tests python3 tools/balloon-board-lock.py acquire tx --purpose "test"
   # Verify port is chmod 000
   ls -la /dev/balloon-tx
   # Try to access — should fail
   cat /dev/balloon-tx  # Permission denied
   # Release lock
   python3 tools/balloon-board-lock.py release tx
   # Verify port restored to 666
   ls -la /dev/balloon-tx
   ```

3. Install pio guard shim:
   ```
   mkdir -p ~/bin
   cp tools/pio-guard.sh ~/bin/pio
   chmod +x ~/bin/pio
   echo 'export PATH="$HOME/bin:$PATH"' >> ~/.bashrc
   # Test: try upload without BALLOON_TRACK — should be BLOCKED
   pio run -e rp2040-sweep-gps-tx -t upload --upload-port /dev/balloon-tx
   # Should print: GUARD: BALLOON_TRACK not set. Upload BLOCKED.
   ```

4. Report: PASS or FAIL per check

### Deliverables
- /dev/balloon-tx and /dev/balloon-rx stable symlinks
- chmod enforcement verified
- pio guard shim installed and tested
- Status report

---

## PHASE 3: 1-Meter Indoor Validation

**Assigned to:** range-tests
**Depends on:** Phase 1 + Phase 2 complete
**Effort:** 30 min
**Blocks:** Phase 5 (walk test)

### Tasks

1. Place TX and RX boards 1m apart, both on desk

2. Send SET_TIME to both boards:
   ```
   echo "SET_TIME $(date +%s)" > /dev/balloon-tx
   echo "SET_TIME $(date +%s)" > /dev/balloon-rx
   ```

3. Run 3 full sweep cycles (~10 min):
   ```
   python3 scripts/sweep_capture.py --port /dev/balloon-rx --distance 1 --env indoor --cycles 3
   ```

4. Validation criteria (ALL must pass):

   | Check | Expected | Fail Action |
   |-------|----------|-------------|
   | Boot banner TX == RX hash | Match | Re-flash both from same commit |
   | FLRC sync header found | SYNC_NOT_FOUND < 10% | Check FLRC packet params |
   | GPS valid in FLRC packets | lat 32.63-32.65, lon -16.93 to -16.96 | Check sync search logic |
   | GPS valid in LoRa packets | Same range | Check LoRa RX_PATH config |
   | APP_CRC_FAIL = 0 | Zero failures | Check CRC byte offsets |
   | LoRa packets received | > 0 per SF7/SF9 phase | Check radio config for LoRa |
   | tx_fw in PHASE_RESULT | Matches RX hash | Check TX payload bytes 22-28 |
   | Sequence numbers sequential | Incrementing | Check seq encoding |

5. If any check fails: STOP, document, escalate to orchestrator

6. Report: PASS or FAIL with capture file

### Deliverables
- Capture file: data/validation-1m-<date>/
- Validation checklist completed
- Status report

---

## PHASE 4: Capture Infrastructure

**Assigned to:** orchestrator (do directly, do not delegate)
**Depends on:** Nothing (can run in parallel with Phases 1-3)
**Effort:** 1 hour

### Tasks

1. Create capture metadata header system:
   - Modify sweep_capture.py to read RX boot banner at start
   - Write metadata header to capture file before data lines
   - Format:
     ```
     # CAPTURE START 2026-07-25T09:00Z
     # RX_FIRMWARE hash=abc123d tag=RX0 built=2026-07-25T08:45Z
     # TX_FIRMWARE hash=abc123d tag=TX0 (verified via PKT tx_fw field)
     # OPERATOR: Felix
     # NOTES: Both boards flashed from 9b740aa, verified at 1m
     ```

2. Create data directory convention:
   ```
   data/
     walk-YYYY-MM-DD/
       capture-rx.txt
       phone-gps.csv
       metadata.json
       plots/
       analysis.md
   ```

3. Create pre-walk checklist script:
   ```
   tools/pre-walk-check.sh
   - Reads TX boot banner
   - Reads RX boot banner
   - Compares hashes
   - Checks TX GPS lock (sats > 6)
   - Creates data directory
   - Starts capture with metadata header
   ```

4. Commit and push

### Deliverables
- Updated sweep_capture.py with metadata headers
- tools/pre-walk-check.sh
- Data directory template

---

## PHASE 5: Walk Test Execution

**Assigned to:** operator (Felix) + range-tests (capture monitoring)
**Depends on:** Phase 3 PASS + Phase 4 complete
**Effort:** 1-2 hours

### Pre-Walk (15 min before)

1. Run pre-walk-check.sh — ALL checks must pass
2. Flash TX in rucksack, GPS antenna with clear sky view (NOT buried in bag)
3. RX on balcony, USB cable secured (tape if needed)
4. Send SET_TIME to both boards
5. Start phone GPS recording
6. Start capture: `python3 scripts/sweep_capture.py --port /dev/balloon-rx ...`
7. Verify first PHASE_RESULT shows valid data before walking

### During Walk

1. Orchestrator monitors capture (no sub-manager board access)
2. Check every 10 min: line count growing, PKT lines appearing
3. Alert operator if capture dies

### Post-Walk

1. Stop capture
2. Download phone GPS
3. Commit everything to git
4. Delegate analysis to range-tests

---

## PHASE 6: Post-Walk Analysis

**Assigned to:** range-tests
**Depends on:** Phase 5 complete
**Effort:** 1 hour

### Tasks

1. Run plot_walk_data.py on new capture
2. Generate 6 standard plots (RSSI vs distance, time series, packet counts, GPS track, distribution, signal map)
3. Verify this walk has VALID GPS data (unlike last walk)
4. Compare RSSI vs distance to previous walk (should be similar signal, but now with valid data)
5. Report: what worked, what didn't, what to fix next

### Deliverables
- 6 plots in data/walk-<date>/plots/
- analysis.md
- Status report

---

## DISPATCH MATRIX

| Phase | Owner | Can Start | Blocks | Deliverable |
|-------|-------|-----------|--------|-------------|
| 2 | speed-tests | NOW | Phase 1 | udev + chmod + pio guard |
| 4 | orchestrator | NOW | Phase 5 | capture metadata + pre-walk script |
| 1 | range-tests | After Phase 2 | Phase 3 | flashed boards + bench test |
| 3 | range-tests | After Phase 1 | Phase 5 | 1m validation PASS |
| 5 | operator + range-tests | After Phase 3+4 | Phase 6 | walk test data |
| 6 | range-tests | After Phase 5 | — | analysis + plots |

**Parallel tracks:** Phase 2 + Phase 4 can run simultaneously right now.

---

## SUCCESS CRITERIA FOR NEXT WALK

The next walk test is SUCCESSFUL if:

1. tx_fw hash in PHASE_RESULT matches RX firmware hash (binary integrity)
2. GPS data in >50% of FLRC packets is valid (lat 32-33, lon -16 to -17, sats 6-31)
3. APP_CRC_FAIL = 0 (no CRC mismatches)
4. At least 1 LoRa mode receives >10 packets with valid GPS
5. RSSI vs distance plot shows expected signal decay (not flat noise floor)
6. Phone GPS track correlates with packet timestamps

If criteria 1-3 pass but 4-5 don't, that's still major progress — we've fixed the data layer and can now isolate RF issues.

---

## ROLLBACK PLAN

If Phase 1 or Phase 3 fails:
1. Do NOT walk
2. Document the failure with raw byte dumps
3. Escalate to orchestrator with evidence
4. Orchestrator dispatches targeted fix to range-tests
5. Re-run Phase 1

If Phase 5 (walk) has issues:
1. Keep recording — raw data is always valuable
2. Analyze what we got
3. Fix and re-test
