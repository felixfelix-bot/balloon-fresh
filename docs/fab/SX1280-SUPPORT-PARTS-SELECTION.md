# SX1280 SUPPORT PARTS — selected from live JLCPCB data

**Date:** 2026-10-14 · **Source:** live JLCPCB SMT API (`selectSmtComponentList/v2`), controls passing
(`BQ25504RGTR` → total=1, matching the known-good result from earlier sessions).

Everything here is chosen against **measured datasheet constraints**, not preference.

---

## 1. The 52 MHz crystal

**Table 3-9 (Semtech SX1280/SX1281 Rev 3.2) — Crystal Oscillator Specifications:**

| symbol | meaning | value |
|---|---|---|
| `F_XOSC` | crystal oscillator frequency | **52 MHz** |
| `C_LOAD` | crystal loading capacitance | **10 pF typical** |
| `C0_XTAL` | crystal shunt capacitance | typ 2 pF, **max 5 pF** |
| `R_S_XTAL` | crystal series resistance | typ 10 Ω, **max 50 Ω** (90 Ω if C0 < 3 pF) |
| `C_M_XTAL` | motional capacitance | 3 · 3.52 · 4 fF |

**`C_LOAD` is the binding constraint, and this is the trap.** Figure 15-1 shows **no external load
capacitors** — the datasheet text says the foot capacitances are **internally integrated**. So the
resonant load is **fixed at 10 pF in silicon**, and a crystal specified at any other load will sit at
the wrong frequency. The crystal cannot be chosen on price alone.

### ⚠ The cheapest 52 MHz crystal FAILS

| part | LCSC | @1 | `C_LOAD` | verdict |
|---|---|---:|---|---|
| `L327S520H11L` Lucki | **`C7502106`** | **$0.0904** | **10 pF** | ✅ **PASS** |
| `SX2B52.000F0810F30` | `C49253545` | $0.1196 | 8 pF | ❌ |
| `7D052000F01` HD | `C781783` | $0.1426 | **8 pF** | ❌ |
| `Q22FA12800519` Seiko Epson | `C841202` | $0.2658 | **8 pF** | ❌ |

**`C781783` was the first hit — 14,783 in stock and the third-cheapest by unit price — and it is
WRONG.** Its ERP name reads `52MHz ±10ppm 8pF`. **The Seiko Epson at 3× the price is also 8 pF.**

**Filter across 41 distinct candidates:** **14 pass** on 10 pF · 12 rejected (8, 9, 11, 12, 16, 20 pF)
· 15 unknown (value absent from the name).

### RECOMMENDATION: `C7502106` — `L327S520H11L` (Lucki), `SMD3225-4P`, $0.0904, stock 3,007

Cheapest part that **passes** the constraint. ±10 ppm.

**Alternates, both passing 10 pF, for stock resilience:**
- `C49253546` `SX2B52.000F1010F30` (Shenzhen SCTF), 2016-4P, $0.1235, stock 3,003
- `C2932996` `CM4052M00010T8188150` (JWT), $0.1309, stock 2,954
- `C7294606` `CF4052M00010001`, $0.1244, stock 4,173 — **highest stock of the passers**

### Two honest limits

1. **C0 and R_S are NOT in the API data** for these parts. The datasheet bounds them (C0 ≤ 5 pF,
   R_S ≤ 50 Ω), so **the specific crystal's datasheet must be checked before the order.** Reported as
   **UNVERIFIED, not as a pass.**
2. **Every 52 MHz crystal is JLCPCB `expand` tier** — 52 MHz is not a common frequency, so there is
   **no Basic-tier option**. That is an unavoidable extended-part fee, not a selection error.

### TCXO alternative (not chosen)

Figure 15-3 documents a TCXO option that **removes the C_LOAD dependency entirely**. `C54333744`
(TCXO SMD2016-4P, 52 MHz, 3.3 V, ±0.5 ppm) costs **$0.5612 — 6.2× the crystal** and needs a supply
rail plus different support parts. **±10 ppm at 2.4 GHz is a 24 kHz offset**, small against FLRC
channel bandwidths, so the crystal is sufficient. Recorded so the choice is visible, not implicit.

---

## 2. The reference-design passives (Figure 15-1, read from the rendered schematic)

| function | designator | value | part | LCSC | lib | stock | @1 |
|---|---|---|---|---|---|---|---|
| **DC-DC inductor** | `L4` | **15 µH** | `CD32-150M 15UH` | `C2826623` | expand | 3,655 | $0.0337 |
| **DC-DC filter cap** | `C9` | 470 nF | `CL05A474KP5NNNC` | `C47339` | expand | 853,854 | $0.0117 |
| **`VR_PA` bypass** | `C5` | 10 nF | `CL05B103KB5NNNC` | **`C15195`** | **base** | 6,381,677 | $0.0041 |
| **`VDD_IN` bypass** | `C6` | 10 nF | same as `C5` | **`C15195`** | **base** | 6,381,677 | $0.0041 |
| **`VBAT_IO` bypass** | `C8` | 100 nF | `CC0402KRX7R9BB104` | `C60133`-class | expand | — | ~$0.008 |
| **`VBAT` bypass** | `C10` | 100 nF | same as `C8` | — | expand | — | ~$0.008 |
| **rail link** | `R15` | **0 Ω** | `0402WGF0000TCE` | **`C17168`** | **base** | 9,442,324 | $0.0011 |

**`C15195` (10 nF) and `C17168` (0 Ω) are Basic tier** — no extended fee. The crystal and the 15 µH
inductor are Extended, which is unavoidable.

**The DC-DC is two parts total** (`L4` + `C9`), not a converter: it is the low-pass filter around the
SX1280's **internal** regulator. The datasheet states the regulator is *"considered switched ON
unless otherwise stated"*, so **`L4` and `C9` must be populated** even if the DC-DC is unused.

---

## 3. What the datasheet does NOT specify — and will not be invented

**Figure 15-1 prints the RF network designators `C0, L1, C1, L2, C4, C2, C3` with NO VALUES.** The
schematic text describes them as an impedance match (`C0`, `L1`) followed by a PI-section harmonic
filter (`C1`, `L2`, `C4`, `C2`) and a DC-blocking series cap (`C3`) to the antenna — but the values
are described as layout-, frequency- and antenna-dependent.

They are **not** in this datasheet and **will not be guessed.** They require a separate Semtech
matching document or an impedance pull from the SX1280 datasheet's `RFIO` S-parameter data.

---

## Method note (recorded because it nearly caused a wrong part)

**The API's attribute list returns attribute NAMES with EMPTY values.** A check that reads those and
finds nothing looks identical to a check that finds no violation — **and would have selected the 8 pF
crystal on price.** The real spec lives in `erpComponentName` (`"52MHz ±10ppm 8pF"`).

This is the same failure class as the fabricated-green DRC grading earlier in this campaign: **an
instrument that reports nothing is not an instrument that reports "fine".**
