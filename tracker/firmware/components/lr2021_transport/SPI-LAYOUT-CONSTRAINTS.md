# SPI Layout Constraints — LR2021 at 20 MHz

Authoritative hardware guidance for the LR2021 SPI bus at 20 MHz.
Validated against ESP32-C3 FLRC throughput tests and RP2040 baseline data.
Guides Phase 5 breadboard testing and the production PCB layout.

## 20MHz SPI — Proven Performance

- **ESP32-C3:** 20 MHz, 1733 kbps, 1000/1000 packets, 0% PER
- **RP2040:** caps at ~12 MHz actual regardless of request, 77% RX loss at 20 MHz setting
- **40 MHz** corrupts FIFO writes — hard ceiling

## PCB Layout Rules (for production PCB)

- **Trace length:** <30 mm ideal for 20 MHz on 2-layer FR4
- **Length matching:** SCK vs MOSI/MISO within ±5 mm
- **Corners:** 45° or rounded, no 90°
- **Ground plane** under SPI bus (minimize loop area)
- **Decoupling:** 100 nF + 10 µF close to LR2021 VCC pin

## Phase 5 Breadboard Setup

ESP32-C3 ↔ LR2021 pin connections:

| ESP32-C3 GPIO | LR2021 Signal | Net Name |
|---------------|---------------|----------|
| GPIO6         | SCK           | SPI_CLK  |
| GPIO7         | MOSI          | SPI_MOSI |
| GPIO2         | MISO          | SPI_MISO |
| GPIO10        | CS (NSS)      | SPI_CS   |
| GPIO4         | BUSY          | BUSY     |
| GPIO5         | DIO9 (IRQ)    | IRQ      |
| GPIO3         | RST           | RST      |

- **Wire length:** <10 cm jumpers, shortest practical
- **Ground:** single common ground return, star topology
- **Avoid:** long flat ribbon cables, shared ground with high-current devices

## MCU Comparison Table

| MCU       | SPI Clock (actual) | Throughput | PER | Notes                                              |
|-----------|--------------------|------------|-----|----------------------------------------------------|
| ESP32-C3  | 20 MHz (true)      | 838 kbps   | 0%  | Direct SPI, no RTOS contention on SPI              |
| RP2040    | 12 MHz (capped)    | 1377 kbps  | 0%  | Batched DMA, dedicated radio processor             |

> **Note:** RP2040 achieves higher **throughput** despite lower clock because of
> batched DMA transfers.

## References

- ADR-020: Raw 2-byte SPI protocol (no RadioLib)
- ADR-026: Dual-MCU radio architecture
- `docs/lr2021-spi-protocol-reference.md`
- `firmware/esp32-c3-flrc/main/main.cpp`
