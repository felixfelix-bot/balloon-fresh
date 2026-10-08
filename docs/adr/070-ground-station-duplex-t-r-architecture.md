# ADR-070 — Ground-station internet-gateway duplex / T-R architecture: **two band antennas, no circulator**; the 2.4 GHz uplink is **attenuated, not amplified**

- **Status:** **Proposed** (agent-authored draft, 2026-10-08) — `Proposed` is **not** frozen;
  this is **not** an operator decision, orders nothing, and freezes no fab.
- **Date:** 2026-10-08
- **Decision owner:** Felix (operator)
- **Author:** Hermes agent (worker), branch `design/rf-shopping-list`
- **Evidence:** `docs/analysis/rf-shopping-list-and-duplex-architecture.md` +
  `docs/analysis/rf_shopping_list_model.py` (prints every number below; run
  `python3 docs/analysis/rf_shopping_list_model.py`).

**Numbering note.** `scripts/adr_next_number.py` returns **066**, but **066 is already
claimed** on `design/ground-station-lowpower-link` *and* `design/ground-station-flrc-max`;
**067** on `design/ground-station-flrc-max` *and* `design/positioner-lowcost`; **068** on
`design/gain-per-dollar`; **069** on `design/tier0-accessible` (verified 2026-10-08 with a
prefix-anchored scan of `docs/adr/0(6[6-9]|7[0-9])-` across every `github/*` branch). None
of those has merged, so those numbers are not free. **070 is the next free number and is
taken here.**

**Related (stable references only):**

- `docs/adr/034-radio-band-split-433-tx-2g4-rx.md` — the band split this ADR builds on.
- `docs/adr/041-rf-frontend-licence-exempt.md` — the licence-exempt front end.
- `docs/adr/039-licence-exempt-433-design-point.md` — the 433 design point.
- `docs/analysis/radio-legal-power-limits.md` + `docs/analysis/radio_power_limits_model.py`
- `docs/2G4-LINK-BUDGET-ANALYSIS.md`
- ADR-066 / ADR-067 (433 downlink FLRC-max) — **not** re-derived here.
- `docs/ssot/parameters.json`

---

## Context

The ground station is an **internet gateway** for the balloon **bent pipe**: ground users
reach the internet through the balloon. That makes the link **bidirectional and
simultaneous**, and it fixes the **per-direction bands at the ground end**:

| At the ground station | Band | Direction |
|---|---|---|
| **RECEIVE** | **433 MHz** | balloon → ground (downlink) |
| **TRANSMIT** | **2450 MHz** | ground → balloon (uplink) |

Two consequences follow, and they are the whole of this decision:

1. **Full duplex is required → a half-duplex T/R switch is ruled out.** Both directions run
   at once, on two different bands.
2. **The two bands are 5.65× apart (2.5 octaves).** The natural duplexer for two bands is a
   **band diplexer** or — simpler and better — **two separate band antennas**. A
   single-band **circulator** is a narrowband ferrite device (typ. 10–20 % bandwidth) and a
   2.4 GHz unit has **no 433 MHz path**; it cannot route two different bands at all.

Verified numbers (model §0, §0b):

- Two separate band antennas give **≈ 68 dB** TX→RX isolation (20 dB spacing/pattern +
  3 dB own-antenna mismatch + 45 dB RX-BPF rejection). A band diplexer gives ≈ 60 dB. A
  single 2.4 GHz circulator gives **≈ 20 dB at one band, nothing at the other**.
- The residual hazard — the ground's own 2.4 GHz TX leaking into its own 433 MHz RX — is
  **−56 dBm** at the LNA input nominally (−36 dBm pessimistic, −38 dBm even with a +30 dBm
  PA), i.e. **56–78 dB below** the owned TQP3M9037's +20 dBm P1dB and +22 dBm CW input
  rating. Model §0b.
- On the uplink, the licence-exempt **EIRP ceiling at FLRC-max bandwidth** (2.666 MHz) is
  **14.26 dBm EIRP** (`min(20, 10 dBm/MHz + 10·log₁₀ BW)`); with an 11.1 dBi ground antenna
  that is only **+3.2 dBm conducted** — the LR2021's own **+12 dBm** HF PA must be turned
  **down ~9 dB**. Model §1b.
- Because the EIRP ceiling *falls* as 10·log₁₀(BW) while sensitivity improves only ~1–2 dB
  per FLRC step, the uplink reaches **≈ 4–5 km at every FLRC rate** (model §2b).

## Decision

**D1 — Use two separate band antennas and NO circulator.** The gateway receives 433 MHz on
one antenna and transmits 2450 MHz on a different one. No T/R switch, no circulator, no
duplexer. Two feeds = full duplex for free.

**D2 — If a single dual-band feedline is ever mandatory, use a band diplexer, never a
circulator.** A circulator is not a candidate for a two-band duplex in this design.

**D3 — The primary protection for the 433 MHz RX front end is a 433 MHz band-pass filter
*placed before the LNA*, not a circulator and not a limiter.** The owned TQP3M9037 is
wideband (0.7–6 GHz) and would otherwise amplify the ground's 2.4 GHz TX leakage by +20 dB
into the mixer. Filter first; a PIN-diode limiter (10–20 dBm threshold class) is optional
insurance only.

**D4 — The 2.4 GHz uplink power control is a *digital step attenuator* (0–31.75 dB,
0.25 dB step), not a PA.** Under the licence-exempt ISM PSD ceiling the required conducted
power with a directional ground antenna is *below* the LR2021's own +12 dBm HF PA, so a PA
is counter-productive. A PA is permitted **only** on a higher legal footing (amateur /
fixed-link) or with an omni antenna, and then the DSA remains in line for the closed loop
(≈ 40–45 dB range: 40 dB of path-loss swing 0.5→50 km, plus trim).

**D5 — The closed-loop power reference is range or downlink RSSI.** The loop drives the DSA
(and the radio's own 0.5 dB-step TX power) from GPS range or the 433 MHz downlink RSSI,
closing the loop that keeps the balloon receiver from being overloaded at close range.

## Invariants

- **INV-1.** RX and TX are on **different bands**; no component in the duplex path may be
  required to pass both 433 MHz and 2.45 GHz through a single narrowband element.
- **INV-2.** Full duplex — **no** half-duplex T/R switch in the gateway path.
- **INV-3.** A **433 MHz BPF sits between the RX antenna and the LNA**; the wideband LNA
  never sees out-of-band energy un-filtered.
- **INV-4.** No PA is placed in the uplink chain unless a **legal footing above the ISM/PSD
  ceiling** is documented in the BOM/ADR set; the ISM path uses the DSA, not a PA.
- **INV-5.** The 2.4 GHz uplink EIRP is computed from the **occupied bandwidth** via the
  10 dBm/MHz PSD rule, not asserted as a fixed 20 dBm.

## Consequences

### Positive

- **Deletes a purchase** (no circulator, ~€34–116 saved) and the loss a circulator would add
  (0.3–0.5 dB in *both* directions).
- **≈ 68 dB** duplex isolation, far more than any single-band circulator gives, with **no
  switching transients** and no switching latency.
- The controllable-gain element is a **€19 DSA** instead of a PA + driver + heatsink.
- Two simple narrowband antennas beat one dual-band compromise feed for both bands.

### Costs / trade-offs

- **Two antennas and two feedlines** — more mast hardware and mast wind load than one
  antenna. (The sibling positioner/gain-per-dollar work owns that side.)
- A **433 MHz BPF is now a required part** (it was not in the original sketch) and it adds a
  small in-band insertion loss.
- **Range is capped at ≈ 4–5 km** by the ISM EIRP/PSD ceiling at max FLRC throughput — the
  gateway is a **local** service unless the operator moves to a higher legal footing.
- **`TODO(unverified)`**: the 68 dB isolation is a composite of norms, not a measurement on
  this hardware; the first build should measure S21 between the two antennas.

## Rollout / PR sequence

**TBD — implementation not yet started.** No PR sequence is committed. This ADR records the
architecture; it orders nothing and freezes no BOM. When the operator accepts it, the
antenna/filter/DSA selections in
`docs/analysis/rf-shopping-list-and-duplex-architecture.md` §6 become the BOM input.

## Notes

- The **brief's premise that FLRC is "Semtech fast chirp" is corrected** in the companion
  analysis: the LR2021 datasheet §18.1 states FLRC is **GMSK + forward error correction and
  interleaving**. The Red Pitaya cannot generate it directly (DAC DC–60 MHz), and no public
  FLRC PHY reverse-engineering comparable to the gr-lora LoRa precedent is known
  (`TODO(unverified)` — absence of evidence, search backends bot-blocked this fleet).
- The **cycle of sibling ground-station ADRs is deliberate**: this ADR settles the *T-R /
  duplex* question (different bands, full duplex), while ADR-066/067 (433 downlink FLRC-max),
  068 (gain-per-dollar) and 069 (Tier-0) settle adjacent questions. If two records later
  disagree on the band split, the owner is `docs/adr/034-*`.
