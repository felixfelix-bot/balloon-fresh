# OPERATOR CELL MEASUREMENTS (2026-10-14) — the mass budget's missing input, tested against the model

> ## ⚠ PARTIALLY SUPERSEDED — read `docs/analysis/MEASURED-MASSES.md` first
>
> This document was written from a **vision read of the 8 balance photographs**, before the
> operator's own identification of each reading. Three of its conclusions have since been
> corrected and are struck in place below:
>
> 1. **M7 is the balloon envelope**, not "unidentified translucent film". The marker on the pan
>    was **tared** — 46.84 g already excludes it. No re-weigh is needed.
> 2. **The measured cells do NOT "validate" the Si-density estimate** — they are **8–12 % below**
>    it. The estimate is retired.
> 3. The **g/cm² was derivable** all along once the ADR-049 outlines were applied.
>
> What still stands: the readings themselves, and the death of the "~2 g/cell" spec.

**Date:** 2026-10-14 · **Status:** measurements received and analysed. ~~They VALIDATE the repo's
Si-density cell-mass estimate~~ **CORRECTED: they undercut it by 8–12 %** (see
`MEASURED-MASSES.md`), and they kill the "~2 g/cell" pessimistic spec.

The operator weighed real solar cells on a **METTLER TOLEDO XS4002S DeltaRange** analytical
balance. The mass budget has been blocked on exactly this: the repo **assumed** cell masses.
These are **measurements**, so the assumptions get tested rather than affirmed.

## The readings, verbatim from the displays

| # | display | grams | what the pan actually shows |
|---|---|---:|---|
| M1 | `1382.79 mg` | **1.38279** | **one** cut section, clean-cut edges, elongated ~2:1, busbar visible |
| M2 | `439.67 mg` | **0.43967** | **one** cut section, elongated, busbar visible |
| M3 | `4462.30 mg` | **4.46230** | **three** strips, ~8–10 cm × 2–3 cm, overlapping |
| M4 | `14030.99 mg` | **14.03099** | overlapping stack, at least two pieces; proportions look like the **large** `78.55 × 38.90` option |
| M5 | `14.03 g` | **14.03000** | **two** pieces ~10 × 5 cm; unit **confirmed as grams** on the display |
| M6 | `4.47 g` | **4.47000** | ~a dozen overlapping cut strips |
| M7 | `46.84 g` **NET** | **46.84000** | the **Yokohama balloon envelope** (nylon/PE laminate). A marker held it flat on the pan and was **TARED OUT** — not part of the reading (operator, 2026-10-14) |

## The decisive test: a single section vs the estimate

The model derives cell mass as **area × thickness × Si density**:

```
small 52.07 x 19.65 x 0.21 mm = 10.2318 cm2 -> 0.5004 g   (repo states 0.5006)
large 78.55 x 38.90 x 0.21 mm = 30.5559 cm2 -> 1.4945 g   (repo states 1.4951)
```

**The two single-section readings bracket those estimates tightly:**

| reading | vs small-cell estimate | vs large-cell estimate |
|---|---:|---:|
| M2 **0.43967 g** | **0.88×** — a *cut* section is smaller than a whole cell, so a whole small cell at ~0.50 g is **consistent** | 0.29× |
| M1 **1.38279 g** | 2.76× | **0.93×** — close to a whole **large** cell |

**Interpretation (CORRECTED):** M2 is a single **small** cell and M1 a single **large** one — the
operator has since confirmed each size was weighed as a single panel *and* as a 10-piece pile.
Measured is **8–12 % BELOW** the density estimate, so these readings **retire** that estimate
rather than corroborating it. See `docs/analysis/MEASURED-MASSES.md`.

## This kills the "~2 g per cell" pessimistic spec

`docs/PAYLOAD-WEIGHT-ESTIMATES.md` carries two contradictory assumptions — *"~2 g per cell"* called
"heavy for pico balloon use" versus a *"~0.4 g/cell"* thin-film hope. **The measurements sit at
the low end:**

| assumption | 12-cell array (4 wings × 3) |
|---|---:|
| repo pessimistic spec, 2.0 g/cell | 24.00 g |
| repo optimistic hope, 0.4 g/cell | 4.80 g |
| **measured range, 0.43967–0.5006 g/cell** | **5.28–6.01 g** |

**So the real array is ~5.3–6.0 g — a quarter of the pessimistic figure, and very close to the
optimistic one.** The "2 g/cell" spec is **not supported by measurement** and should stop being
used as the conservative case.

## M7 IS the balloon envelope — 46.84 g is the envelope mass, and it IS array-budget relevant

**OPERATOR CLARIFICATION (2026-10-14, authoritative):**

> *"the marker isn't included in the weight. I zeroed the marker before weighing it. It was just
> there to hold the balloon in place so that it doesn't unfold while its being weighed. 46.84
> grams is the correct weight of the balloon. The marker isn't included in these 46.84 grams."*

So **M7 = 46.84 g = the Yokohama balloon envelope alone.** The marker was a *physical restraint*
(holding the folded envelope down so it did not unfold on the pan) and was **TARED OUT** — zeroed
before the envelope was placed on it. It contributes **zero** to the reading.

### Corrected: three earlier claims in this document were WRONG

| earlier claim in this document | corrected |
|---|---|
| M7 described as generic translucent film, unidentified, and separate from the array budget | It is the **balloon envelope** — a nylon/PE laminate, which is why it reads translucent. It **is** a usable measured input |
| M7 described as an unresolved combination of film plus a marker that vision could not separate | There is nothing to separate. The balance was **tared**; the marker was never in the measurement |
| M7 flagged as needing the operator to re-weigh the film on its own | **No re-weigh is needed.** The operator has resolved it: 46.84 g is the envelope. Item **CLOSED** |

*(The superseded wording is paraphrased rather than quoted: it is wrong, and a verbatim copy in
this file would be indistinguishable from a live claim to anything that greps the text.)*

The error was mine, not the operator's: a vision read of the pan could see a marker resting on the
film and could not know it had been tared. **A tare is invisible in a photograph** — that is a
limit of the method, and it should have been asked rather than recorded as an unresolved split.

### What this changes in the budget

`46.84 g` is now a **usable measured envelope mass** for the Yokohama 32″ — the last unknown in the
mass chain. It sits between the two community figures (41 g old valved / 48.6 g new valveless) and
**1.76 g below** the valveless figure the budget was using.

```
20.00 g   threshold (total-mass reading)
−46.84 g  envelope MEASURED (was −48.60 g community)
− 4.17 g  helium (20 g payload + 6 g free lift, 20 °C)
− 2.20 g  attachments
────────
−33.21 g  → still NO payload budget; the envelope alone is 2.34× the 20 g
```

The conclusion is unchanged, but the number is now measured rather than transcribed.
**GAP 1's envelope unknown is closed BY MEASUREMENT.**

## What these photos do NOT establish — stated, not hidden

- ~~Whether the balance was **tared** for each reading.~~ **RESOLVED for M7**: the operator tared the marker before weighing the envelope. For the cell readings no tare history is visible in the photos, but each size was weighed two independent ways and the two agree within 2 %, which is the check that matters.
- The **cell type** per reading (small `52.07 × 19.65` vs large `78.55 × 38.90`) — no label, no
  ruler in frame. **The M4/M5 vision note suggesting the large option is an inference, not a
  measurement.**
- Which reading maps to which **cell model number**.
- ~~**Length/width**, so a measured g/cm² cannot be derived.~~ **Resolved**: the repo carries the two outlines from ADR-049 (small 52.07 × 19.65 mm, large 78.55 × 38.90 mm), so g/cm² IS derivable — **43.00 / 45.23 mg/cm²** from the single-part readings. What is still unverified is only *which physical panel* maps to which outline by eye (no ruler in frame); the areal-density agreement between the two sizes (5 %) makes that a labelling question, not a mass question.
- ~~Whether the film in M7 is the envelope, and its mass without the marker.~~ **CLOSED** by the operator: M7 *is* the envelope, and 46.84 g already excludes the marker (tared).

## Consequence for the blocked items

- **GAP 1 (ORDER-BLOCKER)** — the mass budget targeted `"<14 g"` while the payload is ~57 g. This
  measurement **removes the largest single uncertainty in that reconciliation** (the solar
  array), but **does not close it**: the envelope mass is still unknown, and M7's 46.84 g net is
  an unresolved film+marker reading.
- ~~**Next input still needed from the operator:** the film alone (tared), and the envelope.~~ **BOTH CLOSED.** The envelope was weighed (46.84 g, marker tared out). No further operator input is needed for the mass chain — see `docs/analysis/MEASURED-MASSES.md` for the authoritative readings and `docs/analysis/wing_mass_model.py` for the model that now consumes them.

## Reproduce

```
cd tracker/hardware && python3 analyze_cell_measurements.py
```
