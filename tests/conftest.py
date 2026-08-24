"""
conftest.py — pytest fixtures for balloon walk test firmware.

Fixtures:
  flash_tx    — Build + flash TX board, wait for boot, yield port
  flash_rx    — Build + flash RX board, wait for boot, yield port
  flash_both  — Flash both boards, yield (tx_port, rx_port)
  serial_tx   — Find TX board port (no flash), yield port device path
  serial_rx   — Find RX board port (no flash), yield port device path

Board serial numbers are defined here — change if boards are swapped.
"""
import os
import re
import time
import subprocess
import pytest

# Board identification
TX_SERIAL = "E663B035977F242D"
RX_SERIAL = "E663B035973B8332"
BAUD = 115200
BOOT_WAIT = 10  # seconds to wait after flash for board to boot
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_port(serial_substr: str, timeout: float = 10.0) -> str | None:
    """Find /dev/ttyACM* port by serial number substring."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        for i in range(10):
            port = f"/dev/ttyACM{i}"
            if not os.path.exists(port):
                continue
            try:
                result = subprocess.run(
                    ["udevadm", "info", "-q", "property", "-n", port],
                    capture_output=True, text=True, timeout=3
                )
                if serial_substr in result.stdout:
                    return port
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue
        time.sleep(0.5)
    return None


def flash_board(env_name: str, serial_substr: str) -> str:
    """Build + flash a board, wait for boot, return port path."""
    fw_dir = os.path.join(REPO_ROOT, "firmware", "rp2040")
    port = find_port(serial_substr, timeout=5)
    if not port:
        pytest.skip(f"Board with serial {serial_substr} not found")

    result = subprocess.run(
        ["pio", "run", "-e", env_name, "-t", "upload", "--upload-port", port],
        cwd=fw_dir, capture_output=True, text=True, timeout=120
    )
    if result.returncode != 0:
        pytest.fail(f"Flash failed for {env_name}: {result.stderr[-500:]}")

    time.sleep(BOOT_WAIT)
    port = find_port(serial_substr, timeout=10)
    if not port:
        pytest.fail(f"Board {serial_substr} disappeared after flash")
    return port


def read_serial(port: str, duration: float = 5.0) -> list[str]:
    """Read lines from serial port for given duration. Returns list of lines."""
    import serial
    lines = []
    try:
        with serial.Serial(port, BAUD, timeout=1) as ser:
            deadline = time.time() + duration
            buffer = b""
            while time.time() < deadline:
                chunk = ser.read(1024)
                if chunk:
                    buffer += chunk
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        lines.append(line.decode("ascii", errors="replace").strip())
    except Exception as e:
        pytest.fail(f"Serial read error on {port}: {e}")
    return lines


# ── Flash Fixtures ──

@pytest.fixture
def flash_tx():
    """Flash TX board and return its port."""
    port = flash_board("rp2040-sweep-tx", TX_SERIAL)
    yield port


@pytest.fixture
def flash_rx():
    """Flash RX board and return its port."""
    port = flash_board("rp2040-sweep-rx", RX_SERIAL)
    yield port


@pytest.fixture
def flash_both(flash_tx, flash_rx):
    """Flash both boards. Returns (tx_port, rx_port)."""
    yield (flash_tx, flash_rx)


# ── Serial-Only Fixtures (no flash) ──

@pytest.fixture
def serial_tx():
    """Find TX board port (no flash). Yield port path."""
    port = find_port(TX_SERIAL, timeout=5)
    if not port:
        pytest.skip(f"TX board not found")
    yield port


@pytest.fixture
def serial_rx():
    """Find RX board port (no flash). Yield port path."""
    port = find_port(RX_SERIAL, timeout=5)
    if not port:
        pytest.skip(f"RX board not found")
    yield port


# ── Helper Functions ──

def parse_phase_result(line: str) -> dict | None:
    """Parse a PHASE_RESULT line into a dict."""
    if not line.startswith("PHASE_RESULT"):
        return None
    parts = line.split()
    result = {"phase": int(parts[1]), "mode": parts[2]}
    for part in parts[3:]:
        if "=" in part:
            k, v = part.split("=", 1)
            try:
                result[k] = float(v)
            except ValueError:
                result[k] = v
    return result


def parse_beacon(line: str) -> dict | None:
    """Parse a BEACON line into a dict."""
    if not line.startswith("BEACON"):
        return None
    parts = line.split()
    result = {}
    for part in parts[1:]:
        if "=" in part:
            k, v = part.split("=", 1)
            try:
                result[k] = int(v)
            except ValueError:
                result[k] = v
    return result


def parse_gps_unix(line: str) -> int | None:
    """Extract unix timestamp from GPS_UNIX line."""
    if "GPS_UNIX" not in line:
        return None
    m = re.search(r'unix=(\d+)', line)
    return int(m.group(1)) if m else None
