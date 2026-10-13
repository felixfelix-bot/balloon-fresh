# Host-Driven Range Bench — Build-Ready Plan (RP2040 + Host Controller)

**Repo:** `~/repos/balloon-fresh` (git remote `github` = felixfelix-bot/balloon-fresh)
**Integration target branch:** `range-tests` (HEAD `655d094`)
**Prepared:** 2026-08-17 · All facts below verified against the actual trees.

---

## 0. Key Decisions (verified against repo state)

| Decision | Choice | Rationale (evidence) |
|---|---|---|
| Branch | **`feat/host-driven-bench` off `range-tests`** (655d094), NOT off main | The proven LR2021 SPI/radio init code to reuse (`flrc_range_tx_sweep.cpp` `rfSwitchBitrate()` L221-240, `rawInitRadio()` L273-347; RX RSSI readback `0x024B` in `flrc_range_rx_sweep.cpp` L158-201) exists **only on range-tests**. Main lacks it. |
| Worktree | **`~/worktrees/host-driven-bench`** (new worktree for the new branch) | `range-tests` is already checked out at `~/worktrees/balloon-range-tests` (the integration/review tree) — don't disturb it. Matches existing `~/worktrees/*` convention (15 worktrees present). |
| Conflicted files policy | **Zero edits to `flrc_range_tx_auto.cpp` (21 committed `<<<<<<<` blocks), `flrc_range_rx_auto.cpp` (18), `flrc_range_rx_gps.cpp` (22)** — census via `git grep -c "^<<<<<<< " range-tests -- firmware/rp2040/src/`. These markers are *committed* (worktree is clean), i.e. a historical bad merge. The plan adds **new files only + appends one env block to `platformio.ini`** (not conflicted), so the Stage-E merge to range-tests cannot conflict. Resolution of the auto/gps trio is a separate out-of-scope card. |
| Build env | **Single env `[env:rp2040-range-host]`, runtime ROLE** (one binary, flashed once, `ROLE TX\|RX` over console) | Host-driven = no reflashing per role. Matches task recommendation. Env template copied from `[env:rp2040-range-tx-sweep]` (platformio.ini L594-611): earlephilhower core, `build_src_filter = -<*> +<flrc_range_host*.cpp>`, picotool upload. |
| Radio code source | **Sweep firmware LR2021 raw-SPI backend** (TX: `flrc_range_tx_sweep.cpp`; RX RSSI: `flrc_range_rx_sweep.cpp`) — NOT E80 radio code | E80 bench is STM32+SX1280@2.4GHz; LR2021 registers/sequences differ. Port from E80 only: protocol, Wilson math, safety math, host-script architecture. |
| Host script location | **`tools/range_bench_ctl.py` + `tools/test_range_bench_ctl.py`** (repo root `tools/`, range-tests worktree) | Must `import board_serial` (BoardSerial wrapper, `tools/board_serial.py`) — same dir import works from any CWD. |
| Firmware host-test seam | Pure modules compiled by **`firmware/rp2040/host-tests/Makefile` + system g++** (no Arduino includes in `*_cmd/_stats/_safety.cpp`) | Mirrors E80 `make test-host` (cmake+ctest) but simpler; enables Stage-A TDD with no hardware. |

### ⚠ Two discovered gotchas the plan bakes in
1. **ESP32 bridge v7 auto-resets the RP2040 after 30 s of UART silence** (`firmware/esp32-uart-bridge/src/main.cpp` watchdog in `loop()`). The new firmware MUST print a heartbeat line on `Serial1` (≤10 s period) or long RX listens / idle waits get the board reset out from under the host. → requirement in FW-9, verified in HW-B1.
2. **`tools/board_serial.py` PORT_TO_RESOURCE is stale**: maps ttyACM0→rx(8332 board), ttyACM3→tx(F242D). Current hardware per brief: **F242D on ttyACM1, bridge on ttyACM0**. Ports move on replug; mapping must be re-verified before Stage B. → task HW-B0.

---

## 1. Console Protocol v1 (spec for workers)

Single-line, case-insensitive commands, `\r\n`-terminated, accepted on **both USB CDC (`Serial`) and UART (`Serial1` → ESP32 bridge)**; every reply echoed on both. Mirrors E80 `bench_cmd.c` grammar.

| Command | Valid args | Reply | Errors |
|---|---|---|---|
| `ID?` | — | `ID range-host v1 fw=<hash> role=<r>` | — |
| `ROLE TX` / `ROLE RX` / `ROLE NONE` | — | `OK ROLE <r>` | `ERR ARG` |
| `MOD FLRC <br_kbps>` | br ∈ {260,325,520,650,1040,1300,2080,2600} | `OK MOD FLRC br_hz=<n>` (+re-init) | `ERR RANGE` |
| `MOD LORA <sf> <bw_khz>` | sf 5–12; bw ∈ {125,250,500} | `OK MOD LORA sf=<n> bw_hz=<n>` (+re-init) | `ERR RANGE` |
| `FREQ <hz>` | **863_000_000–870_000_000** (EU SRD, LF path, hard clamp v1 — no override) | `OK FREQ <hz>` (+re-init) | `ERR RANGE` |
| `PA <dbm>` | −18..+22; **>10 requires prior `POWER MODE OUTDOOR 2026`** | `OK PA <dbm>` (+re-init) | `ERR RANGE` / `ERR POWER-LOCKED` |
| `LEN <bytes>` | 8–255 (4B seq + payload; 255 = FLRC FIFO max, sweep fw `fifoCmd[2+255]`) | `OK LEN <n>` | `ERR RANGE` |
| `N <count>` | 1–1_000_000 | `OK N <n>` | `ERR RANGE` |
| `GAP <us>` | 100–100_000_000 | `OK GAP <n>` | `ERR RANGE` |
| `POWER MODE OUTDOOR <pin>` | pin==2026 | `OK POWER OUTDOOR` | `ERR ARG` |
| `START` | role ∈ {TX,RX} set (two-step TX inhibit) | `OK START n= len= gap_us=` (TX) / `OK START RX` | `ERR INHIBITED` / `ERR BUSY` |
| `STOP` | — | `OK STOP` (standby, session frozen) | — |
| `STAT?` | — | one line, see below | — |
| `HELP` / `?` | — | command list | — |

**STAT? reply (keys chosen so E80 `parse_stat()` port stays ~verbatim):**
```
STAT role=TX mod=FLRC br_hz=650000 freq_hz=869525000 dbm=10 len=51 n=1000 gap_us=5000
     sent=1000 sent_ok=1000 rx=0 crc_err=0 per_x1e6=0 per_ci_x1e6=[0,3764]
     rssi_avg_dbm=-128.0 rssi_min_dbm=-128.0 snr_avg_db=0.0 kbps=641.2 elapsed_s=6.2 state=IDLE
```

**Re-init rule:** any `MOD/FREQ/PA/LEN` while IDLE ⇒ full re-apply exactly per `rfSwitchBitrate()` (STDBY_RC `02 00 01` → MOD_PARAMS → CALIBRATE `01 22 5F` → CLEAR_IRQ `02 0B 02`). While a session is active ⇒ `ERR BUSY` (host must `STOP` first).

**Safety state machine:** boot → `role=NONE`, TX inhibited. TX requires `ROLE TX` **then** `START` (two-step). `ROLE NONE`/STOP re-inhibits. GAP semantics identical to E80 `bench.c` L789: next TX begins when `now − t_tx_done_us ≥ gap_us` (air-time paced; UART latency irrelevant).

**Burst packet format** (from sweep fw): bytes 0–3 = big-endian seq, payload = incrementing pattern; final packet = `DE AD BE EF` + 4B total-count (RX-side sanity anchor).

---

## 2. Task Breakdown

Legend: **[HW]** = hardware needed (boards plugged / Felix at bench). Est = minutes. Each task = ≤2 deliverables, TDD-able, one atomic commit.

### Lane FW — firmware (worktree `~/worktrees/host-driven-bench`)

**FW-1 · Scaffold branch, worktree, env, stub main** · est 30 · deps: —
- Deliverables: (1) worktree + branch + `[env:rp2040-range-host]` appended to `firmware/rp2040/platformio.ini`; (2) `src/flrc_range_host.cpp` stub: setup() inits `Serial`+`Serial1` @115200, banner `ID range-host v1 role=NONE tx_inhibited=1`, echoes any line with `ERR UNKNOWN`.
- Files: `firmware/rp2040/platformio.ini` (append only), `firmware/rp2040/src/flrc_range_host.cpp` (new).
- Test: `pio run -e rp2040-range-host` → exit 0.
- Evidence: build log tail in commit message. Gate: none (Stage-A sub-step).

**FW-2 · Pure command parser + host-test harness seam** · est 45 · deps: FW-1
- Deliverables: (1) `src/flrc_range_host_cmd.{h,cpp}` — port of E80 `bench_cmd.c` (tokenizer, `bench_strcaseeq`, `parse_u32/i8`, overflow guards) adapted to §1 grammar (adds standalone LEN/N/GAP cmds, drops BAND/FLASH); (2) `firmware/rp2040/host-tests/` = `Makefile` (g++ pattern rule) + `test_cmd.cpp` ported from E80 `tests/test_bench_cmd.c` vectors (valid cmds, each ERR class, case-insensitivity, overflow).
- Files: `flrc_range_host_cmd.{h,cpp}`, `host-tests/Makefile`, `host-tests/test_cmd.cpp` (all new).
- Test: `make -C firmware/rp2040/host-tests` → all PASS. TDD: commit failing tests first, then port.
- Evidence: test output in commit.

**FW-3 · Pure stats module (Wilson 95% CI)** · est 30 · deps: FW-1
- Deliverables: `src/flrc_range_host_stats.{h,cpp}` — verbatim integer port of E80 `bench_stats.c` (`bench_isqrt64`, `wilson_ppm`, `per_ppm`, stats struct/reset) to C++ + `host-tests/test_stats.cpp` with E80 `tests/test_bench_stats.c` vectors incl. S==N ⇒ exactly 1_000_000 ppm edge.
- Test: `make -C firmware/rp2040/host-tests`.

**FW-4 · Pure safety math module** · est 45 · deps: FW-1
- Deliverables: `src/flrc_range_host_safety.{h,cpp}` — port `bench_safety.c` airtime (LoRa AN1200.24-style, FLRC ×4/3 coded), `tx_timeout_ms = airtime×2+50 clamped [100,60000]`, loop backstop check; ADD: `freq_in_eu_band(hz)`, `pa_allowed(dbm, outdoor_unlocked)`. DROP: STM32 IWDG prescaler math (RP2040 uses SDK `watchdog_enable` directly — document in header).
- Files: + `host-tests/test_safety.cpp` (E80 vectors + new EU-band/PA-cap vectors).
- Test: `make -C firmware/rp2040/host-tests`.

**FW-5 · Radio backend port (TX+RX)** · est 45 · deps: FW-1
- Deliverables: `src/flrc_range_host_radio.{h,cpp}` — copy verbatim from sweep fw: `rfWaitBusy/rfWriteCmd/rfReadStatus/rfReadIrqStatus/rfClearIrq/rfSetTx/rfWriteTxFifo/rfClearTxFifo/rfSetFreq/rfSetBitrate/rfSetTxPower/rfSetPktSize/rfSwitchBitrate/rawInitRadio` (`flrc_range_tx_sweep.cpp` L85-347) + RX side: FIFO read, `GET_FLRC_PACKET_STATUS 0x024B` 9-bit RSSI assembly, `GET_RSSI_INST 0x020B` (`flrc_range_rx_sweep.cpp` L158-201) + LoRa LF init from `lora_868_tx.cpp`. Parameterize freq/br/power/pktlen as struct (no #defines).
- Test: `pio run -e rp2040-range-host` compiles (linked into stub). No unit test (raw register code — hardware-validated in Stage B).
- Evidence: build log; diff shows copy provenance comments.

**FW-6 · Command dispatch → radio actions (pure plan layer)** · est 45 · deps: FW-2, FW-5
- Deliverables: (1) pure `bench_apply_cmd(state, cmd) → action_plan` (which radio calls + ERR reason) in `flrc_range_host.cpp` section guarded `#ifndef HOST_TEST`; host-testable without radio; (2) wiring: MOD/FREQ/PA/LEN handlers call re-init, ID?/HELP/STAT? replies per §1.
- Test: extend `host-tests/test_cmd.cpp` (dispatch decision table: re-init on each config cmd, `ERR BUSY` while active, `ERR INHIBITED` START w/o ROLE TX, `ERR POWER-LOCKED` PA>10 locked, FREQ clamp) + pio build.

**FW-7 · TX burst engine (air-time paced)** · est 45 · deps: FW-6, FW-4
- Deliverables: `START` TX path in `flrc_range_host.cpp`: per-packet `rfClearIrq→rfClearTxFifo→rfWriteTxFifo→rfSetTx`, spin on `sio_hw->gpio_in` IRQ bit (sweep pattern L378-398), GAP pacing `now − t_done ≥ gap_us` (E80 bench.c L789 pattern), seq numbering + DEADBEEF end marker, stats accumulation (`sent/sent_ok/timeouts`), hardware watchdog: `watchdog_enable(tx_timeout_ms)` before each TX, `watchdog_update()` on IRQ; loop backstop force-STDBY+abort on overrun.
- Test: pio build green; pure pacing/backstop helpers unit-tested in `host-tests/test_safety.cpp` extension.
- Evidence: build + unit output.

**FW-8 · RX engine (count + per-packet RSSI)** · est 30 · deps: FW-6, FW-3
- Deliverables: `START` RX path: set RX continuous, poll IRQ/packet flags, read FIFO, verify payload pattern + seq window, accumulate `rx_ok/crc_err/rssi_sum/min/max/snr_sum`, first/last seq for PER (`per_ppm` port), STOP on `STOP` cmd or session end.
- Test: pio build green. (RSSI math assembly unit-testable only w/ synthetic SPI buf — optional stretch test in host-tests.)

**FW-9 · STAT? line, STOP, heartbeat, safety integration** · est 30 · deps: FW-7, FW-8
- Deliverables: (1) `STAT?` single-line formatter per §1 (pure function `format_stat(state, stats, buf)` — unit-tested); STOP → STDBY + freeze; (2) **heartbeat**: every 10 s on Serial1+Serial `HB uptime_ms=<n> role=<r> state=<s>` (feeds ESP32-bridge 30 s silence watchdog — gotcha #1); TX-inhibit state machine final review (boot NONE, two-step, ROLE NONE re-inhibits).
- Test: `make -C firmware/rp2040/host-tests` (new `test_stat_fmt.cpp` or extension) + pio build.

**FW-10 · Stage-A integration build + dry protocol run (virtual)** · est 30 · deps: FW-9
- Deliverables: full `pio run -e rp2040-range-host` release build `-O2 -Wall` **zero warnings**; console loop multiplexes Serial+Serial1 line buffers; commit protocol transcript from a PTY fake-echo? (No — that's HS-5.) Deliverable = build log + `git diff --stat` proof-of-no-touch on conflicted trio.
- Test: `pio run -e rp2040-range-host && git diff range-tests --stat -- firmware/rp2040/src/ | grep -v "^ .*flrc_range_host" | wc -l` → 0 (no other src file touched).
- **Gate A (firmware half) evidence:** build log + host-tests PASS log committed under `docs/evidence/stage-a/`.

### Lane HS — host script (same worktree)

**HS-1 · Scaffold + pure helpers port** · est 45 · deps: FW-1 (branch exists; else none)
- Deliverables: (1) `tools/range_bench_ctl.py` skeleton (argparse per §7: `--tx-port/--rx-port/--matrix/--anchor/--csv/--site/--stop/--dist-m/--repeat/--freq/--dbm/--n/--len/--gap/--t0/--rx-lead/--dry-run`, `MOD_DEFS` incl. `flrc650/flrc2600/sf7/sf12`); pure fns ported from E80: `lora_airtime_s/flrc_airtime_s/airtime_s/make_cell/n_for_mod/build_matrix_cells/parse_t0/build_stop_schedule/freq_gate/fmt_offset`; (2) `tools/test_range_bench_ctl.py` — port matching test classes from `test_e80_bench_ctl.py` (`AirtimeTests/NRegimeTests/MatrixCellTests/ScheduleTests/FreqGateTests`).
- Test: `python3 -m pytest tools/test_range_bench_ctl.py -q` (also unittest-compatible).

**HS-2 · STAT parser + CsvLog port** · est 30 · deps: HS-1
- Deliverables: `parse_stat()` (E80 L193-237 port, our STAT keys are a superset — keep legacy tolerance) + `CsvLog` class (append-only, header-once, `#` stop-metadata comments, CSV_COLUMNS exactly `site,stop,dist_m,repeat,mod,len,pa,freq_hz,n,sent,recv,per,per_ci_lo,per_ci_hi,rssi,snr,kbps,elapsed_s,timestamp`) + tests (`ParseStatTests`, new `CsvLogTests`: header-once, append-only, comment format).
- Test: pytest as above.

**HS-3 · BoardSerial integration + port/lock layer** · est 30 · deps: HS-1
- Deliverables: `BoardCtl` class: opens port(s) via **`from board_serial import BoardSerial`** (never raw `serial.Serial`), `cmd()/query()` wrappers with `OK/ERR/STAT/ID` prefix matching + timeout, drain/discard boot banner, ID? handshake (`role=` field check); FakeBoard test double (port from E80 `test_e80_bench_ctl.py` `FakeBoard`) enabling full-runner tests without hardware.
- Test: pytest with FakeBoard (no hardware).

**HS-4 · Session runner (arm→schedule→burst→CSV)** · est 45 · deps: HS-2, HS-3
- Deliverables: `run_session()`: single-host bench mode (rx arm `rx_lead` early, tx at scheduled epoch, poll STAT? till `state=IDLE` + timeout = expected×1.5+30 s, append row) and range modes (only one of `--tx-port/--rx-port` given → runs that half against the same T0 schedule); Ctrl-C → STOP both + `# ABORTED` comment; per-cell drift check (warn if arrival >2 s late vs schedule).
- Test: pytest end-to-end against FakeBoard pair incl. abort path.

**HS-5 · Dry-run rehearsal mode (Gate A host half)** · est 30 · deps: HS-4
- Deliverables: `--dry-run` prints the full command script + schedule table + would-be CSV rows, opens **no ports**; transcript of `--matrix flrc650,flrc2600,sf7,sf12 --anchor --dry-run` saved.
- Test: pytest asserts dry-run output lines; transcript committed `docs/evidence/stage-a/dryrun-matrix.txt`.
- **Gate A (host half) evidence:** pytest green + dry-run transcript.

**HS-6 · T0/NTP discipline + docs-in-script** · est 15 · deps: HS-4
- Deliverables: `--t0` accepts `YYYY-MM-DD HH:MM[:SS]`, ISO `T` form, or int epoch; refuses start if `now > t0`; `--t0-ntp` reads system clock only after `timedatectl show -p NTPSynchronized` check (warns, requires `--i-trust-clock` to proceed unsynced). Module docstring documents two-laptop NTP procedure.
- Test: pytest for parse + refusal.

### Lane HW — Stage B (single board; **[HW]** = F242D Pico + bridge + attenuator/cage; FLASH-QUEUE approval required before any flash, per repo AGENTS.md)

**HW-B0 · [HW] Port census + board_serial map fix** · est 20 · deps: FW-1
- Deliverables: probe `/dev/ttyACM0/1` (bridge banner `=== ESP32 UART Bridge v7 ===` vs Pico USB CDC), record F242D port; update `tools/board_serial.py` `PORT_TO_RESOURCE` to current reality (gotcha #2) or add explicit `--lock-name`; verify `balloon-board-lock.py acquire/check/release` cycle for the resource.
- Evidence: lock check exit codes + diff of map.

**HW-B1 · [HW] Flash + bridge pass-through + heartbeat verify** · est 30 · deps: FW-10, HW-B0, FLASH-QUEUE approval
- Deliverables: flash `rp2040-range-host` via bridge `BOOTSEL` cmd + `pio -t upload` (lock held); verify `ID?` answered identically over **both** direct USB CDC and via bridge ttyACM0; leave idle ≥60 s and confirm NO bridge watchdog reset (heartbeat working — gotcha #1).
- Evidence: session log with two ID? replies + uptime continuity.

**HW-B2 · [HW] Cage TX sanity + safety interlocks** · est 45 · deps: HW-B1
- Deliverables: attenuator/cage on antenna; run `MOD FLRC 650 / FREQ 869525000 / PA 0 / LEN 51 / N 100 / GAP 5000 / ROLE TX / START / STAT?` → assert `sent=100 sent_ok=100`, elapsed plausible (≈100×(airtime+5 ms)), `per_ci` present; negative tests: `START` before `ROLE TX` → `ERR INHIBITED`; `FREQ 2400000000`→`ERR RANGE`; `PA 30` → `ERR RANGE`; `PA 14` w/o unlock → `ERR POWER-LOCKED`; MID-burst `STOP` → clean stop.
- Evidence: full transcript + first CSV row via `range_bench_ctl.py --tx-port ... --csv docs/evidence/stage-b/cage.csv`.
- **Gate B evidence:** transcript + CSV + FLASH-QUEUE row DONE.

**HW-B3 · [HW] LoRa path + airtime cross-check** · est 30 · deps: HW-B2
- Deliverables: `MOD LORA 12 125` cage burst N=50 → STAT? sane; compare measured `elapsed_s` vs `lora_airtime_s()` prediction (±15%); GAP floor check FLRC-2600 (GAP=100) — no FIFO underrun timeouts.
- Evidence: transcript + one CSV row.

### Stage C — two-board link (DEFERRED / BLOCKED — 2nd Pico with colleague)

**HW-C1 · [HW][BLOCKED] Two-board matrix session** — dep: 2nd Pico returns + Gate B. Arm RX board via second host with shared `--t0`, run full `--matrix`, verify PER monotonic-ish vs distance, CSV complete.
**HW-C2 · [HW][BLOCKED] Cross-family smoke (old sweep fw ↔ new host fw)** — interop check against `flrc_range_rx_sweep` if 2nd board runs old fw.
Keep both cards created-but-blocked; nothing in Stages A/B/D/E depends on them.

### Stage D — cross-family cold review

**RV-1 · Cold review package** · est 30 · deps: Gate A (Stage B optional but recommended first)
- Deliverables: `git diff range-tests...feat/host-driven-bench --stat` showing **only new files + platformio.ini append**; reviewer checklist (protocol §1 conformance, safety two-step, no raw serial.Serial, no edits to conflicted trio, atomic commits, docs-in-commit); route to a cross-family reviewer (different track) per quality gates; address findings.
- Evidence: review sign-off comment + fix commits.

### Stage E — docs + merge

**DOC-1 · README-host-driven-bench.md** · est 30 · deps: RV-1
- Deliverables: `docs/README-host-driven-bench.md` (repo-root `docs/` in worktree): wiring (Pico GP12/13↔bridge GPIO3/2), flash procedure incl. FLASH-QUEUE, protocol table §1, script usage (bench single-host / range two-host T0+NTP), CSV schema, safety model (two-step, EU clamp, PA unlock, watchdogs incl. bridge 30 s rule), Stage B/C evidence links.
- Test: n/a (docs-in-commit gate).

**MRG-1 · Merge to range-tests + push verified** · est 20 · deps: DOC-1, Gate B
- Deliverables: merge `feat/host-driven-bench` → `range-tests` (only-additive diff ⇒ trivial), `git push github range-tests`, verify remote HEAD; ngit sync optional per repo convention.
- Evidence: push output + remote SHA match. **Gate E complete.**

---

## 3. Dependency Graph & Parallelization

```
FW-1 ──┬─► FW-2 ──┐
       ├─► FW-3 ──┼─► FW-6 ──┬─► FW-7 ──┐
       ├─► FW-4 ──┘          └─► FW-8 ──┼─► FW-9 ─► FW-10 ─► [GATE A fw]
       └─► FW-5 ──► FW-6                │
HS-1 ──┬─► HS-3 ──┐                      │
       ├─► HS-2 ──┴─► HS-4 ─► HS-5 ─► [GATE A host]   HS-6 (after HS-4)
HW-B0 [HW] (after FW-1; parallel lane)
HW-B1 [HW] (FW-10 + HW-B0 + FLASH-QUEUE) ─► HW-B2 ─► HW-B3 ─► [GATE B]
[GATE A] ─► RV-1 ─► DOC-1 ─► MRG-1 ─► [GATE E]
HW-C1/C2 [BLOCKED: 2nd Pico]
```

**Parallel lanes (3 workers max):**
- After FW-1: **FW-2 ∥ FW-3 ∥ FW-4 ∥ FW-5** (four independent pure/build tasks) and the whole **HS lane (HS-1…)** runs fully parallel to the FW lane.
- After FW-6: **FW-7 ∥ FW-8** (TX vs RX engines, merge in FW-9).
- HW-B0 can run anytime after FW-1 (needs boards, not firmware).

**Critical path:** FW-1 → FW-5 → FW-6 → FW-7 → FW-9 → FW-10 → HW-B1 → HW-B2 → MRG-1 ≈ 6 fw-tasks + 2 hw-tasks. With 2 workers (fw + host), Stage A in ≈1 day; Stage B in one bench session with Felix.

---

## 4. Validation Ladder — Gate Evidence Summary

| Gate | Requires | Evidence artifact (committed) |
|---|---|---|
| **A — host-only** | FW-10 + HS-5 | `pio run` log (0 warnings), `make -C firmware/rp2040/host-tests` PASS, `pytest tools/test_range_bench_ctl.py` PASS, `docs/evidence/stage-a/dryrun-matrix.txt` |
| **B — single board [HW]** | HW-B2 (HW-B3 optional) | FLASH-QUEUE DONE row, session transcripts (both console paths), `docs/evidence/stage-b/cage.csv`, safety negative-test transcript |
| **C — two-board [BLOCKED]** | 2nd Pico | (later) full matrix CSV both ends, T0 alignment log |
| **D — cold review** | RV-1 | `git diff --stat` additive-only proof + reviewer sign-off |
| **E — merge+docs** | DOC-1 + MRG-1 | README-host-driven-bench.md, merge commit, verified `git push github range-tests` |

**Quality gates honored per repo rules:** TDD (failing test first on FW-2/3/4, HS-1/2), atomic commits (1 task = 1 commit), docs-in-commit (each HW task commits its transcript; DOC-1), push-verified (MRG-1), board lock + FLASH-QUEUE before every flash, BoardSerial for every serial open.

---

## 5. Out of Scope (explicitly)
- Resolving the committed conflict markers in `flrc_range_{tx,rx}_auto.cpp` / `flrc_range_rx_gps.cpp` (separate card; plan cannot touch these files).
- ESP32 bridge firmware changes (v7 pass-through + BOOTSEL/RESET suffices; heartbeat solves the 30 s watchdog).
- 2.4 GHz HF path, PA-board (2 W) high-power operation beyond the `POWER MODE OUTDOOR` unlock seam, band override.
- V4 interleave epoch-modulo sync replacement work beyond decommission note in README.

---
# REV-2 — Adversarial Grill Resolutions (2026-08-17, manager decisions)

## Blockers → Decisions
- **B1 (HF-hardwired backend)**: FW-5a must implement the per-band init matrix copied from `dual_radio_gps_sweep_tx.cpp` L505-580: RX_PATH (HF=0x01/LF), FE freq `|0x8000` HF-only, PA_CONFIG select byte (0x80 HF vs LF), per `isHF` flag. `rfSwitchBitrate()` alone is INSUFFICIENT — re-init rule = full band-aware init.
- **B2 (LF-FLRC unproven on this module)**: HW-B2 gains a FIRST cell: LF-FLRC feasibility smoke (MOD FLRC 650, FREQ 868000000, N=50 into cage). Cross-evidence: E80 (same LR2021 silicon) runs FLRC-650@868 fine. If smoke fails → matrix drops LF-FLRC cells (LoRa-only LF; FLRC on HF as separate later session). Decision recorded in cage CSV metadata.
- **B3 (SDK wdt 8388ms cap)**: Defense-1 = CHIP TX timeout via `set_tx(timeout_ticks)` + TIMEOUT IRQ (port E80 `radio_bench.c` L285-309 pattern — PA unkeys in silicon). Defense-2 = SDK watchdog ≤8000ms as superloop-wedge catcher ONLY (feed between packets; SF12 9s airtime is covered by defense-1, NOT wdt). E80's 60s ambition dropped. Test vectors in FW-4 must encode the 8000ms cap.
- **B4 (BW code contradiction)**: New task BW-1 extracts the authoritative LoRa BW code table from vendored Semtech `lr20xx_driver` in ~/repos/balloon-e80bench (ground truth), reconciles vs `lora_868_tx.cpp` (203/406/812) and `dual_radio` comment (0x05=250k). Output: docs/bw-code-table.md + shared header both FW and HS use. BLOCKS FW-5a + HS-1b.

## Majors → task-body directives
- **M1**: FW-6 lives in own TU `flrc_range_host_dispatch.cpp` (pure, zero Arduino includes).
- **M2**: Serial1 = protocol port (bridge). CDC output gated on `Serial` connected flag; NEVER call `Serial.flush()`. FW-7 polls console between packets (E80 superloop pattern) so mid-burst STOP works.
- **M3**: HS-4 re-checks `ID?` mid-poll-loop; role/fw/unlock change ⇒ mark row ABORTED, re-arm, re-issue `POWER MODE OUTDOOR` unlock. Port E80 `e80_bench_ctl.py` L461 pattern.
- **M4**: FW-5 split → FW-5a (TX backend + band matrix) / FW-5b (RX + RSSI both mods incl LoRa packet status read). HS-1 split → HS-1a (scaffold+airtime/N-regime) / HS-1b (matrix/schedule/freq-gate). Honest estimate: Stage A = 2-3 days with 2 workers.
- **M5**: New FW-0: worktree AGENTS.md note superseding tollgate mapping (this worktree = range-tests track; boards = F242D Pico + ESP32 bridge, by-id resolution).
- **M6**: FW-7 deps += FW-3 (stats). HS-2 gains STAT?-conformance test against §1 example line (late-binding kill).

## Minors → baked in
- Port ID via `/dev/serial/by-id/usb-Raspberry_Pi_Pico_E663977F242D-if00`; do NOT edit PORT_TO_RESOURCE; re-census after every BOOTSEL (HW-B1→B2).
- RSSI marked UNCALIBRATED in CSV; HW-B3 adds cage calibration (known PA + attenuator).
- STOP semantics: abort burst → standby → stats RETAINED until next START (START resets stats). Documented in README + HELP.
- All work in `~/worktrees/host-driven-bench` (single pinned worktree; tools/ dir inside it).
- Grammar: keep plan §1 standalone-arg grammar (NOT E80 kwargs); HS-2 conformance test locks it.
