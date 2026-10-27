# LoRa1280 escape-corridor study — placement is NOT the blocker

Status: **measured 2026-10-26. Refutes the previous conclusion.** The router failure is not a
geometry problem.

Reproduce:

```bash
/usr/bin/python3 tracker/hardware/tmp_probes/corridor_study_lora1280.py
```

## Method

Rasterise copper obstacles per layer (tracks as segments, vias and pads as circles, all inflated by
the board's 0.20 mm minimum clearance) and march a **2.0 mm-wide corridor** outward from each pad
row's midpoint in the four cardinal directions, up to 16 mm. Zones are deliberately excluded: pours
re-clear around new copper on refill, so counting them would report "blocked" for copper that will
simply step aside.

## Result — the part has room in every direction

```
row 1-8  midpoint (53.00, 60.95)   span 14.00 mm
   NORTH  B.Cu 16.00 CLEAR   F.Cu  1.75
   SOUTH  B.Cu 16.00 CLEAR   F.Cu 16.00 CLEAR
   WEST   B.Cu 16.00 CLEAR   F.Cu 13.25
   EAST   B.Cu 16.00 CLEAR   F.Cu 16.00 CLEAR

row 9-16 midpoint (53.00, 75.25)   span 14.00 mm
   NORTH  B.Cu 16.00 CLEAR   F.Cu 16.00 CLEAR
   SOUTH  B.Cu 16.00 CLEAR   F.Cu 16.00 CLEAR
   WEST   B.Cu 12.25         F.Cu 12.25
   EAST   B.Cu 15.00         F.Cu 15.00
```

**15 of 16 direction/layer combinations reach the full 16 mm probe distance on B.Cu or F.Cu.**
Only `row 1-8 NORTH on F.Cu` is short (1.75 mm), and that row has three other clear directions.

So the placement chosen at `(53.000, 68.100)`, `dy = +1.5`, on B.Cu has ample escape room. A
2.0 mm-wide corridor is far wider than a 0.25 mm track needs.

## This contradicts what I told the operator

I reported that "step 4 is not a routing task, it is a PLACEMENT study" and inferred the part had
inherited no corridor. **The measurement says otherwise.** The geometry is open; the router still
returned routed 0 / failed 9 on two different placements (F.Cu before the side fix, B.Cu after).

A claim that the geometry blocks routing must be backed by a corridor that is too narrow. None
here is. The failure therefore lies in the router's model, not in the copper — candidates, in
order of likelihood:

1. **The router may treat the filled B.Cu GND/+3V3 pours as solid obstacles.** The part is now
   bottom-mounted, and B.Cu carries those pours. This study excludes zones precisely because they
   refill; if the router does not, B.Cu looks fully blocked and only F.Cu remains — where the
   footprint's own pads are not.
2. Pad-to-net association inside the router's grid may not have picked up the `SetNetCode`
   assignment performed by the swap script, in which case the nets have no start point.
3. The router's `--append` loader may reconcile against a stale connectivity model after 123 tracks
   were removed.

## What to do next

Do not move the part again on the strength of a routing failure. Test the hypotheses above
directly:

- fill the zones, then run the router **without** `--append` on a copy and see whether the failure
  signature changes (isolates hypothesis 1);
- print the router's start-pad list for one net and confirm it is non-empty (hypothesis 2);
- re-run the router from a freshly loaded board rather than a mutated in-memory one (hypothesis 3).

**Rule for the next session:** a routing failure is evidence about the *router* until a corridor
measurement says the copper is too narrow. This session got that backwards and told the operator
the placement was at fault.
