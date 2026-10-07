# ADR-062 — Variant B design basis: a separate, under-20 g vehicle with its own mass, energy, array and outline

- Status: **Proposed** — the *text* has **NOT** been accepted by a human. The 20 g wall is the
  operator's stated **design target** (recorded at `docs/analysis/two-variant-mass-budget.md`
  line 17), **not** a verified legal threshold; a parallel task
  (`analysis/free-balloon-mass-threshold`) owns the legal question and this record asserts
  nothing about it.
- Date: 2026-10-07
- Decision owner: Felix (operator)
- Author: subagent (Hermes), branch `adr/variant-b-design-basis`, worktree `~/worktrees/bf-variantb`.
- Number allocated with `python3 scripts/adr_next_number.py` (printed **62**, exit 0) and
  cross-checked across **all** refs: `git log --all --name-only --pretty=format: | grep -c
  'docs/adr/062'` → **0**. 055–061 are allocated; `062` is free everywhere inspected.
- Related records (all `docs/adr/` on `github/main`): ADR-006 (supercapacitor power, Accepted),
  ADR-029 (dual-band flight board; D1 the `-N8R8` module, D1.1 the three PSRAM pins, the
  ADR-061 correction), ADR-034 (band split 433 TX / 2.4 RX), ADR-036 (energy policy:
  burst-sized storage, daylight-only TX, mandatory night deep-sleep, the 100 µW night anchor),
  ADR-040 (radio-site optionality), ADR-044 (v9 power rails), ADR-047 (F33 power provisioning —
  the 6.15 W maximum draw B deletes), ADR-048 (hub-side wing interfaces), ADR-049 (wing
  architecture, cell class), ADR-050 (MPPT charge path), ADR-051 (hub array + cut topology —
  the 64.9 / 106.1 cm² figures), ADR-052 (end-only cell mount), ADR-053/054 (bypass diodes),
  ADR-055 (hub geometry — **the array plane is HORIZONTAL**, the 103 mm square, 0.4 mm),
  ADR-056/057 (drift), ADR-059 (NTC provision, DNP), ADR-061 (on-board storage — internal
  8 MB flash, no external part), ADR-108 (F33 + SX1280 pin plan).
- Related artefacts: `docs/analysis/two-variant-mass-budget.md` (the existing B budget this
  record re-derives), `docs/POWER-BUDGET-V9-D2BE.md`, `docs/V9-RADIO-SITE-MATRIX.md`,
  `docs/analysis/wing-insolation-geometry.md`, `docs/inventory.md`, `docs/PAYLOAD-WEIGHT-ESTIMATES.md`.

---

## 0. What this record is, and what it is not

This is a **design basis** for Variant B — an ADR-first record. It **does not** lay out, route,
place or build a B board, and it **modifies nothing** in the Variant A board, schematic, netlist
or placement (`tracker/hardware/hub_board_v9.kicad_pcb` is untouched). The board work is the
**next** stage, gated on this basis landing.

The project has been carrying A and B as if they were **one board with a population option**.
They are not the same design problem, and the arithmetic below is the proof:

- **Variant A** = hub + four jettisonable wings on a ~50 N (~5 kg) balloon. A's board is
  **103 × 103 mm = 106.1 cm²** and its thickness lever (0.6 → 0.4 mm = **4.51 g**, ADR-055 D4)
  is **0.07 %** of a ~5 kg payload. For A the thickness is an **optimisation**.
- **Variant B must come in under 20 g total payload** — the operator's own number. At that wall
  the **same 4.5 g thickness lever is ~22 %** of the entire payload budget. In B, mass is not a
  tie-breaker; **mass is the constraint**, and the board area, thickness and cell count are
  **structural decisions**, not optimisations.

**B's parts, verified against the records (not taken on faith).** `docs/analysis/two-variant-mass-budget.md`
§1 lists B as `ESP32-S3-WROOM-1U-N8R8` + `SX1280` + bare `LoRa2021` + GNSS (`MAX-M10S`) +
voltage regulator (`TPS7A02`) + pressure sensor + capacitor — **no `LoRa2021F33-2G4`, no wing
boards, no cut/jettison hardware**. That matches this task's list. Two corrections found while
verifying: the power budget names the barometer **`MS5607-02BA03`**
(`docs/POWER-BUDGET-V9-D2BE.md` §2/§4) while the mass budget names **`MS5611`** — both parts are
named in-repo, the mass line is 0.03 g either way, and the discrepancy is recorded, not resolved;
and the F33's peak current is **1118 mA @ 5.5 V = 6.15 W** (`docs/adr/047-v9-power-provisioning.md`
§1), while ADR-034/`docs/inventory.md` state **1200 mA** for the same part — this record uses the
bounding **6.15 W**.

---

## 1. Context — why B is a different design problem

### 1.1 The absent F33 is the dominant mass **and** energy change

The `LoRa2021F33-2G4` is the module B deletes. It is:
- **the 5 V rail** — it is the *only* 5 V load in `docs/POWER-BUDGET-V9-D2BE.md` §2
  ("F33 433 MHz TX … 5 V tap"), so deleting it **deletes the whole 5 V rail**;
- **the peak load** — **6.15 W DC (1118 mA @ 5.5 V)**, ADR-047 §1, which is **2.56×** the
  accepted solar array's own peak (2.4 W, ADR-006) and is why A's *bank*, not the array, is
  the PA's source (ADR-047 §1);
- **the burst-energy driver** — A's buffer is sized to that 6 W PA: ~1 mF for an FLRC burst,
  **0.47 F** for a LoRa SF12 burst (`docs/POWER-BUDGET-V9-D2BE.md` §3, ADR-036);
- **~4.0 g** of mass (CITED, `docs/PAYLOAD-WEIGHT-ESTIMATES.md` §3 "LR2021F33, 3–5 g");
- **illegal in the licence-exempt regime the operator selected for flight** — the 2 W PA is
  "dead weight at ≤ 10 mW ERP" (`docs/V9-RADIO-SITE-MATRIX.md` §4; ADR-039).

Removing it removes the 5 V rail, the 6.15 W peak, the 0.47 F-class buffer requirement, ~4 g,
and a legal constraint at once. **B's mass and energy architecture is not "A minus a part" — it
is a single-rail, single-radio vehicle.**

### 1.2 The 20 g wall is hard, and the operator has the scale

The wall is the operator's stated design target (`docs/analysis/two-variant-mass-budget.md`
line 17: *"[B must come in] under 20 g total payload — the operator's number"*). The repo owns
a **0.01 g-resolution scale** for exactly this (`docs/inventory.md` line 68, "MS300 Waage
0,01g Aufloesung"). **Everything in §3 below that is an ESTIMATE is a thing the operator can
convert to a measurement in one sitting**, and §3 names each one.

---

## 2. Decision

**D1. Variant B is a SEPARATE BOARD from Variant A.** It is not a population option on
`hub_board_v9.kicad_pcb`. See §5; the two deciding numbers are the outline (B ≈ **61 cm²** vs A
**106.1 cm²**) and the fact that B built on A's plate **cannot clear the 20 g wall**
(§5.2: 21.06 g at 0.4 mm, 25.58 g at 0.6 mm).

**D2. B's mass budget is carried against the 20 g wall, itemised, with the margin stated and
the pessimistic case worked through** (§3). Estimated **≈ 17.2 g** on B's own board with a
0.47 F-class store (**≈ 2.8 g margin**), **≈ 18.2 g** with the Accepted 2 × AVX bank
(**≈ 1.8 g margin**). **The pessimistic case fails** (§3.4).

**D3. B has its own energy budget derived from B's radio set** (§4), not A's. Average
**≈ 0.203 W** (0.522 × A's 0.388 W), **dominated by the GNSS (25 mA, ≈49 % of the 3.3 V rail)**,
not by any radio TX. Peak **≈ 1.28 W** (one transmitter keyed at a time, ADR-035), against A's
6.15 W — **a 4.8× reduction**. Night anchor: the ADR-036/ADR-050 policy figure **100 µW**.

**D4. B's array is sized to the arithmetic MINIMUM for B's draw, on the factor that applies to
B's vehicle** (§4.4): **0.186530** — the **horizontal/flat plane** day-mean per-unit-area factor
(ADR-055 D1/D2, ADR-051 §1.4). **B's ≈ 55.4 cm²** vs A's 106.1 cm². The factor used by the
existing budget for B (**0.305107**, vertical blades) **does not transfer**: it requires four
vertical blades, and **B has no wings**.

**D5. B's outline is its own: ≈ 61 cm², ≈ 78 × 78 mm** (two LARGE cells) or **≈ 157 × 39 mm**
(six SMALL cells) — driven by the flat-array minimum plus the component court, **not** A's
103 × 103 mm (§5). Square is *not* preferred for B (B has no four-socket symmetry — ADR-048's
four 90° interfaces belong to A).

**D6. B's board thickness target is 0.4 mm** (§6), the ADR-055 D4 target; it saves **≈ 2.60 g**
against 0.6 mm at B's own ≈ 61.2 cm² outline. A stiffness/stack-up check is **required** before
it is frozen (ADR-055 D4, Open item 3) and is **not** done here.

**D7. Nothing is ordered, and no board is drawn, by this record.**

---

## 3. The mass budget against the hard 20 g wall

### 3.1 Shared constants (unchanged from the existing budget — they are cell/geometry constants, not A-specific)

| Constant | Value | Provenance |
|---|---|---|
| FR4 density × uplift | 1.85 g/cm³ × 1.15 | **CITED** `docs/PAYLOAD-WEIGHT-ESTIMATES.md` line 20 |
| 0.6 mm FR4 areal mass | **127.65 mg/cm²** | **COMPUTED** 0.060 × 1.85 × 1.15 |
| 0.4 mm FR4 areal mass | **85.10 mg/cm²** | **COMPUTED** 0.040 × 1.85 × 1.15 |
| 0.21 mm bare-Si areal mass | **48.93 mg/cm²** | **COMPUTED** 0.021 × 2.33 |
| **Cell areal density, bare-Si** | **48.93 mg/cm²** | same |
| Cell areal density, repo's heavy listing | 195.6 mg/cm² (≈2 g per 52 × 19 cell) | **CITED** `docs/analysis/wing-mass-shape.md` §1.2/§8 item 1 — a **4×** conflict with bare-Si, flagged not resolved |
| 30 AWG line | 0.460 mg/mm | **CITED** `docs/analysis/wing-mass-shape.md` §2.4 |

### 3.2 B's itemised budget — own board, flat minimum array, 0.47 F store

| # | Item | Unit (g) | Qty | Subtotal (g) | Source / class |
|---|---|---:|---:|---:|---|
| B1 | **B's own hub PCB, ≈ 61.2 cm² FR4, 0.4 mm** | 5.21 | 1 | **5.21** | **COMPUTED** 61.2 cm² × 85.10 mg/cm² — B's own outline (§5), the array carrier ARE the board (ADR-055 D6/D7) |
| B2 | `ESP32-S3-WROOM-1U-N8R8` | 2.5 | 1 | **2.5** | **ESTIMATE** by analogy to the repo's `ESP32-C3-Mini-1` line (2.5 g) in `docs/PAYLOAD-WEIGHT-ESTIMATES.md` §3 — **no S3 mass anywhere in repo** (`docs/V9-RADIO-SITE-MATRIX.md` §3.5) |
| B3 | `SX1280IMLTRT` + matching/passives | 0.2 | 1 | **0.2** | **ESTIMATE** (QFN-24 + 0402 class) |
| B4 | Bare `LoRa2021` castellated module | 1.2 | 1 | **1.2** | **CITED** `docs/PAYLOAD-WEIGHT-ESTIMATES.md` §3 ("LR2021 bare, 1–2 g"); exact part `TODO(unverified)` |
| B5 | GNSS `MAX-M10S` (bare, direct-soldered) | 0.4 | 1 | **0.4** | **CITED** same §3 (breakout is 1.0 g) |
| B6 | LDO `TPS7A02` (SOT-23-5) | 0.05 | 1 | **0.05** | **CITED** `docs/component-guide.md` §6 |
| B7 | Pressure sensor `MS5611` / `MS5607` (bare) | 0.03 | 1 | **0.03** | **CITED** `docs/POWER-BUDGET-V9-D2BE.md` §4 / `PAYLOAD-WEIGHT-ESTIMATES.md` §3 |
| B8 | Supercap 0.47 F class | 2.0 | 1 | **2.0** | **ESTIMATE** 2–7 g/F × 0.47 F vs the repo's 0.45 g/F AVX cell — **no 0.47 F part named anywhere** |
| B9 | **Solar cells, 61.2 cm² bare-Si** (flat array, §4.4) | 2.99 | 1 | **2.99** | **COMPUTED** 61.2 × 48.93 mg/cm² — bare-Si floor; the heavy listing would be 11.97 g (see §3.4) |
| B10 | Charge-path converter (ADR-050 MPPT, retained) | 1.0 | 1 | **1.0** | **CITED band** ADR-050 §3.7 (≈ 0.70–1.20 g); **required** for B because the flat minimum array cannot reach the bank voltage by direct connection (§4.5) |
| B11 | Antenna wire dipole | 0.2 | 1 | **0.2** | **CITED** `PAYLOAD-WEIGHT-ESTIMATES.md` §3 |
| B12 | Connectors, passives, solder paste, potting | 1.0 | 1 | **1.0** | **ESTIMATE** — repo bands 0.5–1 g + 0.2–0.5 g (`PAYLOAD-WEIGHT-ESTIMATES.md` Key Assumptions 8/9); **not itemised anywhere** |
| B13 | Balloon attachment (30 AWG, ~1 m) | 0.46 | 1 | **0.46** | **COMPUTED** 1 m × 0.460 mg/mm |
| | **B TOTAL — own board, 0.47 F store** | | | **≈ 17.2 g** | **margin vs 20 g ≈ 2.8 g** |
| | **B TOTAL — own board, Accepted 2 × AVX 3.3 F bank (3.0 g)** | | | **≈ 18.2 g** | **margin vs 20 g ≈ 1.8 g** |

**Deleted from A to get B:** the F33 (−4.0 g), the four wing boards + cells + solder (−41.2 g),
the jettison hardware (−2.0 g), and A's four-wing structure entirely — **≈ 50 g removed for
≈ 17 g kept.** That is still why B clears the wall *nominally*. It is **not** because the 20 g
line is soft.

**Why the total is ~17.2 g and not the existing budget's 12.9 g.** Two B-specific corrections,
both forcing the number **up**:

1. **B's array is flat, so it is 1.64× larger per watt** (§4.4). The existing budget sized B's
   array at 32.9 cm² using the **vertical-blade** factor 0.305107 — a factor that **requires four
   vertical wings that B does not have**. On the factor that actually applies to B (0.186530,
   horizontal), B's minimum array is **55.4 cm²**, realised as **61.2 cm²** of whole cells.
   Cells go from 1.61 g → **2.99 g**.
2. **A board of B's own, sized to that array, is 61.2 cm², not the existing budget's 55.15 × 45.15 mm
   (24.90 cm²) hub.** At 0.4 mm that is 5.21 g, not 2.12 g. The board is the array carrier
   (ADR-055 D6), so the board area *is* the array area.

### 3.3 Where B's grams actually are

| Rank | Item | g | Share | Own/declared |
|---:|---|---:|---:|---|
| 1 | B's own PCB, ≈ 61.2 cm² @ 0.4 mm | 5.21 | 30.2 % | **structural** (array-driven) |
| 2 | Solar cells, 61.2 cm² bare-Si | 2.99 | 17.3 % | structural |
| 3 | `ESP32-S3-WROOM-1U-N8R8` | 2.5 | 14.5 % | **ESTIMATE** — weight it |
| 4 | Supercap | 2.0 | 11.6 % | **ESTIMATE** |
| 5 | bare `LoRa2021` | 1.2 | 7.0 % | CITED |
| 6 | Charge-path converter | 1.0 | 5.8 % | CITED band |
| 7 | Connectors/passives/potting | 1.0 | 5.8 % | **ESTIMATE** |
| 8 | Balloon attachment | 0.46 | 2.7 % | COMPUTED |
| 9 | GNSS | 0.4 | 2.3 % | CITED |
| 10 | SX1280 + matching | 0.2 | 1.2 % | **ESTIMATE** |
| 11 | Antenna wire | 0.2 | 1.2 % | CITED |

**The two structural items (PCB + cells) are 47.5 % of B.** Unlike A — where moving the wing
carrier full → spine saves 16.35 g in one decision — **B has no single large lever left**; its
biggest is the 0.4 mm thickness choice (2.60 g, §6). **B's mass is dominated by the board and
the cells, both structural, both set by the flat-array minimum.**

### 3.4 The pessimistic case — **B does NOT clear 20 g if every soft number goes bad**

This is the spine of the task: §4.2 of `docs/analysis/two-variant-mass-budget.md` asked whether B
still clears 20 g when every soft number is pessimistic. Re-worked at B's **own** (flat) array
area, the answer changes from "yes, mostly" to **no**.

| Pessimistic assumption | Delta | B total (own board, 0.47 F store) |
|---|---:|---:|
| (baseline) | — | **17.24 g** |
| S3 module is **5 g**, not 2.5 g | +2.50 g | 19.74 g — *passes* (barely) |
| Solar cells use the repo's **heavy 2 g/cell** listing, not bare-Si (61.2 cm² ⇒ +8.98 g) | +8.98 g | **26.22 g — FAILS** |
| Supercap is the **top of the range** (3.3 g, not 2.0 g) | +1.30 g | 18.54 g — *passes* (barely) |
| **S3-heavy + cell-heavy** | +11.48 g | **28.72 g — FAILS** |
| **All three at once** | +12.78 g | **30.02 g — FAILS** |

Restated honestly: **B clears 20 g on two of the three single-pessimism axes and fails on the
third; it fails every combination of two or more.** With the Accepted 2 × AVX bank (3.0 g) the
baseline becomes 18.24 g and even the **S3-alone** pessimism fails (20.74 g).

The burden of the whole verdict therefore sits on **two unweighed items** — the **S3 module** and
the **cell mass** — exactly as the existing budget said, but at B's *real* array area the
cell-mass axis alone is enough to break the wall. **What settles it: weigh one
`ESP32-S3-WROOM-1U-N8R8`, one 52 × 19 mm cell and one 78 × 39 mm cell on the MS300 0.01 g scale
(`docs/inventory.md` line 68)** and record the three numbers in this record.

### 3.5 ESTIMATE vs MEASUREMENT — the operator's weighing list

**Nothing in §3.2 is a measurement of a physical part.** Every gram is arithmetic on a cited
constant, an in-repo computed figure, or a labelled ESTIMATE. The lines that are **ESTIMATE**
(not CITED, not COMPUTED) are: **B2 (S3, 2.5 g), B3 (SX1280, 0.2 g), B8 (supercap, 2.0 g),
B12 (connectors/potting, 1.0 g)**; and **B9's floor is COMPUTED from a constant whose repo
listing differs 4×**. B10 is a CITED *band* (0.70–1.20 g), not a point value. **To be weighed
on the 0.01 g scale before this budget is trusted:** the S3 module, one LARGE and one SMALL cell,
the bare `LoRa2021`, an `SX1280IMLTRT` + its passives, the chosen supercap part, and (if
selected) a charge-path converter.

---

## 4. B's own energy budget and array sizing

### 4.1 Why A's 0.388 W must not be imported

`docs/POWER-BUDGET-V9-D2BE.md` §2 builds A's average from **two rails**:
`5 V rail (F33): 0.0318 A × 5.0 V = 0.159 W` and `3.3 V rail: 49.6 mA × 3.3 V = 0.164 W`,
giving `(0.159 + 0.164) × 1.20 = 0.388 W`. **0.159 W of that — 41 % of the input power before
the 1.20 allowance — is the F33, the only 5 V load.** B deletes the 5 V rail entirely, so
importing 0.388 W into B would be importing a load B does not carry. But **nor may B simply
copy A's 3.3 V line**: B *has* a transmitter (the bare `LoRa2021`, ADR-040's default-populated
LP part), and A's 3.3 V sum explicitly **excludes** the bare module's own TX/RX currents
(`docs/POWER-BUDGET-V9-D2BE.md` §2 lists "bare LoRa2021 2.4 GHz RX … TODO"). B's budget must
therefore **add** the LP module's own TX and RX terms.

### 4.2 B's load table (3.3 V rail only)

| Load | Peak | Duty | Average (mA) | Source |
|---|---:|---:|---:|---|
| bare `LoRa2021` **TX @ 433 MHz, +22 dBm** | 120 mA | 1 % | 1.20 | **CITED** `docs/inventory.md` line 29 (`TX @433MHz 22dBm: <120mA`); duty = ADR-035 TDM class, `TODO(unverified)` |
| bare `LoRa2021` **RX @ 2.4 GHz** | 7 mA | 5 % | 0.35 | **CITED** `docs/inventory.md` line 30 (`RX 2.4GHz: <7mA`) |
| bare `LoRa2021` sleep | 2 µA | 94 % | ≈0 | **CITED** `docs/inventory.md` line 31 |
| `SX1280` ranging TX (+13 dBm) | 70 mA | 0.2 % | 0.14 | `docs/POWER-BUDGET-V9-D2BE.md` §2 — `TODO(unverified)` on the peak |
| `SX1280` ranging RX | 15 mA | 2 % | 0.30 | same |
| `ESP32-S3` CPU + digital | 240 mA | 10 % | 24.0 | same — `TODO(unverified)` |
| GNSS `MAX-M10S` tracking | 25 mA | continuous | 25.0 | same — `TODO(unverified)` budget |
| pressure sensor conversion | 1.5 mA | 10 % | 0.16 | same — `TODO(unverified)` |
| `TPS7A02` LDO quiescent | 25 nA | continuous | ≈0 | **CITED** ADR-006 §LDO |
| **3.3 V rail average** | | | **51.15 mA** | |

```
B input power = 51.15 mA × 3.3 V × 1.20 = 0.2026 W  ≈  0.203 W
B / A         = 0.2026 / 0.388  =  0.522
```

**B's average draw ≈ 0.203 W, 52 % of A's 0.388 W.** Two things must be said plainly:

- **The dominant term is the GNSS, not a radio.** `MAX-M10S` at 25 mA continuous is
  **49 % of the 3.3 V rail**. Drop GNSS to intermittent tracking and B's average falls to
  **≈ 0.104 W** (the last row of the calculation) — halving B's array. **Whether the mission
  needs continuous GNSS is a mission decision, not a hardware one, and it is deferred (§8).**
- **This number is a floor, not a ceiling.** Every peak in the table is `TODO(unverified)` in the
  repo, and `docs/POWER-BUDGET-V9-D2BE.md` §2's duty cycles are explicitly *"design targets, not
  measured flight values"*. The number is honest arithmetic on the repo's stated inputs; it is
  not a measurement.

### 4.3 B's peak draw — the burst the buffer must hold

Worst case, honouring ADR-035's **one-transmitter-at-a-time** invariant:

```
S3 CPU/digital 240 mA + bare LoRa2021 TX @433 120 mA + GNSS 25 mA + baro 1.5 mA
  = 386.5 mA @ 3.3 V = 1.275 W  ≈ 1.28 W
(if the invariant were violated and the SX1280 ranged while the LP keyed: 456.5 mA = 1.51 W)
```

**B's peak ≈ 1.28 W against A's 6.15 W — a 4.8× reduction**, and the direct consequence of the
absent F33. It collapses the burst-buffer requirement that drove A's 0.47 F-class store
(`docs/POWER-BUDGET-V9-D2BE.md` §3):

| B burst | Energy | Buffer C for 5.4 V → 3.5 V |
|---|---:|---:|
| 100 B FLRC @ 2.6 Mbps (0.308 ms) | 0.39 mJ | **≈ 47 µF** (millifarad-class, ~0.2 g) |
| LoRa SF12/BW125 minimal packet (0.656 s) | 0.836 J | **≈ 0.099 F** |

So B's *worst-case* (SF12) buffer is **≈ 0.1 F**, not 0.47 F. This is a **saving the existing B
budget does not bank** (it carried A's 0.47 F option forward without re-deriving it from B's
own peak) and it is recorded here as a lever, not applied to §3.2's total.

### 4.4 B's array: the factor that applies to B's vehicle, and the arithmetic minimum

**Which way does B's array face?** B has **no wings** — no vertical blades, no jettison, no
socket land sets. Its array can only be **the hub board's own upper face**, and ADR-055 D1/D6
fix that plane as **HORIZONTAL, flat, un-tilted** ("The hub array lies in a HORIZONTAL plane —
flat, un-tilted"; "the hub-array cells are mounted on the UPPER face"). ADR-055's orientation
decision was made for A's hub, but its **physics is a property of a flat body-mounted array**,
so it applies to B's array by construction.

```
FLAT/horizontal plane, day-mean per-unit-area factor = 0.186530      [ADR-051 §1.4; ADR-055 D2]
  (contrast: VERTICAL blade, day-mean            = 0.305107          [requires four vertical fins])
ratio vertical/flat = 0.305107 / 0.186530 = 1.6357                    [ADR-055 §1.2]

large-cell nameplate density = 0.60 W / 30.6 cm² = 19.608 mW/cm²      [ADR-051 §1.3]
flat day-mean harvested density = 19.608 × 0.186530 = 3.658 mW/cm²    [ADR-051 §1.4]

A: 388 mW / 3.658 mW/cm² = 106.1 cm²   ← reproduces ADR-051 §1.4's flat-plane figure
B: 203 mW / 3.658 mW/cm² =  55.4 cm²   ← B's arithmetic MINIMUM on the factor that applies to B
```

**The insolation factor that applies to B is 0.186530, and it does NOT transfer from the
existing B budget's 0.305107.** The existing budget used the vertical-blade factor for B; that
factor is earned only by four vertical planes, i.e. by the wings **B does not have**. Using the
flat factor **raises B's minimum installed area from 32.9 cm² to 55.4 cm² (1.64×)** — which is
exactly B's share of ADR-055's own vertical-vs-flat ratio, and is the single largest correction
this record makes to the existing B budget.

**Why this area is the arithmetic minimum and not a duty choice.** For A, ADR-055 D3 makes the
array area a **ceiling chosen by the operator's sustained-duty decision** (≈106 cm² = full duty,
≈53 cm² = 50 % duty) — A *may* degrade. **B may not**: at a 20 g wall the area is fixed by the
draw it must cover, and 55.4 cm² is the **floor**, not a ceiling. B has no duty knob here.

**Cell granularity.** 55.4 cm² of installed cell area realises as **two LARGE cells (2 × 30.6 =
61.2 cm²)** or **six SMALL cells (6 × 10.23 = 61.4 cm²)** — 61.2 cm² is the built figure used
throughout §3. The conservative, derate-inclusive area (ADR-051 §1.6's chain: × 0.9 envelope
shading × 0.85 charge-path efficiency, the latter `TODO(unverified)` even in ADR-050) would be
**≈ 72.4 cm²** — a bound, stated but not adopted as the minimum.

**Recorded alternative (not chosen).** If B mounted a **single vertical fin** the factor would be
0.305107 and the minimum area **≈ 33.9 cm²** — but that adds a structural plane and an interface
to a vehicle whose whole point is that it has none, and at cell granularity it saves at most two
SMALL cells (≈ 1.0 g bare-Si / ≈ 4.0 g on the heavy listing). **The measurement that would settle
it** is the built mass of a fin + its interface versus the saved cells.

### 4.5 The consequence the area reveals: the charge path is mandatory for B

A flat array of B's minimum area delivers **~1.0–1.2 V** (two LARGE cells in series). The
accepted bank sits at **5.4 V** and ADR-049 records that even a **6-cell / 3.0 V** string
"**cannot charge the 5.4 V bank at all**". **B's minimum array therefore cannot feed the bank by
direct connection.** B **must** use a converter that harvests at low input voltage — the
ADR-050 single MPPT charge-path converter (operator-approved: *"a single MPPT charge-path
converter between the array and the supercap bank"*, ADR-050 §0) or the **bq25570**-class
harvester ADR-055 D2 already specifies as the low-input-voltage reference (cold-start
`VIN(CS)` 600 mV typ; ADR-051 §2.2). This is why **B10 (1.0 g) is in B's mass budget** — it is
not optional for B, whereas for A the converter competes with the four-wing string.

### 4.6 The night anchor

B inherits ADR-036's policy in full: **daylight-only TX, mandatory night deep-sleep, cold start
at dawn accepted**. The night anchor is the policy figure the record names — **100 µW** of
housekeeping (ADR-036's arithmetic: 100 µW × 10 h = 3.6 J ≈ 0.3 F, versus 1 mW × 10 h = 36 J
which "needs multi-farad storage, contradicting the burst-sized mass goal"). This figure
**transfers to B** because it is a statement about the *payload's sleep*, not about the F33 —
but **B's realised deep-sleep current is unmeasured** (ADR-036 Open item; ADR-059's night bound is
`I_Q ≤ 5 µA`). At 100 µW / 3.3 V = 30 µA the night cannot also carry the GNSS; B's night is
deep-sleep-or-nothing, exactly as ADR-036 decided.

---

## 5. B's outline, and whether B is a separate board

### 5.1 The outline follows the array

For B there is no four-socket symmetry (ADR-048's four 90° interfaces belong to A), so B's board
is free in shape and its area is set by the **array plus the component court**:

```
array minimum (installed cells)   55.4 cm²
component court                   ≈ 25 cm²   [ADR-055 D7 — TODO(unverified), no in-repo source]
integrated board area            = max(55.4, 25) = 55.4 cm²
cell-granular built area         = 61.2 cm²  (2 LARGE)  or  61.4 cm² (6 SMALL)
```

Two concrete outlines, both **false** for A's plate:

| B outline | Shape | Area |
|---|---|---:|
| two LARGE cells, end-mounted (ADR-052), side by side | ≈ **78.6 × 77.8 mm** | 61.1 cm² |
| six SMALL cells, 3-series × 2-parallel | ≈ **156.2 × 39.3 mm** | 61.4 cm² |
| *A's board (for comparison)* | **103 × 103 mm** | **106.09 cm²** |

**Conclusion: B needs its OWN outline — ≈ 61 cm², e.g. ≈ 78 × 78 mm — not A's 103 × 103 mm.**
Square is convenient but *not* a requirement for B (ADR-055 D5's square preference rests on A's
four-socket symmetry, which B does not have). An integrated single board is lighter than
splitting electronics from a separate array carrier
(61.2 cm² × 85.10 = 5.21 g, versus ≈ 2.13 g for a 25 cm² electronics board **plus** 5.21 g for a
61 cm² carrier **plus** a connector) — so **B should use one integrated board**, which decides
ADR-055 D7's open question *for B only*.

### 5.2 B on A's board cannot clear the wall — the arithmetic that forces a separate board

If B were a population option on `hub_board_v9.kicad_pcb` (103 × 103 mm = 106.09 cm²), the board
alone is the whole problem:

| B's electronics carried on… | Board mass | + B's non-board items (12.03 g) | Total | vs 20 g |
|---|---:|---:|---:|---|
| **B's own ≈ 61.2 cm² board @ 0.4 mm** | 5.21 g | 12.03 g | **17.24 g** | **PASS** |
| A's 106.09 cm² @ 0.4 mm | 9.03 g | 12.03 g | **21.06 g** | **FAIL** |
| A's 106.09 cm² @ 0.6 mm | 13.54 g | 12.03 g | **25.58 g** | **FAIL** |

**A's board plate — even at the 0.4 mm target — consumes enough of the 20 g wall that B's
electronics cannot ride on it.** Sharing A's outline is not merely sub-optimal; it **breaks the
one constraint B exists to satisfy**. This is the finding, and it is what D1 rests on.

### 5.3 What B's board does NOT carry (and why the outlines can never be one artifact)

- **No wing socket land sets** (ADR-048's four interfaces at 90°) — B has no wings.
- **No `LoRa2021F33-2G4` site** and **no 5 V rail / PA provisioning** — ADR-040's Site-A
  HP option and ADR-047's 6.15 W provisioning are A's.
- **No jettison/cut channels** (ADR-049/051 cut ladder) — B has nothing to cut.
- **Fewer radio pins**: ADR-108's plan carries the F33 on SPI2 with 8 control lines; B's F33-free
  radio set frees those lines, and the `-N8R8` PSRAM pins IO35/36/37 (ADR-029 D1.1) stay
  reserved exactly as in A. B's pin plan is **not** derived here (deferred).

**Verdict (D1): YES — B is a separate board.** Distinct outline (≈ 61 cm² vs 106.09 cm²),
distinct radio population, distinct power architecture (no 5 V rail), distinct array
(no wings), no shared mechanical interface. The only thing B shares with A is a parts bin.

---

## 6. Thickness

**Recommended: 0.4 mm** — the ADR-055 D4 target, and the largest remaining lever on B.

| B's ≈ 61.2 cm² board | Mass | vs 0.6 mm |
|---|---:|---:|
| 0.6 mm FR4 (current `hub_board_v9.kicad_pcb` thickness) | 7.81 g | — |
| **0.4 mm FR4** | **5.21 g** | **−2.60 g** |

**Reasoning.** FR4 areal mass is linear in thickness (85.10 vs 127.65 mg/cm², both derived from
`docs/PAYLOAD-WEIGHT-ESTIMATES.md` line 20's density × uplift), the board *is* the array carrier
(ADR-055 D6), and ADR-055 D4 already names 0.4 mm as the hub target and quantifies it as "larger
than any other single lever left on the hub". On B that lever is **2.60 g = 13 % of the whole
payload** — a structural decision, not an optimisation, exactly as the 20 g wall demands.

**The cost, stated:** a 0.4 mm plate is less stiff. ADR-055 D4 requires a **stack-up / stiffness
check before 0.4 mm is frozen** (Open item 3, `TODO(unverified)`) — and B carries no cantilevered
wings, so B's mechanical load case is **lighter** than A's (single point attachment, no four-arm
moment), which makes 0.4 mm *more* defensible for B than for A, not less. Whether the chosen
supplier fabricates B's 4-layer-or-fewer stack at 0.4 mm is a fab question, deferred.

**Mass consequence:** 2.60 g saved; B's total with 0.4 mm is **≈ 17.2 g** (§3.2). At 0.6 mm it
would be **≈ 19.8 g** — inside 20 g only nominally, and failing on the first pessimistic axis.

---

## 7. Consequences

### Positive

- **The two variants are separated on the record.** B is a separate board (D1, §5) with its own
  mass (§3), energy (§4) and outline (§5) — a later session cannot silently fit B's parts onto
  A's 103 × 103 mm plate and call it a population option.
- **The transferred-factor error is corrected in writing.** B's array factor is 0.186530, not
  0.305107; using A's blade factor on a wingless vehicle under-sized B's array by 1.64× (§4.4).
- **The 6.15 W peak is removed from B's problem**, collapsing B's buffer from 0.47 F-class to
  ≈ 0.1 F and its peak from 6.15 W to 1.28 W (D3, §4.3).
- **The pessimistic boundary is now explicit and honest:** B fails the multi-axis pessimistic
  case (§3.4), and the two items that decide it (S3 mass, cell mass) are named and weighable.
- **The GNSS is identified as B's dominant load** (49 % of the 3.3 V rail) — the lever that
  matters most is a mission decision, now visible.

### Costs (accepted)

- **B's nominal margin is only ≈ 2.8 g** (0.47 F store) / **≈ 1.8 g** (Accepted AVX bank), not the
  ≈ 7 g the existing budget claimed — and **zero** under the pessimistic case.
- **B's array must be ≈ 1.64× larger per watt** than a vertical-blade vehicle's, because it has
  no wings (D4). This is the price of B being wingless, and the existing budget did not pay it.
- **The charge path is mandatory for B** (§4.5): the flat minimum array cannot charge the 5.4 V
  bank directly, so B carries a converter and its ~1 g plus a failure mode that A's four-wing
  string does not.
- **B's board is a form-factor of its own** — a new outline, a new placement, a new BOM. It is
  **not** free by reusing A's plate; per §5.2, reusing A's plate is what B cannot afford.
- **B inherits no solar redundancy** (no jettisonable blades) and, with a flat array, **no
  instantaneous peak** — it runs at ≤ 0.286 of face-on at 50 °N winter noon (ADR-055 D2).

---

## 8. Open items / deferred (kept open, not resolved here)

1. **Weigh the deciding parts** on the MS300 0.01 g scale (`docs/inventory.md` line 68):
   `ESP32-S3-WROOM-1U-N8R8`, one 52 × 19 mm cell, one 78 × 39 mm cell, the bare `LoRa2021`,
   an `SX1280IMLTRT`, the chosen supercap part, and (if selected) the charge-path converter.
   **This is the single highest-value action.**
2. **B's GNSS duty** — continuous tracking (the 25 mA assumption) vs intermittent. Dropping it
   roughly halves B's average (0.203 → 0.104 W) and its array (55.4 → 28.6 cm²). A mission
   decision; it is the largest remaining lever on B.
3. **B's TX band and power** — 433 MHz / +22 dBm / 120 mA (the ADR-034-consistent choice) or
   2.4 GHz / +12 dBm / 35 mA. This sets B's peak and its link budget.
4. **B's charge-path converter type and part** (§4.5) — ADR-050's MPPT vs the bq25570-class
   harvester; ADR-050 is Proposed and its converter is `TODO(unverified)`.
5. **B's board layer count and the 0.4 mm stack-up/stiffness check** (ADR-055 D4, Open item 3) —
   required before 0.4 mm is frozen.
6. **Integrated board vs separate array carrier** — decided for B by mass (§5.1), but the trade
   should be re-costed once a layout exists (ADR-055 D7).
7. **B's board layout, placement, routing, schematic, netlist** — the NEXT stage, after this
   basis lands. Nothing is drawn here.
8. **The launch latitude and season** — every insolation figure assumes **50.0 °N, winter
   solstice** (`docs/analysis/wing-insolation-geometry.md` §1); no in-repo source states it.
9. **The derate factors** — envelope shading 0.9 (`docs/SOLAR-PIN-REGULATORY.md` §1.1) and
   charge-path efficiency 0.85 (ADR-050, itself `TODO(unverified)`). Adopting them would take B's
   array from 55.4 → ≈ 72.4 cm².
10. **B's night deep-sleep current (µA)** — decides whether B's flight log survives the night
    (ADR-036 Open item).
11. **The NTC provision (ADR-059) for B's bare module** — DNP (~0 g); whether B's crystal-drift
    exposure (ADR-040 Open item 2, no TCXO on the LP part) requires it to be fitted is open.
12. **The 20 g wall's legal status** — owned by the parallel task
    (`analysis/free-balloon-mass-threshold`); **this record does not assert 20 g is a legal
    limit**, only the operator's design target.

---

## 9. Authorised by this record

Nothing that touches hardware. **No schematic, netlist, placement, routing, BOM or order change
is authorised**, and `tracker/hardware/hub_board_v9.kicad_pcb` is **not modified** (ADR-first).
Design work only — **order nothing**.

## 10. Rollout

1. **Operator accepts, amends, or rejects this text.** It is `Proposed`.
2. **Operator weighs the §8.1 parts** and records the numbers here (an append-only amendment).
3. **The B board is laid out** against B's own outline (§5) — next stage.
4. `python3 scripts/gen_adr_index.py` regenerates `docs/adr/INDEX.md`;
   `python3 -m pytest tests/test_adr_numbering.py -q` stays green.

## 11. Notes

- **What this record does not do:** it is not a board, a schematic, a BOM or an order; it does
  not resolve the GNSS-duty, TX-band, converter-type or stack-up questions (all §8); it does not
  re-derive A's budget and it **modifies no A artefact**.
- **Re-verified, not inherited.** Every A figure reused here is reused **with its reason stated**:
  the FR4 areal masses (cell/geometry constants), the cell-class nameplate density (a
  cell property, transferable), the module/cell mass lines (parts B still carries), and the
  ADR-036 energy policy (a policy about the payload, not about the F33). The two figures
  **deliberately NOT inherited** are A's **0.388 W** average (§4.1) and the **0.305107** array
  factor (§4.4).
- **A's board, verified in the file.** `tracker/hardware/hub_board_v9.kicad_pcb` is a
  **Variant-A** board: `(thickness 0.6)`, four copper layers (`F.Cu`, `In1.Cu`, `In2.Cu`,
  `B.Cu`), and an `Edge.Cuts` extent to **(103, 103) mm** — i.e. the ≈103 mm square ADR-055 D5
  set as A's destination, now realised. **ADR-055 §3's line "no v9 hub PCB exists, so nothing is
  frozen in a board file" is stale** — the v9 hub board has since landed on
  `github/main` (`feat/v9-hub-placement`), so A's outline is now a drawn artifact, not a target.
  That does not change ADR-055's logic; it fixes the starting point.
- **Honesty.** Every number above is (i) a printed output of the arithmetic shown, (ii) cited to
  the in-repo source named beside it, or (iii) marked ESTIMATE / `TODO(unverified)`. **Nothing
  unverified is asserted as measured**, and no datasheet value, part number or mass is invented.
  The < 20 g wall is the operator's design target, not a legal threshold.
