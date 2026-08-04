# TollGate Hardware Board Mutex System

This document describes the hardware mutex system for TollGate, which prevents concurrent access to ESP32 and RP2040 serial ports.

## Overview

The board mutex system uses a combination of:
1. **flock(2)** for cross-process mutual exclusion
2. **Hard device locking** (chmod 000) to physically block raw device access
3. **Sentinel daemons** that monitor process health and auto-release locks
4. **Integration** with pytest fixtures and Make targets

## System Architecture

### Core Components

1. **`balloon-board-lock.py`** - Full-featured lock manager (shared across balloon tracks)
2. **`board-lock.py`** - TollGate-specific wrapper with simplified interface
3. **`board_lock_fixtures.py`** - pytest fixtures for automated testing
4. **`99-rp2040-stable.rules`** - udev rules for persistent device symlinks
5. **Makefile targets** - Command-line integration

### Locking Mechanism

```
Process → acquire() → Open device fd → flock() → Start sentinel → chmod 000
                                                    ↓
Process using device ← sentinel keeps fd open ← can still read/write
                                                    ↓
Other processes → open() → EACCES (permission denied)
```

## Usage

### Command Line

```bash
# Acquire TX board lock
BALLOON_TRACK=tollgate make lock-tx

# Acquire both TX and RX locks
BALLOON_TRACK=tollgate make lock-both

# Acquire ESP32 TX board
BALLOON_TRACK=tollgate make lock-esp32-tx

# Release locks
BALLOON_TRACK=tollgate make lock-release BOARD=tx
BALLOON_TRACK=tollgate make lock-release BOARD=both

# Check lock status
make lock-status

# Verify we hold the lock
BALLOON_TRACK=tollgate make lock-check BOARD=tx
```

### Direct Python Usage

```python
import subprocess
import os

# Set track environment variable
os.environ["BALLOON_TRACK"] = "tollgate"

# Acquire lock
result = subprocess.run([
    "python3", "/path/to/balloon-fresh/tools/board-lock.py",
    "acquire", "tx", "--purpose", "my test", "--timeout", 60
])

if result.returncode == 0:
    print("Lock acquired!")
    
    # Use the board...
    # ...
    
    # Release lock
    subprocess.run([
        "python3", "/path/to/balloon-fresh/tools/board-lock.py",
        "release", "tx"
    ])
```

### Pytest Fixtures

```python
# Import the fixtures
from tests.board_lock_fixtures import locked_tx, locked_rx, locked_both

# Test with TX board locked
def test_tx_communication(locked_tx):
    port = locked_tx  # /dev/ttyACM2 or similar
    # Test code here - port is guaranteed to be locked
    
# Test with both boards locked
def test_synchronized_test(locked_both):
    tx_port, rx_port = locked_both
    # Both ports are locked and ready to use
```

## Available Boards

### RP2040 Boards
- **tx**: RP2040 TX board (serial: F242D)
- **rx**: RP2040 RX board (serial: 8332)

### ESP32 Boards  
- **esp32-tx**: ESP32-S3 TX board (MAC: 94:a9:90:2e:37:7c)
- **esp32-rx**: ESP32-S3 RX board (MAC: fc:01:2c:c5:50:50)

### Board Groups
- **both**: TX + RP2040 boards
- **esp32-both**: Both ESP32 boards

## UDEV Rules for Stable Symlinks

The system includes udev rules that create persistent device symlinks:

```bash
# Install udev rules
sudo cp /home/c03rad0r/repos/balloon-fresh/rules/99-rp2040-stable.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger

# Use stable symlinks in tests
with serial.Serial("/dev/rp2040-tx", 115200) as ser:
    # ...
```

This solves the problem of ports changing on every USB replug.

## pytest Integration

### Markers

```bash
# Run only hardware tests with locking
pytest -m "hardware" tests/test_board_lock.py

# Run all tests (unit + hardware)
pytest tests/
```

### Fixture Scopes

- **`board_lock`** (session): Lock manager for the entire test session
- **`locked_tx`** (function): Acquires TX board lock for a single test
- **`locked_rx`** (function): Acquires RX board lock for a single test  
- **`locked_both`** (function): Acquires both board locks for a single test
- **`locked_esp32_tx`** (function): Acquires ESP32 TX board lock

### Automatic Cleanup

All fixtures automatically release locks when done, even if tests fail:

```python
def test_failure(locked_tx):
    port = locked_tx
    # This test fails...
    assert False, "Intentional failure"
    # Lock is automatically released despite the failure
```

## Error Handling

### Common Error Scenarios

1. **Lock timeout**: `acquire()` returns exit code 1 after timeout
2. **Permission denied**: Hard device lock blocks raw access
3. **Board not found**: `find_port_by_serial()` returns None
4. **Process crash**: Sentinels detect process death and auto-release

### Debug Commands

```bash
# Check lock status
make lock-status

# Monitor running sentinels
ps aux | grep 'balloon-board-lock' | grep -v grep

# Check theft log
cat ~/.hermes/peripheral_locks/board-lock-theft.log

# Test device permissions
ls -la /dev/ttyACM*
```

## Security Features

### Theft Protection

- **Sentinel daemons** trap SIGTERM and log theft attempts
- **Only SIGKILL** can forcibly release a lock
- **Audit logging** tracks all lock acquisition/release events
- **Track identification** prevents cross-track interference

### Hard Device Locking

- **chmod 000** blocks all raw device access
- **Sentinels keep file descriptors open** for continued access
- **Automatic restoration** on system reboot/crash

## Integration Examples

### Makefile Target for Testing

```makefile
test-with-locks: ## Run hardware tests with automatic locking
	make lock-both
	pytest -m "hardware" tests/
	make lock-release BOARD=both
```

### Test Runner Script

```python
#!/usr/bin/env python3
"""Test runner with board locking"""

import subprocess
import os
import sys

def run_locked_test():
    os.environ["BALLOON_TRACK"] = "tollgate"
    
    # Acquire locks
    subprocess.run([
        "python3", "tools/board-lock.py", "acquire", "both", 
        "--purpose", "test run", "--timeout", 60
    ], check=True)
    
    try:
        # Run tests
        subprocess.run(["pytest", "-m", "hardware", "tests/"], check=True)
    finally:
        # Always release locks
        subprocess.run([
            "python3", "tools/board-lock.py", "release", "both"
        ])

if __name__ == "__main__":
    run_locked_test()
```

## Troubleshooting

### Lock Not Acquired

1. **Check status**: `make lock-status`
2. **Verify track**: `echo $BALLOON_TRACK`
3. **Check permissions**: `ls -la ~/.hermes/peripheral_locks/`
4. **Kill orphaned sentinels**: `kill $(pgrep -f balloon-board-lock)`

### Device Permission Issues

1. **Check udev rules**: `sudo udevadm info -q property -n /dev/ttyACM0`
2. **Reload rules**: `sudo udevadm control --reload-rules && sudo udevadm trigger`
3. **Check group membership**: `groups $USER`

### Board Not Found

1. **Check connections**: `make identify-ports`
2. **Check USB devices**: `lsusb | grep -E "(2e8a|303a)"`
3. **Check udev properties**: `udevadm info -q property -n /dev/ttyACM0`

## Performance Considerations

- **Lock acquisition time**: ~2-5 seconds per board
- **Overhead**: Minimal - flock system call is fast
- **Memory usage**: ~10MB per sentinel process
- **CPU usage**: Negligible (sleeps between health checks)

## Best Practices

1. **Always use fixtures** in pytest - don't manually acquire locks
2. **Keep lock scope minimal** - acquire only when needed, release immediately
3. **Handle timeouts gracefully** - don't assume locks will be available
4. **Test both locked and unlocked scenarios** for robustness
5. **Monitor lock status** during long-running tests
6. **Use stable symlinks** (`/dev/rp2040-tx`) instead of dynamic ports