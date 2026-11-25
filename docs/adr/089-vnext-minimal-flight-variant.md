# ADR-089 — vnext MINIMAL flight variant: F33 TX + one LR2021 RX, pogo programming pads, gates before any routing

> Numbered **089** on 2026-11-25 by `scripts/adr_next_number.py` (which prints the next free
> number at or above 044; 089–099 are free, the 100–152 range is occupied by displaced/historical
> and later records). Verified before writing: `scripts/adr_next_number.py` → `89` (exit 0);
> `--number 089` → `89` (exit 0); `--path docs/adr/089-vnext-minimal-flight-variant.md` → `89`
> (exit 0).

- **Status:** ACCEPTED — operator instruction, 2026-11-25 (task brief: *"User approved minimum
  flight variant: F33 transmitter + ONE low-power LR2021 receiver + ESP32 + required power"*
  plus the removal and gate list recorded below). Design intent only, NOT a layout or order
  authorization.
- **Date:** 2026-11-25
- **Decision owner:** Felix (operator) — the direction is his; the gate ordering is taken
  verbatim from his instruction.
- **Author:** Hermes worker (worker-reviewer-glm), worktree `~/worktrees/vnext-minimal-docs`,
  branch `pr/vnext-minimal-docs`, fresh from `github/master` @ `9fd276a8`. Docs-only slice:
  **no board, schematic, footprint or BOM file was touched; nothing purchased, flashed or ordered.**
- **Scope:** the NEXT flight board ("vnext"), as a THIRD variant beside ADR-074's high-power and
  low-power boards. It removes optionality from the **MINIMAL variant only** — v10 (built/ordered)
  and the full v11 change list are unaffected.
- **Related:** ADR-074 (two flight-board variants — EXTENDED, see §3), ADR-119 (v10 four RF sites —
  scoped supersession, §3), ADR-121 (J_PROG header — scoped amendment, §3), ADR-145 (U_C GPIO
  economy — scoped, §3), ADR-138/139 (ranging gate / site-D part — conditional, §3),
  ADR-112/ADR-120 (placement gates that still apply), `docs/fab/V11-DESIGN-SPEC.md` (the FULL
  v11 change list), `docs/fab/VNEXT-MINIMAL-PLAN.md` (implementation plan),
  `docs/fab/VNEXT-MINIMAL-REQUIREMENTS.json` (machine-readable requirements + mass baseline).

---

## 0. The decision, in one paragraph

The next flight board gets a **MINIMAL variant** whose radio set is the **F33 transmitter
(`U2`) + ONE low-power LR2021 receiver (`U3`) + the ESP32-S3 and its required power**, with the
**redundant second LR2021 (`U_C`)** and the **SX1280-class ranging site** removed from THIS
variant (not from the family), the **tall 6-pin programming header replaced by functional pogo
pads**, and **direct power wiring / strain relief evaluated**. GPS/tracking, necessary burst
storage, and release safety are **retained until evidence permits removal**; the **ground
plane and module shields are retained**. The support/wing interfaces must be **weighed**. The
outline is **NOT asserted** — a 50 × 60 mm example is **not a proven fit** — and four layers at
a nominal 0.8 mm is a **candidate, not a qualified stackup**. A fixed gate sequence (§5) must
pass before any routing.

## 1. The MINIMAL variant's part set (measured from the current v11 sources)

The v11 netlist (`tracker/hardware/schematics/flight_board/v11_flight.net`) carries four radio
references. Measured (grep, 2026-11-25, this worktree):

| ref | value / part | role | MINIMAL decision |
|---|---|---|---|
| `U2` | `LoRa2021F33-2G4` | 433 MHz TX (HP) | **KEEP** (the transmitter) |
| `U3` | `LoRa2021_Castellated` (bare LR2021) | 2.4 GHz RX link | **KEEP** (the ONE receiver) |
| `U_C` | `LoRa2021_Castellated` | second 2.4 GHz option | **REMOVE** from MINIMAL (redundant here) |
| `U_LORA1280` | `LoRa1280` (SX1280, ranging) | 2.4 GHz ranging site D | **REMOVE** from MINIMAL |

Also removed from MINIMAL: the J_PROG 2.54 mm vertical header (5.0 × 15.2 mm courtyard,
ADR-121), replaced by **pogo pads** exposing the SAME six signals (GND, +3V3, EN, USB_D−,
USB_D+, IO0) plus the EN RC (10 kΩ / 1 µF) — the electrical contract of ADR-121 carries over;
only the mating hardware changes.

**Retained:** MAX-M10S GNSS/tracking (`docs/modules/max-m10s/`), burst storage (supercap bank,
ADR-006/ADR-036), release safety (the four nichrome cut channels, ADR-129 /
`docs/fab/V11-CUT-CHANNELS.md`) — all *until evidence permits removal*, the ground plane
(ADR-067) and module shields.

**A measured inconsistency the footprint gate must resolve:** the v11 NETLIST names site D
`U_LORA1280` (per ADR-139), while the stage-1 BOARD (`tracker/hardware/hub_board_v11_stage1.kicad_pcb`,
commit `e27a0d3c`) still carries `U_E28` with the `E28-2G4M27SX` footprint. The two files disagree
about the ranging site's identity; on MINIMAL the site is removed either way, but any non-MINIMAL
vnext build must reconcile netlist and board first (gate G1/G2).

## 2. What this record does NOT decide (non-claims)

- **No outline.** 50 × 60 mm is an example, not a proven fit. The full-variant fit probe
  (`tracker/hardware/v11_fit_probe.json`) measures **101 components, min square outline 75.7 mm**;
  the MINIMAL set is smaller, but its fit is **unmeasured** and is an OUTPUT of gates G3–G5.
- **No stackup qualification.** Four layers at nominal 0.8 mm (the JLC 4-layer minimum,
  `docs/fab/hub-v9/PRE-ORDER-CHECKLIST.md`) is a CANDIDATE. Thickness/mating verification is
  gate G5.
- **No routing, no layout, no ERC/DRC claim, no BOM change, no purchase.** This is the docs-only
  first slice of a bounded task.

## 3. Scoped supersession and annotation (explicit, per repo rule)

| record | relationship | scope |
|---|---|---|
| **ADR-074** | **EXTENDED** — the variant set gains a third member: the MINIMAL flight variant (F33 TX + one LR2021 RX) for the operator's next licensed flight. ADR-074's two variants and its invariants (ground sized for the low-power board; F33 a multiplier) are unchanged. | whole family |
| **ADR-119** | **SUPERSEDED IN PART** — its four-RF-site table governs the full variant; the MINIMAL variant carries **two** sites (A: F33, B: one LR2021) and **no** site C / site D. Sites C/D remain valid for non-MINIMAL variants. | MINIMAL only |
| **ADR-121** | **AMENDED IN PART** — "every flight board carries a 6-pin 2.54 mm header" becomes, on MINIMAL, "functional pogo pads exposing the same six signals + EN RC". Other variants keep the header. | MINIMAL only |
| **ADR-145** | **MOOT ON MINIMAL** (its three GPIO-economy measures exist to address `U_C`, which MINIMAL removes). Remains PROPOSED for variants that keep `U_C`. | MINIMAL only |
| **ADR-138 / ADR-139** | **CONDITIONAL** — the ranging flight gate and the site-D part choice bind only where site D exists. MINIMAL has no ranging site, so for MINIMAL the gate is satisfied by removal, not by measurement. | non-MINIMAL unaffected |

Each superseded/amended record carries a pointer blockquote at its top (this commit). Where two
records disagree, the one that explicitly supersedes wins (AGENTS.md DECISION RECORDS rule).

## 4. Mass baseline (operator-measured anchors; no bare-PCB number invented)

| quantity | value | provenance |
|---|---|---|
| owner assembly mass, **without** F33 | **27.05 g** | operator-measured, task brief 2026-11-25; not independently re-measured in-repo |
| owner assembly mass, **with** F33 | **31.05 g** | same |
| difference | **4.00 g** | same — **an assembly-level delta, NOT bare-PCB mass** |
| F33 module mass | **+2.8 g** | ADR-074 D4 (module only) |

The 4.00 g delta exceeds the +2.8 g module figure; the remainder is unmeasured support hardware
and is **not** decomposed here. Removing `U_C` and the ranging site removes their *footprints and
support copper* from MINIMAL — the bare-PCB mass saving is `TODO(unverified)` until the outline
exists (it is an output of the gates, not an input). The support/wing interface hardware must be
**weighed** (gate G5) before any total-mass claim. Machine-readable baseline:
`docs/fab/VNEXT-MINIMAL-REQUIREMENTS.json`.

## 5. Required next gates — in this order, before ANY routing

1. **G1 — Reconcile the ordered archive.** The vnext baseline must inherit the true ORDERED v10
   state (`docs/fab/v10-order-top-only/`, `docs/fab/V10-JLCPCB-ORDER-SHEET.md`,
   `docs/fab/FOUR-BOARDS-ORDER-STATUS.md`), not any working-tree drift; and the v11
   netlist-vs-stage1-board ranging-site divergence (§1) is reconciled.
2. **G2 — Correct the real-module footprint mismatch.** The F33 land pattern has never been
   verified pin-for-pin against a real module (`docs/fab/F33-PART-NUMBER-VERIFICATION.md` §Honest
   limits; the family name itself was wrong — `LoRa1121F33-2G4`, not `LoRa2021F33-2G4`), and the
   LoRa1280 land geometry needs the caliper check (`docs/modules/lora128x/FOOTPRINT-SPEC.md` §3).
   Both surviving radio sites must be measured against real parts before placement.
3. **G3 — Per-layer track length / nets / filled-copper audit** of the reference board
   (`hub_board_v11_stage1.kicad_pcb`) restricted to the MINIMAL net set, so the reduced board's
   routing demand is known before placement is trusted.
4. **G4 — Keep / optional / remove annotated layout.** Every reference annotated KEEP / OPTIONAL /
   REMOVE against the MINIMAL set, so optionality is visible, not implied.
5. **G5 — Single- vs double-sided compact-placement comparison** with REAL courtyards, holes,
   antenna/receiver desense, thermal and mechanical constraints, reported with the full
   AGENTS.md §1b density table (per-side courtyard occupancy, largest empty rectangle,
   reservation areas, denominators). The 0.8 mm four-layer candidate's **thickness/mating
   verification** (wing-socket/tab mating, pogo-pad contact, connector seating) and the
   **direct-power-wiring / strain-relief evaluation** land here; the **support/wing interface
   mass** is weighed here.
6. **G6 — Human placement gate** (ADR-112 / ADR-120 R3): operator sign-off on renders before
   routing. **Only then routing.**

Phase-by-phase plan with exit criteria: `docs/fab/VNEXT-MINIMAL-PLAN.md`.

## 6. Reproduce (the measurements this record cites)

```
grep -B3 'value "LoRa' tracker/hardware/schematics/flight_board/v11_flight.net   # U2/U3/U_C/U_LORA1280
grep -n 'U_E28\|E28-2G4M27SX' tracker/hardware/hub_board_v11_stage1.kicad_pcb    # the site-D divergence
cat tracker/hardware/v11_fit_probe.json                                          # 101 comps, 75.7 mm min square (FULL variant)
python3 scripts/adr_next_number.py                                               # -> 89 (this record's number)
grep -n '27.05\|31.05' docs/fab/VNEXT-MINIMAL-REQUIREMENTS.json                  # operator-measured anchors
```

## 7. What would change this decision

- Evidence that the single LR2021 receiver cannot close its link (then `U_C` or site D returns).
- A ranging requirement re-asserted for the next flight (site D returns, ADR-138 gate re-binds).
- A measured assembly where pogo pads cannot make reliable contact (then ADR-121's header returns
  on MINIMAL).
- The operator's mass target forcing removal of GPS/burst/release items — each such removal needs
  its own evidence and its own record; this ADR explicitly does not remove them.
