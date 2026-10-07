# PROGRESS — JLCPCB size-tier quote salvage

Branch: `analysis/jlcpcb-size-tier-quote-salvage` (worktree `/home/c03rad0r/worktrees/bf-quote2`)
Base: `github/main` @ `716974a`
Task: salvage a timed-out (3600 s) JLCPCB quoting run by documenting the on-disk measurements.
**No order placed. No browser re-driven.**

## Cluster 1 — recon & worktree
- [x] `git fetch -q github`; confirmed `github/main` tip = `716974a`.
- [x] `analysis/jlcpcb-size-tier-quote` already existed (held by the stale `bf-quote` worktree,
  pointing at `8032cb4`) -> created fresh branch/worktree `analysis/jlcpcb-size-tier-quote-salvage`
  off `github/main` at `/home/c03rad0r/worktrees/bf-quote2`.
- [x] Inventoried `~/quote-scratch/measurements/`: 36 per-config JSONs + `SUMMARY.json`.
  Noted the raw JSONs live OUTSIDE the repo.

## Cluster 2 — read & classify the raw evidence
- [x] Parsed every per-config JSON (`quote` object) and `SUMMARY.json` (in-force option set +
  `panel_pairs` charge lines).
- [x] Verified the isolation claim: 35/36 files carry `page_load` = "FRESH navigation (new tab) ->
  isolated"; `t1_103_4L_06` has no `page_load` field (older schema) -> residual.
- [x] Classified 30 VALID vs 6 INVALID. Invalid: 4 empty-price 2-layer rows
  (`c_100_2L_06`, `c_89_2L_06`, `h_100_2L_16`, `h_89_2L_16` — config price empty, SUMMARY $4.00),
  `i_89_4L_04_ENIG` ($0.00, options failed to apply), `t1_103_4L_06` (residual schema).
- [x] Confirmed `engineering_fee: null` in the cheap class is truthful (single "Special Offer"
  line instead of Engineering fee + Board); arithmetic closes exactly.
- [x] Confirmed the boundary (102, 102.5] mm on the largest side and the driver = largest single
  dimension, with explicit exclusion of area and perimeter.

## Cluster 3 — write the doc (machine-generated numbers)
- [x] Wrote `/tmp/gen_doc.py` to emit `docs/analysis/jlcpcb-size-tier-quote.md` so every figure is
  computed from the JSONs (no hand-typed figures).
- [x] Sections: isolation, full valid charge-line table, invalid table, boundary + driver, delta,
  reproducibility, engineering-fee finding, thickness/finish confound, Different Design 2,
  the 1 mm-trim option + recommendation, output-field summary, provenance.
- [x] Regenerated after fixing the `l_*` option fields (from their own `final_selected`) and the
  §9.2 wording (295% is the price increase; the saving is a 74.7% reduction).

## Cluster 4 — commit & dual push
- [x] `git add docs/analysis/jlcpcb-size-tier-quote.md` (only the doc; raw JSONs NOT committed).
- [x] `git add -f PROGRESS.md REPORT.md` (both gitignored at .gitignore:67/68 — forced onto THIS
  branch only; they are NOT pushed to main).
- [ ] Push `github` FIRST, then `ngit` SEPARATELY (no --atomic); verify with `git ls-remote`.
