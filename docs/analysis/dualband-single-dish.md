# Can one Ku-band dish serve 2.4 GHz uplink and 433 MHz downlink?

**Status:** Analysis in progress — `docs/analysis/`, not yet an ADR.  
**Date:** 2026-10-08  
**Repro command:** `python3 docs/analysis/dualband_dish_arithmetic.py` (prints every table in this document).  
**Scope:** RF design only. No procurement. No flight-board changes.  

---

## 1. Executive summary

A single Ku-band reflector cannot be an excellent 433 MHz antenna: a 1.2 m dish is only ~1.7 wavelengths across at 433 MHz, and a feed sized for 2.4 GHz is electrically tiny at 433 MHz.  But the operator’s instinct to use **one mechanical mount** is sound.  The honest optimum is to **share the positioner, not the reflector**: use the Ku dish for the 2.4 GHz uplink (it is overbuilt for this and gives ~25–27 dBi), and mount a 7-element 433 MHz Yagi on the same dish structure or az/el head, boresighted with the dish.  This preserves 2.4 GHz performance, meets the 433 MHz link-budget target, and avoids a second steerable mount.

The earlier “single dish is a worse antenna than two purpose-built ones” framing was **too strong**: it correctly said one reflector is worse than two antennas, but under-weighted the real mechanical benefit of sharing the positioner and the fact that two feeds near the focus are mechanically feasible because 433 MHz has a 17 cm λ/4 tolerance.

**Key numbers:**
- Ku dish surface accuracy: λ/20 at 2.4 GHz = 6.2 mm; a Ku dish built for 12 GHz is ~5–12× better than needed.
- 1.2 m dish gain: **27.4 dBi @ 2.4 GHz**, **12.5 dBi @ 433 MHz** (theoretical, aperture formula, η=0.60).
- D needed for 20 dBi @ 433 MHz: **~2.7–3.0 m** — not portable.
- Feed illumination half-angle for f/D 0.6–0.7: **39–45°**.
- 2.4 GHz feed (λ/2 = 62.5 mm) is **0.09 λ** at 433 MHz.
- λ/4 positioning tolerance: **17.3 cm @ 433 MHz**, **3.1 cm @ 2.4 GHz**.
- Two feeds near focus: **≤1 dB** penalty at 2.4 GHz, **~0.1–0.2 dB** at 433 MHz.

**Decision status:** ADR not yet warranted; the 433 MHz gain of a single-reflector option is still an estimate.  Close with one measurement: mount a candidate 433 feed near the focus of a candidate 0.9–1.2 m Ku dish and measure its gain vs free space.

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
| η = 0.55 | 2.97 m | 1.67 m |
| η = 0.65 | 2.73 m | 1.54 m |

Sanity check: `G = 10·log₁₀(0.55·(π·3.0/0.6924)²) = 20.1 dBi` — a 3 m dish at 433 MHz just clears 20 dBi.

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

## 6. Ranking every way to make one dish serve both bands

All numbers assume a 1.2 m consumer offset Ku dish unless noted.

| Option | 2.4 GHz gain | 433 MHz gain | Pointing penalty | Preserves 2.4? | Mechanical complexity | Cost band |
|---|---|---|---|---|---|---|
| **(a) Two feeds near focus** | ~27 dBi | ~0–6 dBi (feed-mismatch limited) | None shared | Yes; ≤1 dB | Low: second feed arm, small dipole | € |
| **(b) 433 Yagi boresighted on dish structure** | ~27 dBi | 10–14 dBi (dedicated Yagi) | ~0 dB when dish is pointed | Yes | Low: bracket on feed arm or rim | € |
| **(b′) 433 Yagi on same positioner, off dish** | ~27 dBi | 10–14 dBi | Separate small alignment | Yes | Low: extra mast on az/el head | €€ |
| **(c) True dual-band feed + diplexer** | ~25–27 dBi | ~4–8 dBi | None | ~1–2 dB at 2.4 (phase-centre compromise) | Medium: dual-band horn, diplexer | €€ |
| **(d) Dichroic / frequency-selective subreflector** | ~27 dBi | ~10–12 dBi | None | Yes | High: custom FSS, precision mounts | €€€€ |
| **(e) Nested dishes / Cassegrain subreflector** | ~27 dBi | ~12–15 dBi | None | Yes | High: 2+ reflectors, aligned subreflector | €€€ |
| **Reference: separate 2.4 dish + 433 Yagi** | ~27 dBi | 12–15 dBi | None | Yes | Medium: two mounts or one big head | €€ |

### 6.1 Option (a) — two feeds near the focus

Put the 2.4 GHz feed at the focus.  Mount a small 433 MHz feed (e.g. dipole + tiny reflector, or a 3-element Yagi) a few cm away on the same feed arm.

- **2.4 GHz:** unchanged, ~27 dBi.
- **433 MHz:** the dish is too small to be great, and the feed is mismatched, so practical gain is likely 0–6 dBi.  This still *works* because the link budget has huge margin (+24 dB with a 12 dBi Yagi), but it is worse than a real Yagi.
- **Penalty:** ~0.1–0.2 dB at 433 from defocus, ≤1 dB at 2.4 from blockage/scatter.
- **Why it ranks first mechanically:** simplest shared pointing, no second mast.

### 6.2 Option (b) — 433 Yagi strapped to the dish and boresighted

A 7-element 433 Yagi (~12 dBi, ~1.2 m boom) mounted on the dish structure, aimed parallel to the dish boresight.  This is **not** “the dish at 433”; the dish only provides the pointing reference.

- **2.4 GHz:** unchanged.
- **433 MHz:** 12 dBi, exactly what the link budget wants.
- **Pointing:** because 433 Yagi beamwidth is ~40–50°, whenever the 2.4 GHz dish (7° beam) is on target, the Yagi is automatically on target.
- **Penalty:** near-zero.
- **Why it ranks best overall:** delivers the target 433 gain without sacrificing 2.4 GHz, and still uses one positioner.

### 6.3 Option (b′) — 433 Yagi on same positioner, but off the dish

A separate short mast on the az/el head carries the 433 Yagi beside the dish.

- Same RF performance as (b).
- Slightly more structure and one-time boresight adjustment.
- Avoids any chance of the Yagi blocking/scattering the dish aperture.

### 6.4 Option (c) — true dual-band feed with diplexer

A single feed physically common to both bands with a diplexer.  The phase centre of a dual-band horn cannot sit at the paraboloid focus for both frequencies simultaneously because the effective phase centre moves with frequency and the optimum illumination angle changes (±40° at 2.4 GHz would need a much wider pattern at 433 MHz than any fixed horn provides).

- **2.4 GHz:** ~1–2 dB compromise from non-optimal phase centre / illumination.
- **433 MHz:** pattern still wrong for the dish, so 4–8 dBi at best.
- **Complexity:** medium; diplexer + dual-band horn.
- **Verdict:** neat but does not solve the fundamental size mismatch.

### 6.5 Option (d) — dichroic / frequency-selective subreflector

A subreflector transparent at 2.4 GHz and reflective at 433 MHz, with the 2.4 feed behind it and a 433 feed at the Cassegrain secondary focus.  This is the professional multi-band reflector approach (Deep Space Network, large earth stations).

- **RF:** excellent at both bands.
- **Mechanical:** requires a precision subreflector, struts, dual foci.
- **Cost/complexity:** completely out of scale for a portable balloon ground station.

### 6.6 Option (e) — nested dishes / Cassegrain subreflector

Use the big dish for 433 and a small 2.4 GHz subreflector / separate feed at the focus.  This inverts the problem: the 2.4 path uses a Cassegrain stage, the 433 path uses the prime focus.

- Still needs the big dish to be ~3 m at 433 to be worth it.
- Adds alignment and subreflector mounting complexity.
- Not gimbal-mountable in portable form.

### 6.7 Ranking summary

For this project the sensible order is:

1. **Best RF + acceptable mechanics:** **(b) Yagi on the dish structure** — hits the link-budget target at 433 and keeps 2.4 intact.
2. **Best mechanics + acceptable RF:** **(a) two feeds near focus** — the most elegant single-reflector idea, but 433 gain is poor.
3. **Nearly as good:** **(b′) Yagi on the positioner beside the dish** — same RF as (b), one extra mast.
4. **Neat but compromised:** **(c) dual-band feed** — adds complexity without fixing 433.
5. **Overkill:** **(d) dichroic subreflector** and **(e) nested dishes** — correct physics, wrong scale.

---

## 7. The mechanical counter-argument — the operator is right about this

The earlier “single dish is a worse antenna than two purpose-built ones” framing is correct **only if RF performance is the only metric**.  The operator’s pushback is about **system integration**: one dish on one positioner means:

- **One pointing system** instead of two independent az/el mechanisms.
- **No second steerable 433 mount** to build, tune, or power.
- **One target to track** during a pass; both RF paths move together.
- **Reduced cabling and RF rotator joints** (one coax run, not two).
- **Lower mass and wind load** than two separate reflectors.

A separate steerable 433 antenna at this gain level is not free.  A 1.2 m boom Yagi on its own az/el head is a second mechanical subsystem: two more motors, two more position encoders, a sturdier mast, and a synchronization/alignment procedure so the two boresights stay parallel.  For a portable ground station this can easily dominate the build effort and the failure modes.

**The fair statement:** the operator’s instinct to share the dish mount is mechanically sound.  The RF problem is not that the dish is too rough or too small at 2.4 GHz — it is that the same dish is too small and the feed is too electrically tiny at 433 MHz.  The correct compromise is **share the positioner, not necessarily the reflector**.

---

## 8. Verdict and what would change it

### 8.1 Verdict

- **Ku-band dish at 2.4 GHz:** fully suitable.  Surface accuracy has huge margin; a 0.9–1.2 m dish gives 25–27 dBi, more than the link budget needs.
- **Ku-band dish at 433 MHz:** electrically small.  A 1.2 m dish gives only ~12.5 dBi in theory and probably 0–6 dBi in practice because the feed is mismatched.  A 3 m dish would be needed to reach 20 dBi — not portable.
- **One dish for both:** **mechanically shareable, RF-poor at 433**.  The best single-positioner solution is **a 2.4 GHz dish plus a 433 MHz Yagi mounted on the same dish structure or positioner head** (option b or b′), not a single reflector with a dual-band feed.
- **Was the earlier answer too strong?** **Yes, partially.**  The earlier “bad idea” under-weighted the mechanical benefit of sharing the positioner and overstated the difficulty of mounting two feeds near the focus.  It was right that a single reflector is worse than two purpose-built antennas, but wrong to imply that “one dish” must mean “one reflector”.  “One positioner, two antennas” is the honest optimum.

### 8.2 What measurement closes it

Build or buy the cheapest candidate 0.9–1.2 m offset Ku dish and:

1. **Measure its RMS surface error** (straightedge + feeler gauge at several points, or photogrammetry).  Confirms §2 margin.
2. **Put a 2.4 GHz feed at the focus and compare gain against a known reference** (e.g. a calibrated 2.4 GHz Yagi at the same range).  Confirms §3.
3. **Mount a small 433 MHz dipole / 3-element Yagi near the focus** and measure its gain on the dish boresight vs the same antenna in free space.  This one measurement closes the **~10 dB feed-mismatch estimate** in §4.3 and the **0.1–0.2 dB defocus penalty** in §5.1.

Until (3) is done, the 433 MHz gain of any single-dish option remains an **estimate**, not a decision.

---

## 9. For future sessions

**One-line rule:** share the **positioner**, not the **reflector**; use the Ku dish for 2.4 GHz and strap a 433 Yagi to the dish or its head.

**Paths:**
- Analysis: `docs/analysis/dualband-single-dish.md`
- Link budget it answers to: `docs/LINK-BUDGET-LICENCE-EXEMPT.md`
- Next design step (mechanical): bracket a 7-element 433 Yagi to the dish feed arm so it is boresighted with the dish.

**Command to reproduce the key numbers:**

```bash
python3 -c "
import math
c=299.792458e6
for f in [2.4e9,433e6,12e9]:
    print(f, c/f*1000, 'mm')
for D in [0.6,0.9,1.2,1.5]:
    print(D, 10*math.log10(0.6*(math.pi*D/(c/2.4e9))**2), 'dBi @2.4')
"
```

---

## 10. Unsourced / TODO items

1. **Ku dish RMS surface accuracy** — 0.3–1.0 mm is an industry rule of thumb, not a measured or datasheet value for a specific dish.
2. **433 MHz feed-mismatch loss (~10 dB)** — based on small-antenna theory and dish-feed rules of thumb; needs MoM simulation or measurement.
3. **λ/4 ≈ 1 dB defocus rule and quadratic extrapolation** — widely cited but an approximation; needs measurement/simulation for the candidate dish.
4. **Specific Yagi gain/pattern at 433 MHz** — the 12–15 dBi/40–50° beamwidth numbers are typical, not a datasheet.
5. **Offset dish effective f/D** — assumed 0.6–0.7 for consumer offset Ku; needs measurement of the candidate dish.

---

*End of analysis.*
