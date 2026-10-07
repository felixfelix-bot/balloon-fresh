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

## Amendment 2026-10-07 — datasheet correction (Addendum A)

The original ADR-042 was written from the repo's lesson file and got one premise wrong. A
datasheet-sourced **amendment** (a new `Addendum A` section; **no rewrite, no deletion**) was
added, and the affected sentence in §D3 step 6 was corrected. Every quote was verified with
`pdftotext -layout` against the in-tree datasheet
`docs/LR2021_LR2022_LR2012_Datasheet_Rev2.1.pdf` (branch `docs/lr2021-lessons`, commit
`581b38b`; Semtech *Final Datasheet Rev. 2.1*, `DS.LR20xx 13/04/26`, 243 pp), citing
chapter/table and quoting the line per point:

1. **CORRECTION — a runtime temperature sensor does exist.** `GetTemp` (`§6.5.2`, p.113;
   `Table 6-32`/`6-33`; `0x0125`) returns raw or °C, with `Source(1:0)` selecting die Vbe /
   die-close-to-XOSC / **NTC** / RFU, and `Format` selecting raw vs °C. The "if no runtime
   sensor exists / last known soak temperature" fallback in §D3 step 6 is **retracted**.
2. **The cheap hardware fix (new; ranked ABOVE the heater, alongside the TCXO):** the LR2021
   already contains the correct closed loop — an external **NTC on pin 3** measured against
   the XTAL, with on-chip compensation via **`SetTempCompCfg 0x0132`** (`§6.12.1`,
   `Table 6-69`), parameters via `SetNtcParams 0x0133`, mechanism in `§1.9.2` (p.32), pin
   description in `Table 2-1` (pin 3 = NTC). On our plain NiceRF module that pin is
   **unpopulated** (lesson line 22: "crystal, no TCXO, no NTC"), so the engine is idle.
   Fitting a **100 K NTC on pin 3** closes it for one component and a microwatt-scale bias,
   correcting the frequency instead of holding temperature — no continuous power, no awake
   MCU. Module-level details (exact placement, NTC bonding point, whether pin 3 is broken out
   on the NiceRF pads, series-R value) are **`TODO(unverified)`**, settled by the module
   mechanical drawing or a deshield photo.
3. **Why a board oven/heater still fails:** §D1's arithmetic is kept, joined by structural
   reasons — heat-only control needs a setpoint above the hottest ambient (up to ~80 K lift,
   sized against the 1.65 F bank); a control loop needs the MCU awake, contradicting
   ADR-036's mandatory night deep-sleep; the sensor/heater/plant path has an FR4 gradient, so
   the loop controls the wrong node; and the MS5611 conflict (§D6) stands.
4. **NEW CONSTRAINT — temperature-triggered recalibration:** the chip advises image
   calibration after a **temperature change > 10 °C**, and re-running PLL/AAF calibration
   beyond **±20 °C** (`§6.4` p.109, `§6.4.1` p.110). A launch-to-float swing far exceeds
   both, so firmware owes a sourced, temperature-triggered `Calibrate` (0x0122) cycle before
   the next flight-critical TX, triggered at runtime from `GetTemp`.
5. **Characterised window:** `FRTOLHF` = **±10 ppm over −20…+70 °C** (`Table 3-24`, p.68,
   `§3.5`). The −60 °C mission is **outside** it; the NTC loop and the TCXO are the two ways
   of dealing with it, and **neither gives a guaranteed ppm figure outside the characterised
   range** — no number is claimed there. (Supporting: `Tmr` −55…125 °C; `Top` ambient
   −40…85 °C; `Tmaxj` 105 °C.)
6. **ESP32 on-die sensor — log, don't tune:** `CONFIG_SOC_TEMP_SENSOR_SUPPORTED=y` in every
   `sdkconfig`, but `docs/data-handover/HARMONIZATION-GAP-ANALYSIS.md` row **N4** records no
   code reads/emits it. A free telemetry field, not a control input (wrong node).

**Ranking after the amendment:** (1) TCXO, (1b) 100 K NTC on pin 3, (2) firmware f(T)
pre-distortion, (3) wider channel plan. §D1's heater arithmetic is **unchanged and stands**.

## Working notes

- Worktree `/home/c03rad0r/worktrees/bf-adr-thermal`, branch `adr/thermal-drift-strategy`,
  base `af6f806` (`master`); amendment sits on **`5ce85e3`** (the commit it amends).
- Documentation only; no schematic/placement/routing work. Explicit `git add <path>` only —
  no `-A`, no `-a`. No force-push, no history rewrite; `5ce85e3` remains the parent.
- All numbers are either computed with units shown, cited to repo documents/datasheet, or
  marked `TODO(unverified)`.
- Branches owned by other workers (`docs/*`, `pr/*`, `fix/*`) were only read, never written.

## Verification of refs after push

Push order was **github → ngit → origin** (sequential; each verified before the next).

- Amendment commit: `7b0dcb9b423bf7faefba20214e8ef4e526a6b4d5` — parent
  `5ce85e3fc5008786077872031cd7e9040ccc748a` (`git merge-base --is-ancestor 5ce85e3 7b0dcb9`
  → true, so the amendment is a **fast-forward child of `5ce85e3`**).
- Report/close-out commit (this file): see commit list in `git log`; its parent is the
  amendment commit, so it too is a fast-forward descendant of `5ce85e3`.

`git ls-remote <remote> refs/heads/adr/thermal-drift-strategy` observed SHAs:

| Remote | Observed SHA | Note |
|--------|--------------|------|
| `github` | `7b0dcb9b423bf7faefba20214e8ef4e526a6b4d5` | push `5ce85e3..7b0dcb9`, exit 0 |
| `ngit`   | `7b0dcb9b423bf7faefba20214e8ef4e526a6b4d5` | push `5ce85e3..7b0dcb9`, exit 0; state event published to 1/2 relays (nos.lol failed) |
| `origin` | `7b0dcb9b423bf7faefba20214e8ef4e526a6b4d5` | "Everything up-to-date" (same GitHub URL as `github`), exit 0 |

Final-tip re-verification on all three remotes after the close-out commit is recorded in the
PROGRESS/commit log; refs match the local tip.
