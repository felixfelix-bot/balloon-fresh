# PLAN — Pre-Range Testing Work (Kanban Tasks)

> **For:** Kanban workers (LLM agents) picking up discrete tasks.
> **Worktree:** `~/worktrees/balloon-speed-tests/`
> **Branch:** `speed-sustained-sweep`
> **Date:** 2026-07-23
> **Context:** Read `docs/HANDOVER-speed-tests-2026-07-23.md` first for verified results, bug fixes, and hardware setup.

---

## How to Use This Plan

Each task below is **self-contained** — a worker can pick up any task whose dependencies are met and execute it independently. Every task has:

- **ID** — for kanban tracking (`TASK-P1-1`, etc.)
- **Description** — what to build/do
- **Acceptance Criteria** — how to know it's done (checkable)
- **Complexity** — S (<1h), M (1–4h), L (4h+)
- **Dependencies** — which other tasks must be done first
- **Files to Modify** — specific paths
- **Reasoning Prompt** — WHY this task matters (for workers who lack full project context)

### Global Prerequisites (All Tasks)

Before starting ANY task:
1. Read `docs/HANDOVER-speed-tests-2026-07-23.md` for the bug fixes and verified results.
2. Acquire the board mutex:
   ```bash
   BALLOON_TRACK=speed-tests python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py acquire
   ```
3. Use ESP32 bridge ports: `/dev/ttyACM1` (RX #8332), `/dev/ttyACM3` (TX #F242D). **Never** use direct USB (ACM0/ACM2) — they swap on reset.
4. Flash with `picotool load -v -x firmware.uf2` (both `-v` and `-x` mandatory).
5. Release the mutex when done:
   ```bash
   BALLOON_TRACK=speed-tests python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py release
   ```

### Build + Flash Quick Reference

```bash
# Build firmware
cd ~/worktrees/balloon-speed-tests/firmware/rp2040
pio run -e rp2040-lora-tx-sf7          # example env

# Flash to TX board (RP2040 #F242D via ACM3 bridge)
~/.platformio/packages/tool-rp2040tools/picotool load -v -x .pio/build/rp2040-lora-tx-sf7/firmware.uf2

# Flash to RX board (RP2040 #8332 via ACM1 bridge)
~/.platformio/packages/tool-rp2040tools/picotool load -v -x .pio/build/rp2040-lora-rx/firmware.uf2
```

---

## Phase 1: FLRC Bitrate Sweep (Compile-Time Firmware)

### TASK-P1-1: Create FLRC TX Firmware with Compile-Time Bitrate Selection

**ID:** `TASK-P1-1`
**Complexity:** M
**Dependencies:** None (can start immediately)

**Description:**
Create a new FLRC TX firmware source file that selects the FLRC bitrate at **compile time** via a `#define FLRC_BITRATE` macro. This replaces the dead runtime-serial-command approach (USB CDC dies during TX loops — see handover doc "What Doesn't Work").

The bitrate macro should map to the `brBw` byte sent in `SET_FLRC_MODULATION_PARAMS` (opcode `0x0208`):
| FLRC_BITRATE | brBw byte | Theoretical kbps |
|---|---|---|
| 2600 | (existing — see `flrc_range_tx.cpp`) | 2600 |
| 1300 | TBD (check `bitrateToBrBw()` in existing code) | 1300 |
| 650  | TBD | 650 |
| 325  | TBD | 325 |

Base the new firmware on `firmware/rp2040/src/flrc_raw_tx.cpp` (the verified-working 2600 kbps TX). Add a `#ifndef FLRC_BITRATE / #define FLRC_BITRATE 2600 / #endif` guard at the top. Use the existing `bitrateToBrBw()` helper or create one if it doesn't exist for all 4 bitrates.

**Files to Modify:**
- `firmware/rp2040/src/flrc_bitrate_tx.cpp` (NEW — copy from `flrc_raw_tx.cpp`)
- `firmware/rp2040/platformio.ini` (add 4 envs: `rp2040-flrc-tx-2600`, `-1300`, `-650`, `-325`)

**Acceptance Criteria:**
- [ ] `flrc_bitrate_tx.cpp` compiles with `FLRC_BITRATE` set to each of 2600, 1300, 650, 325.
- [ ] All 4 PlatformIO environments build successfully (`pio run -e <env>` exits 0).
- [ ] The `brBw` byte is correct for each bitrate (verify against LR2021 datasheet or existing `flrc_range_tx.cpp` `bitrateToBrBw()` function).
- [ ] No runtime serial bitrate commands — bitrate is set at boot via `#define` only.

**Reasoning Prompt:**
> The LR2021 supports 4 FLRC bitrates (2600/1300/650/325 kbps), but we've only verified 2600 kbps. We tried runtime serial bitrate commands, but USB CDC dies during the TX loop (the serial port vanishes mid-test). So we need each bitrate as a separate compiled binary. This task creates the TX side. Without it, we can't characterize how PER/throughput varies with bitrate — critical data for deciding which bitrate to use at different ranges in the balloon mesh.

---

### TASK-P1-2: Create FLRC RX Firmware Matching Compile-Time Bitrate

**ID:** `TASK-P1-2`
**Complexity:** M
**Dependencies:** TASK-P1-1 (same `FLRC_BITRATE` macro convention)

**Description:**
Create a matching FLRC RX firmware that uses the same `#define FLRC_BITRATE` macro to configure the RX-side modulation params. The RX must use `SET_FLRC_MODULATION_PARAMS` (`0x0208`) with the same `brBw` byte as the TX.

Base on `firmware/rp2040/src/flrc_range_rx.cpp` (the verified-working RX). Ensure the `cumulativeRx` PER stats fix (commit `9352337`) is present in the new file.

**Files to Modify:**
- `firmware/rp2040/src/flrc_bitrate_rx.cpp` (NEW — copy from `flrc_range_rx.cpp`)
- `firmware/rp2040/platformio.ini` (add 4 envs: `rp2040-flrc-rx-2600`, `-1300`, `-650`, `-325`)

**Acceptance Criteria:**
- [ ] `flrc_bitrate_rx.cpp` compiles with `FLRC_BITRATE` set to each of 2600, 1300, 650, 325.
- [ ] All 4 PlatformIO environments build successfully.
- [ ] RX modulation params match TX (same `brBw` byte for each bitrate).
- [ ] `cumulativeRx` field is present in the stats struct (PER fix from commit `9352337`).
- [ ] RSSI decode is correct (see handover — FLRC uses `GET_FLRC_PACKET_STATUS` `0x024B`).

**Reasoning Prompt:**
> The RX firmware must match the TX bitrate exactly — if the RX is configured for 2600 kbps but the TX sends at 325 kbps, the RX will receive nothing. Each bitrate needs its own compiled RX binary, same as TX. This task mirrors TASK-P1-1 for the receive side. Without it, we can't test lower bitrates at all.

---

### TASK-P1-3: Build + Verify All 4 FLRC Bitrates Compile

**ID:** `TASK-P1-3`
**Complexity:** S
**Dependencies:** TASK-P1-1, TASK-P1-2

**Description:**
Run a clean build of all 8 FLRC bitrate environments (4 TX + 4 RX) and verify they all compile without errors. Fix any compilation issues found.

```bash
cd ~/worktrees/balloon-speed-tests/firmware/rp2040
for env in rp2040-flrc-tx-2600 rp2040-flrc-tx-1300 rp2040-flrc-tx-650 rp2040-flrc-tx-325 \
           rp2040-flrc-rx-2600 rp2040-flrc-rx-1300 rp2040-flrc-rx-650 rp2040-flrc-rx-325; do
    echo "=== Building $env ==="
    pio run -e "$env" || echo "FAILED: $env"
done
```

**Files to Modify:**
- `firmware/rp2040/src/flrc_bitrate_tx.cpp` (fixes if needed)
- `firmware/rp2040/src/flrc_bitrate_rx.cpp` (fixes if needed)
- `firmware/rp2040/platformio.ini` (fixes if needed)

**Acceptance Criteria:**
- [ ] All 8 environments build with exit code 0.
- [ ] `.pio/build/<env>/firmware.uf2` exists for each environment.
- [ ] No warnings about undefined `FLRC_BITRATE` or invalid `brBw` values.

**Reasoning Prompt:**
> This is a gate task — it verifies the firmware from P1-1 and P1-2 actually compiles before we spend time flashing and testing on hardware. A 10-minute build check saves an hour of debugging on the bench. If compilation fails here, fix it before moving to hardware testing.

---

### TASK-P1-4: Run Automated FLRC Sweep at All 4 Bitrates, Capture Results

**ID:** `TASK-P1-4`
**Complexity:** M
**Dependencies:** TASK-P1-3 (firmware must compile first)

**Description:**
Flash each bitrate pair (TX + RX) and run a sustained throughput test (10,000 packets, same methodology as the verified 2600 kbps test). Capture: TX count, TX rate, RX count, PER, RSSI, sustained throughput.

Procedure per bitrate:
1. Acquire board mutex.
2. Build TX + RX firmware for the target bitrate.
3. Flash TX to RP2040 #F242D (ACM3 bridge) and RX to RP2040 #8332 (ACM1 bridge).
4. Start RX first (so it's listening), then start TX.
5. Let TX send 10,000 packets.
6. Capture RX serial output: packet count, PER, RSSI, throughput.
7. Record results.
8. Release mutex.

**Files to Modify:**
- `docs/flrc-bitrate-sweep-results-2026-07-23.md` (NEW — results table)

**Acceptance Criteria:**
- [ ] All 4 bitrates tested (2600, 1300, 650, 325 kbps).
- [ ] Results table captures: bitrate, TX count, RX count, PER, RSSI, sustained throughput, % of theoretical.
- [ ] 2600 kbps results match the previously verified values (0% PER, ~1485 kbps) — sanity check.
- [ ] Results documented in `docs/flrc-bitrate-sweep-results-2026-07-23.md`.

**Reasoning Prompt:**
> We know FLRC 2600 kbps works at close range, but we don't know how lower bitrates perform. Lower bitrates are more robust (better sensitivity, more processing gain) but slower. This sweep tells us the PER vs throughput tradeoff at each bitrate — essential for the adaptive protocol (ADR-007) that will switch between FLRC bitrates based on link quality. Without this data, we're guessing which bitrate to use at different ranges.

---

## Phase 2: TX Power Sweep

### TASK-P2-1: Verify SET_TX_PARAMS Opcode Controls Output Power on LR2021

**ID:** `TASK-P2-1`
**Complexity:** S
**Dependencies:** None

**Description:**
Verify that the `SET_TX_PARAMS` opcode actually controls the LR2021's output power. The firmware uses opcode `{0x02, 0x03, power_raw, ramp}` (see `flrc_range_tx.cpp:176-179` and `lora_range_tx.cpp:327`). The task spec lists `0x0216` — resolve this discrepancy by checking the Semtech LR2021 datasheet.

Test: Flash TX firmware at 2 different power levels (e.g., 0 dBm and 12 dBm), measure RSSI on RX, confirm RSSI changes by ~12 dB.

**Files to Modify:**
- `docs/lr2021-tx-params-verification.md` (NEW — verification notes)

**Acceptance Criteria:**
- [ ] Opcode discrepancy resolved: confirm whether `0x0203` or `0x0216` is correct (check datasheet + existing working code).
- [ ] RX RSSI changes measurably when TX power changes from 0 dBm to 12 dBm (expect ~12 dB delta).
- [ ] `power_raw = dbm × 2` mapping confirmed (0.5 dB steps).
- [ ] Findings documented.

**Reasoning Prompt:**
> Before we can sweep TX power (P2-3), we need to confirm that the power control opcode actually works. If SET_TX_PARAMS is a no-op or uses the wrong opcode, the entire power sweep would produce meaningless data. Also, there's a discrepancy between the task spec (0x0216) and the code (0x0203) that must be resolved — the verified-working 12 dBm tests used 0x0203, but we should confirm this is the canonical opcode. This is a 30-minute sanity check that de-risks the entire power sweep phase.

---

### TASK-P2-2: Create TX Firmware with Compile-Time Power Setting

**ID:** `TASK-P2-2`
**Complexity:** M
**Dependencies:** TASK-P2-1 (confirm opcode first)

**Description:**
Create TX firmware variants (or a single parametric source) that sets TX power via compile-time `#define TX_POWER_DBM`. This avoids the USB CDC death problem (same as bitrate — no runtime serial commands during TX).

Base on `firmware/rp2040/src/lora_range_tx.cpp` (already uses `cfgPower` from a `#define`). Add a `#ifndef TX_POWER_DBM / #define TX_POWER_DBM 12 / #endif` guard. Add PlatformIO environments for power levels: 0, 3, 6, 9, 12, 12.5 dBm.

**Files to Modify:**
- `firmware/rp2040/src/lora_range_tx.cpp` (add `TX_POWER_DBM` macro, or create `lora_power_tx.cpp`)
- `firmware/rp2040/platformio.ini` (add envs: `rp2040-lora-tx-sf7-pwr0`, `-pwr3`, `-pwr6`, `-pwr9`, `-pwr12`, `-pwr12.5`)

**Acceptance Criteria:**
- [ ] `TX_POWER_DBM` macro controls the power byte sent to `SET_TX_PARAMS`.
- [ ] All 6 power-level environments compile successfully.
- [ ] `power_raw = TX_POWER_DBM × 2` (0.5 dB resolution).

**Reasoning Prompt:**
> We need to sweep TX power to find the power-vs-PER-vs-range curve. But we can't change power at runtime (USB CDC dies during TX loops). So we need one compiled binary per power level, same as the bitrate approach. Using SF7 (fastest LoRa) for the sweep gives quick turnaround — each test takes ~7 seconds for 200 packets instead of ~2 minutes at SF12.

---

### TASK-P2-3: Run Power Sweep at SF7 Across 0–12.5 dBm

**ID:** `TASK-P2-3`
**Complexity:** M
**Dependencies:** TASK-P2-2 (firmware must exist)

**Description:**
Flash each power-level TX firmware (0, 3, 6, 9, 12, 12.5 dBm) and measure PER, RSSI, and SNR on the RX at fixed 1–2 m range. Use SF7 LoRa (fast turnaround). 200 packets per power level.

**Files to Modify:**
- `docs/power-sweep-results-2026-07-23.md` (NEW — results table)

**Acceptance Criteria:**
- [ ] All 6 power levels tested (0, 3, 6, 9, 12, 12.5 dBm).
- [ ] Results table: power (dBm), TX count, RX count, PER, RSSI, SNR.
- [ ] RSSI increases monotonically with TX power (sanity check).
- [ ] Results documented.

**Reasoning Prompt:**
> At close range (1–2 m), we expect near-0% PER at all power levels — the link is too strong. But this sweep validates that power control actually works and gives us a baseline RSSI-vs-power calibration curve. When we move to range testing, we'll need to know how much we can back off power to simulate longer distances (or use actual distance). This data feeds directly into the adaptive TX power decision (ADR-010).

---

### TASK-P2-4: Document Power vs PER vs RSSI Relationship

**ID:** `TASK-P2-4`
**Complexity:** S
**Dependencies:** TASK-P2-3

**Description:**
Analyze the power sweep results and write a summary document describing the power → RSSI → PER relationship. Include: RSSI-per-dBm slope, PER threshold (at what RSSI does PER start climbing), and recommendations for adaptive power.

**Files to Modify:**
- `docs/power-vs-per-analysis-2026-07-23.md` (NEW)

**Acceptance Criteria:**
- [ ] RSSI-per-dBm slope calculated (expect ~1:1 at this range).
- [ ] PER sensitivity threshold identified (if visible at this range).
- [ ] Recommendation for adaptive power control strategy.
- [ ] Document references the raw data from TASK-P2-3.

**Reasoning Prompt:**
> Raw test data is useless without analysis. This task converts numbers into actionable engineering decisions: at what power level does the link become unreliable? How much margin do we have? This feeds the adaptive protocol design (ADR-007, ADR-010) that will dynamically adjust TX power based on link conditions during balloon flight.

---

## Phase 3: Automated Test Harness

### TASK-P3-1: Write Python Test Runner (Flash + Capture + Parse)

**ID:** `TASK-P3-1`
**Complexity:** L
**Dependencies:** TASK-P1-3 (needs working firmware to orchestrate)

**Description:**
Write a Python script that automates the full test cycle:
1. Acquire board mutex.
2. Build firmware for given env (call `pio run`).
3. Flash TX to ACM3, RX to ACM1 (call `picotool load -v -x`).
4. Open RX serial port, start capture.
5. Wait for TX to complete (detect via serial output or timeout).
6. Parse RX serial output: packet count, PER, RSSI, SNR, throughput.
7. Release mutex.
8. Return structured results.

```bash
# Usage example:
python3 scripts/run_speed_test.py --tx-env rp2040-flrc-tx-2600 --rx-env rp2040-flrc-rx-2600 --duration 10
```

**Files to Modify:**
- `scripts/run_speed_test.py` (NEW)
- `scripts/serial_capture.py` (NEW — serial port reader, if separate module preferred)

**Acceptance Criteria:**
- [ ] Script runs end-to-end: build → flash → capture → parse → output.
- [ ] Works with both FLRC and LoRa environments.
- [ ] Handles serial port errors gracefully (port not found, timeout, CDC death).
- [ ] Mutex acquire/release is automatic and guaranteed (even on error/crash).
- [ ] Output is human-readable (printed to stdout).

**Reasoning Prompt:**
> Right now, every test requires manual steps: build, flash TX, flash RX, start capture, watch serial, copy numbers into a doc. This takes 15+ minutes per configuration and is error-prone. With 4 FLRC bitrates × 6 power levels × 3 LoRa SFs = 72+ configurations to test, manual testing is infeasible. This harness automates the entire cycle so we can run sweeps unattended. It's the highest-leverage investment in this plan — once it works, all subsequent testing is 10× faster.

---

### TASK-P3-2: Add JSON Results Output Format

**ID:** `TASK-P3-2`
**Complexity:** S
**Dependencies:** TASK-P3-1

**Description:**
Extend the test runner to output results in a structured JSON format alongside the human-readable output. Define a schema for test results.

Proposed schema:
```json
{
  "test_id": "flrc-2600-2026-07-23T14:30:00",
  "timestamp": "2026-07-23T14:30:00Z",
  "config": {
    "modulation": "FLRC",
    "bitrate_kbps": 2600,
    "frequency_mhz": 2440,
    "tx_power_dbm": 12,
    "payload_bytes": 127,
    "spreading_factor": null,
    "coding_rate": null
  },
  "results": {
    "tx_packets": 10000,
    "tx_time_s": 6.8,
    "tx_rate_kbps": 1753,
    "rx_packets": 21923,
    "per_percent": 0.0,
    "rssi_dbm": -71,
    "snr_db": null,
    "sustained_throughput_kbps": 1485,
    "theoretical_kbps": 2600,
    "efficiency_percent": 57.0
  },
  "metadata": {
    "range_m": "1-2",
    "environment": "indoor",
    "tx_board": "F242D",
    "rx_board": "8332",
    "firmware_git": "9352337"
  }
}
```

**Files to Modify:**
- `scripts/run_speed_test.py` (add `--json-output <path>` flag)
- `scripts/test_result_schema.json` (NEW — JSON schema definition)

**Acceptance Criteria:**
- [ ] JSON output validates against the schema.
- [ ] All fields from the verified results are representable.
- [ ] `--json-output` flag writes to a file; stdout still shows human-readable summary.
- [ ] JSON includes git commit hash of the firmware for reproducibility.

**Reasoning Prompt:**
> Human-readable docs are great for handovers, but machine-readable JSON lets us aggregate, compare, and plot results programmatically. When we have 72+ test configurations, we need to generate comparison tables automatically (TASK-P5-2). JSON is the lingua franca for that. This schema also serves as the canonical record — if someone questions a result later, the JSON has the full provenance (config, git hash, timestamp).

---

### TASK-P3-3: Add Sweep Mode (Run All Configs Automatically, Tabulate)

**ID:** `TASK-P3-3`
**Complexity:** M
**Dependencies:** TASK-P3-1, TASK-P3-2

**Description:**
Extend the test runner with a `--sweep` mode that runs a list of configurations automatically and produces a summary table. Define sweep profiles (FLRC bitrate sweep, LoRa SF sweep, power sweep) as config files.

```bash
# Run the FLRC bitrate sweep:
python3 scripts/run_speed_test.py --sweep configs/flrc-bitrate-sweep.yaml

# Run the power sweep:
python3 scripts/run_speed_test.py --sweep configs/power-sweep-sf7.yaml
```

Sweep config format (YAML):
```yaml
name: "FLRC Bitrate Sweep"
configs:
  - tx_env: rp2040-flrc-tx-2600
    rx_env: rp2040-flrc-rx-2600
    label: "FLRC 2600"
  - tx_env: rp2040-flrc-tx-1300
    rx_env: rp2040-flrc-rx-1300
    label: "FLRC 1300"
  # ...
output: docs/flrc-bitrate-sweep-results.json
```

**Files to Modify:**
- `scripts/run_speed_test.py` (add `--sweep` mode)
- `configs/flrc-bitrate-sweep.yaml` (NEW)
- `configs/power-sweep-sf7.yaml` (NEW)
- `configs/lora-sf-sweep.yaml` (NEW)

**Acceptance Criteria:**
- [ ] `--sweep` runs all configs in a YAML profile sequentially.
- [ ] Each config result is saved as individual JSON.
- [ ] Summary table printed to stdout at the end (markdown table format).
- [ ] Aggregate JSON output written to the path specified in the sweep config.
- [ ] Mutex is held for the entire sweep (not per-config).

**Reasoning Prompt:**
> This is the payoff of TASK-P3-1 and P3-2. Instead of running 4 separate commands for the FLRC sweep, you run one command with a sweep profile and get the full results table. This makes repeatable testing trivial — re-run the sweep after any firmware change to catch regressions. The YAML profiles also serve as documentation of what configurations have been tested.

---

## Phase 4: Firmware Cleanup + Bug Verification

### TASK-P4-1: Re-Verify PER Stats Fix with SF12 (cumulativeRx)

**ID:** `TASK-P4-1`
**Complexity:** S
**Dependencies:** None (high priority — should be done FIRST)

**Description:**
The `cumulativeRx` PER stats fix (commit `9352337`) has been coded and compiles but has **NOT been verified on hardware**. The SF12 test that showed 198/200 (1% PER) was run BEFORE the fix — the actual PER was calculated manually from raw data.

Re-run the SF12 test with the fixed firmware and verify that the firmware-reported PER matches the manually-computed PER.

Procedure:
1. Build `rp2040-lora-tx-sf12` and `rp2040-lora-rx-sf12` (with the `cumulativeRx` fix).
2. Flash both boards.
3. Run 200-packet SF12 test.
4. Compare firmware-reported PER with manual PER = `(maxSeq+1 - received) / (maxSeq+1)`.

**Files to Modify:**
- `docs/per-fix-verification-2026-07-23.md` (NEW — verification result)

**Acceptance Criteria:**
- [ ] SF12 test run with fixed firmware.
- [ ] Firmware-reported PER matches manual calculation (within 1%).
- [ ] PER is NOT inflated to 78% (the old bug symptom).
- [ ] Result documented: before (78% bug) vs after (correct value).

**Reasoning Prompt:**
> This is the highest-priority verification task. We fixed a bug that was inflating PER from 1% to 78%, but we never confirmed the fix works on real hardware. If the fix is wrong, ALL subsequent PER measurements will be garbage. Before running any new tests (FLRC sweep, power sweep), we must confirm the PER calculation is correct. This is a 15-minute test that validates the foundation of all future testing.

---

### TASK-P4-2: Consolidate Redundant Firmware Files (Remove Dead Experiments)

**ID:** `TASK-P4-2`
**Complexity:** M
**Dependencies:** None (can be done anytime, but after P4-1 is cleaner)

**Description:**
The `firmware/rp2040/src/` directory has 30+ source files, many of which are dead experiments from the development process. Consolidate by:
1. Identifying which files are referenced by PlatformIO environments in `platformio.ini`.
2. Identifying files NOT referenced (dead code).
3. Moving dead files to `firmware/rp2040/src/archive/` (don't delete — preserve history).
4. Documenting which files are "canonical" (in use) vs "archived".

**Files to Modify:**
- `firmware/rp2040/src/archive/` (NEW directory — move dead files here)
- `firmware/rp2040/platformio.ini` (remove dead envs if any)
- `docs/firmware-file-inventory.md` (NEW — canonical vs archived listing)

**Acceptance Criteria:**
- [ ] Every `.cpp` file in `src/` is categorized as "canonical" or "archived".
- [ ] Dead files moved to `src/archive/`.
- [ ] All canonical environments still build after consolidation.
- [ ] `docs/firmware-file-inventory.md` lists every file with its status and purpose.

**Reasoning Prompt:**
> 30+ firmware files is cognitive overload for any new worker. Half of them are dead experiments (PIO TX v1/v2/v3, batch SPI, DMA TX, etc.) that were tried and abandoned. A clean directory structure with only canonical files + an archive makes it obvious which firmware to use. This reduces onboarding time and prevents workers from accidentally using deprecated firmware. The key learning: RadioLib is dead, batch SPI is reverted, PIO TX was abandoned — those files should be archived.

---

### TASK-P4-3: Verify RSSI Raw Byte Dump Matches Expected Format

**ID:** `TASK-P4-3`
**Complexity:** S
**Dependencies:** TASK-P4-1 (PER fix verified first)

**Description:**
After the RSSI/SNR byte swap fix (commit `dca7a84`), verify that the raw bytes from `GET_LORA_PACKET_STATUS` (`0x022A`) match the expected format:
- `buf[2]` = RSSI raw byte
- `buf[3]` = SNR raw byte

Add a debug mode to the RX firmware that dumps the raw 4+ bytes from the packet status read, then verify the decode:
- RSSI: signed, offset decode → should be ~-8 dBm at 1–2 m
- SNR: signed, 0.25 dB steps → should be ~31.8 dB at 1–2 m

**Files to Modify:**
- `firmware/rp2040/src/lora_range_rx.cpp` (add `#define DEBUG_RSSI_RAW` conditional dump)
- `docs/rssi-raw-byte-verification.md` (NEW)

**Acceptance Criteria:**
- [ ] Raw byte dump shows `buf[2]` and `buf[3]` values.
- [ ] Decoded RSSI ≈ -8 dBm (matches the verified SF7 result).
- [ ] Decoded SNR ≈ 31.8 dB (matches the verified SF7 result).
- [ ] Byte order confirmed: RSSI before SNR (not reversed).
- [ ] Document includes the raw hex bytes and the decode math.

**Reasoning Prompt:**
> We fixed the RSSI/SNR byte swap, but we verified it by checking that the output "looks right" (-8 dBm instead of -127 dBm). We haven't dumped the raw bytes to confirm the fix is in the right place. This is a belt-and-suspenders verification: dump the raw SPI response bytes and manually decode them to prove the byte order is correct. If the raw bytes don't match, the "fix" might be compensating for a different bug. Important for range testing where RSSI accuracy is critical for link budget analysis.

---

### TASK-P4-4: Document LR2021 LoRa Modulation Parameter Encoding

**ID:** `TASK-P4-4`
**Complexity:** M
**Dependencies:** None

**Description:**
Write a comprehensive reference document for the LR2021 LoRa modulation parameter encoding, covering:
- `SET_LORA_MODULATION_PARAMS` (`0x0220`): byte layout for SF+BW and CR+LDRO
- `SET_LORA_PACKET_PARAMS` (`0x0221`): preamble, payload length, flags
- Coding Rate encoding: internal index 1–4 (NOT denominator 4/5, 4/6, etc.)
- SF encoding: which bits, valid values
- BW encoding: which bits, valid values
- LDRO (Low Data Rate Optimization) bit position

Cross-reference against the Semtech LR2021 datasheet and the verified-working code in `lora_range_tx.cpp`.

**Files to Modify:**
- `docs/lr2021-lora-modulation-encoding.md` (NEW)
- `docs/lr2021-spi-command-reference.md` (update if it exists — add modulation params detail)

**Acceptance Criteria:**
- [ ] Every byte of `SET_LORA_MODULATION_PARAMS` documented with bit-field layout.
- [ ] CR encoding table: index 1→4/5, 2→4/6, 3→4/7, 4→4/8 (with SPI byte values).
- [ ] SF encoding table: SF5–SF12 with their byte values.
- [ ] BW encoding table: valid bandwidths with byte values.
- [ ] LDRO bit documented (when to enable it).
- [ ] Cross-referenced against `lora_range_tx.cpp` code (show which `#define` maps to which byte).

**Reasoning Prompt:**
> The CR encoding bug (LORA_CR=5 → 0x50 garbage) happened because nobody documented the encoding. The datasheet uses internal indices, not human-readable values, and the mapping wasn't written down anywhere. This reference prevents the next person from making the same mistake. It also serves as the authoritative source for any future modulation parameter work — if someone needs to add a new SF or BW, they look here instead of reverse-engineering the code. This is "documentation as bug prevention."

---

## Phase 5: Test Data Consolidation

### TASK-P5-1: Create Master Results JSON with All Test Data

**ID:** `TASK-P5-1`
**Complexity:** M
**Dependencies:** TASK-P1-4, TASK-P2-3 (need test data to consolidate)

**Description:**
Aggregate all test results (FLRC bitrate sweep, LoRa SF sweep, power sweep) into a single master JSON file. Include the already-verified results from the handover doc (FLRC 2600, LoRa SF7/SF9/SF12) plus all new results.

Structure:
```json
{
  "project": "balloon-speed-tests",
  "date": "2026-07-23",
  "tests": [
    { "test_id": "...", "config": {...}, "results": {...}, ... },
    ...
  ]
}
```

**Files to Modify:**
- `docs/master-results-2026-07-23.json` (NEW)

**Acceptance Criteria:**
- [ ] All verified results from the handover doc included (FLRC 2600, LoRa SF7/SF9/SF12).
- [ ] All new sweep results included (FLRC 1300/650/325, power sweep).
- [ ] JSON validates (no syntax errors).
- [ ] Each test entry has full provenance (git hash, timestamp, board IDs, environment).
- [ ] File is the single source of truth for all speed-test data.

**Reasoning Prompt:**
> Test results are currently scattered across multiple markdown docs, serial captures, and chat logs. When someone asks "what's the PER at FLRC 1300?", they shouldn't have to hunt through 5 documents. A master JSON file is the canonical data store — all docs and tables are generated from it. This is the database for the speed-test track. Without it, results get lost, duplicated, or contradicted.

---

### TASK-P5-2: Generate Summary Comparison Table (FLRC vs LoRa at All Configs)

**ID:** `TASK-P5-2`
**Complexity:** S
**Dependencies:** TASK-P5-1 (needs master JSON)

**Description:**
Generate a markdown summary table comparing all modulation modes and configurations side by side. Pull data from the master results JSON.

Table format:
| Modulation | Bitrate/SF | TX Rate | RX Throughput | PER | RSSI | SNR | Efficiency |
|---|---|---|---|---|---|---|---|
| FLRC | 2600 kbps | 1753 | 1485 | 0% | -71 | — | 57% |
| FLRC | 1300 kbps | ... | ... | ... | ... | — | ... |
| LoRa | SF7 | ... | ... | ... | ... | ... | ... |
| LoRa | SF9 | ... | ... | ... | ... | ... | ... |
| LoRa | SF12 | ... | ... | ... | ... | ... | ... |

**Files to Modify:**
- `docs/speed-test-summary-table-2026-07-23.md` (NEW)

**Acceptance Criteria:**
- [ ] Table includes all tested configurations (FLRC × 4, LoRa × 3).
- [ ] All columns populated from master JSON (no blank cells where data exists).
- [ ] Efficiency column = sustained_throughput / theoretical × 100%.
- [ ] Table is copy-pasteable into other docs (markdown format).

**Reasoning Prompt:**
> This is the "executive summary" of the entire speed-test track. When someone asks "how fast can the balloon link go?", this table is the answer. It shows the full tradeoff space: FLRC is fast but fragile, LoRa is slow but robust, and the numbers quantify exactly how much. This table feeds into the adaptive protocol design (ADR-007) — it's the data behind "when do we switch from FLRC to LoRa?"

---

### TASK-P5-3: Write Handover Doc for Range Testing Phase

**ID:** `TASK-P5-3`
**Complexity:** M
**Dependencies:** TASK-P5-1, TASK-P5-2 (need consolidated data)

**Description:**
Write a handover document for the **range testing phase** (outdoor, varying distance, antenna orientation, noise environment). This is the bridge between the controlled indoor speed tests and real-world range characterization.

The doc must cover:
1. **What to test:** distance sweeps (2, 4, 8, 16, 32, 64, 128, 256, 512, 1024 m — binary step), at each modulation mode, with/without directional antennas, in different noise environments.
2. **How to test:** test procedure (flash TX+RX, position boards, measure distance, run 200-packet test, record PER/RSSI/SNR), equipment needed (GPS for distance, antenna stands, spectrum analyzer if available).
3. **Expected results:** based on the indoor baseline, predict how PER/RSSI will degrade with distance. Use the link budget from `docs/link-budget.md`.
4. **What we know so far:** indoor baseline (FLRC 2600: -71 dBm at 1–2 m; LoRa SF7: -8 dBm at 1–2 m).
5. **Safety/logistics:** outdoor test permissions, weather considerations, equipment checklist.

**Files to Modify:**
- `docs/HANDOVER-range-testing-phase-2026-07-23.md` (NEW)

**Acceptance Criteria:**
- [ ] Distance sweep plan with binary-step methodology (2m → 1024m).
- [ ] Test matrix: which modulations to test at which distances.
- [ ] Expected RSSI at each distance (from link budget + free-space path loss).
- [ ] PER prediction (when does each modulation drop below acceptable PER?).
- [ ] Equipment checklist (boards, antennas, GPS, batteries, stands).
- [ ] References to indoor baseline data (master JSON + summary table).
- [ ] References to existing range test docs (`docs/OUTDOOR-TEST-PROCEDURE.md`, `docs/range-test-comprehensive-plan-2026-07-17.md`).

**Reasoning Prompt:**
> The indoor speed tests tell us "how fast can the link go at close range." The range tests tell us "how far can the link go." These are complementary — speed tests define the ceiling, range tests define the floor. This handover doc is the bridge: it takes everything we learned indoors and translates it into a plan for outdoor testing. Without it, the range-testing team would have to re-derive the methodology from scratch. The binary-step distance sweep mirrors the binary-step bitrate sweep — same philosophy, applied to distance instead of speed. Expected: FLRC will fail first (high bitrate = short range), LoRa SF12 will go furthest (low bitrate = long range). The question is: at what distance does each mode become unreliable?

---

## Dependency Graph

```
P4-1 (PER verify)  ────────────────────────────────────────┐ (DO FIRST)                                                            │
                                                            ▼
P1-1 (FLRC TX)  ──►  P1-2 (FLRC RX)  ──►  P1-3 (Build)  ──►  P1-4 (FLRC Sweep)
                                                            │
P2-1 (TX_PARAMS)  ──►  P2-2 (Power FW)  ──►  P2-3 (Power Sweep)  ──►  P2-4 (Analysis)
                                                            │
P3-1 (Runner)  ──►  P3-2 (JSON)  ──►  P3-3 (Sweep Mode)
                                  │       │
P4-2 (Cleanup)  P4-3 (RSSI)  P4-4 (Doc)   │
                                  │       │
                                  ▼       ▼
                    P5-1 (Master JSON)  ──►  P5-2 (Summary Table)  ──►  P5-3 (Range Handover)
```

### Recommended Execution Order

1. **TASK-P4-1** — Verify PER fix (blocks confidence in all future PER data)
2. **TASK-P1-1, P1-2, P1-3** — FLRC bitrate firmware (parallel with P2-1)
3. **TASK-P2-1** — Verify TX_PARAMS opcode (parallel with P1)
4. **TASK-P1-4** — FLRC sweep (after P1-3)
5. **TASK-P2-2, P2-3** — Power firmware + sweep (after P2-1)
6. **TASK-P3-1** — Python test runner (can start anytime, highest leverage)
7. **TASK-P3-2, P3-3** — JSON output + sweep mode (after P3-1)
8. **TASK-P4-2, P4-3, P4-4** — Cleanup + verification (parallel, low priority)
9. **TASK-P2-4** — Power analysis (after P2-3)
10. **TASK-P5-1** — Master JSON (after P1-4, P2-3)
11. **TASK-P5-2** — Summary table (after P5-1)
12. **TASK-P5-3** — Range testing handover (after P5-2 — final deliverable)

### Parallel Tracks

A team of 3 workers could parallelize as:
- **Worker A:** P4-1 → P1-1/P1-2/P1-3 → P1-4 → P5-1 → P5-2 → P5-3
- **Worker B:** P2-1 → P2-2 → P2-3 → P2-4
- **Worker C:** P3-1 → P3-2 → P3-3 (then help with P4-2/P4-3/P4-4)

---

## Reference: LR2021 Key Opcodes

| Opcode | Name | Key Detail |
|---|---|---|
| `0x0207` | SET_PACKET_TYPE | LoRa=`0x00`, FLRC=`0x04` |
| `0x0220` | SET_LORA_MODULATION_PARAMS | SF+BW byte, CR+LDRO byte |
| `0x0221` | SET_LORA_PACKET_PARAMS | preamble, payloadLen, flags |
| `0x0208` | SET_FLRC_MODULATION_PARAMS | bitrate+BW byte, CR byte, shaping byte |
| `0x022A` | GET_LORA_PACKET_STATUS | `buf[2]=RSSI`, `buf[3]=SNR` |
| `0x024B` | GET_FLRC_PACKET_STATUS | FLRC packet status |
| `0x0283` | SET_TX | Trigger transmission |
| `0x0282` | SET_RX | Trigger reception (with timeout) |
| `0x0203`* | SET_TX_PARAMS | `[power_raw, ramp]` — power = dbm×2 |

> *The actual firmware code uses `{0x02, 0x03, ...}` = `0x0203`. The task spec lists `0x0216`. The verified 12 dBm tests used `0x0203`. Resolve in TASK-P2-1.

**IRQ status (32-bit):** `RX_DONE` = bit 18, `TX_DONE` = bit 19.
