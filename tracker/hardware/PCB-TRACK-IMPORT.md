# PCB Track Import — root cause and fix (Phase 1 of PCB-AUTOROUTE-EXECUTION-PLAN)

**Date:** 2026-09-29
**Script:** `tracker/hardware/import_tracks_fixed.py`
**Spec:** `tests/test_pcb_track_import.py` (22 tests)
**Board:** `tracker/hardware/hub_board_v1_routed.kicad_pcb`

## Result

| metric | before | after |
|---|---|---|
| DRC violations | **402** | **175** |
| `track_dangling` | **181** | **0** |
| `copper_edge_clearance` | **58** | **0** |
| `tracks_crossing` | 0 | **0** |
| unconnected items | **68** | **26** |
| tracks on board | 651 | **160** (+14 vias) |

Phase 1 gate (`DRC < 230`, `track_dangling` eliminated) — **PASS**.

Both boards re-measured with `kicad-cli pcb drc --format json`; the pre-change
figure is 402 (`405` appeared in an earlier draft and in the spec header — the
what-matters part, 181 `track_dangling`, is exact, and the DRC type list is
identical).

## The two defects in the old import

The stale board was produced by a hand-rolled DSN parser. Two independent
defects, each measured rather than assumed:

### 1. Y was never inverted

A Specctra DSN writes Y **negated** relative to the `.kicad_pcb` coordinate
system. The proof is inside the DSN itself — its `placement` block has component
`U` at `(12000.0, -12000.0)` um while the board has it at `(12.000, 12.000)` mm,
and all 13 placed components agree on `y_board = -y_dsn`.

The old importer used `+y`, which threw the entire route off the board:
**1221 of 1302 track endpoints landed at negative Y**, i.e. outside the
0..40 mm outline. That single sign is what produced all 58
`copper_edge_clearance` violations and both of the old import's error classes.

### 2. Degenerate-segment collapse was missing

The Freerouting DSN exporter emits a jittered ~0.1 um duplicate after *every*
real vertex, so a point-by-point import turns a fine polyline into a run of
zero-length tracks. The DSN of record's 651 raw segments break down as:

| length band | count |
|---|---|
| exactly 0 | 76 |
| < 0.5 um | 334 |
| **0.5 .. 1.0 um** | **0** |
| 1 .. 5 um | 2 (real jogs, 1.6 and 1.7 um) |
| >= 5 um | 239 (real geometry) |

The **empty** 0.5..1.0 um band is the load-bearing fact: it gives a 1 um
collapse threshold ~0.6 um of margin on the tight side. The spec asserts the
band stays empty, so if a future DSN fills it the threshold gets re-derived
instead of silently eating geometry.

The DSN also contains **export spurs**: `LR2021_RST` walks to x = 53.33 mm on a
50 mm board and back. Those vertices are clipped against the router's own
declared boundary (`(boundary (rect pcb -100.0 -40100.0 50100.0 100.0))`).

## The bigger finding: the DSN is not the route

Fixing the two defects above still does **not** produce a good board. The DSN's
segment list is not the router's route — it is a partial, stub-laden echo of it.

Measured by exact segment-endpoint match against the SES from the same
Freerouting run (`v1_freerouting_routed.dsn` / `.ses`):

- the DSN contributes 193 real segments, the SES has 160 authored segments;
- only **60** of the DSN's 193 appear in the SES at all;
- only **60** of the SES's 160 are covered by the DSN.

So a DSN-only import reconstructs 60 of 160 segments — a strict subset — and the
missing copper shows up as **60 `tracks_crossing` violations**. Comparing the
two import paths on the same clean board:

| import path | DRC violations | `tracks_crossing` |
|---|---|---|
| hand-rolled DSN parse (both defects fixed) | 483 | 60 |
| **KiCad `ImportSpecctraSES` on the sibling SES** | **175** | **0** |

Hence the script's design: **the SES is the primary source**, imported with
KiCad's own `pcbnew.ImportSpecctraSES`, which is coordinate-correct by
construction and produces no degenerate geometry (0 zero-length, 0 sub-1 um,
0 outside the outline). The DSN parser is the documented fallback for routing
whose SES was never kept, and `build()` reports which path it used via
`stats["source"]` so a fallback can never masquerade as the good path.

**That report is not enough on its own** (cold-review finding, 2026-09-29): the
fallback board *also* has 0 zero-length, 0 sub-1 um and 0 off-outline tracks,
so the geometry checks pass and the CLI used to print `PASS` and exit 0 for a
board measuring **464** DRC violations (31 `track_dangling`, 36
`tracks_crossing`). The loss is structural, not visible in any single track.
So the fallback is now **refused before it writes**, in `build()` itself rather
than only in the CLI: a DSN-only import raises `LossyFallbackError`, the CLI
prints `FAIL` and exits 1, and no board reaches disk unless
`--allow-dsn-fallback` / `allow_dsn_fallback=True` accepted the loss by name.
An explicit `--ses` that does not exist is a hard error, and an unparseable SES
is a clean refusal rather than a traceback or a quiet slide into the DSN parser.

Two things the fix deliberately does *not* do: it does not delete the DSN
parser (routing whose SES was never kept still needs it), and it does not
pretend the fallback can be made safe — the subset relation is inherent to the
format difference, so the only honest options are "refuse" and "opt in".

## Reproduce

```bash
HW=tracker/hardware
/usr/bin/python3.14 $HW/import_tracks_fixed.py \
    --dsn $HW/output/v1_freerouting_routed.dsn \
    --pcb $HW/hub_board_v1_clean.kicad_pcb \
    --output $HW/hub_board_v1_routed.kicad_pcb
kicad-cli pcb drc --format json --output /tmp/drc.json $HW/hub_board_v1_routed.kicad_pcb
/usr/bin/python3 -m pytest tests/test_pcb_track_import.py -v
```

Exit code is non-zero if any imported track is zero-length, sub-1um, or outside
the outline — checked by re-loading the **written file**, never by trusting the
importer's own claim. It is also non-zero if the import would have taken the
lossy DSN fallback without being asked to.

## The other importers in this directory

`ses_import.py` (hand-rolled SES parser, written when
`ImportSpecctraSES` was believed to fail headless) and
`s1_import_freerouting.py` (S1's SES importer, which also verifies the frozen
placement did not move) both touch the same problem from different campaigns.
They are siblings by history, not by design: this file is the Phase 1 fix and
the only one that carries the DSN fallback guard. Consolidating them behind one
entry point is Phase 2+ work, deliberately not smuggled into this fix.

## Artefact provenance note

The plan named `/tmp/routed_output.dsn`, which no longer exists. These in-repo
twins are used instead, and they are the same generation of routing: the
committed board's 651 traces match `output/v1_freerouting_output.dsn`'s 651 raw
segments **exactly** (every one of the first 200 routed tracks is byte-equal to
a raw DSN segment). That DSN has no surviving SES, which is why the deliverable
board is built from the `v1_freerouting_routed` pair — the newest routing in the
repo that has both halves.

## What is left for Phase 2

The 175 remaining violations are overwhelmingly **pre-existing design issues**,
not routing:

| violation | count | nature |
|---|---|---|
| `solder_mask_bridge` | 33 | pad spacing, not routing |
| `lib_footprint_mismatch` | 28 | footprint library version skew |
| `text_height` / `text_thickness` | 25 / 18 | silkscreen text below fab minimums |
| `silk_over_copper` / `silk_overlap` | 17 / 14 | silkscreen legibility |
| `shorting_items` | 15 | **unchanged from baseline — needs investigation** |
| `via_dangling` | 9 | 9 of the 14 imported vias dangle |
| `clearance` | 8 | unchanged from baseline |
| `silk_edge_clearance`, `lib_footprint_issues`, `hole_to_hole` | 5 / 2 / 1 | design |

`shorting_items` at 15 was present in the baseline and is untouched by the
import — it is a schematic/placement question, not an import question.
`via_dangling` (9) is new relative to the baseline only because the baseline had
no vias at all; those vias come from the SES and their dangling ends are a
routing-completeness issue for Phase 2.
