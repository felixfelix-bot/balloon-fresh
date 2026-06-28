#!/usr/bin/env python3
"""Quick interop test: ESP32-A→B FLRC+LoRa, RP2040 probe."""
import serial, time, re

A = "/dev/ttyACM2"
B = "/dev/ttyACM3"
R = "/dev/ttyACM1"

def esp(port):
    s = serial.Serial()
    s.port = port; s.baudrate = 115200; s.dtr = False; s.rts = False; s.timeout = 0.5
    s.open(); time.sleep(0.3); s.read(65536)
    return s

def cmd(s, c, w=0.5):
    s.write((c + "\n").encode()); time.sleep(w)
    r = b""
    for _ in range(10):
        d = s.read(4096)
        if d: r += d
        else: break
    return r.decode(errors='replace')

def drain(s, t):
    s.timeout = 0.3; end = time.time() + t; chunks = []
    while time.time() < end:
        d = s.read(4096)
        if d: chunks.append(d)
    return b"".join(chunks).decode(errors='replace')

print("=== PROBE ===")
sa = esp(A); sb = esp(B)
print("A:", cmd(sa, 'CONFIG', 0.5).strip()[:100])
print("B:", cmd(sb, 'CONFIG', 0.5).strip()[:100])

# T1: ESP32-A TX -> ESP32-B RX (FLRC)
print("\n=== T1: ESP32-A>B FLRC 2600 255B 100pkts ===")
for c in ["ROLE RX","MODE FLRC","FREQ 2450","BR 2600","PWR 12","SIZE 255","RUN"]:
    cmd(sb, c, 0.2)
for c in ["ROLE TX","MODE FLRC","FREQ 2450","BR 2600","PWR 12","SIZE 255","COUNT 100","DELAY 10"]:
    cmd(sa, c, 0.2)
print("TX firing...")
tx = cmd(sa, "RUN", 8)
print("TX:", tx.strip()[:200])
rx = drain(sb, 15)
print("RX (%dB): %s" % (len(rx), rx.strip()[:400]))
rxc = re.findall(r'rx=(\d+)', rx, re.I)
rssi = re.findall(r'RSSI[:\s]+(-?\d+)', rx)
print("Parsed: rx=%s rssi=%s" % (rxc, rssi))

# T2: LoRa mode
print("\n=== T2: ESP32-A>B LORA SF7 BW500 ===")
for c in ["ROLE RX","MODE LORA","FREQ 2450","SF 7","BW 500","SIZE 255","RUN"]:
    cmd(sb, c, 0.2)
for c in ["ROLE TX","MODE LORA","FREQ 2450","SF 7","BW 500","PWR 12","SIZE 255","COUNT 50","DELAY 100"]:
    cmd(sa, c, 0.2)
print("TX firing...")
tx = cmd(sa, "RUN", 10)
print("TX:", tx.strip()[:200])
rx = drain(sb, 20)
print("RX (%dB): %s" % (len(rx), rx.strip()[:400]))
rxc = re.findall(r'rx=(\d+)', rx, re.I)
rssi = re.findall(r'RSSI[:\s]+(-?\d+)', rx)
print("Parsed: rx=%s rssi=%s" % (rxc, rssi))

# RP2040
print("\n=== RP2040 probe ===")
try:
    sr = serial.Serial(R, 115200, timeout=1)
    sr.dtr = True; time.sleep(0.5)
    boot = drain(sr, 3)
    print("RP2040 boot:", boot.strip()[:200])
    sr.write(b"T\n")
    time.sleep(5)
    txr = drain(sr, 5)
    print("RP2040 TX:", txr.strip()[:300])
    sr.close()
except Exception as e:
    print("RP2040:", e)

sa.close(); sb.close()
print("\n=== DONE ===")
