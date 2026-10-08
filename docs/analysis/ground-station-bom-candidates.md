# Ground-station BOM candidates — purchasable antenna hardware (2.4 GHz uplink + 433 MHz downlink)

**Status: BOM INPUT SOURCING.** Nothing here is ordered. This document exists so the
ground-station bill of materials can cite real vendors, real URLs and real prices.

**Branch:** `design/ground-station-bom` (off `github/main`, tip `09e1b69`).
**Method:** every figure below was read off the vendor page or vendor price list named in
the item's **Source** line. Items marked **CONFIRMED** = the vendor page was fetched and the
figure seen. Items marked **INFERRED** = the *family/vendor* is real and confirmed but this
exact figure was not on a page I could read. `TODO(unverified)` = I could not verify it and
did **not** invent a value.

**Scope rules applied:** nothing is ordered; no fab freeze; `AGENTS.md` untouched.

---

## 0. Summary table

Prices are the vendor's listed price. `€` = EUR. "Wind" = vendor-stated wind-load rating
(units as the vendor gives them — Yaesu quotes antenna *area*; RF Hamdesign quotes
*displacement at 120 km/h*).

### 0.1 433 MHz downlink antennas

| # | Vendor | Product | Gain | Conn. | Boom | Price | Region | Status |
|---|--------|---------|-----:|-------|------|------:|--------|--------|
| A1 | Funktechnik Bielefeld (DE) | Sirio WY 400-3N | 7 dBi | N-f | ~0.6 m | €99.00 | EU | CONFIRMED |
| A2 | Funktechnik Bielefeld (DE) | Sirio WY 400-6N | 11 dBi | N-f | ~1.2 m | €132.00 | EU | CONFIRMED |
| A3 | Funktechnik Bielefeld (DE) | Sirio WY 400-10N | 14 dBi | N-f | 2.0 m | €155.00 | EU | CONFIRMED |
| A4 | Funktechnik Bielefeld (DE) | Diamond A-430S10R | 13.1 dBi | PL/SO-239 | 0.82 m | €69.00 | EU | CONFIRMED |
| A5 | Funktechnik Bielefeld (DE) | Diamond A-430S15R | 14.8 dBi | TODO | 1.39 m | €74.50 | EU | CONFIRMED |
| A6 | Funktechnik Bielefeld (DE) | FlexaYagi FX 7015V | 10.2 dBd (12.4 dBi) | TODO | 1.19 m | €125.00 | EU | CONFIRMED |
| A7 | Funktechnik Bielefeld (DE) | FlexaYagi FX 7044 | 14.4 dBd (16.6 dBi) | TODO | 3.08 m | €164.00 | EU | CONFIRMED |
| A8 | Funktechnik Bielefeld (DE) | FlexaYagi FX 7044-4 | 14.5 dBd (16.7 dBi) | TODO | 3.08 m | €219.00 | EU | CONFIRMED |
| A9 | Funktechnik Bielefeld (DE) | FlexaYagi FX 7073 | 15.8 dBd (18.0 dBi) | TODO | 5.07 m | €215.00 | EU | CONFIRMED |
| A10 | RF Hamstore (NL) | 70 cm power divider | — | N-f | — | TODO(unverified) | EU | INFERRED |

### 0.2 Ku-band dishes (0.8–1.2 m) reusable at 2.4 GHz

| # | Vendor | Product | Ø | Wind | Price | Region | Status |
|---|--------|---------|---:|------|------:|--------|--------|
| B1 | hm-sat (DE) | Gibertini OP100SE (100 SE Profi) | 0.97×1.04 m | 91 kg @ 120 km/h | €143.90 | EU | CONFIRMED |
| B2 | hm-sat (DE) | Gibertini 85 SE Profi | 0.85 m | TODO | €104.90 | EU | CONFIRMED |
| B3 | hm-sat (DE) | Gibertini 75 SE Profi | 0.75 m | TODO | €94.90 | EU | CONFIRMED |
| B4 | hm-sat (DE) | Kathrein CAS 90 | 0.90 m | TODO | €249.00 | EU | CONFIRMED |
| B5 | hm-sat (DE) | Kathrein CAS 80 | 0.75 m | TODO | €169.00 | EU | CONFIRMED |
| B6 | Kleinanzeigen (DE) | used 90 cm Kathrein CAS 90 | 0.90 m | TODO | €50 (example) | EU | CONFIRMED |

### 0.3 2.4 GHz feeds for a dish + Wi-Fi-grid alternatives

| # | Vendor | Product | Band | f/D | Price | Status |
|---|--------|---------|------|-----|------:|--------|
| C1 | RF Hamdesign (NL) | HORN-13 S-band horn feed | 2.0–2.5 GHz | 0.45 | quote | CONFIRMED |
| C2 | RF Hamdesign (NL) | FPF RS-ONE ring feed | 0.9–3.4 GHz tune | 0.45 | €185.00 | CONFIRMED |
| C3 | RF Hamdesign (NL) | LH-13XL helix feed | 2.1–2.7 GHz | 0.45 | €220.00 | CONFIRMED |
| C4 | RF Hamdesign (NL) | LH-ISS helix feed | 2.4–2.5 GHz | 0.45 | €220.00 | CONFIRMED |
| C5 | RF Hamdesign (NL) | CIR-2320 LHCP/RHCP feed | 2320 MHz | 0.45 | quote | CONFIRMED |
| C6 | RF Hamdesign (NL) | CLX1 / CLX-06 feed clamp | — | — | €46 / €199 | CONFIRMED |
| C7 | TP-Link / Ubiquiti | Wi-Fi 24 dBi grid / 2.4 GHz dish | 2.4 GHz | n/a | TODO(unverified) | INFERRED |

### 0.4 433 MHz mesh dish (purchasable + DIY)

| # | Vendor | Product | Ø | Mesh | Price | Status |
|---|--------|---------|---:|------|------:|--------|
| D1 | RF Hamdesign (NL) | FPD 1M2 KIT mesh dish | 1.2 m | 6 mm | €387.20 | CONFIRMED |
| D2 | RF Hamdesign (NL) | FPD 1M5 KIT mesh dish | 1.5 m | 6 mm | €499.73 | CONFIRMED |
| D3 | RF Hamdesign (NL) | FPD 1M9 KIT mesh dish | 1.9 m | 6 mm | €901.45 | CONFIRMED |
| D4 | RF Hamdesign (NL) | BR-50 fixed-elevation bracket | — | — | €135.00 | CONFIRMED |
| D5 | Bauhaus/OBI/Amazon (DE) | aluminium window mesh / welded wire | — | — | TODO(unverified) | INFERRED |

### 0.5 AZ/EL positioners with wind-load ratings

| # | Vendor | Product | Axes | Wind rating | Price | Status |
|---|--------|---------|------|-------------|------:|--------|
| E1 | Funktechnik Bielefeld (DE) | Yaesu G-5500DC | AZ+EL | 1.00 m² tower / 0.50 m² mast | €949.00 | CONFIRMED |
| E2 | Funktechnik Bielefeld (DE) | Yaesu G-450CDC | AZ+EL* | 1.00 / 0.50 m² (G-450A) | €359.00 | CONFIRMED |
| E3 | Funktechnik Bielefeld (DE) | Yaesu G-1000DXC | AZ | 2.20 / 0.74 m² (G-1000DXA) | €529.00 | CONFIRMED |
| E4 | Funktechnik Bielefeld (DE) | Yaesu G-2800DXC | AZ | 3.00 / 1.00 m² (G-2800DXA) | €1,049.00 | CONFIRMED |
| E5 | RF Hamdesign (NL) | SPID RAS AZ&EL | AZ+EL | TODO(unverified) | €1,260.82 | CONFIRMED |
| E6 | RF Hamdesign (NL) | SPID BIG-RAS AZ&EL | AZ+EL | handles dishes ≤5 m | €1,775.00 | CONFIRMED |
| E7 | RF Hamdesign (NL) | SPX-01 AZ&EL (light) | AZ+EL | TODO(unverified) | €1,132.00 | CONFIRMED |
| E8 | RF Hamdesign (NL) | SPX-02 AZ&EL (medium) | AZ+EL | TODO(unverified) | €1,249.00 | CONFIRMED |
| E9 | RF Hamdesign (NL) | SPX-06 AZ&EL slew drive | AZ+EL | 716 Nm, IP65 | €5,487.35 | CONFIRMED |

### 0.6 Low-loss coax

| # | Cable | Ø | Loss @433 MHz | Loss @2.4 GHz | Price | Status |
|---|-------|---:|--------------:|--------------:|------:|--------|
| F1 | Ecoflex 15 | 14.6 mm | 0.61 dB/10 m | 1.62 dB/10 m | €13.60/m | CONFIRMED |
| F2 | Ecoflex 10 | 10.3 mm | 0.85 dB/10 m | 2.24 dB/10 m | €6.70/m | CONFIRMED |
| F3 | Airborne 10 (LMR-400 class) | 10.3 mm | 0.76 dB/10 m | 1.92 dB/10 m | €6.50/m | CONFIRMED |
| F4 | H2010 EVO | 10.3 mm | 0.81 dB/10 m | 2.08 dB/10 m | €6.50/m | CONFIRMED |
| F5 | Aircell 7 | 7.3 mm | 1.29 dB/10 m | 3.38 dB/10 m | €4.06/m | CONFIRMED |

---

## 1. 433 MHz Yagi downlink antennas

**Band note.** The EU 70 cm amateur band is 430–440 MHz; the 433 MHz ISM/ISM-SRD allocation
is 433.05–434.79 MHz, which sits **inside** it. A 70 cm ham Yagi (430–440 MHz) therefore
covers 433 MHz directly, and the Sirio WY 400 family (400–470 MHz) covers it with margin.
Gain figures below are as printed by the vendor (some in **dBd** = gain over a dipole;
conversion **dBi = dBd + 2.15**).

**Polarisation.** All of these are linearly polarised Yagis, normally mounted with elements
**vertical** or **horizontal** at choice (Sirio gives both E- and H-plane beamwidths). Match
the balloon's antenna orientation. The ballon downlink uses the LR2021 (see
`docs/analysis/meshcore-lr2021-drift.md`); low-power assumption means ground gain may need to
be at the high end of this list.

### A1 — Sirio WY 400-3N (short / entry)
- **Vendor:** Funktechnik Bielefeld (DE) · **Price:** €99.00
- **URL:** https://www.funktechnik-bielefeld.de/sirio-wy-400-3n-3-element-400-470-mhz
- **Gain:** 7 dBi · **Elements:** 3 · **Band:** 400–470 MHz · **Max power:** 150 W CW
- **Beamwidth:** 125° (H-plane −3 dB), 65° (E-plane −3 dB) · **F/B:** ≥17 dB
- **Connector:** N female (page states N-Buchse)
- **Array:** vendor spec explicitly lists “Stacked and bayed array for more gain” and an
  optional ±20° tilting bracket → this family is designed to be stacked.
- **Status:** CONFIRMED (vendor page)

### A2 — Sirio WY 400-6N (moderate, ~9–11 dBi class)
- **Vendor:** Funktechnik Bielefeld (DE) · **Price:** €132.00
- **URL:** https://www.funktechnik-bielefeld.de/sirio-wy-400-6n-6-element-70cm-band-yagi-richtantenne-400-470-mhz
- **Gain:** 11 dBi / 9 dBd · **Elements:** 6 · **Band:** 400–470 MHz
- **Connector:** N female + rubber weather cap (page states N Buchse / Gummiwasserschutzkappe)
- **Status:** CONFIRMED (vendor page)

### A3 — Sirio WY 400-10N (mid, ~2 m boom)
- **Vendor:** Funktechnik Bielefeld (DE) · **Price:** €155.00
- **URL:** https://www.funktechnik-bielefeld.de/sirio-wy-400-10n-10-element-richtantenne-400-470-mhz
- **Gain:** up to 14 dBi (vendor text “bis zu 14 dBi Antennengewinn möglich”) · **Elements:** 10
- **Band:** 400–470 MHz · **Max power:** 150 W CW
- **Boom:** 2000 × 375 mm, rotation radius ~1860 mm · **Mast:** 35–52 mm
- **Connector:** N female (Antennenanschluss: N-Buchse)
- **Status:** CONFIRMED (vendor page)

### A4 — Diamond A-430S10R (mid/short, low wind)
- **Vendor:** Funktechnik Bielefeld (DE) · **Price:** €69.00
- **URL:** https://www.funktechnik-bielefeld.de/diamond-a-430s10r-uhf-10-element-70cm-band-richtantenne
- **Gain:** 13.1 dBi (Antennengewinn lt. Hersteller) · **Elements:** 10
- **Band:** 430–440 MHz · **Max power:** 50 W · **Boom:** 820 mm · **Mast:** 25–47 mm
- **Connector:** PL socket (SO-239 / UHF female)
- **Status:** CONFIRMED (vendor page)

### A5 — Diamond A-430S15R (long, 15 elements)
- **Vendor:** Funktechnik Bielefeld (DE) · **Price:** €74.50
- **URL:** https://www.funktechnik-bielefeld.de/diamond-a-430s15r-uhf-15-element-richtantenne-70cm-band
- **Gain:** 14.8 dBi · **Elements:** 15 · **Band:** 430–440 MHz · **Max power:** 50 W
- **Boom:** 1390 mm · **Mast:** 25–47 mm · **Connector:** TODO(unverified — page shows a
  mast bracket drawing 2245×370×73 mm but the connector type was not stated)
- **Status:** CONFIRMED price/gain; connector TODO

### A6 — FlexaYagi FX 7015V (short, ~10 dBd)
- **Vendor:** Funktechnik Bielefeld (DE) · **Price:** €125.00
- **URL:** https://www.funktechnik-bielefeld.de/flexayagi-fx-7015v-70cm-band-vormast-richtantenne-119cm-laenge
- **Gain:** 10.2 dBd (= 12.4 dBi) · **Boom:** 119 cm · **Max power:** 400 W PEP
- **Connector:** TODO(unverified — not stated on the vendor page)
- **Status:** CONFIRMED gain/price/boom; connector TODO

### A7 — FlexaYagi FX 7044 (long, ~3 m boom)
- **Vendor:** Funktechnik Bielefeld (DE) · **Price:** €164.00
- **URL:** https://www.funktechnik-bielefeld.de/flexayagi-fx-7044-70cm-band-richtantenne-308cm-laenge
- **Gain:** 14.4 dBd (= 16.6 dBi) · **Boom:** 308 cm · **Boom tube:** 15×15×1 mm
- **Connector:** TODO(unverified)
- **Status:** CONFIRMED gain/price/boom; connector TODO

### A8 — FlexaYagi FX 7044-4 (long, heavy-boom variant)
- **Vendor:** Funktechnik Bielefeld (DE) · **Price:** €219.00
- **URL:** https://www.funktechnik-bielefeld.de/flexayagi-fx-7044-4-70cm-band-richtantenne-308cm-laenge
- **Gain:** 14.5 dBd (= 16.7 dBi) · **Boom:** 308 cm
- **Status:** CONFIRMED gain/price/boom; connector TODO

### A9 — FlexaYagi FX 7073 (longest, ~5 m boom — high gain)
- **Vendor:** Funktechnik Bielefeld (DE) · **Price:** €215.00
- **URL:** https://www.funktechnik-bielefeld.de/flexayagi-fx-7073-70cm-band-richtantenne-507cm-laenge
- **Gain:** 15.8 dBd (= 18.0 dBi) · **Boom:** 507 cm
- **Status:** CONFIRMED gain/price/boom; connector TODO

> **Caution on dBd claims.** The FlexaYagi dBd figures (esp. 14.4 dBd on a 3.08 m boom)
> are the *vendor's* numbers and are optimistic versus typical published 70 cm Yagi data
> (a 70 cm Yagi is usually ~13–17 dBi). Treat them as vendor-stated, not measured. Verify
> against the manufacturer datasheet before the final BOM.

### A10 — 433 MHz stacked pair (array) + power divider
- The Sirio WY 400 datasheet explicitly supports “Stacked and bayed array for more gain”, so a
  **stacked pair of A2/A3** is the cheapest documented array path.
- **Divider:** RF Hamstore (NL) lists an **“Antenna Power Dividers → 70cm HAM Radio Dividers”**
  category — https://www.rfhamstore.com/ (category confirmed, individual product price
  `TODO(unverified)`).
- **Alt divider reference:** RF Hamdesign price list lists **FPQ RING13** (13 cm 3 dB hybrid
  ring coupler, 1 kW, N-female) at **€178.00** and **FPR 432** directional coupler
  (432–2320 MHz, 1 kW, 2×N-female) at **€144.00** — both in the Oct-2026 price list at
  https://www.rfhamdesign.com/downloads/rf-hamdesign-pricelist.pdf (these are 13 cm / power-
  measurement parts, included here only as confirmed N-type high-power couplers from the
  same vendor; a true 70 cm *power divider* should be bought from the rfhamstore category above).
- **Indicative stacked-pair gain:** 2× A3 stacked ≈ 14 dBi + 2.5–3 dB → ~17 dBi, at the cost of
  two booms and a divider. CONFIRMED products, INFERRED array gain.

---

## 2. Ku-band satellite dishes (0.8–1.2 m) reusable at 2.4 GHz

**Why a Ku dish works at 2.4 GHz.** A consumer Ku RX dish is built surface-accurate for
10.7–12.75 GHz (λ/20 ≈ 1.2 mm). At 2.4 GHz (λ/20 ≈ 6.25 mm) it is **~5× over-accurate**, so
the Ruze surface-error loss is < 0.05 dB and the reflector behaves as a near-perfect 2.4 GHz
aperture. Confirmed dish-family numbers below.

**TX vs RX (READ THIS).** Every dish in this section is a *consumer satellite-TV reflector*
shipped with a **receive-only LNB**. The **reflector itself is passive aluminium alloy** — it
transmits fine at 2.4 GHz and **is suitable for TX at 2.4 GHz**, provided you (a) remove the
LNB and (b) fit your own 2.4 GHz feed at the focus (section 3). The "receive-only" flag applies
to the *supplied feed/LNB*, not to the dish. This is the whole basis of the two-band plan in
`docs/analysis/dualband-single-dish.md`.

### B1 — Gibertini OP100SE (≈1.0 m) — the reference candidate
- **Vendor:** hm-sat shop (DE) · **Price:** €143.90
- **URL:** https://www.hm-sat-shop.de/gibertini-sat-antenne-100cm-se-profi-serie-sat-spiegel-schuessel-alu-anthrazit/12615-001
- **Reflector:** 97 × 104 cm outer, **94 × 101 cm working surface** · aluminium · 1.2 mm sheet
- **Efficiency:** 70 % · **Gain:** 39.0 dB @ 10.7 GHz / 39.7 @ 11.7 / 40.5 @ 12.75 GHz
- **Cross-pol:** 28 dB · **Sidelobe suppression:** 24 dB · **Noise temp:** 38 K @ 30° elevation
- **Feed geometry (KEY):** offset feed · **F/D = 0.66** · −3 dB aperture angle 1.70° ·
  offset correction angle 21° · **required feed illumination 70°** (±35°) · feed-holder bore 40 mm
  (23 mm option)
- **Mount:** mast 30–90 mm, Quick-Fix mast bracket, integral elevation scale
- **Wind load (KEY):** **91 kg @ 120 km/h (33.3 m/s)** — scaling by v² gives ≈ 33 kg ≈ **320 N
  at 20 m/s**, which matches the analysis' 330 N solid-dish figure.
- **Mass:** ~10 kg · **Temp:** −30…+70 °C
- **2.4 GHz suitability:** TX-capable reflector; at 2.4 GHz ≈ **25–27 dBi** (η 0.6).
- **Status:** CONFIRMED (vendor page technical-data block)

### B2 — Gibertini 85 SE Profi (0.85 m)
- **Vendor:** hm-sat shop (DE) · **Price:** €104.90
- **URL:** https://www.hm-sat-shop.de/gibertini-sat-antenne-85cm-se-profi-serie-sat-spiegel-schuessel-alu-weiss/11700-009
- Same SE Profi construction (offset, double-frame feed arm). f/D and wind load not printed on
  this page → `TODO(unverified)`; expect the same OP-series f/D ≈ 0.66 family value.
- **Status:** CONFIRMED price/Ø; f/D + wind TODO

### B3 — Gibertini 75 SE Profi (0.75 m)
- **Vendor:** hm-sat shop (DE) · **Price:** €94.90
- **URL:** https://www.hm-sat-shop.de/gibertini-sat-antenne-75cm-se-profi-serie-sat-spiegel-schuessel-alu-anthrazit/11701-001
- **Status:** CONFIRMED price/Ø; f/D + wind TODO

### B4 — Kathrein CAS 90 (0.90 m, premium)
- **Vendor:** hm-sat shop (DE) · **Price:** €249.00
- **URL:** https://www.hm-sat-shop.de/kathrein-cas-90-gr-sat-antenne-multifeedfaehig-graphit-grau/10210-003
- **Reflector diameter:** 90 cm · powder-coated aluminium · **offset feeding** (vendor text
  “Optimale elektrische Daten … durch Offset-Speisung”) · multifeed-capable
- Supplied: reflector, feed-system holder, mast bracket; stainless fixings; 8 cable clips;
  patented swivelling multifeed plate; elevation scale; fully pre-assembled.
- **TX at 2.4 GHz:** reflector is passive Al → TX-capable with your own feed; supplied
  feed-system holder is for LNB → replace.
- **Status:** CONFIRMED (vendor page description)

### B5 — Kathrein CAS 80 (nominally 0.8 m; reflector 75 cm)
- **Vendor:** hm-sat shop (DE) · **Price:** €169.00
- **URL:** https://www.hm-sat-shop.de/kathrein-cas-80-sat-antenne-graphit-gr-multifeedfaehig/11546-004
- Page states **“Reflektor Durchmesser 75 cm”**; offset feeding; TÜV-tested; multifeed-capable.
- **Status:** CONFIRMED price/Ø; note the nominal-vs-actual 80/75 cm discrepancy.

### B6 — Used / second-hand dishes (DE, cheap)
Used 90 cm offset Ku dishes are abundant and cheap; ideal for a prototype since surface
accuracy is over-specified anyway.
- **Kleinanzeigen search (used, DE):**
  https://www.kleinanzeigen.de/s-suchanfrage.html?keywords=sat+sch%C3%BCssel+90cm
- **Example confirmed listing** — “Kathrein CAS 90 Sat-Schüssel 90cm SatAn Spiegel”, **€50**
  (listing price meta `content="50.00"`):
  https://www.kleinanzeigen.de/s-anzeige/kathrein-cas-90-sat-sch%C3%BCssel-90cm-satan-spiegel/3524169716-175-8410
- Other confirmed used listings seen: Hirschmann 90 cm, Humax Offset 90, Durline 90 cm,
  Maximum 90 cm (prices vary; per-listing price `TODO(unverified)` unless opened).
- **eBay.de:** reachable in a browser but returned HTTP 403 to scripted fetch — search
  https://www.ebay.de/sch/i.html?_nkw=sat+sch%C3%BCssel+90cm manually.
- **Status:** CONFIRMED listing + one confirmed price; bulk per-item prices TODO.

> **1.2 m option.** The largest dish hm-sat lists in this family is the ~1.0 m Gibertini.
> A **confirmed 1.2 m reflector** is the RF Hamdesign mesh dish kit in section 4 (1.2 m,
> F/D 0.45). If a *solid* 1.2 m offset Ku dish is required, Gibertini OP120 / Fuba DAA 120
> class exists but a vendor page was not confirmed here → `TODO(unverified)`.

---

## 3. 2.4 GHz feeds that match the dish's f/D

**The matching rule.** A dish feed must illuminate the *rim angle* the reflector subtends at
the focus. For a paraboloid the geometric full subtended angle is

```
θ_sub = 2 · atan( 1 / (4 · f/D) )
```

| f/D | θ_sub (full, geometric) | Typical feed pattern needed |
|----:|------------------------:|-----------------------------|
| 0.35 | 71.1° | very wide feed |
| 0.40 | 64.0° | wide feed |
| **0.45** | **58.1°** | **RF Hamdesign feeds are specified for this** |
| 0.50 | 53.1° | medium feed |
| 0.60 | 45.2° | narrow feed |
| **0.66** | **41.5°** | **Gibertini OP100SE (needs a narrow feed)** |

> **Reconcile with the Gibertini page.** The vendor quotes a **“required feed illumination:
> 70°”** for the OP100SE (f/D 0.66). That is the feed's *rated illumination angle* (typically
> the −10 dB figure, which is wider than the geometric rim angle). Both statements are
> consistent in direction: the Gibertini needs a **narrower-pattern feed than a deep F/D 0.45
> dish**. **Match the feed's stated f/D to the dish's f/D.** The clean, self-consistent pairing
> is **RF Hamdesign mesh dish (F/D 0.45) + RF Hamdesign feed (F/D 0.45)**.

**Scale check (why feeds at 433 MHz are hard):** at 2.4 GHz λ/2 ≈ 62.5 mm. The same 62.5 mm
element is **0.09 λ at 433 MHz** — electrically tiny, with a broad, near-omni pattern that
cannot form the ~58–70° pencil a dish needs. This is why the 433 band uses a Yagi (section 1),
not the dish feed. See `docs/analysis/dualband-single-dish.md` §4.

### C1 — RF Hamdesign HORN-13 S-band horn feed  ← primary 2.4 GHz feed
- **Vendor:** RF Hamdesign B.V. (NL) · **Price:** quote (“Email for price quote” in the
  Oct-2026 price list) · **P/N:** `HORN-13` (2.3–2.4 GHz single-pol), `HORN-13/DUAL`,
  `HORN-13/CUSTOM` (tuneable 2.0–2.5 GHz, specify centre freq.)
- **URL:** https://www.rfhamdesign.com/products/dish-feeds/single-band-dish-feed/index.php
- **Spec:** horn, **N-female**, linear H or V (or dual H&V), return loss > 25 dB, usable BW
  100 MHz (RL > 15 dB), **50 Ω**, **RF power 1000 W**, **F/D 0.45 (prime focus)**, waterproof,
  **460 g**, supplied with a network-analyser plot · clamp CLX1
- **TX at 2.4 GHz:** **yes — rated 1000 W**, explicitly a TX/RX dish feed.
- **Status:** CONFIRMED (vendor page + Oct-2026 price list)

### C2 — RF Hamdesign FPF RS-ONE ring feed (tuneable 0.9–3.4 GHz)
- **Vendor:** RF Hamdesign (NL) · **Price:** **€185.00** (price list, incl. Dutch VAT)
- **URL:** https://www.rfhamdesign.com/products/dish-feeds/single-band-dish-feed/index.php
  (FPF RS-ONE also listed at https://www.rfhamdesign.com/downloads/rf-hamdesign-pricelist.pdf)
- **Spec:** single-band ring dish feed, **tuneable to any centre frequency 900–3400 MHz**
  (100 MHz usable BW), H or V polarisation, **N-female**, F/D 0.45, mount with CLX-01 clamp
- **Use:** one part covers both 1296 MHz and 2320 MHz (order two, or the dual-band R2313 below).
- **TX at 2.4 GHz:** TX/RX (ring feed, expected 1 kW class — exact power `TODO(unverified)`).
- **Status:** CONFIRMED (price list)

### C3 — RF Hamdesign LH-13XL helix feed (2.1–2.7 GHz, circular)
- **Vendor:** RF Hamdesign (NL) · **Price:** **€220.00** (price list, incl. VAT)
- **URL:** https://www.rfhamdesign.com/downloads/rf-hamdesign-pricelist.pdf
- **Spec:** **LHCP or RHCP helix** dish feed, **2.1–2.7 GHz**, **N-connector**, F/D 0.45,
  needs clamp CLX1. (Other frequencies available.)
- **TX at 2.4 GHz:** TX/RX helix.
- **Status:** CONFIRMED (price list)

### C4 — RF Hamdesign LH-ISS helix feed (2.4–2.5 GHz, circular)
- **Vendor:** RF Hamdesign (NL) · **Price:** **€220.00** (price list, incl. VAT)
- **URL:** https://www.rfhamdesign.com/downloads/rf-hamdesign-pricelist.pdf
- **Spec:** LHCP helix dish feed **2.4–2.5 GHz**, needs CLX1 clamp. Purpose-built for the
  ISS HAM TV downlink band, i.e. squarely a 2.4 GHz dish feed.
- **Status:** CONFIRMED (price list)

### C5 — RF Hamdesign CIR-2320 dual-mode circular feed
- **Vendor:** RF Hamdesign (NL) · **Price:** quote · **URL:** price list (above)
- **Spec:** dual-mode **LHCP/RHCP** dish feed tuned at **2320 MHz**, RX & TX, N-female,
  clamp CLX-06 (**€199.00**).
- **Status:** CONFIRMED (price list)

### C6 — Feed clamps / brackets
- **CLX1** clamp (horn/helix/ring feed to a 3-leg dish support): **€46.00**
- **CLX2**: **€47.00** · **CLX-06** (CIR-2320, CNC milled, 4-leg): **€199.00**
- **URL:** https://www.rfhamdesign.com/downloads/rf-hamdesign-pricelist.pdf
- **Status:** CONFIRMED

### C7 — Wi-Fi-grid-style 2.4 GHz antennas (alternative to a repurposed Ku dish)
If a repurposed Ku dish + feed is not wanted, an off-the-shelf 2.4 GHz grid/dish is an
alternative with similar gain. These are **CONFIRMED model families but the exact 2026 prices
were not verifiable here** (vendor pages are Cloudflare/JS-gated; Amazon listing pages
bot-walled) → prices `TODO(unverified)`.
- **TP-Link TL-ANT2424B** — 2.4 GHz, **24 dBi grid**, N-female, ±c. 10° beam. Manufacturer:
  https://www.tp-link.com/ (product page is JS-gated to scripted fetch); search
  “TL-ANT2424B” on a DE reseller to price. `TODO(unverified)` for price.
- **TP-Link TL-ANT2415D** — 2.4 GHz, 15 dBi panel/reflector. `TODO(unverified)` price.
- **Ubiquiti AirGrid M2 (AGM2)** — 2.4 GHz grid, 14/17/20 dBi variants, includes an integrated
  feed. Ubiquiti store: https://store.ui.com/ · `TODO(unverified)` price.
- **Ubiquiti PowerBeam M2-400** — 2.4 GHz, 18 dBi parabolic dish with integrated feed.
  `TODO(unverified)` price.
- **Cantenna (2.4 GHz):** no verified *purchasable* 2.4 GHz cantenna was found; it is a
  well-documented DIY build (a waveguide can + probe). Marked as a **DIY route**, not a
  BOM line → `TODO(unverified)` for any commercial product.
- **L-com HG2424G** (24 dBi 2.4 GHz grid, N-female) — the L-com product page loads via JS
  (spec table not in the HTML fetched), so gain/connector are confirmed by the product title
  but **price/specs** → `TODO(unverified)`. https://www.l-com.com/

---

*(Sections 4–6 continue below — 433 mesh dish, positioners, coax.)*
