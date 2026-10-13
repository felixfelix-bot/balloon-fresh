# Cross-Board Harmonization Plan — 511-byte FLRC Sweeps on E80 / RP2040 / ESP32-C3

Date: 2026-08-21. Consultant analysis (glm-5.2, 23 API calls), verified in source.
Operator: Felix. Status: SCHEDULED (kanban HARM-T1..T9, board e80-bench).

## Decision: shared host tool + COMMON console protocol (option a)

One host-side `balloon_sweep.py` (generalized from `tools/e80_sweep_full.py`)
drives all three boards via the E80 console protocol; each board's firmware
implements the console on its existing proven radio layer. E80's
`bench_cmd.c`/`bench_pkt.c`/`prbs.c` are freestanding C (zero HAL deps) and
port verbatim (~600 LOC). Rejected: shared C radio library 3-ported (~3-4k
LOC, high risk, re-introduces solved bugs).

## Gap analysis (source-verified)

**E80 (reference, done):** 511B proven (70a6e27). Only open item: merge
fix/t3-flrc-match123 (prerequisite for cross-board FLRC — Match1 mismatch
breaks E80↔RP2040 sessions).

**ESP32-C3 (esp32-balloon-integration-fresh/tracker/firmware):** FLRC never
invoked; RadioLib submodule UNINITIALIZED (build broken). RadioLib hard
gaps, both confirmed in source:
- 511B blocked: `RADIOLIB_LR2021_MAX_PACKET_LENGTH=255` enforced at
  LR2021.cpp:274/1033/1016; chip cmd layer takes uint16_t len — fork patch
  ~50 LOC makes caps FLRC-conditional.
- Match123 unavailable: syncMatch hardcoded 0x01 at 3 sites
  (LR2021_config.cpp:721, LR2021.cpp:1015/1054) — the exact E80 bug class.
- 2.4G RX path (SET_RX_PATH/CALIB HF bit) unverified in RadioLib — RP2040
  rfCalibrate() v4:561 is prior art.
Fix: minimal fork, flag-guarded, patch file in `patches/`, submodule pinned.

**RP2040 (worktrees/balloon-range-tests, multi_radio_sweep_rx_v4.cpp):**
Match123 + 32-bit sync 0x12AD101B already (golden config, 9b740aa lineage).
Gaps: no interactive console (time-driven SET_TIME/FW_QUERY only), FLRC
buffers capped 255 (chip cmd already 16-bit len — 10 LOC lift), PKT line is
GPS-oriented ~12 fields not parity 25. New `multi_radio_bench_console.cpp`
alongside v4 (v4 untouched).

## Protocol contract (normative = E80 bench_cmd/bench_pkt/prbs)

1. Commands: ID? (BENCH <board>), ROLE TX|RX, ARM TX, MOD LORA/FLRC, FREQ,
   PA, START N= LEN=6..511 GAP=, STOP, SESSION, CONFIG, STAT?, PRBS ON|OFF, HELP.
2. PKT line: exactly 25 fields per bench_pkt.c; emitted EVERY packet.
3. PRBS-15: x15+x14+1, seed=(seq^0x5A5A)|1, MSB-first; port prbs.c verbatim.
4. LEN caps: lora 255 / flrc 511, enforced host AND firmware.
5. FLRC golden RF config: Match123, 32-bit sync word 0x12AD101B (RP2040
   field-proven), chip CRC on, CR3/4, preamble 32.
6. SESSION/CONFIG tags echoed in every PKT line.
7. GAP>=40ms for LEN>256 (115200 console limit).

## Frequency plan

868 MHz = comparable baseline (all 3 pairings). 2.4 GHz = optional pair
(ESP32↔RP2040 only), reported separately, never mixed. Host tool carries
per-board FREQ_ALLOWED and refuses non-intersecting cross-board configs.

## Tasks (kanban e80-bench, strict gates)

| # | Task | Repo | Worker | Deps |
|---|------|------|--------|------|
| HARM-T1 | BENCH-CONSOLE-SPEC.md | balloon-e80bench docs/ | worker-balloon | — |
| HARM-T2 | balloon_sweep.py host tool (BoardDriver, TDD golden transcripts) | balloon-e80bench tools/ | worker-balloon | T1 |
| HARM-T3 | RadioLib fork: submodule init + 511/Match123 patch + SPI-byte golden test | esp32 repo | worker-balloon | T1 |
| HARM-T4 | ESP32 bench firmware (console trio + RadioLib glue + host tests + idf build green) | esp32 repo | worker-balloon | T3 |
| HARM-T5 | RP2040 bench console fw (v4 raw-SPI layer, buffers→511, golden tests) | balloon-range-tests worktree | worker-balloon | T1 |
| HARM-T6 | Cross-family cold review (spec vs 3 impls) | read-only | worker-reviewer-kimi | T2,T4,T5 |
| HARM-T7 | HW session 1: E80↔ESP32 @868 LEN matrix both directions (FLASH-QUEUE + lock) | both + balloon-fresh | worker-balloon | T6, fix/t3 merged |
| HARM-T8 | HW session 2: E80↔RP2040 @868, ESP32↔RP2040 @868+@2440 | worktree + coordination | worker-balloon | T6 |
| HARM-T9 | Results package + adoption docs (AGENTS/README submodule init) | all three | worker-admin | T7,T8 |

Parallel: T1 → {T2,T3} → {T4,T5} → T6 → {T7,T8 staggered by board lock} → T9.

## Verification (hardware proof)

1. E80 TX → ESP32 RX: FLRC 650k pa5 LEN {16..511} + BR interaction rows @868,
   N=50: 511B 50/50, PRBS bit_err=0, pcrc16 present. Reverse direction too.
2. E80↔RP2040 @868 same matrix.
3. ESP32↔RP2040 @868 + @2440 (only 2.4G pair; validates RadioLib rx-path).
4. Definitive artifact: ONE balloon_sweep.py run, two different board
   families, same SESSION id — PKT CSVs joinable on session,config,pkt_idx.
5. Regression: E80↔E80 511B row unchanged post-merge.

## Risks (top)

- RadioLib silent clobbering (begin/setSyncWord/startReceive re-program
  Match1/255) → patch ALL sites + golden SPI-byte test pins bytes.
- Cross-track flash contention → FLASH-QUEUE + balloon-board-lock v3, T7/T8
  staggered; orchestrator approves flashes.
- PRBS seed mismatch breaks cross-verify → seed rule normative in spec,
  golden bytes asserted in every repo.
- RadioLib patch rot → minimal flag-guarded patch, `patches/` file, pin
  fork commit, upstream PR early.
