# HANDOVER: Range Testing Track (2026-07-18)

## STATUS: FIRMWARE READY — hardware baseline pending

Configurable TX+RX firmware written, built, committed, pushed. Both boards
were online during this session but disconnected before baseline could run.
Next operator needs to plug boards in, flash, verify 1m baseline, then
proceed to outdoor sweeps.

---

## WHAT WAS ACCOMPLISHED THIS SESSION

### 1. Configurable TX firmware
**File:** `firmware/rp2040/src/flrc_range_tx.cpp`
**PlatformIO env:** `rp2040-range-tx`
**Serial commands:**
- `POWER <dbm>` — TX power (0, 3, 6, 9, 12, 12.5)
- `PKTLEN <bytes>` — payload size (12-255)
- `FREQ <mhz>` — RF frequency (2400-2480)
- `BITRATE <kbps>` — FLRC bitrate (2600, 1300, 650, 325)
- `COUNT <n>` — packet count for next RUN
- `RUN` — transmit burst
- `STATUS` — print config
- `INIT` — re-init radio
- `HELP` — list commands

### 2. Configurable RX firmware
**File:** `firmware/rp2040/src/flrc_range_rx.cpp`
**PlatformIO env:** `rp2040-range-rx`
**Serial commands:**
- `FREQ <mhz>` — match TX frequency
- `PKTLEN <bytes>` — match TX payload size
- `BITRATE <kbps>` — match TX bitrate
- `LISTEN` (alias `RUN`) — enter RX mode
- `RESULTS` — re-print last results
- `STATUS` — print config + radio status
- `INIT` — re-init radio
- `HELP` — list commands

**RSSI readback:** GET_PACKET_STATUS (0x0104) after each packet.
RESULT_RX line includes `rssi_avg` and `rssi_min` in dBm.

### 3. Python range test runner
**File:** `scripts/range_test_runner.py`
**Commands:**
```bash
# Flash configurable firmware to both boards
python3 scripts/range_test_runner.py flash

# Query status
python3 scripts/range_test_runner.py status

# Single test point
python3 scripts/range_test_runner.py test --distance 50 --power 12

# Distance sweep (operator moves boards between points)
python3 scripts/range_test_runner.py sweep-distance 10 25 50 100

# TX power sweep at fixed distance
python3 scripts/range_test_runner.py sweep-power --distance 50 0 3 6 9 12

# Packet size sweep
python3 scripts/range_test_runner.py sweep-pktlen --distance 50 16 32 64 128 255

# Frequency sweep
python3 scripts/range_test_runner.py sweep-freq --distance 10 2400 2422 2440 2462 2480
```

Results saved to: `docs/range-test-results-YYYY-MM-DD.md` in RANGE_TEST format.

### 4. Commits (pushed to GitHub + ngit)
- `c80b78b` — initial configurable firmware + platformio.ini envs
- `c628fd7` — BITRATE command + RSSI readback + test runner

---

## WHAT THE NEXT OPERATOR MUST DO

### Step 1: Connect boards
Plug in both RP2040+LR2021 boards:
- TX: serial E663B035977F242D
- RX: serial E663B035973B8332

Verify: `for d in /dev/ttyACM*; do udevadm info -q property $d | grep SERIAL_SHORT; done`

### Step 2: Flash configurable firmware
```bash
cd ~/worktrees/balloon-range-tests
python3 scripts/range_test_runner.py flash
```
**NOTE:** picotool may need sudo. If flash fails:
```bash
# Enter BOOTSEL manually: hold BOOTSEL button while plugging USB
# Copy UF2 to RPI-RP2 mass storage:
cp firmware/rp2040/.pio/build/rp2040-range-tx/firmware.uf2 /tmp/rp2040-flash/
cp firmware/rp2040/.pio/build/rp2040-range-rx/firmware.uf2 /tmp/rp2040-flash/
```

### Step 3: Verify 1m baseline
```bash
python3 scripts/range_test_runner.py test --distance 1 --env indoor_bench
```
**Expect:** 0% packet loss, ~1300 kbps throughput, RSSI around -30 to -50 dBm.

If baseline fails, DO NOT proceed to outdoor tests. Debug radio init first.

### Step 4: Outdoor distance sweep
Follow: `docs/range-test-comprehensive-plan-2026-07-17.md`

---

## KEY TECHNICAL NOTES

### Init protocol
Both TX and RX use identical init sequence (same freq formula, sync word
0x12AD101B, packet params). The original RX firmware had a different freq
register format (4-byte raw Hz) — the configurable pair standardizes to
3-byte scaled frf matching TX. This may need 1m verification.

### CDC serial output
Known issue with earlephilhower core: USB CDC may not print until DTR is
asserted. If no serial output after flash:
```python
import serial
s = serial.Serial('/dev/ttyACM0', 115200)
s.dtr = True  # assert DTR
```
Or power-cycle the board (unplug/replug USB).

### Board lock
Mutex at `~/repos/balloon-fresh/tools/balloon-board-lock.py`.
Always acquire before using boards:
```bash
python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py acquire both --purpose "range test"
```

### Flashing requires BOOTSEL
RP2040 flash via picotool needs the board in BOOTSEL mode:
- 1200 baud touch on serial port (may not work without pyserial)
- Manual: hold BOOTSEL button while plugging USB
- ESP32-C3 controller can auto-trigger BOOTSEL (if wired per HARDWARE_CONNECTIONS.md)

---

## HARDWARE

| Item | Serial | Role |
|------|--------|------|
| RP2040+LR2021 | E663B035977F242D | TX board |
| RP2040+LR2021 | E663B035973B8332 | RX board |
| ESP32-C3 | 70:AF:09:21:FB:18 | BOOTSEL controller |
| ESP32-C3 | 70:AF:09:13:21:00 | BOOTSEL controller |

---

## WHAT NOT TO DO

- Don't change radio init params without testing at 1m first
- Don't proceed to outdoor sweeps if baseline fails
- Don't attempt throughput optimization — that's the speed-tests track
- Don't forget to match BITRATE between TX and RX (new param)

## LINKS

- Full plan: `docs/range-test-comprehensive-plan-2026-07-17.md`
- Previous handover: `docs/handover-range-testing-2026-07-17.md`
- Worktree: `~/worktrees/balloon-range-tests/`
- Branch: `range-tests`
- GitHub: `https://github.com/c03rad0r/balloon-fresh/tree/range-tests`
