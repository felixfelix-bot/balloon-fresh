# ADR-081 — The ground-station tier ladder, and the recommended option B (Diamond A-430S15R + DIY tracker P2, ≈ EUR 735)

- **Status:** **Proposed** — the ladder is a **recommendation with measured/estimated rungs**; the
  operator has **not** selected a tier. It orders nothing and freezes no BOM.
- **Date:** 2026-10-08
- **Decision owner:** Felix (operator) — the accessibility goal (*"keeping the costs low so that this
  project remains accessible for anyone to replicate"*) and the reachability question
- **Author:** Hermes subagent (consolidation pass), branch `design/adr-set-groundstation`
- **Related (stable references):** ADR-071 (design basis), ADR-072 (EIRP-cap invariant),
  ADR-074 (the licence-free flight variant this ground tier pairs with), ADR-075 (the F33 multiplier),
  ADR-078 (right-sizing), ADR-082 (rate adaptation).
- **Evidence:** `docs/analysis/ground-station-gain-per-dollar.md` (option B + the full candidate
  tables, source branch `design/gain-per-dollar`, whose `068-ground-station-gain-per-dollar.md` is
  **superseded by this record** / ADR-075 / ADR-078); `docs/analysis/tier0-accessible-ground-station.md`
  + `docs/analysis/tier0_accessible_model.py` (source branch `design/tier0-accessible`, whose
  `069-tier0-accessible-ground-station.md` is **superseded by this record** / ADR-072);
  the two sweet spots in `docs/analysis/gain-per-dollar-cliff.md` (source branch
  `design/gain-per-dollar-cliff`, ADR superseded by ADR-078 / this record). Reproduce:
  `python3 docs/analysis/ground_station_gain_per_dollar_model.py` and
  `python3 docs/analysis/tier0_accessible_model.py`.

**Numbering and collision note.** Numbers **066–070 are claimed on sibling design branches**
(see **ADR-071 §Numbering and collision note** for the full table) and are **not reused**.
`scripts/adr_next_number.py` prints 066 because it is branch-blind. This record takes the fresh
number below (verified free, prefix-anchored, against every `github/*` branch, 2026-10-08).

---

## Context

Three findings landed within a day of each other and they shape one ladder:

1. **The 2.4 GHz uplink requires NO ground gain.** Required ground gain is **negative** — −17.4 dBi
   at 300 km, −10.7 dBi at 650 km — under the licence-exempt **20 dBm EIRP** cap with the balloon
   LNA. An omni closes it.
2. **Under the EIRP cap, ground uplink antenna gain above ~8 dBi is INERT.** Because
   `EIRP = P_tx + G_ground ≤ 20 dBm` and the LR2021's own 2.4 GHz PA maxes at **+12 dBm**, exactly
   **8 dB** of ground gain reaches the cap; every dB above that is cancelled one-for-one by PA
   back-off. A **0.6 m dish is 13.4 dB inert; a 1.2 m dish is 19.4 dB inert.** An **8 dBi panel**
   achieves the maximum compliant margin (**+17.4 dB @300 km, +10.7 dB @650 km**).
3. **The 2.4 GHz dish is the sole cause of the positioner class.** It sets the pointing budget to
   **1.5°**, which a printed drive's 0.5–2.0° backlash cannot meet, forcing closed-loop encoders,
   and its 4× swept area forces a NEMA23 + worm reducer. **Remove the dish and the tightest element
   left is the 433 Yagi at ~4° — twice as forgiving** (ADR-078).

**The measured / estimated ladder** (EUR, indicative; every rung's items are line-itemed in the
source analyses):

| tier | what it is | cost | capability |
|---|---|---|---|
| **Tier 0a** — "no pointing at all" | two omnis (2.4 GHz uplink + 433 downlink) on a fixed mast. **No moving parts, no firmware.** | **≈ EUR 90–245** | closes the low-power board in LoRa: 433 downlink **+13.7 dB @650 km**; 2.4 GHz uplink **+5.7 dB @650 km** (omni) / **+10.7 dB** (8 dBi panel). |
| **Tier 0b** — "hand-aimed Yagi" | adds a **Diamond A-430S10R 13.1 dBi** 433 Yagi (EUR 69) on a manual pan-tilt/tripod. | **≈ EUR 144–304** | **F33 FLRC 2.6 Mbps to 650 km (+5.2 dB)** at the cost of a **human** pointing a ~40° beam. |
| **Tier A** — auto, 2.4 GHz dish REMOVED | 433 Yagi + **8 dBi panel** (replaces the 0.75 m Ku dish EUR 94.90 + feed EUR 231.00 = **EUR 325.90**) on a printed tracker. | **≈ EUR 616–685** (DIY P1) / **≈ EUR 546–615** (bought Yaesu G-450CDC EUR 359) — down from ≈ EUR 927–951 as line-itemed | automatic pointing; LoRa-class uplink; 433 driven by the flown TX power. |
| **Tier 0/B "most accessible"** (mirror rung, from the cliff branch) | one 433 Yagi + 2.4 GHz omni on a printed tracker — the **measurement platform**. | **≈ EUR 599** | the D7 measurement campaign station (ADR-078). |
| **Option B (RECOMMENDED)** — A-430S15R + DIY tracker P2 | **Diamond A-430S15R 14.8 dBi 433 Yagi (EUR 74.50)** on the **DIY printed tracker P2** (self-locking worm + NEMA23), 2.4 GHz panel. | **≈ EUR 735** all-in | **150 km at 2.6 Mbps** on the low-power board; **532 km with the F33** (the 3.55× multiplier). |
| **Tier B / dish tiers** | dish rungs (post-cliff), up to the 4-bay-array "best bang for buck" | **≈ EUR 2,166** (4-bay array + 0.75 m dish) … **≈ EUR 5,900–10,100** (dish build, SPID BIG-RAS dominant) | closes FLRC 2.6 Mbps without crossing the cliff (array) or with it (dish). |

**Why option B is recommended.** It is the cheapest rung that is **fully purchasable** (no fab
quote, no out-of-stock kit), it beats **every purchasable dish** on gain-per-euro, and it is **3.4×
cheaper than the commercial BOM (~EUR 2,518)** with no capability loss for the committed link.
The metric behind it is `M2 = EUR_total / max over the rate ladder of (R · d_max(R))` — **EUR per
(kbps·km)** — with `M1` (EUR/dB) and `M1m` (marginal EUR/dB) retained as diagnostics. **`M2` is a
peak-capability-per-euro diagnostic, NOT a mission-value function**; it must be read paired with a
coverage/availability constraint, and a **mission-level goodput/availability simulation is a
required next step**.

## Decision

**D1 — Adopt the EIRP-CAP INVARIANT as a binding design rule.** Ground 2.4 GHz antenna gain is
useful only up to `20 dBm − P_tx_max` (= 8 dB for the LR2021). Any 2.4 GHz ground antenna above
~8 dBi must be justified on **interference-rejection or polarisation grounds ONLY** — never on link
closure or margin. Its "€/dB" above that point is **infinite**.

**D2 — The tier ladder is explicit and quoted by NAME.** Tier 0a (omnis) < Tier 0b (hand Yagi) <
Tier A (auto, dish removed) < option B (recommended) < Tier B / dish tiers. **Any quoted station
cost must name its tier.**

**D3 — RECOMMEND option B: a high-gain 433 Yagi (Diamond A-430S15R 14.8 dBi, EUR 74.50) on the DIY
printed tracker P2, with the 2.4 GHz element a modest panel/omni — ≈ EUR 735 all-in**, delivering
**150 km at 2.6 Mbps** on the low-power board and **532 km with the F33**.

**D4 — Tier 0 is adopted as the accessible floor, in two variants, with one hard limit stated.**
Tier 0 **cannot** carry **low-power FLRC at range** (without the F33, 650 km FLRC 2.6 Mbps needs
+18.9 dBi, a ~2.6 m dish). It is a **LoRa (+ hand-aimed F33)** station **by design**, not a
compromise discovered late. Tier 0 has **no moving parts**; adding a motor to it makes it Tier A and
it must then carry Tier A's wind/backlash/pointing analysis.

**D5 — Every rung's 650 km 2.4 GHz uplink requires the balloon-side LNA** (balloon RX −136/−137 dBm).
Without it the no-LNA case is −7.3 dB (omni) or −2.3 dB (8 dBi panel) at 650 km — **a ground dish
does not fix it; the LNA does.**

**D6 — Any future ground-station proposal is evaluated by re-running the model with the candidate
added**, never by an antenna-only price.

## Invariants

- **INV-1.** No 2.4 GHz ground aperture is bought for gain above ~8 dBi; if a dish is bought on that
  band the record must say it is for interference rejection / polarisation only.
- **INV-2.** A cost quote names its **tier**.
- **INV-3.** Tier 0 has no moving parts.
- **INV-4.** The ladder is scored on `M2` (EUR per kbps·km) with the rig included, **paired with a
  coverage/availability constraint** — never on `M1` (EUR/dB) alone.

## Consequences

### Positive
- The accessible floor drops from **~EUR 650 to ~EUR 90–245** for the LoRa mission, and removing the
  2.4 GHz dish saves **~EUR 265–315** on Tier A while **deleting the positioner-class requirement**,
  not just its cost.
- The recommended rig is **≈ EUR 735 (option B)** versus the commercial BOM's **≈ EUR 2,518** — a
  **3.4×** reduction, every part purchasable, which directly serves the operator's accessibility
  goal and pairs with the licence-free flight variant (ADR-074).

### Costs / risks
- **Tier 0 trades automation for price** — it suits a **stationary-attended** campaign (LoRa
  continuous, or a hand-tracked F33 pass), not an unattended 24/7 high-rate station.
- **The metric is a cost lens, not a mission model.** It prices no outage probability, no loss of
  lock, no retransmission and no interference. A **mission-level goodput/availability simulation** is
  required before the ranking is treated as a mission answer, and the recommended tracker must be
  **tested** for backlash, repeatability, weather sealing and loss-of-lock recovery.
- **Two sibling cost figures differ for a similar config** — option B at **≈ EUR 735** and the
  cliff branch's "most accessible" at **≈ EUR 599** (a P1/P2 tracker and antenna-choice difference).
  This is a **flagged discrepancy**, not reconciled here; quote the config with the price.
- The recommendation is **peak-capability per euro under entered datasheet gains**; the 1.2 dB
  Yagi-over-dish edge is inside datasheet/feed/mismatch uncertainty (ADR-078).

## Open items (not assumed)

- **Flagged defect (inherited):** the **2.4 GHz uplink legal ceiling** — flat **20 dBm EIRP**
  (used by the tier-0 margins above) vs **≈14.26 dBm EIRP** under the 10 dBm/MHz PSD rule
  (`design/rf-shopping-list`). A ~6 dB disagreement; neither retired (ADR-072 Open items).
- **`TODO(unverified)`** the exact ERC Rec 70-03 Annex 1 row.
- **`TODO(unverified)`** the mission-level goodput/availability simulation (INV-4).
- **`TODO(unverified)`** the Tier-B bottom-up cost inputs (used/salvaged mount, feed).

## Relation to other ADRs

- **Supersedes** the off-branch `069-tier0-accessible-ground-station`
  (`design/tier0-accessible`): its ladder and its two Tier-0 variants land here; its EIRP-cap
  invariant lands in **D1** (and ADR-072).
- **Supersedes** the off-branch `068-ground-station-gain-per-dollar`
  (`design/gain-per-dollar`) for the **recommendation and the metric**; its F33 half is ADR-075 and
  its Yagi-before-dish half is ADR-078.
- **Supersedes** the off-branch `068-ground-station-antenna-class-cliff`
  (`design/gain-per-dollar-cliff`) for the **two sweet spots**; its cliff/mesh analysis is ADR-078.
- **Consumes** ADR-074's licence-free **flight** variant as its natural partner: the accessible
  **ground** tier and the accessible **flight** variant are one story.

## For future sessions

- **One-line rule:** the ladder is **Tier 0a < Tier 0b < Tier A < option B (≈ EUR 735, RECOMMENDED)
  < Tier B**; **quote the tier with the price**, and above **~8 dBi** the 2.4 GHz ground gain is
  **inert**.
- **Reproduce:** `python3 docs/analysis/ground_station_gain_per_dollar_model.py`;
  `python3 docs/analysis/tier0_accessible_model.py`.
