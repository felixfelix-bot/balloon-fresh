# SX1280 RF section — Table 15-1, the vendor's own reference BOM

**CORRECTION TO AN EARLIER STATEMENT.** I previously reported twice that the RF network values
"do not exist" and "are not derivable from this document". **That was wrong.** Figure 15-1 (the
drawing) prints designators only — but **`Table 15-1: Reference Design BOM` (page 146) prints MPN,
geometry, value and tolerance for every part.** I read the drawing and never looked for the table.

## The complete network, from the vendor

| ref | value | vendor MPN | tolerance | role |
|---|---|---|---|---|
| `C0` | 0.8 pF | `GRM1555C1HR80BA01D` | C0G **±0.1 pF** | impedance match (shunt) |
| `C1` | 1.2 pF | `GRM1555C1H1R2BA01D` | C0G ±0.1 pF | PI harmonic filter |
| `C2` | 1.2 pF | `GRM1555C1H1R2BA01D` | C0G ±0.1 pF | PI harmonic filter |
| `C3` | 100 pF | `GRM1555C1H101JA01D` | C0G **±5%** | DC block to antenna |
| `C4` | 0.5 pF | `GRM1555C1HR50WA01D` | C0G **±0.05 pF** | parallel with `L2` |
| `L1` | 3.0 nH | `LQW15AN3N0B80D` | **±0.1 nH** | match (series) |
| `L2` | 2.5 nH | `LQW15AN2N5C00D` | ±0.2 nH | PI filter (series) |

**Signal path:** `RFIO(22) → C0‖L1 (match) → C1/L2/C4/C2 (PI low-pass) → C3 (DC block) → U.FL → antenna`

`C3` blocks DC so a **grounded (DC-shorted) antenna** can be used — which is what a U.FL-fed PCB
antenna or whip presents.

**The tolerances are tight deliberately.** At 2.4 GHz a detuned match costs TX power and RX
sensitivity — i.e. link budget, which is the whole point of this radio. `C4` at ±0.05 pF and `L1` at
±0.1 nH are not substitutes for generic parts.

## Vendor part availability at JLCPCB (live query, controls passing)

| ref | LCSC | stock | @1 | status |
|---|---|---|---|---|
| `C0` | `C76988` | 13,333 | $0.0103 | ✅ **exact vendor MPN** |
| `C1`/`C2` | `C172868` `RF15N1R2A500CT` | 1,184 | $0.0182 | ⚠ **value match, tolerance ±0.25 pF — NOT the vendor ±0.1 pF** |
| `C3` | `C77177` | 1,060,776 | $0.0108 | ✅ **exact vendor MPN** |
| `C4` | — | — | — | ❌ **vendor part `GRM1555C1HR50WA01D` (±0.05 pF) NOT stocked**; best fallback ±0.25 pF = **5× the tolerance** |
| `L1` | `C2041661` | 12,126 | $0.1343 | ✅ **exact vendor MPN** |
| `L2` | `C703121` | 6,265 | $0.0687 | ✅ **exact vendor MPN** |

Connector: **`C88374` `U.FL-R-SMT-1(80)`, Hirose, 97,810 stock, $0.1138** — the genuine part.

## ⚠ BLOCKER: the tight-tolerance caps cannot be verified at JLCPCB

`C4` (0.5 pF **±0.05 pF**) is **not stocked**, and no stocked candidate states that precision. Best
fallback is **±0.25 pF — 5× the tolerance on a 0.5 pF part.**

**Honest limits on this finding:** my tolerance-parsing filter is **not trustworthy** — it reported
"0 value-matching candidates" for `C0` even though `C76988` IS the exact vendor part. So the claim
"no part exists" is **NOT** established. What IS established: the exact vendor parts are stocked for
`C0`, `C3`, `L1`, `L2`; `C4`'s is not; and `C1`/`C2`'s is not, with a ±0.25 pF substitute available.

**Three routes, needs an operator decision:**
1. **JLCPCB consigned/BOM parts** — supply the exact Murata parts via "Push BOM to JLCPCB". Keeps the
   vendor match intact. **Recommended.**
2. **Accept ±0.25 pF on `C1`/`C2`/`C4`** and **characterise with a VNA**, tuning on the bench.
   Viable, cheap, but a bench-tuning iteration — should be a choice, not a default.
3. **Order the RF network DNP and hand-populate** — 7 parts, and the operator already hand-solders
   optional parts. Keeps the match exact.

## Also confirmed independently by Table 15-1

`C5`/`C6` = 10 nF X7R · `C8`/`C10` = 100 nF X7R · `C9` = 470 nF · `R15` = 0 Ω · `L4` = 15 µH
(`MLZ2012M150W`, 0805) · **`Q1` = 52.000 MHz with `Cload = 10 pF`** — the crystal constraint is
stated **verbatim in the vendor BOM**, corroborating the Table 3-9 derivation and confirming the
rejection of the 8 pF candidates.

## Antenna

**The reference design does NOT specify an antenna** — it ends at `C3`. The network is designed for
**50 Ω single-ended**, so **any 50 Ω U.FL antenna** works; the matching is on-board.

**Recommended: U.FL → external 50 Ω 2.4 GHz antenna.** Rationale: the payload geometry is not frozen,
and an external antenna **decouples the RF from that decision**; it is a plug rather than a solder
joint, matching the operator's castellated/edge-launch preference; and at 2.4 GHz **antenna placement
dominates** — moving the radiator away from the PCB ground plane is worth more than any on-board
antenna's convenience.
