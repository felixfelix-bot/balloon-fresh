# REPORT — design/gain-per-dollar-cliff

**Task:** find and quantify the cost cliff in the balloon ground-station gain-per-dollar
curve; evaluate every lever that raises performance without crossing it (mesh, stow + latch,
counterweight, and **especially Yagi arrays at 433 MHz**); define **two** sweet spots
(most-accessible and best-bang-for-buck); determine whether the low-power-board experiment can
be run with the cheap ground station by **measuring rather than buying**; produce a full
bottom-up **Tier-B cost**; deliver a doc with figures + a **free-numbered ADR** + an
**independent consultant verdict recorded verbatim with the served model named**.

**Base:** `github/main` @ `09e1b69`. **Branch:** `design/gain-per-dollar-cliff`.
**Worktree:** `/home/c03rad0r/worktrees/bf-cliff`.

---

## 1. Deliverables

| Artifact | Path | State |
|---|---|---|
| Analysis doc | `docs/analysis/gain-per-dollar-cliff.md` | written (~1 000 lines), pushed to github + ngit |
| Model (repro of every table) | `docs/analysis/gain_per_dollar_cliff_model.py` | runs clean, 520 lines of output |
| Figure renderer | `docs/analysis/render_gain_per_dollar_cliff_figures.py` | 3 PNGs rendered |
| Figures | `docs/analysis/assets/gain-per-dollar/fig{1,2,3}-*.png` | committed |
| ADR | `docs/adr/068-ground-station-antenna-class-cliff.md` | **number verified free on all github+ngit branches**; Status **Proposed** |
| ADR index | `docs/adr/INDEX.md` | regenerated; `tests/test_adr_numbering.py` **3 passed** |
| Progress | `PROGRESS.md` | per-cluster milestones (gitignored, `-f` on branch) |
| This report | `REPORT.md` | gitignored, `-f` on branch |
| Consultant verdict | doc §14 | see §5 below |

## 2. What was found

**The cliff is real, quantified, and mostly a ROTATOR-CLASS step.**
- Scaling exponents **VERIFIED** (log-log, R²=1.000): wind **force D^2.000**, wind **moment
  D^3.000**, dish area D^2.000, mass **D^1.80** (vendor mesh-kit masses), HPBW **D^-1.000**.
  The committed positioner torque chain reproduces the same **2.997** D-exponent.
- Whole-station marginal cost of the next dB: **~50–86 EUR/dB** up to a ~1.0 m dish, then
  **592 EUR/dB** across the 1.00 → 1.20 m step — **6.9×**. Of the EUR 938 paid for 1.58 dB,
  **EUR 773 is the rotator class step** (Yaesu G-450CDC EUR 359 → SPX-01 EUR 1132).
- Second, independent cliff: **pointing tolerance ~ 1/D vs constant backlash** — a 0.5°
  backlash consumes the 10 % HPBW budget at **2.4 GHz D = 1.75 m** (or **0.874 m** at 1.0°);
  at 433 MHz the equivalent is 4.85–9.69 m, so the 433 dish is **not** pointing-limited.
- Market gap: **AZ+EL** has no cheap rung between the Yaesu class (EUR 359–949, ≤1.0 m²) and
  EUR 1132; **AZ-only** DOES have one (G-1000DXC 2.2 m² EUR 529, G-2800DXC 3.0 m² EUR 1049),
  **so elevation is the gap**. Pairing the cheap AZ class with a real EL axis lands back on
  the cliff (G-1000DXC + RAEL = EUR 1254 ≈ SPID RAS EUR 1260.82). Verdict: **~40 % physics,
  ~60 % market structure.**
- Gap-fillers found: the **DIY mid-class rotator** (EUR ~300–450, committed "print structure,
  buy gearing"), and — established as a *class* but priced `TODO(unverified)` — the
  **DiSEqC/USALS single-motor satellite positioner** (polar-mount, cheap, but not a drop-in
  AZ+EL), plus **used/salvaged mounts** as the Tier-B fallback.

**The Yagi array IS the pre-cliff high-gain answer.**
- A **4-bay stack of Diamond A-430S15R Yagis** (14.8 dBi each, 4 × EUR 74.50 = EUR 298)
  reaches **20.0 dBi** versus the **+18.9 dBi** required for FLRC 2.6 Mbps at 650 km at the
  balloon's own +22 dBm → **+1.1 dB margin**.
- Its **effective drag area is 0.454 m² = 7.1 %** of a 2.6 m solid dish's 6.37 m² (worst-case
  2.5× sensitivity: 1.104 m² = 17.3 %, still inside the Yaesu tower class).
- It **fits the EUR 359 Yaesu G-450CDC at its mast rating** (0.454 ≤ 0.50 m²). The 2.6 m dish
  needs the **EUR 1775** SPID BIG-RAS.
- **On 433 gain-per-euro the 2.4 m and 2.6 m dish rungs are Pareto-dominated by the array**
  (the dish gives 18.8–19.6 dBi — *less* gain — at 4–5× the cost).
- Stated plainly what the array **cannot** do: CP polarisation on a tumbling payload, a
  narrow 2.4 GHz beam/sidelobe rejection, and **very high gain** — at +13 dBm, 2.6 Mbps needs
  **+27.9 dBi**, which **no** Yagi array reaches, so the dish is the only option there.

**Two sweet spots (both pre-cliff):**
| | (a) MOST ACCESSIBLE | (b) BEST BANG FOR BUCK |
|---|---|---|
| total installed | **≈ EUR 599** | **≈ EUR 2 166** |
| 433 gain | 13.1 dBi (1 Yagi) | 20.0 dBi (4-bay array) |
| closes | FLRC 650 kbps (+0.7 dB) | FLRC **2.6 Mbps** (+1.1 dB) |
| EUR/(bit/s) | €0.92 at 650 kbps | €0.83 at 2.6 Mbps |
| wind drag | 0.060 m² | 0.454 m² |

**Can the experiment be done cheaply? YES, for the decision.** A Tier-A Yagi station flies the
low-power LR2021 and **measures** the two currently-assumed numbers — the **433 MHz FLRC
sensitivity** (today a 915 MHz datasheet proxy) and the **path-loss exponent n** (today
assumed = 2.0 exactly) — plus the residual margin at the flown range. It **can** show the
dish's required gain is over-stated/un-needed at the operating range; it **cannot** retire the
dish by fiat, and a 50 km flight does not prove 650 km. In the **+13 dBm / 2.6 Mbps** regime
the dish is required regardless, and the campaign's job is then to *size* the dish.

**Tier-B bottom-up: EUR ~5 900 – 10 100.** Dominant line: the **SPID BIG-RAS rotator
(EUR 1775, 18–30 % of the total)**; second: **build labour** (EUR 1 000–2 000). Two sourcing
facts found this session: the **2.4 m / 3.0 m mesh dish kits are "Out of production"**, and
**RF Hamdesign has no 70 cm (433 MHz) dish feed** — the 433 feed is the least-sourced line.

## 3. New sourcing done this session (HTTP 200)

- RF Hamdesign **Oct-2026 price list PDF** (276 492 bytes) — SPID BIG-RAS EUR 1775.00, SPX-01
  EUR 1132.00, SPX-02 EUR 1249.00, SPID RAS EUR 1260.82, RAEL EUR 725.00, BIG-RAK EUR 1203.95,
  SPX-06 slew EUR 5487.35, **FPD-BR01 EUR 198.00**, **UA-02 EUR 624.36**, **PW32015 EUR 119.00**,
  4TH-LEG EUR 39.93, CLX1 EUR 46.00, LH-13XL EUR 220.00, CIR-902 EUR 336.38, FPQ RING23 EUR 194.00.
- funktechnik-bielefeld.de **Yaesu G-450CDC EUR 359.00** (`itemprop="price"`).
- metal-market.eu 25×25 mm / 1.75 mm welded mesh, made to measure, **"ab EUR 7,00"**.
- en.wikipedia.org/wiki/DiSEqC — the single-axis satellite-motor class.

## 4. Issues encountered

- `scripts/adr_next_number.py` is **branch-blind** (scans the working tree only) and printed
  **66** — which is **taken** (066 exists on a remote branch). Verified **068** free against
  all `github/*` **and** `ngit/*` branches; 067 is **doubly claimed**. Recorded in doc §12 and
  in the ADR's number-allocation note.
- `PROGRESS.md` **and** `REPORT.md` are both gitignored → committed with `git add -f` on the
  branch, as the brief anticipates.
- `matplotlib` is **absent from the default `python3`** but present in **`/usr/bin/python3`**;
  the figure renderer documents that.
- `vision_analyze` returned **HTTP 503** (flat router, glm-4.6v) on the first attempt — the
  known issue; figure legibility was therefore delegated to the consultant rather than
  self-checked by vision.
- A concurrent agent (`bf-amps`) was using the same `visual_consult.py` lane, which explains
  some lane contention.
- `git push ngit` was rejected once ("failed to push to any git server") and **succeeded on
  retry**.

## 5. Consultant verdict

Recorded **verbatim** in `docs/analysis/gain-per-dollar-cliff.md` §14, with the **served
model** named (read from `--json`'s `served` key, per the `visual-consultant` skill pitfalls
11 and the strict `visual_reviewer_model:` key). Refutations, if any, are recorded as results
in that section.

## 6. Push state

- **github FIRST, then ngit SEPARATELY, never `--atomic`, never main.** SHAs pasted in the
  final reply and in PROGRESS.md §M6.
