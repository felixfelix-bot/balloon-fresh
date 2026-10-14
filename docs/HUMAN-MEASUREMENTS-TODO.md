# HUMAN MEASUREMENTS TODO — blocks the altitude decision

**Owner:** Felix (operator) · **Status:** not yet measured · **Chaser:** cron job
`balloon-human-measurements-nudge` (every 2 days, 10:00)

Three physical measurements **cannot be retrieved from the internet**. I checked
the manufacturer page and the distributors; the masses are not published
anywhere. They decide the achievable float altitude, so the flight plan is
blocked on them.

| # | Item | Why it matters | Value |
|---|---|---|---|
| **M1** | Empty balloon mass (as-shipped, the one to fly) | Envelope mass is subtracted from available lift; it dominates the budget (community: 41–49 g vs a 9–22 g payload) | _pending_ |
| **M2** | One 52×19 mm solar cell mass | Array mass = cell mass × count; `wing_mass_model.py` assumes **1.5 g**; earlier budgets assumed 0.8 g — the spread is 6→12 g for 8 cells | _pending_ |
| **M3** | One latex balloon mass, as-flown | Decides float altitude. The "36 in ≈ 25 g" figure was a **model assumption, not a real envelope** — the real 36 in products measure **33–46 g** | _pending_ |

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
