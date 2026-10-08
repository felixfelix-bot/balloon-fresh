# ADR-080 — The XR-613 divider is a resistive bench tool, NOT an array combiner (resistive ⇒ 6 dB, no array gain)

- **Status:** **Accepted by operator** (Felix, 2026-10-08) — the operator supplied the part's
  identity and nature (*"The XR-613 divider is resistive (DC–5G ⇒ 6 dB, no array gain) and is a
  bench tool, not an array combiner"*). This closes the source branch's open item 1.
- **Date:** 2026-10-08
- **Decision owner:** Felix (operator)
- **Author:** Hermes subagent (consolidation pass), branch `design/adr-set-groundstation`
- **Related (stable references):** ADR-078 (the antenna-class decision this constrains), ADR-075
  (the gain-per-dollar ledger a divider would have to beat), ADR-079 (the receive chain).
- **Evidence:** `docs/analysis/rf-shopping-list-and-duplex-architecture.md` §5 (shopping list row 2,
  "XR-613 power divider (DC–5 GHz), OWNED, identity `TODO(unverified)`") and §8 open item 1 —
  source branch `design/rf-shopping-list`; the array/combining algebra in
  `docs/analysis/ground-station-amplifier-hypothesis-check.md` §Decision 4–5 + the model
  `docs/analysis/ground_station_amplifier_hypothesis_model.py`. Reproduce:
  `python3 docs/analysis/ground_station_amplifier_hypothesis_model.py`.

**Numbering and collision note.** Numbers **066–070 are claimed on sibling design branches**
(see **ADR-071 §Numbering and collision note** for the full table) and are **not reused**.
`scripts/adr_next_number.py` prints 066 because it is branch-blind. This record takes the fresh
number below (verified free, prefix-anchored, against every `github/*` branch, 2026-10-08).

---

## Context

The operator owns an **XR-613** power divider (specified **DC–5 GHz**). A sibling branch carried its
identity as an **unresolved open item** ("no datasheet, vendor page or AliExpress listing found; the
analysis treats it as a DC–5 GHz power divider/splitter") and flagged that the owned Red Pitaya
(DC–60 MHz analog bandwidth) **cannot** verify it at 433 MHz or 2.4 GHz. The operator has now
supplied the fact that closes the item: the part is a **resistive** divider.

**Why the resistor type decides the answer.** A resistive (Wilkinson-free, purely ohmic) divider
splits input power with a **fixed 6 dB theoretical split loss for a 2-way divider** and dissipates
the difference in its resistors; the **combine direction is equally lossy**. It therefore provides
**no array gain** — the split loss and the combine loss cancel any coherent-sum benefit, and being
resistive it cannot be a low-loss hybrid. **It is a bench instrument** (splitting a signal to two
instruments, or injecting a reference), **not a power combiner for an antenna array.**

**The array/combining algebra this sits under (retained from the sibling branch).** Incoherent power
combining of N branches gives **N× signal AND N× noise = +0.00 dB**. Only **coherent** combining — a
real **phased array** (per-element phase shifters / continuous correction) or **MRC with N complete
receivers** (still predetection/coherent) — gives **+10·log10 N** (+3.01 dB N=2, +6.02 dB N=4).
Separate trackers guarantee separate phase, so a "one cheap tracker per Yagi, combined" scheme
**cannot** be the coherent case. And even a genuinely coherent 2-/4-bay stack is priced at
**EUR 76.13 / EUR 93.73 per needed dB** — 207–255× the F33's per-dB cost (ADR-075).

## Decision

**D1 — The XR-613 is recorded as a RESISTIVE divider: DC–5 GHz, ~6 dB split loss, and NO array
gain.** It is **not** an antenna-array combiner and must never be counted as one in a link budget.

**D2 — The XR-613 is a BENCH TOOL.** Its legitimate uses are test/measurement (splitting to two
instruments, reference injection). It is not part of the gateway RF chain.

**D3 — Do NOT build a Yagi array for gain using a resistive combiner.** A resistive combiner
subtracts exactly what a coherent array would add; an array built on it is a **loss**, not a gain.

**D4 — Combining for GAIN requires coherence** — a real phased array or MRC with N receivers. If a
multi-antenna scheme is wanted, the **useful** reading is **multi-sector COVERAGE** (**0 dB gain**),
which removes the precision-tracking requirement rather than adding gain.

**D5 — Any divider counted in a link budget must state its type (resistive / hybrid / Wilkinson) and
its **insertion** loss**, not its split loss alone.

## Invariants

- **INV-1.** No resistive divider may appear as a gain stage in any link budget in this project.
- **INV-2.** Array gain is claimed only for a coherent array; incoherent combining is **+0.00 dB**.
- **INV-3.** Any "array" proposal must state its per-channel phase coherence and its combiner type.

## Consequences

### Positive
- A wrong assumption is closed **before** it costs hardware: the owned divider cannot be repurposed
  as an array combiner.
- The "many cheap trackers, combined" idea is answered in the correct frame (coverage, not gain), so
  it is not re-proposed as a gain scheme.
- One less invented requirement in the shopping list (the LiteVNA 62 was included in the sibling
  branch partly to *verify* the XR-613; with the part identified as resistive, the verification is
  now a **characterisation**, not an identity question).

### Costs / risks
- The XR-613's **exact datasheet figures remain `TODO(unverified)`** — the operator's statement fixes
  its *class* (resistive, ~6 dB, no gain) but not its measured insertion loss or its power rating, so
  it must not be used in any high-power chain.
- A resistive divider at 433 MHz into a mismatched load is **not** a calibrated instrument; treat its
  numbers as indicative.

## Open items (not assumed)

- **`TODO(unverified)`** the XR-613's measured **insertion loss and power rating** (its class is now
  known; its numbers are not).
- **`TODO(unverified)`** the sibling branch's companion open item: the **unmarked mixer module's
  specs** (LO/RF/IF range, conversion loss, drive level) — also owned, also unidentified.

## Relation to other ADRs

- **Closes** open item 1 of the off-branch `design/rf-shopping-list` work (the XR-613 identity), and
  **retains** its shopping-list context. That branch's `070-ground-station-duplex-t-r-architecture.md`
  is superseded by ADR-072.
- **Consumes** the combining algebra of the off-branch `070-ground-station-amplifier-hypothesis`
  §Decision 4–5 (superseded by ADR-079 / this record / ADR-072).
- **Constrains** ADR-078: the pre-cliff Yagi array is a **coherent** stack with a proper hybrid /
  phasing harness; the XR-613 is not that harness.

## For future sessions

- **One-line rule:** the owned **XR-613 is a resistive (~6 dB) bench divider with NO array gain** —
  it is a test tool, not a combiner; combining for gain needs **coherence**.
- **Reproduce:** `python3 docs/analysis/ground_station_amplifier_hypothesis_model.py`.
