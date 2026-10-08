# ADR-075 — The F33 is the cheapest dB in the system (~0.40 USD/dB) and it multiplies every ground candidate's range 3.55×

- **Status:** **Accepted by operator** (Felix, 2026-10-08) as the **two-board plan** and as the
  **cost metric** (*"design the ground for the low-power board; treat the F33 as a multiplier"*).
  The **flight** half (putting the F33 on the balloon) is **gated, not decided** — it waits on the
  licence question and the weight-record correction (D2 / Open items).
- **Date:** 2026-10-08
- **Decision owner:** Felix (operator)
- **Author:** Hermes subagent (consolidation pass), branch `design/adr-set-groundstation`
- **Related (stable references):** ADR-071 (design basis), ADR-073 (FLRC-max), ADR-074 (the two
  flight boards), ADR-078 (the antenna class the F33 removes), ADR-081 (the tier ladder), ADR-047
  (V9 power provisioning — the F33's 6.15 W TX rail), ADR-039 / ADR-041 (licence-exempt point),
  `docs/PAYLOAD-WEIGHT-ESTIMATES.md`.
- **Evidence:** `docs/analysis/ground-station-gain-per-dollar.md` (§Decision 6 + the cost metric,
  source branch `design/gain-per-dollar`, whose file `docs/adr/068-ground-station-gain-per-dollar.md`
  is **superseded by this record** / ADR-078 / ADR-081); the F33 trade table in
  `docs/analysis/ground-station-flrc-max-throughput.md`; the amplifiers ledger in
  `docs/analysis/ground-station-amplifier-hypothesis-check.md`. Reproduce:
  `python3 docs/analysis/ground_station_gain_per_dollar_model.py`.

**Numbering and collision note.** Numbers **066–070 are claimed on sibling design branches**
(see **ADR-071 §Numbering and collision note** for the full table) and are **not reused**.
`scripts/adr_next_number.py` prints 066 because it is branch-blind. This record takes the fresh
number below (verified free, prefix-anchored, against every `github/*` branch, 2026-10-08).

---

## Context

Three independent analyses landed on the same asymmetric result, and it is worth one record
because it is the single highest-leverage number in the ground-station plan.

**1. The bar.** A 433 Yagi bought on the market costs **EUR 3.24–8.3 per marginal dB**
(Diamond A-430S10R → A-430S15R is +1.7 dB for EUR 5.50; a 6 → 15 dBi single Yagi is EUR 69 →
EUR 74.50 ≈ EUR 8.3/dB). The F33 module is **~USD 8 for +20 dB** (low-power/licence-exempt point
+12.15 dBm → F33 +33 dBm at 433 MHz) = **≈ 0.40 USD/dB**. Nothing purchasable on the ground comes
close.

**2. The multiplier.** Fitting the F33 multiplies **every** ground candidate's range by
**3.55×** (10^(11/20)), because +11 dB of extra TX (chip +22 dBm → F33 +33 dBm) buys 10^(dB/20)
in range at constant received power. So the operator's own two-board plan (ADR-074) is priced
correctly by: **design the ground for the low-power board, then read every ground candidate's
range at 3.55× for the F33 flight** — e.g. the recommended option B reaches **150 km at 2.6 Mbps**
on the low-power board and **532 km** with the F33 (ADR-081).

**3. The alternative is not affordable.** Fitting the F33 removes **a factor 10.0 in dish
diameter / factor 100 in reflector area** from the max-throughput 650 km link (7.38 m →
0.74 m). Conversely, closing FLRC-max at 650 km **without** the F33 requires a **2.6–7.4 m**
reflector: 2.62 m at +22 dBm at **zero margin**, or 7.38 m at the +13 dBm premise — i.e. ~42.8 m²
of aperture, ~163 kg, and 53 kN·m at 20 m/s, **14.5× the holding torque of the strongest sourced
rotator even as a coarse mesh, and above 1.9 m no vendor sells the reflector at all**. The
low-power + max-FLRC-at-650 km route is **not affordable; it is not a design**.

**The ledger, in one unit.** Money per **dB of link-budget improvement in the direction that
needs it** (the ADR-078 metric definition):

| candidate | money | dB | per needed dB |
|---|---:|---:|---:|
| **F33 module on the balloon** (+12.15 → +33 dBm) | 8.00 **USD** | 20.0 | **0.40 USD/dB ← the bar** |
| F33, alternative reading (chip +22 → +33 dBm) | 8.00 USD | 11.0 | 0.73 USD/dB |
| **433 masthead LNA** (system dB — see ADR-079) | 257.00 EUR | 9.7 | 26.41 EUR/dB |
| 2-bay Yagi array (marginal over one Yagi) | 228.40 EUR | 3.0 | 76.13 EUR/dB |
| 4-bay Yagi array (marginal over one Yagi) | 562.40 EUR | 6.0 | 93.73 EUR/dB |
| 1.9 m mesh dish + BIG-RAS — gain only | 2,297.00 EUR | 2.84 | 808.80 EUR/dB |
| 1.9 m mesh dish + BIG-RAS — gain + cold-sky noise | 2,297.00 EUR | 6.64 | 345.93 EUR/dB |
| **2.4 GHz ground PA** | 0–185 EUR | **0.0** | **INF — zero needed dB** |

**Ranking: F33 (0.40 USD/dB) ≪ LNA (26.4) < 2-bay array (76.1) < 4-bay array (93.7) <
dish+tracker (346–809) < 2.4 GHz ground PA (infinite).** No ground purchase competes with the
balloon-side PA.

**Baseline ambiguity in the headline numbers — read the multiplier with its baseline named.**
The ledger carries **two** F33 readings and they imply **two** different multipliers:

| reading | TX step | F33 range multiplier | F33 per needed dB |
|---|---|---|---|
| chip-max baseline: bare LR2021 **+22 dBm** → F33 **+33 dBm** | +11 dB | **3.55×** | 0.73 USD/dB |
| licence-exempt baseline: **+12.15 dBm EIRP** → F33 **+33 dBm** | +20.85 dB | **≈11×** | 0.40 USD/dB |

**The commonly quoted "3.55×" is the +22 dBm baseline**, i.e. the bare chip's own maximum — which
is **above** the licence-exempt cap and is an **amateur-band** operating point on the low-power
board. Quoted against the **licence-exempt** point (+12.15 dBm EIRP) the same module multiplies
range by **≈11×**. **A range claim that does not name its baseline power is not usable** (this is an
independent consultant finding, `docs/analysis/plan-review-consultant.md` §2 Q2/Q5). The ground
sizing is unaffected (it is done on the low-power board either way), but **every published range
must carry its baseline**.

## Decision

**D1 — The F33 module is the cheapest dB in the system (≈ 0.40 USD/dB) and is the primary link
lever.** Where more link budget is wanted and the legal footing allows it, buy the F33 before
buying any ground dB.

**D2 — The F33's balloon-side cost is recorded honestly, and its flight is GATED.** +2.8 g module
mass (4.0 g F33 vs 1.2 g bare LR2021) and +3.1 W TX DC (5.50 W @ 5.0 V; 6.15 W @ 5.5 V, already
provisioned by ADR-047). **This record explicitly contradicts
`docs/PAYLOAD-WEIGHT-ESTIMATES.md` §D**, which classes the V2 F33 board as *"Heavy-Lift Reference
… Ground Station Only … not a pico balloon target"*. That label is a **whole-board** statement
(~20.6 g with solar); the radio decision here is a **module swap** (+2.8 g). The contradiction is
**named, not silently resolved**: the operator must confirm the +2.8 g module is acceptable on the
balloon vehicle, and the weight record must be corrected **by its own ADR**. Until then the F33
stays a **design input** for the ground plan and a **gated option** for the flight.

**D3 — Design the ground station for the low-power board; treat the F33 as a range multiplier**
(**3.55×** on the +22 dBm baseline; **≈11×** on the licence-exempt +12.15 dBm EIRP baseline — see
the baseline table above). This is the ordering that makes one ground design serve both flight
variants (ADR-074 D3) and it is the plan the recommended option B is costed under (ADR-081).
**The multiplier applies where the 433 MHz downlink is the limiting link**: if the 2.45 GHz uplink,
pointing/tracking, the receiver sensitivity or the regulatory ceiling limits instead, the range gain
is smaller or zero (independent consultant finding, `docs/analysis/plan-review-consultant.md` §2 Q5).

**D4 — The F33 makes the 433 downlink an amateur-band link, and that is the binding gate.** The
entire +13…+33 dBm class exceeds the committed licence-exempt **+12.15 dBm EIRP** point
(ADR-039 / ADR-041). The F33 flight requires the DE amateur licence and settlement of ADR-039's
airborne-SRD grey area (open item (a)).

**D5 — Rejected alternative, with reason:** *close FLRC-max at 650 km from the ground on the
low-power board.* Rejected as **physically infeasible** — a 7.38 m / ~163 kg / 53 kN·m machine
that no vendor sells and no sourced rotator holds — not as expensive.

## Invariants

- **INV-1.** Any new ground-station proposal is scored as **money per needed dB in the direction
  that needs it** (the ledger's unit), never by antenna gain or device gain alone.
- **INV-2.** The F33 is never assumed to close a link when sizing ground hardware (ADR-074
  INV-2); the ground is sized on the low-power board and the F33 is read as a multiplier.
- **INV-3.** No F33 flight until the licence question and the `PAYLOAD-WEIGHT-ESTIMATES.md` §D
  correction are settled.

## Consequences

### Positive
- One **~USD 8 / +2.8 g** module removes a **7.4 m / ~163 kg** ground machine from the plan.
- The ground plan becomes affordable and reproducible: with the F33, the 433 ground antenna is a
  **0.74–1.9 m class** item, not a 2.7 m one (ADR-078).
- A clean, single yardstick exists for every future proposal (INV-1).

### Costs / risks
- **The regulatory class of the 433 downlink changes** to amateur-band for the F33 flight (D4).
- A new mass and DC line appears on the balloon and **must be reconciled with the weight record**
  (D2) — currently a **named contradiction with no winner**.
- F33 rows in every sibling model depend on the licence question; the numbers are conditional.

## Open items (not assumed)

- **`TODO(unverified)`** the **live F33 module price** (in-repo ≈ USD 8, LCSC `C5913567`, "check").
- **`TODO(unverified)`** the DE amateur-licence and airborne-SRD position (ADR-039 item (a)).
- **Flagged defect:** `docs/PAYLOAD-WEIGHT-ESTIMATES.md` §D "Ground Station Only" vs this record's
  module-swap reading (D2).
- **Flagged:** the solar array is recorded both as **2.4 W** (ADR-044 / ADR-006) and **7.2 W peak**
  (`docs/v9-BOM.md`, ADR-049/051); ADR-047 provisions against the 2.4 W figure.

## Relation to other ADRs

- **Supersedes** the off-branch `068-ground-station-gain-per-dollar`
  (`design/gain-per-dollar`) in its **F33 / metric** half; that record's Yagi-before-dish and
  metal-vs-printed halves land in ADR-078 / ADR-077 and its sweet spots in ADR-081.
- **Consumes** the off-branch `067-flrc-max-433-tx-power-and-coarse-mesh` F33 trade (its decision
  lands in ADR-073; its mesh rule in ADR-078).
- **Consumes** `docs/adr/047-v9-power-provisioning.md` (the F33 TX rail) as the balloon-side cost.
- **Supersedes** the "the F33 half is gated, not decided" wording of the off-branch 068 — here the
  gate is written as an Invariant, so a future session cannot read it as decided.

## For future sessions

- **One-line rule:** the ~**USD 8 F33 is 0.40 USD/dB** — cheaper than any ground dB by 1–3 orders
  of magnitude — and it multiplies every ground candidate's range by **3.55×**; the ground plan
  is still sized on the **low-power** board.
- **Reproduce:** `python3 docs/analysis/ground_station_gain_per_dollar_model.py`.
- **Do not re-derive:** the 7.38 m / 2.62 m dish arithmetic (ADR-073/078 own it).
