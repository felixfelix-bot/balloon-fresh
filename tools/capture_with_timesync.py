#!/usr/bin/env python3
"""Capture serial data from RX board with periodic SET_TIME sync.

Sends SET_TIME <unix_timestamp> to RX every 60 seconds to keep
the RX clock synced to laptop UTC. Captures all output to a file.

Usage:
  python3 capture_with_timesync.py /dev/ttyACM0 output.txt [duration_sec]
  
Default duration: 300 seconds (5 minutes).
"""
import serial
import sys
import time
import os

def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <port> <output_file> [duration_sec]")
        sys.exit(1)
    
    port = sys.argv[1]
    outfile = sys.argv[2]
    duration = int(sys.argv[3]) if len(sys.argv) > 3 else 300
    
    ser = serial.Serial(port, 115200, timeout=0.1)
    
    # Send initial SET_TIME
    ts = int(time.time())
    ser.write(f"SET_TIME {ts}\n".encode())
    print(f"[{time.strftime('%H:%M:%S')}] SET_TIME {ts} sent")
    
    start = time.time()
    last_sync = start
    sync_interval = 60  # seconds between SET_TIME resyncs
    
    with open(outfile, 'w') as f:
        while time.time() - start < duration:
            now = time.time()
            
            # Periodic resync
            if now - last_sync >= sync_interval:
                ts = int(time.time())
                try:
                    ser.write(f"SET_TIME {ts}\n".encode())
                    print(f"[{time.strftime('%H:%M:%S')}] SET_TIME {ts} resync")
                except Exception as e:
                    print(f"[{time.strftime('%H:%M:%S')}] SET_TIME failed: {e}")
                last_sync = now
            
            # Read serial data
            try:
                chunk = ser.read(4096)
                if chunk:
                    text = chunk.decode(errors='replace')
                    f.write(text)
                    f.flush()
            except Exception as e:
                print(f"[{time.strftime('%H:%M:%S')}] Read error: {e}")
                # Try to reopen
                try:
                    ser.close()
                except:
                    pass
                time.sleep(1)
                try:
                    ser = serial.Serial(port, 115200, timeout=0.1)
                except:
                    print(f"[{time.strftime('%H:%M:%S')}] Reopen failed")
                    continue
    
    ser.close()
    elapsed = time.time() - start
    print(f"Capture done: {elapsed:.0f}s, output: {outfile}")

if __name__ == '__main__':
    main()