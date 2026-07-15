# UART Bridge Pin Verification — Honest Test Report
## Date: 2026-07-15 (updated with final verified results)

## VERIFIED WORKING PINS

```
RP2040 GP12 (UART0 TX) ──→ ESP32 GPIO3 (UART1 RX)   [physical pin 3]
RP2040 GP13 (UART0 RX) ←── ESP32 GPIO2 (UART1 TX)   [physical pin 2]
GND ───────────────────── GND
```

Firmware code (esp32-uart-bridge/src/main.cpp v6):
```cpp
Serial1.begin(115200, SERIAL_8N1, GPIO_NUM_3, GPIO_NUM_2);
//                                     RX=GPIO3    TX=GPIO2
```

## What was tested

ESP32-C3 SuperMini UART bridge firmware with three different GPIO pin configs.
Each config was built, flashed to ACM1 (serial 70:AF:09:13:21:00),
and read for 8+ seconds. RP2040 8332 was running FLRC RX firmware
(outputting "HB alive" heartbeats on Serial1).

## Results

| ESP32 RX | ESP32 TX | RP2040 data seen? | Lines received |
|----------|----------|-------------------|----------------|
| GPIO0    | GPIO1    | NO                | 0 (bridge heartbeat only) |
| GPIO2    | GPIO3    | NO                | 0 (bridge heartbeat only) |
| GPIO3    | GPIO4    | PARTIAL           | "HB alive" (RX worked, TX unconfirmed) |
| GPIO3    | GPIO2    | YES — BIDIRECTIONAL | "HB alive" + CONFIG/INIT commands forwarded |

## Bidirectional test (GPIO3 RX / GPIO2 TX) — CONFIRMED WORKING

Sent commands through bridge to RP2040 via ACM1 using pyserial:
- Sent "CONFIG" → RP2040 returned full radio config dump (freq, BR, pins, etc.)
- Sent "INIT" → RP2040 returned "beginFLRC code: -707" (radio init result)
- Received "HB alive" heartbeats continuously

This confirms both directions work: RP2040→ESP32 (data) AND ESP32→RP2040 (commands).

## Earlier confusion: GPIO3(RX)/GPIO4(TX)

Initial test with GPIO3(RX)/GPIO4(TX) showed RP2040 data ("HB alive").
The RX direction worked because GPIO3 IS wired to RP2040 GP12.
The TX direction was unconfirmed — GPIO4 may not be wired to RP2040 GP13.

User then reported physical "pins 2 and 3 counting from zero" = GPIO2 and GPIO3.
Final firmware uses GPIO2(TX)/GPIO3(RX) and BIDIRECTIONAL communication is verified.

## ACM3 (second ESP32, serial 70:AF:09:21:FB:18)

Tested with GPIO3(RX)/GPIO2(TX) — showed ONLY bridge heartbeats.
No RP2040 data from F242D (ACM2). Possible causes:
- F242D firmware doesn't output on Serial1 (TX firmware only dual-prints if radio inits)
- Different wiring on that board pair
- F242D USB CDC also dead, can't verify what firmware it runs

## Physical pin mapping

ESP32-C3 SuperMini silkscreen vs GPIO number:
- Physical pin labeled "3" on board = GPIO3
- Physical pin labeled "2" on board = GPIO2
- User confirmed: "pins 2 and 3. We start counting the pins from zero."

## Conclusion

CORRECT working config:
```cpp
Serial1.begin(115200, SERIAL_8N1, GPIO_NUM_3, GPIO_NUM_2);
```

Wiring:
- RP2040 GP12 (TX) → ESP32 GPIO3 (RX)
- RP2040 GP13 (RX) ← ESP32 GPIO2 (TX)
- GND → GND (shared, already connected via LR2021 ground)

Cross-connect TX→RX on both ends.
