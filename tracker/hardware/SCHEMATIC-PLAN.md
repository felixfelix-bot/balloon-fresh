# SCHEMATIC PLAN — Balloon Relay Board Variants

**Date:** 2026-08-05  
**Author:** worker-layout (kimi-k3)  
**Task:** t_0774be4a — PCB-SCHEMATIC-PLAN  
**Status:** PLANNING ONLY — No .kicad_sch files yet  

**Inputs reviewed:**
- `tracker/hardware/full_pipeline.py` — component list, net definitions, pad mappings
- `docs/coordination/PCB-DRC-CONSULTANT-STRATEGY.md` — lessons learned
- `tracker/firmware/components/` — firmware peripheral expectations
- `tracker/firmware/main/app_main.cpp` — runtime pin usage
- `tracker/firmware/main/Kconfig.projbuild` — configurable peripherals
- `docs/coordination/ARCHITECTURE-FREERTOS-TASKS.md` — dual-MCU architecture reference

---

## Executive Summary

This document plans the schematic design for three balloon relay board variants:

1. **ESP32-C3** (current testing target, bare module on custom PCB)
2. **ESP32-S3** (future target, more GPIO/RAM/PSRAM)
3. **ESP32-C3 + RP2040** (dual-MCU, C3 for app logic + RP2040 for real-time radio)

All variants share the same peripheral set: LR2021F33 radio (SPI), MAX-M10S GPS (UART), TPS7A02 power chain, supercap + solar input, optional FEM, and ADC supercap monitoring.

**Critical constraint from consultant report:** The ESP32-C3 Super Mini footprint has a GPIO5/GPIO6 pad collision bug. For custom PCB, we use the **bare ESP32-C3 module** (ESP32-C3-MINI-1 or ESP32-C3-WROOM-02) with proper pad spacing, avoiding the Super Mini layout bug entirely.

---

## Table of Contents

1. [Variant 1: ESP32-C3](#variant-1-esp32-c3)
2. [Variant 2: ESP32-S3](#variant-2-esp32-s3)
3. [Variant 3: ESP32-C3 + RP2040 (Dual-MCU)](#variant-3-esp32-c3--rp2040-dual-mcu)
4. [Common Design Elements](#common-design-elements)
5. [KiCad Symbol/Footprint Assignments](#kicad-symbolfootprint-assignments)
6. [ERC Checklist](#erc-checklist)
7. [Migration Notes (C3 → S3)](#migration-notes-c3--s3)

---

## Variant 1: ESP32-C3

### 1. Block Diagram

```
                    ┌─────────────────────────────────────────┐
                    │           POWER CHAIN                   │
                    │                                         │
  Solar Panel ─────►│  SOLAR_IN ──► D1(BAT54) ──► VCAP        │
  (2-pin conn)      │                     │                   │
                    │                     ▼                   │
                    │               C_CAP (Supercap)          │
                    │                     │                   │
                    │                     ▼                   │
                    │               C1 (10uF)                 │
                    │                     │                   │
                    │                     ▼                   │
                    │               U4 (TPS7A02)              │
                    │               LDO 3.3V                  │
                    │                     │                   │
                    │                     ▼                   │
                    │               C2 (10uF) ──► 3V3 ────────┼───┐
                    │                                         │   │
                    └─────────────────────────────────────────┘   │
                                                                  │
                    ┌─────────────────────────────────────────┐   │
                    │           ESP32-C3 MODULE (U1)          │   │
                    │                                         │   │
                    │  GPIO0 ──► VDIV_MID ◄── R_DIV1/R_DIV2  │   │
                    │  GPIO1 ──► GPS_RX ◄── U3 TX            │   │
                    │  GPIO2 ──► SPI_MISO ◄── U2 Pin3        │   │
                    │  GPIO3 ──► LR2021_RST ◄── U2 Pin14     │   │
                    │  GPIO4 ──► LR2021_BUSY ◄── U2 Pin7     │   │
                    │  GPIO5 ──► LR2021_DIO9 ◄── U2 Pin13    │   │
                    │  GPIO6 ──► SPI_SCK ──► U2 Pin5         │   │
                    │  GPIO7 ──► SPI_MOSI ──► U2 Pin4        │   │
                    │  GPIO8 ──► (unused, strapping)         │   │
                    │  GPIO9 ──► STATUS_LED ──► R_LED ──► LED1│   │
                    │  GPIO10 ──► SPI_NSS ──► U2 Pin6        │   │
                    │  GPIO18 ──► (unused, USB_D-)           │   │
                    │  GPIO19 ──► FEM_TX ──► FEM (optional)  │   │
                    │  GPIO20 ──► I2C_SDA ──► BMP280 (opt)   │   │
                    │  GPIO21 ──► I2C_SCL ──► BMP280 (opt)   │   │
                    │  VCC ◄──────────────────────────────────┼───┘
                    │  GND ◄──────────────────────────────────┼───┐
                    └─────────────────────────────────────────┘   │
                                                                  │
                    ┌─────────────────────────────────────────┐   │
                    │         LR2021F33 RADIO (U2)            │   │
                    │                                         │   │
                    │  Pin1: 3V3 ◄────────────────────────────┤   │
                    │  Pin2: GND ◄────────────────────────────┤───┤
                    │  Pin3: MISO ──► GPIO2                   │   │
                    │  Pin4: MOSI ◄── GPIO7                   │   │
                    │  Pin5: SCK  ◄── GPIO6                   │   │
                    │  Pin6: NSS  ◄── GPIO10                  │   │
                    │  Pin7: BUSY ──► GPIO4                   │   │
                    │  Pin8: GND ◄────────────────────────────┤   │
                    │  Pin9: RF_SUB ──► ANT1 (U.FL)           │   │
                    │  Pin10: GND ◄───────────────────────────┤   │
                    │  Pin11: GND ◄───────────────────────────┤   │
                    │  Pin12: NC                              │   │
                    │  Pin13: DIO9 ──► GPIO5                  │   │
                    │  Pin14: RST ◄── GPIO3                   │   │
                    │  Pin15: NC                              │   │
                    │  Pin16: GND ◄───────────────────────────┤   │
                    │  Pin17: GND ◄───────────────────────────┤   │
                    │  Pin18: RF_2G4 ──► ANT2 (U.FL)          │   │
                    └─────────────────────────────────────────┘   │
                                                                  │
                    ┌─────────────────────────────────────────┐   │
                    │         MAX-M10S GPS (U3)               │   │
                    │                                         │   │
                    │  Pin1: VCC ◄────────────────────────────┤   │
                    │  Pin2: GND ◄────────────────────────────┤───┘
                    │  Pin3: TX  ──► GPIO1 (GPS_RX)           │
                    │  Pin4: RX  (unused, NC or config)       │
                    └─────────────────────────────────────────┘

                    ┌─────────────────────────────────────────┐
                    │      OPTIONAL: FEM (SKY66112)           │
                    │                                         │
                    │  TX_EN ◄── GPIO19 (FEM_TX)              │
                    │  RX_EN ◄── GPIO0 (if not used for ADC)  │
                    │  VCC ◄── 3V3                            │
                    │  GND ◄── GND                            │
                    └─────────────────────────────────────────┘

                    ┌─────────────────────────────────────────┐
                    │      OPTIONAL: BMP280 (I2C)             │
                    │                                         │
                    │  SDA ◄── GPIO20 (I2C_SDA)               │
                    │  SCL ◄── GPIO21 (I2C_SCL)               │
                    │  VCC ◄── 3V3                            │
                    │  GND ◄── GND                            │
                    └─────────────────────────────────────────┘
```

**Signal Flow:**
- GPS: MAX-M10S TX → UART RX (GPIO1) → ESP32-C3 processes NMEA
- Sensors: BMP280 (I2C) → optional pressure/temp/altitude
- Power Monitor: VCAP → R_DIV1/R_DIV2 → GPIO0 (ADC1_CH0) → supercap voltage
- Radio TX: ESP32-C3 SPI → LR2021 → RF_2G4 or RF_SUB → antenna
- Radio RX: Antenna → LR2021 → SPI → ESP32-C3 → DIO9 IRQ (GPIO5)

### 2. Component List

| Ref | Component | Part Number | Package | Value | Notes |
|-----|-----------|-------------|---------|-------|-------|
| U1 | MCU | ESP32-C3-MINI-1 | Module (castellated) | - | Bare module, NOT Super Mini. Proper pad pitch avoids collision bug. |
| U2 | Radio | NiceRF LR2021F33 | Module (castellated) | - | Dual-band LoRa/FLRC |
| U3 | GPS | u-blox MAX-M10S | Module | - | UART GPS, airborne <1G mode |
| U4 | LDO | TPS7A0233PDBVR | SOT-23-5 | 3.3V | Low-Iq LDO |
| D1 | Diode | BAT54 | SOD-123 | - | Schottky, solar OR-ing |
| C_CAP | Supercap | (TBD by capacity) | 2-pin THT | e.g., 0.1F 5.5V | Flight power reservoir |
| SOLAR | Connector | 2-pin header | 2.54mm THT | - | Solar panel input |
| LED1 | LED | Generic 0603 | 0603 | Red/Green | Status indicator |
| R_LED | Resistor | Generic 0402 | 0402 | 330R | LED current limit |
| R_PD | Resistor | Generic 0402 | 0402 | 10k | SPI MISO pull-down |
| R_DIV1 | Resistor | Generic 0402 | 0402 | 100k | Voltage divider top |
| R_DIV2 | Resistor | Generic 0402 | 0402 | 100k | Voltage divider bottom |
| C1 | Capacitor | Generic 0603 | 0603 | 10uF | LDO input |
| C2 | Capacitor | Generic 0603 | 0603 | 10uF | LDO output |
| C3 | Capacitor | Generic 0402 | 0402 | 100nF | Decoupling near U1 VCC |
| C4 | Capacitor | Generic 0402 | 0402 | 100nF | Decoupling near U2 VCC |
| ANT1 | Connector | U.FL-R-SMT | U.FL SMD | - | Sub-GHz antenna |
| ANT2 | Connector | U.FL-R-SMT | U.FL SMD | - | 2.4GHz antenna |
| FEM | FEM (optional) | SKY66112-11 | QFN-16 | - | PA + LNA (populate if needed) |
| U5 | I2C Sensor (optional) | BMP280 | LGA-8 | - | Pressure/temp (populate if needed) |
| J1 | Programming | 6-pin header | 2.54mm THT | - | UART + power for flashing |
| J2 | Debug | 4-pin header | 2.54mm THT | - | JTAG or extra UART |

**Total: 20 components (18 required, 2 optional)**

### 3. Net List (Complete)

| Net Name | Source Pin(s) | Destination Pin(s) | Type |
|----------|---------------|-------------------|------|
| 3V3 | U4.4 (OUT), C2.1 | U1.VCC, U2.1, U3.1, C3.1, C4.1, FEM.VCC, U5.VCC, J1.VCC | POWER |
| GND | U4.2, C2.2, C_CAP.2, C1.2, C3.2, C4.2, R_DIV2.2, R_PD.1, LED1.K | U1.GND, U2.2/8/10/11/16/17, U3.2, ANT1.GND, ANT2.GND, FEM.GND, U5.GND, J1.GND, J2.GND | GROUND |
| VCAP | D1.K, C_CAP.1, C1.1, U4.1, U4.3 | R_DIV1.1 | POWER |
| SOLAR_IN | SOLAR.1 | D1.A | POWER |
| VDIV_MID | R_DIV1.2, R_DIV2.1 | U1.GPIO0 | SIGNAL (ADC) |
| SPI_SCK | U1.GPIO6 | U2.5 | SIGNAL |
| SPI_MOSI | U1.GPIO7 | U2.4 | SIGNAL |
| SPI_MISO | U2.3, R_PD.2 | U1.GPIO2 | SIGNAL |
| SPI_NSS | U1.GPIO10 | U2.6 | SIGNAL |
| LR2021_BUSY | U2.7 | U1.GPIO4 | SIGNAL |
| LR2021_RST | U1.GPIO3 | U2.14 | SIGNAL |
| LR2021_DIO9 | U2.13 | U1.GPIO5 | SIGNAL (IRQ) |
| GPS_RX | U3.3 | U1.GPIO1 | SIGNAL (UART) |
| GPS_TX | U1.GPIO0 (if not ADC) or NC | U3.4 | SIGNAL (UART, optional) |
| STATUS_LED | U1.GPIO9 | R_LED.1 | SIGNAL |
| LED_ANODE | R_LED.2 | LED1.A | SIGNAL |
| FEM_TX | U1.GPIO19 | FEM.TX_EN | SIGNAL (optional) |
| FEM_RX | U1.GPIO0 (if not ADC) or NC | FEM.RX_EN | SIGNAL (optional) |
| I2C_SDA | U1.GPIO20 | U5.SDA | SIGNAL (optional) |
| I2C_SCL | U1.GPIO21 | U5.SCL | SIGNAL (optional) |
| RF_SUB_868 | U2.9 | ANT1.1 | RF |
| RF_2G4_2400 | U2.18 | ANT2.1 | RF |
| UART_TX | U1.TXD0 | J1.TX | SIGNAL (programming) |
| UART_RX | U1.RXD0 | J1.RX | SIGNAL (programming) |
| EN | J1.EN (or auto-reset circuit) | U1.EN | SIGNAL |
| BOOT | J1.BOOT (or auto-reset) | U1.GPIO9 (strapping) | SIGNAL |

**Total: 24 nets (22 required, 2 optional)**

### 4. Pin Assignments — ESP32-C3

| Function | GPIO | Notes |
|----------|------|-------|
| ADC (supercap) | GPIO0 | ADC1_CH0. Also strapping pin — ensure divider doesn't affect boot. |
| GPS UART RX | GPIO1 | UART1 RX. Also strapping pin — GPS must not pull during boot. |
| SPI MISO | GPIO2 | ADC1_CH2. Needs weak pull-down (R_PD=10k) for boot. |
| LR2021 RST | GPIO3 | Output, active-low reset. |
| LR2021 BUSY | GPIO4 | Input, radio busy indicator. |
| LR2021 DIO9 | GPIO5 | Input, IRQ for RX/TX done. Also strapping pin. |
| SPI SCK | GPIO6 | Output, SPI clock. |
| SPI MOSI | GPIO7 | Output, SPI data out. |
| (unused) | GPIO8 | Strapping pin, NO ADC. Leave unconnected. |
| STATUS_LED | GPIO9 | Output. Also strapping (BOOT button on dev boards). Use with caution. |
| SPI NSS | GPIO10 | Output, chip select (manual control). |
| (unused) | GPIO18 | USB_D-. Available if USB disabled. |
| FEM_TX | GPIO19 | USB_D+. Available if USB disabled. |
| I2C_SDA | GPIO20 | Optional BMP280. |
| I2C_SCL | GPIO21 | Optional BMP280. |
| UART0 TX | U0TXD | Programming/console. |
| UART0 RX | U0RXD | Programming/console. |

**Strapping Pin Summary (C3):**
- GPIO0: Boot mode (must be HIGH for normal boot). Voltage divider impedance must be high enough.
- GPIO1: Boot mode (must be HIGH for normal boot). GPS TX output must not pull LOW during boot.
- GPIO2: Boot mode (must be LOW for download, HIGH for normal boot). R_PD=10k pull-down ensures download mode works.
- GPIO5: Boot mode (must be HIGH for normal boot). LR2021 DIO9 idle state is HIGH — OK.
- GPIO8: SPIHD (must be HIGH for normal boot from flash). Leave unused.
- GPIO9: Boot mode (must be HIGH for normal boot). LED + 330R to GND ensures HIGH at boot (LED off).

### 5. Schematic Sheet Organization

**Sheet 1: Top Level / Power**
- Board outline and mounting holes (for reference)
- Power chain: SOLAR_IN → D1 → VCAP → C_CAP → C1 → U4 → C2 → 3V3
- Voltage divider: R_DIV1, R_DIV2
- Power symbols: 3V3, VCAP, SOLAR_IN, GND

**Sheet 2: MCU (ESP32-C3)**
- U1 module with all GPIO labels
- Decoupling caps: C3, C4 (100nF each, placed near VCC pins)
- Programming header: J1 (UART0 TX/RX, EN, BOOT, 3V3, GND)
- Debug header: J2 (optional JTAG or spare UART)
- Status LED: LED1 + R_LED

**Sheet 3: Radio (LR2021)**
- U2 module with all pin labels
- SPI connections to MCU sheet (hierarchical pins)
- Control lines: BUSY, RST, DIO9
- RF outputs: RF_SUB_868, RF_2G4_2400

**Sheet 4: GPS (MAX-M10S)**
- U3 module
- UART to MCU sheet
- Power from 3V3

**Sheet 5: Connectors / Antennas**
- ANT1 (U.FL sub-GHz)
- ANT2 (U.FL 2.4GHz)
- SOLAR connector
- Optional: FEM (if populated)

**Sheet 6: Optional Sensors**
- BMP280 (I2C) — only if populated
- Connections to MCU sheet

**Hierarchical Structure:**
```
Top
├── Power
├── MCU
│   ├── Radio (SPI + control)
│   ├── GPS (UART)
│   └── Sensors (I2C, ADC)
└── Connectors
```

### 6. KiCad Symbol/Footprint Assignments

| Component | KiCad Symbol | KiCad Footprint | Notes |
|-----------|--------------|-----------------|-------|
| ESP32-C3-MINI-1 | `RF_Module:ESP32-C3-MINI-1` | `RF_Module:ESP32-C3-MINI-1` | In KiCad 8+ libraries |
| LR2021F33 | Custom symbol needed | `RF_Module:NiceRF_Lora1276-C1` (as proxy) or custom | Custom symbol recommended for clarity |
| MAX-M10S | `RF_GPS:ublox_MAX-M10S` | `RF_GPS:ublox_MAX-M10` | In KiCad 8+ libraries |
| TPS7A02 | `Regulator_Linear:TPS7A02` | `Package_TO_SOT_SMD:SOT-23-5` | Standard |
| BAT54 | `Diode:BAT54` | `Diode_SMD:D_SOD-123` | Standard |
| Supercap | `Device:CP1_Small` | `Capacitor_THT:CP_Radial_D10.0mm_P5.00mm` | Or custom for specific supercap |
| Solar Conn | `Connector_Generic:Conn_01x02` | `Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical` | Standard |
| 0603 LED | `Device:LED` | `LED_SMD:LED_0603_1608Metric` | Standard |
| 0402 Resistor | `Device:R` | `Resistor_SMD:R_0402_1005Metric` | Standard |
| 0603 Capacitor | `Device:C` | `Capacitor_SMD:C_0603_1608Metric` | Standard |
| 0402 Capacitor | `Device:C` | `Capacitor_SMD:C_0402_1005Metric` | Standard |
| U.FL | `Connector:U.FL` | `Connector_Coaxial:U.FL_Molex_MCRF_73412-0110` | Standard |
| SKY66112 | `RF_Amplifier:SKY66112-11` (or custom) | `Package_DFN_QFN:QFN-16-1EP_3x3mm_P0.5mm` | Check datasheet |
| BMP280 | `Sensor_Pressure:BMP280` | `Package_LGA:Bosch_LGA-8_2.5x2.0mm_P0.65mm` | Standard |
| 6-pin Header | `Connector_Generic:Conn_01x06` | `Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical` | Programming |
| 4-pin Header | `Connector_Generic:Conn_01x04` | `Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical` | Debug |

**Custom Symbols Needed:**
1. **LR2021F33**: The NiceRF module doesn't have a stock KiCad symbol. Create custom symbol with 18 pins (left 1-9, right 10-18), labeled with signal names.
2. **ESP32-C3-MINI-1**: If KiCad version doesn't include it, use custom symbol with proper pin labels.

### 7. ERC Checklist

**Pin Type Assignments:**
- Power output: U4 pins OUT (3V3), EN (VCAP), IN (VCAP)
- Power input: U1 VCC, U2 pin1, U3 VCC, all VCC pins
- Passive: All resistor/capacitor pins
- Input: U1 GPIO1, GPIO2, GPIO4, GPIO5 (inputs from GPS, SPI, radio)
- Output: U1 GPIO3, GPIO6, GPIO7, GPIO9, GPIO10, GPIO19, GPIO20, GPIO21
- Bidirectional: U1 GPIO0 (ADC input + strapping)
- Open collector: None (all push-pull)
- NC: U2 pins 12, 15; U3 pin4 (if unused)

**ERC Rules to Enforce:**
- [ ] No unconnected pins (except explicitly NC)
- [ ] No power output shorted to power output
- [ ] No input shorted to input without driver
- [ ] All power inputs have decoupling caps nearby
- [ ] No conflicting drivers on same net
- [ ] Strapping pins have correct default states (pull-ups/pull-downs as needed)
- [ ] RF nets have proper impedance-controlled width annotation (0.76mm for 50Ω)

**Special Checks:**
- [ ] GPIO0 voltage divider impedance doesn't affect boot (R_DIV1+R_DIV2 = 200k, well above strapping threshold)
- [ ] GPIO2 pull-down (10k) is strong enough for download mode, weak enough not to interfere with SPI
- [ ] GPIO9 LED circuit doesn't pull pin low during boot (LED is off at boot, 330R to GND)
- [ ] GPS TX output is high-impedance or unpowered during C3 boot (GPS may not be powered until after boot)

---

## Variant 2: ESP32-S3

### 1. Block Diagram

Identical to Variant 1, except:
- MCU is ESP32-S3 (more GPIO, native USB, more RAM/PSRAM)
- Pin assignments differ (see §4 below)
- BMP280 and other optional peripherals are more likely to be included (more GPIO available)

### 2. Component List

Same as Variant 1, with these changes:
- U1: ESP32-S3-MINI-1 or ESP32-S3-WROOM-1 (module with PSRAM if needed)
- Additional decoupling for PSRAM if using OCT PSRAM variant

### 3. Net List

Same as Variant 1. All nets are preserved; only GPIO numbers change.

### 4. Pin Assignments — ESP32-S3

| Function | C3 GPIO | S3 GPIO | Notes |
|----------|---------|---------|-------|
| ADC (supercap) | GPIO0 | GPIO1 | S3 ADC1_CH0. GPIO0 is boot strapping on S3 too. |
| GPS UART RX | GPIO1 | GPIO4 | S3 has more UART-capable pins. |
| SPI MISO | GPIO2 | GPIO12 | S3 SPI2 MISO. |
| LR2021 RST | GPIO3 | GPIO13 | |
| LR2021 BUSY | GPIO4 | GPIO14 | |
| LR2021 DIO9 | GPIO5 | GPIO15 | |
| SPI SCK | GPIO6 | GPIO16 | S3 SPI2 SCK. |
| SPI MOSI | GPIO7 | GPIO17 | S3 SPI2 MOSI. |
| (unused) | GPIO8 | GPIO18 | USB_D- on S3 (native USB). |
| STATUS_LED | GPIO9 | GPIO8 | S3 has no strapping on GPIO8. |
| SPI NSS | GPIO10 | GPIO10 | |
| (unused) | GPIO18 | GPIO19 | USB_D+ on S3. |
| FEM_TX | GPIO19 | GPIO20 | |
| I2C_SDA | GPIO20 | GPIO21 | S3 I2C0 SDA. |
| I2C_SCL | GPIO21 | GPIO47 | S3 I2C0 SCL (or GPIO48). |
| UART0 TX | U0TXD | U0TXD | Programming |
| UART0 RX | U0RXD | U0RXD | Programming |

**Key Differences (C3 → S3):**
- S3 has native USB on GPIO19/20 (D+/D-). These are dedicated USB pins, not GPIO. Using them as GPIO requires disabling USB.
- S3 has more ADC channels and two ADC units.
- S3 has more strapping pins (GPIO0, GPIO3, GPIO45, GPIO46).
- S3 GPIO34-39 are input-only (no output driver).
- S3 has OCT PSRAM on some modules (uses GPIO33-37 internally).

### 5. Schematic Sheet Organization

Same as Variant 1, plus:
- Additional sheet for PSRAM power/decoupling if using ESP32-S3-WROOM-1-N8R8 (8MB PSRAM)
- Native USB connector option (USB-C or micro-USB) on a separate sheet or integrated with programming header

### 6. KiCad Symbol/Footprint Assignments

Same as Variant 1, except:
- ESP32-S3-MINI-1: `RF_Module:ESP32-S3-MINI-1` / `RF_Module:ESP32-S3-MINI-1`
- ESP32-S3-WROOM-1: `RF_Module:ESP32-S3-WROOM-1` / `RF_Module:ESP32-S3-WROOM-1`

### 7. ERC Checklist

Same as Variant 1, plus:
- [ ] USB pins (GPIO19/20) are not used as GPIO if native USB is enabled
- [ ] PSRAM power pins have proper decoupling (if applicable)
- [ ] GPIO34-39 are only used as inputs (if at all)

### 8. Migration Notes (C3 → S3)

**Hardware Changes:**
| Item | C3 | S3 | Action |
|------|----|----|--------|
| Boot strapping | GPIO0,1,2,5,8,9 | GPIO0,3,45,46 | Review strapping pin usage |
| ADC1_CH0 | GPIO0 | GPIO1 | Move voltage divider to GPIO1 |
| SPI2 SCK | GPIO6 | GPIO16 | Remap |
| SPI2 MISO | GPIO2 | GPIO12 | Remap |
| SPI2 MOSI | GPIO7 | GPIO17 | Remap |
| USB D- | GPIO18 | GPIO19 (dedicated) | Use native USB if needed |
| USB D+ | GPIO19 | GPIO20 (dedicated) | Use native USB if needed |
| I2C SDA | GPIO20 | GPIO21 | Remap |
| I2C SCL | GPIO21 | GPIO47/48 | Remap |

**Firmware Kconfig Changes:**
```
# New configs for S3 variant
CONFIG_IDF_TARGET="esp32s3"
CONFIG_GPS_UART_RX_PIN=4  # was 1
CONFIG_GPS_UART_TX_PIN=-1 # unchanged
# SPI pins are hardcoded in esp_idf_lr2021_radio.h — need #ifdef for S3
# ADC channel for supercap: ADC1_CH0 on GPIO1 (S3) vs GPIO0 (C3)
```

**Code Changes Needed:**
1. `esp_idf_lr2021_radio.h`: `#if CONFIG_IDF_TARGET_ESP32S3` block with S3 pin defaults
2. `power_manager.c`: ADC channel is still ADC1_CH0, but verify GPIO mapping
3. `app_main.cpp`: LED_GPIO, I2C pins need S3 variants

---

## Variant 3: ESP32-C3 + RP2040 (Dual-MCU)

### 1. Block Diagram

```
                    ┌─────────────────────────────────────────┐
                    │           POWER CHAIN                   │
                    │  (Same as Variant 1)                    │
                    └─────────────────────────────────────────┘
                                          │
                    ┌─────────────────────┴───────────────────┐
                    │         ESP32-C3 (U1) — APP MCU         │
                    │                                         │
                    │  • WiFi/Bluetooth                       │
                    │  • Application logic                    │
                    │  • Nostr / TollGate                     │
                    │  • GPS UART (GPIO1)                     │
                    │  • I2C Sensors (GPIO20/21)              │
                    │  • ADC Supercap (GPIO0)                 │
                    │  • STATUS_LED (GPIO9)                   │
                    │  • FEM_TX (GPIO19)                      │
                    │                                         │
                    │  Inter-MCU Bus:                         │
                    │    UART_TX (GPIO18) ──► RP2040 UART_RX  │
                    │    UART_RX (GPIO19) ◄── RP2040 UART_TX  │
                    │  (or SPI if higher bandwidth needed)    │
                    └─────────────────────────────────────────┘
                                          │
                    ┌─────────────────────┴───────────────────┐
                    │         RP2040 (U2) — RADIO MCU         │
                    │                                         │
                    │  • LR2021 SPI (GPIO18-21)               │
                    │  • Real-time radio task                 │
                    │  • IRQ handling (DIO9)                  │
                    │  • BUSY monitoring                      │
                    │  • RST control                          │
                    │  • NSS control                          │
                    │                                         │
                    │  FreeRTOS radio_task runs here          │
                    │  (dedicated core, no WiFi contention)   │
                    └─────────────────────────────────────────┘
                                          │
                    ┌─────────────────────┴───────────────────┐
                    │         LR2021F33 (U3)                  │
                    │  (Same as Variant 1, but SPI to RP2040) │
                    └─────────────────────────────────────────┘
```

**Inter-MCU Communication:**
- **Primary: UART** (simple, proven, sufficient for command/response + small packets)
  - C3 GPIO18 (TX) → RP2040 GPIO1 (RX)
  - C3 GPIO19 (RX) → RP2040 GPIO0 (TX)
  - Baud: 115200 or 460800 (both support)
  - Protocol: framed binary with CRC (similar to lr2021_framing)
- **Alternative: SPI** (higher bandwidth, more complex)
  - C3 as SPI master, RP2040 as SPI slave
  - C3 GPIO6/7/2/10 (SPI2) → RP2040 GPIO16-19 (SPI0)
  - Requires RP2040 SPI slave implementation

**Data Flow:**
- App on C3 → UART → RP2040 → SPI → LR2021 → RF
- RF → LR2021 → SPI → RP2040 (IRQ handling) → UART → C3 (app processing)
- GPS → C3 UART → local processing
- Sensors → C3 I2C → local processing

### 2. Component List

| Ref | Component | Part Number | Package | Value | Notes |
|-----|-----------|-------------|---------|-------|-------|
| U1 | App MCU | ESP32-C3-MINI-1 | Module | - | Handles WiFi, app logic, GPS, sensors |
| U2 | Radio MCU | RP2040 | QFN-56 | - | Handles LR2021 real-time SPI |
| U3 | Radio | NiceRF LR2021F33 | Module | - | Dual-band LoRa/FLRC |
| U4 | GPS | u-blox MAX-M10S | Module | - | UART to C3 |
| U5 | LDO | TPS7A0233PDBVR | SOT-23-5 | 3.3V | Powers both MCUs |
| D1 | Diode | BAT54 | SOD-123 | - | Solar OR-ing |
| C_CAP | Supercap | (TBD) | THT | 0.1F+ | Flight power |
| SOLAR | Connector | 2-pin | THT | - | Solar input |
| LED1 | LED | 0603 | 0603 | - | Status (C3) |
| LED2 | LED | 0603 | 0603 | - | Radio status (RP2040, optional) |
| R_LED | Resistor | 0402 | 0402 | 330R | LED1 current limit |
| R_PD | Resistor | 0402 | 0402 | 10k | SPI MISO pull-down (RP2040 side) |
| R_DIV1 | Resistor | 0402 | 0402 | 100k | Voltage divider (C3 ADC) |
| R_DIV2 | Resistor | 0402 | 0402 | 100k | Voltage divider (C3 ADC) |
| C1 | Capacitor | 0603 | 0603 | 10uF | LDO input |
| C2 | Capacitor | 0603 | 0603 | 10uF | LDO output |
| C3 | Capacitor | 0402 | 0402 | 100nF | C3 decoupling |
| C4 | Capacitor | 0402 | 0402 | 100nF | C3 decoupling |
| C5 | Capacitor | 0402 | 0402 | 100nF | RP2040 decoupling |
| C6 | Capacitor | 0402 | 0402 | 100nF | RP2040 decoupling |
| C7 | Capacitor | 0402 | 0402 | 100nF | LR2021 decoupling |
| ANT1 | U.FL | U.FL-R-SMT | SMD | - | Sub-GHz |
| ANT2 | U.FL | U.FL-R-SMT | SMD | - | 2.4GHz |
| J1 | Prog Header (C3) | 6-pin | THT | - | C3 UART + power |
| J2 | Prog Header (RP2040) | 4-pin | THT | - | RP2040 SWD + UART |
| XTAL1 | Crystal | 12MHz | SMD | - | RP2040 crystal (optional, RP2040 can run from ROSC) |
| R_BOOT | Resistor | 0402 | 0402 | 10k | RP2040 boot select pull-down |

**Total: 28 components**

### 3. Net List

| Net Name | Source | Destination | Type |
|----------|--------|-------------|------|
| 3V3 | U5.4 | U1.VCC, U2.VDD/IOVDD, U3.1, U4.1, C3-7.1 | POWER |
| GND | U5.2 | U1.GND, U2.GND, U3.2/8/10/11/16/17, U4.2, C3-7.2, ANT*.2 | GROUND |
| VCAP | D1.K, C_CAP.1, C1.1, U5.1/3 | R_DIV1.1 | POWER |
| SOLAR_IN | SOLAR.1 | D1.A | POWER |
| VDIV_MID | R_DIV1.2, R_DIV2.1 | U1.GPIO0 | SIGNAL |
| UART_C3_TX | U1.GPIO18 | U2.GPIO1 | SIGNAL (inter-MCU) |
| UART_C3_RX | U1.GPIO19 | U2.GPIO0 | SIGNAL (inter-MCU) |
| SPI_SCK | U2.GPIO18 | U3.5 | SIGNAL |
| SPI_MOSI | U2.GPIO19 | U3.4 | SIGNAL |
| SPI_MISO | U3.3, R_PD.2 | U2.GPIO16 | SIGNAL |
| SPI_NSS | U2.GPIO17 | U3.6 | SIGNAL |
| LR2021_BUSY | U3.7 | U2.GPIO20 | SIGNAL |
| LR2021_RST | U2.GPIO21 | U3.14 | SIGNAL |
| LR2021_DIO9 | U3.13 | U2.GPIO22 | SIGNAL |
| GPS_RX | U4.3 | U1.GPIO1 | SIGNAL |
| STATUS_LED | U1.GPIO9 | R_LED.1 | SIGNAL |
| LED_ANODE | R_LED.2 | LED1.A | SIGNAL |
| FEM_TX | U1.GPIO19 (shared w/ UART_C3_RX) | FEM.TX_EN | SIGNAL |
| I2C_SDA | U1.GPIO20 | BMP280.SDA (opt) | SIGNAL |
| I2C_SCL | U1.GPIO21 | BMP280.SCL (opt) | SIGNAL |
| RF_SUB_868 | U3.9 | ANT1.1 | RF |
| RF_2G4_2400 | U3.18 | ANT2.1 | RF |
| C3_UART0_TX | U1.U0TXD | J1.TX | SIGNAL |
| C3_UART0_RX | U1.U0RXD | J1.RX | SIGNAL |
| C3_EN | J1.EN | U1.EN | SIGNAL |
| C3_BOOT | J1.BOOT | U1.GPIO9 | SIGNAL |
| RP_SWCLK | J2.SWCLK | U2.SWCLK | SIGNAL |
| RP_SWDIO | J2.SWDIO | U2.SWDIO | SIGNAL |
| RP_UART_TX | U2.GPIO0 | J2.TX (optional) | SIGNAL |
| RP_UART_RX | U2.GPIO1 | J2.RX (optional) | SIGNAL |
| RP_BOOT | R_BOOT.1 | U2.QSPI_SS (BOOTSEL) | SIGNAL |

**Total: 28 nets**

### 4. Pin Assignments

**ESP32-C3 (App MCU):**

| Function | GPIO | Notes |
|----------|------|-------|
| ADC supercap | GPIO0 | ADC1_CH0 |
| GPS UART RX | GPIO1 | UART1 RX |
| (unused) | GPIO2 | Was SPI MISO, now free |
| (unused) | GPIO3 | Was LR2021 RST, now free |
| (unused) | GPIO4 | Was LR2021 BUSY, now free |
| (unused) | GPIO5 | Was LR2021 DIO9, now free |
| (unused) | GPIO6 | Was SPI SCK, now free |
| (unused) | GPIO7 | Was SPI MOSI, now free |
| (unused) | GPIO8 | Strapping, leave unused |
| STATUS_LED | GPIO9 | Status LED |
| (unused) | GPIO10 | Was SPI NSS, now free |
| UART_C3_TX | GPIO18 | To RP2040 UART_RX |
| UART_C3_RX / FEM_TX | GPIO19 | Shared: app UART RX + FEM TX. If FEM used, need分时 or different pin. |
| I2C_SDA | GPIO20 | BMP280 |
| I2C_SCL | GPIO21 | BMP280 |
| UART0 TX | U0TXD | Programming |
| UART0 RX | U0RXD | Programming |

**RP2040 (Radio MCU):**

| Function | GPIO | Notes |
|----------|------|-------|
| UART_C3_RX | GPIO0 | From C3 UART_TX |
| UART_C3_TX | GPIO1 | To C3 UART_RX |
| SPI0_RX (MISO) | GPIO16 | From LR2021 MISO |
| SPI0_CSn (NSS) | GPIO17 | To LR2021 NSS |
| SPI0_SCK | GPIO18 | To LR2021 SCK |
| SPI0_TX (MOSI) | GPIO19 | To LR2021 MOSI |
| LR2021_BUSY | GPIO20 | Input |
| LR2021_RST | GPIO21 | Output |
| LR2021_DIO9 | GPIO22 | Input (IRQ) |
| (optional) | GPIO23 | Radio status LED |
| (optional) | GPIO24 | Extra GPIO / future use |
| (optional) | GPIO25 | Extra GPIO / future use |
| SWCLK | SWCLK | Debug |
| SWDIO | SWDIO | Debug |
| QSPI_SS | BOOTSEL | Pull-down for normal boot |

**RP2040 Crystal (optional):**
- If accurate timing needed: 12MHz crystal on XIN/XOUT
- If not critical: use internal ROSC (saves 2 pins and crystal)

### 5. Schematic Sheet Organization

**Sheet 1: Top Level / Power**
- Same as Variant 1

**Sheet 2: MCU — ESP32-C3**
- C3 module, decoupling, programming header, GPS UART, I2C, ADC, status LED
- Inter-MCU UART connections (hierarchical labels)

**Sheet 3: MCU — RP2040**
- RP2040, decoupling, SWD header, crystal (if used), boot select
- Inter-MCU UART connections
- SPI connections to radio sheet

**Sheet 4: Radio — LR2021**
- LR2021 module
- SPI to RP2040 sheet
- Control: BUSY, RST, DIO9
- RF outputs

**Sheet 5: GPS**
- Same as Variant 1

**Sheet 6: Connectors / Antennas**
- Same as Variant 1

**Sheet 7: Optional**
- FEM, BMP280, extra LEDs

### 6. KiCad Symbol/Footprint Assignments

| Component | KiCad Symbol | KiCad Footprint |
|-----------|--------------|-----------------|
| RP2040 | `MCU_RaspberryPi:RP2040` | `Package_DFN_QFN:QFN-56-1EP_7x7mm_P0.4mm` |
| 12MHz Crystal | `Device:Crystal` | `Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm` |
| Others | Same as Variant 1 | Same as Variant 1 |

### 7. ERC Checklist

Same as Variant 1, plus:
- [ ] RP2040 BOOTSEL has proper pull-down (10k)
- [ ] RP2040 crystal load caps are correct (if crystal used)
- [ ] Inter-MCU UART has no conflicting drivers
- [ ] RP2040 and C3 reset circuits are independent
- [ ] Both MCUs have adequate decoupling (100nF per VDD pin)

### 8. Design Considerations for Dual-MCU

**Power Sequencing:**
- Both MCUs power up simultaneously from 3V3
- RP2040 boots faster than C3 — ensure inter-MCU UART is not driven before both are ready
- Add 100ms delay in RP2040 firmware before listening on UART

**Reset Strategy:**
- Independent resets: C3 EN and RP2040 RUN (or external reset supervisor)
- C3 can reset RP2040 via GPIO if needed (optional GPIO from C3 to RP2040 RUN)

**Firmware Protocol:**
- Frame format: `[0xAA][0x55][LEN][CMD][DATA...][CRC16]`
- Commands: TX_PACKET, RX_PACKET, GET_STATUS, SET_FREQ, SET_TX_POWER, etc.
- RP2040 handles all real-time radio operations autonomously
- C3 sends high-level commands; RP2040 returns events (RX_DONE, TX_DONE, etc.)

---

## Common Design Elements

### Power Supply Design

**TPS7A02 LDO:**
- Input: VCAP (2.7V - 5.5V from supercap)
- Output: 3.3V @ 300mA (sufficient for C3 + LR2021 + GPS + RP2040)
- Low Iq: 25nA shutdown, 350nA operating
- Dropout: ~150mV at 200mA

**Voltage Supervisor (optional but recommended):**
- Add TPS3839 or similar 3.3V supervisor for clean reset
- Ensures reliable boot when supercap is slowly charging

**Reverse Polarity Protection:**
- BAT54 diode provides solar input reverse protection
- Additional P-MOSFET ideal diode on VCAP if higher efficiency needed

### ADC Voltage Divider

**Supercap Monitoring:**
- R_DIV1 = 100k, R_DIV2 = 100k
- Divider ratio: 2:1
- Max VCAP = 5.5V → VDIV_MID max = 2.75V (within C3 ADC range of 0-3.1V with 12dB attenuation)
- Power consumption: 5.5V / 200k = 27.5µA continuous (acceptable for always-on monitoring)

### RF Layout Notes

**LR2021 RF Traces:**
- RF_SUB_868: 0.76mm width (50Ω on 2-layer 1.6mm FR4 with ground plane on B.Cu)
- RF_2G4_2400: 0.76mm width
- Keep RF traces < 10mm from module to U.FL connector
- Ground via fence along RF traces
- No signal traces under RF path

### Decoupling Strategy

| Location | Capacitor | Purpose |
|----------|-----------|---------|
| U1 VCC | 100nF 0402 | High-frequency decoupling |
| U1 VCC (bulk) | 10uF 0603 | Low-frequency decoupling |
| U2 VCC | 100nF 0402 | LR2021 decoupling |
| U3 VCC | 100nF 0402 | GPS decoupling |
| RP2040 VDD | 100nF 0402 x2 | One per VDD pin |
| LDO IN | 10uF 0603 | Input stability |
| LDO OUT | 10uF 0603 | Output stability + transient response |

### Programming / Debug

**ESP32-C3:**
- UART0: TX, RX, GND, 3V3, EN, GPIO9 (BOOT)
- Auto-reset circuit: DTR/RTS from USB-UART bridge (optional)

**RP2040:**
- SWD: SWCLK, SWDIO, GND, 3V3
- UART: GPIO0 (TX), GPIO1 (RX) for printf debugging
- BOOTSEL: Pull-down, button to GND for UF2 flashing

---

## Quality Gates Checklist

- [x] All 3 variants have complete component lists
- [x] All 3 variants have complete net lists
- [x] All 3 variants have pin assignments
- [x] Schematic sheet organization defined
- [x] KiCad symbols identified
- [x] ERC checklist defined
- [x] Migration notes (C3 → S3) defined
- [x] Dual-MCU interconnections defined

---

## Next Steps

1. **Create KiCad schematic files** (.kicad_sch) for Variant 1 (ESP32-C3)
2. **Generate netlist** and verify ERC passes
3. **Create custom symbols** for LR2021F33 and RP2040 (if not in libraries)
4. **Run ERC** with checklist rules
5. **Proceed to PCB layout** using the placement clustering strategy from the consultant report
6. **Iterate for S3 and dual-MCU variants** after C3 schematic is validated

---

## References

- `tracker/hardware/full_pipeline.py` — original component/net definitions
- `docs/coordination/PCB-DRC-CONSULTANT-STRATEGY.md` — placement bug analysis
- `tracker/firmware/main/app_main.cpp` — runtime pin usage
- `tracker/firmware/main/Kconfig.projbuild` — peripheral configuration
- `tracker/firmware/components/lr2021_transport/SPI-LAYOUT-CONSTRAINTS.md` — 20MHz SPI layout rules
- `docs/coordination/ARCHITECTURE-FREERTOS-TASKS.md` — dual-MCU architecture
