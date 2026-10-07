# REPORT — ADR-040 (v9 dual radio-site optionality)

## Outcome
Recorded ADR-040 (v9 dual radio-site optionality) and the per-config
population/GPIO/rail/regulatory matrix, reconciled against the existing v9 dual-LR memo,
on branch `adr/v9-radio-site-optionality` pushed to github + ngit + origin with each ref
verified.

## What was decided / recorded
- Two radio sites on the v9 board back: Site A = variant (LP-or-HP, mutually exclusive),
  Site B = LP-only; both DNP by default; operator hand-solders.
- Default population = LOW-POWER at both sites (the {LP+LP} config delivers ADR-034's
  simultaneous 433-TX/2.4-GHz-RX for ~+120 mA and +4 GPIO, no PA-table work).
- HP leg kept as an option for licensed operation / ground station (F33 0.5 ppm TCXO is the
  reason to want it at all).
- Explicit distinction: the memo's "mutually exclusive footprint" objection was to nesting
  for SIMULTANEOUS operation; the variant slot wants exactly that mutual exclusivity.
- Prerequisite P1 recorded as NOT done: F33 land pattern FAIL 0/18 pads (another worker is
  fixing it) — blocks all {HP}/{HP+LP} assembly.
- Per-config legal regime tabulated: HP leg is dead weight / not usable in the licence-exempt
  433.05–434.79 MHz regime, legal only under the DE amateur licence (with callsign, no
  encryption, secondary status, cross-border open).

## Files created
- `docs/adr/040-v9-radio-site-optionality.md` (ADR record)
- `docs/V9-RADIO-SITE-MATRIX.md` (per-config matrix)
- `PROGRESS.md`, `REPORT.md`

## Commits
- (a) ADR record
- (b) matrix

## Push verification
- github, ngit, origin refs verified with `git ls-remote` (SHAs quoted in commit trail).

## Unverified / TODO items recorded (not invented)
- Module mass (g), bare-module land pattern, exact F33 extra GPIO, feed/keep-out routing
  feasibility, Site A shared-VCC selection scheme, F33 5 V rail (open), plain crystal drift.
