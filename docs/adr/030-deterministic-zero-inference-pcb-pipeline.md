# ADR-030 — Deterministic, zero-inference PCB placement and routing

- Status: **Proposed** (2026-10-05). The *direction* is operator-ratified — this ADR was
  commissioned by the operator on 2026-10-04 ("record this as a decision, it is not an ADR
  today") — but the *text* has not been accepted by a human, so it does not claim Accepted.
  Acceptance is a human action and must name the authoriser and the date.
- Date: 2026-10-05
- Decision owner: Felix (operator)
- Author: worker-pcb (Hermes agent). Sources: `tracker/hardware/PCB-S1-ROUTING.md`,
  `tracker/hardware/PCB-S2-ADJUDICATION.md`, `tracker/hardware/PCB-CARD-DOD.md`,
  `tracker/hardware/drc_snapshots/history.jsonl` (every number below re-read from those
  artefacts on 2026-10-05, not quoted from memory).
- Related: ADR-029 (v9 dual-band flight board — its Related list cites this record by number;
  it lives on the branch `pr/029-dual-band-flight-board` and the two land independently),
  ADR-031 (bring-up isolation + staged population), ADR-032 (simulation evidence), ADR-028
  (schematic-first three-variant PCB design), ADR-022 (mandatory test coverage).
- Related artefacts in this repo:
  `tracker/hardware/jlcpcb-s1-frozen.kicad_dru` (the committed rule file),
  `tracker/hardware/drc_score.py` (the referee's scorecard),
  `tracker/hardware/gate25_check.py` · `tracker/hardware/placement_guard.py` (the placement
  gate), `tracker/hardware/v8f_escape_probe.py` · `v8f_escape_fix.py` (exact-geometry via
  legaliser), `tracker/hardware/s2b_legalize_vias.py` (the naive legaliser kept as the
  counter-example), `tracker/hardware/drc_snapshots/history.jsonl` (one row per attempt),
  `tracker/hardware/PCB-CARD-DOD.md` (the card Definition of Done that consumes the rows),
  `tracker/hardware/PLAN-flight-board-routing.md` (S0–S4 gates),
  `tracker/hardware/output/gerbers_v8h_jlcpcb.zip` (the first fab package produced this way).

> Numbering note: 029 and 030 are reserved for the cards that own them (ADR-031 and ADR-032
> already say so in their own Related lists). This record takes 030. `feat/e80-spi-bypass`
> carries an unmerged `docs/adr/029-firmware-output-harmonization.md`; that collision is
> ADR-029's to flag, not this record's.

---

## Context

Placement and routing on this project were done for months by **scripts and sessions emitting
coordinates**, and the failures were electrical, not cosmetic:

- `gen_pcb.py`'s `seg()` wrote raw KiCad segment text with **no collision check**. Measured on
  V1: **86 shorts, 65 crossings, 53 clearance violations**; on F33: 53 shorts, 42 crossings
  (`docs/PLAN-ROUTING-REWRITE.md`). The 2-layer handoff state of the flight board scored in
  `drc_snapshots/history.jsonl` (label `v7-2layer`, `fp 20`, sha `347c56a3cfea`) carries
  **17 × `shorting_items`**, 11 clearance, 40 unconnected, total 69.
- The same **two pad-overlap pairs** (`U2/C4`, `D1/U1`) survived a 55×45 mm outline, an 80×60 mm
  outline, a 2-layer route, a 4-layer route and a fully automated route. Identical results across
  four methods means the router was never the variable — the placement was. That is why
  `placement_guard.py` opens with "nobody owned the coordinates": placement coordinates were
  hand-typed literals spread over 58 coordinate pairs in `gen_pcb.py`, 25 in `grid_placement.py`
  and 12 more placement/patch scripts, with two scripts writing the same board path.

Against that, the v8 line of the flight board reached a **fab-ready Gerber package with $0.00 of
inference** (measured on the v8h board and package below). The difference is not a better model or
a better prompt. It is a different *method*: the geometry is produced and judged by
deterministic tools, and language models write the referee, review it, and read its output.

This decision is recorded because it must be citable, not folkloric. ADR-029 (v9) and ADR-031/032
already cite "ADR-030 (zero-inference PCB pipeline)" by number; this is that record.

## Decision

### D1 — Models never route. Everything geometric is deterministic.

A language model cannot be asked to emit track coordinates. That is arithmetic over thousands of
coupled constraints, and when it is wrong the board **shorts power to ground** (measured above:
17 `shorting_items` on one board, 86 on another). What *can* be automated is the **referee**:
read the board as geometry, place copper with a deterministic solver, and let the fab's own rule
checker decide. Models write and review the referee, and read its output.

| deterministic component | role | where it lives |
|---|---|---|
| `kicad-cli pcb drc --json` (KiCad 9.0.8) | **the referee** — machine-readable violations, per class | `drc_score.py` runs it and parses the JSON |
| KRT — `drandyhaas/KiCadRoutingTools` 0.22.0, A* (45°/octilinear), multi-layer, auto-vias | routing + placement-for-routability | `~/tools/KiCadRoutingTools/py_router/route.py`, run under `/usr/bin/python3.14` (not vendored in this repo) |
| FreeRouting 2.4.1 (DSN→SES round-trip through `pcbnew`) | **independent second-opinion router** | `s1_import_freerouting.py` + `pcbnew.ImportSpecctraSES` |
| `pcbnew` | geometry API — read/write copper, vias, zones | `/usr/bin/python3.14` only (python3.11 segfaults on this host) |
| `jlcpcb-s1-frozen.kicad_dru` (+ its sibling `.kicad_pro`) | the committed rule set — a verdict must not be arguable from a commit message | `tracker/hardware/`, sha `5acd7dce…` |
| `placement_guard.py` · `gate25_check.py` · `drc_score.py` · `v8f_escape_probe.py`/`v8f_escape_fix.py` | the gate, the audit, the exact-geometry fixer, the score | `tracker/hardware/` |
| `pcb_zero_burn.py` + `pcb_rules.json` | optional operator front-end that wraps the same gates (`placement-gate`, `via-audit`, `via-probe`, `via-fix`, `score`, `compare`) | `pcb-routing-zero-burn` skill bundle (`scripts/`). **Not in this repo** — the in-repo equivalents are the scripts above |

Frozen rule values (JLCPCB standard capability with 2× margin): clearance ≥ 0.20 mm, track width
≥ 0.20 mm, via diameter ≥ 0.60 mm, via hole ≥ 0.30 mm, hole-to-hole ≥ 0.25 mm. Every attempt board
carries **byte-identical siblings** of that `.kicad_dru` and `.kicad_pro`; verified by sha256
before scoring (`s1-rule-freeze.json`).

### D2 — One metric, and it must FALL.

```
progress  = shorts + clearance + tracks_crossing + hole_clearance + unconnected    must fall
fab_ready = those == 0   AND   footprints >= 10
```

`drc_score.py` implements the blocking fold as `shorts` (`shorting_items`) plus `clearance`
(`clearance` + `hole_clearance` + `copper_edge_clearance` + `hole_to_hole` +
`track_dangling_via`) plus `unconnected`, and zeroes `fab_ready` when `fp < 10` — an empty board
is trivially DRC-clean and must never score as progress.

> **Known referee gap (recorded, not hidden).** `tracks_crossing` is part of the metric above and
> `kicad-cli` does report it (measured: 15 on the `hub-f33` row), but it is **not** currently in
> `drc_score.py`'s `CLEARANCE_TYPES` fold, so today it lands in `other` and does not block
> `fab_ready`. Until that fold is corrected, `tracks_crossing` must be read per class from the DRC
> JSON itself. This is an instance of the D-cost below: the referee is code and must be
> maintained.

Residual violations are **bucketed and named, never averaged**:

- **electrical** (blocking) — `shorting_items`, `clearance`, `hole_clearance`,
  `copper_edge_clearance`, `tracks_crossing`, `unconnected`.
- **fab-margin** (not blocking, not free) — `via_diameter`, `drill_out_of_range`, `track_width`.
  These are the board being *more conservative than the fab's own floor*; they are tracked and
  adjudicated per class (`PCB-S2-ADJUDICATION.md`), never silently dropped.
- **cosmetic** (fab-irrelevant) — `silk_edge_clearance`, `silk_over_copper`, `silk_overlap`,
  `solder_mask_bridge`, `text_height`, `courtyards_overlap`. JLCPCB ignores them, so they must be
  *listed* rather than hidden, and they must never be reported as progress.

A drop in the headline `violations` total is **not** progress: the live example in
`PCB-CARD-DOD.md` §3 is a row where `unconnected` fell 20 → 1 (real gain) while `clearance` rose
3 → 125 → `REGRESSED`.

### D3 — Pipeline order is normative. The placement gate comes before any copper exists.

1. **`placement-gate` — before any copper exists.** This is a *gate*, not a phase. Gate 2.5 must
   pass on the frozen placement board: `0` pad-box overlap pairs at 0.2 mm, `courtyards_overlap 0`,
   `0` segments (i.e. un-routed by construction), `fp >= 10`. `placement_guard.py --gate25`
   exits 0/1. Nothing routes until it passes — the four-method experiment in Context is why.
2. **route** — KRT A*, e.g.
   `python3.14 py_router/route.py placed.kicad_pcb routed.kicad_pcb "*" --track-width 0.2
   --clearance 0.2 --via-size 0.6 --via-drill 0.3 --power-nets GND +3V3
   --fab-tier standard --same-net-pad-clearance 0.2 --strict-sizes --write-fill`,
   with the sibling frozen `.kicad_dru`/`.kicad_pro` next to the board.
3. **`via-audit`** — histogram `(diameter, drill)`; list every under-size via; flag via-in-pad.
   This is the check that found the only non-cosmetic residual class on the whole campaign.
4. **`via-probe` → `via-fix`** — search legal sites by **exact geometry** (see N3), then write a
   **new file** and refill zones. The artefact under test is never edited.
5. **`score`** — one row per attempt appended to `drc_snapshots/history.jsonl` (committed with the
   board change); **`compare`** across attempts, per lineage label, with `dViol`, `usd/dViol`,
   `vias/dViol` and a `REGRESSED` flag.

### D4 — Evidence: a prose "DRC clean" does not close anything.

A board card is done only when its handoff carries a `drc_score.py` row **for the exact board it
claims** — board path, `sha256_12`, `shorts`, `clearance`, `unconnected`, `fp` — committed in
`history.jsonl` alongside the board change (`tracker/hardware/PCB-CARD-DOD.md`, GATE S4). A
screenshot, a rendered PNG, a 100 KB raw DRC dump, or a row scored on a different file are not
evidence. The policy exists because an early F33 card reported the board ready while the measured
report held **44 `shorting_items`** (`docs/PLAN-F33-SHORTS-FIX.md`,
`docs/PLAN-DRC-CLEANUP-JLCPCB-ORDER.md`).

### D5 — Comparability requires the same rule file and the same placement hash.

Set by `PCB-CARD-DOD.md` §4 and enforced by construction here: every attempt carries the frozen
`.kicad_dru` (sha `5acd7dce…`) and the frozen `.kicad_pro` (sha `a29acec3…`) as byte-identical
siblings, and the placement is pinned by hash (`f3cf0143…`). Re-running the router can change the
board sha **without changing quality** — a new hash is not progress and an old hash is not a
regression.

Two artefact classes inflate a "worse" score and must be ruled out before concluding regression:
**rule-strictness mismatch** (`clearance 0.2000 mm; actual 0.0000 mm` vs
`actual 0.1000 mm`) and **stale zone fill** (N4).

### D6 — Never edit the artefact under test.

Every fixer writes a **new** file (`v8f_unfilled.kicad_pcb`, `v8e → v8f`, `v8b → v8d`). An
experiment that overwrites the artefact it is scoring cannot be scored against it, and the
comparison that produced this ADR's negative results depends on both sides surviving.

### D7 — Bucket the residual before funding the next attempt.

A **placement-fixable failure is not a routing failure**, and a fab-margin residue is not an
electrical one. The gate ordering in D3 exists to force that distinction; the buckets in D2 exist
so that "not fab-ready" names *which* class is open (`PCB-S2-ADJUDICATION.md` classifies every
residual on every attempt as **cosmetic** / **REAL-justified** / **REAL-blocking**).

### D8 — Independence is information, not a tie to break.

When KRT and FreeRouting disagree on the same placement, that disagreement is evidence about the
board. It is not resolved by preference. On the reference campaign KRT routed 22/22 nets with
0 opens, while FreeRouting left **1 open** (a GND SMD pad never stitched to the In1.Cu plane) and
descended to 0.15 mm tracks under its own DSN floor — so KRT carried the fab candidate and
FreeRouting stayed the second opinion.

## Reference campaign (measured, `drc_snapshots/history.jsonl`, all `cost_usd 0.0`)

| attempt | tool | what changed | viol | shorts | clr | unconn | fp | vias at target | fab_ready |
|---|---|---|---|---|---|---|---|---|---|
| `v7-2layer` (before) | manual | pre-4-layer handoff, model-written segments | 69 | **17** | 11 | 40 | 20 | — | 0 |
| `v8b` | krt | S1b KRT re-route from the S0b netlist of record | 10 | 0 | 0 | 0 | 20 | **48 / 51** (3 via-in-pad clamps 0.45/0.20) | 1 |
| `v8c` | krt | `+ --strict-sizes` only | 10 | 0 | 0 | 0 | 20 | **48 / 51** — unchanged | 1 |
| `v8e` | krt | `+ --same-net-pad-clearance 0.2` (via-in-pad forbidden) | 9 | 0 | 0 | 0 | 20 | **47 / 49** (2 U5 escape clamps left) | 1 |
| `v8d` | krt+s2b | naive relocation of those clamps | 11 | 0 | **7** | 0 | 20 | 51 / 51 — **REGRESSED** | 0 |
| **`v8f`** | krt+v8f_fix | exact-geometry escape fix + zone refill + 1 track widened 0.1998→0.200 | **4** (silk only) | 0 | 0 | 0 | 20 | **49 / 49** | **1** |

Residual 4 on `v8f` = `silk_edge_clearance` only. Wall-clock for the whole campaign: minutes per
attempt (KRT re-route of 22 nets: 1.06 s at S1b, 19 s at S1). The router's own runs are logged
next to the boards (`output/*_run.log`) and its in-run DRC-floor adjustment (`#650`:
`rules.min_hole_clearance` 0.25 → 0.2 mm written into the **sibling** `.kicad_pro`) was reverted
to the frozen bytes before scoring, every time.

### What "fab-ready" actually meant on v8h (the first package produced under this pipeline)

- `output/v8h_krt_u2_lora2021.kicad_pcb`, sha256_12 **`d2e7c3d1ae55`**: `fp 20`, 55 vias all
  0.60/0.30, 399 segments, 821.1 mm copper; DRC JSON re-read for this ADR: **5 violations, all
  cosmetic** (3 `silk_edge_clearance`, 2 `silk_over_copper`), `unconnected_items 0`,
  `schematic_parity 0`.
- `output/gerbers_v8h_jlcpcb.zip`: **16 files**, 145 267 bytes, sha256
  `f029db78d046546a3ed7de3b70c75f38a20503fb83c239dbf5c5e03fea320d61` — 11 plotted gerber layers
  (F/In1/In2/B copper, two masks, two pastes, two silks, edge cuts) + `job.gbrjob` + `ipc2581` +
  `PTH.drl` (81 hole coordinates) + `NPTH.drl` (**0 holes** — see Adoption) + `pos_v8h.csv`
  (20-part CPL).
- Every one of the above was produced, scored, fixed and re-scored with **$0.00 of inference**.

## Negative results (the load-bearing part)

These are the observations that make the pipeline's *order* and its *checks* non-arbitrary. Each
one cost a board revision; none of them is recoverable by reading a DRC dump.

**N1 — Post-hoc DRC fixing does not converge.** Measured: **86 shorts → 1002 violations** after a
layer-change "fix" (`PCB-S1-ROUTING.md` §"Open items"). U-shaped detours traded shorts for
unconnected nets. The only class that repairs cleanly *after* generation is `unconnected`
(parse → inject a bridge trace) — which is why real violations are fixed at generation time, with
the router treating pads/vias/tracks as obstacles and checking clearance *before* placing a
segment, and why only `unconnected` repairs are attempted afterwards.

**N2 — `--strict-sizes` does not stop via downgrade.** A router told `--via-size 0.6
--via-drill 0.3` can still deliver 0.45/0.20. `v8c` is that attempt: identical 10 violations, still
3 × `via_diameter` + 3 × `drill_out_of_range`, with the router saying so only in
`JSON_SUMMARY design_rules` ("2 feature(s) on 2 net(s) delivered below the requested size …
smallest via diameter 0.45 mm") and exiting non-zero (recorded in the row's note as "exit 3 flags
it"). The switch that changes behaviour is **`--same-net-pad-clearance > 0`**, which keeps every
via off same-net SMD pads *and* off their solder-paste openings; `-1` explicitly allows
via-in-pad. `v8e` applied it and the via-in-pad clamps disappeared — the `--strict-sizes` flag
alone never would have.

**N3 — A legaliser that enforces only the copper rule produces a strictly worse board.** `v8d`
(`s2b_legalize_vias.py`) relocated the clamps and removed **every** via-size violation — and
introduced **4 `clearance` + 3 `hole_clearance`: blocking open went 0 → 7** on a board that had
0. It checked the 0.20 mm copper rule and ignored the board's own **0.25 mm copper-to-hole** rule. The
fixer must evaluate **every** rule in `pcb_rules.json` **across the layers a via spans**, plus a
safety margin so an exact-equality settlement cannot fail the DRC. `v8f_escape_probe.py` does
exactly that (copper 0.20 + hole 0.25 + edge 0.50, +0.01 mm over each, 0.025 mm grid), and its
result was a two-via change that made the board clean:

```
via (22.700, 36.300) -> legal in place; only the SIZE changed 0.45/0.20 -> 0.60/0.30
via (22.000, 35.700) -> shifted 0.075 mm in x; same size change
zones refilled afterwards (fill_for_delivery.py)
1 track widened 0.1998 -> 0.200 mm   (rounding artifact)
```

**N4 — Zone fill is not refreshed by routing.** Refill after *any* pad/via/track change or the DRC
reports phantom shorts/opens (`Via vs Zone`, `actual 0.0000 mm`). `kicad-cli pcb drc
--refill-zones` does **not exist** in KiCad 9.0.8, so persistent fill is required: `--write-fill`
at route time, `py_tools/fill_for_delivery.py` after any implant. The refill tool also validates
the **`.kicad_pcb` extension** and reads net classes from the **sibling `.kicad_pro`** — a scratch
copy missing the sibling exits 1 and silently leaves the stale fill. The v7 re-score proves the
class: its 90 `clearance` items read `actual 0.0000 mm` — real touching copper plus 35 stale-fill
`hole_clearance` items.

**N5 — A fix that moves copper can open a net, so connectivity is re-proved, not assumed.** `v8g`
applied the same escape fix (2 vias → 0.6/0.3, one shifted 1.399 mm) and introduced **1
unconnected** where the pre-fix board had 0. v8h recovered it by keeping `U4.1` connected and
routing one 0.10 mm In1 `SOLAR_IN` dogleg instead of relocating that via — i.e. the fixer is
allowed to prefer "resize in place" and to add a short dogleg, and its output must be re-scored
for `unconnected`, not only for via size.

**N6 — Comparability requires the same `.kicad_dru` *and* the same placement hash.** Re-running the
router changes the board sha without changing quality. Scored under a different rule file, the
same board looks like a regression (the `.kicad_dru` pickup was itself verified by temporarily
inserting `(constraint clearance (min 3.0mm))`, which took the DRC from 4 violations to 165).

**N7 — "DRC clean" in a commit message is not evidence.** See D4: the F33 report held **44
`shorting_items`** while the card's prose said the board was ready; ~30 hand-read `drc_*.txt`
dumps had accumulated in `tracker/hardware/` because there was no metric. Hence the policy, the
row, and the committed `history.jsonl`.

**N8 — A courtyard warning must be confirmed with polygon geometry before acting.** Bounding-box
overlap is not overlap: `pcbnew`'s `GetBoundingBox()` mixes coordinate frames for footprint
graphics, and a non-rectangular (L-shaped) courtyard around a module's antenna area reported an
overlap that polygon maths refuted. The authoritative read parses the board S-expression's
`F.CrtYd` geometry directly (`courtyard_sexpr_check.py`); `placement_guard.py` therefore reports
courtyard hits as *warnings* and the Gate 2.5 criterion is pad-box overlap, not bbox courtesy.

## Consequences

### Positive

- Reproducible and scoreable: each attempt is one row, so a paid/LLM attempt can be judged against
  the free baseline (`usd/dViol` is literally a column).
- Failures get attributed before they get funded: placement-fixable vs routing-fixable vs
  fab-margin vs cosmetic is decided by a gate ordering, not by opinion.
- The board changes that matter are geometry changes reviewed as diffs on artefacts that both
  sides of a comparison keep.

### Costs

- **The referee is code and must be maintained.** `drc_score.py`, `gate25_check.py`,
  `placement_guard.py`, `jlcpcb-s1-frozen.kicad_dru`, and the `pcb-routing-zero-burn` skill are
  load-bearing; a stale rule file silently changes every verdict (N6).
- The rule file must keep the frozen `.kicad_pro` next to the board, and the router's in-run rule
  adjustment must be reverted before scoring — an operation with a foot-gun if skipped.
- Board size is cheaper than debugging: 45×35 → 50×40 → 55×45 mm turned "45 overlapping parts"
  into "20 parts with 2 mm gaps". Budgeting area is part of the method.
- `pcbnew` only imports under `/usr/bin/python3.14` on this host, which pins the toolchain.
- Cosmetic residue is *tolerated on purpose* (v8h ships 5 cosmetic violations and v8f shipped 4).
  Anyone expecting "0 violations" as the bar will misread the verdict; the bar is the electrical
  bucket reaching 0 at `fp >= 10`, with the other buckets named and listed.

## Rejected alternatives

- **Let a model emit track coordinates** (status quo ante). Measured cost: 17 `shorting_items` on
  one board (69 violations total), 86 shorts on another, and the same two pad-overlap pairs
  surviving four different routing methods.
- **Judge routing by a DRC text dump read by hand.** ~30 of these accumulated; two readers reach
  two conclusions about "better".
- **Judge by the headline `violations` total.** Cosmetics move it; `PCB-CARD-DOD.md` §3 records
  the row where the total fell while the board got less manufacturable.
- **Repair the generated board afterwards.** N1: 86 → 1002. Only `unconnected` repairs cleanly
  after generation.
- **A single router.** FreeRouting's independent opinion is what told us the KRT board was not
  merely "the only thing we had" (and FreeRouting's own 1-open GND link is what told us a DSN
  round-trip can silently treat a plane as fully connected).
- **Trust the router's size report.** N2: `--strict-sizes` did not hold; only
  `--same-net-pad-clearance > 0` changed the outcome, and the delivered sizes must be histographed
  (`via-audit`), not assumed.
- **Trust a fixer that checks one rule.** N3: 0 blocking → 7 blocking.
- **Edit the artefact under test and re-score it.** Destroys the comparison the pipeline is built
  on (D6).

## Adoption

- This pipeline is the **standing, mandatory** method for board work on this project from this
  record onward. Ad-hoc or LLM-coordinate placement/routing is superseded.
- **v8i** (the GNSS + mechanics lap) is the first lap that must ship under it: placement gate
  before copper, one `drc_score.py` row per attempt, frozen rule file + placement hash, no
  prose verdicts. Its card carries the cross-reference to this record.
- **v9** (ADR-029, dual-band flight board) and every later designable board inherit it; ADR-029's
  Related list already cites ADR-030 by number, and ADR-031/032 build on top of the same referee
  (bring-up isolation adds *electrical* evidence, ADR-032 adds *simulation* evidence — neither
  replaces the geometric referee, and D2's metric is unchanged by them).
- The `pcb-routing-zero-burn` skill is the executable form of this ADR and links here for the
  doctrine; the skill may restate the *commands*, never the *decisions*.
- v8h's empty `NPTH.drl` is not a defect of this pipeline: it records that the current board has no
  non-plated holes at all, which is precisely the fact the v8i lap (mounting holes) exists to fix.
