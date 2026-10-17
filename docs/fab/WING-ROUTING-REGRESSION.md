# ~~Wing v9: the ADR-065 routed board was REPLACED by an unrouted one, and the commit claimed the opposite~~

> ## 🔴 THIS FINDING IS WRONG — CORRECTED IN PLACE 2026-10-17
>
> **The board is intact. My measurement was broken.** `pcbnew.LoadBoard()` on the committed board returns
> **15 footprints, 28 tracks, 20 segments, 8 vias, per-layer `{F.Cu: 10, B.Cu: 10}`** — exactly what
> ADR-065 requires and exactly what the test demands. **Nothing was deleted. The commit message was
> accurate.**
>
> **What actually happened:** I counted with `grep -c -F '(segment '` — **with a trailing space**. KiCad
> changed its writer format: `0ed25484e` wrote `(segment (start 3 12.5)` (matches); HEAD writes `(segment`
> on its own line (**no trailing space → no match**). **A reformat is not a deletion, and a
> format-dependent delimiter cannot tell the two apart.**
>
> **The real defect is the TEST**, which uses the same delimiter (`text.split('(segment ')`) and therefore
> parses **zero** segments out of a fully routed board. **Master CI is red for a parsing reason, not an
> engineering one.**
>
> **Full correction, including the compounding failure** (I built a new audit tool *because* I wanted this
> gate, then trusted its output without validating the parser against a known-good board):
> **`docs/fab/WING-ROUTING-REGRESSION-CORRECTION.md`**
>
> **The false claims below are kept visible on purpose — a correction that hides the original is worse than
> no correction.** Read them as the record of a wrong measurement, not as findings.

## ~~The measurement~~ (WRONG — see correction above)

| revision | segments | vias | footprints | model blocks | sha256 |
|---|---|---|---|---|---|
| `0ed25484e` — *"fix(wing): wire the B.Cu solar back string (ADR-065)"* | **20** | **8** | 15 | 12 | `a38b45756bb36cdd…` |
| **current HEAD** — after `ce5082acf` / `2cf6aa8af` *"WING v9 PACKAGE AUDIT"* | **0** | **0** | 15 | 12 | — |

**File:** `tracker/hardware/wing_board/wing_board_v9.kicad_pcb` (35423 bytes now; 27657 at the wired revision).

```
current:  (segment 0   (via 0   (arc 0   (zone 0   (gr_line 0   (gr_poly 0   (net 51
```

## The commit message asserts the opposite of the file

`ce5082acf` says, verbatim:

> *"It is **ROUTED AND ELECTRICALLY COMPLETE** — 0 unconnected items, **28 tracks on 4 solar nets**, 184.1 x 25.1 mm, 15 footprints. No audit-4-class blocker."*

**The file it committed carries zero segments and zero vias.** The diff shows the segments being **deleted** (`-  (segment (start 3 12.5) (end 2 12.5)` …), inside a change of `1955 insertions(+), 770 deletions(-)` to that one file.

**This is the failure class of this whole programme in its starkest form: a self-report contradicted by the artefact it describes.** It is the same shape as `fab_grade.sh` printing `NOT ORDERABLE` and exiting 0, and as the `U1.41` claim living on in five documents — **a claim believed because it was written down, never measured against the thing it describes.**

## Why master CI is red

`tests/test_3d_models_wing.py::test_board_still_carries_the_wings_12_references_and_the_cells` asserts:

```python
segs = [...]
assert len(segs) == 20, f'{len(segs)} segments'
assert segs.count('F.Cu') == 10
assert segs.count('B.Cu') == 10
assert text.count('(via ') == 8, 'vias tying each back node to the front'
```

It fails with `AssertionError: 0 segments`, `assert 0 == 20`.

**This is NOT a stale test.** The test is doing exactly its job — and its own comment records why it was made strict:

> *"20 segments = 10 F.Cu + 10 B.Cu: the back series string is wired (ADR-065 addendum). Assert the PER-LAYER split, not just a total — **the total-only form of this check passed for a year while the back string was electrically isolated** on a board whose cells sat on B.Cu."*

**Commit `f93adabe0` tightened it to the per-layer split; the regression came after; the red was left standing.** The stricter test caught a real loss.

## What the regression costs

The wing is the **second board in the order**. `ADR-065` is the **double-sided solar cell** decision: cells on both faces, with the **back series string wired on B.Cu** and **8 vias tying each back node to the front**. With the segments gone:

- **the back series string is electrically isolated again** — the exact defect `f93adabe0` exists to prevent
- the board is **not routed**, so it is **not orderable** in this state
- and the commit that did it **reported the opposite**, so nothing downstream flagged it

## Recovery

**The routed revision is fully recoverable** — `0ed25484e:tracker/hardware/wing_board/wing_board_v9.kicad_pcb` gives back **20 segments, 8 vias, 15 footprints, 12 model blocks**, sha256 `a38b45756bb36cdd…`.

**But a blind `git checkout` of that path would discard whatever the audit legitimately changed.** The audit's commit is `1955 insertions / 770 deletions`; both revisions have **12 model blocks**, so the model coverage is not the difference. **The fix must reconcile the two, not pick one:**

1. **Diff the two revisions** and enumerate what the audit actually intended to change.
2. **Re-apply the routing** (20 segments, 8 vias) onto the current board, or re-apply the audit's intended changes onto the routed revision — whichever preserves both intents.
3. **Assert the result**: 20 segments, 10 F.Cu + 10 B.Cu, 8 vias, 15 footprints, 12 model blocks.
4. **Re-run `tests/test_3d_models_wing.py`** — it must pass, and it is the acceptance test.
5. **Re-export the wing gerbers** if the board changes, since the audit also re-exported them "with hash" — a gerber set generated from an unrouted board is itself wrong.

## The process fix this argues for

**A commit message claiming a board property must be checked against the artefact.** The repo already has the pattern: `fab_grade.sh` now drives its exit code from its verdict, and the pad audit exists because count-based gates structurally cannot see pad numbers. **The missing check is the simplest one: does the committed board still carry the routing the previous revision had?** A regression test on the *board's own routing primitives* — segments, vias, per-layer split — would have caught this at commit time, and `test_3d_models_wing.py` is already 90% of it.

## Status

Filed as a kanban card at urgency **now**. Master CI is red until this is fixed, so **item 5 of the RALPH queue ("merged with CI green") cannot complete before it** — and the wing cannot be ordered.
