# OPERATOR CELL MEASUREMENTS (2026-10-14) — the mass budget's missing input, tested against the model

**Date:** 2026-10-14 · **Status:** measurements received and analysed. **They VALIDATE the repo's
Si-density cell-mass estimate and kill the "~2 g/cell" pessimistic spec.**

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
| M7 | `46.84 g` **NET** | **46.84000** | folded **translucent film** + an edding marker — **not a cell** |

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

**Interpretation:** M2 is a section of a **small** cell; M1 is a section of a **large** cell (or a
nearly-whole large cell). **Both readings corroborate the density model instead of contradicting
it** — which is the useful outcome, because the estimate was previously unmeasured.

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

## M7 is NOT array mass — do not add it

**46.84 g net = folded translucent film + a marker.** Vision could not separate the two, and
**could not confirm the film is the balloon envelope.** This is the **operator's** scale, so the
film-vs-marker-vs-net split is only resolvable by the operator re-weighing the film alone.
**Recorded as an open item, not silently folded into the budget.**

## What these photos do NOT establish — stated, not hidden

- Whether the balance was **tared** for each reading (no photo shows a tare history).
- The **cell type** per reading (small `52.07 × 19.65` vs large `78.55 × 38.90`) — no label, no
  ruler in frame. **The M4/M5 vision note suggesting the large option is an inference, not a
  measurement.**
- Which reading maps to which **cell model number**.
- **Length/width**, so a measured g/cm² cannot be derived — only the *mass* is measured.
- Whether the film in M7 is the envelope, and its mass without the marker.

## Consequence for the blocked items

- **GAP 1 (ORDER-BLOCKER)** — the mass budget targeted `"<14 g"` while the payload is ~57 g. This
  measurement **removes the largest single uncertainty in that reconciliation** (the solar
  array), but **does not close it**: the envelope mass is still unknown, and M7's 46.84 g net is
  an unresolved film+marker reading.
- **Next input still needed from the operator:** the **film alone** (no marker, tared), and the
  **envelope** on the scale — those are the remaining unknowns in the mass chain.

## Reproduce

```
cd tracker/hardware && python3 analyze_cell_measurements.py
```
