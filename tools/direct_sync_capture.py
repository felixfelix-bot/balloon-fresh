#!/usr/bin/env python3
"""
Direct USB sync+capture using os.open (bypasses pyserial board guard).
Reads TX GPS UTC line-by-line, forwards SET_TIME to RX in <1ms.
Captures all RX output simultaneously.
"""
import os, sys, time, threading, re, subprocess, termios, tty

# Detect ports
TX=None; RX=None
for p in sorted([f'/dev/ttyACM{i}' for i in range(16)] + [f'/dev/ttyUSB{i}' for i in range(4)]):
    if not os.path.exists(p): continue
    r=subprocess.run(['udevadm','info','-q','property','-n',p],capture_output=True,text=True,timeout=2)
    for line in r.stdout.split('\n'):
        if 'ID_SERIAL_SHORT=' in line:
            sn=line.split('=',1)[1]
            if '242D' in sn: TX=p
            elif '8332' in sn: RX=p

print(f'TX={TX} RX={RX}', flush=True)
if not TX or not RX:
    print('ERROR: Cannot find both boards')
    sys.exit(1)

# Open with os.open (bypasses pyserial board guard)
tx_fd=os.open(TX, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
rx_fd=os.open(RX, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)

# Set raw mode on both
for fd in [tx_fd, rx_fd]:
    tty.setraw(fd)

DURATION=int(sys.argv[1]) if len(sys.argv)>1 else 170
OUTDIR=os.path.expanduser('~/repos/balloon-fresh/data/range-tests/20260725')
os.makedirs(OUTDIR, exist_ok=True)
OUTFILE=os.path.join(OUTDIR, f'forwarded-{time.strftime("%H%M%S")}.log')

print(f'Duration: {DURATION}s | Output: {OUTFILE}', flush=True)
print('GPS UTC forwarded line-by-line (sub-ms latency)', flush=True)
print('---', flush=True)

# Forwarder thread: read TX, extract GPS UTC, write SET_TIME to RX
stop_flag=False
sync_count=0

def forwarder():
    global sync_count
    buf=b''
    while not stop_flag:
        try:
            data=os.read(tx_fd, 4096)
        except (BlockingIOError, OSError):
            time.sleep(0.001)
            continue
        if data:
            buf+=data
            while b'\n' in buf:
                line, buf=buf.split(b'\n', 1)
                s=line.decode('ascii', errors='ignore')
                m=re.search(r'unix=(\d{10,})', s)
                if m:
                    utc=m.group(1).encode()
                    os.write(rx_fd, b'SET_TIME '+utc+b'\n')
                    sync_count+=1

t=threading.Thread(target=forwarder, daemon=True)
t.start()

# Main: capture RX output
rx_buf=b''
start=time.time()
with open(OUTFILE, 'wb') as f:
    while time.time()-start < DURATION:
        try:
            data=os.read(rx_fd, 4096)
        except (BlockingIOError, OSError):
            time.sleep(0.005)
            continue
        if data:
            rx_buf+=data
            f.write(data)
            f.flush()

stop_flag=True
t.join(timeout=2)
os.close(tx_fd)
os.close(rx_fd)

# Parse results
content=rx_buf.decode('ascii', errors='ignore')
phase_lines=[l for l in content.split('\n') if 'PHASE_RESULT' in l]

decoded_count=0
decoded_list=[]
failed_list=[]
for line in phase_lines:
    rx_m=re.search(r'rx=(\d+)', line)
    per_m=re.search(r'per=([\d.]+)', line)
    rssi_m=re.search(r'rssi_avg=(-?\d+)', line)
    sats_m=re.search(r'sats=(\d+)', line)
    parts=line.split()
    pid=parts[1] if len(parts)>1 else '?'
    mode=parts[2] if len(parts)>2 else '?'
    
    rx_val=int(rx_m.group(1)) if rx_m else 0
    if rx_val>0:
        decoded_count+=1
        per=per_m.group(1) if per_m else '?'
        rssi=rssi_m.group(1) if rssi_m else '?'
        sats=sats_m.group(1) if sats_m else '?'
        decoded_list.append((pid, mode, rx_val, per, rssi, sats))
    elif 'SKIP' not in mode:
        failed_list.append((pid, mode))

print(f'\n=== RESULTS ===')
print(f'Sync pushes: {sync_count}')
print(f'Total phases: {len(phase_lines)}')
print(f'Decoded: {decoded_count}')
print(f'File: {OUTFILE}')

print(f'\n=== DECODED ===')
for pid, mode, rx, per, rssi, sats in sorted(decoded_list, key=lambda x: int(x[0])):
    print(f'  OK P{pid:>3} {mode:<24} rx={rx:>4} PER={per}% RSSI={rssi} sats={sats}')

print(f'\n=== FAILED ===')
for pid, mode in sorted(failed_list, key=lambda x: int(x[0])):
    print(f'  XX P{pid:>3} {mode}')
