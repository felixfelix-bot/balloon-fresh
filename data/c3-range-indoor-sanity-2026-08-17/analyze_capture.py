#!/usr/bin/env python3
"""Analyze range-test RX serial capture (raw log from rx_capture.py).

Prints: boot/reboot count, scan rotations, sync locks per window,
per-window RESULT table (recv/total, PER, RSSI), PKT counts, errors.

Usage: analyze_capture.py RAWLOG
"""
import re
import sys

RAW = sys.argv[1]

boot_banner = re.compile(r"=== LR2021 Range Test")
rst_marker = re.compile(r"rst:0x|boot:0x|load:0x")
scan_line = re.compile(r"Scanning: (\S+) (\S+)")
win_lock = re.compile(r">>> Window (\d+): (\S+)")
win_done = re.compile(r"<<< Window (\d+) DONE: recv=(\d+)/(\d+)")
result_line = re.compile(r"^.*\] (RESULT,.*)$")
pkt_line = re.compile(r"^.*\] (PKT,.*)$")
err_line = re.compile(r"(Radio init failed|Failed to init|spiTransfer failed|spi_bus_initialize failed|Guru Meditation|abort\(\)|assert failed|backtrace)", re.I)

boots = 0
rsts = 0
scans = []
locks = []
dones = []
results = []
pkts = 0
errs = []

with open(RAW, "r", errors="replace") as f:
    for line in f:
        if boot_banner.search(line):
            boots += 1
        if rst_marker.search(line):
            rsts += 1
        m = scan_line.search(line)
        if m:
            scans.append(m.group(0))
        m = win_lock.search(line)
        if m:
            locks.append((m.group(1), m.group(2)))
        m = win_done.search(line)
        if m:
            dones.append((m.group(1), int(m.group(2)), int(m.group(3))))
        m = result_line.match(line)
        if m:
            results.append(m.group(1))
        if pkt_line.match(line):
            pkts += 1
        m = err_line.search(line)
        if m:
            errs.append(line.strip())

print(f"== {RAW} ==")
print(f"app_main banners (boots): {boots}")
print(f"rst/boot markers:         {rsts}")
print(f"PKT lines:                {pkts}")
print(f"scan rotations:           {len(scans)}")
print(f"window sync locks:        {len(locks)}")
print(f"window DONE lines:        {len(dones)}")
print(f"RESULT lines:             {len(results)}")
print(f"error-ish lines:          {len(errs)}")

print("\n-- window sync locks (in order) --")
for wid, name in locks:
    print(f"  win {wid}: {name}")

print("\n-- RESULT lines (recv>0 => decoded) --")
decoded = set()
for r in results:
    fields = r.split(",")
    # RESULT,loop,winid,name,mode,freq,br,sf,bw,cr,pwr,pkt_size,total,recv,...
    try:
        winid = fields[2]
        total = int(fields[12])
        recv = int(fields[13])
        per = fields[14]
        rssi = fields[17]
        if recv > 0:
            decoded.add((winid, fields[3]))
        print(f"  win {winid:>2} {fields[3]:<14} mode={fields[4]:<4} recv={recv}/{total} PER={per}% RSSI={rssi}")
    except (IndexError, ValueError):
        print(f"  unparsed: {r[:100]}")

print(f"\ndecoded windows (recv>0): {sorted(decoded, key=lambda x: int(x[0]))}")
if errs:
    print("\n-- first 10 error lines --")
    for e in errs[:10]:
        print(f"  {e[:160]}")
