#!/usr/bin/env python3
"""
Continuous GPS time forwarder + RX capture.
Reads TX serial line-by-line, forwards every GPS_UNIX to RX within milliseconds.
Simultaneously captures ALL RX output to log file.
Zero-latency sync — every unix= line forwarded the instant it arrives.

Usage: python3 time_forward_capture.py [duration_seconds]
"""
import serial, time, sys, threading, os

DURATION = int(sys.argv[1]) if len(sys.argv) > 1 else 170
BAUD = 115200

# Auto-detect ports by serial number
TX_PORT = None
RX_PORT = None
import subprocess
for p in ['/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyACM2', '/dev/ttyACM3', '/dev/ttyACM4']:
    if not os.path.exists(p):
        continue
    try:
        r = subprocess.run(['udevadm', 'info', '-q', 'property', '-n', p],
                         capture_output=True, text=True, timeout=2)
        for line in r.stdout.split('\n'):
            if 'ID_SERIAL_SHORT=' in line:
                sn = line.split('=', 1)[1]
                if '242D' in sn:
                    TX_PORT = p
                elif '8332' in sn:
                    RX_PORT = p
    except:
        pass

if not TX_PORT or not RX_PORT:
    print(f"ERROR: Cannot find boards. TX={TX_PORT} RX={RX_PORT}")
    sys.exit(1)

OUTDIR = os.path.expanduser('~/repos/balloon-fresh/data/range-tests/20260725')
os.makedirs(OUTDIR, exist_ok=True)
OUTFILE = os.path.join(OUTDIR, f"forwarded-{time.strftime('%H%M%S')}.log")

print(f"=== TIME FORWARD + CAPTURE ===")
print(f"TX={TX_PORT} RX={RX_PORT} Duration={DURATION}s")
print(f"Output: {OUTFILE}")
print(f"GPS UTC forwarded line-by-line (zero latency)")

# Open serial ports
tx = serial.Serial(TX_PORT, BAUD, timeout=0.01)
rx = serial.Serial(RX_PORT, BAUD, timeout=0.01)
time.sleep(0.2)

# Shared state
latest_utc = None
sync_count = 0
capture_lines = []

# Thread: read TX continuously, forward GPS UTC to RX immediately
def tx_forwarder():
    global latest_utc, sync_count
    buf = b""
    while not stop_event.is_set():
        data = tx.read(4096)
        if data:
            buf += data
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line_str = line.decode('ascii', errors='ignore').strip()
                # Extract GPS UTC
                if 'unix=' in line_str:
                    import re
                    m = re.search(r'unix=(\d{10,})', line_str)
                    if m:
                        utc = m.group(1)
                        latest_utc = utc
                        # Forward IMMEDIATELY to RX
                        rx.write(f"SET_TIME {utc}\n".encode())
                        sync_count += 1

stop_event = threading.Event()

# Start forwarder thread
fwd_thread = threading.Thread(target=tx_forwarder, daemon=True)
fwd_thread.start()

# Main: capture RX output for DURATION seconds
start = time.time()
while time.time() - start < DURATION:
    data = rx.read(4096)
    if data:
        text = data.decode('ascii', errors='ignore')
        capture_lines.append(text)
        sys.stdout.write(text)
        sys.stdout.flush()

stop_event.set()
fwd_thread.join(timeout=2)
tx.close()
rx.close()

# Save captured data
with open(OUTFILE, 'w') as f:
    f.writelines(capture_lines)

# Parse results
with open(OUTFILE) as f:
    content = f.read()

phase_results = [l for l in content.split('\n') if 'PHASE_RESULT' in l]
decoded = [l for l in phase_results if 'rx=0' not in l.split('rx=')[1][:1] or 'rx=1' in l or 'rx=2' in l or 'rx=3' in l or 'rx=4' in l or 'rx=5' in l]

# Better parse
import re
total_phases = len(phase_results)
decoded_count = 0
for line in phase_results:
    m = re.search(r'rx=(\d+)', line)
    if m and int(m.group(1)) > 0:
        decoded_count += 1

print(f"\n=== RESULTS ===")
print(f"Sync pushes: {sync_count}")
print(f"Total phases: {total_phases}")
print(f"Decoded: {decoded_count}")
print(f"File: {OUTFILE}")

# Show decoded phases
for line in phase_results:
    m = re.search(r'rx=(\d+)', line)
    if m and int(m.group(1)) > 0:
        parts = line.split()
        phase_id = parts[1] if len(parts) > 1 else "?"
        mode = parts[2] if len(parts) > 2 else "?"
        rx_val = m.group(1)
        per_m = re.search(r'per=([\d.]+)', line)
        rssi_m = re.search(r'rssi_avg=(-?\d+)', line)
        per = per_m.group(1) if per_m else "?"
        rssi = rssi_m.group(1) if rssi_m else "?"
        print(f"  OK  P{phase_id:>3} {mode:<24} rx={rx_val:>4} PER={per}% RSSI={rssi}")

# Show failed phases
print(f"\n=== FAILED ===")
for line in phase_results:
    m = re.search(r'rx=(\d+)', line)
    if m and int(m.group(1)) == 0 and 'SKIP' not in line:
        parts = line.split()
        phase_id = parts[1] if len(parts) > 1 else "?"
        mode = parts[2] if len(parts) > 2 else "?"
        print(f"  XX  P{phase_id:>3} {mode}")
