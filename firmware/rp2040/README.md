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
| GP12        | UART0 TX | → ESP32 GPIO3 (RX) |
| GP13        | UART0 RX | ← ESP32 GPIO2 (TX) |

**UART pins verified 2026-07-15.** GP20/GP21 are on the backside of RP2040-Zero
(inaccessible when soldered). GP12/GP13 (UART0 function) are top-side and confirmed
working bidirectionally through the ESP32 UART bridge.

See: `docs/uart-bridge-pin-verification.md`

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

## FLRC Speed RX (`rp2040-flrc-rx` env)

A standalone build that uses **RadioLib for modulation init** and a **raw SPI hot
loop** for minimum per-packet latency. This is the RX half of the speed-record
test (2450 MHz, BR=2600, uncoded, 255-byte fixed packets). It is a separate
source file (`src/flrc_rx_main.cpp`) and a separate PlatformIO environment so it
does **not** touch the UART coprocessor firmware (`main.cpp` / `radio.cpp`).

```bash
cd firmware/rp2040
pio run -e rp2040-flrc-rx
pio run -e rp2040-flrc-rx -t upload --upload-port /dev/ttyACM1
pio device monitor -p /dev/ttyACM1 -b 115200
```

### How it works

1. **Init** — `radio.beginFLRC(2450, 2600, CR_1_0, 22, 16, BT_0.5, tcxo=0)` +
   `fixedPacketLengthMode(255)` + `startReceive()`. RadioLib configures the
   modulation and maps RX_DONE onto DIO9 (GP7). A custom `MbedSPI` on SPI0
   (GP2/GP3/GP4 at 16 MHz) is handed to RadioLib via `Module(cs,irq,rst,busy,
   SPIClass&, SPISettings)`, so init and the hot loop share one bus. (The mbed
   core's global `SPI` is on GP16/18/19, hence the explicit injection.)
2. **Hot loop** — poll DIO9 for RX_DONE, then three raw-SPI ops with `micros()`
   timing: `READ_RX_FIFO` (0x0001, read 255 B) → `CLEAR_IRQ` (0x0116) →
   `SET_RX` (0x020C, timeout=0xFFFFFF = continuous) to re-arm. Opcodes verified
   against RadioLib `LR2021_commands.h`.
3. **Counting** — big-endian seq# from the first 4 bytes; a `DEADBEEF` end
   marker `{DE,AD,BE,EF, totalSent(4 B)}` from the ESP32 TX ends the run.

> Note: the legacy `radio.h`/`radio.cpp` use a wrong FIFO opcode (0x0200 = SET_RF)
> and a wrong RX_DONE bit (3 instead of **19**) for the LR2021. `flrc_rx_main.cpp`
> uses the correct values inline and does not depend on those files.

### Serial commands (USB CDC, 115200)

| Command  | Action |
|----------|--------|
| `RUN`    | start receiving; stops on DEADBEEF marker, silence (3 s), or hard cap (12 s) |
| `CONFIG` | print radio config + pin map |
| `RESULTS`| print accumulated statistics |
| `HELP`   | list commands |

Output includes per-packet CSV (`pkt,seq,irq2read_us,read2clr_us,clr2rx_us,total_us`),
a human-readable summary, and a machine-readable `RESULT,...` line.

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
