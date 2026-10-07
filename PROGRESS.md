# PROGRESS — adr/thermal-drift-strategy (ADR-042)

Base: `af6f806` (`master`). Branch: `adr/thermal-drift-strategy`. Documentation only.

## Steps

- [x] Read evidence: ADR-006 (`master`), ADR-036 (`adr/energy-policy`, commit `b304efd`), ADR-029 (`adr/radioband-tdm`, tip), `docs/LR2021-LESSONS-2026-09.md` (`docs/lr2021-lessons`, commit `581b38b`).
- [x] Verify 042 is free (no `042-*` file on any inspected branch; 036/038 exist on other branches, 039–041 claimed concurrently by other workers).
- [x] Create worktree `/home/c03rad0r/worktrees/bf-adr-thermal` from `master` and branch `adr/thermal-drift-strategy`.
- [x] Recompute the board-heater arithmetic with units and mark all unverified assumptions `TODO(unverified)`.
- [x] Write `docs/adr/042-thermal-drift-strategy.md`.
- [x] Write `REPORT.md` at worktree root.
- [x] Commit with explicit `git add <path>`. (Amendment commit `7b0dcb9`, parent `5ce85e3`.)
- [x] Push `github`, then `ngit`, then `origin` sequentially.
- [x] Verify each ref with `git ls-remote`, quoting observed SHAs. (All three = `7b0dcb9b423bf7faefba20214e8ef4e526a6b4d5`; `git merge-base --is-ancestor 5ce85e3 7b0dcb9` true → fast-forward child of `5ce85e3`.)
- [x] AMENDMENT 2026-10-07: datasheet correction — runtime sensor exists (`GetTemp`), 100 K NTC-on-pin-3 fix added (ranked alongside TCXO, above heater), >10 °C temperature-triggered recalibration requirement, ±10 ppm / −20…+70 °C window, ESP32 on-die sensor logged-not-tuned. All quotes verified with `pdftotext -layout` against `docs/LR2021_LR2022_LR2012_Datasheet_Rev2.1.pdf` (branch `docs/lr2021-lessons`). Heater arithmetic in §D1 unchanged.
