# E80 Range Test — Operator Quickstart Guide

> **You don't need to know Linux.** Plug in a board, type one command, done.

## What You Need

- 2× E80-STM32 bench boards (one is TX, one is RX — the board knows which it is)
- 2× computers (laptop + mini PC), each with one board plugged in via USB
  - Each board has **two USB cables**: one for serial (CH340), one for the debug probe (Pico)
  - Plug BOTH cables in — the board needs both to be detected
- WiFi or Ethernet: both computers must be on the same network
- A phone with GPS (for coordinates)

---

## Step 0: One-time Setup (skip if already done)

On **each machine**, clone the repo and install deps:

```bash
git clone https://github.com/your-org/balloon-e80bench.git ~/repos/balloon-e80bench
cd ~/repos/balloon-e80bench/firmware/e80-stm32-bench/tools
make check-deps
```

If it says "pyserial missing":
```bash
pip install pyserial
```

If it says "openocd missing" (only needed for board recovery, not for normal tests):
```bash
sudo apt install openocd
```

If you see "Permission denied" on serial ports:
```bash
sudo usermod -aG dialout $USER
# Then log out and log back in (or run: newgrp dialout)
```

---

## Step 1: Start the Server on Each Machine

### On the TX machine (the one with the TX board):
```bash
cd ~/repos/balloon-e80bench/firmware/e80-stm32-bench/tools
make tx-server
```

You'll see:
```
Starting TX board server on port 7780...
[server] Role=TX  Port=/dev/ttyUSB3  Probe=148757200D2D1425  FW=0561b29
[server] ID: ID E80BENCH v1.2 fw=0561b29 role=TX ...
[server] Listening on 0.0.0.0:7780 (role=TX)
```

**Leave this terminal open.** The server is now running.

### On the RX machine (the one with the RX board):
```bash
cd ~/repos/balloon-e80bench/firmware/e80-stm32-bench/tools
make rx-server
```

Same output but with `Role=RX` and `Probe=203584200D2D0D42`.

### Don't know which board is which?

Just run `make auto-server` on each machine. It auto-detects whether the
board is TX or RX. The output tells you:
```
[server] Role=TX  Port=/dev/ttyUSB3  ...
```

### Running the RX server on DQ05 from the T470:

If DQ05 is reachable over SSH:
```bash
make rx-server-remote DQ05_HOST=192.168.1.20
```
This SSHes into DQ05 and starts the RX server there.

---

## Step 2: Run the Range Test

From **either machine** (or your own laptop on the same network):

```bash
cd ~/repos/balloon-e80bench/firmware/e80-stm32-bench/tools

make range-test TX_HOST=192.168.1.10 RX_HOST=192.168.1.20 \
  SITE=fieldA STOP=S3 DIST_M=200 \
  GPS_TX=52.0123,4.0456 GPS_RX=52.0234,4.0123 \
  OPERATOR=alice
```

Replace the IPs with your machines' addresses. Find them with `hostname -I`
on each machine.

### Don't know which IP is TX and which is RX?

```bash
make range-test-auto HOST_A=192.168.1.10 HOST_B=192.168.1.20 \
  SITE=fieldA STOP=S3 DIST_M=200
```

The client connects to both servers and auto-detects roles. No need to know
which board is where.

---

## Step 3: Check Your Results

```bash
make show-results SITE=fieldA STOP=S3 REPEAT=1
```

Output files:
- **CSV**: `results/fieldA_S3_r1.csv` — one row per modulation, with PER, RSSI, SNR
- **JSON**: `results/fieldA_S3_r1-meta.json` — test metadata (operator, GPS, timestamps, board IDs)

### CSV format:
```csv
site,stop,dist_m,repeat,mod,len,pa,freq_hz,n,sent,recv,per,per_ci_lo,per_ci_hi,rssi,snr,kbps,elapsed_s,timestamp
fieldA,S3,200,1,flrc650,51,10,868000000,10000,10000,9876,1.24,1.1,1.4,-87,-9,512,15.3,2026-08-23T15:42:00
...
```

Lines starting with `#` are metadata (SESSION_START, STOP info, GPS, board IDs).

### JSON metadata:
```json
{
  "test_id": "20260823-154200",
  "operator": "alice",
  "tx": {
    "host": "192.168.1.10",
    "probe_serial": "148757200D2D1425",
    "gps": "52.0123,4.0456"
  },
  "rx": {
    "host": "192.168.1.20",
    "probe_serial": "203584200D2D0D42",
    "gps": "52.0234,4.0123"
  },
  "params": { "site": "fieldA", "stop": "S3", "frequency_hz": 868000000 }
}
```

---

## All Makefile Targets

| Target | What it does |
|--------|-------------|
| `make help` | Show all available commands |
| `make check-deps` | Verify openocd + pyserial + board detection |
| `make detect` | Auto-detect local board (role + port) |
| `make tx-server` | Start TX board server (auto-detects port) |
| `make rx-server` | Start RX board server (auto-detects port) |
| `make auto-server` | Start server, auto-detect role (TX or RX) |
| `make rx-server-remote` | Start RX server on DQ05 via SSH |
| `make range-test TX_HOST=ip RX_HOST=ip` | Run full range test campaign |
| `make range-test-auto HOST_A=ip HOST_B=ip` | Run test, auto-detect which is TX/RX |
| `make all-in-one` | Start both servers + run test (fully automated) |
| `make dry-run` | Print test plan without needing boards |
| `make stop-servers` | Stop all board servers |
| `make show-results` | Display latest CSV results |
| `make test-single` | Single-shot bench test (both boards on one machine) |

---

## Makefile Parameters

All of these can be set on the command line: `make range-test FREQ=915000000 DBM=22`

| Parameter | Default | Description |
|-----------|---------|-------------|
| `FREQ` | 868000000 | Frequency in Hz (863-870 MHz EU SRD) |
| `DBM` | 10 | TX power in dBm (10=indoor, 22=max outdoor) |
| `SITE` | siteA | Site name for CSV |
| `STOP` | S1 | Stop number (S0-S5) |
| `DIST_M` | 100 | Distance in meters |
| `REPEAT` | 1 | Repeat number (1-3) |
| `OPERATOR` | (username) | Your name |
| `GPS_TX` | ? | GPS coords of TX rig (lat,lon) |
| `GPS_RX` | ? | GPS coords of TX rig (lat,lon) |
| `H_TX` | 1.5 | TX antenna height AGL in meters |
| `H_RX` | 1.5 | RX antenna height AGL in meters |
| `GROUND` | ? | Ground type (grass, asphalt, water, etc.) |
| `WEATHER` | ? | Weather description |
| `CSV` | results/SITE_STOP_rN.csv | CSV output path |
| `TCP_PORT` | 7780 | TCP port for board servers |
| `DQ05_HOST` | dq05 | SSH hostname/IP for DQ05 |

---

## How Port Detection Works (Technical)

The #1 pain point: **CH340 USB-serial ports swap on every reboot.**
`/dev/ttyUSB3` might become `/dev/ttyUSB4` tomorrow. This system solves it:

1. **SWD probe serial (primary)**: Each board has a Raspberry Pi Pico debug
   probe with a unique USB serial number (TX: `148757200D2D1425`,
   RX: `203584200D2D0D42`). We read this from
   `/sys/bus/usb/devices/*/serial` — a simple file read, no openocd needed.
   The serial permanently identifies which board is TX and which is RX.

2. **ID? firmware query (verification)**: We send `ID?` to the detected
   CH340 port. The firmware responds with `role=TX` or `role=RX`, plus
   firmware hash, frequency, modulation, and power state.

3. **USB tree matching (dual-board fallback)**: When both boards are on one
   machine, we match each CH340 port to its probe via the USB device tree
   (shared parent hub). If that fails, we fall back to the `role=` field
   from ID?.

4. **Radio handshake (last resort)**: The existing `identify_boards()` in
   `e80_sweep_full.py` does a radio handshake (send test packets, see who
   receives). This always works but requires both boards on one machine.

The server uses method 1 + 2 on startup. This works on any machine —
the operator just plugs in one board and starts the server.

---

## Troubleshooting

### "no SWD probe found"
- Ensure both USB cables are plugged into the board (CH340 + Pico probe)
- Check: `lsusb | grep 2e8a` — should show a Pico Debugprobe
- If not: the USB cable to the probe port may be loose

### "no CH340 serial port found"
- Check: `ls /dev/ttyUSB*` — should show ports
- If ports exist but not detected: check `dmesg | grep ch341`
- Permission denied? `sudo usermod -aG dialout $USER && newgrp dialout`

### "timeout waiting for reply"
- The board may be in a bad state. If openocd is installed, the server
  will attempt an SWD reset automatically.
- If openocd is NOT installed: power-cycle the board (unplug + replug USB)
- Install openocd: `sudo apt install openocd` or `make install-openocd`

### "Connection refused" when running range-test
- The server isn't running on that machine. Start it first:
  `make tx-server` on the TX machine, `make rx-server` on the RX machine
- Check the IP address: `hostname -I` on each machine
- Check firewall: `sudo ufw allow 7780/tcp` on both machines

### Ports swapped after reboot
- This is expected and solved! Just restart the servers with `make tx-server`
  / `make rx-server`. The auto-detection handles the port swap automatically.
- No need to figure out which port is which — the system does it for you.

### Board server says wrong role
- If `make tx-server` says "expected role=TX but detected role=RX",
  you have the TX board plugged into the wrong machine, or the board
  identity doesn't match the expected probe serial.
- Check: `make detect` to see what's detected.
- Override: use `make auto-server` instead (accepts either role).
