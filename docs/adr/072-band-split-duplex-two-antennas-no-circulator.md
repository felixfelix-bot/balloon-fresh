# ADR-072 — Band-split duplex at the gateway: two band antennas, and NO circulator

- **Status:** **Accepted by operator** (Felix, 2026-10-07 for the band split, via ADR-034;
  2026-10-08 for the "owned T/R hardware is not needed" reading) — the *text* is agent-drafted.
- **Date:** 2026-10-08
- **Decision owner:** Felix (operator)
- **Author:** Hermes subagent (consolidation pass), branch `design/adr-set-groundstation`
- **Related (stable references):** ADR-071 (this set's design basis), ADR-034
  (`docs/adr/034-radio-band-split-433-tx-2g4-rx.md` — the balloon-side split this mirrors),
  ADR-035 (`docs/adr/035-tdm-radio-schedule.md`), ADR-039 / ADR-041 (licence-exempt design
  point and front end), `docs/LINK-BUDGET-LICENCE-EXEMPT.md`.
- **Evidence:** `docs/analysis/rf-shopping-list-and-duplex-architecture.md` +
  `docs/analysis/rf_shopping_list_model.py` (source branch `design/rf-shopping-list`, which
  carried this decision as its file `docs/adr/070-ground-station-duplex-t-r-architecture.md`
  — now **superseded by this record**). Reproduce:
  `python3 docs/analysis/rf_shopping_list_model.py`.

**Numbering and collision note.** Numbers **066–070 are claimed on sibling design branches**
(066: `design/ground-station-lowpower-link` + `design/ground-station-flrc-max`; 067:
`design/ground-station-flrc-max` + `design/positioner-lowcost`; 068: `design/gain-per-dollar` +
`design/gain-per-dollar-cliff` + `design/amplifier-substitution`; 069: `design/tier0-accessible`;
070: `design/amplifier-hypothesis-check` + `design/rf-shopping-list`) and are **not reused** here.
`scripts/adr_next_number.py` prints 066 because it is branch-blind. The full table and the reason
no rename is made are in **ADR-071 §Numbering and collision note**. This record takes the fresh
number **072** (verified free, prefix-anchored, against every `github/*` branch, 2026-10-08).

---

## Context

ADR-071 fixes the gateway as **full duplex**. This record fixes *how* the duplex is built at
the ground end, and it is a one-line answer with a large consequence:

| at the ground station | band | direction |
|---|---|---|
| **RECEIVE** | **433 MHz** | balloon → ground (downlink) |
| **TRANSMIT** | **2450 MHz** | ground → balloon (uplink) |

The two bands are **5.65× apart (≈2.5 octaves)**. Three consequences were verified on the
source branch:

1. **A half-duplex T/R relay is ruled out** (ADR-071 INV-1).
2. **Duplexing is by band separation, not by a same-band duplexer.** The natural duplexer for
   two separated bands is a **band diplexer**, or — simpler and better — **two separate band
   antennas**. A **circulator** is a narrowband ferrite device (typ. 10–20 % bandwidth) and a
   2.4 GHz unit has **no 433 MHz path at all**; it cannot route two different bands. It is not
   a weaker option here, it is the wrong device class.
3. **Measured-class isolation:** two separate band antennas ≈ **68 dB** TX→RX isolation
   (20 dB spacing/pattern + 3 dB own-antenna mismatch + 45 dB RX band-pass rejection); a band
   diplexer ≈ 60 dB; a single 2.4 GHz circulator ≈ 20 dB **at one band only and nothing at the
   other**.

**Residual hazard, quantified.** The ground's own 2.4 GHz TX leaking into its own 433 MHz RX
lands at the LNA input nominally **−56 dBm** (−36 dBm pessimistic; −38 dBm even with a +30 dBm
PA) — i.e. **56–78 dB below** the owned TQP3M9037's +20 dBm P1dB and +22 dBm CW input rating.
The hazard is therefore managed by a **433 MHz band-pass filter placed before the LNA**, not by
a circulator and not by a limiter.

**The uplink is attenuated, not amplified.** On the uplink, the licence-exempt ceiling at
FLRC-max bandwidth (2.666 MHz) is **14.26 dBm EIRP** under the 10 dBm/MHz PSD rule
(`min(20, 10 + 10·log10 BW)`); with an 11.1 dBi ground antenna that is only **+3.2 dBm
conducted**, so the LR2021's own **+12 dBm** HF PA must be turned **down ≈9 dB**. A ground PA
would push the station *through* the legal ceiling for no gain.

## Decision

**D1 — Two separate band antennas and NO circulator.** The gateway receives 433 MHz on one
antenna and transmits 2450 MHz on a different one. No T/R switch, no circulator, no duplexer.
Two band antennas = full duplex for free.

**D2 — If a single dual-band feedline is ever mandatory, use a band diplexer, never a
circulator.** A circulator is **not a candidate** for this duplex.

**D3 — The 433 MHz RX front end's primary protection is a 433 MHz band-pass filter placed
before the LNA.** The owned LNA is wideband and would otherwise amplify 2.4 GHz TX leakage into
the mixer. A PIN-diode limiter (10–20 dBm threshold class) is **optional insurance** only
(third-party 2.4 GHz transmitters at close range), not the primary mechanism.

**D4 — The 2.4 GHz uplink power control is a digital step attenuator (0–31.75 dB, 0.25 dB
step), not a PA.** A PA is permitted **only** on a higher legal footing (amateur / fixed-link)
or with an omni antenna, and even then the DSA stays in line for the closed loop.

**D5 — The power-control closed loop is driven by GNSS range or the 433 MHz downlink RSSI.**

## Invariants

- **INV-1.** RX and TX are on **different bands**; no component in the duplex path may be
  required to pass both 433 MHz and 2.45 GHz through one narrowband element.
- **INV-2.** Full duplex — **no** half-duplex T/R switch in the gateway path.
- **INV-3.** A **433 MHz BPF sits between the RX antenna and the LNA**; the wideband LNA never
  sees out-of-band energy un-filtered.
- **INV-4.** No PA is placed in the uplink chain unless a legal footing **above** the ISM/PSD
  ceiling is documented; the ISM path uses the DSA.
- **INV-5.** The 2.4 GHz uplink EIRP is computed from the **occupied bandwidth** via the
  10 dBm/MHz PSD rule, never asserted as a flat 20 dBm.

## Consequences

### Positive
- Deletes a purchase (no circulator, ≈ EUR 34–116 saved) and the insertion loss a circulator
  would add (0.3–0.5 dB **in both** directions).
- ≈ 68 dB of duplex isolation — far more than any single-band circulator gives — with no
  switching transients and no switching latency.
- The controllable-gain element is a **≈ EUR 19 DSA** instead of a PA + driver + heatsink.

### Costs / risks
- **Two antennas and two feedlines**: more mast hardware and mast wind load than one antenna
  (the positioner/gain-per-dollar records own that side — ADR-077/078).
- A **433 MHz BPF is now a required part** and adds a small in-band insertion loss.
- **Service radius is capped by the ISM ceiling.** Under the PSD reading the compliant uplink
  reaches only **≈4–5 km at every FLRC rate** (the EIRP ceiling falls as 10·log10 BW while
  sensitivity improves only 1–2 dB per FLRC step). Under the flat-20 dBm reading the uplink
  reaches much further. **The two readings disagree and neither is retired here** — see Open
  items.
- The 68 dB isolation figure is a composite of norms, **not a measurement on this hardware**;
  the first build must measure S21 between the two antennas.

## Open items (not assumed)

- **`TODO(unverified)` — the 2.4 GHz uplink legal ceiling, a named defect with no winner.**
  `docs/LINK-BUDGET-LICENCE-EXEMPT.md` (and ADR-081's ladder) use a flat **20 dBm EIRP**;
  `design/rf-shopping-list` finds the **10 dBm/MHz PSD** condition caps FLRC-max at
  **14.26 dBm EIRP**. This is a ~6 dB disagreement that decides the uplink's range. Per the
  repo rule (a contradiction that names no winner is a **DEFECT**), it is **flagged, not
  resolved**; one read of the current ERC Rec 70-03 Annex 1 / EN 300 328 clause closes it.
- **`TODO(unverified)`** the exact ERC Rec 70-03 Annex 1 row (inherited).
- **`TODO(unverified)`** the measured S21 isolation of the chosen antenna pair.
- **`TODO(unverified)`** whether the operator's owned T/R hardware (2.4 GHz amplifier +
  circulator) is to be shelved or repurposed; this record makes it **not required**.

## Relation to other ADRs

- **ADR-034** owns the balloon-side band split this mirrors; if the two ever disagree on the
  band assignment, **ADR-034 is the owner**.
- **ADR-071** is the design basis (full duplex).
- **Supersedes** the off-branch record `070-ground-station-duplex-t-r-architecture`
  (`design/rf-shopping-list`) — same decision, fresh number, and this record adds the
  supersession/defect statements that record lacked.
- **Supersedes** the "adopt a ground 2.4 GHz PA for the uplink" half of the off-branch
  `068-ground-station-amplifier-vs-antenna` (`design/amplifier-substitution`): under the
  EIRP/PSD ceiling the uplink needs **attenuation, not amplification** (D4).

## For future sessions

- **One-line rule:** *two band antennas, no circulator* — a narrowband circulator cannot duplex
  433 MHz and 2.45 GHz; and the ISM uplink is **attenuated**, not amplified.
- **Read alongside:** ADR-034 (band split), ADR-071 (full duplex), ADR-079 (the LNA the BPF
  protects).
- **Reproduce:** `python3 docs/analysis/rf_shopping_list_model.py`.
