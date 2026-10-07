# REPORT — wing fabrication, hand-assembly and order-cost analysis

**Deliverable:** `docs/analysis/wing-fab-cost.md` (CONSULTANT ANALYSIS, not a decision record).
**Branch:** `analysis/wing-fab-cost`, base commit `76dd04d` (tip of `github/main`).
**Date:** 2026-10-07. **Lens:** manufacturability, hand-assembly effort, order cost.

## Top-line recommendation
Order **hub + ONE small-cell wing** — after the small cell's real pad geometry is measured.
Keep a **large-cell wing as a separate second design**; do **not** build a "universal" wing.
Carry **three cells per wing** (not 9 or 12): that is the minimum-joint build and the biggest
single lever on build risk.

## The numbers

### Joints (3 hand joints per one-pad-per-face cell; tab = 8 joints/wing; 4 wings/aircraft)
| Build | Cells/wing | J/wing | J/aircraft |
|---|---|---|---|
| (b) 3 SMALL in series | 3 | **9** | **36** |
| (a) 3 LARGE in series | 3 | **9** | **36** |
| (d1) mixed 1L+2S | 3 | 9 | 36 |
| (d2) mixed 1L+6S | 7 | 21 | 84 |
| (c9) 9 SMALL (3s×3p) | 9 | 27 | **108** |
| (c12) 12 SMALL (3s×4p) | 12 | 36 | **144** |

Per cell: **2 terminations, one per face → 3 joints** (1 direct + a 2-end **jumper**); **2 joints**
if the far pad is reached by an **edge wrap** or the cell arrives pre-tabbed. **A via cannot
substitute** — the pad is on the cell, not the board. **Joint count is the primary risk metric on
a hand-built vehicle.**

### FAB (JLCPCB) — LIVE, read 2026-10-07
- **Min outline 3 × 3 mm**; max 2-layer 670 × 600 mm, thinner-FR4 (<0.8 mm) 599 × 497 mm ⇒
  **a 250 mm wing is deep inside the envelope**; length is a *price class*, not a feasibility issue.
- **Min NON-plated slot = 1.0 mm** ⇒ **ADR-046's 0.9 mm slot is below the minimum** and its
  worst-case gap against a 0.6 mm tab is **0.00 mm** (COMPUTED) — a hub-side blocker.
- Plated 0.9 mm slot is inside the minimum (0.5 mm 2-layer) but is copper-lined ⇒ electrically wrong here.
- **Live quote for the repo's real wing gerber (25 × 184 mm, qty 5):**
  2-layer **$6.40** (Engineering $4.00 + Board $2.30 + Deburring $0.10);
  4-layer **$28.00** (Engineering $25.00 + Board $2.90 + Deburring $0.10) ⇒ **+$21.60 / ×4.4 step**.
  Thickness 0.6 mm = $0.00 delta. Page renders **`Calculated Price`** + **`Shipping Estimate`**
  (DHL Express DDP, 2–4 days, 0.20 kg). Order page has a **"Different Design: 1 2 3 4"** input.
- **Indicative only (un-isolated option states):** $22.98 (leftover Via Covering $16.58),
  $256.10, $289.18 (a `Panel $33.08` line), shipping $31.23.

### Order shape
| Shape | Designs | qty | Panelise? | Risk |
|---|---|---|---|---|
| (a) hub + 1 universal wing | 2 | 5+5 | marginal | HIGH (one land for two cells) |
| (b) hub + 2 wings | 3 | 5+5+5 | no | HIGHEST (two unmeasured lands) |
| (c) hub + 1 small wing | 2 | 5+5 | marginal | MEDIUM — **recommended first order** |
| (d) hub + 1 large wing | 2 | 5+5 | no | HIGH (unconfirmed pad + hub re-freeze) |

### Universal vs two dedicated
A universal board saves only the **≈$4 2-layer Engineering fee** (LIVE) and pays in bigger, more
crowded copper and the worst failure mode (a land right for neither cell). **Two dedicated designs
is the better value**; for the first order, one small-only design.

## Checklist highlights (⚠ = irreversible if wrong)
⚠ small cell contact geometry · ⚠ joint scheme (jumper vs wrap/tab) · ⚠ large cell pad layout ·
⚠ which cell size(s) and the outline(s) · ⚠ hub slot must be ≥1.0 mm non-plated ·
⚠ substrate thickness · ⚠ hub layer count (2L vs 4L) · re-run the order gate on the exact
board+fab pair before ordering.

## Provenance
Every figure is labelled **LIVE** (read from a live JLCPCB page this session), **COMPUTED**
(arithmetic shown), or **TODO(unverified)/ESTIMATE** (explicitly not verified). The 250 mm-outline
price, the isolated qty curve and the hub quote are **not** verified — the hub has no PCB to quote.

## Push verification (observed with `git ls-remote`)
Delivery commit (the analysis doc + PROGRESS/REPORT):
- **local  SHA: `52aa7b0345a41c000ed8b278560defa78e194f3e`**
- **github SHA: `52aa7b0345a41c000ed8b278560defa78e194f3e`** (`git ls-remote github refs/heads/analysis/wing-fab-cost`)
- **ngit   SHA: `52aa7b0345a41c000ed8b278560defa78e194f3e`** (`git ls-remote ngit refs/heads/analysis/wing-fab-cost`)

All three match. Pushed separately to `github` then `ngit` (`--no-verify`); no force-push.
`github refs/heads/main` still at `76dd04d88c4b14c2468c80d5e77cb921b1c356a0` — **main untouched**.
This REPORT.md records the SHAs of the preceding delivery commit; the branch tip is the
follow-up commit that added this section.
