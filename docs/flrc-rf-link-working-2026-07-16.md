# FLRC RF Link — WORKING (2026-07-16)

## Result
- TX: 1000/1000 TX_DONE (100%), 1292.8 kbps
- RX: 997/1000 received (99.7%), 0 duplicates, 0.30% PER
- RX throughput: 1302.9 kbps
- Packet data correct: seq 0,1,2,3... with payload

## Hex dump (first packets)
```
Pkt 0: 00 00 00 00 04 05 06 07  (seq=0)
Pkt 1: 00 00 00 01 04 05 06 07  (seq=1)
Pkt 2: 00 00 00 02 04 05 06 07  (seq=2)
Pkt 3: 00 00 00 03 04 05 06 07  (seq=3)
```

## 6 Root Causes Fixed
1. Missing CLEAR_ERRORS before init
2. PA config byte 0x01→0x80 (HF PA select bit 7)
3. SET_RX/SET_TX 6→5 bytes (extra trailing byte = CMD_ERROR)
4. GET_AND_CLEAR_IRQ_STATUS in TX poll loop clearing TX_DONE prematurely
5. CALIBRATE bitmask 0x2F→0x6F
6. TX power not multiplied by 2

## Key Firmware Fixes
- TX: IRQ pin-only polling (no SPI GET_AND_CLEAR during wait loop)
- TX: STDBY_XOSC (0x01) between TX packets
- RX: Single SPI transaction FIFO read (no CS toggle, no status bytes)
- RX: CLEAR_RX_FIFO (0x011E) after each packet
- RX: Removed broken GET_RX_BUFFER_STATUS (0x013D LR11x0 opcode)

## Boards
- TX: RP2040 8332 (ACM2)
- RX: RP2040 F242D (ACM0)
- Bridge: ESP32-C3 (ACM1)

## Next: Optimize for higher throughput
- Current: ~1300 kbps (50% of 2600 kbps FLRC max)
- Target: 2600 kbps
- Bottleneck: per-packet overhead (STDBY + DIO re-config + FIFO clear between each TX)
