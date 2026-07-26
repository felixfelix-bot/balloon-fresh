# V4 Firmware Bug Fix Plan

**Date:** 2026-07-27
**Author:** Orchestrator
**Status:** EXECUTING

---

## BUG 1: tx_fw=unknown (TRIVIAL — 2 lines)

**Root cause:** V4 envs in platformio.ini missing `extra_scripts = pre:tools/inject_git_version.py`. The inject script exists and works for V1/V3 envs. V4 envs were created without copying this line.

**Fix:** Add `extra_scripts = pre:tools/inject_git_version.py` to both `[env:rp2040-sweep-tx-v4]` and `[env:rp2040-sweep-rx-v4]` blocks.

**Quality gate:** Build both targets, verify firmware hash appears in serial output, verify RX decode shows tx_fw=<hash> not "unknown".

**Owner:** worker-balloon (kanban)
**Estimated time:** 5 minutes

---

## BUG 2: Phase sync bounce at boundaries (EASY — 1 condition change)

**Root cause:** Line 950 of multi_radio_sweep_rx_v4.cpp:
```cpp
if (txPhaseId != currentPhase && txPhaseId < numInterleavePhases) {
    currentPhase = txPhaseId;
```
This allows BACKWARD phase jumps. When a late packet from phase N arrives during phase N+1, RX jumps back to N. Then next packet from N+1 jumps forward again — bounce.

**Fix:** Only accept FORWARD phase changes (monotonic). Replace with:
```cpp
if (txPhaseId != currentPhase && txPhaseId < numInterleavePhases 
    && txPhaseId > currentPhase) {
```

Edge case: At cycle wrap (phase 76 → 0), txPhaseId (0) < currentPhase (76) but is valid. Add wrap-around:
```cpp
bool isForward = (txPhaseId > currentPhase) || 
                 (currentPhase > 70 && txPhaseId < 5);  // wrap
if (txPhaseId != currentPhase && txPhaseId < numInterleavePhases && isForward) {
```

**Quality gate:** Build RX, capture 1 full cycle (5 min), verify no duplicate PHASE_RESULT entries for any phase.

**Owner:** worker-balloon (kanban)
**Estimated time:** 10 minutes

---

## BUG 3: LF-FLRC-650 small packet failure (INVESTIGATION NEEDED)

**Symptom:** FLRC-650 has 87-100% PER at 32/64/128B but 22% at 255B. All other bitrates (325, 1300, 2600) work at all sizes.

**Observation:** This is specific to 650 kbps bitrate AND small payloads. The radio configuration for FLRC uses:
- Same preamble length (0x0E = 14)
- Same sync word for all FLRC bitrates
- Dynamic payload size via SET_FLRC_PACKET_PARAMS

**Hypotheses to investigate:**
1. Bitrate code 0x04 (650) may have different sync detection timing than 0x00/0x02/0x06
2. CRC length or sync word search window may need adjustment for 650
3. At 650 kbps, small packets may have too few preamble symbols for reliable sync

**Investigation plan:**
1. Compare full SET_FLRC_MODULATION_PARAMS between 650 and 1300 (which works)
2. Check if FLRC-650 needs different sync word length or preamble length
3. Test with extended preamble (0x14 instead of 0x0E)
4. If no clear fix found, add SKIP flag for FLRC-650 small packet phases (non-blocking)

**Quality gate:** Build both targets, capture 1 full cycle with FLRC-650 phases, verify PER improvement or document as hardware limitation.

**Owner:** worker-balloon (kanban) — investigation first, then fix
**Estimated time:** 30 minutes

---

## EXECUTION ORDER

1. Bug 1 (trivial) — do first, unblocks firmware version tracking
2. Bug 2 (easy) — do second, improves data quality immediately
3. Bug 3 (investigation) — do last, may require datasheet consultation

After all 3: rebuild both boards, capture 2 full cycles, sub-manager consensus review.
