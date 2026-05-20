# Mesh Stack - AI Agent Instructions

## Overview
Multi-balloon mesh relay network for internet transport. Balloons at ~12 km altitude relay UDP traffic between ground stations using LR2021 (2.4 GHz + Sub-GHz).

## Key Constraints
- **Not Starlink**: Realistic targets 1-130 kbps per link, 4-520 kbps aggregated
- **UDP not TCP**: RTT too high for TCP congestion control
- **Erasure coding (Wirehair)**: Eliminates per-packet ACKs, works with 30-37% packet loss
- **Balloon = natural TDMA coordinator**: Visible to all ground stations, GS can't see each other

## Architecture Layers
1. **Physical**: LR2021 (LoRa/FLRC) + SKY66112 FEM + wire dipole
2. **Link**: TDMA frames with per-slot adaptive TX power/modulation
3. **Network**: Erasure-coded blocks, multi-path routing
4. **Transport**: UDP tunnel to ground station ( Wirehair → UDP → internet)
5. **MultiWAN**: Bond 4 balloon links for aggregate throughput

## Performance Targets

### V1 (Mesh V1, ~14g, night-off)
- 2.4 GHz @ +22 dBm: 22 kbps @ 300 km
- Net throughput ~40% of air rate: ~9 kbps per link
- 4x MultiWAN: ~36 kbps @ 300 km
- Avg power: ~167 mW (adaptive TX), night-off default

### V2 (Mesh V2, ~18-22g, night-active)
- 2.4 GHz @ +30 dBm with PCB Yagis: 38-87 kbps @ 300 km
- 4x MultiWAN: ~150-350 kbps @ 300 km
- Avg power: ~431 mW, night-active with larger caps

## Key Files
- `mesh-stack/ROADMAP.md` — Full plan, link budgets, power analysis, research checklist
- `docs/adr/009-antenna-strategy-v1-v2.md` — V1 omni + V2 directional decision
- `docs/adr/010-adaptive-tx-power.md` — Adaptive TX per TDMA slot
- `docs/power-budget.md` — Tracker + mesh relay power scenarios
- `docs/antenna-strategy.md` — Full antenna comparison + product research

## Research Repos (to study)
- Wirehair: `https://github.com/catid/wirehair` — fountain code
- Shorthair: `https://github.com/catid/shorthair` — streaming variant
- ts-lora: `https://github.com/deltazita/ts-lora` — TDMA frame structure
- LoRaMesher: `https://github.com/LoRaMesher/LoRaMesher` — mesh superframes
- LoraRangingTest: `https://github.com/yplam/LoraRangingTest` — ranging
- ublox: `https://github.com/u-blox/ublox-GNSS-Arduino-Library` — GPS PPS

## Current Status
- Link budget analysis complete (50-500 km, both bands)
- Throughput analysis complete (V1 + V2 + MultiWAN)
- Power budget complete (tracker + mesh relay scenarios)
- Antenna strategy decided (V1 omni, V2 directional)
- Night-off design complete
- ADR-009, ADR-010, ADR-011 written
- First flight planned: single Yokohama 32" + He 4.6, Minimal variant (ADR-011)
- Multi-balloon research added as Phase 5 (see ROADMAP.md)
- **Not started**: Protocol implementation, TDMA firmware, erasure coding integration

## Night-Off Default
Balloons sleep at night. Ground stations estimate position from wind data.
Multiple balloons at different longitudes provide 24h coverage.
Configurable night-active mode with larger caps for special missions.
Same PCB, different component population.
