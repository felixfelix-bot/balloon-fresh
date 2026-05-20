# Implementation Plan — DIY v0.1 Dev Board

## Overview

This plan covers all steps from current state (working firmware, verified pin mapping) through to a fully tested hardware prototype on the DIY v0.1 hub board. The board will be fabricated using toner transfer at c-base Berlin.

## Prerequisites (Already Done)

- [x] Firmware compiles successfully with RadioLib v7.6.0 + LR2021
- [x] ESP32-C3_Mini_V1 dev board pinout verified (see `hardware/footprints/esp32c3-mini-v1.json`)
- [x] NiceRF LoRa2021 footprint data captured (see `hardware/footprints/nicerf-lora2021.json`)
- [x] GPIO pin mapping verified: all 9 firmware GPIOs accessible on dev board header
- [x] Strapping pin conflicts analyzed: no blocking conflicts
- [x] Wiring reference CSV created (see `hardware/footprints/wiring-dev-board.csv`)

## Phase 1: Breadboard Validation (No PCB needed)

**Goal**: Verify firmware runs on actual ESP32-C3_Mini_V1 hardware with LoRa2021 module on breadboard.

### Step 1.1: Prepare Dev Board
- [ ] Solder header pins to ESP32-C3_Mini_V1 (if not pre-soldered)
- [ ] Plug into breadboard
- [ ] Connect USB-C cable, verify `/dev/ttyACM0` appears
- [ ] Test with `idf.py -p /dev/ttyACM0 monitor` — see boot messages
- [ ] Flash a blink test to verify GPIO8 LED works (inverted: LOW = on)

### Step 1.2: Wire LoRa2021 on Breadboard
- [ ] Wire connections per `hardware/footprints/wiring-dev-board.csv`:
  ```
  ESP32 D7 (GPIO7)  → LoRa2021 Pin 4 (MOSI)
  ESP32 D6 (GPIO6)  → LoRa2021 Pin 5 (SCK)
  ESP32 D2 (GPIO2)  → LoRa2021 Pin 3 (MISO)
  ESP32 D10 (GPIO10) → LoRa2021 Pin 6 (NSS)
  ESP32 D4 (GPIO4)  → LoRa2021 Pin 7 (BUSY)
  ESP32 D3 (GPIO3)  → LoRa2021 Pin 14 (RST)
  ESP32 D5 (GPIO5)  → LoRa2021 Pin 15 (DIO9)
  ESP32 3V3         → LoRa2021 Pin 1 (VCC)
  ESP32 GND         → LoRa2021 Pins 2,8,11,12,18
  ```
- [ ] Add decoupling: 100nF cap + 10uF cap between VCC and GND near LoRa2021
- [ ] Attach 16.4cm wire to LoRa2021 Pin 9 (ANT) for 868 MHz
- [ ] Keep wire lengths short (<5cm for SPI lines)

### Step 1.3: Flash and Test Firmware
- [ ] `source ~/esp/esp-idf/export.sh && cd firmware && idf.py build`
- [ ] `idf.py -p /dev/ttyACM0 flash monitor`
- [ ] Verify boot messages: "LR2021 initialized OK"
- [ ] Check for SPI errors (indicates wiring issue)
- [ ] Monitor TX cycles (60-second interval)
- [ ] Check current draw: ~20mA idle, ~120mA during TX burst

### Step 1.4: Wire BMP280 (Optional)
- [ ] Connect BMP280 breakout:
  ```
  ESP32 D8 (GPIO8) → BMP280 SDA
  ESP32 D9 (GPIO9) → BMP280 SCL
  ESP32 3V3        → BMP280 VCC
  ESP32 GND        → BMP280 GND
  ```
- [ ] Note: LED on GPIO8 will flicker during I2C reads (cosmetic)
- [ ] Verify temperature/pressure readings in serial output

### Step 1.5: LoRa Range Test
- [ ] Set up a second ESP32-C3_Mini_V1 + LoRa2021 as receiver (or use SDR)
- [ ] Test at increasing distances: 10m, 100m, 500m, 1km
- [ ] Verify packet reception at 868 MHz, SF9, +22 dBm
- [ ] Log RSSI/SNR at receiver end
- [ ] Expected range with wire dipole: ~1-5 km ground-level, ~100-480 km line-of-sight

## Phase 2: KiCad PCB Design

**Goal**: Design the DIY v0.1 hub board in KiCad, ready for toner transfer fabrication.

### Step 2.1: Install and Set Up KiCad
- [ ] `sudo apt install kicad`
- [ ] Create KiCad project: `hardware/hub_board_diy/hub_board_diy.kicad_pro`
- [ ] Configure design rules:
  - Min trace width: 0.4mm
  - Min clearance: 0.4mm
  - Min pad size: 1.5mm diameter
  - Drill sizes: 0.8mm (headers), 1.0mm (antenna pads)
  - No vias
  - Single-sided (bottom copper only)

### Step 2.2: Create Custom Footprints
- [ ] **NiceRF LoRa2021 footprint**: Create from `hardware/footprints/nicerf-lora2021.json`
  - 18 castellated pads, 1.29mm pitch, 19.81x14.98mm body
  - Left: 9 pads (top to bottom: ANT, GND, BUSY, NSS, SCK, MOSI, MISO, GND, VCC)
  - Right: 9 pads (top to bottom: 2.4G, GND, GND, VTCXO, RST, DIO9, DIO8, DIO7, GND)
  - Pad size: 1.0mm x 1.5mm (castellated, extending to board edge)
- [ ] **ESP32-C3_Mini_V1 footprint**: Create 2x8 through-hole header (2.54mm pitch)
  - 22.52 x 18mm board outline (reference, not copper)
  - Pin 1 marker for orientation
  - Pin mapping per `hardware/footprints/esp32c3-mini-v1.json`

### Step 2.3: Schematic Design
- [ ] Place U1 (ESP32-C3_Mini_V1) symbol with 16 header pins
- [ ] Place U2 (LoRa2021) symbol with 18 pins
- [ ] Place U3 (BMP280 breakout) symbol with 4 pins
- [ ] Place C1-C4 (decoupling caps)
- [ ] Place AE1, AE2 (antenna pad symbols)
- [ ] Place J1 (debug header, optional)
- [ ] Place SB1, SB2 (solder bridge pairs for SCK/MOSI swap)
- [ ] Wire SPI bus via solder bridges:
  - GPIO6(D6) → SB1 pad A1, SB1 pad B1 → LoRa2021 SCK (Config A: straight)
  - GPIO7(D7) → SB2 pad A2, SB2 pad B2 → LoRa2021 MOSI (Config A: straight)
  - Cross-routed traces allow Config B: D6→MOSI, D7→SCK
- [ ] Wire SPI direct: GPIO2→MISO, GPIO10→NSS
- [ ] Wire control: GPIO4→BUSY, GPIO3→RST, GPIO5→DIO9
- [ ] Wire I2C: GPIO8→SDA, GPIO9→SCL
- [ ] Wire power: 3V3→VCC, GND→GND (all ground pins)
- [ ] Wire RF: ANT pad (Pin 9), 2.4G pad (Pin 10)
- [ ] Wire decoupling caps near VCC pins
- [ ] Assign net names: SPI_SCK, SPI_MISO, SPI_MOSI, SPI_CS, LR_BUSY, LR_RST, LR_IRQ, I2C_SDA, I2C_SCL, VCC_3V3, GND, RF_SUBGHZ, RF_24GHZ
- [ ] Electrical rules check (ERC)

### Step 2.4: PCB Layout
- [ ] Board outline: 45 x 38 mm rectangle with rounded corners
- [ ] Component placement:
  - ESP32-C3_Mini_V1: left side, oriented with USB-C toward board edge
  - LoRa2021: right side, ANT pad toward board edge for antenna wire
  - BMP280: bottom-left corner
  - Decoupling caps: between ESP32 and LoRa2021, near VCC pins
  - Antenna pads: right edge of board, accessible for soldering wires
- [ ] Route SPI bus via solder bridge pads:
  - D6 and D7 traces go to SB1/SB2 pad clusters (4 pads each, cross-routed)
  - MISO and NSS are direct (no bridge needed)
  - SCK and MOSI emerge from solder bridge output pads
  - Route crossed traces around pad cluster (no via needed)
- [ ] Route control signals: BUSY, RST, IRQ
- [ ] Route I2C: SDA, SCL (short traces, <20mm)
- [ ] Route power: VCC_3V3 as thicker trace (0.6mm), star topology from ESP32 3V3 pin
- [ ] Route GND: fill remaining bottom copper as ground plane, with gaps for signal traces
- [ ] Add antenna wire solder pads (2mm x 3mm oval pads)
- [ ] Add mounting holes (2x M2, optional)
- [ ] Add silkscreen labels: component references, pin functions, board name "DIY v0.1"
- [ ] Design rules check (DRC): 0 errors, 0 warnings
- [ ] Review all traces for accidental shorts, missing connections

### Step 2.5: Export for Fabrication
- [ ] Export bottom copper layer as **mirrored B&W PDF** (for toner transfer printing)
- [ ] Export board outline as **SVG** (for FR4 cutting guide)
- [ ] Export drill map as **PDF** (for Platinenbohrmaschine)
- [ ] Export assembly diagram as **PDF** (component placement reference)
- [ ] Optional: export Gerber files for future JLCPCB order
- [ ] Save all exports to `hardware/hub_board_diy/export/`

## Phase 3: PCB Fabrication at c-base Berlin

**Goal**: Fabricate the board using toner transfer method at c-base workshop.

### Step 3.1: Prepare Material
- [ ] Cut FR4 board to 45 x 38 mm (using c-base shear or saw)
- [ ] Clean copper surface with isopropyl alcohol
- [ ] Print bottom copper pattern on **laser printer** using glossy/transfer paper (c-base laser printer)
- [ ] Verify print quality: all traces visible, no smudges, pads clear

### Step 3.2: Toner Transfer
- [ ] Place print face-down on copper side of FR4
- [ ] Use c-base Bügelpresse (iron press): ~180°C, ~2-3 minutes, even pressure
- [ ] Let board cool for 5 minutes
- [ ] Soak in water to soften paper, then gently rub off paper
- [ ] Inspect: all traces transferred cleanly? Touch up with permanent marker if needed

### Step 3.3: Etching
- [ ] Prepare etching bath (c-base Ätzbad): ferric chloride or sodium persulfate
- [ ] Immerse board, agitate gently
- [ ] Etch for 10-15 minutes until exposed copper is removed
- [ ] Remove board, rinse thoroughly with water
- [ ] Clean off toner with acetone
- [ ] Final inspection: no shorts, no broken traces, all pads isolated

### Step 3.4: Drilling
- [ ] Use c-base Platinenbohrmaschine (drill press)
- [ ] Drill header pin holes: 0.8mm diameter
  - ESP32-C3_Mini_V1: 16 holes (2x8 header)
  - BMP280 breakout: 4 holes
  - Debug header (optional): 6 holes
  - Antenna pads: 2 holes (1.0mm)
- [ ] Deburr holes if needed

### Step 3.5: Soldering
- [ ] Solder female header sockets for ESP32-C3_Mini_V1 (board plugs in from top)
- [ ] Solder LoRa2021 castellated pads flat on board surface
  - Apply flux to all 18 pads
  - Tin pads lightly, then position module
  - Solder one corner pad, check alignment, then solder remaining pads
  - Use fine tip iron, 0.5mm solder
- [ ] Solder BMP280 header pins
- [ ] Solder 0805 decoupling caps (C1-C4)
- [ ] Solder antenna wires:
  - 16.4cm wire to ANT pad (868 MHz Sub-GHz)
  - 3.1cm wire to 2.4G pad (optional for DIY v0.1)
- [ ] Solder bridges SB1+SB2: blob solder straight across (Config A: D6=SCK, D7=MOSI)
  - If SPI init fails after first test: desolder with wick, re-solder crossed (Config B)
- [ ] Inspect all joints under magnification: no bridges, no cold joints

## Phase 4: Integration Test

**Goal**: Verify the assembled PCB works as a complete system.

### Step 4.1: Initial Power-Up
- [ ] Plug ESP32-C3_Mini_V1 into the socket on hub board
- [ ] Connect USB-C cable
- [ ] Check for shorts: 3V3 to GND resistance should be >1kΩ
- [ ] Power on: measure 3.3V on VCC rail (multimeter)
- [ ] Check current draw: <50mA expected at idle

### Step 4.2: Firmware Flash and Test
- [ ] `idf.py -p /dev/ttyACM0 flash monitor`
- [ ] Verify "LR2021 initialized OK" message
- [ ] Check BMP280 readings (temp, pressure)
- [ ] Monitor TX cycles at 60-second interval
- [ ] Check current draw during TX: should spike to ~120mA, then drop back

### Step 4.3: RF Verification
- [ ] Use second LoRa2021 board or SDR to verify 868 MHz transmission
- [ ] Check frequency accuracy: should be within +/-10 kHz of 868.0 MHz
- [ ] Measure TX power with power meter or SDR: expect +22 dBm
- [ ] Test reception at 10m, 100m, 500m+ distances

### Step 4.4: Power Budget Verification
- [ ] Measure sleep current (should be <1mA with LoRa2021 in sleep)
- [ ] Measure active TX current (should be ~120mA peak)
- [ ] Calculate duty cycle power budget
- [ ] Verify deep sleep mode works (future: needed for solar operation)

## Phase 5: Enclosure and Field Prep (Optional for DIY)

- [ ] 3D print or craft a lightweight enclosure
- [ ] Add solar cell connectors (or test with bench supply simulating solar)
- [ ] Add supercapacitor power supply circuit
- [ ] Test complete solar → supercap → LDO → system power chain
- [ ] Outdoor range test with solar power

## File Inventory (Created/Updated in This Phase)

| File | Description |
|------|-------------|
| `hardware/footprints/esp32c3-mini-v1.json` | Full ESP32-C3_Mini_V1 pinout, specs, firmware GPIO map |
| `hardware/footprints/esp32c3-mini-v1.csv` | Pin table in CSV format |
| `hardware/footprints/wiring-dev-board.csv` | Complete firmware-to-hardware wiring reference |
| `hardware/footprints/nicerf-lora2021.json` | LoRa2021 footprint data (existing) |
| `hardware/hub_board_diy/plan.md` | PCB design plan with verified pin mapping |
| `hardware/hub_board_diy/implementation-plan.md` | This file |
| `AGENTS.md` | Updated with correct dev board info |

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| LoRa2021 doesn't respond to SPI | Medium | High | Test on breadboard first (Phase 1); solder bridges SB1/SB2 allow swapping SCK/MOSI without rewiring |
| GPIO6/7 swapped vs expected | Low | Medium | Solder bridges SB1/SB2 on PCB — just re-blob crossed instead of straight; update firmware `#define` |
| GPIO4-7 conflict with flash | Low | Critical | Verified: these are user GPIO, not flash pins (ESP32-C3 flash uses GPIO11-17) |
| Toner transfer quality poor | Medium | Medium | Practice on scrap FR4; use laser printer with good resolution |
| LoRa2021 castellated pads hard to solder | Medium | Medium | Use flux, fine tip iron, practice on spare module first |
| Boot fails due to strapping pins | Low | High | Verified: GPIO2 (MISO) is high-Z at boot, GPIO8/9 defaults are OK |
| U.FL antenna switch not configured | Low | Low | Some boards need solder bridge; check with continuity tester |
| RF emissions from breadboard | High | Low | Breadboard test is for functionality, not range; PCB will be better |

## Timeline Estimate

| Phase | Duration | Dependencies |
|-------|----------|-------------|
| Phase 1: Breadboard | 1-2 days | Hardware in hand |
| Phase 2: KiCad Design | 2-3 days | KiCad installed, footprints created |
| Phase 3: PCB Fabrication | 1 day at c-base | KiCad design complete, FR4 stock |
| Phase 4: Integration Test | 1-2 days | Assembled board |
| **Total** | **5-8 days** | |
