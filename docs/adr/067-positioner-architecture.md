# ADR-067 — Ground-station AZ/EL positioner: right-sized dish, printed structure, purchased self-locking gearing

**Status:** Proposed (agent-authored draft, 2026-10-08) — `Proposed` is **not** frozen;
this is **not** an operator decision, orders nothing, and freezes no fab.

**Numbering note.** `scripts/adr_next_number.py` returns **066**, but `066` is **already
claimed** by a remote branch (`docs/adr/066-ground-station-lowpower-shared-positioner.md`).
`067` was verified free on **every** `github/*` remote branch before use. The allocator
cannot see unmerged branches — this is the known collision mode, recorded here rather than
renumbered silently.

**Companion analysis (not a decision record):**
`docs/analysis/positioner-lowcost-3dprinted.md`
(+ repro `docs/analysis/positioner_lowcost_model.py`,
figure `docs/analysis/figures/positioner-rightsizing.png`).

## Context

A commercial ground-station BOM for the balloon station came to **~€2,518 reference /
~€1,402 prototype** (`docs/analysis/ground-station-bom-candidates.md`), with the AZ/EL
positioner alone at **€949–€1,775** (`ground-station-bom-candidates.md` §0.5). The operator
wants a **3D-printed AZ/EL positioner using stepper motors**. A previously printed tracker
(Printables model **945761**, *Antenna Tracker* by Stratos) was **too small/weak**: it uses
**28BYJ-48** steppers, the author states the motors *"are not the best option"*, and its
4 × 608zz bearing / 14:50 pitch-gear layout has **no stated mass or wind rating**
(`docs/analysis/positioner-lowcost-3dprinted.md` §1).

Three committed facts bound the design:

1. **The 2.4 GHz uplink does not need a dish.** Required ground gain is **negative** —
   **−17.4 dBi at 300 km**, **−10.7 dBi at 650 km** — under the licence-exempt 20 dBm EIRP
   cap with the balloon LNA
   (`docs/LINK-BUDGET-LICENCE-EXEMPT.md` §1b/§3; recomputed in
   `positioner_lowcost_model.py` §7). An omni closes the link; the dish buys *margin and
   beam discipline*, not closure.
2. **Swept area and wind torque scale as D².** 1.2 m → 0.6 m is **4.00× less area and
   4.00× less wind force** at the same wind speed
   (`positioner_lowcost_model.py` Table 1: 0.6 m → 83.1 N, 1.2 m → 332.5 N at 20 m/s, solid).
3. **The 433 downlink is LoRa (committed low-power LR2021).** A 10–15 dBi Yagi closes it
   with +24…+30 dB margin. **Only if a long-range FLRC mode is required** does the 433 side
   need **≈ +19…+28 dBi**, i.e. a **~2.7–3.0 m dish**, which is *not* a printing candidate
   (`docs/analysis/ground-station-lowpower-link-and-shared-dish.md` §0/§2).

## Decision

**Adopt the hybrid positioner architecture:**

1. **Right-size the 2.4 GHz dish to ~0.6 m** (or a salvaged 0.6–0.9 m offset Ku reflector).
   Do **not** buy the 1.2 m dish for the uplink: its extra ~6 dB is not needed for closure
   and costs 4× the swept area and 4× the wind torque.
2. **Boresight the 433 downlink Yagi** (Sirio WY 400-6N, 11 dBi) on the same positioner.
3. **3D-print the structure only** — yoke, turret, bearing housings, dish backplate,
   Yagi clamp, electronics bay (PETG/ASA, ribbed, metal bearing inserts).
4. **BUY the gearing — no printed gears in the drive.** Use a **self-locking worm reducer**
   (**NMRV40 20:1**, rated **40 N·m**) on each axis, driven by **NEMA23 3.0 N·m** steppers.
5. **Closed-loop position feedback** (per-axis absolute magnetic encoder) plus
   **unidirectional-approach** backlash discipline; optionally re-peak the 433 downlink RSSI.
6. **Survival = stow, not steel.** Size the structure for a **12–14 m/s operating wind**,
   **stow aperture-up** (11.8 % of broadside wind area → ~8.5× torque reduction,
   `positioner_lowcost_model.py` Table 3) on an **anemometer cutoff**, with a **fail-safe
   stow direction** and **two hard endstops per axis**. Treat stow as a **mechanical latch /
   brake**, not a software-only state.

## Invariants

- **No printed gear or printed tooth face carries AZ/EL hold torque.** Torque reaction lives
  in the purchased worm reducer and in purchased bearings/shafts.
- **The fail-safe direction is STOW**, asserted by an MCU-level cutout (not a PC-level one).
- **The survival case is the stow case**: the structure is rated for operating wind, and the
  storm case is handled by stowing aperture-up plus a positive hold.
- **Self-locking is treated as a primary brake, never as the only brake**: a holding brake or
  a mechanical stow latch is required wherever loss of hold is unacceptable.

## Consequences

### Positive
- ~**1.9–3.9×** cheaper than the commercial BOM in parts (≈ €650–730 reference; ≈ €430–510
  with a DIY feed and a salvaged dish), most of the saving from the right-sized dish and from
  not buying a €949–€1,775 rotator.
- One structural class down: **24.9 N·m** required (0.6 m, balanced, SF 2) vs
  **199.5 N·m** at 1.2 m — the difference between one NMRV40 + NEMA23 and a NEMA34 + large
  NMRV50/2-stage.
- Beamwidth **doubles** (7.3° → 14.6°), which is exactly the tolerance a cheap drive needs.
- Rebuildable/repairable: the printed structure is the cheap, replaceable part.

### Costs
- The printed structure is a **prototype**, not a product: mass and stiffness must be
  measured, not assumed.
- The worm's self-locking is **ratio- and friction-dependent** and the vendor does not
  warrant it for holding loads (`positioner_lowcost_model.py` §6 vendor caveat) → brake.
- The **2.4 GHz feed** on a repurposed Ku dish carries an unmeasured mismatch loss (inherited
  `TODO(unverified)` from `docs/analysis/dualband-single-dish.md` §5.2).
- Selecting 0.6 m trades ~6 dB of uplink margin against 1.2 m; if a high-rate 2.4 GHz mode is
  ever required, the dish must grow (and so must the positioner).

## Rollout / PR sequence

TBD — implementation not yet started. This ADR is proposed alongside the analysis; no BOM,
schematic or fab change is authorised by it. The single closing measurement that would
firm it up is listed in the analysis §14.

## Notes

**Independent consultant.** The companion figure was reviewed by the independent visual
consultant (served model **`gpt-6-astra`**), which returned **APPROVED** with substantive
caveats — recorded verbatim in the analysis doc §15. Its two load-bearing points are folded
in here: (a) the 0.6 m dish is justified by **margin/robustness, not closure** (already the
doc's position), and (b) **stow must be a mechanical latch/brake**, and the **11.8 %
silhouette is geometry-specific**, not a universal reduction.

**Explicitly NOT decided here:** the 433-band modulation choice (LoRa vs FLRC — it decides
whether a ~3 m salvage-only dish is required), and anything about the flight board.
