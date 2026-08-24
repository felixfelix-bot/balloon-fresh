#!/usr/bin/env python3
"""e80_sweep2.py — Robust E80-to-E80 LoRa sweep.

Differences from v1:
- SWD reset both boards between configs (avoids ROLE NONE hang bug)
- RX configured BEFORE TX (proven sequence from manual E2E)
- No ROLE NONE ever sent
- Proper line-based reads
"""

import serial, time, statistics, os, sys, subprocess
from datetime import datetime

TX_PORT = "/dev/ttyUSB4"
RX_PORT = "/dev/ttyUSB3"
TX_PROBE = "148757200D2D1425"   # ttyACM1
RX_PROBE = "203584200D2D0D42"   # ttyACM0
BAUD = 115200
FREQ = 868000000

SWEEPS = [
    (7, 125, 10), (8, 125, 10), (9, 125, 10), (10, 125, 10),
    (11, 125, 10), (12, 125, 10),
    (7, 250, 10), (8, 250, 10), (9, 250, 10),
    (7, 500, 10), (8, 500, 10),
    (7, 125, 0), (8, 125, 0), (9, 125, 0),
]

NPKTS = 50
PKT_LEN = 64
GAP_US = 10000

def swd_reset(probe_serial):
    subprocess.run([
        "/usr/bin/openocd", "-f", "interface/cmsis-dap.cfg",
        "-f", "target/stm32f1x.cfg",
        "-c", f"transport select swd; adapter serial {probe_serial}; init; reset run; exit"
    ], capture_output=True, timeout=30, cwd=os.path.expanduser("~/repos/balloon-e80bench/firmware/e80-stm32-bench"))
    time.sleep(1.5)

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

def cmd(ser, line, timeout=3.0):
    ser.reset_input_buffer()
    ser.write((line + "\r\n").encode())
    return readline(ser, timeout)

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
    # Fresh boards
    swd_reset(TX_PROBE)
    swd_reset(RX_PROBE)

    tx = serial.Serial(TX_PORT, BAUD, timeout=0.1)
    rx = serial.Serial(RX_PORT, BAUD, timeout=0.1)

    try:
        # Sync
        t_id = cmd(tx, "ID?")
        r_id = cmd(rx, "ID?")
        if not t_id or "E80BENCH" not in t_id:
            raise RuntimeError(f"TX not responsive: {t_id!r}")
        if not r_id or "E80BENCH" not in r_id:
            raise RuntimeError(f"RX not responsive: {r_id!r}")

        # RX first (proven sequence)
        r = cmd(rx, f"MOD LORA {sf} {bw}")
        if not r or not r.startswith("OK MOD"): raise RuntimeError(f"RX MOD: {r!r}")
        r = cmd(rx, f"FREQ {FREQ}")
        if not r or not r.startswith("OK FREQ"): raise RuntimeError(f"RX FREQ: {r!r}")
        r = cmd(rx, f"PA {pa}")
        if not r or not r.startswith("OK PA"): raise RuntimeError(f"RX PA: {r!r}")
        r = cmd(rx, "ROLE RX")
        if not r or not r.startswith("OK ROLE RX"): raise RuntimeError(f"RX ROLE: {r!r}")

        # TX
        r = cmd(tx, f"MOD LORA {sf} {bw}")
        if not r or not r.startswith("OK MOD"): raise RuntimeError(f"TX MOD: {r!r}")
        r = cmd(tx, f"FREQ {FREQ}")
        if not r or not r.startswith("OK FREQ"): raise RuntimeError(f"TX FREQ: {r!r}")
        r = cmd(tx, f"PA {pa}")
        if not r or not r.startswith("OK PA"): raise RuntimeError(f"TX PA: {r!r}")
        r = cmd(tx, "ROLE TX")
        if not r or not r.startswith("OK ROLE TX"): raise RuntimeError(f"TX ROLE: {r!r}")
        r = cmd(tx, "ARM TX")
        if not r or not r.startswith("OK ARMED"): raise RuntimeError(f"TX ARM: {r!r}")

        # Clear RX input before burst
        rx.reset_input_buffer()

        # START immediately after ARM (IWDG rule)
        tx.write(f"START N={NPKTS} LEN={PKT_LEN} GAP={GAP_US}\r\n".encode())
        start_reply = readline(tx, 3.0)

        # Estimate wait: SF12 @ BW125 64B ≈ 1.3s/pkt → 50pkts ≈ 65s + gaps
        toa_map = {125: {7:0.05, 8:0.09, 9:0.17, 10:0.33, 11:0.65, 12:1.31},
                   250: {7:0.025, 8:0.045, 9:0.085},
                   500: {7:0.013, 8:0.023}}
        toa = toa_map.get(bw, {}).get(sf, 1.5)
        wait_s = NPKTS * (toa + GAP_US/1e6) + 8

        tx_lines = drain_lines(tx, wait_s)
        rx_lines = drain_lines(rx, 5)

        tx_done = any("TX DONE" in l for l in tx_lines)
        stat = cmd(rx, "STAT?")
        sd = parse_stat(stat) if stat else {}

        # Count PKT lines
        npkt_lines = sum(1 for l in rx_lines if l.startswith("PKT,"))
        rssi_list = []
        snr_list = []
        for l in rx_lines:
            if l.startswith("PKT,"):
                p = l.split(",")
                try:
                    rssi_list.append(float(p[5]))
                    snr_list.append(float(p[6]))
                except (ValueError, IndexError):
                    pass

        return {
            "sf": sf, "bw": bw, "pa": pa,
            "rx_pkts": npkt_lines,
            "rx_stat_rx": sd.get("rx", 0),
            "crc_err": sd.get("crc_err", 0),
            "rssi_avg": statistics.mean(rssi_list) if rssi_list else None,
            "snr_avg": statistics.mean(snr_list) if snr_list else None,
            "tx_done": tx_done,
            "start_reply": start_reply,
        }
    finally:
        tx.close()
        rx.close()

def main():
    print(f"E80 LoRa Sweep v2 — {datetime.now().isoformat()}")
    print(f"TX={TX_PORT} RX={RX_PORT} {NPKTS}pkts {PKT_LEN}B gap={GAP_US}us")
    print()
    results = []
    for i, (sf, bw, pa) in enumerate(SWEEPS):
        print(f"[{i+1}/{len(SWEEPS)}] SF{sf} BW{bw} PA{pa:+d} ...", end=" ", flush=True)
        try:
            r = run_config(sf, bw, pa)
            results.append(r)
            rssi_s = f"{r['rssi_avg']:.1f}" if r['rssi_avg'] is not None else "  -"
            snr_s = f"{r['snr_avg']:.1f}" if r['snr_avg'] is not None else " -"
            print(f"rx={r['rx_pkts']}/{NPKTS} rssi={rssi_s} snr={snr_s} crc={r['crc_err']} done={r['tx_done']}")
        except Exception as e:
            print(f"FAIL: {e}")
            results.append({"sf": sf, "bw": bw, "pa": pa, "error": str(e)})
        sys.stdout.flush()

    # Summary
    print("\n" + "="*76)
    print(f"{'SF':>3} {'BW':>4} {'PA':>3} {'RX':>6} {'%':>5} {'RSSI':>6} {'SNR':>5} {'CRC':>4}")
    print("-"*76)
    for r in results:
        if "error" in r:
            print(f"{r['sf']:>3} {r['bw']:>4} {r['pa']:>3}   ERROR {r['error'][:45]}")
            continue
        pct = 100*r['rx_pkts']/NPKTS
        rssi_s = f"{r['rssi_avg']:.1f}" if r['rssi_avg'] is not None else "-"
        snr_s = f"{r['snr_avg']:.1f}" if r['snr_avg'] is not None else "-"
        print(f"{r['sf']:>3} {r['bw']:>4} {r['pa']:>3} {r['rx_pkts']:>4}/{NPKTS} {pct:>4.0f}% {rssi_s:>6} {snr_s:>5} {r['crc_err']:>4}")

    csv = f"/home/c03rad0r/repos/balloon-e80bench/sweep2-{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv"
    with open(csv, "w") as f:
        f.write("sf,bw_khz,pa_dbm,npkts_sent,npkts_rx,pct,rssi_avg,snr_avg,crc_err\n")
        for r in results:
            if "error" in r:
                f.write(f"{r['sf']},{r['bw']},{r['pa']},0,0,0,,,0\n")
            else:
                pct = 100*r['rx_pkts']/NPKTS
                f.write(f"{r['sf']},{r['bw']},{r['pa']},{NPKTS},{r['rx_pkts']},{pct:.1f},"
                        f"{r['rssi_avg'] if r['rssi_avg'] is not None else ''},"
                        f"{r['snr_avg'] if r['snr_avg'] is not None else ''},{r['crc_err']}\n")
    print(f"\nCSV: {csv}")
    return 0

if __name__ == "__main__":
    sys.exit(main())