# LA Probe Wiring: RP2040 ↔ ESP32-C3 ↔ LR2021

## Logic Analyzer Channel Map

Same LA channel mapping works for both MCUs. Saleae Logic (fx2lafw), 24 MHz sample rate.

### RP2040 (Waveshare RP2040-Zero)

| LA Channel | Signal | RP2040 Pin |
|------------|--------|------------|
| D0 | CS (NSS) | GP5 |
| D1 | SCK | GP6 |
| D2 | MOSI | GP7 |
| D3 | MISO | GP4 |
| D4 | BUSY | GP8 |
| D5 | IRQ (DIO9) | GP9 |
| D6 | RST | GP10 |
| GND | GND | GND |

### ESP32-C3 (Super Mini V1)

| LA Channel | Signal | ESP32-C3 GPIO |
|------------|--------|---------------|
| D0 | CS (NSS) | GPIO10 |
| D1 | SCK | GPIO6 |
| D2 | MOSI | GPIO7 |
| D3 | MISO | GPIO2 |
| D4 | BUSY | GPIO4 |
| D5 | IRQ (DIO9) | GPIO5 |
| D6 | RST | GPIO3 |
| GND | GND | GND |

> Pinout reference: see `docs/esp32-c3-pinout.jpg`

## LR2021 SPI Protocol (2-byte opcodes)

| Command | Opcode | Bytes | Direction |
|---------|--------|-------|-----------|
| CLEAR_IRQ_STATUS | 0x0116 | 6 | Write |
| WRITE_TX_FIFO | 0x0002 | 2+N | Write |
| SET_TX | 0x020D | 5 | Write |
| READ_IRQ_STATUS | 0x0117 | 5 | Read |

Protocol: `NSS LOW → wait BUSY LOW → send [opcode_hi, opcode_lo, ...payload] → NSS HIGH`

## Wiring Diagram (Text)

```
                ┌─────────────────────┐
                │   Logic Analyzer    │
                │   (Saleae fx2lafw)  │
                └──┬──┬──┬──┬──┬──┬──┬┘
                   │  │  │  │  │  │  │
              D0 ──┘  │  │  │  │  │  └── D6
              D1 ────┘  │  │  │  │
              D2 ──────┘  │  │  │
              D3 ────────┘  │  │
              D4 ──────────┘  │
              D5 ────────────┘

    ┌──────────────┐                    ┌──────────────────┐
    │    RP2040    │                    │   ESP32-C3       │
    │  (or)        │──── SPI ──────────│   Super Mini     │
    │              │                    │                  │
    │  GP5  = CS   │                    │  GPIO10 = CS     │──→ LR2021 NSS
    │  GP6  = SCK  │                    │  GPIO6  = SCK    │──→ LR2021 SCK
    │  GP7  = MOSI │                    │  GPIO7  = MOSI   │──→ LR2021 MOSI
    │  GP4  = MISO │                    │  GPIO2  = MISO   │──→ LR2021 MISO
    │  GP8  = BUSY │                    │  GPIO4  = BUSY   │←── LR2021 BUSY
    │  GP9  = IRQ  │                    │  GPIO5  = IRQ    │←── LR2021 DIO9
    │  GP10 = RST  │                    │  GPIO3  = RST    │──→ LR2021 NRESET
    │  GND  = GND  │                    │  GND   = GND     │──→ LR2021 GND
    └──────────────┘                    └──────────────────┘
```

## Switching from RP2040 to ESP32-C3

Move LA probes:
- D0: GP5 → GPIO10
- D1: GP6 → GPIO6
- D2: GP7 → GPIO7
- D3: GP4 → GPIO2
- D4: GP8 → GPIO4
- D5: GP9 → GPIO5
- D6: GP10 → GPIO3

MCU-to-LR2021 wiring also changes (different GPIO numbers). Both MCUs use the same SPI protocol — only the MCU-side pins differ.

## Related Files

- `docs/esp32-c3-pinout.jpg` — ESP32-C3 Super Mini pinout reference
- `docs/mcu-assessment-rp2040-vs-esp32.md` — hardware comparison + benchmark plan
- `docs/plan-esp32-vs-rp2040-benchmark.md` — 7-task benchmark plan
- `docs/rp2040-baseline-results.md` — RP2040 baseline data (1,760 kbps)
- `captures/bench-rp2040.sr` — RP2040 baseline capture
