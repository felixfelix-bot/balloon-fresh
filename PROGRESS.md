# PROGRESS — cluster: FLRC-max 433 MHz downlink trade (branch design/ground-station-flrc-max)

Task: 433 downlink FIXED on FLRC at max throughput (LoRa rejected). Compute the
balloon-TX-power vs ground-dish-size trade, mesh viability, rate adaptation,
source the real parts, deliver a cited doc + ADR + consultant verdict.

## Milestones
- [x] M0 read prior art (branch design/ground-station-lowpower-link @4b90be94,
      branch design/ground-station-bom @283cad72) — not re-derived.
- [x] M1 worktree /home/c03rad0r/worktrees/bf-flrc off github/main 09e1b69.
- [x] M2 model docs/analysis/ground_station_flrc_max_model.py (trade table,
      rate-vs-range, mesh wind) — runs, prints every table.
- [ ] M3 doc docs/analysis/ground-station-flrc-max-throughput.md (first commit).
- [ ] M4 external sourcing (mesh materials, SPID rating, F33 cost) + BOM additions.
- [ ] M5 consultant verdict (verbatim + served model).
- [ ] M6 ADR-067 (supersedes ADR-066).
- [ ] M7 REPORT.md + DONE.

## Notes
- ADR number: scripts/adr_next_number.py returns 66 on this branch, but 066 is
  TAKEN on the pushed branch design/ground-station-lowpower-link (commit
  4b90be94) => 067 is the genuinely free number. Will document that.
