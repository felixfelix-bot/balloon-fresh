#!/usr/bin/env python3
"""BUF-T3 flash smoke — 10x full-capacity BUF LOAD + CRC + src= smokes.

Hardware: E80 TX board console (CH340 /dev/ttyUSB3, 115200 8N1).
Firmware: buf/t2-impl (91cd0ae), bin at
  ~/repos/balloon-e80bench/firmware/e80-stm32-bench/build-fw/e80_bench.bin
  (26828 B / 40.94% flash — build verified 2026-08-21).

Gates (kanban t_dd4e516b, FLASH-QUEUE approved row):
  G1  10/10 full 4096-B random loads reply 'OK BUF 4096 1' (CRC OK)
  G2  START with staged buffer replies 'OK START ... src=BUF'
  G3  after BUF CLEAR, START replies 'OK START ... src=PRBS'

Binary-phase rules (docs/plans/tx-buffer-spec.md):
  - Command lines use CRLF consistently.  The firmware drains the UART
    RXNE register and swallows the pending '\n' in console_binary_start()
    BEFORE entering the binary phase, so no '\n' leaks into the payload.
  - Dedicated non-retrying loader: once 'OK BINARY <n>' is seen there is
    NO reset_input_buffer and NO retry — a corrupted load fails loudly.
  - Idle timeout 1.0 s between payload bytes; firmware is silent between
    the ack and the verdict line.
IWDG: starts at the first ARM TX (2-4 s window, superloop-fed). In armed
sequences START is sent immediately after the ARM ack — host gaps < 1 s.

Exit code 0 iff all gates pass.
"""

import argparse
import os
import sys
import time

import serial

# Golden CRC-16/CCITT-FALSE vectors shared C<->Python (buffer.c, T1).
GOLDEN = [
    (b"123456789", 0x29B1),
    (bytes(64), 0xD6DA),
    (bytes(i % 256 for i in range(4096)), 0x0F69),
]


def crc16_ccitt_false(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if (crc & 0x8000) else (crc << 1)
            crc &= 0xFFFF
    return crc


class Fail(Exception):
    pass


class Console:
    def __init__(self, port: str, baud: int = 115200, log=print):
        self.ser = serial.Serial(port, baud, timeout=0.05)
        self.log = log
        self.t0 = time.monotonic()
        # Hygiene flush ONCE, in line mode, before any binary phase.
        self.ser.reset_input_buffer()

    def ts(self) -> str:
        return f"[{time.monotonic() - self.t0:7.3f}]"

    def write_raw(self, data: bytes) -> None:
        n = self.ser.write(data)
        if n != len(data):
            raise Fail(f"short write: {n}/{len(data)}")

    def cmd(self, line: str) -> str:
        """Line-mode command with CRLF; returns the first reply line."""
        self.write_raw(line.encode() + b"\r\n")
        return self.readline()

    def readline(self, timeout: float = 3.0) -> str:
        """One console line (stripped); raises on timeout."""
        deadline = time.monotonic() + timeout
        buf = bytearray()
        while time.monotonic() < deadline:
            chunk = self.ser.read(256)
            if chunk:
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    line = line.rstrip(b"\r").decode(errors="replace")
                    if line:
                        self.log(f"{self.ts()} <- {line}")
                        return line
        raise Fail(f"timeout waiting for line (got partial: {bytes(buf)!r})")

    def expect(self, prefix: str, timeout: float = 3.0, consume_note=True) -> str:
        """Read lines until one starts with prefix; interleaved lines
        (e.g. 'NOTE IWDG STARTED') are logged and skipped."""
        deadline = time.monotonic() + timeout
        skipped = 0
        while True:
            remain = deadline - time.monotonic()
            if remain <= 0:
                raise Fail(f"timeout waiting for prefix {prefix!r}")
            line = self.readline(timeout=remain)
            if line.startswith(prefix):
                return line
            skipped += 1
            if not consume_note or skipped > 10:
                raise Fail(f"unexpected line {line!r} (wanted {prefix!r})")

    def drain_silent(self, seconds: float) -> list:
        """Collect any lines for a while (TX DONE wait); no expectations."""
        out = []
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                out.append(self.readline(timeout=0.2))
            except Fail:
                pass
        return out


def buf_load(con: Console, payload: bytes) -> str:
    """One full load cycle. NO retry, NO input flush after the preamble."""
    n = len(payload)
    crc = crc16_ccitt_false(payload)
    # CRLF is safe: console_binary_start() drains RXNE and swallows the
    # '\n' before entering the binary phase.  The NVIC guard prevents ISR
    # /polling duplicate-byte races that corrupted the ring on bare-CR.
    con.write_raw(f"BUF LOAD {n} {crc:04X}\r\n".encode())
    ack = con.expect("OK BINARY ", timeout=3.0)
    if ack != f"OK BINARY {n}":
        raise Fail(f"bad ack {ack!r}")
    con.write_raw(payload)  # blocking; UART paces at line rate
    verdict = con.expect("OK BUF ", timeout=10.0)
    # Verdict format: 'OK BUF <n> 1'. Anything else (ERR CRC / ERR TIMEOUT
    # / gate rejection) fails loudly here — no retry.
    if verdict != f"OK BUF {n} 1":
        raise Fail(f"load verdict: {verdict!r}")
    return verdict


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/ttyUSB4")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--loads", type=int, default=10)
    ap.add_argument("--size", type=int, default=4096)
    args = ap.parse_args()

    for data, want in GOLDEN:
        got = crc16_ccitt_false(data)
        if got != want:
            print(f"CRC self-test FAIL: {data[:9]!r}... {got:#06x} != {want:#06x}")
            return 2
    print("CRC self-test: 3/3 golden vectors OK")

    con = Console(args.port, args.baud)
    results = {"loads_ok": 0, "drops": None, "src_buf": False, "src_prbs": False}

    # --- Sync + deterministic pre-state -----------------------------------
    ident = con.cmd("ID?")
    if not ident.startswith("ID E80BENCH"):
        print(f"FAIL: no bench banner on ID?: {ident!r}")
        return 1
    print(f"board: {ident}")
    # Skip ROLE NONE if already NONE — ID? does a radio wake/sleep cycle,
    # and calling radio_sleep_now() again on an already-asleep radio can
    # hang the SPI bus (firmware bug, not under test here).
    if "role=NONE" not in ident:
        line = con.cmd("ROLE NONE")
        if not line.startswith("OK ROLE NONE"):
            print(f"FAIL: ROLE NONE -> {line!r}")
            return 1
    else:
        print("pre-state: role already NONE (skipping redundant ROLE NONE)")

    # --- G1: 10/10 full-capacity random loads ------------------------------
    st = ""
    for i in range(1, args.loads + 1):
        payload = os.urandom(args.size)
        try:
            buf_load(con, payload)
            st = con.cmd("BUF STATUS")
            # 'BUF len=<n> crc=<HEX4> drops=<d>'
            want_crc = f"crc={crc16_ccitt_false(payload):04X}"
            if f"len={args.size}" not in st or want_crc not in st:
                raise Fail(f"status mismatch after load {i}: {st!r}")
            results["loads_ok"] += 1
            print(f"G1 load {i:2d}/{args.loads}: OK BUF {args.size} 1  [{st}]")
        except Fail as e:
            print(f"G1 load {i:2d}/{args.loads}: FAIL: {e}")
            # Line mode is guaranteed again after any verdict/ERR; if the
            # failure was mid-phase, resync with ID? (never a retry of the
            # load itself — the failed attempt is recorded, not repeated).
            try:
                con.cmd("ID?")
            except Fail:
                print("console desynced after failure; aborting remaining loads")
                break
    if "drops=" in st:
        results["drops"] = int(st.split("drops=")[1].split()[0])

    # --- G2: src=BUF smoke ---------------------------------------------------
    try:
        line = con.cmd("ROLE TX")
        if not line.startswith("OK ROLE TX"):
            raise Fail(f"ROLE TX -> {line!r}")
        # First ARM TX also emits 'NOTE IWDG STARTED ...' (expect skips it).
        con.write_raw(b"ARM TX\r\n")
        con.expect("OK ARMED", timeout=3.0)
        # IWDG rule: START leaves immediately (<1 s after ARM ack).
        con.write_raw(b"START N=10 LEN=255 GAP=5000\r\n")
        start_reply = con.expect("OK START ", timeout=3.0)
        results["src_buf"] = "src=BUF" in start_reply
        print(f"G2 START reply: {start_reply}  -> src=BUF={results['src_buf']}")
        tail = con.drain_silent(30.0)
        print(f"G2 post-burst lines: {tail}")
    except Fail as e:
        print(f"G2 FAIL: {e}")

    # --- G3: src=PRBS smoke --------------------------------------------------
    try:
        line = con.cmd("BUF CLEAR")  # allowed while armed (no gate on CLEAR)
        if line != "OK BUF 0":
            raise Fail(f"BUF CLEAR -> {line!r}")
        st = con.cmd("BUF STATUS")
        if not st.startswith("BUF len=0 "):
            raise Fail(f"status after clear: {st!r}")
        # Still armed (TX DONE does not disarm) — START directly.
        con.write_raw(b"START N=10 LEN=255 GAP=5000\r\n")
        start_reply = con.expect("OK START ", timeout=3.0)
        results["src_prbs"] = "src=PRBS" in start_reply
        print(f"G3 START reply: {start_reply}  -> src=PRBS={results['src_prbs']}")
        tail = con.drain_silent(30.0)
        print(f"G3 post-burst lines: {tail}")
    except Fail as e:
        print(f"G3 FAIL: {e}")

    # --- Summary --------------------------------------------------------------
    g1 = results["loads_ok"] == args.loads
    g2 = results["src_buf"]
    g3 = results["src_prbs"]
    print(f"\nG1 loads {results['loads_ok']}/{args.loads} CRC-OK"
          f"  (final drops={results['drops']}) : {'PASS' if g1 else 'FAIL'}")
    print(f"G2 src=BUF  : {'PASS' if g2 else 'FAIL'}")
    print(f"G3 src=PRBS : {'PASS' if g3 else 'FAIL'}")
    ok = g1 and g2 and g3
    print(f"SMOKE RESULT: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
