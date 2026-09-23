#!/usr/bin/env python3
"""E28/SX1282 ToF ranging bench harness (LILYGO T3S3 x2 on one host).

Board identity is resolved from the USB-Serial-JTAG MAC in
/dev/serial/by-id/ (stable across replug; ttyACM numbers are not).

Usage:
  e28_range_bench.py [--iters N] [--pa DBM] [--sf N] [--freq HZ]
                     [--master-serial 9C:13:9E:F1:0C:28]
                     [--slave-serial  9C:13:9E:F1:0C:60]
                     [--log FILE]

Protocol (firmware/esp32-e28-range console):
  slave: RANGE-SLAVE  -> blocks up to 10 s answering one ranging exchange
  master: RANGE       -> one exchange -> DIST=<m>m | RANGE TIMEOUT
  both: RANGE?  -> last distance ; STAT? -> role/freq/sf/bw/pa/addr/last/err
"""
import argparse
import glob
import os
import re
import sys
import time

import serial  # pyserial 3.5

BAUD = 115200
BY_ID_GLOB = "/dev/serial/by-id/*"


def resolve_port(serial_short, by_id_glob=BY_ID_GLOB):
    """Map a board USB serial (MAC, e.g. 9C:13:9E:F1:0C:28) to a tty path.

    Board identity MUST come from the USB serial, not the ttyACM number: the
    numbers are reassigned on every replug and the two boards are otherwise
    indistinguishable. Raises LookupError when the board is absent.
    """
    hits = glob.glob(by_id_glob)
    matches = [h for h in hits if serial_short in h]
    if not matches:
        raise LookupError("no device with USB serial %s (present: %s)"
                          % (serial_short, sorted(hits)))
    return os.path.realpath(matches[0])


def parse_distance(line):
    """Extract the metres value from a 'DIST=<m>m' console line, else None."""
    m = re.search(r"DIST=([-+0-9]*\.?[0-9]+)m", line)
    return float(m.group(1)) if m else None


def parse_stat(line):
    """Parse a STAT? line into a dict. Absent fields are simply omitted.

    STAT? -> role=<master|slave|idle> freq=<MHz> sf=<n> bw=<kHz> pa=<dBm>
             addr=<0x..> last=<m|none> err=<code>
    """
    out = {}
    for key in ("role", "freq", "sf", "bw", "pa", "addr", "last", "err"):
        m = re.search(r"\b%s=([^\s]+)" % key, line)
        if m:
            out[key] = m.group(1)
    return out


def is_timeout(line):
    return "TIMEOUT" in line.upper()


def open_port(path):
    """Open without asserting DTR/RTS (both asserted = ESP32-S3 reset/download)."""
    ser = serial.Serial()
    ser.port = path
    ser.baudrate = BAUD
    ser.timeout = 0.2
    ser.dtr = False
    ser.rts = False
    ser.open()
    time.sleep(0.15)
    return ser


def send(ser, cmd):
    ser.write((cmd + "\r\n").encode())
    ser.flush()


def drain(ser, seconds, sink, tag):
    """Read lines for `seconds`, append (t, tag, line) to sink, return lines."""
    out = []
    end = time.time() + seconds
    buf = b""
    while time.time() < end:
        chunk = ser.read(4096)
        if chunk:
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.decode("utf-8", "replace").strip()
                if line:
                    sink.append((time.time(), tag, line))
                    out.append(line)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=5)
    ap.add_argument("--pa", type=int, default=None)
    ap.add_argument("--sf", type=int, default=None)
    ap.add_argument("--freq", type=int, default=None)
    ap.add_argument("--master-serial", default="9C:13:9E:F1:0C:28")
    ap.add_argument("--slave-serial", default="9C:13:9E:F1:0C:60")
    ap.add_argument("--log", default="/tmp/e28_ranging_run.log")
    args = ap.parse_args()

    mpath = resolve_port(args.master_serial)
    spath = resolve_port(args.slave_serial)
    print("master(serial %s) = %s" % (args.master_serial, mpath))
    print("slave (serial %s) = %s" % (args.slave_serial, spath))

    m = open_port(mpath)
    s = open_port(spath)
    log = []

    # ---- identity + config -------------------------------------------------
    for name, ser in (("master", m), ("slave", s)):
        send(ser, "ID?")
        send(ser, "STAT?")
        lines = drain(ser, 1.5, log, name)
        print("%s: %s" % (name, " | ".join(lines) if lines else "<no reply>"))

    if args.pa is not None:
        for name, ser in (("master", m), ("slave", s)):
            send(ser, "PA %d" % args.pa)
            print("%s: %s" % (name, " | ".join(drain(ser, 0.8, log, name))))
    if args.sf is not None:
        for name, ser in (("master", m), ("slave", s)):
            send(ser, "SF %d" % args.sf)
            print("%s: %s" % (name, " | ".join(drain(ser, 0.8, log, name))))
    if args.freq is not None:
        for name, ser in (("master", m), ("slave", s)):
            send(ser, "FREQ %d" % args.freq)
            print("%s: %s" % (name, " | ".join(drain(ser, 0.8, log, name))))

    # ---- ranging loop -----------------------------------------------------
    results = []
    for i in range(1, args.iters + 1):
        print("\n--- ranging %d/%d ---" % (i, args.iters))
        # slave arms first (blocks up to 10 s), then master initiates
        send(s, "RANGE-SLAVE")
        time.sleep(0.3)
        send(m, "RANGE")
        mlines, slines = [], []
        end = time.time() + 12.0
        while time.time() < end:
            mlines += drain(m, 0.25, log, "master")
            slines += drain(s, 0.25, log, "slave")
            if any("DIST=" in l or "TIMEOUT" in l for l in mlines):
                break
        print("  master: %s" % (" | ".join(mlines) if mlines else "<no reply>"))
        print("  slave : %s" % (" | ".join(slines) if slines else "<no reply>"))
        dist = None
        for l in mlines:
            d = parse_distance(l)
            if d is not None:
                dist = d
        results.append(dist)
        time.sleep(0.4)

    # ---- RANGE? + STAT? final --------------------------------------------
    print("\n--- final state ---")
    for name, ser in (("master", m), ("slave", s)):
        send(ser, "RANGE?")
        send(ser, "STAT?")
        print("%s: %s" % (name, " | ".join(drain(ser, 1.2, log, name))))

    m.close()
    s.close()

    ok = [r for r in results if r is not None]
    print("\n===== SUMMARY =====")
    print("ranging attempts : %d" % args.iters)
    print("valid distances  : %d" % len(ok))
    if ok:
        print("distances (m)    : %s" % ", ".join("%.3f" % r for r in ok))
        print("min/mean/max     : %.3f / %.3f / %.3f"
              % (min(ok), sum(ok) / len(ok), max(ok)))
    else:
        print("distances        : NONE (all attempts timed out)")

    with open(args.log, "w") as fh:
        for t, tag, line in log:
            fh.write("%.3f\t%s\t%s\n" % (t, tag, line))
    print("\nraw log: %s (%d lines)" % (args.log, len(log)))
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
