#!/usr/bin/env python3
"""Phase 1 interop test runner v2 — robust serial handling, no hangs.

Usage: /home/c03rad0r/.espressif/python_env/idf5.4_py3.13_env/bin/python3 tests/run_interop_v2.py
"""
import serial, time, sys, re, json, os

ESP32_A = "/dev/ttyACM2"
ESP32_B = "/dev/ttyACM3"
RP2040  = "/dev/ttyACM1"
BAUD    = 115200
RESULTS_DIR = "tests/results/phase1"
os.makedirs(RESULTS_DIR, exist_ok=True)

def open_port(port):
    """Open serial port without triggering DTR reset."""
    s = serial.Serial()
    s.port = port
    s.baudrate = BAUD
    s.dtr = False
    s.rts = False
    s.timeout = 0.5
    s.open()
    time.sleep(0.3)
    s.read(65536)  # drain any pending
    return s

def send_and_read(s, cmd, wait=0.5):
    """Send command, read response. Never blocks more than wait+1s."""
    s.write((cmd + "\n").encode())
    time.sleep(wait)
    resp = b""
    for _ in range(10):
        d = s.read(4096)
        if d:
            resp += d
        else:
            break
    return resp.decode(errors='replace')

def drain_for(s, duration):
    """Read everything for duration seconds."""
    s.timeout = 0.3
    end = time.time() + duration
    chunks = []
    while time.time() < end:
        d = s.read(4096)
        if d:
            chunks.append(d)
    return b"".join(chunks).decode(errors='replace')

def parse_rx_results(text):
    """Parse RX output for packet count, RSSI, etc."""
    results = {}
    # Look for "RX RESULTS" section
    m = re.search(r'rx=(\d+)', text, re.I)
    if m: results['rx_count'] = int(m.group(1))
    m = re.search(r'tx=(\d+)', text, re.I)
    if m: results['tx_count'] = int(m.group(1))
    m = re.search(r'RSSI[:\s]+(-?\d+)', text)
    if m: results['rssi'] = int(m.group(1))
    m = re.search(r'SNR[:\s]+(-?\d+(?:\.\d+)?)', text)
    if m: results['snr'] = float(m.group(1))
    m = re.search(r'PER[:\s]+(\d+(?:\.\d+)?)', text)
    if m: results['per'] = float(m.group(1))
    # Count individual packet lines (PKT, RX, rcv)
    pkt_lines = len(re.findall(r'PKT|RX_PKT|rcv=|received:', text, re.I))
    if pkt_lines: results['pkt_lines'] = pkt_lines
    return results

def run_test(name, tx_port, rx_port, tx_cmds, rx_cmds, tx_trigger, duration=15):
    """Run a single interop test."""
    print(f"\n{'='*50}")
    print(f"TEST: {name}")
    print(f"{'='*50}")
    
    try:
        s_tx = open_port(tx_port)
        s_rx = open_port(rx_port)
        
        # Configure RX first (start listening before TX)
        for cmd in rx_cmds:
            resp = send_and_read(s_rx, cmd, 0.3)
            if resp.strip():
                print(f"  RX << {resp.strip()[:100]}")
        
        # Configure TX
        for cmd in tx_cmds:
            resp = send_and_read(s_tx, cmd, 0.3)
            if resp.strip():
                print(f"  TX << {resp.strip()[:100]}")
        
        # Trigger TX and capture
        print(f"  Triggering: {tx_trigger}")
        s_tx.write((tx_trigger + "\n").encode())
        
        # Read RX output
        rx_data = drain_for(s_rx, duration)
        tx_data = drain_for(s_tx, 2)
        
        print(f"  TX output ({len(tx_data)} bytes): {tx_data.strip()[:200]}")
        print(f"  RX output ({len(rx_data)} bytes): {rx_data.strip()[:300]}")
        
        parsed = parse_rx_results(rx_data)
        print(f"  Parsed: {parsed}")
        
        s_tx.close()
        s_rx.close()
        
        return {
            'test': name,
            'rx_output_len': len(rx_data),
            'rx_output_sample': rx_data[:500],
            'tx_output_sample': tx_data[:300],
            'parsed': parsed,
            'packets_received': parsed.get('rx_count', parsed.get('pkt_lines', 0)),
            'rssi': parsed.get('rssi'),
        }
    except Exception as e:
        print(f"  ERROR: {e}")
        return {'test': name, 'error': str(e)}

# ============================================================
# PROBE PHASE
# ============================================================
print("=" * 60)
print("PHASE 1 INTEROP TEST RUNNER v2")
print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
print("=" * 60)

print("\n--- PROBING DEVICES ---")
all_ok = True
for port, name in [(ESP32_A, "ESP32-A"), (ESP32_B, "ESP32-B")]:
    try:
        s = open_port(port)
        resp = send_and_read(s, "CONFIG", 0.5)
        if "freq=" in resp or "mode=" in resp:
            print(f"  {name}: ALIVE — {resp.strip()[:120]}")
        else:
            print(f"  {name}: RESPONDING but unexpected — {resp.strip()[:100]}")
        s.close()
    except Exception as e:
        print(f"  {name}: FAILED — {e}")
        all_ok = False

# RP2040
try:
    s = open_port(RP2040)
    # RP2040 may output on boot or need input
    boot = drain_for(s, 2)
    if boot.strip():
        print(f"  RP2040: BOOT OUTPUT — {boot.strip()[:150]}")
    else:
        s.write(b"\n")
        resp = drain_for(s, 2)
        if resp.strip():
            print(f"  RP2040: RESPONDS — {resp.strip()[:150]}")
        else:
            print(f"  RP2040: SILENT (firmware may not use serial)")
    s.close()
except Exception as e:
    print(f"  RP2040: FAILED — {e}")

# ============================================================
# TEST MATRIX
# ============================================================
results = []

# Common configs for FLRC mode at 2.4 GHz
flrc_tx = [
    "ROLE TX", "MODE FLRC", "FREQ 2450", "BR 2600", "PWR 12",
    "SIZE 255", "COUNT 100", "DELAY 10"
]
flrc_rx = [
    "ROLE RX", "MODE FLRC", "FREQ 2450", "BR 2600"
]

# Test 1: ESP32-A TX → ESP32-B RX (FLRC baseline)
results.append(run_test(
    "T1: ESP32-A→ESP32-B FLRC2600 255B",
    ESP32_A, ESP32_B,
    flrc_tx, flrc_rx,
    "RUN", duration=15
))

# Test 6: ESP32-A TX → ESP32-B RX (LoRa mode)
lora_tx = [
    "ROLE TX", "MODE LORA", "FREQ 2450", "SF 7", "BW 500",
    "PWR 12", "SIZE 255", "COUNT 50", "DELAY 100"
]
lora_rx = [
    "ROLE RX", "MODE LORA", "FREQ 2450", "SF 7", "BW 500"
]
results.append(run_test(
    "T6: ESP32-A→ESP32-B LORA SF7 BW500",
    ESP32_A, ESP32_B,
    lora_tx, lora_rx,
    "RUN", duration=20
))

# Test 2: ESP32-A TX → RP2040 RX
# RP2040 is in RX mode by default (raw SPI bypass). Send ESP32 TX.
results.append(run_test(
    "T2: ESP32-A→RP2040 FLRC2600",
    ESP32_A, RP2040,
    flrc_tx, [],
    "RUN", duration=15
))

# Test 3: RP2040 TX → ESP32-B RX
# RP2040 TX command is 'T'
results.append(run_test(
    "T3: RP2040→ESP32-B (RP2040 TX mode)",
    RP2040, ESP32_B,
    [], flrc_rx,
    "T", duration=15
))

# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 60)
print("RESULTS SUMMARY")
print("=" * 60)
print(f"{'Test':<35} {'Pkts RX':<10} {'RSSI':<8} {'Status'}")
print("-" * 65)
for r in results:
    pkts = r.get('packets_received', 0)
    rssi = r.get('rssi', '—')
    status = "PASS" if pkts > 0 else ("ERROR" if 'error' in r else "NO RX")
    print(f"{r['test']:<35} {pkts:<10} {rssi!s:<8} {status}")

# Save results
with open(f"{RESULTS_DIR}/results.json", "w") as f:
    json.dump(results, f, indent=2, default=str)
print(f"\nResults saved to {RESULTS_DIR}/results.json")
