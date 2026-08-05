# Dual-Board Strategy: Single-MCU V2 + Dual-MCU V1-Fixed

## Problem
V1 PCB has 527 DRC violations including:
- 3V3↔GND shorts (35 instances) — board will smoke on power-up
- SPI bus shorted (SCK↔MOSI↔MISO↔NSS) — radio dead
- UART TX/RX shorted — GPS dead
- I2C shorted to power/ground — sensors dead
- RF traces shorted — radios compromised
- 44 unconnected nets

Root cause: V1 was auto-routed with no human review. The GPIO fix we applied today (text editing .kicad_pcb) only changed net labels — it didn't fix the catastrophic routing underneath.

## Solution: Two Board Variants

### Board A: Single-MCU V2 (NEW DESIGN)
- Target: ESP32-C3 only (matches our firmware)
- Purpose: First flight board
- Design: Clean schematic from scratch, hand-routed
- No RP2040, no dual-MCU complexity
- Firmware: our current autonomous/mesh-baseline (single C3)

### Board B: Dual-MCU V1-Fixed (REPAIR)
- Target: ESP32-C3 + RP2040 (original V1 design intent)
- Purpose: Future mesh V2 with FIPS on RP2040
- Design: Fix V1 routing (527 violations → 0)
- Keep dual-footprint MCU socket
- Firmware: future dual-MCU architecture

## Why Two Boards

1. Our firmware TODAY runs on single C3. Board A can fly first.
2. V1 fix is 2-4 days of PCB routing work. Board A can be ordered in 2 days.
3. Dual-MCU is the mesh V2 architecture — needed for FIPS transport.
4. Single-MCU is the tracker V1 architecture — needed for first flight.
5. Different firmware = different boards. Don't force one board to do both.

## Board A: Single-MCU V2 Spec

| Component | Part | GPIO |
|-----------|------|------|
| MCU | ESP32-C3 (dev board header) | — |
| Radio | NiceRF LR2021 | SPI: GPIO2/6/7, NSS=GPIO10, RST=GPIO3, BUSY=GPIO4, IRQ=GPIO5 |
| GPS | MAX-M10S | UART1: GPIO0=TX, GPIO1=RX |
| LED | NeoPixel or simple LED | GPIO18 (test point on V1) |
| FEM | SKY66112 (optional) | GPIO19 (test point on V1) |
| ADC | Supercap voltage divider | GPIO8 |
| I2C | BMP280 (optional) | GPIO9=SDA, GPIO10... wait, conflict |

NOTE: ESP32-C3 only has 11 GPIOs (0-10). GPIO18/19 don't exist on C3 — they're USB D-/D+. The V1 GPIO fix (LED→18, FEM→19) only works on S3, not C3.

For Board A (single C3), use:
- LED: GPIO9 (was I2C_SDA on V1 — repurpose or use NeoPixel on GPIO8)
- FEM: not included on V1 flight (wire dipole only, per FLIGHT-BOARD-PLAN.md)
- Keep GPIO0-5 for radio, GPIO6-7 for SPI, GPIO8 for ADC, GPIO9-10 for I2C/GPS

## Timeline

| Step | Board A | Board B |
|------|---------|---------|
| Schematic | 1 day (from FLIGHT-BOARD-PLAN.md) | 1 day (fix V1 schematic) |
| PCB layout | 2 days (hand-route, simple) | 4 days (fix 527 violations) |
| DRC pass | 1 day | 1 day |
| JLCPCB order | Day 4 | Day 7 |
| Delivery | Day 18 | Day 21 |
| First flight | Day 20 | Day 25+ |

## Recommendation

Board A first. Board B later. Our firmware is single-MCU today. Don't block first flight on dual-MCU architecture.

The consultant review V6 (running) will provide more detail on this strategy.