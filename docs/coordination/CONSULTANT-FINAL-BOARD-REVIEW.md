# CONSULTANT FINAL BOARD REVIEW — V2-ADC Balloon Board

**Reviewer:** Senior PCB reviewer (subagent)
**Date:** 2026-08-05
**Board:** `tracker/hardware/output/v2_adc_JLCPCB_READY.kicad_pcb`
**Gerbers:** `tracker/hardware/output/gerbers_v2/`
**Tools:** kicad-cli 9.0.8, python3.14 + pcbnew 9.0.8

## VERDICT: 🔴 NEEDS CHANGES — DO NOT ORDER

## Findings

### 1. DRC — PASS (but vacuous)
`kicad-cli pcb drc --format json` → 0 violations, 0 unconnected items.
However this is trivially true: see below.

### 2. Board contents — 🔴 CRITICAL: BOARD IS EMPTY
Programmatic inspection (pcbnew 9.0.8):
- **Footprints: 0   Pads: 0   Tracks: 0   Zones: 0   Nets: 1 (only the empty net)**
- No components, no traces, no copper zones of any kind.
- The board file contains only: layer stack, a 50×40 mm Edge.Cuts rectangle,
  and one silkscreen text line ("Balloon V2-ADC — JLCPCB 2-layer 0.6mm").

### 3. GPIO / pad-to-net assignments — 🔴 UNVERIFIABLE
There are no pads. LED-on-GPIO9, no-FEM, ADC-disabled cannot be checked.
The schematic connectivity simply does not exist on the PCB.

### 4. Board dimensions — 🔴 MISMATCH
- Edge.Cuts rectangle: 50.15 × 40.15 mm (50×40 nominal) ✅ correct outline.
- Layer count: 2 ✅ correct.
- **Stackup thickness declared: 1.600 mm** ❌ — the file itself specifies
  1.6 mm, contradicting the 0.6 mm requirement AND the silkscreen text.
  JLCPCB would fab a 1.6 mm board from this file.

### 5. GND zone fill — 🔴 NO ZONE EXISTS
Zero zones defined. There is nothing to fill.

### 6. Gerbers — 🔴 MOSTLY EMPTY
- `Edge_Cuts.gm1` (581 B): correct 50×40 mm profile ✅
- `F_Silkscreen.gto` (14.5 KB): contains only the title text ⚠️
- `F_Cu.gtl`, `B_Cu.gbl`, all masks/pastes/courtyards (~450-480 B):
  header + **empty aperture list** + `M02*`. Zero copper, zero pads.
- A JLCPCB order from these gerbers would yield a blank etched rectangle.

## Root cause
`v2_adc_JLCPCB_READY.kicad_pcb` is not a populated layout — it appears to be
a placeholder/outline file. The "DRC clean, 0 unconnected" claim is accurate
but meaningless for an empty board.

## Required before ordering
1. Open the actual V2-ADC layout (schematic-driven update from the source
   project, not this outline file) and place all footprints.
2. Set board stackup thickness to 0.6 mm in Setup → Board Setup → Physical
   Stackup (currently 1.6 mm).
3. Route all nets; create and fill the GND zone(s).
4. Re-export gerbers; copper layers must contain real aperture/draw data.
5. Re-run DRC and confirm violations == 0 against the populated board.

**Recommendation to Felix: do not place the JLCPCB order from this file.**
