# FLRC Throughput: Platform Analysis & Bottleneck Deep-Dive

**Date:** 2026-07-16
**Status:** Authoritative — supersedes earlier per-session docs for this analysis
**Repo:** balloon-fresh
**Hardware:** 2x RP2040 Pico + 2x ESP32-C3 + NiceRF LoRa2021 (Semtech LR2021 Gen 4)

---

## 1. WHY WE SWITCHED FROM ESP32-C3 TO RP2040

The original platform was ESP32-C3 (the actual flight hardware). During FLRC
throughput testing, the ESP32-C3 **RX pipeline became the bottleneck**:
when packets arrived faster than the ESP32 could read the FIFO, clear IRQ,
and re-arm RX, packets were lost. The "RX blind window" was too large.

The RP2040 was chosen because it offered three hardware capabilities that
should have eliminated this:

| Capability | What it should do | Status |
|-----------|-------------------|--------|
| PIO state machines | Hardware-driven SPI with cycle-exact timing, zero CPU overhead | FAILED on TX, never tested on RX |
| DMA channels | Autonomous FIFO reads/writes, CPU-free data movement | FAILED on TX, never tested on RX |
| Dual-core (Core 0 + Core 1) | Core 0: radio state + IRQ. Core 1: FIFO reads in parallel | NEVER TESTED |

**The fundamental expectation:** these features would shrink the RX blind
window from ~572µs to <100µs, allowing the radio to listen 94% of the time
instead of 62%. This would support TX rates up to ~2000-2540 kbps without
RX packet loss.

---

## 2. WHAT ACTUALLY HAPPENED ON RP2040

**We are NOT using ANY RP2040 hardware acceleration.**

The RP2040 is running plain Arduino `SPI.transfer()` byte-by-byte — the same
approach an ESP32 would use. The platform switch produced zero throughput
benefit because every attempt to use the advanced hardware failed:

### 2.1 TX-Side Failures (All Tested on Real Hardware)

| Approach | What We Tried | Result | Root Cause |
|----------|--------------|--------|------------|
| Pico SDK `spi_write_blocking()` | Batch SPI transfer | Fake TX_DONE, 8160 kbps reported (impossible), 0 RX | Pico SDK FIFO management incompatible with LR2021 timing |
| DMA via `spi0_hw->dr` | DMA channel feeds SPI TX register | Radio init fails (Status=0x00) | Direct register access bypasses Arduino transaction protocol |
| Direct HW SPI tight loop | CPU writes `spi0_hw->dr` in loop | No actual RF transmission | Same as DMA — register access doesn't drive LR2021 correctly |
| Runtime SPI clock change | `spi_deinit()+spi_init()` | Permanently kills radio sync | SPI peripheral teardown breaks LR2021 sync, needs full HW reset |
| PIO state machine v1 | PIO drives SPI from boot | Kills USB CDC immediately. 1377 kbps (no gain over Arduino) | DMA_IRQ_0 starves TinyUSB IRQ |
| PIO state machine v2 | Hybrid Arduino init + PIO TX | CDC alive during init, dies during TX loop | Same — DMA and USB conflict during sustained TX |
| PIO state machine v3 | Deferred printing fix | CDC partially restored. Throughput unmeasured (CDC unstable) | Fundamental incompatibility remains |

**Root cause of ALL failures:** The LR2021 chip requires specific per-byte
SPI timing — CS assertion pattern, inter-byte gaps, BUSY pin waits — that
batch/DMA/PIO methods don't replicate. Only Arduino's `transfer()` function
maintains the correct timing protocol because it goes through the full
Arduino SPI transaction layer.

### 2.2 RX-Side: Never Optimized

**Critical gap:** ALL optimization effort went to TX. The RX hot loop still
uses the same Arduino byte-by-byte `transfer()` for FIFO reads. No DMA, no
PIO, no dual-core was ever attempted on the RX side.

The PIO RX code exists in the repo (`pio_lr2021_rx.cpp`, `pio_lr2021_rx.pio`)
but was never flashed or tested. It was written but never reached hardware.

---

## 3. THE CURRENT BOTTLENECK — COMPLETE PICTURE

### 3.1 TX Per-Packet Breakdown (v4 at 1377 kbps, ~1481µs total)

| Component | Time (µs) | % of Total | Reducible? |
|-----------|-----------|------------|------------|
| **RF air time** | **803** | **54%** | **NO — physics (2088 bits / 2.6 Mbps)** |
| Arduino SPI (268 bytes @ 12 MHz actual) | 535 | 36% | No working alternative on RP2040 |
| IRQ poll + loop overhead | 143 | 10% | Partially (~24µs via combined CS) |

**Key insight:** SPI overlaps with air time. While packet N is on-air (803µs),
CPU starts writing packet N+1 to the FIFO (535µs). The overlap means SPI
savings yield almost nothing:
- Arduino SPI: 1367 kbps
- PIO SPI (saves 430µs): 1377 kbps → **0.7% gain (noise)**

### 3.2 RX Per-Packet Breakdown (~572µs blind window)

For each received packet, the RX loop does:

| Step | SPI Bytes | Time (µs) | During This Time |
|------|-----------|-----------|------------------|
| Read IRQ status | 6 | ~12 | Radio not listening |
| Read RX FIFO (255 bytes) | 257 | ~514 | Radio not listening |
| Clear IRQ | 6 | ~12 | Radio not listening |
| Re-arm RX (SET_RX) | 2 | ~4 | Radio not listening |
| BUSY waits | — | ~30 | Radio not listening |
| **Total blind window** | **271** | **~572** | **Any incoming packet is LOST** |

The 514µs FIFO read dominates. It's 255 bytes × Arduino `transfer()` = ~2µs per byte.

### 3.3 The Coupling Problem

TX and RX throughput are linked through the blind window:

```
TX packet interval:     1481µs (at 1377 kbps)
RX blind window:         572µs
RX listening window:     909µs
RF air time:             803µs
Spare margin:            106µs (just enough)
```

If TX gets faster (say 800µs/pkt), RX blind window (572µs) leaves only 228µs
of listening — less than the 803µs air time. Packets would be dropped.
**The RX blind window is the hard limit on bidirectional throughput.**

This is the exact same problem the ESP32 had. The RP2040 platform switch
did not fix it because we're using the same Arduino SPI approach.

### 3.4 Why We Can't Break 803µs Air Time

```
FLRC air rate:     2,600,000 bps
Payload:           255 bytes = 2,040 bits
Preamble:          16 bits
Sync word:         32 bits
Total per packet:  2,088 bits
Air time:          2,088 / 2,600,000 = 803µs  ← IMMUTABLE PHYSICS
```

The maximum possible payload throughput is:
```
2,040 / 0.000803 = 2,540,847 bps ≈ 2540 kbps
```

Current: 1377 kbps = 54% of theoretical max.

---

## 4. THE FPGA QUESTION

### 4.1 What an FPGA Would Fix

An FPGA implements SPI in pure hardware logic — gates, not software. It could
replicate Arduino `transfer()`'s exact timing pattern but at hardware speed
with zero CPU overhead. The LR2021 SPI timing requirements that break every
RP2040 optimization wouldn't matter — the FPGA generates timing in silicon.

### 4.2 FPGA Throughput Projection

| Component | Arduino (current) | FPGA (projected) | Gain |
|-----------|-------------------|-------------------|------|
| TX SPI (268 bytes) | 535µs | ~50µs | 10.7× |
| TX overhead | 143µs | ~30µs | 4.8× |
| TX total per packet | 1481µs | ~883µs (air time dominates) | 1.7× |
| TX throughput | 1377 kbps | ~2310 kbps | 1.7× |
| TX with full overlap | — | ~803µs | — |
| **TX theoretical max** | — | **2540 kbps** | — |
| RX blind window | 572µs | ~108µs | 5.3× |
| RX listening % | 62% | 92% | 1.5× |

### 4.3 Why FPGA Is Probably Wrong

1. **Weight & power for flight:** Pico balloon target is <14g. Even smallest
   iCE40 (LP384) adds ~0.5g and draws 10-20mA. Flight hardware is ESP32-C3
   + LR2021. Adding a third chip defeats the purpose.

2. **Three untested paths remain cheaper:** ESP32-C3 native DMA, RP2040
   dual-core, RP2040 logic-analyzer-driven PIO. All are free (existing
   hardware), none have been tried.

3. **ESP32-C3 has different SPI hardware:** The reasons DMA failed on RP2040
   (Pico SDK FIFO management, `spi0_hw->dr` register behavior) are
   RP2040-specific. The ESP32's `spi_master` driver with DMA might work
   perfectly with LR2021. Never tested.

4. **Application doesn't need it:** Balloon telemetry = 24 bytes/minute =
   0.003 kbps. Mesh relay = a few kbps. 1377 kbps is 500× more than needed.
   The throughput work was about proving link capacity, not application need.

5. **Air time is the floor:** Even FPGA can't break 803µs. 2540 kbps is the
   absolute ceiling. Going from 1377 to 2540 doesn't change any application
   outcome.

### 4.4 When FPGA Would Be Justified

- If we need sustained >2000 kbps bidirectional throughput
- AND ESP32-C3 DMA fails with LR2021
- AND RP2040 dual-core doesn't shrink the blind window enough
- AND we've characterized exact SPI timing with a logic analyzer
- THEN a small FPGA (iCE40 UP5K, ~$5, 28-QFN, available) would be the path

---

## 5. PLATFORM COMPARISON — HONEST ASSESSMENT

| Feature | ESP32-C3 | RP2040 | FPGA (iCE40) |
|---------|----------|--------|--------------|
| Current tested throughput | 15.5 kbps (original) | 1377 kbps (optimized) | Untested |
| Native SPI DMA | `spi_master` driver — UNTESTED with LR2021 | `spi0_hw->dr` — FAILED with LR2021 | N/A (SPI in logic) |
| PIO / custom SPI HW | N/A | Exists, FAILED on TX, never tested on RX | Full custom |
| Dual-core | Single core | Dual core — NEVER TESTED | Parallel pipelines |
| USB CDC stability | Native USB Serial | TinyUSB — dies under DMA_IRQ load | N/A |
| Weight (flight) | ~2g (bare chip) | N/A (dev only) | +0.5g minimum |
| Power | Low (sleep modes) | Low | Moderate (10-20mA) |
| Application fit | Flight hardware ✓ | Dev boards only | Overkill |

**The ESP32-C3 is the correct platform for flight. The RP2040 was useful for
development but we outgrew its hardware acceleration limitations. The right
next step is testing ESP32-C3 native SPI DMA.**

---

## 6. SUMMARY OF WHERE WE ARE

```
Proven link:        TX 1377 kbps, RX 0% loss, RF confirmed
TX ceiling:         ~1400 kbps (air time + Arduino SPI overlap)
RX blind window:    572µs (514µs is FIFO read — the real bottleneck)
Theoretical max:    2540 kbps (air time limited, unbreakable)
Platform gap:       RP2040 hardware acceleration all failed
Untested paths:     ESP32 DMA, RP2040 dual-core, RP2040 PIO RX, logic analyzer
FPGA verdict:       Theoretically reaches ~2500 kbps, practically unnecessary
```

---

*See `docs/flrc-optimization-comprehensive-plan-2026-07-16.md` for the
actionable plan to pursue the remaining optimization paths.*
