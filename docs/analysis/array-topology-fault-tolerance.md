# Array topology fault tolerance — cracked-cell and wing-cut behaviour of seven solar-array topologies, with the converter part search that decides which are buildable

> **STATUS: ENGINEERING ANALYSIS — NOT A DECISION RECORD.**
> This document is an engineering comparison produced **for the operator to decide on**. It is
> **not** an ADR, it **amends nothing**, it **orders nothing**, and nothing in it may be read as an
> accepted design. It is the evidence base for a decision the operator has not yet taken, and it
> **does not supersede any record by itself** — where it disagrees with a committed record it says
> so explicitly and names the record and clause (§7 is the only place it argues a supersession, and
> it argues it *about* ADR-051, it does not perform it).
>
> Every number is one of:
> **(a) computed** here with its formula shown (re-runnable:
> `docs/analysis/array_topology_fault_tolerance_model.py`, stdlib only — `python3
> docs/analysis/array_topology_fault_tolerance_model.py` prints every figure in this document);
> **(b) cited** to an in-repo file and section;
> **(c) read from a vendor product page** on 2026-10-07 with the reading route named, because a
> product page is **not** a datasheet and is labelled as such below; or
> **(d) marked `TODO(unverified)`** with the exact open question named.
>
> **No part number, datasheet figure or URL here is invented.** Two figures come from *datasheets*
> properly (the bypass diodes, §5.3); the converter figures come from vendor product pages and are
> labelled accordingly (§5.4) — the distinction matters and is kept throughout.

| | |
|---|---|
| Date | 2026-10-07 |
| Author | subagent (Hermes), branch `analysis/array-topology-fault-tolerance`, worktree `~/worktrees/bf-topo` |
| Base | `ce2366e` (`github/main`, tip at time of writing) |
| Lens | **array-level topology, fault tolerance and charge-path buildability** — not board layout, not wing geometry, not mechanical |
| Scope ruled out | no schematic edit, no BOM freeze, no ADR, no wing redraw, no part ordered |
| Question answered | *"can the circuit be designed so the converter tolerates individual CRACKED cells — i.e. avoid series wherever reasonably possible?"* (operator, via the manager) |
| Reads first | ADR-049, ADR-050, ADR-051, `docs/analysis/wing-electrical.md`, `docs/analysis/mppt-charge-path-specification.md`, `docs/analysis/array-power-architecture.md`, `docs/analysis/wing-ladder.md` |
| Companion artefact | `docs/analysis/array_topology_fault_tolerance_model.py` (prints every number below) |

---

## 0. The honest framing, restated (so §4 is read with it in view)

The operator's question is a good one and the answer is not "all parallel". Three statements are
true at once and §4 shows all three:

1. **Series exists to keep the current sane.** 12 cells in parallel at 0.5 V would be
   **14.40 A** for 7.20 W against **1.20 A** at 6.0 V — a **12× current** and therefore
   **144× the I²R loss** in the same conductor network
   (`I²R ratio = (14.40/1.20)² = 144×`; model §0). Fully parallel is therefore **not** an
   efficiency-dominated choice, and it is not "free".
2. **Unprotected series is the actual defect.** With no bypass diode an *open* cell makes the
   string current zero: the array goes to **0.00 W**, not to 11/12 of its power
   (`docs/analysis/wing-ladder.md` §3.1 states this for a cut; the same physics applies to a
   cracked cell that opens). That is a **100 % loss from one failure** — the thing to fix.
3. **Per-cell bypass converts "a cracked cell kills the string" into "a cracked cell costs one
   cell"** — **8.33 %** of the array's 12-cell voltage, or **14.67 %** once the bypass diode's own
   forward drop is counted (§4.1). This is the operator's intuition, and it is correct.

So the real question §4 answers is not *series or parallel* but **how much diode and converter
complexity buys how much survivability, and which of those purchases a real, purchasable converter
can actually serve.** On that test the answer is unambiguous and it is *not* parallel (§5, §8):
**the parallel families are the ones no verified converter can serve.**

---

## 1. Inputs (cited, not re-derived)

| Quantity | Value | Source |
|---|---|---|
| Cells | 12 = **4 wings × 3** | ADR-006; ADR-049 §Decision; ADR-051 §1.1 |
| LARGE cell | 78.55 × 38.90 × 0.21 mm, **30.6 cm²**, ~0.50 V, ~1.2 A, 1.50 g, one pad per face | ADR-049 §Measured inputs; ADR-051 §1.4 |
| Wing | 3 cells series = **1.50 V**, **1.80 W** | ADR-006; ADR-049 |
| Array | 12 cells series = **6.00 V @ 1.20 A = 7.20 W** | ADR-049; `wing-electrical` §3(a) |
| Cell nameplate density | `0.50 × 1.20 / 30.6 = ` **19.608 mW/cm²** | computed; ADR-051 §1.4 |
| Cell cold Voc (per cell) | `0.62 + 2.1e-3 × 85 = ` **0.7985 V** at −60 °C | `wing-electrical` §5.1 — its two coefficients are `TODO(unverified)` |
| Array cold Voc | 12s **9.5820 V** · 6s **4.7910 V** · 3s **2.3955 V** · 1 cell **0.7985 V** | computed from the above |
| Bank | 3.3 F at ≤ **5.40 V** top, 3.00 V floor, **33.264 J** usable, no battery | ADR-006; ADR-047 §3.2; ADR-050 §3.3 |
| Radio draw | **6.15 W** peak, **0.388 W** daylight mission average | ADR-047 §1.2; `docs/POWER-BUDGET-V9-D2BE.md` line 85 |
| Night anchor | **100 µW** | ADR-036 (via ADR-047 §6.1) |
| Mounting | end-only, **no adhesive bond**, cells free to float; failure mode is THERMAL cracking | `docs/analysis/pico-balloon-solar-survey.md` §2.1/§4.3; ADR-052 (branch `adr/cell-mounting-end-only`, **Proposed**, not on main) |
| Cut wiring today | 4 wings **in series through the hub**; bypass diodes **DNP** and under-rated (BAT54, 200 mA/30 V) | `docs/WING-TO-HUB-SOCKET-SPEC.md` §3.1; ADR-046 §2.3/§6; ADR-051 §1.1, §2.7 |
| Hub array sizing | 106.1 cm² (horizontal face) or 64.9 cm² (vertical fins) for 0.388 W | ADR-051 §1.4 (supersedes the brief's single `0.3051` figure in the sense that **both** planes must be quoted) |
| Insolation factors | vertical-plane `0.30511`; horizontal-plane day-mean `0.18653` | `wing-insolation-geometry.md` §2; `wing-omnidirectional.md` §1.3 |
| Day length | **7.852 h** at 50.0 °N winter solstice → **16.15 h dark** | `wing-omnidirectional.md` (H₀ = 58.8884°); latitude/season assumed — `TODO(unverified)` |
| Converter input spec (committed) | **1.50 V … 9.58 V**, rating ≥ 12 V; practical floor 3.0 V | ADR-050 §3.2 |
| Converter quiescent bound | **I_Q ≤ 5 µA** from the bank at 5.4 V (target ≤ 2 µA) | ADR-050 §3.6 |
| Assumed power-path efficiency | **85 %** (`TODO(unverified)`) | ADR-050 §1 |
| Land ampacity | 4.0 × 1.2 mm tab land carries **2.73 A** (1 oz, ΔT = 10 °C) | `wing-electrical` §6.3 |

**The single most important column in §4 is not the power loss — it is the array-side current**,
because that number simultaneously sets (i) the I²R penalty, (ii) whether the existing tab lands
stay legal, and (iii) whether *any* low-quiescent converter can carry the array at all. §5 shows
(iii) is the one that decides the design.

---

## 2. The two cracked-cell failure modes, stated precisely before they are compared

The brief's framing — *"a shorted cell in an unprotected series string is the worse case"* — is
worth correcting with the arithmetic, because the correction changes which topology is safe:

**In a SERIES string, the OPEN cell is the killer and the SHORT is (nearly) benign.**

```
cell OPENS   -> the one current path is broken.  String I = 0 -> array P = 0.00 W  (100 % loss)
cell SHORTS  -> the short IS a conductor.  The string continues through it with n-1
                contributing cells -> P = (n-1)/n of nominal = 11/12 = 91.67 % (8.33 % loss)
```

A hard short costs **8.33 %** and is *self-healing* in the sense that the string keeps working.
A **soft / partial** short (a crack that leaves a low-resistance shunt) is the intermediate case
that actually hurts in series: it eats part of the string's voltage and dissipates it locally as a
hot spot. Its magnitude depends on the shunt resistance, which **is not measured →
`TODO(unverified)`**.

**In a PARALLEL group the SHORT is the killer.**

```
one cell SHORTS in a 12-cell parallel group -> the group node is clamped near 0 V; the other
   11 cells dump their full photocurrent into the short:
      11 × 1.20 A = 13.20 A into one cell  ->  array ~ 0.00 W  (~100 % loss)
one cell OPENS in a parallel group -> benign: the other 11 continue, 11/12 = 91.67 %
```

**Consequence for §4, stated once:** the *same* physical crack is survivable in one family and
catastrophic in the other, depending on whether the cells are in series or parallel with each
other — and the two families are exact opposites. **This is why "avoid series wherever reasonably
possible" is not a safe simplification:** moving to parallel trades a *100 %-loss open* for a
*100 %-loss short*, and a shorted cell is the failure mode a cracked, thermal-cycled cell is at
least as likely to produce as an open one (both are `TODO(unverified)` — nobody has measured the
open/short split for this cell class in flight).

---

## 3. The seven topologies

| # | Name | Shape | Notes |
|---|---|---|---|
| **T1** | 12S + 12 cell diodes | all 12 in series; a bypass diode **across every single cell** | the literal reading of the brief's T1; **as specified it has no diode on the hub side** → see §4.2b |
| **T2** | 12S + 4 group diodes | all 12 in series; one bypass diode **across every group of 3** (one per wing) | this is the ADR-046 §2.3 / ADR-051 §2.4 `D_BP1…D_BP4` provision |
| **T3** | 4P × 3S | 4 wings in **parallel**, each wing **3 cells in series** (1.5 V) with a blocking Schottky per string | the naive "get rid of series" answer |
| **T4** | 2S2P | two wings in series (3.0 V) × two such pairs in parallel | the naïve "split the difference" answer |
| **T5** | 12P | all 12 in parallel (0.5 V) with a blocking Schottky per cell-group | the brief's T5 |
| **T6a** | 12S + 12 cell **AND** 4 wing diodes | all 12 in series, per-cell bypass **plus** a hub per-wing bypass in parallel with the three cell diodes | the hybrid §3.1 argues for |
| **T7** | 4 × (3S + own harvester) | 4 independent wing strings, **each with its own converter** into the common bank | the distributed-MPPT hybrid; the only topology in which a cut *cannot* move the bus voltage |

### 3.1 Why T6a is a genuinely better hybrid than T1, and why T1-as-written is not buildable

Two facts, both from the repo, force it:

1. **A wing cut at the tab removes the wing's own diodes with the wing.** The bypass provision that
   survives a cut is the **hub-side** one — ADR-051 §2.4 decision 4.2 says exactly this: *"A cut
   leaves the wing's socket lands open, which opens the string; the string continues only because
   the interface's bypass Schottky (D_BP1…D_BP4, across `W<n>_SOLAR_P` ↔ `W<n>_SOLAR_N`) shorts
   the removed wing's position."* Per-cell diodes sitting **on the wing** are gone the moment the
   wing is.
2. **So T1-as-written has no cut tolerance at all** — its 12 diode locations all leave with a cut
   wing, the socket opens, and the array goes to **0.00 W**. This is the same "cut = suicide"
   failure ADR-051 §1.3 exists to prevent, reached by a different route.

`T1 + the 4 hub diodes = T6a`, and T6a has both properties: **per-cell granularity** for a crack
and **one diode drop instead of three** for a cut (§4.1, §4.2). T6a is therefore not a decorative
extra — it is the form T1 has to take to be cut-tolerant at all.

---

## 4. The comparison, item by item

All arithmetic from `docs/analysis/array_topology_fault_tolerance_model.py`. `V_F = 0.38 V` is the
bypass diode's forward drop at 1.2 A, **interpolated** from the PMEG4030ER's datasheet figure of
460 mV at 3 A — `TODO(unverified)`: 1.2 A is not a tabulated point.

### 4.0 The summary table

| Topology | V_nom | **I_array** | I²R vs all-series | tab-land margin (2.73 A) | cold Voc | cracked OPEN | cracked SHORT | 1 wing cut | post-1-cut bus | converter family it needs |
|---|---|---|---|---|---|---|---|---|---|---|
| **T1** as written | 6.00 V | **1.20 A** | **1×** | 2.27× | 9.58 V | **−14.67 %** | −8.33 % | **−100 %** (no hub diode) | 0 V | wide-input, ≥12 V (ADR-050 §3.2) |
| **T2** | 6.00 V | **1.20 A** | **1×** | 2.27× | 9.58 V | **−31.33 %** | −8.33 % | −31.33 % | 4.12 V | wide-input, ≥12 V |
| **T3** | 1.50 V | **4.80 A** | **16×** | **0.57× FAILS** | 2.40 V | −25.00 % | −25.00 % | −25.00 % | 1.50 V (< floor) | low-Vin boost ≤5.5 V |
| **T4** | 3.00 V | **2.40 A** | **4×** | 1.14× | 4.79 V | −50.00 % | −50.00 % | **−50.00 %** | 3.00 V | wide-input, ≥6 V |
| **T5** | 0.50 V | **14.40 A** | **144×** | **0.19× FAILS** | 0.80 V | −8.33 % | **~−100 %** | −25.00 % | 0.50 V (< floor) | sub-0.8 V cold-start harvester |
| **T6a** | 6.00 V | **1.20 A** | **1×** | 2.27× | 9.58 V | **−14.67 %** | −8.33 % | **−31.33 %** | **4.12 V** | wide-input, ≥12 V |
| **T7** | 1.50 V/string | **1.20 A**/string | **1×** | 2.27× | 2.40 V | −8.33 % (per-cell bypass in the wing) | −8.33 % | −25.00 % | **1.50 V, unchanged** | low-Vin boost, **one per wing** |

Column headings used below: **(1)** cracked-cell tolerance, **(2)** wing-cut tolerance,
**(3)** converter input range demanded + input current, **(4)** I²R penalty, **(5)** diode count and
mass, **(6)** back-feed/shading, **(7)** MPPT/harvester behaviour on mismatched strings.

---

### 4.1 T1 — all 12 in series, bypass diode across every single cell (12 diodes)

1. **Cracked-cell tolerance.** **OPEN:** the failed cell's own diode conducts, the string continues
   with 11 cells. `V = 11 × 0.50 − 0.38 = 5.12 V`; `P = 5.12 × 1.20 = 6.14 W` — **keeps 85.33 %,
   loss 14.67 %**, of which 8.33 points are the lost cell and 6.33 points the diode drop. With an
   ideal diode it would be 91.67 %. **SHORT:** a hard short is a conductor; the cell simply stops
   contributing: `11 × 0.50 = 5.50 V`, `P = 6.60 W`, **loss 8.33 %**, benign (the cell's own bypass
   diode is shorted out too, so it does nothing). A soft/partial short is the unattractive case and
   its magnitude is `TODO(unverified)`.
2. **Wing-cut tolerance.** **This topology as specified does not survive a wing cut.** The 3 cells
   of the cut wing take their 3 bypass diodes with them; the socket lands open; **the string
   opens; the array delivers 0.00 W — a 100 % loss.** If instead the cut is made *below* the cell
   diodes (so they stay in circuit), the 3 diodes conduct in series:
   `V = 4.50 − 3 × 0.38 = 3.36 V`; `P = 4.03 W` — **loss 44.00 %**, bus 3.36 V (still above the
   2.5 V floor). T1's cut cost is therefore either 100 % or 44 % — never better than T2's 31.33 %.
3. **Converter input range demanded.** `1.50 V` (one wing, below every wide-input part's floor —
   ADR-050 §3.2) to `9.58 V` (cold Voc, 12 cells); **rating ≥ 12 V**, prefer ≥ 16 V. **Input current
   1.20 A ideal / 1.41 A at the assumed 85 %** (`7.20/6.0`; `7.20/(0.85 × 6.0)`).
4. **I²R penalty.** **1× — the reference.**
5. **Diode count and mass.** 12 diodes. Named, verified part: **PMEG4030ER**, 40 V / 3 A, SOD123W
   (Nexperia, 23 Jan 2023; §5.3). Continuous current through any one diode = **1.20 A**, i.e.
   2.50× under a 3 A part. Diode mass: **108 mg for 12**, from a **9.0 mg/diode ESTIMATE** (SOD123W
   is 2.6 × 1.7 × 1.0 mm at ~2 g/cm³) — `TODO(unverified)`, no datasheet states mass.
6. **Back-feed / shading.** Not applicable in the parallel sense: one current path means a *shaded
   cell* is the same event as an open cell and its own diode handles it (`wing-electrical` §4.2
   establishes that a **per-wing** diode does **not** protect a cell inside its own string — only a
   per-cell diode does, which is what T1 has). No blocking diodes needed.
7. **MPPT / harvester behaviour.** One series string, one MPP — no string mismatch exists. The
   single converter sees one I-V curve. **This is T1's real advantage and it is not a small one**
   (contrast T3/T4/T5, §4.3–§4.5).
8. **ADR-051 cut ladder.** T1 does not implement it (see §7).

---

### 4.2 T2 — all 12 in series, bypass diode across every group of 3 (4 diodes)

1. **Cracked-cell tolerance.** **OPEN: a single cracked cell costs THREE cells.** The group of 3
   becomes an open circuit, so the string current is forced through the group's bypass diode,
   shunting the 2 *good* cells along with the failed one:
   `V = (12 − 3) × 0.50 − 0.38 = 4.12 V`; `P = 4.94 W` — **loss 31.33 %** (25 points of lost cells
   + 6.33 points of diode drop). **SHORT: 8.33 %** (the group still conducts through the short;
   the group diode stays off). **The asymmetry is the finding: a group-bypass design is fine for a
   short and quadratically bad for an open.**
2. **Wing-cut tolerance.** *This is the same event as T2's cracked-cell-open case*, because the
   diode is across exactly one wing: `V = 4.12 V`, `P = 4.94 W`, **loss 31.33 %**, bus **4.12 V** —
   above the 2.5 V floor and comfortably above an LTC3115-1's 2.7 V. `docs/WING-TO-HUB-SOCKET-SPEC.md`
   §5 + ADR-051 §2.4 decision 4.2 mandate populating exactly these 4 diodes.
3. **Converter input range.** Identical to T1: `1.50–9.58 V`, rating ≥ 12 V, **1.20 A / 1.41 A**.
4. **I²R penalty.** **1×** (reference).
5. **Diode count and mass.** **4 diodes** — the cheapest of every topology here. Same verified
   part. Estimated mass **36 mg**.
6. **Back-feed / shading.** One path, no blocking diodes. But note per `wing-electrical` §4.2: the
   per-wing diode does **not** protect a cell inside its own string, so a *partial* shading event
   inside a wing is unprotected in T2 (it is protected in T1/T6a).
7. **MPPT.** Single string, single MPP — no mismatch problem.
8. **ADR-051 cut ladder.** T2 is the topology ADR-051 §2.4's ladder table describes. See §7: the
   table's *shape* is right and its *numbers* are 0.38 V/cut optimistic.

---

### 4.3 T3 — 4 wings in PARALLEL, each 3 cells in series (1.5 V), blocking Schottky per string

1. **Cracked-cell tolerance.** With **no** in-branch bypass: an **OPEN** cell opens its branch; the
   other 3 branches continue: `P = 3 × 1.80 = 5.40 W`, **loss 25.00 %**. A **SHORT** cell drops that
   branch to 2 cells = 1.0 V; the branch is now *below* the shared bus, so its blocking Schottky
   reverse-biases it and the branch delivers nothing: **loss 25.00 %**. (Without the blocking diode
   the bus would drive current *backwards* through the branch's 2 good cells — a hot spot.
   **The blocking diode is not optional; it is what converts back-feeding into dropping out.**)
   Adding per-cell bypass inside each branch would reduce both to 8.33 % — 12 more diodes.
2. **Wing-cut tolerance.** A cut wing removes one branch; the other 3 stay at **1.50 V**:
   `P = 5.40 W`, **loss 25.00 %**, and **the bus voltage does not change at all** (always 1.50 V).
   That invariance is T3's genuine structural advantage. **But 1.50 V is below the input floor of
   every wide-input converter** (TPS63060 2.5 V, TPS63070 2.0 V, LTC3115-1 2.7 V) — so the bus is
   *usable as a source* only by a **boost** part with ≤ 5.5 V input, and §5 shows those cap at
   0.1–0.4 A. **The topology's cut tolerance is real and its converter does not exist.**
3. **Converter input range.** `1.50 V` nominal (1.0 V with a shorted cell) to a **cold Voc of
   2.40 V** (3 cells × 0.7985 V) — `1.50–2.40 V`, so a ≥ 3 V-rated input suffices and the 9.58 V
   problem **disappears**. **This is the one large benefit of going parallel.** **Input current
   at 7.20 W: 4.80 A ideal / 5.65 A at 85 %.**
4. **I²R penalty.** `(4.80/1.20)² = ` **16×** the all-series loss for the same conductor network —
   plus the existing 4.0 × 1.2 mm tab lands are **0.57× — over their 2.73 A rating** at ΔT = 10 °C
   (`wing-electrical` §6.3). Either the lands change or the network is split four ways.
5. **Diode count and mass.** 4 blocking Schottky (one per branch) minimum; +12 if per-cell bypass
   is added. Verified parts are the same PMEG4030ER/PMEG4020ER family. Estimated mass **36 mg**
   (4 diodes).
6. **Back-feed / shading.** Blocking diodes **required, one per string**; without them a shaded or
   lower-voltage branch is **back-fed** by the others (current driven backwards through its cells =
   a hot spot). With them, a shaded branch simply drops out and the others are undragged — a real
   advantage over series. The cost is 4 diodes and their forward drop (0.38 V × 1.2 A = 0.46 W per
   branch that is *not* delivering). `docs/analysis/pico-balloon-solar-survey.md` §7 item 5 records
   that the pico-balloon world does exactly this ("one Schottky per parallel group" — KS4VA uses
   three SMD Schottkys "to 'steer' or isolate the dark solar panels from the illuminated one";
   NIBBB uses 1N5817 × 3).
7. **MPPT / harvester behaviour on mismatched strings — the classic failure of naive parallel
   designs, addressed explicitly.** Four parallel strings of *nominally* identical voltage will not
   stay identical: a shaded wing, a warm wing, a cracked wing and a wing at 60 % insolation all
   present different MPP voltages. **A single MPPT front-end sees ONE node voltage**, so it can only
   hold one string at its maximum; the others run off-MPP, and with a plain CV clamp the strongest
   string *binds* the bus and the weaker strings contribute little or nothing. This is not a
   tuning issue — it is structural: one converter has one input operating point. **Options:**
   (i) accept the mismatch (the array's output is set by the *weakest* string at the common
   voltage — the parallel analogue of the series current limit); (ii) go to **T7**, one converter
   per string, which harvests every string at its own MPP and removes the problem entirely;
   (iii) add per-string MPPT, which *is* (ii). **A single MPPT will not "handle" four mismatched
   parallel strings; it will follow one of them.**
8. **ADR-051 cut ladder.** Not applicable — T3 is not a series chain through the hub, so the
   1.5 V-per-cut ladder does not describe it at all.

---

### 4.4 T4 — 2S2P: two wings in series (3.0 V) × two such pairs in parallel

1. **Cracked-cell tolerance.** **OPEN:** the affected 6-cell branch drops to 5 cells = 2.5 V; the
   intact branch sits at 3.0 V, so the 2.5 V branch's blocking diode reverse-biases it and the
   branch **drops out**: `P = 3.60 W`, **loss 50.00 %**. (With per-cell bypass the branch would sit
   at `2.5 − 0.38 = 2.12 V` and still be blocked — the parallel topology's mismatch penalty does
   not go away.) **SHORT:** same 50.00 %, for the same reason at 2.5 V.
2. **Wing-cut tolerance.** One wing cut leaves its partner as a **single 1.5 V wing**, which the
   intact 3.0 V pair **blocks**: `P = 3.60 W`, **loss 50.00 %**, bus stays at 3.00 V (usable).
   **A single cut costs half the array — worse than T3's 25 %.** This is the non-obvious defect of
   naive 2S2P: the top pair's voltage acts as a *floor* that the damaged pair cannot reach, so the
   damaged pair's surviving cells are worth nothing. Second cut on the other pair brings both to
   1.5 V → bus 1.5 V, `P = 3.60 W` again.
3. **Converter input range.** `3.00 V` nominal to a **cold Voc of 4.79 V** (6 cells) →
   `3.00–4.79 V`. Both the TPS63060 (2.5 V floor) and the LTC3115-1 (2.7 V floor) are admissible at
   the nominal end, with **0.30 V** of margin against the LTC part and 0.50 V against the TI part.
   **Input current 2.40 A ideal / 2.82 A at 85 %.**
4. **I²R penalty.** `(2.40/1.20)² = ` **4×**. Tab lands: `2.73/2.40 = 1.14×` margin — the tightest
   topology that still passes.
5. **Diode count and mass.** **2 blocking** (one per pair) **+ 4 wing bypass = 6 diodes**, ~54 mg
   estimated.
6. **Back-feed / shading.** 2 blocking diodes **required** — exactly the mismatch situation above:
   without them the 3.0 V pair drives current backwards through the 2.5 V branch (hot spot).
7. **MPPT.** Worse than T3: the two strings' MPP voltages differ by a whole cell (0.5 V) after any
   single fault, so one MPPT follows whichever string it happens to be tracking and the other is
   lost. Single-MPPT 2S2P is the configuration that most cleanly demonstrates the parallel
   mismatch failure.
8. **ADR-051 cut ladder.** Not applicable.

---

### 4.5 T5 — all 12 in parallel (0.5 V)

1. **Cracked-cell tolerance.** **OPEN: 8.33 %** — the best in the table (a parallel group shrugs off
   an open). **SHORT: essentially 100 %.** The short clamps the common node and the other 11 cells
   drive their full photocurrent into it: `11 × 1.20 = 13.20 A` into one 30.6 cm² cell. **The worst
   single failure in the table, and it is worse than the series family's worst case (31.33 %).**
2. **Wing-cut tolerance.** 3 cells leave a 12-parallel array: `P = 5.40 W`, **loss 25.00 %**, bus
   **0.50 V** — far below any converter's floor. Usable only as a source for a sub-0.8 V
   cold-start harvester.
3. **Converter input range.** `0.50 V` nominal to a **cold Voc of 0.7985 V** (one cell) →
   `0.50–0.80 V`. **This is inside the cold-start window of only a few parts**: BQ25570 (600 mV typ
   / 700 mV max cold start), LTC3105 (250 mV start-up, V_IN 225 mV–5 V), ADP5091/ADP5092 (380 mV
   typical cold start, 0.08–3.3 V operating). All three are **0.1–0.15 A-output** parts (§5.4).
   **Input current at 7.20 W: 14.40 A ideal / 16.94 A at 85 %** — `1.20 A` through a cell pad and
   `0.19×` of the tab-land rating.
4. **I²R penalty.** `(14.40/1.20)² = ` **144×** — the number in the brief, confirmed.
5. **Diode count and mass.** 4 blocking (one per 3-cell group) minimum; 12 if every cell is
   individually blocked. ~36 mg (4).
6. **Back-feed / shading.** Blocking diodes required, and they are doing more work here than
   anywhere else: with 12 parallel cells at ±0.05 V of each other, every shading gradient
   back-feeds an unblocked cell. **12 blocking diodes is the honest count for real shading
   tolerance** (4 only protects at wing granularity, which is worthless when a *cell*-level
   mismatch is what a partial shade produces).
7. **MPPT.** The worst case of §4.3.7: a 0.5 V bus with 12 slightly different MPPs. A single
   converter's fraction-of-Voc loop will hold one operating point for all 12.
8. **ADR-051 cut ladder.** Not applicable.

---

### 4.6 T6a — 12S + per-cell (12) **AND** per-wing (4) bypass diodes

1. **Cracked-cell tolerance.** **OPEN: −14.67 %** (1 cell + 1 diode drop) — identical to T1, because
   the wing's remaining 1.0 V keeps the hub per-wing diode off and the failed cell's own diode
   conducts. **SHORT: −8.33 %**, benign. **This is the best cracked-cell behaviour available in the
   series family, at cell granularity.**
2. **Wing-cut tolerance.** The hub per-wing diode conducts and **shorts out the wing's three cell
   diodes**, so the cut costs **one** diode drop, not three:
   `V = 9 × 0.50 − 0.38 = 4.12 V`; `P = 4.94 W`; **loss 31.33 %**; bus **4.12 V**, usable by both the
   TPS63060 (2.5 V) and LTC3115-1 (2.7 V) floors. **T6a therefore gives T1's crack granularity AND
   T2's cut economy — it strictly dominates both**, which is why it is ranked first (§8).
3. **Converter input range.** `1.50–9.58 V` (identical to T1/T2), rating ≥ 12 V, **1.20 A ideal /
   1.41 A at 85 %**. Same wide-input requirement — which §5 shows is the *satisfiable* one.
4. **I²R penalty.** **1×.**
5. **Diode count and mass.** **16 diodes** — the highest count in the table. Verified part
   (§5.3). Estimated mass **144 mg** — still **≈ 1/10 of one 1.50 g cell**, and 16 × 9 mg is not a
   mass decision on a payload where ADR-049's whole 4-wing array is 12.85 g.
6. **Back-feed / shading.** No parallel strings, no blocking diodes, no back-feed. Per-cell diodes
   cover *partial* in-wing shading, which T2 cannot (`wing-electrical` §4.2).
7. **MPPT.** Single string, single MPP. No mismatch problem.
8. **ADR-051 cut ladder.** §7.

---

### 4.7 T7 — four independent wing strings, each with its own converter

1. **Cracked-cell tolerance.** One wing = 3 cells. With per-cell bypass inside the wing:
   `V = 2 × 0.50 − 0.38 = 0.62 V` for that wing; the wing's own converter follows it down and keeps
   harvesting `0.62 × 1.20 = 0.74 W`; array `= 5.40 + 0.74 = 6.14 W` — **loss 14.67 %**. Without
   in-wing bypass: that wing drops out, **loss 25.00 %**. **SHORT:** same class — the wing's
   terminal voltage falls and its own MPPT tracks it, so a short costs its wing's share (8.33 %)
   rather than clamping anyone else. **No other topology degrades this gracefully**, because in
   every other topology a fault propagates through a shared node.
2. **Wing-cut tolerance.** The cut wing's converter sees 0 V and idles; **the other three are
   electrically unaffected, and the bus voltage (the bank) does not move at all.** `P = 5.40 W`,
   **loss 25.00 %**, and **this is the only topology in which the cut CANNOT change the bus
   voltage** — there is no shared string node for the cut to open. The ADR-051 §1.3 failure mode
   ("the cut causes the loss of the vehicle it was meant to keep alive") is **structurally
   impossible** here.
3. **Converter input range.** Per string: `1.50 V` nominal to a **cold Voc of 2.40 V** — so the
   9.58 V problem disappears, as in T3. **Input current: 1.20 A per string (1.41 A at 85 %), four
   strings** — i.e. **the array-side current stays at the series value**, which is T7's decisive
   advantage over T3: four converters each at 1.20 A, not one converter at 4.80 A. The **bank-side**
   current is 1.33 A in every topology and is unaffected.
4. **I²R penalty.** **1× on the shared harness** (the bank-side 1.33 A), and **1× per string** — the
   16× penalty of T3 is *not* incurred, because the current is never summed on the array side.
   Tab lands: 2.27× margin. **This is the only parallel-family topology that keeps the existing
   lands and harness legal.**
5. **Diode count and mass.** **16 diodes**: 4 in-wing per-cell diodes per wing × 4 = **12 cell
   diodes**, plus **4 hub blocking/bypass diodes** (one per string). Or **4 blocking only** if a
   wing loss of 25 % is accepted. But the real mass cost is not the diodes: it is **four converters
   and four sets of passives** — at ADR-050 §3.7's ≈ 0.70–1.20 g
   per converter that is **+2.8–4.8 g**, on a payload where mass is *the* binding constraint
   (ADR-049, ADR-051 §1.5). **And the quiescent draw multiplies four times**: ADR-050 §3.6's
   `I_Q ≤ 5 µA` bound is **per converter**, so four converters must each be ≤ 5 µA to hold the
   total at the same 27 µW; at 5 µA each the line is **4 × 27 = 108 µW = 108 % of ADR-036's
   100 µW night anchor before the load.** That is a hard, quantified strike against T7.
6. **Back-feed / shading.** Each string is isolated by its own converter; a blocking diode is
   needed only for reverse protection of the string itself, not to prevent inter-string
   back-feed. **This is the cleanest answer to the shading problem in the whole table** — four
   shaded strings do not interact at all.
7. **MPPT.** **Four MPPTs, four operating points** — every string is harvested at its own maximum,
   which is exactly what T3/T4/T5's single-converter designs cannot do. This is the topology the
   question 7 failure mode *requires*.
8. **ADR-051 cut ladder.** Not applicable — there is no ladder, because there is no series chain.
   The cut ladder becomes a **power** ladder (7.20 → 5.40 W) instead of a **voltage** ladder.

---

## 5. THE BINDING QUESTION — the real part search

### 5.1 What a candidate must satisfy (four constraints, all of them hard)

| # | Constraint | Value | Source |
|---|---|---|---|
| (a) | **accept the topology's input range** | T1/T2/T6a: 1.50–9.58 V (rating ≥ 12 V). T3: 1.50–2.40 V. T4: 3.00–4.79 V. T5: 0.50–0.80 V. T7: 1.50–2.40 V per string | computed §4; ADR-050 §3.2 |
| (b) | **≥ 7.20 W into a 5.4 V bank** | `7.20 / 5.40 / 0.85 = ` **1.569 A** output | computed; ADR-050 §1 |
| (c) | **quiescent low enough not to destroy the night budget** | **I_Q ≤ 5 µA** from the bank at 5.4 V (`5 µA × 5.4 V = 27.0 µW = 27 %` of the 100 µW anchor); target ≤ 2 µA | ADR-050 §3.6 |
| (d) | **hand-solderable** | the payload is hand-assembled by the operator; no BGA/WLCSP; QFN/SON with an exposed pad is marginal, TSSOP/MSOP/SOIC/SOD/SMA are fine | task brief; ADR-051 §1.5 | 

### 5.2 The method, and how the figures were obtained (stated honestly)

- **TI parts**: product-page parameter tables fetched **directly from `ti.com`** with `curl` on
  2026-10-07 (200 OK). **This is a product page, not the datasheet** — labelled as such.
- **ADI and ST parts**: `analog.com` was **unreachable from this host** on 2026-10-07 (no route;
  and through the `r.jina.ai` text proxy it returned **HTTP 403**). The figures were therefore read
  from **archived copies of the vendor product pages via `web.archive.org`** on 2026-10-07. **These
  are vendor-published spec text but they are NOT a read of the datasheet**, and they are labelled
  `TODO(unverified)` where a datasheet would settle the point.
- **Datasheet aggregators were blocked**: `mouser.com` and `alldatasheet.com` returned bot walls
  ("Access to this page has been denied" / "Just a moment..."); `digikey.com` and
  `datasheet.octopart.com` returned 403; the **headless browser daemon did not come up**
  (`browser-harness: daemon default didn't come up`), so the browser route was unavailable; the
  search engines tried (DuckDuckGo HTML and lite endpoints, Bing) returned challenge pages or
  irrelevant results.
- **The two bypass-diode figures ARE datasheet reads** — `PMEG4020ER.pdf` and `PMEG4030ER.pdf` were
  fetched directly from `assets.nexperia.com` (200 OK) and read (§5.3).

### 5.3 The bypass diode — a verified part, and a rating condition the brief does not mention

`docs/adr/051-hub-array-and-cut-topology.md` §2.7 re-rates the bypass diodes to **≥ 2 A / 40 V**
and disqualifies BAT54 (200 mA / 30 V, `wing-electrical` §4.3 computes it as 6× undersized). Two
real parts, **read from their datasheets**:

| Part | V_R | I_F(AV) | Package | V_F | T_amb | Source |
|---|---|---|---|---|---|---|
| **PMEG4020ER** | **40 V** | **2 A** | SOD123W (CFP3), 2.6 × 1.7 mm | 430 mV typ / 490 mV max @ 2 A | **−55 … +150 °C** | Nexperia product data sheet, 1 Jan 2023 |
| **PMEG4030ER** | **40 V** | **3 A** | SOD123W (CFP3), 2.6 × 1.7 mm | 460 mV typ / 540 mV max @ 3 A | **−55 … +150 °C** | Nexperia product data sheet, 23 Jan 2023 |

Both are 2-terminal flat-lead SOD and therefore **hand-solderable**, and both meet ADR-051 §2.7's
≥ 2 A / 40 V target. **Recommended: PMEG4030ER (3 A / 40 V)** — at the permanent-continuous bypass
current of **1.20 A** it has **2.5×** headroom in the *average-current* sense.

**Two conditions the brief and ADR-051 §2.7 do not state, and they matter:**

1. **`I_F(AV)` is a duty-cycle rating.** Both datasheets specify it at **δ = 0.5, 20 kHz, square
   wave**. The bypass path this design is creating is **permanent and continuous (δ = 1, DC)** —
   ADR-051 §2.4 decision 4.3 says so explicitly. The δ = 1 curve (Fig. 9 and Fig. 11 of both
   datasheets: *"Average forward current as a function of ambient temperature"*, curve (1) labelled
   **"δ = 1; DC"**) sits **below** the δ = 0.5 curve and falls faster with ambient temperature.
   **So the honest rating check is not "1.2 A vs 3 A" but "1.2 A vs the δ = 1 curve at the flight's
   ambient."** `TODO(unverified)` — the exact δ = 1 value at 1.2 A is a **graph**, not a table, and
   was not digitised here; at the flight's cold ambient the DC curve is near its high end, so 1.2 A
   is plausible (0.40× of 3 A), but it must be read off Fig. 9/11 or measured, not asserted.
2. **Every verified part here is rated to −55 °C ambient; the design case is −60 °C.** The
   PMEG4030ER/PMEG4020ER `T_amb` minimum is **−55 °C** (`T_stg` is −65 °C). **Every converter in
   §5.4 is likewise −40 °C or −40…85 °C.** So the array's cold case crosses the *rating* of every
   silicon part in this analysis by 5–20 °C. The junction self-heats, which may rescue the diode —
   but this is a **rating question that must be stated, not hidden**, and it is not in any repo
   source. `TODO(unverified)`.

### 5.4 The candidate converters — verified parameters

Read 2026-10-07 as described in §5.2. "Verdict" is against §5.1's four constraints **for the
topology family named**.

| Part | Topology | V_IN min | V_IN max | I_out | I_Q run | I_Q shutdown | Package | Verdict |
|---|---|---|---|---|---|---|---|---|
| **TPS63060** | buck-boost | **2.5 V** | **12 V** | 2 A @5 V (V_IN<10 V, buck); 1.3 A (V_IN>4 V, boost) | **30 µA** | — | WSON-10 3×3 mm | V_IN **covers the series family** (9.58 × 1.25 = 11.98 ≤ 12 — 0.02 V of margin); fails (c) at 30 µA = **162 µW = 162 %** of the anchor unless disabled; **cannot** serve T3/T5 (1.5/0.5 V below 2.5 V) |
| **TPS63070** | buck-boost | **2.0 V** | **16 V** | 2 A | **50 µA** | — | — | V_IN covers series with 1.67× margin; fails (c) harder (50 µA = 270 µW); cannot serve T3 (1.5 V) |
| **TPS63020** | buck-boost | **1.8 V** | **5.5 V** | 4 A switch (2 A @3.3 V) | **25 µA** | — | VSON-14 4×3 mm | **fails (a) for the series family** — 5.5 V against a 9.58 V cold Voc (**1.74×** over); fine for T3/T4/T7; fails (c) |
| **TPS63030** | buck-boost | 1.8 V | 5.5 V | 0.5–0.8 A | 25 µA | — | WSON-10 2.5×2.5 mm | same (a) failure; also fails (b) on current |
| **TPS61200** | **boost only** | **0.3 V** | **5.5 V** | 0.6 A @5 V | **50 µA** | — | VSON-10 3×3 mm | fails (a) for series (5.5 V); **boost-only** cannot pull 6.0 V down to 5.4 V (ADR-050 §3.1); fails (b) and (c) |
| **TPS61099** | **boost only** | 0.7 V | 5.5 V | ~0.3 A @5 V | **0.8 / 1 µA** | — | WSON-6 2×2 mm / 6-ball WCSP | **passes (c) — the only TI part that does**; fails (a) for series; fails (b) ~5× on current; **boost-only** |
| **BQ25570** | boost + MPPT | **0.6 V** (cold start 600 mV typ / **700 mV max**) | **5.1 V** (abs max 5.5 V) | **0.1 A charge** | **488 nA** | < 5 nA | VQFN-20 3.5×3.5 mm | **passes (c) by 10×**; **fails (a) for series (5.1 V vs 9.58 V) and fails (b) ~15×** on current; also blocked by its **510 mW `PIN_PK` absolute maximum** and "≤ 400 mW recommended" — **a single 30.6 cm² LARGE cell is 0.60 W face-on, i.e. it exceeds that rating by itself** (ADR-051 §2.2) |
| **LTC3105** | boost + MPPC | **0.225 V** (start-up 250 mV) | **5.0 V** | 400 mA | **24 µA** | — | DFN-10 3×3 mm / MSOP-12 | fails (a) for series (**5.0 V max**); fails (b) and (c); boost-only |
| **LTC3129-1** | **buck-boost** | **2.42 V** (1.92 V bootstrapped) | **15 V** | **200 mA** (buck mode) | **1.3 µA** | **10 nA** | QFN 3×3 mm / MSOP-16 | **passes (a) — 15 V gives 1.57× margin on 9.58 V — AND passes (c) at 1.3 µA.** **Fails (b): 200 mA × 5.4 V = 1.08 W against the 7.20 W needed (6.7× short).** Has programmable MPPT. **This is the near-miss part: input range and quiescent are right, current is wrong.** |
| **LTC3115-1** | **buck-boost** | **2.7 V** | **40 V** | **1 A for V_IN ≥ 3.6 V, V_OUT = 5 V; 2 A in step-down for V_IN ≥ 6 V** | **30 µA** | **3 µA** | DFN-14 4×5 mm / TSSOP-20 | **passes (a) (40 V = 4.2× margin) and passes (b) at 6.0 V (2 A step-down → 10.8 W).** Fails (c) *running* (30 µA = 162 µW) but **passes (c) in shutdown: 3 µA × 5.4 V = 16.2 µW = 16 % of the anchor, inside ADR-050 §3.6's ≤ 5 µA bound.** Cannot serve T3/T5 (1.5/0.5 V < 2.7 V). **This is the part that makes the series family buildable.** |
| **ADP5091 / ADP5092** | boost + MPPT | **0.08 V** (cold start 380 mV typ) | **3.3 V** | **150 mA** | **510 nA** (SYS pin) | — | — | passes (c); **fails (a) for series by 2.9×** (3.3 V vs 9.58 V) and fails (b) ~10× |
| **LM2623** | **boost only** | 0.8 V | **14 V** | 2.85 A switch limit | **80 µA** | — | VSSOP-8 / WSON-14 | V_IN range looks wide and the current is there — **but it is boost-only** (cannot regulate 6.0 V down to 5.4 V, ADR-050 §3.1) and **fails (c) at 80 µA = 432 µW = 432 % of the anchor**; `T_oper` is also only **−40…85 °C** |
| **SPV1040** | boost + MPPT | **0.3 V** | **5.5 V** | **1.8 A peak** current threshold | **`TODO(unverified)`** | — | **TSSOP-8 3×4.4 mm** | **passes (a) for T3/T4/T5/T7** (0.3–5.5 V covers 0.5, 1.5 and 3.0 V; cold Voc ≤ 4.79 V fits); **(b) is marginal-to-adequate per string** (1.8 A peak on a 1.2 A/1.5 V string); **(d) is the best of any candidate — TSSOP-8 is unambiguously hand-solderable**; **(c) is unknown — `TODO(unverified)`, and it is the one number that decides the parallel family.** |
| **LTC3119** | buck-boost | `TODO` | `TODO` | **up to 5 A continuous** (vendor page) | `TODO` | `TODO` | — | **Named but NOT usable as a verdict** — the archived page yielded only the 5 A output figure; its input range and quiescent could not be read on 2026-10-07 → `TODO(unverified)` |

### 5.5 The result, stated plainly

**For the SERIES family (T1, T2, T6a, and the incumbent ADR-051 chain) exactly one verified part
satisfies all four constraints: the `LTC3115-1`.** 2.7–40 V input (4.2× margin on the 9.58 V cold
Voc), 1 A at V_OUT = 5 V for V_IN ≥ 3.6 V and 2 A in step-down for V_IN ≥ 6 V (2 A × 5.4 V =
10.8 W ≥ the 7.20 W needed), quiescent 30 µA running **but a 3 µA shutdown state that sits inside
ADR-050 §3.6's ≤ 5 µA bound** (3 µA × 5.4 V = 16.2 µW = 16 % of the 100 µW anchor), and a
DFN-14/TSSOP-20 package. **Every other verified wide-input candidate fails the night budget without
a disable path: TPS63060 30 µA, TPS63070 50 µA, TPS63020 25 µA.** The `LTC3129-1` is the closest
*architectural* fit (15 V input, 1.3 µA, 10 nA shutdown, programmable MPPT) and fails only on
output current — **200 mA against the 1.57 A needed.** A **second LTC3115-1-class or LTC3115-1 in
parallel-per-string configuration** is the only route around that, and it multiplies quiescent.

**For the PARALLEL families (T3 and T5) NO verified part satisfies all four constraints.** Every
part with the required current (TPS63020 2 A, TPS63070 2 A, TPS63060 2 A, LM2623 2.85 A) either
fails the input range for the parallel bus's **5.5 V maximum on the high side** (they need ≥ 12 V
for the series case but are *fine* on the parallel case's low side — the point is different) — the
actual obstruction is the **low** side: nothing carries **4.80 A at 1.5 V** or **14.40 A at 0.5 V**
with a µA-class quiescent. Every µA-class part (BQ25570 0.1 A, ADP5091/92 0.15 A, LTC3105 0.4 A,
TPS61099 ~0.3 A) caps at **0.1–0.4 A** — **4× to 48× short of the 1.569 A** the array needs. The
BQ25570 is additionally blocked outright by its **510 mW `PIN_PK` absolute maximum**, which a single
30.6 cm² LARGE cell exceeds on its own (ADR-051 §2.2).

**The part that unlocks the parallel options, if one does: `SPV1040`.** It is the only candidate
whose **input range (0.3–5.5 V) covers every parallel topology's window** including T5's 0.5–0.80 V,
whose **current capability (1.8 A peak) covers one 1.5 V / 1.20 A wing string**, which **embeds
MPPT** (so the §4.3.7 mismatch problem is addressed per string rather than shared), and whose
**TSSOP-8 3 × 4.4 mm package** is the most hand-solderable of any part surveyed. **It does not
unlock T5** (14.40 A in parallel — no single part, and not this one) and it does **not** carry a
whole 4.80 A T3 bus in one instance. **It unlocks the per-wing-converter topology T7** (four
SPV1040s, one per wing), and its **quiescent current is unverified** — `TODO(unverified)` — which is
the single number that decides whether even that is admissible against ADR-050 §3.6.

**Therefore, plainly:** the topology that the *operator's* question implicitly points at (get rid
of series) is the topology the *parts* forbid, and the topology the parts allow (keep series, add
diodes) is the one that answers his actual requirement (a cracked cell must not kill the string).
**One part — the LTC3115-1 — is the difference between the series family being buildable and not.**

---

## 6. The winter night is the real sizing criterion — and it does not change the answer

The array must survive a 50 °N winter night, not merely cover a daily mean. The arithmetic:

```
day length (50.0 °N, winter solstice)   =  7.852 h     (wing-omnidirectional.md; H0 = 58.8884°)
dark                                    = 16.148 h    (the brief says ~15 h; the repo figure is 16.15)
night anchor (ADR-036)                  = 100 µW
night energy                            = 100 µW x 16.148 h x 3600 = 5.81 J
usable bank (ADR-047 §3.2)              = 33.264 J   -> covers the night 5.7x over
daytime load                            = 0.388 W x 7.852 h = 10 968 J
required day-mean array power           = (10 968 + 5.81) J / (7.852 x 3600) s = 388.206 mW
                                        vs 388.000 mW for the load alone
                                        -> +205.7 µW = +0.05 %
worst case: drain the FULL 33.264 J every night -> +1177 µW = +0.30 %
```

**Verdict: the winter night does NOT change the sizing, does NOT change any topology's ranking, and
does NOT change the ranking of any converter.** It changes the 0.388 W requirement by **0.05 %**
(0.30 % in the pathological case where the bank is fully drained every night, which ADR-036's
policy does not do). The reason is that the night load is the **100 µW anchor**, not the 0.388 W
mission average, and the 3.3 F bank holds **5.7×** the night's energy.

**The real sizing criterion is therefore — and this is the thing to flag — the WINTER DAY-MEAN
INSOLATION over a 7.85 h day, not the night.** The requirement is `0.388 W / (density × factor)`
and it moves with the two numbers ADR-051 §1.4/§1.6 already isolate:

| Hub-array cell plane | factor | required area for 0.388 W | ADR-051 status |
|---|---|---|---|
| vertical fins / blades | 0.30511 | **64.9 cm²** | ADR-051 §1.4; and after the 0.9 shading × 0.85 power-path derates, **84.8 cm²** |
| flush on the horizontal hub face | 0.18653 (day-mean) | **106.1 cm²** | ADR-051 §1.4; **138.7 cm²** after the same derates |

**So the real sizing criterion is a two-part statement:** *(i)* the array must be sized on the
**winter day-mean** (`0.388 W / (19.608 mW/cm² × 0.18653 or 0.30511)`), and *(ii)* the night is a
**+0.2 mW rounding term** because the night load is the 100 µW anchor — **provided** the bank
survives the night, which at 5.7× margin it does, and **provided** a part in the chain does not
raise the night floor. That last proviso is real: **four SPV1040-class harvesters (T7) at even
2 µA each add 4 × 10.8 = 43 µW, and the LTC3115-1's 3 µA adds 16 µW** — small against the 100 µW
anchor, but **T7's four-converter quiescent is the one architecture choice in this analysis that
could move the night line materially** (at 5 µA each it is 108 µW, i.e. **it doubles the night
budget**). Sizing criterion **unchanged; night-budget allocation is what T7 spends**.

`TODO(unverified)`: whether the −60 °C case changes the supercap's usable energy. ADR-047 §3/§4
carry the bank's cold behaviour as open; if the 33.264 J usable falls materially at −60 °C the 5.7×
night margin shrinks and this section must be re-run.

---

## 7. Does this supersede ADR-051's cut-ladder premise? — **YES, the ladder table, and here is exactly how**

**The premise being tested** (ADR-051 §2.4, quoted in substance): the 4 wings are one series chain
through the hub, so *"cutting a wing at its tab removes that wing's three cells and drops the string
by 1.5 V"*, giving the ladder **6.0 / 4.5 / 3.0 / 1.5 V** for 0–3 cuts, with the converter floor at
2.5 V (ADR-050 §3.2) and *"2 wings"* as the practical floor. On that basis the table says cuts 1 and
2 still charge and cuts 3 and 4 do not.

**My result supersedes it, for two independent reasons, each with a number:**

1. **The per-cut drop is 1.5 V *plus the bypass diode's forward drop*, and those drops ADD across
   cuts.** ADR-051 §2.4 decision 4.2 mandates the hub bypass diode, and decision 4.3 says it carries
   the array current *continuously* for the rest of the flight — so the diode is **in the string**.
   Each cut wing's bypassed position is in series with the others':

   ```
   0 cuts : 12 cells                = 6.00 V   (table says 6.00)  charges
   1 cut  :  9 cells - 1 x 0.38 V   = 4.12 V   (table says 4.50)  charges
   2 cuts :  6 cells - 2 x 0.38 V   = 2.24 V   (table says 3.00)  DOES NOT CHARGE
   3 cuts :  3 cells - 3 x 0.38 V   = 0.36 V   (table says 1.50)  does not charge
   4 cuts :  0 cells                = 0.00 V   (table says 0.00)  no charge
   ```

   **The 2-cut row is wrong: 2.24 V is below the 2.5 V floor of *every* verified wide-input part.**
   ADR-051 §1.1 and §2.4 list the **raw cell voltages** and omit the diode drop their own decision
   4.2 introduces. `docs/analysis/array-power-architecture.md` §3.2 ("3 wings → 4.20 V … 2 wings →
   2.70 V") does include a 0.3 V diode drop — the two records disagree, and the ADR-051 table is
   the one without it.

2. **Which part is fitted changes the ladder depth, and the part the night budget demands is the
   one with the *higher* floor.** The only part meeting ADR-050 §3.6's `I_Q ≤ 5 µA` bound with
   enough current is the **LTC3115-1**, whose input minimum is **2.7 V**, not 2.5 V (§5.5). At
   2.24 V the 2-cut case misses **both** floors anyway — so the ladder is capped at **one cut**, not
   two, on any part that is actually admissible. ADR-051 §2.4 decision 4.1 makes the ladder's depth
   depend on the **hub array's area**; this analysis adds a second, independent cap —
   **the converter's input floor, with the diode drop included.**

3. **The premise is also *inapplicable* to four of the seven topologies.** T3's bus is 1.50 V
   regardless of cuts (the ladder is meaningless); T4's first cut costs **50 %** because the
   surviving 1.5 V pair is blocked by the intact 3.0 V pair; T5 sits at 0.50 V; T7 has no shared
   node at all. **The 1.5 V-per-cut ladder is a property of the series-through-hub topology, not of
   the array.**

**What is NOT superseded, and should be kept:** ADR-051 §1.1's core claim that a cut *removes*
string voltage and that the hub array is therefore the enabling condition; §2.4 decision 4.2's
mandate to **populate** the per-interface bypass diodes; decision 4.3's statement that the bypass
path is **continuous**; and §2.1's independence invariant. **My result strengthens decisions 4.2 and
4.3 (this analysis shows they are mandatory even for a per-cell-bypassed design, because a cut at
the tab takes the wing's own diodes with it — §3.1) and corrects the ladder *table*.**

**Recommendation to the worker editing the cut record:** the ladder table should be restated as
**6.00 / 4.12 / 2.24 / 0.36 V** with the diode drop explicit, and the "2 cuts still charges" row
should be marked **`NO` on any verified part** unless the hub array itself is in the string — which
ADR-051 §2.1 forbids. **The number of cuts the vehicle actually survives is one, plus whatever the
independent hub array can carry.** That is a materially shallower ladder than ADR-051 §2.4 records,
and it is a fact about the *bypass diode its own decision 4.2 mandates*.

---

## 8. Ranked recommendation

**The single number that decides it: the array-side current at 7.20 W.**

| Topology | array-side current | I²R vs series | tab-land margin | converter exists at that current? |
|---|---|---|---|---|
| **T6a / T2 / T1** | **1.20 A** | **1×** | 2.27× | **yes — LTC3115-1** |
| **T7** | **1.20 A/string** (4 strings) | **1×** | 2.27× | **maybe — SPV1040 ×4, I_Q `TODO`** |
| **T4** | 2.40 A | 4× | 1.14× | yes on paper (TPS63060/LTC3115-1) |
| **T3** | 4.80 A | 16× | **0.57× FAILS** | **no part carries it** |
| **T5** | **14.40 A** | **144×** | **0.19× FAILS** | **no part carries it** |

**1.20 A is the number.** It keeps the existing 4.0 × 1.2 mm tab lands legal (2.27× margin,
`wing-electrical` §6.3), keeps the shared array harness at 1× I²R, and — decisively — it is the only
array-side current at which a **verified** converter (LTC3115-1) both exists and meets the night
budget. **Every parallel family multiplies this number and simultaneously deletes the converter
that could serve it.**

### The ranking

1. **T6a — 12 cells in series with a bypass diode across every cell (12) *and* a hub bypass diode
   across every wing (4).** Best cracked-cell behaviour available in the series family (**−14.67 %
   open / −8.33 % short**), a wing cut costs **31.33 %** with the bus at **4.12 V** (usable), array
   current **1.20 A**, converter **LTC3115-1 verified**. Diode count 16 ≈ 144 mg estimated — **about
   one tenth of a single cell's mass** — on a payload whose whole 4-wing array is 12.85 g
   (ADR-049), so the diode count is not the binding cost. **This is the recommendation.** It also
   *is* the honest form of T1 (T1-as-written cannot survive a cut, §3.1).
2. **T7 — four independent wing strings, one MPPT converter each.** The only topology in which a
   cut **cannot change the bus voltage** and the only one that harvests mismatched strings at their
   own MPP. Loses to T6a on **mass (+2.8–4.8 g, ADR-050 §3.7 × 4) and night budget (4× the
   quiescent — 108 µW at 5 µA each, which is 108 % of ADR-036's anchor)**, and its converter is
   **unverified** (SPV1040 `I_Q` is `TODO`). **The right answer if T6a's one-cut ladder is judged
   too shallow — the price is mass and night budget, both quantified.**
3. **T2 — 12S with 4 group diodes.** Same converter as T6a, **4 diodes instead of 16** (36 mg),
   and a **documented, already-mandated** provision (ADR-046 §2.3 / ADR-051 §2.4). The cost is
   precise and large: **one cracked cell costs three cells (31.33 %)** instead of one (14.67 %).
   **Choose T2 over T6a only if the 108 mg of extra diodes is genuinely unaffordable — it is
   ≈ 0.8 % of the 12.85 g array, so it is not.**
4. **T4 — 2S2P.** Inside TPS63060's window and (just) inside LTC3115-1's, at 4× I²R and a tab-land
   margin of 1.14×. **A single cut costs 50 %** — the intact 3.0 V pair blocks the surviving 1.5 V
   pair — and a single cracked cell costs the same. **This is the topology that most cleanly
   demonstrates why the "split the difference" instinct is wrong.**
5. **T3 — 4P × 3S.** The only parallel topology with genuinely attractive *cut* behaviour (25 %,
   bus invariant) marred by a **1.50 V bus below every wide-input part's floor**, a **4.80 A** array
   current (16× I²R, **tab lands over rating**), and the classic single-MPPT mismatch failure
   (§4.3.7). **Buildable only with four converters — at which point it *is* T7, but with the
   converters summed onto a 4.80 A array bus instead of four 1.20 A strings.** Strictly dominated
   by T7.
6. **T5 — all 12 in parallel.** Worst on every axis: **14.40 A (144× I²R, tab lands at 0.19× of
   rating)**, a **shorted cell costs ~100 %**, a **0.50 V bus** needs a sub-0.8 V cold-start
   harvester, and the only µA-class parts with that cold-start (BQ25570, LTC3105, ADP5091) are
   **0.1–0.4 A-output** parts — 4–16× short. **The brief's premise is right that 144× is the cost
   and wrong that the topology is available.**

### What this does to the operator's question

**"Avoid series wherever reasonably possible" is the wrong lever; "protect the series you have,
cell by cell" is the right one.** The 144× I²R number is real and it is why the parallel families
are not *available* — but the deeper reason is §5: **no purchasable part carries a 1.2 A, 1.5 V
string with a µA-class quiescent.** The series string is not a legacy inconvenience to be removed;
it is the only array-side current at which a hand-solderable, night-quiet converter exists. And the
cracked-cell tolerance the operator wants is available **without leaving series** — it costs
**16 diodes, ≈ 144 mg**, at **+2.5× the group-diode count** (T2 → T6a), and it converts his stated
failure ("a cracked cell kills the string") into **−14.67 % open / −8.33 % short**.

**What the recommendation forces on the other subsystems** (stated because it is not free):
(i) the hub needs a **16-diode land plan** inside ADR-048 §2's interface keep-out, which is a hub
**re-layout** and must be re-checked against ADR-030's placement gate (the same re-freeze ADR-051
§2.3 already triggers);
(ii) the **converter choice is now LTC3115-1 or nothing** for the series family, which re-opens
ADR-050 §3.2's part survey and its DFN-14/TSSOP-20 land;
(iii) the **cut record's ladder table must be corrected** (§7);
(iv) **ADR-050 §3.6's `I_Q ≤ 5 µA` bound is now load-bearing**, because the only admissible series
part passes it *in shutdown only* (3 µA) and fails it running (30 µA) — **firmware must disable the
converter at night or the 100 µW anchor is overdrawn by 62 %.**

---

## 9. What this analysis CANNOT settle (all of it needs a bench measurement or a datasheet)

1. **The converter efficiency at 1.5 V and 6.0 V.** No datasheet curve was read for any candidate
   and none of the three VI curves exists in the repo. ADR-050 §2(b).2 already carries this; it
   remains open and every "does it pass 7.20 W" statement above assumes the ADR-050 §1 **85 %**,
   itself `TODO(unverified)`. **This single measurement decides whether the LTC3115-1's
   2 A-at-5 V / 1 A-at-5 V figures clear the array.**
2. **The `LTC3115-1`'s 3 µA shutdown current against its *datasheet*.** The 3 µA and the 30 µA
   figures are from the **archived ADI product page** (2026-10-07); the datasheet was not read
   (§5.2 — `analog.com` unreachable). The **disabled-state leakage** and whether firmware can hold
   the part in shutdown without a keeper are **both `TODO(unverified)`** and both decide whether
   the series family meets ADR-050 §3.6.
3. **`SPV1040`'s quiescent current.** Its input range, 1.8 A peak current and TSSOP-8 package are
   verified from the archived ST product page; **its `I_Q` is not stated there.** It is the single
   number that decides whether T7 (and therefore the whole parallel family) is admissible. **Not
   read; `TODO(unverified)`.**
4. **The bypass diode's δ = 1 (DC) continuous rating at the flight's ambient.** Both PMEG datasheets
   give `I_F(AV)` only at **δ = 0.5, 20 kHz**; the permanent-continuous path needs the **δ = 1 curve
   (Fig. 9 / Fig. 11)**, which is a graph. **1.20 A against a 3 A headline is not the check.** Also
   `TODO(unverified)`: diode **mass** from any datasheet (none states it; the 9 mg/diode figure here
   is a package-volume estimate).
5. **The −60 °C rating question, across every part in the analysis.** Every verified semiconductor
   here is rated to **−55 °C ambient** (diodes) or **−40 °C** (all converters) against a **−60 °C**
   design case. Whether the *junction* self-heating is sufficient, and whether an extended/
   automotive grade of any of these parts exists at −55 °C, is **`TODO(unverified)`** and applies to
   the recommendation, not just to the alternatives.
6. **The open-vs-short split for a thermally-cracked cell of this class.** §2 and §4 turn on it: the
   series family is safe against a short and exposed to an open, the parallel families the reverse.
   **Nobody has measured which a −60 °C thermal cycle on a bare 78.55 × 38.90 × 0.21 mm poly-Si
   cell actually produces**, and it is the highest-value measurement in this document.
7. **A soft/partial short's series-loss magnitude.** §2/§4.1 flag it as the unattractive
   intermediate case; its magnitude depends on the shunt resistance after a crack, which is
   unmeasured.
8. **The cells' real MPP power density in flight illumination.** ADR-051 §1.6 carries this; it
   scales every area and every "the array needs X cm²" statement in §6. It does not change any
   *topology* ranking (all seven use the same cells), which is why §6 could be written without it.
9. **Whether a single MPPT can be made to work across four mismatched parallel strings by design
   rather than by luck.** §4.3.7 states the structural problem (one converter, one input operating
   point) and the escape (T7); it does **not** model a specific controller's behaviour against four
   real I-V curves, because the cells' measured curves do not exist (item 8). **A bench test with
   four real wings at four shaded insolation levels is the only way to put a number on it.**
10. **The hub array's own sizing and orientation** — the operator has still not chosen the hub cell
    plane (horizontal `0.18653` vs vertical `0.30511`), and §6 shows that choice moves the
    requirement by **1.64×** (64.9 → 106.1 cm²). **This analysis does not choose it and cannot.**
11. **`LTC3119`'s parameters.** Named as a candidate (up to 5 A continuous output, vendor page) but
    its input range and quiescent could not be read on 2026-10-07 → it carries no verdict here.
    **`TODO(unverified)`.** It is the obvious next part to try for the series family with more
    current headroom.
12. **Cut energy and the cut mechanism** — unchanged, owned by ADR-050 §3.10 and
    `docs/analysis/wing-jettison.md`. This analysis prices the *electrical* consequence of a cut,
    not its actuation.

---

## 10. Sources

**In-repo (cited above):** ADR-006, ADR-029, ADR-030, ADR-036, ADR-044, ADR-046, ADR-047, ADR-048,
ADR-049, ADR-050, ADR-051; `docs/analysis/wing-electrical.md`,
`docs/analysis/mppt-charge-path-specification.md`, `docs/analysis/array-power-architecture.md`,
`docs/analysis/wing-ladder.md`, `docs/analysis/wing-insolation-geometry.md`,
`docs/analysis/wing-omnidirectional.md`, `docs/analysis/pico-balloon-solar-survey.md`;
`docs/POWER-BUDGET-V9-D2BE.md`, `docs/WING-TO-HUB-SOCKET-SPEC.md`, `docs/hardware-design.md`;
`docs/adr/052-cell-mounting-end-only.md` (branch `adr/cell-mounting-end-only`, **Proposed**, not
mergeable to main by this document).

**Datasheets (fetched directly, 2026-10-07):**
- Nexperia **PMEG4020ER** product data sheet, 1 Jan 2023 — `assets.nexperia.com/documents/data-sheet/PMEG4020ER.pdf`
- Nexperia **PMEG4030ER** product data sheet, 23 Jan 2023 — `assets.nexperia.com/documents/data-sheet/PMEG4030ER.pdf`

**Vendor product pages (read 2026-10-07; these are pages, NOT datasheets):**
- Direct from `ti.com/product/{TPS63060, TPS63070, TPS63020, TPS63030, TPS61200, TPS61099, BQ25570, LM2623}`
  (200 OK, `curl`).
- Via `web.archive.org` because `analog.com` was unreachable and returned 403 through the `r.jina.ai`
  proxy: **LTC3105, LTC3129-1, LTC3115-1, LTC3119, ADP5091/ADP5092** (Analog Devices product pages),
  and **SPV1040** (ST product page).

**Unreachable on 2026-10-07 (stated so the gaps are not mistaken for coverage):** `analog.com`
direct (no route); `r.jina.ai` proxy → 403; `mouser.com` → "Access to this page has been denied";
`alldatasheet.com` → Cloudflare challenge ("Just a moment..."); `digikey.com` and
`datasheet.octopart.com` → 403; `st.com` direct → no route; the search engines tried
(DuckDuckGo HTML + lite endpoints, Bing) → challenge pages or irrelevant results; the **headless
browser daemon did not come up** (`browser-harness: daemon default didn't come up`), so the
browser route was unavailable.

**No hardware was ordered, no BOM was changed, and no schematic was edited by this document.**
