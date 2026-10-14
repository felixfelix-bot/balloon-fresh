# THE NICHROME-CUT DRIVE FET — selected, with live price and JLC assembly data

**Date:** 2026-10-14 · **Operator instruction:** *"please include the FET & please choose an
appropriate one for me. Please pay attention to price when surfacing the options. Please make sure
what you choose is available for soldering & assembly by JLCPCB."*

**Selection: `AO3400A`, LCSC `C20917` — Alpha & Omega Semiconductor, SOT-23, JLCPCB `base` library.**
$0.0891 at qty 1, $0.063 at qty 150. Stock **773,985**.

## Why the freeze needed this part at all

`docs/analysis/mppt-charge-path-specification.md` §3.5 specifies the cut as:

> *"bank node (VSCAP) → **firmware-gated MOSFET** (the repo's cut channel, `balloon-test-results.md`
> line 253) → nichrome → the tether"*

The `CUT_CHANNEL` symbol carried **no MOSFET**. It has `DRIVE` (pin 4, added by the symbol surgery)
with nothing to drive. **This part closes that gap.**

## The requirements, read from the repo rather than assumed

| parameter | value | source |
|---|---|---|
| `V_cut` | **3.3 – 5.4 V** | the **bank node (VSCAP)**, not the array side — so the cut works at night and works even if the converter has failed open |
| `I_cut` | **0.5 – 1.0 A** | the cut is a **resistive heater held on for 1–3 s**, not a logic pulse |
| gate drive | **3.3 V MCU logic line** | `DRIVE` on `CUT_CHANNEL` |
| **leakage** | **must join a night budget anchored at `I_Q ≤ 5 µA`** | §3.5: *"the MOSFET's leakage and the gate-drive bias are non-zero must join the night budget of §2's quiescent accounting"* |

**The leakage line is the one that makes this a real choice and not a default.** A microamp-class
off-state current is a **sizing constraint**, not a footnote.

## The candidates, live-queried with 3/3 positive controls passing

Controls resolved first (`C50645` SS24 774,321 @ $0.0257; `C2876746` BQ25504RGTR 21 @ $4.5857;
`C128413` SN74LVC1G373DBVR 34,892 @ $0.2779) — **so the negatives below are real, not a broken query.**

| part | LCSC | library | pkg | RDS(on) | I_max | Vgs(th) | stock | @1 | @150 |
|---|---|---|---|---|---|---|---:|---:|---:|
| **`AO3400A`** ✅ | **`C20917`** | **base** | SOT-23 | **48 mΩ @ 2.5 V** | **5.7 A** | 1.45 V | 773,985 | $0.0891 | $0.063 |
| `2N7002` ❌ | `C8545` | base | SOT-23 | **5 Ω @ 10 V** | **115 mA** | — | 1,861,350 | **$0.0175** | $0.014 |
| `SI2302` (Hottech) | `C181087` | **expand** | SOT-23 | 110 mΩ @ 2.5 V | 3 A | 1.2 V | 76,987 | $0.0337 | — |
| `SI2301CDS` (Vishay) | `C10487` | base | SOT-23 | 65 mΩ @ 4.5 V | 2.2 A | — | 96,500 | $0.0978 | — |
| `AO3400A` (UMW) | `C347475` | expand | SOT-23 | — | — | — | 700,906 | $0.0372 | — |
| `AO3400A` (BORN) | `C344010` | expand | SOT-23 | — | — | — | 80,440 | $0.0624 | — |

## The cheapest part is the wrong part — and that is the point

**`2N7002` at $0.0175 is 5× cheaper than the pick. It fails on BOTH load axes:**

- **`I_max` = 115 mA against a 0.5–1.0 A requirement.** It cannot pass *half* the minimum cut current.
- **RDS(on) = 5 Ω *at 10 V gate drive*.** The gate here is **3.3 V**, where it is worse still — call it
  8–10 Ω. At 1 A that is an **8–10 V drop from a 5.4 V rail**: physically impossible.

**So a price-first ranking would have selected a part that cannot cut the tether.** The lesson is
recorded because it is the exact failure mode the operator's "pay attention to price" invites if read
as "pick the cheapest": price only ranks candidates **that pass the requirement.**

**`SI2302` (Hottech, $0.0337) passes** — 3 A and 110 mΩ at 2.5 V — **but it is an `expand` part**, so
it carries JLCPCB's **extended-part fee**, and it is worse than `AO3400A` on every electrical axis at
a comparable unit price. **The `base`/`expand` tier is the price structure that matters here**, not
the unit price: a Basic part at $0.0891 can beat an Extended part at $0.0337 once the per-order fee is
charged.

## Why `AO3400A` wins

1. **JLCPCB `base` library** — assembled with **no extended-part fee**. This is the direct answer to
   "available for soldering & assembly by JLCPCB": it is in their **Basic** tier, not merely orderable.
2. **48 mΩ at 2.5 V / 5.7 A** — the only candidate that clears 1 A *comfortably* from a 3.3 V gate.
   Dissipation at 1 A ≈ **0.05 W**; drop ≈ **0.05 V** against a 5.4 V rail.
3. **Vgs(th) 1.45 V** — fully enhanced at 3.3 V logic **with margin**, and enhanced even at the
   VSCAP low end.
4. **30 V Vds against a 5.4 V rail** — large avalanche headroom for a heater load switched on a
   flying board.
5. **773,985 in stock** — no supply risk.
6. **SOT-23** — hand-solderable by the operator **and** machine-placeable by JLCPCB.

## The honest caveats, stated rather than buried

- **Leakage is NOT in the API data.** The describe field gives RDS(on), I_max, Vgs(th), Qg and
  capacitances but **no `Idss`**. The `AO3400A` datasheet figure is microamp-class at 25 °C, and
  **leakage rises steeply with temperature** (roughly doubling per ~10 °C) — so it is *smallest* at
  the mission's cold temperatures and worst on a warm bench. **The `I_Q ≤ 5 µA` night budget is
  therefore an ASSUMPTION until bench-measured.** The spec already requires that measurement (§4.4
  quiescent draw), so the requirement and the test already exist; **what must not happen is the budget
  being treated as met without the number.**
- **Gate-drive bias.** A **100 kΩ gate pull-down to GND** guarantees the FET is OFF if the MCU line
  floats (unpowered MCU). In the static case a pull-down dissipates **nothing** — once the gate has
  settled to GND no current flows — so it costs nothing in the night budget while removing the
  floating-gate failure. **A gate resistor (≈100 Ω) between `DRIVE` and the gate** limits the
  switching edge; it is not in the night budget either.
- **The latch (`U_CUT1–4`) and the FET are different parts.** `U_CUT` = `SN74LVC1G373DBVR` (the
  latched decision). The FET is the **switch**. Both are needed; neither substitutes for the other —
  the latch cannot pass 1 A, and the FET cannot remember.
- **Not yet wired.** This document records the SELECTION. The FET must still be added to the
  schematic per channel (`Q_CUT1–4` + gate R + pull-down R), the netlist re-exported, and the board
  re-placed and re-routed. **The selection is done; the wiring is not.**
