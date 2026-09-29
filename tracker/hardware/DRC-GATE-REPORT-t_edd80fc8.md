# PCB Inspector Gate — DRC verification after Phase 2 and Phase 4

**Task:** t_edd80fc8 (worker-inspector)
**Date:** 2026-09-29
**Toolchain:** kicad-cli 9.0.8 (independent re-run — no implementer DRC JSON trusted)
**Repo inspected:** ~/repos/balloon-fresh @ fix/tollgate-payack-seq-whitespace (worktree ~/worktrees/t_24d9e30c)
**Plan under test:** docs/coordination/PCB-AUTOROUTE-EXECUTION-PLAN.md

---

## VERDICT: BLOCKED — BOTH GATES FAIL

| Gate | Requirement | Measured | Result |
|------|-------------|----------|--------|
| Phase 2 | <50 violations | **405** | FAIL |
| Phase 2 | 0 shorting_items | **15** | FAIL |
| Phase 2 | 0 clearance violations | **8 clearance (+58 copper_edge_clearance = 67 clearance-class)** | FAIL |
| Phase 4 | gerbers exist for all layers of the Phase 4 board | **no Phase 4 board, no Phase 4 gerber set** | FAIL |
| Phase 4 | final DRC <50 | not evaluable (no Phase 4 artifact) | FAIL |
| Phase 4 | JLCPCB order-ready | no CPL, no BOM, no order zip from this pipeline | FAIL |

**Downstream tasks must not proceed.** Phases 3, 4 and 6 are already `blocked`; Phase 5 is
`ready` and is NOT gated on Phase 4 by any task_link (see §4).

---

## 1. Phase 2 gate — DRC reduction to <50 / 0 shorts / 0 clearance

Board that Phase 2 was required to produce: `tracker/hardware/hub_board_v1_final.kicad_pcb`.
**That file does not exist anywhere** — not in the worktree, not on `github/autonomous/mesh-baseline`,
not on `feat/tracker-tx-tempcomp`. The nearest candidate artifacts were measured instead.

Fresh `kicad-cli pcb drc --format json` runs (repeat-run determinism confirmed: 2 identical runs):

| Board | sha256 (12) | fp | violations | shorting_items | clearance-class | unconnected |
|-------|-------------|----|-----------|----------------|-----------------|-------------|
| hub_board_v1_routed.kicad_pcb | bb30f5430071 | 30 | 405 | 15 | 67 | 68 |
| hub_board_v1_routed_clean.kicad_pcb | 81390eeee4ee | 30 | 428 | 34 | 124 | 28 |
| hub_board_v1.kicad_pcb (baseline) | 0924ccc6290c | 30 | 436 | 56 | 46 | 44 |

`clearance-class` is the drc_score.py definition: clearance + hole_clearance +
copper_edge_clearance + hole_to_hole + track_dangling_via.

Violation breakdown for `hub_board_v1_routed.kicad_pcb` (405):
track_dangling 181, copper_edge_clearance 58, solder_mask_bridge 33,
lib_footprint_mismatch 28, text_height 25, text_thickness 18, silk_over_copper 17,
shorting_items 15, silk_overlap 14, clearance 8, silk_edge_clearance 5,
lib_footprint_issues 2, hole_to_hole 1.

**Phase 2 did not merely miss the target — the file it was gated on was never produced.**
The 181 `track_dangling` violations are exactly the Phase 1 defect
(`import_tracks_fixed.py` zero-length-track filter) that Phase 1 was supposed to fix.
`import_tracks_fixed.py` does not exist either, so Phase 1 also produced no artifact.

### The 405-violation result is the untouched starting state
The plan's §1.3 documented baseline is "Total violations: 405, Unconnected: 68,
track_dangling: 181". The board on disk reproduces that baseline exactly. Phase 2
removed nothing.

## 2. Phase 4 gate — gerbers + JLCPCB readiness

Phase 4 declares `PCB_FINAL=$HW_DIR/hub_board_v1_final.kicad_pcb` and
`GERBER_DIR=$HW_DIR/gerbers_v1_final`. In the worktree:

- `hub_board_v1_final.kicad_pcb` — **absent**
- `gerbers_v1_final/` — **absent**
- `import_tracks_fixed.py` — **absent**

Gerber directories that do exist (`gerbers_v1`, `output/gerbers_v2`,
`output/gerbers_v2_2layer`, `output/gerbers_v_c3`, `output/gerbers_v_c3_final`)
all predate this pipeline (last touched 2026-07-30 → 2026-09-18) and belong to the
V1 / V2-ADC / C3 lanes, not to the autoroute pipeline. `gerbers_v1/` carries
`hub_board_v1-*` names plus `hub_board_v1_jlcpcb.zip` (23 files, all timestamps
2026-07-30 01:54) — exported from the pre-Phase-1 board.

**JLCPCB order-readiness: FAIL.** None of the gerber sets in the tree contains a BOM
or a CPL/position file pair for a JLCPCB assembly order; `gerbers_v1/pos_v1.csv` exists
but with no accompanying BOM.

## 3. FALSE-PASS HAZARD — a blank board reports a clean DRC

`tracker/hardware/output/v2_adc_JLCPCB_READY.kicad_pcb` (sha256 0bccf59f79d8)
returns **0 violations / 0 shorting_items / 0 clearance / 0 unconnected** from a
fresh `kicad-cli pcb drc` run, and ships a cached sidecar
`v2_adc_JLCPCB_READY_drc.json` reading:

```
"source": "v2_adc_JLCPCB_READY.kicad_pcb", "unconnected_items": [], "violations": []
```

It is **not a board**. Direct inspection: 0 footprints, 0 segments, 0 vias, 0 zones,
1 declared net, and the only two graphical items are an `Edge.Cuts` rectangle
(50x40) and one silkscreen `gr_text` reading
"Balloon V2-ADC — JLCPCB 2-layer 0.6mm". File size 2377 bytes.

A `<50 violations / 0 shorts` gate applied to this file **passes trivially and means
nothing**. This is precisely the failure mode the board's own S4 policy card
(t_51d1d219) was written to prevent, and `drc_score.py` already implements the guard
(`fp < 10 → fab_ready 0`, warning `EMPTY/NEAR-EMPTY BOARD`). Any future board gate on
this board MUST apply the footprint guard, not the raw violation count alone.

## 4. Task-graph state (why the gate cannot simply "unblock" the chain)

- `t_877751ec` (Phase 1) — status `ready`, 3 crashed runs (2026-08-05), no artifact on disk.
- `t_e6dfe4e2` (Phase 2) — status `blocked`; was marked `completed` 2026-08-05 17:46 with
  `result_len 0`, `summary null` (no gate evidence).
- `t_cca6e387` (Phase 3) — `blocked`.
- `t_745016d5` (Phase 4) — status `blocked`; also `completed` 2026-08-05 17:46 with
  `result_len 0`, `summary null`.
- `t_807f52d4` (Phase 5, firmware GPIO) — status `ready`, **not linked** to Phase 4 in
  `task_links`. The chain is 1→2→3→4→6 only; Phase 5 sits outside it.
- `t_e72667d2` (Phase 6, commit/push) — `blocked`.

Every PCB card carries a `gate-tick: BLOCKED (completion-pending)` comment dated
2026-09-28 23:39 listing missing gates: tests_green, pushed_or_consolidated,
ci_evidence, cold_cross_family_review, review_artifact, consolidated, secrets_clean,
no_live_drift.

## 5. Pipeline input is gone — this pipeline cannot be resumed as written

Phase 1's input `DSN_ROUTED=/tmp/routed_output.dsn` **no longer exists** (tmp was
cleared after 2026-08-05). Phases 1–4 are not re-runnable from this state without
regenerating the Freerouting DSN from scratch.

Additionally, the manager already recorded on both Phase 2 and Phase 4 at
2026-08-05 17:23 — 23 minutes before their no-evidence "completion" —:

> BLOCKED: superseded by fresh C3 PCB build from schematic

The autoroute pipeline is superseded. The replacement lane (C3 build from schematic)
is itself not fab-ready: the best measured C3 candidate,
`output/v_c3_flight_4layer_routed.kicad_pcb` (sha256 874cf608c65a, fp 20), scores
17 violations / 0 shorts / 3 clearance-class / **20 unconnected** — fab_ready 0.

## 6. Reproduction

```bash
cd ~/worktrees/t_24d9e30c/tracker/hardware
kicad-cli pcb drc --format json --output /tmp/g.json hub_board_v1_routed.kicad_pcb
python3 -c "import json,collections;d=json.load(open('/tmp/g.json'));\
print(len(d['violations']),len(d['unconnected_items']),\
collections.Counter(v['type'] for v in d['violations']))"
# -> 405 68 Counter({'track_dangling': 181, ..., 'shorting_items': 15, 'clearance': 8})

grep -c '(footprint' output/v2_adc_JLCPCB_READY.kicad_pcb   # -> 0  (blank board)
sha256sum hub_board_v1_routed.kicad_pcb                     # -> bb30f54300714fea...
```

## 7. Scoresheet (drc_score.py rows, label t_edd80fc8-gate)

| board | sha256 (12) | fp | viol | short | clr | unconn | fab_ready |
|-------|-------------|----|------|-------|-----|--------|-----------|
| hub_board_v1_routed.kicad_pcb | bb30f5430071 | 30 | 405 | 15 | 67 | 68 | 0 |
| hub_board_v1_routed_clean.kicad_pcb | 81390eeee4ee | 30 | 428 | 34 | 124 | 28 | 0 |
| output/v2_adc_JLCPCB_READY.kicad_pcb | 0bccf59f79d8 | 0 | 0 | 0 | 0 | 0 | 0 (EMPTY BOARD — not meaningful) |
| output/v_c3_flight_4layer_routed.kicad_pcb | 874cf608c65a | 20 | 17 | 0 | 3 | 20 | 0 |
| output/v2_adc_v3_clean.kicad_pcb | f96d4a68c240 | 17 | 10 | 5 | 0 | 26 | 0 |
| output/v_c3_flight_v7_routed.kicad_pcb | 347c56a3cfea | 20 | 68 | 17 | 10 | 40 | 0 |

## 8. Recommendations

1. **Do not proceed to Phase 3/4/6 and do not order any board from this pipeline.**
2. **Do not re-run the autoroute pipeline as written** — `/tmp/routed_output.dsn` is gone
   and the plan is superseded by the C3-from-schematic lane.
3. **Operator decision needed:** archive/close the superseded chain
   (t_877751ec, t_e6dfe4e2, t_cca6e387, t_745016d5, t_e72667d2) rather than retrying it.
4. **Wire Phase 5** (`t_807f52d4`) into the graph or archive it — it is currently `ready`
   with no parent, so it can fire on a board that does not exist.
5. **Any future board gate must carry a footprint guard.** A blank `.kicad_pcb` scores
   0 violations; `drc_score.py`'s `fp < 10` rule is the only thing standing between a
   clean-looking DRC report and a fabrication order for an empty board.
