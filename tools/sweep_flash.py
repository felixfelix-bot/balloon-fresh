#!/usr/bin/env python3
"""
Flash sweep firmware to both RP2040 boards.
Uses picotool upload + USB authorized toggle for power cycle.
All board access goes through BoardSerial for verification.

Usage:
  BALLOON_TRACK=speed-tests python3 sweep_flash.py
"""
import os
import sys
import subprocess
import time

os.environ.setdefault("BALLOON_TRACK", "speed-tests")

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

PIO_DIR = os.path.expanduser("~/worktrees/balloon-speed-tests/firmware/rp2040")

def find_port_by_serial(serial_fragment):
    """Find /dev/ttyACMx by udev serial number."""
    import glob
    for port in sorted(glob.glob("/dev/ttyACM*")):
        try:
            result = subprocess.run(
                ["udevadm", "info", "-q", "property", "-n", port],
                capture_output=True, text=True, timeout=5
            )
            if serial_fragment in result.stdout:
                return port
        except:
            pass
    return None

def usb_power_cycle(serial_fragment):
    """Toggle USB authorized to force CDC re-enumeration."""
    for d in os.listdir("/sys/bus/usb/devices/"):
        devpath = f"/sys/bus/usb/devices/{d}"
        try:
            with open(f"{devpath}/idVendor") as f:
                if f.read().strip() != "2e8a":
                    continue
            with open(f"{devpath}/serial") as f:
                if serial_fragment not in f.read():
                    continue
        except (FileNotFoundError, PermissionError):
            continue
        print(f"  Power-cycling {serial_fragment} at {devpath}")
        subprocess.run(["sudo", "sh", "-c", f"echo 0 > {devpath}/authorized"])
        time.sleep(2)
        subprocess.run(["sudo", "sh", "-c", f"echo 1 > {devpath}/authorized"])
        return True
    print(f"  WARNING: Could not find USB device for {serial_fragment}")
    return False

def flash_board(port, env, label):
    """Flash via picotool upload."""
    print(f"=== Flash {label} ({port}) ===")
    r = subprocess.run(
        ["pio", "run", "-e", env, "-t", "upload", "--upload-port", port],
        cwd=PIO_DIR, capture_output=True, text=True
    )
    if "SUCCESS" in r.stdout:
        print(f"  Flash SUCCESS")
        return True
    else:
        print(f"  Flash FAILED: {r.stdout[-200:]}")
        return False

# Find boards by serial
rx_port = find_port_by_serial("8332")
tx_port = find_port_by_serial("F242D")

if not rx_port or not tx_port:
    print(f"ERROR: Could not find boards. RX={rx_port}, TX={tx_port}")
    sys.exit(1)

print(f"RX (8332): {rx_port}")
print(f"TX (F242D): {tx_port}")

# Flash both
flash_board(rx_port, "rp2040-sweep-rx", "RX")
flash_board(tx_port, "rp2040-sweep-tx", "TX")

# USB power cycle both (REQUIRED — USB CDC dies after picotool flash)
print("\n=== USB power cycle ===")
usb_power_cycle("8332")
usb_power_cycle("F242D")

# Wait for re-enumeration
time.sleep(8)

# Verify using BoardSerial
print("\n=== Verify ===")
from board_serial import BoardSerial

for port, label in [(rx_port, "RX"), (tx_port, "TX")]:
    try:
        s = BoardSerial(port, 115200, timeout=3)
        time.sleep(0.5)
        data = s.read(8192)
        s.close()
        text = data.decode(errors="replace").strip()
        if text:
            lines = [l for l in text.split("\n") if l.strip()][-3:]
            print(f"  {label}: {' | '.join(lines)[:200]}")
        else:
            print(f"  {label}: SILENT (may need more time)")
    except Exception as e:
        print(f"  {label}: ERROR {e}")

print("\nDone. Both boards should be sweeping.")
