#!/usr/bin/env python3
"""
GPS-synced walk capture. Reads GPS UTC from TX serial, forwards to RX,
captures RX output. Uses threading for zero-latency forwarding.

Usage: python3 walk_sync_capture.py [duration_sec]
"""
import sys, os, time, threading, re

DURATION = int(sys.argv[1]) if len(sys.argv) > 1 else 300
RX_PORT = '/dev/ttyACM1'
TX_PORT = '/dev/ttyACM3'
BAUD = 2000000
OUTDIR = os.path.expanduser('~/repos/balloon-fresh/data/range-tests/20260725')
os.makedirs(OUTDIR, exist_ok=True)
OUTFILE = os.path.join(OUTDIR, f'walk-py-synced-{time.strftime("%H%M%S")}.log')

# Acquire board lock
os.environ['BALLOON_TRACK'] = 'balloon-hermes'
import subprocess
subprocess.run(['python3', os.path.expanduser('~/repos/balloon-fresh/tools/balloon-board-lock.py'), 
                'acquire', 'both', '--purpose', 'walk-capture', '--timeout', str(DURATION+30)],
               capture_output=True)

import serial

tx = serial.Serial(TX_PORT, BAUD, timeout=0.05)
rx = serial.Serial(RX_PORT, BAUD, timeout=0.05)
time.sleep(0.2)
tx.read(8192)  # drain
rx.read(8192)  # drain

sync_count = 0
stop_flag = threading.Event()

def tx_to_rx_forwarder():
    """Continuously read TX serial, forward GPS UTC to RX within milliseconds."""
    global sync_count
    buf = b''
    while not stop_flag.is_set():
        data = tx.read(4096)
        if not data:
            continue
        buf += data
        # Process complete lines
        while b'\n' in buf:
            line, buf = buf.split(b'\n', 1)
            line_str = line.decode('utf-8', errors='replace')
            # Forward GPS UTC to RX
            m = re.search(r'unix=(\d+)', line_str)
            if m:
                gps_utc = m.group(1)
                rx.write(f"SET_TIME {gps_utc}\n".encode())
                rx.flush()
                sync_count += 1
                if sync_count % 20 == 0:  # Print every ~2s (10Hz GPS)
                    print(f"[{time.strftime('%H:%M:%S')}] sync #{sync_count} GPS_UTC={gps_utc}")

# Start forwarder thread
fwd_thread = threading.Thread(target=tx_to_rx_forwarder, daemon=True)
fwd_thread.start()

print(f"=== WALK CAPTURE (Python GPS sync) ===")
print(f"Duration: {DURATION}s | RX: {RX_PORT} | TX: {TX_PORT}")
print(f"Output: {OUTFILE}")
print(f"GPS UTC forwarded in real-time (zero latency)")
print()

# Capture RX output
start = time.time()
with open(OUTFILE, 'w') as f:
    while time.time() - start < DURATION:
        data = rx.read(4096)
        if data:
            text = data.decode('utf-8', errors='replace')
            f.write(text)
            f.flush()

stop_flag.set()
time.sleep(0.5)

# Count results
with open(OUTFILE) as f:
    content = f.read()
lines = content.count('\n')
phases = content.count('PHASE_RESULT')
decoded = len(re.findall(r'rx=[1-9]', content))

print(f"\n=== DONE ===")
print(f"Sync pushes: {sync_count}")
print(f"Lines: {lines} | Phases: {phases} | Decoded: {decoded}")
print(f"File: {OUTFILE}")

# Release lock
subprocess.run(['python3', os.path.expanduser('~/repos/balloon-fresh/tools/balloon-board-lock.py'),
                'release', 'both'], capture_output=True)
