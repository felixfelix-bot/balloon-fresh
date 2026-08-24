"""Pytest fixtures for balloon range test hardware tests.

Per ADR-020: fixtures flash boards, setup/teardown, handle port detection.
"""
import os
import re
import time
import signal
import subprocess
import pytest
import serial

# Board serial IDs (last 4 chars of USB serial)
TX_SERIAL = "242D"
RX_SERIAL = "8332"
BAUD = 115200


def find_port(serial_suffix):
    """Find /dev/ttyACM* by board serial ID suffix."""
    for i in range(10):
        dev = f"/dev/ttyACM{i}"
        if not os.path.exists(dev):
            continue
        try:
            result = subprocess.run(
                ["udevadm", "info", "-q", "property", "-n", dev],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.splitlines():
                if "ID_SERIAL_SHORT=" in line:
                    val = line.split("=", 1)[1]
                    if val.endswith(serial_suffix):
                        return dev
        except Exception:
            pass
    return None


def send_command(port, cmd, timeout=2):
    """Send a serial command to a board."""
    try:
        with serial.Serial(port, BAUD, timeout=timeout) as s:
            s.write(f"{cmd}\n".encode())
            s.flush()
            time.sleep(0.5)
            return s.read(4096).decode(errors='replace')
    except Exception as e:
        return f"ERROR: {e}"


def read_output(port, duration_s=10, filter_prefix=None):
    """Read serial output for a duration. Optionally filter by prefix."""
    lines = []
    try:
        with serial.Serial(port, BAUD, timeout=duration_s) as s:
            start = time.time()
            while time.time() - start < duration_s:
                line = s.readline().decode(errors='replace').strip()
                if line:
                    if filter_prefix is None or line.startswith(filter_prefix):
                        lines.append(line)
    except Exception as e:
        lines.append(f"ERROR: {e}")
    return lines


def flash_board(serial_suffix, uf2_path):
    """Flash a board via BOOTSEL mode."""
    port = find_port(serial_suffix)
    if not port:
        pytest.fail(f"Board {serial_suffix} not found")

    # Enter BOOTSEL
    try:
        s = serial.Serial(port, 1200)
        s.setDTR(False)
        time.sleep(0.1)
        s.close()
    except Exception:
        pass
    time.sleep(3)

    # Find RPI-RP2 disk
    result = subprocess.run(["lsblk", "-ln", "-o", "NAME,LABEL"],
                          capture_output=True, text=True, timeout=5)
    disk = None
    for line in result.stdout.splitlines():
        if "RPI-RP2" in line:
            disk = line.split()[0]
            break

    if not disk:
        pytest.fail(f"RPI-RP2 disk not found for {serial_suffix}")

    # Mount + copy + unmount
    subprocess.run(["sudo", "mount", "-o", f"uid={os.getuid()},gid={os.getgid()}",
                    f"/dev/{disk}1", "/tmp/rp2040-flash"], timeout=10)
    subprocess.run(["cp", uf2_path, "/tmp/rp2040-flash/"], timeout=10)
    subprocess.run(["sync"], timeout=10)
    subprocess.run(["sudo", "umount", "/tmp/rp2040-flash"], timeout=10)
    time.sleep(5)


@pytest.fixture
def tx_port():
    """Find TX board. Do NOT flash — just find and yield port."""
    port = find_port(TX_SERIAL)
    if not port:
        pytest.skip(f"TX board ({TX_SERIAL}) not connected")
    yield port


@pytest.fixture
def rx_port():
    """Find RX board. Do NOT flash — just find and yield port."""
    port = find_port(RX_SERIAL)
    if not port:
        pytest.skip(f"RX board ({RX_SERIAL}) not connected")
    yield port


@pytest.fixture
def both_ports(tx_port, rx_port):
    """Both boards found. Sync RX with laptop time."""
    epoch = int(time.time())
    send_command(rx_port, f"SET_TIME {epoch}")
    send_command(rx_port, "SET_INTERLEAVE 1")
    time.sleep(5)  # Wait for phase computation
    yield (tx_port, rx_port)


@pytest.fixture
def synced_both(both_ports):
    """Both boards synced with the SAME epoch."""
    tx_port, rx_port = both_ports
    epoch = int(time.time())
    send_command(tx_port, f"SET_TIME {epoch}")
    send_command(rx_port, f"SET_TIME {epoch}")
    time.sleep(15)  # Wait for phase alignment
    yield (tx_port, rx_port)
