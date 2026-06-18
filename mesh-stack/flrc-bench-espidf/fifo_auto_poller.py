#!/usr/bin/env python3
"""Auto-poll for TX board, flash fifo_tx.bin, then monitor both boards for FIFO test results."""

import subprocess
import serial
import time
import sys
import os
import glob

BUILD_DIR = "/home/c03rad0r/esp32-balloon-integration/mesh-stack/flrc-bench-espidf/build"
RX_PORT = "/dev/ttyACM1"
TX_MAC = "96:dc"

def find_tx_board():
    """Look for a new ESP32-C3 that isn't our RX board."""
    for port in sorted(glob.glob("/dev/ttyACM*")):
        if port == RX_PORT:
            continue
        try:
            result = subprocess.run(
                ["esptool.py", "--no-stub", "-p", port, "chip_id"],
                capture_output=True, text=True, timeout=5
            )
            if "ESP32-C3" in result.stdout:
                return port
        except:
            continue
    return None

def flash_tx(port):
    """Flash fifo_tx.bin to the TX board."""
    print(f"[FLASH] Flashing fifo_tx.bin to {port}...", flush=True)
    
    bootloader = f"{BUILD_DIR}/bootloader/bootloader.bin"
    partition = f"{BUILD_DIR}/partition_table/partition-table.bin"
    
    # Try to build TX firmware if build dir has RX config
    # Check if the binary matches TX by looking at the config
    app_bin = f"{BUILD_DIR}/flrc-bench-espidf.bin"
    
    cmd = [
        "esptool.py", "--chip", "esp32c3", "-p", port, "-b", "115200",
        "--before", "default_reset", "--after", "hard_reset", "--no-stub",
        "write_flash", "--flash_mode", "dio", "--flash_size", "4MB",
        "--flash_freq", "80m",
        "0x0", bootloader,
        "0x8000", partition,
        "0x10000", app_bin
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode == 0:
        print(f"[FLASH] SUCCESS", flush=True)
        return True
    else:
        # Try without --no-stub
        cmd2 = [
            "esptool.py", "--chip", "esp32c3", "-p", port, "-b", "115200",
            "--before", "default_reset", "--after", "hard_reset",
            "write_flash", "--flash_mode", "dio", "--flash_size", "4MB",
            "--flash_freq", "80m",
            "0x0", bootloader,
            "0x8000", partition,
            "0x10000", app_bin
        ]
        result2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=120)
        if result2.returncode == 0:
            print(f"[FLASH] SUCCESS (with stub)", flush=True)
            return True
        print(f"[FLASH] FAILED: {result.stderr[-200:]}", flush=True)
        return False

def monitor_both(tx_port, duration=180):
    """Monitor both TX and RX serial outputs."""
    print(f"\n[MONITOR] TX={tx_port} RX={RX_PORT} for {duration}s", flush=True)
    
    tx_log = open("fifo_tx_output.csv", "a")
    rx_log = open("fifo_rx_results.csv", "a")
    
    try:
        tx_ser = serial.Serial(tx_port, 115200, timeout=1)
    except:
        print("[ERROR] Cannot open TX port", flush=True)
        return
    try:
        rx_ser = serial.Serial(RX_PORT, 115200, timeout=1)
    except:
        print("[ERROR] Cannot open RX port", flush=True)
        tx_ser.close()
        return
    
    start = time.time()
    interesting = 0
    
    while time.time() - start < duration:
        elapsed = int(time.time() - start)
        
        # Read TX
        try:
            tx_line = tx_ser.readline().decode('utf-8', errors='replace').strip()
            if tx_line:
                tx_log.write(f"{elapsed},{tx_line}\n")
                tx_log.flush()
                if any(k in tx_line for k in ['sent=', 'Burst', 'COMPLETE']):
                    print(f"[{elapsed:3d}s TX] {tx_line}", flush=True)
        except:
            pass
        
        # Read RX
        try:
            rx_line = rx_ser.readline().decode('utf-8', errors='replace').strip()
            if rx_line:
                rx_log.write(f"{elapsed},{rx_line}\n")
                rx_log.flush()
                if any(k in rx_line for k in ['Phase', 'FIFO', 'getRxFifoLevel', 
                        'batch_ratio', 'throughput', 'Read ', 'auto_rx',
                        'ALL TEST', 'pkts_in_fifo']):
                    print(f"[{elapsed:3d}s RX] {rx_line}", flush=True)
                    interesting += 1
        except:
            pass
        
        # Check if TX board still alive
        if not os.path.exists(tx_port):
            print(f"[{elapsed}s] TX board disconnected!", flush=True)
            break
    
    tx_ser.close()
    rx_ser.close()
    tx_log.close()
    rx_log.close()
    print(f"\n[MONITOR] Done. {interesting} interesting lines captured.", flush=True)

def main():
    print("=" * 60, flush=True)
    print("  FIFO Test Auto-Poller", flush=True)
    print("  RX on ttyACM1 (C6:98), waiting for TX board (96:DC)", flush=True)
    print("=" * 60, flush=True)
    
    # First, rebuild RX firmware and reflash
    print("\n[SETUP] Rebuilding RX firmware...", flush=True)
    os.chdir("/home/c03rad0r/esp32-balloon-integration/mesh-stack/flrc-bench-espidf")
    
    # Write RX config
    with open("sdkconfig.defaults", "w") as f:
        f.write("""CONFIG_IDF_TARGET="esp32c3"
CONFIG_ESP_SYSTEM_DEFAULT_CPU_FREQ_80=y
CONFIG_ESP_SYSTEM_DEFAULT_CPU_FREQ=80
CONFIG_LOG_DEFAULT_LEVEL_INFO=y
CONFIG_LOG_DEFAULT_LEVEL=3
CONFIG_ESP_SYSTEM_PANIC_PRINT_REBOOT=y
CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y
CONFIG_ESPTOOLPY_FLASHMODE_DIO=y
CONFIG_ESPTOOLPY_FLASHMODE="dio"
CONFIG_ESPTOOLPY_FLASHSIZE_4MB=y
CONFIG_ESPTOOLPY_FLASHSIZE="4MB"
CONFIG_ESP_TASK_WDT=n
CONFIG_BENCH_MODE_FIFO_TEST=y
""")
    
    subprocess.run(["bash", "-c", "source ~/esp/esp-idf/export.sh && idf.py build"], 
                   capture_output=True, text=True, timeout=300)
    print("[SETUP] RX firmware built", flush=True)
    
    # Flash RX
    subprocess.run([
        "esptool.py", "--chip", "esp32c3", "-p", RX_PORT, "-b", "115200",
        "--before", "default_reset", "--after", "hard_reset", "--no-stub",
        "write_flash", "--flash_mode", "dio", "--flash_size", "4MB", "--flash_freq", "80m",
        "0x0", "build/bootloader/bootloader.bin",
        "0x8000", "build/partition_table/partition-table.bin",
        "0x10000", "build/flrc-bench-espidf.bin"
    ], capture_output=True, text=True, timeout=120)
    print("[SETUP] RX firmware flashed", flush=True)
    
    # Now build TX firmware (keep build dir for flashing later)
    print("\n[SETUP] Building TX firmware...", flush=True)
    with open("sdkconfig.defaults", "w") as f:
        f.write("""CONFIG_IDF_TARGET="esp32c3"
CONFIG_ESP_SYSTEM_DEFAULT_CPU_FREQ_80=y
CONFIG_ESP_SYSTEM_DEFAULT_CPU_FREQ=80
CONFIG_LOG_DEFAULT_LEVEL_INFO=y
CONFIG_LOG_DEFAULT_LEVEL=3
CONFIG_ESP_SYSTEM_PANIC_PRINT_REBOOT=y
CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y
CONFIG_ESPTOOLPY_FLASHMODE_DIO=y
CONFIG_ESPTOOLPY_FLASHMODE="dio"
CONFIG_ESPTOOLPY_FLASHSIZE_4MB=y
CONFIG_ESPTOOLPY_FLASHSIZE="4MB"
CONFIG_ESP_TASK_WDT=n
CONFIG_BENCH_MODE_FIFO_TX=y
""")
    subprocess.run(["bash", "-c", "rm -rf build sdkconfig && source ~/esp/esp-idf/export.sh && idf.py build"], 
                   capture_output=True, text=True, timeout=300)
    
    # Save TX binary
    import shutil
    shutil.copy("build/flrc-bench-espidf.bin", "/tmp/range_bins/fifo_tx_ready.bin")
    shutil.copy("build/bootloader/bootloader.bin", "/tmp/range_bins/fifo_tx_bootloader.bin")
    shutil.copy("build/partition_table/partition-table.bin", "/tmp/range_bins/fifo_tx_partition.bin")
    print("[SETUP] TX firmware built and saved to /tmp/range_bins/", flush=True)
    
    # Poll for TX board
    poll_start = time.time()
    max_poll = 600  # 10 minutes
    
    while time.time() - poll_start < max_poll:
        elapsed = int(time.time() - poll_start)
        
        if not os.path.exists(RX_PORT):
            print(f"[{elapsed}s] RX board gone! Waiting...", flush=True)
            time.sleep(10)
            continue
        
        tx_port = find_tx_board()
        if tx_port:
            print(f"\n[{elapsed}s] TX BOARD FOUND: {tx_port}!", flush=True)
            
            if flash_tx(tx_port):
                time.sleep(5)  # Wait for TX boot
                
                if os.path.exists(tx_port) and os.path.exists(RX_PORT):
                    print("\n[MONITOR] Starting dual monitoring...", flush=True)
                    monitor_both(tx_port, duration=180)
                else:
                    print("[ERROR] A board disappeared during setup", flush=True)
            break
        
        if elapsed % 30 == 0 and elapsed > 0:
            print(f"[{elapsed}s] Still polling for TX board...", flush=True)
        
        time.sleep(5)
    
    if elapsed >= max_poll - 10:
        print(f"\n[TIMEOUT] TX board did not appear in {max_poll}s", flush=True)
    
    print("\n[DONE] Poller finished.", flush=True)

if __name__ == "__main__":
    main()
