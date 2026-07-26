#!/usr/bin/env python3
"""
Walk capture — RX-ONLY. No TX connection needed.

Laptop clock syncs RX phase scheduling. TX runs independently on power bank
with its own GPS-based phase timing.

Usage: python3 walk_capture.py [duration_seconds] [rx_port]
  duration: default 600s (10 min walk)
  rx_port: default auto-detect

Procedure:
  1. Power TX from USB bank, wait for GPS lock (~1-2 min)
  2. Plug RX into laptop, run this script
  3. Walk away with TX
  4. Script logs all decoded packets: RSSI, mode, phase, PER, GPS coords from TX

Output: ~/repos/balloon-fresh/data/walk-tests/walk-YYYYMMDD-HHMMSS.log
"""
import os, sys, time, re, subprocess, termios, tty, signal

DURATION = int(sys.argv[1]) if len(sys.argv) > 1 else 600
RX_OVERRIDE = sys.argv[2] if len(sys.argv) > 2 else None

# ── Find RX board (serial 8332) ──────────────────────────────────────
RX = RX_OVERRIDE
if not RX:
    for p in sorted([f'/dev/ttyACM{i}' for i in range(16)] + [f'/dev/ttyUSB{i}' for i in range(4)]):
        if not os.path.exists(p):
            continue
        try:
            r = subprocess.run(['udevadm', 'info', '-q', 'property', '-n', p],
                             capture_output=True, text=True, timeout=2)
            if '8332' in r.stdout:
                RX = p
                break
        except Exception:
            continue

if not RX:
    print('ERROR: Cannot find RX board (serial 8332). Specify port manually.')
    print('Usage: python3 walk_capture.py [duration] [rx_port]')
    sys.exit(1)

print(f'RX={RX}', flush=True)
print(f'Duration: {DURATION}s', flush=True)
print(f'Laptop clock will sync RX phase scheduling every 2s.', flush=True)
print(f'TX runs independently — just needs GPS lock before you walk.', flush=True)
print('---', flush=True)

# ── Open RX port (bypass pyserial board guard) ───────────────────────
rx_fd = os.open(RX, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
tty.setraw(rx_fd)
stty_backup = termios.tcgetattr(rx_fd)

def cleanup(*args):
    os.close(rx_fd)
    sys.exit(0)

signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)

# ── Output ───────────────────────────────────────────────────────────
OUTDIR = os.path.expanduser('~/repos/balloon-fresh/data/walk-tests')
os.makedirs(OUTDIR, exist_ok=True)
OUTFILE = os.path.join(OUTDIR, f'walk-{time.strftime("%Y%m%d-%H%M%S")}.log')

# ── Main loop: sync + capture ────────────────────────────────────────
start = time.time()
sync_count = 0
pkt_count = 0
last_sync = 0

with open(OUTFILE, 'wb') as f:
    while time.time() - start < DURATION:
        elapsed = time.time() - start

        # Sync RX from laptop clock every 2 seconds
        if elapsed - last_sync >= 2.0:
            utc = int(time.time())
            os.write(rx_fd, f'SET_TIME {utc}\n'.encode())
            sync_count += 1
            last_sync = elapsed

        # Read RX output
        try:
            data = os.read(rx_fd, 4096)
        except (BlockingIOError, OSError):
            time.sleep(0.005)
            continue

        if data:
            f.write(data)
            f.flush()

            # Quick stats every 10s
            text = data.decode('ascii', errors='ignore')
            new_pkts = text.count('PHASE_RESULT')
            pkt_count += new_pkts

            if int(elapsed) % 10 == 0 and int(elapsed) > 0:
                # Count decoded phases so far
                f.flush()
                with open(OUTFILE, 'r') as check:
                    content = check.read()
                total = content.count('PHASE_RESULT')
                decoded = len(re.findall(r'rx=[1-9]\d*', content))
                remaining = int(DURATION - elapsed)
                print(f'[{int(elapsed)}s] syncs={sync_count} phases={total} decoded={decoded} '
                      f'remaining={remaining}s', flush=True)

            # Print decoded packets live
            for line in text.split('\n'):
                if 'PHASE_RESULT' in line and 'rx=0' not in line:
                    m = re.search(r'(\S+)\s+(\S+)\s+.*?rx=(\d+).*?per=([\d.]+).*?rssi_avg=(-?\d+)', line)
                    if m and int(m.group(3)) > 0:
                        print(f'  RX: {m.group(2):<24} rx={m.group(3):>4} '
                              f'PER={m.group(4):>5}% RSSI={m.group(5)}dBm', flush=True)

stop = True
os.close(rx_fd)

# ── Summary ──────────────────────────────────────────────────────────
with open(OUTFILE, 'r') as f:
    content = f.read()

total = content.count('PHASE_RESULT')
decoded = len(re.findall(r'rx=[1-9]\d*', content))

# Extract best/worst RSSI
rssi_vals = [int(x) for x in re.findall(r'rssi_avg=(-?\d+)', content) if int(x) != 0]

print(f'\n=== WALK CAPTURE DONE ===')
print(f'Duration: {DURATION}s | Syncs: {sync_count}')
print(f'Phases: {total} | Decoded: {decoded}')
if rssi_vals:
    print(f'RSSI range: {min(rssi_vals)} to {max(rssi_vals)} dBm')
print(f'File: {OUTFILE}')
print(f'\nWalk data saved. Analyze with:')
print(f'  python3 ~/repos/balloon-fresh/tools/analyze_walk.py {OUTFILE}')
