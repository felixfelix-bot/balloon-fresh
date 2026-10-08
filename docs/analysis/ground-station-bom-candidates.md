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

## 4. 433 MHz mesh / grid dish options + DIY route

**Mesh-hole limit at 433 MHz.** A perforated/mesh reflector behaves as solid while the hole
pitch is well under ~λ/10. At 433 MHz, λ = 692 mm → **λ/10 = 69 mm**. That is *coarse*: any
practical mesh (window screen ≈ 1–2 mm, welded wire ≤ 25 mm) is 3–70× finer than required, so
a mesh dish at 433 MHz is effectively a solid reflector **and** has far lower wind load
(permeable). This is why a mesh dish is the right 433 MHz gain-element if a dish is wanted.

### D1 — RF Hamdesign Mesh Dish Kit, 1.2 m (FPD 1M2 KIT)  ← recommended 433 mesh dish
- **Vendor:** RF Hamdesign B.V. (NL) — webshop https://www.rfhamstore.com/ ·
  **Price:** **€387.20** incl. Dutch VAT (€320.00 excl. VAT) · **P/N:** `FPD 1M2 KIT`
- **URL:** https://www.rfhamdesign.com/products/parabolicdishkit/12meterdishkit/index.php
  (price: https://www.rfhamdesign.com/downloads/rf-hamdesign-pricelist.pdf)
- **Geometry:** 1.2 m diameter, **F/D 0.45 (prime focus)** · supplied as a DIY rivet kit:
  pre-drilled ribs, CNC-milled aluminium hub, **6 mm square galvanised-steel mesh**, rivets,
  all nuts/bolts/washers, heavy-duty mast clamp (max 52 mm), **3-leg feed support**
- **Mesh:** standard 6 mm square mesh → **usable to 6 GHz**; optional **2.8 mm mesh** (+€48)
  → usable to 11 GHz
- **Mass:** 4.8 kg (6 mm mesh)
- **Gain (vendor table, 6 mm mesh):**
  | Freq | Gain (dBd) | Gain (dBi) | −3 dB angle |
  |-----:|-----------:|-----------:|------------:|
  | 1000 MHz | 17.1 | 19.3 | 16.8° |
  | 1296 MHz | 20.3 | 22.5 | 14.4° |
  | **2320 MHz** | **25.2** | **27.4** | **8.1°** |
  | 3456 MHz | 28.4 | 30.6 | 5.4° |
- **2.4 GHz use:** **25.2 dBd ≈ 27.4 dBi** — this *is* a home-buildable 27 dBi 2.4 GHz mesh
  dish, matching the 2.4 GHz uplink target. Pair with the RF Hamdesign HORN-13 / RS-ONE feed
  (both F/D 0.45 → exact match, section 3).
- **433 MHz use:** 433 MHz is not tabulated. Scaling the aperture |G| ∝ (D/λ)² from the
  1000 MHz row (17.1 dBd) down to 433 MHz gives 20·log₁₀(433/1000) = −7.3 dB →
  **≈ 9.8 dBd ≈ 12 dBi** (INFERRED, aperture scaling only; the mesh is electrically solid).
  This matches the analysis' 12.5 dBi figure in `docs/analysis/dualband-single-dish.md` §3.2.
- **Status:** CONFIRMED (vendor page + price list); 433 MHz gain INFERRED.

### D2 — RF Hamdesign Mesh Dish Kit, 1.5 m (FPD 1M5 KIT)
- **Price:** **€499.73** incl. VAT (€413.00 excl.) · same F/D 0.45, 6 mm mesh
- **URL:** https://www.rfhamdesign.com/products/parabolicdishkit/15meterdishkit/index.php
- Gain scales +20·log₁₀(1.5/1.2) = +1.94 dB vs D1 → **~27.2 dBd @ 2320 MHz**,
  **~11.7 dBd ≈ 13.9 dBi @ 433 MHz** (INFERRED).
- **Status:** CONFIRMED price; gains INFERRED by scaling

### D3 — RF Hamdesign Mesh Dish Kit, 1.9 m (FPD 1M9 KIT)
- **Price:** **€901.45** incl. VAT (€745.00 excl.) · F/D 0.45, 6 mm mesh, Max 6 GHz
- **URL:** https://www.rfhamdesign.com/products/parabolicdishkit/19meterdishkit/index.php
- Gain scales +20·log₁₀(1.9/1.2) = +4.0 dB vs D1 → **~29.2 dBd ≈ 31.4 dBi @ 2320 MHz**,
  **~13.8 dBd ≈ 15.9 dBi @ 433 MHz** (INFERRED). **This is the cheapest confirmed way to get
  433 MHz dish gain into the 16–17 dBi class** if a dish (not Yagi) is wanted.
- **Status:** CONFIRMED price; gains INFERRED by scaling

### D4 — Brackets / accessories (RF Hamdesign)
- **BR-50** fixed-elevation dish bracket (0–90° elevation, dishes ≤1.9 m, 2.5 kg): **€135.00**
- **4TH-LEG** 4th feed-support leg (needed for 4-leg feed brackets): **€39.93**
- **BR-08** adaptor plate to mount a mesh dish (≤1.9 m) on an SPX-01/SPX-02 rotor: **€38.00**
- **CLX-10** adaptor for mast >55 mm: quote
- **URL:** https://www.rfhamdesign.com/downloads/rf-hamdesign-pricelist.pdf
- **Status:** CONFIRMED

> **Not available / discontinued:** RF Hamdesign mesh dish kits **2.4 m, 3.0 m and 4.5 m are
> “Out of production”** per the Oct-2026 price list. The 1.0 m (`FPD 1M0 KIT`, €342.43 incl.)
> is available if a smaller dish is wanted.

### D5 — DIY mesh route (cheapest, low wind)
Because the 433 MHz hole limit is 69 mm, ordinary hardware-store mesh is a valid reflector.
- **Reflector conductor options:** aluminium window screen (Fliegengitter/Alu-Gittergewebe),
  welded/galvanised wire mesh (Schweißgitter) with ≤ 25 mm squares, aluminium insect mesh.
- **Frames / support:** the mesh needs a parabolic former — either the RF Hamdesign rib kit
  (D1–D3, buy without mesh is not offered) or a hand-formed rib set. Aluminium **tape** on a
  moulded former is the alternative conductor.
- **Suppliers (DE):** Bauhaus (https://www.bauhaus.info/), OBI (https://www.obi.de/),
  Hornbach (https://www.hornbach.de/), Amazon.de (search “Fliegengitter Aluminium” /
  “Schweißgitter Alu”). **Prices for specific mesh rolls → `TODO(unverified)`** (retail sites
  were Cloudflare/JS-gated or the pages bot-walled during this pass).
- **Design tolerance check:** at 433 MHz the reflector RMS tolerance is λ/20 = **34.6 mm**
  (see `ground-station-dish.md` §2) → the mesh may sag centimetres and still be fine.
- **Status:** INGREDIENTS confirmed as real product categories; specific prices TODO.

> **Purchasable "433 MHz mesh dish" summary:** the only *confirmed, purchasable, spec'd*
> mesh dish found is the **RF Hamdesign FPD series** (D1–D3). General-purpose consumer
> 433 MHz mesh dishes are not a retail product; the practical alternatives are (a) an RF
> Hamdesign mesh kit, or (b) a repurposed Wi-Fi 2.4 GHz grid (whose mesh is far finer than
> 433 MHz needs) with the feed swapped.

---

## 5. AZ/EL positioners / rotators with wind-load ratings

**How rotators are rated.** Commercial rotators are sold with a **maximum wind-load antenna
area (m²)** — the projected area of antenna they can hold in a survival wind. Yaesu quotes it
in **sq ft** (and labels "inside tower" vs "mast mounted"); SPID/SPX quote a load/area in their
datasheets. Because the ground station needs **both azimuth and elevation**, only the AZ+EL
units are direct candidates — the pure-AZ units are listed because they are the cheap path if
one axis is handled another way.

**Reference wind load for the dish (from section B1):** a 1.2 m dish ≈ **1.13 m² geometric**
(π·0.6²) and ~1.4 m² effective with a drag factor; the Gibertini OP100SE is rated 91 kg @ 120 km/h
≈ 320 N at 20 m/s. So **any rotator must be able to hold ≈1.1–1.4 m² minimum.**

### Yaesu family (prices: Funktechnik Bielefeld DE; wind ratings: DX Engineering US)

| Model | Axes | Wind (tower) | Wind (mast) | Price | URL |
|-------|------|-------------:|------------:|------:|-----|
| **G-5500DC** | AZ+EL | **1.00 m²** | **0.50 m²** | €949.00 | price: https://www.funktechnik-bielefeld.de/yaesu-g-5500dc-satellitenrotor · wind: https://www.dxengineering.com/parts/ysu-g-5500dc |
| G-450CDC | AZ+EL | 1.00 m² (G-450A) | 0.50 m² | €359.00 | price: https://www.funktechnik-bielefeld.de/yaesu-g-450cdc-antennenrotor-mit-steuergeraet · wind: https://www.dxengineering.com/parts/ysu-g-450a |
| G-1000DXC | AZ | 2.20 m² (G-1000DXA) | 0.74 m² | €529.00 | price: https://www.funktechnik-bielefeld.de/yaesu-g-1000dxc-antennenrotor-mit-stecker/ohne-kabel · wind: https://www.dxengineering.com/parts/ysu-g-1000dxa |
| G-2800DXC | AZ | 3.00 m² (G-2800DXA) | 1.00 m² | €1,049.00 | price: https://www.funktechnik-bielefeld.de/yaesu-g-2800dxc-antennenrotor-mit-stecker/ohne-kabel · wind: https://www.dxengineering.com/parts/ysu-g-2800dxa |
| G-800DXA | AZ | 2.00 m² | 0.74 m² | TODO | wind: https://www.dxengineering.com/parts/ysu-g-800dxa |

- **G-5500DC (E1)** is the classic affordable **AZ+EL** satellite rotator (funktechnik text: two
  rotors G-400 + G-550 stacked with a supplied U-bracket; includes controller).
  **IMPORTANT:** its **mast-mounted** wind rating is only **0.50 m²** — below a 1.2 m dish.
  A 1.2 m dish would have to be **tower-mounted** (rating 1.00 m², still marginal) or the
  mount stiffened. **Verdict: G-5500DC is fine for the 0.75–0.85 m dishes (B2/B3) and for a
  small mesh dish, NOT for a 1.0–1.2 m dish on a mast.**
- **E2 G-450CDC** — same wind class, cheaper; light AZ+EL.
- **E3/E4** are **AZ-only**; they need a separate elevation axis.
- The DXE pages state the wind **area** but **not the reference wind speed** → `TODO(unverified)`
  for the survival wind speed (Yaesu's own manual quotes a reference; not seen on these pages).
- **Status:** prices CONFIRMED (funktechnik), wind ratings CONFIRMED (DXE), reference wind speed TODO.

### SPID / SPX family (RF Hamdesign NL — prices from Oct-2026 price list, incl. Dutch VAT)

| Model | Axes | Rating / torque | Price | URL |
|-------|------|-----------------|------:|-----|
| SPID RAU | AZ | light AZ | €719.00 | https://www.rfhamdesign.com/downloads/rf-hamdesign-pricelist.pdf |
| SPID RAK | AZ | AZ | €749.00 | price list |
| SPID BIG-RAK | AZ | heavy AZ | €1,203.95 | price list |
| **SPID RAS** | **AZ+EL** | AZ&EL, standard | **€1,260.82** | price list + https://www.rfhamdesign.com/products/spid-antenna--rotator/ras-az--el-rotor/index.php |
| **SPID BIG-RAS** | **AZ+EL** | **“dishes up to 5 m”**, 22 kg, double worm drive | **€1,775.00** | https://www.rfhamdesign.com/products/spid-antenna--rotator/big-ras-az--el-rotor/index.php |
| SPID RAEL | EL only | elevation axis | €725.00 | price list |
| **SPX-01/MD-03** | **AZ+EL** | light duty, 0.5°/step | **€1,132.00** | https://www.rfhamdesign.com/products/spx-antenna-rotators/spx-01-az--el/index.php |
| SPX-02/MD-03 | AZ+EL | medium duty | €1,249.00 | https://www.rfhamdesign.com/products/spx-antenna-rotators/spx-02-az--el/index.php |
| SPX-03/MD-03 | AZ+EL | heavy duty | €1,629.00 | price list |
| SPX-362 | AZ | medium AZ | €757.00 | price list |
| **SPX-06/AZ&EL/ABS** | **AZ+EL** | **716 Nm**, IP65, absolute encoders, 0.1° | **€5,487.35** | price list |
| SPX-05/XY/ABS | X/Y | 716 Nm, IP65 | €5,517.60 | price list |

- **SPID BIG-RAS (E6)** — vendor states it **“will handle big systems, array's, dishes up to
  5 Meter”**, weight 22 kg, azimuth 360°±180°, elevation 180°±20°, 0.5° resolution, magnetic
  reed 0.5°/pulse, **double metal worm gear drive for holding position in the wind**. Comes
  with Rot2Prog/MD-03 controller, USB track interface, emulates Yaesu GS-232 / Hy-Gain / Orion
  protocols. **This is the confirmed heavy AZ+EL option for a 1.0–1.2 m dish.**
- **SPX-01/02 (E7/E8)** are light/medium AZ+EL with 0.5°/step; SPX-06 (E9) is a **slew drive**
  with a stated **716 Nm** holding torque and IP65 — the robust option.
- **Controller/power:** all SPID/SPX include a controller; standalone MD-03 controller €526.35,
  PS-03 PSU €482.00, PSU-1228 €129.00, Ethernet module €108.00 (price list).
- **Wind-load area (m²) for SPID/SPX:** not printed on the product pages; the manufacturer
  datasheets (`/downloads/spid-bigras-specifications.pdf` etc.) returned **HTTP 466 Access
  Forbidden** to scripted fetch → **`TODO(unverified)`**. The vendor's *load statement*
  (“dishes up to 5 m” for BIG-RAS) is the confirmed substitute.
- **Status:** prices CONFIRMED; BIG-RAS load statement CONFIRMED; SPID/SPX wind area TODO.

### Recommendation logic (see §7 shortlist)
- **1.2 m dish + AZ/EL:** **SPID BIG-RAS** (€1,775) or **SPX-06 slew drive** (€5,487). The
  G-5500DC (€949) is **not** rated for it on a mast.
- **0.75–0.85 m dish + AZ/EL:** **Yaesu G-5500DC** (€949) on a tower, or **SPX-01** (€1,132).
- **Cheap AZ-only + separate elevation:** G-1000DXC (€529, 2.2 m² tower) is the affordable
  AZ workhorse; elevation would need a linear actuator or SPID RAEL (€725).

---

## 6. Low-loss coax

**Band split matters.** The ground station has two RF runs: the **2.4 GHz uplink** (dish feed,
where loss is worst and the run should be as short as possible — ideally put the PA at the
dish and run only DC/LAN up the mast) and the **433 MHz downlink** (Yagi; loss is ~2.5× lower
per metre, so a longer run is tolerable). All figures below are the **vendor's own attenuation
table** (`Dämpfung dB/100 m`), converted to **dB/10 m**.

Vendor: **Kabel-Kusch (DE)**, https://www.kabel-kusch.de/ — every row below was read from the
product page's attenuation table.

| Cable | Ø | Loss @433 MHz | Loss @2.4 GHz | Price/m | Product URL |
|-------|---:|--------------:|--------------:|--------:|-------------|
| **Ecoflex 15** | 14.6 mm | **0.61 dB/10 m** | **1.62 dB/10 m** | €13.60 | https://www.kabel-kusch.de/produkt/ecoflex-15/17 |
| **Ecoflex 10** | 10.3 mm | 0.85 dB/10 m | 2.24 dB/10 m | €6.70 | https://www.kabel-kusch.de/produkt/ecoflex-10/14 |
| **Airborne 10** (LMR-400 class) | 10.3 mm | 0.76 dB/10 m | 1.92 dB/10 m | €6.50 | https://www.kabel-kusch.de/produkt/airborne-10/2 |
| **H2010 EVO** | 10.3 mm | 0.81 dB/10 m | 2.08 dB/10 m | €6.50 | https://www.kabel-kusch.de/produkt/h2010-evo/601 |
| **Aircell 7** | 7.3 mm | 1.29 dB/10 m | 3.38 dB/10 m | €4.06 | https://www.kabel-kusch.de/produkt/aircell-7/4 |

**Raw vendor figures (dB/100 m), as printed:**
- Ecoflex 15: 432 MHz **6.10**, 2400 MHz **16.20**
- Ecoflex 10: 432 MHz **8.46**, 2400 MHz **22.42**
- Airborne 10: 430 MHz **7.60**, 2400 MHz **19.20**
- H2010 EVO: 430 MHz **8.10**, 2400 MHz **20.80**
- Aircell 7: 432 MHz **12.92**, 2400 MHz **33.82**

- **Status:** ALL CONFIRMED (vendor attenuation tables + listed per-metre price).
- **Note on the LMR-400 name:** *Airborne 10* is the Messi & Paoloni **LMR-400-class** 10.3 mm
  cable with a confirmed attenuation table; it is the practical LMR-400 substitute in the EU.
  LMR-400's own datasheet host (timesmicrowave.com) returned **HTTP 403** to scripted fetch →
  LMR-400's own published figure is `TODO(unverified)` here; use Airborne 10's confirmed numbers.
- **H100:** not stocked by kabel-kusch (the modern 10 mm equivalents H2010 EVO / Ecoflex 10 /
  Airborne 10 cover the same niche) → `TODO(unverified)`.

### Connectors (N-type, SMA) — Kabel-Kusch
| Connector | For cable | Price | URL |
|-----------|-----------|------:|-----|
| N-Stecker crimp 7 mm (N 7 cr) | H2007 / Aircell 7 / LMR-300 | €6.00 | https://kabel-kusch.de/kategorie/stecker/n-stecker/22 |
| N-Stecker crimp H155/HyperFlex 5 (N 155 cr) | 5.4 mm | €5.11 | https://kabel-kusch.de/kategorie/stecker/n-stecker/22 |
| N-Buchse solder 7 mm (UG 22-7 TA) | 7 mm | €6.85 | https://kabel-kusch.de/kategorie/stecker/n-stecker/22 |
| SMA-10 crimp | 10 mm cable | TODO(unverified) | https://kabel-kusch.de/produkt/sma-10/118 |

- Connector categories: **N** https://kabel-kusch.de/kategorie/stecker/n-stecker/22 ·
  **SMA** https://kabel-kusch.de/kategorie/stecker/sma-stecker/23
- The N-Stecker 7 mm price (€6.00) and N-Buchse 7 mm (€6.85) and N 155 cr (€5.11) are CONFIRMED
  from the category page; other sizes exist on the same page.

> **Practical cable plan.** 2.4 GHz dish run: **Ecoflex 15** (1.62 dB/10 m) if the run is long,
> else **Airborne 10 / Ecoflex 10** with the PA mounted at the feed. 433 MHz Yagi run: **Airborne 10
> or Aircell 7** is ample (≤0.8–1.3 dB/10 m). Use **N-type** throughout for the antenna/rotator
> ends (weatherproof) and **SMA** at the radio.

---

## 7. Recommended shortlist + indicative cost

### 7.1 2.4 GHz uplink (dish + feed) — pick ONE dish + ONE feed

| Option | Dish | Feed | Dish € | Feed € | Notes |
|--------|------|------|-------:|-------:|-------|
| **2.4-A (cheapest)** | used 90 cm Kathrein CAS 90 (Kleinanzeigen) | HORN-13 (quote) | ~50 | ~185 (RS-ONE priced proxy) | f/D must be matched to the feed; used → verify surface |
| **2.4-B (recommended)** | Gibertini OP100SE 97×104 cm, f/D 0.66 | HORN-13 / RS-ONE (F/D 0.45) + CLX1 €46 | 143.90 | 185 + 46 | documented f/D 0.66; feed slightly mismatched (needs ~70° illumination) |
| **2.4-C (matched, single vendor)** | RF Hamdesign FPD 1M2 1.2 m mesh, F/D 0.45 | HORN-13 (F/D 0.45, exact match) + CLX1 €46 | 387.20 | 185 + 46 | **exact f/D match**, 27.4 dBi @2.4 GHz, low wind; feed price is a quote |

Feed row detail: HORN-13 is quoted "Email for price quote"; the **FPF RS-ONE ring feed at €185.00**
is the *priced* confirmed stand-in (also F/D 0.45, N-female, tuneable 900–3400 MHz → covers
2320 MHz). LH-13XL / LH-ISS helix feeds are €220.00.

### 7.2 433 MHz downlink (Yagi) — pick ONE (or a stacked pair)

| Option | Product | Gain | Boom | Price | Fit |
|--------|---------|-----:|-----:|------:|-----|
| **433-short** | FlexaYagi FX 7015V | 12.4 dBi | 1.19 m | €125.00 | low wind, low gain |
| **433-mid (recommended)** | Sirio WY 400-10N | 14 dBi | 2.0 m | €155.00 | N-f, stackable, 400–470 MHz |
| **433-mid-alt (cheapest)** | Diamond A-430S15R | 14.8 dBi | 1.39 m | €74.50 | PL socket, 430–440 MHz |
| **433-high** | FlexaYagi FX 7044 | 16.6 dBi | 3.08 m | €164.00 | high gain, long boom |
| **433-array** | 2 × Sirio WY 400-10N + divider | ~17 dBi | 2 × 2.0 m | €310 + divider | per Sirio "stacked and bayed array" spec |

### 7.3 Positioner (AZ/EL) — pick ONE

| Option | Product | Wind rating | Handles | Price |
|--------|---------|-------------|---------|------:|
| **POS-light** | Yaesu G-5500DC | 1.00 m² tower / 0.50 m² mast | ≤0.85 m dish (tower) | €949.00 |
| **POS-medium** | SPID RAS AZ&EL | (datasheet TODO) | medium dishes | €1,260.82 |
| **POS-heavy (recommended for 1.0–1.2 m)** | SPID BIG-RAS AZ&EL | dishes up to 5 m (vendor) | 1.0–1.2 m dish | €1,775.00 |
| **POS-slew** | SPX-06 AZ&EL slew drive | 716 Nm, IP65 | heavy dish | €5,487.35 |

### 7.4 Coax

| Option | Product | 2.4 GHz loss | Price/m |
|--------|---------|-------------:|--------:|
| **CX-best** | Ecoflex 15 | 1.62 dB/10 m | €13.60 |
| **CX-recommended** | Airborne 10 (LMR-400 class) | 1.92 dB/10 m | €6.50 |
| **CX-cheap** | Aircell 7 | 3.38 dB/10 m | €4.06 |

### 7.5 Indicative reference BOM (one row per band, "recommended" picks)

| Line | Item | Qty | Unit € | Line € |
|------|------|----:|-------:|-------:|
| 2.4 GHz dish | Gibertini OP100SE (B1) | 1 | 143.90 | 143.90 |
| 2.4 GHz feed | RF Hamdesign HORN-13 (quote; RS-ONE €185 proxy) (C1/C2) | 1 | 185.00 | 185.00 |
| Feed clamp | RF Hamdesign CLX1 (C6) | 1 | 46.00 | 46.00 |
| 433 Yagi | Sirio WY 400-10N (A3) | 1 | 155.00 | 155.00 |
| Positioner | SPID BIG-RAS AZ&EL (E6) | 1 | 1,775.00 | 1,775.00 |
| Coax 2.4 GHz | Ecoflex 15, 5 m | 1 | 68.00 | 68.00 |
| Coax 433 MHz | Airborne 10, 15 m | 1 | 97.50 | 97.50 |
| N/SMA connectors | misc | ~8 | ~6 | ~48.00 |
| **Total (indicative, incl. Dutch/EU VAT where the vendor quotes it)** | | | | **≈ €2,518** |

**Cheap prototype variant** (used dish, small feeding, no heavy rotator):
used 90 cm Ku dish (~€50) + RS-ONE feed (€185) + CLX1 (€46) + Diamond A-430S15R (€74.50) +
**Yaesu G-5500DC only if dish ≤0.85 m on a tower** (€949) + Airborne 10 15 m (€97.50) ≈ **€1,402**.
> ⚠ The G-5500DC (0.50 m² mast rating) is **not** adequate for a 0.9–1.2 m dish on a mast; the
> cheap variant only balances if the dish is ≤0.85 m and tower-mounted.

---

## 8. Open items / TODO(unverified)

1. **FlexaYagi connector types** (A6–A9) — not printed on the vendor pages.
2. **FlexaYagi dBd gain claims** (14.4–15.8 dBd) are vendor figures; verify against manufacturer.
3. **Diamond A-430S15R connector** — not stated on the page.
4. **f/D + wind load for Gibertini 85/75 and Kathrein CAS 80/90** — not printed on the vendor pages.
5. **A *solid* 1.2 m offset Ku dish** (Gibertini OP120 / Fuba DAA 120 class) — no confirmed vendor
   page located; the confirmed 1.2 m is the RF Hamdesign mesh kit.
6. **433 MHz Yagi stacked-pair power divider** — the rfhamstore "70cm HAM Radio Dividers" category
   is confirmed to exist, but no individual divider price was read.
7. **Wi-Fi-grid antenna prices** (TL-ANT2424B, AirGuard M2, PowerBeam M2, L-com HG2424G) — pages
   were JS- or bot-gated; models confirmed, prices TODO.
8. **Priced 2.4 GHz cantenna** — none found; DIY only.
9. **DIY mesh material prices** (aluminium screen / welded wire) — retail sites gated.
10. **SPID/SPX wind-load area (m²)** — vendor datasheets returned HTTP 466; only the BIG-RAS
    "dishes up to 5 m" statement is confirmed.
11. **Yaesu wind-load reference wind speed** — the DX Engineering pages give the area but not the
    survival wind speed.
12. **LMR-400 own datasheet figure** — timesmicrowave.com returned HTTP 403; use Airborne 10's
    confirmed table as the LMR-400-class number.
13. **eBay.de** — 403 to scripted fetch; used-dish searching there is manual.

## 9. Method / reproduction

- Fetch helper used a browser User-Agent + `curl --compressed`; vendor pages that returned
  Cloudflare challenges (wimo.com subcategories, conrad.de, tp-link.com) are marked as gated.
- Prices: Shopware pages expose `itemprop="price" content="…"`; RF Hamdesign prices come from the
  **Oct-2026 price list PDF** at
  https://www.rfhamdesign.com/downloads/rf-hamdesign-pricelist.pdf (first column = EUR incl. 21 %
  Dutch VAT; second = EUR excl. VAT for EU businesses/export).
- **Search engines (Bing/DDG/Searx) bot-block curl** → discovery was done by fetching vendor
  category pages and site search endpoints directly.

*End of analysis.*
