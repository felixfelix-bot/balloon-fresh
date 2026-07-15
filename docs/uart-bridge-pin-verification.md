# UART Bridge Pin Verification — Honest Test Report
## Date: 2026-07-15

## What was tested

ESP32-C3 UART bridge firmware with three different GPIO pin configs.
Each config was built, flashed to ACM1 (serial 70:AF:09:13:21:00),
and read for 8+ seconds. RP2040 8332 was running FLRC RX firmware
(outputting "HB alive" heartbeats on Serial1).

## Results

| GPIO RX | GPIO TX | RP2040 data seen? | Lines received |
|---------|---------|-------------------|----------------|
| GPIO0   | GPIO1   | NO                | 0 (bridge heartbeat only) |
| GPIO2   | GPIO3   | NO                | 0 (bridge heartbeat only) |
| GPIO3   | GPIO4   | YES               | "HB alive" every ~2s |

## What "RP2040 data seen" means

The bridge outputs two types of lines:
- `[BRIDGE ALIVE Ns]` — ESP32 bridge heartbeat (every 5s)
- `HB alive` — RP2040 UART output forwarded through bridge (every ~2s)

Only GPIO3(RX)/GPIO4(TX) produced RP2040 data lines.

## Bidirectional test (GPIO3/GPIO4)

Sent "RUN\r\n" through bridge to RP2040 via ACM1.
- No error on send
- RP2040 continued outputting "HB alive" (didn't change to RX_START)
- This suggests RP2040 received the command but radio init failed

## ACM3 (second ESP32, serial 70:AF:09:21:FB:18)

Tested with GPIO3(RX)/GPIO4(TX) — showed ONLY bridge heartbeats.
No RP2040 data from F242D (ACM2). Possible causes:
- F242D firmware doesn't output on Serial1
- Different wiring on that board pair
- F242D USB CDC also dead, can't verify what firmware it runs

## User-reported wiring

User stated: "pin 12 and 13 from rp2040 go to pins 3 and 4 on the esp32"
Then corrected: "pins 2 and 3. We start counting the pins from zero."

Code uses GPIO_NUM_3 (RX) and GPIO_NUM_4 (TX) which WORKS.
User's physical "pins 2,3" (0-indexed) may correspond to GPIO3/GPIO4
if board silkscreen doesn't match raw GPIO numbers.

ESP32-C3 SuperMini pin numbering varies by manufacturer.
The verified fact: GPIO3=RX, GPIO4=TX in firmware code produces results.

## Conclusion

Working config: `Serial1.begin(115200, SERIAL_8N1, GPIO_NUM_3, GPIO_NUM_4)`
- RP2040 GP12 (TX) → ESP32 GPIO3 (RX)
- RP2040 GP13 (RX) ← ESP32 GPIO4 (TX)
