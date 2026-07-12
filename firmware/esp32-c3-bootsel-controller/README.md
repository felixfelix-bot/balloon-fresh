# ESP32 RP2040 BOOTSEL Controller

## Overview

This ESP32-C3 firmware provides complete programmatic control over RP2040 BOOTSEL mode, enabling automated testing, recovery, and firmware flashing without human intervention. This is part of the balloon board infrastructure for continuous testing.

## Features

- ✅ **Automated BOOTSEL Control**: Programmatic entry into BOOTSEL mode
- ✅ **UART Communication**: Bidirectional communication with RP2040
- ✅ **Heartbeat Monitoring**: Continuous health monitoring with watchdog recovery
- ✅ **Self-Recovery**: Automatic detection and recovery from RP2040 crashes
- ✅ **Firmware Flashing**: Automated RX/TX firmware deployment
- ✅ **Hardware Integration**: Direct pin control with proper electrical isolation

## Hardware Configuration

### Pin Mapping (RX Board - 8332)
| ESP32-C3 Pin | RP2040 Pin | Function | Pull-up |
|-------------|------------|----------|---------|
| GPIO1 (D1) | RUN (pin 30) | Reset control | 10kΩ to 3V3 |
| GPIO8 (D8) | GP0/BOOTSEL (pin 1) | BOOTSEL control | 10kΩ to 3V3 |
| GPIO20 (RX) | GP21 (TX) | UART receive | - |
| GPIO21 (TX) | GP20 (RX) | UART transmit | - |
| GND | GND | Common ground | - |

### Wiring Diagram
```
ESP32-C3                  RP2040
┌─────────────┐          ┌─────────────┐
│ GPIO1 (D1)  ├──────────►│ RUN         │
│ GPIO8 (D8)  ├──────────►│ BOOTSEL     │
│ GPIO20 (RX) ├──────────►│ GP21 (TX)   │
│ GPIO21 (TX) ├──────────►│ GP20 (RX)   │
│ GND         ├──────────►│ GND         │
└─────────────┘          └─────────────┘
```

**Important**: Use 1kΩ series resistors on GPIO1→RUN and GPIO8→BOOTSEL, with 10kΩ pull-up resistors to 3V3 on the RP2040 side.

## Build & Flash Instructions

### Prerequisites
```bash
# Install PlatformIO
pip install platformio

# Clone repository
cd ~/repos/balloon-fresh/firmware/esp32-c3-bootsel-controller
```

### Build Firmware
```bash
pio run -e esp32-c3-bootsel-controller
```

### Flash ESP32
```bash
pio run -e esp32-c3-bootsel-controller -t upload
```

### Monitor Serial Output
```bash
pio device monitor
```

## Usage

### Basic Testing
```bash
# Run test suite
python3 test_bootsel_controller.py

# Test specific commands
echo "BOOTSEL" > /dev/ttyACM1
echo "RESET" > /dev/ttyACM1
echo "STATUS" > /dev/ttyACM1
```

### Enhanced Board Watcher
```bash
# Start continuous monitoring with auto-recovery
./enhanced_board_watcher.sh monitor

# One-time firmware flash
./enhanced_board_watcher.sh flash-rx
./enhanced_board_watcher.sh flash-tx

# Check system status
./enhanced_board_watcher.sh status

# Manual control
./enhanced_board_watcher.sh reset
./enhanced_board_watcher.sh bootsel
```

## Protocol Reference

### Heartbeat Packet Format
```
HB rx=<count> lat=<ms> gaps=<count> time=<timestamp>\r\n
```

Example: `HB rx=8234 lat=12 gaps=3 time=1712345678\r\n`

### Control Commands
| Command | Description | Expected Response |
|---------|-------------|-------------------|
| `BOOTSEL` | Force BOOTSEL mode | `OK\r\n` |
| `RESET` | Reset RP2040 | `OK\r\n` |
| `FLASH_TX` | Flash TX firmware | `FLASHING\r\n` → `DONE\r\n` |
| `FLASH_RX` | Flash RX firmware | `FLASHING\r\n` → `DONE\r\n` |
| `STATUS` | Get system status | `STATUS:running\r\n` |

### Firmware Flashing Protocol
```
ESP32 → RP2040: FLASH_RX
RP2040 → ESP32: FLASHING
ESP32 → RP2040: [UF2 data blocks]
RP2040 → ESP32: DONE
```

## Integration with Balloon Infrastructure

### Continuous Monitoring Setup
```bash
# Create systemd service for 24/7 monitoring
sudo tee /etc/systemd/system/balloon-board-watcher.service > /dev/null <<EOF
[Unit]
Description=Balloon Board Watcher with ESP32 Controller
After=network.target

[Service]
Type=simple
User=c03rad0r
WorkingDirectory=/home/c03rad0r/repos/balloon-fresh/firmware/esp32-c3-bootsel-controller
ExecStart=/home/c03rad0r/repos/balloon-fresh/firmware/esp32-c3-bootsel-controller/enhanced_board_watcher.sh monitor
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable balloon-board-watcher
sudo systemctl start balloon-board-watcher

# Check status
sudo systemctl status balloon-board-watcher
```

### Hardware Validation
```bash
# Step 1: Verify ESP32 is connected and responsive
python3 -c "
import serial
s = serial.Serial('/dev/ttyACM1', 115200, timeout=1)
s.write(b'STATUS\n')
print(s.readline().decode())
s.close()
"

# Step 2: Test BOOTSEL control
python3 -c "
import serial
s = serial.Serial('/dev/ttyACM1', 115200, timeout=1)
s.write(b'BOOTSEL\n')
print('BOOTSEL response:', s.readline().decode())
s.write(b'RESET\n')
print('RESET response:', s.readline().decode())
s.close()
"

# Step 3: Verify UART communication
python3 -c "
import serial
import time
s = serial.Serial('/dev/ttyACM1', 115200, timeout=1)
print('Monitoring heartbeats for 10 seconds...')
start = time.time()
while time.time() - start < 10:
    if s.in_waiting:
        line = s.readline().decode().strip()
        if line.startswith('HB rx='):
            print(f'Heartbeat: {line}')
s.close()
"
```

## Troubleshooting

### Common Issues

#### 1. ESP32 Cannot Control RP2040
**Symptoms**: No response to BOOTSEL/RESET commands
**Solutions**:
- Check wiring: GPIO1→RUN, GPIO8→BOOTSEL with correct pull-ups
- Verify 3V3 power to both boards
- Check ground connection
- Ensure 1kΩ series resistors are in place

#### 2. UART Communication Issues
**Symptoms**: No heartbeat data, garbled output
**Solutions**:
- Verify TX→RX, RX→TX cross-connection
- Check baud rate (115200)
- Ensure both boards have common ground
- Check for noise on UART lines

#### 3. BOOTSEL Not Working
**Symptoms**: RP2040 doesn't enter BOOTSEL mode
**Solutions**:
- Verify BOOTSEL pin is pulled LOW when commanded
- Check RUN pin reset pulse timing (10ms pulse, 50ms delay)
- Monitor with oscilloscope if available
- Check RP2040 is not already in BOOTSEL mode

### Debug Commands
```bash
# View ESP32 logs
pio device monitor

# Check UART communication
echo "STATUS" > /dev/ttyACM1
head -1 /dev/ttyACM1

# Test manual BOOTSEL
python3 -c "
import serial
s = serial.Serial('/dev/ttyACM1', 115200)
s.write(b'BOOTSEL\n')
print(s.readline().decode())
s.close()
"

# Monitor system logs
journalctl -u balloon-board-watcher -f
```

## Testing & Validation

### Automated Test Suite
```bash
# Run all tests
python3 test_bootsel_controller.py

# Test with specific port
python3 test_bootsel_controller.py --port /dev/ttyACM2 --baudrate 115200
```

### Hardware Validation Checklist
- [ ] ESP32-C3 powered and connected via USB
- [ ] RP2040 powered and connected to ESP32
- [ ] GPIO1→RUN connection with 1kΩ resistor
- [ ] GPIO8→BOOTSEL connection with 1kΩ resistor
- [ ] 10kΩ pull-up resistors on RP2040 RUN and BOOTSEL pins
- [ ] UART cross-connected (ESP32 TX→RP2040 RX, ESP32 RX→RP2040 TX)
- [ ] Common ground between all boards
- [ ] ESP32 firmware flashed successfully
- [ ] Basic commands (BOOTSEL, RESET, STATUS) work
- [ ] Heartbeat monitoring functional
- [ ] Recovery sequence tested and working

## Deployment

### Production Setup
1. **Physical Installation**: Secure ESP32-C3 and RP2040 boards with proper strain relief
2. **Power Management**: Ensure stable 3V3 power supply with adequate current
3. **Service Configuration**: Enable balloon-board-watcher service for 24/7 monitoring
4. **Monitoring**: Set up log rotation and monitoring for system health
5. **Backup**: Keep spare ESP32-C3 boards programmed and ready

### Maintenance
- Check system logs weekly: `journalctl -u balloon-board-watcher --since "1 week ago"`
- Test recovery sequence monthly
- Monitor RP2040 performance and heartbeats
- Keep firmware updated and tested

## Version History

### v1.0.0 (Current)
- ✅ Basic BOOTSEL control
- ✅ UART communication
- ✅ Heartbeat monitoring
- ✅ Recovery sequence
- ✅ Enhanced board watcher integration

### Planned Features (v1.1.0)
- 🔄 OTA firmware updates
- 🔄 Multiple RP2040 board support
- 🔄 Enhanced diagnostics
- 🔄 Performance metrics collection

## Support

For issues, questions, or contributions, please check:
- Repository: `~/repos/balloon-fresh/firmware/esp32-c3-bootsel-controller`
- Documentation: `~/repos/balloon-fresh/docs/`
- Hardware connections: `~/repos/balloon-fresh/HARDWARE_CONNECTIONS.md`

---

**Implementation Status**: ✅ Phase 1 Complete | 🔄 Phase 2 (Integration) In Progress | ⏳ Phase 3 (Production) Planned