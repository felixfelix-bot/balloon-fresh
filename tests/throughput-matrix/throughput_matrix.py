import serial, time, subprocess

openocd = '/home/c03rad0r/.espressif/tools/openocd-esp32/v0.12.0-esp32-20241016/openocd-esp32/bin/openocd'

# Port mapping: A=ttyUSB3, B=ttyUSB4
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

def setup_tx(rate, payload):
    send(a, 'MOD flrc {} 10'.format(rate))
    send(a, 'FREQ 869850000')
    send(a, 'POWER MODE OUTDOOR 2026')
    send(a, 'PA 22')
    send(a, 'ROLE TX')
    send(a, 'ARM TX')

def setup_rx(rate, payload):
    send(b, 'MOD flrc {} 10'.format(rate))
    send(b, 'FREQ 869850000')
    send(b, 'POWER MODE OUTDOOR 2026')
    send(b, 'ROLE RX')

def run_test(rate, payload, n=200, gap=10000):
    print(f'\n=== FLRC {rate} kbps, {payload}B, N={n}, GAP={gap}us ===')
    reset_both()
    setup_tx(rate, payload)
    setup_rx(rate, payload)
    
    send(b, f'START N={n} LEN={payload} GAP={gap}', 1)
    send(a, f'START N={n} LEN={payload} GAP={gap}', 1)
    
    # Wait for completion (N*GAP/1e6 + N*payload*8/rate + margin)
    wait_time = max(15, int(n * gap / 1e6 + n * payload * 8 / (rate * 1000) + 10))
    print(f'Waiting {wait_time}s...')
    time.sleep(wait_time)
    
    tx_stat = send(a, 'STAT?', 3)
    rx_stat = send(b, 'STAT?', 3)
    
    print(f'TX: {tx_stat}')
    print(f'RX: {rx_stat}')
    
    # Parse RX stats
    if 'rx=' in rx_stat:
        for part in rx_stat.split():
            if 'rx=' in part: rx_count = int(part.split('=')[1])
            if 'crc_err=' in part: crc = int(part.split('=')[1])
            if 'kbps=' in part: kbps = part.split('=')[1]
            if 'rssi_avg=' in part: rssi = part.split('=')[1]
        print(f'  -> RX={rx_count}/{n} CRC={crc} kbps={kbps} rssi={rssi}')
    
    return tx_stat, rx_stat

# Test matrix: rates x payloads
results = []
for rate in [260, 650, 1300, 2600]:
    for payload in [64, 128, 255]:
        tx, rx = run_test(rate, payload)
        results.append((rate, payload, tx, rx))
        time.sleep(2)

print('\n\n=== SUMMARY ===')
print(f'{"Rate":>6} {"Len":>4} {"RX/200":>7} {"CRC":>4} {"kbps":>6} {"RSSI":>6}')
for rate, payload, tx, rx in results:
    rx_count = 'ERR'
    crc = '?'
    kbps = '?'
    rssi = '?'
    for part in rx.split():
        if 'rx=' in part: rx_count = part.split('=')[1]
        if 'crc_err=' in part: crc = part.split('=')[1]
        if 'kbps=' in part: kbps = part.split('=')[1]
        if 'rssi_avg_dbm=' in part: rssi = part.split('=')[1]
    print(f'{rate:>6} {payload:>4} {rx_count:>7} {crc:>4} {kbps:>6} {rssi:>6}')

a.close(); b.close()