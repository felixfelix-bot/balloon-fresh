# Integration Architecture: FIPS + MeshCore + TollGate + Nostr on LR2021

This document describes the detailed technical architecture for the balloon mesh stack. See ADR-012 for the strategic decision and rationale.

## Full Protocol Stack

```
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 7: Application Services                                      │
│  ┌─────────────────┐  ┌──────────────┐  ┌───────────────────────┐ │
│  │ TollGate (Cashu) │  │ Nostr Relay  │  │ MeshCore Chat/Map    │ │
│  │ Pay-per-use WiFi │  │ Store+Forward│  │ Community messaging  │ │
│  │ Ground station   │  │ L7 async msg │  │ Sub-GHz community    │ │
│  └────────┬────────┘  └──────┬───────┘  └──────────┬────────────┘ │
├───────────┼──────────────────┼──────────────────────┼──────────────┤
│  Layer 6: │ FIPS Noise XK    │ (end-to-end encrypt) │ MeshCore    │
│           │ FIPS session mgmt│                      │ encryption  │
├───────────┼──────────────────┼──────────────────────┼─────────────┤
│  Layer 5: │ FIPS mesh routing (spanning-tree, bloom-filter disc.) │
│           │ Nostr-native identity (secp256k1 keypairs)             │
├───────────┼──────────────────────────────────────────────────────┤
│  Layer 4: │ UDP/IP tunnel over FIPS mesh                           │
├───────────┼──────────────────────────────────────────────────────┤
│  Layer 3: │ Erasure-coded fragmentation                           │
│           │ Wirehair fountain codes + sx1280-serial fragmentation │
├───────────┼──────────────────────────────────────────────────────┤
│  Layer 2: │ TDMA dual-band scheduler                              │
│           │ Sub-GHz slots (MeshCore) + 2.4 GHz slots (FIPS)      │
├───────────┼──────────────────────────────────────────────────────┤
│  Layer 1: │ LR2021 radio (dual-band LoRa/FLRC)                    │
│           │ Sub-GHz: 868 MHz (Pin 9)  │  2.4 GHz (Pin 10)       │
└───────────┴──────────────────────────────────────────────────────┘
```

## Sub-GHz Band Plan (868 MHz)

**Role**: Community mesh engagement via MeshCore repeater + coverage mapping.

| Parameter | Value | Notes |
|-----------|-------|-------|
| Frequency | 869.618 MHz | EU ISM band, MeshCore EU preset |
| Modulation | LoRa | MeshCore standard |
| Spreading Factor | SF8 | MeshCore EU/UK Narrow preset |
| Bandwidth | 62.5 kHz | Narrow setting for EU duty cycle compliance |
| Coding Rate | 4/8 | Maximum hardware FEC |
| TX Power | +22 dBm | LR2021 direct (no FEM needed at Sub-GHz) |
| Antenna | Wire dipole, 8.6 cm legs | λ/2 at 868 MHz |
| Antenna port | Pin 9 (Sub-GHz) | LR2021 dedicated Sub-GHz output |
| MeshCore role | Repeater | Forwards packets using geographic routing |
| Duty cycle | 10% max (EU SRD) | MeshCore narrow preset is designed for this |

**MeshCore repeater configuration on balloon**:
- Set name: "STRATORELAY-xx" (xx = balloon ID)
- Set location: dynamic from GPS (updated every TX cycle)
- Flood advert interval: 1 hour (less frequent than ground repeaters to save power)
- Zero-hop advert interval: 5 minutes (announces to nearby nodes directly)
- Path hash mode: 2 (3-byte path hash for disambiguation from ground repeaters)

## 2.4 GHz Band Plan

**Role**: FIPS mesh networking + Nostr event transport + TollGate session relay.

| Parameter | Short Range (<50 km) | Medium Range (50-200 km) | Long Range (200-300 km) |
|-----------|---------------------|-------------------------|------------------------|
| Modulation | FLRC 1300 kbps | LoRa SF9 / 1625 kHz | LoRa SF10 / 125 kHz |
| Air Rate | ~1300 kbps | ~22 kbps | ~1.0 kbps |
| Net (~40%) | ~520 kbps | ~9 kbps | ~0.4 kbps |
| TX Power | +12 dBm (LR2021 direct) | +22 dBm (with FEM) | +22 dBm (with FEM) |
| Antenna | Wire dipole, 3.1 cm legs | Wire dipole | Wire dipole |

Modulation selected adaptively based on ground station distance estimate from GPS coordinates.

## TDMA Dual-Band Scheduler

The LR2021 has one radio core shared between Sub-GHz and 2.4 GHz. A TDMA scheduler time-shares access.

### Frame Structure (2 seconds)

```
Slot 0          Slot 1          Slot 2          Slot 3
┌───────────────┬───────────────┬───────────────┬───────────────┐
│ Sub-GHz RX    │ 2.4 GHz TX   │ Sub-GHz RX    │ 2.4 GHz RX   │
│ MeshCore      │ FIPS/Nostr   │ MeshCore      │ FIPS/Nostr   │
│ 500 ms        │ 500 ms        │ 500 ms        │ 500 ms        │
└───────────────┴───────────────┴───────────────┴───────────────┘
│←── Guard ──→│←── Guard ──→│←── Guard ──→│←── Guard ──→│
    5 ms           5 ms           5 ms           5 ms
```

- **Clock discipline**: GPS PPS from MAX-M10S provides ±nanosecond accuracy
- **Guard bands**: 5 ms between slots (accounts for 300 km propagation = 1 ms + clock drift)
- **Slot assignment**: Balloon is natural coordinator (visible to all ground stations)
- **Band switching overhead**: LR2021 requires ~200 us frequency change (well within guard band)

### Power Budget per 2s Frame

| Activity | Duration | Current | Energy (mAs) |
|----------|----------|---------|-------------|
| Sub-GHz RX (MeshCore) | 2 × 500 ms | 11 mA | 11.0 |
| 2.4 GHz TX (FIPS) | 500 ms | 120 mA (+22 dBm) | 60.0 |
| 2.4 GHz RX (FIPS) | 500 ms | 11 mA | 5.5 |
| GPS PPS + fix maintenance | - | 8 mA avg | 4.4 |
| Band switching + guard | 4 × 5 ms | 5 mA | 0.1 |
| **Subtotal active** | | | **81.0** |
| Deep sleep (between frames) | 0 ms (continuous) | - | 0.0 |

**Average power**: 81 mAs / 2s × 3.3V = **134 mW continuous**

This requires 8-12 solar cells (~320-480 mW average) and 2× 3.3F supercaps. Night-off is mandatory (deep sleep when solar voltage drops below threshold).

### Night-Off Mode

When solar voltage drops below 2.5V:
1. Send "SLEEPING" MeshCore advert + FIPS disconnect
2. GPS sleep (PUBX command)
3. LR2021 sleep (< 1 uA)
4. ESP32-C3 deep sleep (10-15 uA)
5. Wake on solar voltage rise via GPIO or RTC timer
6. GPS hot start (~1s), MeshCore advert, FIPS reconnect

Deep sleep current: ~15 uA → 73+ hours reserve with 2× 3.3F caps at 5.4V.

## FIPS Transport over LoRa

FIPS is transport-agnostic. The microfips `Transport` trait sends and receives byte frames. We implement this trait over LoRa using proven sx1280-serial components plus Wirehair erasure coding.

### Frame Lifecycle (TX path)

```
1. Application data (Nostr event JSON, ~500 bytes)
     ↓
2. FIPS Noise XK encryption (adds ~50 bytes overhead)
     → Encrypted frame: ~550 bytes
     ↓
3. Wirehair erasure encoding
     → k = ceil(550 / 120) = 5 source blocks (120 bytes payload each)
     → Transmit 1.5× k = 8 encoded blocks for 35% loss tolerance
     ↓
4. Fragment header prepended to each encoded block
     → [block_id (4B)] [seed (1B)] [k (1B)] [payload (120B)] = 126 bytes
     ↓
5. LoRa TX in assigned TDMA slot
     → 8 fragments × 126 bytes at SF9/1625 kHz ≈ 8 × 5 ms = 40 ms airtime
```

### Frame Lifecycle (RX path)

```
1. Receive LoRa fragments in TDMA RX slots
     → May receive fragments from multiple blocks simultaneously
     ↓
2. Demux by block_id
     → Buffer encoded fragments per block
     ↓
3. Wirehair decode
     → Once k fragments received for a block → decode → original data
     → Discard excess fragments
     ↓
4. FIPS Noise XK decryption
     → Plaintext frame
     ↓
5. Deliver to application (Nostr event, TollGate message, etc.)
```

### Fragment Header Format

```
Byte  Offset  Field         Description
0-3   0       block_id      Unique per FIPS frame (monotonic counter)
4     4       seed          Wirehair seed for this block (0 = source block 0)
5     5       k             Number of source blocks (decode threshold)
6-125 6       payload       Wirehair-encoded fragment data (120 bytes)
```

Total fragment: 126 bytes. Fits within LoRa SF7-SF12 maximum payload at all bandwidths.

## Nostr over FIPS over LoRa

### Design

The balloon acts as a Nostr store-and-forward relay. It does not run a full NIP-01 WebSocket server. Instead, it:

1. **Receives** Nostr events from ground users over FIPS/LoRa (encrypted)
2. **Stores** events in flash (SPIFFS/LittleFS FIFO buffer)
3. **Forwards** events to ground station over FIPS/LoRa when in range
4. **Serves** stored events to other LoRa users who query over FIPS

The ground station runs a full Nostr relay (strfry or esp32-tollgate relay) that bridges LoRa users to the internet.

### Event Size Constraints (Phase 2)

| Kind | Description | Typical Size | LoRa Fragments (at 120B payload) |
|------|-------------|-------------|----------------------------------|
| 0 | User metadata (name, about) | ~200-500 B | 2-5 |
| 1 | Short text note | ~200-400 B | 2-4 |
| 7 | Reaction | ~150 B | 2 |
| 9735 | Zap receipt | ~300 B | 3 |

Events exceeding 500 bytes are rejected with a "too large" response. This keeps airtime per event under 30 ms at SF9/1625 kHz.

### Balloon Storage

| Parameter | Value |
|-----------|-------|
| Storage backend | SPIFFS or LittleFS on ESP32-C3 4MB flash |
| Partition size | ~1 MB (reserved from 4 MB flash) |
| Max events | ~2000 (at 500 bytes average) |
| Eviction policy | FIFO (oldest evicted when full) |
| Event TTL | 24 hours (configurable) |
| Indexing | By created_at timestamp only (simple) |

### Nostr-over-FIPS Protocol

Custom application protocol running inside FIPS encrypted sessions:

```
Message Types:
  EVENT    (0x01) — Nostr event JSON (kind 0/1/7)
  REQ      (0x02) — Filter request (query stored events)
  COUNT    (0x03) — Count matching events
  REPLY    (0x04) — Response to REQ (batch of events)
  OK       (0x05) — Acceptance/rejection of EVENT
  TOO_LARGE (0x06) — Event exceeds size limit
```

This is a simplified subset of NIP-01, optimized for LoRa bandwidth constraints. Full NIP-01 WebSocket relay runs at the ground station.

### Ground Station Bridge

```
[LoRa user]                              [Internet user]
    ↓ FIPS/LoRa                              ↓ WebSocket
[Balloon] ──(FIPS/LoRa)──> [Ground Station]
                              ├─ FIPS daemon (full mesh node)
                              ├─ Nostr relay (strfry or esp32-tollgate)
                              │   ├─ Accepts events from LoRa via FIPS
                              │   ├─ Stores in LMDB/SQLite
                              │   ├─ Serves to internet users via WebSocket
                              │   └─ Sends pending events UP to balloon
                              └─ TollGate (WiFi hotspot, Cashu payments)
```

## Ground Station Architecture

### Option A: Minimal (ESP32-C3 + LR2021)

```
┌─────────────────────────────────────┐
│  ESP32-C3 + LR2021                  │
│  ├─ FIPS leaf node (microfips)     │
│  ├─ Nostr event buffer (SPIFFS)    │
│  ├─ Serial bridge to host PC       │
│  └─ No TollGate (no WiFi AP)       │
│                                     │
│  Host PC (connected via USB)        │
│  ├─ FIPS daemon (via serial)       │
│  ├─ strfry Nostr relay             │
│  └─ Internet connection            │
└─────────────────────────────────────┘
```

Use case: temporary field deployment, low cost (~25 EUR).

### Option B: Full (Raspberry Pi + LR2021)

```
┌──────────────────────────────────────────────────────┐
│  Raspberry Pi 4/5 + LR2021 (via SPI)                │
│  ├─ FIPS daemon (full Rust)                         │
│  ├─ strfry Nostr relay (WebSocket on port 4242)     │
│  ├─ tollgate-module-basic-go on OpenWRT container   │
│  │   ├─ Cashu mint integration                      │
│  │   ├─ NoDogSplash captive portal                  │
│  │   └─ WiFi AP (pay-per-use internet)              │
│  ├─ MQTT bridge for MeshCore data → mapme.sh        │
│  └─ Ethernet or LTE backhaul                        │
└──────────────────────────────────────────────────────┘
```

Use case: permanent installation with internet, full TollGate payment flow.

## MeshCore Coverage Mapping from Stratosphere

### Value Proposition

A MeshCore repeater at 12 km altitude has geometric line-of-sight to ~900 km. During a single circumnavigation (14-30 days), the balloon will pass over most European MeshCore nodes multiple times.

### Data Collected

Each received MeshCore advert produces a data point:
- Balloon GPS position (lat, lon, alt)
- Timestamp (GPS-derived)
- Repeater ID (first byte of public key)
- RSSI and SNR
- Frequency and preset used

### Mapme.sh Integration

Ground station bridges MeshCore data to mapme.sh:
1. Balloon receives MeshCore adverts from ground repeaters
2. Balloon logs: [timestamp, balloon_pos, repeater_id, RSSI, SNR]
3. Balloon sends log to ground station over FIPS/LoRa
4. Ground station uploads to mapme.sh API

A single flight produces the most comprehensive MeshCore coverage map ever created — stratospheric perspective reveals propagation patterns invisible from ground level.

### Range Expectations at 12 km Altitude

| Ground Repeater Distance | FSPL (868 MHz) | Received Power | Decodable? |
|-------------------------|----------------|---------------|------------|
| 100 km | 131.2 dB | -107.2 dBm | Yes (SF8 sens: -126 dBm) |
| 300 km | 140.8 dB | -116.8 dBm | Yes |
| 500 km | 145.2 dB | -121.2 dBm | Yes |
| 700 km | 148.1 dB | -124.1 dBm | Yes (marginal) |
| 900 km | 150.3 dB | -126.3 dBm | Marginal |

Balloon TX: +22 dBm, 2 dBi dipole. Ground repeater: assumed 0 dBi antenna, SF8 sensitivity -126 dBm. Atmospheric loss at altitude is minimal (clear LOS).

## C++ vs Rust Tradeoff for Balloon Firmware

| Factor | C++ / ESP-IDF | Rust / esp-rs (microfips) |
|--------|---------------|--------------------------|
| **Tracker consistency** | Same build system, shared components | Separate build, port telemetry component |
| **RadioLib** | Already integrated (C++ native) | Need Rust SPI bindings or C FFI |
| **FIPS compatibility** | Need C++ FIPS leaf node implementation | microfips already exists (Rust/no_std) |
| **MeshCore compatibility** | MeshCore is C++/PlatformIO | Need Rust MeshCore client or C FFI |
| **Wirehair** | C library, direct integration | Need Rust FFI or Rust fountain code |
| **ESP32-C3 support** | Native (ESP-IDF) | esp-rs supports RISC-V, but microfips tested on Xtensa only |
| **No std library** | Full std available | no_std required for embedded, microfips already no_std |
| **Build complexity** | Single build system (idf.py) | Two build systems (idf.py + cargo) |
| **Memory safety** | Manual management | Compiler-enforced |
| **Community** | Larger ESP ecosystem | Growing esp-rs ecosystem |

### Hybrid Option

Tracker firmware stays C++/ESP-IDF. Mesh firmware is a separate Rust binary using microfips + sx1280-serial codebase. Shared telemetry via C ABI:
- `telemetry_serialize()` / `telemetry_validate()` exposed as C functions
- Rust mesh firmware calls C telemetry for GPS/sensor data

Decision: deferred to Phase 2 implementation.

## Component Weight Budget (Mesh V1)

| Component | Weight |
|-----------|--------|
| ESP32-C3 bare (ESP-C3-12F) | 1.0g |
| NiceRF LoRa2021 module | 1.8g |
| u-blox MAX-M10S GPS | 0.6g |
| 2× 3.3F 2.7V supercaps | 3.0g |
| 8× solar cells 52x19mm | 4.0g |
| Wire dipole (Sub-GHz + 2.4 GHz) | 0.4g |
| PCB hub (0.4mm FR4) | 0.2g |
| Passive components | 0.2g |
| Misc (solder, Kapton) | 0.3g |
| **Total** | **~11.5g** |

Within 14g Mesh V1 target (3.3g margin for FEM if needed).

## Power Budget Summary

| Mode | Average Power | Solar Needed | Night Reserve |
|------|--------------|-------------|---------------|
| Tracker only (TX every 120s) | ~7 mW | 2 cells | 73h (2×3.3F) |
| MeshCore repeater only (Sub-GHz RX continuous) | ~36 mW | 4 cells | 14h |
| Full mesh (dual-band TDMA) | ~134 mW | 8-12 cells | 3-5h |
| Full mesh + Nostr relay | ~140 mW | 8-12 cells | 3-5h |

Night-off is mandatory for full mesh mode. During night, balloon sleeps (~15 uA) and wakes at sunrise.
