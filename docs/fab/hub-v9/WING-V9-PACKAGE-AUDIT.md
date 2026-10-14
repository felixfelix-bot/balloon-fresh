# WING v9 BOARD — package audit (same checks as the hub)

**Date:** 2026-10-14 · **Status:** routed, electrically complete, **two artefact defects FIXED**,
package re-exported with a recorded hash. No audit-4-class blocker.

The goal requires every board routed, DRC-passing and JLC-orderable. The wing is the second
board in the order, so it gets the same audit the hub received.

## Measured state

| property | value |
|---|---|
| outline | **184.1 × 25.1 mm** (edges bbox X −8.05…176.05, Y −0.05…25.05) |
| footprints | **15** |
| tracks | 28, on **4 nets** (`SOLAR_P`, `SOLAR_N`, `SOLAR_MID1`, `SOLAR_MID2`) |
| **unconnected items** | **0** ✅ |
| DRC violations | 37 |

## The 37 DRC items, classified as the hub's were

| type | count | fab-legality |
|---|---:|---|
| `lib_footprint_issues` | 15 | **Environment artifact** — `kicad-cli` cannot read a project-local `fp-lib-table` (measured on the hub too). Not a board defect. |
| `silk_edge_clearance` | 9 | **Ruleset artifact** — JLC *clips* silkscreen at the board edge; it does not reject. |
| `nonmirrored_text_on_back_layer` | 6 | **Cosmetic** — back-layer reference designators not mirrored. JLC does not care. |
| `text_height` | 2 | **Ruleset** — board setup wants ≥0.8 mm silk text, actual 0.6 mm. |
| `track_dangling` | 2 | ✅ **RESOLVED — see below.** |
| `silk_overlap` | 2 | Clipped, not rejected. |
| `silk_over_copper` | 1 | "Silkscreen clipped by solder mask" — clipped, not rejected. |

**35 of 37 are artifact or clip-not-reject classes. The remaining 2 are resolved.**

## The 2 `track_dangling` — RESOLVED, not a defect

**Measured:** for all four nets, the set of track endpoints that are **neither shared with
another track nor landing on a pad** is **EMPTY**:

```
SOLAR_P     8 tracks | 3 pads | unshared-not-on-pad endpoints: []
SOLAR_N    12 tracks | 3 pads | unshared-not-on-pad endpoints: []
SOLAR_MID1  4 tracks | 4 pads | unshared-not-on-pad endpoints: []
SOLAR_MID2  4 tracks | 4 pads | unshared-not-on-pad endpoints: []
```

Combined with **0 unconnected items**, the geometry is consistent with a **legal tapped
solar-string**: the `SOLAR_MID1/2` taps land on another net's path rather than a second pad of
their own, which DRC reports as a dangling end while being electrically correct.

## Two artefact defects FOUND and FIXED

### (a) thickness 0.6 in the file, decision 0.8
Exactly the hub's defect class. **Fixed: 0.6 → 0.8.** (And corrected in the export script's own
comment, which said *"a 2-layer **0.6 mm** board"* — a stale claim carried in the tool itself.)

### (b) `FB1` / `RF1` said DNP in TEXT but not in the FLAG
```
FB1: value='FerriteBead_0402_DNP_V2only'  IsDNP=False
RF1: value='RF_ProvisionPad_v2only'       IsDNP=False
```
The intent is recorded **only in the value string**. **A BOM/CPL generator reads the DNP FLAG** —
so it would have tried to **place v2-only parts on a v1 board**. This is the mirror image of the
hub's "claimed DNP, flag absent" defect. **Fixed: both flags set to DNP; verified True.**

## Package re-exported

```
tracker/hardware/output/gerbers_wing_v9_jlcpcb.zip
sha256 5e36d1cd1a88a71a6a32c656faa5e45b46ee2099c6ea546c998822a9503aa1c3
drill: wing_board_v9-NPTH.drl 3 holes · wing_board_v9-PTH.drl 8 holes
CPL rows: 15
```

## BOM/CPL: correctly absent — nothing to assemble

All 15 footprints are solar cells, NPTH holes, fiducials, the board-edge tab (`J1`) and the two
now-DNP v2 provision pads. **There is no purchasable non-DNP part on the wing**, so JLC assembly
has nothing to place. (This matches the earlier note that the wing PCBA is not meaningful.)

## CORRECTION to my own first pass

My first wing write-up said the `SOLAR_P`/`SOLAR_N` nets had pads *"at x = −5.0, which looks
OFF-BOARD"*, and implied `FB1`/`RF1` *might* need their flag set.

**Both were wrong, and measured so:**
1. **Off-board pads: ZERO.** The outline bbox starts at **X = −8.05**, so x = −5.0 is **inside**.
   Those four points are `J1`'s wing-tab pads — the hub-mating interface the board is shaped
   around (the same edge-launched-interface class as the hub's 68 edge items).
2. `FB1`/`RF1` **did** need the flag — so the second guess happened to be right, but it was a
   guess; the measurement is what settled it.

## Reproduce

```
~/venvs/kicad/bin/python ~/audit_wing.py            # outline, unconnected, DRC histogram
~/venvs/kicad/bin/python ~/check_wing_truth.py      # dangling-endpoint resolution
cd tracker/hardware/wing_board && bash export_wing_v9_gerbers.sh
sha256sum ../output/gerbers_wing_v9_jlcpcb.zip
```
