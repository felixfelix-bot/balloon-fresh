# PROGRESS — ground-station BOM sourcing (branch design/ground-station-bom)

**Task:** source purchasable ground-station antenna hardware for the balloon ground station;
write `docs/analysis/ground-station-bom-candidates.md`.

**Milestones (each committed + pushed to github then ngit separately):**

- [x] M1 — repo/worktree setup; 433 MHz Yagi section (9 confirmed products, 4 vendors-worth of
      gains 7→18 dBi, Sirio/Diamond/FlexaYagi, + stacked-pair/divider path). COMMITTED.
- [x] M2 — Ku-band dishes 0.8–1.2 m (Gibertini OP100SE/85/75, Kathrein CAS 80/90, used on
      Kleinanzeigen). COMMITTED.
- [x] M3 — 2.4 GHz feeds matched to dish f/D (RF Hamdesign HORN-13 / RS-ONE / LH-13XL /
      LH-ISS / CIR-2320) + Wi-Fi-grid alternatives. COMMITTED.
- [x] M4 — 433 MHz mesh dish (RF Hamdesign mesh kits) + DIY mesh materials. COMMITTED.
- [x] M5 — AZ/EL positioners with wind ratings (Yaesu family + SPID/SPX family). COMMITTED.
- [x] M6 — low-loss coax (Ecoflex 10/15, Airborne 10, H2010 EVO, Aircell 7 + connectors). COMMITTED.
- [x] M7 — recommended shortlist + indicative total; REPORT.md; final commit/push. COMMITTED.

**DONE.** All 7 milestones committed and pushed to github + ngit.

## Sourcing toolchain notes (reusable)
- Bing/DDG/Searx all bot-block curl → **fetch vendor sites directly** with a browser UA and
  `curl --compressed` (reichelt returns gzip). Helper: `/tmp/src/fetch.py` (HTML→text),
  `/tmp/src/bing.py`, `/tmp/src/px.py`, `/tmp/src/desc.py`, `/tmp/src/coax.py`.
- Cloudflare-gated: wimo.com subcategories, conrad.de, tp-link.com. Fetchable: funktechnik-
  bielefeld.de, pmr-funkgeraete.de, hm-sat-shop.de, kabel-kusch.de, rfhamdesign.com,
  rfhamstore.com, dxengineering.com (spec tables), kleinanzeigen.de.
- Shopware product pages carry `itemprop="price" content="…"` — reliable price scrape.

## Key numbers gathered
- 1.2 m RF Hamdesign mesh dish: **25.2 dBd (~27.4 dBi) @ 2320 MHz**, 8.1° beamwidth, 4.8 kg,
  6 mm mesh → matches the 27 dBi 2.4 GHz target.
- Gibertini OP100SE: **f/D 0.66, 70° feed illumination, 91 kg wind load @ 120 km/h**, 10 kg.
- Yaesu G-5500DC wind load: **1.00 m² (tower) / 0.50 m² (mast)** → marginal for a 1.2 m dish.
- Yaesu G-2800DXA: **3.00 m² / 1.00 m²**; SPID BIG-RAS handles dishes ≤5 m.
