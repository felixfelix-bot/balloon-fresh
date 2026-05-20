# Ground Station

Consolidated ground station software for the pico balloon tracker.

## Components

### `ground_station.py` — Telemetry Decoder
Receives and decodes 24-byte telemetry packets over serial from the balloon tracker.
```bash
pip install pyserial
python ground_station.py /dev/ttyUSB0 -b 115200
```

### `antenna-tracker/` — Motorized Antenna Tracker
ESP32-based azimuth/elevation antenna tracker with MCP (Model Context Protocol) control via Nostr.

#### Architecture
```
MCP Client → Nostr (ContextVM) → TS MCP Server → Serial → ESP32 Firmware → 28BYJ-48 Stepper Motors
```

#### Firmware (ESP32, Rust/ESP-IDF)
- `antenna-tracker/antenna-firmware/` — Rust ESP-IDF firmware for ESP32
  - Controls 2x 28BYJ-48 stepper motors (azimuth + elevation)
  - Accepts `AZ <steps>` and `EL <steps>` commands over serial
  - Build: `./scripts/build_with_idf_gcc.sh`

#### Alternative Firmware (Arduino)
- `antenna-tracker/antenna_tracker_usb.ino` — Arduino sketch, same serial protocol

#### MCP Server (TypeScript)
- `antenna-tracker/ts/` — TypeScript MCP server
  - Exposes `move_antenna` and `echo` tools over Nostr via ContextVM
  - Controls ESP32 via serial port
  - Run: `cd ts && NODE_OPTIONS="--require ./websocket-shim.cjs" npx tsx src/server.ts`

#### Rust MCP Server (experimental)
- `antenna-tracker/mcp-antenna/` — Rust MCP server (builds but tool listing not working via gateway)

#### Docs
- `antenna-tracker/docs/` — Pinout, wiring diagrams, MCP setup, troubleshooting
