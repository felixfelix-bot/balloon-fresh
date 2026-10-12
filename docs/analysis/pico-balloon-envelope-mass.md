# Pico-Balloon Envelope Mass — Yokohama Balloon 32-inch class

**Branch:** `analysis/pico-balloon-envelope-mass`
**Status:** Research note (research only — nothing ordered, nothing bought)
**Question it answers:** what does the Yokohama envelope actually weigh, what do the gas and the
attachments add, what does the pico-balloon community actually fly, and — under a **total-mass**
reading of a mass threshold — **how much payload mass is left** for a 32-inch-class Yokohama?

**Scope:** physical masses only. The *authoritative legal* position (German LuftVO / EU, and the
question of whether any threshold counts payload or total system mass) is established by the
sibling task in `docs/analysis/free-balloon-mass-threshold-DE.md` — this document does **not**
re-litigate the law. It supplies the numbers that task needs.

---

## 0. Source-quality legend

| Tag | Meaning |
|---|---|
| **MFR** | Stated by the manufacturer (Yokohama Balloon Co., Ltd.) on its own site/catalogue |
| **MEASURED** | First-hand value measured on a scale by a named community practitioner |
| **COMMUNITY** | Value published by a named practitioner/group from their own experience (may be measured or estimated — stated per row) |
| **DERIVED** | Arithmetic on the above; the arithmetic is shown inline |
| **TODO(unverified)** | Could not confirm against a source — **not invented** |

The manufacturer publishes **no mass figure at all** for the 32-inch sphere (see §1). Every mass
number below therefore comes from the community, and each is labelled with who measured it.

---

## 1. Which Yokohama models the pico-balloon community actually flies

The manufacturer is **Yokohama Balloon Co., Ltd. (横浜風船株式会社)**, Yokohama, Japan. Its export
shop is `yokohamaballoon.com` (Shopify). I pulled the whole catalogue (`/products.json`, 30
products, retrieved 2026-10-07).

**Findings (MFR):**

* The community flies the **32-inch spherical ("Sphere Balloon")** — the product the manufacturer
  sells as:
  * `Crystal Clear Sphere Balloon (32inch)：1bag(10pieces)` — slug
    `sphere-balloon32inch-1bag10pieces`; variant code **`（260601）`**; offered **With valve**
    and **No Valve** (the "no nozzle / valveless" version). URL:
    <https://yokohamaballoon.com/products/sphere-balloon32inch-1bag10pieces>
  * `Sphere Balloon(32inch)` (coloured / metallic) — slug `sphere-balloon32inch-1bag10pieces-1`
  * Older handle used widely in community posts:
    <https://yokohamaballoon.com/products/sphere-balloon32inch> (e.g. variant `41763086729369`)
* **Material (MFR):** "Nylon, Polyethylene" (a nylon/PE laminate — designed to *stretch*, unlike
  Mylar foil).
* **There is no 36-inch Yokohama sphere in the catalogue.** The sphere range on the manufacturer's
  own store runs **7 / 10 / 14 / 20 / 24 / 32 inch**; 32 inch is the largest. The "36-inch"
  balloons in circulation in the pico community are **other brands** — Qualatex 36" silver
  (33–37 g) and Chinese-clear 36" (38 g), Grabo silver 36" (44.5 g), SAG/Orbz 35" (46 g) — per the
  community comparison table in §2. **A "36-inch Yokohama" is, on the available evidence, a
  misnomer; do not size a design around one.**
* **Sizes are nominal.** The community treats the "32-inch" figure as the *nominal* size and then
  **pre-stretches** the envelope to a **~100–105 inch circumference** before flight (i.e. it flies
  essentially fully round, ~32–33 in diameter at altitude). Manufacturer-claimed figures quoted in
  the community compilation: *"Yokohama claim 32inch, 113 cm, 80 cm, 270 litres"* (COMMUNITY,
  KevWal/Balloon-Info — see §2).

---

## 2. The stated / measured mass of each

### 2.1 The decisive number — 32-inch Yokohama

| Model | Nominal size | Mass | Source | Confidence note |
|---|---|---|---|---|
| **Yokohama "Crystal Clear" 32" sphere — _new_ valveless version** (the one the community now buys; the operator's own docs say he has the "no nozzle" version) | 32 in / ~800 mm nominal; ~100–105 in circumference when stretched | **48.6 g** | **COMMUNITY compilation, first-hand scale value:** `KevWal/Balloon-Info` `README.md` + `Yokohama.MD` (GitHub), compiled from `groups.io/g/picoballoon` posts, "as of 5 November 2022". The file states plainly: *"Balloon empty weight: 48.6g."* | **MEDIUM–HIGH.** A named community practitioner's scale figure, curated into a comparison table (see 2.2). Corroborated in magnitude by Ruthroff's "nearly half of 85 g" (§4) and by the repo's own 47 g. **No manufacturer figure exists to compare against.** |
| **Same product, _old_ version (with self-sealing valve)** | 32 in | **41 g** | Same source (`README.md`: row "Yoko 32" Old … 41 g") | **MEDIUM.** Same provenance; the Δ≈7.6 g vs the new version is attributed to the removed valve/nozzle hardware. |
| Yokohama 32" as used in this repo's docs | 32 in | 47 g | `docs/PRE-STRETCHING-PROTOCOL.md` §A/§C/E.2 (`analysis/*` branches carry the same file). The doc's source line names "Yokohama manufacturer" | **LOW provenance.** The manufacturer publishes **no** mass, so the "manufacturer" attribution cannot be right; the value sits between the measured 41 g and 48.6 g and matches the new (heavy) version within ~1.6 g. Treat as a **repo estimate**, superseded by the 48.6 g measurement. |
| Coloured / metallic Yokohama 32" sphere | 32 in | not published, not measured | — | **TODO(unverified)** |
| Yokohama 7 / 10 / 14 / 20 / 24 inch spheres | 7–24 in | not published | `products.json` (MFR) | **MFR states no mass for any size.** |

### 2.2 Community comparison table (useful for cross-checks)

`KevWal/Balloon-Info/README.md` (COMMUNITY, sourced to `groups.io/g/picoballoon` table id=38275
and the picoballoon archive) — reproduced verbatim in values:

| Balloon | Volume | Empty weight | Max free lift |
|---|---|---|---|
| Qualatex Silver 36" (2016 & 2018-08) | 120 L | 37 g | 2.5 g |
| Qualatex Silver 36" (2017-04) | 120 L | 33 g | 2.5 g |
| Chinese Clear 36" | — | 38 g | 7 g |
| Grabo Silver 36" | 145 L | 44.5 g | 2.5 g |
| **Yokohama ("Yoko") 32" Old** | **240–270 L** | **41 g** | 8 g |
| **Yokohama ("Yoko") 32" New** | **240–270 L** | **48.6 g** | 8 g |
| SAG Silver / Orbz 35" | 240 L | 46 g | 5 g |

Flights logged against the "Yoko 32" New" row in that same table: *7 g payload → 13.5 km; 28 g
payload → 10.3 km+; 40 g payload → 10 km* (COMMUNITY).

**Independent sanity check — a different measured envelope:** Traquito (traquito.github.io) measured
a cheap 50-inch Amazon foil balloon at **52 g** ("Stats: 52 grams, Length = 49″ end-to-end",
MEASURED). So the 32" Yokohama at ~41–49 g is *lighter* than a comparable-lift cheap foil balloon
— plausible for a thin nylon/PE laminate.

### 2.3 What the manufacturer *does* state (for completeness)

* Material: **Nylon, Polyethylene** (MFR, product page).
* "Balloons filled with helium gas will float for about a week" (MFR, product page — a shop
  duration claim, not a mass figure).
* Price (MFR store, 2026-10-07): Crystal Clear 32" 10-pack **US$120** (no valve) / **$130** (with
  valve); coloured 32" 10-pack $110. Community price reports: NIBBB (Jan 2025) quotes **$125/10 +
  $100 Japan freight** for the valved, **$120/10** for the valveless.

---

## 3. Gas mass and attachment mass

### 3.1 Gas densities — verified against sources

| Quantity | Value | Source |
|---|---|---|
| Helium, STP (0 °C, 1 atm) | 0.1786 g/L | Wikipedia, *Helium* (Density at STP) |
| Helium, **20 °C** | **0.166 kg/m³ = 0.166 g/L** | fluidprops.com, *Helium density* — "Helium density is 0.166 kg/m³ at 20 °C" |
| Hydrogen, STP | 0.08988 g/L | Wikipedia, *Hydrogen* (Density at STP) |
| Hydrogen, **20 °C** | **0.084 kg/m³ = 0.084 g/L** | fluidprops.com, *Hydrogen density* — "At 20 °C and atmospheric pressure, the density of hydrogen is 0.084 kg/m³" |
| Air, **20 °C**, 1 atm | **1.2041 g/L** | kg-m3.com *Air 20 °C*; matches Wikipedia *Density of air* |
| Air, ISA sea level (15 °C) | 1.2250 g/L | Wikipedia, *Density of air* |

The two figures quoted in the task brief (**He ≈ 0.166 g/L, H₂ ≈ 0.084 g/L**) are therefore
**confirmed** — they are the 20 °C values, not the STP values. Any calculation must pair them with
air at the **same** temperature (1.2041 g/L at 20 °C), which the figures below do.

**Lift available per litre (DERIVED, 20 °C):**

```
Helium:     1.2041 − 0.166 = 1.0377 g/L   ≈ 1.04 g/L
Hydrogen:   1.2041 − 0.084 = 1.1204 g/L   ≈ 1.12 g/L
```

(Hydrogen lifts ~8 % more per litre than helium — consistent with the repo's own note.)

### 3.2 Fill volume assumed, and the gas mass

**Assumption (stated explicitly):** the community fills by *required lift*, not to a fixed volume —
"fill until the balloon hovers with the payload plus the chosen free lift". So the fill volume is
**DERIVED** from the required lift:

```
V      = L / (ρ_air − ρ_gas)      with L = payload + free lift  [g]
m_gas  = V × ρ_gas                 [g]
```

Free lift is taken as **6 g** — the community's optimum band is 5–7 g (Traquito: "Around 5-7
grams"; NIBBB: 6–7 g; Ruthroff: "five or six grams … the magic number"; desertrats: 6–8 g). 6 g is
the middle of every published band.

| Payload | + free lift | Required lift | Helium volume → **gas mass** | Hydrogen volume → **gas mass** |
|---|---|---|---|---|
| 9 g | 6 g | 15 g | 14.5 L → **2.41 g** | 13.4 L → **1.12 g** |
| 14 g | 6 g | 20 g | 19.3 L → **3.21 g** | 17.9 L → **1.50 g** |
| 18 g | 6 g | 24 g | 23.1 L → **3.85 g** | 21.4 L → **1.79 g** |
| **20 g** | 6 g | 26 g | 25.1 L → **4.17 g** | 23.2 L → **1.94 g** |
| 22 g | 6 g | 28 g | 27.0 L → **4.49 g** | 25.0 L → **2.09 g** |

> **Note on reported volumes.** The community's reported launch volumes for this balloon vary:
> Ruthroff states *"It needs about 0.07 cubic meters of gas at launch"* (≈70 L) and *"about 0.28
> cubic meters"* to stretching capacity (COMMUNITY, theastroimager.com); the repo's own
> `PRE-STRETCHING-PROTOCOL.md` says "Gas volume ~70 L"; KevWal gives 240–270 L at full stretch.
> 70 L of helium would give ~73 g of lift — far more than the ~20 g neck lift those same authors
> describe — so the 70 L figure appears to be a *stretching/shape* volume rather than the gas
> actually retained at launch. **The physically consistent reading is the table above** (fill for
> the required lift). Flagged rather than silently reconciled — see §7.

**Gas mass at full stretch (DERIVED, for reference only — not the launch fill):**

| Envelope volume | Helium gas mass / net lift | Hydrogen gas mass / net lift |
|---|---|---|
| 240 L | 39.9 g / 249.0 g | 20.1 g / 268.9 g |
| 270 L (MFR-claimed) | 44.9 g / 280.2 g | 22.6 g / 302.5 g |
| 280 L (0.28 m³, Ruthroff) | 46.6 g / 290.6 g | 23.4 g / 313.7 g |

### 3.3 Attachment mass (neck / tie / payload line)

| Item | Mass | Source / status |
|---|---|---|
| Heat-seal at the neck | **0 g added** (seals the balloon's own neck material) | Method, Traquito/NIBBB/KevWal |
| Kapton tape to seal the neck | **~1 g** | NIBBB, COMMUNITY estimate — *"Is it possible the tape weighed almost a gram?"* |
| Antenna / payload suspension wire (36 AWG, 20 m dipole, **both** legs) | **1.2 g measured** | Traquito, *Free Lift* page — *"For my wire, it's 1.2 g total for both dipole legs together."* (The tracker hangs on this wire — no separate load line is used: "You do not need a separate load-bearing wire or cable support.") |
| Ribbon-loop handle / nozzle tie for holding the balloon | **TODO(unverified)** — not quantified by any source found | — |
| Magnet (0.5 g) to orient tilted solar cells south | 0.5 g | KevWal/Balloon-Info, MEASURED |
| **Total attachment allowance used below** | **≈ 2.2 g** (1 g tape + 1.2 g wire) | DERIVED from the two sourced items; the loop tie is unquantified |

For a **total-mass** reading, all three — envelope, gas, attachments — count. Sum the table above
with the payload.

---

## 4. All-up payload mass that real pico-balloon flights actually carry

"Payload" in every source below means the **flight package** (transmitter + solar + antenna +
support), i.e. **not** the balloon and **not** the gas.

| Source | Stated payload mass | Type |
|---|---|---|
| John Ruthroff (theastroimager.com), own flights JR01–JR35 | **14 g** (JR01–06, 09) … **16.4–18.4 g** (JR14/28/29) … **21–22 g** (JR32) … **28.7 g** (JR35) | MEASURED (own scale, per-flight) |
| Ruthroff, whole-package budget | *"The total package, balloon, payload, power supply … normally can't weigh more than 3 ounces [85 g]. Since nearly half that weight is taken up by the balloon itself, we're down to lifting a useful payload/power supply combination of 8/10th's of an ounce [23 g]"* | COMMUNITY statement (implies envelope ≈ 40 g — consistent with §2) |
| KI4MCW (via repo docs) | 15.1 g (lightest) … 19.2–22.9 g (most) … 28.9 g (heaviest) | MEASURED |
| IEEE Spectrum (David Schneider) | *"The payload of a pico balloon is so light (between 12 to 30 grams)…"* | COMMUNITY/magazine |
| SF-HAB, Pacificon **2023** | **10 to 20 g** | COMMUNITY (club presentation) |
| SF-HAB, Pacificon **2025** | **10 to 40 g** | COMMUNITY |
| desertrats.us (2025 presentation) | *"Payload weighs 5 to 17 grams"* | COMMUNITY |
| w7lt / PARC (2025) | *"Payloads < 20 grams"*; elsewhere *"less than 15 grams"* | COMMUNITY |
| lakewashingtonhamclub (2025) | *"The Payload Must be light! Less than 20 grams"* | COMMUNITY |
| NIBBB (own builds) | tracker+poly-solar+dipole package **9.2 g**; high-power/low-sun package **~20 g**; horizontal solar panel alone 4.2 g, film cylinder panel 18 g | MEASURED |
| Traquito | *"Total weight doesn't really matter that much (within reason)"* — no fixed figure | COMMUNITY guidance |
| picoballoon.io (commercial superpressure) | JL-1 envelope 136 g "while carrying payloads up to 50 g"; FD-11 probe 10 g | MFR (commercial) |

**Reading of the above:** the community's **normal, proven** payload band is roughly **9–22 g**,
with a long-duration sweet spot around **14–18 g**; record-light builds go below 9 g; heavier builds
(23–29 g) still flew for months but at lower altitude. This is **payload only** in every case — the
~41–49 g envelope is counted separately.

---

## 5. The "20 gram" figure the community quotes

The 20 g number is quoted repeatedly, and in **every source located it is attached to the
*payload*, not to the whole system**:

* lakewashingtonhamclub: *"The **Payload** Must be light! Less than 20 grams"*
* w7lt / PARC: *"**Payloads** < 20 grams"*
* SF-HAB Pacificon 2023: *"**Payload mass** … 10 to 20 Grams"*
* desertrats.us: *"**Payload** weighs 5 to 17 grams"*
* NIBBB, describing a build: *"bringing the total **package** to over 20 grams compared to 9 grams"*
  — i.e. they treat **20 g as a package (payload) target to stay under**, and 9 g as good.
* Ruthroff's arithmetic is the operational origin of the number: *"if my payload weighs 14 grams, I
  add, say 6 grams to that and come up with **20 grams of what is called 'neck lift'**"* — 20 g is
  here a **lift** target (payload + free lift), not a legal mass limit.

**What evidence the community cites for a 20 g threshold:** none of the sources above cites a
*legal* instrument for "20 g". The only regulation they actually quote is the **US 14 CFR Part 101
Subpart D** payload applicability (desertrats.us and nibbb.org both reproduce it verbatim):
payloads **< 4 lb** (and a weight/size ratio test), **< 6 lb**, or **< 12 lb** for two-or-more
packages are not subject to Subpart D. Those are **pounds**, three orders of magnitude above 20 g —
so the community's "20 g" is a **performance rule of thumb for staying aloft** (a heavier payload
flies lower: Ruthroff's "Gravity is the great equalizer"), **not** a legal threshold. NIBBB asserts
their flights are *"exempt from 14 CFR 101"* on the basis of that payload rule, not of any 20 g
clause.

> **This document takes no position on the law.** The authoritative German/EU position — including
> whether any German threshold counts payload or total system mass (the ~500 g *envelope+ballast*
> CTR de-minimis, the 4 kg "leicht" class, etc.) — is in `docs/analysis/free-balloon-mass-threshold-DE.md`.
> The finding reported here is narrow: **the community believes and applies 20 g as a payload
> figure, and the only legal text they cite does not contain a 20 g threshold at all.**

---

## 6. Bottom line — payload budget under a **total-mass** reading

Under a total-mass reading, what the envelope weighs comes straight off the payload budget:

```
payload_budget = threshold − envelope − gas − attachment
```

**Non-payload mass of a 32-inch Yokohama, new (valveless) envelope, at the §3.2 fill:**

| Component | Helium fill | Hydrogen fill |
|---|---|---|
| Yokohama 32" envelope (new, measured) | 48.6 g | 48.6 g |
| Lifting gas (for a 20 g payload + 6 g free lift) | 4.17 g | 1.94 g |
| Attachments (tape ≈1 g + dipole wire 1.2 g) | 2.20 g | 2.20 g |
| **Non-payload subtotal** | **54.97 g** | **52.74 g** |

**Explicit subtraction — if the threshold is the community's "20 g" read as TOTAL mass:**

```
20.00 g  (threshold, total-mass reading)
−48.60 g  Yokohama 32" envelope (new, measured)
− 4.17 g  helium (20 g payload + 6 g free lift, 20 °C)
− 2.20 g  attachments (tape + dipole wire)
────────
−34.97 g  → payload budget = −35.0 g
```

With hydrogen instead of helium the subtotal is 52.74 g, giving a budget of **−32.7 g**.
Hydrogen buys back only ~2.2 g, because **the gas is a rounding error next to the envelope.**

**Answer to the question as asked:** under a total-mass reading of a 20 g threshold, **there is no
remaining payload budget at all — the design is ~35 g *over* before a single gram of payload is
added.** The envelope alone (48.6 g) is **2.43×** the entire 20 g allowance. A "20 g" figure is only
attainable if it is a **payload-only** figure (which is exactly how the community uses it, §5).

**Budget as a function of the threshold** (Helium fill, same non-payload subtotal of 54.97 g):

| Threshold T (total-mass reading) | Payload budget = T − 54.97 g |
|---|---|
| 20 g (community's number, total-mass reading) | **−35.0 g** (impossible) |
| 30 g | −25.0 g |
| 54.97 g (the physical minimum) | 0 g (nothing left; balloon alone floats) |
| 60 g | +5.0 g |
| 85 g (Ruthroff's "3 oz" package ceiling) | +30.0 g |
| 100 g | +45.0 g |
| 500 g (German CTR de-minimis on envelope+ballast — see sibling task) | **+445.0 g** |
| 1814 g (4 lb, US 14 CFR 101 payload exemption) | +1759.0 g |

So: **any threshold at or above ~55 g total leaves headroom; a 20 g total-mass threshold does not
admit a 32-inch Yokohama at all.** If the operative threshold instead counts *payload* (as the
community's usage does, and as the US rule effectively does), the full 20 g payload band is
available and the ~49 g envelope is irrelevant to it.

**For the operator's own build:** weigh *your* balloon on the MS300 scale (it fits — the balloon is
~49 g, well inside the scale's range; ⚠ do **not** put a magnet on the pan, per
`PRE-STRETCHING-PROTOCOL.md` §E.3). A 32" Yokohama should come in around **41–49 g**; if you measure
the valveless "no nozzle" version you should expect ≈ **48.6 g**. That measured number is what goes
into the subtraction above.

---

## 7. TODO(unverified) — figures I could NOT confirm

* `TODO(unverified)` — **A manufacturer-stated envelope mass.** Yokohama Balloon publishes **no**
  mass for any sphere size on its own store/catalogue (`products.json`, checked 2026-10-07). The
  48.6 g / 41 g figures are community-measured, not manufacturer-stated.
* `TODO(unverified)` — **The mass attribution in this repo (`docs/PRE-STRETCHING-PROTOCOL.md`,
  47 g).** Its source line names "Yokohama manufacturer", but no such manufacturer figure exists;
  provenance could not be established. Superseded by the 48.6 g measurement.
* `TODO(unverified)` — **A second, independent first-hand scale value** for the 32" Yokohama
  beyond the KevWal compilation (which is itself a *compilation* of the inaccessible
  `groups.io/g/picoballoon` archive — the primary posts are behind a login, so I could not read the
  raw weighing posts; I cite the compilation, and note it is one layer removed from the scale).
* `TODO(unverified)` — **Whether the 48.6 g figure is for the crystal-clear envelope or a coloured
  one.** The compilation lists a single "Yoko 32" New" row; the clear film is reported to be lighter
  than the silver in the same file, but the row is not colour-qualified.
* `TODO(unverified)` — **Ribbon-loop handle / neck-tie mass**, the "payload line" component. Not
  quantified by any source found (the community hangs the tracker directly on the antenna wire).
* `TODO(unverified)` — **The 70 L vs 240–270 L launch-volume discrepancy** (§3.2). The 70 L figure
  (Ruthroff; repo) is inconsistent with the ~20 g neck lift those same authors describe; the
  physically consistent launch volume is the DERIVED 14–27 L in §3.2. Could not resolve which the
  authors meant.
* `TODO(unverified)` — **Manufacturer's claimed 113 cm / 80 cm dimensions** ("Yokohama claim
  32inch, 113cm, 80cm, 270litres"). Reported second-hand in the community compilation; not visible
  on the manufacturer's own product page.
* `TODO(unverified)` — **Confirmation that no 36-inch Yokohama sphere exists** in the *Japanese*
  domestic catalogue (`balloonya.com`). The JP site's product sitemap was checked but the sphere
  balloon category page could not be resolved (404 on the guessed path). The **English** store has
  no 36" sphere; that is the strongest evidence available. **Do not assume a 36" Yokohama exists.**
* `TODO(unverified)` — Any **legal** bearing of these masses. Out of scope here; see
  `docs/analysis/free-balloon-mass-threshold-DE.md`.

---

## 8. Sources

1. Yokohama Balloon Co., Ltd. (横浜風船株式会社), export shop — <https://yokohamaballoon.com/>
   (`/products.json` catalogue, product page `sphere-balloon32inch-1bag10pieces`; retrieved 2026-10-07). **[MFR]**
2. `KevWal/Balloon-Info` — `README.md` (balloon comparison table) and `Yokohama.MD`; GitHub,
   master branch. Community data compiled from `groups.io/g/picoballoon` (table id=38275 and the
   Yokohama archive), "as of 5 November 2022". **[COMMUNITY/MEASURED]**
3. John Ruthroff — *PICO-Ballooning*, <https://www.theastroimager.com/picoballoning/pico-ballooning/>. **[COMMUNITY/MEASURED]**
4. Traquito — *Free Lift* and *Balloons*, <https://traquito.github.io/flying/freelift/> and
   <https://traquito.github.io/flying/balloons/>. **[MEASURED]**
5. NIBBB (Northern Illinois Bottlecap Balloon Brigade) — <https://nibbb.org/technical-info/>,
   <https://nibbb.org/tag/yokohama/>, <https://nibbb.org/blog/page/3/>. **[COMMUNITY/MEASURED]**
6. Klofas / SF-HAB — *Picoballoons*, Pacificon 2021, <https://www.klofas.com/papers/Picoballoons-Pacificon-2021.pdf>. **[COMMUNITY]**
7. SF-HAB — Pacificon presentations 2023 and 2025,
   <https://sf-hab.org/wp-content/uploads/2023/12/amateur-radio-ballooning-for-fun-and-science.pdf> and
   <https://sf-hab.org/wp-content/uploads/2025/10/2025-pacificon-presentation.pdf>; plus
   <https://sf-hab.org/2023/07/26/new-yokohama-balloon-preparation/>. **[COMMUNITY]**
8. desertrats.us — *Pico-Balloons & Amateur Radio* (2025),
   <https://desertrats.us/wp-content/uploads/2025/05/Pico-Balloon-Presentation-5163-Read-Only.pdf>. **[COMMUNITY]**
9. w7lt / PARC — *PicoBalloon Plan* (2025),
   <https://w7lt.org/wp-content/uploads/2025/10/PARC_PicoBalloonPlanMeeting1.pdf>. **[COMMUNITY]**
10. lakewashingtonhamclub — *Amateur Radio Ballooning* (2025),
    <https://lakewashingtonhamclub.org/content/files/2025/02/Amateur-Radio-Ballooning---VE7NZ-and-VA7SL---Jan-2025.pdf>. **[COMMUNITY]**
11. picoballoon.io — <https://www.picoballoon.io/> (commercial superpressure hardware). **[MFR]**
12. Wikipedia — *Helium* (density at STP), *Hydrogen* (density at STP), *Density of air* (1.2250 kg/m³ ISA). **[reference]**
13. fluidprops.com — *Helium density* (0.166 kg/m³ at 20 °C) and *Hydrogen density* (0.084 kg/m³ at 20 °C). **[reference]**
14. kg-m3.com — *Air 20 °C* (1.2041 kg/m³ at 1 atm). **[reference]**
