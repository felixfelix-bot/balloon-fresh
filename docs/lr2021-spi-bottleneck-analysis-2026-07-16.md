# LR2021 SPI Bottleneck Analysis + Path Forward (2026-07-16)

## EXECUTIVE SUMMARY

The RP2040 platform switch was justified — the chip CAN accelerate SPI
beyond ESP32-C3 capabilities. However, we have NOT used any of this
hardware acceleration. Every PIO, DMA, and batch SPI approach failed.
The root cause is unknown because we never measured actual SPI signals.

The next diagnostic step is a logic analyzer capture — NOT more firmware
guessing. This document explains why, and what the paths forward are.

---

## 1. WHY WE SWITCHED FROM ESP32-C3 TO RP2040

The ESP32-C3 RX pipeline couldn't keep up at high packet rates. When
packets arrived faster than the ESP32 could read the FIFO, clear IRQ,
and re-arm RX, packets were lost. The RX "blind window" was the
bottleneck.

The RP2040 was supposed to fix this with three hardware features:
1. **PIO state machines** — hardware-driven SPI with cycle-accurate timing
2. **DMA** — autonomous FIFO reads, zero CPU overhead
3. **Dual-core** — pipeline SPI operations with radio processing

These were expected to shrink the RX blind window from ~572µs to ~60µs.

## 2. CURRENT REALITY: ZERO HARDWARE ACCELERATION USED

Every optimization attempt (TX-side) failed on real hardware:

| Approach | Result | Root Cause (Guessed) |
|----------|--------|----------------------|
| Pico SDK batch transfer | Fake TX_DONE (spin=0), 0 RX | "SPI timing incompatible" |
| DMA via spi0_hw->dr | Radio init fails (Status=0x00) | "Bypasses transaction protocol" |
| Direct HW register writes | 7034 kbps fake, 0 RX | "Same as DMA" |
| Runtime SPI clock change | Radio never re-syncs | "spi_deinit tears down peripheral" |
| PIO+DMA v1/v2/v3 | TX loop hangs, CDC death | "DMA IRQ never fires" |

**Critical admission:** We do NOT know the actual root cause of any of
these failures. All explanations are hypotheses based on observed
symptoms, not measured SPI signals. We never used a logic analyzer.

## 3. THE REAL BOTTLENECK: RX BLIND WINDOW

### TX Side (solved, physics-bound)
- RF air time: 803µs (54% of per-packet time) — cannot reduce
- Arduino SPI: 535µs (36%) — only working path
- Total: 1492µs/packet = 1377 kbps

### RX Side (the real problem)
For every received packet, the radio is NOT listening for ~572µs:
- Read IRQ status: ~12µs (6 SPI bytes)
- Read RX FIFO: ~514µs (257 SPI bytes: 2 status + 255 data)
- Clear IRQ: ~12µs (6 bytes)
- Re-arm RX: ~4µs (2 bytes)
- rfWaitBusy overhead: ~30µs
- **Total blind window: ~572µs**

During this window, any incoming packet is lost. Currently 0% loss
because TX sends every 1492µs, leaving 920µs of RX listening time.

### The Coupling Problem
TX and RX throughput are linked. If TX gets faster (shorter inter-
packet gap), the RX blind window doesn't shrink. Eventually TX fires
faster than RX can re-arm, and packets start dropping.

This is the SAME problem the ESP32 had. The RP2040 was supposed to
fix it via hardware acceleration. It didn't because acceleration failed.

## 4. WHY DOES THE LR2021 REJECT NON-ARDUINO SPI?

This is the central unanswered question of the entire optimization
effort. Our hypotheses (in order of likelihood):

### Hypothesis A: Inter-Byte Gap Timing (MOST LIKELY)
Arduino `transfer(byte)` adds overhead between each byte: function
call, beginTransaction check, register write, TX-complete wait, RX
FIFO read. This creates natural ~100-200ns gaps between bytes.

Batch/DMA modes pump bytes back-to-back with no gap. The LR2021 may
require inter-byte gaps to process each byte in its internal state
machine. If the chip's SPI peripheral can't keep up with back-to-back
bytes, it drops data or corrupts commands.

### Hypothesis B: CS Assertion Pattern
LR2021 requires "one command per CS assertion" — we proved this when
combined CS assertions broke TX_DONE. Arduino per-byte transfer may
be accidentally creating the right CS pattern because beginTransaction/
endTransaction wraps the entire multi-byte command.

DMA might assert CS once and pump data, or toggle CS at wrong times.

### Hypothesis C: Status Byte Polling
Some SPI radios require reading a status byte after each data byte
(the classic "write byte, read status, check BUSY/WIP" pattern from
Flash chips). Arduino transfer() returns a byte each call, which the
calling code ignores. But the timing effect — write, wait, read,
wait — might match what the LR2021 expects.

DMA pumps data one direction only (TX), skipping the read phase.

### Hypothesis D: SPI Mode/Clock Phase Issue
RP2040 SPI peripheral might configure CPHA/CPOL differently between
Arduino SPIClass and direct register/DMA access. If Arduino uses
MODE0 with specific sampling edge, and DMA defaults to a different
edge, the chip would see garbage.

### THE PROBLEM WITH ALL THESE HYPOTHESES
They're all guesses. We have ZERO measured data. Every "root cause"
in our documentation is inferred from behavior, not verified with
an oscilloscope or logic analyzer.

## 5. THE MISSING DIAGNOSTIC: LOGIC ANALYZER

A $10-20 logic analyzer (Saleae clone, DSLogic, or any 8-channel
24MHz+ USB analyzer) would answer all these questions in one afternoon:

### What to Capture
1. **Working transaction:** Arduino `transfer()` CS, SCK, MOSI, MISO
   during a successful TX_DONE packet
2. **Failing transaction:** DMA or batch transfer on same pins
3. **Compare:** inter-byte gaps, CS timing, clock phase, MISO behavior

### What We'd Learn
- Exact inter-byte gap in working mode (confirm/deny Hypothesis A)
- CS pattern during multi-byte commands (confirm/deny Hypothesis B)
- Whether MISO returns data between bytes (confirm/deny Hypothesis C)
- CPHA/CPOL on both paths (confirm/deny Hypothesis D)

### Cost vs Benefit
- Cost: $20, 1 afternoon
- Benefit: Definitive root cause → targeted fix → potential 2000+ kbps
- Alternative: Continue guessing, waste more sessions

## 6. PATHS FORWARD (IN PRIORITY ORDER)

### Path 1: Logic Analyzer Diagnosis (RECOMMENDED — FIRST)
- Buy/use any 8-channel 24MHz+ logic analyzer
- Capture working vs failing SPI transactions
- Identify exact timing/protocol difference
- Cost: $20 + 1 afternoon
- Expected outcome: Targeted fix for PIO/DMA firmware

### Path 2: Fix RP2040 PIO/DMA Based on Findings (DEPENDS ON PATH 1)
- If inter-byte gap: program PIO to insert gaps
- If CS pattern: program PIO CS control per command
- If status polling: add MISO read between TX bytes
- If clock phase: fix DMA channel config
- Cost: 1-3 days development
- Expected outcome: 2000+ kbps TX, ~60µs RX blind window

### Path 3: Dual-Core RX Pipelining (INDEPENDENT — CAN DO NOW)
- Core 0: IRQ detection + radio state management
- Core 1: FIFO read + packet processing
- Pipeline: read packet N's FIFO while listening for packet N+1
- Cost: 2-4 days development
- Expected outcome: RX blind window drops from 572µs to ~100µs
- Enables TX rates up to ~2000 kbps without RX loss
- DOES NOT require fixing the SPI acceleration problem

### Path 4: FPGA SPI Controller (FALLBACK IF PATH 2 FAILS)
If logic analyzer shows the LR2021 has fundamental SPI requirements
that RP2040 PIO cannot meet, a small FPGA can replicate ANY timing:

**Hardware options:**
- Lattice iCE40 Ultra (iCE40UP5K): ~$5-8, QFN-48, ~0.5g
- Gowin GW1N (GW1N-1): ~$3-5, QFN-48, ~0.4g
- Lattice MachXO2-256: ~$3, TQFP-48, ~0.8g

**Architecture:**
```
RP2040 (protocol/app) ←UART/SPI→ FPGA (LR2021 SPI controller)
                                        ↓
                               LR2021 (radio)
```

FPGA implements a Verilog SPI state machine that:
- Replicates exact Arduino transfer() timing in hardware
- Runs at true 20MHz (RP2040 caps at 12MHz due to prescaler)
- Zero inter-byte overhead, zero jitter
- Dual-buffer pipeline: TX FIFO write overlapped with RF air time
- Instant RX FIFO read (dedicated hardware, no CPU)

**Expected performance:**
- TX: max(803µs air, ~107µs SPI at 20MHz) = 803µs = ~2540 kbps
- RX blind window: ~30µs (just IRQ read + clear + re-arm)
- Nearly 2× current throughput

**Cost:**
- Development: 2-4 weeks (Verilog + PCB design + bring-up)
- Hardware: ~$10 per board (FPGA + passives)
- Weight: +0.5g (QFN FPGA) — acceptable for balloon
- Power: +20-50mA — needs power budget review

**Risk:** If the LR2021 SPI failure is NOT a timing issue (e.g., it's
a protocol/FIFO bug), the FPGA hits the same wall. Logic analyzer
confirms this BEFORE investing in FPGA development.

### Path 5: Accept 1377 kbps (PRAGMATIC FALLBACK)
- 1377 kbps is 50-100× faster than typical LoRa
- Sufficient for telemetry, mesh relay, basic internet transport
- Move to tracker/mesh integration
- Revisit throughput only if application demands more

## 7. SUMMARY TABLE

| Path | Cost | Time | Expected Throughput | Risk |
|------|------|------|---------------------|------|
| Logic analyzer | $20 | 1 day | Diagnostic only | None |
| Fix PIO/DMA | $0 | 1-3 days | 2000+ kbps | Medium |
| Dual-core RX | $0 | 2-4 days | 1377 TX, better RX | Low |
| FPGA controller | $10 | 2-4 weeks | ~2540 kbps | High |
| Accept current | $0 | 0 | 1377 kbps | None |

## 8. RECOMMENDATION

1. **Logic analyzer FIRST** — it's cheap, fast, and answers the core
   question we've been guessing at for 4 sessions
2. **Dual-core RX IN PARALLEL** — independent of SPI fix, shrinks
   blind window, enables higher TX rates
3. **FPGA ONLY IF** logic analyzer confirms RP2040 can't match LR2021
   timing requirements

The logic analyzer is the single highest-value action we can take.
Every hour spent on more firmware guessing is an hour wasted when
a $20 tool would give us the answer.
