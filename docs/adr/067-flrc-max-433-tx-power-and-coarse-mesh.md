# ADR-067 — 433 MHz FLRC-max-throughput downlink: the power belongs on the BALLOON (2 W F33), and any large 433 dish must be a COARSE MESH

- **Status:** **Proposed** — the analysis is complete and cited; the *text* has not been
  accepted by a human.
- **Date:** 2026-10-08
- **Decision owner:** Felix (operator)
- **Author:** Hermes subagent (design analysis), per the operator's 2026-10-08 instruction
  that the 433 downlink is **FIXED on FLRC at maximum throughput**, that **LoRa is REJECTED
  as too slow**, and that "as much gain as we can get" is wanted — while **mass is the
  binding limit on the balloon** and the operator also said **"do the heavy lifting on the
  ground"**.
- **Supersedes:** **ADR-066** (`066-ground-station-lowpower-shared-positioner.md`,
  introduced on branch `design/ground-station-lowpower-link` @ `4b90be94`) — its
  **"LoRa carries the far link / FLRC is a close-range mode"** decision is **DEAD**, because
  LoRa has been rejected. Its *other* half (share the **positioner**, not the **reflector**)
  is **retained and strengthened**. See "Relation to other ADRs".
- **Related:** ADR-039 (licence-exempt 433 design point — the power cap this ADR collides
  with), ADR-041 (RF front end, no balloon FEM), ADR-047 (V9 power provisioning — the F33's
  6.15 W TX rail), ADR-051 / ADR-049 (the 6.0 V / 7.2 W-peak wing array), ADR-034 / ADR-035
  (433 TX / 2.4 GHz RX band split, TDM schedule), ADR-029 (LR2021 module), ADR-108
  (F33 + SX1280 pin plan — the land-pattern work already done for the F33).
- **Companion evidence:** `docs/analysis/ground-station-flrc-max-throughput.md` (the
  TX-power-vs-dish trade table, the rate-vs-range tables, the mesh wind analysis, the
  sourced parts, the recommendation, and the consultant verdict recorded verbatim).
  Repro: `python3 docs/analysis/ground_station_flrc_max_model.py`; figure
  `python3 docs/analysis/render_flrc_max_figure.py` →
  `docs/analysis/assets/flrc-max-trade.png`.
  Builds on (does not re-derive) `docs/analysis/ground-station-lowpower-link-and-shared-dish.md`
  (@`4b90be94`) and `docs/analysis/ground-station-bom-candidates.md` (@`283cad72`).
- **Consulted:** fleet visual consultant, served model **`gpt-6-astra`** — verdict
  **APPROVED / CONFIRM** (verbatim in the analysis §7). A visual consult is not a code
  review and does not satisfy the ADR-010 review gate.
- **Numbering note:** **`066` is RESERVED, not free.** `scripts/adr_next_number.py` returns
  `66` on this branch because this branch descends from `github/main`, which never received
  ADR-066 — but `066-ground-station-lowpower-shared-positioner.md` **already exists on the
  pushed branch `design/ground-station-lowpower-link` (commit `4b90be94`)**. Claiming 066
  here would collide the moment that branch reaches main. **`067` is the genuinely free
  number**, and 066's file is brought onto this branch marked *Superseded by ADR-067* so the
  index and the record agree. Do not hand-pick; a later ADR re-runs the script.

---

## Context

### The architecture input changed

ADR-066 was written on the premise that the 433 downlink is **LoRa** at low power, with
FLRC merely a close-range mode. The operator has now **fixed** the input: the 433 downlink
runs **FLRC at maximum throughput**, and **LoRa is rejected as too slow**. ADR-066's
deciding sentence — *"LoRa's required ground gain is negative … make LoRa the far-link mode
and FLRC the close-mode"* — therefore **no longer describes the system**. Its tripwire
(*"if FLRC is ever required at 650 km, this ADR reopens and the 433 antenna must become a
~2.7–3.0 m dish"*) has **tripped**.

### The deciding calculation

`required_G_ground = S + FSPL − P_tx − G_balloon`, at **650 km** and
`FSPL(433.05 MHz) = 141.4 dB`, `G_balloon = 0 dBi` (no attitude control);
`D = (λ/π)·√(10^(G/10)/η)` with `η = 0.55`, `λ = 0.6923 m`.

| P_tx | FLRC 2.6 Mbps (S = −100.5 dBm) | FLRC 650 kbps (S = −107 dBm) |
|---:|---|---|
| **+13 dBm** (low power, the ADR-066 premise) | reqG **+27.9 dBi** → **D = 7.38 m** (42.8 m²) | +21.4 dBi → D = 3.49 m |
| **+22 dBm** (LR2021 chip max, no external PA) | +18.9 dBi → **D = 2.62 m** | +12.4 dBi → **D = 1.24 m** |
| **+33 dBm** (F33 2 W PA) | **+7.9 dBi → D = 0.74 m** | +1.4 dBi → D = 0.35 m |

**The low-power premise plus max throughput implies a 7.38 m reflector.** That is not a
hard design, it is **not a design**: ~42.8 m² of aperture, ~163 kg of structure (scaling the
vendor's own 3.0 m / 27 kg mesh kit), and **53 kN·m of moment at a 20 m/s wind** — 20× the
holding torque of the strongest AZ/EL rotator in the sourced BOM, and 14.5× even as a
coarse mesh. No vendor sells a 433 dish above 1.9 m today (RF Hamdesign's 2.4 m and 3.0 m
kits are **out of stock**; its 4.5 m ceased production in 2024). **The ground cannot "do
the heavy lifting" for FLRC-max at 650 km at low power — that is a physical impossibility,
not a cost.**

### The mesh fact that makes a large 433 dish viable at all

At 433 MHz the **λ/10 reflector-hole rule is 69.2 mm** (Wikipedia, *Parabolic antenna*:
a metal screen reflects as effectively as a solid surface when its holes are smaller than
one tenth of a wavelength, "so screen reflectors are often used to reduce weight and wind
loads"). The one vendor in this market corroborates the rule exactly at its limit: RF
Hamdesign's standard **6 mm mesh is rated "usable to 6 GHz"** (λ/10 there = 5.0 mm) and its
**2.8 mm mesh option to 11 GHz** (λ/10 = 2.7 mm) — i.e. the mesh is *just* λ/10 at its
advertised ceiling and is therefore **11.5× finer than needed at 433 MHz**, i.e.
electrically solid with an enormous margin.

That matters mechanically, not just electrically. Wind moment, with `F = ½ρv²·A·Cd·σ`
(`Cd = 1.38` **derived** from the Gibertini OP100SE vendor wind figure of 91 kg @ 120 km/h
over a 0.949 m² surface; `σ` = the mesh's solid fraction, published by JAERA as
" Durchlass " = 77–88 % open for 25–50 mm mesh), against the **SPID BIG-RAS holding torque
of 2,712 N·m** (vendor spec sheet, fetched — a *real* rating, replacing the BOM study's
`TODO(unverified)`):

| D | SOLID (× rating) | 6 mm coarse mesh (σ = 0.265) |
|---:|---:|---:|
| 1.90 m | 0.93× | 0.25× |
| **2.40 m** | **1.88× ✗** | **0.50× ✓** |
| **2.62 m** | **2.45× ✗** | **0.65× ✓** |
| 3.00 m | 3.67× ✗ | 0.97× (at the limit) |
| 3.49 m | 5.79× ✗ | 1.53× ✗ |
| 7.38 m | 54.7× ✗ | 14.5× ✗ |

**A solid 2.4 m or 2.62 m dish exceeds the strongest BOM rotator's holding torque at
120 km/h; the same dish as a coarse mesh sits at half to two-thirds of it.** The mesh is
what brings the large 433 dish back into a feasible positioner class — at zero RF cost.

---

## Decision

1. **The 433 MHz downlink carries FLRC at maximum throughput (LoRa REJECTED), and the
   balloon's transmit power is the primary link lever — not the ground aperture.**
   Where a max-throughput 650 km link is required, the **2 W F33 (NiceRF LoRa2021F33-2G4,
   +33.0 dBm @ 5.0 V / 1100 mA)** is to be used, not the low-power LR2021. Its +20 dB over
   the +13 dBm premise removes a **factor 10.0 in dish diameter / factor 100 in reflector
   area**: 7.38 m → 0.74 m. **20 dB of balloon TX is decisively cheaper than the ground dish
   it removes, because that dish is not purchasable, not buildable and not holdable.**

2. **The F33's balloon-side cost is recorded honestly, because the operator's binding limit
   is mass: +2.8 g of module mass and +3.1 W of TX DC power.**
   * Module mass **4.0 g (F33) vs 1.2 g (bare LR2021)** → **+2.8 g**
     (`docs/PAYLOAD-WEIGHT-ESTIMATES.md` lines 62/119/177).
   * TX DC **5.50 W @ 5.0 V** (5.0 V × 1.100 A) and **6.15 W @ 5.5 V** (ADR-047 §1.1–1.2);
     ADR-047 already provisions this rail (27× the 100 ms TX slot on the 1.65 F bank) and
     states the array alone never key the PA — the bank is the source.
   * **This ADR EXPLICITLY CONTRADICTS `docs/PAYLOAD-WEIGHT-ESTIMATES.md` §D**, which
     classes the V2 F33 board as *"Heavy-Lift Reference … Ground Station Only … not a pico
     balloon target"*. That label is a **whole-board** statement (~20.6 g with solar); the
     radio decision here is a **module swap** (+2.8 g). **The operator must confirm the
     +2.8 g module is acceptable on the balloon vehicle, and that weight record must then be
     corrected by its own ADR.** The contradiction is named, not silently resolved.

3. **If the F33 is NOT put on the balloon, FLRC-max at 650 km is not achievable.** The
   fallback is **+22 dBm + a 2.62 m COARSE-MESH dish + the committed rate ladder**, and even
   that sits at **zero margin** (648 km closure). The affordable fallback is
   **+22 dBm + a 1.24 m mesh dish at 650 kbps** (648 km closure), with FLRC-max reserved for
   ≤ ~300 km (307 km at 0.74 m / +22 dBm). **This is a named consequence, not a preference.**

4. **THE MESH RULE, as a standing constraint: any 433 MHz dish of 2 m or more built for
   this project MUST be a coarse mesh reflector, not a solid one.** At 433 MHz λ/10 permits
   **69.2 mm** holes, so 6–25 mm commodity welded mesh (RF Hamdesign 6 mm kit mesh; JAERA
   25/50 mm sheet; metal-market 25/50 mm; drahtgewebe-shop 6 mm/1 mm) is electrically solid
   **and** cuts the wind moment to ~0.14–0.27 of a solid dish. **A solid 2.4 m+ 433 dish is
 mechanically infeasible on the strongest non-slew rotator in the BOM; the mesh version is
 comfortable.** **The edge of that rule is exact and must be quoted with it:** the mesh
 stays inside the BIG-RAS rating up to **2.62 m (0.65×)**; at **3.00 m the mesh is AT the
 rating — 0.97×, zero margin**; at **3.49 m it exceeds it (1.53×)**. So **≥ 3.0 m mesh ⇒
 the slew-drive rotator class (SPID SPX-05/06, €5,487) plus counterweights.**

5. **The ground dish is sized for MARGIN AND HORIZON, not for closure.** With the F33:
   0.74 m closes 2.6 Mbps at 649 km; **1.24 m** adds +2.2 dB (1,088 km); **1.9 m** adds
   +6.4 dB (1,667 km). **The recommended ground station is a 1.2–1.9 m coarse-mesh 433 dish**
   (RF Hamdesign `FPD 1M2 KIT` €387.20 / `FPD 1M9 KIT` €901.45, in stock) on a light-to-medium
   AZ/EL rotator (SPID SPX-01, €1,132) — every such combination is ≤ 0.25× the BIG-RAS holding
   torque. If a 2 m+ dish is ever required, it is the **mesh** dish on a **SPID BIG-RAS
   (€1,775, 2,712 N·m)** and the mesh rule of Decision 4 applies.

6. **Rate adaptation is retained and formalised as the long-range mechanism, not as the
   solution to the 650 km question.** With the F33, 2.6 Mbps at 650 km is a 0.74 m dish, so
   the ladder's job is range/robustness: the same **1.24 m** dish delivers **either 650 kbps
   at 650 km or 2.6 Mbps at 1,254 km**, and the **1.9 m** dish delivers **1,667 km @ 2.6 Mbps
   / 3,523 km @ 650 kbps / 5,583 km @ 260 kbps**. The committed ladder
   (`docs/RANGE-THROUGHPUT-PLAN.md`: *2600 → 1300 → 650 → LoRa fallback*) is the right shape;
   the **LoRa fallback step is now out of scope** by the operator's decision.

7. **The two gates that are NOT engineering are recorded as the real blockers:**
   * **Licence.** The entire +13…+33 dBm class **exceeds** the committed licence-exempt
     design point of **+12.15 dBm EIRP** (ADR-039 / ADR-041). Recommending the F33 makes the
     433 downlink an **amateur-band** link. The DE amateur licence and ADR-039's
     airborne-SRD grey area (open item (a)) must be settled **before** any flight.
     **This — not mass — is the binding constraint on Decision 1.**
   * **Registry / weight record.** See Decision 2's named contradiction with
     `docs/PAYLOAD-WEIGHT-ESTIMATES.md` §D.

8. **Rejected alternatives** (with the reason, not by preference):
   * **Closing FLRC-max at 650 km from the ground at ≤ +22 dBm** — requires a 2.62 m dish at
     **zero margin**, DIY-only (the 2.4 m/3.0 m kits are out of stock), and at 0.65× of the
     BIG-RAS holding torque even as mesh; at **+13 dBm** it requires a 7.38 m dish that is not
     a product, not holdable, and ~163 kg. **Rejected as physically infeasible, not as
     expensive.**
   * **A large SOLID 433 dish** — exceeds the strongest BOM rotator's holding torque from
     2.4 m upward at 120 km/h (1.9–3.7×). Rejected mechanically; the RF justification for a
     solid surface does not exist at 433 MHz (λ/10 = 69.2 mm).
   * **ADR-066's "one small 433 antenna on the Ku positioner"** — retained only as the
     *mechanical* concept (share the positioner). Rejected as a *link* plan, because with
     FLRC-max the 433 element is no longer a small Yagi **unless** the F33 carries the link
     (Decision 1) — in which case a 0.74 m dish on the shared positioner is exactly what
     ADR-066's architecture wanted and could not have.

---

## Consequences

1. **The far link's viability moves from the ground to the balloon.** With the F33 the 433
   ground antenna is a **0.74–1.9 m class** dish, not a 2.7–3.0 m one; without it, FLRC-max
   at 650 km does not exist (Decision 3).
2. **A new mass and DC line appears on the balloon side** (+2.8 g module; 5.50–6.15 W TX DC
   rail, already provisioned by ADR-047) and **must be reconciled with the weight record**
   (Decision 2).
3. **The 433 reflector is now specified as a coarse mesh** wherever it exceeds ~2 m
   (Decision 4), with the sourced mesh materials listed in the analysis §5.5; this is a
   procurement constraint, not a preference.
4. **The regulatory class of the 433 downlink changes** (Decision 7): amateur-band operation
   is now a design precondition, not an option.
5. **ADR-066 is superseded in its link plan and retained in its mechanics.** Its "share the
   positioner, not the reflector" conclusion stands; its "LoRa carries the far link" is dead.
6. **No procurement follows from this record** — it is a design decision only.

---

## Open items (not assumed)

- **`TODO(unverified)`** a **433 MHz prime-focus dish feed** for the sized mesh dishes (the
  vendor's feed range begins at 900 MHz) — the concrete blocker on buying a 433 dish *as a
  dish*.
- **`TODO(unverified)`** the **rib/former set** for a >1.9 m DIY 433 mesh dish (no vendor
  sells ribs without mesh; the ≥2.4 m kits are out of stock).
- **`TODO(unverified)`** the **wire diameter of the RF Hamdesign 6 mm mesh** (σ = 0.265
  assumes 1.0 mm), and the **exact wind-drag exponent and rib-area allowance** the σ-model
  omits.
- **`TODO(unverified)`** a **measured** mesh-vs-solid reflector gain penalty in dB.
- **`TODO(unverified)`** the **live F33 module price** (in-repo figure ~$8, LCSC `C5913567`,
  marked "check"; the LCSC page is JS-gated).
- **`TODO(unverified)`** a **433 MHz-specific FLRC sensitivity row** (915 MHz datasheet rows
  used; inherited from ADR-066).
- **`TODO(unverified)`** the DE amateur-licence and airborne-SRD position for a +33 dBm
  airborne 433 transmitter (ADR-039 open item (a)).
- **Flagged, not resolved:** the solar array is recorded both as **2.4 W**
  (`docs/adr/044-v9-power-rails.md`, ADR-006) and as **7.2 W peak** (`docs/v9-BOM.md`,
  ADR-049/051). ADR-047 provisions against the 2.4 W figure.
- Horizon: 650 km at ~30 km altitude is slightly beyond the geometric radio horizon (618 km)
  but inside the standard 4/3-Earth refractive horizon (~714 km); taken as given.

---

## Relation to other ADRs

- **ADR-066** — **SUPERSEDED by this record** in its link plan; **retained** in its
  mechanical conclusion (share the positioner, not the reflector). The supersede pointer is
  carried in 066's own Status line, per the repo's ADR-first rule that "the one that
  explicitly supersedes wins".
- **ADR-039 / ADR-041** — this ADR **collides** with their +12.15 dBm EIRP licence-exempt
  cap and makes the amateur-licence gate explicit; it does not change them.
- **ADR-047** — consumes its F33 rail provisioning (6.15 W @ 5.5 V) as the balloon-side cost.
- **ADR-049 / ADR-051 / ADR-044 / ADR-006** — the wing array whose peak/nominal figures
  bound the TX rail (flagged, §Open items).
- **ADR-108 / ADR-029** — the F33 module and its already-designed land pattern.
- **ADR-034 / ADR-035** — the band split and TDM schedule this station serves.

---

## For future sessions

**One-line rule:** **the 20 dB belongs on the balloon (2 W F33) — the ground dish it removes
is a 7.4 m machine that does not exist; and any 433 dish ≥ 2 m MUST be a coarse mesh
(λ/10 = 69 mm), because as a solid reflector it exceeds the strongest rotator's holding
torque while the mesh sits at half of it.** The ground dish is bought for **margin and
horizon** (1.2–1.9 m), not for closure.

**Files:** analysis `docs/analysis/ground-station-flrc-max-throughput.md`; model
`docs/analysis/ground_station_flrc_max_model.py`; figure
`docs/analysis/render_flrc_max_figure.py` → `docs/analysis/assets/flrc-max-trade.png`;
consult verdict `docs/analysis/assets/consult-verdict-flrc-max.txt`.

**Reproduce:** `python3 docs/analysis/ground_station_flrc_max_model.py`.

**Do not re-derive:** the FLRC sensitivities (Semtech LR2021 datasheet v2.2 Table 3-12:
2.6 Mbps = −100.5 dBm, 650 kbps = −107 dBm) or the repo's **−143 dBm** figure — that one is
**LoRa SF12 / BW 62.5 kHz** (Table 3-17), 36 dB away from FLRC, and must never be used in an
FLRC budget.

**Do not re-run `scripts/adr_next_number.py` and take its answer on this branch:** it returns
`66`, which is **reserved** by the pushed branch `design/ground-station-lowpower-link`.
