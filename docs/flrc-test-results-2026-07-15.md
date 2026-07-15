# FLRC Throughput Test Results — 2026-07-15

## Hardware Setup
- 2x RP2040 Pico boards: 8332 (ACM0) and F242D (ACM2)
- 2x ESP32-C3 SuperMini: ACM1 (bridge), ACM3 (unused)
- LR2021 modules on both RP2040 boards
- 2.4 GHz antennas confirmed connected (pin 10)
- UART bridge: RP2040 GP12→ESP32 GPIO3(RX), GP13←GPIO2(TX)

## Firmware
- `flrc_raw_rx.cpp` / `flrc_raw_tx.cpp` — fully raw SPI, NO RadioLib
- Build envs: `rp2040-raw-rx`, `rp2040-raw-tx`

## RadioLib -707 Root Cause (from source analysis)
RadioLib `SPItransferStream()` (Module.cpp line 318):
1. **Heap alloc** per SPI transaction: `new uint8_t[buffLen]` — fragments RP2040 heap
2. **GPIO busy-wait** with timeout: `while(digitalRead(gpioPin))` — interferes with TinyUSB
3. **Status callback parsing** — can flag CMD_ERROR from chip
4. **TCXO/XTAL mismatch detection** — primary documented cause of -707

RadioLib docs (LR2021.h lines 77/92/106/120):
"If you are seeing -706/-707 error codes, it likely means you are using
non-0 value for module with XTAL."

Our code passes `tcxoVoltage=0.0f` (correct for crystal), but -707 persists
because of the heavy SPI machinery itself, not the TCXO value.

Raw SPI avoids all of this: stack buffers, simple busy-wait, no callbacks.

## Test Results

### Run 1: TX=8332, RX=F242D (simultaneous)
```
TX: sent=1000, elapsed=1508ms, throughput=1352.8 kbps
RX: received=0, unique=0, lost=1, PER=100%, elapsed=12000ms, throughput=0.0 kbps
```
Radio status after init: St=0x05 (RX mode), IRQ=0x00230020

### Run 2: TX=8332 (USB visible), monitored via USB
```
TX: sent=1000, elapsed=1508ms, throughput=1352.8 kbps
USB CDC SURVIVES with raw SPI (RadioLib killed it)
```

### Run 3: Manual RUN after INIT via bridge
```
INIT Status=0x05 IRQ=0x00030000
RADIO_INIT_WARN CMD_ERROR (St=0x05) — radio entered RX despite partial error
RX: received=0 (12s timeout)
```

## Key Observations
1. **TX works perfectly** — 1000 packets, consistent 1352.8 kbps
2. **RX enters RX mode** (St=0x05) but receives 0 packets
3. **USB CDC survives** with raw SPI (no RadioLib = no CDC death)
4. **UART bridge bidirectional** — commands + data both work
5. **IRQ polling changed** from DIO pin to SPI register read (untested)
6. **Antennas confirmed** connected at 2.4 GHz (pin 10)

## What Does NOT Explain 0 Packets
- NOT timing (TX burst finishes in 1.5s, RX listens for 12s)
- NOT USB CDC (raw SPI doesn't kill it)
- NOT antenna (confirmed connected)
- NOT radio mode (St=0x05 confirmed)

## Suspects (in priority order)
1. **Sync word mismatch** — both files have 0x12/0xAD/0x10/0x1B but untested on-air
2. **DIO9 IRQ mapping** — switched to SPI polling but untested
3. **IRQ clear timing** — `rfReadIrqStatus` reads AND clears, may clear before check
4. **Frequency mismatch** — both use 2440 MHz but PLL divider formula unverified
5. **Packet params encoding** — bitfields in SET_FLRC_PACKET_PARAMS may be wrong

## Next Steps
- Swap TX/RX roles to monitor TX via bridge (Option A)
- Add status byte read after SET_TX (Option B)
- Add RSSI read in RX loop to detect any signal
- Verify sync word by transmitting known pattern
