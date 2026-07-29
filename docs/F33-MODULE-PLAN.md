# F33 Module + 2W PA Circuit Design Plan

## Key Decision: Module Switch

**From:** NiceRF LoRa2021 (bare chip, +22 dBm max output, needs external SKY66112 FEM for 2.4 GHz PA)
**To:** NiceRF LoRa2021F33-2G4 (built-in 2W PA, +33 dBm output on 433 MHz, +30 dBm on 868/915/2.4 GHz)

### What This Changes

- **No SKY66112 FEM needed** — PA is built into the F33 module
- **No TX_EN GPIO needed** — module handles PA internally
- **Simpler PCB:** fewer components, fewer traces, less impedance matching
- **Same LR2021 chip inside** — same RadioLib driver, same firmware
- **Same SPI interface** — same ESP32 GPIO assignments as validated DIY setup
- **Larger module** — 39x21mm vs 19.81x14.98mm (F33 is ~2x larger)
- **New CE pin** — LDO enable / sleep control (Pin 5), needs a new GPIO
- **Higher power supply** — 3.0-5.5V (5V for full 2W) vs 1.8-3.6V (3.3V) on bare LoRa2021
- **Industrial-grade TCXO** — 0.5ppm, internal (no VTCXO pin)
- **No DIO7/DIO8/DIO9 pins** — only IRQ (Pin 18) as digital interface

### F33 Module Specs (from official NiceRF datasheet V1.1, confirmed 18 pins, 39x21mm per LCSC)

| Spec | Value |
|------|-------|
| Model | G-NiceRF LoRa2021F33-2G4 |
| Chipset | LR2021 (same chip, Gen 4) |
| Module dimensions | 39 x 21 mm |
| Total pins | 18 (castellated, 9 per side) |
| Pin pitch | ~2.0 mm |
| Output power 433 MHz | +33 dBm (2W) |
| Output power 868/915 MHz | +30 dBm (1W) |
| Output power 2.4 GHz | +30 dBm (1W) |
| Sub-GHz sensitivity | -143 dBm (BW=62.5KHz, SF=12) |
| 2.4 GHz sensitivity | -136 dBm (BW=125KHz, SF=10) |
| TX current @433MHz 5V 2W | <1200 mA |
| TX current @868/915MHz 5V 1W | <800 mA |
| TX current @2.4GHz 5V 1W | <900 mA |
| RX current Sub-GHz | <8 mA |
| RX current 2.4G bypass ON | <9 mA |
| RX current 2.4G bypass OFF | <42 mA |
| Sleep current | <20 µA |
| Power supply | 3.0-5.5V (5V for full 2W output) |
| Interface | SPI |
| TCXO | Industrial-grade 0.5ppm (internal, no pin) |

### F33 Pinout (Confirmed — 18 pins, top view)

| Pin | Function | Type | Notes |
|-----|----------|------|-------|
| 1 | VCC | Power | 3.0-5.5V, use 5V for full 2W output |
| 2 | GND | GND | |
| 3 | GND | GND | |
| 4 | GND | GND | |
| 5 | CE | Input | Internal LDO enable. Drive high or float for operation. Pull LOW for sleep mode. 0-3.3V logic |
| 6 | GND | GND | |
| 7 | GND | GND | |
| 8 | GND | GND | |
| 9 | ANT | RF | Sub-GHz antenna (433/868/915 MHz), 50 Ohm |
| 10 | ANT-2G4 | RF | 2.4 GHz antenna, 50 Ohm |
| 11 | GND | GND | |
| 12 | SCK | Input | SPI clock, 0-3.3V |
| 13 | NSS | Input | SPI chip select, active low, 0-3.3V |
| 14 | BUSY | Output | Status indicator, 0-3.3V |
| 15 | MOSI | Input | SPI data input (MCU -> module), 0-3.3V |
| 16 | MISO | Output | SPI data output (module -> MCU), 0-3.3V |
| 17 | RESET | Input | Reset trigger, 0-3.3V |
| 18 | IRQ | Output | Multipurpose digital interface, 0-3.3V |

### ESP32-C3 GPIO Mapping (unchanged from validated DIY setup)

| ESP32 GPIO | Silkscreen | F33 Pin | Function |
|------------|------------|---------|----------|
| GPIO7 | D7 | Pin 15 | MOSI |
| GPIO6 | D6 | Pin 12 | SCK |
| GPIO2 | D2 | Pin 16 | MISO |
| GPIO10 | D10 | Pin 13 | NSS |
| GPIO4 | D4 | Pin 14 | BUSY |
| GPIO3 | D3 | Pin 17 | RESET |
| GPIO5 | D5 | Pin 18 | IRQ |
| GPIO9 | D9 | Pin 5 | CE (NEW — LDO enable / sleep control) |

### ASCII Pinout Diagram

```
          ┌──────────────────────────────────────┐
   VCC  1 │                                      │ 10 ANT-2G4
   GND  2 │                                      │ 11 GND
   GND  3 │                                      │ 12 SCK
   GND  4 │       LoRa2021F33-2G4                 │ 13 NSS
    CE  5 │       39x21mm                        │ 14 BUSY
   GND  6 │       Castellated                    │ 15 MOSI
   GND  7 │       18-pin                         │ 16 MISO
   GND  8 │                                      │ 17 RESET
   ANT  9 │                                      │ 18 IRQ
          └──────────────────────────────────────┘
          (Left: pins 1-9 top to bottom)  (Right: pins 10-18 top to bottom)
```

## Tasks

### Task 1: Update Footprint Data (DONE)

- ✅ Created F33 footprint JSON: `tracker/hardware/footprints/nicerf-lora2021f33-2g4.json`
- ✅ Created KiCad footprint: `tracker/hardware/hub_board_diy/custom.pretty/LoRa2021F33_2G4.kicad_mod`
  - 18-pin castellated module, 39x21mm body
  - 9 pins per side, 2.0mm pitch, 1.5mm offset from edge
  - Pin 1 marker at top-left corner

### Task 2: Update DIY v0.1 Board Design (DONE)

- ✅ Updated SKiDL hub schematic (`hub_schematic.py`) to use F33 pinout
- ✅ Updated KiCad schematic (`hub_board_diy.kicad_sch`) with F33 labels and pinout
- ✅ Added CE pin connection (GPIO9/D9 → F33 Pin 5)
- ✅ Removed SKY66112 FEM references from schematic files
- ✅ Removed VTCXO decoupling cap (C3) — F33 has internal TCXO
- ✅ Updated decoupling: C4 changed from 10uF to 100uF for 2W TX burst current
- ✅ Updated antenna pad labels: Pin 9 = Sub-GHz ANT, Pin 10 = 2.4G ANT-2G4
- ✅ Updated implementation plan with F33 pinout and power requirements

### Task 3: Power Supply Change (TODO — Design Decision Needed)

The F33 needs 5V for full 2W output. Current power chain:
```
Solar → BAT54 → supercap (5.5V) → TPS7A02 (3.3V LDO) → system
```

Options:
1. **Replace TPS7A02 with 5V LDO** (e.g., MCP1826S-5002, HT7550-3) — simple, but LDO dropout limits useful supercap voltage range
2. **Boost converter** (e.g., TPS61099, LTC3525) — more efficient from low supercap voltage, but adds complexity/weight
3. **Run at 3.3V** (reduced power ~+30 dBm / 1W) — simplest, no power chain change needed

⚠️ **Power budget impact:** At 2W TX, current draw spikes to 1200 mA. Supercap must handle this burst. 100uF bulk cap added (C4) but may need more.

### Task 4: Architecture — Simplified Signal Chain

```
Before (bare LR2021):
  ESP32-C3 --SPI--> LR2021 (bare) --RF--> SKY66112 FEM --TX_EN--> Antenna

After (F33 module):
  ESP32-C3 --SPI--> F33 module (LR2021 + PA integrated) --RF--> Antenna
```

Two components removed from signal chain (SKY66112 FEM + TX_EN GPIO). Fewer points of failure. Simpler PCB. But CE pin added for sleep control.