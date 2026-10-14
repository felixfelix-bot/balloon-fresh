#!/usr/bin/env python3
"""E80 bench serial agent — runs on the host that owns the board's console.

Driven by the RFA-1b matrix runner (tools/rfa1b_pram_matrix.py), which may live
on a different host: every board interaction goes through this script so the
local and ssh paths are byte-identical.

Usage:
    python3 e80_serial_agent.py --port /dev/ttyUSB1 --ops-b64 <b64> --out out.json
                                [--mark-file /tmp/rx_listening]

Ops (JSON list):
    {"op": "send",   "cmd": "MOD flrc 260 10", "expect": "OK MOD",
     "retries": 3, "timeout_s": 3.0}
    {"op": "listen", "seconds": 30, "mark": "LISTENING"}
    {"op": "sleep",  "seconds": 1.0}
    {"op": "flush"}

Output JSON: {"port":..., "ops":[{op, ok, reply, error}], "lines":[...],
"raw":"...", "id": "<last ID? reply>"}

Every command is validated (expected substring, retries on ERR/empty) — the
2026-08-20 lesson: unvalidated commands turn silent failures into fake RF
results.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time

import serial

DEFAULT_BAUD = 115200
LINE_END = b"\n"


class Agent:
    def __init__(self, port: str, baud: int, mark_file: str | None):
        self.port = port
        self.baud = baud
        self.mark_file = mark_file
        self.buf = b""
        self.lines: list[str] = []
        self.ser = serial.Serial(port, baud, timeout=0.1, write_timeout=3.0)

    # -- low level ---------------------------------------------------------
    def _pump(self, deadline: float) -> None:
        while time.time() < deadline:
            chunk = self.ser.read(4096)
            if chunk:
                self.buf += chunk
                while b"\n" in self.buf:
                    line, self.buf = self.buf.split(b"\n", 1)
                    line = line.strip(b"\r").decode(errors="replace")
                    if line:
                        self.lines.append(line)
            else:
                time.sleep(0.005)

    def send(self, cmd: str, expect: str | None, retries: int, timeout_s: float) -> dict:
        last = ""
        for attempt in range(1, retries + 1):
            self.ser.reset_input_buffer()
            self.buf = b""
            self.ser.write(cmd.encode() + LINE_END)
            self.ser.flush()
            deadline = time.time() + timeout_s
            got = ""
            while time.time() < deadline:
                start = len(self.lines)
                self._pump(time.time() + 0.05)
                new = "\n".join(self.lines[start:])
                if new:
                    got = new
                if expect and expect in "\n".join(self.lines):
                    break
            joined = "\n".join(self.lines)
            ok = (expect is None) or (expect in joined)
            if ok:
                return {"op": "send", "cmd": cmd, "ok": True, "attempt": attempt}
            last = joined or got
            time.sleep(0.3)
        return {"op": "send", "cmd": cmd, "ok": False, "error": f"expect {expect!r} not seen",
                "reply": last, "attempts": retries}

    def wait_for(self, expect: str, seconds: float) -> dict:
        """Listen without sending anything until <expect> shows up."""
        deadline = time.time() + seconds
        while time.time() < deadline:
            self._pump(min(time.time() + 0.25, deadline))
            if expect in "\n".join(self.lines):
                return {"op": "wait", "expect": expect, "ok": True}
        return {"op": "wait", "expect": expect, "ok": False, "error": "not seen before timeout"}

    def listen(self, seconds: float, mark: str | None) -> dict:
        if self.mark_file:
            with open(self.mark_file, "w") as fh:
                fh.write(mark or "LISTENING")
        n0 = len(self.lines)
        self._pump(time.time() + seconds)
        return {"op": "listen", "ok": True, "seconds": seconds, "new_lines": len(self.lines) - n0}

    def run(self, ops: list[dict]) -> dict:
        results = []
        for op in ops:
            kind = op.get("op")
            if kind == "send":
                results.append(self.send(op["cmd"], op.get("expect"),
                                         int(op.get("retries", 3)),
                                         float(op.get("timeout_s", 3.0))))
            elif kind == "listen":
                results.append(self.listen(float(op.get("seconds", 10.0)), op.get("mark")))
            elif kind == "wait":
                results.append(self.wait_for(op["expect"], float(op.get("timeout_s", 30.0))))
            elif kind == "sleep":
                time.sleep(float(op.get("seconds", 1.0)))
                results.append({"op": "sleep", "ok": True, "seconds": op.get("seconds", 1.0)})
            elif kind == "flush":
                self.buf = b""
                results.append({"op": "flush", "ok": True})
            else:
                results.append({"op": kind, "ok": False, "error": "unknown op"})
        id_line = ""
        for line in reversed(self.lines):
            if line.startswith("ID E80BENCH"):
                id_line = line
                break
        return {"port": self.port, "baud": self.baud, "ops": results,
                "lines": self.lines, "id": id_line, "ok": all(r.get("ok") for r in results)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True)
    ap.add_argument("--baud", type=int, default=DEFAULT_BAUD)
    ap.add_argument("--ops-b64", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--mark-file", default=None)
    args = ap.parse_args()

    ops = json.loads(base64.b64decode(args.ops_b64).decode())
    agent = Agent(args.port, args.baud, args.mark_file)
    try:
        out = agent.run(ops)
    except Exception as exc:  # noqa: BLE001 - reported to the runner verbatim
        out = {"port": args.port, "ops": [], "lines": agent.lines, "ok": False,
               "error": f"{type(exc).__name__}: {exc}"}
    finally:
        agent.ser.close()

    tmp = args.out + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(out, fh)
    os.replace(tmp, args.out)
    print(json.dumps({"ok": out.get("ok"), "error": out.get("error"),
                      "n_lines": len(out.get("lines", []))}))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
