# MCU Assessment: RP2040 vs ESP32-C3 for LR2021 SPI Throughput

## Date: 2026-07-30
## Status: HYPOTHESIS — needs empirical testing

## Question
Which MCU maximizes SPI throughput to the LR2021 radio chip?

## Hardware Comparison

| Factor | ESP32-C3 | RP2040 | Advantage |
|--------|----------|--------|-----------|
| CPU clock | 160 MHz RISC-V | 133 MHz ARM Cortex-M0+ | ESP32 (+20%) |
| Cores | 1 | 2 | RP2040 (parallel TX + USB) |
| Max SPI clock | 80 MHz | 62.5 MHz | ESP32 |
| SPI FIFO depth | 64 bytes | 8 bytes | ESP32 (8x larger) |
| DMA channels | 3 (GDMA) | 12 | RP2040 (4x more) |
| DMA-SPI integration | ESP-IDF auto-DMA for >4 byte transfers | earlephilhower manual setup | ESP32 (mature) |
| IRQ polling | GPIO interrupt + direct register | `sio_hw->gpio_in` direct | RP2040 (faster M0+ ISR) |
| USB CDC overhead | Separate USB-serial chip (CH340/CP2102) | Native USB CDC (same core) | RP2040 (no UART bridge) |

## Current Measured Performance (RP2040, 255-byte payload)

| Metric | Value |
|--------|-------|
| SPI clock (requested) | 20 MHz |
| SPI clock (actual) | 10.35 MHz |
| SPI transfer time | 205 us |
| Inter-packet gap | 309 us |
| Firmware loop overhead | ~320 us |
| Effective throughput | 1,797 kbps |
| % of PHY max (2600 kbps) | 69% |

## Bottleneck Breakdown (per 255-byte packet)

```
[217us SPI] [309us air time] [320us firmware overhead] = 846us total
   26%           36%              38%
```

- **Air time (309us)**: PHYSICS — fixed at 2600 kbps air rate. Same on any MCU.
- **SPI transfer (217us)**: At 10.35 MHz. If we got 20 MHz → 108us. If 40 MHz → 54us.
- **Firmware overhead (320us)**: Serial polling, IRQ spin loop, function call overhead.

## Where ESP32-C3 Could Win

1. **SPI clock delivery**: ESP32-C3 GDMA-SPI typically hits closer to requested frequency.
   The RP2040 only delivers 10.35 MHz when 20 MHz is requested (divider rounding).

2. **DMA-SPI out of the box**: ESP-IDF SPI driver auto-enables DMA for transfers > 4 bytes.
   No manual DMA configuration needed. The 255-byte FIFO write becomes a background operation.

3. **64-byte FIFO**: 8x deeper than RP2040's 8-byte FIFO. Fewer interrupt-driven refills
   during the 255-byte transfer. Less CPU overhead per packet.

## Where RP2040 Wins

1. **Dual core**: Core 1 runs a pure TX tight loop (no USB CDC interrupts). Core 0 handles
   serial + USB. ESP32-C3 must time-slice everything on one core.

2. **Native USB CDC**: No external UART bridge. Serial prints don't compete with SPI bus.

3. **12 DMA channels**: More DMA slots for future mesh stack (SPI + UART + I2C simultaneously).

4. **Proven toolchain**: LA probes wired, make targets built, firmware debugged over multiple
   sessions. Switching platforms costs 2-3 days of rework.

## Theoretical Ceiling Analysis

Air time is fixed: 255 bytes × 8 bits / 2600 kbps = 784us per packet.
This is the absolute floor — no MCU can transmit faster than the radio allows.

```
Theoretical max throughput = 255 × 8 / 784us = 2,602 kbps
```

Current (RP2040): 1,797 kbps = 69% of max.

Even with perfect firmware (zero overhead, 40 MHz SPI):
- SPI time: 54us
- Air time: 784us
- Throughput: 255×8 / (54+784)us = 2,438 kbps = 94% of max

So the realistic ceiling is ~2,400-2,500 kbps regardless of MCU choice.
The question is which MCU gets there with less engineering effort.

## Decision Matrix

| Criterion | RP2040 | ESP32-C3 |
|-----------|--------|----------|
| Time to optimize | 2-3 days (manual DMA) | 0.5 day (auto-DMA exists) |
| Theoretical max reachable | Yes (with DMA) | Yes (DMA built-in) |
| Mesh stack suitability | Better (dual core) | Adequate (single core) |
| Toolchain readiness | Ready now | Needs LA targets |
| Production weight | Same | Same |

## Recommendation: TEST BEFORE DECIDING

Both devices are on the bench. Run identical continuous TX tests on both MCUs.
Compare measured SPI clock, transfer time, and effective throughput.

**If ESP32-C3 shows >15% throughput improvement**: use ESP32-C3 for the 2W board.
**If <15%**: stay on RP2040 (dual core advantage outweighs marginal speed gain).

## Next Steps

See: `docs/plan-esp32-vs-rp2040-benchmark.md`
