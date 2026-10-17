# CORRECTION — the "wing routing regression" was an INSTRUMENT BUG, not a lost board

**This file corrects `docs/fab/WING-ROUTING-REGRESSION.md`, which asserted a routing regression that does
not exist.** The false claim is kept visible rather than deleted; the measurement is placed beside it.

## What was claimed, and why it was wrong

I claimed a "package audit" commit (`ce5082acf`) had **replaced the routed wing board with an unrouted one**,
citing `(segment 0` / `(via 0` on the committed file and a commit message that called the board *"ROUTED AND
ELECTRICALLY COMPLETE — 28 tracks on 4 solar nets"*.

**Every part of that was wrong, and it was wrong because my measurement was.**

## The authoritative measurement

```
~/venvs/kicad/bin/python -c "import pcbnew; b = pcbnew.LoadBoard('tracker/hardware/wing_board/wing_board_v9.kicad_pcb'); ..."

  footprints: 15
  tracks total: 28
  segments: 20
  vias: 8
  per-layer: {'F.Cu': 10, 'B.Cu': 10}
  zones: 0
```

**The board is exactly what `ADR-065` requires and exactly what the test demands** — 20 segments, a 10 F.Cu /
10 B.Cu split, 8 vias tying each back node to the front. **The commit message was accurate. Nothing was lost.
The wing is routed and orderable.**

## The actual instrument bug

I counted with `grep -c -F '(segment '` — **with a trailing space** — and the same delimiter inside the test.

**KiCad changed its writer format:**

```
0ed25484e  (old writer)   (segment (start 3 12.5) (end 2 12.5)   <- matches '(segment ' WITH trailing space
HEAD       (KiCad 9)      (segment                              <- on its own line, NO trailing space
```

**A reformat is not a deletion, and a format-dependent delimiter cannot tell the two apart.** Measured
correctly, both revisions carry 20 segments and 8 vias.

**So the real defect is the TEST, not the board:** `tests/test_3d_models_wing.py` does
`text.split('(segment ')`, so it silently parses **zero** segments out of a fully routed board and reports
`AssertionError: 0 segments`. **Master CI has been red for a parsing reason, not an engineering one** — and
the "stricter test caught a real regression" story I told was me inventing a narrative to fit a wrong number.

## The compounding failure — the one that matters most

**I wrote a new audit script (`tracker/hardware/audit_board_routing.py`) specifically to be the missing gate,
then reported its output as fact without validating its parser against a board whose state I already knew.**

That is the same failure this whole programme keeps producing: **a claim believed because it was written
down, never measured against the thing it describes.** I had just finished cataloguing eight instances of it
and then produced a ninth — while building the tool intended to prevent it.

**The guard that would have caught it is trivial and I did not apply it:** run the new measurement against a
**known-good object** first. A parser that returns 0 for a board with 834 segments (the hub) is broken, and
one command would have shown it.

## What is actually true

| claim | verdict |
|---|---|
| the package-audit commit deleted the wing routing | **FALSE** — a reformat, not a deletion |
| the wing board is unrouted / not orderable | **FALSE** — 20 segments, 8 vias, 10+10 split |
| the commit message contradicts the file | **FALSE** — the message was accurate |
| `tests/test_3d_models_wing.py` fails on master | **TRUE** |
| the cause is the test's format-dependent parser | **TRUE** |
| the hub board is unrouted | **FALSE** — 834 segments, 286 vias, 3 zones (same instrument bug) |

## The real fix

**The test must parse the board structurally, not by a whitespace-sensitive delimiter.** Options, in order of
robustness:

1. **Use `pcbnew`** — the authoritative reader. `LoadBoard()`, count `PCB_TRACE_T` / `PCB_VIA_T`, and read
   the layer of each. That is what settled this, and `tests/test_3d_models_wing.py` already runs in an
   environment where `pcbnew` is available for the render test.
2. **If it must stay text-based**, match `r'\(segment\b'` (a word boundary, not a trailing space) and split on
   that regex — format-independent for both the compact and multiline writers.

**And the missing gate is still worth having**, built on `pcbnew`: a check that a committed board still
carries the routing the previous revision had. **It must be validated against a known-good board before it is
trusted** — which is the step I skipped.

## Consequence for the queue

**Master CI red is a TEST defect, not a board defect** — so it does not block the wing from being ordered, and
the wing's gerbers do not need regenerating. It **does** still block RALPH item 5 (*"merged with CI green"*),
because a red suite is red. **The fix is small: make the test parse structurally.**
