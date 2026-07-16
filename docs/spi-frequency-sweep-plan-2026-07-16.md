# SPI Clock Frequency Sweep Plan — 2026-07-16

## Objective

Find the optimal SPI clock frequency between 16MHz and 20MHz for LR2021 FLRC TX on RP2040.

## Background

| Clock | TX Throughput | RX Loss | Notes |
|-------|--------------|---------|-------|
| 16 MHz | 1367 kbps | 0% | PROVEN baseline (v4) |
| 20 MHz | 1377 kbps | 0% (with 16MHz RX) | Marginal gain, 20MHz RX breaks |
| 20 MHz RX | N/A | 77% | RX SPI too fast for reliable reception |

The 16→20MHz improvement is only 10 kbps (0.7%) — likely within noise. A frequency sweep will determine if there's a sweet spot or if SPI clock isn't the bottleneck.

## Sweep Points

Test these SPI frequencies on TX (RX stays at 16MHz proven):

1. **8 MHz** — baseline low (validate sweep methodology)
2. **10 MHz** — common SPI speed
3. **12 MHz** — midpoint
4. **14 MHz** — below proven 16MHz
5. **16 MHz** — proven baseline (already have data: 1367 kbps)
6. **17.5 MHz** — between proven + tested
7. **18 MHz** — above proven
8. **19 MHz** — just below 20MHz
9. **20 MHz** — already tested (1377 kbps)

## Methodology

1. Subagent creates a single firmware file with SPI_FREQ_HZ as a runtime parameter
   - Read SPI frequency from serial input before starting TX burst
   - OR: create multiple build envs with different SPI_FREQ_HZ
   - Better approach: single firmware, accept "SETSPI <freq_hz>\n" command via serial
2. Manager flashes one firmware, sends commands for each frequency point
3. Each test: send "SETSPI <freq>\n" then "RUN\n", capture throughput
4. 3 runs per frequency for averaging
5. RX stays at 16MHz throughout (proven 0% loss)

## Expected Outcomes

- **If throughput scales with SPI clock:** SPI is the bottleneck, higher is better
- **If throughput plateaus at ~1370 kbps:** bottleneck is elsewhere (RF air time, IRQ polling overhead, loop overhead)
- **If throughput drops above some frequency:** SPI signal integrity degrades at higher clocks

## RP2040 SPI Clock Constraints

RP2040 SPI peripheral clock = system clock (125 MHz) / prescaler
- Prescaler values: 1, 2, 4, 8, 16, 32, 64, 128, 256
- Achievable frequencies: 125M, 62.5M, 31.25M, 15.625M, 7.8M, ...
- Arduino SPI.setFrequency() maps to nearest valid prescaler
- 16 MHz → prescaler 8 → 15.625 MHz actual
- 20 MHz → prescaler 6 → 20.833 MHz actual (or prescaler 8 → 15.625 if 6 not supported)

**CRITICAL:** RP2040 may not achieve exact frequencies between 16-20 MHz. The actual SPI clock depends on the prescaler. We need to check what frequencies are actually achievable.

This means the sweep should test prescaler-based values:
- 125/4 = 31.25 MHz (too fast for LR2021, max 20MHz)
- 125/6 = 20.83 MHz (slightly above 20MHz spec — risky)
- 125/8 = 15.625 MHz (what "16MHz" actually is)
- 125/10 = 12.5 MHz
- 125/12 = 10.42 MHz
- 125/16 = 7.8125 MHz
- 125/20 = 6.25 MHz
- 125/24 = 5.2 MHz
- 125/32 = 3.9 MHz

The earlephilhower core may use fractional divisors. Need to check SPIClassRP2040 implementation.