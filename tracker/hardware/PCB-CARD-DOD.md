# POLICY — Definition of Done for PCB / board cards (no prose "DRC clean")

**Status:** ACTIVE (GATE S4 of `PLAN-flight-board-routing.md`, recorded 2026-09-16)
**Applies to:** every card on the `balloon` board whose deliverable includes a
`.kicad_pcb`, a gerber set, a routed/placed/reworked board, or any routing attempt.
**Source of the rule:** this file (board convention) + the
`kicad-cli-headless-pcb` skill (`references/pcb-card-definition-of-done.md`).
**Standing procedure:** `tracker/hardware/PLAN-flight-board-routing.md` (S0–S4).

---

## 1. The rule

A PCB card is **done only when its handoff carries a `drc_score.py` row for the exact
board it claims to have scored** — board path, `sha256_12`, `shorts`, `clearance`,
`unconnected`, `fp`.

Prose is not evidence. All of these do **not** close a card:

- "DRC clean" / "DRC passes" / "no violations" in the summary
- a screenshot or a rendered PNG of the board
- a raw `kicad-cli ... drc` dump with no row and no board hash
- a row scored on a *different* board file than the one claimed (or scored before the
  last edit — see §5)

### Why (incident of 2026-09-16)

A worker reported completion on a structurally untouched board — the 26 unconnected
items were exactly those of the previous attempt, and nothing had moved. In the same
period, routing attempts were being judged by hand-reading 100 KB DRC text dumps
(`tracker/hardware/drc_*.txt`, ~30 of them), which is not a metric: two people reading
the same dump reach different conclusions about "better".

The scorecard (`drc_score.py`) exists to make that judgement one comparable row per
attempt. The policy exists because a row is only emitted if someone runs the tool.

---

## 2. Producing the row (the only accepted evidence)

```bash
cd tracker/hardware
python3 drc_score.py <board.kicad_pcb> --label <lineage> \
    --tool <manual|freerouting|krt|skidl-script|...> \
    --cost-usd <usd attributed to this attempt> \
    --note "<what changed since the previous attempt>"
python3 drc_score.py --compare          # the scoreboard (human review)
python3 drc_score.py <board> --label X --json   # machine-readable row
```

- Rows append to `tracker/hardware/drc_snapshots/history.jsonl` — **commit that file**
  with the board change, so the row travels with the revision it scores.
- Paste the row (or its `--json` output) into the card result. A card that names a
  board file in prose but has no row is not done.
- `--label` is the *lineage* (`v7-4layer`, `hub-f33`, …). History and the derived
  `dViol` / `usd/dViol` / `REGRESSED` flags are per label, so a new label silently
  restarts the comparison — reuse the label of the lineage you are iterating on.

---

## 3. Progress rule — the headline number is not evidence

**Progress counts only if `shorts + clearance + unconnected` FALLS** versus the
previous row of the same label.

- `violations` (the total) may fall while the board gets *less* manufacturable:
  `silk_over_copper`, `solder_mask_bridge`, `silk_overlap`, `courtyards_overlap` are
  cosmetic and move the total. Never report a total-count drop as progress.
- A row whose blocking total is **higher** than the previous same-label row is
  `REGRESSED` in `--compare`, counts as **waste**, and must be explained before the
  next attempt is funded.
- Live example from `history.jsonl` (the reason the rule is written down):

  ```
  ts                 label  tool          fp  viol  short  clr  unconn  vias  copper_mm  fab  dViol
  09-16T12:13        v7-4la manual         20    17      0    3     20    48      167.2    0      -
  09-16T12:18        v7-4la freerouting    20   134      0  125      1    66      577.8    0   -103  REGRESSED
  ```

  `unconnected` fell 20 → 1 (real gain: nets actually routed, copper 167 → 578 mm) but
  `clearance` rose 3 → 125 → **REGRESSED**. Judge the class, not the headline, and see
  §4 before calling that clearance a routing failure.

---

## 4. Comparability (otherwise you are scoring the harness, not the router)

A row is comparable only when it was measured under:

1. the **same design-rule file** (`.kicad_dru`). Tightening rules mid-series inflates
   `clearance` and is not a regression; and
2. the **same frozen placement/revision** (`sha256_12` pins this).

Two artifact classes inflate a "worse" score and must be ruled out before concluding
regression: **rule-strictness mismatch** (`clearance 0.2000 mm; actual 0.1000 mm`) and
**stale zone fill after SES import** (`hole_clearance` with `actual 0.0000 mm`,
via-vs-zone). Refill zones, re-run, and only then score.

---

## 5. Fab-ready gate

`fab_ready = 1` requires **`shorts = 0` AND `clearance = 0` AND `unconnected = 0`
AND `fp >= 10`**. The `fp` clause exists because an empty or near-empty board is
trivially DRC-clean; `drc_score.py` zeroes `fab_ready` and sets a `warning` for
`fp < 10`. A claimed fab-ready board with `fp < 10` is a fabricated claim, not a pass.

Ordering gates (from the standing procedure) still apply on top: placement Gate 2.5
(0 pad-overlap pairs) before any routing row, and the operator's sign-off (S3) before
the JLCPCB order.

---

## 6. Card body template — paste this into every PCB card

```
## Definition of done (PCB policy — tracker/hardware/PCB-CARD-DOD.md)
- Evidence: ONE drc_score.py row for the exact scored board, incl. board path,
  sha256_12, shorts, clearance, unconnected, fp. Row committed in
  tracker/hardware/drc_snapshots/history.jsonl with the board change.
- Progress counts ONLY if shorts+clearance+unconnected FALLS vs the previous row of
  the same label. Total `violations` is not evidence (cosmetics move it).
- Fab-ready = shorts 0 AND clearance 0 AND unconnected 0 AND fp >= 10.
- Comparability: same .kicad_dru + frozen placement (sha256_12), else the comparison
  is invalid.
- A prose 'DRC clean' claim does NOT close this card. No row = not done.
- Standing procedure: tracker/hardware/PLAN-flight-board-routing.md
```

The card creator (manager) owns pasting this block; the card is created with it or not
created at all. Reviewers and the gate reject a completion that lacks the row.

---

## 7. Related

- `tracker/hardware/drc_score.py` — the scorecard (metric definitions in its docstring).
- `tracker/hardware/PLAN-flight-board-routing.md` — S0–S4 gates, owners, resource rules.
- `tracker/hardware/PCB-ROUTING-TOOLING-VERDICT.md` — which routers/tools are admissible.
- skill `kicad-cli-headless-pcb` → `references/pcb-card-definition-of-done.md` and
  `references/free-router-scoring-and-artifacts.md`.
