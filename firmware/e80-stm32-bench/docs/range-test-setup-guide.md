# E80 Range Test — Manual Setup Guide (for an unknown machine)

This guide walks an operator through running the **RX side** of a
distributed E80 range test on a machine that has never seen this repo
before — e.g. a friend's laptop. No Ansible, no orchestration: just
pip, a serial driver, and the repo.

The TX side is assumed to be running on the agent-controlled machine
(T470). Felix brings the RX board + his laptop to the field, follows
this guide, and ships the resulting data back as a zip.

> **Prerequisites**: a laptop with a free USB port, the E80 board + its
> CH340 USB-serial cable + the CMSIS-DAP SWD probe, and the
> `balloon-e80bench` repo cloned from GitHub.

---

## 0. One-time: clone the repo

```bash
git clone https://github.com/<org>/balloon-e80bench.git
cd balloon-e80bench/firmware/e80-stm32-bench
git checkout feat/2g4-sweep   # or whatever branch the TX operator specifies
```

If you don't have git yet:
- **Linux (Debian/Ubuntu)**: `sudo apt install git`
- **macOS**: `xcode-select --install` (installs git as part of Command Line Tools)
- **Windows**: install [Git for Windows](https://git-scm.com/download/win) and
  run the rest of this guide inside **Git Bash** (the Makefile uses shell
  syntax that MSYS understands).

---

## 1. Install Python dependencies

The RX side only needs **Python 3** + **pyserial**. The firmware itself is
already flashed on the board — no toolchain required on the RX machine.

### Linux (Debian / Ubuntu / Raspberry Pi OS)

```bash
# Python 3 + pip
sudo apt update
sudo apt install -y python3 python3-pip python3-venv

# pyserial (user install, no sudo needed)
pip3 install --user pyserial
# OR, recommended on Debian to avoid PEP-668 "externally managed" error:
pip3 install --user --break-system-packages pyserial
```

### macOS

macOS ships Python 3 via Command Line Tools. If you don't have it yet:

```bash
xcode-select --install         # installs python3 + git
# or use Homebrew:
brew install python
```

Then install pyserial:

```bash
pip3 install --user pyserial
# On newer macOS that complains about PATH, use:
python3 -m pip install --user pyserial
```

Verify:

```bash
python3 -c "import serial; print(serial.__version__)"
# → should print e.g. 3.5
```

### (Optional) Install `openocd`

The RX side does NOT strictly need `openocd` — it's only used for SWD
resets between configs with different modulations. If the firmware hangs
on a modulation switch, openocd lets the host reset the board without
unplugging USB. Install it if you can; skip if you can't.

- **Linux**: `sudo apt install openocd`
- **macOS**: `brew install openocd`
- **Windows**: download from
  [github.com/xpack-dev-tools/openocd-xpack](https://github.com/xpack-dev-tools/openocd-xpack/releases)

---

## 2. Plug in the board + find the serial port

Plug in **both** USB cables:
1. The CH340 USB-serial cable (data — what `pyserial` talks to)
2. The CMSIS-DAP SWD probe (debug — used by openocd for resets, optional)

### Linux: list candidate ports

```bash
# Quick: list all USB-serial devices
ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null

# Better: show only CH340 adapters
for d in /dev/ttyUSB*; do
  udevadm info -q property -n "$d" 2>/dev/null | grep -q CH340 && echo "CH340: $d"
done
```

You should see something like:

```
CH340: /dev/ttyUSB3
```

**Permission denied?** Add your user to the `dialout` group (one-time,
log out + back in afterwards):

```bash
sudo usermod -aG dialout "$USER"
# Then log out and back in, or run: newgrp dialout
```

### macOS: list candidate ports

```bash
ls /dev/cu.usbserial* /dev/cu.usbmodem* 2>/dev/null
```

Typical output:

```
/dev/cu.usbserial-1420       # CH340 data port
/dev/cu.usbmodem123456781    # CMSIS-DAP probe (ignore)
```

The CH340 port name contains `usbserial` — that's the one to use.

### Verify you can talk to the board

```bash
# Linux:
python3 -c "import serial; s=serial.Serial('/dev/ttyUSB3', 115200, timeout=2); \
print(s.read_until(b'OK').decode(errors='replace')[:80] or '(no banner — try ID? )')"

# macOS:
python3 -c "import serial; s=serial.Serial('/dev/cu.usbserial-1420', 115200, timeout=2); \
print(s.read_until(b'OK').decode(errors='replace')[:80] or '(no banner — try ID?)')"
```

If you see `OK` or the board's banner, you're good.

---

## 3. Coordinate T0 + session ID with the TX operator

The TX and RX machines must agree on **T0** (the absolute start time) and
a **session ID** so the logs can be merged afterwards. Agree on these
BEFORE plugging in / powering the boards.

| Parameter    | Example value           | Notes                                                   |
|--------------|-------------------------|---------------------------------------------------------|
| `T0`         | `2026-08-30 14:00`      | Local time, 5-10 min from now. Both sides use the same. |
| `SESSION_ID` | `2608301400`            | `date +%y%m%d%H%M` works. Both sides use the same.      |
| `CONFIGS`    | `configs/outdoor-10.json` | Path to the config preset. TX operator sends this.   |
| `BAND`       | `868` (or `915`, `433`) | 868 MHz default for EU.                                 |

**Clock sync**: phones sync automatically via NTP. For laptops, make
sure the clock is correct within ~1 second:

```bash
# Linux:
timedatectl status      # look for "System clock synchronized: yes"

# macOS:
sntp time.apple.com     # shows offset; should be <+/-0.1s
```

If your clock is off by more than a second, sync it (Linux:
`sudo systemctl restart systemd-timesyncd`; macOS: System Settings →
General → Date & Time → "Set time and date automatically").

---

## 4. Run the RX side

From inside `firmware/e80-stm32-bench/`:

```bash
make range-rx \
    T0='2026-08-30 14:00' \
    CONFIGS=configs/outdoor-10.json \
    BAND=868 \
    RX_LOG=rx-log.csv \
    PRIME_DISCARD=2 \
    --skip-fw-check    # if the board isn't running the exact firmware git SHA
```

The first run will print the schedule (one line per config cell with its
start time). The RX waits until `T0 + margin` and then arms + captures.
Each received packet row is flushed to `rx-log.csv` immediately — partial
data survives an abort.

**Keep the laptop awake**: close the lid at your peril. If the laptop
suspends, the schedule is lost. On Linux, inhibit suspend:

```bash
systemd-inhibit --what=sleep --mode=block make range-rx T0='...' ...
```

On macOS, run `caffeinate -i make range-rx ...` to keep the system awake.

**To abort**: `Ctrl-C` — the script writes an `# ABORTED by operator`
comment into the log and stops cleanly.

### What you get

After the run, you have `rx-log.csv` with one row per received packet:

```
session,config,pkt_idx,ts_ms,rssi_dbm,snr_db,crc_ok,bit_err,freq_hz,mod,sf_or_br,bw,pa_dbm,len,pcrc16,captured_ts
# DISTRIBUTED_RX_MODE t0=2026-08-23T20:04:49 port=/dev/ttyUSB3 probe=203584200D2D0D42
2608232002,0,0,334846,-42.0,0.0,1,0,868000000,FLRC,8,125,10,64,0,2026-08-23T20:06:09
...
```

The `captured_ts` column is what the GPS stitch script joins against.

### Prime discard (AGC warmup)

The `--prime-discard N` flag (default 2, set to 0 to disable) sends N
extra "prime" packets at the start of each burst before the measured
window. The TX sends `N_measured + N_prime` total packets; the RX
receives them all but discards the first `N_prime` from the log so they
don't count toward PER.

This compensates for the LR2021 chip's AGC not being fully settled for
the first 1-2 packets of a burst (especially FLRC with short
preambles). Without prime discard, the first few packets may show
depressed RSSI or elevated CRC errors, biasing the PER measurement.

Set `PRIME_DISCARD=0` in the Makefile or `--prime-discard 0` on the CLI
to disable (e.g. for LoRa SF12 where airtime is long and AGC has time
to settle within the first packet).

---

## 5. Record GPS alongside the test (parallel)

The goal is a GPX or CSV track whose timestamps overlap the test window.
Run the tracker on the **same phone** (or laptop) whose clock is synced.

### Recommended phone apps

| App                          | Platform         | Output | Notes                              |
|------------------------------|------------------|--------|------------------------------------|
| [OsmAnd](https://osmand.net) | Android / iOS    | GPX    | Free, open-source. Trip recording. |
| [GPX Tracker](https://apps.apple.com/app/gpx-tracker/id1114695369) | iOS | GPX | Free, simple. |
| [Strava](https://strava.com) | Android / iOS    | GPX (export) | Record a ride, then export GPX from the web. |
| [Open GPX Tracker](https://f-droid.org/packages/io.github.dyessc.gpx_tracker/) | Android (F-Droid) | GPX | No account needed. |
| [Komoot](https://komoot.com) | Android / iOS    | GPX (export) | Tour recorder. |

### Steps

1. **Sync the phone clock** to network time before recording (phones do
   this automatically — just make sure "Set automatically" is on in
   Settings → Date & Time).
2. **Start recording ~1 minute before T0**.
3. **Walk / ride along the planned route** during the test.
4. **Stop recording ~1 minute after the last config ends.**
5. **Export the track as GPX** (or CSV if the app only does CSV).

### If you have a dedicated GPS Logger (not a phone)

Any device that outputs **GPX 1.1** or **CSV with timestamp/lat/lon
columns** works. Make sure it's logging in UTC and that the clock is
synced to within a few seconds.

### Manual GPS (worst case)

If you have no tracker, you can write a CSV by hand. These columns are
mandatory (header row required):

```
timestamp,lat,lon,ele
2026-08-30T14:00:00Z,52.0123,4.0456,5.2
2026-08-30T14:02:00Z,52.0124,4.0457,5.4
...
```

The `timestamp` column accepts ISO-8601 (`...Z` or with offset) or a
unix epoch number. `ele` (elevation, metres) is optional.

---

## 6. Zip the results and send to the TX operator

From inside `firmware/e80-stm32-bench/`:

```bash
make range-zip \
    RX=rx-log.csv \
    GPS=track.gpx \
    SITE=fieldA \
    OPERATOR=alice
```

This produces a timestamped zip like `20260830T140500Z_fieldA.zip`
containing:
- `rx-log.csv` — the packet log
- `track.gpx` — your GPS track (omit `GPS=` if you have no track)
- `metadata-XXXX.txt` — operator name, host OS, repo git SHA,
  file sizes, and the RX log header (for sanity-check after merge)

**Send the zip via Signal** (or Slack / email / USB stick) to the TX
operator. Files are typically 5-50 KB — well under any messaging
attachment limit.

### Without `make` / without `zip`

If `make` or `zip` isn't available, you can bundle the files manually:

```bash
# macOS / Linux, using tar instead of zip:
tar czf range-session.tgz rx-log.csv track.gpx
# Or using Python (always available):
python3 -c "import zipfile; z=zipfile.ZipFile('range.zip','w'); \
z.write('rx-log.csv'); z.write('track.gpx'); z.close()"
```

---

## 7. After the test: GPS stitch (done by the TX operator)

The TX operator runs the stitch on the merged data after receiving the
zip. For reference, the command is:

```bash
make range-stitch \
    RX=rx-log.csv \
    GPS=track.gpx \
    TX_GPS=52.0123,4.0456 \
    OUT=rx-with-gps.csv
```

This joins each packet row with the nearest GPS fix by timestamp, adds
`gps_lat` / `gps_lon` / `gps_ele` / `gps_offset_s` columns, and — when
`TX_GPS` is provided — a `dist_m` haversine distance from the TX
reference point. See `tools/gps_stitch.py --help` for advanced options
(e.g. `--t0-epoch` if the RX log only has `ts_ms` firmware uptime).

---

## Troubleshooting

### "Permission denied" opening the serial port (Linux)

Add yourself to the `dialout` group and re-login:

```bash
sudo usermod -aG dialout "$USER"
# log out + back in (or: newgrp dialout)
```

### The CH340 cable shows up but no data comes through

- Verify the baud rate is `115200` (the firmware default).
- Make sure the TX side is actually running — coordinate via phone.
- Try swapping the TX/RX roles of the two physical boards (the role is
  set by the firmware based on the SWD probe serial).

### Make says `T0 required`

You MUST pass `T0=` when invoking `make range-rx`. Example:

```bash
make range-rx T0='2026-08-30 14:00' --skip-fw-check
```

### The board reboots / no packets received mid-test

The SX1280 radio cannot hot-switch modulation (LoRa ↔ FLRC) via the `MOD`
command — the firmware looks like it accepts the change but the radio
stays on the old config. The RX script handles this by issuing an SWD
reset between modulation-changing configs, but only if `openocd` is
installed. If you can't install openocd, either:
- Use a config preset that doesn't mix LoRa and FLRC, OR
- Manually unplug + replug the board's USB between configs.

### GPS stitch complains "nearest GPS point is N seconds away"

This means your phone clock or laptop clock drifted. Check that both
devices have automatic time sync on. The stitch emits a one-time warning
and still produces output — the `gps_offset_s` column tells you the
actual offset per packet so you can filter bad matches.

### `python3 -m pip install --user pyserial` fails with "externally managed"

This is Debian 12+ enforcing PEP-668. Either:

```bash
pip3 install --user --break-system-packages pyserial
# OR, cleaner:
python3 -m venv ~/e80env && source ~/e80env/bin/activate
pip install pyserial
# run make with the venv's python:
make range-rx PYTHON=~/e80env/bin/python T0='...' ...
```

---

## Quick reference (cheat sheet)

```bash
# 1. (Linux) install deps
sudo apt install -y python3-pip
pip3 install --user --break-system-packages pyserial

# 2. plug in board, find CH340 port
for d in /dev/ttyUSB*; do udevadm info -q property -n "$d" 2>/dev/null \
  | grep -q CH340 && echo "CH340: $d"; done

# 3. coordinate T0 + session ID with TX operator, then:
make range-rx T0='2026-08-30 14:00' --skip-fw-check

# 4. (parallel) start a GPX tracker app on your phone, sync'd to NTP

# 5. after the test, zip + send:
make range-zip RX=rx-log.csv GPS=track.gpx SITE=fieldA OPERATOR=alice
# then Signal the *.zip to the TX operator
```
