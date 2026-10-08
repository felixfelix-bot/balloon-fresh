# ADR-068 — Ground station: buy the uplink's dB with a 2.4 GHz PA (which collapses the tracker), but keep antenna gain for the 433 downlink

- **Status:** **Proposed** — the analysis is complete and cited; the *text* has not been
  accepted by a human.
- **Date:** 2026-10-08
- **Decision owner:** Felix (operator)
- **Author:** Hermes subagent (design analysis), per the operator's 2026-10-08 instruction to
  test whether ground-station **amplifiers** (2.4 GHz PA on the uplink, 433 MHz LNA on the
  downlink) are a cheaper way to buy link budget than **antenna gain** — and specifically
  whether trading antenna gain for amplifier gain widens the beam enough to collapse the
  antenna-tracker requirement. Cost and gain-per-euro only; regulatory questions excluded by
  the same instruction.
- **Companion evidence:** `docs/analysis/ground-station-amplifier-vs-antenna.md`
  (every price/NF/gain/P1dB with a URL; three costed stations; consultant verdict recorded).
  Repro: `python3 docs/analysis/ground_station_amp_vs_ant_model.py`.
  Figure: `docs/analysis/assets/ground-station-amp-vs-ant-figure.svg`.
- **Related:** ADR-034 (433 TX / 2.4 GHz RX band split — the direction mapping this ADR types
  against), ADR-066 / ADR-067 (ground-station positioner & dish — this ADR *contests the
  antenna choice* those records assume), ADR-039 / ADR-041 (licence-exempt RF front end —
  the regulatory question explicitly **deferred**, not answered, here), ADR-047 (v9 power),
  ADR-005 (SKY66112 FEM), ADR-037 (MCU-S3 no-FEM).
- **Numbering note:** `068` verified unused on **all** `github/*` and `ngit/*` branches this
  session (`git ls-tree -r --name-only <ref> docs/adr` across every ref: the highest allocated
  low-band numbers are `066`, `067` — both claimed on other branches — and `100–110`; `068` is
  the next genuinely free low number). `scripts/adr_next_number.py` was **not found** in this
  repo (`find` over `repos/`, `hermes-orchestration/` returned nothing), so the check was done
  manually and is recorded here. Do not hand-pick; re-run the check if the script appears.

---

## Context

The ground station must close two links (ADR-034): a **2.4 GHz uplink** (ground transmits,
balloon receives) and a **433 MHz downlink** (balloon transmits, ground receives). ADR-066/067
sized the ground antennas generously — up to a **0.74–1.9 m 433 dish** and a **Ku-band dish
reused at 2.4 GHz (~21–27 dBi)** on a shared az/el positioner. High antenna gain means a narrow
beam, and a narrow beam means a demanding tracker: at 27 dBi / 2.4 GHz the beam is **7.3°** and
the pointing budget (10 % of beamwidth) is **0.73°**, which in practice means a commercial az/el
rotator (SPID RAS €1,260.82 → BIG-RAS €1,775.00).

The operator asked whether the same link can be bought more cheaply by **amplification**:
a ground **2.4 GHz power amplifier** substituting for ground TX-antenna gain (EIRP), and a
ground **433 MHz LNA** substituting for ground RX-antenna gain — with the *side benefit* that a
lower-gain antenna has a **wider beam**, so the tracker requirement might collapse to a hand-aim
mount or an open-loop stepper.

The analysis (`docs/analysis/ground-station-amplifier-vs-antenna.md`) prices both routes with
sourced parts and finds the substitution is **asymmetric**: it holds on transmit and fails on
receive.

The numbers that decide it (all sourced; €/dB in the companion doc §2):

* **2.4 GHz PA:** DXpatrol QO100-PA-1W **€69** (+30 dBm, 12 dB gain) → **€5.75/dB**;
  QO100-AMP12 **€185** (12 W, ~24 dB gain) → **€8.30/dB**. A 2.4 GHz dish + feed is
  **€15.6–19.9/dB** — the PA is **2–2.7× cheaper per dB**.
* **433 LNA:** SSB Electronic LNA ISM 433 **€257** (20 dB gain, **0.7 dB NF**). Its *raw* gain
  suggests €12.85/dB, but the **Friis cascade caps its real benefit at ≈ 6.4 dB**, making the
  honest cost **€40.4/dB** — versus a 433 Yagi at **€3.24/dB** marginal (13.1→14.8 dBi) and
  **€8.3/dB** (6→15 dBi in one antenna).
* **Beamwidth/tracker:** 27 dBi / 2.4 GHz → 7.3° → 0.73° budget → commercial rotator;
  15 dBi → 29.0° → 2.90° → open-loop stepper (€40); 7 dBi → 81.7° → hand-aim/none.
  Because both bands share **one** positioner, the station's pointing need is set by the
  **narrowest** beam — so removing the 2.4 GHz dish removes the tracker requirement.

## Decision

1. **Do NOT buy the 2.4 GHz uplink's margin with ground antenna gain.** Buy it with a **ground
   2.4 GHz PA**, and keep the ground 2.4 GHz antenna **modest (≤ ~15 dBi)** so the ground
   transmit beam stays ≥ ~29°. This is the operator's hypothesis, and it is **adopted** for the
   transmit direction.

2. **DO buy the 433 MHz downlink's margin with ground antenna gain (a 13–15 dBi Yagi), not with
   an LNA.** An LNA is not a 1:1 substitute on receive: its link benefit is capped at ~6.4 dB by
   the noise-figure cascade, and dropping antenna gain adds a **3.17 dB** noise-temperature
   penalty. Reserve the LNA for the case where the Yagi has run out (~15–18 dBi) or where a very
   low NF is required against a warm antenna.

3. **Cap the ground 2.4 GHz PA at the ~1 W class (+30 dBm, €69) for the co-located station.**
   The 12 W PA (€185) is **not** adopted with a co-located 433 LNA: at 12 W the ground
   transmitter **blocks its own 433 receiver inside ~10 m** (self-desense), saturates the
   balloon's receiver inside **~772 m** (if paired with a 27 dBi dish) or 69 m (with a 7 dBi
   antenna), and draws **~27 W DC**. If a higher-power uplink is ever needed, it requires
   **≥10 m antenna separation + a coaxial limiter + a 2.4 GHz TX filter + T/R sequencing**, and
   sequencing forfeits the simultaneity ADR-034 bought.

4. **Adopt the "balanced" ground station (Candidate C of the companion doc)** as the design
   baseline: 433 RX = Diamond A-430S15R 14.8 dBi (€74.50); 2.4 TX = 13 cm Yagi ~15 dBi (€239) +
   DXpatrol QO100-PA-1W (€69); positioner = open-loop stepper (€40) or light rotator
   (Yaesu G-450CDC €359–399). **Station ≈ €1,032, ≈ €24.7/dB, 2.25 W DC.**
   This supersedes, *for the ground antenna/tracker choice*, the dish-based sizing in ADR-066/067.

5. **Recorded alternative, NOT selected: the "amplifier-led" station (Candidate B)** — 433 RX =
   7 dBi Yagi + 433 LNA; 2.4 TX = 7 dBi antenna + 12 W PA; open-loop stepper. Cost ≈ €1,041,
   ≈ €24.7/dB — the same money as the balanced station, but it carries the three 12 W problems in
   decision 3 and is therefore rejected. Recorded so it is not silently re-proposed.

6. **Recorded alternative, NOT selected: the "antenna-led" station (Candidate A)** —
   14 dBi 433 Yagi + 1.0 m Ku dish (~21–27 dBi) + SPID RAS (€1,260.82). Cost ≈ €2,045,
   ≈ €58.4/dB. It is **dominated**: ~2× the cost for **fewer** link dB than B or C, because it
   buys a narrow beam and must then buy the tracker to hold it.

## Consequences

1. **The tracker collapses by ≈ €1,220** (€1,260.82 rotator → €40 open-loop stepper), driven by
   replacing the 2.4 GHz dish with a modest antenna. This is the largest single cost lever found.
2. **The narrow-beam tracker is not a *speed* problem** — the balloon's apparent rate at 300 km
   is ~0.006°/s (0.73° budget lasts ~127 s), so a **telemetry-fed open-loop** re-point suffices
   even for a dish. The tracker class is set by **mount stiffness and absolute accuracy**, not by
   tracking speed; the dish's stiffness requirement is what costs the money.
3. **Absolute limits are now recorded as numbers**, not adjectives: the LNA **cannot** buy more
   than ~6.4 dB on receive; the wider beam costs **4.63 dB @2.4 GHz / 3.17 dB @433** in noise
   temperature; the balloon RX's **absolute-max input is +10 dBm** (LR2021 Table 3-1) and its
   blocking thresholds are **−20…−32 dBm**, so a big dish + big PA is forbidden.
4. **DC/thermal becomes a real line item** for any PA above ~1 W: ~27 W DC ≈ 2.3–2.8 A at 12 V —
   a car battery, not a field pack.
5. **The regulatory question is untouched.** This ADR types against capability and cost only.
   Whether the ground may legally run a 2.4 GHz PA at the chosen output remains a separate
   question owned by ADR-039 / ADR-041.

## What would falsify this

* A bench/field measurement showing the ground 433 **receiver's own NF is already so low** that
  an LNA's cascade benefit is < 2 dB (making the LNA even worse value), **or** that a site's
  man-made noise floor dominates the system NF (in which case *neither* antenna gain nor an LNA
  buys dB, and the whole receive-side analysis changes).
* A measurement showing the F33-2G4's **module-level max input** is far above the chip's +10 dBm
  (making the balloon-overload keep-out much smaller than computed) — this would weaken
  decision 3 and could revive the 12 W option.
* A measurement showing a **0.7 dB-NF 433 LNA survives** a co-located 12 W 2.4 GHz PA with a
  real filter and a limiter at ≤ 1 m separation — this would remove the self-desense objection
  to decision 3.
* A 433 MHz receive requirement that the 15 dBi Yagi cannot meet **and** that the LNA's ~6.4 dB
  cannot close — which would force the 433 dish back and reopen the shared-positioner question.
