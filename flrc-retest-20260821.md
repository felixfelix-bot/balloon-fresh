# FLRC re-test findings — 2026-08-21 (post-full-sweep)

Fresh spot measurements, fw=88a00cf both boards, 868 MHz, auto-detected
TX=/dev/ttyUSB3 RX=/dev/ttyUSB5, roles assigned via radio handshake.

## Result 1 — Original FLRC CRC failure does NOT reproduce

BR650/PA5/LEN=64 (failed 50/50 in full-sweep-20260821-162143):
NOW 10/10 CRC-clean, RSSI -70. Identical reset+config procedure.

## Result 2 — LEN=255 exactly fails in FLRC (reproducible)

| LEN | pkts | CRC ok | RSSI dBm |
|-----|------|--------|----------|
| 16  | 10   | 10/10  | -68 |
| 64  | 10   | 10/10  | -69 |
| 128 | 10   | 10/10  | -69 |
| 192 | 10   | 10/10  | -70 |
| 255 | 10   | 0/10   | -34 |
| 300 | 10   | 10/10  | -34 |
| 384 | 10   | 10/10  | -34 |
| 511 | 20   | 20/20  | -34 |

BR650 L255: 0/10 fail, RSSI -39. BR1300 L255: 0/10 fail, RSSI -34.

## Observations

1. **LEN=255 is a hard CRC failure point** at both BRs tested. 254 and 256
   untested yet. Boundary at the SX1262 LoRa max (255) suggests the firmware
   branches on plen <= 255 vs > 255 and the boundary case is mishandled
   (TX and RX may take different branches, or an off-by-one in payload strip).
2. **RSSI jumps +35 dB at LEN >= 255** (-69 → -34) — same link, same PA.
   Suggests the radio config path actually changes at 255 (different packet
   handling / AGC / RSSI readout mode), not just a parser artifact.
3. **SNR consistently reads 0 in FLRC** — matches full sweep; likely SNR
   register not valid/implemented for FLRC packets in driver.
4. Original sweep's L64 failures may have been state-dependent (sweep ran
   FLRC after 40 LoRa configs; spot-tests today ran FLRC fresh). Needs
   controlled reproduction attempt with the exact sweep sequence before
   declaring the sweep data wrong.

## Next

- Consultant root-cause (deleg_5df15411) in flight; feed this file to fix plan.
- Test LEN 254/256 to confirm boundary; check firmware branch on 255.
- Full FLRC re-sweep after fix.
