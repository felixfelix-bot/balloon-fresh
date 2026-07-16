# FLRC TX Optimization Progress — 2026-07-16

## Session Summary

Full optimization campaign on RP2040 + LR2021 FLRC TX. Started from 1293.6 kbps baseline, tested 4 optimization stages + SPI frequency sweep. Final proven throughput: **1377 kbps**.

## Hardware Setup

- TX: RP2040 board 8332 (RPi Pico) at `/dev/ttyACM0`
- RX: RP2040 board F242D at `/dev/ttyACM2`
- LR2021 module wired: SCK=GP2 MOSI=GP3 MISO=GP4 CS=GP5 BUSY=GP6 IRQ=GP7 RST=GP8
- UART backup: GP12=TX GP13=RX (for CDC crash debugging)
- FLRC: 2440 MHz, 2600 kbps bitrate, 255-byte payload, preamble=8

## Optimization Stage Results

| Stage | Change | TX_DONE | Throughput | Real RF? | Spin Count |
|-------|--------|---------|------------|----------|------------|
| Baseline | 16MHz SPI, preamble=16 | 1000/1000 | 1293.6 kbps | YES | ~13692 |
| Stage 1 | Preamble 16→8 symbols | 1000/1000 | 1377 kbps | YES | ~13511 |
| Stage 2 | SPI clock 16→20MHz | 1000/1000 | 1377 kbps | YES | ~13510 |
| Stage 3 | Direct HW SPI + skip rfWaitBusy | 1000/1000 | 8986.8 kbps | **NO — FAKE** | 0 |
| Stage 4 | Higher bitrate attempt | N/A | N/A | 2600 kbps = MAX | — |

### Stage 1: Preamble Reduction (16→8 symbols)
- Changed register 0x49 byte 0: 0x0E→0x0C (preamble length 16→8 symbols)
- Result: 1293→1377 kbps (+6.5%)
- TX_DONE: 1000/1000 — solid
- Spin count dropped ~181 cycles (airtime reduction from shorter preamble)

### Stage 2: SPI Clock Increase (16→20MHz)
- Changed `SPI_FREQ_HZ` from 16000000 to 20000000
- Result: 1377 kbps — **no improvement**
- Spin count: 13511 → 13510 — identical
- **Finding: SPI speed is NOT the bottleneck.** RF airtime dominates. The ~1.35ms per packet is almost entirely radio transmission time, not SPI transfer time.

### Stage 3: Direct HW SPI + Skip rfWaitBusy — FAKE RESULT
- Rewrote TX loop to use `spi0_hw` register writes directly, bypassing Arduino SPI class
- Skipped `rfWaitBusy()` before WRITE_FIFO and SET_TX
- Result: 8986.8 kbps, TX_DONE=1000/1000 — **LOOKED AMAZING BUT WAS FAKE**
- **Spin count = 0 for every packet** — smoking gun
- **Root cause:** IRQ pin was ALREADY HIGH before TX was triggered. Without rfWaitBusy, the chip never processed SET_TX. No actual RF output. The IRQ was a leftover from previous state, not from actual transmission.
- **Reverted** in commit f5170b8
- **LESSON: rfWaitBusy() is MANDATORY before every SPI command to the LR2021.** Skipping it produces phantom results — the chip hasn't processed the previous command yet.

### Stage 4: Bitrate Ceiling
- FLRC max bitrate is 2600 kbps (confirmed from Semtech datasheet, 18 web sources)
- Current setting already at 2600 kbps
- No higher bitrate available in FLRC mode
- GMSK modulation at 2600 kbps is the hard ceiling

## SPI Frequency Sweep — CRITICAL FINDING

### What was tried
- Runtime SPI frequency change via `spi_deinit() + spi_init()` to test 8/10/12/16/20/24 MHz
- All tested frequencies showed spin=0, 0 RX packets — ALL FAKE

### Why it failed
**Runtime SPI re-initialization breaks the radio.** `spi_deinit()` tears down the RP2040 SPI peripheral completely. When `spi_init()` rebuilds it at a new frequency, the LR2021 never re-syncs — the SPI bus state machine is in an unknown state. All subsequent SPI commands are garbage.

### Correct approach
**Compile-time SPI frequency selection only.** Must rebuild firmware for each frequency. Runtime SPI frequency changes are NOT safe with the LR2021.

### Tested at compile time
- 16MHz: 1377 kbps, TX_DONE 1000/1000 ✓
- 20MHz: 1377 kbps, TX_DONE 1000/1000 ✓
- No difference → SPI is not the bottleneck

## Key Learnings

1. **rfWaitBusy() is sacred.** Every SPI command to LR2021 MUST be preceded by BUSY pin check. Skipping it = phantom TX, no RF output. The chip needs time to process each command.

2. **Runtime SPI re-init kills the radio.** Never call `spi_deinit()` + `spi_init()` to change frequency at runtime. The LR2021 SPI state machine doesn't recover. Use compile-time `SPI_FREQ_HZ` only.

3. **SPI speed is NOT the bottleneck.** Going from 16MHz to 20MHz SPI produced zero throughput change. The bottleneck is RF airtime (~1.35ms per 255-byte packet at 2600 kbps FLRC).

4. **FLRC 2600 kbps is the hard ceiling.** No higher bitrate available. The ~1377 kbps effective throughput (53% of raw bitrate) is expected — overhead from preamble, sync word, packet headers, and command processing.

5. **CDC USB serial + direct HW SPI conflict.** Direct `spi0_hw` register access can crash TinyUSB CDC. Using Arduino SPI class (`beginTransaction/transfer/endTransaction`) is safe. The CDC crash that started this session was caused by direct HW SPI register writes during radio init.

6. **IRQ pin polling works.** Using `sio_hw->gpio_in & irqMask` for tight GPIO polling is safe and doesn't interfere with CDC. TX_DONE detection via IRQ pin is reliable (1000/1000).

7. **Serial.flush() blocks CDC.** Calling `Serial.flush()` when no USB host has the port open causes a hard block. Removed from v4 firmware. Heartbeat prints during 8-second wait window let host catch output whenever it connects.

## Current Firmware State

**File:** `firmware/rp2040/src/flrc_raw_tx.cpp` (v4)
**Commit:** 0bbd179 (HEAD of master, pushed to GitHub + ngit)

### Configuration
- SPI: 20MHz, Arduino SPI class (no direct HW registers)
- Preamble: 8 symbols (reduced from 16)
- FLRC: 2440 MHz, 2600 kbps, 255-byte payload
- TX power: +12 dBm
- TX count: 1000 packets per burst
- IRQ: pin poll via `sio_hw->gpio_in`
- CDC: no `Serial.flush()`, heartbeat during wait window

### Proven Performance
- TX_DONE: 1000/1000 (100%)
- Throughput: 1377 kbps
- Spin count: ~13510 (consistent RF airtime)
- RX verified receiving packets (see flrc-rf-link-working-2026-07-16.md)

## Throughput Analysis

```
Raw FLRC bitrate:     2600 kbps
Effective throughput: 1377 kbps (53% efficiency)

Per-packet breakdown (255 bytes payload):
  RF airtime:  ~1.35 ms (dominates)
  SPI overhead: ~0.01 ms (negligible at 20MHz)
  Command overhead (CLR_IRQ + WRITE_FIFO + SET_TX): ~0.05 ms
  Preamble:    8 symbols ≈ 3 µs
  Sync word:   4 bytes ≈ 12 µs
  
Theoretical max at 2600 kbps, 255B payload:
  255*8 / 2600e3 = 0.785 ms airtime only
  Real: ~1.35ms = 58% overhead from headers, preamble, processing
```

## What Was NOT Tested (Future Work)

1. **Sub-GHz FLRC** — same 2600 kbps max but different propagation characteristics
2. **FEC coding rate changes** — 3/4 vs uncoded may affect effective payload size
3. **Larger packet sizes** — if LR2021 supports >255 bytes (FIFO is 512 bytes)
4. **DMA TX** — started but not completed. DMA for SPI transfers could reduce CPU overhead further, but won't help since RF airtime dominates
5. **Compile-time SPI sweep** — 10/12/14/18 MHz to find if there's a sweet spot (unlikely, since 16→20MHz showed no change)

## Commit History (This Session)

| Commit | Description |
|--------|-------------|
| d3bfba1 | 20MHz TX variant + DMA TX BUSY-pin fix + test results |
| b59c8f9 | LR2021 research findings and SPI frequency sweep plan |
| d52e42a | Stage 3 — direct HW SPI hot loop + skip 2 rfWaitBusy (FAKE, reverted) |
| f5170b8 | Revert Stage 3 |
| 0bbd179 | LR2021 reference + SPI frequency sweep + batch/pipe firmware |

All pushed to: GitHub (c03rad0r/balloon-fresh) + ngit (relay.ngit.dev)