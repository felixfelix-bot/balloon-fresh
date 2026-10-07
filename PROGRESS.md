# PROGRESS — docs/v9-system-diagram (worktree `bf-sysdiag`)

Branch: `docs/v9-system-diagram`, based on `github/main` tip `e4d0569`.

## Cluster 1 — recon (DONE)
- Worktree created from `github/main` (`e4d0569`); schematic files present at
  `tracker/hardware/schematics/flight_board/`.
- Regenerated the v9 schematic with `build_flight_sch.py v9` → confirms
  **46 components / 47 nets / 225 symbol pins / 12 no-connects / 32 TODO notes**.
- Parsed `v9_flight.net`: 46 `(comp)` blocks, 47 `(net)` blocks.

## Cluster 2 — BOM extractor (DONE)
- `scripts/gen_v9_bom.py` written: reads the netlist, emits `docs/v9-BOM.md`.
  - Machine columns (Reference / Value / Footprint / lib id / DNP / nets) are read
    from the netlist; FUNCTION prose is a dict that must cover every ref or the
    script exits non-zero.
  - `--check` mode for staleness; verified idempotent.
- Result: 46 rows, 46 counted, matches `grep -c '(comp (ref '`.
- DNP found in the netlist: **`R_NTC1`, `TH_NTC1`** (from `(property (name "dnp"))`
  and confirmed against `(dnp yes)` in the `.kicad_sch`).
- Discrepancies recorded: barometer MS5611-01BA vs ADR-108's MS5607-02BA03;
  D_BP1..D_BP4 part family/rating/DNP state (ADR-048 text vs ADR-049 rating);
  wing pin 3 `RF_FEED` wired as cut-sense (contra ADR-048 §2.3);
  `U_HUB_CVT` output rail has no net; ERC = 23 `pin_not_connected`, 0 warnings.

## Cluster 3 — diagram SVG (DONE)
- `docs/v9-system-diagram.svg` hand-authored, 1900 × 1472, dark theme, inline
  styles only, system fonts, no external CSS/JS/fonts.
- Regions: POWER / RADIO / SENSING / COMPUTE & STORAGE / CUT-SHED /
  KEY NUMBERS / LEGEND+gaps.
- Iteration 1 was measured and **failed** 22 text-overflow checks — the layout was
  re-gridded (wider canvas, 3-column power chain, wider cards) and re-measured.
- `scripts/check_v9_diagram_layout.py` written as the layout gate: measures every
  `<text>` getBBox() in headless Chromium against its enclosing rect.
  Final: **0 text overflow, 0 rect overlap, 0 text-vs-text overlap** → PASS.

## Cluster 4 — PNG (DONE)
- `rsvg-convert`: ABSENT. `inkscape`: ABSENT. `cairosvg`: ABSENT.
- Fell back to headless Chromium via `scripts/render_v9_diagram_png.sh`;
  documented explicitly in REPORT.md (no fabrication: real raster of the same file).
- `docs/v9-system-diagram.png` = **1900 × 1472, 614 904 bytes** (> 10 KB).
  Pixel-verified: corners exactly `#0d1117`, panels brighter, ~4.9 % bright pixels,
  41 660 unique colours.

## Cluster 5 — commit / push (DONE)
- Committed the SVG, PNG, BOM, three scripts, PROGRESS.md and REPORT.md
  (`git add -f` for the two gitignored files).
- Pushed to `github` first, then `ngit` separately; SHAs verified with
  `git ls-remote` on both remotes.
