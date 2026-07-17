# Balloon Project — Kanban Board

## Track 1 — Radio Link (balloon-hermes)
### Done
- [x] Baseline proven: 1377 kbps, 0% packet loss, bench distance
- [x] Coordinated TX/RX test harness (scripts/coordinated_tx_rx_test.py)
- [x] LR2021 FLRC reference documented
- [x] PIO/DMA approach abandoned (air time dominates, not SPI)

### In Progress
- [ ] Configurable TX firmware (serial commands: POWER, PKTLEN, FREQ, COUNT, RUN)

### TODO
- [ ] Verify baseline at 1m
- [ ] Outdoor distance sweep: 10m, 25m, 50m, 100m
- [ ] Power sweep
- [ ] Packet size sweep
- [ ] Frequency sweep
- [ ] Modulation comparison (FLRC vs LoRa)
- [ ] Antenna comparison

---

## Track 2 — Nostr Relay (balloon-nostr)
### TODO
- [ ] Read + understand wisp-esp32 codebase (components/, main/)
- [ ] Build wisp-esp32 standalone on ESP32-S3
- [ ] Verify: WebSocket connections accepted, events stored/served, subscriptions work
- [ ] Benchmark: memory usage, flash usage, concurrent connection limit
- [ ] Port wisp_relay to ESP32-C3 (4MB flash, 400KB RAM)
- [ ] Verify C3 port: relay accepts connections, stores in LittleFS
- [ ] Report porting constraints to coordinator

---

## Track 3 — Tollgate/Cashu (balloon-tollgate)
### TODO
- [ ] Read esp32-tollgate AGENTS.md + understand architecture
- [ ] Identify which components are needed for balloon (captive portal, DNS, Cashu)
- [ ] Test captive portal + payment flow on ESP32-S3 (already works on 3 boards)
- [ ] Extract core components (strip display, cvm_server, mining)
- [ ] Port extracted components to ESP32-C3
- [ ] Verify: captive portal works, Cashu token validation works, DNS hijack works
- [ ] Report porting constraints to coordinator

---

## Track 4 — PoW/Mining (balloon-pow)
### TODO
- [ ] Read sw_miner.c, stratum_client.c, asic_miner.c
- [ ] Extract mining components from esp32-tollgate into standalone build
- [ ] Test software SHA256 mining on ESP32-S3: verify hashrate, share submission
- [ ] Test Stratum v2 connection: verify handshake, job distribution
- [ ] Benchmark: hashrate, power consumption, heat
- [ ] Test ASIC (BM1366) interface if hardware available
- [ ] Port to ESP32-C3 (if feasible — C3 has limited RAM for SHA256)
- [ ] Report feasibility + hashrate expectations to coordinator

---

## Track 5 — FIPS Mesh (balloon-fips)
### TODO
- [ ] Read microfips-esp32c3 crate (crates/, docs/)
- [ ] Understand core protocol (M0-M11): Noise IK/XK, FSP sessions
- [ ] Identify transport interface: how UART/BLE/WiFi/ESPNOW transports plug in
- [ ] Design LR2021 transport adapter (LoRa packet transport for FIPS mesh)
- [ ] Implement LR2021 transport using RadioLib (already proven in balloon-fresh)
- [ ] Test: two ESP32-C3 nodes communicate via LR2021 using FIPS protocol
- [ ] Benchmark: latency, throughput, mesh hop count
- [ ] Report feasibility + mesh topology to coordinator

---

## Track 6 — Blossom Server (balloon-blossom)
### TODO
- [ ] Read BUD-02 protocol spec (Blossom server media upload)
- [ ] Read NIP-96 for media attachment specs
- [ ] Study Python uploader at ~/repos/prta-review/lib/blossom_publisher.py
- [ ] Design minimal ESP32 Blossom server (HTTP upload, LittleFS storage, auth)
- [ ] Implement: BUD-02 PUT /upload endpoint with kind 24242 auth
- [ ] Implement: BUD-01 GET /<sha256> download endpoint
- [ ] Test: upload file from client, retrieve it, verify integrity
- [ ] Port to ESP32-C3 (storage limited to LittleFS partition)
- [ ] Report storage constraints + feasibility to coordinator

---

## Cross-Track Dependencies
- Track 5 (FIPS) depends on Track 1 (radio link proven) for LR2021 transport
- Track 6 (Blossom) depends on Track 2 (Nostr relay) for event publishing
- Final integration (here) depends on ALL tracks passing standalone tests
- No integration begins until each track reports "standalone verified"
