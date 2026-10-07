# PROGRESS — F33 land size derived from the operator datum (0.80 mm castellation)

Branch `fix/f33-land-size` @ base `github/main` `8032cb4`. Worktree `~/worktrees/bf-f33land2`.
Everything committed on THIS branch; `PROGRESS.md` / `REPORT.md` are gitignored, so they are
`git add -f`'d on the branch only.

## Cluster 1 — derive the land, regenerate all copies (DONE)

**Operator datum (authoritative, 2026-10-07):** castellation hole diameter
**D = 0.80 ± 0.10 mm**, the operator's own reading of the vendor drawing
(datasheet §9 p8, an embedded JPEG raster with no text layer — hence never
extractable in-repo).

**Rule:** `land = castellation aperture + a uniform 0.25 mm solder-fillet margin on every side`.
- along the edge (x): `L = D + 2×0.25 = 0.80 + 0.50 = 1.30 mm` (old guess: 2.0 mm = **2.5×D**)
- across the edge (y): `W = D + 2×0.25 = 1.30 mm`, symmetric about the pad centre, which the
  vendor file pins on the module edge (y = ±10.5) **and must not move** →
  inward `0.65 ≥ D/2 = 0.40`; outward `0.65` (hand-solder iron access, never smaller than inward)

**Arithmetic reported:** gap between neighbouring lands `3.9289 − 1.30 = 2.6289 mm`;
tolerance band `D=0.70→1.20 mm` / `D=0.90→1.40 mm` → gaps `2.7289 / 2.5289 mm`, no bridging.

**Files:** `scripts/gen_f33_landpattern.py` — hard-coded `LAND_*_MM` replaced by the
derivation (`CASTELLATION_D_MM`, `CASTELLATION_D_TOL_MM`, `LAND_FILLET_MARGIN_MM`);
`LAND_SIZE_VERIFIED = True`; `--land-length` / `--land-width` kept as explicit overrides;
`TODO(unverified)` land-size flag **dropped** in the generator, the emitted footprint and the
docs. Datum recorded in `tracker/hardware/footprints/nicerf-lora2021f33-2g4.json`.

**Pad POSITIONS unchanged — proven.** The pad-centre list of all four copies is byte-identical
to the pre-change list: sha256 `960877b2d9d17346e51ed0936451d80bd427c968351a326ae8fff9334eacc4ef`
before **and** after. Signature bbox unchanged at `31.4312 × 21.0000 mm`; only `sizes=2x1` →
`sizes=1.3x1.3`.

**Reproducibility:** two consecutive `--install` runs → byte-identical; each copy
sha256 `389e059cb2b10493ffbf76a21d6a309507abc6ff3bd3ec81ee8cf98046485e12`.

**`--verify-all`:** exit **0**, all four copies `18/18` vendor-coincident, nearest 0.000 mm.

## Cluster 2 — v9 design of record + consequence check (DONE)

- `build_flight_sch.py v9` regenerated `v9_lib/…LoRa2021F33_2G4.kicad_mod` (18/18 vendor-coincident
  guard PASSES; `sizes=1.3x1.3`), plus the sch/sym description text. Pad centres of the v9
  footprint byte-identical to before (`960877b2…`). `check_sch_gates.py v9` → **V9 GATES PASS**.
- **Consequence check on the frozen hub board:**
  - control run (restore OLD footprint, `--publish`) reproduces the frozen sha **exactly**
    → `2f0a66733b7a853b0052062e1e73833e7194fc7c38dcc257a749965314ab9238`
  - real run (corrected footprint) → board sha `07b0683bcfa967a25840f2855a4d8bd657d28d1785b4db864614fc3c611a3217`,
    seed sha `06ac5c92baa3214f11d89a30033e5815b07a07f3376f67f1d76256b55a832abf`
  - board diff vs frozen: **only U2 (the F33) moved**, y `12.00 → 12.15` (+0.15 mm, the builder's
    own pad-box proxy), **38 of 39 footprints identical** in position *and* geometry. No re-route.
  - S0 gates on the new board: pad overlaps **0**, courtyard overlaps **0**, `placement_gate PASS`.
  - board byte-reproducible across two publishes.
- **Classified: RE-VERIFICATION ONLY** (not a re-place, not a re-route) — no component left its
  floorplan seat; the frozen placement still holds.

## Cluster 3 — docs (DONE)

- `F33-LANDPATTERN-VERIFICATION.md` — **APPENDED** §11 (body §1–§10 untouched).
- `F33-SUPERSEDED-ARTIFACTS.md` — updated the "NOT available" datum sections + pre-order checklist.

## Gates (all green)

`gen_f33_landpattern.py --verify-all` → 0 · `check_sch_gates.py v9` → PASS ·
`hub_array_topology_check.py` → PASS · `bypass_diode_check.py` → PASS ·
pytest trio → 35 passed · full suite → see REPORT.md. **Order nothing.**
