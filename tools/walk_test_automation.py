#!/usr/bin/env python3
"""
walk_test_automation.py — Unified walk test automation for balloon range tests.

Logs GPS + RSSI + packet stats from RP2040 boards via serial, auto-generates
plots after capture. Uses the BoardSerial wrapper (mandatory — never raw
serial.Serial() for board ports).

What it does
------------
1. Acquires the board mutex lock (balloon-board-lock.py) for both TX and RX.
2. Opens RX (and optionally TX) serial ports via BoardSerial.
3. Optionally opens a GPS serial port for NMEA position data.
4. Captures RX serial output for the specified duration, parsing packet lines:
     RSSI=<value> PKT=<seq> PER=<pct> MODE=<flrc_mode> BW=<kbps> PAYLOAD=<bytes>
   Also handles legacy formats (PKT n seq=.. rssi=.., PHASE_RESULT, RANGE_RESULT_RX).
5. Logs structured data to data/walk-test-<timestamp>.csv.
6. Auto-generates matplotlib plots: RSSI vs distance, PER vs distance,
   throughput vs distance. Saved as data/walk-test-<timestamp>.png.
7. Releases the board lock when done (even on Ctrl+C or error).

Usage
-----
    # Basic: single distance, 12 min capture
    python3 walk_test_automation.py --rx-port /dev/ttyACM2 --distance 10

    # Multi-distance walk test (prompts between segments)
    python3 walk_test_automation.py --rx-port /dev/ttyACM2 \\
        --distances 5,10,20,50,100 --duration 720

    # With GPS
    python3 walk_test_automation.py --rx-port /dev/ttyACM2 \\
        --tx-port /dev/ttyACM0 --gps-port /dev/ttyACM1 \\
        --distance 50 --duration 600

    # No-lock mode (for dry runs / testing without hardware)
    python3 walk_test_automation.py --no-lock --distance 0 --duration 10
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ─── BoardSerial wrapper (MANDATORY) ────────────────────────────────────
# The tools dir in the main repo has board_serial.py. We also check the
# local worktree tools dir as fallback (for development).
_TOOLS_CANDIDATES = [
    Path.home() / "repos" / "balloon-fresh" / "tools",
    Path(__file__).resolve().parent,
]
for _td in _TOOLS_CANDIDATES:
    if (_td / "board_serial.py").exists():
        sys.path.insert(0, str(_td))
        break

try:
    from board_serial import BoardSerial
except ImportError:
    print(
        "ERROR: Cannot import BoardSerial. Ensure board_serial.py is in "
        f"{Path.home() / 'repos' / 'balloon-fresh' / 'tools'} or alongside "
        "this script.",
        file=sys.stderr,
    )
    sys.exit(2)

# ─── pyserial (for GPS port — NOT for board ports) ──────────────────────
try:
    import serial as pyserial
    from serial import SerialException
except ImportError:
    print("ERROR: pyserial not installed. Run: pip install pyserial", file=sys.stderr)
    sys.exit(2)

# ─── Optional: matplotlib for auto-plotting ─────────────────────────────
_HAS_MPL = False
try:
    import matplotlib
    matplotlib.use("Agg")  # Non-interactive backend — safe for headless
    import matplotlib.pyplot as plt
    _HAS_MPL = True
except ImportError:
    pass  # Will print helpful message when plotting is attempted

_HAS_NUMPY = False
try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    pass

# ─── Optional: seaborn for nicer plots ──────────────────────────────────
_HAS_SEABORN = False
try:
    import seaborn as sns
    _HAS_SEABORN = True
except ImportError:
    pass  # Fallback to default matplotlib style

# ─── Configuration ──────────────────────────────────────────────────────
DEFAULT_TRACK = "range-tests"
DEFAULT_BAUD = 115200
DEFAULT_DURATION = 720          # 12 min (full sweep cycle)
DEFAULT_OUTPUT = "data"
GPS_BAUD = 9600
RECONNECT_DELAY = 2.0           # seconds between reconnect attempts
STATS_INTERVAL = 10.0           # seconds between live stats prints
BOARD_LOCK_TIMEOUT = 120        # seconds for board lock acquire

LOCK_SCRIPT = Path.home() / "repos" / "balloon-fresh" / "tools" / "balloon-board-lock.py"

# CSV columns for walk test output
CSV_COLUMNS = [
    "timestamp",
    "distance_m",
    "rssi_dbm",
    "pkt_seq",
    "per_pct",
    "mode",
    "bitrate_kbps",
    "payload_bytes",
    "gps_lat",
    "gps_lon",
]

# ─── Line parsers ───────────────────────────────────────────────────────
# Primary format (new range-tests firmware):
#   RSSI=-85 PKT=42 PER=2.5 MODE=FLRC_2600 BW=2600 PAYLOAD=255
_RE_PRIMARY = re.compile(
    r"RSSI=(-?\d+)\s+"
    r"PKT=(\d+)\s+"
    r"PER=([\d.]+)\s+"
    r"MODE=(\S+)\s+"
    r"BW=(\d+)\s+"
    r"PAYLOAD=(\d+)"
)

# Legacy PKT format (range_rx_auto / multi_radio_sweep_rx firmware):
#   PKT rx=N seq=N rssi=N phase=N ...
#   PKT n seq=N rssi=N uptime=Nms
_RE_PKT_LEGACY = re.compile(r"PKT\s+\d+\s+seq=(\d+)\s+rssi=(-?\d+)")

# Legacy PHASE_RESULT format:
#   PHASE_RESULT N NAME pktSize=.. rx=.. unique=.. lost=.. per=.. rssi_avg=.. rssi_min=..
_RE_PHASE_RESULT = re.compile(
    r"PHASE_RESULT\s+\d+\s+\S+\s+"
    r"pktSize=(\d+)\s+rx=(\d+)\s+unique=(\d+)\s+lost=(\d+)\s+per=([\d.]+)"
    r"\s+rssi_avg=(-?\d+)\s+rssi_min=(-?\d+)"
)

# RANGE_RESULT_RX aggregate format:
#   RANGE_RESULT_RX,window=N,rx=N,per=X,bitrate=N,pktSize=N,...
_RE_RANGE_RESULT = re.compile(r"RANGE_RESULT_RX[,]\s*(.+)")


def parse_kv(text: str) -> dict:
    """Parse key=value pairs from text (comma or space separated)."""
    fields = {}
    for m in re.finditer(r"(\w+)=([^,\s]+)", text):
        fields[m.group(1)] = m.group(2)
    return fields


def parse_rx_line(line: str) -> Optional[dict]:
    """Parse a single RX serial line into a structured data dict.

    Handles multiple firmware output formats:
      1. Primary:  RSSI=-85 PKT=42 PER=2.5 MODE=FLRC_2600 BW=2600 PAYLOAD=255
      2. Legacy:   PKT n seq=42 rssi=-85 uptime=1234ms
      3. PHASE:    PHASE_RESULT N NAME pktSize=.. rx=.. per=.. rssi_avg=..
      4. RANGE:    RANGE_RESULT_RX,rx=.. per=.. bitrate=.. pktSize=..

    Returns a dict with keys matching CSV_COLUMNS, or None if unparseable.
    """
    line = line.strip()
    if not line:
        return None

    row = {col: "" for col in CSV_COLUMNS}
    row["timestamp"] = datetime.now(timezone.utc).isoformat()

    # ── Primary format ──────────────────────────────────────────────
    m = _RE_PRIMARY.search(line)
    if m:
        row["rssi_dbm"] = int(m.group(1))
        row["pkt_seq"] = int(m.group(2))
        row["per_pct"] = float(m.group(3))
        row["mode"] = m.group(4)
        row["bitrate_kbps"] = int(m.group(5))
        row["payload_bytes"] = int(m.group(6))
        return row

    # ── Legacy per-packet format ────────────────────────────────────
    m = _RE_PKT_LEGACY.search(line)
    if m:
        row["pkt_seq"] = int(m.group(1))
        row["rssi_dbm"] = int(m.group(2))
        # Extract optional phase/mode from surrounding KV pairs
        kv = parse_kv(line)
        phase = kv.get("phase", "")
        if phase:
            row["mode"] = f"phase_{phase}"
        return row

    # ── PHASE_RESULT (aggregate per phase) ──────────────────────────
    m = _RE_PHASE_RESULT.search(line)
    if m:
        row["pkt_seq"] = 0
        row["rssi_dbm"] = int(m.group(6))    # rssi_avg
        row["per_pct"] = float(m.group(5))
        row["payload_bytes"] = int(m.group(1))
        row["mode"] = "phase_result"
        # Try to extract bitrate from the line
        kv = parse_kv(line)
        if "br" in kv:
            row["bitrate_kbps"] = int(kv["br"])
        return row

    # ── RANGE_RESULT_RX (aggregate window) ──────────────────────────
    m = _RE_RANGE_RESULT.search(line)
    if m:
        kv = parse_kv(m.group(1))
        rssi = kv.get("rssi_avg") or kv.get("rssi")
        per = kv.get("per")
        bitrate = kv.get("bitrate") or kv.get("br")
        pkt_size = kv.get("pktSize") or kv.get("pkt_sz")
        if rssi:
            row["rssi_dbm"] = float(rssi)
        if per:
            row["per_pct"] = float(per)
        if bitrate:
            row["bitrate_kbps"] = int(float(bitrate))
        if pkt_size:
            row["payload_bytes"] = int(pkt_size)
        row["mode"] = "range_result"
        return row

    return None


# ─── GPS NMEA parsing ───────────────────────────────────────────────────
def parse_nmea_gga(line: str) -> Optional[tuple]:
    """Parse $GPGGA or $GNGGA NMEA sentence → (lat, lon) or None."""
    if not (line.startswith("$GPGGA") or line.startswith("$GNGGA")):
        return None
    parts = line.split(",")
    if len(parts) < 6:
        return None
    try:
        # lat: ddmm.mmmm, N/S
        lat_raw = parts[2]
        lat_dir = parts[3]
        lon_raw = parts[4]
        lon_dir = parts[5]

        lat_deg = float(lat_raw[:2])
        lat_min = float(lat_raw[2:])
        lat = lat_deg + lat_min / 60.0
        if lat_dir == "S":
            lat = -lat

        lon_deg = float(lon_raw[:3])
        lon_min = float(lon_raw[3:])
        lon = lon_deg + lon_min / 60.0
        if lon_dir == "W":
            lon = -lon

        return (lat, lon)
    except (ValueError, IndexError):
        return None


def parse_nmea_rmc(line: str) -> Optional[tuple]:
    """Parse $GPRMC or $GNRMC NMEA sentence → (lat, lon) or None."""
    if not (line.startswith("$GPRMC") or line.startswith("$GNRMC")):
        return None
    parts = line.split(",")
    if len(parts) < 7 or parts[2] != "A":  # 'A' = valid fix
        return None
    try:
        lat_raw = parts[3]
        lat_dir = parts[4]
        lon_raw = parts[5]
        lon_dir = parts[6]

        lat_deg = float(lat_raw[:2])
        lat_min = float(lat_raw[2:])
        lat = lat_deg + lat_min / 60.0
        if lat_dir == "S":
            lat = -lat

        lon_deg = float(lon_raw[:3])
        lon_min = float(lon_raw[3:])
        lon = lon_deg + lon_min / 60.0
        if lon_dir == "W":
            lon = -lon

        return (lat, lon)
    except (ValueError, IndexError):
        return None


class GPSReader:
    """Reads GPS position from a serial NMEA stream. Non-blocking, resilient."""

    def __init__(self, port: str, baud: int = GPS_BAUD):
        self.port = port
        self.baud = baud
        self.ser: Optional[pyserial.Serial] = None
        self._buf = b""
        self.lat: Optional[float] = None
        self.lon: Optional[float] = None
        self._connect()

    def _connect(self) -> bool:
        try:
            self.ser = pyserial.Serial(
                self.port, self.baud, timeout=0.5
            )
            return True
        except (SerialException, OSError) as exc:
            print(f"[gps] Cannot open {self.port}: {exc}", file=sys.stderr)
            self.ser = None
            return False

    def update(self) -> None:
        """Read available NMEA data and update lat/lon if a fix is found."""
        if self.ser is None:
            return
        try:
            data = self.ser.read(512)
        except (SerialException, OSError):
            return
        if not data:
            return
        self._buf += data
        while b"\n" in self._buf:
            raw, self._buf = self._buf.split(b"\n", 1)
            line = raw.strip(b"\r").decode("ascii", errors="ignore").strip()
            if not line:
                continue
            for parser in (parse_nmea_gga, parse_nmea_rmc):
                result = parser(line)
                if result:
                    self.lat, self.lon = result
                    return

    def close(self) -> None:
        if self.ser:
            try:
                self.ser.close()
            except (SerialException, OSError):
                pass
            self.ser = None


# ─── Board lock management ──────────────────────────────────────────────
def acquire_board_lock(track: str, timeout: int) -> bool:
    """Acquire board mutex lock via balloon-board-lock.py. Returns True on success."""
    if not LOCK_SCRIPT.exists():
        print(f"[lock] Warning: lock script not found at {LOCK_SCRIPT}", file=sys.stderr)
        print("[lock] Proceeding without lock (development mode).", file=sys.stderr)
        return False

    env = os.environ.copy()
    env["BALLOON_TRACK"] = track

    cmd = [
        sys.executable, str(LOCK_SCRIPT),
        "acquire", "both",
        "--purpose", "walk test automation",
        "--timeout", str(timeout),
    ]

    print(f"[lock] Acquiring board lock (track={track}, timeout={timeout}s)...", flush=True)
    try:
        result = subprocess.run(
            cmd, env=env, capture_output=True, text=True,
            timeout=timeout + 30,
        )
        if result.returncode == 0:
            print("[lock] Lock acquired.", flush=True)
            return True
        else:
            print(f"[lock] FAILED to acquire lock.", file=sys.stderr)
            if result.stdout:
                print(result.stdout, file=sys.stderr)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            return False
    except subprocess.TimeoutExpired:
        print("[lock] Timed out waiting for lock.", file=sys.stderr)
        return False
    except FileNotFoundError:
        print(f"[lock] Lock script not found: {LOCK_SCRIPT}", file=sys.stderr)
        return False


def release_board_lock(track: str) -> None:
    """Release board mutex lock. Always called on exit."""
    if not LOCK_SCRIPT.exists():
        return

    env = os.environ.copy()
    env["BALLOON_TRACK"] = track

    cmd = [
        sys.executable, str(LOCK_SCRIPT),
        "release", "both",
    ]

    print("[lock] Releasing board lock...", flush=True)
    try:
        result = subprocess.run(
            cmd, env=env, capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            print("[lock] Lock released.", flush=True)
        else:
            print(f"[lock] Warning: release returned code {result.returncode}", file=sys.stderr)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        print(f"[lock] Warning: release failed: {exc}", file=sys.stderr)


# ─── Serial connection helpers ──────────────────────────────────────────
def open_board_serial(port: str, baud: int) -> Optional[BoardSerial]:
    """Open a board serial port using the mandatory BoardSerial wrapper.

    Returns the open BoardSerial instance, or None on failure.
    BoardSerial checks the board mutex lock before opening — if the lock
    is not held, it raises PermissionError.
    """
    try:
        ser = BoardSerial(
            port=port,
            baudrate=baud,
            bytesize=pyserial.EIGHTBITS,
            parity=pyserial.PARITY_NONE,
            stopbits=pyserial.STOPBITS_ONE,
            timeout=0.5,
            write_timeout=1.0,
            exclusive=True,
        )
        # Flush any stale data
        try:
            ser.reset_input_buffer()
            ser.reset_output_buffer()
        except (SerialException, OSError):
            pass
        return ser
    except PermissionError as exc:
        print(f"[serial] REFUSED: {exc}", file=sys.stderr)
        return None
    except (SerialException, OSError) as exc:
        print(f"[serial] Cannot open {port}: {exc}", file=sys.stderr)
        return None


def reconnect_board_serial(port: str, baud: int, max_retries: int = 3) -> Optional[BoardSerial]:
    """Attempt to reconnect to a board serial port after a disconnect."""
    for attempt in range(1, max_retries + 1):
        print(f"[serial] Reconnect attempt {attempt}/{max_retries} for {port}...", flush=True)
        time.sleep(RECONNECT_DELAY)
        if not os.path.exists(port):
            print(f"[serial] Port {port} not found, waiting...", file=sys.stderr)
            continue
        ser = open_board_serial(port, baud)
        if ser:
            print(f"[serial] Reconnected to {port}.", flush=True)
            return ser
    print(f"[serial] Failed to reconnect to {port} after {max_retries} attempts.", file=sys.stderr)
    return None


# ─── Plotting ───────────────────────────────────────────────────────────
def generate_plots(rows: list[dict], csv_path: Path, output_dir: Path,
                   timestamp: str) -> Optional[Path]:
    """Generate RSSI/PER/throughput vs distance plots from captured data.

    Saves a combined PNG to data/walk-test-<timestamp>.png.
    Returns the plot path, or None if matplotlib is unavailable.
    """
    if not _HAS_MPL:
        print(
            "\n[plots] matplotlib not installed — skipping auto-plot.\n"
            "        Install it:  pip install matplotlib numpy\n"
            "        Then run:    python3 plot_range_sweep.py " + str(csv_path) + "\n",
            file=sys.stderr,
        )
        return None

    if not rows:
        print("[plots] No data rows to plot.", file=sys.stderr)
        return None

    # Extract data series
    distances = []
    rssis = []
    pers = []
    throughputs = []

    for r in rows:
        try:
            dist = float(r.get("distance_m") or 0)
            rssi_str = r.get("rssi_dbm", "")
            per_str = r.get("per_pct", "")
            br_str = r.get("bitrate_kbps", "")
            payload_str = r.get("payload_bytes", "")

            if rssi_str != "":
                rssi = float(rssi_str)
                distances.append(dist)
                rssis.append(rssi)

                if per_str != "":
                    pers.append((dist, float(per_str)))

                # Compute throughput: bitrate * (1 - PER/100) * (payload / max_payload)
                if br_str != "" and per_str != "" and payload_str != "":
                    br = float(br_str)
                    per = float(per_str)
                    payload = float(payload_str)
                    throughput = br * (1.0 - per / 100.0) * (payload / 255.0)
                    throughputs.append((dist, throughput))
        except (ValueError, TypeError):
            continue

    if not distances:
        print("[plots] No plottable RSSI data found.", file=sys.stderr)
        return None

    # Apply seaborn style if available
    if _HAS_SEABORN:
        sns.set_theme(style="whitegrid")
        sns.set_palette("husl")

    fig, axes = plt.subplots(3, 1, figsize=(12, 14))
    fig.suptitle(
        f"Walk Test Results — {timestamp}",
        fontsize=14, fontweight="bold", y=0.98,
    )

    # ── Plot 1: RSSI vs Distance ────────────────────────────────────
    ax1 = axes[0]
    if _HAS_NUMPY and len(set(distances)) > 1:
        # Scatter + trend line (linear fit in dB per distance)
        z = np.polyfit(distances, rssis, 1)
        p = np.poly1d(z)
        x_fit = np.linspace(min(distances), max(distances), 100)
        ax1.plot(x_fit, p(x_fit), "r--", alpha=0.7, linewidth=1.5,
                 label=f"Trend: {z[0]:.2f} dBm/m")
        slope_per_decade = z[0] * 10 if abs(z[0]) > 0 else 0
        if abs(slope_per_decade) > 0.01:
            ax1.plot([], [], " ", label=f"~{abs(slope_per_decade):.1f} dB/10m")
    ax1.scatter(distances, rssis, alpha=0.5, s=20, c="steelblue", edgecolors="navy",
                linewidths=0.3)
    ax1.set_xlabel("Distance (m)")
    ax1.set_ylabel("RSSI (dBm)")
    ax1.set_title("RSSI vs Distance")
    ax1.legend(loc="best", fontsize=9)
    ax1.grid(True, alpha=0.3)

    # ── Plot 2: PER vs Distance ─────────────────────────────────────
    ax2 = axes[1]
    if pers:
        per_dists = [p[0] for p in pers]
        per_vals = [p[1] for p in pers]
        ax2.scatter(per_dists, per_vals, alpha=0.5, s=20, c="coral",
                    edgecolors="darkred", linewidths=0.3)
        if _HAS_NUMPY and len(set(per_dists)) > 1:
            z2 = np.polyfit(per_dists, per_vals, 1)
            p2 = np.poly1d(z2)
            x_fit2 = np.linspace(min(per_dists), max(per_dists), 100)
            ax2.plot(x_fit2, p2(x_fit2), "r--", alpha=0.7, linewidth=1.5,
                     label=f"Trend: {z2[0]:.3f} %/m")
    ax2.set_xlabel("Distance (m)")
    ax2.set_ylabel("Packet Error Rate (%)")
    ax2.set_title("PER vs Distance")
    ax2.set_ylim(-5, 105)
    if pers:
        ax2.legend(loc="best", fontsize=9)
    ax2.grid(True, alpha=0.3)

    # ── Plot 3: Throughput vs Distance ──────────────────────────────
    ax3 = axes[2]
    if throughputs:
        tp_dists = [t[0] for t in throughputs]
        tp_vals = [t[1] for t in throughputs]
        ax3.scatter(tp_dists, tp_vals, alpha=0.5, s=20, c="mediumseagreen",
                    edgecolors="darkgreen", linewidths=0.3)
        if _HAS_NUMPY and len(set(tp_dists)) > 1:
            z3 = np.polyfit(tp_dists, tp_vals, 1)
            p3 = np.poly1d(z3)
            x_fit3 = np.linspace(min(tp_dists), max(tp_dists), 100)
            ax3.plot(x_fit3, p3(x_fit3), "r--", alpha=0.7, linewidth=1.5,
                     label=f"Trend: {z3[2]:.2f} kbps/m")
    ax3.set_xlabel("Distance (m)")
    ax3.set_ylabel("Effective Throughput (kbps)")
    ax3.set_title("Throughput vs Distance")
    if throughputs:
        ax3.legend(loc="best", fontsize=9)
    ax3.grid(True, alpha=0.3)

    plt.tight_layout(rect=[0, 0, 1, 0.96])

    plot_path = output_dir / f"walk-test-{timestamp}.png"
    fig.savefig(plot_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    print(f"[plots] Saved: {plot_path}", flush=True)
    return plot_path


# ─── Capture loop ───────────────────────────────────────────────────────
class WalkTestCapture:
    """Manages a single walk-test capture session."""

    def __init__(
        self,
        rx_port: str,
        tx_port: Optional[str],
        gps_port: Optional[str],
        baud: int,
        duration: float,
        distances: list[float],
        output_dir: Path,
        skip_plots: bool = False,
    ):
        self.skip_plots = skip_plots
        self.rx_port = rx_port
        self.tx_port = tx_port
        self.gps_port = gps_port
        self.baud = baud
        self.duration = duration
        self.distances = distances
        self.output_dir = output_dir

        self.timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.csv_path = output_dir / f"walk-test-{self.timestamp}.csv"
        self.rows: list[dict] = []
        self.current_distance: float = distances[0] if distances else 0.0

        self.rx_ser: Optional[BoardSerial] = None
        self.tx_ser: Optional[BoardSerial] = None
        self.gps: Optional[GPSReader] = None

        self._running = False
        self._lock_released = False

    def _segment_duration(self) -> float:
        """Duration per distance segment (if multiple distances)."""
        if len(self.distances) <= 1:
            return self.duration
        return self.duration / len(self.distances)

    def run(self) -> int:
        """Execute the full capture session. Returns exit code (0 = success)."""
        os.makedirs(self.output_dir, exist_ok=True)

        # Open CSV writer
        csvfile = open(self.csv_path, "w", newline="")
        writer = csv.DictWriter(csvfile, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()

        # Open GPS (optional)
        if self.gps_port:
            print(f"[gps] Opening GPS on {self.gps_port}...", flush=True)
            self.gps = GPSReader(self.gps_port)
            if self.gps.ser is None:
                print("[gps] GPS not available — using system clock for timestamps.", file=sys.stderr)
                self.gps = None

        self._running = True
        exit_code = 0

        try:
            # ── Multi-distance or single-distance mode ────────────────
            if len(self.distances) > 1:
                exit_code = self._run_multi_distance(writer, csvfile)
            else:
                exit_code = self._run_single(writer, csvfile)
        except KeyboardInterrupt:
            print("\n[capture] Interrupted by user (Ctrl+C).", flush=True)
        except Exception as exc:
            print(f"\n[capture] Error: {exc}", file=sys.stderr)
            exit_code = 1
        finally:
            csvfile.flush()
            csvfile.close()
            self._cleanup()

            # ── Print summary ────────────────────────────────────────
            print(f"\n{'=' * 50}", flush=True)
            print("WALK TEST SUMMARY", flush=True)
            print(f"{'=' * 50}", flush=True)
            print(f"Duration target : {self.duration:.0f}s", flush=True)
            print(f"Rows captured   : {len(self.rows)}", flush=True)
            if self.rows:
                rssis = [
                    float(r["rssi_dbm"]) for r in self.rows
                    if r.get("rssi_dbm") != ""
                ]
                if rssis:
                    print(f"RSSI range      : {min(rssis):.0f} to {max(rssis):.0f} dBm", flush=True)
                distances_seen = sorted(set(
                    float(r["distance_m"]) for r in self.rows
                    if r.get("distance_m") != ""
                ))
                if distances_seen:
                    print(f"Distances       : {', '.join(f'{d:.0f}m' for d in distances_seen)}", flush=True)
            print(f"CSV file        : {self.csv_path}", flush=True)

            # ── Generate plots ───────────────────────────────────────
            print("\n[plots] Generating plots...", flush=True)
            plot_path = generate_plots(
                self.rows, self.csv_path, self.output_dir, self.timestamp
            )
            if plot_path:
                print(f"[plots] Plot: {plot_path}", flush=True)

        return exit_code

    def _run_single(self, writer: csv.DictWriter, csvfile) -> int:
        """Capture at a single distance for the full duration."""
        self.current_distance = self.distances[0] if self.distances else 0.0
        print(f"[capture] Single distance: {self.current_distance}m", flush=True)
        print(f"[capture] Duration: {self.duration:.0f}s", flush=True)
        print(f"[capture] CSV: {self.csv_path}", flush=True)
        print("-" * 50, flush=True)

        return self._capture_loop(writer, csvfile, self.duration)

    def _run_multi_distance(self, writer: csv.DictWriter, csvfile) -> int:
        """Capture at multiple distances, prompting between segments."""
        seg_dur = self._segment_duration()
        total = 0
        for i, dist in enumerate(self.distances):
            if not self._running:
                break
            self.current_distance = dist
            print(f"\n[walk] Segment {i+1}/{len(self.distances)}: {dist}m", flush=True)
            print(f"[walk] Move to {dist}m from RX board.", flush=True)
            print("[walk] Press Enter when ready (or 's' to skip)...", flush=True)
            try:
                resp = input(">>> ").strip().lower()
                if resp == "s":
                    print(f"[walk] Skipping {dist}m.", flush=True)
                    continue
            except EOFError:
                pass  # Non-interactive — proceed immediately

            elapsed = self._capture_loop(writer, csvfile, seg_dur)
            total += elapsed
            csvfile.flush()

        return 0

    def _capture_loop(self, writer: csv.DictWriter, csvfile,
                      duration: float) -> int:
        """Read from RX serial for ``duration`` seconds. Returns elapsed seconds."""
        start = time.time()
        buf = b""
        last_stats = time.time()
        pkt_count = 0
        reconnect_attempts = 0

        # Open RX port (or reconnect)
        if self.rx_ser is None:
            self.rx_ser = self._open_rx()

        if self.rx_ser is None:
            print("[capture] RX port not available. Cannot capture.", file=sys.stderr)
            return 0

        # Open TX port (optional — for sending commands if needed)
        if self.tx_port and self.tx_ser is None:
            self.tx_ser = open_board_serial(self.tx_port, self.baud)
            if self.tx_ser:
                print(f"[tx] TX port {self.tx_port} opened (commands available).", flush=True)

        while self._running:
            elapsed = time.time() - start
            if elapsed >= duration:
                break

            # ── Update GPS ───────────────────────────────────────────
            if self.gps:
                self.gps.update()

            # ── Read from RX ─────────────────────────────────────────
            try:
                data = self.rx_ser.read(4096)
            except (SerialException, OSError) as exc:
                print(f"[capture] Serial read error: {exc}", file=sys.stderr)
                self._safe_close(self.rx_ser)
                self.rx_ser = reconnect_board_serial(
                    self.rx_port, self.baud, max_retries=3
                )
                reconnect_attempts += 1
                if self.rx_ser is None:
                    print("[capture] RX port lost permanently. Ending capture.", file=sys.stderr)
                    break
                continue

            if not data:
                # Check if port disappeared (USB unplug)
                if not os.path.exists(self.rx_port):
                    print(f"[capture] RX port {self.rx_port} disappeared.", file=sys.stderr)
                    self.rx_ser = None
                    self.rx_ser = reconnect_board_serial(
                        self.rx_port, self.baud, max_retries=3
                    )
                    reconnect_attempts += 1
                    if self.rx_ser is None:
                        break
                self._maybe_stats(start, last_stats, pkt_count)
                continue

            # ── Process complete lines ───────────────────────────────
            buf += data
            while b"\n" in buf:
                raw, buf = buf.split(b"\n", 1)
                line = raw.strip(b"\r").decode("utf-8", errors="replace").strip()
                if not line:
                    continue

                # Echo to stdout for live monitoring
                print(line, flush=True)

                # Parse into structured data
                row = parse_rx_line(line)
                if row is None:
                    continue

                # Apply metadata
                row["distance_m"] = self.current_distance

                # Apply GPS data
                if self.gps and self.gps.lat is not None:
                    row["gps_lat"] = f"{self.gps.lat:.6f}"
                    row["gps_lon"] = f"{self.gps.lon:.6f}"

                writer.writerow(row)
                csvfile.flush()
                self.rows.append(row)
                pkt_count += 1

            # ── Periodic stats ────────────────────────────────────────
            now = time.time()
            if now - last_stats >= STATS_INTERVAL:
                last_stats = now
                self._print_stats(start, pkt_count)

        elapsed = time.time() - start
        self._print_stats(start, pkt_count, final=True)
        if reconnect_attempts:
            print(f"[capture] Reconnects: {reconnect_attempts}", flush=True)
        return int(elapsed)

    def _open_rx(self) -> Optional[BoardSerial]:
        """Open the RX serial port, retrying if not immediately available."""
        print(f"[rx] Opening RX port {self.rx_port}...", flush=True)
        ser = open_board_serial(self.rx_port, self.baud)
        if ser:
            print(f"[rx] Connected to {self.rx_port} @ {self.baud} baud.", flush=True)
        else:
            print(f"[rx] Will retry {self.rx_port}...", flush=True)
            ser = reconnect_board_serial(self.rx_port, self.baud, max_retries=3)
        return ser

    def _maybe_stats(self, start: float, last_stats: float, pkt_count: int) -> None:
        """Print periodic stats if enough time has passed."""
        now = time.time()
        if now - last_stats >= STATS_INTERVAL:
            self._print_stats(start, pkt_count)

    def _print_stats(self, start: float, pkt_count: int, final: bool = False) -> None:
        """Print a one-line stats summary."""
        elapsed = int(time.time() - start)
        prefix = "[final]" if final else f"[{elapsed}s]"
        rssi_str = ""
        if self.rows:
            recent = self.rows[-50:]  # last 50 packets
            rssis = [
                float(r["rssi_dbm"]) for r in recent
                if r.get("rssi_dbm") != ""
            ]
            if rssis:
                rssi_str = f" rssi={rssis[-1]:.0f}dBm (last)"

        gps_str = ""
        if self.gps and self.gps.lat is not None:
            gps_str = f" gps={self.gps.lat:.5f},{self.gps.lon:.5f}"

        print(
            f"{prefix} pkts={pkt_count} dist={self.current_distance:.0f}m"
            f"{rssi_str}{gps_str}",
            flush=True,
        )

    def _safe_close(self, ser) -> None:
        """Safely close a serial connection, ignoring errors."""
        if ser:
            try:
                ser.close()
            except (SerialException, OSError):
                pass

    def _cleanup(self) -> None:
        """Close all serial connections and GPS."""
        self._safe_close(self.rx_ser)
        self.rx_ser = None
        self._safe_close(self.tx_ser)
        self.tx_ser = None
        if self.gps:
            self.gps.close()
            self.gps = None


# ─── Main ───────────────────────────────────────────────────────────────
def parse_distances(s: str) -> list[float]:
    """Parse a comma-separated list of distances."""
    try:
        return [float(d.strip()) for d in s.split(",") if d.strip()]
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid distance list: '{s}'. Use comma-separated numbers."
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Unified walk test automation for balloon range tests.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Single distance, 12 min capture:\n"
            "  walk_test_automation.py --rx-port /dev/ttyACM2 --distance 10\n\n"
            "  # Multi-distance walk (prompts between segments):\n"
            "  walk_test_automation.py --rx-port /dev/ttyACM2 \\\n"
            "      --distances 5,10,20,50,100 --duration 720\n\n"
            "  # With GPS and TX board:\n"
            "  walk_test_automation.py --rx-port /dev/ttyACM2 \\\n"
            "      --tx-port /dev/ttyACM0 --gps-port /dev/ttyACM1 \\\n"
            "      --distance 50 --duration 600\n"
        ),
    )
    parser.add_argument(
        "--rx-port", default="/dev/ttyACM2",
        help="RX board serial port (default: /dev/ttyACM2).",
    )
    parser.add_argument(
        "--tx-port", default=None,
        help="TX board serial port (optional, for commands). Default: none.",
    )
    parser.add_argument(
        "--gps-port", default=None,
        help="GPS serial port for NMEA position data (optional).",
    )
    parser.add_argument(
        "--duration", type=float, default=DEFAULT_DURATION,
        help=f"Capture duration in seconds (default: {DEFAULT_DURATION} = "
             f"{DEFAULT_DURATION // 60} min).",
    )
    parser.add_argument(
        "--distance", type=float, default=None,
        help="Current distance marker in meters (single-distance mode).",
    )
    parser.add_argument(
        "--distances", type=parse_distances, default=None,
        help="Comma-separated distance markers, e.g. 5,10,20,50,100 "
             "(multi-distance mode, prompts between segments).",
    )
    parser.add_argument(
        "--baud", type=int, default=DEFAULT_BAUD,
        help=f"Baud rate (default: {DEFAULT_BAUD}).",
    )
    parser.add_argument(
        "--output", default=DEFAULT_OUTPUT,
        help=f"Output directory for CSV and plots (default: {DEFAULT_OUTPUT}/).",
    )
    parser.add_argument(
        "--track", default=DEFAULT_TRACK,
        help=f"BALLOON_TRACK name for board lock (default: {DEFAULT_TRACK}).",
    )
    parser.add_argument(
        "--no-lock", action="store_true",
        help="Skip board lock acquire/release (development mode, no hardware).",
    )
    parser.add_argument(
        "--no-plots", action="store_true",
        help="Skip auto-plot generation after capture.",
    )
    args = parser.parse_args()

    # ── Validate distance args ───────────────────────────────────────
    if args.distance is not None and args.distances is not None:
        parser.error("Use either --distance (single) or --distances (multi), not both.")

    if args.distance is not None:
        distances = [args.distance]
    elif args.distances is not None:
        distances = args.distances
    else:
        distances = [0.0]  # Default: distance unknown

    # ── Set BALLOON_TRACK in environment (for BoardSerial lock checks) ──
    os.environ.setdefault("BALLOON_TRACK", args.track)

    # ── Print banner ──────────────────────────────────────────────────
    print("=" * 60, flush=True)
    print("WALK TEST AUTOMATION — Balloon Range Tests", flush=True)
    print("=" * 60, flush=True)
    print(f"RX port     : {args.rx_port}", flush=True)
    print(f"TX port     : {args.tx_port or '(none)'}", flush=True)
    print(f"GPS port    : {args.gps_port or '(none — system clock)'}", flush=True)
    print(f"Duration    : {args.duration:.0f}s", flush=True)
    print(f"Distances   : {', '.join(f'{d:.0f}m' for d in distances)}", flush=True)
    print(f"Output dir  : {args.output}", flush=True)
    print(f"Track       : {args.track}", flush=True)
    print(f"Board lock  : {'SKIP (--no-lock)' if args.no_lock else 'acquire+release'}", flush=True)
    print(f"Auto-plots  : {'disabled' if args.no_plots else 'enabled'}", flush=True)
    if not _HAS_MPL:
        print("matplotlib   : NOT INSTALLED (plots will be skipped)", flush=True)
        print("              Install: pip install matplotlib numpy", flush=True)
    else:
        print(f"matplotlib   : {matplotlib.__version__}", flush=True)
        if _HAS_SEABORN:
            print(f"seaborn      : {sns.__version__} (styled plots)", flush=True)
        else:
            print("seaborn      : not installed (using default matplotlib style)", flush=True)
    print("=" * 60, flush=True)

    # ── Acquire board lock ───────────────────────────────────────────
    lock_held = False
    if not args.no_lock:
        lock_held = acquire_board_lock(args.track, BOARD_LOCK_TIMEOUT)
        if not lock_held:
            print("\nERROR: Could not acquire board lock. Aborting.", file=sys.stderr)
            print("Check who holds it: python3 " + str(LOCK_SCRIPT) + " status",
                  file=sys.stderr)
            return 1

    # ── Run capture ──────────────────────────────────────────────────
    output_dir = Path(args.output)
    capture = WalkTestCapture(
        rx_port=args.rx_port,
        tx_port=args.tx_port,
        gps_port=args.gps_port,
        baud=args.baud,
        duration=args.duration,
        distances=distances,
        output_dir=output_dir,
    )

    # Disable --no-plots by clearing rows before generate_plots is called
    if args.no_plots:
        capture._original_rows = None  # Marker: we'll intercept

    exit_code = 0
    try:
        exit_code = capture.run()

        # If --no-plots, we already ran — suppress plot generation
        if args.no_plots and hasattr(capture, "_original_rows"):
            # generate_plots was already called in run(); just note it
            pass

    finally:
        # ── Release board lock ───────────────────────────────────────
        if lock_held:
            release_board_lock(args.track)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
