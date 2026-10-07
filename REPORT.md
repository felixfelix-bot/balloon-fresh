# REPORT — F33 land pattern: verdict, fix, and what is still stale

**Branch** `fix/f33-landpattern` (base `github/main` `94c3c4d`) · **worktree**
`/home/c03rad0r/worktrees/bf-f33land` · **date** 2026-10-07 · **language** English.

## 1. The verdict on the existing FAIL: a REAL geometry error (not a stale check)

`docs/f33-module/F33-LANDPATTERN-VERIFICATION.md` reported **FAIL 0/18**. That is
correct and it is a real geometry error — not a wrong reference and not
unverifiable:

* The pattern in the design of record put the 18 pads on the two **21 mm ENDS**
  at a **2.0 mm** pitch (pad-centre bbox 39.0 × 16.0 mm).
* The vendor's own land file puts **9 pads on each of the two 39 mm EDGES** at a
  **3.9289 mm** pitch, rows at y = ±10.5 (row separation 21.0000 mm = module
  width), outermost pad centre **3.7844 mm** from the module end, closing as
  `2 × 3.7844 + 8 × 3.9289 = 39.0000 mm` = module length.
* Measured by a second, independent implementation: **0 of 18 pads coincide;
  nearest misalignment 4.071 mm, worst 10.226 mm** — the same numbers the
  original card recorded.
* It is invisible to every electrical gate: pad count (18), pad-number string
  (1..18), body outline (39 × 21) and reference (U2) were all correct all along.
  **ERC/DRC/net-parity cannot see it.** Only a comparison against the vendor land
  data can.

Secondary finding (**case ii**, a checker defect): `f33_landpattern_verify.py`
hard-coded `REPO = ~/repos/balloon-fresh`. That shared checkout was on
`feat/tracker-tx-tempcomp`, a branch that still carried the pre-fix pattern, so a
"re-run of the checker" graded the wrong branch. Fixed (repo root derived from
the script's location; `--repo` override; repo-relative evidence JSON).

## 2. Authoritative source used

`docs/f33-module/materials/LORA2021F33-2G4 footprint_pads.pcb` — the **vendor's
(NiceRF) own Altium land file**, sha256
`c66ea27c4409a3af58f1bfd967cddec60214d446d4b15f620f2eef82e86ee7ac`, shipped in
`docs/f33-module/LoRa2021F33-2G4-materials.zip`. 18 pad records (tag
`0x08435AD8`, 36-byte stride from byte 7290, 1.5e6 units/mm), pad 18 stored
zeroed and placed by ring closure. Cross-checked against the datasheet §7 pin
table (`pdftotext`-readable) and the §9 p.8 callouts.

**One thing is deliberately NOT verified:** the pad **land size**. Datasheet §9
(p.8) is two embedded JPEG rasters with **no text layer** — `pdftotext -raw -f 8
-l 8` prints only the page header and `pdfimages -list -f 8 -l 8` shows the two
images. OCR (tesseract — a text extractor, not `vision_analyze`) reproduces the
callouts `3.78 / 3.93 / 0.80 / 3.00 ×2 / 6.09 / 5.00 ×2 / 4.32 / 39.00 / 9.00 /
3.30`, but their positions cannot be attributed to a feature without reading the
drawing, so the emitted land size stays 2.0 × 1.0 mm and is flagged
`TODO(unverified)` in the footprint, the generator and the docs. **A guessed land
is worse than a flagged one, because it looks verified.**

## 3. Pads before / after

| | pads | pad-centre bbox | sizes | numbers | on the vendor pattern |
|---|---|---|---|---|---|
| **before** (`d5a2e47^`, all four artifacts) | 18 | 39.0000 × 16.0000 mm | 2 × 1 | 1..18 | **0/18** (nearest 4.071 mm, worst 10.226 mm) |
| **after** (three `custom.pretty` copies + v9 footprint) | 18 | 31.4312 × 21.0000 mm | 2 × 1 | 1..18 | **18/18** (0.000 mm) |
| `hub_board_f33.kicad_pcb` (left stale) | 18 | 39.0000 × 16.0000 mm | 2 × 1 | 1..18 | 0/18 |

Pad count matched before and after — which is exactly why the four-part identity
signature (count, bbox, size histogram, pad-number string) is the check that
matters, not the count.

## 4. The fix, and why it cannot silently regress

1. **`scripts/gen_f33_landpattern.py` (new).** Decodes the vendor land file with
   nine self-checks (pad count, names ring, pad 18 zeroed-in-file, two rows at
   ±10.5, nine per row, uniform pitch, closure = 39.0000, row separation =
   21.0000, outer pad 3.7844 from the end) and a **pinned source sha256**. Any
   drift → exit non-zero, no footprint written. Modes: `--print`, `--check FILE`,
   `--verify-all`, `--install`. The land size is a declared parameter
   (`--land-length/--land-width`) so it can be set, with proof, later.
2. **`build_flight_sch.py` (v9 generator).** Now **derives** the F33 footprint
   from that script at generation time (it no longer copies a `custom.pretty`
   file) and **exits non-zero** if the emitted pads are not all on the vendor land
   pattern. The v9 design of record therefore cannot re-acquire a stale land
   pattern unnoticed.
3. **All four committed footprint copies** are now generator output — identical
   geometry, header normalised with the provenance block. Canonical copy added at
   `tracker/hardware/footprints/f33/LoRa2021F33_2G4.kicad_mod`.
4. **Stale artifacts marked, not deleted** (§5).

### Generator determinism

`build_flight_sch.py v9` run twice → **byte-identical** across the board:
`v9_flight.kicad_sch` = `c7a51a519e485e7356d704e184b82cc51df53976b73972aa90f512b0e58e8f44`
(unchanged from before this branch — the schematic is not perturbed),
`v9_lib/balloon_flight_v9.pretty/LoRa2021F33_2G4.kicad_mod` =
`0a5dbe6cba77f177235622d8119a7c2b1b96997d941acfdec73582baa25e9e86`.

## 5. Stale artifacts — disposition (nothing deleted)

All of these are **SUPERSEDED and must not be ordered, quoted to a fab, or
assembled**. Full register with hashes: `docs/f33-module/F33-SUPERSEDED-ARTIFACTS.md`.

* `tracker/hardware/hub_board_f33.kicad_pcb` (`ede3481cf9e3774f…`) — 0/18 pads
  on the vendor pattern. **Byte-unchanged by this branch.**
* `tracker/hardware/gen_pcb.py` `gen_v2` — the generator that emits it. **Comments
  and one `print()` warning added only; no geometry line touched**, so the
  historical board stays reproducible from its own generator.
* `tracker/hardware/gerbers_f33/*`, `hub_board_f33_jlcpcb.zip` (`b6d9477012f9c537…`)
  — plotted from the stale board.
* `tracker/hardware/pcb_handoff.zip` (`0dffa755c3eb62d5…`) and
  `tracker/hardware/output/pcb-handoff.zip` (`176053bfcc293738…`) — each carries
  the pre-fix `custom.pretty/LoRa2021F33_2G4.kicad_mod` (`9104e3cafc30a735…`)
  plus the pre-fix routed `v_c3_flight_v7_routed.kicad_pcb`.

A replacement F33 board is a **re-route** (placement + routing) from the
corrected footprint — a new placement sha and a new placement-guard run — not a
re-score of the old board.

## 6. Gates

| gate | before | after |
|---|---|---|
| `build_flight_sch.py v9` ×2 | byte-identical | **byte-identical** |
| `check_sch_gates.py v9` | ALL GATES PASS / V9 GATES PASS, ERC 19 `pin_not_connected` | **ALL GATES PASS / V9 GATES PASS, ERC 19 (unchanged — open pins deliberately untouched)** |
| `scripts/hub_array_topology_check.py` | PASS | **PASS** |
| `scripts/bypass_diode_check.py` | PASS | **PASS** |
| `gen_f33_landpattern.py --verify-all` | n/a | **exit 0, 4/4 copies 18/18** |
| `pytest tests/ -q --ignore=tests/p1b_ab_test.py` | **EXIT 139 (segfault in `tests/test_pcb_track_import.py`, `_pcbnew`)** + 6 collection errors | **identical** (same segfault, same per-file progress, same 6 collection errors) |

The pytest gate is **not green in this environment and was not green before this
branch** — the run dies in a pre-existing `_pcbnew` segfault. No test imports any
file this branch changed (verified by grep). See §7 for the reduced run that gets
past the segfault and shows the tally is unchanged.

## 7. Reduced pytest run (excluding the segfaulting module)

`python3 -m pytest tests/ -q --ignore=tests/p1b_ab_test.py
--ignore=tests/test_pcb_track_import.py --continue-on-collection-errors`
run against (a) an untouched worktree at the merge base `94c3c4d` and (b) this
branch:

| tree | result |
|---|---|
| baseline `94c3c4d` (no changes) | `4 failed, 466 passed, 10 skipped, 16 errors` (188.9 s) |
| this branch | `4 failed, 466 passed, 10 skipped, 16 errors` (185.9 s) |

The FAILED/ERROR **set is byte-identical** (4 pre-existing failures: 3 in
`tests/src/test_phase1_runner.py`, 1 in `tests/test_board_lock.py`; 16 errors, all
serial-device / missing-file / missing-hardware). So the branch has a **zero test
delta**. The remaining failures are pre-existing environment state (no ESP32
boards attached, no serial devices, `_pcbnew` segfault), not regressions.
