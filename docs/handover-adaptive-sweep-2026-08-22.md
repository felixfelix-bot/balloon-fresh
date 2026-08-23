# E80 Bench — Adaptive Sweep Plan + 2.4 GHz Campaign Handover

2026-08-22 · Felix's E80/STM32 FLRC+LoRa bench · prepared by Hermes (balloon-hermes)

This document supersedes the 2026-08-21 handover for the same recipient. It is
fully self-contained — no reference to prior conversations is needed. Every
file path is given as both a GitHub URL and a local repo path.

**Repo:** https://github.com/felixfelix-bot/balloon-fresh
**Branch:** `feat/2g4-sweep`
**Base URL for all paths:**
https://github.com/felixfelix-bot/balloon-fresh/tree/feat/2g4-sweep/

---

## 1. What's new since the last handover (2026-08-21)

| Item | Before (2026-08-21) | Now (2026-08-22) |
|------|---------------------|------------------|
| **Band coverage** | 868 MHz sub-GHz only | **Dual-band**: 863–870 MHz + 2400–2483.5 MHz ISM |
| **Firmware** | `88a00cf` (868-only, prbs15 + pcrc16) | **`0561b29`** (feat/2g4-sweep: BAND OVERRIDE + HF PA/RX path ≥ 1.6 GHz, console 2 Mbaud) |
| **Sweep configs** | 61 configs (868 MHz single-band) | **113 configs** (dual-band: 868 MHz full matrix + 2.4 GHz LoRa/FLRC matrix + 5 freq-probe points) |
| **Sweep status** | Complete (session 2608212001) | **Complete** (session 2608222108, 113 configs, 5650 pkts) |
| **STOP mid-burst** | Not tested | **Verified STOP-CLEAN** on both LoRa and FLRC (ADAPT-0 task) |
| **Adaptive plan** | Not yet written | **Written, operator-approved (D1–D6)**, ready for implementation |

### Key hardware/firmware changes

- **2.4 GHz is now real HF path data.** Firmware commit `0561b29` adds BAND
  OVERRIDE (RAM-resident, frequency range extended to 2483 MHz) and enables the
  HF PA/RX path on the LR2021-class module (≥ 1.6 GHz). The sweep tool sets
  `BAND OVERRIDE 2026` before 2.4 GHz configs and re-arms it after every SWD
  reset (reset kills the override — it is RAM-only).
- **Console baud raised to 2 Mbaud** for 2.4 GHz (FLRC at 2.6 Mbps produces
  back-to-back packets that overflow the 115200 baud UART buffer).
- **Both boards**: E80 (STM32F103 + LR2021-class module), TX/RX roles, SMA
  antennas ~30 cm apart. Same physical rig as before — bench environment, not
  range.

### Dual-band sweep headline numbers

- 113 configs × 50 pkts = 5650 packet rows total
- 868 MHz configs (0–87): LoRa SF5–12 BW125, FLRC all 8 bitrates, PA 0–10,
  LEN 64. Same matrix as the 868-only sweep, now re-run on the new firmware.
- 2.4 GHz configs (88–112): LoRa SF8 BW125 at 5 freq points {2400, 2420, 2440,
  2460, 2480} MHz; FLRC BR650/1300/2600 × PA {1,3,5,7,10} at 2440 MHz; LoRa
  SF{5,6,7} BW125 at 2440 MHz × PA {1,5,10}; LoRa SF{5,7,11} BW500 at 2440 MHz
  × PA {1,5,10}.
- **FLRC CRC still unreliable** on this firmware (same pre-Match123-fix issue).
  Use `bit_err` (PRBS-15) as the integrity signal — see §5 caveat 1.
- **2.4 GHz FLRC**: `crc_err=50` on every config (same chip-CRC issue); PRBS
  `bit_err_total=0` everywhere — payload integrity is perfect.

---

## 2. Adaptive sweep plan explained

**Plan document (read in full for details):**
- GitHub: https://github.com/felixfelix-bot/balloon-fresh/tree/feat/2g4-sweep/docs/plans/adaptive-sweep-plan-20260822.md
- Local: `docs/plans/adaptive-sweep-plan-20260822.md`

### Why adaptive?

Range tests are **operator-limited**: every minute at a distance point is
precious (setup + walk + battery). A FULL dual-band sweep takes ~75 min (113
configs × 50 pkts). The adaptive plan cuts per-stop time to **5–9 min** — a
**65–75% saving** — by testing fewer configs and fewer packets when the link
quality is clearly good or clearly dead.

FULL sweeps stay unchanged (baseline characterization, bench only). The
adaptive modes are additive — a new host-side tool `tools/e80_campaign.py`
that imports helpers from the existing `e80_sweep_full.py`. Zero firmware
changes.

### Modes

| Mode | Purpose | Configs | Pkts/config | When |
|------|---------|---------|-------------|------|
| **FULL** | Baseline characterization — UNCHANGED | 61 (868) / 113 (dual) | 50 fixed | bench, pre/post campaign |
| **CAMPAIGN-PROBE** | Link-state classification at a stop | 2 | SPRT ≤ 20 | every range stop, first thing |
| **CAMPAIGN-GOOD** | Throughput matrix (clean link) | ~25 | SPRT ≤ 20, reset-skip | probe verdict CLEAN |
| **CAMPAIGN-DEGRADED** | Robustness ladder + telemetry (poor link) | ~8 | SPRT ≤ 20 | probe verdict DEAD |
| **CLIFF-SEARCH** | Localize PER cliff on SF axis | ~5 probes | SPRT ≤ 20 | EDGE verdict, or core range deliverable |

### How the branching works (plain language)

1. **PROBE**: Two canary configs (LoRa SF7 BW125 + FLRC BR650, both LEN=51),
   ~1 min total. The controller classifies the link as CLEAN / DEAD / EDGE.
2. **If CLEAN** → run the throughput matrix (~25 fast configs, 4–6 min).
3. **If DEAD** → run the robustness ladder (~8 slow/robust configs, 4–5 min).
4. **If EDGE** → cliff-search first (binary search on SF5–12 axis to find the
   PER boundary, 2.5–3.5 min), then the degraded ladder.
5. **Anchors at every stop**: FLRC-650 + SF7 re-tested as tripwires (~40 s).
   If an anchor contradicts a carry-forward prediction → monotonicity violated
   → invalidate skips, retest affected configs.

### SPRT in plain language

> **Stop testing when you're statistically confident.**

Instead of always sending 50 packets per config, the controller uses a
Sequential Probability Ratio Test (SPRT) to decide after each packet whether
the link is clearly good (PER ≤ 2%) or clearly dead (PER ≥ 20%). Once
confident, it sends a `STOP` command to the TX board and moves to the next
config.

- **Clean link** (PER ≈ 0%): stops at 15 packets → **70% saving**.
- **Dead link** (PER ≈ 100%): stops at 10 packets → **80% saving**.
- **Gray zone** (PER 5–15%): runs to the tier cap (20 campaign / 50 full) → no
  saving, but this is honest — SPRT saves time only at the extremes, which is
  exactly the bench/range reality (configs are either 0/50 or 50/50).

Parameters: H₀: PER = 2%, H₁: PER = 20%, α = β = 0.05, n_min = 10, n_cap = 20.
Error indicator: `bit_err > 0` (PRBS-15 primary; `crc_ok` secondary only — chip
CRC unreliable for FLRC pre-fix).

### Operator decisions (resolved 2026-08-22, D1–D6)

| Decision | Resolution |
|----------|------------|
| **D1: STOP semantics** | YES — bench-verify fw STOP mid-burst abort. **Verified STOP-CLEAN** on both mods. No fallback needed. |
| **D2: Cliff edge precision** | Boundary cells VALIDATED AT n=50 (characterization-grade CIs; interior search stays SPRT ≤ 20). |
| **D3: Campaign bands** | DUAL-BAND stops (868 + 2.4 GHz). Skip-list prunes 2.4 GHz fast at range. |
| **D4: Walk order** | NOT guaranteed. Controller is symmetric — branch decision comes from probe verdicts, never from position. Carry-forward DB works both directions. |
| **D5: PA ramp** | KEPT unchanged (safety: PA0 → PA10 → PA22 only past 50m). SPRT applies per-cell. PA-22 cells always reset-guarded. |
| **D6: Anchor set** | APPROVED — FLRC-650 + SF7 every-stop tripwires (~40 s/stop). |

### STOP verify results (ADAPT-0)

- GitHub: https://github.com/felixfelix-bot/balloon-fresh/tree/feat/2g4-sweep/docs/plans/stop-verify-results.md
- Local: `docs/plans/stop-verify-results.md`

| Modulation | Verdict | Stray pkts after STOP | Burst stopped? | Re-ARM+START? |
|------------|---------|-----------------------|----------------|---------------|
| LoRa SF7 | **STOP-CLEAN** | 0 | YES (5/50) | YES (10/10) |
| FLRC 650k | **STOP-CLEAN** | 1 (in-flight, 2 ms airtime) | YES (15/50) | YES (10/10) |

The FLRC stray packet was already in the air when STOP was processed — a
fundamental radio timing artifact, not a firmware defect. The burst state
machine was fully stopped (state → BSTATE_IDLE, no further packets queued).

---

## 3. Artifacts index

All artifacts are on branch `feat/2g4-sweep`. Every path is shown as GitHub URL
+ local repo path.

### Plan documents

| Artifact | GitHub URL | Local path |
|----------|-----------|------------|
| Adaptive sweep plan (the plan) | https://github.com/felixfelix-bot/balloon-fresh/tree/feat/2g4-sweep/docs/plans/adaptive-sweep-plan-20260822.md | `docs/plans/adaptive-sweep-plan-20260822.md` |
| STOP verify results (ADAPT-0) | https://github.com/felixfelix-bot/balloon-fresh/tree/feat/2g4-sweep/docs/plans/stop-verify-results.md | `docs/plans/stop-verify-results.md` |
| Prior handover (2026-08-21, for reference) | https://github.com/felixfelix-bot/balloon-fresh/tree/feat/2g4-sweep/docs/handover-data-collaborator-2026-08-21.md | `docs/handover-data-collaborator-2026-08-21.md` |

### Dual-band sweep data (2026-08-22, session 2608222108, fw 0561b29, 113 configs)

| Artifact | GitHub URL | Local path |
|----------|-----------|------------|
| Session meta JSON | https://github.com/felixfelix-bot/balloon-fresh/tree/feat/2g4-sweep/full-sweep-results-2g4-meta-20260822-210817.json | `full-sweep-results-2g4-meta-20260822-210817.json` |
| Per-config summary CSV (113 rows + header) | https://github.com/felixfelix-bot/balloon-fresh/tree/feat/2g4-sweep/full-sweep-results-2g4-summary-20260822-210817.csv | `full-sweep-results-2g4-summary-20260822-210817.csv` |
| Per-packet CSV (~5650 rows) | https://github.com/felixfelix-bot/balloon-fresh/tree/feat/2g4-sweep/full-sweep-results-2g4-pkts-20260822-210817.csv | `full-sweep-results-2g4-pkts-20260822-210817.csv` |
| Analysis report (read first) | https://github.com/felixfelix-bot/balloon-fresh/tree/feat/2g4-sweep/full-sweep-results-2g4-report-20260822-210817.md | `full-sweep-results-2g4-report-20260822-210817.md` |

### Prior 868 MHz sweep data (2026-08-21, session 2608212001, fw 88a00cf, 61 configs)

| Artifact | GitHub URL | Local path |
|----------|-----------|------------|
| Session meta JSON | https://github.com/felixfelix-bot/balloon-fresh/tree/feat/2g4-sweep/full-sweep-meta-20260821-200111.json | `full-sweep-meta-20260821-200111.json` |
| Per-config summary CSV (61 rows + header) | https://github.com/felixfelix-bot/balloon-fresh/tree/feat/2g4-sweep/full-sweep-summary-20260821-200111.csv | `full-sweep-summary-20260821-200111.csv` |
| Per-packet CSV (~3050 rows) | https://github.com/felixfelix-bot/balloon-fresh/tree/feat/2g4-sweep/full-sweep-pkts-20260821-200111.csv | `full-sweep-pkts-20260821-200111.csv` |

### Sweep tool source

| Artifact | GitHub URL | Local path |
|----------|-----------|------------|
| Sweep orchestrator (current) | https://github.com/felixfelix-bot/balloon-fresh/tree/feat/2g4-sweep/firmware/e80-stm32-bench/tools/e80_sweep_full.py | `firmware/e80-stm32-bench/tools/e80_sweep_full.py` |
| STOP verify script | https://github.com/felixfelix-bot/balloon-fresh/tree/feat/2g4-sweep/firmware/e80-stm32-bench/tools/stop_verify.py | `firmware/e80-stm32-bench/tools/stop_verify.py` |
| Firmware source (protocol reference) | https://github.com/felixfelix-bot/balloon-fresh/tree/feat/2g4-sweep/firmware/e80-stm32-bench/src/ | `firmware/e80-stm32-bench/src/` |

> **Note:** The adaptive campaign tool `tools/e80_campaign.py` does not exist
> yet — it is the next implementation step described in the plan. It will be a
> sibling to `e80_sweep_full.py` in the same `tools/` directory.

---

## 4. Data schemas

### 4.1 Per-packet CSV (current — verified against actual file headers)

One row per received packet. **12 columns:**

| # | Column | Type | Description |
|---|--------|------|-------------|
| 1 | `idx` | int | Config index (0–112 in dual-band; 0–60 in 868-only) |
| 2 | `label` | string | Human config id, e.g. `SF7 BW125 PA10`, `FLRC 650k pa5 L511`, `2G4 SF8 BW125 @ 2440MHz` |
| 3 | `pkt_idx` | int | Packet sequence number within the burst (dedupe key; join with `session` + `config`) |
| 4 | `session` | int | Session id (e.g. `2608222108` = 2026-08-22 21:08) |
| 5 | `config` | int | Config index within session (matches `idx` in summary CSV) |
| 6 | `replicate` | int | Replicate number (always `1` in current sweeps) |
| 7 | `ts_ms` | int | Host-receive timestamp in ms (basis of throughput calculations) |
| 8 | `rssi_dbm` | float | Per-packet RSSI (see caveat 2 for FLRC LEN ≥ 255 step) |
| 9 | `snr_db` | float | LoRa SNR; **0.0 in FLRC by design** (chip exposes no FLRC SNR) |
| 10 | `crc_ok` | int (0/1) | Chip-hardware CRC verdict — **unreliable in FLRC** pre-fix (see caveat 1) |
| 11 | `bit_err` | int | PRBS-15 payload bit-error count — **THE reliable integrity signal** |
| 12 | `pcrc16` | int | App-layer CRC16 of received payload; populated only when chip CRC passed (0 otherwise — see caveat 3) |

### 4.2 Per-config summary CSV (current — verified against actual file headers)

One row per config. **21 columns:**

| # | Column | Type | Description |
|---|--------|------|-------------|
| 1 | `idx` | int | Config index |
| 2 | `label` | string | Human config id |
| 3 | `mod` | string | Modulation: `lora` or `flrc` |
| 4 | `sf` | int/empty | LoRa spreading factor (5–12); empty for FLRC |
| 5 | `bw` | int/empty | LoRa bandwidth (125, 500); empty for FLRC |
| 6 | `br` | int/empty | FLRC bitrate (260–2600); empty for LoRa |
| 7 | `pa` | int | PA setting in dBm (0, 1, 3, 5, 7, 10, 22) |
| 8 | `freq` | int | Frequency in Hz (e.g. `868000000`, `2440000000`) |
| 9 | `plen` | int | Payload length in bytes (64, 128, 255, 511, etc.) |
| 10 | `gap_us` | int | Inter-packet gap in microseconds (adaptive: 1.2 × ToA + 5 ms for LoRa; 10000 for FLRC) |
| 11 | `toa_s` | float | Computed time-on-air in seconds |
| 12 | `rx_pkts` | int | Number of packets received (compare to 50 for delivery rate) |
| 13 | `crc_err` | int | Count of packets with chip CRC failure (**unreliable for FLRC** — see caveat 1) |
| 14 | `rssi_avg` | float | Mean RSSI across received packets |
| 15 | `rssi_min` | float | Minimum RSSI |
| 16 | `rssi_max` | float | Maximum RSSI |
| 17 | `snr_avg` | float | Mean SNR (LoRa only; 0.0 for FLRC) |
| 18 | `snr_min` | float | Minimum SNR (LoRa only; 0.0 for FLRC) |
| 19 | `bit_err_total` | int | Sum of PRBS-15 bit errors across all received packets — **THE reliable integrity signal** |
| 20 | `tx_done` | string | `True`/`False` — whether TX board reported burst completion |
| 21 | `error` | string | Error message if config failed (empty = success) |

### 4.3 Session meta JSON (current — verified against actual file)

```json
{
  "session": 2608222108,
  "started": "2026-08-22T21:08:17.303439",
  "operator": "Felix",
  "rig": "e80-stm32",
  "env": "bench",
  "fw_flashed_on_boards": "0561b29 (feat/2g4-sweep: BAND OVERRIDE + HF path, console 2 Mbaud)",
  "fw_source_commit": "",
  "tx": { "hw": "E80 STM32F103 + LR2021-class module", "port": "/dev/ttyUSB3" },
  "rx": { "hw": "E80 STM32F103 + LR2021-class module", "port": "/dev/ttyUSB4" },
  "band": "dual-band: 863-870 MHz + 2400-2483.5 MHz ISM (BAND OVERRIDE 2026, HF path >= 1.6 GHz)",
  "antennas": "SMA, ~30 cm apart",
  "packets_per_config": 50,
  "integrity_note": "pre-Match123-fix fw: trust bit_err (PRBS-15), not crc_ok, for FLRC"
}
```

### 4.4 Upcoming schema changes (adaptive campaign — not yet implemented)

These changes are planned for the `tools/e80_campaign.py` implementation. They
will appear in campaign-mode CSVs only; FULL sweep CSVs remain unchanged unless
noted.

**Change 1: `mode=` column on every row (both PKT and summary CSVs)**

A new column `mode` will be added to both the per-packet and per-config summary
CSVs, indicating which adaptive mode produced the row:

| Value | Meaning |
|-------|---------|
| `FULL` | Full 50-pkt characterization (existing sweeps) |
| `PROBE` | CAMPAIGN-PROBE (2 canary configs, SPRT ≤ 20) |
| `GOOD` | CAMPAIGN-GOOD (throughput matrix, clean link) |
| `DEGRADED` | CAMPAIGN-DEGRADED (robustness ladder, poor link) |
| `CLIFF` | CLIFF-SEARCH (PER cliff localization on SF axis) |
| `ANCHOR` | Anchor config at every stop (FLRC-650 + SF7 tripwires) |

**Change 2: New `configs.csv` sidecar file**

A new per-config metadata file with wall-clock timing:

| Column | Type | Description |
|--------|------|-------------|
| `idx` | int | Config index |
| `label` | string | Human config id |
| `t_start` | string | ISO timestamp when config started |
| `t_end` | string | ISO timestamp when config ended |
| `dur_s` | float | Wall-clock duration in seconds (includes reset + reconfig + burst) |
| `rxcnt` | int | Packets received (may be < 50 if SPRT early-stopped) |

**Change 3: Meta JSON gains timing fields**

The session meta JSON will gain three new fields:

| Field | Type | Description |
|-------|------|-------------|
| `started` | string | ISO timestamp (already present) |
| `finished` | string | ISO timestamp when sweep completed |
| `total_elapsed_s` | float | Total wall-clock time for the entire sweep |

> **These changes are not yet in any committed file.** They are the next
> implementation step. See §6 for feedback requests on these schema changes.

---

## 5. Known quirks (carried forward + 2.4 GHz additions)

These quirks apply to ALL datasets on this firmware (`88a00cf` for 868-only,
`0561b29` for dual-band). They are reproducible, documented, and do not
invalidate the data — but you must account for them in analysis.

| # | Quirk | Impact | Workaround |
|---|-------|--------|------------|
| 1 | **FLRC `crc_ok` unreliable (pre-Match123-fix)** | Chip-hardware CRC verdict is wrong for FLRC: most FLRC rows show `crc_err=50` despite PRBS `bit_err=0`. Root cause: RX sync-match mode Match1 (fix under review). | **Use `bit_err` (PRBS-15) as the integrity signal.** Ignore `crc_ok` / `crc_err` for FLRC on this firmware. |
| 2 | **SNR = 0.0 in FLRC (by design)** | The chip exposes no FLRC SNR in its API. Every FLRC row has `snr_db=0.0` / `snr_avg=0.0`. | Filter FLRC rows out of SNR analysis. Do not interpret 0.0 as "no signal." |
| 3 | **RSSI +31.9 dB step at LEN ≥ 255 (FLRC)** | FLRC RSSI jumps ~+32 dB when payload length ≥ 255 bytes (e.g. −71 → −39 dBm regime). Reproducible across datasets. | Compare RSSI only within one regime (LEN < 255 vs LEN ≥ 255). Do not cross-compare. |
| 4 | **LoRa LEN > 255 unsupported** | The firmware caps LoRa payload at 255 bytes. FLRC caps at 511. | LoRa rows with LEN > 255 do not exist by design. |
| 5 | **Dedupe on `pkt_idx`** | Some configs have 51/50 rows (one stray duplicate from buffer leftover). | Deduplicate on `pkt_idx` within each `session` + `config` pair. |
| 6 | **2.4 GHz is now real HF path data** | Prior sweeps were 868 MHz only. The dual-band sweep (session 2608222108) includes 2.4 GHz configs with real HF PA/RX path data via BAND OVERRIDE. | 868 MHz and 2.4 GHz are **independent ladders** — never carry a verdict across bands. RSSI/SNR absolute values are not comparable across bands. |

---

## 6. Feedback requested

We need your input on five items before implementing the adaptive campaign
tool. Please relay through Felix.

### (a) Schema compatibility

The upcoming schema changes (§4.4) will add:
- A `mode=` column to every row in both PKT and summary CSVs.
- A new `configs.csv` sidecar file with `idx, label, t_start, t_end, dur_s, rxcnt`.
- New `finished` and `total_elapsed_s` fields in the meta JSON.

**Questions:**
1. Will the `mode=` column break Bloons ingestion? (It's appended after the
   existing columns — does your parser tolerate extra trailing columns, or do
   you need us to insert it in a specific position?)
2. Will the new `configs.csv` file require explicit ingestion config, or will
   Bloons auto-detect it alongside the existing summary/pkts pair?
3. For `dur_s` (wall-clock per-config duration): is this useful for your
   dashboards, or noise?
4. For configs skipped via carry-forward (DEAD at a farther distance → not
   retested closer): what format do you prefer for the skipped row? Options:
   (i) omit the row entirely, (ii) include the row with `rx_pkts=0` and a
   `skipped=` annotation column, (iii) copy the prior verdict with a
   `carry_forward_from=` column. What works best for Bloons?

### (b) SPRT verdicts + Wilson CIs vs your aggregates

The adaptive controller produces per-config verdicts (CLEAN / DEAD / EDGE)
with Wilson 95% CIs on the stopped sample. For example: "SF7 BW125 at 500 m:
CLEAN, k=0, n=15, Wilson CI [0%, 20.4%]."

**Questions:**
1. Does Bloons want only the raw PKT streams (as today), or also a verdict
   summary file (e.g. `campaign-verdicts.csv` with `stop_id, config_idx,
   label, verdict, k, n, ci_lo, ci_hi`)?
2. If both: how should Bloons reconcile SPRT-stopped samples (n=10–20) with
   your existing aggregation logic that may assume n=50? Would a `n_pkts`
   column in the summary CSV suffice, or do you need a separate flag?

### (c) Range campaign data shape

The range campaign will add per-stop metadata that doesn't exist in bench
sweeps. Proposed fields:

| Field | Type | Description |
|-------|------|-------------|
| `stop_id` | string | Unique stop identifier (e.g. `S0`, `S1`, ... `S7`) |
| `distance_m` | float | Distance between TX and RX antennas in meters |
| `gps_lat` | float | GPS latitude of RX position (if available) |
| `gps_lon` | float | GPS longitude of RX position (if available) |

**Questions:**
1. Are these fields sufficient for Bloons dashboards, or do you need more
   (e.g. `bearing_deg`, `tx_gps_lat/lon`, `environment` tag)?
2. Where should these live — in the meta JSON, a separate `stops.csv`, or
   as columns on every PKT/summary row?
3. Does Bloons have existing geospatial visualization (map view), or would
   `distance_m` alone suffice?

### (d) Timing data usefulness

The upcoming `configs.csv` will carry `dur_s` (wall-clock duration per config)
and the meta JSON will carry `total_elapsed_s`. The plan also has per-mode
time budget estimates.

**Question:** Is wall-clock timing data useful for your analysis, or is it
purely operational? Would you want it joined to per-config results, or kept
in a separate sidecar?

### (e) Early-stop = fewer pkts per config — data quality concerns

SPRT early-stop means some configs will have n=10–20 packets instead of 50.
The plan's §5 Wilson CI table shows the trade-off:

| n | k | p̂ | Wilson 95% CI | Context |
|---|---|---|---------------|---------|
| 50 | 0 | 0% | [0%, 7.1%] | FULL characterization |
| 20 | 0 | 0% | [0%, 16.1%] | Campaign clean claim (classification) |
| 15 | 0 | 0% | [0%, 20.4%] | SPRT clean stop point |
| 10 | 10 | 100% | [72.3%, 100%] | SPRT dead stop point |

**Questions:**
1. Does Bloons have minimum-n thresholds for ingestion or display? Would
   n=15 CLEAN or n=10 DEAD rows be flagged or filtered?
2. For cliff-search boundary cells, the plan validates at n=50 (FULL tier).
   Is that sufficient for your aggregates, or do you need n=50 on all
   "interesting" configs?
3. Any concern with mixing SPRT-stopped and FULL-tier rows in the same CSV
   (distinguished only by the `mode=` column)?

---

## 7. How to reproduce

### Clone and checkout

```bash
git clone https://github.com/felixfelix-bot/balloon-fresh.git
cd balloon-fresh
git checkout feat/2g4-sweep
```

### Key file list (verify after checkout)

| File | Purpose |
|------|---------|
| `docs/plans/adaptive-sweep-plan-20260822.md` | The adaptive sweep plan (modes, SPRT, controller pseudocode, operator decisions D1–D6) |
| `docs/plans/stop-verify-results.md` | STOP mid-burst abort verification results (ADAPT-0, VERDICT: STOP-CLEAN both mods) |
| `full-sweep-results-2g4-meta-20260822-210817.json` | Dual-band sweep session meta (fw 0561b29, 113 configs) |
| `full-sweep-results-2g4-summary-20260822-210817.csv` | Per-config summary (113 rows + header) |
| `full-sweep-results-2g4-pkts-20260822-210817.csv` | Per-packet rows (~5650 rows) |
| `full-sweep-results-2g4-report-20260822-210817.md` | Analysis report for the dual-band sweep |
| `full-sweep-meta-20260821-200111.json` | Prior 868-only sweep session meta (fw 88a00cf, 61 configs) |
| `full-sweep-summary-20260821-200111.csv` | Prior 868-only per-config summary (61 rows + header) |
| `full-sweep-pkts-20260821-200111.csv` | Prior 868-only per-packet rows (~3050 rows) |
| `firmware/e80-stm32-bench/tools/e80_sweep_full.py` | The sweep orchestrator (auto port detect, role handshake, adaptive gap, PRBS verify, CSV/MD emission) |
| `firmware/e80-stm32-bench/tools/stop_verify.py` | STOP verify test script |
| `firmware/e80-stm32-bench/src/` | Firmware source (console `bench_cmd.c`, `prbs.c`, `bench_pkt.c` — the protocol reference) |

### Running a sweep (requires hardware)

The sweep tool requires two E80 boards connected via CH340 USB-UART. Full
instructions are in the tool source header. Quick reference:

```bash
cd firmware/e80-stm32-bench/tools/
python3 e80_sweep_full.py --help          # see all options
python3 e80_sweep_full.py                 # full dual-band sweep (113 configs, ~75 min)
python3 e80_sweep_full.py --only "2G4"    # 2.4 GHz configs only
python3 e80_sweep_full.py --only "k pa5"  # FLRC with PA=5 subset
```

The tool auto-detects CH340 ports, performs a radio handshake ID, and emits
the exact CSV/MD/JSON formats documented in §4.

### Commit history for this branch

```
e2db77c feat(sweep): wall-clock timing — per-config dur_s, configs.csv, meta started/finished/elapsed, planning formulas
a7e8677 feat(sweep): 2.4 GHz dual-band sweep — 5 freq points + full LoRa/FLRC matrix at 2440 MHz
f318371 docs(plan): adaptive/time-optimal sweep modes — SPRT early-stop, branch controller, cliff-search, carry-forward (operator-approved D1-D6)
0561b29 feat(fw): 2.4 GHz band support — HF PA/RX path + override range to 2483 MHz
ec1fb09 feat(sweep): emit session-meta sidecar JSON (operator/fw/HW/ports) for downstream tooling
```

Full history: https://github.com/felixfelix-bot/balloon-fresh/commits/feat/2g4-sweep

---

## Provenance

Every file above is on branch `feat/2g4-sweep`. Raw per-packet CSVs are the
ground truth; reports are derived. The adaptive plan is operator-approved (D1–D6
resolved 2026-08-22) but the campaign tool (`e80_campaign.py`) is not yet
implemented — schema changes in §4.4 are proposed, not final.

Ask Felix to relay analysis requests or feedback — we can rerun any config
subset on demand and will adjust schemas based on your input in §6.