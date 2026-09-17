#!/usr/bin/env python3
"""e28_board_server.py — ContextVM (Nostr MCP) board server for the E28 ranging bridge.

Wraps the E28 ranging serial console (firmware/esp32-e28-range, LILYGO T3S3
ESP32-S3 + SX1282) as a set of JSON-RPC tools exposed over Nostr relays using
gift-wrapped kind 1059 events (NIP-44/NIP-59), mirroring cvm_board_server.py.

The E28 console protocol (see e28_range_console.c):

    ID?          -> E28-RANGE v1.0 fw=<hash>
    STAT?        -> role=<master|slave|idle> freq=<MHz> sf=<n> bw=<kHz>
                    pa=<dBm> addr=<0x…> last=<m|none> err=<code>
    RANGE        -> master: DIST=<m>m | RANGE TIMEOUT
    RANGE-SLAVE  -> slave: SLAVE OK
    RANGE?       -> DIST=<m>m (or DIST=none)
    FREQ <hz> / SF <n> / BW <khz> / PA <dbm> / ADDR <hex> / HELP

Tools (JSON-RPC tools/call with name+arguments):

    e28_range        {freq?, sf?, bw?, pa?}  -> {ok, status}   (TX master)
    e28_range_slave  {freq?, sf?, bw?, pa?}  -> {ok, status}   (RX responder)
    e28_query        {}                      -> {ok, distance_m, rssi?, status}
    e28_config       {freq?, sf?, bw?, pa?}  -> {ok, status}   (best-effort)

Role enforcement: e28_range requires role=TX (initiates master ranging);
e28_range_slave requires role=RX (responds). e28_query and e28_config are
role-agnostic.

Transport: reuses CVMBoardServer from cvm_board_server.py (~75% of the
gift-wrap kind 1059 / _NotificationHandler / dispatch_rpc machinery). The
E28 serial wrapper is a BoardController-style drain-thread wrapper with a
different line protocol (reuse the pattern, not the class).

Usage:
    # TX machine:
    CVM_SERVER_HEX=<hex_secret> python3 e28_board_server.py --role tx

    # RX machine:
    CVM_SERVER_HEX=<hex_secret> python3 e28_board_server.py --role rx

    python3 e28_board_server.py --role tx --port /dev/ttyUSB4 \
        --relays wss://relay.primal.net,wss://nostr.mom \
        --server-hex <hex> --allowed-client-npubs npub1xxx,npub1yyy
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import signal
import sys
import threading
import time
from typing import Optional

# Sibling imports
_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

# Reuse the CVM transport machinery from cvm_board_server.py (~75% reuse):
# gift-wrap kind 1059, _NotificationHandler, dispatch_rpc, JSON_RPC_ERROR,
# DEFAULT_RELAYS, _load_keys, run_server's serve-loop scaffolding.
from cvm_board_server import (  # noqa: E402
    CVMBoardServer,
    DEFAULT_RELAYS,
    JSON_RPC_ERROR,
    KIND_CVM_RPC,
    KIND_GIFT_WRAP,
    _NotificationHandler,
    _extract_p_tag,
    _load_keys,
)

# E28 serial console defaults.
E28_BAUD = 115200
# Indoor TX power cap (matches E28_RANGE_TXPOW_CAP_INDOOR_DBM in firmware).
E28_TXPOW_CAP_INDOOR_DBM = 10
# Ranging-valid bandwidth (812.5 kHz only per firmware).
E28_BW_DEFAULT_KHZ = 812.5
# Known-good manual config fallback (sx1280-correlation-test lesson: vendor
# config protocol historically unreliable — default to manual known-good).
E28_KNOWN_GOOD = {
    "freq": 2440000000,
    "sf": 7,
    "bw": E28_BW_DEFAULT_KHZ,
    "pa": E28_TXPOW_CAP_INDOOR_DBM,
}


# ===========================================================================
# E28 serial controller — BoardController-style drain-thread wrapper
# ===========================================================================

class E28Controller:
    """Owns the E28 serial port with a background drain thread.

    Mirrors e80_board_server.BoardController's pattern (drain thread + serial
    lock) but with the E28 line protocol: FREQ/SF/BW/PA emit no success reply
    (fire-and-forget via send()), while RANGE/RANGE-SLAVE/RANGE?/ID?/STAT?
    return a reply line.
    """

    def __init__(self, port: str, baud: int = E28_BAUD):
        import serial as pyserial

        self.port = port
        self.baud = baud
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

    # --- Command interface ---

    def query(self, line: str, prefixes=("OK", "ERR", "STAT", "ID", "DIST", "SLAVE"),
              timeout=15.0) -> str:
        """Send a line and wait for a reply matching one of `prefixes`."""
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

    def send(self, line: str) -> None:
        """Fire-and-forget write (FREQ/SF/BW/PA emit no success reply)."""
        with self._serial_lock:
            self.ser.reset_input_buffer()
            self.ser.write((line + "\r\n").encode())

    def id_query(self) -> Optional[str]:
        try:
            return self.query("ID?", prefixes=("E28", "ID", "ERR"), timeout=5.0)
        except (TimeoutError, RuntimeError):
            return None

    def ensure_alive(self) -> bool:
        for _ in range(2):
            r = self.id_query()
            if r and "E28-RANGE" in r:
                return True
            time.sleep(1.0)
        return False

    def close(self):
        self._running = False
        self._drain_thread.join(timeout=2.0)
        try:
            self.ser.close()
        except Exception:
            pass


# ===========================================================================
# E28 tools — pure-Python wrapper around E28Controller, no Nostr
# ===========================================================================

class E28Tools:
    """Exposes E28Controller methods as discoverable CVM tools.

    Each method returns a dict that the CVM server JSON-encodes into the
    JSON-RPC result.content[0].text field. Hardware exceptions (TimeoutError,
    RuntimeError) propagate; the CVM layer catches and wraps them.
    """

    def __init__(self, ctrl: E28Controller, role: str):
        self.ctrl = ctrl
        self.role = role.upper()

    # --- tool dispatch ---

    def dispatch_tool(self, name: str, args: dict) -> dict:
        """Dispatch a tool call to the controller. Returns a result dict.

        Hardware/argument errors (TimeoutError, RuntimeError, ValueError) are
        caught and returned as ``{"ok": False, "error": str(e)}`` dicts. The
        only exception that propagates is ``ValueError`` for an unknown tool
        name, which ``dispatch_rpc`` maps to ``METHOD_NOT_FOUND``.
        """
        fn = getattr(self, f"tool_{name}", None)
        if fn is None:
            raise ValueError(f"unknown tool: {name} (role={self.role})")
        try:
            return fn(args)
        except (TimeoutError, RuntimeError, ValueError) as e:
            return {"ok": False, "error": str(e)}

    # --- helpers ---

    @staticmethod
    def _clamp_pa(pa) -> int:
        """Clamp TX power to the EU indoor cap (+10 dBm)."""
        pa = int(pa)
        if pa > E28_TXPOW_CAP_INDOOR_DBM:
            pa = E28_TXPOW_CAP_INDOOR_DBM
        return pa

    def _apply_config(self, args: dict) -> list[str]:
        """Best-effort: send FREQ/SF/BW/PA commands (fire-and-forget).

        Falls back to known-good manual config when args are absent. Returns
        the list of commands sent.
        """
        cfg = dict(E28_KNOWN_GOOD)
        for k in ("freq", "sf", "bw", "pa"):
            if k in args and args[k] is not None:
                cfg[k] = args[k]
        commands = []
        if "freq" in cfg:
            commands.append(f"FREQ {int(cfg['freq'])}")
        if "sf" in cfg:
            commands.append(f"SF {int(cfg['sf'])}")
        if "bw" in cfg:
            commands.append(f"BW {float(cfg['bw'])}")
        if "pa" in cfg:
            commands.append(f"PA {self._clamp_pa(cfg['pa'])}")
        for c in commands:
            self.ctrl.send(c)
        return commands

    # --- tool implementations ---

    def tool_e28_range(self, args: dict) -> dict:
        """TX master: initiate one ranging exchange."""
        if self.role != "TX":
            raise RuntimeError(
                f"e28_range: requires role=TX (master), got role={self.role}")
        self._apply_config(args)
        reply = self.ctrl.query("RANGE", prefixes=("DIST", "RANGE", "ERR"),
                                timeout=15.0)
        return {"ok": True, "status": reply}

    def tool_e28_range_slave(self, args: dict) -> dict:
        """RX responder: respond to master's ranging requests."""
        if self.role != "RX":
            raise RuntimeError(
                f"e28_range_slave: requires role=RX (responder), got role={self.role}")
        self._apply_config(args)
        reply = self.ctrl.query("RANGE-SLAVE", prefixes=("SLAVE", "ERR"),
                                timeout=15.0)
        return {"ok": True, "status": reply}

    def tool_e28_query(self, args: dict) -> dict:
        """Query the last measured distance (RANGE?)."""
        reply = self.ctrl.query("RANGE?", prefixes=("DIST", "ERR"), timeout=5.0)
        m = re.match(r"DIST=([0-9.]+)m", reply)
        distance_m = float(m.group(1)) if m else None
        return {"ok": True, "distance_m": distance_m, "status": reply}

    def tool_e28_config(self, args: dict) -> dict:
        """Best-effort configure the E28 radio (FREQ/SF/BW/PA)."""
        commands = self._apply_config(args)
        return {"ok": True, "status": "OK", "commands": commands}


# ===========================================================================
# E28 CVM board server — reuses CVMBoardServer transport
# ===========================================================================

class E28BoardServer(CVMBoardServer):
    """Nostr-backed CVM board server serving E28Tools over gift-wrapped
    JSON-RPC. Inherits the full transport (serve loop, _NotificationHandler,
    dispatch_rpc, gift-wrap reply) from CVMBoardServer.
    """

    def __init__(self, tools: E28Tools, server_keys, relays: list[str],
                 role: str, allowed_client_pubkeys: Optional[list[str]] = None,
                 log=print):
        super().__init__(tools, server_keys=server_keys, relays=relays,
                         role=role, allowed_client_pubkeys=allowed_client_pubkeys,
                         log=log)


# ===========================================================================
# Server entrypoint
# ===========================================================================

def run_server(role: str, port_spec: str = "auto",
               server_keys=None, relays: Optional[list[str]] = None,
               allowed_clients: Optional[list[str]] = None,
               log=print) -> int:
    """Open the E28 serial port, build the CVM server, serve forever."""
    if relays is None:
        relays = list(DEFAULT_RELAYS)
    if server_keys is None:
        raise SystemExit("server_keys required to serve")

    # --- Open the E28 serial port ---
    if port_spec == "auto":
        # Auto-detect: prefer the first /dev/ttyUSB* or /dev/ttyACM* that
        # answers ID? with E28-RANGE.
        serial_port = _detect_e28_port()
        if serial_port is None:
            print("ERROR: no E28 serial port found (try --port /dev/ttyUSB4)",
                  file=sys.stderr)
            return 1
    else:
        serial_port = port_spec

    try:
        ctrl = E28Controller(serial_port)
    except Exception as e:
        print(f"ERROR: cannot open {serial_port}: {e}", file=sys.stderr)
        return 1

    # Detect role from ID? reply if possible (E28 console doesn't carry role
    # in ID?, so fall back to the --role flag).
    id_reply = ctrl.id_query()
    if id_reply:
        print(f"[e28-server] ID: {id_reply}", flush=True)
    ctrl.role = role.upper()

    print(f"[e28-server] Role={ctrl.role} Port={serial_port}", flush=True)

    # --- Build + serve ---
    tools = E28Tools(ctrl, role=ctrl.role)
    server = E28BoardServer(tools, server_keys=server_keys, relays=relays,
                            role=ctrl.role, allowed_client_pubkeys=allowed_clients,
                            log=log)

    # Signal handling: SIGINT/SIGTERM → graceful shutdown
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    ready = asyncio.Event()

    def _stop_handler(*_):
        log("[e28-server] stop signal received")
        server.stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop_handler)
        except (NotImplementedError, RuntimeError):
            signal.signal(sig, lambda *args: _stop_handler(*args))

    try:
        loop.run_until_complete(server.serve(ready_signal=ready))
    except KeyboardInterrupt:
        pass
    finally:
        ctrl.close()
        log("[e28-server] clean shutdown")
    return 0


def _detect_e28_port() -> Optional[str]:
    """Find a serial port that answers ID? with E28-RANGE."""
    import glob
    candidates = []
    for pat in ("/dev/ttyUSB*", "/dev/ttyACM*"):
        candidates.extend(sorted(glob.glob(pat)))
    for port in candidates:
        try:
            ctrl = E28Controller(port)
            try:
                r = ctrl.id_query()
                if r and "E28-RANGE" in r:
                    return port
            finally:
                ctrl.close()
        except Exception:
            continue
    return None


def main():
    ap = argparse.ArgumentParser(
        description="CVM (ContextVM/Nostr MCP) board server for the E28 ranging bridge")
    ap.add_argument("--role", required=True, choices=["tx", "rx"],
                    help="Board role — TX (master) or RX (responder) server")
    ap.add_argument("--port", default="auto",
                    help="Serial port ('auto' or /dev/ttyUSB4)")
    ap.add_argument("--relays", default=",".join(DEFAULT_RELAYS),
                    help="Comma-separated relay URLs")
    ap.add_argument("--server-hex", default=os.environ.get("CVM_SERVER_HEX"),
                    help="Server Nostr private key (64-char hex)")
    ap.add_argument("--nsec", default=os.environ.get("CVM_SERVER_NSEC"),
                    help="Server Nostr private key (nsec1... bech32)")
    ap.add_argument("--allowed-client-npubs",
                    default=os.environ.get("CVM_ALLOWED_CLIENTS", ""),
                    help="Comma-separated client npub allow-list (default: any)")
    args = ap.parse_args()

    if not args.server_hex and not args.nsec:
        print("ERROR: must pass --server-hex <hex> or --nsec nsec1... "
              "(env: CVM_SERVER_HEX)", file=sys.stderr)
        return 2

    server_keys = _load_keys(args.server_hex, args.nsec)
    print(f"[e28-server] npub={server_keys.public_key().bech32()}", flush=True)

    relays = [r.strip() for r in args.relays.split(",") if r.strip()]
    allowed = [c.strip() for c in args.allowed_client_npubs.split(",")
               if c.strip()] or None
    if allowed:
        import nostr_sdk
        allowed_hex = []
        for c in allowed:
            try:
                if c.startswith("npub1"):
                    allowed_hex.append(nostr_sdk.PublicKey.parse(c).to_hex())
                else:
                    allowed_hex.append(c)
            except Exception as e:
                print(f"WARNING: bad client npub {c}: {e}", file=sys.stderr)
        allowed = allowed_hex

    return run_server(args.role.upper(), port_spec=args.port,
                      server_keys=server_keys, relays=relays,
                      allowed_clients=allowed)


if __name__ == "__main__":
    sys.exit(main())
