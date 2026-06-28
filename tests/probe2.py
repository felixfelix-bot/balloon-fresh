#!/usr/bin/env python3
"""Deeper probe: try DTR/RTS combos + esptool-style reset, long reads."""
import serial, time

def deep_probe(port, label):
    print(f"\n===== {label} @ {port} =====")
    # Open with DTR asserted (USB-CDC often gates output on DTR)
    for dtr, rts in [(True, False), (False, False)]:
        try:
            s = serial.Serial()
            s.port = port
            s.baudrate = 115200
            s.dtr = dtr
            s.rts = rts
            s.timeout = 0.5
            s.open()
            break
        except Exception as e:
            print(f"  open dtr={dtr} failed: {e}")
            continue
    # esptool-style reset for native USB Serial/JTAG: toggle DTR/RTS
    try:
        s.dtr = False; s.rts = True   # EN low (via RTS on usb-jtag? actually n/a)
        time.sleep(0.1)
        s.dtr = True;  s.rts = False
        time.sleep(0.05)
        s.dtr = False
    except Exception:
        pass
    # collect boot output for 4s
    s.timeout = 0.3
    end = time.time() + 4.0
    chunks = []
    while time.time() < end:
        d = s.read(4096)
        if d:
            chunks.append(d)
        else:
            time.sleep(0.1)
    out = b"".join(chunks)
    print(f"  boot ({len(out)}B): {out.decode(errors='replace')[:600]!r}")
    # send CONFIG and HELP, read
    s.write(b"CONFIG\n")
    time.sleep(0.4)
    s.write(b"HELP\n")
    time.sleep(0.8)
    end = time.time() + 2.0
    chunks = []
    while time.time() < end:
        d = s.read(4096)
        if d: chunks.append(d)
        else: time.sleep(0.1)
    out = b"".join(chunks)
    print(f"  resp ({len(out)}B): {out.decode(errors='replace')[:600]!r}")
    s.close()

deep_probe("/dev/ttyACM2", "ESP32-A")
deep_probe("/dev/ttyACM3", "ESP32-B")

# RP2040: 1200baud reset then read boot banner
print("\n===== RP2040 @ /dev/ttyACM1 =====")
try:
    r = serial.Serial("/dev/ttyACM1", 1200); r.close()
    print("  1200baud reset sent")
except Exception as e:
    print(f"  1200baud reset err: {e}")
time.sleep(2.5)
s = serial.Serial("/dev/ttyACM1", 115200, timeout=0.3); s.dtr=True
s.timeout=0.3; end=time.time()+4.0; chunks=[]
while time.time()<end:
    d=s.read(4096)
    if d: chunks.append(d)
    else: time.sleep(0.1)
out=b"".join(chunks)
print(f"  boot ({len(out)}B): {out.decode(errors='replace')[:800]!r}")
s.close()
