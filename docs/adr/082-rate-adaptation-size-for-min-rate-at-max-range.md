# ADR-082 — Rate adaptation: size the dish/antenna for the minimum useful rate at maximum range

- **Status:** **Accepted by operator** (Felix, 2026-10-08) as the sizing rule; the committed rate
  ladder's shape (`docs/RANGE-THROUGHPUT-PLAN.md`) is retained, with its **LoRa fallback rung
  deleted** by ADR-073 D1/D4.
- **Date:** 2026-10-08
- **Decision owner:** Felix (operator)
- **Author:** Hermes subagent (consolidation pass), branch `design/adr-set-groundstation`
- **Related (stable references):** ADR-071 (design basis), ADR-073 (FLRC-max; LoRa rejected),
  ADR-075 (the F33 multiplier), ADR-078 (right-sizing), ADR-081 (the ladder), ADR-035
  (`docs/adr/035-tdm-radio-schedule.md`).
- **Evidence:** the rate-vs-range tables and the recommendation in
  `docs/analysis/ground-station-flrc-max-throughput.md` §Decision 6 +
  `docs/analysis/ground_station_flrc_max_model.py` (source branch
  `design/ground-station-flrc-max`, whose `067-flrc-max-433-tx-power-and-coarse-mesh.md` is
  **superseded by ADR-073 / ADR-075 / ADR-078**); the committed ladder in
  `docs/RANGE-THROUGHPUT-PLAN.md`. Reproduce:
  `python3 docs/analysis/ground_station_flrc_max_model.py`.

**Numbering and collision note.** Numbers **066–070 are claimed on sibling design branches**
(see **ADR-071 §Numbering and collision note** for the full table) and are **not reused**.
`scripts/adr_next_number.py` prints 066 because it is branch-blind. This record takes the fresh
number below (verified free, prefix-anchored, against every `github/*` branch, 2026-10-08).

---

## Context

With FLRC fixed as the downlink modulation (ADR-073), the ground antenna's size is a **rate-vs-range
choice**, not a single number. The link equation makes the trade explicit: ground gain can be spent
either on **range at a fixed rate** or on **rate at a fixed range**, and the rate ladder
(**2600 → 1300 → 650 kbps**, `docs/RANGE-THROUGHPUT-PLAN.md`) is the mechanism that converts one
into the other.

**The sizing rule follows from that.** A station designed for the *maximum* rate at the *maximum*
range is over-sized for the mission: it buys dB that only the top rung ever uses. A station designed
for the **minimum useful rate at the maximum range** is the smallest antenna that still delivers a
usable service over the required distance — everything above that rung is delivered by stepping the
rate **down as range increases**, which is free (it costs modulation, not hardware).

**Worked consequence (with the F33, ADR-075).** Because +20 dB of balloon TX is so cheap, the rates
land where a *small* antenna already is:

| ground antenna | delivered (F33 on the balloon) |
|---|---|
| 0.74 m | 2.6 Mbps at **649 km** (closure) |
| **1.24 m** | adds +2.2 dB → **1,088 km at 2.6 Mbps**, *or* **650 kbps at 650 km** |
| **1.9 m** | adds +6.4 dB → **1,667 km @ 2.6 Mbps / 3,523 km @ 650 kbps / 5,583 km @ 260 kbps** |

So the same **1.24 m** antenna delivers either the top rung at 650 km or the middle rung at 1,254 km
— the ladder is what buys the extra range **without a bigger antenna**. With a single Yagi
(ADR-081 option B) the same logic gives **150 km at 2.6 Mbps** and the range grows as the rate steps
down.

**What rate adaptation does NOT do.** It does **not** solve the 650 km question at low power: the
low-power board at 2.6 Mbps / 650 km needs a 7.38 m dish (ADR-073 Context), and stepping the rate
down to 650 kbps still needs 3.49 m. **The ladder's job is range/robustness at a given TX power, not
to substitute for TX power.**

## Decision

**D1 — Size the ground antenna for the MINIMUM USEFUL RATE AT THE MAXIMUM RANGE, not for the
maximum rate at the maximum range.** The top rungs are delivered by the link when conditions allow,
not by antenna hardware.

**D2 — Rate adaptation (the committed 2600 → 1300 → 650 kbps ladder) is the formal long-range
mechanism.** It is retained as the mechanism that converts a small antenna into long range as the
rate steps down.

**D3 — The LoRa fallback rung is DELETED** (ADR-073 D1/D4: LoRa is rejected). The ladder's shape is
otherwise unchanged.

**D4 — Rate adaptation is not a substitute for balloon TX power.** Any claim that the ladder closes
a link the antenna cannot close must name the rung and the TX power it assumes (ADR-073 D3).

**D5 — No ground antenna may be justified by "the top rung at max range"** unless the mission
requires that exact combination; state the minimum useful rate and the required range, and size on
those.

## Invariants

- **INV-1.** The committed ladder is **2600 → 1300 → 650 kbps**; **LoRa is not a rung**.
- **INV-2.** Antenna sizing starts from (minimum useful rate, required range), not from (max rate,
  max range).
- **INV-3.** A rate-adaptation claim states the TX power it assumes and the ground gain it assumes.

## Consequences

### Positive
- The antenna stays in the cheap class: the extra range that a bigger antenna would have bought is
  delivered by stepping the rate down instead.
- It makes the F33's value legible: the same small antenna reaches **1,667 km at 2.6 Mbps** with the
  F33 on the balloon, so the ladder is a *robustness* mechanism rather than a *range* mechanism.
- One station serves the whole ladder (ADR-081 D6).

### Costs / risks
- A stepped-down rate is a **service degradation**, so the *minimum useful rate* must be an operator
  decision, not an engineering convenience; it is recorded here as a rule, not as a number.
- The bottom rung is now **650 kbps**, so the deepest fade margin the system can trade rate for is
  smaller than it was with the LoRa fallback.

## Open items (not assumed)

- **Highest-value missing artifact (independent consultant finding,
  `docs/analysis/plan-review-consultant.md` §2 Q2/Q5): a per-rate TWO-WAY link budget.** Each rung
  (2.6 / 1.3 / 0.65 Mbps) needs its own **occupied bandwidth, PSD calculation, total permitted
  EIRP, receiver sensitivity, margin and range**, for **both** directions, showing which direction
  limits the rung — and the whole ladder must be recomputed once one legal ceiling is frozen
  (ADR-072 Open items). The 2.6 Mbps rung is the most exposed to the PSD reading.
- **Not decided here:** the **minimum useful rate** and the **required range** for the service. The
  rule needs both; the ladder cannot substitute for them (and no service definition exists in the
  repo — ADR-071 Open items).
- **`TODO(unverified)`** a **433 MHz-specific FLRC sensitivity row** (915 MHz values are used;
  inherited from ADR-073).

## Relation to other ADRs

- **Supersedes** ADR-073's predecessor (`067-flrc-max-…`) for the **rate-ladder material**, and it
  **retains that record's warning** that the ladder is not the answer to the 650 km question.
- **ADR-073** owns the modulation choice and the LoRa rejection that D3 applies.
- **ADR-075 / ADR-081** own the TX-power and antenna-class numbers this rule sizes against.
- **ADR-078** owns the right-sizing/cliff constraint that D1 must not violate.

## For future sessions

- **One-line rule:** **size the antenna for the minimum useful rate at the maximum range**; the
  rate ladder (2600 → 1300 → 650 kbps, **no LoRa rung**) buys the extra range, not a bigger antenna.
- **Reproduce:** `python3 docs/analysis/ground_station_flrc_max_model.py`.
