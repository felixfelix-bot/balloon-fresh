# PROGRESS — design/gain-per-dollar-cliff

Task: find + quantify the cost cliff in the balloon ground-station gain-per-dollar curve;
evaluate every lever (mesh, stow+latch, counterweight, **Yagi arrays at 433**); define TWO
sweet spots; decide whether the low-power-board experiment can run on the cheap ground
station; full bottom-up Tier-B cost. Deliverable: `docs/analysis/gain-per-dollar-cliff.md`
+ ADR-**068** + consultant verdict (verbatim, model named).

Base: `github/main` @ `09e1b69`. Worktree `/home/c03rad0r/worktrees/bf-cliff`.

## Number hygiene
- ADR number: **068**. Verified free with `python3 scripts/adr_next_number.py --number 68`
  (exit 0) **and** a scan of `git ls-tree` on **every** `github/*` and `ngit/*` branch:
  066 = `066-ground-station-lowpower-shared-positioner.md` (taken),
  067 = `067-flrc-max-433-tx-power-and-coarse-mesh.md` **and** `067-positioner-architecture.md`
  (taken, twice). 068 appears nowhere. See `docs/analysis/gain-per-dollar-cliff.md` §12.

## Milestones
- [x] worktree on `design/gain-per-dollar-cliff` off `github/main` 09e1b69
- [x] read prior branches: positioner-lowcost, ground-station-flrc-max, ground-station-bom,
      ground-station-lowpower-link
- [x] PROGRESS.md written + first commit/push
- [ ] model script + figures
- [ ] doc
- [ ] ADR-068
- [ ] consultant verdict
- [ ] REPORT.md + final push (github, then ngit)

## Log

### M0 — setup
Worktree created; prior work read (BOM prices, positioner torque chain, FLRC dish-vs-power
table, mesh-vs-solid wind ratios, 433 FLRC sensitivity/required-gain table). Nothing re-derived.

### M1 — PROGRESS + early commit
Written before the analysis, per the brief (prior workers died on 503; write early).
