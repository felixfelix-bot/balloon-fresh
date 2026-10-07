# REPORT — JLCPCB price-tier record + 102 × 102 mm hub outline decision

**Branch:** `docs/jlcpcb-pricing-and-outline-decision` (off `github/main` @ `716974a`)
**Worktree:** `/home/c03rad0r/worktrees/bf-jlcdoc`
**Deliverables commit:** `632c6f173d6de8f93083346402b97578fd3608c7` (commit A, below)
**Mode:** documentation + salvaged raw evidence only. **No board / schematic / netlist / footprint /
placement file was changed. No order was placed.**

## Output schema fields

| field | value |
|---|---|
| `branch` | `docs/jlcpcb-pricing-and-outline-decision` |
| `head_sha` | `632c6f173d6de8f93083346402b97578fd3608c7` (deliverables commit; branch tip after adding PROGRESS/REPORT is the push tip — see the push-verification table) |
| `github_sha` | see push-verification table (github pushed FIRST) |
| `ngit_sha` | see push-verification table (ngit pushed SEPARATELY, no `--atomic`) |
| `adr_number` | `063` |
| `adr_path` | `docs/adr/063-hub-outline-trim.md` |
| `analysis_path` | `docs/analysis/jlcpcb-pricing-and-size-tier.md` |
| `raw_evidence_path` | `docs/analysis/jlcpcb-quote-2026-10/` (119 files: `measurements/` 41 JSON + 40 TXT, `logs/`, `scripts/`, `README.md`) |
| `cheap_class_price` | `$8.00` (qty 5, 4-layer, 1.6 mm, HASL-with-lead; single "Special Offer" line) |
| `expensive_class_price` | `$31.60` (103 × 103 mm: Engineering fee $25.00 + Board $6.60) |
| `delta` | `$23.60` (per qty-5 order; $4.72/board at qty 5) |
| `boundary_mm` | between **102.0 mm** (cheap) and **102.5 mm** (expensive) on the **largest single side** |
| `repeats_consistent` | **yes** — 103 mm ×4 → $31.60; 102 mm ×2 → $8.00; 89 mm ×2 → $8.00 |
| `confound_stated` | **yes** — thickness and surface finish are coupled; 0.8 mm→LeadFree HASL($5.20–5.30), 1.6 mm→HASL-with-lead($0.00). No thickness price effect asserted. |
| `invalid_configs_listed` | **yes** — `c_89_2L_06`, `c_100_2L_06`, `h_89_2L_16`, `h_100_2L_16`, `i_89_4L_04_ENIG` (+ residual `t1_103_4L_06`) |
| `residual_103_measurement_closed` | **yes** — closed as *configuration not offered*: 0.6 mm is **DISABLED at 4 layers** (`res_103_4L_06.json`); no valid 103 mm/4L/0.6 mm quote exists or can exist |
| `duty_implication` | 104.04 / 106.1 cm² = **98.07 %**, so ≈ **98.1 % of the full-design sustained duty**; the full 0.388 W design is **~1.9 % short**. ADR-055 D3 owns the area; if full duty is required, 102 mm and the cheap tier are mutually exclusive. |
| `ssot_registry_exists` | **no** — no SSOT parameter registry on `main`; the outline entry is **owed**, no competing file created |
| `re_place_flagged` | **yes** — the 1 mm trim re-opens hub placement; ADR-030 gate must be re-run against 102 × 102 mm |
| `tests_after` | `549 passed, 37 skipped, 1 failed` → the single failure `tests/test_board_lock.py::test_lock_status` is the anticipated 10 s-timeout contention flake; **re-run of that file: 2 passed, 6 skipped**. No regression. |

## Verified task claims

| claim | verdict | evidence |
|---|---|---|
| 89/100/101/102 × (same) → $8.00 | CONFIRMED | `b_89_4L_16`, `g_89_4L_16_repeat`, `b_100_4L_16`, `b_101_4L_16`, `g_102_4L_16`, `res_102_4L_16` |
| 102.5 → $31.50; 102.9, 103 → $31.60 | CONFIRMED | `g_102p5_4L_16`, `g_102p9_4L_16`, `b_103_4L_16` |
| $25 Engineering-fee line absent (null) in the cheap class IS the mechanism | CONFIRMED | cheap class = single "Special Offer" line; expensive = Engineering fee + Board; both reconcile exactly |
| Repeats confirm (103 ×3, 89 ×2) | CONFIRMED (+1: 103 now ×4) | §6 of the analysis doc |
| Boundary driver = LARGEST SINGLE DIMENSION, not area/perimeter | CONFIRMED | `100x104` (area 10400 < 102x102's 10404) expensive; same-perimeter 100x104 vs 102x102 split; `50x103` expensive |
| Mechanism is NOT documented vendor policy | CONFIRMED | page documents no 102/102.5 mm rule; recorded as empirical |
| Thickness/finish confound unresolved | CONFIRMED | 89×89 4L: 0.8 mm $13.20 (LeadFree HASL) vs 1.6 mm $8.00 (HASL-with-lead) |

## Push verification

| remote | command | sha |
|---|---|---|
| local | `git rev-parse HEAD` | _(filled after push)_ |
| github (FIRST) | `git ls-remote github refs/heads/docs/jlcpcb-pricing-and-outline-decision` | _(filled after push)_ |
| ngit (SEPARATELY) | `git ls-remote ngit refs/heads/docs/jlcpcb-pricing-and-outline-decision` | _(filled after push)_ |

## Notes / deviations

- `docs/analysis/jlcpcb-quote-2026-10/` holds **salvaged raw evidence**, committed for durability.
  The docs read those JSONs; they did **not** re-drive the timed-out worker's browser. The four
  `res_*` configs were produced 2026-10-08 (fresh loads) to close the residual.
- A sibling remote branch `analysis/jlcpcb-size-tier-quote-salvage` carries a differently-scoped
  analysis of the same run (no raw JSON committed, no ADR, outline choice left open). Noted in the
  analysis doc §13 so the two are not confused.
- `AGENTS.md` was **not** touched.
