# RANGE-TEST-PLAN-MINIMAL — Optimized 3-Stop Campaign

**Goal:** Characterize E80 STM32 FLRC/LoRa radio (868 MHz, +10 dBm) with
**minimum test runs**. No unnecessary parameter sweeping.

**Date:** 2026-08-24
**Branch:** feat/2g4-sweep
**Firmware:** c70f582+ (chip self-reset on modulation change — no SWD probe needed)

---

## 1. What We Already Know

### Data summary from 3 valid sessions

| Session | Distance | C0 FLRC-650 64B | C1 FLRC-2600 64B | C2 LoRa SF7 64B | C3 LoRa SF12 64B | C4 FLRC-650 255B |
|---------|----------|-----------------|-------------------|-----------------|-------------------|-------------------|
| 2608231820 | ~0 m | 10/10 RSSI -24 | 10/10 RSSI -23 | 10/10 RSSI -20 SNR 15 | 10/10 RSSI -20 SNR 18 | 10/10 RSSI -21 |
| 2608232130 | ~0 m | 10/10 RSSI -52 | 10/10 RSSI -52 | 0/10 firmware bug | 0/10 firmware bug | 10/10 RSSI -60 |
| 2608232205 | ~218 m | 10/10 RSSI -91.5 | 0/10 sensitivity | 0/10 firmware bug | 0/10 firmware bug | 0/10 cascade failure |

### Key findings

1. FLRC-650 64B (C0): Rock solid. 0% PER at 0m and 218m. RSSI dropped
   from -24 to -91.5 dBm (~67 dB over 218m). Still perfect. Need to find
   its cliff.

2. FLRC-2600 64B (C1): Worked at 0m, DEAD at 218m (0/10). 2600 kHz has
   ~8-10 dB worse sensitivity than 650 kHz. Dead at 218m. Drop from
   further range tests.

3. LoRa SF7 64B (C2): Worked at 0m (session 1820: 10/10, SNR 15). Failed
   at 218m due to firmware bug. Firmware now fixed (c70f582). Zero valid
   LoRa range data. Must test at range.

4. LoRa SF12 64B (C3): Same as SF7. Worked at 0m (10/10, SNR 18). Failed
   at 218m due to firmware bug. Must test at range. SF12 has ~12 dB
   processing gain over SF7 — should reach significantly farther.

5. FLRC-650 255B (C4): Worked at 0m. Failed at 218m due to cascade
   failure (chip stuck after LoRa configs failed). With firmware fix,
   should work. Must re-test to confirm.

### Anchored RSSI estimates (from measured -91.5 dBm at 218m, 6 dB/doubling)

| Distance | Est. RSSI (dBm) | FLRC-650 (-105) | LoRa SF7 (-120) | LoRa SF12 (-135) |
|----------|-----------------|-----------------|-----------------|------------------|
| 218 m    | -91.5 (measured) | 14 dB margin     | 29 dB margin    | 44 dB margin     |
| 436 m    | -97.5           | 8 dB margin      | 23 dB margin    | 38 dB margin     |
| 872 m    | -103.5          | 2 dB (cliff!)    | 17 dB margin    | 32 dB margin     |
| 1744 m   | -109.5          | dead             | 11 dB margin    | 26 dB margin     |
| 3488 m   | -115.5          | dead             | 5 dB margin     | 20 dB margin     |

Sensitivity figures estimated from SX1280 datasheet. Actual LR2021 may differ.

---

## 2. Distance Strategy: 3 Stops (2 new + optional 4th)

Binary doubling from 218m. Each doubling = 6 dB path loss. Maps directly
to sensitivity margins.

| Stop | Distance | Rationale |
|------|----------|-----------|
| R1 (done) | 218 m | Baseline. FLRC-650 works. Others failed (firmware bug). |
| R2 | 436 m | +6 dB. FLRC-650 should still work (8 dB margin). LoRa first real range test. FLRC-650 255B re-test. |
| R3 | 872 m | +12 dB. FLRC-650 cliff zone (~2 dB margin). LoRa SF7 should work (~17 dB). LoRa SF12 easy (~32 dB). |
| R4 (opt) | 1744 m | Only if R3 shows FLRC-650 still alive. FLRC-650 dead. LoRa SF7 edge. LoRa SF12 still strong. |

Why doubling, not golden ratio: 6 dB steps map to sensitivity margins.
Golden ratio (1.618x) gives 4 dB steps — too fine for 3-4 stops. Doubling
maximizes cliff-edge separation between configs.

---

## 3. Config Decisions

| Config | Verdict | Rationale |
|--------|---------|----------|
| 0 FLRC-650 64B | KEEP all stops | Baseline. Need to find cliff. Only real range data. |
| 1 FLRC-2600 64B | DROP all stops | Dead at 218m. Worse sensitivity. Zero info from farther. Revisit only with +22 dBm PA. |
| 2 LoRa SF7 64B | KEEP all stops | Zero valid range data. Must test with fixed firmware. Most relevant for balloon telemetry. |
| 3 LoRa SF12 64B | KEEP all stops | Zero valid range data. Long-range mode. Need to characterize. |
| 4 FLRC-650 255B | R2 only | Failed at 218m due to cascade. Re-test at 436m to confirm fix. Same modulation/sensitivity as 64B — if R2 confirms parity, drop from R3. |

---

## 4. Concrete Test Matrix

### Primary plan: 2 new stops, 7 total config runs

|          | C0 FLRC-650 64B | C1 FLRC-2600 64B | C2 LoRa SF7 64B | C3 LoRa SF12 64B | C4 FLRC-650 255B | Total |
|----------|:---:|:---:|:---:|:---:|:---:|:---:|
| 218m done | X (10/10) | X (0/10) | X (0/10 bug) | X (0/10 bug) | X (0/10 cascade) | 5 |
| R2 436m  | X | — DROPPED | X | X | X | 4 |
| R3 872m  | X | — DROPPED | X | X | — *1 | 3 |

\*1: Only test C4 at R3 if R2 shows 255B failing while 64B works. If R2
confirms parity, skip at R3.

Total new cells: 4 + 3 = 7. Active test time: ~35 min. Field time incl
travel: ~1.5 hours.

### Extended plan: +1 stop if R3 shows FLRC-650 alive

|          | C0 | C2 | C3 | Total |
|----------|:---:|:---:|:---:|:---:|
| R4 1744m | X | X | X | 3 |

Extended total: 7 + 3 = 10 new config runs.

---

## 5. Expected Outcomes and Decision Tree

R2 at 436m (4 configs):
- C0 FLRC-650 64B: expect 10/10 (8 dB margin). If 0/10, check for
  obstruction. If partial, cliff is near 436m — adjust R3 to 500m.
- C2 LoRa SF7: expect 10/10 (23 dB margin). If 0/10, firmware self-reset
  still broken — debug before R3.
- C3 LoRa SF12: expect 10/10 (38 dB margin). If 0/10, same firmware issue.
- C4 FLRC-650 255B: expect 10/10 (8 dB margin, same as 64B). If 0/10
  while 64B works, self-reset does not fix 255B issue — investigate
  separately, still go to R3 without 255B.

R3 at 872m (3 configs):
- C0 FLRC-650 64B: expect 0-10/10 (cliff zone, ~2 dB margin). If 10/10,
  go to R4. If partial, cliff at ~872m. If 0/10, cliff between 436-872m.
- C2 LoRa SF7: expect 10/10 (17 dB margin). If partial/0, SF7 cliff
  near 872m.
- C3 LoRa SF12: expect 10/10 (32 dB margin). If partial, check for
  obstruction. SF12 should have huge margin.

R4 at 1744m (optional, 3 configs):
- C0 should be dead. C2 SF7 entering edge (~11 dB margin). C3 SF12
  still strong (~26 dB margin). Run only if R3 C0 was 10/10.

---

## 6. What This Plan Gives You

After 2 new stops (R2 + R3):

| Characteristic | Answer |
|----------------|--------|
| FLRC-650 64B range | Cliff bracketed 436-872m (or go R4) |
| FLRC-2600 range | < 218m confirmed dead (intentional skip) |
| LoRa SF7 range | First real range data at 436m and 872m |
| LoRa SF12 range | Working at both stops, may need R4 for cliff |
| Payload size 64B vs 255B | Confirmed identical or separate issue found |
| Firmware fix validation | LoRa at range with self-reset confirmed |

What you will NOT get (acceptable):
- Exact cliff distance for FLRC-650 (bracketed to 2:1 range)
- Exact cliff for LoRa SF12 (may need R4)
- FLRC-2600 at range (dead, intentional)
- PER vs distance curve shape (2-3 points per config, first-order only)

---

## 7. Practical Notes

### Pre-test (both boards, every stop)
1. Flash both boards with firmware c70f582+. Self-reset fix required.
2. Verify with ID? command — check commit hash.
3. Antennas finger-tight before power-on. Never TX into bare SMA.
4. RX stationary at lat 32.6420447, lon -16.9556977 (same as 2608232205).
5. TX: walk/drive to distance. GPS-measure from RX position. Aim for LOS.

### Config order per stop (matters for self-reset)

C1 FLRC-2600 is skipped entirely. Do not load it.

### At R2 (436m): 4 configs, ~20 min
1. Walk to ~436m from RX position
2. C0 (FLRC-650 64B): 12 pkts, ~35s
3. C2 (LoRa SF7 64B): 12 pkts, ~2 min (SF7 ~0.1s/pkt)
4. C3 (LoRa SF12 64B): 12 pkts, ~5 min (SF12 ~2.5s/pkt)
5. C4 (FLRC-650 255B): 12 pkts, ~35s
6. Total active: ~8 min + setup

### At R3 (872m): 3 configs, ~15 min
1. Walk to ~872m from RX position
2. C0 (FLRC-650 64B): ~35s
3. C2 (LoRa SF7 64B): ~2 min
4. C3 (LoRa SF12 64B): ~5 min
5. Skip C4 unless R2 showed 255B failing
6. Total active: ~8 min + setup

### Data to record per stop
- TX GPS (lat/lon), RX GPS (same fixed)
- Actual GPS-measured distance
- Antenna heights (both ends)
- LOS description (clear, partial, terrain)
- Weather, time of day
- Anomalies (people, vehicles, RF interference)

---

## 8. Summary

| Metric | Value |
|--------|-------|
| New stops | 2 (R2: 436m, R3: 872m) |
| Optional stop | R4: 1744m (only if R3 C0 alive) |
| Configs per stop | 4 at R2, 3 at R3 |
| Total new runs | 7 (or 10 with R4) |
| Active test time | ~35 min (or ~50 min with R4) |
| Total field time | ~1.5 hours (or ~2.5 hours with R4) |
| Dropped config | FLRC-2600 (dead at 218m) |
| Key risk | LoRa could still fail if self-reset has edge cases |
