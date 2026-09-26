# Harmonized Cross-Board Bench — Collaborator Package

**Status:** HARM-T9. This is the entry point for anyone (human or agent) who has
to run, extend, or audit a cross-board bench measurement.
**Board families:** E80 (STM32F103 + LR2021-class), ESP32 (ESP32-C3 + LR2021 via RadioLib), RP2040 (RP2040 + LR2021).

This document is deliberately self-contained: every repository, branch, path, and
command below is spelled out, because two of the names used inside the project
are *not* GitHub repository names (see §1).

---

## 0. The document set

| Document | Read it when you want to… |
|---|---|
| **this file** | find the repos, build and flash a board, run a session, hand data back |
| [`BENCH-CONSOLE-SPEC.md`](BENCH-CONSOLE-SPEC.md) | know the normative wire protocol (`ID?`, `SET`, `N`, `PKT`, `STAT?`, framing) |
| [`harmonization-plan-20260821.md`](harmonization-plan-20260821.md) | see the task chain HARM-T1…T9, acceptance criteria, and what was promised |
| [`HARMONIZED-RESULTS.md`](HARMONIZED-RESULTS.md) | find the results summary table and the 868-vs-2.4-GHz comparability rules |
| [`HARMONIZED-RUN-REPORT-TEMPLATE.md`](HARMONIZED-RUN-REPORT-TEMPLATE.md) | write up a single run |
| [`rca-fix-plan-20260821.md`](rca-fix-plan-20260821.md) | understand the L511 / FLRC-CRC / LEN-255 defects behind the number quirks |
| [`BALLOON-SWEEP-TOOL.md`](BALLOON-SWEEP-TOOL.md) | drive the *legacy* RP2040 multi-radio sweep |
| [`SWEEP-RESULTS.md`](SWEEP-RESULTS.md) | read the legacy RP2040 10-phase sweep results (timing-drift era, pre-harmonization) |

---

## 1. Repository reality check (read before cloning anything)

The plan and the board cards use five names. Only three of them are GitHub
repositories. Getting this wrong wastes a clone attempt.

| Name used in plans | What it actually is | Where it lives |
|---|---|---|
| `balloon-e80bench` | **not a repo.** Local directory name for a clone of `balloon-fresh` that happens to hold the E80 bench tree (`firmware/e80-stm32-bench/`) | `~/repos/balloon-e80bench` on the workstation; upstream = `balloon-fresh` |
| `balloon-range-tests` | **not a repo.** A **branch** of `balloon-fresh` named `range-tests` | `git clone -b range-tests https://github.com/felixfelix-bot/balloon-fresh.git` |
| `balloon-fresh` | the monorepo: E80 bench, RP2040 firmware, ESP32 tracker/mesh tree, docs | `https://github.com/felixfelix-bot/balloon-fresh.git` (public) |
| `esp32-balloon-integration-fresh` | ESP32-C3 + LR2021 tracker/mesh tree, with the forked RadioLib submodule | `https://github.com/felixfelix-bot/esp32-balloon-integration-fresh.git` (private) |
| `esp32-balloon-integration` | public sibling of the above, same default branch | `https://github.com/felixfelix-bot/esp32-balloon-integration.git` (public) |

Branch facts as of this writing:

| Repo | Default branch | HARM work lives on |
|---|---|---|
| `balloon-fresh` | `master` | `main` — **the HARM chain (`harm/t5-bench-console`, BENCH-CONSOLE-SPEC, `tools/balloon_sweep.py`) is on `main`, not `master`.** `main` and `master` have diverged (~1210 / ~775 commits off their merge base); check out `main` for bench work. |
| `balloon-fresh` (branch) | — | `range-tests` — the "balloon-range-tests" track: range runs, bench console, data handover package |
| `esp32-balloon-integration-fresh` | `harm/t3-radiolib-fork` | `harm/t3-radiolib-fork` (the only branch) |

Submodule warning: `esp32-balloon-integration-fresh` carries the forked RadioLib
driver as a git submodule. A fresh clone builds against a **missing** driver
until you initialize it — see §3.2.

---

## 2. Board families, tags, and where they are claimed

`tools/balloon_sweep.py` (`--tx` / `--rx`) accepts exactly three families, and
stamps each board's CSV rows with its tag:

| `--tx/--rx` value | Tag written to `PKT` | Hardware | Firmware tree | Console |
|---|---|---|---|---|
| `e80` | `E80BENCH` | STM32F103C8T6 + E80-900MBL-02 (LR2021-class) | `firmware/e80-stm32-bench/` (balloon-fresh) | `/dev/ttyUSB*` via CH340 |
| `esp32` | `ESP32BENCH` | ESP32-C3 + NiceRF LoRa2021, RadioLib fork | `tracker/firmware/` (esp32-balloon-integration-fresh) | `/dev/ttyACM*` (native USB-CDC) |
| `rp2040` | `RP2040BENCH` | RP2040 + LR2021 | `firmware/rp2040/` (balloon-fresh) | `/dev/ttyUSB*`/`/dev/ttyACM*` |

The console is a **single mechanism across all three**: 115200 8N1 (E80) /
native USB (ESP32, RP2040) with the same `ID?/SET/N/PKT/STAT?` verb set. That is
the whole point of the harmonization — a `PKT` line from an ESP32 and a `PKT`
line from an E80 are the same 25-column record and can be merged mechanically.

Ports are **not stable**. The CH340 bridges re-enumerate on every power cycle;
ESP32 boards change `/dev/ttyACM*` on replug. Always hard-verify before flashing:

```bash
esptool.py --port /dev/ttyACM0 chip_id      # ESP32 family
python3 firmware/e80-stm32-bench/tools/e80_detect.py   # E80 family
```

Board access is mutually exclusive. Before touching any board, take the shared
lock and release it afterwards — concurrent flashing corrupts boards:

```bash
BALLOON_TRACK=<track> python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py acquire <board> \
    --purpose "<what you are doing>" --timeout 120
BALLOON_TRACK=<track> python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py release <board>
```

---

## 3. Build and flash, per family

### 3.1 E80 (STM32F103 + E80-900MBL-02)

```bash
git clone https://github.com/felixfelix-bot/balloon-fresh.git
cd balloon-fresh && git checkout main
cd firmware/e80-stm32-bench

make                 # build the bench firmware (arm-none-eabi-gcc)
make flash           # SWD, auto-detects the probe (openocd)
```

First flash on a stock board **must** go over SWD; the UART/`stm32flash` path is
dead on stock firmware (the ROM bootloader is not left resident). Details, the
BOOT0 procedure, and the stock-firmware dump/restore commands are in
[`firmware/e80-stm32-bench/FLASHING.md`](../firmware/e80-stm32-bench/FLASHING.md).

Operate a run:

```bash
make tx              # TX mode — T0 + SESSION_ID auto-generated
make rx              # RX mode — capture to rx-log
make range-merge     # merge TX+RX logs, compute PER, generate report
make range-check     # post-stop gap check, write a re-send preset
```

### 3.2 ESP32 (ESP32-C3 + LR2021 via RadioLib fork)

```bash
git clone https://github.com/felixfelix-bot/esp32-balloon-integration-fresh.git
cd esp32-balloon-integration-fresh

# REQUIRED FIRST STEP — the LR2021 driver is a submodule; without this the
# build fails or silently uses nothing:
git submodule update --init --recursive
# (equivalently: git clone --recurse-submodules ...)

source ~/esp/esp-idf/export.sh
cd tracker/firmware
idf.py build
idf.py -p /dev/ttyACM0 flash monitor
```

The RadioLib submodule points at `github.com/felixfelix-bot/RadioLib`, branch
`lr2021-flrc-511-match123`, and is what provides the two features this family
contributes to the harmonized protocol: 511-byte FLRC payloads and
`setFlrcSyncWordMatch()` (Match1 / Match1+2 / Match1+2+3). The equivalent patch
is mirrored in `patches/radiolib-lr2021-flrc511-match123.patch`, so the driver
can be reconstructed without the submodule if its remote is unavailable. See
`docs/radiolib-fork.md` for the update policy.

### 3.3 RP2040 (+ LR2021)

```bash
cd balloon-fresh && git checkout main     # RP2040 tree is in the same repo
cd firmware                               # the rp2040-* targets live in firmware/Makefile
make rp2040-build        # or: cd rp2040 && pio run
make rp2040-flash
make rp2040-monitor
```

(`firmware/rp2040/Makefile` additionally offers per-role targets —
`build-tx`/`build-rx`/`build-both`, `flash-tx`/`flash-rx`/`flash-both`,
`monitor-tx`/`monitor-rx`, `capture`, `capture-stop`, `ports`, `walks`. The
`rp2040-*` names in `firmware/rp2040/README.md` are the `firmware/Makefile`
targets, so run them from `firmware/`.)

### 3.4 The `range-tests` branch (a.k.a. "balloon-range-tests")

```bash
git clone -b range-tests https://github.com/felixfelix-bot/balloon-fresh.git balloon-range-tests
cd balloon-range-tests && git checkout range-tests
```

This branch carries the range-run work and its own data handover package
(`docs/`). It shares the bench console and the per-family build/flash steps in
§3.1–§3.3; the branch-specific bench-console usage is documented in its own
`AGENTS.md`/`README.md`.

---

## 4. Running a harmonized session

The driver is `tools/balloon_sweep.py` (v1.0.0) in `balloon-fresh`.

```bash
cd balloon-fresh && git checkout main

# 1. pre-hardware plan check — enforces the spec, touches nothing
python3 tools/balloon_sweep.py --tx e80 --rx esp32 --session <yymmddHHMM> --dry-run

# 2. refuse-to-run guards are real: an illegal band/pair/LEN/GAP combination
#    exits non-zero with
#      REFUSED (pre-hardware, spec enforcement): <reason>
#    Fix the plan; do not work around it.

# 3. the real run
python3 tools/balloon_sweep.py --tx e80 --rx esp32 --session <yymmddHHMM>

# 4. re-run a subset (e.g. after a STAT? drop, with GAP doubled)
python3 tools/balloon_sweep.py --tx e80 --rx esp32 --session <yymmddHHMM> --only 5 7 11

# 5. custom output
python3 tools/balloon_sweep.py --tx rp2040 --rx esp32 --session <yymmddHHMM> \
    --out-prefix data/e80-bench/<session>-<pair>-<band>/
```

Useful flags: `--tx-port/--rx-port` (pin a serial device), `--tx-probe/--rx-probe`
(pin an E80 SWD probe serial), `--only IDX...`, `--out-prefix`, `--dry-run`.

Rules that the tool enforces and that make results comparable (spec §6–§9):

| Rule | Consequence if violated |
|---|---|
| `LEN ≤ 255` for LoRa, `≤ 511` for FLRC | `REFUSED ... LEN <n> > cap <cap> for <mod> (spec S6)` — row is *refused*, not 0 % |
| `GAP ≥ 40 000 µs` whenever `LEN > 256` | `REFUSED ... GAP <n>us < 40000us required for LEN <n> > 256 (spec S7)` — large frames overrun the RX FIFO |
| Frequency must be inside the pair's band plan | `REFUSED ... FREQ <hz> not allowed for pair <TX><-><RX> (spec S9)` |
| Cross-board FLRC uses Match123 + sync `0x12AD101B` + chip CRC ON | Results are not comparable with the legacy E80↔E80 config (Match1, sync `2D D4 D4 B2`) |

### Output layout (what a session must produce)

```
data/e80-bench/<session>-<pair>-<band>/
  <prefix>-summary.csv     # one row per config, machine-readable
  <prefix>-pkts.csv        # one row per received packet
  <prefix>-report.md       # human summary (see the report template)
  <prefix>-meta.json       # session id, boards, probes, fw SHA, environment
```

Join keys: `session`, `config`, `pkt_idx`; `replicate` disambiguates re-runs of
the same config. `CONFIG_START,<config>,<replicate>,<ts_ms>` marker lines bracket
each config segment, so a partially failed config can be cut out without
guessing. Row format and the `#`-prefixed header convention are documented in
[`data/README.md`](../data/README.md).

### Handing data back

1. Commit `docs/runs/<run-id>.md` (from
   [`HARMONIZED-RUN-REPORT-TEMPLATE.md`](HARMONIZED-RUN-REPORT-TEMPLATE.md)) and
   the four CSV/JSON artifacts **in one commit**, so the numbers and their
   evidence share a revision.
2. Add the run's rows to [`HARMONIZED-RESULTS.md`](HARMONIZED-RESULTS.md) in the
   matching pair × band table, link the raw CSV, and update §1 "Data status".
3. Report anything anomalous even if the run passes. The known ones to check
   for are listed in the report template §8.

---

## 5. What is still missing (honest ledger)

This package is complete as *documentation*. It is not complete as *evidence*.

| Item | State | Blocker |
|---|---|---|
| E80 ↔ ESP32 @868 (HARM-T7) | **no data, no runs** | card un-run; no sweep CSVs exist on any branch |
| E80 ↔ RP2040 @868 (HARM-T8) | **no data** | card marked done but produced no CSVs, no `harm/t8-results` branch |
| ESP32 ↔ RP2040 @868 | **no data** | never attempted |
| ESP32 ↔ RP2040 @2440 | **no data** | the measurement that would close "does the forked RadioLib 2.4 GHz RX path receive?" |
| E80 ↔ E80 (both bands) | measured, pre-harmonization tool | usable only as the regression baseline; see `HARMONIZED-RESULTS.md` §2.1/§3.1 |
| LEN 254/255/256 boundary bisect | open | `rca-fix-plan-20260821.md` BUG 3; needed before LEN-255 comparisons are trustworthy |
