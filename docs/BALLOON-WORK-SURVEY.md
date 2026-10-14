# BALLOON WORK SURVEY — ralph loop scope

**Date:** 2026-10-14 · survey for initiating a new ralph loop covering all
outstanding balloon work.

## Where the work actually lives

| Board | Status counts |
|---|---|
| `balloon` | blocked 84 · todo 42 · triage 24 · done 364 · archived 407 |
| `esp32-balloon-integration` | done 2 — board finished |
| repo | `balloon-fresh` (default `master`, github + ngit) |

**84 blocked on `balloon` is the real backlog.** Filtered to genuinely
actionable, the ralph loop should cover the following (deduped, grouped).

## A. Boards still to order (operator-gated)

| # | Item | State |
|---|---|---|
| A1 | Hub v9 ×10 at **0.8 mm** explicitly, re-price | pre-order checklist open, 6 blockers |
| A2 | Wing boards ×N (`wing_board_v9`, 0.6 mm **2-layer** — legal) | not ordered |
| A3 | Base-station board | checklist committed (`BASE-STATION-BOARD-CHECKLIST.md`) |
| A4 | `V9-D8` nested dual footprint: F33 **or** bare LoRa2021 (selectable rail + DNP RF) | **blocked** (`worker-pcb`) |
| A5 | Re-price + verify packets for all three | agent does; operator places |

## B. Experiments worth flying (from the gap analysis)

| # | Item | State |
|---|---|---|
| B1 | E-00 range & speed base↔balloon, then **LoRaWAN fallback** | designed |
| B2 | E-CS1..6 cold-start (freezer ramp, brownout recovery, duty cycle) | plan committed |
| B3 | Freezer tempco: 4× LR2021 modules vs E80 TCXO reference | **blocked** |
| B4 | Bench validation: freezer ramp RX decode (E80 TX vs cold mapper) | **blocked** |
| B5 | RFA-1c: re-calibrate LR2021 after every bitrate change (260→650 deafness) | **blocked** |
| B6 | Semtech AN1200.22 isotropic-conducted setup (real sensitivity) | not started |
| B7 | Wing/tab mechanical survival, night survival, float stability, SEU | designed in INDEX |

## C. Software still to implement (when boards arrive)

| # | Item | State |
|---|---|---|
| C1 | Flight libs S1–S6 (telemetry, resetlog, ringstore, scheduler, gpsconfig, expframework) | **✅ shipped, 336 checks** |
| C2 | L0 LR2021 driver + `radio_core` HAL | 4 workers dispatched, mid-flight |
| C3 | L2 LoRaWAN · L3 MeshCore · L4 Meshtastic | same dispatch |
| C4 | `hub_v9` PlatformIO env — **does not exist**; per-dir envs only, no S3 env anywhere | **missing** |
| C5 | Telemetry schema versions + ground-side decode | not started |
| C6 | OTA update path (littlefs ring interacts with it) | not started |

## D. Hardware / bench blockers

| # | Item | State |
|---|---|---|
| D1 | `Board B: fix pio toolchain, build green, flash + serial smoke` | **blocked** |
| D2 | `T2: Build+flash RX firmware, verify console on ttyACM1` | **blocked** |
| D3 | `P0.4: ESP32 SPI clock 40 MHz → 16 MHz (datasheet compliance)` | **blocked** |
| D4 | `PCB-V2 Phase 7: SPI timing characterisation on S3 board` | **blocked** |
| D5 | `PCB-V2 Phase 4B: independent DRC verification — both boards` | **blocked** |
| D6 | RFA-1b: flash PRAM-patched binary (needs replug + SWD re-seat) | **blocked** |
| D7 | ESP32-C3 refactor: remove LR2021 SPI, add UART mesh client | **blocked** |
| D8 | EN pull-up (absent from netlist) → rev-10 | known, unfixed |

## E. Flight-physics / envelope (gating everything)

| # | Item | State |
|---|---|---|
| E1 | **M1** weigh empty balloon · **M2** weigh one 52×19 mm cell · **M3** weigh one 36" latex | operator, cron nudge active |
| E2 | Reconcile ~57 g payload vs 9–22 g long-duration band | analysis committed |
| E3 | Latex-vs-superpressure literature survey | dispatched |
| E4 | Decide: accept ~7–9 km, or move to 36–40 in mylar/latex | operator decision |
| E5 | Wing config (b) spine+ribs — saves ~16 g | design exists, not adopted |

## The honest headline

**Order-blocking work is nearly done; the backlog is dominated by *bench* work
blocked on physical access** (D1–D7: pio toolchain, SPI clock, flash, DRC). A
ralph loop is the right instrument — but it will **stall on D and E** unless the
loop is told to treat those as explicit operator-handoff items rather than
retrying them. **C4 is the highest-value unblocked task** (no `hub_v9` env
exists, blocking all firmware build work).
