# ESP32-C3 vs RP2040 LR2021 SPI Throughput Benchmark Plan

**Branch:** `speed-sustained-sweep`
**Date:** 2026-07-30
**Status:** Ready to execute (RP2040 baseline captured; ESP32 capture pending)
**Companion docs:**
- `docs/PLAN-esp32-speed-test-2026-07-27.md` — radio-level goodput plan (1377 kbps target)
- `docs/lr2021-bottleneck-analysis-2026-07-29.md` — SPI clock / FIFO / overhead audit
- `docs/lr2021-throughput-fix-plan-2026-07-29.md` — phased fix roadmap
- `docs/esp32-vs-rp2040-rx-analysis-2026-07-27.md` — software root-cause comparison

---

## Objective

Decide which MCU platform hosts the LR2021 for sustained FLRC throughput, using
**logic-analyzer (LA) measured** SPI bus data — not end-to-end goodput alone. The
question is concrete: *does the ESP32-C3 sustain a faster SPI bus + tighter
inter-packet timing than the RP2040, by enough to justify resoldering the
LR2021 + F33 PA onto an ESP32 board?*

The radio-level goodput plan (`PLAN-esp32-speed-test-2026-07-27.md`) answers
"how many bytes get through the air"; this plan answers "why" by measuring the
SPI bus behaviour that produces the goodput.

---

## Hardware Under Test

| Board | MCU | SPI peripheral | LR2021 module | Notes |
|-------|-----|----------------|---------------|-------|
| TX/RX  | RP2040 Zero | HW SPI (Arduino-Pico core) | NiceRF LoRa2021 | Baseline; `firmware/rp2040` |
| ESP32 board | ESP32-C3 Mini V1 | ESP32 GSPI | NiceRF LoRa2021 | `firmware/esp32-c3-flrc` |

Both boards drive the same LR2021 part, so the radio is a fixed variable; only
the MCU SPI path differs. Logic analyzer (fx2lafw, 24 MHz sample rate) is shared
hardware, wired identically for both (see channel map below).

---

## Metrics to Capture (per MCU)

Captured for **each** payload size in the test matrix, repeated across 2 runs.

| # | Metric | Unit | How measured (sigrok) |
|---|--------|------|-----------------------|
| 1 | **Actual SPI clock** | MHz | Count SCK edges inside a CS-low window ÷ CS-low duration. Cross-check with PulseView measurement cursors on a single packet. |
| 2 | **Effective throughput** | kbps | payload_bytes ÷ total cycle time (CS-low → next CS-low), per-packet average over the capture window |
| 3 | **Packet loss** | % | ≥1000-packet goodput run; 100 × (1 − rx_count/tx_count). Requires 2 boards TX→RX. |
| 4 | **Per-packet SPI time** | µs | CS-low duration of the main `WRITE_FIFO`/TX transaction (D0 falling→rising edge). |
| 5 | **Inter-packet gap** | µs | Time from CS rising (end of one TX packet cycle) to CS falling (start of next). |
| 6 | **Bus duty cycle** | % | 100 × Σ(CS-low time) ÷ capture_duration. Bus busy = CS low OR BUSY high during TX. |
| 7 | **RSSI at receiver** | dBm | Reported by RX board over serial during the ≥1000-packet run (if two boards). |
| 8 | **Per-packet latency** | µs | TX_CS_falling → RX_CS_falling (two-board, same LA, two probe sets). *Optional / best-effort.* |

> **Channel map (identical for both MCUs):** D0=CS(NSS), D1=SCK, D2=MOSI, D3=MISO, D4=BUSY, D5=IRQ, D6=RST.
> This matches the existing `make capture` target exactly, so captures from
> either MCU are directly comparable with the same `decode` SPI decoder settings.

---

## RP2040 Baseline (already captured — reference data)

Source of truth: `captures/bench-rp2040.sr` plus the payload sweep captures
`captures/sweep-{32,64,128,255}.sr`. Analysis lives in the LR2021 bottleneck
audit (`docs/lr2021-bottleneck-analysis-2026-07-29.md`) and the dedicated
baseline results file (file the full per-payload LA numbers into
`docs/rp2040-baseline-results.md` / `docs/spi-timing-analysis.md`).

| Metric | RP2040 value | Source |
|--------|-------------|--------|
| Requested SPI clock | 20 MHz | `firmware/rp2040/src/flrc_raw_tx.cpp` (`SPI_HZ`) |
| **Actual SPI clock** | **10.40 MHz** (52% of requested) | LA measurement — RP2040 prescaler clamps 20 MHz request |
| Effective throughput @ 255 B | **1760 kbps** | goodput sweep capture |
| Effective throughput @ 32 B | **1192 kbps** | goodput sweep capture |
| Bus duty cycle | **18.3%** | LA, 1 s window |
| Inter-packet gap | **320 µs** (air time; BUSY high during TX) | LA — dominated by RF air time, not SPI |
| Packet loss | 0% at 1000/1000 | `docs/SWEEP-RESULTS.md` (FLRC phases) |

**Interpretation:** the RP2040 is near-optimal. SPI is *not* the bottleneck — the
320 µs inter-packet gap is RF air time. SPI itself (10.4 MHz, 18% duty) leaves
headroom. For ESP32 to "win" it must materially close the air-time gap via a
faster SPI path that lets commands overlap more tightly, or hit the 20 MHz SPI
ceiling to enable deeper pipelining.

---

## Test Matrix

Run **2 captures per payload size** for variance check. Same duration (1 s,
24 MHz sample) and same LA wiring for every cell.

| Payload size | 32 B | 64 B | 128 B | 255 B |
|--------------|------|------|-------|-------|
| **Run #1** (capture file) | `sweep-esp32-32-r1.sr` | `sweep-esp32-64-r1.sr` | `sweep-esp32-128-r1.sr` | `bench-esp32.sr` |
| **Run #2** (capture file) | `sweep-esp32-32-r2.sr` | `sweep-esp32-64-r2.sr` | `sweep-esp32-128-r2.sr` | `sweep-esp32-255-r2.sr` |
| Actual SPI clock (MHz) | | | | |
| Effective throughput (kbps) | | | | |
| Packet loss (%) — 1000-pkt run | | | | |
| Per-pkt SPI time (µs) | | | | |
| Inter-packet gap (µs) | | | | |
| Bus duty cycle (%) | | | | |
| RSSI at RX (dBm) | | | | |

The 255 B × Run #1 cell is the headline result; it is produced by the
`make capture-esp32` target into `captures/bench-esp32.sr` (matching the RP2040
`bench-rp2040.sr` naming convention).

---

## Measurement Procedure

1. **Flash ESP32 cont-TX firmware.**
   `make capture-esp32` (builds + flashes `firmware/esp32-c3-flrc` via ESP-IDF,
   then runs the sigrok capture). Firmware must continuously transmit FLRC
   packets of the configured payload size.
2. **LA capture** — identical method to RP2040:
   `sigrok-cli --driver fx2lafw --config samplerate=24mhz --samples 24000000
   --channels D0,D1,D2,D3,D4,D5,D6 -o captures/bench-esp32.sr`
   (1 s window, 7 channels, same map as RP2040.)
3. **Decode SPI** and extract timings:
   `make decode-esp32` → `sigrok-cli -i captures/bench-esp32.sr
   -P spi:cs=D0:clk=D1:mosi=D2:miso=D3 -A spi`
   - Measure actual clock (#1) by edge-counting inside a CS-low window.
   - Measure per-packet SPI time (#4) and inter-packet gap (#5) from CS edges.
   - Compute duty cycle (#6) over the full 1 s window.
4. **Goodput + packet loss** for each payload size using the existing goodput
   script (TX on ESP32, RX on the second board). 1000+ packets per cell.
5. **Repeat** each cell for Run #2.
6. **Compare** every cell against the RP2040 baseline table above.
7. **Commit** all captures (`captures/bench-esp32.sr`, `sweep-esp32-*.sr`) and
   fill the test matrix + a new `docs/esp32-baseline-results.md`.

---

## Decision Criteria

| Outcome | Decision |
|---------|----------|
| ESP32 sustains **> 15 MHz** SPI, stable, ≥ RP2040 goodput | **ESP32 wins.** Solder LR2021 + F33 PA onto an ESP32 board. |
| ESP32 **< 12 MHz** or unstable / high packet loss | **RP2040 stays.** Already near-optimal (see baseline). |
| ESP32 hits **20 MHz** stable + tighter gap | **Strong win** — potential ~2× throughput via deeper pipelining. |
| ESP32 12–15 MHz, marginal | Re-run with the GDMA HAL (`feat/esp32-spi-gdma`) before deciding; do not resolder on marginal data. |

> Note: the LR2021 datasheet SPI maximum is **16 MHz**. ESP32 configurations that
> overdrive at 40 MHz (`EspHalC3.h`) work at bench range but are a reliability
> risk at operational distance (see bottleneck analysis §2). The 20 MHz "strong
> win" case is above datasheet max and must be validated for robustness, not just
> peak throughput.

---

## Deliverables

- [ ] `captures/bench-esp32.sr` (255 B headline capture)
- [ ] `captures/sweep-esp32-{32,64,128,255}-r{1,2}.sr` (full matrix)
- [ ] `docs/esp32-baseline-results.md` (filled test matrix + per-payload LA analysis)
- [ ] Filled RP2040 baseline files (`docs/rp2040-baseline-results.md`,
      `docs/spi-timing-analysis.md`) from the existing RP2040 captures
- [ ] Go/no-go decision recorded against the criteria above
- [ ] All captures + results committed and pushed

## Makefile support

ESP32 capture targets added to the Makefile (see the "ESP32 LA capture" section):

- `make esp32-build` — build `firmware/esp32-c3-flrc` via ESP-IDF
- `make esp32-flash` — flash to `$(ESP_PORT)` (default `/dev/ttyACM0`)
- `make capture-esp32` — build + flash + sigrok capture → `captures/bench-esp32.sr`
- `make decode-esp32` — SPI decode of `bench-esp32.sr` (same pins/decoder as RP2040)
