# ADR-068 — Ground-station antenna class: choose the pre-cliff Yagi-array rung, not the post-cliff dish rung

> **Number allocation — checked, because this repo has a live defect class here.**
> `python3 scripts/adr_next_number.py` is **branch-blind** (it scans only the working tree,
> where 066/067 do not exist), so its printed number is not trustworthy. 068 was verified
> free against **every** `github/*` **and** `ngit/*` branch:
> ```
> $ for b in $(git ls-remote --heads github | sed 's#.*refs/heads/##'); do \
>     git ls-tree -r --name-only "github/$b" | grep -E '^docs/adr/0[6-9][0-9]-'; done | sort -u
> docs/adr/066-ground-station-lowpower-shared-positioner.md
> docs/adr/067-flrc-max-433-tx-power-and-coarse-mesh.md
> docs/adr/067-positioner-architecture.md      <- 067 is DOUBLY claimed
> $ python3 scripts/adr_next_number.py --number 68 ; echo $?
> 68
> 0
> ```
> **066 and 067 are taken (067 twice). 068 appears on no `github/*` or `ngit/*` branch and
> the checker returns it free.** No file is renamed or renumbered.

- **Status: Proposed.** This is a *design direction*, not an accepted decision. It authorises
  no order, no fab freeze and no change to any BOM, schematic or plan. Nothing may treat an
  antenna class, a rotator purchase or a dish build as frozen until a human accepts it
  (ADR-first rule).
- **Date:** 2026-10-08
- **Decision owner:** Felix (operator). The questions — *"where is the cliff, how do we raise
  performance without crossing it, what are the two sweet spots, and can we measure instead of
  buying?"* — are his. The text is not accepted.
- **Author:** Hermes subagent, branch `design/gain-per-dollar-cliff`, worktree
  `~/worktrees/bf-cliff`.
- **Evidence base read in full to write this record:** `docs/analysis/gain-per-dollar-cliff.md`
  (this work, with its model `gain_per_dollar_cliff_model.py` and figures), and the four prior
  committed analyses it consumes and cites: `positioner-lowcost-3dprinted.md`,
  `ground-station-flrc-max-throughput.md`, `ground-station-bom-candidates.md`,
  `ground-station-lowpower-link-and-shared-dish.md`.
- **Related records:** ADR-034 (433 TX / 2.4 GHz RX band split), ADR-039/ADR-041
  (licence-exempt EIRP caps), ADR-066 (low-power shared positioner — **Proposed on a remote
  branch**; this record does not supersede it), ADR-067 (positioner architecture — **Proposed**;
  this record consumes its torque chain and stow finding), ADR-037 (2.4 GHz balloon antenna).
- **No hardware is ordered by this record. It is design work only.**

---

## 0. The question this record answers

The operator asked four questions about the ground station: **(1)** find and quantify the
*cost cliff* in the gain-per-dollar curve; **(2)** evaluate every lever that raises performance
without crossing it — mesh, stow + latch, counterweight, and **especially Yagi arrays at
433 MHz**; **(3)** define **two** sweet spots (most-accessible and best-bang-for-buck);
**(4)** can the low-power-board experiment be run with the cheap ground station, by *measuring*
rather than buying? A fifth, prior question is implicit: **is the cliff physics, or a market
artifact?**

The analysis `docs/analysis/gain-per-dollar-cliff.md` answers all of them. This record states
the decision that follows.

## 1. Decision

**D1. Treat the rotator-class boundary at ~1.0 m² of antenna wind-load area as a design
constraint, not a budget line to be crossed by default.** The cliff is real and quantified:
the marginal whole-station cost of the next dB of 433 gain is **~50–86 EUR/dB up to a ~1.0 m
dish**, then **~592 EUR/dB** across the 1.00 → 1.20 m step — a **6.9× jump** driven by the
purchasable AZ+EL rotator price stepping from **EUR 359** (Yaesu G-450CDC) to **EUR 1132**
(SPX-01/MD-03) and **EUR 1775** (SPID BIG-RAS). **Nothing may propose a ground-station antenna
that exceeds ~1.0 m² of wind-load area without explicitly stating that it crosses this cliff
and naming the concrete capability the crossing buys.**

**D2. For a 433 MHz high-gain ground station at the balloon's own +22 dBm class, the
preferred antenna class is a stacked 433 MHz Yagi ARRAY, not a dish.** A 4-bay stack of
commercially available 433 Yagis reaches **~20 dBi** — at or above the required **+18.9 dBi**
for FLRC 2.6 Mbps at 650 km — with an effective wind drag area of **0.454 m²**, i.e.
**~7 % of a 2.6 m solid dish's 6.37 m²**, and it needs only the **EUR 359** rotator class.
On 433 gain-per-euro the 2.4–3.0 m dish rungs are **Pareto-dominated by the array** (the dish
has *no more* 433 gain and costs 4–5×), as computed from the cost-carrying model table.
**Two binding qualifications, both accepted from an independent consultant round:** the array
must be sized against the rotator's **TOWER** rating (1.00 m², array at 45 %) — the **MAST**
rating (0.50 m²) leaves only 9 % margin and is **too thin** once frame, ice and cable are
counted — and the **pessimistic drag case (1.104 m²) EXCEEDS the tower rating by ~10 % and is
rejected** unless a higher-rated rotator/support is chosen or the array is redesigned. A stated
design margin is required; operating near a wind-area rating is not accepted.

**D3. Mesh, stow + a MECHANICAL LATCH + anemometer, and balanced-axis geometry are accepted
levers; the counterweight is accepted for a *different* purpose than often assumed.**
- **Mesh** (Cd 1.2 → ~0.5) is accepted and is **RF-free at 433 MHz** (λ/10 = 69.2 mm; the
  vendor's 6 mm mesh is 11.5× finer than required). It is worth **a whole rotator class at
  1.2 m** (EUR 1132 → EUR 359). Where a large dish is unavoidable, it must be **coarse mesh**.
- **Stow + anemometer cutoff** is accepted **only as a unit with a positive mechanical latch
  or brake** — the committed consultant finding ("you cannot hold stow with motor torque")
  stands, and holding stow on worm self-locking is **not** accepted as a safety property.
- **Counterweight** is accepted for **motor sizing and power-loss stability**, and this record
  states plainly that it **does not reduce wind torque**. Only **elevation-axis placement
  through the dish's centre of pressure** (balanced geometry) reduces the wind lever, and it
  is worth **4× torque**.
- A **DIY mid-class rotator** (printed structure + purchased self-locking worm + NEMA23, the
  committed "print structure, buy gearing" verdict) is accepted as the rotator that repairs
  the **market gap** — and noted as *unnecessary* if the array is chosen, because the array
  never leaves the EUR 359 class.

**D4. Recommend the two pre-cliff sweet spots as the candidate operating points.** The
**MOST ACCESSIBLE** station (one 433 Yagi + a 2.4 GHz omni on a printed tracker, **≈ EUR 599**)
is the default build and the **measurement platform**. The **BEST BANG FOR BUCK** station
(4-bay 433 Yagi array + 0.75 m 2.4 GHz dish, **≈ EUR 2 166**) is the performance point that
closes FLRC **2.6 Mbps** without crossing the cliff.

**D5. The dish is reserved for one regime only: the LOW-POWER case.** At the balloon's
**+13 dBm**, FLRC 2.6 Mbps needs **+27.9 dBi**, which **no Yagi array reaches** — there the
dish is the only option and the cliff must be crossed. **This is the one place the dish is
justified on link closure**, and the decision between "array" and "dish" therefore reduces to
**which TX-power/rate regime the mission actually flies**.

**D6. Run the measurement campaign BEFORE any dish/rotator purchase.** A Tier-A Yagi station
flies the low-power LR2021 and measures the two currently *assumed* numbers — the **433 MHz
FLRC sensitivity** (today a 915 MHz datasheet proxy) and the **path-loss exponent n** (today
assumed to be exactly 2.0) — plus the residual margin at the flown range. The campaign
**cannot** prove the range beyond what was flown and **cannot** retire the dish by fiat; it
**can** show the dish's required gain is over-stated or un-needed at the operating range, which
is exactly the decision that crosses or does not cross the cliff (§4 of the analysis).

**D7. If and only if a dish is chosen, it is a Tier-B build (EUR ~5 900–10 100), and the
SPID BIG-RAS (EUR 1775) is the dominant line — with a used/salvaged mount as the stated
fallback.** The 2.4/3.0 m mesh-dish kits are **"Out of production"**, so a 2.6 m dish is a
from-scratch rib+mesh build; the **433 prime-focus feed has no catalogue source** in the only
mesh-dish vendor's line and is the highest-uncertainty line item.

## 2. What is NOT proposed

* **A printed plastic geartrain** to carry the AZ/EL torque reaction — rejected in the
  committed positioner analysis and not revived here.
* **Holding stow on motor torque or worm self-locking alone** — rejected by the consultant
  finding; a mechanical latch/brake is required with it.
* **A "print everything" tracker** for a dish — rejected in the committed analysis.
* **A 7.38 m class 433 dish** (the low-power LR2021 at 2.6 Mbps / 650 km) — not a design; not
  purchasable; not holdable. It is the argument for balloon TX power, not a ground plan.
* **Buying the SPID BIG-RAS up front, before the measurement campaign** — the specific
  behaviour this record's D6 exists to prevent.

## 3. Consequences

* **Positive:** the antenna decision is made on a measured link at a known range instead of on
  a worst-case model; the high-gain station is reachable at a fraction of the Tier-B cost
  (**~7 % of the wind drag area, ~7.6 % of the modelled wind moment**) and needs no rotator
  above the **EUR 359** class; the cliff becomes an explicit, stated constraint.
* **Negative / risk:** the array's advantage is **regime-dependent** — it evaporates at
  +13 dBm / 2.6 Mbps, where the dish is required (§D5). A **linearly polarised** array is
  **not** robust to a tumbling balloon the way a CP dish feed is (the strongest genuine
  argument for the dish). The array's drag estimate is **dominated by its mounting frame**
  (0.252 of 0.454 m²), so a heavy frame, ice or cable load raises it — the 2.5× pessimistic
  case (1.104 m²) still fits the Yaesu tower class, but the margin is not unlimited.
* **Open (the array is a SCREENING result until these close):**
  1. **the full gust/moment/structural load case** through the array frame → mast/tower →
     rotator → foundation — an independent consultant's round-3 precondition;
  2. the **array harness loss** (modelled 0.5 / 0.8 dB) and the **component-level frame Cd·A**
     (the frame is 0.252 of the 0.454 m² and is an ESTIMATE geometry);
  3. the **unmeasured 433 MHz FLRC sensitivity**. Both (2) and (3) are measured, not assumed,
     under D6.
  4. the **Yaesu G-450CDC allowable moment** is not published (a wind-load *area* is), so the
     array's 154 N·m (SF 2) cannot be checked against a vendor limit.

## 4. Reproduce

```bash
python3 docs/analysis/gain_per_dollar_cliff_model.py                       # every table
python3 docs/analysis/render_gain_per_dollar_cliff_figures.py              # the three figures
```

*End of record.*
