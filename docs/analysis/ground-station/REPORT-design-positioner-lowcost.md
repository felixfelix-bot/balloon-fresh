# REPORT — Low-cost AZ/EL positioner (design/positioner-lowcost)

**STATUS: consultant analysis + ADR draft. Nothing ordered. No fab freeze. `AGENTS.md` untouched.**

## Deliverables

| Artifact | Path |
|---|---|
| Analysis doc | `docs/analysis/positioner-lowcost-3dprinted.md` |
| Repro model (stdlib, exit 0) | `docs/analysis/positioner_lowcost_model.py` |
| Figure + generator | `docs/analysis/figures/positioner-rightsizing.png` · `render_positioner_figure.py` |
| ADR draft (Proposed) | `docs/adr/067-positioner-architecture.md` (+ `docs/adr/INDEX.md` entry) |

## The answer in one paragraph

**The dominant cost lever is the dish diameter, and the 2.4 GHz uplink does not need a dish
at all.** The committed uplink budget closes the 2.4 GHz link with a **negative** required
ground gain (**−17.4 dBi @300 km**, **−10.7 dBi @650 km**), so an omni closes it and the
1.2 m dish in the commercial pair is *margin*, not *closure*. Right-sizing to **0.6 m** cuts
swept area and wind force **4.00×** and doubles the beamwidth (7.3° → 14.6°), which is
exactly the tolerance a cheap drive needs. On the drive: **print the structure, buy the
gearing** — a printed gear cannot hold the **24.9–49.9 N·m** the 0.6 m dish needs at 8.3–16.6:1
on a NEMA23, whereas a **NMRV40 20:1 self-locking worm (40 N·m)** can. Survive by **stowing**
(aperture-up ≈ 11.8 % of broadside area → ~8.5× torque reduction) with an **anemometer
cutoff**, not with steel. Reference parts cost **≈ €650–730** (≈ €430–510 with a DIY feed and
a salvaged dish) versus the commercial BOM's **€2,518 reference / €1,402 prototype**.

## Headline numbers

| Quantity | Value | Source |
|---|---|---|
| 0.6 / 0.9 / 1.2 m dish gain (2.4 GHz, η 0.55) | **20.98 / 24.50 / 27.00 dBi** | COMPUTED |
| 0.6 / 0.9 / 1.2 m swept area | **0.2827 / 0.6362 / 1.1310 m²** | COMPUTED |
| Wind force @20 m/s, solid (Cd 1.2) | **83.1 / 187.0 / 332.5 N** | COMPUTED (task: ~330 N @1.2 m ✓) |
| Wind force @20 m/s, mesh (Cd 0.5) | **34.6 / 77.9 / 138.5 N** | COMPUTED (task: ~125 N @1.2 m, 11 % low) |
| Required elevation torque, SF 2, balanced | **24.9 / 84.2 / 199.5 N·m** | COMPUTED |
| Reduction ratio needed (NEMA23 3.0 N·m) | **8.3 / 28.1 / 66.5 : 1** | COMPUTED |
| 2.4 GHz required ground gain | **−17.4 dBi @300 km / −10.7 dBi @650 km** | COMPUTED from `LINK-BUDGET-LICENCE-EXEMPT.md` |
| Stow (aperture-up) area ratio | **0.118 → 8.5× torque reduction** | COMPUTED |
| Pointing budget @1.2 m / 0.6 m | **0.73° / 1.46°**; printed backlash 0.5–2.0° | COMPUTED |

## Consultee

`visual_review: APPROVED` · `visual_reviewer_model: gpt-6-astra` (engaged on 2nd attempt;
1st = HTTP 503). Verdict **verbatim** in doc §15, with a reconciliation of its one numeric
objection (it read the chart's dish-gain-vs-required-gain pairing as a link margin; that
pairing is a *headroom* figure — the compliant margin is **+17.4 dB @300 km**). Its three
accepted points: the 0.6 m dish is justified by **margin/robustness, not closure**; stow must
be a **mechanical latch/brake**; the **11.8 %** stow silhouette is geometry-specific (excludes
feed/struts/back structure) and needs a gust factor.

## Honest gaps (`TODO(unverified)` — 39 markers in the doc)

NMRV gearbox **price** (StepperOnline renders prices via JS → guest page shows `$0.00`);
printed **PLA/PETG/ASA torque-per-tooth**; **28BYJ-48** output torque; a written
**self-locking guarantee** for the specific NMRV40; a **2.4 GHz FLRC** sensitivity row;
**wiper / power-steering / wheelchair-scooter** motor torques; **slewing-bearing price**;
**used-Yaesu** second-hand price; exact **ERC 70-03 Annex 1** row. Cause: all general search
backends (Brave/DuckDuckGo/Bing/Ecosia/Mojeek) served **captchas** to this fleet's egress IP
after the first two queries; Wikipedia + direct vendor fetches stayed reachable. Nothing was
guessed in place of a source.

## What flips the recommendation

1. A **high-rate (FLRC-class) 2.4 GHz uplink** → required gain +20…+30 dBi → ~1 m dish returns.
2. The **433 downlink forced to long-range FLRC** → 433 side needs a **~2.7–3.0 m dish**,
   which is **NOT a 3D-printing candidate** — it requires a salvaged/purchased polar mount or
   a decommissioned C-band/VSAT mount.
3. Insisting on a **1.2 m dish** → 199.5–399.0 N·m, NEMA34 + NMRV50/2-stage, and the 0.73°
   budget then makes a printed drive impossible without closed-loop correction.

## SHAs

local = github = ngit = **`33523591b4edd6c733ddbc765dc6064c41682da9`** (earlier milestone
`391efaeb9be5668d6409e5374a435209c205d725`). Pushed github first, then ngit, separately.
