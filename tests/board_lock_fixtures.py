"""
Board lock fixtures for TollGate hardware testing.
These fixtures use the hardware mutex system to prevent concurrent access to serial ports.
"""

import pytest
import os
import subprocess
from pathlib import Path


def find_port_by_serial(serial_substr: str, timeout: float = 10.0) -> str | None:
    """Find /dev/ttyACM* port by serial number substring."""
    import time
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


@pytest.fixture(scope="session")
def board_lock():
    """Session-scoped board lock manager."""
    import subprocess
    import time
    
    # Define TollGate boards
    BOARDS = {
        "tx": {"serial": "E663B035977F242D", "name": "RP2040 TX"},
        "rx": {"serial": "E663B035973B8332", "name": "RP2040 RX"}, 
        "esp32-tx": {"serial": "94:a9:90:2e:37:7c", "name": "ESP32-S3 TX"},
        "esp32-rx": {"serial": "fc:01:2c:c5:50:50", "name": "ESP32-S3 RX"},
    }
    
    locked_boards = {}
    
    def acquire_board(board_name: str, purpose: str = "testing", timeout: int = 60):
        """Acquire lock for a specific board."""
        if board_name not in BOARDS:
            raise ValueError(f"Unknown board: {board_name}")
            
        board = BOARDS[board_name]
        
        # Set environment for the lock script
        env = os.environ.copy()
        env["BALLOON_TRACK"] = "tollgate"
        
        try:
            # Run the lock script
            result = subprocess.run([
                "python3", 
                str(Path(__file__).parent.parent / "tools" / "board-lock.py"),
                "acquire", board_name,
                "--purpose", purpose,
                "--timeout", str(timeout)
            ], env=env, capture_output=True, text=True, timeout=timeout + 5)
            
            if result.returncode == 0:
                # Verify the lock was acquired
                verify_result = subprocess.run([
                    "python3",
                    str(Path(__file__).parent.parent / "tools" / "board-lock.py"), 
                    "check", board_name
                ], env=env, capture_output=True, text=True)
                
                if verify_result.returncode == 0:
                    locked_boards[board_name] = {
                        "purpose": purpose,
                        "locked_at": time.time()
                    }
                    print(f"LOCKED: {board['name']} ({board_name}) for {purpose}")
                    return True
                else:
                    print(f"LOCK VERIFY FAILED: {board_name}")
                    return False
            else:
                print(f"LOCK ACQUIRE FAILED: {board_name} - {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print(f"LOCK TIMEOUT: {board_name}")
            return False
        except Exception as e:
            print(f"LOCK ERROR: {board_name} - {e}")
            return False
    
    def release_board(board_name: str):
        """Release lock for a specific board."""
        if board_name not in locked_boards:
            print(f"NOT LOCKED: {board_name}")
            return True
            
        env = os.environ.copy()
        env["BALLOON_TRACK"] = "tollgate"
        
        try:
            result = subprocess.run([
                "python3",
                str(Path(__file__).parent.parent / "tools" / "board-lock.py"),
                "release", board_name
            ], env=env, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                del locked_boards[board_name]
                print(f"RELEASED: {board_name}")
                return True
            else:
                print(f"RELEASE FAILED: {board_name} - {result.stderr}")
                return False
                
        except Exception as e:
            print(f"RELEASE ERROR: {board_name} - {e}")
            return False
    
    def release_all():
        """Release all locked boards."""
        for board_name in list(locked_boards.keys()):
            release_board(board_name)
    
    # Cleanup after all tests
    yield {
        "acquire": acquire_board,
        "release": release_board, 
        "release_all": release_all,
        "locked_boards": locked_boards
    }
    
    # Cleanup
    release_all()


@pytest.fixture
def locked_tx(board_lock):
    """Acquire lock for TX board, yield port path."""
    if not board_lock["acquire"]("tx", "pytest TX test"):
        pytest.skip("TX board lock acquisition failed")
        
    port = find_port_by_serial("E663B035977F242D")
    if not port:
        board_lock["release"]("tx")
        pytest.skip("TX board not found")
        
    try:
        yield port
    finally:
        board_lock["release"]("tx")


@pytest.fixture  
def locked_rx(board_lock):
    """Acquire lock for RX board, yield port path."""
    if not board_lock["acquire"]("rx", "pytest RX test"):
        pytest.skip("RX board lock acquisition failed")
        
    port = find_port_by_serial("E663B035973B8332")
    if not port:
        board_lock["release"]("rx")
        pytest.skip("RX board not found")
        
    try:
        yield port
    finally:
        board_lock["release"]("rx")


@pytest.fixture
def locked_both(board_lock):
    """Acquire locks for both TX and RX boards, yield (tx_port, rx_port)."""
    if not board_lock["acquire"]("tx", "pytest both test"):
        pytest.skip("TX board lock acquisition failed")
        
    if not board_lock["acquire"]("rx", "pytest both test"):  
        board_lock["release"]("tx")
        pytest.skip("RX board lock acquisition failed")
        
    tx_port = find_port_by_serial("E663B035977F242D")
    rx_port = find_port_by_serial("E663B035973B8332")
    
    if not tx_port or not rx_port:
        board_lock["release_all"]()
        pytest.skip("One or both boards not found")
        
    try:
        yield (tx_port, rx_port)
    finally:
        board_lock["release_all"]()


@pytest.fixture
def locked_esp32_tx(board_lock):
    """Acquire lock for ESP32 TX board, yield port path."""
    if not board_lock["acquire"]("esp32-tx", "pytest ESP32 TX test"):
        pytest.skip("ESP32 TX board lock acquisition failed")
        
    # Find ESP32 by MAC (need to check udev properties)
    port = None
    for i in range(10):
        test_port = f"/dev/ttyACM{i}"
        if not os.path.exists(test_port):
            continue
        try:
            result = subprocess.run(
                ["udevadm", "info", "-q", "property", "-n", test_port],
                capture_output=True, text=True, timeout=3
            )
            if "94:a9:90:2e:37:7c" in result.stdout:
                port = test_port
                break
        except:
            continue
            
    if not port:
        board_lock["release"]("esp32-tx")
        pytest.skip("ESP32 TX board not found")
        
    try:
        yield port
    finally:
        board_lock["release"]("esp32-tx")