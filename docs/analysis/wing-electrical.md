# Wing electrical analysis — series/parallel matching, mixed-cell wings, shading bypass, charge path, conductor sizing

> **STATUS: CONSULTANT ANALYSIS — NOT A DECISION RECORD.**
> This is a reasoned electrical analysis with numbers, produced for the operator to
> decide on. It is **not** an ADR, it does **not** amend ADR-006 / ADR-046 / ADR-047 /
> ADR-048, and nothing here may be read as an accepted design. Every number is either
> (a) computed with its formula shown, (b) cited to an in-repo document, or
> (c) marked `TODO(unverified)` with the open question named. Where this analysis
> disagrees with an accepted record it says so explicitly and does not silently
> override it.

| | |
|---|---|
| Date | 2026-10-07 |
| Author | subagent (Hermes), branch `analysis/wing-electrical` |
| Base commit | `76dd04d` (tip of `main`, = tip of `github/main` and `ngit/main` at the time of writing; verified with `git ls-remote`) |
| Lens | **electrical, matching and protection** (not board layout, not mechanical) |
| Scope ruled out | no board code, no schematic edit, no BOM change in this document |

## 0. Inputs (given; cited, not re-derived)

### 0.1 Solar cells in hand — GIVEN FACTS

| Cell | Dimensions (caliper / listing) | Area | Listing | Pads |
|---|---|---|---|---|
| **SMALL** | 52.07 × 19.65 × 0.20–0.21 mm | **10.23 cm²** | 0.5 V / 400 mA | 1 front + 1 back (caliper-measured) |
| **LARGE** | 78.55 × 38.90 × 0.21 mm | **≈30.6 cm²** | 0.54 W / 0.5 V (repo listing) | pad layout **unconfirmed**; current inferred ≈1.2 A by area |

Both polycrystalline. ~100 small panels in hand; number of large unknown
(`docs/adr/006-supercapacitor-power.md` §Komponenten: *"Prototyp: 78x39mm (0.54W, 0.5V) -
bereits vorhanden (50er Pack)"*; `docs/component-guide.md:108`; `docs/coordination/INDEX.md:284`).

```
small area  = 52.07 mm × 19.65 mm = 1 023.2 mm² = 10.232 cm²      (matches the 10.23 cm² given)
large area  = 78.55 mm × 38.90 mm = 3 055.6 mm² = 30.556 cm²      (matches "≈30.6 cm²" given)
area ratio  = 3 055.6 / 1 023.2 = 2.986  ≈ 3.0
```

### 0.2 A conflict in the given/listed numbers that must be stated, not hidden

The **area-scaling** inference of the large cell's current and the **listing**
figure disagree:

```
by area:   I_large = I_small × (A_large / A_small) = 0.400 A × 2.986 = 1.194 A  ≈ 1.2 A   [given]
by listing: P_large = 0.54 W at 0.5 V  →  I_large = 0.54 / 0.5 = 1.080 A
```

The task fixes the large cell at **≈1.2 A**; this analysis uses 1.2 A throughout as the
given figure. The listing implies 1.08 A, i.e. the large cell may be **10 % weaker** than
area-scaling suggests (larger cells are often fractionally less efficient).
`TODO(unverified)` — **the large cell's actual short-circuit / maximum-power current; the
listing "0.54 W" and the 1.2 A area-scaling figure have never been reconciled by a
measurement.** Every large-cell current number below scales linearly with this choice.

### 0.3 Architecture inputs (cited)

| Symbol | Value | Source |
|---|---|---|
| ADR-006 | 4 wings × 3 cells in series = **1.5 V/wing**, **12 cells**, **6.0 V @ 400 mA = 2.4 W** peak | `docs/adr/006-supercapacitor-power.md` (Status **Akzeptiert**); `docs/POWER-BUDGET-V9-D2BE.md:29-33`; `docs/SOLAR-PIN-REGULATORY.md:11` |
| ADR-046 | 4-pin wing tab: 1 `SOLAR_P`, 2 `GND`, 3 `RF_FEED` (V2-only, unused on v9), 4 `SOLAR_N`; **hub owns the series chain**, GND returned only at the stack bottom; **DNP bypass Schottky per wing** | `docs/adr/046-wing-board-interface.md` §2.1, §2.3, §6 |
| ADR-046 wing outline | **176.0 × 25.0 mm** body + 8 × 9 mm tab (184 mm total) | `docs/adr/046-wing-board-interface.md` §3.2 |
| ADR-046 cell lands | 1.6 × 4.0 mm per cell terminal; 6 lands; cells laid **52 mm along length, 19 mm across width** | `docs/adr/046-wing-board-interface.md` §3.3, §3.4 |
| Tab land geometry | **4.0 × 1.2 mm**, 1.8 mm pitch; bypass diode part suggestion "BAT54 family, SOD-323 or SMA" | ADR-046 §2.2; `docs/WING-TO-HUB-SOCKET-SPEC.md` §2, §5 |
| ADR-047 | radio max **1118 mA at 5.5 V = 6.15 W**, fed **PRE-LDO** from the raw supercap node; bank doubled to **3.3 F at 5.4 V**; **boost REFUSED**; rail monitor + firmware TX-inhibit; radio VCC max 5.5 V **with no absolute-maximum table published**; array open-circuit voltage at −60 °C **UNMEASURED** | `docs/adr/047-v9-power-provisioning.md` §1, §2.2, §5, §7 |
| Charge element | **BAT54 Schottky** between stack top and supercap bank | ADR-006; ADR-047 §2.1 |
| Hub sockets | 4 identical, series-wired W1→W2→W3→W4 on the hub, one DNP bypass (BAT54 family, SOD-323) per socket | `docs/adr/048-v9-hub-wing-interfaces.md` §2.3 |

---

## 1. The series / parallel rule, and what a mismatched series pair throws away

### 1.1 The rule

> **SERIES RULE.** In a series string every element carries the *same* current (there is one
> path — Kirchhoff's current law). Therefore the string current is **limited by the
> lowest-current element**, and each element's *voltage* adds.
>
> **PARALLEL RULE.** In a parallel group every element sits at the *same* voltage, and the
> currents **add**; the group current is the sum of what each element can source at that
> voltage.

For photovoltaic cells this is the operating-point statement: a cell is a current source
squelched by its own area-proportional photocurrent. In **series**, the smallest-area cell
(i.e. the smallest photocurrent) sets the current for the whole string. In **parallel**,
identical-voltage cells simply sum.

### 1.2 Worked example — one LARGE in series with one SMALL

Given: large ≈1.2 A, small ≈0.4 A, both nominal 0.5 V.

```
Series current          I_string = min(I_large, I_small) = min(1.2 A, 0.4 A) = 0.4 A
Series voltage          V_string = 0.5 V + 0.5 V = 1.0 V
Pair power              P_pair   = 1.0 V × 0.4 A = 0.40 W

Large cell's own capability   P_large,cap = 0.5 V × 1.2 A = 0.60 W
Large cell's actual output    P_large,act = 0.5 V × 0.4 A = 0.20 W   (throttled to the small's current)

THROWN AWAY              ΔP = 0.60 W − 0.20 W = 0.40 W
PERCENT                  ΔP / P_large,cap = 0.40 / 0.60 = 66.7 %
```

**66.7 % of the large cell's capability is discarded — 0.40 W of 0.60 W — pushed as
excess voltage across the small cell's impedance and dissipated there.**

The clarifying consequence: the **pair (0.40 W) is worse than the large cell running
alone (0.60 W)**. A series string that contains one mismatched small cell is not merely
"limited to the small cell"; it is *worse than not using the small cell at all*.

`TODO(unverified)` — the exact mismatch loss at the true operating point depends on both
cells' I-V curves (fill factor, shunt resistance) which are not measured. The 66.7 %
figure is the first-order photocurrent-limited result and is the number to plan against.

---

## 2. Is a MIXED WING electrically sensible?

### 2.1 Current-matching a series position

One series position must present the **same current** as its neighbours (series rule, §1.1).
To match one large cell (1.2 A) with small cells (0.4 A):

```
n = I_large / I_small = 1.2 A / 0.4 A = 3.0   → exactly 3 small cells in PARALLEL per position
```

**Accepted tolerance: ±10 % on the summed parallel-group current**, i.e. a group is a valid
match to a 1.2 A large cell if it delivers **1.08 … 1.32 A**.

Justification of the tolerance (not guessed):
- In a **series** chain a current deficit is a *direct, undiluted* power loss:
  `loss_fraction = (I_match − I_group)/I_match`. A −10 % group costs the whole string
  **10 % of its power**. That is why the tolerance cannot be loose.
- A **3-cell parallel group averages** its members: if each small cell varies by ±10 %,
  the group's spread is ≈ `10 %/√3 = 5.8 %`. So **3 paralleled small cells are a
  *tighter* current source than a single large cell** — the practical match is usually
  inside ±6 %, and the ±10 % limit is the reject threshold, not the typical error.
- `TODO(unverified)` — the small cells' actual per-cell current spread (vendor tolerance,
  binning) has never been measured on the 100-cell batch in hand. The ±10 % group
  tolerance is a stated engineering choice, not a measurement.

### 2.2 Power of three wing arrangements, all at 1.5 V/wing (3 series positions)

Each position is 3 cells in series-equivalent (3 series positions × ≈0.5 V = 1.5 V/wing).

**(a) 3 series positions × (3 smalls in parallel)**

```
position current = 3 × 0.4 A = 1.2 A ;  position voltage = 0.5 V ;  P_pos = 0.6 W
wing  I = min = 1.2 A ;  V = 3 × 0.5 V = 1.5 V
P_wing = 1.5 V × 1.2 A = 1.80 W      cells = 9 small
```

**(b) 3 series positions × (1 large)**

```
position current = 1.2 A ;  position voltage = 0.5 V ;  P_pos = 0.6 W
wing  I = 1.2 A ;  V = 1.5 V
P_wing = 1.5 V × 1.2 A = 1.80 W      cells = 3 large
```

**(c) 3 series positions × (1 large ∥ 3 smalls)**

```
position current = 1.2 A + 3 × 0.4 A = 2.4 A ;  position voltage = 0.5 V ;  P_pos = 1.2 W
wing  I = 2.4 A ;  V = 1.5 V
P_wing = 1.5 V × 2.4 A = 3.60 W      cells = 3 large + 9 small = 12
```

### 2.3 Harvest per wing **and per soldered joint**

Joint-counting model (stated, so it is reproducible): each cell requires **2 soldered
terminal joints** (front + back pad), and a 3-position series chain requires **2
inter-position links**:

```
joints = 2 × N_cells + (positions − 1) = 2·N_cells + 2
```

| Arrangement | Wing power | Cells | Joints | **W / joint** | Buildable on the 176 × 25 mm wing? |
|---|---:|---:|---:|---:|---|
| (a) 3 × (3 small ∥) | 1.80 W | 9 small | 20 | **0.090** | No — 92.1 cm² of cells vs 44 cm² wing area (§3) |
| (b) 3 × (1 large) | 1.80 W | 3 large | 8 | **0.225** | No — a 78.55 × 38.90 mm cell does not fit a 25 mm-wide body (§3.1) |
| (c) 3 × (1 large ∥ 3 small) | **3.60 W** | 12 | 26 | 0.138 | No — 183.8 cm² of cells on a 44 cm² wing |

**Answer to "which maximises harvest per wing and per joint":**
- **Per wing: (c) at 3.60 W** — but (c) is *not buildable on the current outline* (it needs
  ~184 cm² of cell area per wing against a 44 cm² wing). It is a comparison point only.
- **Among buildable arrangements, (a) and (b) tie at 1.80 W/wing.**
- **Per joint: (b) wins at 0.225 W/joint — 2.5× (a) and 1.6× (c).** (b) uses one third of
  the cells and 40 % of the joints of (a) for the *same* wing power.
- **Per unit wing area: (a) wins** (40.9 mW/cm² on a 44 cm² wing vs 15.7 mW/cm² for (b)
  on the ~115 cm² wing (b) needs). Since wing area is the cube span and the mass budget,
  the choice between (a) and (b) is a **mass/area trade, not a power trade**.

### 2.4 Verdict on a mixed wing

A **mixed wing is electrically sensible only as cell-paralleling inside a position** (§2.1,
3 smalls ∥ = 1 large), and even then it is **worse per joint** than using one large cell.
Mixing is **not sensible across positions within a series string** (§1.2: −66.7 % on the
large element) and **not sensible across wings** (§3 scenario c). On the current
176 × 25 mm outline, **no mixed arrangement fits at all** (§3).

---

## 3. If a WHOLE SIZE CLASS is omitted, does the array still work?

### 3(a) ONLY LARGE cells

To keep 1.5 V/wing you still need **3 cells in series per wing** (cell voltage ≈0.5 V
regardless of size):

```
cells per wing  = 3 large        (series, 1.5 V)
cells per array = 3 × 4 = 12 large
array voltage   = 4 × 1.5 V = 6.0 V nominal          ← UNCHANGED vs the accepted records
array current   = 1.2 A                              (large-cell current, series-limited)
array peak      = 6.0 V × 1.2 A = 7.20 W             (vs 2.4 W for the 12-small array)
```

- **Does it still equal the 6.0 V nominal the accepted records assume?  YES.** Cell
  voltage is ~0.5 V for both sizes; 12 in series = 6.0 V. The voltage premise of
  ADR-006 / ADR-046 / ADR-047 is preserved by a 12-large array.
- **Does the wing outline change?  YES — it must.** A 78.55 × 38.90 mm cell:
  - 38.90 mm **does not fit the 25 mm wing width** (38.90 > 25), in **either orientation**
    (the other dimension, 78.55 mm, is worse);
  - 3 cells × 78.55 mm = 235.65 mm **does not fit the 176 mm length** either.
  Re-deriving with the ADR's own margin convention (a 19 mm cell in a 25 mm width = 3 mm
  each side) and its 6 mm land gap:

```
width  = 38.90 + 3 + 3              = 44.90 mm
length = 3 × 78.55 + 2 × 6 + 4 + 4  = 255.65 mm  (+ 8 mm tab = 263.65 mm total)
wing area = 255.65 × 44.90 mm       = 11 478 mm² = 114.8 cm²   vs the accepted 44.0 cm²  → ×2.6
```

- **Mass:** `docs/component-guide.md:108` gives the 78×39 mm cell at ~2 g vs the 52×19 mm at
  ~0.5 g → 12 large ≈ 24 g vs 12 small ≈ 6 g. `TODO(unverified)` — the mass table in
  `docs/POWER-BUDGET-V9-D2BE.md` marks all 12 cells `TODO(unverified)`; the per-cell masses
  are from `component-guide.md`, not weighed.
- **Historical note:** the 78×39 mm cell was previously specified for the **dev board with a
  boost converter** (`docs/hardware-design.md:196-202`, *"Boost Converter | Ja (78x39mm
  Zellen)"*). ADR-047 **refuses** a boost. Using only large cells therefore re-opens the
  6-cell series → boost-to-5 V plan that ADR-047 closed, unless the 12-cell 3 V-per-wing
  series arrangement is kept (which it can be — 12 large cells still make 6.0 V).

### 3(b) ONLY SMALL cells

Two sub-cases. Baseline = the accepted 12-cell array.

**(b-i) Baseline 12 small cells (3/wing).** This *is* the accepted array:
`6.0 V @ 0.4 A = 2.4 W`. Works, but the current is 0.4 A, i.e. one third of the large array.

**(b-ii) Match the large-cell current (1.2 A) with small cells** — requires 3 smalls in
parallel per position (§2.1):

```
cells per wing   = 3 positions × 3 parallel = 9 small      (extra cells vs baseline = 9 − 3 = +6, +200 %)
cells per array  = 9 × 4 = 36 small
array voltage    = 6.0 V nominal                             ← UNCHANGED
array current    = 1.2 A
array peak       = 6.0 V × 1.2 A = 7.20 W                    (same as the 12-large array)
solder joints/wing = 2 × 9 + 2 = 20 joints                   (vs 8 for the 3-small baseline, vs 8 for 3 large)
```

- **Extra cells to match:** 36 small vs 12 large, i.e. **3× the cells** (and 6 extra per wing
  over the baseline). The 100-cell stock supports ~11 matched wings, i.e. ~2.7 flight sets.
- **Solder joints per wing: 20**, versus **8** for the 3-large wing (§2.3) — **2.5× the
  joints for the same 1.8 W/wing.**
- **Wing outline for 9 smalls:** unavoidable — 9 × 10.23 = 92.1 cm² of cell area will not
  fit a 44 cm² body. Best packing (3 across, 3 deep):

```
width  = 3 × 19.65 + 6      = 64.95 mm
length = 3 × 52.07 + 2 × 6 + 8 = 176.21 mm
wing area = 176.21 × 64.95  = 11 444 mm² = 114.4 cm²
```

  (One-across packing is far worse: 9 × 52.07 ≈ **469 mm** long.) So a *matched small* wing
  and an *only-large* wing are **the same area to within 0.3 %** (114.4 vs 114.8 cm²) — the
  real difference is **mass** (4.5 g small vs 6 g large) and cell-count flexibility, not size.

### 3(c) Both present, but on SEPARATE wings (some all-large wings, some all-small wings)

Two cases.

**c-i — all-small wings at the baseline 3 cells (unmatched):**

```
large wing: 1.5 V @ 1.2 A   (capability 1.80 W)
small wing: 1.5 V @ 0.4 A   (capability 0.60 W)
series array current = min(1.2, 0.4) = 0.4 A       (series rule, §1.1)
array voltage = 4 × 1.5 V = 6.0 V ;  array peak = 6.0 × 0.4 = 2.40 W
per large wing: capable 1.80 W, delivers 0.60 W  →  1.20 W thrown away
two large wings: 2 × 1.20 = 2.40 W thrown away
```

**c-ii — all-large wings + matched (9-cell) all-small wings:** array = 6.0 V @ 1.2 A =
7.20 W, but this needs 9-cell small wings (114.4 cm², §3(b-ii)) and is therefore
practically the same as just building all-large wings.

**Compatibility with the hub-owned series chain and the ADR-046 bypass diodes:**

| Question | Answer |
|---|---|
| Does the hub series chain still work? | **Yes, structurally.** The hub wires W1→W2→W3→W4 in series and each wing is a floating 1.5 V source with 2 solar terminals (`docs/adr/048-v9-hub-wing-interfaces.md` §2.3). The hub does not know or care what cell size a wing carries, and every wing is still 1.5 V. |
| What actually happens electrically? | With **unmatched** wings (c-i) the array collapses to the **smallest wing's current (0.4 A)** and **2.40 W is thrown away** in the two large wings — the same field-relevant trap as ADR-046 §2.3's shading, but **permanent**, not transient. |
| Is that compatible with the ADR-046 DNP bypass Schottky? | **Only partially, and not as a design.** The per-wing bypass diode is *across the whole wing*. It can bypass a **current-starved** wing — but for c-i the current-mismatch reverse-stresses the small wings whenever the load tries to draw > 0.4 A, so with the diodes **fitted** the array degrades to `3 × 1.5 V = 4.5 V` (the small wings dropped); with the diodes **DNP** (the first prototype, per ADR-046 §2.3 / ADR-048 §2.3) the small wings are **reverse-stressed** and the array current collapses. Either way the mixed-by-wing array loses or damages cells. |
| Verdict | **Mixed-by-wing is NOT compatible with the intended design.** It re-introduces the shading failure mode permanently. Mix **inside** a position (§2.1) or **don't mix at all**. |

**Overall answer to Q3:** the array still *works* electrically in every scenario — the
**6.0 V nominal is preserved by any 12-cell series arrangement** because cell voltage is
size-independent — but **every scenario except the all-small baseline forces either a wing
outline change (a, b-ii) or a permanent current-mismatch loss (c-i)**. The size class is
therefore **not** a free choice; it is a wing-geometry and diode-rating decision.

---

## 4. Shading and bypass

### 4.1 Model — one shaded wing in the 6.0 V series chain

Four wings in series, each 1.5 V, nominal string 6.0 V @ 0.4 A. Wing *k* goes fully dark.

**Without any bypass:**

```
string current = shaded wing's current ≈ 0  (diffuse only)
array peak     → falls from 6.0 V × 0.4 A = 2.40 W to ≈ 0
the other 3 wings (≈4.5 V of drive, up to 0.4 A) are forced through the shaded wing's
3 cells in REVERSE:
  dissipation in the shaded wing = 4.5 V × 0.4 A = 1.80 W over 3 cells = 0.60 W / cell
```

A solar cell dissipating **0.60 W in reverse** is a **hot spot** — the classic
cell-degradation mechanism ADR-046 §2.3 already names (*"a hot-spot / cell-degradation
risk, not just a power loss"*).

**With the ADR-046 per-wing bypass Schottky (cathode to `SOLAR_P`):** the shaded wing is
shunted, the remaining 3 wings deliver:

```
array = 3 × 1.5 V = 4.5 V @ 0.4 A = 1.80 W      (diode drop ≈ 0.3 V × 0.4 A = 0.12 W)
```

This is why the diode is mandated. **This part of ADR-046 is sound.**

### 4.2 Is the per-wing bypass Schottky SUFFICIENT?

It is sufficient **only** for the all-four-wings-identical, *fully*-shaded-wing case. It is
**not sufficient** for two cases this task forces onto the table:

1. **Partial shading within a wing.** If *one cell* of a wing is shaded, the wing still
   sources ≈1.0 V from its two lit cells; the wing's terminal voltage stays positive, so
   the per-wing diode (across the wing) **never turns on** and the shaded cell is
   reverse-stressed by the wing's own other cells. A per-wing bypass cannot protect a cell
   inside its own string → needs **per-cell** bypass.
2. **Once cells are PARALLELED in a position** (which is exactly what a mixed/matched wing
   does — §2.1, §3(b-ii)). In a parallel group of 3 smalls, if one cell is shaded the other
   two **drive current backward through it** at the common node voltage; again the
   per-wing diode cannot act on an intra-position imbalance → needs **per-cell** (or at
   minimum **per-position**) bypass. Per-position bypass protects a group from the rest of
   the string but does **not** protect cells *inside* the group from each other, so once
   cells are paralleled the correct provision is **per-cell bypass**.

**Conclusion:**
- **One size class, unmatched, cells in series only, full-wing shading** → the ADR-046 DNP
  per-wing Schottky is sufficient (as an unpopulated provision). Keep it.
- **Any paralleled position (mixed or matched wing)** → the per-wing diode is **not
  enough**; add **per-cell bypass Schottky** (one across each cell), or at minimum
  per-position, and be explicit that per-position does not protect within the group.

### 4.3 Diode type and ratings (from the currents above)

Two ratings bracket everything:

```
By-pass forward current  I_F : must carry the FULL string current.
   accepted small array  = 0.4 A
   large / matched array = 1.2 A      (ADVERSITY CASE FOR RATING)
   spec with 1.5× margin = 1.5 × 1.2 A = 1.80 A  → specify I_F ≥ 2 A
Reverse voltage          V_R : must block the other wings' combined voltage, plus the
   cold-Voc excursion (§5):  the other 3 wings ≈ 4.5 V + margin, and the array's own
   cold open-circuit voltage (§5) is ≈9 V, so specify V_R ≥ 40 V (standard, cheap).
```

**Finding — the ADR's chosen part is UNDER-RATED.** ADR-046 §6 / ADR-048 §2.3 specify the
DNP bypass as **"BAT54 family, SOD-323"**. The BAT54 family is rated **200 mA / 30 V**
(standard BAT54 datasheet class):

```
BAT54 rating 0.20 A vs small-array string 0.40 A  → 0.40/0.20 = 2.0×  OVER-RATED requirement
BAT54 rating 0.20 A vs large-array string 1.20 A  → 1.20/0.20 = 6.0×  OVER-RATED requirement
```

So a **BAT54 bypass is already undersized for the accepted 0.4 A array** (it needs 400 mA
and is rated 200 mA), and grossly undersized (6×) for a large-cell array.
`TODO(unverified)` — the exact BAT54 part number and its datasheet I_F/V_R were not read for
this analysis; the 200 mA / 30 V figures are the standard BAT54-family class ratings. Verify
against the actual ordered part before relying on it.

**Specified diodes (recommendation, superseding the BAT54 provision for the bypass role):**

| Role | Type / rating | Why |
|---|---|---|
| **Per-wing bypass** (ADR-046/048 provision, DNP) | **SS24 (2 A, 40 V, SMA)** or PMEG4020ER (2 A, 40 V, SOD-323) | `I_F ≥ 2 A` (1.5× the 1.2 A adversity current), `V_R ≥ 40 V`. The `SOLAR_P–SOLAR_N` series-blocking BAT54 at the stack output (ADR-006) is **unchanged** — it carries the same array current and should be checked too (`1.2 A > 0.2 A` → also under-rated for a large cell). |
| **Per-cell bypass** (if positions are paralleled) | **SS24 / PMEG4020ER** (2 A, 40 V), one per cell | same current/voltage basis; per-cell placement is what protects paralleled or partially shaded cells (§4.2). |

---

## 5. Charge path — can the array over-voltage the bank or the radio?

### 5.1 The premise: V_OC > V_MPP, and V_OC rises when cold

The array's nominal 6.0 V is its **maximum-power** voltage (`V_MPP`, 12 × ≈0.5 V). A Si
cell's **open-circuit voltage exceeds its MPP voltage** — ADR-047 §7.3 states exactly this
(*"a Si cell's V_OC exceeds its V_MPP"*) — and it **rises as temperature falls**
(dV_OC/dT ≈ −2 mV/°C per cell, the standard Si temperature coefficient).

```
Assume (TODO(unverified) — see below): V_OC,cell(25 °C) ≈ 0.62 V ; dV_OC/dT ≈ −2.1 mV/(°C·cell)
At −60 °C (ΔT = −85 °C):
   V_OC,cell(−60) = 0.62 + (−2.1e-3)×(−85) = 0.62 + 0.179 = 0.80 V
   12 cells:  V_OC,array(−60) = 12 × 0.80 = 9.58 V       (BEFORE the BAT54)
   through BAT54 (≈0.3 V):  ≈ 9.28 V presented to the raw supercap node
```

### 5.2 Can the array over-voltage the bank or the radio?

**YES.** There is **no limiter in the accepted design** — the array is a current source and
the only "limiter" is the load, so the node voltage rises until charge current = load
current. The 2 × 10 kΩ balancing resistors bleed only `5.4 V / 20 kΩ = 0.27 mA` — utterly
unable to absorb the array's 0.4–1.2 A.

```
Bank top (rated)    = 2 × 2.7 V = 5.4 V            [ADR-006]
Radio VCC max       = 5.5 V                        [ADR-047 §1.1, §7.1]
Array cold Voc      ≈ 9.3 V (post-BAT54)           [derived above]
Over-voltage headroom needed = 9.3 − 5.5 = 3.8 V   (≈ 68 % above the radio's stated max)
```

Both the **supercap bank** (rated 5.4 V; driving a 2.7 V cell above its rating is a
failure mode) and the **radio** (fed raw off the same node, ADR-047 §2.1) can be
over-volted. ADR-047 §7.3 already flags this as *"the real over-voltage path"*; this
analysis puts a number on it.

### 5.3 What keeps the top below 5.5 V — the series count does not, a clamp does

**Series count alone cannot solve it** — there is no integer *n* that both charges the bank
to 5.4 V and keeps cold V_OC under 5.5 V:

```
To charge the bank to 5.4 V the array V_MPP must exceed it plus the BAT54 drop:
   n ≥ (5.4 V + 0.3 V) / 0.5 V = 11.4   →  n = 12 cells       (this is WHY 12 cells, and it is right)
To keep cold V_OC below the radio's 5.5 V:
   n ≤ 5.5 V / 0.80 V = 6.9        →  n ≤ 6 cells
```

These are mutually exclusive (12 vs ≤6). **Therefore a clamp (shunt) is required**, not a
series recount. This is exactly the finding ADR-047 §7.4 reaches (the clamp becomes
*required insurance*), here given an explicit over-voltage magnitude.

**Recommendation for the clamp (electrical spec, not a part number):**
- A **precision shunt regulator / active crowbar at the raw supercap node**, set between
  **5.4 V (full charge) and 5.5 V (radio max)** — a window of only 0.1 V, so a plain Zener
  (tolerance ±5 % = ±0.27 V) **cannot** hold it. Use an **active shunt** (op-amp/TC-shunt or
  an OV-monitored switch) whose trip is trimmable, or accept a lower bank top (e.g. 5.1 V)
  with a fixed clamp so the ±0.1 V window is not needed.
- The clamp must sink the array's **full array current at 5.5 V** = up to **1.2 A at 5.5 V =
  6.6 W** for a large/matched array (0.4 A → 2.2 W for the accepted small array). This is
  the single most important rating: a clamp sized for 0.4 A is destroyed by a 1.2 A array.
- `TODO(unverified)` (carried from ADR-047 §7): **the array's open-circuit voltage at −60 °C
  and the F33's actual damage threshold are both unmeasured/unpublished**, so the clamp's
  set point **cannot be finalised**. Every number in §5.1 is conditional on the assumed
  V_OC(25 °C) = 0.62 V and −2.1 mV/(°C·cell), both of which must be replaced by a
  measurement or the cell's own datasheet (which is not in this repo).

### 5.4 Is the accepted 12-cell series arrangement still correct once cell sizes change?

**Voltage-wise, YES — unchanged.** Cell voltage is ~0.5 V for both sizes, so a 12-cell
series (3/wing × 4) is **6.0 V nominal for large cells, small cells, or any mix**. The
`n = 12` choice is driven by the 5.4 V charge target (§5.3), which is size-independent.

**What DOES change with cell size:**
- Array **current** (0.4 A → 1.2 A) → the **BAT54 stack diode** (0.2 A rated) and the
  **per-wing bypass diode** (§4.3) must be re-rated from ~0.2 A to ≥ 2 A.
- The **clamp must sink up to 1.2 A** (§5.3), not 0.4 A.
- The **wing outline** (§3(a), §3(b-ii)).
- **Nothing about the 6.0 V nominal or the 12-cell count changes.**

So: the accepted 12-cell series arrangement **remains electrically correct for any cell
size**; the change is in the **current-carrying parts around it** and the **wing geometry**,
not in the series count.

---

## 6. Conductor sizing

### 6.1 Assumptions (stated)

| Parameter | Value | Basis |
|---|---|---|
| Copper weight | **1 oz (35 µm = 1.378 mil)** | ADR-046 §3.2 gives the wing as 0.6 mm FR4 / 2 layers; 1 oz is the JLCPCB default and the only weight consistent with a 0.6 mm thin board's cost. `TODO(unverified)` — the wing's actual copper weight is not stated in any in-repo source. |
| Temperature-rise allowance | **ΔT = 10 °C** (and 20 °C shown) | Conservative for a sun-facing outer layer with no active cooling. |
| Layer | **external** (F.Cu) | ADR-046 §3.4b: *"the v9 board routes everything on F.Cu and carries no B.Cu pour"* → outer-layer k applies. |
| Formula | **IPC-2221A**: `I = k · ΔT^0.44 · A^0.725` → `A = (I / (k·ΔT^0.44))^(1/0.725)`, k = **0.048** (external), A in mil², width `W = A / (1.378 mil)` | standard IPC-2221A chart fit |
| Largest expected array current | **1.2 A** (large/matched array; 0.4 A for the accepted small array; 2.4 A for the unbuildable (c)) | §3 |

### 6.2 Computed widths (1 oz external, ΔT = 10 °C)

```
A = (I / (0.048 × 10^0.44))^(1/0.725) = (I / 0.13220)^1.3793        [mil²]
```

| Current | A (mil²) | **W (mm)** at ΔT = 10 °C | W (mm) at ΔT = 20 °C |
|---|---:|---:|---:|
| 0.40 A (accepted small array) | 4.60 | **0.085 mm** | 0.056 mm |
| **1.20 A (large / matched array)** | 20.96 | **0.386 mm** | 0.254 mm |
| 1.50 A (1.2 A + 25 % design margin) | 28.51 | **0.525 mm** | 0.345 mm |
| 2.40 A (arrangement (c), unbuildable) | 54.51 | 1.005 mm | 0.660 mm |

### 6.3 The 4.0 × 1.2 mm tab lands — adequate or must they change?

The current-carrying lands are **pins 1 (`SOLAR_P`) and 4 (`SOLAR_N`)**, each a
**4.0 × 1.2 mm** SMD land (ADR-046 §2.2; `docs/WING-TO-HUB-SOCKET-SPEC.md` §2). Current
flows along the 4.0 mm insertion axis, so the **restricting width is the 1.2 mm pad width**:

```
1.2 mm = 47.24 mil ;  A = 47.24 × 1.378 = 65.1 mil²
I_max = 0.048 × 10^0.44 × 65.1^0.725 = 0.13220 × 20.65 = 2.73 A   (1 oz, ΔT = 10 °C)
```

| Check | Required width | Pad width | Verdict |
|---|---:|---:|---|
| 1.2 A (large array) | 0.386 mm | 1.20 mm | **adequate — 3.1× margin** (pad can carry 2.73 A) |
| 2.4 A (arrangement (c)) | 1.005 mm | 1.20 mm | adequate (pad can carry 2.73 A) |

**The 4.0 × 1.2 mm tab lands are ADEQUATE for every current in this analysis and do NOT
need to change on ampacity grounds.** At 1 oz they carry up to ~2.7 A at a 10 °C rise,
against a maximum expected 1.2 A (2.4 A only in the unbuildable (c)).

### 6.4 On-wing interconnect — the real risk

ADR-046 §3.4 does **not state a track width** for the on-wing `SOLAR_P`/`SOLAR_N` runs
(*"the routing must reach pins 1 and 4 … a 4.0 mm land … which is what makes the board
routable"*). If those tracks are laid at or near a typical 0.2 mm DRC minimum:

```
0.2 mm = 7.87 mil ;  A = 10.84 mil²
I_max = 0.13220 × 10.84^0.725 = 0.13220 × 5.63 = 0.74 A     (1 oz, ΔT = 10 °C)
```

**A 0.2 mm on-wing track carries only ~0.74 A — too small for a 1.2 A large-cell array.**
Required minimum for 1.2 A is **0.386 mm**; a safe design value is **0.5 mm** (carries
1.45 A at 10 °C).

**Recommendation:** for any large-cell or matched build, specify the on-wing
`SOLAR_P`/`SOLAR_N` interconnect at **≥ 0.5 mm (1 oz)**; for the accepted 0.4 A small array
the 0.085 mm minimum is met by any normal track, so no change is needed there.
`TODO(unverified)` — the wing's actual routed track widths were not extracted for this
analysis (the `.kicad_pcb` was not measured); the 0.2 mm figure is a *typical* DRC minimum,
not an observed value. Verify from `tracker/hardware/wing_board/wing_board_v9.kicad_pcb`
before relying on it.

---

## 7. Comparison table of the arrangements

| # | Arrangement | Cells/wing | Wing V | Wing I | **Wing P** | Joints/wing | **W/joint** | Wing area | Buildable on 176×25? |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| baseline | 3 small in series | 3 small | 1.5 V | 0.4 A | 0.60 W | 8 | 0.075 | 44 cm² | **Yes (accepted)** |
| (a) | 3 × (3 small ∥) | 9 small | 1.5 V | 1.2 A | 1.80 W | 20 | 0.090 | ~114 cm² | No (§3b-ii) |
| (b) | 3 × (1 large) | 3 large | 1.5 V | 1.2 A | 1.80 W | 8 | **0.225** | ~115 cm² | No (§3a) |
| (c) | 3 × (1 large ∥ 3 small) | 3L+9S = 12 | 1.5 V | 2.4 A | **3.60 W** | 26 | 0.138 | ~184 cm² | No |
| mix-by-wing c-i | 2 large wings + 2 small wings | mixed | 6.0 V array | 0.4 A array | 2.40 W array | — | — | — | Yes, but 2.40 W discarded (§3c) |

**Array-level (4 wings):**

| Scenario | Cells/array | Array V | Array I | Array P | 6.0 V nominal kept? | Outline changes? |
|---|---:|---:|---:|---:|---|---|
| accepted: 12 small | 12 | 6.0 V | 0.4 A | 2.40 W | yes | no |
| only large | 12 | 6.0 V | 1.2 A | **7.20 W** | **yes** | **yes** (→ ~256 × 45 mm wing) |
| only small, matched | 36 | 6.0 V | 1.2 A | 7.20 W | yes | yes (→ ~176 × 65 mm wing) |
| mix-by-wing (unmatched) | mixed | 6.0 V | 0.4 A | 2.40 W | yes | maybe — but **2.40 W discarded** |

---

## 8. Top-line recommendation

1. **Do not build a mixed wing.** Cells of different sizes must **never sit in the same
   series string** (−66.7 % of the large cell's capability is discarded, §1.2) and must
   **not** be split across wings (permanent current-mismatch loss and reverse-stress,
   §3c). Mixing is only defensible as **3 smalls in parallel = 1 large** inside a
   position, and even that is **worse per soldered joint** than one large cell (0.090 vs
   0.225 W/joint, §2.3).
2. **Pick one size class per build.** Either choice keeps the **6.0 V nominal and the
   12-cell series count** (§3a, §5.4) — but **both** choices need a new wing outline: the
   **only-large** wing was found to be ~256 × 45 mm (~115 cm²) and the **matched-small**
   wing ~176 × 65 mm (~114 cm²). The current 176 × 25 mm wing cannot carry a large cell at
   all (§3a). **Feeding this back: the wing outline is an *electrical* consequence of the
   cell size, not a free parameter.**
3. **Re-rate the bypass diode.** The ADR-046/048 "BAT54 family (200 mA / 30 V)" DNP bypass
   is **undersized even for the accepted 0.4 A array** (needs 400 mA) and **6× undersized
   for a large-cell array**. Specify **≥ 2 A / 40 V** — e.g. SS24 (SMA) or PMEG4020ER
   (SOD-323) — for the per-wing bypass, and **per-cell** bypass if any position is
   paralleled (§4.3, §4.2).
4. **Add a clamp — the series count cannot do it.** The 12-cell array's **cold (~−60 °C)
   open-circuit voltage is ≈9.3 V**, far above the bank's 5.4 V and the radio's 5.5 V, and
   the accepted design has **no limiter** (§5). No integer series count both charges to
   5.4 V and stays under 5.5 V cold, so a **shunt clamp at the raw supercap node is
   required**, sized to sink the **full array current at 5.5 V (up to 1.2 A = 6.6 W)**.
   Its set point remains `TODO(unverified)` until the array's −60 °C Voc is measured
   (ADR-047 §7 open item).
5. **Conductors are fine; the lands are fine.** The **4.0 × 1.2 mm tab lands are adequate**
   (≈2.7 A at 1 oz / 10 °C vs a 1.2 A maximum, §6.3) and need not change. The risk is the
   **un-specified on-wing interconnect**: at a 0.2 mm DRC minimum it carries only ~0.74 A,
   so a large-cell build must specify **≥ 0.5 mm** on-wing `SOLAR_P`/`SOLAR_N` (§6.4).
6. **If the operator's goal is energy per unit mass and per unit labour, the large cell
   wins decisively** (1.80 W/wing from 3 cells / 8 joints vs 1.80 W/wing from 9 cells /
   20 joints) — *provided* the wing outline is re-derived to hold it and the ~2× area is
   acceptable in the 4-arm cube span.

---

## 9. Open items (explicit, none invented)

1. `TODO(unverified)` — the large cell's actual maximum-power current (listing 0.54 W
   implies 1.08 A; area scaling implies 1.2 A). §0.2.
2. `TODO(unverified)` — both cells' I-V curves (V_OC, V_MPP, fill factor, temperature
   coefficients). §1.2, §5.1.
3. `TODO(unverified)` — per-cell current spread of the 100-cell small batch. §2.1.
4. `TODO(unverified)` — the exact BAT54 (and SS24/PMEG) datasheet I_F / V_R for the parts
   actually ordered. §4.3.
5. `TODO(unverified)` — the array's open-circuit voltage at −60 °C and the F33's damage
   threshold (carried from ADR-047 §7). §5.3.
6. `TODO(unverified)` — the wing's actual routed `SOLAR_P`/`SOLAR_N` track widths; not
   measured from `tracker/hardware/wing_board/wing_board_v9.kicad_pcb`. §6.4.
7. `TODO(unverified)` — the wing's actual copper weight (1 oz assumed). §6.1.
8. `TODO(unverified)` — per-cell masses (component-guide figures, not weighed). §3a.

---

## 10. Sources cited

- `docs/adr/006-supercapacitor-power.md` (Accepted) — array, bank, BAT54, LDO.
- `docs/adr/046-wing-board-interface.md` (Proposed) — tab, outline, series order, DNP bypass.
- `docs/adr/047-v9-power-provisioning.md` (Proposed) — 1118 mA/5.5 V, pre-LDO tap, boost
  refused, clamp, over-voltage path.
- `docs/adr/048-v9-hub-wing-interfaces.md` (Proposed) — 4 hub sockets, hub series wiring.
- `docs/WING-TO-HUB-SOCKET-SPEC.md` — hub land geometry, bypass-provision wording.
- `docs/POWER-BUDGET-V9-D2BE.md` — 12 cells, 6.0 V/400 mA/2.4 W, mass table.
- `docs/SOLAR-PIN-REGULATORY.md` — array sizing authority, harness derate.
- `docs/hardware-design.md` — 65 × 28 mm wing (superseded by ADR-046), dev-board boost.
- `docs/component-guide.md` — cell masses, cell options.
- IPC-2221A — conductor-width chart fit (§6.1).
