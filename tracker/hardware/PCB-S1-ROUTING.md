# PCB-S1 — flight board routed under ONE frozen rule set, at $0

**Date:** 2026-09-17 · **Card:** `t_a93eab7b` · **Parent:** `t_7c65638f` (S0, placement frozen)
**Plan:** `PLAN-flight-board-routing.md` §S1 · **Referee:** `drc_score.py` (`drc_snapshots/history.jsonl`)

## Verdict

**GATE S1 reached** — `shorts = 0`, `clearance = 0`, `unconnected = 0`, `fp = 20`, measured under
ONE frozen rule file and the frozen S0 placement hash.

| attempt | tool | board (`output/`) | fp | viol | short | clr | unconn | vias | copper mm | gate |
|---|---|---|---|---|---|---|---|---|---|---|
| S0 baseline (pre-route) | krt-place_optimize | `v_c3_flight_4layer_placed.kicad_pcb` | 20 | 4 | 0 | 0 | 64 | 0 | 0 | — |
| **A** | KRT A* (`route.py`) | `v8_krt_routed.kicad_pcb` | 20 | 10 | **0** | **0** | **0** | 57 | 663.5 | **PASS** |
| A2 (variant) | KRT A* + tap relocation | `v8_krt_v2_routed.kicad_pcb` | 20 | 9 | **0** | **0** | **0** | 48 | 739.6 | **PASS** |
| **B** | Freerouting 2.4.1 | `v8_freerouting_routed.kicad_pcb` | 20 | 18 | 0 | 0 | **1** | 43 | 678.7 | fail (1 open) |
| diagnostic | Freerouting (old v7 board, re-scored) | `fr_trial/v7_4layer_freerouted.kicad_pcb` | 20 | 204 | 0 | 125 | 1 | 66 | 577.8 | — |

## Frozen inputs (the "ONE rule set")

| artifact | sha256 |
|---|---|
| rule file `tracker/hardware/jlcpcb-s1-frozen.kicad_dru` | `5acd7dced4a0d8b3edb8b3b977cc2a110a0a97fba0c6d867ce698b243835ca59` |
| placement `output/v_c3_flight_4layer_placed.kicad_pcb` (S0, commit `ff19ea9`) | `f3cf0143e7deff991e9650643f1322945388fd135efbf5191f51520dcd6edaa6` |
| frozen project `output/v_c3_flight_4layer_placed.kicad_pro` (netclass carrier) | `a29acec391bae6b1d53f69be95e0fcce6af5bae7c6d06a4ba0706f7a54920238` |

Rule values (JLCPCB standard capability with 2× margin): clearance ≥ 0.20 mm, track width ≥ 0.20 mm,
via diameter ≥ 0.60 mm, via hole ≥ 0.30 mm (vias only), hole-to-hole ≥ 0.25 mm.
**Every attempt board carries byte-identical copies** of that `.kicad_dru` and that `.kicad_pro`
as its siblings — verified by sha256 before scoring (`s1-rule-freeze.json`).

Why this makes the comparison honest: the board's Default net class already carries
`clearance 0.2 / track 0.2 / via 0.6 / drill 0.3`, and the router inputs are derived from the same
numbers — KRT got `--clearance 0.2 --track-width 0.2 --via-size 0.6 --via-drill 0.3`; the Specctra
DSN exported for Freerouting carries `(width 200) (clearance 200)` (µm) and a
`Via[0-3]_600:300_um` via. So referee and routers agree by construction rather than by hope.

`.kicad_dru` pickup was **verified, not assumed**: a temporary rule `(constraint clearance (min 3.0mm))`
next to the placed board took the DRC from 4 violations to 165 (161 `clearance`); with the frozen
file the same board reports only the 4 cosmetic `silk_edge_clearance`.

## Attempt A — KRT A* (`drandyhaas/KiCadRoutingTools` 0.22.0)

```
/usr/bin/python3.14 py_router/route.py output/v_c3_flight_4layer_placed.kicad_pcb \
    output/v8_krt_routed.kicad_pcb '*' \
    --track-width 0.2 --clearance 0.2 --via-size 0.6 --via-drill 0.3 \
    --power-nets GND +3V3 --power-nets-widths 0.3 0.3 \
    --fab-tier standard --no-fix-drc-settings --write-fill --stats
```
19 s wall, 400 k A* iterations, 22/22 single-ended nets routed, 66/66 multi-point pads connected
(76/76 pad pairs), 57 vias, 663.5 mm copper, in-run KiCad-oracle recheck: 0 links remaining.
`--write-fill` filled both plane zones (In1.Cu GND, In2.Cu +3V3) with KiCad's own ZONE_FILLER.

Variant **A2** added `--same-net-pad-clearance 0.2` + `KICAD_TAP_RELOCATION=1` to push tap vias out
of pads: gate still passes, residual drops 10 → 9 (one fewer clamped via), at the cost of +76 mm copper.

## Attempt B — Freerouting 2.4.1

```
pcbnew.ExportSpecctraDSN(placed) -> v8_freerouting.dsn      # rules 0.2/0.2, via 0.6/0.3, 2 planes
xvfb-run -a $JAVA_HOME(25)/bin/java -Dgui.enabled=false \
    -jar ~/tools/freerouting/freerouting.jar -de v8_freerouting.dsn -do v8_freerouting.ses -mp 10 -mt 4
/usr/bin/python3.14 s1_import_freerouting.py placed v8_freerouting.ses v8_freerouting_raw.kicad_pcb
/usr/bin/python3.14 py_tools/fill_for_delivery.py <raw> -o output/v8_freerouting_routed.kicad_pcb
```
Freerouting auto-detected both inner layers as dedicated power planes ("contains a large conduction
area covering >50% of the board"), reporting 0 unrouted nets with 76 internal violations after 3
passes + 3 min of optimization (its own `-mt 4` warning: multi-threaded optimization is known to
generate clearance violations).

Import used **pcbnew's canonical `ImportSpecctraSES`** (works headless on KiCad 9.0.8 + python3.14 —
the in-repo `ses_import.py` predates that and maps unknown layers to F.Cu, which would short a
4-layer board). `s1_import_freerouting.py` imports and then **proves the placement did not move**:
all 20 footprints identical position/orientation vs the frozen board (219 segments on
F.Cu/In1.Cu/In2.Cu/B.Cu, 43 vias 0.6/0.3).

Result: `shorts 0`, `clearance 0`, **`unconnected 1`** → gate not reached. The open link is
`Via [GND] F.Cu–B.Cu @ (34.25, 21.72)` ↔ `Pad 8 [GND] of U2 @ (30.48, 16.00)`: Freerouting treats
the GND plane as fully connected, so it never stitched that SMD GND pad down to In1.Cu.

## Residual per class — declared, not hidden

| class | count | adjudication |
|---|---|---|
| `silk_edge_clearance` (all attempts) | 4 | pre-existing cosmetic (also on the S0 board); JLCPCB-ignored |
| `via_diameter` 0.45 vs 0.60 (A: 3, A2: 2) | 2–3 | **via-in-pad clamp**: the tap via is placed inside a small power pad where a 0.6 mm via cannot keep an annular ring; 0.45/0.2 is JLCPCB's published standard floor, i.e. fab-legal but below our 2× margin. Tap relocation did not find an off-pad site for these two. S2 material. |
| `drill_out_of_range` 0.2 vs 0.3 (A: 3, A2: 2) | 2–3 | same two/three vias, seen from the hole side. Same adjudication. |
| `track_width` 0.1998 vs 0.2000 (A2: 1) | 1 | **rule-strictness/rounding artifact**: 200 nm under the floor on one VDIV_MID segment — not a fabrication issue. |
| `track_width` 0.15 vs 0.20 (B: 14) | 14 | Freerouting's optimizer descended below the DSN's 0.2 mm floor (10 on GND, 2 +3V3, 2 SPI_NSS, 2 LR_DIO0). Real geometry; below the requested size; fab-legal at JLCPCB's 0.10–0.15 mm floor. |

**No stale-fill class appeared.** The `hole_clearance` cluster ("via vs In1.Cu GND pour", 33
observed in earlier work) is absent from every row: re-filling the KRT board with KiCad's
ZONE_FILLER reproduces the shipped numbers exactly (`fill_for_delivery` on `v8_krt_routed`:
`unconnected 0 -> 0`, DRC identical: 3 `via_diameter` + 3 `drill_out_of_range` + 4 silk).
Note: `kicad-cli pcb drc --refill-zones` does **not exist** in KiCad 9.0.8 — persistent fill
(`--write-fill` / `fill_for_delivery`) is the way to honour "refill after every import" here.

## What the old v7 numbers actually were (the KNOWN-ARTIFACT hint, re-tested)

Re-scoring the old freerouted v7 board under the frozen rule set (row `v7-recheck`, board
`output/fr_trial/v7_4layer_freerouted.kicad_pcb`) reproduces the historical numbers (clr 125,
unconn 1) and shows they are **not** rule strictness: the 90 `clearance` items read
`clearance 0.2000 mm; actual 0.0000 mm` — real touching copper — plus 35 `hole_clearance` (stale
fill), 48 `via_diameter` (0.45), 22 `track_width` (0.15) and **2 `courtyards_overlap`** — the
pre-S0 placement defect (U2/C4, D1/U1). So the improvement from 125 → 0 in the `clearance` class is
the S0 placement freeze + a fresh fill, not a rule change. Only the via/track **size** clusters are
margin artifacts.

## Open items handed to S2 / RF review (not fixed here, by policy)

1. **RF path**: `RF_OUT` is routed at 0.20 mm on F.Cu in both attempts (4 segments, 11 mm,
   45° diagonals from U2 pad 9 to ANT1 pad 1). JLCPCB 4-layer microstrip at h≈0.21 mm wants
   ≈0.39 mm for 50 Ω, so the RF trace needs its own impedance pass + stitching confirmation
   (plan §2 "RF path confirmation… agent checks → Felix confirms").
2. The 2–3 under-floor plane-tap vias of attempt A/A2 (and the 0.15 mm Freerouting tracks) need a
   real-vs-justified call in S2 — **no coordinates were hand-patched** (the recorded non-convergence:
   86 shorts → 1002 violations).
3. Freerouting's single open GND link (U2 pad 8) would need a stitch via to reach the In1.Cu plane
   if attempt B is ever promoted.

## Reproduce

```bash
cd tracker/hardware
sha256sum jlcpcb-s1-frozen.kicad_dru output/v_c3_flight_4layer_placed.kicad_pcb   # both hashes above
python3 drc_score.py --compare --label v8                                          # the 4 campaign rows
python3 drc_score.py output/v8_krt_routed.kicad_pcb --label v8 --tool krt --cost-usd 0.00
```

Evidence files: `output/v8_krt_routed_drc.json`, `output/v8_krt_v2_routed_drc.json`,
`output/v8_freerouting_routed_drc.json` (`--severity-all`), `output/v8_freerouting.dsn`,
`output/v8_freerouting.ses`, `output/v8_freerouting_run.log`, `s1-rule-freeze.json`.
