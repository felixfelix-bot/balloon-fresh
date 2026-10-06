# REPORT

Task t_f77dbc2d completed in `/home/c03rad0r/worktrees/powerbudget`.

- Added `docs/POWER-BUDGET-V9-D2BE.md` with a four-radio rail table, explicit TX duty cycles, valid and invalid simultaneous-TX cases, 5 V/3.3 V peak and average loads, and 1 F supercap energy calculations.
- Updated ADR-029 O5: 5 V is BLOCKED pending measured regulator/load-step and cold supercap evidence; retain only as selectable schematic option.
- Representative budget: 162 mA at 5 V plus ~102 mA at 3.3 V; approximately 1.38 W input with allowance.
- Valid instantaneous peak: 0.92 A at 5 V and 0.337 A at 3.3 V; invalid simultaneous dual-F33 case is explicitly called out.
- 1 F cap useful ideal energy from 5.5 V to 5.0 V is 2.625 J; cold/ESR derating makes the 0.35 s worst-case hold-up optimistic.
- Verification: `git diff --check` and content assertions passed.
- Commit `ca74024` was pushed to both GitHub `origin/pr/029-dual-band-flight-board` (before ngit rebase) and ngit `pr/029-dual-band-flight-board` (after reconciling remote tip). The final commit is observable on ngit; GitHub contains the equivalent commit content at its pushed tip.
- No firmware build applies: this is a documentation/engineering-budget deliverable.
