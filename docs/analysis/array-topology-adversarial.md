# Array topology — an adversarial derivation of the best solar-array topology

> **STATUS: CONSULTANT ANALYSIS — NOT A DECISION RECORD.**
> This is an **independent, adversarial** derivation written by a consultant who was
> deliberately **not told** the conclusion of the parallel-in-flight topology comparison and
> did **not** read it. It is **not** an ADR, it does **not** amend ADR-006 / ADR-044 / ADR-046 /
> ADR-047 / ADR-048 / ADR-049 / ADR-050 / ADR-051, and **nothing here may be read as an accepted
> design**. It orders nothing, modifies no design file, and carries no authorisation to change
> any board, BOM, schematic, wing outline or series count.
> Every number below is either **(a) computed** with its formula or the script line that
> produced it shown, **(b) cited** to an in-repo file, **(c) read from a vendor datasheet PDF**
> (the vendor, the document number and the retrieval path are named), or **(d) marked
> `TODO(unverified)`** with the open question named. Where this analysis disagrees with an
> accepted or proposed record it says so explicitly and does not silently override it.

| | |
|---|---|
| Date | 2026-10-07 |
| Author | independent adversarial consultant (Hermes subagent) |
| Branch / worktree | `analysis/array-topology-adversarial` · `/home/c03rad0r/worktrees/bf-topo2` |
| Base | `github/main` = `ce2366e` ("merge(analysis): analysis/free-balloon-mass-threshold") |
| Lens | **array topology, cell-failure physics, charge-path feasibility, buildability** |
| Scope ruled out | no board code, no schematic edit, no BOM change, no wing redraw |
| Explicitly not read | the parallel worker's in-flight topology comparison (per the brief) |

**The proposition this document attacks** (quoted from the brief):

> *"you can make the converter tolerate cracked cells by adding a bypass Schottky across every
> cell (or every 2-3 cells), instead of abandoning the series string."*

**Order of business, as the brief requires:** my own derivation and ranking comes **first**
(§1), so the reader can see whether I converged independently, *before* any critique. The
falsification attempts follow (§2), then the equal attack on the parallel alternatives (§3),
then the part reality check (§4), then the single falsifier and the cheapest experiment (§5),
then a bottom line that states plainly where I agree and disagree (§6).

---

## 0. The system under review (given facts, and what in the repo corroborates them)

| Item | Value | Source |
|---|---|---|
| Cells | 12 × LARGE bare polycrystalline, 78.55 × 38.90 × 0.21 mm, **30.6 cm²**, ~0.5 V, ~1.2 A, **1.50 g** | brief-given; `docs/adr/049-wing-architecture.md` §Measured inputs (LARGE: 78.55 × 38.90 × 0.21 mm, 30.6 cm², ~0.5 V, ~1.2 A) and `docs/analysis/array-power-architecture.md` §1.1 (≈1.50 g) |
| Cell terminals | **one pad per face** (one front, one back) | brief-given; `docs/adr/049-wing-architecture.md` §Measured inputs gives this for the **SMALL** cell ("one pad on the FRONT face, one on the BACK face") and marks the **LARGE** cell's pad layout *"not yet confirmed"* — so the two-face construction is `TODO(unverified)` for the LARGE cell until the pads are measured (ADR-049's own order blocker) |
| Mounting | **END-ONLY, no adhesive bond** | brief-given; consistent with ADR-049 §Decision ("spine-and-ribs frame", not a full-area FR4 carrier) |
| Array target | 6.0 V at 1.2 A = **7.2 W** peak | brief-given; `docs/adr/049-wing-architecture.md` §Decision ("12 cells, 6.0 V nominal / 1.2 A ≈ 7.2 W peak") |
| Storage | 3.3 F bank, ≤ 5.4 V, **33.264 J usable** (5.4 → 3.0 V), **no battery** | `docs/adr/047-v9-power-provisioning.md` §3.2 |
| Load | radio average **0.388 W**, peak **6.15 W**, F33 rail **3.0 V min / 5.0 V typ / 5.5 V max**, 1118 mA max | `docs/POWER-BUDGET-V9-D2BE.md` §2 (0.388 W); ADR-047 §1.2 and §"Voltage range" row (6.1495 W, min 3.0 / typ 5 / max 5.5 V) |
| Night budget | **100 µW** housekeeping anchor | ADR-036, via ADR-047 §6.1 and ADR-050 §3.6 |
| Wings | **jettisonable**; the vehicle must keep operating after a shed | brief-given; ADR-051 §0 |
| Converter decision | wide-input non-inverting buck-boost / SEPIC, output regulated to 5.40 V, input rated ≥ 12 V | `docs/adr/050-mppt-charge-path.md` §3.1–§3.3 |
| Cut topology | hub array is an independent string; per-interface bypass diodes populated | `docs/adr/051-hub-array-and-cut-topology.md` §2.1, §2.4 |
| Wing socket stack | W1.N→W2.P→W3.N→W4.P, one bypass Schottky provision per interface | `docs/WING-TO-HUB-SOCKET-SPEC.md` §3.1, §5 |

**Physical model used throughout.** A PV cell is a **photocurrent source** (≈ area-proportional
current, ~1.2 A for this cell) squelched by a diode, with a **voltage ceiling ≈ 0.5 V** at MPP.
Consequences I use and state once so they are not re-argued:

```
SERIES  : the current is ONE path (Kirchhoff) → string I = min(element I); voltages ADD.
PARALLEL: the voltage is ONE node           → branch V = common V; currents ADD.
In SERIES the array current is set by the WEAKEST element. In PARALLEL the array
voltage is dragged to the WEAKEST element (a dark branch's V_oc ≈ 0 clamps the bus).
POWER IS CONSERVED: wiring redistributes V and I; it cannot create watts.
```

The series/parallel rules above are the same statement as `docs/analysis/wing-electrical.md`
§1.1 (which I cite rather than re-derive), and the "topology cannot create watts" statement is
`docs/analysis/array-power-architecture.md` §3.1.

---

## 1. INDEPENDENT DERIVATION — series versus parallel current arithmetic, and my ranking

### 1.1 The arithmetic, from the physics up

12 cells at 0.5 V / 1.2 A each. Every rearrangement below delivers the **same 7.2 W** — that is
the conservation statement of §0. What changes is the **voltage the bank sees**, the **input
current the converter must carry**, and the **conduction (I²R) loss**:

```
V = n_series × 0.50 V          I = n_parallel × 1.20 A          P = V × I = 7.20 W (all rows)

topology   V       I        I²R vs 12s1p   boost ratio to reach 5.4 V   direct-charge 5.4 V bank?
12s1p      6.00 V  1.20 A   1×  (base)    0.90  → BUCK                     YES (6.0 > 5.4 + diode)
6s2p       3.00 V  2.40 A   4×            1.80  → BOOST                    no
4s3p       2.00 V  3.60 A   9×            2.70  → BOOST                    no
3s4p       1.50 V  4.80 A   16×           3.60  → BOOST                    no
2s6p       1.00 V  7.20 A   36×           5.40  → BOOST                    no
1s12p      0.50 V  14.40 A  144×          10.80 → BOOST                    no
```

The last column is the whole argument. **The 12-cell series string is the only arrangement that
stands above the 5.4 V bank, so it is the only one that needs no step-up ratio at all** (0.90×,
i.e. a small buck) and the only one whose conduction loss is at the 1× base. Every parallel
rearrangement buys nothing (same watts) and pays: 4× to 144× the I²R loss, a 1.8× to 10.8×
step-up ratio, and an input current of 2.4 A to 14.4 A instead of 1.2 A.

Two further derived facts:

```
at ≤1.5 V input the same 7.2 W costs ≥4.8 A  →  (4.8/1.2)² = 16× the I²R loss
                                                (the "3s4p / wing-parallel" row)
at 0.5 V input it costs 14.4 A               →  (14.4/1.2)² = 144×
```

The 16× figure for a 1.5 V array is already computed in the repo (`docs/analysis/mppt-charge-path-specification.md`
§2(b).1 — "the same 7.2 W costs 4.8 A at 1.5 V against 1.2 A at 6.0 V … I²R loss ratio = 16×"),
and it is the reason the repo's own specification refuses the low-voltage end. I re-derived it
independently from `P = V·I` and it agrees.

**And the diode symmetry — the point that decides half of §3 before any critique.** A PV cell
cannot be put in parallel with a dissimilar cell without protection *either*:

- in **series**, a weak/open element must be **bypassed** (diode **across** the element);
- in **parallel**, a weak element at a lower V_oc is **back-driven** by the stronger ones, so it
  must be **blocked** (diode **in series** with the element).

So **paralleling does not remove diodes from the array — it relocates them from an idle,
normally-reverse-biased position to a permanent series position in the current path.** A bypass
diode is reverse-biased (idle) in normal operation; a blocking diode drops `V_f` on **every**
branch **all the time**:

```
series topology  : ONE stack diode at 6.0 V  → 0.3/6.0 = 5 % tax on one path
per-wing parallel: blocking diode per branch on 1.5 V → 0.3/1.5 = 20 % tax on every branch
per-cell parallel: blocking diode per branch on 0.5 V → 0.3/0.5 = 60 % tax on every branch  ← absurd
```

(This is why parallel PV arrays are built from high-voltage modules, not single cells.) That is
an argument **against** parallel that costs no datasheet at all.

### 1.2 My ranked recommendation — stated BEFORE any critique, as required

> **RANK 1 (recommended).** **Keep the 12-cell series string** (4 wings × 3 cells). Charge it
> through the wide-input **non-inverting buck-boost / SEPIC** of ADR-050 (output regulated to
> 5.40 V, input rated ≥ 12 V for the 9.58 V cold open-circuit case). The converter — not the
> wiring — is what makes the array tolerant of a lost cell or a lost wing.
>
> **RANK 2 (mandatory, and it is the load-bearing protection).** **One bypass Schottky per
> WING/INTERFACE, placed ON THE HUB, across `W<n>_SOLAR_P` ↔ `W<n>_SOLAR_N`, rated ≥ 2 A / 40 V.**
> This is required because a *cut* wing and an *open* cell both break the series **path**, and a
> bypass diode is the only element that restores a broken path. It must be on the hub, not the
> wing (§2.4).
>
> **RANK 3.** **Per-cell bypass diodes** (one per cell) — a **second-order refinement**, not a
> requirement. It buys back ≈ 1.2 W of the 7.2 W array per event, and is the **only** protection
> for an intra-wing *soft* shunt. I rank it **below** Rank 2, and §2 and §6 explain exactly why
> and under what condition it would move up.
>
> **RANK 4 and below (rejected).** Any **parallel rearrangement** (§1.1, §3), including
> wing-level parallel (1.5 V / 4.8 A) and cell-level parallel (0.5 V / 14.4 A).
> **Direct connection with no converter** is also rejected — not on efficiency but on **mission
> continuity**: with 3 of 4 wings the string tops the bank at **4.20 V**
> (`docs/analysis/array-power-architecture.md` §3.2: 4.5 V − 0.3 V) and with 2 wings at
> **2.70 V**, below the radio's 3.0 V minimum → **mission over**. The converter is bought for
> continuity, and ADR-050 §1 already states that its efficiency case is *negative* at the bank's
> normal operating point (break-even 5.10 V = 94.4 % of the 5.4 V top).

So my independent answer is: **keep the series string; add bypass diodes; do not go parallel.**
That is, on the decision, the same side as the proposition. **Where I diverge is the granularity
(per-wing, not per-cell, is the load-bearing protection), the mechanism (a bypass diode does not
confer converter tolerance — the converter already has that), and the buildability** (§2.5).

---

## 2. FALSIFICATION ATTEMPTS — attacking the proposition seriously

I tried to break it. Eight attacks; each is stated with its verdict. The crux (F1) is first.

### F1 — **SUCCEEDED (partly). Does a bypass diode help a cell that fails SHORTED? The crux.**

This is the question the brief flags as decisive, and the answer is **"it depends on the short,
and the proposition conflates three failure modes that behave differently."** A bypass diode
conducts only when the voltage across the cell it guards reaches the diode's forward drop
(≈ 0.3–0.4 V at 1.2 A; per-part `TODO(unverified)`). Whether that happens is determined by the
**resistance** of the failed cell:

| Failure | Cell model | What the parallel bypass diode does | String result |
|---|---|---|---|
| **OPEN** (crack severs the wafer/metallisation — no path) | `R → ∞` | The cell cannot carry the string current, so the parallel diode is driven into conduction and carries the **full 1.2 A**; it clamps the position at ≈ 0.35 V | String loses `0.5 V (the cell) + 0.35 V (the diode)` ≈ **0.85 V** and **keeps charging**. **The diode IS the remedy** — without it the string is dead. |
| **HARD short** (a weld/bridge across the cell, a melted-through junction; `R ≈ 0`) | `R ≈ 0` | `I·R ≈ 0 < V_f` → **the diode never reaches its forward threshold and never conducts.** It is **inert**, and it **protects nothing** | The short itself carries the current at ≈ 0 V; the string simply loses that cell's 0.5 V and **keeps charging anyway** — with **no diode needed**. |
| **SOFT / partial short** (a crack that forms a shunt of ~0.3 Ω … ∞) | `R = R_sh` | If `1.2 A × R_sh > V_f`, the diode turns on and **clamps the cell at ≈ 0.35 V**, shunting the remainder | The diode **does** protect — but as a **hot-spot clamp**, not as a "converter tolerance" device |

Worked numbers for the soft-shunt row, because it is the only row where the diode does
something the string would not do for itself:

```
soft shunt R_sh = 1 Ω, string current 1.2 A, no bypass:
   cell drops 1.2 V and dissipates I²R = 1.2² × 1 = 1.44 W in 30.6 cm²
   = 47.1 mW/cm², against the 19.6 mW/cm² nameplate density (= 0.60 W / 30.6 cm²)
   → 2.4× nameplate local dissipation = a genuine hot spot
with a per-cell bypass diode clamping the cell at 0.35 V:
   cell dissipates 0.35² / 1 = 0.12 W (a 12× reduction) and the diode carries ≈ 0.85 A
```

**Verdict on F1.** The proposition's claim, "make the **converter** tolerate cracked cells by
adding a bypass diode," **misattributes the mechanism**, and this is the single most important
finding in this document:

- A **hard-shorted** cell needs no diode and **cannot be helped by one** — the string conducts
  through the short and the converter absorbs the 0.5 V loss. **The converter's wide input
  voltage range is what tolerates it, not the diode.** (ADR-050 §3.2: the TPS63060's input
  window is 2.5–12 V; a 0.5 V string drop is invisible to it.)
- An **open** cell is the case the diode exists for — but then the diode is repairing the
  **PATH**, which is a property of the wiring, not of the converter.
- A **soft-shorted** cell is the one case where the correct description is a **hot-spot clamp**,
  and there the per-cell granularity is genuinely the right one (a per-wing diode cannot do it —
  see F2).

So the proposition is **true in actionable content** (keep the string; add bypass diodes) and
**wrong in its stated mechanism**, and it is **silent on the fact that a hard short is
self-bypassing** — which matters because a "cracked cell" can fail either way and the brief's
own framing treats "cracked" as one failure.

### F2 — **FAILED to falsify (the proposition wins here). A per-wing diode cannot protect a cell inside its own wing.**

The attempt was: "per-2-3-cell bypass covers everything a per-cell bypass covers, because one
open cell opens its whole 3-cell wing and the wing's single diode then bypasses it." **That half
is true** — in a series sub-string an open element breaks the path, so the sub-string's own
bypass diode does bridge it. But the *soft*-short row of F1 defeats the attempt:

```
wing = cells 1,2,3 in series; cell 2 is a soft shunt, R_sh = 1 Ω
  cell 1 and cell 3 still source ≈ 0.5 V each ⇒ the WING's terminal voltage stays
  POSITIVE (≈ +0.5 − 1.2 + 0.5 = −0.2 V … 0 V, not reverse enough to turn the
  wing's bypass diode on)
  ⇒ the per-WING diode never conducts, cell 2 keeps dissipating ~1.4 W
  ⇒ only a PER-CELL diode clamps cell 2
```

**Verdict:** the per-cell granularity has **one unique, real job** — protecting a cell whose
failure or shading leaves its own sub-string still sourcing voltage. I could not falsify that.
It is recorded as an **argument in the proposition's favour** and it is the reason my Rank 3
exists at all rather than being deleted.

### F3 — **SUCCEEDED. Per-cell diodes are cut away with the wing, so they are dead mass at the cut.**

The wings are jettisonable (`docs/adr/051-hub-array-and-cut-topology.md` §0, §1.1). A per-cell
diode is soldered to **the wing** or to the wing's cell nodes. **When the wing is cut, its
per-cell diodes leave with it** — they cannot bridge the gap, because they are on the wrong side
of the gap. Only a **hub-side, per-interface** diode can short the removed wing's position and
keep the string charging (ADR-051 §2.4 decision 4.2 states exactly this: the per-interface bypass
diodes must be **populated, not DNP**, "because a cut leaves the wing's socket lands open, which
opens the string").

**Consequence, stated plainly:** a flight that carries cutters and has **per-cell diodes but no
hub-side per-interface diodes** is **strictly worse off than the baseline** — the first cut kills
the array, and the 12 per-cell diodes did nothing. So "every cell" is **not** an acceptable
substitute for "every 2-3 cells"; the proposition's parenthetical is not a free choice. This also
resolves the package-placement contradiction ADR-049 §Consequences clause 5 flags in ADR-046
("bypass Schottky placed on the hub (§2.3) but specified per-wing in the build brief"): **for the
cut, the hub placement is the one that works.**

### F4 — **SUCCEEDED. Granularity buys power no requirement asks for.**

Numbers for one event, per bypassed unit (all four rows computed in §1.1/§2 scripts):

```
12s1p healthy string                 : 6.00 V × 1.2 A = 7.20 W      100 %
one CELL bypassed (0.5 + 0.35 V)     : 5.15 V × 1.2 A = 6.18 W       86 %   (loss 1.02 W = 14.2 %)
one WING bypassed (1.5 + 0.35 V)     : 4.15 V × 1.2 A = 4.98 W       69 %   (loss 2.22 W = 30.8 %)
per-cell minus per-wing granularity  : 6.18 − 4.98 = 1.20 W  = 16.7 % of the array
```

The mission's average draw is **0.388 W** (`docs/POWER-BUDGET-V9-D2BE.md` §2) and the radio's
peak is **6.1495 W** (ADR-047 §1.2). **4.98 W of residual array power still covers the 0.388 W
average 12.8× over**, and it is 81 % of the radio's peak. So the per-cell granularity is buying
≈ 1.2 W of **peak** power that **no requirement in the repo asks for**. It is a real gain, but it
is a gain in a currency the mission has a **15.85× surplus** of (radio peak ÷ mission average
= 6.1495 / 0.388 = 15.85, `docs/analysis/array-power-architecture.md` §3.2).

**Counter-attack on my own attack, stated because it is honest:** per-cell bypassing is also
**gentler** — it recovers 86 % instead of 69 %, i.e. it keeps **2 sibling cells alive inside the
damaged wing**. If the vehicle ever flies a **high-duty** profile (the operator's "high TX duty"
direction in ADR-050 §0), the 1.2 W stops being surplus. So F4 succeeds **conditionally**: on the
recorded 0.388 W average it succeeds; on an unrecorded high-duty profile it may not.

### F5 — **SUCCEEDED. Per-cell bypass on THIS mount is the one option that puts new risk on the component it protects.**

The mounting decision that was *just made* is **END-ONLY, no adhesive bond** (brief; consistent
with ADR-049's rejection of the full-area FR4 carrier in favour of a spine-and-ribs frame). Three
consequences, each concrete:

1. **There is no board face to glue a diode to.** The only two physical homes for a per-cell
   diode are (a) the **cell's own pads** — i.e. soldering a component directly onto a **0.21 mm
   bare polycrystalline wafer** whose pad geometry is ADR-049's own *"order blocker"*
   (`TODO(unverified)`: "pad size and position on both cell sizes, both faces"), where a hot iron
   is a thermal-shock/crack risk — or (b) **a free-standing bridge between two adjacent spine
   nodes**. Option (b) is mechanically defensible *if the nodes are designed for it*, but the
   diode then becomes exactly the kind of unsupported spanning element that the spine-and-ribs
   frame exists to avoid (ADR-049 §Open items: *"whether spine-and-ribs leaves unsupported silicon
   spans that crack; the frame's rib pitch is set by that answer"*).
2. **+24 hand-soldered joints.** The 12-cell LARGE array is **8 joints per wing = 32 per aircraft**
   (ADR-046/`wing-electrical` §2.3: `joints = 2·N_cells + (positions − 1) = 2·3 + 2 = 8`). One
   bypass diode per cell adds **2 joints × 3 cells = 6 per wing → +24**, i.e. **+75 %** on the
   array joint count. ADR-049's own headline ("108 hand-soldered joints per aircraft instead of
   36") shows the project treats joint count as a first-class cost.
3. **One reversed diode silently destroys a cell's output *by construction*.** A bypass diode for
   cell *k* is normal-operation **reverse**-biased: **anode → the cell's LOW node, cathode → the
   cell's HIGH node**. Install it the other way round and it is **forward-biased by the cell's own
   0.5 V**: it clamps the cell to ≈ 0.35 V and shunts it, so the cell produces ≈ 0 V while the
   diode carries the full 1.2 A continuously. **A single hand-orientation error therefore creates
   exactly the "hard-shorted cell" failure mode the diode was fitted to prevent** — and it adds
   0.42 W of permanent loss (0.35 V × 1.2 A). Twelve diodes in a hand-built array are twelve
   chances to do this; nothing in the topology catches it (it is invisible to a string-voltage
   check, because the loss is only 0.85 V of 6.0 V).

**Verdict:** per-cell bypass is **buildable in principle** on the wing side (the inter-cell nodes
exist anyway as series links), but on this mount it is the option that adds the most new thermal,
mechanical and assembly-error risk, concentrated on the brittle part it is meant to protect.

### F6 — **SUCCEEDED (a correction to the repo's own ladder). The interface diodes' forward drops move the 2-cut case below the converter floor.**

ADR-051 §1.1 tabulates the cut ladder as `2 wings left → 3.0 V string → charging? yes (the
ADR-050 §3.2 practical floor)`. But ADR-051 §2.4 decision 4.2 makes the per-interface bypass
diodes **populated** on any cutter-carrying flight, and after a cut the current flows **through**
that interface's diode. **Each cut therefore costs one `V_f` in the string, and the ladder must
subtract it:**

```
0 cuts : 4 × 1.5 − 0 × 0.35 = 6.00 V   charges (≥ 2.5 V floor)  YES
1 cut  : 3 × 1.5 − 1 × 0.35 = 4.15 V   YES
2 cuts : 2 × 1.5 − 2 × 0.35 = 2.30 V   NO   ← below the 2.5 V TPS63060 floor
3 cuts : 1 × 1.5 − 3 × 0.35 = 0.45 V   NO   (hub array only)
```

So **two cuts does not charge, not "charges at the floor"** — the two interface diodes eat
0.70 V of the 3.0 V that remained. This is a **conservative** result (it assumes `V_f = 0.35 V`;
if the chosen ≥2 A Schottky is nearer 0.30 V the figure is 2.40 V, still below 2.5 V), and it is
conditioned on the part, which ADR-051 §Open items 11 already carries as `TODO(unverified)` ("the
temperature-derated continuous current of the specific chosen part"). The
**consequence is real**: the hub array stops being optional at **two** cuts, not three, so the
hub-array sizing decision and the cut-ladder depth are coupled one step earlier than ADR-051
§2.4.1 states. (ADR-051's own §3 already notes H2 may not close 0.388 W, which makes this bite.)

### F7 — **SUCCEEDED. "Bypass" and "converter tolerance" are different requirements, and the array needs both — the proposition offers one.**

Stated as a table, because this is the cleanest way to show the category error:

| Requirement | What supplies it | Does a bypass diode supply it? |
|---|---|---|
| Keep charging when the **string voltage moves** (short cell, loss of a wing's voltage, ageing, cold, partial shading of a whole sub-string) | the converter's wide input window (2.5–12 V) | **No** — and it does not need to; the converter already has it |
| Keep charging when the **path breaks** (open cell, cut wing, an unpopulated/DNP interface diode) | a bypass diode **across the broken element**, on the **hub** side of any cut | **Yes — this is the diode's real job** |
| Prevent a **hot spot** in a partially failed/shaded cell inside a live sub-string | a **per-cell** bypass clamp (F2) | **Yes, per-cell only** |
| Prevent the **cold open-circuit 9.58 V** from destroying the bank/radio | the **shunt clamp** (ADR-049 clause 3, ADR-047 §7, retained by ADR-050 §3.5) | **No — a different part entirely** |

So "add bypass diodes so the converter tolerates cracked cells" merges two independent
requirements into one sentence and credits the wrong part for one of them. The converter needs
the clamp, not the diodes; the diodes need the converter, not the other way round.

### F8 — **FAILED to falsify. Keeping the series string is correct, and no alternative I could construct beats it.**

I tried to build a better topology. Every attempt landed on the series string:

- **Series with more cells per wing** (per-wing 6 V): 12 cells/wing = **48 cells**, **4.00×** the
  cells, area, mass and peak power for **zero** extra watts (`docs/analysis/array-power-architecture.md`
  §1.2). REJECT.
- **Series on fewer boards** (one 12-cell board): preserves 6.0 V/7.2 W but concentrates the array
  into a single point of failure and destroys the 4-arm harvest geometry. REJECT (per the same
  analysis, §1.5).
- **Parallel in any arrangement:** §1.1 arithmetic plus §3. REJECT.
- **A second independent string for the hub** (ADR-051 §2.1): this does **not** replace the wing
  series string; it adds to it, for the post-cut case. It is **compatible with** and **secondary
  to** Rank 1. Not a falsifier.
- **Small cells (3 ∥ × 3 series per wing)** as a current-matched alternative: same 6.0 V/1.2 A and
  the same 7.2 W, but **20 joints per wing vs 8** (`wing-electrical` §3(b-ii); ADR-049: "108
  hand-soldered joints per aircraft instead of 36") and 36 cells. It is a **stock fallback**, not a
  better topology. Not a falsifier.

**Verdict:** the series string survives every alternative I could construct from the physics.
**I converged on the proposition's decision** — independently, and before reading anything about
it.

### F9 — **SUCCEEDED (summary form of F1 + F3 + F7).**

**A bypass diode does not make the converter tolerate anything: the converter's 2.5–12 V input
window already tolerates the voltage consequence of every cell failure including a hard short. A
bypass diode restores a broken *path*, and the only path a *cut* breaks is the one bridged by the
**hub-side per-interface** diode — which per-cell diodes cannot reach, because they are
jettisoned with the wing.**

---

## 3. THE PARALLEL ALTERNATIVES, ATTACKED EQUALLY

The brief asks me to attack parallel as hard as series, and to say whether the "14.4 A at 0.5 V"
objection is decisive or a strawman. Both.

### 3.1 What breaks when you parallel at different voltages / insolation / ageing

1. **A dark or weak branch drags the common node down.** In parallel all branches share **one
   voltage**. A shaded/dark wing's `V_oc` collapses toward 0, so it clamps the bus toward 0 V
   unless it is blocked. In series the same wing merely sets the **current**. Series failure =
   loss of current; parallel failure = loss of the **voltage the bank needs**. Series is the
   better failure shape for this load.
2. **Reverse current into the weak element.** At a common bus voltage, the strongest branch drives
   current **backwards** through the weakest. This is not a "loss" — it is **dissipation in the
   weak element** (the same hot-spot mechanism `docs/analysis/wing-electrical.md` §4.1 computes for
   the series case: 0.60 W/cell at 0.4 A, 1.8 W/cell at 1.2 A).
3. **The fix is a blocking diode per branch — and it costs 20–60 % of the branch voltage**
   (§1.1): 0.3 V of 1.5 V = 20 % at wing level; 0.3 V of 0.5 V = 60 % at cell level. This is the
   decisive economic point and it needs no datasheet: **you cannot afford series blocking diodes
   on a 0.5 V cell.** Parallel therefore does **not** reduce the diode count; it makes the diodes
   *more* expensive because they sit in the main current path instead of idling.
4. **One MPPT front end cannot track mismatched parallel branches.** A converter presents **one**
   operating point to the array. Parallel branches at different insolation share a voltage and
   therefore each sits **off its own MPP**; the tracker finds a compromise on the summed curve.
   The fix is **per-branch MPPT = N converters**, which multiplies **quiescent draw, mass and
   EMI** by N. On a 100 µW night anchor (≈ 18.5 µA at 5.4 V — `100 µW / 5.4 V = 18.52 µA`) that is
   fatal for any multi-µA part: 4 × 30 µA = 120 µA = 648 µW = **648 %** of the anchor. Even at the
   best verified harvester quiescent (488 nA) you could afford four, but that class cannot carry
   7.2 W (§4).
5. **Mixed ageing / mixed cell voltage** is case (2) again, permanently.

### 3.2 Is "14.4 A at 0.5 V" decisive, or a strawman? — **It is a strawman, and the real objection is stronger.**

The `14.4 A at 0.5 V` figure is the **cell-level-parallel extreme** (`1s12p`). Dismissing "all
parallel options" with it **is** a strawman, because the realistic parallel alternatives are:

```
3s4p  = the four 1.5 V wings in parallel : 1.5 V @ 4.8 A   (the wing-level option)
6s2p  = two 3.0 V sub-strings in parallel: 3.0 V @ 2.4 A
```

So the honest objection is not "14.4 A" but the two facts that survive for **every** parallel
arrangement:

- **The array's voltage falls to ≤ 3.0 V, i.e. below or at the converter's floor.** Wing-parallel
  (1.5 V) is **below the 2.5 V input minimum of the only verified full-power part** (§4), and
  6s2p (3.0 V) sits barely above it with **zero margin** — and any single sub-string loss or the
  loss of one wing from a sub-string drops it below. So the *parallel* rearrangement throws away
  the one property the series string had for free: **standing above the bank, so no step-up is
  needed at all.**
- **16× (wing-parallel) to 144× (cell-parallel) the I²R loss** at the same delivered watts.

**What the array would really look like if you accepted the parallel requirement** (asked
directly by the brief): you would be designing around **1.5 V at 4.8 A** (realistic) or **0.5 V at
14.4 A** (extreme). That is a **≥ 3.6× to 10.8× step-up at 4.8–14.4 A input** — not a nano-power
harvester (those are 0.1 A class, §4) but a **multi-amp boost**: an inductor with ≥ 6–17 A
saturation, ≥ 6 A switches, a current-carrying loop an order of magnitude larger than the 1.2 A
series case, whose quiescent draw is tens of µA (**> the whole night anchor**), and which puts a
multi-amp switching loop next to a −136 dBm receiver (ADR-029 §5 tests 1/3 are already the
acceptance numbers for the *1.2 A* converter, ADR-050 §3.9). Plus a blocking diode per branch
(§3.1.3) and **still** the shunt clamp. **So accepting the parallel claim converts a ≈ 1 g,
one-active-part converter into a multi-gram, multi-amp one and adds parts — for zero extra
watts.** The "14.4 A" objection is a strawman; the conclusion it was reaching for is correct
anyway.

---

## 4. PART REALITY CHECK (independent) — can any purchasable converter unlock the parallel topologies?

**The question, stated as a requirement** (from the brief): a part that takes a **sub-2.5 V**
input (which is what any parallel arrangement requires, §1.1) and delivers **≈ 7.2 W into a 5.4 V
bank**, with a quiescent current small enough not to destroy a **≈ 100 µW** night budget.

**The night-budget bound, computed:**

```
100 µW anchor at 5.4 V = 18.52 µA
I_Q ≤  5 µA →  27.0 µW =  27 % of the anchor      (ADR-050 §3.6 hard bound)
I_Q ≤  2 µA →  10.8 µW =  11 % of the anchor      (ADR-050 §3.6 target)
I_Q = 30 µA → 162.0 µW = 162 % of the anchor      (breaks it)
I_Q = 55 µA → 297.0 µW = 297 % of the anchor      (breaks it badly)
I_Q = 488 nA → 2.64 µW = 2.6 % of the anchor      (fine)
```

**What I verified myself, from the vendor datasheet PDFs** (fetched from `ti.com` on 2026-10-07
via `https://www.ti.com/lit/ds/symlink/<part>.pdf`; every figure below is read from the PDF, not
from a product-page summary):

| Part | Doc (fetched) | V_in typ/operating | V_in abs/rec. max | Output capability | I_Q typ | Verdict for THIS array |
|---|---|---|---|---|---|---|
| **bq25570** | TI **SLUSBH2G**, Rev G (Mar 2013 – rev. Mar 2019) | cold-start **≥ 600 mV** typ (`VIN(CS)`); continuous harvest to **100 mV** | **5.1 V** recommended; **5.5 V** absolute max (abs-max table: VIN_DC … –0.3 to 5.5 V); peak input power **510 mW** abs max, ≤ **400 mW** recommended | **peak output current up to 110 mA**; buck cycle-by-cycle limit 160/185/205 mA | **488 nA** (typ, VSTOR = 2.1 V) | **Fails on power and on input max.** 110 mA × 5.4 V = **0.59 W** = **12.1× short** of 7.2 W (trickle only); and 5.1–5.5 V input cannot see the array's **9.58 V** cold `V_oc` without a front-end limiter that must sink up to 6.6 W (ADR-050 §2(d).2). **Its 488 nA is the best quiescent in the class and proves the class exists — at 0.1 A.** |
| **TPS63060** | TI **SLVSA92C** (Nov 2011 – rev. Sept 2020) | **2.5 V** min | **12 V** max ("High Input Voltage, Buck-Boost Converter With 2-A Switch Current"); η up to 93 % | output current at 5 V (VIN < 10 V) = **2 A in buck mode** → **10.8 W** at 5.4 V | **< 30 µA** typ; has an **EN** pin, "converter can be disabled to minimize battery drain", "load disconnect during shutdown" | **The only verified part that carries 7.2 W and survives 9.58 V.** 9.5820 V × 1.25 = 11.98 V ≤ 12 V (1.25× margin, ADR-050 §3.2). **But its 2.5 V input minimum means it cannot take 1.5 V (wing-parallel) or 0.5 V (cell-parallel) — so it does not unlock parallel.** Its 30 µA = 162 % of the night anchor → admissible **only** in a disabled-to-sub-µA state, which ADR-050 §3.6 already requires and its EN pin makes plausible (`TODO(unverified)`: the datasheet's actual shutdown current was not read for this analysis). |
| **TPS63020** | TI (datasheet fetched) | **1.8 V** min | **5.5 V** max; 4-A switches; I_Q 25 µA | 4 A switch | 25 µA | **Fails the 9.58 V input** (5.5 V max) and its 25 µA ≥ 135 % of the anchor. |
| **TPS61200** | TI (datasheet fetched) | **0.3 V** min; startup into full load at 0.5 V | **5.5 V** max | up to **600 mA at a 5-V output** = **3.0 W** | **< 55 µA** | **Fails on all three counts:** 5.5 V max input (dies at 9.58 V), 3.0 W = **2.4× short** of 7.2 W, and 55 µA = **297 %** of the anchor. |
| **TPS61099** | TI **SLVSD88M** (Jul 2016 – rev. Aug 2026) | **0.7 V** min | **5.5 V** max | min **0.8 A** switch peak limit; up to **300 mA** 3.3→5 V (≈ 1.5 W) | ~**1 µA** (light load) | **Fails:** 5.5 V max input; ~1.5 W is ~4.8× short of 7.2 W. (Its ~1 µA quiescent is excellent — again, at the wrong power.) |
| **LTC3105, LTC3129(-1), ADP5091, ADP5092, SPV1040** | **`TODO(unverified)` — NOT VERIFIED. Retrieval failed from this host.** | — | — | — | — | **See the retrieval-failure note below.** The repo's own survey (`docs/adr/050-mppt-charge-path.md` §3.2, `docs/analysis/mppt-charge-path-specification.md` §2(d).1) records: every ≤ 1.5 V-capable part tops out at **5.1–5.5 V input**; every ≥ 12 V-capable part starts at **2.42–2.5 V**; the LTC3129-1 is quoted as **≥ 2.42 V** in, **15 V** max, **200 mA** out, **1.3 µA** I_Q. That is **cited from the repo, not re-verified here.** |

**Retrieval-failure note (reproducible, and it is a finding, not an excuse).** The Analog
Devices parts in the brief's list could **not** be checked from this host. Every path failed:
`analog.com` returned **HTTP 403 "Access Denied" (Akamai `errors.edgesuite.net`)** to `curl`, to a
**real headless Chrome** (CDP), and to the `r.jina.ai` text proxy; `mouser.com` returned a
**bot-block page**; `lcsc.com` returned an **Akamai 403**; `uk.farnell.com` returned
`ERR_HTTP2_PROTOCOL_ERROR`; `tme.eu` served a **Cloudflare challenge**. This matches the note
already in `docs/adr/051-hub-array-and-cut-topology.md` §2.2 ("downloading `analog.com` failed
from this host on 2026-10-07"). **So no ADI figure is asserted in this document** — they are
`TODO(unverified)`, exactly as ADR-051 left them.

### 4.1 The finding: the parallel topologies are **BLOCKED**, by a part-selection gap

```
required for any PARALLEL arrangement : V_in ≤ 1.5 V (wing-parallel) … ≤ 0.5 V (cell-parallel)
required for THIS array               : ~7.2 W into 5.4 V  → ~1.33 A out, input current 4.8–14.4 A
required at night                     : I_Q ≤ ~2–5 µA from the 5.4 V bank
required for the array's cold V_oc    : V_in rating ≥ 12 V

verified sub-2.5 V parts   → all top out at 5.1–5.5 V in, and deliver 0.59 W (bq25570)
                             to 3.0 W (TPS61200)  = 2.4× to 12.1× SHORT of 7.2 W
verified ≥ 12 V-input parts → all start at 1.8–2.5 V  (TPS63060 is the only one ≥ 12 V
                             rating; TPS63020 tops out at 5.5 V)
```

**No part I verified covers a sub-2.5 V input AND ~7.2 W AND a night-safe I_Q AND ≥ 12 V input.
The gap is structural, not a search failure:** a 1.5 V input at 7.2 W needs **4.8 A** and a 0.5 V
input needs **14.4 A**, which is a **multi-amp converter** — a different silicon class from every
nano-power harvester, with an inductor and switches measured in grams and a quiescent draw in the
tens of µA. **So the parallel topologies are BLOCKED — not merely expensive — by available
silicon at flight mass.** The series string's 6.0 V / 1.2 A operating point is the only one the
available parts can serve, and the only verified part that serves it end-to-end is the TPS63060
(2.5–12 V in, 2 A/10.8 W out, disabled-to-shut-down for the night).

**And note what the parallel claim would cost if silicon were free:** even an ideal sub-2.5 V
converter at 1.5 V in would carry **4.8 A** and pay **(4.8/1.2)² = 16×** the I²R loss of the
series case — plus a blocking diode on **every** branch at **20 %** of the branch voltage. The
physics does not go away because a part appears.

---

## 5. THE SINGLE CONDITION THAT WOULD CHANGE MY MIND, AND THE CHEAPEST EXPERIMENT

### 5.1 The single condition

> **I would move per-cell bypass diodes from Rank 3 to Rank 2 — i.e. accept that the proposition's
> "across every cell" is the correct granularity — if a measurement shows that the DOMINANT
> failure mode of a cracked cell in *this* mount (end-only, no adhesive bond, hand-soldered,
> thermal-cycled to −60 °C) is a PARTIAL/SOFT SHUNT rather than an OPEN or a hard short.**

Why exactly this condition and no other:

- On the **open** failure mode, a **per-wing/hub-side** diode already keeps the string charging
  (F2), and per-cell granularity only adds ≈ 1.2 W of peak power the 0.388 W mission does not need
  (F4).
- On the **hard-short** failure mode, **no** bypass diode helps at all and none is needed (F1).
- On the **soft-shunt** failure mode, F1 and F2 together show the **per-cell** diode is the
  **only** protection — the per-wing diode cannot see it (the wing still sources voltage). So if
  soft shunts dominate, the proposition's per-cell granularity becomes **load-bearing for
  hot-spot safety**, and the cost in F5 becomes a cost worth paying.

So the condition is: **the failure-mode distribution of a cracked bare cell in this mount.** All
three of my other disagreements (mechanism attribution, cut-away dead mass, granularity economics)
are **independent of the failure mode** and would survive it — they are reasons to rank per-cell
**second**, not to reject it.

### 5.2 The cheapest experiment that would settle it

**Bend-to-crack bench test on scrap LARGE cells** — no board, no flight hardware, no converter:

```
fixtures : 2 scrap LARGE cells clamped END-ONLY (the chosen mount) across a 3 mm gap,
           one with a soldered joint at each pad, one bare
measure  : after each bend/thermal cycle, 4-wire measure (a) R across the cell at 0 V,
           (b) the cell's I-V curve at one illumination level
repeat   : until each cell is unambiguously dead; record the LAST measured R and I-V
classify : R ≈ open (≫ 1 Ω, I ≈ 0) = OPEN ; R < 0.3 Ω = HARD SHORT ;
           R in ~0.3 Ω … 1 kΩ with a degraded I-V = SOFT SHUNT
also add : one thermal cycle to −60 °C (or a dry-ice/ethanol soak) before the bend,
           because dV_oc/dT = −2.1 mV/°C/cell (wing-electrical §5.1) is the only
           temperature coefficient the repo has, and the mount is a temperature-cycled
           no-bond joint by construction
cost     : 2 scrap cells, a multimeter, a DC load or a resistor + DMM, and an afternoon.
           The measured I-V ALSO settles the unresolved 1.2 A vs 1.08 A question
           (docs/analysis/wing-electrical.md §0.2) and the pads' geometry
           (ADR-049's "order blocker"), so it pays for itself twice.
```

**And the second-cheapest, which settles the other half of the brief's part question:** the
**hub-array / parallel question is already closed by the arithmetic and the verified part set
(§4.1)** — no experiment is needed to reject parallel. The only experiment that could reopen it is
**finding a part** (a $0 search, not a bench test): a datasheet with `V_in ≤ 1.5 V` **and** ~7.2 W
out **and** `V_in ≥ 12 V` **and** `I_Q ≤ 2 µA`. Nobody I can find has published one; if the ADI
parts could be read from a host that `analog.com` does not block, that is where to look first.

---

## 6. BOTTOM LINE — where I AGREE and where I DISAGREE with the naive "add bypass diodes, keep series"

### 6.1 Where I AGREE

1. **Keep the series string.** My independent derivation (§1) puts the 12-cell series string at
   Rank 1, for four separate reasons: it is the only arrangement above the 5.4 V bank (no step-up
   needed); it has the lowest array current (1.2 A vs 2.4–14.4 A) and therefore 1×–144× the
   conduction loss of the alternatives; it needs the fewest diodes (one per wing, and they idle);
   and it is the only topology the verified part set can serve at all (§4.1).
2. **Add bypass diodes — they are necessary.** Without a bypass path, an open cell or a cut wing
   kills the array and reverse-stresses cells at hot-spot dissipation
   (`docs/adr/046-wing-board-interface.md` §2.3; `wing-electrical` §4.1). With it, the array keeps
   charging.
3. **Do not go parallel.** Parallel buys no watts, multiplies current 4×–144×, needs blocking
   diodes on every branch at 20–60 % of the branch voltage, and is **blocked by available
   silicon** at ≤ 1.5 V (§4.1).
4. **The converter is what tolerates *voltage* consequences.** A hard-shorted cell is absorbed by
   the converter's 2.5–12 V window with **no diode at all**.

### 6.2 Where I DISAGREE

1. **The mechanism is misattributed.** A bypass diode does **not** "make the converter tolerate"
   anything — the converter already tolerates the voltage of every cell failure including a hard
   short (F1, F7). The diode restores a broken **path**. Two different requirements; the sentence
   credits the wrong part.
2. **"Every cell" is not a substitute for "every 2-3 cells."** The load-bearing protection is the
   **hub-side per-interface** diode, because a cut jettisons the wing and everything soldered to it
   (F3). A flight with per-cell diodes and no populated hub-side interface diodes is **worse off
   than the baseline**: the first cut kills the array. ADR-051 §2.4 decision 4.2 already gets this
   right; the proposition's parenthetical does not.
3. **Per-cell granularity buys power no recorded requirement asks for.** 86 % vs 69 % of the array
   retained per event = ≈ 1.2 W, on a mission with a 15.85× peak-to-average surplus and a 0.388 W
   average (F4). It is worth paying **only** if soft shunts dominate (F2 + §5.1) — which is
   unmeasured.
4. **Per-cell bypass is the option with the worst buildability on this mount** (F5): no board face
   behind a no-bond end-mounted cell; +24 hand-soldered joints (+75 %); and a **single reversed
   diode silently creates the hard-short failure mode it was fitted to prevent**.
5. **A number in the repo's cut ladder is optimistic** (F6): the interface bypass diodes' forward
   drops (one per cut) move the 2-cut case from 3.0 V to **2.30 V**, **below** the 2.5 V converter
   floor — so the hub array stops being optional at **two** cuts, not three. `TODO(unverified)` on
   the specific part's `V_f`.

### 6.3 The verdict in one paragraph

**The series string survives every falsification attempt I could make, and the parallel
alternatives do not survive the arithmetic or the part survey. So I agree with the proposition's
decision — keep the series string, add bypass diodes — and I disagree with two of its three
justifications and with its proposed granularity. The bypass diode is not a converter-tolerance
device; it is a path-restoration and hot-spot-clamp device, and the diode that must be populated
is the HUB-SIDE PER-INTERFACE one (≥ 2 A / 40 V), because that is the only one a cut cannot
jettison. Per-cell diodes are a real but second-order refinement, justified by one unmeasured
failure mode (soft shunts) and paid for in buildability risk on the very component they protect.**

---

## 7. Open items and retrieval failures carried, not dropped

1. **`TODO(unverified)` — the LARGE cell's pad geometry** (one pad per face is brief-given and
   measured only for the SMALL cell; ADR-049 calls the LARGE cell's pad layout *"not yet
   confirmed"* and its measurement *"the order blocker"*). Every per-cell-bypass buildability
   statement in §2.5 depends on it.
2. **`TODO(unverified)` — the real crack failure-mode distribution** (§5.1). This is the single
   measurement that would move per-cell bypass up or down the ranking.
3. **`TODO(unverified)` — the LARGE cell's actual MPP current** (1.2 A area-scaled vs 1.08 A from
   the 0.54 W listing, `wing-electrical` §0.2). Every current and loss number scales with it.
4. **`TODO(unverified)` — the chosen ≥ 2 A / 40 V Schottky's `V_f` at 1.2 A and at altitude/cold.**
   It sets the cut-ladder correction in F6 and the per-bypass losses in F4.
5. **`TODO(unverified)` — the TPS63060's actual shutdown current** with EN low (the disabled-state
   leakage that would justify its 30 µA operating I_Q against the 100 µW anchor). Its EN pin and
   "load disconnect during shutdown" are verified; the number is not.
6. **`TODO(unverified)` — the ADI low-V_in harvester family** (LTC3105, LTC3129(-1), ADP5091,
   ADP5092, SPV1040). **Not verified — `analog.com` HTTP 403 (Akamai) via curl, via headless
   Chrome and via the r.jina.ai proxy; Mouser bot-block; LCSC 403; Farnell HTTP/2 error; TME
   Cloudflare challenge.** No figure for these parts is asserted here. The repo's survey figures
   (`docs/adr/050-*.md` §3.2, `mppt-charge-path-specification.md` §2(d).1) are cited, not adopted.
7. **Not re-derived here (cited only):** the wing geometry / insolation work
   (`docs/analysis/wing-insolation-geometry.md`, `wing-omnidirectional.md`), the progressive-shed
   ladder (`docs/analysis/wing-ladder.md`), the jettison study, and the hub-array sizing
   (ADR-051 §2.2). None of them changes the topology conclusion above.

**No hardware is ordered by this document. It is analysis only.**
