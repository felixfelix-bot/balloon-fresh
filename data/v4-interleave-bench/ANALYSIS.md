# V4 Interleave Analysis — 2026-07-25

## Phase Coverage Summary

### WORKING (decoded with rx>0, BER=0):
- Phase 0-3:   HF-LoRa-SF7 (32/64/128/255) ✓
- Phase 4-7:   HF-LoRa-SF9 (32/64/128/255) ✓
- Phase 8-11:  HF-LoRa-SF12 (32/64/128/255) ✓
- Phase 13-15: HF-FLRC-2600 (64/128/255) ✓
- Phase 16-19: HF-FLRC-1300 (32/64/128/255) ✓
- Phase 20-23: HF-FLRC-650 (32/64/128/255) ✓
- Phase 24-25: HF-FLRC-325 (32/64) ✓
- Phase 30-31: LF-LoRa-SF7 (128/255) ✓
- Phase 32:    LF-LoRa-SF9-32 ✓
- Phase 36:    LF-LoRa-SF12-32 ✓
- Phase 40-55: LF-FLRC ALL (2600/1300/650/325 × 32/64/128/255) ✓

### NEVER DECODED:
- Phase 12:    HF-FLRC-2600-32 ← TRANSITION ISSUE (SF12→FLRC extreme reconfig)
- Phase 26-27: HF-FLRC-325-128/255 ← phase drift (not captured aligned)
- Phase 28-29: LF-LoRa-SF7-32/64 ← phase drift
- Phase 33-35: LF-LoRa-SF9-64/128/255 ← phase drift
- Phase 37-39: LF-LoRa-SF12-64/128/255 ← SKIP BY DESIGN (26s+ air time)

### KEY FINDING:
Phase 12 (HF-FLRC-2600-32) is the ONLY mode/size combination that fails
consistently. All other HF-FLRC-2600 sizes (64/128/255) work perfectly.
ROOT CAUSE: Phase 11 (HF-LoRa-SF12-255, 11 second air time) immediately
precedes phase 12 (HF-FLRC-2600-32, fastest packet). This is the most
extreme radio reconfiguration in the cycle. RX likely doesn't complete
radio init before TX starts transmitting.

FIX OPTIONS:
1. Add 500ms inter-phase gap between SF12 and FLRC phases
2. Reorder phases: put HF-FLRC before HF-LoRa-SF12
3. Increase phase 12 slot time from 2s to 3s
4. Add explicit SET_STANDBY between band/mode changes

### PHASE ALIGNMENT:
Root cause of most "never decoded" phases was TX/RX using different
phase computation formulas (ms-precision vs truncated seconds).
FIXED in commit e303327. Both boards now use identical formula.
10-second SET_TIME resync loop bounds clock drift to <0.3s.

### DATA INTEGRITY:
- BER = 0.00e+00 on ALL valid packets across ALL captures
- CRC-16-CCITT: zero false passes
- GPS position data embedded in every packet
- 5-7 satellites tracked throughout
