# PCB Handover Document — Balloon Tracker for JLCPCB Manufacturing

**Prepared for:** balloon-circuit-design sub-manager
**Author:** balloon-range-tests sub-manager (auto-generated from repo + verified firmware)
**Date:** 2026-07-29
**Source repo:** `~/repos/balloon-fresh/`
**Primary firmware reference:** `firmware/rp2040/src/multi_radio_sweep_gps_v4.cpp`
**Status:** Ready for circuit-design input → manufacturable Gerber files

> **READ THIS FIRST.** This document is the single source of truth for pin assignments, footprints, and power budgets. All pin numbers below are **extracted from running firmware** (`multi_radio_sweep_gps_v4.cpp` lines 88–98, setup() at 950+) and the **measured** NiceRF LoRa2021 footprint (`tracker/hardware/footprints/nicerf-lora2021.json`). Do **not** invent pin numbers from a different chip's datasheet (SX1280/SX1262/etc.) — the LR2021 uses a unique 2-byte SPI protocol and a unique module pinout.

---

## 0. Critical Warnings for the Circuit Designer

1. **LR2021 ≠ SX1280.** The SPI opcodes are **2-byte big-endian** (e.g. `0x02 0x0D` = SET_TX), not the 1-byte opcodes (0x80–0xFF) of older Semtech chips. This affects nothing on the PCB, but it's the reason RadioLib does not work — the firmware uses raw SPI.
2. **Ground is non-negotiable.** The LR2021 module has **5 GND pins** (2, 8, 11, 12, 18). All five must be tied to a solid ground plane. With a 2 W external PA, the ground return path must handle **1.7 A peaks** — use a pour, not thin traces.
3. **SPI clock is 20 MHz max.** Keep SCK / MOSI / MISO traces **< 5 cm** and matched in length. Longer traces will corrupt the 2-byte opcode framing.
4. **The firmware proven on the bench uses an RP2040 Pico.** That is the DEV config. The FLIGHT target is an ESP32-C3 bare chip. **Two separate pin maps are given below — do not mix them up.** Section 4 explains which one to use for the JLCPCB order.
5. **The "2 W LR2021 amplifier board" (1.7 A peak)** mentioned in this project's context is **not a part number we have on file**. Section 2.4 flags this as an OPEN ITEM — confirm the part with Felix before routing the PA rail.

---

## 1. CURRENT WIRING — RP2040 + LR2021 (DEV / BENCH CONFIG)

This is the wiring that is **proven working** on the bench today. The firmware `multi_radio_sweep_gps_v4.cpp` (TX side) and `multi_radio_sweep_rx_v4.cpp` (RX side) are the matching pair.

### 1.1 RP2040 pin assignments (verbatim from firmware)

Source: `firmware/rp2040/src/multi_radio_sweep_gps_v4.cpp` lines 88–98, 521, 1006–1012.

| Function       | RP2040 GP | `#define`     | Direction (set in setup()) | Net name (KiCad) |
|----------------|-----------|---------------|----------------------------|------------------|
| SPI SCK        | **GP2**   | `PIN_SCK  2`  | spi0 SCK (output)          | SPI_SCK          |
| SPI MOSI       | **GP3**   | `PIN_MOSI 3`  | spi0 TX (output)           | SPI_MOSI         |
| SPI MISO       | **GP4**   | `PIN_MISO 4`  | spi0 RX (input)            | SPI_MISO         |
| SPI CS / NSS   | **GP5**   | `PIN_CS 5`    | OUTPUT, idle HIGH          | SPI_NSS          |
| BUSY           | **GP6**   | `PIN_BUSY 6`  | INPUT (read via `sio_hw`)  | LR_BUSY          |
| IRQ (DIO9)     | **GP7**   | `PIN_IRQ 7`   | INPUT, level-triggered     | LR_IRQ           |
| RST            | **GP8**   | `PIN_RST 8`   | OUTPUT, idle HIGH (act-lo) | LR_RST           |
| GPS UART RX    | **GP1**   | `PIN_GPS_RX 1`| UART0 RX (← GPS TX, NMEA)  | UART_GPS_RX      |
| GPS UART TX    | **GP0**   | `PIN_GPS_TX 0`| UART0 TX (→ GPS RX, opt)   | UART_GPS_TX      |
| Status LED     | **GP25**  | `PIN_LED 25`  | OUTPUT, idle LOW (on=HIGH) | LED_STATUS       |

**IMPORTANT — do NOT use GP16–GP22 for the radio.** Earlier docs / memories referenced those pins. They are wrong. The proven firmware pins are GP2–GP8 for radio, GP0/GP1 for GPS, GP25 for LED. The SPI peripheral used is **spi0** (instantiated at line 521 as `SPIClassRP2040 spiRf(spi0, PIN_MISO, PIN_CS, PIN_SCK, PIN_MOSI)`).

### 1.2 SPI electrical parameters

| Parameter | Value | Source |
|-----------|-------|--------|
| SPI clock | **20 MHz** (`SPI_FREQ_HZ 20000000UL`) | firmware line 100. Datasheet max is 20 MHz. A 16 MHz conservative setting also works (see env `rp2040-raw-tx` history). |
| SPI mode  | MODE 0 (CPOL=0, CPHA=0), MSBFIRST | firmware line 522 |
| Opcode format | **2-byte big-endian** (hi byte first) | e.g. SET_TX = `0x02 0x0D`, WRITE_TX_FIFO = `0x00 0x02` |
| Transaction protocol | `NSS LOW → wait BUSY LOW → send [op_hi, op_lo, payload...] → NSS HIGH` | firmware lines 524–538 |
| NSS idle state | HIGH (active low) | setup() line 1010 |
| RST idle state | HIGH (active low pulse: 200 µs LOW to reset) | `rfResetAndStandby()` lines 647–657 |

### 1.3 GPS UART

| Parameter | Value |
|-----------|-------|
| Module | GEPRC GEP-M10nano (u-blox M10) |
| Baud | **115200** (factory default; firmware auto-detects 115200 → 9600 → 38400 → 19200) |
| RX ring buffer | 1024 entries (enlarged from default 32 to survive 100 ms SPI gaps — see firmware line 972) |
| Protocol | NMEA 4.11, GGA + RMC sentences parsed |
| Wiring | GPS TX → RP2040 GP1 (RX), GPS RX → RP2040 GP0 (TX, optional config out), 3V3, GND |

### 1.4 Build flags (from `firmware/rp2040/platformio.ini`)

The active production environments are:

```ini
[platformio]
default_envs = rp2040-sweep-tx-v4, rp2040-sweep-rx-v4

[env:rp2040-sweep-tx-v4]
platform    = raspberrypi
board       = pico
framework   = arduino
board_build.core = earlephilhower     # NOT arduino-mbed
build_src_filter = -<*> +<multi_radio_sweep_gps_v4.cpp>
build_flags = -D SERIAL_BAUD=115200 -O2 -Wall
upload_protocol = picotool
monitor_speed = 115200
extra_scripts = pre:tools/inject_git_version.py
```

Key points for the circuit designer:
- **Core is `earlephilhower`** (Arduino-Pico), NOT mbed. This affects which SPI library is in use — but for hardware it just means GP2/GP3/GP4 map to spi0 SCK/MOSI/MISO.
- **USB CDC is the only debug console.** `Serial` = USB, `Serial1` = GPS UART (do NOT print debug to Serial1).
- A CDC watchdog reboots the board if `Serial.write()` returns 0 for 30 s (line 65). This is for autonomous battery operation; **on the bench keep USB connected**.

### 1.5 LED / debug pins

| Pin | Function | Behavior |
|-----|----------|----------|
| GP25 (Pico onboard green LED) | Status | Blink during GPS wait, solid during TX, off in pause |
| GP14 | (profiler envs only) | Scope/LA trigger for SPI timing diagnostics — NOT used in v4 |

---

## 2. POWER REQUIREMENTS

### 2.1 Voltage rails

| Rail | Voltage | Source | Consumers |
|------|---------|--------|-----------|
| VCC_3V3 | 3.3 V | LDO (TPS7A02 recommended, 25 nA IQ) from supercap | RP2040/Pico, LR2021 VCC pin 1, GPS, BMP280, optional FEM VCC |
| VRAW (supercap bus) | 0 – 5.4 V | Solar cells → BAT54/P-MOSFET → supercaps | LDO input |
| VPA (PA rail) | 3.3 V (or 5 V depending on PA module — see §2.4) | Dedicated LDO or direct from supercap | 2 W external PA — **must be separate from logic rail** |
| VSOLAR | ~1.5 V × N cells in series | Solar cells (52×19 mm, 0.5 V 400 mA each) | Via blocking diode to VRAW |

### 2.2 LR2021 module current draw (no external PA)

From `nicerf-lora2021.json` electrical specs:

| Mode | Current |
|------|---------|
| TX 433 MHz @ +22 dBm | 120 mA |
| TX 2.4 GHz @ +12 dBm | 35 mA |
| RX sub-GHz | 6 mA |
| RX 2.4 GHz | 7 mA |
| Sleep | 2 µA |

Firmware sets `TX_POWER_DBM = 12.5f` (line 263). For 2.4 GHz this is the chip's own PA. For sub-GHz the chip's own PA can already do +22 dBm.

### 2.3 RP2040 / ESP32-C3 / GPS current

| Part | Idle | Active TX | Sleep |
|------|------|-----------|-------|
| RP2040 Pico (dev) | ~15 mA | ~30 mA | (no deep sleep) |
| ESP32-C3_Mini_V1 (dev board, ME6211 regulator) | — | — | ~43 µA |
| ESP-C3-12F bare chip (flight target) | ~5 mA | ~25 mA | ~5 µA |
| GEPRC GEP-M10nano GPS | ~8 mA (PSM) | ~25 mA (cont) | (sleep via PUBX cmd) |

### 2.4 The 2 W external amplifier board — ⚠ OPEN ITEM

> **The task brief specifies a "2 W LR2021 amplifier board with 1.7 A peak current, needs 3+ ground connections."** This part is **not documented anywhere in the repo** — no part number, no datasheet, no footprint, no SKU. The repo's component guide (`docs/component-guide.md`) lists a **SKY66112-11 FEM** (+10 dB TX, +14 dB RX, ~0.1 g, ~3 EUR) as the planned amplifier option — that is a +22 dBm (158 mW) part, not 2 W.

**Before routing the PA rail, the circuit-design sub-manager MUST confirm with Felix:**

1. **Part number / datasheet** of the 2 W amplifier board.
2. **Supply voltage** — is it 3.3 V or 5 V? At 2 W RF out with ~36 % PA efficiency the DC input is ~5.6 W. At 3.3 V that is **~1.7 A** (matches the brief); at 5 V it is ~1.1 A.
3. **Footprint** — is it a castellated module (like the LR2021) or a QFN chip (like the SKY66112)?
4. **Control pins** — TX_EN, RX_EN, bypass? How does the MCU switch it?
5. **Antenna routing** — does the PA sit between LR2021 ANT pin and the antenna, on one band or both?

**Until the part is confirmed, the design below assumes:**

| Spec | Assumed value | Justification |
|------|---------------|---------------|
| RF output | 2 W (+33 dBm) | Per task brief |
| DC input current (peak) | **1.7 A at 3.3 V** | 2 W / 0.36 efficiency / 3.3 V |
| Ground connections | **≥ 3 dedicated** to ground pour (not thin traces) | Per task brief |
| PA rail | **Separate from VCC_3V3 logic rail**, fed from supercap/LDO capable of 2 A+ | Prevents logic brownout during TX bursts |
| Bulk decoupling | **≥ 100 µF low-ESR tantalum or ceramic** at PA VCC, plus 100 nF HF bypass | 1.7 A spikes need real energy storage |

If Felix actually means the **SKY66112-11 FEM** (the repo-documented part), the requirements are much lighter: ~250 mA peak at +22 dBm TX, QFN-16 package, single 3.3 V rail OK.

### 2.5 Solar input (flight version)

From `docs/component-guide.md` §5:

- **Cells on hand:** 100× of 52×19 mm (0.5 V, 400 mA each), 50× of 78×39 mm (0.54 W each).
- **Wiring:** 3 cells in series = 1.5 V; 4 wings in series = 6 V → directly into supercaps (no boost converter).
- **Blocking diode:** BAT54 (0.3 V drop) or P-MOSFET ideal diode (preferred for flight — no voltage loss).
- **Input pad on PCB:** VSOLAR net with reverse-polarity protection.

### 2.6 Supercapacitor connections

| Option | Config | Capacity | Weight | Reserve |
|--------|--------|----------|--------|---------|
| 2× 3.3 F, 2.7 V | Series + 10 kΩ balancing resistors | 1.65 F @ 5.4 V | ~3.0 g | ~73 h deep sleep |
| 2× 1.5 F, 2.7 V | Series + 10 kΩ balancing | 0.75 F @ 5.4 V | ~1.5 g | ~36 h |
| 1× 1 F, 5.5 V | Single cap (no balancing needed) | 1.0 F @ 5.5 V | ~2.0 g | ~48 h |
| 1× 0.47 F, 5.5 V | Single cap | 0.47 F @ 5.5 V | ~0.5 g | ~15 h |

**Recommended:** 2× 3.3 F for the dev/medium PCB, 1× 1 F 5.5 V for the minimal flight board.

**PCB footprint notes:**
- Through-hole radial caps, 8.0 mm diameter, 3.5 mm pitch (per `hub_schematic.py` line 41).
- ADC voltage divider: 2× 1 MΩ to bring 0–5.4 V down to 0–2.7 V at the ADC pin (or use the LR2021's internal voltage read).

---

## 3. RF-SPECIFIC REQUIREMENTS

### 3.1 LR2021 module footprint (NiceRF LoRa2021 Gen 4)

Source: `tracker/hardware/footprints/nicerf-lora2021.json` (measured) and `tracker/hardware/hub_board_diy/custom.pretty/LoRa2021_Castellated.kicad_mod` (KiCad footprint already exists).

| Dimension | Measured value | Note |
|-----------|----------------|------|
| Width  | **19.81 mm** | (task brief said 19.72 — use 19.81, the measured value) |
| Height | **14.98 mm** | (task brief said 15 — close enough) |
| Thickness | **2.32 mm** | (task brief said 2.2 — close enough) |
| Pin type | Castellated half-vias | Solder flat on PCB surface |
| Pins per side | 9 (left) + 9 (right) = **18 total** | |
| Pin pitch | **1.29 mm** | |
| Pin offset from edge | 1.69 mm | First pad center from top edge |

**Pin map (component-side / top view):**

```
         ┌──────────────────────────┐
  ANT  9 │                          │ 10  2.4G_ANT
  GND  2 │                          │ 11  GND
 BUSY  7 │                          │ 12  GND
  NSS  6 │       LoRa2021            │ 13  VTCXO
  SCK  5 │       19.81×14.98 mm      │ 14  RST
 MOSI  4 │       Castellated         │ 15  DIO9 (IRQ)
 MISO  3 │       18-pin              │ 16  DIO8
  GND  8 │                          │ 17  DIO7
  VCC  1 │                          │ 18  GND
         └──────────────────────────┘
   Left side (pins 9→1, top→bottom)   Right side (pins 10→18, top→bottom)
```

**Power/ground pins:** VCC = pin 1 (1.8–3.6 V, use 3.3 V). **GND = pins 2, 8, 11, 12, 18** (5 ground pins — tie all to plane).

**Decoupling (per `hub_board_diy/plan.md`):**
- 100 nF at pin 1 (VCC) → GND
- 100 nF at pin 13 (VTCXO) → GND
- 10 µF bulk at pin 1 (VCC) → GND

**Existing KiCad footprint:** `custom:LoRa2021_Castellated` — 18 SMD pads, 2 mm × 0.7 mm each, on F.Cu/F.Paste/F.Mask. Already DRC-clean in `hub_board_diy.kicad_pcb`. **Reuse this footprint — do not redraw.**

### 3.2 Antenna connections

| Band | LR2021 pin | Antenna type (dev) | Antenna type (flight) | Length |
|------|------------|--------------------|-----------------------|--------|
| Sub-GHz (433/868/915 MHz) | **Pin 9 (ANT)**, 50 Ω | U.FL connector on dev module → SMA pigtail → 3 dBi rubber duck | Wire dipole, soldered to PCB pad | **λ/2 @ 868 MHz = 16.4 cm** |
| 2.4 GHz | **Pin 10 (2.4G/S_ANT)**, 50 Ω | U.FL on module → 2.4 GHz stub | Wire dipole | **λ/2 @ 2.4 GHz = 3.1 cm** |

**PCB pads for flight wires:** 2 mm × 3 mm oval through-hole pads (1.0 mm drill), one per band. Place at board edge for strain relief. Silk-label "868 MHz" and "2.4 GHz".

**⚠ With a 2 W external PA**, the PA sits between pin 9 (or pin 10) and the antenna pad. The LR2021's own +22 dBm output becomes the PA input. **Confirm PA input power tolerance with Felix** — most 2 W PAs expect 0 to +10 dBm input, not +22 dBm. An attenuator may be needed.

### 3.3 PA considerations (external amplifier)

Given the 2 W PA board (§2.4 — specs unconfirmed):

| Concern | Requirement |
|---------|-------------|
| PA supply rail | **Dedicated 2 A+ capable rail.** Do not share with VCC_3V3 logic. Use a separate LDO or direct supercap tap. |
| PA ground | **≥ 3 vias to ground plane** directly at PA GND pads. Use a ground pour, not traces. 1.7 A return current will corrupt SPI if it crosses signal grounds. |
| TX/RX switching | PA needs TX_EN and RX_EN control from MCU. Reserve 2 GPIOs (e.g. GP9/GP10 on RP2040, or GPIO0/GPIO1 on ESP32-C3 — but check strapping conflicts). |
| Antenna isolation | PA output must NOT feed back into LR2021 RX path during RX. Use an RF switch (e.g. SKY13351-378LF SP4T, already in `hub_schematic.py`) or the PA's internal bypass. |
| Thermal | 2 W RF out at 36 % efficiency = 3.5 W heat. The PA module needs copper pour for heat spreading. Do not place under the LR2021 or GPS. |

### 3.4 SPI signal integrity

The LR2021 uses a **2-byte big-endian opcode** protocol at up to **20 MHz**. Signal integrity rules for the PCB:

| Rule | Value | Reason |
|------|-------|--------|
| Max SPI trace length | **< 50 mm** (ideal < 30 mm) | 20 MHz SCK has 25 ns period; long traces cause reflections that corrupt opcode framing |
| Trace impedance | ~50 Ω (0.4 mm trace over ground plane on 1.6 mm FR4 is close) | Not critical at 20 MHz but helps |
| Series termination | Optional 22–33 Ω resistor in series with SCK at the MCU pin | Damping ringing on long traces |
| Ground return | SPI traces should run over continuous ground plane (no gaps) | Return current must follow signal path |
| Decoupling at LR2021 | 100 nF at pin 1, 100 nF at pin 13, 10 µF bulk at pin 1 | Prevents brownout during TX bursts |
| CS (NSS) trace | Can be longer than SCK/MOSI/MISO but keep < 100 mm | CS is not timing-critical |

---

## 4. FLIGHT vs DEV DIFFERENCES

> **The current proven firmware is RP2040-specific.** The flight target is ESP32-C3. The JLCPCB order should be for the **flight board (ESP32-C3)** unless Felix explicitly wants a dev-board PCB. Both pin maps are given; do not mix them.

### 4.1 Dev config (RP2040 Pico — CURRENT WORKING)

| Property | Value |
|----------|-------|
| MCU | Raspberry Pi Pico (RP2040, dual Cortex-M0+, 133 MHz) |
| Weight | ~3 g bare Pico, more on carrier board |
| USB | Yes (CDC serial for debug + flashing) |
| Deep sleep | **No** (RP2040 has no ESP32-style deep sleep) |
| Firmware | `firmware/rp2040/src/multi_radio_sweep_gps_v4.cpp` — **proven** |
| Pin map | See §1.1 above (GP2–GP8 radio, GP0/GP1 GPS, GP25 LED) |
| Use case | Bench testing, range/walk tests, firmware development |

### 4.2 Flight config (ESP32-C3 bare chip — TARGET)

| Property | Value |
|----------|-------|
| MCU | ESP32-C3 (RISC-V, 160 MHz, 400 KB SRAM) — bare chip: **ESP-C3-12F** (~1.0 g) or ESP32-C3FH4 (~0.8 g) |
| Weight | ~1.0 g (bare chip) vs ~4 g (ESP32-C3_Mini_V1 dev board) |
| USB | Dev board has USB-C; bare chip needs UART or USB-serial bridge for flashing |
| Deep sleep | **Yes** — ~5 µA on bare chip, ~43 µA on Mini_V1 dev board |
| Firmware | **Needs port** — `tracker/firmware/` (ESP-IDF) is the target, but current proven code is RP2040. See `firmware/esp32-c3-flrc/` for a proven ESP32-C3 LR2021 raw-SPI starting point. |
| Pin map | See §4.3 below |
| Use case | Actual balloon flight |

### 4.3 ESP32-C3 pin map (from `wiring-dev-board.csv` + `esp32c3-mini-v1.csv`)

This is for the **ESP32-C3_Mini_V1 dev board** (Maker go, 22.52×18 mm, USB-C). A bare ESP-C3-12F chip uses the same GPIO numbers but without the onboard regulator/USB.

| Function | ESP32-C3 GPIO | Silkscreen (Mini_V1) | LR2021 pin | Notes |
|----------|---------------|----------------------|------------|-------|
| SPI_SCK  | **GPIO6**  | D6  | Pin 5  | JTAG TCK (usable as GPIO); via solder bridge SB1 |
| SPI_MOSI | **GPIO7**  | D7  | Pin 4  | JTAG TDO; via solder bridge SB2 |
| SPI_MISO | **GPIO2**  | D2  | Pin 3  | ⚠ **Strapping pin** — but safe as input (LR2021 MISO is high-Z at boot) |
| SPI_CS   | **GPIO10** | D10 | Pin 6  | Active low |
| BUSY     | **GPIO4**  | D4  | Pin 7  | JTAG TMS |
| RST      | **GPIO3**  | D3  | Pin 14 | Active low |
| IRQ      | **GPIO5**  | D5  | Pin 15 (DIO9) | JTAG TDI |
| I2C_SDA  | **GPIO8**  | D8  | BMP280 SDA | ⚠ **Strapping pin** + shared with onboard LED (inverted) |
| I2C_SCL  | **GPIO9**  | D9  | BMP280 SCL | ⚠ **Strapping pin** + shared with BOOT button |
| GPS UART RX | GPIO0 (or any free) | D0 | GPS TX | GPIO0 is strapping — OK if GPS TX is high-Z at boot |
| GPS UART TX | GPIO1 (or any free) | D1 | GPS RX | GPIO1 is ADC1_CH1 |
| LED      | GPIO8      | D8  | — | Inverted (LOW = on) |

**⚠ Strapping pins on ESP32-C3:** GPIO2, GPIO8, GPIO9 are strapping pins. The choices above are **verified safe** (see `hub_board_diy/plan.md` §"Strapping Pin Behavior"):
- GPIO2 (MISO) is high-Z during boot — LR2021 doesn't drive it until NSS goes low. ✅
- GPIO8 (SDA/LED) must be LOW or floating for normal SPI boot. I2C pullup (~4.7 kΩ) is compatible. ✅
- GPIO9 (SCL/BOOT) must be HIGH for normal boot (internal pullup). I2C pullup keeps it HIGH. ✅

**Solder bridges SB1/SB2** on the dev PCB allow swapping SCK/MOSI in case GPIO6/GPIO7 silkscreen is reversed on a particular board batch. **For a JLCPCB flight board with a known ESP-C3-12F chip, solder bridges are NOT needed** — the chip's GPIO assignments are fixed.

### 4.4 Porting checklist (RP2040 → ESP32-C3)

When the firmware team ports v4 to ESP32-C3, the circuit designer needs to know:
1. SPI peripheral changes from RP2040 spi0 to ESP32-C3 SPI2 (GPSPI2). Pin assignments may shift — coordinate with firmware.
2. GPS UART moves from RP2040 UART0 to ESP32-C3 UART1 (UART0 is used for USB console on ESP32-C3).
3. LED pin may change (no onboard LED on bare ESP-C3-12F).
4. Deep sleep wake-up: ESP32-C3 can wake from GPIO or timer. Reserve a GPIO for wake source if needed.

---

## 5. EXISTING SCHEMATIC STATE

### 5.1 What exists in the repo today

| Path | Type | State | Usable? |
|------|------|-------|---------|
| `tracker/hardware/hub_board/hub_schematic.py` | SKiDL Python | **STUB ONLY** — creates part objects with **stub nets** (no actual wiring). Calls `generate_netlist()` but produces an empty netlist. | ❌ Not usable — would need complete rewrite |
| `tracker/hardware/hub_board_diy/hub_board_diy.kicad_pro` | KiCad project | Valid project file | ✅ Starting point |
| `tracker/hardware/hub_board_diy/hub_board_diy.kicad_sch` | KiCad schematic | **Partial** — has U1 (ESP32-C3 as 2×8 header), U2L+U2R (LoRa2021 split into two 9-pin connectors), U3 (BMP280), C1–C4 (decoupling), AE1/AE2 (antenna pads), SB1/SB2 (solder bridges). **Nets are labeled but NOT all wires drawn.** Power symbols present. | ⚠ Needs wire completion |
| `tracker/hardware/hub_board_diy/hub_board_diy.kicad_pcb` | KiCad PCB | **SKELETON ONLY** — board outline (45×38 mm), layer stackup, net class definitions (Default + Power), but **zero routed traces** (only a placeholder segment from 0,0 to 0,0). | ❌ Needs full layout |
| `tracker/hardware/hub_board_diy/custom.pretty/LoRa2021_Castellated.kicad_mod` | KiCad footprint | **Complete** — 18 SMD pads, correct 1.29 mm pitch, courtyard + silkscreen | ✅ Reuse as-is |
| `tracker/hardware/hub_board_diy/custom.pretty/ESP32-C3_Mini_V1_Header.kicad_mod` | KiCad footprint | **Complete** — 2×8 through-hole, 2.54 mm pitch, courtyard + silkscreen | ✅ Reuse (dev board only; for bare chip use ESP-C3-12F footprint) |
| `tracker/hardware/hub_board_diy/custom.pretty/SolderBridge_2Pad.kicad_mod` | KiCad footprint | **Complete** — 2 pads, 0.5 mm gap | ✅ Reuse (dev board only) |
| `tracker/hardware/footprints/nicerf-lora2021.json` | JSON footprint data | **Complete** — measured dimensions, full pinout, electrical specs | ✅ Reference |
| `tracker/hardware/footprints/esp32c3-mini-v1.json` | JSON pinout | **Complete** — all GPIOs, ADC channels, strapping, JTAG | ✅ Reference |
| `tracker/hardware/footprints/wiring-dev-board.csv` | CSV wiring table | **Complete** — ESP32-C3 ↔ LR2021 ↔ BMP280 net-by-net | ✅ Reference |

### 5.2 Part numbers (from `docs/component-guide.md`)

| Component | Part number | Package | Qty in inventory | Source |
|-----------|-------------|---------|------------------|--------|
| LoRa module | **NiceRF LoRa2021 Gen 4** | 18-pin castellated, 19.81×14.98 mm | 4× | Owned |
| Alt 2.4 GHz module | EBYTE E28-2G4M27S (SX1281, +27 dBm) | — | 3× | Owned |
| Dev MCU | ESP32-C3_Mini_V1 (Maker go) | 22.52×18 mm, USB-C, U.FL | 20× | Owned |
| Flight MCU (bare) | **ESP-C3-12F** | — | 0 (need to buy) | ~2 EUR |
| LDO | **TPS7A02** (3.3 V, 25 nA IQ) | SOT-23-5 | — | ~0.50 EUR |
| Blocking diode | BAT54 | SOD-123 | — | ~0.10 EUR |
| FEM (PA + LNA) | **SKY66112-11** (+10 dB TX, +14 dB RX) | QFN-16, 3×3 mm | — | ~3 EUR |
| RF switch | SKY13351-378LF (SP4T) | QFN-12, 3×3 mm | — | ~2 EUR |
| Pressure sensor | BMP280 | LGA-8, 2×2.5 mm | — | ~0.50 EUR (bare) / ~1 EUR (breakout) |
| GPS | GEPRC GEP-M10nano (u-blox M10) | — | 1× (in use on bench) | — |
| Supercaps | 2× 3.3 F, 2.7 V (series) | THT radial, 8 mm dia | — | ~6 EUR |
| Solar cells | 52×19 mm, 0.5 V, 400 mA | — | 100× | Owned |

### 5.3 Recommended starting point for JLCPCB Gerber generation

1. **Use the existing `hub_board_diy.kicad_pro` project** as the starting point — the footprints are already DRC-clean.
2. **Complete the schematic wiring** in `hub_board_diy.kicad_sch` — nets are labeled but wires are not all drawn. Use §1.1 (RP2040) or §4.3 (ESP32-C3) pin maps depending on which board Felix wants manufactured.
3. **Decide dev vs flight.** For a first JLCPCB order, the **dev board (ESP32-C3_Mini_V1 + LoRa2021, no PA)** is lower-risk and matches the existing footprint library. The 2 W PA flight board is a separate, higher-complexity design.
4. **Do the PCB layout** in `hub_board_diy.kicad_pcb` — currently empty. Board outline (45×38 mm) is defined.
5. **If the 2 W PA is required**, add: PA module footprint (TBD — see §2.4), dedicated PA power rail, TX_EN/RX_EN GPIOs, RF switch between PA and antenna.
6. **Export Gerbers** per JLCPCB specs (RS-274X, 2-layer, 1.6 mm or 0.4 mm FR4 depending on weight target).

---

## 6. Summary Checklist for the Circuit-Design Sub-Manager

- [ ] Confirm with Felix: **dev board (ESP32-C3 Mini_V1) or flight board (bare ESP-C3-12F + 2 W PA)?**
- [ ] Confirm the **2 W amplifier part number, datasheet, and footprint** (§2.4 — not in repo).
- [ ] Pick the correct pin map: §1.1 (RP2040 dev) or §4.3 (ESP32-C3 flight).
- [ ] Use the **existing KiCad footprints** in `hub_board_diy/custom.pretty/` — do not redraw.
- [ ] Route **all 5 LR2021 GND pins** (2, 8, 11, 12, 18) to ground plane.
- [ ] Keep **SPI traces < 50 mm**, over continuous ground plane.
- [ ] Add **100 nF at LR2021 pin 1, 100 nF at pin 13, 10 µF bulk at pin 1**.
- [ ] If PA present: **dedicated PA rail ≥ 2 A, ≥ 100 µF bulk, ≥ 3 ground vias**.
- [ ] Antenna pads: 2 mm × 3 mm oval, 1.0 mm drill, at board edge. Label "868 MHz" / "2.4 GHz".
- [ ] Export Gerbers + drill files + BOM + pick-and-place for JLCPCB.

---

## Appendix A: Net name reference (KiCad)

| Net name | Source pin | Destination pin(s) |
|----------|-----------|-------------------|
| SPI_SCK  | RP2040 GP2 / ESP32 GPIO6 | LR2021 pin 5 |
| SPI_MOSI | RP2040 GP3 / ESP32 GPIO7 | LR2021 pin 4 |
| SPI_MISO | RP2040 GP4 / ESP32 GPIO2 | LR2021 pin 3 |
| SPI_NSS  | RP2040 GP5 / ESP32 GPIO10 | LR2021 pin 6 |
| LR_BUSY  | RP2040 GP6 / ESP32 GPIO4 | LR2021 pin 7 |
| LR_IRQ   | RP2040 GP7 / ESP32 GPIO5 | LR2021 pin 15 (DIO9) |
| LR_RST   | RP2040 GP8 / ESP32 GPIO3 | LR2021 pin 14 |
| UART_GPS_RX | RP2040 GP1 / ESP32 GPIO0 | GPS TX |
| UART_GPS_TX | RP2040 GP0 / ESP32 GPIO1 | GPS RX |
| I2C_SDA  | ESP32 GPIO8 | BMP280 SDA (ESP32-C3 only) |
| I2C_SCL  | ESP32 GPIO9 | BMP280 SCL (ESP32-C3 only) |
| VCC_3V3  | LDO output | LR2021 pin 1, MCU VCC, GPS VCC, BMP280 VCC |
| GND      | Ground plane | LR2021 pins 2,8,11,12,18; MCU GND; GPS GND; all decoupling |
| RF_SUBGHZ | LR2021 pin 9 | Antenna pad AE1 (via PA if present) |
| RF_24GHZ  | LR2021 pin 10 | Antenna pad AE2 (via PA if present) |
| LED_STATUS | RP2040 GP25 | Onboard LED (dev only) |
| VSOLAR   | Solar cell + terminal | Blocking diode → VRAW |
| VRAW     | Supercap + terminal | LDO input |

## Appendix B: File reference

| File | Purpose |
|------|---------|
| `firmware/rp2040/src/multi_radio_sweep_gps_v4.cpp` | **Primary firmware** — pin assignments, SPI protocol, GPS parsing |
| `firmware/rp2040/platformio.ini` | Build environments (env `rp2040-sweep-tx-v4` is the active TX) |
| `tracker/hardware/footprints/nicerf-lora2021.json` | LR2021 measured footprint + electrical specs |
| `tracker/hardware/footprints/esp32c3-mini-v1.json` | ESP32-C3 Mini_V1 full pinout |
| `tracker/hardware/footprints/wiring-dev-board.csv` | ESP32-C3 ↔ LR2021 ↔ BMP280 wiring |
| `tracker/hardware/hub_board_diy/hub_board_diy.kicad_sch` | Partial KiCad schematic (starting point) |
| `tracker/hardware/hub_board_diy/hub_board_diy.kicad_pcb` | Empty KiCad PCB (needs full layout) |
| `tracker/hardware/hub_board_diy/custom.pretty/LoRa2021_Castellated.kicad_mod` | LR2021 footprint (DRC-clean, reuse) |
| `tracker/hardware/hub_board_diy/custom.pretty/ESP32-C3_Mini_V1_Header.kicad_mod` | ESP32-C3 Mini_V1 header footprint (reuse for dev) |
| `tracker/hardware/hub_board_diy/plan.md` | Full design plan (45×38 mm single-sided toner transfer — adapt for JLCPCB 2-layer) |
| `tracker/hardware/hub_board_diy/implementation-plan.md` | Full fab + test plan |
| `tracker/hardware/hub_board/hub_schematic.py` | SKiDL stub (not usable — reference only) |
| `docs/component-guide.md` | Complete parts list with alternatives + pricing |
| `HARDWARE_CONNECTIONS.md` | ESP32-C3 ↔ RP2040 BOOTSEL controller wiring (for dev flashing rig) |
