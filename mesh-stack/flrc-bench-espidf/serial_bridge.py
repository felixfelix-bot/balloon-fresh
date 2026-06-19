#!/usr/bin/env python3
"""serial_bridge.py — Bridge between CDC ACM (ESP32-C3) and PTY (for FIPS).

Usage:
    python3 serial_bridge.py /dev/ttyACM0 /tmp/fips_serial_a
    python3 serial_bridge.py /dev/ttyACM1 /tmp/fips_serial_b

Creates a PTY that FIPS opens with tokio_serial. pyserial handles CDC ACM
reads reliably (blocking I/O). PTYs support epoll, so FIPS's async reader
works without modification.
"""
import os
import pty
import select
import serial
import signal
import sys
import time


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <acm_device> <pty_link>", file=sys.stderr)
        sys.exit(1)

    acm_dev = sys.argv[1]
    pty_link = sys.argv[2]

    # Create PTY pair
    master_fd, slave_fd = pty.openpty()
    slave_name = os.ttyname(slave_fd)

    # Set raw mode on both PTY ends (no line buffering, no echo)
    import termios
    attrs = termios.tcgetattr(master_fd)
    attrs[3] = attrs[3] & ~termios.ECHO  # noecho
    termios.tcsetattr(master_fd, termios.TCSANOW, attrs)

    attrs = termios.tcgetattr(slave_fd)
    attrs[3] = attrs[3] & ~termios.ECHO
    termios.tcsetattr(slave_fd, termios.TCSANOW, attrs)

    # Create symlink
    if os.path.islink(pty_link) or os.path.exists(pty_link):
        os.unlink(pty_link)
    os.symlink(slave_name, pty_link)

    # Open ACM with pyserial (blocking I/O — proven to work with CDC ACM)
    acm = serial.Serial(acm_dev, 115200, timeout=0)
    acm.flushInput()
    acm.flushOutput()

    print(f"Bridge: {acm_dev} <-> {pty_link} ({slave_name})", flush=True)

    # Bidirectional bridge loop
    while True:
        try:
            r, _, _ = select.select([acm, master_fd], [], [], 1.0)

            if acm in r:
                data = acm.read(4096)
                if data:
                    os.write(master_fd, data)  # ACM → PTY → FIPS reads

            if master_fd in r:
                data = os.read(master_fd, 4096)
                if data:
                    acm.write(data)  # FIPS writes → PTY → ACM → ESP32
                    acm.flush()

        except (OSError, serial.SerialException) as e:
            print(f"Bridge error: {e}", flush=True)
            # Try to reopen ACM
            try:
                acm.close()
            except:
                pass
            time.sleep(1)
            try:
                acm = serial.Serial(acm_dev, 115200, timeout=0)
                print(f"Reopened {acm_dev}", flush=True)
            except:
                pass


if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    main()
