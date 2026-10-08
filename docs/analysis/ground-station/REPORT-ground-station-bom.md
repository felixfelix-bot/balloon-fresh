# REPORT — ground-station BOM candidates

**Branch:** `design/ground-station-bom` (off `github/main` @ `09e1b69`).
**Deliverable:** `docs/analysis/ground-station-bom-candidates.md`.
**Scope:** sourcing only — real vendors, real URLs, real prices. Nothing ordered.

## What was produced
A single analysis doc covering all six requested categories, with a summary table plus per-item
detail (vendor, product, URL, price, gain, connector, wind rating, mass, TX-suitability, status).
Every price/spec carries a source URL; unverifiable figures are marked `TODO(unverified)`.

## Confirmed coverage
- **433 MHz Yagis (9 products, 7→18 dBi):** Sirio WY 400-3N/6N/10N, Diamond A-430S10R/A-430S15R,
  FlexaYagi FX 7015V/7044/7044-4/7073. All DE (Funktechnik Bielefeld). Plus a stacked-pair array
  route (Sirio supports "stacked and bayed array") and a divider category at rfhamstore.
- **Ku dishes 0.8–1.2 m (6):** Gibertini OP100SE (f/D 0.66, **91 kg @120 km/h** wind, 10 kg),
  Gibertini 85/75 SE, Kathrein CAS 90/80 (all hm-sat, DE), plus used 90 cm dishes on Kleinanzeigen
  (one confirmed at €50). TX-capable reflector vs receive-only LNB clearly flagged.
- **2.4 GHz dish feeds (5) + Wi-Fi-grid alternatives:** RF Hamdesign HORN-13 (F/D 0.45, N-f,
  1000 W, TX-capable), RS-ONE (€185), LH-13XL/LH-ISS (€220), CIR-2320; CLX1/CLX-06 clamps.
  Wi-Fi-grid models named (TL-ANT2424B, AirGrid M2, PowerBeam M2, L-com HG2424G) with prices TODO.
- **433 mesh dish (purchasable + DIY):** RF Hamdesign FPD mesh kits 1.0/1.2/1.5/1.9 m (F/D 0.45,
  6 mm mesh; 1.2 m → **25.2 dBd ≈ 27.4 dBi @ 2320 MHz**, 4.8 kg), plus brackets and a DIY mesh route.
- **AZ/EL positioners with wind ratings (9+):** Yaesu G-5500DC (1.00/0.50 m²), G-450CDC, G-1000DXC
  (2.20/0.74 m²), G-2800DXC (3.00/1.00 m²); SPID RAS, **BIG-RAS** ("dishes up to 5 m"), SPX-01/02/03,
  SPX-06 slew drive (**716 Nm, IP65**).
- **Coax (5):** Ecoflex 15 (1.62 dB/10 m @2.4 GHz, 0.61 @433), Ecoflex 10, Airborne 10 (LMR-400
  class), H2010 EVO, Aircell 7 — all from vendor attenuation tables; N/SMA connector prices.

## Key findings
1. A **1.2 m RF Hamdesign mesh dish is a confirmed, purchasable ~27.4 dBi 2.4 GHz dish** at €387
   (incl. VAT), with an **exact f/D 0.45 match** to the RF Hamdesign feeds — the self-consistent
   2.4 GHz uplink stack.
2. The **Gibertini OP100SE** is the best-documented repurposed Ku dish: **f/D 0.66, 70° feed
   illumination, 91 kg wind load @120 km/h** (= ~320 N @20 m/s, matching the analysis' 330 N).
3. **The Yaesu G-5500DC is NOT adequate for a 1.2 m dish** on a mast (0.50 m² mast rating). A
   1.0–1.2 m dish needs **SPID BIG-RAS** (€1,775) or an SPX-06 slew drive (€5,487).
4. At 433 MHz the mesh-hole limit is **69 mm (λ/10)** → hardware-store mesh is electrically solid
   and low-wind; the mesh dish is a valid 433 element (~12 dBi at 1.2 m).
5. **Indicative reference BOM ≈ €2,518** (new dish + feed + Yagi + SPID BIG-RAS + coax);
   cheap prototype ≈ €1,402.

## Issues / limitations
- Search engines (Bing/DDG/Searx) bot-block curl; discovery was done by fetching vendor category
  and site-search pages directly. WiMo subcategories, conrad.de, tp-link.com, L-com and
  timesmicrowave.com are Cloudflare/JS/403-gated.
- 13 explicit `TODO(unverified)` items are listed in the doc §8 (connector types, some f/D + wind
  values, Wi-Fi-grid prices, SPID wind areas, LMR-400 own datasheet, etc.).

## Process
- 7 milestone commits, each pushed to **github first, then ngit separately** (never `--atomic`).
- `PROGRESS.md` and `REPORT.md` are gitignored (`.gitignore:67/68`) → added with `git add -f`.
