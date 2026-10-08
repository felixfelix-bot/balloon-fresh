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

