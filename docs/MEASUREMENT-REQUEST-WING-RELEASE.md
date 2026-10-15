# MEASUREMENT REQUEST — what the operator needs to weigh, pull and measure

**Date:** 2026-10-14 · **From:** balloon-hermes (manager CW) · **To:** Felix (operator)
**Context:** `docs/HANDOVER-WING-RELEASE-AND-BYPASS-DIODE.md` §4.3 lists two blocking numbers as
`TODO(unverified)`. This document turns them into bench instructions, and adds a third that is
**cheaper than both and supersedes an assumption** the whole force window rests on.

---

## 0. Summary — three measurements, in priority order

| # | What | Why it blocks | Difficulty | Time |
|---|---|---|---|---|
| **A** | **Weigh one real wing** (bare FR4 + 3 soldered cells, no glue) | The 10 g shock force, the whole force window, and the pull-out spec all scale with this — and 3.2 g is an **estimate**, not a measurement | Trivial | 2 min |
| **B** | **Nylon loop break load** | The keeper holds the slip-fit closed **through the nylon loop**; if a knot-able cord cannot carry ~490 mN at −60 °C, the concept needs a different keeper before any layout | Easy | 20 min |
| **C** | **Contact resistance** (only after a connector is chosen) | Sets the electrical budget and the MPPT headroom | Needs a part first | 30 min |

**Do A first.** It is the cheapest and it re-derives the number everything else depends on.

**And a note on honesty:** measurement C cannot be done today, because no connector has been
selected yet — "contact resistance of the chosen slip-fit" is circular until the slip-fit exists.
So the request below splits C into **C1 (which class of connector)** and **C2 (measure the chosen
one)**. That split is not pedantry: it is the difference between a bench task and a design task.

---

## 1. Measurement A — weigh one real wing

**Why it matters more than it looks.** `docs/analysis/wing-jettison.md` §7 uses **3.2 g per wing**.
That figure is an estimate. Every force below is proportional to it:

| Wing mass | 1 g load | 10 g shock | ×1.5 margin (design lower bound) |
|---|---|---|---|
| 3.20 g *(current estimate)* | 31.4 mN | 314 mN | **471 mN** |
| 4.15 g | 40.7 mN | 407 mN | **610 mN** |
| 5.00 g | 49.0 mN | 490 mN | **735 mN** |
| 6.00 g | 58.8 mN | 588 mN | **883 mN** |

If a wing turns out to be 5 g rather than 3.2 g, the required holding force rises by **56 %** —
and that decides whether a small slip-fit is adequate or a heavy one is needed. The whole design
hinges on a number nobody has measured.

**What to weigh:** the wing as it will fly — FR4 substrate, three soldered cells, **no** temporary
jig, **no** tape, **no** glue you would not fly with.

**Protocol (the tare rule applies — see the skill):**
1. Put the wing flat on the scale. If you need a marker or clip to stop it sliding off, **zero the
   scale with the fixture in place first**, exactly as you did for the balloon.
2. Record the single-wing mass in grams to 0.001 g if the milligram scale will take it; otherwise
   0.01 g on the gram scale is fine.
3. Ideally weigh **two** wings and report both — the spread tells us the build repeatability.

**Report:** `wing mass = ___ g` (and the second one if you weigh it).

**What I do with it:** recompute the force window, the keeper's release-force requirement, and the
mass budget in `docs/analysis/wing-jettison.md` §7.

---

## 2. Measurement B — nylon loop break load

**Why it matters.** The keeper concept is: *a nylon loop holds the slip-fit closed; nichrome cuts
the loop; the contacts part passively.* That means **the nylon loop carries the same load as the
joint** — roughly **314–490 mN** depending on A. So a pre-condition of the whole design is:
**can a cord you can actually knot carry ~0.5 N without creeping or breaking?**

`docs/analysis/wing-jettison.md` §2 already found the load-driven diameter would be
**0.02–0.10 mm** — unbuildable — and that "any cord you *can* knot is ~100× stronger than the
load". If that is right, B passes trivially and the concept is fine. **B exists to check that the
study's own conclusion still holds for a loaded loop, not just a static tether.**

**Protocol:**
1. Tie the loop termination you would actually fly.
2. Hang known masses from it — a jug of water is fine; add water in steps.
3. Record the mass at which it **creeps** (stretches and slips) and at which it **breaks**.
4. Report both, and the cord type/diameter you used.

**Cheap version:** if you have a kitchen scale and a jug, this is a 20-minute exercise at room
temperature. **Cold/vacuum behaviour stays `TODO(unverified)`** — the repo has no −60 °C chamber,
and I will not pretend a room-temperature break test answers it.

**Report:** `cord = ___ (type/diameter), creep at ___ g, break at ___ g`.

---

## 3. Measurement C — contact resistance

**C1 — the prior question (design decision, not a measurement).** Pick the contact **class**
first. The options, with the electrical consequence:

| Class | Typical contact R | Loss at 400 mA | Verdict |
|---|---|---|---|
| Gold-plated pogo / spring pin | 20–50 mΩ | 3–8 mW | **Best electrical**; needs a normal force |
| Edge-connector / castellated slip-fit | 50–200 mΩ | 8–32 mW | Simple; R depends on fit and plating |
| Pin-header friction fit (0.1 in) | 20–50 mΩ | 3–8 mW | Cheap, but bulky and not vibration-proof |
| Soldered tab *(today)* | < 10 mΩ | < 2 mW | Reference only — solder, not a slip-fit |

The target: **< 100 mΩ**, i.e. **≤ 0.67 % of the 2.4 W harvest** and **≤ 40 mV** of the 6.0 V stack.

**C2 — measure the chosen one.** 4-wire (Kelvin) measurement:
1. Force **400 mA** through the contact pair.
2. Measure the voltage **across the contact only** (not the leads).
3. `R = V / 0.4` — report in mΩ.
4. Repeat with the part in a freezer (or a bag of ice + salt) for the cold figure.

**Why 400 mA and not 1.2 A:** 400 mA is the per-wing daytime harvest current (ADR-046 §2.3). The
1.2 A figure is the *string* current when two wings are shaded — a transient. Both matter, but the
400 mA case is the one that runs for hours.

**Do not do C2 until C1 is chosen.** Measuring a random connector tells us nothing about the part
we will fly.

---

## 4. Why there is no fourth measurement (and where the real risk actually sits)

The wing-board routing defect (`t_273cbf1a`) and the SSOT drift (`t_b6eb2562`) are **not**
measurements — they are repairs, and they are already carded. **Do not fold them into this.**

The genuinely unmeasurable items stay `TODO(unverified)` and I will not invent them:
- Nylon behaviour at −60 °C **in vacuum** (outgassing raises T_g; the repo has no chamber).
- Nylon **knot/loop termination** strength (the real weak link — §6 of the jettison study).
- The **actual peak shock at balloon burst** — assumed 10 g-equivalent, unsourced.

**If you can only do one thing: weigh a wing (A).** It is the difference between a design based on
an estimate and one based on your own scale — the same distinction that has now mattered three
times in this project (the envelope, the cells, and this).
