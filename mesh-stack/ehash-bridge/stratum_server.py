#!/usr/bin/env python3
"""
stratum_server.py — Ground station Stratum V1 bridge daemon.

Listens on TCP localhost:3333 as a Stratum V1 server that a Bitaxe (NerdMiner)
connects to. Serves the standard stratum protocol:

    mining.subscribe   → returns subscription ID + extranonce1 + extranonce2_size
    mining.authorize   → returns true (auth handled by tollgate, not stratum)
    mining.notify      → pushes job from latest EHASH_TEMPLATE (decoded from radio)
    mining.submit      → receives share, difficulty filter (D7), encodes EHASH_NONCE

Data flow:
    1. EHASH_TEMPLATE binary arrives via stdin/file (simulating LR2021 downlink)
    2. Decoded → reconstructed as Stratum V1 mining.notify JSON
    3. Pushed to all connected miners
    4. mining.submit from Bitaxe → encoded as EHASH_NONCE binary (21 bytes)
    5. Difficulty filter (D7): only shares above threshold pass through
    6. Nonces output to stdout/file (simulating LR2021 uplink)

Tollgate integration:
    Calls GET http://127.0.0.1:3334/v1/balance before serving templates.
    If balance <= 0 or has_access is false, withholds mining.notify.

Usage:
    # Mock mode (generates fake templates internally)
    python3 stratum_server.py --template-input mock

    # Read templates from stdin
    python3 mock_template.py --loop | python3 stratum_server.py --template-input stdin

    # Read templates from file
    python3 stratum_server.py --template-input file:templates.bin

    # With tollgate balance check enabled
    python3 stratum_server.py --tollgate-enabled

No external dependencies — Python stdlib only (socket, json, struct, threading,
hashlib, urllib, argparse).
"""

import argparse
import json
import logging
import os
import socket
import struct
import sys
import threading
import time

# Add parent dir to path so we can import ehash_codec
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ehash_codec import (
    EHASH_NONCE,
    EhashNonce,
    EhashTemplate,
    check_share,
    decode_template,
    encode_nonce_envelope,
    get_envelope_type,
    template_to_notify_params,
)

logger = logging.getLogger("ehash-bridge")


# ========================================================================
#  Framing helpers (2-byte LE length prefix)
# ========================================================================


def write_frame(stream, data: bytes) -> None:
    """Write a length-prefixed binary frame."""
    stream.write(struct.pack("<H", len(data)) + data)
    stream.flush()


def read_exact(stream, n: int) -> bytes:
    """Read exactly n bytes from a binary stream. Returns None on EOF."""
    buf = b""
    while len(buf) < n:
        chunk = stream.read(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


def read_frame(stream) -> bytes:
    """Read a length-prefixed binary frame. Returns None on EOF."""
    hdr = read_exact(stream, 2)
    if hdr is None:
        return None
    (length,) = struct.unpack("<H", hdr)
    if length == 0:
        return b""
    return read_exact(stream, length)


# ========================================================================
#  Template Store (thread-safe current template holder)
# ========================================================================


class TemplateStore:
    """Thread-safe store for the current block template + job tracking."""

    def __init__(self):
        self._lock = threading.Lock()
        self._template: EhashTemplate | None = None
        self._job_counter = 0

    def update(self, tmpl: EhashTemplate) -> None:
        """Set the current template."""
        with self._lock:
            self._template = tmpl

    def get(self) -> EhashTemplate | None:
        """Get the current template, or None if none received yet."""
        with self._lock:
            return self._template


# ========================================================================
#  Tollgate Client
# ========================================================================


class TollgateClient:
    """Client for the tollgate balance/session API (Interface Boundary 2).

    Calls GET /v1/balance to check if templates should be served.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:3334",
        enabled: bool = False,
        permissive: bool = True,
        timeout: float = 3.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.enabled = enabled
        self.permissive = permissive  # If True, allow access when tollgate is down
        self.timeout = timeout

    def check_balance(self) -> tuple[bool, dict | None]:
        """Check if the station has access (balance > 0).

        Returns (has_access, response_data).
        If tollgate is disabled, returns (True, None).
        If tollgate is down and permissive, returns (True, None).
        If tollgate is down and not permissive, returns (False, None).
        """
        if not self.enabled:
            return True, None

        try:
            from urllib.request import urlopen
            from urllib.error import URLError

            url = f"{self.base_url}/v1/balance"
            resp = urlopen(url, timeout=self.timeout)
            data = json.loads(resp.read().decode("utf-8"))

            has_access = data.get("has_access", False)
            balance = data.get("balance_sats", 0)

            if not has_access or balance <= 0:
                logger.warning(
                    "Tollgate: access denied (balance=%d, has_access=%s)",
                    balance,
                    has_access,
                )
                return False, data

            logger.info("Tollgate: access granted (balance=%d)", balance)
            return True, data

        except Exception as e:
            logger.warning("Tollgate check failed: %s", e)
            if self.permissive:
                logger.info("Tollgate permissive mode: allowing access")
                return True, None
            else:
                return False, None


# ========================================================================
#  Nonce Output
# ========================================================================


class NonceOutput:
    """Output EHASH_NONCE binary frames (simulating LR2021 uplink)."""

    def __init__(self, output_mode: str = "stdout"):
        """output_mode: 'stdout', 'none', or 'file:<path>'"""
        self._lock = threading.Lock()
        self._mode = output_mode
        self._file = None

        if output_mode.startswith("file:"):
            path = output_mode[5:]
            self._file = open(path, "wb")
            logger.info("Nonce output → file: %s", path)
        elif output_mode == "stdout":
            logger.info("Nonce output → stdout")
        elif output_mode == "none":
            logger.info("Nonce output → disabled")
        else:
            raise ValueError(f"Unknown nonce output mode: {output_mode}")

    def write(self, nonce: EhashNonce) -> None:
        """Encode and write an EHASH_NONCE envelope."""
        envelope = encode_nonce_envelope(nonce)

        with self._lock:
            if self._mode == "none":
                return
            elif self._mode == "stdout":
                write_frame(sys.stdout.buffer, envelope)
            elif self._file:
                write_frame(self._file, envelope)

    def close(self):
        if self._file:
            self._file.close()


# ========================================================================
#  Miner Connection Handler
# ========================================================================


class MinerConnection:
    """Handles a single Bitaxe stratum V1 TCP connection."""

    def __init__(
        self,
        conn: socket.socket,
        addr,
        server: "StratumServer",
    ):
        self.conn = conn
        self.addr = addr
        self.server = server
        self.subscribed = False
        self.authorized = False
        self.subscription_id = f"ehash-{os.urandom(4).hex()}"
        self.extranonce1 = struct.pack("<I", server.station_id)
        self.extranonce2_size = 4
        self.authorize_id = None
        self._running = True
        self._lock = threading.Lock()

    def send_json(self, obj: dict) -> None:
        """Send a JSON-RPC message followed by newline."""
        data = (json.dumps(obj) + "\n").encode("utf-8")
        try:
            with self._lock:
                self.conn.sendall(data)
        except (BrokenPipeError, ConnectionResetError, OSError):
            self._running = False

    def send_notify(self) -> None:
        """Push a mining.notify with the current template."""
        tmpl = self.server.store.get()
        if tmpl is None:
            return  # No template yet

        params = template_to_notify_params(tmpl)
        self.send_json(
            {"id": None, "method": "mining.notify", "params": params}
        )
        logger.debug("Sent mining.notify job=%s to %s", tmpl.job_id, self.addr)

    def send_difficulty(self, difficulty: float) -> None:
        """Push a mining.set_difficulty message."""
        self.send_json(
            {"id": None, "method": "mining.set_difficulty", "params": [difficulty]}
        )

    def handle_subscribe(self, msg: dict) -> None:
        """Handle mining.subscribe request."""
        req_id = msg.get("id")
        result = [
            [
                ["mining.set_difficulty", self.subscription_id],
                ["mining.notify", self.subscription_id + "-notify"],
            ],
            self.extranonce1.hex(),
            self.extranonce2_size,
        ]
        self.send_json({"id": req_id, "result": result, "error": None})
        self.subscribed = True
        logger.info("Client %s subscribed (sub_id=%s)", self.addr, self.subscription_id)

    def handle_authorize(self, msg: dict) -> None:
        """Handle mining.authorize request."""
        req_id = msg.get("id")
        params = msg.get("params", [])
        username = params[0] if params else "unknown"

        self.send_json({"id": req_id, "result": True, "error": None})
        self.authorized = True
        self.authorize_id = req_id
        logger.info("Client %s authorized as '%s'", self.addr, username)

        # Send difficulty + first notify
        self.send_difficulty(self.server.difficulty)

        # Check tollgate before serving templates
        has_access, _ = self.server.tollgate.check_balance()
        if has_access:
            # Small delay to ensure authorize is processed first
            threading.Timer(0.1, self.send_notify).start()
        else:
            logger.warning("Withholding templates from %s (tollgate gate)", self.addr)
            self.send_json(
                {
                    "id": None,
                    "method": "client.show_message",
                    "params": ["Access denied: insufficient balance"],
                }
            )

    def handle_submit(self, msg: dict) -> None:
        """Handle mining.submit — process a share submission."""
        req_id = msg.get("id")
        params = msg.get("params", [])

        if len(params) < 5:
            self.send_json(
                {
                    "id": req_id,
                    "result": False,
                    "error": [23, "Malformed submission", None],
                }
            )
            return

        worker_name = params[0]
        job_id_str = params[1]
        extranonce2_hex = params[2]
        ntime_hex = params[3]
        nonce_hex = params[4]

        logger.info(
            "Share from %s: job=%s nonce=%s ntime=%s",
            self.addr,
            job_id_str,
            nonce_hex,
            ntime_hex,
        )

        # Build the EHASH_NONCE
        nonce_obj = EhashNonce(
            job_id=int(job_id_str),
            worker_id=self.server.station_id,
            extranonce2=int(extranonce2_hex, 16),
            ntime=int(ntime_hex, 16),
            nonce=int(nonce_hex, 16),
        )

        # Difficulty filter (D7): check share against threshold
        if self.server.share_threshold > 0:
            tmpl = self.server.store.get()
            if tmpl is not None and tmpl.job_id == nonce_obj.job_id:
                passes = False
                try:
                    passes = check_share(
                        tmpl,
                        self.extranonce1,
                        nonce_obj.extranonce2,
                        nonce_obj.ntime,
                        nonce_obj.nonce,
                        difficulty_multiplier=self.server.share_threshold,
                    )
                except Exception as e:
                    logger.debug("Difficulty check error (mock data?): %s", e)
                    passes = True  # Accept if check fails (e.g., mock template)

                if not passes:
                    logger.info(
                        "Share DROPPED by difficulty filter (threshold=%.2f)",
                        self.server.share_threshold,
                    )
                    # Still accept at stratum level (miner did work)
                    # But don't send nonce to radio uplink
                    self.send_json({"id": req_id, "result": True, "error": None})
                    return
            else:
                logger.debug(
                    "Job mismatch or no template — accepting share without filter"
                )

        # Share passes filter — encode and output nonce
        self.server.nonce_output.write(nonce_obj)
        logger.info(
            "Share ACCEPTED → EHASH_NONCE job=%d nonce=0x%08x",
            nonce_obj.job_id,
            nonce_obj.nonce,
        )

        # Respond to miner
        self.send_json({"id": req_id, "result": True, "error": None})

    def handle_message(self, msg: dict) -> None:
        """Dispatch a parsed JSON-RPC message."""
        method = msg.get("method", "")

        if method == "mining.subscribe":
            self.handle_subscribe(msg)
        elif method == "mining.authorize":
            self.handle_authorize(msg)
        elif method == "mining.submit":
            self.handle_submit(msg)
        else:
            logger.debug("Unknown method '%s' from %s", method, self.addr)
            req_id = msg.get("id")
            self.send_json(
                {"id": req_id, "result": None, "error": [20, f"Unknown method: {method}", None]}
            )

    def run(self) -> None:
        """Main loop: read JSON lines, dispatch messages."""
        self.conn.settimeout(1.0)  # Allow periodic template pushes
        buf = b""

        try:
            while self._running and self.server.running:
                try:
                    data = self.conn.recv(4096)
                    if not data:
                        break
                    buf += data

                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            msg = json.loads(line.decode("utf-8"))
                            self.handle_message(msg)
                        except json.JSONDecodeError as e:
                            logger.warning("Bad JSON from %s: %s", self.addr, e)
                except socket.timeout:
                    # Periodically push new templates
                    self._maybe_push_update()
                    continue
        except (ConnectionResetError, BrokenPipeError, OSError) as e:
            logger.debug("Connection error from %s: %s", self.addr, e)
        finally:
            self.conn.close()
            self.server.remove_connection(self)
            logger.info("Connection closed: %s", self.addr)

    def _maybe_push_update(self) -> None:
        """Push mining.notify if a new template has arrived since last push."""
        if self.authorized and self.server.running:
            tmpl = self.server.store.get()
            if tmpl is not None:
                # Check if this is a new job we haven't pushed yet
                current_job = getattr(self, "_last_pushed_job", None)
                if tmpl.job_id != current_job:
                    self._last_pushed_job = tmpl.job_id
                    # Verify tollgate access
                    has_access, _ = self.server.tollgate.check_balance()
                    if has_access:
                        self.send_notify()


# ========================================================================
#  Stratum Server
# ========================================================================


class StratumServer:
    """TCP Stratum V1 server. Accepts Bitaxe connections."""

    def __init__(self, host: str, port: int, station_id: int, args):
        self.host = host
        self.port = port
        self.station_id = station_id
        self.args = args
        self.store = TemplateStore()
        self.tollgate = TollgateClient(
            base_url=args.tollgate_url,
            enabled=args.tollgate_enabled,
            permissive=args.tollgate_permissive,
        )
        self.nonce_output = NonceOutput(args.nonce_output)
        self.difficulty = args.difficulty
        self.share_threshold = args.share_threshold
        self.running = True
        self._connections: list[MinerConnection] = []
        self._conn_lock = threading.Lock()
        self._sock = None

    def add_connection(self, conn: MinerConnection) -> None:
        with self._conn_lock:
            self._connections.append(conn)

    def remove_connection(self, conn: MinerConnection) -> None:
        with self._conn_lock:
            if conn in self._connections:
                self._connections.remove(conn)

    def broadcast_notify(self) -> None:
        """Push mining.notify to all authorized connections."""
        with self._conn_lock:
            conns = list(self._connections)
        for conn in conns:
            if conn.authorized:
                has_access, _ = self.tollgate.check_balance()
                if has_access:
                    conn.send_notify()

    def template_feeder(self) -> None:
        """Background thread: read EHASH_TEMPLATE binary frames from input source.

        Supports:
        - 'stdin': read length-prefixed frames from sys.stdin.buffer
        - 'file:<path>': read from file, then watch for appends
        - 'mock': generate fake templates internally
        """
        source = self.args.template_input

        if source == "mock":
            self._mock_feeder()
        elif source == "stdin":
            self._stream_feeder(sys.stdin.buffer, "stdin")
        elif source.startswith("file:"):
            path = source[5:]
            try:
                f = open(path, "rb")
                self._stream_feeder(f, f"file:{path}")
            except FileNotFoundError:
                logger.error("Template file not found: %s", path)
                logger.info("Waiting for file to appear...")
                while self.running:
                    try:
                        f = open(path, "rb")
                        self._stream_feeder(f, f"file:{path}")
                        break
                    except FileNotFoundError:
                        time.sleep(2)
        else:
            logger.error("Unknown template input: %s", source)

    def _mock_feeder(self) -> None:
        """Generate fake templates periodically using mock_template.py."""
        from mock_template import make_fake_template

        job_id = 1
        logger.info("Mock template feeder started (interval=%.0fs)", self.args.mock_interval)

        while self.running:
            tmpl = make_fake_template(job_id)
            self.store.update(tmpl)
            logger.info("Mock template job_id=%d stored, broadcasting", job_id)
            self.broadcast_notify()
            job_id += 1
            time.sleep(self.args.mock_interval)

    def _stream_feeder(self, stream, name: str) -> None:
        """Read length-prefixed EHASH_TEMPLATE frames from a binary stream."""
        logger.info("Template feeder reading from %s", name)

        while self.running:
            try:
                frame = read_frame(stream)
                if frame is None:
                    logger.info("Template input %s: EOF", name)
                    # For file mode, try re-reading (file may still be appended)
                    if name.startswith("file:"):
                        time.sleep(1)
                        continue
                    break
                if len(frame) == 0:
                    continue

                # Parse the L7 envelope
                msg_type = get_envelope_type(frame)
                if msg_type != 0x10:  # EHASH_TEMPLATE
                    logger.debug(
                        "Ignoring non-template message type 0x%02x from %s",
                        msg_type,
                        name,
                    )
                    continue

                # Decode payload (skip type byte)
                tmpl = decode_template(frame[1:])
                self.store.update(tmpl)
                logger.info(
                    "Template job_id=%d decoded (%d bytes), broadcasting",
                    tmpl.job_id,
                    len(frame),
                )
                self.broadcast_notify()

            except Exception as e:
                logger.error("Template feeder error: %s", e)
                if not name.startswith("file:"):
                    break
                time.sleep(1)

    def serve(self) -> None:
        """Accept TCP connections and spawn handler threads."""
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.port))
        self._sock.listen(5)
        self._sock.settimeout(1.0)

        logger.info("Stratum server listening on %s:%d", self.host, self.port)
        print(
            f"[bridge] Stratum V1 server on {self.host}:{self.port} "
            f"(station_id={self.station_id})",
            file=sys.stderr,
        )

        while self.running:
            try:
                conn, addr = self._sock.accept()
                logger.info("New connection from %s", addr)
                handler = MinerConnection(conn, addr, self)
                self.add_connection(handler)
                t = threading.Thread(target=handler.run, daemon=True)
                t.start()
            except socket.timeout:
                continue
            except OSError:
                break

    def shutdown(self) -> None:
        """Graceful shutdown."""
        self.running = False
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
        self.nonce_output.close()
        logger.info("Server shut down")


def main():
    parser = argparse.ArgumentParser(
        description="E-Hash ground station Stratum V1 bridge daemon",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Data flow:
  EHASH_TEMPLATE (radio) → decode → mining.notify (stratum JSON) → Bitaxe
  mining.submit (Bitaxe) → difficulty filter → EHASH_NONCE (binary) → radio uplink

Examples:
  # Mock mode (generates fake templates, no balloon needed)
  python3 stratum_server.py --template-input mock

  # Read templates from stdin
  python3 mock_template.py --loop | python3 stratum_server.py --template-input stdin

  # With tollgate balance check
  python3 stratum_server.py --tollgate-enabled --tollgate-url http://127.0.0.1:3334
""",
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="Stratum listen address (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", type=int, default=3333, help="Stratum listen port (default: 3333)"
    )
    parser.add_argument(
        "--station-id",
        type=int,
        default=66,
        help="Ground station ID / worker_id (default: 66)",
    )
    parser.add_argument(
        "--difficulty",
        type=float,
        default=1.0,
        help="Stratum difficulty for mining.set_difficulty (default: 1.0)",
    )
    parser.add_argument(
        "--share-threshold",
        type=float,
        default=0.0,
        help="D7 difficulty filter threshold (default: 0 = pass all shares)",
    )
    parser.add_argument(
        "--template-input",
        default="mock",
        help="Template source: stdin, file:<path>, or mock (default: mock)",
    )
    parser.add_argument(
        "--nonce-output",
        default="stdout",
        help="Nonce output: stdout, none, or file:<path> (default: stdout)",
    )
    parser.add_argument(
        "--tollgate-enabled",
        action="store_true",
        help="Enable tollgate balance check before serving templates",
    )
    parser.add_argument(
        "--tollgate-url",
        default="http://127.0.0.1:3334",
        help="Tollgate API base URL (default: http://127.0.0.1:3334)",
    )
    parser.add_argument(
        "--tollgate-permissive",
        action="store_true",
        default=True,
        help="Allow access when tollgate is unreachable (default: True)",
    )
    parser.add_argument(
        "--no-tollgate-permissive",
        dest="tollgate_permissive",
        action="store_false",
        help="Deny access when tollgate is unreachable",
    )
    parser.add_argument(
        "--mock-interval",
        type=float,
        default=30.0,
        help="Mock template generation interval seconds (default: 30)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable debug logging"
    )
    args = parser.parse_args()

    # Configure logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        stream=sys.stderr,
    )

    server = StratumServer(args.host, args.port, args.station_id, args)

    # Start template feeder in background
    feeder_thread = threading.Thread(target=server.template_feeder, daemon=True)
    feeder_thread.start()

    # Run TCP server in main thread
    try:
        server.serve()
    except KeyboardInterrupt:
        print("\n[bridge] Shutting down...", file=sys.stderr)
        server.shutdown()


if __name__ == "__main__":
    main()
