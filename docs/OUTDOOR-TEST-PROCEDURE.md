# Outdoor Range Test Procedure

**Date:** 2026-07-21
**Firmware:** `rp2040-range-tx-auto` + `rp2040-range-rx-auto`
**Radio:** SX1280 FLRC, 2440 MHz, 2600 kbps, 255-byte packets, 12 dBm TX power
**Boards:** 2× RP2040 (serials E663B035977F242D and E663B035973B8332)

---

## Pre-Test (Indoors, ~10 min)

### 1. Flash Both Boards

```bash
cd ~/worktrees/balloon-range-tests/firmware/rp2040

# Plug in BOTH RP2040 boards via USB
# Acquire board lock so both are accessible
python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py acquire both

# Flash TX board (check which serial is which)
pio run -e rp2040-range-tx-auto -t upload --upload-port /dev/ttyACM0

# Flash RX board
pio run -e rp2040-range-rx-auto -t upload --upload-port /dev/ttyACM1
```

> **Note:** If upload ports are swapped, check `ls /dev/ttyACM*` and try both.
> If a board is stuck, hold BOOTSEL while plugging in to enter UF2 mode and
> copy the `.uf2` file from `.pio/build/rp2040-range-*-auto/firmware.uf2` manually.

### 2. Verify at 1 Meter

1. Place both boards 1m apart with antennas attached.
2. Open serial monitor on the RX board:
   ```bash
   pio device monitor -p /dev/ttyACM1 -b 115200
   ```
   (or use `screen /dev/ttyACM1 115200`)
3. You should see within a few seconds:
   - `BOOT RX RANGE AUTO`
   - `RADIO_INIT_OK (RX mode)`
   - `AUTO RX LISTENING`
   - `RX_WINDOW 0 START ...`
4. The TX board auto-starts 3 seconds after boot (LED countdown blink).
   You should see packets arriving on the RX serial:
   - `PKT 1 seq=0 rssi=-XX uptime=XXXXms`
   - `PKT 2 seq=1 rssi=-XX uptime=XXXXms`
   - ...
   - `RX_END DEADBEEF`
5. After each burst (500 packets + DEADBEEF marker), the RX prints a summary:
   ```
   =============================================
     Window:   0
     Received: 500 (unique 500, dup 0)
     TX sent:  500
     Lost:     0 (0.00%)
     Elapsed:  XXXX ms
     THROUGHPUT: XXXX.X kbps
     RSSI: avg=-XX.X dBm min=-XX dBm max=-XX dBm (n=500)
   =============================================
   ```
6. At 1m you should see **0% packet loss** and RSSI around -20 to -40 dBm.
   If you see 0% loss at 1m, you're ready to go outside.

### 3. Capture RX Serial Log

Start a serial log capture that will run for the entire outdoor test:

```bash
# On the computer connected to the RX board:
pio device monitor -p /dev/ttyACM1 -b 115200 | tee ~/range-test-$(date +%Y%m%d-%H%M).log
```

Keep this running for the entire test. All RX output (per-packet, burst summaries,
and structured `RANGE_RESULT_RX` lines) will be saved to the log file.

---

## During Test (Outdoors)

### Setup

1. **RX board** stays connected to the computer (laptop) via USB.
   - Antenna attached, placed on a stable surface (tripod, table, or box).
   - Serial monitor logging running (see Pre-Test step 3).
   - LED solid = radio OK, blink = packet received.

2. **TX board** is unplugged from the computer and plugged into a **USB power bank**.
   - Antenna attached.
   - On power-up: LED blinks for 3 seconds (countdown), then goes solid (transmitting).
   - TX sends 500-packet bursts, pauses 2 seconds, repeats forever.
   - No laptop needed — fully autonomous.

3. **Phone GPS**: Open a GPS tracking app (e.g., OsmAnd, GPS Logger, Strava).
   - Start recording a track BEFORE you begin walking.
   - The track will record your position over time.
   - You'll correlate GPS timestamps with the RX serial log timestamps.

### Test Distances

Walk away from the RX board to each distance marker. At each marker:

1. **Note the time** — look at your phone's GPS app and record the timestamp
   (to the second) when you arrive at the distance marker.
   Write it down or take a screenshot: "10m — 14:32:15"
2. **Stand still for ~30 seconds** — this ensures at least one full RX window
   (30s window) captures a complete burst while you're at that distance.
3. **Watch the RX LED** (if visible) or just wait — the RX is logging everything.
4. **Move to the next distance** — walk to the next marker and repeat.

| Distance | Min Dwell Time | What to Record |
|----------|----------------|----------------|
| 10 m     | 30 s           | GPS timestamp on arrival |
| 25 m     | 30 s           | GPS timestamp on arrival |
| 50 m     | 30 s           | GPS timestamp on arrival |
| 100 m    | 30 s           | GPS timestamp on arrival |

> **Tip:** If you have line-of-sight at 100m and still see 0% loss, try 200m+.
> If you see heavy loss at 50m, note it and still try 100m for comparison.

### LED Indicators (TX Board)

| LED State         | Meaning                        |
|-------------------|--------------------------------|
| Blinking (3s)     | Countdown — about to start TX  |
| Solid ON          | Transmitting (burst active)   |
| Off               | Pause between bursts (2s)     |
| Fast triple blink | Radio init failed (SOS pattern)|

### LED Indicators (RX Board)

| LED State         | Meaning                        |
|-------------------|--------------------------------|
| Blink on receive  | Packet received (brief flash)  |
| Solid ON (GP16)   | Radio initialized and listening|
| Fast triple blink | Radio init failed (SOS pattern)|

---

## Post-Test (Back Indoors)

### Data to Bring Back

1. **RX serial log** — the `~/range-test-*.log` file captured during the test.
   This contains all per-packet data, burst summaries, and structured result lines.

2. **GPS track export** — export your GPS track from your phone app as GPX or KML.
   This contains timestamps and positions for your entire walk.

3. **Your notes** — the timestamps you recorded at each distance marker.
   Example:
   ```
   10m  — arrived 14:32:15
   25m  — arrived 14:33:45
   50m  — arrived 14:35:30
   100m — arrived 14:38:00
   ```

### Data Correlation

The RX serial log includes `uptime_ms` timestamps on every line:
- `RX_WINDOW N START uptime=XXXXms` — when each 30s listening window began
- `PKT N seq=X rssi=-XX uptime=XXXXms` — per-packet timestamp
- `RANGE_RESULT_RX,window=N,...,uptime_ms=XXXX` — structured summary with timestamp

To correlate with GPS:
1. Note the wall-clock time when you started the RX serial monitor (the log file
   name includes a timestamp, e.g., `range-test-20260721-1430.log` → started 14:30).
2. RX `uptime_ms` = milliseconds since RX board booted.
3. Your GPS timestamps are wall-clock. Correlate by:
   `wall_clock = serial_monitor_start_time + (uptime_ms / 1000)`

Example: If serial monitor started at 14:30:00 and a `RANGE_RESULT_RX` line has
`uptime_ms=180000`, that corresponds to 14:30:00 + 180s = 14:33:00 wall clock.
If your GPS shows you were at 50m at 14:33:00, that result line is your 50m data point.

### Structured Output Format

Each burst produces a parseable CSV line:
```
RANGE_RESULT_RX,window=0,rx=500,unique=500,lost=0,total=500,per=0.00,elapsed_ms=1234,throughput_kbps=825.5,rssi_avg=-35.2,rssi_min=-38,freq=2440.0,bitrate=2600,pktSize=255,uptime_ms=5000
```

Fields:
- `window` — burst number (incrementing)
- `rx` — packets received
- `unique` — unique packets (excluding duplicates)
- `lost` — packets lost (total - received)
- `total` — total packets TX sent (from DEADBEEF marker)
- `per` — packet error rate (%)
- `elapsed_ms` — time span of received packets
- `throughput_kbps` — measured throughput
- `rssi_avg` — average RSSI (dBm)
- `rssi_min` — minimum (worst) RSSI (dBm)
- `freq` — frequency (MHz)
- `bitrate` — FLRC bitrate (kbps)
- `pktSize` — packet size (bytes)
- `uptime_ms` — RX board uptime at window start (ms)

---

## How to Change Bitrate (If Needed)

The default is FLRC 2600 kbps. If range is too short or too long, you can
reflash with a different bitrate. Supported options:

| Bitrate | `#define` value | Relative range | Relative speed |
|---------|----------------|-----------------|----------------|
| 2600    | 2600 (default) | Shortest        | Fastest        |
| 1300    | 1300           | ~1.4× range     | Half speed     |
| 650     | 650            | ~2× range        | Quarter speed  |
| 325     | 325            | Longest          | Slowest        |

To change, edit **both** source files:
- `src/flrc_range_tx_auto.cpp`: change `#define TX_BITRATE_KBPS 2600`
- `src/flrc_range_rx_auto.cpp`: change `#define RX_BITRATE_KBPS 2600`

Then rebuild and reflash both boards. TX and RX **must** use the same bitrate.

---

## Quick Reference: Flash Commands

```bash
cd ~/worktrees/balloon-range-tests/firmware/rp2040

# Build (already verified passing)
pio run -e rp2040-range-tx-auto
pio run -e rp2040-range-rx-auto

# Flash (replace /dev/ttyACM* with actual ports)
pio run -e rp2040-range-tx-auto -t upload --upload-port /dev/ttyACM0
pio run -e rp2040-range-rx-auto -t upload --upload-port /dev/ttyACM1

# Monitor RX
pio device monitor -p /dev/ttyACM1 -b 115200 | tee ~/range-test-$(date +%Y%m%d-%H%M).log
```

---

## Checklist

- [ ] Both boards flashed (TX-auto + RX-auto)
- [ ] 1m verification: 0% packet loss confirmed
- [ ] RX serial log capture started (tee to file)
- [ ] Phone GPS tracking started
- [ ] TX board plugged into power bank
- [ ] TX LED solid (transmitting) — confirmed before walking
- [ ] Walk to 10m — note GPS timestamp, dwell 30s
- [ ] Walk to 25m — note GPS timestamp, dwell 30s
- [ ] Walk to 50m — note GPS timestamp, dwell 30s
- [ ] Walk to 100m — note GPS timestamp, dwell 30s
- [ ] Return to RX board, stop serial log
- [ ] Export GPS track from phone (GPX/KML)
- [ ] Save notes with timestamps per distance