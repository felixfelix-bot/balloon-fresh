# RP2040 Coprocessor Firmware (Board B / ADR-015)

Firmware for the RP2040-Zero coprocessor that drives the LR2021 radio via hardware SPI,
bypassing the ESP32-C3's single-core RX pipeline bottleneck.

## Architecture

```
[ESP32-C3 (TX)] ──RF──→ [LR2021] ←SPI0→ [RP2040-Zero] ←UART→ [ESP32-C3 (RX/log)]
```

- **Core 0**: Radio I/O — tight IRQ-polling loop, raw SPI FIFO reads, auto RX restart
- **Core 1**: Statistics + UART output — packet queue, CSV logging, throughput calc

## Pin Map

| RP2040 GPIO | Function | LR2021 Pin |
|:-----------:|:--------:|:----------:|
| GP2         | SPI0 SCK | Pin 5      |
| GP3         | SPI0 MOSI| Pin 4      |
| GP4         | SPI0 MISO| Pin 3      |
| GP5         | CS (GPIO)| Pin 6 (NSS)|
| GP6         | BUSY in  | Pin 7      |
| GP7         | IRQ in   | Pin 15 (DIO9)|
| GP8         | RST out  | Pin 14     |
| GP20        | UART1 TX | → ESP32 GPIO1 |
| GP21        | UART1 RX | ← ESP32 GPIO0 |

See: `docs/adr/015-three-board-hardware-strategy.md`

## Build & Flash

```bash
# Install PlatformIO (one-time)
pip install platformio

# Build
make rp2040-build          # or: cd firmware/rp2040 && pio run

# Flash (hold BOOT on RP2040-Zero while plugging USB)
make rp2040-flash

# Monitor
make rp2040-monitor
```

## Test

```bash
# Simulation tests (no hardware needed)
make rp2040-sim

# Hardware speed test (TX board + RP2040 + LR2021 connected)
make rp2040-test TX_PORT=/dev/ttyUSB0 RX_PORT=/dev/ttyACM0
```

## Serial Protocol

The RP2040 outputs:
1. `READY\n` — boot complete, waiting for start command
2. On receiving `S\n` → `START\n` + CSV header
3. Per-packet: `pkt,seq,irq_us,read_us,clr_us,rx_us,total_us\n`
4. Summary: `RESULT,recv,unique,dup,err,tput_kbps,min_us,avg_us,max_us\n`

## Performance Targets

| Metric | ESP32-C3 (Board A) | RP2040 (Board B) | Target |
|--------|-------------------|-------------------|--------|
| SPI clock | 10.46 Mbps | 18-31.25 Mbps | ↑ |
| Processing/pkt | 188µs (raw) | <140µs (est.) | <200µs |
| Throughput | 838.8 kbps | 2000+ kbps | ≥2000 |
| Max pkt rate | ~5300 pkt/s | ~7100+ pkt/s | — |

Bottleneck shifts from CPU/RTOS overhead (ESP32-C3) to air rate (2600 kbps FLRC).
