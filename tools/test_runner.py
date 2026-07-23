#!/usr/bin/env python3
"""
Balloon LR2021 Test Runner — automated flash + capture + parse.

Subcommands:
  flash   Build + flash firmware to both RP2040 boards via ESP32 bridges
  capture Open serial ports, collect output, parse RESULT lines
  sweep   Run a test matrix from JSON config
  parse   Parse a serial log file for RESULT lines

Board mapping (stable via ESP32 UART bridges):
  /dev/ttyACM1 → RP2040 #8332 (RX board)
  /dev/ttyACM3 → RP2040 #F242D (TX board)

Flash procedure:
  RX: flash bootsel-oneshot to ACM1 → triggers 8332 BOOTSEL → picotool load -v -x → restore UART bridge
  TX: send BOOTSEL command to ACM3 → picotool load -v -x

Usage:
  python3 tools/test_runner.py flash --tx rp2040-lora-tx-sf9 --rx rp2040-lora-rx-sf9
  python3 tools/test_runner.py capture --duration 35
  python3 tools/test_runner.py sweep --config tools/sweep-config.json
  python3 tools/test_runner.py parse --file captured_output.txt
"""

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

try:
    import serial
except ImportError:
    print("ERROR: pyserial not installed. Run: pip install pyserial", file=sys.stderr)
    sys.exit(1)

# ─── Constants ─────────────────────────────────────────────────────────
WORKTREE = Path(os.environ.get("BALLOON_WORKTREE", os.path.expanduser("~/worktrees/balloon-speed-tests")))
FW_DIR = WORKTREE / "firmware" / "rp2040"
BUILD_DIR = FW_DIR / ".pio" / "build"
PICOTOOL = os.path.expanduser("~/.platformio/packages/tool-rp2040tools/picotool")
ESPTOOL = os.path.expanduser("~/.platformio/packages/tool-esptoolpy/esptool.py")
BRIDGE_BUILD = WORKTREE / "firmware" / "esp32-uart-bridge" / ".pio" / "build" / "esp32-uart-bridge"
BOOTSEL_BUILD = WORKTREE / "firmware" / "esp32-c3-bootsel-controller" / ".pio" / "build" / "esp32-c3-bootsel-controller"

PORT_RX = "/dev/ttyACM1"   # ESP32 bridge → RP2040 #8332
PORT_TX = "/dev/ttyACM3"   # ESP32 bridge → RP2040 #F242D
BAUD = 115200

# ─── Result line parser ────────────────────────────────────────────────
RESULT_PATTERN = re.compile(
    r'^((?:LORA|FLRC)_(?:TX|RX)_RESULT),'
    r'(.+)$'
)

def parse_result_line(line: str) -> dict | None:
    """Parse a RESULT line into a dict. Returns None if not a result line."""
    line = line.strip()
    m = RESULT_PATTERN.match(line)
    if not m:
        return None
    result_type = m.group(1)
    fields_str = m.group(2)
    result = {"type": result_type}
    for field in fields_str.split(","):
        if "=" in field:
            key, val = field.split("=", 1)
            key = key.strip()
            val = val.strip()
            # Try numeric conversion
            try:
                if "." in val:
                    result[key] = float(val)
                else:
                    result[key] = int(val)
            except ValueError:
                result[key] = val
    return result

def parse_serial_output(text: str) -> list[dict]:
    """Parse all RESULT lines from serial output text."""
    results = []
    for line in text.split("\n"):
        parsed = parse_result_line(line)
        if parsed:
            results.append(parsed)
    return results

# ─── Serial capture ───────────────────────────────────────────────────
def capture_serial(port_tx: str = PORT_TX, port_rx: str = PORT_RX,
                   duration: int = 30) -> tuple[str, str]:
    """
    Open both serial ports, capture output for duration seconds.
    Returns (tx_output, rx_output) as decoded strings.
    """
    tx_data = bytearray()
    rx_data = bytearray()

    try:
        tx_ser = serial.Serial(port_tx, BAUD, timeout=0.1)
        rx_ser = serial.Serial(port_rx, BAUD, timeout=0.1)
    except serial.SerialException as e:
        print(f"ERROR: Cannot open serial port: {e}", file=sys.stderr)
        return "", ""

    # Flush existing data
    tx_ser.read(65536)
    rx_ser.read(65536)
    time.sleep(0.3)

    def collect(ser, buf):
        while True:
            chunk = ser.read(4096)
            if chunk:
                buf.extend(chunk)

    t1 = threading.Thread(target=collect, args=(tx_ser, tx_data), daemon=True)
    t2 = threading.Thread(target=collect, args=(rx_ser, rx_data), daemon=True)
    t1.start()
    t2.start()

    print(f"Capturing for {duration}s...", file=sys.stderr)
    for remaining in range(duration, 0, -1):
        print(f"\r  {remaining}s remaining", end="", file=sys.stderr, flush=True)
        time.sleep(1)
    print(file=sys.stderr)

    tx_ser.close()
    rx_ser.close()

    return tx_data.decode(errors="replace"), rx_data.decode(errors="replace")

# ─── Print summary ────────────────────────────────────────────────────
def print_summary(results: list[dict]):
    """Print a formatted summary table from parsed results."""
    if not results:
        print("No RESULT lines found in captured output.")
        return

    print("\n" + "=" * 60)
    print("CAPTURED RESULTS")
    print("=" * 60)

    for r in results:
        rtype = r.get("type", "UNKNOWN")
        print(f"\n--- {rtype} ---")
        for key in ["sent", "fired", "timeout", "rx", "cum_rx", "unique",
                     "lost", "total", "per", "throughput_kbps",
                     "rssi_avg", "rssi_min", "snr_avg",
                     "sf", "bw", "cr", "pktSize", "freq", "elapsed_ms"]:
            if key in r:
                print(f"  {key:20s} = {r[key]}")

    # Compute derived metrics
    tx_results = [r for r in results if "TX_RESULT" in r.get("type", "")]
    rx_results = [r for r in results if "RX_RESULT" in r.get("type", "")]

    if tx_results and rx_results:
        tx = tx_results[-1]  # last TX result
        rx = rx_results[-1]  # last RX result
        print("\n--- SUMMARY ---")
        sent = rx.get("total", tx.get("sent", 0))
        received = rx.get("cum_rx", rx.get("rx", 0))
        per = rx.get("per", 0.0)
        tput = rx.get("throughput_kbps", 0)
        rssi = rx.get("rssi_avg", 0)
        snr = rx.get("snr_avg", 0)
        print(f"  Packets sent:     {sent}")
        print(f"  Packets received: {received}")
        print(f"  PER:              {per:.2f}%")
        print(f"  Throughput:       {tput:.1f} kbps")
        print(f"  RSSI:             {rssi:.1f} dBm")
        print(f"  SNR:              {snr:.1f} dB")
    print("=" * 60)

# ─── Flash functions ──────────────────────────────────────────────────
def build_firmware(env: str) -> bool:
    """Build a PlatformIO firmware environment."""
    cmd = ["pio", "run", "-e", env]
    print(f"Building {env}...", file=sys.stderr)
    result = subprocess.run(cmd, cwd=str(FW_DIR), capture_output=True, text=True)
    if result.returncode != 0:
        print(f"BUILD FAILED for {env}:", file=sys.stderr)
        print(result.stderr[-500:], file=sys.stderr)
        return False
    uf2 = BUILD_DIR / env / "firmware.uf2"
    if not uf2.exists():
        print(f"BUILD OK but firmware.uf2 missing for {env}", file=sys.stderr)
        return False
    print(f"Build OK: {uf2}", file=sys.stderr)
    return True

def flash_rx_board(rx_env: str) -> bool:
    """Flash RX RP2040 #8332 via ACM1 bridge: bootsel-oneshot → picotool → restore bridge."""
    rx_fw = BUILD_DIR / rx_env / "firmware.uf2"
    if not rx_fw.exists():
        print(f"ERROR: {rx_fw} not found. Build first.", file=sys.stderr)
        return False

    # Step 1: Flash bootsel-oneshot to ACM1 to trigger 8332 BOOTSEL
    print("Flashing bootsel-oneshot to ACM1...", file=sys.stderr)
    cmd = [
        sys.executable, ESPTOOL,
        "--port", PORT_RX, "--chip", "esp32c3", "--baud", "460800",
        "write_flash",
        "0x0", str(BOOTSEL_BUILD / "bootloader.bin"),
        "0x8000", str(BOOTSEL_BUILD / "partitions.bin"),
        "0x10000", str(BOOTSEL_BUILD / "firmware.bin"),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"esptool failed: {result.stderr[-300:]}", file=sys.stderr)
        return False
    print("Waiting 5s for BOOTSEL trigger...", file=sys.stderr)
    time.sleep(5)

    # Step 2: Flash RX firmware via picotool
    print(f"Flashing RX firmware ({rx_env})...", file=sys.stderr)
    cmd = ["sudo", PICOTOOL, "load", "-v", "-x", str(rx_fw)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"picotool failed: {result.stderr[-300:]}", file=sys.stderr)
        return False
    print("RX firmware flashed OK.", file=sys.stderr)
    time.sleep(3)

    # Step 3: Restore UART bridge to ACM1
    print("Restoring UART bridge on ACM1...", file=sys.stderr)
    cmd = [
        sys.executable, ESPTOOL,
        "--port", PORT_RX, "--chip", "esp32c3", "--baud", "460800",
        "write_flash",
        "0x0", str(BRIDGE_BUILD / "bootloader.bin"),
        "0x8000", str(BRIDGE_BUILD / "partitions.bin"),
        "0x10000", str(BRIDGE_BUILD / "firmware.bin"),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Bridge restore failed: {result.stderr[-300:]}", file=sys.stderr)
        return False
    print("UART bridge restored.", file=sys.stderr)
    return True

def flash_tx_board(tx_env: str) -> bool:
    """Flash TX RP2040 #F242D via ACM3 bridge: BOOTSEL serial command → picotool."""
    tx_fw = BUILD_DIR / tx_env / "firmware.uf2"
    if not tx_fw.exists():
        print(f"ERROR: {tx_fw} not found. Build first.", file=sys.stderr)
        return False

    # Send BOOTSEL command via serial to ACM3 bridge
    print("Sending BOOTSEL to TX bridge...", file=sys.stderr)
    try:
        ser = serial.Serial(PORT_TX, BAUD, timeout=2)
        time.sleep(0.3)
        ser.write(b"BOOTSEL\n")
        time.sleep(2)
        ser.read(256)
        ser.close()
    except serial.SerialException as e:
        print(f"Failed to send BOOTSEL: {e}", file=sys.stderr)
        return False

    time.sleep(1)

    # Flash via picotool
    print(f"Flashing TX firmware ({tx_env})...", file=sys.stderr)
    cmd = ["sudo", PICOTOOL, "load", "-v", "-x", str(tx_fw)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"picotool failed: {result.stderr[-300:]}", file=sys.stderr)
        return False
    print("TX firmware flashed OK.", file=sys.stderr)
    return True

def do_flash(tx_env: str, rx_env: str):
    """Build + flash both boards."""
    if not build_firmware(tx_env):
        sys.exit(1)
    if not build_firmware(rx_env):
        sys.exit(1)
    if not flash_rx_board(rx_env):
        sys.exit(1)
    if not flash_tx_board(tx_env):
        sys.exit(1)
    print(f"\nDone. TX={tx_env} on F242D, RX={rx_env} on 8332.")

# ─── Capture command ──────────────────────────────────────────────────
def do_capture(duration: int, port_tx: str, port_rx: str, output_file: str | None):
    """Capture serial output and parse results."""
    tx_text, rx_text = capture_serial(port_tx, port_rx, duration)

    if output_file:
        with open(output_file, "w") as f:
            f.write("=== TX OUTPUT ===\n")
            f.write(tx_text)
            f.write("\n=== RX OUTPUT ===\n")
            f.write(rx_text)
        print(f"Saved to {output_file}", file=sys.stderr)

    all_text = tx_text + "\n" + rx_text
    results = parse_serial_output(all_text)
    print_summary(results)

    if results:
        # Output JSON for machine consumption
        json_results = json.dumps(results, indent=2)
        if output_file:
            json_file = output_file.replace(".txt", ".json").replace(".log", ".json")
            if json_file == output_file:
                json_file = output_file + ".json"
            with open(json_file, "w") as f:
                f.write(json_results)
            print(f"JSON results saved to {json_file}", file=sys.stderr)

# ─── Sweep command ────────────────────────────────────────────────────
def do_sweep(config_file: str, output_dir: str):
    """Run a test matrix from JSON config."""
    with open(config_file) as f:
        config = json.load(f)

    tests = config.get("tests", [])
    if not tests:
        print("No tests in config file.", file=sys.stderr)
        sys.exit(1)

    all_results = []
    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)

    for i, test in enumerate(tests):
        name = test.get("name", f"test_{i}")
        tx_env = test["tx_env"]
        rx_env = test["rx_env"]
        duration = test.get("duration", 30)

        print(f"\n{'='*60}", file=sys.stderr)
        print(f"SWEEP [{i+1}/{len(tests)}]: {name}", file=sys.stderr)
        print(f"  TX={tx_env}  RX={rx_env}  Duration={duration}s", file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)

        # Flash
        if not build_firmware(tx_env) or not build_firmware(rx_env):
            print(f"SKIP {name}: build failed", file=sys.stderr)
            all_results.append({"name": name, "status": "build_failed"})
            continue
        if not flash_rx_board(rx_env) or not flash_tx_board(tx_env):
            print(f"SKIP {name}: flash failed", file=sys.stderr)
            all_results.append({"name": name, "status": "flash_failed"})
            continue

        # Capture
        tx_text, rx_text = capture_serial(duration=duration)
        results = parse_serial_output(tx_text + "\n" + rx_text)

        for r in results:
            r["test_name"] = name
        all_results.append({"name": name, "status": "ok", "results": results})

        # Save individual test output
        test_file = outdir / f"{name}.txt"
        with open(test_file, "w") as f:
            f.write(f"=== {name} (TX={tx_env}, RX={rx_env}) ===\n")
            f.write("=== TX OUTPUT ===\n")
            f.write(tx_text)
            f.write("\n=== RX OUTPUT ===\n")
            f.write(rx_text)

        # Print summary
        print_summary(results)

    # Save combined JSON
    json_file = outdir / "sweep_results.json"
    with open(json_file, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nAll results saved to {json_file}", file=sys.stderr)

# ─── Parse command ────────────────────────────────────────────────────
def do_parse(filepath: str):
    """Parse a serial log file for RESULT lines."""
    with open(filepath) as f:
        text = f.read()

    results = parse_serial_output(text)
    if results:
        print(json.dumps(results, indent=2))
    else:
        print("No RESULT lines found.")
        # Show lines that look like they might be results
        for line in text.split("\n"):
            if "RESULT" in line or "result" in line:
                print(f"  (unparsed) {line.strip()[:200]}")

# ─── Main ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Balloon LR2021 test runner — flash, capture, parse, sweep.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Flash both boards
  %(prog)s flash --tx rp2040-lora-tx-sf9 --rx rp2040-lora-rx-sf9

  # Capture 35s and show results
  %(prog)s capture --duration 35

  # Capture to file
  %(prog)s capture --duration 35 --output sf9_test.txt

  # Run a sweep matrix
  %(prog)s sweep --config tools/sweep-config.json --output-dir results/

  # Parse an existing log
  %(prog)s parse --file captured_output.txt
        """,
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # flash
    p_flash = sub.add_parser("flash", help="Build + flash firmware to both boards")
    p_flash.add_argument("--tx", required=True, help="TX PlatformIO env name")
    p_flash.add_argument("--rx", required=True, help="RX PlatformIO env name")

    # capture
    p_cap = sub.add_parser("capture", help="Capture serial output and parse results")
    p_cap.add_argument("--duration", type=int, default=30, help="Capture duration in seconds")
    p_cap.add_argument("--port-tx", default=PORT_TX, help=f"TX serial port (default: {PORT_TX})")
    p_cap.add_argument("--port-rx", default=PORT_RX, help=f"RX serial port (default: {PORT_RX})")
    p_cap.add_argument("--output", "-o", default=None, help="Save raw output to file")

    # sweep
    p_sw = sub.add_parser("sweep", help="Run a test matrix from JSON config")
    p_sw.add_argument("--config", required=True, help="JSON config file path")
    p_sw.add_argument("--output-dir", default="results", help="Directory for results")

    # parse
    p_par = sub.add_parser("parse", help="Parse a serial log file")
    p_par.add_argument("--file", "-f", required=True, help="Log file to parse")

    args = parser.parse_args()

    if args.command == "flash":
        do_flash(args.tx, args.rx)
    elif args.command == "capture":
        do_capture(args.duration, args.port_tx, args.port_rx, args.output)
    elif args.command == "sweep":
        do_sweep(args.config, args.output_dir)
    elif args.command == "parse":
        do_parse(args.file)

if __name__ == "__main__":
    main()
