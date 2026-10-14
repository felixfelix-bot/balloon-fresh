# LIFT & FLOAT ANALYSIS — Yokohama 32-inch sphere + hub v9 assembly

**Date:** 2026-10-14 · committed for future reference
**Envelope:** Yokohama Balloon "Sphere Balloon(32inch) 1bag(10pieces)",
variant 47870710481049. D = 813 mm, V(full) = 281 L. Material unstated on the
page; **chloroprene assumed** (Yokohama's sphere range; latex runs lighter).
Envelope mass bounded **60–100 g** — *weigh one to replace this bound*.

## Mass budget (hub v9 @ 0.8 mm — the thickness-corrected board)

| Item | Mass |
|---|---|
| Bare PCB 115×103×0.8 mm FR4 (+15% Cu/mask) | 20.2 g |
| ESP32-S3-WROOM-1U | 3.2 g |
| solder/reflow, all SMD | 0.5 g |
| MAX-M10S fleet-average (1.3 g × 4/10 boards) | 0.5 g |
| SX1280 + LDO + passives + diodes | 0.6 g |
| U.FL ×4 | 0.5 g |
| **Hub populated** | **25.5 g** |
| Wings: 2× PCB 25×184 mm | 15.7 g |
| Solar cells (4–8 × 1.2 g) | 4.8–9.6 g |
| Misc (interconnects, tape, tether) | 2.0 g |
| **Wings total** | **22.5–28.3 g** |
| **PAYLOAD (hub + wings)** | **48–54 g** |
| **ALL-UP (payload + envelope)** | **108–154 g** |

## Launch

- Full 281 L helium sphere lifts **298 g** at sea level.
- For **5–7 g free lift** (community standard): fill **~150 L ≈ 53–54%** of the
  full sphere. (100% fill at launch = 144–190 g net lift = burst risk.)

## Float — where it actually settles

While the envelope can still expand, a sealed gas mass keeps **constant net
lift** — the "lift vs altitude" curve is flat and tells you nothing. Float
happens where the **fully-stretched** envelope's displacement equals all-up mass:

| Case | Float at nominal 281 L | For 11 km | For 13.7 km |
|---|---|---|---|
| Light all-up 108 g | **~9.5 km** | 342 L = 1.22× (34 in) | 523 L = 1.86× (39 in) |
| Heavy all-up 154 g | **~6.4 km** | 488 L = 1.74× (38 in) | 746 L = 2.65× (44 in) |

**Chloroprene does not stretch 1.7–2.6×** — that is latex territory.

## Verdict

With this envelope, realistic float is **6.4–9.5 km** — below the proven
11–13.7 km pico band, but above weather and fully usable for the comms
missions (radio horizon at 8 km ≈ 320 km; FLRC link budget already covers it).

**Options:**
1. **Accept 7–9 km float** — sufficient for the experiment programme; coldest
   ambient improves to ≈ −40…−45 °C, which also relaxes the −55 °C risk.
2. **Lighten payload** (delete GPS from more boards, thinner wings).
3. **36–40 inch latex** for the 11–13.7 km band. Note our all-up 108–154 g is
   **2–3× a typical pico payload** — even latex needs the large size.

## Reproduce

`docs/analysis/lift_budget_32in.py` and `float_analysis_32in.py` are committed.
When the real envelope mass and cell count are measured, update
`ENVELOPE_MASS_G` / `SOLAR_CELLS_G` and re-run.
