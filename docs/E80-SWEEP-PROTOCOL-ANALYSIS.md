# E80 Sweep Protocol Analysis — Zero Packets Root Cause

**Date:** 2026-08-20
**Firmware:** commit e79f0c0 (branch feat/persist-tx-seq)
**Analysis of:** `~/repos/balloon-fresh/tools/e80_sweep_run.py`

## Executive Summary

The sweep script captured zero packets across all 10 configs because **the RX
board's modulation parameters were never updated to match the TX board's
config changes**. The `MOD` command was sent only to the TX board; the RX
board remained at its boot default of SF8/BW125 for the entire sweep. Since
none of the 10 sweep configs used SF8/BW125, the RX board could not
demodulate any transmitted packets.

## Root Cause: RX Modulation Never Reconfigured

### The Bug

In `e80_sweep_run.py`, per-config setup is:

```python
# Set config_id on RX
send(rx, f'CONFIG {cfg_id} 0', 0.3)

# Configure TX
send(tx, 'ROLE TX', 0.5)
send(tx, f'MOD lora {sf} {bw}', 0.3)
send(tx, f'PA {power}', 0.3)
send(tx, f'CONFIG {cfg_id} 0', 0.3)
send(tx, 'ARM TX', 0.3)
```

The `MOD` command (which sets SF/BW) is sent **only to the TX board**.
The RX board receives only `CONFIG <id> 0`, which sets the `pkt_ctx.config_id`
metadata for PKT line logging but does **not** change radio modulation.

### Firmware Confirmation

In `bench.c`, the `CONFIG` command handler (line 805-821) only updates
`pkt_ctx.config_id` and `pkt_ctx.replicate` — it does not touch the radio
configuration struct `cfg` or call `radio_bench_apply_cfg()`.

The `MOD` command handler (line 533-572) updates `cfg.mod`, `cfg.sf`,
`cfg.bw_hz`, and (for RX role) calls `radio_rearm_rx()` which applies the
new modulation to the radio hardware. But this command was never sent to RX.

The RX board was initialized once at the top of the script:
```python
send(rx, 'ROLE RX', 1)    # sets up RX with default SF8/BW125
send(rx, 'PRBS ON', 0.5)  # enables PRBS-15 verification
```

The boot default `cfg` in `bench.c` (line 60-63) is:
```c
.mod = BENCH_MOD_LORA, .sf = 8, .cr = 5, .bw_hz = 125000
```

The 10 sweep configs use SF7/SF8/SF9/SF10/SF11/SF12 at BW125, plus SF7/SF8
at BW250 and BW500. **None of the first configs match SF8/BW125**, and even
config 1 (SF8/BW125) is preceeded by config 0 (SF7/BW125) which would have
zero packets, potentially causing the script to hang or misbehave.

Actually, config 1 is `(1, 8, 125, 10)` which IS SF8/BW125 — the same as the
RX default. So config 1 should have worked. But the script hung with zero
packets overall, suggesting a secondary issue may also be present (see
Secondary Issues below).

## Secondary Issues

### 1. No START sent to RX board

The firmware's START handler has an RX path (line 652-665):
```c
if (role == BENCH_ROLE_RX) {
    tx_len = (uint16_t)c->len_bytes;
    bench_stats_reset(&stats);
    stats.t_start_us = bench_micros();
    session_active = true;
    radio_rearm_rx();
    ...
}
```

This resets RX stats and re-arms the receiver with the correct packet length.
The sweep script never sends START to the RX board. While LoRa uses variable-
length packets (so the length mismatch isn't fatal), the stats are not reset
per config, causing cumulative counting across all configs.

### 2. No per-config RX re-arm after MOD change

When `MOD` is sent to the RX board with role=RX, the firmware calls
`radio_rearm_rx()` (line 570-571), which calls `radio_bench_apply_cfg(&cfg)`
and `radio_bench_rx_arm()`. This is necessary to actually tune the radio
hardware to the new SF/BW. Without it, the cfg struct changes but the radio
chip still operates with the old modulation.

### 3. No settle time between RX reconfiguration and TX start

After changing modulation on both boards, a brief settle time should be
allowed before starting TX, to ensure the RX board's radio chip has fully
configured its modem and is listening.

### 4. send() function may miss responses

The `send()` function resets the input buffer before writing, sleeps, then
reads. If the firmware responds faster than the sleep duration, the response
is captured. But if the firmware responds slower (e.g., during radio
reconfiguration), the response may be missed. More critically, the function
does not check for `OK` vs `ERR` in the response — errors are silently
ignored.

### 5. Possible UART buffer overflow on RX

At 2 Mbaud with 50 packets, each PKT line is ~100 bytes. Total: ~5KB. The
default serial buffer in pyserial is 4096 bytes for the `read()` call, but
the OS kernel buffer is typically 64KB+. With `rx.read(65536)` and a
sufficiently long wait, this should be fine. But if the wait is too short,
packets may be missed.

## Firmware State Machine Analysis

### Command Order Requirements

Based on the firmware source code analysis:

1. **MOD can be sent before or after ROLE TX:**
   - `MOD` updates the `cfg` struct regardless of role.
   - If role == RX, it also calls `radio_rearm_rx()` to apply immediately.
   - If role == TX, it only updates the struct; the radio is configured on
     the next `apply_cfg` call (in START handler).
   - **Conclusion:** MOD can be sent after ROLE TX for TX role. It just
     updates the struct. The hardware is configured when START runs.

2. **ARM TX is cleared by every ROLE TX:**
   - `ROLE TX` handler sets `tx_armed = false` (line 488).
   - Must re-send `ARM TX` after every `ROLE TX`.
   - After a START burst completes, `tx_armed` is NOT cleared (the burst
     completion path at line 887-898 only changes state and sleeps the radio).
   - **Conclusion:** If you send `ROLE TX` each loop, you MUST re-arm. If
     you DON'T send `ROLE TX` again, you can send START directly (the board
     is still armed, just asleep — START calls `radio_ensure_awake()`).

3. **CONFIG is metadata-only:**
   - Sets `pkt_ctx.config_id` and `pkt_ctx.replicate` for PKT line tagging.
   - Does not affect radio configuration.
   - Can be sent at any time, in any order relative to other commands.

4. **No explicit state reset between configs:**
   - There is no "RESET" or "CLEAR" command.
   - `STOP` puts the radio to sleep and stops the session.
   - `ROLE NONE` puts the radio to sleep and resets the role.
   - For sweeps, the cleanest approach is to NOT re-send ROLE TX each loop
     (avoid the disarm), and instead just send MOD + START for each new
     config. Or send ROLE TX + ARM TX each loop if you want a clean reset.

5. **Changing MOD while radio is asleep is fine:**
   - MOD only updates the cfg struct. It doesn't touch the radio hardware
     (for TX role). The hardware is configured when START calls
     `radio_bench_apply_cfg(&cfg)`.

6. **After START completes, the radio is asleep:**
   - The burst completion path (line 887-898) sets the radio to sleep and
     state to BSTATE_IDLE.
   - The next START will call `radio_ensure_awake()` to wake it up.

### Correct Command Sequence for Multi-Config Sweeps

**TX board, per config:**
```
MOD lora <sf> <bw>     # update cfg struct (can be before or after ROLE TX)
PA <dbm>               # update cfg struct
CONFIG <id> <rep>      # set metadata for PKT lines
ARM TX                 # re-arm (only needed if ROLE TX was sent, or first time)
START N=<n> LEN=<l> GAP=<g>  # starts burst, applies cfg to radio hardware
```

**RX board, per config:**
```
MOD lora <sf> <bw>     # update cfg struct AND re-arm RX with new modulation
CONFIG <id> <rep>      # set metadata for PKT lines
START N=<n> LEN=<l> GAP=<g>  # reset stats and re-arm RX (optional for LoRa but recommended)
```

**Key insight:** The RX board MUST receive `MOD` for each config change.
Without it, the RX radio chip operates with stale modulation parameters and
cannot demodulate packets transmitted with different SF/BW.

### Why the Working Single-Config Test Succeeded

The working test (documented in E80-PRBS-VERIFY-2026-08-20.md) used:
- RX: `ROLE RX` + `PRBS ON` (default SF8/BW125)
- TX: `ROLE TX` → `ARM TX` → `START N=100 LEN=64 GAP=10000`

Both boards used the default SF8/BW125, so modulation matched. No MOD
command was needed. 100/100 packets received.

## Fixed Sweep Script

```python
#!/usr/bin/env python3
"""E80 LoRa sweep — multi-config with RX modulation sync.

FIX: The original sweep script only sent MOD to the TX board. The RX board
stayed at the boot default SF8/BW125 for all configs, so it could not
demodulate any packets transmitted with different SF/BW settings.

This corrected script sends MOD to BOTH boards for each config, resets RX
stats per config via START, and adds settle time between reconfiguration
and transmission.
"""
import serial
import time
import os
import sys

BAUD = 2000000
TX_PORT = '/dev/ttyUSB3'
RX_PORT = '/dev/ttyUSB4'
N_PKTS = 50
PKT_LEN = 64
GAP_US = 10000

# (config_id, SF, BW_kHz, power_dbm)
CONFIGS = [
    (0,  7, 125, 10),
    (1,  8, 125, 10),
    (2,  9, 125, 10),
    (3, 10, 125, 10),
    (4, 11, 125, 10),
    (5, 12, 125, 10),
    (6,  7, 250, 10),
    (7,  8, 250, 10),
    (8,  7, 500, 10),
    (9,  8, 500, 10),
]

# Approximate time-on-air per packet (ms) for LoRa CR=4/5, 64B payload
TOA_MS = {
    (7,125): 46,   (7,250): 23,   (7,500): 12,
    (8,125): 82,   (8,250): 41,   (8,500): 21,
    (9,125): 164,  (9,250): 82,   (9,500): 41,
    (10,125): 328, (10,250): 164, (10,500): 82,
    (11,125): 656, (11,250): 328, (11,500): 164,
    (12,125): 1312,(12,250): 656, (12,500): 328,
}


def send(ser, cmd, wait=0.5):
    """Send a command and return the response. Checks for errors."""
    ser.reset_input_buffer()
    ser.write((cmd + '\n').encode())
    time.sleep(wait)
    resp = ser.read(4096).decode(errors='replace').strip()
    if resp and 'ERR' in resp:
        print(f"  [!] ERROR response to '{cmd}': {resp}", flush=True)
    return resp


def main():
    tx = serial.Serial(TX_PORT, BAUD, timeout=5)
    rx = serial.Serial(RX_PORT, BAUD, timeout=5)

    # --- One-time RX setup ---
    print("RX: ROLE RX", flush=True)
    resp = send(rx, 'ROLE RX', 1)
    print(f"  {resp}", flush=True)

    print("RX: PRBS ON", flush=True)
    resp = send(rx, 'PRBS ON', 0.5)
    print(f"  {resp}", flush=True)

    # --- One-time TX setup ---
    print("TX: ROLE TX", flush=True)
    resp = send(tx, 'ROLE TX', 1)
    print(f"  {resp}", flush=True)

    all_pkts = []
    all_stats = []

    for cfg_id, sf, bw, power in CONFIGS:
        print(f"\n--- Config {cfg_id}: SF{sf} BW{bw} PWR={power} ---",
              flush=True)

        # --- RX: update modulation for THIS config ---
        # MOD with role=RX calls radio_rearm_rx() in firmware,
        # applying the new SF/BW to the radio hardware immediately.
        resp = send(rx, f'MOD lora {sf} {bw}', 0.5)
        print(f"  RX MOD: {resp}", flush=True)

        # RX: set config metadata
        resp = send(rx, f'CONFIG {cfg_id} 0', 0.3)
        print(f"  RX CONFIG: {resp}", flush=True)

        # RX: re-arm with START to reset stats per config
        resp = send(rx, f'START N={N_PKTS} LEN={PKT_LEN} GAP={GAP_US}', 0.3)
        print(f"  RX START: {resp}", flush=True)

        # --- TX: update modulation for THIS config ---
        # MOD with role=TX only updates the cfg struct; the radio hardware
        # is configured when START calls radio_bench_apply_cfg().
        resp = send(tx, f'MOD lora {sf} {bw}', 0.3)
        print(f"  TX MOD: {resp}", flush=True)

        # TX: set power
        resp = send(tx, f'PA {power}', 0.3)
        print(f"  TX PA: {resp}", flush=True)

        # TX: set config metadata
        resp = send(tx, f'CONFIG {cfg_id} 0', 0.3)
        print(f"  TX CONFIG: {resp}", flush=True)

        # TX: re-arm (tx_armed was cleared by ROLE TX at startup)
        # Note: on subsequent loops, tx_armed is still true from the previous
        # loop, but re-arming is harmless (idempotent).
        resp = send(tx, 'ARM TX', 0.3)
        print(f"  TX ARM: {resp}", flush=True)

        # --- Settle time: let RX radio fully configure ---
        time.sleep(0.5)

        # --- Clear RX serial buffer before burst ---
        rx.reset_input_buffer()

        # --- Start TX burst ---
        resp = send(tx, f'START N={N_PKTS} LEN={PKT_LEN} GAP={GAP_US}', 0.3)
        print(f"  TX START: {resp}", flush=True)

        # --- Calculate wait time based on time-on-air ---
        toa = TOA_MS.get((sf, bw), 100)
        per_pkt_s = (toa + GAP_US / 1000) / 1000.0
        total_s = per_pkt_s * N_PKTS
        wait_s = max(total_s * 1.5, 5)
        print(f"  TOA={toa}ms/pkt, est={total_s:.1f}s, wait={wait_s:.1f}s",
              flush=True)

        time.sleep(wait_s)

        # --- Read PKT lines from RX ---
        rx_data = rx.read(65536).decode(errors='replace')
        pkts = [l.strip() for l in rx_data.split('\n')
                if l.strip().startswith('PKT,')]
        all_pkts.extend(pkts)
        print(f"  Captured {len(pkts)} PKT lines", flush=True)

        # --- Collect stats ---
        tx_stat = send(tx, 'STAT?', 1)
        rx_stat = send(rx, 'STAT?', 1)
        all_stats.append(
            f"=== Config {cfg_id} (SF{sf} BW{bw} PWR={power}) ===")
        all_stats.append(f"TX: {tx_stat}")
        all_stats.append(f"RX: {rx_stat}")
        all_stats.append("")
        print(f"  TX: {tx_stat[:120]}", flush=True)
        print(f"  RX: {rx_stat[:120]}", flush=True)

        # --- Inter-config delay ---
        time.sleep(1)

    tx.close()
    rx.close()

    # --- Save results ---
    out_dir = os.path.expanduser(
        '~/repos/balloon-fresh/data/e80-sweep-2026-08-20')
    os.makedirs(out_dir, exist_ok=True)

    csv_path = os.path.join(out_dir, 'e80_sweep_20260820.csv')
    with open(csv_path, 'w') as f:
        f.write('PKT,session_id,config_id,replicate,seq,ts_ms,rssi_dbm,'
                'snr_db,crc_ok,bit_err,bytes_bad,freq_hz,mod,sf,bw_khz,'
                'cr,power_dbm,pkt_size,gps_fix,gps_lat,gps_lon,gps_alt,'
                'gps_sats,gps_hdop\n')
        for line in all_pkts:
            f.write(line + '\n')

    stats_path = os.path.join(out_dir, 'e80_sweep_20260820_stats.txt')
    with open(stats_path, 'w') as f:
        f.write('\n'.join(all_stats))

    print(f"\n=== SWEEP COMPLETE ===", flush=True)
    print(f"Total PKT lines: {len(all_pkts)}", flush=True)
    print(f"CSV: {csv_path}", flush=True)
    print(f"Stats: {stats_path}", flush=True)


if __name__ == '__main__':
    main()
```

## Summary of Changes in Fixed Script

| # | Change | Reason |
|---|--------|--------|
| 1 | **Send `MOD` to RX board per config** | Root cause fix: RX radio must be reconfigured to match TX SF/BW |
| 2 | Send `START` to RX board per config | Resets RX stats and re-arms receiver cleanly |
| 3 | One-time `ROLE TX` at startup | Avoids redundant disarm/re-arm each loop; tx_armed persists |
| 4 | Add 0.5s settle time after RX reconfig | Ensures radio chip fully configured before TX starts |
| 5 | Check for `ERR` in send() responses | Surface firmware errors instead of silently ignoring |
| 6 | Print all command responses | Aids debugging if something goes wrong |
| 7 | Print first 120 chars of STAT? | More context in console output |

## Protocol Reference (from firmware source)

```
┌─────────────────────────────────────────────────────────────────┐
│                    FIRMWARE STATE MACHINE                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Boot: radio ASLEEP, role=NONE, tx_armed=false                  │
│        cfg = {LoRa, SF8, CR5, BW125k, 868MHz, +10dBm}          │
│                                                                  │
│  ROLE TX → tx_armed=false, radio awake, apply_cfg, STDBY_RC    │
│  ROLE RX → tx_armed=false, radio awake, reset stats, rx_arm    │
│  ROLE NONE → radio sleep                                        │
│                                                                  │
│  ARM TX → requires role==TX, sets tx_armed=true                 │
│           starts IWDG watchdog (first time only)                │
│                                                                  │
│  MOD → updates cfg struct (sf, bw, mod)                         │
│        if role==RX: calls radio_rearm_rx() [applies to HW]      │
│        if role==TX: only updates struct [HW applied at START]   │
│                                                                  │
│  PA → updates cfg.txpow_dbm                                     │
│       if radio awake: calls apply_cfg() [applies to HW]         │
│                                                                  │
│  CONFIG → sets pkt_ctx metadata only (no radio effect)          │
│                                                                  │
│  START (TX) → requires role==TX AND tx_armed==true              │
│              calls radio_ensure_awake() + apply_cfg()           │
│              builds payload, starts TX burst                    │
│                                                                  │
│  START (RX) → resets stats, re-arms RX with pkt length          │
│                                                                  │
│  Burst complete → radio SLEEP, state=IDLE, session=false        │
│                   tx_armed stays true (NOT cleared)             │
│                                                                  │
│  STOP → radio sleep, session=false                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Correct Multi-Config Sequence (Both Boards)

```
# ---- ONE TIME ----
RX:  ROLE RX                          # start continuous RX, default SF8/BW125
RX:  PRBS ON                          # enable PRBS-15 verification

TX:  ROLE TX                          # set TX role, radio awake, tx_armed=false
TX:  ARM TX                           # arm TX, start IWDG

# ---- PER CONFIG ----
RX:  MOD lora <sf> <bw>              # reconfigure RX radio (calls radio_rearm_rx)
RX:  CONFIG <id> 0                    # set metadata
RX:  START N=<n> LEN=<l> GAP=<g>     # reset stats, re-arm RX

TX:  MOD lora <sf> <bw>              # update TX cfg struct
TX:  PA <dbm>                         # update TX power
TX:  CONFIG <id> 0                    # set metadata
# (no need to re-ARM TX if ROLE TX was only sent once at startup)
TX:  START N=<n> LEN=<l> GAP=<g>     # apply cfg to HW, start burst

# wait for burst to complete (based on TOA * N_PKTS + gaps)
# read PKT lines from RX
# query STAT? from both boards
```