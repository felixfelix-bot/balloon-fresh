#!/usr/bin/env python3
"""Verify both E80 boards run the 2.4 GHz fw (expect fw=0561b29, 2 Mbaud console)."""
import glob, subprocess, time
import serial

def ch340_ports():
    ports = []
    for dev in sorted(glob.glob("/dev/ttyUSB*")):
        r = subprocess.run(["udevadm", "info", "-q", "property", "-n", dev],
                           capture_output=True, text=True, timeout=5)
        if "CH340" in r.stdout:
            ports.append(dev)
    return ports

def rd(ser, t=2.0):
    time.sleep(0.2)
    return ser.read(4096).decode(errors="replace")

ports = ch340_ports()
print("CH340 ports:", ports)
for p in ports:
    s = serial.Serial(p, 2000000, timeout=0.3)
    time.sleep(0.5)
    s.reset_input_buffer()
    s.write(b"ID?\r\n")
    print(f"--- {p} ---")
    print(rd(s).strip()[:300])
    # quick BAND OVERRIDE round-trip check (safety: reject wrong pin)
    s.reset_input_buffer()
    s.write(b"BAND OVERRIDE 0000\r\n")
    print("wrong-pin:", rd(s).strip()[:120])
    s.close()
