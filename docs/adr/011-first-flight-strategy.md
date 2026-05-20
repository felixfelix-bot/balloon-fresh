# ADR 011: First Flight Strategy — Single Balloon, Helium, Minimal Variant

## Status

Accepted

## Context

We are ready to transition from design/documentation to hands-on hardware assembly and first flight. Several interrelated decisions need to be made simultaneously:

### Balloon Configuration

The pico ballooning community has 80+ documented flights from 6+ practitioners. All successful long-duration flights (30+ days) used a **single Yokohama balloon** filled with hydrogen or ultra-pure helium.

Multi-balloon + cut-down configurations offer theoretical redundancy but have **zero successful long-duration precedent** in the community. Jetstream winds at 40,000 ft (150+ km/h) cause tandem balloons to rub and abrade.

### Gas Choice

Ruthroff's data from 37 flights with Yokohama balloons:

| Gas | Purity | Flights | Circumnavigations | Rate |
|-----|--------|---------|-------------------|------|
| Party-store He | ~80% | 9 | 0 | **0%** |
| Ultra-pure He | 99.999% | 3 | 2 | **67%** |
| Hydrogen | ~99% | ~9 | 5 | **55%** |

Source: https://www.theastroimager.com/picoballoning/pico-ballooning/

Hydrogen provides ~8% more lift (1.10 g/L vs 1.02 g/L) and is cheaper, but:
- Cannot be handled indoors (explosive)
- Requires outdoor-only filling with anti-static precautions
- Requires left-hand thread regulator
- Transport restrictions (ADR hazardous goods)
- Static spark ignition risk

Industrial helium (grade 4.6 = 99.996% purity) from Linde/Air Liquide/Messer:
- Completely inert, zero explosion risk
- Can be handled indoors
- Standard right-hand thread regulator
- Higher circumnavigation rate in limited data (67% vs 55%)
- ~7% less lift than H2 (negligible with 32" Yokohama's 250g+ gross lift)
- More expensive per fill (~EUR 5-10 vs ~EUR 3)

### Payload Variant

| Variant | Weight | BMP280 | Notes |
|---------|--------|--------|--------|
| DIY v0.1 | ~15g | Yes (dev board) | Heavy but easy to assemble |
| Minimal | ~8-9g | No | Lightest, max free lift margin |
| Mittel | ~12-13g | Yes | Balanced |

The first flight's primary goal is **range and throughput characterization** across frequencies, not maximum altitude or duration. Horizontal position + temperature data from the radio module itself would already be valuable.

### First Flight Goals

1. Verify LoRa range at 868 MHz (ground test → short flight)
2. Characterize which modulation modes work at what distances
3. Validate power chain (solar → supercaps → LDO → radio)
4. Learn balloon preparation (stretching, sealing, free lift measurement)
5. Practice launch procedure

## Decision

### 1. Single Yokohama 32" Balloon (Valveless)

Use one Yokohama 32" Sphere Balloon per flight. **Order valveless version** (no self-sealing valve). No multi-balloon, no cut-down mechanism.

**Rationale:** Proven across 528-day flights. Multi-balloon adds complexity with no community precedent for success. Our 9-14g payload is well within the single-balloon capacity.

**Valveless choice:** Self-sealing valves are unreliable at altitude (Ruthroff: "The self-sealing nozzle may not self-seal" after deflation/refill cycle). Yokohama sells "no nozzle" versions specifically for pico-balloonists. We heat-seal the neck with an impulse sealer + Kapton tape instead — proven across all 37 Ruthroff flights.

**Multi-balloon research is deferred to mesh-stack Phase 5.** See `mesh-stack/ROADMAP.md`.

### 2. Industrial Helium 4.6 (Not Hydrogen)

Use industrial-grade helium (≥99.996% purity) from Air Liquide ALbee Fly system.

**Rationale:** Safety and convenience outweigh the 8% lift advantage of H2 for initial flights. He 4.6 has a higher circumnavigation rate (67%) than H2 (55%) in Ruthroff's data. Indoor filling allows careful free-lift measurement. The ALbee Fly system integrates the pressure reducer, avoiding separate regulator purchase.

**Gas procurement sequence:**
1. Use remaining Amazon He for DecoGlee shakedown tests (short flights)
2. Order ALbee Fly helium from Air Liquide for Yokohama flights
3. Consider switching to H2 in future if cost or flight duration demands it (requires ADR update)

**German sources for He 4.6:**
- Air Liquide ALbee Fly: https://www.airliquide.com/ (integrated regulator)
- Linde Gas Ballongas: https://www.linde-gas.de/
- Messer Group: https://www.messergroup.com/
- Hornbach/Bauhaus exchange cylinders (Messer/Linde, ≥98%)

### 3. Minimal Variant (~9g) for First Flight

Start with the Minimal variant (no BMP280, no FEM, wire dipole only).

**Rationale:** The first flight goal is range/throughput characterization, not altitude logging. The 9g weight maximizes free lift margin for learning. Horizontal position from WSPR/LoRa reception + radio temperature is sufficient for range estimation. BMP280 can be added in Mittel variant for subsequent flights.

### 4. Yokohama 32" Sphere Balloon 10-Pack (Valveless, Crystal Clear)

Order the 10-pack Crystal Clear variant from https://www.yokohamaballoon.com/ (€105.95).

**Rationale:** €10.60/flight is the cheapest component. 10-pack allows iterative learning across multiple launches. Crystal Clear absorbs less solar IR than colored variants, helping maintain stable internal pressure. Valveless version avoids unreliable self-sealing valves.

**Material note:** Yokohama balloons are Nylon/PE laminate (NOT metalized foil/Mylar). Despite foil having better theoretical gas barrier properties, nylon/PE vastly outperforms in practice due to stretchability, thermal cycling tolerance, and superior seam construction. See `docs/balloon-options-analysis.md` for material comparison.

## Consequences

### Immediate
- Order: Yokohama 32" 10-pack (€96.95) + ALbee Fly He (TBD) + heat sealer (~€15) + Kapton tape (~€5)
- Build: Minimal variant tracker on protoboard with ESP32-C3_Mini_V1 + LoRa2021
- Test: Range test on ground first, then DecoGlee short flight, then Yokohama flight

### Deferred
- Multi-balloon research → mesh-stack Phase 5 (see `mesh-stack/ROADMAP.md`)
- Hydrogen consideration → future ADR if needed
- BMP280 altitude logging → Mittel variant for second flight
- FEM + directional antennas → V2 upgrade path

### Cost Summary

| Item | Cost |
|------|------|
| Yokohama 32" Crystal Clear 10-pack (valveless) | €105.95 |
| ALbee Fly helium | ~€30-50 |
| Heat sealer (impulse) | ~€15 |
| Kapton tape | ~€5 |
| BMP280 + supercaps + passives + wire | ~€12 |
| **Total to first flight** | **~€175-195** |

## Key References

- Ruthroff (37 flights): https://www.theastroimager.com/picoballoning/pico-ballooning/
- KI4MCW (31 flights): https://sites.google.com/site/ki4mcw/Home/pico-balloonery
- K9YO beginner guide: https://sites.google.com/view/picoballoonsbyk9yo/beginners-guide
- Yokohama Balloon shop: https://www.yokohamaballoon.com/
- Air Liquide ALbee: https://www.airliquide.com/
- Balloon flight lessons: `docs/balloon-flight-lessons.md`
- Balloon options analysis: `docs/balloon-options-analysis.md`
- Balloon test results (DecoGlee): `docs/balloon-test-results.md`
