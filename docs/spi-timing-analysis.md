# SPI Timing Analysis — LR2021 Cont-TX

## Method
- Firmware: `rp2040-cont-tx` (continuous TX, 255-byte payload, FLRC 2600 kbps air rate)
- Capture: sigrok fx2lafw, 24 MHz sample rate, 1 second
- Channels: D0=CS, D1=SCK, D2=MOSI, D3=MISO, D4=BUSY, D5=IRQ, D6=RST

## Baseline Results (cont-tx, ORIGINAL firmware)

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

## Transaction Pattern (3 commands per packet, repeating every ~3.6ms)

Corrected opcode identification:
1. `00 02 00 00 05 XX ...` (~250 bytes) — WRITE_TX_FIFO + payload
2. `02 0D 00 00 00` (5 bytes) — SET_TX (trigger transmission)
3. `01 16 FF FF FF FF` (6 bytes) — CLEAR_IRQ_STATUS

NOT redundant status polls as initially thought. All 3 are required.

## Root Cause of Low Throughput

The 320us gaps are mostly AIR TIME — the LR2021 is BUSY transmitting the
packet on RF during the gap. At 2600 kbps air rate, 255 bytes takes ~784us.
The chip pulls BUSY high during TX. This is radio physics, not firmware.

## Optimization Attempt 1: Batched SPI (FAILED)

Tried batching CLEAR_IRQ + WRITE_FIFO + SET_TX into one CS-low burst.
**Result:** Chip only executed first command (CLEAR_IRQ). TX never started.
**Root cause:** LR2021 requires CS-HIGH between SPI commands.

## Optimization Attempt 2: Manual Inline SPI (WORSE)

Replaced function-call-based SPI with manual digitalWrite CS + transfer.
**Result:** 20% SLOWER throughput (1,404 kbps vs 1,754 kbps).

| Metric | Baseline (cont-tx) | Fast (cont-tx-fast) | Change |
|--------|--------------------|---------------------|--------|
| SPI clock | 10.40 MHz | 4.78 MHz | **HALVED** |
| Transactions | 107 | 84 | -21% |
| Avg gap | 320us | 305us | -5% |
| Bus duty | 18.3% | 37.3% | 2x (misleading) |
| Throughput | 1,754 kbps | 1,404 kbps | **20% WORSE** |

**Root cause:** Manual `beginTransaction`/`digitalWrite` in tight loop caused
RP2040 SPI peripheral to reinitialize at lower clock divider. The helper
functions (rfWriteTxFifo, rfSetTx, rfClearIrq) manage SPI state better.

## Conclusion: Baseline firmware is already near-optimal

- SPI clock: 10.4 MHz (RP2040 max for stable LR2021 comms)
- 3 SPI commands per packet: all required, none redundant
- Gaps are air time (BUSY during TX), not firmware overhead
- Effective throughput 1,754 kbps is ~67% of 2,600 kbps air rate
- Remaining gap = packet overhead (preamble, sync word, CRC) + SPI cmd time

## Next Optimization: Payload Size

Larger payloads amortize the fixed per-packet overhead (SPI commands +
preamble + sync word). Testing 64/128/255 byte payloads to find sweet spot.

## NiceRF Communication (2026-07-29)

Ann from G-NiceRF confirmed:
- 2.6 Mbps = air interface rate (theoretical PHY max), NOT achievable throughput
- SPI commands are in the chip datasheet (Semtech LR2021)
- She offered technical support for SPI command sequences
