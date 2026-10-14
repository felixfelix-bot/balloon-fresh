# MEASURED MASSES — operator scale readings, 2026-10-14 (authoritative)

**Status:** ✅ **MEASURED.** These replace every prior estimate for solar panels and the balloon
envelope. Source: operator statement + 8 balance photographs, read directly.

## The readings

| item | mass | method |
|---|---:|---|
| **1 small panel** | **0.440 g** | milligram balance, single panel |
| **10 small panels** | **4.462 g** | gram balance → **0.4462 g/panel** |
| **1 large panel** | **1.382 g** | milligram balance, single panel |
| **10 large panels** | **14.04 g** | gram balance → **1.4040 g/panel** |
| **Balloon (Yokohama)** | **46.84 g** | gram balance — envelope ALONE; a marker on the pan was **taréd out** and is not in the reading (operator, 2026-10-14) |

**Two different balances were used**, and that matters: a **gram balance (0.01 g readability)** for
the 10-piece piles and a **milligram balance (0.01 mg)** for single panels.

## Cross-check: each size was weighed two independent ways — and they agree

This is a real test, because each panel size has **two independent readings on two different
instruments**:

| size | single panel | 10-piece average | delta |
|---|---:|---:|---:|
| small | 0.440 g | 0.44620 g | **−0.0062 g (1.41 %)** |
| large | 1.382 g | 1.40400 g | **−0.0220 g (1.59 %)** |

**Both agree within 2 %.** The 10-piece route is *tighter* than it looks — the bucketing is on a
0.01 g balance, so the per-panel resolution is 0.001 g, finer than the single-panel readability.
**The measurements are internally consistent.**

## Solar panels vs the repo's silicon-density estimate

The model derived mass as **area × thickness × Si density** (0.21 mm, 2.329 g/cm³):

| panel | area | Si estimate | **measured** | ratio |
|---|---:|---:|---:|---:|
| small `52.07 × 19.65` | 10.2318 cm² | 0.5004 g | **0.440 g** | **0.88×** |
| large `78.55 × 38.90` | 30.5559 cm² | 1.4945 g | **1.382 g** | **0.92×** |

**Measured is consistently ~8–12 % BELOW the Si-only estimate.** That is the **expected direction**:
the estimate was computed from *bare* silicon and explicitly **ignored the cell's metallisation,
busbars and any encapsulant** — yet the real cells come out *lighter* than bare-silicon mass would
predict for their nominal dimensions. **The most likely explanation is that the physical panels are
slightly under nominal size, or the nominal thickness (0.21 mm) is high.** Either way the measured
values are the truth and the estimate is now retired.
**`UNVERIFIED` on the mechanism** — establishing it needs calipers on the panels, which only the
operator can do.

## Retired assumptions

| retired | replaced by | error it carried |
|---|---|---|
| **"~2 g per cell"** | measured 0.440 g (small) / 1.382 g (large) | **4.5× too heavy** — 12 small cells would be 24.00 g vs **5.28 g** measured |
| "~0.4 g/cell thin-film hope" | measured 0.440 g | the "hope" was **1.10× — essentially correct** |
| Si-density estimate 0.5006 g (small) | **measured 0.440 g** | **12 % high** |
| Si-density estimate 1.4951 g (large) | **measured 1.382 g** | **8 % high** |

**The cells are already at the thin-film figure** the doc was urging us to switch to. **The biggest
"weight lever" in `PAYLOAD-WEIGHT-ESTIMATES.md` was a phantom** — the cells were never the problem.

## Effect on the v9 array

v9 baseline is **4 wings × 3 small cells = 12 cells** (ADR-049, 1.5 V/wing):

| | mass |
|---|---:|
| **measured array, 12 × 0.440 g** | **5.280 g** |
| previous model, 12 × 0.5006 g | 6.007 g |
| **change** | **−0.727 g** |

**If large panels were used instead:** 12 × 1.382 = **16.584 g** (**+11.30 g** vs small). So panel
size is a **11 g decision**, which is now a measured number rather than an estimate.

## The balloon, and GAP 1

**The envelope is measured at 46.84 g (Yokohama).** The M7 photo was the **balloon itself**; an
earlier reading of it as a generic folded film was wrong on the object's **identity**.

**OPERATOR CLARIFICATION (2026-10-14, authoritative) — the marker question is CLOSED:**

> *"the marker isn't included in the weight. I zeroed the marker before weighing it. It was just
> there to hold the balloon in place so that it doesn't unfold while its being weighed. 46.84
> grams is the correct weight of the balloon. The marker isn't included in these 46.84 grams."*

So the balance was **taréd on the marker before the envelope went on the pan**. The marker was a
*physical restraint* only — it kept the folded envelope from unfolding — and it contributes
**zero** to the reading. **No re-weigh is needed and none is outstanding.**

Earlier in this document it was noted that a marker on the pan is ~10 g (21 % of the value) and
that re-weighing "is worth doing". **That concern is withdrawn**: it was based on not knowing
whether the display's `NET` had excluded the marker, and the operator has confirmed it did.

**Checked: no other photo also reads 46.84**, so this is one reading, not a duplicate.

With both measured:

| | mass |
|---|---:|
| hub PCB (0.8 mm, 70×70) | 20.20 g |
| hub parts | 5.30 g |
| wing array (measured cells) | 5.28 g |
| **flight hardware** | **30.78 g** |
| **balloon (measured)** | **46.84 g** |
| **TOTAL floating mass** | **77.62 g** |

**`docs/PAYLOAD-WEIGHT-ESTIMATES.md` targets "under 9 g" / "under 14 g". The measured total is
77.6 g — 5.5× the 14 g target.**

**GAP 1 is now CLOSED as a measurement, not a reconciliation:** the `<14 g` target is **not
achievable with this envelope**, and never was. It was written around hardware-only mass (≈31 g)
with an envelope that was assumed, not weighed. **The correct target is the balloon's own lift
budget** — which is what the float analysis already computes.

## What is now measured vs still assumed

**MEASURED:** solar panels (both sizes, two methods each), balloon envelope.
**STILL ASSUMED:** hub PCB mass (20.2 g from area × FR4 density), hub parts (5.3 g), solder, wire,
adhesive, panel-mounting mass. The **hub PCB** figure is the next-largest uncertainty and **can be
checked against the real board** once JLCPCB delivers.

## Reproduce

```
cd tracker/hardware && python3 measured_masses.py
```
