# RP2040 FLRC TX Timing Profile — Real Hardware Data

**Date:** 2026-07-16
**Firmware:** flrc_timing_profiler.cpp (env: rp2040-timing-profiler)
**Hardware:** RP2040 Pico F242D + NiceRF LoRa2021
**SPI Clock:** 16 MHz requested (12 MHz actual on RP2040)

---

## Per-Packet Breakdown (Average of 100 packets)

| Operation | Duration (µs) | % of Total | Bytes |
|-----------|---------------|------------|-------|
| CLR_IRQ | 14.3 | 1.0% | 6 |
| WRITE_FIFO | 517.3 | 35.3% | 257 |
| SET_TX | 13.8 | 0.9% | 5 |
| TX_DONE_WAIT | 919.1 | 62.7% | 0 |
| **TOTAL** | **1466.8** | **100%** | — |

**Measured throughput: 1390.8 kbps**

## Per-Byte SPI Analysis

| Measurement | Time | Per-Byte |
|-------------|------|----------|
| 10 bytes contiguous (one CS) | 22 µs | 2.20 µs/byte |
| 255 bytes contiguous (one CS) | 517 µs | 2.03 µs/byte |
| 10 separate transactions (CS each) | 54 µs | 5.40 µs/byte |

## Key Findings

### 1. TX_DONE_WAIT dominates at 62.7% (919 µs)
- Expected RF air time: 803 µs (2088 bits / 2.6 Mbps)
- Extra 116 µs: chip processing between SET_TX command and actual RF start
- This is NOT reducible by software — it's chip internal latency

### 2. WRITE_FIFO is 35.3% (517 µs for 257 bytes)
- 2.03 µs/byte via Arduino transfer()
- At 12 MHz SPI: 8 bits should take 0.67 µs
- Overhead per byte: 1.36 µs (68% overhead!)
- If batch transfer worked: 257 × 0.67 = 172 µs (3x faster)
- But batch/DMA doesn't work with LR2021 on RP2040

### 3. CS toggle overhead is 2.6x
- Contiguous: 2.03 µs/byte
- Separate transactions: 5.40 µs/byte (beginTransaction + CS + transfer + CS + endTransaction)
- Combined CS savings possible: merge CLR_IRQ + WRITE_FIFO + SET_TX into fewer transactions

### 4. Theoretical bounds
- Minimum possible per-packet (all SPI optimized): 172 µs FIFO + 14 µs overhead + 919 µs TX_DONE = 1105 µs → 1844 kbps
- With full pipelining (SPI overlaps air time): 919 µs → 2219 kbps
- Absolute theoretical max: 2540 kbps (air time limited)

## What the Logic Analyzer Needs to Capture

1. **CS setup time:** How long between CS falling edge and first SCK edge?
2. **Inter-byte gap:** Time between last SCK edge of byte N and first SCK edge of byte N+1
3. **CS hold time:** How long between last SCK edge and CS rising edge
4. **BUSY pin behavior:** When does BUSY assert/deassert relative to CS and SCK?
5. **Compare:** Capture both Arduino transfer() AND Pico SDK spi_write_blocking() to see the difference

This data tells us EXACTLY what PIO must replicate.

---

*Raw data from real hardware. Captured via flrc_timing_profiler.cpp on RP2040 F242D.*
