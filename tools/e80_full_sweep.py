#!/usr/bin/env python3
"""E80-to-E80 Full Harmonization Sweep — Correct Command Sequence v2.

Both boards flashed with fw=e79f0c0, baud=2000000.
TX at /dev/ttyUSB3, RX at /dev/ttyUSB4.

Key fix from v1: drain responses after every command to keep boards happy.
Also handle \\r\\n line endings from firmware.
"""

import serial
import time
import sys
import os
import re
from datetime import datetime

TX_PORT = "/dev/ttyUSB3"
RX_PORT = "/dev/ttyUSB4"
BAUD = 2000000
OUTPUT_FILE = os.path.expanduser("~/repos/balloon-fresh/tools/e80_full_sweep_results.txt")

# Sweep configs: (config_id, SF, BW_kHz, pkt_size, N)
CONFIGS = [
    (0, 7,  125, 64,  100),
    (1, 8,  125, 64,  100),
    (2, 9,  125, 64,  100),
    (3, 10, 125, 64,  50),
    (4, 11, 125, 64,  50),
    (5, 12, 125, 64,  50),
    (6, 8,  250, 64,  100),
    (7, 8,  500, 64,  100),
    (8, 8,  125, 128, 100),
    (9, 8,  125, 255, 50),
]

# Adaptive wait times per SF (seconds)
SF_WAIT = {
    7: 20,   # 15 + 5 margin
    8: 20,   # 15 + 5 margin
    9: 30,   # 25 + 5 margin
    10: 50,  # 45 + 5 margin
    11: 95,  # 90 + 5 margin
    12: 125, # 120 + 5 margin
}


def open_port(port, label):
    """Open a serial port with the E80 settings."""
    try:
        s = serial.Serial(
            port=port,
            baudrate=BAUD,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1,
            write_timeout=5.0,
        )
        s.reset_input_buffer()
        s.reset_output_buffer()
        print(f"  [{label}] Opened {port} @ {BAUD} baud")
        return s
    except Exception as e:
        print(f"  [{label}] FAILED to open {port}: {e}")
        return None


def send_cmd(ser, label, cmd, wait=0.5, drain=True):
    """Send a command (with \\n) and optionally wait + drain response."""
    full = cmd + "\n"
    ser.write(full.encode("ascii"))
    ser.flush()
    if wait > 0:
        time.sleep(wait)
    if drain:
        # Drain any response
        resp = b""
        deadline = time.time() + 0.3
        while time.time() < deadline:
            chunk = ser.read(4096)
            if chunk:
                resp += chunk
                deadline = time.time() + 0.2
            else:
                break
        if resp:
            lines = resp.decode("ascii", errors="replace").strip().split("\n")
            for ln in lines:
                print(f"  [{label}] RECV: {ln.strip()}")
    print(f"  [{label}] SENT: {cmd}")


def read_all(ser, label, timeout_s=2.0):
    """Read all available data from a serial port with a read timeout."""
    ser.timeout = 0.1
    data = b""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        chunk = ser.read(4096)
        if chunk:
            data += chunk
            deadline = time.time() + 0.5  # extend if data is flowing
        else:
            if data:
                break  # got some data and no more coming
    lines = data.decode("ascii", errors="replace").strip().split("\n") if data else []
    for ln in lines:
        print(f"  [{label}] RECV: {ln.strip()}")
    return lines


def send_and_read(ser, label, cmd, wait=0.5, read_timeout=2.0):
    """Send a command, wait, then read response."""
    send_cmd(ser, label, cmd, wait=0, drain=False)
    time.sleep(wait)
    return read_all(ser, label, timeout_s=read_timeout)


def get_id(ser, label):
    """Query board identity."""
    send_cmd(ser, label, "ID?", wait=0, drain=False)
    time.sleep(0.5)
    lines = read_all(ser, label, timeout_s=1.0)
    return "\n".join(lines)


def try_recover(ser, label, port):
    """Try to recover a hung board."""
    print(f"  [{label}] Attempting recovery: ROLE NONE + STOP")
    try:
        send_cmd(ser, label, "ROLE NONE", wait=0.5, drain=False)
        time.sleep(0.5)
        read_all(ser, label, timeout_s=1.0)
        send_cmd(ser, label, "STOP", wait=1.0, drain=False)
        time.sleep(1.0)
        read_all(ser, label, timeout_s=1.0)
        send_cmd(ser, label, "ID?", wait=0, drain=False)
        time.sleep(0.5)
        resp = read_all(ser, label, timeout_s=1.0)
        if resp:
            print(f"  [{label}] Recovery successful")
            return True
    except Exception as e:
        print(f"  [{label}] Recovery failed: {e}")
    return False


def reflash_board(cfg_file, label):
    """Reflash a board via OpenOCD."""
    binary = "/home/c03rad0r/repos/balloon-e80bench/firmware/e80-stm32-bench/build-fw/e80_bench.bin"
    cmd = f"/usr/bin/openocd -f {cfg_file} -c 'program {binary} verify reset exit 0x08000000'"
    print(f"  [{label}] Reflashing with: {cmd}")
    ret = os.system(cmd)
    if ret == 0:
        print(f"  [{label}] Reflash successful, waiting 3s...")
        time.sleep(3)
        return True
    else:
        print(f"  [{label}] Reflash FAILED (ret={ret})")
        return False


def parse_pkt_line(line):
    """Parse a PKT line: PKT <seq> <rssi> <snr> <ok> <bit_errs> <bytes_bad> <total> <config_id>"""
    parts = line.strip().split()
    if len(parts) < 2 or parts[0] != "PKT":
        return None
    try:
        d = {}
        d["seq"] = int(parts[1])
        d["rssi"] = int(parts[2]) if len(parts) > 2 else 0
        d["snr"] = int(parts[3]) if len(parts) > 3 else 0
        d["ok"] = int(parts[4]) if len(parts) > 4 else 0
        d["bit_errs"] = int(parts[5]) if len(parts) > 5 else 0
        d["bytes_bad"] = int(parts[6]) if len(parts) > 6 else 0
        d["total"] = int(parts[7]) if len(parts) > 7 else 0
        d["config_id"] = int(parts[8]) if len(parts) > 8 else -1
        return d
    except (ValueError, IndexError):
        return None


def parse_stat_line(lines):
    """Parse STAT? response lines.
    Expected format: STAT role=NONE sent=0 sent_ok=0 rx=0 crc_err=0 per_x1e6=0 elapsed_s=0.0 kbps=0 rssi_avg_dbm=0.0 rssi_min_dbm=0.0 rssi_max_dbm=0.0 snr_avg_db=0.0 cr=5 session=0 config=0 replicate=0 drops=0 gap_us=5000
    """
    result = {}
    for line in lines:
        line = line.strip()
        if line.startswith("STAT"):
            # Parse key=value pairs
            for token in line.split():
                if "=" in token:
                    k, v = token.split("=", 1)
                    try:
                        result[k] = int(v)
                    except ValueError:
                        try:
                            result[k] = float(v)
                        except ValueError:
                            result[k] = v
        elif line.startswith("ERR"):
            result["error"] = line
    return result


def run_config(tx_ser, rx_ser, config_id, sf, bw_khz, pkt_size, n_packets, results_file):
    """Run a single sweep config."""
    wait_time = SF_WAIT.get(sf, 30)
    
    header = f"\n{'='*70}\n"
    header += f"CONFIG {config_id}: SF{sf} BW={bw_khz}kHz pkt_size={pkt_size} N={n_packets} gap=10000us PA=10\n"
    header += f"{'='*70}\n"
    print(header, end="")
    results_file.write(header)
    results_file.flush()
    
    # Step 1: ROLE NONE to both (reset)
    send_cmd(tx_ser, "TX", "ROLE NONE", wait=0.5)
    send_cmd(rx_ser, "RX", "ROLE NONE", wait=0.5)
    
    # Step 2: ROLE RX
    send_cmd(rx_ser, "RX", "ROLE RX", wait=0.5)
    
    # Step 3: PRBS ON
    send_cmd(rx_ser, "RX", "PRBS ON", wait=0.5)
    
    # Step 4: ROLE TX
    send_cmd(tx_ser, "TX", "ROLE TX", wait=0.5)
    
    # Step 5: MOD to both (BW in kHz!)
    mod_cmd = f"MOD loRa {sf} {bw_khz}"
    send_cmd(tx_ser, "TX", mod_cmd, wait=1.0)
    send_cmd(rx_ser, "RX", mod_cmd, wait=1.0)
    
    # Step 6: FREQ to TX only
    send_cmd(tx_ser, "TX", "FREQ 868000000", wait=0.5)
    
    # Step 7: PA to TX
    send_cmd(tx_ser, "TX", "PA 10", wait=0.5)
    
    # Step 8: CONFIG id to TX
    send_cmd(tx_ser, "TX", f"CONFIG {config_id} 0", wait=0.5)
    
    # Step 9: ARM TX
    send_cmd(tx_ser, "TX", "ARM TX", wait=0.5)
    
    # Step 10: START to both
    start_cmd = f"START N={n_packets} LEN={pkt_size} GAP=10000"
    send_cmd(tx_ser, "TX", start_cmd, wait=0, drain=True)
    send_cmd(rx_ser, "RX", start_cmd, wait=0, drain=True)
    
    # Step 11: Wait for completion
    print(f"  Waiting {wait_time}s for transmission to complete...")
    time.sleep(wait_time)
    
    # Step 12: Read ALL data from RX (PKT lines)
    pkt_lines = read_all(rx_ser, "RX", timeout_s=5.0)
    
    # Step 13: TX STAT?
    tx_stat_lines = send_and_read(tx_ser, "TX", "STAT?", wait=0.5, read_timeout=2.0)
    
    # Step 14: RX STAT?
    rx_stat_lines = send_and_read(rx_ser, "RX", "STAT?", wait=0.5, read_timeout=2.0)
    
    # Parse PKT lines
    pkt_data = []
    for line in pkt_lines:
        if line.strip().startswith("PKT"):
            d = parse_pkt_line(line)
            if d:
                pkt_data.append(d)
    
    # Parse stats
    tx_stat = parse_stat_line(tx_stat_lines)
    rx_stat = parse_stat_line(rx_stat_lines)
    
    # Write PKT lines to file
    results_file.write(f"  PKT lines ({len(pkt_data)} received):\n")
    for line in pkt_lines:
        if line.strip().startswith("PKT"):
            results_file.write(f"    {line.strip()}\n")
    non_pkt = [l.strip() for l in pkt_lines if not l.strip().startswith("PKT")]
    if non_pkt:
        results_file.write(f"  (Non-PKT lines: {non_pkt})\n")
    
    # Write TX STAT
    results_file.write(f"  TX STAT:\n")
    for line in tx_stat_lines:
        results_file.write(f"    {line.strip()}\n")
    
    # Write RX STAT
    results_file.write(f"  RX STAT:\n")
    for line in rx_stat_lines:
        results_file.write(f"    {line.strip()}\n")
    
    results_file.flush()
    
    # Compute summary stats
    n_rx = len(pkt_data)
    n_tx = n_packets
    per = (1.0 - n_rx / n_tx) * 100 if n_tx > 0 else 100.0
    
    rssi_vals = [p["rssi"] for p in pkt_data if p["rssi"] != 0]
    snr_vals = [p["snr"] for p in pkt_data if p["snr"] != 0]
    rssi_avg = sum(rssi_vals) / len(rssi_vals) if rssi_vals else 0
    snr_avg = sum(snr_vals) / len(snr_vals) if snr_vals else 0
    
    bit_err_total = sum(p["bit_errs"] for p in pkt_data)
    bytes_bad_total = sum(p["bytes_bad"] for p in pkt_data)
    
    # Also try to get stats from STAT? response
    if "sent" in tx_stat:
        n_tx = tx_stat["sent"]
    if "rx" in rx_stat:
        n_rx_stat = rx_stat.get("rx", 0)
        if n_rx_stat > n_rx:
            n_rx = n_rx_stat
    if "rssi_avg_dbm" in rx_stat:
        rssi_avg = rx_stat["rssi_avg_dbm"]
    if "snr_avg_db" in rx_stat:
        snr_avg = rx_stat["snr_avg_db"]
    if "per_x1e6" in rx_stat:
        per = rx_stat["per_x1e6"] / 10000.0
    
    per = (1.0 - n_rx / n_tx) * 100 if n_tx > 0 else 100.0
    
    summary = {
        "config_id": config_id,
        "sf": sf,
        "bw": bw_khz,
        "pkt_size": pkt_size,
        "n_tx": n_tx,
        "n_rx": n_rx,
        "per": per,
        "rssi_avg": rssi_avg,
        "snr_avg": snr_avg,
        "bit_err_total": bit_err_total,
        "bytes_bad_total": bytes_bad_total,
    }
    
    print(f"  Result: N_tx={n_tx} N_rx={n_rx} PER={per:.1f}% RSSI_avg={rssi_avg:.1f} SNR_avg={snr_avg:.1f} bit_err={bit_err_total} bytes_bad={bytes_bad_total}")
    
    return summary


def main():
    print("E80-to-E80 Full Harmonization Sweep v2")
    print("=" * 70)
    print(f"Date: {datetime.now().isoformat()}")
    print(f"Firmware: e79f0c0")
    print(f"TX: {TX_PORT}, RX: {RX_PORT}, Baud: {BAUD}")
    print(f"Configs: {len(CONFIGS)}")
    print()
    
    # Open serial ports
    tx_ser = open_port(TX_PORT, "TX")
    rx_ser = open_port(RX_PORT, "RX")
    
    if not tx_ser or not rx_ser:
        print("FATAL: Could not open serial ports!")
        sys.exit(1)
    
    # Get board IDs
    print("\nBoard identification:")
    tx_id = get_id(tx_ser, "TX")
    rx_id = get_id(rx_ser, "RX")
    print(f"  TX ID: {tx_id}")
    print(f"  RX ID: {rx_id}")
    
    # Open results file
    with open(OUTPUT_FILE, "w") as f:
        # Write header
        f.write(f"E80-to-E80 Full Harmonization Sweep Results\n")
        f.write(f"{'='*70}\n")
        f.write(f"Date: {datetime.now().isoformat()}\n")
        f.write(f"Firmware: e79f0c0\n")
        f.write(f"TX port: {TX_PORT}\n")
        f.write(f"RX port: {RX_PORT}\n")
        f.write(f"Baud: {BAUD}\n")
        f.write(f"TX ID: {tx_id}\n")
        f.write(f"RX ID: {rx_id}\n")
        f.write(f"Frequency: 868 MHz (TX), default (RX)\n")
        f.write(f"CR: 4/5 (hardcoded in firmware)\n")
        f.write(f"PA: 10 dBm\n")
        f.write(f"Gap: 10000 us\n")
        f.write(f"Modulation: LoRa\n")
        f.write(f"Configs: {len(CONFIGS)}\n")
        f.write(f"{'='*70}\n")
        f.flush()
        
        # Run all configs
        summaries = []
        for config_id, sf, bw_khz, pkt_size, n_packets in CONFIGS:
            # Check if boards are still responsive
            boards_ok = True
            for ser, label, port, cfg_file in [
                (tx_ser, "TX", TX_PORT, "/tmp/openocd-e80.cfg"),
                (rx_ser, "RX", RX_PORT, "/tmp/openocd-e80-2.cfg"),
            ]:
                try:
                    ser.write(b"ID?\n")
                    ser.flush()
                    time.sleep(0.3)
                    _ = ser.read(4096)
                except Exception as e:
                    print(f"  [{label}] board not responding: {e}")
                    if try_recover(ser, label, port):
                        pass
                    else:
                        print(f"  [{label}] needs reflash!")
                        if reflash_board(cfg_file, label):
                            if label == "TX":
                                tx_ser.close()
                                time.sleep(1)
                                tx_ser = open_port(TX_PORT, "TX")
                                ser = tx_ser
                            else:
                                rx_ser.close()
                                time.sleep(1)
                                rx_ser = open_port(RX_PORT, "RX")
                                ser = rx_ser
                        else:
                            boards_ok = False
            
            if not boards_ok:
                print(f"  CONFIG {config_id} SKIPPED — boards not responding")
                summaries.append({
                    "config_id": config_id, "sf": sf, "bw": bw_khz,
                    "pkt_size": pkt_size, "n_tx": n_packets, "n_rx": 0,
                    "per": 100.0, "rssi_avg": 0, "snr_avg": 0,
                    "bit_err_total": 0, "bytes_bad_total": 0,
                })
                continue
            
            try:
                summary = run_config(tx_ser, rx_ser, config_id, sf, bw_khz, pkt_size, n_packets, f)
                summaries.append(summary)
            except Exception as e:
                print(f"  CONFIG {config_id} FAILED with exception: {e}")
                import traceback
                traceback.print_exc()
                # Try recovery
                try:
                    try_recover(tx_ser, "TX", TX_PORT)
                except:
                    pass
                try:
                    try_recover(rx_ser, "RX", RX_PORT)
                except:
                    pass
                summaries.append({
                    "config_id": config_id, "sf": sf, "bw": bw_khz,
                    "pkt_size": pkt_size, "n_tx": n_packets, "n_rx": 0,
                    "per": 100.0, "rssi_avg": 0, "snr_avg": 0,
                    "bit_err_total": 0, "bytes_bad_total": 0,
                })
            
            # Brief cooldown between configs
            print("  Cooldown 2s...")
            time.sleep(2)
    
    # Write summary table
    with open(OUTPUT_FILE, "a") as f:
        f.write(f"\n{'='*70}\n")
        f.write(f"SUMMARY TABLE\n")
        f.write(f"{'='*70}\n")
        f.write(f"{'Cfg':>3} {'SF':>3} {'BW':>5} {'Len':>4} {'N_tx':>5} {'N_rx':>5} {'PER':>7} {'RSSI':>6} {'SNR':>6} {'BitErr':>7} {'BadByt':>7}\n")
        f.write(f"{'-'*3} {'-'*3} {'-'*5} {'-'*4} {'-'*5} {'-'*5} {'-'*7} {'-'*6} {'-'*6} {'-'*7} {'-'*7}\n")
        for s in summaries:
            f.write(f"{s['config_id']:>3} {s['sf']:>3} {s['bw']:>5} {s['pkt_size']:>4} {s['n_tx']:>5} {s['n_rx']:>5} {s['per']:>6.1f}% {s['rssi_avg']:>6.1f} {s['snr_avg']:>6.1f} {s['bit_err_total']:>7} {s['bytes_bad_total']:>7}\n")
        f.write(f"\n{'='*70}\n")
        f.write(f"END OF SWEEP\n")
        f.write(f"{'='*70}\n")
    
    # Print summary to console
    print(f"\n{'='*70}")
    print("SWEEP COMPLETE — Summary:")
    print(f"{'='*70}")
    print(f"{'Cfg':>3} {'SF':>3} {'BW':>5} {'Len':>4} {'N_tx':>5} {'N_rx':>5} {'PER':>7} {'RSSI':>6} {'SNR':>6} {'BitErr':>7} {'BadByt':>7}")
    for s in summaries:
        print(f"{s['config_id']:>3} {s['sf']:>3} {s['bw']:>5} {s['pkt_size']:>4} {s['n_tx']:>5} {s['n_rx']:>5} {s['per']:>6.1f}% {s['rssi_avg']:>6.1f} {s['snr_avg']:>6.1f} {s['bit_err_total']:>7} {s['bytes_bad_total']:>7}")
    
    print(f"\nResults saved to: {OUTPUT_FILE}")
    
    # Close ports
    try:
        tx_ser.close()
        rx_ser.close()
    except:
        pass


if __name__ == "__main__":
    main()