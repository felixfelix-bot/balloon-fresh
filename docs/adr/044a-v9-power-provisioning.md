# ADR-044a — v9 F33 power provisioning: over-provisioning the 5 V PA rail for the module's maximum draw

- Status: **Proposed** — the *text* has **NOT** been accepted by a human. It records the
  operator's directive (quoted verbatim below) and the design it forces, but it does not say
  Accepted, and per the ADR-first rule (ADR-029 §Context) no schematic, placement, BOM freeze
  or fabrication may treat it as frozen until the operator accepts it.
- Date: 2026-10-07
- Decision owner: Felix (operator), directive given 2026-10-07.
- Author: worker-sch (Hermes subagent), working on branch `feat/v9-sch-rev2` at
  `/home/c03rad0r/worktrees/bf-v9-sch2`.
- **This is a companion record to ADR-044 and does not rewrite it.** ADR-044
  (`docs/adr/044-v9-power-rails.md`, branch `adr/v9-5v-rail-and-index`, commit `829ee06`)
  answers which rail topology v9 uses and recommends **option (a)** (direct tap of the supercap
  node into the D8 pin-1 selector) with **option (c)** (a clamp) as insurance. This record
  takes option (a) as given, raises the *sizing target* to the F33's measured maximum draw as a
  hard requirement, and makes the clamp **required insurance** rather than optional. Where this
  record and ADR-044 differ they differ only in the sizing target and the clamp's status, and
  both differences are stated explicitly.
- Related records: ADR-006 (`docs/adr/006-supercapacitor-power.md`, **Accepted** — the power
  architecture of record), ADR-029 (`docs/adr/029-dual-band-flight-board.md`, **item D8** the
  operator-ratified selectable pin-1 rail and **O5** the open 5 V-rail item),
  ADR-029 pin plan (`docs/adr/108-f33-sx1280-pin-plan.md`), ADR-034
  (`docs/adr/034-radio-band-split-433-tx-2g4-rx.md`, 433 MHz TX band), ADR-035
  (`docs/adr/035-tdm-radio-schedule.md`, the slot durations), ADR-036
  (`docs/adr/036-energy-policy-burst-storage-daylight-only-tx.md`, burst-sized storage and the
  µA-level night budget), ADR-037 (MCU, no FEM), ADR-038
  (`docs/adr/038-wifi-bt-disabled.md`, Wi-Fi/BT never enabled), ADR-044 (the companion
  topology record), ADR-045 (`docs/adr/045-antenna-solder-access.md`, antenna solder access).
- Related artefacts: `docs/f33-module/LoRa2021F33-2G4-datasheet-v1.1.pdf` §6 (electrical
  characteristics) and §8 (voltage-vs-power table), `docs/POWER-BUDGET-V9-D2BE.md`,
  `docs/PCB-HANDOVER-FOR-JLCPCB.md` §2.4, `docs/coordination/SCHEMATIC-PLAN-3VARIANTS.md`,
  `tracker/hardware/output/v8i_krt_gnss.kicad_pcb` (the frozen v8i board),
  `tracker/hardware/schematics/flight_board/build_flight_sch.py`,
  `tracker/hardware/schematics/flight_board/v9_flight.kicad_sch`.

---

## 0. The operator directive, verbatim

> "I want to provision more than enough power for the maximum draw that F33 can draw. Treat
> that as a hard design requirement, not a preference."

This is a **sizing directive**, not a topology change. It does not ask for a regulator, a
converter or a new rail; it asks that whatever supplies the F33 be sized to the F33's
*maximum* draw with margin, and that the design be treated as non-negotiable on that point.

---

## 1. The maximum draw being provisioned for (arithmetic shown)

### 1.1 The measured maximum

Source: **ADR-044 §2**, which quotes the F33 datasheet §8 *Voltage vs Power Table* by text
extraction (`pdftotext -layout`, Rev 1.1 — *not* a vision model). The 433/470 MHz column,
which is the v9 TX band (ADR-034 D1/D2):

| VCC | 433/470 MHz | current |
|---|---|---|
| 3.3 V | 28.9 dBm | 770 mA |
| 3.6 V | 30.3 dBm | 903 mA |
| 4.0 V | 31.2 dBm | 994 mA |
| 4.5 V | 31.8 dBm | 1008 mA |
| 5.0 V | 33.0 dBm | 1100 mA |
| **5.5 V** | **33.3 dBm** | **1118 mA** ← the maximum row |

**Maximum draw provisioned for: 1118 mA at 5.5 V.**

### 1.2 As DC watts

```
P_DC,max = V × I = 5.5 V × 1.118 A = 6.1495 W  ≈ 6.15 W
```

### 1.3 Decomposed as RF output at the stated efficiency plus quiescent

```
P_RF(33.3 dBm) = 10^(33.3/10) mW = 2138 mW = 2.138 W
PA DC at the repo's stated PA efficiency η = 36 %:
  2.138 W / 0.36 = 5.94 W
module's own quiescent (datasheet §6: Sleep Current < 20 µA):
  5.5 V × 20 µA = 0.11 mW ≈ 0.0001 W
```
→ **P_DC,max ≈ 5.94 W** by decomposition.

The **36 %** efficiency is the repo's own stated figure:
`docs/PCB-HANDOVER-FOR-JLCPCB.md` §2.4 — *"At 2 W RF out with ~36 % PA efficiency the DC input
is ~5.6 W."* The datasheet's own maximum row implies **34.8 %** (2.138 W / 6.1495 W), and the
5.0 V row implies **36.3 %** (1.9953 W / 5.5 W).

**The datasheet's directly-measured 6.15 W is 3.5 % above the 5.94 W decomposition, so 6.15 W
is the bounding figure and 6.15 W is what this record provisions for.** Provisioning for the
decomposition instead would under-provision by 0.21 W.

### 1.4 The margin multiple

| Ratio | Value | Meaning |
|---|---|---|
| 6.15 W ÷ 6.0 W | **1.03×** | vs the 6 W DC figure ADR-044 §5 sizes against |
| 6.15 W ÷ 2.4 W | **2.56×** | vs the solar array's own peak (ADR-006: 6.0 V × 400 mA = 2.4 W) — i.e. the array alone can never key the PA; the bank is the source |
| 1118 mA ÷ 1200 mA | **0.93×** | vs the datasheet's §6 round "< 1200 mA" TX-current bound (the §8 row is the tighter, real number) |
| 5.41 s ÷ 0.100 s | **54×** | endurance at 6.15 W on the **proposed doubled bank** vs the 100 ms sub-GHz TX slot of ADR-029 §3 |
| 2.71 s ÷ 0.100 s | **27×** | the same on the **accepted 1.65 F bank** |

Provisioning target, stated plainly: **6.15 W DC (1118 mA at 5.5 V) sustained rail capacity**,
with the storage margin of §3.

---

## 2. The supply path — and the trap that would be a hard failure

### 2.1 The path, specified

```
Solar array (12 cells, 4×3 in series, 6.0 V / 400 mA / 2.4 W peak)  [ADR-006]
      │
   D1  BAT54 Schottky (reverse-current block)                        [ADR-006]
      │
      ├──────────────────────────────────────────────┐
      │  VSCAP  = raw supercap node, POST-BAT54, PRE-LDO
      │                                              │
   C_CAP1 ── SCAP_MID ── C_CAP2   (2 × 3.3 F 2.7 V in series = 1.65 F @ 5.4 V, ADR-006)
      │        (R_BAL1 / R_BAL2 = 2 × 10 kΩ balancing, ADR-006 / ADR-044 §"already fixed")
      │
      ├── U7  TPS7A02 3.3 V LDO  →  +3V3  (the logic rail, and the bare LoRa2021's VCC)
      │
      └── J_VCC   pin-1 SELECTOR  (ADR-029 D8, operator-ratified 2026-10-05)
             pin 1 = VSCAP (raw cap rail, ≈5.4 V full charge)   ← F33 position
             pin 2 = COMMON → F33_VCC
             pin 3 = +3V3 (TPS7A02 OUT)                        ← nested bare-LoRa2021 position
                    │
                 F33_VCC  ── C_BULK (100 µF) ─ C_HF (100 nF) ─ D_CLAMP (TVS) ─ R_MON1/R_MON2
                    │
              U2 pin 1 (VCC)  LoRa2021F33-2G4, 2 W PA
```

**Schematic rendering of the selector (for the reviewer).** `J_VCC` is drawn as a
**3-pad solder jumper** (`Jumper:SolderJumper-3_P1.3mm_Open_RoundedPad1.0x1.5mm`) whose symbol is
emitted from the repo-local `balloon_flight_v9` library rather than KiCad's `Jumper` library:
the shared project `sym-lib-table` is written by *both* schematic generators, and the C3
generator's union does not carry `Jumper`, so pulling the symbol from a stock library would
have left the v9 sheet unresolvable whenever the C3 target was regenerated. Keeping the symbol
repo-local makes the sheet generation-order independent. Pin 2 is the common pad.

### 2.2 Why the selector exists (it is not this record's invention)

ADR-029 **D8** (operator-**RATIFIED** 2026-10-05, quoted in ADR-044 §1) requires it:

> "**Pin 1 VCC conflict — BLOCKING.** Bare module VCC = **1.8–3.6 V (use 3.3 V)**. F33 = **5 V**,
> up to **~1200 mA**. Same pad number → same net. … **Requires a selectable rail on pin 1**
> (solder jumper or DNP regulator), or the option is unsafe to build."

Both modules are 18-pad with identical pad numbering (measured pad-for-pad in D8), so pin 1 is
one physical net and *must* be selectable. ADR-044 §1 records the same as "already fixed and
not re-opened here". This record therefore inherits the selector and only fixes what feeds it.

### 2.3 The trap: the F33's PA must NEVER be fed through the TPS7A02

**This is a hard failure, not a hypothesis.** Stated against the parts that exist:

| Quantity | Value | Source |
|---|---|---|
| F33 maximum draw at pin 1 | **1118 mA** | F33 datasheet §8, 5.5 V / 433 MHz row (ADR-044 §2) |
| TPS7A02 recorded output rating | **≤ 300 mA** | ADR-006 (§LDO Regler): *"Ausgang: 3.3V @ bis 300mA (reicht fuer TX-Bursts)"* |
| KiCad stock symbol the repo maps the SOT-23-5 LDO to, `Regulator_Linear:TPS7A0533PDBV` | **200 mA** | `/usr/share/kicad/symbols/Regulator_Linear.kicad_sym`, Description: *"200-mA Ultra-Low-Iq LDO, 3.3V, SOT-23-5"*; it is the `PART_MAP` target for `Package_TO_SOT_SMD:SOT-23-5` in `build_flight_sch.py` |

```
1118 mA ÷ 300 mA = 3.73×   over the ADR-006 figure
1118 mA ÷ 200 mA = 5.59×   over the KiCad-lib figure
```

**Feeding the F33's PA through the TPS7A02 would demand 3.7–5.6× the regulator's output
rating.** The consequence is not degraded link: at best the LDO current-limits, its output
collapses mid-packet, and the 3.3 V rail — which also carries the ESP32-S3, the SX1280 and the
GNSS — browns out with it; at worst the LDO is destroyed and takes those loads down. This is
an arithmetic certainty against a cited rating, which is why it is written as a trap to avoid
rather than as a risk.

The same requirement is stated independently by `docs/PCB-HANDOVER-FOR-JLCPCB.md` §2.4:

| Spec | Value | Justification (verbatim in the repo) |
|---|---|---|
| PA rail | **Separate from VCC_3V3 logic rail**, fed from supercap/LDO capable of **2 A+** | *"Prevents logic brownout during TX bursts"* |

**Requirement.** `F33_VCC` is fed from **VSCAP** (post-BAT54, pre-LDO) through J_VCC pin 1.
The TPS7A02 output reaches pin 1 only in the bare-module position of the selector, where the
load is the bare LoRa2021's 1.8–3.6 V / ~120 mA class draw (D8 item 1; `docs/inventory.md`
line 29 records `TX @433MHz 22dBm: <120mA`).

**TODO(unverified) — the exact open question:** *what is the TPS7A02's datasheet output-current
rating and its current-limit behaviour?* The part's own datasheet is not committed in this
repository, so the figures used above are ADR-006's 300 mA and the KiCad library's 200 mA for
the sibling TPS7A05. Both are far below 1118 mA, so the trap's conclusion is unchanged by
which figure is correct; only the exact multiple is. Note also that ADR-006's 300 mA line ends
"reicht fuer TX-Bursts" (enough for TX bursts) — true for the *original* single-radio 3.3 V
load, and false for the F33's 2 W PA.

---

## 3. Storage sizing for margin

### 3.1 The accepted bank (ADR-006, Accepted)

```
C = 1.65 F  (2 × AVX SCC 3.3 F 2.7 V in series), V_top = 5.4 V   [ADR-006; ADR-044 §5]
E_full   = ½ · 1.65 F · (5.4 V)²  = 24.057 J   (ADR-044 §5: 24.06 J)
E @ 3.0 V= ½ · 1.65 F · (3.0 V)²  =  7.425 J   (ADR-044 §5:  7.43 J)
Usable, 5.4 → 3.0 V               = 16.632 J   (ADR-044 §5: 16.63 J)
Endurance at 6.15 W               = 16.632 J ÷ 6.1495 W = 2.705 s
```

### 3.2 What doubling buys (4 cells: two in parallel at each series position)

```
C = 3.3 F  (4 × AVX SCC 3.3 F 2.7 V: 2 series positions × 2 parallel cells each)
E_full        = ½ · 3.3 F · (5.4 V)² = 48.114 J
E @ 3.0 V     = ½ · 3.3 F · (3.0 V)² = 14.850 J
Usable        = 33.264 J              →  ΔJ = +16.632 J  (exactly double, as expected)

Endurance at 6.15 W: 33.264 J ÷ 6.1495 W = 5.410 s      →  Δt = +2.705 s
```

| Quantity | Accepted bank (1.65 F, 2 cells) | Doubled bank (3.3 F, 4 cells) | Δ |
|---|---:|---:|---:|
| Usable energy, 5.4 → 3.0 V | 16.632 J | 33.264 J | **+16.632 J** |
| Endurance at 6.15 W DC | 2.705 s | 5.410 s | **+2.705 s** |
| Bank ESR (2·ESR_cell → ESR_cell) | 2·ESR_cell | ESR_cell | **−50 %** |
| Cell mass | 2 × 1.5 g = 3.0 g | 4 × 1.5 g = 6.0 g | **+3.0 g** |
| Margin vs the 100 ms sub-GHz TX slot (ADR-029 §3) | 27× | 54× | +27× |
| Margin vs a 0.65 s SF12 packet (ADR-044 §5) | 4.2× | 8.3× | +4.1× |

**Added mass: +3.0 g**, i.e. the bank doubles from 3.0 g to 6.0 g.
Source: ADR-006 §Supercapacitors — *"Gewicht: 2x 1.5g = 3.0g"*; restated in
`docs/POWER-BUDGET-V9-D2BE.md` §mass — *"2 × AVX SCC 3.3 F 2.7 V supercap | 3.00"*. Each cell
is 1.5 g, so two more cells is 3.0 g.

### 3.3 Does "over-provisioning for the F33 maximum draw" imply the double? — the numbers, then the pick

Two candidate readings, both checked against numbers rather than assumed:

- **Reading A — "more energy":** already satisfied without doubling. The accepted bank holds
  **27×** the 100 ms sub-GHz TX slot (ADR-029 §3) and **4.2×** a 0.65 s SF12 packet
  (ADR-044 §5). Energy is **not** the binding constraint, so on this reading the directive
  implies no storage change at all.
- **Reading B — "more current into a rail that must not sag":** this is where the double earns
  its place. The bank's contribution to the rail step during a burst is
  `ΔV = I · ESR_bank` (see §4), and doubling halves `ESR_bank` (2·ESR_cell → ESR_cell).

**Pick: accept the doubled bank (3.3 F, four cells, +3.0 g), as the storage side of the
directive; but state plainly that this is a *margin purchase*, not a *fix*, and that a larger
multiple is NOT implied by the directive.** The arithmetic behind that three-part statement:

1. **The double is what "more than enough" means for the current path.** It is the only
   storage-side lever that reduces the bank's ESR step, and +3.0 g is cheap against the
   module it protects: the F33 alone is a 39 × 21 mm module (ADR-029 D8), and the doubling
   costs 3 g.
2. **A larger multiple buys nothing the directive asks for.** Quadrupling to 6.6 F would add a
   further +6.0 g and another 27× of endurance that no mission profile asks for — there is no
   burst in ADR-029 §3, ADR-035 or ADR-036 longer than 100 ms of sub-GHz TX. Over-provisioning
   is not the same as unbounded provisioning, and 54× is already the "more than enough" end of
   it.
3. **Neither bank meets the rail-step acceptance number, so the double must not be sold as a
   fix.** ADR-029 §5 test 4 accepts a rail dip of **< 20 mV** during a worst-case burst. At
   1.2 A that requires `ESR_bank ≤ 16.7 mΩ` (§4). With an assumed cell ESR of 0.10 Ω the
   doubled bank's ESR is 0.10 Ω (12× too high) and the accepted bank's is 0.20 Ω (12× too
   high); reaching 16.7 mΩ from 0.10 Ω cells would take **12 cells in parallel per series
   position — 24 cells, +36 g**. That is a different board, not an over-provisioning margin.
   The honest conclusion is that **ADR-029 §5 test 4 is not met by scaling this cell family**,
   and the next step is the measurement, not more cells.

> **TODO(unverified) — the exact open questions.** (i) *The AVX SCC 3.3 F 2.7 V cell's ESR is
> not in this repository* — neither at 25 °C nor at −60 °C. Every ESR-derived number in §3 and
> §4 is conditional on the assumed 0.10 Ω/cell and scales linearly with it. (ii) *The bank's
> −60 °C capacitance and ESR are unmeasured* (ADR-036 open item; ADR-042 line 116 notes the same
> for the LDO/supercap chain). (iii) *ADR-029 §5 test 4 (rail dip < 20 mV) has not been run.*

---

## 4. Local decoupling at the module pin, sized for the pulse

### 4.1 What the bulk cap is for (and what it is not for)

ADR-044 §5 already established the important half: the **bank** supplies the burst, not a small
cap — *"the local bulk cap at the module is therefore about suppressing the fast component
(ESR/inductance of the run to the cap string), not about supplying the burst."* The arithmetic
confirms it. A bulk cap alone supplying the burst would need:

```
ΔV = I · t / C  →  C = I · t / ΔV
100 ms at 1.2 A within 3 V:  C = 1.2 × 0.100 / 3.0 = 40 mF   (impossible at this mass)
```

### 4.2 The rail step during the intended burst, itemised

Intended bursts: **0.1 s** (the sub-GHz TX slot, ADR-029 §3) and **0.31 ms** (a 100-byte FLRC
burst at 2.6 Mbps, ADR-044 §5). Max draw **1.2 A**.

| Term | Formula | Accepted bank | Doubled bank |
|---|---|---|---|
| Bank capacitance term, 100 ms | `I·t/C_bank` | 1.2 × 0.100 / 1.65 = **72.7 mV** | 1.2 × 0.100 / 3.3 = **36.4 mV** |
| Bank capacitance term, 0.31 ms | `I·t/C_bank` | **0.225 mV** | **0.113 mV** |
| **Bank ESR step** | `I · ESR_bank` | 1.2 × 0.20 Ω = **0.240 V** | 1.2 × 0.10 Ω = **0.120 V** |
| Bulk-cap term for the burst | — | **absent** (the bank supplies it) | absent |
| **Total worst step, 100 ms** | | **0.313 V** | **0.156 V** |

So the **ESR step dominates by ~3 orders of magnitude** and is the one term a bulk capacitor
cannot reduce. Total rail excursion over a 100 ms burst from full charge: **5.4 → 5.087 V**
(accepted bank) or **5.4 → 5.244 V** (doubled) — both far inside the module's 3.0–5.5 V range.
The ESR step only becomes a link-budget threat at the **bottom of the discharge**, which is
why §6's firmware rule is written against the *loaded* rail.

### 4.3 The bulk capacitor values, and what they actually cover

The bulk cap covers the **current step edge**, not the burst:

| C_BULK | time at 1.2 A within 20 mV | within 100 mV | within 1 V |
|---|---|---|---|
| 100 µF | 1.67 µs | 8.3 µs | 83 µs |
| 470 µF | 7.8 µs | 39 µs | 392 µs |

**Specified values (both cited, not invented):**

| Ref | Value | Footprint | Citation |
|---|---|---|---|
| `C_BULK` | **100 µF** low-ESR ceramic or tantalum | `C_1206_3216Metric` | `docs/PCB-HANDOVER-FOR-JLCPCB.md` §2.4: *"Bulk decoupling — **≥ 100 µF low-ESR tantalum or ceramic** at PA VCC, plus 100 nF HF bypass — 1.7 A spikes need real energy storage"* |
| `C_HF` | **100 nF** | `C_0402_1005Metric` | same line (*"plus 100 nF HF bypass"*); ADR-029 §2(f) also requires each radio rail to get *"its own ferrite + bulk cap"* |

100 µF is the cited floor and is what is fitted; it covers the PA's current step for the
first ~8 µs within 100 mV, after which the bank is the source. A larger bulk cap cannot fix
the ESR step (§4.2), so it is not a substitute for §3's bank decision or for §5's answer.

**Assumed ESR, and where it comes from:** `ESR_cell = 0.10 Ω`, giving `ESR_bank = 0.20 Ω` for
two cells in series and `0.10 Ω` for the doubled bank. This value is **not citable from this
repository** — hence:

> **TODO(unverified) — exact open question:** *what is the AVX SCC 3.3 F 2.7 V cell's ESR, at
> 25 °C and at −60 °C?* No datasheet, measurement or vendor figure for the cell's ESR is
> committed to this repository. The 0.10 Ω figure is a placeholder used so the arithmetic is
> checkable; every `ΔV_ESR` number above is linear in it, and it must be replaced by a measured
> or vendor-cited value before the rail is frozen.

---

## 5. Is a boost / buck-boost converter required for the directive? — **no, refused**

**Refused**, and the grounds are ADR-044's own option (b) analysis (ADR-044 §3, §4), unchanged
by this directive:

- **mass** — roughly €1.50–4.00 plus an inductor and reservoir caps, order of 0.5–1.5 g
  (ADR-044 §3 option (b); part selection not made, `TODO(unverified)` there);
- **quiescent draw** — a switcher's I_Q is added to a bank whose *night* budget is the deciding
  quantity (ADR-036: deep-sleep current in µA decides whether the night log survives);
- **EMI** — a switching node ~2 mm from a −136 dBm 2.4 GHz receiver forces ADR-032 simulation of
  switcher harmonics and makes ADR-029 §5 tests 1 and 3 (2.4 GHz noise floor rise < 3 dB, GNSS
  C/N0 drop < 1 dB) the acceptance numbers for an intrinsic noise source;
- ADR-044 §4 recommendation: *"Do NOT adopt option (b) unless a bench measurement shows the sag
  breaks the link"* — and no such measurement exists.

**What that costs, stated plainly and without overstatement.** With no converter the rail **is**
the cap voltage, so it falls from 5.4 V toward ~3.0 V over the discharge (ADR-044 §3). Reading
the exact rows of ADR-044 §2 (433/470 MHz column):

| Rail voltage | Output | +30 dBm (1 W) available? |
|---|---|---|
| 5.5 V | 33.3 dBm | yes |
| 5.0 V | 33.0 dBm | yes |
| 4.5 V | 31.8 dBm | yes |
| 4.0 V | 31.2 dBm | yes |
| 3.6 V | 30.3 dBm | yes |
| **≈3.5 V** | **≈30.0 dBm** | **threshold** |
| 3.3 V | 28.9 dBm | **no** |

- **+30 dBm is therefore available only above ≈3.5 V of supply.** The datasheet publishes no
  row at exactly +30.0 dBm; the bracketing rows are **3.3 V → 28.9 dBm** and **3.6 V → 30.3 dBm**,
  and linear interpolation between them gives
  `3.3 + 0.3 × (30.0 − 28.9) / (30.3 − 28.9) = 3.54 V`. **This is an interpolation between
  published rows, not a datasheet claim**, and it is marked as such.
- **The module's full output (33.0 dBm / 2 W) requires the 5.0 V row** (5.0 V → 33.0 dBm /
  1100 mA). At 4.5 V it is 31.8 dBm; at 4.0 V, 31.2 dBm.
- On the 868/915 MHz column +30 dBm is never available below 5.5 V (5.5 V → 30.4 dBm), but that
  band is not the v9 TX band (ADR-034 D1/D2).

So the honest statement of the directive's limit is: **more than enough *power provisioning*
does not buy more *supply voltage*.** Without a converter the rail's top is 5.4 V at full
charge and full +33 dBm / 2 W is available only near that top; the design's answer is
*firmware gating on the measured rail* (§6), not a regulated rail.

---

## 6. Rail monitor and the firmware inhibit rule

### 6.1 The monitor, specified

An ADC divider on the F33's own supply node into an ESP32-S3 ADC pin:

```
F33_VCC ── R_MON1 (4.7 MΩ) ──┬── F33_VSENSE ──→ U1 (ESP32-S3) pin 21 = GPIO13
                             │
                        C_MON (10 nF)
                             │
F33_VSENSE ── R_MON2 (4.7 MΩ) ── GND
```

| Quantity | Value | Basis |
|---|---|---|
| Divider ratio | 0.5 | R_MON1 = R_MON2 = 4.7 MΩ |
| F33_VSENSE at 5.4 / 5.0 / 3.5 / 3.0 V | 2.70 / 2.50 / 1.75 / 1.50 V | arithmetic; all inside the ESP32-S3 ADC's input range |
| Divider bias at 5.4 V | **0.574 µA (3.1 µW)** | 5.4 V ÷ 9.4 MΩ |
| Tap settling τ with C_MON = 10 nF | **23.5 ms** | (4.7 MΩ ∥ 4.7 MΩ) × 10 nF — fast enough to track a bank that discharges over ~5.4 s, slow enough to be quiet |
| Existing supercap divider (ADR-006) bias | **2.70 µA (14.6 µW)** | R_DIV1/R_DIV2 = 2 × 1 MΩ — *recorded here because it dominates the pair* |

**Why 4.7 MΩ and not 1 MΩ:** ADR-036's night arithmetic is *"at 100 µW, 10 h = 3.6 J"*, i.e.
the night budget is at the 100 µW scale. A 1 MΩ/1 MΩ monitor would draw 14.6 µW and, added to
the existing supercap divider's 14.6 µW, would put **29 µW — 29 % of ADR-036's 100 µW anchor —
into two dividers alone.** At 4.7 MΩ the new monitor costs 3.1 µW, and the pair costs 17.7 µW.
`C_MON` (10 nF) is required because a 2.35 MΩ Thevenin source cannot charge the ADC's
sample-and-hold capacitor within its sample window; the cap is the charge reservoir.

> **TODO(unverified) — exact open questions.** (i) *Which ESP32-S3 ADC channel corresponds to
> GPIO13, and is ADC2 usable on this board?* The assertion here rests on: GPIO13 is assigned to
> nothing in the ADR-029 pin plan; and ADR-038 D1 makes Wi-Fi/BT **never enabled**
> (`CONFIG_ESP_WIFI_ENABLED=n`, `CONFIG_ESP_BT_ENABLED=n` in
> `tracker/firmware/sdkconfig.defaults.esp32s3`), which is the condition normally attached to
> ADC2 use. The channel number itself is not committed in this repository.
> (ii) *What source impedance does the ESP32-S3 ADC require for the accuracy this monitor
> needs?* Not in this repository.
> (iii) *The pin plan has not been amended to record GPIO13's new assignment* — it must be,
> with the strapping audit re-checked, before the board is frozen.

### 6.2 The firmware rule (normative)

Over-provisioning the storage is void if the rail sags below the PA's minimum **mid-packet**.
The monitor exists so the firmware can measure the loaded rail and refuse to key into a sag:

- **R1.** `f33_tx_inhibit` is evaluated against the **measured** `F33_VSENSE`, immediately
  before keying and held for the duration of the burst — not against a stored or assumed value.
- **R2.** For the module's full output (33.0 dBm / 2 W on 433 MHz), `V_rail_loaded` must be
  **≥ 5.0 V** (the datasheet row at which 33.0 dBm is reached, ADR-044 §2). Below that the
  firmware selects a lower power level from the §8 table rather than claiming 2 W.
- **R3.** For a +30 dBm target, `V_rail_loaded` must be **≥ 3.54 V (interpolated) plus the
  bank's ESR step**, i.e. **≥ 3.66 V with the doubled bank** (3.54 + 0.120 V) or **≥ 3.78 V
  with the accepted bank** (3.54 + 0.240 V). The threshold is on the *loaded* rail: gating on
  the open-circuit rail would key the PA into the ESR step and land below the PA's minimum.
- **R4.** Any measurement below the threshold for the wanted power must **reduce the target
  power**, not the threshold. This is ADR-029 O5's own fallback: *"operate the F33 at 3.3 V with
  reduced output rather than claim +30 dBm."*
- **R5.** The monitor must be sanity-checked at bring-up against a bench supply before it is
  trusted to gate TX (a divider that reads high would permit a sagging rail to key).

---

## 7. Over-voltage — ADR-044's finding, repeated, and the clamp as required insurance

Repeating ADR-044 §2 (it is the finding this record's §5 and §6 depend on), with the status of
the clamp changed by the directive:

1. The datasheet's §6 *Voltage Range* row is **"Min 3.0 / Typ 5 / Max 5.5 V"**. The supercap
   string's top is **5.4 V** (2 × 2.7 V) — **inside** the stated operating range, with **0.1 V
   (1.8 %)** of margin.
2. **Rev 1.1 publishes no Absolute Maximum Ratings table at all.** `grep -iE
   "absolut|rating|stress"` over the extracted text returns only the operating-temperature row
   and the §8 note-2 PA warning. **5.5 V is a maximum *operating* figure; the level at which the
   part is actually damaged is not published in this revision.**
3. The rail is **not inherently limited to 5.4 V by the module**. It is limited to the cap
   string's rating *if the balancing resistors do their job*, and otherwise by whatever the
   12-cell array pushes through the BAT54. The array's **open-circuit** voltage exceeds its 6.0 V
   nominal working figure (a Si cell's V_OC exceeds its V_MPP), and the cells operate near −60 °C
   — that is the real over-voltage path.
4. **The clamp.** ADR-044 §3 option (c) recommends a clamp (*"a low-capacitance TVS/zener or a
   crowbar/OV-monitored switch"*, ~€0.05–0.30, < 0.1 g) but records it as **not mandatory** on
   the datasheet's stated maximum. **Under this directive it is required insurance:** the
   operator has asked for the provision to be treated as a hard requirement, and the clamp is
   the only part whose whole job is to convert an *unpublished* damage threshold into a
   *defined* one. It is fitted as `D_CLAMP`, a TVS across `F33_VCC` to GND, alongside the
   series bank and its balancing resistors.

> **TODO(unverified) — the exact open questions.** (i) *What is the 12-cell array's
> open-circuit voltage at −60 °C?* It is not in this repository, so the maximum the BAT54 can
> present to the cap string's top node is unknown, and no claim can be made that the top node
> never exceeds the F33's stated 5.5 V maximum. (ii) *What is the F33's actual damage
> threshold?* Unpublished in Rev 1.1 and therefore unknown. **Consequence, stated so it is not
> glossed over: the clamp's set point cannot be finalised.** It must conduct above the 5.4 V
> rail top and below a threshold that is not published, and that window is not closable until
> (i) or (ii) is measured. The clamp is therefore fitted and its part/set point carries an
> explicit `TODO(unverified)` on the schematic, not a guessed part number.

---

## 8. What this ADR does NOT close

- **O5's evidence half stays open** (ADR-044 §7 is unchanged): no 5 V chain demonstrated at
  ≥ 1.2 A load-step; no 3.3 V rail at ≥ 0.60 A transient; no cold supercap/regulator evidence;
  no ADR-029 §5 test 4 (< 20 mV rail dip). This record sizes for the maximum draw; it does not
  measure the chain.
- **The supercap cell ESR and the −60 °C bank behaviour** (§3, §4, §7) — unmeasured.
- **The array's open-circuit voltage at −60 °C** and the F33's damage threshold (§7).
- **The clamp's set point** (§7) and **the exact rail-monitor ADC channel** (§6).
- **The BOM freeze** — this record adds parts, and per ADR-029 O5 the freeze stays gated on the
  evidence plus O0.

## 9. What would falsify this

- A bench measurement showing the 5 V chain **cannot** deliver 1.2 A load steps → the tap is
  not viable at the maximum draw and option (b) returns with the measurement in hand.
- A measurement showing the cap-string top node **can** exceed 5.5 V → the clamp becomes
  *mandatory* rather than insurance, and its set point is fixed by the measurement.
- A measurement of cell ESR materially above the assumed 0.10 Ω → the ESR step grows linearly
  and the doubled bank's advantage grows with it; ≥ ~0.5 Ω would break the +30 dBm threshold in
  §6 by itself.
- An operator preference for a regulated rail (e.g. to decouple output power from state of
  charge) → option (b), accepted on the record with its mass, I_Q and EMI costs.

---

## Appendix — the arithmetic, in one place

```
P_DC,max        = 5.5 V × 1.118 A                     = 6.1495 W
P_RF(33.3 dBm)  = 10^(33.3/10) mW                     = 2.1380 W
decomposition   = 2.1380/0.36 + 5.5 × 20e-6           = 5.9389 W   (36 % from PCB-HANDOVER §2.4)
provisioned     = max(6.1495, 5.9389)                 = 6.1495 W   → 6.15 W

E(1.65 F, 5.4→3.0 V) = ½·1.65·(5.4²−3.0²)             = 16.632 J  → 16.632/6.1495 = 2.705 s
E(3.3  F, 5.4→3.0 V) = ½·3.3 ·(5.4²−3.0²)             = 33.264 J  → 33.264/6.1495 = 5.410 s
ΔJ = +16.632 J ; Δt = +2.705 s ; Δmass = +2 × 1.5 g   = +3.0 g

ΔV_ESR(2 cells)  = 1.2 A × 2 × 0.10 Ω                 = 0.240 V
ΔV_ESR(4 cells)  = 1.2 A × 1 × 0.10 Ω                 = 0.120 V
ΔV_bank(0.1 s)   = 1.2 × 0.1 / 1.65 (or 3.3)          = 0.0727 V (or 0.0364 V)
C_BULK holds 1.2 A within 20 mV for t = C·ΔV/I         = 100e-6 × 0.020 / 1.2 = 1.67 µs

+30 dBm crossing (interpolated, 433 MHz)              ≈ 3.54 V
load-gated threshold  = 3.54 + 0.120 (doubled bank)    = 3.66 V
                       3.54 + 0.240 (accepted bank)   = 3.78 V

TPS7A02 vs F33: 1118/300 = 3.73× ; 1118/200 = 5.59×     → hard-failure trap, §2.3
rail monitor bias: 5.4 V / 9.4 MΩ                      = 0.574 µA = 3.1 µW
```
