# DECODE-GAPS REMEDIATION PLAN — LR2021 RF Characterization Campaign

**Date:** 2026-08-17 · **Author:** decode-gaps consultant subagent (read-only audit; this report is the only artifact)
**Scope:** decode/measurement gaps across the three LR2021 rigs — C3 autonomous range fw (`~/worktrees/c3-range-bringup/mesh-stack/flrc-bench-espidf`), RP2040 bench fw family (`~/repos/balloon-e80bench/firmware/rp2040/src` + host-driven-bench plan `~/host-driven-bench-plan.md`), E80 STM32 bench (`~/repos/balloon-e80bench/firmware/e80-stm32-bench`).
**Method:** every root cause below was verified by reading source at file:line on this bench PC. Nothing is asserted from memory. Cross-referenced: `~/reports/data-census-2026-08-17.md`, `docs/RSSI-FIX-PLAN.md`, `docs/WALK-TEST-FIX-PLAN.md`, `docs/spi-frequency-sweep-results-2026-07-16.md`, RCA commit `da0b113`.

---

## EXECUTIVE SUMMARY

**17 gaps evaluated → 4 already covered by the host-driven-bench pipeline · 8 remediable now via 6 NEW tasks (B) · 5 parked/deferred (C).**

| # | Gap | Verdict |
|---|-----|---------|
| G1 | C3 RX scan table missing 3 TX windows (SF9/BW500, SF9/CR4-7, FLRC-1300/CR3-4) | **B → N1** |
| G2 | C3 scan-cycle sync-catch yield (~9 %/pass for FLRC windows) | **B (mitigation in N1)** + rework **C → P4** |
| G3 | LoRa packet-status RSSI opcode missing on RP2040 host-driven fw | **A → FW-5b** `t_41b23f6c` |
| G4 | LoRa BW-code contradiction (RP2040 fw) | **A → BW-1** `t_c91296d9` |
| G5 | RSSI uncalibrated (RP2040/E80 absolute) | **A → HW-B3** `t_a5b82271` (+HW-B2 cage) |
| G6 | RSSI uncalibrated (C3 rig) | **C → P5** |
| G7 | LF-FLRC @868 never proven on LR2021 RP2040 module | **A → HW-B2** `t_be4e177b` |
| G8 | ESP32-C3 GDMA RX = 0 packets (built-never-tested branch) | **C → P1** (trigger defined) |
| G9 | GPS patch antenna in rucksack / field placement guidance | **B → N6** (doc-only) |
| G10 | E80 BER feasibility | **C → P2** (not meaningful; rationale below) |
| G11 | RP2040 BER addition (PRBS payload) | **C → P3** (cheap card, low value; rationale below) |
| G12 | Three CSV schemas across rigs | **B → N3** |
| G13 | Historical split-CS garbage-RSSI bug — residual pattern risk | **B → N4** (audit + parser tests) |
| G14 | SPI 20 MHz requested vs ~10.4–12 MHz actual — timing-margin question | **B → N5** (mostly code-verifiable; precedent data exists) |
| G15 | C3 PKT line lacks per-packet timestamp, SNR, bitErr; CRC-error packets invisible per-packet | **B → N2** |
| G16 | C3 no on-device seq dedup (duplicates inflate rx; lost can read 0) | **B → N2 optional / N3 offline** |
| G17 | Canonical CSV lacks `crc_err` column (E80 STAT has it, CSV drops it) | **B → N3** (decision point) |

**Total NEW effort:** ~3–3.5 h across 6 tasks, all 15–45 min, **none require boards or Felix at bench** (all are code + host-test + docs; bench verification can ride the next already-scheduled hardware session). One soft ordering constraint: **N4 should land before FW-5a/FW-5b code review** (see dependency notes).

---

## PART A — ALREADY COVERED BY PIPELINE (do NOT duplicate)

### A1. LoRa packet-status RSSI on RP2040 host-driven fw — **FW-5b = `t_41b23f6c`**
- **Verified root cause:** the RX backend being ported reads packet status only via FLRC `GET_FLRC_PACKET_STATUS 0x024B` with FLRC 9-bit assembly (`flrc_range_rx_sweep.cpp` L158-175; `flrc_range_rx_v2.cpp:187-188`). LoRa needs `GET_LORA_PACKET_STATUS 0x022A` with a different response layout (rssiSync at buf[2], SNR at buf[3] — proven implementation in `lora_868_rx.cpp:172-213`, incl. the historical RSSI/SNR index-swap fix note at :180). Vendored-driver ground truth: `lr20xx_radio_flrc_types.h:230-238` (`rssi_avg_in_dbm`/`rssi_sync_in_dbm`) vs `lr20xx_radio_lora_types.h:298-312` (`rssi_pkt_in_dbm`, `snr_pkt_raw` in 0.25 dB, `crc`) — **different structs, different opcodes**.
- **Pipeline coverage:** plan REV-2 M4 splits FW-5 → FW-5b "RX + RSSI both mods incl LoRa packet status read" (`~/host-driven-bench-plan.md` L244, L127). Until FW-5b lands, LoRa cells in the new bench CSV would have empty/wrong RSSI.
- **Residual (→ N4):** FW-5a/5b will *copy* the sweep-fw GET_* helpers verbatim; those helpers carry the split-CS/single-CS inconsistency documented in G13. N4 hardens exactly the code being copied — schedule N4 alongside, not instead.

### A2. LoRa BW-code table — **BW-1 = `t_c91296d9`**
- Plan REV-2 B4 (`~/host-driven-bench-plan.md` L238): extract authoritative BW table from vendored `lr20xx_driver`, reconcile vs `lora_868_tx.cpp` (203/406/812) and the dual_radio comment (0x05=250k). Blocks FW-5a + HS-1b. Nothing to add.

### A3. RSSI cage calibration (RP2040/E80 absolute axis) — **HW-B3 = `t_a5b82271`** (+ HW-B2 cage session)
- Plan minors: "RSSI marked UNCALIBRATED in CSV; HW-B3 adds cage calibration (known PA + attenuator)" (L250; HW-B3 body L159-161). Census gap 1 confirms. **Residual → P5:** the C3 rig's RSSI stays uncalibrated even after HW-B3 (different radio instance); acceptable while RSSI is used only as relative slope per RANGE-TEST-PLAN §3.

### A4. LF-FLRC @868 feasibility — **HW-B2 = `t_be4e177b`**
- Plan REV-2 B2 (L236): HW-B2's first cage cell is the LF-FLRC feasibility smoke (MOD FLRC 650, FREQ 868000000, N=50); cross-evidence: E80 (same LR2021 silicon) runs FLRC-650@868 fine (`radio_bench.c` FLRC init L63-72 + demo-proven hal). Decision recorded in cage CSV metadata.

---

## PART B — NEW TASKS WORTH SCHEDULING NOW (no pipeline dependency)

All six: host-only work, TDD-able, atomic, landable today. Bench verification (where applicable) rides the next scheduled hardware session — boards are currently physically removed per worktree HEAD `ee1e276` ("BLOCKED at flash"), which affects flashing only, not code+tests.

---

### N1 — C3 range RX: complete scan table (3 windows) + CR4/7 decision + FLRC sync-dwell mitigation

- **Gap(s):** G1, G2 (mitigation half).
- **Root cause (verified):** `range_test.h` TX table `range_windows[]` (L37-54) has 16 windows; RX scan table `range_scan_modes[]` (L119-135) has 13 modes and is **missing exact matches** for:
  - window idx 2 `L9W-868` (LoRa SF9 **BW500** CR5 @868, h:40) — scan LoRa-868 entries are BW125 only (h:127-129);
  - window idx 4 `L9CR7-868` (LoRa SF9 BW125 **CR7**, h:42) — scan has CR5 only;
  - window idx 11 `F1300C34-868` (FLRC 1300 **CR3/4 = cr 0x01**, h:49) — scan FLRC-1300 entry is cr 0x02 (=CR 1/0 uncoded), h:121.
  Mode-mismatch (BW/CR/FEC) ⇒ demodulator never locks ⇒ RX never sees even the sync packets ⇒ those three windows are silently never measured. `RANGE_SCAN_MODE_COUNT` (h:135) is sizeof-derived, so entries are the only change.
- **CR4/7 decision (verified in vendored RadioLib):** LR2021 LoRa CR is the *denominator* form — `LR2021::setCodingRate` `RADIOLIB_CHECK_RANGE(cr, 4, 8)` then `cr-4` (LR2021_config.cpp, setCodingRate; raw enums `LR2021_commands.h:381-384`). The TX value `cr=7` is valid and already in use. FLRC CR is the raw register form 0x00=1/2, **0x01=3/4**, 0x02=1/0, 0x03=2/3 (`LR2021_commands.h:505-508`) — the table's 0x00/0x01/0x02 values are correct for LR2021 (note: they would be WRONG for the SX128x class API — document this in-range-file so nobody "fixes" it). **Verdict: CR4/7 fully supported; just add the scan entry `{RANGE_LORA, 868.0f, 0, 9, 125.0f, 7, 22}`** (and BW500 entry `{... 9, 500.0f, 5, 22}`, FLRC `{RANGE_FLRC, 868.0f, 1300, 0, 0.0f, 0x01, 22}`).
- **Scan-yield risk found during audit (G2):** scan dwell is 5 s/mode (`RANGE_SCAN_TIMEOUT_MS`, h:11; range_test.cpp:296) → full cycle 13×5=65 s now, **16×5=80 s after the fix**. TX sync phase = 5 sync pkts × `sync_delay_ms`: LoRa 2 s → 10 s; **FLRC 0.5 s → 2.5 s** (h:38-53). P(catch per TX pass) ≈ (dwell+sync)/cycle: LoRa ≈ 19 %, **FLRC ≈ 9 %** → a FLRC window is expected to be caught only every ~5-10 TX loops (each loop ≈ 7-15 min) ⇒ hours per window. Minimal mitigation inside this task: raise FLRC windows' `sync_delay_ms` 500→1500 (one-line ×5 windows; sync phase is dead air anyway) → FLRC catch ≈ 15 %. Deeper scheduler rework stays parked (P4).
- **Fix approach:** add 3 scan entries (+5 lines), bump 5 FLRC `sync_delay_ms`, add a static host test asserting **every `range_windows[]` entry has ≥1 matching `range_scan_modes[]` entry on (mode, freq, bitrate, sf, bw, cr)**.
- **TDD seam (red first):** compile `range_test.h` on host g++ (it is `#pragma once` + plain structs — no SDK includes) with a test that iterates windows×scan and fails on the 3 uncovered windows → RED on current HEAD, GREEN after entries. Guards regressions forever.
- **Hardware dependency:** none for code+test. Bench verify: C3 pair + FLASH-QUEUE at next session (range fw currently built-not-flashed anyway).
- **Pipeline dependency:** none. (Different firmware from the RP2040 host-driven bench.)
- **Risk if unfixed:** 3 of 16 characterization cells (SF9/BW500, SF9/CR4/7, FLRC-1300/CR3-4) yield zero data in every future range session; SF9/BW500 and CR4/7 are exactly the link-budget-sensitive variants. Plus FLRC windows may waste hours per session on sync misses.
- **Size:** 30 min.
- **Branch:** `feat/c3-range-bringup` (worktree `~/worktrees/c3-range-bringup`, remote `github`, current HEAD `ee1e276`).

---

### N2 — C3 range RX: per-packet observability (timestamp + SNR + bitErr; optional CRCERR line + seq dedup)

- **Gap(s):** G15, G16.
- **Root cause (verified):** the per-packet `PKT,...` printf (`range_test.cpp:472-478`) carries loop/winId/name/mode/radio-params/pkt_size/**seq/rssi**/GPS — but:
  - **no timestamp** (RX tracks `lastPktMs` at :323 for timeouts but never prints it; RP2040 fw already prints `uptime=%lums` — `flrc_range_rx_v2.cpp:550-555` — so host-side arrival timestamps are the only, jittered, option today);
  - **no SNR** for LoRa windows — `getSNR()` is never called; only `getRSSI(false)` at :449. (RP2040 `lora_868_rx.cpp:216-239` and E80 `radio_bench.c:393` both capture SNR; the canonical CSV has an `snr` column that C3 data can never fill);
  - **no per-packet bitErr/bytesBad** — `prbs15_verify` returns them (:465-468) but only window aggregates survive into `RESULT` (:375) / NVS. Offline BER-by-distance or burst-error structure is impossible;
  - **CRC-error packets are invisible per-packet** — `rxCrcErrors` increments on `readData != ERR_NONE` (:440-441) but no record of *when* or *which seq neighborhood*; `lost = tx_sent − rxReceived` (:373) conflates *missing* with *CRC-failed* (E80 separates `crc_err` in STAT; V4 fw separates `crc_err=` in PHASE_RESULT — `multi_radio_sweep_rx_v4.cpp:701`);
  - **no on-device seq dedup** — `rxReceived++` per good packet (:448); a duplicate seq inflates the count and can drive `lost` to 0 falsely (V4 fw has `unique=` dedup; E80 uses first/last-seq window, `bench.c:821-825`).
- **Fix approach (scoped):** extend the PKT printf with `ts_ms` (the existing `esp_timer` ms already in hand at :323), `snr` (call `radio->getSNR()` in LoRa mode; FLRC has none — print 0 like E80 does, `radio_bench.c:404`), and `bit_err,bytes_bad` from the already-computed `prbs15_verify` outputs. Emit a one-line `CRCERR,ts_ms` record in the :440-441 branch. Optional second commit: seq-based dedup (track last-seq/high-water, count duplicates separately).
- **TDD seam:** extract the PKT-line formatting into a pure function `format_pkt_line(...)` (no SDK types — pass plain ints) and golden-test the output string on host g++; red-first test written against the NEW field list. (No host-test harness exists yet in flrc-bench-espidf — this task adds `main/host_tests/` with one Makefile pattern rule, mirroring the E80 `make test-host` seam.)
- **Hardware dependency:** none for code+tests. Bench verify rides next session.
- **Pipeline dependency:** none (C3 fw). Note: converter N3 should be scheduled with N2 or after, so the canonical schema can bind ts/snr/bitErr fields.
- **Risk if unfixed:** C3 field data stays second-class for post-hoc analysis: no per-packet timing (fade/burst analysis), no LoRa SNR column (link-budget modeling loses the SNR axis on the only rig with GPS-tagged range data), no per-packet BER contribution, and loss-vs-CRC-error ambiguity in every window.
- **Size:** 30 min core (ts+snr+bitErr+CRCERR) + 15 min optional (dedup).

---

### N3 — Schema unification: ONE canonical per-window schema + C3→canonical converter

- **Gap(s):** G12, G17.
- **Root cause (verified):** three live schemas:
  - E80 host CSV, 19 cols, one row per cell: `site,stop,dist_m,repeat,mod,len,pa,freq_hz,n,sent,recv,per,per_ci_lo,per_ci_hi,rssi,snr,kbps,elapsed_s,timestamp` (`tools/e80_bench_ctl.py` CSV_COLUMNS L53-55);
  - RP2040 host-driven plan adopts the **same 19 columns** (plan §HS-2, L124) — these two are aligned by design;
  - **C3 is the outlier**: per-window `RESULT,...` (27 comma fields, `range_test.cpp:384-394`) + per-packet `PKT,...` (19 fields, :472-478) + NVS mirror (`nvs_results.h`); historical V4/walk adds `PHASE_RESULT` (18 fields, `multi_radio_sweep_rx_v4.cpp:701`).
  Additionally the canonical 19-col has **no `crc_err` column** even though E80 STAT and V4 PHASE_RESULT both count it — silent conflation at conversion time if not decided.
- **Fix approach (decision):** canonical = the E80/RP2040 19-col schema (already 2-of-3 rigs, zero migration cost), extended by **optional nullable columns** `crc_err`, `ber_pct`, `rssi_min/rssi_max`, `ts_start/ts_end`, `fw_id` appended after `timestamp` (append-only so existing consumers keep parsing). Converter `tools/c3_to_canonical.py`: parse PKT+RESULT lines → per-window rows with **seq-based dedup** and **seq-window PER** (`expected = last_seq − first_seq + 1`, E80 `bench_stats.c:55` semantics), RSSI avg/min/max from PKT lines, `ber_pct` from RESULT aggregate (per-packet bitErr only after N2). Join-at-analysis-time stays possible (converter is lossless: PKT lines preserved).
- **TDD seam:** pytest with synthetic golden fixtures — PKT streams including duplicate seqs, seq gaps, out-of-order arrivals, a missing END/RESULT line (window recoverable from PKT alone), CRC-err-only windows; assert canonical rows + Wilson-free PER. Red-first: write the fixture tests before the parser exists.
- **Hardware dependency:** none. (No real C3 capture exists yet — range fw never flashed — so fixtures are synthetic; that's also why this must NOT wait for field data.)
- **Pipeline dependency:** none hard. Soft: land before DOC-1 (README-host-driven-bench documents the CSV schema — reference the canonical doc instead of restating).
- **Risk if unfixed:** every cross-rig comparison (the whole point of running three rigs) requires bespoke glue per session; C3 windows can't be deduped/re-PER'd after the fact once raw logs rotate; crc_err ambiguity baked into every future analysis.
- **Size:** 45 min.

---

### N4 — SPI transaction-pattern audit: harmonize GET_* helpers vs vendored Semtech hal + mock-SPI parser tests

- **Gap(s):** G13 (+ hardening the code FW-5a/5b will copy).
- **Root cause / status (verified):**
  - History: garbage RSSI (constant 36 dBm over 206,947 packets) was SX1280 opcode `0x0104` sent to LR2021 — **fixed 2026-07-23** to `0x024B` with 9-bit assembly in `flrc_range_rx_auto.cpp`, `flrc_range_rx_gps.cpp` (`docs/RSSI-FIX-PLAN.md`, "STATUS: RESOLVED"); LoRa RSSI/SNR byte-index swap fixed and documented in `lora_868_rx.cpp:180-182` and `lora_range_rx.cpp:185`.
  - **Residual inconsistency:** `multi_radio_sweep_rx_v4.cpp:410-412` asserts GET_IRQ_STATUS "MUST be single CS-low transaction … Splitting CS toggle between send+read makes the chip forget the command → all reads return 0x00 (silent packet drops)", while `lora_868_rx.cpp:188-203` reads packet status in **two CS windows** (cmd phase, then read phase), and the vendored Semtech `lr20xx_hal.c` (L144-170) — demo-proven on this exact hardware, designated ground truth by BW-1 — uses the **split-phase pattern** (NSS↓ cmd NSS↑ → wait BUSY → NSS↓ read NSS↑). Two contradictory conventions are now in the fw family that FW-5a/5b copy from.
- **Fix approach:** audit table of every GET_* helper across `firmware/rp2040/src/*.cpp` (packet status FLRC/LoRa, IRQ status, RSSI inst, FIFO read) × transaction pattern; reconcile each against `lr20xx_hal.c`; produce `docs/spi-transaction-patterns.md` + a tiny shared header comment; where code changes, change only the audit-confirmed-wrong helper(s). Extract the two packet-status byte-parsers (FLRC 0x024B 9-bit `raw=(buf[4]<<1)|((buf[6]&0x04)>>2)`, `-(int8_t)(raw/2)`; LoRa 0x022A `-(int8_t)(buf[2]/2)` + SNR sign-extend) into pure functions + host unit tests with synthetic SPI buffers (edge values: 0x00, 0xFF, half-dBm bit set/unset, SNR ≥/<128).
- **TDD seam:** parser tests red-first (functions don't exist yet); audit doc is the deliverable that de-risks FW-5a/5b.
- **Hardware dependency:** none (pattern reconciliation is code-vs-code). Any behavior change on-air is verified in the already-scheduled HW-B1/B2 sessions.
- **Pipeline dependency:** **should land before FW-5a/FW-5b review** (soft ordering; the pipeline copies these helpers verbatim). No hard block.
- **Risk if unfixed:** the next port (FW-5a/5b) inherits an untested convention mismatch; a silent 0x00-read regression on packet status would look exactly like the 2026-07-23 garbage-RSSI incident — discovered only after a field session.
- **Size:** 30-45 min.

---

### N5 — SPI actual-clock boot log + FLRC-2600 timing-margin note

- **Gap(s):** G14.
- **Root cause / status (verified):** every RP2040 bench fw requests `SPI_FREQ_HZ 20000000UL` (~15 files, e.g. `flrc_cont_rx.cpp:37`, `flrc_range_rx_v2.cpp:57`). Measured reality (Pico SDK divider, `docs/spi-frequency-sweep-results-2026-07-16.md`): **requests ≥12 MHz all map to 12.0 MHz actual; the "16 MHz" v4 fw ran at 12 MHz**; a 10.42 MHz request mapped to 8.0 MHz. The parent-cited 10.40 MHz figure is consistent with the same divider family (≈125 MHz/(CPSDVSR·SCR)). The doc's conclusion: **SPI clock is NOT the throughput bottleneck** — per-byte Arduino `transfer()` overhead and the IRQ-poll loop are.
- **Fix approach:** stop guessing — log it. pico-sdk `spi_set_baudrate()` **returns the actual achieved frequency**; add a boot-banner line `SPI actual=<n> Hz (requested <m>)` next to the existing init logs, and extract `spi_actual_baud(req_mhz, sysclk_mhz)` (SSP CPSDVSR/SCR divider math, even-prescale ≥2) as a pure host-testable function. Add a 5-line margin note to the sweep-results doc: FLRC-2600 worst-case FIFO read 255 B @12 MHz ≈ 170 µs vs ≈780 µs airtime ⇒ ~4.6× margin; the decode risk was never the clock, it was per-byte call overhead (already addressed by raw-SPI helpers).
- **TDD seam:** red-first host test for `spi_actual_baud` against the measured table rows (20→12, 16→12, 10.42→8.0).
- **Hardware dependency:** none for the computation+log. A logic-analyzer confirmation is optional and NOT required to close the gap (the SDK-divider math is deterministic); if ever desired, ride any already-scheduled bench session.
- **Pipeline dependency:** none; note in the card that FW-5a should replicate the one-line banner in the host-driven fw init.
- **Risk if unfixed:** every future "are we SPI-limited?" debate re-litigates an answered question; configs silently run at 52-60 % of requested clock with nobody noticing when sysclk or prescaler assumptions change.
- **Size:** 15-20 min.

---

### N6 — Field guidance doc: antenna + board placement for walk tests (GPS patch in rucksack)

- **Gap(s):** G9.
- **Root cause / status (verified):** Jul 24 walk procedure put the TX board **inside the rucksack** with GPS + battery (`docs/MORNING-HANDOVER-V4.md:82`). Outcome: FLRC excellent (-55 dBm @ 5.7 km, zero degradation), GPS fine (7-21 sats), **LoRa phases 0 packets with noise-floor RSSI (-93..-104 dBm)** — and the postmortem (`docs/WALK-TEST-FIX-PLAN.md` §2) attributes the LoRa zero to **radio configuration (RX_PATH/SET_RX_PATH verification), not the antenna**. So the antenna-placement gap is about *GPS patch sky-view and RF antenna body-shadowing* as standing field risk, while the LoRa-0 root cause is tracked separately in that plan.
- **Fix approach:** doc-only: `docs/field-antenna-placement.md` — GPS patch antenna needs unobstructed sky view (external mount / top pocket, never under body or battery), LoRa/FLRC antenna vertical & away from torso ≥20 cm where practical, rucksack vs handheld mounting matrix, per-stop photo protocol (photo of rig placement into metadata.json per the V4 capture convention), and a pointer that LoRa-0-packets has a radio-config suspect (WALK-TEST-FIX-PLAN §2) so antenna changes aren't blamed for config bugs.
- **TDD seam:** n/a (docs-in-commit gate only).
- **Hardware dependency:** none.
- **Pipeline dependency:** none.
- **Risk if unfixed:** next walk repeats a mixed-factor experiment (antenna placement + radio config + body shadowing all varying at once) — another 5.7 km session that can't attribute its zeros.
- **Size:** 15-20 min.

---

## PART C — PARKED / DEFERRED (with explicit reasons and re-trigger conditions)

### P1 — GDMA RX diagnosis (G8) — **KEEP PARKED, trigger defined**
- **Verified:** GDMA HAL exists and is real (`feat/esp32-spi-gdma` tip `3b70f8e`: persistent DMA staging buffers + async queue `spiQueueTrans`/`spiGetResult`; the C3 worktree's `EspHalC3.h:128-190` already carries it — the range fw uses the **blocking staging path**, not the async queue, so it is NOT exposed to the 0-packet RX issue). RCA commit `da0b113` ("ESP32 vs RP2040 RX pipeline root cause analysis") records the branch as **built-never-tested** and its own recommendation #1 is "test it — just needs flashing". TX reportedly hit 1571 kbps; RX got 0 packets (async path).
- **Why parked:** diagnosis is impossible without the C3 pair at the bench (FLASH-QUEUE + orchestrator approval), and the RP2040 host-driven bench pipeline is now the primary decode path — GDMA only matters if ESP32-C3 must decode FLRC-2600 itself.
- **Re-trigger:** schedule a 45-min [HW] card ("flash GDMA build, loopback SPI test first, then FLRC-2600 RX vs RP2040 reference") the moment an ESP32-side high-bitrate decode requirement appears, or at any bench session with spare board-time. Loopback-first keeps it cheap.

### P2 — E80 BER (G10) — **PARKED; verdict: BER not meaningful on E80 as built**
- **Verified:** LR2021 packet status exposes **no bit-error count** — LoRa status = length/crc/cr/detector/rssi/snr (`lr20xx_radio_lora_types.h:298-312`); FLRC status = length/syncword_index/rssi_avg/rssi_sync (`lr20xx_radio_flrc_types.h:230-238`). CRC-failed packets never reach payload verify (`radio_bench.c` counts them as `rx_crc_err`, L829); payload verify is boolean (`bench_payload_verify`, xorshift32 LFSR, `bench_payload.c:60-78`). ⇒ any BER would be **post-FEC-post-CRC residual** ≈ 0 for a real channel (undetected-CRC probability ~2⁻¹⁶/packet); a nonzero value indicates firmware/payload bugs, not channel quality. Meaningful channel BER would require a CRC-off mode (losing the crc_err/PER separation and FLRC sync integrity) — a redesign, not a task. **PER + RSSI + SNR is the correct absolute metric set** (RANGE-TEST-PLAN §3 agrees). Document this verdict in the E80 README (one paragraph, fold into N3's schema doc) and stop carrying the gap.

### P3 — RP2040 PRBS-BER extension (G11) — **PARKED; cheap card if ever needed**
- **Verified:** FW-7 payload is **not PRBS** — plan §1 L59: "bytes 0-3 = big-endian seq, payload = incrementing pattern"; FW-8 verifies pattern pass/fail (L104-106). So PRBS-BER needs: port C3 `prbs15_fill/verify` (portable, `prbs.h` 8 lines) into the TX/RX engines + bit counters + a CSV column — ~30-45 min. **But the same CRC logic as P2 applies**: with CRC on, measured BER is residual-only. Its honest value is payload-integrity cross-check (catches silent FIFO/driver corruption), which FW-8's pattern-verify already mostly provides. Park; pull the card if a firmware-corruption hunt ever needs bit-level evidence.

### P4 — C3 scan-scheduler rework (G2, deep half) — **PARKED**
- The N1 mitigation (longer FLRC sync dwell) gets yield to workable (~15 %/pass); a proper fix (scan order synchronized to the deterministic TX window sequence, or per-mode adaptive dwell) is a firmware-behavior change deserving its own bench-verified card. Pull it up only if the next field session still shows FLRC windows taking >2 loops to catch.

### P5 — C3-rig RSSI absolute calibration (G6) — **PARKED**
- HW-B3 calibrates the RP2040 bench radio instance. The C3 rig would need its own cage session. Only worth it if cross-rig absolute-RSSI comparison becomes a deliverable; until then C3 RSSI = relative slope only (documented in RANGE-TEST-PLAN §3).

---

## PROPOSED NEW KANBAN TASK BODIES (ready to paste)

> Common quality gates for all cards below (do not restate in each): **TDD red-first** (failing test committed before implementation where a test seam exists) · **tests green** before done · **docs-in-commit** (evidence/test output or doc in the same commit) · **atomic commits** (1 card = 1-2 commits, no drive-bys) · **push-verified** (`git push` + remote SHA check) · **review-not-done** (self-merge ≠ done; route to cross-family reviewer per RV-1 pattern before marking complete).

---

**N1 · C3 range RX: add 3 missing scan-table entries (SF9/BW500, SF9/CR4-7, FLRC-1300/CR3-4) + FLRC sync dwell 500→1500 ms**
Branch `feat/c3-range-bringup` (worktree `~/worktrees/c3-range-bringup`). Add to `range_scan_modes[]` (`main/range_test.h:119-135`): `{RANGE_LORA,868.0f,0,9,500.0f,5,22}`, `{RANGE_LORA,868.0f,0,9,125.0f,7,22}`, `{RANGE_FLRC,868.0f,1300,0,0.0f,0x01,22}`; bump `sync_delay_ms` 500→1500 on the five FLRC windows (h:46-53). Add host coverage test (new `main/host_tests/`, g++ Makefile pattern): every `range_windows[]` entry must match ≥1 scan mode on mode/freq/bitrate/sf/bw/cr — commit the failing test FIRST (3 windows uncovered on HEAD ee1e276). Include a header comment: FLRC cr values are LR2021 raw register codes (0x00=1/2, 0x01=3/4, 0x02=1/0 — `LR2021_commands.h:505-508`); LoRa cr is denominator 4-8 — do NOT "normalize" to SX128x-style constants. Evidence: host-test output + build log (`idf.py build` for both range overlays). Bench verify deferred to next board session (boards currently off-site). ~30 min.

**N2 · C3 range RX: per-packet observability — ts_ms + SNR + bit_err in PKT line, CRCERR records, optional seq dedup**
Branch `feat/c3-range-bringup`, after N1. Extend `PKT,...` printf (`main/range_test.cpp:472-478`) with `ts_ms` (esp_timer ms already tracked at :323), `snr` (call `radio->getSNR()` LoRa-only; FLRC prints 0, cf. E80 `radio_bench.c:404`), `bit_err,bytes_bad` from existing `prbs15_verify` outputs (:465-468). Emit `CRCERR,<ts_ms>` line in the CRC branch (:440-441). Extract formatting into pure `format_pkt_line()` + host golden-string test in `main/host_tests/` (red-first against new field list). Optional second commit: last-seq dedup counter (V4 `unique=` precedent, `multi_radio_sweep_rx_v4.cpp:701`). Evidence: host-test output + build log. ~30 min (+15 optional).

**N3 · Canonical per-window CSV schema + C3→canonical converter (`tools/c3_to_canonical.py`)**
Repo `~/repos/balloon-e80bench` (tools live beside `e80_bench_ctl.py`). Deliverables: (1) `docs/canonical-csv-schema.md` — canonical = E80/RP2040 19-col (`site,stop,dist_m,repeat,mod,len,pa,freq_hz,n,sent,recv,per,per_ci_lo,per_ci_hi,rssi,snr,kbps,elapsed_s,timestamp`) + append-only nullable extension `crc_err,ber_pct,rssi_min,rssi_max,ts_start,ts_end,fw_id`; (2) converter: C3 `PKT`/`RESULT` lines → one row per window with seq-dedup, seq-window PER (`last−first+1`), RSSI min/max/avg from PKT lines, `ber_pct` from RESULT; (3) pytest golden fixtures: duplicate seqs, seq gaps, out-of-order, missing-RESULT (recover from PKT alone), CRC-err-only window; assert `crc_err` passthrough decision (schema G17). Commit failing fixtures first. Also fold in the P2 verdict paragraph (E80 BER = residual-only by design; PER is the metric). Evidence: pytest output. No hardware. ~45 min.

**N4 · SPI transaction-pattern audit + packet-status parser unit tests (feeds FW-5a/5b review)**
Repo `~/repos/balloon-e80bench`, `firmware/rp2040/src`. Deliverables: (1) `docs/spi-transaction-patterns.md` — table of every GET_* helper (FLRC pkt-status 0x024B, LoRa pkt-status 0x022A, IRQ status, RSSI-inst 0x020B, FIFO read) × CS pattern, reconciled against vendored Semtech ground truth `lr20xx_hal.c:144-170` (split-phase: NSS↓cmd NSS↑ → BUSY → NSS↓read NSS↑); resolve or explicitly document the contradiction with `multi_radio_sweep_rx_v4.cpp:410-412` (single-CS claim); (2) extract FLRC 9-bit (`raw=(buf[4]<<1)|((buf[6]&0x04)>>2)`, `-(int8_t)(raw/2)`) and LoRa (`-(int8_t)(buf[2]/2)` + SNR sign-extend) parsers into pure functions with host unit tests over synthetic SPI buffers (edge: 0x00, 0xFF, half-dBm bit, SNR 127/128). Red-first. Evidence: test output + audit doc. No hardware (behavior changes, if any, verify in HW-B1/B2). Soft-dep: land before FW-5a/FW-5b review. ~30-45 min.

**N5 · Log actual SPI clock at boot + timing-margin note (20 MHz request → ~12 MHz actual)**
Repo `~/repos/balloon-e80bench`, `firmware/rp2040/src` (sweep fw family). Add pure `spi_actual_baud(req_mhz, sysclk_mhz)` (pico-sdk SSP CPSDVSR/SCR even-prescale math) + host tests pinned to the measured rows in `docs/spi-frequency-sweep-results-2026-07-16.md` (20→12, 16→12, 10.42→8.0) — red-first. Boot banner prints `SPI actual=<n> Hz (requested <m>)` (cross-check vs `spi_set_baudrate()` return at runtime). Append 5-line margin note to the sweep-results doc: FLRC-2600 FIFO 255 B @12 MHz ≈ 170 µs vs ≈780 µs airtime ⇒ ~4.6× margin; bottleneck is per-byte Arduino overhead, not clock. Note for FW-5a: replicate the banner line. ~15-20 min.

**N6 · Field doc: antenna + board placement for walk tests (GPS patch sky-view; LoRa-0 has a radio-config suspect)**
Repo `~/repos/balloon-e80bench`, new `docs/field-antenna-placement.md`. Content: GPS patch antenna unobstructed sky view (top pocket/external, never under battery/body); RF antenna vertical, ≥20 cm from torso where practical; rucksack-vs-handheld mounting matrix; per-stop rig photo into capture metadata (V4 `#` header + metadata.json convention); explicit note that Jul-24 LoRa-0-packets is attributed to radio config per `docs/WALK-TEST-FIX-PLAN.md` §2 (noise-floor RSSI, SET_RX_PATH check) — don't blame antenna for config bugs. Docs-in-commit gate. ~15-20 min.

---

## DEPENDENCY NOTES (pipeline interaction summary)

- **No hard blocks either way.** None of N1-N6 blocks a pipeline task, and no pipeline task blocks N1-N6.
- **Soft ordering:** N4 before FW-5a (`t_*` FW-5a card) / FW-5b (`t_41b23f6c`) **review** — the pipeline copies the audited helpers verbatim. N2 before/with N3 so the canonical schema binds the new PKT fields. N3 before DOC-1 (README references canonical schema doc). N5's banner line should be replicated inside FW-5a when it lands (one line, note on card).
- **Bench verification debt:** N1/N2 changes are verified on-air only at the next board session (boards physically removed, HEAD `ee1e276`); flashing then requires FLASH-QUEUE approval per repo rules. This is deliberate: cards close on host-test evidence, field confirmation rides the already-scheduled HW-B1/B2/B3 session.
- **Do-not-duplicate guard:** BW-1 (`t_c91296d9`), FW-5b (`t_41b23f6c`), HW-B2 (`t_be4e177b`), HW-B3 (`t_a5b82271`) already own G3/G4/G5/G7. Nothing in N1-N6 touches their scope.

---

## APPENDIX — Evidence index (file:line, all read on this bench PC 2026-08-17)

| Claim | Evidence |
|---|---|
| 3 scan entries missing | `range_test.h:37-54` (windows) vs `:119-135` (scan modes) |
| CR4/7 supported; FLRC cr raw-coded | RadioLib vendored `LR2021_config.cpp` setCodingRange(4,8)+`cr-4`; `LR2021_commands.h:381-384, 505-508` |
| Scan dwell 5 s / FLRC sync 2.5 s | `range_test.h:11`; `range_test.cpp:296`; windows `sync_delay_ms` h:46-53 |
| TX seq+PRBS15; RX seq parse/verify | `range_test.cpp:144-151, 461-468` |
| PKT line fields (no ts/snr/bitErr) | `range_test.cpp:472-478` |
| CRC-err counted but per-packet invisible; lost conflates | `range_test.cpp:440-441, 373` |
| RP2040 PKT has uptime; V4 has unique/crc_err | `flrc_range_rx_v2.cpp:550-555`; `multi_radio_sweep_rx_v4.cpp:701` |
| LoRa vs FLRC status layouts | `lr20xx_radio_lora_types.h:298-312`; `lr20xx_radio_flrc_types.h:230-238`; opcodes `lr20xx_radio_flrc.c:73-77`, `lora_868_rx.cpp:172,192` |
| Garbage-RSSI history fixed | `docs/RSSI-FIX-PLAN.md` (RESOLVED 2026-07-23; 0x0104→0x024B; RSSI/SNR swap note `lora_868_rx.cpp:180-182`) |
| Split-CS contradiction | `multi_radio_sweep_rx_v4.cpp:410-412` vs `lora_868_rx.cpp:188-203` vs vendored `lr20xx_hal.c:144-170` |
| SPI actual < requested; clock not bottleneck | `docs/spi-frequency-sweep-results-2026-07-16.md` (≥12 MHz→12.0; 16 MHz fw ran 12 MHz; overhead is bottleneck); `SPI_FREQ_HZ 20000000UL` at `flrc_cont_rx.cpp:37` et al. |
| GDMA built-never-tested; blocking path in range fw | commits `3b70f8e`, `da0b113`; worktree `EspHalC3.h:128-190` |
| E80: no BER source; boolean verify; crc_err separate | `bench_payload.c:60-78`; `radio_bench.c:383-417, 829`; `bench_stats.h` |
| E80/RP2040 CSV = 19-col; C3 outlier | `tools/e80_bench_ctl.py` CSV_COLUMNS (via census); plan §HS-2 L124; `range_test.cpp:384-394` |
| FW-7 payload not PRBS | `~/host-driven-bench-plan.md` L59, L100, L104-106 |
| Jul-24 walk facts | `docs/MORNING-HANDOVER-V4.md:82`; `docs/WALK-TEST-FIX-PLAN.md` §2 + "What Worked" |
| Pipeline task coverage | `~/host-driven-bench-plan.md` L236 (B2), L238 (B4/BW-1), L244 (M4/FW-5b), L250 (HW-B3) |
