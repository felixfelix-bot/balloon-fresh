#!/usr/bin/env python3
"""
measure_goodput.py — LR2021 FLRC goodput measurement from RX board UART.

Connects to the RX board via serial, captures incoming packets for a
configurable duration, and computes:
  - Packet count, unique count, duplicate count
  - Packet loss % (based on sequence number gaps)
  - Effective throughput (kbps)
  - Average / min / max RSSI (if the RX firmware reports it)
  - Inter-packet arrival time: min / max / avg (latency proxy)

Usage:
    python3 scripts/measure_goodput.py --port /dev/ttyACM0 --duration 10 --payload-size 255
    python3 scripts/measure_goodput.py --port /dev/ttyACM2 --duration 30 --output results.json
    python3 scripts/measure_goodput.py --port /dev/ttyACM2 --duration 10 --reset-board

The script parses ESP-IDF log output from the RX board. It handles:
  - Per-packet lines:    I (TIMESTAMP) FLRC: COUNT,SEQ
  - Enhanced per-packet:  I (TIMESTAMP) FLRC: PKT,COUNT,SEQ,RSSI
  - Summary line:         RESULT_RX,rx=N,...
  - TX stats (if visible): CONT_TX_STATS,sent=N,...

RSSI values are expected unsigned from the radio; the script negates them
for dBm display (per AGENTS.md: "RSSI is unsigned — negate for dBm").
"""

import argparse
import json
import os
import re
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

# ─── BoardSerial import ──────────────────────────────────────────────
TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS_DIR))

try:
    from board_serial import BoardSerial  # noqa: E402
except ImportError:
    # Fallback: BoardSerial not available (e.g., running outside balloon repo)
    try:
        import serial as pyserial
        BoardSerial = pyserial.Serial
        print("WARNING: board-serial.py not found; using plain pyserial "
              "(board lock NOT enforced).", file=sys.stderr)
    except ImportError:
        print("ERROR: pyserial not installed. Run: pip install pyserial",
              file=sys.stderr)
        sys.exit(1)

import serial as pyserial  # for SerialException type checking


# ─── ESP-IDF log line parser ─────────────────────────────────────────
# Matches: I (12345) TAG: content   or   I (12345) TAG: content\r\n
# Also matches raw lines without the ESP-IDF prefix.
LOG_RE = re.compile(
    r'^[IWE] \((\d+)\) (\w+): (.*)$'
)

# Per-packet formats:
#   "COUNT,SEQ"                        (existing main.cpp)
#   "PKT,COUNT,SEQ"                    (enhanced, no RSSI)
#   "PKT,COUNT,SEQ,RSSI"               (enhanced, with RSSI)
PKT_SIMPLE_RE = re.compile(r'^(\d+),(\d+)$')
PKT_ENHANCED_RE = re.compile(r'^PKT,(\d+),(\d+)(?:,(\d+))?$')

# Summary formats:
RESULT_RX_RE = re.compile(r'^RESULT_RX,(.+)$')
CONT_TX_STATS_RE = re.compile(r'^CONT_TX_STATS,(.+)$')
CONT_TX_START_RE = re.compile(r'^CONT_TX_START,(.+)$')

# DEADBEEF end marker
DEADBEEF_RE = re.compile(r'DEADBEEF|RX_END')


def parse_kv(s):
    """Parse key=value,key=value string into a dict."""
    result = {}
    for part in s.split(','):
        part = part.strip()
        if '=' in part:
            k, v = part.split('=', 1)
            result[k.strip()] = v.strip()
    return result


def parse_log_line(line):
    """Parse a single UART line into (timestamp_ms, tag, content) or None.

    Strips ESP-IDF log prefix if present, otherwise treats the whole line
    as content with timestamp=None.
    """
    line = line.strip()
    if not line:
        return None

    m = LOG_RE.match(line)
    if m:
        return int(m.group(1)), m.group(2), m.group(3)

    # No ESP-IDF prefix — try to parse content directly
    return None, None, line


class GoodputMeasurement:
    """Collects and computes goodput metrics from RX board output."""

    def __init__(self, payload_size):
        self.payload_size = payload_size
        self.packets = []           # list of dicts: {rx_ts, seq, rssi, esp_ts}
        self.tx_stats = {}          # latest TX board stats (if visible)
        self.tx_start = {}          # TX start info
        self.result_rx = {}         # RESULT_RX summary from firmware
        self.capture_start = None   # wall-clock capture start
        self.capture_end = None     # wall-clock capture end
        self.deadbeef_seen = False

    def process_line(self, line, rx_wall_ts):
        """Process one UART line, extracting packet/metric data."""
        esp_ts, tag, content = parse_log_line(line)
        if content is None:
            return

        # Per-packet data
        m = PKT_SIMPLE_RE.match(content)
        if m:
            count = int(m.group(1))
            seq = int(m.group(2))
            self.packets.append({
                'rx_ts': rx_wall_ts,
                'seq': seq,
                'count': count,
                'esp_ts': esp_ts,
                'rssi': None,
            })
            return

        m = PKT_ENHANCED_RE.match(content)
        if m:
            count = int(m.group(1))
            seq = int(m.group(2))
            rssi_raw = int(m.group(3)) if m.group(3) else None
            rssi_dbm = -rssi_raw if rssi_raw is not None else None
            self.packets.append({
                'rx_ts': rx_wall_ts,
                'seq': seq,
                'count': count,
                'esp_ts': esp_ts,
                'rssi': rssi_dbm,
            })
            return

        # SUMMARY: RESULT_RX
        m = RESULT_RX_RE.match(content)
        if m:
            self.result_rx = parse_kv(m.group(1))
            return

        # TX STATS (if TX board output is on same serial — unlikely but handle)
        m = CONT_TX_STATS_RE.match(content)
        if m:
            stats = parse_kv(m.group(1))
            stats['_timestamp'] = rx_wall_ts
            self.tx_stats = stats
            return

        m = CONT_TX_START_RE.match(content)
        if m:
            self.tx_start = parse_kv(m.group(1))
            return

        # DEADBEEF marker
        if DEADBEEF_RE.search(content):
            self.deadbeef_seen = True
            return

    def compute_metrics(self):
        """Compute goodput metrics from collected packet data."""
        if not self.packets:
            return {
                'packets_received': 0,
                'error': 'No packets received during capture window.',
            }

        seqs = [p['seq'] for p in self.packets]
        rssi_values = [p['rssi'] for p in self.packets if p['rssi'] is not None]
        timestamps = [p['rx_ts'] for p in self.packets]

        # Unique sequence numbers
        unique_seqs = sorted(set(seqs))
        num_unique = len(unique_seqs)
        num_received = len(seqs)
        num_duplicates = num_received - num_unique

        # Packet loss estimation from sequence gaps
        min_seq = min(seqs)
        max_seq = max(seqs)
        expected_range = max_seq - min_seq + 1
        # Count gaps: missing sequence numbers in [min_seq, max_seq]
        seq_set = set(seqs)
        missing = [s for s in range(min_seq, max_seq + 1) if s not in seq_set]
        num_lost = len(missing)
        loss_pct = (100.0 * num_lost / expected_range) if expected_range > 0 else 0.0

        # Throughput calculation
        capture_duration_ms = 0
        if self.capture_start and self.capture_end:
            capture_duration_ms = (self.capture_end - self.capture_start) * 1000.0
        elif len(timestamps) >= 2:
            capture_duration_ms = (timestamps[-1] - timestamps[0]) * 1000.0

        effective_throughput_kbps = 0.0
        if capture_duration_ms > 0:
            effective_throughput_kbps = (
                (num_received * self.payload_size * 8.0) / capture_duration_ms
            )

        # Inter-packet arrival times (latency proxy)
        inter_pkt_times_ms = []
        if len(timestamps) >= 2:
            for i in range(1, len(timestamps)):
                delta_ms = (timestamps[i] - timestamps[i-1]) * 1000.0
                inter_pkt_times_ms.append(delta_ms)

        min_iat = min(inter_pkt_times_ms) if inter_pkt_times_ms else None
        max_iat = max(inter_pkt_times_ms) if inter_pkt_times_ms else None
        avg_iat = statistics.mean(inter_pkt_times_ms) if inter_pkt_times_ms else None
        stdev_iat = statistics.stdev(inter_pkt_times_ms) if len(inter_pkt_times_ms) >= 2 else None

        # RSSI stats
        avg_rssi = statistics.mean(rssi_values) if rssi_values else None
        min_rssi = min(rssi_values) if rssi_values else None
        max_rssi = max(rssi_values) if rssi_values else None

        return {
            # Counts
            'packets_received': num_received,
            'packets_unique': num_unique,
            'duplicates': num_duplicates,
            # Loss
            'packets_lost': num_lost,
            'expected_in_range': expected_range,
            'loss_pct': round(loss_pct, 2),
            'missing_sequences': missing[:50],  # cap to avoid huge output
            'missing_count_total': num_lost,
            # Sequence range
            'min_seq': min_seq,
            'max_seq': max_seq,
            # Throughput
            'effective_throughput_kbps': round(effective_throughput_kbps, 1),
            'capture_duration_ms': round(capture_duration_ms, 1),
            'payload_size_bytes': self.payload_size,
            'payload_bits_total': num_received * self.payload_size * 8,
            # Inter-packet arrival time (latency proxy)
            'min_iat_ms': round(min_iat, 3) if min_iat is not None else None,
            'max_iat_ms': round(max_iat, 3) if max_iat is not None else None,
            'avg_iat_ms': round(avg_iat, 3) if avg_iat is not None else None,
            'stdev_iat_ms': round(stdev_iat, 3) if stdev_iat is not None else None,
            # RSSI
            'avg_rssi_dbm': round(avg_rssi, 1) if avg_rssi is not None else None,
            'min_rssi_dbm': round(min_rssi, 1) if min_rssi is not None else None,
            'max_rssi_dbm': round(max_rssi, 1) if max_rssi is not None else None,
            # TX stats (if captured)
            'tx_stats': self.tx_stats if self.tx_stats else None,
            'tx_start_info': self.tx_start if self.tx_start else None,
            # Firmware summary (if captured)
            'firmware_result_rx': self.result_rx if self.result_rx else None,
            'deadbeef_seen': self.deadbeef_seen,
            # Metadata
            'timestamp': datetime.now().isoformat(),
        }


def reset_board(ser):
    """Toggle DTR/RTS to reset an ESP32-C3 board (USB CDC/JTAG)."""
    try:
        ser.dtr = False
        ser.rts = True
        time.sleep(0.1)
        ser.dtr = True
        ser.rts = False
        time.sleep(0.1)
        ser.dtr = False
    except Exception as e:
        print(f"  (board reset via DTR/RTS failed: {e})")


def capture_packets(port, duration, baud, payload_size, reset, quiet=False):
    """Capture packets from RX board for specified duration."""
    print(f"Opening {port} at {baud} baud...")
    ser = BoardSerial(port, baud, timeout=0.1)
    time.sleep(0.5)

    # Flush any existing data
    while ser.in_waiting:
        ser.read(ser.in_waiting)

    # Optionally reset board to restart RX mode
    if reset:
        print("Resetting RX board (DTR/RTS toggle)...")
        reset_board(ser)
        time.sleep(3)  # Wait for boot + radio init
        while ser.in_waiting:
            ser.read(ser.in_waiting)  # flush boot messages

    measurement = GoodputMeasurement(payload_size)

    print(f"Capturing for {duration}s...")
    print(f"  Port: {port}")
    print(f"  Payload: {payload_size} bytes")
    print(f"  Duration: {duration}s")

    start_time = time.time()
    measurement.capture_start = start_time
    last_report = start_time
    pkt_count_display = 0

    while time.time() - start_time < duration:
        if ser.in_waiting:
            data = ser.read(ser.in_waiting)
            if data:
                text = data.decode('utf-8', errors='replace')
                now = time.time()
                for line in text.split('\n'):
                    if line.strip():
                        measurement.process_line(line, now)
                        # Quick packet count for progress display
                        if re.match(r'^[IWE] \(\d+\) \w+: (\d+),\d+', line) or \
                           re.match(r'^[IWE] \(\d+\) \w+: PKT,', line):
                            pkt_count_display += 1

        # Progress report every 2 seconds
        elapsed = time.time() - start_time
        if time.time() - last_report >= 2.0:
            print(f"  [{elapsed:.0f}s] {pkt_count_display} packets captured")
            last_report = time.time()
        else:
            time.sleep(0.01)

    measurement.capture_end = time.time()
    ser.close()
    print(f"  [{duration}s] Capture complete: {pkt_count_display} packets total")

    return measurement


def print_summary(metrics):
    """Print human-readable summary of goodput metrics."""
    print(f"\n{'=' * 60}")
    print(f"  GOODPUT MEASUREMENT RESULTS")
    print(f"{'=' * 60}")

    if 'error' in metrics:
        print(f"  ERROR: {metrics['error']}")
        print(f"{'=' * 60}\n")
        return

    print(f"  Packets received:   {metrics['packets_received']:,}")
    print(f"  Unique packets:     {metrics['packets_unique']:,}")
    print(f"  Duplicates:         {metrics['duplicates']:,}")
    print(f"")
    print(f"  Packet loss:        {metrics['packets_lost']:,} / "
          f"{metrics['expected_in_range']:,} "
          f"({metrics['loss_pct']:.2f}%)")
    print(f"  Sequence range:     {metrics['min_seq']} – {metrics['max_seq']}")
    print(f"")
    print(f"  Payload size:       {metrics['payload_size_bytes']} bytes")
    print(f"  Total data:         {metrics['payload_bits_total']:,} bits")
    print(f"  Duration:           {metrics['capture_duration_ms']:.0f} ms")
    print(f"  THROUGHPUT:         {metrics['effective_throughput_kbps']:.1f} kbps")
    print(f"")
    print(f"  Inter-packet timing (latency proxy):")
    iat_fields = [
        ('    Min', 'min_iat_ms'),
        ('    Max', 'max_iat_ms'),
        ('    Avg', 'avg_iat_ms'),
        ('    StDev', 'stdev_iat_ms'),
    ]
    any_iat = False
    for label, key in iat_fields:
        val = metrics.get(key)
        if val is not None:
            print(f"{label}: {val:.3f} ms")
            any_iat = True
    if not any_iat:
        print(f"  (insufficient data)")

    print(f"")
    print(f"  RSSI:")
    rssi_fields = [
        ('    Average', 'avg_rssi_dbm'),
        ('    Min', 'min_rssi_dbm'),
        ('    Max', 'max_rssi_dbm'),
    ]
    any_rssi = False
    for label, key in rssi_fields:
        val = metrics.get(key)
        if val is not None:
            print(f"{label}: {val:.1f} dBm")
            any_rssi = True
    if not any_rssi:
        print(f"  (not available — RX firmware does not report RSSI)")

    if metrics.get('tx_stats'):
        print(f"")
        print(f"  TX board stats (if visible):")
        for k, v in metrics['tx_stats'].items():
            if k != '_timestamp':
                print(f"    {k}: {v}")

    if metrics.get('firmware_result_rx'):
        print(f"")
        print(f"  Firmware RESULT_RX:")
        for k, v in metrics['firmware_result_rx'].items():
            print(f"    {k}: {v}")

    print(f"{'=' * 60}\n")


def main():
    parser = argparse.ArgumentParser(
        description='Measure LR2021 FLRC goodput from RX board UART output.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 10-second capture at 255-byte payload
  python3 scripts/measure_goodput.py --port /dev/ttyACM0 --duration 10

  # 30-second capture, save JSON results
  python3 scripts/measure_goodput.py --port /dev/ttyACM2 --duration 30 --output results.json

  # Reset RX board before capture
  python3 scripts/measure_goodput.py --port /dev/ttyACM2 --duration 10 --reset-board

  # Non-standard payload size
  python3 scripts/measure_goodput.py --port /dev/ttyACM2 --duration 10 --payload-size 64
        """,
    )
    parser.add_argument('--port', '-p', required=True,
                        help='Serial port for RX board (e.g. /dev/ttyACM0)')
    parser.add_argument('--duration', '-d', type=int, default=10,
                        help='Capture duration in seconds (default: 10)')
    parser.add_argument('--payload-size', type=int, default=255,
                        choices=[32, 64, 128, 255],
                        help='Expected payload size in bytes (default: 255)')
    parser.add_argument('--baud', type=int, default=115200,
                        help='Serial baud rate (default: 115200)')
    parser.add_argument('--output', '-o', type=str, default=None,
                        help='Output JSON results to file')
    parser.add_argument('--reset-board', action='store_true',
                        help='Toggle DTR/RTS to reset the RX board before capture')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='Suppress progress output')

    args = parser.parse_args()

    # Validate duration
    if args.duration < 1:
        print(f"ERROR: duration must be at least 1 second", file=sys.stderr)
        sys.exit(1)

    # Capture
    try:
        measurement = capture_packets(
            port=args.port,
            duration=args.duration,
            baud=args.baud,
            payload_size=args.payload_size,
            reset=args.reset_board,
            quiet=args.quiet,
        )
    except PermissionError as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except pyserial.SerialException as e:
        print(f"\nERROR: Could not open {args.port}: {e}", file=sys.stderr)
        sys.exit(1)

    # Compute metrics
    metrics = measurement.compute_metrics()

    # Print human-readable summary
    print_summary(metrics)

    # Output JSON
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(metrics, f, indent=2)
        print(f"JSON results saved to: {output_path}")

    # Also print compact JSON to stdout for piping
    print("RESULT_JSON:")
    print(json.dumps(metrics))

    # Exit code: 0 if packets received, 1 if none
    sys.exit(0 if metrics['packets_received'] > 0 else 1)


if __name__ == '__main__':
    main()
