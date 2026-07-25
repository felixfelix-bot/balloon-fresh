# V4 Firmware Status — 2026-07-25

## What V4 Does

V4 adds **dynamic packet size sweeping** across all 14 radio modes × 4 payload sizes (32/64/128/255 bytes) = **56 test phases**. This lets us characterize how packet error rate (PER), throughput, and bit error rate (BER) vary with payload size for each modulation mode.

## Base Mode vs Interleave Mode

### BASE MODE (SET_INTERLEAVE 0)
- TX sends 255B packets on ONE fixed radio mode (LF-FLRC-2600) continuously
- RX listens on the same mode continuously
- Simple, no phase transitions, no time sync needed
- Use case: quick link validation, range testing at max payload

### INTERLEAVE MODE (SET_INTERLEAVE 1)
- TX and RX both cycle through 56 phases sequentially
- Each phase = one radio mode + one payload size (e.g., phase 0 = HF-FLRC-2600-32B)
- Each phase gets a time slot (duration varies by mode: 10s for fast modes, 60s+ for LoRa SF12)
- Both boards compute current phase from: `phase = (unix_time % cycle_duration) / slot_duration`
- Requires both boards to have same epoch time (SET_TIME)
- **NOT round-robin**: it's sequential. All packets in phase 0, then all in phase 1, etc.

## V4 Changes from V3

1. **Interleave table**: 14 modes × 4 sizes = 56 phases with air-time-aware pktCount
2. **SET_INTERLEAVE serial command**: 0=base 255B, 1=56-phase sweep
3. **Dynamic pktSize per phase** from interleave table
4. **Extended CRC-16**: covers full variable payload (bytes 4 to pktSize-3)
5. **BER fill pattern**: bytes 29 to pktSize-3 filled with known pattern for bit error analysis
6. **LF-LoRa-SF12 at >32B auto-skipped** (104s/pkt impractical)

## CRC-16 Architecture

Both TX and RX use identical CRC-16-CCITT (polynomial 0x1021, init 0xFFFF).

### TX Packet Layout (255B example)
```
Bytes 0-3:   Sync header (0xA5 0x5A 0x42 0x24)
Bytes 4-18:  GPS data (lat, lon, sats, fixQ, utcSec)
Byte  19:    Phase ID
Bytes 20-21: Sequence number (uint16 BE)
Bytes 22-28: Firmware git hash (7 ASCII chars)
Bytes 29-252: BER fill pattern (byte[i] = i & 0xFF)
Bytes 253-254: CRC-16 (uint16 BE) over bytes 4-252
Byte 255:    (not used — pktSize=255 means bytes 0-254)
```

For 32B packets: same layout, but CRC covers bytes 4-29 (26 bytes), stored at bytes 30-31.

### RX Verification
1. Scan for sync header (0xA5 0x5A 0x42 0x24) in receive buffer
2. Extract gpsOff = syncOffset + 4
3. Read expected CRC from `rxBuf[syncOffset + pktSize - 2..-1]`
4. Compute CRC over `rxBuf[gpsOff..gpsOff + pktSize - 6]`
5. Compare → PASS or FAIL

## Bug Found + Fixed (2026-07-25)

### TX Radio Init Hardcoded pktSize
**Bug**: TX `rfInitForPhase()` used `LORA_PKT_SIZE=255` and `FLRC_PKT_SIZE=255` in
SET_LORA_PACKET_PARAMS and SET_FLRC_PACKET_PARAMS commands, instead of the dynamic
`p.pktSize` from the interleave table.

**Effect**: When TX entered a phase with pktSize=32, the radio chip was still configured
for 255-byte payloads. TX wrote 32 bytes to the FIFO, but the radio framed/padded for 255.
RX received 255 bytes of garbage beyond the actual 32-byte payload.

**Fix**: Changed TX init to use `(uint8_t)p.pktSize`:
```cpp
// Before (BUG):
uint8_t c[] = {0x02, 0x21, 0x00, 0x08, LORA_PKT_SIZE, flags};
// After (FIX):
uint8_t c[] = {0x02, 0x21, 0x00, 0x08, (uint8_t)p.pktSize, flags};
```

RX was already correct — it uses dynamic `p.pktSize`.

## Verification Status

### Base Mode (255B) — VERIFIED WORKING
- TX sends 255B packets on LF-FLRC-2600
- RX receives with sync header found, sequential seq numbers
- CRC PASSES (first packet verified, confirmed "PKT rx=" output)
- RSSI values reported (-40 to -121 dBm depending on distance)

### Interleave Mode — PARTIALLY WORKING
- Phase computation works (both boards cycle through 56 phases)
- TX sends correct pktSize per phase (verified via phase names in output)
- RX receives packets in most phases
- **Issue**: RX sometimes stays in base mode after SET_INTERLEAVE command
  (command may not be reliably received). Re-sending the command fixes it.

## Time Synchronization

Both boards use `SET_TIME <unix_epoch>` to set their internal clock. Phase is computed as:
```cpp
int phase = (unix_now % CYCLE_SECONDS) / slot_seconds;
```

**Time source priority:**
1. Laptop NTP time (via SET_TIME serial command) — accurate to <1s
2. GPS time (when GPS has fix) — accurate to <1ms with PPS

**No bidirectional RF sync needed.** Both boards have independent reference clocks.
The 1-8s drift observed was from GPS time being wrong (no fix indoors), not from
SET_TIME imprecision. Laptop NTP is reliable.

## Files

- `firmware/rp2040/src/multi_radio_sweep_gps_v4.cpp` — TX firmware (962 lines)
- `firmware/rp2040/src/multi_radio_sweep_rx_v4.cpp` — RX firmware (1061 lines)
- `firmware/rp2040/platformio.ini` — build environments
- `scripts/plot_v4_interleave.py` — proof plot generator (PER/throughput/BER vs size)
- `data/v4-interleave-bench/` — captured test data

## Board Assignment
- TX: F242D (serial E663B035977F242D) — multi_radio_sweep_gps_v4.cpp
- RX: 8332 (serial E663B035973B8332) — multi_radio_sweep_rx_v4.cpp
