# STATUS: balloon-range-tests

**Last Updated**: 2026-07-21
**Phase**: Infrastructure complete, outdoor distance sweep pending

## Current State

- Proven RF baseline: 1377 kbps FLRC, 0% packet loss at <1m, 1000/1000 packets
- 2x RP2040+LR2021 boards working (TX: E663B035973B8332, RX: E663B035977F242D)
- Runtime-configurable FLRC firmware committed (POWER, PKTLEN, FREQ, COUNT, BITRATE, RUN commands)
- RSSI readback + test runner implemented
- Ground station receiver firmware built (181KB, 82% partition free), P0/P1 bugs fixed
- Board mutex (balloon-board-lock.py) deployed
- 5 failed SPI optimization approaches documented

## Next Steps

1. Flash GS receiver to second ESP32-C3, bench test tracker TX → GS RX
2. Baseline re-verification after transport/reconnection
3. Outdoor distance sweep: 10m, 25m, 50m, 100m LOS
4. TX power sweep (0-12.5 dBm) + packet size sweep (16-255 bytes)

## Blockers

None. Requires physical board access + outdoor space for distance sweep.

## Hardware Required

- 2x RP2040+LR2021 boards (owned)
- 2x wire dipole antennas λ/2=61mm at 2440 MHz
- Laptop + USB cables for outdoor testing
