# Link Budget — Licence-Exempt Regime (v9, 300 km slant range)

Companion table to **ADR-041** (`docs/adr/041-rf-frontend-licence-exempt.md`).
Every number is either **SOURCED** (with its source) or **COMPUTED** (tool output
quoted verbatim) or marked **TODO(unverified)**. Nothing here is invented.

The two link directions are computed **separately** because the licence-exempt cap
binds the balloon's *transmitter* (433 MHz downlink), not the ground's transmitter
(2.4 GHz uplink). ADR-037 conflated them under one EIRP figure (37 dBm); this table
splits them and shows which direction actually binds.

---

## 0 — Inputs and their sources

| Input | Value | Source |
|---|---|---|
| Design slant range | 300 km | ADR-037 / `docs/link-budget.md` (established design point) |
| 433.05–434.79 MHz licence-exempt ERP cap | **10 mW ERP** (integral antenna) | `docs/SOLAR-PIN-REGULATORY.md` §3.2 (branch `docs/solar-pin-regulatory`, tip `bc50dacd`), citing Wikipedia LPD433 → ERC Recommendation 70-03 (CEPT), Annex 1. Re-verified 2026-10-07 by fetching the LPD433 article (200 OK, text confirms "10 mW … integral and non-removable antenna"). |
| 2400–2483.5 MHz licence-exempt EIRP cap | **100 mW EIRP** (20 dBm) | Brief 10 (`/home/c03rad0r/reports/balloon-adr/ADR-BRIEF-10-licence-exempt-design-point.md`); general CEPT/EU SRD rule (ERC Rec 70-03 Annex 1, ETSI EN 300 328). **TODO(unverified): exact Annex 1 table row / duty-cycle or LBT/AFA condition for wideband-data in 2.4 GHz** — would be settled by reading the current ERC Rec 70-03 Annex 1 table directly at https://docdb.cept.org (the licence-exempt design-point doc on branch `docs/licence-exempt-design-point` had **not yet landed** as of this commit — its tip `144c8191` is identical to `adr/mcu-s3-no-fem`; this table therefore uses the brief's 100 mW EIRP figure and flags the annex row as unverified). |
| FSPL @ 433 MHz, 300 km | 134.7 dB | COMPUTED — `python3 tools/link_budget.py --freq 433 … --dist 300` (tool output quoted in §2) |
| FSPL @ 2400 MHz, 300 km | 149.6 dB | COMPUTED — `python3 tools/link_budget.py --freq 2400 … --dist 300` (tool output quoted in §1/§3) |
| 2.4 GHz path-loss penalty vs 433 MHz | **14.9 dB** | COMPUTED — 149.6 − 134.7 |
| F33-2G4 2.4 GHz RX sensitivity, LNA in circuit (DIO5 HIGH) | −136 dBm (BW 125 kHz, SF10) | SOURCED — `docs/F33-MODULE-PLAN.md` line 34, from G-NiceRF datasheet Rev 1.1; also ADR-029 D2 / ADR-037 D3 |
| F33-2G4 2.4 GHz RX sensitivity, LNA bypassed (DIO5 LOW) | −124 dBm | SOURCED — ADR-037 D3 / ADR-029 D2 ("DIO5 LOW costs 12 dB", −136 → −124) |
| Bare LoRa2021 2.4 GHz RX sensitivity | −137 dBm (SF12 / 203 kHz) | SOURCED — `docs/inventory.md` ("Sensitivity: … -137dBm (SF12/203kHz 2.4GHz)") |
| Bare LoRa2021 sub-GHz RX sensitivity | −143 dBm (SF12 / 62.5 kHz) | SOURCED — `docs/inventory.md`; `docs/F33-MODULE-PLAN.md` line 33 |
| `tools/link_budget.py` LoRa sensitivity table, SF12/BW125 | −137 dBm | SOURCED — `tools/link_budget.py` `LORA_SENSITIVITY[(12,125)] = -137` |
| SKY66112-11 LNA gain / NF | +14 dB / 1.8 dB | SOURCED — `docs/adr/005-sky66112-fem.md` (ADR-005) |
| Ground-station 433 Yagi gain | 10–15 dBi | Brief 10 / ADR-034 D1 item 2 ("ground station can afford amplification and a large antenna") — **TODO(unverified): a named 433 Yagi part datasheet would pin the exact dBi and pattern** |
| Balloon 2.4 GHz RX antenna gain | 6–10 dBi (PCB Yagi) | `docs/link-budget.md` ("PCB Yagi ~6 dBi"); ADR-037 scenario used 10 dBi — range shown |
| Balloon 433 TX antenna gain | 0 dBi (small monopole/wire) to 2.15 dBi (½-wave dipole) | TODO(unverified): the actual balloon 433 antenna is not specified in a committed datasheet; 0 dBi is the conservative assumption, 2.15 dBi the dipole-equivalent |

> **ERP vs EIRP.** The 433 cap is stated in **ERP** (relative to a half-wave dipole,
> 0 dBd). EIRP = ERP + 2.15 dB. So 10 mW ERP = +10 dBm ERP = +12.15 dBm EIRP. This
> table computes both: a conservative 10 dBm EIRP case (0 dBi balloon antenna) and a
> 12.2 dBm EIRP case (½-wave dipole, +2.15 dBi). The difference is 2.1 dB of margin.

---

## 1 — 2.4 GHz UPLINK (ground → balloon): the ADR-037 case, re-examined

This is the direction ADR-037 computed. Ground transmits, balloon receives.
**Under licence-exempt, the ground transmitter is capped at 100 mW EIRP (20 dBm),
NOT 10 mW** — the 10 mW ERP cap binds only the *balloon's* 433 TX (§2). The "27 dB
drop" framing (EIRP 37 → 10 dBm) is therefore **wrong for this direction**; the
correct drop is 37 → 20 dBm = **17 dB**.

### 1a — ADR-037 baseline (2 W-era, 37 dBm EIRP) — reproduced

Tool command and verbatim output (`python3 tools/link_budget.py --freq 2400 --sf 12
--bw 125 --tx 27 --tx-ant 12 --rx-ant 10 --cable-loss 2 --dist 300 --payload 51`):

```
  EIRP:           37.0 dBm
  FSPL:           149.6 dB
  RX Power:       -102.6 dBm
  Sensitivity:    -137.0 dBm     (tool LoRa table, SF12/BW125)
  Link Margin:    34.4 dB OK
```

Margins against the **module** sensitivities (ADR-037 D3, the citable quantities):

| RX front end (balloon) | Sensitivity | Margin vs −102.6 dBm |
|---|---|---|
| With LNA in circuit (F33 DIO5 HIGH) | −136 dBm | **+33.4 dB** |
| Without LNA (DIO5 bypass, LOW) | −124 dBm | **+21.4 dB** |

**Reproduces ADR-037 D3 exactly.** The tool's −137 dBm gives +34.4 dB; the module's
−136 dBm gives +33.4 dB. The 1 dB difference is the tool's generic LoRa table vs the
module datasheet; ADR-037 used the module figure and so does this table below.

### 1b — Licence-exempt 2.4 GHz uplink: 100 mW EIRP (20 dBm), balloon RX 10 dBi

Tool command and verbatim output (`--tx 20 --tx-ant 0 --rx-ant 10 --cable-loss 0`):

```
  EIRP:           20.0 dBm
  FSPL:           149.6 dB
  RX Power:       -119.6 dBm
  Sensitivity:    -137.0 dBm     (tool)
  Link Margin:    17.4 dB OK
```

Margins against the **module** sensitivities:

| RX front end (balloon) | Sensitivity | Margin vs −119.6 dBm | Verdict |
|---|---|---|---|
| **With LNA in circuit** (F33 DIO5 HIGH / bare LR2021 −137) | −136 / −137 dBm | **+16.4 / +17.4 dB** | CLOSES, comfortable |
| **Without LNA** (F33 DIO5 bypass, LOW) | −124 dBm | **+4.4 dB** | CLOSES, but **thin** (4 dB) |

### 1c — Same, balloon RX antenna = 6 dBi (PCB Yagi, `docs/link-budget.md` figure)

```
  RX Power:       -123.6 dBm
  Link Margin:    13.4 dB OK      (tool, −137)
```

| RX front end | Sensitivity | Margin vs −123.6 dBm |
|---|---|---|
| With LNA (−136/−137) | −136/−137 dBm | **+12.4 / +13.4 dB** |
| Without LNA (−124) | −124 dBm | **+0.4 dB** — **effectively fails** |

**With a 6 dBi balloon antenna the no-LNA case is +0.4 dB — indistinguishable from
failure.** The F33's internal LNA (or an equivalent) is **required** at 6 dBi.

### 1d — The WRONG 10 dBm EIRP framing (for completeness / to reproduce the brief's numbers)

Tool command (`--tx 10 --tx-ant 0 --rx-ant 10`):

```
  EIRP:           10.0 dBm
  RX Power:       -129.6 dBm
  Link Margin:    7.4 dB OK        (tool, −137)
```

| RX front end | Sensitivity | Margin vs −129.6 dBm |
|---|---|---|
| With LNA (−136) | −136 dBm | **+6.4 dB** |
| Without LNA (−124) | −124 dBm | **−5.6 dB — FAILS** |

**This reproduces the brief's +6.4 / −5.6 dB figures exactly** — but the 10 dBm EIRP
assumption is **incorrect for the 2.4 GHz uplink**, because the 2.4 GHz uplink is
transmitted from the ground where the cap is 100 mW EIRP, not 10 mW ERP. The −5.6 dB
"no-LNA fails" conclusion is therefore an artefact of mis-applying the 433 cap to the
2.4 GHz direction. The correct licence-exempt 2.4 GHz uplink margin (§1b) is +4.4 dB
without the LNA — still positive, still thin.

---

## 2 — 433 MHz DOWNLINK (balloon → ground): the direction the 10 mW cap binds

This direction was **not** computed in ADR-037 (which only did the 2.4 GHz RX path).
It is the direction the operator's ≤ 10 mW ERP choice actually constrains. The
balloon transmits at ≤ 10 mW ERP; the ground receives with a 10–15 dBi Yagi and may
add a ground-side LNA (unregulated, no balloon mass).

### 2a — 10 mW ERP, balloon TX 0 dBi (conservative), ground 12 dBi Yagi

```
  EIRP:           10.0 dBm
  FSPL:           134.7 dB
  RX Power:       -112.7 dBm
  Sensitivity:    -137.0 dBm      (tool)
  Link Margin:    24.3 dB OK
```

Against the **bare LR2021 sub-GHz sensitivity (−143 dBm, `docs/inventory.md`)**:
margin = −112.7 − (−143) = **+30.3 dB**.

### 2b — 10 mW ERP as ½-wave dipole (+2.15 dBi), EIRP 12.2 dBm, ground 12 dBi

```
  EIRP:           12.2 dBm
  RX Power:       -110.6 dBm
  Link Margin:    26.4 dB OK       (tool, −137)
```

### 2c — 10 mW ERP, ground 15 dBi Yagi

```
  EIRP:           10.0 dBm
  RX Power:       -109.7 dBm
  Link Margin:    27.3 dB OK       (tool, −137)
```

### 2d — 2 W (33 dBm) baseline, for the delta — ground 12 dBi

```
  EIRP:           33.0 dBm
  RX Power:       -89.7 dBm
  Link Margin:    47.3 dB OK       (tool, −137)
```

**The 433 downlink loses 23 dB going from 2 W to 10 mW ERP (33 → 10 dBm) but still
closes with +24.3 dB margin** (tool sensitivity) / **+30.3 dB** (module −143 dBm).
The 14.9 dB lower path loss at 433 MHz vs 2.4 GHz, plus 12–15 dBi of ground Yagi gain,
more than recovers the 23 dB TX cut. **The 433 downlink is NOT the binding direction.**

---

## 3 — Summary table (both directions, licence-exempt)

| Direction | Band | Cap (licence-exempt) | EIRP used | FSPL@300km | RX pwr | RX front end | Sens. | **Margin** | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| Uplink (ground→balloon) | 2.4 GHz | 100 mW EIRP | 20 dBm | 149.6 | −119.6 | F33 LNA in (DIO5 HI) | −136 | **+16.4 dB** | CLOSES, comfortable |
| Uplink (ground→balloon) | 2.4 GHz | 100 mW EIRP | 20 dBm | 149.6 | −119.6 | F33 LNA bypass (DIO5 LO) | −124 | **+4.4 dB** | CLOSES, **thin** |
| Uplink (ground→balloon) | 2.4 GHz | 100 mW EIRP | 20 dBm | 149.6 | −123.6 | bare LR2021, 6 dBi ant, no LNA | −124 | **+0.4 dB** | **effectively fails** |
| Downlink (balloon→ground) | 433 MHz | 10 mW ERP | 10 dBm | 134.7 | −112.7 | ground 12 dBi Yagi, module −143 | −143 | **+30.3 dB** | CLOSES, comfortable |
| Downlink (balloon→ground) | 433 MHz | 10 mW ERP | 10 dBm | 134.7 | −112.7 | ground 12 dBi Yagi, tool −137 | −137 | **+24.3 dB** | CLOSES, comfortable |
| Downlink (balloon→ground) | 433 MHz | 10 mW ERP | 10 dBm | 134.7 | −109.7 | ground 15 dBi Yagi, tool −137 | −137 | **+27.3 dB** | CLOSES, comfortable |

**Binding direction: the 2.4 GHz uplink**, at +4.4 dB without the F33's internal LNA.
The 433 downlink is never binding under these assumptions — ground-side gain covers it.

---

## 4 — What this means for the front-end decision

1. **The 433 downlink does NOT require a balloon-side FEM or LNA.** 10 mW ERP into a
   0 dBi balloon antenna, received by a 12 dBi ground Yagi, gives +24.3 dB margin
   (tool) / +30.3 dB (module −143 dBm). Put the gain on the ground.
2. **The 2.4 GHz uplink does NOT require the external SKY66112 FEM either** — but it
   **does require the F33 module's internal 2.4 GHz LNA to be in circuit (DIO5 HIGH)**.
   Without it the margin is +4.4 dB (10 dBi balloon ant) or +0.4 dB (6 dBi) — too thin
   for a 300 km link with real-world fades. With the internal LNA the margin is
   +16.4 dB — comfortable.
3. **The external SKY66112 LNA (+14 dB / 1.8 dB NF, ADR-005) is not needed on top of
   the F33's internal LNA.** An external LNA in front of an already-low-NF module
   front end cannot improve a system already at its own floor (the same reasoning
   ADR-037 D3 used at 2 W). The internal LNA is the citable −136 dBm figure; the
   external LNA's incremental benefit is **TODO(unverified)** — a cascade NF
   measurement would settle it, but is not needed to close the link.
4. **The "27 dB drop → −5.6 dB no-LNA fails" framing is wrong for the 2.4 GHz uplink.**
   The 2.4 GHz uplink is ground-transmitted and capped at 100 mW EIRP (20 dBm), not
   10 mW. The correct drop is 17 dB, and the no-LNA margin is +4.4 dB (positive but
   thin), not −5.6 dB.

---

## 5 — TODO / UNVERIFIED items (fail-closed)

- **TODO(unverified): exact ERC Rec 70-03 Annex 1 row** for 2400–2483.5 MHz wideband
  data — the 100 mW EIRP figure is the widely-cited CEPT/EU SRD value and is stated in
  Brief 10, but the precise annex item number and any LBT/AFA or duty-cycle condition
  were not fetched directly. Would be settled by reading the current Annex 1 table at
  https://docdb.cept.org. The licence-exempt design-point doc (branch
  `docs/licence-exempt-design-point`) had not landed as of this commit.
- **TODO(unverified): exact SRD duty-cycle ceiling** in ERC Rec 70-03 Annex 1 for
  433.05–434.79 MHz (some non-specific SRD categories are < 1 %). Carried from
  `docs/SOLAR-PIN-REGULATORY.md` §3.2 UNVERIFIED item 2. Affects average throughput,
  not the per-burst margin computed here.
- **TODO(unverified): named 433 Yagi part** — the 12 dBi / 15 dBi ground antenna gains
  are design assumptions (Brief 10, ADR-034), not a cited part datasheet. A named Yagi
  datasheet would pin exact dBi, pattern and front-to-back ratio.
- **TODO(unverified): balloon 433 TX antenna gain** — 0 dBi (conservative) and 2.15 dBi
  (½-wave dipole) are assumed; the actual flight antenna is not specified in a
  committed datasheet.
- **TODO(unverified): cascade NF of F33 internal LNA + SKY66112** — not needed to close
  the link (sensitivity is the citable quantity), but would settle whether the external
  LNA gives any incremental benefit. ADR-037 D3 made the same honesty note.
- **UNVERIFIED: the licence-exempt design-point doc** (branch
  `docs/licence-exempt-design-point`) was not yet landed (tip `144c8191` == tip of
  `adr/mcu-s3-no-fem`, no new content). This table used Brief 10 as its source for the
  2.4 GHz 100 mW EIRP cap. When that doc lands, its sourced annex rows should replace
  the TODO above.