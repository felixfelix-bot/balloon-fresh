# VNEXT MINIMAL — compact implementation plan (docs-only first slice)

**Status:** PLAN — derived from ADR-089 (ACCEPTED, 2026-11-25). No board, schematic, footprint or
BOM file is changed by this slice. Nothing is purchased, flashed or ordered.

**Variant:** MINIMAL = `U2` F33 TX + `U3` (one LR2021 RX) + ESP32-S3 + required power; `U_C` and
the ranging site (`U_LORA1280`/`U_E28`) removed **from this variant**; J_PROG header → pogo pads;
GPS/tracking, burst storage, release safety, ground plane, shields RETAINED.

**Baseline:** worktree `~/worktrees/vnext-minimal-docs`, branch `pr/vnext-minimal-docs`,
fresh from `github/master` @ `9fd276a8`. Sources: v11 schematic/netlist
(`tracker/hardware/schematics/flight_board/`), stage-1 board
(`tracker/hardware/hub_board_v11_stage1.kicad_pcb` @ `e27a0d3c`), v10 order record
(`docs/fab/v10-order-top-only/`).

---

## Phase 0 — Reconcile the ordered archive (gate G1)

**Goal:** the vnext baseline reflects what was actually ORDERED on v10, and the v11 netlist vs
stage-1 board divergence is resolved so the MINIMAL net set is unambiguous.

Steps:
1. Diff the net set of `v11_flight.net` against the stage-1 board's embedded netlist; record the
   site-D reference divergence (`U_LORA1280` in netlist vs `U_E28`/`E28-2G4M27SX` footprint on
   board) as a FINDING with both readings.
2. Lock the MINIMAL net list: drop every net whose only consumers are `U_C` and the ranging site
   (`/U_C_*`, `/E28_*` or `/LORA1280_*` control nets), keep everything else including
   `/F33_*`, `/U3_*`, GNSS, power, cut channels, I²C (both ADS1115 stay — they serve
   `/SCAP_ADC` + solar dividers + cut sense, not the removed radios).
3. Exit criteria: (a) a committed `MINIMAL-NETLIST.md` (or diff table) naming every removed net
   and the ref that consumed it; (b) no net removed that a KEPT reference still touches.

## Phase 1 — Footprint truth (gate G2)

**Goal:** both surviving radio sites verified against REAL modules, plus the pogo pad geometry.

1. F33 (`U2`): measure a real module — body L×W, castellation Ø and pitch — against
   `scripts/gen_f33_landpattern.py` and `docs/f33-module/F33-LANDPATTERN-VERIFICATION.md`.
   Known hazards already in the record: the family is `LoRa1121F33-2G4`
   (`docs/fab/F33-PART-NUMBER-VERIFICATION.md`), and pin/land pattern was never verified.
2. LR2021 bare (`U3`): verify the castellated pad geometry against a real module
   (`LoRa2021_Castellated`, 18-pad).
3. Pogo pads: select pogo pin pitch/force class, define pad geometry (≥ Ø0.9 mm typical for
   1.0 mm-pitch pogos — `TODO(unverified)`, set from the chosen pin's datasheet), keep the
   ADR-121 six-signal contract + EN RC; annotate keep-out for the pogo fixture on both faces.
4. Exit criteria: a `FOOTPRINT-VERIFICATION.md` per site with measured numbers (caliper),
   the chosen pogo part, and updated land geometry where the measurement demands it.

## Phase 2 — Routing-demand audit (gate G3)

**Goal:** know the MINIMAL board's per-layer copper demand BEFORE placement is trusted.

1. Run the per-layer track-length/nets/filled-copper audit on the reference board restricted to
   the MINIMAL net set (Phase-0 list): per-layer track length, per-net segment/via counts, zone
   fill coverage per layer. Tooling exists: `docs/analysis/run_all_gates.py`,
   `tracker/hardware/tmp_probes/` (note: 64/65 probes hardcode `worktrees/master-check` paths —
   run from the right worktree or fix paths per-probe).
2. Record the removed nets' copper (the `U_C` control runs alone spanned 19.81 mm on opposite
   faces — ADR-145); that is the measured copper the removal buys.
3. Exit criteria: a committed audit table (analysis doc with method + reproduce command, per
   `docs/analysis/` conventions) covering at minimum: per-layer total track length, per-net
   segment counts, filled-copper area per layer, for the MINIMAL set.

## Phase 3 — Keep/optional/remove annotated layout (gate G4)

**Goal:** every reference on the reference board annotated KEEP / OPTIONAL / REMOVE with reason.

1. Start from `v11_fit_probe.json` (101 components, FULL variant) — the MINIMAL probe is a new
   measurement, not a subtraction of totals.
2. Annotate: radios per ADR-089 §1; J_PROG → REMOVE (pogo pads KEEP-as-new); `U_CUT1..4` + gate
   resistors KEEP (release safety); ADS1115 ×2 KEEP; MAX-M10S KEEP; supercap bank KEEP;
   `D_BP1..4` KEEP (top side per ADR-146); mounting holes per support/wing interface decision.
3. Exit criteria: committed annotation table (ref → verdict → reason → evidence), covering 100%
   of the FULL-variant reference set; anything without a verdict is a defect, not an omission.

## Phase 4 — Compact placement comparison + mechanics (gate G5)

**Goal:** the measured smallest outline, single- vs double-sided, with all constraints real.

1. Two placement studies at true-footprint courtyards (concept rectangles first is allowed for
   round 1 per ADR-112's gate rounds, but the DECIDING round uses true footprints):
   - single-sided: all MINIMAL parts on one face;
   - double-sided: per AGENTS.md §1b — compute the ≥10 % threshold, report the full density
     table (per-side occupancy, largest empty rectangle, reservation areas with sizes and
     justifications).
2. Constraints that must be real numbers, not vibes: antenna keep-outs BOTH faces at each module
   site (ADR-119/ADR-137: antenna at module, 3D volume reservations per the balloon conventions —
   CONFIRMED/PROVISIONAL labelled with evidence lines); receiver desense separation between the
   F33 TX site and the `U3` RX site; thermal (buck loop tight, PA dissipation); mounting/support
   holes for the support/wing interface; holes and courtyards per ADR-141 (drill ≥ 0.20 mm).
3. Thickness/mating: verify the 0.8 mm four-layer CANDIDATE against wing-socket tab insertion
   (ADR-131 assumes 0.6 mm FR4 wing inserts — re-check the slot/hole geometry at 0.8 mm), pogo
   contact at the chosen pad height, and connector seating.
4. Direct power wiring / strain relief: evaluate soldered-in power leads vs a connector with a
   strain-relief feature; the wing-power nets already land on edge sockets, so the evaluation is
   about the BATTERY/SUPERCAP side; record decision + reasoning per AGENTS.md standing authority.
5. Weigh the support/wing interface hardware (screws, sockets, inserts, tether holes) — needed for
   the mass table in `VNEXT-MINIMAL-REQUIREMENTS.json`.
6. Exit criteria: both outlines measured with the full density table; desense/thermal/mechanical
   constraints quantified; thickness mating verified or a different stackup chosen with reasoning;
   power-wiring decision recorded; interface mass weighed.

## Phase 5 — Human placement gate, then routing (gate G6)

1. Render front+back placement from measured courtyards; operator sign-off in Signal (ADR-120 R3
   — the gate is binding; routing on an ungated placement is discarded).
2. Only after sign-off: schematic-first re-entry (settle the cut-driver gate/sense resistor
   values still open from `V11-DESIGN-SPEC.md` §3 if the cut channels carry into the MINIMAL
   build), then route per the v10 campaign's two checks (previously-connected pairs not broken;
   opens decreasing).

## What this plan deliberately does NOT do

- No outline assertion (50 × 60 mm example is not a proven fit — fit is a Phase-4 OUTPUT).
- No stackup qualification (0.8 mm/4-layer is a candidate until Phase 4.3).
- No removal of GPS/burst-storage/release-safety (retained until evidence permits, per ADR-089 §7).
- No purchase, no flash, no order.

## Mass accounting hooks

`docs/fab/VNEXT-MINIMAL-REQUIREMENTS.json` holds the machine-readable baseline: the
operator-measured assembly masses (27.05 g / 31.05 g / 4.00 g delta — an assembly-level figure,
NOT bare-PCB mass), the ADR-074 module delta (+2.8 g), and the `TODO(unverified)` slots the gates
fill (bare-PCB mass, interface hardware mass, pogo pad mass). Update it as gates land; do not
fill a slot without its measurement.
