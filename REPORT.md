# REPORT — Pico / small-balloon solar survey

**STATUS: CONSULTANT ANALYSIS — NOT A DECISION RECORD.**

- Deliverable: `docs/analysis/pico-balloon-solar-survey.md` (this branch)
- Branch: `analysis/pico-balloon-solar` · Worktree: `/home/c03rad0r/worktrees/bf-pico` · Base: `af9a672`
- Date: 2026-10-07

## What was asked

The operator challenged `docs/analysis/wing-literature-survey.md` because most of its mechanical
rigour (bond the cell to a vented substrate, Kapton laminate, via stitching >5/cm², chip budgets) came
from **CubeSat** teams whose vehicles are ~1.33 kg, while his payload is 20–40 g — mass 30–60× more
critical. He asked: **what do the pico-balloon people actually do?**

## Top 3 findings

1. **The pico-balloon world never bonds a bare cell to a vented rigid substrate — and the one builder
   who explains why cites thermal contraction, not vacuum.** John Ruthroff (KC9IKB), who flies 7–8
   bare 0.5 V polycrystalline cells: *"Some people glue their cells to the airframe. I don't do this
   because of the possibility that the temperature change between the assembly area and the cold at
   40,000 feet + may crack a cell. I just attach each end of the solar array to the airframe with
   epoxy, so the cells can 'float' and contract a certain amount."* Traquito sandwiches bare cells
   between two thin PCBs soldered through plated holes; NIBBB glues cell **corners** to a **foam
   disposable plate**. **No pico-balloon source in this survey uses a bonded + vented substrate.**

2. **The operator's bare cells win the mass trade by ~1.9× and should be kept.** Measured bare
   poly-Si = **0.400 W/g** (0.200 W ÷ 0.5006 g). Best flexible module found (PowerFilm MPT6-150,
   vendor spec) = **0.212 W/g** (0.600 W ÷ 2.83 g); the module the community actually recommends
   (MPT3.6-75) = **0.084 W/g**. Thin film *does* win on areal mass (17.0 vs 48.9 mg/cm²) but at
   **≈3.6 %** efficiency vs the bare cell's **≈19.6 %**, so switching the whole 7.2 W array to thin
   film would need 12 × MPT6-150 = **33.96 g and 1997 cm², 5.4× the area** — worse on both counts.
   The balloon-world mounting overhead is only **≈0.15 g/cell** (NIBBB: 7 bare cells, 4.5–4.7 g
   total), so there is almost nothing to save by changing the *structure*.

3. **The CubeSat void warning is a bad analogue for this flight, and the real pressure is higher than
   the earlier survey said.** Pico balloons float at 10–12 km = **19–26 kPa ≈ 0.19–0.26 atm** at
   **≈−50 to −56 °C** (US Standard Atmosphere), for **hours to ~305 days** — not the earlier survey's
   "0.05–0.1 atm" (that figure is 2–4× too low) and not a multi-year 10⁻⁶ Torr CubeSat vacuum
   (~1.4 × 10⁸× lower pressure). **No balloon-world evidence was found either way on void-cracking**,
   so the CubeSat conclusion is explicitly *not* borrowed.

## Recommendation (deciding number: 0.400 W/g vs 0.212 W/g)

Keep the bare cells; **do not bond them**. Mount them **end-only** on the spine-and-ribs frame (or a
thin two-PCB sandwich, Traquito style) so they can contract; add a **Schottky per parallel group**
(both NIBBB and KS4VA do this — `1N5817`; KS4VA: *"three SMD Schottky diodes … to 'steer' or isolate
the dark solar panels from the illuminated one"*). Use thin film **only where low sun angle or
handling robustness binds** — a **mixed** strategy on the NIBBB model (bare flat array in
spring/summer, thin-film low-angle prism in winter) — and note NIBBB's own numbers say its thin-film
low-sun array is **3–4× heavier** (`16.70 g` for `0.816 W` vs `4.6 g` for `1.4 W`).

**Not settled by evidence — needs his own bench test:** (a) W/g of his exact cell class in a flown
mount (NIBBB uses the same 52 × 19 mm AOSHIKE class but publishes no reconciled current); (b) whether
his hand-soldered joints survive −50 °C + launch (no balloon source has published this); (c) the
void-cracking question, if he still wants a bond; (d) real current at 5°/10°/15° sun elevation for the
winter launch.

## Evidence base

26 sources read and quoted (URLs + quotes in the survey). **First-hand build reports:**
Traquito (Solar System / PowerFilm / tracker), NIBBB (standard array, low-sun array, measured panel
specs, technical page), K9YO (K9YO group), John Ruthroff KC9IKB, K1FM, KS4VA (×2), missile.design,
AA0O, IEEE Spectrum, WB8ELK (nearspaceflights + HamSCI). **Vendor:** PowerFilm (×3 part pages), ZachTek
(product + blog), QRP Labs (U4B manual + product page), Project:Traveler. **Second-hand/reference:**
NPR, Hackaday, BCARC, Pico Balloon Archive, US Standard Atmosphere. **UNVERIFIED (not read, listed in
§8):** groups.io VE3KCL post (login wall), lora-aprs.org (bot wall), reverea.dev (stub), two Dropbox
links, two paywalled microcrack papers, one sbmicro PDF (body failed to extract).

Full text: **`docs/analysis/pico-balloon-solar-survey.md`**.
