# REPORT — RF gaps cluster: 433↔2.4 GHz harmonics, 2.4 GHz reflector surface budget, masthead LNA

- **Branch:** `design/rf-gaps-harmonics-diy` (base `github/main` @ `09e1b69`)
- **Worktree:** `/home/c03rad0r/worktrees/bf-rfgaps`
- **Deliverables:** `docs/analysis/rf-harmonics-and-diy-dish.md` (Parts A–C), `docs/analysis/rf_gaps_model.py`,
  `docs/analysis/render_rf_gaps_figure.py`, `docs/analysis/assets/rf-gaps/*`,
  `docs/adr/083-2g4-reflector-production-ku-offset-dish.md` + regenerated `docs/adr/INDEX.md`.

## What was asked vs what was built

Three genuinely-uncovered parts of a lost ground-station study, re-deriving none of the superseded
content (link budgets, dish-vs-Yagi, wind/torque, positioner ranking) — all cited from the landed
design branches.

**Part A — 433 ↔ 2.4 GHz harmonic / IM coexistence.** Built the full harmonic series of the
433.05–434.79 MHz TX and checked every n = 1…12 against 2400–2483.5 MHz, plus the reverse
(2.4 GHz harmonics and 1/n subharmonics vs 433), the RX LO harmonics, and 2nd/3rd-order IM products
of the two carriers. **Finding: no product lands in either band** — the nearest approach is the
433 6th harmonic (2598.30 MHz), 114.80 MHz above the 2.4 GHz band top. The only real coupling is
the station's own 2.4 GHz TX leaking into its own wideband 433 LNA (56 dB nominal / 76 dB
pessimistic below the LNA P1dB), handled by the ADR-072 ≥20 dB 433 BPF. **Verdict: non-issue
requiring a modest filter; ADR-072 is NOT changed** (only the ≥20 dB rejection number is added).

**Part B — 2.4 GHz reflector surface-accuracy budget + DIY viability.** Quantified with Ruze's
equation (`685.81 (ε/λ)²` dB, sourced): at 2.400 GHz (λ = 124.91 mm) **< 0.5 dB needs RMS ≤ 3.37 mm**
and **< 1 dB needs ≤ 4.77 mm**; λ/10 = 12.49 mm is a **6.86 dB** tolerance, not a budget. Scored
six construction methods (foil, tape, mesh, 3D-printed, fibreglass, used dish). **Finding: a
hand-built reflector is accurate enough but NOT cheaper** than the €94.90 Gibertini once a
former/rib set and labour are counted, and the **feed + clamp are 74 % of the €360.90 assembly**;
the one cost-beater is a **used production Ku offset dish (~€50 ESTIMATE)** — cheaper, more
accurate (~λ/100 margin) and usually larger. Because 2.4 GHz ground gain above ~8 dBi is inert
(ADR-081 D1), the reflector is bought for interference-rejection/polarisation, not dB.
**This changed the recommended reflector choice → ADR-083 written** (bought production Ku dish,
new or used; hand-built reflectors rejected).

**Part C — masthead vs shack-end LNA.** Friis cascade with real coax figures (Kabel-Kusch
Ecoflex 15 / Airborne 10 / Aircell 7, re-fetched live). **Finding: masthead is mandatory — the
shack-end penalty is 1.2 dB (433 MHz, 15 m Airborne 10), 2.5 dB (2.4 GHz, 15 m Ecoflex 15) and
4.9 dB (2.4 GHz, 15 m Aircell 7)**, i.e. **20–50 % of the LNA's whole +6.8…+12.3 dB (central
+9.7 dB) benefit**. Confirms ADR-079 D1's masthead placement with the missing numbers.

## Consultant (required for Part B)

- **Served model: `gpt-6-astra`** (read back from the response `model` field, not the alias sent).
- **Verdict of record: `VERDICT: CONFIRM`** (round 2, corrected figure). Verbatim round-1 and
  round-2 answers in `docs/analysis/assets/rf-gaps/consult-verdict.txt`.
- The **round-1 answer caught a real bug** — my Part-B thresholds had been typed from a 2.45 GHz run
  (3.30 / 4.67 mm) while the figure used the 2.400 GHz edge (3.37 / 4.77 mm). Fixed in the figure,
  the analysis doc and ADR-083; the figure now computes the thresholds from the model.
- The CLI's structured `verdict` field returned **`UNPARSED`** (the model said `CONFIRM`, outside
  the CLI's APPROVED/CHANGES_REQUESTED/PARTIAL vocabulary); per the `visual-consultant` skill only
  the model's explicit `VERDICT:` line counts.

## ADR number

`scripts/adr_next_number.py` printed **066** (branch-blind). Verified prefix-anchored against
**every `github/*` branch**: 066–070 claimed on sibling branches, **071–082 on
`design/adr-set-groundstation`**, nothing carries 083 → **took 083**. `docs/adr/INDEX.md` regenerated
mechanically.

## Honesty / open items

- `TODO(unverified)`: TQP3M9037 vendor gain/NF (vendor page HTTP **429**; values are ADR-079's
  captured figures, and the part's 433 MHz coverage is the inherited flagged defect D5).
- `TODO(unverified)`: used-Ku-dish price (~€50 ESTIMATE; eBay.de 403) and its measured RMS.
- Method RMS brackets are **ESTIMATEs** and labelled as such everywhere; only the Ruze curve and the
  budget thresholds are computed.
- The Part-B **citations to `docs/analysis/*` and `docs/adr/071–082`** live on sibling branches and
  are reachable at the listed SHAs, not on `main`.

## Pushes (github first, then ngit, separately)

```
$ git rev-parse HEAD
<see the final block below>
```
