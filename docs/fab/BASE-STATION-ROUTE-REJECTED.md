# BASE-STATION ROUTE — first pass REJECTED: it is below the JLC floor

**Date:** 2026-10-14 · **Status:** ⚠ **route produced but NOT acceptable. Diagnosed, not shipped.**

The first route attempt ran with `--track-width 0.2 --clearance 0.2 --via-size 0.6 --via-drill 0.3
--board-edge-clearance 0.6`. It **completed**, reported **33/35 nets routed, 107 vias**, and **also
relaxed the fab floor in the output project.** Both facts matter.

## What the router said, verbatim

```
"Routed": 33, "vias": 107, "regraded_nets": 35,
"pad_pairs_open": {"count": 2, "nets": ["XIN", "XOUT"]}
"min_clearance_used": 0.1   (below nominal 0.2)
```

and then, writing `output/bs_v1_routed.kicad_pro`:

```
FAB FLOOR RELAXED -- the output project declares a smaller minimum than the board originally did:
  via diameter: 0.5 -> 0.25 mm; 15 of 117 object(s) are below the ORIGINAL 0.5mm
  via annular ring: 0.1 -> 0.05 mm; 14 of 117 object(s) are below the ORIGINAL 0.1mm
  hole diameter: 0.3 -> 0.15 mm
  copper-to-hole clearance: 0.25 -> 0.1 mm
Every checker (check_drc, board_score, KiCad's own DRC) grades against the NEW value, so this
copper will read clean. Confirm your fab supports it; if the original number was a real process
limit, re-route at that floor rather than shipping this project.
```

**The router warns about its own self-grading.** Grading against the rewritten project would show
**clean** copper that **JLC cannot manufacture.**

## Measured against the FROZEN floors instead

`grade_route.py` reads the copper from the board itself, so the rewritten project cannot hide it:

| property | measured | frozen floor | JLC floor | verdict |
|---|---:|---:|---:|---|
| **min track width** | **0.0889 mm** | 0.20 | **0.10** | ⛔ **BELOW JLC** |
| **min via diameter** | **0.25 mm** | 0.60 | **0.45** | ⛔ **BELOW JLC** |
| **min via drill** | **0.15 mm** | 0.30 | **0.20** | ⛔ **BELOW JLC** |

**All three are below JLC's own capability floor**, not merely below our 2× margin. **This board
could not be ordered as routed.**

## Diagnosis: they are ESCALATION artifacts, not a bad router run

The track histogram is decisive:

| width | count | |
|---:|---:|---|
| **0.0889 mm** | **560** | ⛔ below the JLC 0.10 floor |
| 0.1248 mm | 3 | below the frozen 0.20 |
| **0.2000 mm** | **455** | ✅ the requested width |

**0.0889 mm is not a width anyone asked for** (0.2 was requested). **455 tracks are at exactly the
requested 0.2 mm** — so the router routed the bulk correctly and then, **while escalating** to close
the remaining connections, **added 560 undersized segments plus vias down to 0.25/0.15.**

**The affected nets are `GND` and `DET_VOUT`** (plus the two open `XIN`/`XOUT` pairs) — i.e. the
escalation targeted grounds/stitching and the detector line, **not the signal routing.**

**So the fix is not a redesign:** route with **escalation disabled** (or bounded to widths ≥ 0.10)
so the router cannot manufacture sub-floor copper, and accept the resulting unrouted nets as a
**declared, measured residue** instead of hiding them under a relaxed project.

## Why this is an important catch, not a failure

**It is the self-grading hazard the hub already taught us, in a sharper form.** For the hub the
router rewrote `clearance 0.2 → 0.175`; here it rewrote **four floor values at once**, and the
router's own message says every checker will then read clean. **A tool that relaxes the standard it
is graded against will always pass.**

**The guard that caught it: read the copper from the BOARD, not the project, and compare against a
floor recorded OUTSIDE the tool.** That is now `grade_route.py`, and it is reusable.

## Corrective plan (next)

1. **Re-route with escalation off / floored at 0.10 track and 0.20 drill**, so no sub-floor copper
   can be produced.
2. **Grade with `grade_route.py`** — it must show min track ≥ 0.10, via ≥ 0.45, drill ≥ 0.20.
3. **Declare the residual unrouted nets** (`XIN`/`XOUT` are the crystal — the shortest, most local
   connection on the board) as a measured list, and either hand-route them at 0.2 or accept them
   with a recorded rationale.
4. **Never ship the relaxed `.kicad_pro`.** The frozen rule file is the standard; the router's
   output project is a by-product.

## Also discovered (kept)

**`XIN`/`XOUT` connect `Y1` to `U_MCU`** — the 12 MHz crystal. **The crystal is the last thing that
should be left unrouted**: it is a ≤ 5 mm connection and its stub length and symmetry matter for
clock integrity. Worth checking **placement proximity** of `Y1` to `RP2040` pins 24/25 before
hand-routing, because a long crystal stub is a design issue, not a routing inconvenience.

## Reproduce

```
cd tracker/hardware/base_station
~/venvs/kicad/bin/python grade_route.py      # verdict vs the FROZEN floor
~/venvs/kicad/bin/python diagnose_route.py   # width histogram + offending nets
```
