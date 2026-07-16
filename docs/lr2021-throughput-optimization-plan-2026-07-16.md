# LR2021 Throughput Optimization — Comprehensive Plan (2026-07-16)

## Current State
- TX: 1377 kbps, 1000/1000 TX_DONE, Arduino per-byte SPI only
- RX: 0% packet loss, 572µs blind window per packet
- 5 SPI acceleration approaches tried, ALL failed, root cause UNKNOWN
- Zero hardware acceleration used despite RP2040 platform switch

## Phases

### PHASE 0: Logic Analyzer Diagnosis (GATE — must complete before Phase 2)
**Goal:** Determine exactly WHY LR2021 rejects non-Arduino SPI
**Cost:** $20 hardware + 1 afternoon
**Risk:** None (diagnostic only)

Steps:
1. Acquire 8-channel 24MHz+ logic analyzer (Saleae clone, DSLogic, or similar)
2. Connect to SPI bus: CS(GP5), SCK(GP2), MOSI(GP3), MISO(GP4), BUSY(GP6), IRQ(GP7)
3. Flash working firmware (rp2040-flrc-tx-raw) to TX board
4. Capture: Arduino transfer() during successful TX packet (CS→SCK→MOSI→MISO→BUSY)
5. Flash failing firmware (rp2040-pio-tx-v3 or rp2040-dma-tx)
6. Capture: DMA/PIO SPI transaction for comparison
7. Analyze in Sigrok/Pulseview:
   - Inter-byte gap timing (Arduino vs DMA)
   - CS assertion pattern (per-command vs continuous)
   - CPHA/CPOL on both paths
   - MISO response bytes between MOSI writes
   - BUSY pin timing relative to CS/SCK
8. Document findings in docs/lr2021-logic-analyzer-results.md
9. Decision tree:
   - If inter-byte gap → PIO firmware fix (Phase 2A)
   - If CS pattern → PIO firmware fix (Phase 2B)
   - If status polling → PIO firmware fix (Phase 2C)
   - If clock phase → DMA config fix (Phase 2D)
   - If fundamental protocol issue → FPGA path (Phase 4)

**Deliverable:** docs/lr2021-spi-timing-capture-2026-07-XX.md with measured waveforms
**Gate:** Cannot proceed to Phase 2 until root cause is identified

---

### PHASE 1: Dual-Core RX Pipelining (INDEPENDENT — can start now, no dependencies)
**Goal:** Shrink RX blind window from 572µs to ~100µs
**Cost:** $0 hardware
**Risk:** Low (additive — doesn't break working TX)
**Expected gain:** Enable TX rates up to ~2000 kbps without RX packet loss

Steps:
1. Create firmware/rp2040/src/flrc_dual_core_rx.cpp
2. Architecture:
   - Core 0: IRQ pin polling, radio state machine (SET_RX, CLEAR_IRQ), packet counting
   - Core 1: FIFO read + sequence extraction + processing
   - Inter-core FIFO: ring buffer (Core 0 signals "packet ready", Core 1 reads)
3. Core 0 hot loop (minimal — just re-arm radio ASAP):
   ```
   while (running):
     if IRQ pin HIGH:
       signal Core 1: "read FIFO now"
       wait for Core 1: "done reading"
       CLEAR_IRQ
       SET_RX  ← radio listening again, ~60µs blind
   ```
4. Core 1 handler:
   ```
   on signal:
     READ_RX_FIFO(buf, 255)  ← 514µs, but radio already re-armed by Core 0
     extract seq
     update stats
   ```
5. Key insight: Core 0 re-arms RX BEFORE Core 1 finishes reading FIFO
   - But LR2021 FIFO holds last packet until next SET_RX overwrites
   - Need to verify: does CLEAR_IRQ + SET_RX preserve FIFO data?
   - If not: read FIFO first, THEN clear+re-arm (same as current, no gain)
   - Alternative: dual-buffer in radio — check if LR2021 supports packet queueing
6. Test: flash dual-core RX + existing TX, measure packet loss at 1377 kbps
7. If 0% loss: increase TX rate (shorter inter-packet delay), find new drop threshold
8. Build env: rp2040-dualcore-rx

**Deliverable:** Working dual-core RX firmware, measured blind window, throughput-vs-loss curve
**Parallel with:** Phase 0

---

### PHASE 2: Fix PIO/DMA SPI Based on Logic Analyzer Findings (DEPENDS ON PHASE 0)
**Goal:** Working hardware-accelerated SPI for LR2021
**Cost:** $0 hardware
**Risk:** Medium (depends on Phase 0 findings)
**Expected gain:** TX 2000+ kbps, RX blind window ~30µs

#### Phase 2A: Inter-Byte Gap Fix (if logic analyzer shows gap is the issue)
1. Modify PIO program to insert N clock cycles between bytes
2. PIO state machine: shift out byte → wait N cycles → shift next byte
3. Tune N from logic analyzer measurement (probably 2-10 SCK cycles)
4. Test: flash PIO TX, verify TX_DONE=1000/1000, measure throughput

#### Phase 2B: CS Pattern Fix (if logic analyzer shows CS timing issue)
1. Modify PIO to assert/deassert CS per-command, not per-session
2. PIO: CS LOW → send opcode → CS HIGH → wait BUSY → CS LOW → send data → CS HIGH
3. Match exact CS timing from Arduino capture
4. Test: flash PIO TX, verify real TX_DONE

#### Phase 2C: Status Byte Polling Fix (if LR2021 requires read-between-writes)
1. Modify PIO/DMA for bidirectional: write byte → read status → check → next byte
2. This is slower than pure TX but may be what LR2021 requires
3. Expected: ~250µs per packet (vs 535µs Arduino) — still 2× faster
4. Test: flash, verify TX_DONE

#### Phase 2D: DMA Clock Phase Fix (if CPHA/CPOL mismatch)
1. Check RP2040 SPI SSPCR0 register: CPHA/CPOL bits
2. Compare Arduino SPISettings(MODE0) vs DMA default
3. Fix DMA channel config to match MODE0 exactly
4. Test: flash DMA TX, verify TX_DONE

**Deliverable:** Working hardware-accelerated SPI firmware, measured throughput
**Gate:** Phase 0 logic analyzer results must identify the specific issue

---

### PHASE 3: Full Accelerated TX+RX Pipeline (DEPENDS ON PHASE 2)
**Goal:** Combine accelerated SPI with dual-core RX for maximum throughput
**Cost:** $0 hardware
**Risk:** Medium
**Expected gain:** TX 2000+ kbps, RX ~30µs blind window, near-theoretical throughput

Steps:
1. Take working accelerated SPI from Phase 2
2. Apply to BOTH TX and RX hot paths
3. Combine with dual-core architecture from Phase 1
4. Measure bidirectional throughput
5. Test at increasing TX rates until RX drops packets
6. Document the throughput-vs-loss tradeoff curve

**Deliverable:** Final optimized firmware, throughput report

---

### PHASE 4: FPGA SPI Controller (FALLBACK — only if Phase 2 fails)
**Trigger:** Logic analyzer shows LR2021 has fundamental SPI requirements RP2040 cannot meet
**Cost:** ~$10/board + 2-4 weeks development
**Risk:** High (PCB design, Verilog, bring-up)

#### 4.1: FPGA Selection
- Primary: Lattice iCE40UP5K (open-source toolchain: yosys+nextpnr)
- Alternative: Gowin GW1N-1 (Gowin EDA, free for small chips)
- Package: QFN-48 (~6×6mm, ~0.5g)
- LUTs needed: <1000 (simple SPI controller)

#### 4.2: PCB Design
- RP2040 ↔ FPGA: SPI or UART (FPGA is SPI master to LR2021)
- FPGA ↔ LR2021: CS, SCK, MOSI, MISO, BUSY, IRQ
- Power: 3.3V from RP2040 board
- Footprint: must fit on existing wing/carrier board
- Design in KiCad, fab via JLCPCB ($2 for 5 boards)

#### 4.3: Verilog SPI Controller
```verilog
// Simplified concept — actual implementation TBD
module lr2021_spi_master(
    input clk,           // 50MHz FPGA clock
    input [7:0] cmd_data,
    input cmd_valid,
    output cmd_ready,
    output reg cs_n,
    output reg sck,
    output reg mosi,
    input miso,
    input busy,
    // Exact timing from logic analyzer capture
);
  // State machine replicating Arduino transfer() timing
  // Inter-byte gaps, CS pattern, all from Phase 0 measurements
endmodule
```

#### 4.4: Bring-up + Testing
1. Flash FPGA bitstream
2. RP2040 sends commands via UART → FPGA translates to SPI → LR2021
3. Verify: TX_DONE=1000/1000 at 20MHz true SPI clock
4. Measure: throughput, compare to RP2040 baseline
5. Expected: ~2540 kbps (RF air time limited)

**Deliverable:** Working FPGA-based SPI controller PCB, 2540 kbps throughput

---

### PHASE 5: Accept Current Performance + Move to Integration (ALWAYS AVAILABLE)
**Goal:** Use 1377 kbps as-is, focus on tracker/mesh application
**Cost:** $0
**Risk:** None
**Trigger:** If all optimization phases stall or application doesn't need more

Steps:
1. Lock flrc_tx_raw.cpp + flrc_rx_raw.cpp as canonical firmware
2. Begin tracker firmware integration (GPS, BMP280, telemetry)
3. Begin mesh-stack protocol design
4. Revisit throughput only if application demands >1377 kbps

---

## DEPENDENCY GRAPH

```
Phase 0 (Logic Analyzer)
   │
   ├─→ Phase 2 (Fix PIO/DMA) ──→ Phase 3 (Full Pipeline)
   │         │
   │         └─→ FAIL? ──→ Phase 4 (FPGA)
   │
   └─→ Phase 0 shows fundamental issue ──→ Phase 4 (FPGA)

Phase 1 (Dual-Core RX) ← INDEPENDENT, runs in parallel

Phase 5 (Accept + Integrate) ← ALWAYS AVAILABLE
```

## PRIORITY ORDER

1. **Phase 0** (logic analyzer) — highest ROI, unblocks everything
2. **Phase 1** (dual-core RX) — independent, no-risk improvement
3. **Phase 2** (fix PIO/DMA) — depends on Phase 0, biggest potential gain
4. **Phase 3** (full pipeline) — depends on Phase 2
5. **Phase 4** (FPGA) — last resort, high effort
6. **Phase 5** (accept + integrate) — pragmatic fallback at any time

## TIMELINE ESTIMATE

| Phase | Duration | Parallel? |
|-------|----------|-----------|
| Phase 0 | 1 day | No (blocks Phase 2) |
| Phase 1 | 2-4 days | YES (parallel with Phase 0) |
| Phase 2 | 1-3 days | After Phase 0 |
| Phase 3 | 1-2 days | After Phase 2 |
| Phase 4 | 2-4 weeks | Only if Phase 2 fails |
| Phase 5 | Ongoing | Anytime |

## SUCCESS CRITERIA

| Milestone | Metric | Target |
|-----------|--------|--------|
| Phase 0 complete | Root cause identified | Named hypothesis confirmed/denied |
| Phase 1 complete | RX blind window | <150µs (down from 572µs) |
| Phase 2 complete | TX throughput | >1800 kbps |
| Phase 3 complete | Bidirectional throughput | >1800 kbps TX, <5% RX loss |
| Phase 4 complete | TX throughput | >2400 kbps |
| Phase 5 complete | Application demo | Telemetry over FLRC link |

## RISK MITIGATION

- Phase 1 is ZERO RISK — pure additive improvement, doesn't touch working TX
- Phase 0 is ZERO RISK — diagnostic only
- Phase 2 is MEDIUM RISK — but Phase 0 findings guide the fix precisely
- Phase 4 is HIGH RISK — 2-4 weeks, PCB fab, unknown chip behavior
- At any point, Phase 5 provides a safe exit with working 1377 kbps link
