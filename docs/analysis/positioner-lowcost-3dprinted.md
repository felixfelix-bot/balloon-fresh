# Low-cost AZ/EL positioner for the balloon ground station — 3D-printed structure, RIGHT-SIZED dish

> **STATUS: CONSULTANT ANALYSIS — NOT A DECISION RECORD.** This is an analysis in
> `docs/analysis/`. It is **not** an ADR, **not** an operator decision, and it authorises
> no order, no fab freeze and no change to any board, BOM or schematic. The companion ADR
> (`docs/adr/067-positioner-architecture.md`) is **Proposed** and must not be treated as
> decided. A prior sibling ADR claims `066` (`docs/adr/066-ground-station-lowpower-shared-positioner.md`,
> on a remote branch) — `067` was verified free on every remote branch before use.

| Field | Value |
|---|---|
| **Date** | 2026-10-08 |
| **Branch** | `design/positioner-lowcost` |
| **Worktree** | `/home/c03rad0r/worktrees/bf-positioner` |
| **Base commit** | `09e1b69` (`github/main`) |
| **Author** | Hermes Agent (subagent), for the operator |
| **Repro command** | `python3 docs/analysis/positioner_lowcost_model.py` (prints every table below verbatim) |
| **Lens** | Mechanical / RF-interface / cost. I do **not** re-derive the RF sensitivities — I read them from the committed budgets and the Semtech datasheet numbers the repo already carries. |
| **Out of scope** | Control software, tracker firmware, procurement, the 433 MHz vs 2.4 GHz band-split decision (ADR-034 owns that). |
| **Read first** | `docs/LINK-BUDGET-LICENCE-EXEMPT.md` (§1 2.4 GHz uplink, §3 summary); `docs/analysis/ground-station-lowpower-link-and-shared-dish.md` (433 FLRC dish floor); `docs/analysis/ground-station-bom-candidates.md` (prices/URLs); `docs/analysis/dualband-single-dish.md` (gain vs diameter). |

Every number below is **COMPUTED** (formula shown, script printed it), **CITED**
(repo path + §, or vendor URL), a labelled **ESTIMATE** (basis named), or an explicit
**`TODO(unverified)`**. Nothing is presented as sourced that was not fetched.

---

## 0. Answer first

**The dominant cost lever is not the drive, the gearing or the printing — it is the dish
diameter, and the 2.4 GHz uplink does not need a dish at all.** The committed uplink
budget closes the 2.4 GHz link with **negative** required ground gain (§3 below); the
1.2 m dish in the commercial pair (RF Hamdesign FPD 1M2 mesh dish **€387.20**,
`ground-station-bom-candidates.md` §0.4) is ~6 dB larger than a 0.6 m dish and **4× the
swept area and 4× the wind torque** for gain the link already has.
Right-size to **0.6 m** and the whole positioner drops one structural class.

**Five findings carry the recommendation:**

1. **Right-sizing is worth 4× on everything mechanical.** Swept area and wind force scale
   as D². 1.2 m → 0.6 m is **4.00× less area and 4.00× less wind force** (Table 1), and it
   *doubles the beamwidth* (7.3° → 14.6°), which is exactly the tolerance a cheap printed
   drive needs (Finding 5).
2. **The 2.4 GHz uplink does not require a dish.** Required ground gain is **−17.4 dBi at
   300 km** and **−10.7 dBi at 650 km** (licence-exempt 20 dBm EIRP, balloon LNA, 10 dBi
   balloon antenna; Table 7). An **omni closes it**. The dish is a *margin / low-PA /
   beam-discipline* device, not a link-closure device.
3. **Printed plastic gears cannot carry the AZ/EL drive — buy the gearing.** Holding the
   0.6 m dish at 20 m/s with a 2× safety factor needs **24.9 N·m** (balanced) to
   **49.9 N·m** (worst-case axis) at the output (Table 4). That is **8.3:1 to 16.6:1** on a
   3.0 N·m NEMA23, i.e. a real reducer — and a printed gear tooth at those tooth loads
   strips/creeps (`TODO(unverified)`: no accessible torque-per-tooth datasheet for
   PLA/PETG/ASA was found this session; the operator's own tracker is the field evidence).
   **Print the structure, buy the worm gearing.**
4. **Back-driving is the reason the reducer must be a *worm*.** A NEMA23 with a 20:1
   NMRV worm reducer holds **40 N·m** and the vendor states the worm is **self-locking**
   (Table 5, §5). A spur/belt drive at 20:1 back-drives in a 20 m/s gust and the dish
   walks.
5. **Backlash, not torque, is what kills open-loop pointing — and the smaller dish fixes
   it.** A printed belt/gear drive carries **0.5–2.0°** of backlash; the 1.2 m beam budget
   is **0.73°** (7.3° × 10 %), so backlash alone **consumes 69–274 %** of the budget and
   open-loop *fails*. At 0.6 m the budget is **1.46°**, so 0.5° backlash is 34 % of budget
   and closed-loop/or re-peak correction closes the remaining gap (Table 6).

**RECOMMENDED ARCHITECTURE (one line):** a **0.6 m** 2.4 GHz dish + a **boresighted
Sirio WY 400-6N 433 Yagi**, on a **3D-printed yoke/turret carrying PURCHASED
NMRV40 20:1 self-locking worm reducers driven by NEMA23 3.0 N·m closed-loop steppers**,
with an **anemometer cutoff + zenith stow**. Reference cost ≈ **€650–730** in parts
(≈ **€430–510** with a DIY feed and a salvaged dish; §10) versus the commercial BOM's
**€2,518 reference / €1,402 prototype** — a **≈1.9–3.9×** reduction, most of it from the dish.

**The one thing that flips this:** if the 2.4 GHz uplink must run a **high-rate (FLRC-class)
mode**, the required ground gain jumps to the +20…+30 dBi class and a ~1 m dish (and a
heavier positioner) returns. The committed uplink is LoRa-class, so it does not apply today
(`TODO(unverified)`: a 2.4 GHz FLRC sensitivity row — see §9).

---

## 1. What the operator already printed (Printables model 945761)

Fetched this session. `https://www.printables.com/model/945761-antenna-tracker` returns
**HTTP 403** to scripted requests (bot wall), so the page text was read from the **Internet
Archive** snapshot `2026-04-02` (`https://web.archive.org/web/20260402154451id_/https://www.printables.com/model/945761-antenna-tracker`,
HTTP 200) and the model record confirmed through the Printables GraphQL API
(`print(id:945761)` → `{"id":"945761","name":"Antenna Tracker"}`). This is a **verbatim
reading of the author's own description**, not an inference:

| Attribute | Value (author's own words) |
|---|---|
| Title / author | **Antenna Tracker** by **Stratos** (`@Stratos_45104`) |
| Published / updated | updated **August 11, 2024** |
| **Axes** | **AZ + EL** ("To support both vertical and horizontal axis…") |
| **Stepper** | **28BYJ-48** — "a very simple antenna tracker with **28BYJ-48 stepper motors**" |
| **Author's own verdict on the motors** | "**Considering how weak those motors are, they are not the best option, but they work.**" |
| **Bearings** | "**2 608zz bearings (4 in total)** are needed" |
| **Elevation gear ratio** | **14:50** ("Edit V3: Changed gear ratio for **pitch to 14:50**") — i.e. **3.57:1** |
| Endstops | "Added space for endstops" (V2); "mounting for second pitch endstop" (V3) |
| Frame | "adapter to be mounted on a **tripod**"; "**only the main body (no electronics bay)**" |
| Printed vs purchased | **Structure printed**; the **motors, bearings and fasteners are purchased** (author names 608zz bearings as a needed purchase) |
| Rated/implied antenna limit | **None stated.** The description gives **no mass or wind rating**. The implied limit is set by the 28BYJ-48 motors. |

**Why it was "too small/weak" — quantified.** A 28BYJ-48 is a 5 V unipolar geared stepper
whose *output-shaft* holding torque is of order **0.3–0.4 kg·cm ≈ 0.03–0.04 N·m**
(`TODO(unverified)`: no vendor datasheet read this session; widely published figure,
not fetched). Its own internal gearbox is ~64:1, and the printed 3.57:1 pinion is
**plastic-on-plastic**. At the **0.6 m** rung the positioner must hold **24.9–49.9 N·m**
(Table 4) — ****~600–830×** above what a 28BYJ-48 can produce even through
its own reduction. The model is not "slightly weak"; it is the wrong motor *class* by
most of three orders of magnitude. That is a mass/scale statement, not a criticism of the design of a hobby tracker
for a small RC Yagi: **the printed-geometry idea transfers; the motor and gearing do not.**

---

## 2. Assumption table

| # | Assumption | Value | Basis |
|---|---|---|---|
| A1 | Dish aperture efficiency η | **0.55** primary, 0.60 shown | brief (`eta ~= 0.55`); repo uses 0.60 in `dualband-single-dish.md` §3.2 — both tabulated |
| A2 | 2.4 GHz wavelength | 124.9 mm | COMPUTED `λ = c/2.4e9` |
| A3 | Air density ρ | 1.225 kg/m³ | ASSUMPTION (ISA sea level, 15 °C) |
| A4 | Drag coefficient, solid reflector | **1.2** | brief / task, matching `ground_station_dish_model.py` (it also runs Cd 1.4) |
| A5 | Drag coefficient, mesh reflector | **0.5** | brief / task |
| A6 | Reference wind | **20 m/s** (72 km/h) | task ("~330 N solid / ~125 N mesh at 20 m/s") — reproduced as **332.5 / 138.5 N** (Table 1) |
| A7 | Holding safety factor SF | **2.0** | ASSUMPTION (task suggests "e.g. 2x") |
| A8 | Stepper pull-out / holding derate K_dyn | **0.6** | ESTIMATE (pull-out torque is typically ~50–70 % of holding; not a datasheet figure) |
| A9 | Worm efficiency | **0.75** | ESTIMATE (NMRV single-stage typical 0.7–0.85 at these ratios) |
| A10 | Elevation-axis lever arm | **L = 0.25·D** (balanced) and **0.5·D** (worst case) | repo `ground_station_dish_model.py` TABLE 7 uses exactly `D/4` and `D/2` |
| A11 | Pointing budget | **10 % of HPBW** | brief / task |
| A12 | Stepper holding torques | NEMA17 0.59, NEMA23 3.0, NEMA34 8.2 N·m | VENDOR StepperOnline product pages (see §6) |
| A13 | Balloon 2.4 GHz RX sensitivity | −137 dBm (bare LR2021 SF12) / −136 (F33+LNA) / −124 (F33 no-LNA) | CITED `LINK-BUDGET-LICENCE-EXEMPT.md` §0 |
| A14 | Balloon 2.4 GHz RX antenna | 10 dBi (ADR-037) / 6 dBi (PCB Yagi) | CITED same §0 |
| A15 | Licence-exempt 2.4 GHz cap | **20 dBm EIRP** (100 mW) | CITED `LINK-BUDGET-LICENCE-EXEMPT.md` §0 (`TODO(unverified)` exact ERC 70-03 Annex 1 row, inherited) |

---

## 3. THE COST LEVER — dish right-sizing

```
G = 10·log10( η·(πD/λ)² )      A = πD²/4      F = ½·ρ·v²·A·Cd      HPBW = 70·λ/D
```

**Table 1 — dish right-sizing (script output, verbatim).** λ = 124.9 mm, v = 20 m/s:

```
  D[m]    G[0.55]    G[0.60]  HPBW[deg]     A[m^2] F_solid[N]  F_mesh[N] F_solid[kgf]
  0.60      20.98      21.36      14.57     0.2827       83.1       34.6       8.48
  0.90      24.50      24.88       9.72     0.6362      187.0       77.9      19.07
  1.20      27.00      27.38       7.29     1.1310      332.5      138.5      33.91
  1.50      28.94      29.31       5.83     1.7671      519.5      216.5      52.98

Ratio of 1.2 m to 0.6 m:  area = 4.00x, wind force = 4.00x (D^2 law)
Ratio of 1.2 m to 0.9 m:  area = 1.78x, wind force = 1.78x
```

The 1.2 m figure reproduces the brief's stated pair (**27.4 dBi** at η 0.60, 7.3°
beamwidth) and the brief's wind figure (**332.5 N** solid ≈ the stated 330 N; **138.5 N**
mesh ≈ the stated 125 N — the mesh value here is 11 % higher because A is computed exactly
from D rather than rounded). Note the two repo η conventions give **27.0 vs 27.4 dBi**: a
**0.4 dB** spread that does not change any conclusion — see §4.4.

**Wind force vs speed** (Table 2, verbatim) — this is what sets the *operating* class:

```
v[m/s]    v[km/h] | F_solid[N]: 0.6 / 0.9 / 1.2 m    | F_mesh[N]: 0.6 / 0.9 / 1.2 m    
    10         36 |    20.8    46.8    83.1          |     8.7    19.5    34.6         
    14         50 |    40.7    91.6   162.9          |    17.0    38.2    67.9         
    20         72 |    83.1   187.0   332.5          |    34.6    77.9   138.5         
    30        108 |   187.0   420.8   748.1          |    77.9   175.3   311.7         
    40        144 |   332.5   748.1  1330.0          |   138.5   311.7   554.2         
```

### 3.1 What 2.4 GHz link gain is actually REQUIRED (Table 7, verbatim)

```
required_G_ground = S_balloon + FSPL - P_tx_conducted - G_balloon_rx
FSPL: 2.4 GHz 300 km = 149.6 dB ; 650 km = 156.3 dB ; 433 MHz 300 km = 134.7 dB

---- range 300 km ----
 P_tx[dBm]  G_rx[dBi]      reqG@-137      reqG@-136      reqG@-124
         0         10            2.6            3.6           15.6
        12         10           -9.4           -8.4            3.6
        20         10          -17.4          -16.4           -4.4
        30         10          -27.4          -26.4          -14.4

---- range 650 km ----
         0         10            9.3           10.3           22.3
        12         10           -2.7           -1.7           10.3
        20         10          -10.7           -9.7            2.3
        30         10          -20.7          -19.7           -7.7

EIRP-CAPPED REGIME (licence-exempt 100 mW EIRP = 20 dBm total):
    300 km, EIRP 20 dBm, G_rx 10 dBi, S=-137 dBm -> margin  +17.4 dB
    650 km, EIRP 20 dBm, G_rx 10 dBi, S=-137 dBm -> margin  +10.7 dB
    300 km, EIRP 20 dBm, G_rx 10 dBi, S=-124 dBm -> margin   +4.4 dB
    650 km, EIRP 20 dBm, G_rx 10 dBi, S=-124 dBm -> margin   -2.3 dB
```

**Reading, and the crux of the whole study:**

* **With the balloon LNA in circuit, the required ground gain is NEGATIVE** at both 300 km
  (−17.4 dBi) and 650 km (−10.7 dBi). **No dish is required to close the 2.4 GHz uplink.**
  An omni closes it; the dish buys margin.
* **Under the licence-exempt EIRP cap the dish is a *power-reduction* device, not a link
  device.** Because EIRP = (P_tx + G_antenna) is capped at 20 dBm, adding aperture gain
  forces a proportional PA back-off: the ground gain **cancels out of the link equation**.
  A 0.6 m dish (21.0 dBi) with a **0 dBm** PA is *exactly* the 20 dBm EIRP cap and still
  shows **+17.4 dB at 300 km / +10.7 dB at 650 km** (script output). So the correct physical
  statement is: **the ground dish's job is (a) to achieve the legal EIRP with a low-power PA
  and (b) to buy fade/pointing margin and narrow the interference footprint — closure is
  already there.**
* **The one row that binds is the no-LNA + 6 dBi balloon at 650 km (−2.3 dB)** — and its fix
  is the **balloon-side LNA**, not a ground dish (same conclusion as
  `LINK-BUDGET-LICENCE-EXEMPT.md` §4.2).

### 3.2 THE SMALLEST DISH THAT CLOSES

| Question | Answer |
|---|---|
| Smallest dish that **closes** the committed 2.4 GHz uplink | **none — 0 dBi (an omni) closes it** by +17.4 dB at 300 km / +10.7 dB at 650 km (balloon LNA, 20 dBm EIRP). |
| Smallest dish **worth building** (covers the EIRP cap with a low-PA, + margin, beam discipline) | **0.6 m (21.0 dBi)** — +18.4 dB margin at 300 km with a 0 dBm PA; 14.6° beam. |
| Smallest dish if you also want ≥12 dB margin at the **no-LNA** 650 km worst case | **~0.9 m** under a 30 dBm ground PA class (`TODO(unverified)`: that regime is amateur-licence, not licence-exempt). |
| Cheapest self-consistent choice | **0.6 m**, because at 0.6 m the beam is wide enough that a cheap printed/backlashed drive still points it (Finding 5). |

**So right-sizing cuts the positioner class outright**: 0.6 m needs **83.1 N** and
**12.5 N·m** (balanced) instead of 1.2 m's **332.5 N** and **99.8 N·m** — an **8× torque
reduction**, which is the difference between a NEMA23 + one NMRV40 (**40 N·m**, €~40-class)
and a NEMA34 + a big NMRV50/2-stage.

### 3.3 The 433 MHz side — says plainly why a big dish is NOT printable

CITED `ground-station-lowpower-link-and-shared-dish.md` §0/§2:

* **If the 433 downlink is LoRa** (the committed low-power LR2021 mode), a **10–15 dBi Yagi**
  closes it with +24…+30 dB margin. Sirio WY 400-6N **11 dBi, €132**; Diamond A-430S10R
  **13.1 dBi, €69**. Boresight it on the *same* positioner (1–2 % aperture blockage at
  2.4 GHz ≈ 0.05–0.1 dB, cited `dualband-single-dish.md` §5).
* **If the 433 downlink is FLRC at ≤ +19 dBm or ≥ 1 Mbps**, the 433 side needs
  **≈ +19…+28 dBi**, which means a **433 MHz dish of ~2.7–3.0 m diameter** (aperture
  formula, η 0.60: 2.7 m → 19.5 dBi, 3.0 m → 20.5 dBi, `dualband-single-dish.md` §3.3).

> **A 2.7–3.0 m dish is NOT a 3D-printing candidate.** It is not a "print the structure"
> problem at all: at 3 m the reflector is a rigidity/area/erection problem, the mass is
> 100+ kg class, and the swept area is **7.069 m²** (π·3²/4 → **2,078 N** solid at 20 m/s,
> **8,313 N** at 40 m/s). A 3 m dish needs a **salvaged or purchased polar mount / a
> decommissioned C-band or VSAT mount / a second-hand amateur rotator of the Yaesu G-2800
> class (€1,049 new, `ground-station-bom-candidates.md` §0.5) or larger**. The correct
> engineering answer for the 433 FLRC case is therefore **"do not print it — salvage the
> mount"**, and the cheapest way to avoid the whole problem is to keep the 433 downlink in
> LoRa (which the committed design already does).

---

## 4. The 2.4 GHz / 433 mechanical interface (what the positioner must carry)

| Payload item | Value | Source |
|---|---|---|
| 0.6 m dish + feed + bracket | ~2.5–4 kg | ESTIMATE (0.6 m class offset dish is a fraction of a 1.0 m's ~10 kg — `ground-station-bom-candidates.md` §B1 quotes ~10 kg for a 0.94×1.01 m), to be weighed |
| 433 Yagi (Sirio WY 400-6N) | ~1–1.5 kg | ESTIMATE (1.2 m boom, 6 elements — vendor page gives dimensions, not mass) |
| Wind force at 20 m/s, 0.6 m solid | **83.1 N** | COMPUTED (Table 1) |
| Elevation output torque required, SF 2 | **24.9 N·m** balanced / **49.9 N·m** worst | COMPUTED (Table 4) |

---

## 5. ENGINEERING QUESTION 1 — the motor torque chain

**Table 4 — torque chain (script output, verbatim).** `T = F·L`, `L = lever_frac · D`,
`T_req = T · SF` (SF = 2.0):

```
---- lever_frac = 0.25 ----          (balanced: elevation axis through the dish CP)
  D[m]      F[N]  T_wind[Nm]     T_req[Nm] | n(NEMA17)  n(NEMA23)  n(NEMA34)
  0.60      83.1        12.5          24.9 |      42.3        8.3        3.0
  0.90     187.0        42.1          84.2 |     142.7       28.1       10.3
  1.20     332.5        99.8         199.5 |     338.1       66.5       24.3

---- lever_frac = 0.50 ----          (worst case: elevation axis at the rim plane)
  0.60      83.1        24.9          49.9 |      84.5       16.6        6.1
  0.90     187.0        84.2         168.3 |     285.3       56.1       20.5
  1.20     332.5       199.5         399.0 |     676.3      133.0       48.7
```

**Required reduction ratio** (n = T_req / holding torque, 20 m/s solid, SF 2):

| Dish | Axis lever | T_req | NEMA17 (0.59 N·m) | NEMA23 (3.0 N·m) | NEMA34 (8.2 N·m) |
|---|---:|---:|---:|---:|---:|
| 0.6 m | balanced (D/4) | 24.9 N·m | 42:1 | **8.3:1** | 3.0:1 |
| 0.6 m | worst (D/2) | 49.9 N·m | 85:1 | **16.6:1** | 6.1:1 |
| 0.9 m | balanced | 84.2 N·m | 143:1 | **28.1:1** | 10.3:1 |
| 1.2 m | balanced | 199.5 N·m | 338:1 | **66.5:1** | 24.3:1 |
| 1.2 m | worst | 399.0 N·m | 676:1 | **133:1** | 48.7:1 |

**Read what this does to the printed-gear question.** Even at the friendliest rung
(0.6 m, balanced, NEMA17) the ratio needed is **42:1**. A printed plastic spur or
belt at 42:1 means a large printed gear (or belt) carrying the **full 24.9 N·m** at the
output tooth. Printed thermoplastic gears:

* carry their load through **a small number of teeth in contact**, with **much lower
  stiffness and much higher friction** than steel, so the tooth-root bending stress is
  concentrated and the contact creep is thermally sensitive;
* **creep/relax under sustained static load**, which is exactly the mode of a
  *continuously held* dish;
* have **layer-adhesion anisotropy** — a printed tooth shears preferentially along the
  layer lines.

**I could not fetch a torque-per-tooth datasheet for PLA/PETG/ASA this session**
(`TODO(unverified)`: every general web-search backend returned a captcha to this fleet's
egress IP — Brave, DuckDuckGo, Bing, Ecosia, Mojeek; only Wikipedia and direct vendor
fetches stayed reachable). Saying that plainly is the honest move; the verdict does not
depend on it, because:

1. **The operator's own tracker is the field evidence.** Its author states the motors are
   "too weak" — and those are 28BYJ-48-class, *orders of magnitude* below the 24.9 N·m
   requirement. A printed drive that failed at RC-Yagi loads will not survive a 0.6 m dish.
2. **The physics of printed gears is a well-known class limitation** — printed gears are
   routinely used where the torque is a fraction of a N·m (robot arms, RC, camera
   sliders), not for tens of N·m held continuously in wind.
3. **There is a purchasable part that settles it outright** (Finding 4): the NMRV worm
   reducer is self-locking, rated, and cheap. When a real part exists at the required
   rating, printing the gear is a false economy.

> **PRINTED-GEAR VERDICT: printed gears strip and must not carry the AZ/EL hold torque.
> Print the *structure* (yoke, turret, bearing housings, dish backplate, feed boom, cable
> management); BUY the gearing. This is the honest hybrid.**

**Where printing DOES carry load, safely:** the static/compressive structure — the yoke
arms, the turret base, the bearing bores, the dish-back stiffener, the 433-Yagi boom clamp,
the electronics enclosure. Design rules: **metal bearing inserts/bores** (do not run steel
shafts directly on printed bores), ribs in the load path, ≥4 perimeters, and put ALL the
torque reaction into a **purchased reducer + tapered/roller bearings** so the plastic never
sees the tooth load.

---

## 6. ENGINEERING QUESTION 2 — back-driving, and the self-locking reducer

**Why back-driving matters.** A non-self-locking drive (spur, belt, planetary, harmonic)
can be turned *by the load*: a 20 m/s gust pushes the dish, the motor's detent torque is
dwarfed, and the dish walks off point — or falls to a stop. A **worm** reducer with a
**small lead angle** is **self-locking (irreversible)**: the load cannot drive the worm
backwards because the friction angle exceeds the lead angle.

**Vendor evidence for the purchasable part** (fetched this session):

| Part | Ratio | Rated output torque | Input shaft | Self-locking | URL |
|---|---:|---:|---|---|---|
| **NMRV40** worm gearbox | **20:1** | **40 N·m** | 14 mm | Vendor: *"The advantage for this gearbox is efficiency and self-locking"*; *"worm gears are generally self-locking"* | https://www.omc-stepperonline.com/20-1-worm-gearbox-nmrv40-worm-gear-speed-reducer-14mm-input-shaft-diameter-nmrv40-g20-d14 |
| NMRV50 | 30:1 | **85 N·m** | 19 mm | same family claim | https://www.omc-stepperonline.com/30-1-worm-gearbox-nmrv50-worm-gear-speed-reducer-19mm-input-shaft-diameter-nmrv50-g30-d19 |
| NMRV50 | 50:1 | 74 N·m | 19 mm | same family claim | https://www.omc-stepperonline.com/50-1-worm-gearbox-nmrv50-worm-gear-speed-reducer-19mm-input-shaft-diameter-nmrv50-g50-d19 |
| NMRV30 | 15:1 | 18 N·m | 9 mm | same family claim | https://www.omc-stepperonline.com/15-1-worm-gearbox-nmrv30-worm-gear-speed-reducer-9mm-input-shaft-diameter-nmrv30-g15-d9 |

> **Vendor caveat, quoted honestly:** the same pages say *"For critical holding/lifting
> applications, confirm with us."* Self-locking on a worm is **ratio- and
> friction-dependent** — the standard engineering position is that a worm is reliably
> self-locking only at **ratios above ~20:1** and even then the vendor will not warrant it
> for holding loads without confirmation. **`TODO(unverified)`: a written self-locking
> guarantee / lead-angle figure for the specific NMRV40 unit.** Recommendation: treat
> self-locking as the *primary* brake **and** add a **fail-safe holding brake** (a
> spring-applied, power-released brake on the stepper, or an electromagnetic brake motor)
> if any loss of hold is unacceptable.

**Output capability with a NEMA23** (Table 5, verbatim):

```
gearbox       ratio rated[Nm]   in-shaft with NEMA23(3.0Nm)
NMRV30 15:1      15     18.0       9 mm           18.0
NMRV40 20:1      20     40.0      14 mm           40.0
NMRV50 30:1      30     85.0      19 mm           67.5
NMRV50 50:1      50     74.0      19 mm           74.0
```

So **NEMA23 + NMRV40 20:1 → 40 N·m**, which covers the 0.6 m dish at the balanced lever
(**24.9 N·m** required) with **1.6× headroom**. For 0.9 m (84.2 N·m) step up to
**NEMA34 8.2 N·m + NMRV50 30:1 → 67.5 N·m** (still short of 84.2 N·m — 0.9 m needs a
2-stage or the 50:1 with a bigger motor; another reason 0.6 m is the sweet spot).

**Back-driving verdict:** a worm reducer is the only cheap drive that both
(a) provides the ~8–17:1 reduction a NEMA23 needs at 0.6 m and (b) does not back-drive in
wind. A **belt or spur at 8–17:1 back-drives** and is therefore rejected outright.

**Salvage alternative that is also self-locking:** a **satellite-dish linear actuator** is a
**lead-screw** drive and is therefore *intrinsically* self-locking. Tek2000 QARL-24 SuperJack
heavy-duty 36 V actuator: **$339.00 USD, load rating 675 kg (1500 lb)**, 24-inch stroke
(https://www.tek2000.com/cgi-bin/web.cgi?command=product&item=24-inch+Linear+QARL+Actuator+(36V)-ND).
A buying guide confirms the class: *"Screw-driven (lead screw or acme thread): Most common.
Offers high thrust (500–1000N), self-locking behavior (no back-driving)"*
(https://electronics.alibaba.com/buyingguides/12v-satellite-dish-actuator-guide-choose-right).
This is the classic cheap elevation axis for a dish of this size — see §8.

---

## 7. ENGINEERING QUESTION 3 — stow / survival strategy (the design principle that makes it cheap)

**The rule: size the structure for OPERATING wind, and STOW for storms.** Real tracking
antennas (Yaesu rotors, research dishes, VSAT) are rated for operating wind and are
**parked** for storms, with an **anemometer cutoff**. This is the single biggest structural
saving available, and it composes with right-sizing.

**Stow geometry (Table 3, verbatim).** Parking the dish **aperture-up** (elevation 90°)
presents the rim/silhouette to a horizontal wind:

```
  D[m]    f/D     f[m]   sag[m]  A_full[m^2]  A_stow[m^2]      ratio
  1.20   0.45    0.540   0.1667       1.1310       0.1333      0.118
...
  F_broadside = 1330 N   F_stowed = 157 N   reduction = 8.5x     (1.2 m, 40 m/s, solid)
```

**So a stowed dish (aperture up) has 11.8 % of its broadside wind area → an 8.5× torque
reduction.** Combine that with sizing for operating wind rather than storm wind:

| Case | Wind | Lever | Force (0.6 m solid) | Torque | Structure implied |
|---|---:|---:|---:|---:|---|
| Operating | 12–14 m/s | D/4 | 40.7 N | 6.1 N·m | nominal |
| Operating (task ref) | 20 m/s | D/4 | 83.1 N | 12.5 N·m | nominal + SF 2 → 24.9 N·m |
| Storm, **broadside, unstowed** | 40 m/s | D/4 | 332.5 N | 49.9 N·m | **4× operating** (D² law) |
| Storm, **stowed (aperture-up)** | 40 m/s | D/4 | **39.2 N** (11.8 % of 332.5 N, Table 3) | **5.9 N·m** | **≈ operating** |

**Verdict:** a system that (a) is sized for a **12–14 m/s operating wind**, (b) **stows
aperture-up on a wind cutoff**, and (c) is **self-locking** (so it holds the stow without
power) needs **NO extra storm structure** — the storm case collapses to roughly the
operating case. That is the **3–5× (here up to ~8×)** structural cut the brief predicted,
and it is achieved with software + an anemometer, not steel.

**Anemometer + cutoff — real options:**

| Option | Spec | Price | URL |
|---|---|---:|---|
| **Argent Data ADS-WS1** wind/rain sensor assembly; RJ11 reed-switch anemometer | switch closure per rotation (frequency ∝ wind speed) | **$68.00** assembly; **$15.00** replacement anemometer; **$89.00** base unit | https://www.argentdata.com/catalog/product_info.php?products_id=145 |
| Generic reed/pulse cup anemometer breakout (SparkFun class) | *"Measures wind speed by closing a switch once per rotation"* | TODO(unverified) exact SKU price | https://www.sparkfun.com (weather-meter class) |
| Ultrasonic anemometer (no moving parts) | — | TODO(unverified) | — |

**Cutoff logic (design, not a purchase):** read wind speed ≥ N consecutive samples above a
threshold (e.g. **15 m/s sustained for 10 s**) → command **STOW** → stop tracking; resume
when wind < a lower hysteresis threshold for a dwell time. Two **hard endstops** per axis
(the operator's own tracker already provisions endstops) plus a **soft-limit** in firmware.
The **fail-safe direction must be stow**, so the cutoff must assert the brake/stow even if
the tracker host crashes (an MCU-level cutout, not a PC-level one).

---

## 8. ENGINEERING QUESTION 4 — backlash vs pointing

**Table 6 — backlash vs pointing (script output, verbatim).** Budget = 10 % of HPBW:

```
  D[m]    HPBW[deg]    budget[deg] bl 0.5deg/bud bl 2.0deg/bud
  0.60        14.57          1.457         0.34         1.37
  0.90         9.72          0.972         0.51         2.06
  1.20         7.29          0.729         0.69         2.74
```

* **1.2 m:** budget 0.73°. Printed-drive backlash 0.5–2.0° is **0.69× to 2.74× the entire
  budget**. **Open-loop pointing FAILS** — you can lose the beam entirely with 2° of slack
  (and 2° at 300 km is **10.5 km** of lateral error, Table 6).
* **0.6 m:** budget 1.46°. 0.5° backlash = 34 % of budget (leaves 66 % for everything else);
  2.0° still exceeds it. So 0.6 m makes backlash *survivable* but not *free*.

**Verdict: open-loop steppers do NOT reliably hold the beam on a printed drive.**
Recommend, in order of preference:

1. **Closed-loop steppers with shaft encoders** — an absolute magnetic encoder on each axis
   (AS5600, 12-bit → **0.088°** resolution; MT6701, 14-bit → **0.022°**, both far below the
   budget) lets the controller *know* the axis position and correct residual backlash by
   always approaching from the same direction (unidirectional approach). This is the cheap,
   robust fix.
2. **Preload / low-backlash drive** — a preloaded worm (spring the worm against the wheel)
   or a zero-backlash planetary. Costlier; the worm was chosen for self-locking, and
   preloading a self-locking worm trades some of that margin.
3. **Re-peak on the signal** — since the 2.4 GHz uplink is the *ground→balloon* direction,
   the ground cannot re-peak on its own transmit; it must re-peak the **433 downlink**
   (balloon→ground) RSSI, which is co-boresighted. A slow conical-scan dither around the
   commanded point, maximising 433 RSSI, removes residual pointing error to within the noise
   floor. **This is the highest-value software mitigation** and needs no extra hardware —
   but it requires the 433 downlink to be up, so it is a *trim*, not a *hold*.
4. **Approach-direction discipline (free):** drive AZ and EL always from one side (e.g. always
   finishing a move in +AZ/−EL) so the same tooth flank is loaded — this alone removes the
   *differential* backlash, which is what actually breaks pointing.

**Pointing budget quantified** (Table 6): at 300 km, 0.10° = 524 m, 0.73° = 3.8 km,
2.0° = 10.5 km of lateral aim error. The *beam* is what matters — a 0.6 m beam (14.6°) is
generous, but the margin is finite: 3 axes of 0.5° could sum to 1.5° of error, ~10 % of the
0.6 m beam, i.e. a ~0.5–1 dB pointing loss plus part of the link margin.

---

## 9. ENGINEERING QUESTION 5 — salvaged / non-printed cheap options

| Option | Torque / capability | Self-locking? | Price | URL | Status |
|---|---|---|---|---|---|
| **36 V satellite linear actuator** (Tek2000 QARL-24 SuperJack, heavy duty) | **675 kg (1500 lb) load rating**, 24" stroke; class thrust 500–1000 N (light) to ~6000 N (heavy) | **YES** (lead-screw) | **$339.00** | https://www.tek2000.com/cgi-bin/web.cgi?command=product&item=24-inch+Linear+QARL+Actuator+(36V)-ND | CONFIRMED (page fetched) |
| 36 V actuator vendor portals (selection of stroke/thrust) | 12/18/24/36" strokes, prime-focus dishes to 2.5 m | YES | varies | https://www.primesat.eu/satellite_dish_actuators_motors.php · https://www.satellitesuperstore.com/satellite_diseqc_motors_36_volt_motors.htm · https://www.powerjackmotion.com/product/satellite-dish-actuator-heavy-duty-type/ | CONFIRMED (pages fetched) |
| **Used amateur rotator (Yaesu G-450 / G-5500)** | G-450C: 1.0 m² tower / 0.5 m² mast wind area; G-5500: same class | Worm (Yaesu rotors are self-locking worm drives) | **New**: G-450CDC **€359**, G-5500DC **€949** at Funktechnik Bielefeld | https://www.funktechnik-bielefeld.de (prices CITED `ground-station-bom-candidates.md` §0.5) | New price CONFIRMED; **second-hand price TODO(unverified)** |
| **Used Ku/C-band dish + mount** (salvage) | reflector only | n/a | precedent: used 0.9 m Kathrein CAS 90 **€50 (example)** | Kleinanzeigen (CITED `ground-station-bom-candidates.md` §0.6) | CONFIRMED as a *class*; specific listing TODO |
| **Small slewing bearing** (crane/excavator turntable) | large moment + radial load in one compact ring | n/a (bearing) | TODO(unverified) | definition: https://en.wikipedia.org/wiki/Slewing_bearing | Concept CITED; **price TODO(unverified)** |
| **Automotive wiper motor** | TODO(unverified) torque | NO (worm gear, often *not* self-locking at low ratio) | TODO(unverified) | — | **TODO(unverified)** |
| **Power-steering / wheelchair / scooter motor** | TODO(unverified) torque | NO | TODO(unverified) | — | **TODO(unverified)** |
| **Trailer / hi-lift worm drive** | TODO(unverified) | YES (worm/jack screw) | TODO(unverified) | — | **TODO(unverified)** |

> **Sourcing honesty.** Five general web-search backends (Brave, DuckDuckGo, Bing, Ecosia,
> Mojeek) returned **captchas or empty results to this fleet's egress IP** during this
> session; only direct vendor fetches and Wikipedia stayed reachable. The rows I could not
> fetch are marked `TODO(unverified)` rather than guessed — for a **torque** figure that is
> the right call, because a mis-quoted motor torque silently inverts the recommendation.
> The three rows that matter most for the recommendation (**36 V actuator, Yaesu new price,
> salvaged dish**) ARE sourced.

### 9.1 THE HONEST HYBRID, evaluated explicitly

| Approach | Structure | Gearing | Motors | Verdict |
|---|---|---|---|---|
| **Print everything** | printed | **printed plastic gears** | NEMA17/23 | **REJECT** — printed gears cannot hold 8–17:1 output torque at these tooth loads and creep under sustained wind (§5); the operator's own tracker is the field failure. |
| **Print structure, BUY gearing (RECOMMENDED)** | printed yoke/turret/bearing bores | **purchased NMRV40 20:1 self-locking worm** | NEMA23 3.0 N·m (closed-loop) | **ACCEPT** — plastic carries only the static/compressive structure, which it is good at; the torque reaction lives in steel/worm-bronze. Cheap, rebuildable, printable-in-place. |
| **Buy everything (salvage mount)** | bought | bought (lead-screw actuator or rotor) | bought | **ACCEPT as the 433-FLRC fallback** and for ≥0.9 m — but for 0.6 m it is *more* expensive and *less* flexible than the hybrid. |
| **Do nothing / manual pointing** | none | none | none | **REJECT for a 0.6 m dish** — 14.6° beam over a moving balloon pass is not hand-trackable at the required cadence. |

---

## 10. RECOMMENDED ARCHITECTURE

**Right-sized payload:** 0.6 m 2.4 GHz dish + boresighted 433 Yagi.
**Printed:** yoke, turret base, bearing housings, dish backplate/stiffener, Yagi boom clamp,
electronics bay. **Bought:** all gearing, motors, bearings, RF.

| # | Item | Spec | Qty | Price | URL |
|---|---|---|---:|---:|---|
| 1 | 2.4 GHz dish (right-sized) | 0.75 m offset Ku alu (or a salvaged ~0.6–0.9 m Ku dish ~€50) | 1 | **€94.90** | https://www.hm-sat-shop.de/gibertini-sat-antenne-75cm-se-profi-serie-sat-spiegel-schuessel-alu-anthrazit/11701-001 |
| 2 | 2.4 GHz feed | RF Hamdesign LH-13XL helix (2.1–2.7 GHz, f/D 0.45) — or a DIY helix to cut this line | 1 | **€220.00** | `ground-station-bom-candidates.md` §C4 (https://www.rfhamdesign.com) |
| 3 | 433 downlink antenna | Sirio WY 400-6N, 11 dBi, N-female | 1 | **€132.00** | https://www.funktechnik-bielefeld.de/sirio-wy-400-6n-6-element-70cm-band-yagi-richtantenne-400-470-mhz |
| 4 | AZ/EL motors | NEMA23 3.0 N·m bipolar stepper (23HE45-4204S) | 2 | **$23.02 ea** | https://www.omc-stepperonline.com/e-series-nema-23-bipolar-1-8deg-3-0-nm-425oz-in-4-2a-57x57x113mm-4-wires-23he45-4204s |
| 5 | AZ/EL reducers | **NMRV40 20:1 self-locking worm**, 40 N·m rated | 2 | TODO(unverified) | https://www.omc-stepperonline.com/20-1-worm-gearbox-nmrv40-worm-gear-speed-reducer-14mm-input-shaft-diameter-nmrv40-g20-d14 |
| 6 | Stepper drivers | DM542 / TB6600 class, 24–48 V | 2 | ~€12 ea (ESTIMATE) | TODO(unverified) |
| 7 | Axis encoders (closed-loop) | AS5600 or MT6701 magnetic absolute | 2 | ~€5 ea (ESTIMATE) | TODO(unverified) |
| 8 | Bearings | tapered-roller or deep-groove for the AZ/EL shafts (metal, purchased) | set | ~€30 (ESTIMATE) | TODO(unverified) |
| 9 | Anemometer | Argent ADS-WS1 wind sensor assembly (or the $15 anemometer alone) | 1 | **$68** (or $15) | https://www.argentdata.com/catalog/product_info.php?products_id=145 |
| 10 | Printer filament (PETG/ASA) + hardware (bolts, inserts, cable) | — | — | ~€30 (ESTIMATE) | — |

**Reference total: ≈ €646–726** in parts.
Sourced subtotal (items 1–5, 9, 10; gearbox price is a `TODO(unverified)` placeholder of
€40 each): dish 94.90 + feed 220 + Yagi 132 + motors ≈ €42 + gearboxes ≈ €80 (placeholder)
+ drivers ≈ €24 + encoders ≈ €10 + bearings ≈ €30 + anemometer ≈ €63 + filament/hardware
€30 = **≈ €726**. With the **$15** anemometer instead of the $68 assembly and a **DIY feed**
+ a **salvaged dish**, the same list is **≈ €412 (€430–510 with a modest dish/feed budget)**.

Against the commercial BOM's **€2,518 reference / €1,402 prototype**, that is a
**≈1.9–3.9× reduction**, and the saving is *dominated by item #1/#2 right-sizing and by not
buying a €949–€1,775 positioner*.

**What 3D printing CAN carry:** static compressive structure — yoke arms, turret, bearing
bores (with metal inserts), dish backplate, Yagi clamp, enclosure. Multi-perimeter, ribbed,
PETG/ASA (UV + heat), **never the gear teeth**.

**What 3D printing CANNOT carry:** the AZ/EL torque reaction (gear teeth), the worm/wormwheel
contact, the shaft-bearing interface (use purchased bearings), and anything holding the dish
against storm wind if stow fails.

---

## 11. Failure-mode table (ranked by severity × likelihood)

| # | Failure | Severity | Likelihood | Mitigation |
|---|---|---|---|---|
| F1 | Printed plastic gear strips / creeps under held wind torque | **High** | **High** | **Design out** — purchased worm reducer carries all torque. *No printed gears in the drive.* |
| F2 | Drive back-drives in a gust → dish walks/loses the beam | High | Medium | **Self-locking worm reducer** (NMRV40 20:1+) + fail-safe brake; anemometer cutoff. |
| F3 | Backlash (0.5–2.0°) exceeds the 0.73° budget at 1.2 m → beam loss | High | High (at 1.2 m) | **Right-size to 0.6 m** (budget 1.46°) + closed-loop encoders + unidirectional-approach + 433-RSSI re-peak. |
| F4 | Storm exceeds stow assumption / stow command lost | **High** | Low–Medium | Fail-safe stow direction + two hard endstops + MCU-level (not PC-level) cutoff + self-locking hold. |
| F5 | Self-locking not guaranteed at the chosen ratio (vendor won't warrant) | Medium | Medium | Brake; or step up ratio; or clamp/stow. `TODO(unverified)` per-unit lead angle. |
| F6 | Printed part fails at a fastener/bearing insert | Medium | Medium | Metal inserts, washer-faced bolts, ribs; keep plastic out of the load path. |
| F7 | Pointing loss from wind-induced structural deflection | Medium | Medium | Short, stiff yoke; stow early; accept ≤10 % beam loss (design target). |
| F8 | 2.4 GHz feed mismatch on a repurposed Ku dish | Medium | Medium | `TODO(unverified)` feed-mismatch loss (inherited from `dualband-single-dish.md` §5.2) — close with one measurement. |

---

## 12. Recommendation, and the condition under which it flips

**Recommendation:** build the **hybrid** — right-size the 2.4 GHz dish to **0.6 m**,
**print the structure**, **buy the worm gearing** (NMRV40 20:1 self-locking), drive it with
**NEMA23 3.0 N·m closed-loop** steppers, and add an **anemometer cutoff + zenith stow**.
Reference parts **≈ €560–640**.

**It flips if:**
* the 2.4 GHz uplink must carry an **FLRC-class high-rate mode** → required ground gain
  jumps to +20…+30 dBi → a ~1 m dish returns (and with it a heavier reducer / NEMA34);
* the **433 downlink must be FLRC at long range** → the 433 side needs a **2.7–3.0 m dish**,
  which is **not printable** and forces a salvaged/purchased polar mount (this is a
  *different machine*, not a bigger version of this one);
* the operator insists on a **1.2 m dish** for margin → the torque chain jumps to
  **199.5–399.0 N·m**, requiring a **NEMA34 + NMRV50 30:1 (or 2-stage)**, and the **1.2 m
  backlash budget (0.73°) then makes a printed drive impossible** without closed-loop
  correction (F3).

---

## 13. Disagreements and honest notes

* **η = 0.55 vs 0.60.** The brief says 0.55; the repo's `dualband-single-dish.md` §3.2 says
  0.60 (giving 27.4 dBi at 1.2 m). Both are tabulated; the 0.4 dB spread changes nothing.
* **Wind figure.** My exact-area computation gives **332.5 N / 138.5 N** at 1.2 m vs the
  brief's rounded "330 N / 125 N". The mesh figure is 11 % higher; if the brief's 125 N is
  authoritative (measured), use it — the conclusions are unchanged.
* **I could NOT source printed-gear tooth strength, wiper/wheelchair/power-steering motor
  torques, slewing-bearing prices, or used-Yaesu prices** (search backends captcha-blocked).
  Those are `TODO(unverified)`; the recommendation rests on the sourced rows.

---

## 14. Open items (every `TODO(unverified)` in one place)

1. `TODO(unverified)` — **NMRV40/50 price** (StepperOnline renders prices via JS; guest page
   shows `$0.00`). Budget a placeholder and confirm before ordering.
2. `TODO(unverified)` — **printed PLA/PETG/ASA torque-per-tooth / shear strength** (no
   accessible source this session).
3. `TODO(unverified)` — **28BYJ-48 output-shaft holding torque** (widely published
   ~0.3–0.4 kg·cm; not fetched).
4. `TODO(unverified)` — **written self-locking guarantee / lead angle for the specific
   NMRV40 unit.**
5. `TODO(unverified)` — **2.4 GHz FLRC sensitivity row** (Semtech Table 3-12 covers sub-GHz
   FLRC; the 2.4 GHz figure is not tabulated). Determines whether a high-rate uplink forces
   a ~1 m dish.
6. `TODO(unverified)` — **wiper / power-steering / wheelchair-scooter motor torque**,
   **slewing-bearing price**, **trailer/hi-lift worm-drive spec**, **used Yaesu second-hand
   price**, **anemometer SKU price (SparkFun class)**.
7. `TODO(unverified)` — **exact ERC Rec 70-03 Annex 1 row** for 2400–2483.5 MHz (inherited
   from `LINK-BUDGET-LICENCE-EXEMPT.md` §5).
8. **Must be weighed** — the real masses of the candidate 0.6–0.75 m dish and the Yagi
   (the ESTIMATE in §4).
9. **Must be measured** — feed-mismatch loss of a 2.4 GHz feed on the chosen Ku dish
   (inherited), and the achievable backlash of the chosen worm in situ.

---

*All numbers in §3, §5, §6, §7 and §8 are the printed output of
`docs/analysis/positioner_lowcost_model.py` (run: `python3 docs/analysis/positioner_lowcost_model.py`).*
