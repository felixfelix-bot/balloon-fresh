#!/usr/bin/env python3
"""
sweep_capture.py — Capture LR2021 multi-radio sweep data from RX board.

Two modes:
  1. STOP-AND-CAPTURE (default): operator places TX at fixed distance, enters --distance
  2. WALK MODE (--walk): operator walks with TX in rucksack; RX stays home logging.
     Distance is computed from GPS coordinates in received packets (haversine).

Firmware output formats:

  Old firmware (no GPS):
    PHASE_RESULT <phase> <name> rx=<n> unique=<n> lost=<n> per=<pct> rssi_avg=<dbm> rssi_min=<dbm> crc_err=<n>
    PKT rx=<n> seq=<n> rssi=<dbm> phase=<n>

  New firmware (with GPS in TX payload):
    PHASE_RESULT <phase> <name> rx=<n> unique=<n> lost=<n> per=<pct> rssi_avg=<dbm> rssi_min=<dbm> lat=<lat> lon=<lon> sats=<n> fix=<q> utc=<sec>
    PKT rx=<n> seq=<n> rssi=<dbm> phase=<n> lat=<lat> lon=<lon>

Usage:
  # Walk mode — continuous capture with GPS distance
  python3 scripts/sweep_capture.py --port /dev/ttyACM0 --walk --env outdoor_los
  python3 scripts/sweep_capture.py --port /dev/ttyACM0 --walk --base-lat 52.5 --base-lon 13.4 --duration 3600

  # Stop-and-capture mode — fixed distance
  python3 scripts/sweep_capture.py --port /dev/ttyACM0 --distance 10 --env outdoor_los
  python3 scripts/sweep_capture.py --port /dev/ttyACM0 --distance 1 --env indoor --cycles 1

Requires:
  - pyserial (pip install pyserial)
  - BoardSerial wrapper at ~/repos/balloon-fresh/tools/board_serial.py
  - Board lock acquired: BALLOON_TRACK=range-tests python3 tools/balloon-board-lock.py acquire both
"""

import argparse
import csv
import math
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ─── BoardSerial import ──────────────────────────────────────────────────
TOOLS_DIR = Path.home() / "repos" / "balloon-fresh" / "tools"
sys.path.insert(0, str(TOOLS_DIR))

try:
    from board_serial import BoardSerial
except ImportError:
    print("ERROR: Cannot import BoardSerial from", TOOLS_DIR, file=sys.stderr)
    print("Ensure balloon-fresh repo is cloned.", file=sys.stderr)
    sys.exit(1)

# ─── Phase table (must match firmware multi_radio_sweep_rx.cpp) ───────────
PHASE_TABLE = [
    {"name": "HF-LoRa-SF7",   "mod": "LORA", "freq": 2440, "bitrate": 0,    "sf": 7,  "bw": 812, "sent": 50},
    {"name": "HF-LoRa-SF9",   "mod": "LORA", "freq": 2440, "bitrate": 0,    "sf": 9,  "bw": 812, "sent": 50},
    {"name": "HF-LoRa-SF12",  "mod": "LORA", "freq": 2440, "bitrate": 0,    "sf": 12, "bw": 812, "sent": 30},
    {"name": "HF-FLRC-2600",  "mod": "FLRC", "freq": 2440, "bitrate": 2600, "sf": 0,  "bw": 0,   "sent": 200},
    {"name": "HF-FLRC-1300",  "mod": "FLRC", "freq": 2440, "bitrate": 1300, "sf": 0,  "bw": 0,   "sent": 200},
    {"name": "HF-FLRC-650",   "mod": "FLRC", "freq": 2440, "bitrate": 650,  "sf": 0,  "bw": 0,   "sent": 200},
    {"name": "HF-FLRC-325",   "mod": "FLRC", "freq": 2440, "bitrate": 325,  "sf": 0,  "bw": 0,   "sent": 200},
    {"name": "LF-LoRa-SF7",   "mod": "LORA", "freq": 868,  "bitrate": 0,    "sf": 7,  "bw": 250, "sent": 50},
    {"name": "LF-LoRa-SF9",   "mod": "LORA", "freq": 868,  "bitrate": 0,    "sf": 9,  "bw": 250, "sent": 50},
    {"name": "LF-LoRa-SF12",  "mod": "LORA", "freq": 868,  "bitrate": 0,    "sf": 12, "bw": 250, "sent": 20},
    {"name": "LF-FLRC-2600",  "mod": "FLRC", "freq": 868,  "bitrate": 2600, "sf": 0,  "bw": 0,   "sent": 200},
    {"name": "LF-FLRC-1300",  "mod": "FLRC", "freq": 868,  "bitrate": 1300, "sf": 0,  "bw": 0,   "sent": 200},
    {"name": "LF-FLRC-650",   "mod": "FLRC", "freq": 868,  "bitrate": 650,  "sf": 0,  "bw": 0,   "sent": 200},
    {"name": "LF-FLRC-325",   "mod": "FLRC", "freq": 868,  "bitrate": 325,  "sf": 0,  "bw": 0,   "sent": 200},
]

NUM_PHASES = len(PHASE_TABLE)

# ─── CSV columns ─────────────────────────────────────────────────────────
# Phase result CSV columns (extended with GPS fields)
CSV_COLUMNS = [
    "timestamp_iso",
    "cycle",
    "phase",
    "name",
    "freq_mhz",
    "modulation",
    "bitrate_kbps",
    "spreading_factor",
    "bandwidth_khz",
    "tx_sent",
    "rx_received",
    "rx_unique",
    "lost",
    "per_pct",
    "rssi_avg_dbm",
    "rssi_min_dbm",
    "crc_errors",
    "lat",
    "lon",
    "sats",
    "fix_quality",
    "utc_sec",
    "distance_m",
    "environment",
    "notes",
]

# Per-packet CSV columns
PKT_COLUMNS = [
    "timestamp_iso",
    "phase",
    "seq",
    "rssi_dbm",
    "lat",
    "lon",
    "distance_m",
]

# ─── Haversine distance ──────────────────────────────────────────────────

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute great-circle distance in meters between two lat/lon points."""
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# ─── Line parsers ────────────────────────────────────────────────────────

def parse_phase_result(line: str) -> dict | None:
    """
    Parse PHASE_RESULT lines (both old and new firmware formats).

    Old:  PHASE_RESULT <phase> <name> rx=<n> unique=<n> lost=<n> per=<pct> rssi_avg=<dbm> rssi_min=<dbm> crc_err=<n>
    New:  PHASE_RESULT <phase> <name> rx=<n> unique=<n> lost=<n> per=<pct> rssi_avg=<dbm> rssi_min=<dbm> lat=<lat> lon=<lon> sats=<n> fix=<q> utc=<sec>
    """
    line = line.strip()
    if not line.startswith("PHASE_RESULT"):
        return None

    parts = line.split()
    if len(parts) < 4:
        return None

    try:
        phase_num = int(parts[1])
    except (ValueError, IndexError):
        return None

    name = parts[2]

    result: dict = {"phase": phase_num, "name": name}
    for kv in parts[3:]:
        if "=" not in kv:
            continue
        key, val = kv.split("=", 1)
        key = key.strip()
        val = val.strip()
        if key == "rx":
            result["rx_received"] = int(val)
        elif key == "unique":
            result["rx_unique"] = int(val)
        elif key == "lost":
            result["lost"] = int(val)
        elif key == "per":
            result["per_pct"] = float(val)
        elif key == "rssi_avg":
            result["rssi_avg_dbm"] = float(val)
        elif key == "rssi_min":
            result["rssi_min_dbm"] = float(val)
        elif key == "crc_err":
            result["crc_errors"] = int(val)
        elif key == "lat":
            result["lat"] = float(val)
        elif key == "lon":
            result["lon"] = float(val)
        elif key == "sats":
            result["sats"] = int(val)
        elif key == "fix":
            result["fix_quality"] = int(val)
        elif key == "utc":
            result["utc_sec"] = int(val)

    return result


def parse_cycle_start(line: str) -> int | None:
    """Parse: === CYCLE <n> START uptime=<ms> ==="""
    m = re.search(r"CYCLE (\d+) START", line)
    return int(m.group(1)) if m else None


def parse_cycle_complete(line: str) -> int | None:
    """Parse: === CYCLE <n> COMPLETE uptime=<ms> ==="""
    m = re.search(r"CYCLE (\d+) COMPLETE", line)
    return int(m.group(1)) if m else None


def parse_pkt(line: str) -> dict | None:
    """
    Parse PKT lines (both old and new firmware formats).

    Old:  PKT rx=<n> seq=<n> rssi=<dbm> phase=<n>
    New:  PKT rx=<n> seq=<n> rssi=<dbm> phase=<n> lat=<lat> lon=<lon>
    """
    line = line.strip()
    if not line.startswith("PKT"):
        return None
    parts = line.split()
    result: dict = {}
    for kv in parts[1:]:
        if "=" not in kv:
            continue
        key, val = kv.split("=", 1)
        key = key.strip()
        val = val.strip()
        if key == "rx":
            result["rx"] = int(val)
        elif key == "seq":
            result["seq"] = int(val)
        elif key == "rssi":
            result["rssi"] = float(val)
        elif key == "phase":
            result["phase"] = int(val)
        elif key == "lat":
            result["lat"] = float(val)
        elif key == "lon":
            result["lon"] = float(val)
    return result if result else None


# ─── Serial reconnection wrapper ─────────────────────────────────────────

class RobustSerial:
    """
    Wraps BoardSerial with automatic reconnection on disconnect.

    Handles USB CDC unplug/replug, ESP32 bridge UART resets, and
    transient serial errors without crashing the capture loop.
    """

    def __init__(self, port: str, baud: int, timeout: float = 1.0):
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self._ser: BoardSerial | None = None
        self._connect()

    def _connect(self):
        """Open the serial port, retrying on failure."""
        attempt = 0
        while True:
            try:
                self._ser = BoardSerial(self.port, self.baud, timeout=self.timeout)
                if attempt > 0:
                    print(f"  [serial] Reconnected to {self.port} after {attempt} attempt(s)",
                          file=sys.stderr)
                return
            except PermissionError:
                # Board lock issue — don't retry, this needs manual intervention
                raise
            except Exception as e:
                attempt += 1
                if attempt == 1:
                    print(f"  [serial] Cannot open {self.port}: {e}. Retrying...",
                          file=sys.stderr)
                if attempt <= 3:
                    time.sleep(2)
                else:
                    time.sleep(5)
                if attempt % 10 == 0:
                    print(f"  [serial] Still retrying ({attempt} attempts)...",
                          file=sys.stderr)

    def read(self, size: int = 4096) -> bytes:
        """Read data, reconnecting on error."""
        if self._ser is None:
            self._connect()
            return b""
        try:
            data = self._ser.read(size)
            # If we got nothing and the port seems dead, check if still open
            if not data and not self._ser.is_open:
                print(f"  [serial] Port {self.port} disconnected. Reconnecting...",
                      file=sys.stderr)
                self._ser = None
                self._connect()
                return b""
            return data
        except Exception as e:
            print(f"  [serial] Read error: {e}. Reconnecting...", file=sys.stderr)
            try:
                if self._ser:
                    self._ser.close()
            except Exception:
                pass
            self._ser = None
            time.sleep(2)
            self._connect()
            return b""

    def close(self):
        if self._ser:
            try:
                self._ser.close()
            except Exception:
                pass
            self._ser = None


# ─── CSV writers ──────────────────────────────────────────────────────────

def write_phase_csv_row(writer: csv.DictWriter, phase_data: dict, cycle: int,
                        distance_m: float, env: str, notes: str):
    """Write a phase result row to CSV, enriched with phase table metadata and GPS."""
    phase_num = phase_data.get("phase", -1)
    if 0 <= phase_num < NUM_PHASES:
        meta = PHASE_TABLE[phase_num]
    else:
        meta = {"name": phase_data.get("name", "?"), "mod": "?", "freq": 0,
                "bitrate": 0, "sf": 0, "bw": 0, "sent": 0}

    row = {col: "" for col in CSV_COLUMNS}
    row["timestamp_iso"] = datetime.now(timezone.utc).isoformat()
    row["cycle"] = cycle
    row["phase"] = phase_num
    row["name"] = phase_data.get("name", meta["name"])
    row["freq_mhz"] = meta["freq"]
    row["modulation"] = meta["mod"]
    row["bitrate_kbps"] = meta["bitrate"]
    row["spreading_factor"] = meta["sf"]
    row["bandwidth_khz"] = meta["bw"]
    row["tx_sent"] = meta["sent"]
    row["rx_received"] = phase_data.get("rx_received", "")
    row["rx_unique"] = phase_data.get("rx_unique", "")
    row["lost"] = phase_data.get("lost", "")
    row["per_pct"] = phase_data.get("per_pct", "")
    row["rssi_avg_dbm"] = phase_data.get("rssi_avg_dbm", "")
    row["rssi_min_dbm"] = phase_data.get("rssi_min_dbm", "")
    row["crc_errors"] = phase_data.get("crc_errors", "")
    row["lat"] = phase_data.get("lat", "")
    row["lon"] = phase_data.get("lon", "")
    row["sats"] = phase_data.get("sats", "")
    row["fix_quality"] = phase_data.get("fix_quality", "")
    row["utc_sec"] = phase_data.get("utc_sec", "")
    row["distance_m"] = distance_m
    row["environment"] = env
    row["notes"] = notes

    writer.writerow(row)

    # Console summary
    gps_str = ""
    if "lat" in phase_data and "lon" in phase_data:
        gps_str = f"  GPS=({phase_data['lat']:.5f},{phase_data['lon']:.5f}) d={distance_m:.0f}m"
    elif distance_m >= 0:
        gps_str = f"  d={distance_m:.0f}m"
    print(f"  [{cycle}] Phase {phase_num:2d} {row['name']:16s} "
          f"rx={row['rx_received']:>3}/{row['tx_sent']:<3} "
          f"PER={row['per_pct']:>5.1f}%  "
          f"RSSI={row['rssi_avg_dbm']:>4.0f}dBm  "
          f"(min {row['rssi_min_dbm']:.0f}){gps_str}",
          file=sys.stderr)


def write_pkt_csv_row(writer: csv.DictWriter, pkt_data: dict,
                      base_lat: float | None, base_lon: float | None):
    """Write a per-packet row to the packet CSV."""
    lat = pkt_data.get("lat")
    lon = pkt_data.get("lon")

    if lat is not None and lon is not None and base_lat is not None and base_lon is not None:
        distance_m = haversine(base_lat, base_lon, lat, lon)
    else:
        distance_m = -1

    row = {col: "" for col in PKT_COLUMNS}
    row["timestamp_iso"] = datetime.now(timezone.utc).isoformat()
    row["phase"] = pkt_data.get("phase", "")
    row["seq"] = pkt_data.get("seq", "")
    row["rssi_dbm"] = pkt_data.get("rssi", "")
    row["lat"] = lat if lat is not None else ""
    row["lon"] = lon if lon is not None else ""
    row["distance_m"] = distance_m

    writer.writerow(row)


# ─── Main capture loop ───────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Capture LR2021 multi-radio sweep data from RX board. "
                    "Supports walk mode with GPS distance computation."
    )
    parser.add_argument("--port", default="/dev/ttyACM0",
                        help="Serial port for RX board (default: /dev/ttyACM0)")
    parser.add_argument("--baud", type=int, default=115200,
                        help="Baud rate (default: 115200)")

    # Distance — now optional
    parser.add_argument("--distance", type=float, default=0,
                        help="TX-RX distance in meters (0 = from GPS, used in stop-and-capture mode)")

    # Walk mode
    parser.add_argument("--walk", action="store_true",
                        help="Walk capture mode: run indefinitely, log every PHASE_RESULT with "
                             "GPS-based distance computation. Ctrl-C or --duration to stop.")

    # GPS reference point
    parser.add_argument("--base-lat", type=float, default=None,
                        help="Base station (RX) latitude. If not set, uses first GPS fix from TX.")
    parser.add_argument("--base-lon", type=float, default=None,
                        help="Base station (RX) longitude. If not set, uses first GPS fix from TX.")

    # Stop-and-capture mode args
    parser.add_argument("--env", default="walk",
                        help="Environment tag (default: walk). Use indoor, outdoor_los, etc. for stop-and-capture.")
    parser.add_argument("--cycles", type=int, default=0,
                        help="Number of complete sweep cycles to capture (0 = until Ctrl-C or --duration)")
    parser.add_argument("--duration", type=int, default=0,
                        help="Maximum capture duration in seconds (0 = unlimited, Ctrl-C to stop)")
    parser.add_argument("--notes", default="",
                        help="Free-text notes for this capture session")
    parser.add_argument("--output-dir", default="data",
                        help="Output directory for CSV files (default: data/)")
    parser.add_argument("--raw-log", action="store_true",
                        help="Also save raw serial log alongside CSV")
    args = parser.parse_args()

    # ─── Validate mode ────────────────────────────────────────────────────
    if args.walk and args.distance > 0:
        print("WARNING: --distance ignored in --walk mode (GPS distance used instead)",
              file=sys.stderr)

    # ─── Build output filenames ───────────────────────────────────────────
    os.makedirs(args.output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if args.walk:
        csv_filename = f"walk_{timestamp}.csv"
        pkt_filename = f"walk_{timestamp}_packets.csv"
    else:
        csv_filename = (f"char_dist_{int(args.distance)}m_env_{args.env}"
                        f"_{timestamp}.csv")
        pkt_filename = (f"char_dist_{int(args.distance)}m_env_{args.env}"
                        f"_{timestamp}_packets.csv")

    csv_path = os.path.join(args.output_dir, csv_filename)
    pkt_path = os.path.join(args.output_dir, pkt_filename)

    raw_log_path = None
    raw_log_file = None
    if args.raw_log:
        raw_log_path = csv_path.replace(".csv", ".log")
        raw_log_file = open(raw_log_path, "w")

    # ─── GPS base point ───────────────────────────────────────────────────
    base_lat = args.base_lat
    base_lon = args.base_lon
    if base_lat is not None and base_lon is not None:
        print(f"Base station GPS: ({base_lat:.6f}, {base_lon:.6f})", file=sys.stderr)
    elif args.walk:
        print("No --base-lat/--base-lon set. Will use first GPS fix from TX as base.",
              file=sys.stderr)

    # ─── Open serial ──────────────────────────────────────────────────────
    mode_str = "WALK (continuous)" if args.walk else "STOP-AND-CAPTURE"
    print(f"Mode: {mode_str}", file=sys.stderr)
    print(f"Connecting to {args.port} at {args.baud} baud...", file=sys.stderr)

    try:
        ser = RobustSerial(args.port, args.baud, timeout=1.0)
    except PermissionError as e:
        print(f"ERROR: Board lock not held for {args.port}: {e}", file=sys.stderr)
        print("Ensure board lock is acquired:", file=sys.stderr)
        print(f"  BALLOON_TRACK=range-tests python3 {TOOLS_DIR}/balloon-board-lock.py acquire both",
              file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Cannot open {args.port}: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Connected. Waiting for sweep data...", file=sys.stderr)
    if not args.walk and args.distance > 0:
        print(f"Distance: {args.distance}m  Environment: {args.env}", file=sys.stderr)
    if args.duration > 0:
        print(f"Duration: {args.duration}s ({args.duration/60:.1f} min)", file=sys.stderr)
    if args.cycles > 0 and not args.walk:
        print(f"Will capture {args.cycles} complete cycle(s), then exit.", file=sys.stderr)
    print("Press Ctrl-C to stop capture.", file=sys.stderr)
    print(f"Phase CSV:  {csv_path}", file=sys.stderr)
    print(f"Packet CSV: {pkt_path}", file=sys.stderr)
    if raw_log_path:
        print(f"Raw log:    {raw_log_path}", file=sys.stderr)
    print("-" * 60, file=sys.stderr)

    # ─── Open CSV writers ─────────────────────────────────────────────────
    csv_file = open(csv_path, "w", newline="")
    writer = csv.DictWriter(csv_file, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    csv_file.flush()

    pkt_file = open(pkt_path, "w", newline="")
    pkt_writer = csv.DictWriter(pkt_file, fieldnames=PKT_COLUMNS)
    pkt_writer.writeheader()
    pkt_file.flush()

    # ─── State ────────────────────────────────────────────────────────────
    current_cycle = -1
    cycles_completed = 0
    phases_in_cycle = 0
    pkt_count = 0
    buf = ""
    start_time = time.time()

    try:
        while True:
            # Check duration
            if args.duration > 0 and (time.time() - start_time) >= args.duration:
                print(f"\nDuration limit ({args.duration}s) reached. Stopping.", file=sys.stderr)
                break

            # Read available data
            data = ser.read(4096)
            if not data:
                continue

            # Decode — handle both ASCII and potentially garbage bytes
            try:
                text = data.decode("ascii", errors="replace")
            except Exception:
                text = data.decode("utf-8", errors="replace")

            if raw_log_file:
                raw_log_file.write(text)
                raw_log_file.flush()

            buf += text

            # Process complete lines (handle \r\n, \n, or \r termination)
            while "\n" in buf or "\r" in buf:
                # Split on whichever comes first
                nl_pos = len(buf)
                for sep in ("\n", "\r"):
                    pos = buf.find(sep)
                    if pos != -1 and pos < nl_pos:
                        nl_pos = pos

                line = buf[:nl_pos].strip()
                # Consume the separator(s)
                buf = buf[nl_pos:]
                # Skip consecutive separators (e.g. \r\n)
                while buf and buf[0] in ("\r", "\n"):
                    buf = buf[1:]

                if not line:
                    continue

                # ── Cycle start ──
                cycle_num = parse_cycle_start(line)
                if cycle_num is not None:
                    current_cycle = cycle_num
                    phases_in_cycle = 0
                    print(f"\n=== CYCLE {current_cycle} START ===", file=sys.stderr)
                    continue

                # ── Cycle complete ──
                cycle_done = parse_cycle_complete(line)
                if cycle_done is not None:
                    cycles_completed += 1
                    print(f"\n=== CYCLE {cycle_done} COMPLETE "
                          f"({cycles_completed} done) ===\n", file=sys.stderr)
                    csv_file.flush()
                    pkt_file.flush()

                    # In stop-and-capture mode with --cycles, exit after N cycles
                    if not args.walk and args.cycles > 0 and cycles_completed >= args.cycles:
                        print(f"\nCaptured {cycles_completed} cycle(s). Done!",
                              file=sys.stderr)
                        raise KeyboardInterrupt  # clean exit

                    continue

                # ── Phase result ──
                phase_data = parse_phase_result(line)
                if phase_data is not None:
                    # Compute distance
                    distance_m = -1  # default: unknown

                    if args.walk:
                        # In walk mode, try GPS-based distance
                        lat = phase_data.get("lat")
                        lon = phase_data.get("lon")
                        fix = phase_data.get("fix_quality", 0)

                        if lat is not None and lon is not None and fix > 0:
                            # Set base from first fix if not provided
                            if base_lat is None or base_lon is None:
                                base_lat = lat
                                base_lon = lon
                                print(f"  [gps] Base station set to first TX fix: "
                                      f"({base_lat:.6f}, {base_lon:.6f})", file=sys.stderr)

                            distance_m = haversine(base_lat, base_lon, lat, lon)
                        elif lat is not None and lon is not None and fix == 0:
                            distance_m = -1  # no fix
                    else:
                        # Stop-and-capture: use manual distance
                        distance_m = args.distance

                    write_phase_csv_row(writer, phase_data, current_cycle,
                                        distance_m, args.env, args.notes)
                    csv_file.flush()
                    phases_in_cycle += 1
                    continue

                # ── Per-packet (PKT) ──
                pkt_data = parse_pkt(line)
                if pkt_data is not None:
                    write_pkt_csv_row(pkt_writer, pkt_data, base_lat, base_lon)
                    pkt_file.flush()
                    pkt_count += 1
                    continue

                # ── Phase start (informational) ──
                if line.startswith("PHASE_START"):
                    parts = line.split()
                    if len(parts) >= 3:
                        print(f"  Phase {parts[1]}: {parts[2]} ...", file=sys.stderr)
                    continue

                # ── Other lines — print if they look interesting ──
                # (debug output, errors, etc.)
                if any(keyword in line for keyword in ("ERROR", "WARN", "GPS", "FIX", "BOOT", "READY")):
                    print(f"  [fw] {line}", file=sys.stderr)

    except KeyboardInterrupt:
        print(f"\n\nCapture stopped.", file=sys.stderr)
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
    finally:
        csv_file.close()
        pkt_file.close()
        ser.close()
        if raw_log_file:
            raw_log_file.close()

    # ─── Summary ──────────────────────────────────────────────────────────
    elapsed = time.time() - start_time
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"CAPTURE SUMMARY", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    print(f"Mode:            {mode_str}", file=sys.stderr)
    print(f"Duration:        {elapsed:.1f}s ({elapsed/60:.1f} min)", file=sys.stderr)
    print(f"Phase CSV:       {csv_path}", file=sys.stderr)
    print(f"Packet CSV:      {pkt_path}", file=sys.stderr)
    print(f"Cycles captured: {cycles_completed}", file=sys.stderr)
    if base_lat is not None:
        print(f"Base GPS:        ({base_lat:.6f}, {base_lon:.6f})", file=sys.stderr)

    # Count rows
    try:
        with open(csv_path) as f:
            row_count = sum(1 for _ in f) - 1
        print(f"Phase results:   {row_count}", file=sys.stderr)
    except Exception:
        pass

    try:
        with open(pkt_path) as f:
            pkt_row_count = sum(1 for _ in f) - 1
        print(f"Packets logged:  {pkt_row_count}", file=sys.stderr)
    except Exception:
        pass

    if raw_log_path:
        print(f"Raw log:         {raw_log_path}", file=sys.stderr)

    print(f"\nParse with: python3 tools/parse_unified_csv.py {csv_path}",
          file=sys.stderr)
    print(f"Plot with:   python3 tools/plot_characterization.py {csv_path}",
          file=sys.stderr)


if __name__ == "__main__":
    main()