# HUMAN MEASUREMENTS TODO — blocks the altitude decision

**Owner:** Felix (operator) · **Status:** M1 + M2 **MEASURED 2026-10-14** · M3 still pending ·
**Chaser:** cron job `balloon-human-measurements-nudge` (every 2 days, 10:00)

**M1 (envelope) and M2 (solar cells) are now measured** — see the tables below and
`docs/analysis/MEASURED-MASSES-2026-10-14.md` for the raw readings and the reproduction script.
**M3 (a real 36″ latex balloon) is still outstanding**; it is the one that decides latex vs
superpressure, so it remains the blocker on that decision.

The original brief: three physical measurements **cannot be retrieved from the internet**. I
checked the manufacturer page and the distributors; the masses are not published anywhere. They
decide the achievable float altitude, so the flight plan is blocked on them.

| # | Item | Why it matters | Value |
|---|---|---|---|
| **M1** | Empty balloon mass (as-shipped, the one to fly) | Envelope mass is subtracted from available lift; it dominates the budget (community: 41–49 g vs a 9–22 g payload) | **✅ 46.84 g** (2026-10-14) |
| **M2** | One 52×19 mm solar cell mass | Array mass = cell mass × count; `wing_mass_model.py` assumes **1.5 g**; earlier budgets assumed 0.8 g — the spread is 6→12 g for 8 cells | **✅ measured, both sizes** (2026-10-14) |
| **M3** | One latex balloon mass, as-flown | Decides float altitude. The "36 in ≈ 25 g" figure was a **model assumption, not a real envelope** — the real 36 in products measure **33–46 g** | _pending_ |

### M1 — measured 46.84 g

Yokohama envelope, as-shipped. Sits **between** the two community figures for this envelope
(41 g old valved / 48.6 g new valveless) and **1.76 g below** the valveless value the mass budget
was using. Use the measured number for the envelope in hand.

### M2 — measured, and it corrects a 2× error

Two sizes were weighed, each as a 10-pack and as a single part:

| Size | 10-pack | single | mean | repo outline | areal |
|---|---|---|---|---|---|
| large | 14.04 g | 1.382 g | **1.4040 g** | 78.55 × 38.90 mm | 45.95 mg/cm² |
| small | 4.462 g | 0.440 g | **0.4462 g** | 52.07 × 19.65 mm | 43.61 mg/cm² |

- Against `wing_mass_model.py`'s **1.5 g** assumption: **−0.096 g/cell (−6.4 %)** — the model is
  close but slightly heavy.
- Against the earlier **0.8 g** budget figure: **+0.604 g/cell (+75.5 %)** — **the 0.8 g figure is
  refuted by measurement**; it is 1.76× light for the large cell.
- The two sizes differ 3.15× in mass but only **5.4 % in areal density**, identifying them as one
  cell technology in two cut sizes (see the reproduction script).

Array consequence: **12 large cells = 16.85 g**, **36 small cells = 16.06 g** — within 0.8 g of
each other, so the count decision is a *joints* decision (36 vs 108 hand-soldered joints), not a
mass one. Both are **far above** the 1.6 g a 4-cell array is carried at in
`PAYLOAD-WEIGHT-ESTIMATES.md`.

> The original "0.7 g error × 12 cells ≈ 8.4 g, ~1 km of altitude" concern was of the right
> magnitude: the real error against the 0.8 g figure is **0.604 g/cell × 12 = 7.25 g**.


## What each number changes

- **M1** — sets the envelope's own weight in the lift equation. A 20 g error
  moves the float ceiling by roughly a kilometre.
- **M2** — a 0.7 g error × 12 cells ≈ **8.4 g**, i.e. ~1 km of altitude.
- **M3** — this is the number that decides latex vs superpressure. If a real
  36 in latex balloon is ~40 g rather than ~25 g, the latex route loses most of
  its advantage over the nylon/PE laminate from Yokohama.

## How to measure

Kitchen/postal scale, 0.1 g resolution ideally (0.5 g acceptable — the errors
above are all ≥ 0.5 g). Weigh **as-flown**: cut the neck tie, weigh the balloon
alone, weigh one cell with its interconnect, and the latex balloon uninflated.

Record each as a line: `M1 <grams>` — e.g. `M1 47.3`. Send it in the balloon
group and the numbers get folded into
`docs/analysis/wing_mass_model.py` + `ALTITUDE-AND-MASS-REQUIREMENTS.md`.

## Why the model cannot substitute

The repo's own envelope survey says the community's proven long-duration payload
band is **9–22 g** and that the envelope is counted **separately at ~41–49 g**.
Both are *measured* figures from named operators. Any flight plan built on an
assumed envelope mass is a plan built on a guess, and the whole point of the
altitude analysis is to stop guessing.
