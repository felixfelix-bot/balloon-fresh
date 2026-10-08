# ADR-077 — Print the structure, buy the gearing: a self-locking worm reducer is mandatory

- **Status:** **Accepted by operator** (Felix, 2026-10-08) for the **printed-positioner
  direction** (*"a 3D-printed AZ/EL positioner using stepper motors"*). The specific constraint
  that the **gearing must be bought and self-locking** is an agent-locked engineering requirement;
  no operator dissent is recorded.
- **Date:** 2026-10-08
- **Decision owner:** Felix (operator) — the printed-positioner direction
- **Author:** Hermes subagent (consolidation pass), branch `design/adr-set-groundstation`
- **Related (stable references):** ADR-071 (design basis), ADR-076 (stow policy — the hold this
  gearing must not be relied on for), ADR-078 (right-sizing), ADR-082.
- **Evidence:** `docs/analysis/positioner-lowcost-3dprinted.md` +
  `docs/analysis/positioner_lowcost_model.py` (source branch `design/positioner-lowcost`, whose
  `docs/adr/067-positioner-architecture.md` is **superseded by this record** / ADR-076 / ADR-078);
  metal-vs-printed material table and the "buy the gearing" finding in
  `docs/analysis/ground-station-gain-per-dollar.md` §§3–4 (source branch `design/gain-per-dollar`).
  Reproduce: `python3 docs/analysis/positioner_lowcost_model.py`.

**Numbering and collision note.** Numbers **066–070 are claimed on sibling design branches**
(see **ADR-071 §Numbering and collision note** for the full table) and are **not reused**.
`scripts/adr_next_number.py` prints 066 because it is branch-blind. This record takes the fresh
number below (verified free, prefix-anchored, against every `github/*` branch, 2026-10-08).

---

## Context

A commercial AZ/EL positioner for this station costs **EUR 949–1,775** (the BOM study's
`docs/analysis/ground-station-bom-candidates.md` §0.5), which dominates the station cost above
~1.5 m of aperture. The operator wants a **3D-printed AZ/EL positioner with stepper motors**.

A previously printed tracker (Printables model **945761**, *Antenna Tracker* by Stratos) was
**too weak**: it uses **28BYJ-48** steppers, its author states the motors *"are not the best
option"*, and its 4 × 608zz bearing / 14:50 pitch-gear layout has **no stated mass or wind
rating**. That is the failure mode this record exists to prevent: **plastic gear teeth carrying a
wind load**.

Three properties of the materials decide the split:

| property | metal (5052/5754 Al, 304 SS) | printed PETG/ASA |
|---|---|---|
| stiffness | E ≈ 70 GPa | E ≈ 2 GPa (~1/35) |
| creep under sustained load | none | **real** — the failure mode of a held antenna |
| wind survival | ductile, yields | brittle/anisotropic along layer lines |
| cost per part (qty 1) | EUR 45–160 | EUR 0.30–3.00 filament |
| iteration | 1 day (Protolabs) – 5–8 days (Schaeffer) | hours |

A **self-locking worm reducer** (e.g. NMRV40 20:1, rated 40 N·m) driven by **NEMA23 3.0 N·m**
steppers moves the required hold torque into a **purchased** element: the axis needs **24.9 N·m**
at 0.6 m (balanced, SF 2) vs **199.5 N·m** at 1.2 m — the difference between one NMRV40 + NEMA23
and a NEMA34 + large two-stage reducer. But the vendor **does not warrant** the worm's
self-locking for holding loads (it is ratio- and friction-dependent), which is exactly why
ADR-076 requires a separate positive mechanical hold.

## Decision

**D1 — 3D-print the STRUCTURE only.** Yoke, turret, bearing housings, antenna backplate, boom
clamp and electronics bay are printed (PETG/ASA, ribbed, with metal bearing inserts).

**D2 — BUY the GEARING. No printed gear or printed tooth face may carry AZ/EL hold torque.** The
torque reaction lives in the purchased worm reducer and in purchased bearings/shafts.

**D3 — A SELF-LOCKING worm reducer is mandatory on each axis.** (Not a printed gear train, not a
belt, not a non-self-locking spur pair.) Driven by a stepper or closed-loop stepper.

**D4 — Metal for the load path, printed for covers.** The azimuth platform/turret base, antenna
backplate, mast/rotor plates, all load-path brackets and the bearing housings (or their metal
inserts) are **metal** (sheet-metal laser cutting + bending is a commodity online service);
electronics bay, covers, cable guides, boom clamp, feed spider and non-structural spacers stay
**printed**. The **gearing** is bought — neither printed nor sheet-metal.

**D5 — Closed-loop position feedback is required for pointing, and it is NOT wind protection.**
Per-axis absolute magnetic encoders plus **unidirectional-approach** backlash discipline; this is
what keeps a cheap tracker viable on a small dish's pointing budget. A motor that knows its
position **does not** stop a drive being back-driven, and actively correcting a back-driven axis
burns torque and can oscillate.

**D6 — The correct combination is: self-locking worm (primary brake) + closed-loop feedback +
fail-safe spring-applied brake + anemometer stow.** Self-locking is treated as a **primary
brake, never as the only brake** (ADR-076 INV-3).

## Invariants

- **INV-1.** No printed gear or printed tooth face carries AZ/EL hold torque.
- **INV-2.** Each axis has a **self-locking** purchased reducer.
- **INV-3.** Closed-loop feedback is not accepted as a substitute for the mechanical hold.
- **INV-4.** Any load-path part is metal; printing is for non-load-bearing geometry.

## Consequences

### Positive
- ≈ **1.9–3.9×** cheaper than the commercial BOM in parts (≈ EUR 650–730 reference; ≈ EUR 430–510
  with a DIY feed and a salvaged dish).
- One structural class down: **24.9 N·m** required at 0.6 m (balanced, SF 2) vs **199.5 N·m** at
  1.2 m.
- Rebuildable: the printed structure is the cheap, replaceable part; the bought gearing is the
  load-bearing one.
- A **DIY mid-class rotator** (printed structure + bought self-locking worm + NEMA23) **repairs
  the market gap** between the EUR 359 Yaesu class and the EUR 1,132+ SPX/SPID class (ADR-078).

### Costs / risks
- The printed structure is a **prototype, not a product**: mass and stiffness must be **measured**,
  not assumed.
- Printed PETG/ASA **creeps under sustained load** — the failure mode of a held dish — which is
  precisely why hold must not depend on printed parts.
- The worm's self-locking is **vendor-unwarranted** → the brake/latch of ADR-076 is required.
- Encoder and closed-loop driver parts are costed `TODO(unverified)` (AS5600/MT6701 class;
  closed-loop stepper drivers ≈ USD 46.64–48.04; a 17-bit absolute-encoder AC servo kit ≈ USD
  98.43), so the drive's exact price is not frozen.

## Open items (not assumed)

- **`TODO(unverified)`** encoder and closed-loop driver prices.
- **`TODO(unverified)`** measured stiffness and creep of the printed structure under the held
  load.
- **`TODO(unverified)`** the bought reducer/stepper part numbers, which are candidates named in
  the analysis (NMRV40 class, NEMA23) rather than a frozen BOM.

## Relation to other ADRs

- **Supersedes** the off-branch `067-positioner-architecture` (`design/positioner-lowcost`) for the
  **print/buy split and the gearing requirement**; its survival policy lands in ADR-076 and its
  right-sizing in ADR-078.
- **Consumes** the off-branch `068-ground-station-gain-per-dollar` §§3–5 (metal-vs-printed,
  closed-loop) — that record is superseded by ADR-075 / ADR-078 / ADR-081.
- **ADR-076** owns the hold that this gearing must not be solely relied on for.

## For future sessions

- **One-line rule:** *print the structure, buy the gearing* — the **load path is metal**, the
  **covers are printed**, and a **self-locking worm reducer is mandatory** with a separate
  mechanical hold (ADR-076).
- **Reproduce:** `python3 docs/analysis/positioner_lowcost_model.py`.
