#!/usr/bin/env python3
"""Coordinated TX/RX test: arm RX first, then trigger TX."""
import serial, time, subprocess, sys

def find_port(serial_substr):
    out = subprocess.check_output("ls /dev/ttyACM*", shell=True, text=True)
    for port in out.strip().split():
        try:
            info = subprocess.check_output(["udevadm", "info", "--query=property", port], text=True)
            if serial_substr in info:
                return port.strip()
        except:
            pass
    return None

tx_port = find_port("8332")
rx_port = find_port("F242D")
if not tx_port or not rx_port:
    print(f"ERROR: TX={tx_port}, RX={rx_port}")
    sys.exit(1)

print(f"TX: {tx_port}, RX: {rx_port}")
tx = serial.Serial(tx_port, 115200, timeout=0.1)
rx = serial.Serial(rx_port, 115200, timeout=0.1)
time.sleep(0.5)
tx.read(4096)
rx.read(4096)

# Step 1: Arm RX first
print("Arming RX...")
rx.write(b"RUN\n")
rx.flush()
time.sleep(2)  # Let RX enter receive mode

# Step 2: Trigger TX
print("Triggering TX...")
tx.write(b"RUN\n")
tx.flush()

# Step 3: Capture for 15 seconds
print("Capturing 15s...")
start = time.time()
results = {"TX": [], "RX": []}

while time.time() - start < 15:
    for name, s in [("TX", tx), ("RX", rx)]:
        data = s.read(4096)
        if data:
            text = data.decode('ascii', errors='replace')
            for line in text.strip().split('\n'):
                if line.strip():
                    ts = time.strftime('%H:%M:%S')
                    entry = f"[{ts}][{name}] {line.strip()}"
                    print(entry)
                    results[name].append(entry)

tx.close()
rx.close()

with open('/tmp/coordinated_results.txt', 'w') as f:
    f.write(f"=== Coordinated TX/RX Test {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n\n")
    for name in ["TX", "RX"]:
        f.write(f"--- {name} ---\n")
        for line in results[name]:
            f.write(line + '\n')
        f.write('\n')

print(f"\nTX lines: {len(results['TX'])}, RX lines: {len(results['RX'])}")
print("Saved to /tmp/coordinated_results.txt")
