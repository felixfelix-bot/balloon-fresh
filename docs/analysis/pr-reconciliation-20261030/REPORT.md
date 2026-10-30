# Protected hub PR reconciliation — 2026-10-30

**No missing changes to salvage from #372–374. Do not merge their old board snapshots.** All three are squash-history duplicates, not new routing work. No board, placement, project rule, existing branch or PR state was changed by this reconciliation.

## Frozen baseline and disposition

Remote master was fetched and rechecked at `c7074ddbd574f0b677161f1609abfbedef61faf0`. Canonical board: `tracker/hardware/hub_board_v10_lora1280_7of9.kicad_pcb`, SHA256 `732bfe889020b3c957fb778f1c30f2a84a3e96171cec37c1fa51dae58a9c6561`.

| PR | Frozen head | Measured landing evidence | Recommendation |
|---|---|---|---|
| [#372](https://github.com/felixfelix-bot/balloon-fresh/pull/372) | `5ab3723b74a335e2f8a62256bb9368a38380505c` | Entire tree equals landed `bd96d565` (#370); single unique-history commit is patch-equivalent | Superseded; close only with owner authorization, retain branch/archive |
| [#373](https://github.com/felixfelix-bot/balloon-fresh/pull/373) | `c9cb9bace850d7bfb838a7f0804441cdc44acedb` | Entire tree equals #372 and landed `bd96d565`; both unique-history commits patch-equivalent | Superseded duplicate of #368 + #370; do not merge |
| [#374](https://github.com/felixfelix-bot/balloon-fresh/pull/374) | `bf99ae60c4df8f6dad60e63a235d89212065e566` | Entire tree equals landed `123d6204` (#368); unique-history commit patch-equivalent | Superseded; do not merge |
| [#377](https://github.com/felixfelix-bot/balloon-fresh/pull/377) | `df793aaf77f2cf49bf6cfb179ab28c946eedb827` | 14 new audit-only files, current-master base, clean diff check, rerun reproduces findings | Technically ready as an audit record, not fab approval; formal independent review/merge authorization still absent |

None of #372–374 heads is an ancestor of master: the squash commits explain that, not missing work. #374 is an ancestor of #373; #372 and #373 have identical whole trees despite different history. `git cherry` marks every unique-history commit of these three `-`. Whole-tree equality to the landed commits is stronger than patch-ID evidence. `evidence.json` gives every PR-touched path and both blob IDs: **every non-board path is still byte-identical to current master**.

Specifically already landed: #372's `route_board_nets.py` and `route_lora1280_independent.py` changes and two routed F33 nets via #370; #374's workstation playbook, make targets, DRC summary, runbook, tests, swap tool/seed board and images via #368. #373 combines those same changes. No extraction branch is needed; this `pr/` branch carries evidence only. Old commit prose claiming most missing records are plane joins is superseded by #377, not a basis for new routing.

## Geometry protection, not snapshot replacement

Master has **843 track segments + 41 vias**. Its canonical track/via geometry set is identical to operator commit `7129c584` (zero objects unique to either side). Whole board bytes differ from that operator commit in zone-fill serialization; do not claim whole-file identity. The current board hash above is the protected baseline for subsequent work.

Relative to master, #372/#373 have 62 stale-only track/via geometry records and lack 54 master records; #374 has 62 stale-only and lacks 112 master records. Counts compare net, layer, endpoints, width and via geometry, independent of UUID/order. These are differences, **not missing work to restore**: exact historical-tree equality proves their origin before the operator routing landed in #375 (`6a314f59`). Replacing the board with any old snapshot would overwrite protected operator work. No trial merge, router, copper edit or snapshot application was performed.

## Actual copper-layer usage

Measured with KiCad 9.0.9, not inferred from stackup or screenshots. Length is summed track centerline length; zones/vias are excluded from that denominator.

| Layer | Track segments | Track length mm | Filled zones |
|---|---:|---:|---|
| F.Cu | 452 | 944.542429 | GND |
| In1.Cu | 0 | 0 | GND |
| In2.Cu | 5 | 15.486501 | none |
| B.Cu | 386 | 486.220019 | +3V3, GND, /VSCAP |

**Not outer-layers-only:** In2 carries two `/F33_BUSY` segments and three `/GNSS_PPS` segments. In1 is used for a GND pour even though it has zero tracks. Both inner-layer uses are already present in the operator snapshot; no layer changes made here. Full per-net/per-layer counts and zone UUIDs are in `evidence.json`. This is usage inventory, not impedance/stackup qualification or proof that a 2-layer conversion is safe.

## #377 review and real rerun

Read all three audit scripts and report; reran `run_audit.py`, `classify.py`, `verify.py` in separate detached worktree `~/worktrees/reconcile-audit377-check-20261030` at the exact PR head. All three wrappers exited 0; the actual DRC subprocess exited **5**, correctly reporting violations. Source unchanged; refilled board hash equals the protected board. Reproduced **40 violations, 86 unconnected records, 59 real / 27 unresolved, nine native and polygon signal paths, nine negative controls**. Graph, summary, radio paths and verification outputs are byte-identical to committed evidence. DRC chooses different representative endpoints/order on some equal-distance ratsnest edges, so raw DRC and ledger bytes differ; row IDs are stable within the captured run, not global cross-run identities. Keep the frozen ledger and compare connected components on rerun.

Live GitHub state: MERGEABLE/CLEAN, all three checks SUCCESS, **no reviews**. Check URLs, manifests, subprocess statuses and rerun summary are in `review-verification.json`; full rerun output in `audit-rerun.log`. `git diff --check` passed. No formal GitHub review was posted. Findings support merging #377 as an evidence-only audit after the required review/authorization, never ordering this board. Remaining audit issues (27 island attribution gaps, library resolution, edge/thermal/silk violations) remain explicit.

Reproduction: `/usr/bin/python3 docs/analysis/pr-reconciliation-20261030/measure.py` from this worktree after fetching the four PR refs as `origin/reconcile-N`. It only extracts snapshots to `.reconcile-snapshots/` and loads them read-only. Hardware files remain unchanged. Reconciliation scope ends here; no broad routing or fab-release work was attempted.
