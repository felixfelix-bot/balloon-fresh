# Antenna MCP Commands

This document describes the MCP tools exposed by the TypeScript server
(`ts/src/server.ts`) and how they map to the ESP32 antenna firmware.

## Transport Overview

MCP Client → Nostr (ContextVM) → TypeScript MCP Server → Serial (USB) → ESP32 Firmware

The ESP32 listens for simple UART commands:

```
AZ <steps>
EL <steps>
```

---

## Exposed MCP Tools

### 1. move_antenna

Moves the antenna in azimuth and/or elevation.

**Input schema:**

- `azimuth_steps` (number, optional)
- `elevation_steps` (number, optional)

**Example MCP calls:**

```
move_antenna azimuth_steps=50
```

```
move_antenna elevation_steps=-25
```

```
move_antenna azimuth_steps=10 elevation_steps=5
```

**Serial commands sent to ESP32:**

- `AZ <steps>`
- `EL <steps>`

**Terminal logging (server-side):**

When called, the server logs:

```
[MCP] move_antenna called with: { ... }
[SERIAL] -> AZ X
[SERIAL] -> EL Y
```

---

### 2. echo

Simple debugging tool to verify MCP connectivity.

**Input schema:**

- `message` (string)

**Example:**

```
echo message="hello"
```

**Response:**

```
Echo: hello
```

The server logs:

```
[MCP] echo called with: { message: "hello" }
```

---

## Firmware Command Reference

From `antenna-firmware/src/main.rs`:

Supported UART commands:

- `AZ <steps>` → Move azimuth motor
- `EL <steps>` → Move elevation motor

Firmware responds with:

- `AZ done`
- `EL done`

---

## Notes

- There are currently no movement bounds enforced.
- Large step values will rotate indefinitely.
- Position is not yet persisted or tracked in the MCP layer.

Future improvements:

- Add `get_position` tool
- Add movement limits
- Track internal state in server
- Parse `AZ done` / `EL done` responses
