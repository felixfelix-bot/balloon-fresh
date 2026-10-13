# ADR-046 — Wing-board interface: tab/socket geometry, 4-wire pinout, wing outline, order shape

- Status: **Proposed** — the *design direction* this ADR records is a worker-derivable
  engineering consequence of ADR-006/ADR-034/ADR-040; the *text* has **not been accepted
  by a human**. It does not say Accepted. Every number below is either cited to an in-repo
  source or carries an explicit `TODO(unverified)` naming the open question.
- Date: 2026-10-07
- Decision owner: Felix (operator)
- Author: worker-balloon (Hermes agent), branch `feat/wing-board-v9`.
- Related:
  - `docs/hardware-design.md` (Hub-Board / Wing-Board sections) — **partly superseded here,
    see §0.3**.
  - `docs/adr/006-supercapacitor-power.md` — the 4-wing × 3-cell series stack, 1.5 V/wing,
    6.0 V/400 mA, 2× 3.3 F 2.7 V supercaps, TPS7A02 LDO, BAT54.
  - `docs/adr/029-dual-band-flight-board.md`, `docs/adr/034-radio-band-split-433-tx-2g4-rx.md`
    (433 MHz TX on the F33-2G4 / 2.4 GHz RX on a bare LoRa2021), `docs/adr/035-tdm-radio-schedule.md`,
    `docs/adr/040-v9-radio-site-optionality.md`, `docs/V9-RADIO-SITE-MATRIX.md`.
  - `docs/POWER-BUDGET-V9-D2BE.md` line 29–33 (12 cells, 1.5 V/wing, 6.0 V, ~120 cm²).
  - `tracker/hardware/wing_board/wing_schematic.py` — the old wing generator — **its net
    topology is reused; its footprints and tab pin count are superseded here, see §0.3**.
  - `docs/WING-TO-HUB-SOCKET-SPEC.md` (this branch) — the hub-side requirement derived
    from this ADR.
- Companion artefact: `tracker/hardware/wing_board/wing_board_v9.kicad_pcb` (the real wing
  board built to this ADR).

---

## 0. Reconciliation — which document wins, and why

### 0.1 The wing cannot be 65 × 28 mm and carry three 52 × 19 mm cells

`docs/hardware-design.md` line 62 gives the wing as **65 × 28 mm**, and lines 78–85/122–124
and `docs/POWER-BUDGET-V9-D2BE.md` line 29 require **three 52 × 19 mm cells in series per
wing**. A 52 mm dimension does not fit into a 28 mm width, and three 52 mm cells in a row do
not fit into a 65 mm length (3 × 52 = 156 mm). **The two statements in the same document
cannot both be true.**

What wins: **the electrical requirement (3 cells/wing, 12 cells total, 1.5 V/wing, 6.0 V
stack) wins**, because it is the load-bearing system requirement of ADR-006 and is repeated
in `docs/POWER-BUDGET-V9-D2BE.md`, `docs/SOLAR-PIN-REGULATORY.md` line 11 and
`docs/component-guide.md` line 113. The outline is therefore re-derived in §3.

Note the one number worth keeping: `docs/hardware-design.md`'s **65 mm** length factors
exactly as *8 mm tab + 3 × 19 mm cell pitch = 65 mm*, which is strong evidence that the
*documented length was the cell stack along the length*, and that the **28 mm width is the
erroneous figure** (it is the only figure that must change to admit a 52 mm cell).
This ADR keeps that reading as far as it can (§3.3) and flags the residual difference.

### 0.2 The 4-wings-in-series stack cannot use a common GND per wing

`docs/hardware-design.md` line 51–57 lists **three** connections per wing slot: `RF`,
`V_SOLAR`, `GND`. `wing_schematic.py` implements a 3-pin tab (`V_OUT`, `GND`, `V_CHAIN_IN`)
plus a separate `RF_FEED` pad.

In a **4-in-series** string (ADR-006) each wing's negative terminal sits at a *different*
potential: wing 1's − is the stack bottom (0 V), wing 2's − is +1.5 V, wing 3's − is +3.0 V,
wing 4's − is +4.5 V. **A single "GND" pin per wing cannot carry the series return** — it
would short every cell of every wing in parallel. The stack therefore needs **two floating
solar terminals per wing**, plus a separate system `GND` for the wing's ground plane / RF
reference. That is a minimum of **3 pins**, and the RF provision makes **4**.

### 0.3 Which artefact wins

| Item | `docs/hardware-design.md` / `wing_schematic.py` says | This ADR fixes | Why |
|---|---|---|---|
| Wing outline | 65 × 28 mm | **176 × 25 mm body + 8 × 9 mm tab (184 mm total)** (§3) | 65 × 28 cannot hold three 52 × 19 cells (§0.1); the electrical requirement wins |
| Tab pin count | 3 (`RF`/`V_SOLAR`/`GND`) and 3 (`V_OUT`/`GND`/`V_CHAIN_IN` + separate RF pad) | **4, single tab** (§2) | a 4-in-series stack needs 2 floating solar terminals + GND + RF provision (§0.2) |
| Tab width | 5 mm | **9.0 mm** (§2.1) | 4 pads at 1.8 mm pitch with 1.2 mm lands need 9 mm |
| RF per wing | part of the tab's 3 connections | **V2-only provision, not used on v9** (§2.4) | ADR-034/040 put every v9 radio on the hub; no v9 RF path exists on a wing |
| Solar cells | `TestPoint:TestPoint_THTPad_D2.0mm_Drill1.0mm` | real solder lands, one 1.6 × 14.0 mm land per cell terminal (§3.4) | a test point is a 2 mm via-style pad, not a cell land |
| RF pads | `TestPoint:TestPoint_THTPad_D2.0mm_Drill1.0mm` | real 4.0 × 1.2 mm tab land (§2.2) | same |
| Net topology (3 cells in series, RF feed net, optional ferrite) | `wing_schematic.py` | **reused unchanged** | it is electrically correct; only the physical footprints were fake |

---

## 1. Context

The v9 flight board is a **3D assembly**: one central hub PCB plus **four identical wing
PCBs** soldered onto the hub's edges at **90° spacing**. The wing is the solar carrier
(3 cells in series = 1.5 V per wing) and, on V2, is intended to also carry a 2.4 GHz PCB
Yagi. On v9 the radios are on the hub (ADR-034, ADR-040), so the wing is a **solar carrier
plus a mechanical member**; the RF land is carried as a provision only.

---

## 2. ELECTRICAL interface (the wing tab)

### 2.1 Pin count and pinout — **4 pins, one tab**

**Decision: the wing has exactly ONE tab with FOUR pins.**

| Pin | Net name | Function | Direction |
|---|---|---|---|
| 1 | `SOLAR_P` | this wing's solar **positive** terminal (the + end of the wing's 3-cell series string) | out of the wing |
| 2 | `GND` | system ground / wing ground-plane reference | reference |
| 3 | `RF_FEED` | 2.4 GHz antenna feed **provision** — see §2.4 | bidir, unused on v9 |
| 4 | `SOLAR_N` | this wing's solar **negative** terminal (the − end of the wing's 3-cell series string) | out of the wing |

Pins 1 and 4 are the two terminals of the wing's solar string and are placed **outermost**
so the hub can link adjacent wings without crossing signals. Pins 2 and 3 sit between them.

- Cell-internal series chain on the wing (reused from `wing_schematic.py`):
  `SC1+ = SOLAR_P` → `SC1− = SOLAR_MID1 = SC2+` → `SC2− = SOLAR_MID2 = SC3+` → `SC3− = SOLAR_N`.
- `GND` is **not** in the solar string. On the wing it terminates at the bottom-copper ground
  reference (V2 antenna ground); on v9 it is the wing's mechanical/ground reference only.
- `RF_FEED` is a **V2-only provision** (§2.4).

### 2.2 Tab land geometry (wing side)

| Parameter | Value |
|---|---|
| Pads | 4, rectangular, SMD, F.Cu + F.Paste + F.Mask |
| Pad size | **4.0 mm (along the insertion axis) × 1.2 mm** |
| Pad pitch | **1.8 mm** (0.6 mm between pad edges) |
| Pad centres | 1.0 mm inboard of the tab's inner edge; 1.2 mm clear of the tab's side edges |
| Copper-to-board-edge clearance | ≥ 1.0 mm on every tab pad |

### 2.3 The 6.0 V stack: series order, polarity, shading

**Series order (mandated).** With all four wings identical and each wing's `SOLAR_P` the
positive terminal of its own 1.5 V string:

```
stack_top  = W1.SOLAR_P        -> BAT54 -> supercap bank (ADR-006)
             W1.SOLAR_N == W2.SOLAR_P      (hub link)
             W2.SOLAR_N == W3.SOLAR_P      (hub link)
             W3.SOLAR_N == W4.SOLAR_P      (hub link)
stack_bot  = W4.SOLAR_N        -> system GND
```

**Polarity.** `SOLAR_P` is the positive end of each wing's 3-cell series string;
`SOLAR_N` the negative end. Nominal 1.5 V per wing, 6.0 V across the string at 400 mA
(2.4 W peak in direct sun) — ADR-006, `docs/POWER-BUDGET-V9-D2BE.md` line 31.

**Where GND returns.** There is **no per-wing solar ground return**. The single system
`GND` return is the stack bottom (`W4.SOLAR_N`), which the hub ties to the ground plane.
Each wing's `GND` pin is a *reference/plane* connection, not a solar return.

**What happens if one wing is shaded.** All four wings are in **series**, so the string
current is set by the *weakest* element. A shaded wing
1. stops sourcing, and
2. becomes a reverse-biased element that the other three wings (up to 400 mA) will try to
   drive through — a hot-spot / cell-degradation risk, not just a power loss.

Consequence: **the 6.0 V stack collapses to (approximately) the illuminated-wings' voltage
only if the shaded wing is bypassed; without a bypass path the whole string's current
collapses and the shaded cells are reverse-stressed.**
**Mitigation (mandated):** one **bypass Schottky per wing slot, on the hub**, across
`SOLAR_P`–`SOLAR_N` of that wing, so a shaded wing is bypassed and the remaining 3 wings
still deliver ≈ 4.5 V. The bypass diodes are **DNP for the first prototype build** (see
`docs/WING-TO-HUB-SOCKET-SPEC.md` §5). The 6.0 V / 2.4 W budget of ADR-006 and
`docs/POWER-BUDGET-V9-D2BE.md` is only valid with all four wings illuminated; a bypassed
string must be re-budgeted (3/4 of the array) — `docs/POWER-BUDGET-V9-D2BE.md` §"Array
coverage check" already notes that 1–2 illuminated wings are the representative case.

### 2.4 Is the per-wing RF connection used on v9?

**No. It is a V2-only provision and is not connected on v9.**

- ADR-034 D1 puts both v9 radio directions on the **hub** (TX 433 MHz on the F33-2G4,
  RX 2.4 GHz on a bare LoRa2021); ADR-040 keeps both radio **sites on the back of the hub**.
  No v9 radio has a port that reaches a wing.
- `docs/hardware-design.md`'s "RF (vom SP4T)" per slot describes the **v1/v2 single-SP4T**
  antenna-switch architecture (`docs/antenna-strategy.md` §Yagi/SP4T), which v9 does not have.
- Therefore on v9 the wing's pin 3 (`RF_FEED`) is a **copper land that is left electrically
  unconnected** (a provision). It carries no net on v9; the wing's RF_FEED net is a
  1-pad net so there is no ratsnest and no DRC consequence.
- **The wing's 2.4 GHz PCB Yagi is deferred to V2** and is NOT etched on the v9 wing.
  Rationale: v9 has no wing RF path, so a Yagi would be dead copper; and 50 Ω CPW on the
  wing would need the hub's RF switch that v9 does not carry. The `RF_FEED` land is
  provisioned so a V2 wing can be ordered with the same tab.
- `TODO(unverified)`: the exact V2 wing RF stack-up (CPW geometry on 0.6 mm FR4,
  `er` — `docs/hardware-design.md` line 100 states `er = 4.4` while line 64's stack is
  0.6 mm FR4; the V2 CPW width for that stack is **not** derived in any in-repo source).

---

## 3. WING footprint count and dimensions

### 3.1 Count

- **4 identical wing PCBs per flight assembly** (ADR-006; `docs/hardware-design.md` line 8).
- On each wing PCB: **12 component footprints** —
  3 × solar-cell mount footprint (1 land each), 1 × wing tab (4 lands),
  3 × mounting/handling hole (NPTH), 3 × fiducial, 1 × ferrite-bead provision (DNP),
  1 × RF test land (V2 provision, DNP).

### 3.2 Outline

| Parameter | Value |
|---|---|
| Body | **176.0 mm × 25.0 mm** |
| Tab | **8.0 mm** protruding × **9.0 mm** wide, centred on the body's short axis, at one end |
| **Total outline length (incl. tab)** | **184.0 mm** |
| Substrate | 0.6 mm FR4, 2 layers (Top: solar/power, Bottom: GND) — `docs/hardware-design.md` lines 14/63 |
| Substrate thickness | 0.6 mm (`docs/hardware-design.md` line 14/63). `TODO(unverified)`: whether the first JLCPCB order will accept 0.6 mm for a 176 mm board — JLCPCB's 0.6 mm option is a listed thickness, but its **minimum board size / warpage handling for 0.6 mm at 184 mm length is not confirmed in any in-repo source**, and the operator may prefer 0.8 mm for handling. |

### 3.3 The three 52 × 19 mm cells (positions, board-local mm, origin = body lower-left, +x toward the tip)

Cells are oriented with their **52 mm dimension across the wing (y)** and their **19 mm
dimension along the wing (x)**, so the stack runs tip-ward from the tab — the reading of
`docs/hardware-design.md`'s 65 mm length that its 65 = 8 + 3 × 19 factorisation supports:

| Cell | x span (mm) | y span (mm) | Note |
|---|---|---|---|
| SC1 (nearest the tab) | 4 … 56 | 3 … 22 | |
| SC2 | 62 … 114 | 3 … 22 | |
| SC3 (tip) | 120 … 172 | 3 … 22 | |
| — | pitch 58 mm = 52 mm cell + 6 mm land gap | | |

- Tab: x ∈ [−8, 0], y ∈ [8, 17].
- Cell-free corridors used by the routing: x ∈ [0, 4] (tab-side margin),
  x ∈ [56, 62] and x ∈ [114, 120] (land gaps), x ∈ [172, 176] (tip margin),
  y ∈ [0, 3] and y ∈ [22, 25] (edge margins).
- **Residual difference from `docs/hardware-design.md`**: the outline is 176 × 25 mm, not
  65 × 28 mm. The length grows because the cells are stacked along the length; the width
  shrinks to 25 mm because the documented 28 mm is 3 mm wider than the 19 mm cell plus
  margins needs, and every millimetre of wing is a millimetre of cube-span at the hub.
  `TODO(unverified)`: whether the operator prefers the alternative packing
  (3 cells stacked across a ~65 × 57 mm wing, which keeps the documented 65 mm length and
  changes only the width). Both packings satisfy ADR-006; this ADR picks the long-thin one
  because it is the one the word "wing" and the `docs/hardware-design.md` §3D-Assembly
  4-arm radial describe, and because it keeps the wing narrow at the hub.

### 3.4b Bottom copper on the v9 wing is unused (deviation, stated)

`docs/hardware-design.md` line 64 gives the wing as "2 layers (Top: Solar + Antenne,
Bottom: GND)". **On the v9 wing the bottom copper is NOT populated** — the v9 board routes
everything on F.Cu and carries no B.Cu pour or plane, so the plotted B.Cu gerber is empty.
Reason: ADR-046 §2.4 makes the wing RF a V2 provision, so there is no antenna ground to
return on v9, and the wing's single `GND` pin is a provision land. Adding a B.Cu pour would
be dead copper on v9 and would need thermal reliefs around a net that has one pad.
`TODO(unverified)`: the V2 wing **will** need a B.Cu ground for the 2.4 GHz CPW, so a V2
wing is a different board, not a population change.

### 3.4 Solar-cell lands

- **One land per cell terminal** (two per cell → 6 lands total), because each cell's two
  terminals are at the cell's two **x** ends.
- Land size: **1.6 mm (x) × 4.0 mm (y)**, SMD, F.Cu + F.Mask + F.Paste, centred on y = 12.5 mm
  (y span 10.5…14.5 mm).
- Land x positions: `SC1+` 2.0, `SC1−` 58.0, `SC2+` 60.0, `SC2−` 116.0, `SC3+` 118.0, `SC3−` 174.0
  (all mm, board-local, absolute x). On the board these are the pads of the three
  `SolarCell_52x19mm` footprints, whose origins are the cell centres x = 30 / 88 / 146 mm.
- **Why the land is 4.0 mm and not more**: the 4 tab pins occupy y = 9.8…15.2 mm, and the
  SOLAR_P / SOLAR_N tracks must reach pins 1 and 4 along y = 9.8 / 15.2 mm respectively
  without entering the SC1 land. A 4.0 mm land (10.5…14.5 mm) leaves 0.7 mm of clearance
  above and below that pair of tracks, which is what makes the board routable with
  **0 errors and 0 unconnected items** (see §6 evidence). A taller land would have to be
  approached on B.Cu, and a via pair at the tab would then sit inside the tab's 9 mm width.
- The land is therefore a **routing-constrained** land, not a matched land pattern.
  `TODO(unverified)`: the **exact solder-tab geometry of the 52 × 19 mm cell** (contact
  width, contact pitch, contact distance from the cell edge). No in-repo source carries it;
  `docs/component-guide.md` line 107 lists only "52x19mm (0.5V 400mA)". **If the measured
  contact is wider than 4.0 mm the land must grow and the routing must move to B.Cu** — this
  is the single most likely reason for a respin after the cells are measured.

---

## 4. MECHANICAL interface — the tab/socket joint

### 4.1 Geometry (this ADR's numbers)

| Parameter | Value | Source / basis |
|---|---|---|
| Wing tab width | **9.0 mm** | §2.1 (4 pads at 1.8 mm pitch) |
| Wing tab thickness | **0.6 mm** (= substrate) | `docs/hardware-design.md` line 63 |
| Tab protrusion beyond the body | **8.0 mm** | §3.2 |
| **Insertion depth into the hub** | **6.0 mm** | `docs/hardware-design.md` line 46 gives "~1 mm wide slot"; the depth is not given. 6.0 mm keeps the slot 5.0 mm short of the 22 mm hub's centre, clear of the component court. `TODO(unverified)`: the hub's actual component keep-out at the slot location is an **hub-layout** number owned by the concurrent v9 hub worker; see `docs/WING-TO-HUB-SOCKET-SPEC.md` §3. |
| Hub slot width | **0.9 mm nominal, ±0.10 mm** | proposed; see §4.3 |
| Nominal solder gap | 0.30 mm (0.9 mm slot − 0.6 mm tab) | derived |
| Attach angle | **90°** to the hub plane, wing plane normal to the hub plane | `docs/hardware-design.md` lines 46–48, §3D-Assembly |
| Slots per hub | **4, at 90° spacing** | `docs/hardware-design.md` line 47 |

### 4.2 Option set: milled slot vs plain pads

**Option A — milled edge slot (recommended).**
The hub's edge carries a routed slot 0.9 mm wide × 6.0 mm deep, with the four wing-tab lands
reproduced on the hub's edge faces (`docs/WING-TO-HUB-SOCKET-SPEC.md` §2). The wing tab
inserts 6 mm into the slot and is soldered on both faces.
- Pro: the slot **keys** the 90° angle and the insertion depth; the solder fillet is loaded
  in shear and the joint cannot peel, because the tab is captured.
- Pro: hand-assembly of four wings at 90° needs a fixture only for the fillet, not for the angle.
- Con: **adds a fabrication step** (routed/milled internal cut-out).

**Option B — plain pad pair on the hub edge (no slot).**
No slot. The hub carries a pair of solder lands on its top/bottom face beside its edge; the
wing's tab is laid on them at 90° and soldered.
- Pro: **cheapest** — no milling line item, no extra fab step.
- Con: **the joint's strength is entirely the solder fillet.** A 0.6 mm FR4 tab edge-soldered
  to a land has a small fillet area and a long lever arm (176 mm of wing); peel and shock
  are taken by the solder, and a 90° alignment must be fixtured by hand for four wings.
- Con: no positive insertion-depth stop.

**Recommendation: Option A (milled edge slot) for the first prototype**, on the grounds that
hand-aligning four 176 mm wings with no mechanical key is the higher risk in a
one-shot prototype build, and because the slot also fixes the insertion depth. Option B
remains a valid cost-down for a later volume run once the assembly fixture exists.

`TODO(unverified)`: the **JLCPCB line-item cost delta of the milled slot** is not derivable
from any in-repo source — JLCPCB prices routed cut-outs by a routing line item and the
operator must read the live quote. This ADR records the *shape* of the cost (a fab step and
a line item, against a cheaper plain-pad joint that relies on the fillet) and not a number.

### 4.3 Slot tolerance rationale

`docs/hardware-design.md` line 46 says the slot is "~1 mm wide" for a board it also says is
0.6 mm thick, i.e. a 0.4 mm nominal gap. Recorded here: **0.9 mm ± 0.10 mm** is preferred
over ~1.0 mm because a 0.4 mm gap is more solder than the joint needs and lets the wing rock
during soldering, while a 0.3 mm gap still fills reliably.
`TODO(unverified)`: JLCPCB's actual **routed-slot width tolerance** (the ±0.10 mm above is an
assumption, not a cited figure). If the supplier cannot hold it, Option B (plain pads)
becomes the fallback — a slot that can come out equal to the 0.6 mm tab is worse than no slot.

### 4.4 Mechanical load and other features

- The **solder fillet carries the mechanical load in both options** — the slot only stops
  rotation and over-insertion. `docs/hardware-design.md` line 162 ("Loetverbindungen an
  allen 4 Slots tragen mechanisch") is confirmed as the load path.
- The wing carries **3 × NPTH handling/mounting holes** and **3 fiducials** so the wing can
  be held in a jig and located for the solder step without touching the cell lands.
- `TODO(unverified)`: the wing's **structural adequacy** under the 4-arm cantilever load
  (shock, and the ~176 mm lever arm) is **not** analysed in this ADR and no in-repo source
  analyses it. If the first prototype flexes at the tab, the fix is a longer slot/fillet or a
  hub-side fillet rib, not a thicker wing.

---

## 5. Order shape: designs and quantities

### 5.1 How many distinct PCB designs

**Two distinct designs per flight set:**
1. the **v9 hub** — one design, containing all four 90° sockets; and
2. the **v9 wing** — one design, used **four times** per assembly.

### 5.2 Panel or separate designs on one order?

**Recommendation: two SEPARATE designs on ONE order (two line items), NOT a single panel.**

Reasons:
1. **Different designs, different stack-ups.** The hub is a multi-layer board (its layer
   count is being set by the concurrent v9 worker) while the wing is a 2-layer 0.6 mm board.
   A single panel is only possible when every member shares one stack-up; the two designs do
   not, so **if the hub is 4-layer the decision is forced to separate designs**.
2. **Panel utilisation is poor anyway.** The wing is 176 × 25 mm; panelling one long thin
   part saves little, and the parts are not the same material/finish requirement.
3. **Shared shipping, separate pricing** — one order, two line items, is how JLCPCB prices
   different designs; the operator gets one shipment.

`TODO(unverified)`: the **v9 hub's layer count and thickness** are owned by the concurrent
v9 hub worker and are not fixed at the time of writing. If the hub turns out to be
2-layer / 0.6 mm / same finish, a **single combined panel becomes possible** and should be
re-costed; this ADR does not pick the panel because the hub's stack-up is unknown.

### 5.3 Quantities for the first prototype build

| Design | Quantity | Basis |
|---|---|---|
| Wing | **5** | one flight set = 4 identical wings; 5 is JLCPCB's 5-piece minimum and leaves 1 spare |
| Hub | **5** | JLCPCB 5-piece minimum; 1 flight set + spares |

A second flight set would need 10 wings + 5 hubs. `TODO(unverified)`: whether the first
prototype is **one** flight set or **two** — the operator's intent is not recorded in any
in-repo source, and it changes the wing quantity from 5 to 10.

---

## 6. Consequences

- The wing tab is a **4-pin single-edge tab**; the hub must reproduce those 4 lands per slot
  on **both** edge faces (`docs/WING-TO-HUB-SOCKET-SPEC.md`).
- The **series stack is wired on the hub**, not the wing. Each wing is a floating 1.5 V source
  with a separate ground reference.
- A **bypass Schottky per slot on the hub** is mandated as a DNP provision, because without it
  one shaded wing collapses (and reverse-stresses) the whole 6.0 V string.
- The **wing RF/Yagi is V2-only**; v9 wings are solar carriers.
- The hub and the wing are ordered as **two designs on one order** (5 each), unless the hub's
  stack-up lands identical to the wing's.

## 7. Open items (all explicit, none invented)

1. `TODO(unverified)` — exact 52 × 19 mm cell solder-tab geometry (contact size/position).
2. `TODO(unverified)` — JLCPCB cost delta of the milled slot vs plain pads.
3. `TODO(unverified)` — JLCPCB routed-slot width tolerance (±0.10 mm assumed).
4. `TODO(unverified)` — 0.6 mm substrate availability/handling for a 184 mm board.
5. `TODO(unverified)` — hub v9 layer count / thickness (owns whether a single panel is possible).
6. `TODO(unverified)` — whether the first prototype is one flight set or two.
7. `TODO(unverified)` — hub-side component keep-out at the slot (owned by the v9 hub worker).
8. `TODO(unverified)` — structural adequacy of the tab fillet under the 4-arm cantilever load.
9. `TODO(unverified)` — the operator's preferred cell packing (long-thin 176 × 25 vs
   stacked 65 × 57); this ADR picks long-thin and says so.

## 7b. Evidence actually observed for the companion board

All figures below are from tool output on branch `feat/wing-board-v9`
(`tracker/hardware/wing_board/wing_board_v9.kicad_pcb`, built by
`tracker/hardware/wing_board/build_wing_v9.py`):

| Check | Command | Result |
|---|---|---|
| repo DRC scorecard | `python3 tracker/hardware/drc_score.py wing_board/wing_board_v9.kicad_pcb --label wing-v9 --tool skidl-script` | `fab_ready: 1`, `fp: 12`, `shorts: 0`, `clearance: 0`, `unconnected: 0`, `vias: 0`, `copper_mm: 212.0` |
| fleet order gate | `pcb_order_gate.py wing_board_v9.kicad_pcb --fab gerbers_wing_v9 --out wing_v9-GATE-RECORD.json` (tool: `/home/c03rad0r/.hermes/profiles/manager/scripts/fleet/pcb_order_gate.py` — the SAME tool that wrote `tracker/hardware/v8j-GATE-RECORD.json`; the repo has no in-tree copy) | **`ORDER GATE: PASS`, exit 0**, `errors=0 unconnected=0 warnings=23 kicad=9.0.8` |
| pair verification | `pcb_order_gate.py … --verify wing_v9-GATE-RECORD.json` | `ORDER GATE: VERIFIED`, exit 0 |
| board sha256 | — | `8448d76b3a4e108f12016e1980bb954f068625d27522a1640a07ffc72fa3682c` (deterministic: two consecutive builder runs produced this same digest) |
| fab (gerber dir) sha256 | — | `90cb2480a28b2dce7388f490b439ca299b41dde9feeae0570889824dd2159477` (the digest `pcb_order_gate.py` binds) |
| fab (order zip) sha256 | — | `dab1e8dcfb075d6563f7208a93ef1eb88f83c597e3fe1ca851dac376c77766f5` |

The 23 items the gate counts are **warnings only** (12 `lib_footprint_issues`, 6
`silk_edge_clearance`, 2 `silk_overlap`, 2 `text_height`, 1 `silk_over_copper`) — the gate's
contract is 0 errors / 0 unconnected, which is met. There are **0 errors** and **0
unconnected items**.

## 8. Status of this text

**Proposed.** The *design direction* (4-pin tab, hub-side series stack, V2-only wing RF,
long-thin wing, two designs on one order) is an engineering consequence of the cited ADRs.
**The text has not been accepted by a human.** Nothing in this ADR is to be read as an
operator decision beyond what ADR-006/ADR-034/ADR-040 already record.
