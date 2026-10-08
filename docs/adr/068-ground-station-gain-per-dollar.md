# ADR-068 — Ground-station cost metric: price gain AND the rig in the same unit, and buy a Yagi before a dish

- **Status:** **Proposed** — the analysis is complete and cited; the *text* has not been
  accepted by a human.
- **Date:** 2026-10-08
- **Decision owner:** Felix (operator)
- **Author:** Hermes subagent (design analysis), per the operator's 2026-10-08 instruction to
  *"include the cost of the holding rig / antenna tracker in our link budget per dollar or
  gain per dollar calculation"* and to identify *"a path to getting maximum gain per dollar
  while keeping the costs low so that this project remains accessible for anyone to
  replicate."*
- **Related:** ADR-066 (ground station for the low-power LR2021 433 MHz downlink — share the
  positioner, not the reflector) on `design/ground-station-lowpower-link`; ADR-067
  (`positioner-architecture`) on `design/positioner-lowcost`; ADR-039 (licence-exempt 433
  design point); ADR-041 (RF front end); ADR-034 (433 TX / 2.4 GHz RX band split).
- **Companion evidence:** `docs/analysis/ground-station-gain-per-dollar.md` — the metric
  definition and rationale, the full candidate comparison (Tables A–D), the
  non-monotonicity analysis, the metal-fabrication research with URLs, the closed-loop
  answer, and the recommendation + choice table. Repro:
  `python3 docs/analysis/ground_station_gain_per_dollar_model.py` (prints every table
  verbatim); figure: `python3 docs/analysis/render_gain_per_dollar_figure.py`.
- **Consulted:** fleet visual consultant, served model **`gpt-6-astra`** — verdict and
  verbatim answer in the analysis §10. A visual consult is not a code review and does not
  satisfy the ADR-010 review gate.
- **Numbering note:** `scripts/adr_next_number.py` → `66`, but **`066` and `067` are taken on
  other branches** (`design/ground-station-lowpower-link` → `066-ground-station-lowpower-shared-positioner.md`;
  `design/positioner-lowcost` → `067-positioner-architecture.md`). `068` was verified free on
  every inspected remote branch before use, and `docs/adr/INDEX.md` was updated to record that
  `066`/`067` are occupied off-branch. Do not hand-pick a later number; re-run the script and
  re-check the branches.

---

## Context

The operator asked three cost questions that the prior analyses answered only in engineering
units, never in money:

1. *What is the maximum gain per dollar?*
2. *Can the whole rig be made of metal, and what would that cost?*
3. *Would a motor that knows its own position help against the wind?*

The prior art already established the engineering facts this decision rests on:

- The **433 downlink is the direction that sets ground gain**; the 2.4 GHz uplink needs
  **negative** required ground gain (−17.4 dBi at 300 km, −10.7 dBi at 650 km) and closes with
  an omni (`ground-station-lowpower-link-and-shared-dish.md` §0/§6; the positioner study §3.2).
- **LoRa closes everywhere; FLRC does not.** FLRC sensitivity is **≈36 dB worse** than LoRa at
  433 MHz (−107 dBm @ 650 kbps vs −143 dBm @ SF12/62.5 kHz), so the 433 antenna choice is
  driven entirely by FLRC. On the **low-power LR2021** at +22 dBm, FLRC at 650 km needs
  **+12.4 dBi** (650 kbps) to **+18.9 dBi** (2.6 Mbps) at zero margin — with a 6 dB operating
  margin, **+21 to +27.5 dBi**, i.e. a **3.0–3.5 m dish**.
- **Mesh is the enabler for a large 433 dish** (λ/10 = 69.2 mm): the mesh is electrically
  solid and cuts the wind moment to **0.50×** (2.40 m) / **0.97×** (3.00 m) of solid at
  120 km/h, against the SPID BIG-RAS's 2,712 N·m brake (`flrc-max` §4.1–§4.3).
- The **DIY printed tracker with a bought self-locking NMRV worm** is the cheap positioner
  (≈€279 mechanics + €50 controller + €100 mast), and **printed gears must not carry the hold
  torque**; **secondary (stow) and tertiary (topology/coupling) effects dominate the
  positioner's difficulty** (`positioner-lowcost` §5–§7, §10).

**What was missing, and is the substance of this ADR, is a single unit that prices gain
*and* the rig together, so that the operator can compare a Yagi, a 1.2 m dish and a 3.5 m
dish on the same axis.** The metric must include **antenna, feed, coax, the positioner or the
whole DIY tracker (motors, reducers, encoders, drivers, controller, anemometer), the
mast/structure and a construction allowance** — the operator's explicit requirement — because
the positioner, not the reflector, dominates the cost above ~1.5 m.

---

## Decision

**1. Adopt the metric `M2 = EUR_total / max over the rate ladder of (R · d_max(R))` — EUR per
(kbps·km) — as the primary ground-station cost metric, with `M1` (average EUR/dB) and `M1m`
(marginal EUR/dB) retained as *diagnostic* metrics and `M3` (EUR/km at a fixed rate) as the
range-first check. `EUR_total` MUST include the positioner/tracker, mast and build allowance —
never the antenna alone.**

**2. Buy a Yagi before a dish on the 433 side.** For every purchasable candidate the
best gain-per-euro, the best EUR/(kbps·km) and the best EUR/km are all a **70 cm Yagi**. The
recommended rig is a **high-gain Yagi (Diamond A-430S15R 14.8 dBi €74.50, or FlexaYagi
FX 7073 18.0 dBi €215) on the DIY printed tracker**, with the 0.6 m 2.4 GHz dish boresighted
on the same positioner.

**3. Any 433 dish of 2 m or more MUST be coarse MESH — and even then a dish is not
recommended while no vendor sells a parabolic former above 1.9 m.** The mesh rule is retained
from `flrc-max` §4.3, and this ADR records its *cost* consequence: at the **0.90 m** size the
mesh version is **€785** where the solid version is **€2,081** for **identical 10.35 dBi**,
because the solid dish's 0.636 m² projected area exceeds the Yaesu G-5500DC's **0.50 m² mast
rating** and forces a SPID BIG-RAS (€1,775). **Mesh is a positioner-class saving, not a
reflector saving.**

**4. The positioner must be a self-locking worm reduction + closed-loop encoder feedback +
a fail-safe brake + an anemometer stow. Closed-loop alone is NOT wind protection.** A motor
that knows its position fixes **pointing error** (and is what makes the €429 DIY tracker
viable on a 0.6 m dish's 1.46° beam budget); it does **NOT** stop a non-self-locking drive
being back-driven, and actively correcting a back-driven axis burns torque and can oscillate.

**5. Metal for the load path, printed for covers.** Sheet-metal laser cutting + bending is a
commodity online service (Xometry, Protolabs, Schaeffer AG, 247TailorSteel, Laserhub,
Cutworks, Blechking, SendCutSend); the azimuth platform, dish back-plate, mast/rotor plates
and all load-path brackets should be **metal**, while the electronics bay, covers, boom clamps
and complex 3-D geometry stay **printed**. The **gearing must be bought** — neither printed
nor sheet-metal.

**6. The highest-leverage euro in the architecture is the ~$8 F33 module on the balloon.**
Fitting it multiplies **every** ground candidate's range by **3.55** (10^(11/20)) for ~$8 and
+2.8 g, which no ground purchase can match. This confirms `flrc-max` REC-1 and prices the
operator's own two-board plan: **design the ground for the low-power board; treat the F33 as a
3.55× multiplier on whatever the ground can do.**

---

## The metric, and why it is the right unit

| # | Metric | Units | Role |
|---|---|---|---|
| M1 | `EUR_total / G433` | EUR/dB | diagnostic — rewards any cheap gain; **misleading alone** |
| M1m | `ΔEUR_total / ΔG` | EUR/dB | **diagnostic — exposes the non-monotonicity** |
| **M2** | `EUR_total / max_R (R · d_max(R))` | **EUR/(kbps·km)** | **PRIMARY** — prices range AND throughput |
| M3 | `EUR_total / d_max(650 kbps)` | EUR/km | range-first complement |

**Why M2 and not M1:** range enters the link equation logarithmically (`FSPL ∝ 20 log10 d`)
while rate enters the sensitivity term linearly, so `R · d_max` rewards the candidate that
keeps a high rate *and* still reaches — which is the operator's "maximise BOTH". M1 is blind
to the positioner-class jump: it scores the 0.90 m mesh dish (10.35 dBi) at 75.9 EUR/dB and
the 18.0 dBi FlexaYagi FX 7073 at 73.1 EUR/dB — 7.65 dB apart, "equivalent" per M1.

**Stated bias (recorded, not hidden):** M2 weights rate linearly and range logarithmically, so
it is a throughput-first metric. M3 is the range-first check; the two agree on the ranking
here, which is why the recommendation is robust.

**Margin-immunity (the property that makes the ranking trustworthy):** every candidate shares
the same implementation loss and fade margin, so **the ratio of any two candidates' €-per-unit
is exactly independent of the margin chosen**. Only the absolute km values move.

---

## The comparison (worst-case low-power LR2021, +22 dBm, 6 dB margin)

Selected rows; the full 17-row tables (A: +22 dBm, B: licence-exempt +12.15 dBm EIRP, C: F33
+33 dBm, D: marginal over a shared rig) are printed by the repro command.

| candidate | G433 dBi | total EUR | EUR/dB | EUR/(kbps·km) | 2.6 Mbps to | F33: 2.6 Mbps to |
|---|---:|---:|---:|---:|---:|---:|
| **Diamond A-430S15R** + DIY P2 | 14.8 | **735** | 49.7 | **0.0019 (best)** | 150 km | 532 km |
| Diamond A-430S10R + DIY P1 | 13.1 | **650** | 49.6 | 0.0020 | 123 km | 438 km |
| 2× Sirio WY 400-10N stacked + DIY P2 | 17.0 | 971 | 57.1 | 0.0019 | 193 km | 686 km |
| FlexaYagi FX 7073 + Yaesu G-5500DC | 18.0 | 1,316 | 73.1 | 0.0023 | 217 km | 769 km |
| 0.90 m dish, **mesh** | 10.35 | **785** | 75.9 | 0.0034 | 90 km | 319 km |
| 0.90 m dish, **solid** | 10.35 | **2,081** | 201.1 | 0.0089 | 90 km | 319 km |
| 1.90 m mesh (RFH FPD 1M9) + BIG-RAS | 16.8 | 2,878 | 170.9 | 0.0058 | 190 km | 673 km |
| 3.50 m mesh (DIY, frame TODO) + BIG-RAS | 22.2 | 3,677 | 166.0 | 0.0040 | 349 km | 1,240 km |

**The dish is beaten by the Yagi at every purchasable size.** The 1.9 m mesh dish (€2,878,
16.8 dBi) delivers *less* gain than the €1,316 18.0 dBi Yagi rig. **The dish only becomes
interesting above ~2.5 m, and there the parabolic former is not purchasable.**

## The non-monotonicity (the key insight, now recorded)

Marginal EUR/dB across the ladder:

- **Yagi + DIY ladder: €5.9–68.8 per dB** (the first 13.1 dB cost **€69 = €5.3/dB**; the
  3.7 dB from 13.1 to 16.8 dBi cost **€2,228 = €136/dB**, i.e. **26× the price per dB**).
- **Dish ladder: €127–598 per dB**, with the cliffs at the **positioner class boundaries**:
  1.50 m → 1.90 m mesh costs **+€1,228 for +2.05 dB (€598/dB)** purely because 1.90 m's
  effective wind area (0.751 m²) crosses the Yaesu's **0.50 m² mast rating**; the reflector is
  only €402 of that, **the rotator is 59 % of the marginal cost**.
- **The 0.90 m solid-vs-mesh case is the purest demonstration** (identical gain, €2,081 vs
  €785).
- **The metric is non-monotonic in BOTH directions:** above 1.9 m every mesh dish shares the
  same €1,775 BIG-RAS, so the *average* EUR/dB **falls** from 170.9 (1.9 m) to 157.7 (2.4 m) —
  **the expensive step is the class change, not the size.**

---

## Metal vs printed (§3 of the analysis, condensed)

| property | metal (5052/5754 Al, 304 SS) | printed PETG/ASA |
|---|---|---|
| stiffness | E ≈ 70 GPa | E ≈ 2 GPa (~1/35) |
| creep under sustained load | none | **real** — the failure mode of a held dish |
| wind survival | ductile, yields | brittle/anisotropic along layer lines |
| cost per part (qty 1) | **€45–160** | €0.30–3.00 filament |
| iteration | 1 day (Protolabs) – 5–8 days (Schaeffer) | hours |

**Indicative cost of the metal part set** (azimuth platform ~300 mm dia, 4 brackets, dish
back-plate, rotor plate): **≈ €250–470 at quantity 1** — **ESTIMATE**, extrapolated from
SendCutSend's single published example ($37.49 for a 5052-Al 2.54 mm, 136.5 × 160 mm laser
part at qty 1); obtain a real instant quote before ordering. Published terms: **Xometry
"no minimums", 3 business days**; **Protolabs "as fast as 1 day"**; **Schaeffer AG 5–8
working days**, quantity discounts 10/20/30 %, express 3 days +100 % / 1 day +200 %;
**Cutworks Express Plus same-day if ordered by 09:30**.

**Metal:** azimuth platform/turret base, dish back-plate, mast/rotor plates, all load-path
brackets, and the bearing housings (or their metal inserts). **Printed:** electronics
bay, covers, cable guides, Yagi boom clamp, feed spider, non-structural spacers. **Bought:**
the gearing.

---

## Closed-loop / position-aware motors

**Yes for pointing error; no for back-driving.** Feedback tells the controller where the axis
is and lets it remove *differential* backlash by a unidirectional approach — that is what keeps
the **€429 DIY tracker** viable on a 0.6 m dish (backlash 0.5° = 34 % of the 1.46° budget).
Feedback does **not** add holding torque: a non-self-locking drive is still pushed by the wind,
and correcting it burns torque and can oscillate. Sourced options: **AS5600/MT6701 magnetic
absolute encoders** (0.088°/0.022° — far below budget, price `TODO(unverified)`); closed-loop
stepper drivers **$46.64–48.04** and a NEMA 17 closed-loop motor **$77.40** (StepperOnline);
and a **17-bit absolute-encoder AC servo kit at $98.43**, which is cheaper than most bespoke
closed-loop retrofits. **The correct combination: self-locking worm (primary brake) + closed-loop
feedback + fail-safe spring-applied brake + anemometer stow.**

---

## Consequences

- **Cost:** the recommended rig is **€735 all-in** (option B) versus the commercial BOM's
  **€2,518** — a **3.4×** reduction with no capability loss for the committed link, and every
  part is purchasable (no fab quote, no out-of-stock kit). This directly serves the operator's
  "accessible for anyone to replicate".
- **The metric becomes the house tool:** any future ground-station proposal is evaluated by
  re-running `ground_station_gain_per_dollar_model.py` with the candidate added, **never by an
  antenna-only price**.
- **The F33 half of this ADR is gated, not decided.** ADR-039 open item (a) (licence-exempt
  airborne SRD) and the `docs/PAYLOAD-WEIGHT-ESTIMATES.md` §D "Ground Station Only"
  classification both remain unresolved; **both must be settled before the F33 goes on the
  balloon** (inherited from `flrc-max` REC-6).
- **Two open items are flagged, not resolved:** (i) **SPX-06 is €5,487 with a 716 N·m published
  rating while BIG-RAS is €1,775 with a 2,712 N·m brake** — price and rating orderings disagree
  because the bases differ (slew rating vs brake); per the repo rule a contradiction that names
  no winner is a **defect**. (ii) no vendor sells a **433 MHz prime-focus dish feed** or a
  **parabolic former above 1.9 m**.
- **Not covered:** procurement, the 2.4 GHz feed detail, and the control software.

## Alternatives considered and rejected

1. **Rank by antenna gain per antenna-price (no rig).** Rejected: it is the error the operator
   explicitly asked to avoid — a 3.5 m dish looks cheap and is not, because the rig jumps a
   class.
2. **Rank by average EUR/dB (M1) only.** Rejected: it scores a 10.35 dBi mesh dish and an
   18.0 dBi Yagi as equal.
3. **Maximise absolute gain (buy the biggest dish).** Rejected: the gain is not purchasable
   above 1.9 m, and below that a Yagi ties or beats it for 1/2 to 1/9 the cost.
4. **Close FLRC at 650 km from the ground on the low-power board.** Rejected: it requires a
   3.0–3.5 m dish whose former no vendor sells; the honest fix is the F33 on the balloon.

## For future sessions

- **One-line rule:** *price the rig with the antenna, in EUR per (kbps·km), before choosing a
  433 antenna — a Yagi beats a dish at every purchasable size.*
- **Files:** metric + tables `docs/analysis/ground-station-gain-per-dollar.md`; model
  `docs/analysis/ground_station_gain_per_dollar_model.py`; figure
  `docs/analysis/render_gain_per_dollar_figure.py`.
- **Reproduce:** `python3 docs/analysis/ground_station_gain_per_dollar_model.py`.
- **Read alongside:** ADR-066 (low-power 433 ground station), ADR-067 (positioner
  architecture), and `docs/analysis/ground-station-flrc-max-throughput.md` (mesh/wind, F33).
