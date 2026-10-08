# PROGRESS — RF gaps cluster (433↔2.4 GHz harmonics, 2.4 GHz reflector budget, masthead LNA)

Branch: `design/rf-gaps-harmonics-diy` (base `github/main` @ `09e1b69`)
Worktree: `/home/c03rad0r/worktrees/bf-rfgaps`

## Milestones

- [x] **M1 — worktree + source read-in.** Worktree created; read (did NOT re-derive)
      `design/ground-station-lowpower-link` `4b90be942ce7`, `design/ground-station-flrc-max`
      `4ecbf5ca`, `design/positioner-lowcost` `b74bf5f6`, `design/ground-station-bom` `283cad72`,
      `design/gain-per-dollar` `f0f1e08a`, `design/amplifier-hypothesis-check` `148578c3`,
      `design/adr-set-groundstation` `c07bd868` (ADRs 071–082), and
      `design/gain-per-dollar-cliff` §8.2 (sweet spot (b)).
- [x] **M2 — model + analysis doc, committed + pushed EARLY.** `docs/analysis/rf_gaps_model.py`
      (Parts A–C, no deps) + `docs/analysis/rf-harmonics-and-diy-dish.md`. Committed and pushed to
      **github**, then **ngit** (separately). *(born of the predecessor's max_iterations death:
      write and commit early.)*
- [x] **M3 — Part B figure.** `docs/analysis/render_rf_gaps_figure.py` → SVG (+ PNG) of the Ruze
      curve with the budget lines and the DIY methods marked; geometrically verified via SVG text
      parsing (0 label collisions, 0 out-of-bounds text).
- [x] **M4 — consultant on the Part B figure.** `visual_consult.py --timeout 900`; served model
      `gpt-6-astra`; **`VERDICT: CONFIRM`**. Round 1 caught a real threshold bug (3.30/4.67 mm →
      3.37/4.77 mm), fixed; round 2 CONFIRMED the corrected figure.
- [x] **M5 — ADR-083** (Part B changes the reflector recommendation → ADR written; number 083
      verified free against every `github/*` branch). `docs/adr/INDEX.md` regenerated.
- [x] **M6 — PROGRESS.md + REPORT.md**, final dual push, remote verification.

## Findings in one line each

- **A** — No harmonic / subharmonic / LO-harmonic / 2nd-3rd-order IM product of {433.05–434.79 MHz}
  and {2400–2483.5 MHz} lands in the other band. Non-issue; the only coupling is the station's own
  2.4 GHz TX leaking into its own 433 RX (56–76 dB below the LNA P1dB), handled by the ADR-072
  ≥20 dB 433 BPF. **ADR-072 unchanged** (only the ≥20 dB number added).
- **B** — 2.4 GHz needs RMS ≤ 3.37 mm (<0.5 dB) / ≤ 4.77 mm (<1 dB) by Ruze (λ/10 = 12.49 mm is a
  6.86 dB tolerance). Hand-built reflectors are accurate enough but not cheaper than €94.90; the
  **feed+clamp are 74 %** of the €360.90 assembly. A **used production Ku dish (~€50 ESTIMATE)**
  beats the commercial dish. → **ADR-083**.
- **C** — Masthead LNA is mandatory: shack-end costs **1.2 dB @433/15 m**, **2.5 dB @2.4 GHz/15 m
  Ecoflex 15**, **4.9 dB @2.4 GHz/15 m Aircell 7** — 20–50 % of the LNA's +9.7 dB benefit.
  Confirms ADR-079 D1.

## Deliverables

| file | status |
|---|---|
| `docs/analysis/rf-harmonics-and-diy-dish.md` | done (Parts A–C, verdicts) |
| `docs/analysis/rf_gaps_model.py` | done (reproduce all three parts) |
| `docs/analysis/render_rf_gaps_figure.py` | done |
| `docs/analysis/assets/rf-gaps/ruze-2g4-surface-error.svg` / `.png` | done |
| `docs/analysis/assets/rf-gaps/consult-verdict.txt` | done (verbatim, both rounds) |
| `docs/adr/083-2g4-reflector-production-ku-offset-dish.md` | done |
| `docs/adr/INDEX.md` | regenerated |
| `REPORT.md` | done (gitignored; `git add -f`) |

## Numbers provenance

- Band edges: LPD433 (en.wikipedia.org/wiki/LPD433) ; 2.4 GHz ISM 2400–2483.5 MHz
  (en.wikipedia.org/wiki/List_of_WLAN_channels, quoting ISED RSS-247).
- Ruze: `685.81 (ε/λ)²` dB (en.wikipedia.org/wiki/Ruze%27s_equation).
- Coax: Kabel-Kusch Ecoflex 15 (432 → 6.10, 2400 → 16.20 dB/100 m) and Airborne 10
  (430 → 7.60, 2400 → 19.20 dB/100 m) — both re-fetched live 2026-10-08.
- LNA TQP3M9037 gain 20 dB / NF 0.4 dB: ADR-079 captured; vendor page HTTP **429** →
  `TODO(unverified)`.
