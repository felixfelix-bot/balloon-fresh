# ADR-074 — Two flight-board variants: an F33 high-power board and a low-power LR2021 board, so others can fly without a licence

- **Status:** **Accepted by operator** (Felix, 2026-10-08) — the two-board plan is the
  operator's (*"two flight boards are built"*). The *text* is agent-drafted.
- **Date:** 2026-10-08
- **Decision owner:** Felix (operator)
- **Author:** Hermes subagent (consolidation pass), branch `design/adr-set-groundstation`
- **Related (stable references):** ADR-071 (design basis), ADR-073 (FLRC-max downlink),
  ADR-075 (the F33 module trade and its gated flight decision), ADR-029
  (`docs/adr/029-dual-band-flight-board.md`), ADR-034 (`docs/adr/034-radio-band-split-433-tx-2g4-rx.md`),
  ADR-047 (`docs/adr/047-v9-power-provisioning.md` — the F33 TX rail), ADR-107 / ADR-108
  (three-variant PCB design, F33 + SX1280 pin plan), ADR-039 / ADR-041 (licence-exempt point),
  `docs/PAYLOAD-WEIGHT-ESTIMATES.md`.
- **Evidence:** priced in `docs/analysis/ground-station-gain-per-dollar.md` §Decision 6
  (source branch `design/gain-per-dollar`); the board/EU-variant surface is ADR-029 / ADR-107 /
  ADR-108 on `main`; the weight record is `docs/PAYLOAD-WEIGHT-ESTIMATES.md`.

**Numbering and collision note.** Numbers **066–070 are claimed on sibling design branches**
(see **ADR-071 §Numbering and collision note** for the full table) and are **not reused**.
`scripts/adr_next_number.py` prints 066 because it is branch-blind. This record takes the fresh
number below (verified free, prefix-anchored, against every `github/*` branch, 2026-10-08).

---

## Context

The 433 downlink decision (ADR-073) creates a tension that a single flight board cannot
resolve:

- **FLRC at maximum throughput over 650 km needs the 2 W F33** (+33 dBm). ADR-075 shows that the
  F33 is the cheapest dB in the whole system (≈ **0.40 USD/dB**), and it is what removes a
  7.38 m ground dish from the plan.
- **The F33's +33 dBm class is an amateur-band link.** The entire +13…+33 dBm class **exceeds**
  the committed licence-exempt design point of **+12.15 dBm EIRP** (ADR-039 / ADR-041). Flying
  the F33 requires the DE amateur licence.
- **Not everyone who might replicate or fly this balloon holds an amateur licence**, and the
  operator's stated goal for the ground side is that *"this project remains accessible for
  anyone to replicate"*. A plan whose only variant is licence-gated is not accessible.
- The repo already carries **multiple board variants** (ADR-029 dual-band flight board;
  ADR-107 three-variant PCB design; ADR-062 variant-B design basis), so "two variants" is an
  extension of an existing pattern, not a new architectural borrow.

## Decision

**D1 — Build TWO flight-board variants:**

| variant | 433 transmitter | intended operator | legal footing |
|---|---|---|---|
| **High-power** | **F33** (`LoRa2021F33-2G4`, +33 dBm @ 433 MHz) | the licensed flight (flown with the wing/solar boards the TX rail requires) | **amateur band** (DE licence) |
| **Low-power** | **bare `LoRa2021`** (sub-GHz PA ≤ +22 dBm; clamped to ≤ **+12.15 dBm EIRP** under the committed design point) | **anyone, including operators without an amateur licence** | **licence-exempt** ISM/SRD |

**D2 — The low-power variant is the accessible, licence-free baseline.** It needs no wing/solar
array for the TX rail or the extra module mass, so it flies as a lighter, cheaper board; it is
the variant a third-party replicator can legally fly. **This is the reason the two boards exist**,
and it is the design driver for the ground station's own accessibility tier (ADR-081).

**D3 — Design the ground station for the low-power board, and treat the F33 as a multiplier.**
The ground station must close the link on the **low-power** board; the F33 is then a **3.55×
range multiplier** (10^(11/20)) on whatever the ground can already do (ADR-075 D6). This ordering
is deliberate: it keeps a single ground design valid for both flight variants.

**D4 — The F33's +2.8 g module mass and its TX DC rail are recorded honestly and are gated, not
assumed.** The **High-power** board's flight decision is **not** made by this record: it is
**gated** on (i) the DE amateur licence / airborne-SRD question (ADR-039 open item (a)) and
(ii) correcting the weight record — `docs/PAYLOAD-WEIGHT-ESTIMATES.md` §D classes the F33 board
as *"Ground Station Only … not a pico balloon target"*, a **whole-board** statement (~20.6 g with
solar) that a **+2.8 g module swap** does not by itself overturn. ADR-075 D2 names that
contradiction; it must be resolved by the operator before the high-power board flies.

## Invariants

- **INV-1.** The **low-power variant must close the committed mission without any component that
  requires an amateur licence.**
- **INV-2.** The ground station is sized against the **low-power** variant's link budget; no
  ground item may assume the F33 to close a link.
- **INV-3.** No flight of the high-power variant until the licence question and the weight-record
  correction are settled (ADR-075).
- **INV-4.** The two variants share one firmware/board family (ADR-029 / ADR-107); the
  difference is the radio module and its power provisioning.

## Consequences

### Positive
- The project stays **replicable without a licence**: a third party can build and fly the
  low-power board on the ISM footing.
- The F33 becomes an **optional upgrade** for a licensed operator rather than a prerequisite
  for the design — which is exactly what makes the cheap ground tier meaningful (ADR-081).
- One ground design serves both variants (D3).

### Costs / risks
- **Two boards to design, build, qualify and keep in sync** (BOM, pin plan, firmware variant
  selection). ADR-107 already tracks the three-variant surface; this adds a power/module axis to
  it.
- The low-power board's mission is **short-range FLRC or LoRa-class**, because FLRC-max at 650 km
  needs the F33 (ADR-073 D3). Making that explicit is the point; hiding it would make the
  accessible variant look more capable than it is.
- Mass and DC bookkeeping is now per-variant, and `docs/PAYLOAD-WEIGHT-ESTIMATES.md` §D
  currently contradicts the high-power board's flight (D4).

## Open items (not assumed)

- **`TODO(unverified)`** the **F33 module price** (in-repo ≈ USD 8, LCSC `C5913567`, marked
  "check"; the page is JS-gated).
- **`TODO(unverified)`** the DE amateur / airborne-SRD position (ADR-039 open item (a)).
- **Flagged, no winner:** `docs/PAYLOAD-WEIGHT-ESTIMATES.md` §D ("Ground Station Only") vs this
  record's high-power variant — must be corrected by its own record before the high-power board
  flies.
- **Not decided here:** the mechanical/wing consequence of carrying the F33 (the wing-array
  records own it).

## Relation to other ADRs

- **ADR-073** fixes the modulation that makes the F33 necessary for the far link.
- **ADR-075** prices the F33/Ground split and gates the F33 flight; **this record is the plan
  half of that decision** (two boards), ADR-075 is the cost half.
- **ADR-081** builds the accessible **ground** tier that pairs with this record's accessible
  **flight** variant.
- **Does not supersede** ADR-029 / ADR-107: it extends their variant set with a power axis.

## For future sessions

- **One-line rule:** **two flight boards** — a licence-gated F33 high-power board and a
  licence-exempt low-power LR2021 board — exist so the project can be flown by people **without
  an amateur licence**; size the ground station for the **low-power** board.
- **Do not** treat the F33 as required to close any link; it is a **3.55× multiplier**
  (ADR-075).
