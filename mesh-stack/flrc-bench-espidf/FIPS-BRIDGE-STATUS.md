# FIPS-over-FLRC Bridge Status

## Current State: Bridge relay works, FIPS handshake pending

### Architecture
```
FIPS A (laptop) → /dev/ttyACM0 → ESP32-C3 bridge → LR2021 radio TX → ✓ WORKS
                                                                    ↓
FIPS B (laptop) ← /dev/ttyACM1 ← ESP32-C3 bridge ← LR2021 radio RX ← ✗ NOT DECODING
```

### What's Verified Working
- Bridge firmware correctly relays SLIP data between USB serial JTAG and LR2021 radio
- Manual test: sent 6-byte SLIP frame to ACM0, received 257-byte SLIP frame on ACM1
- FIPS A serial transport sends datagrams (confirmed in debug log: msg_id 1-4, 114 bytes each)
- FIPS A data arrives at ACM1 with correct FIPS magic (0xF1 0x50) — 524 bytes received
- Radio link is clean (0% PER in throughput tests)

### Root Cause of Handshake Failure (Under Investigation)
The bridge sends 255-byte fixed-length radio packets (padded with zeros).
FIPS B receives these but doesn't complete the handshake.

**Hypothesis 1 (most likely):** The 255-byte frame exceeds FIPS's SLIP decoder
`max_raw_len` when `fragment_payload_max < 238`. Setting it to 238 should fix this
(`max_raw_len = 13 + 238 + 4 = 255`), but handshake still fails.

**Hypothesis 2:** The radio's variable-length packet query returns wrong length.
The bridge queries `CMD_GET_RX_PKT_LENGTH` (0x0212) but the response format may
not match what we expect (2-byte big-endian vs little-endian).

**Hypothesis 3:** Console output (ESP_LOGI) on the USB serial JTAG interferes
with FIPS SLIP data. Both console and bridge data share the same USB pipe.
Console was disabled (CONFIG_ESP_CONSOLE_NONE=y) but handshake still failed —
though this might have been because the debug build wasn't actually flashed.

### Next Debugging Steps
1. Flash the debug build (already compiled, binary exists in build/)
2. Monitor bridge serial output on ACM1 to verify radio packets arrive
3. Check if FIPS magic (0xF1 0x50) is present in received radio data
4. If CRC fails → investigate radio data integrity
5. If no packets → investigate IRQ/RX task

### Files
- Bridge firmware: `mesh-stack/flrc-bench-espidf/main/fips_bridge.cpp`
- FIPS config A: `/home/c03rad0r/fips/.runtime/flrc-bridge/node-a.yaml`
- FIPS config B: `/home/c03rad0r/fips/.runtime/flrc-bridge/node-b.yaml`
- FIPS binary: `/home/c03rad0r/fips/target/debug/fips`

### Build Config
```
CONFIG_BENCH_MODE_FIPS_BRIDGE=y
CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y  (debug build, may interfere)
CONFIG_LOG_DEFAULT_LEVEL_INFO=y        (for bridge RX debug output)
fragment_payload_max: 238              (FIPS config, both nodes)
```
