#!/usr/bin/env python3
"""e80_sweep.py — E80-to-E80 LoRa sweep measurement.

Sweeps SF7-12 at BW125, SF7-9 at BW250, SF7-8 at BW500, and SF7-9 at PA=0.
Each config: 50 packets, 64B payload, PRBS-15 fill+verify, 10ms gap.
"""

import serial, time, statistics, os, sys
from datetime import datetime

TX_PORT = "/dev/ttyUSB3"
RX_PORT = "/dev/ttyUSB4"
BAUD = 2000000
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
        # ERR or empty — retry
        time.sleep(0.2)
    return r

def cmd_expect(s, msg, expect, wait=0.3, retries=5):
    """Send command until response contains `expect`."""
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
    parts = line[4:].split(",")
    if len(parts) != 23:
        return None
    return {
        "session": int(parts[0]), "config": int(parts[1]), "replicate": int(parts[2]),
        "seq": int(parts[3]), "ts_ms": int(parts[4]),
        "rssi": int(parts[5]), "snr": int(parts[6]),
        "crc_ok": int(parts[7]), "bit_err": int(parts[8]), "bytes_bad": int(parts[9]),
        "freq": int(parts[10]), "mod": parts[11], "sf": int(parts[12]),
        "bw": int(parts[13]), "cr": int(parts[14]), "power": int(parts[15]),
        "pkt_size": int(parts[16]),
    }

def parse_stat(text):
    d = {}
    for token in text.split():
        if "=" in token:
            k, v = token.split("=", 1)
            d[k] = v
    return d

def main():
    tx = serial.Serial(TX_PORT, BAUD, timeout=0.5)
    rx = serial.Serial(RX_PORT, BAUD, timeout=0.5)
    time.sleep(0.5)

    # Initial stop
    cmd(tx, "STOP", 0.5)
    cmd(rx, "STOP", 0.5)

    results = []
    raw_lines = []
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for idx, (sf, bw, pa) in enumerate(SWEEPS):
        print(f"\n=== Config {idx+1}/{len(SWEEPS)}: SF{sf} BW{bw} PA={pa} ===", flush=True)

        # Stop both (ignore errors — board may be idle/reset)
        cmd(tx, "STOP", 0.4)
        cmd(rx, "STOP", 0.4)
        time.sleep(0.3)

        # Configure RX — VERIFY role actually set (CH340 corrupts commands!)
        cmd_expect(rx, "ROLE RX", "ROLE RX", 0.3)
        cmd(rx, f"MOD loRa {sf} {bw}", 0.3)
        cmd(rx, f"FREQ {FREQ}", 0.3)
        cmd(rx, f"PA {pa}", 0.3)
        cmd(rx, "PRBS ON", 0.3)
        cmd(rx, f"SESSION {idx}", 0.3)
        cmd(rx, f"CONFIG {idx} 0", 0.3)

        # Configure TX (all BEFORE arming — IWDG starts at ARM TX!)
        cmd_expect(tx, "ROLE TX", "ROLE TX", 0.3)
        cmd(tx, f"MOD loRa {sf} {bw}", 0.3)
        cmd(tx, f"FREQ {FREQ}", 0.3)
        cmd(tx, f"PA {pa}", 0.3)
        cmd(tx, f"SESSION {idx}", 0.3)
        cmd(tx, f"CONFIG {idx} 0", 0.3)

        time.sleep(0.3)

        # ARM + START back-to-back (<1s — IWDG window is 2-4s, must be fast!)
        r = ""
        arm_ok = False
        for _ in range(3):
            cmd(tx, "ARM TX", 0.05)
            r = cmd(tx, "START N=50 LEN=64 GAP=10000", 0.25)
            if "OK START" in r:
                arm_ok = True
                break
            time.sleep(0.2)
        if not arm_ok:
            print(f"  !! ARM/START failed after retries — SWD recover needed", flush=True)
        print(f"  TX START: {r[:80]}", flush=True)

        # Capture RX — adaptive duration
        if sf >= 11:
            cap_dur = 90.0
        elif sf >= 9:
            cap_dur = 30.0
        else:
            cap_dur = 15.0

        print(f"  Capturing {cap_dur}s...")
        rx.reset_input_buffer()
        pkts = []
        start = time.time()
        buf = ""
        while time.time() - start < cap_dur:
            chunk = rx.read(rx.in_waiting or 1).decode(errors="replace")
            buf += chunk
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                line = line.strip()
                if line.startswith("PKT,"):
                    p = parse_pkt(line)
                    if p:
                        pkts.append(p)
                        raw_lines.append(f"# Config {idx}: SF{sf} BW{bw} PA={pa}")
                        raw_lines.append(line)

        # Stop TX
        cmd(tx, "STOP", 0.3)

        # Query stats
        tx_stat = parse_stat(cmd(tx, "STAT?", 0.5))
        rx_stat = parse_stat(cmd(rx, "STAT?", 0.5))

        # Compute results
        rx_count = len(pkts)
        rx_crc_err = int(rx_stat.get("crc_err", 0))
        rssi_vals = [p["rssi"] for p in pkts if p["rssi"] != 0]
        snr_vals = [p["snr"] for p in pkts if p["snr"] != 0]
        bit_err_total = sum(p["bit_err"] for p in pkts)
        bytes_bad_total = sum(p["bytes_bad"] for p in pkts)
        tx_sent = int(tx_stat.get("sent", 0))
        tx_sent_ok = int(tx_stat.get("sent_ok", 0))
        pkt_loss = round((1 - rx_count / 50) * 100, 1) if rx_count <= 50 else 0

        avg_rssi = round(statistics.mean(rssi_vals), 1) if rssi_vals else 0
        min_rssi = min(rssi_vals) if rssi_vals else 0
        max_rssi = max(rssi_vals) if rssi_vals else 0
        avg_snr = round(statistics.mean(snr_vals), 1) if snr_vals else 0
        min_snr = min(snr_vals) if snr_vals else 0
        max_snr = max(snr_vals) if snr_vals else 0

        r = {
            "idx": idx, "sf": sf, "bw": bw, "pa": pa,
            "tx_sent": tx_sent, "tx_sent_ok": tx_sent_ok,
            "rx_count": rx_count, "rx_crc_err": rx_crc_err,
            "avg_rssi": avg_rssi, "min_rssi": min_rssi, "max_rssi": max_rssi,
            "avg_snr": avg_snr, "min_snr": min_snr, "max_snr": max_snr,
            "bit_err_total": bit_err_total, "bytes_bad_total": bytes_bad_total,
            "pkt_loss_pct": pkt_loss,
        }
        results.append(r)
        print(f"  RX: {rx_count}/50 pkts, CRC_err={rx_crc_err}, RSSI={avg_rssi}dBm, SNR={avg_snr}dB, bit_err={bit_err_total}, loss={pkt_loss}%")

        time.sleep(0.5)

    tx.close()
    rx.close()

    # Write CSV
    csv_path = os.path.expanduser("~/repos/balloon-fresh/data/e80-sweep-2026-08-20.csv")
    with open(csv_path, "w") as f:
        f.write("config_idx,sf,bw_khz,pa_dbm,tx_sent,tx_sent_ok,rx_count,rx_crc_err,avg_rssi,min_rssi,max_rssi,avg_snr,min_snr,max_snr,bit_err_total,bytes_bad_total,pkt_loss_pct\n")
        for r in results:
            f.write(f"{r['idx']},{r['sf']},{r['bw']},{r['pa']},{r['tx_sent']},{r['tx_sent_ok']},{r['rx_count']},{r['rx_crc_err']},{r['avg_rssi']},{r['min_rssi']},{r['max_rssi']},{r['avg_snr']},{r['min_snr']},{r['max_snr']},{r['bit_err_total']},{r['bytes_bad_total']},{r['pkt_loss_pct']}\n")

    # Write raw
    raw_path = os.path.expanduser("~/repos/balloon-fresh/data/e80-sweep-2026-08-20-raw.txt")
    with open(raw_path, "w") as f:
        f.write(f"E80 LoRa Sweep — {timestamp}\n")
        f.write(f"Firmware: fw=e79f0c0, TX={TX_PORT}, RX={RX_PORT}, baud={BAUD}\n")
        f.write(f"Each config: 50 packets, 64B payload, PRBS-15, 10ms gap\n\n")
        for line in raw_lines:
            f.write(line + "\n")

    # Write summary
    sum_path = os.path.expanduser("~/repos/balloon-fresh/data/e80-sweep-2026-08-20-summary.txt")
    with open(sum_path, "w") as f:
        f.write(f"E80 LoRa Sweep Measurement — {timestamp}\n")
        f.write(f"Firmware: fw=e79f0c0\n")
        f.write(f"TX: {TX_PORT}, RX: {RX_PORT}, baud={BAUD}\n")
        f.write(f"Each config: N=50, LEN=64, PRBS-15, GAP=10ms\n\n")
        f.write(f"{'Cfg':>3} {'SF':>2} {'BW':>3} {'PA':>2} {'TX':>3} {'RX':>3} {'CRC':>3} {'RSSI':>6} {'SNR':>5} {'BER':>4} {'Loss%':>5}\n")
        f.write("-" * 50 + "\n")
        for r in results:
            f.write(f"{r['idx']:>3} {r['sf']:>2} {r['bw']:>3} {r['pa']:>2} {r['tx_sent']:>3} {r['rx_count']:>3} {r['rx_crc_err']:>3} {r['avg_rssi']:>6} {r['avg_snr']:>5} {r['bit_err_total']:>4} {r['pkt_loss_pct']:>5}\n")
        f.write("\n")
        # Highlights
        bit_err_configs = [r for r in results if r["bit_err_total"] > 0]
        loss_configs = [r for r in results if r["pkt_loss_pct"] > 0]
        f.write(f"Configs with bit_err > 0: {len(bit_err_configs)}\n")
        for r in bit_err_configs:
            f.write(f"  SF{r['sf']} BW{r['bw']} PA={r['pa']}: bit_err={r['bit_err_total']}, bytes_bad={r['bytes_bad_total']}\n")
        f.write(f"\nConfigs with packet loss: {len(loss_configs)}\n")
        for r in loss_configs:
            f.write(f"  SF{r['sf']} BW{r['bw']} PA={r['pa']}: {r['rx_count']}/50 received ({r['pkt_loss_pct']}% loss)\n")
        if snr_vals:
            best_snr = max(results, key=lambda x: x["avg_snr"])
            worst_snr = min(results, key=lambda x: x["avg_snr"])
            f.write(f"\nBest SNR: SF{best_snr['sf']} BW{best_snr['bw']} PA={best_snr['pa']} ({best_snr['avg_snr']}dB)\n")
            f.write(f"Worst SNR: SF{worst_snr['sf']} BW{worst_snr['bw']} PA={worst_snr['pa']} ({worst_snr['avg_snr']}dB)\n")

    print(f"\n=== RESULTS WRITTEN ===")
    print(f"CSV: {csv_path}")
    print(f"Raw: {raw_path}")
    print(f"Summary: {sum_path}")
    print(f"\nTotal configs: {len(results)}")
    print(f"Configs with 0 packet loss: {sum(1 for r in results if r['pkt_loss_pct'] == 0)}")
    print(f"Configs with bit_err > 0: {sum(1 for r in results if r['bit_err_total'] > 0)}")

if __name__ == "__main__":
    main()