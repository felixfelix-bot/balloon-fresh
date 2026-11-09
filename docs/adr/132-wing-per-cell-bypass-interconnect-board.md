# ADR-132 — The wing carries its own interconnect board with a PER-CELL bypass diode, and that board is the wing↔hub interface

> Numbered **132** on 2026-10-25. Verified free with the repo's own allocator
> (`scripts/adr_next_number.py --number 132` / `--path …` both exit 0) and across all
> refs (`git log --all --name-only --pretty=format: -- 'docs/adr/132*'` returns nothing).

> **AMENDED 2026-10-25 by ADR-134.** The tab is now **TWO pins** (`SOLAR_P`, `SOLAR_N`);
> `GND` and `RF_FEED` were removed as dead copper (antennas attach to the hub by U.FL).
> The board is therefore **4 nets and 2 tab pads**, not 6 and 4. The board also became a
> genuine **small connector**: 44 × 20 mm = 8.8 cm², **0.79 g/wing, 3.18 g for four** —
> the cells stay on the foam and only their `+`/`−` tails reach the board. Everything
> else in this record (per-cell SS24 bypass, end-only cells, cathode marks, the two-layer
> protection argument) **stands**.

- **Status:** **Accepted by operator** (Felix, 2026-10-25, verbatim): *"the wing board needs
  bypass diodes for each solar cell. Please update the adrs accordingly and please make a
  small board with bypass diodes that all the cells can be soldered to. This board will be
  responsible for connecting the wing to the hub board."*
- **Date:** 2026-10-25
- **Author:** balloon-hermes (manager CW), branch `pr/wing-interconnect-board`.
- **Supersedes:** **ADR-054 §2.3** — the **per-cell bypass REJECTION**, for the WING array.
  ADR-054's series topology, its hub-side per-interface `D_BP` and its mechanism correction
  **all stand.** See §3 for why the rejection no longer holds.
- **Amends:** **ADR-131 D2** — the "carried insert" becomes a **real small PCB** with a
  defined BOM, not a bare strip. ADR-131's other decisions (4-pin row retained, slot ≥1.0 mm,
  release designed with the interface) **stand unchanged**.
- **Amends:** **ADR-130 D1** — "the wing has no PCB" becomes "the wing has **one** small
  interconnect board and **no full-area carrier**". The mass argument ADR-130 made is
  unaffected: the board is a spine, not a plate (§5).
- **Confirms:** **ADR-129 D2** — which already puts **one SS24 per hub-array cell**
  (`D_HUB1`/`D_HUB2`). This record makes the wing side symmetric with it.
- **Binding constraints:** **ADR-052** (cells END-MOUNTED, no face bond) and **ADR-051
  §2.5.1** (latched one-shot cut).

---

## 1. The decision, in one paragraph

**Each wing carries one small FR4 interconnect board. All three cells are soldered to it at
their ends, and each cell has its own SS24 Schottky bypass diode across it. The board presents
the existing 4-pad tab, so it is the single part that both protects the cells and connects the
wing to the hub.**

---

## 2. What the board contains (electrically)

The wing string is 3 cells in series (ADR-006 / ADR-046 §2.1). Three cells create **two
internal nodes**, so per-cell coverage needs **three diodes**:

| Ref | Cathode (K) → | Anode (A) → | Protects |
|---|---|---|---|
| `D1` | `SOLAR_P` (SC1 +) | `SOLAR_MID1` (SC1 −/SC2 +) | SC1 |
| `D2` | `SOLAR_MID1` | `SOLAR_MID2` (SC2 −/SC3 +) | SC2 |
| `D3` | `SOLAR_MID2` | `SOLAR_N` (SC3 −) | SC3 |

- **Part: SS24, SMA (2 A / 40 V)** — the same class ADR-129 D2 already uses for the hub
  array. ADR-054 §2.4 requires **≥2 A continuous / ≥40 V** for a bypass carrying the other
  cells' current, and it **disqualifies the BAT54 (200 mA / 30 V)** as 6× under-rated. The
  TAB's `D_BP1..4` must be re-rated to SS24 for the same reason (ADR-129 already did).
- **Polarity is fixed by the part:** cathode to the cell's **HIGH** node, anode to its **LOW**
  node, so the diode is **reverse-biased in normal operation** and conducts only when the cell
  is shaded, cracked or open. **See §4 — a reversed diode is the hazard.**

### 2.1 Cell-to-board lands

Each cell lands **at its two ends only** (ADR-052 — no face bond). The board is therefore
**not** a full carrier: it is a spine with **three windows** cut where the cell centres sit,
so no FR4 lies under a cell face.

```
wing string, on the board:

  SOLAR_P ──[SC1 pad]──==cell==──[pad]── SOLAR_MID1 ──[SC2 pad]──==cell==──[pad]── SOLAR_MID2 ──[SC3 pad]──==cell==──[pad]── SOLAR_N
                  │                          │                            │                        │
                 D1                         D2                           D3                       (tab)
```

Joint count per wing: **6 cell-end joints** (2 per cell) + **6 diode joints** (2 per diode) =
**12**, plus the 4 tab lands. Across four wings that is **+24 diode joints** — the figure
ADR-054 §2.3 already quoted, now accepted rather than rejected.

---

## 3. Why ADR-054 §2.3's rejection no longer holds

ADR-054 rejected per-cell bypass on two grounds. **Both were arguments against the WING-BOARD
placement as it then existed — and one of them is dissolved by this record's own change.**

**(a) "+24 joints for ~1.2 W of peak on a 15.85× surplus."** Still true, and still the cost.
It is **accepted here by operator decision**, not re-argued. The operator's requirement is
per-cell protection; the mass/joint cost is the price and §5 states it.

**(b) "A free-standing 2-lead bridge over a 0.21 mm bare wafer" — the decisive objection.**
ADR-054 §2.3 wrote:

> *"On the END-ONLY, no-adhesive-bond mount (ADR-052) there is no board face behind the cell,
> so a per-cell diode would require a **free-standing 2-lead bridge over a 0.21 mm bare
> wafer** — exactly the unsupported spanning element the spine-and-ribs frame exists to
> avoid."*

**That objection only applies when there is no board. This record puts the diodes ON a board**,
so each diode sits on copper with its own pads, and no part bridges the wafer. ADR-054's
mechanism objection is **dissolved by the very change the operator has asked for.**

**(c) The soft-shunt hole is closed.** ADR-054 §2.3 named the one condition that reopens the
rejection:

> *"Per-cell bypass becomes load-bearing for hot-spot safety … if the operator's bench crack
> test shows SOFT SHUNTS dominate. On a soft shunt, only a per-cell diode clamps the failing
> cell: a per-wing diode cannot see it, because the wing still sources positive voltage."*

**Per-cell protection removes this dependency on an unmeasured test entirely.** That is the
substantive engineering gain of this record and the reason it is not merely a preference.

**(d) Symmetry with the hub.** ADR-129 D2 already specified **one SS24 per hub-array cell**
(`D_HUB1`/`D_HUB2`). The wing was the ONLY array without per-cell protection. After this
record the two arrays are protected the same way, and there is no longer a rule that says
"per-cell on the hub, per-wing on the wing" for an operator to have to remember.

### 3.1 What is NOT reopened

- **ADR-054's 12-cell series topology** stands (the array-side current argument in §1.1 is
  untouched by diode placement).
- **The HUB-side per-interface `D_BP1..4` stays MANDATORY** and stays on the hub.
  **This board's diodes do NOT replace them** — see §4.1.
- **The mechanism correction (§2.4)** stands: a bypass diode does not "make the converter
  tolerate" failures.

---

## 4. The two failure modes this board must not introduce

### 4.1 A cut still needs the hub-side `D_BP` — the wing board cannot provide it

The wing board's diodes protect **cells inside the wing**. They **cannot** protect against the
wing being **cut away**, because they leave with it. ADR-054 §3.2 is explicit:

> *"If the per-group diodes are on the wing boards, a cut jettisons them and the array dies on
> the first cut."*

So for a cutter-carrying flight **both** layers are required:

| Layer | Where | Protects against | Part |
|---|---|---|---|
| **Per-cell** | **this board (wing)** | shaded / cracked / open / soft-shunted **cell** | `D1..D3`, SS24 |
| **Per-interface** | **hub** `D_BP1..4` | **wing cut** (module gone) | SS24, ADR-129 |

**Fitting this board does not reduce the requirement for `D_BP`.** Anyone reading this ADR as
"the wing now has bypass, so the hub diodes are optional" has it backwards — read ADR-054 §2.2.

### 4.2 A reversed diode silently shorts out its own cell

ADR-054 §2.3(b) — the hazard is **real and unchanged**:

> *"Install it the other way round and it is forward-biased by the cell's own 0.5 V: it clamps
> the cell to ≈0.35 V and shunts it, so the cell produces ≈0 V while the diode carries the full
> 1.2 A continuously. Twelve diodes in a hand-built array are twelve chances to do this;
> nothing in the topology catches it (it is invisible to a string-voltage check, because the
> loss is only 0.85 V of 6.0 V)."*

**Mitigations made mandatory by this record:**

1. **Silkscreen polarity on every diode position** — cathode bar drawn on the silk, plus the
   cell's `+` marked at each land. Silk is already a hard gate (AGENTS.md §23).
2. **A first-article continuity test** on every wing before flight: with the cells dark, each
   diode must read **reverse-biased** (open) across its cell. A forward reading is a reversed
   diode — reject the wing. This must be a written step, not a habit.
3. **`TODO(unverified)`:** the diode's reverse leakage at −55 °C against the **100 µW** night
   anchor (ADR-036). 3 diodes/wing × 4 = **12** diodes leaking in the dark; ADR-054 already
   carries the equivalent question for the hub diodes and it is not measured.

---

## 5. Mass and size — stated, because this adds a board back

ADR-130 retired the full-area FR4 carrier (20.26 g/wing) in favour of foam (0.653 g carrier).
**This record does not bring that back**, and the first layout attempt proved how easy it
would be to do so by accident.

### 5.1 The rejected first draft — a full cell-COURT board

Laying the board out as a plate big enough for all three cells (ADR-049's "2 rows, 2+1"
court) gives:

```
83.8 x 159.1 mm = 133.3 cm2 of 0.4 mm FR4 = 12.04 g per wing = 48.2 g for four
```

**48 g is more than the entire ~42 g corrected payload.** The operator asked for a
**small** board; that is not one. Recorded because the arithmetic is the argument: the
cell court cannot be shrunk (a cell is 78.55 x 38.90 mm), so a *court-sized* board is
unaffordable by construction.

### 5.2 The board as built — a SPINE

The board carries **only copper**: the 4-pad tab, 3 diode footprints and 6 cell-end lands.
**The cell bodies rest on the XPS foam**, which is the airframe (ADR-117), and each cell's
two ends land on the spine (ADR-052 end-mount). That is exactly the split ADR-130 D1
describes — one small interconnect board, no full-area carrier.

| Item | Value | Basis |
|---|---|---|
| Board outline | **130.0 × 11.0 mm**, 0.4 mm FR4 | `build_wing_interconnect.py` |
| Board area | **14.3 cm²** | 130 × 11 mm |
| FR4 0.4 mm | **1.29 g per wing**, **5.16 g for four** | 90.28 mg/cm² (ADR-063 §5) |
| 3 × SS24 (SMA) | **≈ 0.04 g** | SMA body ≈ 13 mg typical; `TODO(unverified)` — weigh one |
| **Delta over the bare insert** | **≈ +1.3 g per wing, +5.2 g for four** | vs. the ADR-131 bare strip |
| Wing total, EPS 3 mm single-sided | **5.249 → ≈ 6.5 g** | ADR-130 §2 table + this delta |

**Exact outline and geometry are `TODO`-frozen by the layout, not by this record** — the
builder is the source of truth for the numbers above.

**Consequence for the release:** the keeper force scales with wing mass (ADR-131 §3). At
≈6.5 g the ×1.5 lower bound moves from **772 mN → ≈956 mN**. Re-derive it once the assembled
wing is weighed — do not size the keeper to the pre-board number.

---

## 6. What this record does NOT do

- **No schematic, no `.kicad_pcb`, no BOM freeze, no order.** The board is specified, not laid out.
- **No window/tab geometry frozen** — the layout owns it, gated by ADR-030's placement gate and
  AGENTS.md §19–21 (schematic → ERC 0 → netlist → board → DRC 0 → gates → render).
- **No change to ADR-054's topology, to `D_BP1..4`, or to the cut ladder.**
- **No RF change** — see ADR-133 for `RF_FEED`.

## 7. For future sessions

- **Both bypass layers are required.** Per-cell on this board (cells); per-interface `D_BP1..4`
  on the hub (cuts). Neither replaces the other.
- **A reversed SS24 is invisible to a string check.** Silk polarity + a first-article
  reverse-bias continuity test on every wing is mandatory.
- **The board is a SPINE, not a carrier.** Windows under each cell centre, so ADR-052's
  no-face-bond rule survives; do not "simplify" it into a solid plate.
- **Re-derive the keeper force** after weighing the assembled wing (ADR-131 §3).

---

*Accepted by operator 2026-10-25. Design only: no board, BOM, order or fab authorisation.*

> **CORRECTION 2026-11-10 — the size in the paragraph above is STALE.** Measured from the board
> (`wing_interconnect_v1.kicad_pcb`, `Edge.Cuts` centreline): **34.60 × 20.00 mm**, not 44 × 20.
> The generator derives the width from the pad extents — *"pads end at x=33.00, +1.6 edge = 34.6"* —
> because the original 44 mm outline left **11 mm of the right-hand side with no copper at all**.
> Mass therefore improves: **0.62 g/wing, 2.50 g for four** (was 0.79 / 3.18).
> The BOARD is correct; this record's figure is stale. Fab bundle and full derivation:
> `docs/fab/wing-interconnect-order/README.md`. Everything else in this record stands.
