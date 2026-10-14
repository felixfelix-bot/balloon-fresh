# HUB BOARD — the last unrouted net, and what it would take

**Date:** 2026-10-14 · **State:** hub board at 44/44 placed, **1 net unrouted**, **30 edge-delta
errors**, zero other real errors.

## Progress this pass, all measured

| metric | before | now |
|---|---:|---:|
| placed components | 39 (5 missing) | **44** |
| unconnected items | 5 | **1** |
| `starved_thermal` | 3 | **0** |
| `drill_out_of_range` | 12 | **0** |
| `copper_edge_clearance` | 28 | 30 (the two new GND vias join the same documented delta) |
| single-ended routed (first pass) | 33/35 | 49/50 |

## The remaining net: `/SX1280_DIO1`

The router **partially** routed it. Reported as `Pad 10 [U4] on F.Cu` — `Track on In2.Cu, length 1.0`
unconnected.

**What exists** (from the board, not the log):

```
U1.33 (67.450,11.840)  --F.Cu 0.2830-->  via (66.500,12.000)
                       --In2.Cu 3.3941--> (64.100,14.400)
                       --In2.Cu 1.0000--> via (64.100,15.400)     <-- STOPS HERE
U4.10 (52.500,28.200)  -- nothing
```

**So ~15 mm is missing**, from the via at `(64.100, 15.400)` to the pad at `(52.500, 28.200)`.

## Why the router cannot close it

`/SX1280_DIO1` joins **U1** (ESP32-S3, centre x 58.7) and **U4** (SX1280, centre x 52.25). **11 nets
touch both parts:**

```
+3V3, /SX1280_ANT_SW, /SX1280_BUSY, /SX1280_CS_N, /SX1280_DIO1,
/SX1280_DIO2, /SX1280_DIO3, /SX1280_MISO, /SX1280_MOSI, /SX1280_RESET_N, /SX1280_SCK
```

**Eleven nets must cross the same channel between two adjacent parts.** The channel is **bounded on
the left by U2's (F33) courtyard, which reaches x = 46.670.** So all 11 share a corridor roughly
x 47…70 — and because U1's courtyard reaches x = 47.099, the *effective* channel is narrow.

**Measured escapes:** DIO2 and DIO3 both reach U4 from **below** (`B.Cu` up to y ≈ 28.8 then `F.Cu`
into the pad). DIO1 is the last one through that approach and there is no room left beside DIO2's
corridor at the same y.

**`In2.Cu` is the deep layer and is heavily used** — measured 30 nets routed on it in the region
x 44–60, y 8–32, including `+3V3` (27 segments), `/VSCAP` (14), `/F33_VCC` (11). It is a maze, not a
wall: 812 of 1536 cells free. But a maze is exactly what a greedy net-at-a-time router fails on when
it reaches the 11th net.

## Attempts made, all at the frozen floor, all honest

| approach | result |
|---|---|
| full board route, `--escalation off` | 49/50, MISO failed |
| `--nets /SX1280_MISO --rip-existing-nets` | **0/1 routed** |
| group 6 SPI nets ripped together | MISO routed; **DIO1 broke** |
| group DIO1+DIO2+DIO3 | **0/1**, DIO1 failed |
| `--guide-corridor --guide-corridor-layer F.Cu` | **0/1**, DIO1 failed |

## The structural fix

**The 11-net U1↔U4 channel is a placement problem, not a routing problem.** The same conclusion the
base station reached: *the long nets are long because the parts are at opposite ends.* Here it is
worse — the parts are already adjacent, so it is a **channel capacity** problem.

Two real options, both placement changes rather than hand routing:

1. **Move U4 away from U1** to open the channel. The F33 (U2) courtyard at x ≤ 46.670 and U1 at
   x ≥ 47.099 leave almost no slack, so U4 would have to move **outside** the U1/U2 pair — e.g. below
   U1 with a clear approach from a different quadrant, turning 11 crossings into 2 directions.
2. **Re-order U4's pin escape** so its SPI/DIO groups exit on the side facing U1 rather than all
   needing to cross under U1 — a footprint/symbol-level change, not a routing one.

**Both are beyond a hand route.** A hand route would have to weave four occupied layers across a
15 mm channel against 11 nets of existing traffic, and the earlier hand-route attempt on the base
station **made things worse** (829 violations vs 770, closing only 5 of 18 nets). **I am not
repeating that experiment here** — the evidence says a naive hand route on a congested channel adds
defects.

## Honest status

The hub board is **not orderable**: 1 unrouted net and 30 edge-delta items. The 30 are a
**documented delta** with a physical justification (edge-launched wing sockets, ADR-046/048) that
**cannot be expressed as a scoped rule** in KiCad's condition language — measured with controls in
`docs/fab/EDGE-RULE-INERT-FINDING.md`.

**Every other defect class is closed and gated.** The remaining work is one placement decision, not
more routing attempts.
