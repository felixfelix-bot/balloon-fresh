#!/usr/bin/env python3
"""
parse_unified_csv.py — Convert raw LR2021 sweep serial logs to unified CSV.

Reads a serial log file captured from the RX (or TX) board via ``tee`` and
extracts structured data into the unified CSV schema used by the balloon
range-test analysis pipeline.

Supported log line types
-------------------------
  SWEEP_RX_RESULT  — per-burst receive statistics (RSSI, count, SNR)
  SWEEP_TX_RESULT  — per-burst transmit statistics (sent, throughput, power)
  BURST_END        — burst packet count (fallback for packets_sent)
  MODE_SWITCH      — mode metadata (informational, not emitted as CSV row)
  PKT              — per-packet data (accumulated for stats, not a CSV row)

Usage
-----
  python3 tools/parse_unified_csv.py <log_file> [--gpx <gpx_file>] [--output results.csv]

Exit codes:  0 = success (rows written),  1 = no parseable data,  2 = usage error
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from typing import Optional

# ─── Unified CSV schema ─────────────────────────────────────────────────────

CSV_HEADERS = [
    "timestamp_iso",
    "path",
    "freq_mhz",
    "modulation",
    "bitrate_kbps",
    "spreading_factor",
    "bandwidth_khz",
    "coding_rate",
    "tx_power_dbm",
    "pa_state",
    "distance_m",
    "los",
    "packets_sent",
    "packets_rx",
    "packets_unique",
    "per_percent",
    "throughput_kbps",
    "rssi_avg_dbm",
    "rssi_min_dbm",
    "rssi_max_dbm",
    "snr_avg_db",
    "pkt_size_bytes",
    "uptime_ms",
    "notes",
]


# ─── Data containers ────────────────────────────────────────────────────────

@dataclass
class SweepResult:
    """One row of output — populated from RX+TX join."""
    timestamp_iso: str = ""
    path: str = ""
    freq_mhz: str = ""
    modulation: str = ""
    bitrate_kbps: str = ""
    spreading_factor: str = ""
    bandwidth_khz: str = ""
    coding_rate: str = ""
    tx_power_dbm: str = ""
    pa_state: str = ""
    distance_m: str = ""
    los: str = ""
    packets_sent: str = ""
    packets_rx: str = ""
    packets_unique: str = ""
    per_percent: str = ""
    throughput_kbps: str = ""
    rssi_avg_dbm: str = ""
    rssi_min_dbm: str = ""
    rssi_max_dbm: str = ""
    snr_avg_db: str = ""
    pkt_size_bytes: str = ""
    uptime_ms: str = ""
    notes: str = ""

    def to_dict(self) -> dict:
        return {h: getattr(self, h, "") for h in CSV_HEADERS}


# ─── Parsing helpers ────────────────────────────────────────────────────────

def _parse_kv_fields(parts: list[str]) -> dict:
    """Parse ``key=value`` tokens into a dict, skipping non-kv tokens."""
    out: dict[str, str] = {}
    for tok in parts:
        if "=" in tok:
            k, _, v = tok.partition("=")
            out[k.strip()] = v.strip()
    return out


def _split_log_line(line: str) -> tuple[str, list[str]]:
    """
    Split a log line into (prefix, tokens).

    Handles two formats:
      comma-separated:  ``SWEEP_RX_RESULT,mode=0,type=FLRC,...``
      space-separated:  ``BURST_END mode=0 n=500``
    """
    line = line.strip()
    # Try comma-separated first (our main data lines)
    comma_parts = line.split(",")
    prefix = comma_parts[0].strip()
    # If prefix contains a space, it's actually a space-separated line
    if " " in prefix:
        space_parts = line.split()
        return space_parts[0].strip(), space_parts[1:]
    return prefix, comma_parts[1:]


def _safe_float(val: str) -> Optional[float]:
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_int(val: str) -> Optional[int]:
    try:
        return int(val)
    except (ValueError, TypeError):
        f = _safe_float(val)
        return int(f) if f is not None else None


def parse_sweep_rx(tokens: list[str]) -> Optional[dict]:
    """Parse SWEEP_RX_RESULT comma-separated fields."""
    fields = _parse_kv_fields(tokens)
    if not fields:
        return None
    # Validate we have at least the essential fields
    if "received" not in fields and "rx" not in fields:
        return None
    return fields


def parse_sweep_tx(tokens: list[str]) -> Optional[dict]:
    """Parse SWEEP_TX_RESULT comma-separated fields."""
    fields = _parse_kv_fields(tokens)
    if not fields:
        return None
    if "sent" not in fields:
        return None
    return fields


def parse_burst_end(tokens: list[str]) -> Optional[dict]:
    """Parse ``BURST_END mode=0 n=500`` space-separated fields."""
    fields: dict[str, str] = {}
    for tok in tokens:
        if "=" in tok:
            k, _, v = tok.partition("=")
            fields[k.strip()] = v.strip()
    if "n" not in fields:
        return None
    return fields


def parse_mode_switch(tokens: list[str]) -> Optional[dict]:
    """Parse ``MODE_SWITCH mode=0 type=FLRC freq=2440 bitrate=2600``."""
    fields: dict[str, str] = {}
    for tok in tokens:
        if "=" in tok:
            k, _, v = tok.partition("=")
            fields[k.strip()] = v.strip()
    if "mode" not in fields:
        return None
    return fields


# ─── Field mapping helpers ──────────────────────────────────────────────────

def _map_common_fields(fields: dict, result: SweepResult) -> None:
    """Populate common fields shared by RX and TX results."""
    result.path = fields.get("path", "")
    result.freq_mhz = fields.get("freq", fields.get("freq_mhz", ""))
    result.modulation = fields.get("type", fields.get("modulation", ""))
    result.pa_state = fields.get("pa_state", "")
    result.bandwidth_khz = fields.get(
        "bandwidth_khz", fields.get("bw", "")
    )
    result.bitrate_kbps = fields.get("bitrate", fields.get("bitrate_kbps", ""))
    result.spreading_factor = fields.get("SF", fields.get("spreading_factor", ""))


def _make_key(mode: str, path: str, freq: str) -> tuple:
    """Join key for matching TX↔RX: (mode, path, freq)."""
    return (mode, path, str(freq))


# ─── GPX distance correlation ───────────────────────────────────────────────

class GpxDistance:
    """Distance lookup from a GPX track, matched by elapsed-millis timestamp."""

    def __init__(self, gpx_file: str):
        self.points: list[tuple[float, float, datetime]] = []  # (lat, lon, time)
        self._load(gpx_file)

    def _load(self, gpx_file: str) -> None:
        try:
            import gpxpy  # type: ignore
        except ImportError:
            print(
                f"WARNING: gpxpy not installed — cannot compute distances from {gpx_file}."
                "\n         Install with: pip install gpxpy",
                file=sys.stderr,
            )
            return

        try:
            with open(gpx_file, "r") as f:
                gpx = gpxpy.parse(f)
        except Exception as exc:
            print(f"WARNING: Could not parse GPX file {gpx_file}: {exc}", file=sys.stderr)
            return

        for track in gpx.tracks:
            for segment in track.segments:
                for pt in segment.points:
                    if pt.time:
                        self.points.append((pt.latitude, pt.longitude, pt.time))

        for route in gpx.routes:
            for pt in route.points:
                if pt.time:
                    self.points.append((pt.latitude, pt.longitude, pt.time))

        self.points.sort(key=lambda p: p[2])
        if self.points:
            print(
                f"GPX loaded: {len(self.points)} track points"
                f" from {self.points[0][2].isoformat()} to {self.points[-1][2].isoformat()}",
                file=sys.stderr,
            )

    @property
    def available(self) -> bool:
        return len(self.points) > 0

    def distance_at_seconds(self, elapsed_seconds: float) -> str:
        """
        Return distance (meters) from GPX start at *elapsed_seconds*.

        If no GPX data or timestamp is out of range, returns empty string.
        """
        if not self.points:
            return ""

        try:
            import gpxpy.geo  # type: ignore
        except ImportError:
            return ""

        base_time = self.points[0][2]
        target = base_time + timedelta(seconds=elapsed_seconds)

        # Binary search for closest point
        lo, hi = 0, len(self.points) - 1
        if target <= self.points[0][2]:
            return "0"
        if target >= self.points[-1][2]:
            # Compute total distance up to last point
            total = 0.0
            for i in range(1, len(self.points)):
                lat1, lon1, _ = self.points[i - 1]
                lat2, lon2, _ = self.points[i]
                total += gpxpy.geo.haversine_distance(lat1, lon1, lat2, lon2)
            return f"{total:.1f}"

        while lo < hi:
            mid = (lo + hi) // 2
            if self.points[mid][2] < target:
                lo = mid + 1
            else:
                hi = mid

        # Accumulate distance up to lo
        total = 0.0
        for i in range(1, lo + 1):
            lat1, lon1, _ = self.points[i - 1]
            lat2, lon2, _ = self.points[i]
            total += gpxpy.geo.haversine_distance(lat1, lon1, lat2, lon2)
        return f"{total:.1f}"

    def timestamp_at_seconds(self, elapsed_seconds: float) -> str:
        """Return ISO timestamp from GPX for *elapsed_seconds*, or empty."""
        if not self.points:
            return ""
        base_time = self.points[0][2]
        target = base_time + timedelta(seconds=elapsed_seconds)
        return target.isoformat()


# ─── Main parser ────────────────────────────────────────────────────────────

def parse_log(
    log_file: str,
    gpx: Optional[GpxDistance] = None,
) -> tuple[list[SweepResult], dict]:
    """
    Parse the log file and return (results, stats).

    stats contains counts of each line type parsed/skipped.
    """
    stats: dict = defaultdict(int)
    tx_records: dict[tuple, dict] = {}      # key → TX fields
    burst_end_counts: dict[tuple, int] = {}  # key → sent count fallback
    rx_list: list[tuple[tuple, dict]] = []   # (key, rx_fields)
    pkt_rssi_values: list[int] = []

    try:
        with open(log_file, "r", errors="replace") as f:
            for lineno, raw_line in enumerate(f, 1):
                line = raw_line.rstrip("\n\r")
                if not line.strip():
                    continue

                prefix, tokens = _split_log_line(line)

                if prefix == "SWEEP_RX_RESULT":
                    stats["rx_lines"] += 1
                    fields = parse_sweep_rx(tokens)
                    if fields is None:
                        stats["rx_parse_fail"] += 1
                        print(f"WARNING: line {lineno}: unparseable SWEEP_RX_RESULT: {line[:120]}", file=sys.stderr)
                        continue
                    mode = fields.get("mode", "")
                    key = _make_key(mode, fields.get("path", ""), fields.get("freq", ""))
                    rx_list.append((key, fields))
                    stats["rx_parsed"] += 1

                elif prefix == "SWEEP_TX_RESULT":
                    stats["tx_lines"] += 1
                    fields = parse_sweep_tx(tokens)
                    if fields is None:
                        stats["tx_parse_fail"] += 1
                        print(f"WARNING: line {lineno}: unparseable SWEEP_TX_RESULT: {line[:120]}", file=sys.stderr)
                        continue
                    mode = fields.get("mode", "")
                    key = _make_key(mode, fields.get("path", ""), fields.get("freq", ""))
                    tx_records[key] = fields
                    stats["tx_parsed"] += 1

                elif prefix == "BURST_END":
                    stats["burst_end_lines"] += 1
                    fields = parse_burst_end(tokens)
                    if fields is None:
                        stats["burst_end_parse_fail"] += 1
                        continue
                    # Store as fallback sent-count for this mode
                    mode = fields.get("mode", "")
                    n = _safe_int(fields.get("n", ""))
                    if n is not None:
                        burst_end_counts[mode] = n
                    stats["burst_end_parsed"] += 1

                elif prefix == "MODE_SWITCH":
                    stats["mode_switch_lines"] += 1
                    # Informational only — not emitted as CSV row

                elif prefix == "PKT":
                    stats["pkt_lines"] += 1
                    # PKT,seq,?,rssi — accumulate RSSI for fallback stats
                    pkt_parts = line.split(",")
                    if len(pkt_parts) >= 4:
                        rssi = _safe_int(pkt_parts[-1])
                        if rssi is not None:
                            pkt_rssi_values.append(rssi)

                else:
                    # Skip lines we don't recognise (boot messages, debug, etc.)
                    stats["skipped_other"] += 1

    except FileNotFoundError:
        print(f"ERROR: log file not found: {log_file}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"ERROR reading {log_file}: {exc}", file=sys.stderr)
        sys.exit(1)

    # ─── Join RX with TX to build output rows ───────────────────────────

    results: list[SweepResult] = []

    for key, rx_fields in rx_list:
        row = SweepResult()
        _map_common_fields(rx_fields, row)

        # RX-specific fields
        received = _safe_int(rx_fields.get("received", "")) or 0
        max_seq = _safe_int(rx_fields.get("max_seq", ""))
        row.packets_rx = str(received)
        row.packets_unique = str(max_seq) if max_seq is not None else str(received)

        rssi_avg = _safe_float(rx_fields.get("rssi_avg", ""))
        row.rssi_avg_dbm = f"{rssi_avg:.1f}" if rssi_avg is not None else rx_fields.get("rssi_avg", "")
        row.rssi_min_dbm = rx_fields.get("rssi_min", "")
        row.rssi_max_dbm = rx_fields.get("rssi_max", "")

        snr = rx_fields.get("snr_avg", "")
        row.snr_avg_db = "" if snr.upper() == "NA" else snr

        uptime = rx_fields.get("start_ms", rx_fields.get("uptime_ms", ""))
        row.uptime_ms = uptime

        # ── Join with TX record for sent count, throughput, power ──────
        tx = tx_records.get(key)
        notes_parts: list[str] = []

        if tx:
            sent = _safe_int(tx.get("sent", "")) or 0
            row.packets_sent = str(sent)
            row.throughput_kbps = tx.get("throughput_kbps", "")
            row.pkt_size_bytes = tx.get("pktSize", tx.get("pkt_size", ""))
            power = _safe_float(tx.get("power", ""))
            row.tx_power_dbm = f"{power:.1f}" if power is not None else tx.get("power", "")

            # Fill in modulation/fields from TX if RX was missing them
            if not row.modulation:
                row.modulation = tx.get("type", "")
            if not row.bandwidth_khz:
                row.bandwidth_khz = tx.get("bandwidth_khz", tx.get("bw", ""))
            if not row.bitrate_kbps:
                row.bitrate_kbps = tx.get("bitrate", "")
            if not row.spreading_factor:
                row.spreading_factor = tx.get("SF", "")
            if not row.pa_state:
                row.pa_state = tx.get("pa_state", "")
        else:
            # Try BURST_END as fallback for sent count
            mode_str = str(key[0]) if key else ""
            burst_n = burst_end_counts.get(mode_str)
            if burst_n is not None:
                row.packets_sent = str(burst_n)
            else:
                notes_parts.append("no TX data")

        # ── Compute PER ────────────────────────────────────────────────
        sent_val = _safe_int(row.packets_sent)
        if sent_val and sent_val > 0:
            per = (sent_val - received) / sent_val * 100.0
            row.per_percent = f"{per:.2f}"
        else:
            # Unknown sent count → cannot compute PER
            row.per_percent = ""

        # ── GPX distance correlation ───────────────────────────────────
        if gpx and gpx.available:
            uptime_val = _safe_float(uptime)
            if uptime_val is not None:
                elapsed_sec = uptime_val / 1000.0
                row.distance_m = gpx.distance_at_seconds(elapsed_sec)
                ts = gpx.timestamp_at_seconds(elapsed_sec)
                if ts:
                    row.timestamp_iso = ts
            else:
                row.timestamp_iso = datetime.now(timezone.utc).isoformat()
        else:
            # No GPX — use current time as a fallback timestamp
            row.timestamp_iso = datetime.now(timezone.utc).isoformat()

        if notes_parts:
            row.notes = "; ".join(notes_parts)

        results.append(row)

    # ─── If we have TX records with no matching RX, emit TX-only rows ──
    rx_keys = {key for key, _ in rx_list}
    for key, tx_fields in tx_records.items():
        if key in rx_keys:
            continue  # already joined
        row = SweepResult()
        _map_common_fields(tx_fields, row)
        sent = _safe_int(tx_fields.get("sent", "")) or 0
        row.packets_sent = str(sent)
        row.packets_rx = "0"
        row.per_percent = "100.00"
        row.throughput_kbps = tx_fields.get("throughput_kbps", "")
        row.pkt_size_bytes = tx_fields.get("pktSize", tx_fields.get("pkt_size", ""))
        power = _safe_float(tx_fields.get("power", ""))
        row.tx_power_dbm = f"{power:.1f}" if power is not None else tx_fields.get("power", "")
        row.uptime_ms = tx_fields.get("uptime_ms", "")

        if gpx and gpx.available:
            uptime_val = _safe_float(tx_fields.get("uptime_ms", ""))
            if uptime_val is not None:
                elapsed_sec = uptime_val / 1000.0
                row.distance_m = gpx.distance_at_seconds(elapsed_sec)
                ts = gpx.timestamp_at_seconds(elapsed_sec)
                if ts:
                    row.timestamp_iso = ts
        else:
            row.timestamp_iso = datetime.now(timezone.utc).isoformat()

        row.notes = "TX-only (no RX data)"
        results.append(row)

    stats["total_output_rows"] = len(results)
    stats["pkt_rssi_collected"] = len(pkt_rssi_values)

    return results, dict(stats)


# ─── Output ─────────────────────────────────────────────────────────────────

def write_csv(results: list[SweepResult], output_file: str) -> None:
    """Write results to CSV file."""
    try:
        with open(output_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            writer.writeheader()
            for row in results:
                writer.writerow(row.to_dict())
    except Exception as exc:
        print(f"ERROR writing CSV to {output_file}: {exc}", file=sys.stderr)
        sys.exit(1)


def print_summary(results: list[SweepResult], stats: dict) -> None:
    """Print summary statistics to stderr."""
    print("\n" + "=" * 60, file=sys.stderr)
    print("PARSE SUMMARY", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    print(f"\nLog line stats:", file=sys.stderr)
    for k in sorted(stats):
        print(f"  {k:30s} {stats[k]}", file=sys.stderr)

    print(f"\nOutput rows: {len(results)}", file=sys.stderr)

    if not results:
        print("  (no data rows)", file=sys.stderr)
        return

    # Per-path breakdown
    path_stats: dict[str, dict] = defaultdict(
        lambda: {"count": 0, "rx_sum": 0, "sent_sum": 0, "per_sum": 0.0}
    )
    for r in results:
        p = r.path or "(unknown)"
        ps = path_stats[p]
        ps["count"] += 1
        rx = _safe_int(r.packets_rx)
        sent = _safe_int(r.packets_sent)
        per = _safe_float(r.per_percent)
        if rx:
            ps["rx_sum"] += rx
        if sent:
            ps["sent_sum"] += sent
        if per is not None:
            ps["per_sum"] += per

    print(f"\nPer-path breakdown:", file=sys.stderr)
    print(f"  {'Path':<16s} {'Rows':>5s} {'TotalRx':>8s} {'TotalSent':>10s} {'AvgPER':>8s}", file=sys.stderr)
    print(f"  {'-'*16} {'-'*5} {'-'*8} {'-'*10} {'-'*8}", file=sys.stderr)
    for path in sorted(path_stats):
        ps = path_stats[path]
        avg_per = ps["per_sum"] / ps["count"] if ps["count"] else 0
        print(
            f"  {path:<16s} {ps['count']:>5d} {ps['rx_sum']:>8d} {ps['sent_sum']:>10d} {avg_per:>7.1f}%",
            file=sys.stderr,
        )

    print(file=sys.stderr)


# ─── CLI ────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert LR2021 sweep serial logs to unified CSV.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python3 tools/parse_unified_csv.py sweep_log.txt
  python3 tools/parse_unified_csv.py sweep_log.txt --gpx track.gpx --output results.csv
""",
    )
    parser.add_argument("log_file", help="Path to serial log file")
    parser.add_argument(
        "--gpx", default=None, help="Optional GPX track file for distance correlation"
    )
    parser.add_argument(
        "--output", "-o", default=None, help="Output CSV path (default: <log_file>.csv)"
    )
    args = parser.parse_args()

    if not os.path.isfile(args.log_file):
        print(f"ERROR: log file not found: {args.log_file}", file=sys.stderr)
        return 2

    output_file = args.output
    if output_file is None:
        base, _ = os.path.splitext(args.log_file)
        output_file = base + "_unified.csv"

    # Load GPX if provided
    gpx = None
    if args.gpx:
        if not os.path.isfile(args.gpx):
            print(f"WARNING: GPX file not found: {args.gpx} — skipping distance correlation", file=sys.stderr)
        else:
            gpx = GpxDistance(args.gpx)

    # Parse
    results, stats = parse_log(args.log_file, gpx)

    # Write CSV
    if results:
        write_csv(results, output_file)
        print(f"Wrote {len(results)} rows to {output_file}", file=sys.stderr)
    else:
        print("WARNING: no parseable data rows found in log.", file=sys.stderr)

    # Summary
    print_summary(results, stats)

    return 0 if results else 1


if __name__ == "__main__":
    sys.exit(main())
