# PROGRESS — ground-station amplifier-hypothesis check

Branch `design/amplifier-hypothesis-check` · worktree `/home/c03rad0r/worktrees/bf-ampcheck`
· base `09e1b69` (`github/main`) · cluster: ground-station / RF architecture.

> NOTE: `PROGRESS.md` and `REPORT.md` are **gitignored** in this repo
> (`.gitignore` lines 67–68, confirmed with `git check-ignore -v`). Per this task's
> instruction they are **force-added on this branch only** (`git add -f`).

## Milestones

| # | milestone | state |
|---|---|---|
| 1 | Worktree cut from `github/main` @ `09e1b69`; read the four prior branches (gain-per-dollar, flrc-max, bom, positioner-lowcost) + ADR-066/067/068 | DONE |
| 2 | Reproducible model written and run green (`docs/analysis/ground_station_amplifier_hypothesis_model.py`, exit 0, no `%%` leakage) | DONE |
| 3 | Analysis doc written + committed + pushed (`f17940e`) | DONE |
| 4 | Figure rendered (`docs/analysis/assets/amplifier-hypothesis-ebar.png`) | DONE |
| 5 | Visual consultant engaged with a 14-attempt background retry loop (HTTP 503 is routine) | RUNNING |
| 6 | ADR-070 (Proposed) + `docs/adr/INDEX.md` occupancy correction | DONE |
| 7 | REPORT.md + final reply | DONE |

## ADR numbering — the brief's own premise was wrong (recorded, not hidden)

The brief said *"066 and 067 are already claimed … 068 is likely next free."*
**Both halves are wrong.** Verified 2026-10-08 against **every** `github/*` branch:

* **066** claimed — `design/ground-station-lowpower-link`, `design/ground-station-flrc-max`
* **067** claimed **TWICE** — `design/ground-station-flrc-max`
  (`067-flrc-max-433-tx-power-and-coarse-mesh.md`) **and** `design/positioner-lowcost`
  (`067-positioner-architecture.md`) → a genuine **number collision**
* **068** claimed — `design/gain-per-dollar`, `design/gain-per-dollar-cliff`
* **069** claimed — `design/tier0-accessible`
* **070** verified free on every inspected branch → **used by ADR-070**

`scripts/adr_next_number.py` still returns **66**, so the script alone would have collided a
third time. The index's "next free" line is corrected in this branch.

## Findings that carry the deliverable

1. **Q1 premise WRONG** — the LNA buys **+6.8…+12.3 dB** of T_sys (central **+9.7 dB**);
   cold-sky directivity adds only **+3.80 dB** (433) / **1.5–2.8 dB** (2.4 GHz) *more*, and
   that part is directivity-only. Additive, not alternatives.
2. **Q2 DO NOT ARRAY** — 2-bay **76.13 €/dB**, 4-bay **93.73 €/dB**; Yagi **2–3 %**
   (9–13 MHz); beam narrows **10–32 %** (2-bay) / **33 %** (4-bay); real cost is the doubled
   wind moment. **The 433 LNA (433–435 MHz = 0.46 %) is NARROWER than the Yagi and sets the
   receive system bandwidth.**
3. **Q3 COVERAGE, NOT GAIN** — incoherent combining **+0.00 dB**; coherent and MRC
   **+10·log₁₀N** (+3.01/+6.02 dB) but both need phase coherence (MRC also N radios);
   multi-sector is the useful form.
4. **Q4 MANAGEABLE, NOT NEEDED** — +33 dBm on 12.4 dBi compresses the balloon RX inside
   **≈14.5 m**, hard-overloads inside **≈1.4 m**; ground-side AGC cannot help (wrong end).
5. **Q5 DO-NOT-BUILD** — owned 2.4 GHz amp+circulator are the wrong band; uplink already
   **+23.1…+36.1 dB** in surplus; a **~20 dB** circulator is insufficient isolation for a
   same-band +33 dBm front end.

Ledger: **F33 0.40 USD/dB ≪ 433 LNA 26.4 €/dB < 2-bay 76.1 < 4-bay 93.7 < dish 346–809;
2.4 GHz ground PA = INF (buys zero needed dB).**

## Sourcing (all fetched this session with a browser UA; search engines captcha-gated)

* **WiMo** (static prices in HTML): SSB LNA ISM 433 (20 dB / 0.7 dB / **€257**), RT-2400-2 T/R
  amp (13/14 dB, NF 3.2 / **€355**), DXpatrol 1 W (**€69**) and 12 W (**€185**) 2.4 GHz PAs,
  SHF adjustable-gain preamp (**€151.90**), SP-S VOX preamp (**€345**), 430 MHz 2000 W
  splitter (**€61.40**), phase line (**€63**), coax relays, attenuators.
* **Mini-Circuits datasheets** (PDF): ZX60-P103LN+ (Rev D), ZFL-1000LN+, DAT-31R5A-PN+,
  ZVE-8G+, ZHL-16W-43+. **Prices are AJAX-only → `TODO(unverified)`.**
* **Funktechnik Bielefeld**: Sirio WY 400-3N (published 65°/125° beamwidths), WY 400-10N,
  Diamond A-430S10R/S15R, FlexaYagi FX 7073.
* **Wikipedia REST** (full HTML): Antenna noise temperature, Noise figure, Friis formulas for
  noise, Yagi–Uda antenna, Phased array, Maximal-ratio combining, Diversity combining,
  Directivity, Circulator.
* **Blocked → no value invented:** DDG HTML (HTTP 202), fairviewmicrowave/everythingrf (404),
  kuhne-electronic.de / ssb-electronic.de (000), reichelt (404), Mini-Circuits price AJAX (empty).

## Carried-forward work for the next session

* `TODO(unverified)`: LR2021 NF + max input; 2.4 GHz circulator datasheet; Mini-Circuits
  prices; 10/15-el beamwidths; a 433 MHz phase-shifter product; a bare-MMIC LNA price.
* The **receive LNA is not in `ground_station_gain_per_dollar_model.py`** — adding it would let
  its €/dB be compared on the repo's M2 metric, not only on this document's dB ledger.
* ADR-039 open item (a) + `PAYLOAD-WEIGHT-ESTIMATES.md` §D still gate the F33 on the balloon.
