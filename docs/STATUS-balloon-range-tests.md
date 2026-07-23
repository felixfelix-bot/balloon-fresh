# STATUS: balloon-range-tests

**Last Updated**: 2026-07-23 (session 3)
**Phase**: All software fixes complete. Ready for outdoor range testing.

## Current State

- RX FIFO race bug FIXED (commit 3dcddaf). Was unsolved across 8+ sessions.
- 0% PER at 12.5 dBm (PA enabled). Correct seq 0-499. DEADBEEF marker caught.
- Power sweep v2 complete (commit 5b439f3): PA discontinuity confirmed.
- LR2021 has binary PA: codes 0-24 bypass PA (identical ~4% PER), code 25 enables PA (~0% PER).
- RSSI measurement FIXED (commit d85b5ea). Uses correct LR2021 command 0x024B.
- PER calculation FIXED: handles multi-burst windows correctly.
- Auto noise floor measurement at boot.
- Packet size mismatch fixed: all RX envs now 127B matching TX.
- All 9 firmware envs compile clean (2600/1300/650/325 kbps TX+RX pairs + raw-rx-127).
- Board lock released. Both boards free.

## Board Assignments

| Role | Serial | Port (verify each session) |
|------|--------|---------------------------|
| TX   | E663B035977F242D | /dev/ttyACM* (swaps on reflash) |
| RX   | E663B035973B8332 | /dev/ttyACM* (swaps on reflash) |

**ALWAYS verify by serial number.** Ports swap when boards enter BOOTSEL mode.

## Verified Performance (Indoor, ~30cm)

| Power (dBm) | PER | Throughput | RSSI | PA Status |
|-------------|-----|------------|------|-----------|
| 0.0-12.0    | ~4% | ~1460 kbps | -103 dBm | Bypassed |
| 12.5        | ~0% | 219 kbps*  | -60 dBm  | Enabled   |

*Continuous RX mode. RSSI: avg -61 dBm, min -105, max -58.
Noise floor: -103 to -105 dBm (measured at boot).

## Git State

- Branch: range-tests
- Commits: 3dcddaf (GPIO IRQ), 5b439f3 (power sweep), 9210ef3 (docs), d85b5ea (RSSI)
- Software fixes pending commit (PER fix, noise floor, pkt size fix, docs update)
- Pushed to: ngit + GitHub (felixfelix-bot/balloon-fresh)

## Firmware Envs Ready for Testing

| Env | Bitrate | Status | Use |
|-----|---------|--------|-----|
| rp2040-range-tx-auto | 2600 kbps | Compiles | Standard TX |
| rp2040-raw-rx-127 | 2600 kbps | Compiles | Primary RX (RSSI+PER+noise) |
| rp2040-range-tx-1300 | 1300 kbps | Compiles | Extended range |
| rp2040-range-rx-1300 | 1300 kbps | Compiles | Extended range |
| rp2040-range-tx-650 | 650 kbps | Compiles | Long range |
| rp2040-range-rx-650 | 650 kbps | Compiles | Long range |
| rp2040-range-tx-325 | 325 kbps | Compiles | Max range |
| rp2040-range-rx-325 | 325 kbps | Compiles | Max range |

## Next Steps (Physical — Operator Required)

1. Flash TX+RX with current firmware (rp2040-range-tx-auto + rp2040-raw-rx-127)
2. Outdoor range test: 10m, 50m, 100m, 500m at 2600 kbps
3. Repeat at 1300/650/325 kbps for range vs bitrate tradeoff
4. Record results in data/range-test-template.csv
5. Battery-powered autonomous walk test
