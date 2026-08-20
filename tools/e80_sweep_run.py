#!/usr/bin/env python3
"""E80 LoRa sweep — 10 configs, 50 pkts each, harmonized 23-field format."""
import serial, time, os, sys

BAUD = 2000000
TX_PORT = '/dev/ttyUSB3'
RX_PORT = '/dev/ttyUSB4'
N_PKTS = 50
PKT_LEN = 64
GAP_US = 10000

# (config_id, SF, BW_kHz, power_dbm)
CONFIGS = [
    (0, 7,  125, 10),
    (1, 8,  125, 10),
    (2, 9,  125, 10),
    (3, 10, 125, 10),
    (4, 11, 125, 10),
    (5, 12, 125, 10),
    (6, 7,  250, 10),
    (7, 8,  250, 10),
    (8, 7,  500, 10),
    (9, 8,  500, 10),
]

# Approximate time-on-air per packet (ms) for LoRa CR=4/5, 64B payload
# SF7=46, SF8=82, SF9=164, SF10=328, SF11=656, SF12=1312 at BW125
# BW250 halves, BW500 quarters
TOA_MS = {
    (7,125): 46,  (7,250): 23,  (7,500): 12,
    (8,125): 82,  (8,250): 41,  (8,500): 21,
    (9,125): 164, (9,250): 82,  (9,500): 41,
    (10,125): 328,(10,250): 164,(10,500): 82,
    (11,125): 656,(11,250): 328,(11,500): 164,
    (12,125): 1312,(12,250): 656,(12,500): 328,
}

def send(ser, cmd, wait=0.5):
    ser.reset_input_buffer()
    ser.write((cmd + '\n').encode())
    time.sleep(wait)
    return ser.read(4096).decode(errors='replace').strip()

def main():
    tx = serial.Serial(TX_PORT, BAUD, timeout=5)
    rx = serial.Serial(RX_PORT, BAUD, timeout=5)
    
    # Setup RX
    print("RX: ROLE RX", flush=True)
    send(rx, 'ROLE RX', 1)
    print("RX: PRBS ON", flush=True)
    send(rx, 'PRBS ON', 0.5)
    
    all_pkts = []
    all_stats = []
    
    for cfg_id, sf, bw, power in CONFIGS:
        print(f"\n--- Config {cfg_id}: SF{sf} BW{bw} PWR={power} ---", flush=True)
        
        # Set config_id on RX
        send(rx, f'CONFIG {cfg_id} 0', 0.3)
        
        # Configure TX
        send(tx, 'ROLE TX', 0.5)
        send(tx, f'MOD lora {sf} {bw}', 0.3)
        send(tx, f'PA {power}', 0.3)
        send(tx, f'CONFIG {cfg_id} 0', 0.3)
        send(tx, 'ARM TX', 0.3)
        
        # Clear RX buffer
        rx.reset_input_buffer()
        
        # Start TX
        send(tx, f'START N={N_PKTS} LEN={PKT_LEN} GAP={GAP_US}', 0.3)
        
        # Calculate wait time
        toa = TOA_MS.get((sf, bw), 100)
        per_pkt_s = (toa + GAP_US/1000) / 1000.0
        total_s = per_pkt_s * N_PKTS
        wait_s = max(total_s * 1.5, 5)
        print(f"  TOA={toa}ms/pkt, est={total_s:.1f}s, wait={wait_s:.1f}s", flush=True)
        
        time.sleep(wait_s)
        
        # Read PKT lines
        rx_data = rx.read(65536).decode(errors='replace')
        pkts = [l.strip() for l in rx_data.split('\n') if l.strip().startswith('PKT,')]
        all_pkts.extend(pkts)
        print(f"  Captured {len(pkts)} PKT lines", flush=True)
        
        # STAT?
        tx_stat = send(tx, 'STAT?', 1)
        rx_stat = send(rx, 'STAT?', 1)
        all_stats.append(f"=== Config {cfg_id} (SF{sf} BW{bw} PWR={power}) ===")
        all_stats.append(f"TX: {tx_stat}")
        all_stats.append(f"RX: {rx_stat}")
        all_stats.append("")
        print(f"  TX: {tx_stat[:100]}", flush=True)
        print(f"  RX: {rx_stat[:100]}", flush=True)
        
        time.sleep(1)
    
    tx.close()
    rx.close()
    
    # Save
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