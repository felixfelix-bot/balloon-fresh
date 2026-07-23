# STATUS: balloon-range-tests

**Last Updated**: 2026-07-23
**Phase**: RF link verified, power sweep complete, outdoor range testing next

## Current State

- RX FIFO race bug FIXED (commit 3dcddaf). Was unsolved across 8+ sessions.
- 0% PER at 12.5 dBm (PA enabled). Correct seq 0-499. DEADBEEF marker caught.
- Power sweep v2 complete (commit 5b439f3): PA discontinuity confirmed.
- LR2021 has binary PA: codes 0-24 bypass PA (identical ~4% PER), code 25 enables PA (~0% PER).
- RSSI register reads unreliable (0x022A always returns -127 dBm).
- Board lock released. Both boards free.

## Board Assignments

| Role | Serial | Port (verify each session) |
|------|--------|---------------------------|
| TX   | E663B035977F242D | /dev/ttyACM0 (swaps on reflash) |
| RX   | E663B035973B8332 | /dev/ttyACM2 (swaps on reflash) |

**ALWAYS verify by serial number.** Ports swap when boards enter BOOTSEL mode.

## Verified Performance (Indoor, ~30cm)

| Power (dBm) | PER | Throughput | PA Status |
|-------------|-----|------------|-----------|
| 0.0-12.0    | ~4% | ~1460 kbps | Bypassed  |
| 12.5        | ~0% | 219 kbps*  | Enabled   |

*Continuous RX mode. Per-burst: 622/500 pkts, 0% PER, 260 kbps.

## Git State

- Branch: range-tests
- Commits: 3dcddaf (GPIO IRQ fix), 5b439f3 (power sweep data)
- Pushed to: ngit + GitHub (felixfelix-bot/balloon-fresh)
- Working tree: clean

## Next Steps

1. Outdoor range test (10m, 50m, 100m+ LOS)
2. Fix RSSI measurement (register 0x022A broken)
3. Test 1300/650 kbps modes for extended range
4. Investigate 4% non-PA PER (enable CRC to distinguish lost vs corrupted)
5. Battery-powered autonomous walk test
