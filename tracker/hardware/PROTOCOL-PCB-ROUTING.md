# PROTOCOL-PCB-ROUTING — metric card catalogue, status vocabulary, trap set, resource rubric

**Date:** 2026-09-17 · **Card:** `t_9a6424cd` (S2) · **Supersedes:** PCB-ROUTING-TOOLING-VERDICT.md §4–§5
**Scope:** every PCB routing card on this repo from now on. A card is not "done" until its
`drc_score.py` row and its `drc_traps.py` green run are committed.

---

## 1. Metric catalogue (stable IDs)

The referee is `kicad-cli 9.0.8 pcb drc --format json --severity-all`, always under one
frozen `.kicad_dru` per campaign. Scores are appended to `drc_snapshots/history.jsonl`
by `drc_score.py`.

| ID | name | type | threshold / target | basis |
|----|------|------|--------------------|-------|
| M-SHORTS | `shorts` | count | **0** | Any shorting item is a fab defect (copper bridge). |
| M-CLEAR | `clearance` | count | **0** | Clearance + hole_clearance + copper_edge + hole_to_hole + track_dangling_via. |
| M-UNCON | `unconnected` | count | **0** | A net left unrouted is an open circuit. |
| M-FP | `fp` | count | **≥ 10** | Empty board trivially DRC-clean; vacuous if fewer footprints. |
| M-VIOL | `violations` | count | ≤ expected cosmetics | Silk/mask/courtyard noise moves the headline; not blocking. |
| M-OTHER | `other` | count | ≤ expected cosmetics | `violations − shorts − clearance`. |
| M-VIAS | `vias` | count | — | Routing drag; context only. |
| M-COPPER | `copper_mm` | float | — | Total segment length; context only. |
| M-SHA-B | `sha256_12` | hash | must match exported board | Edit-after-score detection. |
| M-SHA-R | sibling `.kicad_dru` sha | hash | must equal campaign frozen sha | Rule-drift detection. |
| M-SHA-P | placement sha | hash | must equal S0 frozen sha | Placement-drift detection. |
| M-FAB | `fab_ready` | bool | `shorts==0 && clearance==0 && unconnected==0 && fp≥10` | The fab gate. |

Per-campaign rows: the scoreboard derives `dViol` (blocking removed vs prior row),
`usd_per_dViol`, and `REGRESSED` (a later attempt with more blocking errors than an
earlier one — counted as waste).

---

## 2. Per-metric cards

Each metric card states: why | command | threshold + basis | how a third party reproduces.

### M-SHORTS / M-CLEAR / M-UNCON (blocking class)
- **why**: any non-zero value means the board as drawn has a fab defect. JLCPCB will
  either reject or, worse, fab it.
- **command**: `kicad-cli pcb drc --format json --output /tmp/drc.json <board.kicad_pcb>`
- **threshold + basis**: 0 items. JLCPCB minimum capability is 0.10 mm; any violation
  under the frozen rule (0.2 mm) is by construction at least 2× margin under the fab floor.
- **reproduce**: `python3 drc_score.py <board> --label <label> --tool <tool>` — output row
  lists shorts/clearance/unconnected. Cross-check with `jq` on the DRC JSON.

### M-FP (footprint guard)
- **why**: an empty board reports zero violations; without a guard the referee
  confuses "empty" with "clean".
- **command**: `drc_score.py` counts footprints via `\b(footprint\b`.
- **threshold + basis**: ≥ 10 for this flight board (20 expected).
- **reproduce**: `grep -c '^\t(footprint' <board>`.

### M-SHA-B / M-SHA-R / M-SHA-P (integrity hashes)
- **why**: a DRC row is only meaningful if the board that was scored is the board
  that is shipped, and if the rule file applied is the one the campaign agreed on.
- **command**: `sha256sum`, compared against the campaign's frozen values
  (`s1-rule-freeze.json` for S1, `s2-rule-freeze.json` if any for S2).
- **threshold + basis**: byte-identical sha256.
- **reproduce**: hash each sibling `.kicad_dru`, `.kicad_pcb`, and the frozen
  placement; any drift fails the row.

---

## 3. Status vocabulary (closed set)

| status | meaning |
|--------|---------|
| **PASS** | all blocking metrics zero; integrity hashes match; only declared cosmetic residuals. |
| **FAIL** | at least one blocking metric non-zero, or an integrity-hash mismatch. |
| **REGRESSED** | a later attempt has more blocking errors than an earlier attempt with the same label — counted as waste, must be investigated before the next attempt. |
| **COSMETIC** | a violation class declared fab-irrelevant (silk, courtyard, rounding). Suppression must be via the committed `.kicad_dru`, never silent. |
| **REAL — justified** | a violation class that is fab-relevant but explicitly accepted with a reason (e.g. via-in-pad at JLCPCB floor). |
| **REAL — blocking** | a violation class that is fab-relevant and not justified. Fab gate fails. |
| **VACUOUS** | board reports zero violations but has fewer footprints than the guard floor; row is not meaningful. |

---

## 4. Trap set with detectors (`drc_traps.py`)

Each trap simulates a known way to produce a false "ready" verdict and checks that
the detector fires. The suite runs from `tracker/hardware/drc_traps.py`, exit 0 on 8/8.

| ID | scenario | detector | expected outcome |
|----|----------|----------|------------------|
| T1 | **empty board** (all footprints/tracks/zones stripped) | fp count + violation count | violations=0 AND fp<10 flagged vacuous-clean |
| T2 | **cosmetic masking a real clearance** (add a 3.0 mm clearance rule to the frozen `.kicad_dru`) | total violation count before vs after | violations rise (rule picks up new items) |
| T3 | **stale DRC report** (score row refers to a board whose current sha differs) | `sha256_12` in scorecard row vs current board sha | mismatch detected |
| T4 | **board edited between score and export** | same as T3 — both are the same integrity check | mismatch detected |
| T5 | **sha256 mismatch** (any deliberate edit changes the sha) | `sha256(before) != sha256(after)` | detected |
| T6 | **stale zone fill** (refill the board with `fill_for_delivery.py` and re-DRC) | violation counts identical pre/post fill | identical (fill already current) |
| T7 | **placement drift** (placement frozen at S0 sha; routed board must match per-footprint x/y/layer/rot) | per-footprint tuple match | no movement |
| T8 | **rule-file drift** (attempt sibling `.kicad_dru` differs from frozen) | sibling sha vs frozen sha | identical |

All 8 traps PASS on the S1 campaign (commit `3018945`).

---

## 5. Resource rubric

| rule | statement |
|------|-----------|
| R1 | **$0 inference budget for routing stages.** Deterministic tools attack our failure classes for free; past paid attempts produced 17-short boards. Any paid attempt must beat the $0 row on `usd_per_dViol`. |
| R2 | **Stop rule.** 3 attempts with no monotone decrease in `shorts+clearance+unconnected` → change **method**, not model. |
| R3 | **REGRESSED rows are waste.** A regressed row cannot be silently dropped; it is investigated and the reason is committed before the next attempt. |
| R4 | **Human time for verification only.** The operator reviews gerber previews and signs off; never hand-places or edits coordinates a $0 script can produce. |
| R5 | **Free tools own the geometry.** KRT (A* / placement) and Freerouting produce coordinates; the LLM only supplies constraints. Inference is never spent on coordinates. |

---

## 6. Fab-gate predicate (bool)

```
fab_ready := shorts == 0
         AND clearance == 0
         AND unconnected == 0
         AND fp >= 10
         AND sha256(board_scored) == sha256(board_exported)
         AND sibling_dru_sha == campaign_frozen_dru_sha
         AND sibling_pro_sha == campaign_frozen_pro_sha
         AND placement_sha == s0_frozen_placement_sha
```

The predicate is the S0/S1/S2 contract. If any conjunct is false, the row is not
fab-ready and the gate is **not met**.

---

## 7. S2 outcome vs the predicate

Best candidate: attempt **A** (`output/v8_krt_routed.kicad_pcb`, sha256_12 `5d5003c95260`).

- shorts 0 · clearance 0 · unconnected 0 · fp 20 ✓
- M-SHA-B: row sha `5d5003c95260…` == current board sha ✓
- M-SHA-R: sibling `.kicad_dru` sha `5acd7dce…` == frozen ✓
- M-SHA-P: placement hash matches S0 frozen sha `f3cf0143…` (T7) ✓
- trap suite T1–T8: 8/8 PASS ✓
- residuals: 2 via-in-pad (REAL — justified), 4 silk (COSMETIC) ✓ — see `PCB-S2-ADJUDICATION.md`

`**fab-gate: MET** for attempt A under the S1 frozen basis.`

The RF_OUT 50 Ω finding (trace 0.20 mm vs target ~0.39 mm) is **not** in the DRC metric
and **not** part of the fab predicate; it is a separate sign-off item owned by the RF
review before S3. The fab gate above covers manufacturability, not signal integrity.
