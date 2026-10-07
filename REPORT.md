# REPORT — ADR-108 pin-plan revision R1 (v9 open pins settled)

Branch: `adr/pin-plan-revision` (base `github/main` = `94c3c4dac97b1820bd1bf7b074424be8b528a769`)
Worktree: `/home/c03rad0r/worktrees/bf-pinplan`

> `PROGRESS.md` and `REPORT.md` are gitignored in this repo (`.gitignore:67/68`). They are
> tracked **on this branch only** with `git add -f`, per the task instruction; they must
> not go to `main`.

## 1. Outcome in five lines

* **ERC 19 → 3 errors**, all `pin_not_connected`, **0 warnings** throughout.
* **16 pins closed**; the residual is exactly `U1.3` (EN), `U1.13` (USB_D-), `U1.14`
  (USB_D+) — the console cluster, which needs a **fitted** connector. Its connector part,
  pinout and reset-RC values are now **named** (R1.7), so it is a fitting task, not a
  decision.
* Generator byte-identical across two runs: sha256 `ab3516fc34b4cce704631572ccd47bae871b3264e67cc974ccbfd650ee33ed1c`.
* **No part added or moved; no band split change; no ERC severity touched; nothing silenced.**
* ADR-108 revised **in place** with a dated `## Revision R1` section (the repo's
  append-only convention, cf. ADR-042 "Addendum A"/"Correction …"); no new ADR number
  consumed, so `docs/adr/INDEX.md` is unchanged and `tests/test_adr_numbering.py` stays green.

## 2. The two claims, measured separately

```
kicad-cli sch erc --exit-code-violations -o v9_flight-erc.rpt v9_flight.kicad_sch
  before R1 : Found 19 violations  -> 19 errors, 0 warnings, kinds=[pin_not_connected]  (exit 5)
  after  R1 : Found  3 violations  ->  3 errors, 0 warnings, kinds=[pin_not_connected]  (exit 5)

python3 check_sch_gates.py v9      -> V9 GATES PASS
   V9 GATE 1 REPORTS the ERC counts (errors=3 warnings=0) - it does not fail on them.
   "gates pass" is a SEPARATE, WEAKER claim than the ERC numbers above.
```

`comm -23` (closed) / `comm -13` (new) of the two `pin_not_connected` coordinate sets:

* **NEW = empty** — no error was traded for another.
* **CLOSED = 16**: `U4.1 U4.2 U4.14 U3.6 U3.7 U3.9 U3.14 U3.15 U3.16 U3.17 U5.15 U5.18
  U7.4 U1.20 U1.24 U1.25`.
* The one pin R1 *retires* from the sheet's `V9_NC` list is `U1.19` (IO11), which R1
  spends on `U3_IRQ` instead of leaving it a no-connect.

**The schematic is NOT called "clean".** Three real, sourced, open `pin_not_connected`
errors remain and each is registered with a reason and an owner (below).

## 3. The pin plan — assignment, constraint, citation

| Pin | Assignment | Constraint that decided it | Citation |
|---|---|---|---|
| U4.1 / U4.2 | `+3V3` | The SX1280 sits on the existing 3.3 V logic rail; no new/gated rail | ADR-047 §2.3; POWER-BUDGET-V9-D2BE §2; ADR-060 §4 |
| U4.14 RFIO | `ANT2_2G4_RANGE` (ANT2 re-pointed) | Four U.FL sites, four RF parts; the F33 carries TX only | ADR-034 D1/D5; ADR-029 D2b/D3; ADR-035; ADR-009 |
| U2.10 F33 ANT-2G4 | **no-connect** | Consequence of the above; no stub, no matching network | ADR-034 D5; ADR-029 D8 item 2 |
| U3.6 NSS | IO12 (`U1.20`) | Second SPI2 slave needs its own CS; IO12 free (CE is a 3V3 strap) | ADR-040 D2; V9-RADIO-SITE-MATRIX §3.1 |
| U3.7 BUSY | IO47 (`U1.24`) | Arbiter polls BUSY by GPIO | ADR-029 D4 R3; matrix §3.1 |
| U3.14 RESET | IO48 (`U1.25`) | Second radio needs its own reset | matrix §3.1; ADR-040 D2 |
| U3.15 IRQ/DIO9 | IO11 (`U1.19`) | Second radio needs its own IRQ; IO11 free (F33 has no DIO5 pad) | ADR-029 D4; matrix §3.1; OPEN-6 |
| U3.9 sub-GHz ANT | **no-connect** | The 433 TX role sits on the Site-A module in every configuration | ADR-034 D1; ADR-040 D1/D2; matrix §3.3/§3.4 |
| U3.16 DIO8 / U3.17 DIO7 | **no-connect** | LR2021 DIO5-8 are front-end control lines; this module has no front end | LR2021-LESSONS-2026-09; F33-MODULE-PLAN; ADR-034 D1 item 2 |
| U5.15 VIO_SEL | **no-connect** (leave open) | V_IO is +3V3 → 3.3 V range is selected by leaving it **open**; GND would select 1.8 V and exceed the 1.98 V abs-max | MAX-M10S `UBX-20035208-R08` Table 10 + Table 12 |
| U5.18 SAFEBOOT_N | **no-connect** (leave open) | Safeboot unused; the datasheet says leave it open | MAX-M10S `UBX-20035208-R08` Table 10 |
| U7.4 TPS7A02 pin 4 | **no-connect** | Pin 4 of DBV/SOT-23-5 is **NC on the part** | TPS7A02 `SBVS277C` Table 5-1 / Fig. 5-2 |
| U1.20 / U1.24 / U1.25 | IO12 / IO47 / IO48 | Same +4 budget (OPEN-14 pins, now assigned) | matrix §3.1; OPEN-14 |
| U1.3 / U1.13 / U1.14 | **still OPEN** (OPEN-10) | Console connector not fitted; R1 names the part + RC | see §4 |

## 4. Datasheets obtained (nothing invented)

All three were fetched and text-extracted with `pdftotext -layout` — **not** a vision model:

| part | document | the row that decided a pin |
|---|---|---|
| TI TPS7A02 | `SBVS277C` (Rev C, Sept 2022) | Table 5-1 / Fig. 5-2: DBV(SOT-23-5) **pin 4 = NC** — *"No connect pin. This pin is not internally connected. Connect to ground or leave floating."* (1 IN / 2 GND / 3 EN / 4 NC / 5 OUT) |
| u-blox MAX-M10S | `UBX-20035208-R08` | Table 10: pin 15 VIO_SEL *"Connect to GND for 1.8 V supply, or leave open for 3.3 V supply"*; pin 18 SAFEBOOT_N *"Leave open if not used."* |
| Espressif ESP32-S3-WROOM-1/-1U | datasheet v1.8 | §9 Peripheral Schematics p.41: *"it is advised to add an RC delay circuit at the EN pin. The recommended setting … is usually **R = 10 kΩ and C = 1 µF**."* |

**The `U7.4` contradiction was resolved from the datasheet, and the frozen boards were NOT
followed.** The frozen boards disagree with each other — `v8i`/`v8j`/`v8b`/`v8c`/`v8f` tie
SOT-23-5 pad 4 to `+3V3`; `v8_krt_routed` leaves pads 3 and 5 netless;
`hub_board_v1_clean` puts `3V3` on **pad 5**. The datasheet says pad 4 is NC and pad 5 is
OUT, so the sheet's own `NC` label was right, no tie-off was adopted from a
contradiction, and `hub_board_v1_clean` corroborates the call independently.

## 5. The feed count (OPEN-2) — settled at FOUR

`ADR-029 D2b/D3`: four connectors {GNSS, F33 sub-GHz, F33 ANT-2G4, SX1280}.
`ADR-034 D1`: adds a bare `LoRa2021` 2.4 GHz RX → a fifth candidate feed.
Four U.FL sites are drawn; no part may be added. `ADR-034 D5` states *"the F33 carries TX
only"*, so the F33's 2.4 GHz port is the one feed with no role. **ANT2 is therefore
re-pointed to the SX1280 RFIO** and U2 pin 10 becomes an explicit no-connect:

| site | feed |
|---|---|
| ANT1 | 433 MHz TX (`U2.9`) |
| ANT2 | 2.4 GHz **ranging** (`U4.14`, SX1280) |
| ANT3 | 2.4 GHz link **RX** (`U3.10`) |
| ANT4 | GNSS L1 (`U5.11`) |

The two 2.4 GHz-capable feeds stay **separate** (ADR-029 D3's λ/2 separation survives);
they were not merged onto one connector, which would have made two PA/LNA ports load each
other. Antennas are hub-side wire dipoles (ADR-009), unchanged — a wing cut still costs no
comms. **Not claimed:** the SX1280's RFIO **pad number** stays `TODO(unverified)`
(OPEN-13) — R1 names the net, not a proven pad ordering.

## 6. Files changed

| file | change |
|---|---|
| `docs/adr/108-f33-sx1280-pin-plan.md` | + dated `## Revision R1`; status pointer; supersede note on the GPIO11/GPIO12 rows |
| `tracker/hardware/schematics/flight_board/build_flight_sch.py` | the only connectivity edit: `+3V3` += U4.1/U4.2; ANT2 net re-pointed + renamed `ANT2_2G4_RANGE`; 4 new nets `U3_CS_N/U3_BUSY/U3_RESET_N/U3_IRQ`; `V9_NC` += 7 sourced no-connects, − U1.19; `V9_TODO` OPEN-1/2/3/4/5/8/9/14 retitled CLOSED + OPEN-10 rewritten + new OPEN-33 |
| `tracker/hardware/schematics/flight_board/v9_flight.kicad_sch` | regenerated (never hand-edited) |
| `tracker/hardware/schematics/flight_board/v9_flight.net` | regenerated; `home-path` scrubbed (`~/…`) |
| `tracker/hardware/schematics/flight_board/v9_flight-erc.rpt` | regenerated (19 → 3) |
| `docs/v9-BOM.md` | regenerated from the netlist; `--check` passes |
| `docs/v9-system-diagram.svg` / `.png` | ANT2 text updated; PNG re-rendered with the repo's own render script; `check_v9_diagram_layout.py` PASSES (0 defects) |
| `PROGRESS.md`, `REPORT.md` | added with `git add -f` (repo-gitignored); branch-local only |

Reverted as pure worktree-path/timestamp churn from `check_sch_gates.py`:
`v_c3_flight.net`, `v_c3_flight-erc.rpt`.

## 7. Verification transcript

```
python3 build_flight_sch.py v9 ; sha256sum v9_flight.kicad_sch     # run 1
python3 build_flight_sch.py v9 ; sha256sum v9_flight.kicad_sch     # run 2  -> identical
ab3516fc34b4cce704631572ccd47bae871b3264e67cc974ccbfd650ee33ed1c

kicad-cli sch erc --exit-code-violations -o v9_flight-erc.rpt v9_flight.kicad_sch   # exit 5, 3 errors
kicad-cli sch export netlist -o v9_flight.net v9_flight.kicad_sch
python3 check_sch_gates.py v9                # V9 GATES PASS (ERC counts REPORTED)
python3 scripts/gen_v9_bom.py --check        # OK: docs/v9-BOM.md is current (46 components)
python3 scripts/check_v9_diagram_layout.py   # PASS: 0 defects
python3 scripts/hub_array_topology_check.py --quiet                  # exit 0
python3 scripts/hub_array_topology_check.py --require-cut-sense --quiet   # exit 0
python3 scripts/bypass_diode_check.py --quiet                        # exit 0
python3 scripts/bypass_diode_check.py --require-populated --quiet    # exit 0
python3 -m pytest tests/test_hub_array_topology.py tests/test_bypass_diode_check.py -q  # 32 passed
python3 -m pytest tests/test_adr_numbering.py -q                     # 3 passed
python3 scripts/adr_next_number.py                                   # 62 (NOT consumed; 108 revised in place)
```

The netlist-export `Warning: schematic has annotation errors …` is **pre-existing**: a copy
of `HEAD`'s sheet exports with the identical warning (proved by exporting `git show
HEAD:…v9_flight.kicad_sch` from a scratch dir).

## 8. Judgement calls, stated so they can be overruled

1. **No part was added, so the console cluster stays open.** The task's HARD CONSTRAINT
   says *"do NOT add or move a part"*, while OPEN-10's description says the pin plan must
   *"NAME a connector part and the reset-RC values before either can be netted"*. R1
   satisfies both literally: it names the part
   (`Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical`, the frozen v8i board's
   own `J1` "Prog_Header") and the RC (10 kΩ / 1 µF, ESP32-S3-WROOM-1 v1.8 §9), and leaves
   the three pins registered OPEN with an owner. **If the intent was to fit the connector
   and reach 0, that is a one-edit follow-up** — the decision is complete, only the part is
   unfitted.
2. **The `{HP}` reading is a capability, not a role.** V9-RADIO-SITE-MATRIX §3.3 reads the
   F33's 2.4 GHz port from the *datasheet* ("the F33 exposes both 50 Ω ports"); ADR-034 D5
   is the *v9 role* assignment and says TX only. R1 follows the role record. Re-opening
   `{HP}`'s use of that port would be a change to ADR-034 D1, not a pin-plan edit.
3. **`U3.9` is a decided no-connect, not a reflex.** OPEN-4's warning was taken seriously:
   the population case was read out of ADR-034 D1 + ADR-040 D1/D2 + the matrix's DNP table
   before the no-connect was written.

## 9. Report-only findings (NOT fixed — outside the change surface)

* **ADR-108's prose says `MS5607-02BA03`; the sheet's barometer is `MS5611-01BA`.** The
  discrepancy is pre-existing and still unreconciled (as flagged in the prior pass). The
  generator's own `V9_TODO` already carries it for two members of the MS56xx family.
* **`GPIO 13` was missing from ADR-108's original table** even though ADR-047 §6 had spent
  it on the rail monitor; R1 records it, but the omission predates this revision.
* **`OPEN-13` is untouched and still blocks ADR-045 D1's antenna-access checker** on the
  SX1280 (the checker exits 2, CANNOT-VERIFY, until a Semtech SX1280 datasheet is committed).
* **`docs/V9-RADIO-SITE-MATRIX.md` §3.3's `{HP}` row now reads optimistically** against
  ADR-034 D5; this revision did not edit that document (not in the change surface), but a
  reader should take ADR-034 D5 as the role of record.
