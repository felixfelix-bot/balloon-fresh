#!/bin/bash
# Simple TX board poller - watches for new ESP32-C3, flashes TX firmware, monitors

source ~/esp/esp-idf/export.sh 2>/dev/null

RX_PORT="/dev/ttyACM1"
TX_BIN="/tmp/fifo_bins/fifo_tx.bin"
BOOTLOADER="/tmp/fifo_bins/bootloader.bin"
PARTITION="/tmp/fifo_bins/partition.bin"
LOG="/home/c03rad0r/esp32-balloon-integration/mesh-stack/flrc-bench-espidf/fifo_results.log"

echo "=== TX Board Poller ===" | tee "$LOG"
echo "Watching for new ESP32-C3 (not $RX_PORT)..." | tee -a "$LOG"

for i in $(seq 1 120); do
    # Check for new ports
    for port in /dev/ttyACM*; do
        [ "$port" = "$RX_PORT" ] && continue
        [ ! -e "$port" ] && continue
        
        # Check if it's an ESP32-C3
        CHIP=$(esptool.py --no-stub -p "$port" chip_id 2>&1 | grep "Detecting")
        if echo "$CHIP" | grep -q "ESP32-C3"; then
            echo "[$(date +%H:%M:%S)] TX BOARD FOUND: $port" | tee -a "$LOG"
            
            # Flash TX firmware
            echo "Flashing fifo_tx.bin..." | tee -a "$LOG"
            esptool.py --chip esp32c3 -p "$port" -b 115200 \
                --before default_reset --after hard_reset --no-stub \
                write_flash --flash_mode dio --flash_size 4MB --flash_freq 80m \
                0x0 "$BOOTLOADER" 0x8000 "$PARTITION" 0x10000 "$TX_BIN" 2>&1 | tee -a "$LOG"
            
            if [ $? -eq 0 ]; then
                echo "[$(date +%H:%M:%S)] TX FLASH SUCCESS" | tee -a "$LOG"
                sleep 5
                
                # Monitor both boards for 3 minutes
                echo "[$(date +%H:%M:%S)] Starting 3-minute monitoring..." | tee -a "$LOG"
                timeout 180 python3 -c "
import serial, time, sys
tx = serial.Serial('$port', 115200, timeout=1)
rx = serial.Serial('$RX_PORT', 115200, timeout=1)
start = time.time()
while time.time() - start < 170:
    elapsed = int(time.time() - start)
    try:
        tx_line = tx.readline().decode('utf-8', errors='replace').strip()
        if tx_line and any(k in tx_line for k in ['sent=', 'Burst', 'COMPLETE']):
            print(f'[{elapsed:3d}s TX] {tx_line}', flush=True)
    except: pass
    try:
        rx_line = rx.readline().decode('utf-8', errors='replace').strip()
        if rx_line and any(k in rx_line for k in ['Phase', 'FIFO', 'batch_ratio', 'throughput', 'Read ', 'auto_rx', 'ALL TEST', 'getRxFifoLevel']):
            print(f'[{elapsed:3d}s RX] {rx_line}', flush=True)
    except: pass
tx.close(); rx.close()
" 2>&1 | tee -a "$LOG"
                echo "[$(date +%H:%M:%S)] Monitoring complete" | tee -a "$LOG"
            else
                echo "[$(date +%H:%M:%S)] TX FLASH FAILED" | tee -a "$LOG"
            fi
            exit 0
        fi
    done
    
    # Status every 30s
    if [ $((i % 6)) -eq 0 ]; then
        echo "[$(date +%H:%M:%S)] Still polling ($((i*5))s elapsed)..." | tee -a "$LOG"
    fi
    
    sleep 5
done

echo "[$(date +%H:%M:%S)] TIMEOUT: TX board did not appear in 10 minutes" | tee -a "$LOG"
