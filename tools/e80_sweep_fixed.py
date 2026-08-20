#!/usr/bin/env python3
"""E80 LoRa sweep — multi-config with RX modulation sync.
FIX: Send MOD to BOTH TX and RX for each config.
"""
import serial, time, os, sys

BAUD = 2000000
TX_PORT = '/dev/ttyUSB3'
RX_PORT = '/dev/ttyUSB4'
N_PKTS = 50
PKT_LEN = 64
GAP_US = 10000

CONFIGS = [
    (0,  7, 125, 10),
    (1,  8, 125, 10),
    (2,  9, 125, 10),
    (3, 10, 125, 10),
    (4, 11, 125, 10),
    (5, 12, 125, 10),
    (6,  7, 250, 10),
    (7,  8, 250, 10),
    (8,  7, 500, 10),
    (9,  8, 500, 10),
]

TOA_MS = {
    (7,125): 46,   (7,250): 23,   (7,500): 12,
    (8,125): 82,   (8,250): 41,   (8,500): 21,
    (9,125): 164,  (9,250): 82,   (9,500): 41,
    (10,125): 328, (10,250): 164, (10,500): 82,
    (11,125): 656, (11,250): 328, (11,500): 164,
    (12,125): 1312,(12,250): 656, (12,500): 328,
}

def send(ser, cmd, wait=0.5):
    ser.reset_input_buffer()
    ser.write((cmd + '\n').encode())
    time.sleep(wait)
    resp = ser.read(4096).decode(errors='replace').strip()
    if resp and 'ERR' in resp:
        print(f"  [!] ERROR to '{cmd}': {resp}", flush=True)
    return resp

def main():
    tx = serial.Serial(TX_PORT, BAUD, timeout=5)
    rx = serial.Serial(RX_PORT, BAUD, timeout=5)

    print("RX: ROLE RX", flush=True)
    print(f"  {send(rx, 'ROLE RX', 1)}", flush=True)
    print("RX: PRBS ON", flush=True)
    print(f"  {send(rx, 'PRBS ON', 0.5)}", flush=True)
    print("TX: ROLE TX", flush=True)
    print(f"  {send(tx, 'ROLE TX', 1)}", flush=True)
    print("TX: ARM TX", flush=True)
    print(f"  {send(tx, 'ARM TX', 0.3)}", flush=True)

    all_pkts = []
    all_stats = []

    for cfg_id, sf, bw, power in CONFIGS:
        print(f"\n--- Config {cfg_id}: SF{sf} BW{bw} PWR={power} ---", flush=True)

        # RX: update modulation (calls radio_rearm_rx in firmware)
        print(f"  RX MOD lora {sf} {bw}", flush=True)
        send(rx, f'MOD lora {sf} {bw}', 0.5)
        send(rx, f'CONFIG {cfg_id} 0', 0.3)
        send(rx, f'START N={N_PKTS} LEN={PKT_LEN} GAP={GAP_US}', 0.3)

        # TX: update modulation (only updates struct, applied at START)
        send(tx, f'MOD lora {sf} {bw}', 0.3)
        send(tx, f'PA {power}', 0.3)
        send(tx, f'CONFIG {cfg_id} 0', 0.3)

        # Settle
        time.sleep(0.5)
        rx.reset_input_buffer()

        # Start TX burst
        send(tx, f'START N={N_PKTS} LEN={PKT_LEN} GAP={GAP_US}', 0.3)

        toa = TOA_MS.get((sf, bw), 100)
        per_pkt_s = (toa + GAP_US / 1000) / 1000.0
        total_s = per_pkt_s * N_PKTS
        wait_s = max(total_s * 1.5, 5)
        print(f"  TOA={toa}ms/pkt, est={total_s:.1f}s, wait={wait_s:.1f}s", flush=True)

        time.sleep(wait_s)

        rx_data = rx.read(65536).decode(errors='replace')
        pkts = [l.strip() for l in rx_data.split('\n') if l.strip().startswith('PKT,')]
        all_pkts.extend(pkts)
        print(f"  Captured {len(pkts)} PKT lines", flush=True)

        tx_stat = send(tx, 'STAT?', 1)
        rx_stat = send(rx, 'STAT?', 1)
        all_stats.append(f"=== Config {cfg_id} (SF{sf} BW{bw} PWR={power}) ===")
        all_stats.append(f"TX: {tx_stat}")
        all_stats.append(f"RX: {rx_stat}")
        all_stats.append("")
        print(f"  TX: {tx_stat[:120]}", flush=True)
        print(f"  RX: {rx_stat[:120]}", flush=True)

        time.sleep(1)

    tx.close()
    rx.close()

    out_dir = os.path.expanduser('~/repos/balloon-fresh/data/e80-sweep-2026-08-20')
    os.makedirs(out_dir, exist_ok=True)

    csv_path = os.path.join(out_dir, 'e80_sweep_20260820.csv')
    with open(csv_path, 'w') as f:
        f.write('PKT,session_id,config_id,replicate,seq,ts_ms,rssi_dbm,snr_db,crc_ok,bit_err,bytes_bad,freq_hz,mod,sf,bw_khz,cr,power_dbm,pkt_size,gps_fix,gps_lat,gps_lon,gps_alt,gps_sats,gps_hdop\n')
        for line in all_pkts:
            f.write(line + '\n')

    stats_path = os.path.join(out_dir, 'e80_sweep_20260820_stats.txt')
    with open(stats_path, 'w') as f:
        f.write('\n'.join(all_stats))

    print(f"\n=== SWEEP COMPLETE ===", flush=True)
    print(f"Total PKT lines: {len(all_pkts)}", flush=True)
    print(f"CSV: {csv_path}", flush=True)
    print(f"Stats: {stats_path}", flush=True)

if __name__ == '__main__':
    main()
