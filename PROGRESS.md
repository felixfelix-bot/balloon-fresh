# PROGRESS — feat/3d-models-wing (WING only; the hub board is a different worker)

Worktree: `~/worktrees/bf-3dwing` · base `github/main` @ `e03696a` · branch `feat/3d-models-wing`
Deliverable: parametric 3D models for the v9 WING board's parts (incl. its three solar cells),
assigned so a render resolves, + top & isometric renders + a 3D coverage report + the assembly note.

Not pushed to main, not force-pushed, hub board untouched. This file and `REPORT.md` are
gitignored (`.gitignore:67/68`) and are `git add -f`-ed on THIS branch only.

| # | Cluster | State |
|---|---|---|
| 0 | Worktree + baseline: `pytest tests/ -q` = **549 passed / 1 failed / 37 skipped** (the failure is `test_board_lock.py::test_lock_status`, a board-lock tool timeout; it passes 2/6 alone → environmental flake, re-run at the end) | done |
| 1 | Read the wing: outline measured (body 176×25, tab 8×9, total 184×25×0.6), 12 refs, 3 cells, cell class established as **SMALL 52.07×19.65×0.21** (ADR-049 §Measured inputs; board says `SolarCell_52x19mm`) | done |
| 2 | Measured KiCad's VRML convention with a throwaway probe board (`kicad-cli pcb export vrml --units mm`): **1 unit = 2.54 mm**, frame **x = footprint +x, y = −(footprint +y), z = 0 at board top face**; corroborated by the shipped `ecc83.wrl` demo model (8.86 units = 22.5 mm envelope vs a 21.2 mm courtyard) | done |
| 3 | Wrote `scripts/gen_3d_models_wing.py` + 6 committed VRML models in `tracker/hardware/3dmodels/` (`cells/` = shared, `wing/` = wing-specific), each header citing a dimension source or `TODO(unverified)` | done |
| 4 | Assigned models in the generator `build_wing_v9.py`, regenerated the board: **+99 lines, 0 deletions**; proven by parse-and-set-compare that nets (17), footprints (12: lib id/ref/at/pads), segments (8), Edge.Cuts (8), gr_text (1), thickness are all identical. Determinism: two runs byte-identical | done |
| 5 | NPTH finding: a model in the drill volume **plugs** the bore (measured 20/25 → 0/25 transparent px with `--quality basic --width 700 --height 500`); a zero-thickness liner is byte-identical to no model → **H1–H3 carry NO MODEL** (kicad-cli punches the bore itself) | done |
| 6 | Rendered `--side top` and `--side top --rotate -45,0,45` at `--quality high --perspective --width 1800 --height 1400` → `renders/wing_v9_top.png`, `renders/wing_v9_iso.png` (1768×1376 as delivered). `--side right` rejected (edge-on: 0 cell pixels) | done |
| 7 | Render verification (numeric, not by eye): calibrated on the 184.0 mm outline, the three cell faces measure **51.88 mm** each against the modelled 52.07 mm; cell-face area 167 017 px ≈ 3×52.07×19.65 mm²; a `--side bottom` control has **0** blue px → cells are on the TOP face | done |
| 8 | `docs/3d-model-coverage-wing.md` — all 12 refs, per-ref source, counts 9 `modeled` / 3 `NO MODEL`, the land-vs-cell discrepancy (56.00 mm land pitch vs 52.07 mm cell), the §8 **assembly note** (no assembly render; the orientation contradiction + socket + ADR-055 D6 standoff named) | done |
| 9 | Gate record refreshed: `pcb_order_gate.py … --fab tracker/hardware/output/gerbers_wing_v9` → **PASS, errors 0, unconnected 0, warnings 23** (identical to the pre-change record), `--verify` **exit 0**, `fab_sha256` unchanged; gerbers re-plotted from the new board differ only in the two embedded creation-date lines | done |
| 10 | `tests/test_3d_models_wing.py` (18 cases) green — gates the generator/`--check` staleness, per-model provenance, VRML well-formedness, the **2.54 mm unit convention vs the cited 52.07 mm**, the 9/3 assignment, and the coverage report | done |
| 11 | Full suite re-run: **567 passed / 1 failed / 37 skipped** (549+18 new cases). The single failure, `test_c_host.py::TestWirehair::test_wirehair_host` (a g++ compile that hit its 60 s timeout under load), **passes in 7.05 s when re-run alone** — environmental, as was the baseline's `test_board_lock` failure. Then `PROGRESS.md` + `REPORT.md` (`git add -f`), commit, push `github` then `ngit` separately, `git ls-remote` on both | see REPORT.md |

Unsourced dimensions carried in the models (all written as `TODO(unverified)` in the model headers):
the cell's solder-tab geometry (ADR-049: the order blocker) · whether the small cell's terminations
are both on the front face or front+back · the FB1 0402 body **height** 0.5 mm (the size code fixes
only length/width) · the FB1 part number/impedance · socket slot tolerance · 0.6 mm/184 mm fab
acceptance · the ADR-055 D6 standoff height.
