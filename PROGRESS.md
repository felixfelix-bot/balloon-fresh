# PROGRESS — ADR-040 (v9 dual radio-site optionality)

Worktree: `~/worktrees/adr040-radio-site`
Branch: `adr/v9-radio-site-optionality` (base `github/master` = `2de3fa6`)

## Done
- Read and reconciled against:
  - `docs/V9-DUAL-LR-DESIGN-MEMO.md` (docs/v9-dual-lr, ad3b8ad)
  - `docs/f33-module/F33-LANDPATTERN-VERIFICATION.md` (docs/f33-landpattern-verification, d983bab)
  - `docs/LR2021-LESSONS-2026-09.md` (docs/lr2021-lessons, 581b38b)
  - `docs/REGULATORY-AMATEUR-LICENCE.md` (docs/regulatory-amateur, 0f02f29d)
  - ADR-029/034/035/036/037/038 and the F33/SX1280 pin plan.
- Verified ADR number: 040 (038 highest committed; 039 concurrently written by another worker).
- Verified the "+120 mA per PLAIN module" ground truth from `docs/inventory.md` line 29 and
  `docs/DUAL-VARIANT-DESIGN.md` line 75 (NOT the memo's F33 +0.8/+0.9 A figure).
- Wrote `docs/adr/040-v9-radio-site-optionality.md` (ADR record).
- Wrote `docs/V9-RADIO-SITE-MATRIX.md` (per-config population/GPIO/rail/regulatory matrix).

## To do
- Commit ADR (concern a).
- Commit matrix (concern b).
- Push github → ngit → origin sequentially, verify each ref with `git ls-remote`.

## Not touched (scope guard)
- v8j MS5611 respin; docs/v9-dual-lr; docs/f33-landpattern-verification;
  docs/lr2021-lessons; docs/regulatory-amateur; docs/licence-exempt-design-point;
  fix/f33-landpattern-vendor; any other adr/* branch.
