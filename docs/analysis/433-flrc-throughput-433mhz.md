# FLRC throughput achievable inside the 433.05–434.79 MHz band

**Status:** `docs/analysis/` findings document — **not** an ADR; it freezes no mode and orders nothing.
**Date:** 2026-10-10
**Branch:** `docs/gap-tracking` (off `origin/main` @ `1cab792`).
**Question answered:** *what FLRC throughput is actually achievable in the 433.05–434.79 MHz band
(1.74 MHz wide) given the LR2021's occupied-bandwidth modes, and is 2.6 Mbit possible on 433?*
**Reproduces the arithmetic:** `python3 -c "import math; ..."` — every line is shown below.

---

## Verdict first

| Question | Answer |
|---|---|
| Is **2.6 Mbit** possible on 433 (433.05–434.79 MHz)? | **NO — not physically and not legally.** The 2.6 Mbps mode occupies **2.666 MHz DSB**, which is **1.53×** the entire 1.74 MHz allocation. It does not fit, so it cannot be radiated inside the band. Separately, German amateur law caps occupied bandwidth on 70 cm at **2 MHz**, which 2.666 MHz also exceeds. |
| What is the **maximum** FLRC rate on 433? | **1300 kbps raw** (`FLRC_BR_1_300_BW_1_3`, **1.333 MHz DSB**) — the highest LR2021 FLRC mode whose occupied bandwidth fits inside 1.74 MHz *and* inside the 2 MHz legal cap. Effective rate **975 kbps** at the shipped CR 3/4. |
| Where does 2.6 Mbit belong? | The **2.4 GHz link**, whose German amateur occupied-bandwidth cap is **10 MHz** (and which has ~83.5 MHz of ISM spectrum available). |
| Consequence for the committed architecture | **ADR-073 ("433 downlink = FLRC at maximum throughput", i.e. 2.6 Mbps) is a live defect as written** — the maximum on 433 is 1.3 Mbps. The record and the duplexer/filter band plan must move to **1.333 MHz occupied**, not 2.666 MHz, before the filter is frozen. |

---

## 1. The band

The band is **433.050–434.790 MHz** = **434.790 − 433.050 = 1.740 MHz** wide.

Everyone who cares about this band says the same thing about the width:

- **ERC/REC 70-03, Annex 1** — the CEPT SRD recommendation — designates **433.050–434.790 MHz** for
  licence-exempt short-range devices (entries `f` / `f1` / `f2`).
  `docs/analysis/radio-legal-power-limits.md` lines 151–153.
- **German national implementation** (`Vfg. 91/2025`, rows 44a / 44b / 45c) reproduces the same
  band and adds a **≤ 10 % duty cycle** on the 10 mW e.r.p. row.
  `docs/analysis/radio-legal-power-limits.md` lines 126–140, 179.
- The band **sits inside the German amateur 430–440 MHz allocation**.
  `docs/REGULATORY-AMATEUR-LICENCE.md` line 57; `docs/analysis/433-lna-substitution-and-amateur-licence.md` §2.2.

So there is exactly **1.74 MHz of width** to put an FLRC signal in.

---

## 2. The LR2021's FLRC modes (the occupied bandwidths)

The authoritative source is the in-repo Semtech datasheet
`docs/lr2021-research/semtech-official/LR2021_LR2022_LR2012_Datasheet_v2.2.pdf`
(Rev 2.2, **Table 18-1, p. 209**, *"Valid FLRC Bit Rate and Bandwidth Combinations"*). Extracted:

| LR2021 symbol | Raw bit rate `Rb` (Mbps) | Occupied BW (MHz **DSB**) |
|---|---:|---:|
| `FLRC_BR_2_600_BW_2_6` | **2.6** | **2.666** |
| `FLRC_BR_2_080_BW_2_2` | 2.08 | **2.222** |
| `FLRC_BR_1_300_BW_1_3` | **1.3** | **1.333** |
| `FLRC_BR_1_040_BW_1_3` | 1.04 | 1.333 |
| `FLRC_BR_0_650_BW_0_7` | 0.65 | 0.740 |
| `FLRC_BR_0_520_BW_0_6` | 0.52 | 0.571 |
| `FLRC_BR_0_325_BW_0_3` | 0.325 | 0.357 |
| `FLRC_BR_0_260_BW_0_3` | 0.26 | 0.307 |

**Effective (post-FEC) rates** are in **Table 18-2** of the same datasheet: at the shipped coding rate
CR 3/4 the effective rates are **1.95 Mbps** (raw 2.6), **1.56 Mbps** (2.08), **0.975 Mbps** (1.3),
0.78 Mbps (1.04), 0.488 Mbps (0.65). With CR NONE (1) the effective rate equals the raw rate.

> **Internal datasheet note (stated honestly).** Table 3-12's *condition lines* for the sensitivity
> rows are not perfectly consistent with Table 18-1: the 2080 kbps FLRC sensitivity row is annotated
> **`BWF = 2666 kHz`** (not 2.222 MHz), and the 1300 kbps row is annotated **`BWF = 1200 kHz`**
> (not 1.333 MHz). Both readings are in the same Rev 2.2 document. **It makes no difference to the
> conclusion:** whether the 2080 mode occupies 2.222 MHz (Table 18-1) or 2.666 MHz (Table 3-12
> condition), it is **still wider than 1.74 MHz**; and whether the 1300 mode occupies 1.333 MHz or
> has a 1200 kHz channel filter, it is **still narrower than 1.74 MHz**.

---

## 3. The arithmetic — what fits

Definition: a mode fits iff its occupied (DSB) bandwidth **≤ 1.740 MHz**.

```
2600 kbps :  2.666 MHz  vs 1.740 MHz  →  2.666 / 1.740 = 1.532×  →  DOES NOT FIT
2080 kbps :  2.222 MHz  vs 1.740 MHz  →  2.222 / 1.740 = 1.277×  →  DOES NOT FIT
1300 kbps :  1.333 MHz  vs 1.740 MHz  →  1.333 / 1.740 = 0.766×  →  FITS   ← highest that fits
1040 kbps :  1.333 MHz  →  0.766×  →  FITS
 650 kbps :  0.740 MHz  →  0.425×  →  FITS
 520 kbps :  0.571 MHz  →  0.328×  →  FITS
 325 kbps :  0.357 MHz  →  0.205×  →  FITS
 260 kbps :  0.307 MHz  →  0.176×  →  FITS
```

**Headroom when the 1.333 MHz mode is centred on the conventional 433.92 MHz carrier:**

```
lower edge = 433.920 − 1.333/2 = 433.920 − 0.6665 = 433.2535 MHz
upper edge = 433.920 + 0.6665             = 434.5865 MHz
clearance below 433.050 = 433.2535 − 433.050 = 0.2035 MHz
clearance above 434.790 = 434.790 − 434.5865 = 0.2035 MHz
```

The whole 1.333 MHz signal sits **0.2035 MHz clear of each band edge** (~15 % of the band left as
roll-off margin). This is the arithmetic that says **1300 kbps is the maximum FLRC rate that can be
radiated inside 433.05–434.79 MHz.** 2.6 Mbit needs **2.666 MHz**, which is **0.927 MHz wider than the
whole band** — placing it anywhere inside the allocation puts ≥ 0.46 MHz of occupied spectrum outside
433.05 and/or 434.79.

---

## 4. The legal ceiling — it lands on the same answer

Two independent legal rules each stop *above* 1300 kbps:

| Footing | Rule | Occupied-BW ceiling | Highest legal FLRC |
|---|---|---|---|
| **German amateur** (430–440 MHz, in force because the F33 and the licence put the station on the amateur footing) | AFuV **Anlage 1, Lfd. Nr. 18**, Zusatzbestimmung **7**: *"Maximal zulässige belegte Bandbreite einer Amateurfunk-Aussendung: 2 MHz"* | **2.0 MHz** | **1300 kbps** (1.333 MHz). 2600 kbps (2.666) and 2080 kbps (2.222) both fail. |
| **Licence-exempt / SRD** (ERC REC 70-03 Annex 1) | The band is only **1.74 MHz wide** (§1) | **1.74 MHz** (physical) | **1300 kbps** (1.333 MHz) |

Both footings give the **same** ceiling: **FLRC 1300 kbps raw / 0.975 Mbps effective at CR 3/4.**
Sources: `docs/analysis/433-lna-substitution-and-amateur-licence.md` §2.2 (the AFuV 2 MHz cap and the
per-rate legal table); `docs/analysis/radio-legal-power-limits.md` §2 (the 1.74 MHz SRD band).

> **The 2.4 GHz uplink is unaffected.** AFuV Anlage 1 Lfd. Nr. 23 note **9** caps 2400–2450 MHz at
> **10 MHz** occupied bandwidth, so **every** FLRC rate — including 2.6 Mbps — is legal on the
> uplink. `docs/analysis/433-lna-substitution-and-amateur-licence.md` §2.2 (line 333).

---

## 5. The legal duty-cycle consequence

The rate reduction changes **airtime**, and airtime is what a duty-cycle limit counts. Using the
repo's own FLRC airtime estimator (`flrc_airtime_s`: `(payload·8 + 64)/bitrate + 0.1 ms`, from
`docs/frequency-plan-868.md` §4):

```
FLRC 2.6 Mbps, 255 B : (255·8 + 64)/2.6e6 + 0.1 ms = 0.909 ms / packet
FLRC 1.3 Mbps, 255 B : (255·8 + 64)/1.3e6 + 0.1 ms = 1.718 ms / packet   → airtime DOUBLES
```

**Duty-cycle budgets** (ERC REC 70-03 Appendix 4: `DC = Σ T_on / 3600 s`, per sub-band, airtime only):

| Applicable row | Duty cycle | Hourly airtime budget | Packets/h @ 255 B, 1.3 Mbps | @ 255 B, 2.6 Mbps |
|---|---|---:|---:|---:|
| **ERC Annex 1 entry `f` / Vfg 91/2025 row 44b** (10 mW e.r.p.) | **≤ 10 %** | 360 s/h | **209,489** | 395,939 |
| ERC Annex 1 entry `f1` (1 mW e.r.p.) | no duty-cycle requirement | — | (power-limited to 1 mW) | — |
| **ERC Annex 1 entry `f2` / row 45c** — **434.040–434.790 MHz only** | **≤ 100 %** **iff occupied BW ≤ 25 kHz** | 3600 s/h | **not usable** — FLRC needs ≥ 307 kHz | not usable |
| **German amateur footing** (430–440 MHz) | **no duty-cycle limit** | — | bandwidth-limited only (§4) | — |

Sources: `docs/analysis/radio-legal-power-limits.md` lines 126–167 (the three SRD rows and ERC
Annex 1 Note 1); `docs/frequency-plan-868.md` §4 (the DC definition and the airtime estimator).

**Reading.**
1. **The duty-cycle penalty of dropping to 1300 kbps is negligible for a telemetry link.** At the
   *tightest* licence-exempt tier (10 % duty, 10 mW e.r.p.) 1300 kbps still allows **≈ 209,000
   packets/hour at 255 B** — roughly **58 packets per second** of sustained 255-byte traffic. A
   telemetry cadence of one frame per second uses ~1.6 %/s · 1 s = well under 0.05 % duty.
2. **The `f2` escape hatch cannot be used.** The row that removes the duty cycle (434.040–434.790,
   ≤ 100 % duty) requires **occupied BW ≤ 25 kHz**. The narrowest FLRC mode is **307 kHz** (0.26 Mbps)
   — **12× too wide** — so no FLRC mode can claim the no-duty-cycle row. A duty cycle is always the
   route for FLRC on 433 under the SRD footing.
3. **The real cost of the 1.3 Mbps ceiling is throughput, not availability:** the link carries
   **≈ 0.975 Mbps effective** (and the repo's measured sustained ceiling at the *2.6 Mbps* setting is
   **1484.9 kbps** — `docs/frequency-plan-868.md` §4 note), i.e. roughly **half** the downlink rate
   the committed architecture assumed. This must be re-run through the 433 link budget.

---

## 6. What is NOT settled (honest limits)

- **No 433 MHz-specific FLRC sensitivity row exists.** The datasheet's FLRC sensitivity table
  (**Table 3-12**) is characterised at **915 MHz** (sub-GHz) and **2.4 GHz**; there is no 433 MHz row.
  The 915 MHz values (−100.5 dBm @ 2600 kbps, −104.5 dBm @ 1300 kbps) are the honest stand-in.
  `TODO(unverified)`. (Inherited from `docs/adr/073-…` open item and
  `docs/analysis/ground-station-flrc-max-throughput.md` §1.1.)
- **No in-repo sustained-throughput measurement of the 1.3 Mbps mode.** The best measured sustained
  figure on disk (**1484.9 kbps**) is at the *2.6 Mbps* setting
  (`FLRC-512B-THROUGHPUT-AUDIT-2026-10-06.md`). The 1.3 Mbps mode's sustained goodput has **not** been
  measured → `TODO(unverified)`; the arithmetic ceiling is 0.975 Mbps effective at CR 3/4.
- **The exact ERC/REC 70-03 duty-cycle text for *airborne* use** is `TODO(unverified)` in the repo
  (`docs/analysis/PROGRAM-GAP-ANALYSIS-ROUND2.md` §3.1). The duty figures above are the ground-use
  SRD rows.

---

## Appendix — provenance and reproduce

- **Datasheet:** `docs/lr2021-research/semtech-official/LR2021_LR2022_LR2012_Datasheet_v2.2.pdf`,
  Table 18-1 (p. 209, bit-rate/bandwidth), Table 18-2 (effective rates), Table 3-12 (FLRC 1% PER
  sensitivities, p. 50). Extract: `pdftotext -layout <pdf> -`.
- **Band width / duty rows:** `docs/analysis/radio-legal-power-limits.md` lines 126–167;
  `docs/frequency-plan-868.md` §4.
- **German 70 cm bandwidth cap:** `docs/analysis/433-lna-substitution-and-amateur-licence.md` §2.2
  (AFuV Anlage 1 Lfd. Nr. 18 + Zusatzbestimmung 7).
- **The live defect this closes:** `docs/adr/073-433-downlink-flrc-max-lora-rejected.md` (fixes the
  433 downlink on FLRC-max = 2.6 Mbps).
- Reproduce §3: width `434.79 − 433.05 = 1.74`; fit test `BW ≤ 1.74`; centring
  `433.92 ± BW/2` vs the band edges.
