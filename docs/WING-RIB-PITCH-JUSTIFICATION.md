# Wing Rib Pitch — Proposed Layout and Its (Missing) Justification

**Status:** PROPOSAL — **`S_crack` is UNKNOWN. No strength number is invented here.**
**Track:** balloon-pre-stretching (envelope prep) · cross-refs wing/hub structural track
**Related:** ADR-049 (wing architecture), ADR-055 §D4, ADR-063 §6, ADR-065 (skeletonised wing), ADR-066 (conservative unfreeze), `docs/analysis/hub-array-overhang-and-support.md` §7, `docs/evidence/vertical-hub-consult-20261009.md`

> **Purpose.** ADR-065 adopts a *skeletonised* wing frame whose rib pitch is explicitly
> **gated** by a coupon measurement (`S_crack`) that does not exist yet. This document records
> the **proposed** pitch and the arithmetic the repo *does* support, and states plainly what
> the proposal is **not** allowed to claim. It adds no empirical number.

---

## 1. The question

A rib pitch sets the **unsupported span `L`** over which each
**78.55 × 38.90 × 0.21 mm** solar cell is carried, end-only, unbonded (ADR-052 constraint).
Too large a span cracks the silicon; too small a pitch gives back the mass the skeletonised
frame was adopted to save. The governing rule from the repo is:

> **`pitch ≤ S_crack`**, where `S_crack` is the unsupported span at which the 0.21 mm wafer
> fails — ADR-063 §6, ADR-065 §"Gating dependency".

---

## 2. What the repo gives us (verified) vs what it does not (UNKNOWN)

| Item | Value | Status |
|------|-------|--------|
| Cell geometry | 78.55 × 38.90 × 0.21 mm | **Documented** (repo) |
| End-only, no-bond support rule | required | **Documented** (ADR-052) |
| Simply-supported span demand formula | `σ = 3 ρ g L² / (4 t)` | **Documented** (ADR-063 §D4) |
| Cantilever demand formula | `σ = 3 ρ g L² / (2 t)` (one end uncarried) | **Documented** |
| Demand @ large cell 78.55 mm, 1 g, full span | **0.504 MPa** | **Verified arithmetic** (ADR-063 §D4) |
| Demand @ large cell 78.55 mm, 2 g, full span | **1.007 MPa** | **Verified arithmetic** |
| Demand, cantilever 78.55 mm @ 1 g | **2.01 MPa** | **Verified arithmetic** |
| **`S_crack` (0.21 mm silicon, flight temp)** | **UNKNOWN** | **NOT IN THE REPO — NOT IN THE DATASHEET** |
| Flexural strength of 0.21 mm silicon | **UNKNOWN** | ADR-065: "does not invent one" |
| Surface strain at first damage | **UNKNOWN** | not measured |
| Cold-soak limit available on the rig | **−18 °C** | Protocol §D.5 (far short of −55 °C) |

**The gap is one number.** With `S_crack` the pitch is set directly and the demand table
converts to an admissible surface stress. Without it, **no margin can be computed** — so the
proposal below deliberately does **not** claim one.

---

## 3. The proposed layout — chosen to *avoid* needing the missing number

> **Proposal: support every cell at **both ends** and add **one mid-span rib** per cell —
> i.e. **`L ≈ 39.3 mm`** (half of the 78.55 mm cell) — for the interim build. Adopt the
> conservative default from ADR-065; defer any lighter (larger-pitch) spacing until `S_crack`
> is measured.**

**Why this is *proposed* and not *invented*:** the proposal is a *layout choice* that needs
**no** strength assumption, because it is the least-mass-aggressive skeleton the ADR already
sanctions. The numbers below are the repo's own demand formula evaluated at the proposed span
— arithmetic on a documented formula, **not** a measured strength, and **not** a margin claim.

| Layout | Unsupported `L` | Demand @1 g | Demand @2 g | Cantilever @1 g |
|--------|-----------------|-------------|-------------|-----------------|
| Full span (no mid rib) | 78.55 mm | 0.504 MPa | 1.007 MPa | 2.01 MPa |
| **Proposed: +1 mid-span rib** | **39.28 mm** | **0.126 MPa** | **0.252 MPa** | **0.503 MPa** |
| +3 ribs (quarter span) | 19.64 mm | 0.032 MPa | 0.063 MPa | — |

*(Demand scales as `L²`; the proposed span is `½` the full span, so demand is `¼`.) These are
**demands** — what the load asks of the silicon — **not** capacities. The `S_crack`/strength
column is **blank on purpose**: no capacity number exists.*

> ⚠️ **A low demand number is not a safety margin.** "0.126 MPa at 1 g" says nothing about
> whether 0.21 mm silicon survives 0.126 MPa, because the capacity is UNKNOWN. This is the
> exact error `docs/evidence/vertical-hub-consult-20261009.md` recorded: *"no larger rib pitch
> is justified: bending grows ~quadratically with span, `S_crack` is unmeasured, and no
> allowable stress, fracture toughness, flaw size, fatigue life or safety factor appears."*

---

## 4. The governing load case is the **drop**, and it is unbounded in the repo

The repo repeatedly notes the true worst case is the **pre-launch drop** (an unbounded
acceleration), not the 1 g/2 g flight load. So even a *measured* `S_crack` at 1–2 g does not by
itself close the pitch with margin — the coupon must, at minimum, probe to failure and the
drop case must be handled by a margin whose size is **the operator's call**, documented as
such. **Neither the drop magnitude nor the margin exists as a number in the repo.**

---

## 5. What would close this — one coupon test (and it is the operator's own bench work)

Re-scoped from the *joint* to the *span* (ADR-052 §2.7, `hub-array-overhang-and-support.md` §7):

> Take one **real** 78.55 × 38.90 × 0.21 mm cell. Support it at its two ends over a gap `S`,
> in the real **end-only, no-bond** manner. Load to **1 g**, then **2 g**, and **increase `S`
> until the cell cracks. Record `S_crack` and the surface strain at first damage. Repeat
> **cold-soaked at ≈ −55 °C** and after N thermal cycles.

**Two hard limits on that session, both real:**

1. **The rig's cold soak is −18 °C, not −55 °C** (Protocol §D.5). So the *cold* `S_crack` —
   the one the flight temperature needs — **cannot be measured with the current freezer.**
   This is a genuine blocker, not a formality.
2. **The coupon needs the operator's hands.** It is destructive, specimen-prep heavy, and
   cannot be simulated. No agent action substitutes for it.

**Result table to fill (all cells UNKNOWN today):**

| Quantity | Room temp | −18 °C | −55 °C | After N cycles |
|----------|-----------|--------|--------|----------------|
| `S_crack` (mm) | **UNKNOWN** | **UNKNOWN** | **UNKNOWN** | **UNKNOWN** |
| surface strain at first damage | **UNKNOWN** | **UNKNOWN** | **UNKNOWN** | **UNKNOWN** |

---

## 6. Explicit non-claims

- This document **does not** state, estimate, or bound `S_crack` or any silicon strength.
- It **does not** claim the proposed `L ≈ 39.3 mm` has margin — only that it is the
  least-aggressive layout that needs no strength assumption.
- It **does not** freeze a rib pitch for production; per ADR-066, any reduction in carrier
  support must be a **new measured decision**.
- **No hardware test has been run** to produce any number in this document.

## 7. References

- ADR-049 (wing architecture; open rib-pitch item), ADR-055 §D4, **ADR-063 §6**, **ADR-065**, **ADR-066**
- `docs/analysis/hub-array-overhang-and-support.md` §7 (the closing measurement, in priority order)
- `docs/analysis/vertical-hub-load-cases.md` and `docs/evidence/vertical-hub-consult-20261009.md`
- `docs/adr/066-conservative-hub-unfreeze.md` — the conservative baseline this proposal aligns with
