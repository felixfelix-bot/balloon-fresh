#!/usr/bin/env python3
"""
rx_capture.py — Robust RX capture daemon for the LR2021 sweep range tests.

Implements ADR-020 ("Robust RX Capture Daemon"). Replaces every ad-hoc
`cat /dev/ttyACM*` / `dd if=/dev/ttyACM*` / walk_capture.py invocation that
fought over the RX serial port.

Design invariants (ADR-020):
  1. Opens the RX port by SERIAL ID (8332), never a hardcoded /dev path —
     ports shift on replug; the board's OTP serial is stable.
  2. Writes timestamped files: rx_capture_YYYYMMDD_HHMMSS.log
  3. Rotates files every 30 minutes (keeps individual files tractable).
  4. Survives port disconnect/reconnect — re-scans udev, reopens, keeps going.
  5. EXCLUSIVE lock: fcntl on a lockfile + pyserial exclusive=TIOCEXCL — no two
     capture processes can ever read the same port.
  6. Clean shutdown on SIGINT/SIGTERM — flushes, releases lock, closes port.
  7. Optional --resync: continuously send "SET_TIME <epoch>" to the RX every
     10s so its UTC phase clock tracks the laptop NTP clock (ADR-019 sync).

Firmware output (RX board, multi_radio_sweep_rx_v4.cpp) is plain ASCII:
    PHASE_START <n> <name> pktSize=<n>
    PHASE_RESULT <n> <name> pktSize=<n> rx=<n> unique=<n> ... tx_fw=<h> rx_fw=<h>
    PKT rx=<n> seq=<n> rssi=<dbm> phase=<n> ...
This daemon writes those lines verbatim (binary-safe) to the rotating log,
prefixed with an ISO-8601 UTC timestamp so analysis is possible even if the
firmware line itself lacks timing.

Usage:
  # Foreground, default RX serial 8332, 30-min rotation, no resync:
  python3 tools/rx_capture.py
  # With continuous 10s SET_TIME resync + custom output dir:
  python3 tools/rx_capture.py --resync --out-dir data/rx_captures
  # Override serial / baud / rotation:
  python3 tools/rx_capture.py --serial 8332 --baud 115200 --rotate-min 30

Make targets (firmware/rp2040/Makefile):
  make capture        # start this daemon in the background
  make capture-stop   # stop it (SIGTERM via pidfile)

Dependencies: pyserial. Port detection uses the sibling port_util.py module
(udevadm-based; no extra Python deps).
"""

import argparse
import fcntl
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Import the sibling port detection utility.
TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))
from port_util import find_port  # noqa: E402

try:
    import serial as pyserial
except ImportError:
    print("ERROR: pyserial required. Install with: pip install pyserial",
          file=sys.stderr)
    sys.exit(1)


# ─── Globals for signal handling ──────────────────────────────────────────
_RUNNING = True
_PORT: pyserial.Serial | None = None


def _request_shutdown(signum, _frame):
    global _RUNNING
    _RUNNING = False
    print(f"\n[capture] received signal {signum}, shutting down...", file=sys.stderr)
    try:
        if _PORT is not None and _PORT.is_open:
            _PORT.close()
    except Exception:
        pass


# ─── Exclusive lock ───────────────────────────────────────────────────────

class ExclusionLock:
    """flock-based singleton lock so only one rx_capture runs at a time."""

    def __init__(self, path: Path):
        self.path = path
        self._fh = None

    def acquire(self, timeout: float = 10.0) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "w")
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(self._fh.fileno(),
                            fcntl.LOCK_EX | fcntl.LOCK_NB)
                # Write our PID for `make capture-stop`.
                self._fh.seek(0)
                self._fh.truncate()
                self._fh.write(str(os.getpid()))
                self._fh.flush()
                return True
            except (BlockingIOError, OSError):
                if time.monotonic() >= deadline:
                    self._fh.close()
                    self._fh = None
                    return False
                time.sleep(0.3)

    def release(self):
        if self._fh:
            try:
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
            try:
                self._fh.close()
            except Exception:
                pass
            try:
                self.path.unlink()
            except Exception:
                pass
            self._fh = None


# ─── Rotating log writer ──────────────────────────────────────────────────

class RotatingLog:
    """Writes raw serial bytes to a timestamped .log file, rotating every N min.

    File naming: rx_capture_YYYYMMDD_HHMMSS.log
    A new file is created at startup and on each rotation boundary.
    Bytes are flushed after every write so data survives an abrupt kill.
    """

    PREFIX = "rx_capture"

    def __init__(self, out_dir: Path, rotate_minutes: int = 30):
        self.out_dir = out_dir
        self.rotate_seconds = rotate_minutes * 60
        self._fh = None
        self._current_path: Path | None = None
        self._segment_start = 0.0
        self._bytes_written = 0
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def _open_new(self):
        self.close()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._current_path = self.out_dir / f"{self.PREFIX}_{ts}.log"
        self._fh = open(self._current_path, "ab")  # binary, append-safe
        self._segment_start = time.monotonic()
        self._bytes_written = 0
        header = (f"# rx_capture segment start {datetime.now(timezone.utc).isoformat()}\n"
                  f"# rotation={self.rotate_seconds}s\n").encode()
        self._fh.write(header)
        self._fh.flush()
        print(f"[capture] writing to {self._current_path}", file=sys.stderr)

    def write(self, data: bytes):
        if self._fh is None or \
                (time.monotonic() - self._segment_start) >= self.rotate_seconds:
            self._open_new()
        assert self._fh is not None  # _open_new guarantees a handle
        if not data:
            return
        # Prefix each complete/arriving chunk with a wall-clock stamp so the
        # log is self-describing even without firmware-embedded timestamps.
        # We write raw bytes after the stamp to stay binary-safe.
        stamp = f"{datetime.now(timezone.utc).isoformat()} ".encode()
        self._fh.write(stamp)
        self._fh.write(data)
        # Ensure lines aren't split across stamps if data lacks a trailing NL.
        if not data.endswith(b"\n"):
            self._fh.write(b"\n")
        self._fh.flush()
        os.fsync(self._fh.fileno())
        self._bytes_written += len(data)

    def close(self):
        if self._fh:
            try:
                self._fh.flush()
                self._fh.close()
            except Exception:
                pass
            self._fh = None
            if self._bytes_written > 0 and self._current_path:
                print(f"[capture] closed {self._current_path} "
                      f"({self._bytes_written} bytes)", file=sys.stderr)


# ─── Serial connection manager ────────────────────────────────────────────

class RxConnection:
    """Opens the RX port by serial ID, with reconnect-on-disconnect.

    Uses pyserial exclusive=True (TIOCEXCL on Linux) so a second open() of the
    same device fails — defence in depth beyond the flock singleton.
    """

    def __init__(self, serial_suffix: str, baud: int, timeout: float = 1.0):
        self.serial_suffix = serial_suffix
        self.baud = baud
        self.timeout = timeout
        self._ser: pyserial.Serial | None = None
        self._cur_port: str | None = None

    def _open(self) -> bool:
        global _PORT
        port = find_port(self.serial_suffix, timeout=0)
        if not port:
            return False
        try:
            self._ser = pyserial.Serial(
                port, self.baud, timeout=self.timeout, exclusive=True)
            self._cur_port = port
            _PORT = self._ser
            return True
        except Exception as e:
            print(f"[capture] open({port}) failed: {e}", file=sys.stderr)
            self._ser = None
            _PORT = None
            return False

    def ensure_open(self) -> bool:
        if self._ser is not None:
            try:
                # Cheap liveness probe.
                if self._ser.in_waiting >= 0:
                    return True
            except Exception:
                self.close()
        return self._open()

    def read(self, size: int = 4096) -> bytes:
        try:
            data = self._ser.read(size) if self._ser else b""
        except Exception as e:
            print(f"[capture] read error: {e} — reconnecting", file=sys.stderr)
            self.close()
            return b""
        if not data:
            # Distinguish idle from disconnect.
            try:
                if self._ser is not None and not self._ser.is_open:
                    self.close()
            except Exception:
                self.close()
        return data

    def write(self, data: bytes) -> int:
        if self._ser is None:
            return 0
        try:
            n = self._ser.write(data)
            return n if n is not None else 0
        except Exception as e:
            print(f"[capture] write error: {e} — reconnecting", file=sys.stderr)
            self.close()
            return 0

    def close(self):
        global _PORT
        if self._ser:
            try:
                self._ser.close()
            except Exception:
                pass
        self._ser = None
        self._cur_port = None
        _PORT = None


# ─── Resync loop helper ───────────────────────────────────────────────────

def _send_resync(conn: RxConnection) -> bool:
    """Push the laptop's UTC epoch to the RX so both boards share a phase clock.

    RX firmware (multi_radio_sweep_rx_v4.cpp) accepts:
        SET_TIME <unix_timestamp>\n
    Sending this every 10s keeps the RX's computePhaseFromUTC() aligned with
    the laptop's NTP-disciplined clock (ADR-019 invariant: phase offset < 500ms).
    TX gets its time from GPS autonomously (ADR-018) — never needs this.
    """
    epoch = int(time.time())
    ok = conn.write(f"SET_TIME {epoch}\n".encode()) > 0
    if ok:
        print(f"[capture] resync SET_TIME {epoch} -> RX", file=sys.stderr)
    return ok


# ─── Main loop ────────────────────────────────────────────────────────────

def run(serial_suffix: str, baud: int, out_dir: Path, rotate_min: int,
        resync: bool, resync_interval: float):
    global _RUNNING

    # Singleton lock — refuse to start if another capture daemon is running.
    lock_path = Path("/tmp") / f"rx_capture_{serial_suffix}.lock"
    lock = ExclusionLock(lock_path)
    if not lock.acquire(timeout=2.0):
        holder_pid = ""
        try:
            holder_pid = lock_path.read_text().strip()
        except Exception:
            pass
        print(f"ERROR: another rx_capture is already running "
              f"(pid={holder_pid}, lock={lock_path}).", file=sys.stderr)
        print("Run `make capture-stop` first.", file=sys.stderr)
        sys.exit(1)

    signal.signal(signal.SIGINT, _request_shutdown)
    signal.signal(signal.SIGTERM, _request_shutdown)

    conn = RxConnection(serial_suffix, baud, timeout=1.0)
    log = RotatingLog(out_dir, rotate_minutes=rotate_min)

    print(f"[capture] RX serial suffix={serial_suffix} baud={baud} "
          f"rotate={rotate_min}min resync={resync} -> {out_dir}",
          file=sys.stderr)

    last_resync = 0.0
    reconnect_backoff = 1.0
    total_bytes = 0

    try:
        while _RUNNING:
            if not conn.ensure_open():
                # Port not present — poll for it.
                if reconnect_backoff <= 1.0:
                    print(f"[capture] RX ({serial_suffix}) not found; "
                          f"waiting for reconnect...", file=sys.stderr)
                time.sleep(reconnect_backoff)
                reconnect_backoff = min(reconnect_backoff * 1.5, 10.0)
                continue

            reconnect_backoff = 1.0  # reset after a successful open

            data = conn.read(4096)
            if data:
                total_bytes += len(data)
                log.write(data)
            else:
                # Idle tick — avoid busy loop.
                time.sleep(0.05)

            # Continuous resync (ADR-019): keep RX phase clock aligned.
            if resync and time.monotonic() - last_resync >= resync_interval:
                if _send_resync(conn):
                    last_resync = time.monotonic()

    finally:
        print(f"[capture] stopping — captured {total_bytes} bytes total",
              file=sys.stderr)
        log.close()
        conn.close()
        lock.release()
        print("[capture] clean shutdown complete", file=sys.stderr)


# ─── CLI ──────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        description="Robust RX capture daemon (ADR-020). Writes timestamped, "
                    "rotating logs from the RX board, locked & reconnect-safe.")
    p.add_argument("--serial", default="8332",
                   help="RX board serial ID suffix (default: 8332)")
    p.add_argument("--baud", type=int, default=115200,
                   help="serial baud rate (default: 115200)")
    p.add_argument("--out-dir", default="data/rx_captures",
                   help="output directory for rx_capture_*.log files "
                        "(default: data/rx_captures)")
    p.add_argument("--rotate-min", type=int, default=30,
                   help="log rotation interval in minutes (default: 30)")
    p.add_argument("--resync", action="store_true",
                   help="continuously send SET_TIME to RX every N seconds "
                        "(keeps RX phase clock aligned to laptop NTP, ADR-019)")
    p.add_argument("--resync-interval", type=float, default=10.0,
                   help="seconds between SET_TIME resyncs (default: 10)")
    args = p.parse_args()

    out_dir = Path(args.out_dir)
    run(serial_suffix=args.serial, baud=args.baud, out_dir=out_dir,
        rotate_min=args.rotate_min, resync=args.resync,
        resync_interval=args.resync_interval)


if __name__ == "__main__":
    main()
