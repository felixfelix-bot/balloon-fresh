#!/usr/bin/env python3
"""
Range Test Runner — drives configurable FLRC TX+RX firmware for outdoor
distance/power/packet-size/frequency sweeps.

Usage:
  # Flash configurable firmware to both boards (one-time, at desk)
  python3 scripts/range_test_runner.py flash

  # Single test point (operator sets distance physically, then runs)
  python3 scripts/range_test_runner.py test --distance 50 --power 12

  # Full distance sweep (10m, 25m, 50m, 100m)
  python3 scripts/range_test_runner.py sweep-distance 10 25 50 100

  # TX power sweep at fixed distance
  python3 scripts/range_test_runner.py sweep-power --distance 50 0 3 6 9 12

  # Packet size sweep at fixed distance
  python3 scripts/range_test_runner.py sweep-pktlen --distance 50 16 32 64 128 255

  # Frequency sweep at fixed distance
  python3 scripts/range_test_runner.py sweep-freq --distance 10 2400 2422 2440 2462 2480

Board serials (auto-detected):
  TX: E663B035977F242D   (Pico with LR2021)
  RX: E663B035973B8332   (Pico with LR2021)

Results logged to: docs/range-test-results-YYYY-MM-DD.md
"""
import argparse
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import serial
except ImportError:
    print("ERROR: pyserial not installed. Run: pip install pyserial")
    sys.exit(1)

# ─── Constants ────────────────────────────────────────────────────────
TX_SERIAL = "E663B035977F242D"
RX_SERIAL = "E663B035973B8332"
BAUD = 115200
DEFAULT_PKT_COUNT = 1000
DEFAULT_PKT_SIZE = 255
DEFAULT_FREQ = 2440.0
DEFAULT_POWER = 12

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / "docs"
MUTEX_SCRIPT = Path.home() / "repos" / "balloon-fresh" / "tools" / "balloon-board-lock.py"
FIRMWARE_DIR = REPO_ROOT / "firmware" / "rp2040"


# ─── Board discovery ─────────────────────────────────────────────────
def find_port(serial_substr: str) -> str | None:
    """Find USB serial port by serial number substring."""
    import glob
    for port in sorted(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*")):
        try:
            info = subprocess.check_output(
                ["udevadm", "info", "--query=property", port],
                text=True, stderr=subprocess.DEVNULL
            )
            if serial_substr in info:
                return port
        except Exception:
            continue
    return None


def discover_ports():
    """Find TX and RX ports. Returns (tx_port, rx_port) or exits."""
    tx = find_port(TX_SERIAL)
    rx = find_port(RX_SERIAL)
    if not tx:
        print(f"ERROR: TX board ({TX_SERIAL}) not found. Check USB connection.")
    if not rx:
        print(f"ERROR: RX board ({RX_SERIAL}) not found. Check USB connection.")
    if not tx or not rx:
        print("\nConnected devices:")
        import glob
        for p in sorted(glob.glob("/dev/ttyACM*")):
            print(f"  {p}")
        sys.exit(1)
    print(f"TX: {tx}  RX: {rx}")
    return tx, rx


# ─── Serial communication ────────────────────────────────────────────
class Board:
    """Wraps a serial connection to an RP2040 board."""

    def __init__(self, port: str, name: str):
        self.port = port
        self.name = name
        self.ser = serial.Serial(port, BAUD, timeout=0.1)
        time.sleep(0.5)
        self.ser.read(4096)  # flush boot messages

    def send(self, cmd: str):
        """Send a command line."""
        self.ser.write(f"{cmd}\n".encode())
        self.ser.flush()

    def read_until(self, pattern: str, timeout: float = 60.0) -> str | None:
        """Read lines until one matches regex pattern. Returns matched line or None."""
        regex = re.compile(pattern)
        deadline = time.time() + timeout
        buf = ""
        while time.time() < deadline:
            data = self.ser.read(4096)
            if data:
                text = data.decode("ascii", errors="replace")
                buf += text
                for line in buf.split("\n"):
                    line = line.strip()
                    if line:
                        print(f"  [{self.name}] {line}")
                    if regex.search(line):
                        return line
                # Keep last partial line
                buf = buf.split("\n")[-1] if "\n" in buf else buf
            time.sleep(0.05)
        return None

    def wait_result(self, timeout: float = 120.0) -> dict | None:
        """Wait for RESULT_TX or RESULT_RX line. Parse into dict."""
        line = self.read_until(r"RESULT_(?:TX|RX),", timeout=timeout)
        if not line:
            return None
        # Parse: RESULT_TX,key=val,key=val,...
        parts = line.split(",", 1)
        if len(parts) < 2:
            return None
        result = {}
        for kv in parts[1].split(","):
            if "=" in kv:
                k, v = kv.split("=", 1)
                k = k.strip()
                try:
                    result[k] = float(v)
                except ValueError:
                    result[k] = v
        return result

    def close(self):
        self.ser.close()


# ─── Mutex lock ──────────────────────────────────────────────────────
def acquire_lock():
    if not MUTEX_SCRIPT.exists():
        return  # skip if not available
    r = subprocess.run(
        [sys.executable, str(MUTEX_SCRIPT), "acquire", "both",
         "--purpose", "range-test-runner", "--timeout", "30"],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        print(f"WARNING: mutex acquire failed: {r.stdout.strip()}")
        print("Continuing anyway...")


def release_lock():
    if not MUTEX_SCRIPT.exists():
        return
    subprocess.run(
        [sys.executable, str(MUTEX_SCRIPT), "release", "both"],
        capture_output=True, text=True
    )


# ─── Flash firmware ──────────────────────────────────────────────────
def flash_boards():
    """Flash configurable firmware to both boards."""
    tx_port, rx_port = discover_ports()
    acquire_lock()
    try:
        for env, port, name in [
            ("rp2040-range-tx", tx_port, "TX"),
            ("rp2040-range-rx", rx_port, "RX"),
        ]:
            print(f"\n{'='*50}")
            print(f"Flashing {name} ({env}) to {port}...")
            print(f"{'='*50}")
            r = subprocess.run(
                ["pio", "run", "-e", env, "-t", "upload",
                 "--upload-port", port],
                cwd=str(FIRMWARE_DIR),
                timeout=120,
            )
            if r.returncode != 0:
                print(f"ERROR: flash failed for {name}")
                sys.exit(1)
            print(f"{name} flashed OK.")
            time.sleep(3)  # let board reboot
    finally:
        release_lock()
    print("\nBoth boards flashed. Verify with: python3 scripts/range_test_runner.py status")


def check_status():
    """Send STATUS command to both boards."""
    tx_port, rx_port = discover_ports()
    tx = Board(tx_port, "TX")
    rx = Board(rx_port, "RX")
    try:
        tx.send("STATUS")
        time.sleep(1)
        rx.send("STATUS")
        time.sleep(2)
    finally:
        tx.close()
        rx.close()


# ─── Test execution ──────────────────────────────────────────────────
def run_test_point(
    tx: Board, rx: Board,
    distance_m: float = 0,
    power_dbm: int = DEFAULT_POWER,
    pkt_size: int = DEFAULT_PKT_SIZE,
    freq_mhz: float = DEFAULT_FREQ,
    pkt_count: int = DEFAULT_PKT_COUNT,
    antenna: str = "wire_dipole",
    orientation: str = "both_vert",
    environment: str = "unknown",
    notes: str = "",
) -> dict:
    """
    Run a single TX→RX test point.
    Arms RX first, then triggers TX, captures results from both.
    """
    # Configure TX
    tx.send(f"POWER {power_dbm}")
    time.sleep(0.3)
    tx.send(f"PKTLEN {pkt_size}")
    time.sleep(0.3)
    tx.send(f"FREQ {freq_mhz}")
    time.sleep(0.5)
    tx.send(f"COUNT {pkt_count}")
    time.sleep(0.2)

    # Configure RX (must match TX: freq + pktlen)
    rx.send(f"FREQ {freq_mhz}")
    time.sleep(0.3)
    rx.send(f"PKTLEN {pkt_size}")
    time.sleep(0.5)

    print(f"\n--- Test: d={distance_m}m pwr={power_dbm}dBm pkt={pkt_size}B "
          f"freq={freq_mhz}MHz count={pkt_count} ---")

    # Arm RX (start listening)
    rx.send("LISTEN")
    time.sleep(2)  # let RX enter receive mode

    # Trigger TX
    tx.send("RUN")

    # Wait for results (RX has DEADBEEF marker, finishes first)
    rx_result = rx.wait_result(timeout=pkt_count * 0.01 + 30)
    tx_result = tx.wait_result(timeout=30)

    # Parse results
    sent = int(tx_result.get("sent", pkt_count)) if tx_result else pkt_count
    received = int(rx_result.get("rx", 0)) if rx_result else 0
    unique = int(rx_result.get("unique", received)) if rx_result else received
    lost = int(rx_result.get("lost", sent - received)) if rx_result else (sent - received)
    loss_pct = (100.0 * lost / sent) if sent > 0 else 100.0
    throughput = float(rx_result.get("throughput_kbps", 0)) if rx_result else 0
    elapsed = int(rx_result.get("elapsed_ms", 0)) if rx_result else 0

    result = {
        "distance_m": distance_m,
        "power_dbm": power_dbm,
        "pkt_size": pkt_size,
        "freq_mhz": freq_mhz,
        "mode": "FLRC2600",
        "antenna": antenna,
        "orientation": orientation,
        "packets_sent": sent,
        "packets_rx": received,
        "unique_rx": unique,
        "loss_pct": round(loss_pct, 2),
        "throughput_kbps": round(throughput, 1),
        "elapsed_ms": elapsed,
        "environment": environment,
        "notes": notes,
    }

    print(f"\n>>> RESULT: rx={received}/{sent} ({loss_pct:.1f}% loss) "
          f"tput={throughput:.0f}kbps")
    return result


# ─── Result logging ──────────────────────────────────────────────────
def format_result_line(r: dict) -> str:
    """Format a single result as RANGE_TEST line."""
    date = datetime.now().strftime("%Y-%m-%d")
    return (
        f"RANGE_TEST,date={date},"
        f"distance_m={r['distance_m']},"
        f"power_dbm={r['power_dbm']},"
        f"pkt_size={r['pkt_size']},"
        f"mode={r['mode']},"
        f"freq_mhz={r['freq_mhz']},"
        f"antenna={r['antenna']},"
        f"orientation={r['orientation']},"
        f"packets_sent={r['packets_sent']},"
        f"packets_rx={r['packets_rx']},"
        f"loss_pct={r['loss_pct']},"
        f"throughput_kbps={r['throughput_kbps']},"
        f"environment={r['environment']},"
        f"notes={r['notes']}"
    )


def save_results(results: list[dict], sweep_name: str):
    """Append results to daily results file."""
    RESULTS_DIR.mkdir(exist_ok=True)
    date = datetime.now().strftime("%Y-%m-%d")
    filepath = RESULTS_DIR / f"range-test-results-{date}.md"

    new_file = not filepath.exists()
    with open(filepath, "a") as f:
        if new_file:
            f.write(f"# Range Test Results — {date}\n\n")
            f.write("## Format\n")
            f.write("```\n")
            f.write("RANGE_TEST,date=YYYY-MM-DD,distance_m=X,power_dbm=Y,...\n")
            f.write("```\n\n")
            f.write("## Data\n\n")
            f.write("```\n")

        f.write(f"# {sweep_name} — {datetime.now().strftime('%H:%M:%S')}\n")
        for r in results:
            f.write(format_result_line(r) + "\n")
        f.write("\n")

    print(f"\nResults saved to: {filepath}")


# ─── CLI ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="LR2021 FLRC Range Test Runner"
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("flash", help="Flash configurable firmware to both boards")
    sub.add_parser("status", help="Query STATUS from both boards")

    p_test = sub.add_parser("test", help="Run single test point")
    p_test.add_argument("--distance", type=float, default=0, help="Distance in meters")
    p_test.add_argument("--power", type=int, default=DEFAULT_POWER)
    p_test.add_argument("--pktlen", type=int, default=DEFAULT_PKT_SIZE)
    p_test.add_argument("--freq", type=float, default=DEFAULT_FREQ)
    p_test.add_argument("--count", type=int, default=DEFAULT_PKT_COUNT)
    p_test.add_argument("--antenna", default="wire_dipole")
    p_test.add_argument("--orientation", default="both_vert")
    p_test.add_argument("--env", default="unknown")
    p_test.add_argument("--notes", default="")

    p_dist = sub.add_parser("sweep-distance", help="Distance sweep")
    p_dist.add_argument("distances", type=float, nargs="+")
    p_dist.add_argument("--power", type=int, default=DEFAULT_POWER)
    p_dist.add_argument("--pktlen", type=int, default=DEFAULT_PKT_SIZE)
    p_dist.add_argument("--freq", type=float, default=DEFAULT_FREQ)
    p_dist.add_argument("--count", type=int, default=DEFAULT_PKT_COUNT)
    p_dist.add_argument("--env", default="outdoor_LOS")
    p_dist.add_argument("--antenna", default="wire_dipole")

    p_pwr = sub.add_parser("sweep-power", help="TX power sweep at fixed distance")
    p_pwr.add_argument("--distance", type=float, required=True)
    p_pwr.add_argument("powers", type=float, nargs="+")
    p_pwr.add_argument("--pktlen", type=int, default=DEFAULT_PKT_SIZE)
    p_pwr.add_argument("--freq", type=float, default=DEFAULT_FREQ)
    p_pwr.add_argument("--count", type=int, default=DEFAULT_PKT_COUNT)
    p_pwr.add_argument("--env", default="outdoor_LOS")

    p_pkt = sub.add_parser("sweep-pktlen", help="Packet size sweep at fixed distance")
    p_pkt.add_argument("--distance", type=float, required=True)
    p_pkt.add_argument("pktlens", type=int, nargs="+")
    p_pkt.add_argument("--power", type=int, default=DEFAULT_POWER)
    p_pkt.add_argument("--freq", type=float, default=DEFAULT_FREQ)
    p_pkt.add_argument("--count", type=int, default=DEFAULT_PKT_COUNT)
    p_pkt.add_argument("--env", default="outdoor_LOS")

    p_freq = sub.add_parser("sweep-freq", help="Frequency sweep at fixed distance")
    p_freq.add_argument("--distance", type=float, required=True)
    p_freq.add_argument("freqs", type=float, nargs="+")
    p_freq.add_argument("--power", type=int, default=DEFAULT_POWER)
    p_freq.add_argument("--pktlen", type=int, default=DEFAULT_PKT_SIZE)
    p_freq.add_argument("--count", type=int, default=DEFAULT_PKT_COUNT)
    p_freq.add_argument("--env", default="outdoor_LOS")

    args = parser.parse_args()

    if args.command == "flash":
        flash_boards()
        return

    if args.command == "status":
        check_status()
        return

    # All test commands need boards
    tx_port, rx_port = discover_ports()
    acquire_lock()
    try:
        tx = Board(tx_port, "TX")
        rx = Board(rx_port, "RX")
        results = []

        if args.command == "test":
            r = run_test_point(
                tx, rx,
                distance_m=args.distance,
                power_dbm=args.power,
                pkt_size=args.pktlen,
                freq_mhz=args.freq,
                pkt_count=args.count,
                antenna=args.antenna,
                orientation=args.orientation,
                environment=args.env,
                notes=args.notes,
            )
            results.append(r)

        elif args.command == "sweep-distance":
            for d in args.distances:
                input(f"\n>>> Position boards at {d}m, press ENTER to test...")
                r = run_test_point(
                    tx, rx, distance_m=d, power_dbm=args.power,
                    pkt_size=args.pktlen, freq_mhz=args.freq,
                    pkt_count=args.count, environment=args.env,
                    antenna=args.antenna,
                )
                results.append(r)

        elif args.command == "sweep-power":
            for pwr in args.powers:
                r = run_test_point(
                    tx, rx, distance_m=args.distance, power_dbm=int(pwr),
                    pkt_size=args.pktlen, freq_mhz=args.freq,
                    pkt_count=args.count, environment=args.env,
                )
                results.append(r)
                time.sleep(2)

        elif args.command == "sweep-pktlen":
            for plen in args.pktlens:
                r = run_test_point(
                    tx, rx, distance_m=args.distance, power_dbm=args.power,
                    pkt_size=plen, freq_mhz=args.freq,
                    pkt_count=args.count, environment=args.env,
                )
                results.append(r)
                time.sleep(2)

        elif args.command == "sweep-freq":
            for freq in args.freqs:
                r = run_test_point(
                    tx, rx, distance_m=args.distance, power_dbm=args.power,
                    pkt_size=args.pktlen, freq_mhz=freq,
                    pkt_count=args.count, environment=args.env,
                )
                results.append(r)
                time.sleep(2)

        else:
            parser.print_help()
            return

        tx.close()
        rx.close()

        if results:
            save_results(results, args.command)

    finally:
        release_lock()


if __name__ == "__main__":
    main()
