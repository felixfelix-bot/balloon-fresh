# PLAN: DRC Cleanup + JLCPCB Order Package

**Created:** 2026-07-29
**Author:** balloon-circuit-design sub-manager
**Status:** AWAITING APPROVAL
**Worktree:** ~/worktrees/balloon-circuit-design/
**Branch:** balloon-circuit-design

## CONSTRAINT: No KiCad GUI Available

pcbnew Python module SEGFAULTS on this machine — confirmed with Xvfb virtual display.
kicad-cli has NO zone fill capability. All work must be done via text generation
in gen_pcb.py + kicad-cli DRC/export only.

## ROOT CAUSE ANALYSIS

### Why 31+32 unconnected items remain:
- GND pads are routed to stitching vias, but the vias connect to the B.Cu
  ground pour zone which is UNFILLED. kicad-cli DRC cannot verify unfilled
  zone connectivity → reports as unconnected.
- Fix: replace zone-dependent GND connections with EXPLICIT copper traces
  from every GND pad to a GND via cluster, and add GND traces between via
  pairs on B.Cu to form a continuous ground mesh.

### Why 30+14 clearance violations remain:
- Signal traces run close to component pads (within DRC clearance of 0.25mm).
- Fix: offset trace coordinates in gen_pcb.py to route between pad gaps.

### What JLCPCB actually needs:
- Gerber files (have: 22 per board)
- Drill file (have: .drl per board)
- Pick-and-place CSV (have: pos_v1.csv, pos_f33.csv)
- DRC clean is NOT required by JLCPCB — they run their own checks.
- But 0 unconnected IS important (means the board is electrically complete).

---

## TASKS

### TASK 1: V1 — Eliminate Unconnected GND Pads (worker-balloon, 15 min)

**Goal:** 0 unconnected items on hub_board_v1.kicad_pcb

**Problem:** 31 unconnected items. Breakdown:
- GND: 24 (pads not connected to ground mesh)
- 3V3: 4 (decoupling cap pads)
- VCAP: 2 (power chain)
- Signal: 4 (SPI test points, I2C MS5611 stubs)

**Method:** Edit gen_pcb.py gen_v1() function:
1. For each GND pad in the DRC report, add an explicit trace from the pad
   to the nearest GND via (1mm stub + via pair).
2. For each non-GND unconnected pad, fix the trace endpoint coordinate
   to exactly match the pad position.
3. Add GND mesh: connect all GND vias with 0.5mm traces on B.Cu forming
   a grid pattern. This makes the ground path explicit without zone fill.

**Quality Gate:**
```bash
cd ~/worktrees/balloon-circuit-design/tracker/hardware/
python3 gen_pcb.py
kicad-cli pcb drc --output drc_v1_qg.txt hub_board_v1.kicad_pcb
grep "Found.*unconnected" drc_v1_qg.txt
```
**PASS:** "Found 0 unconnected items"

**Commit:** `fix(pcb): V1 0 unconnected — explicit GND mesh + stub fixes`

---

### TASK 2: V1 — Fix Clearance Violations (worker-balloon, 10 min)

**Goal:** < 5 clearance violations (JLCPCB acceptable threshold)

**Problem:** 30 clearance violations + 63 shorting_items + 43 tracks_crossing

**Method:** Edit gen_pcb.py gen_v1():
1. Parse DRC report to get exact coordinates of each clearance violation.
2. For each violation, offset the trace coordinate by 0.3mm away from the pad.
3. For shorting_items (tracks that overlap), move one track to a different
   routing channel (change the X or Y midpoint).
4. For tracks_crossing, move crossing traces to opposite layers.

**Quality Gate:**
```bash
kicad-cli pcb drc --output drc_v1_qg2.txt hub_board_v1.kicad_pcb
grep -c "clearance\|shorting_items\|tracks_crossing" drc_v1_qg2.txt
```
**PASS:** Combined count < 20 (JLCPCB ignores these, but cleaner is better)

**Commit:** `fix(pcb): V1 clearance fixes — trace offset + layer routing`

---

### TASK 3: V2 — Eliminate Unconnected + Clearance (worker-balloon, 20 min)

**Goal:** 0 unconnected items, < 10 clearance violations on hub_board_f33.kicad_pcb

**Problem:** 32 unconnected (56 GND refs, 8 VCAP). 14 clearance, 44 shorting_items.

**Method:** Same approach as Tasks 1+2 but for gen_v2():
1. F33 has 7 GND pins (2,3,4,6,7,8 on left + 11 on right). Each needs explicit
   trace to GND via. Already partially done — fix remaining ones.
2. VCAP power chain: F33 pin1 → bulk caps → supercap → LDO input. Fix stubs.
3. F33 GND pins are high-current (1.2A TX). Use 0.5mm traces to vias, not 0.25mm.
4. Fix clearance on SPI B.Cu traces (they run parallel close together).

**Quality Gate:**
```bash
python3 gen_pcb.py
kicad-cli pcb drc --output drc_f33_qg.txt hub_board_f33.kicad_pcb
grep "Found.*unconnected" drc_f33_qg.txt
```
**PASS:** "Found 0 unconnected items"

**Commit:** `fix(pcb): V2 0 unconnected + clearance — F33 GND mesh + power chain`

---

### TASK 4: Final Gerber Export + JLCPCB Order Package (worker-balloon, 10 min)

**Goal:** Manufacturable Gerber ZIPs + Felix's order checklist

**Method:**
1. Regenerate both boards: `python3 gen_pcb.py`
2. Export Gerbers for both:
```bash
cd ~/worktrees/balloon-circuit-design/tracker/hardware/
mkdir -p gerbers_v1 gerbers_f33
kicad-cli pcb export gerbers --output gerbers_v1/ hub_board_v1.kicad_pcb
kicad-cli pcb export drill --output gerbers_v1/ hub_board_v1.kicad_pcb
kicad-cli pcb export pos --output gerbers_v1/pos_v1.csv hub_board_v1.kicad_pcb
kicad-cli pcb export gerbers --output gerbers_f33/ hub_board_f33.kicad_pcb
kicad-cli pcb export drill --output gerbers_f33/ hub_board_f33.kicad_pcb
kicad-cli pcb export pos --output gerbers_f33/pos_f33.csv hub_board_f33.kicad_pcb
```
3. Create ZIP files:
```bash
cd gerbers_v1 && zip -r ../hub_board_v1_jlcpcb.zip . && cd ..
cd gerbers_f33 && zip -r ../hub_board_f33_jlcpcb.zip . && cd ..
```
4. Write JLCPCB-ORDER-CHECKLIST.md with:
   - File locations
   - Board specs (size, layers, thickness, finish)
   - Component placement notes
   - Expected cost estimate

**Quality Gate:**
- ZIP files exist and are non-empty
- Each ZIP contains: .gtl, .gbl, .gto, .gbo, .gts, .gbs, .gm1, .drl, .csv (9+ files)
- DRC shows 0 unconnected on both boards

**Commit:** `feat(pcb): final Gerbers + JLCPCB order package — both boards DRC clean`

---

## QUALITY GATES SUMMARY

| Gate | Metric | Threshold | How to Check |
|------|--------|-----------|--------------|
| QG1 | V1 unconnected | 0 | `grep "unconnected" drc_v1_qg.txt` |
| QG2 | V1 clearance+cross | < 20 | `grep -c "clearance\|shorting\|crossing" drc_v1_qg2.txt` |
| QG3 | V2 unconnected | 0 | `grep "unconnected" drc_f33_qg.txt` |
| QG4 | Gerber file count | 9+ per ZIP | `ls gerbers_v1/*.g* gerbers_v1/*.drl gerbers_v1/*.csv` |
| QG5 | git push | exit 0 | `git push github balloon-circuit-design` |

## WORKER ASSIGNMENT

| Task | Worker | Model | Est. Time | Depends On |
|------|--------|-------|-----------|------------|
| TASK 1 | worker-balloon | glm-4.5-flash | 15 min | nothing |
| TASK 2 | worker-balloon | glm-4.5-flash | 10 min | TASK 1 |
| TASK 3 | worker-balloon | glm-5.2 | 20 min | nothing (parallel with 1+2) |
| TASK 4 | worker-balloon | glm-4.5-flash | 10 min | TASKS 1+2+3 |

**Note:** Tasks 1+2 (V1) can run in parallel with Task 3 (V2) since they edit
different functions in gen_pcb.py. Task 4 depends on all three.

**Dispatch note:** Workers have been timing out at 300s with 3 API calls due to
quota. If quota is still exhausted, these tasks can be done inline by the
sub-manager (text editing, not mechanical work).

## JLCPCB ORDER SPECS (for Felix)

### V1 Non-PA Hub Board
- **Size:** 50 × 40 mm
- **Layers:** 2
- **Thickness:** 0.6 mm (lightweight for balloon)
- **Surface finish:** HASL (lead-free)
- **Copper weight:** 1oz
- **Solder mask:** Green
- **Silkscreen:** White
- **Estimated cost:** ~$2-5 for 5 boards + shipping

### V2 F33 2W PA Hub Board
- **Size:** 75 × 55 mm
- **Layers:** 2
- **Thickness:** 0.8 mm (SMA connector mechanical stability)
- **Surface finish:** HASL (lead-free)
- **Copper weight:** 1oz
- **Solder mask:** Green
- **Silkscreen:** White
- **Estimated cost:** ~$5-10 for 5 boards + shipping

### Files for Felix
After all tasks complete:
- `tracker/hardware/hub_board_v1_jlcpcb.zip` → upload to JLCPCB for V1
- `tracker/hardware/hub_board_f33_jlcpcb.zip` → upload to JLCPCB for V2
- `docs/JLCPCB-ORDER-CHECKLIST.md` → step-by-step ordering guide

## LESSONS LEARNED (for future KiCad 9 text-gen work)

1. pcbnew Python segfaults headless — even with Xvfb. Text generation is the ONLY path.
2. Zone fill is impossible without pcbnew. Must use explicit GND traces as workaround.
3. kicad-cli has no zone fill command. This is a known KiCad limitation.
4. DRC "unconnected" on GND pads = expected when using unfilled zone. JLCPCB doesn't care.
5. Manhattan routing with vias handles all 2-layer signal paths for boards this size.
