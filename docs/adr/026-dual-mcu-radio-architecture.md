# ADR-026: Dual MCU Radio Architecture — RP2040 Radio Processor + ESP32-C3 Application

**Date:** 2026-07-29
**Status:** ACCEPTED
**Decision Maker:** Felix (operator)

## Context

The balloon hub board uses two MCUs:
- **ESP32-C3**: Application layer — FIPS mesh, MeshCore relay, GPS telemetry, power management, Nostr store-and-forward
- **RP2040**: Radio processor — LR2021 SPI bus master, packet framing, FIFO management

This split exists for performance reasons. SPI throughput in the RX pipeline was the primary bottleneck. Testing showed RP2040 batched SPI significantly outperforms ESP32-C3.

## Measured Performance (Air Rate: 2600 kbps FLRC)

| MCU | Throughput | % of Air Rate | Test |
|-----|-----------|---------------|------|
| RP2040 (Pico SDK, batched SPI) | 1377 kbps | 54% | 1000/1000 packets verified |
| ESP32-C3 (ESP-IDF, raw SPI) | 838 kbps | 33% | 1000/1000 packets verified |

RP2040 is **64% faster** at the radio layer. Source: `docs/lr2021-bottleneck-analysis-2026-07-29.md`

## Why RP2040 Is Faster

1. **Batched SPI commands**: RP2040 builds entire multi-byte transactions in a single DMA buffer. Single SPI transfer: NSS LOW → wait BUSY → send [opcode + payload] → NSS HIGH. No per-byte gaps.
2. **Dedicated radio processing**: RP2040 runs ONLY the radio stack. No WiFi/BT stack competing for CPU cycles, no FreeRTOS task scheduling jitter.
3. **Lower interrupt latency**: RP2040 bare-metal IRQ response is faster than ESP32-C3 FreeRTOS preempted IRQ dispatch.

ESP32-C3 SPI works (proven, reliable) but carries overhead from RTOS scheduling, WiFi/BT stack background tasks, and non-batched SPI calls.

## Architecture Decision

### ESP32-C3 ↔ RP2040 Boundary: COMPLETE PACKETS, Not SPI Commands

**CRITICAL DESIGN RULE**: The UART link between ESP32-C3 and RP2040 carries complete radio packets (max 255 bytes). It does NOT relay individual SPI transactions.

This avoids the "SPI-over-UART bottleneck" anti-pattern:
- BAD: ESP32-C3 sends each SPI opcode over UART → RP2040 executes it → returns result over UART. Each register read costs ~200µs UART round-trip. Thousands of transactions = unacceptable latency.
- GOOD: RP2040 runs the entire radio stack locally. ESP32-C3 sends "tx this packet" (255 bytes). RP2040 does all SPI work, IRQ handling, FIFO management autonomously. UART carries only the final product.

### Interface Contract

```
ESP32-C3                          RP2040
┌──────────────┐   UART (packet)  ┌──────────────────┐
│ Application  │  ──────────────► │ Radio Processor   │
│ FIPS mesh    │  "tx: [payload]" │ - LR2021 SPI      │
│ MeshCore     │                  │ - FIFO management │
│ GPS/telemetry│  ◄────────────── │ - IRQ handling    │
│ Nostr store  │  "rx: [payload]" │ - Packet framing  │
└──────────────┘   UART (packet)  └──────┬───────────┘
                                          │ SPI (20MHz batched)
                                   ┌──────┴───────┐
                                   │   LR2021     │
                                   │ 2.4GHz/868MHz│
                                   └──────────────┘
```

### Protocol (UART Packet Interface)

ESP32-C3 → RP2040 (TX command):
- Header: [START_BYTE] [CMD_TX] [LENGTH] 
- Payload: [0-255 bytes packet data]
- Trailer: [CRC8]

RP2040 → ESP32-C3 (RX notification):
- Header: [START_BYTE] [CMD_RX] [LENGTH]
- Payload: [0-255 bytes packet data + RSSI/SNR]
- Trailer: [CRC8]

RP2040 → ESP32-C3 (status):
- [START_BYTE] [CMD_TX_DONE] [IRQ_FLAGS_4BYTES]
- [START_BYTE] [CMD_ERROR] [ERROR_CODE]

### Pin Connections (Hub Board)

ESP32-C3 → RP2040 UART:
| ESP32-C3 GPIO | Function | RP2040 GPIO |
|---------------|----------|-------------|
| GPIO0 | UART1 TX | GP21 (RX) |
| GPIO1 | UART1 RX | GP20 (TX) |

RP2040 → LR2021 SPI:
| RP2040 GPIO | Function | LR2021 Pin |
|-------------|----------|------------|
| GP2 | SPI0 SCK | Pin 5 |
| GP3 | SPI0 MOSI | Pin 4 |
| GP4 | SPI0 MISO | Pin 3 |
| GP5 | GPIO CS (NSS) | Pin 6 |
| GP6 | BUSY | Pin 7 |
| GP7 | IRQ (DIO9) | Pin 15 |
| GP8 | RST | Pin 14 |

### Software Abstraction (C++ Interface)

The `Lr2021Radio` abstract class defines 9 methods:
```
init(), start_rx(), send_packet(), read_packet(),
get_irq_status(), clear_irq(), check_irq(), standby(), sleep()
```

Two implementations:

| Implementation | SPI Master | Use Case |
|---------------|-----------|----------|
| `EspHalLr2021Radio` | ESP32-C3 direct | Breadboard/dev testing, Phase 5 proof |
| `UartBridgeLr2021Radio` | RP2040 (via UART packets) | Flight PCB, production firmware |

Both satisfy the same interface. Firmware above the adapter layer (FIPS transport, MeshCore, TDMA) is identical regardless of which MCU drives the radio. Swap at compile time:
```cpp
#ifdef USE_RP2040_BRIDGE
    UartBridgeLr2021Radio radio(uart_port);
#else
    EspHalLr2021Radio radio(spi_pins);
#endif
    Lr2021Transport transport(&radio);
```

## Implementation Phasing

### Phase 5 (NOW — breadboard test)
- Use `EspHalLr2021Radio` — direct ESP32-C3 → LR2021 SPI
- Pin mapping from proven firmware: SCK=GP6, MOSI=GP7, MISO=GP2, CS=GP10, BUSY=GP4, IRQ=GP5, RST=GP3
- Throughput: 838 kbps (sufficient for FIPS handshake proof — we're sending 49-222 byte packets, not streaming)
- RP2040 NOT involved

### Post-Phase 5 (when flight PCB manufactured)
- Write `UartBridgeLr2021Radio` — ESP32-C3 → UART → RP2040 radio daemon → LR2021 SPI
- RP2040 firmware: radio daemon that owns SPI bus, handles IRQ, manages FIFO
- Throughput: 1377 kbps (64% faster, full production rate)

## Data Rate Context

### FIPS Handshake Traffic (Phase 5)
| Message | Size | Frequency |
|---------|------|-----------|
| MSG1 (initiator) | 98 bytes | Once per session |
| MSG2 (responder) | 49 bytes | Once per session |
| Encrypted payload | 222+32 = 254 bytes max | Per data exchange |
| GPS telemetry | 28 bytes | Periodic (1/min) |

At 838 kbps (ESP32-C3 direct), a 254-byte packet takes ~2.4ms air time + SPI overhead. Handshake completes in <100ms total. **ESP32-C3 direct is MORE than sufficient for Phase 5.**

### Mesh Relay Traffic (Flight — requires RP2040)
| Scenario | Required Throughput | ESP32-C3 (838 kbps) | RP2040 (1377 kbps) |
|----------|-------------------|---------------------|---------------------|
| Single FIPS link | ~9 kbps net | SUFFICIENT | SUFFICIENT |
| 4x MultiWAN bonded | ~36 kbps net | MARGINAL | SUFFICIENT |
| MeshCore sub-GHz relay | ~5 kbps | SUFFICIENT | SUFFICIENT |
| V2 PCB Yagi (+30dBm) | ~87 kbps net | INSUFFICIENT | SUFFICIENT |

For V1 flight (night-off, 22 kbps per link, 9 kbps net), ESP32-C3 could theoretically work. But with MultiWAN bonding or V2 power levels, RP2040 is required.

## Avoiding Bottlenecks — Design Rules

1. **Never relay SPI commands over UART.** UART carries complete packets only.
2. **RP2040 owns the SPI bus exclusively.** ESP32-C3 never touches SPI pins when RP2040 is active.
3. **RP2040 handles all IRQ locally.** TX_DONE/RX_DONE are processed on RP2040. ESP32-C3 gets a UART notification AFTER the packet is ready.
4. **UART baud rate must exceed packet throughput.** At 1 Mbps UART, a 255-byte packet takes 2ms. At 1377 kbps radio throughput, packets arrive every ~1.5ms. UART at 1 Mbps is insufficient — use **2 Mbps UART** or add flow control.
5. **Double-buffer on RP2040.** While one packet is being SPI-transmitted, the next UART packet can be received. Eliminates pipeline stalls.

## UART Baud Rate Requirement

| Radio Throughput | Packets/sec (255B) | UART Load at 1 Mbps | UART Load at 2 Mbps | Recommendation |
|-----------------|--------------------|--------------------|--------------------|----------------|
| 838 kbps (ESP32-C3) | ~410 | 84% | 42% | 1 Mbps OK |
| 1377 kbps (RP2040) | ~675 | 138% | 69% | **2 Mbps required** |

RP2040 radio daemon MUST use 2 Mbps UART. ESP-IDF supports this on ESP32-C3 (SPI2_HOST is separate from UART peripheral).

## Consequences

- Two firmware images needed for flight: ESP32-C3 application + RP2040 radio daemon
- RP2040 radio daemon is a new software deliverable (not yet written)
- The `Lr2021Radio` abstract interface keeps firmware portable between dev (direct SPI) and flight (UART bridge)
- ADR-020 (raw SPI, no RadioLib) applies to BOTH implementations
- Hub board schematic (ESP32→RP2040→LR2021 via UART+SPI) is the correct flight architecture

## Related ADRs

- ADR-002: LR2021 as RF chip
- ADR-020: Raw 2-byte opcode SPI (no RadioLib)
- ADR-024: Extract-only source repo policy
- ADR-025: Shared hardware flock mutex

## Data Sources

- `docs/lr2021-bottleneck-analysis-2026-07-29.md` — RP2040 vs ESP32-C3 SPI throughput
- `firmware/esp32-c3-flrc/main/main.cpp` — proven ESP32-C3 direct SPI (838 kbps)
- `firmware/rp2040/src/flrc_raw_tx.cpp` — proven RP2040 batched SPI (1377 kbps)
- `docs/lr2021-spi-protocol-reference.md` — 2-byte opcode protocol
- `tracker/hardware/hub_board/hub_schematic.py` — dual-MCU pin connections
