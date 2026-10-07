# REPORT — ADR-042 thermal / frequency-drift strategy

## Outcome

Wrote ADR-042 settling the operator's board-heater question: **reject the board heater**
with shown arithmetic against ADR-006/036, ranked the alternatives, named the deciding
number, and recorded the MS5611 self-heating conflict.

- **ADR number:** 042 (036–038 taken on concurrent branches; 039–041 being written
  concurrently; no `042-*` file found on any inspected branch).
- **New file:** `docs/adr/042-thermal-drift-strategy.md`.
- **Heater rejection arithmetic (verified):**
  - `R_thermal ≈ 100 K/W` (marked `TODO(unverified)`); 10 K lift ≈ 100 mW continuous.
  - 55 K lift (-55 °C → 0 °C) ≈ 0.55 W continuous.
  - 0.5 W × 10 h = 18 kJ; `C = 2E/V² ≈ 1235 F` at 5.4 V, vs the fitted 1.65 F (≈750× shortfall).
  - 1 mW heating buys only 0.1 K at 100 K/W.
- **Alternatives ranked:** (1) TCXO stability (F33-2G4 0.5 ppm TCXO or external TCXO), (2)
  firmware f(T) pre-distortion with a concrete cryo-bath protocol and pass/fail criterion,
  (3) wider bandwidth / channel plan.
- **Deciding number:** carrier-offset tolerance vs actual drift — recorded as
  `UNVERIFIED` and named as the gate that decides whether any mitigation is needed.
- **Conflict recorded:** deliberate board heating biases the MS5611/MS5607 pressure
  measurement and corrupts altitude telemetry; thermal management and pressure sensing
  conflict directly.
- **Standing ADRs not edited:** ADR-006, ADR-036, ADR-029 left untouched; relationships
  stated inside ADR-042, with a note that other workers are adding pointers there.

## Working notes

- Worktree `/home/c03rad0r/worktrees/bf-adr-thermal`, branch `adr/thermal-drift-strategy`,
  base `af6f806` (`master`).
- Documentation only; no schematic/placement/routing work.
- All numbers are either computed with units shown, cited to repo documents, or marked
  `TODO(unverified)`.
- No absolute `/home/` paths in committed files.

## Verification of refs after push

(To be filled after sequential push to github, ngit, origin.)
