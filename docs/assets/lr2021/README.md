# NiceRF LoRa2021 Module — Assets & Reference

> LLM-friendly summary of all datasheets, certifications, and reference materials
> for the NiceRF LoRa2021 (Semtech LR2021 Gen 4) wireless module.

## Chip Overview

The NiceRF **LoRa2021** is a dual-band wireless transceiver module based on
the **Semtech LR2021** chip (4th-generation LoRa IP core).

- **Sub-GHz**: 150–960 MHz (433/470/868/915 MHz presets)
- **High band**: 1.5–2.5 GHz (2.4 GHz ISM + S-band for SATCOM)
- **Modulations**: LoRa, FLRC (up to 2.6 Mbps), FSK, LR-FHSS, O-QPSK, OOK
- **TX Power**: +22 dBm (Sub-GHz), +12 dBm (2.4 GHz)
- **RX Sensitivity**: −143 dBm (Sub-GHz, BW=62.5 kHz, SF=12)
- **Sleep Current**: < 2 µA
- **Supply Voltage**: 1.8–3.6 V (typ 3.3 V)
- **TCXO**: 0.5 PPM, onboard, powered via VTCXO pin (see below)
- **Certifications**: FCC ID `2AD66-LORA2021-915`, CE-RED (868 MHz)

## Complete Pinout (from datasheet V1.3, page 6)

This is the **authoritative** pin table from the NiceRF datasheet. The module
has 18 pads. **Pin 13 (VTCXO) is omitted from the AGENTS.md pinout by design**
— it should be left unconnected.

| Pin | Name   | I/O | Function                                                        | Connect? |
|-----|--------|-----|-----------------------------------------------------------------|----------|
| 1   | VCC    | —   | Positive power supply (3.3 V)                                    | ✅ 3V3   |
| 2   | GND    | —   | Ground                                                           | ✅ GND   |
| 3   | MISO   | O   | SPI data output                                                  | ✅ SPI   |
| 4   | MOSI   | I   | SPI data input                                                   | ✅ SPI   |
| 5   | SCK    | I   | SPI clock input                                                  | ✅ SPI   |
| 6   | NSS    | I   | SPI chip select (CS)                                             | ✅ GPIO  |
| 7   | BUSY   | O   | Status indication (busy/handshake)                               | ✅ GPIO  |
| 8   | GND    | —   | Ground                                                           | ✅ GND   |
| 9   | ANT    | —   | Sub-GHz antenna (50 Ω, external antenna)                        | ✅ Ant   |
| 10  | 2.4G/S | —   | 2.4 GHz + S-band antenna (50 Ω)                                 | ⚪ Optional |
| 11  | GND    | —   | Ground                                                           | ✅ GND   |
| 12  | GND    | —   | Ground                                                           | ✅ GND   |
| **13** | **VTCXO** | **O** | **Controlled power output for TCXO. Auto-on during TX/RX, off during sleep.** | **❌ NC (leave floating)** |
| 14  | RST    | I   | Reset trigger input                                              | ✅ GPIO  |
| 15  | DIO9   | I/O | Multipurpose digital (used as IRQ)                               | ✅ GPIO  |
| 16  | DIO8   | I/O | Multipurpose digital                                             | ❌ NC    |
| 17  | DIO7   | I/O | Multipurpose digital                                             | ❌ NC    |
| 18  | GND    | —   | Ground                                                           | ✅ GND   |

### VTCXO (Pin 13) — Detailed Explanation

**What it is:** Pin 13 is a **controlled power OUTPUT**, not an input. The
LR2021 chip generates a stabilized voltage (~3 V) on this pin to power the
onboard TCXO crystal oscillator during TX/RX, and turns it OFF during deep
sleep to achieve < 2 µA sleep current.

**Why it matters:** At FLRC speeds (2.6 Mbps), frequency drift from chip
heating causes packet loss. The 0.5 PPM TCXO keeps the oscillator locked.
For SATCOM, the TCXO counteracts Doppler shift. For RTToF ranging, it
provides exact timing synchronization.

**Do NOT:**
- ❌ Supply external power to Pin 13
- ❌ Pull it high or low with a resistor
- ❌ Connect it to any net on your host PCB

**Do:**
- ✅ Leave Pin 13 **unconnected** (floating)
- ✅ The chip manages TCXO power internally via SPI device profile config

### DIO7 (Pin 17) and DIO8 (Pin 16) — Why They're NC

The LR2021 chip exposes DIO7 and DIO8 as multipurpose digital pins, but for
standard SPI-based radio operation with RadioLib, **only DIO9 (Pin 15) is
used as the IRQ pin**. DIO7/DIO8 are alternative interrupt/GPIO functions
that can be configured via the chip's command interface but are not needed
for our use case. Leave them floating.

## Wiring Summary

### For RP2040 Coprocessor (Board B)

See `docs/rp2040-wiring-guide.md` for the full wiring guide.

| LR2021 Pin | RP2040 GPIO | Function |
|------------|-------------|----------|
| 3 (MISO)   | GP4         | SPI0 RX  |
| 4 (MOSI)   | GP3         | SPI0 TX  |
| 5 (SCK)    | GP2         | SPI0 SCK |
| 6 (NSS)    | GP5         | GPIO CS  |
| 7 (BUSY)   | GP6         | GPIO in  |
| 14 (RST)   | GP8         | GPIO out |
| 15 (DIO9)  | GP7         | GPIO IRQ |

### For ESP32-C3 Direct (Board A / Breadboard)

See `docs/breadboard-wiring-guide.md` for the full wiring guide.

| LR2021 Pin | ESP32-C3 GPIO | Function |
|------------|---------------|----------|
| 3 (MISO)   | GPIO2         | SPI MISO |
| 4 (MOSI)   | GPIO7         | SPI MOSI |
| 5 (SCK)    | GPIO6         | SPI SCK  |
| 6 (NSS)    | GPIO10        | SPI CS   |
| 7 (BUSY)   | GPIO4         | GPIO in  |
| 14 (RST)   | GPIO3         | GPIO out |
| 15 (DIO9)  | GPIO5         | GPIO IRQ |

## Power Supply Decoupling (Critical)

- 100 nF ceramic cap between Pin 1 (VCC) and Pin 2 (GND), as close to module as possible
- 10 µF cap on the 3.3 V rail near the LR2021 (for TX burst current up to 120 mA)

## Antenna

- **Sub-GHz (868 MHz)**: Wire dipole, each leg 8.6 cm (λ/4 at 868 MHz ≈ 86.4 mm)
- **2.4 GHz**: Wire dipole, each leg 3.1 cm, or PCB Yagi (Komfort variant)
- Both are 50 Ω impedance

## Mechanical Dimensions

- Module size: 19.72 × 15 × 2.2 mm (18-pad SMD)
- Pad pitch: 1.27 mm (standard)
- See `LoRa2021_Package/` for DXF and PCB footprint files

## SMT Reflow Profile (from datasheet page 10)

- Ramp-up rate: max 3 °C/s
- Preheat (150–200 °C): 60–120 s
- Above 217 °C: at least 30 s
- Peak: 255 °C (max 260 °C)
- Ramp-down rate: max 6 °C/s

## Electrical Characteristics (from datasheet page 4)

| Parameter                  | Min  | Typ  | Max  | Unit  |
|----------------------------|------|------|------|-------|
| Supply Voltage             | 1.8  | 3.3  | 3.6  | V     |
| Operating Temperature      | -40  | 25   | 85   | °C    |
| TX Current @433 MHz        | —    | —    | 120  | mA    |
| TX Current @2.4 GHz        | —    | —    | 35   | mA    |
| RX Current (DCDC, 2.4 GHz) | —    | <7   | —    | mA    |
| RX Current (LDO, Sub-GHz)  | —    | <9.3 | —    | mA    |
| Sleep Current              | —    | <2   | —    | µA    |
| TX Power (Sub-GHz)         | 19   | 21   | 22   | dBm   |
| TX Power (2.4 GHz)         | 10   | 11   | 12   | dBm   |

## Demo Board (Appendix 1)

The NiceRF demo board has three buttons (SET, UP, DOWN) and supports:
- LoRa and FLRC modulation modes
- Master/Slave bidirectional communication
- TX power test (TXTEST)
- Receiver sensitivity test (RXTEST)
- Sleep test

FLRC data rates: 0.26, 0.32, 0.52, 0.65, 1.04, 1.3, 2.08, 2.6 Mbps
FLRC coding rates: 1/2, 3/4, 1, 2/3
FLRC pulse shaping: BT_05, BT_1, OFF

## Asset Files

| File | Source | Description |
|------|--------|-------------|
| `LoRa2021-Module-Datasheet-V1.3.pdf` | [NiceRF product page](https://www.nicerf.com/lora-module/lora2021.html) | Full V1.3 datasheet (10 pages) |
| `LoRa2021-assets-1.zip` | [NiceRF upload](https://www.nicerf.com/upload/20260113/636989721590ffde0244b27497565987.zip) | PCB package: DXF + pads (.pcb) + ASCII footprint |
| `LoRa2021-assets-2.zip` | [NiceRF upload](https://www.nicerf.com/upload/20260331/d3ea3b790bc7203dbe4f0814d1d508a3.zip) | CE-RED certification: 6 test reports (EN 301 489, 300 220, 300 328, 62311, 62368, EU-Type Certificate) |
| `LoRa2021_Package/` | (extracted from assets-1.zip) | `LoRa2021 V1.2_pads.dxf`, `LoRa2021V1.2_pads.pcb`, `LoRa2021 V1.2_pads.asc` |
| `CE-RED_Certification/` | (extracted from assets-2.zip) | 6 PDF test reports for LoRa2021-868 CE-RED |

### Still Needed

- **FCC ID zip** (`G-NiceRF LoRa Wireless Module LoRa2021-915 FCC ID.zip`): Available from
  the [NiceRF product page](https://www.nicerf.com/lora-module/lora2021.html#download-password-13279)
  (password-protected download, needs browser/JS). Contains FCC certification docs for the
  915 MHz variant.

## Source URLs

- Product page: https://www.nicerf.com/lora-module/lora2021.html
- Datasheet V1.3 PDF: https://www.nicerf.com/upload/20260410/854dad89545deb389f58e7f6a38971f4.pdf
- PCB Package ZIP: https://www.nicerf.com/upload/20260113/636989721590ffde0244b27497565987.zip
- CE-RED Certification ZIP: https://www.nicerf.com/upload/20260331/d3ea3b790bc7203dbe4f0814d1d508a3.zip
- FCC ID download: https://www.nicerf.com/lora-module/lora2021.html#download-password-13279

## Cross-References

- `docs/adr/002-lr2021-as-rf-chip.md` — ADR selecting LR2021 over LR1121/SX1280
- `docs/rp2040-wiring-guide.md` — RP2040-Zero ↔ LR2021 wiring (Board B)
- `docs/breadboard-wiring-guide.md` — ESP32-C3 ↔ LR2021 breadboard wiring (Board A)
- `docs/adr/015-three-board-hardware-strategy.md` — Three-board architecture (A/B/C)
- `AGENTS.md` — Project overview, pin mappings, build commands
