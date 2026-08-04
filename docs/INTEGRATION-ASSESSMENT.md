# Integration Assessment — balloon-speed-tests

**Date:** 2026-08-05
**Assessor:** balloon-hermes orchestrator (delegated)
**Track scope:** LR2021 FLRC throughput benchmarking and TX optimization

---

## Track Scope and Components

Deliver **maximum sustained throughput benchmarks** for the LR2021 FLRC radio
and characterize the TX optimization path from baseline to peak performance.
Produces the throughput data that informs mesh capacity planning.

**Components:**
- `firmware/rp2040/src/flrc_raw_tx.cpp` — RP2040 raw SPI TX (PROVEN: 1377 kbps)
- `firmware/esp32-c3-flrc/` — ESP32-C3 TX+RX (PROVEN WORKING)
- `firmware/esp32_raw_tx.cpp` — ESP32 continuous TX for throughput benchmarking
- `firmware/esp32_batched_tx.cpp` — batched SPI TX (clearIrq+FIFO+setTx in one burst)
- `scripts/goodput_measure.py` — goodput measurement for LR2021 throughput
- `docs/PLAN-esp32-vs-rp2040-benchmark.md` — benchmark comparison plan
- `docs/SPEED-P0P2P3-HW-VERIFICATION-PLAN.md` — 4 speed-record branch mapping
- Sigrok SPI decode pipeline (capture-byte, decode-tx, transaction grouping)

## What Works (Proven, Tested)

- ✅ **Raw SPI 2-byte opcode protocol proven on both platforms:**
  - RP2040 TX: 1377 kbps verified end-to-end throughput
  - 0% packet loss at 1000/1000 packets
  - Full dual-band support (2.4 GHz + sub-GHz 915 MHz)
- ✅ **4 speed-record branches mapped and verified:**
  - SPEED-P0 (`44ad093`): packet params fix
  - SPEED-P2 (`67c0552`): RadioLib bypass
  - SPEED-P3 (`45b57ab`): FLRC_MAX + sweep params
  - MERGE-FIX (`dc9d2e2`): P3 + shaping fix (PRIMARY TARGET)
- ✅ **Batched SPI TX** — clearIrq+FIFO+setTx in one burst for reduced overhead
- ✅ **Goodput measurement script** — ready for automated benchmarking
- ✅ **Sigrok SPI decode pipeline** — capture, decode, transaction grouping
- ✅ **ESP32 capture targets** — Makefile targets for ESP32-C3 LR2021 capture/decode
- ✅ **Discovery sync adopted** — P1B.1-FIX SPI TX debugging techniques (SET_FLRC_PACKET_PARAMS already present)

## What Doesn't Work (Blockers)

- ❌ **ESP32-C3 vs RP2040 benchmark not yet executed** — plan exists but no
     head-to-head throughput comparison data collected
- ❌ **Sustained throughput under real mesh conditions untested** — benchmarks
     are point-to-point TX, not through FIPS mesh stack with fragmentation
- ❌ **No goodput data at range** — all measurements are bench distance. Need
     range-tests track data to characterize throughput vs distance tradeoff
- ⚠️ **Continuous TX firmware may cause thermal issues** at +22 dBm with PA
     enabled — not yet characterized for sustained operation

## C3 Portability Assessment

**✅ EXCELLENT — proven on ESP32-C3 already:**

- ESP32-C3 firmware (`esp32-c3-flrc/`) uses identical raw SPI 2-byte opcode protocol
- Both TX and RX proven working on ESP32-C3 hardware
- Batched SPI TX technique is platform-agnostic (SPI burst optimization)
- Goodput measurement script works with any serial-connected platform
- No RP2040-specific dependencies in the benchmark methodology

**Note:** ESP32-C3 clock is 160 MHz vs RP2040's 133 MHz — may actually achieve
higher SPI throughput. Benchmark comparison will quantify this.

## What's Next

1. **Execute SPEED-P0P2P3 verification plan** — benchmark all 4 branches against
   MERGE-FIX to identify the optimal TX configuration
2. **Run ESP32-C3 vs RP2040 head-to-head** — the core deliverable
3. **Measure sustained throughput** — 10+ minute continuous TX with goodput logging
4. **Characterize thermal behavior** at +22 dBm sustained operation
5. **Correlate with range-tests** — throughput vs distance using outdoor data
6. **Feed results into mesh capacity planning** — throughput informs MultiWAN sizing
