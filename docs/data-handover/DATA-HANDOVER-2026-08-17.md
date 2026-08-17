DATA HANDOVER — LR2021 RF CHARACTERIZATION
Date: 2026-08-17 · Status: DRAFT v2 for review by Felix + data contributor
Purpose: everything you need to know about what data we record, at what rate, what it can and cannot answer, and what's being fixed.
This doc lives in git: felixfelix-bot/balloon-fresh, branch range-tests, docs/data-handover/ — all URLs in §9.

1. THE THREE DATA-PRODUCING RIGS

RIG A: E80 pair (STM32+LR2021, 900 MHz)
  host-driven bench, ONE row per test cell,
  19 columns incl. Wilson 95% CI, ~100-190 pkt/s during bursts,
  GPS = stop-level metadata (# rows)

RIG B: ESP32-C3 pair (direct LR2021), marker-follow range fw
  ONE row PER PACKET (20-field PKT lines)
  + ONE row per window (27-field RESULT, ~every 7 min loop)
  up to 100 pkt/s, 16 windows, GPS per-packet (when wired, with sats/hdop)

RIG C: RP2040+LR2021 host-driven (IN BUILD, ~2-3 days out)
  ONE row per cell, same 19-col schema as E80 by design,
  ~200 pkt/s, Wilson CI on-board, GPS off in v1

HISTORICAL: V4 walk-test data (Jul 2026): 11-attr per-packet + 18-attr per-phase + 32-col host CSVs + 440-point phone-GPS ground truth (5.7 km walk). FLRC reached -55 dBm at 5.7 km, zero degradation. LoRa phases = 0 packets (radio-config bug, NOT antenna).

2. WHAT EACH RIG RECORDS

Rig A — E80 pair (per-CELL granularity)
- 19 columns: site, stop, dist_m, repeat, mod, len, pa, freq_hz, n, sent, recv, per, per_ci_lo, per_ci_hi, rssi, snr, kbps, elapsed_s, timestamp
- Rate: one row per test cell (N=100-10,000 packets; bursts ~190 pkt/s FLRC; cell = seconds to minutes)
- Metadata: # comment rows — stop location, GPS, heights, weather, session ID, fw version
- Stats computed ON-BOARD: Wilson 95% CI (integer math), per-cell RSSI/SNR averages, crc_err counted separately from missing
- Format: append-only CSV. Code: firmware/e80-stm32-bench/ + tools (branch feat/e80-stm32-bench — URLs §9)

Rig B — ESP32-C3 pair (per-PACKET + per-WINDOW) — richest
- PKT line, 20 fields per packet: loop, window id/name, mode, radio params, pkt_size, seq, rssi, GPS (lat/lon/alt/sats/hdop)
- RESULT line, 27 fields per window: sent/recv/lost, bitErrors/bitsChecked (BER via PRBS15!), payloadCorrupt, RSSI avg/min/max, elapsed, GPS snapshot
- NVS dump: 30 columns (on-board flash log, survives power loss)
- Rate: up to 100 pkt/s per-packet; window summaries every ~7 min loop
- Gap (fixing): PKT lines lack timestamp, SNR, per-packet bitErr → task N2

Rig C — RP2040 host-driven (per-CELL, same schema as Rig A)
- Same 19 columns + agreed nullable extensions (fw_id, gap_us, atten_db, crc_err, ber_pct, rssi_min/max, ts_start/end)
- GPS off v1 (phone GPS covers distance); RSSI marked UNCALIBRATED until cage calibration (task HW-B3)

3. FACT-CHECK OF CURRENT UNDERSTANDING (claims vs verified reality)

- Packet error rate recorded: YES — all rigs; Wilson CI on E80 + Rig C
- Sweeping power: LEGACY ONLY — current windows FIX power. Power sweeps exist in old datasets (data/, branch range-tests). Outdoor plan re-introduces PA steps per stop
- FLRC vs LoRa swept: YES — 8 FLRC + 8 LoRa windows (C3); matrix modes (E80/Rig C)
- "All the different channels" swept: NO — no firmware sweeps channels. Frequencies fixed per band: 868 (LF), 2440/2450 (HF). Channel-sweep tooling scheduled (host-side, Rig A + Rig C)
- LF vs HF carrier swept: YES — dual-band on C3 and V4 multi-radio
- BER recorded: C3 ONLY — PRBS15 bitErrors/bitsChecked (post-FEC). E80 + Rig C v1 = packet-level (PER), no BER
- "No error correction": WRONG — we DO use FEC. FLRC CR 1/2 + 3/4 windows; LoRa CR 4/5 vs 4/7 windows. FEC-corrected packets look "perfect" in PER — that's FEC working; BER-after-FEC still measurable on C3 via PRBS
- GPS position: PARTIAL — C3 per-packet (when wired, with sats/hdop); E80 stop-level metadata; Rig C v1 none

MISSING (nobody claimed these): SNR on C3 range fw (regression, being fixed), voltage/temperature (NEVER recorded anywhere), per-packet RSSI on E80/Rig C (per-cell only), firmware hash per row (scheduled fix: both rigs), duty-cycle/gap column (scheduled), sub-ms timestamps.

4. WHAT THE DATA CAN ANSWER TODAY

- PER vs distance per modulation, with honest uncertainty (Wilson CI ribbons)
- PER vs PA (legacy sweeps) / PER vs mod at fixed power
- FEC coding gain: F1300 vs F1300-CR34, L9 vs L9-CR4/7 direct comparisons (C3)
- Post-FEC BER vs RSSI (C3 only)
- RSSI slope vs distance per band (relative, uncalibrated)
- Dual-band comparison panels (LF vs HF same session)
- Airtime-normalized throughput (kbps recorded alongside PER)

5. WHAT IT CANNOT ANSWER YET (and why)

1. Absolute sensitivity / fade margin — RSSI uncalibrated on all rigs → calibration task HW-B3
2. Pre-FEC BER — CRC-on everywhere; nonzero "BER" would mean firmware bugs, not channel. Verdict: PER+RSSI+SNR is the correct metric set (documented)
3. Per-packet fade time-series on C3 — no per-packet timestamps (→ N2)
4. Channel selectivity — no channel sweeping yet (host tooling scheduled T4; no fw change needed for Rig C)
5. Cross-rig absolute RSSI comparison — three different readback chains, one calibration
6. LoRa SNR on C3 — getSNR never called (→ N2)

6. FIXES IN FLIGHT (agreed by consultants 2026-08-17, all kanban-scheduled with TDD gates)

Already scheduled (host-driven-bench pipeline): LoRa-RSSI opcode fix (FW-5b), LoRa BW-code table (BW-1), LF-FLRC@868 feasibility smoke (HW-B2), RSSI cage calibration (HW-B3).

Decode-gaps board:
- N1: C3 scan-table completion — 3 of 16 windows can NEVER decode today + FLRC sync-dwell bump (catch probability ~9%→~15% per TX pass)
- N2: C3 per-packet observability — add ts_ms, SNR, bitErr, CRCERR lines, seq-dedup
- N3: Schema unification — ONE canonical 19-col + nullable schema + C3→canonical converter
- N4: SPI transaction-pattern audit — reconcile CS-toggle conventions vs vendored Semtech hal
- N5: SPI actual-clock boot log — configs silently run at 52-60% of requested clock
- N6: Field antenna/placement guide — GPS patch needs sky view; stop mixed-factor experiments
- T1: E80 fw — git SHA in ID? reply + rssi_min/max in STAT
- T2: E80 host CSV — session banner + fw_id/gap_us/crc_err/drops/atten_db nullable cols
- T3: C3 fw — version banner + trailing fw_id on RESULT lines
- T4: Channel-sweep host matrix + duty guard (E80 --freq-list; Rig C spec)
- T5: 868 MHz duty/EIRP compliance doc (ERC 70-03 / EN 300 220)
- T6: Visualization starter kit (8 plots) + canonical CSV linter
- T7: NVS-dump ingestion into converter

Parked (with triggers): GDMA RX diagnosis (blocked-HW card, loopback-first), E80 BER (not meaningful as built — LR2021 exposes no bit-error count), RP2040 PRBS (low value while CRC on), scan-scheduler rework (if N1 insufficient), C3 RSSI calibration (only if cross-rig absolute comparison becomes a deliverable).

7. VISUALIZATION MENU (the 8 plots the campaign needs)

1. PER vs distance, log-Y, one curve per mod, CI ribbons — the money plot
2. PER vs PA (sweep curves per mod) — link-budget headroom
3. RSSI vs distance scatter + fit, per band — watermark "uncalibrated" until HW-B3
4. Dual-band slopegraph — LF vs HF at matched distances
5. Airtime-normalized goodput (kbps vs distance) — the "how fast can we talk" plot
6. Power × mod heatmap (PER) — the sweep overview
7. BER vs RSSI (C3) — the FEC story
8. FEC coding-gain panel — coded vs uncoded pairs side by side

8. OPEN DECISIONS FOR YOU TWO (the discussion list)

1. Sign off the canonical schema (19 base + nullable fw_id,gap_us,atten_db,crc_err,ber_pct,rssi_min,rssi_max,ts_start,ts_end) — N3 implements; cheap now, expensive after data accumulates
2. Granularity policy: keep C3 per-packet + per-cell elsewhere, or unify at per-packet? (Storage: per-packet ~100 rows/s — fine for CSV, needs parquet/duckdb for campaigns)
3. Tooling preference: Python+matplotlib vs notebook-first vs something you bring? (Affects whether we ship converter only, or converter + analysis starter kit — T6)
4. Calibration appetite: one cage session calibrates Rig C absolute RSSI; worth extending to C3 rig too? (half-day each)
5. Voltage/temp: never recorded — worth adding? (RP2040 has ADC free; E80/C3 would need wiring)

9. WHERE EVERYTHING LIVES — GIT URLs (self-contained)

ONE public repo holds ALL rig firmware, tools, and data:
  https://github.com/felixfelix-bot/balloon-fresh

RIG A — E80 pair · branch feat/e80-stm32-bench:
  https://github.com/felixfelix-bot/balloon-fresh/tree/feat/e80-stm32-bench
  - Test plan: docs/RANGE-TEST-PLAN.md
  - Bench firmware: firmware/e80-stm32-bench/src/bench.c (+ bench_stats.c/.h)
  - Host control tool: firmware/e80-stm32-bench/tools/e80_bench_ctl.py
  - Host unit tests: firmware/e80-stm32-bench/tests/

RIG B — ESP32-C3 pair · branch feat/c3-range-bringup:
  https://github.com/felixfelix-bot/balloon-fresh/tree/feat/c3-range-bringup
  - Range firmware: mesh-stack/flrc-bench-espidf/main/range_test.cpp
  - Build overlays: mesh-stack/flrc-bench-espidf/sdkconfig.range_tx and sdkconfig.range_rx
  - Capture tooling + resume notes: data/c3-range-indoor-sanity-2026-08-17/ (rx_capture.py, analyze_capture.py, NOTES.md)
  - Raw RX capture logs: data/rx_captures/, data/consolidated-test/

RIG C — RP2040 host-driven (IN BUILD) · branch feat/host-driven-bench:
  https://github.com/felixfelix-bot/balloon-fresh/tree/feat/host-driven-bench
  - Binding plan: docs/PLAN-host-driven-bench.md
  - FW scaffold: firmware/rp2040/src/flrc_range_host.cpp (+ firmware/rp2040/platformio.ini)
  (branch base: range-tests @ 655d094)

RP2040 AUTONOMOUS FW FAMILY (historical + current auto rigs) · branch range-tests:
  https://github.com/felixfelix-bot/balloon-fresh/tree/range-tests
  - firmware/rp2040/src/flrc_range_tx.cpp, flrc_range_rx.cpp, flrc_range_rx_auto.cpp, flrc_range_rx_gps.cpp, flrc_range_rx_sweep.cpp, flrc_range_rx_v2.cpp, flrc_range_rx_v5.cpp

HISTORICAL DATASETS + postmortems (on all branches; canonical: range-tests):
  https://github.com/felixfelix-bot/balloon-fresh/tree/range-tests/data
  - data/README.md — dataset index
  - walk-test CSVs, bitrate sweeps (325/650/1300), power sweeps (868/2.4G), box-mounted RX logs

THIS DOCUMENT + EVIDENCE (branch range-tests):
  https://github.com/felixfelix-bot/balloon-fresh/tree/range-tests/docs/data-handover
  - DATA-HANDOVER-2026-08-17.md (this file)
  - data-census-2026-08-17.md — full census, every claim with file:line evidence
  - decode-gaps-plan-2026-08-17.md — 17-gap audit + remediation plan

RadioLib (vendored as submodule at tracker/firmware/components/RadioLib — no action needed):
  https://github.com/jgromes/RadioLib

QUICK START for the contributor:
  git clone https://github.com/felixfelix-bot/balloon-fresh.git
  cd balloon-fresh
  git checkout range-tests          # data + docs + RP2040 fw
  git checkout feat/c3-range-bringup  # C3 range fw + capture tooling
  git checkout feat/e80-stm32-bench   # E80 bench + host tool

— END — Task IDs (N1-N6, T1-T7, HW-B2/B3) are internal kanban references; all fixes are scheduled and running. Repo is public — no access needed. Raw capture logs live in the repo under data/; multi-GB artifacts stay on the lab PC.
