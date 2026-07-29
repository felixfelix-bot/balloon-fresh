# LR2021 Throughput Bottleneck Analysis

**Date:** 2026-07-29  
**Branch:** speed-sustained-sweep  
**Datasheet reference:** Semtech LR2021 LR2022 LR2012 Datasheet Rev 2.1 (`docs/LR2021_LR2022_LR2012_Datasheet_Rev2.1.pdf`)

---

## Executive Summary

A full audit of the FLRC firmware against the Semtech LR2021 datasheet identified **8 throughput bottlenecks** in the current SPI command sequences. The modulation parameters are already optimal (2600 kbps, uncoded CR=1, BT0.5), so all remaining gains come from SPI and protocol overhead reduction.

### Current Throughput vs Theoretical Maximum

| Platform | Current | Pipelined Max | Non-Pipelined Max | Theoretical Max | Efficiency |
|----------|---------|---------------|--------------------|-----------------|------------|
| RP2040   | 1377 kbps | 2540 kbps | 2200 kbps | 2540 kbps | 54% |
| ESP32-C3 | 838 kbps  | 2540 kbps | 2200 kbps | 2540 kbps | 33% |

At 2600 kbps air rate with 255-byte payloads, RF air time is ~803 µs. SPI at 16 MHz for 257 bytes takes ~128 µs. If SPI is overlapped with RF (pipelined), the system approaches 2540 kbps. Without pipelining, 2200 kbps.

---

## Bottleneck #1: SPI Clock Capped at 12 MHz on RP2040

| Field | Value |
|-------|-------|
| **Datasheet optimal** | 16 MHz (min SCK period 61.5 ns) |
| **Current** | 12 MHz actual — RP2040 prescaler maps ≥12 MHz requests to 12 MHz |
| **Impact** | ~25% SPI bandwidth lost |
| **Fix difficulty** | Medium — RP2040 prescaler limitation; may need PIO-based SPI |

### Details

The RP2040 system clock runs at 125 MHz. The SPI peripheral prescaler only supports even integer dividers, so achievable SPI clock frequencies are 125/N MHz for integer N. To get 16 MHz you'd need N=7.8125, which is not an integer — the closest achievable rates are 15.625 MHz (N=8) and 17.857 MHz (N=7), neither of which the prescaler can produce. Requests for 16–20 MHz all map to 12 MHz actual (N≈10.4 → 12.5 MHz rounded down to 12 MHz by the Arduino core).

### Code References

- `flrc_raw_tx.cpp:32` — requests 20 MHz (`SPI_HZ = 20 * 1000 * 1000`)
- `flrc_raw_tx_pipe.cpp:37` — requests 16 MHz
- `flrc_cont_tx.cpp:46` — requests 20 MHz

### Fix Approach

PIO-based SPI on RP2040 could achieve arbitrary clock frequencies including 16 MHz. Alternatively, overclocking the system clock to a frequency that divides cleanly to 16 MHz (e.g., 128 MHz → 16 MHz with N=8). Requires validation that the LR2021 reliably accepts 16 MHz SCK.

---

## Bottleneck #2: ESP32-C3 Overdrives SPI at 40 MHz

| Field | Value |
|-------|-------|
| **Datasheet max** | 16 MHz |
| **Current** | 40 MHz (2.5× datasheet maximum) |
| **Impact** | Reliability risk, not a throughput bottleneck |
| **Fix difficulty** | Easy — change one #define |

### Details

The ESP32-C3 is configured at 40 MHz SPI clock, which is 2.5× the datasheet maximum of 16 MHz. This works at bench range (~1 m) due to short trace/wire lengths, but at operational range the faster edges may cause signal integrity issues leading to corrupted SPI transactions, dropped packets, or silent failures. This is a reliability risk, not a throughput issue — reducing to 16 MHz will make SPI transfers take longer but will dramatically improve robustness.

### Code Reference

- `EspHalC3.h:32` — `#define ESPHAL_C3_SPI_HZ (40 * 1000 * 1000)`

### Fix

Change to `(16 * 1000 * 1000)`. Validate that throughput impact is minimal (SPI is not the dominant time component on ESP32 — protocol overhead is).

---

## Bottleneck #3: Per-Byte `transfer()` for FIFO Write on RP2040

| Field | Value |
|-------|-------|
| **Datasheet optimal** | `WriteRadioTxFifo` (0x0002) — single SPI frame, continuous SCK, no NSS toggle per byte |
| **Current** | Per-byte `spiRf.transfer(data[i])` in loop — ~535 µs for 257 bytes |
| **Optimal at 16 MHz** | ~128 µs for 257 bytes |
| **Impact** | 407 µs/pkt wasted (29% of total packet time) |
| **Fix difficulty** | HARD — blocked on logic analyzer diagnosis |

### Details

The datasheet specifies that `WriteRadioTxFifo` (opcode 0x0002) should be a single SPI transaction: pull NSS LOW, send opcode, send all payload bytes with continuous SCK, raise NSS. The current RP2040 TX code sends each byte individually via `spiRf.transfer()`, which toggles NSS per byte and incurs per-byte function call overhead.

At 12 MHz, per-byte transfer of 257 bytes takes ~535 µs. A single batch transfer at 16 MHz would take ~128 µs — a 407 µs saving per packet, which is 29% of the total packet cycle time.

### Code References

- `flrc_raw_tx.cpp:104-113` — per-byte `spiRf.transfer(data[i])` loop
- `flrc_cont_tx.cpp:178-189` — uses batch `transfer(buf, rx, len)`, closer to optimal

### Critical Blocker

Previous batch/DMA/PIO SPI transfer attempts on RP2040 with the LR2021 **all failed** — symptoms included fake TX_DONE interrupts and initialization failures. The root cause was never diagnosed because **no logic analyzer was used** to capture the actual SPI bus signals. This is the single highest-impact fix but is blocked on hardware diagnosis.

### Fix Approach

1. Capture SPI bus with logic analyzer during both per-byte and batch transfers
2. Compare timing, NSS behavior, and SCK signal quality
3. Identify why batch transfer fails (likely: NSS timing, SCK glitches between bytes, or FIFO pointer management)
4. Implement working batch transfer or PIO-based SPI

---

## Bottleneck #4: BUSY Polling Before Every Command

| Field | Value |
|-------|-------|
| **Datasheet** | BUSY must be LOW before each SPI command; DIO interrupts available |
| **Current** | `rfWaitBusy()` called before every `rfWriteCmd`, `rfWriteTxFifo`, `rfReadIrqStatus` |
| **Impact** | ~30 µs per call × 3-4 calls per packet = ~90-120 µs/pkt (~8% of total packet time) |
| **Fix difficulty** | Medium — eliminate redundant waits, use DIO interrupt |

### Details

The LR2021 asserts BUSY during command processing. The datasheet requires BUSY to be LOW before sending a new SPI command. However, many of the current BUSY waits are redundant — after the IRQ pin goes HIGH (indicating TX_DONE or RX_DONE), the chip has already returned to STDBY mode and BUSY is already LOW.

The current code calls `rfWaitBusy()` unconditionally before every SPI command, adding ~30 µs of spin-wait per call. With 3-4 commands per packet cycle, this wastes 90-120 µs per packet.

### Code References

- `flrc_raw_tx.cpp:49-53` — RP2040 TX: BUSY wait before every command
- `flrc_raw_rx.cpp:57-62` — RP2040 RX: BUSY wait before every command
- `esp32_raw_rx.cpp:50-55` — ESP32 RX: BUSY wait before every command

### Fix Approach

1. After IRQ pin goes HIGH, chip is in STDBY — BUSY is already LOW. Remove the BUSY wait before `WRITE_FIFO` and `SET_TX` in the pipelined path.
2. Use DIO interrupt to detect command completion instead of polling BUSY.

---

## Bottleneck #5: IRQ Pin Polling via Spin Loop (No GPIO Interrupts)

| Field | Value |
|-------|-------|
| **Datasheet** | DIO pins provide interrupt signals for TX_DONE, RX_DONE, etc. |
| **Current** | Tight spin-loop polling of IRQ/DIO pin |
| **Impact** | CPU waste, timing jitter, RX blind window |
| **Fix difficulty** | Medium — RP2040 has no easy GPIO interrupt in Arduino; ESP32 has task notification |

### Details

All firmware variants poll the IRQ/DIO pin in a tight spin loop rather than using GPIO interrupts. This wastes CPU cycles, introduces timing jitter, and creates RX blind windows where the radio cannot receive because the CPU is busy polling.

**RP2040 TX** (`flrc_raw_tx.cpp:257-259`): `while(spinCount < 500000)` spin loop — blind delay, no actual IRQ check.

**RP2040 RX** (`flrc_raw_rx.cpp:308`): Calls `rfReadIrqStatus()` — a 6-byte SPI read — **every loop iteration**. This is massive overhead: each iteration costs ~20 µs of SPI time just to check if a packet arrived.

**ESP32 RX** (`esp32_raw_rx.cpp:314`): Correctly polls the DIO9 GPIO pin first (cheap digital read), only does the SPI read if the pin is HIGH. This is the correct pattern.

### Fix Approach

- **ESP32:** Switch from DIO9 GPIO polling to GPIO interrupt + FreeRTOS task notification. The bench version already does this per `RESULTS.md` line 243.
- **RP2040:** Replace the `rfReadIrqStatus()` SPI poll loop with a DIO9 GPIO pin check (like ESP32 does). RP2040 Arduino core doesn't expose easy GPIO interrupts, but direct register access or PIO can be used.

---

## Bottleneck #6: No SetAutoRxTx — Re-issue SetTx/SetRx Per Packet

| Field | Value |
|-------|-------|
| **Datasheet** | `SetAutoRxTx` enables continuous TX/RX cycling without re-issuing commands |
| **Current** | 4-5 SPI commands per packet (CLR_IRQ, CLR_FIFO, CLR_ERR, WRITE_FIFO, SET_TX) |
| **Impact** | ~100 µs/pkt overhead |
| **Fix difficulty** | Medium — need to verify SetAutoRxTx works in FLRC mode on LR2021 |

### Details

The LR2021 datasheet defines `SetAutoRxTx` which configures the radio to automatically cycle between TX and RX modes without host intervention. When enabled, the chip automatically re-arms after each TX_DONE or RX_DONE, eliminating the need to re-issue `SetTx` or `SetRx` commands for every packet.

`SetAutoRxTx` is **not used anywhere** in the codebase (zero matches across all source files). The ESP32 bench `RESULTS.md` line 209 notes that `autoTxRx()` was tested successfully in RadioLib but was never integrated into the raw SPI hot path.

### Current Per-Packet Command Sequence

1. `CLR_IRQ` — clear interrupt flags
2. `CLR_TX_FIFO` — clear TX FIFO (unnecessary, see bottleneck #7)
3. `CLR_ERRORS` — clear error flags (unnecessary, see bottleneck #7)
4. `WRITE_FIFO` — write payload to TX FIFO
5. `SET_TX` — start transmission

### With SetAutoRxTx

1. `WRITE_FIFO` — write payload to TX FIFO
2. (chip auto-transmits and auto-re-arms)

### Fix Approach

1. Test `SetAutoRxTx` in FLRC mode on both RP2040 and ESP32 with actual hardware
2. Verify timing parameters (dead time between TX_DONE and next TX)
3. Integrate into hot path if successful

---

## Bottleneck #7: Redundant Per-Packet Commands

| Field | Value |
|-------|-------|
| **Datasheet** | TX FIFO auto-cleared on TX_DONE; error clear only needed if error IRQ is set |
| **Current** | `CLR_TX_FIFO` + `CLR_ERRORS` issued every packet unconditionally |
| **Impact** | ~60 µs/pkt on RP2040, ~30 µs/pkt on ESP32 |
| **Fix difficulty** | EASY — remove from hot loop |

### Details

Two commands in the per-packet hot loop are unnecessary in normal operation:

1. **`CLR_TX_FIFO`**: The datasheet states that the TX FIFO is automatically cleared when TX_DONE is asserted. Issuing this command every packet is redundant — it only needs to be sent on initialization or after an abort.

2. **`CLR_ERRORS`**: The error clear command is only needed when an error IRQ flag is set. In normal operation (no errors), issuing this every packet wastes SPI time.

### Code References

- `flrc_raw_tx_pipe.cpp:308-321` — adds `CLR_TX_FIFO` + `CLEAR_ERRORS` to hot loop
- `esp32_raw_tx.cpp:296-326` — `rfClearErrors()` + `rfClearTxFifo()` every packet

### Fix Approach

Remove both commands from the hot loop. Only issue them when the corresponding IRQ flags are set (error IRQ → clear errors; initialization or abort → clear FIFO). This is a pure code change with no hardware dependencies.

---

## Bottleneck #8: ESP32 Two-Phase FIFO Read

| Field | Value |
|-------|-------|
| **Datasheet** | `ReadRadioRxFifo` (0x0001) — single continuous SPI frame |
| **Current (ESP32)** | Two-phase: opcode sent, CS raised, BUSY wait, CS lowered again, data read |
| **Current (RP2040)** | Correct single-phase — opcode + read in one CS-low session |
| **Impact** | ~30 µs/pkt on ESP32 |
| **Fix difficulty** | EASY — merge into single CS-low session |

### Details

The datasheet specifies that `ReadRadioRxFifo` (opcode 0x0001) should be a single SPI transaction: pull NSS LOW, send opcode, read all payload bytes with continuous SCK, raise NSS. The RP2040 correctly implements this as a single CS-low session.

The ESP32 implementation incorrectly splits this into two phases:
1. Phase 1: Pull CS LOW, send opcode, pull CS HIGH
2. BUSY wait
3. Phase 2: Pull CS LOW again, read data, pull CS HIGH

This adds an extra CS toggle and an extra BUSY wait per packet read, wasting ~30 µs.

### Code References

- `esp32_raw_rx.cpp:82-98` — two-phase FIFO read (incorrect)
- `flrc_raw_rx.cpp:74-85` — single-phase FIFO read (correct, reference implementation)

### Fix Approach

Modify the ESP32 RX FIFO read to match the RP2040 pattern: send opcode and read data in a single CS-low session with continuous SCK. No BUSY wait needed between opcode and data read for FIFO reads.

---

## Additional Finding: Pulse Shape Mismatch

Not a throughput bottleneck, but a link margin issue discovered during the audit:

| Platform | Pulse Shape | Register Value |
|----------|-------------|----------------|
| RP2040   | BT0.5       | 0x05           |
| ESP32    | BT0.5       | 0x05           |

The two platforms use different pulse shape filters. Cross-platform TX→RX communication will have degraded link margin because the receiver's matched filter doesn't match the transmitter's pulse shape. Standardizing on BT0.5 (0x05) across both platforms will improve cross-platform link margin.

### Code References

- RP2040: `flrc_raw_tx.cpp` — BT0.5 (0x05)
- ESP32: `esp32_raw_tx.cpp:195` — BT0.5 (0x05) ✅
- ESP32: `esp32_raw_rx.cpp:180` — BT0.5 (0x05) ✅

Status: unified on BT0.5 across RP2040 and ESP32.

## Bottleneck Summary Table

| # | Bottleneck | Platform | Impact (µs/pkt) | Fix Difficulty |
|---|-----------|----------|-----------------|----------------|
| 1 | SPI clock capped at 12 MHz | RP2040 | ~25% SPI BW lost | Medium |
| 2 | ESP32 SPI at 40 MHz (overdriven) | ESP32 | Reliability risk | Easy |
| 3 | Per-byte transfer() for FIFO write | RP2040 | 407 µs (29%) | Hard |
| 4 | BUSY polling before every command | Both | 90-120 µs (8%) | Medium |
| 5 | IRQ spin-loop polling (no GPIO int) | Both | CPU waste + jitter | Medium |
| 6 | No SetAutoRxTx | Both | ~100 µs | Medium |
| 7 | Redundant per-packet commands | Both | 30-60 µs | Easy |
| 8 | ESP32 two-phase FIFO read | ESP32 | ~30 µs | Easy |

## Theoretical Maximum Calculation

| Component | Time |
|-----------|------|
| RF air time (255-byte payload @ 2600 kbps) | ~803 µs |
| SPI at 16 MHz (257 bytes = 255 payload + 2 opcode) | ~128 µs |
| **Pipelined total** (SPI overlapped with RF) | ~803 µs → **2540 kbps** |
| **Non-pipelined total** (SPI + RF sequential) | ~931 µs → **2200 kbps** |

Current RP2040 at 1377 kbps achieves 54% of the pipelined maximum.  
Current ESP32 at 838 kbps achieves 33% of the pipelined maximum.

The modulation parameters are already optimal — no air-time improvement is possible. All gains must come from reducing SPI and protocol overhead.