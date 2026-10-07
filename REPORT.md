# REPORT — parametric 3D models for the v9 WING board (feat/3d-models-wing)

**Scope:** the WING only. `tracker/hardware/hub_board/*`, the schematic and the master netlist were
**not touched** (they belong to the parallel `feat/3d-models-hub` worker). No push to main, no
force-push, nothing ordered.
**Base:** `github/main` @ `e03696a` · **branch:** `feat/3d-models-wing` · worktree `~/worktrees/bf-3dwing`
**Committed coverage report:** `docs/3d-model-coverage-wing.md` (all 12 refs, per-ref source, the
assembly note). **This file and `PROGRESS.md` are gitignored (`.gitignore:67/68`) and are committed
with `git add -f` on THIS branch only — they must never go to main.**

## 1. Outcome

* **The wing now renders with its parts.** Before: no reference on the board carried a model, so a
  3D render showed a bare FR4 outline with the three solar cells — the wing's whole purpose —
  invisible. After: 9 of the 12 references carry a committed model.
* **The cells are the point, and they are the SMALL class.** `SC1`/`SC2`/`SC3` are modelled at
  **52.07 × 19.65 × 0.21 mm** and are visible as three deep-violet cell faces in both delivered
  renders. Class evidence: the board puts all three under `WingV9:SolarCell_52x19mm` /
  `SolarCell_52x19mm_0.5V` with a 52 × 19 mm silk field and lands at x = ±28, matching ADR-049's
  measured small cell (52.07 × 19.65 × 0.20–0.21 mm) and ADR-051 §1.4's distinction from the large
  class (78.55 × 38.90). A 38.90 mm-wide cell cannot physically fit this 25 mm body. (ADR-049
  *recommends* the LARGE class but its status is **Proposed, not accepted**; the large model is
  shipped as a shared asset for the hub/array direction, unassigned.)
* **Deliverables:** `renders/wing_v9_top.png` + `renders/wing_v9_iso.png` (both 1768 × 1376, high
  quality, perspective), `docs/3d-model-coverage-wing.md`, 6 committed VRML models in
  `tracker/hardware/3dmodels/`, the generator `scripts/gen_3d_models_wing.py`, the gate
  `tests/test_3d_models_wing.py` (18 cases), and the refreshed wing gate record.
* **No assembly render, deliberately.** The wing's plane orientation is contradictory across four
  records (`ADR-049 §5.6` vertical · `WING-TO-HUB-SOCKET-SPEC §1` horizontal/30° in the same
  paragraph · `ADR-046 §4.1` 90° · `ADR-048` `OPEN-23` recorded unresolved) and the standoff height
  is itself open (`ADR-055 D6`, constraint `cot(e) × Z = 3.363 Z`, value unfixed). §8 of the
  coverage report states exactly what would have to be frozen first. Nothing was invented.

## 2. What was built (files)

| Path | What it is |
|---|---|
| `scripts/gen_3d_models_wing.py` | parametric generator; `--check` mode fails closed on a stale tree; the module docstring carries the **measured** KiCad frame/unit convention and how it was measured |
| `tracker/hardware/3dmodels/cells/solar_cell_small_52.07x19.65x0.21.wrl` | **the wing's cell** (assigned to SC1–SC3) — distinct violet illuminated face + grey back/sides |
| `tracker/hardware/3dmodels/cells/solar_cell_large_78.55x38.90x0.21.wrl` | shared asset (hub/array direction) — deliberately **unassigned** on the wing |
| `tracker/hardware/3dmodels/wing/wing_v9_tab_4pin_lands.wrl` | J1's four 4.0 × 1.2 lands at 1.8 mm pitch, pinout in the header |
| `tracker/hardware/3dmodels/wing/wing_v9_fiducial_1mm_dot.wrl` | FID1–FID3, ⌀1.0 × 0.035 |
| `tracker/hardware/3dmodels/wing/ferrite_bead_0402_dnp.wrl` | FB1 — **DNP**, rendered at transparency 0.75 so it cannot be read as a populated part |
| `tracker/hardware/3dmodels/wing/wing_v9_rf_provision_pad_2x2.wrl` | RF1's V2 provision land |
| `tracker/hardware/wing_board/build_wing_v9.py` | patched to emit the `(model …)` children; nothing else |
| `tracker/hardware/wing_board/wing_board_v9.kicad_pcb` | regenerated: **+99 lines / 0 deletions**, all model metadata |
| `tracker/hardware/wing_board/renders/wing_v9_top.png`, `…_iso.png` | the two delivered renders |
| `docs/3d-model-coverage-wing.md` | committed 3D coverage report + the assembly note |
| `tests/test_3d_models_wing.py` | gate: staleness, provenance, VRML well-formedness, the 2.54 mm unit convention, the 9/3 assignment, the report's contents |
| `tracker/hardware/wing_board/wing_v9-GATE-RECORD.json` | refreshed (`board_sha256` changed; every verdict figure identical) |
| `PROGRESS.md`, `REPORT.md` | `git add -f` on this branch (gitignored; never on main) |

## 3. Verification (numbers, not adjectives)

* **Nothing else changed on the board.** Parsed both revisions and set-compared: nets (17),
  footprints (12, with lib id / reference / position / every pad), track segments (8), Edge.Cuts
  lines (8), `gr_text` (1), thickness (0.6) — **identical**. The diff is exactly the 9 `(model …)`
  blocks (99 lines), 0 deletions. Two generator runs are byte-identical (no drift).
* **Reuse check before creating anything:** `git ls-tree -r github/main | grep -iE '3dmodel|\.wrl'`
  → empty, and no `feat/3d-models-hub` branch existed on `github` or `ngit` when this branch was cut
  → **nothing was reused; 6 models were created**, with the cell models placed in a `cells/`
  subdirectory so the hub worker can reuse them rather than duplicate them.
* **Renders verified numerically** (calibrated on the known 184.0 mm outline, 7.4022 px/mm): the
  three cell faces measure **51.88 mm** wide against the modelled 52.07 mm (0.4 %, ≈1 px); cell-face
  area 167 017 px ≈ 3 × 52.07 × 19.65 mm²; a `--side bottom` control render has **0** blue pixels,
  proving the Z convention (cells on the TOP face, not sunk into the 0.6 mm board).
* **NPTH holes: a model would have been wrong.** Measured with
  `--side top --quality basic --width 700 --height 500`: with no model assigned the three hole sites
  are **20/25 transparent** (a punched bore); with a ⌀2.2 × 0.6 cylinder in the drill volume they are
  **0/25** (the bore is plugged). A zero-thickness bore liner produced a byte-identical image to no
  model. So `H1`–`H3` are **NO MODEL** with that measurement recorded — coverage is **9 modeled /
  3 NO MODEL**, not 12/0.
* **Wing gate record:** `pcb_order_gate.py tracker/hardware/wing_board/wing_board_v9.kicad_pcb --fab
  tracker/hardware/output/gerbers_wing_v9 --out …/wing_v9-GATE-RECORD.json` → **ORDER GATE: PASS,
  errors 0, unconnected 0, warnings 23** — the same five warning categories with the same counts as
  the pre-change record; `--verify` → **VERIFIED, exit 0**. `fab_sha256` unchanged (`90cb2480…`);
  re-plotting the gerbers from the new board reproduces the committed package with only the two
  embedded creation-date lines differing, i.e. **the copper did not change and the fab package was
  not re-cut**.
* **Tests:** `python3 -m pytest tests/test_3d_models_wing.py -q` → **18 passed**.
  Full suite: `python3 -m pytest tests/ -q --continue-on-collection-errors` → see §5.
* **Not claimed:** the renders are the bare board with its parts — no hub, no second wing, no balloon
  line. They are not an assembly, and they are not a statement that anything is ready to order
  (the cell-tab geometry that ADR-049 calls the order blocker is still `TODO(unverified)`).

## 4. Findings the operator may care about

1. **The land field is wider than the cell it must carry.** ADR-046 §3.4 puts the two lands 56.00 mm
   apart (±28 mm from each cell centre) while the measured cell is 52.07 mm long, so the modelled
   cell stops **1.17 mm short of each land's inner edge** and does not overlap its own lands as
   drawn. Not changed (placement is not this card's scope) — but it is the concrete form of ADR-049's
   order blocker, and it is what the operator's cell-tab measurement must settle.
2. **Modelling a hole destroys it** (measured above) — worth knowing before anyone "completes" the
   hub's coverage with fastener models.
3. **The hub board's 32 existing model assignments all point at `${KICAD9_3DMODEL_DIR}/…step`**
   (e.g. `R_0402_1005Metric.step`), i.e. at `kicad-packages3d`, which is **not installed** and must
   not be (4.77 GB vs ~2.3 GB free). Those references resolve to nothing today, so the hub renders
   bare. That is the parallel worker's scope; flagged here only because it is the other half of the
   "see the whole vehicle" goal, and it is the reason a hub+wings render would still show a bare hub.
4. **Disk is tight** (2.3 GB free at the end); `kicad-packages3d` remains un-installable, which is
   exactly why these models are plain text in-repo (52 KB total).

## 5. Test suite + tree hygiene

* Full suite after the change (`python3 -m pytest tests/ -q --continue-on-collection-errors`):
  **567 passed / 1 failed / 37 skipped, exit 1**, 421.8 s. The new module adds 18 cases
  (549 + 18 = 567), and all 18 pass.
* **The one failure is environmental, and it is a different test from the baseline's failure.**
  `tests/test_c_host.py::TestWirehair::test_wirehair_host` failed with
  `subprocess.TimeoutExpired: … 'g++' … timed out after 60 seconds` — a C++ host compile that needs
  more than 60 s only while the machine is loaded (this run raced the wing renders and two other
  worktrees). **Re-run alone with the machine quiet: `1 passed in 7.05 s`.** Baseline before the
  change was **549 passed / 1 failed / 37 skipped** (the brief said 550/37/exit 0), where the failure
  was `tests/test_board_lock.py::test_lock_status` — a board-lock tool call that times out at 10 s
  only under the full-suite load; re-run alone **2 passed / 6 skipped**. Both are load/hardware
  flakes on a contended machine, and neither test touches anything this branch changes (no firmware,
  no board lock, no 3D model). The suite is otherwise green and no test regressed.
* **Two files show as modified and are deliberately NOT staged:**
  `tracker/firmware/components/fips_transport/test/test_fips` and `…/test_fips_pipeline` are checked-in
  ELF test binaries that the test run rebuilt (113 208 → 113 200 bytes, 132 832 → 132 824). They are
  build artifacts of the suite, not this card's work; staging them would sweep another track's tree
  into this branch.
