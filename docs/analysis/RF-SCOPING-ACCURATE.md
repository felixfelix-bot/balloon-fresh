# RF scoping — accurate (correcting the LoRa-sensitivity inflation)

- Status: **analysis / scoping** — decision-input, not a decision record.
- Date: 2026-10-10
- Author: analysis worker (`analysis/rf-accurate`), subagent.
- Supersedes for the *quantitative* link figures: the uplink rows in
  `docs/LINK-BUDGET-LICENCE-EXEMPT.md` and the uplink-surplus verdict (Q5) in
  `docs/analysis/ground-station-amplifier-hypothesis-check.md`.
- Question answered: **can more ground antenna gain + a ground power amplifier
  close the uplink?** → §6. Short answer: the amplifier alone cannot and the
  antenna alone cannot; **the pair closes it, but only on the amateur footing** —
  and the licence-exempt EIRP ceiling binds **34.77 dB before the amplifier does**.

**Labelling convention (repo rule):** `SOURCED` = a datasheet/regulatory value
quoted from an in-repo file; `COMPUTED` = arithmetic from SOURCED inputs, shown
step by step here; `ESTIMATE` = a modelling assumption, stated as such;
`TODO(unverified)` = not sourced in-repo.

---

## 0. Provenance inventory (what the task asked to cite)

| Asked-for path | Present on `main` (`4ba3e67`)? | Use |
|---|---|---|
| `docs/LINK-BUDGET-LICENCE-EXEMPT.md` | **PRESENT** | 433 licence-exempt ERP cap; **carries the inflated −137 dBm LoRa figure** (§1.2) |
| `docs/REGULATORY-AMATEUR-LICENCE.md` | **PRESENT** | amateur power ceilings, 70 cm (entry 18) and 2400–2450 MHz (entry 23) |
| `docs/frequency-plan-868.md` | **PRESENT**, but it is the **868 MHz** plan — **not** a 433/2400 MHz source | not used for ceilings |
| `docs/analysis/radio-legal-power-limits.md` | **PRESENT** | 2.4 GHz licence-exempt density condition → **10 mW EIRP (57a)**; 433 duty-cycle footings |
| `docs/analysis/433-2g4-flrc-link-budget-and-regulatory-audit.md` | **MISSING on `main`** (exists only as an untracked file in the dirty primary worktree) | cited once, flagged |
| Datasheets | `docs/LR2021_LR2022_LR2012_Datasheet_Rev2.1.pdf`, `docs/f33-module/LoRa2021F33-2G4-datasheet-v1.1.pdf` | **PRESENT** — all RF specs below |

Other in-repo sources used and present on `main`:
`docs/link-budget.md`, `docs/coordination/CONSULTANT-PLAN-REVIEW-V2.md` (CONCERN-4),
`docs/coordination/ARCHITECTURE-FREERTOS-TASKS.md`,
`docs/adr/036-energy-policy-burst-storage-daylight-only-tx.md`,
`docs/analysis/pico-balloon-solar-survey.md`,
`docs/analysis/two-variant-mass-budget.md`,
`docs/analysis/ground-station-bom-candidates.md`,
`docs/analysis/ground-station-amplifier-hypothesis-check.md`.

---

## 1. Constants, geometry, and the two defects

### 1.1 Geometry and free-space path loss (reproduced)

Altitude **h = 12 km**, ground range **d = 300 km** (`docs/…` mission assumption).

```
slant R = √(300² + 12²) = √(90000 + 144) = √90144 = 300.240 km
```

```
FSPL(f, R) = 32.44 + 20·log10(f_MHz) + 20·log10(R_km)     [dB]

FSPL(433.92 MHz, 300.240 km) = 32.44 + 20·log10(433.92) + 20·log10(300.240)
                             = 32.44 + 52.7492 + 49.5488
                             = 134.738 dB   → 134.74 dB   ✓ (matches the agreed value)

FSPL(2450 MHz,   300.240 km) = 32.44 + 20·log10(2450)   + 49.5488
                             = 32.44 + 67.7832 + 49.5488
                             = 149.773 dB   → 149.77 dB   ✓ (matches the agreed value)
```

Band penalty between the two legs:
`149.773 − 134.738 = 15.035 dB → 15.04 dB` (this is the 2.4 GHz propagation tax).

Radio horizon at 12 km alt (repo-taken Earth-radius model) = **451 km**
(`SOURCED`, agreed). A 300.24 km slant leg therefore has geometric slack; the
link is **budget-limited, not horizon-limited**.

### 1.2 DEFECT (a) — the LoRa-sensitivity inflation

The uplink is a **high-rate** link. The correct receiver for it is the **FLRC**
mode of the same LR2021 chip, **not** LoRa SF12. The repo's uplink figures were
computed against **LoRa** sensitivity.

**Correct uplink sensitivities (FLRC, 1 % PER, 2.4 GHz)** — `SOURCED`,
`docs/LR2021_LR2022_LR2012_Datasheet_Rev2.1.pdf` Table 3-13 (2.4 GHz rows),
verified by text extraction of the in-repo PDF:

| FLRC mode | BRF | BWF (occupied) | CR | effective bit rate | S (1 % PER, 2.4 GHz) |
|---|---|---|---|---|---|
| `FLRC_2600_CR05_2G4_S` | 2600 kbps | **2666 kHz** | 3/4 | 1.95 Mbps | **−99.0 dBm** |
| `FLRC_2080_CR05_2G4_S` | 2080 kbps | 2666 kHz | 3/4 | 1.56 Mbps | −100.0 dBm |
| `FLRC_1300_CR05_2G4_S` | 1300 kbps | **1200 kHz** | 3/4 | 975 kbps | **−101.5 dBm** |
| `FLRC_650_CR05_2G4_S` | 650 kbps | ~600 kHz | 3/4 | 487 kbps | **−104.0 dBm** |

> The task's "~−99.5 dBm" is the datasheet's **−99.0 dBm** at 2.6 Mbit; the
> 0.5 dB is rounding. **All uplink arithmetic below uses −99.0 dBm.**

**What the repo actually used (the inflation):**

| Repo figure used for the *uplink* receiver | Where | Correct FLRC value | **Inflation** |
|---|---|---|---|
| −137.0 dBm (LoRa SF12 / 125 kHz) | `docs/LINK-BUDGET-LICENCE-EXEMPT.md` L26/28/58/81/144 (`tools/link_budget.py` `LORA_SENSITIVITY[(12,125)]`); used in the "+23.1 dB surplus" of `ground-station-amplifier-hypothesis-check.md` Q5 | −99.0 | **+38.0 dB** |
| −137.0 dBm (SF12 / 203 kHz 2.4 GHz) | `docs/inventory.md` L31, quoted in `ground-station-lowpower-link-and-shared-dish.md` L230 | −99.0 | **+38.0 dB** |
| −136.0 dBm (F33 spec, SF10/125 kHz 2.4 GHz, bypass OFF) | `docs/f33-module/…datasheet…` L137, quoted in `ground-station-lowpower-link-and-shared-dish.md` L126 | −99.0 | **+37.0 dB** |
| −124.0 dBm (SF10/125 kHz 2.4 GHz, F33 **LNA on**) | `docs/LINK-BUDGET-LICENCE-EXEMPT.md` L188 (the "best-case" uplink row: **+0.4 dB**, "effectively fails") | −99.0 | **+25.0 dB** |

**Consequence, stated exactly.** Every uplink margin in the repo is overstated by
the *difference* between the LoRa row it used and −99.0 dBm. The delta is exact
regardless of the baseline arithmetic:

```
corrected_margin = repo_margin − inflation
```

- The `ground-station-amplifier-hypothesis-check.md` Q5 claim *"the 2.4 GHz uplink
  already closes with **+23.1 dB** of surplus"*: `+23.1 − 38.0 = −14.9 dB` → **fails**.
- The same doc's *"up to +36.1 dB with a +33 dBm PA"*: `+36.1 − 38.0 = −1.9 dB` → **fails**.
- The `LINK-BUDGET-LICENCE-EXEMPT.md` L188 row *"+0.4 dB"*: `+0.4 − 25.0 = −24.6 dB` → **fails**.

That is the whole defect: the mission's high-rate uplink was planned against a
**38 dB-better** receiver than the one it will use.

### 1.3 DEFECT (b) — 2 MHz FLRC cannot fit the 433 band

The licence-exempt 433 band is **433.05–434.79 MHz = 1.74 MHz wide**
(`SOURCED`, ERC Rec 70-03 Annex 1 / LPD433, via `docs/LINK-BUDGET-LICENCE-EXEMPT.md` L19).
The FLRC modes' **occupied** bandwidth is the *BWF* column, **not** the bit-rate
label (`SOURCED`, Table 18-1):

| FLRC mode | occupied BWF | fits 1.74 MHz band? |
|---|---|---|
| 2600 kbps | 2666 kHz = 2.67 MHz | **NO** (−0.93 MHz over) |
| 2080 kbps | 2666 kHz = 2.67 MHz | **NO** |
| 1300 kbps | **1333 kHz = 1.33 MHz** | **YES** (0.41 MHz slack) |
| 1040 kbps | 1333 kHz = 1.33 MHz | YES |
| 650 kbps | **740 kHz = 0.74 MHz** | **YES** (1.00 MHz slack) |

So a "2 MHz FLRC" downlink is **not implementable on the 433 balloon TX**; the
ceiling is **1.3 Mbit (1.333 MHz DSB)**. The operator's accepted trade —
"*slightly lower throughput* to keep the balloon transmitting on 433 MHz" — is
therefore **mandatory, not optional**, and its cost is small: 2.6 → 1.3 Mbit.

> Cross-check with the amateur 70 cm band plan (`docs/REGULATORY-AMATEUR-LICENCE.md`
> §2/§3): the IARU segments quoted there are "ALL MODES, no bandwidth limit", so
> under the **amateur** footing 1.333 MHz is unambiguously legal; the 1.74 MHz
> constraint is specific to the **licence-exempt** 433.05–434.79 SRD window.

---

## 2. DOWNLINK budget — balloon → ground, **433.92 MHz**, FLRC

Half-duplex **balloon TX** leg (`ADR-034`: 433 TX / 2.4 GHz RX split;
`docs/coordination/CONSULTANT-PLAN-REVIEW-V2.md` CONCERN-4;
`docs/coordination/ARCHITECTURE-FREERTOS-TASKS.md`).

### 2.1 Modes that fit the band — occupied BW + real sensitivity

**Sub-GHz FLRC sensitivity** — `SOURCED`, Table 3-12. The datasheet's FLRC rows
are tabulated at **915 MHz**; there is **no 433-specific FLRC row**
(`TODO(unverified)`: treat as band-flat to within a few dB — see §8):

| Mode | BRF | occupied BWF | eff. bit rate | S (1 % PER) |
|---|---|---|---|---|
| `FLRC_1300_CR05_915_S` | 1300 kbps | **1333 kHz** | 975 kbps | **−104.5 dBm** |
| `FLRC_1040_CR05_915_S` | 1040 kbps | 1333 kHz | 780 kbps | −105.0 dBm |
| `FLRC_650_CR05_915_S` | 650 kbps | **740 kHz** | 487 kbps | **−107.0 dBm** |
| `FLRC_520_CR05_915_S` | 520 kbps | 571 kHz | 390 kbps | −108.5 dBm |
| `FLRC_325_CR05_915_S` | 325 kbps | 357 kHz | 243 kbps | −110.0 dBm |

### 2.2 Maximum achievable bitrate in the 1.74 MHz band

**FLRC 1300 kbit/s (1.333 MHz occupied, 975 kbps effective) is the maximum**
— the highest FLRC mode whose occupied bandwidth fits 1.74 MHz. 2.6 and 2.08 Mbit
do not fit (§1.3).

### 2.3 Margin at 300 km — stated EIRP × stated ground gain

Balloon EIRP options (`SOURCED`):
- **F33 module, 433 MHz, 2 W PA**: `P_tx = +33.0 dBm` typical (spec range
  31.5/33/34 dBm — `docs/f33-module/LoRa2021F33-2G4-datasheet-v1.1.pdf` L128);
  balloon antenna gain **0 dBi** (conservative, `docs/LINK-BUDGET-LICENCE-EXEMPT.md`)
  → **EIRP = +33.0 dBm**.
- **Licence-exempt 10 mW ERP**: `+12.15 dBm EIRP` (10 mW ERP + 2.15 dB; §5).
- Bare LR2021 chip (no F33), +22 dBm, as a fallback `ESTIMATE` shape.

Ground gain options: **G_ground = 12 dBi** or **20 dBi** (task-specified; both are
in-family for 433 — e.g. Diamond A-430S15R 14.8 dBi €74.50, FlexaYagi FX 7073
18.0 dBi €215, `docs/analysis/ground-station-bom-candidates.md`).

```
P_rx = EIRP − FSPL(433.92) + G_ground
margin = P_rx − S_mode
```

| Balloon EIRP | G_ground | `EIRP − 134.74 + G` | P_rx (dBm) | margin @1300 k (−104.5) | margin @650 k (−107.0) |
|---|---|---|---|---|---|
| **+33.0 dBm** (F33 2 W) | 12 dBi | 33.00 − 134.74 + 12 | **−89.74** | **+14.76 dB** | +17.26 dB |
| **+33.0 dBm** (F33 2 W) | 20 dBi | 33.00 − 134.74 + 20 | **−81.74** | **+22.76 dB** | +25.26 dB |
| +12.15 dBm (lx 10 mW ERP) | 12 dBi | 12.15 − 134.74 + 12 | −110.59 | **−6.09 dB** ✗ | −3.59 dB ✗ |
| +12.15 dBm (lx 10 mW ERP) | 20 dBi | 12.15 − 134.74 + 20 | −102.59 | +1.91 dB | +4.41 dB |
| +22.0 dBm (bare chip) | 12 dBi | 22.00 − 134.74 + 12 | −100.74 | +3.76 dB | +6.26 dB |

**Worked example (first row):**
`33.00 − 134.738 + 12 = −89.738 ≈ −89.74 dBm`;  `−89.74 − (−104.5) = +14.76 dB`.

**Required ground gain** (solve `G = S + FSPL − EIRP`):

```
1300 kbit:  G_req = −104.5 + 134.738 − EIRP  →  F33: −2.76 dBi ; lx 10 mW: +18.09 dBi
 650 kbit:  G_req = −107.0 + 134.738 − EIRP  →  F33: −5.26 dBi ; lx 10 mW: +15.59 dBi
```

**Downlink verdict:** with the F33 at 2 W, the 433 downlink closes at **1300 kbit
with +14.8 dB (12 dBi Yagi)** to **+22.8 dB (20 dBi Yagi)** margin. On the bare
licence-exempt 10 mW it needs **+18.1 dBi** even at 1300 kbit — i.e. the
licence-exempt downlink is marginal and antenna-bound, not power-bound.

---

## 3. UPLINK budget — ground → balloon, **2450 MHz**, FLRC

Half-duplex **balloon RX** leg. This is the direction the operator asked about.

Mode used for the headline case: **FLRC 2600 kbit → S = −99.0 dBm**
(`SOURCED`, §1.2). Ground TX chain: `P_tx` → feed loss `L_feed = 0.5 dB`
(`ESTIMATE`, typical short mast run) → antenna `G_ground` → balloon RX antenna
`G_balloon`.

```
required ground EIRP = S + FSPL(2450) − G_balloon
required P_tx        = required EIRP − G_ground + L_feed
```

### 3.1 Headline case — FLRC 2600 kbit, S = −99.0 dBm

Balloon RX antenna **G_balloon = 6 dBi** (`SOURCED`, PCB Yagi,
`docs/link-budget.md` "Antenne Ballon: PCB-Yagi ~6 dBi"):

```
required EIRP = −99.0 + 149.773 − 6.0 = +44.77 dBm
```

| Ground antenna (task-specified) | `P_tx = 44.77 − G + 0.5` | **P_tx (W)** | ground EIRP | closes on power? |
|---|---|---|---|---|
| 6 dBi omni | +39.27 dBm | **8.46 W** | +44.77 dBm | yes (8.5 W) |
| 12 dBi Yagi | +33.27 dBm | **2.13 W** | +44.77 dBm | yes (2.1 W) |
| 20 dBi Yagi | +25.27 dBm | **0.337 W** | +44.77 dBm | yes (340 mW) |
| 24 dBi dish | +21.27 dBm | **0.134 W** | +44.77 dBm | yes (134 mW) |

**Worked example (12 dBi Yagi):** `44.77 − 12 + 0.5 = +33.27 dBm`;
`10^(33.27/10)/1000 = 2125 mW = 2.13 W`.

If the balloon RX antenna is the **10 dBi** variant (`ADR-037` /
`docs/LINK-BUDGET-LICENCE-EXEMPT.md` §1b), required EIRP drops to
`−99.0 + 149.773 − 10 = +40.77 dBm`, i.e. **−4.0 dB of required power**:
6 dBi omni → 3.37 W; 12 dBi → 0.846 W; 20 dBi → 0.134 W; 24 dBi → 0.053 W.

### 3.2 Lower-rate uplink (the operator's accepted trade works here too)

| Uplink mode | S | required EIRP (G_balloon 6 dBi) | 12 dBi Yagi P_tx | 20 dBi Yagi P_tx |
|---|---|---|---|---|
| FLRC 2600 k (1.95 Mbps) | −99.0 | +44.77 dBm | 2.13 W | 0.337 W |
| FLRC 1300 k (975 kbps) | −101.5 | +42.27 dBm | 1.20 W | 0.189 W |
| FLRC 650 k (487 kbps) | −104.0 | +39.77 dBm | 0.672 W | 0.106 W |

Dropping the uplink to **650 kbit buys +5.0 dB** (it halves the needed power);
dropping to 1300 kbit buys +2.5 dB.

### 3.3 Which CLOSE — regulatory overlay

Ceilings (§5): licence-exempt 2.4 GHz = **+10 dBm EIRP**; amateur **Kl E = +36.99 dBm**,
**Kl A = +48.75 dBm** conducted.

Target `required EIRP = +44.77 dBm`, G_balloon 6 dBi:

| G_ground | P_tx | ℓ-exempt (+10 dBm EIRP) | **Kl E ≤ +36.99 dBm** | **Kl A ≤ +48.75 dBm** |
|---|---|---|---|---|
| 6 dBi omni | +39.27 dBm | **FAIL by 34.77 dB** | **FAIL by 2.28 dB** | PASS |
| 12 dBi Yagi | +33.27 dBm | FAIL by 34.77 dB | **PASS (+3.72 dB)** | PASS |
| 20 dBi Yagi | +25.27 dBm | FAIL by 34.77 dB | **PASS (+11.72 dB)** | PASS |
| 24 dBi dish | +21.27 dBm | FAIL by 34.77 dB | **PASS (+15.72 dB)** | PASS |

**Reading:** on power alone **all four close** (even a 6 dBi omni needs only
8.46 W). On the **licence-exempt** footing **none close** — the ceiling is 10 mW
EIRP, the need is +44.77 dBm EIRP, a **34.77 dB** shortfall. On the **amateur**
footing three of four close under **Kl E**; the 6 dBi omni misses Kl E by 2.28 dB
(but passes Kl A).

### 3.4 Does the EIRP limit bind before the amplifier? — YES, with the numbers

Under licence-exempt 2.4 GHz, the binding constraint is **EIRP, not the PA**:

```
licence-exempt cap            = +10.0 dBm EIRP
required EIRP (2600 k, 6 dBi) = +44.77 dBm EIRP
shortfall                     = 44.77 − 10.0 = 34.77 dB
```

**A ground PA is illegal past +10 dBm EIRP**, i.e. **34.77 dB before the amplifier's
own capability is ever the limit.** Even a 24 dBi dish plus a 134 mW amplifier
produces +44.77 dBm EIRP — **34.77 dB above the licence-exempt ceiling**. The
amplifier cannot be the last dB; the *licence footing* is.

Under the amateur footing the cap is power-based and does bind on one row:
the **6 dBi omni + Kl E** case needs +39.27 dBm against a +36.99 dBm ceiling →
**FAIL by 2.28 dB**; the fix there is antenna gain (→ 12 dBi), not more power
(Kl A would allow 8.46 W but the operator's Kl E ceiling is the relevant one if
that is the held class).

---

## 4. Mass / energy consequence at the balloon, per option

The decisive asymmetry: **the uplink is ground→balloon.** Improving the uplink
with *ground* antenna gain or a *ground* PA costs the balloon **nothing** — the
balloon only **receives** on that leg. Improving the uplink on the *balloon* side
(bigger 2.4 GHz antenna, balloon LNA) costs mass and/or power.

### 4.1 The balloon cost of *power at the balloon* (why it is expensive)

In-repo solar constants (`docs/analysis/pico-balloon-solar-survey.md`, derived):

```
areal power   = 0.01955 W/cm²  (bare Si, 1 sun: 200 mW / 10.23 cm²)
areal mass    = 0.04893 g/cm²  (0.21 mm bare Si)
→ area per watt = 1 / 0.01955 = 51.15 cm²/W
→ mass per watt = 51.15 × 0.04893 = 2.503 g/W
```

Each **watt of continuous balloon load** costs **51.2 cm² of cell** and
**2.50 g of bare-Si mass** — before carrier/encapsulation. There is **no battery**
in this design (`docs/adr/036-…` / ADR-006: no battery works at −60 °C); storage
is a **1.65 F @ 5.4 V** supercap bank, **3.0 g**, sized by ADR-036 to hold **one
TX burst**, with **TX daylight-only** (`docs/adr/036-energy-policy-burst-storage-daylight-only-tx.md`).

**F33 downlink TX, 433 MHz, 2 W** (`SOURCED`, F33 datasheet L111: `< 1200 mA @ 5 V`):

```
P_dc = 5.0 V × 1.200 A = 6.0 W   (RF = 2 W → PA efficiency ≈ 2/6 = 33 %, heat = 4.0 W)
solar area to source it = 6.0 / 0.01955 = 306.9 cm²
bare-Si cell mass       = 306.9 × 0.04893 = 15.02 g
```

- The current array peaks at **~2.4 W** (`ADR-006`), so the 2 W TX draws **2.5×
  the array's peak** — that is exactly why ADR-036 exists (burst-sized storage,
  daylight-only TX). Airborne the constraint is a **supercap current-burst**, not
  average energy: a 255 B packet at 1.3 Mbit has **airtime = (255·8+64)/1.3e6 +
  0.1 ms = 1.72 ms**, i.e. **10.3 mJ** at 6 W DC — ≈2 300 such bursts fit in the
  24 J bank.
- **Trying to buy downlink margin with more balloon power is unaffordable:**
  +3 dB of RF (4 W) at the same 33 % efficiency = 12.0 W DC = **613.8 cm²** of
  cell = **30.0 g** of bare Si — **larger than the entire `B1` mass target**
  (`docs/analysis/two-variant-mass-budget.md` B1 ≈12.9 g, <20 g goal).

**F33 uplink RX, 2.4 GHz** (`SOURCED`, F33 datasheet L137/L139): RX current
`< 42 mA` with the 2.4 GHz LNA engaged (`DIO5` HIGH, bypass OFF), `< 9 mA` bypass
ON. At 5 V that is **≤ 0.21 W** — trivial beside the TX burst.

### 4.2 Per-option mass/energy table

| Option | Balloon mass Δ | Balloon energy Δ | Comment |
|---|---|---|---|
| **Ground 2.4 GHz antenna gain** (12→20→24 dBi) | **0 g** | **0 W** | balloon is RX-only on this leg |
| **Ground 2.4 GHz PA** (0.13–8.5 W) | **0 g** | **0 W** | all mass/power is at the ground |
| Balloon 2.4 GHz RX antenna 6→10 dBi | small (+ wire/PCB) | 0 W | `docs/analysis/two-variant-mass-budget.md` A10 antenna wire 0.2 g today |
| Balloon-side LNA / RX boost | ~0 g (in-radio: F33 LNA is built in, +6 dB / bypass OFF) | +0.11–0.21 W (42 vs 9 mA) | helps **both** legs' RX; already in the F33 |
| **+3 dB of balloon 433 TX** (2→4 W) | **≈ +15 g** cell (30 g total cell) | +6.0 W DC | **does not fit the mass budget** |
| **Bigger balloon TX PA** beyond F33 | forfeits the F33 integration | — | not needed; downlink already +15…+23 dB |

**Conclusion for §4:** the *cheapest place to add uplink margin is the ground* —
it is the only place that adds margin at **zero balloon mass and zero balloon
power**. The balloon-side alternatives are either already free (the built-in F33
LNA) or unaffordable (+15…30 g of solar cell for +3 dB of TX).

---

## 5. Regulatory ceilings — the legally relevant limits

### 5.1 433 MHz (balloon TX / ground RX)

| Footing | Ceiling | Duty / BW condition | In-repo source |
|---|---|---|---|
| **Licence-exempt** | **10 mW ERP** (= +10 dBm ERP = **+12.15 dBm EIRP**) | available on three footings: (i) ≤ **10 %** duty cycle, or (ii) ≤ **25 kHz** BW inside 434.04–434.79 MHz (≤100 % duty), or (iii) the German national deviation, printed without a parameter. **Unconditional ceiling in the whole band = 1 mW ERP.** | `docs/LINK-BUDGET-LICENCE-EXEMPT.md` L19 (LPD433 / ERC Rec 70-03 Annex 1); `docs/analysis/radio-legal-power-limits.md` row "433 MHz, balloon→ground" + L128/136/153 |
| **Amateur (70 cm, 430–440 MHz)** | Kl **A 750 W PEP**, Kl **E 75 W PEP**, Kl **N 6.1 W ERP** | secondary allocation; automatic/remote terrestrial stations >30 MHz limited to **50 W ERP** | `docs/REGULATORY-AMATEUR-LICENCE.md` §1 (AFuV Anlage 1 entry 18: „18 430–440 MHz P 750 W PEP 75 W PEP 6,1 W ERP …") |

`ERP → EIRP: +2.15 dB` (`docs/LINK-BUDGET-LICENCE-EXEMPT.md` L34).

### 5.2 2.4 GHz (ground TX / balloon RX) — the uplink

| Footing | Ceiling | Condition | In-repo source |
|---|---|---|---|
| **Licence-exempt** | **10 mW EIRP** (= +10 dBm EIRP) | The 100 mW EIRP tier (row **57c / D57c "WLAN"**) carries a **power-density** condition: *10 mW/MHz EIRP for every modulation other than frequency hopping*. FLRC (and LoRa) with ≤1 MHz occupied BW therefore **cannot** radiate 100 mW; the applicable row is **57a / CEPT Annex 1 h = 10 mW EIRP**. | `docs/analysis/radio-legal-power-limits.md` row "2.4 GHz, ground→balloon" |
| **Amateur (2400–2450 MHz)** | Kl **A 75 W PEP** = +48.75 dBm; Kl **E 5 W PEP** = +36.99 dBm | secondary; AFuV Anlage 1 entry 23 („23 2 400–2 450 MHz S 75 W PEP 5 W PEP …") | `docs/REGULATORY-AMATEUR-LICENCE.md` §8 |

**The ceiling that decides the uplink answer:** licence-exempt 2.4 GHz is
**+10 dBm EIRP**, and the required uplink EIRP is **+44.77 dBm** → the
licence-exempt route is short by **34.77 dB** at every antenna gain. The
uplink can only close under the **amateur** licence, whose relevant ceilings are
**+36.99 dBm (Kl E)** and **+48.75 dBm (Kl A)** conducted.

> The 433 licence-exempt 10 mW ERP ceiling is likewise **below** the balloon's
> F33 capability (+33 dBm) — the F33 downlink is only legal on the **amateur**
> footing; on licence-exempt the balloon must fall back to +12.15 dBm EIRP
> (§2.3), where the downlink needs **+18.1 dBi** of ground gain at 1300 kbit.

---

## 6. Verdict

**Can more ground antenna gain + a ground power amplifier close the uplink?**

- **Ground antenna gain alone: NO** (on licence-exempt). The binding constraint is
  EIRP, and the licence-exempt 2.4 GHz ceiling is +10 dBm EIRP — antenna gain
  raises EIRP, so gain *is* the right lever, but no purchasable antenna closes a
  **34.77 dB** EIRP gap. Antenna-only cannot overcome the ceiling.
- **Ground amplifier alone: NO.** A PA also raises EIRP and so is capped at the
  same +10 dBm EIRP on licence-exempt — the amplifier is **34.77 dB past the legal
  ceiling** before it is past its own limits.
- **Antenna + PA together: YES — but only after the licence footing changes.**
  On the amateur footing the pair closes comfortably:
  - **12 dBi Yagi + 2.13 W** → Kl E (+3.72 dB headroom), Kl A (comfortable).
  - **20 dBi Yagi + 0.337 W** → Kl E (+11.72 dB headroom).
  - **24 dBi dish + 0.134 W** → Kl E (+15.72 dB headroom).
  - A 6 dBi omni needs 8.46 W = **Kl A only** (misses Kl E by 2.28 dB).

**What realistically closes:**
- **Downlink (433, balloon→ground):** closes on the amateur/F33 footing at
  **FLRC 1300 kbit** (max that fits 1.74 MHz) with **+14.8 dB (12 dBi Yagi)** to
  **+22.8 dB (20 dBi Yagi)**. Licence-exempt downlink is marginal: needs **+18.1 dBi**.
- **Uplink (2.4 GHz, ground→balloon):** closes on the **amateur** footing with a
  modest Yagi + a few watts, at **zero balloon cost**.

**What does NOT close:**
- Any **licence-exempt** uplink (34.77 dB EIRP short, at any gain/PA).
- Any plan built on the repo's **LoRa −137 dBm** uplink sensitivity — the true
  FLRC receiver is **−99.0 dBm**, and correcting this **removes 38 dB** from every
  uplink margin (`+23.1 dB surplus → −14.9 dB`).

**The single cheapest change that buys the most margin — ranked by dB per € (in-repo prices):**

1. **Move the 2.4 GHz uplink from the licence-exempt +10 dBm EIRP ceiling to the
   operator's amateur footing (Kl A).** Cost **€0** (the operator already holds
   the licence — `docs/REGULATORY-AMATEUR-LICENCE.md` §1/§8), buys **+38.75 dB**
   of conducted-power headroom (10 mW EIRP → 75 W PEP). **This is the single
   cheapest change that buys the most margin** — it is the change that turns the
   34.77 dB licence-exempt shortfall into a surplus with no hardware at all.
   *(Rank-2 hardware change, if antenna-limited instead: ground 2.4 GHz antenna
   gain — a 12→20 dBi Yagi step is ~+8 dB for a Yagi's price, `docs/analysis/ground-station-bom-candidates.md`;
   a **ground PA is explicitly the last resort**: `docs/analysis/ground-station-amplifier-hypothesis-check.md`
   L109 lists the DXpatrol 2.4 GHz PAs at €69 (1 W) / €185 (12 W) but rates their
   €/dB "INF" *because the uplink was (wrongly) in surplus* — **with the corrected
   −99.0 dBm sensitivity that rating flips**, and a modest grounded PA now buys
   real margin, again at zero balloon cost.)*

---

## 7. Step-by-step arithmetic summary (for audit)

```
FSPL433  = 32.44 + 20log10(433.92) + 20log10(300.240) = 134.738 dB
FSPL2450 = 32.44 + 20log10(2450.0) + 20log10(300.240) = 149.773 dB

DOWNLINK  P_rx = EIRP − 134.738 + G_ground
  F33 +33.0 dBm, G=12 : 33.00 − 134.738 + 12 = −89.738 dBm ; margin@1300k = −89.738 + 104.5 = +14.76 dB
  F33 +33.0 dBm, G=20 : 33.00 − 134.738 + 20 = −81.738 dBm ; margin@1300k =                +22.76 dB
  lx  +12.15 dBm, G=12: 12.15 − 134.738 + 12 = −110.588 dBm ; margin@1300k = −6.09 dB  (needs G≥+18.09 dBi)
  lx  +12.15 dBm, G=20: 12.15 − 134.738 + 20 = −102.588 dBm ; margin@1300k = +1.91 dB

UPLINK    required EIRP = S + 149.773 − G_balloon ;  P_tx = EIRP − G_ground + 0.5
  S=−99.0, G_balloon=6 : req EIRP = −99.0 + 149.773 − 6 = +44.773 dBm
     G=6  dBi : P_tx = 44.773 − 6  + 0.5 = +39.273 dBm = 10^(3.9273) mW = 8459 mW = 8.46 W
     G=12 dBi : P_tx = 44.773 − 12 + 0.5 = +33.273 dBm = 2125 mW = 2.13 W
     G=20 dBi : P_tx = 44.773 − 20 + 0.5 = +25.273 dBm =  337 mW = 0.337 W
     G=24 dBi : P_tx = 44.773 − 24 + 0.5 = +21.273 dBm =  134 mW = 0.134 W
  licence-exempt shortfall = 44.773 − 10.0 = 34.77 dB  (EIRP binds before the PA)
  Kl E margin @12 dBi      = 36.99 − 33.273 = +3.72 dB (PASS)
  Kl E margin @6  dBi      = 36.99 − 39.273 = −2.28 dB (FAIL → Kl A)

INFLATION  −137.0 → −99.0 = 38.0 dB ;  repo "+23.1 dB uplink surplus" → 23.1 − 38.0 = −14.9 dB

BALLOON   area/W = 1/0.01955 = 51.15 cm²/W ; mass/W = 51.15 × 0.04893 = 2.503 g/W
  F33 433 2 W: P_dc = 5 × 1.2 = 6.0 W ; area = 306.9 cm² ; mass = 15.02 g ; eff = 2/6 = 33 %
  +3 dB (4 W RF): P_dc = 12.0 W ; area = 613.8 cm² ; mass = 30.0 g  (> B1 target)
```

---

## 8. Open items / TODO(unverified)

1. **No 433-specific FLRC sensitivity row** in the LR2021 datasheet; the 915 MHz
   FLRC rows (§2.1) are used as a band-flat stand-in. A bench measurement at
   433.92 MHz would firm §2.3 by a few dB. `TODO(unverified)`.
2. **`docs/analysis/433-2g4-flrc-link-budget-and-regulatory-audit.md` is not on
   `main`** (untracked in the primary worktree). Its figures are therefore not
   relied on here; the corrections are anchored to the datasheet directly.
3. **Licence-exempt 2.4 GHz density condition** (`docs/analysis/radio-legal-power-limits.md`)
   already concludes the 10 mW EIRP cap for this modulation — re-confirm against
   the current BNetzA Vfg. 91/2025 Tabelle 2 row (the doc flags its own annex row
   as previously unverified). `TODO(unverified)`.
4. **F33 2.4 GHz TX current** (`< 900 mA @2.4 GHz 5 V 1 W`, datasheet L113) is not
   needed for the uplink (ground TX) but is relevant if a 2.4 GHz **balloon** TX
   is ever considered; noted for completeness.
5. Earth-radius model behind the **451 km** radio horizon is repo-taken as agreed;
   not re-derived here.
