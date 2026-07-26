#!/bin/bash
# flash_board.sh — Flash RP2040 via BOOTSEL mode
# Usage: flash_board.sh <serial_suffix> <uf2_path>
# Example: flash_board.sh 242D .pio/build/rp2040-sweep-tx-v4/firmware.uf2

SERIAL="$1"
UF2="$2"

if [ -z "$SERIAL" ] || [ -z "$UF2" ]; then
    echo "Usage: $0 <serial_suffix> <uf2_path>"
    exit 1
fi

if [ ! -f "$UF2" ]; then
    echo "ERROR: UF2 file not found: $UF2"
    exit 1
fi

# Find board by serial ID
PORT=""
for dev in /dev/ttyACM[0-4]; do
    [ -e "$dev" ] || continue
    s=$(udevadm info -q property -n "$dev" 2>/dev/null | grep ID_SERIAL_SHORT | head -1 | cut -d= -f2 | tail -c5)
    if [ "$s" = "$SERIAL" ]; then
        PORT=$dev
        break
    fi
done

if [ -z "$PORT" ]; then
    echo "ERROR: Board with serial $SERIAL not found"
    echo "Connected boards:"
    for dev in /dev/ttyACM[0-4]; do
        [ -e "$dev" ] || continue
        s=$(udevadm info -q property -n "$dev" 2>/dev/null | grep ID_SERIAL_SHORT | head -1 | cut -d= -f2 | tail -c5)
        echo "  $dev ...$s"
    done
    exit 1
fi

echo "Found board: $PORT (serial=$SERIAL)"

# Enter BOOTSEL mode via 1200 baud touch
python3 -c "
import serial, time, sys
try:
    s = serial.Serial('$PORT', 1200)
    s.setDTR(False)
    time.sleep(0.1)
    s.close()
except Exception as e:
    print(f'Warning: 1200 baud touch failed: {e}', file=sys.stderr)
"

sleep 3

# Find RPI-RP2 disk
DISK=$(lsblk -ln -o NAME,LABEL | grep 'RPI-RP2' | awk '{print $1}' | head -1)

if [ -z "$DISK" ]; then
    echo "ERROR: RPI-RP2 disk not found after BOOTSEL reset"
    exit 1
fi

echo "Flashing: /dev/$DISK ← $UF2"
sudo mount -o uid=$(id -u),gid=$(id -g) /dev/${DISK}1 /tmp/rp2040-flash 2>/dev/null || \
sudo mount /dev/${DISK}1 /tmp/rp2040-flash 2>/dev/null || \
sudo mount /dev/$DISK /tmp/rp2040-flash 2>/dev/null

cp "$UF2" /tmp/rp2040-flash/
sync
sudo umount /tmp/rp2040-flash

echo "Flash complete: $SERIAL ($UF2)"
sleep 3
