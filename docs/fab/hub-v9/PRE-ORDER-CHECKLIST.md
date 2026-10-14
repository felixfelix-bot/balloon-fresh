# HUB v9 — PRE-ORDER CHECKLIST

**Created:** 2026-10-14 · **Status:** not yet orderable — open blockers below
**Rule:** an order is placed by the operator (Felix) manually. The agent verifies
the packet and the price; it never places the order.

---

## A. BLOCKING — must be cleared before the order goes in

| # | Item | Why it blocks | State |
|---|------|---------------|-------|
| A1 | **Stackup: select 0.8 mm on the order form** | The board file said 0.6 mm, which **is not a JLC 4-layer option** (4-layer starts at 0.8). Gerbers do **not** carry thickness, so the form is the only place it can be set. | ⬜ OPEN — file fixed to 0.8, must be chosen at order time |
| A2 | **Re-price at 0.8 mm 4-layer** | The captured quote was a page default (~1.6 mm). Every total so far is a *lower bound* on the PCB line. | ⬜ OPEN |
| A3 | **Flight mass budget reconciled** | Payload ~57 g vs the stale `<14 g` doc. The 32-inch chloroprene sphere **cannot** reach 12 km at any payload — envelope decision pending (latex research in flight). | ⬜ OPEN — see `docs/analysis/ALTITUDE-AND-MASS-REQUIREMENTS.md` |
| A4 | **Per-placement assembly fee measured** | Only the $25/side setup fee is captured. Per-placement adds are unknown → all order totals are **lower bounds**. | ⬜ OPEN |
| A5 | **Envelope choice locked** | 32-inch chloroprene floats only 6.4–9.5 km. 36-inch latex (~25 g) modelled at 12–13 km. Literature check in progress. | ⬜ OPEN |
| A6 | **EN pull-up decided** | EN is **absent from the netlist** (no pull-up). Boot reliability depends on the module's internal EN pull-up — unverified. Either accept + verify on first article, or add R in rev-10. | ⬜ OPEN |

## B. ORDER-FORM SETTINGS (copy these exactly)

| Setting | Value | Source |
|---|---|---|
| Layers | 4 | board design |
| Thickness | **0.8 mm** | JLC 4-layer minimum (0.6 mm is 2-layer only) |
| Surface finish | ENIG | U.FL + fine pitch |
| Via treatment | **Epoxy filled & capped** | operator standing preference |
| Assembly | 1 variant, platform populated on all 10 | no baro; GPS as DNP rows + 4 loose |
| Quantity | 10 | order split locked (`a8c10205`) |
| Qty-10 note | ICs cliff at qty 10 (−$2.11/board) | measured |

## C. PACKET CONTENTS (verify the zip before uploading)

| # | Item | State |
|---|------|-------|
| C1 | Gerbers **re-exported at 0.8 mm** | ✅ `docs/fab/hub-v9/gerbers-0.8mm/` |
| C2 | Drill files in the same zip | ✅ (NPTH 2 hole types; PTH 153) |
| C3 | BOM: single-variant platform, GPS + baro as **DNP rows** | ✅ 2 DNP rows verified |
| C4 | CPL / positions matching the BOM | ✅ |
| C5 | GPS add-on line: **4× MAX-M10S loose** | ✅ separate CSV |
| C6 | Zip prepared for upload | ✅ `~/jlc-quote-inputs/hub_v9_0.8mm.zip` |

## D. KNOWN ACCEPTED RISKS (do not re-litigate; log them)

- **Cold:** all ICs are −40 °C rated; 7–9 km float ambient is ≈ −40…−50 °C (a 12 km float would be colder). Accepted, to be **measured** in flight via the NTC sense lines.
- **U.FL edge proximity:** all four connectors are **2.5 mm** pad-centre to edge. Not a fab problem; mitigations = right-angle pigtails zip-tied 10 mm from the connector, mate on the bare bench, 1 spare board per 10.
- **Wing tabs / 2 mounting holes:** both holes at **x = 9.425** → the board is pinned along one edge and the far half cantilevers. Mitigations = thread/kevlar through both holes + a third soft tie, epoxy-fillet the holes, soft washer.
- **Supercap DNP:** no buffer for TX bursts at dawn/dusk → cold-start untested (E-CS1…6 planned).
- **Night descent:** floats cool and drop; not yet characterised (E-06).

## E. BENCH MEASUREMENTS NEEDED FROM THE OPERATOR (with calipers / scale)

Not on the internet — these change the flight answer.

| # | What | Why it matters | Method | State |
|---|---|---|---|---|
| E1 | **Empty balloon mass** | Decides float altitude (±1.5 km between the 60 g and 100 g bounds) and whether chloroprene can work at all | lab scale, one balloon | ⬜ **NEEDED** |
| E2 | **One 52×19 mm solar cell mass** | 12 cells; 0.8 vs 1.6 g = 9.6 g swing, comparable to all hub components | lab scale | ⬜ **NEEDED** |
| E3 | **One latex balloon you intend to fly** (36 in / 40 in) | The 25 g @ 36 in figure is **modelled, not measured**; it sets float altitude directly | lab scale | ⬜ **NEEDED** |
| E4 | **Hub PCB thickness after receipt** | Confirms 0.8 mm actually shipped | calipers | ⬜ after delivery |
| E5 | **Wing PCB thickness after receipt** | 0.6 mm 2-layer is legal, but confirm | calipers | ⬜ after delivery |
| E6 | **Envelope inflated diameter** (the 32-in sphere often measures smaller) | Volume ∝ D³ — a 5 % diameter error is ~16 % volume | tape, on a filled envelope | ⬜ NEEDED |
| E7 | **Fill fraction that just floats the payload** | Gives the real free-lift margin | bench: fill, weigh net lift | ⬜ NEEDED |

## F. TOOLING EVIDENCE (added 2026-10-14)

- `docs/analysis/lr2021-bench-audit-2026-10-14.md` — LR2021 receive-only audit on real silicon
- `ansible/e80-lr2021-audit.yml` — provision a host to run the audits
- `make lr2021-audit` / `make lorawan-plan-audit` — reproducible runners

## G. ORDER-DAY PROCEDURE

1. Clear **every** A-item (or record an explicit operator waiver for it).
2. Verify the packet table (C) against the uploaded zip — hash the zip.
3. Set the order-form values (B) **by hand**; never accept a page default.
4. Read the price back and compare against the model; note any delta ≥ 5 %.
5. Place the order (operator only). Record the order number + the final price.
6. On delivery: run E4/E5, then the first-article bring-up (see `esp32-s3-flash-*`).
