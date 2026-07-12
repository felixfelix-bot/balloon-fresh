# RP2040 Coprocessor Speed Test — Complete Wiring Guide

> Board B from ADR-015: ESP32-C3 + RP2040-Zero coprocessor + LR2021
> Purpose: Bypass ESP32-C3 single-core RX pipeline bottleneck to achieve 2000+ kbps

## What the bottleneck is

The LR2021 air rate is **2600 kbps**, but the ESP32-C3's single-core RX pipeline caps at ~838.8 kbps even with raw SPI bypass + no-STBY + high-priority tasks. The bottleneck is **CPU/RTOS overhead per packet** — the ESP32-C3 must handle IRQ → SPI read → clear IRQ → restart RX sequentially on one core.

The RP2040 solves this with **PIO (programmable I/O)** doing the SPI master in hardware + **dual cores** (Core 0: radio I/O, Core 1: protocol/queue).

## Architecture

```
[TX: ESP32-C3 + LR2021]  ──── RF ────→  [LR2021] ←SPI0→ [RP2040-Zero] ←UART→ [ESP32-C3 (RX board)]
                                         (coprocessor)                (logging/power)
```

The **RX side** changes: LR2021 moves from the ESP32-C3's SPI to the RP2040's SPI0. The ESP32-C3 becomes a passive logger/controller connected via UART.

## Wiring Table 1: LR2021 → RP2040-Zero (SPI0)

| NiceRF LR2021 Pin | Function | RP2040-Zero GPIO | RP2040 SPI0 Function | Wire Color (suggested) |
|:-:|:-:|:-:|:-:|:-:|
| Pin 1 | VCC | 3V3 (pin 36) | — | Red |
| Pin 2 | GND | GND | — | Black |
| Pin 3 | MISO | **GP4** | SPI0 RX | Yellow |
| Pin 4 | MOSI | **GP3** | SPI0 TX | Orange |
| Pin 5 | SCK | **GP2** | SPI0 SCK | Green |
| Pin 6 | NSS (CS) | **GP5** | GPIO (manual CS) | Blue |
| Pin 7 | BUSY | **GP6** | GPIO input | Purple |
| Pin 8 | GND | GND | — | Black |
| Pin 9 | ANT (Sub-GHz) | — | Wire dipole 16.4cm (868 MHz) | Antenna |
| Pin 10 | 2.4G | — | Wire dipole 3.1cm (2.4 GHz) | Antenna |
| Pin 11 | GND | GND | — | Black |
| Pin 12 | GND | GND | — | Black |
| Pin 14 | RST | **GP8** | GPIO output | White |
| Pin 15 | DIO9 (IRQ) | **GP7** | GPIO interrupt | Brown |
| Pin 16 | DIO8 | NC | Leave floating | — |
| Pin 17 | DIO7 | NC | Leave floating | — |
| Pin 18 | GND | GND | — | Black |

## Wiring Table 2: ESP32-C3 → RP2040-Zero (UART data link)

| ESP32-C3_Mini_V1 | Function | RP2040-Zero GPIO | RP2040 UART1 Function |
|:-:|:-:|:-:|:-:|
| GPIO0 (D0) | UART1 TX → | **GP21** | UART1 RX |
| GPIO1 (D1) | UART1 RX ← | **GP20** | UART1 TX |
| 3V3 | Power (shared) | 3V3 | — |
| GND | Ground (shared) | GND | — |

**Note:** GP20 = UART1 TX on RP2040, GP21 = UART1 RX. Cross-connect TX↔RX.

## Wiring Table 3: Power

| Source | Destination | Notes |
|:-:|:-:|:-:|
| USB-C (either board) | 3.3V rail | Pick ONE USB power source, jumper 3.3V between boards |
| 3.3V rail | LR2021 Pin 1 | Radio draws ~120mA TX burst |
| GND | All GND pins | **Star ground** — tie all GNDs together at one point |

## Wiring Table 4: GPS Module (u-blox MAX-M10S)

> **GPS connects to the ESP32-C3 — NOT the RP2040.**
> Per ADR-015 (Board B architecture), the ESP32-C3 retains GPS, sensors, power management, and FIPS routing. The RP2040 is a dedicated radio coprocessor (PIO SPI master for the LR2021).

### Why I2C instead of UART on Board B

In Board A (ESP32-C3 solo), GPS uses UART1 on **GPIO0 (RX)** / **GPIO1 (TX)** — see `docs/breadboard-wiring-guide.md`.

In Board B, UART1 is repurposed for the ESP32↔RP2040 data link on the **same GPIO0/GPIO1 pins** (Wiring Table 2 above). The ESP32-C3 has only two hardware UARTs:

| UART | Used by | Pins |
|:-:|:-:|:-:|
| UART0 | USB serial console (USB-CDC) | (internal) |
| UART1 | RP2040 data link | GPIO0/GPIO1 |

Both are occupied, so UART is unavailable for GPS. The MAX-M10S supports **I2C (u-blox DDC mode)** natively at address `0x42`. The I2C bus already carries the BMP280 sensor, so the GPS simply joins the same two-wire bus — **zero additional GPIO pins**.

### GPS I2C Wiring (Board B — recommended)

| u-blox MAX-M10S Pin | ESP32-C3 Dev Board | ESP32-C3 Flight Board | Bus | Notes |
|:-:|:-:|:-:|:-:|:-:|
| VCC | 3V3 | 3V3 | Power | 3.3V only — do NOT use 5V |
| GND | GND | GND | Power | Star ground |
| SDA | **GPIO8** (D8) | **GPIO20** | I2C | Shared with BMP280 |
| SCL | **GPIO9** (D9) | **GPIO21** | I2C | Shared with BMP280 |
| PPS | **GPIO2** (D2) | **GPIO2** | GPIO int | Optional — 1 pulse/sec for TDMA timing |
| TX | NC | NC | — | Leave floating (UART unused on Board B) |
| RX | NC | NC | — | Leave floating (UART unused on Board B) |

Wire color suggestion: SDA = Grey, SCL = White, PPS = Orange.

### GPS UART Wiring (Board A / alternative on Board B)

If using the ESP32-C3 solo (Board A), or if the RP2040 UART link is **relocated** to other GPIO pins (e.g. GPIO4 TX → GP21, GPIO5 RX ← GP20), the GPS can use UART1 as originally designed:

| u-blox MAX-M10S Pin | ESP32-C3 GPIO | Silkscreen | Wire Color (suggested) | Notes |
|:-:|:-:|:-:|:-:|:-:|
| VCC | 3V3 | 3V3 | Red | 3.3V |
| GND | GND | GND | Black | |
| TX | **GPIO0** | D0 | Green | → ESP32 UART1 RX |
| RX | **GPIO1** | D1 | Blue | ← ESP32 UART1 TX |

⚠️ **GPIO0 is a strapping pin** — must be LOW at boot for SPI flash boot. GPS TX is high-Z at boot, so this is safe. But double-check if debugging boot issues.

### MAX-M10S Pinout Reference

```
       u-blox MAX-M10S breakout (top view)
    ┌──────────────────────────────────┐
    │  VCC  ●──── 3.3V (NOT 5V!)       │
    │  GND  ●──── Ground               │
    │  TX   ●──── UART TX → MCU RX     │  (Board A only)
    │  RX   ●──── UART RX ← MCU TX     │  (Board A only)
    │  SDA  ●──── I2C Data  (addr 0x42)│  (Board B)
    │  SCL  ●──── I2C Clock            │  (Board B)
    │  PPS  ●──── 1 Pulse / Second     │  (optional)
    │  SAFE ●──── Safeboot (NC)        │
    │  V_BCKP ●── Backup bat (optional)│
    └──────────────────────────────────┘
```

### GPS Notes

- **I2C address**: `0x42` (u-blox DDC default). BMP280 is at `0x76`/`0x77` — **no bus conflict**.
- **Pull-ups**: The I2C bus needs 4.7kΩ pull-up resistors on SDA and SCL. Most BMP280 breakouts already include them; if the GPS breakout also has pull-ups, you may have redundant ones (usually fine — lowers resistance slightly, strengthens the signal).
- **PPS pin**: Provides a precise 1 Hz pulse — useful for TDMA slot alignment on the balloon. Connect to any GPIO with interrupt capability (GPIO2 recommended, it's free in Board B).
- **Cold start**: First fix can take 5–10 minutes with a clear sky view. Adding a backup battery (CR1220 or supercap) to V_BCKP preserves ephemeris across reboots, reducing time-to-fix to ~1 second (warm start).
- **Antenna**: Use the onboard chip antenna, or an external 25×25mm patch antenna for better reception at altitude. Keep antenna away from the LR2021 RF section.
- **Firmware**: Enable with `CONFIG_ENABLE_GPS=y` in Kconfig. The current GPS driver (`components/gps/gps.c`) is UART-based; for Board B I2C mode, the driver needs adaptation to u-blox DDC protocol (read register 0xFD for data-available count, then read 0xFF for NMEA bytes).
- **Power**: MAX-M10S draws ~26 mA tracking, ~67 mA acquisition, ~16 µA in backup mode. Negligible vs the LR2021 (~120 mA TX burst).

## Decoupling (critical)

- 100nF ceramic cap between LR2021 Pin 1 (VCC) and Pin 2 (GND) — as close to module as possible
- 10µF cap on the 3.3V rail near the LR2021 (TX burst current)
- 100nF cap on RP2040 3.3V near the board

## ASCII Wiring Diagram

```
                            ┌─── RP2040-Zero ───────────────────┐
     ┌──────────────┐       │                                    │
     │  LR2021      │       │  GP2 (SCK)  ←──── Pin 5 (SCK)     │
     │  (NiceRF)    │       │  GP3 (MOSI) ←──── Pin 4 (MOSI)    │
     │              │       │  GP4 (MISO) ────→ Pin 3 (MISO)    │
     │  Pin 1 (VCC) │←──────┤  3V3          ──── Pin 1 (VCC)    │
     │  Pin 2 (GND) │←──────┤  GND          ──── Pin 2,8,11..   │
     │  Pin 3 (MISO)│──────→│  GP5 (CS)    ──── Pin 6 (NSS)     │
     │  Pin 4 (MOSI)│←──────┤  GP6 (BUSY)  ←─── Pin 7 (BUSY)    │
     │  Pin 5 (SCK) │←──────┤  GP7 (IRQ)   ←─── Pin 15 (DIO9)   │
     │  Pin 6 (NSS) │←──────┤  GP8 (RST)   ──── Pin 14 (RST)    │
     │  Pin 7 (BUSY)│──────→│                                    │
     │  Pin 9 (ANT) │── 16.4cm wire (868 MHz dipole)            │
     │  Pin 14 (RST)│←──────┤                                    │
     │  Pin 15 (DIO9)│─────→│                                    │
     └──────────────┘       │  GP20 (UART1 TX) ──→ ESP32 RX     │
                            │  GP21 (UART1 RX) ←── ESP32 TX     │
                            │  USB-C (programming/debug)         │
                            └──────────────┬─────────────────────┘
                                           │ UART + 3.3V + GND
                            ┌──────────────▼─────────────────────┐
                            │  ESP32-C3_Mini_V1                  │
                            │  GPIO0 (TX) ──→ RP2040 GP21        │
                            │  GPIO1 (RX) ←── RP2040 GP20        │
                            │  GPIO8 (SDA) ←→ BMP280 + GPS (I2C) │
                            │  GPIO9 (SCL) ←→ BMP280 + GPS (I2C) │
                            │  GPIO2     ←── GPS PPS (optional)  │
                            │  USB-C (serial monitor / power)    │
                            │  GPIO3-7,10: FREE                  │
                            └────────────────────────────────────┘
```

## Pin Self-Test

The RP2040 firmware includes a boot-time pin self-test that verifies:
1. **CS pin toggle** — can drive GP5 high/low
2. **BUSY response** — LR2021 BUSY pin is readable after reset pulse
3. **RST pulse** — toggling GP8 causes BUSY to respond
4. **SPI communication** — can read LR2021 registers (chip ID)
5. **IRQ pin** — DIO9 interrupt is configured

Output on serial: `SELFTEST_PASSED` or `SELFTEST_WARN` (non-fatal if no radio connected).

## Build & Flash

```bash
# Build
cd firmware/rp2040 && pio run

# Flash (hold BOOTSEL while connecting USB)
pio run -t upload
# OR copy UF2 manually:
cp .pio/build/rp2040/firmware.uf2 /run/media/$USER/RPI-RP2/

# Monitor
pio device monitor -p /dev/ttyACM1 -b 115200
```

## Performance Targets

| Metric | ESP32-C3 (Board A) | RP2040 (Board B) | Target |
|--------|-------------------|-------------------|--------|
| SPI clock | 10.46 Mbps | 18 MHz | ↑ |
| Processing/pkt | 188µs (raw) | <140µs (est.) | <200µs |
| Throughput | 838.8 kbps | 2000+ kbps | ≥2000 |

## Wiring Table 5: ESP32-C3 → RP2040 BOOTSEL/RESET Control (VERIFIED 2026-07-13)

> **DIRECT WIRE, NO RESISTORS.** See `docs/FLIGHT-BOARD-AUTO-BOOTSEL.md` for full design.
> RP2040 button pads have internal pull-ups. No series or pull-up resistors needed.

| ESP32-C3 Pin | Via | RP2040 Button Pad | Resistors |
|:-:|:-:|:-:|:-:|
| GPIO1 (D1) | DIRECT WIRE | RESET button (3V3 signal side) | NONE |
| GPIO8 (D8) | DIRECT WIRE | BOOTSEL button (3V3 signal side) | NONE |
| GND | DIRECT WIRE | GND | NONE |

**CRITICAL:** Solder to the 3V3 signal side of each button pad (NOT the GND side).
Use multimeter to verify: correct pad reads ~3.3V idle, drops to 0V when pressed.

**Why no resistors:** 1kOhm series resistors create a voltage divider with the RP2040
internal pull-ups, producing 1.65V — not low enough for logic LOW (<0.8V threshold).
Direct wire lets ESP32 overpower the pull-up and drive to true 0V.

## References

- `docs/adr/015-three-board-hardware-strategy.md` — Three-board architecture decision
- `docs/FLIGHT-BOARD-AUTO-BOOTSEL.md` — BOOTSEL circuit design (VERIFIED WORKING)
- `HARDWARE_CONNECTIONS.md` — Detailed soldering instructions
- `mesh-stack/flrc-bench-espidf/THROUGHPUT-OPTIMIZATION-PLAN.md` — Optimization phases
- `mesh-stack/flrc-bench-espidf/main/fast_rx.cpp` — ESP32-C3 raw SPI bypass reference
- `firmware/rp2040/src/radio.cpp` — RP2040 raw SPI driver
- `firmware/rp2040/src/main.cpp` — Dual-core firmware with pin self-test
