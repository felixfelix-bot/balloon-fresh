# ALTITUDE REQUIREMENTS & FLIGHT MASS — the 12 km question

**Date:** 2026-10-14 · supersedes all earlier payload-weight statements for the
v9 hardware. Every mass is from a committed model or a board file; assumptions
are labelled.

## 1. First, a correction I owe you: the plan files were stale

The `<14 g` target in `PAYLOAD-WEIGHT-ESTIMATES.md` describes **"Mesh V1:
ESP32-C3, 50×40 mm"** — a board that no longer exists in this design. The v9
flight hardware is the **115×103 mm hub** plus a **4-arm cross carrying 4 wings**.

| Item | Mass | Source |
|---|---|---|
| Hub v9 populated (PCB 20.2 @0.8 mm + 5.3 parts) | **25.5 g** | board file + datasheet parts |
| 4-wing array, **full carrier as built** (7.300 g/wing) | **29.2 g** | `docs/analysis/wing_mass_model.py` (committed) |
| Harness, tether, tie-points | **~2.5 g** | estimate |
| **FLIGHT PAYLOAD** | **≈ 57 g** | |

That is **~4× the old target**. Nobody re-derived the lift when the design moved
from a 50×40 C3 board to the hub v9 — this document closes that gap.

Wing array alternatives already modelled (same script):

| Config | Array mass | Total payload |
|---|---|---|
| (a) Full carrier **as built** | 29.2 g | **≈ 57 g** |
| (b) Spine + ribs | 12.85 g | ≈ 41 g |
| (c) Cells only + flex/ribbon | 8.35 g | ≈ 36 g |
| (d) Double-sided carrier (6 cells/wing) | 35.57 g | ≈ 63 g |

## 2. Your 32-inch Yokohama sphere cannot reach 12 km — at any payload

Physics: float happens where the **fully-inflated** envelope's displacement
equals all-up mass. Lift per m³ = ρ_air(alt) × (1 − 0.138).

**The 32-inch sphere displaces 281 L. Its absolute lift ceiling:**

| Altitude | Displaces | Minus envelope 60 g | Minus envelope 100 g |
|---|---|---|---|
| 9 km | 133.8 g | 73.8 g | 33.8 g |
| 11 km | 88.2 g | 28.2 g | **−11.8 g** |
| **12 km** | **75.6 g** | **15.6 g** | **−24.4 g** |
| 13 km | 64.6 g | 4.6 g | −35.4 g |
| 14 km | 55.2 g | **−4.8 g** | −44.8 g |

**At 12 km the sphere displaces only 75.6 g. The envelope alone weighs 60–100 g.**
So the maximum payload for 12 km is **15.6 g** (best case) — i.e. you would have
to cut 57 g → 16 g, which is not the hub v9 with any wing.

**Your 32-inch sphere tops out at ~8–9 km with this payload.**

## 3. What payload WOULD reach 12 km? — the answer is "wrong lever"

**With the existing 32-inch sphere:** 12 km needs payload ≤ **15.6 g** (light
envelope) and 13 km ≤ **4.6 g**. Not achievable with v9 hardware.

**Keeping the 57 g payload, chloroprene doesn't work either** — envelope mass
scales as D², so it chases its own tail:

| Altitude | Chloroprene D for 49–59 g payload | Envelope mass |
|---|---|---|
| 12 km | 43.2–44.6 in | 137–146 g |
| 13 km | 48.0–49.4 in | 169–179 g |
| 14 km | 53.6–55.0 in | 211–222 g |

A 54-inch chloroprene sphere weighing 220 g to float our 57 g payload is absurd.

**The fix is latex, not payload reduction.** Latex is ~3× lighter per size and
stretches ~2× diameter before burst:

| Altitude | 36-in latex (≈25 g) fill to | Verdict |
|---|---|---|
| 11 km | 84–87 % of nominal | OK |
| **12 km** | 88–92 % | **OK** |
| 13 km | 93–97 % | OK, tight |
| 14 km | 98–102 % | at the limit |

**A 36-inch latex balloon carries the full 57 g payload to 12–13 km with no
payload reduction at all.** For ≥13.5 km with real margin, use **40-inch latex**.

## 4. ⚠️ 12 km is NOT above the passenger traffic

Your premise needs correcting, because it changes the target:

| Traffic | Altitude |
|---|---|
| Airliner cruise band (FL290–FL410) | **8.8 – 12.5 km** |
| Typical long-haul (FL350–FL400) | **10.7 – 12.2 km** |
| Business jets | up to 15.5 km |

**12 km sits inside the cruise band.** To actually be above the traffic, target
**≥13.5 km, ideally 14 km**.

And the honest caveat: **an ascending/descending balloon crosses the cruise band
regardless of where it floats.** Floating high reduces *dwell time* in the band;
it cannot eliminate the transit. The real risk-management levers are (a) float
high, (b) keep the descent short and predictable, (c) the envelope's tiny radar
and visual signature, (d) regulatory compliance for light balloons.

## 5. Recommendation

| Decision | Recommendation |
|---|---|
| Envelope | **40-inch latex**, not the 32-in chloroprene sphere — reaches 13.5–14 km with the payload unchanged |
| Payload reduction | **Not required** for the latex route. Worth doing anyway: wing config **(b) spine+ribs saves 16 g** for free (already designed) |
| Target altitude | **13.5–14 km** (above the cruise band), not 12 km |
| If you keep the 32-in sphere | Accept **~8–9 km** float — fine for the comms experiments, but it is NOT above traffic |

## 6. What still needs measuring (not on the internet)

| # | Measurement | Effect | Status |
|---|---|---|---|
| 1 | **Weigh one Yokohama 32-in sphere** (empty, dry) | Confirms/refutes the 60–100 g envelope bound | **✅ 46.84 g** (2026-10-14) |
| 2 | **Weigh one 52×19 mm solar cell** | 0.8 vs 1.6 g = 9.6 g across 12 cells | **✅ 0.4462 g small / 1.4040 g large** (2026-10-14) |
| 3 | **Weigh one latex balloon you intend to fly** | The latex mass figures above (25 g @36 in) are modelled, not measured — this decides the float altitude | _pending_ |

Measured readings, the identification of the two cell sizes and the reproduction script:
`docs/analysis/MEASURED-MASSES-2026-10-14.md`.
**Note on row 2:** the "0.8 vs 1.6 g" spread is now closed — neither figure was right. The small
cell measures **0.4462 g** (not 0.8) and the *large* cell is a different part at **1.4040 g**;
a 12-cell array of large cells is **16.85 g**, not 9.6 or 19.2 g.

Reproduce everything: `docs/analysis/altitude_requirement.py`.
