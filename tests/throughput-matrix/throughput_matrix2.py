import serial, time, subprocess

openocd = '/home/c03rad0r/.espressif/tools/openocd-esp32/v0.12.0-esp32-20241016/openocd-esp32/bin/openocd'

a = serial.Serial('/dev/ttyUSB3', 115200, timeout=0.05)
b = serial.Serial('/dev/ttyUSB4', 115200, timeout=0.05)

def send(s, cmd, wait=2):
    s.read(65536)
    time.sleep(0.1)
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

def setup_tx(rate):
    send(a, 'MOD flrc {} 10'.format(rate))
    send(a, 'FREQ 869850000')
    send(a, 'POWER MODE OUTDOOR 2026')
    send(a, 'PA 22')
    send(a, 'ROLE TX')
    send(a, 'ARM TX')

def setup_rx(rate):
    send(b, 'MOD flrc {} 10'.format(rate))
    send(b, 'FREQ 869850000')
    send(b, 'POWER MODE OUTDOOR 2026')
    send(b, 'ROLE RX')

def run_test(rate, payload, n=200, gap=10000):
    print(f'\n=== FLRC {rate} kbps, {payload}B, N={n}, GAP={gap}us ===', flush=True)
    reset_both()
    
    # Verify boards alive
    id_a = send(a, 'ID?', 3)
    id_b = send(b, 'ID?', 3)
    if 'E80BENCH' not in id_a:
        print(f'  Board A not responding: {id_a[:80]}', flush=True)
        return None, None
    if 'E80BENCH' not in id_b:
        print(f'  Board B not responding: {id_b[:80]}', flush=True)
        return None, None
    
    setup_tx(rate)
    setup_rx(rate)
    
    # Start RX first, then TX
    rx_start = send(b, 'START N={} LEN={} GAP={}'.format(n, payload, gap), 1)
    tx_start = send(a, 'START N={} LEN={} GAP={}'.format(n, payload, gap), 1)
    print(f'  RX START: {rx_start}', flush=True)
    print(f'  TX START: {tx_start}', flush=True)
    
    # Wait for completion
    wait_time = max(20, int(n * gap / 1e6 + n * payload * 8 / (rate * 1000) + 15))
    print(f'  Waiting {wait_time}s...', flush=True)
    time.sleep(wait_time)
    
    tx_stat = send(a, 'STAT?', 3)
    rx_stat = send(b, 'STAT?', 3)
    
    print(f'  TX: {tx_stat}', flush=True)
    print(f'  RX: {rx_stat}', flush=True)
    
    return tx_stat, rx_stat

def parse_stat(stat):
    d = {}
    for part in stat.split():
        if '=' in part:
            k, v = part.split('=', 1)
            d[k] = v
    return d

results = []
for rate in [260, 650, 1300, 2600]:
    for payload in [64, 128, 255]:
        tx, rx = run_test(rate, payload)
        if tx and rx:
            results.append((rate, payload, tx, rx))
        time.sleep(2)

print('\n\n=== SUMMARY ===', flush=True)
print('{:>6} {:>4} {:>7} {:>7} {:>6} {:>8} {:>8} {:>8}'.format(
    'Rate', 'Len', 'TX/200', 'RX/200', 'CRC', 'kbps', 'RSSIavg', 'elapsed'))
for rate, payload, tx, rx in results:
    td = parse_stat(tx)
    rd = parse_stat(rx)
    print('{:>6} {:>4} {:>7} {:>7} {:>6} {:>8} {:>8} {:>8}'.format(
        rate, payload,
        td.get('sent', '?'),
        rd.get('rx', '?'),
        rd.get('crc_err', '?'),
        rd.get('kbps', '?'),
        rd.get('rssi_avg_dbm', '?'),
        rd.get('elapsed_s', '?')))

a.close(); b.close()