# Comprehensive Speed Test Plan (2026-07-17)

## PURPOSE

Maximize SPI throughput between RP2040 and LR2021 using existing
hardware. No FPGA, no platform switch. Push beyond 1377 kbps.

## CURRENT STATE

| Metric | Value | Method |
|--------|-------|--------|
| TX throughput | 1377 kbps | Arduino per-byte SPI.transfer() |
| TX_DONE success | 1000/1000 | BUSY pin polling |
| RX packet loss | 0% | At <1m distance |
| SPI method | Per-byte only | ALL alternatives failed |
| SPI frequency | 16 MHz requested, ~12 MHz actual | RP2040 prescaler limit |
| Per-packet time | 1492 µs | 803µs RF + 535µs SPI + 154µs overhead |
| RX blind window | 572 µs | 514µs FIFO read + 58µs overhead |

## ROOT CAUSE HYPOTHESIS (REVISED)

Previous batch SPI tests used TWO separate transfer() calls under one CS:

```cpp
spiRf.transfer(hdr, nullptr, 2);      // batch 1 — SCK runs then STOPS
spiRf.transfer(data, nullptr, 255);   // batch 2 — SCK restarts
```

`spi_write_blocking()` drains the FIFO between calls → SCK stops → LR2021
may reject discontinuous clock during CS assertion.

**Proposed fix:** Concatenate into ONE transfer call:
```cpp
uint8_t combined[257] = {0x00, 0x02, ...payload...};
spiRf.transfer(combined, nullptr, 257);  // continuous SCK
```

## EXPERIMENTS (PRIORITY ORDER)

### Experiment 1: Single-Batch SPI Test (30 MIN — HIGHEST VALUE)

**Goal:** Test if continuous SCK batch transfer works with LR2021.

**Steps:**
1. Write `flrc_tx_single_batch.cpp` — identical to flrc_raw_tx.cpp but
   replaces split-batch calls with concatenated single-batch calls
2. All SPI write functions use pre-built buffers with header+payload combined
3. Flash to TX board
4. Run: send 1000 packets, check TX_DONE count
5. If TX_DONE=1000/1000: RX board listens, check reception
6. Measure throughput with `scripts/coordinated_tx_rx_test.py`

**Files to create:**
- `firmware/rp2040/src/flrc_tx_single_batch.cpp`
- PlatformIO env `rp2040-flrc-tx-single-batch`

**Expected outcomes:**
- BEST: TX_DONE=1000/1000, RX receives, throughput >1800 kbps
- GOOD: TX_DONE=1000/1000, but no speed improvement (batch isn't faster)
- BAD: TX_DONE=0/1000 — confirms LR2021 rejects batch SPI fundamentally

**Decision gate:**
- If BEST: proceed to Experiment 3 (optimize further)
- If GOOD: batch works but SDK overhead negates gain → Experiment 4
- If BAD: batch fundamentally incompatible → Experiment 4 (dual-core)

### Experiment 2: Self-Timing Diagnostic (10 MIN — ALREADY WRITTEN)

**Goal:** Get exact µs timing for per-byte vs split-batch vs single-batch.

**Status:** Firmware written (`flrc_spi_timing_diag.cpp`), builds OK.
Board F242D is in BOOTSEL from last session. Needs reflashing.

**Steps:**
1. Reflash `rp2040-spi-timing-diag` to board F242D
2. Send "RUN\n" over serial
3. Capture output — 3 numbers:
   - Per-byte average µs (working baseline)
   - Split-batch average µs (failed method)
   - Single-batch average µs (proposed fix)
4. Calculate speedup factor and inter-batch gap cost

**What we learn:**
- Exact SPI cost per method (eliminates all estimation)
- Whether single-batch is actually faster than per-byte
- How much time the SCK gap costs in split-batch

**No radio chip needed for this test** — pure SPI timing measurement.

### Experiment 3: Dual-Core RX Pipelining (2-4 HRS — INDEPENDENT)

**Goal:** Shrink RX blind window from 572µs to ~100µs by overlapping
FIFO read with radio re-arm.

**Architecture:**
```
Core 0 (radio manager):
  - Poll IRQ pin
  - On IRQ: signal Core 1, clear IRQ, set RX (re-arm radio ASAP)
  - ~60µs to re-arm vs current 572µs

Core 1 (FIFO reader):
  - Wait for signal from Core 0
  - Read 255 bytes from RX FIFO (514µs)
  - Extract sequence number
  - Update statistics
  - Done — ready for next signal
```

**Critical question:** Does LR2021 preserve FIFO data after SET_RX command?
If SET_RX clears the FIFO, we must read BEFORE re-arming (no pipelining gain).

**FIFO protocol research needed:**
- Check SX1281 datasheet: does SET_RX clear RX_FIFO?
- Check LR2021: same silicon family, likely same behavior
- Alternative: if FIFO is cleared, use LR2021's packet queueing (if supported)
- Test empirically: read FIFO, then re-arm, check if data still valid

**Steps:**
1. Research FIFO behavior (datasheet + empirical test)
2. Write `flrc_dual_core_rx.cpp`
3. PlatformIO env `rp2040-flrc-dualcore-rx`
4. Flash to RX board, test with current TX
5. Measure: blind window, packet loss at various TX rates

**Expected outcomes:**
- BEST: Blind window <100µs → supports TX rates up to ~2000 kbps
- MODERATE: Blind window ~300µs → some improvement, limited TX headroom
- BLOCKED: FIFO cleared on SET_RX → need alternative approach

### Experiment 4: SPI Frequency Push (30 MIN)

**Goal:** Test if LR2021 can handle higher SPI clock speeds.

**Current:** 16 MHz requested → ~12 MHz actual (RP2040 prescaler: 125MHz/(10*1)=12.5MHz)

**Test frequencies:**
- 8 MHz (0x4C prescaler — conservative)
- 12 MHz (current actual)
- 16 MHz (current requested)
- 20 MHz (attempt — RP2040 prescaler: 125MHz/(6*1)=20.83MHz)
- 24 MHz (attempt — may not be achievable)

**Protocol:**
1. In TX firmware, change SPI_FREQ_HZ constant
2. Flash, run 1000-packet test
3. Check TX_DONE and RX reception at each frequency

**Risk:** Higher SPI clock may cause LR2021 command errors. Watch for:
- Status=0x00 (radio dead — SPI too fast for chip)
- TX_DONE=0 (command not received properly)
- Random corruption

**Expected:** LR2021 datasheet specifies max SPI clock. Need to check.
SX1281 datasheet says 18 MHz max. RP2040 can deliver 20.83 MHz — may
exceed chip spec.

### Experiment 5: DMA RX (DEPENDS ON EXPERIMENT 1 RESULT)

**Goal:** If single-batch SPI works (Exp 1), try DMA for RX FIFO read.

**Rationale:** If the batch compatibility issue is solved, DMA may now work.
DMA would read the RX FIFO with zero CPU overhead.

**Steps:**
1. Configure DMA channel: source=spi0_hw->dr, dest=rx_buffer, count=257
2. Trigger DMA on IRQ pin rising edge (or manual trigger)
3. Wait for DMA completion
4. Process buffer

**Expected:** If DMA works, RX FIFO read drops from 514µs to ~20µs (just
DMA setup + bus arbitration). Blind window becomes negligible.

### Experiment 6: Logic Analyzer Capture (NON-BLOCKING — WHEN CONVENIENT)

**Goal:** Document exact SPI timing for root cause analysis.

**Status:** NOT a prerequisite for any other experiment. Only needed for
academic documentation of why batch/DMA failed originally.

**Equipment:** Red Pitaya (available), 6 probe wires.

**Only do this if:**
- Experiments 1-5 all fail and we're stuck
- We want to publish/present the findings
- We have spare time between range tests

---

## EXECUTION ORDER

```
Exp 2 (timing diag, 10 min)
  ↓
Exp 1 (single-batch, 30 min)
  ↓
  ├─ WORKS → Exp 4 (SPI freq push) → Exp 5 (DMA RX)
  │
  └─ FAILS → Exp 3 (dual-core RX)
               ↓
               └─ Combined TX per-byte + dual-core RX = best achievable
```

**Parallel:** Exp 2 and Exp 3 can be coded simultaneously.
Exp 3 is independent of Exp 1 result.

## FIRMWARE ENVIRONMENT MATRIX

| Env Name | Purpose | Status |
|----------|---------|--------|
| rp2040-flrc-tx-raw | Current TX baseline | DONE, proven |
| rp2040-flrc-rx-raw | Current RX baseline | DONE, proven |
| rp2040-spi-timing-diag | SPI timing measurement | BUILT, needs flash |
| rp2040-flrc-tx-single-batch | Single-batch SPI test | TO WRITE |
| rp2040-flrc-dualcore-rx | Dual-core RX pipelining | TO WRITE |
| rp2040-flrc-dma-rx | DMA RX (if batch works) | TO WRITE |

## MEASUREMENT PROTOCOL

Every experiment records:
1. TX_DONE count (out of 1000)
2. RX packets received + loss %
3. Throughput (kbps) — from coordinated test script
4. Any status byte anomalies
5. Any USB CDC issues

Save to: docs/speed-test-results-2026-07-XX.md

## SUCCESS CRITERIA

| Milestone | Target | Method |
|-----------|--------|--------|
| Timing baseline | Exact µs per method | Exp 2 |
| Batch SPI works | TX_DONE=1000/1000 | Exp 1 |
| Throughput >1500 kbps | Any improvement | Exp 1 or 4 |
| Throughput >1800 kbps | Significant gain | Exp 1+4 combined |
| RX blind window <200µs | Dual-core gain | Exp 3 |
| Batch+DMA RX | Zero-copy FIFO read | Exp 5 |
| Max throughput achieved | Best of all experiments | Combined |

## WHAT WE DON'T NEED

- Logic analyzer (not a blocker)
- FPGA (rejected — maximize RP2040 first)
- Platform switch (RP2040 is the platform)
- ESP32 DMA test (RP2040 is sufficient, no need to revisit ESP32)
