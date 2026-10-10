# Half-duplex, the bent pipe, and the 433 MHz high-rate downlink — four answers

- **Scope:** the operator's four pointed system-design questions, answered from this repo's
  own committed files only. Every claim below carries a file path (and, where useful, a line).
  No number here is invented; where the repo has no figure, it says so.
- **Status:** analysis only. This document makes no decision and freezes no hardware.
- **Author:** Hermes subagent, branch `analysis/half-duplex-answers`, worktree
  `~/worktrees/bf-halftime`.
- **Load-bearing in-repo sources:** `docs/adr/034-radio-band-split-433-tx-2g4-rx.md`,
  `docs/adr/035-tdm-radio-schedule.md`, `docs/adr/071-ground-station-gateway-design-basis.md`,
  `docs/adr/072-band-split-duplex-two-antennas-no-circulator.md`,
  `docs/adr/073-433-downlink-flrc-max-lora-rejected.md`,
  `docs/adr/079-amplifier-led-receive-chain-owned-tqp3m9037-lna.md`,
  `docs/coordination/CONSULTANT-PLAN-REVIEW-V2.md`,
  `docs/coordination/ARCHITECTURE-FREERTOS-TASKS.md`,
  `docs/analysis/433-lna-substitution-and-amateur-licence.md`,
  `docs/analysis/rf-shopping-list-and-duplex-architecture.md`,
  `docs/analysis/free-balloon-mass-threshold-DE.md`,
  `docs/licence-exempt-design-point.md`.

---

## Q1 — Is a bent pipe simultaneous by definition, and can it be, given the radio is half-duplex?

**Bottom line: the bent pipe *as this program defines it* requires simultaneity, but it is a
property of the architecture, not of any radio. A single LR2021 is half-duplex and can never be
simultaneous. Simultaneity therefore requires a second radio chain — which is exactly what
ADR-034 already mandates. Time-division (TDD) on one radio is the fallback, and it costs the
very simultaneity the gateway is built on.**

**1a. Simultaneity is a stated requirement of the gateway's bent pipe (not of the words "bent
pipe" alone).** `docs/adr/071-ground-station-gateway-design-basis.md` Context items 1–3 and D1/D2
fix it:

- "The link is bidirectional and simultaneous" (Context item 1).
- "The balloon is a bent pipe, not a store-and-forward node … relayed with minimal processing
  latency" (Context item 2).
- "Full duplex is therefore a requirement, not a preference — and it rules out a half-duplex T/R
  relay" (Context item 3; D2 repeats "REJECTED").
- **INV-1:** "Both directions are live simultaneously; nothing in the duplex path may be
  time-shared between them."

So in this repo, "bent pipe" is coupled to "full duplex" by decision, not by etymology. A
store-and-forward relay is also a relay; the gateway service model is what forces simultaneity.

**1b. One LR2021 can never be simultaneous. The repo says so three ways:**

- `docs/coordination/CONSULTANT-PLAN-REVIEW-V2.md` CONCERN-4: "The LR2021 is half-duplex — it
  cannot TX and RX simultaneously. In the current code, TX is synchronous … **During a TX,
  nothing can receive.**"
- `docs/coordination/ARCHITECTURE-FREERTOS-TASKS.md`: "Half-duplex: can't TX and RX
  simultaneously. Accept packet loss during TX."
- `docs/adr/034-radio-band-split-433-tx-2g4-rx.md` Context: the LR2021 "is **half-duplex**: it
  cannot TX on one port while RX-ing on the other, so the two directions are mutually exclusive
  in time by construction." ADR-034 also kills the hope that one module's two 50 Ω ports give
  two transceivers: "AD-029 D2 … That is true of the ports; it is **not** true of the transceiver
  behind them."

**1c. So true simultaneous FDD requires a second radio chain — and the design already has one.**
`docs/adr/034-...md` D1 puts TX on the `LoRa2021F33-2G4` (433 MHz, 2 W port) and RX on a separate
bare `LoRa2021` (2.4 GHz), "two independent chips", because "Two RF ports do not make two
transceivers." `docs/analysis/PROGRAM-GAP-ANALYSIS.md` §bent pipe states the same: "Two radio
chips are needed because the LR2021 is half-duplex (ADR-071 D2)."

**Cost of the second chain (what the repo budgets):**

- **Mass:** the bare `LoRa2021` castellated module is **1.2 g** as the committed mass line item
  (`docs/analysis/two-variant-mass-budget.md` row A4, cited from `PAYLOAD-WEIGHT-ESTIMATES.md`
  §3, "LR2021 bare, 1–2 g"). The relay study prices an added radio at **+0.5 g per additional
  LR2021** (`docs/adr/014-bent-pipe-fpga-bridging.md` Consequences; `docs/adr/015-three-board-hardware-strategy.md`
  gives "+0.8 g (FPGA+flash) + 0.5 g per additional LR2021").
- **Power:** **+3–25 mA during active operation, daytime only** for the coprocessor-plus-radio
  path (`docs/adr/014-...md` Consequences, power-gated by the MCU).
- **Board area / I/O:** a second radio costs **+4 GPIO** (`docs/adr/040-v9-radio-site-optionality.md`;
  `docs/adr/108-f33-sx1280-pin-plan.md` — "The +4 GPIO budget is spent, in full, on the second
  radio"). A board-area figure for the second radio site is **not itemised anywhere in the repo**
  (`docs/analysis/two-variant-mass-budget.md` marks the module part itself `TODO(unverified)`).

**1d. The TDD alternative: what it costs at a 300 km hop.** The committed design slant range is
**300 km** (`docs/LINK-BUDGET-LICENCE-EXEMPT.md` provenance rows; `docs/adr/037-mcu-s3-no-fem.md`
uses it for the link). The costs are not dominated by propagation:

- **Propagation (arithmetic, not a repo figure):** 300 km one-way at c ≈ 299,792,458 m/s ≈ **1 ms**,
  so a round trip ≈ **2 ms**. This is a physical constant, not an in-repo measurement.
- **Serialisation (the real cost):** one half-duplex radio cannot receive while it transmits, so a
  packet arriving during the TX window is lost — CONCERN-4's "During a TX, nothing can receive",
  whose stated resolution is "Accept packet loss during processing." A TDD relay interleaves the
  two directions in time, which ADR-071 D2 says "breaks TCP/IP simultaneity and the bent pipe".
- **Scheduling floor:** ADR-035's TDM schedule bounds the duty cycle, and the repo's TDMA transport
  records the frame-level latency explicitly: "TDMA frame (2s) + LoRa airtime + FIPS overhead.
  **Total RTT: 2-6s**" (`docs/adr/106-e-hash-relay-transport-layer.md`). ADR-014's per-hop air time
  is **0.6 ms** (`docs/adr/014-...md` relay arithmetic), confirming that air time is not the
  problem; the *interleaving* is.

**Verdict Q1: simultaneous bent pipe = yes, but only on two chips. One LR2021 = no, ever. TDD on
one radio = the fallback that ADR-071 D2 explicitly rejects and CONCERN-4 prices in dropped
packets.**

---

## Q2 — Does "balloon ALWAYS transmits on 433 MHz and listens on 2.4 GHz" work?

**Bottom line: yes as a band-direction assignment — it is literally ADR-034 — but it is coherent
only with two chips, the high-rate leg correctly rides 433, the 2.4 GHz return pays ~15 dB more
loss and must be closed on the ground, and "ALWAYS transmits" is not literal: the legal and
energy budgets bound the duty cycle hard.**

**2a. This plan *is* ADR-034.** `docs/adr/034-radio-band-split-433-tx-2g4-rx.md` D1:
**TX = 433 MHz** on the `F33-2G4`'s 2 W sub-GHz port; **RX = 2.4 GHz** on a separate bare
`LoRa2021`. It is the mirror of the ground station (`docs/adr/071-...md` INV-2: ground RX 433 /
ground TX 2.45 GHz). The operator's wording selects exactly this record.

**2b. It needs two radios to be simultaneous — see Q1.** ADR-034 D1 states the whole point of the
split is simultaneity ("the one thing a single half-duplex module could never offer"), and ADR-035
D5 is honest that the gain is *not* parallel throughput: "N radios do NOT give N× throughput."

**2c. The traffic asymmetry is the reason the high-rate leg rides 433.** At the committed 300 km:

- FSPL @ 433 MHz = **134.7 dB** vs FSPL @ 2400 MHz = **149.6 dB** (`docs/LINK-BUDGET-LICENCE-EXEMPT.md`
  rows; computed by `tools/link_budget.py`) → **14.9 dB lower path loss at 433** (`docs/adr/041-rf-frontend-licence-exempt.md`
  D1: "the **14.9 dB lower path loss at 433 vs 2.4 GHz**").
- The high-rate direction is the **433 MHz downlink**, fixed as **FLRC at maximum throughput**
  (`docs/adr/073-433-downlink-flrc-max-lora-rejected.md` D1). Putting the high-rate stream on the
  low-loss band is correct.
- The **2.4 GHz return** has ~15 dB *more* loss and is the **binding** link (`docs/adr/041-...md`
  D1: "the 2.4 GHz uplink is the binding direction"). The design absorbs that on the *ground*
  (big dish: `docs/adr/073-...md` D2, `docs/adr/078-...md`) and keeps the airborne 2.4 GHz RX
  **deliberately unamplified** (`docs/adr/034-...md` D1 item 2).

**2d. "ALWAYS transmits" is not literal, and this matters.** What each direction actually is:

| Direction | Band | Balloon role | Ground role |
|---|---|---|---|
| downlink | 433 MHz | TX (F33-2G4) | RX: Yagi → 433 BPF → LNA → RX (`docs/analysis/PROGRAM-GAP-ANALYSIS.md` §blocks) |
| uplink | 2.4 GHz | RX (bare LoRa2021, unamplified) | TX: radio → BPF → DSA → BPF → antenna (`docs/analysis/PROGRAM-GAP-ANALYSIS.md`) |

The balloon is not continuously on: the licence-exempt design runs a **~1.7 % duty cycle — 1 s per
60 s** (`docs/licence-exempt-design-point.md` §7); ADR-035 bounds the 433 TX slot and gates it on
stored energy (`docs/adr/035-tdm-radio-schedule.md` D7/D8); and on the licence-exempt footing the
**2 W F33 is over-limit** (cap ≤10 mW ERP; the bare module's own 22 dBm is also over-limit —
`docs/licence-exempt-design-point.md` §6). 2 W on 433 is only available on the **amateur** footing,
which is a separate, unresolved gate (`docs/adr/034-...md` open item "Legality of 2 W on 433 MHz in DE").

**2e. Two further republic-internal consequences to keep in view.**

- **868 is forbidden as the RX partner:** 433 × 2 = 866 MHz falls inside the 868 MHz band — a
  self-inflicted second-harmonic collision (`docs/adr/034-...md` D3). 2.4 GHz is the safe partner.
- **A bent pipe carrying third-party traffic collides with the amateur rules** (AFuG §5(4)/(5):
  no commercial purpose, no third-party traffic) — `docs/analysis/433-lna-substitution-and-amateur-licence.md`
  §"Also flagged": "the amateur footing buys uplink power at the cost of the service model."

**Verdict Q2: the frequency plan works and is the committed one (ADR-034), but it is a
two-chip plan; 433 carries the high-rate downlink for good physical reason; the 2.4 GHz return is
the binding link and is closed on the ground; and "always transmits" must be read as "433 is the
transmit band", bounded to a ~1.7 % duty cycle on the licence-exempt footing.**

---

## Q3 — For a bent pipe on two bands: circulator or band-split duplexer?

**Bottom line: neither. A circulator is the wrong device class (narrowband; no dual-band path) and
the correct duplexer is band separation — two separate band antennas (≈68 dB isolation), or a band
diplexer if one feedline is mandatory. If a receive LNA is used it must be a 433-specific part at
the masthead; the owned wideband LNA does not cover 433, and coax ahead of the LNA degrades the
system noise figure ≈1:1.**

**3a. The repo's answer is explicit: no circulator.**

- `docs/adr/072-band-split-duplex-two-antennas-no-circulator.md` D1: "**Two separate band antennas
  and NO circulator.** … No T/R switch, no circulator, no duplexer." D2: a circulator is "**not a
  candidate**". Context: "a **circulator** is a narrowband ferrite device (typ. 10–20 % bandwidth)
  and a 2.4 GHz unit has **no 433 MHz path at all**; it cannot route two different bands."
- `docs/analysis/rf-shopping-list-and-duplex-architecture.md` §1: "**DO NOT BUY A CIRCULATOR** …
  a single-antenna circulator cannot be used at all". Isolation table: two separate band antennas
  **≈68 dB** (RECOMMENDED); band diplexer on one feedline **≈60 dB**; single-band circulator
  **≈20 dB at one band and nothing at the other** (NOT APPLICABLE).
- ADR-072 INV-1: "no component in the duplex path may be required to pass both 433 MHz and
  2.45 GHz through one narrowband element." ADR-071 INV-2 fixes the two bands.

**3b. Which LNA, and the noise figure.** The repo's measured/documented figures:

- **Owned part, Qorvo TQP3M9037:** gain 20 dB, **NF 0.4 dB** — but its vendor band is **0.7–6 GHz**
  and it does **not cover 433 MHz**. The repo resolves the dispute *against* it:
  "**NO — the dispute resolves AGAINST it**" (`docs/analysis/433-lna-substitution-and-amateur-licence.md`
  §0.2 Q1; band rows at §1). It stays off the 433 path.
- **Mini-Circuits ZX60-P103LN+:** **NF 0.5 dB**, 50–3000 MHz, ~€110 — the "CHEAPEST WORKABLE"
  candidate, but wideband (so it needs the 433 BPF in front) and a bare SMA module, not a masthead
  box (`docs/analysis/433-lna-substitution-and-amateur-licence.md` LNA ledger + §1.1).
- **Recommended:** **SSB Electronic LNA ISM 433 MHz — NF 0.7 dB**, 433–435 MHz, gain 20 dB typ,
  €257 (`docs/analysis/433-lna-substitution-and-amateur-licence.md` §0.3/§1.1). ADR-079 records
  this as the masthead LNA the BPF protects (`docs/adr/079-amplifier-led-receive-chain-owned-tqp3m9037-lna.md`).

**3c. Does coax degrade NF 1:1, and must the LNA be masthead? Yes and yes.**

- Friis: a lossy element *ahead* of the first amplifier adds its loss directly to the system noise
  figure; the repo's numbers are exactly the feedline loss counted. Shack-end penalty:
  **1.2 dB (433 MHz, 15 m Airborne 10)**, **2.5 dB (2.4 GHz, 15 m Ecoflex 15)**, **4.9 dB
  (2.4 GHz, 15 m Aircell 7)** — i.e. "**20–50 % of the LNA's whole +6.8…+12.3 dB (central +9.7 dB)
  benefit**" (`docs/analysis/ground-station/REPORT-design-rf-gaps-harmonics-diy.md` Part C;
  `docs/analysis/ground-station/PROGRESS-design-rf-gaps-harmonics-diy.md`). Frozen as ADR-079
  **INV-1: "The receive LNA is at the masthead, ahead of the feedline."**
- Additionally the **433 BPF must precede the LNA** (ADR-072 INV-3; ADR-079 INV-2): the LNA is
  wideband and would otherwise amplify the ground's own 2.4 GHz TX leakage. No circulator and no
  limiter is the primary protection; the measured acceptance test is the recorded criterion
  (ADR-072 "Acceptance criterion": measured S21, BPF rejection, and an end-to-end desense test).

**Verdict Q3: neither device. Duplex by band separation (two band antennas ≈68 dB, or a diplexer
≈60 dB if forced onto one feedline). The wideband owned LNA is out on 433; use a 433-specific part
(SSB ISM 433, NF 0.7 dB) at the masthead, because coax ahead of the LNA costs ≈1 dB of system NF
per dB of feedline loss.**

---

## Q4 — The 2 MHz FLRC / 1.74 MHz band conflict: can the balloon really transmit its high-rate stream on 433 MHz?

**Bottom line: no.** A 2 MHz FLRC signal cannot legally occupy 433.05–434.79 MHz. The band is only
**1.74 MHz wide**, and even on the amateur footing the maximum legal occupied bandwidth on 70 cm is
**2 MHz**, while FLRC-max is **2.666 MHz**. The highest legal FLRC rate on 433 is **1300 kbps
(1.333 MHz)**. ADR-073's committed FLRC-max downlink therefore cannot ride 433 legitimately — this
is an unresolved collision, not a link-budget problem.

**4a. The band is 1.74 MHz wide.** 433.05–434.79 MHz = 1.74 MHz = 0.40 % of carrier
(`docs/analysis/ground-station-amplifier-hypothesis-check.md` §2.1: the priced narrowband LNA
"forbids any operation outside" the "433.05–434.79 MHz ISM allocation (1.74 MHz, 0.40 %)";
`docs/licence-exempt-design-point.md` §3; `docs/adr/039-licence-exempt-433-design-point.md`).
A 2 MHz signal is wider than the band it would have to sit inside.

**4b. The maximum legal occupied bandwidth on 70 cm, from the repo's own regulatory read.**
`docs/analysis/433-lna-substitution-and-amateur-licence.md` §2.1–2.2 quotes **AFuV Anlage 1,
Lfd. Nr. 18 + Zusatzbestimmung 7**: 430–440 MHz is the primary amateur allocation, and
"Maximal zulässige belegte Bandbreite … **2 MHz**". Against the FLRC ladder (DSB bandwidths from
the LR2021 datasheet table):

| FLRC mode | BW (DSB) | Legal on 70 cm (≤ 2 MHz)? |
|---|---:|---|
| **2600 kbps (FLRC-max, committed by ADR-073 D1)** | **2.666 MHz** | **NO** |
| 2080 kbps | 2.222 MHz | **NO** |
| **1300 kbps** | 1.333 MHz | **YES — highest legal rate** |
| 1040 kbps | 1.333 MHz | YES |
| 650 kbps | 0.740 MHz | YES |

The same document's actionable list states it flatly: "**Cap the 433 downlink at 2 MHz occupied
bandwidth → FLRC 1300 kbps maximum**" (§2.4 item 5), and warns the impact is "a **rate/airtime
consequence**, not merely a paperwork one, and it must be re-run through the link budget" (§2.2).

**4c. On the licence-exempt footing it is worse, not better.** The German SRD entries
(`docs/analysis/free-balloon-mass-threshold-DE.md` §7.1, from Vfg. 91/2025 Tabelle 2):

- **44a** 433.05–434.79 MHz: **1 mW ERP**, no condition (the unconditional limit).
- **44b** 433.05–434.79 MHz: **10 mW ERP**, but "Arbeitszyklus: ≤ 10 %".
- **45c** **434.04–434.79 MHz**: 10 mW ERP, duty ≤ 100 % **only at a bandwidth ≤ 25 kHz**.

So the only continuous-duty licence-exempt window caps occupied bandwidth at **25 kHz** — five
orders of magnitude below FLRC-max — and the whole licence-exempt band is 1.74 MHz, narrower than
a 2 MHz signal. The licence-exempt design point's own duty-cycle figure is **~1.7 %** anyway
(`docs/licence-exempt-design-point.md` §7).

**4d. This is an unreconciled collision in the repo.** `docs/adr/073-433-downlink-flrc-max-lora-rejected.md`
D1 fixes the 433 downlink at "FLRC at maximum throughput" and rejects LoRa as too slow, while its
own "Costs / risks" and the LNA/licence analysis cap the same band at 2 MHz occupied BW. ADR-073's
INV-2 notes FLRC-max at range implies the F33; it does not address the bandwidth cap. The two
statements are not reconciled anywhere, and `docs/analysis/433-lna-substitution-and-amateur-licence.md`
§2.2 flags the rate consequence as something that "must be re-run through the link budget".

**Verdict Q4: no. The high-rate FLRC-max stream cannot legally be transmitted on 433 MHz. The band
is 1.74 MHz wide; the amateur occupied-BW cap is 2 MHz; FLRC-max is 2.666 MHz. The best legal
433 downlink rate is FLRC 1300 kbps. Either the 433 modulation is re-decided, or the high-rate
leg moves off 433, or the regulatory footing changes — and none of those is settled in-repo.**

---

## Cross-cutting finding

The four answers share one structure: **every "simultaneous", "always-on", or "max-rate" property
the operator's plan assumes is bounded by something the repo already recorded.** The simultaneity
is bought by a second chip (ADR-034); the duty cycle is bounded by energy and by the SRD entries;
the duplexing is by band separation, never a circulator (ADR-072); and the high-rate 433 downlink
collides with the 2 MHz occupied-bandwidth cap (AFuV Anlage 1 Zusatzbestimmung 7). None of these
is a link-budget shortfall — each is an architectural or regulatory gate that a session should
settle explicitly rather than discover in the field.

## Sources (file paths cited above)

- `docs/adr/014-bent-pipe-fpga-bridging.md`, `docs/adr/015-three-board-hardware-strategy.md`
- `docs/adr/034-radio-band-split-433-tx-2g4-rx.md`, `docs/adr/035-tdm-radio-schedule.md`
- `docs/adr/039-licence-exempt-433-design-point.md`, `docs/adr/040-v9-radio-site-optionality.md`
- `docs/adr/041-rf-frontend-licence-exempt.md`, `docs/adr/071-ground-station-gateway-design-basis.md`
- `docs/adr/072-band-split-duplex-two-antennas-no-circulator.md`
- `docs/adr/073-433-downlink-flrc-max-lora-rejected.md`
- `docs/adr/079-amplifier-led-receive-chain-owned-tqp3m9037-lna.md`
- `docs/adr/106-e-hash-relay-transport-layer.md`, `docs/adr/108-f33-sx1280-pin-plan.md`
- `docs/coordination/CONSULTANT-PLAN-REVIEW-V2.md`, `docs/coordination/ARCHITECTURE-FREERTOS-TASKS.md`
- `docs/analysis/433-lna-substitution-and-amateur-licence.md`
- `docs/analysis/rf-shopping-list-and-duplex-architecture.md`
- `docs/analysis/free-balloon-mass-threshold-DE.md`
- `docs/analysis/ground-station-amplifier-hypothesis-check.md`
- `docs/analysis/ground-station/REPORT-design-rf-gaps-harmonics-diy.md`
- `docs/analysis/PROGRAM-GAP-ANALYSIS.md`, `docs/analysis/two-variant-mass-budget.md`
- `docs/licence-exempt-design-point.md`, `docs/LINK-BUDGET-LICENCE-EXEMPT.md`
