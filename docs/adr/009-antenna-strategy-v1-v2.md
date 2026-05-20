# ADR 009: V1 Omnidirectional Antennas with V2 Directional Upgrade Path

## Status
Accepted

## Context

The balloon needs 2.4 GHz antennas for the mesh internet transport link. The original design (ADR-004) specified 4x PCB Yagis with SP4T switching. However, the mesh vision changes the optimization target: **balloon-to-ground** is the primary link (not balloon-to-balloon), and the ground station has unlimited size/weight/power for antenna gain.

A thorough product search and link budget analysis was conducted to determine whether directional antennas are needed on the balloon at all.

### Link Budget Finding

With an 18 dBi ground station Yagi (reasonable: ~1.5m, ~EUR 30-50):

| TX Power | Balloon Antenna | Received @300 km | Best Modulation | Air Rate |
|----------|----------------|------------------|-----------------|----------|
| +22 dBm (FEM) | Omnidirectional (2 dBi) | -109.6 dBm | SF9/1625 | 22 kbps |
| +22 dBm (FEM) | Yagi (7 dBi) | -102.6 dBm | SF8/1625 | 38 kbps |

22 kbps at 300 km with just a wire dipole and ground station gain. With 4x MultiWAN bonding: ~88 kbps aggregate. **Directional antennas on the balloon buy 2-3x throughput, but omni already works.**

### Product Research Findings

A comprehensive search for off-the-shelf 2.4 GHz CP patch antennas suitable for pico balloons found:

| Product | Frequency | Polarization | Gain | Weight | Suitable? |
|---------|-----------|-------------|------|--------|-----------|
| AliExpress FPC strips | 2.4 GHz | Linear (not CP) | ~1-2 dBi (despite "5 dBi" claim) | ~0.2g | Omnidirectional, no directional gain |
| Foxeer Lollipop 2.4G | 2.4 GHz | RHCP | 2.6 dBi | ~3g each (x4 = 12g) | CP but omnidirectional, too heavy |
| iFlight 2.4G CP panel | 2.4 GHz | RHCP/LHCP | ~5-8 dBi | ~15-25g | Too heavy for balloon |
| Custom CP PCB patch | 2.4 GHz | RHCP | ~5-7 dBi | ~0.5g | Requires EM simulation + VNA tuning |
| PCB Yagi (our design) | 2.4 GHz | Linear | ~6-9 dBi | ~0g (etched) | Already designed, works |

**No commercially available lightweight 2.4 GHz CP directional patch antenna exists.** The market is dominated by 5.8 GHz (FPV drones) and GPS L1 (1.575 GHz). 2.4 GHz antennas are almost exclusively linear WiFi/BT antennas.

### Balloon-to-Balloon Range

At 12 km altitude, two balloons have a geometric line-of-sight of ~780 km. However, practical 2.4 GHz LoRa range at this distance requires directional antennas at both ends and is limited to SF12 (~0.25 kbps). The primary mesh links are balloon-to-ground (~300 km), not balloon-to-balloon.

## Decision

**V1 (build first): Omnidirectional wire dipoles for both bands.**
- 868 MHz: wire dipole, ~16.4 cm, ~2 dBi, omnidirectional, rotation immune
- 2.4 GHz: wire dipole, ~6 cm, ~2 dBi, omnidirectional, rotation immune
- Ground station: 868 MHz linear Yagi (~12 dBi) + 2.4 GHz CP helical (~14 dBi RHCP)
- No SP4T switch, no antenna switching firmware, no wing board antenna design
- Throughput: ~22 kbps at 300 km (single link), ~88 kbps with 4x MultiWAN bonding

**V2 (upgrade path): Directional antennas when higher throughput needed.**
- PCB Yagis on wing boards (current design in tracker/hardware/docs/hardware-design.md)
- Or custom CP PCB patches if VNA access available
- SP4T switch + antenna diversity firmware
- Throughput: ~38-87 kbps at 300 km (single link)
- PCB designed to accommodate SP4T footprint and wing board connectors

### Night-Off Default

The balloon enters deep sleep at night (no solar). This is the default configuration:
- Saves ~3.5g (smaller supercaps: 0.47F vs 3.3F, fewer solar cells: 6-8 vs 12)
- Ground stations estimate night position from wind data
- Multiple balloons at different longitudes provide 24h coverage
- Configurable night-active mode: populate larger caps and more solar cells for special missions

### Ground Station Antennas

| Band | Antenna | Polarization | Gain | Cost | Purpose |
|------|---------|-------------|------|------|---------|
| 868 MHz | Linear Yagi | Linear | ~12 dBi | ~EUR 15 | Sub-GHz telemetry + fallback |
| 2.4 GHz | CP Helical (5-turn) | RHCP | ~14 dBi | ~EUR 15 (DIY) | High-rate 2.4 GHz link, rotation immune |

The 2.4 GHz CP helical converts the balloon's linear dipole signal with a fixed 3 dB polarization loss (predictable, manageable). An 18 dBi linear Yagi is an alternative for maximum range but has the rotation vulnerability (0-30 dB loss).

## Alternatives Considered

| Option | Rejected Because |
|--------|-----------------|
| CP patches on balloon | No off-the-shelf products exist at 2.4 GHz in lightweight form |
| Foxeer Lollipop 2.4G | CP but omnidirectional (2.6 dBi), 3g each x4 = 12g total |
| FPC sticker antennas | Linear, omnidirectional — same rotation issue as Yagis but no directional gain |
| 868 MHz only | Lower FSPL but max ~1.7 kbps — insufficient for internet transport |
| Always-on Yagis (ADR-004) | Adds complexity; ground station gain makes directional balloons unnecessary for V1 |

## Consequences

- V1 hardware is simpler: no SP4T, no wing board antenna design, no switching firmware
- V1 fits within Mittel weight budget (~14g with night-off)
- V2 upgrade path preserved in PCB layout (SP4T footprint, wing board connectors)
- Ground stations need two antennas (868 MHz Yagi + 2.4 GHz helical)
- Balloon rotation is handled at ground station (CP helical), not on balloon
