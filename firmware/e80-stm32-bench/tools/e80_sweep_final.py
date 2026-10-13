#!/usr/bin/env python3
"""e80_sweep_final.py — E80-to-E80 LoRa sweep measurement (definitive).

Both boards: E80 STM32 bench, fw=698687d (T5a: pcrc16 + NVIC fix).
PKT format (25 fields):
  [0]PKT [1]session [2]config [3]replicate [4]pkt_idx [5]ts_ms
  [6]rssi_dbm [7]snr_db [8]crc_ok [9]bit_err [10]?
  [11]freq_hz [12]mod [13]sf [14]bw_khz [15]cr [16]pa_dbm [17]len
  [18-23] zeros [24]pcrc16

Port mapping (POST-SWAP, verify at runtime):
  TX = /dev/ttyUSB4, SWD probe ttyACM1 serial 148757200D2D1425
  RX = /dev/ttyUSB3, SWD probe ttyACM0 serial 203584200D2D0D42

SWD reset between configs avoids ROLE NONE hang bug.
RX configured before TX (proven E2E sequence).
No ROLE NONE ever sent.
"""

import serial, time, statistics, os, sys, subprocess, csv
from datetime import datetime

# ---- Config ----
TX_PORT = "/dev/ttyUSB4"
RX_PORT = "/dev/ttyUSB3"
TX_PROBE = "148757200D2D1425"
RX_PROBE = "203584200D2D0D42"
BAUD = 115200
FREQ = 868000000
FW_DIR = os.path.expanduser("~/repos/balloon-e80bench/firmware/e80-stm32-bench")

SWEEPS = [
    # (sf, bw_khz, pa_dbm)
    (7, 125, 10), (8, 125, 10), (9, 125, 10), (10, 125, 10),
    (11, 125, 10), (12, 125, 10),
    (7, 250, 10), (8, 250, 10), (9, 250, 10),
    (7, 500, 10), (8, 500, 10),
    (7, 125, 0), (8, 125, 0), (9, 125, 0),
]
NPKTS = 50
PKT_LEN = 64
GAP_US = 10000

# Airtime estimates (seconds per packet) for wait calculation
TOA = {
    125: {7: 0.05, 8: 0.09, 9: 0.17, 10: 0.33, 11: 0.66, 12: 1.31},
    250: {7: 0.025, 8: 0.046, 9: 0.085},
    500: {7: 0.013, 8: 0.023},
}


def swd_reset(probe_serial):
    """Reset board via SWD. stdout/stderr -> DEVNULL (avoids pipe deadlock).
    Uses 'reset halt; resume' instead of 'reset run' — the latter sometimes
    leaves the UART in a bad state on these boards."""
    subprocess.run(
        ["/usr/bin/openocd", "-f", "interface/cmsis-dap.cfg",
         "-f", "target/stm32f1x.cfg",
         "-c", f"transport select swd; adapter serial {probe_serial}; "
               f"init; reset halt; resume; exit"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        timeout=30, cwd=FW_DIR,
    )
    time.sleep(2.0)


def readline(ser, timeout=3.0):
    deadline = time.monotonic() + timeout
    buf = bytearray()
    while time.monotonic() < deadline:
        chunk = ser.read(256)
        if chunk:
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                txt = line.rstrip(b"\r").decode(errors="replace").strip()
                if txt:
                    return txt
    return None


def cmd(ser, line, timeout=5.0):
    """Send command, return first reply line. Retries once on empty."""
    for attempt in range(2):
        ser.reset_input_buffer()
        ser.write((line + "\r\n").encode())
        r = readline(ser, timeout)
        if r:
            return r
        time.sleep(0.5)
    return None


def drain_lines(ser, seconds):
    out = []
    deadline = time.monotonic() + seconds
    leftover = bytearray()
    while time.monotonic() < deadline:
        chunk = ser.read(1024)
        if chunk:
            leftover += chunk
            while b"\n" in leftover:
                line, leftover = leftover.split(b"\n", 1)
                txt = line.rstrip(b"\r").decode(errors="replace").strip()
                if txt:
                    out.append(txt)
    return out


def parse_pkt(line):
    """Parse PKT line: 25 comma-separated fields."""
    if not line.startswith("PKT,"):
        return None
    p = line.strip().split(",")
    if len(p) < 10:
        return None
    try:
        return {
            "idx": int(p[4]),
            "ts_ms": int(p[5]),
            "rssi": float(p[6]),
            "snr": float(p[7]),
            "crc_ok": int(p[8]),
            "bit_err": int(p[9]),
            "sf": int(p[13]),
            "bw": int(p[14]),
            "pa": int(p[16]),
            "pkt_len": int(p[17]),
            "pcrc16": int(p[24]) if len(p) > 24 else None,
        }
    except (ValueError, IndexError):
        return None


def parse_stat(stat):
    d = {}
    for tok in stat.split()[1:]:
        if "=" in tok:
            k, v = tok.split("=", 1)
            try:
                d[k] = float(v) if "." in v else int(v)
            except ValueError:
                d[k] = v
    return d


def run_config(sf, bw, pa):
    swd_reset(TX_PROBE)
    swd_reset(RX_PROBE)

    tx = serial.Serial(TX_PORT, BAUD, timeout=0.1)
    rx = serial.Serial(RX_PORT, BAUD, timeout=0.1)

    try:
        t_id = cmd(tx, "ID?")
        r_id = cmd(rx, "ID?")
        if not t_id or "E80BENCH" not in t_id:
            raise RuntimeError(f"TX not responsive: {t_id!r}")
        if not r_id or "E80BENCH" not in r_id:
            raise RuntimeError(f"RX not responsive: {r_id!r}")

        # RX first
        for s, label in [(rx, "RX"), (tx, "TX")]:
            r = cmd(s, f"MOD LORA {sf} {bw}")
            if not r or not r.startswith("OK MOD"):
                raise RuntimeError(f"{label} MOD: {r!r}")
            r = cmd(s, f"FREQ {FREQ}")
            if not r or not r.startswith("OK FREQ"):
                raise RuntimeError(f"{label} FREQ: {r!r}")
            r = cmd(s, f"PA {pa}")
            if not r or not r.startswith("OK PA"):
                raise RuntimeError(f"{label} PA: {r!r}")

        r = cmd(rx, "ROLE RX")
        if not r or not r.startswith("OK ROLE RX"):
            raise RuntimeError(f"RX ROLE: {r!r}")
        r = cmd(tx, "ROLE TX")
        if not r or not r.startswith("OK ROLE TX"):
            raise RuntimeError(f"TX ROLE: {r!r}")
        r = cmd(tx, "ARM TX")
        if not r or not r.startswith("OK ARMED"):
            raise RuntimeError(f"TX ARM: {r!r}")

        rx.reset_input_buffer()
        tx.write(f"START N={NPKTS} LEN={PKT_LEN} GAP={GAP_US}\r\n".encode())
        start_reply = readline(tx, 3.0)

        toa = TOA.get(bw, {}).get(sf, 1.5)
        wait_s = NPKTS * (toa + GAP_US / 1e6) + 10

        tx_lines = drain_lines(tx, wait_s)
        rx_lines = drain_lines(rx, 5)

        tx_done = any("TX DONE" in l for l in tx_lines)
        stat = cmd(rx, "STAT?")
        sd = parse_stat(stat) if stat else {}

        pkts = [parse_pkt(l) for l in rx_lines]
        pkts = [p for p in pkts if p is not None]

        rssi_list = [p["rssi"] for p in pkts]
        snr_list = [p["snr"] for p in pkts]
        bit_err_list = [p["bit_err"] for p in pkts]

        return {
            "sf": sf, "bw": bw, "pa": pa,
            "rx_pkts": len(pkts),
            "crc_err": sd.get("crc_err", 0),
            "rssi_avg": round(statistics.mean(rssi_list), 1) if rssi_list else None,
            "rssi_min": round(min(rssi_list), 1) if rssi_list else None,
            "rssi_max": round(max(rssi_list), 1) if rssi_list else None,
            "snr_avg": round(statistics.mean(snr_list), 1) if snr_list else None,
            "bit_err_total": sum(bit_err_list) if bit_err_list else 0,
            "tx_done": tx_done,
            "start_reply": start_reply,
            "rx_stat": stat,
            "pkts": pkts,
        }
    finally:
        tx.close()
        rx.close()


def main():
    ts = datetime.now()
    print(f"E80 LoRa Sweep — {ts.isoformat()}")
    print(f"TX={TX_PORT} (probe {TX_PROBE}) RX={RX_PORT} (probe {RX_PROBE})")
    print(f"FW=698687d  {NPKTS}pkts {PKT_LEN}B gap={GAP_US}us freq={FREQ}")
    print(f"Configs: {len(SWEEPS)}")
    print("=" * 80)
    sys.stdout.flush()

    results = []
    for i, (sf, bw, pa) in enumerate(SWEEPS):
        print(f"[{i+1}/{len(SWEEPS)}] SF{sf} BW{bw} PA{pa:+d} ...", end=" ", flush=True)
        try:
            r = run_config(sf, bw, pa)
            results.append(r)
            rssi_s = f"{r['rssi_avg']:.1f}" if r['rssi_avg'] is not None else "-"
            snr_s = f"{r['snr_avg']:.1f}" if r['snr_avg'] is not None else "-"
            print(f"rx={r['rx_pkts']}/{NPKTS} rssi={rssi_s} snr={snr_s} "
                  f"crc={r['crc_err']} biterr={r['bit_err_total']} done={r['tx_done']}")
        except Exception as e:
            print(f"FAIL: {e}")
            results.append({"sf": sf, "bw": bw, "pa": pa, "error": str(e)})
        sys.stdout.flush()

    # Summary table
    print("\n" + "=" * 90)
    hdr = f"{'SF':>3} {'BW':>4} {'PA':>3} {'RX':>7} {'%':>5} {'RSSI':>7} {'SNR':>5} {'CRC':>4} {'BitErr':>7} {'TXDone':>7}"
    print(hdr)
    print("-" * 90)
    for r in results:
        if "error" in r:
            print(f"{r['sf']:>3} {r['bw']:>4} {r['pa']:>3}   ERROR: {r['error'][:50]}")
            continue
        pct = 100 * r['rx_pkts'] / NPKTS
        rssi_s = f"{r['rssi_avg']:.1f}" if r['rssi_avg'] is not None else "-"
        snr_s = f"{r['snr_avg']:.1f}" if r['snr_avg'] is not None else "-"
        done_s = "yes" if r['tx_done'] else "no"
        print(f"{r['sf']:>3} {r['bw']:>4} {r['pa']:>3} {r['rx_pkts']:>4}/{NPKTS} {pct:>4.0f}% "
              f"{rssi_s:>7} {snr_s:>5} {r['crc_err']:>4} {r['bit_err_total']:>7} {done_s:>7}")

    # Save CSV (summary)
    ts_str = ts.strftime("%Y%m%d-%H%M%S")
    csv_path = os.path.join(FW_DIR, "..", "..", f"sweep-results-{ts_str}.csv")
    csv_path = os.path.abspath(csv_path)
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sf", "bw_khz", "pa_dbm", "npkts_sent", "npkts_rx",
                     "pct", "rssi_avg", "rssi_min", "rssi_max", "snr_avg",
                     "crc_err", "bit_err_total", "tx_done"])
        for r in results:
            if "error" in r:
                w.writerow([r['sf'], r['bw'], r['pa'], 0, 0, 0, "", "", "", "", "", "", ""])
            else:
                pct = 100 * r['rx_pkts'] / NPKTS
                w.writerow([r['sf'], r['bw'], r['pa'], NPKTS, r['rx_pkts'],
                            f"{pct:.1f}", r['rssi_avg'] or "", r['rssi_min'] or "",
                            r['rssi_max'] or "", r['snr_avg'] or "",
                            r['crc_err'], r['bit_err_total'], r['tx_done']])
    print(f"\nSummary CSV: {csv_path}")

    # Save per-packet CSV
    pkt_csv = csv_path.replace("sweep-results-", "sweep-pkts-")
    with open(pkt_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sf", "bw_khz", "pa_dbm", "pkt_idx", "ts_ms", "rssi_dbm",
                     "snr_db", "crc_ok", "bit_err", "pkt_len", "pcrc16"])
        for r in results:
            if "error" in r or "pkts" not in r:
                continue
            for p in r["pkts"]:
                w.writerow([r['sf'], r['bw'], r['pa'], p['idx'], p['ts_ms'],
                            p['rssi'], p['snr'], p['crc_ok'], p['bit_err'],
                            p['pkt_len'], p['pcrc16'] or ""])
    print(f"Per-packet CSV: {pkt_csv}")

    # Save markdown report
    md_path = csv_path.replace(".csv", ".md")
    with open(md_path, "w") as f:
        f.write(f"# E80-to-E80 LoRa Sweep — {ts.date()}\n\n")
        f.write(f"**Date:** {ts.isoformat()}\n")
        f.write(f"**Firmware:** 698687d (T5a: pcrc16 + NVIC race fix)\n")
        f.write(f"**TX:** {TX_PORT} (SWD probe serial {TX_PROBE})\n")
        f.write(f"**RX:** {RX_PORT} (SWD probe serial {RX_PROBE})\n")
        f.write(f"**Frequency:** {FREQ} Hz\n")
        f.write(f"**Packets per config:** {NPKTS}\n")
        f.write(f"**Payload:** {PKT_LEN} bytes PRBS\n")
        f.write(f"**Gap:** {GAP_US} µs\n")
        f.write(f"**Configs:** {len(SWEEPS)}\n\n")
        f.write("## Results\n\n")
        f.write("| SF | BW (kHz) | PA (dBm) | RX | % | RSSI avg (dBm) | SNR avg (dB) | CRC err | Bit err | TX done |\n")
        f.write("|---|---|---|---|---|---|---|---|---|---|\n")
        for r in results:
            if "error" in r:
                f.write(f"| {r['sf']} | {r['bw']} | {r['pa']} | ERROR | | | | | | |\n")
                continue
            pct = 100 * r['rx_pkts'] / NPKTS
            rssi_s = f"{r['rssi_avg']:.1f}" if r['rssi_avg'] is not None else "-"
            snr_s = f"{r['snr_avg']:.1f}" if r['snr_avg'] is not None else "-"
            done_s = "✓" if r['tx_done'] else "✗"
            f.write(f"| {r['sf']} | {r['bw']} | {r['pa']:+d} | {r['rx_pkts']}/{NPKTS} | {pct:.0f}% "
                    f"| {rssi_s} | {snr_s} | {r['crc_err']} | {r['bit_err_total']} | {done_s} |\n")
        f.write(f"\n## Files\n\n")
        f.write(f"- Summary CSV: `sweep-results-{ts_str}.csv`\n")
        f.write(f"- Per-packet CSV: `sweep-pkts-{ts_str}.csv`\n")
        f.write(f"- This report: `sweep-results-{ts_str}.md`\n")
        f.write(f"- Sweep script: `firmware/e80-stm32-bench/tools/e80_sweep_final.py`\n")
    print(f"Markdown report: {md_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())