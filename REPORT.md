# REPORT — wing electrical consultant analysis

**Deliverable:** `docs/analysis/wing-electrical.md` — CONSULTANT ANALYSIS (not a decision record).
**Branch:** `analysis/wing-electrical` (worktree `/home/c03rad0r/worktrees/bf-winge`, base `76dd04d`).
**Date:** 2026-10-07.

## Headline findings (each with arithmetic in the analysis)

1. **Series mismatch destroys the large cell.** One large (1.2 A) in series with one small
   (0.4 A) is limited to 0.4 A: **0.40 W of the large cell's 0.60 W is discarded = 66.7 %**.
   The mismatched pair (0.40 W) is *worse than the large cell alone* (0.60 W).

2. **3 smalls in parallel = 1 large (0.4 A × 3 = 1.2 A).** Accepted tolerance **±10 %** on the
   summed group current (a −10 % group costs 10 % of the string's power).

3. **Bigger cells do NOT change the voltage premise.** Cell voltage is ~0.5 V for both sizes,
   so **any 12-cell series arrangement is still the 6.0 V nominal** the accepted records
   assume. What changes is current, diode ratings and wing geometry.

4. **The wing outline is a consequence of the cell size.** A 78.55 × 38.90 mm large cell
   **cannot fit the 176 × 25 mm wing** in either orientation. Only-large needs a
   **~256 × 45 mm (~115 cm²)** wing; matched-small (9 cells) needs **~176 × 65 mm (~114 cm²)**.

5. **Per-joint, the large cell wins 2.5×.** 1.80 W/wing from 3 large cells / 8 joints
   (0.225 W/joint) vs 1.80 W/wing from 9 small cells / 20 joints (0.090 W/joint).

6. **The ADR-046/048 DNP bypass is under-rated.** "BAT54 family" = 200 mA / 30 V, but the
   accepted array already needs 400 mA (2×) and a large-cell array needs 1.2 A (6×).
   Specify **≥ 2 A / 40 V** (SS24 / PMEG4020ER); **per-cell** bypass once any position is
   paralleled.

7. **The 12-cell array can over-voltage the bank and the radio.** Cold (−60 °C) open-circuit
   ≈ **9.3 V** vs the bank's 5.4 V and the radio's 5.5 V, with **no limiter** in the accepted
   design. No series count both charges to 5.4 V and stays under 5.5 V cold → a **shunt
   clamp is required**, sized to sink **up to 1.2 A at 5.5 V (6.6 W)**.

8. **Conductors:** the **4.0 × 1.2 mm tab lands are adequate** (≈2.7 A at 1 oz / 10 °C vs a
   1.2 A max) and need not change; the **un-specified on-wing interconnect is the risk** — a
   0.2 mm track carries only 0.74 A, so a large-cell build needs **≥ 0.5 mm**.

## Top-line recommendation

**Do not mix cell sizes — neither in a series string nor across wings. Pick ONE size class
per build.** Both choices preserve the 6.0 V / 12-cell series arrangement, but **both force a
new wing outline** (the large cell does not fit the current 176 × 25 mm wing at all). Then
**re-rate the bypass diode to ≥ 2 A / 40 V**, add **per-cell bypass if any position is
paralleled**, and add a **shunt clamp at the raw supercap node** (the array's cold Voc,
≈9.3 V, otherwise over-volts both the bank and the radio). The tab lands and (for the 0.4 A
array) the on-wing tracks are fine as they stand.

## Status

- Analysis written and self-checked: all arithmetic re-computed in Python before the doc was
  written; every number in `docs/analysis/wing-electrical.md` is computed with its formula
  shown or cited to an in-repo source; 8 explicit `TODO(unverified)` items listed (§9).
- Nothing in this work is a decision record; it does not edit any ADR, schematic or board.
- HONESTY: no number, commit or push in this report is claimed that was not observed.
