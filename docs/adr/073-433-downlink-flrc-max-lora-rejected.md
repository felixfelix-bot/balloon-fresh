# ADR-073 — 433 MHz downlink: FLRC at maximum throughput, and LoRa REJECTED

- **Status:** **Accepted by operator** (Felix, 2026-10-08) — the operator fixed the modulation:
  *"the 433 downlink is FIXED on FLRC at maximum throughput"* and *"LoRa is REJECTED as too
  slow"*. The *text* is agent-drafted.
- **Date:** 2026-10-08
- **Decision owner:** Felix (operator)
- **Author:** Hermes subagent (consolidation pass), branch `design/adr-set-groundstation`
- **Related (stable references):** ADR-071 (design basis), ADR-072 (band-split duplex),
  ADR-075 (the F33 that makes FLRC-max-at-range affordable), ADR-078 (the ground antenna class
  this implies), ADR-082 (the rate ladder), ADR-034 / ADR-035 (band split, TDM schedule),
  ADR-039 / ADR-041 (licence-exempt 433 design point — the cap this decision collides with).
- **Evidence:** `docs/analysis/ground-station-flrc-max-throughput.md` +
  `docs/analysis/ground_station_flrc_max_model.py` (source branch
  `design/ground-station-flrc-max`, which carried this as its file
  `docs/adr/067-flrc-max-433-tx-power-and-coarse-mesh.md` — now **superseded by this record**
  and by ADR-075 / ADR-078). Reproduce:
  `python3 docs/analysis/ground_station_flrc_max_model.py`.

**Numbering and collision note.** Numbers **066–070 are claimed on sibling design branches**
(see **ADR-071 §Numbering and collision note** for the full table) and are **not reused**.
`scripts/adr_next_number.py` prints 066 because it is branch-blind. This record takes the fresh
number below (verified free, prefix-anchored, against every `github/*` branch, 2026-10-08).

---

## Context

**The modulation is now an operator-fixed input.** The earlier low-power analysis
(`design/ground-station-lowpower-link`) was written on the premise that the 433 downlink runs
**LoRa** and that FLRC is only a close-range mode. That premise is dead: LoRa is rejected as
too slow, and the downlink runs **FLRC at maximum throughput**.

**The sensitivity facts that make this decisive.** The repo's committed **−143 dBm** figure is a
**LoRa** number (SF12 / BW 62.5 kHz — Semtech LR2021 datasheet v2.2 Table 3-17; NiceRF
LoRa2021 V1.3; `docs/inventory.md`). Sub-GHz **FLRC** is a completely different number:
**−107 dBm at 650 kbps** and **−100.5 dBm at 2.6 Mbps** (datasheet **Table 3-12**) — **≈36 dB
worse** than the −143 dBm figure at the low-rate end. **Any 433 budget that pairs an FLRC plan
with −143 dBm is 36 dB optimistic**, and a LoRa-based budget cannot be reused for FLRC by
substitution.

**What FLRC-max costs the ground.** With the low-power LR2021 (+13 dBm premise), FLRC 2.6 Mbps
at 650 km needs **+27.9 dBi** of ground gain — a **7.38 m** reflector, ≈42.8 m² of aperture,
≈163 kg of structure and **53 kN·m** of moment at 20 m/s. That is not a product, not a build and
not holdable. **FLRC-max at 650 km from the ground alone, at low power, is a physical
impossibility, not a cost.** Its affordable form requires the balloon-side power of the F33
(ADR-075): at **+33 dBm** the same link is a **0.74 m** dish (+7.9 dBi).

**LoRa's opposite property, recorded so it is not re-proposed as a fallback without a decision.**
LoRa's required ground gain at 650 km is **negative** (−23.6 dBi at SF12/BW62.5 kHz), i.e. an
isotropic antenna closes it with 12–28 dB margin. That is *why* LoRa was the earlier plan; it is
also *why* it is slow. The rejection is a rate decision, and it is the operator's.

## Decision

**D1 — The 433 MHz downlink carries FLRC at maximum throughput. LoRa is REJECTED as too slow.**
This is an operator-fixed input, not an analysis preference.

**D2 — The balloon's transmit power is the primary link lever, not the ground aperture.** Where a
max-throughput 650 km link is required, the **2 W F33** (+33.0 dBm @ 5.0 V / 1100 mA) is to be
used, not the low-power LR2021 (ADR-075). Its +20 dB over the +13 dBm premise removes a **factor
10.0 in dish diameter / factor 100 in reflector area** (7.38 m → 0.74 m).

**D3 — FLRC must not be required at 650 km without the F33.** If the F33 is not flown, FLRC-max
at 650 km does not exist from the ground; the honest no-F33 fallback is **+22 dBm at 650 kbps
with a 2.62 m coarse-mesh dish at zero margin**, or FLRC-max reserved for ≤ ~300 km
(ADR-078).

**D4 — The LoRa fallback rung is out of scope.** The committed rate ladder
(`docs/RANGE-THROUGHPUT-PLAN.md`: 2600 → 1300 → 650 → LoRa fallback) keeps its shape but its
**LoRa step is deleted** by D1 (ADR-082).

**D5 — Rejected alternatives, with reasons (not preferences):**
- **LoRa for the far link** — rejected by the operator as too slow; its −143 dBm sensitivity is
  real but it cannot carry an Internet-gateway service.
- **Closing FLRC-max at 650 km from the ground at ≤ +22 dBm** — requires a 2.62 m dish at
  **zero margin**, DIY-only (the 2.4 m / 3.0 m kits are out of stock), at 0.65× of the strongest
  sourced rotator's holding torque even as mesh. Rejected as **infeasible**, not as expensive.
- **A large SOLID 433 dish** — exceeds the strongest sourced rotator's holding torque from
  2.4 m upward at 120 km/h (1.9–3.7×). Rejected mechanically; the RF justification for a solid
  surface does not exist at 433 MHz (λ/10 = 69.2 mm) (ADR-078 D4).

## Invariants

- **INV-1.** No 433 MHz link budget in this project may use the **−143 dBm** figure for an FLRC
  mode. FLRC sensitivities are −107 dBm (650 kbps) / −100.5 dBm (2.6 Mbps) at the entered rates.
- **INV-2.** FLRC at 650 km implies the F33 on the balloon (ADR-075); a proposal that claims
  FLRC-max at 650 km without it must name the ≥2.6 m dish it implies and the rotator class it
  crosses.
- **INV-3.** LoRa is not a fallback rung. Re-introducing it changes the service class and
  requires a new record.

## Consequences

### Positive
- The station can carry an Internet-gateway service class rather than a telemetry class.
- The decision forces the honest balloon-vs-ground split of the link: the cheap 20 dB belongs on
  the balloon (ADR-075), not in a ground machine that does not exist.

### Costs / risks
- **The binding gate is regulatory, not mass.** The whole +13…+33 dBm class **exceeds** the
  committed licence-exempt design point of **+12.15 dBm EIRP** (ADR-039 / ADR-041). Recommending
  the F33 makes the 433 downlink an **amateur-band** link; the DE amateur licence and ADR-039
  open item (a) (airborne-SRD grey area) must be settled **before** any flight. This — not mass
  — is the binding constraint (ADR-075).
- The 433 ground antenna class becomes load-bearing (ADR-078), where the earlier LoRa plan had
  required no more than a short Yagi.

## Open items (not assumed)

- **`TODO(unverified)`** a **433 MHz-specific FLRC sensitivity row** (915 MHz datasheet values
  are used; the 36 dB LoRa/FLRC gap dwarfs any band-to-band difference).
- **`TODO(unverified)`** the DE amateur-licence and airborne-SRD position for a +33 dBm airborne
  433 transmitter (ADR-039 open item (a)).
- Horizon: 650 km at ~30 km altitude is slightly beyond the geometric radio horizon (618 km) but
  inside the standard 4/3-Earth refractive horizon (~714 km); taken as given.

## Relation to other ADRs

- **Supersedes** the off-branch `067-flrc-max-433-tx-power-and-coarse-mesh`
  (`design/ground-station-flrc-max`). Its FLRC-max decision lands here; its **mesh rule** lands
  in ADR-078; its **F33 power trade** lands in ADR-075; its **rate ladder** lands in ADR-082.
- **Supersedes** the link half of the off-branch `066-ground-station-lowpower-shared-positioner`
  (`design/ground-station-lowpower-link`): the sentence *"LoRa carries the far link and FLRC is
  a close-range mode"* is **dead**. Its mechanical half (share the positioner, not the
  reflector) is **retained** in ADR-071 D3.
- **ADR-039 / ADR-041** are collided with, not changed: this record makes the amateur-licence
  gate explicit.

## For future sessions

- **One-line rule:** the 433 downlink is **FLRC-max, LoRa rejected**; the 36 dB between FLRC and
  the repo's −143 dBm LoRa figure is the number people get wrong.
- **Do not re-derive:** FLRC sensitivities from Semtech LR2021 datasheet v2.2 **Table 3-12**;
  the −143 dBm figure is **Table 3-17 LoRa SF12/BW62.5 kHz** and must never enter an FLRC budget.
- **Reproduce:** `python3 docs/analysis/ground_station_flrc_max_model.py`.
