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
                            │  ESP32-C3_Mini_V1 (RX board)       │
                            │  GPIO0 (TX) ──→ RP2040 GP21        │
                            │  GPIO1 (RX) ←── RP2040 GP20        │
                            │  USB-C (serial monitor)            │
                            │  GPIO2-7,10: FREE (LR2021 removed) │
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

## References

- `docs/adr/015-three-board-hardware-strategy.md` — Three-board architecture decision
- `mesh-stack/flrc-bench-espidf/THROUGHPUT-OPTIMIZATION-PLAN.md` — Optimization phases
- `mesh-stack/flrc-bench-espidf/main/fast_rx.cpp` — ESP32-C3 raw SPI bypass reference
- `firmware/rp2040/src/radio.cpp` — RP2040 raw SPI driver
- `firmware/rp2040/src/main.cpp` — Dual-core firmware with pin self-test
