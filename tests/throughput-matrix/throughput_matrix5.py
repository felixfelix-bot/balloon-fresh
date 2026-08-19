import serial, time, subprocess

openocd = '/home/c03rad0r/.espressif/tools/openocd-esp32/v0.12.0-esp32-20241016/openocd-esp32/bin/openocd'

a = serial.Serial('/dev/ttyUSB3', 115200, timeout=0.05)
b = serial.Serial('/dev/ttyUSB4', 115200, timeout=0.05)

def send(s, cmd, wait=0.5):
    s.read(65536)
    time.sleep(0.05)
    s.write(cmd.encode() + b'\r')
    time.sleep(wait)
    r = s.read(65536)
    return r.decode(errors='replace').strip()

def reset_both():
    subprocess.run([openocd, '-f', 'interface/cmsis-dap.cfg', '-c', 'adapter serial 148757200D2D1425',
        '-f', 'target/stm32f1x.cfg', '-c', 'adapter speed 1000', '-c', 'init; reset; exit'],
        capture_output=True, timeout=10)
    subprocess.run([openocd, '-f', 'interface/cmsis-dap.cfg', '-c', 'adapter serial 203584200D2D0D42',
        '-f', 'target/stm32f1x.cfg', '-c', 'adapter speed 1000', '-c', 'init; reset; exit'],
        capture_output=True, timeout=10)
    time.sleep(3)
    a.read(65536); b.read(65536)

def run_one(rate, payload, n=200, gap=10000):
    print(f'\n=== FLRC {rate} kbps, {payload}B ===', flush=True)
    reset_both()
    
    ida = send(a, 'ID?', 1)
    idb = send(b, 'ID?', 1)
    if 'E80BENCH' not in ida or 'E80BENCH' not in idb:
        print(f'  Retry...', flush=True)
        reset_both()
        ida = send(a, 'ID?', 1)
        idb = send(b, 'ID?', 1)
        if 'E80BENCH' not in ida or 'E80BENCH' not in idb:
            print('  FAILED', flush=True)
            return None, None
    
    # RX setup (no IWDG)
    send(b, 'MOD flrc {} 10'.format(rate), 0.5)
    send(b, 'FREQ 869850000', 0.5)
    send(b, 'POWER MODE OUTDOOR 2026', 0.5)
    send(b, 'ROLE RX', 0.5)
    
    # TX setup — everything EXCEPT ARM TX
    send(a, 'MOD flrc {} 10'.format(rate), 0.5)
    send(a, 'FREQ 869850000', 0.5)
    send(a, 'POWER MODE OUTDOOR 2026', 0.5)
    send(a, 'PA 22', 0.5)
    send(a, 'ROLE TX', 0.5)
    
    # Start RX first
    rxs = send(b, 'START N={} LEN={} GAP={}'.format(n, payload, gap), 0.5)
    
    # CRITICAL: Send ARM TX + START as ONE serial write (no gap = no IWDG timeout)
    a.read(65536)
    a.write(b'ARM TX\rSTART N=' + str(n).encode() + b' LEN=' + str(payload).encode() + 
            b' GAP=' + str(gap).encode() + b'\r')
    time.sleep(1)
    txs = a.read(65536).decode(errors='replace').strip()
    
    print(f'  RX: {rxs}', flush=True)
    print(f'  TX: {txs}', flush=True)
    
    # Wait for completion
    wait = max(20, int(n * gap / 1e6 + n * payload * 8 / (rate * 1000) + 15))
    print(f'  Wait {wait}s...', flush=True)
    time.sleep(wait)
    
    tx_stat = send(a, 'STAT?', 3)
    rx_stat = send(b, 'STAT?', 3)
    print(f'  TX: {tx_stat}', flush=True)
    print(f'  RX: {rx_stat}', flush=True)
    
    return tx_stat, rx_stat

# Valid FLRC rates: 260, 325, 520, 650, 1040, 1300, 2080, 2600
tests = [
    (260, 64), (260, 128), (260, 255),
    (650, 64), (650, 128), (650, 255),
    (1300, 64), (1300, 128), (1300, 255),
    (2600, 64), (2600, 128), (2600, 255),
]

all_results = []
for rate, payload in tests:
    tx, rx = run_one(rate, payload)
    if tx and rx:
        all_results.append((rate, payload, tx, rx))
    time.sleep(2)

print('\n\n=== FINAL SUMMARY ===', flush=True)
print('{:>6} {:>4} {:>7} {:>7} {:>5} {:>6} {:>8} {:>8}'.format(
    'Rate', 'Len', 'TXsent', 'RXgot', 'CRC', 'kbps', 'RSSIavg', 'elapsed'))
for rate, payload, tx, rx in all_results:
    td = {}
    rd = {}
    for part in tx.split():
        if '=' in part: td[part.split('=')[0]] = part.split('=')[1]
    for part in rx.split():
        if '=' in part: rd[part.split('=')[0]] = part.split('=')[1]
    print('{:>6} {:>4} {:>7} {:>7} {:>5} {:>6} {:>8} {:>8}'.format(
        rate, payload,
        td.get('sent', '?'),
        rd.get('rx', '?'),
        rd.get('crc_err', '?'),
        rd.get('kbps', '?'),
        rd.get('rssi_avg_dbm', '?'),
        rd.get('elapsed_s', '?')))

a.close(); b.close()