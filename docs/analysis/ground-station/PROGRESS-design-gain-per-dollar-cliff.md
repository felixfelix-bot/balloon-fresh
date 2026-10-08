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

### M2 — model + figures
`docs/analysis/gain_per_dollar_cliff_model.py` (520 lines of output) and
`render_gain_per_dollar_cliff_figures.py` → 3 PNGs. Exponents VERIFIED: wind force D^2.000,
wind MOMENT D^3.000, mass D^1.80, HPBW D^-1.000, torque chain reproduces the committed
model's 2.997. Cliff quantified: 86 EUR/dB -> 592 EUR/dB across the 1.00->1.20 m rotator
step (6.9x). Committed + pushed to github and ngit.

### M3 — doc + ADR-068
`docs/analysis/gain-per-dollar-cliff.md` (all four operator questions + Tier-B + measurement
campaign) and `docs/adr/068-ground-station-antenna-class-cliff.md`. `tests/test_adr_numbering.py`
green; `docs/adr/INDEX.md` regenerated.

### M4 — sourcing
Fetched THIS session (HTTP 200): RF Hamdesign Oct-2026 pricelist PDF (SPID BIG-RAS EUR 1775,
SPX-01 EUR 1132, RAS EUR 1260.82, RAEL EUR 725, FPD-BR01 EUR 198, UA-02 EUR 624.36,
PW32015 EUR 119, 4TH-LEG EUR 39.93, CLX1 EUR 46, LH-13XL EUR 220); funktechnik-bielefeld
Yaesu G-450CDC EUR 359.00; metal-market.eu 25x25 welded mesh "ab EUR 7,00"; Wikipedia DiSEqC
(single-axis satellite motor class). **Found: no 433 MHz dish feed in the RF Hamdesign
catalogue; the 2.4 m / 3.0 m mesh dish kits are "Out of production".**

### M5 — consultant (3 rounds, all served by `gpt-6-astra`, verdict QUALIFY each time)
R1: fig2 only → REFUTED that fig2 can carry the cost claim; flagged 0.454 m² = 91 % of the
    mast rating; flagged label crowding (matched my own bbox audit).
R2: fig1 (cost axis) + fixed fig2 → C1 "supported after correcting terminology"; required
    explicit design margin + rejection of the pessimistic 1.104 m² case.
R3: revised figs → points A/B/D/E RESOLVED; C "adequately disclosed but not technically
    closed" → added the §7.8 moment table + precondition list and DOWNGRADED §7.9 to a
    SCREENING result.
All three verdicts recorded VERBATIM in doc §14 with `served: gpt-6-astra` named; every
refutation accepted and acted on (§14.2).

### M5b — deterministic figure audit (no-vision fallback)
`vision_analyze` = HTTP 503, so figure legibility was audited mechanically (matplotlib window
extents: pairwise Text overlaps + edge clips). First render FAILED (4 overlaps in fig2, 1 in
fig3 — same crowding the consultant reported); after fixes all three figures are
overlaps NONE / clips NONE. Recorded in doc §13.1.

### M6 — REPORT.md + final push (github, then ngit): SHAs pasted.

