# Walk Test Fix Plan — Priority Order

## Status: AWAITING SUB-MANAGER DISPATCH
Created: 2026-07-24 after 5.7km walk test postmortem

## Fixes (priority order)

### 1. FIFO Byte Offset Fix (range-tests) — HIGHEST
- Sync header 0xA5 0x5A 0x42 0x24 NOT at byte 0 in received FIFO
- LR2021 packet engine prepends framing bytes
- Fix: search for sync header dynamically in rxBuf
- Fixes: ALL GPS payload corruption

### 2. LoRa Radio Config Verification (range-tests)
- LoRa phases show noise floor RSSI (-93 to -104 dBm)
- Radio may not be configured correctly for LoRa modes
- Fix: dump radio registers at phase transitions, verify SET_RX_PATH

### 3. udev chmod Enforcement (speed-tests) — FASTEST
- Advisory flock bypassed 5+ times today
- Fix: chmod 000 /dev/ttyACMx on lock, chmod 666 on release
- Prevents: board theft by sub-managers

### 4. Flash Wrapper Enforcement (speed-tests)
- pio-flash.sh is voluntary, sub-managers bypass it
- Fix: PATH wrapper intercepts pio/picotool/openocd

### 5. Firmware build_id (range-tests)
- Can't verify which binary was running during walk
- Fix: -DFW_BUILD_ID=N in build flags, embed in packets bytes 22-23

## What Worked (no changes needed)
- FLRC range: -55 dBm at 5.7km, zero degradation. 10+ km margin.
- GPS on TX: valid epoch, 7-21 sats
- ESP32 bridge failover: kept capture alive after RX USB dropout
- Auto-reconnect capture loop: seamless CDC handling
- Phone GPS correlation: perfect timestamp alignment
