# Two-variant mass budget — Variant A (full) and Variant B (light)

> **STATUS: CONSULTANT ANALYSIS / PLANNING — NOT A DECISION RECORD AND NOT AN ORDER.**
> This document orders nothing and authorises no parts purchase. It is an itemised,
> source-backed mass budget for two variants of the first-flight vehicle, produced for the
> operator to decide on. Where it disagrees with an accepted record it says so; where a
> number has no source it is marked `TODO(unverified)` and no datasheet value is invented.

| | |
|---|---|
| Date | 2026-10-07 |
| Branch | `analysis/two-variant-mass-budget` |
| Base | `8ca1257` (tip of `github/main`, "merge: feat/mppt-charge-path") |
| Model | `docs/analysis/two_variant_mass_model.py` — every constant and every total below is its own printed output. Run `python3 docs/analysis/two_variant_mass_model.py`. |
| Provenance legend | **CITED** = an in-repo file/datasheet figure (file named) · **COMPUTED** = arithmetic shown · **ESTIMATE** = labelled analogy, *not* a datasheet number · `TODO(unverified)` = no source carries it |
| The binding constraint | mass (task context; see `docs/adr/049-wing-architecture.md` and the array work) |
| The design target | **Variant B must come in under 20 g total payload** — the operator's number. A parallel task is verifying the legal threshold; **this document does not assume 20 g is a legal limit**, it treats it as the design target it was given. |

**Sources found and used** (paths verified in this worktree, not trusted from the brief):
`docs/analysis/wing-mass-shape.md`, `docs/analysis/wing-insolation-geometry.md`,
`docs/analysis/array-power-architecture.md`, `docs/analysis/wing-jettison.md`,
`docs/analysis/wing-electrical.md`, `docs/PAYLOAD-WEIGHT-ESTIMATES.md`,
`docs/POWER-BUDGET-V9-D2BE.md`, `docs/SOLAR-PIN-REGULATORY.md`, `docs/hardware-design.md`,
`docs/component-guide.md`, `docs/inventory.md`, `docs/V9-RADIO-SITE-MATRIX.md`,
`docs/adr/006-supercapacitor-power.md` (**Accepted**), `docs/adr/009-antenna-strategy-v1-v2.md`,
`docs/adr/044-v9-power-rails.md`, `docs/adr/046-wing-board-interface.md`,
`docs/adr/047-v9-power-provisioning.md`, `docs/adr/048-v9-hub-wing-interfaces.md`,
`docs/adr/049-wing-architecture.md`, `docs/adr/050-mppt-charge-path.md`,
and the in-flight ADR-051 hub-array work.

> **Note on the brief's `044a` path.** The brief named `docs/adr/044a-v9-power-provisioning.md`.
> No such file exists. The power-**provisioning** record is `docs/adr/047-v9-power-provisioning.md`,
> and `docs/adr/044-v9-power-rails.md` is its companion. Both are used; ADR-047 is the
> provisioning one. Also note `docs/adr/050-*.md` is `050-mppt-charge-path.md`.
>
> **Note on the in-flight ADR-051.** ADR-051 is **not committed** anywhere on `github/main`
> or on the `adr/hub-array-cut-topology` branch, which exists only as a local worktree
> (`/home/c03rad0r/worktrees/bf-hubarray`, at the same base `8ca1257`) carrying two
> **uncommitted** files: `scripts/hub_array_topology_check.py` (a fail-closed gate) and
> `tests/test_hub_array_topology.py`. The gate's docstring is the only in-repo statement of
> ADR-051's requirement — it mandates that the hub-mounted solar array be **"an electrically
> independent series string from the four jettisonable wing strings, feeding the charge path
> through its own converter input"**, with canonical nets `HUB_PV_P` / `HUB_PV_N`, because
> otherwise *"the FIRST wing cut removes the hub array's return path together with the wing's
> cells and the vehicle goes dark: the cut becomes suicide."* This document therefore cites
> ADR-051 **as an in-flight, uncommitted gate script**, not as an accepted record, and marks
> its numbers `TODO(unverified)`.

---

## 0. Answer first

**Variant B can be built under 20 g — with roughly 7 g of margin — for *either* its
solar sub-case (B1 keeps a small hub array, B2 has none).** The honest reason is not that the
20 g line is hard: it is that **the heavy things in Variant A are exactly the things B
deletes**, and what remains is a single MCU + two radios + GNSS + a MEMS sensor + a small
capacitor bank.

| Variant | What it is | Estimated total | vs the 20 g target |
|---|---|---:|---|
| **A — full** (as-built wing carriers) | F33 + 4 cuttable wings + jettison hardware + hub array | **≈ 62.2 g** | over (target is B's, A is unconstrained) |
| **A — full** (recommended spine wings) | same, spine+ribs wings instead of full carriers | **≈ 45.8 g** | over |
| **B1 — light, small hub array** | no F33, no wings, no cut hardware, ~33 cm² hub solar | **≈ 12.9 g** | **PASS, ~7 g margin** |
| **B2 — light, no solar at all** | as B1, capacitor-only | **≈ 10.8 g** | **PASS on mass — but it is a < 2-minute store, not a flight** |

**The two honest caveats, stated up front and not buried:**

1. **B2 passes the mass test and fails the mission.** A capacitor is not a battery and not a
   solar array. With **no** array there is no recharge, so the vehicle runs for the store's
   single discharge: **≈ 20 s** on a 0.47 F cap and **≈ 85 s** on the full 1.65 F bank, at B's
   own average draw (§5.3). That is a sounding-rocket-style hop, not a stratospheric float.
2. **The number that dominates B is not the solar — it is the MCU module, and the repo does not
   carry its mass.** `ESP32-S3-WROOM-1U-N8R8` has **no mass figure anywhere in this repository**
   (`docs/V9-RADIO-SITE-MATRIX.md` §3.5 says so explicitly for the radio modules; the same is
   true of the S3). Every B total below therefore rests on a labelled **ESTIMATE**, and the
   single most valuable thing the operator can do is **weigh one module**. The repo owns a
   0.01 g scale for exactly this (`docs/inventory.md` line 68, "MS300 Waage").

The truthful one-line verdict: **B can hit < 20 g; whether that vehicle is worth flying is a
different question, and B2's answer is no.**

---

## 1. The task's own lists, restated as the two variants

**Variant A (full)** — the operator's list: `ESP32-S3-WROOM-1U-N8R8` + `SX1280` +
`LoRa2021` (bare, 2.4 GHz RX) + `LoRa2021F33-2G4` (1 W 433 MHz) + GPS (`MAX-M10S`) +
voltage regulator + pressure sensor (`MS5611`) + capacitor bank + **four wing boards with the
jettison/cutoff hardware** + **the hub solar array**.

**Variant B (light)** — the operator's list: `ESP32-S3-WROOM-1U-N8R8` + `SX1280` +
`LoRa2021` (bare) + GPS + voltage regulator + pressure sensor + capacitor. **No F33, no wing
boards, no cutoff hardware, and the operator did not list solar.** Both sub-cases are
evaluated:
- **B1** — B plus a small hub-mounted solar array (the survival floor);
- **B2** — B with **no** solar at all (capacitor only).

A board must exist in every variant to hold the modules; B's board is budgeted as the same v9
hub PCB, because the v9 hub outline is **not fixed** (`docs/adr/048-v9-hub-wing-interfaces.md`
§5 item 5) and no smaller board has been drawn.

---

## 2. The shared mass constants (and where they come from)

Every figure below is `CITED` or `COMPUTED`; nothing is invented.

| Constant | Value | Provenance |
|---|---|---|
| FR4 density | 1.85 g/cm³ | **CITED** `docs/PAYLOAD-WEIGHT-ESTIMATES.md` line 20 |
| Finished-board uplift | × 1.15 (copper + mask + silk) | **CITED** same line 20 |
| Silicon density | 2.33 g/cm³ | physical constant (crystalline Si 2.329) |
| Cell thickness | 0.21 mm | **CITED** `docs/adr/049-wing-architecture.md` (operator caliper 0.20–0.21 mm) |
| **0.6 mm FR4 areal mass** | **127.65 mg/cm²** | **COMPUTED** 0.060 cm × 1.85 × 1.15 |
| 0.4 mm FR4 areal mass | 85.10 mg/cm² | **COMPUTED** 0.040 × 1.85 × 1.15 |
| 0.8 mm FR4 areal mass | 170.20 mg/cm² | **COMPUTED** 0.080 × 1.85 × 1.15 |
| 0.21 mm Si areal mass | 48.93 mg/cm² | **COMPUTED** 0.021 × 2.33 |
| 30 AWG wire | 0.460 mg/mm (0.23 g / 500 mm) | **CITED** `docs/analysis/wing-mass-shape.md` §2.4 |

### 2.1 The repo's `127.6 mg/cm²` figure is correct — it does not need correcting

The brief asked to find and, if wrong, correct the repo's 0.6 mm FR4 figure. It is **right**:

```
0.060 cm × 1.85 g/cm³ × 1.15 = 0.127650 g/cm² = 127.65 mg/cm²
```

`docs/analysis/wing-mass-shape.md` §2.1 and `docs/adr/049-wing-architecture.md` both state
**127.6 mg/cm²**, and both carry the same ×1.15 provenance from
`docs/PAYLOAD-WEIGHT-ESTIMATES.md` line 20. The derived ratio against the 0.21 mm silicon cell
(`127.65 / 48.93 = 2.61×`) also reproduces the repo's own "**2.61×**" headline. **No correction
is required.** The one soft spot is *inside* that figure, not in its arithmetic: the ×1.15
uniform uplift is a rule of thumb, and for the **as-built wing the real copper is far below
full cover** (empty `B_Cu`, only 212 mm² of `F_Cu` — `docs/adr/046-wing-board-interface.md`
§7b), so ×1.15 is a *conservative floor* for that board and a plausible *over*-estimate for a
copper-light one. That is stated in the source and repeated here.

---

## 3. VARIANT A — full, itemised

### 3.1 The item table

`Qty` is per vehicle. Cell class is the **ADR-049 decision** (3 LARGE cells per wing, 12
total). Wing PCB is the **as-built full carrier** (4472 mm²); the recommended spine+ribs
alternative is given in §3.2 because it is the single largest mass lever.

| # | Item | Unit (g) | Qty | Subtotal (g) | Source | Verification |
|---|---|---:|---:|---:|---|---|
| A1 | Hub PCB, 55.15 × 45.15 × 0.6 mm FR4 | 2.76 | 1 | **2.76** | **CITED** `docs/POWER-BUDGET-V9-D2BE.md` §4 (computed there from `hub_board_v1_clean.kicad_pcb`) | CITED (bare-FR4; ×1.15 would give 3.18 g — see §3.3) |
| A2 | `ESP32-S3-WROOM-1U-N8R8` | 2.5 | 1 | **2.5** | **ESTIMATE** by analogy to the repo's `ESP32-C3-Mini-1` line (2.5 g, 2–3 g) in `docs/PAYLOAD-WEIGHT-ESTIMATES.md` §3 | `TODO(unverified)` — **no S3 mass in repo** |
| A3 | `SX1280IMLTRT` + matching/passives | 0.2 | 1 | **0.2** | **ESTIMATE** (QFN-24 class + 0402 passives) | `TODO(unverified)` |
| A4 | Bare `LoRa2021` castellated module (2.4 GHz RX) | 1.2 | 1 | **1.2** | **CITED** `docs/PAYLOAD-WEIGHT-ESTIMATES.md` §3 ("LR2021 bare, 1–2 g") | `TODO(unverified)` for the exact part (`V9-RADIO-SITE-MATRIX.md` §3.5) |
| A5 | `LoRa2021F33-2G4` module (433 TX, 1 W PA) | 4.0 | 1 | **4.0** | **CITED** `docs/PAYLOAD-WEIGHT-ESTIMATES.md` §3 ("LR2021F33, 3–5 g") | `TODO(unverified)` for the exact part (`V9-RADIO-SITE-MATRIX.md` §3.5) |
| A6 | GPS `MAX-M10S` (bare, direct-soldered) | 0.4 | 1 | **0.4** | **CITED** `docs/PAYLOAD-WEIGHT-ESTIMATES.md` §3 | CITED (bare; breakout is 1.0 g) |
| A7 | Voltage regulator `TPS7A02` (SOT-23-5) | 0.05 | 1 | **0.05** | **CITED** `docs/component-guide.md` §6 | CITED |
| A8 | Pressure sensor `MS5611` (bare) | 0.03 | 1 | **0.03** | **CITED** `docs/PAYLOAD-WEIGHT-ESTIMATES.md` §3 | CITED (bare; breakout 0.3 g) |
| A9 | Supercap bank, 2 × AVX SCC 3.3 F 2.7 V | 1.5 | 2 | **3.0** | **CITED** `docs/adr/006-supercapacitor-power.md` ("2× 1.5 g = 3.0 g"); `docs/POWER-BUDGET-V9-D2BE.md` §4 | CITED (doubled 4-cell option = 6.0 g, ADR-047 §3.2) |
| A10 | Antenna wire dipole (433 + 2.4 GHz) | 0.2 | 1 | **0.2** | **CITED** `docs/PAYLOAD-WEIGHT-ESTIMATES.md` §3 (868 MHz wire ~0.2 g) | `TODO(unverified)` for the v9 dual-band harness; U.FL pigtails add mass (see A16) |
| A11 | Wing PCB × 4 — **full carrier** 4472 mm², 0.6 mm | 5.709 | 4 | **22.84** | **CITED** `docs/analysis/wing-mass-shape.md` §1.4 / §2.2 | CITED (gerber Edge.Cuts, 184 × 25 mm) |
| A12 | Wing solar cells × 4 — 3 LARGE in series (1.50 g each) | 4.50 | 4 | **18.00** | **CITED** `docs/analysis/wing-mass-shape.md` §1.2/§1.4; `array-power-architecture.md` §1.2 | `TODO(unverified)` — bare-Si computed 1.50 g vs the repo's "~2 g per 78×39 cell" listing (4× conflict; weigh a cell) |
| A13 | Wing solder + 30 AWG interconnect | 0.090 | 4 | **0.36** | **CITED** `docs/analysis/wing-mass-shape.md` §1.3 | COMPUTED estimate in the source |
| A14 | **Jettison/cutoff hardware** — MOSFET + nichrome + nylon, 4 channels | 0.5 | 4 | **2.00** | **CITED** `docs/analysis/wing-jettison.md` §3.5 (repo precedent `balloon-test-results.md` line 254, "≈0.5 g per channel") | `TODO(unverified)` — no channel has been built or weighed; ADR-050 §3.10 uses the same 0.5 g precedent |
| A15 | **Hub solar array** ~65 cm² cells (survival floor) | 3.17 | 1 | **3.17** | **COMPUTED** §5.2 below: 64.8 cm² × 48.93 mg/cm² (bare Si) | `TODO(unverified)` — area derived here/in-flight ADR-051; carrier & interconnect not budgeted |
| A16 | Connectors, U.FL/pigtails, passives, solder paste, potting/conformal | 1.0 | 1 | **1.0** | **ESTIMATE** — repo bands: "heat-shrink/conformal 0.5–1 g" and "wire/strain relief 0.2–0.5 g" (`PAYLOAD-WEIGHT-ESTIMATES.md`, Key Assumptions 8/9); SMD+solder alone 0.19–0.25 g there | `TODO(unverified)` — **not itemised anywhere** |
| A17 | Balloon attachment (30 AWG suspension line, ~1 m) | 0.46 | 1 | **0.46** | **COMPUTED** 1 m × 0.460 mg/mm (`wing-mass-shape.md` §2.4) | `TODO(unverified)` — line length/tie not specified |
| | **VARIANT A TOTAL (as-built full-carrier wings)** | | | **≈ 62.2 g** | | |
| | **VARIANT A TOTAL (recommended spine+ribs wings, §3.2)** | | | **≈ 45.8 g** | | |

The MPPT charge path of **ADR-050** (Proposed) adds **≈ 0.70–1.20 g** when adopted
(`docs/adr/050-mppt-charge-path.md` §3.7 — its own budget, ~one active part + inductor + caps +
~150 mm² PCB). It is *not* in the A total above because ADR-050 is Proposed and, on ADR-050's
own analysis, the hub array as an **independent string** (ADR-051) is the mission-continuity
mechanism, with the converter as the belt-and-braces alternative. If A is built **with** the
converter, add ≈ 1 g → **≈ 63.2 g**).

### 3.2 Why the wing carrier is the whole game in Variant A

`docs/analysis/wing-mass-shape.md` §1.4 / §4 already computed the four-wing array for both
carrier styles, at 0.6 mm FR4:

| Wing build | PCB (g/wing) | cells (g/wing) | solder (g/wing) | **wing (g)** | **array ×4 (g)** |
|---|---:|---:|---:|---:|---:|
| (a) FULL CARRIER (as built) | 5.709 | 1.502\* | 0.090 | 7.300\* | 29.20\* |
| (b) SPINE + RIBS (recommended) | 1.620 | 1.502\* | 0.090 | 3.212\* | 12.846\* |

\* The source's table is for **small** cells (1.502 g/wing). This document uses the **ADR-049
large** class (3 × 1.4951 = 4.485 g/wing of cells, **17.94 g/array**), so its array figures are
higher: **full carrier 4 × (5.709 + 4.485 + 0.090) = 41.14 g**; **spine 4 × (1.620 + 4.485 +
0.090) = 24.78 g**. The **PCB lever alone** is identical to the source's: **−16.35 g on the
array** (4472 − 1269.1 = 3202.9 mm² × 127.65 mg/cm² = 4.0874 g/wing × 4). The cell-class lever
is separate and is quantified in §6.

### 3.3 Variant A — where the grams are (ranked)

| Rank | Item | g | Share | Note |
|---:|---|---:|---:|---|
| 1 | 4 × wing PCB (full carrier) | 22.84 | 36.7 % | a structure decision, not an electrical one |
| 2 | 12 large solar cells | 18.00 | 29.0 % | the power source — cannot be deleted, only resized |
| 3 | `LoRa2021F33-2G4` | 4.0 | 6.4 % | the module B deletes |
| 4 | Hub solar array (~65 cm² cells) | 3.17 | 5.1 % | the survival floor |
| 5 | Supercap bank (2 cells) | 3.0 | 4.8 % | 6.0 g if doubled (ADR-047) |
| 6 | Hub PCB | 2.76 | 4.4 % | bare-FR4 figure; 3.18 g with the ×1.15 rule |
| 7 | `ESP32-S3-WROOM-1U-N8R8` | 2.5 | 4.0 % | **ESTIMATE** |
| 8 | Jettison/cutoff hardware (4 ch) | 2.00 | 3.2 % | carried all flight |

The striking fact: **the two solar/wing structural items (ranks 1–2) are 65.7 % of Variant A.**
Variant A is not "a radio with solar panels"; it is "two solar arrays flying in radio form".

---

## 4. VARIANT B — light, itemised (B1 with solar, B2 without)

### 4.1 The item table

Every A row that B deletes is struck out; B's rows are the remainder. B's average power and
solar area are derived in §5.

| # | Item | Unit (g) | Qty | Subtotal (g) | Source | Verification |
|---|---|---:|---:|---:|---|---|
| B1 | Hub PCB, 55.15 × 45.15 × 0.6 mm FR4 | 2.76 | 1 | **2.76** | **CITED** `docs/POWER-BUDGET-V9-D2BE.md` §4 | CITED — could shrink if a smaller board is drawn (`TODO`) |
| B2 | `ESP32-S3-WROOM-1U-N8R8` | 2.5 | 1 | **2.5** | **ESTIMATE** by analogy (same as A2) | `TODO(unverified)` — **weigh it** |
| B3 | `SX1280IMLTRT` + matching/passives | 0.2 | 1 | **0.2** | **ESTIMATE** | `TODO(unverified)` |
| B4 | Bare `LoRa2021` castellated module (2.4 GHz RX) | 1.2 | 1 | **1.2** | **CITED** `PAYLOAD-WEIGHT-ESTIMATES.md` §3 | `TODO(unverified)` |
| B5 | GPS `MAX-M10S` (bare) | 0.4 | 1 | **0.4** | **CITED** `PAYLOAD-WEIGHT-ESTIMATES.md` §3 | CITED |
| B6 | Voltage regulator `TPS7A02` | 0.05 | 1 | **0.05** | **CITED** `component-guide.md` §6 | CITED |
| B7 | Pressure sensor `MS5611` (bare) | 0.03 | 1 | **0.03** | **CITED** `PAYLOAD-WEIGHT-ESTIMATES.md` §3 | CITED |
| B8 | Supercap — 0.47 F option | 2.0 *(range 0.9–3.3)* | 1 | **2.0** | **ESTIMATE** — task-stated published range **2–7 g/F** × 0.47 F; the repo's own AVX SCC 3.3 F part is 1.5 g/cell = **0.45 g/F** (`ADR-006`) | `TODO(unverified)` — **no 0.47 F part is named anywhere** |
| B9 | Antenna wire dipole | 0.2 | 1 | **0.2** | **CITED** `PAYLOAD-WEIGHT-ESTIMATES.md` §3 | `TODO(unverified)` for the v9 harness |
| B10 | Connectors, passives, solder paste, potting | 1.0 | 1 | **1.0** | **ESTIMATE** (same repo bands as A16) | `TODO(unverified)` |
| B11 | Balloon attachment (30 AWG, ~1 m) | 0.46 | 1 | **0.46** | **COMPUTED** 1 m × 0.460 mg/mm | `TODO(unverified)` |
| | **B2 SUBTOTAL — no solar at all** | | | **≈ 10.8 g** | | |
| B12 | Hub solar array ~33 cm² cells (**B1 only**) | 1.61 | 1 | **1.61** | **COMPUTED** §5.2: 32.9 cm² × 48.93 mg/cm² (bare Si) | `TODO(unverified)` — area derived here; carrier/interconnect extra |
| B13 | Hub-array carrier + interconnect + mounting (**B1 only**) | 0.5 | 1 | **0.5** | **ESTIMATE** (spine-class FR4 + 30 AWG + adhesive) | `TODO(unverified)` |
| | **B1 TOTAL — with small hub array** | | | **≈ 12.9 g** | | |
| | **B2 TOTAL — capacitor only** | | | **≈ 10.8 g** | | |

**Deleted from A to get B:** the F33 (−4.0 g), the four wing boards and their cells and
solder (−22.84 − 18.00 − 0.36 = **−41.2 g**), the jettison hardware (−2.0 g), and the large
hub array (−3.17 g, offset by B's small array +1.61 g). That is **≈ 50 g removed** for **≈ 13 g
kept** — which is why B clears 20 g.

### 4.2 Sensitivity — does B still clear 20 g if every soft number is pessimistic?

This is the check that matters, because several B lines are `TODO(unverified)`.

| Pessimistic assumption | Effect on B1 | B1 total |
|---|---|---:|
| S3 module is **5 g**, not 2.5 g | +2.5 g | 15.4 g |
| Solar cells use the repo's **heavy 2 g / 52×19 cell** figure, not bare-Si 0.5 g (33 cm² ⇒ +4.8 g) | +4.8 g | 17.7 g |
| Supercap is the **top of the range** (3.3 g, not 2.0 g) | +1.3 g | 14.2 g |
| S3-heavy **and** cell-heavy together | +7.3 g | **20.2 g** |
| **All three at once** | +8.6 g | **21.5 g** |

So **B1 clears 20 g on any single pessimistic assumption, and on two of the three pairings —
but the S3-heavy + cell-heavy combination lands at 20.2 g and the triple-pessimistic build at
21.5 g, both just over.** That is the honest boundary: the margin is real, but it is not
enormous once the two heaviest unverified items (the S3 module and the cell mass) are both wrong
in the same direction. B2 (no solar) clears 20 g even then (≈ 14.6 g), because it drops B12/B13.

### 4.3 Variant B — where the grams are (ranked)

| Rank | Item | g | Reduction lever and what it is worth |
|---:|---|---:|---|
| 1 | Hub PCB (55.15 × 45.15 × 0.6) | 2.76 | shrink the board and/or drop to 0.4 mm: the panel area scales directly; 0.4 mm at the same outline = **2.12 g (−0.64 g)**; a 30 × 30 mm 0.6 mm board = **1.04 g (−1.72 g)** *(COMPUTED, needs a layout)* |
| 2 | `ESP32-S3-WROOM-1U-N8R8` | 2.5 *(EST)* | none within the S3 family — the WROOM is the module; a bare-chip custom PCB would save mass but is a new board (`PAYLOAD-WEIGHT-ESTIMATES.md` recommends exactly this, ~1.5 g) |
| 3 | Supercap | 2.0 | drop to a smaller cap, but this is **circular** — a smaller store shortens B2's already-short run time (§5.3). Only viable for B1 |
| 4 | Bare `LoRa2021` | 1.2 | none — it is the 2.4 GHz RX the mission needs |
| 5 | Hub solar array + carrier (B1) | 2.11 | shrink the array to the minimum that covers 0.197 W (§5.2); bare-Si is the floor |
| 6 | Passives/connectors/potting | 1.0 | direct-solder everything, minimal potting (−0.3 g est.) |
| 7 | Balloon attachment | 0.46 | shorter/thinner line (−0.2 g) |
| 8 | GPS | 0.4 | none — flight position needs it |

There is **no single large lever in B.** Unlike A — where moving the wing carrier from full to
spine saves 16.35 g in one decision — B's every line is 0.03–2.8 g. **B's mass is dominated by
the MCU module and the PCB, both of which are structural, not electrical.**

---

## 5. Power cross-check for Variant B

### 5.1 B's average draw (the F33 is gone, so the 5 V rail is gone)

`docs/POWER-BUDGET-V9-D2BE.md` §2 builds the **Variant-A** average from two rails:

```
5 V  rail (F33): 0.01 × 1.20 A + 0.99 × 0.020 A = 0.0318 A → × 5.0 V = 0.159 W
3.3 V rail:      0.14 + 0.30 + 24.0 + 25.0 + 0.16 = 49.6 mA → ×3.3 V = 0.164 W
A representative input power = (0.159 + 0.164) × 1.20 = 0.388 W
```

**B deletes the entire 5 V rail**, because the F33 is the only 5 V load. B's load is the 3.3 V
rail alone, plus the bare `LoRa2021`'s own 2.4 GHz RX current — which the repo leaves as
`TODO(unverified)` (`POWER-BUDGET-V9-D2BE.md` §2 line: "bare LoRa2021 2.4 GHz RX … TODO").

```
B input power ≈ 0.164 W × 1.20 = 0.197 W          ← held as TODO on the bare-LoRa2021 line
B / A         = 0.197 / 0.388  = 0.507            (B needs ~half of A's power)
```

**So B's average draw is ≈ 0.197 W, about 51 % of A's 0.388 W.** The subtraction is legitimate
because the F33's line is the *only* 5 V term and B deletes the part outright; it is **not** a
fudge — but the number is a **floor-optimistic** 0.197 W, because the bare `LoRa2021` RX
current is unaccounted in the repo and only adds.

### 5.2 The solar area B needs (and why it is far below A's 65 cm²)

The brief's chain, verified rather than repeated:

```
peak plane-of-array power density = 7.2 W / 366.7 cm²            = 19.63 mW/cm²
   [COMPUTED from ADR-049 §Decision: 6.0 V × 1.2 A = 7.2 W; 366.7 cm² = 12 × 30.5559 cm²]
rotation factor (vertical blades, uncontrolled azimuth)
   = (1/π)·cos h = 0.305107                     [CITED wing-insolation-geometry.md §2]
average density = 19.63 × 0.305107 = 5.99 mW/cm²  [COMPUTED]
```

Then, area = average load ÷ average density:

```
Variant A hub array = 0.388 W / 0.00599 W/cm² = 64.8 cm²   → matches the brief's ~65 cm²
Variant B hub array = 0.197 W / 0.00599 W/cm² = 32.9 cm²   → ~33 cm², ~half of A
```

**The logic verifies, and the "B needs far less" claim is correct — for the stated reason.** A's
65 cm² is driven by A's 0.388 W average, and **0.159 W of that 0.388 W is the F33** (41 % of the
input power before the 1.20 allowance). Remove the F33 and B's requirement falls **almost
exactly in half (64.8 → 32.9 cm², ×0.507)**. The two numbers are consistent by construction,
which is the cross-check the brief asked for.

Two caveats that keep this honest:
- The **19.63 mW/cm² "peak"** is *not* an irradiance figure — it is the **nameplate electrical
  power density of the accepted 12-cell array** (7.2 W spread over its own 366.7 cm² installed
  cell area). It happens to be numerically close to a heavily-derated winter plane irradiance,
  but it is used here as **power per installed cell cm²**, which is what the rotation factor and
  the area arithmetic require. The repo's *separate* insolation/derate model
  (`docs/SOLAR-PIN-REGULATORY.md` §1.1: 1361 W/m² × η 0.22 × 0.35 = **10.5 mW/cm²** for rigid
  c-Si) is a **different** figure answering a different question (irradiance→electricity), and
  the two must not be mixed. Using 10.5 mW/cm² instead would roughly halve the *derate-inclusive*
  area, so this document stays with the **array-nameplate** method above and says which method it
  used.
- The rotation factor **0.305107 is the series-good case with bypass diodes fitted.** Without
  the four bypass Schottkys the vertical string collapses to ≈ 0 near four azimuths
  (`wing-insolation-geometry.md` §2b), so **B's solar floor inherits A's bypass-diode
  requirement** if it is mounted as vertical blades. A flat hub array (β = 0) needs no bypass but
  has the lower daily factor (0.186 series-day).

### 5.3 B2 — capacitor-only run time, stated plainly

There is **no recharge** in B2, so the vehicle runs the store down once. Using B's 0.197 W
average and `E = ½C(V_hi² − V_lo²)` (the same formula as `ADR-044` §5 / `ADR-047` §3.1):

| Store | Usable to 3.5 V | Usable to 3.0 V (radio min) | **Run time at 0.197 W** |
|---|---:|---:|---:|
| 0.47 F (B8) | 3.97 J | 4.74 J | **20 s** (24 s to 3.0 V) |
| 1.65 F (2 × 3.3 F, ADR-006, = 3.0 g) | 13.95 J | 16.63 J | **71 s** (85 s to 3.0 V) |
| 3.3 F doubled (ADR-047, = 6.0 g) | 27.90 J | 33.26 J | **142 s** (169 s to 3.0 V) |

**Plainly: a capacitor-only B2 is a 20-second to ~3-minute vehicle**, depending on the cap.
Even the *doubled* bank (6 g of supercaps — a third of B's whole mass) buys under three minutes
at the mission average. There is no duty-cycle trick that rescues it: the energy is `½CV²` and
the C you can carry at this mass is irreducibly small. **B2 is not a stratospheric flight; it is
a drop-test / captive-lift / one-shot telemetry burst.** If any flight time is wanted, **B1 is
the minimum configuration** and even B1 needs its array sized to the mission average (§5.2) to
hold station — and, with no wing blades to jettison, no solar redundancy at all.

---

## 6. The supercapacitor bank — the sleeper term, audited

The brief flagged the cap bank as a suspected sleeper and asked whether the repo names parts.
It does, partially:

| Option | Part named? | Mass | Source |
|---|---|---|---|
| **Accepted bank** 2 × AVX SCC **3.3 F / 2.7 V** series = 1.65 F @ 5.4 V | **YES** — "AVX SCC", 3.3 F, 2.7 V | **1.5 g/cell → 3.0 g** | **CITED** `docs/adr/006-supercapacitor-power.md` ("Gewicht: 2x 1.5g = 3.0g"); `POWER-BUDGET-V9-D2BE.md` §4 |
| **Doubled bank** 4 × AVX SCC (2 series × 2 parallel) = 3.3 F | YES | **6.0 g (+3.0 g)** | **CITED** `docs/adr/047-v9-power-provisioning.md` §3.2 |
| **Smaller 0.47 F option** (night-off) | **NO** — no part is named anywhere | `TODO(unverified)` | `docs/adr/009-antenna-strategy-v1-v2.md` §"Night-Off Default" |

**The repo's own part density: 1.5 g ÷ 3.3 F = 0.45 g/F** (2.7 V class). The brief's stated
"published 5.5 V supercaps ≈ 2–7 g/F" is a **different voltage class** and a **much heavier**
one — a 5.5 V part typically contains two cells internally, which is why its g/F is several
times the repo's 2.7 V cell. **Both are stated; the operator must pick the family**, because the
mass differs by roughly **4–15×** for the same nominal farads.

**Where the 3.5 g saving actually comes from — audited, not repeated.** ADR-009 §"Night-Off
Default" claims a **~3.5 g** saving from "smaller supercaps (0.47 F vs 3.3 F, fewer solar cells:
6–8 vs 12)". That 3.5 g is **not** a capacitor-only saving; it is the *sum* of two changes:

```
fewer cells:  12 → 8 cells of ~0.5 g (bare-Si small cell)  ≈  4 × 0.50 = −2.0 g
smaller cap:  3.0 g (2× 3.3 F) → a ~1 g 0.47 F part        ≈  −1.5 g   (soft)
                                                        TOTAL ≈  −3.5 g   ✓ matches ADR-009
```

So **≈ 2.0 g of the 3.5 g is solar cells, not capacitance**, and the cap half (~1.5 g) rests on
**no named part**. On the brief's 2–7 g/F range, a 0.47 F 5.5 V part is **0.9–3.3 g** — i.e. the
cap saving could be anywhere from **−2.1 g to +0.3 g** (even a *gain* if the small part is a
heavy 5.5 V family). **This is genuinely soft and is flagged as such.** Settle it by weighing the
actual candidate part on the 0.01 g scale.

**Recommendation on the bank (mass-only view, no mission claim):** for **B**, the 0.47 F option is
the right *mass* choice **only if** B is not expected to hold station through a night — and §5.3
shows B2 cannot hold through anything, so the cap choice is second-order next to the decision of
whether B has an array at all. For **A**, the bank is a survival-floor element and the doubled
bank's +3.0 g must be justified on the ESR/rail-step grounds ADR-047 §3.2 gives, not on energy.

---

## 7. Ranked levers, each with the grams it is worth

### 7.1 Variant A levers (largest → smallest)

| Lever | Grams saved | Basis |
|---|---:|---|
| **Wing PCB: full carrier → spine + ribs** (0.6 mm) | **−16.35 g** | **CITED** `wing-mass-shape.md` §2.6 (3202.9 mm² × 127.65 mg/cm² × 4) |
| **Cell class: 12 LARGE → 12 SMALL cells** | **−11.93 g** | **COMPUTED** (18.00 − 6.01); **cost: peak 7.2 W → 2.4 W**, below the radio's 6.15 W max draw |
| **Wing PCB thickness 0.6 → 0.4 mm** (spine wings) | **−2.16 g** | **COMPUTED** (1269.1 mm² × (127.65 − 85.10) mg/cm² × 4). *Note: the repo's §8 item 9 states 1.206 g / −0.414 g per wing, i.e. −1.66 g/array; by the repo's own ×1.15 rule the correct figure is **1.080 g / −0.540 g per wing (−2.16 g/array)**. The repo §8 item 9 figure appears arithmetically inconsistent and is flagged here, not adopted.* |
| Wing PCB thickness 0.6 → 0.4 mm (full carrier) | −7.61 g | **COMPUTED** (44.72 cm² × (127.65 − 85.10) mg/cm² × 4) |
| **Delete the F33 (→ Variant B)** | **−4.0 g** | **CITED** A5 |
| Delete the jettison hardware | −2.0 g | **CITED** A14 (and `wing-jettison.md` recommends exactly this: the mechanism is mass-negative even before it is unsafe) |
| Shrink the hub solar array to B's 33 cm² | −1.56 g | **COMPUTED** (3.17 → 1.61 g) |
| Hub PCB 0.6 → 0.4 mm | −1.06 g | **COMPUTED** (3.179 → 2.119 g with the ×1.15 rule) |
| Delete the 4 wings entirely (→ Variant B) | −41.20 g | **COMPUTED** (22.84 PCB + 18.00 cells + 0.36 solder) |

### 7.2 Variant B levers (largest → smallest)

| Lever | Grams saved | Basis |
|---|---:|---|
| Shrink the board (55×45 → 30×30 mm, 0.6 mm) | −1.72 g | **COMPUTED** (0.618 vs 3.179 g ×1.15; needs a layout) |
| Board 0.6 → 0.4 mm (same outline) | −1.06 g | **COMPUTED** (3.179 → 2.119 g) |
| Delete B1's hub array entirely (→ B2) | −2.11 g | **COMPUTED** — **but see §5.3: this is the flight** |
| Supercap: 2 g → 0.5 g (smaller named part) | −1.5 g *(soft)* | **ESTIMATE** — depends on the part family (§6) |
| Direct-solder, minimal potting | −0.3 g | **ESTIMATE** |
| Shorten the suspension line | −0.2 g | **COMPUTED** (0.460 mg/mm) |
| **Nothing else** | — | B's remaining lines are 0.03–2.5 g and mostly irreducible |

**B has no levers worth a decision.** The only one that changes the vehicle is deleting the
array, which deletes the flight (§5.3). This is the honest conclusion of the exercise: **B's
problem is not that it is too heavy, it is that once it is light enough it is too small to do
the job.**

---

## 8. UNKNOWN — what the operator must weigh / decide

The following are **not** resolvable from any in-repo source and are required before either
variant's total can be trusted. Each names what would settle it.

**Must be weighed (0.01 g MS300 scale, `docs/inventory.md` line 68):**

1. **`ESP32-S3-WROOM-1U-N8R8`**, one module. **Highest-priority weighing.** It is the largest
   single unknown in B (estimated 2.5 g by analogy; the repo has **no** S3 mass — `V9-RADIO-SITE-MATRIX.md`
   §3.5 confirms the repo carries no module masses, only a scale).
2. **`LoRa2021F33-2G4`**, one module (A5) — repo marks it `UNVERIFIED`
   (`V9-RADIO-SITE-MATRIX.md` §3.5; 39 × 21 mm body). Deletes entirely in B.
3. **Bare `LoRa2021`** castellated module (A4/B4) — same `UNVERIFIED` status.
4. **One 52 × 19 mm cell and one 78 × 39 mm cell.** The bare-Si calc (0.5006 g / 1.4951 g) and
   the repo's "~2 g" listing differ **4×** (`wing-mass-shape.md` §1.2, §8 item 1 — the source
   calls this "the single largest uncertainty in the entire model"). This flips which item is
   largest in both variants.
5. **One `SX1280IMLTRT`** (+ its passives) — no repo figure.
6. **The actual 0.47 F supercap part** if that option is taken (§6) — family decides 0.9–3.3 g.
7. **One jettison/cutoff channel** as built (MOSFET + nichrome + nylon) — the 0.5 g/channel is a
   repo *precedent*, not a measurement (`wing-jettison.md` §3.5).

**Must be decided / measured (not weighable):**

8. **The v9 hub board outline and thickness.** The repo contradicts itself: `hardware-design.md`
   line 13 says **22 × 22 mm** (≈ 0.54 g bare FR4 at 0.6 mm) while `POWER-BUDGET-V9-D2BE.md` §4
   and ADR-029 use **55.15 × 45.15 mm** (2.76 g bare / 3.18 g with the ×1.15 rule) — a **5.9×**
   PCB-mass difference. `docs/adr/048-v9-hub-wing-interfaces.md` §5 item 5 records the outline
   as unfixed. This alone moves both variants' totals by up to ~2.6 g.
9. **Whether A is built with the ADR-050 MPPT charge path** (+ ≈ 0.70–1.20 g, Proposed) or with
   the ADR-051 independent hub string alone.
10. **The ADR-051 hub-array figures** — the only in-repo artefact is an **uncommitted** gate
    script in a local worktree; its 65 cm² / 33 cm² sizing and any carrier mass are **not
    committed** and must be written down before they can be budgeted.
11. **The bare `LoRa2021` 2.4 GHz RX current** (`TODO(unverified)` in `POWER-BUDGET-V9-D2BE.md`
    §2) — it sets the 0.197 W B average that sets B's array area.
12. **Connectors, U.FL/pigtails, potting, fasteners, strain relief** — no line item exists in any
    repo mass table; budgeted here as a single 1.0 g ESTIMATE from the repo's own 0.5–1 g +
    0.2–0.5 g bands (`PAYLOAD-WEIGHT-ESTIMATES.md` Key Assumptions 8/9). **Itemise or accept the
    ESTIMATE — do not omit.**
13. **The balloon attachment** — 30 AWG line length, tie method and any anchor mass are
    unspecified; budgeted at ~0.46 g for 1 m.

---

## 9. The verdict, in one paragraph

**Variant B can be built under 20 g — estimated ≈ 12.9 g for B1 (small hub array) and ≈ 10.8 g
for B2 (no array) — with the caveat that two unweighed items (the S3 module and the solar-cell
mass) carry most of the uncertainty and, if both come out pessimistic, B1 lands at ≈ 20.2 g
(≈ 21.5 g if the cap is heavy as well).** The margin
is real for a single-pessimism build and thin for a triple-pessimism one, which is exactly why
the operator's scale work is the next step. **The mass test is the easy half.** The hard half is
that B2 passes the mass test and cannot fly (a **20-second to ~3-minute** capacitor-only store,
§5.3), and B1 passes the mass test but has **no solar redundancy and no wing blades** — it is the
survival floor without the peak-power array. If the operator wants a light vehicle *and* a
mission, **B1 with the array sized to the mission average (≈ 33 cm², §5.2) is the minimum
configuration**, and its verdict is: **under 20 g, yes; a comfortable margin, no; and not a
vehicle to trust without the bypass diodes and the coupling measured on the bench.**

---

## 10. What this analysis does NOT establish

- It contains **no measurement** of any physical part. Every gram is arithmetic on a cited
  constant, an in-repo computed figure, or a labelled ESTIMATE.
- It does **not** authorise a board change, a BOM change, an order, or a flight. It orders
  nothing.
- It does **not** resolve the hub outline/thickness conflict (§8 item 8) or the cell-mass 4×
  conflict (§8 item 4); it states both.
- It does **not** re-derive the electrical architecture; ADR-006 (Accepted), ADR-044/047,
  ADR-049 and the Proposed ADR-050 are taken as stated, and the in-flight ADR-051 is cited as an
  uncommitted gate script.
- It does **not** claim 20 g is a legal threshold. It treats 20 g as the operator's stated design
  target; the legal number is a separate, parallel question.
