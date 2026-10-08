# REPORT — design/amplifier-substitution

**Task:** determine whether ground-station **amplifiers** (2.4 GHz PA on the uplink, 433 LNA
on the downlink) are a cheaper way to buy link budget than **antenna gain**, and whether
trading antenna gain for amplifier gain widens the beam enough to **collapse the
antenna-tracker requirement**. Cost + gain-per-euro only; regulatory questions explicitly
out of scope (operator instruction).

**Branch:** `design/amplifier-substitution` off `github/main` (`09e1b69`).
**Worktree:** `/home/c03rad0r/worktrees/bf-amps`.

## Deliverables

| File | What |
|---|---|
| `docs/analysis/ground-station-amplifier-vs-antenna.md` | the analysis (all numbers sourced/computed/assumed, 3 costed stations, breakdown points) |
| `docs/analysis/ground_station_amp_vs_ant_model.py` | repro: `python3 docs/analysis/ground_station_amp_vs_ant_model.py` prints every numeric table |
| `docs/analysis/assets/ground-station-amp-vs-ant-figure.svg` (+`.png`) | beamwidth/tracker + €/dB figure; generator `docs/analysis/ground_station_amp_vs_ant_figure.py` |
| `docs/analysis/assets/consult-verdict-amp-vs-ant.txt` | visual-consultant verdict (verbatim) |
| `docs/adr/068-ground-station-amplifier-vs-antenna.md` | ADR draft (068 verified free on all github/ngit branches; 066/067 already claimed) |
| `PROGRESS.md` | milestone log |

## Answer (short)

**The operator's hypothesis is confirmed on transmit and refuted on receive.**

* **2.4 GHz uplink (ground TX):** a ground PA substitutes for ground TX-antenna gain **1:1 in
  EIRP**, at **€5.75–8.30/dB** (DXpatrol QO100-PA-1W €69; QO100-AMP12 €185) versus
  **€15.6–19.9/dB** for a 2.4 GHz dish + feed — **2–2.7× cheaper per dB**. Replacing the
  ~27 dBi dish (7.3° beam, 0.73° pointing budget) with a modest ≤15 dBi antenna widens the
  ground TX beam to ≥29°, and since both bands share **one** positioner the station's pointing
  need drops to the 433 Yagi's beam — **collapsing the tracker from a €1,260 commercial az/el
  rotator to a €40 open-loop stepper (≈€1,220 saving).** This is the design's biggest cost lever.
* **433 MHz downlink (ground RX):** an LNA does **not** substitute 1:1. Its real benefit is the
  **noise-figure delta**, which the Friis cascade caps at **≈6.4 dB** — so the honest cost is
  **€40.4/dB**, not the headline €12.85/dB — versus a 433 Yagi at **€3.24–8.3/dB**. Dropping
  antenna gain also costs **3.17 dB** of noise temperature (2.4 GHz: 4.63 dB).

**Three costed stations**

| | Cost | Link dB | €/dB | Tracker class | DC |
|---|---:|---:|---:|---|---|
| A antenna-led | €2,044.72 | 35.0 | €58.4 | commercial az/el (€1,260.82) | none |
| B amplifier-led | €1,041.00 | 42.2 | €24.7 | open-loop stepper (€40) | **~27 W DC** |
| **C balanced (rec.)** | **€1,031.50** | **41.8** | **€24.7** | open-loop/light rotator | **2.25 W DC** |

A is **dominated** (2× cost, fewer dB). B and C tie on cost and €/dB; **C is recommended**
because it reaches the same link with a **1 W** PA and so avoids the 12 W PA's three problems.

**Where the amplifier approach breaks down (exact points)**

1. **Receive ceiling ≈6.4 dB** — no LNA can buy more; the rest must come from antenna gain.
2. **Noise-temperature penalty:** 4.63 dB @2.4 GHz, 3.17 dB @433 — unrecoverable.
3. **Balloon RX overload:** LR2021 absolute-max RF input **+10 dBm** (Table 3-1); a 12 W PA +
   27 dBi dish (EIRP +67.8 dBm) **blocks the balloon RX within ~772 m** (69 m with a 7 dBi TX
   antenna). Never pair a big dish with a big PA.
4. **Self-desense:** a 12 W 2.4 GHz PA **blocks the co-located 433 LNA inside ~10 m** —
   incompatible with ADR-034's simultaneous TX/RX unless power ≤1 W, or ≥10 m separation, or
   sequencing (which forfeits simultaneity).
5. **DC/thermal:** the 12 W PA is **~27–33 W DC (~2.3–2.8 A @12 V)** — car-battery class.

## Sourcing discipline

Every price, NF, gain, P1dB and max-input is cited with a URL (WiMo DE, Funktechnik Bielefeld,
hm-sat, RF Hamdesign/RF Hamstore) or a datasheet table (Semtech LR2021 v2.2 Table 3-1 / 3-12 /
3-22; G-NiceRF F33 v1.1). Unknown values are `TODO(unverified)` — listed in §8 of the analysis.
No part or figure was invented.

## Consultant

`scripts/fleet/visual_consult.py` on the figure — served model **`gpt-6-astra`**,
`visual_review: APPROVED`, substance **CONFIRMED with qualifications** (the qualifier: present
the beamwidth/tracker-class and €/dB conclusions as *approximate, assumption-dependent* — which
the analysis already does, stating η, T_ant and the receiver NF as explicit assumptions).
Full verdict verbatim: `docs/analysis/assets/consult-verdict-amp-vs-ant.txt`; reproduced in the
analysis §7.

## Push evidence

Pushed **github first, then ngit separately** (never `--atomic`, never `main`/`master`).

Branch: `design/amplifier-substitution`

| Where | SHA |
|---|---|
| LOCAL | `02fb4a154d557969dfbde417817e5f44e84f8407` |
| GITHUB | `02fb4a154d557969dfbde417817e5f44e84f8407` |
| NGIT   | `02fb4a154d557969dfbde417817e5f44e84f8407` |

Verified with `git ls-remote github refs/heads/design/amplifier-substitution` and
`git ls-remote ngit refs/heads/design/amplifier-substitution`. Commits: `478138f` (analysis + model)
→ `02fb4a1` (figure + consult + ADR-068 + report). Milestone-1 push was verified green on both
remotes before the second commit (same method).
