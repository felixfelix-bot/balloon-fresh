# BASE-STATION BOARD COMPONENT CHECKLIST — living, version-controlled

> **What this is.** The tracked checklist of every component that must go on the **GROUND /
> BASE-STATION** board of the balloon internet gateway. It is a **document, NOT a KiCad layout** —
> no schematic, no netlist, no gerbers. It is a **living checklist the operator can tick off**.
> It **EXTENDS** the sibling shopping list (`design/rf-shopping-list` @ `eea1cbc00702`,
> `docs/analysis/rf-shopping-list-and-duplex-architecture.md`) rather than duplicating it.
>
> **It orders nothing and buys nothing.** Prices are vendor pages or AliExpress German-listing
> "from" prices read **2026-10-08**; anything not sourced is **`TODO(unverified)`**.

| | |
|---|---|
| Date | 2026-10-08 |
| Branch | `design/level-control-architecture` (base `github/main` @ `09e1b69`) |
| Design | `docs/analysis/ground-station-level-control-design.md` (+ ADR-084) |
| Related | ADR-071 (gateway basis), **ADR-072** (band-split duplex, BPF-before-LNA), ADR-079 (owned LNA), ADR-080 (XR-613), ADR-083 (2.4 GHz dish) |

## Status key

| Status | Meaning |
|---|---|
| **OWNED** | The operator already has it in hand. Carried, not bought. |
| **TO-BUY** | Priced and sourceable now. In the TO-BUY total. |
| **OPT** | Optional / only under a stated condition. **Not** in the TO-BUY total. |
| **TODO(unverified)** | Required but the part or its price is not yet verified. **Counted as €0 in the total — it is a real gap.** |

## The checklist

| # | Block | Function | Part | Status | Qty | Price (EUR) + URL | Interface / notes |
|---:|---|---|---|---|---:|---|---|
| 1 | RX 433 | antenna | **Diamond A-430S15R** 430–440 MHz 15-el Yagi, 14.8 dBi, PL/SO-239 | **TO-BUY** | 1 | **74.50** · `funktechnik-bielefeld.de/diamond-a-430s15r-uhf-15-element-richtantenne-70cm-band` CONFIRMED | Needs a **PL→SMA adapter** (row 12). Owns the 433 downlink gain (ADR-081 option B). |
| 2 | RX 433 | **band-pass filter BEFORE the LNA** | 433 MHz BPF, FBP-433s class | **TO-BUY** | 1 | **24.19** (cheap alt **9.29**) · `aliexpress.com` item `1005012493261239` (alt `1005004047000536`) | **ADR-072 INV-3.** Must be **first** — the wideband LNA would otherwise amplify 2.4 GHz TX leakage. **HOW TO VERIFY:** must pass 433.92 MHz with ≤ ~1 dB IL and reject **2.45 GHz by ≥ 40 dB** (the sibling model's 68 dB duplex figure assumes 45 dB). |
| 3 | RX 433 | **LNA** (masthead gain) | **Qorvo TQP3M9037** | **OWNED** | 1 | — (owned) · `qorvo.com/products/p/TQP3M9037` (via Wayback) | Gain 20 dB, NF 0.4 dB, OP1dB +20 dBm, +22 dBm CW. **⚠ BAND-EDGE DISPUTE — see "Spec disputes" below.** Must be at the **masthead** (ADR-079 INV-1). |
| 4 | RX 433 | input protection (optional insurance) | PIN-diode RF limiter, SMA, 10 MHz–6 GHz, 10–20 dBm class | **TO-BUY** | 1 | **4.39** · `aliexpress.com` item `1005012328874838` | **INSURANCE ONLY** (ADR-072 D3): residual TX leakage is −56 dBm nominal, 56–78 dB below the LNA's ratings. Choose the threshold **just above** the expected in-band signal. |
| 5 | RX 433 | **level control (AGC element)** | **Analog Devices ADL5240** digital VGA: 100 MHz–4 GHz, +20.3/−12 dB, 6-bit DSA 0.5 dB step, NF 2.8 dB @450 MHz, SPI+parallel | **TO-BUY** | 1 | **≈ 2.09** (chip, "from") · `aliexpress.com` item `1005006722641749`; datasheet `analog.com/media/en/technical-documentation/data-sheets/ADL5240.pdf` | **AFTER the LNA** (ADR-084). Alternative: **ADL5330** (10 MHz–3 GHz, −35…+22 dB, analog 20 mV/dB, NF 8 dB) `…/ADL5330.pdf` ≈ €15.59; or the **PE43711-class SMA DSA module** below (row 6). |
| 6 | LEVEL CTRL | **digital step attenuator (RX path alt / TX path)** | **pSemi PE43711**-class SMA DSA: 9 kHz–6 GHz, **0–31.75 dB, 0.25 dB step** | **TO-BUY** | 1 | **18.89** · `aliexpress.com` item `1005012321787574`; silicon `psemi.com/products/digital-step-attenuators/pe43711` | Same part family on **TX** (range→attenuation LUT, ADR-084 §3). **HOW TO VERIFY:** ≥ 6 GHz and 0.25 dB LSB on the listing; glitch-less. |
| 7 | LEVEL CTRL | **log detector** (AGC feedback) | **Analog Devices AD8318**: 1 MHz–8 GHz, 70 dB, ±1.0 dB /55 dB, 10/12 ns | **TODO(unverified)** | 1 | price not confirmed · datasheet `analog.com/media/en/technical-documentation/data-sheets/AD8318.pdf` | Tap **after the BPF/LNA** (band-selective) **and put a 433 MHz BPF at the detector input** — the AD8318 is broadband and would otherwise let 2.45 GHz TX leakage drive the loop's gain down (consult F5). Cheaper alt: **ADL5513** (1 MHz–4 GHz, 80 dB, −70 dBm) `…/ADL5513.pdf`. **HOW TO VERIFY:** the chip vs eval board; needs a power-detector **coupler/tap**. |
| 8 | LEVEL CTRL | **ADC + MCU** (digital AGC + TX LUT) | RP2040 board **or** ESP32-S3 module (ADC + SPI) | **TODO(unverified)** | 1 | ~4 (AliExpress RP2040-class board; exact listing/price not verified) | Runs the AGC state machine, the range→attenuation LUT, the mode switch and the bypass. **May be the same host that already does GNSS/housekeeping.** Keep the TX code path independent of the RX-loop state (ADR-084 §6). |
| 9 | TX 2.4 | antenna | **Sirio SLP-17** log-periodic, 1700–2500 MHz, 11.1 dBi | **TO-BUY** | 1 | **59.00** · `funktechnik-bielefeld.de/sirio-slp-17-1800-2500-mhz-richtantenne` CONFIRMED | Above ~8 dBi the 2.4 GHz ground gain is EIRP-inert (ADR-081 D1); bought for pattern/polarisation. Boresighted with row 1 on one positioner (ADR-071 D3). |
| 10 | TX 2.4 | band-pass filter | 2.4 GHz BPF | **TO-BUY** | 1 | **17.79** (alt 23.99) · `aliexpress.com` item `1005012653486194` (alt `32820151286`) | Cleans the uplink spectrum (ADR-072). |
| 11 | TX 2.4 | **uplink PA / FEM — MISSING** | 2.4 GHz FEM with gain-control pin (e.g. Skyworks **SKY66112-11**) **or** a discrete PA | **TODO(unverified)** | 1 | price/topology not decided · `web.archive.org/web/20240404044111id_/https://www.skyworksinc.com/-/media/SkyWorks/Documents/Products/2201-2300/SKY66112-11_203225O.pdf` (CONFIRMED) | **NOT required on the ISM footing** (ADR-072 D4: the uplink needs attenuation, not amplification). Required iff a **higher legal footing** (amateur / fixed link) or an omni antenna is chosen. The RF2126 module (~€7.69, `aliexpress.com` item `1005011559280074`) is the cheap option on that footing. |
| 12 | interconnect | coax + connectors | Airborne 10 (LMR-400 class) + N-male crimps + **PL→SMA adapter** | **TO-BUY** | 15 m / 4 / 1 | **64.50** (15 m @4.30/m) `kabel-kusch.de/produkt/airborne-10/2`; **5.74** (4 N-male) `aliexpress.com` item `32875381213`; **3.49** (PL→SMA) `aliexpress.com` item `1005006143199910` | Attenuation @433/2.4 GHz per 10 m = **0.76 dB / 1.92 dB** (Kabel-Kusch tables). Keep the run short; N where possible. |
| 13 | bench | **VNA to verify every passive at 433 AND 2.4 GHz** | **LiteVNA 62** (50 kHz–6.3 GHz) | **TO-BUY** | 1 | **166.99** · `aliexpress.com` item `1005003536382606` CONFIRMED | **This is what the owned Red Pitaya cannot do** (row 15). Verifies the BPFs, the DSA, the XR-613 (ADR-080) and the TQP3M9037 band edge (spec dispute below). |
| 14 | power/bias | bias tee + rails | LNA/DSA/detector bias (5 V), bias tee, decoupling | **TODO(unverified)** | 1 set | not priced | The ADL5240 runs on 4.75–5.25 V @ 93 mA; the ADL5330 is differential. Bias-tee and rail parts not selected. Ground DC energy is **not** a constraint (operator). |
| 15 | bench (owned) | IF instruments | **Red Pitaya** STEMlab 125-14 | **OWNED** | 1 | — (owned) · `redpitaya.com/product/stemlab-125-14/` | **DC–60 MHz analog — an IF tool, NOT an RF front end.** Cannot see 433 or 2.4 GHz (ADR-080). Usable *behind a downconverter* (IF receiver / waveform gen / spectrum monitor ≤ 62.5 MHz / logic analyser). |
| 16 | bench (owned) | divider | **XR-613** resistive power divider (DC–5 GHz) | **OWNED** | 1 | — (owned) | **RESISTIVE ⇒ ~6 dB, NO array gain — bench tool only (ADR-080).** Never a gain stage in a link budget. |
| 17 | bench (owned) | mixer (for an IF/downconverter path) | **unmarked RF/LO/IF mixer module** | **OWNED** | 1 | — (owned) | Specs and model number **unknown — `TODO(unverified)`** (inherited open item, ADR-080). Assumed LO/RF/IF → usable behind the Red Pitaya. |
| 18 | mechanical | mast-head mounting / enclosure | mast clamps, weatherproof enclosure, cable glands | **TODO(unverified)** | 1 set | not priced | Mast-head hardware and wind load belong to ADR-076/077/078 (positioner/stow); this row is the **electronics enclosure + mast-head feedpoint** only. |

> **Qty note (consult F11).** Rows 5–6 are the **level-control elements**, and they are **separate
> physical instances** if both directions are automated: one in the **433 RX** path (the AGC element,
> row 5) and one in the **2.4 GHz TX** path (the range→attenuation DSA, row 6). They are **not** one
> part shared across bands — nothing in the duplex path may be required to pass both bands through one
> narrowband element (ADR-072 INV-1). Count **qty 2** if both are populated; **qty 1 on TX only** is the
> sufficient first-flight build (the RX chain then runs at manual/commanded gain).

### Rows deliberately OUT OF SCOPE here

- **Positioner / rotator / stow latch / mast** — owned by ADR-076 (stow), ADR-077 (gearing),
  ADR-078 (right-sizing); the tier price is in ADR-081 option B (≈ €735 total).
- **2.4 GHz reflector/dish** — ADR-083 (bought production Ku offset dish; new €94.90 or used ~€50).
- **Balloon-side radios (F33 / LR2021)** — flight boards, ADR-074/075; this checklist is **ground-only**.

## Totals

| Roll-up | Items | Indicative total (EUR) |
|---|---|---:|
| **OWNED subtotal** (rows 3, 15, 16, 17) | 4 line items | **€0 outlay** (already in hand) |
| **TO-BUY subtotal, excluding the VNA** (rows 1, 2, 4, 5, 6, 9, 10, 12) | 8 priced rows | **≈ €274.58** |
| **TO-BUY subtotal, including the VNA** (adds row 13) | 9 priced rows | **≈ €441.57** |
| **Not counted (real gaps)** | rows 7, 8, 11, 14, 18 | **`TODO(unverified)` — not in the totals** |
| **OPT (not counted)** | RF2126 PA €7.69 | €0 unless a higher legal footing is chosen |

*Arithmetic, excluding the LiteVNA (row 13):* 74.50 + 24.19 + 4.39 + 2.09 + 18.89 + 59.00 + 17.79 +
(64.50 + 5.74 + 3.49) = **274.58**. *Adding the LiteVNA 166.99* → **441.57**. The single largest line
is the **LiteVNA 62** — it is deliberately included because it is what replaces the Red Pitaya for
verifying the XR-613 and every passive at both bands.

## MISSING from the board (state plainly)

These are required for a working gateway and are **not yet specified** (each is a real gap, not a
rounding):

1. **2.4 GHz uplink PA or FEM** (row 11) — needed only on a higher legal footing / omni antenna.
2. **433 MHz BPF** — *specified* (row 2) but not owned and not measured.
3. **LNA input limiter** — *specified* (row 4), inexpensive insurance.
4. **Antennas** — *specified* (rows 1, 9), not owned.
5. **AGC detector / ADC / MCU** (rows 7, 8) — the level-control brain is **`TODO(unverified)`**.
6. **DSA** (row 6) — *specified*, the TX level-control element.
7. **Bias / PSU** (row 14) — bias tee and rails **not selected**.
8. **Enclosure** (row 18) — not selected.
9. **Mast-head hardware** (row 18) — not selected (positioner itself: ADR-076/077/078).

## Spec disputes and "how to verify this part is the right one"

| Row | Dispute | How to verify (one test) |
|---:|---|---|
| 3 | **TQP3M9037 433 MHz coverage is DISPUTED.** Module label **0.1 MHz–6 GHz** (operator) vs vendor **0.7–6 GHz** (Qorvo page via Wayback). If 0.7 GHz is authoritative the part **does not cover the 433 downlink at all** (ADR-079 **D5**, CONDITIONAL). | **Sweep it on the bench.** With the LiteVNA 62 (row 13) measure **S21 from 400 to 500 MHz**: if in-band gain ≥ ~15 dB and NF is sane at 433.92 MHz, the lower edge is ≤ 0.4 GHz and the record stands; if S21 collapses below ~0.7 GHz, the 433 RX chain needs a **433-capable LNA** and **ADR-079 must be reopened**. Do this **before** buying the 433 BPF/limiter. |
| 2 | The 68 dB duplex isolation (ADR-072) is a **composite of norms, not a measurement**. | Measure the BPF's **rejection at 2.45 GHz** (≥ 40 dB required) and its **in-band IL** (counted in NF). Then the end-to-end **desense test**: PER/sensitivity **with the 2.45 GHz TX at max permitted output** (ADR-072 acceptance criterion). |
| 16 | XR-613 identity/insertion loss. | Its **class** is known (resistive, ~6 dB, no gain — ADR-080). Its **measured IL / power rating** are `TODO(unverified)`: sweep on the LiteVNA 62 and keep it **out of any high-power chain**. |
| 17 | Unmarked mixer specs. | Model number unknown. Characterise conversion loss and LO/RF/IF range before relying on it behind the Red Pitaya; otherwise treat as a spare. |
| 5/6 | ADL5240 vs ADL5330 vs PE43711 DSA — which is "the" level element. | Choose on **interface**: SPI register (ADL5240, repeatable) vs analog `GAIN` pin (ADL5330, no firmware) vs ready-made SMA DSA (PE43711 module, no board work). Verify the DSA's **0.25 dB LSB and ≥ 6 GHz** on the listing (row 6). |
| 13 | AliExpress "from" prices. | Re-check the item page at checkout — item pages are JS-rendered, so the "from" price may differ. |

## How to use this checklist

1. Tick a row only when the part is **in hand** (OWNED/TO-BUY → done) or **measured** (spec dispute rows).
2. The two **blocking** verifications before any 433 purchase are: the **TQP3M9037 band-edge sweep**
   (row 3) and the **433 BPF rejection** (row 2). Everything in the 433 RX chain depends on row 3.
3. A **first flight needs no level-control automation**: rows 5–8 can be deferred and the chain run at
   **manual/commanded gain** (ADR-084 §5). Rows 1, 2, 3, 4, 9, 10, 12 are the minimum to close a link.

*(Living document — edit rows in place, keep the status key, re-run the arithmetic in "Totals".)*
