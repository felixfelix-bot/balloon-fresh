#!/usr/bin/env python3
"""Sustained throughput test coordinator for LR2021 FLRC + LoRa binary-step sweep.

Sends RUN to RX first (2s head start), then RUN to TX, captures RX output.
Works with ESP32 UART bridges: ACM0→F242D(TX), ACM2→8332(RX).
"""
import serial, time, sys, os

TX_PORT = "/dev/ttyACM0"   # ESP32 bridge → F242D
RX_PORT = "/dev/ttyACM2"   # ESP32 bridge → 8332
BAUD = 115200

def run_test(duration_sec=15, label="FLRC_2600"):
    """Run one sustained throughput test point."""
    print(f"\n{'='*60}")
    print(f"TEST: {label} ({duration_sec}s)")
    print(f"{'='*60}")
    
    # Open both ports
    tx = serial.Serial(TX_PORT, BAUD, timeout=1)
    rx = serial.Serial(RX_PORT, BAUD, timeout=1)
    time.sleep(0.5)
    
    # Flush
    while tx.in_waiting: tx.read(tx.in_waiting)
    while rx.in_waiting: rx.read(rx.in_waiting)
    
    # Arm RX first (2s head start)
    print(f"[{time.strftime('%H:%M:%S')}] Arming RX...")
    rx.write(b"RUN\r\n")
    time.sleep(2)
    
    # Start TX
    print(f"[{time.strftime('%H:%M:%S')}] Starting TX...")
    tx.write(b"RUN\r\n")
    
    # Capture RX output for duration
    print(f"[{time.strftime('%H:%M:%S')}] Capturing {duration_sec}s...")
    start = time.time()
    lines = []
    while time.time() - start < duration_sec:
        if rx.in_waiting:
            data = rx.read(rx.in_waiting).decode('utf-8', errors='replace')
            lines.append(data)
        else:
            time.sleep(0.05)
    
    # Also grab TX output
    tx_lines = []
    while tx.in_waiting:
        tx_lines.append(tx.read(tx.in_waiting).decode('utf-8', errors='replace'))
    
    tx.close()
    rx.close()
    
    # Parse and print results
    rx_text = ''.join(lines)
    tx_text = ''.join(tx_lines)
    
    print(f"\n--- TX Output ---")
    for line in tx_text.split('\n')[:10]:
        print(line.rstrip())
    
    print(f"\n--- RX Output ---")
    for line in rx_text.split('\n')[:50]:
        print(line.rstrip())
    
    # Extract structured results
    results = {'label': label, 'duration': duration_sec}
    for line in rx_text.split('\n'):
        if 'RANGE_RESULT_RX' in line or 'LORA_RX_RESULT' in line:
            print(f"\n*** RESULT: {line.strip()}")
            results['rx_line'] = line.strip()
        if 'SUSTAINED_TX_RESULT' in line or 'LORA_TX_RESULT' in line:
            print(f"*** TX RESULT: {line.strip()}")
            results['tx_line'] = line.strip()
    
    return results

def set_bitrate_both(br):
    """Set bitrate on both TX and RX boards via serial commands."""
    tx = serial.Serial(TX_PORT, BAUD, timeout=1)
    rx = serial.Serial(RX_PORT, BAUD, timeout=1)
    time.sleep(0.3)
    while tx.in_waiting: tx.read(tx.in_waiting)
    while rx.in_waiting: rx.read(rx.in_waiting)
    
    # Stop TX if running
    tx.write(b'STOP\r\n')
    time.sleep(0.5)
    while tx.in_waiting: tx.read(tx.in_waiting)
    
    # Set bitrate on both
    tx.write(f'BITRATE {br}\r\n'.encode())
    rx.write(f'BITRATE {br}\r\n'.encode())
    time.sleep(0.5)
    
    # Set pktSize to 127 on RX (in case it reset)
    rx.write(b'PKTLEN 127\r\n')
    time.sleep(0.3)
    
    # Set count to 50000 on TX
    tx.write(b'COUNT 50000\r\n')
    time.sleep(0.3)
    
    # Read back any responses
    while tx.in_waiting: 
        print(f"  TX: {tx.read(tx.in_waiting).decode('utf-8', errors='replace').strip()}")
    while rx.in_waiting: 
        print(f"  RX: {rx.read(rx.in_waiting).decode('utf-8', errors='replace').strip()}")
    
    tx.close()
    rx.close()

def run_flrc_sweep():
    """Phase 1: FLRC sustained sweep at 4 bitrates."""
    all_results = []
    
    bitrates = [2600, 1300, 650, 325]
    durations = [10, 10, 10, 10]
    
    for br, dur in zip(bitrates, durations):
        label = f"FLRC_{br}"
        print(f"\n{'='*60}")
        print(f"Setting bitrate to {br} kbps on both boards...")
        set_bitrate_both(br)
        time.sleep(1)
        
        result = run_test(duration_sec=dur, label=label)
        all_results.append(result)
        time.sleep(2)
    
    return all_results

def run_lora_sweep():
    """Phase 2: LoRa sustained sweep at 4 SF/BW combos."""
    all_results = []
    
    # LoRa configs: (SF, BW_kHz, duration_sec)
    configs = [
        (5, 1625, 30),    # SF5 BW1625 — fast LoRa
        (7, 812, 60),     # SF7 BW812 — medium
        (9, 406, 120),    # SF9 BW406 — slow
        (12, 203, 100),   # SF12 BW203 — very slow
    ]
    
    for sf, bw, dur in configs:
        label = f"LoRa_SF{sf}_BW{bw}"
        
        # Set LoRa params on both boards
        tx = serial.Serial(TX_PORT, BAUD, timeout=1)
        rx = serial.Serial(RX_PORT, BAUD, timeout=1)
        time.sleep(0.3)
        while tx.in_waiting: tx.read(tx.in_waiting)
        while rx.in_waiting: rx.read(rx.in_waiting)
        
        tx.write(f"SF {sf}\r\n".encode())
        tx.write(f"BW {bw}\r\n".encode())
        rx.write(f"SF {sf}\r\n".encode())
        rx.write(f"BW {bw}\r\n".encode())
        time.sleep(0.5)
        tx.write(b"INIT\r\n")
        rx.write(b"INIT\r\n")
        time.sleep(2)
        
        while tx.in_waiting: tx.read(tx.in_waiting)
        while rx.in_waiting: rx.read(rx.in_waiting)
        
        tx.close()
        rx.close()
        
        result = run_test(duration_sec=dur, label=label)
        all_results.append(result)
        time.sleep(2)
    
    return all_results

if __name__ == "__main__":
    phase = sys.argv[1] if len(sys.argv) > 1 else "flrc"
    
    if phase == "flrc":
        results = run_flrc_sweep()
    elif phase == "lora":
        results = run_lora_sweep()
    elif phase == "all":
        results = run_flrc_sweep() + run_lora_sweep()
    else:
        # Single test with custom duration
        dur = int(sys.argv[2]) if len(sys.argv) > 2 else 15
        results = [run_test(duration_sec=dur, label=phase)]
    
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for r in results:
        print(f"  {r['label']}: {r.get('rx_line', 'NO RX RESULT')}")