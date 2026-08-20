#!/usr/bin/env python3
"""
E80 Full LoRa Sweep — 10 configs, 50 packets each = 500 total.
Boards: TX at /dev/ttyUSB3, RX at /dev/ttyUSB4, 2000000 baud.

Uses the same BoardSerial pattern as e80_bench_ctl.py:
  - \r\n line endings
  - readline() with prefix matching for responses
  - PKT lines are comma-separated (23 fields after "PKT")
"""
import os
import sys
import time
import csv
import serial
from datetime import datetime

TX_PORT = '/dev/ttyUSB3'
RX_PORT = '/dev/ttyUSB4'
BAUD = 2000000
N_PKTS = 50
LEN = 64
GAP = 10000  # microseconds
TIMEOUT_S = 60  # per config

# Sweep matrix: (config_id, SF, BW_kHz, POWER)
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

DATA_DIR = os.path.expanduser('~/repos/balloon-fresh/data/e80-sweep-2026-08-20')

# PKT CSV field names (23 fields after "PKT")
PKT_FIELDS = [
    'pkt_type',           # "PKT"
    'session_id',
    'config_id',
    'replicate',
    'seq',
    'ts_ms',
    'rssi_dbm',
    'snr_db',
    'crc_ok',
    'bit_err',
    'bytes_bad',
    'freq_hz',
    'mod',
    'sf',
    'bw_khz',
    'cr',
    'power',
    'pkt_size',
    'gps_fix',
    'gps_lat',
    'gps_lon',
    'gps_alt',
    'gps_sats',
    'gps_hdop',
]


class BoardSerial:
    """Line-oriented serial console for E80 bench boards.
    
    Boards reply 'OK ...' or 'ERR <reason>' to state commands;
    'ID ...' to ID? and 'STAT ...' to STAT? (no OK prefix on those two).
    PKT lines start with 'PKT,' (comma-separated).
    """

    def __init__(self, port, baud=BAUD, timeout=5.0):
        self.ser = serial.Serial(
            port=port,
            baudrate=baud,
            parity='N',
            stopbits=1,
            bytesize=8,
            timeout=timeout,
        )
        self.port = port
        self.drain()

    def drain(self, quiet=0.5):
        """Consume boot noise / stale output until quiet for `quiet` seconds."""
        self.ser.timeout = quiet
        while True:
            line = self.ser.readline()
            if not line:
                break
            # Print any interesting lines
            text = line.decode('ascii', errors='replace').strip()
            if text:
                print(f"  [drain {self.port}] {text[:120]}")
        self.ser.timeout = 5.0

    def write_cmd(self, line):
        """Send a command line with \r\n."""
        self.ser.write((line + '\r\n').encode())

    def query(self, line, prefixes=('OK', 'ERR', 'STAT', 'ID'), timeout=15.0):
        """Send a line, return the first reply starting with any prefix."""
        self.ser.write((line + '\r\n').encode())
        deadline = time.time() + timeout
        while time.time() < deadline:
            reply = self.ser.readline().decode('ascii', errors='replace').strip()
            if not reply:
                continue
            for p in prefixes:
                if reply.startswith(p):
                    print(f"  [{self.port}] {line} -> {reply[:150]}")
                    if reply.startswith('ERR'):
                        raise RuntimeError(f"{self.port} rejected '{line}': {reply}")
                    return reply
            # Print unhandled lines (could be PKT, CONFIG_START, etc.)
            # print(f"  [{self.port}] (unhandled) {reply[:120]}")
        raise RuntimeError(f"{self.port}: timeout waiting for reply to '{line}'")

    def cmd(self, line, expect_ok=True, timeout=30.0):
        return self.query(line, prefixes=('OK', 'ERR'), timeout=timeout)

    def stat(self):
        return self.query('STAT?', prefixes=('STAT', 'ERR', 'OK'))

    def id(self):
        return self.query('ID?', prefixes=('ID', 'ERR'))

    def close(self):
        self.ser.close()


def parse_stat(reply):
    """Parse STAT line into dict."""
    fields = {}
    for tok in reply.split():
        if '=' in tok:
            k, v = tok.split('=', 1)
            fields[k] = v
    return fields


def parse_pkt(line):
    """Parse a PKT CSV line into a dict matching PKT_FIELDS."""
    parts = line.strip().split(',')
    if len(parts) < 2:
        return None
    d = {}
    for i, field in enumerate(PKT_FIELDS):
        if i < len(parts):
            d[field] = parts[i]
        else:
            d[field] = ''
    return d


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    
    print("Opening serial ports...")
    tx = BoardSerial(TX_PORT)
    rx = BoardSerial(RX_PORT)
    
    # Verify firmware
    tx_id = tx.id()
    rx_id = rx.id()
    print(f"TX ID: {tx_id}")
    print(f"RX ID: {rx_id}")
    
    # Setup RX: ROLE RX, PRBS ON
    print("\nSetting up RX: ROLE RX, PRBS ON...")
    rx.cmd('ROLE RX')
    rx.cmd('PRBS ON')
    
    # Setup TX: ROLE TX
    print("Setting up TX: ROLE TX...")
    tx.cmd('ROLE TX')
    
    # Set frequency on both boards (868 MHz)
    tx.cmd('FREQ 868000000')
    rx.cmd('FREQ 868000000')
    
    all_pkt_rows = []
    stats_lines = []
    summary_data = []
    
    for cfg_id, sf, bw, power in CONFIGS:
        print(f"\n{'='*60}")
        print(f"Config {cfg_id}: SF{sf} BW={bw}kHz POWER={power}dBm")
        print(f"{'='*60}")
        
        # Set CONFIG on both boards
        tx.cmd(f'CONFIG {cfg_id} 0')
        rx.cmd(f'CONFIG {cfg_id} 0')
        
        # Set modulation: MOD lora <sf> <bw_khz>
        tx.cmd(f'MOD lora {sf} {bw}')
        rx.cmd(f'MOD lora {sf} {bw}')
        
        # Set TX power: PA <dbm>
        tx.cmd(f'PA {power}')
        # RX doesn't need PA but set for consistency
        rx.cmd(f'PA {power}')
        
        # Arm TX
        tx.cmd('ARM TX')
        time.sleep(0.5)
        
        # Clear RX buffer before burst
        rx.ser.timeout = 0.1
        rx.ser.read(65536)
        rx.ser.timeout = 5.0
        
        # Start burst
        start_cmd = f'START N={N_PKTS} LEN={LEN} GAP={GAP}'
        print(f"  TX: {start_cmd}")
        tx.write_cmd(start_cmd)
        
        # Collect PKT lines from RX and poll TX STAT
        pkts = []
        start_time = time.time()
        tx_done = False
        rx.ser.timeout = 0.3  # short timeout for polling RX
        
        while time.time() - start_time < TIMEOUT_S:
            # Read RX for PKT lines
            rx_data = rx.ser.read(8192)
            if rx_data:
                text = rx_data.decode('ascii', errors='replace')
                for line in text.split('\n'):
                    line = line.strip()
                    if line.startswith('PKT,'):
                        row = parse_pkt(line)
                        if row:
                            pkts.append(row)
                            all_pkt_rows.append(row)
            
            # Check TX STAT every ~2s (but not too aggressively)
            if not tx_done and (time.time() - start_time) > 2.0:
                tx.ser.timeout = 0.5
                tx.write_cmd('STAT?')
                time.sleep(0.3)
                tx_resp = tx.ser.readline().decode('ascii', errors='replace').strip()
                tx.ser.timeout = 5.0
                if tx_resp.startswith('STAT'):
                    stat = parse_stat(tx_resp)
                    sent = int(stat.get('sent', 0))
                    if sent >= N_PKTS:
                        tx_done = True
                        print(f"  TX burst complete: sent={sent}")
        
        # Final drain of RX
        time.sleep(1.0)
        rx.ser.timeout = 0.3
        for _ in range(20):  # drain for up to 6s
            rx_data = rx.ser.read(8192)
            if not rx_data:
                break
            text = rx_data.decode('ascii', errors='replace')
            for line in text.split('\n'):
                line = line.strip()
                if line.startswith('PKT,'):
                    row = parse_pkt(line)
                    if row:
                        pkts.append(row)
                        all_pkt_rows.append(row)
        rx.ser.timeout = 5.0
        
        # Query STAT? on both boards
        tx_stat_raw = tx.stat()
        rx_stat_raw = rx.stat()
        
        tx_stat = parse_stat(tx_stat_raw)
        rx_stat = parse_stat(rx_stat_raw)
        
        sent = int(tx_stat.get('sent', 0))
        sent_ok = int(tx_stat.get('sent_ok', 0))
        rx_count = int(rx_stat.get('rx', 0))
        crc_err = int(rx_stat.get('crc_err', 0))
        
        received = len(pkts)
        per = ((sent - received) / sent * 100) if sent > 0 else 0
        
        # Parse PKT rows for RSSI, SNR, bit_err, bytes_bad
        rssi_vals = []
        snr_vals = []
        bit_err_total = 0
        bytes_bad_total = 0
        
        for row in pkts:
            try: rssi_vals.append(float(row.get('rssi_dbm', 0)))
            except: pass
            try: snr_vals.append(float(row.get('snr_db', 0)))
            except: pass
            try: bit_err_total += int(row.get('bit_err', 0))
            except: pass
            try: bytes_bad_total += int(row.get('bytes_bad', 0))
            except: pass
        
        rssi_min = min(rssi_vals) if rssi_vals else 0
        rssi_max = max(rssi_vals) if rssi_vals else 0
        rssi_avg = sum(rssi_vals)/len(rssi_vals) if rssi_vals else 0
        snr_min = min(snr_vals) if snr_vals else 0
        snr_max = max(snr_vals) if snr_vals else 0
        snr_avg = sum(snr_vals)/len(snr_vals) if snr_vals else 0
        
        print(f"  Sent={sent} sent_ok={sent_ok} Received(PKT)={received} RX_stat={rx_count} CRC_err={crc_err}")
        print(f"  PER={per:.1f}%")
        print(f"  RSSI: min={rssi_min:.1f} max={rssi_max:.1f} avg={rssi_avg:.1f} dBm")
        print(f"  SNR: min={snr_min:.1f} max={snr_max:.1f} avg={snr_avg:.1f} dB")
        print(f"  bit_err={bit_err_total} bytes_bad={bytes_bad_total}")
        
        stats_lines.append(f"=== Config {cfg_id}: SF{sf} BW={bw}kHz POWER={power}dBm ===")
        stats_lines.append(f"TX STAT: {tx_stat_raw}")
        stats_lines.append(f"RX STAT: {rx_stat_raw}")
        stats_lines.append(f"Packets sent: {sent} (sent_ok={sent_ok})")
        stats_lines.append(f"Packets received (PKT lines): {received}")
        stats_lines.append(f"RX stat rx count: {rx_count}")
        stats_lines.append(f"CRC errors: {crc_err}")
        stats_lines.append(f"PER: {per:.2f}%")
        stats_lines.append(f"RSSI: min={rssi_min:.1f} max={rssi_max:.1f} avg={rssi_avg:.1f} dBm")
        stats_lines.append(f"SNR: min={snr_min:.1f} max={snr_max:.1f} avg={snr_avg:.1f} dB")
        stats_lines.append(f"bit_err_total: {bit_err_total}")
        stats_lines.append(f"bytes_bad_total: {bytes_bad_total}")
        stats_lines.append("")
        
        summary_data.append({
            'config': cfg_id, 'sf': sf, 'bw': bw, 'power': power,
            'sent': sent, 'sent_ok': sent_ok, 'received': received,
            'rx_stat': rx_count, 'crc_err': crc_err, 'per': per,
            'rssi_min': rssi_min, 'rssi_max': rssi_max, 'rssi_avg': rssi_avg,
            'snr_min': snr_min, 'snr_max': snr_max, 'snr_avg': snr_avg,
            'bit_err': bit_err_total, 'bytes_bad': bytes_bad_total,
        })
        
        # 2s delay between configs
        if cfg_id < CONFIGS[-1][0]:
            print("  Waiting 2s for radio to settle...")
            time.sleep(2)
    
    # Save CSV — all PKT lines
    csv_path = os.path.join(DATA_DIR, 'e80_sweep_20260820.csv')
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=PKT_FIELDS, extrasaction='ignore')
        writer.writeheader()
        for row in all_pkt_rows:
            writer.writerow(row)
    print(f"\nCSV saved: {csv_path} ({len(all_pkt_rows)} rows, {len(PKT_FIELDS)} fields)")
    
    # Save stats
    stats_path = os.path.join(DATA_DIR, 'e80_sweep_20260820_stats.txt')
    with open(stats_path, 'w') as f:
        f.write('\n'.join(stats_lines))
    print(f"Stats saved: {stats_path}")
    
    # Save summary markdown
    summary_path = os.path.join(DATA_DIR, 'e80_sweep_20260820_summary.md')
    with open(summary_path, 'w') as f:
        f.write("# E80 Full LoRa Sweep — 2026-08-20\n\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"Firmware: e79f0c0 (SNR pass-through on CRC-failed packets)\n")
        f.write(f"Boards: TX={TX_PORT}, RX={RX_PORT}\n")
        f.write(f"Modulation: LoRa, 868 MHz, CR=4/5\n")
        f.write(f"Payload: {LEN} bytes, {N_PKTS} packets per config, GAP={GAP}us\n")
        f.write(f"Total configs: {len(CONFIGS)}\n")
        f.write(f"Total packets intended: {len(CONFIGS) * N_PKTS}\n\n")
        f.write("## Results per Config\n\n")
        f.write("| Config | SF | BW(kHz) | Power | Sent | Sent_OK | Rcvd(PKT) | RX_stat | CRC_err | PER(%) | RSSI min | RSSI max | RSSI avg | SNR min | SNR max | SNR avg | bit_err | bytes_bad |\n")
        f.write("|--------|----|---------|-------|------|---------|-----------|---------|---------|--------|----------|----------|----------|---------|---------|---------|---------|-----------|\n")
        for s in summary_data:
            f.write(f"| {s['config']} | {s['sf']} | {s['bw']} | {s['power']} | {s['sent']} | {s['sent_ok']} | {s['received']} | {s['rx_stat']} | {s['crc_err']} | {s['per']:.1f} | {s['rssi_min']:.1f} | {s['rssi_max']:.1f} | {s['rssi_avg']:.1f} | {s['snr_min']:.1f} | {s['snr_max']:.1f} | {s['snr_avg']:.1f} | {s['bit_err']} | {s['bytes_bad']} |\n")
        f.write("\n## Summary\n\n")
        total_sent = sum(s['sent'] for s in summary_data)
        total_sent_ok = sum(s['sent_ok'] for s in summary_data)
        total_rcvd = sum(s['received'] for s in summary_data)
        total_per = (total_sent - total_rcvd) / total_sent * 100 if total_sent > 0 else 0
        f.write(f"- Total packets sent: {total_sent}\n")
        f.write(f"- Total packets sent_ok: {total_sent_ok}\n")
        f.write(f"- Total packets received (PKT lines): {total_rcvd}\n")
        f.write(f"- Overall PER: {total_per:.2f}%\n")
        f.write(f"- Total bit_err: {sum(s['bit_err'] for s in summary_data)}\n")
        f.write(f"- Total bytes_bad: {sum(s['bytes_bad'] for s in summary_data)}\n")
        f.write(f"- Total CRC errors: {sum(s['crc_err'] for s in summary_data)}\n")
    print(f"Summary saved: {summary_path}")
    
    # Close serial ports
    tx.close()
    rx.close()
    
    print(f"\nDone! {len(all_pkt_rows)} PKT lines captured across {len(CONFIGS)} configs.")

if __name__ == '__main__':
    main()