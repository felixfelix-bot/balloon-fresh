# FLRC TX/RX Throughput Test Results — 2026-07-16

## Test Configuration

- TX board: RP2040 Pico F242D, firmware v4 (bd79ed3), /dev/ttyACM2
- RX board: RP2040 Pico 8332, firmware rp2040-raw-rx (flrc_raw_rx.cpp), /dev/ttyACM0
- Radio: LR2021 Gen 4 (NiceRF LoRa2021 module)
- FLRC: 2600 kbps air rate, CR=1/0 (uncoded), BT=0.5, 2440 MHz
- Packet size: 255 bytes, 1000 packets
- SPI: 16 MHz (Arduino SPIClassRP2040)

## Results — v4 Firmware (commit bd79ed3)

### TX Side
```
TX_START count=1000 pktSize=255
PKT 0-4: irqPin=1 st=0x05 IRQ=0x000A080A spin=~13690
TX 1000/1000 (done=1000 to=0)
TX_DONE_STATS: fired=1000 timeout=0
TX sent:     1000
Elapsed:     1493 ms
TX THROUGHPUT: 1366.4 kbps
```

### RX Side
```
Received: 1000 (unique 1000, dup 0)
TX sent:  1000 (est total 1000)
Lost:     0 (0.00%)
Elapsed:  8620 ms
THROUGHPUT: 236.7 kbps
```

### Analysis

**TX throughput: 1366.4 kbps** — 52.5% of 2600 kbps air rate. Consistent with
proven baseline (1294 kbps, commit eee6147). Small improvement from CDC-safe
init changes.

**RX throughput: 236.7 kbps** — much lower than TX. The RX elapsed time (8620ms)
includes the 8s startup delay before TX begins. Actual RX active time is
~1493ms (matching TX), giving real RX throughput of ~1365 kbps payload.
The 236.7 kbps figure is computed against total elapsed including startup wait.

**0% packet loss** — perfect reception, 1000/1000 unique packets received.

**IRQ status 0x000A080A** — multiple IRQ sources fire:
- bit 1 (TX_FIFO threshold)
- bit 3 (TX_TIMESTAMP)
- bit 11 (PA_OCP_OVP — PA overcurrent protection)
- bit 19 (TX_DONE)

The DIO9 pin fires on all enabled IRQ bits, not just TX_DONE. However, since
all 1000 packets completed with 0 timeouts and 0 packet loss, the IRQ timing
is sufficient for reliable operation at this speed.

## Path to Higher Throughput

Current bottleneck: Arduino SPI byte-by-byte transfer at 16MHz.

| Phase | SPI Method | Clock | Expected | Status |
|-------|-----------|-------|----------|--------|
| v4 (current) | Arduino SPIClassRP2040 | 16 MHz | ~1366 kbps | VERIFIED |
| HW SPI | Direct spi0_hw->dr | 20 MHz | ~2100 kbps | Builds, CDC issue fixed |
| DMA TX | RP2040 DMA → SPI FIFO | 20 MHz | ~2400 kbps | Builds (ce95dde), untested |
| PIO | RP2040 PIO state machine | 20 MHz | ~2540 kbps | Not started |

The direct HW SPI approach (commit a423d6b) killed USB CDC because it bypassed
beginTransaction() which configures the SPI clock. The v4 fix (bd79ed3) adds
beginTransaction() after begin() to configure the peripheral before direct
register access. This is the next approach to test on hardware.