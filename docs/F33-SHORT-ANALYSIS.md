# F33 Board Short Analysis — 2026-07-30

## Summary
- Starting shorts: 44 (blind seg2()/via2() placement)
- After Router + pad pitch fix: 16 shorts remain
- Root cause of all remaining: rt.connect() auto-routes SPI signals on F.Cu crossing each other

## Remaining 16 Shorts (8 unique issues)

### 1. SPI0_NSS ↔ LR2021_CE (2x) — GUI-FIXABLE
- **Location:** CE trace at (49,31.51) F.Cu, NSS pad at (57,31)
- **Cause:** CE exits B.Cu via at (49,31.51) and routes on F.Cu to RP2040, crossing NSS auto-route
- **Fix:** Route CE entirely on B.Cu to RP2040 pin

### 2. SPI0_NSS ↔ LR2021_BUSY — GUI-FIXABLE
- **Location:** NSS auto-route at (57,31), BUSY pad at (57,29)
- **Cause:** rt.connect() auto-routes NSS on F.Cu across BUSY pad
- **Fix:** Replace NSS rt.connect() with B.Cu Manhattan routing (x=55 column)

### 3. SPI0_MISO ↔ SPI0_MOSI — GUI-FIXABLE
- **Location:** MISO/MOSI auto-routes crossing on F.Cu
- **Cause:** Both use rt.connect() which picks same F.Cu path
- **Fix:** Route MOSI on B.Cu (x=53), MISO on B.Cu (x=52)

### 4. LR2021_RST ↔ SPI0_MISO — GUI-FIXABLE
- **Location:** RST auto-route crosses MISO auto-route
- **Cause:** rt.connect() overlap
- **Fix:** Route RST on B.Cu (x=51)

### 5. 3V3 ↔ VCAP (3x) — GUI-FIXABLE
- **Location:** VCAP via at (6.5,40), 3V3 trace at (6,38) B.Cu
- **Cause:** Via too close to 3V3 B.Cu trunk
- **Fix:** Move VCAP via to (8,40), 3V3 trunk at x=12

### 6. RF_2G4_2400 ↔ ESP_TX_RP2040_RX (2x) — GUI-FIXABLE
- **Location:** ESP_TX via at (58,36.59), RF_2G4 pad at (57,37)
- **Cause:** Via 1.4mm from RF pad
- **Fix:** Move ESP_TX via to (56,36.59)

### 7. SOLAR_IN ↔ GPS_TX_ESP_RX — FOOTPRINT CONFLICT
- **Location:** SOLAR TH pad at (4,46.73), GPS TH pad at (6,46.27)
- **Cause:** Through-hole pads too close (2.5mm center-to-center)
- **Fix:** Move solar connector from (4,48) to (2,48)

### 8. I2C_SCL ↔ GND via — GUI-FIXABLE
- **Location:** SCL trace at y=25 B.Cu, GND via at (28,25)
- **Cause:** GND via on SCL B.Cu path
- **Fix:** Move GND via to (28,20) or route SCL at y=26

### 9. VCAP ↔ GND — FOOTPRINT CONFLICT
- **Location:** C8 (now at 22,37) GND pad, VCAP trace
- **Cause:** C8 was moved but VCAP route still passes through old area
- **Fix:** Verify C8 VCAP trace connects to new x=22 position

### 10. RF_SUB_868 ↔ C9 GND — GUI-FIXABLE
- **Location:** RF_SUB trace at (18,21), C9 GND pad at (18.85,19)
- **Cause:** Trace starts at F33 pad edge, too close to C9
- **Fix:** Route RF_SUB at x=15 immediately from F33 pad

## Classification
- GUI-fixable (delete trace + interactive router): 13 of 16
- Footprint placement conflict (move component): 3 of 16
- rt.connect() auto-route crossing (replace with B.Cu Manhattan): 8 of 16

## Recommended GUI Workflow
1. Open hub_board_f33.kicad_pcb in KiCad
2. Run DRC (Inspect → Design Rules Checker)
3. For each SPI signal (SCK/NSS/MOSI/MISO/BUSY/RST/IRQ): delete the rt.connect() trace, press X to interactively re-route on B.Cu
4. For VCAP↔GND and SOLAR↔GPS: move components in footprint editor
5. Re-run DRC, verify 0 shorts
6. Fill zones (B.Cu GND pour)
7. Export new gerbers

## History
| Version | Shorts | Key Change |
|---------|--------|------------|
| v1 (original) | 44 | Blind seg2()/via2() placement |
| v2 (Router) | 27 | Router class + U1 pad pitch 1.5→2.54mm |
| v3 (B.Cu power) | 19 | 3V3+VCAP power bus to B.Cu |
| v4 (more B.Cu) | 15 | UART+I2C to B.Cu |
| v5 (surgical) | 16 | C8 move, lane shifts, CE/GND/RF reroutes |
