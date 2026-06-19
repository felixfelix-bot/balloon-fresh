# FIPS-over-FLRC Validation & Flight Path Plan

**Created**: 2026-06-19
**Status**: Active

## Background

On 2026-06-19, we proved FIPS Noise XK handshake over FLRC radio (2.4 GHz, 2600 kbps). Two ESP32-C3 + LR2021 nodes established encrypted peer sessions via a SLIP→FLRC bridge firmware. This plan covers end-to-end validation, bridge hardening, and the path to first flight.

## What Worked

| Area | Result |
|------|--------|
| FIPS serial transport compile fix | `Err(_)` arm added to serial read match |
| fips_bridge.cpp RX padding fix | Parse FIPS header to trim to exact frame length |
| FIPS Noise XK handshake over FLRC | Both nodes promoted to active peers |
| Bidirectional traffic | 37B heartbeats, 114B/168B/200B/1071B datagrams |
| Multi-fragment datagrams | 1071B split into 5 SLIP frames, reassembled correctly |
| FLRC bench tests | 0% PER @ 20ms spacing, 838.8 kbps raw SPI |
| MeshCore LR2021 | 70+ community nodes, 7 targets build |
| StratoRelay utilities | 11/11 tests pass |
| Tracker firmware v0.2 | 17/17 tests, first telemetry RX |

## What Didn't Work / Is Blocked

- [x] TUN device as user — `Operation not permitted` (needs root or CAP_NET_ADMIN)
- [x] TUN stale routes — `fd00::/8` route from previous instance (`File exists`)
- [x] RADIOLIB_GODMODE — silently corrupts RX config
- [x] PlatformIO Arduino — can't TX with LR2021
- [x] Board MAC 96:DC — flaky USB
- [x] 160 MHz CPU — worse than 80 MHz (USB JTAG IRQ)

## Transport Architecture Decision

**Serial transport now, external_radio daemon later.**

- **Phase 1-2 (bench + first flight)**: Serial transport (FIPS owns MAC/TDMA)
- **Phase 3+ (mesh V1)**: External radio daemon (precise TDMA for multi-balloon)

---

## TRACK 1: End-to-End FIPS Mesh Validation

**Goal**: Prove real IP traffic (UDP) flows through the FLRC mesh via FIPS TUN.

### Step 1.1: Fix TUN Permissions & Stale Routes
- [x] Add pre-launch cleanup: remove stale routes, TUN devices, Unix sockets
- [x] Set CAP_NET_ADMIN on FIPS binary (`setcap cap_net_admin=eip`)
- [x] Fix TUN route conflict (fd00::/8 "File exists" — made non-fatal in tun.rs)
- [x] Verify both TUN interfaces come up (`fipsa`, `fipsb`)
- [x] Record IPv6 addresses: fipsa=fd12:ce2:..., fipsb=fdfd:fef7:...

### Step 1.2: Verify IPv6 Connectivity
- [x] `ip -6 addr show fipsa` / `ip -6 addr show fipsb` — both up
- [ ] `ping6 -I fipsa <fipsb_addr>` — measure RTT (blocked: both TUNs on same host, kernel shortcuts; needs netns isolation or 2 machines)
- [x] `ip -6 route show` — verified mesh routing
- [x] FIPS control socket: peer connected, MMP ETX=1.0, loss=0%
- [x] End-to-end session: **ESTABLISHED** (handshake_established=true, dataplane_proven=true)
- [x] Mesh forwarding: 22 packets / 1777 bytes delivered, 0% loss

### Step 1.3: UDP Throughput Measurement
- [x] iperf3 connected through mesh (UDP client/server)
- [ ] Meaningful throughput measurement (needs 2 separate machines — same-host kernel shortcuts TUN routing)
- [x] FIPS forwarding counters confirm traffic traversed radio link
- [ ] Test with different fragment_payload_max (48, 128, 238)

### Step 1.4: TCP Feasibility Test (informational)
- [ ] Try `iperf3 -c <fipsb> -t 10` (TCP)
- [ ] Document: confirms why UDP-only for balloon mesh

### Step 1.5: Stability Test
- [ ] Run iperf3 UDP for 10+ minutes
- [ ] Monitor FIPS logs: CRC errors, reassembly timeouts, connection drops
- [ ] Monitor bridge logs: serial errors, reconnections
- [ ] Record: packet loss %, throughput degradation over time

### Step 1.6: Document Results
- [ ] Update `mesh-stack/flrc-bench-espidf/RESULTS.md` with FIPS-over-FLRC section
- [ ] Record: handshake time, throughput, latency, packet loss
- [ ] Create ADR-014: FIPS Serial Transport over FLRC

---

## TRACK 2: Bridge Firmware Hardening

**Goal**: Production-quality serial→FLRC bridge, eliminate Python PTY bridge.

### Step 2.1: Eliminate Python Bridge
- [ ] Test if FIPS tokio_serial can open `/dev/ttyACM0` directly (CDC ACM)
- [ ] If yes: update node configs to use real devices, remove Python bridge
- [ ] If no: improve Python bridge (auto-reconnect, error handling) or write C/Rust PTY daemon

### Step 2.2: RadioLib-Based Bridge Firmware (**CRITICAL BLOCKER**)
- [x] Write RadioLib-based bridge firmware (replaces raw SPI TX/RX with `radio->transmit()` / `radio->readData()`)
- [x] Use variable packet length mode (no 255-byte padding)
- [x] Add radio mutex for thread-safe TX/RX
- [x] Add 15-second watchdog with full radio reinit
- [x] Build passes (idf.py build — SUCCESS)
- [ ] **FLASH TO HARDWARE** — BLOCKED: both ESP32-C3 boards have flaky USB connections
- [ ] Test RadioLib bridge stability (>30 min continuous operation)
- [ ] If stable: proceed with UDP throughput tests

### Step 2.3: Variable Packet Length Mode
- [x] Implemented in new RadioLib-based firmware (Step 2.2)

### Step 2.4: TX Completion via IRQ
- [x] RadioLib `transmit()` handles TX completion internally

### Step 2.5: Bridge Statistics
- [ ] Add counters: TX pkts, RX pkts, TX errors, RX CRC errors (in firmware)
- [ ] Output stats via serial on demand

---

## TRACK 3: GPS Integration Prep

**Goal**: GPS module soldered and working with tracker firmware.

### Step 3.1: Solder GPS Module
- [ ] Identify GPS module pins (VCC, GND, TX, RX)
- [ ] Wire: GPS TX → GPIO1, GPS RX → GPIO0
- [ ] Verify NMEA sentences on serial monitor

### Step 3.2: Outdoor GPS Fix Test
- [ ] Take board outdoors
- [ ] Verify cold-start fix time (< 30s clear sky)
- [ ] Verify NMEA parsing in tracker firmware

---

## TRACK 4: First Flight Planning

**Goal**: Tracker-only balloon in the air.

### Step 4.1: Balloon Prep
- [ ] Pre-stretch Yokohama 32" (pump to 100-105" circumference, hold 10-24h)
- [ ] Leak test: heat seal + pressure sensor, monitor 30-60 min
- [ ] Weight check: payload < net lift budget

### Step 4.2: Hardware Assembly
- [ ] Wire tracker breadboard per `docs/breadboard-wiring-guide.md`
- [ ] Cut wire dipole antenna (868 MHz: 8.6 cm legs)
- [ ] Power test: 3.3V stable under TX load
- [ ] Configure tracker: callsign, TX interval, frequency

### Step 4.3: Ground Range Test
- [ ] 100m, 500m, 1km, 5km with tracker on pole
- [ ] Record RSSI/SNR at each distance

### Step 4.4: Flight Prep
- [ ] HYSPLIT trajectory prediction
- [ ] Flight checklist per `docs/first-flight-checklist.md`
- [ ] File NOTAM if required
- [ ] Launch: Yokohama 32" + He 4.6, Minimal variant

---

## TRACK 5: Long-Term Architecture (Post-Flight)

### Step 5.1: Serial→Daemon Migration
- [ ] Port sx1280-serial daemon to LR2021 (Rust)
- [ ] Test daemon with external_radio transport on real hardware
- [ ] Compare TDMA precision: serial transport vs daemon

### Step 5.2: MeshCore + FIPS Coexistence
- [ ] Dual-band TDMA: Sub-GHz MeshCore + 2.4 GHz FIPS
- [ ] StratoRelayMesh implementation (B.8.9-B.8.17)
- [ ] Balloon telemetry over MeshCore (B.9)

### Step 5.3: Multi-Balloon Mesh
- [ ] Launch 2+ validated balloons
- [ ] Test inter-balloon relay
- [ ] MultiWAN bonding test
- [ ] Night-off / night-active modes
