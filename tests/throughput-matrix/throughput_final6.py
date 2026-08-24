#!/usr/bin/env python3
"""E80 FLRC Final Clean Throughput Test v6
FIXES:
- No ARM RX (doesn't exist). ROLE RX puts board in continuous RX
- GAP= not GAP_US= (firmware expects GAP key)
- ARM TX + START as single serial write
- Test at PA 10 (indoor cap, no outdoor unlock needed)
- 3s wait (not 5s or 20s) — just enough for 200 pkts at 10ms gap
- Only 260/650/1300 kbps (skip 2600 — marginal)
"""
import serial, time, sys, re

BAUD = 115200
N_PKTS = 200
GAP_US = 10000
FREQ = 869850000
PA_DBM = 10  # Indoor cap, no unlock needed

TESTS = [
    (260, 64), (260, 128), (260, 255),
    (650, 64), (650, 128), (650, 255),
    (1300, 64), (1300, 128), (1300, 255),
]

def send_cmd(ser, cmd, wait=0.5):
    ser.write((cmd + '\r').encode())
    time.sleep(wait)
    return ser.read(8192).decode('ascii', errors='replace').strip()

def run_test(rate_kbps, payload, tx_port, rx_port):
    print(f"\n=== FLRC {rate_kbps} kbps, {payload}B ===")
    
    tx = serial.Serial(tx_port, BAUD, timeout=1)
    rx = serial.Serial(rx_port, BAUD, timeout=1)
    time.sleep(0.2)
    tx.read(4096); rx.read(4096)
    
    # Setup RX first (continuous mode, no ARM needed)
    r = send_cmd(rx, f'MOD flrc {rate_kbps} 10', 0.3)
    if 'ERR' in r:
        print(f"  RX MOD: {r}"); tx.close(); rx.close(); return None
    
    send_cmd(rx, f'FREQ {FREQ}', 0.2)
    r = send_cmd(rx, 'ROLE RX', 0.3)
    print(f"  RX ROLE: {r[:60]}")
    
    # Setup TX
    r = send_cmd(tx, f'MOD flrc {rate_kbps} 10', 0.3)
    if 'ERR' in r:
        print(f"  TX MOD: {r}"); tx.close(); rx.close(); return None
    
    send_cmd(tx, f'FREQ {FREQ}', 0.2)
    send_cmd(tx, f'PA {PA_DBM}', 0.2)
    r = send_cmd(tx, 'ROLE TX', 0.3)
    print(f"  TX ROLE: {r[:60]}")
    
    # ARM TX + START as single write — GAP= not GAP_US=
    tx.write(f'ARM TX\rSTART N={N_PKTS} LEN={payload} GAP={GAP_US}\r'.encode())
    time.sleep(0.5)
    arm_resp = tx.read(8192).decode('ascii', errors='replace').strip()
    print(f"  TX ARM+START: {arm_resp[:80]}")
    
    # Wait for completion (200 pkts * 10ms = 2s + overhead)
    time.sleep(4)
    
    tx_stat = send_cmd(tx, 'STAT?', 0.5)
    rx_stat = send_cmd(rx, 'STAT?', 0.5)
    print(f"  TX: {tx_stat[:120]}")
    print(f"  RX: {rx_stat[:120]}")
    
    def p(stat, key):
        m = re.search(rf'{key}=([^\s]+)', stat)
        return m.group(1) if m else '?'
    
    result = {
        'rate': rate_kbps, 'len': payload,
        'tx_sent': p(tx_stat, 'sent'),
        'rx_got': p(rx_stat, 'rx'),
        'crc_err': p(rx_stat, 'crc_err'),
        'tx_kbps': p(tx_stat, 'kbps'),
        'rssi': p(rx_stat, 'rssi_avg_dbm'),
        'tx_elapsed': p(tx_stat, 'elapsed_s'),
    }
    
    tx.close(); rx.close()
    time.sleep(1)
    return result

def main():
    print(f"E80 FLRC Final Throughput Test v6")
    print(f"N={N_PKTS}, GAP={GAP_US}us, freq={FREQ}, PA={PA_DBM}dBm (indoor)")
    
    # Auto-detect: ID? both ports — need extra settle time after SWD reset
    ports = {}
    for p in ['/dev/ttyUSB3', '/dev/ttyUSB4']:
        try:
            s = serial.Serial(p, BAUD, timeout=2)
            time.sleep(0.5)
            s.read(4096)  # drain any pending
            s.write(b'ID?\r')
            time.sleep(1.0)
            r = s.read(4096).decode('ascii', errors='replace')
            s.close()
            if 'E80BENCH' in r:
                ports[p] = True
            else:
                print(f"  {p}: no response (got: {r[:40]})")
        except Exception as e:
            print(f"  {p}: exception {e}")
    
    if len(ports) < 2:
        print(f"ERROR: Only {len(ports)} boards found. Need 2.")
        sys.exit(1)
    
    port_list = list(ports.keys())
    tx_port, rx_port = port_list[0], port_list[1]
    print(f"TX: {tx_port}, RX: {rx_port}")
    
    results = []
    for rate, payload in TESTS:
        r = run_test(rate, payload, tx_port, rx_port)
        if r:
            results.append(r)
    
    print(f"\n=== FINAL SUMMARY ===")
    print(f"{'Rate':>6} {'Len':>4} {'TXsent':>7} {'RXgot':>7} {'CRC':>5} {'TXkbps':>7} {'RSSI':>7} {'el_s':>5}")
    for r in results:
        print(f"{r['rate']:>6} {r['len']:>4} {r['tx_sent']:>7} {r['rx_got']:>7} {r['crc_err']:>5} {r['tx_kbps']:>7} {r['rssi']:>7} {r['tx_elapsed']:>5}")

if __name__ == '__main__':
    main()