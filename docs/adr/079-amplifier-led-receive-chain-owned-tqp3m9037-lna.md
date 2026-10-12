# ADR-079 — Amplifier-led receive chain using the owned TQP3M9037 LNA

- **Status:** **Accepted by operator (2026-10-08) — but CONDITIONAL, not "locked".** The operator
  owns the TQP3M9037 and directed the receive chain to use it, accepting the wide-beam
  noise-temperature penalty. **One contradiction is flagged, not resolved** (D5 / Open items): the
  operator's stated band edge (**0.1 MHz–6 GHz**) is contradicted by the vendor figure captured on a
  sibling branch (**0.7–6 GHz**), and the two disagree on whether the part covers the **433 MHz
  downlink at all**. The independent consultant review (`docs/analysis/plan-review-consultant.md`
  §2 Q3) returned this as a hard condition: **if 0.7–6 GHz is authoritative, the amplifier-led
  433 receive chain does not stand and this record must be reopened** — so the decision is
  **conditional on one datasheet read**, and must not be described as a locked decision until then.
- **Date:** 2026-10-08
- **Decision owner:** Felix (operator)
- **Author:** Hermes subagent (consolidation pass), branch `design/adr-set-groundstation`
- **Related (stable references):** ADR-071 (design basis), ADR-072 (band-split duplex — the BPF
  that protects this LNA), ADR-075 (the gain-per-dollar ledger this chain is scored in), ADR-078
  (the wide-beam trade), ADR-005 (`docs/adr/005-sky66112-fem.md` — the only in-repo LNA NF),
  ADR-041 (`docs/adr/041-rf-frontend-licence-exempt.md`).
- **Evidence:** `docs/analysis/rf-shopping-list-and-duplex-architecture.md` §§5–7 +
  `docs/analysis/rf_shopping_list_model.py` (source branch `design/rf-shopping-list`); the Friis /
  noise-temperature ledger in `docs/analysis/ground-station-amplifier-hypothesis-check.md` §Decision
  2–3 + `docs/analysis/ground_station_amplifier_hypothesis_model.py` (source branch
  `design/amplifier-hypothesis-check`, whose `070-…-amplifier-hypothesis.md` is **superseded by this
  record** / ADR-080 / ADR-072); the amplifier-vs-antenna pricing in
  `docs/analysis/ground-station-amplifier-vs-antenna.md` (source branch `design/amplifier-substitution`,
  whose `068-…-amplifier-vs-antenna.md` is **superseded by this record** / ADR-072). Reproduce:
  `python3 docs/analysis/ground_station_amplifier_hypothesis_model.py`.

**Numbering and collision note.** Numbers **066–070 are claimed on sibling design branches**
(see **ADR-071 §Numbering and collision note** for the full table) and are **not reused**.
`scripts/adr_next_number.py` prints 066 because it is branch-blind. This record takes the fresh
number below (verified free, prefix-anchored, against every `github/*` branch, 2026-10-08).

---

## Context

The ground receive chain must close the **433 MHz downlink**, which is the direction that carries
the system's link budget (ADR-073). The operator owns a **wideband LNA, the Qorvo TQP3M9037**, and
the decision is to buy the receive chain's margin with **amplification at the masthead** rather than
with a larger 433 antenna.

The supporting arithmetic, from the two source branches:

- **An LNA does buy real dB on receive.** It sets the system noise figure (Friis). Against a
  bracketed model it buys **+6.8 … +12.3 dB** of system noise temperature on the 433 downlink
  (central case **+9.7 dB** at `T_ant` = 200 K, receiver NF 8 dB). The operator's earlier premise
  (*"an amplifier makes sense on the transmitter but not on the receiver"*) is **inverted by ~10 dB**
  — an LNA is *the* receive-side device that earns its place.
- **What an LNA cannot buy is cold-sky directivity.** With the LNA fitted, replacing a wide-beam
  antenna with a cold-sky dish removes only the `T_ant` term: **+3.80 dB at 433 MHz**. **LNA and
  directivity are additive, not alternatives.**
- **The wide beam is not free:** a lower-gain ground antenna adds a **~3.17 dB (433 MHz) / 4.63 dB
  (2.4 GHz)** noise-temperature penalty versus a narrow-beam cold-sky antenna. The operator accepts
  this penalty in exchange for the wide beam's pointing tolerance (ADR-078 D2) and for using the
  **owned** part instead of buying antenna gain.
- **The part, as captured in-repo:** Qorvo **TQP3M9037** — gain 20 dB, NF 0.4 dB, **OP1dB +20 dBm**,
  **+22 dBm CW** input ruggedness, integrated shutdown control, **OWNED**. Its bandwidth is the
  flagged item (D5).

## Decision

**D1 — Adopt an amplifier-led receive chain for the 433 MHz downlink: the owned TQP3M9037 LNA at
the masthead, ahead of the receiver.** The LNA is a **receive** device and is placed at the antenna
(masthead), not after a lossy feedline.

**D2 — Buy the wide-beam / smaller-antenna trade explicitly.** A modest 433 antenna plus the LNA is
accepted in place of a larger antenna, accepting the **~4–5 dB** noise-temperature penalty of the
wide beam (the exact figure is 3.17 dB at 433 MHz, 4.63 dB at 2.4 GHz).

**D3 — A 433 MHz band-pass filter sits BEFORE the LNA** (ADR-072 INV-3). The LNA is wideband and
would otherwise amplify the ground's own 2.4 GHz TX leakage by +20 dB into the mixer. A PIN-diode
limiter (10–20 dBm threshold class, ≈ EUR 5–10) is **optional insurance** — the residual leakage is
−56 dBm nominal / −36 dBm pessimistic, 56–78 dB below the LNA's +20 dBm P1dB and +22 dBm CW rating.

**D4 — Score the LNA in the ADR-075 ledger, in the direction that needs the dB.** Its cost is
**≈ EUR 26.4 per needed dB** (against the **+9.7 dB** system improvement) — ~72× the F33's per-dB
cost, but a **real, needed** dB. This is the correct comparison; scoring it on its own 20 dB gain
would make it look free.

**D5 — FLAGGED CONTRADICTION (band edge), not resolved here.** The operator's statement is
**0.1 MHz–6 GHz**, which would cover both 433 MHz and 2.4 GHz. The vendor figure captured on the
source branch is **0.7–6 GHz** (`qorvo.com/products/p/TQP3M9037` via Wayback; the source analysis
§8 explicitly corrects the 0.1 MHz low edge as `TODO(unverified)`), which would **exclude the
433 MHz downlink entirely**. The source analysis simultaneously asserts the correction *"does not
affect the 433 MHz use case"* while placing the LNA in the 433 RX chain — which is self-inconsistent.
**No winner is named; the item is flagged as a defect to close from the datasheet.** If the LF edge
is 0.7 GHz, this ADR reopens and the 433 receive chain needs a **433-capable** device (either a
different LNA or the LNA moved to the 2.4 GHz path only).

## Invariants

- **INV-1.** The receive LNA is at the **masthead**, ahead of the feedline.
- **INV-2.** A **433 MHz BPF precedes the LNA**; the wideband LNA never sees unfiltered out-of-band
  energy.
- **INV-3.** Any amplifier is scored as **money per needed dB in the direction that needs it** —
  never by its own gain, and never across bands (a dB is not fungible across bands).
- **INV-4.** No 2.4 GHz **PA** is placed in the uplink chain (ADR-072 D4/INV-4): the uplink needs
  attenuation, not amplification.
- **INV-5.** No component may be assumed to cover 433 MHz until its datasheet's LF edge is confirmed
  (D5).

## Consequences

### Positive
- The receive chain gains a real **+6.8…+12.3 dB** (central +9.7 dB) of system noise temperature for
  an **owned** part, and the wide beam it permits relaxes the pointing/tracker class (ADR-078).
- The "amplifier-led" direction is now correctly understood: it is a **receive**-led design, and the
  buy-list item is a **filter and a limiter**, not a PA.
- A single, uniform yardstick (INV-3) stops a wrong-band gain block from looking free.

### Costs / risks
- **The band-edge contradiction (D5) is load-bearing** — if the part does not cover 433 MHz, the
  receive chain needs a different device, and this is the first thing to check.
- The wide beam costs **3.17 dB (433) / 4.63 dB (2.4 GHz)** of noise temperature versus a cold-sky
  antenna; the LNA's gain and the antenna's directivity are additive, so choosing the wide beam
  gives up real dB that the LNA must then supply.
- The **antenna's own noise temperature** and the local man-made noise floor are the model's weak
  inputs; if a site's man-made noise dominates, **neither** antenna gain nor an LNA buys dB and the
  receive-side analysis changes.

## Open items (not assumed)

- **Flagged defect — first to close:** the **TQP3M9037 LF band edge** (0.1 MHz vs 0.7 GHz). One
  datasheet read settles it, and it decides whether this record stands as written.
- **`TODO(unverified)`** the **LR2021 receiver NF and maximum input** (inherited).
- **`TODO(unverified)`** the 433 LNA's narrowband behaviour: the sibling analysis prices a **433-only
  masthead LNA (SSB Electronic LNA ISM 433, EUR 257, 0.7 dB NF, ≈0.46 % bandwidth)** as the
  alternative. Owning the wideband part **forecloses nothing** but does **not** supply that
  narrowband selectivity, so the BPF of D3 carries more of the burden.
- **`TODO(unverified)`** the local man-made noise floor at the chosen site.

## Relation to other ADRs

- **Supersedes** the off-branch `070-ground-station-amplifier-hypothesis`
  (`design/amplifier-hypothesis-check`) for the **receive-LNA recommendation**: that record priced a
  **bought** 433-only LNA (EUR 257) and framed the design as "do NOT build an amplifier-led ground
  station". The operator's locked decision is an **amplifier-led receive chain using the owned
  wideband part**; the ledger and the "+0 dB incoherent combining" finding from that record are
  retained and land in ADR-080.
- **Supersedes** the receive-chain half of the off-branch `068-ground-station-amplifier-vs-antenna`
  (`design/amplifier-substitution`) — its "buy the SSB 433 LNA, keep the antenna gain" decision is
  replaced by "use the owned wideband LNA"; its uplink-PA half is superseded by ADR-072 D4.
- **ADR-072** owns the BPF/limiter protection that D3 depends on.

## For future sessions

- **One-line rule:** the 433 receive chain is **amplifier-led with the owned TQP3M9037** and accepts
  a **~4–5 dB** wide-beam noise penalty; **filter first**, and **score any amp in money per needed
  dB** in the direction that needs it.
- **Check first:** the LNA's **LF band edge** (D5) — the one fact that can invalidate this record.
- **Reproduce:** `python3 docs/analysis/ground_station_amplifier_hypothesis_model.py`.
