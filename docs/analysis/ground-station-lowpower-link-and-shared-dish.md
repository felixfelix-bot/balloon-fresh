# Ground-station link analysis — LOW-POWER LR2021 433 MHz downlink + the shared-dish architecture

**Status:** Analysis — `docs/analysis/`, not yet an ADR.
**Date:** 2026-10-08
**Scope:** RF/link design only. Design only — nothing is ordered here.
**Repro command:** `python3 docs/analysis/ground_station_lowpower_link_model.py`
(prints every numeric table in this document).
**Supersedes/relates:** `docs/LINK-BUDGET-LICENCE-EXEMPT.md` (300 km, 10 mW ERP design
point), ADR-039 (licence-exempt 433 design point), ADR-041 (RF front end),
`docs/analysis/dualband-single-dish.md` (branch `design/dualband-single-dish`).
**Operator decision driving this:** the 433 downlink uses the **LOW-POWER LR2021**,
not the F33 (2 W / 33 dBm). The operator wants the ground station to carry the gain.

Every sensitivity and power figure below is either a **datasheet value** (table + local
citable PDF + origin URL) or a **computed** value with its formula. Anything not yet
sourced is marked `TODO(unverified)`.

> **Sourcing note.** The LR2021 figures are read from the **Semtech LR2021/LR2022/LR2012
> Final Datasheet**, local citable copy
> `docs/lr2021-research/semtech-official/LR2021_LR2022_LR2012_Datasheet_v2.2.pdf`
> (Rev 2.2, 250 pp, PDF created 2026-07-29, md5 `18a392b72ff448083e6f26b2dd6e3925`).
> Its origin is the Semtech LR2021 product page
> <https://www.semtech.com/products/wireless-rf/lora-plus/lr2021> (the datasheet download
> link itself is session-scoped/Salesforce-hosted; the product page is the citable origin,
> per `docs/lr2021-research/SOURCES.md` §A2). The Rev 2.1 copy
> (`docs/LR2021_LR2022_LR2012_Datasheet_Rev2.1.pdf`) carries **identical** numbers for
> every value used here (verified this session by extracting both PDFs).

---

## 0. Verdict first

**CONFIRMS** the architecture *"Ku dish for the 2.4 GHz uplink + a 433 MHz antenna
boresighted on the same positioner"* — **but only for the LoRa downlink**, which is the
actual long-range mode.

* **LoRa requires no ground gain at all** at 650 km: the required ground gain is
  **negative** (−12 to −28 dBi). Even a 0 dBi omni closes with **12–28 dB** margin. A
  12–15 dBi Yagi (the licence-exempt budget's assumption) is *enormous* overkill → +24 to
  +40 dB margin. **A dedicated steerable 433 dish is not needed for LoRa.**
* **FLRC is the exception, and it is the whole answer.** FLRC's sensitivity is **~36 dB
  worse** than LoRa at 433 MHz (datasheet: −107 dBm @ 650 kbps vs −143 dBm @ SF12/62.5 kHz).
  FLRC at 650 km demands **+9 to +28 dBi** of ground gain depending on rate and power.

**THE ONE CASE WHERE THE ARCHITECTURE CHANGES:** if the 650 km downlink must carry
**FLRC** (any rate) at **low power (≤ +19 dBm)** — or any rate ≥ 1 Mbps even at +22 dBm —
then the 433 antenna needs **≈ +19 to +28 dBi**, which **no practical Yagi delivers**. It
would have to be a **433 MHz dish of ~2.7–3.0 m** diameter, which is a different machine
from "a small boresighted 433 antenna on the Ku positioner". So:

* **LoRa downlink → CONFIRMED.** Ku dish (2.4 GHz) + boresighted 433 Yagi, one positioner.
* **FLRC downlink at 650 km / low power → REFUTED.** The 433 side must become a dish.

> **Consultant qualification (do not over-read "~20 dBi dish").** See §9: the independent
> visual consultant (OpenAI `gpt-6-astra`) confirmed the split but correctly flagged that a
> **nominal 20 dBi dish is NOT sufficient for every FLRC case** — the worst row
> (FLRC 2.6 Mbps @ +13 dBm) requires **+27.9 dBi**, which even a 3.0 m dish (20.5 dBi) does
> not provide. So the honest statement is *"FLRC at long range needs a **class** of antenna
> from a large dish to something larger still; a 20 dBi dish only covers the middle of the
> FLRC range."* That strengthens, not weakens, the conclusion: FLRC is a close-range mode.

FLRC is a **short-range, high-rate** mode in this project's own budget
(`docs/link-budget.md`: "FLRC @ 1.3 Mbps … → Distanz ~25–30 km … perfekt fuer direkten
Ueberflug"). If that stays true, the refutation never binds and the architecture stands.

---

## 1. Datasheet inputs (every number in the source table)

### 1a. Receiver sensitivity — Semtech LR2021

**Sub-GHz LoRa**, 64-byte payload, 1% PER — datasheet **Table 3-17**
("LoRa Sub-GHz 64B Payload (LR20xx)"), CR 4/5, `rx_boost=7`:

| Symbol | Condition | Typ | dBm |
|---|---|---:|---:|
| `LORA_SUB_125_SF12` | BW 125 kHz, SF 12 | −141.5 | dBm |
| **`LORA_SUB_62_SF12`** | **BW 62 kHz, SF 12** | **−143** | **dBm** |
| `LORA_SUB_31_SF12` | BW 31 kHz, SF 12 | −147 | dBm |
| `LORA_SUB_250_SF12` | BW 250 kHz, SF 12 | −138.5 | dBm |
| `LORA_SUB_1000_SF12` | BW 1000 kHz, SF 12 | −131 | dBm |

**Sub-GHz FLRC**, 1% PER @ 915 MHz — datasheet **Table 3-12**
("FLRC Sub-GHz 1% PER (LR2021)"), `G13 rx_boost=7`:

| Symbol | Rate (BRF / effective) | Typ | dBm |
|---|---|---:|---:|
| `FLRC_2600_CR05_915_S` | 2600 kbps / 1.95 Mbps | −100.5 | dBm |
| `FLRC_1040_CR05_915_S` | 1040 kbps / 780 kbps | −105 | dBm |
| **`FLRC_650_CR05_915_S`** | **650 kbps / 487 kbps** | **−107** | **dBm** |
| `FLRC_520_CR05_915_S` | 520 kbps / 390 kbps | −108.5 | dBm |
| `FLRC_325_CR05_915_S` | 325 kbps / 243 kbps | −110 | dBm |
| `FLRC_260_CR05_915_S` | 260 kbps / 195 kbps | −111 | dBm |

> These FLRC values are taken at **915 MHz** (the datasheet's sub-GHz FLRC test point);
> the 433 MHz figures are not separately tabulated and are expected to be the same class
> (sub-GHz FLRC sensitivity is band-flat within a few dB). **`TODO(unverified)`:** a
> 433 MHz-specific FLRC sensitivity row. The 915 MHz values are used as the honest
> characterisation; using them at 433 MHz does not change any conclusion (the LoRa/FLRC
> gap is 36 dB, far larger than any band-to-band few-dB difference).

**2.4 GHz LoRa** (for the uplink cross-check), **Table 3-18**:
`LORA_2G4_200_SF12` (BW 200 kHz, SF 12) = **−137 dBm**; `LORA_2G4_400_SF12` = −134 dBm.

### 1b. Transmitter power — Semtech LR2021

Datasheet **Table 3-22** ("Transmit Mode Specification"):

| Symbol | Description | Min | Typ | Max |
|---|---|---:|---:|---:|
| `TXOPLF` | Maximum Tx power, **sub-GHz** PA | 19 | **22** | —  dBm |
| `TXOPHF` | Maximum Tx power, 2.4 GHz PA | — | **12** | —  dBm |
| `TXPRNGLF` | Tx power range (programmable) | — | 63 steps × 0.5 dB = **31.5 dB** below max | — |

So the **low-power LR2021** (bare chip, no external PA) delivers **up to +22 dBm** on
433 MHz, programmable down in 0.5 dB steps — the operator's **"+13…+22 dBm class" is
consistent with the chip's own PA** (max 19–22 dBm; 63 × 0.5 dB of range below it).

### 1c. NiceRF LoRa2021 module — independent confirmation

NiceRF **LoRa2021 Module Datasheet V1.3** (local copy
`docs/assets/lr2021/LoRa2021-Module-Datasheet-V1.3.pdf`; NiceRF product family — the
sub-GHz + 2.4 GHz LR2021 module used on the flight board):

* **Transmit Power:** `@Sub-GHz  19 / 21 / 22 dBm` (min/typ/max); `@2.4GHz  10 / 11 / 12 dBm`.
* **Receive Sensitivity:** `-143 dBm @ BW=62.5 kHz, SF=12 (Sub-GHz)`; `-136 dBm @ BW=125 kHz,
  SF=10 (Sub-GHz)`; `-134 dBm @ BW=406 kHz, SF=12 (2.4 GHz)`.
* **FLRC modulation rate @sub-GHz: 260 – 2600 kbps.**

This corroborates the Semtech numbers (module adds a PCB/LNA path, hence −143 for the
module vs −143 for the bare chip at the same SF/BW).

---

## 2. The deciding calculation

**Equation.** With `G_balloon` the balloon's 433 transmit-antenna gain (dBi) and `P_tx`
the conducted power (dBm → EIRP `= P_tx + G_balloon`, dBm):

```
required_G_ground  =  S_dBm  +  FSPL_dB  −  P_tx_dBm  −  G_balloon_dBi
```

**Path loss.** `FSPL = 20 log10(4πdf/c)`; at **433.05 MHz, 650 km → 141.4 dB** (computed;
the repo's committed 300 km figure is 134.7 dB, so 650 km adds **+6.7 dB**).

**Assumptions.** `G_balloon = 0 dBi` (conservative; `docs/LINK-BUDGET-LICENCE-EXEMPT.md`
uses 0 dBi for the small balloon 433 antenna and notes 2.15 dBi for a half-wave dipole).
`P_tx` is swept from the chip max (**+22 dBm**) down to a low-power point (**+13 dBm**),
plus the **committed licence-exempt design point** (**+12.15 dBm EIRP** = 10 mW ERP
integral antenna, per ADR-039/041; EIRP = ERP + 2.15 dB).

### 2a. LoRa (SF12-class) — huge negative requirement, i.e. gain is optional

`G_balloon = 0 dBi`. Required ground gain (dBi) and margin with a 12 dBi Yagi:

| Modulation | S (dBm) | req G_ground @ +22 dBm | @ +13 dBm | @ +12.15 dBm EIRP | margin @ 12 dBi Yagi |
|---|---:|---:|---:|---:|---:|
| LoRa SF12 / BW125 | −141.5 | **−22.1** | −13.1 | −12.2 | +34.1 dB |
| **LoRa SF12 / BW62.5** | **−143** | **−23.6** | −14.6 | −13.7 | **+35.6 dB** |
| LoRa SF12 / BW31.25 | −147 | −27.6 | −18.6 | −17.7 | +39.6 dB |

**Reading:** the required ground gain is *negative* — an isotropic antenna already closes
the 650 km LoRa link by 12–28 dB. **The ground station does not need a 433 Yagi to close
LoRa; it needs one only to buy fade margin.** A 12–15 dBi Yagi turns that into +24 to +40 dB.

### 2b. FLRC — a positive requirement, and it decides the antenna class

`G_balloon = 0 dBi`. Required ground gain (dBi):

| Modulation | S (dBm) | @ +22 dBm | @ +19 dBm | @ +13 dBm | @ +12.15 dBm EIRP |
|---|---:|---:|---:|---:|---:|
| FLRC 2.6 Mbps | −100.5 | **+18.9** | +21.9 | **+27.9** | +28.8 |
| FLRC 1.04 Mbps | −105 | **+14.4** | +17.4 | +23.4 | +24.3 |
| **FLRC 650 kbps** | **−107** | **+12.4** | +15.4 | **+21.4** | +22.3 |
| FLRC 520 kbps | −108.5 | +10.9 | +13.9 | +19.9 | +20.8 |
| FLRC 325 kbps | −110 | +9.4 | +12.4 | +18.4 | +19.3 |

Margin with a 12 dBi Yagi (`G_yagi − req_G`):

| Modulation | @ +22 dBm | @ +13 dBm | @ +12.15 dBm EIRP |
|---|---:|---:|---:|
| FLRC 2.6 Mbps | **−6.9** | −15.9 | −16.8 |
| FLRC 1.04 Mbps | −2.4 | −11.4 | −12.3 |
| FLRC 650 kbps | **−0.4** | **−9.4** | −10.3 |
| FLRC 325 kbps | +2.6 | −6.4 | −7.3 |

**Reading:** at the chip's **+22 dBm** and the slowest practical FLRC rate (650 kbps), a
12 dBi Yagi is **exactly at zero margin (−0.4 dB)** — indistinguishable from failure once
any real-world loss (polarisation, pointing, atmosphere) is added. At **low power**
(+13 dBm / the licence-exempt +12.15 dBm EIRP point) FLRC needs **+21 to +29 dBi** — a
**dish-level** antenna.

### 2c. What 433 MHz gain is achievable, per antenna class

Dish gain `G = 10 log10(η (πD/λ)²)`, η = 0.60, λ(433 MHz) = 692.3 mm (computed):

| Diameter | G @ 433 MHz |
|---:|---:|
| 1.2 m | 12.5 dBi |
| 1.5 m | 14.4 dBi |
| 2.7 m | 19.5 dBi |
| 3.0 m | 20.5 dBi |

| Antenna class | Gain | Covers |
|---|---:|---|
| Omni / small whip | 0–3 dBi | **all LoRa cases** |
| 7–9-elem Yagi (repo's assumption) | **10–15 dBi** | LoRa; FLRC 650 kbps @ +22 dBm only (0 margin) |
| Array of Yagis / large Yagi | 15–18 dBi | marginal FLRC 650 kbps |
| **Dish ~2.7–3.0 m** | **≈ 20 dBi** | FLRC @ low power, FLRC ≥ 1 Mbps |

**Conclusion of the deciding calc:** the antenna class each modulation implies is
**LoRa → omni-to-Yagi**; **FLRC → dish**, and the *specific* crossover is
**FLRC at 650 km with power below ~+22 dBm, or any FLRC rate ≥ 1 Mbps at any power**.

---

## 3. Reconciling the repo's −143 dBm figure

The task flagged "an earlier note claims the repo's own link budget uses −143 dBm for
sub-GHz — check whether it is LoRa or FLRC".

**It is LoRa. Confirmed, not FLRC.**

* `docs/inventory.md` line 31: `Sensitivity: -143dBm (SF12/62.5kHz Sub-GHz), -137dBm
  (SF12/203kHz 2.4GHz)` → **SF12/62.5 kHz = LoRa**.
* `docs/F33-MODULE-PLAN.md` line 33: `Sub-GHz sensitivity | -143 dBm (BW=62.5KHz, SF=12)`.
* `docs/assets/lr2021/README.md`: `RX Sensitivity: −143 dBm (Sub-GHz, BW=62.5 kHz, SF=12)`.
* Semtech datasheet Table 3-17, `LORA_SUB_62_SF12 = −143 dBm` — matches exactly.
* NiceRF V1.3 module datasheet: `-143dBm @ BW=62.5 KHz, SF=12` — matches.

**The FLRC figure is a completely different number.** FLRC at 650 kbps is **−107 dBm**
(Semtech Table 3-12) — **36 dB worse** than LoRa's −143 dBm. That 36 dB is the entire
reason this analysis produces two different answers.

`docs/LINK-BUDGET-LICENCE-EXEMPT.md` §0/§2 correctly labels the −143 figure
"Bare LoRa2021 sub-GHz RX sensitivity (−143 dBm, SF12/62.5 kHz)" and computes the 433
downlink at **+30.3 dB** margin (12 dBi Yagi, 10 dBm EIRP). Reproduced here: with
−143 dBm, +10 dBm EIRP, 12 dBi Yagi at **300 km** → margin ≈ +30.3 dB. At **650 km**
the extra 6.7 dB of path loss brings it to **≈ +23.6 dB** — still comfortably closed.
**The repo's committed budget is internally consistent and is a LoRa budget.**

> **If anyone has been implicitly treating the 433 downlink as FLRC while quoting
> −143 dBm, they are 36 dB optimistic.** That is the single most important
> reconciliation in this document.

---

## 4. Reconciling "low-power LR2021, +13…+22 dBm" with the licence-exempt cap

There is a genuine conflict between the operator's power assumption and the committed
regulatory design point, and it is worth stating plainly:

* The **chip** can do **+19 to +22 dBm** sub-GHz (datasheet Table 3-22 `TXOPLF`), programmable
  down by 31.5 dB.
* The **committed design point** (ADR-039 "Licence-Exempt 433 MHz Design Point", ADR-041)
  caps the balloon's 433 transmitter at **10 mW ERP with an integral antenna** =
  **+10 dBm ERP = +12.15 dBm EIRP** (`docs/LINK-BUDGET-LICENCE-EXEMPT.md` §0, sourced to
  `docs/SOLAR-PIN-REGULATORY.md` §3.2 → ERC Rec 70-03 Annex 1 / LPD433).
* **+12.15 dBm EIRP lies below the operator's own +13 dBm low end.** Under the
  licence-exempt design point the balloon **cannot** transmit the +13…+22 dBm class at
  433 MHz; the whole range is **at or above the cap** (ADR-041: "even the bare module's own
  22 dBm, exceed[s] the 433 licence-exempt 10 mW ERP ceiling").

**Implication for this analysis.** The +13…+22 dBm rows are only physically realisable
under the **German amateur (DE) licence** (or another regime that permits it). Both are
modelled above, and **the conclusion does not depend on which regime applies**: LoRa closes
with negative required gain in *every* row, and FLRC needs a dish in *every* row except
"+22 dBm at ≤ 650 kbps". The regulatory cap only makes the FLRC-dish requirement *worse*.

> **`TODO(unverified)`:** ADR-039 open item (a) — licence-exempt SRD **airborne** use is a
> grey area; a national-regulation check is required before flight. This analysis inherits
> that caveat.

---

## 5. Shared-dish research findings

The task's four questions, answered with citations. Where a real, checkable source does
not exist, it is said so rather than invented.

### 5.1 Reusing a Ku-band satellite dish at 2.4 GHz — established practice?

**Yes, it is well-established amateur/commercial practice**, and the RF reasons are
favourable:

* **Surface accuracy is a non-issue.** A consumer offset Ku dish is built for ~10.7–12.75 GHz;
  at 2.4 GHz it is grossly over-accurate. Wikipedia (Parabolic antenna): *"To achieve the
  maximum gain, the shape of the dish needs to be accurate within a small fraction of a
  wavelength, around one sixteenth [of a wavelength]"* — at 2.4 GHz one sixteenth is
  ~7.8 mm, versus an offset Ku dish's Ku-tight tolerance (< 1.5 mm)
  (<https://en.wikipedia.org/wiki/Parabolic_antenna>).
* **Documented reuse builds exist.** A widely-cited amateur build repurposes a surplus
  **Primestar** Ku TV dish as an IEEE 802.11 (2.4 GHz) antenna: *"The resulting antenna has
  about **22 db of gain** … fed with 50 ohm coaxial cable … range using two of these
  antennas with a line of sight path is around 10 miles at full bandwidth."*
  <https://fweb.wallawalla.edu/~frohro/Airport/Primestar/Primestar.html>
  — note the build **replaces the feed** with a "juice can" (can-tenna) feed; it does not
  reuse the Ku LNB feed. That is the key real-world lesson: **reuse the reflector, replace
  the feed.**
* **The constraint is the feed, not the dish.** For a paraboloid the rim subtends a
  half-angle at the focus `θ = 2·atan(1/(4·f/D))` (computed):

  | f/D | θ (half-angle) |
  |---:|---:|
  | 0.25 | 90.0° |
  | 0.35 | 71.1° |
  | 0.40 | 64.0° |
  | 0.50 | 53.1° |
  | 0.60 | 45.2° |
  | 0.70 | 39.3° |

  Consumer offset Ku dishes sit around **f/D 0.5–0.75** (satsig.net: *"If the f/D is large
  like 0.5 to 0.75 then the feed will be further away from the dish and needs to project its
  power into a narrower angle"* — <https://www.satsig.net/focal-length-parabolic-dish.htm>).
  So the 2.4 GHz feed must illuminate roughly **±40–53°**.
* **Optimum illumination is a 10 dB edge taper.** W1GHZ, *Microwave Antenna Handbook*
  Ch. 11: *"maximum aperture efficiency occurs when the illumination energy is 10 dB down
  at the edge of the dish"*, and a feed pattern is best matched to **f/D ≈ 0.4**; for
  f/D > 0.5 *"spillover loss increases"*.
  <https://www.qsl.net/n1bwt/chap11.pdf>
* **Offset geometry is a genuine advantage here.** Wikipedia (Parabolic antenna): a
  front/prime-focus feed *"and its supports block some of the beam, which limits the
  aperture efficiency to only 55–60%"*, whereas an *"off-axis or offset feed … move[s] the
  feed structure out of the beam path"*
  (<https://en.wikipedia.org/wiki/Parabolic_antenna>). So an offset Ku dish at 2.4 GHz is
  the *better* geometry — feed blockage is designed out.

**Verdict 5.1:** the Ku dish at 2.4 GHz is not a compromise, it is over-qualified
(~22–27 dBi, surface accuracy with ≥5× margin, offset geometry that avoids feed blockage).
**Feasible and documented.**

### 5.2 Dual-band single-reflector feeds at a 5.5 : 1 ratio (433 MHz + 2.4 GHz)

**No product or documented build of a single feed illuminating one reflector at both
433 MHz and 2.4 GHz was found.** `TODO(unverified)` — an exhaustive search was not possible
this session; if a vendor feed exists it should replace this paragraph.

What *does* exist, and why the 5.5:1 case is hard:

* **Dichroic / frequency-selective subreflectors** are the professional technique — an
  FSS is *"a thin, repetitive surface … designed to reflect, transmit or absorb
  electromagnetic fields based on the frequency of the field"*
  (<https://en.wikipedia.org/wiki/Frequency_selective_surface>). This is the Cassegrain/
  DSN multi-band approach; it needs a precision subreflector and dual foci — out of scale
  for a portable balloon station.
* **Diplexers** combine two bands onto **one feedline** (`docs` note; Wikipedia Diplexer,
  <https://en.wikipedia.org/wiki/Diplexer>) — but a diplexer solves the *cable/port*
  problem, **not** the *illumination* problem. One aperture still needs one feed whose
  pattern covers the rim angle at *both* frequencies.
* **The illumination-angle wall is the real barrier.** A single feed must illuminate
  ±40–53° (2.4 GHz, f/D 0.6–0.7) *and* a much wider angle at 433 MHz for the same dish.
  A fixed feed cannot do both; this is exactly the size-mismatch the prior analysis
  (`docs/analysis/dualband-single-dish.md` §4) quantified: a 2.4 GHz λ/2 feed element
  (~62.5 mm) is only **0.09 λ** at 433 MHz — an electrically tiny, near-omni radiator, i.e.
  a bad dish feed.
* **"Two feeds near the focus" is sound at 433 MHz, precisely because λ is long.** The
  λ/4-as-1-dB defocus tolerance is **173 mm at 433 MHz** vs **31 mm at 2.4 GHz** (computed).
  A second 433 feed can sit ~5–10 cm off the 2.4 GHz feed's focus and lose only
  ~0.1–0.2 dB. The prior analysis reached the same conclusion
  (`dualband-single-dish.md` §5) and flagged the exact loss as `TODO(unverified)`
  (needs MoM simulation/measurement).

**Verdict 5.2:** a *true* single dual-band feed at 5.5:1 is not a thing you can buy or
that was found documented; the physics (illumination angle + electrically-tiny feed at
433 MHz) argues against it. **"Two feeds near the focus" is mechanically viable but the
433 MHz path still only yields a few dBi from a Ku-sized dish** (aperture formula gives
~12.5 dBi for 1.2 m at 433 MHz, and feed mismatch pushes the practical figure down). The
prior analysis's `TODO(unverified)` on that mismatch still stands.

### 5.3 Coarse mesh / grid reflectors at 433 MHz

**The λ/10 hole rule is real and generously satisfies 433 MHz.** Wikipedia (Parabolic
antenna): *"A metal screen reflects radio waves as effectively as a solid metal surface if
its holes are smaller than **one-tenth of a wavelength**, so screen reflectors are often
used to reduce weight and wind loads on the dish."*
<https://en.wikipedia.org/wiki/Parabolic_antenna>

Computed λ/10:

| Band | λ | λ/10 (max hole) |
|---|---:|---:|
| **433 MHz** | 692.3 mm | **69.2 mm** |
| 2.4 GHz | 124.9 mm | 12.5 mm |

**Verdict 5.3:** at 433 MHz a mesh/grid with **~70 mm** holes is electrically equivalent
to a solid reflector — **extremely coarse mesh is fine**, and a wire-grid parabola is
practical and light. **But at 2.4 GHz the same reflector needs ≤ 12.5 mm holes**, so a
single coarse mesh cannot serve both bands. This is a concrete reason the *shared
reflector* idea fails while the *shared positioner* idea works: the 2.4 GHz dish must be a
solid (or fine-mesh) offset Ku dish, and the 433 element should be a **separate**
antenna.

> Grid-dish "penalties" beyond the λ/10 rule (edge effects, cross-polarisation from the
> grid orientation) and a **named commercial grid-dish example with a datasheet hole size**
> are `TODO(unverified)` here — web-search backends were unavailable for this item this
> session, so no example is cited rather than a guessed one. The λ/10 rule above is the
> citable core; the physics conclusion (coarse 433 mesh cannot also serve 2.4 GHz) does not
> depend on it.

### 5.4 Boresighting a Yagi on the dish structure — blockage / interference

**The concern is real but small at these wavelength ratios, and the published rule is
about *prime-focus* feeds, not side-mounted elements.**

* Wikipedia (Parabolic antenna): a prime-focus feed *"and its supports block some of the
  beam, which limits the aperture efficiency to only 55–60%"*
  (<https://en.wikipedia.org/wiki/Parabolic_antenna>). That is the upper bound of the
  effect, for a feed **in** the beam on-axis.
* Geometric blockage scales as the **area ratio**. A 433 Yagi (boom ~1.2 m, elements
  thin, cross-section maybe ~0.05 m² at 2.4 GHz) inside a 1.2 m dish aperture (~1.13 m²)
  blocks ~1–2 % of area → **≈ 0.05–0.1 dB** — negligible. The prior analysis computed the
  same order (`dualband-single-dish.md` §5.2: a 15 cm Yagi ≈ 1.6 % → ~0.07 dB).
* **The cleaner mechanical answer is the operator's own idea, improved:** mount the 433
  Yagi **on the positioner head beside the dish** rather than in the 2.4 GHz beam
  (prior analysis option (b′)). If the 433 Yagi is boresighted with the dish but offset
  laterally from the aperture, blockage is ~0 while pointing is shared.
* **Pointing is not a problem.** The 433 Yagi's beamwidth is ~40–50°, so whenever the
  2.4 GHz dish (narrow, ~7–10°) is on target, the Yagi is automatically on target. The
  433 Yagi is the *forgiving* element; the dish does the tight pointing.
* **Interference** (433 TX coupling into the 2.4 GHz RX chain): the two bands are 5.5:1
  apart, so a diplexer/filter on the shared feedline handles it; if the antennas are
  physically separate (recommended), coupling is just proximity at very different
  frequencies and is managed by separation + filtering. `TODO(unverified)`: a measured
  isolation figure for the chosen geometry.

**Verdict 5.4:** boresighting a 433 Yagi on the dish structure is **sound**; the
blockage penalty is ~0.1 dB if it is offset from the aperture, and pointing comes free.
Prefer mounting beside/under the dish on the same az/el head rather than across the
2.4 GHz aperture.

---

## 6. Recommendation

1. **Keep the 2.4 GHz uplink on the Ku offset dish.** It is over-qualified (~22–27 dBi),
   surface-accuracy-rich, and the offset geometry removes feed blockage (§5.1). Replace
   the Ku LNB with a **2.4 GHz feed designed for the dish's f/D** (illuminate ±40–53°,
   ~10 dB edge taper) — this is the standard, documented reuse path.

2. **Use the Ku dish for 2.4 GHz and a SEPARATE 433 antenna on the same positioner.**
   Do **not** try to make one reflector serve 433 MHz: a coarse 433 mesh cannot also serve
   2.4 GHz (§5.3), a true 5.5:1 dual-band feed does not exist (§5.2), and a 1.2 m dish
   gives only ~0–12 dBi at 433 MHz anyway.

3. **For the LoRa downlink — which is the long-range mode — a 12–15 dBi 433 Yagi is more
   than enough** (required gain is negative; margin +24 to +40 dB). Boresight it on the
   positioner head beside the dish (§5.4). **The ground station is not the bottleneck for
   LoRa; the Ku dish is set by the 2.4 GHz uplink, not by the 433 downlink.**

4. **Treat FLRC as a short-range mode, and say so in the design.** FLRC at 650 km needs
   +9 to +28 dBi (§2b). If FLRC is only used for nearby high-rate passes (as
   `docs/link-budget.md` already assumes: ~25–30 km), the architecture is confirmed.

5. **THE ONE CASE THAT CHANGES THE ANSWER — state it and own it:** if the 650 km downlink
   must carry **FLRC at low power (≤ +19 dBm), or any FLRC rate ≥ 1 Mbps**, then the 433
   antenna must deliver **≈ +19 to +28 dBi**, i.e. a **2.7–3.0 m dish** (or a large Yagi
   array) — not a boresighted Yagi. At that point the "small boresigned 433 antenna on the
   Ku positioner" premise is refuted: you would need a second large reflector, with its
   own mass/wind/pointing problem. **Recommendation: do not require FLRC on the far link;
   make LoRa the far-link mode and FLRC the close-mode. Then the shared-positioner
   architecture is confirmed.**

**Verdict on the operator's architecture:** **CONFIRMS** *"Ku dish for 2.4 GHz + boresighted
433 antenna on one positioner"* **for LoRa**, and **REFUTES** it **only** in the FLRC-at-
long-range / low-power case, where the 433 antenna must become a dish.

---

## 7. Open items (not assumed)

1. `TODO(unverified)` 433 MHz-specific FLRC sensitivity row (915 MHz values used; §1a).
2. `TODO(unverified)` a documented / purchasable **single** dual-band feed at 433/2400 MHz
   (§5.2) — none was found; the claim is "not found", not "does not exist".
3. `TODO(unverified)` measured 433 MHz feed-mismatch loss on a Ku dish
   (inherited from `dualband-single-dish.md` §4.3) — closes the "0–6 dBi practical" estimate.
4. `TODO(unverified)` measured RMS surface accuracy of the candidate Ku dish (§5.1) —
   industry rule-of-thumb only.
5. `TODO(unverified)` ADR-039 item (a): licence-exempt SRD airborne-use grey area (§4).
6. `TODO(unverified)` `docs/LINK-BUDGET-LICENCE-EXEMPT.md` §0 already flags the exact
   ERC Rec 70-03 Annex 1 row / duty-cycle condition for 2.4 GHz wideband — inherited.
7. Horizon caveat: 650 km at 30 km altitude is slightly **beyond** the geometric radio
   horizon `√(2Rh) = 618 km` (the repo uses this formula, `docs/link-budget.md`) but
   within the standard 4/3-Earth refraction horizon (~714 km). 650 km is taken as given
   by the task; it is physically plausible with atmospheric refraction.

---

## 9. Independent consultation (visual consultant)

**Consultant:** `scripts/fleet/visual_consult.py` (fleet script), pinned model
**`gpt-6-astra`** (OpenAI Astra 6, `astra-consultant` profile — per
`visual-consultant` skill). Artifact consulted:
`docs/analysis/assets/lowpower-link-verdict.png` (rendered from
`docs/analysis/render_lowpower_link_figure.py`).

**Engagement status:** engaged. The first attempt returned HTTP 503 ("all candidate lanes
busy or capped") — the same failure class that killed the two prior attempts at this task —
but retries succeeded and the lane served **`gpt-6-astra`**. Verdict recorded verbatim below.

**Served model (read back from the response):** `gpt-6-astra`

**Verdict line (verbatim):**
```
visual_review: APPROVED
visual_reviewer_model: gpt-6-astra
```

**Consultant answer (verbatim, saved to `docs/analysis/assets/consult-verdict.txt`):**

> 1. **Yes, broadly.** The LoRa bars are all left of the 0 dBi line, so even an approximately
> isotropic 433 MHz antenna closes the link with margin. The FLRC bars require positive gain:
> they are at or above the 12 dBi Yagi reference and extend beyond the 20 dBi dish line,
> especially at 13 dBm TX power and higher data rates. Thus the figure supports the
> LoRa/FLRC split.
> *Qualification:* a nominal 20 dBi dish is not sufficient for every listed FLRC case—the
> required gain reaches about 27.9 dBi.
>
> 2. **Yes.** The 433 MHz Yagi is sketched beside/below the dish aperture, not across the
> Ku/2.4 GHz dish beam. The drawing explicitly labels it "beside the aperture."
>
> 3. **No obvious visual contradiction.** The bars, reference lines, antenna sketch, and
> bottom verdict all consistently show LoRa as workable with a Yagi or lower-gain antenna,
> while demanding FLRC cases require substantially more than a Yagi and may require a
> dish-class antenna. The only qualification visible in the figure is that a 20 dBi dish is
> not enough for all low-power/high-rate FLRC combinations.
>
> independent VERDICT: **CONFIRM**

**How the consultation changed this document:** the consultant's qualification (item 1) was
**accepted as correct** and folded into §0 and §6 — "~20 dBi dish" was shorthand that
understated the worst FLRC case (+27.9 dBi). The recommendation is unchanged; the wording is
now honest about the size.

**Note:** a visual consult is not a cross-family *code* review — it does not satisfy the
D-128/ADR-010 review gate (see `visual-consultant` skill, pitfall 10).

---

## 10. Reproduce


```bash
python3 docs/analysis/ground_station_lowpower_link_model.py
```

Every table in §1a, §1b (values), §2 and §5 (geometry) is printed by that script from
datasheet constants; the datasheet PDFs it cites are in-repo:
`docs/lr2021-research/semtech-official/LR2021_LR2022_LR2012_Datasheet_v2.2.pdf` and
`docs/assets/lr2021/LoRa2021-Module-Datasheet-V1.3.pdf`.

---

*End of analysis.*
