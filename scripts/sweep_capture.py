#!/usr/bin/env python3
"""
sweep_capture.py — Capture LR2021 multi-radio sweep data from RX board.

Connects to the RX board via BoardSerial (mandatory flock wrapper),
parses PHASE_RESULT and PKT lines, and writes structured CSV.

Firmware: multi_radio_sweep_rx.cpp (14 phases, auto-start 8s after boot)
Output format from firmware:
    PHASE_START <phase_num> <name>
    PKT rx=<n> seq=<n> rssi=<dbm> phase=<n>
    PHASE_RESULT <phase_num> <name> rx=<n> unique=<n> lost=<n> per=<pct> rssi_avg=<dbm> rssi_min=<dbm> crc_err=<n>
    === CYCLE <n> START uptime=<ms> ===
    === CYCLE <n> COMPLETE uptime=<ms> ===

Usage:
    python3 scripts/sweep_capture.py --port /dev/ttyACM2 --distance 10 --env outdoor_los
    python3 scripts/sweep_capture.py --port /dev/ttyACM2 --distance 1 --env indoor --cycles 1
    python3 scripts/sweep_capture.py --port /dev/ttyACM3 --distance 50 --env outdoor_los --notes "antenna vertical"

Requires:
    - pyserial (pip install pyserial)
    - BoardSerial wrapper at ~/repos/balloon-fresh/tools/board_serial.py
    - Board lock acquired: BALLOON_TRACK=range-tests python3 tools/balloon-board-lock.py acquire both
"""

import argparse
import csv
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ─── BoardSerial import ──────────────────────────────────────────────────
# Add the balloon-fresh tools dir to path so we can import BoardSerial
TOOLS_DIR = Path.home() / "repos" / "balloon-fresh" / "tools"
sys.path.insert(0, str(TOOLS_DIR))

try:
    from board_serial import BoardSerial
except ImportError:
    print("ERROR: Cannot import BoardSerial from", TOOLS_DIR, file=sys.stderr)
    print("Ensure balloon-fresh repo is cloned.", file=sys.stderr)
    sys.exit(1)

# ─── Phase table (must match firmware multi_radio_sweep_rx.cpp) ───────────
# Indexed by phase number 0-13
PHASE_TABLE = [
    # (name, modulation, freq_mhz, bitrate_kbps, sf, bw_khz, tx_sent_default)
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

# CSV columns
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
    "distance_m",
    "environment",
    "notes",
]

# ─── Line parsers ────────────────────────────────────────────────────────

def parse_phase_result(line: str) -> dict | None:
    """
    Parse: PHASE_RESULT <phase_num> <name> rx=<n> unique=<n> lost=<n> per=<pct> rssi_avg=<dbm> rssi_min=<dbm> crc_err=<n>
    """
    line = line.strip()
    if not line.startswith("PHASE_RESULT"):
        return None

    # Split: PHASE_RESULT <num> <name> key=val key=val ...
    parts = line.split()
    if len(parts) < 4:
        return None

    try:
        phase_num = int(parts[1])
    except (ValueError, IndexError):
        return None

    name = parts[2]

    # Parse key=value pairs
    result = {"phase": phase_num, "name": name}
    for kv in parts[3:]:
        if "=" in kv:
            key, val = kv.split("=", 1)
            key = key.strip()
            val = val.strip()
            # Map firmware keys to our fields
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
    """Parse: PKT rx=<n> seq=<n> rssi=<dbm> phase=<n>"""
    line = line.strip()
    if not line.startswith("PKT"):
        return None
    parts = line.split()
    result = {}
    for kv in parts[1:]:
        if "=" in kv:
            key, val = kv.split("=", 1)
            if key in ("rx", "seq", "rssi", "phase"):
                result[key] = int(val) if key != "rssi" else float(val)
    return result if result else None


# ─── CSV writer ──────────────────────────────────────────────────────────

def write_csv_row(writer: csv.DictWriter, phase_data: dict, cycle: int,
                  distance_m: float, env: str, notes: str):
    """Write a phase result row to CSV, enriched with phase table metadata."""
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
    row["distance_m"] = distance_m
    row["environment"] = env
    row["notes"] = notes

    writer.writerow(row)
    print(f"  [{cycle}] Phase {phase_num:2d} {row['name']:16s} "
          f"rx={row['rx_received']:>3}/{row['tx_sent']:<3} "
          f"PER={row['per_pct']:>5.1f}%  "
          f"RSSI={row['rssi_avg_dbm']:>4.0f}dBm  "
          f"(min {row['rssi_min_dbm']:.0f})",
          file=sys.stderr)


# ─── Main capture loop ───────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Capture LR2021 multi-radio sweep data from RX board"
    )
    parser.add_argument("--port", default="/dev/ttyACM2",
                        help="Serial port for RX board (default: /dev/ttyACM2)")
    parser.add_argument("--baud", type=int, default=115200,
                        help="Baud rate (default: 115200)")
    parser.add_argument("--distance", type=float, required=True,
                        help="TX-RX distance in meters (REQUIRED)")
    parser.add_argument("--env", required=True,
                        help="Environment tag: indoor, outdoor_los, outdoor_nlos, etc.")
    parser.add_argument("--cycles", type=int, default=0,
                        help="Number of complete sweep cycles to capture (0 = until Ctrl-C)")
    parser.add_argument("--notes", default="",
                        help="Free-text notes for this capture session")
    parser.add_argument("--output-dir", default="data",
                        help="Output directory for CSV files (default: data/)")
    parser.add_argument("--raw-log", action="store_true",
                        help="Also save raw serial log alongside CSV")
    args = parser.parse_args()

    # Build output filename
    os.makedirs(args.output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = (f"char_dist_{int(args.distance)}m_env_{args.env}"
                    f"_{timestamp}.csv")
    csv_path = os.path.join(args.output_dir, csv_filename)

    raw_log_path = None
    raw_log_file = None
    if args.raw_log:
        raw_log_path = csv_path.replace(".csv", ".log")
        raw_log_file = open(raw_log_path, "w")

    # Open serial via BoardSerial (enforces flock)
    print(f"Connecting to {args.port} at {args.baud} baud...", file=sys.stderr)
    try:
        ser = BoardSerial(args.port, args.baud, timeout=1.0)
    except Exception as e:
        print(f"ERROR: Cannot open {args.port}: {e}", file=sys.stderr)
        print("Ensure board lock is acquired:", file=sys.stderr)
        print(f"  BALLOON_TRACK=range-tests python3 {TOOLS_DIR}/balloon-board-lock.py acquire both",
              file=sys.stderr)
        sys.exit(1)

    print(f"Connected. Waiting for sweep data...", file=sys.stderr)
    print(f"Distance: {args.distance}m  Environment: {args.env}", file=sys.stderr)
    if args.cycles > 0:
        print(f"Will capture {args.cycles} complete cycle(s), then exit.", file=sys.stderr)
    else:
        print("Press Ctrl-C to stop capture.", file=sys.stderr)
    print(f"Output: {csv_path}", file=sys.stderr)
    if raw_log_path:
        print(f"Raw log: {raw_log_path}", file=sys.stderr)
    print("-" * 60, file=sys.stderr)

    # Open CSV writer
    csv_file = open(csv_path, "w", newline="")
    writer = csv.DictWriter(csv_file, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    csv_file.flush()

    current_cycle = -1
    cycles_completed = 0
    phases_in_cycle = 0
    buf = ""

    try:
        while True:
            # Read available data
            data = ser.read(4096)
            if not data:
                continue

            text = data.decode("ascii", errors="replace")
            if raw_log_file:
                raw_log_file.write(text)
                raw_log_file.flush()

            buf += text

            # Process complete lines
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                line = line.strip()

                if not line:
                    continue

                # Check for cycle start
                cycle_num = parse_cycle_start(line)
                if cycle_num is not None:
                    current_cycle = cycle_num
                    phases_in_cycle = 0
                    print(f"\n=== CYCLE {current_cycle} START ===", file=sys.stderr)
                    continue

                # Check for cycle complete
                cycle_done = parse_cycle_complete(line)
                if cycle_done is not None:
                    cycles_completed += 1
                    print(f"\n=== CYCLE {cycle_done} COMPLETE "
                          f"({cycles_completed} done) ===\n", file=sys.stderr)
                    csv_file.flush()

                    if args.cycles > 0 and cycles_completed >= args.cycles:
                        print(f"\nCaptured {cycles_completed} cycle(s). Done!",
                              file=sys.stderr)
                        raise KeyboardInterrupt  # clean exit

                    continue

                # Check for phase result
                phase_data = parse_phase_result(line)
                if phase_data is not None:
                    write_csv_row(writer, phase_data, current_cycle,
                                  args.distance, args.env, args.notes)
                    csv_file.flush()
                    phases_in_cycle += 1
                    continue

                # PKT lines — just count, don't store per-packet in CSV
                # (can be enabled later if needed)
                if line.startswith("PKT"):
                    # Could parse and store per-packet RSSI if needed
                    continue

                # PHASE_START — informational
                if line.startswith("PHASE_START"):
                    parts = line.split()
                    if len(parts) >= 3:
                        print(f"  Phase {parts[1]}: {parts[2]} ...", file=sys.stderr)
                    continue

    except KeyboardInterrupt:
        print(f"\n\nCapture stopped.", file=sys.stderr)
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
    finally:
        csv_file.close()
        ser.close()
        if raw_log_file:
            raw_log_file.close()

    # Print summary
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"CAPTURE SUMMARY", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    print(f"Output file:     {csv_path}", file=sys.stderr)
    print(f"Cycles captured: {cycles_completed}", file=sys.stderr)
    print(f"Distance:        {args.distance}m", file=sys.stderr)
    print(f"Environment:     {args.env}", file=sys.stderr)

    # Count rows in CSV
    try:
        with open(csv_path) as f:
            row_count = sum(1 for _ in f) - 1  # minus header
        print(f"Phase results:   {row_count}", file=sys.stderr)
    except Exception:
        pass

    print(f"\nParse with: python3 tools/parse_unified_csv.py {csv_path}",
          file=sys.stderr)
    print(f"Plot with:   python3 tools/plot_characterization.py {csv_path}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
