# PROGRESS — v9 open-pin closure (`feat/v9-close-open-pins`)

Base `github/main` @ `e4d0569`. Worktree `/home/c03rad0r/worktrees/bf-erc`.

## Cluster 1 — measured the baseline (not the inherited number)

- `kicad-cli sch erc --exit-code-violations v9_flight.kicad_sch` → **23 errors, 0 warnings, all
  `pin_not_connected`** (exit 5). The inherited "known classes" list in the task was **stale**: the
  live 23 were the pin-plan leftovers (U5 MAX-M10S 15/18; U1 3/13/14/19/20/24/25; U4 1/2/14; U3
  6/7/9/14/15/16/17; U6 2/4/6; U7 4) — **not** the F33 VCC rail, `J_VCC`, MS5611 I2C, or the straps
  (IO0/IO3/IO45/IO46 and IO35-37 are already no-connected from an earlier pass).
- All 23 already mapped onto existing `OPEN-1..10/14` entries in `V9_TODO`.

## Cluster 2 — read the landed records (citation trap found)

- `docs/adr/*.md` **filenames do not match their internal ADR numbers** (e.g.
  `101-lr2021-only-ban-sx1280.md` is internally `ADR 017 … SUPERSEDED`; `108-…` is internally
  "V9 D2b(b) — LoRa2021F33 + SX1280 pin plan"). Built the canonical name→number map before citing
  anything.
- **No** MS5611 / MS5607 / MAX-M10S / SX1280 / ESP32-S3 datasheet is committed → tie-offs that would
  need those datasheets cannot be decided from a datasheet and stay OPEN.
- `docs/LR2021-LESSONS-2026-09.md` + `docs/F33-MODULE-PLAN.md` + the F33 18-pad table (quoted in-repo
  at ADR-059 §1.3) prove the F33's DIO5–DIO8 are **internal** front-end DIOs with no board pads →
  `U1.19` (`F33_DIO5`) is stranded.
- Frozen-board sweep found the decisive precedent: **`output/v8j_krt_ms5611.kicad_pcb`** uses the
  **same `Package_LGA:LGA-8_3x5mm_P1.25mm`** footprint as this sheet, in the same I2C mode
  (pads 7/8 = `I2C_SDA`/`I2C_SCL`), and ties pads **2 = GND, 4 = +3V3, 5 = +3V3, 6 = GND**. (The
  register had only considered **v8i**, whose barometer is a *different* 2.5×2.5 mm footprint.)

## Cluster 3 — generator edits (source of truth), then regenerate

Edited `build_flight_sch.py` only, scripted + anchored + `compile()`-checked after every batch:

1. `+3V3` node list += `U6.4`; `GND` node list += `U6.2`, `U6.6`; both net citations gained the v8j
   precedent sentence.
2. `V9_NC` += `("U1","19", …)` — the IO11 / `F33_DIO5` no-connect with its three-source citation.
3. `V9_BARE_PINS` `PAD16_??`/`PAD17_??` → `DIO8`/`DIO7` (sourced naming correction) + comment updated.
4. `V9_TODO`: OPEN-6 and OPEN-7 rewritten as **CLOSED** with the citation that closed them; OPEN-1,
   -2, -3, -4, -5, -8, -9, -10, -14 each gained the deciding action **and an OWNER**.
5. The MS5611 symbol is re-homed to `balloon_flight_v9:MS5611_BARO` with the SDO pin typed `passive`
   (geometry copied verbatim; U6's `lib_id` updated). Reason: an `output` pin on the flagged GND net
   produced a `pin_to_pin`; overriding the *stock* library raised a `lib_symbol_mismatch` warning, so
   the corrected symbol lives in the project's own library instead. No connectivity change.

Regenerated twice → `v9_flight.kicad_sch` sha256
`c7a51a519e485e7356d704e184b82cc51df53976b73972aa90f512b0e58e8f44` **both runs** (byte-identical).
Re-exported `v9_flight.net`.

## Cluster 4 — verified

- ERC: **19 errors, 0 warnings, all `pin_not_connected`**; `comm` set-diff shows **4 pins closed**
  (U6.2, U6.4, U6.6, U1.19) and the only "new" lines are the U3.16/U3.17 **rename at identical
  coordinates** (same pins, still open).
- Netlist cross-check: U6 nodes = `1,4,5 → +3V3`, `2,3,6 → GND`, `7 → I2C_SDA`, `8 → I2C_SCL` —
  **exact** match to v8j's pads. `U1.19` absent from every net (NC).
- `check_sch_gates.py v9` → ALL GATES PASS + V9 GATES PASS; both fail-closed checkers PASS (defaults
  **and** `--require-*` strict flags); `pytest tests/test_hub_array_topology.py
  tests/test_bypass_diode_check.py` → **32 passed**.
- Proved the netlist-export annotation warning **pre-existed** (HEAD sheet exported from a scratch
  copy → same warning).
- Reverted the C3 collateral (`v_c3_flight.net`, `v_c3_flight-erc.rpt`) — their whole diff was the
  embedded worktree path + timestamp.

## Cluster 5 — report-only items

- The v9 sheet **still carries the stale F33 land pattern** (`docs/f33-module/
  F33-LANDPATTERN-VERIFICATION.md`: FAIL, 0/18 pads; the v9 footprint copy differs from
  `hub_board_f33.kicad_pcb`'s only in its header line).
- **MS5611 vs MS5607**: ADR-108 and `POWER-BUDGET-V9-D2BE.md` say `MS5607-02BA03`; the generator/sheet
  say `MS5611-01BA`. Reported, not fixed.
