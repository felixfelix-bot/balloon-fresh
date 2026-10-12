# REPORT — Dualband single-dish analysis (design/dualband-single-dish)

Date: 2026-10-08. Worktree: `/home/c03rad0r/worktrees/bf-dualband`. Base: `09e1b69` (github/main tip at fetch).

## What was asked

Rigorously answer whether ONE Ku-band dish can serve BOTH the 2.4 GHz uplink and the 433 MHz downlink, with worked arithmetic; rank every way to make one dish work; fairly state the mechanical benefit the operator is right about; deliver a verdict or state what measurement closes it. Design only — nothing ordered. Branch touches `docs/**` only (plus gitignored PROGRESS.md/REPORT.md, force-added on this branch only).

## Deliverable

`docs/analysis/dualband-single-dish.md` (10 sections) + repro script `docs/analysis/dualband_dish_arithmetic.py` (repo convention: model scripts live in docs/analysis/, cf. `array_power_architecture_model.py`).

**ADR deliberately NOT written** — the decision is not genuinely reachable yet: the 433 MHz gain of any single-reflector option rests on an unverified ~10 dB feed-mismatch estimate. The analysis states exactly what measurement closes it (mount a candidate 433 feed near the focus and measure gain vs free space). ADR number **066** was allocated by `scripts/adr_next_number.py` but left unclaimed so it cannot collide. Verified: `docs/adr/INDEX.md` highest existing = 065; `git ls-remote github` shows no 066+ ADR file on any of the 23 `adr/*` branches (checked with `git ls-tree -r github/<branch> -- docs/adr`).

## Key results (all reproducible via the script)

1. **Ku dish at 2.4 GHz: SUITABLE, with ~5–12× surface margin.** λ/20 @ 2.4 GHz = 6.2 mm vs λ/20 @ 12 GHz = 1.25 mm. Ruze loss for σ = 1.0 mm RMS: 1.1 dB @ 12 GHz but only 0.044 dB @ 2.4 GHz. 0.9–1.2 m dishes give 24.9–27.4 dBi (η = 0.60) — above the 18 dBi the 2.4 GHz link budget assumes (`docs/2G4-LINK-BUDGET-ANALYSIS.md` §3.2).
2. **Ku dish at 433 MHz: too small.** D/λ = 1.7 at 1.2 m. Theoretical 12.5 dBi, but ~0.09 λ feed mismatch likely drags practical gain to 0–6 dBi. 20 dBi at 433 MHz needs D ≈ 2.7–3.0 m — not gimbal-portable.
3. **Two feeds near the focus: mechanically viable.** λ/4 defocus tolerance is 17.3 cm at 433 MHz vs 3.1 cm at 2.4 GHz. A 5 cm offset costs ~0.08 dB at 433 MHz (quadratic λ/4≈1 dB rule) and ≤1 dB at 2.4 GHz from blockage. Defocus is NOT the blocker; feed-pattern mismatch is.
4. **Options ranked:** (b) 433 Yagi boresighted on the dish structure — best RF (12 dBi at 433, 2.4 untouched, one positioner) > (a) two feeds near focus — best mechanical purity, poor 433 gain > (b′) Yagi beside the dish on the same positioner > (c) dual-band feed + diplexer (phase centre cannot coincide at both bands; ~1–2 dB 2.4 GHz compromise; 433 still pattern-limited) > (d) dichroic subreflector and (e) nested dishes — correct physics, wrong scale for a portable ground station.
5. **The earlier answer was too strong.** It was right that one reflector < two purpose-built antennas, but under-weighted the mechanical win of one pointing system (one az/el head, one coax run, no second steerable mount to build/align) and overstated the difficulty of two feeds near the focus. "Share the positioner, not the reflector" is the honest optimum.

## Verdict

Use the Ku dish for the 2.4 GHz uplink; strap a 7-element 433 MHz Yagi (~12 dBi) to the dish feed arm or the positioner head, boresighted with the dish. 433's ~40° beam means it stays pointed whenever the 2.4 GHz dish (7° beam) is on target.

## Unsourced / TODO(unverified)

Listed in doc §10: Ku-dish RMS surface accuracy (rule of thumb 0.3–1.0 mm), ~10 dB 433 feed-mismatch estimate, λ/4≈1 dB quadratic extrapolation, Yagi gain/beamwidth figures, offset-dish effective f/D (0.6–0.7).

## Process compliance

- Commits pushed after each milestone (github first, then ngit separately, no --atomic): dce58d5 (gain tables) → f5d3c20 (feed analysis) → 12f880d (ranking+verdict+script).
- `git ls-remote` verified on BOTH remotes after each push; local == github == ngit == 12f880d at completion.
- No flight-board files, no AGENTS.md writes, no orders, no band-plan re-litigation.
- Test suite: see final status in the parent summary (run under load ~20+).
