# SPI Timing Analysis — LR2021 Cont-TX Baseline

## Method
- Firmware: `rp2040-cont-tx` (continuous TX, 255-byte payload, FLRC 2600 kbps air rate)
- Capture: sigrok fx2lafw, 24 MHz sample rate, 1 second
- Channels: D0=CS, D1=SCK, D2=MOSI, D3=MISO, D4=BUSY, D5=IRQ, D6=RST

## Baseline Results (cont-tx)

| Metric | Value |
|--------|-------|
| SPI clock | 10.40 MHz |
| SCK period | 96 ns |
| Transactions in 41.7ms | 107 |
| Avg transaction duration | 71 us |
| Avg gap between transactions | **320 us** |
| Bus duty cycle | **18.3%** (idle 82%) |
| Effective throughput | **1,754 kbps** |
| Active SPI throughput | 9,600 kbps |

## Transaction Pattern (repeating every ~3.6ms)

1. `02 0D 00 00 00` (5 bytes) — status check
2. `01 16 FF FF FF FF` (6 bytes) — register poll
3. `00 02 00 00 05 XX ...` (~260 bytes) — FIFO payload write

## Root Cause of Low Throughput

The SPI bus is fast enough (10.4 MHz, clean). The bottleneck is firmware:
- 320us average gap between SPI transactions
- Bus idle 82% of the time
- Two redundant status polls before every FIFO write

## Optimization Attempt 1: Batched SPI (FAILED)

Tried batching CLEAR_IRQ + WRITE_FIFO + SET_TX into one CS-low burst.
**Result:** Chip only executed first command (CLEAR_IRQ). TX never started.
**Root cause:** LR2021 requires CS-HIGH between SPI commands.

## Optimization Attempt 2: Skip Status Polls (FIXED)

Eliminated redundant status check (02 0D) and register poll (01 16).
3 SPI transactions per packet instead of 5:
1. WRITE_FIFO (CS toggle)
2. SET_TX (CS toggle)
3. CLEAR_IRQ after TX_DONE (CS toggle)

## NiceRF Communication (2026-07-29)

Ann from G-NiceRF confirmed:
- 2.6 Mbps = air interface rate (theoretical PHY max), NOT achievable throughput
- SPI commands are in the chip datasheet (Semtech LR2021)
- She offered technical support for SPI command sequences
