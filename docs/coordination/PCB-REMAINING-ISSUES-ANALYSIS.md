# PCB Remaining Issues Analysis

**Date:** 2026-08-05
**Author:** Orchestrator (direct DRC analysis)

---

## ROOT CAUSE: Power Net Completion Failure

Both boards have the SAME root cause: **3V3 and GND multi-pin nets are incompletely routed.**

The A* router handles 1:1 signal connections well but fails on multi-pin power nets. Every IC needs 3V3 and GND — that's 6+ pads on 3V3, 6+ pads on GND. The router connects SOME pads but misses others.

### V1-FAST A* (43 unconnected)
- ALL 43 items are missing 3V3 and GND connections
- Components affected: U3 (GPS), C2, U4, U2 (LR2021), U1 (RP2040), FEM
- SHORT: LR2021_DIO9 shorted to SPI_SCK (routing error)
- solder_mask_bridge between different nets

### V2-ADC A* (19 unconnected)
- ALL 19 items are missing 3V3 and GND connections
- Tracks exist (tiny: 0.07mm, 0.05mm) but don't reach all pads
- 2 track_dangling (tracks with unconnected ends)

### V2 Freerouted (20 unconnected)  
- Nearly identical to A* — same power net gaps
- Freerouting did NOT do better than A* on power nets

## ROOT CAUSE DEEP DIVE

The A* router routes net-by-net, treating each pad-to-pad connection independently. For multi-pin nets like 3V3 (6+ pads) and GND (6+ pads), it creates separate routes but misses connections because:

1. Each route is a point-to-point path — no concept of "bus" or "star" topology
2. No copper pour for GND (plan explicitly said "no pours" to avoid shorts)
3. Power nets need a different routing strategy than signal nets
4. Grid resolution may be too coarse to hit pad centers exactly

## RESOLUTION: Copper Pour + Power Bus

The fix is to add a GND copper pour on B.Cu and route 3V3 as an explicit bus (star topology). This is standard 2-layer PCB practice.

### Recommended Path: Hybrid Power Routing + Freerouting for Signals

1. Add GND copper pour on B.Cu (bottom layer) — connects ALL GND pads automatically
2. Route 3V3 explicitly as a bus connecting all VCC pads
3. Re-run DRC — power net violations should drop to 0
4. Fix the LR2021_DIO9/SPI_SCK short on V1 (remove conflicting track)
5. Re-export gerbers

### Estimated Time: 1-2 hours per board

## WORKER INSTRUCTIONS

See: Direct delegate_task dispatched to worker-balloon
