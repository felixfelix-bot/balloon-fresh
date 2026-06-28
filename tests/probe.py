#!/usr/bin/env python3
"""Quick probe: confirm device responsiveness + RP2040 reset-via-1200baud."""
import serial, time, sys

PY = sys.executable

def open_port(port, baud=115200, timeout=1.0):
    return serial.Serial(port, baud, timeout=timeout)

def drain(s, label, secs=2.0):
    """Read everything available for `secs` seconds."""
    s.timeout = 0.3
    end = time.time() + secs
    chunks = []
    while time.time() < end:
        data = s.read(4096)
        if data:
            chunks.append(data)
        else:
            time.sleep(0.1)
    out = b"".join(chunks)
    if out:
        print(f"[{label}] RX ({len(out)} bytes):\n{out.decode(errors='replace')}")
    else:
        print(f"[{label}] (no output)")
    return out

def try_reset_1200(port):
    """arduino-pico reset-on-1200baud: open at 1200, close. Returns True if likely reset."""
    try:
        s = serial.Serial(port, 1200, timeout=0.5)
        s.close()
        return True
    except Exception as e:
        print(f"  1200baud reset failed: {e}")
        return False

# Probe ESP32-A (ACM2)
print("=== ESP32-A /dev/ttyACM2 ===")
s = open_port("/dev/ttyACM2")
time.sleep(2.0)  # allow boot after port-open auto-reset
drain(s, "A-boot", 1.5)
s.write(b"CONFIG\n")
time.sleep(0.5)
drain(s, "A-CONFIG", 1.5)
s.close()

# Probe ESP32-B (ACM3)
print("\n=== ESP32-B /dev/ttyACM3 ===")
s = open_port("/dev/ttyACM3")
time.sleep(2.0)
drain(s, "B-boot", 1.5)
s.write(b"CONFIG\n")
time.sleep(0.5)
drain(s, "B-CONFIG", 1.5)
s.close()

# Probe RP2040 (ACM1) — try reset first
print("\n=== RP2040 /dev/ttyACM1 ===")
print("Attempting 1200baud reset...")
try_reset_1200("/dev/ttyACM1")
time.sleep(2.0)
s = open_port("/dev/ttyACM1")
drain(s, "RP2040-boot", 4.0)
s.close()

print("\nDone.")
