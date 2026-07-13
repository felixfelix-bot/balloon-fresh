#!/usr/bin/env python3
"""
balloon_flash_test.py — Automated flash + serial capture for RP2040 board testing.

Usage:
  uv run --with pyserial python3 balloon_flash_test.py flash <port> <env>
  uv run --with pyserial python3 balloon_flash_test.py capture <port> <seconds>
  uv run --with pyserial python3 balloon_flash_test.py test <tx_port> <rx_port> <seconds>

The flash command:
  1. Sends 1200 baud to trigger BOOTSEL
  2. Waits for RPI-RP2 mass storage
  3. Copies the UF2 firmware
  4. Waits for board to reboot

The capture command:
  1. Opens serial port at 115200
  2. Captures output for N seconds
  3. Parses heartbeat lines for statistics

The test command:
  1. Captures both TX and RX serial simultaneously
  2. Calculates throughput, PER, reception rate
"""

import serial, time, sys, os, subprocess, shutil, re, threading
from collections import defaultdict

REPO = "/home/c03rad0r/repos/balloon-fresh"
# rp2040-flrc-max is the current throughput test firmware (TX env + RX env)
# rp2040 is the legacy directory (kept for backward compat)
FIRMWARE_DIRS = {
    "tx": f"{REPO}/firmware/rp2040-flrc-max",
    "rx": f"{REPO}/firmware/rp2040-flrc-max",
}
BUILD_DIR = f"{REPO}/firmware/rp2040-flrc-max/.pio/build"

def find_bootsel():
    """Find BOOTSEL mass storage device."""
    r = subprocess.run(['lsblk', '-o', 'NAME,SIZE,LABEL', '-n'], capture_output=True, text=True)
    for line in r.stdout.split('\n'):
        if 'RPI-RP' in line:
            # Extract device name (strip tree characters)
            name = line.strip().split()[0].replace('└─', '').replace('├─', '')
            return f'/dev/{name}'
    return None

def flash_firmware(port, env):
    """Flash firmware via 1200 baud BOOTSEL trigger + UF2 copy."""
    uf2_path = f"{BUILD_DIR}/{env}/firmware.uf2"
    if not os.path.exists(uf2_path):
        print(f"Building {env}...")
        fw_dir = FIRMWARE_DIRS.get(env, f"{REPO}/firmware/rp2040-flrc-max")
        r = subprocess.run(
            ['pio', 'run', '-e', env],
            cwd=fw_dir,
            capture_output=True, text=True, timeout=120
        )
        if not os.path.exists(uf2_path):
            print(f"ERROR: Build failed or UF2 not found at {uf2_path}")
            return False

    # Step 1: 1200 baud reset
    print(f"Triggering BOOTSEL on {port}...")
    try:
        s = serial.Serial(port, 1200, timeout=1)
        s.close()
    except Exception as e:
        print(f"1200 baud failed: {e}")
        print("Try USB power-cycle or physical BOOTSEL button")
        return False

    # Step 2: Wait for BOOTSEL mass storage
    for i in range(15):
        dev = find_bootsel()
        if dev:
            print(f"BOOTSEL found: {dev}")
            subprocess.run(['udisksctl', 'mount', '-b', dev], capture_output=True)
            time.sleep(1)
            r = subprocess.run(['findmnt', '-n', '-o', 'TARGET', dev], capture_output=True, text=True)
            mount = r.stdout.strip()
            if mount:
                print(f"Mounted at: {mount}")
                shutil.copy(uf2_path, mount)
                os.sync()
                print(f"Flashed {env} firmware!")
                time.sleep(3)
                return True
        time.sleep(1)

    print("BOOTSEL device did not appear")
    return False

def capture_serial(port, duration, label=""):
    """Capture serial output and return parsed statistics.

    Heartbeat intervals are measured from real timestamps, NOT assumed.
    (Earlier versions assumed a fixed 2 s heartbeat, which under-reported
    throughput ~33x for firmware that emits every ~62 ms.)
    """
    try:
        s = serial.Serial(port, 115200, timeout=0.5)
        s.reset_input_buffer()
    except Exception as e:
        return {"error": str(e), "lines": []}

    lines = []
    start = time.time()
    # Track (timestamp, count) pairs so rates derive from real elapsed time.
    tx_samples = []  # [(epoch_seconds, TXtotal)]
    rx_samples = []  # [(epoch_seconds, rx_total)]
    while time.time() - start < duration:
        data = s.readline()
        if data:
            line = data.decode(errors='replace').strip()
            lines.append(line)
            now = time.time()
            # TX heartbeat (rp2040-flrc-max): "TX 500/2000 (3283.0 kbps)"
            m = re.search(r'TX\s+(\d+)/\d+\s+\(([0-9.]+)\s*kbps', line)
            if m:
                tx_samples.append((now, int(m.group(1))))
                # store latest kbps for direct reporting
                stats_latest_tx_kbps = m.group(2)
            # TX heartbeat (legacy): "HB St=0x21 TXtotal=XXXXX ..."
            m = re.search(r'TXtotal=(\d+)', line)
            if m:
                tx_samples.append((now, int(m.group(1))))
            # RX heartbeat (rp2040-flrc-max): "RX 500 pkts (1234.5 kbps) RSSI=-45"
            m = re.search(r'RX\s+(\d+)\s+pkts\s+\(([0-9.]+)\s*kbps', line)
            if m:
                rx_samples.append((now, int(m.group(1))))
            # RX heartbeat (legacy): "rx=XXX ..."
            m = re.search(r'rx=(\d+)', line)
            if m:
                rx_samples.append((now, int(m.group(1))))
    s.close()

    stats = {"lines": lines, "label": label}

    # Latest crc/gaps/dups values (sweep all lines; last occurrence wins)
    for line in lines:
        for field, key in (('crc', 'crc_errors'), ('gaps', 'gaps'), ('dups', 'dups')):
            mm = re.search(field + r'=(\d+)', line)
            if mm:
                stats[key] = int(mm.group(1))

    # rp2040-flrc-max final throughput line: "  Throughput: 3283.0 kbps"
    for line in lines:
        mm = re.search(r'Throughput:\s+([0-9.]+)\s*kbps', line)
        if mm:
            stats['final_kbps'] = mm.group(1)

    def _rate(samples):
        """Return (pkts_per_s, kbps) from real timestamps, or (None, None)."""
        if len(samples) < 2:
            return None, None
        t0, c0 = samples[0]
        t1, c1 = samples[-1]
        dt = t1 - t0
        if dt <= 0:
            return None, None
        pkts_per_s = (c1 - c0) / dt
        kbps = pkts_per_s * 255 * 8 / 1000  # 255-byte FLRC payload
        return pkts_per_s, kbps

    if len(tx_samples) >= 2:
        pps, kbps = _rate(tx_samples)
        stats['tx_pkts_per_s'] = pps
        stats['tx_kbps'] = kbps
        stats['tx_heartbeat_ms'] = (tx_samples[-1][0] - tx_samples[0][0]) / (len(tx_samples) - 1) * 1000

    if len(rx_samples) >= 2:
        pps, kbps = _rate(rx_samples)
        stats['rx_pkts_per_s'] = pps
        stats['rx_kbps'] = kbps
        stats['rx_heartbeat_ms'] = (rx_samples[-1][0] - rx_samples[0][0]) / (len(rx_samples) - 1) * 1000

    return stats

def run_test(tx_port, rx_port, duration):
    """Capture both TX and RX simultaneously and calculate throughput."""
    results = {}

    def capture_thread(port, label):
        results[label] = capture_serial(port, duration, label)

    threads = [
        threading.Thread(target=capture_thread, args=(tx_port, 'tx')),
        threading.Thread(target=capture_thread, args=(rx_port, 'rx')),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Print results
    print(f"\n{'='*60}")
    print(f"TEST RESULTS ({duration}s capture)")
    print(f"{'='*60}")

    tx = results.get('tx', {})
    rx = results.get('rx', {})

    if 'tx_kbps' in tx:
        print(f"TX: {tx['tx_pkts_per_s']:.1f} pkts/s = {tx['tx_kbps']:.1f} kbps")
    else:
        print(f"TX: no data or error: {tx.get('error', 'no heartbeat parsed')}")

    if 'rx_kbps' in rx:
        print(f"RX: {rx['rx_pkts_per_s']:.1f} pkts/s = {rx['rx_kbps']:.1f} kbps")
        print(f"    CRC errors: {rx.get('crc_errors', '?')}")
        print(f"    Seq gaps: {rx.get('gaps', '?')}")
        
        if 'tx_pkts_per_s' in tx and tx['tx_pkts_per_s'] > 0:
            reception_rate = rx['rx_pkts_per_s'] / tx['tx_pkts_per_s'] * 100
            print(f"    Reception rate: {reception_rate:.1f}%")
    else:
        print(f"RX: no data or error: {rx.get('error', 'no heartbeat parsed')}")

    print(f"{'='*60}")
    
    # Print sample lines
    for label in ['tx', 'rx']:
        lines = results.get(label, {}).get('lines', [])
        if lines:
            print(f"\nSample {label.upper()} output:")
            for l in lines[:3]:
                print(f"  {l}")

    return results

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "flash":
        port = sys.argv[2]
        env = sys.argv[3]
        ok = flash_firmware(port, env)
        sys.exit(0 if ok else 1)

    elif cmd == "capture":
        port = sys.argv[2]
        duration = int(sys.argv[3]) if len(sys.argv) > 3 else 10
        stats = capture_serial(port, duration, port)
        for line in stats.get('lines', []):
            print(line)
        if 'tx_kbps' in stats:
            print(f"\nTX: {stats['tx_kbps']:.1f} kbps ({stats['tx_pkts_per_s']:.1f} pkts/s)")
        if 'rx_kbps' in stats:
            print(f"RX: {stats['rx_kbps']:.1f} kbps ({stats['rx_pkts_per_s']:.1f} pkts/s)")

    elif cmd == "test":
        tx_port = sys.argv[2]
        rx_port = sys.argv[3]
        duration = int(sys.argv[4]) if len(sys.argv) > 4 else 30
        run_test(tx_port, rx_port, duration)

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)

if __name__ == "__main__":
    main()
