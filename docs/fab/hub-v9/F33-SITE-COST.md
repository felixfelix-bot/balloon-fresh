# DECISION PACKAGE — the F33 site: what dropping it saves, now that its 2 W is unusable

**Date:** 2026-10-14 · **Status:** operator decision required, **before the order**.
**Trigger:** `RF-433-LEGALITY-DECISION.md` — the F33's +33 dBm (2 W) is **not licence-free
legal** in Germany, and the amateur route is blocked for a drifting balloon by **AFuV §13
Abs. 1 (location)**. So the F33's headline capability is **unusable** on this flight.

**This document quantifies what that costs us, using measurements — not estimates.**

---

## 1. The measured footprint cost (from the frozen board, via `pcbnew`)

`tracker/hardware/measure_f33_cost.py` on `hub_board_v9.kicad_pcb`:

| site | footprint | bounding box | pads |
|---|---|---:|---:|
| **`U2`** | `LoRa2021F33_2G4` | **39.65 × 26.20 = 1038.8 mm²** | 18 |
| **`U3`** | `LoRa2021_Castellated` (bare) | **21.81 × 20.20 = 440.6 mm²** | 18 |
| **`U5`** | `ublox_MAX` (GNSS) | 11.85 × 13.95 = 165.3 mm² | 18 |

**The F33 costs 598.3 mm² more than the bare module** — **12.2 % of the 70 × 70 mm board.**

**And it is a major reason the outline is 70 mm at all:** the seat probe found **65 mm
overflowed on `U5`** and **70 mm seats all 39 parts**. A ~598 mm² block is a large part of
what forced 60 → 70 mm.

**Mass consequence** (at the repo's own 6.26 g / 4900 mm² @ 0.6 mm density):

| | area | 0.6 mm mass |
|---|---:|---:|
| F33 site (`U2`) | 1038.8 mm² | **1.33 g** |
| bare site (`U3`) | 440.6 mm² | **0.56 g** |
| **delta** | **598.3 mm²** | **0.76 g** |

*(0.76 g is small against a ~57 g payload — so **mass is NOT the argument.** Area and the
pre-regulator branch are.)*

## 2. The cost that matters — the rail split, stated precisely

ADR-070's decision to keep **both** sites was justified by capability: `U2` F33 for the
**433 TX** and `U3` bare for the **2.4 RX**. But the F33 is the *only* reason the board
carries:

- **a second, separate feed for `U2`'s pin 1 — a pre-regulator from raw `VSCAP` (~5.4 V)**,
  because the F33 needs **5 V** for full output while the bare module runs at **3.3 V**, and
- the **~1100 mA at 5 V** peak TX current path (vs **120 mA** for the bare part), and
- the **PA table / RF-switch support** (`setRfSwitchTable`, `DIO5`/`DIO6`) the *bare* module
  does not need, and
- **12.2 % of board area**, which is **upstream of the outline decision**.

> **Precision matters here:** ADR-070 says this is a **pre-regulator fed from raw `VSCAP`**,
> **not** the D14-frozen TPS62162 5 V network. So *"if we drop the F33 we delete the 5 V
> rail"* is **WRONG** — the D14 5 V network stays regardless. What the F33 alone justifies is
> the **extra pre-regulator branch, its selectable pin-1 rail, and the 1.1 A current path.**

**If the F33's 2 W is unusable, that hardware serves a capability we cannot legally
exercise.** The lawful ceiling is **+12.15 dBm EIRP**; the **bare** LoRa2021 at **+22 dBm**
also exceeds it — so **both parts must be backed off**, and the legal operating point is
reachable **without** the F33.

## 3. And the range consequence is small, because the binding mode is LoRa

From `RF-433-LEGALITY-DECISION.md` §3, at the 10 mW ERP ceiling:

| mode | 300 km verdict |
|---|---|
| FLRC 2.6 Mbit | **FAILS** (−10.1 dB) |
| FLRC 650 kbit | **FAILS** (−3.6 dB) |
| **LoRa SF12** | **PASSES, +32.4 dB margin** |

**The lawful mission is a low-rate LoRa beacon either way.** The F33's extra 11 dB does not
change which mode survives; **the mode is decided by the legal ceiling, not by the part.**

## 4. The honest counter-arguments (why this is a decision, not an obvious win)

1. **The F33 might still be worth keeping for a licensed future.** If we ever hold an
   amateur licence or obtain an individual BNetzA assignment, the F33's 2 W becomes usable
   **without a board re-spin**. DNP-by-default already costs us nothing at fab time.
2. **A DNP site is not free in design terms** — it still occupies area, forces the outline,
   and carries the extra pre-regulator branch. But it **is** free in *order* terms (JLC
   does not populate it).
3. **The pre-regulator branch may be wanted for other loads** — the D14 5 V network stays
   regardless (it is a *different* rail); what would go is the extra `VSCAP`-fed branch,
   which must be confirmed as otherwise-unused before removal.
4. **Re-spin risk:** removing a footprint after routing invalidates the route. **This is the
   real cost** — and it is why this belongs in the **order** decision rather than a
   post-order cleanup.

## 5. Options

**Option A — keep both sites as they are (status quo).**
Board stays routed and JLC-legal. Pay area, the extra pre-regulator branch, and outline
pressure for a capability unusable without a licence. **No re-spin. Zero schedule risk.**

**Option B — keep `U2` as a DNP site, do not populate it.** *(likely best)*
Nothing changes in the fab package; we simply **do not buy the ~$8 part** (×N boards) and
**do not populate it**. Keeps the licensed-future option **and** the pre-regulator branch,
with **no re-spin**. This is what ADR-070's DNP-by-default already permits — it just makes the intent
explicit.

**Option C — remove `U2` and shrink the board.** Recovers ~598 mm² and possibly the
outline. **Requires a re-route** and re-verification (DRC, seat, floor). **Highest risk, and
it invalidates the routed board we just verified as 48/48 JLC-legal.**

**Recommendation: Option B now; defer C until after the first flight.** A DNP site costs
nothing at order time, keeps the licensed option open at zero engineering cost, and **avoids
re-spinning a board that is already fully routed and fab-legal.** If the flight programme
decides the licence route is permanently closed, **Option C becomes a clean 598 mm² reclaim
for a future revision** — with no urgency now.

## 6. Where the saving actually is, today

- **Parts:** the F33 module **~$8/board** (per `docs/DUAL-VARIANT-DESIGN.md`, LCSC
  ⛔ **`C5913567` DOES NOT EXIST** — verified live 2026-10-14; the real 433 MHz code is **`C53243927` at $21.8467, 2.7× our ~$8 assumption**). **Build only what we can fly: 1–2 units, not all 10.**
- **Do NOT order** the F33 for boards that will not be flown § — and ⛔ **`C5913567` is NOT a real code**: the 433 MHz part is **`C53243927`, $21.8467** (so buying 1–2 instead of 10 saves **~$175–196**, not the ~$64–72 the wrong price implied)
  before ordering, since that record is marked *"(check)"*.
- **Do NOT remove the footprint yet** — that is Option C, and it costs a re-route.

## 7. Reproduce

```
cd tracker/hardware
~/venvs/kicad/bin/python measure_f33_cost.py hub_board_v9.kicad_pcb
# U2 39.65x26.20 = 1038.8 mm2 / U3 21.81x20.20 = 440.6 mm2 / delta 598.3 mm2
```
