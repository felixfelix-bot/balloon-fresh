# FLRC PIO TX v3 Flash + Capture — Pitfalls (2026-07-16 S2)

## What Was Learned

### 1. Capture Script Blocks BOOTSEL (CRITICAL)

Running `cat /dev/ttyACMX` in background **holds the serial port open**.
When `make bootsel` tries `pyserial Serial(port, 1200)`, it fails because
the port is already occupied by the capture process.

**Symptom:** `make rp2040-flash` → "ERROR: BOOTSEL trigger failed"

**Fix:** Kill ALL capture processes BEFORE flashing:
```bash
pkill -f flrc-capture
pkill -f "cat /dev/ttyACM"
fuser -k /dev/ttyACM*
sleep 1
```

### 2. Stale Mount After TX Flash Breaks RX Flash

After flashing TX via UF2 copy, the `/tmp/rp2040-flash` mount point
holds a stale mount. When RX BOOTSEL triggers and a new RPI-RP2 appears,
the old mount interferes:

**Symptom:** `cp firmware.uf2 /tmp/rp2040-flash/` → "Permission denied"
or "No space left on device"

**Fix:** Always umount between flashes:
```bash
SUDO_ASKPASS=~/.hermes/scripts/sudo-askpass.sh sudo -A umount /tmp/rp2040-flash
```

### 3. Correct Sequence: Flash → Capture (NOT concurrent)

Capture must start AFTER flash completes, not during. The board needs
the port free for 1200 baud BOOTSEL, then reboots with new firmware.

```bash
# 1. Kill capture
pkill -f flrc-capture; sleep 1

# 2. Flash TX
make rp2040-flash ENV=rp2040-pio-tx-v3 PORT=/dev/ttyACM0

# 3. Re-discover ports (numbers shift!)
for dev in /dev/ttyACM*; do
    [ -e "$dev" ] || continue
    s=$(udevadm info -q property "$dev" | grep ID_SERIAL_SHORT | cut -d= -f2)
    echo "$dev serial=$s"
done

# 4. IMMEDIATELY read UART bridge (catches 8s WAIT + TX start + debug)
stty -F /dev/ttyACM2 115200 raw -echo
timeout 30 cat /dev/ttyACM2

# 5. Flash RX (umount stale first)
sudo umount /tmp/rp2040-flash
make rp2040-flash ENV=rp2040-flrc-rx PORT=/dev/ttyACM0
```

### 4. Port Assignments

Current (2026-07-16):
- ACM0 = TX board (8332) — disappears when PIO kills CDC
- ACM1 = ESP32 (70:AF:09:21:FB:18)
- ACM2 = ESP32 UART bridge (70:AF:09:13:21:00)
- ACM3 = RX board (F242D)
