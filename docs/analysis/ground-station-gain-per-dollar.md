# Ground-station GAIN-PER-DOLLAR / LINK-BUDGET-PER-DOLLAR — metric, comparison, metal fabrication, closed-loop position-aware motors

> **STATUS: CONSULTANT ANALYSIS — NOT A DECISION RECORD.** This is an analysis in
> `docs/analysis/`. It is **not** an ADR, **not** an operator decision, and it authorises no
> order, no fab freeze and no change to any board, BOM or schematic. The companion ADR
> (`docs/adr/068-ground-station-gain-per-dollar.md`) is **Proposed**.
>
> **Design only.** Nothing is ordered. `AGENTS.md` untouched.

| Field | Value |
|---|---|
| **Date** | 2026-10-08 |
| **Branch** | `design/gain-per-dollar` |
| **Worktree** | `/home/c03rad0r/worktrees/bf-gainperdollar` |
| **Base commit** | `09e1b69` (`github/main`) |
| **Author** | Hermes Agent (subagent), for the operator |
| **Repro command** | `python3 docs/analysis/ground_station_gain_per_dollar_model.py` (prints every numeric table below verbatim) |
| **Read first (prior art this builds on, not re-derives)** | `design/ground-station-bom` (`283cad72`) → `docs/analysis/ground-station-bom-candidates.md` (real prices + URLs); `design/ground-station-lowpower-link` (`4b90be94`) → `docs/analysis/ground-station-lowpower-link-and-shared-dish.md` (link analysis); `design/positioner-lowcost` → `docs/analysis/positioner-lowcost-3dprinted.md` (DIY tracker, back-driving, stow policy); `design/ground-station-flrc-max` → `docs/analysis/ground-station-flrc-max-throughput.md` (mesh vs solid wind, rate ladder) |
| **Scope** | The **433 MHz downlink** antenna + its positioner, because that is the direction that sets ground gain (§1.3). The 2.4 GHz uplink is handled separately (§1.3) and does not move the ranking. |
| **Out of scope** | Procurement; the 2.4 GHz uplink feed detail (owned by `dualband-single-dish.md`); regulatory licensing (ADR-039/041). |

Every figure is **SOURCED** (vendor URL / repo path), **COMPUTED** (formula + script shown),
a labelled **ESTIMATE** (basis named), or an explicit **`TODO(unverified)`**. No price, part
number, gain or datasheet value in this document was invented.

---

## 0. Answer first (the short version)

1. **The metric that matters is cost per unit of the thing the operator wants — throughput ×
   range — and it says: use a cheap high-gain 70 cm Yagi.** The **Diamond A-430S15R**
   (14.8 dBi, **€74.50**) on the **DIY printed tracker** (€509) is the best €/(kbps·km) of any
   candidate that closes the worst-case board: **€735 all-in**, **0.0019 €/(kbps·km)**.
   The **Diamond A-430S10R** (13.1 dBi, **€69**) is the best *marginal* gain-per-dollar:
   **€5.3 per dB** (§2.5).

2. **A 433 MHz dish is a worse deal than a Yagi at every size that is purchasable today.**
   The RF Hamdesign **1.9 m mesh dish (€901.45) + SPID BIG-RAS (€1,775) = €2,878** delivers
   **16.84 dBi**. The **FlexaYagi FX 7073 (€215) on a Yaesu G-5500DC (€949) = €1,316**
   delivers **18.0 dBi** — **more gain for 2.2× less money**. The dish only becomes
   interesting above ~2.5 m, and then only as MESH — and those kits are out of stock (§2.4).

3. **The metric is NON-MONOTONIC, and the jumps are the whole story.** The clearest case:
   *the same 0.90 m dish* costs **€785 as mesh** and **€2,081 as solid** — **identical gain
   (10.35 dBi)**, because the solid dish's 0.636 m² projected area exceeds the Yaesu
   G-5500DC's **0.50 m² mast rating** and forces a **SPID BIG-RAS (€1,775)**. Mesh is not a
   cheaper reflector; it is a **cheaper positioner class** (§2.6, §4).

4. **Metal fabrication is available online at retail scale, from €7 for a cut mesh panel to
   ~€40/part for a mid-size laser-cut aluminium part.** Instant-quote services that ship to DE
   and publish terms: **Xometry** (no minimum, **3 business days**), **Protolabs** (as fast as
   **1 day**), **Schaeffer AG** Berlin (**5–8 working days**, quantity discounts 10/20/30 %),
   **247TailorSteel**, **Laserhub**, **Cutworks**, **Blechking**, **SendCutSend** (US).
   **Metal for the load path, printed for covers** (§3).

5. **Yes, closed-loop position-aware motors help — but they fix POINTING ERROR, not
   back-driving.** A closed-loop stepper knows where the axis *is*; it does not stop the wind
   pushing the axis *while it holds*. The correct combination is **self-locking worm reduction
   (so the load cannot back-drive) + closed-loop feedback (so residual backlash is corrected
   by a unidirectional approach) + a fail-safe brake** (§5).

6. **The single highest-leverage euro in the whole architecture is the ~$8 F33 module.**
   Swapping the ground antenna cannot buy 11 dB cheaply; the F33 buys **+11 dB of TX power for
   ~$8 and +2.8 g** on the balloon, which improves *every* ground candidate's €-per-unit by
   **≈3.55×** (§2.4, Table C). That is the operator's "maximum gain per dollar", and it is on
   the balloon, not on the ground.

**RECOMMENDATION: §6. CHOICE TABLE: §7.**

---

## 1. THE METRIC

### 1.1 The operator's objective, stated as a quantity

The operator, verbatim: *"the more the better. For the time being the goal is to measure
what's possible and to identify a path to getting maximum gain per dollar while keeping the
costs low so that this project remains accessible for anyone to replicate,"* and *"Lets
include the cost of the holding rig / antenna tracker in our link budget per dollar or gain
per dollar calculation."*

So the objective has **two axes** (range AND throughput) and **one constraint** (cost, *all
in*, including the rig). The task names the two candidate metric families: **EUR per dB of
system gain** and **EUR per (dB × metre of range) or EUR per bit/s at a given range**.

Four metrics are defined below. All are computed by
`docs/analysis/ground_station_gain_per_dollar_model.py`.

### 1.2 The link equation the metrics sit on

```
required_G_ground = S(rate) + FSPL(d) − P_tx − G_balloon
FSPL(d) = 20·log10(4π/λ) + 20·log10(d)          λ(433.05 MHz) = 692.33 mm
budget  = P_tx + G_balloon + G_ground − S(rate) − L_impl − M_fade
d_max   = 10^((budget − 25.18 dB) / 20)  metres
```

Constants and their provenance (all from prior art on this repo; see §9):

| Symbol | Value | Source |
|---|---|---|
| `S` FLRC 2.6 Mbps | −100.5 dBm | Semtech LR2021 datasheet **Table 3-12**, sub-GHz FLRC 1 % PER |
| `S` FLRC 1.04 Mbps | −105.0 dBm | same table (`FLRC_1040_CR05`) |
| `S` FLRC 650 kbps | −107.0 dBm | same table (`FLRC_650_CR05`) |
| `S` LoRa SF12/62.5 kHz | −143.0 dBm | Semtech **Table 3-17** (`LORA_SUB_62_SF12`), corroborated by NiceRF V1.3 |
| `P_tx` chip max (sub-GHz) | **+22.0 dBm** | Semtech **Table 3-22** (`TXOPLF` typ) |
| `P_tx` licence-exempt point | **+12.15 dBm EIRP** | ADR-039 / ADR-041 (10 mW ERP integral antenna) |
| `P_tx` F33 module | **+33.0 dBm** | NiceRF `LoRa2021F33-2G4` (`docs/F33-MODULE-PLAN.md`) |
| `G_balloon` | 0 dBi | `docs/LINK-BUDGET-LICENCE-EXEMPT.md` (conservative) |
| `L_impl` | 2.6 dB | **ESTIMATE**: coax 1.14 (15 m Airborne 10 @0.76 dB/10 m) + N connectors 0.5 + polarisation 0.5 + pointing 0.5 |
| `M_fade` | 6 dB | **ESTIMATE**, stated operating fade margin |

> **The ratio is margin-immune.** Every candidate shares the same `L_impl` and `M_fade`, so
> **the ratio of any two candidates' €-per-unit is exactly independent of the margin chosen**
> — a constant margin multiplies every candidate's `d_max` by the same factor. Only the
> absolute km numbers move. This is the property that makes the ranking trustworthy.

### 1.3 Why the metric is applied to the 433 MHz downlink

The **433 downlink is the direction that sets ground gain.** The **2.4 GHz uplink needs
almost no ground gain**: `positioner-lowcost-3dprinted.md` §3.1 computes the required ground
gain as **−17.4 dBi at 300 km** and **−10.7 dBi at 650 km** (licence-exempt 20 dBm EIRP,
balloon LNA) — **negative**, i.e. an omni closes it. The uplink's dish is a *margin / EIRP /
beam-discipline* device (0.6 m sufficies, §3.2 there), not a link-closure device.

Therefore the ground-gain decision is decided entirely by the 433 downlink, and this document
prices the 433 side. Where the 2.4 GHz side matters — because it is why a positioner exists at
all — it is handled in **§2.5 (the shared-rig marginal view)**, which is the decision-relevant
one.

### 1.4 The four metrics

| # | Metric | Formula | Units | What it is good for |
|---|---|---|---|---|
| **M1** | average gain-per-dollar | `EUR_total / G_ground` | €/dB | quick sanity; **misleading alone** (rewards a cheap low-gain antenna and hides a positioner-class jump) |
| **M1m** | **marginal** gain-per-dollar | `ΔEUR_total / ΔG` between adjacent rungs | €/dB | **exposes the non-monotonicity** — the price of the *next* dB |
| **M2** | capability-per-dollar | `EUR_total / (R · d_max(R))` where `R` maximises `R·d_max` over the rate ladder | € per (kbps·km) | **THE metric** — prices both axes the operator wants; the rate/range optimum falls out |
| **M3** | range-per-dollar at a fixed rate | `EUR_total / d_max(650 kbps)` | €/km | complement to M2 for a range-first reading |

### 1.5 Which metric is more useful, and why

**M2 — EUR per (kbps·km) — is the most useful, and M1m is the most *diagnostic*.**

* **M1 (average €/dB) is a trap.** It is minimised by the cheapest thing that has *any*
  gain: the 0.90 m **mesh** dish at €785 scores 75.9 €/dB while the **18 dBi** FlexaYagi
  FX 7073 at €1,315 scores 73.1 €/dB — M1 says they are equivalent, which is absurd given one
  is 7.65 dB stronger. M1 cannot see the positioner-class jump because it only divides.
* **M2 sees what the operator actually buys.** Range enters the link equation logarithmically
  (`FSPL ∝ 20·log10 d`) while rate enters linearly (`S(rate)`), so `R · d_max` rewards the
  candidate that keeps a *high* rate *and* still reaches — exactly "maximise BOTH". It picks
  the 14.8 dBi Yagi, not the 3.5 m dish (Table A).
  > **Honest caveat, stated because it is a real bias:** `R · d_max` weights rate **linearly**
  > and range **logarithmically**, so it is a *throughput-first* figure of merit. For a
  > *range-first* reading use **M3** (€/km at a fixed rate) — the two agree on the ranking
  > here, which is why the recommendation is robust, but they need not agree in general.
* **M3 is the range-first complement.** It sets the rate (650 kbps) and asks how far a euro
  reaches. It ranks identically to M2 in Table A (0.9 €/km-class Yagis beat every dish).
* **M1m is what proves non-monotonicity.** M1m across the dish ladder goes
  **… 143.8 €/dB (2.4→2.6 m mesh) → 241 €/dB → 224 €/dB**, while the same rungs against a
  **Yagi baseline cost 5.9–68.8 €/dB**. That gap *is* the operator's insight (§2.6).

**One-line statement of the metric used for the ranking:**

> **M2 = EUR_total / max over the rate ladder of (R · d_max(R))**, where `EUR_total` =
> antenna + 433 feed + coax + connectors + **positioner/rotator or the full DIY tracker
> (motors, reducers, encoders, drivers, controller, anemometer)** + mast + a build/filament
> allowance; and `d_max` closes the 433 link for the **worst-case low-power LR2021 board**.

### 1.6 What is inside `EUR_total` (the operator's explicit requirement)

| Component | Value used | Basis |
|---|---|---|
| Antenna | per-candidate | `ground-station-bom-candidates.md` §0.1/§0.4 (vendor prices) |
| 433 MHz prime-focus feed (dishes only) | **€50** | **ESTIMATE** — no vendor sells a 433 MHz prime-focus dish feed (`flrc-max` §8 open item 2); DIY |
| Coax (15 m Airborne 10) | €97.50 | kabel-kusch.de **€6.50/m**, 0.76 dB/10 m @430 MHz |
| N/SMA connectors ×8 | €24.00 | bom-candidates §6 (`N-Stecker 7 mm €6.00`, `N-Buchse €7 mm €6.85`) |
| **Positioner / rotator or DIY tracker** | **€429 / €509 / €949 / €1,775 / €5,487** | sourced below |
| Mast + base | **€100** | **ESTIMATE** (included inside the DIY P1/P2 line) |
| Build / filament / hardware allowance | **€30** | **ESTIMATE** (positioner-lowcost §10 item 10) |

**Positioner menu** (the cost driver; all prices sourced):

| key | unit | € | rating basis | source |
|---|---|---:|---|---|
| P1 | **DIY printed tracker** NEMA23 3.0 N·m + NMRV40 20:1 self-locking worm | **429.00** | hold **40 N·m** | `positioner-lowcost` §10: €279 mechanics+electronics + €50 controller + €100 mast; StepperOnline `NMRV40 20:1` rated 40 N·m |
| P2 | as P1 but **NEMA34 8.2 N·m + NMRV50 30:1** | **509.00** | hold **67.5 N·m** | same list, `positioner-lowcost` Table 5 |
| P3 | **Yaesu G-5500DC** (AZ+EL) | **949.00** | **1.00 m² tower / 0.50 m² mast** | price funktechnik-bielefeld.de; wind DX Engineering |
| P5 | **SPID BIG-RAS** (AZ+EL) | **1,775.00** | **brake/hold 2,712 N·m**, turning 500 N·m, 318 kg | `spid-bigras-specifications.pdf` |
| P6 | **SPX-06** slew drive (AZ+EL) | **5,487.35** | 716 N·m rated, IP65, absolute encoders, 0.1° | RF Hamdesign Oct-2026 price list |

**Assignment rule (stated so the pairing is auditable, not asserted):** for each antenna the
model computes the **20 m/s operating wind moment** `M20` and the **effective wind area**
`A_eff` (mesh: `A_eff = σ·πD²/4`, `σ = 0.265` for 6 mm mesh — `flrc-max` §4.2), then picks
**the cheapest menu entry that passes either the vendor's published wind-area rating
(`A_eff ≤ area`) or a holding test (`hold ≥ 1.5 · M20`)**. `V_OP = 20 m/s` and the 1.5 factor
implement the operator's adopted **stow-on-wind policy** (size for 10–15 m/s operation, park
for storms — `positioner-lowcost` §7).

> **SPX-01 (€1,132) is deliberately excluded from the menu** because its paper rating is
> `TODO(unverified)` (`flrc-max` §5.2) — including it would require inventing a number. It is
> noted as the alternative for the 1.9–2.4 m class the moment its rating is sourced. Also
> **flagged as a repo defect, not resolved:** SPX-06 is **€5,487 with a 716 N·m published
> rating** while BIG-RAS is **€1,775 with a 2,712 N·m brake** — the price and rating orderings
> disagree because the bases differ (slew rating vs brake). The repo rule ("a contradiction
> that names no winner is a DEFECT — fix the record; never pick a side silently") applies;
> this document uses BIG-RAS wherever its brake holds and flags the pair as an open item
> (**§8 item 2**).

---

## 2. THE CANDIDATE COMPARISON

### 2.0 Shared geometry and the rate ladder

Free-space path loss at 650 km / 433.05 MHz = **141.4 dB** (reproduces
`ground-station-lowpower-link-and-shared-dish.md` §2). Rate ladder = the committed
**2600 → 1040 → 650 kbps** FLRC rates (`flrc-max` §1.4). Dish gain uses **η = 0.65**, the
vendor's **own** published efficiency (verified against RF Hamdesign's 1296/2320 MHz tables,
`flrc-max` §5.1).

**Dish gain at 433.05 MHz (η = 0.65) vs the required ground gain at 650 km, zero margin:**

```
   D m  G433 dBi |  FLRC 2.6 Mbps FLRC 1.04 Mbps  FLRC 650 kbps
------------------------------------------------------------------------
  0.60      6.83 |           18.9           14.4           12.4
  0.90     10.35 |           18.9           14.4           12.4
  1.20     12.85 |           18.9           14.4           12.4
  1.50     14.79 |           18.9           14.4           12.4
  1.90     16.84 |           18.9           14.4           12.4
  2.40     18.87 |           18.9           14.4           12.4
  2.60     19.57 |           18.9           14.4           12.4
  3.00     20.81 |           18.9           14.4           12.4
  3.50     22.15 |           18.9           14.4           12.4
  req G_ground = S + FSPL(650 km) − P_tx − G_balloon; FSPL(650 km) = 141.4 dB
  (zero margin); TX = +22 dBm
```

**Reading:** at the **low-power board's own chip maximum (+22 dBm)** the far link needs
**+12.4 dBi for 650 kbps / +18.9 dBi for 2.6 Mbps** at 650 km with *zero* margin. With the 6 dB
operating margin and 2.6 dB implementation loss the practical requirement becomes **+21.0 dBi
for 650 kbps** and **+27.5 dBi for 2.6 Mbps** — i.e. **a dish of 3.0–3.5 m for FLRC at 650 km
on the low-power board** (§2.3).

### 2.1 Table A — WORST CASE: low-power LR2021 board (+22 dBm, DE amateur regime)

```
candidate                          G433     ant€     pos€     tot€   €/dB  M20 Nm       best    d_km   Q kbps·km  €/(kbps·km)  €/km@650  d_LoRa km
--------------------------------------------------------------------------------------------------------------------------------
Diamond A-430S10R 10el            13.10    69.00   429.00   649.50   49.6    18.1 FLRC 2.6 Mbps   123.3      320607       0.0020       2.5      16444
Diamond A-430S15R 15el            14.80    74.50   509.00   735.00   49.7    30.6 FLRC 2.6 Mbps   150.0      389918       0.0019       2.3      19999
Sirio WY 400-6N 6el               11.00   132.00   429.00   712.50   64.8    26.5 FLRC 2.6 Mbps    96.8      251752       0.0028       3.5      12912
Sirio WY 400-10N 10el             14.00   155.00   509.00   815.50   58.2    44.1 FLRC 2.6 Mbps   136.8      355609       0.0023       2.8      18239
FlexaYagi FX 7015V                12.40   125.00   429.00   705.50   56.9    26.2 FLRC 2.6 Mbps   113.8      295783       0.0024       2.9      15171
FlexaYagi FX 7044                 16.60   164.00   949.00  1264.50   76.2    67.9 FLRC 2.6 Mbps   184.5      479704       0.0026       3.2      24604
FlexaYagi FX 7073                 18.00   215.00   949.00  1315.50   73.1   111.8 FLRC 2.6 Mbps   216.8      563603       0.0023       2.9      28907
2x Sirio WY 400-10N stacked       17.00   310.00   509.00   970.50   57.1    44.1 FLRC 2.6 Mbps   193.2      502312       0.0019       2.4      25763
0.90 m SOLID (Gibertini 85 SE)    10.35   104.90  1775.00  2081.40  201.1    48.4 FLRC 2.6 Mbps    89.9      233620       0.0089      11.0      11982
0.90 m mesh (same dish, meshed)   10.35   154.90   429.00   785.40   75.9    12.8 FLRC 2.6 Mbps    89.9      233620       0.0034       4.1      11982
1.20 m mesh (RFH FPD 1M2)         12.85   387.20   509.00  1097.70   85.4    30.4 FLRC 2.6 Mbps   119.8      311493       0.0035       4.3      15976
1.50 m mesh (RFH FPD 1M5)         14.79   499.73   949.00  1650.23  111.6    59.4 FLRC 2.6 Mbps   149.8      389366       0.0042       5.2      19970
1.90 m mesh (RFH FPD 1M9)         16.84   901.45  1775.00  2877.95  170.9   120.7 FLRC 2.6 Mbps   189.7      493197       0.0058       7.2      25296
2.40 m mesh (DIY, frame TODO)     18.87  1000.00  1775.00  2976.50  157.7   243.2 FLRC 2.6 Mbps   239.6      622986       0.0048       5.9      31952
2.60 m mesh (DIY, frame TODO)     19.57  1100.00  1775.00  3076.50  157.2   309.2 FLRC 2.6 Mbps   259.6      674901       0.0046       5.6      34615
3.00 m mesh (DIY, frame TODO)     20.81  1400.00  1775.00  3376.50  162.3   475.0 FLRC 2.6 Mbps   299.5      778732       0.0043       5.3      39941
3.50 m mesh (DIY, frame TODO)     22.15  1700.00  1775.00  3676.50  166.0   754.3 FLRC 2.6 Mbps   349.4      908521       0.0040       5.0      46597
2.40 m SOLID (DIY)                18.87  1000.00  1775.00  2976.50  157.7   917.7 FLRC 2.6 Mbps   239.6      622986       0.0048       5.9      31952
```

**Reading (the operator's actual answer):**

* **Best €/(kbps·km): Diamond A-430S15R (0.0019) and 2× Sirio stacked (0.0019)**, then
  FX 7073 and Sirio 10N (0.0023). Every one of these is **under €1,000 all-in** and delivers
  **2.6 Mbps out to 150–217 km** with the *worst-case* board.
* **The dish column is 1.7–2.2× worse per unit** than the best Yagis (0.0034–0.0058 vs
  0.0019) — and the DIY frames for the >1.9 m mesh dishes **cannot be bought** (§2.4).
* **`d_LoRa` is 12,000–46,000 km for every candidate.** LoRa (SF12/62.5 kHz, −143 dBm) closes
  the 650 km link with **every** antenna in the table, including a 0 dBi omni. **The entire
  antenna decision on the 433 side is therefore driven by FLRC, not by LoRa** — this
  reproduces `ground-station-lowpower-link-and-shared-dish.md` §0 in €-per-unit terms.

### 2.2 Table B — low-power LR2021 inside the licence-exempt cap (+12.15 dBm EIRP)

```
candidate                          G433     ant€     pos€     tot€   €/dB  M20 Nm       best    d_km   Q kbps·km  €/(kbps·km)  €/km@650  d_LoRa km
--------------------------------------------------------------------------------------------------------------------------------
Diamond A-430S10R 10el            13.10    69.00   429.00   649.50   49.6    18.1 FLRC 2.6 Mbps    39.7      103151       0.0063       7.7       5291
Diamond A-430S15R 15el            14.80    74.50   509.00   735.00   49.7    30.6 FLRC 2.6 Mbps    48.3      125451       0.0059       7.2       6434
Sirio WY 400-6N 6el               11.00   132.00   429.00   712.50   64.8    26.5 FLRC 2.6 Mbps    31.2       80998       0.0088      10.8       4154
FlexaYagi FX 7044                 16.60   164.00   949.00  1264.50   76.2    67.9 FLRC 2.6 Mbps    59.4      154338       0.0082      10.1       7916
FlexaYagi FX 7073                 18.00   215.00   949.00  1315.50   73.1   111.8 FLRC 2.6 Mbps    69.7      181332       0.0073       8.9       9300
2x Sirio WY 400-10N stacked       17.00   310.00   509.00   970.50   57.1    44.1 FLRC 2.6 Mbps    62.2      161612       0.0060       7.4       8289
0.90 m SOLID (Gibertini 85 SE)    10.35   104.90  1775.00  2081.40  201.1    48.4 FLRC 2.6 Mbps    28.9       75164       0.0277      34.1       3855
0.90 m mesh (same dish, meshed)   10.35   154.90   429.00   785.40   75.9    12.8 FLRC 2.6 Mbps    28.9       75164       0.0104      12.9       3855
1.20 m mesh (RFH FPD 1M2)         12.85   387.20   509.00  1097.70   85.4    30.4 FLRC 2.6 Mbps    38.5      100219       0.0110      13.5       5140
1.90 m mesh (RFH FPD 1M9)         16.84   901.45  1775.00  2877.95  170.9   120.7 FLRC 2.6 Mbps    61.0      158679       0.0181      22.3       8139
3.50 m mesh (DIY, frame TODO)     22.15  1700.00  1775.00  3676.50  166.0   754.3 FLRC 2.6 Mbps   112.4      292304       0.0126      15.5      14992
```
*(full 17-row table: run the repro command)*

**Reading:** the −9.85 dB of TX power costs **≈3.1× on every metric** (range ×0.32). At
**+12.15 dBm EIRP, FLRC at 650 km needs +22.3 dBi** (zero margin) → a **3.5 m mesh dish**
(22.15 dBi) *with zero margin*, i.e. **FLRC at 650 km is not reachable under the
licence-exempt cap from the ground**. LoRa still closes everywhere (5,300–15,000 km).
**Consequence: under licence-exempt rules, LoRa is the only far-link mode; FLRC is a
short-range mode** — the same conclusion as `ground-station-lowpower-link-and-shared-dish.md`
§0/§6, now priced.

### 2.3 Table C — HIGH-POWER F33 board (+33 dBm): what the second board buys

```
candidate                          G433     ant€     pos€     tot€   €/dB  M20 Nm       best    d_km   Q kbps·km  €/(kbps·km)  €/km@650  d_LoRa km
--------------------------------------------------------------------------------------------------------------------------------
Diamond A-430S10R 10el            13.10    69.00   429.00   649.50   49.6    18.1 FLRC 2.6 Mbps   437.5     1137557       0.0006       0.7      58345
Diamond A-430S15R 15el            14.80    74.50   509.00   735.00   49.7    30.6 FLRC 2.6 Mbps   532.1     1383481       0.0005       0.7      70958
Sirio WY 400-6N 6el               11.00   132.00   429.00   712.50   64.8    26.5 FLRC 2.6 Mbps   343.6      893251       0.0008       1.0      45814
FlexaYagi FX 7044                 16.60   164.00   949.00  1264.50   76.2    67.9 FLRC 2.6 Mbps   654.6     1702054       0.0007       0.9      87297
FlexaYagi FX 7073                 18.00   215.00   949.00  1315.50   73.1   111.8 FLRC 2.6 Mbps   769.1     1999739       0.0007       0.8     102565
2x Sirio WY 400-10N stacked       17.00   310.00   509.00   970.50   57.1    44.1 FLRC 2.6 Mbps   685.5     1782269       0.0005       0.7      91411
0.90 m SOLID (Gibertini 85 SE)    10.35   104.90  1775.00  2081.40  201.1    48.4 FLRC 2.6 Mbps   318.8      828914       0.0025       3.1      42514
0.90 m mesh (same dish, meshed)   10.35   154.90   429.00   785.40   75.9    12.8 FLRC 2.6 Mbps   318.8      828914       0.0009       1.2      42514
1.20 m mesh (RFH FPD 1M2)         12.85   387.20   509.00  1097.70   85.4    30.4 FLRC 2.6 Mbps   425.1     1105218       0.0010       1.2      56686
1.90 m mesh (RFH FPD 1M9)         16.84   901.45  1775.00  2877.95  170.9   120.7 FLRC 2.6 Mbps   673.0     1749929       0.0016       2.0      89753
3.50 m mesh (DIY, frame TODO)     22.15  1700.00  1775.00  3676.50  166.0   754.3 FLRC 2.6 Mbps  1239.8     3223553       0.0011       1.4     165334
```
*(full 17-row table: run the repro command)*

**Reading — the headline of the whole study:**

* **The F33 multiplies `d_max` by 10^(11/20) = 3.55 for every candidate**, so **every
  €-per-unit in Table C is ≈3.55× better than Table A** for the same hardware.
* **The €69 Diamond A-430S10R now reaches 437 km at 2.6 Mbps** on a €650 all-in ground
  station — better range at max rate than the 3.5 m dish could do on the low-power board
  (349 km, €3,677).
* **The F33 costs ~$8 and +2.8 g** (in-repo `docs/DUAL-VARIANT-DESIGN.md:192`; the live LCSC
  price is `TODO(unverified)` — `flrc-max` §5.4). **No ground antenna can buy 11 dB for
  anything near $8.** This is the maximum-gain-per-dollar answer, and it is on the balloon.
* This reproduces and *prices* `flrc-max` REC-1 (put the F33 on the balloon) and the
  operator's own two-board plan: **design the ground for the low-power board (Table A), and
  treat the F33 as a 3.55× multiplier on whatever the ground can do (Table C).**

### 2.4 Table D — MARGINAL cost over a SHARED rig (the decision-relevant view)

The 433 antenna shares the positioner with the 2.4 GHz uplink, which needs only a 0.6–0.75 m
dish (§1.3) → the baseline rig **already pays for the DIY P1 tracker (€429)**. The marginal
433 cost is therefore **antenna + 433 feed + any positioner upgrade over P1**:

```
candidate                          G433  ant+feed€  pos up€    marg€    d_km   Q kbps·km  €/dB marg   €/(kbps·km) marg
----------------------------------------------------------------------------------------------------------------------
Diamond A-430S10R 10el            13.10      69.00     0.00    69.00   123.3      320607        5.3           0.000215
Diamond A-430S15R 15el            14.80      74.50    80.00   154.50   150.0      389918       10.4           0.000396
Sirio WY 400-6N 6el               11.00     132.00     0.00   132.00    96.8      251752       12.0           0.000524
Sirio WY 400-10N 10el             14.00     155.00    80.00   235.00   136.8      355609       16.8           0.000661
FlexaYagi FX 7015V                12.40     125.00     0.00   125.00   113.8      295783       10.1           0.000423
FlexaYagi FX 7044                 16.60     164.00   520.00   684.00   184.5      479704       41.2           0.001426
FlexaYagi FX 7073                 18.00     215.00   520.00   735.00   216.8      563603       40.8           0.001304
2x Sirio WY 400-10N stacked       17.00     310.00    80.00   390.00   193.2      502312       22.9           0.000776
0.90 m SOLID (Gibertini 85 SE)    10.35     154.90  1346.00  1500.90    89.9      233620      145.0           0.006425
0.90 m mesh (same dish, meshed)   10.35     204.90     0.00   204.90    89.9      233620       19.8           0.000877
1.20 m mesh (RFH FPD 1M2)         12.85     437.20    80.00   517.20   119.8      311493       40.3           0.001660
1.50 m mesh (RFH FPD 1M5)         14.79     549.73   520.00  1069.73   149.8      389366       72.3           0.002747
1.90 m mesh (RFH FPD 1M9)         16.84     951.45  1346.00  2297.45   189.7      493197      136.4           0.004658
2.40 m mesh (DIY, frame TODO)     18.87    1050.00  1346.00  2396.00   239.6      622986      127.0           0.003846
3.00 m mesh (DIY, frame TODO)     20.81    1450.00  1346.00  2796.00   299.5      778732      134.4           0.003590
3.50 m mesh (DIY, frame TODO)     22.15    1750.00  1346.00  3096.00   349.4      908521      139.8           0.003408
2.40 m SOLID (DIY)                18.87    1050.00  1346.00  2396.00   239.6      622986      127.0           0.003846
```

**Reading — this is the strongest single result in the document:**

* **The first 13.1 dB of 433 gain costs €69 (€5.3/dB).** The next 3.7 dB to 16.84 dBi costs
  **€2,228 more (€136/dB)** — **26× the price per dB.** That non-monotonicity is the whole
  answer to the operator's question.
* The **positioner upgrade (€1,346, DIY P1 → BIG-RAS)** dominates every dish above 1.5 m:
  for the 1.9 m mesh dish, **59 % of the marginal cost is the rotator, not the reflector.**
  This is exactly why the operator's instruction to include the rig in the metric matters.
* The best marginal deal beyond a single Yagi is the **2 × Sirio WY 400-10N stacked pair**
  (17.0 dBi for **€390 marginal**, 22.9 €/dB) — because a stacked pair stays on a light
  positioner, whereas a dish of the same gain drags the rig up a class.

### 2.5 The two-axis view (why M2 and not M1)

| candidate | gain €/dB (M1) | **capability €/(kbps·km) (M2)** | range €/km @650 kbps (M3) |
|---|---:|---:|---:|
| Diamond A-430S10R | 49.6 | **0.0020** | 2.5 |
| Diamond A-430S15R | 49.7 | **0.0019 ← best** | 2.3 |
| FlexaYagi FX 7073 (18 dBi) | 73.1 | 0.0023 | 2.9 |
| 1.90 m mesh + BIG-RAS | 170.9 | 0.0058 | 7.2 |
| 3.50 m mesh + BIG-RAS | 166.0 | 0.0040 | 5.0 |

**M1 and M2 agree that the Yagis win** — but M1 rates the FX 7073 (18 dBi) as *worse* than the
3.5 m dish (166.0 vs 73.1) only because of the price, while M2 and M3 both put a 3.5 m dish
behind a €74.50 Yagi. **M2/M3 are the metrics to decide on; M1/marginal are the metrics to
explain the decision.**

### 2.6 NON-MONOTONICITY, enumerated (the key insight)

Marginal €/dB across the ladder (`monotonicity()` output):

```
rung                                 G433     tot€  €/dB avg     pos€       d€  marginal €/dB
------------------------------------------------------------------------------------------------
Diamond A-430S10R 10el              13.10   649.50      49.6   429.00
Diamond A-430S15R 15el              14.80   735.00      49.7   509.00                         50.3
Sirio WY 400-10N 10el               14.00   815.50      58.2   509.00                         34.3
FlexaYagi FX 7044                   16.60  1264.50      76.2   949.00                        133.1
FlexaYagi FX 7073                   18.00  1315.50      73.1   949.00                         36.4
2x Sirio WY 400-10N stacked         17.00   970.50      57.1   509.00                        345.0
0.90 m SOLID (Gibertini 85 SE)      10.35  2081.40     201.1  1775.00                       -167.1
0.90 m mesh (same dish, meshed)     10.35   785.40      75.9   429.00                  (same G)
1.20 m mesh (RFH FPD 1M2)           12.85  1097.70      85.4   509.00                        125.0
1.50 m mesh (RFH FPD 1M5)           14.79  1650.23     111.6   949.00                        285.1
1.90 m mesh (RFH FPD 1M9)           16.84  2877.95     170.9  1775.00                        597.9
2.40 m mesh (DIY, frame TODO)       18.87  2976.50     157.7  1775.00                         48.6
2.60 m mesh (DIY, frame TODO)       19.57  3076.50     157.2  1775.00                        143.8
3.00 m mesh (DIY, frame TODO)       20.81  3376.50     162.3  1775.00                        241.4
3.50 m mesh (DIY, frame TODO)       22.15  3676.50     166.0  1775.00                        224.1
```

Four distinct non-monotonic mechanisms, each with its trigger:

1. **The reflector-to-positioner coupling (the big one).** The `Δtot€` column is dominated by
   the `pos€` column. Going **1.50 m → 1.90 m mesh** costs **+€1,228 for +2.05 dB = €598/dB**,
   purely because 1.90 m's effective wind area (0.751 m²) crosses the Yaesu's **0.50 m² mast
   rating** and forces a **SPID BIG-RAS (€1,775)**. The reflector itself is only €402 of that.
2. **Solid vs mesh at IDENTICAL gain — the purest case.** The **0.90 m dish** is **10.35 dBi
   either way**; **solid = €2,081, mesh = €785.** The solid 0.90 m projected area is
   **0.636 m² > 0.50 m²**, so it needs BIG-RAS; the mesh version (A_eff **0.169 m²**) runs on
   the **€429 DIY tracker**. **Mesh here is a positioner-class saving of €1,296, not a
   reflector saving.** (A tower instead of a mast would lift the Yaesu to 1.00 m² and rescue
   the solid dish — see §2.7.)
3. **The dish plateau / reversal.** Above 1.9 m every mesh dish shares the **same €1,775**
   rotator, so the *average* €/dB **falls** from 170.9 (1.9 m) to 157.7 (2.4 m) to 166.0
   (3.5 m) — i.e. **the metric is non-monotonic in the "big dish is worse" direction too**:
   once the rotator class is paid for, more dish is *better* per euro. **The expensive step is
   the class change, not the size.**
4. **The stacking anomaly / the honest caveat.** A **2 × Sirio stacked pair (17.0 dBi, €970)**
   has a *worse* M1 (57.1 €/dB) than the FX 7073 (18.0 dBi, 73.1 €/dB) yet a *better* marginal
   (22.9 €/dB) — because the stacked pair stays on a €509 drive while the 3.08 m-boom FX 7044
   crosses to a €949 Yaesu. **Non-monotonicity is not only "bigger dish = worse"; it is "any
   step that crosses a positioner class boundary."**

**Why this is exactly the insight the operator needs:** a naive "€/dB" table would rank the
18 dBi Yagi and the 3.5 m mesh dish as comparable. The metric with the rig included shows the
real structure is **step-wise**: the price of gain is **€5–68/dB on the Yagi ladder** and
**€127–145/dB on the dish ladder**, with the cliffs at the **positioner class boundaries**
(0.50 m² mast → BIG-RAS; 2,712 N·m brake → SPX-06).

### 2.7 Wind / torque classification (audit trail for the pairing)

```
candidate                        kind          A_eff m2  M20 N.m  1.5xM20 | picked positioner                             €  hold N.m
-------------------------------------------------------------------------------------------------------------------------------------
Diamond A-430S10R 10el           Yagi             0.150     18.1     27.1 | DIY NEMA23+NMRV40 20:1 (printed yoke)    429.00      40.0
Diamond A-430S15R 15el           Yagi             0.150     30.6     46.0 | DIY uprated NEMA34+NMRV50 30:1           509.00      67.5
Sirio WY 400-6N 6el              Yagi             0.150     26.5     39.7 | DIY NEMA23+NMRV40 20:1 (printed yoke)    429.00      40.0
Sirio WY 400-10N 10el            Yagi             0.150     44.1     66.2 | DIY uprated NEMA34+NMRV50 30:1           509.00      67.5
FlexaYagi FX 7015V               Yagi             0.150     26.2     39.4 | DIY NEMA23+NMRV40 20:1 (printed yoke)    429.00      40.0
FlexaYagi FX 7044                Yagi             0.150     67.9    101.9 | Yaesu G-5500DC (AZ+EL, MAST 0.50 m2)     949.00       nan
FlexaYagi FX 7073                Yagi             0.150    111.8    167.7 | Yaesu G-5500DC (AZ+EL, MAST 0.50 m2)     949.00       nan
2x Sirio WY 400-10N stacked      Yagi             0.150     44.1     66.2 | DIY uprated NEMA34+NMRV50 30:1           509.00      67.5
0.90 m SOLID (Gibertini 85 SE)   dish 0.90 m solid     0.636     48.4     72.6 | SPID BIG-RAS (AZ+EL)                    1775.00    2712.0
0.90 m mesh (same dish, meshed)  dish 0.90 m mesh     0.169     12.8     19.2 | DIY NEMA23+NMRV40 20:1 (printed yoke)    429.00      40.0
1.20 m mesh (RFH FPD 1M2)        dish 1.20 m mesh     0.300     30.4     45.6 | DIY uprated NEMA34+NMRV50 30:1           509.00      67.5
1.50 m mesh (RFH FPD 1M5)        dish 1.50 m mesh     0.468     59.4     89.1 | Yaesu G-5500DC (AZ+EL, MAST 0.50 m2)     949.00       nan
1.90 m mesh (RFH FPD 1M9)        dish 1.90 m mesh     0.751    120.7    181.0 | SPID BIG-RAS (AZ+EL)                    1775.00    2712.0
2.40 m mesh (DIY, frame TODO)    dish 2.40 m mesh     1.199    243.2    364.8 | SPID BIG-RAS (AZ+EL)                    1775.00    2712.0
2.60 m mesh (DIY, frame TODO)    dish 2.60 m mesh     1.407    309.2    463.8 | SPID BIG-RAS (AZ+EL)                    1775.00    2712.0
3.00 m mesh (DIY, frame TODO)    dish 3.00 m mesh     1.873    475.0    712.5 | SPID BIG-RAS (AZ+EL)                    1775.00    2712.0
3.50 m mesh (DIY, frame TODO)    dish 3.50 m mesh     2.550    754.3   1131.4 | SPID BIG-RAS (AZ+EL)                    1775.00    2712.0
2.40 m SOLID (DIY)               dish 2.40 m solid     4.524    917.7   1376.6 | SPID BIG-RAS (AZ+EL)                    1775.00    2712.0
```

Model: `q = ½ρv²`, `F = q·A·Cd`, `M = F·(D/4)`, `ρ=1.225`, **`Cd = 1.38` DERIVED** from the
Gibertini OP100SE vendor figure (91 kg @ 120 km/h over 0.949 m² — `flrc-max` §4.2), mesh
`σ = 0.265` for 6 mm mesh. **`V_OP = 20 m/s`, SF = 1.5** (the stow-on-wind policy).

> **TWO HONEST CAVEATS ON THIS TABLE, stated because they change the conclusion.**
> **(a) Solid vs mesh separates at STORM wind, not at the operating wind.** At 20 m/s, a
> 2.40 m SOLID dish's operating moment is **1,377 N·m ≤ 2,712 N·m**, so **BIG-RAS holds it at
> the same €1,775 as the mesh version** (hence the identical Table D rows). The mesh's
> advantage appears at **120 km/h (33.3 m/s)**, where `flrc-max` §4.3 measures the 2.40 m SOLID
> at **1.88× the BIG-RAS brake** (infeasible) vs the **mesh at 0.50×** (fine). **The stow
> policy is what makes solid feasible at all; if the stow ever fails, solid is the one that
> breaks.** Mesh + stow is therefore the recommendation, for *survival* reasons rather than
> cost reasons (§4).
> **(b) The Yagi `A_eff = 0.15 m²` is an ESTIMATE.** No vendor publishes a wind figure for
> these Yagis (`TODO(unverified)`), so the Yagi wind column is a modelled estimate and the
> long-boom Yagis' assignment to a Yaesu is driven by it. The **ranking is not sensitive** to
> it: any plausible value keeps the Yagis on the two cheapest positioner classes, and the
> conclusion (Yagi beats dish per euro) is unchanged.

---

## 3. TASK 2 — METAL MANUFACTURING (research, with URLs)

The operator asked: *"would it be possible to get the whole thing made out of metal? Are there
services that can manufacture such things for us at a reasonable cost?"*

**Answer: yes, for every part that should be metal — at retail scale, online, from single
parts.** Sheet-metal laser cutting + bending is a commodity online service in 2026 and ships
to Germany. What you cannot buy is the **RF** metal (the dish reflector is a vendor kit) or
the **gearing** (a bought NMRV worm); those stay as they are.

### 3.1 Sourced services and published terms

| Service | Region | Process | Min order | Lead time (stated) | Price evidence | URL |
|---|---|---|---|---|---|---|
| **Xometry** | US + international (tariffs noted) | laser + waterjet cutting, sheet & tube fabrication, bending, PEM inserts, welding, finishing | **"No minimums"** | **standard 3 business days**; blank 5′×10′; auto-quote to ±0.005″ | instant quote; "competitive custom prices for low-volume prototypes" | https://www.xometry.com/capabilities/sheet-metal-fabrication/ |
| **Protolabs** | US/EU | laser cutting, press-brake forming, sheet-metal assemblies | not stated | **"as fast as 1 day"**; quote in minutes | online quote platform | https://www.protolabs.com/services/sheet-metal-fabrication/ |
| **SendCutSend** | **US** (free US shipping ≥ $39) | laser cutting, bending, 175+ materials/thicknesses | **"No minimum quantities"**; volume discounts up to 80 % | same-week (customer quote, not a spec) | **published example: 5052 aluminium 0.100″ (2.54 mm), 5.375 × 6.3 in laser-cut part = $37.49/ea @ qty 1** | https://sendcutsend.com/pricing/ · https://sendcutsend.com/materials/ |
| **Schaeffer AG** | **DE (Berlin)** | CNC **milled** front panels, enclosures, milled parts; bending, anodising, powder coat | 1 part | **5–8 working days** std; express **3 days +100 %**, **1 day +200 %** | live price in the free **Frontplatten-Designer**; qty discount **10 % (5–9), 20 % (10–19), 30 % (20–29)**; powder coat RAL **€83.05 net**; RAL/NCS paint **€55.20 net**; drawing/engraving service **€23.70 net** per started ¼ h | https://www.schaeffer-ag.de/support/preise-und-versand |
| **247TailorSteel** | **NL / DE / BE** | laser-cut sheet & tube + **bending**, automated 24/7 production | 1 part | not stated; "order ahead → lower price" | instant online ordering (Sophia®) | https://www.247tailorsteel.com/en |
| **Laserhub** | **DE / DACH** | laser, plasma, flame, **bent parts**, tube laser, CNC | 1 part | "transparent instant quote day and night"; a customer quote claims lead time reduced "by up to 50 %" | instant quote platform; ISO 9001:2015; cost calculator | https://www.laserhub.com/ |
| **Cutworks GmbH** | **DE** | laser + flame cutting, **bending**, deburring, drilling & tapping | registration to see prices | **Express Plus: order by 09:30 → same working day** | tiered (Staffel) prices shown in the online shop after registration | https://www.cutworks.com/de/infos/preise-und-rabatte/ |
| **Blechking** | **DE** | online cut-to-size + **bending** ("Blechselektor", 5 steps) | 1 part | not stated | shop lists cut-to-size **aluminium 1/2/3 mm, steel 1/3/6 mm, galvanised 1/1.5/2/3 mm, stainless 1/2/3 mm** | https://blechking.de/Bleche-kaufen |
| **metal-market.eu** | **AT/EU** | cut-to-size **mesh** ("nach Maß") | 1 panel | not stated (free shipping > €100) | **welded mesh from €7.00** (cut-to-size listing) | https://metal-market.eu/collections/schweissgitter |

> **`TODO(unverified)`:** PCBWay and JLCPCB are often named as sheet-metal houses, but their
> sheet-metal URLs returned **HTTP 404** to a direct fetch this session
> (`pcbway.com/sheet-metal*.html`, `jlcpcb.com/sheet-metal*`), so **no PCBWay/JLCPCB sheet-metal
> claim is made here.** Their 3D-printing/CNC trees exist; the sheet-metal page does not
> resolve. Do not cite them for metal without a re-check.
> Also `TODO(unverified)`: a **waterjet-specific** shop with published per-part prices — the
> waterjet German site I tried (`wasserstrahlschneiden24.de`) is **a parked domain for sale**
> ("steht zum Verkauf"), so only **Xometry's** waterjet service is cited, with no published
> price.

### 3.2 Indicative cost for the representative part set

There is **one real anchor price** in the sources above: **SendCutSend's own published example
of a 5052-aluminium 2.54 mm laser-cut part 136.5 × 160 mm at $37.49 each, quantity 1.** The
figures below extrapolate **from that anchor** by bounding-box area and bend count. They are
**ESTIMATES, not quotes** — obtain a real instant quote before any order (all the services
above quote instantly).

| Part | Material / process | Indicative qty-1 (ESTIMATE) | Basis |
|---|---|---|---|
| **Azimuth platform, ~300 mm dia** | 5052 Al (or 5754), 3 mm, laser cut + deburr; optional 4–6 tapped holes | **≈ €45–90** | 4.3× the anchor's bounding area, no bends, rounded geometry |
| **Turret side brackets (×2–4)** | 5052 Al or 304 stainless, 2–3 mm, laser cut + **bent** | **≈ €15–30 each** (bend uplift) | below the anchor in area; Schaeffer's and Cutworks' bend services confirm bending is an add-on |
| **Dish back-plate / stiffener, 1.2 m** | 5052 Al or 5754, 3–4 mm, laser cut + rolled/ribbed | **≈ €70–160** | 10–18× the anchor's area; 1.2 m fits a 5′×10′ blank |
| **Mast adaptor / rotor plate** | 304 stainless or 5 mm Al, laser cut + bends + drilled | **≈ €50–110** | Schaeffer's own `BR-50B` precedent: "**5 mm laser-cut steel**, 6 kg, dishes up to 3 m" (RF Hamdesign, `flrc-max` §5.1) |
| **Printed-versus-metal allowance** | — | **+€0.30–3.00/part metal premium** | metal needs CAD/DXF and a service; printing is free at the margin |

**Set total (ESTIMATE) for the metal parts of a 1.2–1.9 m mesh dish tracker
(platform + 4 brackets + back-plate + rotor plate): ≈ €250–470** at quantity 1, versus
**≈ €30 of PETG/ASA filament** for the printed equivalents (`positioner-lowcost` §10 item 10).

### 3.3 METAL vs PRINTED — the comparison the operator asked for

| Property | **Laser-cut/bent metal (5052/5754 Al, 304 SS)** | **Printed PETG/ASA (≥4 perimeters, ribbed)** |
|---|---|---|
| **Stiffness** | high (E ≈ 70 GPa Al, 200 GPa SS) | **low** (E ≈ 2 GPa PETG) — ~1/35 of Al |
| **Creep under sustained load** | none (elastic to yield) | **real and time-dependent** — the failure mode of a continuously held dish in wind (`positioner-lowcost` §5) |
| **Backlash contribution** | none (single piece) | none in the structure; **never the gear teeth** (printed gears creep/strip) |
| **Wind survival** | ductile; fails by yielding, and a 5 mm steel bracket is the vendor's own 3 m-dish part | **brittle/anisotropic failure along layer lines** under shock; UV/heat degrade it |
| **Mass** | higher (3 mm 5052 Al ≈ 8.1 kg/m²) | lower (≈ 1.27 kg/m² at 100 % infill, less with infill) |
| **Cost per part (qty 1)** | **€45–160** for the parts above + CAD time | **€0.30–3.00** filament, + print time |
| **Iteration speed** | 3 days–2 weeks (post, ship) | hours |
| **Weather / UV** | needs anodise/paint (Schaeffer powder coat €83.05 net) | PETG/ASA OK-ish; PLA degrades |
| **Assembly** | needs drilling/tapping; Schaeffer offers that as a service | printed-in-place features, heat-set inserts |

**Which parts should be metal, and which stay printed (this is the operator's answer):**

**MUST be metal (buy from a sheet-metal service):**
1. the **azimuth platform / turret base disc** — it takes the whole overturning moment;
2. the **dish back-plate / stiffener** — it sets reflector rigidity (and mesh sag tolerance);
3. the **mast adaptor and the rotor-to-structure plate** — the load path into the mast;
4. **all brackets in the load path**, and the **bearing housings or their metal inserts**
   (never run a steel shaft directly on a printed bore — `positioner-lowcost` §5);
5. **the worm reducers and all gearing** — bought, not printed and not sheet-metal
   (`positioner-lowcost`: printed gears creep and strip at these tooth loads).

**SHOULD stay printed:**
6. the **electronics bay / enclosure**, covers, and cable guides (non-structural);
7. the **Yagi boom clamp** and **433 feed-support spider** (light, non-critical);
8. **non-structural spacers, jigs, drill guides and the feed clamp**;
9. **any geometry that is complex in 3-D** and cheap to print — the printed yoke **is**
   acceptable *if* it is properly reinforced and carries no tooth load (the consultant's own
   point, `positioner-lowcost` §15 item 2).

> **Verdict: "the whole thing out of metal" is possible and affordable, but it is not the
> optimum.** Metal where the load and the weather are; printed where the geometry is complex
> and the load is low. **The one thing that must be neither printed nor sheet-metal is the
> gearing** — buy the self-locking worm reducer.

---

## 4. Why MESH, in one place (the enabler the operator identified)

λ/10 at 433 MHz = **69.2 mm** (`bom-candidates` §4), so 6–25 mm commodity mesh is
**electrically solid** and costs **zero RF performance** — the mesh is **11.5× finer than
required** (`flrc-max` §4.1). Its whole purpose is the **wind area**: at 120 km/h a 2.40 m
SOLID dish is **1.88×** the BIG-RAS brake while the mesh is **0.50×**; at 3.00 m the mesh is
**0.97×** (at the limit) (`flrc-max` §4.3). **The mesh is what brings a large 433 dish into a
feasible positioner class at all**, and this document prices the consequence: **mesh is a
positioner-class saving (€1,296 on the 0.90 m dish), not a reflector saving.** Housekeeping:
6 mm/1 mm welded mesh is stocked (drahtgewebe-shop.de); 25 × 25 mm / 1.75 mm galvanised mesh is
**€7.00** cut-to-size (metal-market.eu); the mesh **skins** are cheap and purchasable, but for
>1.9 m **no vendor sells the parabolic former** (`flrc-max` §4.4/§8 item 3) — which is why the
2.4–3.5 m rows in the tables are labelled **"DIY, frame TODO"** and are **not a purchasable
option today**.

---

## 5. TASK 3 — CLOSED-LOOP / POSITION-AWARE MOTORS vs WIND

The operator asked: *"would it help to have a motor that knows its orientation / position and
can correct for errors introduced by the wind?"*

### 5.1 The answer

**Yes — for POINTING ERROR. No — for BACK-DRIVING. They are different problems and the
operator's question conflates them.**

| Problem | What it is | Does closed-loop feedback fix it? |
|---|---|---|
| **Position/pointing error** (counts lost to missed steps, backlash, thermal drift) | the controller's *belief* about the axis diverges from reality | **YES.** An encoder tells the controller where the axis actually is; it can re-command and, by always approaching from one direction, remove the *differential* backlash. |
| **Back-driving** | the wind **physically turns the axis while it is holding** | **NO.** Feedback does not add holding torque. A non-self-locking drive still moves; the controller then fights the wind, **burning torque continuously and risking oscillation** (`positioner-lowcost` §6, and the consultant, §15: *"Closed-loop steppers correct position error; they do not remove backlash or guarantee wind survival."*). |

**The correct combination (this is the design answer):**

```
self-locking worm reduction   →  the load CANNOT back-drive (holds the stow with no power)
  + closed-loop encoder feedback →  the controller KNOWS the axis position and corrects
                                   residual backlash by unidirectional approach
  + fail-safe holding brake      →  survives a controller/power failure
  + anemometer cutoff + stow      →  removes the storm case entirely
```

Self-locking is **ratio- and friction-dependent**: it is reliable only above **~20:1**, and the
vendor will not warrant it for holding loads without confirmation (`positioner-lowcost` §6,
quoting StepperOnline: *"For critical holding/lifting applications, confirm with us"*). So
**treat the worm as the primary brake and add a spring-applied (power-released) brake as the
fail-safe.** A **satellite-dish linear actuator** (lead-screw) is *intrinsically* self-locking
and is the classic cheap elevation axis — Tek2000 QARL-24 SuperJack heavy-duty 36 V,
**$339.00, 675 kg (1500 lb)** rating, 24″ stroke.

### 5.2 Sourced options and prices

All from `omc-stepperonline.com` (fetched this session, HTTP 200) unless noted:

| Option | Class | Price | Notes |
|---|---|---|---|
| **AC servo kit, 17-bit ABSOLUTE encoder**, 400 W / 1.27 N·m, IP67 | servo + true absolute feedback | **$98.43** | 17-bit = **131,072 counts/rev ≈ 0.0027°** — far below any pointing budget. **A complete absolute-feedback servo kit for ~$98 makes a bespoke "closed-loop retrofit" uneconomic at the top of the range.** |
| AC servo kit, 750 W / 2.39 N·m, 17-bit absolute, IP67 | servo | **$116.38** | same page |
| AC servo kit, 1000 W / 3.18 N·m, 17-bit absolute, IP67 | servo | **$147.15** | same page |
| **P-Series NEMA 17 closed-loop stepper** 48 N·cm | closed-loop stepper | **$77.40** | encoder-equipped stepper |
| **Closed Loop Stepper Driver V4.1** 0–3.0 A 24–48 VDC (NEMA 11/17 class) | driver (stepper must be encoder-equipped) | **$46.64 / $48.04** | |
| **Y-Series V2.0 Closed Loop Stepper Driver** 0–7.0 A 24–50 VDC (NEMA 17) | driver | **$47.75** | |
| Open-loop digital driver **DM542T** 0–4.2 A 20–50 V | driver (no feedback) | **$19.65** | **corrects an in-repo ESTIMATE**: `positioner-lowcost` §10 item 6 estimated "~€12 ea"; the real part is **$19.65** |
| NEMA 8 / NEMA 11 closed-loop stepper | small closed-loop stepper | **$48.17 / $49.73** | |
| Incremental optical encoder, 300 PPR | encoder | **$49.73 / $40.44** | |
| **NEMA23 / NEMA34 *closed-loop* motor prices** | — | **`TODO(unverified)`** | the category pages did not render prices to this session's fetch; **do not invent a number** |
| **AS5600 / AS5048 magnetic absolute encoder** (cheap retrofit: 12-bit → **0.088°**; MT6701 14-bit → **0.022°**) | magnetic absolute encoder | **`TODO(unverified)`** on the part price (retail pages bot-walled); `positioner-lowcost` carries it as "~€5 ea ESTIMATE" and its resolution figures are far below the pointing budget | the cheap retrofit path |
| Satellite linear actuator Tek2000 QARL-24 (36 V, lead-screw) | self-locking elevation drive | **$339.00** | `positioner-lowcost` §6 — intrinsically self-locking |

### 5.3 The cost consequence for THIS ground station

* The positioner's own design already specifies **closed-loop steppers** (`positioner-lowcost`
  §10 item 4: "NEMA23 3.0 N·m **bipolar stepper**", item 7: "Axis encoders (closed-loop)
  AS5600 or MT6701"). **Closed-loop is the plan; it just must not be mistaken for wind
  protection.**
* The **cheapest adequate upgrade** is the **AS5600/MT6701 magnetic absolute encoder per axis**
  (a few euro, resolution 0.022–0.088° vs the 0.6 m beam budget of 1.46° —
  `positioner-lowcost` Table 6). The **most robust** is a **17-bit absolute-encoder AC servo kit
  at $98.43**, which is cheaper than most "big closed-loop stepper" retrofits and gives true
  absolute position.
* **What closed-loop buys in the metric:** it lets the 0.6 m dish keep its **1.46° beam budget**
  on a cheap drive with 0.5° backlash (34 % of budget — `positioner-lowcost` Table 6), i.e. it
  is what makes the **€429 DIY tracker** viable rather than a €949+ commercial rotator. That is
  the metric's real dependence on this answer: **closed-loop + self-locking worm is what keeps
  the positioner in the €429–509 class, which is the class the whole recommendation rests on.**

---

## 6. RECOMMENDATION (with explicit reasoning)

### 6.1 The recommendation

> **Build the ground station as a cheap high-gain 70 cm YAGI on the DIY printed tracker, and
> put the money on the balloon instead: fit the F33.**
>
> **Specifically: `FlexaYagi FX 7073` (18.0 dBi, €215) or `Diamond A-430S15R` (14.8 dBi,
> €74.50) on the DIY P1/P2 tracker (€429–509), with the 0.6 m 2.4 GHz dish boresighted on the
> same positioner. Do NOT buy a 433 MHz dish.**
>
> **Do not attempt to close FLRC at 650 km from the ground with the low-power board** — that
> needs a 3.0–3.5 m dish (€3,377–3,677) whose former **no vendor sells** (`flrc-max` §8 item 3).
> With the F33, the €69 `Diamond A-430S10R` reaches **437 km at 2.6 Mbps** and the FX 7073
> reaches **769 km at 2.6 Mbps**.

### 6.2 Reasoning, step by step

1. **The binding direction is the 433 downlink, and the binding board is the low-power one.**
   The 2.4 GHz uplink needs *negative* ground gain (§1.3). So the ground-gain decision is set
   by the worst case — the low-power LR2021 — exactly as the operator specified.
2. **On the 433 side, LoRa closes everywhere with anything.** `d_LoRa` is 12,000–46,000 km for
   every candidate including a 0 dBi omni (Table A). So the antenna choice is **entirely** a
   **FLRC** decision. This is the single most important framing: the operator's "maximise both
   range and throughput" resolves to "LoRa for range, FLRC for throughput," and only FLRC
   prices the antenna.
3. **Within FLRC, the Yagi wins on every metric.** Best €/(kbps·km) (0.0019, Table A), best
   €/km (2.3), best marginal €/dB (€5.3 for the first 13.1 dB, Table D). The dish is 1.7–2.2×
   worse per unit and needs a **€1,346 positioner upgrade** to even exist above 1.5 m.
4. **The dish only wins on absolute gain above ~2.5 m, and that is not purchasable.**
   The 1.9 m RFH FPD 1M9 (**16.84 dBi, €901**) is *beaten* by the **18.0 dBi FX 7073 (€215)**.
   The 2.4/3.0/3.5 m kits are **out of stock** and their formers are **DIY-only**
   (`flrc-max` §5.1), so they cannot be recommended as a buy.
5. **The positioner is the cost, not the reflector** — so build the positioner well and cheaply:
   **self-locking NMRV worm + closed-loop feedback + anemometer stow**, i.e. the
   `positioner-lowcost` architecture, which is what keeps the rig in the €429–509 class.
6. **The highest-leverage euro is the F33 (~$8).** It multiplies every ground candidate's
   range by **3.55** (Table C) — including *both* flight boards' experiment, since the F33
   board is the high-power variant of the same experiment. **No ground purchase can match
   $8 for 11 dB.** This is the operator's "maximum gain per dollar," and it is on the balloon.
7. **Replicability is preserved.** The recommended rig is **€735 all-in** (or **€650** with the
   A-430S10R) — cheaper than the commercial BOM's **€2,518** by 3.4×, and it uses a
   **purchasable Yagi + a printed tracker + bought worm gearing + an $8 module**, i.e. parts
   any replicator can obtain. **No part requires a fab quote, a machine shop, or a vendor that
   is out of stock.**

### 6.3 What would flip the recommendation (stated honestly)

* **If a >2.5 m mesh dish becomes purchasable** (former/rib kit back in stock, or a metal-shop
  quote for laser-cut ribs — §3), the €/(kbps·km) of the 3.5 m mesh (**0.0040**, Table A)
  approaches the Yagis and its **22.15 dBi** becomes the only way to FLRC at 650 km on the
  low-power board. My metric says this is *still* worse per euro, but it is the only route to
  that specific capability.
* **If the experiment requires a very narrow beam** (interference rejection, or precise
  boresight for a high-rate pass), the dish's narrow beamwidth is a feature, not a cost, and
  the metric does not price it. This is the same qualification the visual consultant made on
  the positioner study ("justified by pointing margin, interference rejection, polarization, or
  operational robustness—not link closure alone", §15).
* **If the F33 is excluded** (mass or licence), the fallback is **+22 dBm + 650 kbps** with the
  best Yagi, and **FLRC-max is reserved for ≤ ~150 km** — and the metric then *does* favour a
  dish, badly enough that the honest answer is "change the balloon, not the ground."

---

## 7. CHOICE TABLE — 3–4 options for the operator

All costs are **€, out of pocket, all-in** (antenna + 433 feed + coax + connectors + positioner
+ mast + build allowance), from the model. Range and rate are for the **worst-case low-power
LR2021 board at +22 dBm**; the **F33** column is what the same rig does with the high-power board.

| # | Option | Rig | Total € | What it buys (low-power board, +22 dBm) | With the F33 (+33 dBm) | 433 gain |
|---|---|---|---|---|---|---|
| **A** | **CHEAPEST REPLICABLE** | `Diamond A-430S10R` (13.1 dBi, €69) + DIY **P1** tracker (€429) + boresighted 0.6 m 2.4 GHz dish | **≈ €650** | **2.6 Mbps to 123 km**; 650 kbps to ~260 km; LoRa unlimited | **2.6 Mbps to 438 km** | 13.1 dBi |
| **B** | **BALANCED — RECOMMENDED** | `Diamond A-430S15R` (14.8 dBi, €74.50) + DIY **P2** tracker (€509) + 0.6 m 2.4 GHz dish | **≈ €735** | **2.6 Mbps to 150 km**; 650 kbps to ~317 km; LoRa unlimited | **2.6 Mbps to 532 km** | 14.8 dBi |
| **C** | **MAX GAIN-PER-EURO (Yagi)** | `FlexaYagi FX 7073` (18.0 dBi, €215) + Yaesu **G-5500DC** (€949) + 0.6 m dish | **≈ €1,316** | **2.6 Mbps to 217 km**; 650 kbps to ~460 km | **2.6 Mbps to 769 km** | 18.0 dBi |
| **D** | **MAX PERFORMANCE (dish), purchasable today** | RFH **1.9 m mesh FPD 1M9** (€901) + **SPID BIG-RAS** (€1,775) + 0.6 m dish | **≈ €2,878** | **2.6 Mbps to 190 km**; 650 kbps to ~415 km | **2.6 Mbps to 673 km** | 16.8 dBi |
| *(E)* | *gain-per-euro alternative* | *2 × `Sirio WY 400-10N` stacked (17.0 dBi, €310) + DIY P2 (€509) + 0.6 m dish* | *≈ €971* | *2.6 Mbps to 193 km* | *2.6 Mbps to 686 km* | *17.0 dBi |

**How to read it:** **Option D costs 3.9× option B and buys *less* gain (16.8 vs 14.8 dBi is
+2.0 dB) for 3.9× the money — and it is only 1.2 dB better than option C while costing 2.2×
more.** Option E is the honest "more gain without the Yaesu jump": a stacked Yagi pair beats
option D on **both** gain (17.0 > 16.84) and cost (€971 < €2,878).

**Recommendation: Option B** (best €/(kbps·km) at 0.0019 with the lowest absolute cost in the
top group), **with Option C or E if the operator wants the extra 3 dB and the ~460 km FLRC
range**, and **the F33 fitted regardless** — it dominates every option on gain-per-euro.

---

## 8. Open items / `TODO(unverified)`

1. **`TODO(unverified)`** a **433 MHz prime-focus dish feed** — none exists as a product; the
   €50 feed line in `EUR_total` is a **DIY ESTIMATE** (`flrc-max` §8 item 2).
2. **REPO DEFECT, flagged not resolved:** **SPX-06 is €5,487 with a 716 N·m published rating,
   BIG-RAS is €1,775 with a 2,712 N·m brake** — the price and rating orderings disagree. The
   bases differ (slew rating vs brake). Per the repo rule a contradiction with no named winner
   is a defect; this document uses BIG-RAS wherever its brake holds and does not pick a winner.
3. **`TODO(unverified)`** the **former/rib set** for a >1.9 m DIY 433 dish — no vendor sells
   ribs without mesh; the ≥2.4 m kits are out of stock (`flrc-max` §4.4/§8 item 3).
4. **`TODO(unverified)`** **NEMA23 / NEMA34 closed-loop stepper prices** — the StepperOnline
   category pages did not render prices to this session's fetch (their NEMA 8/11/17 CL,
   driver and servo-kit prices **were** read and are cited in §5.2).
5. **`TODO(unverified)`** **AS5600 / AS5048 / MT6701 module prices** — retail pages bot-walled;
   resolutions are cited from `positioner-lowcost` §8, the price is not.
6. **`TODO(unverified)`** **PCBWay / JLCPCB sheet-metal** capability and pricing — their
   sheet-metal URLs returned HTTP 404; **not** cited as a metal service.
7. **`TODO(unverified)`** a **waterjet** shop with published per-part prices (the German site
   tried is a parked domain); only Xometry's waterjet service is cited, with no price.
8. **`TODO(unverified)`** a **433 MHz-specific FLRC sensitivity row** (915 MHz datasheet rows
   used; inherited from `flrc-max` §8 item 1).
9. **ESTIMATE, not sourced:** Yagi effective wind area (0.15 m²), the €50 433 feed, the €100
   mast, the €30 build allowance, `L_impl` = 2.6 dB, `M_fade` = 6 dB, and the §3.2 metal part
   costs (extrapolated from SendCutSend's single published example).
10. **`TODO(unverified)`** the DE amateur-licence / airborne-SRD position for a +33 dBm
    airborne 433 transmitter (ADR-039 open item (a)) — **inherited; it is the binding
    constraint on the F33 half of this recommendation.**
11. **Repo contradiction, flagged:** `docs/PAYLOAD-WEIGHT-ESTIMATES.md` §D classifies the F33
    board as "Ground Station Only … not a pico balloon target" — inherited from `flrc-max`
    REC-6, and it must be resolved by an ADR before the F33 goes on the balloon.
12. **Not modelled:** the 0.6 m 2.4 GHz dish's own mass/blockage effect on the shared
    positioner (treated as already inside the baseline rig, `positioner-lowcost` §4).

---

## 9. Sources and reproduction

**Reproduce every numeric table:**

```bash
python3 docs/analysis/ground_station_gain_per_dollar_model.py
```

It prints §1.6, §2.0–§2.7 verbatim. All constants sit at the top of the file with their
provenance. **No datasheet value or vendor URL in this document was invented**; where a number
could not be sourced it is marked `TODO(unverified)` and no conclusion depends on it.

**Prior art read (not re-derived):**

| Branch (commit) | Path | What was taken |
|---|---|---|
| `design/ground-station-bom` (`283cad72`) | `docs/analysis/ground-station-bom-candidates.md` | all Yagi/dish/rotator/coax prices + URLs + wind-area ratings |
| `design/ground-station-lowpower-link` (`4b90be94`) | `docs/analysis/ground-station-lowpower-link-and-shared-dish.md` | LR2021 sensitivities, TX power points, the LoRa/FLRC 36 dB gap, the 2.4 GHz negative-required-gain result |
| `design/positioner-lowcost` | `docs/analysis/positioner-lowcost-3dprinted.md` | the DIY tracker BOM (€279/€429/€509), NMRV self-locking/hold torques, back-driving, stow policy, backlash vs budget, encoders, anemometer, its consultant verdict |
| `design/ground-station-flrc-max` | `docs/analysis/ground-station-flrc-max-throughput.md` | mesh vs solid wind multiples, σ = 0.265, Cd = 1.38 derivation, mesh-dish inventory + availability, the F33 route, its consultant verdict |

**External sources fetched this session (HTTP 200 unless noted):**
Xometry sheet metal (`https://www.xometry.com/capabilities/sheet-metal-fabrication/`),
Protolabs (`https://www.protolabs.com/services/sheet-metal-fabrication/`),
SendCutSend pricing + materials (`https://sendcutsend.com/pricing/`, `/materials/`),
Schaeffer AG prices (`https://www.schaeffer-ag.de/support/preise-und-versand`),
247TailorSteel (`https://www.247tailorsteel.com/en`),
Laserhub (`https://www.laserhub.com/`),
Cutworks (`https://www.cutworks.com/de/infos/preise-und-rabatte/`),
Blechking (`https://blechking.de/Bleche-kaufen`),
metal-market.eu mesh (`https://metal-market.eu/collections/schweissgitter`),
StepperOnline closed-loop motor/kit/encoder/servo categories
(`https://www.omc-stepperonline.com/closed-loop-stepper-motor`, `/closed-loop-stepper-kit`,
`/encoder`). **Blocked/gated this session → no value invented:** DuckDuckGo HTML/Lite
(challenge, HTTP 202), Mojeek (captcha), DigiKey/Mouser (403/denied),
`pcbway.com`/`jlcpcb.com` sheet-metal pages (404), `wasserstrahlschneiden24.de` (parked
domain). All web fetches used a browser User-Agent + `curl --compressed`.

---

## 10. Independent consultation (visual consultant) — metric and ranking challenge

**Consultant route:** `scripts/fleet/visual_consult.py` (fleet script; manifest
`/home/c03rad0r/hermes-orchestration/scripts/fleet/visual_consult.py`), per the
`visual-consultant` skill. This consult was asked to **challenge the metric itself and the
ranking**, not to review a figure's layout.

**Engagement status:** _(pending — recorded verbatim below; if the lane cannot be reached, the
failure is recorded verbatim and no verdict is claimed.)_

**Served model (read back from the response `resp["model"]`, never the alias):** _(pending)_

**Verdict line (verbatim):** _(pending)_

**Consultant answer (verbatim):** _(pending)_

---

*End of analysis.*

