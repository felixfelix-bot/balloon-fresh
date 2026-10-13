#!/usr/bin/env python3
"""E80-900MBL-02 STM32F103 stock dump via ROM ISP.

Sync strategy: spam 0x7F continuously on both CH340 ports. Any RESET
release re-enters the ROM bootloader and catches sync within ~50ms.
Then run the minimal STM32 ISP protocol (GET, GET ID, READ MEMORY) to
pull the full 64K flash image per port.

Usage: python3 e80_isp_dump.py [window_seconds]
"""
import sys, time, threading, os

import serial

PORTS = ["/dev/ttyUSB3", "/dev/ttyUSB4"]
FLASH_BASE = 0x08000000
FLASH_SIZE = 0x10000  # 64K for F103C8
CHUNK = 256
OUT_DIR = os.path.join(os.path.dirname(__file__), "..")

def open_port(port):
    return serial.Serial(
        port, 57600, bytesize=8, parity=serial.PARITY_EVEN,
        stopbits=1, timeout=0.05,
    )

def ack(ser, what):
    b = ser.read(1)
    if b != b"\x79":
        raise RuntimeError(f"{what}: expected ACK 0x79, got {b.hex() if b else 'timeout'}")
    return True

def sync_spam(ser, deadline):
    """Spam 0x7F until ACK. Returns True if synced."""
    ser.reset_input_buffer()
    while time.time() < deadline:
        ser.write(b"\x7f")
        time.sleep(0.05)
        data = ser.read(64)
        if b"\x79" in data:
            # stop spam, drain stragglers / NACKs
            time.sleep(0.1)
            ser.reset_input_buffer()
            return True
    return False

def isp_get(ser):
    ser.write(bytes([0x00, 0xFF]))
    ack(ser, "GET")
    n = ser.read(1)[0]
    ver = ser.read(1)[0]
    ser.read(n)  # supported commands + extra
    ack(ser, "GET tail")
    return ver

def isp_get_id(ser):
    ser.write(bytes([0x75, 0x8A]))
    ack(ser, "GET-ID")
    n = ser.read(1)[0]
    pid = ser.read(n + 1)
    ack(ser, "GET-ID tail")
    return pid.hex()

def isp_read(ser, addr, n):
    """READ MEMORY: n bytes (1..256) at addr."""
    ser.write(bytes([0x11, 0xEE]))
    ack(ser, "READ cmd")
    a = [(addr >> 16) & 0xFF, (addr >> 8) & 0xFF, addr & 0xFF]
    ser.write(bytes(a + [a[0] ^ a[1] ^ a[2]]))
    ack(ser, "READ addr")
    m = n - 1  # device returns N+1 bytes
    ser.write(bytes([m, (~m) & 0xFF]))
    ack(ser, "READ len")
    data = bytearray()
    while len(data) < n:
        chunk = ser.read(n - len(data))
        if not chunk:
            raise RuntimeError(f"READ data timeout at +{len(data)}")
        data.extend(chunk)
    ack(ser, "READ tail")
    return bytes(data)

def worker(port, window, results):
    r = {"status": "START"}
    results[port] = r
    try:
        ser = open_port(port)
    except Exception as e:
        r["status"] = f"OPEN-FAIL: {e}"
        print(f"[{port}] {r['status']}", flush=True)
        return
    print(f"[{port}] spamming 0x7F for {window}s — PRESS+RELEASE RESET now", flush=True)
    if not sync_spam(ser, time.time() + window):
        ser.close()
        r["status"] = "NO-SYNC (no RESET catch, or BOOT0 not high)"
        print(f"[{port}] {r['status']}", flush=True)
        return
    t_sync = time.strftime("%H:%M:%S")
    r["status"] = "SYNCED"
    print(f"[{port}] *** SYNCED at {t_sync} (ROM bootloader alive) ***", flush=True)
    try:
        ver = isp_get(ser)
        pid = isp_get_id(ser)
        r["bl_version"], r["chip_id"] = f"0x{ver:02x}", f"0x{pid}"
        print(f"[{port}] bootloader v0x{ver:02x} chip-id 0x{pid}", flush=True)
    except Exception as e:
        # sync confirmed but handshake odd — try to continue anyway
        print(f"[{port}] WARN handshake: {e}", flush=True)

    out = os.path.join(OUT_DIR, f"E80_stock_dump_{port.split('/')[-1]}.bin")
    blob = bytearray()
    t0 = time.time()
    try:
        for off in range(0, FLASH_SIZE, CHUNK):
            blob.extend(isp_read(ser, FLASH_BASE + off, CHUNK))
            if off % 0x4000 == 0:
                print(f"[{port}] read {len(blob)}/{FLASH_SIZE}", flush=True)
    except Exception as e:
        r["status"] = f"DUMP-FAIL at {len(blob)}: {e}"
        print(f"[{port}] {r['status']}", flush=True)
        ser.close()
        return
    dt = time.time() - t0
    with open(out, "wb") as f:
        f.write(blob)
    r["status"] = "DUMP-DONE"
    r["file"], r["size"], r["secs"] = out, len(blob), round(dt, 1)
    print(f"[{port}] *** DUMP-DONE {out} {len(blob)} bytes in {dt:.1f}s ***", flush=True)
    # leave port open; ROM stays in ISP (no reset) -> immediate reflash possible
    r["ser"] = ser
    return

def main():
    window = int(sys.argv[1]) if len(sys.argv) > 1 else 150
    results = {}
    threads = [
        threading.Thread(target=worker, args=(p, window, results), daemon=True)
        for p in PORTS
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(window + 300)
    print("=== FINAL ===", flush=True)
    for p, r in results.items():
        print(f"{p}: {r.get('status')} "
              f"bl={r.get('bl_version','?')} chip={r.get('chip_id','?')} "
              f"size={r.get('size','-')}", flush=True)

if __name__ == "__main__":
    main()
