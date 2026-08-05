# C3 Flight Board — Consultant Sign-Off (C3-P7)

**Task:** t_daadf24e (C3-P7: Consultant sign-off)
**Reviewer:** worker-inspector (independent — no implementation context)
**Date:** 2026-08-05
**Toolchain:** kicad-cli 9.0.8, git (branch `autonomous/mesh-baseline`)
**Reference plan:** `tracker/hardware/PCB-EXECUTION-PLAN.md` (ADR-028)
**Expected deliverables:** `tracker/hardware/schematics/v_c3_flight.kicad_sch`, `tracker/hardware/v_c3_flight_2layer.kicad_pcb`, `tracker/hardware/gerbers_v_c3/`

---

## VERDICT: REJECT — board does not exist, sign-off cannot be performed

The Balloon-C3 flight board was **never built**. The consultant sign-off gate
cannot be passed because there is no artefact to verify. Every upstream pipeline
phase that the sign-off depends on (P1 schematic → P2 ERC → P3 layout → P4 route
→ P5 DRC → P6 gerbers) is either `todo` or `ready` in the board — none completed.

This task was dispatched against an empty pipeline. Signing off would be
certifying a board that does not exist.

---

## 1. Deliverable presence check (BLOCKING)

| Expected artefact | Path | Present? | Size |
|---|---|---|---|
| KiCad project | `tracker/hardware/schematics/v_c3_flight.kicad_pro` | YES | 165 lines — **project settings stub only** (design rules, no board/schematic) |
| Schematic (P1) | `tracker/hardware/schematics/v_c3_flight.kicad_sch` | **NO** | — |
| PCB board (P3/P4) | `tracker/hardware/v_c3_flight_2layer.kicad_pcb` | **NO** | — |
| Gerbers (P6) | `tracker/hardware/gerbers_v_c3/` | **NO** | — |

Verified by:
- `find` over the entire repo for `*v_c3*` → only the `.kicad_pro` stub.
- `git log --all -- '*v_c3*'` → the C3 board/schematic/gerbers were **never committed in any branch**.
- Sibling worker workspaces (`t_c5b818c9`, `t_58b8d370`, `t_64c61c6d`) → none contain a C3 flight board; `t_64c61c6d` (C3-P4) is in fact holding V2-ADC artefacts (`flight-pcba-v02*`), not C3.

All other `.kicad_pcb` files in the repo belong to V1, V2-ADC, `hub_board`, or `f33` variants — **none is the ESP32-C3 flight board**.

## 2. DRC re-run

**Could not run.** `kicad-cli pcb drc` on the only C3 artefact (the `.kicad_pro`
stub) returns `Failed to load board` — it is not a board file. There is no
`v_c3_flight_2layer.kicad_pcb` to feed the checker.

| Gate | Required | Result |
|---|---|---|
| DRC 0 violations / 0 unconnected | 0 / 0 | **N/A — no board** |

## 3. Checks that could not be performed (artefact absent)

- **0.6 mm thickness** — no `.kicad_pcb` `(thickness ...)` token to read.
- **Gerber sizes** — no `gerbers_v_c/` directory; nothing to measure.
- **Footprint count** (>10 per P3 gate) — no board, no footprints.
- **Board-level GPIO18/19 absence** — no netlist/pads to inspect.

---

## 4. Checks that COULD be performed (firmware + plan review)

Although the board is absent, the firmware and plan are present. Reviewing them
surfaces issues the layout worker must fix **before** a board can pass this gate.

### 4.1 GPIO-to-firmware cross-check

Authoritative ESP32-C3 firmware: `firmware/esp32-c3-flrc/main/main.cpp:37-44`.

| Function | Plan §2.4 | Firmware (`main.cpp`) | Match? |
|---|---|---|---|
| SPI SCK | GPIO6 | `PIN_SCK = 6` | OK |
| SPI MOSI | GPIO7 | `PIN_MOSI = 7` | OK |
| SPI MISO | GPIO2 | `PIN_MISO = 2` | OK |
| SPI NSS | GPIO10 | `PIN_CS = 10` | OK |
| LR2021 BUSY | GPIO4 | `PIN_BUSY = 4` | OK |
| LR2021 DIO9 (IRQ) | GPIO5 | `PIN_IRQ = 5` | OK |
| LR2021 RST | GPIO3 | `PIN_RST = 3` | OK |
| **STATUS_LED** | **GPIO9** | **`PIN_LED = 8`** | **MISMATCH** |

The 7 LR2021/SPI pins agree. **The status LED does not:** the plan assigns
STATUS_LED to GPIO9 (a strapping pin w/ pull-up) and marks GPIO8 as "unused /
strapping", while the firmware drives the LED on **GPIO8**. Whichever pin the
board routes, it must match the firmware that will actually run. The schematic
worker (P1) must reconcile this before drawing the symbol.

### 4.2 GPIO18 / GPIO19 absence (sign-off rule)

Sign-off rule: **no GPIO18/19 on C3.**

- Firmware (`esp32-c3-flrc`): uses **only** GPIO {2,3,4,5,6,7,8,10}. GPIO18/19
  not referenced. PASSES the rule.
- **Plan netlist (§2.3) VIOLATES the rule:** it maps `FEM_TX → U1.GPIO19`, and
  §2.4 lists GPIO18 (USB_D−) / GPIO19 (USB_D+) as "available if USB disabled".
  GPIO18/19 on the ESP32-C3-MINI-1 are the dedicated USB D−/D+ pins; reusing
  them forfeits USB and conflicts with this gate. The schematic must **not**
  route GPIO18/GPIO19 to FEM or anything else. (FEM is optional anyway — leave
  it unconnected or move FEM_TX to a free non-USB GPIO.)

### 4.3 Thickness specification conflict

- P3 task body: "Set 0.6mm".
- This sign-off rule: "verify 0.6mm thickness".
- Plan §4.2 (JLCPCB Order Specs): **"Thickness | 1.6mm"**.

The execution tasks (0.6 mm) and the order spec (1.6 mm) disagree. The
consultant cannot verify 0.6 mm against a plan that specifies 1.6 mm. Resolve
explicitly (0.6 mm is plausible for a 2-layer flex-ish carrier but unusual for a
4-layer FR4 JLCPCB order; 1.6 mm is the JLCPCB default). Document the decision in
the plan before layout.

---

## 5. Quality-gate scorecard

| Gate | Required | Status |
|---|---|---|
| G1: Board artefact exists | yes | **FAIL** (absent) |
| G2: DRC 0 violations / 0 unconnected | 0 / 0 | **BLOCKED** (no board) |
| G3: Thickness 0.6 mm | verify | **BLOCKED** (no board) |
| G4: Gerbers present & sized | yes | **FAIL** (absent) |
| G5: Footprint count > 10 | > 10 | **BLOCKED** (no board) |
| G6: GPIO matches firmware | yes | **PARTIAL FAIL** (LED GPIO9 vs 8) |
| G7: No GPIO18/19 | yes | **PLAN FAIL** (FEM_TX→GPIO19 in §2.3); firmware OK |
| G8: Commit + push sign-off | yes | PASS (this report committed) |

---

## 6. Remediation (re-open P1–P6, do not re-run P7 until done)

1. **Resolve the spec conflicts in `PCB-EXECUTION-PLAN.md` first:**
   - Pin STATUS_LED: GPIO8 (match firmware) or GPIO9 (match plan) — pick one and fix the other side.
   - Remove `FEM_TX → GPIO19` from netlist §2.3; FEM optional/unconnected or moved to a non-USB GPIO.
   - Settle thickness: 0.6 mm or 1.6 mm — make plan §4.2 and the layout task agree.
2. **Execute the pipeline in order:** P1 schematic → P2 ERC clean → P3 layout (+0.6 mm + Edge.Cuts) → P4 route → P5 DRC 0/0 → P6 gerbers. None of these currently produce a C3 artefact.
3. **Re-run P7 (this task)** only after P1–P6 are `done` and `v_c3_flight_2layer.kicad_pcb` + `gerbers_v_c3/` exist and are committed.

---

## 7. Status

**REJECT.** Do not order / fabricate. No C3 flight board exists to fabricate.
Re-open the C3 layout pipeline; revisit this sign-off once P1–P6 deliver the
artefacts defined above.
