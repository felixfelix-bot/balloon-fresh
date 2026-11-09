# Wing interconnect (solar cell connector) — JLCPCB order bundle

**The board that the three solar cells solder to, and that connects each wing to the hub.**
Built and verified 2026-11-10. Rebuild any time:

```
/usr/bin/python3 tracker/hardware/build_wing_order_bundle.py
```

## Upload one file

```
wing-interconnect-jlcpcb-upload.zip     8,187 B, 12 entries
sha256 230478400d398402c3382cb743bb219c96e58466b136fde6ddf88fa4637bf988
```

9 gerber layers + drill + BOM + CPL.

## Board

| | |
|---|---|
| Dimensions | **34.60 × 20.00 mm** centreline (34.70 × 20.10 stroke-inflated bbox) |
| Layers | **2** |
| Thickness | **0.4 mm** — chosen for mass: 0.62 g/wing, 2.50 g for four |
| Quantity | operator's choice — 4 wings, so **8 or 12** gives spares |
| Assembly | **Top side only**, 3 placements |

## What JLC places: three diodes. That is the whole BOM.

| ref | part | LCSC | purpose |
|---|---|---|---|
| `D1`, `D2`, `D3` | SS24 (SMA) | **`C50645`** | per-cell bypass — one across each cell |

Three cells in series (`SOLAR_P → MID1 → MID2 → SOLAR_N`), one Schottky across each. A shaded cell
gets bypassed instead of dragging the string down. Same part the v10 hub uses for its bypass diodes.

## What YOU solder: 4 solder-point footprints, no purchasable part

| ref | function | nets |
|---|---|---|
| `J1` | wing → hub tab, 2 pads | `SOLAR_P`, `SOLAR_N` |
| `SC1` | cell 1 tail lands | `SOLAR_P`, `SOLAR_MID1` |
| `SC2` | cell 2 tail lands | `SOLAR_MID1`, `SOLAR_MID2` |
| `SC3` | cell 3 tail lands | `SOLAR_MID2`, `SOLAR_N` |

These carry **no LCSC number** and are deliberately absent from the BOM. A BOM containing them
stalls the order on a no-match. See `solder-points-NOT-FOR-JLC.csv`.

The cells stay on the foam; only their `+`/`−` tails reach this board (ADR-132).

## One defect this bundle build found

The board declared only `F.Cu`, `B.Cu`, silkscreen and `Edge.Cuts` — **no `F.Mask`, `B.Mask`,
paste layers**. The gerber exporter silently omitted them, so there was no mask opening on any pad
and **JLCPCB could not have produced this board**.

`kicad-cli pcb drc` reported **0 violations / 0 unconnected** on that board. DRC checks geometry; it
does not check whether the *layer set* is complete. "DRC clean" is not "orderable" — the same lesson
as the v10 `lib_footprint_issues`, which were also invisible to the connectivity engine.

Fixed by declaring the mask and paste layers in the generator. Verified: **9/9 required layers
export**, DRC still **0/0**, routing intact at 32 segments + 2 vias.

## Two ways this board was nearly broken during packaging

1. **Regenerating the board wiped the routing.** `build_wing_interconnect.py` emits placement-only by
   design; running it over the routed file dropped 32 tracks and 2 vias and took DRC from 0/0 to
   0 violations / **6 unconnected**. Recovered from git, then the layer table was patched **in place**
   instead. The generator fix is recorded so the next regeneration includes the layers, but the
   routed file must still never be regenerated casually.
2. **Filename case.** `kicad-cli` names outputs from the board's layer *names*, which here are
   lowercase, so it emits `-f_silkscreen.gto` not `-F_Silkscreen.gto`. A hardcoded stem check
   reported two "missing layers" that were present. Now matched case-insensitively on extension.

## Order settings

- **2 layers** · **0.4 mm** · **1 oz** · **HASL is fine** (no fine-pitch parts, vias are 0.6/0.3)
- Assembly: **Top side only**, Economic class OK — three SS24s are Extended-library but there are
  only three
- **Parts substitution: OFF**
- No castellation, no edge plating

## Verified before this bundle

| check | result |
|---|---|
| DRC | **0 violations / 0 unconnected** |
| Copper routing | 32 segments, 2 vias, all 4 nets connected |
| Gerbers | **9/9 required layers present** |
| BOM ↔ CPL | 3 = 3 designators |
| Board size | 34.60 × 20.00 mm centreline (measured, not remembered) |

## Stale figures corrected

ADR-132 and ADR-134 both state **"44 × 20 mm = 8.8 cm², 0.79 g/wing"**. That predates the width
being derived from pad extents. The generator's own comment records the measurement: *pads end at
x=33.00, +1.6 edge = 34.6* — 11 mm of the right-hand side carried no copper, so it was cut.

**The board is right; both ADRs are stale.** Corrected in place with a CORRECTION note rather than
rewritten, per the repo's annotate-don't-rewrite convention.
