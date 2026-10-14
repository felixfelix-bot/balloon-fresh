# DECISION PACKAGE — the five `TODO(unverified)` parts

**Date:** 2026-10-14 · **Status:** for operator decision. Nothing frozen, nothing ordered.
**Sources:** `~/PART-SELECTION-U-CUT.md` (607 lines), `~/PART-SELECTION-U-HUB-CVT.md` (328 lines).
Every LCSC number and price below was read from JLCPCB's **live parts API**, not memory.

---

## 0. The finding that matters most (U_CUT): the symbol is 3-PIN and CANNOT satisfy the ADR

**MEASURED from the committed netlist** (`tracker/hardware/schematics/flight_board/v9_flight.net:581`):

```
libsource (lib "balloon_flight_v9") (part "CUT_CHANNEL")
  pin 1 = VSCAP   (raw supercap node, post-BAT54, PRE-LDO)
  pin 2 = GND
  pin 3 = CUT_W   (the wing's RF_FEED land → /CUT_SENSE_W<n>)
```

And its **own description field** says:

> *"THE DRIVE MUST BE A LATCHED ONE-SHOT: cutting is irreversible and a
> level-sensitive driver can re-fire on a reset, a brown-out, a firmware retry or a
> floating gate (ADR-051 §2.5.1)."*

**A 3-pin block has no GPIO, no clock, no data and no arm line.** There is nothing to
latch *from* and nothing to arm *with*. So the ADR's requirement **cannot be met by
choosing a part for this symbol** — the symbol itself must grow. The consultant's
recommendation therefore carries `+4 nets and ~4–8 added pads per channel`.

**Any option that "fits the current 3-pin symbol" is, by construction, a bare
MOSFET — and the ADR explicitly excludes that.** This is worth stating plainly
because it means the part choice is *downstream* of a schematic change.

## 1. `U_CUT1–4` — recommended: the COLD-RATED SET

The consultant found a second, decisive problem: **every candidate must survive
−55 °C** (ADR-043's flight profile is −40 to −55 °C), and **most logic families are
only rated to −40 °C.**

| Ref | Part | LCSC | Package | $ q10 | Temp | Note |
|---|---|---|---|---:|---|
| `U_CUT1/2` | **2× onsemi MC74VHC74DTR2G** | **C464023** | TSSOP-14 | **$0.2062** | **−55…+125 °C** | dual D-FF → 2 latches each, so 2 parts give 4 channels' latches |
| `U_AND1–4` | **4× onsemi NL17SZ08DFT2G** | **C150234** | SOT-353 | **$0.0461** | **−55…+125 °C** | 2-input AND = arm/fire merge; **all gated by one shared `ARM_RAW`** |
| `Q_CUT1–4` | **AO3400A** | **C20917** | SOT-23 | **$0.0891** | — | JLC **Basic** (no feeder fee) |
| — | 8× 0402 100k | C25741 | 0402 | Basic | — | defined-low on D/CLK **and** gate-hold |
| — | 4× BAT54W | C699107 | SOD-323 | — | — | flyback clamps |

**Totals:** **$1.1112/board @q10**, $0.9202 @q100. **7 packages / 25 placements**,
**~142 mm² ≈ 3.9 % of a 70×70 board**; the **delta vs a bare-MOSFET baseline is only
~39 mm² ≈ 1.1 %.**

**Three design points that are the real substance:**

1. **The shared `ARM_RAW` line IS the cheap hardware non-overlap interlock.** All four
   AND gates are gated by one arm line, so no two channels can fire without the arm
   sequence — the ADR's "hardware series gate requiring an explicit arming sequence",
   obtained for the cost of an AND gate.
2. **The gate-hold resistor is the actual floating-gate re-fire defence** — not the
   latch alone.
3. **ALL LOGIC ON THE 3.3 V RAIL, NOT `VSCAP`.** This is a genuine engineering catch:
   at `VSCAP` = 5.4 V, every CMOS/VHC/LVC/74HC family has `V_IH = 0.7 × VCC = 3.78 V`,
   which **a 3.3 V ESP32 GPIO cannot drive**. Only 74AHCT (`V_IH` = 2.0 V fixed) runs
   from ~5 V — but it is **4.5–5.5 V-only on a rail that sags to 3.0 V**, which is
   worse. So the latch must be 3.3 V-powered while the *load* stays on `VSCAP`.

**Hardware latch vs a firmware NVS "fired" flag — worth it, and nearly free:** the
4-pin signal path adds only **~39 mm²**, and the set is **cheaper than the ADR's own
unlatched incumbent** (`IRLML2502TRPbF`, LCSC **C2589**, $0.3911 @q10).

**Two supply risks, flagged honestly:**
- **`C464023` stock is down to 55 units** (20 needed for a 10-board run) — **covers one
  run, reel nearly dry.** Cold-rated substitute: **`C604209`** (`NLV17SZ74USG`,
  AEC-Q100, stock 3000, $0.5058 @q10).
- **`C893416`** (cold shared 3-input gate) at **206** — thin.

## 2. `U_HUB_CVT` — recommended: **TI `BQ25504RGTR`**, LCSC **C2876746**

VQFN-16-EP 3 × 3 mm, **$4.0881 @q10** / $3.4650 @q100, **Iq 330 nA typ**, JLCPCB
Extended library.

**Why:** it is the **only class member that cold-starts** at the hub string's
**~0.6–1.0 V** input, **and** it passes ADR-050 §3.6's night Iq budget by **10×**
(330 nA × 5.4 V = **1.8 µW = 1.8 %** of ADR-036's 100 µW anchor). It is also the
cheapest/smallest sub-µA harvester in stock.

- Second choice: **BQ25570RGRR `C506250`** (Iq 488 nA, stock 333, 0.5 mm/side larger, has an unneeded second buck).
- Fallback only if the array is resized to ≥4 cells: **TPS63900DSKR `C1518762`** (buck-boost, 75 nA, $0.9739 @q10).
- **Do NOT change `TPS62162` or the LDO.**

**The consultant also corrected our own ADR:** it **flags with numbers that the
"sub-µA harvester" premise is wrong for 0.388 W average.** That is a useful
contradiction of our premise, not a part problem.

**Open item O-1, recorded not invented:** ADR-051 §2.2 says the output lands in *"the
bank"*, but the **exact output net is not in the netlist** — `VSCAP` was inferred, so
the output node must be **decided**.

## 3. What I recommend you decide

1. **`U_CUT`:** adopt the **cold-rated set**; accept that it requires a **schematic
   symbol change** from 3 pins to ~7 (the ADR cannot be satisfied otherwise).
2. **`U_HUB_CVT`:** adopt **BQ25504RGTR (C2876746)**; and **re-examine the sub-µA
   premise** against 0.388 W, since the consultant says it does not hold.
3. **Supply:** decide whether to buy the thin-stock parts now (`C464023` 55 units) or
   pre-emptively switch to the AEC-Q100 substitute.

## 4. UNVERIFIED, stated as such

- JLC's **per-unique-part feeder fee** could not be found anywhere → quoted per-board
  costs are **PARTS ONLY**.
- The **GPIO/expander requirement** triggered by the ~17 new nets is **identified but
  deliberately not costed** — and this interacts with `OPEN-17`/`OPEN-25`, which
  already showed the S3 has **no free ADC pin**. Adding GPIO demand makes that tighter.
- **ADP5091 / SPV1040 / LTC3106** Iq values are **LCSC attributes only** (analog.com
  and st.com were unreachable from the sandbox).
- **Every candidate is rated only to −40 °C** in the `U_HUB_CVT` set, while the flight
  profile is **−40 to −55 °C** (ADR-043 gate) — a real open item.
