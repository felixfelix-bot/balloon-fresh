# SPI Frequency Sweep Plan — LR2021 FLRC TX

## Objective
Find optimal RP2040 SPI clock speed for LR2021 FLRC TX.
Test 16, 17, 18, 19, 20 MHz and measure throughput + TX_DONE count.

## Method
For each frequency, subagent changes SPI_FREQ_HZ constant, builds, commits.
Manager flashes + reads serial + reports results.

## Test Points
| SPI MHz | SPI_FREQ_HZ | Expected |
|---------|-------------|----------|
| 16 | 16000000 | 1377 kbps (baseline, proven) |
| 17 | 17000000 | ? |
| 18 | 18000000 | ? |
| 19 | 19000000 | ? |
| 20 | 20000000 | 1377 kbps (tested, same as 16) |

## RP2040 SPI Clock
RP2040 SPI peripheral derives clock from system clock (125MHz) via divider.
Available divisors: 2, 4, 6, 8, ... (even numbers only on RP2040)
- 125/8 = 15.625 MHz ≈ 16 MHz
- 125/6 = 20.83 MHz ≈ 20 MHz
- 125/2 = 62.5 MHz (too fast for LR2021)

Note: RP2040 SPI only supports even divisors, so intermediate values
(17, 18, 19 MHz) may not be exactly achievable. The actual clock
will be 125MHz / nearest_even_divisor.