# FW-6 — Dispatch layer, decision table + wiring (t_561d8a41)

Module: `firmware/rp2040/src/flrc_range_host_dispatch.{h,cpp}` (pure TU)
Tests: `firmware/rp2040/host-tests/test_dispatch.cpp` (TDD: RED → GREEN)
Wiring: `firmware/rp2040/src/flrc_range_host.cpp` (main TU = plan executor)
Plan: `host-driven-bench-plan.md` REV-2 §B1 / kanban t_561d8a41

## What shipped

The M1-fix dispatch layer: `bench_apply_cmd(state, cmd) -> plan` with the
plan carrying `{reinit_full | start_burst | stop | none, err, band_aware}`.
**Zero Arduino includes** — its own TU linking only the FW-2 parser, FW-4
safety and FW-3 stats TUs, so the entire decision table runs in host unit
tests. The Arduino main is now a thin *executor*: parse → dispatch → reply
string → plan execution against the FW-5a backend.

## Decision table (every row locked in test_dispatch.cpp)

| command             | IDLE                         | ACTIVE                     |
|---------------------|------------------------------|----------------------------|
| MOD / FREQ / PA/LEN | `REINIT_FULL` (state applied)| `ERR BUSY` (state intact)  |
| ROLE / N / GAP / POWER | applied, `NONE`           | `ERR BUSY` (ext., below)   |
| START               | role=NONE → `ERR INHIBITED`; else stats RESET → ACTIVE → `START_BURST` | `ERR BUSY` |
| STOP                | OK, `NONE` (ext., below)     | `STOP`, stats **RETAINED** |
| ID? / HELP / STAT?  | OK, `NONE`                   | OK, `NONE` (never BUSY)    |

Guards:

- **PA**: parser range −18..22; `PA > 10` without `POWER MODE OUTDOOR 2026`
  unlock → `ERR POWER-LOCKED` (via `bench_safety_pa_allowed`, FW-4). Unlock
  is sticky; re-lock = reboot.
- **FREQ**: parser clamps 863..870 MHz **and** dispatch re-checks via
  `bench_safety_freq_in_eu_band()` — a hand-built cmd struct that bypassed
  the parser (tested with 915 MHz) still gets `ERR RANGE`.
- **band_aware flag**: true when the applied delta touches the modulation /
  front-end block — MOD param delta (FLRC↔LoRa, bitrate, SF/BW) or FREQ
  delta (CALIB_FRONT_END parameter). PA/LEN and no-op re-applies → false.
  Executor must run the full B1 band-aware re-init when flagged.
- **STOP semantics**: abort → standby; counters readable via STAT? until
  the next START wipes them (`bench_stats_reset` at START). Tested through
  a fabricate → START(reset) → accumulate → STOP(retain) → STOP(idle OK) →
  START(reset) cycle.

## Documented FW-6 extensions of §1

§1 lists no error class for ROLE / N / GAP / POWER mid-session and no
STOP-while-IDLE behavior. FW-6 closes both conservatively:

1. **Only queries are legal while ACTIVE** — ROLE / N / GAP / POWER also
   return `ERR BUSY`. Rationale: deterministic burst parameters (stats
   comparability requires frozen n/len/gap mid-burst) and a role flip
   mid-burst is physically meaningless on one radio.
2. **STOP while IDLE → OK, no action** (idempotent standby), stats kept.

Both are called out in the HELP text so operators see them.

## Wiring (flrc_range_host.cpp)

- Boot: `bench_state_init` (§1 STAT-example defaults: FLRC 650k @ 869.525,
  10 dBm, LEN 51 / N 1000 / GAP 5000) → `bench_radio_hardware_begin()` →
  `bench_radio_full_init(cfg)`; failure only disables re-init execution
  (config still stored; HW-B1 catches hardware issues).
- `RH_PLAN_REINIT_FULL` → `bench_radio_cfg_valid()` guard → `bench_radio_reinit()`
  (FW-5a; full band-aware sequence, so `band_aware` is advisory but kept
  for the executor/HS-2 audit trail).
- `START_BURST` / `STOP` → marked hookup points for FW-7/FW-8 engines.
- Banner + ID? now come from `bench_format_id()` (`ID range-host v1
  fw=<hash> role=<r>`); `FW_HASH` injectable via `-DFW_HASH`, `dev` locally.
- STAT? still falls back to `ERR UNKNOWN STAT?` until the FW-9 formatter
  (reply vocabulary unchanged — no conformance test broken).
- HELP text is emitted by `bench_help_text()` and includes the REV-2-mandated
  STOP-stats-retained and PA-unlock notes.

## RED → GREEN record

- RED: `make -C firmware/rp2040/host-tests test_dispatch` →
  `No rule to make target '../src/flrc_range_host_dispatch.cpp'`
  (module absent — full decision-table test written first).
- GREEN (after implementing the TU, first run):
  `test_dispatch: ALL PASS` — 17 test groups, ~150 CHECKs, built with
  `-std=c++17 -Wall -Wextra -Werror`.

## Gates

- `make -C firmware/rp2040/host-tests` — 6/6 binaries build clean
  (stats, safety, cmd, bw_codes, radio, dispatch), all pass.
- `python3 -m pytest tools/test_range_bench_ctl.py -q` — 88 passed.
- `pio run -e rp2040-range-host` — SUCCESS (31.6 s).
- Untouchable trio untouched: ESP32 bridge .ino / tools/range_bench_ctl.py /
  docs/PLAN-host-driven-bench.md not in `git status`.
- Diff scope: dispatch TU (2 new), test_dispatch.cpp (new), Makefile
  (+1 target, TESTS list), flrc_range_host.cpp (stub → executor),
  .gitignore (+1 binary).

## Notes for reviewers / next tasks

- FW-7/FW-8 engines own `stats.t_start_us`/`t_stop_us` stamping; dispatch
  resets counters at START only.
- HS-2 late-binding kill: add a STAT?-conformance test against the FW-9
  firmware; reply formats here (`OK START n= len= gap_us=`, `OK START RX`,
  `OK MOD ...`) are the FW-6 half of that contract.
- The worktree AGENTS.md still carries the stale tollgate identity (FW-0
  supersede never landed) — orthogonal to FW-6, flagged for the manager.
