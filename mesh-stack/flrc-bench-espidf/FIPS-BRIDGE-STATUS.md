# FIPS-over-FLRC Bridge Status

## Current State: FIPS session ESTABLISHED, 30-min link survival proven

### v4 Firmware Test Results (2026-06-19)
- **30-minute stability test**: PASS — peer link survived entire duration
- **Valid-frame watchdog**: Working — radio auto-resets after 15s of noise-only RX
- **Active data exchange**: First ~5 minutes (24 packets delivered, 0% loss, ETX=1.0)
- **RX degradation after ~5 min**: Known limitation of raw SPI TX approach
- **TX stability**: 99 packets sent over 30 min with zero errors
- **Auto-reconnect**: FIPS maintains peer connection across watchdog resets

### Architecture
```
FIPS A (laptop) → PTY → Python bridge → USB CDC → ESP32-C3 bridge → LR2021 radio TX → ✓ WORKS
                                                                                ↕ (air, 2.4 GHz)
FIPS B (laptop) ← PTY ← Python bridge ← USB CDC ← ESP32-C3 bridge ← LR2021 radio RX ← ✓ WORKS
```

### What's Verified Working (2026-06-19)
- FIPS Noise XK handshake over FLRC: **PROVEN** (both nodes promoted to active peer, ~22s)
- End-to-end session: **ESTABLISHED** (handshake_established=true, dataplane_proven=true)
- Mesh forwarding: 22 packets / 1777 bytes delivered, **0% loss, ETX=1.0**
- iperf3 UDP connectivity through mesh
- Multi-fragment datagrams (1071B split into 5 SLIP frames, reassembled correctly)
- Both TUN interfaces (fipsa, fipsb) with IPv6 addresses

### Bridge Firmware Version History

| Version | TX Method | Watchdog | Result |
|---------|-----------|----------|--------|
| v1 (original) | Raw SPI, 900µs delay | None | Works ~5 min, then radio locks up |
| v2 | Raw SPI, 900µs, startReceive() after TX | IRQ-based 15s | Works ~5 min, watchdog doesn't fire (noise IRQs keep it alive) |
| v3 | RadioLib transmit() | Valid-frame 15s | TX collisions (~15ms TX time), link dead immediately |
| **v4 (current)** | **Raw SPI, 1200µs, jitter TX, startReceive()** | **Valid-frame 15s (FIPS magic check)** | **Pending test** |

### v4 Stability Fixes Applied

1. **Valid-frame watchdog**: `lastValidRxMs` only updates when FIPS magic (0xF1 0x50 0x01) is detected. Noise/garbage IRQs don't prevent watchdog from firing.
2. **TX jitter**: 0-3ms random delay before each TX (`esp_random() % 3000`). Reduces collisions between the two nodes.
3. **Noise packet suppression**: Packets without FIPS magic are silently dropped (not SLIP-encoded, not sent to serial). Eliminates serial flooding.
4. **Sub-GHz compile option**: Uncomment `#define BRIDGE_BAND_SUBGHZ` for 868 MHz operation (less WiFi interference, +22 dBm TX power).

### Known Limitations

- **Radio lockup**: Raw SPI TX eventually corrupts LR2021 state (3-5 min). v4 watchdog should auto-recover.
- **Flaky USB**: Both ESP32-C3 boards have intermittent USB connections. Flash when USB is stable.
- **Python PTY bridge required**: tokio_serial can't read USB CDC ACM directly. Python bridge (serial_bridge.py) converts CDC ACM ↔ PTY.
- **Same-host TUN shortcut**: Both TUNs on one machine → kernel delivers locally, bypassing mesh. Use 2 machines or network namespaces for real throughput.

### Files
- Bridge firmware: `mesh-stack/flrc-bench-espidf/main/fips_bridge.cpp`
- Python PTY bridge: `mesh-stack/flrc-bench-espidf/serial_bridge.py`
- FIPS config A: `/home/c03rad0r/fips/.runtime/flrc-bridge/node-a.yaml`
- FIPS config B: `/home/c03rad0r/fips/.runtime/flrc-bridge/node-b.yaml`
- FIPS binary: `/home/c03rad0r/fips/target/debug/fips` (with cap_net_admin)
- Launch script: `/tmp/run_flrc_test.sh`
- Results: `mesh-stack/flrc-bench-espidf/RESULTS.md` (FIPS-over-FLRC section)
