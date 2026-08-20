#!/usr/bin/env python3
"""Quick diagnostic: configure both boards for one config and capture ALL raw output."""

import serial
import time

TX_PORT = "/dev/ttyUSB3"
RX_PORT = "/dev/ttyUSB4"
BAUD = 2000000
FREQ = 868000000

def send(port, cmd, wait=0.1):
    port.write((cmd + "\r\n").encode())
    time.sleep(wait)
    resp = port.read(port.in_waiting or 4096)
    print(f"  >> {cmd:30s} -> {resp.decode(errors='replace').strip()[:120]}")
    return resp.decode(errors='replace')

tx = serial.Serial(TX_PORT, BAUD, timeout=0.5)
rx = serial.Serial(RX_PORT, BAUD, timeout=0.5)
time.sleep(0.3)

# Drain
tx.read(tx.in_waiting or 4096)
rx.read(rx.in_waiting or 4096)

print("=== Board IDs ===")
send(tx, "ID?", 0.3)
send(rx, "ID?", 0.3)

print("\n=== Stop both ===")
send(tx, "STOP", 0.1)
send(rx, "STOP", 0.1)
time.sleep(0.5)

print("\n=== Configure RX: ROLE RX ===")
send(rx, "ROLE RX", 0.1)
time.sleep(0.5)
send(rx, "MOD loRa 7 125", 0.1)
time.sleep(0.1)
send(rx, f"FREQ {FREQ}", 0.1)
time.sleep(0.1)
send(rx, "PA 10", 0.1)
time.sleep(0.1)
send(rx, "PRBS ON", 0.1)
time.sleep(0.1)
send(rx, "SESSION 1", 0.1)
time.sleep(0.1)
send(rx, "CONFIG 1 0", 0.1)

print("\n=== Configure TX: ROLE TX ===")
send(tx, "ROLE TX", 0.1)
time.sleep(0.5)
send(tx, "MOD loRa 7 125", 0.1)
time.sleep(0.1)
send(tx, f"FREQ {FREQ}", 0.1)
time.sleep(0.1)
send(tx, "PA 10", 0.1)
time.sleep(0.1)
send(tx, "SESSION 1", 0.1)
time.sleep(0.1)
send(tx, "CONFIG 1 0", 0.1)

print("\n=== Arm TX ===")
send(tx, "ARM TX", 0.2)

print("\n=== Check RX role/status ===")
send(rx, "ID?", 0.3)

print("\n=== Start TX (N=10 LEN=64 GAP=10000) ===")
send(tx, "START N=10 LEN=64 GAP=10000", 0.1)

print("\n=== Capturing RX raw output for 10 seconds ===")
# DO NOT drain — capture everything from now on
start = time.time()
while time.time() - start < 10.0:
    if rx.in_waiting:
        data = rx.read(rx.in_waiting)
        text = data.decode(errors='replace')
        for line in text.split('\n'):
            line = line.strip().strip('\r')
            if line:
                print(f"  RX_RAW: {line}")
    if tx.in_waiting:
        data = tx.read(tx.in_waiting)
        text = data.decode(errors='replace')
        for line in text.split('\n'):
            line = line.strip().strip('\r')
            if line:
                print(f"  TX_RAW: {line}")
    time.sleep(0.05)

print("\n=== Final STAT? ===")
send(tx, "STAT?", 0.5)
send(rx, "STAT?", 0.5)
send(rx, "ID?", 0.3)
send(tx, "ID?", 0.3)

tx.close()
rx.close()