# Wing shape: an N-gon vertical prism versus the four vertical blades — consultant analysis

**STATUS: CONSULTANT ANALYSIS, not a decision record.** Nothing here is an operator
decision, an accepted ADR, or an implementation authorisation. Every number is either
(i) printed by the committed script `docs/analysis/ngon_prisms.py` (run it to reproduce),
(ii) cited to an in-repo document, or (iii) carries an explicit `TODO(unverified)` naming
the open question.

- Date: 2026-10-07
- Branch: `analysis/wing-ngon` · Worktree: `/home/c03rad0r/worktrees/bf-wingngon`
- Base: `af9a672` (main tip — ADR-049 itself; observed live, not hardcoded)
- Lens: **geometry and topology of the general regular N-sided vertical prism.** The
  rotation/flat-vs-vertical analysis is `docs/analysis/wing-insolation-geometry.md`
  (+ `insolation_factors.py`); mass and structure are `docs/analysis/wing-mass-shape.md`
  (+ `wing_mass_model.py`). Neither is re-derived. The cylinder-vs-four-blade limit is a
  parallel consultant's deliverable; it appears here only as the N→∞ boundary check (Part 1).

---

## 0. The operator's question, and what is taken as given

> Would a **TRIANGLE** or a **PENTAGON** array be better than the accepted four vertical
> blades — reasoning that *flat faces mean the cells do not have to be bent*, and that a
> *triangle might be more stable*?

Stated as two claims to test: **(a)** a triangle is an energy question; **(b)** a triangle is
more stable. Both are refuted below, and the pentagon is refuted on nothing more than
arithmetic.

**Taken as given (cited, not re-derived):**

| Item | Value | Source |
|---|---|---|
| Payload attitude | **none** — slow uncontrolled rotation about the **vertical** axis; sun azimuth uncontrolled | task context; ADR-049 §Context; `wing-insolation-geometry.md` §2 |
| Cells | small 52.07 × 19.65 × 0.21 mm (10.2318 cm², ~0.5 V, ~0.4 A, ~0.5006 g); large 78.55 × 38.90 × 0.21 mm (30.5559 cm², ~0.5 V, ~1.2 A, ~1.4951 g) | ADR-049 "Measured inputs" (operator caliper) |
| Series count | **12 cells in series → 6.0 V nominal**; cell V is size-independent | ADR-046 §2.3, ADR-049 |
| Radio ceiling | **5.5 V** (the F33 max row: 5.5 V / 1118 mA) | ADR-047 §1.1 |
| Load maximum | 5.5 V × 1.118 A = **6.149 W ≈ 6.15 W** | ADR-047 §1.2 |
| Supercap bank | **5.4 V**; clamp is now a **required rated part**; −60 °C string OCV ≈ **9.3 V** | ADR-049 §3 |
| Hub sockets | **four, at 90°** — `J_W1..J_W4`, already in the schematic | ADR-048 §2.1 |
| Arms | all four must be **identical boards** | ADR-049 §"Recommended outline" |
| Season/geometry | winter solstice at φ = 50 °N → noon elevation h = 16.56° | assumed in `insolation_factors.py` (`TODO(unverified)`) |
| Accepted design | 3 large cells/wing, **vertical plane**, spine-and-ribs, 4 arms at 90° | ADR-049 §Decision |

**The model this document analyses** (stated so the reader can attack it — script header,
and Part 4 note on the alternative reading):

A *regular N-sided vertical prism*: axis vertical, **N identical flat faces**, each face a
vertical rectangle of **width w** (tangential) and **height H** (vertical). Face normals are
horizontal, spaced 360/N in azimuth. **Cells are stacked in series along the face's long
dimension, which is the vertical (blade) height**, so the blade height grows with the
per-face cell count `c = 12/N`. `w` is the cell width plus margins, held the same across N.
All N faces are identical boards (ADR-049).

> **Important, and easy to miss:** the accepted "four vertical blades" are **not** the N=4
> face of this prism. The accepted blades are **radial fins** (long axis radial/horizontal,
> `wing-insolation-geometry.md` §6), so their normals point **tangentially**; a prism's faces
> are tangential panels whose normals point **radially**. Both are vertical planes with
> horizontal normals — which is why Parts 1–3 are identical for either reading — but the
> physical sizes are completely different (Part 4). Part 5 carries the alternative reading as
> a cross-check; the Part 6 recommendation is the same either way.

---

## 1. Part 1 — the N-independence proof: harvest per unit installed area is (1/π)·cos h

### 1.1 The algebra

Sun direction (pointing **to** the sun), with azimuth 0 and elevation h:
`s = (cos h, 0, sin h)`. A face of a vertical prism whose normal is at azimuth ψ_k has

```
n_k = (cos ψ_k, sin ψ_k, 0)
cos(incidence)_k = s · n_k = cos h · cos ψ_k
```

A face turned away gives a negative cosine and delivers **zero**, so every average takes the
positive part. With uniform rotation (ψ uniform over 360°), the rotation average of **one
face** — for *any* fixed mounting azimuth, because uniform rotation makes the mounting
azimuth irrelevant — is

```
⟨max(0, cos h·cos ψ)⟩_ψ = cos h · (1/2π) ∫₀^{2π} max(0, cos ψ) dψ
                        = cos h · (1/2π) ∫_{−π/2}^{π/2} cos ψ dψ
                        = cos h · (1/2π) · 2
                        = cos h / π                                        (★)
```

The N-face total is the sum, and **every one of the N faces has the same average (★)**, so

```
(sum over N faces) / N installed face-areas = N·(cos h/π) / N = cos h / π
```

— the installed area of a face, `A = w·H`, cancels (every face is identical). The result is
**independent of N** and, in the limit, of the cylinder: a cylinder's azimuthal area element
`R dφ dz` is uniform in φ, so its per-unit-installed-area harvest is the *same* integral (★).

**N entered the derivation exactly once, as a label, and cancelled.**

### 1.2 The numeric check (script, section (1))

`⟳ ngon_prisms.py` section `(1)`: numeric mean over a full 360° rotation, n = 72001 samples,
of the per-face `max(0, cos h cos(ψ − a_k))` and of the N-face total / N, at winter noon
h = 16.56°:

| N | per-face avg | sum(N faces)/N | dev from cos h/π = 0.305107 |
|---|---|---|---|
| 2 | 0.305116 | 0.305109 | +9.1e−06 |
| 3 | 0.305116 | 0.305107 | +9.1e−06 |
| 4 | 0.305116 | 0.305106 | +9.1e−06 |
| 5 | 0.305116 | 0.305107 | +9.1e−06 |
| 6 | 0.305116 | 0.305107 | +9.1e−06 |
| 8 | 0.305116 | 0.305107 | +9.1e−06 |
| 12 | 0.305116 | 0.305107 | +9.1e−06 |
| **cylinder** | **0.305107** | **0.305107** | **+3.3e−07** |

The residual ≈ +9 × 10⁻⁶ is the **sampling bias** of a uniform grid across the kink where the
clamp switches on (`O(1/n)`, n = 72001) — identical for every N, which is itself the point.
The cylinder row is the same integral (★) by direct quadrature. The closed form is
`(1/π)·cos(16.56°) = 0.305107`.

### 1.3 The answer to "is shape an energy question?"

**No. Shape choice is not an energy question at all.** For the same installed cell area, the
same vertical orientation and uncontrolled azimuth, **every N harvests identically**:
0.305107 of nameplate, i.e. `(1/π)·cos h`, at winter noon — 30.5 %, matching ADR-049's
preliminary note and `wing-insolation-geometry.md` §2 (`cos h/π = 0.30511` per blade).

Therefore the entire choice of N must be made on **topology** (Part 3), **mass, size and
ripple** (Parts 2, 4) and **buildability** (Part 5). If a proposal to switch to a polygon
cites *energy*, it is citing a number that does not exist.

---

## 2. Part 2 — ripple: the triangle is *smoother* than the square

### 2.1 Ripple of the total harvest

Total(ψ) = cos h · R(ψ) with `R(ψ) = Σ_k max(0, cos(ψ − a_k))`, `a_k = 360k/N`.
`cos h` is a common factor, so the **percentage** ripple of the total is **independent of
elevation** (only the mean scales with cos h). Script section `(2)`:

| N | R_min | R_max | R_mean (= N/π) | ripple pk-pk (% of mean) | ± % |
|---|---|---|---|---|---|
| 2 (flat plate) | 0.00000 | 1.00000 | 0.63662 (2/π) | 157.08 | ±78.5 |
| **3 (triangle)** | 0.86603 | 1.00000 | 0.95493 (3/π) | **14.03** | ±7.01 |
| **4 (square)** | 1.00000 | 1.41421 | 1.27324 (4/π) | **32.53** | ±16.27 |
| 5 (pentagon) | 1.53884 | 1.61803 | 1.59155 (5/π) | 4.98 | ±2.49 |
| 6 (hexagon) | 1.73205 | 2.00000 | 1.90986 (6/π) | 14.03 | ±7.01 |
| 8 | 2.41421 | 2.61313 | 2.54648 (8/π) | 7.81 | ±3.91 |
| 12 | 3.73205 | 3.86370 | 3.81972 (12/π) | 3.45 | ±1.72 |

`R_mean = N/π` exactly, for every N — this is Part 1 again, numerically.

### 2.2 The counter-intuitive case is real: **N=3 has LESS ripple than N=4**

```
N=3 ripple 14.03 %   vs   N=4 ripple 32.53 %   →  the triangle is smoother by 2.3×
```

**Why, in terms of how many faces are lit at once.** The number of simultaneously lit faces
and their factors differ sharply between an even and an odd N:

- **Square (N=4).** At ψ = 0° one face is dead-on the sun (1.000) and the two perpendicular
  faces are **exactly edge-on** (0.000) → R = 1.000. At ψ = 45° **two** faces are each at
  45°, both at **0.707** → R = √2 = 1.414. The square swings 41 % between these two states:
  it alternates between "one face full, two dead" and "two faces at 71 %".
- **Triangle (N=3).** Face normals are 120° apart, so the nearest face is **never more than
  60° off the sun** (cos ≥ 0.5) — a triangle *always* has a well-lit face. And the second face
  can only ever reach 0.5, and only at the instant the first is also at 0.5, so a *second
  strongly lit face never appears at the same time as a strong first face*. R stays in
  [0.866, 1.000]: min at ψ = 30° (one face at cos 30° = 0.866), max at ψ = 0° **and** ψ = 60°
  (one face at 1.000, or two at 0.500 each = 1.000 — the two maxima are equal).
- General pattern (script table): the N=2, 4, 8 even cases carry the large ripples
  (157 / 32.5 / 7.8 %) because two opposed faces can be strongly lit at once; the odd cases
  are smoother because the face count that can be simultaneously lit *and strong* is one.

### 2.3 On the series metric (the string as actually wired)

`ADR-046 §2.3` wires the wings as **one series string**; with an ideal per-face bypass the
string's best operating point is `P/P_ideal = max_j ( j · cos_(j) ) / N` (`cos_(j)` = j-th
largest instantaneous factor). Script section `(2)`, bottom table — **N=3 is again smoother
than N=4**:

| N | S_min | S_max | S_mean | ripple pk-pk |
|---|---|---|---|---|
| 3 | 0.20919 | 0.31951 | 0.27879 | **39.6 %** |
| 4 | 0.21445 | 0.33889 | 0.25075 | **49.6 %** |
| 5 | 0.18799 | 0.31018 | 0.23325 | 52.4 % |
| 6 | 0.19050 | 0.27670 | 0.23213 | 37.1 % |

(Compare `wing-insolation-geometry.md` §2b: β=90, noon series ψ=0 → 0.2396, ψ=45 → 0.3389 —
consistent, and the mean 0.25075 there equals the N=4 row.)

### 2.4 Does ripple matter? Mostly no — the load is a supercap + shunt clamp, not a battery + MPPT

- The bank is a **supercapacitor with a shunt clamp and no MPPT** (ADR-044/047/049). A cap
  integrates the input; a battery+MPPT would need smooth power to track the maximum power
  point, and there is no MPP tracker here. The quantity that decides energy capture is the
  **integral** over the rotation, and Part 1 proves that integral is **identical for every N**.
- Ripple only affects **instantaneous margin**: when the dip deepens below the 6.15 W load the
  cap supplies the deficit for the dip's duration. The dip period is the **rotation period**
  (slow) and the dip depth is 14–33 % about the mean, so the bank needs to ride through
  ~50–95 % of the load for ~a quarter period. **`TODO(unverified)`: the cap value and the
  rotation period are not in the repo, so the ride-through is not computed here.** This is the
  same obligation the **already-accepted** 4-blade design carries (32.5 % ripple), and the
  triangle would *ease* it (14 %), so ripple is an argument **for** the triangle, not against
  it — but it is a second-order one, and it cannot outweigh Part 3.
- Corollary: **ripple is not a reason to change away from the accepted four blades**, because
  the accepted design's ripple is a design obligation already being met.

---

## 3. Part 3 — the series arithmetic: the hard constraint (and the pentagon's death)

Each face is one wing carrying one series string, and **all faces must be identical boards**
(ADR-049). So the per-face cell count `c` must satisfy `N · c = 12` with `c` a positive
integer, and the array voltage is `12 × 0.5 V = 6.0 V` **for every legal N** (cell voltage is
size-independent — 12 cells in series is 6.0 V however they are grouped).

Script section `(3)`:

| N | c = 12/N | uniform faces? | cells (uniform) | V nominal | cold (−60 °C) OCV | verdict |
|---|---|---|---|---|---|---|
| 2 | 6 | yes | 12 | 6.00 V | 9.30 V | *voltage* OK — **but N=2 is a flat plate** (see below) |
| 3 | 4 | yes | 12 | 6.00 V | 9.30 V | **COMPATIBLE** |
| 4 | 3 | yes | 12 | 6.00 V | 9.30 V | **COMPATIBLE** (the accepted design) |
| 5 | 2.4 | **NO** | 10 → 5.00 V | **5.00 V < 5.4 V bank → cannot charge** | 7.75 V | **FAIL** |
| 5 | — | NO | 15 → 7.50 V | **7.50 V > 5.5 V ceiling (nominal)** | 11.62 V | **FAIL** |
| 5 | — | NO | 12 → 6.00 V | 6.00 V | 9.30 V | only as **non-uniform (2,2,2,3,3)** — violates ADR-049 |
| 6 | 2 | yes | 12 | 6.00 V | 9.30 V | **COMPATIBLE** |

**Why the pentagon fails, explicitly.** 12 does not divide by 5. A uniform-face pentagon must
carry the same cell count on every face, so it can only be **10 cells** (2/face) or **15 cells**
(3/face):

- **10 cells → 5.00 V nominal.** Below the **5.4 V bank** (ADR-049 §3). The string cannot
  charge the bank at all — the same topology failure that kills the "half shape"
  (`wing-insolation-geometry.md` §4e). Cold OCV 7.75 V also sits below where the clamp would
  matter, so the array is simply inert.
- **15 cells → 7.50 V nominal**, and **11.62 V** at −60 °C OCV. Worse than the accepted 9.3 V
  on the very axis ADR-049 §3 calls out ("no series count satisfies both"): it forces **more**
  clamp dissipation, more over-voltage exposure, and a worse array-to-clamp ratio, for the same
  6.0 V of useful series tap.
- The only way to keep 12 cells is a **non-uniform face population** (e.g. 2,2,2,3,3). That is
  a **6.0 V** array that works electrically — but it makes the five wing boards **different
  boards**: different cell counts per face, different per-wing voltage (1.0 V vs 1.5 V),
  unequal series sources, and a mass imbalance off the hub. **ADR-049 requires identical arms**
  ("All four arms must be identical boards (one order line; equal series sources; no mass
  imbalance)"). Non-uniform faces are therefore **not acceptable**, and with that the pentagon
  is rejected on **arithmetic alone** — no ripple or mass argument is even needed.

**Honest nuance on the 5.5 V ceiling.** Even the **accepted** 12-cell / 6.0 V string
**exceeds the 5.5 V radio ceiling in nominal terms**, and its −60 °C OCV (≈9.3 V) exceeds it by
far. That is precisely why ADR-049 §3 makes the **rated shunt clamp mandatory** ("no series
count satisfies both"). So `≤ 5.5 V` is **unreachable at any N**; the criterion that actually
selects a polygon is the integrality of `12/N` with the array held at 6.0 V.

**Survivors by the series arithmetic: N = 3, 4, 6.** (N = 2 also divides, but a two-sided
prism is a **flat plate** — its two faces are back-to-back and 0.6 mm apart, so the sunward
face casts a geometric shadow on the far face and the far face produces nothing;
`wing-mass-shape.md` §2.5 rejects exactly this double-sided arrangement. N = 2 is excluded as
degenerate, not as arithmetic.)

---

## 4. Part 4 — physical consequences per surviving N

Definitions (script section `(4)`), all in millimetres:

```
face height H = c·L + (c−1)·gap + 2·m_end         c = 12/N,  gap = 6.0, m_end = 3.8  (ADR-046 §3.3 / §6)
face width  w = W + 2·m_side                      m_side = 2.675  (ADR-046 §3.2/§6)
outer diameter D = w / sin(π/N)                   regular N-gon: side = D·sin(π/N)
board area = w·H + tab(8 × 9)  per face           full-face carrier;  mass = cm² × 0.1276 g/cm²
aspect ratio AR = H / D                           HIGHER AR = taller and narrower
```

### 4.1 SMALL cells (52.07 × 19.65 mm) — face width 25.00 mm for every N

| N | c | face outline (mm) | blade HEIGHT (mm) | outer ⌀ (mm) | tab/socket joints | edge seams | AR | board area (cm²) | board mass (g) | cell mass (g) | installed cell area (cm²) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **3** | 4 | 233.88 × 25.00 | **233.88** | **28.87** | **3** | 3 | **8.10** | 177.57 | 22.658 | 6.01 | 122.78 |
| **4** | 3 | 175.81 × 25.00 | 175.81 | 35.36 | 4 | 4 | 4.97 | 178.69 | 22.801 | 6.01 | 122.78 |
| **6** | 2 | 117.74 × 25.00 | **117.74** | **50.00** | 6 | 6 | **2.35** | 180.93 | 23.087 | 6.01 | 122.78 |

### 4.2 LARGE cells (78.55 × 38.90 mm) — face width 44.25 mm for every N

| N | c | face outline (mm) | blade HEIGHT (mm) | outer ⌀ (mm) | tab/socket joints | edge seams | AR | board area (cm²) | board mass (g) | cell mass (g) | installed cell area (cm²) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **3** | 4 | 339.80 × 44.25 | **339.80** | 51.10 | **3** | 3 | **6.65** | 453.24 | 57.834 | 17.94 | 366.67 |
| **4** | 3 | 255.25 × 44.25 | 255.25 | 62.58 | 4 | 4 | 4.08 | 454.67 | 58.016 | 17.94 | 366.67 |
| **6** | 2 | 170.70 × 44.25 | **170.70** | **88.50** | 6 | 6 | **1.93** | 457.53 | 58.381 | 17.94 | 366.67 |

**The installed cell area and cell mass are IDENTICAL for every N** (12 cells): 122.78 cm² /
6.01 g (small) or 366.67 cm² / 17.94 g (large). This is Part 1 in mechanical terms — N changes
only the **board** geometry, and even that barely (Part 4.3).

### 4.3 The plain answers

Using the small cell and the full-face carrier (board mass only; cells are equal for all N):

- **Shortest:** **N=6** — 117.74 mm (vs 175.81 mm at N=4, 233.88 mm at N=3).
- **Lightest:** **N=3** — 22.658 g of board vs 22.801 (N=4) and 23.087 (N=6). The spread across
  N is only **0.429 g (1.9 %)**, because every N lays down the *same* total cell-string length
  and the difference is just 2·m_end per face. **Mass is essentially N-independent.**
- **Fewest joints:** **N=3** — 3 tab/socket joints (and 3 edge seams), vs 4 (N=4) and 6 (N=6).
- **Largest diameter / widest:** **N=6** — 50.00 mm outer ⌀ (vs 35.36 mm at N=4).
- **Most stable by aspect ratio:** **N=6** (AR = 2.35). **Least stable:** **N=3** (AR = 8.10).

### 4.4 The operator's stability expectation is **contradicted**

> "a triangle might be more stable."

**The arithmetic says the opposite.** `12/N` forces the triangle to carry **4 cells per face**,
and the triangle is the polygon with the **smallest** circumscribed diameter for a given face
width (`D = w/sin(π/N)`: 28.87 mm at N=3 vs 35.36 mm at N=4 vs 50.00 mm at N=6). So the triangle
is the **tallest (233.88 mm) and narrowest (28.87 mm) — AR 8.10** — and the hexagon is the
**shortest (117.74 mm) and widest — AR 2.35**. A **taller, narrower** body is **less** stable,
not more: it is a higher-aspect-ratio cantilever, its mass sits further from the hub plane, it
has the least rotational inertia for a given disturbing torque, and it presents the largest
side-on area per unit diameter. **The triangle is the least stable of the three survivors.**
The operator's premise is **refuted**; if the goal is stability, the polygon argument points to
**N=6**, not N=3.

(The same ordering holds for the large cell: AR 6.65 / 4.08 / 1.93 for N = 3 / 4 / 6.)

---

## 5. Part 5 — buildability and stability, honestly

### 5.1 Does a closed prism require the faces to be joined along their long edges? **Yes.**

A *closed* prism is a structural ring: adjacent faces meet at N vertical edges, and the edge
join is what makes the ring stiff. Two build routes, both worse than the incumbent:

1. **N separate boards, soldered/welded along N long edges.** Each seam is an **edge-to-edge
   joint of two 0.6 mm FR4 plates** running the **full face height** — 117.74 mm (N=6) to
   233.88 mm (N=3) for small cells, up to **339.80 mm** for large. That is N large,
   hand-made, brittle joints in the load path.
2. **One board with folded score lines — N−1 folds.** The required fold is the prism's
   exterior angle, `360/N`: **120° at N=3, 90° at N=4, 60° at N=6** (script section `(4)`).
   `TODO(unverified)`: **whether a folded FR4 score line is a credible structural feature at
   −60 °C.** Engineering judgement (not a measured or cited fact): standard 0.6 mm FR4 is a
   **brittle glass-fibre/epoxy thermoset** — it is not a ductile metal at any temperature, and
   a tight crease either snaps the glass weave or leaves a stress-raiser; the conventional
   workarounds (a routed/scored V-groove with an epoxy fillet, or a flex hinge) both add a
   material joint and mass. **This is not sourced in-repo and is flagged, not asserted.**

There is a third route — **hold each face only by its hub tab, no edge joins** — but then the
faces are N independent panels in a ring, i.e. **the prism is not closed and has no ring
stiffness advantage**; it collapses back into N blades.

### 5.2 What the closed prism costs versus the four independent blades

| | Current model (4 independent blades) | Closed N-gon prism |
|---|---|---|
| Face boards | 4 | N (3, 4 or 6) |
| Tab/socket joints to hub | 4 | **N** (3 / 4 / 6) |
| **Edge seams** (long-edge joins) | **0** (blades are independent) | **N** (3 / 4 / 6), or N−1 folds |
| Seam solder mass | 0 | **≈ +1.56 g for every N** (script §(6): `A_f·H·7.4e-3`, A_f = 0.30 mm² `TODO(unverified)`) — nearly N-independent because total seam length ≈ 2× total string length |
| Failure modes | each blade fails alone; a cracked blade does not propagate | **one seam crack propagates around the ring**; every seam is a new brittle joint in the load path; a fold is a new crease/glass-break site |
| Hub change | none (already built: 4 sockets at 90°, `J_W1..J_W4`) | **new hub: N sockets at 360/N** — for N=3 or 6 a **respin** of ADR-048 |

### 5.3 "Flat faces mean the cells do not have to be bent" — **confirmed, and it is not triangle-specific**

**Confirmed:** every **polygonal** prism has **flat** faces, so cells lie flat on any face for
**N = 3, 4, 5, 6, …** — and the **accepted four-blade design is already flat too** (each blade
is a flat FR4 plate; `wing-mass-shape.md` §2, `wing-insolation-geometry.md` §6). **Only a true
cylinder** (the N→∞ limit) has a continuously curved surface, and only a cylinder would force
cells onto a curved or polygonal-chord substrate. Therefore:

> **"Cells do not need bending" is true of the existing four blades, of a triangle, of a
> pentagon and of a hexagon alike — it is a property of being flat, not of being a triangle.
> It is not an argument for the triangle, and it is not an argument against the incumbent.**
> **Refuted as a triangle-specific reason.**

---

## 6. Part 6 — the answer

### Recommended: **KEEP the current four vertical blades (N = 4).** Do not build a triangle, and do not build a pentagon.

The deciding facts, in order of force:

1. **The pentagon is dead on arithmetic.** `12 ∤ 5`. Uniform faces force 10 cells (5.00 V,
   cannot charge the 5.4 V bank) or 15 cells (7.50 V nominal, 11.62 V cold OCV, worse over-voltage
   than the accepted 9.3 V). The only 12-cell pentagon is a non-uniform (2,2,2,3,3) face
   population, which **violates ADR-049's identical-arms rule**. **The deciding number is 12/N.**
2. **There is no energy prize for any N.** Per installed cell area, every N and the cylinder
   harvest exactly `(1/π)·cos h = 0.305107` (Part 1). So the choice is purely mechanical, and
   the incumbent is **already implemented** (ADR-048: four sockets at 90°, `J_W1..J_W4`).
3. **The triangle's stated advantage is backwards.** `12/3 = 4` cells/face makes the triangle
   the **tallest (233.88 mm) and narrowest (28.87 mm ⌀, AR 8.10)** — the **least stable** of the
   survivors, not the most. It also needs 3 board-to-board seams that the incumbent does not.
4. **The triangle's one real win is ripple (14.03 % vs 32.53 %)** — but with a supercap bank and
   a shunt clamp (no MPPT) the rotation-average *energy* is what is captured, and that is
   identical for both. Ripple is a second-order margin question and the incumbent already lives
   with a larger one.
5. **The hexagon (N=6) is the only mechanically attractive alternative** — shortest (117.74 mm),
   widest (50.00 mm), lowest aspect ratio (2.35, most stable) — but it buys **zero energy**,
   costs **6 tab joints + 6 edge seams**, forces **6 hub sockets at 60°** (a hub respin), grows
   the outer diameter to 50 mm (more drag and inertia than the 35.36 mm N=4 prism), and drops
   each face to 2 cells. **Not worth the hub respin for no energy gain.**

**If a polygon were nevertheless forced on us, it would be N=6** (most stable, shortest) —
never N=3, and never N=5.

**What a switch would force on the hub.** Socket count and angle change from **4 @ 90°** to
**N @ 360/N** — 3 @ 120° (triangle) or 6 @ 60° (hexagon). Because ADR-048's four sockets are
already in the schematic (`J_W1..J_W4`) and on the v9 sheet, that is a **hub respin plus a
re-validation of the wing tab geometry (ADR-046) and the antenna solder access (ADR-045)** —
i.e. the switch costs a new hub design order for a change that Parts 1–4 show buys **no**
energy, and (for N=3) makes stability **worse**.

**The alternative reading does not change the verdict.** If "polygon" instead means *N radial
fin blades at 360/N* (script §(5)), then the accepted four blades **are** the N=4 case; the
triangle becomes 4 cells/fin → a **233.88 mm blade and a 467.76 mm diameter** (bigger inertia,
more mass, more drag), and the pentagon still fails `12 ∤ 5`. **Keep N = 4 under either
reading.**

---

## 7. `TODO(unverified)` register

1. `TODO(unverified)` — **launch latitude and season.** Assumed 50.0 °N / winter solstice
   (δ = −23.44°); no in-repo source states either. Every absolute number scales with these;
   the *N-independence* result (Part 1) does not.
2. `TODO(unverified)` — **whether a folded 0.6 mm FR4 score line is a credible structural
   feature at −60 °C.** §5.1 is engineering judgement, not a measurement or a cited source.
3. `TODO(unverified)` — **the supercap value C and the payload's rotation period.** Without
   them the ripple ride-through (§2.4) cannot be computed; the repo does not state either.
4. `TODO(unverified)` — **solder-fillet cross-section `A_f = 0.30 mm²`** used for the seam-mass
   estimate (§5.2 / script §(6)). Assumed, not measured.
5. `TODO(unverified)` — **self-shading between prism faces is not modelled** (same gap as
   `wing-insolation-geometry.md` §7 item 5). Prism faces are 0.6 mm plates radiating from a
   small ring, so it is expected small, but no figure exists.
6. `TODO(unverified)` — **the prism model's cell orientation.** This document stacks the string
   **vertically** along the blade (the task's "blade HEIGHT scales with the per-face cell
   count"). The cross-check reading (radial fins, script §(5)) is given but not fully tabled;
   the cell packing orientation affects the absolute outlines, not the Part 1–3 results.
7. `TODO(unverified)` — **the wing's mechanical adequacy** under a 233.88–339.80 mm face
   (N=3) is unanalysed; ADR-046 §7 item 8 already files the tab-fillet cantilever as open.

---

## 8. Reproduction

```
python3 docs/analysis/ngon_prisms.py      # ~5 s; prints every number above
```

Dependency-free (stdlib `math` only). Model: sun `s = (cos h, 0, sin h)`; prism face normal
`n_k = (cos(ψ − 360k/N), sin(ψ − 360k/N), 0)`; `cos(incidence) = cos h · cos(ψ − a_k)`, clamped
at 0; rotation averages over uniform ψ; the series metric is `max_j (j · cos_(j)) / N`; the
cylinder and the K-facet polygon are the same integral, which is why N cancels.
