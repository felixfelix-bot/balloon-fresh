# E80 Range Test Operator Guide

> **Self-contained onboarding guide.** Everything you need to run a
> distributed E80 LoRa/FLRC range test — from zero to merged data —
> using only this repo and two laptops.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Hardware Setup](#2-hardware-setup)
3. [Prerequisites by OS](#3-prerequisites-by-os)
4. [Quick Start](#4-quick-start)
5. [Flashing the Board](#5-flashing-the-board)
6. [Running the TX Side](#6-running-the-tx-side)
7. [Running the RX Side](#7-running-the-rx-side)
8. [How T0 Sync Works](#8-how-t0-sync-works)
9. [Config Presets](#9-config-presets)
10. [Data Format](#10-data-format)
11. [Prime Discard (AGC Warmup)](#11-prime-discard-agc-warmup)
12. [Merging TX + RX Logs](#12-merging-tx--rx-logs)
13. [GPS Recording & Stitching](#13-gps-recording--stitching)
14. [Packaging Data for Sharing](#14-packaging-data-for-sharing)
15. [Make Target Reference](#15-make-target-reference)
16. [Troubleshooting](#16-troubleshooting)
17. [Test Results Reference](#17-test-results-reference)
18. [Quick Reference Cheat Sheet](#18-quick-reference-cheat-sheet)

---

## 1. Overview

The E80 range test measures packet error rate (PER), RSSI, SNR, and bit
errors across multiple modulation schemes (FLRC and LoRa) at various
distances. It uses two E80 boards — one as TX, one as RX — each
connected to a separate computer. The boards are **interchangeable**:
there is no factory TX/RX labeling. Role is set at runtime by software.

Each operator runs a single `make` command. The system auto-computes a
synchronized start time (T0) — no communication needed between
operators beyond starting within 4 minutes of each other.

### What you need

| Item | Qty | Notes |
|------|-----|-------|
| E80-STM32 bench board | 2 | One per machine. Boards are interchangeable. |
| Computer (laptop, mini PC) | 2 | One per board. Linux, macOS, or Windows. |
| USB cables | 2 per board | CH340 USB-serial (data) + CMSIS-DAP/Pico SWD probe (debug). Both must be plugged in for `make tx`/`make rx`. |
| Phone with GPS | 1 | Optional, for distance measurement. Any GPS app that exports GPX or KML. |

### E80 board anatomy

The E80 board contains:

- **STM32F103C8** microcontroller
- **LR2021** radio (Semtech LoRa Gen 4) — supports LoRa and FLRC modulation
- **CH340** USB-serial chip — data port for host communication
- **Raspberry Pi Pico** (CMSIS-DAP debugprobe) — SWD port for flashing + resets

Both USB connections are required during normal operation:
- The **CH340** port carries serial commands and data between host and board.
- The **Pico SWD probe** allows the host to reset the board between
  modulation switches (important when mixing LoRa and FLRC configs).

For `make flash` (firmware flashing), only the SWD probe needs to be
connected. For `make tx` / `make rx`, both must be plugged in.

---

## 2. Hardware Setup

### Connecting a board

1. Plug the **CH340 USB-serial cable** into the board's serial port and
   into a USB port on the computer.
2. Plug the **CMSIS-DAP SWD probe** (Raspberry Pi Pico) into the board's
   SWD header and into another USB port on the same computer.
3. Repeat for the second board on the second computer.

### Finding the serial port

#### Linux

```bash
# List all USB-serial devices
ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null

# Identify the CH340 specifically
for d in /dev/ttyUSB*; do
  udevadm info -q property -n "$d" 2>/dev/null | grep -q CH340 && echo "CH340: $d"
done
```

Expected output:
```
CH340: /dev/ttyUSB3
```

> **Permission denied?** See [Troubleshooting](#permission-denied-on-devttyusb-linux).

#### macOS

```bash
ls /dev/cu.usbserial* /dev/cu.usbmodem* 2>/dev/null
```

Typical output:
```
/dev/cu.usbserial-1420       # CH340 data port — use this one
/dev/cu.usbmodem123456781    # CMSIS-DAP probe (ignore for serial)
```

The CH340 port name contains `usbserial` — that's your data port.

#### Windows (Git Bash)

Open **Device Manager** → Ports (COM & LPT). Look for a "USB-SERIAL
CH340" entry. Note the COM port number (e.g., `COM5`).

In Git Bash, the port will be referenced as `/dev/ttyS5` (the COM
number minus the prefix). However, `make tx` / `make rx` auto-detects
the port — you should not need to specify it manually.

### Verifying the board is alive

```bash
# Linux:
python3 -c "import serial; s=serial.Serial('/dev/ttyUSB3', 115200, timeout=2); \
print(s.read_until(b'OK').decode(errors='replace')[:80] or '(no banner — try ID?)')"

# macOS:
python3 -c "import serial; s=serial.Serial('/dev/cu.usbserial-1420', 115200, timeout=2); \
print(s.read_until(b'OK').decode(errors='replace')[:80] or '(no banner — try ID?)')"
```

If you see `OK` or the board's banner text, the connection is good.

> **Note on baud rate:** The firmware console runs at **2,000,000
> baud** (since firmware commit `0561b29`). The auto-detection in
> `make tx` / `make rx` handles this automatically. If you're manually
> sending commands, use `2000000` as the baud rate. Older firmware
> versions used `115200`.

---

## 3. Prerequisites by OS

### Linux (Debian / Ubuntu / Raspberry Pi OS)

```bash
# System packages
sudo apt update
sudo apt install -y git python3 python3-pip gcc-arm-none-eabi openocd

# Python serial library
pip3 install --user pyserial

# If you hit PEP-668 "externally managed" error:
pip3 install --user --break-system-packages pyserial
# OR use a virtualenv:
#   python3 -m venv ~/e80env && source ~/e80env/bin/activate && pip install pyserial
```

### macOS

```bash
# Command Line Tools (includes git)
xcode-select --install

# Python + toolchain via Homebrew
brew install python openocd arm-none-eabi-gcc

# Python serial library
pip3 install --user pyserial
# On newer macOS, if pip3 is not found:
python3 -m pip install --user pyserial
```

### Windows

1. **Install Git for Windows**: <https://git-scm.com/download/win>
   - Run all commands below inside **Git Bash** (the Makefile uses
     shell syntax that MSYS understands).

2. **Install Python 3**: <https://www.python.org/downloads/>
   - During install, check "Add Python to PATH".
   - In Git Bash: `pip3 install --user pyserial`

3. **Install openocd** (for flashing + board resets):
   - Download from [xpack-dev-tools/openocd-xpack](https://github.com/xpack-dev-tools/openocd-xpack/releases)
   - Extract to e.g. `C:\opt\xpack-openocd\`
   - Add the `bin` folder to your PATH

4. **Install arm-none-eabi-gcc** (for firmware compilation, only if
   you need to flash):
   - Download from [xpack-dev-tools/arm-none-eabi-gcc-xpack](https://github.com/xpack-dev-tools/arm-none-eabi-gcc-xpack/releases)
   - Extract and add to PATH

5. **CH340 driver**: Windows should auto-install the CH340 driver on
   first plug-in. If not, download from
   <https://www.wch-ic.com/downloads/CH341SER_EXE.html>.

### Verify prerequisites

```bash
git --version
python3 --version
python3 -c "import serial; print('pyserial', serial.__version__)"

# Only needed for flashing / SWD resets:
openocd --version
arm-none-eabi-gcc --version
```

---

## 4. Quick Start

After prerequisites are installed, the full flow is:

```bash
# Clone the repo
git clone https://github.com/felixfelix-bot/balloon-fresh.git
cd balloon-fresh/firmware/e80-stm32-bench
git checkout feat/2g4-sweep

# One-time: flash the board (needs both USB cables connected)
make flash

# Run the test — T0 + SESSION_ID are auto-generated
make tx       # on the TX machine
make rx       # on the RX machine (run within 4 min of make tx)
```

That's it. The system will:
1. Auto-detect the board's serial port and SWD probe.
2. Compute T0 = next 5-minute epoch boundary (both machines compute the
   same value independently).
3. Beep a countdown at T-10, T-5, T-4, T-3, T-2, T-1 seconds.
4. Run the test according to the config preset.
5. Write results to `tx-log.csv` (TX side) or `rx-log.csv` (RX side).

After the test, merge the logs:
```bash
make range-merge RX=rx-log.csv TX=tx-log.csv
```

---

## 5. Flashing the Board

> Firmware must be flashed once before first use, and re-flashed after
> any firmware update. Only the SWD probe needs to be connected for
> flashing (but having both plugged in is fine).

```bash
cd firmware/e80-stm32-bench
make flash
```

This will:
1. Cross-compile the firmware using `arm-none-eabi-gcc` + CMake.
2. Flash the resulting binary to the board via SWD using `openocd`.
3. Verify the firmware by querying the board's `ID?` response.

### What you need for flashing

| Prerequisite | Linux | macOS | Windows |
|---|---|---|---|
| arm-none-eabi-gcc | `sudo apt install gcc-arm-none-eabi` | `brew install arm-none-eabi-gcc` | xpack release (see above) |
| openocd | `sudo apt install openocd` | `brew install openocd` | xpack release (see above) |
| CMake | `sudo apt install cmake` | `brew install cmake` | <https://cmake.org/download/> |

### Common flash errors

| Error | Fix |
|---|---|
| `arm-none-eabi-gcc not found` | Install the cross-compiler (see [Prerequisites](#3-prerequisites-by-os)). |
| `openocd not found` | Install openocd. |
| `Error: open failed` | Check that the SWD probe USB cable is plugged in securely. |
| Flash succeeds but `ID?` returns nothing | The CH340 cable may not be plugged in. Plug in both USB cables and retry. |

---

## 6. Running the TX Side

On the TX machine:

```bash
cd firmware/e80-stm32-bench
make tx
```

You'll see output like:

```
╔══════════════════════════════════════════════╗
║  E80 TX MODE — waiting for T0               ║
╠══════════════════════════════════════════════╣
║  T0:           1724515500 (epoch)
║  SESSION_ID:   2408241425
║  Configs:      /path/to/configs/outdoor-10.json
║  Band:         868 MHz
║  Prime discard: 2
╚══════════════════════════════════════════════╝
T0 in 240s (4m 0s). RX operator should run: make rx
Countdown: 240s remaining
T-10 T-5 T-4 T-3 T-2 T-1 GO!
```

The TX side:
- Auto-detects the board's serial port and SWD probe.
- Sends test packets according to the config preset schedule.
- Writes a summary log to `tx-log.csv`.

### Customizing TX

```bash
# Use a different config preset
make tx CONFIGS=configs/indoor-baseline.json

# Override band (default 868)
make tx BAND=915

# Disable prime discard (for LoRa SF12 with long airtime)
make tx PRIME_DISCARD=0

# Explicit T0 + session ID (for debugging — usually not needed)
make tx T0=1724515500 SESSION_ID=2408241425

# Different output log filename
make tx TX_LOG=my-tx-log.csv
```

### Keeping the laptop awake

If the laptop suspends during the test, the schedule is lost.

**Linux:**
```bash
systemd-inhibit --what=sleep --mode=block make tx
```

**macOS:**
```bash
caffeinate -i make tx
```

**Windows:** Use a power plan that doesn't sleep. Or run in a
terminal that inhibits idle sleep.

---

## 7. Running the RX Side

On the RX machine:

```bash
cd firmware/e80-stm32-bench
make rx
```

Output is similar to TX mode but shows `RX MODE`:

```
╔══════════════════════════════════════════════╗
║  E80 RX MODE — waiting for T0               ║
╠══════════════════════════════════════════════╣
║  T0:           1724515500 (epoch)
║  SESSION_ID:   2408241425
║  Configs:      /path/to/configs/outdoor-10.json
║  Band:         868 MHz
║  Prime discard: 2
╚══════════════════════════════════════════════╝
T0 in 235s (3m 55s). TX operator should run: make tx
```

The RX side:
- Auto-detects the board's serial port and SWD probe.
- Arms the radio and captures incoming packets.
- Writes one CSV row per received packet to `rx-log.csv` (flushed
  immediately — partial data survives an abort).

### Customizing RX

Same variables as TX:

```bash
make rx CONFIGS=configs/indoor-baseline.json
make rx BAND=915
make rx PRIME_DISCARD=0
make rx RX_LOG=my-rx-log.csv
```

### Aborting

Press `Ctrl-C` at any time. The script writes `# ABORTED by operator`
into the log and stops cleanly. Partial data is preserved in the CSV.

### Preventing laptop sleep (RX side is more sensitive)

The RX side must stay awake for the entire test window. Use the same
sleep-inhibition commands as TX:

```bash
# Linux:
systemd-inhibit --what=sleep --mode=block make rx

# macOS:
caffeinate -i make rx
```

---

## 8. How T0 Sync Works

The T0 synchronization is **deterministic and communication-free**.

### Algorithm

Both `make tx` and `make rx` independently compute:

```
T0 = (next 5-minute epoch boundary from current time)
```

Specifically: `T0 = (floor(now / 300) + 1) * 300` (Unix epoch seconds).

Both machines get the **same T0** as long as:
1. Their clocks are NTP-synced (within ~1 second).
2. They start `make tx` / `make rx` within 4 minutes of each other.

The `SESSION_ID` is derived from T0: `strftime('%y%m%d%H%M', gmtime(T0))`.
Both machines compute the same session ID.

### Countdown beeps

The terminal emits audible beeps (`\a` / bell character) at:
- **T-10** seconds
- **T-5** seconds
- **T-4** seconds
- **T-3** seconds
- **T-2** seconds
- **T-1** second
- Then prints `GO!`

This helps operators know the test is about to start without watching
the screen.

### Clock sync verification

Before the test, verify your clock is synced:

```bash
# Linux:
timedatectl status      # look for "System clock synchronized: yes"

# macOS:
sntp time.apple.com     # offset should be < ±0.1s

# Windows:
w32tm /query /status    # look for "Last Successful Sync Time"
```

### What if clocks drift?

If one machine's clock is off by more than ~60 seconds past T0, the
lateness guard catches it and reports an error. The test won't start
with bad timing — you'll get a clear error message, not silently
corrupted data.

### Manual T0 override

For debugging or manual coordination, you can set T0 explicitly:

```bash
make tx T0=1724515500 SESSION_ID=2408241425
make rx T0=1724515500 SESSION_ID=2408241425
```

Both sides must use the same values. This bypasses the auto-computed
5-minute boundary.

---

## 9. Config Presets

Config presets are JSON files that define the test schedule: which
modulations, how many packets per config, payload length, TX power,
frequency, and inter-packet gap.

### Available presets

#### `configs/outdoor-10.json`

Outdoor range test — 10 packets per config, 868 MHz EU SRD.

| # | Label | Modulation | Bitrate/SF | BW | PA | Payload | Gap | Packets |
|---|-------|-----------|------------|-----|-----|---------|-----|---------|
| 0 | FLRC-650 LEN64 | FLRC | 650 kbps | — | 10 dBm | 64 B | 5 ms | 10 |
| 1 | FLRC-2600 LEN64 | FLRC | 2600 kbps | — | 10 dBm | 64 B | 5 ms | 10 |
| 2 | LoRa-SF7 BW125 | LoRa | SF7 | 125 kHz | 10 dBm | 64 B | 10 ms | 10 |
| 3 | LoRa-SF12 BW125 | LoRa | SF12 | 125 kHz | 10 dBm | 64 B | 10 ms | 10 |
| 4 | FLRC-650 LEN255 | FLRC | 650 kbps | — | 10 dBm | 255 B | 5 ms | 10 |

Total: 50 packets across 5 configs. Duration: ~2-3 minutes.

#### `configs/indoor-baseline.json`

Indoor bench baseline — 1000 packets per config, 868 MHz.

| # | Label | Modulation | Bitrate/SF | BW | PA | Payload | Gap | Packets |
|---|-------|-----------|------------|-----|-----|---------|-----|---------|
| 0 | FLRC-650 LEN255 | FLRC | 650 kbps | — | 10 dBm | 255 B | 5 ms | 1000 |
| 1 | LoRa-SF7 BW125 | LoRa | SF7 | 125 kHz | 10 dBm | 64 B | 10 ms | 1000 |

Total: 2000 packets. Duration: ~15-30 minutes. Used for long-run
statistical baseline measurements.

### Using a custom config

```bash
make tx CONFIGS=/path/to/my-config.json
make rx CONFIGS=/path/to/my-config.json
```

Both sides must use the same config file. The config format is
self-documenting — see `configs/outdoor-10.json` as a template.

### Config field reference

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Preset name (informational) |
| `description` | string | Human-readable description |
| `band` | string | Frequency band: "868", "915", "433" |
| `configs` | array | Array of config objects (see below) |
| `configs[].label` | string | Short label for reports |
| `configs[].mod` | string | Modulation: "flrc" or "lora" |
| `configs[].sf` | int/null | LoRa spreading factor (7-12), null for FLRC |
| `configs[].bw` | int/null | LoRa bandwidth in kHz (125, 250, 500), null for FLRC |
| `configs[].br` | int/null | FLRC bitrate in kbps (260, 325, 650, 1300, 2600), null for LoRa |
| `configs[].pa` | int | TX power in dBm |
| `configs[].freq` | int | Frequency in Hz |
| `configs[].plen` | int | Payload length in bytes (max 255) |
| `configs[].gap` | int | Inter-packet gap in milliseconds |
| `configs[].n_pkts` | int | Number of packets to send per config |

---

## 10. Data Format

### RX log CSV (`rx-log.csv`)

One row per received packet. Comment lines (starting with `#`) contain
metadata about the session.

**Column order:**

```
session,config,pkt_idx,ts_ms,rssi_dbm,snr_db,crc_ok,bit_err,freq_hz,mod,sf_or_br,bw,pa_dbm,len,pcrc16,captured_ts
```

| Column | Type | Description |
|--------|------|-------------|
| `session` | string | Session ID (e.g. `2608231820`) |
| `config` | int | Config index (0-based, from preset) |
| `pkt_idx` | int | Packet index within config (starts at 2 when prime_discard=2) |
| `ts_ms` | int | Firmware uptime in milliseconds (since board boot) |
| `rssi_dbm` | float | Received signal strength in dBm |
| `snr_db` | float | Signal-to-noise ratio in dB (LoRa only; 0.0 for FLRC) |
| `crc_ok` | int | 1 = CRC valid, 0 = CRC error |
| `bit_err` | int | Bit errors from PRBS15 verification |
| `freq_hz` | int | Frequency in Hz |
| `mod` | string | Modulation: "FLRC" or "LORA" |
| `sf_or_br` | int | LoRa spreading factor or FLRC bitrate (kbps) |
| `bw` | int | LoRa bandwidth in kHz (0 for FLRC) |
| `pa_dbm` | int | TX power in dBm |
| `len` | int | Payload length in bytes |
| `pcrc16` | int | Payload CRC16 (expected) |
| `captured_ts` | string | ISO-8601 timestamp when host captured the packet (wall-clock) |

**Example rows:**
```
session,config,pkt_idx,ts_ms,rssi_dbm,snr_db,crc_ok,bit_err,freq_hz,mod,sf_or_br,bw,pa_dbm,len,pcrc16,captured_ts
# DISTRIBUTED_RX_MODE t0=2026-08-23T20:05:00 port=/dev/ttyUSB1 probe=203584200D2D0D42
2608232005,0,2,334846,-42.0,0.0,1,0,868000000,FLRC,650,0,10,64,0,2026-08-23T20:06:09
2608232005,0,3,339846,-41.0,0.0,1,0,868000000,FLRC,650,0,10,64,0,2026-08-23T20:06:14
```

The `captured_ts` column is the join key for GPS stitching.

### TX log CSV (`tx-log.csv`)

One row per config (summary). Columns:

```
session,config,label,mod,sf_or_br,bw,pa_dbm,freq_hz,plen,n_pkts,gap_ms,prime_discard,sent_ts
```

### Merged output (`combined.csv`)

After `make range-merge`, the merged file has one row per expected
packet (received or lost):

| Column | Description |
|--------|-------------|
| `session` | Session ID |
| `config` | Config index |
| `pkt_idx` | Packet index (0-based) |
| `status` | `received` or `lost` |
| `rssi_dbm` | RSSI (or empty if lost) |
| `snr_db` | SNR (or empty if lost) |
| `crc_ok` | CRC status |
| `bit_err` | Bit errors |
| `freq_hz` | Frequency |
| `mod` | Modulation |
| `sf_or_br` | SF or bitrate |
| `bw` | Bandwidth |
| `pa_dbm` | TX power |
| `len` | Payload length |
| `label` | Config label from preset |
| `n_pkts` | Expected packets for this config |

A human-readable report is also generated: `combined-range-report.md`.

---

## 11. Prime Discard (AGC Warmup)

The LR2021 radio's automatic gain control (AGC) needs 1-2 packets to
settle at the start of each burst. Without compensation, the first few
packets show depressed RSSI or elevated CRC errors, biasing PER.

### How it works

- `PRIME_DISCARD=2` (default): the TX sends 2 extra "prime" packets
  before the measured window for each config. The RX receives them but
  discards them from the log.
- With `PRIME_DISCARD=2`, `pkt_idx` in the CSV starts at 2 (indices 0
  and 1 are the discarded prime packets).
- Prime packets are still counted toward the total airtime but NOT
  toward PER.

### When to disable

Set `PRIME_DISCARD=0` for:
- **LoRa SF12**: airtime is so long (1+ seconds) that AGC settles within
  the first packet's preamble.
- **Controlled bench tests** where you want every packet logged.

```bash
make tx PRIME_DISCARD=0
make rx PRIME_DISCARD=0
```

> **Both sides must use the same `PRIME_DISCARD` value.** If TX sends
> prime packets but RX doesn't expect them (or vice versa), the
> packet index alignment will be off.

---

## 12. Merging TX + RX Logs

After both sides complete the test, collect both log files on one
machine and merge:

```bash
make range-merge RX=rx-log.csv TX=tx-log.csv
```

This runs `tools/merge_csvs.py` which:
1. Joins TX and RX logs on `(session, config, pkt_idx)`.
2. Counts missing RX packets as lost → contributes to PER.
3. Flags foreign packets (wrong session) as anomalies.
4. Outputs `combined.csv` (machine-readable) and
   `combined-range-report.md` (human-readable).

### Merge report example

```markdown
# E80 Distributed Range Test — Merge Report

## Summary

| Metric | Value |
|--------|-------|
| Total expected | 50 |
| Total received | 50 |
| Total lost | 0 |
| Overall PER | 0.0% |
| Foreign packets | 0 |

## Per-Config Results

| Config | Label | N | Received | Lost | PER | RSSI avg | SNR avg |
|--------|-------|---|----------|------|-----|----------|---------|
| 0 | FLRC-650 LEN64 | 10 | 10 | 0 | 0% | -20.0 | 0.0 |
| 1 | FLRC-2600 LEN64 | 10 | 10 | 0 | 0% | -21.0 | 0.0 |
| 2 | LoRa-SF7 BW125 LEN64 | 10 | 10 | 0 | 0% | -22.0 | 15.5 |
| 3 | LoRa-SF12 BW125 LEN64 | 10 | 10 | 0 | 0% | -24.0 | 18.0 |
| 4 | FLRC-650 LEN255 | 10 | 10 | 0 | 0% | -20.0 | 0.0 |
```

### Custom output directory

```bash
make range-merge RX=rx-log.csv TX=tx-log.csv OUT_DIR=results/
```

---

## 13. GPS Recording & Stitching

GPS tracking is optional but recommended for outdoor tests. It lets
you correlate signal quality with distance from the TX.

### Recording GPS

1. **Sync your phone clock** to network time (Settings → Date & Time →
   "Set automatically"). Phones do this by default.
2. **Start recording ~1 minute before T0.**
3. **Walk or ride along the planned route** during the test.
4. **Stop recording ~1 minute after the last config ends.**
5. **Export the track** as GPX or KML.

### Recommended GPS apps

| App | Platform | Output | Notes |
|-----|----------|--------|-------|
| [BasicAirData GPS Logger](https://play.google.com/store/apps/details?id=eu.basicairdata.gpslogger) | Android | GPX/KML | Free, no account. Recommended. |
| [OsmAnd](https://osmand.net) | Android / iOS | GPX | Free, open-source. Trip recording. |
| [GPX Tracker](https://apps.apple.com/app/gpx-tracker/id1114695369) | iOS | GPX | Free, simple. |
| [Open GPX Tracker](https://f-droid.org/packages/io.github.dyessc.gpx_tracker/) | Android (F-Droid) | GPX | No account needed. |

### Stitching GPS to packet data

After the test, stitch the GPS track onto the RX log:

```bash
make range-stitch \
    RX=rx-log.csv \
    GPS=track.kml \
    TX_GPS=52.0123,4.0456 \
    OUT=rx-with-gps.csv
```

This:
- Joins each packet row with the nearest GPS fix by timestamp.
- Adds `gps_lat`, `gps_lon`, `gps_ele`, `gps_time`, `gps_offset_s`
  columns.
- If `TX_GPS` is provided, adds `dist_m` (haversine distance from TX
  reference point to the matched GPS point).

### GPS format support

The `gps_stitch.py` tool auto-detects the format:

| Format | Extension | Source | Notes |
|--------|-----------|--------|-------|
| GPX 1.1 | `.gpx` | Most GPS apps | Parsed with stdlib XML. |
| KML | `.kml` | BasicAirData GPS Logger | Parsed with stdlib XML. |
| CSV | `.csv` | Manual or app export | Header auto-detected: `timestamp`/`time`/`ts`, `lat`/`latitude`, `lon`/`lng`/`longitude`, `ele`/`elevation`/`alt` |

### Manual GPS CSV (worst case)

If you have no tracker, write a CSV by hand:

```
timestamp,lat,lon,ele
2026-08-30T14:00:00Z,52.0123,4.0456,5.2
2026-08-30T14:02:00Z,52.0124,4.0457,5.4
```

The `timestamp` column accepts ISO-8601 (`...Z` or with offset) or a
Unix epoch number. `ele` is optional.

### Firmware uptime fallback

If the RX log only has `ts_ms` (firmware uptime) and no `captured_ts`,
use `--t0-epoch` to map uptime onto absolute time:

```bash
python3 tools/gps_stitch.py \
    --rx rx-log.csv \
    --gps track.gpx \
    --t0-epoch 1724515500
```

This is rarely needed — `captured_ts` is the preferred join key and is
always present in current firmware.

---

## 14. Packaging Data for Sharing

After the RX side completes, package the data as a zip for the TX
operator (or for archival):

```bash
make range-zip \
    RX=rx-log.csv \
    GPS=track.kml \
    SITE=outdoor-test \
    OPERATOR=alice
```

This produces a timestamped zip like `20260824T143000Z_outdoor-test.zip`
containing:
- `rx-log.csv` — the packet log
- `track.kml` (or `.gpx`) — your GPS track (if provided)
- `metadata-XXXX.txt` — operator name, host OS, repo git SHA, file
  sizes, and the RX log header for sanity-checking

### Without `make` or `zip`

```bash
# Using tar (Linux / macOS):
tar czf range-session.tgz rx-log.csv track.kml

# Using Python (always available):
python3 -c "import zipfile; z=zipfile.ZipFile('range.zip','w'); \
z.write('rx-log.csv'); z.write('track.kml'); z.close()"
```

---

## 15. Make Target Reference

All commands run from `firmware/e80-stm32-bench/`.

### Core targets

| Target | Description | Requires |
|--------|-------------|----------|
| `make flash` | Build + flash firmware via SWD | arm-none-eabi-gcc, openocd, SWD probe |
| `make tx` | TX mode — auto-generates T0 + SESSION_ID | Board (CH340 + SWD), pyserial |
| `make rx` | RX mode — auto-generates T0 + SESSION_ID | Board (CH340 + SWD), pyserial |
| `make range-dry-run` | Preview schedule without hardware | Python only |
| `make range-merge` | Merge TX + RX logs, compute PER, generate report | TX + RX log files |
| `make range-stitch` | Stitch GPS track onto RX log | RX log + GPS file |
| `make range-zip` | Package RX log + GPS + metadata as zip | RX log file |
| `make range-test-host` | Run pytest unit tests | Python + pytest |
| `make firmware` | Cross-compile firmware only (no flash) | arm-none-eabi-gcc, cmake |
| `make test-host` | Build + run C unit tests with host gcc | gcc, cmake |
| `make clean` | Remove build artifacts | — |
| `make range-coord` | Print T0 + SESSION_ID for manual sharing | Python only |

### Common variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CONFIGS` | `configs/outdoor-10.json` | Path to config preset |
| `BAND` | `868` | Frequency band in MHz |
| `T0` | Auto (next 5-min boundary) | Start time as Unix epoch |
| `SESSION_ID` | Auto (derived from T0) | Session identifier |
| `PRIME_DISCARD` | `2` | Number of AGC warmup packets to discard |
| `TX_LOG` | `tx-log.csv` | TX output log filename |
| `RX_LOG` | `rx-log.csv` | RX output log filename |
| `RX` | (required for merge/stitch/zip) | RX log path |
| `TX` | (required for merge) | TX log path |
| `GPS` | (optional) | GPS track file path |
| `TX_GPS` | (optional) | TX reference coordinates `lat,lon` |
| `SITE` | `unknown` | Site label for zip filename |
| `OPERATOR` | `whoami` | Operator name for metadata |
| `OUT` | (auto) | Output path for stitch |
| `OUT_DIR` | `.` | Output directory for merge |

### Examples

```bash
# Default outdoor test with auto T0
make tx
make rx

# Indoor baseline with 1000 pkts per config
make tx CONFIGS=configs/indoor-baseline.json
make rx CONFIGS=configs/indoor-baseline.json

# Preview the schedule without hardware
make range-dry-run

# Merge after the test
make range-merge RX=rx-log.csv TX=tx-log.csv

# Stitch GPS
make range-stitch RX=rx-log.csv GPS=track.kml TX_GPS=52.0123,4.0456

# Package for sharing
make range-zip RX=rx-log.csv GPS=track.kml SITE=fieldA OPERATOR=alice

# Run unit tests
make range-test-host

# Print T0 + session for manual coordination
make range-coord
```

---

## 16. Troubleshooting

### "no CH340 serial port found"

**Cause:** The CH340 USB-serial cable is not plugged in or not
detected by the OS.

**Fix:**
1. Plug in the **CH340 USB-serial cable** (not just the SWD probe).
   Both USB cables must be connected.
2. **Linux:** Check `ls /dev/ttyUSB*` — you should see at least one port.
   Run `dmesg | grep ch341` to see if the kernel recognized the device.
3. **macOS:** Check `ls /dev/cu.usbserial*` — you should see a port
   with `usbserial` in the name.
4. **Windows:** Check Device Manager → Ports (COM & LPT) for a
   "USB-SERIAL CH340" entry. If missing, install the CH340 driver from
   <https://www.wch-ic.com/downloads/CH341SER_EXE.html>.
5. Try a different USB port or cable — some USB-C-to-A adapters don't
   pass through serial.

### "timeout waiting for reply to SESSION"

**Cause:** The board is hung or in a bad state.

**Fix:**
1. Power-cycle the board: **unplug both USB cables**, wait 2 seconds,
   **replug both**.
2. If you have `openocd` installed, the script will attempt an SWD reset
   automatically. If not:
   - **Linux:** `sudo apt install openocd`
   - **macOS:** `brew install openocd`
   - **Windows:** Install from [xpack-dev-tools](https://github.com/xpack-dev-tools/openocd-xpack/releases).
3. Retry `make tx` or `make rx`.

### "probe says role=TX, but target was RX"

**Cause:** This was an issue in older firmware where the board retained
its role from the previous session. **This is now fixed.** Boards are
interchangeable — role is set at runtime by the software (`make tx`
sets TX, `make rx` sets RX).

**Fix:** Update firmware with `make flash`. If the error persists,
power-cycle the board.

### `make flash` fails: "arm-none-eabi-gcc not found"

**Fix:** Install the ARM cross-compiler:

| OS | Command |
|----|---------|
| Linux | `sudo apt install gcc-arm-none-eabi` |
| macOS | `brew install arm-none-eabi-gcc` |
| Windows | Download from [xpack-dev-tools](https://github.com/xpack-dev-tools/arm-none-eabi-gcc-xpack/releases) |

### Permission denied on `/dev/ttyUSB*` (Linux)

**Cause:** Your user is not in the `dialout` group.

**Fix:**
```bash
sudo usermod -aG dialout "$USER"
# Then log out and back in, or:
newgrp dialout
```

### `pip3 install --user pyserial` fails with "externally managed"

**Cause:** Debian 12+ enforces PEP-668.

**Fix:**
```bash
# Option 1: bypass (simplest)
pip3 install --user --break-system-packages pyserial

# Option 2: virtualenv (cleaner)
python3 -m venv ~/e80env
source ~/e80env/bin/activate
pip install pyserial
# Run make with the venv's python:
make rx PYTHON=~/e80env/bin/python
```

### Board reboots / no packets received mid-test

**Cause:** The LR2021 radio cannot hot-switch modulation (LoRa ↔ FLRC)
via a serial command — the firmware accepts the change but the radio
stays on the old config.

**Fix:** The test script handles this by issuing an SWD reset between
modulation-changing configs, but only if `openocd` is installed. If you
can't install openocd:
1. Use a config preset that doesn't mix LoRa and FLRC, OR
2. Manually unplug + replug the board's USB between configs.

### GPS stitch complains "nearest GPS point is N seconds away"

**Cause:** Your phone clock or laptop clock drifted relative to each
other.

**Fix:**
1. Check that both devices have automatic time sync enabled.
2. The stitch still produces output — the `gps_offset_s` column tells
   you the actual offset per packet so you can filter bad matches.
3. For future tests, verify clock sync before starting (see
   [How T0 Sync Works](#8-how-t0-sync-works)).

### CH340 cable shows up but no data comes through

1. Verify the baud rate — current firmware uses **2,000,000 baud**.
2. Make sure the TX side is actually running — coordinate via phone.
3. Try swapping the two boards' roles (boards are interchangeable, role
   is set by software).
4. Check that both boards are on the same frequency band (`BAND=868` on
   both sides).

### `make` says "T0 required"

This should not happen with current Makefile (T0 is auto-computed). If
you see it, you may be overriding `T0=` with an empty value. Just run
`make tx` or `make rx` without the `T0=` parameter.

### Windows-specific: Git Bash can't find `make`

Install `make` for Windows:
- Via [Chocolatey](https://chocolatey.org): `choco install make`
- Via [MSYS2](https://www.msys2.org): `pacman -S make`
- Or download from [xpack-dev-tools/make-xpack](https://github.com/xpack-dev-tools/make-xpack/releases)

### macOS: `python3` not found after `brew install python`

Homebrew's Python may not be on your PATH. Fix:
```bash
# Add Homebrew to PATH (Apple Silicon):
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"

# Or use the full path:
/opt/homebrew/bin/python3 -m pip install --user pyserial
```

---

## 17. Test Results Reference

### Session 2608231820 (single-machine benchmark)

| Metric | Value |
|--------|-------|
| Date | 2026-08-23 |
| Session ID | 2608231820 |
| Config | outdoor-10.json |
| Total expected | 50 |
| Total received | 50 |
| PER | 0% |
| Bit errors | 0 |
| RSSI range | -20 to -24 dBm |
| LoRa SNR range | 15-18 dB |
| Board | Single machine, both boards on one host |

This session demonstrated clean 0% PER at close range (indoor/bench)
with the outdoor-10 config preset. The data is archived in
`docs/hardware-test-data/rx-single-machine-2608231820.csv`.

### Interpretation guide

| Metric | Good | Marginal | Bad |
|--------|------|----------|-----|
| PER | 0-5% | 5-30% | >30% |
| RSSI | >-80 dBm | -80 to -100 dBm | <-100 dBm |
| LoRa SNR | >10 dB | 0-10 dB | <0 dB |
| Bit errors | 0 | 1-10 | >10 |

---

## 18. Quick Reference Cheat Sheet

```bash
# ── One-time setup ──────────────────────────────────────────────
# Linux:
sudo apt install git python3 python3-pip gcc-arm-none-eabi openocd cmake
pip3 install --user pyserial

# macOS:
xcode-select --install
brew install python openocd arm-none-eabi-gcc cmake
pip3 install --user pyserial

# Windows (Git Bash):
# Install Git for Windows, Python 3, pyserial, openocd, arm-none-eabi-gcc
pip3 install --user pyserial

# ── Clone + flash ───────────────────────────────────────────────
git clone https://github.com/felixfelix-bot/balloon-fresh.git
cd balloon-fresh/firmware/e80-stm32-bench
git checkout feat/2g4-sweep
make flash          # needs both USB cables, one-time

# ── Run the test ───────────────────────────────────────────────
# TX machine:
make tx             # auto T0 + SESSION_ID

# RX machine (within 4 minutes of TX):
make rx

# ── After the test ──────────────────────────────────────────────
# Merge logs:
make range-merge RX=rx-log.csv TX=tx-log.csv

# Stitch GPS (optional):
make range-stitch RX=rx-log.csv GPS=track.kml TX_GPS=52.0,4.05

# Package for sharing:
make range-zip RX=rx-log.csv GPS=track.kml SITE=outdoor OPERATOR=alice

# ── Preview / debug ────────────────────────────────────────────
make range-dry-run              # see schedule without hardware
make range-coord                # print T0 + SESSION_ID
make range-test-host            # run unit tests

# ── Find serial port ───────────────────────────────────────────
# Linux:
for d in /dev/ttyUSB*; do udevadm info -q property -n "$d" 2>/dev/null \
  | grep -q CH340 && echo "CH340: $d"; done

# macOS:
ls /dev/cu.usbserial* /dev/cu.usbmodem* 2>/dev/null

# ── Fix permissions (Linux) ────────────────────────────────────
sudo usermod -aG dialout "$USER" && newgrp dialout
```

---

## Appendix: Repository

- **Repo:** <https://github.com/felixfelix-bot/balloon-fresh>
- **Branch:** `feat/2g4-sweep`
- **Path:** `firmware/e80-stm32-bench/`
- **Tools:** `firmware/e80-stm32-bench/tools/`
- **Configs:** `configs/` (at repo root)

### Key files

| File | Description |
|------|-------------|
| `Makefile` | All make targets — the primary entry point |
| `tools/e80_bench_ctl.py` | Main test controller (TX + RX logic) |
| `tools/e80_detect.py` | Board auto-detection (port + role) |
| `tools/countdown.py` | T0 countdown with terminal beeps |
| `tools/merge_csvs.py` | TX + RX log merger + PER report |
| `tools/gps_stitch.py` | GPS track stitching onto RX log |
| `configs/outdoor-10.json` | Outdoor preset (5 configs, 10 pkts each) |
| `configs/envelope-4cfg-max.json` | 4-config envelope — max payload per modulation |
| `configs/indoor-baseline.json` | Indoor preset (2 configs, 1000 pkts each) |
| `tools/cvm_board_server.py` | CVM (Nostr MCP) board server — remote control |
| `tools/test_cvm_config_provider.py` | Tests for set_config MCP tool |
| `tools/test_cvm_campaign_dynamic_config.py` | Tests for dynamic config pushing via set_config |

---

## CVM Config Provider Mode

The CVM board server (`tools/cvm_board_server.py`) exposes board tools over
Nostr relays using gift-wrapped JSON-RPC (NIP-44/NIP-59). This enables a remote
coordinator (Hermes LLM or script) to push configs to TX/RX boards over the
internet instead of using static `--configs` files.

### set_config MCP Tool

The `set_config` tool accepts a config preset and pushes MOD/FREQ/PA/ROLE
commands to the board. Two modes:

1. **config_name** — server looks up `configs/<name>.json` on its filesystem:
   ```json
   {"config_name": "envelope-4cfg-max"}
   ```

2. **config_json** — coordinator sends the full config preset inline:
   ```json
   {"config_json": "{\"name\":\"...\",\"configs\":[...]}"}
   ```

The tool sends `MOD LORA <sf> <bw>` or `MOD FLRC <br> <pa>`, then `PA <dbm>`
(LoRa only), `FREQ <hz>`, and `ROLE <TX|RX>` for each config entry, returning
per-entry responses (label, commands sent, board replies).

### Usage

```bash
# Start CVM server on TX machine (optionally load an initial config):
CVM_SERVER_HEX=<hex_secret> make range-cvm-server ROLE=tx CONFIGS=envelope-4cfg-max

# Start CVM server on RX machine:
CVM_SERVER_HEX=<hex_secret> make range-cvm-server ROLE=rx CONFIGS=envelope-4cfg-max

# Remote coordinator runs the adaptive sweep (config JSON passed inline):
CVM_CLIENT_HEX=<hex_secret> make range-adaptive TX_NPUB=npub1... RX_NPUB=npub1... CONFIGS=envelope-4cfg-max
```

`range-cvm-server` accepts `CONFIGS` (a config preset name or path) and applies
it as the board's **initial config** at startup via the `set_config` tool, so
the board boots into a known radio state before the coordinator connects.
`range-adaptive` reads the same `CONFIGS` and passes the config preset to the
coordinator **inline as JSON** (`--configs-json`, derived from the `CONFIGS_JSON`
Makefile variable). This lets the coordinator run on a third machine without
having the config file present locally.

The Makefile derives `CONFIGS_JSON` from `CONFIGS` by shelling out to python —
no separate file to keep in sync. If `CONFIGS` is a bare preset name (e.g.
`envelope-4cfg-max`), it is resolved against `configs/` first.

CVM is an optional layer — `make tx` / `make rx` work without it using
fixed-schedule mode. CVM enhances with real-time remote config changes when
internet is available (e.g. lab WiFi or phone hotspot in the field).

### Dynamic Config Pushing (cvm_campaign.py)

The CVM campaign coordinator (`tools/cvm_campaign.py`) uses `set_config` to
push each config entry to both TX and RX boards dynamically. For each config
in the preset:

1. Coordinator calls `set_config` on both TX and RX with the single config
   entry as inline JSON (`config_json` mode)
2. Each board server applies MOD/FREQ/PA/ROLE commands to the board
3. Coordinator sends SESSION/CONFIG metadata via `board_send`
4. Coordinator arms TX (`board_query` with "ARM TX")
5. Coordinator starts burst on TX (`board_start_burst`)
6. Coordinator captures on RX (`board_capture`)
7. SPRT decision logic runs on the captured packets

This replaces the previous approach where the coordinator sent individual
`board_send` commands for each radio parameter (MOD, FREQ, PA, ROLE). The
`set_config` tool encapsulates all radio config in one MCP call, enabling
the LLM coordinator to push configs remotely with a single round-trip.