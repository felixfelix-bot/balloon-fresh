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
    PHASE_RESULT <phase> <name> rx=<n> unique=<n> lost=<n> per=<pct> rssi_avg=<dbm> rssi_min=<dbm> crc_err=<n> gps_lat=<lat> gps_lon=<lon> gps_sats=<n> gps_fix=<n> gps_time_delta_ms=<ms>
    PKT rx=<n> seq=<n> rssi=<dbm> phase=<n> rx_ms=<ms> tx_lat=<lat> tx_lon=<lon> sats=<n> fix=<q> utc=<sec>

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
# payload_bytes: LoRa=127, FLRC=255 (per firmware TX payload size)
# slot_ms: total phase duration in milliseconds (from firmware phase config)
# theoretical_kbps: rough air-interface maximum for comparison
#   LoRa SF7 BW812 ~6800, SF9 ~3400, SF12 ~210; FLRC as named bitrate
# header_overhead: bytes per packet not carrying useful payload
#   LoRa: 13 preamble + 5 header + 2 CRC = 20 bytes
#   FLRC: 4 preamble + 4 sync word + 2 CRC = 10 bytes
# useful_payload_bytes: payload_bytes - header_overhead
PHASE_TABLE = [
    {"name": "HF-LoRa-SF7",   "mod": "LORA", "freq": 2440, "bitrate": 0,    "sf": 7,  "bw": 812, "sent": 50,  "payload_bytes": 127, "header_overhead": 20, "useful_payload_bytes": 107, "slot_ms": 15000, "theoretical_kbps": 6800},
    {"name": "HF-LoRa-SF9",   "mod": "LORA", "freq": 2440, "bitrate": 0,    "sf": 9,  "bw": 812, "sent": 50,  "payload_bytes": 127, "header_overhead": 20, "useful_payload_bytes": 107, "slot_ms": 15000, "theoretical_kbps": 3400},
    {"name": "HF-LoRa-SF12",  "mod": "LORA", "freq": 2440, "bitrate": 0,    "sf": 12, "bw": 812, "sent": 30,  "payload_bytes": 127, "header_overhead": 20, "useful_payload_bytes": 107, "slot_ms": 30000, "theoretical_kbps": 210},
    {"name": "HF-FLRC-2600",  "mod": "FLRC", "freq": 2440, "bitrate": 2600, "sf": 0,  "bw": 0,   "sent": 200, "payload_bytes": 255, "header_overhead": 10, "useful_payload_bytes": 245, "slot_ms": 8000,  "theoretical_kbps": 2600},
    {"name": "HF-FLRC-1300",  "mod": "FLRC", "freq": 2440, "bitrate": 1300, "sf": 0,  "bw": 0,   "sent": 200, "payload_bytes": 255, "header_overhead": 10, "useful_payload_bytes": 245, "slot_ms": 8000,  "theoretical_kbps": 1300},
    {"name": "HF-FLRC-650",   "mod": "FLRC", "freq": 2440, "bitrate": 650,  "sf": 0,  "bw": 0,   "sent": 200, "payload_bytes": 255, "header_overhead": 10, "useful_payload_bytes": 245, "slot_ms": 8000,  "theoretical_kbps": 650},
    {"name": "HF-FLRC-325",   "mod": "FLRC", "freq": 2440, "bitrate": 325,  "sf": 0,  "bw": 0,   "sent": 200, "payload_bytes": 255, "header_overhead": 10, "useful_payload_bytes": 245, "slot_ms": 8000,  "theoretical_kbps": 325},
    {"name": "LF-LoRa-SF7",   "mod": "LORA", "freq": 868,  "bitrate": 0,    "sf": 7,  "bw": 250, "sent": 50,  "payload_bytes": 127, "header_overhead": 20, "useful_payload_bytes": 107, "slot_ms": 12000, "theoretical_kbps": 6800},
    {"name": "LF-LoRa-SF9",   "mod": "LORA", "freq": 868,  "bitrate": 0,    "sf": 9,  "bw": 250, "sent": 50,  "payload_bytes": 127, "header_overhead": 20, "useful_payload_bytes": 107, "slot_ms": 25000, "theoretical_kbps": 3400},
    {"name": "LF-LoRa-SF12",  "mod": "LORA", "freq": 868,  "bitrate": 0,    "sf": 12, "bw": 250, "sent": 20,  "payload_bytes": 127, "header_overhead": 20, "useful_payload_bytes": 107, "slot_ms": 60000, "theoretical_kbps": 210},
    {"name": "LF-FLRC-2600",  "mod": "FLRC", "freq": 868,  "bitrate": 2600, "sf": 0,  "bw": 0,   "sent": 200, "payload_bytes": 255, "header_overhead": 10, "useful_payload_bytes": 245, "slot_ms": 8000,  "theoretical_kbps": 2600},
    {"name": "LF-FLRC-1300",  "mod": "FLRC", "freq": 868,  "bitrate": 1300, "sf": 0,  "bw": 0,   "sent": 200, "payload_bytes": 255, "header_overhead": 10, "useful_payload_bytes": 245, "slot_ms": 8000,  "theoretical_kbps": 1300},
    {"name": "LF-FLRC-650",   "mod": "FLRC", "freq": 868,  "bitrate": 650,  "sf": 0,  "bw": 0,   "sent": 200, "payload_bytes": 255, "header_overhead": 10, "useful_payload_bytes": 245, "slot_ms": 8000,  "theoretical_kbps": 650},
    {"name": "LF-FLRC-325",   "mod": "FLRC", "freq": 868,  "bitrate": 325,  "sf": 0,  "bw": 0,   "sent": 200, "payload_bytes": 255, "header_overhead": 10, "useful_payload_bytes": 245, "slot_ms": 8000,  "theoretical_kbps": 325},
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
    "throughput_kbps",
    "goodput_kbps",
    "goodput_efficiency_pct",
    "effective_throughput_kbps",
    "theoretical_max_kbps",
    "throughput_efficiency_pct",
    "gps_time_delta_ms",
    "environment",
    "notes",
]

# Per-packet CSV columns
PKT_COLUMNS = [
    "timestamp_iso",
    "phase",
    "seq",
    "rssi_dbm",
    "rx_ms",
    "tx_lat",
    "tx_lon",
    "sats",
    "fix_quality",
    "utc_sec",
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
    New:  PHASE_RESULT <phase> <name> rx=<n> unique=<n> lost=<n> per=<pct> rssi_avg=<dbm> rssi_min=<dbm> crc_err=<n> gps_lat=<lat> gps_lon=<lon> gps_sats=<n> gps_fix=<n> gps_time_delta_ms=<ms>
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
        elif key == "tx_lat" or key == "gps_lat":
            result["lat"] = float(val)
        elif key == "tx_lon" or key == "gps_lon":
            result["lon"] = float(val)
        elif key == "sats" or key == "gps_sats":
            result["sats"] = int(val)
        elif key == "fix" or key == "gps_fix":
            result["fix_quality"] = int(val)
        elif key == "utc":
            result["utc_sec"] = int(val)
        elif key == "gps_time_delta_ms":
            result["gps_time_delta_ms"] = int(val)

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
    New:  PKT rx=<n> seq=<n> rssi=<dbm> phase=<n> tx_lat=<lat> tx_lon=<lon> sats=<n> fix=<q> utc=<sec>
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
        elif key == "rx_ms":
            result["rx_ms"] = int(val)
        elif key == "tx_lat":
            result["lat"] = float(val)
        elif key == "tx_lon":
            result["lon"] = float(val)
        elif key == "sats":
            result["sats"] = int(val)
        elif key == "fix":
            result["fix_quality"] = int(val)
        elif key == "utc":
            result["utc_sec"] = int(val)
        elif key == "tx_fw":
            result["tx_fw"] = val
        elif key == "rx_fw":
            result["rx_fw"] = val
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

    def write(self, data: bytes) -> int:
        """Write data to serial, reconnecting on error."""
        if self._ser is None:
            self._connect()
        try:
            return self._ser.write(data)
        except Exception as e:
            print(f"  [serial] Write error: {e}. Reconnecting...", file=sys.stderr)
            try:
                if self._ser:
                    self._ser.close()
            except Exception:
                pass
            self._ser = None
            time.sleep(2)
            self._connect()
            return 0

    def close(self):
        if self._ser:
            try:
                self._ser.close()
            except Exception:
                pass
            self._ser = None


# ─── CSV writers ──────────────────────────────────────────────────────────

def write_phase_csv_row(writer: csv.DictWriter, phase_data: dict, cycle: int,
                        distance_m: float, env: str, notes: str,
                        throughput_kbps: float = -1, goodput_kbps: float = -1):
    """Write a phase result row to CSV, enriched with phase table metadata and GPS.

    Goodput computation:
      goodput_kbps = (unique_packets × useful_payload_bytes × 8) / (slot_ms / 1000) / 1000
      goodput_efficiency_pct = goodput_kbps / theoretical_kbps × 100

    where useful_payload_bytes = payload_bytes - header_overhead
      LoRa: 127 - 20 = 107 bytes (13 preamble + 5 header + 2 CRC)
      FLRC: 255 - 10 = 245 bytes (4 preamble + 4 sync + 2 CRC)
    """
    phase_num = phase_data.get("phase", -1)
    if 0 <= phase_num < NUM_PHASES:
        meta = PHASE_TABLE[phase_num]
    else:
        meta = {"name": phase_data.get("name", "?"), "mod": "?", "freq": 0,
                "bitrate": 0, "sf": 0, "bw": 0, "sent": 0,
                "payload_bytes": 0, "header_overhead": 0,
                "useful_payload_bytes": 0, "slot_ms": 0, "theoretical_kbps": 0}

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
    row["throughput_kbps"] = throughput_kbps if throughput_kbps >= 0 else ""
    row["goodput_kbps"] = goodput_kbps if goodput_kbps >= 0 else ""

    # ─── Effective throughput computation ────────────────────────────────
    # effective_throughput_kbps = (unique_packets × payload_bytes × 8) / (slot_duration_s) / 1000
    unique_packets = phase_data.get("rx_unique")
    payload_bytes = meta.get("payload_bytes", 0)
    slot_ms = meta.get("slot_ms", 0)
    theoretical_kbps = meta.get("theoretical_kbps", 0)

    if unique_packets is not None and payload_bytes > 0 and slot_ms > 0:
        effective_kbps = (unique_packets * payload_bytes * 8) / (slot_ms / 1000.0) / 1000.0
        row["effective_throughput_kbps"] = round(effective_kbps, 2)
        row["theoretical_max_kbps"] = theoretical_kbps
        if theoretical_kbps > 0:
            efficiency = (effective_kbps / theoretical_kbps) * 100.0
            row["throughput_efficiency_pct"] = round(efficiency, 1)
        else:
            row["throughput_efficiency_pct"] = ""
    else:
        row["effective_throughput_kbps"] = ""
        row["theoretical_max_kbps"] = theoretical_kbps if theoretical_kbps > 0 else ""
        row["throughput_efficiency_pct"] = ""

    # ─── Goodput computation ──────────────────────────────────────────────
    # goodput_kbps = (unique_packets × useful_payload_bytes × 8) / (slot_ms / 1000) / 1000
    # goodput_efficiency_pct = goodput_kbps / theoretical_kbps × 100
    useful_payload_bytes = meta.get("useful_payload_bytes", 0)
    if unique_packets is not None and useful_payload_bytes > 0 and slot_ms > 0:
        gp_kbps = (unique_packets * useful_payload_bytes * 8) / (slot_ms / 1000.0) / 1000.0
        row["goodput_kbps"] = round(gp_kbps, 2)
        if theoretical_kbps > 0:
            gp_eff = (gp_kbps / theoretical_kbps) * 100.0
            row["goodput_efficiency_pct"] = round(gp_eff, 1)
        else:
            row["goodput_efficiency_pct"] = ""
    else:
        row["goodput_kbps"] = ""
        row["goodput_efficiency_pct"] = ""

    # ─── GPS time delta ──────────────────────────────────────────────────
    # gps_time_delta_ms = laptop_utc_time - gps_time_from_tx_packet (ms)
    # Captures radio propagation delay + clock drift + processing delay.
    # -1 = unknown (old firmware without this field).
    row["gps_time_delta_ms"] = phase_data.get("gps_time_delta_ms", -1)

    row["environment"] = env
    row["notes"] = notes

    writer.writerow(row)

    # Console summary
    gps_str = ""
    if "lat" in phase_data and "lon" in phase_data:
        gps_str = f"  GPS=({phase_data['lat']:.5f},{phase_data['lon']:.5f}) d={distance_m:.0f}m"
    elif distance_m >= 0:
        gps_str = f"  d={distance_m:.0f}m"
    tp_str = ""
    if row["effective_throughput_kbps"] != "":
        tp_str = f"  TP={row['effective_throughput_kbps']:.1f}kbps/{row['theoretical_max_kbps']}kbps({row['throughput_efficiency_pct']}%)"
    gp_str = ""
    if row["goodput_kbps"] != "":
        gp_str = f"  GP={row['goodput_kbps']:.1f}kbps({row['goodput_efficiency_pct']}%)"
    gps_td_str = ""
    if row["gps_time_delta_ms"] != -1 and row["gps_time_delta_ms"] != "":
        gps_td_str = f"  Δt={row['gps_time_delta_ms']}ms"
    print(f"  [{cycle}] Phase {phase_num:2d} {row['name']:16s} "
          f"rx={row['rx_received']:>3}/{row['tx_sent']:<3} "
          f"PER={row['per_pct']:>5.1f}%  "
          f"RSSI={row['rssi_avg_dbm']:>4.0f}dBm  "
          f"(min {row['rssi_min_dbm']:.0f}){gps_str}{tp_str}{gp_str}{gps_td_str}",
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
    row["rx_ms"] = pkt_data.get("rx_ms", "")
    row["tx_lat"] = lat if lat is not None else ""
    row["tx_lon"] = lon if lon is not None else ""
    row["sats"] = pkt_data.get("sats", "")
    row["fix_quality"] = pkt_data.get("fix_quality", "")
    row["utc_sec"] = pkt_data.get("utc_sec", "")
    row["distance_m"] = distance_m

    writer.writerow(row)


# ─── Firmware query and metadata ─────────────────────────────────────────

def query_rx_firmware(ser) -> str:
    """Send FW_QUERY to RX board and parse response.

    Returns the full FW_BOOT banner line, or an error string if no response.
    """
    try:
        ser.write(b"FW_QUERY\n")
        response = ""
        deadline = time.time() + 3.0
        while time.time() < deadline:
            data = ser.read(4096)
            if data:
                response += data.decode("ascii", errors="replace")
                if "FW_BOOT" in response:
                    for line in response.split("\n"):
                        if "FW_BOOT" in line:
                            return line.strip()
        return "UNKNOWN (no FW_QUERY response)"
    except Exception as e:
        return f"UNKNOWN (error: {e})"


def build_metadata_header(rx_fw_banner: str, args) -> str:
    """Build the metadata header string for capture files."""
    operator = os.getenv("OPERATOR", "unknown")
    notes = args.notes if hasattr(args, "notes") and args.notes else "none"
    return (
        f"# CAPTURE START {datetime.now(timezone.utc).isoformat()}\n"
        f"# RX_FIRMWARE {rx_fw_banner}\n"
        f"# TX_FIRMWARE (pending — will appear in first PKT tx_fw field)\n"
        f"# OPERATOR: {operator}\n"
        f"# ENV: {args.env}\n"
        f"# DISTANCE_START: {args.distance}\n"
        f"# CYCLES: {args.cycles}\n"
        f"# PORT: {args.port}\n"
        f"# NOTES: {notes}\n"
    )


def write_tx_fw_sidecar(base_path: str, tx_fw_hash: str, rx_fw_hash: str = ""):
    """Write/update a sidecar .meta file with TX firmware info.

    Called when the first PKT with tx_fw= is seen during capture.
    """
    meta_path = base_path.rsplit(".", 1)[0] + ".meta"
    try:
        with open(meta_path, "w") as f:
            f.write(f"TX_FIRMWARE_HASH {tx_fw_hash}\n")
            if rx_fw_hash:
                f.write(f"RX_FIRMWARE_HASH {rx_fw_hash}\n")
            f.write(f"TX_FW_DISCOVERED_AT {datetime.now(timezone.utc).isoformat()}\n")
        print(f"  [meta] TX firmware discovered: {tx_fw_hash}", file=sys.stderr)
        print(f"  [meta] Sidecar written: {meta_path}", file=sys.stderr)
    except Exception as e:
        print(f"  [meta] WARNING: Failed to write TX firmware sidecar: {e}",
              file=sys.stderr)


# ─── Main capture loop ───────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Capture LR2021 multi-radio sweep data from RX board. "
                    "Supports walk mode with GPS distance computation. "
                    "CSV columns include throughput, goodput (useful payload excluding "
                    "preamble/header/CRC overhead), and gps_time_delta_ms "
                    "(laptop_utc - gps_tx_time, in ms)."
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
    parser.add_argument("--out", default=None,
                        help="Explicit output file path (overrides auto-naming). "
                             "Packet file derived from this base name.")
    args = parser.parse_args()

    # ─── Validate mode ────────────────────────────────────────────────────
    if args.walk and args.distance > 0:
        print("WARNING: --distance ignored in --walk mode (GPS distance used instead)",
              file=sys.stderr)

    # ─── Build output filenames ───────────────────────────────────────────
    os.makedirs(args.output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if args.out:
        # Explicit output path — derive packet file from base name
        out_base = args.out
        if "." in os.path.basename(out_base):
            stem, ext = out_base.rsplit(".", 1)
            csv_path = out_base
            pkt_path = stem + "_packets." + ext
        else:
            csv_path = out_base + ".csv"
            pkt_path = out_base + "_packets.csv"
        # Ensure parent dir exists
        out_dir = os.path.dirname(csv_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
    elif args.walk:
        csv_filename = f"walk_{timestamp}.csv"
        pkt_filename = f"walk_{timestamp}_packets.csv"
        csv_path = os.path.join(args.output_dir, csv_filename)
        pkt_path = os.path.join(args.output_dir, pkt_filename)
    elif args.distance > 0:
        csv_filename = (f"char_dist_{int(args.distance)}m_env_{args.env}"
                        f"_{timestamp}.csv")
        pkt_filename = (f"char_dist_{int(args.distance)}m_env_{args.env}"
                        f"_{timestamp}_packets.csv")
        csv_path = os.path.join(args.output_dir, csv_filename)
        pkt_path = os.path.join(args.output_dir, pkt_filename)
    else:
        csv_filename = f"capture_env_{args.env}_{timestamp}.csv"
        pkt_filename = f"capture_env_{args.env}_{timestamp}_packets.csv"
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

    # ─── Query RX firmware version ────────────────────────────────────────
    print(f"Querying RX firmware (FW_QUERY)...", file=sys.stderr)
    rx_fw_banner = query_rx_firmware(ser)
    print(f"RX firmware: {rx_fw_banner}", file=sys.stderr)

    print(f"Connected. Sending TIME sync to RX...", file=sys.stderr)

    # ─── Send laptop time to RX for UTC bootstrap ──────────────────────
    # RX has no GPS — laptop (NTP-synced) sends time-of-day seconds
    # (h*3600 + m*60 + s) so the RX board can sync its clock before capture.
    # Firmware expects "TIME <utc_sec>\n".
    # This is also re-sent every 120s during capture to keep the clock fresh.
    TIME_SYNC_INTERVAL = 20.0  # seconds between periodic time refreshes (every phase)
    last_sync_time = 0.0

    def send_time_sync():
        """Send TIME with current time-of-day seconds to RX board."""
        try:
            now = datetime.now()
            utc_sec = now.hour * 3600 + now.minute * 60 + now.second
            ser.write(f"SET_TIME {int(time.time())}\n".encode("ascii"))
        except Exception as e:
            print(f"WARNING: Failed to send TIME sync: {e}", file=sys.stderr)

    send_time_sync()
    last_sync_time = time.time()
    time.sleep(1.0)  # Wait 1s for RX to process TIME command
    print(f"Sent TIME sync to RX", file=sys.stderr)

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
    # Build metadata header (written as # comment lines before CSV header)
    metadata_header = build_metadata_header(rx_fw_banner, args)

    csv_file = open(csv_path, "w", newline="")
    csv_file.write(metadata_header)
    csv_file.flush()
    writer = csv.DictWriter(csv_file, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    csv_file.flush()

    pkt_file = open(pkt_path, "w", newline="")
    pkt_file.write(metadata_header)
    pkt_file.flush()
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
    tx_fw_written = False  # TX firmware sidecar written after first PKT with tx_fw=

    # Per-phase packet rx_ms timestamps for throughput computation
    phase_rx_ms_list: list[int] = []  # rx_ms values for current phase
    phase_rx_count = 0               # total received count for current phase
    phase_unique_count = 0           # unique count for current phase

    try:
        while True:
            # Check duration
            if args.duration > 0 and (time.time() - start_time) >= args.duration:
                print(f"\nDuration limit ({args.duration}s) reached. Stopping.", file=sys.stderr)
                break

            # Periodic TIME resend (every 120s) to keep RX clock synced
            if (time.time() - last_sync_time) >= TIME_SYNC_INTERVAL:
                send_time_sync()
                last_sync_time = time.time()
                print("Resent TIME sync", file=sys.stderr)

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
                    elif args.distance > 0:
                        # Stop-and-capture with explicit distance
                        distance_m = args.distance
                    else:
                        # No distance given — log tx_lat/tx_lon from packet,
                        # distance can be computed post-hoc
                        lat = phase_data.get("lat")
                        lon = phase_data.get("lon")
                        if lat is not None and lon is not None:
                            if base_lat is None or base_lon is None:
                                base_lat = lat
                                base_lon = lon
                                print(f"  [gps] Base station set to first TX fix: "
                                      f"({base_lat:.6f}, {base_lon:.6f})", file=sys.stderr)
                            distance_m = haversine(base_lat, base_lon, lat, lon)

                    # ── Compute throughput using slot_ms from PHASE_TABLE ──
                    # throughput_kbps = (unique * payload_bytes * 8) / (slot_ms/1000) / 1000
                    # goodput_kbps   = (unique * useful_payload_bytes * 8) / (slot_ms/1000) / 1000
                    throughput_kbps = -1.0
                    goodput_kbps = -1.0
                    phase_num = phase_data.get("phase", -1)
                    if 0 <= phase_num < NUM_PHASES:
                        meta = PHASE_TABLE[phase_num]
                        pkt_size = meta["payload_bytes"]
                        useful_bytes = meta["useful_payload_bytes"]
                        slot_ms = meta["slot_ms"]
                    else:
                        pkt_size = 127
                        useful_bytes = 107
                        slot_ms = 0

                    num_unique = phase_data.get("rx_unique", 0)
                    if num_unique and num_unique > 0 and slot_ms > 0:
                        throughput_kbps = (num_unique * pkt_size * 8) / (slot_ms / 1000.0) / 1000.0
                        goodput_kbps = (num_unique * useful_bytes * 8) / (slot_ms / 1000.0) / 1000.0

                    write_phase_csv_row(writer, phase_data, current_cycle,
                                        distance_m, args.env, args.notes,
                                        throughput_kbps, goodput_kbps)
                    csv_file.flush()
                    phases_in_cycle += 1
                    continue

                # ── Per-packet (PKT) ──
                pkt_data = parse_pkt(line)
                if pkt_data is not None:
                    write_pkt_csv_row(pkt_writer, pkt_data, base_lat, base_lon)
                    pkt_file.flush()
                    pkt_count += 1
                    # Track rx_ms for throughput computation
                    if "rx_ms" in pkt_data:
                        phase_rx_ms_list.append(pkt_data["rx_ms"])
                    # Write TX firmware sidecar on first PKT with tx_fw=
                    if not tx_fw_written and "tx_fw" in pkt_data:
                        tx_fw_hash = pkt_data["tx_fw"]
                        rx_fw_hash = pkt_data.get("rx_fw", "")
                        write_tx_fw_sidecar(csv_path, tx_fw_hash, rx_fw_hash)
                        tx_fw_written = True
                    continue

                # ── Phase start (informational) ──
                if line.startswith("PHASE_START"):
                    parts = line.split()
                    if len(parts) >= 3:
                        print(f"  Phase {parts[1]}: {parts[2]} ...", file=sys.stderr)
                    # Reset per-phase throughput tracking
                    phase_rx_ms_list = []
                    phase_rx_count = 0
                    phase_unique_count = 0
                    continue

                # ── Other lines — print if they look interesting ──
                # (debug output, errors, etc.)
                if any(keyword in line for keyword in ("ERROR", "WARN", "GPS", "FIX", "BOOT", "READY", "TIME_SYNCED", "PHASE_JUMP")):
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