# BASE-STATION ROUTING — the honest state: my hand routes were WORSE, and the 699 "violations" are mostly unrefilled zones

**Date:** 2026-10-14 · **Operator approved hand-routing the 18 open nets.** This records what
happened, measured, including that **my first hand-routing attempt made the board worse.**

## What the three escalation settings actually produce (all measured)

| setting | min track | routed | `--strict-sizes` | verdict |
|---|---:|---|---|---|
| `off` | **0.200** | **17/35** | — | clean copper, 18 nets open |
| `board` | **0.0889** | 31/35 | **exit 3, 125 features below request** | sub-floor |
| `fab` (first pass) | **0.0889** | 33/35 | — + **relaxed 4 project floors** | rejected |

**There is no setting that yields both clean copper AND complete routing.** The operator's ruling —
prefer clean copper, hand-route the rest — therefore stands. **But:**

## My hand-routing attempt was worse than doing nothing, and I am not shipping it

I added 5 straight-line routes at 0.2 mm. Measured before/after with `kicad-cli pcb drc`:

| | violations | unconnected |
|---|---:|---:|
| **strict route (before my change)** | **770** | **18** |
| **after my 5 hand routes** | **829** | **13** |

**My change added 59 violations and closed only 5 nets.** The new violations are mine:

- **`solder_mask_bridge` 41** — e.g. `Track [QSPI_SS] length 56.85 mm` bridging `Pad 34 [USB_DP]`,
  `Pad 35 [GND]`, and `PTH pad 1 [VIN_GS]`. **A 56.85 mm straight line across the whole board** is
  not a route; it is a line drawn through the package.
- **`shorting_items` 12** — e.g. `Track [VGA_GAIN1] length 45.6 mm` shorting a `Via [GND]`.

**The cause is my method, not the idea.** The routed nets were cleared, so I connected the remaining
pairs with **straight lines** — `PAD-to-PAD` runs of **56.85, 45.63, 45.2 mm** that cross the MCU's
own pads, `J_PWR`, and every GND via between them. **That is precisely the mistake `--escalation off`
was protecting against: the router refuses to complete them because they are NOT TRIVIALLY ROUTABLE
— they need layer changes and corridor planning, which is the router's job, not a straight line's.**

**So the 5 "hand routes" are REVERTED.** `bs_v1_routed_hand.kicad_pcb` is kept only as evidence.

## The 500 clearance + 199 hole violations are MOSTLY NOT REAL — and I nearly mis-graded them

**Measured composition of the 699:**

| pair type | count |
|---|---:|
| **track + ZONE** | **311** |
| **via + ZONE** | **189** |
| pad + pad | 0 |
| via + zone hole clearance | 199 |

**Every one is copper against the GND ZONES.** These zones have **never been refilled** — and filed
zones fire DRC against copper that the actual fill would clear. **This is the known
fill-then-recheck issue, not a routing defect.**

**So the honest procedure is: REFILL THE ZONES, THEN GRADE.** I have not done that yet, and **grading
before the refill would have produced exactly the false verdict this campaign has already made
once** — the broken CPL checker that reported MISMATCH.

**Worth stating plainly: I nearly reported "699 real DRC violations" as a finding.** They are 699
entries produced **before the step that makes them meaningful.**

## The genuinely hard nets, named

| net | connection | length |
|---|---|---|
| `XIN`, `XOUT` | `U_MCU` 24/25 ↔ `Y1` 1/3 (12 MHz crystal) | **5.17 / 3.91 mm** — short, needs care |
| `QSPI_SS` | `U_MCU` 10 ↔ `U_FLASH` 1 | **56.85 mm** across the board |
| `VGA_GAIN1/2` | `U_MCU` 19/20 ↔ `U_VGA` 7/8 | **45.6 / 45.2 mm** across the board |

**`XIN`/`XOUT` are the ones worth hand-routing** — 5.17 and 3.91 mm, local, and crystal stub length
matters for clock integrity. **The other three are long haul runs** and belong to the router.

**And note a placement consequence I found by measuring:** `U_MCU` sits at x ≈ 2.6–7.4 mm and
`U_FLASH` at x = 59.27 mm, `U_VGA` at x ≈ 50.55 mm. **`QSPI_SS` and the VGA gain lines are long
because the parts are at opposite ends of the board.** That is a **floorplan** observation, not a
routing one — **moving `U_FLASH` and `U_VGA` closer to `U_MCU` would shorten three nets at once**,
and on a 55 × 40 board we have 58.5 % area free.

## Honest state

**The base-station route is NOT complete and I am not claiming otherwise.** What exists:

- **`bs_v1_routed_strict.kicad_pcb`** — clean copper at the frozen floor (min track 0.200, via 0.600,
  drill 0.300), **17/35 nets routed (18 open)**. **This is the honest best artifact so far.**
- All three escalation variants are kept with their measured minima, so the trade is auditable.

**Next, in order:** (1) **refill zones and re-grade** — the real violation count is unknown until
then; (2) **move `U_FLASH`/`U_VGA` nearer `U_MCU`** to shorten three of the open nets; (3) re-route
with `--escalation off`; (4) hand-route only `XIN`/`XOUT`, with a proper 2-segment path and layer
change if needed; (5) then DRC → classify → refill → export.
