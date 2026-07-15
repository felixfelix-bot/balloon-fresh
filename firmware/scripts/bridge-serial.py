#!/usr/bin/env python3
"""Bridge serial helper — read, send, monitor RP2040 via ESP32 UART bridge.

Usage:
  python3 bridge-serial.py read  PORT=/dev/ttyACM1 SECS=10
  python3 bridge-serial.py send  PORT=/dev/ttyACM1 CMD=RUN
  python3 bridge-serial.py monitor PORT=/dev/ttyACM1
  python3 bridge-serial.py test  PORT=/dev/ttyACM1  # send RUN + listen 20s
"""
import serial, time, sys

def parse_args(argv):
    args = {}
    for a in argv:
        if '=' in a:
            k, v = a.split('=', 1)
            args[k.lower()] = v
    return args

args = parse_args(sys.argv[2:])
port = args.get('port', '/dev/ttyACM1')
mode = sys.argv[1] if len(sys.argv) > 1 else 'read'

if mode == 'send':
    cmd = args.get('cmd', 'RUN')
    s = serial.Serial(port, 115200)
    s.write(f"{cmd}\r\n".encode())
    s.close()
    print(f"Sent: {cmd}")
    sys.exit(0)

if mode == 'read':
    secs = int(args.get('secs', '10'))
    s = serial.Serial(port, 115200, timeout=0.5)
    end = time.time() + secs
    while time.time() < end:
        d = s.read(4096)
        if d:
            sys.stdout.write(d.decode(errors='replace'))
            sys.stdout.flush()
    s.close()
    sys.exit(0)

if mode == 'monitor':
    s = serial.Serial(port, 115200, timeout=0.5)
    try:
        while True:
            d = s.read(4096)
            if d:
                sys.stdout.write(d.decode(errors='replace'))
                sys.stdout.flush()
    except KeyboardInterrupt:
        pass
    s.close()
    sys.exit(0)

if mode == 'test':
    secs = int(args.get('secs', '20'))
    s = serial.Serial(port, 115200, timeout=0.5)
    # Flush
    s.read(4096)
    # Send RUN
    s.write(b'RUN\r\n')
    time.sleep(0.5)
    # Listen
    end = time.time() + secs
    while time.time() < end:
        d = s.read(4096)
        if d:
            sys.stdout.write(d.decode(errors='replace'))
            sys.stdout.flush()
    s.close()
    sys.exit(0)

print(f"Unknown mode: {mode}")
print(__doc__)
sys.exit(1)
