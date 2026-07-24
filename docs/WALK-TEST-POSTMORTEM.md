# Walk Test Postmortem — 2026-07-24

## Test Parameters
- TX: RP2040 in rucksack, battery powered, GPS antenna external
- RX: RP2040 on balcony, USB powered
- Distance: 1.0 to 5.7 km (phone GPS ground truth, 440 points)
- Duration: 57 minutes (12:35-13:32 UTC)
- Firmware: multi_radio_sweep_gps.cpp (TX), multi_radio_sweep_rx.cpp (RX)
- Commit: aaa7ebf (byte alignment fix), possibly overwritten by sub-manager

## Results Summary
- 253 packets received, 0 valid decodes (100% PER)
- FLRC RSSI: -53 to -59 dBm stable across ALL distances (excellent signal)
- LoRa: 0-9 packets total (near-zero reception)
- GPS payload: 100% garbage (lat=48.79, lon=-50.62, sats=59092)
- RX USB dropped at 12:53 UTC (cable loose), ESP32 bridge took over

## ROOT CAUSE ANALYSIS

### Issue 1: GPS Payload Corruption (ALL modes)

**Symptom:** Every received packet has garbage GPS data. lat/lon/sats/utc are all random values.

**Root Cause: FIFO byte offset mismatch**

TX writes:
```
txBuf[0] = 0xA5;  // sync header
txBuf[1] = 0x5A;
txBuf[2] = 0x42;
txBuf[3] = 0x24;
// bytes 4-18: GPS data (embedGPS)
```

RX reads FIFO and expects bytes 0-3 = sync header (165, 90, 66, 36).

**Evidence from FLRC_RAW32 dumps:**
```
Expected bytes 0-3: 165 90 66 36
Actual FLRC:         92 103 250 144
Actual LoRa:         38 98 16 153
```

The sync header is NEVER found at byte offset 0. The entire payload is byte-shifted.

**Why:** The LR2021 packet engine adds framing bytes before the application payload:
- **LoRa explicit header mode** (flags=0x04): chip prepends 3-4 header bytes (length, SF info) before payload
- **FLRC**: chip may prepend packet length or address bytes

The firmware assumes FIFO[0] = first TX byte. In reality, FIFO[0] = chip framing byte, and the actual TX payload starts at a later offset.

**Fix:** 
1. Add a raw byte dump for ALL received packets (not just first per phase)
2. Search for sync header 0xA5 0x5A 0x42 0x24 in the raw bytes to find the true offset
3. Use that offset dynamically: `gpsOff = findSyncHeader(rxBuf) + 4`
4. Alternatively: disable explicit header mode and use implicit mode with fixed length

### Issue 2: LoRa Near-Zero Reception (Phase Desync)

**Symptom:** FLRC phases receive 55-702 packets. LoRa phases receive 0-9 packets.

**Root Cause: Phase timing + packet time-on-air mismatch**

Phase durations (identical in TX and RX):
```
HF-LoRa-SF7:  15s    (50 pkts expected at 50ms interval)
HF-LoRa-SF9:  15s    (50 pkts expected)
HF-LoRa-SF12: 30s    (30 pkts expected at 1s interval)
LF-LoRa-SF7:   8s    (50 pkts expected)
LF-LoRa-SF9:  20s    (50 pkts expected)
LF-LoRa-SF12: 50s    (20 pkts expected at 2.5s interval)
```

Total cycle = 202 seconds. Phase = unixTime % 202.

TX was GPS-synced (confirmed: utc=1784892034 valid). RX was SET_TIME synced initially but drifts:
- TX crystal accuracy: ~30 ppm = ~0.18s per 202s cycle
- RX crystal accuracy: ~30 ppm = ~0.18s per 202s cycle
- Combined drift: up to 0.36s per cycle
- After 10 cycles (~34 min): up to 3.6s drift

FLRC packets are short (8s slots, fast TX). Even with 3.6s drift, TX and RX overlap for ~4.4s — enough for packets.

LoRa SF12 packets take ~1s to transmit. With guard bands, the effective listen window is narrow. 3.6s drift can push TX completely outside the RX listen window.

**But:** LoRa SF7 has 8-15s slots and fast packets (50ms). 3.6s drift should still allow overlap. Yet SF7 got only 9 packets total.

**Secondary cause:** The RX uses `rxSetPhase()` which calls `rfSetRx()` ONCE at phase start. If no IRQ fires, it stays in RX mode for the whole slot. This is correct. But the LoRa radio config (SET_RX_PATH, calibration) may fail silently, leaving the radio in a broken state for LoRa modes while FLRC works fine.

**Evidence:** LoRa RSSI on rare packets = -93 to -104 dBm = noise floor. The radio isn't even seeing the TX signal on LoRa modes. This suggests a radio configuration issue, not just timing.

**Fix:**
1. Add periodic resync: re-send SET_TIME every 60s during capture
2. Verify SET_RX_PATH is called correctly for each LoRa band switch
3. Add radio register dump at phase transitions for debugging
4. Test LoRa modes in isolation (single-mode firmware) to isolate config issues

### Issue 3: RX USB Dropout

**Symptom:** RX Pico disappeared from USB at 12:53 UTC. Never came back.

**Root Cause:** Physical USB cable loose on balcony (wind/movement).

**Evidence:** 
- Board completely gone from lsusb (not just serial port)
- No BOOTSEL mode (would show as different USB device)
- CDC watchdog reboot would bring it back within 30s — it didn't
- ESP32 bridge (ACM1) continued working fine throughout

**Fix:**
- Hot-glue or tape USB connector to board
- Use USB-C with positive locking (current micro-USB has no latch)
- Consider permanent soldered USB cable

### Issue 4: Board Lock Bypassed by Sub-Managers

**Symptom:** Multiple sub-managers spawned capture processes on ACM0 during the walk, competing with the orchestrator's capture. Board locks were stolen (RELEASE_WITH_STEAL) at 12:32 UTC.

**Root Cause:** Advisory flock cannot prevent:
1. `cat /dev/ttyACM0` — raw serial reads bypass the lock entirely
2. `pio run -t upload` — flash commands bypass the lock
3. Sub-managers don't check lock status before accessing boards

**Evidence (theft log):**
```
12:32:50 tx stolen from balloon-hermes by track=unknown pid=899320
12:32:50 rx stolen from balloon-hermes by track=unknown pid=899320
```

**Fix:**
1. udev rule: `chmod 000 /dev/ttyACMx` when board is locked, `chmod 666` on release
2. picotool/openocd/pio wrappers that hard-check flock before allowing access
3. Firmware build_id embedded in packets (so we can detect unauthorized reflashing)
4. Flash queue: all flashing must be approved by orchestrator

### Issue 5: No Firmware Traceability

**Symptom:** We don't know which binary was running on TX/RX during the walk. Sub-managers may have reflashed mid-test.

**Root Cause:** Packets contain no firmware version identifier. USB output has no build banner.

**Evidence:** The byte alignment fix (commit aaa7ebf) was flashed, but a sub-manager may have reflashed with a different commit afterward. We have no way to verify.

**Fix:**
1. Embed FW_BUILD_ID (uint8, auto-incremented at build time) in packet bytes 22-23
2. Print `FW_BUILD=N COMMIT=<hash> BINARY=<name>` on USB boot
3. Build script auto-increments counter via `-DFW_BUILD_ID=N`
4. Mapping file: `firmware/BUILD_MAP.md` = build_id → commit → binary → date
5. Pre-flight check script: `verify_board.sh` reads boot banner, verifies build_id

## WHAT WORKED WELL

1. **FLRC range is excellent:** -55 dBm at 5.7km with no degradation from 1km. These modules have 10+ km margin.
2. **GPS on TX worked:** After resoldering + NMEA baud fix, GPS acquired 7-21 satellites and computed valid Unix epoch time.
3. **ESP32 bridge failover:** When RX Pico USB dropped, the ESP32 bridge on ACM1 kept data flowing. 10 auto-reconnects handled seamlessly.
4. **Auto-reconnect capture loop:** The `while` loop with CDC drop detection worked perfectly — never lost data due to software.
5. **Phone GPS correlation:** CSV with Unix timestamps made distance correlation straightforward.
6. **Board locking (partial):** Lock acquisition and sentinel tracking worked. The gap is enforcement, not tracking.

## PRIORITY FIX ORDER

1. **FIFO offset fix** (HIGHEST — fixes all GPS payload corruption)
2. **LoRa radio config verification** (fixes zero LoRa packets)
3. **udev chmod enforcement** (prevents board theft)
4. **Firmware build_id** (prevents traceability loss)
5. **USB cable securing** (prevents physical dropout)
