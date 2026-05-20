# Serial Integration Learnings

This document captures what we validated while manually interacting with the
ESP32 antenna tracker over USB serial and how it maps to the MCP server.

---

## 1. Confirmed Working Serial Path

We verified direct UART communication using:

Terminal 1:

```
cat /dev/ttyUSB1
```

Terminal 2:

```
echo "AZ 10" > /dev/ttyUSB1
echo "EL 10" > /dev/ttyUSB1
```

Observed responses:

```
AZ done
EL done
```

This confirms:

- ✅ Firmware is running
- ✅ UART0 over USB works
- ✅ Baud rate is correct (115200)
- ✅ Command parsing works
- ✅ Motors respond to commands

---

## 2. Correct Baud Rate

Firmware explicitly sets:

```
UartConfig::default().baudrate(115200)
```

Therefore the correct terminal setting is:

```
115200 8N1
```

Using 1152000 (extra zero) will not work.

---

## 3. Firmware Serial Protocol

The ESP32 listens for ASCII commands terminated by newline:

```
AZ <steps>\n
EL <steps>\n
```

Examples:

```
AZ 50
EL -20
```

Responses:

```
AZ done
EL done
```

---

## 4. MCP Server → Serial Mapping

The TypeScript MCP server (`ts/src/server.ts`) sends commands exactly like
our manual test:

```ts
port.write(`AZ ${azimuth_steps}\n`);
port.write(`EL ${elevation_steps}\n`);
```

This matches the working manual test:

```
echo "AZ 10" > /dev/ttyUSB1
```

Therefore the MCP server is correctly issuing serial commands in the
same format as validated manually.

---

## 5. Common Serial Issues Encountered

1. Device busy → another process (screen/node) holding the port
2. Wrong baud rate (1152000 instead of 115200)
3. Local echo disabled in picocom
4. MCP server locking the port

All were resolved.

---

## 6. Current Architecture Status

Working chain:

MCP Client → Nostr → TypeScript MCP Server → Serial → ESP32 Firmware → Motors

Both manual CLI control and MCP-triggered control now use the same
validated serial command format.

---

## 7. Next Possible Improvements

- Parse and log `AZ done` / `EL done` responses in server
- Track current position in MCP layer
- Add movement bounds and safety limits
- Add homing routine

---

Status: ✅ Serial integration fully verified.
