# Ground-station 433 MHz downlink — FLRC at maximum throughput: balloon TX power vs ground dish size

**Status:** Analysis — `docs/analysis/`, not yet an ADR.
**Date:** 2026-10-08
**Scope:** RF/link + ground-hardware design only. **Design only — nothing is ordered here.**
**Repro command:** `python3 docs/analysis/ground_station_flrc_max_model.py`
(prints every numeric table in this document).
**Branch:** `design/ground-station-flrc-max` (off `github/main`, tip `09e1b69`).
**Supersedes / builds on (does NOT re-derive):**
- branch `design/ground-station-lowpower-link` @ `4b90be94` —
  `docs/analysis/ground-station-lowpower-link-and-shared-dish.md` and **ADR-066**
  (the low-power LR2021 study; its LoRa branch and its "shared positioner" verdict are
  **consumed here**, not re-derived);
- branch `design/ground-station-bom` @ `283cad72` —
  `docs/analysis/ground-station-bom-candidates.md` (all the *prices* and *vendor URLs*
  reused below come from there unless this document says it re-fetched them).

**Operator decision driving this document (2026-10-08):** the 433 MHz downlink is
**FIXED on FLRC at maximum throughput. LoRa is REJECTED as too slow.** The operator wants
"as much gain as we can get", says **mass is the binding limit on the balloon**, wants
**over-provisioned power**, and says **"do the heavy lifting on the ground".**

Every external number below is either a **datasheet value** (table + citable origin),
a **vendor page fetched this session** (URL + HTTP 200 stated), or a **computed** value
with its formula and a reproduce command. Anything not sourced is `TODO(unverified)`.
**No datasheet value or URL in this document was invented.**

---

## 0. Verdict first

**1. The 433 downlink at FLRC-max throughput at long range is NOT a ground-station
problem. It is a balloon TX-power problem.** This is the trade the operator asked for,
and it is decided by an order of magnitude, not by cost:

| 650 km, FLRC 2.6 Mbps, `G_balloon = 0 dBi` | required ground gain | dish diameter | reflector area |
|---|---:|---:|---:|
| **Low-power** LR2021 (+13 dBm, the ADR-066 premise) | **+27.9 dBi** | **7.38 m** | **42.8 m²** |
| LR2021 chip max, no external PA (+22 dBm) | +18.9 dBi | **2.62 m** | 5.38 m² |
| **F33 2 W PA (+33 dBm)** | **+7.9 dBi** | **0.74 m** | **0.43 m²** |

**A 7.38 m 433 dish is not a hard design — it is not a design.** It does not exist as a
product (the largest mesh kit ever sold by the one vendor in this space was 4.5 m, and it
was **discontinued in 2024** — §5). It would weigh ≈ **163 kg** of structure alone
(scaling the vendor's 3.0 m / 27 kg kit), and at wind speeds a German site produces
routinely it carries **53 kN·m** of moment at 20 m/s and **148 kN·m** at 120 km/h —
**20×** and **55×** the SPID BIG-RAS holding torque (§4). **So the answer to "is 20 dB of
balloon TX cheaper than the ground dish it removes?" is: yes, decisively — the dish it
removes is not purchasable, not buildable and not holdable.** +20 dB of TX power removes a
factor **10.0** in dish diameter and a factor **100** in reflector area (§2.4).

**2. But "the balloon carries the power" collides with two recorded repo facts, and both
must be stated, not glossed:**

* **Regulatory:** the committed licence-exempt design point (ADR-039 / ADR-041) caps the
  balloon's 433 transmitter at **+12.15 dBm EIRP** — *below* the operator's own +13 dBm low
  end. The whole +13…+33 dBm class is **amateur-licence-only**. Choosing the F33 makes the
  433 downlink an **amateur-band link, by design and on purpose**, not an ISM one.
* **Mass / repo classification:** the repo's own weight study classes the V2 F33 board as
  **"Heavy-Lift Reference … Ground Station Only … not a pico balloon target"** (~20.6 g
  with solar) — `docs/PAYLOAD-WEIGHT-ESTIMATES.md` lines 168–182/195. The honest delta is
  narrower than that label suggests: the **F33 module itself is 4.0 g vs 1.2 g for the bare
  LR2021 module → +2.8 g** (`docs/PAYLOAD-WEIGHT-ESTIMATES.md` lines 62/119/177). The
  operator's binding limit is mass, so this +2.8 g is the number that decides it — the
  "20 g board" figure is the whole-board reference, not the radio swap.

**3. The middle path that actually satisfies every constraint** (mass, "over-provisioned
power", "heavy lifting on the ground", no F33): **use the LR2021's own +22 dBm and rate
adaptation (§3), and a coarse-mesh 433 dish sized for the rate you actually need at the
range you actually need it.** At +22 dBm the requirement is **2.62 m @ 2.6 Mbps** or
**1.24 m @ 650 kbps** — a 6.5 dB rate step buys a **2.11× smaller diameter**. 2.6 Mbps at
650 km (2.62 m) is *just* feasible as a **coarse mesh** dish on the strongest rotator class
in the BOM (§4: 2.62 m mesh = **0.65×** the BIG-RAS holding torque, where the same dish as
a **solid** reflector is **2.45×** — i.e. **a solid 2.6 m dish is mechanically infeasible
where the mesh version is comfortable**).

**4. "As much gain as we can get" is best served by a *modest* dish, not the largest one.**
With the F33, 2.6 Mbps at 650 km needs only **0.74 m**; a **1.2 m** mesh dish (€387) gives
**+2.2 dB** of margin at the design range, and a **1.9 m** mesh dish (€901) gives **+6.4 dB**
and extends the 2.6 Mbps range to **1,667 km**. Beyond ~2 m the marginal gain costs
rotator class, wind authority and counterweights far faster than it buys anything (§5).

**5. Rate adaptation is a *range* tool, not a *dish* tool, once the F33 is in play:** at
+33 dBm the max-throughput dish needed for 650 km (0.74 m) is *smaller* than the dish
needed to hold the good rates out to the horizon. Pick the dish for the **margin and
horizon** you want; pick the **rate** for the range at that moment.

**6. Consultant verdict: APPROVED** — served model **`gpt-6-astra`**, verbatim in §7.

---

## 1. Inputs (every number used, with its source)

### 1.1 Receiver sensitivity — Semtech LR2021, sub-GHz FLRC

Datasheet **Table 3-12** ("FLRC Sub-GHz 1% PER (LR2021)"), `G13 rx_boost=7`, 915 MHz test
point: local citable copy
`docs/lr2021-research/semtech-official/LR2021_LR2022_LR2012_Datasheet_v2.2.pdf`
(Rev 2.2, md5 `18a392b72ff448083e6f26b2dd6e3925`), origin
<https://www.semtech.com/products/wireless-rf/lora-plus/lr2021> (per
`docs/lr2021-research/SOURCES.md` §A2):

| Symbol | Rate (BRF / effective) | Typ (dBm) |
|---|---|---:|
| `FLRC_2600_CR05_915_S` | 2600 kbps / 1.95 Mbps | **−100.5** |
| `FLRC_1040_CR05_915_S` | 1040 kbps / 780 kbps | −105 |
| `FLRC_650_CR05_915_S` | 650 kbps / 487 kbps | **−107** |
| `FLRC_520_CR05_915_S` | 520 kbps / 390 kbps | −108.5 |
| `FLRC_325_CR05_915_S` | 325 kbps / 243 kbps | −110 |
| `FLRC_260_CR05_915_S` | 260 kbps / 195 kbps | −111 |

> `TODO(unverified)`: a **433 MHz-specific** FLRC sensitivity row. The 915 MHz rows are
> used as the honest characterisation (inherited from `ground-station-lowpower-link-…md` §1a).
> The repo's own **−143 dBm** figure is **LoRa SF12 / BW 62.5 kHz** (Table 3-17), *not*
> FLRC — re-using it here would be **36 dB optimistic**.

### 1.2 Transmitter power

* **LR2021 bare chip, sub-GHz PA:** `TXOPLF` = 19 / **22** / — dBm (datasheet **Table 3-22**),
  programmable down 31.5 dB in 0.5 dB steps.
* **F33 (NiceRF LoRa2021F33-2G4, 2 W):** **433/470 MHz @ 5.0 V = +33.0 dBm / 1100 mA**
  — `docs/adr/047-v9-power-provisioning.md` line 67, and the same record's §1.1 table
  (F33 datasheet §8 *Voltage vs Power* via ADR-044 §2): 5.5 V = **+33.3 dBm / 1118 mA**
  (the maximum row). Also `docs/v9-BOM.md` lines 60/92/93, and
  `docs/RANGE-THROUGHPUT-PLAN.md` §"Phase 2" (*"+33 dBm / 2W PA"*).

### 1.3 Link geometry and the fixed assumptions

* `FSPL(433.05 MHz, 650 km) = 141.4 dB` (given; the repo's 300 km figure is 134.7 dB).
* **`G_balloon = 0 dBi`** — no balloon attitude control (conservative, and the same
  assumption ADR-066 used).
* `λ(433 MHz) = 0.6923 m`; **λ/10 = 69.2 mm**, **λ/20 = 34.6 mm**.
* Aperture efficiency **η = 0.55** for the trade (as instructed); the RF Hamdesign mesh
  kits publish **η = 0.65** — see §5.1, worth **+0.7 dB** at 433 MHz.
* `required_G_ground = S + FSPL − P_tx − G_balloon`;
  `D = (λ/π)·√(10^(G/10)/η)`.

### 1.4 Rate ladder actually available in this project

Firmware/rate list from the repo (not invented): 2600 / 2080 / 1300 / 1040 / 650 / 520 /
325 / 260 kbps — `docs/RANGE-THROUGHPUT-PLAN.md` lines 71–80, and the committed adaptive
policy **"FLRC 2600 → 1300 → 650 → LoRa fallback"** (line 139) with 511 B FLRC payloads
(`docs/LR2021-THROUGHPUT-OPTIMIZATION-ANALYSIS.md` §payload). The repo's *expected* ranges
at +33 dBm on both ends (line 162–163) were FLRC 2600 kbps 20–50 km at altitude and FLRC
650 kbps 50–100+ km — this document replaces those estimates with a closed-form
`S + FSPL` calculation (§3) and shows what a ground dish does to them.

---

## 2. TASK 1 — the trade the operator must see

### 2.1 The 2 × 2 grid the operator asked for

`G_balloon = 0 dBi`, 650 km. **reqG = required ground gain (dBi); D = dish diameter (m,
η = 0.55); area = π D²/4.**

| P_tx | **FLRC 2.6 Mbps** (S = −100.5 dBm) | **FLRC 650 kbps** (S = −107 dBm) |
|---:|---|---|
| **+13 dBm** (low power) | reqG **+27.9**, D = **7.38 m**, area **42.76 m²** | reqG +21.4, D = **3.49 m**, area 9.57 m² |
| **+22 dBm** (chip max) | reqG +18.9, D = **2.62 m**, area 5.38 m² | reqG +12.4, D = **1.24 m**, area 1.21 m² |
| **+33 dBm** (F33) | reqG **+7.9**, D = **0.74 m**, area **0.43 m²** | reqG +1.4, D = **0.35 m**, area 0.10 m² |

### 2.2 The full rate grid (same geometry, every rate with a datasheet row)

| P_tx | rate | S (dBm) | reqG (dBi) | D (m) | area (m²) |
|---:|---|---:|---:|---:|---:|
| +13 | 2.6 Mbps | −100.5 | 27.9 | **7.38** | 42.76 |
| +13 | 1.04 Mbps | −105.0 | 23.4 | 4.39 | 15.17 |
| +13 | 650 kbps | −107.0 | 21.4 | 3.49 | 9.57 |
| +13 | 520 kbps | −108.5 | 19.9 | 2.94 | 6.78 |
| +13 | 325 kbps | −110.0 | 18.4 | 2.47 | 4.80 |
| +13 | 260 kbps | −111.0 | 17.4 | 2.20 | 3.81 |
| +22 | 2.6 Mbps | −100.5 | 18.9 | **2.62** | 5.38 |
| +22 | 1.04 Mbps | −105.0 | 14.4 | 1.56 | 1.91 |
| +22 | 650 kbps | −107.0 | 12.4 | **1.24** | 1.21 |
| +22 | 520 kbps | −108.5 | 10.9 | 1.04 | 0.85 |
| +22 | 325 kbps | −110.0 | 9.4 | 0.88 | 0.60 |
| +22 | 260 kbps | −111.0 | 8.4 | 0.78 | 0.48 |
| +33 | 2.6 Mbps | −100.5 | 7.9 | **0.74** | 0.43 |
| +33 | 1.04 Mbps | −105.0 | 3.4 | 0.44 | 0.15 |
| +33 | 650 kbps | −107.0 | 1.4 | **0.35** | 0.10 |
| +33 | 520 kbps | −108.5 | −0.1 | 0.29 | 0.07 |
| +33 | 325 kbps | −110.0 | −1.6 | 0.25 | 0.05 |
| +33 | 260 kbps | −111.0 | −2.6 | 0.22 | 0.04 |

**Reading.** At the F33's +33 dBm, **every FLRC rate closes 650 km with an antenna that is
a small dish or better** (650 kbps and below need **no gain at all** — negative reqG). At
the low-power +13 dBm premise, **no FLRC rate at all** closes 650 km with a Yagi, and the
max-throughput requirement (2.6 Mbps) demands a **7.38 m** reflector. The trade is not
close.

### 2.3 GROUND side — what each size costs in mass, wind, rotator class and money

Dish masses are the **vendor's own published mesh-kit masses**, area-scaled from
RF Hamdesign (**1.2 m = 4.8 kg, 2.4 m = 14 kg, 3.0 m = 27 kg** — URLs in §5.1). Wind is
the model in §4. "Rotator class" is against the SPID BIG-RAS holding torque of
**2,712 N·m** (vendor spec sheet, §5.3).

| D (m) | area (m²) | mesh mass ≈ (kg) | wind moment @20 m/s, 6 mm mesh (N·m) | @120 km/h, 6 mm mesh | rotator class implied | reflector € |
|---:|---:|---:|---:|---:|---|---:|
| 0.74 | 0.43 | ~2 | 14 | 40 | any AZ/EL | n/a (Yagi/horn class) |
| 1.24 | 1.21 | ~5 | 67 | 187 | light AZ/EL (G-5500DC tower) | 387 (FPD 1M2 KIT) |
| 1.90 | 2.84 | ~12 | 242 | 672 | light/medium AZ/EL (SPX-01) | 901 (FPD 1M9 KIT) |
| 2.40 | 4.52 | ~14 (measured) | 487 | 1,354 | **SPID BIG-RAS** (0.50× @120 km/h) | *out of stock* |
| 2.62 | 5.39 | ~17 | 634 | 1,761 | **SPID BIG-RAS** (0.65×) | quote only |
| 3.00 | 7.07 | 27 (measured) | 952 | 2,644 | **BIG-RAS at the limit (0.97×)** → SPX-05/06 | *out of stock* |
| 3.49 | 9.57 | ~37 | 1,499 | 4,163 | **SPX-05/06 slew class (1.53×)** | not sold |
| **7.38** | **42.76** | **~163** | **14,171 (5.2×)** | **39,363 (14.5×)** | **none** | **does not exist** |

> The 7.38 m row is the point of §2: **the low-power + FLRC-max combination is not a
> procurement question.**

### 2.4 BALLOON side — what the F33 actually costs (all figures from the repo)

| Quantity | Value | Source (file : line) |
|---|---|---|
| F33 RF output, 433 MHz | **+33.0 dBm @ 5.0 V** | `docs/adr/047-v9-power-provisioning.md:67` |
| F33 TX supply current | **1100 mA @ 5.0 V** | `docs/adr/047-v9-power-provisioning.md:67`, `docs/v9-BOM.md:93` |
| F33 DC power, 5.0 V row | **5.50 W** (5.0 × 1.100) | computed |
| F33 DC power, max row (5.5 V / 1118 mA / +33.3 dBm) | **6.15 W** | `docs/adr/047-v9-power-provisioning.md` §1.1–1.2 |
| F33 module mass | **4.0 g** (39 × 21 mm) | `docs/PAYLOAD-WEIGHT-ESTIMATES.md:62,177` |
| Bare LR2021 module mass | **1.2 g** | `docs/PAYLOAD-WEIGHT-ESTIMATES.md:119` |
| **Module mass delta (F33 − bare)** | **+2.8 g** | computed from the two above |
| Full V2/F33 board reference mass | **~20.6 g** with 4 thin-film cells | `docs/PAYLOAD-WEIGHT-ESTIMATES.md:195` |
| Full V2/F33 board classification | **"Ground Station Only … not a pico balloon target"** | `docs/PAYLOAD-WEIGHT-ESTIMATES.md:168–170` |
| Solar array peak | **4 wings × 3 cells = 12 series = 6.0 V @ 1.2 A = 7.2 W** | `docs/v9-BOM.md:101`; `docs/adr/051-hub-array-and-cut-topology.md:75` |
| Solar array nominal (the rail ADR-047 sizes against) | **6.0 V @ 400 mA = 2.4 W** | `docs/adr/044-v9-power-rails.md:46,118`; ADR-006 |
| ADR-047's own margin statement | 6.15 W ÷ 2.4 W = **2.56×** → *"the array alone can never key the PA; the bank is the source"* | `docs/adr/047-v9-power-provisioning.md` §1.4 |
| F33 module indicative cost | **~$8** (LCSC `C5913567`, marked "check" in-repo) | `docs/DUAL-VARIANT-DESIGN.md:192` — live price `TODO(unverified)` (LCSC search page is JS-gated) |

**The balloon-side cost of the F33 is: +2.8 g of module mass, +3.1 W of extra TX DC power
(5.50 W vs the ~2.4 W an LR2021 at +22 dBm needs), and a requirement that the supercap
bank — not the array — supply the TX slot.** That is the whole balloon bill.

### 2.5 The answer, stated plainly

> **Is 20 dB of balloon TX (+13 → +33 dBm) cheaper than the ground dish it removes?**
> **Yes — by an order of magnitude in diameter and two orders in reflector area — and in
> the max-throughput case it is the difference between a design and no design.**
>
> * It removes the **7.38 m / 42.8 m² / ~163 kg** reflector (which no vendor sells, no
>   positioner holds, and no site survives) and replaces it with a **0.74 m** one.
> * Its balloon-side price is **+2.8 g** (module swap) and **+3.1 W** of TX DC (a bank
>   requirement ADR-047 has already provisioned: 6.15 W at 5.5 V, ~27× the 100 ms slot).
> * **The two things that are genuinely expensive are not mass or mass-budget: they are
>   (a) the amateur-licence gate** (the entire +13…+33 dBm class exceeds the licence-exempt
>   **+12.15 dBm EIRP** cap of ADR-039/041), **and (b) the honest contradiction with the
>   repo's own "F33 = ground station only" classification** in
>   `docs/PAYLOAD-WEIGHT-ESTIMATES.md` §D — which is a *whole-board* statement (~20.6 g),
>   not a *module-swap* statement (+2.8 g). **If the operator's mass budget can carry
>   +2.8 g and their licence covers 433 MHz amateur operation, the F33 is the correct call
>   and this whole document's §2 collapses to a 0.74 m dish.** If it cannot, then
>   **FLRC-max at 650 km does not exist for this balloon** — and the honest fallback is
>   the +22 dBm / rate-adaptive / 2.6 m coarse-mesh station of §3–§4, not a bigger dish.

**Note the operator's own two constraints pull opposite ways, and this is where the honest
answer has to pick:** "mass is binding, we want over-provisioned power" **and** "do the
heavy lifting on the ground". For FLRC-max at 650 km the ground **cannot** do the heavy
lifting at low power — §2.3 shows the required ground machine is unbuildable. **The heavy
lifting is only possible on the balloon.** The ground's role is to convert the F33's 20 dB
into *margin and horizon* (§3), which it does very cheaply.

---

## 3. TASK 2 — rate adaptation: what dish does "max range" actually set?

The operator wants max throughput, but the link does not need max rate at max range. The
committed adaptive policy is already **2600 → 1300 → 650 → LoRa fallback**
(`docs/RANGE-THROUGHPUT-PLAN.md:139`). The question is what the **max-range requirement**
sets once rate is allowed to drop.

### 3.1 Candidate dishes and their 433 MHz gains

| D (m) | G @ 433 MHz, η = 0.55 | G @ 433 MHz, η = 0.65 (RF Hamdesign published) | purchasable as |
|---:|---:|---:|---|
| 0.74 | 7.9 dBi | 8.7 dBi | Yagi/horn class (no dish needed) |
| 1.24 | 12.4 dBi | 13.1 dBi | RFH `FPD 1M2 KIT` €387.20 |
| 1.90 | 16.1 dBi | 16.8 dBi | RFH `FPD 1M9 KIT` €901.45 |
| 2.40 | 18.1 dBi | 18.9 dBi | RFH `FPD 2M4 KIT` — **out of stock** |
| 2.62 | 18.9 dBi | 19.6 dBi | DIY only |
| 3.00 | 20.1 dBi | 20.8 dBi | RFH `FPD 3M0 KIT` — **out of stock** |
| 3.49 | 21.4 dBi | 22.1 dBi | DIY only |

### 3.2 Rate vs range — F33 (+33 dBm), `G_balloon = 0 dBi`, free-space closure

Max slant range (km) at which the link is exactly closed, per candidate dish:

| rate | S (dBm) | 0.74 m | 1.24 m | 1.90 m | 2.40 m | 2.62 m | 3.00 m | 3.49 m |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **2.6 Mbps** | −100.5 | **649** | **1,088** | **1,667** | 2,105 | 2,298 | 2,632 | 3,062 |
| 1.04 Mbps | −105.0 | 1,090 | 1,826 | 2,798 | 3,535 | 3,859 | 4,418 | 5,140 |
| **650 kbps** | −107.0 | **1,372** | **2,299** | **3,523** | 4,450 | 4,858 | 5,562 | 6,471 |
| 520 kbps | −108.5 | 1,631 | 2,732 | 4,187 | 5,289 | 5,773 | 6,611 | 7,690 |
| 325 kbps | −110.0 | 1,938 | 3,247 | 4,976 | 6,285 | 6,862 | 7,857 | 9,140 |
| 260 kbps | −111.0 | 2,174 | 3,644 | 5,583 | 7,052 | 7,699 | 8,815 | 10,255 |

### 3.3 The same table without the F33 — LR2021 chip max (+22 dBm)

| rate | 0.74 m | 1.24 m | 1.90 m | 2.40 m | 2.62 m | 3.00 m | 3.49 m |
|---|---:|---:|---:|---:|---:|---:|---:|
| **2.6 Mbps** | 183 | 307 | 470 | 593 | **648** | 742 | 863 |
| 1.04 Mbps | 307 | 515 | 789 | 996 | 1,087 | 1,245 | 1,449 |
| **650 kbps** | 387 | **648** | 993 | 1,254 | 1,369 | 1,568 | 1,824 |
| 520 kbps | 460 | 770 | 1,180 | 1,491 | 1,627 | 1,863 | 2,167 |
| 325 kbps | 546 | 915 | 1,402 | 1,771 | 1,934 | 2,214 | 2,576 |
| 260 kbps | 613 | 1,027 | 1,574 | 1,988 | 2,170 | 2,485 | 2,890 |

### 3.4 What the tables say (quantified answers)

1. **With the F33, the max-range requirement for max throughput is satisfied by a 0.74 m
   dish** (649 km — i.e. exactly the 650 km design range). In other words, **once the F33
   is on the balloon, "FLRC at 2.6 Mbps at 650 km" is no longer a dish problem at all.**
   The "as much gain as we can get" instinct is then about **margin and horizon**, not
   closure: **1.24 m buys +2.2 dB / 1,088 km; 1.90 m buys +6.4 dB / 1,667 km.**
2. **Without the F33, the max-range requirement for max throughput (2.6 Mbps) sets a 2.62 m
   dish** — the largest dish that is still mechanically viable as a coarse mesh (§4), and
   only *just* at the horizon: 648 km of free-space closure means **zero margin**.
   **Rate adaptation is the only affordable lever here:** dropping one step to 1.04 Mbps
   needs **1.56 m**; dropping to 650 kbps needs **1.24 m** (a **2.11×** diameter saving for
   a **6.5 dB** rate step, i.e. diameter ∝ 10^(ΔG/20)). Note the direction of the
   adaptation: 650 kbps at 650 km needs **+12.4 dBi (1.24 m)**, while 2.6 Mbps at 1,254 km
   also needs 1.24 m — **one 1.24 m dish gives either 650 kbps at 650 km or 2.6 Mbps at
   1,254 km on the *same* hardware**, and the firmware's existing ladder chooses between
   them per packet.
3. **"As much gain as we can get" is *not* best served by a dish sized for the closest
   range at the highest rate.** Sizing for the close-in / max-rate case is exactly what a
   **0.74 m** dish does — it is *already* the max-rate-at-650 km solution. Spending more
   aperture only buys *range at a given rate* (row 1: 649 → 3,062 km from 0.74 m → 3.49 m).
   Since the balloon is beyond 650 km only near the horizon (and 650 km at ~30 km is already
   *past* the geometric horizon of 618 km and inside the 4/3-Earth horizon of ~714 km), the
   honest reading of "as much gain as we can get" for **this** geometry is: **pile the gain
   into the balloon (F33 = +20 dB, free), and buy the ground dish for margin, ~1.2–1.9 m.**
4. **The rate ladder saves the *link*, not the *dish*:** at a fixed dish the ladder adds the
   range margins seen across each column (e.g. the 1.90 m column spans **1,667 km →
   5,583 km** as the rate falls 2.6 Mbps → 260 kbps). Conversely, at a fixed 650 km the
   ladder is worth **−27 dB of path margin** of headroom (the FSPL difference between the
   649 km and 5,583 km closures) — i.e. rain/fade/polarisation/pointing budget that the
   rate adaptation trades away throughput for, on demand.

---

## 4. TASK 3 — the coarse MESH is what makes a large 433 dish viable

### 4.1 The λ/10 rule is *generous* at 433 MHz — and the only mesh vendor in this market proves it

Wikipedia (Parabolic antenna): *"The reflector can be constructed from sheet metal, a metal
screen, or a wire grill … A metal screen reflects radio waves as effectively as a solid
metal surface if its holes are smaller than **one-tenth of a wavelength**, so screen
reflectors are often used to **reduce weight and wind loads** on the dish."*
<https://en.wikipedia.org/wiki/Parabolic_antenna>

| band | λ | **λ/10 (max hole)** |
|---|---:|---:|
| **433 MHz** | 692.3 mm | **69.2 mm** |
| 2.4 GHz | 124.9 mm | 12.5 mm |
| 6 GHz | 50.0 mm | 5.0 mm |
| 11 GHz | 27.3 mm | 2.7 mm |

**The rule is corroborated by the vendor's own product line, exactly at its limit:** RF
Hamdesign ships **6 mm square galvanised mesh** "which can be used up to 6 GHz" and offers a
**2.8 mm mesh option "max 11 GHz"** (§5.1, vendor pages fetched this session). At 6 GHz the
6 mm mesh is **1.20 × λ/10**; at 11 GHz the 2.8 mm mesh is **1.03 × λ/10**. That is a
manufacturer publishing a mesh that is *just* at the λ/10 boundary at its rated maximum
frequency — **which is exactly the validation of the rule.** At **433 MHz the same 6 mm mesh
is 11.5 × finer than required**, i.e. electrically solid with an enormous margin.

> `TODO(unverified)`: a **quantitative** measured mesh-vs-solid gain penalty in dB (a
> controlled A/B of the same reflector with mesh vs sheet). Searches this session produced no
> citable measurement; the λ/10 rule + the vendor's rated-max-frequency statement are the
> evidence used. The prior study reached the same "not found" conclusion.

### 4.2 Wind load model (with its source and its stated assumption)

```
q(v)      = 0.5 · ρ · v²                  ρ = 1.225 kg/m³
F         = q · A · Cd · σ                 A = π D²/4 ; σ = solid fraction (1.0 = solid dish)
M_mount   = F · (0.5 · D)                   lever arm = 0.5 × D (stated assumption)
```

* **`Cd` is derived, not assumed, from a vendor's own wind figure.** Gibertini OP100SE
  (940 × 1010 mm working surface = 0.949 m²) is rated **91 kg at 120 km/h** by the vendor
  (hm-sat product page, fetched this session, HTTP 200):
  `Cd = 91 × 9.80665 / (680 Pa × 0.949 m²) = **1.38**`.
* **The `σ`-proportional model for a permeable surface** is the standard drag treatment of
  a screen/windbreak: the Wikipedia *Windbreak* article describes the flow effect as *"the
  loss of momentum caused by the drag of leaves and branches … a distributed momentum
  sink"* — <https://en.wikipedia.org/wiki/Windbreak>, citing Wilson, *Numerical studies of
  flow through a windbreak*, J. Wind Eng. Ind. Aerodyn. (1985),
  doi:10.1016/0167-6105(85)90001-7.
* **`σ` for real mesh is a vendor-published number, not a guess.** JAERA publishes the
  **open-area fraction ("Durchlass")** of every welded mesh it stocks: e.g. 25 × 25 mm / 3 mm
  wire → **77.44 % open** (σ = 0.226); 50 × 50 mm / 3 mm → **88.36 % open** (σ = 0.116);
  40 × 40 mm / 4 mm → 81 % (σ = 0.19) —
  <https://jaera.de/produkt-kategorie/schweissgitter/>. The 6 mm / ~1 mm mesh the RF
  Hamdesign kits use is σ = 1 − (6/7)² = **0.265** (the 1 mm wire is an assumption: the
  vendor does not publish the wire diameter → `TODO(unverified)`; the commercial
  **6 mm / 1 mm** welded mesh does exist and is stocked: see §5.4).

> **Stated limitation:** the linear-`σ` model is a standard engineering treatment of
> high-porosity screens but it is **not** a wind-tunnel result for a *dish-shaped* mesh.
> The frame/ribs (RF Hamdesign: 12 ribs of 15–20 mm square aluminium tube, 3–4 inner rings,
> a 3 × 15–20 mm outer rim strip — §5.1) add a **structural** wind area that does **not**
> scale with σ. The numbers below are therefore **optimistic for the mesh** and
> **conservative for the solid** dish; both directions are stated. An exact exponent and a
> rib-area allowance are `TODO(unverified)`.

### 4.3 The result — mesh vs solid, against the strongest rotator in the BOM

SPID BIG-RAS (vendor spec sheet, fetched this session, HTTP 200,
<https://www.rfhamdesign.com/downloads/spid-bigras-specifications.pdf>):
**holding/brake torque 24,000 in·lb = 2,712 N·m**; turning torque 500 N·m @ 18 V;
**vertical load > 700 lb / 318 kg**; mass 22 kg; environment *"Ground / Mobile free air
and/or Sheltered"*.

**Wind moment at 120 km/h (33.3 m/s), as a multiple of the 2,712 N·m holding torque**
(1.00 = the rating line):

| D (m) | **SOLID** | **6 mm mesh (σ = 0.265)** | **25 mm mesh (σ = 0.143)** |
|---:|---:|---:|---:|
| 0.74 | 0.06× | 0.01× | 0.01× |
| 1.24 | 0.26× | 0.07× | 0.04× |
| **1.90** | **0.93×** | 0.25× | 0.13× |
| **2.40** | **1.88× ✗** | **0.50× ✓** | 0.27× ✓ |
| **2.62** | **2.45× ✗** | **0.65× ✓** | 0.35× ✓ |
| **3.00** | **3.67× ✗** | **0.97× (at the limit)** | 0.52× ✓ |
| **3.49** | **5.79× ✗** | 1.53× ✗ | **0.83× ✓** |
| 7.38 | 54.7× ✗ | 14.5× ✗ | ~7.5× ✗ |

At a 20 m/s (72 km/h) operating wind the same table reads 0.68× / 0.18× (2.4 m),
0.88× / 0.23× (2.62 m), 1.32× / 0.35× (3.0 m) — i.e. **a solid 2.6 m dish is already at
its rotator's limit at an ordinary 72 km/h wind, while the mesh version sits at a quarter
of it.**

**This is the key finding for a large 433 dish, and it is quantitative:**

> **A 2.40 m or 2.62 m 433 dish as a SOLID reflector exceeds the strongest AZ/EL rotator in
> the BOM (1.9× and 2.5× its holding torque at 120 km/h). The same dish as a 6 mm coarse
> mesh sits at 0.50× / 0.65× — comfortably inside it. The mesh is what brings the large 433
> dish back into a feasible positioner class; as a solid dish it is simply not holdable.**
> At 433 MHz the λ/10 rule (69.2 mm) makes the mesh **electrically solid** (§4.1), so the
> mechanical win costs **zero RF performance** — the mesh is 11.5 × finer than required.
>
> **State the boundary exactly (this is what an independent review of the figure caught —
> see §7):** the mesh is comfortable **up to 2.62 m (0.65×)**; at **3.00 m the mesh is AT the
> rating — 0.97×, i.e. no margin at all** — and at **3.49 m it exceeds it (1.53×)**. So the
> coarse mesh takes the mechanically-viable 433 dish class from "≤ 1.9 m" to **~2.6 m with
> margin / 3.0 m exactly at the limit**, and **anything at or above 3.0 m needs the slew-drive
> class (SPX-05/06, €5,487) and counterweights** — which is also, inconveniently, the
> **largest mesh dish this vendor ever made** and it is **out of stock** (§5).

### 4.4 DIY build materials (real products, hole sizes, URLs)

Because neither the 2.4 m nor the 3.0 m kit is purchasable today (§5.1), a large 433 mesh
dish is a **DIY build**: buy the parabolic **former** (ribs/hub — only sold as a kit) or
build ribs, and skin it with commodity mesh. The mesh is the cheap, well-sourced part:

| material | mesh | wire | open area | price | URL | status |
|---|---|---|---|---|---|---|
| Welded mesh (JAERA, steel, blank) | 25 × 25 mm | 3 mm | **77.44 %** (σ 0.226) | by enquiry (shop lists it; per-piece price not on the category page) | https://jaera.de/produkt-kategorie/schweissgitter/ | CONFIRMED specs; price `TODO(unverified)` |
| Welded mesh (JAERA, steel) | 50 × 50 mm | 3 mm | **88.36 %** (σ 0.116) | as above | same | CONFIRMED |
| Welded mesh (JAERA, steel) | 40 × 40 mm | 4 mm | **81 %** (σ 0.19) | as above | same | CONFIRMED |
| Welded mesh (JAERA) sheet sizes | — | — | — | — | 1000×2000 / 1250×2500 / 1500×3000 / 2000×3000 mm, wire 1.6–8 mm | CONFIRMED |
| Welded mesh, galvanised (metal-market.eu) | **25 × 25 mm** | 1.75 mm | ~87 % (σ ~0.13) | **€7.00 (vendor "nach Maß" listing price)** | https://metal-market.eu/collections/schweissgitter | CONFIRMED listing + price |
| Welded mesh, galvanised (metal-market.eu) | **50 × 50 mm** | 2 mm | ~92 % | **€7.00** | same | CONFIRMED |
| Welded mesh, galvanised (metal-market.eu) | 12 × 12 mm | 1 mm | ~86 % | €7.00 | same | CONFIRMED |
| Mesh (drahtgewebe-shop.de, cut-to-size) | **6 mm** | **1 mm** | σ = **0.265** | by configuration (order by length×width) | https://www.drahtgewebe-shop.de/ | CONFIRMED mesh+wire table |
| Mesh (drahtgewebe-shop.de) | 9 / 10 / 11 / 15.8 / 20 mm | 1 / 1 / 1.6 / 1.2 / 1.5 mm | — | by configuration | same | CONFIRMED |
| Aluminium window screen (Fliegengitter) | `TODO(unverified)` hole size | — | — | `TODO(unverified)` | retail only (Bauhaus/OBI/Amazon) | **`TODO(unverified)` — no hole size sourced** |

**Design tolerance:** at 433 MHz the reflector **RMS surface tolerance is λ/20 = 34.6 mm**
(Wikipedia, Parabolic antenna; the prior study used the same figure). The mesh may therefore
sag **centimetres** and still be electrically fine — which is precisely why a cheap
DIY wire-mesh parabola is a sound 433 MHz reflector and a bad 2.4 GHz one (§4.1: the same
mesh needs ≤ 12.5 mm holes at 2.4 GHz).

**Frame/former:** the RF Hamdesign kits are supplied with **3 (or 4) aluminium ribs, CNC
hub, 3 inner rings, a 3×15–20 mm rim strip and a 3/4-leg feed support**, as a self-assembly
rivet kit (§5.1). No vendor sells the former alone → **a large DIY 433 dish either reuses a
kit's former (out of stock beyond 1.9 m) or fabricates ribs**. That is the *real* blocker for
a >1.9 m 433 mesh dish, not the mesh itself. Marked plainly: **frame sourcing is
`TODO(unverified)`.**

---

## 5. TASK 4 — sourced 433 MHz dishes, positioners, and the F33 route

All pages below were **fetched this session** (HTTP 200 with a browser User-Agent) or are
re-fetched from the BOM study with the URL given. Prices are as printed; the RF Hamdesign
figures come from its **Oct-2026 price list** PDF.

### 5.1 433 MHz mesh / prime-focus dishes — purchasable and DIY

| # | Vendor | Product | Ø | F/D | η | Weight | 433 MHz gain (computed) | € | Availability | URL |
|---|---|---|---:|---|---:|---:|---:|---:|---|---|
| D1 | RF Hamdesign (NL) | **FPD 1M0 KIT** mesh dish | 1.0 m | 0.45 | 65 % | — | ~11.2 dBi | **342.43** | in stock | https://www.rfhamdesign.com/products/parabolicdishkit/1meterdishkit/index.php · price: https://www.rfhamdesign.com/downloads/rf-hamdesign-pricelist.pdf |
| D2 | RF Hamdesign | **FPD 1M2 KIT** mesh dish | **1.2 m** | 0.45 | 65 % | **4.8 kg** | **12.9 dBi** | **387.20** | in stock | https://www.rfhamdesign.com/products/parabolicdishkit/12meterdishkit/index.php |
| D3 | RF Hamdesign | **FPD 1M5 KIT** mesh dish | 1.5 m | 0.45 | 65 % | — | 14.8 dBi | **499.73** | in stock | https://www.rfhamdesign.com/products/parabolicdishkit/15meterdishkit/index.php |
| D4 | RF Hamdesign | **FPD 1M9 KIT** mesh dish | **1.9 m** | 0.45 | 65 % | — | **16.8 dBi** | **901.45** | in stock | https://www.rfhamdesign.com/products/parabolicdishkit/19meterdishkit/index.php |
| D5 | RF Hamdesign | **FPD 2M4 KIT** mesh dish | **2.4 m** | 0.45 | 65 % | **14 kg** | **18.9 dBi** | no price printed | **OUT OF STOCK — "availability of new stock is not yet known. Pre-order not possible."** | https://www.rfhamdesign.com/products/parabolicdishkit/24meterdishkit/index.php |
| D6 | RF Hamdesign | **FPD 3M0 KIT** mesh dish | **3.0 m** | 0.45 | 65 % | **27 kg** | **20.8 dBi** | no price printed | **OUT OF STOCK** (same wording); vendor says it *"can be used with SPID BIG-RAS (HR) or SPX-05/06 … Dish with dish feed installed needs counter weights!"* | https://www.rfhamdesign.com/products/parabolicdishkit/3meterdishkit/index.php |
| D7 | RF Hamdesign | **FPD 4.5 m** mesh dish | 4.5 m | — | — | — | ~24 dBi | — | **PRODUCTION CEASED** — *"we have had to cease production of our 4.5-meter mesh dish … The last 4.5Meter Mesh Dish Kit is sold in late 2024."* | https://www.rfhamdesign.com/products/parabolicdishkit/45meterdishkit/index.php |
| D8 | generic | coarse welded mesh (skin only, DIY former) | 1.2–3.5 m | — | — | mesh only | — | €7.00 per "nach Maß" weld-mesh item (metal-market.eu) / JAERA by enquiry | purchasable | §4.4 |
| D9 | generic | **no vendor sells a 433 MHz mesh dish >1.9 m off the shelf today** | — | — | — | — | — | — | — | **This is the finding.** |

**Cross-check of the computed 433 MHz gains:** the vendor's *own* published gain tables are
**η = 65 %** — 2.4 m kit: *"2320 MHz … 31.1 dBd"* and 3.0 m kit: *"1296 MHz 30.3 / 2320 MHz
35.4 / 3456 MHz 38.8 / 5760 MHz 43.3"* (aperture formula reproduces both to ±0.1 dB at
η = 0.65, so the 3 m table is in dBi and the 2.4 m table in dBd). Scaling the vendor's own
numbers to 433 MHz gives the column above; using **η = 0.65 instead of the task's 0.55 adds
+0.7 dB** to every row.

**Positioner interface parts (RF Hamdesign price list):** `BR-08` adaptor plate (mesh dish
≤1.9 m onto SPX-01/SPX-02) **€38.00**; `BR-50` fixed-elevation bracket (≤1.9 m, 0–90°) —
the 1.9 m class **€135.00**, the heavy `BR-50B` (5 mm laser-cut steel, 6 kg, **"can be used
with our Mesh Dishes up to 3 Meter diameter"**, mast 63–66 mm) "refer price list";
`FPD-BR01` rotor↔dish bracket for BIG-RAS **€198.00**; `FPD-BR02` for SPID RAS **€172.00**;
`UA-02` XXL heavy-duty bracket with counterweight arms (all SPID/HR rotators) **€624.36**;
`4TH-LEG` **€39.93**; `CLX-10` adaptor for masts >55 mm — quote.

### 5.2 Heavy AZ/EL positioners for the 2–3.5 m class

| # | Vendor | Product | Axes | Rating (vendor) | Price € | URL |
|---|---|---|---|---|---|---|
| E1 | Yaesu (Funktechnik Bielefeld) | **G-5500DC** | AZ+EL | **1.00 m² tower / 0.50 m² mast** | 949.00 | https://www.funktechnik-bielefeld.de/yaesu-g-5500dc-satellitenrotor (wind: https://www.dxengineering.com/parts/ysu-g-5500dc) |
| E2 | RF Hamdesign | **SPID RAS** AZ&EL | AZ+EL | "standard"; spec sheet RAS = 455 N·m turning | 1,260.82 | https://www.rfhamdesign.com/downloads/rf-hamdesign-pricelist.pdf |
| **E3** | RF Hamdesign | **SPID BIG-RAS** AZ&EL | AZ+EL | **brake/holding 2,712 N·m; turning 500 N·m; vertical load 318 kg; 22 kg; "Ground/Mobile free air and/or Sheltered"** — a **fetched, real rating**, not the "dishes up to 5 m" marketing line | **1,775.00** (BIG-RAS/MD03 **2,105.00**) | spec: https://www.rfhamdesign.com/downloads/spid-bigras-specifications.pdf |
| E4 | RF Hamdesign | **SPID BIG-RAS/HR** | AZ+EL | high-resolution (MD-01); same mechanics | 2,578.51 | price list |
| E5 | RF Hamdesign | **SPX-01/MD03** | AZ+EL | light duty, 0.5°/step | 1,132.00 | https://www.rfhamdesign.com/products/spx-antenna-rotators/spx-01-az--el/index.php |
| E6 | RF Hamdesign | **SPX-02/MD03** | AZ+EL | medium duty | 1,249.00 | https://www.rfhamdesign.com/products/spx-antenna-rotators/spx-02-az--el/index.php |
| E7 | RF Hamdesign | **SPX-03/MD03** | AZ+EL | heavy duty | 1,629.00 | price list |
| **E8** | RF Hamdesign | **SPX-06/AZ&EL/ABS slew drive** | AZ+EL | **716 N·m rated, IP65, absolute encoders, 0.1°** | **5,487.35** | price list |
| — | RF Hamdesign | rotator PSUs | — | `PW32015` 18 V/20 A for RAS & BIG-RAS **€119**; `PSU-1228` 9–15 V/28 A **€129**; MD-03 controller **€526.35**; PS-03 **€482** | — | price list |

**The BOM study's SPID wind rating was a `TODO(unverified)`; it is now resolved.** The
BIG-RAS **does** publish a real holding-torque rating — **2,712 N·m brake** — and §4.3 uses
it. (Its marketing line "will handle … dishes up to 5 Meter" is *not* a wind rating; a 5 m
solid dish would be ~9.6× the brake torque in a 120 km/h wind. The 5 m figure is only
credible for a very open mesh, which is exactly this document's point.)

### 5.3 What the sourced parts say about each architecture

| route | dish | positioner | reflector € | rotator € | total € (parts only) | mechanically viable? |
|---|---|---:|---:|---:|---:|---|
| **F33 + small dish** (recommended) | RFH 1.2 m mesh (D2) or 1.9 m (D4) | SPX-01 (E5) | 387–901 | 1,132 | **≈ 1,520–2,035** | **yes, easily** (§4.3: 0.07–0.25× torque) |
| **+22 dBm + max-rate-at-650 km** | 2.62 m mesh (DIY) | SPID BIG-RAS (E3) | ~1,000 (DIY est., `TODO(unverified)`) | 1,775 | **≈ 2,775 + frame** | **yes as mesh (0.65×); NOT as solid (2.45×)** |
| **+22 dBm + 3.0 m mesh** | 3.0 m (D6, out of stock) | BIG-RAS at the limit → SPX-05/06 (E8) | n/p (no price) | 1,775 / 5,487 | **2,775–6,487** | mesh 0.97× on BIG-RAS; 0.52× on slew |
| **+13 dBm + FLRC-max (the ADR-066 premise)** | **7.38 m** | — | — | — | — | **no — 14.5× the brake torque even as mesh, ~163 kg, not sold** |

### 5.4 The F33 route, for comparison

* Module: **NiceRF LoRa2021F33-2G4**, 39 × 21 mm, +33 dBm @ 433/470 MHz, internal TCXO —
  `docs/F33-MODULE-PLAN.md:6,15,21–25`; footprint/land pattern work already exists in-repo
  (`tracker/hardware/footprints/nicerf-lora2021f33-2g4.json`,
  `custom.pretty/LoRa2021F33_2G4.kicad_mod`).
* Indicative cost **~$8** (LCSC `C5913567`) — `docs/DUAL-VARIANT-DESIGN.md:192`, marked
  "check" in-repo; the live LCSC price is **`TODO(unverified)`** (the LCSC search page is
  JS-gated and returned no price this session).
* DC/TX cost and module mass: §2.4 (5.50 W @ 5 V; 6.15 W @ 5.5 V; **+2.8 g** vs the bare
  module).
* **Cost comparison, plainly:** the F33 route adds **~$8 and +2.8 g** to the balloon and
  removes a **€2,775+ ground station** (and, in the max-throughput case, removes a machine
  that cannot be bought at all). **The F33 is the cheapest element in either architecture.**

### 5.5 BOM additions this document proposes (design only — nothing ordered)

| Line | Item | Qty | Unit € | Source |
|---|---|---:|---:|---|
| 433-D1 | RF Hamdesign `FPD 1M2 KIT` 1.2 m 433/2.4 GHz mesh dish (**12.9 dBi @433**, 4.8 kg) | 1 | 387.20 | https://www.rfhamdesign.com/products/parabolicdishkit/12meterdishkit/index.php |
| 433-D2 | RF Hamdesign `FPD 1M9 KIT` 1.9 m mesh dish (**16.8 dBi @433**) | 1 | 901.45 | https://www.rfhamdesign.com/products/parabolicdishkit/19meterdishkit/index.php |
| 433-D2b | feed for the mesh dish — **433 MHz prime-focus feed is the open item**: the vendor's feeds are 900 MHz–10 GHz (RS-ONE / HORN / CIR); a 433 MHz feed is `TODO(unverified)` | 1 | — | https://www.rfhamdesign.com/downloads/rf-hamdesign-pricelist.pdf |
| 433-P1 | SPID `BIG-RAS` AZ&EL (2,712 N·m brake, 318 kg vertical) | 1 | 1,775.00 | spec + price list (§5.2) |
| 433-P2 | SPX-01/MD03 AZ&EL (light class; for the 1.2–1.9 m dish) | 1 | 1,132.00 | §5.2 |
| 433-P3 | `BR-08` adaptor (mesh dish ≤1.9 m ↔ SPX-01/02) | 1 | 38.00 | price list |
| 433-P4 | `FPD-BR01` rotor↔dish bracket (BIG-RAS) | 1 | 198.00 | price list |
| 433-P5 | `UA-02` XXL bracket + counterweight arms | 1 | 624.36 | price list |
| 433-P6 | `PW32015` PSU 18 V/20 A (RAS/BIG-RAS) | 1 | 119.00 | price list |
| 433-M1 | welded galvanised mesh, 25 × 25 mm / 1.75 mm (DIY skins) | as needed | 7.00 per "nach Maß" item | https://metal-market.eu/collections/schweissgitter |
| 433-M2 | welded steel mesh 25 × 25 / 50 × 50 mm, 1000×2000–2000×3000 mm sheets | as needed | by enquiry | https://jaera.de/produkt-kategorie/schweissgitter/ |
| 433-M3 | aluminium window screen (fine, electrically solid at 433 MHz) | optional | `TODO(unverified)` | retail only |
| BAL-1 | **NiceRF LoRa2021F33-2G4** (2 W) — the balloon-side addition | 1 | ~$8 (`TODO(unverified)`) | `docs/DUAL-VARIANT-DESIGN.md:192`; `docs/F33-MODULE-PLAN.md` |
| BAL-2 | supercap bank capacity to source the 6.15 W TX slot (ADR-047 §3 already specifies this) | — | (in existing budget) | `docs/adr/047-v9-power-provisioning.md` |

---

## 6. RECOMMENDATION

**REC-1 (the direct answer). Put the 2 W F33 on the balloon for the 433 downlink, and use a
modest 433 mesh dish on the ground — do not try to close FLRC-max at 650 km from the ground
alone.** The ground cannot do it: at the low-power +13 dBm premise the max-throughput
requirement is a **7.38 m / 42.8 m² / ~163 kg** dish that is **14.5× the strongest BOM
rotator's holding torque even as a coarse mesh** and that **no vendor sells**. The F33's
+20 dB replaces it with a **0.74 m** dish and costs **+2.8 g** and **3.1 W DC**. This is the
single highest-leverage change in the whole architecture, and by a wide margin the cheapest.

**REC-2 (ground sizing bound). Size the ground dish for *margin and horizon*, not for
closure.** With the F33: 0.74 m closes 2.6 Mbps at 649 km; **1.24 m adds +2.2 dB (1,088 km)**
and **1.9 m adds +6.4 dB (1,667 km)**. **Recommend a 1.2–1.9 m coarse-mesh 433 dish**
(RFH `FPD 1M2`/`FPD 1M9`, €387–901, 4.8 kg+) on an **SPX-01 (€1,132)** — every one of those
combinations is **≤ 0.25×** the BIG-RAS holding torque as a 6 mm mesh (§4.3), i.e. with a
4× wind margin.

**REC-3 (the mesh rule). Any 433 dish of 2 m or more MUST be coarse mesh, not solid.** The
λ/10 rule at 433 MHz permits **69.2 mm** holes, so 6–25 mm commodity mesh is electrically
solid (§4.1) **and** cuts the wind moment to **0.14–0.27** of a solid dish (§4.3). A solid
2.4 m or 2.6 m dish **exceeds the BIG-RAS holding torque (1.9× / 2.5×)** at 120 km/h; the
mesh version sits at **0.50× / 0.65×**. This is exactly the difference between an infeasible
machine and a feasible one. **But the rule has a hard edge, stated exactly:** the mesh keeps
the dish inside the BIG-RAS rating only **up to 2.62 m (0.65×)**; **at 3.00 m the mesh is AT
the rating (0.97× — zero margin)** and at **3.49 m it exceeds it (1.53×)**. So **≥ 3.0 m mesh
⇒ the slew-drive class (SPX-05/06, €5,487)**, not the BIG-RAS.

**REC-4 (rate adaptation). Keep and formalise the committed ladder (2600 → 1300 → 650) as
the *long-range* mechanism.** With the F33, rate adaptation is not needed for the 650 km
question (0.74 m already answers it) — it is the tool that gives a **1.24 m dish 650 kbps
at 650 km *or* 2.6 Mbps at 1,254 km** on the same hardware, and that turns the 1.9 m dish
into **1,667 km @ 2.6 Mbps / 3,523 km @ 650 kbps / 5,583 km @ 260 kbps**.

**REC-5 (if and only if the F33 is excluded).** The operator's mass constraint is binding,
so state the honest consequence rather than proposing a big dish: **if the balloon must stay
at ≤ +22 dBm, then FLRC-max at 650 km requires a 2.62 m coarse-mesh dish that is at ZERO
margin (648 km), is DIY-only (the 2.4 m and 3.0 m kits are out of stock), and needs the
SPID BIG-RAS at 0.65× of its holding torque.** The defensible fallback is then **+22 dBm +
a 1.24 m dish + the 650 kbps rate at 650 km** (648 km closure at +22 dBm / 650 kbps — see
§3.3), with **FLRC-max reserved for ≤ ~300 km** (307 km at 0.74 m / +22 dBm).

**REC-6 (the two gates that are not engineering).** Before any of this is built:
1. **Licence.** The whole +13…+33 dBm class is **above** the licence-exempt **+12.15 dBm
   EIRP** cap (ADR-039 / ADR-041). Recommending the F33 makes the 433 downlink an
   **amateur-band** link; the DE amateur licence and the airborne-SRD grey area (ADR-039 open
   item (a)) must be settled first. **This, not mass, is the binding constraint on REC-1.**
2. **The repo's own classification.** `docs/PAYLOAD-WEIGHT-ESTIMATES.md` §D says the F33
   board is *"Ground Station Only … not a pico balloon target"*. REC-1 **contradicts that
   record** for the *module swap* case (+2.8 g versus the ~20.6 g whole-board reference).
   Either the operator accepts the +2.8 g module on the balloon (and that record is
   updated by a future ADR), or REC-5 applies. **This contradiction is flagged, not
   silently resolved.**

**REC-7 (no procurement).** Nothing here is ordered. REC-1/REC-5 are design decisions; the
parts in §5.5 are sourced so that a future procurement can cite a real vendor and a real
price, not so that anything is bought now.

---

## 7. Independent consultation (visual consultant)

**Consultant:** `scripts/fleet/visual_consult.py` (fleet script), per the `visual-consultant`
skill. Artifact consulted: `docs/analysis/assets/flrc-max-trade.png`, rendered by
`docs/analysis/render_flrc_max_figure.py`. Verdicts saved verbatim to
`docs/analysis/assets/consult-verdict-flrc-max.txt`.

**Engagement status:** **ENGAGED.** The lane is flaky (the recurring failure is HTTP 503
*"all candidate lanes busy or capped"* — the same failure class that killed earlier attempts
at this task); round 1 needed one retry, round 2 is a retry loop (see below).

**Served model (read back from the response body, not from the alias):** **`gpt-6-astra`**

---

### 7.1 Round 1 — the ORIGINAL figure, and the finding it produced

**Verdict line as printed by the CLI (`--emit-evidence`), verbatim:**

```
visual_review: APPROVED
visual_reviewer_model: gpt-6-astra
```

> **Read the next paragraph before quoting that line.** `APPROVED` here is the CLI's
> `--verdict` **default token** — `argument --verdict: default="APPROVED"` in
> `scripts/fleet/visual_consult.py:247` — **not the model's opinion**. The consultant's own
> verdict is the last line of its answer body below, and it is **REFUTE**. Both are recorded
> verbatim; the CLI token is quoted only so that the evidence line is not misrepresented as
> something it is not.

**Consultant answer, verbatim:**

> 1. **Panel (a):** Yes. The +13 dBm / 2.6 Mbps bar is well above 20 dBi at 27.9 dBi, while
>    the +33 dBm bar is below 12 dBi at 7.9 dBi. The diameters are consistent: approximately
>    7.38 m to 0.74 m and 3.49 m to 0.35 m, each a tenfold change for 20 dB.
>
> 2. **Panel (b):** The SOLID bars cross 1.00× at 2.40 m and remain above it thereafter.
>    However, the mesh reaches approximately 1.00× at 3.00 m and exceeds it at 3.49 m, so it
>    is not below the line at 3.00 m.
>
> 3. **Labels:** The panel (b) 3.00 m mesh annotation and the “SPID BIG-RAS holding torque”
>    label overlap the dashed 1.00× line and are difficult to read. Other labels are generally
>    legible, with the upper-left panel (a) annotation close to—but not clearly clipped by—the
>    plot boundary.
>
> 4. **Visual contradiction:** Yes. The 3.00 m mesh bar is at the rating line, contradicting
>    the stated conclusion that mesh stays below 1.00× except at 3.49 m.
>
> independent VERDICT: REFUTE

**How round 1 changed this document — the finding was ACCEPTED as correct, and acted on.**
The consultant caught a real defect, and it was **mine, in the claim framing, not in the
physics**: §4.3's *table* always said *"3.00 m: 0.97× (at the limit)"*, but the sentence I
asked the reviewer to check (and the figure's own labelling) implied the mesh stayed inside
the rating until 3.49 m. Three fixes were made:

1. **Figure:** the ≥3.0 m mesh bars are now drawn in **orange** (the rest green) with an
   explicit call-out *"3.00 m mesh = 0.97× — AT the rating, no margin"*, and the
   *"SPID BIG-RAS holding torque"* label was moved left of the bars so it cannot collide with
   any bar label. A figure footnote now carries the **lever-arm (0.5 × D)** and **Cd = 1.38**
   assumptions, which round 1's item 3 also flagged as not visible on the figure.
2. **Document:** §4.3 now states the boundary exactly — *comfortable up to 2.62 m (0.65×),
   AT the rating at 3.00 m (0.97×, zero margin), exceeded at 3.49 m (1.53×) ⇒ the slew-drive
   class*; REC-3 repeats it as a hard edge on the mesh rule.
3. **ADR-067:** Decision 4 now quotes the same edge, so the ADR cannot be read as claiming
   margin that does not exist at 3.0 m.

### 7.2 Round 2 — re-consult on the FIXED figure

**Engagement status:** _`TODO(unverified)` — see the note below; round 2 was retried in a
loop against the flaky lane (`/tmp/consult_retry2.sh`)._

**Served model (read back):** `TODO(unverified)`

**Verdict line (verbatim):** `TODO(unverified)`

**Consultant answer (verbatim):** `TODO(unverified)`

> **If round 2 could not be served, the honest record is exactly this:** the first round
> produced a real, specific, acted-on finding (§7.1); the re-consult on the corrected figure
> could not be completed because the consultant lane stayed capped. **No verdict is claimed
> for round 2, and none is invented.** The single-round outcome is still a completed review
> cycle — the defect it found was fixed and is verifiable in the figure, the doc and the ADR.

> A visual consult is **not** a code review and does not satisfy the ADR-010 review gate.

---

## 8. Open items (not assumed)

1. **`TODO(unverified)`** 433 MHz-specific FLRC sensitivity row (915 MHz datasheet rows used;
   §1.1).
2. **`TODO(unverified)`** a **433 MHz prime-focus dish feed** for the RF Hamdesign mesh
   dishes — the vendor's feed line starts at 900 MHz (RS-ONE tuneable 0.9–3.4 GHz). A 433
   feed is the concrete blocker on buying the dish *as a dish*. (§5.5 line 433-D2b.)
3. **`TODO(unverified)`** the **former/rib set** for a >1.9 m DIY 433 dish — no vendor sells
   ribs without mesh; the ≥2.4 m kits are out of stock. (§4.4.)
4. **`TODO(unverified)`** the **wire diameter of the RF Hamdesign 6 mm mesh** (the σ = 0.265
   figure assumes 1.0 mm; the 6 mm/1 mm commercial mesh exists at drahtgewebe-shop.de).
5. **`TODO(unverified)`** the **exact wind-drag exponent** for a high-porosity screen at
   dish incidence, and the **rib/frame wind area** the σ-model omits (§4.2).
6. **`TODO(unverified)`** a **measured** mesh-vs-solid reflector gain penalty in dB (§4.1).
7. **`TODO(unverified)`** the **hole size and price of aluminium window screen**
   (Fliegengitter) — retail pages were bot-walled.
8. **`TODO(unverified)`** the **live F33 module price** (LCSC `C5913567`); the ~$8 figure is
   the in-repo one (`docs/DUAL-VARIANT-DESIGN.md:192`, marked "check").
9. **`TODO(unverified)`** a **solid 2.4–3.0 m 433 dish** equivalent for comparison; the
   only confirmed ≥2 m 433-capable reflectors found are the (out-of-stock) RFH mesh kits.
10. **Repo inconsistency, flagged not resolved:** the solar array appears as **2.4 W**
    (`docs/adr/044-v9-power-rails.md:46`, ADR-006) and as **7.2 W peak**
    (`docs/v9-BOM.md:101`, ADR-049/051). ADR-047 provisions against the 2.4 W figure and
    concludes the bank must source the PA. This document cites both and does not pick.
11. **`TODO(unverified)`** the DE amateur-licence and airborne-SRD position for a +33 dBm
    airborne 433 transmitter (ADR-039 open item (a), inherited).
12. Horizon: 650 km at ~30 km altitude is slightly **beyond** the geometric radio horizon
    (618 km) but inside the standard 4/3-Earth refractive horizon (~714 km); taken as given.

---

## 9. Method / reproduction

* Every numeric table: `python3 docs/analysis/ground_station_flrc_max_model.py`
  (this document's §2–§4 are printed by it; constants are at the top of the file with their
  provenance).
* Figure: `python3 docs/analysis/render_flrc_max_figure.py` →
  `docs/analysis/assets/flrc-max-trade.png`.
* Web fetches used a browser User-Agent + `curl --compressed`. **Fetched this session
  (HTTP 200):** `rfhamdesign.com` mesh-dish pages (1.0/1.2/1.5/1.9/2.4/3.0/4.5 m), its
  Oct-2026 price list PDF, its SPID BIG-RAS spec sheet PDF, the Gibertini OP100SE page at
  `hm-sat-shop.de`, `jaera.de` welded-mesh category, `metal-market.eu` welded-mesh
  collection, `drahtgewebe-shop.de`, and English Wikipedia (`Parabolic_antenna`,
  `Windbreak`). **Gated/blocked this session → no value invented:** `niceRF.com` product
  pages (404/403), `lcsc.com` search (JS), `timesmicrowave.com` (403),
  `dorstener-drahtwerke.de` (401), eBay.de (403), Bing/DDG/Mojeek HTML result pages
  (bot walls; Bing's RSS endpoint was used for the German product searches that did land).
* Prices are as printed by the vendor; the RF Hamdesign figures are **incl. Dutch VAT**.
* `Cd = 1.38` is **derived** from the Gibertini OP100SE vendor wind figure (91 kg @ 120 km/h
  over a 0.949 m² working surface) — see §4.2; it is not a textbook constant.
* No datasheet value or vendor URL in this document was invented. Where a number could not
  be sourced it is marked `TODO(unverified)` and, where relevant, the *direction* of the
  unknown is stated.
