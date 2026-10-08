# Can one Ku-band dish serve 2.4 GHz uplink and 433 MHz downlink?

**Status:** Analysis in progress — `docs/analysis/`, not yet an ADR.  
**Date:** 2026-10-08  
**Repro command:** `python3 tools/dualband_dish_arithmetic.py` (to be added when verified against this document).  
**Scope:** RF design only. No procurement. No flight-board changes.  

---

## 1. Executive summary (placeholder)

To be filled after §§2–7 below are complete.

---

## 2. Surface accuracy: a Ku dish is MORE than good enough at 2.4 GHz

A Ku-band receive dish is designed for ~10.7–12.75 GHz.

| Surface-accuracy rule | λ at 12 GHz | λ at 2.4 GHz | λ at 433 MHz |
|---|---:|---:|---:|
| λ/20 (low loss) | 1.2–1.4 mm | **6.2 mm** | **34.6 mm** |
| λ/16 (acceptable, ~1 dB loss) | 1.5–1.8 mm | **7.8 mm** | **43.3 mm** |

A consumer Ku dish built to the λ/20 rule for 12 GHz must therefore have an RMS surface error under ~1.2–1.4 mm.  Re-purposing that same dish at 2.4 GHz gives a **≥5× margin to λ/20** (≥4× to λ/16).  At 433 MHz the margin is ≥25×.

Using the Ruze equation, `η/η₀ = exp(−(4πσ/λ)²)`, the surface-error loss on a 1.0 mm RMS Ku dish is:

- @ 12 GHz: ~1.1 dB (this is why it was built to ~0.3–0.8 mm).
- @ 2.4 GHz: **0.044 dB**.
- @ 433 MHz: **0.0014 dB**.

**Verdict:** the Ku dish is mechanically *overbuilt* for 2.4 GHz and for 433 MHz.  Surface accuracy is **NOT** the reason to reject one dish for both bands.

> **TODO(unverified):** a named dish datasheet listing RMS surface accuracy.  The 0.3–1.0 mm figure for consumer offset Ku dishes is a widely cited rule of thumb (e.g. satellite-TV industry practice), but this analysis should be closed by measuring the candidate dish with a straightedge + feeler gauge or by citing its manufacturer spec.

---

## 3. Dish size: fine at 2.4 GHz, far too small at 433 MHz

Gain of a circular aperture: `G = 10·log₁₀(η·(πD/λ)²)`.

### 3.1 Is the dish electrically large?

| D | D/λ @ 2.4 GHz | D/λ @ 433 MHz |
|---:|---:|---:|
| 0.6 m | 4.8 | 0.9 |
| 0.9 m | 7.2 | 1.3 |
| 1.2 m | 9.6 | 1.7 |
| 1.5 m | 12.0 | 2.2 |

At 2.4 GHz even 0.6 m is already electrically useful (D/λ > 4).  At 433 MHz a 1.2 m dish is only 1.7 λ across — it is in the transition region between "flat plate" and "real parabola".  The simple aperture-gain formula still gives a number, but illumination efficiency, spillover, and edge diffraction dominate.

### 3.2 Gain vs diameter at each band

Using η = 0.60 (achievable with a well-matched feed):

| D | G @ 2.4 GHz | G @ 433 MHz |
|---:|---:|---:|
| 0.6 m | 21.4 dBi | 6.5 dBi |
| 0.9 m | 24.9 dBi | 10.0 dBi |
| 1.2 m | 27.4 dBi | 12.5 dBi |
| 1.5 m | 29.3 dBi | 14.4 dBi |
| 3.0 m | 35.3 dBi | 20.5 dBi |
| 5.0 m | 39.8 dBi | 24.9 dBi |

A 1.2 m dish at 2.4 GHz gives ~27 dBi, well above the 18 dBi Yagi the link budget assumes.  At 433 MHz the same dish gives only ~12.5 dBi, while the licence-exempt link budget expects **12–15 dBi ground-station Yagi gain** (`docs/LINK-BUDGET-LICENCE-EXEMPT.md` §0/§2).

### 3.3 What D gives 20 dBi at 433 MHz?

| Aperture efficiency | D for 20 dBi @ 433 MHz | D for 15 dBi @ 433 MHz |
|---:|---:|---:|
| η = 0.55 | 2.95 m | 1.66 m |
| η = 0.65 | 2.72 m | 1.53 m |

A 3 m dish at 433 MHz is not something a portable balloon ground-station gimbal points at the sky.  This is the central size problem: **the operator is right that one dish could share the mount, but the shared dish would have to be ~3 m at 433 MHz to beat a modest Yagi.**  No consumer Ku dish is large enough to make 433 MHz *great*.

### 3.4 Beamwidth consequence

HPBW ≈ 70·λ/D degrees:

| D | HPBW @ 2.4 GHz | HPBW @ 433 MHz |
|---:|---:|---:|
| 0.9 m | 9.7° | 53.9° |
| 1.2 m | 7.3° | 40.4° |
| 1.5 m | 5.8° | 32.3° |

At 433 MHz the same reflector is so wide-beamed that a 1.2 m dish is not meaningfully more directional than a small Yagi, while being far heavier and harder to feed.

---

## 4. The feed problem: illumination angle and electrical size at 433 MHz

### 4.1 Illumination half-angle vs f/D

For a paraboloid, the rim subtends a half-angle θ at the focus:

`tan(θ/2) = 1 / (4 · f/D)`  →  `θ = 2 · arctan(1 / (4·f/D))`

| f/D | θ (half-angle, deg) |
|---:|---:|
| 0.35 | 71.1° |
| 0.40 | 64.0° |
| 0.50 | 53.1° |
| 0.60 | 45.2° |
| 0.70 | 39.3° |

Consumer offset-fed Ku dishes have an **effective f/D around 0.6–0.7**, so the feed must illuminate roughly **±40–45°**.  A 2.4 GHz feed of order λ/2 (≈60 mm) with a modest flare can cover this.

### 4.2 The same physical feed at 433 MHz is electrically tiny

A 2.4 GHz feed element that is λ/2 at 2.4 GHz is:

`λ(2.4 GHz)/2 ≈ 62.5 mm`

At 433 MHz, λ ≈ 692 mm, so the same 62.5 mm element is:

`62.5 mm / 692 mm ≈ 0.09 λ`

A 0.09 λ radiator is essentially an electrically small antenna.  Its pattern is broad and omni-like, not the ±40° pencil the dish needs.  Spillover will be large: much of the feed power misses the dish rim, and ground noise enters the receive path.

### 4.3 Estimated efficiency loss from feed mismatch at 433 MHz

A well-designed dish feed at its design frequency has an illumination efficiency ηᵢ of roughly 0.7–0.85.  When the feed is mismatched (wrong pattern, wrong phase centre, too wide/narrow):

- Spillover can climb from ~5 % to 30–50 %.
- Uneven illumination can drop aperture efficiency by another 3–6 dB.

For this estimate we treat the 433 MHz feed as **mismatched by ~10 dB effective aperture loss** compared with a purpose-built 433 MHz feed for the same reflector.  The dominant mechanisms are:

1. **Pattern mismatch:** a 0.09 λ element cannot form a ±40° beam; much power goes outside the rim.
2. **Phase-centre instability:** an electrically small feed has no well-defined phase centre at the paraboloid focus.
3. **Impedance mismatch:** a fixed-size 2.4 GHz feed is far off 50 Ω at 433 MHz.

> **TODO(unverified):** the 10 dB estimate is a placeholder based on small-antenna pattern theory and dish-feed design rules (e.g. Balanis, *Antenna Theory*, Chap. 15).  It should be closed by NEC/MoM simulation or by measuring a candidate feed on the candidate dish.

**Bottom line:** using the dish’s 2.4 GHz feed structure unchanged at 433 MHz likely throws away most of the 12 dBi the aperture formula promises, bringing the practical 433 MHz gain of a 1.2 m dish down into the **0–6 dBi range** — worse than a cheap Yagi.

---

## 5. Feed-positioning tolerance — the surprising result

The classic rule: an axial feed defocus of λ/4 costs about 1 dB.

| Frequency | λ/4 |
|---|---:|
| 433 MHz | **173 mm = 17.3 cm** |
| 2.4 GHz | **31.2 mm = 3.1 cm** |

A 2.4 GHz feed must sit within ~3 cm of the dish focus.  A 433 MHz feed, however, can be **17 cm away** before it suffers the same 1 dB defocus loss.

### 5.1 Two-feed arrangement: 2.4 GHz feed at focus, 433 feed alongside

If the 2.4 GHz feed is placed exactly at the focus and a separate 433 MHz feed is mounted a few centimetres away (say 5 cm axial offset, 5 cm lateral offset):

- **2.4 GHz loss:** the 433 feed is close to the 2.4 GHz feed (a few cm), so it is effectively at the focus too.  A 5 cm lateral offset at 2.4 GHz is ~1.6 λ; defocus loss is small but may scatter/block some aperture.  Estimate **≤1 dB** if the 433 feed is small and not in the optical path.
- **433 MHz loss:** 5 cm axial offset is 5/17.3 ≈ 0.29 λ/4.  Quadratic scaling from the λ/4 = 1 dB rule gives `1 dB × (0.29)² ≈ 0.08 dB`.  Lateral offset of 5 cm is similarly small.  **Total 433 penalty ≈ 0.1–0.2 dB**.

**This is the key insight:** because 433 MHz is so much longer wavelength, **two separate feeds near the focus are mechanically viable** for the low-gain 433 path.  The earlier “bad idea” framing under-weighted this.

> **TODO(unverified):** exact defocus loss vs offset should be closed by measurement or full-wave simulation.  The λ/4≈1 dB rule is widely cited (e.g. Ruze, “Axial Defocusing of a Parabolic Reflector”) but the small-offset quadratic approximation is an estimate.

### 5.2 Lateral blocking by the 433 feed at 2.4 GHz

A 433 MHz feed / dipole / small Yagi mounted near the focus will be tens of centimetres across at most.  A 1.2 m dish at 2.4 GHz has a 7.3° beam.  The 433 structure, if it is within the first Fresnel zone, blocks or scatters a fraction of the aperture.  A 5 cm wide object blocks roughly `(5 cm / 1.2 m)² ≈ 0.2 %` of the geometric area — negligible.  A 15 cm Yagi could block ~1.6 % → ~0.07 dB.  Still small.

**Conclusion:** the two-feed arrangement does not destroy 2.4 GHz performance, and the 433 penalty is tiny.  The *real* penalty is not defocus; it is the feed-pattern mismatch from §4.

---

