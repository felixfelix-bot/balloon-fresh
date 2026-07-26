# RX Sweep Analysis — rx_sweep_fixed2_204425.log (Post-FLRC-1300 Index Fix)

**Capture date:** 2026-07-25 20:44–20:47 UTC
**File:** `data/v4-channel-sweep/rx_sweep_fixed2_204425.log`
**Size:** 952 KB, 29,905 lines
**Firmware fixes applied (vs previous capture):**
- `7700e22` — correct FLRC-1300 index in channel sweep (wrong bitrate base)
- `536b418` — RX channelSweepMode override clobbering freqMHz
**GPS:** 32.6391°N, -16.9460°W (3–5 sats, fix=1)
**Phase coverage:** 18–64 (47 phases — RX started mid-sweep, phases 0–17 missing)

---

## 1. Full PHASE_RESULT Table (47 phases)

| Ph | Mode | Size | RX | PER | RSSI | Sats | Fix | Status |
|----|------|------|----|-----|------|------|-----|--------|
| 18 | HF-FLRC-1300 | 128 | 0 | 100.0% | -55 | 0 | 0 | ❌ FAIL |
| 19 | HF-FLRC-1300 | 255 | 10 | 90.0% | -45 | 5 | 1 | ✅ DECODE |
| 20 | HF-FLRC-2600 | 32 | 0 | 100.0% | -53 | 0 | 0 | ❌ FAIL |
| 21 | HF-FLRC-2600 | 64 | 0 | 100.0% | -53 | 0 | 0 | ❌ FAIL |
| 22 | HF-FLRC-2600 | 128 | 0 | 100.0% | -53 | 0 | 0 | ❌ FAIL |
| 23 | HF-FLRC-2600 | 255 | 3 | 97.0% | -52 | 5 | 1 | ✅ DECODE |
| 24 | HF-LoRa-SF12 | 32 | 1 | 50.0% | -16 | 5 | 1 | ✅ DECODE |
| 25 | HF-LoRa-SF12 | 64 | 1 | 0.0% | -16 | 5 | 1 | ✅ DECODE |
| 26 | HF-LoRa-SF12 | 128 | 1 | 0.0% | -15 | 5 | 1 | ✅ DECODE |
| 27 | HF-LoRa-SF12 | 255 | 1 | 0.0% | -16 | 5 | 1 | ✅ DECODE |
| 28 | LF-LoRa-SF7 | 32 | 0 | 100.0% | 0 | 0 | 0 | ❌ FAIL |
| 29 | LF-LoRa-SF7 | 64 | 18 | 10.0% | -29 | 5 | 1 | ✅ DECODE |
| 30 | LF-LoRa-SF7 | 128 | 10 | 23.1% | -29 | 5 | 1 | ✅ DECODE |
| 31 | LF-LoRa-SF7 | 255 | 6 | 14.3% | -30 | 5 | 1 | ✅ DECODE |
| 32 | LF-LoRa-SF9 | 32 | 6 | 14.3% | -25 | 5 | 1 | ✅ DECODE |
| 33 | LF-LoRa-SF9 | 64 | 2 | 33.3% | -26 | 5 | 1 | ✅ DECODE |
| 34 | LF-LoRa-SF9 | 128 | 1 | 0.0% | -26 | 4 | 1 | ✅ DECODE |
| 35 | LF-LoRa-SF9 | 255 | 1 | 0.0% | -26 | 5 | 1 | ✅ DECODE |
| 36 | LF-LoRa-SF12 | 32 | 0 | 100.0% | 0 | 0 | 0 | ❌ FAIL |
| 37 | LF-LoRa-SF12 | SKIP-64 | 0 | 0.0% | 0 | 0 | 0 | ⏭️ SKIP |
| 38 | LF-LoRa-SF12 | SKIP-128 | 0 | 0.0% | 0 | 0 | 0 | ⏭️ SKIP |
| 39 | LF-LoRa-SF12 | SKIP-255 | 0 | 0.0% | 0 | 0 | 0 | ⏭️ SKIP |
| 40 | LF-FLRC-325 | 32 | 21 | 79.0% | -48 | 3 | 1 | ✅ DECODE |
| 41 | LF-FLRC-325 | 64 | 17 | 83.0% | -52 | 3 | 1 | ✅ DECODE |
| 42 | LF-FLRC-325 | 128 | 7 | 93.0% | -44 | 3 | 1 | ✅ DECODE |
| 43 | LF-FLRC-325 | 255 | 0 | 100.0% | 0 | 0 | 0 | ❌ FAIL |
| 44 | LF-FLRC-650 | 32 | 0 | 100.0% | 0 | 0 | 0 | ❌ FAIL |
| 45 | LF-FLRC-650 | 64 | 0 | 100.0% | 0 | 0 | 0 | ❌ FAIL |
| 46 | LF-FLRC-650 | 128 | 0 | 100.0% | 0 | 0 | 0 | ❌ FAIL |
| 47 | LF-FLRC-650 | 255 | 0 | 100.0% | 0 | 0 | 0 | ❌ FAIL |
| 48 | LF-FLRC-1300 | 32 | 0 | 100.0% | 0 | 0 | 0 | ❌ FAIL |
| 49 | LF-FLRC-1300 | 64 | 0 | 100.0% | 0 | 0 | 0 | ❌ FAIL |
| 50 | LF-FLRC-1300 | 128 | 0 | 100.0% | 0 | 0 | 0 | ❌ FAIL |
| 51 | LF-FLRC-1300 | 255 | 0 | 100.0% | 0 | 0 | 0 | ❌ FAIL |
| 52 | LF-FLRC-2600 | 32 | 0 | 100.0% | 0 | 0 | 0 | ❌ FAIL |
| 53 | LF-FLRC-2600 | 64 | 0 | 100.0% | 0 | 0 | 0 | ❌ FAIL |
| 54 | LF-FLRC-2600 | 128 | 0 | 100.0% | 0 | 0 | 0 | ❌ FAIL |
| 55 | LF-FLRC-2600 | 255 | 0 | 100.0% | 0 | 0 | 0 | ❌ FAIL |
| 56 | CH-2412 | 64 | 0 | 100.0% | 0 | 0 | 0 | ❌ FAIL |
| 57 | CH-2417 | 64 | 0 | 100.0% | 0 | 0 | 0 | ❌ FAIL |
| 58 | CH-2422 | 64 | 0 | 100.0% | -55 | 0 | 0 | ❌ FAIL |
| 59 | CH-2427 | 64 | 1 | 99.0% | -54 | 3 | 1 | ✅ DECODE |
| 60 | CH-2432 | 64 | 0 | 100.0% | -55 | 0 | 0 | ❌ FAIL |
| 61 | CH-2437 | 64 | 0 | 100.0% | -55 | 0 | 0 | ❌ FAIL |
| 62 | CH-2442 | 64 | 0 | 100.0% | -54 | 0 | 0 | ❌ FAIL |
| 63 | CH-2447 | 64 | 0 | 100.0% | -55 | 0 | 0 | ❌ FAIL |
| 64 | CH-2452 | 64 | 0 | 100.0% | -55 | 0 | 0 | ❌ FAIL |

**Decode rate: 17 / 47 = 36%**

---

## 2. Decode vs Fail by Mode

| Mode Family | Decoded | Failed | Verdict |
|-------------|---------|--------|---------|
| HF-LoRa-SF12 (4 sizes) | 4 | 0 | ✅ Best — 0% PER, -16 dBm |
| LF-LoRa-SF7 (3/4) | 3 | 1 | ✅ Good — 10–23% PER (size 32 fails) |
| LF-LoRa-SF9 (4/4) | 4 | 0 | ✅ Good — 0–33% PER |
| HF-FLRC-1300 (1/2) | 1 | 1 | ⚠️ Only size 255 decodes (90% PER) |
| HF-FLRC-2600 (1/4) | 1 | 3 | ❌ Only size 255 decodes (97% PER) |
| LF-FLRC-325 (3/4) | 3 | 1 | ⚠️ Sizes 32–128 decode, 255 fails |
| LF-FLRC-650 (0/4) | 0 | 4 | ❌ All fail |
| LF-FLRC-1300 (0/4) | 0 | 4 | ❌ All fail |
| LF-FLRC-2600 (0/4) | 0 | 4 | ❌ All fail |
| LF-LoRa-SF12 (0/1) | 0 | 1 | ❌ Size 32 fails (+3 SKIP) |
| Channel sweep (1/9) | 1 | 8 | ❌ Only CH-2427 (1 pkt) |

---

## 3. Channel Sweep — PER per Frequency (WiFi 2.4 GHz, FLRC1300-64)

| Phase | Freq (MHz) | WiFi Ch | RX | PER | RSSI | CRC Err | Garbage |
|-------|------------|---------|----|-----|------|---------|---------|
| 56 | 2412 | 1 | 0 | 100.0% | 0 | 0 | 1034 |
| 57 | 2417 | 2 | 0 | 100.0% | 0 | 0 | 1022 |
| 58 | 2422 | 3 | 0 | 100.0% | -55 | 1 | 1025 |
| 59 | 2427 | 4 | 1 | 99.0% | -54 | 0 | 949 |
| 60 | 2432 | 5 | 0 | 100.0% | -55 | 1 | 953 |
| 61 | 2437 | 6 | 0 | 100.0% | -55 | 0 | 954 |
| 62 | 2442 | 7 | 0 | 100.0% | -54 | 1 | 930 |
| 63 | 2447 | 8 | 0 | 100.0% | -55 | 2 | 964 |
| 64 | 2452 | 9 | 0 | 100.0% | -55 | 2 | 1011 |

**1/9 channels decoded (CH-2427, 1 packet).** Capture was cut short — phases 65–76 (CH-2457..2472 + EU868 863–870) not captured.

**Note:** Several channels now show RSSI=-55 with CRC errors, indicating the radio IS receiving carrier energy at 2.4 GHz — but the LR2021 cannot demodulate FLRC1300 at this frequency (out of band). The energy is likely a harmonic or PCB coupling artifact.

---

## 4. Comparison to Previous Capture (rx_sweep_201758.log, pre-fix)

### 4a. Overall decode rates (different phase ranges — NOT directly comparable)

| Metric | Old (201758) | New (fixed2) |
|--------|-------------|--------------|
| Total phases | 77 unique | 47 |
| Decoded (rx>0) | 30 (39%) | 17 (36%) |
| Phase range | 0–76 (full) | 18–64 (partial) |

### 4b. Apples-to-apples: overlapping phases 18–64 only

| Metric | Old (18–64) | New (18–64) | Delta |
|--------|-------------|-------------|-------|
| Phases captured | 46* | 47 | +1 |
| Decoded | 23 (50%) | 17 (36%) | **-7** |

*Old capture missing phase 42 (LF-FLRC-325-128).

### 4c. Per-phase RX comparison (phases that changed)

| Ph | Mode | Old RX | New RX | Change |
|----|------|--------|--------|--------|
| 19 | HF-FLRC-1300-255 | 8 | 10 | ↑ +2 |
| 23 | HF-FLRC-2600-255 | 6 | 3 | ↓ -3 |
| 24 | HF-LoRa-SF12-32 | 2 | 1 | ↓ -1 |
| 29 | LF-LoRa-SF7-64 | 13 | 18 | ↑ +5 |
| 31 | LF-LoRa-SF7-255 | 7 | 6 | ↓ -1 |
| 32 | LF-LoRa-SF9-32 | 5 | 6 | ↑ +1 |
| 33 | LF-LoRa-SF9-64 | 3 | 2 | ↓ -1 |
| **36** | **LF-LoRa-SF12-32** | **1** | **0** | **↓ LOST** |
| **40** | **LF-FLRC-325-32** | **1** | **21** | **↑ +20** |
| **41** | **LF-FLRC-325-64** | **0** | **17** | **↑ GAINED** |
| **42** | **LF-FLRC-325-128** | **missing** | **7** | **↑ GAINED** |
| **43** | **LF-FLRC-325-255** | **6** | **0** | **↓ LOST** |
| **46** | **LF-FLRC-650-128** | **3** | **0** | **↓ LOST** |
| **47** | **LF-FLRC-650-255** | **3** | **0** | **↓ LOST** |
| **51** | **LF-FLRC-1300-255** | **9** | **0** | **↓ LOST** |
| **55** | **LF-FLRC-2600-255** | **3** | **0** | **↓ LOST** |
| 57 | CH-2417 | 1 | 0 | ↓ LOST |
| **59** | **CH-2427** | **0** | **1** | **↑ GAINED** |
| 60 | CH-2432 | 1 | 0 | ↓ LOST |
| 64 | CH-2452 | 1 | 0 | ↓ LOST |

---

## 5. What Changed

### ✅ Improvements
1. **LF-FLRC-325 dramatically improved**: phases 40–42 went from 1/0/missing → 21/17/7 rx. The FLRC-1300 index fix appears to have corrected the bitrate mapping for the 325 baud mode on the LF band. This is the single biggest win.
2. **HF-FLRC-1300-255 slightly better**: 8→10 rx (marginal).
3. **LF-LoRa-SF7-64 stronger**: 13→18 rx.
4. **LF-LoRa-SF9-32 stronger**: 5→6 rx.

### ❌ Regressions
1. **LF-FLRC-650/1300/2600 all regressed to ZERO**: phases 46, 47, 51, 55 previously had 3–9 rx each; now all rx=0. The index fix that helped FLRC-325 appears to have broken higher LF-FLRC bitrates. **Possible cause:** the bitrate index table mapping was shifted — what was indexed as FLRC-650/1300/2600 before now points to different (wrong) radio parameters.
2. **LF-LoRa-SF12-32 lost**: 1→0 rx (marginal — was already borderline).
3. **LF-FLRC-325-255 lost**: 6→0 rx. Only the smaller packet sizes (32–128) of FLRC-325 now decode.
4. **Channel sweep still broken**: the channelSweepMode freqMHz fix (536b418) did NOT restore channel sweep decoding. 1/9 vs 3/9 channels in old (and those 3 were spurious anyway). CH-2427 gained a packet but CH-2417/2432/2452 lost theirs — consistent with random noise, not a real fix.

---

## 6. What Still Fails

| Failure | Details |
|---------|---------|
| **All LF-FLRC-650/1300/2600** | 0 rx across all 12 phases. RSSI=0 (radio not even detecting carrier). The index fix broke these. |
| **LF-FLRC-325-255** | 0 rx (sizes 32–128 decode, 255 doesn't). |
| **HF-FLRC-1300 sizes 32/64/128** | 0 rx (only 255 decodes). |
| **HF-FLRC-2600 sizes 32/64/128** | 0 rx (only 255 decodes). |
| **LF-LoRa-SF12-32** | 0 rx (sizes 64–255 are SKIP — firmware time budget). |
| **LF-LoRa-SF7-32** | 0 rx (sizes 64–255 decode fine). Small packet + fast SF = sync timing issue. |
| **WiFi 2.4 GHz channel sweep (all)** | Out of LR2021 band. Meaningless test. |
| **EU868 sub-band sweep** | Not captured (phases 65–76 cut off). Was 100% fail in old capture. |

---

## 7. Root Cause Hypothesis

The FLRC-1300 index fix (7700e22) corrected one entry in a bitrate-to-index lookup table. This appears to have:

- **Fixed** the FLRC-325 LF mode (was using wrong radio config → now correct → massive improvement)
- **Broken** the FLRC-650/1300/2600 LF modes (were marginally working with the "wrong" index → now pointed at a different wrong config → total failure)

This suggests the **index table has a systemic offset error**, not just one wrong entry. The fix corrected FLRC-325's entry but shifted adjacent entries. The remaining LF-FLRC entries (650/1300/2600) need to be independently verified against the LR2021 datasheet bitrate register values.

The channel sweep failures are a separate issue: the channelSweepMode freqMHz fix (536b418) did not produce measurable improvement. The sweep still runs on 2.4 GHz frequencies where the LR2021 physically cannot operate.

---

## Summary

| Metric | Value |
|--------|-------|
| Phases captured | 47 (partial: 18–64) |
| Decode rate | 17/47 = 36% |
| Best mode | HF-LoRa-SF12 (0% PER, -16 dBm) |
| Best FLRC mode | LF-FLRC-325-32 (79% PER, 21 pkts) |
| Channel sweep decoded | 1/9 (CH-2427, spurious) |
| vs previous (overlapping phases) | 50% → 36% (regression) |
| Net new decoded modes | +2 (LF-FLRC-325-64, -128) |
| Net lost decoded modes | -9 (LF-FLRC-650/1300/2600, LF-SF12-32, FLRC-325-255, 3 CH) |

**Bottom line:** The FLRC-1300 index fix was a partial fix — it dramatically improved LF-FLRC-325 but broke LF-FLRC-650/1300/2600. The channel sweep fix had no effect. Net decode rate on comparable phases dropped from 50% to 36%. The bitrate index table needs full audit, not single-entry patches.
