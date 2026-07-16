# LR2021 FLRC Link — Dual-Track Master Plan (2026-07-17)

## STATUS: Two parallel tracks, independently executable

Track A and Track B run simultaneously in separate Signal groups.
Neither blocks the other. Logic analyzer is NOT a prerequisite for either.

---

## TRACK A: RANGE TESTING (signal group: balloon-range)

**Goal:** Characterize RF link performance across distance, power, packet
size, modulation, and antenna configurations.

**Status:** READY NOW. Uses current proven firmware (1377 kbps, 1000/1000
TX_DONE, 0% RX loss). No firmware changes needed.

**Prerequisites:** Two RP2040+LR2021 boards, antennas, outdoor space.

**Plan:** docs/range-test-comprehensive-plan-2026-07-17.md

**Key parameters to sweep:**
- Distance: 1m → 100m+ (line of sight)
- TX power: 0 → +12.5 dBm
- Packet size: 16 → 255 bytes
- Modulation: FLRC 2600 kbps vs LoRa (long range mode)
- Antenna: wire dipole vs PCB antenna vs ground station Yagi
- Frequency: 2400-2480 MHz (channel spacing)

**Hardware available:**
- 2x RP2040 + LR2021 (current boards, proven link)
- 3x EBYTE E28-2G4M27S (SX1281, +27 dBm PA — NOT yet integrated)
- 100x solar cells (not relevant for range test)
- Wire dipoles + PCB antennas

---

## TRACK B: THROUGHPUT OPTIMIZATION (signal group: balloon-hermes)

**Goal:** Maximize SPI throughput on RP2040. Push beyond 1377 kbps using
existing hardware. No FPGA, no platform switch.

**Status:** 3 experiments ready, none require logic analyzer.

**Prerequisites:** Same two RP2040+LR2021 boards (shared with Track A when
range tests not running).

**Plan:** docs/speed-test-comprehensive-plan-2026-07-17.md

**Experiments (priority order):**
1. Single-batch SPI test (30 min — combine header+payload into ONE transfer)
2. Self-timing diagnostic flash (10 min — get exact µs numbers)
3. Dual-core RX pipelining (2-4 hrs coding — shrink blind window 572→100µs)
4. Logic analyzer capture (when Red Pitaya wired — NOT blocking)

**Decision gate:** If single-batch works → 2000+ kbps possible.
If it fails → dual-core RX still gives better headroom.
If both fail → accept 1377 kbps (sufficient for application).

---

## LOGIC ANALYZER: NOT A BLOCKER

Previous plan had LA as a gate. Revised: LA is diagnostic documentation,
not a prerequisite. The single-batch test will tell us more in 30 minutes
than an LA afternoon would.

LA priority: LOW. Only needed if we want to document root cause for
academic/reproducibility purposes. Track B experiments 1-3 are independent.

---

## SHARED RESOURCES

| Resource | Track A | Track B |
|----------|---------|---------|
| TX board (B8332) | Range tests | Speed tests |
| RX board (F242D) | Range tests | Speed tests |
| Both boards | Cannot share simultaneously | Cannot share simultaneously |
| Laptop + terminal | Yes | Yes |
| Red Pitaya (LA) | Not needed | Nice-to-have |

**Coordination:** When Track A runs outdoor range tests, Track B does
firmware development (no boards needed). When boards return, Track B
flashes and tests.

---

## LINK MAP

- Track A plan: docs/range-test-comprehensive-plan-2026-07-17.md
- Track B plan: docs/speed-test-comprehensive-plan-2026-07-17.md
- Track A handover: docs/handover-range-testing-2026-07-17.md
- Track B handover: docs/handover-speed-testing-2026-07-17.md
- Historical analysis: docs/lr2021-spi-bottleneck-analysis-2026-07-16.md
- Historical plan (superseded): docs/lr2021-throughput-optimization-plan-2026-07-16.md
