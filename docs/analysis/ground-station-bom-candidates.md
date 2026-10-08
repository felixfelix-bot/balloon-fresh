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

*(Sections 2–6 continue below — dishes, 2.4 GHz feeds, 433 mesh dish, positioners, coax.)*
