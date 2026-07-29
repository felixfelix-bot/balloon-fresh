# ADR 019: GPS-Synchronized Time-Division Mode Switching

## Status
Accepted (2026-07-22)

## Context
ADR-018 defines a 10-config sweep that takes ~55 seconds. For the sweep to work, TX and RX boards must switch to the same mode at the same time. The TX board is battery-powered and carried by a walking operator. The RX board is connected to a computer on a balcony.

Options for synchronization:
1. Button-triggered (TX starts sweep, computer script starts RX simultaneously) — simple but requires manual coordination
2. GPS time sync (both boards read UTC from GPS, agree on schedule) — autonomous, robust

The operator will connect a GEP-M10 GPS module to the TX board. The RX board gets time from the connected computer (NTP-synced system clock).

## Decision

### Phase 1: Button-Triggered Synchronization
For immediate testing (next field walk):
- TX board has a button (GP15 pulled up, pressed = GPIO low)
- Pressing button starts the 55-second sweep on TX
- TX transmits a "SWEEP_START" packet with config index 0
- RX detects SWEEP_START via the logger script and starts a parallel timer
- RX firmware switches modes on the same 55-second schedule
- If SWEEP_START is missed, RX falls back to time-based detection

### Phase 2: GPS Time Sync (Future)
For autonomous operation:
- GEP-M10 connected to TX board via UART0 (GP0/GP1)
- PPS pin connected to GP14 for microsecond accuracy
- Both TX and RX agree on epoch: every minute boundary (UTC second 0)
- Schedule: sweep starts at minute boundary, 55s sweep + 5s guard = 60s cycle
- TX board embeds GPS position + timestamp in each packet
- RX board timestamps each received packet using system clock

### GEP-M10 Wiring (TX Board)

```
GEP-M10 Pin  →  RP2040 Pin  →  Function
VCC          →  3V3 (pin 36)   Power (3.3V)
GND          →  GND (pin 38)   Ground
TX           →  GP1            GPS NMEA output → RP2040 UART0 RX
RX           →  GP0            GPS config input ← RP2040 UART0 TX
PPS          →  GP14           1 pulse-per-second interrupt
```

Default baud: 9600 (configurable to 38400 in firmware).

### Pin Assignment Summary (TX Board)

```
GP0   = UART0 TX → GPS RX
GP1   = UART0 RX ← GPS TX
GP2   = SPI SCK (LR2021)
GP3   = SPI MOSI (LR2021)
GP4   = SPI MISO (LR2021)
GP5   = SPI CS (LR2021)
GP6   = BUSY (LR2021)
GP7   = IRQ (LR2021)
GP8   = RST (LR2021)
GP9   = DIO9 (LR2021)
GP12  = Serial1 TX (UART bridge to ESP32)
GP13  = Serial1 RX (UART bridge)
GP14  = GPS PPS interrupt
GP15  = Sweep button (pulled up, active low)
```

### Packet Format

Each TX packet contains:
```
Byte 0:   Mode ID (0-9, identifies which sweep config)
Bytes 1-4: Sequence number (uint32, per-mode counter)
Bytes 5-8: Timestamp (uint32, UTC seconds from GPS or boot millis)
Bytes 9-12: GPS lat (int32, degrees * 1e7)
Bytes 13-16: GPS lon (int32, degrees * 1e7)
Byte 17:  GPS sats
Bytes 18-19: GPS alt (int16, meters)
Bytes 20+: Padding
```

The RX logger matches Mode ID + Sequence to verify both boards are synchronized.

## Consequences
- Phase 1 can be deployed immediately without GPS hardware
- Phase 2 requires GPS module soldering but enables autonomous walks
- Packet format changes (new fields for mode, GPS)
- RX logger must be updated to parse new packet format
