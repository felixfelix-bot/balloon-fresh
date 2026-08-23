# DESIGN: Distributed Range Test Architecture for E80 Balloon Bench

> **Status:** Implemented on `feat/2g4-sweep` branch
> **Date:** 2026-08-23
> **Author:** Distributed range test design — subagent task

## 1. Problem Statement

The E80 bench controller (`e80_bench_ctl.py`) was built for **both boards on one
machine** — a single Python process opens TX and RX serial ports, controls
the timing between them, and polls STAT? on both. This works on the indoor
bench but breaks for outdoor range testing where:

- TX and RX are on **physically separate machines** (T470 and DQ05)
- The machines may be behind **different NATs** — no guaranteed network path
- Operators cannot manually manage port assignments or probe serials
- CH340 USB-serial ports **swap `/dev/ttyUSB*` numbers on every reboot**

## 2. Design Principles

1. **Schedule-based independence**: Both machines anchor on the same wall-clock
   T0 (exchanged via phone), run independent schedules, and never need to
   communicate during the test.

2. **Single operator command**: `make range-tx T0="..." CONFIGS=outdoor-10`
   runs the entire TX side. No port numbers, no probe serials, no Python args.

3. **Reuse, don't rewrite**: The existing `e80_bench_ctl.py` has all the
   timing infrastructure (`parse_t0`, `build_stop_schedule`, `wait_until`).
   We add `--mode tx/rx` flags, not a new tool.

4. **Auto-detection from `e80_detect.py`**: The existing detection module
   (`detect_board(target_role)`) handles CH340 port discovery + SWD probe
   serial matching via sysfs. No new detection code needed.

5. **Config presets in JSON**: Shared config files in `configs/` directory,
   loaded identically by both TX and RX machines.

6. **Clear error messages**: If no board is detected, print a helpful message
   and exit — never a stack trace.

## 3. Architecture

```
┌─────────────────────────┐       ┌─────────────────────────┐
│    TX MACHINE (T470)    │       │    RX MACHINE (DQ05)    │
│                         │       │                         │
│  make range-tx          │       │  make range-rx          │
│  T0="..." CONFIGS=...   │       │  T0="..." CONFIGS=...   │
│         │               │       │         │               │
│         ▼               │       │         ▼               │
│  e80_bench_ctl.py       │       │  e80_bench_ctl.py       │
│  --mode tx              │       │  --mode rx              │
│         │               │       │         │               │
│    ┌────┴────┐          │       │    ┌────┴────┐          │
│    │ e80_    │          │       │    │ e80_    │          │
│    │ detect  │          │       │    │ detect  │          │
│    │ .py     │          │       │    │ .py     │          │
│    └────┬────┘          │       │    └────┬────┘          │
│         │               │       │         │               │
│    ┌────┴────┐          │       │    ┌────┴────┐          │
│    │ Board   │          │       │    │ Board   │          │
│    │ Serial  │          │       │    │ Serial  │          │
│    │ (CH340) │          │       │    │ (CH340) │          │
│    └────┬────┘          │       │    └────┬────┘          │
│         │               │       │         │               │
│         ▼               │       │         ▼               │
│  ┌─────────────┐        │       │  ┌─────────────┐        │
│  │ E80 TX Board│~~~~~~~~│~~  RF ~│~E80 RX Board │        │
│  │ (fw 0561b29)│  868MHz│   Link │ (fw 0561b29) │        │
│  └─────────────┘        │       │  └─────────────┘        │
│         │               │       │         │               │
│         ▼               │       │         ▼               │
│  tx-log.csv             │       │  rx-log.csv             │
│  (per-config summary)   │       │  (per-packet PKT lines) │
└──────────┬──────────────┘       └──────────┬──────────────┘
           │                                 │
           └────────────┬────────────────────┘
                        │  Operator copies CSVs to merge machine
                        ▼
              make range-merge TX=tx-log.csv RX=rx-log.csv
                        │
                        ▼
              combined.csv + combined-range-report.md
```

### 3.1 Clock Synchronization

Both machines run NTP (systemd-timesyncd or ntpd). The NTP sync discipline
ensures wall-clock alignment within sub-second accuracy, which is well within
the timing margins:

- `rx_lead = 10s` — RX arms 10s before TX starts transmitting
- `guard = 20s` — 20s guard between config cells
- `settle = 2s` — 2s settle after burst before reading STAT
- `t0_margin = 120s` — 2min buffer after T0 before first config starts

These margins absorb any NTP drift, operator timing differences, or board
startup latency.

### 3.2 No Network Dependency During Test

The key design choice: **TX and RX never communicate during the test**.

1. Both machines are given the same T0 and config preset via `make`.
2. The Makefile passes these to `e80_bench_ctl.py --mode tx/rx`.
3. Both machines independently compute the same schedule from T0.
4. TX sends bursts on schedule; RX arms and captures on schedule.
5. After the test, operators copy `tx-log.csv` and `rx-log.csv` to one
   machine and run `make range-merge`.

If SSH is available, a convenience target can fetch the remote CSV
automatically, but the system must work without it.

## 4. Component Specifications

### 4.1 Config Preset Format (`configs/*.json`)

```json
{
  "name": "outdoor-10",
  "description": "Outdoor range test — 10 pkts per config",
  "band": "868",
  "configs": [
    {
      "label": "FLRC-650 LEN64",
      "mod": "flrc",
      "br": 650,
      "sf": null,
      "bw": null,
      "pa": 10,
      "freq": 868000000,
      "plen": 64,
      "gap": 5000,
      "n_pkts": 10
    },
    {
      "label": "LoRa-SF7 BW125 LEN64",
      "mod": "lora",
      "sf": 7,
      "bw": 125,
      "br": null,
      "pa": 10,
      "freq": 868000000,
      "plen": 64,
      "gap": 10000,
      "n_pkts": 10
    }
  ]
}
```

Fields per config:
- `label` — human-readable identifier
- `mod` — "lora" or "flrc"
- `sf` — LoRa spreading factor (5-12), null for FLRC
- `br` — FLRC bit rate (kbps: 260,325,520,650,1040,1300,2080,2600), null for LoRa
- `bw` — LoRa bandwidth (125,250,500 kHz), null for FLRC
- `pa` — TX power dBm (0-10 indoor, 11-22 outdoor with unlock)
- `freq` — center frequency Hz
- `plen` — payload length bytes (6-511 FLRC, 6-255 LoRa)
- `gap` — inter-packet gap microseconds
- `n_pkts` — number of packets in the burst

### 4.2 e80_bench_ctl.py — `--mode tx` and `--mode rx`

#### TX Mode

```
e80_bench_ctl.py --mode tx \
  --t0 "2026-08-30 14:00" \
  --configs configs/outdoor-10.json \
  [--band-override] [--dbm N] [--skip-fw-check] [--tx-log tx-log.csv]
```

Flow:
1. Load config preset JSON
2. Call `e80_detect.detect_board("TX")` → port, probe_serial, role
3. Open BoardSerial on detected port
4. For each config in preset, at T0-anchored start time:
   - Send: SESSION, CONFIG, BAND OVERRIDE (if needed), MOD, FREQ, PA, ROLE TX,
     ARM TX, START
   - Poll STAT? until sent_ok >= n_pkts
   - Record per-config row to tx-log.csv
5. Send ROLE NONE (teardown)
6. Close port

TX log columns: `session,config_idx,label,n_pkts,sent_ok,mod,sf_or_br,bw,pa_dbm,
freq_hz,plen,gap_us,t0_offset_s,actual_start_ts,error`

#### RX Mode

```
e80_bench_ctl.py --mode rx \
  --t0 "2026-08-30 14:00" \
  --configs configs/outdoor-10.json \
  [--band-override] [--skip-fw-check] [--rx-log rx-log.csv]
```

Flow:
1. Load config preset JSON
2. Call `e80_detect.detect_board("RX")` → port, probe_serial, role
3. Open BoardSerial on detected port
4. For each config in preset, at T0-anchored start - rx_lead:
   - Send: SESSION, CONFIG, BAND OVERRIDE (if needed), MOD, FREQ, PA, ROLE RX,
     START (arms RX listener)
   - Drain PKT lines for burst duration + settle
   - Write each parsed PKT line as a row to rx-log.csv
5. Send ROLE NONE (teardown)
6. Close port

RX log columns: `session,config,pkt_idx,ts_ms,rssi_dbm,snr_db,crc_ok,bit_err,
freq_hz,mod,sf_or_br,bw,pa_dbm,len,pcrc16,captured_ts`

### 4.3 merge_csvs.py

```
merge_csvs.py --tx tx-log.csv --rx rx-log.csv [--out-dir .]
```

Output:
- `combined.csv` — machine-readable: one row per (session, config, pkt_idx),
  TX-side metadata + RX-side packet data (empty if lost)
- `combined-range-report.md` — human-readable PER report

Join logic:
1. Load TX log → per-config: session, config_idx, n_pkts
2. Load RX log → per-packet: session, config, pkt_idx, rssi, snr, etc.
3. For each TX config, expected pkt_idx range = 0..n_pkts-1
4. Inner join on (session, config, pkt_idx) → received packets
5. Left join (TX expected - RX actual) = lost packets (counts toward PER)
6. Extra RX packets whose (session, config) not in TX log = flagged as foreign
7. PER per config = lost / expected
8. Overall PER = total_lost / total_expected

### 4.4 Makefile Targets

```makefile
make range-setup                          # Ansible: provision both machines
make range-tx T0="..." CONFIGS=... BAND=  # TX-only mode (local)
make range-rx T0="..." CONFIGS=... BAND=  # RX-only mode (local)
make range-merge TX=... RX=...            # Merge CSVs
make range-dry-run CONFIGS=...            # Print schedule, no hardware
make range-test-host                      # Run pytest (TDD tests)
```

### 4.5 Ansible Playbook (`ansible/range-setup.yml`)

Runs on `all` hosts in inventory. Tasks:
1. Install packages: `openocd`, `python3-serial`, `python3-pip`
2. Install pyserial via pip
3. Clone/update balloon-e80bench repo at `~/repos/balloon-e80bench`
4. Copy udev rules for CH340 (`85-e80-ch340.rules`)
5. Reload udev
6. Verify: `lsusb` shows CH340 + CMSIS-DAP, `openocd --version`, python3
   imports pyserial, `e80_detect.py --check-deps` passes

Idempotent: every task uses `creates:` or state checks.

## 5. Error Handling

- **No board detected**: `e80_detect.detect_board()` returns `{"error": "..."}`
  with a helpful message. The tool prints this and exits 1 — no stack trace.
- **Config not found**: Clear "config file X not found" message, exit 1.
- **Board unresponsive**: Retry SWD reset up to 2x, then clear error message.
- **No openocd**: SWD reset skipped with warning (not fatal). Board must
  already be alive from firmware 0561b29.
- **Clock skew warning**: If `abs(now - expected_schedule_time) > 5s` when
  a config starts, print a warning (test continues but data may be degraded).

## 6. Testing Strategy (TDD)

Tests in `test_e80_range_split.py`:

1. **Config preset loading** — load JSON, validate required fields
2. **Schedule from preset** — `build_preset_schedule()` returns correct
   absolute start times given T0
3. **TX log format** — columns match spec, partial writes survive
4. **RX log format** — PKT line parsing matches firmware 25-field format
5. **Merge: basic join** — TX+RX with matching packets → correct PER=0
6. **Merge: lost packets** — missing RX packets → PER > 0
7. **Merge: extra/foreign packets** — flagged in report
8. **Merge: multi-config** — >1 config per preset
9. **Dry-run preset** — prints schedule without touching hardware
10. **Auto-detect integration** — mock `detect_board()` returns valid result

All tests are pure-function or mock-based — no serial hardware required.

## 7. File Layout

```
configs/
  outdoor-10.json          # 10 pkts/config, 868 MHz
  indoor-baseline.json      # Indoor bench baseline

firmware/e80-stm32-bench/
  Makefile                  # +range-setup, range-tx, range-rx, range-merge,
                            #  range-dry-run, range-test-host targets
  tools/
    e80_bench_ctl.py        # +--mode tx/rx, +load_config_preset(),
                            #  +run_tx_mode(), +run_rx_mode()
    test_e80_range_split.py # TDD tests for split logic
    merge_csvs.py           # Data merge + report generation
    
ansible/
  range-setup.yml           # Ansible playbook
  range-inventory.ini       # Host inventory (T470 + DQ05)
  85-e80-ch340.rules        # udev rules for CH340

docs/
  DESIGN-distributed-range-test.md  # This document
```
