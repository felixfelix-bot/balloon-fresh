#!/usr/bin/env python3
"""P1B comprehensive A/B test: RadioLib vs Raw SPI, DELAY sweep, bitrate sweep.
Auto-detects port assignment. Keeps ports open for entire test suite.
Usage: python3 -u tests/p1b_ab_test.py
"""
import serial, time, re, json, os, sys

# Auto-detect ESP32 ports (skip RP2040 at ACM1)
ESP_PORTS = sorted([f"/dev/ttyACM{i}" for i in range(2, 10) if os.path.exists(f"/dev/ttyACM{i}")])
if len(ESP_PORTS) < 2:
    print("ERROR: Need 2 ESP32 serial ports. Found:", ESP_PORTS)
    sys.exit(1)

PYP = "/home/c03rad0r/.espressif/python_env/idf5.4_py3.13_env/bin/python3"
RESULTS_DIR = "tests/results/phase1b"
os.makedirs(RESULTS_DIR, exist_ok=True)

def open_port(port):
    s = serial.Serial()
    s.port = port; s.baudrate = 115200; s.dtr = False; s.rts = False; s.timeout = 0.5
    s.open()
    return s

def cmd(s, c, w=0.3):
    s.write((c + "\n").encode()); time.sleep(w)
    r = b""
    for _ in range(10):
        d = s.read(4096)
        if d: r += d
        else: break
    return r.decode(errors='replace')

def drain(s, t):
    s.timeout = 0.3; end = time.time() + t; chunks = []
    while time.time() < end:
        d = s.read(4096)
        if d: chunks.append(d)
    return b"".join(chunks).decode(errors='replace')

def parse(text):
    r = {}
    for key in ['received','crc_errors','lost','total_sent_by_tx','elapsed_ms']:
        m = re.search(key + r',(\d+)', text)
        r[key] = int(m.group(1)) if m else 0
    m = re.search(r'throughput_kbps,([\d.]+)', text)
    r['throughput'] = float(m.group(1)) if m else 0
    m = re.search(r'per_pct,([\d.]+)', text)
    r['per'] = float(m.group(1)) if m else 100
    m = re.search(r'avg_rssi,([\d.-]+)', text)
    r['rssi'] = float(m.group(1)) if m else 0
    m = re.search(r'time_per_pkt_ms,([\d.]+)', text)
    r['ms_per_pkt'] = float(m.group(1)) if m else 0
    return r

def run_single_test(sa, sb, mode_cmd, trigger_cmd, br, size, delay, count=100):
    """Run one test. sa=TX port, sb=RX port. Both already open."""
    # Configure RX (must set PWR 12 — default 22 is invalid on 2.4GHz)
    for c in ['ROLE RX', mode_cmd, 'FREQ 2450', f'BR {br}', 'PWR 12', f'SIZE {size}', 'RUN']:
        cmd(sb, c, 0.2)
    # Configure TX
    for c in ['ROLE TX', mode_cmd, 'FREQ 2450', f'BR {br}', 'PWR 12',
              f'SIZE {size}', f'COUNT {count}', f'DELAY {delay}']:
        cmd(sa, c, 0.2)
    # Trigger
    cmd(sa, trigger_cmd, 0.2)
    # Wait for results
    wait = max(5 + delay * count / 1000 + 3, 10)
    rx_data = drain(sb, wait)
    return parse(rx_data)

# ============================================================
print("=" * 70, flush=True)
print("P1B COMPREHENSIVE A/B TEST", flush=True)
print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}", flush=True)
print(f"Ports: {ESP_PORTS}", flush=True)
print("=" * 70, flush=True)

# === AUTO-DETECT PORT ASSIGNMENT ===
print("\n--- Detecting TX/RX assignment ---", flush=True)
port_a, port_b = ESP_PORTS[0], ESP_PORTS[1]

# Try A=TX, B=RX first
sa = open_port(port_a); sb = open_port(port_b)
time.sleep(5)  # Wait for boot
sa.read(65536); sb.read(65536)

print(f"  Trying {port_a}=TX, {port_b}=RX...", flush=True)
r = run_single_test(sa, sb, 'MODE FLRC', 'RUN', 2600, 64, 10, 20)
if r['received'] > 0:
    print(f"  ✅ Works! {r['received']}/{r['total_sent_by_tx']} pkts received", flush=True)
    tx_port, rx_port = port_a, port_b
else:
    print(f"  ❌ No packets. Trying reversed...", flush=True)
    sa.close(); sb.close()
    time.sleep(1)
    sa = open_port(port_b); sb = open_port(port_a)
    time.sleep(5)
    sa.read(65536); sb.read(65536)
    r = run_single_test(sa, sb, 'MODE FLRC', 'RUN', 2600, 64, 10, 20)
    if r['received'] > 0:
        print(f"  ✅ Reversed works! {r['received']}/{r['total_sent_by_tx']} pkts", flush=True)
        tx_port, rx_port = port_b, port_a
    else:
        print(f"  ❌ Neither direction works. Check hardware.", flush=True)
        sa.close(); sb.close()
        sys.exit(1)

print(f"  Assignment: TX={tx_port}, RX={rx_port}", flush=True)

# ============================================================
# GROUP 1: RadioLib DELAY sweep (baseline)
# ============================================================
print("\n--- GROUP 1: RadioLib DELAY sweep (FLRC 2600, 255B) ---", flush=True)
group1 = []
for delay in [10, 5, 2, 1, 0]:
    r = run_single_test(sa, sb, 'MODE FLRC', 'RUN', 2600, 255, delay, 100)
    r['test'] = f'RadioLib DELAY={delay}'
    r['group'] = 'radiolib_delay'
    r['delay'] = delay
    r['mode'] = 'RadioLib'
    group1.append(r)
    status = '✅' if r['received'] > 0 else '❌'
    print(f"  {status} DELAY={delay}ms: {r['received']}/{r['total_sent_by_tx']} pkts, "
          f"{r['throughput']:.1f} kbps, PER={r['per']:.1f}%, {r['ms_per_pkt']:.2f}ms/pkt", flush=True)
    time.sleep(1)

# ============================================================
# GROUP 2: Raw SPI DELAY sweep (bypass)
# ============================================================
print("\n--- GROUP 2: Raw SPI DELAY sweep (FLRC 2600, 255B) ---", flush=True)
group2 = []
for delay in [10, 5, 2, 1, 0]:
    r = run_single_test(sa, sb, 'MODE FLRC', 'RAWTX', 2600, 255, delay, 100)
    r['test'] = f'RawSPI DELAY={delay}'
    r['group'] = 'rawspi_delay'
    r['delay'] = delay
    r['mode'] = 'RawSPI'
    group2.append(r)
    status = '✅' if r['received'] > 0 else '❌'
    print(f"  {status} DELAY={delay}ms: {r['received']}/{r['total_sent_by_tx']} pkts, "
          f"{r['throughput']:.1f} kbps, PER={r['per']:.1f}%, {r['ms_per_pkt']:.2f}ms/pkt", flush=True)
    time.sleep(1)

# ============================================================
# GROUP 3: RadioLib bitrate sweep (DELAY=0, 255B)
# ============================================================
print("\n--- GROUP 3: RadioLib bitrate sweep (DELAY 0, 255B) ---", flush=True)
group3 = []
for br in [2600, 1300, 650, 325]:
    r = run_single_test(sa, sb, 'MODE FLRC', 'RUN', br, 255, 0, 100)
    r['test'] = f'RadioLib BR={br}'
    r['group'] = 'radiolib_bitrate'
    r['br'] = br
    r['mode'] = 'RadioLib'
    group3.append(r)
    status = '✅' if r['received'] > 0 else '❌'
    print(f"  {status} BR={br}: {r['received']}/{r['total_sent_by_tx']} pkts, "
          f"{r['throughput']:.1f} kbps, PER={r['per']:.1f}%", flush=True)
    time.sleep(1)

# ============================================================
# GROUP 4: Raw SPI bitrate sweep (DELAY=0, 255B)
# ============================================================
print("\n--- GROUP 4: Raw SPI bitrate sweep (DELAY 0, 255B) ---", flush=True)
group4 = []
for br in [2600, 1300, 650, 325]:
    r = run_single_test(sa, sb, 'MODE FLRC', 'RAWTX', br, 255, 0, 100)
    r['test'] = f'RawSPI BR={br}'
    r['group'] = 'rawspi_bitrate'
    r['br'] = br
    r['mode'] = 'RawSPI'
    group4.append(r)
    status = '✅' if r['received'] > 0 else '❌'
    print(f"  {status} BR={br}: {r['received']}/{r['total_sent_by_tx']} pkts, "
          f"{r['throughput']:.1f} kbps, PER={r['per']:.1f}%", flush=True)
    time.sleep(1)

# ============================================================
# GROUP 5: Payload size sweep (RadioLib vs RawSPI, DELAY=0, BR=2600)
# ============================================================
print("\n--- GROUP 5: Payload size sweep (FLRC 2600, DELAY 0) ---", flush=True)
group5 = []
for size in [20, 64, 128, 255]:
    for mode_cmd, trigger, label in [('MODE FLRC', 'RUN', 'RadioLib'), ('MODE FLRC', 'RAWTX', 'RawSPI')]:
        r = run_single_test(sa, sb, mode_cmd, trigger, 2600, size, 0, 100)
        r['test'] = f'{label} SIZE={size}'
        r['group'] = 'size_sweep'
        r['size'] = size
        r['mode'] = label
        group5.append(r)
        status = '✅' if r['received'] > 0 else '❌'
        print(f"  {status} {label} SIZE={size}: {r['received']}/{r['total_sent_by_tx']} pkts, "
              f"{r['throughput']:.1f} kbps", flush=True)
        time.sleep(1)

sa.close(); sb.close()

# ============================================================
# SUMMARY
# ============================================================
all_results = group1 + group2 + group3 + group4 + group5

print("\n" + "=" * 70, flush=True)
print("A/B COMPARISON SUMMARY", flush=True)
print("=" * 70, flush=True)

# Delay comparison
print("\nDELAY SWEEP (FLRC 2600, 255B):", flush=True)
print(f"{'DELAY':<8} {'RadioLib kbps':<15} {'RawSPI kbps':<15} {'Speedup'}", flush=True)
print("-" * 50, flush=True)
for i in range(len(group1)):
    rl = group1[i]
    rs = group2[i] if i < len(group2) else {}
    rl_kbps = rl.get('throughput', 0)
    rs_kbps = rs.get('throughput', 0)
    speedup = f"{rs_kbps/rl_kbps:.1f}x" if rl_kbps > 0 else "N/A"
    print(f"{rl['delay']}ms     {rl_kbps:<15.1f} {rs_kbps:<15.1f} {speedup}", flush=True)

# Bitrate comparison
print("\nBITRATE SWEEP (DELAY 0, 255B):", flush=True)
print(f"{'BR':<8} {'RadioLib kbps':<15} {'RawSPI kbps':<15} {'Speedup'}", flush=True)
print("-" * 50, flush=True)
for i in range(len(group3)):
    rl = group3[i]
    rs = group4[i] if i < len(group4) else {}
    rl_kbps = rl.get('throughput', 0)
    rs_kbps = rs.get('throughput', 0)
    speedup = f"{rs_kbps/rl_kbps:.1f}x" if rl_kbps > 0 else "N/A"
    print(f"{rl['br']:<8} {rl_kbps:<15.1f} {rs_kbps:<15.1f} {speedup}", flush=True)

# Best result
best = max(all_results, key=lambda x: x.get('throughput', 0))
print(f"\n🏆 BEST: {best['test']} = {best.get('throughput', 0):.1f} kbps "
      f"({best.get('received',0)}/{best.get('total_sent_by_tx',0)} pkts, "
      f"PER={best.get('per',0):.1f}%)", flush=True)

# Save
with open(f"{RESULTS_DIR}/ab_comparison.json", "w") as f:
    json.dump(all_results, f, indent=2, default=str)
print(f"\nResults saved to {RESULTS_DIR}/ab_comparison.json", flush=True)
print("=== DONE ===", flush=True)
