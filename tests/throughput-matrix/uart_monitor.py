import serial, time, sys

port = sys.argv[1] if len(sys.argv) > 1 else '/dev/ttyUSB4'

s = serial.Serial(port, 115200, timeout=0.05)
print(f"Monitoring {port}... Waiting for boot banner...")

start = time.time()
boot_seen = False
while time.time() - start < 30:
    r = s.read(4096)
    if r:
        print(f"[{time.time()-start:.1f}s] RX {len(r)}b: {r}")
        if not boot_seen and b'BENCH FW' in r:
            boot_seen = True
            print("Boot banner detected! Sending ID?...")
            time.sleep(0.5)
            s.write(b'ID?\r')
            time.sleep(2)
            r2 = s.read(4096)
            if r2:
                print(f"ID? response: {r2}")
            else:
                print("No ID? response")
            s.write(b'HELP\r')
            time.sleep(2)
            r3 = s.read(4096)
            if r3:
                print(f"HELP response: {r3[:200]}")
            break

if not boot_seen:
    print("No boot banner in 30s")

s.close()