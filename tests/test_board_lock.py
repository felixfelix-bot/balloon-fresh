"""
Test the hardware board lock fixtures.
This demonstrates the proper way to use the locking mechanism in pytest tests.
"""

import pytest
import time
import serial
import subprocess
from pathlib import Path


def test_lock_acquisition_release(locked_tx):
    """Test that we can acquire and release TX board lock."""
    port = locked_tx
    
    # Try to open the port (should work since we hold the lock)
    try:
        with serial.Serial(port, 115200, timeout=1) as ser:
            # Send a simple command and read response
            ser.write(b"PING\n")
            time.sleep(0.1)
            response = ser.read(100).decode().strip()
            print(f"TX response: {response}")
    except Exception as e:
        pytest.fail(f"Failed to communicate with TX board: {e}")


def test_lock_concurrent_access_serial():
    """Test that concurrent access to the same board is prevented."""
    from board_lock_fixtures import find_port_by_serial
    
    tx_port = find_port_by_serial("E663B035977F242D")
    if not tx_port:
        pytest.skip("TX board not found")
    
    # Try to open the port without the lock (should fail due to chmod 000)
    try:
        with serial.Serial(tx_port, 115200, timeout=1) as ser:
            # This should not reach here
            pytest.fail("Should not be able to open port without lock")
    except serial.SerialException as e:
        # Expected: permission denied due to hard device lock
        if "Permission denied" in str(e):
            print(f"Correctly blocked access: {e}")
        else:
            pytest.fail(f"Unexpected error: {e}")


def test_rx_board_communication(locked_rx):
    """Test RX board communication with lock held."""
    port = locked_rx
    
    try:
        with serial.Serial(port, 115200, timeout=1) as ser:
            # Send a ping to verify communication
            ser.write(b"PING\n")
            time.sleep(0.1)
            response = ser.read(100).decode().strip()
            print(f"RX response: {response}")
            
            # Verify we got some response (device is alive)
            assert response != "", "Empty response from RX board"
            
    except Exception as e:
        pytest.fail(f"Failed to communicate with RX board: {e}")


def test_both_boards_synchronized(locked_both):
    """Test synchronized communication between TX and RX boards."""
    tx_port, rx_port = locked_both
    
    try:
        # Open both ports
        with serial.Serial(tx_port, 115200, timeout=1) as tx_ser, \
             serial.Serial(rx_port, 115200, timeout=1) as rx_ser:
            
            # Send a test packet from TX
            test_packet = b"SYNC_TEST 12345\n"
            tx_ser.write(test_packet)
            time.sleep(0.1)
            
            # Read response from TX (echo)
            tx_response = tx_ser.read(100).decode().strip()
            print(f"TX echo: {tx_response}")
            
            # RX should not receive anything (no radio link in this test)
            rx_response = rx_ser.read(100).decode().strip()
            print(f"RX received: {rx_response}")
            
    except Exception as e:
        pytest.fail(f"Failed synchronized test: {e}")


def test_lock_status():
    """Test the lock status functionality."""
    try:
        result = subprocess.run([
            "python3", 
            str(Path(__file__).parent.parent / "tools" / "board-lock.py"),
            "status"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("Lock status:")
            print(result.stdout)
        else:
            pytest.fail(f"Lock status failed: {result.stderr}")
            
    except Exception as e:
        pytest.fail(f"Failed to get lock status: {e}")


def test_lock_check_functionality():
    """Test that lock check works correctly."""
    try:
        # Check if we can access the lock status for TX
        result = subprocess.run([
            "python3",
            str(Path(__file__).parent.parent / "tools" / "board-lock.py"), 
            "check", "tx"
        ], capture_output=True, text=True, timeout=10)
        
        # Check should return 1 (not held by us) or 0 (held by us)
        assert result.returncode in [0, 1], f"Lock check returned invalid code: {result.returncode}"
        print(f"Lock check result: {result.returncode}")
        print(f"Lock output: {result.stdout}")
        
    except Exception as e:
        pytest.fail(f"Failed to check lock status: {e}")


@pytest.mark.hardware
def test_with_esp32_lock(locked_esp32_tx):
    """Test ESP32 board locking (requires actual hardware)."""
    port = locked_esp32_tx
    
    try:
        with serial.Serial(port, 115200, timeout=2) as ser:
            # ESP32 specific test - check boot message
            ser.write(b"\n")
            time.sleep(0.5)
            response = ser.read(500).decode().strip()
            print(f"ESP32 boot response: {response[:200]}...")
            
            # Look for typical ESP32 boot patterns
            assert len(response) > 10, "Empty response from ESP32"
            
    except Exception as e:
        pytest.fail(f"Failed ESP32 communication: {e}")


class TestBoardLockIntegration:
    """Integration test class demonstrating proper lock usage."""
    
    def test_manual_lock_pattern(self):
        """Test manual lock acquisition/release pattern."""
        import subprocess
        import time
        
        # Manual lock acquisition
        result = subprocess.run([
            "python3", str(Path(__file__).parent.parent / "tools" / "board-lock.py"),
            "acquire", "tx", "--purpose", "manual test", "--timeout", "30"
        ], capture_output=True, text=True, timeout=35)
        
        if result.returncode != 0:
            pytest.fail(f"Failed to acquire lock: {result.stderr}")
        
        try:
            # Verify lock is held
            check_result = subprocess.run([
                "python3", str(Path(__file__).parent.parent / "tools" / "board-lock.py"),
                "check", "tx"
            ], capture_output=True, text=True)
            
            assert check_result.returncode == 0, "Lock verification failed"
            
            # Use the port
            tx_port = None
            for i in range(10):
                test_port = f"/dev/ttyACM{i}"
                if Path(test_port).exists():
                    try:
                        with serial.Serial(test_port, 115200, timeout=1) as ser:
                            ser.write(b"PING\n")
                            time.sleep(0.1)
                            response = ser.read(100).decode().strip()
                            if response:
                                tx_port = test_port
                                break
                    except:
                        continue
                        
            if not tx_port:
                pytest.skip("TX board not found for manual test")
            
            print(f"Manual lock test successful on {tx_port}")
            
        finally:
            # Release lock
            release_result = subprocess.run([
                "python3", str(Path(__file__).parent.parent / "tools" / "board-lock.py"),
                "release", "tx"
            ], capture_output=True, text=True)
            
            assert release_result.returncode == 0, "Failed to release lock"