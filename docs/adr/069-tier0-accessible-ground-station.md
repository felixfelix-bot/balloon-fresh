# ADR-069 — The accessible floor: a Tier-0 ground station, and Tier A without the 2.4 GHz dish

**Status:** Proposed (agent-authored draft, 2026-10-08) — `Proposed` is **not** frozen; this is
**not** an operator decision, orders nothing, and freezes no fab.

**Numbering note.** `scripts/adr_next_number.py` returns **066**, but **066 is claimed**
(`design/ground-station-lowpower-link` and `design/ground-station-flrc-max`),
**067 is claimed** (`design/positioner-lowcost`, and doubly by `design/ground-station-flrc-max`
— a known collision), and **068 is claimed** (`design/gain-per-dollar`). **069 was verified free
on every `github/*` remote branch** before use. The allocator cannot see unmerged branches; this
is the documented collision mode, recorded rather than renumbered silently.

**Companion analysis (not a decision record):**
`docs/analysis/tier0-accessible-ground-station.md`
(+ repro `docs/analysis/tier0_accessible_model.py`,
figure `docs/analysis/figures/tier0-eirp-capped-uplink.png`).

**Relates to (does not supersede):** ADR-067 (positioner-lowcost), ADR-066 (lowpower shared
positioner), ADR-068 (gain-per-dollar). This ADR **builds on** ADR-068's cheapest option and adds
the tier below it.

## Context

Three findings landed within a day of each other and they point the same way:

1. **The 2.4 GHz uplink requires no ground gain.** Required ground gain is **−17.4 dBi @300 km /
   −10.7 dBi @650 km** under the licence-exempt 20 dBm EIRP cap with the balloon LNA
   (`LINK-BUDGET-LICENCE-EXEMPT.md` §1b/§3; `positioner-lowcost-3dprinted.md` §3.1). An omni
   closes it.
2. **Under the EIRP cap, ground uplink antenna gain above ~8 dBi is inert.** Because
   `EIRP = P_tx + G_ground ≤ 20 dBm` and the LR2021's own 2.4 GHz PA maxes at **+12 dBm**
   (datasheet `TXOPHF`), exactly **8 dB** of ground gain reaches the legal cap; every dB above
   that is cancelled one-for-one by PA back-off. A **0.6 m dish is 13.4 dB inert; a 1.2 m dish is
   19.4 dB inert** (`tier0_accessible_model.py` Tables 1/1b). An **8 dBi panel** achieves the
   maximum compliant margin (+17.4 dB @300 km, +10.7 dB @650 km).
3. **The 2.4 GHz dish is the sole cause of the positioner class.** It sets the station's pointing
   budget to **1.5°**, which a printed drive's 0.5–2.0° backlash cannot meet
   (`positioner-lowcost-3dprinted.md` §8), forcing closed-loop encoders; and its 4× swept area
   forces a NEMA23+worm reducer. **Remove the dish and the tightest element left is the 433 Yagi
   at ~4°** — twice as forgiving.

The consequence the operator asked for: **an accessible tier below the sibling's cheapest
(~€650, which still carried a 0.6 m 2.4 GHz dish)**, and a **re-costing of Tier A** with the dish
removed.

## Decision

**1. Adopt the EIRP-cap invariant as a design rule (binding).**

> **Ground 2.4 GHz antenna gain is useful only up to `20 dBm − P_tx_max` (= 8 dB for the LR2021).
> Any 2.4 GHz ground antenna above ~8 dBi must be justified on interference-rejection or
> polarisation grounds ONLY — never on link closure or margin.** It is not a gain device; it is
> an RF-hygiene device.

**2. Remove the 2.4 GHz dish + feed from Tier A; replace them with an ~8 dBi panel.**

The 0.75 m Ku dish (**€94.90**) + 2.4 GHz feed (**€231.00**) = **€325.90** of hardware is
superseded by an **8 dBi panel (~€15–60)**, link-equivalent and roughly 10× less wind load.
Re-costed Tier A: **≈ €616–685** (DIY printed tracker P1) or **≈ €546–615** (bought **Yaesu
G-450CDC, €359**, now more than sufficient with no dish) — down from **≈ €927–951** as line-itemed.
A **Yaesu G-450CDC (€359)** replaces the previously-required G-5500DC/BIG-RAS class because the
moving wind area collapses when the dish goes.

**3. Adopt Tier 0 as the accessible floor — two variants, no motors, no firmware.**

* **Tier 0a — "no pointing at all" (≈ €90–245):** two omnis (2.4 GHz uplink + 433 LoRa downlink)
  on a fixed mast. Closes the low-power LR2021 board in **LoRa**: 433 downlink **+13.7 dB
  @650 km**, 2.4 GHz uplink **+5.7 dB @650 km** (omni) / **+10.7 dB** (8 dBi panel).
  **No moving parts.** Bit-rate limited to LoRa.
* **Tier 0b — "hand-aimed Yagi" (≈ €144–304):** adds a **Diamond A-430S10R 13.1 dBi 433 Yagi
  (€69)** on a **manual pan-tilt/tripod**. Adds **F33 FLRC 2.6 Mbps to 650 km (+5.2 dB)** at the
  cost of a **human** pointing a ~40° beam. Still no motors, controller, encoder or anemometer.

**4. State Tier 0's one hard limit.** Tier 0 **cannot** carry **low-power FLRC at range** — with
no F33, 650 km FLRC 2.6 Mbps needs +18.9 dBi (a ~2.6 m dish). Tier 0 is a **LoRa (+ hand-aimed
F33)** station by design, not a compromise discovered late.

## Invariants (binding)

- **No 2.4 GHz ground aperture is bought for gain above ~8 dBi.** A dish may be bought for
  interference rejection / polarisation only, and the record must say so.
- **The 433 ground antenna is margin, not closure, for LoRa** (required gain is negative). It is
  load-bearing only for FLRC, and then only with the F33.
- **Tier 0 has no moving parts.** Any proposal to add a motor to Tier 0 makes it Tier A and must
  carry Tier A's wind/backlash/pointing analysis.
- **The tier ladder is explicit:** Tier 0a (omnis) < Tier 0b (hand Yagi) < Tier A (auto, dish
  removed) < Tier B / dish tiers (ADR-068). Quoting a cost must name the tier.

## Consequences

- **Positive:** the accessible floor drops from **~€650 to ~€90–245** for the LoRa mission, and
  the dish-removal saves **~€265–315** on Tier A. The single most mechanically-consequential item
  (the dish) is gone, which **deletes the positioner class requirement**, not just its cost.
- **Positive:** the "€/dB" story becomes honest — above 8 dBi the uplink €/dB is **infinite**.
- **Cost / risk:** Tier 0 trades automation for price. It suits a **stationary-attended** campaign
  (LoRa continuous, or a hand-tracked F33 pass), not an unattended 24/7 high-rate station.
- **Condition (not a defect to hide):** every tier's 650 km **2.4 GHz uplink requires the
  balloon-side LNA** (balloon RX −136/−137 dBm). Without it the no-LNA case is −7.3 dB (omni) or
  −2.3 dB (8 dBi panel) at 650 km — **a ground dish does not fix it; the LNA does**
  (`LINK-BUDGET-LICENCE-EXEMPT.md` §4.2; `tier0_accessible_model.py` Table 1c).
- **Inherited, unresolved:** the F33 rows depend on the DE amateur / airborne-SRD licence question
  (ADR-039 open item (a)); the 2.4 GHz EIRP cap row is `TODO(unverified)` against the exact ERC
  Rec 70-03 Annex 1 entry. Neither changes the Tier-0/Tier-A structure.

## Alternatives rejected

- **Keep the 0.6 m dish for "margin".** Rejected: the margin is capped (Table 1), so the extra
  aperture buys **zero** dB and costs 4× wind area, 1.5° pointing and ~€326.
- **A bigger 2.4 GHz dish for a future high-rate uplink.** Rejected for now: the committed uplink
  is LoRa-class. If a 2.4 GHz FLRC uplink were ever required, re-open this ADR — it would change
  the answer, and that is stated rather than assumed away.
- **A printed open-loop tracker for Tier 0.** Rejected: it is more expensive than a hand-aimed
  pan-tilt and adds firmware, backlash and a failure mode for a capability (automatic pointing)
  that LoRa does not need.

## For future sessions

- **One-line rule:** *above ~8 dBi, ground 2.4 GHz gain is inert — do not buy 2.4 GHz aperture
  for gain. LoRa closes on omnis; FLRC-to-650 km needs the F33 and only a ~13 dBi Yagi.*
- **Reproduce:** `python3 docs/analysis/tier0_accessible_model.py` (every table);
  `python3 docs/analysis/render_tier0_figure.py` (the figure).
- **Owns:** the tier ladder and the EIRP-cap invariant. **Does not own:** the positioner mechanics
  (ADR-067) or the 433 dish class (ADR-066/068).
- Do **not** renumber this record; if `069` collides on a later branch, the collision is a defect
  to report, not to fix by renaming.
