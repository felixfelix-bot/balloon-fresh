# MEASURED MASSES — operator scale readings (2026-10-14)

**Tier: `user-measured`** (Felix, operator) · two scales used: one grams-resolution, one
milligrams-resolution · weighed both a 10-pack and a single unit per size, to separate a
per-unit number from any packing/tape artefact.

This file is the **single source for the raw readings**. Derived arrays live in
`PAYLOAD-WEIGHT-ESTIMATES.md`, `docs/analysis/wing_mass_model.py` and
`docs/analysis/ALTITUDE-AND-MASS-REQUIREMENTS.md`.

---

## 1. Solar cells

| Reading | Mass | Tier |
|---|---|---|
| 10 large panels | **14.04 g** | user-measured |
| 1 large panel | **1.382 g** | user-measured |
| 1 small panel | **0.440 g** | user-measured |
| 10 small panels | **4.462 g** | user-measured |

### Derived per-unit values

| Size | Single | 10-pack mean | Agreement | Repo cell outline | Area | Areal density |
|---|---|---|---|---|---|---|
| **large** | 1.382 g | **1.4040 g** | 1.59 % | 78.55 × 38.90 mm | 30.556 cm² | **45.95 mg/cm²** (from 10-pack), 45.23 (single) |
| **small** | 0.440 g | **0.4462 g** | 1.41 % | 52.07 × 19.65 mm | 10.232 cm² | **43.61 mg/cm²** (from 10-pack), 43.00 (single) |

Use the **10-pack mean**: it averages out the handling/tape residue on a single part, and the
two independent weighings agree to ~1.5 % — the reading is clean, not marginal.

### Which physical panel is which (identification, derived)

The repo carries two cell outlines (ADR-049): **52.07 × 19.65 mm** ("small cell") and
**78.55 × 38.90 mm** ("large cell"). The measured areal densities identify the operator's two
sizes unambiguously:

- **Operator's LARGE = the repo's 78.55 × 38.90 mm cell** — 45.95 mg/cm².
- **Operator's SMALL = the repo's 52.07 × 19.65 mm cell** — 43.61 mg/cm².

Evidence: the two sizes differ by **+5.4 % in areal density** while differing by 3.15× in mass
and 2.99× in area — i.e. the two readings lie on **one common areal-density line**, which is
what a single cell technology cut to two sizes produces. The alternative reading (operator's
"large" = the 52 × 19 mm part) would imply **137 mg/cm²**, roughly 3× any thin cell and
inconsistent with the other reading. It is rejected.

> Sanity anchor: a 0.20–0.21 mm cell at ~2.3 g/cm³ is ≈48 mg/cm². Both measurements sit just
> under that, as expected for a laminated part with an edge margin.

### What this changes

| Assumption currently in the repo | Measured | Delta |
|---|---|---|
| `wing_mass_model.py` assumes **1.5 g per cell** | **1.4040 g** (large) | **−0.096 g/cell (−6.4 %)** |
| earlier budgets assumed **0.8 g per cell** | 1.4040 g (large) | **+0.604 g/cell (+75.5 %)** |
| `PAYLOAD-WEIGHT-ESTIMATES.md` "~0.4 g/cell thin-film" | **0.4462 g** (small) | **+0.046 g/cell (+11.6 %)** |
| `wing_mass_model.py`'s bare-Si formula (area × t × ρ_Si) | 1.4951 g (large) / 0.5006 g (small) | **−6.1 % / −10.9 %** |

**The 0.8 g figure is refuted by measurement** — it is 1.76× light for the large cell.

Note the bare-silicon formula (which the model used until this measurement) was **close but not
right**, and wrong in *both directions* across the two sizes: −6.1 % on the large cell and
−10.9 % on the small. A purely geometric estimate cannot know the real part — which is exactly
why the model now reads the measured constant instead.

**Array consequences:**

| Option | Count | Array mass |
|---|---|---|
| ADR-049 primary (12 large, 3/wing) | 12 | **16.85 g** |
| ADR-049 fallback (36 small, 9/wing) | 36 | **16.06 g** |

Both options land within **0.8 g of each other** — the *count* choice is not a mass choice, it is
a joints-complexity choice (36 vs 108 hand-soldered joints per aircraft). Note both are **far
above** the `1.6 g` the 4-cell array is carried at in `PAYLOAD-WEIGHT-ESTIMATES.md`.

---

## 2. Envelope — Yokohama balloon

| Reading | Mass | Tier |
|---|---|---|
| Yokohama balloon envelope, as-shipped | **46.84 g** | user-measured |

This is a **third** measured figure for the Yokohama 32″ envelope, alongside the two already
recorded in the community number bank:

| Figure | Value | Tier |
|---|---|---|
| Yokohama 32″, old **valved** form | ~41 g | community-reported |
| Yokohama 32″, new **valveless** form | ~48.6 g | community-reported |
| **Felix's unit, as-shipped** | **46.84 g** | **user-measured** |

The measured unit sits **between** the two community figures and **1.76 g below** the valveless
figure the mass budget was using. It supersedes the community value **for the envelope actually
in hand** — which is what the flight plan must use.

### Effect on the subtraction

```
20.00 g   threshold (total-mass reading)
−46.84 g  envelope MEASURED (was −48.60 g)
− 4.17 g  helium (20 g payload + 6 g free lift, 20 °C)
− 2.20 g  attachments
────────
−33.21 g  → still NO payload budget, but 1.76 g better than the community figure
```

The conclusion is unchanged (the envelope alone exceeds a 20 g threshold by 2.34×), but the
number the flight plan uses is now a measured one.

---

## 3. Measurement method and its limits

- Two scales: both a 10-unit batch and one unit per size, so a per-unit number does not depend on
  the packing. The 1.4–1.6 % agreement between the batch mean and the single part is the
  measurement's own error bar.
- **`TODO(unverified)`:** the operator described the two sizes as "big" and "small" panel without
  stating outlines. The identification in §1 is **derived from areal density against the repo's
  two known outlines**, not from a dimension the operator stated. If either cell size in hand is
  actually a third outline, the mass figures stand but the size labels do not.
- **`TODO(unverified)`:** no per-cell interconnect/wire/solder mass was weighed; the array totals
  above are **bare cells only**.
- The envelope figure is as-shipped. If it is weighed again after pre-stretching, record it as a
  separate row — stretching does not change mass, but valve removal and neck trimming do.

## Reproduce

```bash
python3 docs/analysis/panel_mass_measured.py
```
