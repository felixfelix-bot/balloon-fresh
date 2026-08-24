#!/usr/bin/env python3
"""
walk_capture.py — production-robust RX listener for 5km walk-tests.

Purpose
-------
Felix clips the TX board to a power bank and walks away up to 5 km. The RX
board stays plugged into the laptop. Every single packet the TX emits must be
captured to disk — zero data loss, even if the USB cable glitches, the TX is
unplugged (shifting the RX from /dev/ttyACM1 to /dev/ttyACM2), or the laptop
is bumped.

What it does
------------
1. Auto-detects the RX board by USB serial E663B035973B8332 (RP2040 #1),
   retrying every 2 s until it appears.
2. Opens the port with pyserial + ``exclusive=True`` (TIOCEXCL) so no other
   process (cat, minicom) can steal bytes.
3. Reads continuously. EVERY line from RX is:
     a) written to ``data/walk-tests/walk-YYYYMMDD-HHMMSS.log`` via the
        ``logging`` module (auto-flush per line — survives a Python crash),
     b) echoed to stdout for live monitoring.
4. Sends ``SET_TIME <unix_epoch>`` to the RX every 2 s, syncing the RX phase
   clock to the laptop's UTC (which mirrors the TX's GPS UTC).
5. Auto-reconnects on any serial error: closes, re-scans, reopens, and keeps
   writing to the SAME log file.
6. Prints live stats every 10 s and a full summary on exit.
7. Handles Ctrl+C gracefully (flush + close + summary).

Usage
-----
    python3 walk_capture.py                         # run until Ctrl+C
    python3 walk_capture.py 1800                    # run for 30 min
    python3 walk_capture.py 1800 /dev/ttyACM1       # duration + port override
    python3 walk_capture.py --port /dev/ttyACM1     # port only, run forever
    python3 walk_capture.py --baud 2000000 --outdir ./my-out --quiet

Output
------
    ~/repos/balloon-fresh/data/walk-tests/walk-YYYYMMDD-HHMMSS.log

Each captured line is prefixed with ``<ISO8601-UTC> | `` so post-hoc analysis
has wall-clock timing. Reconnect/shutdown events are recorded as
``# MARKER`` lines.
"""
from __future__ import annotations

import argparse
import glob
import logging
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Optional

try:
    import serial
    from serial import SerialException
except ImportError:
    print("ERROR: pyserial not installed. Run: pip install pyserial", file=sys.stderr)
    sys.exit(2)


# ─── Configuration ──────────────────────────────────────────────────────
RX_SERIAL = "E663B035973B8332"            # RP2040 #1 (RX board) USB serial
DEFAULT_BAUD = 2000000                      # USB CDC — baud is cosmetic
DEFAULT_OUTDIR = os.path.expanduser(
    "~/repos/balloon-fresh/data/walk-tests"
)
SET_TIME_INTERVAL = 2.0                    # seconds between SET_TIME syncs
STATS_INTERVAL = 10.0                      # seconds between live stats prints
RECONNECT_POLL = 2.0                       # seconds between board scans
PORT_GLOBS = ("/dev/ttyACM*", "/dev/ttyUSB*")

# PHASE_RESULT line, e.g.:
#   PHASE_RESULT 12 walk-A-walk-B pktSize=64 rx=10 unique=10 lost=0 per=0.0
#   rssi_avg=-57 rssi_min=-60 crc_err=0 garbage=0 tx_lat=52.3 tx_lon=4.9
#   sats=8 fix=1 utc=1234567890 tx_fw=0x10
_RE_PHASE = re.compile(
    r"PHASE_RESULT\s+\d+\s+\S+\s+"          # "PHASE_RESULT N NAME-NAME"
    r"pktSize=(\d+)\s+rx=(\d+)\s+unique=(\d+)\s+lost=(\d+)\s+per=([\d.]+)"
    r"\s+rssi_avg=(-?\d+)\s+rssi_min=(-?\d+)"
)


# ─── Board detection ────────────────────────────────────────────────────
def _udev_properties(port: str) -> str:
    """Return the udev property blob for a tty port ("" on failure).

    Uses ``udevadm info`` via subprocess. Never raises.
    """
    try:
        result = subprocess.run(
            ["udevadm", "info", "-q", "property", "-n", port],
            capture_output=True, text=True, timeout=2,
        )
        return result.stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def find_rx_port() -> Optional[str]:
    """Scan /dev/ttyACM* and /dev/ttyUSB* for the RX board by USB serial.

    Matches ``ID_SERIAL_SHORT`` (or ``ID_USB_SERIAL_SHORT``) against
    ``RX_SERIAL``. Returns the first matching /dev path, or None.
    """
    candidates: list[str] = []
    for pattern in PORT_GLOBS:
        candidates.extend(sorted(glob.glob(pattern)))
    for port in candidates:
        info = _udev_properties(port)
        if not info:
            continue
        # Prefer the precise ID_SERIAL_SHORT field to avoid false positives.
        for line in info.splitlines():
            if (line.startswith("ID_SERIAL_SHORT=")
                    or line.startswith("ID_USB_SERIAL_SHORT=")):
                if RX_SERIAL in line:
                    return port
        # Fallback: any mention of the serial in the blob.
        if RX_SERIAL in info:
            return port
    return None


def wait_for_rx_board(override: Optional[str] = None) -> Optional[str]:
    """Block until the RX board is found, polling every ``RECONNECT_POLL`` s.

    Prints "Waiting for RX board..." on each unsuccessful scan. Returns the
    port path (never None unless ``override`` is falsy AND the loop is broken
    by KeyboardInterrupt, which propagates). If ``override`` is given it is
    returned immediately.
    """
    if override:
        return override
    while True:
        port = find_rx_port()
        if port:
            return port
        print("Waiting for RX board...", flush=True)
        time.sleep(RECONNECT_POLL)


def open_rx_port(port: str, baud: int) -> serial.Serial:
    """Open the RX serial port with exclusive access.

    ``exclusive=True`` sets TIOCEXCL on Linux, preventing any other process
    (cat, minicom, idf.py monitor) from opening the same tty — this kills the
    classic "two readers compete for bytes" bug. Input/output buffers are
    reset to discard leftover data from a previous open.
    """
    ser = serial.Serial(
        port=port,
        baudrate=baud,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.5,            # read() returns every 0.5s → fast Ctrl+C response
        write_timeout=1.0,
        exclusive=True,
    )
    try:
        ser.reset_input_buffer()
        ser.reset_output_buffer()
    except (SerialException, OSError):
        pass
    return ser


# ─── Capture session: log file + live stats ─────────────────────────────
class _UTCFormatter(logging.Formatter):
    """logging.Formatter that emits UTC timestamps with millisecond precision."""
    converter = time.gmtime  # type: ignore[assignment]


class CaptureSession:
    """Owns the output log file and live stats counters for one run.

    The log file is opened ONCE (via a ``logging.FileHandler``) and kept open
    across reconnects — a walk-test is never split across multiple files just
    because the USB cable glitched. The ``logging`` module's FileHandler
    flushes after every emit, so a Python crash never loses committed data.
    """

    def __init__(self, outdir: str) -> None:
        os.makedirs(outdir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.log_path = os.path.join(outdir, f"walk-{ts}.log")

        # Dedicated capture logger → file only (no stderr, no propagation).
        self._logger = logging.getLogger(f"walk_capture.{ts}")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False
        self._handler = logging.FileHandler(
            self.log_path, mode="a", encoding="utf-8"
        )
        self._handler.setFormatter(
            _UTCFormatter("%(asctime)s | %(message)s",
                          datefmt="%Y-%m-%dT%H:%M:%S")
        )
        self._logger.addHandler(self._handler)

        # Stats
        self.start_time = time.time()
        self.syncs_sent = 0
        self.phases_seen = 0          # every PHASE_RESULT line
        self.packets_decoded = 0      # PHASE_RESULT lines with rx >= 1
        self.rssi_min_samples: list[int] = []   # rssi_min field (per-phase floor)
        self.rssi_avg_samples: list[int] = []   # rssi_avg field (for range)
        self.reconnects = 0

    # ── log writers ──────────────────────────────────────────────────
    def write_line(self, line: str) -> None:
        """Write a captured RX line to the log with a UTC timestamp prefix.

        Embedded newlines are split so each physical line gets its own
        timestamp. The FileHandler flushes automatically on each emit.
        """
        pieces = line.splitlines() or [""]
        for piece in pieces:
            self._logger.info(piece)

    def write_marker(self, text: str) -> None:
        """Write a comment marker line (CONNECTED / RECONNECT / SHUTDOWN...)."""
        self._logger.info(f"# {text}")

    # ── PHASE_RESULT parsing ─────────────────────────────────────────
    def parse_phase(self, line: str) -> None:
        """Update counters from a PHASE_RESULT line. Never raises.

        A single malformed line must not take down the capture daemon — the
        whole point is zero data loss.
        """
        match = _RE_PHASE.search(line)
        if not match:
            return
        try:
            # Groups: 1=pktSize 2=rx 3=unique 4=lost 5=per 6=rssi_avg 7=rssi_min
            rx = int(match.group(2))
            rssi_avg = int(match.group(6))
            rssi_min = int(match.group(7))
        except (ValueError, IndexError):
            self.phases_seen += 1
            return

        self.phases_seen += 1
        if rx >= 1:
            self.packets_decoded += 1
            if rssi_min != 0:
                self.rssi_min_samples.append(rssi_min)
            if rssi_avg != 0:
                self.rssi_avg_samples.append(rssi_avg)

    # ── live stats ───────────────────────────────────────────────────
    def maybe_stats(self, last_report: list[float]) -> None:
        """Print a one-line stats block every ``STATS_INTERVAL`` seconds.

        ``last_report`` is a single-element list (mutable time holder).
        Format: ``[Xs] syncs=N phases=M decoded=K rssimin=-YdBm``
        """
        now = time.time()
        if now - last_report[0] < STATS_INTERVAL:
            return
        last_report[0] = now
        elapsed = int(now - self.start_time)
        if self.rssi_min_samples:
            rssimin = min(self.rssi_min_samples)
            rssi_str = f"rssimin={rssimin}dBm"
        else:
            rssi_str = "rssimin=--dBm"
        print(
            f"[{elapsed}s] syncs={self.syncs_sent} "
            f"phases={self.phases_seen} decoded={self.packets_decoded} "
            f"{rssi_str}",
            flush=True,
        )

    # ── shutdown ─────────────────────────────────────────────────────
    def summary(self) -> None:
        """Print the final summary block (duration, totals, RSSI range, path)."""
        elapsed = time.time() - self.start_time
        rssi_lo = min(self.rssi_min_samples) if self.rssi_min_samples else None
        rssi_hi = max(self.rssi_avg_samples) if self.rssi_avg_samples else None
        print("\n=== WALK CAPTURE SUMMARY ===", flush=True)
        print(f"Duration      : {elapsed:.0f}s", flush=True)
        print(f"Total syncs   : {self.syncs_sent}", flush=True)
        print(f"Total phases  : {self.phases_seen}", flush=True)
        print(f"Total decoded : {self.packets_decoded}", flush=True)
        print(f"Reconnects    : {self.reconnects}", flush=True)
        if rssi_lo is not None and rssi_hi is not None:
            samples = len(self.rssi_min_samples)
            print(f"RSSI range    : {rssi_lo}..{rssi_hi} dBm "
                  f"({samples} samples)", flush=True)
        else:
            print("RSSI range    : (no packets decoded with RSSI)", flush=True)
        print(f"Log file      : {self.log_path}", flush=True)

    def close(self) -> None:
        """Flush and close the file handler. Never raises."""
        try:
            self._handler.flush()
            # fsync the underlying file descriptor for durability on power loss.
            stream = self._handler.stream
            if stream is not None:
                try:
                    os.fsync(stream.fileno())
                except (OSError, ValueError):
                    pass
            self._handler.close()
        except Exception:
            pass


# ─── Per-connection read/sync loop ──────────────────────────────────────
def run_connection(
    ser: serial.Serial,
    session: CaptureSession,
    duration: Optional[float],
    port: str,
    echo_stdout: bool = True,
) -> bool:
    """Read from ``ser`` until error, duration elapsed, or KeyboardInterrupt.

    Returns True if the run is finished (duration elapsed) → caller stops.
    Returns False if the connection died → caller should reconnect.
    KeyboardInterrupt propagates to the caller for graceful shutdown.

    Parameters
    ----------
    ser          : open pyserial Serial instance
    session      : the CaptureSession (for logging + stats)
    duration     : total run length in seconds, or None for indefinite
    port         : the port path (for markers + existence check)
    echo_stdout  : if True, print every captured line to stdout
    """
    last_sync = 0.0
    last_report = [time.time()]
    buf = b""

    session.write_marker(f"CONNECTED port={port}")

    while True:
        # ── Duration check ──────────────────────────────────────────
        if duration is not None and time.time() - session.start_time >= duration:
            return True

        # ── Send SET_TIME every SET_TIME_INTERVAL ───────────────────
        now = time.time()
        if now - last_sync >= SET_TIME_INTERVAL:
            utc = int(now)
            try:
                ser.write(f"SET_TIME {utc}\n".encode("ascii"))
                ser.flush()
                session.syncs_sent += 1
                last_sync = now
                # Printed to stdout only (NOT written to the capture log).
                print(f"TIME_SYNCED utc={utc}", flush=True)
            except (SerialException, OSError) as exc:
                print(f"[error] SET_TIME write failed: {exc}",
                      file=sys.stderr, flush=True)
                session.write_marker(f"WRITE_ERROR port={port} ({exc})")
                return False

        # ── Read a chunk ────────────────────────────────────────────
        try:
            data = ser.read(4096)
        except (SerialException, OSError) as exc:
            print(f"[error] serial read failed: {exc}",
                  file=sys.stderr, flush=True)
            session.write_marker(f"READ_ERROR port={port} ({exc})")
            return False

        if not data:
            # No data this 0.5 s tick. Detect port disappearance so we
            # reconnect immediately rather than waiting for a write error
            # (handles USB unplugs where read just returns empty forever).
            if not os.path.exists(port):
                print(f"[warn] port {port} disappeared from filesystem",
                      file=sys.stderr, flush=True)
                session.write_marker(f"PORT_GONE port={port}")
                return False
            session.maybe_stats(last_report)
            continue

        # ── Process complete lines ──────────────────────────────────
        buf += data
        while b"\n" in buf:
            raw, buf = buf.split(b"\n", 1)
            line = raw.strip(b"\r").decode("utf-8", errors="replace").strip()
            if not line:
                continue
            # EVERY line → log file (timestamped, auto-flushed).
            session.write_line(line)
            # EVERY line → stdout for live monitoring.
            if echo_stdout:
                print(line, flush=True)
            if line.startswith("PHASE_RESULT"):
                session.parse_phase(line)
        session.maybe_stats(last_report)


# ─── Main: arg parse + reconnect loop ───────────────────────────────────
def main() -> int:
    """Entry point. Returns process exit code (0 on clean exit)."""
    ap = argparse.ArgumentParser(
        description="Production-robust RX walk-test capture.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  walk_capture.py                       # run until Ctrl+C\n"
            "  walk_capture.py 1800                  # run for 30 min\n"
            "  walk_capture.py 1800 /dev/ttyACM1     # duration + port\n"
            "  walk_capture.py --port /dev/ttyACM1   # port override, forever\n"
            "  walk_capture.py --quiet               # stats + phases only on stdout\n"
        ),
    )
    ap.add_argument(
        "duration", nargs="?", type=float, default=None,
        help="Run length in seconds (default: run until Ctrl+C).",
    )
    ap.add_argument(
        "rx_port_override", nargs="?", default=None,
        help="RX port path, skips auto-detect (default: auto-detect by serial).",
    )
    ap.add_argument(
        "--port", dest="port_flag", default=None,
        help="Alias for rx_port_override positional arg.",
    )
    ap.add_argument("--baud", type=int, default=DEFAULT_BAUD,
                    help=f"Baud rate (default: {DEFAULT_BAUD}).")
    ap.add_argument("--outdir", default=DEFAULT_OUTDIR,
                    help=f"Output directory (default: {DEFAULT_OUTDIR}).")
    ap.add_argument(
        "-q", "--quiet", action="store_true",
        help="Suppress per-line stdout echo (still logs to file; shows stats + phases).",
    )
    args = ap.parse_args()

    duration: Optional[float] = args.duration
    # Positional rx_port_override wins; fall back to --port flag.
    port_override: Optional[str] = args.rx_port_override or args.port_flag
    echo_stdout: bool = not args.quiet

    print("=== WALK CAPTURE (production-robust) ===", flush=True)
    print(f"RX serial   : {RX_SERIAL}", flush=True)
    print(f"Baud        : {args.baud}", flush=True)
    print(f"Outdir      : {args.outdir}", flush=True)
    if duration is not None:
        print(f"Duration    : {duration:.0f}s", flush=True)
    else:
        print("Duration    : indefinite (Ctrl+C to stop)", flush=True)
    if port_override:
        print(f"Port        : {port_override} (override)", flush=True)
    else:
        print(f"Port        : auto-detect by serial {RX_SERIAL}", flush=True)
    print(f"SET_TIME    : every {SET_TIME_INTERVAL:.0f}s", flush=True)
    print(f"Stats       : every {STATS_INTERVAL:.0f}s", flush=True)
    print(f"Stdout echo : {'on' if echo_stdout else 'off (--quiet)'}", flush=True)
    print("---", flush=True)

    session = CaptureSession(args.outdir)
    print(f"Log file    : {session.log_path}", flush=True)

    exit_code = 0
    interrupted = False
    try:
        while True:
            # ── Duration check (also covers 0-duration edge case) ────
            if duration is not None and time.time() - session.start_time >= duration:
                break

            # ── Find / wait for the board ────────────────────────────
            port = wait_for_rx_board(port_override)
            # wait_for_rx_board only returns None if override is None AND the
            # board never appears — but it blocks forever in that case
            # (until KeyboardInterrupt), so `port` is a real path here.
            assert port is not None

            # ── Connect ──────────────────────────────────────────────
            try:
                ser = open_rx_port(port, args.baud)
            except (SerialException, OSError) as exc:
                print(f"[error] cannot open {port}: {exc}",
                      file=sys.stderr, flush=True)
                session.write_marker(f"OPEN_FAIL port={port} ({exc})")
                # Back off — port may be transiently busy.
                time.sleep(RECONNECT_POLL)
                continue

            print(f"[connect] {port} @ {args.baud} baud (exclusive)",
                  flush=True)

            # ── Run until disconnect / duration / interrupt ──────────
            done = run_connection(
                ser, session, duration, port, echo_stdout=echo_stdout
            )
            try:
                ser.close()
            except (SerialException, OSError):
                pass

            if done:
                # Duration elapsed → stop cleanly.
                break

            # Connection died → reconnect. Same log file continues.
            session.reconnects += 1
            session.write_marker(f"RECONNECT ({session.reconnects})")
            print("[RECONNECT] Lost RX board, rescanning...",
                  file=sys.stderr, flush=True)
            time.sleep(RECONNECT_POLL)

    except KeyboardInterrupt:
        interrupted = True
        print("\n[Ctrl+C] shutting down gracefully...", file=sys.stderr, flush=True)
    except (SerialException, OSError) as exc:
        # Unexpected fatal serial error not handled above.
        print(f"[fatal] {exc}", file=sys.stderr, flush=True)
        exit_code = 1
    finally:
        session.write_marker("SHUTDOWN")
        session.summary()
        session.close()

    if interrupted:
        # Distinguish Ctrl+C exit from duration-elapsed exit if needed.
        pass

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
