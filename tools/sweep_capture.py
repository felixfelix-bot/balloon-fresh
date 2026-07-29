#!/usr/bin/env python3
"""
Multi-radio sweep capture script.
Uses BoardSerial wrapper — enforces board lock.
NEVER use raw serial.Serial() or stty/cat for board access.

Usage:
  BALLOON_TRACK=speed-tests python3 sweep_capture.py [duration_seconds]
"""
import os
import sys
import subprocess
import time

# CRITICAL: Set BALLOON_TRACK before importing BoardSerial
os.environ.setdefault("BALLOON_TRACK", "speed-tests")

# Add board tools to path
TOOLS_DIR = os.path.expanduser("~/repos/balloon-fresh/tools")
sys.path.insert(0, TOOLS_DIR)

# Pre-flight lock assertion
r = subprocess.run(
    ["python3", os.path.join(TOOLS_DIR, "board-lock-assert.py"), "tx", "rx"],
    capture_output=True, text=True
)
if r.returncode != 0:
    print(f"LOCK ASSERT FAILED:\n{r.stdout}\n{r.stderr}")
    sys.exit(1)

from board_serial import BoardSerial

DURATION = int(sys.argv[1]) if len(sys.argv) > 1 else 360

# Find RX board by serial number (ports swap on reboot)
def find_rx_port():
    """Find the 8332 board (RX) by udev serial."""
    import glob
    for port in sorted(glob.glob("/dev/ttyACM*")):
        try:
            result = subprocess.run(
                ["udevadm", "info", "-q", "property", "-n", port],
                capture_output=True, text=True, timeout=5
            )
            if "8332" in result.stdout:
                return port
        except:
            pass
    return "/dev/ttyACM0"  # fallback

def find_tx_port():
    """Find the F242D board (TX) by udev serial."""
    import glob
    for port in sorted(glob.glob("/dev/ttyACM*")):
        try:
            result = subprocess.run(
                ["udevadm", "info", "-q", "property", "-n", port],
                capture_output=True, text=True, timeout=5
            )
            if "F242D" in result.stdout:
                return port
        except:
            pass
    return "/dev/ttyACM2"  # fallback

rx_port = find_rx_port()
print(f"RX port: {rx_port} (8332)")

# Open RX with BoardSerial (enforces lock)
rx = BoardSerial(rx_port, 115200, timeout=0.1)
rx.read(65536)  # flush

rx_data = bytearray()
start = time.time()
while time.time() - start < DURATION:
    try:
        chunk = rx.read(4096)
        if chunk:
            rx_data.extend(chunk)
    except Exception as e:
        print(f"Read error: {e}")
        break

rx.close()

# Parse and display results
print(f"\n=== RX RESULTS ({DURATION}s capture) ===")
lines = rx_data.decode(errors="replace").split("\n")
for line in lines:
    l = line.strip()
    if any(k in l for k in ["PHASE_RESULT", "CYCLE", "DEBUG_RSSI"]):
        print(f"  {l[:140]}")
