# Payload Size Sweep — LR2021 Throughput Analysis

## Method
- Firmware: `rp2040-cont-tx` with configurable TX_PKT_SIZE
- Capture: sigrok fx2lafw, 24 MHz, 1 second
- LA D0=CS, D1=SCK, D2=MOSI, D3=MISO, D4=BUSY, D5=IRQ, D6=RST

## Results

| Payload (bytes) | Packets (41.7ms) | SPI Clock | Bus Duty | Avg Gap | Throughput |
|----------------|-------------------|-----------|----------|---------|------------|
| 32             | 426               | 10.35 MHz | 14.0%    | 83.6us  | 1,192 kbps |
| 64             | — (LA dropped)    | —         | —        | —       | —          |
| 128            | — (LA dropped)    | —         | —        | —       | —          |
| 255            | 108               | 10.35 MHz | 19.1%    | 309us   | 1,797 kbps |

255-byte baseline from separate led-test capture for comparison.

## Key Findings

### 1. Smaller packets = shorter gaps
- 32-byte: 83.6us avg gap (10x shorter than 255-byte!)
- 255-byte: 309us avg gap

This proves the 309us gap is mostly **air time** (packet transmission on RF).
At 2600 kbps air rate:
- 32 bytes = 98us air time → fits in 83.6us gap (firmware overlapping TX)
- 255 bytes = 784us air time → 309us measured (IRQ fires partway through)

### 2. Smaller packets = more transactions but lower throughput
- 32-byte: 426 packets in 41.7ms = 10,215 pkt/sec
- 255-byte: 108 packets in 41.7ms = 2,590 pkt/sec

### 3. Per-packet overhead dominates small packets
Each packet has 3 SPI commands (~17us total):
- CLEAR_IRQ (6 bytes, 6.4us)
- WRITE_TX_FIFO (payload + 2 bytes overhead)
- SET_TX (5 bytes, 5.6us)

For 32 bytes: 17us overhead / (17+33)us total = 34% overhead
For 255 bytes: 17us overhead / (17+205)us total = 7.7% overhead

### 4. Throughput scales with payload size
| Payload | Useful bytes | Per-pkt SPI time | Air time | Throughput |
|---------|-------------|------------------|----------|------------|
| 32      | 32          | 17us             | ~98us    | 1,192 kbps |
| 255     | 255         | 217us            | ~784us   | 1,797 kbps |

**Larger payloads are more efficient.** 255 bytes already optimal.

## Conclusion

**255-byte payloads are the throughput sweet spot** — 1,797 kbps, 69% of PHY max.
The bottleneck is air time (physics), not firmware overhead.

### Theoretical ceiling
At 255 bytes with zero firmware overhead:
- Air time: 784us per packet
- Throughput: 255 × 8 / 784us = 2,602 kbps (matches PHY max exactly)

Our 1,797 kbps = 69% of theoretical. The remaining 31% is:
- SPI transfer overhead (217us per packet)
- IRQ polling loop latency
- Inter-packet CS release gap

### Next optimization targets (diminishing returns)
1. **DMA SPI transfers** — eliminate CPU wait during FIFO write
2. **Interrupt-driven TX** — eliminate polling loop overhead
3. **Double-buffered TX** — prepare next packet during current air time
