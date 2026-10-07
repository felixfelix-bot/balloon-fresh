# PROGRESS — fix/f33-landpattern (F33 land pattern)

Branch: `fix/f33-landpattern` (worktree `/home/c03rad0r/worktrees/bf-f33land`).
Base: `github/main` @ `94c3c4d`. Nothing pushed to main/master; no force-push.

## Cluster 1 — establish ground truth (done)

* Read `docs/f33-module/F33-LANDPATTERN-VERIFICATION.md` (FAIL 0/18) and
  understood exactly what it compared: the repo footprint vs the **vendor's own
  land file** (`docs/f33-module/materials/LORA2021F33-2G4 footprint_pads.pcb`,
  sha256 `c66ea27c4409a3af58f1bfd967cddec60214d446d4b15f620f2eef82e86ee7ac`),
  cross-checked against datasheet §9 p.8 callouts.
* Re-decoded the vendor file independently: 18 pad records, tag `0x08435AD8`,
  36-byte stride from byte 7290, names `1..18`, 1.5e6 units/mm; pad 18 stored
  zeroed → ring closure `(-15.7156, -10.5)`. Scale pinned by three agreements
  (pitch 3.9289 ↔ 3.93 ±0.1; row separation 21.0000 = module width; closure
  `2×3.7844 + 8×3.9289 = 39.0000` = module length).
* Datasheet: §7 pin table IS text-extractable (`pdftotext`); §9 p.8 "Mechanism
  Dimension" is **two embedded JPEG rasters with no text layer**
  (`pdftotext -raw -f 8 -l 8` → header only; `pdfimages -list -f 8 -l 8` → 2
  images). OCR (tesseract) reproduces the callouts but they cannot be attributed
  to a feature ⇒ **pad LAND SIZE stays UNVERIFIED, not guessed**.
* Where the wrong pattern lives:
  * FIXED on main by `d5a2e47` (2026-10-07 02:54): the three `custom.pretty` copies.
  * STILL WRONG: `hub_board_f33.kicad_pcb` (0/18), `gen_pcb.py` `gen_v2` (the
    generator that emits it), `gerbers_f33/*`, `hub_board_f33_jlcpcb.zip`,
    `pcb_handoff.zip`, `output/pcb-handoff.zip`.
  * v9 path already correct (copied by `build_flight_sch.py` from hub_board_diy).
  * `v9_lib/balloon_flight_v9.kicad_sym` symbol `F33_2G4` carries NO footprint
    geometry (`grep -c 'pad "'` = 0) — it only stores the `Footprint` property.
* Checker defect found: `f33_landpattern_verify.py` hard-codes
  `REPO = ~/repos/balloon-fresh`; that shared checkout was on
  `feat/tracker-tx-tempcomp` (still pre-fix), so a re-run did NOT grade the
  branch under test.

## Cluster 2 — baseline gates (BEFORE edits), all green

* `build_flight_sch.py v9` × 2 → byte-identical (v9 sch `c7a51a51…`, F33 fp `90a6942f…`).
* `check_sch_gates.py v9` → ALL GATES PASS / V9 GATES PASS; ERC 19 errors
  (`pin_not_connected`, open by design — not touched).
* `scripts/hub_array_topology_check.py` → PASS. `scripts/bypass_diode_check.py` → PASS.
* `pytest tests/ -q --ignore=tests/p1b_ab_test.py` → same 6 collection errors as
  after the change (serial device / missing files); pre-existing environment state.

## Cluster 3 — the fix (done)

* NEW `scripts/gen_f33_landpattern.py` — decodes the vendor land file, 9
  self-checks, pinned sha256, emits the footprint with provenance in the header;
  `--check` / `--verify-all` / `--install`; land size flagged `TODO(unverified)`.
* `build_flight_sch.py` (v9) now DERIVES the F33 footprint from that generator at
  generation time and exits non-zero if the pads are not all on the vendor land
  pattern.
* All four footprint copies refreshed to generator output (geometry unchanged;
  header/comments normalised), canonical copy added at
  `tracker/hardware/footprints/f33/LoRa2021F33_2G4.kicad_mod`.
* `f33_landpattern_verify.py`: repo root from the script's own location +
  `--repo`; per-artifact grading; four-part identity signature; repo-relative
  evidence JSON.
* Stale artifacts marked (not deleted): banner + runtime warning in
  `gen_pcb.py` `gen_v2` (comments/print ONLY — `hub_board_f33.kicad_pcb` is
  byte-unchanged); `docs/f33-module/F33-SUPERSEDED-ARTIFACTS.md`; §10 addendum in
  `F33-LANDPATTERN-VERIFICATION.md`.

## Cluster 4 — proof (done)

* BEFORE (`d5a2e47^` worktree): 4/4 artifacts 0/18 coincident, bbox 39.0 × 16.0,
  nearest 4.071 mm, worst 10.226 mm → reproduces the documented FAIL exactly.
* AFTER: three `custom.pretty` copies + v9 footprint 18/18 coincident (bbox
  31.4312 × 21.0 mm, sizes 2×1, numbers 1..18); `hub_board_f33.kicad_pcb` still
  0/18 (deliberately stale, named superseded).
* `build_flight_sch.py v9` × 2 → byte-identical; v9 sch sha unchanged
  `c7a51a51…`; v9 F33 footprint `0a5dbe6c…`.
* Gates after: check_sch_gates v9 PASS (ERC 19, unchanged), hub_array PASS,
  bypass PASS, generator `--verify-all` exit 0.

## Cluster 5 — merge of github/main and final gate run (done)

`github/main` advanced from `94c3c4d` to `1351ed2e` while this branch was in
progress: *"fix(tests): make the suite runnable as a whole — two defects destroyed
the run"*, touching ONLY `tests/conftest.py` + `tests/test_pcb_track_import.py`
(zero overlap with this branch). Merged in as `33e6179` (clean, no conflicts) so
the pytest gate could be evaluated against the repaired suite. The pre-existing
`_pcbnew` segfault that killed the pre-merge runs is gone.

Final gate run on the merged branch:

* `check_sch_gates.py v9` → ALL GATES PASS / V9 GATES PASS; ERC 19
  (`pin_not_connected`, unchanged); v9 sch sha `c7a51a519e485e73` (unchanged).
* `hub_array_topology_check.py` → PASS. `bypass_diode_check.py` → PASS.
* `gen_f33_landpattern.py --verify-all` → exit 0, 4/4 copies 18/18.
* `pytest tests/ -q --ignore=tests/p1b_ab_test.py` (literal) → EXIT 2, aborts on
  `6 errors during collection` (missing serial devices / missing files).
* `… --continue-on-collection-errors` → **4 failed, 481 passed, 23 skipped, 16
  errors** (199.9 s, EXIT 1). Same 4 pre-existing failures and 16 environment
  errors as the untouched baseline `94c3c4d` → **zero test delta**.
