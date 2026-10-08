# ADR-071 — Ground-station design basis: a full-duplex INTERNET GATEWAY through the balloon as a bent pipe

- **Status:** **Accepted by operator** (Felix, 2026-10-08) — the *architecture direction* is the
  operator's locked decision (a ground station that gives Internet access through the balloon,
  with the ground doing the heavy lifting). The **text** is agent-drafted and has not been
  reviewed by a human as prose; no rollout is authorised by it.
- **Date:** 2026-10-08
- **Decision owner:** Felix (operator)
- **Author:** Hermes subagent (consolidation pass), branch `design/adr-set-groundstation`
- **Related (stable references):** ADR-034 (v9 radio band split — 433 TX / 2.4 GHz RX),
  ADR-035 (TDM radio schedule), ADR-014 (bent-pipe relay for the multi-balloon mesh),
  ADR-039 (licence-exempt 433 design point), ADR-041 (RF front end, licence-exempt),
  ADR-029 (LR2021 module).
- **Companion evidence:** every decision in this set was derived on a sibling design branch.
  The analyses are named in each record's own "Evidence" line; the branch names, tips and
  reproduce commands are in §"The set".

**Numbering and collision note (read before citing this record).** Numbers **066, 067, 068,
069 and 070 are already claimed on sibling design branches** that have not merged:

| number | claimed by | file |
|---|---|---|
| 066 | `design/ground-station-lowpower-link`, `design/ground-station-flrc-max` | `066-ground-station-lowpower-shared-positioner.md` |
| 067 | `design/ground-station-flrc-max`, `design/positioner-lowcost` (**collision**) | `067-flrc-max-433-tx-power-and-coarse-mesh.md` / `067-positioner-architecture.md` |
| 068 | `design/gain-per-dollar`, `design/gain-per-dollar-cliff`, `design/amplifier-substitution` (**collision, three ways**) | `068-ground-station-gain-per-dollar.md` / `068-ground-station-antenna-class-cliff.md` / `068-ground-station-amplifier-vs-antenna.md` |
| 069 | `design/tier0-accessible` | `069-tier0-accessible-ground-station.md` |
| 070 | `design/amplifier-hypothesis-check`, `design/rf-shopping-list` (**collision**) | `070-ground-station-amplifier-hypothesis.md` / `070-ground-station-duplex-t-r-architecture.md` |

`scripts/adr_next_number.py` prints **066** on this branch because it is branch-blind: it scans
only the working tree, which descends from `github/main` and never received 066. Taking 066
would collide the moment any of those branches reaches `main`, and the repo rule is that **no
file is renamed or renumbered to fix a collision** (`docs/adr/INDEX.md`,
`tests/test_adr_numbering.py`). This ADR set therefore **allocates fresh numbers 071–082**
(verified free with a prefix-anchored `docs/adr/07[1-9]-` / `docs/adr/08[0-9]-` scan against
every `github/*` branch on 2026-10-08) and **states the collision rather than resolving it by
rename**. Importing the off-branch files onto this branch as superseded stubs was rejected:
two files at one number in one tree fails
`tests/test_adr_numbering.py::test_numbers_are_not_duplicated`. The supersession of those
off-branch records is declared in each new record and mapped in §"The set" below.

---

## Context

The ground station is not a telemetry receiver. It is the **user-facing end of a service**:
ground users reach the Internet **through the balloon**, which relays between the two link
directions. That makes the station an **Internet gateway**, and it fixes three facts:

1. **The link is bidirectional and simultaneous.** A gateway serves TCP/IP traffic, whose
   acknowledgements travel the opposite way to its payloads. Every direction is live at once.
2. **The balloon is a bent pipe, not a store-and-forward node.** The two link directions are
   relayed with minimal processing latency, because a gateway that buffers per packet cannot
   serve interactive traffic. ADR-014 records the bent-pipe relay path; ADR-034/ADR-035 record
   the two-band radio that makes the two directions independent.
3. **Full duplex is therefore a requirement, not a preference — and it rules out a
   half-duplex T/R relay.** The committed radio family (**LR2021**) is **half-duplex**: one
   transceiver cannot transmit and receive at the same time (ADR-034 §Context). A T/R switch or
   a half-duplex relay in the gateway path would interleave the two directions in time and
   destroy the simultaneity the gateway needs. ADR-034's answer — the two directions on **two
   separate chips, on two separate bands** — is what makes the gateway possible at all.

The consequence for the ground end is that the station owns **two antennas on two bands that
are live at the same time**. That single fact generates most of this ADR set: it fixes the
duplex strategy (ADR-072), it decides which direction sets the gain requirement (ADR-073,
ADR-075), and it decides how the two antennas are carried (ADR-078).

## Decision

**D1 — The ground station is a full-duplex Internet gateway: ground users reach the Internet
through the balloon as a bent pipe.** Both link directions run simultaneously. This is the
design basis every other record in this set assumes.

**D2 — The gateway path is full duplex, and a half-duplex T/R relay/switch is REJECTED.** The
gateway receives 433 MHz (balloon → ground) and transmits 2.45 GHz (ground → balloon). No
component in the duplex path may be required to interleave the two directions in time.
Rationale: the LR2021 is half-duplex (one transceiver at a time), so any single-radio gateway
is a T/R relay; a T/R relay breaks TCP/IP simultaneity and the bent pipe. The accepted
architecture is **two band antennas, live simultaneously** (ADR-072).

**D3 — The station shares ONE az/el positioner between both bands, not one reflector.** The
433 MHz element and the 2.4 GHz element ride the **same** positioner, boresighted together;
the narrow (2.4 GHz / dish) element does the tight pointing and the wide (433 MHz / Yagi)
element is the forgiving one. This is the one mechanical conclusion of the earlier
"share the positioner, not the reflector" analysis that survives the FLRC-max decision
(ADR-073) — its *link* half (LoRa-carries-the-far-link) is superseded.

**D4 — This record is the umbrella of the set.** The 12 records and their authorship are listed
in §"The set" below.

## Invariants

- **INV-1.** Both directions are live simultaneously; nothing in the duplex path may be
  time-shared between them.
- **INV-2.** The ground RX band is 433 MHz and the ground TX band is 2.45 GHz, mirroring
  ADR-034's balloon-side split (balloon TX 433 / balloon RX 2.4 GHz).
- **INV-3.** The balloon relays between the two directions as a **bent pipe**; the ground
  gateway does not depend on balloon-side store-and-forward buffering.
- **INV-4.** One positioner carries both band antennas; proposing a second positioner requires
  a new record that names what the second positioner buys.

## Consequences

### Positive
- The service model is explicit: this is an access gateway, so the 433 MHz **downlink** — the
  direction with the smaller budget — is the direction that sets ground gain (ADR-073).
- No T/R switch, no switching transients, no switching latency in the duplex path.
- Sharing one positioner keeps the mechanical line item to a single tracker (ADR-077/078).

### Costs / risks
- Two antennas and two feedlines is more mast hardware and wind area than one dual-band feed.
- Full duplex on two bands is only available because the **balloon** carries two radios
  (ADR-034). If the balloon ever collapses to a single half-duplex radio, this gateway
  architecture does not survive — the tripwire is balloon-side, not ground-side.
- The uplink is **EIRP/PSD-capped** under licence-exempt rules, which caps the *service radius*
  (ADR-072 §Open items); "Internet gateway" is therefore a **local** service on the ISM
  footing, not a long-range one.

## Open items (not assumed)

- **`TODO(unverified)`** the exact ERC Rec 70-03 Annex 1 row (and the EN 300 328 PSD condition)
  for the 2.4 GHz uplink — inherited from `docs/LINK-BUDGET-LICENCE-EXEMPT.md`.
- **Flagged defect, no winner named in-repo:** the 2.4 GHz uplink's legal ceiling is recorded
  **two ways** — flat **20 dBm EIRP** (`docs/LINK-BUDGET-LICENCE-EXEMPT.md`, used by ADR-081's
  ladder) and **≈14.26 dBm EIRP** under the 10 dBm/MHz PSD rule at FLRC-max bandwidth
  (`docs/analysis/rf-shopping-list-and-duplex-architecture.md` §8.3). The two differ by ~6 dB
  and give different uplink ranges. Settling the Annex 1 row is the single input that closes it.
- A service definition (number of users, duty cycle, availability) is **not** recorded anywhere
  in this set; every range figure in these records is a link-budget range, not a delivered
  service radius.
- **`TODO(unverified)` what "full duplex" means at the NETWORK/MAC layer** (independent consultant
  finding, `docs/analysis/plan-review-consultant.md` §2 Q5): two RF paths are a *necessary* but not
  a *sufficient* condition for a usable bidirectional Internet gateway. The MAC/scheduling contract
  on the balloon side (ADR-035's TDM schedule) and the gateway's buffering/duty-cycle behaviour are
  not written down in this set.
- **Code-review note:** this record was challenged by the independent visual consultant on
  2026-10-08 (verdict **QUALIFY**); the findings and their disposition are recorded in
  `docs/analysis/plan-review-consultant.md`. A visual/plan consult is **not** a code review and does
  not satisfy the ADR-010 review gate.

---

## The set (this consolidation)

**Branch:** `design/adr-set-groundstation`, off `github/main` @ `09e1b69`.
Numbers **066–070 are claimed off-branch** (§Numbering and collision note) and are **not reused**;
the fresh numbers **071–082** are allocated here.

| ADR | Decision | Source branch(es) | Status |
|---|---|---|---|
| **071** | Gateway design basis; full duplex; no half-duplex T/R relay; one positioner | `design/rf-shopping-list` (duplex/T-R), `design/ground-station-lowpower-link` (share the positioner) | Accepted by operator |
| **072** | Band-split duplex: two band antennas, **no circulator**; BPF before the LNA; attenuate, don't amplify, the uplink | `design/rf-shopping-list` (ADR-070-duplex) | Accepted by operator (via ADR-034) |
| **073** | 433 MHz downlink is **FLRC at max throughput**; **LoRa rejected** | `design/ground-station-flrc-max` (ADR-067) | Accepted by operator |
| **074** | **Two flight-board variants** (F33 high-power / low-power LR2021) so others can fly without a licence | operator decision (2026-10-08); priced in `design/gain-per-dollar` (ADR-068 §D6) | Accepted by operator |
| **075** | The **F33 (~$8) is the cheapest dB** in the system; it multiplies every ground candidate's range **3.55×** | `design/gain-per-dollar`, `design/ground-station-flrc-max`, `design/amplifier-hypothesis-check` | Accepted by operator (flight gated) |
| **076** | **Stow-on-wind** survival policy + anemometer cutoff + **mechanical latch** | `design/positioner-lowcost` (ADR-067), `design/gain-per-dollar-cliff` | Proposed |
| **077** | **Print the structure, buy the gearing**; a self-locking worm reducer is mandatory | `design/positioner-lowcost`, `design/gain-per-dollar` | Accepted by operator (printed positioner) |
| **078** | **Right-size** the antenna: small dish / wide beam over big dish / narrow beam; the **positioner-class cliff** and the **mesh rule** | `design/gain-per-dollar-cliff`, `design/positioner-lowcost`, `design/ground-station-flrc-max` | Proposed |
| **079** | **Amplifier-led receive chain** using the **owned TQP3M9037** LNA | `design/rf-shopping-list`, `design/amplifier-hypothesis-check`, `design/amplifier-substitution` | Accepted by operator (band-edge contradiction flagged) |
| **080** | The **XR-613 divider is resistive (DC–5 GHz ⇒ 6 dB, no array gain)** — a bench tool, not an array combiner | `design/rf-shopping-list` (open item 1, now closed by the operator) | Accepted by operator |
| **081** | The **tier ladder** and the **recommended option B** (A-430S15R + DIY tracker P2, ≈ EUR 735) | `design/gain-per-dollar` (ADR-068), `design/tier0-accessible` (ADR-069) | Proposed |
| **082** | **Rate adaptation** — size the antenna for the minimum useful rate at maximum range | `design/ground-station-flrc-max` (ADR-067 §D6) | Accepted by operator |

### Supersession of the off-branch records (declared, not silent)

| off-branch record | fate | superseded by |
|---|---|---|
| 066 `ground-station-lowpower-shared-positioner` | link plan (LoRa far-link) dead; mechanical half (share the positioner) retained | **073** (link), **071 D3** (mechanics) |
| 067 `flrc-max-433-tx-power-and-coarse-mesh` | superseded | **073** (FLRC-max), **075** (F33), **078** (mesh rule) |
| 067 `positioner-architecture` | superseded | **076** (stow), **077** (gearing), **078** (right-sizing) |
| 068 `ground-station-gain-per-dollar` | superseded | **075** (F33/metric), **078** (Yagi-before-dish), **081** (ladder) |
| 068 `ground-station-antenna-class-cliff` | superseded | **078** (cliff + pre-cliff array), **081** (sweet spots) |
| 068 `ground-station-amplifier-vs-antenna` | superseded | **079** (owned LNA receive chain), **072** (no uplink PA) |
| 069 `tier0-accessible-ground-station` | superseded | **081** (ladder), **072** (EIRP-cap invariant) |
| 070 `ground-station-amplifier-hypothesis` | superseded | **079** (owned LNA), **080** (no array gain), **072** (circulator) |
| 070 `ground-station-duplex-t-r-architecture` | superseded | **072** (band-split duplex — same decision, fresh number) |

**None of the off-branch files is modified, renamed or imported by this branch.** They remain
on their own branches; this table is the pointer a future reader needs. Where a new record and
an off-branch record disagree, **the new record wins** and this table says so.

## For future sessions

- **One-line rule:** the ground station is a **full-duplex Internet gateway through a bent-pipe
  balloon**; that is *why* it has two simultaneous band antennas, and it is *why* a half-duplex
  T/R relay is rejected.
- **Read this record first**, then the decision you need (072–082).
- **Reproduce anything** with the command on the record that owns it; the umbrella makes no
  measurements of its own.

