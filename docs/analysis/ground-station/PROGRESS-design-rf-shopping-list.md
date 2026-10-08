# PROGRESS — design/rf-shopping-list (ground-station internet-gateway RF shopping list + duplex ADR)

Branch `design/rf-shopping-list` off `github/main` @ `09e1b69`.
Worktree `/home/c03rad0r/worktrees/bf-shoplist`.
*This file is gitignored in balloon-fresh (`.gitignore` lines ~67-68); it is committed with
`git add -f` on this branch only.*

## Cluster 1 — recon + sourcing (done)
- Remotes fetched; `github/main` tip confirmed `09e1b69`. ADR numbers 066–069 already claimed
  by in-flight sibling ground-station branches (`design/ground-station-lowpower-link`,
  `-flrc-max`, `gain-per-dollar`, `positioner-lowcost`, `tier0-accessible`) → this work takes
  **070**.
- Prior sibling sourcing found (`design/ground-station-bom` @ `283cad72`,
  `docs/analysis/ground-station-bom-candidates.md`) — reused/cited for antennas + coax.
- Sources fetched 2026-10-08: funktechnik-bielefeld.de (A-430S15R €74.50, SLP-17 €59.00,
  WLAN category), kabel-kusch.de (Airborne 10 €4.30/m + dB tables), psemi.com (PE43711),
  analog.com (HMC425A pdf), Skyworks SKY66112-11 datasheet (Wayback), Qorvo TQP3M9037
  (Wayback), redpitaya.com (STEMlab 125-14 DC-60 MHz), nooelec.com (NanoVNA-H4), AliExpress
  search listings (DE/EUR). Mouser/Digi-Key/Pasternack/Qorvo-live blocked.

## Cluster 2 — model + analysis (done)
- `docs/analysis/rf_shopping_list_model.py` — stdlib, runs `exit 0`, prints every table
  (duplex isolation, TX leakage, uplink EIRP vs legal ceiling, PA/attenuator sizing,
  gain-control range, circulator-vs-protection, Red Pitaya reach). No `%%` leakage.
- `docs/analysis/rf-shopping-list-and-duplex-architecture.md` — TASK 0 verdict first, sourced
  parts, single shopping list with OWNED marked, totals for cheapest + recommended builds.

## Cluster 3 — ADR + delivery (done)
- `docs/adr/070-ground-station-duplex-t-r-architecture.md` (Proposed; numbering note records
  the sibling claims). `docs/adr/INDEX.md` regenerated via `scripts/gen_adr_index.py`.
- `scripts/param_ssot_check.py` → **PASS (exit 0)**. `git diff --check` clean.
- Pushed github then ngit separately; both verified at
  `33304dc2880afe3fcd6d3406118ede9820c97a21`.

## Open items carried in the analysis (§8)
XR-613 identity; unmarked mixer specs; RF2126 control pin; nRF21540 gains; Airborne-10 price
discrepancy vs sibling BOM; A-430S10R not re-verified; AliExpress "from" prices; DE amateur
2.4 GHz power limits; cheap circulator isolation figures.
