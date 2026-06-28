#!/usr/bin/env python3
"""Targeted LoRa + RP2040 interop test."""
import serial, time, re, sys

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

# === LoRa test with wider BW ===
print("=== LoRa SF7 BW1625 2450MHz 255B 50pkts ===", flush=True)
sa = esp(A); sb = esp(B)

# RX first - use BW 1625 (known SX128x value) instead of 500
rx_init = cmd(sb, "ROLE RX", 0.3)
print(f"RX ROLE: {rx_init.strip()[:100]}", flush=True)
cmd(sb, "MODE LORA", 0.3)
cmd(sb, "FREQ 2450", 0.3)
cmd(sb, "SF 7", 0.3)
cmd(sb, "BW 1625", 0.3)  # Changed from 500 to 1625
cmd(sb, "SIZE 255", 0.3)
rx_cfg = cmd(sb, "CONFIG", 0.3)
print(f"RX config: {rx_cfg.strip()[:150]}", flush=True)
rx_run = cmd(sb, "RUN", 0.5)
print(f"RX run: {rx_run.strip()[:100]}", flush=True)

# TX
cmd(sa, "ROLE TX", 0.3)
cmd(sa, "MODE LORA", 0.3)
cmd(sa, "FREQ 2450", 0.3)
cmd(sa, "SF 7", 0.3)
cmd(sa, "BW 1625", 0.3)  # Match
cmd(sa, "PWR 12", 0.3)
cmd(sa, "SIZE 255", 0.3)
cmd(sa, "COUNT 50", 0.3)
cmd(sa, "DELAY 200", 0.3)

print("TX firing...", flush=True)
tx = cmd(sa, "RUN", 12)
print(f"TX: {tx.strip()[:200]}", flush=True)

rx = drain(sb, 25)
print(f"RX ({len(rx)}B): {rx.strip()[:500]}", flush=True)

# === RP2040 test ===
print("\n=== RP2040 probe ===", flush=True)
sa.close(); sb.close()
try:
    sr = serial.Serial(R, 115200, timeout=1)
    sr.dtr = True; time.sleep(0.5)
    boot = drain(sr, 3)
    print(f"Boot: {boot.strip()[:300]}", flush=True)
    
    # Send 'T' for TX test  
    sr.write(b"T\n")
    txr = drain(sr, 10)
    print(f"TX output: {txr.strip()[:400]}", flush=True)
    sr.close()
except Exception as e:
    print(f"RP2040: {e}", flush=True)

print("\n=== DONE ===", flush=True)
