# C3 Flight Board — Consultant Sign-Off (C3-P7)

**Task:** t_daadf24e (C3-P7: Consultant sign-off)
**Reviewer:** worker-inspector (independent — no implementation context)
**Date:** 2026-09-29
**Toolchain:** kicad-cli 9.0.8, git (branch `autonomous/mesh-baseline`, tip `10c51ce`)
**Reference plan:** `tracker/hardware/PCB-EXECUTION-PLAN.md` (ADR-028)
**Supersedes:** the 2026-08-05 REJECT (`2252dca`) which was written when no C3
artefact existed. The artefacts now exist and have been re-checked from scratch.

---

## VERDICT: REJECT — board artefacts exist, but the board is not manufacturable

The 2026-08-05 rejection reason no longer applies: the schematic, a routed
`.kicad_pcb` and a full gerber set now exist and are pushed. This re-run is a
**fresh REJECT on substance**, not on absence:

1. **DRC fails the P5 gate** — 1 short, 12 track crossings, 3 clearance
   violations, 4 keepout violations, 49 unconnected (independent re-run).
2. **ERC fails the P2 gate** — 159 violations (97 errors).
3. **GPIO18/GPIO19 are wired on the board** — the exact rule this sign-off
   exists to enforce is violated on U1 pads 13 and 14.
4. **The board netlist does not match the firmware** — 2 of 8 pins disagree,
   and both mismatches are the forbidden GPIO18/19 pins.

Ordering any of these gerbers would produce a non-functional board.

---

## 1. Deliverable presence check — PASS (improved since 2026-08-05)

| Expected artefact | Path | Present? | Evidence |
|---|---|---|---|
| KiCad project | `tracker/hardware/schematics/v_c3_flight.kicad_pro` | YES | 3,930 B |
| Schematic (P1) | `tracker/hardware/schematics/v_c3_flight.kicad_sch` | YES | 4,475 lines, 117,790 B, sha256 `e50eaee7cbe4` |
| PCB board (P3/P4) | `tracker/hardware/output/v_c3_flight_final.kicad_pcb` | YES | 158,674 B, sha256 `0318e7fbb938` |
| Gerbers (P6) | `tracker/hardware/output/gerbers_v_c3/` | YES | 28 files, 284 KB, tracked on the pushed tip |

Note the board lives at `output/v_c3_flight_final.kicad_pcb`, **not** at the
`tracker/hardware/v_c3_flight_2layer.kicad_pcb` path the P7 task body names.
The naming drift is cosmetic but should be settled so P5/P6/P7 all point at one
canonical path.

Board/gerber hashes agree with the pushed remote tip `10c51ce`
(`git ls-tree github/autonomous/mesh-baseline` → `fd6d576c` for the board,
`72b10d18` for `-F_Cu.gtl`); the working copy hashes to the same blobs.

## 2. DRC re-run — FAIL (P5 gate = 0 violations / 0 unconnected)

Independent re-run, `kicad-cli pcb drc --format json` on
`output/v_c3_flight_final.kicad_pcb`:

```
Found 44 violations
Found 49 unconnected items
```

By category:

| Category | Count | Class |
|---|---|---|
| `tracks_crossing` | 12 | **REAL** |
| `items_not_allowed` (keepout) | 4 | **REAL** |
| `clearance` (0.115–0.165 mm vs 0.2 mm rule) | 3 | **REAL** |
| `shorting_items` | 1 | **REAL / fatal** |
| `track_dangling` | 14 | cosmetic (unfinished routing) |
| `silk_overlap` / `silk_over_copper` / `silk_edge_clearance` | 7 | cosmetic |
| `courtyards_overlap` | 2 | cosmetic |
| `isolated_copper` | 1 | cosmetic |

**Real electrical/structural violations: 20. Unconnected: 49.**

The single short is `LED_DRIVE ↔ SPI_NSS` (a crossing track pair at the
`(26.5, 12)` / `(30.475, 12)` region of F.Cu). `SPI_NSS` shorted to the LED
net means chip-select is not controllable — the radio cannot be addressed.

Unconnected, by net: `+3V3` 18, `GND` 14, `VDIV_MID` 3, `I2C_SDA` 3,
`GPS_TX` 2, then 1 each for `VCAP`, `EN`, `SPI_SCK`, `SPI_MOSI`, `LR_RST`,
`LR_BUSY`, `LR_DIO0`, `I2C_SCL`, `UART0_RX`. Power rails unfinished means the
board would not boot even ignoring the short.

Three further candidate boards were re-run as well; **none passes**:

| Board | Violations | Unconnected |
|---|---|---|
| `output/v_c3_flight_final.kicad_pcb` (the gerber source) | 44 | 49 |
| `output/v_c3_flight_v7_routed.kicad_pcb` | 69 | 40 |
| `output/v_c3_flight_4layer_routed_v3.kicad_pcb` | 71 | 8 |
| `output/v_c3_flight_clean_routed.kicad_pcb` (best) | 10 | 20 |

The best variant still carries 1 short, 1 clearance violation, 2 keepout
violations and 20 unconnected items.

**DoD gate note:** the 2026-09-16 PCB card definition of done requires ONE
`drc_score.py` row per attempt in `drc_snapshots/history.jsonl` (path +
`sha256_12` + shorts + clearance + unconnected + fp), with progress counted only
when `shorts + clearance + unconnected` falls. This tree has **no**
`drc_score.py` and **no** `drc_snapshots/history.jsonl`; the only snapshot files
present are V1/V2-ADC legacy JSONs. There is no scored, comparable row for any
C3 attempt — so the card cannot close on evidence even if the raw counts were
acceptable.

## 3. ERC re-run — FAIL (P2 gate = 0 violations)

`kicad-cli sch erc` on `schematics/v_c3_flight.kicad_sch`:

```
Found 159 violations
```

| Type | Count | Severity |
|---|---|---|
| `pin_not_connected` | 72 | error (97 errors total) |
| `endpoint_off_grid` | 55 | warning (62 warnings total) |
| `label_dangling` | 25 | error |
| `footprint_link_issues` | 6 | warning |
| `lib_symbol_issues` | 1 | warning |

`endpoint_off_grid` at this scale means wires and symbol pins are not on the
same connection grid — which is why 72 pins read as unconnected even where a
net label sits next to them. `footprint_link_issues` includes
`Footprint 'NiceRF_Lora1276-C1' not found in library 'RF_Module'`, and
`lib_symbol_issues` reports the symbol library `balloon-custom` is not
configured. The schematic therefore does not produce a trustworthy netlist,
which is the whole point of the ADR-028 schematic-first rule.

## 4. Thickness — PASS the 0.6 mm rule, but the spec conflict is UNRESOLVED

- Board `(general (thickness 0.6))` → **0.6 mm as required by this sign-off**.
  Confirmed independently in the exported `v_c3_flight_final-job.gbrjob`
  (`"BoardThickness": 0.6`).
- `PCB-EXECUTION-PLAN.md` §4.2 (JLCPCB Order Specs) still says
  `| Thickness | 1.6mm |`, and §3.1 explicitly computes the 50Ω RF width
  "on 1.6mm FR4".

So the artefact satisfies one of two mutually contradictory documents. A 0.6 mm
4-layer FR4 order is possible but unusual, and the RF trace width (0.76 mm) was
derived from the 1.6 mm stackup — the impedance claim is unverified for the
0.6 mm board actually exported. This was flagged in the 2026-08-05 reject and is
still unreconciled.

## 5. Gerber sizes / completeness — PARTIAL

`output/gerbers_v_c3/` (28 files, 284 KB) contains: 4 copper layers
(`F_Cu`, `In1_Cu`, `In2_Cu`, `B_Cu`), F/B mask, F/B silkscreen, F/B paste,
F/B adhesive, F/B fab, F/B courtyard, Edge.Cuts, Margin, User_1..4,
User_Comments, User_Drawings, User_Eco1/2, `.drl` drill and `.gbrjob`.

Authenticity verified: a **fresh** `kicad-cli pcb export gerbers` from
`v_c3_flight_final.kicad_pcb` reproduces every file byte-identically after
stripping the generation-date comment — the committed gerbers really are the
export of the committed board and were not hand-edited.

`.gbrjob` declares `LayerNumber: 4`, `BoardThickness: 0.6`,
`Size: 55.15 × 45.15`, `Finish: "None"`.

Gaps:

- **No BOM and no CPL/position file** anywhere in either gerber directory. Per
  the JLCPCB order-package checklist (and the 2026-08-05 lesson) the package is
  not PCBA-orderable; only a bare-PCB order would be possible.
- **`Finish: "None"`** while the plan requires ENIG (§4.2). Surface finish is
  not carried in the job file, so the fab order would default to HASL.
- Board is **55.15 × 45.15 mm**, not the 50 × 40 mm the plan §3.2 specifies.
  Not a defect by itself, but it means the §3.2 dimension table and the artifact
  disagree.
- `output/gerbers_v_c3_final/` is a second, near-duplicate 28-file set. Its
  files differ only in the embedded `G04 … date` comment. Two gerber
  directories for one board invites ordering the wrong one; delete or document
  which is canonical.

## 6. Footprint count — PASS

20 footprints on the board (> 10 required by the P3 gate):

`ANT1, R_LED, R_DIV1, U2, U4, U5, D1, C_CAP, C2, J2, R_PD, C3, SOLAR, C1,
LED1, R_DIV2, C4, U1, J1, U3`.

Two observations for the next layout pass:

- `U2` is instantiated with the footprint `HOPERF_RFM9W_SMD` (an RFM9x proxy),
  not the LR2021F33 footprint. The plan allows `NiceRF_Lora1276-C1` "as proxy"
  but the schematic's own footprint link is broken (§3), so the physical
  radio's pad geometry is unverified against the part being flown.
- `U5` is populated on the board with I2C nets but the plan lists BMP280 as
  "optional"; `C4`/`C3` decoupling exist as required.

## 7. GPIO18/19 rule — FAIL (this is the headline)

Sign-off rule: **no GPIO18/19 on C3.** Resolved against the official KiCad
esp32 symbol (`RF_Module:ESP32-C3-WROOM-02`: pin 13 = IO18, pin 14 = IO19):

| U1 pad | SoC pin | Net on the board | Rule |
|---|---|---|---|
| 13 | **IO18** | `LR_DIO0` (radio IRQ) | **VIOLATION** |
| 14 | **IO19** | `LED_DRIVE` (status LED) | **VIOLATION** |

Both USB D−/D+ pins are committed to signals. The plan §2.3 had the same defect
(`FEM_TX → GPIO19`) and the 2026-08-05 reject told the layout worker to remove
it; the defect has moved rather than been fixed. USB is forfeited on this board,
and the `BOOT` strapping net (`J1.pad 6`) is left unconnected as a result.

## 8. GPIO ↔ firmware cross-check — FAIL (2 of 8 mismatch)

Authoritative firmware: `firmware/esp32-c3-flrc/main/main.cpp:37-44`.

| Function | Firmware | Board (U1 pad → net) | Match |
|---|---|---|---|
| SPI SCK | `PIN_SCK 6` | pad 5 (IO6) → `SPI_SCK` | OK |
| SPI MOSI | `PIN_MOSI 7` | pad 6 (IO7) → `SPI_MOSI` | OK |
| SPI MISO | `PIN_MISO 2` | pad 16 (IO2) → `SPI_MISO` | OK |
| SPI NSS | `PIN_CS 10` | pad 10 (IO10) → `SPI_NSS` | OK |
| LR2021 BUSY | `PIN_BUSY 4` | pad 3 (IO4) → `LR_BUSY` | OK |
| LR2021 RST | `PIN_RST 3` | pad 15 (IO3) → `LR_RST` | OK |
| **LR2021 IRQ** | **`PIN_IRQ 5`** | **pad 13 (IO18) → `LR_DIO0`** | **MISMATCH** |
| **STATUS LED** | **`PIN_LED 8`** | **pad 14 (IO19) → `LED_DRIVE`** | **MISMATCH** |

The firmware's own struct would drive GPIO5/GPIO8 while the board routes the
interrupt to GPIO18 and the LED to GPIO19 — the board compiles, boots, and
silently fails to see radio interrupts. This is the exact silent-runtime-corruption
class the 2026-08-05 reject warned about.

Two further electrical mismatches against the plan's pin map:

- `VDIV_MID` (supercap ADC) is on **IO5** (pad 4). Plan §2.4 assigns it GPIO0.
  On ESP32-C3 only GPIO0–GPIO4 are ADC-capable, so IO5 cannot sample the
  divider at all. (`LR_BUSY` correctly holds GPIO4, so the ADC pin has in fact
  been spent elsewhere.)
- `I2C_SDA`/`I2C_SCL` are on **IO8/IO9** (pads 7/8). Plan §2.4 assigns
  GPIO20/GPIO21. IO9 is a strapping pin with pull-up, and IO8 is the strapping
  pin the plan explicitly says to leave unconnected.

## 9. Net-name divergence between schematic and board

The schematic labels nets `LR2021_DIO9` and `STATUS_LED`; the board's netlist
names the same functions `LR_DIO0` and `LED_DRIVE`
(`(net 15 "LR_DIO0")`, `(net 18 "LED_DRIVE")`). The board also uses a different
net vocabulary throughout (`RF_OUT` vs the plan's `RF_SUB_868`,
`+3V3` vs `3V3`). Any future netlist import/compare between schematic and board
will mismatch by name, and this is one reason the ERC cannot be reconciled
against the board. One naming scheme has to win and be applied on both sides.

---

## 10. Quality-gate scorecard

| Gate | Required | Status |
|---|---|---|
| G1: Board artefact exists | yes | **PASS** (schematic + board + gerbers present on pushed tip) |
| G2: DRC 0 violations / 0 unconnected | 0 / 0 | **FAIL** — 20 real violations, 49 unconnected |
| G3: Thickness 0.6 mm | verify | **PASS on artefact** (0.6); plan §4.2 still says 1.6 mm |
| G4: Gerbers present & sized | yes | **PARTIAL** — 28 files, authentic; no BOM/CPL, `Finish: None` |
| G5: Footprint count > 10 | > 10 | **PASS** (20) |
| G6: GPIO matches firmware | yes | **FAIL** — IRQ (5→18) and LED (8→19) mismatch |
| G7: No GPIO18/19 | yes | **FAIL** — pads 13/14 are GPIO18/19 |
| G8: Commit + push sign-off | yes | PASS (this report) |

## 11. Remediation — required before P7 can pass

1. **Remove GPIO18/19 from the board.** Move the radio IRQ to GPIO5 and the LED
   to GPIO8 (both free per the firmware), re-run ERC, then re-route. The
   `BOOT` strapping net on `J1.pad 6` must also be either wired or formally
   waived in writing.
2. **Reconcile the pin map against the firmware** — one document of record for
   SCK/MOSI/MISO/NSS/BUSY/IRQ/RST/LED, and fix `VDIV_MID` (needs an
   ADC-capable GPIO0–4) and the I2C pins off the strapping pins.
3. **Get DRC to 0/0.** Start from the best variant
   (`v_c3_flight_clean_routed`: 10 violations / 20 unconnected) and clear the
   remaining short, clearance and keepout violations and the unfinished power
   rails. Record every attempt as a `drc_score.py` row in
   `drc_snapshots/history.jsonl` (shorts + clearance + unconnected must fall).
4. **Get ERC to 0** — fix the 55 off-grid endpoints first; that alone removes
   most of the 72 unconnected pins. Restore the `RF_Module`/`balloon-custom`
   library links so the schematic is self-contained.
5. **Settle thickness**: 0.6 mm or 1.6 mm, in both the plan §4.2 and §3.1
   (the RF 0.76 mm width depends on it), then re-verify the RF impedance claim
   for the chosen stackup.
6. **Finish the P6 package**: BOM + CPL, correct surface finish (ENIG per
   §4.2), and delete the duplicate `gerbers_v_c3_final/` directory or document
   which set is canonical.
7. **Re-run P7** only after 1–6 land and the DRC row shows 0/0/0 with
   `fp >= 10`.

---

## 12. Status

**REJECT. Do not order / fabricate.** The board exists — unlike the 2026-08-05
run — but it shorts SPI_NSS to the LED net, leaves both power rails unconnected,
routes the radio IRQ and status LED onto the forbidden USB pins GPIO18/GPIO19,
and disagrees with the firmware on two of eight pins. Ordering it would burn a
JLCPCB batch on a board that cannot work.
