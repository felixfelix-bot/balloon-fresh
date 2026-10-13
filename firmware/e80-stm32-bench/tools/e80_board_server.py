#!/usr/bin/env python3
"""e80_board_server.py — TCP board server daemon for distributed E80 range tests.

Runs on each machine that has an E80 board plugged in. Owns the local
serial port, auto-detects role + port on startup, and exposes a simple
JSON-line protocol over TCP. This lets the range-test client control
both boards from a single machine.

Protocol (newline-delimited JSON, one request per line):

  Server → Client (on connect):
    {"type":"hello","role":"TX","probe_serial":"148...","port":"/dev/ttyUSB3",
     "id":"ID E80BENCH ...","fw":"0561b29","openocd":"/usr/bin/openocd"}

  Client → Server:
    {"cmd":"query","line":"ID?","prefixes":["OK","ERR","STAT","ID"],"timeout":15}
    {"cmd":"cmd","line":"ROLE TX","timeout":15}
    {"cmd":"stat"}
    {"cmd":"drain","seconds":5.0}
    {"cmd":"swd_reset"}
    {"cmd":"ping"}
    {"cmd":"close"}

  Server → Client:
    {"ok":true,"reply":"OK ROLE TX"}               # for query/cmd/stat
    {"ok":true,"lines":["PKT,...", ...]}            # for drain
    {"ok":true}                                      # for swd_reset/ping
    {"ok":false,"error":"reason"}                    # on failure

The server has a background drain thread that continuously reads serial
output into a buffer, preventing kernel TTY buffer overflow during long
bursts (10,000+ packets). When a command is being processed (holding the
serial lock), the drain thread waits.

Usage:
    python3 e80_board_server.py                           # auto-detect + serve
    python3 e80_board_server.py --role TX                # assert TX
    python3 e80_board_server.py --port /dev/ttyUSB3       # skip detection
    python3 e80_board_server.py --port 7780              # TCP port (default 7780)
    python3 e80_board_server.py --daemon                 # detach to background
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import socketserver
import subprocess
import sys
import threading
import time

# Add sibling directory for imports
_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

from e80_detect import (
    BAUD,
    PROBE_TX,
    PROBE_RX,
    check_deps,
    detect_board,
    find_openocd,
)


# -----------------------------------------------------------------------
# Board controller with background drain
# -----------------------------------------------------------------------

class BoardController:
    """Owns a serial port with a background drain thread.

    The drain thread continuously reads serial output into an in-memory
    buffer. When a command is sent (cmd/query/stat), the serial lock is
    held so the drain thread pauses — the command handler reads directly.
    Non-reply lines encountered during a command are also buffered.

    This prevents kernel TTY buffer (4 KB) overflow during long radio
    bursts where the firmware emits many PKT lines.
    """

    def __init__(self, port: str, baud: int = BAUD, probe_serial: str | None = None):
        import serial as pyserial

        self.port = port
        self.baud = baud
        self.probe_serial = probe_serial
        self.role: str = "?"  # set by caller after detection
        self.ser = pyserial.Serial(
            port=port, baudrate=baud, parity="N", stopbits=1,
            bytesize=8, timeout=0.1,
        )
        self._buffer: list[str] = []
        self._buffer_lock = threading.Lock()
        self._serial_lock = threading.Lock()
        self._running = True
        self._drain_thread = threading.Thread(target=self._drain_loop, daemon=True)
        self._drain_thread.start()

    def _drain_loop(self):
        while self._running:
            if self._serial_lock.acquire(timeout=0.05):
                try:
                    self.ser.timeout = 0.05
                    data = self.ser.read(4096)
                    if data:
                        text = data.decode(errors="replace")
                        for line in text.split("\n"):
                            line = line.rstrip("\r").strip()
                            if line:
                                with self._buffer_lock:
                                    self._buffer.append(line)
                finally:
                    self._serial_lock.release()
            time.sleep(0.01)

    def _get_buffered(self) -> list[str]:
        with self._buffer_lock:
            lines = self._buffer[:]
            self._buffer.clear()
            return lines

    # --- Command interface (mirrors BoardSerial) ---

    def query(self, line: str, prefixes=("OK", "ERR", "STAT", "ID"), timeout=15.0) -> str:
        with self._serial_lock:
            self.ser.timeout = timeout
            self.ser.reset_input_buffer()
            self.ser.write((line + "\r\n").encode())
            deadline = time.time() + timeout
            while time.time() < deadline:
                raw = self.ser.readline()
                reply = raw.decode(errors="replace").strip()
                if not reply:
                    continue
                # Buffer non-reply lines for later retrieval
                matched = False
                for p in prefixes:
                    if reply.startswith(p):
                        matched = True
                        break
                if not matched:
                    with self._buffer_lock:
                        self._buffer.append(reply)
                    continue
                if reply.startswith("ERR"):
                    raise RuntimeError(f"{self.port} rejected '{line}': {reply}")
                return reply
            raise TimeoutError(f"{self.port}: timeout waiting for reply to '{line}'")

    def cmd(self, line: str, timeout=15.0) -> str:
        return self.query(line, prefixes=("OK", "ERR"), timeout=timeout)

    def stat(self) -> str:
        return self.query("STAT?", prefixes=("STAT", "ERR", "OK"))

    def id_query(self) -> str | None:
        try:
            return self.query("ID?", prefixes=("ID", "ERR"), timeout=5.0)
        except (TimeoutError, RuntimeError):
            return None

    def drain(self, seconds: float = 1.0) -> list[str]:
        time.sleep(seconds)
        return self._get_buffered()

    def swd_reset(self) -> bool:
        if not self.probe_serial:
            raise RuntimeError("no SWD probe serial — cannot reset")
        openocd = find_openocd()
        if not openocd:
            raise RuntimeError(
                "openocd not installed. Install: sudo apt install openocd"
            )
        fw_dir = os.path.dirname(os.path.dirname(_TOOLS_DIR))
        subprocess.run(
            [openocd, "-f", "interface/cmsis-dap.cfg",
             "-f", "target/stm32f1x.cfg",
             "-c", f"transport select swd; adapter serial {self.probe_serial}; "
                   f"init; reset halt; resume; exit"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=30, cwd=fw_dir,
        )
        time.sleep(2.0)
        return True

    def ensure_alive(self) -> bool:
        for _ in range(2):
            r = self.id_query()
            if r and "E80BENCH" in r:
                return True
            if self.probe_serial:
                try:
                    self.swd_reset()
                except RuntimeError:
                    pass
                time.sleep(1.0)
        return False

    def close(self):
        self._running = False
        self._drain_thread.join(timeout=2.0)
        try:
            self.ser.close()
        except Exception:
            pass


# -----------------------------------------------------------------------
# TCP request handler
# -----------------------------------------------------------------------

class BoardTCPServer:
    """Simple threaded TCP server wrapping a BoardController."""

    def __init__(self, controller: BoardController, host="0.0.0.0", port=7780):
        self.ctrl = controller
        self.host = host
        self.port = port
        self._sock: socket.socket | None = None
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        sock.listen(4)
        sock.settimeout(1.0)
        self._sock = sock
        self._running = True
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()

    def _accept_loop(self):
        while self._running:
            try:
                conn, addr = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            t = threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True)
            t.start()

    def _handle_client(self, conn: socket.SocketType, addr):
        try:
            # Send hello
            hello = self._build_hello()
            conn.sendall((json.dumps(hello) + "\n").encode())
            buf = ""
            while self._running:
                try:
                    data = conn.recv(4096).decode(errors="replace")
                except (ConnectionError, OSError):
                    break
                if not data:
                    break
                buf += data
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        req = json.loads(line)
                        resp = self._process(req)
                    except json.JSONDecodeError as e:
                        resp = {"ok": False, "error": f"bad JSON: {e}"}
                    except Exception as e:
                        resp = {"ok": False, "error": str(e)}
                    try:
                        conn.sendall((json.dumps(resp) + "\n").encode())
                    except (ConnectionError, OSError):
                        break
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _build_hello(self) -> dict:
        id_reply = self.ctrl.id_query()
        fw = None
        if id_reply:
            for tok in id_reply.split():
                if tok.startswith("fw="):
                    fw = tok.split("=", 1)[1]
        return {
            "type": "hello",
            "role": getattr(self.ctrl, "role", "?"),
            "probe_serial": self.ctrl.probe_serial,
            "port": self.ctrl.port,
            "id": id_reply,
            "fw": fw,
            "openocd": find_openocd(),
        }

    def _process(self, req: dict) -> dict:
        cmd = req.get("cmd", "")
        if cmd == "ping":
            return {"ok": True}
        if cmd == "info":
            return self._build_hello()
        if cmd == "query":
            reply = self.ctrl.query(
                req["line"],
                prefixes=tuple(req.get("prefixes", ("OK", "ERR", "STAT", "ID"))),
                timeout=req.get("timeout", 15.0),
            )
            return {"ok": True, "reply": reply}
        if cmd == "cmd":
            reply = self.ctrl.cmd(req["line"], timeout=req.get("timeout", 15.0))
            return {"ok": True, "reply": reply}
        if cmd == "stat":
            reply = self.ctrl.stat()
            return {"ok": True, "reply": reply}
        if cmd == "drain":
            lines = self.ctrl.drain(req.get("seconds", 1.0))
            return {"ok": True, "lines": lines}
        if cmd == "swd_reset":
            self.ctrl.swd_reset()
            return {"ok": True}
        if cmd == "ensure_alive":
            alive = self.ctrl.ensure_alive()
            return {"ok": True, "alive": alive}
        if cmd == "close":
            return {"ok": True}
        return {"ok": False, "error": f"unknown command: {cmd}"}

    def stop(self):
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass


# -----------------------------------------------------------------------
# Server startup
# -----------------------------------------------------------------------

def run_server(port_spec: str, tcp_port: int = 7780, role: str | None = None,
               daemon: bool = False) -> int:
    """Start the board server.

    Args:
        port_spec: "/dev/ttyUSB3" or "auto" for auto-detection
        tcp_port: TCP listen port
        role: assert TX or RX (for auto-detect verification)
        daemon: if True, fork to background
    """
    if daemon:
        _daemonize()

    # Dependency check
    deps = check_deps()
    if not deps["pyserial"]:
        print("ERROR: pyserial not installed. Run: pip install pyserial", file=sys.stderr)
        return 2
    if not deps["openocd"]:
        print("WARNING: openocd not installed (SWD reset unavailable for board recovery).",
              file=sys.stderr)
        print("  Install: sudo apt install openocd", file=sys.stderr)

    # Auto-detect or use explicit port
    if port_spec == "auto":
        result = detect_board(target_role=role)
        if "error" in result:
            print(f"ERROR: {result['error']}", file=sys.stderr)
            return 1
        serial_port = result["port"]
        probe_serial = result["probe_serial"]
        detected_role = result["role"]
        fw_hash = result.get("fw_hash")
        id_reply = result.get("id_reply")
    else:
        serial_port = port_spec
        from e80_detect import query_id, parse_id_reply
        id_reply = query_id(serial_port)
        id_parsed = parse_id_reply(id_reply) if id_reply else {}
        detected_role = id_parsed.get("role", "?")
        fw_hash = id_parsed.get("fw")
        probe_serial = None

        # Try to find probe serial for this port
        from e80_detect import find_swd_probes
        probes = find_swd_probes()
        if len(probes) == 1:
            probe_serial = next(iter(probes.keys()))
            detected_role = probes[probe_serial]["role"]

    if role and detected_role and detected_role.upper() != role.upper():
        print(f"ERROR: expected role={role} but detected role={detected_role}",
              file=sys.stderr)
        return 1

    # Open the board
    print(f"[server] Role={detected_role}  Port={serial_port}  "
          f"Probe={probe_serial or 'N/A'}  FW={fw_hash or '?'}", flush=True)
    if id_reply:
        print(f"[server] ID: {id_reply}", flush=True)

    try:
        ctrl = BoardController(serial_port, probe_serial=probe_serial)
        ctrl.role = detected_role or role or "?"
    except Exception as e:
        print(f"ERROR: cannot open {serial_port}: {e}", file=sys.stderr)
        return 1

    server = BoardTCPServer(ctrl, host="0.0.0.0", port=tcp_port)
    server.start()
    print(f"[server] Listening on 0.0.0.0:{tcp_port} (role={ctrl.role})",
          file=sys.stderr, flush=True)

    # Stay alive until killed
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n[server] Shutting down...", file=sys.stderr)
    finally:
        server.stop()
        ctrl.close()
    return 0


def _daemonize():
    """Fork to background (simple double-fork)."""
    import sys
    pid = os.fork()
    if pid > 0:
        os._exit(0)
    os.setsid()
    pid = os.fork()
    if pid > 0:
        os._exit(0)
    sys.stdout.flush()
    sys.stderr.flush()


def main():
    ap = argparse.ArgumentParser(description="E80 board server daemon")
    ap.add_argument("--port", default="auto",
                    help="serial port ('auto' for auto-detection, or /dev/ttyUSB3)")
    ap.add_argument("--tcp-port", type=int, default=7780,
                    help="TCP listen port (default 7780)")
    ap.add_argument("--role", choices=["TX", "RX"], default=None,
                    help="assert the local board is this role")
    ap.add_argument("--daemon", action="store_true",
                    help="run as background daemon")
    args = ap.parse_args()
    sys.exit(run_server(args.port, args.tcp_port, args.role, args.daemon))


if __name__ == "__main__":
    main()
