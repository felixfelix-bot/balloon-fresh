# Severing the wing: magnetic contacts, solenoids, and the electrical problem

**Date:** 2026-10-14 · **Status:** trade study, **extends** `docs/analysis/wing-jettison.md`
(which remains the primary release-mechanism study and is not contradicted here)

**Questions answered:**
1. Are there magnetic-contact components controllable by solenoid to drop the panels?
2. What are the tradeoffs of such components?
3. What are the options for disconnecting and dropping the panels?
4. We can burn nylon with nichrome — how do we sever the *electrical* contacts?

**Verdict: unchanged from `wing-jettison.md` §0 — do not build a release.** The electrical
question specifically has an answer that *removes* work rather than adding it (§4).

**Reproduce every number here:** `python3 docs/analysis/wing_release_electrical.py`

---

## 0. Answer first

| Question | Answer |
|---|---|
| Magnetic contacts + solenoid? | Yes, they exist (magnetic pogo, reed+coil, PM+electromagnet, latching solenoid). |
| Tradeoffs? | Magnetic holds are **active-hold**: 150–500 mW to stay attached, vs ADR-036's **100 µW** night budget = **>1500×**. Disqualifying alone (§2.3). |
| Options to disconnect electrically? | **Five** catalogued in §3. Four of them cost mass and add a joint. One (Option 1, do nothing) costs nothing. |
| How to sever the electrical contacts? | **You do not need to, and you must not try.** §4: the array is a **series string with bypass diodes DNP**, so opening any one wing's contact kills the entire array. |

**The one-sentence version:** the electrical-severance question is not a hard sub-problem of a
good idea — it is *the mechanism by which a bad idea destroys the mission*.

---

## 1. Components that exist (the catalogue)

All of these are real, off-the-shelf, and used in spaceflight or ruggedised electronics:

| Class | How it holds | How it releases | Static power |
|---|---|---|---|
| **Magnetic pogo / magnetic connector** | NdFeB magnet pair + spring-loaded contacts | pull force exceeded, or a separate pusher | **0 W** (passive hold) |
| **Reed switch + coil** | contacts sealed in glass, actuated by field | coil field opens/ closes | 0 W hold; ~10–30 mW while energised |
| **Permanent magnet + electromagnet (bucking)** | PM alone | coil generates *opposing* field to cancel the PM | 0 W hold; **200–500 mW** while cancelling |
| **Non-latching solenoid** | coil current | de-energise → spring returns | **150–400 mW continuous** |
| **Latching solenoid (PM + coil)** | PM (bistable) | short current pulse flips state | **0 W hold**; pulse only |

**The load-bearing distinction is hold vs release.** The wing must be held for *months* of
flight and released *once*. Any architecture that requires current to hold is paying
continuously for a one-shot event — and it fails *attached* if power dies, or fails
*detached* if power glitches. Both are bad, in opposite directions.

---

## 2. Tradeoffs, with the numbers

### 2.1 Holding force required

The wing mass is **3.2 g** (`wing-jettison.md` §7). So the magnet must resist:

| Load case | Force |
|---|---|
| Wing weight at 1 g | **31.4 mN** |
| Burst shock, 10 g-equivalent (assumed, §2.1 of the jettison study) | **314 mN** |
| Design margin 1.5× on the shock case | **471 mN** (≈ 48 gf) |

That is a modest force — a 3 mm × 1 mm NdFeB disc is already in range. **Force is not the
problem. Power and failure mode are.**

### 2.2 Cold behaviour — the tradeoff that works *against* you

NdFeB has a reversible temperature coefficient of about **−0.11 %/K** for Br near room
temperature. At **−60 °C** (stratospheric night) the flux is roughly **+8.8 % higher** than at
20 °C (computed). Two consequences, both awkward:

- Holding force **increases** in the cold — good for staying attached, which is not the
  direction you want a *release* to have margin in.
- Release force **increases** by the same +8.8 % at the exact moment the energy budget is at
  its worst (cold battery, post-night).

A magnet's temperature coefficient is therefore *backwards* for this application: it makes
the mechanism more certain to hold and less certain to release.

### 2.3 Power — the disqualifying number

| Architecture | Static draw | vs ADR-036 night budget (100 µW) |
|---|---|---|
| Passive magnetic hold | 0 W | — (fine) |
| Bucking electromagnet hold | 350 mW (class) | **3500×** the entire night budget |
| Non-latching solenoid hold | 250 mW (class) | **2500×** the entire night budget |
| Latching solenoid (pulse only) | ~0 W hold | fine, but see §2.4 |

`wing-jettison.md` §3.5 already flags that the nichrome design's *leakage alone* (never mind
firing) costs **22 % of the 100 µW night budget**. A solenoid hold is **three to four orders
of magnitude worse** than the flaw that already contributed to rejecting the nichrome design.

**Pulse energy is not the problem.** Releasing a latching mechanism costs
**0.002–0.15 J** versus **2.59 J** for the nichrome cut — the solenoid is *cheaper per shot* by
**17× (largest pulse) to ~1300× (smallest)**. The problem is the *hold*, and a latching device that holds for free is exactly the
device whose state you cannot verify (§2.4).

### 2.4 Latching is not a free lunch

A latching solenoid holds with no current — but it is **bistable**, meaning:

- It can **re-latch** if the pulse is mis-shaped or the mechanism bounces. There is no
  in-flight telemetry that the latch is open (same gap as `wing-jettison.md` failure mode #2).
- It needs the pulse at the one moment the rail is weakest (§3.4 of the jettison study
  derives the same `>3.3 V` supercap requirement).
- It adds a **magnetic circuit next to an 868 MHz receiver.** Stray field / fringing and any
  switching transient is an RFI question the repo has not analysed.
  `TODO(unverified)` — stray field at 868 MHz, and whether it is measurable on the LR2021 RSSI.

### 2.5 Mass

A micro magnetic connector pair plus a latching coil is plausibly **0.8–1.5 g per wing**
(commercial class figures; `TODO(unverified)` for the exact part). Four wings =
**3.2–6.0 g carried all flight**, against `wing-jettison.md`'s 2.0 g for the nichrome design
and its 3.2 g shed. **Mass-negative, and worse than the design already rejected.**

---

## 3. The five ways to disconnect electrically

| # | Option | How the copper opens | Added mass | Verdict |
|---|---|---|---|---|
| **1** | **Do nothing — keep the 4-pin soldered tab** | it does not open (by design) | **0 g** | **RECOMMENDED** (§5) |
| **2** | **Slip-fit socket** — tab stays, socket pulls out | pull-out force from the release | ~0.2–0.5 g/wing | Feasible *if* a release is mandated. Needs a measured pull-out force window: high enough for vibration, low enough for the actuator. |
| **3** | **Magnetic contact pair** (§1) | contacts separate as the magnet releases | 0.8–1.5 g/wing | Rejected on power (§2.3) and RFI (§2.4). |
| **4** | **Keeper + slip-fit** — actuator holds a *keeper*, not the joint | the slip-fit opens passively when the keeper releases | ~0.5–1.0 g/wing | **The only elegant variant.** Decouples "hold" from "conduct": no copper is ever cut. |
| **5** | **Sever the copper as well** | dedicated nichrome per conductor | ≥4× the nichrome design | Rejected: see §4.2. |

**Option 4 is the interesting one**, because it inverts the problem: instead of cutting the
electrical path, you make the electrical path a **slip-fit that is only held closed by the
mechanical keeper**. Release the keeper and the contacts simply part. No copper is cut, no
extra channels, and the contact resistance stays a normal pogo/tab figure for the whole
flight.

---

## 4. How to sever the electrical contacts — and why you must not

### 4.1 Cutting copper is a different problem from cutting nylon

| Material | Melt point | Thermal conductivity |
|---|---|---|
| Nylon (the tether) | ~260 °C | ~0.25 W/(m·K) |
| Copper (the conductor) | **1085 °C** | **~400 W/(m·K)** |

Copper conducts heat away about **1600× faster** and needs **~4× the temperature rise**. A
nichrome element sized for nylon will not cut copper — it will *conduct into the copper* and
heat the whole nearby run instead of severing it. Cutting a conductor needs roughly an order
of magnitude more energy, plus a fixture that stops the heat from escaping down the very wire
you are trying to cut. `TODO(unverified)` — no in-repo test of nichrome-vs-copper.

### 4.2 …but the decisive reason is the array topology

From **`docs/adr/046-wing-board-interface.md` §2.3**: the four wings are wired as **one series
string** (*"All four wings are in series, so the string current is set by the weakest element"*),
and the per-slot bypass Schottky is **DNP for the first prototype build**. The ADR states the
consequence directly: *"without a bypass path the whole string's current collapses"*.

```
  wing1 ── wire ── wing2 ── wire ── wing3 ── wire ── wing4
    │                                                  │
    └────────────── series string → MPPT ──────────────┘
         bypass per wing: DNP  →  one open = 0 W everywhere
```

So:

- **Opening one wing's contact does not "drop one panel". It drops all four.** The string
  goes open and the array delivers **0 W** — the mission's science instrument is the array.
- This is exactly `wing-jettison.md` failure mode **#1 (Premature release, severity 5,
  mission-ending)** and it is fatal "and worse than losing 25 %".
- Which means the electrical severance is **not a sub-problem you solve to enable a release.
  It is the failure mode the release is supposed not to cause.**

**Therefore the answer to "how do we sever those?" is: you design so that you never have to.**
If a release exists at all, the electrical path must open **as a consequence of the mechanical
release** (Option 2 or 4), not as a second deliberate action — because a deliberate cut of the
wrong conductor is indistinguishable from the mission-ending failure you were trying to avoid.

### 4.3 And the electrical joint is currently the *only* thing holding the wing

`wing-jettison.md` §0 finding 3: on v9 the **4-pin soldered tab is the wing's only electrical
connection**, and replacing it with a release breaks it (ADR-046 §2.1). A release that
disconnects electrically therefore removes the wing's only structural *and* electrical
interface at once — which is why the jettison study notes that a string attachment "degrades
the structure as well as the connection".

---

## 5. Cost/benefit, and the recommendation

| Design | Mass carried all flight | Shed on release | Net |
|---|---|---|---|
| Nichrome + nylon (`wing-jettison.md`) | 2.0 g | 3.2 g | −1.2 g net, but buys 11 % of a walking-pace descent |
| **Magnetic/solenoid (this study)** | **3.2–6.0 g** | 3.2 g | **mass-negative by 0–2.8 g** |
| **Do nothing** | **0 g** | 0 g | **0 g** |

**Recommendation: Option 1 — do nothing.** Unchanged from `wing-jettison.md` §5 option G, and
the magnetic/solenoid family does not change it; it makes the trade worse by every axis
(power, mass, RFI, failure mode).

If a release is nonetheless mandated:

1. Use **Option 4** (keeper + slip-fit) — never cut the copper (§4.2).
2. Arm it **descent-only**, as `wing-jettison.md` §5 already specifies.
3. Accept the honest accounting: the release buys **11 %** of a descent rate that is already
   ~**0.45 m/s**, which is walking pace.

If the underlying worry is the **flimsy soldered tab**, the correct lever is the tab/socket
joint (ADR-046 §4.4; ADR-049 clause 4) — **not** a release. That is `wing-jettison.md`'s
recommendation and this study does not change it.

---

## 6. Open items (nothing silently assumed)

- `TODO(unverified)` — exact part number and mass for a micro magnetic connector pair at this
  holding-force class (0.8–1.5 g/wing is a commercial-class estimate, not a datasheet figure).
- `TODO(unverified)` — NdFeB reversible coefficient at −60 °C for the specific grade; the
  +9 % flux figure here uses a generic −0.11 %/K.
- `TODO(unverified)` — stray magnetic field and switching transient at 868 MHz versus the
  LR2021 receiver; not analysed anywhere in the repo.
- `TODO(unverified)` — nichrome-vs-copper cutting energy; no in-repo test. The 1600× / 4×
  figures in §4.1 are physical constants, not measured cut results.
- `TODO(unverified)` — slip-fit pull-out force window (vibration lower bound, actuator upper
  bound); needs a bench measurement before Option 2/4 could be committed to.
- `TODO(unverified)` — whether a per-wing bypass diode could be fitted (currently DNP); if it
  were **fitted**, failure mode #1 changes from "array dead" to "one wing lost". That single
  part is the highest-leverage change if a release is ever seriously wanted.
