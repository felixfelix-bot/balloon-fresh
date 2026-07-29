# LR2021 Throughput Fix Plan

**Date:** 2026-07-29  
**Branch:** speed-sustained-sweep  
**Companion document:** `docs/lr2021-bottleneck-analysis-2026-07-29.md`

---

## Overview

This plan addresses all 8 throughput bottlenecks identified in the bottleneck analysis. It is organized into 4 phases, ordered from quick wins (no hardware, low risk) through advanced pipelining. Each phase builds on the gains from the previous one.

### Expected Throughput Progression

| Phase | RP2040 Target | ESP32 Target | Key Gains |
|-------|---------------|--------------|-----------|
| Current | 1377 kbps | 838 kbps | — |
| Phase 0 (Quick Wins) | ~1460 kbps | ~900+ kbps | Remove redundant commands, fix SPI clock, fix FIFO read |
| Phase 1 (Protocol Opt) | ~1570 kbps | ~1000+ kbps | SetAutoRxTx, eliminate BUSY waits, GPIO interrupts |
| Phase 2 (SPI Acceleration) | ~2200+ kbps | ~1000+ kbps | Batch SPI transfer on RP2040 |
| Phase 3 (Pipelining) | ~2540 kbps | ~2540 kbps | TX pipelining, dual-core RX |

---

## Phase 0 — Quick Wins (No Hardware, Low Risk)

**Goal:** Eliminate obvious waste in the hot loop. No hardware changes, no architectural changes, minimal risk of regression.

### Task 0.1: Remove Redundant CLR_TX_FIFO + CLR_ERR from RP2040 TX Hot Loop

**Description:**  
The RP2040 pipelined TX hot loop issues `CLR_TX_FIFO` and `CLEAR_ERRORS` on every packet. Per the LR2021 datasheet, the TX FIFO is auto-cleared on TX_DONE and error clear is only needed when an error IRQ is set. Remove both commands from the hot loop; only issue them when the corresponding IRQ flags indicate an error condition.

**Files to modify:**
- `flrc_raw_tx_pipe.cpp` lines 308-321 — remove `CLR_TX_FIFO` + `CLEAR_ERRORS` calls from hot loop

**Expected impact:** ~60 µs/pkt saved on RP2040

**Dependencies:** None

**Test plan:**
1. Capture throughput before change (baseline: ~1377 kbps)
2. Implement change
3. Run sustained TX test for 60 seconds — measure throughput
4. Verify no FIFO overflow errors or stuck TX state
5. Inject an error condition (e.g., bad SPI clock) and verify error recovery still works
6. Capture throughput after change — expect ~1460 kbps

---

### Task 0.2: Remove Redundant rfClearErrors() + rfClearTxFifo() from ESP32 TX Hot Loop

**Description:**  
Same issue as Task 0.1 but on ESP32. The ESP32 TX hot loop calls `rfClearErrors()` and `rfClearTxFifo()` every packet. Remove from hot loop; only call on error IRQ.

**Files to modify:**
- `esp32_raw_tx.cpp` lines 296-326 — remove `rfClearErrors()` + `rfClearTxFifo()` from hot loop

**Expected impact:** ~30 µs/pkt saved on ESP32

**Dependencies:** None

**Test plan:**
1. Capture throughput before change (baseline: ~838 kbps)
2. Implement change
3. Run sustained TX test for 60 seconds — measure throughput
4. Verify no error accumulation or TX stalls
5. Capture throughput after change

---

### Task 0.3: Fix ESP32 Two-Phase FIFO Read → Single CS-Low Session

**Description:**  
The ESP32 RX FIFO read incorrectly splits the operation into two SPI transactions (opcode, CS HIGH, BUSY wait, CS LOW, data read). The datasheet specifies `ReadRadioRxFifo` (0x0001) as a single continuous SPI frame. The RP2040 already implements this correctly. Match the ESP32 implementation to the RP2040 pattern.

**Files to modify:**
- `esp32_raw_rx.cpp` lines 82-98 — merge two-phase read into single CS-low session

**Reference implementation:**
- `flrc_raw_rx.cpp` lines 74-85 — correct single-phase pattern

**Expected impact:** ~30 µs/pkt saved on ESP32

**Dependencies:** None

**Test plan:**
1. Capture RX throughput before change
2. Implement single-phase read
3. Run RX test — verify packets are received with correct payload
4. Verify RSSI and packet count match baseline
5. Capture RX throughput after change

---

### Task 0.4: Fix ESP32 SPI Clock 40 MHz → 16 MHz

**Description:**  
The ESP32-C3 SPI is configured at 40 MHz, which is 2.5× the LR2021 datasheet maximum of 16 MHz. This works at bench range but is a reliability risk at operational distance. Reduce to the datasheet-specified maximum.

**Files to modify:**
- `EspHalC3.h` line 32 — change `#define ESPHAL_C3_SPI_HZ (40 * 1000 * 1000)` to `(16 * 1000 * 1000)`

**Expected impact:** No throughput gain (SPI time increases slightly), but eliminates reliability risk. The SPI time increase (~2.5× slower per byte) is offset by the fact that SPI is not the dominant time component on ESP32 (protocol overhead is).

**Dependencies:** None

**Test plan:**
1. Verify bench RX/TX still works at 16 MHz
2. Run sustained throughput test — verify throughput is stable
3. If possible, test at range (>10 m) and compare packet loss rate vs 40 MHz

---

### Task 0.5: Unify Pulse Shape — Standardize on BT0.5

**Description:**  
RP2040 uses BT0.5 (0x05) pulse shape filter while ESP32 uses BT1.0 (0x07). This mismatch degrades cross-platform link margin because the receiver's matched filter doesn't match the transmitter's pulse shape. Standardize on BT0.5 (0x05) across both platforms.

**Files to modify:**
- `esp32_raw_tx.cpp` line 195 — change pulse shape from 0x07 (BT1.0) to 0x05 (BT0.5)
- `esp32_raw_rx.cpp` line 180 — change pulse shape from 0x07 (BT1.0) to 0x05 (BT0.5)

**Expected impact:** No throughput change, but improved cross-platform link margin (RP2040 TX → ESP32 RX and vice versa).

**Dependencies:** None

**Test plan:**
1. Verify ESP32 self-loopback (TX → RX) still works with BT0.5
2. Verify cross-platform RP2040 TX → ESP32 RX works with BT0.5
3. Compare RSSI at fixed distance with BT0.5 vs BT1.0
4. Verify no packet loss increase

---

### Phase 0 Summary

| Task | Platform | Saved (µs/pkt) | Difficulty |
|------|----------|----------------|------------|
| 0.1 | RP2040 | ~60 | Easy |
| 0.2 | ESP32 | ~30 | Easy |
| 0.3 | ESP32 | ~30 | Easy |
| 0.4 | ESP32 | 0 (reliability) | Easy |
| 0.5 | Both | 0 (link margin) | Easy |

**Expected post-Phase 0 throughput:** RP2040 ~1460 kbps, ESP32 ~900+ kbps

---

## Phase 1 — Protocol Optimization (No Hardware, Medium Risk)

**Goal:** Optimize SPI command sequences and interrupt handling. No hardware changes, but requires careful validation of timing and chip state transitions.

### Task 1.1: Investigate + Implement SetAutoRxTx for FLRC Mode

**Description:**  
The LR2021 datasheet defines `SetAutoRxTx` which enables continuous TX/RX cycling without re-issuing commands. This would eliminate the `SET_TX`/`SET_RX` command per packet, saving ~40 µs/pkt. `SetAutoRxTx` is not used anywhere in the codebase. The ESP32 bench `RESULTS.md` line 209 notes that `autoTxRx()` was tested successfully in RadioLib but never integrated into the raw SPI hot path.

**Files to modify:**
- `flrc_raw_tx_pipe.cpp` — add `SetAutoRxTx` configuration and remove per-packet `SET_TX`
- `flrc_raw_rx.cpp` — add `SetAutoRxTx` configuration and remove per-packet `SET_RX`
- `esp32_raw_tx.cpp` — same changes
- `esp32_raw_rx.cpp` — same changes

**Expected impact:** ~40 µs/pkt saved (eliminates SetTx/SetRx command overhead)

**Dependencies:**
- Verify `SetAutoRxTx` works in FLRC mode (not just LoRa) on LR2021
- Verify timing parameters (dead time between TX_DONE and next TX) are acceptable
- RadioLib source for `autoTxRx()` reference implementation

**Test plan:**
1. Add `SetAutoRxTx` command to initialization sequence on both platforms
2. Remove `SET_TX`/`SET_RX` from hot loop
3. Verify TX still works — send 1000 packets, confirm all received
4. Verify RX still works — receive 1000 packets, confirm all received with correct payload
5. Measure throughput — expect ~40 µs/pkt improvement
6. Test edge cases: long payload (255 bytes), short payload (8 bytes), burst of packets
7. Verify auto-recovery after a missed packet or collision

---

### Task 1.2: Eliminate Redundant rfWaitBusy() Calls

**Description:**  
`rfWaitBusy()` is called before every SPI command, but many of these waits are redundant. After the IRQ pin goes HIGH (TX_DONE or RX_DONE), the chip has returned to STDBY mode and BUSY is already LOW. The wait before `WRITE_FIFO` and `SET_TX` in the pipelined path can be removed.

**Files to modify:**
- `flrc_raw_tx.cpp` lines 49-53 — remove redundant BUSY waits before `WRITE_FIFO` and `SET_TX`
- `flrc_raw_rx.cpp` lines 57-62 — remove redundant BUSY waits in RX path
- `esp32_raw_rx.cpp` lines 50-55 — remove redundant BUSY waits in RX path

**Expected impact:** ~50-60 µs/pkt saved (eliminates 2-3 redundant BUSY waits per packet)

**Dependencies:** None (but should be done after Task 0.1/0.2 to ensure error handling is clean)

**Test plan:**
1. Add timing instrumentation: measure BUSY pin state at each call site
2. Verify that BUSY is already LOW after IRQ pin HIGH (confirm chip is in STDBY)
3. Remove redundant waits one at a time, testing after each removal
4. Run sustained throughput test for 60 seconds
5. Verify no SPI errors or command failures
6. Measure throughput improvement

---

### Task 1.3: ESP32 RX — Switch to GPIO Interrupt + Task Notification

**Description:**  
The ESP32 RX currently polls the DIO9 GPIO pin in a spin loop. The bench version already uses GPIO interrupt + FreeRTOS task notification per `RESULTS.md` line 243. Switch the raw SPI hot path to the same pattern.

**Files to modify:**
- `esp32_raw_rx.cpp` — replace DIO9 polling loop with GPIO interrupt + `xTaskNotifyWait()`

**Expected impact:** Eliminates CPU spin-loop waste, reduces jitter, enables background processing during RX wait

**Dependencies:** FreeRTOS (already available on ESP32)

**Test plan:**
1. Configure DIO9 as GPIO interrupt source (falling edge for RX_DONE)
2. Create FreeRTOS task that blocks on `xTaskNotifyWait()`
3. GPIO ISR sends notification via `xTaskNotifyGive()`
4. Task wakes, reads FIFO, processes packet
5. Measure RX latency (time from DIO9 falling edge to FIFO read complete)
6. Compare jitter: polling vs interrupt
7. Run sustained RX test — measure throughput and packet loss

---

### Task 1.4: RP2040 RX — Replace rfReadIrqStatus() SPI Poll with DIO9 GPIO Check

**Description:**  
The RP2040 RX hot loop calls `rfReadIrqStatus()` — a 6-byte SPI read — every iteration to check if a packet arrived. This is ~20 µs of SPI time per iteration. Replace with a DIO9 GPIO pin check (cheap digital read) first, only doing the SPI read if the pin is HIGH. This matches the ESP32 pattern.

**Files to modify:**
- `flrc_raw_rx.cpp` line 308 — replace `rfReadIrqStatus()` poll loop with DIO9 GPIO check

**Reference implementation:**
- `esp32_raw_rx.cpp` line 314 — DIO9 GPIO pin check pattern

**Expected impact:** Eliminates ~20 µs SPI overhead per poll iteration, reduces RX blind window

**Dependencies:** None

**Test plan:**
1. Add DIO9 GPIO read before `rfReadIrqStatus()` call
2. Only call `rfReadIrqStatus()` if DIO9 is HIGH
3. Verify packets are still received correctly
4. Measure poll loop iteration time (GPIO read vs SPI read)
5. Run sustained RX test — measure throughput and packet loss

---

### Phase 1 Summary

| Task | Platform | Saved (µs/pkt) | Difficulty | Dependencies |
|------|----------|----------------|------------|--------------|
| 1.1 | Both | ~40 | Medium | Verify FLRC mode support |
| 1.2 | Both | ~50-60 | Medium | After Phase 0 |
| 1.3 | ESP32 | CPU/jitter | Medium | FreeRTOS |
| 1.4 | RP2040 | ~20/iteration | Medium | None |

**Expected post-Phase 1 throughput:** RP2040 ~1570 kbps, ESP32 ~1000+ kbps

---

## Phase 2 — SPI Acceleration (Blocked on Logic Analyzer)

**Goal:** Achieve batch SPI transfer on RP2040 to eliminate the 407 µs/pkt per-byte transfer overhead. This phase is blocked on logic analyzer diagnosis of why batch/DMA/PIO SPI transfers fail on RP2040 with LR2021.

### Task 2.1: Logic Analyzer Capture of RP2040 SPI Bus

**Description:**  
Previous batch/DMA/PIO SPI transfer attempts on RP2040 with LR2021 all failed — symptoms included fake TX_DONE interrupts and initialization failures. No logic analyzer was used to diagnose the root cause. Capture the actual SPI bus signals during both per-byte and batch transfers to identify the failure mode.

**Files to modify:** None (diagnostic task)

**Expected impact:** Diagnostic — unblocks Tasks 2.2 and 2.3

**Dependencies:** Logic analyzer hardware ( Saleae, Sigrok-compatible, or similar)

**Test plan:**
1. Connect logic analyzer to RP2040 SPI bus: SCK, MOSI, NSS, BUSY, DIO9
2. Capture per-byte `transfer()` sequence — verify NSS timing, SCK continuity, BUSY behavior
3. Capture batch `transfer(buf, rx, len)` sequence — compare with per-byte capture
4. Look for: NSS glitches, SCK timing violations, BUSY assertion between bytes, FIFO pointer issues
5. Capture DMA-based transfer if available
6. Document findings: timing diagrams, root cause hypothesis

---

### Task 2.2: Implement Working Batch SPI Transfer on RP2040

**Description:**  
Based on logic analyzer findings from Task 2.1, implement a working batch SPI transfer for FIFO writes on RP2040. The target is a single CS-low session that sends the `WriteRadioTxFifo` opcode followed by all payload bytes with continuous SCK.

**Files to modify:**
- `flrc_raw_tx.cpp` lines 104-113 — replace per-byte loop with batch transfer
- Possibly: new SPI wrapper function or PIO program if standard SPI peripheral can't do batch

**Expected impact:** 535 µs → 128 µs for 257-byte FIFO write = 407 µs saved per packet

**Dependencies:** Task 2.1 (logic analyzer diagnosis)

**Test plan:**
1. Implement batch transfer based on Task 2.1 findings
2. Verify TX works — send 1000 packets, confirm all received by counterparty
3. Verify no fake TX_DONE interrupts
4. Measure SPI transfer time with logic analyzer — confirm ~128 µs for 257 bytes
5. Run sustained throughput test for 60 seconds — expect ~2200+ kbps
6. Test edge cases: max payload (255 bytes), min payload (8 bytes), back-to-back packets

---

### Task 2.3: RP2040 SPI Clock Increase to 16 MHz via PIO

**Description:**  
If the standard RP2040 SPI peripheral cannot achieve 16 MHz (due to prescaler limitations — see bottleneck #1), implement PIO-based SPI that can generate an exact 16 MHz SCK. This requires writing a PIO program that bit-bangs SPI at the desired frequency.

**Files to modify:**
- New PIO program file (e.g., `spi16.pio`)
- SPI initialization code to switch from hardware SPI to PIO SPI

**Expected impact:** Additional ~25% SPI bandwidth beyond 12 MHz (combined with Task 2.2 batch transfer, SPI time drops to ~128 µs at 16 MHz vs ~160 µs at 12 MHz)

**Dependencies:** Task 2.1, Task 2.2 (batch transfer must work first)

**Test plan:**
1. Write PIO SPI program targeting 16 MHz SCK
2. Verify SCK frequency with logic analyzer
3. Run basic SPI loopback test
4. Test with LR2021: write config registers, read back, verify correct values
5. Run TX throughput test — measure improvement
6. Run sustained test for 60 seconds — verify stability

---

### Phase 2 Summary

| Task | Platform | Saved (µs/pkt) | Difficulty | Dependencies |
|------|----------|----------------|------------|--------------|
| 2.1 | RP2040 | Diagnostic | — | Logic analyzer |
| 2.2 | RP2040 | ~407 | Hard | Task 2.1 |
| 2.3 | RP2040 | ~32 | Hard | Tasks 2.1, 2.2 |

**Expected post-Phase 2 throughput:** RP2040 ~2200+ kbps, ESP32 unchanged (~1000+ kbps)

---

## Phase 3 — Advanced Pipelining

**Goal:** Overlap SPI operations with RF transmission to approach the theoretical maximum of 2540 kbps. This requires architectural changes to the packet processing pipeline.

### Task 3.1: True TX Pipelining — Write Next FIFO During Current TX

**Description:**  
Currently, the firmware writes the payload to the TX FIFO, then waits for TX_DONE before starting the next packet. True pipelining writes the next packet's payload to the FIFO while the current packet is still being transmitted over RF. The TxDone IRQ for the current packet triggers the next TX.

**Sequence:**
1. Write packet N to FIFO → SET_TX
2. While packet N is transmitting (803 µs air time), write packet N+1 to FIFO
3. On TxDone IRQ for packet N, immediately SET_TX for packet N+1 (FIFO already loaded)
4. Repeat

This overlaps the 128 µs SPI write with the 803 µs RF air time, making SPI time invisible.

**Files to modify:**
- `flrc_raw_tx_pipe.cpp` — restructure loop to pre-load next packet
- `flrc_raw_tx.cpp` — same restructure for non-piped version
- `esp32_raw_tx.cpp` — same

**Expected impact:** SPI time becomes invisible (overlapped with RF) → throughput approaches 803 µs/pkt = 2540 kbps

**Dependencies:** Tasks 2.2 (batch SPI), 1.1 (SetAutoRxTx or fast SET_TX), 1.2 (no redundant BUSY waits)

**Test plan:**
1. Implement double-buffered TX: prepare packet N+1 while N is transmitting
2. Use TxDone IRQ (not spin loop) to trigger SET_TX for N+1
3. Verify packet ordering is maintained (N before N+1)
4. Measure inter-packet gap with logic analyzer — target: <10 µs
5. Run sustained throughput test for 120 seconds — target: 2540 kbps
6. Test with varying payload sizes — verify pipelining works for all sizes
7. Verify no FIFO corruption or packet duplication

---

### Task 3.2: RP2040 Dual-Core RX — Parallel Re-arm + FIFO Read

**Description:**  
Currently, RX processing is single-threaded: receive packet, read FIFO, re-arm radio, repeat. The re-arm gap is the RX blind window (~572 µs where the radio can't receive). Using RP2040's second core, Core 0 can re-arm the radio while Core 1 reads the FIFO in parallel, shrinking the blind window from ~572 µs to ~100 µs.

**Files to modify:**
- `flrc_raw_rx.cpp` — split into two-core architecture
- New: inter-core communication (FIFO queue via SDK mutex/queue)

**Expected impact:** RX blind window shrinks from 572 µs to ~100 µs → higher sustained RX throughput

**Dependencies:** Task 1.4 (DIO9 GPIO check), RP2040 SDK multicore support

**Test plan:**
1. Implement dual-core RX: Core 0 (re-arm radio + DIO9 wait), Core 1 (FIFO read + packet processing)
2. Use inter-core queue to pass received packets from Core 0 to Core 1
3. Measure RX blind window with logic analyzer — target: <100 µs
4. Run sustained RX test with continuous transmitter — measure throughput
5. Verify no packet loss during FIFO read (radio is re-armed in parallel)
6. Test with high packet rate — verify queue doesn't overflow

---

### Task 3.3: FIFO Threshold IRQs for Large Payloads

**Description:**  
For payloads larger than the FIFO size (256 bytes), the LR2021 provides `TxFifoLevel` and `RxFifoLevel` interrupts that fire when the FIFO crosses a threshold. This enables streaming large payloads without waiting for the full FIFO to drain/fill. While current payloads are ≤255 bytes, this future-proofs for larger messages.

**Files to modify:**
- TX path — add `TxFifoLevel` IRQ handler for streaming writes
- RX path — add `RxFifoLevel` IRQ handler for streaming reads

**Expected impact:** Enables payloads >256 bytes without throughput penalty

**Dependencies:** Tasks 3.1 (TX pipelining), understanding of FIFO threshold registers

**Test plan:**
1. Configure FIFO threshold at 50% (128 bytes)
2. TX: write first 128 bytes, wait for TxFifoLevel IRQ, write next 128 bytes
3. RX: read first 128 bytes on RxFifoLevel IRQ, read remaining on RX_DONE
4. Verify large payloads (512 bytes) are transmitted/received correctly
5. Measure throughput with large payloads — verify no degradation vs small payloads

---

### Phase 3 Summary

| Task | Platform | Impact | Difficulty | Dependencies |
|------|----------|--------|------------|--------------|
| 3.1 | Both | SPI invisible → 2540 kbps | Hard | Tasks 2.2, 1.1, 1.2 |
| 3.2 | RP2040 | RX blind window 572→100 µs | Hard | Task 1.4 |
| 3.3 | Both | Large payload support | Medium | Task 3.1 |

**Expected post-Phase 3 throughput:** ~2540 kbps (theoretical maximum)

---

## Dependency Graph

```
Phase 0 (Quick Wins)
├── Task 0.1 (RP2040: remove redundant CLR) ──┐
├── Task 0.2 (ESP32: remove redundant CLR)   ├── Phase 1
├── Task 0.3 (ESP32: fix FIFO read)          │   ├── Task 1.1 (SetAutoRxTx) ──┐
├── Task 0.4 (ESP32: fix SPI clock)          │   ├── Task 1.2 (BUSY waits) ──┤
└── Task 0.5 (Unify pulse shape)             │   ├── Task 1.3 (ESP32 GPIO int)│
                                             │   └── Task 1.4 (RP2040 DIO9)──┤
                                             │                               │
                                             ├── Phase 2                      │
                                             │   ├── Task 2.1 (Logic analyzer)│
                                             │   ├── Task 2.2 (Batch SPI) ────┤
                                             │   └── Task 2.3 (PIO 16 MHz) ──┤
                                             │                               │
                                             └── Phase 3                      │
                                                 ├── Task 3.1 (TX pipeline)──┘
                                                 ├── Task 3.2 (Dual-core RX)
                                                 └── Task 3.3 (FIFO threshold)
```

---

## Measurement Protocol

All throughput measurements should follow this protocol for consistency:

1. **Test duration:** 60 seconds minimum (120 seconds for Phase 3)
2. **Payload size:** 255 bytes (maximum, worst case)
3. **Metrics:** 
   - Throughput (kbps) = (bytes_received × 8) / test_duration
   - Packet count
   - Packet loss rate
   - Inter-packet gap (via logic analyzer or timestamp)
4. **Environment:** Bench setup (1 m distance) for development; range test for validation
5. **Baseline:** Capture baseline before each phase, compare after
6. **Stability:** Verify no error accumulation, no memory leaks, no state corruption over test duration

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| SetAutoRxTx doesn't work in FLRC mode | Test early; if it fails, keep manual SET_TX/SET_RX |
| Batch SPI fails again on RP2040 | Logic analyzer diagnosis first; don't guess |
| TX pipelining causes FIFO corruption | Double-buffer with explicit state machine; verify ordering |
| Dual-core RX race condition | Use mutex/queue; verify with stress test |
| ESP32 16 MHz SPI is slower than 40 MHz | SPI is not dominant time component; protocol savings compensate |
| Pulse shape change affects link margin | Test at range after change; BT0.5 is standard for FLRC |

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2026-07-29 | Initial | Created from bottleneck analysis |