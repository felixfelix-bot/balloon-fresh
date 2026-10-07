# REPORT — v9 flight schematic: open-pin closure (branch `feat/v9-close-open-pins`)

Base: `github/main` @ `e4d0569`, worktree `/home/c03rad0r/worktrees/bf-erc`.

## Headline (measured, not inherited)

| claim | before | after |
|---|---|---|
| `kicad-cli sch erc` messages | 23 | **19** |
| ERC **errors** | 23 | **19** |
| ERC **warnings** | 0 | 0 |
| kinds | `pin_not_connected` ×23 | `pin_not_connected` ×19 |

```
erc_before = "23 errors / 0 warnings (all pin_not_connected)"
erc_after  = "19 errors / 0 warnings (all pin_not_connected)"
```

**The generator is deterministic:** `build_flight_sch.py v9` twice →
`v9_flight.kicad_sch` sha256
`c7a51a519e485e7356d704e184b82cc51df53976b73972aa90f512b0e58e8f44`
both runs (byte-identical).

### The two claims, kept separate (do NOT conflate)

1. **`check_sch_gates.py v9` → ALL GATES PASS / V9 GATES PASS.** This checks the *generator's own
   invariants*: determinism (GATE 0), sheet loads (GATE 1), netlist export + all 46 declared
   components present (GATE 2), the TODO register stays on the sheet (GATE 3), net parity / node
   parity / netless-pad classification / pad coverage (C3 gates).
2. **ERC is NOT clean.** 19 `pin_not_connected` errors remain.

Correct statement: **generated + deterministic + ERC 19 errors** (was 23). Never "the schematic is
clean".

## What closed, and the citation for each

Proved with the set-diff of the two reports
(`grep -A2 '^\[pin_not_connected\]' <rpt> | grep '@(' | sort` + `comm`). CLOSED = 4 pins; the only
"NEW" lines are the *same two pins re-named* (see below), not new errors.

| ref+pin | disposition | citation |
|---|---|---|
| **U6.2 (PS)** | tied **GND** | `tracker/hardware/output/v8j_krt_ms5611.kicad_pcb` — the frozen MS5611 board, **same `Package_LGA:LGA-8_3x5mm_P1.25mm` footprint**, same I2C mode (its pads 7/8 = `I2C_SDA`/`I2C_SCL`, exactly this sheet's U6 7/8); it ties pad 2 = GND |
| **U6.4 (CSB)** | tied **+3V3** | same artefact — pad 4 = +3V3 (and, via the symbol's duplicate-coordinate pin 5, pad 5 = +3V3, which v8j also ties to +3V3) |
| **U6.6 (SDO)** | tied **GND** | same artefact — pad 6 = GND |
| **U1.19 (IO11 / `F33_DIO5`)** | **no-connect** | the F33 has **no DIO5 pad**: G-NiceRF `LoRa2021F33-2G4` datasheet Rev 1.1 §7 enumerates all 18 pads (quoted in-repo at **ADR-059 §1.3**) and lists no DIO5; the v9 F33 symbol defines no DIO5 pin either. `docs/F33-MODULE-PLAN.md` ("No DIO7/DIO8/DIO9 pins — only IRQ (Pin 18) as digital interface") and `docs/LR2021-LESSONS-2026-09.md` ("DIO5-8 are LR2021 DIOs wired to the on-module front-end. setRfSwitchTable() writes the mode mask into the CHIP (not MCU GPIOs)") confirm the F33's front-end DIOs are internal, not board nets — so the pin-plan's `F33_DIO5` has no destination |

Independent cross-check: the resulting U6 node set in the exported netlist is
`1,4,5 → +3V3`, `2,3,6 → GND`, `7 → I2C_SDA`, `8 → I2C_SCL` — an **exact** match to v8j's pad nets
(`1,4,5 = +3V3`, `2,3,6 = GND`, `7,8 = I2C`).

### Renaming (not a closure, recorded as such)

`U3.16`/`U3.17` were renamed `PAD16_??`/`PAD17_??` → **`DIO8`/`DIO7`** — a *naming correction with a
source* (vendor pin table `docs/assets/lr2021/LoRa2021-Module-Datasheet-V1.3.pdf` §7 +
`docs/inventory.md` line 28), no connectivity added. They appear in both the CLOSED and NEW
set-diffs **at identical coordinates** (`274.32 mm, 55.88 mm` / `274.32 mm, 58.42 mm`): the same two
pins, still open. Their MCU **assignment** remains OPEN-5.

## The `OPEN-n` register after (each names the decision + its OWNER)

Still open, 19 pins, all now with an owner recorded in `V9_TODO` on the sheet:

| OPEN | pins still open | decision that must land / OWNER |
|---|---|---|
| OPEN-1 | U4.1, U4.2 (SX1280 VDD_IN/VDD_IO) | ADR-060 §5 explicitly re-files this as unfixed. Conflict to settle: ADR-047 prose says the 3.3 V rail also carries the SX1280 and `docs/POWER-BUDGET-V9-D2BE.md` §2 lists both SX1280 states on 3.3 V. **OWNER: ADR-108 pin-plan revision** |
| OPEN-2 | U4.14 (SX1280 RFIO) | ADR-060 §5 re-files it; also the four-connector/five-feed count (ADR-029 D3 vs ADR-034 D1). **OWNER: ADR-108 pin-plan revision** |
| OPEN-3 | U3.6, U3.7, U3.14, U3.15 (bare-module NSS/BUSY/RESET/IRQ) | no record assigns them (ADR-108 covers F33+SX1280 only). **OWNER: ADR-108 revision + the ADR-040 / `V9-RADIO-SITE-MATRIX` §3.1 +4-GPIO budget** |
| OPEN-4 | U3.9 (bare-module sub-GHz ANT) | not unconditionally unused: in the `{LP}` configuration a bare module can be the 433 TX. **OWNER: ADR-034/ADR-040 population decision** |
| OPEN-5 | U3.16, U3.17 (now `DIO8`/`DIO7`) | names resolved from the vendor table; the MCU assignment is not. **OWNER: ADR-108 pin-plan revision** |
| OPEN-8 | U5.15 (VIO_SEL), U5.18 (~SAFEBOOT) | no record decides them; verified the frozen v8i board (same `ublox_MAX` footprint + `RF_GPS:MAX-M10S` symbol) leaves pads 15 and 18 **un-netted** — the precedent records the gap, it does not decide it. **OWNER: ADR-108 revision** (no MAX-M10S datasheet committed) |
| OPEN-9 | U7.4 (TPS7A02) | no datasheet committed. **OWNER: ADR-108 revision** |
| OPEN-10 | U1.3 (EN), U1.13/U1.14 (USB_D-/D+) | ADR-108 assigns the *function* of GPIO19/20 (USB-Serial-JTAG console) but names no connector and no EN reset RC; the v9 BOM has neither. **OWNER: ADR-108 revision** |
| OPEN-14 | U1.20, U1.24, U1.25 (IO12/IO47/IO48) | ADR-108's strap audit assigns IO0/IO3/IO45/IO46 "none" and reserves IO35-37, but states **no** disposition for IO12/IO47/IO48. **OWNER: ADR-108 revision** |

Nothing was silenced: no ERC severity was changed, no pin type was edited merely to lower the count,
and no pin was no-connected without a source.

## Report-only items (NOT fixed — trivial/obviously-correct check failed, or out of scope)

### 1. The schematic still carries the **stale F33 land pattern**

- `docs/f33-module/F33-LANDPATTERN-VERIFICATION.md` verdict: **FAIL — 0 of 18 pads coincide**; repo
  footprint pitch 2.0 mm vs vendor 3.9289 mm and the pattern is **rotated 90°**; quantified against
  `tracker/hardware/hub_board_f33.kicad_pcb` (`custom:LoRa2021F33_2G4`).
- The footprint referenced by `hub_board_f33.kicad_pcb` and by the fab handoff
  (`tracker/hardware/output/pcb-handoff/custom.pretty/LoRa2021F33_2G4.kicad_mod`,
  `tracker/hardware/hub_board_f33_jlcpcb/custom.pretty/…`, `tracker/hardware/hub_board_diy/custom.pretty/…`)
  all hash to `7dde65b9…`.
- The v9 sheet's `balloon_flight_v9:LoRa2021F33_2G4` is built by the generator from
  `hub_board_diy/custom.pretty/LoRa2021F33_2G4.kicad_mod` — `diff` against the v9 copy shows **only
  the header/name line and whitespace differ**, i.e. the **geometry is the same stale land pattern**.
  **The v9 schematic therefore still carries the stale F33 footprint.** Fixing it changes the BOM's
  assemblability and is owned by the `fix/f33-landpattern-vendor` work, not this card.

### 2. MS5611 vs MS5607 discrepancy (against ADR-108)

- `docs/adr/108-f33-sx1280-pin-plan.md` names the barometer **`MS5607-02BA03`** (header and the §pin
  table row for I2C_SDA/SCL). `docs/POWER-BUDGET-V9-D2BE.md` §2 also says "MS5607 barometer".
- The generator, the v9 sheet and the C3 sheet all use **`MS5611-01BA`** (`BARO_VALUE`, the U6
  component tuple, and `Sensor_Pressure:MS5611-01BA`). ADR-058 also says "MS5611 cross-check".
- Both are 10–1200 hPa LGA-8 pressure sensors on the same footprint family, so this is a *part-number*
  discrepancy, not a wiring one — but the pin plan and the sheet name different parts. **Reported,
  not fixed** (choosing the part is a BOM decision).

### 3. Stale reasoning inside OPEN-7/OPEN-8, corrected

- OPEN-7 previously rejected the **v8i** precedent because v8i's barometer is a Bosch LGA-8 **2.5×2.5 mm**
  footprint. That is correct about v8i — but the repo also holds **v8j**, which uses the **same 3×5 mm**
  footprint as this sheet, and v8j *does* decide the tie-offs. The entry now cites v8j.
- OPEN-9's text and the sheet's own repo-local symbol disagree: `v9_lib/…:TPS7A0233` names U7 pin 4
  **`NC`** while the register calls it "a real pad with an unverified function". The frozen boards are
  also inconsistent (v8i/v8j/v8b/v8c/v8f tie the SOT-23-5 pad 4 to +3V3; `output/v8_krt_routed` and
  `hub_board_v1` leave it netless). No tie-off is adopted from a contradiction; recorded.

## Tests / gates after (all re-run on the regenerated artefacts)

```
python3 check_sch_gates.py v9                        -> ALL GATES PASS  +  V9 GATES PASS
kicad-cli sch erc --exit-code-violations v9_flight.kicad_sch
                                                     -> exit 5, 19 errors, 0 warnings
python3 scripts/hub_array_topology_check.py --quiet                  -> PASS exit 0
python3 scripts/hub_array_topology_check.py --require-cut-sense --quiet -> PASS exit 0
python3 scripts/bypass_diode_check.py --quiet                        -> PASS exit 0
python3 scripts/bypass_diode_check.py --require-populated --quiet    -> PASS exit 0
python3 -m pytest tests/test_hub_array_topology.py tests/test_bypass_diode_check.py -q
                                                                     -> 32 passed in 2.02s
```

## Notes a reviewer should not have to dig for

- **The netlist-export warning is pre-existing.** `kicad-cli sch export netlist` prints
  `Warning: schematic has annotation errors, please use the schematic editor to fix them` while still
  exiting 0. Proved pre-existing: copied `flight_board/` to a scratch dir, restored **HEAD's** sheet
  over the copy, exported from there → **the same warning**.
- **Footprint/symbol change, not a connectivity change.** The MS5611 symbol is *re-homed* to the
  project's own library (`balloon_flight_v9:MS5611_BARO`, written into
  `v9_lib/balloon_flight_v9.kicad_sym`) with the SDO pin typed `passive` and its geometry copied
  **verbatim**. Reason: tying an `output`-typed pin to the GND net (which necessarily carries the
  synthetic `PWR_FLAG` "power output") makes KiCad ERC report a *real-looking* `pin_to_pin`
  ("Pins of type Output and Power output are connected") — an artefact of the synthetic flag, the same
  class of false finding this sheet already corrects on the F33 MISO pins. Overriding the *stock*
  library entry in place would instead raise a `lib_symbol_mismatch` warning, so the corrected symbol
  lives in the repo-local library. **Net: 0 new warnings, 0 new error kinds.**
- **`v9_sym-lib-table` shrank by one line** — the generator emits only the libraries actually
  referenced; `Sensor_Pressure` is no longer referenced now that U6 uses the repo-local symbol. It is
  automatic build-product churn, harmless, and the C3/shared table is untouched.
- **C3 collateral reverted.** Running the gates regenerates the C3 artefacts too; their whole diff was
  the embedded absolute worktree path + timestamp, so `v_c3_flight.net` / `v_c3_flight-erc.rpt` were
  `git checkout --`'d back so this commit does not embed a worktree path into another target's files.

## Scope respected

No part was added or moved; no radio band split was changed; no ERC severity was altered; no error
was suppressed. Design work only — nothing was ordered.
