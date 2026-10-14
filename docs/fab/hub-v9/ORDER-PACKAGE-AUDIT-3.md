# ORDER PACKAGE AUDIT — the CPL/gerber cross-check, and a THIRD stale artefact

**Date:** 2026-10-14 · **Status:** package verified; one artefact is stale and must not be used.
**Continues:** `ORDER-PACKAGE-AUDIT.md`, `-2.md`.

---

## 0. Headline — the shipped package is CORRECT; an older upload set is STALE

I cross-checked the CPL against the gerbers because the coordinates disagreed with an
`~/jlc-pcba-work/upload_hub_cpl.csv` from earlier in the day.

**Measured, with pcbnew — the shipped artefacts are correct:**

| artefact | outline | verdict |
|---|---|---:|
| **`docs/fab/hub-v9/gerbers/hub_v9.kicad_pcb`** (shipped) | **70.2 × 71.7 mm** | ✅ correct |
| **`gerbers/hub_v9-Edge_Cuts.gm1`** (the plotted outline) | **70.0 × 71.6 mm** | ✅ correct |
| `/tmp/h08_fill.kicad_pcb` (route source) | 70.2 × 71.7 mm | ✅ |
| `tracker/hardware/hub_board_v9.kicad_pcb` (**the repo source file**) | **103.2 × 115.0 mm** | ⚠ **STALE** |
| `~/jlc-pcba-work/upload_hub_cpl.csv` (**older upload set**) | coords ~+10 mm off in X | ⚠ **STALE** |

**So: what we would send to JLCPCB is the 70 × 70 board (ADR-068), correctly.** The gerbers
and my CPL agree with the board. **The 103 × 115 board file in the repo is a superseded
artifact that was never updated when ADR-068 changed the outline.**

## 1. My own verifier was wrong — worth recording

`verify_cpl_matches_board.py` first reported **"MISMATCH (134.91 mm)"**. **That was my bug:**
KiCad writes footprint Y **negated** in position files (a Y-flip convention), and I compared
signed values. The board has `ANT1 Y = +15.4`; the CPL writes `−15.400000`. Negating Y gives a
**0.0000 mm** deviation. **The CPL is right; my check was wrong.**

**That is the fifth instance of the same lesson** — the fault was in my verification, not the
artefact. Guard: **when a check reports a wild discrepancy, verify the CHECK on a case whose
answer is known before believing the verdict.**

## 2. Two REAL defects in my own package, found by comparing with the older set

### (a) Wrong BOM column header
The older upload file uses **`JLCPCB Part #`** (the name JLC's BOM tab actually expects);
**I generated `LCSC Part #`.** Fixed by emitting **both** columns.

### (b) The CPL is in kicad-cli's native format, not JLC's expected format

| | columns |
|---|---|
| mine (`kicad-cli pcb export pos --format csv`) | `Ref,Val,Package,PosX,PosY,Rot,Side` |
| **JLC expects** | `Designator,Mid X,Mid Y,Layer,Rotation` |

JLC's validators are picky about header names and `mm` suffixes. **Mine is loadable but not
in the expected shape**, so an upload could be rejected or mis-read. Fixed by converting.

## 3. A part-number CONTRADICTION between our own artefacts

**The SS24 diode has two different LCSC numbers in our own files:**

| file | SS24 → |
|---|---|
| `hub_v9_bom_mapping_report.md` (live API, "193 hits") | **`C50645`** |
| `upload_hub_bom.csv` (newer, an actual upload attempt) | **`C78573`** |

**This is exactly the drift class this whole audit has been about.** I am **NOT** picking one
silently. The mapping report's live-API evidence supports `C50645`
(MDD `SS24`, SMA/DO-214AC, stock 777,745); `C78573` is unexplained. **Flagged for resolution
against the live API before ordering.**

## 4. What I fixed

- **BOM**: emits **`Comment, Designator, Footprint, JLCPCB Part #, LCSC Part #`** (both names);
  malformed row repaired (D1 recovered); not-on-board DNP rows dropped; U5/U6 as DNP per the
  locked split, conflict recorded.
- **CPL**: converted to **JLC's header contract** (`Designator, Mid X, Mid Y, Layer, Rotation`,
  values suffixed `mm`, `Top`/`Bottom`), from the board-verified data.
- **Verifiers**: `verify_bom_against_board.py` (passes) and a corrected
  `verify_cpl_matches_board.py` (Y-negation aware).

## 5. Newly-recorded stale artefacts (do NOT use)

1. `tracker/hardware/hub_board_v9.kicad_pcb` — **103 × 115 mm**, superseded by ADR-068's
   70 × 70. It is the repo *source* file, so this matters for any future re-export. **It should
  be regenerated at 70 × 70 or clearly marked superseded.**
2. `~/jlc-pcba-work/upload_hub_bom.csv` / `upload_hub_cpl.csv` — earlier upload set, stale
   coordinates and the `C78573` SS24 number.
3. `~/jlc-pcba-work/hub_v9_bom_pcba.csv` — the malformed CSV (unquoted comma).

## 6. Reproduce

```
cd tracker/hardware
~/venvs/kicad/bin/python verify_outline.py            # gerbers 70.2x71.7; repo src 103.2x115.0
~/venvs/kicad/bin/python verify_bom_against_board.py  # exit 0 = consistent
~/venvs/kicad/bin/python verify_cpl_matches_board.py  # Y-negation aware
```
