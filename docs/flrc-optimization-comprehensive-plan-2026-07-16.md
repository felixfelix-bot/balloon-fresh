# FLRC Throughput Optimization — Comprehensive Plan

**Date:** 2026-07-16
**Status:** SUPERSEDED — split into two active plans below
**Repo:** balloon-fresh
**Pre-requisite reading:** `docs/flrc-platform-analysis-2026-07-16.md`

> **UPDATE 2026-07-16:** This plan has been superseded by two focused, actionable plans:
> - **[PLAN-speed-optimization.md](PLAN-speed-optimization.md)** — Throughput optimization track (breaking 1391 kbps ceiling)
> - **[PLAN-range-tests.md](PLAN-range-tests.md)** — Range testing track (distance/bitrate/payload sweeps)
>
> Each has its own handover document for separate context windows:
> - [HANDOVER-speed-tests.md](HANDOVER-speed-tests.md)
> - [HANDOVER-range-tests.md](HANDOVER-range-tests.md)
>
> This document is kept for historical context. The two plans above are authoritative.

---

## CURRENT STATE

- TX: 1377 kbps, 1000/1000 TX_DONE, proven on RP2040
- RX: 0% packet loss, DEADBEEF marker received
- RX blind window: 572µs (514µs FIFO read dominates)
- RP2040 hardware acceleration: ALL FAILED (PIO, DMA, batch, direct HW)
- Platform: RP2040 dev boards (NOT the ESP32-C3 flight hardware)

## OBJECTIVE

Maximize sustainable bidirectional FLRC throughput. Current ceiling ~1400 kbps.
Theoretical max ~2540 kbps. The gap is SPI overhead, not physics.

---

## PHASE 0 — ESP32-C3 NATIVE SPI DMA TEST
**Priority: HIGHEST (cheapest, most promising, uses existing flight hardware)**
**Estimated effort: 1-2 days**
**Hardware needed: 2x ESP32-C3 boards with LR2021 wired (already exist)**

### Rationale
The ESP32-C3 has a completely different SPI peripheral than the RP2040. The
reasons DMA failed on RP2040 (Pico SDK FIFO management, `spi0_hw->dr` register
behavior) are RP2040-specific. The ESP32's `spi_master` driver is designed for
exactly this: hardware DMA feeding SPI FIFOs autonomously. We never tested it.

The ESP32-C3 is also the actual flight hardware — so if DMA works here, the
problem is permanently solved with zero extra components.

### Steps

0.1. **Audit existing ESP32 bench firmware** — `mesh-stack/flrc-bench-espidf/`
already has RadioLib-based FLRC firmware for ESP32-C3. Verify pin mapping
matches current wiring (SCK=GPIO6, MISO=GPIO2, MOSI=GPIO7, NSS=GPIO10,
BUSY=GPIO4, IRQ=GPIO5, RST=GPIO3).

0.2. **Write ESP32 raw SPI TX firmware** — Port the proven RP2040 v4 raw SPI
approach (no RadioLib for hot loop) to ESP32-C3 using `spi_master` driver.
Key: use `spi_device_polling_transmit()` for per-byte or burst writes, then
test `spi_device_transmit()` with DMA for FIFO writes.

0.3. **Write ESP32 raw SPI RX firmware** — Same approach for RX side. Use
GPIO interrupt (ESP32 native interrupt, not polling) for RX_DONE detection.
Test `spi_device_polling_transmit()` for FIFO reads first, then DMA.

0.4. **TX throughput test** — Measure TX throughput on ESP32-C3. Compare
to RP2040 baseline (1377 kbps). If ESP32 `spi_master` DMA works: expect
1800-2200 kbps (SPI overhead drops from 535µs to ~100µs).

0.5. **Coordinated TX+RX test** — Two ESP32-C3 boards. Measure packet loss
and RX blind window. If ESP32 DMA reads the RX FIFO faster, blind window
drops from 572µs to maybe ~150µs → supports higher TX rates without loss.

0.6. **Decision gate:**
- If ESP32 DMA works with LR2021 → **PROBLEM SOLVED.** Port to flight
  hardware, move to application layer (Phase 4+). Skip Phases 1-3.
- If ESP32 DMA fails same as RP2040 → proceed to Phase 1.

### Deliverables
- `firmware/esp32-c3-flrc/flrc_tx_dma.cpp` — ESP32 TX with raw SPI
- `firmware/esp32-c3-flrc/flrc_rx_dma.cpp` — ESP32 RX with raw SPI
- Test results committed and pushed
- Throughput comparison: ESP32 vs RP2040

---

## PHASE 1 — RP2040 DUAL-CORE RX PIPELINING
**Priority: HIGH (free, no new hardware, targets the real bottleneck)**
**Estimated effort: 2-3 days**
**Hardware needed: Same 2x RP2040 Pico boards**

### Rationale
The RX blind window (572µs) is the real throughput limiter. Of that, 514µs is
the FIFO read. The RP2040 has TWO cores but we only use Core 0.

Concept: Core 0 detects RX_DONE (GPIO poll, ~2µs) and immediately re-arms RX
(CLEAR_IRQ + SET_RX, ~16µs). Core 1 reads the FIFO data (514µs) in parallel
while the radio is already listening for the next packet.

```
Current (single core):
  |--detect--|--read FIFO (514µs)--|--clear+rearm--|  BLIND=572µs

Dual-core:
  Core 0: |--detect--|--clear+rearm--|  BLIND=~18µs
  Core 1:                |--read FIFO 514µs (in parallel)--|
```

Blind window drops from 572µs to ~18µs. Radio listening time goes from 62%
to 98%. This supports TX rates up to ~2400 kbps without RX loss.

### Steps

1.1. **Write dual-core RX firmware** — `flrc_raw_rx_dualcore.cpp`:
- Core 0: tight GPIO poll on IRQ pin → on RX_DONE → copy FIFO pointer →
  signal Core 1 via FIFO/queue → CLEAR_IRQ + SET_RX → back to polling
- Core 1: wait for signal → read FIFO data → process packet (seq extraction,
  stats, DEADBEEF check) → signal done → wait for next

1.2. **Shared buffer management** — Ping-pong double buffer:
- Buffer A: being filled by Core 1 from FIFO
- Buffer B: available for next RX_DONE
- Swap on each cycle. No contention, no locks needed if timing is right.

1.3. **Test with current TX (1377 kbps)** — Verify 0% packet loss maintained.
This is the baseline — dual-core must not break what works.

1.4. **Test with faster TX** — If we can increase TX rate (e.g., pipe firmware
at 1389 kbps or faster), measure where RX starts dropping. This reveals the
new blind window limit.

1.5. **Measure actual blind window** — Toggle a GPIO when RX re-arms, read
with logic analyzer or scope. Confirm ~18µs target.

1.6. **Decision gate:**
- If blind window <100µs and 0% loss at >1500 kbps → **SUCCESS.** Dual-core
  RX works. Proceed to Phase 4 (application layer). Optionally try Phase 2
  for further gain.
- If blind window still >300µs or packets dropped at current rate → dual-core
  approach failed. Proceed to Phase 2.

### Deliverables
- `firmware/rp2040/src/flrc_raw_rx_dualcore.cpp`
- Blind window measurement (scope/logic analyzer)
- Throughput + packet loss comparison

---

## PHASE 2 — LOGIC ANALYZER CAPTURE + PIO SPI REWORK
**Priority: MEDIUM (high effort, targets root cause)**
**Estimated effort: 3-5 days**
**Hardware needed: Logic analyzer (Saleae-compatible, $10-25)**

### Rationale
Every PIO/DMA attempt failed because we didn't know the exact SPI timing the
LR2021 requires. We were guessing. A logic analyzer capture of a WORKING
Arduino `transfer()` transaction would show us:
- Exact CS assertion timing (how long before first clock edge?)
- Inter-byte gaps (how long between bytes? constant or variable?)
- SCK frequency and duty cycle
- BUSY pin behavior relative to SPI transactions
- Whether the chip requires "dummy" bytes or specific read/write sequencing

With this data, we can program the RP2040 PIO to replicate it exactly.

### Steps

2.1. **Capture working SPI transaction** — Connect logic analyzer to RP2040
Pico running v4 TX firmware. Capture:
- CS (GP5), SCK (GP2), MOSI (GP3), MISO (GP4), BUSY (GP6)
- Trigger on CS falling edge
- Record full TX cycle: CLR_IRQ → WRITE_FIFO (255 bytes) → SET_TX → BUSY wait
- Sample rate: ≥50 MHz (SPI is 12 MHz, need 4x oversampling minimum)

2.2. **Analyze timing** — Measure:
- CS setup time (CS low to first SCK edge)
- CS hold time (last SCK edge to CS high)
- Inter-byte gap (time between consecutive bytes in same transaction)
- BUSY assert/deassert timing relative to CS
- Whether there are any unusual gaps or protocol quirks

2.3. **Compare with PIO output** — Flash PIO TX firmware, capture same
transaction. Compare timing to Arduino `transfer()`. Identify discrepancies.

2.4. **Fix PIO program** — Adjust PIO state machine to match Arduino timing
exactly. This may require:
- Adding delay states for CS setup/hold
- Adjusting inter-byte gaps
- Matching CS toggle pattern (Arduino does CS low → transfer → CS high
  per call; PIO might need same pattern, not continuous CS)

2.5. **Test fixed PIO on TX** — Verify TX_DONE count, compare throughput
to v4 baseline. If PIO now works without killing CDC:
- SPI overhead drops from 535µs to ~50µs
- TX throughput approaches ~2540 kbps

2.6. **Test fixed PIO on RX** — Apply same PIO approach to RX FIFO reads.
If it works:
- FIFO read drops from 514µs to ~50µs
- Blind window drops from 572µs to ~80µs
- Combined with dual-core: ~18µs blind window

2.7. **Decision gate:**
- If PIO TX works and CDC survives → **BREAKTHROUGH.** Full hardware SPI
  on RP2040. Proceed to combine with dual-core RX.
- If PIO still doesn't work even with exact timing → LR2021 may require
  something beyond what we can replicate in PIO. Proceed to Phase 3 (ESP32
  flight hardware) or accept ~1400 kbps ceiling.

### Deliverables
- Logic analyzer captures (saved as .sal or .csv)
- Timing analysis document
- Fixed PIO program
- TX/RX throughput with PIO SPI

---

## PHASE 3 — ESP32-C3 FLIGHT HARDWARE PORT
**Priority: HIGH regardless of throughput results (this is the target platform)**
**Estimated effort: 3-5 days**
**Hardware needed: ESP32-C3 dev boards + LR2021 (already have)**

### Rationale
Even if we hit 2540 kbps on RP2040, the flight hardware is ESP32-C3. All
throughput work must eventually port to ESP32-C3. This phase happens in
parallel with Phases 0-2 — it's the application platform, not just a test.

If Phase 0 (ESP32 DMA) succeeded, this is already done. If not, we port the
proven Arduino SPI approach from RP2040 to ESP32-C3 and accept whatever
throughput it gives.

### Steps

3.1. **Port v4 TX firmware to ESP32-C3** — Translate RP2040 raw SPI commands
to ESP32 `spi_master` driver. Same LR2021 init sequence, same packet format,
same DEADBEEF marker. Use polling mode (not DMA) first to establish baseline.

3.2. **Port RX firmware to ESP32-C3** — Same translation. ESP32 has native
GPIO interrupts (better than RP2040 polling). Use `gpio_isr_handler_add()`
for RX_DONE detection.

3.3. **Measure ESP32-C3 throughput** — Compare to RP2040:
- ESP32 clock: 160 MHz (vs RP2040 125 MHz) — faster CPU
- ESP32 SPI: hardware DMA capable (if it works with LR2021)
- ESP32 GPIO: native interrupts with FreeRTOS task notification

3.4. **Measure ESP32-C3 RX blind window** — If ESP32 GPIO interrupt +
FreeRTOS task notification is used, response time may be 5-20µs (RTOS
scheduling latency). FIFO read time depends on SPI mode (polling vs DMA).

3.5. **Power measurement** — Measure TX current at 12 dBm. Critical for
solar/supercap power budget (ADR-006). Expected: ~30-40 mA TX burst.

3.6. **Deliverables**
- `firmware/esp32-c3-flrc/flrc_tx.cpp` — production TX
- `firmware/esp32-c3-flrc/flrc_rx.cpp` — production RX
- Throughput + power measurements
- Comparison table: RP2040 vs ESP32-C3

---

## PHASE 4 — RANGE TEST
**Priority: MEDIUM-HIGH (validates link budget assumptions)**
**Estimated effort: 1 day**
**Hardware needed: 2x boards (RP2040 or ESP32-C3) + antennas**

### Rationale
All tests so far are bench distance (centimeters). The application needs
km-scale range. Need to validate:
- Does FLRC 2600 kbps actually work at distance? (Higher data rate = shorter
  range for same power)
- At what distance does packet loss start?
- Is the link budget from mesh-stack/ROADMAP.md accurate?

### Steps

4.1. **Outdoor line-of-sight test** — 10m, 50m, 100m, 500m with wire dipoles.
Log: distance, packet count, loss %, RSSI (if available).

4.2. **Throughput vs distance curve** — Plot throughput at each distance.
Expect: flat until sensitivity threshold, then cliff-edge dropout.

4.3. **Frequency band comparison** — Test 868 MHz (Sub-GHz, longer range)
vs 2.4 GHz (FLRC max throughput). Different propagation characteristics.

4.4. **Decision gate:**
- If 2600 kbps FLRC works at >100m → use FLRC for mesh
- If range <50m at 2600 kbps → consider adaptive: FLRC short-range, LoRa
  long-range fallback (ADR-007)

---

## PHASE 5 — APPLICATION LAYER
**Priority: MEDIUM (builds on proven link)**
**Estimated effort: 5-10 days**
**Hardware needed: ESP32-C3 + GPS module + sensors**

### Rationale
The RF link works. Now build the actual application on top of it.

### Steps

5.1. **Telemetry protocol** — Implement 24-byte binary telemetry format
(ADR-008) with CRC-16. Fields: lat, lon, alt, voltage, temp, seq, flags.

5.2. **GPS integration** — Add GPS parsing (NMEA), position encoding into
telemetry packets. Test GPS lock + TX simultaneously.

5.3. **Mesh protocol** — TDMA slot assignment, adaptive data rate (FLRC vs
LoRa fallback), store-and-forward relay. Start with 2-node mesh, expand.

5.4. **Ground station software** — Receive telemetry, decode, display on
map. Web dashboard or simple serial output.

5.5. **Flight test** — Pico balloon launch with telemetry beacon. Track
via ground station or relay mesh.

---

## PHASE 6 — FPGA (LAST RESORT)
**Priority: LOW (only if all else fails AND >2000 kbps is truly needed)**
**Estimated effort: 2-3 weeks**
**Hardware needed: iCE40 UP5K dev board + level shifters**

### Rationale
Only justified if:
- Phase 0 (ESP32 DMA) fails
- Phase 1 (dual-core) insufficient
- Phase 2 (PIO rework) fails
- AND the application genuinely needs >2000 kbps sustained

### Steps

6.1. Select FPGA: iCE40 UP5K (28-QFN, ~$5, open-source toolchain with
Yosys/nextpnr)

6.2. Implement SPI master in Verilog matching LR2021 timing (from Phase 2
logic analyzer data)

6.3. Interface FPGA to LR2021 (3.3V compatible, no level shifters needed)

6.4. Test TX and RX throughput

### Expected Result
~2400-2540 kbps. The FPGA generates SPI timing in silicon — the LR2021
timing incompatibilities that break every software approach don't apply.

---

## DECISION TREE

```
START
  │
  ▼
Phase 0: ESP32-C3 DMA Test
  │
  ├── DMA WORKS ──► Phase 3 (port to flight) ──► Phase 4 (range) ──► Phase 5 (app)
  │
  └── DMA FAILS
       │
       ▼
  Phase 1: RP2040 Dual-Core RX
       │
       ├── BLIND WINDOW <100µs ──► Phase 3 + Phase 4 + Phase 5
       │
       └── STILL >300µs
            │
            ▼
       Phase 2: Logic Analyzer + PIO
            │
            ├── PIO WORKS ──► Combine with dual-core ──► Phase 3 + 4 + 5
            │
            └── PIO FAILS
                 │
                 ▼
            Accept ~1400 kbps ceiling
            Phase 3 (port to ESP32 with polling SPI)
            Phase 4 + 5 (app layer — 1400 kbps is plenty)
            │
            └── IF app truly needs >2000 kbps AND all above failed:
                 │
                 ▼
               Phase 6: FPGA
```

---

## WHAT WE LEARNED (COMPLETE)

### Technical Facts

1. **LR2021 SPI timing is picky.** Only Arduino per-byte `transfer()` works.
   Pico SDK batch, DMA, direct register, and PIO all fail. The chip requires
   specific inter-byte timing/CS patterns that only Arduino's transaction
   layer provides on RP2040.

2. **RP2040 SPI clock is capped at ~12 MHz actual** regardless of request
   (prescaler limitation at 125 MHz system clock). "16 MHz" and "20 MHz"
   firmware both run at 12 MHz.

3. **RP2040 PIO + USB CDC are fundamentally incompatible** when both active.
   DMA_IRQ_0 starves the TinyUSB interrupt. PIO works but kills USB output.

4. **The LR2021 DIO9 IRQ pin fires on ALL enabled IRQ bits**, not just
   TX_DONE/RX_DONE. IRQ status 0x000A080A = TX_FIFO + TX_TIMESTAMP + PA_OCP
   + TX_DONE all fire at once.

5. **BUSY pin is the ground truth** for TX completion. Goes LOW when chip
   returns to STDBY_RC mode.

6. **USB CDC requires DTR assertion** on RP2040: `s.dtr = True` via pyserial
   or `delay(2000)` in firmware for TinyUSB enumeration. `Serial.flush()`
   blocks CDC — never call in hot paths.

7. **1200 baud touch reboots RP2040 into BOOTSEL** reliably. But capture
   scripts that open the serial port BLOCK the 1200 baud touch.

### Process Lessons

8. **We optimized the wrong side.** ALL effort went to TX. The real bottleneck
   was RX (blind window). TX optimization yielded 0.7% gain; RX optimization
   is untested and could yield 40%+ gain.

9. **The platform switch was premature.** We abandoned ESP32-C3 for RP2040
   before testing ESP32 native DMA. The RP2040's advantages (PIO, DMA,
   dual-core) never materialized because of LR2021 incompatibility.

10. **35 commits and 25 documents for TX optimization that yielded 0.7%.**
    The PIO+DMA investigation was expensive in time and tokens. Earlier
    bottleneck analysis (the coupling problem) would have shown that TX
    SPI speed doesn't matter when air time dominates.

### What We'd Do Differently

11. **Profile before optimizing.** Measure where time is actually spent
    before writing 8 firmware variants. The per-packet breakdown table
    would have immediately shown that air time (54%) dominates.

12. **Test RX first.** The RX blind window is the coupling constraint.
    Optimizing TX without fixing RX just moves the bottleneck.

13. **Test ESP32 DMA before switching platforms.** The RP2040 platform
    switch was justified by expected hardware gains that never materialized.

---

## APPENDIX: FIRMWARE INVENTORY (FINAL STATE)

| File | Platform | Status | Throughput | Purpose |
|------|----------|--------|------------|---------|
| flrc_raw_tx.cpp | RP2040 | ✅ CANONICAL | 1367 kbps | v4 baseline TX |
| flrc_raw_rx.cpp | RP2040 | ✅ CANONICAL | 0% loss | RX |
| flrc_raw_tx_20mhz.cpp | RP2040 | ✅ Tested | 1377 kbps | 20MHz TX variant |
| flrc_raw_tx_pipe.cpp | RP2040 | ⚠️ Bug | 1389 kbps | Pipelining (seq bug) |
| flrc_pio_tx.cpp | RP2040 | ❌ Abandoned | 1377 kbps | PIO v1 (kills CDC) |
| flrc_pio_tx_v2.cpp | RP2040 | ❌ Abandoned | Unknown | PIO v2 (CDC dies) |
| flrc_pio_tx_v3.cpp | RP2040 | ❌ Abandoned | Unknown | PIO v3 (partial CDC) |
| flrc_dma_tx.cpp | RP2040 | ❌ Failed | N/A | DMA (init fails) |
| flrc_raw_tx_batch.cpp | RP2040 | ❌ Failed | N/A | Batch (fake TX_DONE) |
| flrc_raw_tx_sweep.cpp | RP2040 | ❌ Failed | N/A | Runtime sweep (kills radio) |
| pio_lr2021_rx.cpp + .pio | RP2040 | ⏸ UNTESTED | — | PIO RX (never flashed) |
| fast_rx.cpp | ESP32-C3 | ⏸ EXISTS | — | RadioLib RX (profiler) |
| profile_rx.cpp | ESP32-C3 | ⏸ EXISTS | — | RX pipeline profiler |
| spi_loopback.cpp | ESP32-C3 | ⏸ EXISTS | — | SPI self-test |
| fifo_tx.cpp | ESP32-C3 | ⏸ EXISTS | — | RadioLib TX |

### Files That Need Writing

| File | Platform | Phase | Purpose |
|------|----------|-------|---------|
| flrc_tx_raw_espidf.cpp | ESP32-C3 | Phase 0/3 | Raw SPI TX (no RadioLib) |
| flrc_rx_raw_espidf.cpp | ESP32-C3 | Phase 0/3 | Raw SPI RX (no RadioLib) |
| flrc_raw_rx_dualcore.cpp | RP2040 | Phase 1 | Dual-core RX pipelining |

---

*This plan is a living document. Update after each phase with actual results.*
