#!/usr/bin/env python3
"""Bounded ROM-ISP sync probe for an E80 board that is already in the ROM
bootloader (entered via the firmware's FLASH command).

Spams the 0x7F sync byte (8E1) and reports what comes back. No writes, no
loops beyond the given budget: if the ROM does not answer, the finding is
"this USB-serial bridge cannot drive the STM32 ROM protocol" and the board
needs a physical power-cycle.

Usage: python3 tools/rfa1b_isp_sync_probe.py --port /dev/ttyUSB1 [--seconds 20]
"""

from __future__ import annotations

import argparse
import time

import serial


def probe(port: str, baud: int, seconds: float, parity: str = "E") -> dict:
    ser = serial.Serial(port, baud, bytesize=8,
                        parity=serial.PARITY_EVEN if parity == "E" else serial.PARITY_NONE,
                        stopbits=1, timeout=0.05)
    got = b""
    acks = 0
    try:
        ser.reset_input_buffer()
        deadline = time.time() + seconds
        while time.time() < deadline:
            ser.write(b"\x7f")
            ser.flush()
            time.sleep(0.02)
            chunk = ser.read(64)
            if chunk:
                got += chunk
                acks += chunk.count(b"\x79")
                if acks:
                    break
    finally:
        ser.close()
    return {"port": port, "baud": baud, "parity": parity, "acks": acks, "bytes": got.hex()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True)
    ap.add_argument("--seconds", type=float, default=20.0)
    args = ap.parse_args()

    # 8E1 is the documented ROM framing; 8N1 is tried because the CH340 is
    # suspected of not driving the parity bit (the ROM itself only cares about
    # start/stop framing for the sync handshake).
    for parity in ("E", "N"):
        for baud in (57600, 115200, 9600, 38400):
            r = probe(args.port, baud, args.seconds, parity)
            print(f"{'8E1' if parity == 'E' else '8N1'} baud={baud}: acks={r['acks']} "
                  f"bytes={r['bytes'][:120]!r}", flush=True)
            if r["acks"]:
                print(f"SYNC OK (parity={parity} baud={baud})")
                return 0
    print("NO SYNC on any baud - bridge cannot drive the STM32 ROM protocol")
    return 4


if __name__ == "__main__":
    raise SystemExit(main())
