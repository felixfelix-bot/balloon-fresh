#!/usr/bin/env python3
"""e80_sweep.py — E80-to-E80 LoRa sweep measurement.

Sweeps SF7-12 at BW125, SF7-9 at BW250, SF7-8 at BW500, and SF7-9 at PA=0.
Each config: 50 packets, 64B payload, PRBS-15 fill+verify, 10ms gap.
"""

import serial, time, statistics, os, sys
from datetime import datetime

TX_PORT = "/dev/ttyUSB4"
RX_PORT = "/dev/ttyUSB3"
BAUD = 115200
FREQ = 868000000

SWEEPS = [
    # (sf, bw_khz, pa_dbm)
    (7, 125, 10), (8, 125, 10), (9, 125, 10), (10, 125, 10),
    (11, 125, 10), (12, 125, 10),
    (7, 250, 10), (8, 250, 10), (9, 250, 10),
    (7, 500, 10), (8, 500, 10),
    (7, 125, 0), (8, 125, 0), (9, 125, 0),
]

def cmd(s, msg, wait=0.3, retries=3):
    """Send command, validate response, retry on ERR/empty."""
    r = ""
    for attempt in range(retries):
        s.reset_input_buffer()
        s.write((msg + "\r\n").encode())
        time.sleep(wait)
        r = s.read(500).decode(errors="replace").strip()
        if r and not r.startswith("ERR"):
            return r
        time.sleep(0.2)
    return r

def cmd_expect(s, msg, expect, wait=0.3, retries=5):
    r = ""
    for attempt in range(retries):
        r = cmd(s, msg, wait, 2)
        if expect in r:
            return r
        time.sleep(0.2)
    raise RuntimeError(f"{msg}: expected '{expect}' in response, got: {r[:100]!r}")

def parse_pkt(line):
    if not line.startswith("PKT,"):
        return None
    parts = line.strip().split(",")
    if len(parts) < 10:
        return None
    try:
        return {
            "idx": int(parts[3]),
            "ts_ms": int(parts[4]),
            "rssi": float(parts[5]),
            "snr": float(parts[6]),
            "cr": int(parts[7]),
            "crc_err": int(parts[8]),
            "len": int(parts[13]) if len(parts) > 13 else 0,
        }
    except (ValueError, IndexError):
        return None

def drain(s, seconds):
    """Collect all output for N seconds."""
    out = []
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        chunk = s.read(1024)
        if chunk:
            for line in chunk.decode(errors="replace").split("\n"):
                line = line.strip()
                if line:
                    out.append(line)
    return out

def run_config(tx, rx, sf, bw_khz, pa_dbm, npkts=50, pkt_len=64, gap_us=10000):
    """Run one sweep config. Returns dict of results."""
    bw_hz = bw_khz * 1000
    mod_str = f"LORA {sf} {bw_khz}"

    # Configure RX first
    cmd(rx, "ROLE NONE")
    time.sleep(0.1)
    cmd_expect(rx, f"MOD LORA {sf} {bw_khz}", "OK MOD")
    cmd_expect(rx, f"FREQ {FREQ}", "OK FREQ")
    cmd_expect(rx, f"PA {pa_dbm}", "OK PA")
    cmd_expect(rx, "ROLE RX", "OK ROLE RX")

    # Configure TX
    cmd(tx, "ROLE NONE")
    time.sleep(0.1)
    cmd_expect(tx, f"MOD LORA {sf} {bw_khz}", "OK MOD")
    cmd_expect(tx, f"FREQ {FREQ}", "OK FREQ")
    cmd_expect(tx, f"PA {pa_dbm}", "OK PA")
    cmd_expect(tx, "ROLE TX", "OK ROLE TX")
    cmd_expect(tx, "ARM TX", "OK ARMED")

    # Clear RX stats
    rx.reset_input_buffer()

    # Start TX burst
    tx.write(f"START N={npkts} LEN={pkt_len} GAP={gap_us}\r\n".encode())
    time.sleep(0.3)
    start_reply = tx.read(256).decode(errors="replace").strip()

    # Wait for TX done + all RX packets
    # Estimate time: npkts * (airtime + gap) + margin
    # Airtime for LoRa: roughly (8*sf*2**sf) / (bw_hz) * (pkt_len+ overhead)
    # Just wait generously
    wait_s = max(15, npkts * (gap_us / 1e6) + 10)
    tx_lines = drain(tx, wait_s)
    rx_lines = drain(rx, 5)

    # Parse RX packets
    pkts = [parse_pkt(l) for l in rx_lines]
    pkts = [p for p in pkts if p is not None]

    # Get RX stats
    rx_stat = cmd(rx, "STAT?", wait=0.5)
    tx_done = any("TX DONE" in l for l in tx_lines)

    return {
        "sf": sf,
        "bw_khz": bw_khz,
        "pa_dbm": pa_dbm,
        "npkts_sent": npkts,
        "npkts_rx": len(pkts),
        "pkts": pkts,
        "tx_done": tx_done,
        "rx_stat": rx_stat,
        "start_reply": start_reply,
    }

def main():
    print(f"E80-to-E80 LoRa Sweep — {datetime.now().isoformat()}")
    print(f"TX={TX_PORT} RX={RX_PORT} FREQ={FREQ}")
    print(f"Configs: {len(SWEEPS)} | 50 pkts each, 64B, 10ms gap")
    print()

    tx = serial.Serial(TX_PORT, BAUD, timeout=0.1)
    rx = serial.Serial(RX_PORT, BAUD, timeout=0.1)
    tx.reset_input_buffer()
    rx.reset_input_buffer()

    # Sync
    tx_id = cmd(tx, "ID?")
    rx_id = cmd(rx, "ID?")
    print(f"TX: {tx_id[:80]}")
    print(f"RX: {rx_id[:80]}")
    print()

    results = []
    for i, (sf, bw, pa) in enumerate(SWEEPS):
        print(f"[{i+1}/{len(SWEEPS)}] SF{sf} BW{bw} PA{pa}...", end=" ", flush=True)
        try:
            r = run_config(tx, rx, sf, bw, pa)
            results.append(r)
            rssi_vals = [p["rssi"] for p in r["pkts"]] if r["pkts"] else []
            snr_vals = [p["snr"] for p in r["pkts"]] if r["pkts"] else []
            rssi_avg = statistics.mean(rssi_vals) if rssi_vals else 0
            snr_avg = statistics.mean(snr_vals) if snr_vals else 0
            pct = 100 * r["npkts_rx"] / r["npkts_sent"]
            print(f"RX {r['npkts_rx']}/{r['npkts_sent']} ({pct:.0f}%) "
                  f"RSSI={rssi_avg:.1f} SNR={snr_avg:.1f} "
                  f"TX_DONE={r['tx_done']}")
        except Exception as e:
            print(f"ERROR: {e}")
            results.append({"sf": sf, "bw_khz": bw, "pa_dbm": pa, "error": str(e)})

        # Reset both boards between configs to avoid IWDG issues
        time.sleep(1)

    tx.close()
    rx.close()

    # Summary table
    print("\n" + "="*80)
    print(f"{'SF':>3} {'BW':>5} {'PA':>4} {'RX':>5} {'%':>5} {'RSSI':>7} {'SNR':>7} {'CRC_ERR':>8}")
    print("-"*80)
    for r in results:
        if "error" in r:
            print(f"{r['sf']:>3} {r['bw_khz']:>5} {r['pa_dbm']:>4}  ERROR: {r['error'][:40]}")
            continue
        rssi_vals = [p["rssi"] for p in r["pkts"]] if r["pkts"] else []
        snr_vals = [p["snr"] for p in r["pkts"]] if r["pkts"] else []
        rssi_avg = statistics.mean(rssi_vals) if rssi_vals else 0
        snr_avg = statistics.mean(snr_vals) if snr_vals else 0
        pct = 100 * r["npkts_rx"] / r["npkts_sent"]
        # Extract crc_err from stat
        crc_err = 0
        if "crc_err=" in r.get("rx_stat", ""):
            try:
                crc_err = int(r["rx_stat"].split("crc_err=")[1].split()[0])
            except:
                pass
        print(f"{r['sf']:>3} {r['bw_khz']:>5} {r['pa_dbm']:>4} {r['npkts_rx']:>5} {pct:>4.0f}% "
              f"{rssi_avg:>7.1f} {snr_avg:>7.1f} {crc_err:>8}")

    # Save CSV
    csv_path = f"/home/c03rad0r/repos/balloon-e80bench/sweep-results-{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv"
    with open(csv_path, "w") as f:
        f.write("sf,bw_khz,pa_dbm,npkts_sent,npkts_rx,pct,rssi_avg,snr_avg,crc_err\n")
        for r in results:
            if "error" in r:
                f.write(f"{r['sf']},{r['bw_khz']},{r['pa_dbm']},0,0,0,0,0,0\n")
                continue
            rssi_vals = [p["rssi"] for p in r["pkts"]] if r["pkts"] else []
            snr_vals = [p["snr"] for p in r["pkts"]] if r["pkts"] else []
            rssi_avg = statistics.mean(rssi_vals) if rssi_vals else 0
            snr_avg = statistics.mean(snr_vals) if snr_vals else 0
            pct = 100 * r["npkts_rx"] / r["npkts_sent"]
            crc_err = 0
            if "crc_err=" in r.get("rx_stat", ""):
                try:
                    crc_err = int(r["rx_stat"].split("crc_err=")[1].split()[0])
                except:
                    pass
            f.write(f"{r['sf']},{r['bw_khz']},{r['pa_dbm']},{r['npkts_sent']},{r['npkts_rx']},{pct:.1f},{rssi_avg:.1f},{snr_avg:.1f},{crc_err}\n")
    print(f"\nCSV saved: {csv_path}")
    return 0

if __name__ == "__main__":
    sys.exit(main())