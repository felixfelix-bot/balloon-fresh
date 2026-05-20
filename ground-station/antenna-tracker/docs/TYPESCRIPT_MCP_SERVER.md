# TypeScript MCP Server (Production Guide)

This document describes how to run and operate the active MCP server
implementation located at:

```
ts/src/server.ts
```

This is the **currently integrated and working server** that bridges:

MCP Client → Nostr (ContextVM) → TypeScript MCP Server → Serial → ESP32 Firmware

---

## 1. Why This Server Is Used

The Rust MCP server (`mcp-antenna/`) successfully connected to relays but
did **not expose tools correctly** through the gateway. Tool listing failed,
so it has been **temporarily sidelined**.

The TypeScript implementation:

- ✅ Correctly exposes tools
- ✅ Connects over Nostr
- ✅ Integrates with serial hardware
- ✅ Returns execution responses
- ✅ Logs command flow

It is currently the authoritative MCP server for the antenna tracker.

---

## 2. Runtime Requirements

Use **Node 20+ only**.

Do NOT use Bun for this server.

Required packages (inside `ts/`):

```
npm install serialport ws
npm install -D tsx
```

---

## 3. WebSocket Shim Requirement

`rxjs` and `@contextvm/sdk` expect a global `WebSocket` constructor.
Node does not expose it as a plain global in this execution context.

We preload a shim:

```
ts/websocket-shim.cjs
```

---

## 4. Production Run Command

From the `ts/` directory:

```
NODE_OPTIONS="--require ./websocket-shim.cjs" npx tsx src/server.ts
```

This:

- Injects global WebSocket
- Starts MCP server
- Connects to Nostr relay
- Opens serial connection
- Logs tool calls and serial responses

---

## 5. Serial Configuration

Default device:

```
/dev/ttyUSB1
```

Override with:

```
ANTENNA_SERIAL=/dev/ttyUSB0 NODE_OPTIONS="--require ./websocket-shim.cjs" npx tsx src/server.ts
```

Baud rate (firmware):

```
115200
```

---

## 6. Exposed MCP Tools

### move_antenna

Inputs:
- `azimuth_steps`
- `elevation_steps`

Serial mapping:

```
AZ <steps>\n
EL <steps>\n
```

Server waits for:

```
AZ done
EL done
```

Then returns completion to MCP client.

---

### echo

Simple connectivity test tool.

---

## 7. Logging Behavior

The server prints:

- MCP tool calls
- Serial commands sent
- Serial responses received
- Relay connection events

This provides full observability of the hardware control pipeline.

---

## 8. Security Note

A static NSEC is currently embedded in `server.ts` for development.

For production:

- Move private key to environment variable
- Do not commit secrets

---

## 9. Current Status

✅ Nostr transport working
✅ Serial integration verified
✅ Firmware validated manually
✅ Full request → execution → acknowledgment loop implemented

Rust MCP server remains sidelined until tool exposure is fixed.
