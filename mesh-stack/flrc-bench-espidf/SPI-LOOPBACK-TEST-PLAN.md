# SPI Loopback Test Plan

## Purpose
Verify SPI signal integrity on new ESP32-C3 SuperMini boards before soldering the LR2021 radio module. This is an automated test that requires only a single jumper wire.

## Test Concept
- Connect jumper wire between D7 (MOSI/GPIO7) and D2 (MISO/GPIO2)
- Send test patterns via SPI at multiple clock speeds
- Verify received data matches sent data
- Report pass/fail for each speed

## Speed Interpretation
| Speed | Passing Means |
|-------|---------------|
| 1 MHz | Basic SPI connectivity works |
| 4 MHz | Adequate for most radio operations |
| 8 MHz | Good signal integrity |
| 18 MHz | Excellent wiring, maximum throughput possible |

## Test Procedure
1. Flash `spi_loopback.bin` to new board
2. Install jumper: D7 → D2 (MOSI to MISO)
3. Board boots, runs automated test
4. Serial output shows results for each speed
5. If all pass → SPI wiring is good, proceed to solder radio
6. If failures at high speeds → use highest passing speed

## Test Patterns
- 0x00 (all zeros)
- 0xFF (all ones)
- 0x55 (alternating 0101)
- 0xAA (alternating 1010)
- PRBS-15 (pseudo-random)

Each pattern: 1000 bytes, count errors, report PASS/FAIL.

---

## Checklist

### Phase 1: Firmware Implementation
- [ ] Create `spi_loopback.cpp` with automated SPI loopback test
- [ ] Add `CONFIG_BENCH_MODE_SPI_LOOPBACK` to `Kconfig.projbuild`
- [ ] Update `bench_main.cpp` guard to exclude SPI_LOOPBACK mode
- [ ] Update `CMakeLists.txt` to include `spi_loopback.cpp`
- [ ] Build `spi_loopback.bin`
- [ ] Test on existing board (ttyACM2) to validate firmware

### Phase 2: New Board Testing (Monday)
- [ ] Flash `spi_loopback.bin` to new board
- [ ] Install jumper D7 → D2
- [ ] Run test, verify all 4 speeds pass
- [ ] If failures: note highest passing speed, investigate GPIO pins
- [ ] Document results

### Phase 3: Hardware Preparation
- [ ] Obtain 100nF ceramic capacitor (0603 or 0805 package)
- [ ] Prepare desoldering tools (hot air or solder wick)
- [ ] Desolder LR2021 from old board (save module + antennas)

### Phase 4: Solder Radio to New Board
- [ ] Solder LR2021 to new board (all 5 GND pins connected)
- [ ] Solder decoupling capacitor (100nF VCC→GND, close to module)
- [ ] Continuity test: all connections good, no shorts
- [ ] Visual inspection under magnification

### Phase 5: Verify Radio Works
- [ ] Flash `range_tx.bin` to new board
- [ ] Verify serial shows "Radio init" success
- [ ] Verify packets being sent
- [ ] If init fails at 18 MHz: modify SPI clock speed in firmware

### Phase 6: Two-Board Range Test
- [ ] New board: `range_tx.bin`
- [ ] Existing board (C6:98): already has `range_rx.bin`
- [ ] Verify TX→RX communication
- [ ] Check NVS logging on both boards
- [ ] Flash `range_dump.bin` to recover data

---

## Parts List

### Required
| Part | Spec | Purpose | Status |
|------|------|---------|--------|
| 100nF ceramic capacitor | 0603 or 0805, 6.3V+ | LR2021 VCC decoupling | Need to obtain |

### Suggested Sources
- Amazon: "100nF 0603 capacitor" (€3-5 for 100pcs)
- Digikey/Mouser: C0603C104K5RACTU (Kemet, ~€0.10 each)
- Salvage: Dead PCBs (marked "104")

---

## Pin Reference

### ESP32-C3 SuperMini V1 GPIO Mapping
```
D0  = GPIO0   (LR2021 DIO7 - optional)
D1  = GPIO1   (LR2021 DIO8 - optional)
D2  = GPIO2   (LR2021 MISO)  ← SPI loopback test point
D3  = GPIO3   (LR2021 RST)
D4  = GPIO4   (LR2021 BUSY)
D5  = GPIO5   (LR2021 DIO9/IRQ)
D6  = GPIO6   (LR2021 SCK)
D7  = GPIO7   (LR2021 MOSI)  ← SPI loopback test point
D8  = GPIO8   (LED, inverted)
D9  = GPIO9   (BOOT button)
D10 = GPIO10  (LR2021 NSS/CS)
```

### LR2021 Module Pins (18-pin)
```
Pin 1  (VCC)   → 3.3V
Pin 2  (GND)   → GND
Pin 3  (MISO)  → D2 (GPIO2)
Pin 4  (MOSI)  → D7 (GPIO7)
Pin 5  (SCK)   → D6 (GPIO6)
Pin 6  (NSS)   → D10 (GPIO10)
Pin 7  (BUSY)  → D4 (GPIO4)
Pin 8  (GND)   → GND
Pin 9  (ANT)   → Sub-GHz antenna
Pin 10 (2.4G)  → 2.4 GHz antenna
Pin 11 (GND)   → GND
Pin 12 (GND)   → GND
Pin 14 (RST)   → D3 (GPIO3)
Pin 15 (DIO9)  → D5 (GPIO5)
Pin 16 (DIO8)  → D1 (GPIO1)
Pin 17 (DIO7)  → D0 (GPIO0)
Pin 18 (GND)   → GND
```

**Important:** Solder ALL 5 GND pins (2, 8, 11, 12, 18) for proper signal integrity.

---

## SPI Crosstalk Mitigation

### Soldering Best Practices
1. **Shortest connections** — direct solder to pads, no flying wires
2. **All 5 GND pins** — ensures solid ground return path
3. **Decoupling capacitor** — 100nF near VCC/GND filters power noise
4. **No parallel runs** — keep SPI lines from running together for long distances
5. **Visual inspection** — check for bridges between adjacent pins

### If Problems Occur
1. Lower SPI clock in `EspHalC3.h`: `dev_cfg.clock_speed_hz = 4000000;`
2. Check continuity on all GND pins
3. Verify VCC at Pin 1 is solid 3.3V
4. Look for solder bridges (especially MOSI/MISO/SCK adjacent pins)

---

## Troubleshooting

### "Radio init failed" after soldering
- Check continuity: MISO=D2, MOSI=D7, SCK=D6, NSS=D10
- Check all GND pins connected
- Check VCC at Pin 1 = 3.3V
- Try lower SPI clock speed

### SPI loopback test fails at high speed
- Check jumper wire is secure (D7→D2)
- Try shorter jumper wire
- Use highest passing speed for radio firmware
- May indicate need for manual GPIO inspection

### TX works but RX never sees packets
- Check antenna connections (Pin 9, Pin 10)
- Verify same frequency and mode on both boards
- Check RSSI values on RX side
