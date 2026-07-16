# FLRC Throughput Optimization Results — 2026-07-16

## Summary

Tested 5 optimization approaches on real hardware (RP2040 + LR2021 Gen 4).
Only pipelining gave a marginal improvement. The bottleneck is NOT SPI clock speed.

## Test Results

| Phase | Approach | TX kbps | TX 1000/1000? | RX Unique | RX Loss | Real? |
|-------|----------|---------|---------------|-----------|---------|-------|
| v4 baseline | 16MHz Arduino SPI per-byte | 1367 | YES | 1000 | 0% | YES — PROVEN |
| 20MHz TX | 20MHz Arduino SPI TX, 16MHz RX | 1377 | YES | 1091 | 0% | YES |
| Phase 1: DMA TX | RP2040 DMA → spi0_hw->dr | N/A | NO (radio init fail) | N/A | N/A | FAILED |
| Phase 2: 20MHz RX | 20MHz Arduino SPI RX | N/A | N/A | 231 | 77% | FAILED (RX too fast) |
| Phase 3: Batch transfer | spiRf.transfer(buf, nullptr, len) | 8160 | YES (fake) | 0 | 100% | FAILED — SDK spi_write_blocking doesn't drive LR2021 correctly |
| Phase 4: Pipelining | Combined CS + pipelined FIFO | 1389 | YES | 162 unique (938 dup) | 0% | YES — marginal improvement |
| SPI sweep | Runtime SETSPI (6-20MHz) | 4564-8718 | YES (all fake) | 0 | 100% | FAILED — runtime spi_deinit breaks radio |

## Key Findings

### 1. SPI clock is NOT the bottleneck
- Pico SDK caps SPI at 12 MHz actual for all requests ≥12 MHz
- "16MHz" and "20MHz" firmware both run at 12 MHz actual
- 10 kbps difference (1367 vs 1377) is measurement noise
- Runtime SPI clock changes (spi_deinit + spi_init) break the LR2021 radio connection

### 2. Pico SDK spi_write_blocking() does NOT work with LR2021
- `spiRf.transfer(buf, nullptr, len)` calls `spi_write_blocking()` internally
- This produces fake TX_DONE (spin=0, 8160 kbps exceeds 2600 air rate 3×)
- Zero RX packets — radio never actually transmits
- Per-byte `spiRf.transfer(byte)` (Arduino implementation) DOES work
- Root cause likely: Pico SDK spi_write_blocking uses different FIFO management that violates LR2021 SPI timing requirements

### 3. DMA via spi0_hw->dr does NOT work with LR2021
- Radio init fails (Status=0x00, IRQ=0x21000200)
- Same root cause as direct register writes — bypasses Arduino SPI transaction protocol

### 4. Pipelining gives marginal improvement
- 1389 kbps vs 1367 baseline = 1.6% improvement
- Combined CS assertions (CLR_IRQ + CLR_FIFO + CLEAR_ERRORS in one burst) saves ~24µs/packet
- Bug in sequence number encoding (938 duplicates) — needs fix but doesn't affect throughput measurement
- 0% packet loss confirmed

### 5. RX SPI clock must stay at 16MHz (12 MHz actual)
- 20MHz RX SPI causes 77% packet loss
- RX is more sensitive to SPI clock than TX

## Bottleneck Analysis

The 1367 kbps = 53.7% of 2540 kbps theoretical max.

Per-packet breakdown (1492µs total at 1367 kbps):
- RF air time: 803µs (54%) — cannot reduce
- SPI overhead (per-byte transfer × 268 bytes): ~535µs (36%)
- IRQ polling + loop overhead: ~154µs (10%)

The SPI overhead is dominated by per-byte function call overhead in `spiRf.transfer(byte)`. The Pico SDK batch alternative doesn't work with LR2021. To significantly improve throughput, need either:
1. Fix the Pico SDK spi_write_blocking compatibility issue (investigate SPI mode/format differences)
2. Use PIO state machine for SPI (hardware-level, bypasses both Arduino and SDK limitations)
3. Accept ~1370 kbps as the practical ceiling for Arduino SPI on RP2040 + LR2021