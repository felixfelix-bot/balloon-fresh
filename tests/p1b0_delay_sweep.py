#!/usr/bin/env python3
"""P1B.0: A/B DELAY sweep — RadioLib baseline at different inter-packet delays.
No firmware change needed. Tests DELAY 0, 1, 5, 10ms to prove the delay is the bottleneck.
Also sweeps FLRC bitrate (2600, 1300, 650) and payload size (64, 128, 255).
"""
import serial, time, re, json, os, sys

A = "/dev/ttyACM4"  # ESP32-A (TX)
B = "/dev/ttyACM5"  # ESP32-B (RX)
RESULTS_DIR = "tests/results/phase1b"
os.makedirs(RESULTS_DIR, exist_ok=True)

def esp(port):
    s = serial.Serial()
    s.port = port; s.baudrate = 115200; s.dtr = False; s.rts = False; s.timeout = 0.5
    s.open(); time.sleep(0.3); s.read(65536)
    return s

def cmd(s, c, w=0.5):
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

def parse_results(text):
    r = {}
    m = re.search(r'received,(\d+)', text); r['received'] = int(m.group(1)) if m else 0
    m = re.search(r'crc_errors,(\d+)', text); r['crc_errors'] = int(m.group(1)) if m else 0
    m = re.search(r'lost,(\d+)', text); r['lost'] = int(m.group(1)) if m else 0
    m = re.search(r'total_sent_by_tx,(\d+)', text); r['sent'] = int(m.group(1)) if m else 0
    m = re.search(r'elapsed_ms,(\d+)', text); r['elapsed_ms'] = int(m.group(1)) if m else 0
    m = re.search(r'throughput_kbps,([\d.]+)', text); r['throughput_kbps'] = float(m.group(1)) if m else 0
    m = re.search(r'per_pct,([\d.]+)', text); r['per_pct'] = float(m.group(1)) if m else 100
    m = re.search(r'ber_pct,([\d.]+)', text); r['ber_pct'] = float(m.group(1)) if m else 0
    m = re.search(r'avg_rssi,([\d.-]+)', text); r['rssi'] = float(m.group(1)) if m else 0
    return r

def run_test(sa, sb, br, size, delay_ms, count=100):
    """Run a single TX→RX test."""
    label = f"FLRC br={br} size={size} delay={delay_ms}ms"
    
    # Configure RX first
    for c in ["ROLE RX", "MODE FLRC", "FREQ 2450", f"BR {br}", f"SIZE {size}", "RUN"]:
        cmd(sb, c, 0.2)
    
    # Configure TX
    for c in ["ROLE TX", "MODE FLRC", "FREQ 2450", f"BR {br}", "PWR 12",
              f"SIZE {size}", f"COUNT {count}", f"DELAY {delay_ms}"]:
        cmd(sa, c, 0.2)
    
    # Fire TX
    cmd(sa, "RUN", 0.2)
    
    # Wait for completion (longer for slow bitrates / large packets)
    wait_time = max(count * (delay_ms + 5) / 1000 + 5, 10)
    rx_data = drain(sb, wait_time)
    
    parsed = parse_results(rx_data)
    parsed['test'] = label
    parsed['br'] = br
    parsed['size'] = size
    parsed['delay_ms'] = delay_ms
    
    status = "PASS" if parsed['received'] > 0 else "FAIL"
    print(f"  {label}: {parsed['received']}/{parsed['sent']} pkts, "
          f"{parsed['throughput_kbps']:.1f} kbps, PER={parsed['per_pct']:.1f}%, "
          f"RSSI={parsed['rssi']:.0f} dBm [{status}]", flush=True)
    
    return parsed

# ============================================================
print("=" * 70, flush=True)
print("P1B.0: A/B DELAY SWEEP — RadioLib Baseline", flush=True)
print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}", flush=True)
print("=" * 70, flush=True)

sa = esp(A); sb = esp(B)
print(f"\nESP32-A: {cmd(sa, 'CONFIG', 0.5).strip()[:80]}", flush=True)
print(f"ESP32-B: {cmd(sb, 'CONFIG', 0.5).strip()[:80]}", flush=True)

all_results = []

# === GROUP 1: DELAY sweep at FLRC 2600, 255B ===
print("\n--- GROUP 1: DELAY sweep (FLRC 2600, 255B, 100pkts) ---", flush=True)
for delay in [0, 1, 2, 5, 10]:
    r = run_test(sa, sb, 2600, 255, delay, 100)
    all_results.append(r)
    time.sleep(1)

# === GROUP 2: Bitrate sweep at DELAY 0, 255B ===
print("\n--- GROUP 2: Bitrate sweep (DELAY 0, 255B, 100pkts) ---", flush=True)
for br in [2600, 2080, 1300, 1040, 650, 325]:
    r = run_test(sa, sb, br, 255, 0, 100)
    all_results.append(r)
    time.sleep(1)

# === GROUP 3: Payload size sweep at FLRC 2600, DELAY 0 ===
print("\n--- GROUP 3: Payload size sweep (FLRC 2600, DELAY 0, 100pkts) ---", flush=True)
for size in [20, 64, 128, 255]:
    r = run_test(sa, sb, 2600, size, 0, 100)
    all_results.append(r)
    time.sleep(1)

sa.close(); sb.close()

# === SUMMARY ===
print("\n" + "=" * 70, flush=True)
print("SUMMARY", flush=True)
print("=" * 70, flush=True)
print(f"{'Test':<45} {'Rx/Tx':<10} {'kbps':<8} {'PER%':<6} {'RSSI'}", flush=True)
print("-" * 75, flush=True)
for r in all_results:
    rxtx = f"{r['received']}/{r['sent']}"
    print(f"{r['test']:<45} {rxtx:<10} {r['throughput_kbps']:<8.1f} {r['per_pct']:<6.1f} {r['rssi']:.0f}", flush=True)

# Find best throughput
best = max(all_results, key=lambda x: x['throughput_kbps'])
print(f"\nBest throughput: {best['throughput_kbps']:.1f} kbps ({best['test']})", flush=True)

# Save
with open(f"{RESULTS_DIR}/p1b0_delay_sweep.json", "w") as f:
    json.dump(all_results, f, indent=2)
print(f"\nResults saved to {RESULTS_DIR}/p1b0_delay_sweep.json", flush=True)
print("=== DONE ===", flush=True)
