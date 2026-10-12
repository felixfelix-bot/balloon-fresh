# Uplink link budget — ground → balloon at 2.4 GHz, realistic ground antennas

**Status:** `docs/analysis/` findings document — design only; it orders nothing and buys nothing.
**Date:** 2026-10-10
**Branch:** `docs/gap-tracking` (off `origin/main` @ `1cab792`).
**Direction:** **ground → balloon** (the 2.4 GHz *uplink*).
**Range used:** **300.24 km** slant.
**Reproduces:** every line below is arithmetic shown in full; re-check with
`python3 -c "import math; print(32.44+20*math.log10(2450)+20*math.log10(300.24))"`.
**Corrects:** `docs/analysis/GAP-TRACKING-CHECKLIST.md` row **RF-02** — the existing
`docs/2G4-LINK-BUDGET-ANALYSIS.md` budgeted this link against a **LoRa** sensitivity (−141.5 dBm),
~40 dB optimistic for the FLRC/high-rate mission.

---

## Verdict first

At **300.24 km**, with the project's own path loss and a **−99.5 dBm** receiver sensitivity for the
2 MHz high-rate mode:

| Ground station | Verdict at 300.24 km |
|---|---|
| **6 dBi omni** | **Does NOT close** on any *legal* footing below ~27 W that a pico-balloon ground station would field. Closes only with a **≥ 26.7 W** transmitter (Klasse A, +44.27 dBm) — see §3, §5. |
| **12 dBi Yagi** | **Does NOT close on Klasse E** (5 W PEP → **−1.28 dB** margin, just short). **Closes on Klasse A** (75 W PEP → **+10.48 dB**). |
| **20 dBi Yagi** | **Closes on Klasse E** (+6.72 dB) and easily on Klasse A (+18.48 dB). |
| **24 dBi dish** | **Closes on Klasse E** (+10.72 dB) and comfortably on Klasse A (+22.48 dB). |
| **Any antenna on the licence-exempt (ISM) footing** (EIRP ≤ 14.26 dBm on this modulation) | **Does NOT close** — **−36.01 dB** at 300.24 km. The uplink is **amateur-footing only** at this range. |

**The single sentence:** *a 300 km 2.4 GHz uplink closes with a **20 dBi Yagi** or a **24 dBi dish** on
a **Klasse E (5 W PEP)** amateur licence, and with a **12 dBi Yagi** on **Klasse A (75 W PEP)**; it
does **not** close on the licence-exempt footing at any realistic antenna, which is why the repo's
~4–5 km ISM radius existed.* The load-bearing knob is the **transmit power + ground aperture**, not
the receiver — every combination here already assumes a **0 dBi** balloon antenna.

---

## 1. Inputs (every number, with its source)

### 1.1 Path loss — the project's real figure

**FSPL = 149.77 dB at 300.24 km** (the figure supplied for this analysis). It reproduces exactly at
the **upper edge of the 2400–2450 MHz band**:

```
FSPL = 32.44 + 20·log10(f_MHz) + 20·log10(d_km)
     = 32.44 + 20·log10(2450) + 20·log10(300.24)
     = 32.44 + 67.7825 + 49.5515
     = 149.774 dB  →  149.77 dB
```

For reference, the same range at the **2400 MHz** edge is **149.60 dB** (0.17 dB lower), and the
repo's 433 MHz figure at 300 km is **134.7 dB** (the 15 dB band difference is the biggest lever in
the whole program — `docs/analysis/PROGRAM-GAP-ANALYSIS-ROUND2.md` §3). This budget uses the
**149.77 dB** figure as instructed.

### 1.2 Receiver sensitivity — the 2 MHz high-rate mode

**S = −99.5 dBm.** Two independent derivations, agreeing to 0.5 dB:

**(a) Noise-floor derivation (the project's own).**
`docs/analysis/PROGRAM-GAP-ANALYSIS-ROUND2.md` §3:
```
thermal noise floor in 2 MHz = −174 + 10·log10(2e6)
                            = −174 + 63.01 = −110.99 dBm
S = noise floor + NF + SNR_req = −110.99 + 1.5 + 10.0 = −99.49 dBm  →  −99.5 dBm
```
(1.5 dB NF = ZX60-P103LN+ 0.5 dB + ~1 dB feed/mix; 10 dB in-channel SNR carried over the ~1.65 dB
Shannon floor.)

**(b) Datasheet, in-repo.** `docs/lr2021-research/semtech-official/LR2021_LR2022_LR2012_Datasheet_v2.2.pdf`,
**Table 3-12** ("FLRC 1% PER", p. 50):
```
FLRC_2600_CR05_2G4_S  – Sensitivity 1% PER 2.4 GHz, BRF = 2600 kbps, CR = 3/4,
                        effective bit rate = 1.95 Mbps  →  −99 dBm
```
Sub-GHz rows for the same mode: `FLRC_2600_CR05_915_S = −100.5 dBm` (915 MHz). There is **no
433 MHz-specific FLRC row** → `TODO(unverified)`.

### 1.3 The sensitivity the *existing* budget wrongly used (why this document exists)

| Figure | What it is | Source |
|---|---|---|
| **−141.5 dBm** | **LoRa, sub-GHz, BW 125 kHz** — used for the 2.4 GHz uplink in `docs/2G4-LINK-BUDGET-ANALYSIS.md` (lines 76, 89) | Datasheet front page: *"LoRa sub-GHz: −141.5 dBm @ LoRa 125 kHz"*; and Table 3-17 (`LORA_SUB_…` rows) |
| **−129.5 dBm** | LoRa 2.4 GHz, SF12 / BW 1000 kHz | Datasheet **Table 3-18**, `LORA_2G4_1000_SF12` (line 3493) |
| **−99 dBm** | **FLRC 2.4 GHz, 2600 kbps CR 3/4** — the mode the mission actually flies | Datasheet **Table 3-12**, `FLRC_2600_CR05_2G4_S` |

**The error is up to ~42.5 dB** (−141.5 vs −99). Any uplink budget written on the LoRa number makes a
300 km link look comfortable when it is not. This document uses **−99.5 dBm**.

### 1.4 Transmit power — explicit, stated

FLRC is **constant-envelope** (GMSK + FEC), so **PEP ≈ average**, and conducted and EIRP are directly
comparable (`docs/adr/073-…`; `docs/analysis/433-lna-substitution-and-amateur-licence.md` §2.5).

| Footing | Conducted power | EIRP basis |
|---|---|---|
| **Licence-exempt / ISM** (the committed design point, ADR-039/041) | — | **EIRP ≤ 14.26 dBm** — the ISM arm `min(20 dBm, 10 dBm/MHz + 10·log10(BW))` at the 2.666 MHz occupied BW: `10 + 10·log10(2.666) = 14.26 dBm` |
| **German amateur, Klasse E** | **5 W PEP = +36.99 dBm** (2400–2450 MHz) | EIRP = Ptx + G_tx − L_feed |
| **German amateur, Klasse A** | **75 W PEP = +48.75 dBm** (2400–2450 MHz) | EIRP = Ptx + G_tx − L_feed |

Sources: `docs/analysis/433-lna-substitution-and-amateur-licence.md` §2.1 (AFuV Anlage 1, Lfd. Nr. 23:
Kl. A 75 W PEP / Kl. E 5 W PEP on 2400–2450 MHz) and §2.5 (the 14.26 dBm ISM EIRP arm);
`docs/adr/039-licence-exempt-433-design-point.md` (the ISM design point).

### 1.5 Ground antennas and the balloon end

| Ground antenna | Gain | Note |
|---|---:|---|
| Omni | **6 dBi** | the "accessible Tier-0" end |
| Yagi (medium) | **12 dBi** | |
| Yagi (large) | **20 dBi** | ~4 m long, ~2 m boom (§6) |
| Dish / reflector | **24 dBi** | |

**Balloon receive antenna: `G_balloon = 0 dBi`** — no attitude control; the repo's conservative
assumption (ADR-066, ADR-081). **Feed loss `L_feed` is stated per table** (0 dB in §3; the realistic
Airborne-10 **1.92 dB / 10 m** from `docs/BASE-STATION-BOARD-CHECKLIST.md` row 12, i.e. **2.88 dB for
15 m**, in §4).

---

## 2. The closure condition

```
Prx    = Ptx + G_tx + G_balloon − FSPL − L_feed        (dBm)
margin = Prx − S

Substituting the fixed values (G_balloon = 0, FSPL = 149.77, S = −99.5):

margin = Ptx + G_tx − L_feed − 149.77 + 99.5
       = Ptx + G_tx − L_feed − 50.27                   (dB)

CLOSE  ⇔  Ptx + G_tx − L_feed  ≥  50.27 dB
```

The budget is dominated by one number: **Ptx + G_tx must reach 50.27 dB.** That is the whole problem,
and it is why the answer turns on **transmit power × ground aperture**, not on the receiver.

---

## 3. Main table — margin per (transmit power × ground antenna), no feed loss

`G_balloon = 0 dBi`, `FSPL = 149.77 dB`, `S = −99.5 dBm`. Margin in **dB** (positive = CLOSES).

| Transmit power (conducted) | 6 dBi omni | 12 dBi Yagi | 20 dBi Yagi | 24 dBi dish |
|---|---:|---:|---:|---:|
| **ISM EIRP ceiling** = +14.26 dBm **EIRP** (gain forfeit) | **−36.01** ✗ | **−36.01** ✗ | **−36.01** ✗ | **−36.01** ✗ |
| **1 W** (+30.00 dBm) | **−14.27** ✗ | **−8.27** ✗ | **−0.27** ✗ | **+3.73** ✓ |
| **2 W / F33** (+33.00 dBm) | **−11.27** ✗ | **−5.27** ✗ | **+2.73** ✓ | **+6.73** ✓ |
| **Klasse E: 5 W PEP** (+36.99 dBm) | **−7.28** ✗ | **−1.28** ✗ | **+6.72** ✓ | **+10.72** ✓ |
| **Klasse A: 75 W PEP** (+48.75 dBm) | **+4.48** ✓ | **+10.48** ✓ | **+18.48** ✓ | **+22.48** ✓ |

**Worked example (one cell, fully written out) — 20 dBi Yagi, Klasse E:**
```
Ptx      = +36.99 dBm   (5 W PEP, AFuV Lfd. Nr. 23 Klasse E)
EIRP     = 36.99 + 20 = +56.99 dBm
Prx      = 56.99 − 149.77 + 0 = −92.78 dBm
margin   = −92.78 − (−99.5) = +6.72 dB          → CLOSES
```

**Worked example (the failure the ISM footing produces) — 24 dBi dish, ISM ceiling:**
```
EIRP     = +14.26 dBm   (the ISM cap at 2.666 MHz BW — gain above this is forfeit)
Prx      = 14.26 − 149.77 + 0 = −135.51 dBm
margin   = −135.51 − (−99.5) = −36.01 dB        → DOES NOT CLOSE
```

---

## 4. With a realistic ground feeder — 15 m Airborne-10, 2.88 dB

Airborne 10 (LMR-400 class) attenuates **1.92 dB / 10 m at 2.4 GHz**
(`docs/BASE-STATION-BOARD-CHECKLIST.md` row 12) → **2.88 dB** for the 15 m run in that row. This is
the *conservative* case (feed loss in the ground TX chain); a **masthead PA** would remove it (§6).

| Transmit power | 6 dBi omni | 12 dBi Yagi | 20 dBi Yagi | 24 dBi dish |
|---|---:|---:|---:|---:|
| **Klasse E** (+36.99 dBm) | **−10.16** ✗ | **−4.16** ✗ | **+3.84** ✓ | **+7.84** ✓ |
| **Klasse A** (+48.75 dBm) | **+1.60** ✓ | **+7.60** ✓ | **+15.60** ✓ | **+19.60** ✓ |

**Reading:** 2.88 dB of feeder drops the Kl.-E / 20 dBi Yagi margin from **+6.72 dB to +3.84 dB** —
still closing, but it is exactly the kind of loss that argues for putting the PA (and the DSA) at the
**masthead**, which is also the **MECH-01** decision in the tracking checklist.

---

## 5. Minimum transmit power per antenna (the inverse question)

For each antenna, the conducted power that exactly closes `Ptx + G_tx ≥ 50.27 dB` (no feed loss):

| Ground antenna | Minimum Ptx | In watts |
|---|---:|---:|
| 6 dBi omni | **+44.27 dBm** | **26.73 W** |
| 12 dBi Yagi | **+38.27 dBm** | **6.71 W** |
| 20 dBi Yagi | **+30.27 dBm** | **1.06 W** |
| 24 dBi dish | **+26.27 dBm** | **0.42 W** |

Add the **Klasse E** and **Klasse A** conducted ceilings for reference: 5 W (+36.99) and 75 W
(+48.75). **Only the 6 dBi omni needs a power above Klasse E; every directional antenna closes within
Klasse E**, and the 24 dBi dish closes with **424 mW**.

---

## 6. Reading the result — which close, which do not, and why

1. **The uplink is amateur-footing-only at 300 km.** On the **ISM** ceiling (**14.26 dBm EIRP** —
   ADR-039 / ADR-041) the link is **−12 to −36 dB short** at every antenna. This is the arithmetic
   behind the repo's retired *"~4–5 km local service"* radius: the ISM PSD/PSR arm, not the
   propagation, was the binding constraint (`docs/analysis/433-lna-substitution-and-amateur-licence.md`
   §2.5).
2. **Klasse E (5 W PEP) closes with a 20 dBi Yagi (+6.72 dB) or a 24 dBi dish (+10.72 dB)** and fails
   on a 6 dBi omni (−7.28 dB) and a 12 dBi Yagi (−1.28 dB, marginal).
3. **Klasse A (75 W PEP) closes with everything**, from a 6 dBi omni (+4.48 dB) up.
4. **Every combination above already assumes a 0 dBi balloon antenna** — the conservative case. Any
   real balloon-side gain only adds margin.
5. **Feed loss is not cosmetic** (§4): 2.88 dB can flip a marginal Kl.-E link, and it argues for a
   masthead PA/DSA (**MECH-01**).
6. **The 20 dBi Yagi is a substantial wind sail** (~4 m long, ~2 m boom —
   `docs/analysis/PROGRAM-GAP-ANALYSIS-ROUND2.md` §6), which is the mechanical reason the repo prefers
   a **modest dish** (ADR-078) over a large Yagi for the uplink aperture.

> **Reconciling "gain is EIRP-inert above ~8 dBi" (ADR-081 D1).** That statement is true **on the ISM
> footing**, where the 2.4 GHz EIRP is capped at 14.26–20 dBm no matter how much antenna you add. On
> the **amateur footing** the cap is the **class PEP** (5 W / 75 W), so ground gain is **not** inert —
> it trades directly against margin. The two footings give **different** antenna economics, which is
> exactly why the ground-station ADRs must be re-baselined on one footing before the aperture is
> bought (round-2 decision **D1**).

---

## 7. Honest limits

- **No 433- or 2.4 GHz-specific FLRC sensitivity is characterised at 2400–2450 MHz in the repo for
  the exact 1.3 Mbps / 1.333 MHz mode** the 433 ceiling forces; the 2.6 Mbps 2.4 GHz row (−99 dBm) is
  used. `TODO(unverified)`.
- **`G_balloon = 0 dBi`, no fade margin, no polarisation loss, no implementation loss** are assumed —
  this is a **free-space closure** budget, an *upper bound* on range (equal to the assumption set the
  repo uses in `docs/analysis/ground-station-flrc-max-throughput.md` §1.3).
- **The balloon's receive chain NF is not modelled** — S = −99.5 dBm already *includes* a 1.5 dB NF in
  its derivation (§1.2a); a cheaper balloon front end would push S up and shrink every margin above.
- **Prices are not touched.** This document computes link margins only; it adds no part and no price.

---

## Appendix — provenance and reproduce

```bash
# FSPL
python3 -c "import math;print(32.44+20*math.log10(2450)+20*math.log10(300.24))"   # 149.774
# noise-floor sensitivity
python3 -c "print(-174+10*math.log10(2e6)+1.5+10)"                                 # -99.49
# closure condition and one cell
python3 -c "P,G,L=36.99,20,0; print(P+G-L-149.77+99.5)"                            # +6.72
```

- **Datasheet:** `docs/lr2021-research/semtech-official/LR2021_LR2022_LR2012_Datasheet_v2.2.pdf` —
  Table 3-12 (`FLRC_2600_CR05_2G4_S = −99 dBm`; `FLRC_2600_CR05_915_S = −100.5 dBm`), Table 3-18
  (`LORA_2G4_1000_SF12 = −129.5 dBm`), front page (`LoRa sub-GHz −141.5 dBm @ 125 kHz`).
- **Power / legal:** `docs/analysis/433-lna-substitution-and-amateur-licence.md` §2.1, §2.5;
  `docs/adr/039-licence-exempt-433-design-point.md`; `docs/adr/041-rf-frontend-licence-exempt.md`.
- **Feed / antennas:** `docs/BASE-STATION-BOARD-CHECKLIST.md` rows 9, 12; ADR-078.
- **The error this corrects:** `docs/2G4-LINK-BUDGET-ANALYSIS.md` lines 76, 89;
  `docs/analysis/GAP-TRACKING-CHECKLIST.md` row RF-02.
