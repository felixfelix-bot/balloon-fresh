# Continuity Test Plan

## Purpose
Detect solder bridges and short circuits on the ESP32-C3 SuperMini after soldering the LR2021 radio module. Runs entirely on-board — no multimeter required (though recommended for verifying INCONCLUSIVE results).

## Test Design

### Three Phases

**Phase 1 — Signal-to-GND (11 pins)**
For each GPIO (D0-D10): configure as INPUT with internal pullup, read value.
If LOW → pin is shorted to GND.

**Phase 2 — Signal-to-VCC (11 pins)**
For each GPIO: configure as INPUT with internal pulldown, read value.
If HIGH → pin is shorted to VCC (3.3V).

**Phase 3 — Pin-to-pin (10 adjacent pairs)**
Uses 4-step baseline+confirmation test to minimize false positives from LR2021 internal circuitry.

### Phase 3: False Positive Mitigation (4-step test)

```
Step 1: BASELINE
  - Set both A and B as INPUT (high-Z)
  - Set B with internal pullup
  - Read B → "baseline"

Step 2: BASELINE CHECK
  - If baseline = LOW → B held low by radio circuitry
    → Mark pair as INCONCLUSIVE, skip
  - If baseline = HIGH → proceed

Step 3: DRIVE TEST
  - Set A as OUTPUT, drive LOW
  - Read B
  - If B = LOW → A pulling B down (potential short)
  - If B = HIGH → no short

Step 4: RELEASE CONFIRMATION
  - Set A back to INPUT (high-Z)
  - Read B
  - If B = HIGH → confirms reversible short
  - If B = LOW → B stuck (radio issue, not our short)
```

**Short reported only if:** baseline=HIGH, driven=LOW, released=HIGH

### Result Categories
| Result | Meaning | Action |
|--------|---------|--------|
| OK | No short detected | Safe |
| SHORT CONFIRMED | All 3 conditions met | Fix solder joint |
| INCONCLUSIVE | Pin held by radio | Verify with multimeter |

### LED Blink Patterns
```
All clear:      1 slow blink / 2s
1 short:        2 fast blinks + 2s pause
2 shorts:       3 fast blinks + 2s pause
3+ shorts:      5 fast blinks + 2s pause
```

### GPIO8/GPIO9 Special Handling
- **GPIO8 (LED):** Skip Phase 1/2 (external LED circuitry affects readings)
- **GPIO9 (BOOT):** Skip Phase 2 (physical pulldown on some boards)
- Both still tested in Phase 3 cross-pairs

---

## Checklist

### Phase A: Firmware Implementation
- [ ] Create `continuity_test.cpp` with 3-phase test
- [ ] Add `CONFIG_BENCH_MODE_CONTINUITY` to `Kconfig.projbuild`
- [ ] Update `bench_main.cpp` guard to exclude CONTINUITY mode
- [ ] Update `CMakeLists.txt` with `continuity_test.cpp`
- [ ] Build `continuity_test.bin`
- [ ] Test on existing board (ttyACM2) to validate firmware

### Phase B: Post-Soldering Verification (Monday)
- [ ] Solder LR2021 to new board (per soldering overview)
- [ ] Flash `continuity_test.bin` to newly soldered board
- [ ] Verify no shorts detected (all OK or INCONCLUSIVE)
- [ ] If SHORT CONFIRMED: fix solder joint, re-test
- [ ] If INCONCLUSIVE: verify with multimeter

### Phase C: Full Radio Verification
- [ ] Flash `spi_loopback.bin` (install jumper D7→D2)
- [ ] Verify SPI speeds pass
- [ ] Remove jumper
- [ ] Flash `range_tx.bin`
- [ ] Verify radio init succeeds
- [ ] Verify packets being sent
- [ ] Run two-board range test with existing RX board

---

## Pins Tested

### Signal Pins (Phase 1 & 2)
```
D0  = GPIO0   (LR2021 DIO7)
D1  = GPIO1   (LR2021 DIO8)
D2  = GPIO2   (LR2021 MISO)
D3  = GPIO3   (LR2021 RST)
D4  = GPIO4   (LR2021 BUSY)
D5  = GPIO5   (LR2021 DIO9/IRQ)
D6  = GPIO6   (LR2021 SCK)
D7  = GPIO7   (LR2021 MOSI)
D8  = GPIO8   (LED - Phase 1/2 skipped)
D9  = GPIO9   (BOOT - Phase 2 skipped)
D10 = GPIO10  (LR2021 NSS/CS)
```

### Cross-Pin Pairs (Phase 3)
```
D0-D1, D1-D2, D2-D3, D3-D4, D4-D5, D5-D6
D6-D7, D7-D8, D8-D9, D9-D10
```

---

## Important Notes

- Radio is **never initialized** — pins stay in reset/high-Z state
- Tests are **non-destructive** (won't damage radio)
- Run on newly soldered board **before** flashing `range_tx.bin`
- Phase 3 INCONCLUSIVE results are **expected** for some pairs — the LR2021's MISO, BUSY, and DIO pins may be held in defined states by internal circuitry
- Always verify INCONCLUSIVE results with a multimeter for certainty
