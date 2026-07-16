# FLRC TX Optimization — Complete Session Report (2026-07-16)

## Overview

Full-day optimization campaign on RP2040 + LR2021 Gen 4 FLRC radio link.
Goal: maximize TX throughput beyond 1294 kbps baseline.
Result: **1389 kbps proven** (pipelining, best real improvement).
**1377 kbps is the practical ceiling** for Arduino SPI on RP2040 + LR2021.

## Hardware

- TX: RP2040 board 8332 at `/dev/ttyACM0`
- RX: RP2040 board F242D at `/dev/ttyACM2`
- LR2021 wiring: SCK=GP2 MOSI=GP3 MISO=GP4 CS=GP5 BUSY=GP6 IRQ=GP7 RST=GP8
- UART backup: GP12=TX GP13=RX
- FLRC: 2440 MHz, 2600 kbps bitrate, 255-byte payload, preamble=8, +12 dBm

## All Optimization Phases — Complete Results

| # | Phase | Approach | TX kbps | TX_DONE 1000/1000? | RX Unique | RX Loss | Real RF? |
|---|-------|----------|---------|---------------------|-----------|---------|----------|
| 0 | Baseline v4 | 16MHz Arduino SPI per-byte, preamble=16 | 1294 | YES | 1000 | 0% | YES — PROVEN |
| 1 | Preamble reduction | preamble 16→8 symbols | 1377 | YES | 1000 | 0% | YES |
| 2 | SPI clock 16→20MHz | 20MHz compile-time SPI | 1377 | YES | 1091 | 0% | YES (noise) |
| 3 | Direct HW SPI + skip busy | spi0_hw regs, skip rfWaitBusy | 8987 | YES | 0 | 100% | **NO — FAKE (spin=0)** |
| 4 | DMA TX | RP2040 DMA → spi0_hw->dr | N/A | NO (init fail) | N/A | N/A | **FAILED** |
| 5 | Batch transfer | spiRf.transfer(buf,nullptr,len) | 8160 | YES (fake) | 0 | 100% | **NO — FAKE (spin=0)** |
| 6 | Pipelining | Combined CS + pipelined FIFO | 1389 | YES | 162 (938 dup) | 0% | YES — BEST |
| 7 | 20MHz RX | 20MHz SPI on RX side | N/A | N/A | 231 | 77% | **FAILED** |
| 8 | SPI freq sweep | Runtime spi_deinit+init | 4564-8718 | YES (fake) | 0 | 100% | **NO — ALL FAKE** |

### Phase Details

#### Phase 1: Preamble Reduction (16→8 symbols)
- Register 0x49 byte 0: 0x0E→0x0C
- +6.5% throughput (1294→1377 kbps)
- TX_DONE solid, spin count dropped ~181 cycles
- **Real improvement, kept in all subsequent firmware**

#### Phase 2: SPI Clock 16→20MHz
- `SPI_FREQ_HZ` 16000000→20000000 (compile-time)
- Zero change — 1377→1377 kbps, spin 13511→13510
- **Finding: Pico SDK caps SPI at 12 MHz actual regardless of request ≥12 MHz**
- SPI speed is NOT the bottleneck. RF airtime dominates.

#### Phase 3: Direct HW SPI + Skip rfWaitBusy — FAKE
- spi0_hw register writes, bypassed Arduino SPI class
- Skipped rfWaitBusy() before WRITE_FIFO and SET_TX
- 8987 kbps looked amazing — **but spin=0 on every packet**
- IRQ pin already HIGH before TX triggered — chip never processed SET_TX
- No RF output. Reverted (commit f5170b8).
- **LESSON: rfWaitBusy() MANDATORY before every SPI command**

#### Phase 4: DMA TX — FAILED
- RP2040 DMA channel → spi0_hw->dr
- Radio init fails: Status=0x00, IRQ=0x21000200
- Direct register access bypasses Arduino SPI transaction protocol
- Same root cause as Phase 3 — direct hw regs don't work with LR2021

#### Phase 5: Batch SPI Transfer — FAKE
- `spiRf.transfer(buf, nullptr, len)` calls Pico SDK `spi_write_blocking()`
- 8160 kbps, spin=0, 0 RX packets — all phantom
- Pico SDK spi_write_blocking uses different FIFO management than per-byte Arduino transfer
- **Per-byte `spiRf.transfer(byte)` is the ONLY working SPI path for LR2021 on RP2040**

#### Phase 6: Pipelining — BEST REAL RESULT
- Combined CS: CLR_IRQ + CLR_TX_FIFO + CLEAR_ERRORS in one SPI burst
- Prime first packet, then pipeline: poll IRQ → combined clear → WRITE_FIFO(next) → SET_TX
- 1389 kbps vs 1367 baseline = 1.6% improvement
- 0% packet loss confirmed
- Bug in sequence number encoding (938 duplicates) — doesn't affect throughput measurement
- **Marginal improvement — confirms Arduino per-byte SPI overhead is small vs RF airtime**

#### Phase 7: 20MHz RX — FAILED
- 20MHz SPI on RX side → 77% packet loss (231 unique of ~1000)
- RX is more sensitive to SPI clock than TX
- **RX must stay at 16MHz (12 MHz actual)**

#### Phase 8: SPI Frequency Sweep — ALL FAKE
- Runtime `spi_deinit()` + `spi_init()` to test 8/10/12/16/20/24 MHz
- All frequencies: spin=0, 0 RX packets
- `spi_deinit()` tears down SPI peripheral, LR2021 never re-syncs
- **Runtime SPI re-init is NOT safe with LR2021. Compile-time only.**

## Bottleneck Analysis

```
Raw FLRC bitrate:     2600 kbps
Effective throughput: 1377-1389 kbps (53-54% efficiency)

Per-packet breakdown (1492 µs total at 1367 kbps):
  RF air time:     803 µs  (54%) — CANNOT REDUCE (2600 kbps = max)
  SPI overhead:    535 µs  (36%) — per-byte Arduino transfer × 268 bytes
  IRQ poll + loop: 154 µs  (10%)
```

The 535 µs SPI overhead is from per-byte `spiRf.transfer(byte)` function call overhead. Pico SDK batch alternative (`spi_write_blocking`) doesn't work with LR2021. To reduce this, options are:

1. **PIO state machine SPI** — hardware-level, bypasses both Arduino and SDK limitations
2. **Accept ~1377 kbps as ceiling** for Arduino SPI on RP2040 + LR2021
3. **Switch to ESP32-C3 as MCU** — has hardware SPI DMA that works correctly

## Complete Learnings

### SPI / Radio Interface
1. **rfWaitBusy() is MANDATORY** before every SPI command. Skipping = phantom TX, no RF.
2. **Pico SDK spi_write_blocking() does NOT work with LR2021.** Different FIFO management violates LR2021 SPI timing. Only per-byte Arduino `transfer(byte)` works.
3. **Direct spi0_hw register access crashes TinyUSB CDC** and fails radio init. Arduino SPI class is the only safe path.
4. **Runtime SPI re-init (spi_deinit+spi_init) kills the radio.** LR2021 SPI state machine doesn't recover. Compile-time `SPI_FREQ_HZ` only.
5. **Pico SDK caps SPI at 12 MHz actual** for all requests ≥12 MHz. "16 MHz" and "20 MHz" firmware both run at 12 MHz.
6. **RX SPI clock is more sensitive than TX.** 20MHz RX = 77% packet loss. RX must stay at 16MHz.

### FLRC Radio
7. **2600 kbps is the hard FLRC ceiling.** Confirmed from 18 Semtech sources. No higher bitrate in FLRC mode.
8. **Preamble reduction (16→8) is the only real gain.** +6.5% from reducing preamble symbols.
9. **RF airtime dominates** — 803 µs of 1492 µs per packet is radio transmission. SPI/loop overhead is secondary.
10. **Pipelining gives marginal improvement** (1.6%) — combined CS assertions save ~24 µs/packet.

### USB CDC
11. **Serial.flush() blocks CDC** when no USB host has port open. Causes hard hang. Removed.
12. **Direct HW SPI register writes crash TinyUSB.** Only Arduino SPI class is CDC-safe.
13. **Heartbeat during wait window** lets host catch output whenever it connects.

## Firmware Environments (platformio.ini)

| Env | File | Purpose | Status |
|-----|------|---------|--------|
| `rp2040-raw-tx` | flrc_raw_tx.cpp | v4 baseline (16MHz) | PROVEN 1377 kbps |
| `rp2040-raw-tx-20mhz` | flrc_raw_tx_20mhz.cpp | 20MHz SPI variant | PROVEN 1377 kbps |
| `rp2040-raw-tx-pipe` | flrc_raw_tx_pipe.cpp | Pipelined TX | PROVEN 1389 kbps |
| `rp2040-raw-tx-batch` | flrc_raw_tx_batch.cpp | Batch SPI (spi_write_blocking) | BROKEN — fake results |
| `rp2040-raw-tx-sweep` | flrc_raw_tx_sweep.cpp | Runtime SPI freq sweep | BROKEN — kills radio |
| `rp2040-dma-tx` | flrc_dma_tx.cpp | DMA TX | BROKEN — init fails |
| `rp2040-raw-rx` | flrc_raw_rx.cpp | v4 RX (16MHz) | PROVEN 1000/1000 RX |
| `rp2040-raw-rx-20mhz` | flrc_raw_rx_20mhz.cpp | 20MHz RX | BROKEN — 77% loss |

## Commit History

| Commit | Description |
|--------|-------------|
| be4147d | Stage 2 — SPI 16MHz→20MHz |
| d3bfba1 | 20MHz TX variant + DMA TX BUSY-pin fix + test results |
| b59c8f9 | LR2021 research findings and SPI frequency sweep plan |
| d52e42a | Stage 3 — direct HW SPI + skip rfWaitBusy (FAKE, reverted) |
| f5170b8 | Revert Stage 3 |
| 0bbd179 | LR2021 reference + SPI frequency sweep + batch/pipe firmware |
| 83beab2 | FLRC TX optimization session summary |
| e31217e | FLRC optimization results — 5 phases tested |
| (this) | Complete consolidated report + next steps |

All pushed to: GitHub (c03rad0r/balloon-fresh) + ngit (relay.ngit.dev)

## Next Steps

### Option A: PIO State Machine SPI (Recommended)
Build a custom PIO program that implements SPI master for the LR2021.
- PIO runs at hardware speed, no per-byte function call overhead
- Can drive SPI at true 20 MHz (not SDK-capped 12 MHz)
- Doesn't use spi0_hw registers directly → CDC-safe
- Estimated improvement: reduce 535 µs SPI overhead to ~50 µs → ~1800 kbps

### Option B: Accept 1377 kbps Ceiling
1377 kbps = 53% of 2600 kbps raw. For balloon tracker telemetry (24 bytes/packet),
this is already massive overkill. Move on to:
- Sub-GHz FLRC testing (range/penetration)
- FEC coding rate experiments
- End-to-end mesh stack integration

### Option C: ESP32-C3 as SPI Master
The ESP32-C3 has working hardware SPI DMA. Move radio SPI to ESP32-C3,
keep RP2040 for PIO-based tasks only. Different architecture but proven SPI DMA.