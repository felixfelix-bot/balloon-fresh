#!/usr/bin/env python3
"""Phase 1 interop test runner. Sends commands to ESP32/RP2040, captures results."""
import serial, time, sys, os

ESP32_A = "/dev/ttyACM2"
ESP32_B = "/dev/ttyACM3"
RP2040  = "/dev/ttyACM1"
BAUD = 115200
PY = "/home/c03rad0r/.espressif/python_env/idf5.4_py3.13_env/bin/python3"

def open_serial(port, wait_boot=True):
    """Open serial port, wait for ESP32 boot if needed."""
    s = serial.Serial(port, BAUD, timeout=0.3)
    s.dtr = False
    s.rts = False
    if wait_boot:
        time.sleep(0.1)
        s.dtr = True
        time.sleep(0.1)
        # Wait for boot
        time.sleep(3)
        # Drain boot messages
        s.read(65536)
    return s

def send_cmd(s, cmd, wait=0.3):
    """Send a command and collect response."""
    s.write((cmd + "\n").encode())
    time.sleep(wait)
    resp = b""
    for _ in range(10):
        d = s.read(4096)
        if d:
            resp += d
        else:
            break
    return resp.decode(errors='replace')

def drain(s, duration=5):
    """Read everything for duration seconds."""
    s.timeout = 0.3
    end = time.time() + duration
    chunks = []
    while time.time() < end:
        d = s.read(4096)
        if d:
            chunks.append(d)
    return b"".join(chunks).decode(errors='replace')

def reset_esp32(port):
    """Reset ESP32 via USB CDC and wait for boot."""
    # Toggle DTR/RTS to trigger reset
    s = serial.Serial()
    s.port = port
    s.baudrate = BAUD
    s.dtr = False
    s.rts = True
    s.timeout = 0.5
    s.open()
    time.sleep(0.1)
    s.dtr = True
    s.rts = False
    time.sleep(0.1)
    s.close()

print("=" * 60)
print("PHASE 1 INTEROP TEST RUNNER")
print("=" * 60)

# === Step 1: Probe ESP32-A ===
print("\n[1/7] Probing ESP32-A (/dev/ttyACM2)...")
try:
    reset_esp32(ESP32_A)
    time.sleep(3)
    s_a = open_serial(ESP32_A, wait_boot=False)
    resp = send_cmd(s_a, "HELP", 0.5)
    if "Commands" in resp:
        print(f"  ✅ ESP32-A alive: {resp.strip()[:100]}")
        esp32_a_ok = True
    else:
        print(f"  ⚠️ ESP32-A unexpected response: {resp.strip()[:100]}")
        esp32_a_ok = False
except Exception as e:
    print(f"  ❌ ESP32-A failed: {e}")
    esp32_a_ok = False

# === Step 2: Probe ESP32-B ===
print("\n[2/7] Probing ESP32-B (/dev/ttyACM3)...")
try:
    reset_esp32(ESP32_B)
    time.sleep(3)
    s_b = open_serial(ESP32_B, wait_boot=False)
    resp = send_cmd(s_b, "HELP", 0.5)
    if "Commands" in resp:
        print(f"  ✅ ESP32-B alive: {resp.strip()[:100]}")
        esp32_b_ok = True
    else:
        print(f"  ⚠️ ESP32-B unexpected response: {resp.strip()[:100]}")
        esp32_b_ok = False
except Exception as e:
    print(f"  ❌ ESP32-B failed: {e}")
    esp32_b_ok = False

# === Step 3: Probe RP2040 ===
print("\n[3/7] Probing RP2040 (/dev/ttyACM1)...")
try:
    s_r = serial.Serial(RP2040, BAUD, timeout=1.0)
    s_r.dtr = True
    time.sleep(2)
    boot = drain(s_r, 3)
    if boot:
        print(f"  ✅ RP2040 alive: {boot.strip()[:200]}")
        rp2040_ok = True
    else:
        # Try sending a character to trigger output
        s_r.write(b"\n")
        time.sleep(1)
        resp = drain(s_r, 2)
        print(f"  ⚠️ RP2040 no boot msg, after newline: {resp.strip()[:200]}")
        rp2040_ok = len(resp) > 0
except Exception as e:
    print(f"  ❌ RP2040 failed: {e}")
    rp2040_ok = False

# === Step 4: Test 1 - ESP32-A TX → ESP32-B RX (FLRC) ===
print("\n[4/7] Test 1: ESP32-A TX → ESP32-B RX (FLRC 2600, 255B, 100pkts)")
if esp32_a_ok and esp32_b_ok:
    try:
        # Configure RX first
        send_cmd(s_b, "ROLE RX", 0.2)
        send_cmd(s_b, "MODE FLRC", 0.2)
        send_cmd(s_b, "FREQ 2450", 0.2)
        send_cmd(s_b, "BR 2600", 0.2)
        send_cmd(s_b, "PWR 12", 0.2)
        send_cmd(s_b, "SIZE 255", 0.2)
        send_cmd(s_b, "RUN", 0.2)  # Start RX
        
        # Configure TX
        send_cmd(s_a, "ROLE TX", 0.2)
        send_cmd(s_a, "MODE FLRC", 0.2)
        send_cmd(s_a, "FREQ 2450", 0.2)
        send_cmd(s_a, "BR 2600", 0.2)
        send_cmd(s_a, "PWR 12", 0.2)
        send_cmd(s_a, "SIZE 255", 0.2)
        send_cmd(s_a, "COUNT 100", 0.2)
        send_cmd(s_a, "DELAY 10", 0.2)
        
        # Trigger TX
        print("  Triggering TX burst...")
        tx_resp = send_cmd(s_a, "RUN", 5)
        print(f"  TX result: {tx_resp.strip()[:200]}")
        
        # Read RX output
        time.sleep(2)
        rx_data = drain(s_b, 10)
        print(f"  RX data ({len(rx_data)} bytes): {rx_data.strip()[:500]}")
        
        # Parse for results
        if "RX RESULTS" in rx_data or "rx=" in rx_data.lower():
            print("  ✅ Test 1: PACKETS RECEIVED")
        elif rx_data.strip():
            print(f"  ⚠️ Test 1: Got output but no clear results")
        else:
            print("  ❌ Test 1: No packets received")
    except Exception as e:
        print(f"  ❌ Test 1 failed: {e}")
else:
    print("  ⏭️ Skipped (devices not ready)")

# === Step 5: Test 2 - ESP32-A TX → RP2040 RX ===
print("\n[5/7] Test 2: ESP32-A TX → RP2040 RX (FLRC)")
if esp32_a_ok and rp2040_ok:
    print("  (RP2040 firmware uses different protocol - checking RX capability)")
    # The RP2040 firmware auto-starts in RX mode after init
    # Just trigger ESP32 TX and see if RP2040 outputs anything
    try:
        # Restart TX on ESP32-A
        send_cmd(s_a, "COUNT 100", 0.2)
        send_cmd(s_a, "RUN", 5)
        # Read RP2040
        time.sleep(2)
        rx_data = drain(s_r, 10)
        print(f"  RP2040 output ({len(rx_data)} bytes): {rx_data.strip()[:300]}")
        if "pkt" in rx_data.lower() or "irq" in rx_data.lower() or "RSSI" in rx_data:
            print("  ✅ Test 2: RP2040 received data")
        elif rx_data.strip():
            print(f"  ⚠️ Test 2: RP2040 output but unclear")
        else:
            print("  ❌ Test 2: No RP2040 output (may be in wrong mode)")
    except Exception as e:
        print(f"  ❌ Test 2 failed: {e}")
else:
    print("  ⏭️ Skipped (devices not ready)")

# === Step 6: Test 3 - RP2040 TX → ESP32-B RX ===
print("\n[6/7] Test 3: RP2040 TX → ESP32-B RX")
if esp32_b_ok and rp2040_ok:
    try:
        # ESP32-B in RX mode
        send_cmd(s_b, "MODE FLRC", 0.2)
        send_cmd(s_b, "FREQ 2450", 0.2)
        send_cmd(s_b, "BR 2600", 0.2)
        send_cmd(s_b, "RUN", 0.2)
        
        # RP2040: send 'T' to transmit
        print("  Sending TX command to RP2040...")
        s_r.write(b"T\n")
        time.sleep(5)
        
        # Read ESP32-B
        rx_data = drain(s_b, 10)
        print(f"  ESP32-B output ({len(rx_data)} bytes): {rx_data.strip()[:300]}")
        if "RX RESULTS" in rx_data or "rx=" in rx_data.lower():
            print("  ✅ Test 3: ESP32 received RP2040 packets")
        elif rx_data.strip():
            print(f"  ⚠️ Test 3: Got output but unclear")
        else:
            print("  ❌ Test 3: No packets received from RP2040")
    except Exception as e:
        print(f"  ❌ Test 3 failed: {e}")
else:
    print("  ⏭️ Skipped (devices not ready)")

# === Step 7: Summary ===
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"ESP32-A: {'✅' if esp32_a_ok else '❌'}")
print(f"ESP32-B: {'✅' if esp32_b_ok else '❌'}")
print(f"RP2040:  {'✅' if rp2040_ok else '❌'}")
print("\nDone. See output above for test results.")

# Close ports
for s in [s_a if esp32_a_ok else None, s_b if esp32_b_ok else None, s_r if rp2040_ok else None]:
    if s:
        try: s.close()
        except: pass
