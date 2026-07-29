# RP2040 Baseline — Official Benchmark Reference

## Capture: captures/bench-rp2040.sr
## Date: 2026-07-30
## Tag: rp2040-baseline-v1

## Setup
- MCU: RP2040 (Waveshare RP2040-Zero, 133 MHz)
- Radio: NiceRF LoRa2021 (Semtech LR2021 Gen 4)
- Firmware: rp2040-cont-tx (255-byte payload, FLRC 2600 kbps air rate)
- SPI requested: 20 MHz
- LA: Saleae Logic (fx2lafw), 24 MHz sample, 1s capture
- Channel map: D0=CS, D1=SCK, D2=MOSI, D3=MISO, D4=BUSY, D5=IRQ, D6=RST

## Measured Results

| Metric | Value |
|--------|-------|
| SPI clock (actual) | 10.40 MHz |
| Transactions in 41.7ms | 107 |
| Avg CS-low duration | 72.4us |
| Avg inter-packet gap | 320.4us |
| Bus duty cycle | 18.3% |
| **Effective throughput** | **1,760 kbps** |
| SPI bits/sec (active only) | 9,634 kbps |
| % of PHY max (2600 kbps) | 67.7% |

## Per-Packet SPI Commands (3 per packet)

| Command | Opcode | Bytes | Duration |
|---------|--------|-------|----------|
| CLEAR_IRQ | 0x0116 | 6 | 6.4us |
| WRITE_TX_FIFO | 0x0002 | 257 | 205.1us |
| SET_TX | 0x020D | 5 | 5.6us |
| **Total SPI** | | | **217.1us** |

## Bottleneck Breakdown

```
[217us SPI transfer] [320us air time + overhead] = 537us per packet
     40%                    60%
```

Throughput = 255 * 8 / 537us = 3,800 kbps theoretical per-packet
Actual (with loop overhead): 1,760 kbps
Implied loop overhead: ~800us/packet (serial poll, IRQ spin, function calls)

## Comparison Data Points

| Payload | Throughput | Source |
|---------|------------|--------|
| 32 bytes | 1,192 kbps | sweep-32 capture |
| 255 bytes | 1,760 kbps | bench-rp2040.sr (this baseline) |
| 255 bytes | 1,797 kbps | earlier led-test capture |

Variance (1,760 vs 1,797) = 2% — within measurement noise.

## Key Finding

RP2040 delivers 10.40 MHz SPI (requested 20 MHz).
52% of requested clock = RP2040 clock divider limitation.
This is the primary firmware-side bottleneck.
