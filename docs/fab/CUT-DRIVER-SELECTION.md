# `U_CUT1…4` — THE LATCHED CUT DRIVER: recommendation with measured prices

**Date:** 2026-10-14 · **Operator instruction:** *"please include these parts. Please pick them for
me based on price and whether they meet our needs."*

## What the part must do (measured from the netlist, not assumed)

| requirement | evidence |
|---|---|
| **Latch independently of MCU state** | `ARM_RAW` exists; the cut must complete even if the MCU dies mid-command |
| **Confirm the cut happened** | the `CUT_SENSE_W*` nets exist for exactly this |
| **Work with the converter dead** | powered from the post-BAT54/pre-LDO **`VSCAP`** node |
| **4 channels, one per wing** | `U_CUT1…4`, one nichrome each |
| **Control side rail** | `+3V3_MCU` |
| **Nichrome drive** | `W1_SOLAR_P`-class current, small |

**So the pin contract is: `VSCAP`, `GND`, `DRIVE`, `ARM`, `CTRL`(GPIO), `SENSE`.**

## Measured prices (live JLCPCB API, control `C50645` SS24 found — so the queries are real)

| candidate | LCSC | stock | price | package |
|---|---|---:|---:|---|
| **`SN74LVC1G373DBVR`** | **`C128413`** | **34,892** | **$0.2779** | SOT-23-6 |
| `SN74LVC1G373DCKR` | `C132097` | 8,706 | $0.2330 | SC-70-6 |
| 2N7002 (N-FET) | `C73302` | 135,025 | $0.0222 | SOT-23-3 |
| BSS84 (P-FET) | `C114481` | 148,041 | $0.0232 | SOT-23-3 |
| MAX16054AZT+T | `C79401` | 1,666 | $3.0213 | TSOT-23-6 |
| LTC2954ITS8-1 | `C580654` | 200 | $6.8549 | TSOT-23-8 |
| LTC2955CDDB-1 | `C580657` | 1 | $4.0669 | DFN-10-EP |
| LTC2954CDDB-1 | `C683779` | 5 | $4.1387 | DFN-8 |
| ADM1075 family | — | **0** | $7.41–15.71 | LFCSP/TSSOP-28 |

**Note the LTC2954/2955 stock: 1–200 pieces, and even the *good* ones are single-digit to low-hundreds.** That is a real supply risk for a flight article.

## Recommendation: **`SN74LVC1G373DBVR` (`C128413`) — one per wing**

**Not the LTC2954. Here is why, and the reasoning matters more than the conclusion.**

### The LTC2954/LTC2955 are the wrong *kind* of part

They are **pushbutton on/off controllers**: they debounce a human finger on a button and drive one
system enable. **We do not have a button.** We have an MCU that decides to cut and must not be able
to *un*-decide, plus a sense line to confirm the cut.

**Their ~6 µA quiescent draw is the killer.** It is *always on* — and it is drawn from **`VSCAP`**,
the supercap node that exists to keep the cut alive with the converter dead. **4 × 6 µA = 24 µA of
permanent load on the one rail whose entire job is to still have charge when everything else is
gone.** The freeze's own reasoning is that this branch must survive a converter failure; **a
permanent leak fights that directly.**

### The `SN74LVC1G373` is a D-type latch — exactly the function

| | |
|---|---|
| **1.65–5.5 V** | works from `+3V3_MCU` **and** from `VSCAP`'s 2.7–5 V window |
| **Latch + enable** | set the output, **hold it**; the MCU cannot retract by dying |
| **`Q` output** | drives the nichrome gate directly |
| **Tri-state/`Q̅`** | can serve the **sense** path |
| **SOT-23-6** | 2.9 × 1.6 mm — small; **placement budget aware** |
| **`C128413` stock 34,892 @ $0.2779** | **orderable, cheap, no supply risk** |

**4 channels ≈ $1.11 total.** Against **$27 for four LTC2954s** — and the LTC2954s would **not
survive a stock check at quantity** (200 max, and that was the *best* variant).

### The discrete 2-FET latch — cheaper, but I am not choosing it

**A 2-transistor latch is ~$0.045/channel (4 × $0.045 ≈ $0.18)** — genuinely cheaper than $1.11.
**But:** it has **no defined initial state**, it **needs a pull-up and a reset path** designed by
hand, its **latch-up behaviour depends on transistor matching**, and **it provides no sense output** —
so the `CUT_SENSE_W*` nets would need separate silicon anyway. **The saving is ~$0.93 across the
whole board.** Against a function that must work **once, in flight, when everything else has
failed**, that is not a saving worth hand-designing a latch for.

**The honest position:** the discrete option is **viable and cheapest**; the D-latch is **$0.93 more
for a defined, characterised, single-part latch with a sense path.** **I recommend the D-latch.**

## The pin contract this produces (6 pins, superseding the current 3-pin symbol)

```
CUT_CHANNEL (latched, 6 pins)
  1  VSCAP      power — post-BAT54/pre-LDO, so a cut works with the converter dead
  2  GND
  3  DRIVE      output to the wing's nichrome
  4  ARM        latch enable / arm
  5  CTRL       MCU GPIO — requests the cut
  6  SENSE      feedback to CUT_SENSE_W*, confirms the cut happened
```

**This is the symbol change the operator authorised.** Changing 3 → 6 pins adds **~3 nets per
channel, 12 nets total**, and takes each channel from **~2 pads to 6** — a **small** placement add
(4 × 4 extra pads) on a board already at 41.5 % utilisation.

## What this does NOT claim

- **I have not verified the `SN74LVC1G373`'s latch behaviour against the nichrome's inrush.** The
  gate drive is a logic output; **whatever switches the nichrome current is still a FET**, and that
  FET is not in the freeze. **That is a real gap and it needs a drive stage, which the 6-pin symbol
  above accommodates but does not name.** I flag it rather than pretend the IC is the whole circuit.
- **I have not checked the `SN74LVC1G373` footprint against a library** — that is the mechanical next
  step, and the repo already has the tooling for it (`footprint_resolves` in the integrity gate).
