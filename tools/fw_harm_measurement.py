#!/usr/bin/env python3
"""fw_harm_measurement.py — Measurement capture + results for firmware harmonization.

Run AFTER Felix flashes both boards and starts TX/RX. This script:

1. Opens serial port to the RX board (C3 or E80, configurable via --port and --rig)
2. Reads boot banner, validates FW_HASH using firmware_hash_gate module
3. Generates session_id using session_manager module
4. Sends SESSION <uuid> command to firmware
5. Captures PKT lines for a configurable duration (default 60s, --duration)
6. Parses each PKT line using pkt_parser module
7. After capture, computes summary statistics:
   - Total packets received
   - CRC OK vs CRC failed count + percentage
   - RSSI: min, max, mean, std dev
   - SNR: min, max, mean (LoRa only)
   - Seq continuity: gaps, duplicates, monotonic check
   - Field count validation (must be exactly 23 fields per line)
   - Unique config_ids seen
   - ts_ms monotonic check
   - Per-config_id breakdown if multiple configs
8. Outputs results in two formats:
   a. JSON to stdout (for machine consumption)
   b. Human-readable summary to a file (--output, default fw_harm_results_<timestamp>.txt)
9. Surfaces results: prints "MEASUREMENT COMPLETE" + key stats to stdout

Usage:
    python3 tools/fw_harm_measurement.py --port /dev/ttyACM0 --rig c3 --duration 60 --output results.txt
    python3 tools/fw_harm_measurement.py --port /dev/ttyUSB0 --rig e80 --duration 120
"""

import argparse
import json
import math
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone

# ── sys.path manipulation to find tools/ modules ────────────────────────────
_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

# Import existing tools modules
from pkt_parser import parse_pkt_line, PKT_FIELDS          # noqa: E402
from firmware_hash_gate import parse_fw_hash, validate_fw_hash  # noqa: E402
from session_manager import generate_session_id            # noqa: E402

try:
    import serial
except ImportError:
    print("ERROR: pyserial not installed. Run: pip install pyserial", file=sys.stderr)
    sys.exit(1)


# ── Constants ───────────────────────────────────────────────────────────────
BOOT_BANNER_TIMEOUT = 10.0   # seconds to wait for boot banner
SESSION_ACK_TIMEOUT = 3.0    # seconds to wait for SESSION ack
DEFAULT_BAUD = 115200         # C3 default; E80 may use 2000000

# Expected field count for valid PKT lines (23 fields after "PKT,")
EXPECTED_PKT_FIELDS = 23


# ── Statistics helpers ──────────────────────────────────────────────────────

def compute_stats(values: list) -> dict:
    """Compute min, max, mean, std dev for a list of numeric values."""
    if not values:
        return {"count": 0, "min": None, "max": None, "mean": None, "std": None}
    n = len(values)
    mean = sum(values) / n
    if n > 1:
        variance = sum((x - mean) ** 2 for x in values) / (n - 1)
        std = math.sqrt(variance)
    else:
        std = 0.0
    return {
        "count": n,
        "min": min(values),
        "max": max(values),
        "mean": round(mean, 2),
        "std": round(std, 2),
    }


def check_seq_continuity(seqs: list) -> dict:
    """Analyze sequence number continuity.

    Returns dict with:
      - total: count of seq values
      - gaps: list of (expected, got) tuples where seq jumped
      - duplicates: count of repeated seq values
      - monotonic: bool, True if seq strictly increasing (no dupes, no gaps = monotonic w/ step 1)
      - min_seq, max_seq
      - expected_count: max - min + 1
      - missing_count: expected_count - actual unique
    """
    if not seqs:
        return {
            "total": 0, "gaps": [], "duplicates": 0,
            "monotonic": True, "min_seq": None, "max_seq": None,
            "expected_count": 0, "missing_count": 0,
        }

    sorted_seqs = sorted(seqs)
    min_seq = sorted_seqs[0]
    max_seq = sorted_seqs[-1]
    expected_count = max_seq - min_seq + 1

    # Detect gaps and duplicates
    gaps = []
    duplicates = 0
    seen = set()
    prev = None

    for s in seqs:
        if s in seen:
            duplicates += 1
        seen.add(s)
        if prev is not None and s < prev:
            # Out of order — not monotonic
            pass
        prev = s

    # Check gaps in sorted unique seqs
    unique_sorted = sorted(set(seqs))
    for i in range(1, len(unique_sorted)):
        if unique_sorted[i] - unique_sorted[i - 1] > 1:
            gaps.append((unique_sorted[i - 1], unique_sorted[i]))

    # Monotonic = strictly increasing with step 1, no duplicates, no gaps
    is_monotonic = (duplicates == 0 and len(gaps) == 0
                    and all(seqs[i] <= seqs[i + 1] for i in range(len(seqs) - 1)))

    return {
        "total": len(seqs),
        "gaps": gaps,
        "duplicates": duplicates,
        "monotonic": is_monotonic,
        "min_seq": min_seq,
        "max_seq": max_seq,
        "expected_count": expected_count,
        "missing_count": expected_count - len(unique_sorted),
    }


def check_ts_monotonic(ts_values: list) -> dict:
    """Check if ts_ms values are monotonically non-decreasing."""
    if not ts_values:
        return {"monotonic": True, "violations": 0, "count": 0}
    violations = sum(
        1 for i in range(1, len(ts_values))
        if ts_values[i] < ts_values[i - 1]
    )
    return {
        "monotonic": violations == 0,
        "violations": violations,
        "count": len(ts_values),
    }


def validate_field_count(line: str) -> bool:
    """Validate that a PKT line has exactly 23 comma-separated fields after 'PKT,'."""
    if not line or not line.startswith("PKT,"):
        return False
    parts = line[4:].strip().split(",")
    return len(parts) == EXPECTED_PKT_FIELDS


def compute_summary_stats(packets: list, bad_field_counts: list) -> dict:
    """Compute full summary statistics from parsed PKT dicts.

    Args:
        packets: list of dicts from parse_pkt_line()
        bad_field_counts: list of raw lines that had wrong field count

    Returns:
        dict with all summary statistics
    """
    total = len(packets)
    total_raw = total + len(bad_field_counts)

    # CRC stats
    crc_ok_count = sum(1 for p in packets if p.get("crc_ok", 0) == 1)
    crc_fail_count = total - crc_ok_count
    crc_ok_pct = round(100.0 * crc_ok_count / total, 2) if total > 0 else 0.0
    crc_fail_pct = round(100.0 * crc_fail_count / total, 2) if total > 0 else 0.0

    # RSSI stats
    rssi_values = [p["rssi_dbm"] for p in packets if "rssi_dbm" in p]
    rssi_stats = compute_stats(rssi_values)

    # SNR stats (LoRa only — may be 0 for FLRC)
    snr_values = [p["snr_db"] for p in packets if "snr_db" in p and p["snr_db"] != 0]
    snr_stats = compute_stats(snr_values) if snr_values else {
        "count": 0, "min": None, "max": None, "mean": None, "std": None
    }

    # Seq continuity
    seqs = [p["seq"] for p in packets if "seq" in p]
    seq_continuity = check_seq_continuity(seqs)

    # ts_ms monotonic check
    ts_values = [p["ts_ms"] for p in packets if "ts_ms" in p]
    ts_check = check_ts_monotonic(ts_values)

    # Unique config_ids
    config_ids = list(set(p.get("config_id", "") for p in packets if p.get("config_id")))
    config_ids.sort()

    # Field count validation
    field_count_ok = len(bad_field_counts) == 0

    # Per-config_id breakdown
    per_config = {}
    if len(config_ids) > 1:
        for cid in config_ids:
            cid_packets = [p for p in packets if p.get("config_id") == cid]
            cid_seqs = [p["seq"] for p in cid_packets if "seq" in p]
            cid_rssi = [p["rssi_dbm"] for p in cid_packets if "rssi_dbm" in p]
            cid_crc_ok = sum(1 for p in cid_packets if p.get("crc_ok", 0) == 1)
            per_config[cid] = {
                "total": len(cid_packets),
                "crc_ok": cid_crc_ok,
                "crc_fail": len(cid_packets) - cid_crc_ok,
                "rssi": compute_stats(cid_rssi),
                "seq": check_seq_continuity(cid_seqs),
            }

    # Modulation types seen
    mod_types = list(set(p.get("mod", "") for p in packets if p.get("mod")))
    mod_types.sort()

    # PRBS bit error statistics
    bit_err_values = [p["bit_err"] for p in packets if "bit_err" in p]
    bytes_bad_values = [p["bytes_bad"] for p in packets if "bytes_bad" in p]
    total_bit_errors = sum(bit_err_values)
    total_bytes_bad = sum(bytes_bad_values)
    packets_with_errors = sum(1 for be in bit_err_values if be > 0)
    crc_ok_packets = [p for p in packets if p.get("crc_ok", 0) == 1]
    crc_ok_bit_err = [p["bit_err"] for p in crc_ok_packets if "bit_err" in p]
    crc_ok_bytes_bad = [p["bytes_bad"] for p in crc_ok_packets if "bytes_bad" in p]

    return {
        "total_packets": total,
        "total_raw_lines": total_raw,
        "bad_field_count_lines": len(bad_field_counts),
        "field_count_ok": field_count_ok,
        "crc": {
            "ok_count": crc_ok_count,
            "fail_count": crc_fail_count,
            "ok_pct": crc_ok_pct,
            "fail_pct": crc_fail_pct,
        },
        "rssi": rssi_stats,
        "snr": snr_stats,
        "seq_continuity": seq_continuity,
        "ts_ms": ts_check,
        "config_ids": config_ids,
        "unique_config_count": len(config_ids),
        "mod_types": mod_types,
        "per_config_breakdown": per_config,
        "prbs": {
            "total_bit_errors": total_bit_errors,
            "total_bytes_bad": total_bytes_bad,
            "packets_with_errors": packets_with_errors,
            "packets_with_errors_pct": round(100.0 * packets_with_errors / total, 2) if total > 0 else 0.0,
            "bit_err_stats": compute_stats(bit_err_values),
            "bytes_bad_stats": compute_stats(bytes_bad_values),
            "crc_ok_bit_errors": sum(crc_ok_bit_err),
            "crc_ok_bytes_bad": sum(crc_ok_bytes_bad),
        },
    }


def format_human_report(summary: dict, session_id: str, fw_hash: str | None,
                        rig: str, port: str, duration: int) -> str:
    """Format a human-readable summary report."""
    lines = []
    lines.append("=" * 70)
    lines.append("FIRMWARE HARMONIZATION MEASUREMENT REPORT")
    lines.append("=" * 70)
    lines.append(f"Timestamp:       {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
    lines.append(f"Session ID:      {session_id}")
    lines.append(f"FW Hash:         {fw_hash or 'N/A'}")
    lines.append(f"Rig:             {rig}")
    lines.append(f"Port:            {port}")
    lines.append(f"Duration:        {duration}s")
    lines.append("")

    lines.append("-" * 40)
    lines.append("PACKET STATISTICS")
    lines.append("-" * 40)
    lines.append(f"Total packets:      {summary['total_packets']}")
    lines.append(f"Raw lines seen:     {summary['total_raw_lines']}")
    lines.append(f"Bad field count:    {summary['bad_field_count_lines']}")
    lines.append(f"Field count valid:  {'YES' if summary['field_count_ok'] else 'NO'}")
    lines.append("")

    lines.append("-" * 40)
    lines.append("CRC RESULTS")
    lines.append("-" * 40)
    lines.append(f"CRC OK:     {summary['crc']['ok_count']} ({summary['crc']['ok_pct']}%)")
    lines.append(f"CRC Failed: {summary['crc']['fail_count']} ({summary['crc']['fail_pct']}%)")
    lines.append("")

    lines.append("-" * 40)
    lines.append("RSSI STATISTICS (dBm)")
    lines.append("-" * 40)
    r = summary["rssi"]
    if r["count"] > 0:
        lines.append(f"Count:  {r['count']}")
        lines.append(f"Min:    {r['min']}")
        lines.append(f"Max:    {r['max']}")
        lines.append(f"Mean:   {r['mean']}")
        lines.append(f"Std:    {r['std']}")
    else:
        lines.append("No RSSI data")
    lines.append("")

    lines.append("-" * 40)
    lines.append("SNR STATISTICS (dB) — LoRa only")
    lines.append("-" * 40)
    s = summary["snr"]
    if s["count"] > 0:
        lines.append(f"Count:  {s['count']}")
        lines.append(f"Min:    {s['min']}")
        lines.append(f"Max:    {s['max']}")
        lines.append(f"Mean:   {s['mean']}")
    else:
        lines.append("No SNR data (FLRC mode or all zeros)")
    lines.append("")

    lines.append("-" * 40)
    lines.append("SEQUENCE CONTINUITY")
    lines.append("-" * 40)
    sc = summary["seq_continuity"]
    lines.append(f"Total seq values:   {sc['total']}")
    lines.append(f"Min seq:            {sc['min_seq']}")
    lines.append(f"Max seq:            {sc['max_seq']}")
    lines.append(f"Expected count:     {sc['expected_count']}")
    lines.append(f"Missing count:      {sc['missing_count']}")
    lines.append(f"Gaps detected:      {len(sc['gaps'])}")
    if sc["gaps"]:
        for gap_start, gap_end in sc["gaps"][:10]:
            lines.append(f"  Gap: {gap_start} -> {gap_end} (missing {gap_end - gap_start - 1})")
        if len(sc["gaps"]) > 10:
            lines.append(f"  ... and {len(sc['gaps']) - 10} more gaps")
    lines.append(f"Duplicates:         {sc['duplicates']}")
    lines.append(f"Monotonic:          {'YES' if sc['monotonic'] else 'NO'}")
    lines.append("")

    lines.append("-" * 40)
    lines.append("TIMESTAMP (ts_ms) CHECK")
    lines.append("-" * 40)
    ts = summary["ts_ms"]
    lines.append(f"Count:       {ts['count']}")
    lines.append(f"Monotonic:   {'YES' if ts['monotonic'] else 'NO'}")
    lines.append(f"Violations:  {ts['violations']}")
    lines.append("")

    lines.append("-" * 40)
    lines.append("PRBS BIT ERROR STATISTICS")
    lines.append("-" * 40)
    prbs = summary.get("prbs", {})
    lines.append(f"Total bit errors:   {prbs.get('total_bit_errors', 0)}")
    lines.append(f"Total bytes bad:    {prbs.get('total_bytes_bad', 0)}")
    lines.append(f"Packets w/ errors: {prbs.get('packets_with_errors', 0)} ({prbs.get('packets_with_errors_pct', 0.0)}%)")
    be_stats = prbs.get("bit_err_stats", {})
    if be_stats.get("count", 0) > 0:
        lines.append(f"Bit err/pkt:        min={be_stats['min']} max={be_stats['max']} mean={be_stats['mean']} std={be_stats['std']}")
    bb_stats = prbs.get("bytes_bad_stats", {})
    if bb_stats.get("count", 0) > 0:
        lines.append(f"Bytes bad/pkt:      min={bb_stats['min']} max={bb_stats['max']} mean={bb_stats['mean']} std={bb_stats['std']}")
    lines.append(f"CRC-OK bit errors:  {prbs.get('crc_ok_bit_errors', 0)}")
    lines.append(f"CRC-OK bytes bad:   {prbs.get('crc_ok_bytes_bad', 0)}")
    lines.append("")

    lines.append("-" * 40)
    lines.append("CONFIG IDS")
    lines.append("-" * 40)
    lines.append(f"Unique config_ids: {summary['unique_config_count']}")
    for cid in summary["config_ids"]:
        lines.append(f"  - {cid}")
    lines.append(f"Mod types:          {', '.join(summary['mod_types']) or 'N/A'}")
    lines.append("")

    if summary["per_config_breakdown"]:
        lines.append("-" * 40)
        lines.append("PER-CONFIG_ID BREAKDOWN")
        lines.append("-" * 40)
        for cid, data in summary["per_config_breakdown"].items():
            lines.append(f"  Config: {cid}")
            lines.append(f"    Packets:  {data['total']}")
            lines.append(f"    CRC OK:   {data['crc_ok']}")
            lines.append(f"    CRC Fail: {data['crc_fail']}")
            if data["rssi"]["count"] > 0:
                lines.append(f"    RSSI:     min={data['rssi']['min']} max={data['rssi']['max']} mean={data['rssi']['mean']}")
            if data["seq"]["total"] > 0:
                lines.append(f"    Seq:      {data['seq']['min_seq']}-{data['seq']['max_seq']} (gaps={len(data['seq']['gaps'])}, dups={data['seq']['duplicates']})")
            lines.append("")

    lines.append("=" * 70)
    return "\n".join(lines)


# ── Serial capture ──────────────────────────────────────────────────────────

def read_boot_banner(ser, timeout_s: float = BOOT_BANNER_TIMEOUT) -> tuple:
    """Read serial lines until we find a boot banner with FW_HASH.

    Returns (fw_hash, raw_banner_lines).
    """
    fw_hash = None
    banner_lines = []
    buf = ""
    start = time.monotonic()

    while (time.monotonic() - start) < timeout_s:
        data = ser.read(256)
        if not data:
            continue
        text = data.decode("ascii", errors="replace")
        buf += text
        while "\n" in buf:
            line, buf = buf.split("\n", 1)
            line = line.strip()
            if not line:
                continue
            banner_lines.append(line)
            print(f"  [BOOT] {line}")
            hash_str = parse_fw_hash(line)
            if hash_str is not None and validate_fw_hash(hash_str):
                fw_hash = hash_str
                return fw_hash, banner_lines

    return fw_hash, banner_lines


def capture_pkts(ser, duration: int, session_id: str) -> tuple:
    """Capture PKT lines for a given duration.

    Returns (parsed_packets, bad_field_lines, raw_lines).
    """
    parsed_packets = []
    bad_field_lines = []
    raw_lines = []
    buf = ""
    start = time.monotonic()
    count = 0

    print(f"\nCapturing PKT lines for {duration}s...")
    print("(Ctrl+C to stop early)\n")

    try:
        while (time.monotonic() - start) < duration:
            data = ser.read(256)
            if not data:
                continue
            text = data.decode("ascii", errors="replace")
            buf += text

            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                line = line.strip()
                if not line:
                    continue

                raw_lines.append(line)

                # Check if it's a PKT line
                if line.startswith("PKT,"):
                    # Validate field count first
                    if not validate_field_count(line):
                        bad_field_lines.append(line)
                        if len(bad_field_lines) <= 5:
                            print(f"  [BAD_FIELDS] {line[:80]}...")
                        continue

                    pkt = parse_pkt_line(line)
                    if pkt:
                        # Inject session_id
                        pkt["session_id"] = session_id
                        parsed_packets.append(pkt)
                        count += 1
                        if count % 100 == 0 or count == 1:
                            print(f"  PKT #{count} seq={pkt['seq']} rssi={pkt['rssi_dbm']} crc={'OK' if pkt['crc_ok'] else 'FAIL'}")
                    else:
                        bad_field_lines.append(line)
                elif line.startswith("CONFIG_START") or line.startswith("CONFIG_END"):
                    print(f"  [CONFIG] {line}")

    except KeyboardInterrupt:
        print("\nCapture interrupted by user.")

    elapsed = time.monotonic() - start
    print(f"\nCapture complete: {count} packets in {elapsed:.1f}s")
    return parsed_packets, bad_field_lines, raw_lines


def main():
    parser = argparse.ArgumentParser(
        description="Firmware harmonization measurement capture + results"
    )
    parser.add_argument("--port", required=True,
                        help="Serial port (e.g. /dev/ttyACM0, /dev/ttyUSB0)")
    parser.add_argument("--rig", required=True, choices=["c3", "e80"],
                        help="Which rig/board type (c3 or e80)")
    parser.add_argument("--duration", type=int, default=60,
                        help="Capture duration in seconds (default: 60)")
    parser.add_argument("--baud", type=int, default=None,
                        help="Serial baud rate (default: 115200 for C3, 2000000 for E80)")
    parser.add_argument("--output", default=None,
                        help="Output file for human-readable report (default: fw_harm_results_<timestamp>.txt)")
    parser.add_argument("--skip-fw-check", action="store_true",
                        help="Skip firmware hash gate validation (not recommended)")
    args = parser.parse_args()

    # Set baud rate based on rig if not specified
    baud = args.baud
    if baud is None:
        baud = 2000000 if args.rig == "e80" else 115200

    # Set output filename
    if args.output is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = f"fw_harm_results_{timestamp}.txt"

    # Open serial port
    print(f"Opening {args.port} at {baud} baud (rig: {args.rig})")
    try:
        ser = serial.Serial(args.port, baud, timeout=1.0)
    except serial.SerialException as e:
        print(f"ERROR: Cannot open serial port: {e}", file=sys.stderr)
        sys.exit(1)

    fw_hash = None
    banner_lines = []

    # ── Step 1-2: Read boot banner + validate FW_HASH ──────────────────────
    if not args.skip_fw_check:
        print(f"\nWaiting for boot banner (timeout {BOOT_BANNER_TIMEOUT:.0f}s)...")
        fw_hash, banner_lines = read_boot_banner(ser)

        if not fw_hash:
            print("\n[FW GATE] ERROR: No valid FW_HASH found in boot banner!")
            print("[FW GATE] Refusing to start capture. Flash firmware with FW_HASH")
            print("[FW GATE] or use --skip-fw-check to bypass (not recommended).")
            ser.close()
            sys.exit(1)
        print(f"\n[FW GATE] Valid FW_HASH={fw_hash} — capture authorised.")
    else:
        print("\n[FW GATE] SKIPPED (--skip-fw-check)")

    # ── Step 3-4: Generate session_id + send to firmware ────────────────────
    session_id = generate_session_id()
    print(f"\n[SESSION] Generated session_id: {session_id}")

    # Send SESSION <uuid> command to firmware
    try:
        cmd = f"SESSION {session_id}\r\n"
        ser.write(cmd.encode("ascii"))
        print(f"[SESSION] Sent: {cmd.strip()}")
    except Exception as e:
        print(f"[SESSION] WARNING: Could not send SESSION command: {e}", file=sys.stderr)

    # Wait briefly for ack
    time.sleep(0.5)
    ack_buf = ""
    ack_start = time.monotonic()
    while (time.monotonic() - ack_start) < SESSION_ACK_TIMEOUT:
        data = ser.read(256)
        if not data:
            continue
        ack_buf += data.decode("ascii", errors="replace")
        if "\n" in ack_buf:
            for line in ack_buf.split("\n"):
                line = line.strip()
                if line:
                    print(f"  [ACK] {line}")
            break

    # ── Step 5-6: Capture PKT lines ────────────────────────────────────────
    packets, bad_lines, raw_lines = capture_pkts(ser, args.duration, session_id)

    ser.close()

    # ── Step 7: Compute summary statistics ─────────────────────────────────
    summary = compute_summary_stats(packets, bad_lines)

    # ── Step 8a: JSON to stdout ─────────────────────────────────────────────
    json_output = {
        "session_id": session_id,
        "fw_hash": fw_hash,
        "rig": args.rig,
        "port": args.port,
        "baud": baud,
        "duration_s": args.duration,
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "summary": summary,
    }
    print("\n" + "=" * 70)
    print("JSON OUTPUT (for machine consumption):")
    print("=" * 70)
    print(json.dumps(json_output, indent=2))

    # ── Step 8b: Human-readable report to file ─────────────────────────────
    report = format_human_report(summary, session_id, fw_hash, args.rig,
                                 args.port, args.duration)
    with open(args.output, "w") as f:
        f.write(report)
    print(f"\nHuman-readable report written to: {args.output}")

    # ── Step 9: Surface results ─────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("MEASUREMENT COMPLETE")
    print("=" * 70)
    print(f"  Session:    {session_id}")
    print(f"  FW Hash:    {fw_hash or 'N/A'}")
    print(f"  Rig:        {args.rig}")
    print(f"  Duration:   {args.duration}s")
    print(f"  Total PKTs: {summary['total_packets']}")
    print(f"  CRC OK:     {summary['crc']['ok_count']} ({summary['crc']['ok_pct']}%)")
    print(f"  CRC Fail:   {summary['crc']['fail_count']} ({summary['crc']['fail_pct']}%)")
    if summary["rssi"]["count"] > 0:
        print(f"  RSSI:       min={summary['rssi']['min']} max={summary['rssi']['max']} mean={summary['rssi']['mean']} std={summary['rssi']['std']}")
    print(f"  Seq gaps:   {len(summary['seq_continuity']['gaps'])}")
    print(f"  Seq dups:   {summary['seq_continuity']['duplicates']}")
    print(f"  Configs:    {summary['unique_config_count']}")
    print(f"  Field OK:   {'YES' if summary['field_count_ok'] else 'NO'}")
    prbs = summary.get("prbs", {})
    print(f"  Bit errors: {prbs.get('total_bit_errors', 0)}")
    print(f"  Bytes bad:  {prbs.get('total_bytes_bad', 0)}")
    print(f"  Pkt w/err:  {prbs.get('packets_with_errors', 0)} ({prbs.get('packets_with_errors_pct', 0.0)}%)")
    print(f"  Report:     {args.output}")
    print("=" * 70)


if __name__ == "__main__":
    main()