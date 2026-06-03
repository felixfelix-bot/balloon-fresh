#!/usr/bin/env python3
"""Passive MeshCore serial monitor with timestamps.
Captures all serial output from the repeater/companion node,
prepends ISO timestamps, and saves to a log file.
Usage: python3 monitor.py [/dev/ttyACM2] [duration_seconds]
"""
import serial, time, sys, os, datetime

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyACM2"
DURATION = int(sys.argv[2]) if len(sys.argv) > 2 else 600
BAUD = 115200
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")

os.makedirs(LOG_DIR, exist_ok=True)
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
logfile = os.path.join(LOG_DIR, f"meshcore_{timestamp}.log")

print(f"Monitoring {PORT} for {DURATION}s, logging to {logfile}")

ser = serial.Serial(PORT, BAUD, timeout=1)
ser.dtr = False
time.sleep(0.1)
ser.rts = True
time.sleep(0.1)
ser.rts = False
time.sleep(0.1)
ser.dtr = True
time.sleep(0.5)

with open(logfile, "w") as f:
    now_str = datetime.datetime.now().isoformat()
    f.write("# MeshCore passive monitor log\n")
    f.write(f"# Port: {PORT}, Baud: {BAUD}, Duration: {DURATION}s\n")
    f.write(f"# Started: {now_str}\n")
    f.flush()

    start = time.time()
    pkt_count = 0
    last_print = 0
    while time.time() - start < DURATION:
        data = ser.read(4096)
        if data:
            now = datetime.datetime.now().isoformat()
            try:
                text = data.decode("utf-8", errors="replace")
            except:
                text = repr(data)
            for line in text.split("\n"):
                if line.strip():
                    ts_line = f"[{now}] {line}\n"
                    f.write(ts_line)
                    sys.stdout.write(ts_line)
                    sys.stdout.flush()
                    if "advert" in line.lower() or "packet" in line.lower() or "RX" in line:
                        pkt_count += 1

        elapsed = int(time.time() - start)
        if elapsed > 0 and elapsed % 60 == 0 and elapsed != last_print:
            last_print = elapsed
            status = f"[{datetime.datetime.now().isoformat()}] --- {elapsed}s elapsed, {pkt_count} events ---\n"
            f.write(status)
            sys.stdout.write(status)
            sys.stdout.flush()

    f.write(f"\n# Finished: {datetime.datetime.now().isoformat()}\n")
    f.write(f"# Duration: {DURATION}s, Events: {pkt_count}\n")

ser.close()
print(f"\nDone. Log saved to {logfile}")
