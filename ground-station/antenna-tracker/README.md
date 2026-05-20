# Antenna Tracker MCP Project

This project integrates an ESP32-based antenna tracker with an MCP server
over Nostr (ContextVM).

---

## ✅ Active Implementation

The currently active MCP server implementation is:

```
ts/src/server.ts
```

It:

- Exposes MCP tools
- Connects to Nostr relays
- Sends commands to ESP32 over serial
- Waits for firmware acknowledgment
- Logs full execution pipeline

Run it with:

```
cd ts
NODE_OPTIONS="--require ./websocket-shim.cjs" npx tsx src/server.ts
```

See:

```
docs/TYPESCRIPT_MCP_SERVER.md
```

---

## ⚠ Rust MCP Server Status

The Rust MCP server (`mcp-antenna/`) builds and connects to relays,
but tools were not successfully listed/exposed via the gateway.

It has been temporarily sidelined in favor of the working
TypeScript implementation.

---

## Firmware

ESP32 firmware located in:

```
antenna-firmware/
```

Recommended build (works on Ubuntu 24.04/25.04):

```
./scripts/build_with_idf_gcc.sh
```

This script:

- Loads the official ESP-IDF environment
- Uses the Espressif GCC toolchain directly
- Avoids the esp-clang compatibility issues on newer Ubuntu versions
- Is currently the most reliable firmware build path

Alternative flash script (uses espflash + Rust toolchain):

```
./scripts/build_and_flash_firmware.sh /dev/ttyUSB1
```

Baud rate: `115200`

---

## Makefile Commands

The project root contains a `Makefile` that wraps common ESP-IDF + Rust
operations for the firmware.

Available targets:

### Setup Environment

```
make setup
```

Loads:

- `~/esp/esp-idf/export.sh`
- `~/export-esp.sh`

Prepares the shell environment for ESP-IDF + Rust builds.

---

### Build Firmware

```
make build
```

Equivalent to:

```
cd antenna-firmware
cargo build
```

Builds the ESP32 firmware (debug profile).

---

### Flash Firmware

```
make flash
```

Equivalent to:

```
cd antenna-firmware
cargo run
```

Builds and flashes the firmware to the ESP32 using the configured
ESP-IDF toolchain.

---

### Monitor Serial Output

```
make monitor
```

Equivalent to:

```
cd antenna-firmware
cargo monitor
```

Opens the ESP-IDF serial monitor.

---

### Clean Build Artifacts

```
make clean
```

Equivalent to:

```
cd antenna-firmware
cargo clean
```

Removes compiled firmware artifacts.

---

⚠️ Note: On Ubuntu 24.04/25.04, the `build_with_idf_gcc.sh` script is
currently the most reliable firmware build method due to esp-clang
compatibility issues.

---

## Architecture

MCP Client → Nostr (ContextVM) → TS MCP Server → Serial → ESP32 Firmware → Motors

---

## Documentation

- `docs/TYPESCRIPT_MCP_SERVER.md`
- `docs/ANTENNA_MCP_COMMANDS.md`
- `docs/SERIAL_INTEGRATION_LEARNINGS.md`
- `docs/WEBSOCKET_RUNTIME_LEARNINGS.md`
- `docs/FIRMWARE_ARCHITECTURE.md`

---

## Current Status

✅ Serial control verified
✅ MCP integration working
✅ Relay connectivity stable
✅ Command acknowledgment implemented

Next improvements:

- Position tracking
- Movement bounds
- Homing routine
- Rust MCP tool exposure fix
