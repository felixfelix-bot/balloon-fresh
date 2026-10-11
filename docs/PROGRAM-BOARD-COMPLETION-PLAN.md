# PROGRAM — Complete every board end-to-end, then order from JLCPCB

**Created:** 2026-10-11
**Owner:** balloon-hermes (manager)
**Objective (operator, 2026-10-11):** 3D models, schematics, board designs and
**routed** PCBs for every board the end-to-end system needs — balloons as a
*bent pipe* connecting base stations via FLRC. Lock geometry early, DRC clean
before advancing a stage, LLM spatial review (Astra-class) before `done`, RF
decisions must be defensible, and every board fab-ready at JLCPCB — then place
the order.

---

## 0. Where the truth lives

| Source | What it owns |
|---|---|
| `docs/analysis/GAP-TRACKING-CHECKLIST.md` | reconciliation of rounds 1+2; the row ids quoted below |
| `docs/analysis/PROGRAM-GAP-ANALYSIS-ROUND2.md` | round 2 gap analysis (base doc: `PROGRAM-GAP-ANALYSIS.md`, 620 lines) |
| `docs/adr/INDEX.md` | every design decision; `scripts/adr_next_number.py` owns the next number |
| `board_status_census.py` + `docs/analysis/board-status/` | machine census of what is actually routed, per layer |
| `AGENTS.md` | measured environment gotchas (`pcbnew` only under `/usr/bin/python3.14`, 3D render limits) |

**Measured machine state (this session, `kicad-cli` 9.0.8 + pcbnew):**

| board | layers | fp | segments | vias | zones(filled) | DRC unconnected | verdict |
|---|---|---|---|---|---|---|---|
| `hub_board_v9` | 4 | 39 | 0 | 0 | 3 (3) | 101 | `plane_only` |
| `wing_board_v9` | 2 | 15 | 20 | 8 | 0 | 0 | `routed` |
| `auto-bootsel-interposer` | 2 | 14 | 9 | 0 | 1 (1) | 0 | `routed` |
| `v8g_krt_routed` (old gen) | 4 | 20 | 398 | 55 | 2 (2) | 0 | `routed` |

---

## 1. Board manifest — required vs. real

| # | Board | Purpose in the end-to-end system | Exists? | State |
|---|---|---|---|---|
| 1 | **Flight/payload hub** (`hub_board_v9`) | Balloon payload: MCU + FLRC radio + power + array interface | yes | 4-layer; **placement + GND planes only, 0 tracks/vias, DRC 101 unconnected** |
| 2 | **Wing** (`wing_board_v9`) | Deployable solar wing (double-sided cells) | yes | 2-layer; **routed, DRC 0 unconnected** (fixed this session, PR #47) |
| 3 | **Base station** | Ground gateway: RX chain, AGC, log detector, ADC/MCU, bias/rails, 2.4 GHz uplink PA | **NO** | `BS-01` — no schematic, netlist or gerber on any ref. ~16 `design/*` branches unmerged; ADRs 071–084 branch-only |
| 4 | **Pre-stretch / pressure bench rig** | Automated leak + pre-stretch cycle before flight | **NO** | `PRE-01` — protocol + breadboard firmware only; no schematic/footprint/layout/BOM |
| 5 | **Auto-BOOTSEL interposer** | Programming aid (ESP32-C3 ↔ RP2040) | yes | 2-layer; routed, DRC 0 |

**Old-gen archaeology:** ~100 `.kicad_pcb` variants under `tracker/hardware/output/`.
None of them is a deliverable; they are history. The `v8g/v8i` family is the most
complete old-gen lineage (4-layer, 398 seg / 55 via / 2 filled planes) and is the
closest thing to a routed flight board that exists.

---

## 2. The gate chain (operator's rules, made mechanical)

A board may advance a stage only when the previous gate has **observed output**,
not a self-report.

```
G0 GEOMETRY FREEZE      outline, modular grid, connector/land geometry, band plan
                        → ADR + single-source-of-truth parameter registry row
G1 SCHEMATIC            .kicad_sch, ERC clean, netlist exportable
G2 PLACEMENT            all parts placed, courtyards present on 100% of footprints
G3 ROUTING              tracks+vias on every net; DRC unconnected == 0
G4 DRC                  kicad-cli pcb drc: 0 errors, 0 unconnected (authoritative)
G5 3D + RENDER          3D models resolve; render shows real bodies (see 3D gap)
G6 SPATIAL REVIEW       Astra-class LLM review, cross-family, before `done`
G7 FAB SET              gerbers + drill + BOM + CPL exported, JLC rules checked
G8 ORDER                operator approves and places the JLCPCB order
```

**Non-negotiables carried from this repo's own rules (AGENTS.md, ADR-030):**
- `pcbnew` only under `/usr/bin/python3.14` — importing it under 3.11 **segfaults**
  the pytest run.
- **A total-only check is not evidence.** `test_3d_models_wing.py` asserted
  `(segment ) == 8` for a year while the back string was electrically isolated.
  Gates assert the **property** (e.g. F.Cu *and* B.Cu carry signal), never a magic total.
- **"Compile/parse clean" ≠ "DRC clean".** Only `kicad-cli pcb drc` counts.
- Vision must not be used to infer component positions from a render (3D library absent).

---

## 3. Blocking defects found now (must be fixed before their gate)

| id | defect | evidence | gates |
|---|---|---|---|
| **D1** | **Wing board: 0 of 12 footprints carry a courtyard.** | measured this session | makes G2 unverifiable — "0 overlap" is not evidence without courtyards (`PCB-01`) |
| **D2** | **Hub board is not routed at all** (0 tracks, 0 vias; 101 unconnected after the GND plane). | census above | G3/G4 |
| **D3** | **3D-model pipeline broken:** `KICAD9_3DMODEL_DIR` unset, no model library → every render is substrate+copper+silk only. Fix UNMERGED (`PCB-02`). | AGENTS.md lines 136–137 | blocks G5 *and* makes G6 blind — a spatial reviewer cannot judge part bodies it cannot see |
| **D4** | **RF-03: 2 MHz FLRC does not fit the 433 band.** ADR-073 fixes the 433 downlink at FLRC-max 2.6 Mbps = **2.666 MHz DSB** against a **1.74 MHz** allocation (1.53×). | `docs/adr/073`, ROUND2 §3.1 | **G0** — the band plan must be settled *before* the duplexer/filter is frozen, or the hardware is wrong at fab |
| **D5** | **RF-01: bent-pipe vs half-duplex.** ADR-035 mandates exactly one radio transmitting at a time; the operator's premise is a bent pipe (simultaneous). | ADR-035; ROUND2 §11.1 | **service model** — decides whether the relay is simultaneous or TDM store-and-forward |
| **D6** | **RF-02: uplink budget used LoRa sensitivity (−141.5 dBm) for an FLRC mission (≈ −99 dBm)** — ~40 dB optimistic. | `docs/2G4-LINK-BUDGET-ANALYSIS.md`; corrected in `uplink-budget-realistic-ground.md` | G0/RF defensibility |
| **D7** | **BS-05: the 433 RX LNA (TQP3M9037) vendor band is 0.7–6 GHz — it does not cover 433.92 MHz.** The whole 433 RX chain is built around it. | `433-lna-substitution-and-amateur-licence.md` §0.1 | G1 of the base station |

**D4, D5, D6 are the RF decisions that must be frozen before any base-station or
flight-board geometry is locked.** That is the operator's "make sure the RF
decisions make sense" gate, and it is a *pre-condition*, not a later review.

---

## 4. Phases

### Phase A — freeze the RF + geometry decisions (G0)
- A1 settle **D4** (433 band plan: real FLRC rates that fit 1.74 MHz, or move the
  high-rate link to 2.4 GHz) → ADR, superseding/amending ADR-073 as needed.
- A2 settle **D5** (bent pipe: simultaneous vs TDM store-and-forward) → ADR-035
  amendment. This decides the latency/throughput service model.
- A3 correct **D6** in place and record the corrected budget as authoritative.
- A4 resolve **D7** (433 LNA: substitute part or re-architect the RX chain).
- A5 write the **single-source-of-truth parameter registry** rows (outline, land
  size, flash, band split, wing orientation, cell class) and reconcile the four
  known duplicate-value defects recorded in AGENTS.md.
- **Exit:** every G0 decision has a landed ADR; no parameter has two live values.

### Phase B — flight/payload boards to fab-ready
- B1 fix **D1** (courtyards on 100%) and re-assert the overlap gate.
- B2 route the **hub** (D2): tracks + vias on every net → DRC 0 unconnected.
- B3 fix **D3** so renders show real bodies, then produce per-side/per-layer
  visual evidence.
- B4 3D models for every footprint on both boards (coverage doc exists for the wing).
- B5 fab set for hub + wing + interposer (G7).
- **Exit:** hub and wing pass G4→G7 with observed output.

### Phase C — base station board (the biggest gap)
- C1 merge/consolidate the ~16 unmerged `design/*` branches so there is a design
  of record (ADRs 071–084 on `main`).
- C2 schematic + ERC (G1) → placement with courtyards (G2) → route (G3) → DRC (G4).
- C3 select the missing 2.4 GHz uplink PA (BS-02) and price the 5 unpriced BOM rows (BS-03).
- C4 fab set (G7).
- **Exit:** base station passes G1→G7.

### Phase D — pre-stretch bench rig
- D1 schematic (pressure sensor, valve, relief/interlock per PRE-04) → layout → route → DRC → fab set.

### Phase E — review + order (G6, G8)
- E1 Astra-class cross-family spatial review on every board **before** `done`.
- E2 operator sign-off, then place the JLCPCB order (G8).

---

## 5. Live blockers (honest)

1. **DISPATCH IS QUOTA-BLOCKED.** `zai-quota-gate.sh` → `cheap-gate: BLOCK
   capacity (no lane has remaining headroom)`, exit 1. Consequences:
   - No subagents, no kanban workers, no LLM crons may be spawned.
   - **G6 (Astra spatial review) cannot run until quota frees.** The operator's
     mandatory review gate is therefore currently unsatisfiable — stated, not hidden.
   - Work that can proceed now is **deterministic and inline**: schematic/PCB
     generation, `kicad-cli` DRC, gerber/drill export, census, courtyard fixes.
2. **PR #47 is open** (`fix/pcb-defects-v9`, MERGEABLE, 4 commits, 19 files):
   wing B.Cu interconnect fix + hub GND planes + machine-checked status figure.
   Not merged — awaiting review.
3. **`main` is behind the design work**: ADRs 071–084 live only on branches (`BS-06`).
4. Every HUMAN/BENCH row (S_crack coupon `PRE-02`, LiteVNA purchase, BNetzA
   enquiry `LEGAL-01`, descent/recovery `SAFE-01`) needs the operator, not an agent.

---

## 6. What "done" means

The program is done when, for **each** board in §1: G0–G7 have observed output in
the repo, an Astra-class review is attached, and the board is in a JLCPCB-orderable
fab set — at which point the operator places one order covering the set.
