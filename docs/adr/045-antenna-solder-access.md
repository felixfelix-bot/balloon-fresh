# ADR-045 — Antenna solder-access constraint (hand-soldered RF parts must be reachable from outside the module body)

- Status: **Proposed.** The *decision* this ADR records is the operator's standing
  requirement (quoted below), but the *text* has **not been accepted by a human**, so it
  does not say Accepted. Several pin attributions are marked **TODO(unverified)** and are
  named as open questions rather than asserted.
- Date: 2026-10-07
- Decision owner: Felix (operator)
- Author: worker-ant (Hermes subagent), recording an operator instruction as a decision
  record and adding the mechanical enforcement tool it implies.
- Related records in this repo (read as they exist today — see the numbering note):
  - `docs/adr/029-dual-band-flight-board.md` (ADR-029, v9 tri-band board + four RF parts;
    D3 = all four feeds are U.FL pigtails)
  - `docs/adr/029-f33-sx1280-pin-plan.md` (ADR-029 pin plan; **duplicate 029 number**)
  - `docs/adr/034-radio-band-split-433-tx-2g4-rx.md` (ADR-034, 433 MHz TX / 2.4 GHz RX on
    two separate LR2021 parts)
  - `docs/adr/040-v9-radio-site-optionality.md` (ADR-040, Site A LP-or-HP + Site B LP-only,
    both DNP by default, operator hand-solders)
  - `docs/V9-RADIO-SITE-MATRIX.md` (per-config population/GPIO/rail/regulatory matrix)
  - `docs/f33-module/F33-LANDPATTERN-VERIFICATION.md` (the land-pattern verification work;
    search key `F33-LANDPATTERN-VERIFICATION` — verdict **FAIL, 0 of 18 pads**, fixed by
    commit `d5a2e47` on `main`)
- Related artefacts in this repo:
  `docs/f33-module/LoRa2021F33-2G4-datasheet-v1.1.pdf` (G-NiceRF, Rev 1.1, §7 pin table),
  `docs/assets/lr2021/LoRa2021-Module-Datasheet-V1.3.pdf` (G-NiceRF bare `LoRa2021`, §7
  pin table),
  `tracker/hardware/hub_board_diy/custom.pretty/LoRa2021F33_2G4.kicad_mod`,
  `tracker/hardware/hub_board_diy/custom.pretty/LoRa2021_Castellated.kicad_mod`,
  `tracker/hardware/tools/antenna_access_check.py` (the enforcement tool this ADR mandates).

> **Numbering note (concurrent work, stated not resolved).** Two ADR numbers collide on
> today's tree: `029-dual-band-flight-board.md` and `029-f33-sx1280-pin-plan.md`. Another
> worker is **renumbering ADR files concurrently**, so the numbers cited above are the
> numbers-as-of-today; they may move. This file takes **045** because it is the
> next-free number on the v9 consolidation line at base `b1af5c9` (highest committed is
> `043-cold-qualification-heating.md`; `044` is not present on this branch). If the
> concurrent renumbering has moved `045`, this ADR must be renumbered with it — it is a
> reference-by-path document, not a reference-by-number one.
>
> **Scope constraint (concurrent work).** Three workers are active: two edit other ADR
> files (renumbering) and the v9 schematic generator. **This ADR touches none of those
> files**; it is a new file plus two new tools.

---

## Context

The v9 board (ADR-029 / ADR-034 / ADR-040) carries **four RF parts plus every U.FL
connector**:

| # | Role | Part | Band | Site |
|---|---|---|---|---|
| 1 | Long-range TX | `LoRa2021F33-2G4` (HP) | 433 MHz | Site A (variant) |
| 2 | Link RX | bare `LoRa2021` (LP, castellated) | 2.4 GHz | Site A (variant) **or** Site B |
| 3 | Ranging | `SX1280` | 2.4 GHz | dedicated |
| 4 | Position / time | `MAX-M10S` | GNSS L1 | dedicated |

Every one of these is fitted **by hand**, by the operator. ADR-040 D1/D2 record this as the
load-bearing premise of the whole site-optionality decision ("we are anyway soldering the
radios on manually ourselves"), and the matrix states it again ("Both sites **DNP by
default**; the operator hand-solders"). ADR-029 D3 then routes all four feeds off-board
through **U.FL pigtails**, so the U.FL connectors are hand-soldered parts too.

A hand-soldered part is only buildable if a **soldering iron can physically reach the pad**.
That is a mechanical constraint on placement and rotation — and, until now, it was not
recorded anywhere and not enforced by anything. The v8i/v8j boards were laid out without it;
ADR-030's deterministic placement gate does not model it; and the F33 land-pattern failure
(`F33-LANDPATTERN-VERIFICATION`, fixed in `d5a2e47`) showed that a footprint can be
self-consistent, DRC-clean and still un-buildable by hand.

### The operator requirement, verbatim

> "the second LR2021 module must be placed such that the antennas can be soldered to their
> respective pins without touching the board that the LR2021 is attached to."

### Precise interpretation recorded here

The phrase "without touching the board that the LR2021 is attached to" means the iron tip
must approach the antenna pad **from outside the module body** and land on copper that is
exposed on the module perimeter — it must not have to reach *under* the module body, and
nothing else on the board may sit in the approach path. Read strictly, the constraint is:

> **Every antenna-port pad of BOTH LoRa2021 modules (the `LoRa2021F33-2G4` on 433 MHz and
> the bare castellated `LoRa2021` on 2.4 GHz) must be reachable with a soldering iron from
> OUTSIDE the module body.** Concretely, the pad must be a **castellated / edge pad on the
> module perimeter**; it must **not sit underneath the module body**; and it must have
> **clear access**: no other footprint, courtyard, tall component or copper keep-out may
> block the approach path to that pad, and there must be **enough clearance** from the board
> edge or adjacent parts to land a soldering tip on it.

The same rule applies to the **`SX1280`** and to the **GNSS module's antenna feed**, and to
**every U.FL connector**.

This interpretation is recorded as a *decision*, not left to each layout pass, because
ADR-029's operator standing rule is "ADR first" and because the constraint is cheap to
satisfy at placement time and expensive to discover at build time.

---

## Decision

### D1 — Which pins are the antenna ports (verified from the datasheets in-repo, by text extraction)

Verification method: **`pdftotext -layout`, not a vision model** (the F33 land-pattern
verification had to fall back on OCR because `vision_analyze` returned HTTP 503; that
failure mode is why this ADR pins its pin numbers with text extraction). Commands and the
observed §7 rows are recorded in PROGRESS.md/REPORT.md.

| Module | Antenna pin | Pin name (datasheet) | Band | Source (dated 2026-10-07) | Status |
|---|---|---|---|---|---|
| `LoRa2021F33-2G4` | **9** | `ANT` — "Sub-GHz Antenna Port, External 50Ω Antenna" | sub-GHz (433 MHz on v9) | `docs/f33-module/LoRa2021F33-2G4-datasheet-v1.1.pdf` §7 pin definition, p.6 | **VERIFIED** |
| `LoRa2021F33-2G4` | **10** | `ANT-2G4` — "2.4 GHz Antenna Port, External 50Ω Antenna" | 2.4 GHz | same, §7 | **VERIFIED** |
| bare `LoRa2021` (castellated) | **9** | `ANTA` / `ANT` — "@sub-GHz band antenna interface, external 50-ohm antenna" | sub-GHz | `docs/assets/lr2021/LoRa2021-Module-Datasheet-V1.3.pdf` §7, p.6 | **VERIFIED** |
| bare `LoRa2021` (castellated) | **10** | `2.4/S_ANTA` — "2.4G and S band antenna interface, external 50-ohm antenna" | 2.4 GHz | same, §7 | **VERIFIED** |
| `SX1280` | **TODO(unverified)** | — | 2.4 GHz | **no SX1280 datasheet is committed in this repo** | **TODO(unverified)** |
| `MAX-M10S` (GNSS) | **TODO(unverified)** | — | GNSS L1 | **no MAX-M10S datasheet is committed in this repo** (the board's footprint is a custom `ublox_MAX` with 18 pads) | **TODO(unverified)** |
| every U.FL connector | **1** (centre signal conductor) | — | — | footprint `U.FL_Molex_MCRF_73412-0110_Vertical`; pad `1` is the centre pin, pads `2` are the three ground/body pads | **VERIFIED (footprint-level, not datasheet)** |

#### Open questions for the two TODO(unverified) rows — exact questions, asked

- **SX1280 antenna port, exact open question:** *which pad/pin of the SX1280 module (or
  QFN land) is the RF input/output (`RFIO`), and is it a castellated/edge pad or an
  underside thermal-pad-adjacent pin?* Needs the SX1280 module datasheet or the vendor land
  file, committed to this repo, before the SX1280's antenna pad can be gated. The checker
  will exit 2 (CANNOT-VERIFY) on an SX1280 footprint until this is answered.
- **MAX-M10S / GNSS antenna feed, exact open question:** *which pad of the board's
  `ublox_MAX` footprint is the GNSS RF input (`RF_IN`)?* Needs the u-blox MAX-M10S
  datasheet or the footprint's pin-to-function map, committed to this repo. The checker
  will exit 2 (CANNOT-VERIFY) on the GNSS footprint until answered.

Both are recorded as **prerequisites for the v9 placement step** (D6), not as silent
assumptions.

### D2 — The access rule as a measurable predicate

For an antenna-port pad `P` of RF footprint `F` on board `B`, with `body(F)` the module
body rectangle and `courtyard(G)` the courtyard polygon of any other footprint `G`:

> **ACCESS(P, F, B) :=
>   (a) `edge(P, F)` — the copper bbox of `P` reaches or crosses an edge of `body(F)`
>       (equivalently: `P` is NOT strictly inside `body(F)` by more than the tolerance
>       `ε` = 0.05 mm), so the pad is on the perimeter and not under the module body; AND
>   (b) `clear(P, B)` — `min_{G ≠ F} dist(copper_bbox(P), courtyard(G)) ≥ G_min`,
>       with `G_min` a configurable minimum access gap, default **1.0 mm**.**

Definitions used by the tool (`tracker/hardware/tools/antenna_access_check.py`):

- `copper_bbox(P)` — the pad's copper bounding rectangle in absolute board millimetres
  (from `pcbnew` `PAD::GetBoundingBox()`).
- `body(F)` — the footprint body rectangle, derived deterministically in this order:
  (1) bounding box of `F.Fab`/`B.Fab` graphics; (2) failing that, the union of the
  footprint's own pad copper bboxes; (3) failing that, the courtyard bbox. The source used
  is reported per footprint.
- `courtyard(G)` — `pcbnew` `FOOTPRINT::GetCourtyard(F_CrtYd|B_CrtYd)`; failing that, the
  footprint's `F.CrtYd`/`B.CrtYd` shapes; failing that, `body(G)`.
- `dist(...)` — minimum Euclidean distance between two convex polygons (pad rectangle vs
  courtyard polygon), computed edge-to-edge; a pad whose centre is inside the other
  courtyard reports a gap of `0` (overlap ⇒ occluded).
- `ε` = 0.05 mm is the castellated-pad-centre-on-the-body-edge tolerance.

**Failure conditions (the gate):**

- **(i) Occluded** — `edge(P,F)` is false: the antenna pad's copper does not reach the
  module perimeter, so it is under the body ⇒ **FAIL**.
- **(ii) Blocked approach / insufficient clearance** — `clear(P,B)` is false
  (`gap < G_min`) ⇒ **FAIL**.
- **(iii) Cannot verify** — the module is an RF part but its antenna pin set is not known
  (SX1280, GNSS) or the footprint has no readable geometry ⇒ **CANNOT-VERIFY**.

The tool is **fail-closed**: (i) or (ii) ⇒ exit 1; (iii) with no (i)/(ii) ⇒ exit 2; all
antenna ports pass and nothing is unverified ⇒ exit 0. A definite FAIL outranks
CANNOT-VERIFY.

> **Honest limit of the predicate.** `courtyard(G)` is a *proxy* for the approach path. It
> does not model the height of a neighbour (a tall electrolytic next to a pad blocks a
> side-entry iron badly; a 0402 resistor does not), nor a copper keep-out that is not a
> footprint, nor the board edge itself. The tool is a *necessary* gate, not a *sufficient*
> one: a PASS means "no footprint courtyard is within `G_min` and the pad is castellated",
> it does **not** mean "an iron fits". The human build check (D5) is the sufficient one.

### D3 — What placement and rotation satisfies it, per part

Derived from the **measured** pad geometry (pcbnew 9.0.8, this repo, 2026-10-07):

**Part 1 — `LoRa2021F33-2G4` (433 MHz TX).** Corrected land pattern (`d5a2e47`): 18 pads,
2.0 × 1.0 mm, pitch 3.9289 mm, rows at y = ±10.5 mm on the 39 mm edges. Antenna pins 9 and
10 are **adjacent on the same `+y` long edge**, at the `+x` end:
`pin 9 @ (+15.7156, +10.5)`, `pin 10 @ (+11.7867, +10.5)`, body 39 × 21 mm.
**Satisfying placement/rotation:** the module's `+y` long edge must face **outward** (to the
nearest board edge or to open board area), with **≥ `G_min` (1.0 mm) clear** along that whole
edge, and the `+x` corner (where both antenna pads sit) must be the corner nearest that free
zone. The other three edges may be crowded. **A rotation that points the `+y` edge at the
board centre, or at another footprint/mounting hole, violates the rule.**

**Part 2 — bare `LoRa2021` (castellated, 2.4 GHz RX).** 18 pads, 2.0 × 0.7 mm, pitch
1.29 mm, body 19.81 × 14.98 mm; pads at x = ±9.905 mm. Antenna pins 9 and 10 are at the
**same `−y` end but on opposite edges**: `pin 9 @ (−9.905, −5.16)`, `pin 10 @ (+9.905,
−5.16)`.
**Satisfying placement/rotation:** the module's `−y` end must face **outward**, and **both**
the `−x` edge and the `+x` edge near that end need `≥ G_min` clear — i.e. the free zone is
an **end/corner**, not a single edge. This is stricter than the F33 case: on the F33 both
antenna pads share one edge, on the bare module they do not. The bare module may sit at
either Site A or Site B (ADR-040); the rule applies at whichever site carries it.

**Part 3 — `SX1280`.** Pin set **TODO(unverified)** (D1). **Recorded requirement, pending
the datasheet:** the RFID/RFIO pad must be a perimeter pad with `≥ G_min` clear approach;
if the chosen SX1280 is a bare QFN with an underside RF pad, **the flat-placement rule
cannot be satisfied** and one of the D4 options must be used. Until verified, the checker
returns CANNOT-VERIFY, not PASS.

**Part 4 — `MAX-M10S` GNSS antenna feed.** Pad number **TODO(unverified)** (D1).
**Recorded requirement:** the GNSS RF feed pad must be a perimeter pad with `≥ G_min` clear
approach, and per ADR-029 §2(d) it must also sit in the **sky-facing-edge** GNSS keep-out
zone (no TX trace, no via ring there). The two requirements are compatible: both push the
GNSS feed to the `+Y` edge with clearance. Until the pad number is verified, the checker
returns CANNOT-VERIFY.

**U.FL connectors (all feeds, per ADR-029 D3).** Each U.FL's **centre signal pad (pad 1)**
must have `≥ G_min` clear approach to the neighbouring footprints' courtyards. The U.FL is
a top-side connector soldered from above, so the *castellated-perimeter* limb of the
predicate is **inapplicable** to it (its centre pad is central by construction); the tool
reports the edge test for information but gates only the clearance limb. The ADR-029 D3
board-edge routing (GNSS `+Y`, sub-GHz `−Y`, 2.4 GHz side edge, no co-polarised 2.4 GHz
feeds within λ/2 ≈ 6 cm) is unchanged and **in addition to** this rule.

### D4 — Option set when a pad cannot be reached on a flat placement

Recorded as a decision, with the cost each option forces, so the option is chosen on the
record and not improvised in layout.

| Option | What it does | What it forces |
|---|---|---|
| **O-1 — antenna edge to the board edge (preferred)** | Rotate/translate so the module edge carrying the antenna pads faces the nearest board edge, antenna edge parallel to (or perpendicular to, per part) that edge, all `≥ G_min`. | **Re-freeze** the placement (new board-edge-adjacent coordinates) for that part; the ADR-030 placement hash changes; re-run DRC. **No re-route** beyond the affected net's escape; the feed trace to the U.FL gets shorter and straighter, which is desirable. |
| **O-2 — rotate the module 90°** | Turn the part so a *different* edge/corner faces the free zone (relevant to the bare `LoRa2021`, whose two antenna pads are on opposite edges at one end). | **Re-freeze** (rotation is part of the placement hash); **re-route** every non-antenna connection (SPI + control) because the pin ring moves; RF feed orientation changes, so the D3 board-edge assignment must be re-checked. |
| **O-3 — raise the module on a standoff** | Lift the module off the board so an iron can approach from the side/under the raised body. | **Re-freeze**; **cannot be done with castellated SMD reflow** — the module must be hand-wired or the footprint changed to a socketed/wired variant; adds mass (adverse for a balloon: every gram matters) and a new mechanical item. **Recorded as last resort only.** This option is also what a **QFN-style underside RF pad** (possible SX1280 case, D1) would force. |
| **O-4 — move the blocking neighbour** | Relocate the offending footprint/keep-out instead of the module. | **Re-freeze** for *that* neighbour; **re-route** its nets. Cheapest when the neighbour is small and low-value; costly when it is the GNSS or a connector. |
| **O-5 — delete the part from this population** | e.g. drop the bare module to Site B only, or leave the SX1280 unpopulated (DNP, as ADR-040 already allows by default). | **Non-solution for the default population** — ADR-040 D2 makes the two-LP configuration the default, so removing an LP site removes the default's function. Recorded for completeness, **not recommended**. |

**Recommendation.** **O-1 first** (antenna edge to the board edge). It has the lowest total
cost — one re-freeze, no re-route, and it *improves* the RF feed by shortening it and
pointing it off-board (which is exactly what ADR-029 D3 wants). If `O-1` cannot be met for
the bare `LoRa2021` (antennas on opposite edges at one end) **use O-2 for that part only**,
and accept the SPI re-route. **O-3 is last resort** and must be recorded in the ADR set as
a mass/mechanical change, not adopted silently.

### D5 — Enforcement: a deterministic fail-closed tool, and a human build check

The rule is enforced mechanically by
**`tracker/hardware/tools/antenna_access_check.py`** (new, this ADR):

- input: one or more `.kicad_pcb` paths; optional reference-designator restriction;
  optional `--min-gap MM` (default 1.0); optional per-reference antenna-pin override.
- output: for **every pad of every RF footprint** — pad number, whether it is an
  edge/castellated pad, and the nearest other footprint courtyard + the gap in mm.
- exit codes: **0** all antenna ports pass; **1** an antenna-port pad is occluded or its gap
  `< G_min`; **2** the board cannot be read, or the footprint cannot be identified (no
  geometry, or an RF part with an unknown antenna pin set).
- it is deterministic (no LLM, no network; the only dependency is the in-tree `pcbnew`).
- it is **fail-closed**: an unreadable footprint or an unknown antenna pin set is
  CANNOT-VERIFY, never a silent PASS.

The tool is a **necessary** gate; it is not sufficient (D2 limit). Therefore the build-time
check stays: the operator visually confirms, on the first assembled v9 board, that an iron
reaches every listed pad without touching the module body. That check is the authority the
tool approximates.

### D6 — This constraint is an INPUT to the v9 placement step (a violating placement is rejected)

**Decision.** The access predicate of D2 is a **hard input to the v9 placement step**
(ADR-030's deterministic placement gate, and any manual placement that precedes it). A
candidate placement in which any antenna-port pad violates `edge(P,F)` or `clear(P,B)` is
**REJECTED** — it is not "noted as a risk", it does not get merged, and it does not proceed
to routing. The placement step must:

1. Run `antenna_access_check.py` on the candidate `.kicad_pcb`; **exit 0 is required**.
2. Treat exit 1 as a placement rejection (the offender is named in the tool output).
3. Treat exit 2 as an **incomplete placement**, not a pass: the SX1280/GNSS antenna pin
   attribution (D1) must be resolved, added to the tool's pin map, and re-run.
4. Record the tool's output (per-pad table + exit code) alongside the placement, so the
   gate is auditable — the same "evidence, not assertion" stance ADR-030 and
   `F33-LANDPATTERN-VERIFICATION` take.

This ADR therefore adds a **new precondition** to the v9 placement step: *the antenna
solder-access gate must pass before placement is frozen.* It does not modify ADR-030's
mechanism; it adds one required check to it.

---

## Consequences

- **Placement is no longer free at the radio sites.** The two LR2021 sites (ADR-040) and the
  SX1280/GNSS must each be oriented with their antenna edge to a free zone. On a 55 × 45 mm
  board carrying a 39 × 21 mm module, this is a real constraint, not a formality — it
  competes with ADR-029's GNSS keep-out and D3's board-edge U.FL assignment, and it must be
  reconciled with them at placement time.
- **The v8i/v8j boards are not retro-gated.** They carry a bare `LoRa2021` (U2) and were laid
  out before this rule. This ADR does not assert they pass; the tool's real output on them is
  recorded in `REPORT.md`.
- **The SX1280 and GNSS rows are open** until their datasheets are committed (D1). Until
  then the tool is CANNOT-VERIFY for those two parts, and the v9 placement cannot be fully
  frozen (D6 rule 3).
- **Mass/mechanical options (O-3) are not free.** Raising a module adds an item and mass;
  recorded, not recommended.

## What would falsify this

- A physical build showing a flat-placed module whose antenna pad the iron *cannot* reach
  even though the D2 predicate passed — would prove the predicate insufficient (expected:
  the courtyard proxy ignores neighbour height) and force the predicate to model height.
- A verified SX1280 or GNSS datasheet showing the antenna port is an **underside** pad —
  would make the flat placement rule unsatisfiable for that part and make O-3 mandatory for
  it, not optional.
- Evidence that ADR-040's default should be a *single* radio rather than two LP sites — the
  constraint would then apply to fewer parts, but the rule itself would be unchanged.
