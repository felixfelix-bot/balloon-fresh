# Software-Only Work Plan

Tasks that can be completed without hardware access. Progress tracked via checklists.

---

## Task 1: FIPS + microfips Code Study

Research the FIPS daemon and microfips leaf node to understand the Noise XK handshake, mesh routing, and Nostr identity for Phase C integration.

- [ ] Clone and study FIPS daemon (`https://github.com/jmcorgan/fips`)
  - [ ] Architecture overview: main components, event loop
  - [ ] Noise XK handshake flow (message exchange, key derivation)
  - [ ] Mesh routing: spanning-tree, bloom-filter discovery
  - [ ] Nostr identity: secp256k1 keypair usage
  - [ ] UDP/IP tunnel: packet format, framing
  - [ ] LoRa bandwidth requirements for handshake
- [ ] Clone and study microfips (`https://github.com/Amperstrand/microfips`)
  - [ ] STM32/ESP32 HAL abstraction
  - [ ] Noise protocol subset implemented
  - [ ] Memory usage and flash footprint
  - [ ] Radio interface (what radio hardware?)
  - [ ] Feasibility: port microfips to ESP32-C3 + LR2021?
- [ ] Write study document: `mesh-stack/research/routing/fips-study.md`
  - [ ] Handshake RTT budget over LoRa
  - [ ] Minimum viable subset for balloon (session mgmt, routing, encryption)
  - [ ] RAM/flash estimates for ESP32-C3
  - [ ] Integration path with existing RadioLib + erasure coding

---

## Task 2: Nostr Event Store Design + Implementation

Design and implement a lightweight Nostr event store for balloon relay.

- [ ] Design compact binary event format for LoRa (vs JSON)
  - [ ] Event fields: id(32), pubkey(32), kind(2), created_at(4), tags(variable), content(variable), sig(64)
  - [ ] Binary encoding: TLV or fixed-offset
  - [ ] Estimate: average event ~200-500 bytes binary
- [ ] Design SPIFFS/LittleFS storage layout
  - [ ] FIFO ring buffer: ~2000 events, ~1 MB
  - [ ] Index file for kind-based lookup
  - [ ] Wear leveling considerations
- [ ] Design bloom filter for dedup
  - [ ] Size: 256 bytes (2048 bits) for ~2000 events, ~10% false positive
  - [ ] Hash function: simple double-hash
- [ ] Create `tracker/firmware/components/nostr_store/` component
  - [ ] `nostr_event.h` — event structure, binary serialize/deserialize
  - [ ] `nostr_store.h/c` — FIFO store with bloom filter
  - [ ] `nostr_bloom.h/c` — bloom filter for dedup
- [ ] Host tests for all sub-components
- [ ] Verify `idf.py build` passes

---

## Task 3: TDMA Scheduler Design + Host Tests

Design a lightweight TDMA scheduler based on our sx1280-serial implementation.

- [ ] Study sx1280-serial TDMA implementation (Rust)
  - [ ] Frame structure: slot count, slot duration, guard bands
  - [ ] Coordinator election algorithm
  - [ ] Clock sync: GPS PPS discipline
  - [ ] Peer discovery and join protocol
- [ ] Study ts-lora TDMA framework
  - [ ] Slot scheduling approach
  - [ ] Guard band calculation
- [ ] Design TDMA scheduler for LR2021
  - [ ] Dual-band frame: Sub-GHz + 2.4 GHz slots
  - [ ] Slot assignment: balloon as coordinator
  - [ ] Guard band: TX→RX turnaround time for LR2021
  - [ ] Clock source: GPS PPS (balloon) / LoRa ranging (ground station)
- [ ] Write design document: `mesh-stack/research/tdma/tdma-design.md`
- [ ] Create `tracker/firmware/components/tdma/` component
  - [ ] `tdma.h` — slot definitions, frame structure, timing constants
  - [ ] `tdma_scheduler.h/c` — slot scheduling, state machine
  - [ ] `tdma_clock.h/c` — GPS PPS clock discipline
- [ ] Host tests: slot timing, transitions, overlap detection
- [ ] Verify `idf.py build` passes

---

## Task 4: Erasure + Fragmentation Integration Pipeline

Wire up existing erasure coding and fragmentation components into a working pipeline.

- [ ] Design pipeline API: encode → fragment → (TX/RX) → defragment → decode
- [ ] Create `tracker/firmware/components/pipeline/` or integrate in existing
  - [ ] `tx_pipeline.h/c` — encode (Wirehair/PRBS23) → fragment → output frames
  - [ ] `rx_pipeline.h/c` — receive frames → defragment → decode → output data
  - [ ] Pipeline configuration: choose encoder (Wirehair vs PRBS23)
- [ ] Host integration test: full roundtrip
  - [ ] Create test data (500 bytes)
  - [ ] TX: encode → fragment → get frame list
  - [ ] Simulate: drop 30% of frames randomly
  - [ ] RX: feed remaining frames → defragment → decode → verify match
- [ ] Test with both Wirehair (host) and PRBS23-XOR
- [ ] Verify `idf.py build` passes

---

## Task 5: Tracker Serial Diagnostic Commands

Add interactive UART commands for debugging and status reporting.

- [ ] Design command set
  - [ ] `status` — show system state (uptime, battery, GPS fix, last TX)
  - [ ] `gps` — show GPS data (lat, lon, alt, sats, HDOP)
  - [ ] `telemetry` — dump current telemetry packet (hex + decoded fields)
  - [ ] `config` — show current Kconfig settings
  - [ ] `radio` — show radio state (frequency, SF, TX power, last RSSI/SNR)
  - [ ] `sleep` — force deep sleep cycle for testing
  - [ ] `help` — list all commands
- [ ] Create `tracker/firmware/components/cli/` component
  - [ ] `cli.h/c` — simple command parser (no dependencies)
  - [ ] Commands call into existing telemetry, GPS, radio functions
- [ ] Integrate in `app_main.cpp` — poll UART in main loop
- [ ] Verify `idf.py build` passes

---

## Task 6: Link Budget Calculator

Write a Python tool for flight planning.

- [ ] Create `tools/link_budget.py`
- [ ] Implement LoRa link budget calculations
  - [ ] Path loss (free space, 2.4 GHz and Sub-GHz)
  - [ ] LoRa sensitivity per SF/BW combination (from SX1262/SX1280 datasheets)
  - [ ] TX power, antenna gain, feed line loss
  - [ ] Link margin and expected range
- [ ] Implement throughput calculations
  - [ ] Air rate per SF/BW/CR
  - [ ] Time-on-air for given payload
  - [ ] Net throughput after headers, FEC, protocol overhead
- [ ] Command-line interface
  - [ ] Input: frequency, SF, BW, TX power, antenna gains, distance
  - [ ] Output: link margin, expected SNR, throughput, max range
- [ ] Pre-computed scenarios: Minimal tracker, Mesh V1, Mesh V2
- [ ] Document usage in script header

---

## Task 7: Ground Station JSON → Nostr Bridge Skeleton

Write the code that bridges received telemetry to Nostr events.

- [ ] Design Nostr event format for telemetry
  - [ ] kind 30023 (parameterized replaceable): balloon telemetry
  - [ ] Tags: callsign, altitude, voltage, position (geo:lat,lon)
  - [ ] Content: JSON telemetry or human-readable summary
- [ ] Create `tracker/ground-station/nostr_bridge/` directory
  - [ ] `nostr_event.py` — create and sign Nostr events (secp256k1)
  - [ ] `nostr_relay.py` — post events to relay (websocket)
  - [ ] `telemetry_to_nostr.py` — convert JSON telemetry → Nostr event
- [ ] Create ground station config
  - [ ] Nostr relay URL (configurable)
  - [ ] Ground station identity (nsec key)
  - [ ] Balloon callsigns to track
- [ ] Test: feed sample JSON → produce valid Nostr event
- [ ] Document setup in `tracker/ground-station/nostr_bridge/README.md`

---

## Progress Tracking

| Task | Status | Tests | Build |
|------|--------|-------|-------|
| 1. FIPS/microfips study | ✅ Complete | N/A | N/A |
| 2. Nostr event store | ✅ Complete | 7/7 | ✅ |
| 3. TDMA scheduler | ✅ Complete | 7/7 | ✅ |
| 4. Erasure+frag pipeline | ✅ Complete | 5/5 | ✅ |
| 5. Serial diagnostics | ✅ Complete | N/A | ✅ |
| 6. Link budget calculator | ✅ Complete | N/A | N/A |
| 7. JSON→Nostr bridge | ✅ Complete | N/A | N/A |

**All 7 tasks complete. 19/19 host tests passing. ESP-IDF build passes.**
