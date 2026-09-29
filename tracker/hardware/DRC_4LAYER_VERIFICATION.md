# DRC 4-LAYER VERIFICATION — V2-ADC 4-layer board

**Verification by:** worker-layout (independent verification card)
**Date:** 2026-09-29
**Task:** t_9c0e1e8f (PCB-4LAYER-REVIEW: verify 4-layer board DRC, planes, routing)
**Parent task:** t_c5f37d19 (PCB-4LAYER: Design + route 4-layer V2-ADC board — status: done/archived)
**Board under test:** `tracker/hardware/output/v2_adc_4layer.kicad_pcb`
**Board sha256:** `1f94ce86f45f554a7fa0331e8a5bee67b761658997ea827582ef931c6d5becda`
**Toolchain:** kicad-cli 9.0.8, python3.14 + pcbnew 9.0.8+dfsg-1, fresh DRC run (no cached JSON)
**Evidence:** `tracker/hardware/output/v2_adc_4layer_drc_verify.json`, `tracker/hardware/verify_4layer_evidence.py`

---

## VERDICT: ❌ FAIL — THE BOARD UNDER TEST DOES NOT EXIST

`tracker/hardware/output/v2_adc_4layer.kicad_pcb` is **not a 4-layer board**. It is the
empty stub that `pcbnew.NewBoard(path)` writes to disk when it constructs a new project:
82 lines, 1999 bytes, **0 footprints, 0 nets, 0 pads, 0 tracks, 0 vias, 0 zones, no board
outline, and 2 copper layers (F.Cu + B.Cu only — there is no In1.Cu and no In2.Cu).**

The file has been byte-identical since it was committed in `a34f092` *("wip: persist
kimi-k3 partial work — 8th timeout on delegate_task (300s limit)", 2026-08-05)* and is
unchanged at the tip of `autonomous/mesh-baseline` (`64b9f2f`). No later commit touched it.

**7 of the 9 required checks FAIL. The two that "pass" pass only vacuously** — the board has
no pads, no nets and no tracks, so "0 shorting_items" and "0 unconnected" are not evidence of
a routed board; they are the signature of an empty file.

---

## Required-check results

| # | Requirement | Measured | Status |
|---|-------------|----------|--------|
| 1 | `kicad-cli pcb drc` runs from scratch | exit 0, `v2_adc_4layer_drc_verify.json` written | ✅ ran |
| 2 | 0 `shorting_items` | 0 — **vacuous** (0 pads, 0 tracks exist to short) | ⚠️ not evidence |
| 3 | 0 `unconnected` | 0 — **vacuous** (0 nets exist to connect) | ⚠️ not evidence |
| 4 | GND zone on In1.Cu, >90% board area | **no In1.Cu layer; 0 zones; coverage 0.0%** | ❌ FAIL |
| 5 | 3V3 zone on In2.Cu, >90% board area | **no In2.Cu layer; 0 zones; coverage 0.0%** | ❌ FAIL |
| 6 | No zones on F.Cu / B.Cu | 0 zones total — satisfied only because nothing exists | ⚠️ vacuous |
| 7 | Gerbers exist in `output/v2_adc_4layer_gerbers/` | 26 files exist, **all empty** (see below) | ❌ FAIL |
| 8 | Report written to `tracker/hardware/DRC_4LAYER_VERIFICATION.md` | this file | ✅ |
| 9 | Git commit + push | this commit | ✅ |

### Additional real DRC violation (not in the card's checklist)

| Type | Count | Description |
|------|-------|-------------|
| `invalid_outline` | 1 | "Board has malformed outline (no edges found on Edge.Cuts layer)" |

Total violations: **1**, unconnected items: **0**. The single violation is real and confirms
the board has no Edge.Cuts outline at all — the design card's STEP 1 requirement ("Create board
outline on Edge.Cuts") is also unmet in the saved artifact.

---

## Evidence

### Board object inventory (`pcbnew.LoadBoard` → `verify_4layer_evidence.py`)

```
copper_layer_count          : 2
copper_layers_enabled       : ["F.Cu", "B.Cu"]          <-- In1.Cu / In2.Cu NOT enabled
footprints                  : 0
nets_nonzero                : 0
pads                        : 0
tracks_total                : 0
vias                        : 0
edge_cuts_bbox_mm           : [0.0, 0.0]                 <-- no outline
board_area_mm2              : 0.0
zones_total                 : 0
```

### Gerbers are syntactically valid but electrically empty

Every `Copper`/`Profile` gerber consists of a header and `M02*` — no aperture list, no
coordinates. The F.Cu layer in full:

```
%TF.GenerationSoftware,KiCad,Pcbnew,9.0.8+dfsg-1*%
%TF.CreationDate,2026-08-05T21:26:58+05:30*%
%TF.FileFunction,Copper,L1,Top*%
...
G04 APERTURE LIST*
G04 APERTURE END LIST*
M02*
```

| File | Size | Copper ops (D01/D02/D03) |
|------|------|--------------------------|
| `v2_adc_4layer-F_Cu.gtl` | 474 B | 0 |
| `v2_adc_4layer-B_Cu.gbl` | 474 B | 0 |
| `v2_adc_4layer-Edge_Cuts.gm1` | 443 B | 0 (no board profile) |
| `v2_adc_4layer.drl` | 281 B | 0 holes, no tool table, header `TF.FileFunction,MixedPlating,1,2` |

The gerber job file (`*.gbrjob`) declares only `Copper,L1,Top` and `Copper,L2,Bot` — a
**2-layer** fab profile. There is no L3/L4 layer in the plot set, so even the gerber package
cannot be ordered as a 4-layer board.

### The "0 unconnected" is a dead giveaway, not a result

The card's premise was "FreeRouting should hit 0/0 on first pass because GND+3V3 are handled
by internal planes". A real 4-layer V2-ADC board has 18 nets and ~19 pads-worth of GND/3V3
plus ~13 signal nets; the DSN for this design (see below) lists **17 placements and 18 nets**.
A board with 18 nets cannot simultaneously report 0 unconnected *and* 0 tracks. The metric
only reaches zero because it is measuring an empty file.

---

## Root cause

The design work was **built in memory and lost before it was saved**.

1. `pcbnew.NewBoard(output_path)` both creates the board *and immediately writes the empty
   stub to `output_path`*. Every subsequent mutation (footprints, nets, outline, planes) lives
   only in the in-memory `BOARD` object until a `pcbnew.SaveBoard()` lands.
2. The run got far enough to prove the design was real:
   - `output/v2_adc_4layer.dsn` (9127 B, dated 2026-08-05) declares a genuine 4-layer stackup
     (`(layer F.Cu) (layer In1.Cu) (layer In2.Cu) (layer B.Cu)`), the 50×40 mm boundary, both
     internal planes (`(plane GND (polygon In1.Cu …))`, `(plane 3V3 (polygon In2.Cu …))`),
     **17 placements** (U1–U4, FEM, ANT1/2, SOLAR, C_CAP, C1, C2, D1, LED1, R_DIV1/2, R_PD,
     R_LED) and **18 nets** (GND, 3V3, SPI_SCK/MOSI/MISO/NSS, LR2021_BUSY/DIO9/RST, GPS_RX,
     RF_SUB_868, RF_2G4_2400, VDIV_MID, VCAP, SOLAR_IN, FEM_TX, LED_ANODE, STATUS_LED).
   - `output/v2_adc_4layer.ses` (15566 B) contains **89 routed wires** — FreeRouting did run
     and did produce output.
3. The pipeline then died before `pcbnew.ImportSpecctraSES()` + `pcbnew.SaveBoard()`. The
   terminal state is exactly the `NewBoard()` stub. The parent card's own last commit message
   records the cause: *"8th timeout on delegate_task (300s limit)"*.
4. The gerbers (`2026-08-05T21:26:58`, same session) were then exported **from the stub on
   disk**, which is why they are empty.

So: the geometry existed, the router ran, and the only missing step is importing the SES and
saving the board — but nothing in the repo ever performed it.

---

## What this means for the parent card

`t_c5f37d19` is marked **done/archived** with `result: null` and no summary, and its body's 8
quality gates were never satisfied. Its own completion is unsupported by any artifact in the
repo: there is no `create_board_v2_adc_4layer()` in `full_pipeline.py` (only the 2-layer
`create_board_v2_adc`), no DRC report, no `drc_snapshots/history.jsonl` row, and the board file
is the constructor stub.

**This is a false completion.** The board was not designed, not routed, not DRC-verified and
not gerber-exported.

---

## Remediation (required before this board can be considered at all)

The missing work is a bounded, $0, deterministic re-run — the design source already exists:

1. Run the existing generator end-to-end with a long timeout and **background execution**
   (the 300 s delegate limit is what killed it):
   `/usr/bin/python3.14 tracker/hardware/run_4layer.py --output tracker/hardware/output/v2_adc_4layer.kicad_pcb`
   (`tracker/hardware/create_4layer.py` is the same pipeline with the SWIG-lifetime fixes.)
2. **Assert the save actually happened** before anything downstream runs — check
   `footprints > 0`, `zones == 2`, `copper_layer_count == 4`, `board_area_mm2 >= 2000`. A
   pipeline that returns the `NewBoard()` stub must fail loudly, not report success.
3. Verify the 4-layer route reaches 0 shorts / 0 clearance / 0 unconnected **with a non-empty
   board** (see `pcb-fab-readiness-gating` S1: the score is `shorts + clearance + unconnected`
   on a board with `fp >= 10`).
4. Watch the known 4-layer hazard: through-vias on signal nets short into the In1.Cu/In2.Cu
   planes unless the planes carry proper clearance islands
   (`kicad-cli-headless-pcb` → `references/4layer-routing-strategy.md`).
5. Re-export gerbers and confirm the job file lists **4** copper layers plus a non-empty
   drill file (tool table + hole coordinates) before any fab claim.

Follow-up card: **t_bba26596 — PCB-4LAYER-REDO: build AND SAVE the 4-layer V2-ADC board
(artifact is an empty NewBoard() stub)** (assignee `worker-pcb`), created from this
verification; parent `t_c5f37d19`.

---

## Reproduction

```bash
cd ~/repos/balloon-fresh && git worktree add /tmp/4l-verify github/autonomous/mesh-baseline
cd /tmp/4l-verify
/usr/bin/python3.14 tracker/hardware/verify_4layer_evidence.py \
    tracker/hardware/output/v2_adc_4layer.kicad_pcb \
    tracker/hardware/output/v2_adc_4layer_gerbers \
    /tmp/4layer_drc.json
# expect: copper_layer_count 2, footprints 0, zones_total 0, fcu_gtl_copper_ops 0
```
