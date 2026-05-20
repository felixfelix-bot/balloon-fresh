# Mesh Stack — DIY Open-Source Mesh Internet Transport

## Vision

A network of stratospheric pico balloons acting as mesh relay nodes, connecting multiple ground stations with internet backhaul. UDP transport with erasure-coded reliability. 2.4 GHz primary link (LR2021), Sub-GHz fallback. MultiWAN bonding across multiple balloon paths for aggregate throughput.

This is **not** a competitor to Starlink (50-350 Mbps via 12 GHz Ku/Ka-band phased arrays + thousands of LEO satellites). Realistic targets are **1-130 kbps per link**, aggregate **4-520 kbps** with 4 balloons bonded. Usable for messaging, small images, sensor data, emergency communication where no other connectivity exists.

## Layered Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Application Layer                                       │
│  Internet transport: IP tunnel / SOCKS / transparent     │
│  proxy. MultiWAN bonding across balloon paths.           │
├─────────────────────────────────────────────────────────┤
│  Transport Layer                                         │
│  UDP datagrams. NO TCP — RTT too high for TCP congestion │
│  control. Reliability from erasure coding below.         │
├─────────────────────────────────────────────────────────┤
│  Network Layer                                           │
│  Mesh routing between balloons. Erasure-coded            │
│  fragmentation (fountain codes). Fragment reassembly.    │
├─────────────────────────────────────────────────────────┤
│  Link Layer                                              │
│  TDMA with coordinator election. Contention windows for  │
│  new node join. Dynamic slot leases. Clock sync via      │
│  GPS PPS (balloons) + ranging (ground stations).         │
├─────────────────────────────────────────────────────────┤
│  Physical Layer                                          │
│  LR2021 2.4 GHz (FLRC high-rate / LoRa long-range)       │
│  LR2021 Sub-GHz (868 MHz LoRa, fallback)                 │
│  Hardware FEC built into LoRa/FLRC modem.                │
└─────────────────────────────────────────────────────────┘
```

## Reference Repositories by Layer

### Physical Layer

| Repo | URL | Notes |
|------|-----|-------|
| RadioLib | `https://github.com/jgromes/RadioLib` | Our RF driver. Supports LR2021 LoRa, FLRC, RTToF ranging. v7.6.0 in use. |
| Semtech USP | `https://github.com/Lora-net/usp` | Official Semtech Unified Software Platform for LR2022/SX1280. Reference for register-level control. |
| Poucet_LCIS_LoRa24 | `https://github.com/Hedwyn/Poucet_LCIS_LoRa24` | SX1280 ranging PHY config. Tip: use 1600 kHz BW for ranging accuracy. |

### Link Layer — TDMA

| Repo | URL | Notes |
|------|-----|-------|
| ts-lora | `https://github.com/deltazita/ts-lora` | Time-slotted LoRa framework. TDMA frame structure, slot scheduling, guard bands. |
| LoRaMesher | `https://github.com/LoRaMesher/LoRaMesher` | TDMA superframes, distributed nodes, deterministic role changes, mesh routing. |
| sx1280-serial | `nostr://npub12m5exm2uk3xa674cc5r0hlyvccs5xxn7qv83ezuteefv5972nquq4j4szl/relay.ngit.dev/sx1280-serial` | Our proven TDMA + coordinator election (Rust). Fragmentation, reassembly, peer warmup, crypto identity. Most mature of our repos. |

### Link Layer — Clock Sync

| Repo | URL | Notes |
|------|-----|-------|
| LoraRangingTest | `https://github.com/yplam/LoraRangingTest` | SX1280 ranging on STM32/mbed. Bare-metal ranging implementation for clock calibration. |
| ublox-GNSS-Arduino | `https://github.com/u-blox/ublox-GNSS-Arduino-Library` | u-blox GPS library. PPS config, airborne mode (UBX-CFG-NAV5 dynamic model 6/7). |
| Poucet_LCIS_LoRa24 | `https://github.com/Hedwyn/Poucet_LCIS_LoRa24` | Ranging PHY optimization (see above). |

### Network Layer — Erasure Coding

| Repo | URL | Notes |
|------|-----|-------|
| Wirehair | `https://github.com/catid/wirehair` | **Primary candidate.** Fountain code library in C. O(N) performance, zero deps. Best fit for embedded. |
| Shorthair | `https://github.com/catid/shorthair` | Streaming erasure codes by same author. UDP-oriented, fixed overhead per generation. |
| OpenFEC | `https://github.com/OpenFEC/OpenFEC` | Academic-grade multi-algorithm: Reed-Solomon, LDPC-Staircase, LT codes, Raptor. Heavier but useful for comparison. |

### Network Layer — Ground Station Tools

| Repo | URL | Notes |
|------|-----|-------|
| pywirehair | `https://github.com/sz3/pywirehair` | Python wrapper for Wirehair. Ground station decode. |
| pyeclib | `https://github.com/openstack/pyeclib` | Python erasure coding with Intel ISA-L backend. |
| ErasureCodes | `https://github.com/ianopolous/ErasureCodes` | JavaScript Reed-Solomon for web UI monitoring. |

### Testing & Methodology (Our Repos)

| Repo | URL | Notes |
|------|-----|-------|
| sx1280-correlation-test | `nostr://npub12m5exm2uk3xa674cc5r0hlyvccs5xxn7qv83ezuteefv5972nquq4j4szl/relay.ngit.dev/sx1280-correlation-test` | Field-tested range testing. 35k CSV records, 30-37% delivery ratio. Deterministic payload + correlation methodology. |
| sx1280-testing | `nostr://npub12m5exm2uk3xa674cc5r0hlyvccs5xxn7qv83ezuteefv5972nquq4j4szl/relay.ngit.dev/sx1280-testing` | Basic bring-up, ~1 kbps throughput benchmark. |
| sx1280-ethernet-adapter | `nostr://npub12m5exm2uk3xa674cc5r0hlyvccs5xxn7qv83ezuteefv5972nquq4j4szl/relay.ngit.dev/sx1280-ethernet-adapter` | ESP32-S3 + SX1280 Wi-Fi AP bridge scaffold. Architecture closest to what ground station could look like. |

### External References (not GitHub)

| Resource | URL | Notes |
|----------|-----|-------|
| Stuart's Balloon Tracker | `https://StuartsProjects.com` | Real SX1280 balloon tracker. Ranging calibration data at 40-85 km. High-altitude GPS + antenna weight data. |
| Semtech Advanced Ranging | Semtech docs site | Theory of SX1280 ranging engine. |
| "Damn Cool Algorithms: Fountain Codes" | `https://blog.notdot.net/2012/01/Damn-Cool-Algorithms-Fountain-Codes` | Excellent Fountain Code explainer. |

## How Erasure Coding Transforms the Architecture

Without erasure coding, every lost fragment requires a retransmission ACK round-trip:

```
Node TX: [frag0] [frag1] [frag2] [frag3]
                              ↑ LOST
Ground:  "I got 0,1,3 but not 2 — please retransmit 2"
Node TX:  .............. [frag2 retransmit]
                                  ↑ LOST AGAIN
Ground:  "Still don't have 2..."
```

With fountain codes (Wirehair), the transmitter generates an infinite stream of encoded fragments. The receiver needs ANY k fragments to decode:

```
Node TX: [E0] [E1] [E2] [E3] [E4] [E5]   ← 6 encoded from 4 original
                        ↑ LOST      ↑ LOST
Ground:  "I got E0,E1,E3,E5 — that's 4 (=k). DECODE SUCCESS."
```

**Why this matters for balloons:**
1. **No ACK round-trip** — balloon blasts encoded fragments in its TDMA slot, goes back to sleep
2. **Works with 30-37% packet loss** — exactly what `sx1280-correlation-test` measured in field tests
3. **Predictive leases** — if loss is ~35%, transmit ~1.5x fragments (k=4 → send 6 encoded blocks)
4. **Eliminates TCP need** — reliability at network layer, UDP above

## Clock Synchronization Options

| Approach | Accuracy | Weight Added | Complexity | Requires Ground Contact? |
|----------|----------|-------------|------------|-------------------------|
| Free-running (no sync) | Seconds/day drift | 0g | Useless for TDMA | N/A |
| TCXO only | ±0.5 ppm (~seconds/week) | ~0g (on-chip) | Moderate | No |
| RTToF ranging sync | ±microseconds | 0g | Complex | Yes — needs 2-way ranging exchange |
| GPS PPS (u-blox MAX-M10S) | ±nanoseconds | ~0.6g bare, ~2g with antenna | Simple | No — self-synchronized |

**Recommended for balloons:** GPS PPS discipline with u-blox MAX-M10S (0.6g bare). Provides stratum-1 clock, PPS hardware interrupt for TDMA slot boundaries, position data for routing. Must configure Airborne <1G mode (UBX-CFG-NAV5 dynamic model 6) to bypass COCOM 18km altitude limit. Supports up to 80,000m.

**Recommended for ground stations without GPS:** RTToF ranging sync. Ground station initiates ranging with balloon, gets distance + propagation delay, balloon injects GPS-corrected time.

## Cold-Start Sync Protocol (Ranging-Based)

For nodes without GPS (ground stations, or balloons recovering from long offline):

```
[ Node (no GPS) ]                           [ Balloon (GPS PPS) ]
      |                                              |
      | -- (1) Broadcast: "I am Node X, need sync" ->|
      |                                              |
      | <- (2) SX1280/LR2021 RTToF Ranging -------- |  Measures ToF
      |                                              |  (exact distance)
      |                                              |
      | <- (3) Data: [GPS_UTC_Time + ToF_Delay] ---- |
      |                                              |
 [Calibrate local clock]                             |
 [Enter TDMA frame clock]                            |
```

Software drift tracking maintains accuracy between sync events:
- `master_time = offset + local_ticks * drift_rate`
- `drift_rate` updated from two sequential sync measurements 60s apart
- Guard bands auto-expand based on time since last sync

## Throughput Estimates

| Mode | Frequency | Modulation | Data Rate | Range | Use Case |
|------|-----------|-----------|-----------|-------|----------|
| LoRa SF12 / 125 kHz | 868 MHz | LoRa | ~0.25 kbps | ~480 km | Maximum range emergency |
| LoRa SF9 / 125 kHz | 868 MHz | LoRa | ~1.7 kbps | ~300 km | Current tracker design |
| LoRa SF10 / 1625 kHz | 2.4 GHz | LoRa | ~12 kbps | ~50 km | Primary mesh link |
| LoRa SF9 / 1625 kHz | 2.4 GHz | LoRa | ~22 kbps | ~40 km | Balanced mesh link |
| FLRC / 1625 kHz | 2.4 GHz | FLRC | ~130 kbps | ~20 km | High-rate short-range |

**MultiWAN bonding estimate:** 4 balloons at FLRC 130 kbps each = ~520 kbps aggregate (before erasure coding overhead). With 1.5x erasure overhead for 35% loss: ~350 kbps net.

**Note:** These are air data rates. Actual throughput depends on TDMA overhead, guard bands, contention windows, erasure coding overhead, and protocol headers. Expect 50-70% of air data rate as net throughput.

**SX1280 USB dongle bottleneck:** The Ebyte E28-2G4T27SX USB dev boards use a CH341 USB-serial chip that bottlenecks throughput at ~9600-115200 baud serial. The dongles are useful for range testing and protocol prototyping but **cannot** measure actual radio throughput. Our LR2021 on ESP32-C3 with direct SPI does not have this bottleneck.

## Relationship to Existing Work

### What We Already Have

| Component | Source | Status |
|-----------|--------|--------|
| LR2021 RadioLib driver | `firmware/` (tracker) | Working, builds |
| ESP32-C3 HAL for RadioLib | `firmware/main/EspHalC3.h` | Working |
| TDMA + coordinator election | `sx1280-serial` (Rust) | Proven, needs port to C++ |
| Fragmentation + reassembly | `sx1280-serial` (Rust) | Proven: SLIP + CRC-32 + 128-byte frags |
| Crypto identity binding | `sx1280-serial` (Rust) | Proven: secp256k1 Schnorr signatures |
| Range testing methodology | `sx1280-correlation-test` | 35k records, deterministic payloads |
| Hardware debug ladder (L0→L3) | `sx1280-serial` feature branch | Proven methodology |
| Wi-Fi AP + HTTP status | `sx1280-ethernet-adapter` | Scaffold only (Rust/ESP-IDF) |
| PCB design for balloon | `hardware/` (tracker) | In progress (KiCad) |

### What's New (Not in Any Existing Repo)

| Component | Library | Notes |
|-----------|---------|-------|
| Erasure/fountain coding | `github.com/catid/wirehair` | Critical new capability |
| Clock sync protocol | Custom + RadioLib ranging | New protocol design |
| GPS PPS discipline | `github.com/u-blox/ublox-GNSS-Arduino-Library` | New hardware component |
| Mesh routing | TBD (study LoRaMesher) | New capability |
| MultiWAN bonding | Custom | New capability |
| UDP/IP transport | Custom | New capability |

## Phased Roadmap

### Phase 1: Balloon Tracker (Current Scope — `tracker/`)
- 1 balloon, 1 ground station
- 868 MHz LoRa telemetry (24 bytes, CRC-16)
- No mesh, no TDMA, no erasure coding
- **Status: In progress** — PCB design, firmware builds

### Phase 2: Reliable Link (`mesh-stack/` research → implement)
- Add Wirehair erasure coding to firmware
- Add RTToF ranging for clock sync via RadioLib
- Add fragmentation/reassembly (port from `sx1280-serial`)
- Switch to UDP transport
- Still 1:1, but now reliable despite 30-37% packet loss
- **Status: Research phase**

### Phase 3: TDMA Mesh (`mesh-stack/`)
- Port TDMA coordinator election from `sx1280-serial`
- Add GPS PPS discipline with MAX-M10S
- Implement contention windows and slot leases
- Reference: `ts-lora`, `LoRaMesher`
- Multiple balloons, multiple ground stations
- **Status: Not started**

### Phase 4: Internet Transport (`mesh-stack/`)
- Mesh routing between balloons
- MultiWAN bonding across balloon paths
- IP tunneling over the mesh
- UDP transport with erasure-coded reliability
- Ground stations provide internet backhaul
- **Status: Not started**

---

## Research Checklist

### Step 1: Erasure Coding
- [ ] Clone `https://github.com/catid/wirehair` — study API, encoder/decoder init, memory usage
- [ ] Determine ESP32-C3 feasibility: 400KB RAM, 160MHz RISC-V — can Wirehair run?
- [ ] Benchmark: What's the maximum block size that fits in ESP32-C3 RAM?
- [ ] Clone `https://github.com/catid/shorthair` — study streaming variant, compare with Wirehair
- [ ] Clone `https://github.com/OpenFEC/OpenFEC` — compare algorithms (LT vs Raptor vs RS vs LDPC)
- [ ] Design fragment header format: `block_id` (4 bytes) + `seed/fragment_index` (1 byte) + `k` (1 byte) + payload
- [ ] Write findings to `mesh-stack/research/erasure-coding/notes.md`

### Step 2: TDMA
- [ ] Clone `https://github.com/deltazita/ts-lora` — study TDMA frame structure, slot scheduling
- [ ] Clone `https://github.com/LoRaMesher/LoRaMesher` — study mesh superframes, node discovery, routing
- [ ] Review `sx1280-serial` TDMA design (`src/link/tdma.rs`, `coord.rs`) — our proven approach
- [ ] Design TDMA frame: epoch structure, contention window size, slot duration, guard bands
- [ ] Determine: Is ts-lora, LoRaMesher, or our sx1280-serial design the best starting point?
- [ ] Write findings to `mesh-stack/research/tdma/notes.md`

### Step 3: Clock Sync
- [ ] Clone `https://github.com/yplam/LoraRangingTest` — study SX1280 ranging implementation
- [ ] Clone `https://github.com/Hedwyn/Poucet_LCIS_LoRa24` — study ranging PHY optimization (1600 kHz BW)
- [ ] Clone `https://github.com/u-blox/ublox-GNSS-Arduino-Library` — study PPS config, airborne mode API
- [ ] Verify: Does LR2021 support the same ranging engine as SX1280, or is it RTToF-only?
- [ ] Verify: What's the ranging accuracy of LR2021 vs SX1280 at 300 km?
- [ ] Design cold-start sync protocol (ranging-based for no-GPS nodes)
- [ ] Design software drift tracking loop (offset + drift_rate)
- [ ] Study Stuart's Balloon Tracker ranging calibration data (40-85 km)
- [ ] Write findings to `mesh-stack/research/clock-sync/notes.md`

### Step 4: Mesh Routing
- [ ] Study LoRaMesher's routing approach
- [ ] Research mesh routing protocols suitable for high-latency, lossy links
- [ ] Determine: full routing protocol vs. simple flood/gateway-discovery
- [ ] Determine: source routing vs. distance-vector vs. reactive (AODV-style)
- [ ] Consider: Does each balloon need a routing table, or can we use balloon-to-balloon flooding?
- [ ] Write findings to `mesh-stack/research/routing/notes.md`

### Step 5: Throughput & Link Budget
- [ ] Calculate TDMA overhead: contention window, guard bands, slot headers
- [ ] Calculate erasure coding overhead for various loss rates (20%, 35%, 50%)
- [ ] Calculate net throughput per modulation mode after all overheads
- [ ] Model MultiWAN bonding: N balloons × per-link throughput × (1 - erasure_overhead)
- [ ] Determine: how many balloons at what modulation for usable internet?
- [ ] Measure actual LR2021 FLRC throughput on ESP32-C3 via SPI (no CH341 bottleneck)
- [ ] Write findings to `mesh-stack/research/throughput/notes.md`

### Step 6: Protocol Specification
- [ ] Write `mesh-stack/protocol/SPEC.md` — layered protocol specification
- [ ] Define PHY modes and their parameters
- [ ] Define TDMA frame format and slot types
- [ ] Define fragment format with erasure coding metadata
- [ ] Define routing packet format
- [ ] Define clock sync message format

### Step 7: Project Reorganization
- [ ] Move `firmware/` → `tracker/firmware/`
- [ ] Move `hardware/` → `tracker/hardware/`
- [ ] Move `ground-station/` → `tracker/ground-station/`
- [ ] Update `AGENTS.md` with new paths
- [ ] Update build commands in docs
- [ ] Write `mesh-stack/AGENTS.md` — scoped context for mesh stack work
- [ ] Git commit and push

---

## Open Research Questions

### Critical (blocks design decisions)
1. **Can Wirehair run on ESP32-C3?** The ESP32-C3 has 400KB RAM and a 160MHz single-core RISC-V CPU. What's Wirehair's peak memory usage for typical block sizes (1-10 KB)? What's encode/decode latency?
2. **Does LR2021 support the same ranging engine as SX1280?** The SX1280 has a hardware ToF ranging engine. The LR2021 datasheet mentions RTToF ranging. Are they the same hardware? Does RadioLib's `range()` function work on LR2021?
3. **What's the realistic FLRC throughput on LR2021 via SPI?** The E28 USB dongles are bottlenecked by the CH341 serial chip (~115200 baud). Direct SPI on ESP32-C3 should be much faster. What's the actual ceiling?

### Important (affects architecture)
4. **Which TDMA framework to use as starting point?** Our `sx1280-serial` TDMA is proven but in Rust. `ts-lora` and `LoRaMesher` are C/C++ but need evaluation. Which is closest to what we need?
5. **What TDMA slot duration for 300 km links?** At 300 km, propagation delay is 1 ms. LoRa packets at SF10 take 10-100 ms airtime. What slot duration + guard band gives usable throughput while tolerating clock drift?
6. **Mesh routing: proactive or reactive?** Balloons move slowly relative to each other (same wind layer). Ground stations are fixed. Does this simplify routing enough to avoid a full mesh protocol?
7. **What GPS module for balloons?** u-blox MAX-M10S is the community favorite (0.6g bare, 25 mW, 80km ceiling). But do we need a full GPS, or can we get away with TCXO + ranging sync for weight savings in the Minimal plan?

### Interesting (deeper investigation)
8. **Shorthair vs Wirehair for streaming?** Shorthair is designed for continuous streams, Wirehair for bulk blocks. Which fits our use case better? We're sending continuous telemetry streams AND occasional bulk data.
9. **MultiWAN bonding algorithm?** How to bond multiple high-latency, variable-loss links? MPTCP won't work (no TCP). Custom UDP bonding? Packet-level striping across balloons?
10. **Coordinator election at altitude?** The sx1280-serial coordinator election assumes all nodes can potentially hear each other. At altitude with directional antennas, the topology is different. How does this change the protocol?
11. **Can we use LoRa hardware FEC + erasure coding together effectively?** LoRa has built-in CR (coding rate) 4/5 to 4/8. Does using a higher CR (more hardware FEC) plus erasure coding give better throughput than lower CR (less overhead) with more erasure overhead? Where's the sweet spot?
12. **Temperature impact on LR2021 frequency stability?** At -60°C stratospheric temps, the LR2021's oscillator may drift. Does this affect ranging accuracy? Do we need TCXO on the radio module too, not just the MCU?
