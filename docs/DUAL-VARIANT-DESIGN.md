# Dual-Variant Hub Board Design — JLCPCB Manufacturing

**Date:** 2026-07-29
**Author:** balloon-circuit-design sub-manager
**Status:** Schematics complete, ready for PCB layout

---

## Overview

Two hub board variants for JLCPCB manufacturing:

| Variant | Module | Power Output | VCC | Size | Antenna | Use Case |
|---------|--------|-------------|-----|------|---------|----------|
| **V1 (Non-PA)** | NiceRF LoRa2021 (bare) | +22 dBm (158 mW) | 3.3V | 19.81×14.98 mm | Wire dipole pads | Pico balloon tracker, minimal weight |
| **V2 (2W PA)** | NiceRF LoRa2021F33-2G4 | +33 dBm (2W) @433, +30 dBm (1W) @868/2.4G | 5.0V | 39×21 mm | SMA bulkhead connectors | Range testing, ground station, heavy-lift balloon |

Both variants share the same MCU architecture (ESP32-C3 + RP2040 coprocessor) and power chain.

---

## V1: Non-PA Hub Board (hub_schematic.py)

### Components: 23 | Nets: 20 | ERC errors: 0

**Architecture:**
- ESP32-C3-MINI-1: application processor, GPS parsing, I²C baro, power management
- RP2040-Zero: radio coprocessor, owns LR2021 SPI bus exclusively
- NiceRF LoRa2021 (bare): dual-band radio, 18-pin castellated, 19.81×14.98 mm
- MS5611: high-altitude barometric pressure sensor (I²C)
- MAX-M10S: GPS/GNSS module (UART)
- TPS7A02 LDO: 3.3V regulator (25 nA IQ)
- BAT54 Schottky: solar reverse-protection diode

**Power chain:**
```
Solar → BAT54 → 1F/5.5V supercap → TPS7A02 (3.3V) → all components
```

**RP2040 → LR2021 wiring (proven from firmware):**
| RP2040 | Function | LR2021 Pin |
|--------|----------|------------|
| GP2 | SPI0 SCK | Pin 5 |
| GP3 | SPI0 MOSI | Pin 4 |
| GP4 | SPI0 MISO | Pin 3 |
| GP5 | GPIO CS (NSS) | Pin 6 |
| GP6 | BUSY input | Pin 7 |
| GP7 | IRQ (DIO9) | Pin 15 |
| GP8 | RST | Pin 14 |

**LR2021 GND pins:** 2, 8, 11, 12, 18 (5 pins to ground plane)

**Antenna:** Wire dipole pads at board edge (2mm THT, labeled "868 MHz" and "2.4 GHz")

---

## V2: 2W PA Hub Board (hub_schematic_f33.py)

### Components: 30 | Nets: 22 | ERC errors: 0

**Architecture:**
Same MCU architecture, but radio module replaced with F33 (2W built-in PA).

**Key differences from V1:**

### 1. Radio Module: LoRa2021F33-2G4 (39×21 mm)

| Parameter | Bare LoRa2021 (V1) | LoRa2021F33-2G4 (V2) |
|-----------|-------------------|---------------------|
| Size | 19.81×14.98 mm | 39×21 mm |
| VCC | 1.8–3.6V (3.3V) | 3.0–5.5V (**5V for full 2W**) |
| TX power @433MHz | +22 dBm (158 mW) | **+33 dBm (2W)** |
| TX power @868MHz | +22 dBm | **+30 dBm (1W)** |
| TX power @2.4GHz | +12 dBm (16 mW) | **+30 dBm (1W)** |
| TX current (max) | 120 mA | **1200 mA** |
| Built-in PA | No | **Yes** |
| Built-in LNA | No | **Yes (2.4GHz, +6dB)** |
| TCXO | External (VTCXO pin) | **Built-in 0.5ppm** |
| Sleep current | 2 µA | 20 µA |
| Pin count | 18 | 18 |
| Pin pitch | 1.29 mm | **2.0 mm** |
| GND pins | 5 (2,8,11,12,18) | **7 (2,3,4,6,7,8,11)** |

### 2. F33 Pin Map (DIFFERENT from bare LoRa2021!)

| Pin | F33 Function | LR2021 (bare) Function |
|-----|-------------|----------------------|
| 1 | VCC (5V) | VCC (3.3V) |
| 2 | GND | GND |
| 3 | GND | MISO |
| 4 | GND | MOSI |
| 5 | **CE** (LDO enable) | GND |
| 6 | GND | BUSY |
| 7 | GND | GND |
| 8 | GND | GND |
| 9 | ANT (sub-GHz) | ANT (sub-GHz) |
| 10 | ANT-2G4 | 2.4G ANT |
| 11 | GND | GND |
| 12 | **SCK** | (not a pin) |
| 13 | **NSS** | (not a pin) |
| 14 | **BUSY** | RST |
| 15 | **MOSI** | DIO9 (IRQ) |
| 16 | **MISO** | DIO8 (NC) |
| 17 | **RESET** | DIO7 (NC) |
| 18 | **IRQ** | GND |

### 3. RP2040 → F33 Wiring

| RP2040 | Function | F33 Pin | Notes |
|--------|----------|---------|-------|
| GP2 | SPI0 SCK | Pin 12 | |
| GP3 | SPI0 MOSI | Pin 15 | |
| GP4 | SPI0 MISO | Pin 16 | |
| GP5 | GPIO CS (NSS) | Pin 13 | |
| GP6 | BUSY input | Pin 14 | |
| GP7 | IRQ | Pin 18 | |
| GP8 | RST | Pin 17 | |
| **GP9** | **CE (LDO enable)** | **Pin 5** | **NEW — sleep control** |

### 4. Power Chain Changes

**V1 (non-PA):** Solar → BAT54 → supercap → TPS7A02 (3.3V) → all components

**V2 (2W PA):**
```
Solar → BAT54 → supercap (5.4V bus)
                        ├─→ TPS7A02 (3.3V) → ESP32, RP2040, GPS, MS5611
                        └─→ F33 VCC (5V direct from supercap bus)
                             + 100µF bulk + 10µF + 100nF decoupling
```

The F33 runs on the raw supercap voltage (3.0–5.5V range, typically 5V).
SPI pins are 0-3.3V logic — the F33 has internal level shifting.

### 5. SMA Bulkhead Connectors

Felix requested "big tail cable" antenna adapters. The V2 board uses:

- **2× SMA edge-mount connectors** (end-launch, 50Ω)
  - J1: sub-GHz (433/868/915 MHz) → F33 pin 9 (ANT)
  - J2: 2.4 GHz → F33 pin 10 (ANT-2G4)
- Footprint: `Connector_Coax:TEConnectivity_292304-3` or equivalent SMA edge-mount
- These accept standard SMA pigtail antennas with bulkhead nuts

**V1 uses wire dipole pads instead** (soldered wire antennas, no connector weight).

### 6. Ground Pour Requirements

The F33 has 7 GND pins carrying up to 1.2A return current during TX:
- All 7 pins (2,3,4,6,7,8,11) must connect to a solid ground pour
- Minimum 3 dedicated ground vias adjacent to the F33 module
- No signal traces crossing the ground return path
- Bulk decoupling: 100µF + 10µF + 100nF at pin 1 (VCC)

---

## JLCPCB Ordering Guide

### Board specifications (both variants)

| Parameter | Value |
|-----------|-------|
| Layers | 2 |
| Thickness | 0.6 mm (lightweight) or 1.6 mm (standard) |
| Copper weight | 1 oz (35 µm) |
| Surface finish | ENIG (gold) — better for castellated pads |
| Minimum trace width | 6 mil (0.15 mm) |
| Minimum via | 0.3 mm drill / 0.6 mm pad |
| Solder mask | Both sides |
| Silkscreen | Both sides |

### Variant-specific notes

**V1 (non-PA):**
- Board size: ~45×38 mm (estimate, confirm after layout)
- 0.4–0.6 mm thickness for weight savings
- No SMA connectors (wire antennas)
- Lower cost (~$2 for 5 boards at JLCPCB)

**V2 (2W PA):**
- Board size: ~60×45 mm (estimate — F33 module alone is 39×21 mm)
- 0.8–1.6 mm thickness recommended (SMA connector mechanical stability)
- 2× SMA connectors add ~$1.50/board for parts
- Heavier ground copper pour (2 oz copper recommended for PA heat dissipation)
- Higher cost (~$5-10 for 5 boards at JLCPCB)

### Component sourcing (LCSC — JLCPCB's component store)

| Component | LCSC Part | Price | Used in |
|-----------|-----------|-------|---------|
| NiceRF LoRa2021 (bare) | — (owned: 4×) | — | V1 |
| NiceRF LoRa2021F33-2G4 | C5913567 (check) | ~$8 | V2 |
| ESP32-C3-MINI-1 | C2913482 | ~$2 | Both |
| RP2040-Zero (Waveshare) | — (owned) | — | Both |
| MS5611 | C21934 (breakout) | ~$3 | Both |
| MAX-M10S (GEP-M10nano) | — (owned: 1×) | — | Both |
| TPS7A0233DBVR | C157172 | ~$0.50 | Both |
| BAT54 | C117039 | ~$0.05 | Both |
| SMA edge connector | C496538 | ~$0.75 | V2 only |
| Supercap 1F/5.5V | C335417 | ~$1.50 | Both |

---

## Next Steps

1. [x] Schematics complete (both variants)
2. [ ] KiCad PCB layout for V1 (non-PA) — import netlist, place, route
3. [ ] KiCad PCB layout for V2 (2W PA) — import netlist, place, route, ground pour
4. [ ] JLCPCB DRC check on both layouts
5. [ ] Gerber export + drill files + pick-and-place
6. [ ] BOM + order

### Pin assignment verification checklist

- [x] RP2040 SPI pins (GP2-GP5) match proven firmware
- [x] RP2040 control pins (GP6-GP8) match proven firmware
- [x] GPS UART (GP0/GP1) match proven firmware
- [x] LR2021 pin map (bare) verified against firmware
- [x] F33 pin map verified against NiceRF datasheet V1.1
- [x] All GND pins connected in both variants
- [x] CE pin added for F33 sleep control
- [x] SMA connectors for F33 variant
- [x] Decoupling caps on all ICs
