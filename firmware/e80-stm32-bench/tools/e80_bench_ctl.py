#!/usr/bin/env python3
"""E80 bench controller — scripts a full FLRC-650 PER run on two E80 boards.

Board A = TX, Board B = RX. Run: RX arm first, then TX burst, then poll STAT.

Usage:
    ./e80_bench_ctl.py --tx /dev/ttyUSB3 --rx /dev/ttyUSB4
    ./e80_bench_ctl.py --tx /dev/ttyUSB3 --rx /dev/ttyUSB4 --freq 868000000 \
        --n 1000 --len 255 --dbm 10
    ./e80_bench_ctl.py --dry-run          # print command script, no ports opened

Defaults follow the firmware safety policy: 868.0 MHz (EU SRD 863-870),
+10 dBm indoor cap. TX requires the firmware two-step (ROLE TX + ARM TX),
which this script performs. PA values above +10 dBm are rejected by firmware
unless 'POWER MODE OUTDOOR 2026' was issued (outdoor range sessions only).
"""
import argparse
import sys
import time

BAUD = 115200
PARITY = "N"
STOPBITS = 1


def build_script(args):
    """Command sequences sent to each board. Returns (tx_cmds, rx_cmds)."""
    rx_cmds = [
        "ID?",
        "ROLE RX",
        "FREQ {}".format(args.freq),
        "MOD flrc 650 {}".format(args.dbm),
        "START N={} LEN={} GAP={}".format(args.n, args.length, args.gap_us),
    ]
    tx_cmds = [
        "ID?",
        "ROLE TX",
        "ARM TX",
        "FREQ {}".format(args.freq),
        "MOD flrc 650 {}".format(args.dbm),
        "START N={} LEN={} GAP={}".format(args.n, args.length, args.gap_us),
    ]
    return tx_cmds, rx_cmds


class BoardSerial:
    """Minimal line-oriented serial console (BoardSerial pattern, inlined).

    Boards reply 'OK ...' or 'ERR <reason>' to every command, newline-terminated.
    """

    def __init__(self, port, baud=BAUD, timeout=5.0):
        import serial  # pyserial

        self.ser = serial.Serial(
            port=port,
            baudrate=baud,
            parity=PARITY,
            stopbits=STOPBITS,
            bytesize=8,
            timeout=timeout,
        )
        self.port = port
        self.drain()

    def drain(self, quiet=0.4):
        """Consume boot noise / stale output until line for `quiet` seconds."""
        self.ser.timeout = quiet
        while True:
            line = self.ser.readline().decode(errors="replace").strip()
            if not line:
                break
        self.ser.timeout = 5.0

    def cmd(self, line, expect_ok=True, timeout=15.0):
        self.ser.write((line + "\r\n").encode())
        deadline = time.time() + timeout
        while time.time() < deadline:
            reply = self.ser.readline().decode(errors="replace").strip()
            if not reply:
                continue
            print("  [{}] {} -> {}".format(self.port, line, reply))
            if reply.startswith("OK"):
                return reply
            if reply.startswith("ERR"):
                if expect_ok:
                    raise RuntimeError("{} rejected '{}': {}".format(self.port, line, reply))
                return reply
        raise RuntimeError("{}: timeout waiting for reply to '{}'".format(self.port, line))

    def stat(self):
        return self.cmd("STAT?")

    def close(self):
        self.ser.close()


def parse_stat(reply):
    """Parse 'OK STAT sent=.. recv=.. per=.. rssi=.. snr=.. elapsed_ms=.. kbps=..'
    into a dict. Tolerant of missing fields."""
    fields = {}
    for tok in reply.split()[2:]:  # skip 'OK STAT'
        if "=" in tok:
            k, v = tok.split("=", 1)
            fields[k] = v
    return fields


def run(args):
    tx_cmds, rx_cmds = build_script(args)

    print("== E80 FLRC bench: {} pkts x {} B @ FLRC-650, {} MHz, +{} dBm ==".format(
        args.n, args.length, args.freq / 1e6, args.dbm))

    print("-- RX board (arm first) --")
    rx = BoardSerial(args.rx)
    try:
        for c in rx_cmds:
            rx.cmd(c)
    finally:
        pass

    print("-- TX board --")
    tx = BoardSerial(args.tx)
    try:
        for c in tx_cmds:
            tx.cmd(c, timeout=max(30.0, args.n * (args.length * 8 / 650e3) + 30))
    finally:
        pass

    # Poll TX until burst complete, then read RX stats.
    burst_s = max(args.n * (args.length * 8 / 650e3) + args.n * args.gap_us / 1e6, 2.0)
    deadline = time.time() + burst_s + 60
    while time.time() < deadline:
        s = parse_stat(tx.stat())
        sent = int(s.get("sent", 0))
        if sent >= args.n:
            break
        time.sleep(2.0)
    time.sleep(2.0)  # let last packets land
    rx_stat = parse_stat(rx.stat())

    print()
    print("========= RESULTS =========")
    print("mode        FLRC-650")
    print("freq        {:.1f} MHz".format(args.freq / 1e6))
    print("tx power    +{} dBm".format(args.dbm))
    print("payload     {} B x {} pkts".format(args.length, args.n))
    for k in ("sent", "recv", "per", "rssi", "snr", "kbps", "per_ci_lo", "per_ci_hi"):
        if k in rx_stat or k in ("recv", "per"):
            print("{:<11} {}".format(k, rx_stat.get(k, "?")))
    tx.close()
    rx.close()
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tx", default="/dev/ttyUSB3", help="TX board serial port")
    ap.add_argument("--rx", default="/dev/ttyUSB4", help="RX board serial port")
    ap.add_argument("--freq", type=int, default=868000000,
                    help="Hz, must be inside 863-870 MHz (default 868000000)")
    ap.add_argument("--n", type=int, default=1000, help="packet count (default 1000)")
    ap.add_argument("--length", type=int, default=255, help="payload bytes (default 255)")
    ap.add_argument("--gap-us", dest="gap_us", type=int, default=5000,
                    help="inter-packet gap in us (default 5000)")
    ap.add_argument("--dbm", type=int, default=10,
                    help="TX power dBm, firmware caps at +10 indoor (default 10)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the command script without opening ports")
    args = ap.parse_args()

    if not (863000000 <= args.freq <= 870000000):
        sys.exit("freq must be within EU SRD 863-870 MHz (got {})".format(args.freq))
    if args.dbm > 10:
        print("note: +{} dBm exceeds indoor cap; firmware will ERR unless "
              "POWER MODE OUTDOOR 2026 was issued on the TX board".format(args.dbm))

    if args.dry_run:
        tx_cmds, rx_cmds = build_script(args)
        print("-- RX board --")
        for c in rx_cmds:
            print(c)
        print("-- TX board --")
        for c in tx_cmds:
            print(c)
        print("-- then poll: TX 'STAT?' until sent==N; read RX 'STAT?' --")
        return 0

    try:
        sys.exit(run(args))
    except RuntimeError as e:
        sys.exit("ERROR: {}".format(e))


if __name__ == "__main__":
    main()
