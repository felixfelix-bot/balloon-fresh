# ADR 010: Adaptive TX Power and Modulation per TDMA Slot

## Status
Accepted

## Context

In the mesh relay scenario, the balloon sits between ground stations at different distances:

```
GS1 (close, 50 km)  <--- Balloon (coordinator) --->  GS2 (far, 300 km)
```

The balloon relays internet traffic between them with approximately 50% RX and 50% TX duty cycle (worst case). Transmitting at full power (+22 dBm) to all stations wastes energy when the target is nearby.

The LR2021 supports on-the-fly changes to TX power and modulation mode. The balloon, as TDMA coordinator, knows the distance to each ground station (from RSSI of join requests or RTToF ranging).

## Decision

**TDMA coordinator assigns per-slot TX power and modulation based on link distance.**

| Station Distance | TX Power | Modulation | Air Rate | DC Current (TX) |
|-----------------|----------|-----------|----------|-----------------|
| < 50 km | +12 dBm | FLRC 1300k or SF7/1625 | 87-1300 kbps | ~30 mA |
| 50-100 km | +15 dBm | SF7/1625 | 87 kbps | ~50 mA |
| 100-200 km | +18 dBm | SF8/1625 | 38 kbps | ~80 mA |
| 200-300 km | +22 dBm | SF9/1625 | 22 kbps | ~150 mA |
| > 300 km | +22 dBm | SF10/1625 or SF9/125 | 1.7-12 kbps | ~150 mA |

The TDMA frame assigns different modulation modes and power levels to each slot:

```
TDMA Frame Example:
  Slot 1: RX from GS-A (50 km)
  Slot 2: TX to GS-B (300 km) at +22 dBm, SF9/1625 (22 kbps)
  Slot 3: RX from GS-B (300 km)
  Slot 4: TX to GS-A (50 km) at +12 dBm, SF7/1625 (87 kbps)
  Slot 5: Contention window (new stations, SF12 max range)
  Slot 6: Balloon telemetry broadcast (SF9/125, 1.7 kbps)
```

### Power Budget Impact

| Design | Avg Power (50/50 relay) | 12-Cell Solar Margin |
|--------|------------------------|---------------------|
| Fixed +22 dBm | ~265 mW | +215 mW (45%) |
| **Adaptive TX** | **~167 mW** | **+313 mW (65%)** |
| Power savings | **38%** | — |

### Asymmetric Throughput

Close stations get higher throughput because the balloon uses higher-rate modulation:

```
Close GS (50 km):  87 kbps air → ~37 kbps net
Far GS (300 km):   22 kbps air → ~9 kbps net

Relay bottleneck: far link at 22 kbps
Close link has 4x spare capacity for telemetry, firmware updates, multiple GS
```

## Distance Estimation

The balloon estimates distance to each ground station via:

1. **RSSI of join request**: Coarse estimate, sufficient for power level selection
2. **RTToF ranging**: More accurate (LR2021 supports RTToF via RadioLib), optional
3. **GPS position exchange**: Most accurate, available if both have GPS

The firmware maintains a distance table per ground station and selects TX parameters from a lookup table.

## Night-Off Integration

Default: balloon sleeps at night. Configurable night-active mode available.

| Mode | Supercaps | Solar Cells | Weight | Avg Power |
|------|-----------|-------------|--------|-----------|
| Night-off (default) | 1x 0.47F 5.5V (0.5g) | 6-8x 52x19mm (3-4g) | ~14g | ~167 mW (day only) |
| Night-active | 2x 3.3F 2.7V (3.0g) | 12x 52x19mm (6.0g) | ~17g | ~167 mW (24h) |

Night-off sequence:
1. Solar voltage drops below threshold (sunset)
2. Announce "sleeping" to ground stations
3. Deep sleep (15 uA)
4. Solar voltage rises (sunrise) → GPIO wake
5. GPS lock (30-60s)
6. Announce "awake" with current position
7. Ground stations send queued traffic + estimated night position (from wind data)
8. Resume mesh relay

## Consequences

- +22 dBm FEM with adaptive TX and 6-8 solar cells supports the mesh relay scenario
- Same PCB accommodates both night-off and night-active configurations (different component population)
- Firmware complexity: distance table, per-slot power/modulation lookup, voltage-based night mode switching
- Ground stations must support buffered/queued traffic for night-off gaps
- Multiple balloons at different longitudes provide continuous mesh coverage
