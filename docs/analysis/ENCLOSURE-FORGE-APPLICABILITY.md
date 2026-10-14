# enclosure-forge → balloon ground station — applicability assessment

> **STATUS: ASSESSMENT — NOT A DECISION RECORD.** This is an analysis in
> `docs/analysis/`. It authorises no order, no fab freeze, no board change and no
> BOM change. It answers the operator's question: *what can we learn from
> `Amperstrand/enclosure-forge`, and can it make the base-station cases and the
> antenna tracker?* Recommendations are marked **REC** and require operator
> approval (PLAN GATE) before any card is scheduled.

| Field | Value |
|---|---|
| Date | 2026-10-11 |
| Base | `origin/main` @ `3020f0b` |
| Author | Hermes Agent (manager), for the operator |
| Subject repo | `https://github.com/Amperstrand/enclosure-forge` — cloned `--depth 1`, HEAD `0925` series, 512 KB, 41 KB of docs read in full |
| Repo-side rows referenced | `docs/analysis/GAP-TRACKING-CHECKLIST.md` (main), `docs/BASE-STATION-BOARD-CHECKLIST.md` (branch `design/level-control-architecture`), `docs/analysis/positioner-lowcost-3dprinted.md` (branch `design/positioner-lowcost`) |

Every claim below is **CITED** (repo path + line, or the forge file it came from),
**COMPUTED** (arithmetic shown), a labelled **ESTIMATE**, or an explicit
**`TODO(unverified)`**. Nothing is presented as sourced that was not fetched.

---

## 0. Answer first

**Learn: a lot — the *doctrine* transfers, and it is better than anything we currently run for mechanical work.**

**Base station: yes, it can build those cases — but it is blocked upstream by a decision we have not made (`MECH-01`), and the block is a *feature*, not a bug: the pipeline's first stage has nothing to measure until the split is chosen.**

**Antenna tracker: partly, and the honest split matters.** `ADR-077` already decided *print the structure, buy the gearing*. The printed structure is exactly enclosure-forge's class of work. But **enclosure-forge has no structural gate** — its only pass criterion is *zero unexpected common volume*. Adopt it for the positioner unmodified and you get **green booleans on a 4 m wind sail**, which is the failure mode its own `SKILL.md` names: *"Shipping a design change with green booleans but unverified semantics."* Use it for the fit/manufacturing geometry; the load path needs a check class it does not have — and its own doctrine tells you how to add one.

**And it exposes a gap our own gap analysis does not carry: there is no mechanical-enclosure workstream row at all.** The masthead enclosure appears exactly once, as BOM row 18, marked `CLOSED (mechanical)` — which is a *deferral*, not a closure.

---

## 1. What enclosure-forge actually is

Not a CAD library. A **staged pipeline with machine-readable gates, a prompt
library, and a cross-project failure catalog**, wrapping CadQuery/OCCT.

From `SKILL.md` — two rules govern everything:

1. **"No dimension is typed from memory."** Every geometric claim about the board comes from
   measured/parsed reference files, tagged with a provenance class. *"Design decisions are
   literals; measurements are not."*
2. **"The boolean gate is the design review."** A stage is done when its machine-readable check
   passes — zero unexpected common volume against real reference geometry. **"Renders illustrate;
   they never prove."**

Stages **S0–S9**: intake (pin the rev) → measure → **orient (device semantics)** → envelopes →
parameters (one provenance-tagged file) → build → **validate (boolean gate)** → render + artifact
proofs → **coupon print** → lessons sync. *"A stage without a green gate is not done — including
'the renders look fine'."*

Supporting corpus: `references/prompts.md` (P1–P16, versioned like data), `references/validation.md`
(the check taxonomy), `references/lessons.md` (48+ cross-project failures, stage-tagged),
`references/frontends.md`, `references/toolchain.md`, `experiments/` (prompt A/B harness with an
eval schema; dspy compilation planned).

**Pass gate, always the same:** zero unexpected common volume (mm³) against the real reference
geometry, written to `analysis/interference_report.json`, CI-red on fail. Intended contacts
(support pads, retention lips, snap fins) are *subtracted and named*. From `validation.md`:
**"A check that can't name its intended contacts isn't a check."**

## 2. What it has proven (4 targets, `references/boards.md`)

| Target | Front-end | What it proved |
|---|---|---|
| `lilygo-a7670-simhat-carrier` | **manufacturer STEP/DXF** | **dual-board carrier for two bought modules**, snap-cage for a **hole-less** board, screw mount for the other, antenna side-tray chosen by elimination probes, 35+28 boolean checks in CI, **printed**, v0.3 print feedback folded back |
| `nucula-enclosure` | **KiCad `.kicad_pcb`** | enclosure family V0–V3, 57 checks; *the orient stage exists because its screen window shipped portrait with every boolean green*; board-rev drift (connector swap) became P11 |
| `rp2040-devboard-enclosure` | KiCad | minimal dev-board case, 7/7; first harness run |
| `easyduino-esp32-enclosure` | KiCad | **first zero-hole board** — added a *pad-and-rail retention class* (no holes → rails + pads + antenna-side rim) |

**Target #1 is the precedent that matters most for us.** It is a **carrier for
modules that were bought, with no board of our own** — which is precisely the
base station's state today.

## 3. The two transfers, separated

**Transfer A — the doctrine (applies broadly, including to our PCB work).**

| Doctrine | What we already got wrong the same way |
|---|---|
| "No dimension is typed from memory" + provenance classes | `tracker/hardware/enclosure/balloon_dev_case.scad` carries **both classes mixed with no tags**: `lr_w = 24.05; // measured` next to `rp_w = 21.5;` / `rp_l = 17.8;` (unmarked, and the README says *"RP2040 board (~21.5 x 17.8mm — **ADJUST in .scad if different**)"*) and `esp_w = 22.52` (0.02 mm precision on a 22.5 mm nominal part). No envelope was ever extracted; nothing is validated. |
| **"Renders are never evidence"** | The round-2 gap audit found `KICAD9_3DMODEL_DIR` unset → `kicad-cli pcb render` emits **substrate + copper + silkscreen only, no component bodies**; a render-based "parts look well placed" judgement is really a judgement about copper and courtyards. Independent convergence on the same rule. |
| **"A check that can't name its intended contacts isn't a check"** | **`PCB-01`** — the wing's "0 overlap violations" gate is **vacuous** because 12/12 footprints carry no courtyard (hub: 39/39 carry one). A gate that cannot fail is not a gate. |
| Artifact-level proof for semantic properties | Our 3D/render pipeline has no artifact-level proof of anything; the wing render on `main` shows 0 of 12 modelled footprints. |
| **S8 coupon-first** — the coupon calls the *same* builder functions as production | Mirrors our one-geometry-source-of-truth rule (cells defined in `build_wing_v9.py`, never hand-edited into the `.kicad_pcb`). |
| **S9 lessons-sync** to a cross-project catalog | We have lessons, but scattered across session notes and ADRs, not a stage-tagged catalog a worker can load. |
| **P11 board-rev drift** | We live this: v7→v9, four hub/wing generations, and the connector/env drift that kills wire routes. |
| `lessons.md` #15: ecosystem standards beat ad-hoc fixtures (adopt-a-library criteria: spec fidelity provable, dependency audited, replaces >100 lines) | Directly applicable to our Gridfinity/pole-mount/rack choices. |

**Transfer B — the tooling (boolean volume checks).** Applies to *interference*,
mating, retention and antenna-law geometry. It does **not** apply to structural
strength, torque, stiffness, backlash or wind survival, because those are not
volume-overlap predicates.

## 4. Base station — can enclosure-forge build those cases?

**Yes — and it is the only thing in our stack that produces a *boolean-validated fit*. The words
"fit" and "print-ready" are not synonyms, and this assessment was wrong to blur them (a consultant
review caught it): the boolean gate proves **volume non-overlap only**. It says nothing about
O-ring compression, IP rating, thermal soak, UV, heat-set insert pull-out, gland torque or cable
fatigue — and a weatherproof case lives or dies on exactly those. Boolean pass is **necessary, not
sufficient** (see `REC-ENV-1`).

**And it cannot start where the gap analysis implies it would.**

The relevant rows, all from `GAP-TRACKING-CHECKLIST.md` (main) unless stated:

- **`BS-01`** — *"The base-station board does not exist."* No schematic, netlist or gerber on any
  ref; `docs/BASE-STATION-BOARD-CHECKLIST.md` declares itself *"a document, NOT a KiCad layout."*
  Blocking: **yes**. → forge **S1 (measure)** has **no repo-local board to measure**.
- **`MECH-01`** — *"Masthead-vs-shack board-split decision NOT made."* The masthead LNA, DSA, log
  detector, ADC/MCU and bias network all want to be **at the masthead**; the control PC wants to be
  **indoors**. ROUND2 §6: *"a decision the current single-board framing does not express, and one
  that **must be made before the board is designed**."* Blocking: **yes**.
- **`BS-03`** — five required BOM rows carry no price, one of which is **row 18**.
- **Row 18 (mechanical / mast-head mounting / enclosure)** —
  `"DNP on PCBA; external weatherproof enclosure + mast clamp"`, status **`CLOSED (mechanical)`**,
  note: *"Mechanical selection remains under ADR-076/077/078. This row is explicitly outside the
  PCBA freeze."* `ADR-076/077/078` are **UNMERGED** (`BS-07`, `BS-06`).
- **`BS-06`** — the whole ground-station design is unmerged: ~16 `design/*` branches, ADRs 071…084
  exist **only on branches**; `main` carries the flight-board ADR line only (to 065).

**The consequence, stated plainly:** designing the masthead case *now* would be
premature — not because the forge is wrong for it, but because **`MECH-01` decides
how many enclosures exist and what is in each one.** Cutting geometry before that
is exactly the "green booleans, unverified semantics" failure. The forge's own
**S2 (orient)** and **S3 (envelopes)** are the right instruments to *make* the
split concrete — you cannot boolean-test a masthead stack that has not been
chosen.

**What IS doable now, at zero design risk:** the forge's **STEP/DXF front-end**
was built for target #1's exact situation — a carrier for **bought** modules.
The base station's mechanically-known inventory is already listed in the BOM:
`ADL5240` (row 5), `PE43711`-class SMA DSA (row 6), `AD8318` (row 7), `RP2040`
(row 8), `Sirio SLP-17` (row 9), coax + N-male crimps (row 12), `ZFBT-4R2GW+`
bias tee (row 14), LiteVNA 62 (row 13), Red Pitaya + XR-613 (rows 15/16). Those
have *some* manufacturer documentation — **but "has documentation" is not "has usable STEP/DXF",
and I did not verify a single one: `TODO(unverified)`.** Several are eval boards or aliexpress SMA
modules that may publish only a PDF outline; `REC-GEO-1` below turns this into the measurement step
it should always have been.

**REC-BS-1** Run `MECH-01` as an enclosure-forge **S2/S3 exercise**, not a memo —
produce the masthead envelope set (LNA + DSA + log detector + bias tee + antenna
aperture + coax strain relief over the AZ/EL rotation range) and the shack
envelope set (RP2040 controller), each with its *named* checks planned. That
turns an open decision into a measured artifact, and it **removes one prerequisite of `BS-01` — it
does not unblock it.** (A consultant review caught this overclaim.) `MECH-01` is an
**electrical/RF/thermal/servicing** decision, not a geometric one: feedline NF, power and data
distribution, thermal path, lightning, and serviceability are not volume-overlap predicates. So the
exercise must be run as **two or three candidate splits**, each with its own S3 envelope set, plus an
RF/thermal/power trade table — the operator then decides with the trade table in hand.
**REC-BS-2** With the split chosen, build the masthead case from **module
STEP/DXF** (target-#1 path), then **P11 drift-check** it when `BS-01` lands.
**REC-BS-3** Carry the masthead enclosure as its **own tracked row** instead of
hiding it inside BOM row 18 — an enclosure with real gates (IP rating, aperture,
mast clamp torque, cable strain over rotation) is a deliverable, not a line item.

## 5. Antenna tracker — the honest boundary

The tracker is **two different things**, and only one of them is forge-shaped.

### 5a. The positioner (structure) — partly forge-shaped

`docs/analysis/positioner-lowcost-3dprinted.md` (branch `design/positioner-lowcost`) states the
decision in its own header: **"Print the structure, buy the worm gearing."** Its numbers:

- Right-sizing worth **4.00×** on everything mechanical (1.2 m → 0.6 m dish; wind force and swept
  area scale as D²), and it **doubles** the beamwidth (7.3° → 14.6°).
- Holding the 0.6 m dish at 20 m/s with a 2× safety factor needs **24.9 N·m** (balanced) to
  **49.9 N·m** (worst-case axis) at the output → **8.3:1 to 16.6:1** on a 3.0 N·m NEMA23.
- A 20:1 NMRV worm holds **40 N·m** and the vendor states it is **self-locking** — the reason a
  worm and not a spur/belt: *"a spur/belt drive at 20:1 back-drives in a 20 m/s gust and the dish
  walks."*
- **Printed gear teeth strip/creep** at those loads (`TODO(unverified)`: no accessible
  torque-per-tooth datasheet for PLA/PETG/ASA was found). The operator's own tracker is the field
  evidence.
- Positioner spec: *"**stiffness and holding torque, not speed**"*; *"backlash after a direction
  reversal is the thing that eats margin over a pass."*

**What the forge contributes:** the AZ/EL mounting plates, mast clamp, dish saddle, gearbox
bracket, LNA/DSA housing, connector bulkheads and cable-strain relief — all geometric, all
interference-checkable, all benefiting from a boolean gate against the **real** dish, mast and
gearbox solids instead of hand-typed numbers.

**What the forge cannot contribute:** torque, stiffness, backlash and wind survival. Its only pass
criterion is volume overlap. **Adopting it unmodified for the load path would produce green
booleans on a ~4 m boom that a 20 m/s gust can walk.** That is the honest boundary, and it is
exactly the class its own `SKILL.md` forbids shipping.

**But the doctrine generalises to a structural gate, and its own files say so:** `validation.md`
ships an extensible *"Check taxonomy (grow with the design)"* table, and its landscape note reads
*"neither tool's self-report is the last word… every defect that would have ruined a print was
found by a number, not a screenshot."* A structural check in the same shape — compute the moment,
assert margin ≥ 2×, write it to machine-readable JSON, fail CI — is a *natural extension*, not a
violation.

**REC-TRK-1** Use the forge for the positioner's **fit/manufacturing geometry**, with the
structural gate added as an explicit new check class (moment margin, backlash, stow-on-wind per
`ADR-076`), and say in the repo that the structural class is *ours*, not the forge's.
**REC-TRK-2** The tracker's **electronics** enclosure (`tracker/ground-station/`) is a straight
forge target — no structural gate needed.

**Blocker to respect:** `ADR-078 D7` requires a **measurement campaign before any dish/rotator
purchase** (`BS-07`: *"ADRs 076/077/078 … UNMERGED"*). So the positioner's *inputs* are not frozen.
Forge work on the positioner is **SOON**, not NOW.

Note the drive this must replace: the in-repo tracker firmware
(`tracker/ground-station/antenna-tracker/antenna_tracker_usb.ino`) drives **28BYJ-48** steppers
directly from IN1–IN4 half-step sequences — a toy-class drive, consistent with the "buy the
gearing" finding.

### 5b. The base station's antenna side (the apertures)

`ADR-071 D3` requires the 433 and 2.4 GHz antennas to be **boresighted on one positioner** (BOM
rows 1 and 9). Two apertures on one moving frame, plus a masthead LNA that must sit at the antenna
because *"feedline loss degrades NF 1:1 (0.76 dB/10 m at 433)"*, is a **single mechanical problem**
that the forge's S3 envelope pass is well suited to express.

## 6. Where it does NOT apply

- **The balloon payload boards** (`hub_board_v9`, `wing_board_v9`) — those are PCBs, not
  enclosures. The forge is the wrong tool. (`PCB-01` is a *gate* lesson, not a forge job.)
- **Load-bearing / torque-bearing structure** — see §5a. Boolean gates are not a structural
  analysis.
- **Anything gated on `S_crack`** (`PRE-02`, `PCPROG-0a`) and the **rib pitch** — the wing
  frame's unsupported-span number does not exist in the repo; the forge cannot measure a cell
  nobody has benchmarked. Same class of error as typing a dimension from memory.

## 7. The gap this exposes

Reading `GAP-TRACKING-CHECKLIST.md` in full (21 rows: `BS-01…07`, `PRE-01…04`, `MECH-01`,
`PCB-01/02`, `RF-01/02/03`, `LEGAL-01`, `SAFE-01`, `REL-01`, `TOOL-01`) there is **exactly one
`MECH` row** — `MECH-01`, the board split — and **no enclosure / mechanical-enclosure row
anywhere.** The masthead enclosure exists only as BOM row 18, `CLOSED (mechanical)`, €0, deferred
to unmerged ADRs.

So the honest framing is **not** "enclosure-forge fills gap row X". It is:
**adopting the forge creates a mechanical workstream the gap analysis does not currently
represent** — and that workstream gates the *physical* build of the base station in the same way
`BS-01` gates its electronics.

## 8. The highest-value first target is already in the repo (and it violates rule #1)

`tracker/hardware/enclosure/` holds a hand-written OpenSCAD waterproof case
(`balloon_dev_case.scad`, plus a `_big` variant and 12 STLs): 66.5 × 45.0 × 35.3 mm, O-ring groove
(2 mm cord), 4× M3 heat-set bosses, 3× cable glands, pole-mount tabs (2× M5), a **solar-panel
recess in the lid**, a **GPS antenna window**, and a Gore-Tex vent.

It is a good design made the way the forge exists to prevent:

- **Dimensions typed from memory** — `rp_w = 21.5; rp_l = 17.8;` are unmarked, and the README
  itself says *"RP2040 board (~21.5 x 17.8mm — **ADJUST in .scad if different**)"*.
- **No provenance classes** — measured and guessed numbers sit side by side with no tag.
- **No boolean gate** — nothing checks the boards against the cavity.
- **No coupon**, **no drift check**, **no artifact proof**.

It is also the **one thing that is already printed and field-relevant** — and it is **unblocked**
by every open decision above (`MECH-01`, `S_crack`, `ADR-078 D7` do not touch it).

**REC-FIRST (highest value / lowest risk)** Re-home `balloon_dev_case` onto the forge, running the
**full S0–S9 sequence** — no stage skipped (a consultant review caught the first draft skipping
S2/S3, which is precisely the documented failure mode of this method): **S0** (pin the rev) →
**S1** (extract the ESP32-C3 SuperMini, LR2021, RP2040 and MAX-M10S geometry into `analysis/*.json`,
provenance-tagged) → **S2** (orient: datum, up axis, which face is the lid, where the GPS window
and glands look — the case has a lid solar recess, a GPS window, 3 glands and pole tabs, all
orientation-sensitive) → **S3** (envelopes + removal kinematics against **all** solids) → **S4** (one
`parameters.py`, measured values loaded, *no magic numbers*) → **S5** (build) → **S6** (boolean
gate: seated interference, component clearance vs all solids, gland/envelope mates, antenna law
for the GPS window, watertight, deterministic rebuild) → **S7** (artifact proof) → **S8** (coupon,
fold the print back in) → **S9** (lessons). Keep the design intent; replace the numbers' *basis*.
Every dimension that was a guess becomes either an extracted value or a
`conservative_assumption` — visibly.

## 9. What I got wrong / what is not settled

- **`BS-02` vs BOM row 11 disagree.** The checklist carries `BS-02` as *"2.4 GHz uplink PA/FEM —
  MISSING ENTIRELY… TODO(unverified)"*, but `BASE-STATION-BOARD-CHECKLIST.md` row 11 reads
  **"DNP — no PA/FEM in v1 / CLOSED (D9)"**, citing `ADR-072 D4` (*"ISM uplink is
  attenuation-only"*). These are two different records of the same row, and **one of them is
  stale** — the checklist is dated 2026-10-10 and cites the BOM as its source. This needs
  reconciling; I have not established which is current. **`TODO(unverified)` on my side.**
- The forge's own `experiments/` harness is early (a dspy optimizer is *planned*, `README`); the
  A/B value it claims rests on a single LM-mode run. Treat the harness as an idea, not a product.
- I did **not** run any forge code. Availability of CadQuery/OCCT on this box is
  **`TODO(unverified)`** — verify before scheduling, because the toolchain file warns about OCC
  segfaults under constrained runners (`OMP_NUM_THREADS=1`).
- The masthead aperture design (water film over a 433 MHz window) is **not** addressed by the
  forge's antenna-law check beyond geometry; RF-through-water is a measurement, not a boolean.

## 10. Recommendations, dependency-ordered

| # | Recommendation | Urgency | Owner | Blocked by |
|---|---|---|---|---|
| **REC-TOOL-0** | **Prerequisite gate.** Install/pin CadQuery+OCCT, then run: one trivial boolean check, one deterministic rebuild (hash-identical STL), and one deliberate CI-fail case. **No other forge REC may start until this is green.** | **NOW** | AGENT | nothing |
| **REC-GEO-1** | Build the **geometry-availability matrix**: MPN · revision · source URL · file hash · license, for every module in the BOM. Every miss gets caliper measurement or a vendor STEP before any carrier is designed. Supersedes the unverified "those have manufacturer geometry" claim in §4. | **NOW** | AGENT→HUMAN | nothing |
| **REC-X-1** | Reconcile `BS-02` vs BOM row 11 (one of them is stale). **Hard predecessor of `REC-BS-1`** — otherwise the masthead envelope is built around the wrong electronics set. | **NOW** | AGENT | nothing |
| **REC-FIRST** | Re-home `balloon_dev_case` onto the forge — **full S0→S9, no stage skipped** | **NOW** | AGENT→HUMAN | REC-TOOL-0 |
| **REC-BS-1** | Run `MECH-01` as an S2/S3 exercise over **2–3 candidate splits** + an RF/thermal/power trade table. Removes ONE prerequisite of `BS-01`; the split stays an operator decision | **SOON** | AGENT then AGENT→HUMAN | REC-TOOL-0, REC-X-1, REC-GEO-1 |
| **REC-BS-2** | Masthead + shack cases from module STEP/DXF (target-#1 path); P11 drift-check when `BS-01` lands | **SOON** | AGENT | REC-BS-1 |
| **REC-BS-3** | Carry the masthead enclosure as a tracked row, not a BOM line item | **SOON** | AGENT | REC-BS-1 |
| **REC-ENV-1** | **Non-boolean gate set** required before any case is called weatherproof: O-ring compression, IP spray/immersion, heat-set insert pull-out, gland torque, thermal soak, UV, cable-strain cycling. Each a measured number or an explicit `MEASUREMENTS_NEEDED` | **SOON** | AGENT→HUMAN | REC-FIRST (first case to carry it) |
| **REC-REQ-1** | **File the enclosure requests upstream** as issues on `Amperstrand/enclosure-forge` — but only **after** each board is complete, so the issue carries the operator's real requirements. Draft → operator approval → post. See the requirements template in §12 | **SOON** | AGENT→HUMAN | each board's completion row (**hard gate, per the operator**) |
| **REC-X-2** | Apply *"a check that can't name its intended contacts isn't a check"* to `PCB-01`. **Staged, not immediate** — see below | **NOW** | AGENT | nothing |
| **REC-X-3** | Vendor the forge as a skill (`skill-vendoring`): **full 40-char SHA + tarball hash**, license check, docs/prompts read-only, executables in a no-network sandbox, human review before a worker consumes an external prompt | **SOON** | AGENT | REC-FIRST outcome |
| **REC-TRK-1** | Positioner fit/manufacturing geometry on the forge. **The structural check class is BLOCKED**: no load cases and no material allowables are measured yet | **DEFER** | AGENT→HUMAN | material characterization + `ADR-078 D7` campaign + merge of ADRs 076/077/078 |
| **REC-TRK-2** | Tracker electronics case (straight forge target) | **DEFER** | AGENT | REC-TRK-1 staging |

**`REC-X-2` staging (do not ship it fail-closed on day one).** Enforcing "a courtyard-less footprint
must fail" immediately turns the wing's CI red for all 12 footprints. The staged path:
**(a)** run the gate in **report-only mode** and publish the count; **(b)** open a tracked row to add
courtyards to the 12 wing footprints — or to *explicitly waive* them with named intended contacts;
**(c)** switch to fail-closed only when every **active** footprint carries a courtyard. That keeps the
rule honest (it can fail) without a red build that teaches workers to skip the gate.

## 11. Open decisions for the operator

1. **Adopt the forge as the mechanical method** (vendor as a skill), or evaluate it on one target
   first and decide after?
2. **`REC-FIRST` vs `REC-BS-1` first** — the dev case is already printed and unblocked; the
   masthead split unblocks the largest downstream chunk (`BS-01`).
3. **`BS-02` vs BOM row 11** — which record is current?
4. Do you want the **structural gate class** for the positioner built by us (my recommendation), or
   should the positioner wait for a bought-rotator route?


## 12. Cross-family review record (mandatory before this assessment is scheduled)

Author family **glm/zai**. Reviewer lane **kimi-k3** (moonshot) — family differs. Served model read
back from the runner's own provenance line:

```
[probe] live lane: kimi-k3
[probe] live lane: deepseek/deepseek-v4-flash
[tokens in=6229 out=8937 ~$0.0105 model=kimi-k3]
OVERALL: REVISE
```

Not truncated (`out=8937` under the 16000 cap), 9 findings. All 9 accepted and incorporated:

| # | Finding | Disposition |
|---|---|---|
| 1 | All forge RECs scheduled `NOW` while CadQuery/OCCT was never run | **INCORPORATED** — added **`REC-TOOL-0`** as a hard prerequisite gate; every forge REC now blocked by it |
| 2 | `REC-BS-1` ordered before reconciling `BS-02` vs BOM row 11 | **INCORPORATED** — `REC-X-1` is now a **hard predecessor** of `REC-BS-1` |
| 3 | S2/S3 geometry treated as sufficient to decide `MECH-01` | **INCORPORATED** — §4 overclaim removed ("removes one prerequisite, does not unblock `BS-01`"); 2–3 candidate splits + RF/thermal/power trade table required |
| 4 | Vendoring the external repo lacked supply-chain/licence/sandbox control | **INCORPORATED** — `REC-X-3` now requires full 40-char SHA + tarball hash, licence check, read-only docs, no-network sandbox for executables, human review of external prompts |
| 5 | Boolean gate presented as producing a "print-ready weatherproof case" | **INCORPORATED** — §4 claim corrected; added **`REC-ENV-1`** non-boolean gate set. Boolean pass is necessary, not sufficient |
| 6 | `REC-FIRST` skipped S2/S3 — reproducing the method's own documented failure | **INCORPORATED** — `REC-FIRST` now runs full S0→S9 with S2/S3 explicit |
| 7 | Structural check class cannot be built to a threshold with current data | **INCORPORATED** — `REC-TRK-1` structural gate marked **BLOCKED** on material characterization + `ADR-078 D7`; no thresholds or CI gates until load cases and allowables are measured |
| 8 | Claim that every listed module has usable manufacturer geometry was unverified | **INCORPORATED** — the claim is now `TODO(unverified)` and **`REC-GEO-1`** makes the geometry-availability matrix a `NOW` task |
| 9 | `REC-X-2` fail-closed would immediately red the wing CI | **INCORPORATED** — staged path added (report-only → tracked remediation/waiver → fail-closed) |

**Note on the review's own provenance gap:** finding 4 correctly observes that this assessment
recorded the subject repo's HEAD as "`0925` series" rather than a full SHA. That is a real defect in
*my* data and is fixed by `REC-X-3`, not argued with.

## 13. Upstream enclosure requests — plan (operator instruction, 2026-10-11)

The operator has relayed the enclosure-forge author's offer to build enclosures for the base
station once it is ready, with an explicit ordering constraint:

> *"Please request the enclosures after completing the boards so that we know what our requirements
> are and so that we can convey our requirements in the issue."*

That constraint is **correct and is adopted as a hard gate**: an enclosure request filed against a
board that does not exist would be a request for the forge author to *guess our requirements* — the
one thing this whole method is built to prevent ("no dimension is typed from memory"). So:

**Gating rule.** Each request is blocked by its board reaching **layout freeze + fab set** (outline
frozen, mounting holes and courtyard positions final, connector list and mating directions fixed,
mounting/environment decided). Not "schematic done", not "placement done".

### 13.1 Which boards get an enclosure, and which do not

| Target | Enclosure? | Why / why not | Gated by |
|---|---|---|---|
| **Base station — masthead RF/bias/telemetry board** | **YES** — weatherproof masthead housing, mast clamp | Outdoor, permanently exposed, holds an LNA that must sit at the antenna. Needs IP sealing, a coax/gland interface, and a maintenance path | `MECH-01` split chosen, then that board's layout freeze (`BS-01`) |
| **Base station — shack controller board** | **YES** — indoor case | Bench/indoor, but a real board with connectors and a display path | same as above (`BS-01`) |
| **Antenna tracker electronics** (ESP32 + drivers) | **YES** — outdoor case, rotates | Mounted on a moving structure, so cable strain over the AZ/EL range is a first-class requirement | tracker electronics layout freeze (`BS-07`) |
| **Pre-stretch / leak-test bench rig** | **YES** — bench case with a hose/valve interface | Bench rig that can destroy an envelope; a case makes it repeatable and keeps the over-pressure interlock honest (`PRE-04`) | the rig board's layout freeze (`PRE-01`) |
| **Auto-bootsel interposer** | **MAYBE** — small bench case | Programming aid; a case mainly stops it shorting on the bench. Low value, low cost | interposer layout (exists already, 14 fp / 9 tracks) |
| **Flight hub board (`hub_board_v9`)** | **NO** | Mass-critical at altitude; a printed case is mass the payload cannot spend. It needs a **retention frame**, not an enclosure | — |
| **Flight wing boards (`wing_board_v9` ×4)** | **NO** | Same — and they are the solar carriers; the ADR-065 skeletonised frame is the structure | — |
| **Dev-board case (`balloon_dev_case`)** | **already exists** — retrofit, not a request | This is ours (OpenSCAD); `REC-FIRST` re-homes it onto the method rather than asking upstream | — |

So the answer to "where it makes sense" is **4 clear requests + 1 marginal**, and **two explicit
non-requests** (the flight boards) which are worth stating to the author rather than leaving implied.

### 13.2 The requirements an issue must carry

An issue that says "we need an enclosure for our base station" pushes the measurement work onto the
author. The issue must carry the *outputs of our own S1/S2/S3*, so the author starts from measured
geometry:

1. **Board identity + pinned rev** — repo, path, full commit SHA, board name, dimensions, thickness, layer count.
2. **Fab set** — gerber/drill location + hash, so the author's geometry and ours cannot drift (P11).
3. **Outline + mounting** — Edge.Cuts, mounting-hole Ø and positions **measured off placed solids** (P4: never off DXF callout anchors), courtyard status (see `PCB-01`: a courtyard-less footprint is not evidence).
4. **Component solids** — a solid per component, or an explicit "not modelled" list. Our own gap audit found the wing at **0 of 12** footprints modelled and the hub radio model file **missing** — an issue that omits this lets the author assume a completeness we do not have.
5. **User-facing semantics** (`S2`) — which face the user/antenna/cable sees, up axis, mating direction per connector, boresight. Cite the board-repo doc or photo, never convenience.
6. **Mating envelopes** — per connector: part, mating cable/plug, exit direction, bend radius, service clearance.
7. **Removal/install kinematics** — how the board goes in, what must be unplugged, what sweeps where.
8. **Antenna law** — the RF keep-out and any wall-thickness ceiling (a dielectric window is a named disclosure, not a silent widening).
9. **Environment** — indoor/outdoor/masthead, IP target, temperature range, UV, condensation/freezing, and the site's wind exposure.
10. **Mechanical interface** — mast/pole diameter, clamp, tilt/rotation range, cable-strain relief path.
11. **Non-boolean gates** (`REC-ENV-1`) — the acceptance the volume gate cannot express: seal compression, insert pull-out, gland torque, thermal soak, cable-strain cycling.
12. **Geometry availability** (`REC-GEO-1`) — the matrix row for every module: MPN, revision, source URL, file hash, licence. Misses are declared, with a caliper-measured stand-in and its precision.
13. **Non-requests, stated** — the flight boards are out of scope for enclosures; say so explicitly so the author does not design a case we will never print.

### 13.3 Discipline for posting

- **Draft first, post after operator approval** (standing rule: draft BEFORE posting; upstream
  contributions are one-per-repo and hand-audited by the operator).
- **One issue per target**, not one omnibus issue — each is separately gated and separately
  reviewable.
- The issue is a **request**, not a PR: no branch, no code, no claim of work. State plainly that the
  geometry above is *our* measurement with its provenance, and that the author is free to re-measure
  and contradict it.
- Close the loop: when the author claims a validated case, we re-run **their** `interference_report.json`
  against **our** pinned rev ourselves before printing. A worker self-report — or a partner's — is
  not verification.

### 13.4 Open questions for the operator

1. **Who posts?** I draft each issue and you approve + post, or I post after your approval in-channel?
2. **Non-requests:** do you want me to tell the author explicitly that the flight boards need **no**
   enclosure (a frame, not a case), or leave that silent?
3. **Pre-stretch bench rig** — in scope for an upstream request, or keep it in-house?
4. **Scope of the offer:** the offer as relayed covers the **base station**. Do I ask about the other
   three targets in the same issue thread, or separately once each board is frozen?
