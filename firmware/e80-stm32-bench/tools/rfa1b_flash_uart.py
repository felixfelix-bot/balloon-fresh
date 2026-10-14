#!/usr/bin/env python3
"""RFA-1b: dump + flash an E80 board over the UART ROM bootloader.

Path (firmware/e80-stm32-bench/FLASHING.md, verified for bench fw >= v1.2):

    1. send 'FLASH' over the console -> the firmware jumps to the STM32F1
       system ROM bootloader (no BOOT0/strap needed: BOOT0 is welded low on
       this hardware, so the reset-dance entry is impossible - see
       docs/E80-FLASH-ACCESS-FINDINGS.md)
    2. the ROM waits for the 0x7F sync byte indefinitely, so stm32flash has
       no race to lose; an interrupted session can simply be re-run

ORDER MATTERS: dump before write. The dump is the only copy of the firmware
that is currently on the board (fw 5fa7912 for the RFA-1b baseline), and its
build source no longer exists anywhere in the fleet.

Usage:
    python3 tools/rfa1b_flash_uart.py --port /dev/ttyUSB1 --dump out.bin \
        [--write build-fw/e80_bench.bin] [--host x240] [--baud 115200]

Exit codes: 0 ok, 2 no console reply, 3 FLASH refused, 4 ROM-ISP sync failed
(the board is then IN the ROM bootloader and needs a physical power-cycle),
5 verify failed.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

import serial

FLASH_SIZE = 65536
BASE = 0x08000000


def console(port: str, baud: int, cmd: str, expect: str, timeout_s: float = 4.0) -> str:
    ser = serial.Serial(port, baud, timeout=0.2, write_timeout=3.0)
    try:
        time.sleep(0.3)
        ser.reset_input_buffer()
        ser.write(cmd.encode() + b"\n")
        ser.flush()
        buf = b""
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            chunk = ser.read(4096)
            if chunk:
                buf += chunk
                if expect in buf.decode(errors="replace"):
                    break
                deadline = time.time() + 1.0
        return buf.decode(errors="replace")
    finally:
        ser.close()


def run_stm32flash(args: list[str]) -> subprocess.CompletedProcess:
    cmd = ["stm32flash"] + args
    print("  $ " + " ".join(cmd), flush=True)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=600)


def rom_isp(port: str, extra: list[str]) -> subprocess.CompletedProcess:
    # stm32flash handles the 8E1 ROM protocol itself (57.6k default).
    return run_stm32flash(["-g", hex(BASE)] + extra + [port])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True)
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--dump")
    ap.add_argument("--write")
    ap.add_argument("--host", default=None, help="informational: which host owns the port")
    args = ap.parse_args()

    where = f"{args.host}:{args.port}" if args.host else args.port
    print(f"=== E80 UART ROM-ISP on {where} ===", flush=True)

    idr = console(args.port, args.baud, "ID?", "ID E80BENCH")
    if "ID E80BENCH" not in idr:
        print(f"NO CONSOLE REPLY: {idr!r}", flush=True)
        return 2
    print("  ID: " + idr.strip().splitlines()[-1], flush=True)
    if "boot=jump-ok" not in idr:
        print("FLASH REFUSED: board reports ", idr.strip(), flush=True)
        return 3

    out = console(args.port, args.baud, "FLASH", "OK JUMPING TO BOOTLOADER", timeout_s=5.0)
    if "OK JUMPING TO BOOTLOADER" not in out:
        print(f"FLASH COMMAND NOT ACKED: {out!r}", flush=True)
        return 3
    print("  ROM bootloader entry acknowledged", flush=True)
    time.sleep(1.5)

    if args.dump:
        # -r needs the sync; if this fails the board is in the ROM already and
        # only a physical power-cycle brings the app back.
        r = run_stm32flash(["-r", args.dump] + [args.port])
        print(r.stdout.strip()[-600:] or r.stderr.strip()[-600:], flush=True)
        if not os.path.exists(args.dump) or os.path.getsize(args.dump) != FLASH_SIZE:
            size = os.path.getsize(args.dump) if os.path.exists(args.dump) else 0
            print(f"DUMP FAILED (size={size}, expected {FLASH_SIZE}) - ROM-ISP sync problem",
                  flush=True)
            return 4
        print(f"  dumped {FLASH_SIZE} B -> {args.dump}", flush=True)

    if args.write:
        r = rom_isp(args.port, ["-w", args.write, "-v"])
        print(r.stdout.strip()[-1200:] or r.stderr.strip()[-1200:], flush=True)
        low = ((r.stdout or "") + (r.stderr or "")).lower()
        if "failed to init" in low or "no response" in low or "failed to write" in low:
            print("WRITE FAILED", flush=True)
            return 5
        if "verified" not in low and "verify" not in low and "done" not in low:
            print("write returned without a verify/done marker - inspect output above", flush=True)
            return 5

    time.sleep(3.0)
    idr2 = console(args.port, args.baud, "ID?", "ID E80BENCH", timeout_s=6.0)
    print("  post-flash ID: " + (idr2.strip().splitlines()[-1] if idr2.strip() else "<none>"),
          flush=True)
    return 0 if "ID E80BENCH" in idr2 else 5


if __name__ == "__main__":
    sys.exit(main())
