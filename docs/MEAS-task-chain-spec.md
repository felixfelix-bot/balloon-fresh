# MEAS Task Chain — First RF Measurement with Harmonized Firmware

> **Created:** 2026-08-20
> **Author:** Manager (balloon-range-tests)
> **Status:** Ready for kanban creation
> **Predecessor:** INT-1 (t_0a18531a) — format compliance checklist

---

## Chain Overview

```
INT-1 (exists) → MEAS-1 → MEAS-2
  ✅ Done?      ⚠️ Op    🤖 Auto
```

| Task | Type | Operator Gate | Worker | Est. Time |
|------|------|---------------|--------|-----------|
| INT-1 | Format compliance checklist | YES (Felix at bench) | Manager | 30m–2h |
| **MEAS-1** | **Range test capture at 3 distances** | **YES (Felix at bench)** | **worker-balloon** | **20m capture + 10m setup = 30m** |
| **MEAS-2** | **Analyze CSV + generate summary + surface to Felix** | **NO — fully automated** | **worker-admin** | **15m** |

**Total chain wall time:** ~45 minutes (after INT-1 is complete and Felix is at the bench).

---

## MEAS-1: Range Test Capture at 3 Distances

### Title
```
[WAVE-5] MEAS-1: Range test capture — E80 rig, 3 distances, harmonized 23-field output
```

### Labels
`firmware-harmonization`, `wave-5`, `measurement`, `worker-balloon`, `operator-gate`

### Assignee
worker-balloon

### Repo
`~/repos/balloon-fresh/` (capture tools) + `~/repos/balloon-e80bench/` (E80 firmware)

### Branch
`feat/e80-stm32-bench` (E80) / `harmonization` (balloon-fresh tools)

### Objective

Record the first RF measurement using the fully harmonized 23-field per-packet output format on the E80 rig (STM32F103C8T6 + LR2021). The measurement is a **range test at three fixed distances** to characterize RSSI degradation and packet error rate as a function of TX-RX separation.

**Why this measurement:** The first measurement with harmonized firmware should answer Felix's most pressing question: *does the harmonized output pipeline produce valid, realistic RF data end-to-end?* A range test at 3 distances simultaneously validates every field in the 23-field format AND produces the RSSI-vs-distance curve that's the foundational data point for balloon mission link budget planning.

**Measurement parameters:**
- **Rig:** E80 (STM32F103C8T6 + LR2021, 2.4 GHz, FLRC mode)
- **Distances:** 1 m (near-field reference), 10 m (mid-range), 30 m (far-field, outdoor LOS)
- **Duration per distance:** 60 seconds (~180–570 packets per distance at 3–9.5 pkt/s FLRC)
- **Total capture:** ~3 minutes of active RF + setup/walk time between distances
- **Environment:** `outdoor_los` (parking lot, clear line of sight)
- **Modulation:** FLRC, BW=200 kHz, CR=3/4 (default E80 config)
- **Power:** +10 dBm (default)
- **Packet size:** 64 bytes (default)

### Dependencies

- **INT-1** (t_0a18531a) — MUST be in `done` status. INT-1 validates all 15 format compliance items (23 fields, session_id, CONFIG_START, FW_HASH, monotonic seq, realistic RSSI, CRC-failed PKT lines, 2 Mbps UART reliability). MEAS-1 captures real RF data, which is meaningless if the format is broken.
- **All Phase 1 tasks** (E80-1..8, C3-1..5, HOST-1..4) — implicitly complete since INT-1 depends on all of them.

### Pre-conditions (Felix at bench — operator gate)

Felix must perform the following physical actions before the worker can start the automated capture:

| # | Action | Hardware | Verification |
|---|--------|----------|-------------|
| 1 | Flash E80 firmware (TX + RX boards) with latest harmonized build | STM32F103C8T6 via SWD/serial | Boot banner shows `FW_HASH=<7hexchars>` |
| 2 | Connect E80 RX board to host laptop via CH340 USB-serial | E80 rig + CH340 | `/dev/ttyACM0` or `/dev/ttyUSB0` appears |
| 3 | Place TX board at **1 m** from RX antenna, clear LOS | E80 TX + antenna | Visual confirmation |
| 4 | Power on TX board (battery or USB), confirm TX LED blinking | E80 TX | TX is actively transmitting |
| 5 | Confirm RX board booted and is outputting PKT lines | E80 RX via serial monitor | `PKT,...` lines visible in serial monitor |
| 6 | Post `HARDWARE_READY` confirmation to the kanban task comment | — | Worker polls for this signal |

> **R7 does not apply** (E80 is single-architecture, no TX/RX version mismatch risk). This is E80-only; C3 and RP2040 rigs are NOT part of MEAS-1.

### Automated steps (worker-balloon, after Felix confirms hardware ready)

Once Felix posts `HARDWARE_READY` to the task comment, the worker executes.

**Primary tool: `tools/fw_harm_measurement.py`** — This tool already exists and is purpose-built for harmonized measurements. It handles FW_HASH gate, session_id generation, PKT capture, 23-field validation, CRC/RSSI/seq stats, and generates both JSON and human-readable reports. It supports `--rig e80` (auto-selects 2 Mbps baud).

**Secondary tool: `tools/capture_sweep.py`** — Used for the raw CSV capture with distance/env metadata columns (for the range-test comparison). Produces structured CSV with `distance_m` and `environment` columns.

```bash
cd ~/repos/balloon-fresh

# ── Step 1: Capture at 1 m (near-field reference) ──
# Felix places TX at 1m, confirms placement
python3 tools/fw_harm_measurement.py --port /dev/ttyACM0 --rig e80 \
  --duration 60 --output data/meas-1/report_1m.txt
python3 tools/capture_sweep.py --port /dev/ttyACM0 --distance 1 \
  --env outdoor_los --duration 60 --out data/meas-1/ \
  --notes "MEAS-1 distance=1m near-field reference"

# ── Step 2: Capture at 10 m (mid-range) ──
# Worker posts to task: "Felix: move TX to 10m and reply READY"
# After Felix confirms:
python3 tools/fw_harm_measurement.py --port /dev/ttyACM0 --rig e80 \
  --duration 60 --output data/meas-1/report_10m.txt
python3 tools/capture_sweep.py --port /dev/ttyACM0 --distance 10 \
  --env outdoor_los --duration 60 --out data/meas-1/ \
  --notes "MEAS-1 distance=10m mid-range"

# ── Step 3: Capture at 30 m (far-field) ──
# Worker posts to task: "Felix: move TX to 30m and reply READY"
# After Felix confirms:
python3 tools/fw_harm_measurement.py --port /dev/ttyACM0 --rig e80 \
  --duration 60 --output data/meas-1/report_30m.txt
python3 tools/capture_sweep.py --port /dev/ttyACM0 --distance 30 \
  --env outdoor_los --duration 60 --out data/meas-1/ \
  --notes "MEAS-1 distance=30m far-field"
```

**Worker pauses between captures** to let Felix reposition TX. Each pause is an operator sub-gate: worker posts "Move TX to <distance>m and reply READY", waits for Felix's confirmation, then runs the next capture.

**Why both tools:** `fw_harm_measurement.py` produces the per-capture stats report (CRC, RSSI, seq continuity, field count validation) and JSON output. `capture_sweep.py` produces the structured CSV with distance/env columns for cross-distance comparison and future plotting via `plot_range_sweep.py`. Both write to the same `data/meas-1/` directory.

**Note on `fw_harm_measurement.py`:** The tool already handles FW_HASH gate validation (refuses to start without valid hash), session_id generation/injection, 23-field validation, and outputs JSON to stdout + human-readable report to `--output` file. It does NOT support `--distance` or `--env` (hence the parallel `capture_sweep.py` run). A future enhancement could add distance/env metadata to `fw_harm_measurement.py` to eliminate the dual-tool approach.

### Output files

```
data/meas-1/
├── report_1m.txt                  # fw_harm_measurement.py report @ 1m (human-readable + JSON)
├── report_10m.txt                 # fw_harm_measurement.py report @ 10m
├── report_30m.txt                 # fw_harm_measurement.py report @ 30m
├── sweep_capture_<ts1>.csv       # capture_sweep.py CSV @ 1m (23-field + distance/env)
├── sweep_capture_<ts1>.raw       # capture_sweep.py raw serial @ 1m
├── sweep_capture_<ts2>.csv       # capture_sweep.py CSV @ 10m
├── sweep_capture_<ts2>.raw       # capture_sweep.py raw serial @ 10m
├── sweep_capture_<ts3>.csv       # capture_sweep.py CSV @ 30m
├── sweep_capture_<ts3>.raw       # capture_sweep.py raw serial @ 30m
└── meas-1-metadata.json          # Session metadata (rig, distances, timestamps, firmware hash)
```

The worker writes `meas-1-metadata.json` after all captures complete:
```json
{
  "task": "MEAS-1",
  "rig": "E80",
  "firmware_hash": "<from boot banner>",
  "session_ids": ["<uuid1>", "<uuid2>", "<uuid3>"],
  "distances_m": [1, 10, 30],
  "environment": "outdoor_los",
  "duration_per_distance_s": 60,
  "capture_tools": ["fw_harm_measurement.py", "capture_sweep.py"],
  "timestamp_start": "<ISO8601>",
  "timestamp_end": "<ISO8601>"
}
```

### Quality gates

| Gate | Check | Pass criteria |
|------|-------|---------------|
| QG-1 | Firmware hash gate | `fw_harm_measurement.py` reports valid FW_HASH (no `--skip-fw-check` used) |
| QG-2 | Packet count | ≥ 50 PKT lines per distance (at 3 pkt/s × 60s = 180 min expected) |
| QG-3 | 23-field completeness | Every PKT line has exactly 23 fields after `PKT,` prefix (no parse failures) |
| QG-4 | RSSI realism | rssi_dbm in range [-150, -10] for all packets; no phantom values (0, 36, -127) |
| QG-5 | RSSI distance correlation | Mean RSSI at 30m < mean RSSI at 1m (expected: signal attenuates with distance) |
| QG-6 | seq monotonicity | seq values are monotonically increasing within each session (no resets) |
| QG-7 | CRC failures at far distance | ≥ 1 `crc_ok=0` PKT line in 30m capture (validates CRC logging path E80-7) |
| QG-8 | Session ID present | Every PKT line has non-empty session_id field |
| QG-9 | CONFIG_START present | ≥ 1 CONFIG_START marker in raw output (validates E80-8) |
| QG-10 | No data loss at 2 Mbps | Raw line count ≈ CSV PKT line count (no dropped lines at 2 Mbps UART) |

If any gate fails, the worker creates a bug ticket referencing the specific gate and escalates to Felix.

### Est. time
- Felix setup (flash + position): 10 min
- 3 × 60s captures + 2 × reposition walks: 20 min
- Worker validation + metadata: 5 min
- **Total: ~35 min** (wall time, including operator gate waits)

### Risk notes
- **R1 (IWDG):** Already validated in INT-1. If IWDG fires during 60s capture, E80 resets — worker will see boot banner in raw output and can detect it.
- **R5 (baud):** Already validated in INT-1. 2 Mbps is the production rate.
- **Weather dependency:** Outdoor LOS requires clear weather. If raining, fallback to indoor LOS at reduced distances (1m, 5m, 15m) — note in metadata.

---

## MEAS-2: Analyze + Surface Results to Felix

### Title
```
[WAVE-5] MEAS-2: Analyze MEAS-1 capture data + generate summary report for Felix
```

### Labels
`firmware-harmonization`, `wave-5`, `measurement`, `worker-admin`, `automated`

### Assignee
worker-admin

### Repo
`~/repos/balloon-fresh/`

### Branch
`harmonization` (same repo, tools/scripts)

### Objective

Parse the three capture datasets produced by MEAS-1 (both `fw_harm_measurement.py` JSON reports and `capture_sweep.py` CSV files), synthesize a cross-distance comparison summary report, write it to a markdown file, and surface it to Felix via Signal message.

### Dependencies

- **MEAS-1** — MUST be in `done` status with all quality gates passed. MEAS-2 analyzes the data that MEAS-1 captures.

### Pre-conditions

- `data/meas-1/` directory exists with:
  - 3 `report_<distance>m.txt` files (from `fw_harm_measurement.py`)
  - 3 `sweep_capture_<ts>.csv` files (from `capture_sweep.py`)
  - `meas-1-metadata.json` (from MEAS-1 worker)
- All MEAS-1 quality gates passed (QG-1 through QG-10)

**No operator gate.** This task is fully automated — no Felix at bench required.

### Automated steps (worker-admin)

```bash
cd ~/repos/balloon-fresh

# ── Step 1: Collect per-distance JSON stats from fw_harm_measurement.py output ──
# Each fw_harm_measurement.py run outputs JSON to stdout — worker captures it
# from the task logs or re-parses the .txt report files.
# The JSON contains: total_packets, crc.ok_count, crc.fail_count, rssi.min/max/mean/std,
# seq_continuity.gaps, seq_continuity.duplicates, field_count_ok, config_ids, mod_types

# ── Step 2: Generate cross-distance comparison ──
# Worker creates a synthesis script tools/synthesize_meas_report.py that:
#   1. Reads the 3 JSON outputs from fw_harm_measurement.py runs
#   2. Reads the 3 CSV files from capture_sweep.py for distance/env metadata
#   3. Builds the per-distance comparison table
#   4. Checks quality gates (RSSI correlation, CRC at far distance, etc.)
#   5. Writes docs/MEAS-1-report.md and data/meas-1/analysis_summary.json

python3 tools/synthesize_meas_report.py \
  --data-dir data/meas-1/ \
  --output-md docs/MEAS-1-report.md \
  --output-json data/meas-1/analysis_summary.json

# ── Step 3: Validate report exists and is non-empty ──
test -s docs/MEAS-1-report.md || { echo "ERROR: Report is empty"; exit 1; }

# ── Step 4: Surface to Felix via Signal ──
# Worker posts summary to balloon-range-tests Signal group
# (or writes to docs/MEAS-1-report.md and commits + pushes)
```

### Analysis script spec (`tools/synthesize_meas_report.py`)

The worker creates a new synthesis script (reusing existing `pkt_parser.py` for CSV parsing and `fw_harm_measurement.py`'s `compute_stats()` for statistics). It does NOT duplicate capture logic — it only synthesizes the already-captured data.

**Per-distance statistics table:**

| Distance | Packets | Mean RSSI (dBm) | RSSI Std | PER (%) | CRC Failures | CRC Rate (%) | Throughput (pkt/s) |
|----------|---------|-----------------|----------|---------|--------------|--------------|--------------------|
| 1 m      | 180     | -42             | 2.1      | 0.0     | 0            | 0.0          | 3.0                |
| 10 m     | 175     | -67             | 3.5      | 2.8     | 5            | 2.9          | 2.9                |
| 30 m     | 142     | -89             | 5.2      | 21.1    | 38           | 26.8         | 2.4                |

**Summary report sections:**

1. **Header:** Task ID, date, rig, firmware hash, environment
2. **Per-distance table** (above)
3. **RSSI vs. Distance chart** (ASCII or note to generate plot later via `plot_range_sweep.py`)
4. **Quality gate pass/fail summary** (all 10 gates from MEAS-1)
5. **Key findings:**
   - RSSI at 1m (near-field reference) → baseline sensitivity
   - RSSI delta 1m→30m → path loss exponent estimate
   - PER at 30m → link margin for balloon mission
   - CRC failure logging verified (E80-7 validated under real RF)
   - Harmonized 23-field format verified end-to-end (all fields populated, parseable, meaningful)
6. **Anomalies** (phantom RSSI, IWDG resets, UART data loss — should be none if gates passed)
7. **Recommendation:** Next measurement (e.g., C3 rig cross-validation, SF/BW sweep, longer distance)

### Output files

```
docs/MEAS-1-report.md                      # Human-readable summary report (markdown)
tools/synthesize_meas_report.py            # Synthesis script (committed + pushed)
data/meas-1/analysis_summary.json          # Machine-readable stats (for future comparison)
```

**Signal message to Felix** (posted by worker to balloon-range-tests group):

```
📊 MEAS-1 COMPLETE — E80 Range Test Results

Rig: E80 (STM32F103 + LR2021, FLRC 2.4 GHz)
Environment: outdoor_los
Firmware: FW_HASH=xxxxxxx

Distance | Packets | Mean RSSI | PER    | CRC Fail
---------|---------|-----------|--------|----------
1 m      | 180     | -42 dBm   | 0.0%   | 0
10 m     | 175     | -67 dBm   | 2.8%   | 5
30 m     | 142     | -89 dBm   | 21.1%  | 38

✅ All 10 quality gates passed
✅ 23-field harmonized format verified end-to-end
✅ CRC-failed packet logging working (E80-7)
✅ 2 Mbps UART no data loss (R1 validated)

Full report: docs/MEAS-1-report.md
Raw data: data/meas-1/

Next steps: C3 rig cross-validation (MEAS-3) or SF/BW sweep (MEAS-4)?
```

### Quality gates

| Gate | Check | Pass criteria |
|------|-------|---------------|
| QG-1 | Report exists | `docs/MEAS-1-report.md` is non-empty, valid markdown |
| QG-2 | All distances analyzed | Report contains stats for all 3 distances (1m, 10m, 30m) |
| QG-3 | RSSI correlation | Report notes whether RSSI decreases with distance (sanity check) |
| QG-4 | CRC analysis | Report includes CRC failure count and rate per distance |
| QG-5 | Gate summary | Report includes pass/fail for all 10 MEAS-1 quality gates |
| QG-6 | Signal message sent | Worker confirms message posted to Signal group |
| QG-7 | Analysis script committed | `tools/synthesize_meas_report.py` committed and pushed to repo |
| QG-8 | JSON summary | `data/meas-1/analysis_summary.json` written with machine-readable stats |

### Est. time
- Create analysis script: 8 min
- Run analysis + generate report: 3 min
- Post to Signal + commit/push: 4 min
- **Total: ~15 min** (fully automated, no operator gate)

### Risk notes
- **Missing data:** If MEAS-1 produced fewer than expected CSV files, MEAS-2 should fail gracefully and escalate. This is a dependency violation, not a MEAS-2 bug.
- **Signal delivery:** If Signal bot is unavailable, worker writes report to `docs/` and notifies manager. Manager manually forwards to Felix.

---

## Design Rationale

### Why a 2-task chain (not single task)?

1. **Operator gate boundary:** MEAS-1 requires Felix at the bench (flash, position TX, walk between distances). MEAS-2 is fully automated (parse CSV, generate report, post to Signal). Splitting at this boundary means the automated analysis can be scheduled and run without Felix's involvement.

2. **Worker profile separation:** MEAS-1 uses `worker-balloon` (knows E80 firmware, capture tools, serial ports). MEAS-2 uses `worker-admin` (knows data analysis, Signal integration, git workflow). Different skill profiles, different task.

3. **Retry isolation:** If the analysis script has a bug, MEAS-2 can be re-run without requiring Felix to re-do the physical measurement. The raw data is already captured.

### Why this measurement (range test at 3 distances)?

1. **Validates the full harmonized pipeline end-to-end.** Every field in the 23-field format is exercised: `rssi_dbm` (varies with distance), `crc_ok` (expected failures at 30m), `seq` (monotonic across 180+ packets), `session_id` (injected by capture tool), `config_id`/`replicate` (from CONFIG command), `freq_hz`/`mod`/`sf`/`bw_khz`/`cr`/`power_dbm`/`pkt_size` (populated from radio config). GPS fields will be empty (bench test, no GPS) — this is expected and validates graceful empty-field handling.

2. **Most actionable for balloon mission planning.** The RSSI-vs-distance curve directly feeds the link budget: "At what altitude does the balloon lose contact?" The 30m data point gives a preliminary path loss exponent that can be extrapolated to balloon altitudes (1–10 km).

3. **Tests the critical R1/R5 path.** The E80 rig at 2 Mbps UART with 60-second continuous capture is exactly the scenario R1 (IWDG blocking) and R5 (baud change breaking host tools) were designed for. If this works, the critical path is proven.

4. **CRC failure logging validation.** At 30m, we expect some CRC failures. This validates E80-7 (CRC-failed packet RSSI extraction) under real RF conditions, not just unit tests.

5. **Relatively quick.** 3 × 60s captures + setup = ~30 minutes at the bench. Felix can do this in one session alongside INT-1.

### What's NOT in MEAS-1 (deferred to future tasks)

- **C3 rig cross-validation** → MEAS-3 (after E80 results are confirmed good)
- **SF/BW sweep** → MEAS-4 (after baseline range test confirms pipeline works)
- **RP2040 rig** → RP2040 firmware doesn't exist yet (RP-1 deferred per schedule)
- **Walk test with GPS** → MEAS-5 (after fixed-distance tests are validated)
- **Throughput at multiple configs** → MEAS-6 (sweep mode with `config_id` variation)

### Worker assignment rationale

| Task | Worker | Why |
|------|--------|-----|
| MEAS-1 | worker-balloon | Knows E80 firmware, capture tools, serial port handling. Same worker that did E80-1..8 and HOST-2. Already familiar with `capture_sweep.py` and the E80 rig. |
| MEAS-2 | worker-admin | Knows data analysis, git workflow, Signal integration. Same worker that did HOST-1/3/4 (host tools, session manager, PKT parser). Already familiar with the 23-field format and `pkt_parser.py`. |

---

## Kanban Creation Checklist

For the manager creating these tickets:

```
□ Create MEAS-1 ticket with title, labels, assignee=worker-balloon
□ Set MEAS-1 dependency: blocked-by INT-1 (t_0a18531a)
□ Add MEAS-1 description (copy Objective + Pre-conditions + Automated steps)
□ Create MEAS-2 ticket with title, labels, assignee=worker-admin
□ Set MEAS-2 dependency: blocked-by MEAS-1
□ Add MEAS-2 description (copy Objective + Automated steps + Output)
□ Verify dependency chain: INT-1 → MEAS-1 → MEAS-2
□ Notify Felix: "MEAS-1 requires you at the bench — flash E80 + position TX at 3 distances"
```