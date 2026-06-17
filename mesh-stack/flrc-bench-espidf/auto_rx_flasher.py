#!/usr/bin/env python3
"""Auto-poll for flaky board, flash RX firmware, then monitor both boards."""

import subprocess
import serial
import time
import sys
import os

BUILD_DIR = "/home/c03rad0r/esp32-balloon-integration/mesh-stack/flrc-bench-espidf/build"
BOOTLOADER = f"{BUILD_DIR}/bootloader/bootloader.bin"
PARTITION = f"{BUILD_DIR}/partition_table/partition-table.bin"
APP = f"{BUILD_DIR}/flrc-bench-espidf.bin"
KNOWN_MAC = "96:dc"
TX_PORT = "/dev/ttyACM1"

def find_new_board():
    """Check for a new ESP32-C3 board that isn't our TX board."""
    try:
        result = subprocess.run(
            ["esptool.py", "--no-stub", "-p", "", "chip_id"],
            capture_output=True, text=True, timeout=3
        )
    except:
        pass
    
    import glob
    ports = sorted(glob.glob("/dev/ttyACM*"))
    for port in ports:
        if port == TX_PORT:
            continue
        try:
            result = subprocess.run(
                ["esptool.py", "--no-stub", "-p", port, "chip_id"],
                capture_output=True, text=True, timeout=5
            )
            if KNOWN_MAC in result.stdout.lower():
                return port
            if "ESP32-C3" in result.stdout:
                return port
        except:
            continue
    return None

def flash_rx(port):
    """Flash range_rx.bin to the given port."""
    print(f"[FLASH] Flashing RX firmware to {port}...", flush=True)
    cmd = [
        "esptool.py", "--chip", "esp32c3", "-p", port, "-b", "115200",
        "--before", "default_reset", "--after", "hard_reset", "--no-stub",
        "write_flash", "--flash_mode", "dio", "--flash_size", "4MB",
        "--flash_freq", "80m",
        "0x0", BOOTLOADER,
        "0x8000", PARTITION,
        "0x10000", APP
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode == 0:
        print(f"[FLASH] SUCCESS - RX firmware flashed to {port}", flush=True)
        return True
    else:
        print(f"[FLASH] FAILED: {result.stderr[-200:]}", flush=True)
        return False

def monitor_both(tx_port, rx_port, duration=300):
    """Monitor both TX and RX serial outputs."""
    print(f"\n[MONITOR] TX={tx_port} RX={rx_port} for {duration}s", flush=True)
    print("[MONITOR] Looking for RX detecting TX...", flush=True)
    
    tx_ser = serial.Serial(tx_port, 115200, timeout=1)
    rx_ser = serial.Serial(rx_port, 115200, timeout=1)
    
    tx_log = open("tx_auto_log.csv", "a")
    rx_log = open("rx_auto_log.csv", "a")
    
    start = time.time()
    rx_detected_tx = False
    pkt_count = 0
    result_count = 0
    
    while time.time() - start < duration:
        elapsed = int(time.time() - start)
        
        # Read TX
        try:
            tx_line = tx_ser.readline().decode('utf-8', errors='replace').strip()
            if tx_line:
                tx_log.write(f"{elapsed},{tx_line}\n")
                tx_log.flush()
        except:
            pass
        
        # Read RX
        try:
            rx_line = rx_ser.readline().decode('utf-8', errors='replace').strip()
            if rx_line:
                rx_log.write(f"{elapsed},{rx_line}\n")
                rx_log.flush()
                
                if 'Window' in rx_line and '>>>' in rx_line:
                    if not rx_detected_tx:
                        rx_detected_tx = True
                        print(f"\n[SUCCESS] RX DETECTED TX! ({rx_line})", flush=True)
                
                if rx_line.startswith('PKT,'):
                    pkt_count += 1
                    if pkt_count % 10 == 0:
                        print(f"  [{elapsed}s] {pkt_count} packets received", flush=True)
                
                if rx_line.startswith('RESULT,'):
                    result_count += 1
                    print(f"  [{elapsed}s] RESULT #{result_count}: {rx_line[:80]}...", flush=True)
        except:
            pass
    
    tx_ser.close()
    rx_ser.close()
    tx_log.close()
    rx_log.close()
    
    print(f"\n[MONITOR] Done. RX detected TX: {rx_detected_tx}", flush=True)
    print(f"[MONITOR] Packets received: {pkt_count}", flush=True)
    print(f"[MONITOR] Window results: {result_count}", flush=True)
    
    return rx_detected_tx

def main():
    print("=" * 60, flush=True)
    print("  Auto RX Flasher + Monitor", flush=True)
    print("  Polling for flaky board (96:DC)...", flush=True)
    print("=" * 60, flush=True)
    
    poll_start = time.time()
    max_poll = 600  # 10 minutes
    
    while time.time() - poll_start < max_poll:
        elapsed = int(time.time() - poll_start)
        
        # Check if TX board still alive
        if not os.path.exists(TX_PORT):
            print(f"[{elapsed}s] TX board gone! Waiting...", flush=True)
            time.sleep(5)
            continue
        
        # Poll for new board
        new_port = find_new_board()
        if new_port:
            print(f"\n[{elapsed}s] NEW BOARD DETECTED: {new_port}", flush=True)
            
            # Flash RX firmware
            if flash_rx(new_port):
                time.sleep(3)  # Wait for boot
                
                # Check TX still alive
                if os.path.exists(TX_PORT):
                    # Monitor both for 5 minutes
                    success = monitor_both(TX_PORT, new_port, duration=300)
                    if success:
                        print("\n[RESULT] BIDIRECTIONAL TEST PASSED!", flush=True)
                    else:
                        print("\n[RESULT] RX did not detect TX in 5 minutes", flush=True)
                else:
                    print("[ERROR] TX board disappeared during RX setup", flush=True)
            break
        
        if elapsed % 30 == 0:
            print(f"[{elapsed}s] Still polling... TX alive on {TX_PORT}", flush=True)
        
        time.sleep(5)
    
    if elapsed >= max_poll - 10:
        print(f"\n[TIMEOUT] Flaky board did not appear in {max_poll}s", flush=True)
        print("[INFO] TX board continues running range_tx.bin", flush=True)

if __name__ == "__main__":
    main()
