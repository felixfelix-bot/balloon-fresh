# ADR 014: Bent-Pipe FPGA/RP2040 Bridging for Multi-Balloon Mesh

## Status

Proposed

## Context

Current balloon relay requires the ESP32-C3 MCU to process every packet sequentially (~15-20ms per packet). This creates two problems:

1. **Latency**: A 3-balloon relay chain adds 45-60ms of processing delay. This is too slow for interactive communication (voice, real-time text, responsive payments).

2. **Throughput bottleneck**: The MCU-based pipeline achieves only 80 kbps (3% of the 2.6 Mbps FLRC air rate). The radio can send/receive much faster than the MCU can process.

Additionally, a single LR2021 radio can only operate on one frequency/mode at a time. For true multi-balloon mesh with frequency diversity, we need multiple radios operating simultaneously.

The LR2021 (unlike the SX1280) has native FIFO capabilities that may partially solve the throughput problem:
- Dedicated RX/TX FIFOs with level monitoring
- FIFO threshold interrupts (EMPTY/LOW/HIGH/FULL/OVERFLOW)
- Auto-RX-TX mode (radio auto-returns to RX after packet)
- Single-frame FIFO read

However, for multi-radio and minimum-latency relay, a dedicated hardware path is needed.

## Decision

Implement a **data plane / control plane separation** using an FPGA or RP2040 coprocessor for bent-pipe packet relaying between radios. The ESP32-C3 remains the main MCU (for its 5µA deep sleep capability) but delegates high-speed packet forwarding to a dedicated coprocessor.

### Architecture

```
┌─ APPLICATION PLANE ────────────────────────────────┐
│  Nostr events (store-and-forward messaging)        │
├─ PAYMENT PLANE ────────────────────────────────────┤
│  TollGate (Cashu token verification, QoS)          │
├─ CONTROL PLANE ────────────────────────────────────┤
│  FIPS (Noise XK encryption, mesh routing, identity)│
│  Runs on ESP32-C3 (~15ms per routing decision)     │
├────────────────────────────────────────────────────┤
│         ↓ configures routing table ↓               │
├─ DATA PLANE ───────────────────────────────────────┤
│  FPGA/RP2040 Crossbar (packet relay, ~1-5µs)       │
│  Transparent to FIPS/TollGate/Nostr                │
│  Moves encrypted packets between antennas          │
├─ PHYSICAL PLANE ───────────────────────────────────┤
│  N× LR2021 radios (FLRC/LoRa, dual-band)           │
└────────────────────────────────────────────────────┘
```

### Option A: FPGA Coprocessor (Lattice iCE40 UP5K)

The FPGA implements an N×N non-blocking crossbar switch between radios:

```
Radio 1 RX ──→ ┌─────────────────┐ ──→ Radio 1 TX
Radio 2 RX ──→ │  FPGA CROSSBAR  │ ──→ Radio 2 TX  
Radio 3 RX ──→ │  (N×N matrix)   │ ──→ Radio 3 TX
Radio 4 RX ──→ └─────────────────┘ ──→ Radio 4 TX
```

- **Latency**: ~1µs per relay hop
- **Power**: ~3-5mA active, <10µA sleep (but FPGA is power-gated by ESP32-C3)
- **Capacity**: iCE40 UP5K has 48 I/O → supports up to 6 LR2021 radios
- **Development**: Verilog/VHDL with yosys/nextpnr open-source toolchain
- **Weight**: ~0.3g (QFN-48 package)
- **Flight heritage**: iCE40 used in cubesats and small satellites

### Option B: RP2040 Coprocessor (Dual-Core + PIO)

The RP2040 uses its dual-core architecture and PIO state machines:

```
LR2021 #1 ──SPI0──→ RP2040 Core 0 ──┐
LR2021 #2 ──SPI1──→ RP2040 Core 1 ──┴──SPI──→ ESP32-C3
```

- **Latency**: ~5µs per relay hop (PIO SPI mastering + SRAM routing)
- **Power**: ~15-25mA active at 48-125MHz, 0.2mA DORMANT (power-gated by ESP32-C3)
- **Capacity**: 2 hardware SPI → supports 2 LR2021 radios natively, 3+ with PIO multiplexing
- **Development**: C/C++ with Pico SDK or Arduino Core, PIO assembly for SPI
- **Weight**: ~0.3g (QFN-56) + external QSPI flash (~0.1g)
- **Advantage**: Much easier to develop than FPGA, dual-core parallelism

### Antenna Strategy

- **Ground stations**: Yagi or dish antennas (directional, high gain, +10-20 dBi)
- **Balloons**: Omnidirectional wire dipoles or patch antennas (low gain but no pointing needed)

Multi-radio balloons can use different antennas per radio:
- Radio 1: Horizontal wire dipole (→ next balloon at similar altitude)
- Radio 2: Patch antenna pointing down (→ ground station)
- Radio 3: Horizontal wire dipole rotated 90° (→ balloon in different direction)

### Integration with FIPS, TollGate, and Nostr

The FPGA/RP2040 data plane is **completely transparent** to all higher layers:

**FIPS** (control plane): Handles end-to-end encryption (Noise XK with secp256k1), mesh routing decisions (spanning-tree, bloom-filter discovery), and session management (FMP/FSP protocol). FIPS runs on the ESP32-C3 and configures the FPGA routing table via SPI. When balloon topology changes (wind drift), FIPS recalculates routes and updates which radio→radio paths are enabled. The FPGA just physically relays already-encrypted FIPS frames — it cannot decrypt or modify them.

**TollGate** (payment plane): Cashu token verification happens at endpoints (ground stations), not at relay balloons. The FPGA does not participate in payment verification — it cannot, because it doesn't understand the TollGate protocol. TollGate operates at the FIPS session layer above the FPGA data plane. The FPGA's benefit to TollGate is reduced latency: payment messages traverse multi-balloon chains in ~2ms instead of ~50ms, enabling responsive payment UX.

**Nostr** (application plane): Store-and-forward events benefit from reduced relay latency. The FPGA does not store events — that's done by the ESP32-C3's SPIFFS/flash. The FPGA just ensures Nostr events traverse multi-balloon chains fast enough for near-real-time messaging.

This is analogous to **Software-Defined Networking (SDN)**:
- FIPS = SDN controller (control plane, slow path)
- FPGA/RP2040 = OpenFlow switch (data plane, fast path)
- LR2021 radios = switch ports

### Multi-Balloon Relay Chain

```
GS1 ←─FIPS─→ B1 ←─FPGA─→ B2 ←─FPGA─→ B3 ←─FIPS─→ GS2
              1µs         1µs
              
Total relay latency: ~3µs (FPGA) + 3×0.6ms (air) = 1.8ms
vs current MCU relay: 3×15ms (MCU) + 3×0.6ms (air) = 47ms
→ 26x latency improvement
```

### Multi-Radio Topologies

**Linear chain** (2 radios per balloon):
```
GS1 ←→ B1 ←→ B2 ←→ B3 ←→ GS2
```

**Star topology** (4 radios on hub balloon):
```
              Balloon Hub (4 radios)
             /     |      \
        Balloon1  Balloon2  Balloon3
```

**Cross-altitude** (balloons at different wind layers):
```
12 km:  Balloon A ←──→ Balloon B
              ↕ (vertical radio link)
 8 km:  Balloon C ←──→ Balloon D
```

### Power-Gated Operation

The ESP32-C3 controls power to the FPGA/RP2040:
- **Night-off**: ESP32-C3 in 5µA deep sleep, FPGA/RP2040 completely powered off (0 mA)
- **Day-active**: ESP32-C3 wakes, enables power to FPGA/RP2040, resumes mesh operation
- This preserves the balloon's ultra-low night-off power budget

## Consequences

### Positive
- **26x latency improvement** for multi-hop relay (47ms → 1.8ms for 3 hops)
- **Near-air-rate throughput** per link (up to 2.6 Mbps vs current 80 kbps)
- **Frequency diversity**: Multiple radios on different bands operate simultaneously
- **Transparent to FIPS/TollGate/Nostr**: No protocol changes needed
- **Scalable**: 2-6 radios per balloon depending on FPGA/RP2040 choice
- **Power-gated**: No impact on night-off sleep budget

### Negative
- **Added weight**: +0.3g (coprocessor) + 0.5g per additional LR2021 = 0.8-2.8g extra
- **Added power**: +3-25mA during active operation (daytime only)
- **Complexity**: Additional firmware (Verilog or RP2040 C/C++) and PCB design
- **Cost**: Additional components (~$1-5 per balloon)

### Research Questions
1. Can the LR2021's native FIFO achieve high throughput WITHOUT a coprocessor? (test first)
2. What is the actual FIFO depth? (API returns uint16_t, suggesting >256 bytes possible)
3. Does the FIFO accumulate multiple packets, or does each overwrite? (hardware test needed)
4. How does TDMA scheduling work with multiple independent radios?
5. What is the optimal number of radios per balloon (2 vs 3 vs 4)?

## Implementation Priority
1. **First**: Test LR2021 native FIFO batching (no extra hardware) — may achieve 800+ kbps
2. **Second**: DMA streaming on ESP32-C3 (no extra hardware) — may achieve 800 kbps-2 Mbps
3. **Third**: RP2040 dual-radio prototype (easiest coprocessor to develop)
4. **Fourth**: FPGA iCE40 port for flight hardware (lowest power)
