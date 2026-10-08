# ADR-070 — Ground station: do NOT build an amplifier-led design; the balloon-side F33 is the only gain per dollar that clears the bar

- **Status:** **Proposed** — the analysis is complete and cited; the *text* has not been
  accepted by a human.
- **Date:** 2026-10-08
- **Decision owner:** Felix (operator)
- **Author:** Hermes subagent (design analysis), per the operator's 2026-10-08 questions:
  *"an amplifier makes sense on the transmitter but not on the receiver, right?"*, *"what
  about a Yagi array?"*, *"use a separate antenna tracker for each Yagi and combine
  multiple Yagis — lots of cheap trackers working together"*, *"can we control the amplifier
  gain externally to fix the close-range overload?"*, and *"I already own a 2.4 GHz
  circulator and a 2.4 GHz amplifier"*.
- **Related:** **ADR-068** (the cost metric: price gain AND the rig in the same unit — this
  ADR uses its metric and its Yagi-before-dish decision); **ADR-067** (F33 433 TX power +
  coarse mesh — the F33 trade this ADR re-verifies); **ADR-066** (low-power 433 ground
  station, shared positioner — the negative required uplink ground gain); **ADR-034**
  (433 TX / 2.4 GHz RX band split — the fact that decides Q5); ADR-039/ADR-041 (licence-exempt
  design point and RF front end); ADR-005 (SKY66112 FEM, the only in-repo LNA NF).
- **Companion evidence:** `docs/analysis/ground-station-amplifier-hypothesis-check.md` — the
  five answers, the Friis/array/combining/T-R arithmetic and the €/dB ledger. Repro:
  `python3 docs/analysis/ground_station_amplifier_hypothesis_model.py` (prints every table
  verbatim); figure: `/usr/bin/python3 docs/analysis/render_amplifier_hypothesis_figure.py`.
- **Consulted:** fleet visual consultant — served model and verbatim verdict recorded in
  §10 of the companion analysis. A visual consult is **not** a code review and does **not**
  satisfy the ADR-010 review gate.
- **Numbering note (this is a DEFECT to record, not to fix by renaming):**
  `scripts/adr_next_number.py` → **66**, and `docs/adr/INDEX.md` (on `main`) still says
  *"next free … 066"*. **That is stale.** Verified against **every** `github/*` branch:
  **`066` is claimed** (`design/ground-station-lowpower-link` +
  `design/ground-station-flrc-max`), **`067` is claimed TWICE**
  (`design/ground-station-flrc-max` → `067-flrc-max-433-tx-power-and-coarse-mesh.md` **and**
  `design/positioner-lowcost` → `067-positioner-architecture.md` — a **number collision**),
  **`068` is claimed** (`design/gain-per-dollar` + `design/gain-per-dollar-cliff`), and
  **`069` is claimed** (`design/tier0-accessible`). **`070` was verified free on every
  inspected `github/*` branch** before use. Do not hand-pick; re-run the script **and**
  re-check the branches, and fix `INDEX.md`'s "next free" line to stop the next session
  walking into 066.

---

## Context

The operator is evaluating an **amplifier-led ground station**: put the gain on the *ground*
(using a 2.4 GHz amplifier and circulator the operator already owns) rather than buying the
F33's 20 dB of transmit power on the balloon. Four prior branches settled the surrounding
terrain — the €/dB metric (ADR-068), the F33 trade and mesh wind model (ADR-067), the
low-power 433 link and its negative required uplink gain (ADR-066), and the antenna prices
(`design/ground-station-bom`). What none of them settled is whether **amplification** is the
right lever, and three of the operator's five premises turned out to be wrong or
half-wrong, so the answer needed its own record.

The committed architecture the decision must fit (`ADR-034`, reproduced in
`ground-station-gain-per-dollar.md` §1.3):

```
  balloon TX = 433 MHz (downlink)   <- the BINDING direction; sets the ground gain needed
  balloon RX = 2.4 GHz (uplink)     <- required ground gain is NEGATIVE (-10.7 dBi @ 650 km)
```

The bar to beat is the **F33 module on the balloon: ~USD 8 for +20 dB = 0.40 USD/dB**
(low-power board / licence-exempt point at +12.15 dBm to the F33's +33 dBm;
`docs/F33-MODULE-PLAN.md`, `flrc-max` REC-1, ADR-067/068 §Decision 6).

---

## Decision

**1. DO NOT build an amplifier-led ground station.** The gain the operator already owns is in
the **wrong band**: a 2.4 GHz amplifier can only amplify the **ground→balloon uplink**, and
that uplink (a) already closes with an **omni**, (b) has **+23.1 dB of surplus** with a
12.4 dBi Yagi before any amplifier and **+36.1 dB** with a +33 dBm PA, and (c) cannot help the
**433 downlink**, which is the direction that needs the dB. Measured against the bar, a
2.4 GHz ground PA costs money per **zero needed dB**.

**2. An LNA IS worth using on receive — the operator's Q1 premise is WRONG.** An LNA sets the
system noise figure (Friis), and against a bracketed model it buys **+6.8 … +12.3 dB** of
system noise temperature on the 433 downlink (central case **+9.7 dB** at `T_ant` = 200 K,
receiver NF 8 dB). The priced, fully-specified part is the **SSB Electronic LNA ISM 433 MHz
(€257.00, 20 dB gain, 0.7 dB NF, OIP3 +32 dBm)**, worth **€26.4 per needed dB** — ~72× the
F33's per-needed-dB cost, but a real, needed dB. **It is a RECEIVE amplifier**, and it must be at the
**masthead**.

**3. What an LNA cannot buy is cold-sky directivity — and that is the *smaller* half.** With
the LNA fitted, replacing the wide-beam antenna with a cold-sky dish removes only the
`T_ant` term: **+3.80 dB at 433 MHz** (and only **+1.5–2.8 dB at 2.4 GHz**, because the
2.4 GHz LNA's gain collapses to 10 dB at 2 GHz and cannot suppress the downstream receiver
noise). LNA and directivity are **additive, not alternatives.** Directivity's other benefit —
its own **gain** — is separate (+8.15 dB for a 3.5 m dish over a 14 dBi Yagi).

**4. DO NOT build a Yagi ARRAY for gain.** A practical 433 MHz Yagi is a **2–3 %
(≈9–13 MHz)** antenna; arraying narrows both the match and the beam. Cost: **2-bay €228.40
marginal for +3.0 dB = €76.13/dB**; **4-bay €562.40 for +6.0 dB = €93.73/dB** — **207×–255×
the F33's per-dB cost** (**2.9×–3.6× the 433 LNA**). A 2-bay narrows the stacked-plane beamwidth by **10 % (high-gain
10/15-el element) to 32 % (3-el element)**, a 4-bay by **33 %**; the heavier cost is the
**doubled wind moment**, which can step the positioner a class (€80–€1,346). A narrower beam
makes the tracker's job **harder**, which is the opposite of what an amplifier-led /
cheap-tracker strategy needs.

**5. "One cheap tracker per Yagi, combined" ADDS COVERAGE, NOT GAIN.** The signal algebra is
unambiguous: **incoherent** power combining of N branches gives **N× signal AND N× noise =
+0.00 dB**. Only **coherent** combining — a real **phased array** (per-element phase
shifters + continuous correction) or **MRC with N complete receivers** (still predetection /
coherent) — gives **+10·log₁₀N** (+3.01 dB N=2, +6.02 dB N=4). Separate trackers guarantee
separate phase, so they cannot be the coherent case. The **useful** reading of the operator's
idea is **multi-sector coverage**: **0 dB gain**, but it **removes the precision-tracking
requirement**.

**6. Balloon-receiver overdrive is MANAGEABLE but NOT NEEDED.** With a +33 dBm ground PA on a
12.4 dBi Yagi the balloon's LR2021-class receiver reaches the **−20 dBm AGC/LNA compression
onset** inside **≈14.5 m** and hard-overloads inside **≈1.4 m** — anchored on the repo's own
**measured** saturation (`docs/power-sweep-results-2026-07-24.md`). A **step attenuator
(€24.50–39.00)** is a calibration, not a control loop; a **downlink-RSSI closed loop** (the
DXpatrol 12 W PA already exports 0–4 V forward-power/SWR outputs) or **GNSS-range power
control on the balloon** solves it fully; **ground-side AGC cannot** — the overdrive is in the
balloon's receiver. The overdrive exists **only because the PA is oversized ~36 dB for its own
link**, so removing the surplus removes the problem.

**7. The owned 2.4 GHz circulator does NOT solve T/R for this architecture.** With the
committed 433/2.4 GHz split the ground RX and TX are on **different bands**, so the need is a
**diplexer/filter**, not a circulator. If the operator instead intends a **same-band 2.4 GHz
bidirectional** link, a **single ~20 dB circulator is still insufficient** isolation at
+30…+40 dBm: **+13.5 dBm would still reach the RX port** at +33 dBm, and a downstream receiver
would be destroyed. Same-band T/R needs **≈40–55 dB** of isolation, i.e. **circulator + a T/R
switch** or a **T/R amplifier/preamp box** (RT-2400-2 €355; SHF adjustable-gain mast preamp
€151.90; SP-S VOX preamp €345; CX-600N coax relay €142). Note also that **2.4 GHz mast preamps
with integrated T/R are discontinued** (vendor page), so the 2.4 GHz T/R route is *harder*
than the 433 one.

**8. BUILD instead:** the **F33 module on the balloon** (~USD 8, **0.40 USD/dB** — the bar); a
**433 MHz masthead LNA** (€257, **+9.7 dB of T_sys**, **€26.4 per needed dB**) **if** extra
receive margin is wanted; and a **single Yagi** on the DIY tracker (ADR-068).

---

## The ledger (the decision, in one table)

Money per **dB of link-budget improvement in the direction that NEEDS it** — the ADR-068
definition ("price gain AND the rig in the same unit"). For a receive device the dB is the
**T_sys improvement**, not the device's gain.

| candidate | money | dB | per needed dB |
|---|---:|---:|---:|
| **F33 module on the balloon** (+12.15 → +33 dBm) | 8.00 **USD** | 20.0 | **0.40 USD/dB** ← the bar |
| F33, alternative reading (chip +22 → +33 dBm) | 8.00 USD | 11.0 | 0.73 USD/dB |
| **433 masthead LNA** (system dB) | 257.00 EUR | 9.7 | **26.41 EUR/dB** |
| **2-bay Yagi array** (marginal over one Yagi) | 228.40 EUR | 3.0 | **76.13 EUR/dB** |
| **4-bay Yagi array** (marginal over one Yagi) | 562.40 EUR | 6.0 | **93.73 EUR/dB** |
| 1.9 m mesh dish + BIG-RAS — **gain only** | 2,297.00 EUR | 2.84 | 808.80 EUR/dB |
| 1.9 m mesh dish + BIG-RAS — **gain + cold-sky noise** | 2,297.00 EUR | 6.64 | 345.93 EUR/dB |
| **2.4 GHz ground PA** (owned or bought) | 0 – 185 EUR | **0.0** | **INF — zero needed dB** |

**Ranking: F33 (0.40 USD/dB) ≪ 433 LNA (26.4) < 2-bay array (76.1) < 4-bay array (93.7) <
dish+tracker (346–809) < 2.4 GHz ground PA (infinite).** Nothing on the ground competes with
the balloon-side PA, and the *one* ground amplifier that buys needed dB is a **receive** one.

> **Definitional warning for future sessions.** `ground-station-gain-per-dollar.md` Table D
> prints a "€/dB marg" of **136.4** for the 1.9 m dish; that column is
> `marginal € ÷ ABSOLUTE gain`, **not** `Δ€ ÷ ΔG`. Under this ADR's uniform definition the
> dish is **808.80 EUR/dB (gain only)** or **345.93 EUR/dB (gain + cold-sky noise)**. The
> numbers are both reproducible; the difference is the **definition in the cited source**, and
> they must not be compared as if they were the same quantity.

---

## Consequences

- **Cost:** the amplifier-led design has a **marginal** cost of **€207–485** (attenuator +
  real T/R switching that works at +33 dBm + PSU/heatsink) for **zero needed dB**, versus
  **~USD 8** for the F33's **+20 dB**. The decision saves the whole marginal spend.
  *(Ground-side DC power and heat are explicitly **not** a constraint per the operator; the
  PSU/heatsink line is retained only because the metal is still bought.)*
- **Capability:** the recommended rig is unchanged from ADR-068 (Yagi + DIY tracker + F33),
  so this ADR **removes** an option rather than changing the build.
- **Q1 becomes a positive finding, not just a refutation:** the 433 masthead LNA is now a
  costed, optional **receive-margin** device (€26.4/needed dB) with a known **0.46 %
  bandwidth** that **sets the receive system bandwidth** — the operator can buy ~10 dB of
  receive margin for €257, which is the correct answer to *"is an LNA useless on receive?"*
- **Two risks are created by the recommended LNA and must be managed:** (i) it is **narrowband**
  (433–435 MHz), so it forecloses frequency agility outside the ISM band; (ii) it is
  **destroyed by close-range TX leakage** if sharing a transmitting antenna (vendor
  statement), so a **T/R-switched** preamp or a relay is required on a shared antenna.
- **Open items flagged, not resolved (inherited and new):** ADR-039 open item (a)
  (airborne licence-exempt SRD) and the `docs/PAYLOAD-WEIGHT-ESTIMATES.md` §D *"Ground Station
  Only"* F33 classification both still gate the F33; the `TODO(unverified)` LR2021 NF and
  maximum input, the exact 2.4 GHz circulator figures, and the 10/15-el beamwidths remain
  open but are **not** load-bearing for this decision (brackets are shown).
- **The metric becomes the arbiter for any future amplifier proposal:** score it as money per
  **needed** dB in the **direction that needs it**. A gain block scored on its own gain looks
  free and can be in the wrong band; this ADR exists to stop exactly that.

## Alternatives considered and rejected

1. **Amplify the 2.4 GHz uplink with the owned amplifier.** REJECTED — the uplink already has
   +23.1…+36.1 dB of surplus and the amp cannot touch the binding 433 downlink; the dB is in
   the wrong band.
2. **Treat the LNA as useless on receive (the operator's premise).** REJECTED — the Friis
   arithmetic gives it +6.8…+12.3 dB; the premise inverts the truth by ~10 dB.
3. **Buy a Yagi array instead of a single Yagi.** REJECTED — €76–94/needed dB (207–255× the
   F33's per-dB cost, 2.9–3.6× the 433 LNA's), a narrower beam, and a doubled wind moment.
4. **"One cheap tracker per Yagi, combined" as a gain scheme.** REJECTED as a gain scheme
   (+0.00 dB incoherent; coherent/MRC need phase coherence and N radios) — **ACCEPTED as a
   multi-sector COVERAGE scheme**, which removes the precision-tracking requirement at 0 dB
   gain.
5. **Use the owned circulator as the T/R solution.** REJECTED — wrong band for the committed
   split; and at ~20 dB isolation insufficient for a same-band +33 dBm front end.
6. **Fix the overdrive with ground-side AGC.** REJECTED — the overdrive is in the balloon's
   receiver; ground AGC cannot reach it.

## For future sessions

- **One-line rule:** *a dB is not fungible across bands — score every amplifier as money per
  **needed** dB in the direction that needs it; the balloon-side F33 (0.40 USD/dB) beats every
  ground option, and the only ground amplifier worth buying is the receive-side LNA.*
- **Files:** `docs/analysis/ground-station-amplifier-hypothesis-check.md`; model
  `docs/analysis/ground_station_amplifier_hypothesis_model.py`; figure
  `docs/analysis/assets/amplifier-hypothesis-ebar.png` (+ renderer
  `docs/analysis/render_amplifier_hypothesis_figure.py`).
- **Reproduce:** `python3 docs/analysis/ground_station_amplifier_hypothesis_model.py`
  (figure: `/usr/bin/python3 docs/analysis/render_amplifier_hypothesis_figure.py` — the
  repo's default `python3` has no matplotlib; `/usr/bin/python3` does).
- **Read alongside:** ADR-068 (metric + Yagi-before-dish), ADR-067 (F33 + mesh), ADR-066
  (low-power 433 link), ADR-034 (the band split that decides Q5).
