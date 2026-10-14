# HUMAN MEASUREMENTS TODO — operator action required

**Created:** 2026-10-14 · **Owner:** Felix (needs scale + calipers)
**Why:** these three numbers change the flight answer and **cannot** be found
online (checked: the Yokohama product page, distributors, and the pico-balloon
community literature). Every altitude figure in `docs/analysis/` is bounded,
not measured, until they exist.

## Follow-up cadence

The agent will **follow up with the operator over the coming days** until these
are done — a scheduled nudge, not a one-off ask. Update the `State` column as
each is measured.

| # | Measurement | Method | Why it matters | State |
|---|-------------|--------|----------------|-------|
| M1 | **Empty balloon mass** — the 32-inch Yokohama sphere | lab/kitchen scale, one balloon, as delivered | Decides float altitude within a **1.5 km** band between the 60 g and 100 g bounds; decides whether chloroprene can work at all | NEEDED |
| M2 | **One solar cell mass** — 52 x 19 mm | scale, one cell | 12 cells; 0.8 g vs 1.6 g = a **9.6 g** swing, comparable to every component on the hub combined | NEEDED |
| M3 | **One latex balloon** you intend to fly (36" or 40") | scale, one balloon | The 25 g @ 36" figure is **modelled, not measured**; it sets the float altitude directly | NEEDED |

## Secondary (bench, when convenient)

| # | Measurement | Method | State |
|---|-------------|--------|-------|
| M4 | Envelope inflated diameter (the "32-inch" sphere often measures smaller) | tape measure on a filled envelope | optional |
| M5 | Fill fraction that just floats the payload | fill, hang, weigh net lift | optional |
| M6 | Hub PCB thickness on delivery | calipers | after delivery |
| M7 | Wing PCB thickness on delivery | calipers | after delivery |

## How the results are used

1. Update `docs/analysis/altitude_requirement.py` / `lift_budget_32in.py` with the
   measured masses and re-run — every float-altitude number is regenerated.
2. If M1 > ~80 g, treat the 32-inch chloroprene path as closed and lock a latex
   envelope (see the latex literature survey in `docs/analysis/`).
3. Record the result in this file (State column) and in the pre-order checklist
   item A3/A5.
