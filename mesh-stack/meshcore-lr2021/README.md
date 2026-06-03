# MeshCore LR2021 Integration Plan

**Created**: 2026-05-23
**Status**: Implementation complete, ready for hardware testing
**Approach**: PlatformIO standalone (no fork maintenance)

## Goal

Send messages between Stettin (LR2021 on ESP32-C3) and Budapest (friend's MeshCore device) via MeshCore community mesh repeaters.

## Key Architecture Decision

MeshCore uses PlatformIO + Arduino. Our tracker uses ESP-IDF. **We do NOT integrate MeshCore into our ESP-IDF build.** Instead, we add an LR2021 variant to MeshCore's PlatformIO build, flash MeshCore firmware standalone for testing, and contribute the variant upstream.

**Why**: MeshCore has 85 releases, 2700+ commits, rapid evolution. Zero maintenance burden. Just `git pull` to update.

## RadioLib Class Hierarchy (Critical Finding)

```
PhysicalLayer
├── SX126x → SX1262 (MeshCore default, private: spreadingFactor)
├── LR11x0 → LR1110 (MeshCore already supported, sibling to LR2021)
└── LRxxxx → LR2021 (our chip, protected: spreadingFactor)
```

MeshCore already has `CustomLR1110.h`, `CustomLR1110Wrapper.h`, and `LR11x0Reset.h` — the LR1110 is a sibling chip to LR2021 (both in the LRxxxx family). Our implementation closely follows the LR1110 pattern.

Both LR1110 and LR2021 inherit from `PhysicalLayer`. MeshCore's `RadioLibWrapper` holds a `PhysicalLayer*`, so it accepts both. The key difference:

| Aspect | SX1262 | LR2021 |
|--------|--------|--------|
| RadioLib class | `SX1262` | `LR2021` (inherits `LRxxxx`) |
| `spreadingFactor` access | `private` (needs GODMODE) | `protected` (subclass access OK) |
| IRQ flags | `uint16_t getIrqFlags()` | `uint32_t getIrqFlags()` |
| Preamble detected | `SX126X_IRQ_PREAMBLE_DETECTED` | `RADIOLIB_LR11X0_IRQ_PREAMBLE_DETECTED` |
| Header valid | `SX126X_IRQ_HEADER_VALID` | `RADIOLIB_LR11X0_IRQ_SYNC_WORD_HEADER_VALID` |
| DIO2 as RF switch | Common | No (NiceRF handles RF switching internally) |
| TCXO | DIO3, configurable voltage | Internal, use 0.0 |
| IRQ pin | DIO1 | DIO9 (must call `setDioFunction(9)`) |

## RADIOLIB_GODMODE Resolution

MeshCore sets `RADIOLIB_GODMODE=1` in build flags. This makes `private:` → `public:` in RadioLib headers. For LR2021:

- `spreadingFactor` is `protected` in `LRxxxx` — already accessible from `CustomLR2021` subclass
- `mod` (Module*) is `protected` — accessible from subclass
- `getRssiInst()`, `calibrate()`, etc. become `public` with GODMODE — needed for wrapper access
- **We set `RADIOLIB_GODMODE=1` in our platformio.ini, same as all other variants**

## LR1110 Pattern (MeshCore Reference Implementation)

MeshCore already supports the LR1110 (LR11x0 family, sibling to LR2021). Our implementation follows this pattern closely:

| Feature | LR1110 Pattern | LR2021 Implementation |
|---------|---------------|----------------------|
| `isReceiving()` | `getIrqStatus()` + `LR11X0_IRQ_*` flags | Same — `getIrqStatus()` works on LRxxxx |
| `getCurrentRSSI()` | `getRssiInst(&rssi)` | Same method available on LR2021 |
| AGC reset | `lr11x0ResetAGC()` from `LR11x0Reset.h` | Custom inline — LR2021 lacks `calibrateImageRejection` |
| `onSendFinished()` | Sets preamble length to 16 | Same — overcomes weird packet size issues |
| `setRxBoostedGainMode()` | `bool en` parameter | `uint8_t level` (0-7) on LR2021, wrapped to match bool API |
| `spreadingFactor` access | Via GODMODE (private on LR1110) | Via subclass (protected on LRxxxx) |

Key difference: `lr11x0ResetAGC()` uses `calibrateImageRejection()` which is LR11x0-specific. LR2021 does image calibration automatically in `setFrequency()`, so our `doResetAGC()` calls `calibrate()` + `setFrequency()` instead.

## Hardware Wiring

```
ESP32-C3_Mini_V1  →  NiceRF LoRa2021
──────────────────────────────────────
3V3               →  Pin 1 (VCC)
GND               →  Pin 2,8,11,12,18 (at least one GND)
D2 (GPIO2)        →  Pin 3 (MISO)
D7 (GPIO7)        →  Pin 4 (MOSI)
D6 (GPIO6)        →  Pin 5 (SCK)
D10 (GPIO10)      →  Pin 6 (NSS/CS)
D4 (GPIO4)        →  Pin 7 (BUSY)
D3 (GPIO3)        →  Pin 14 (RST)
D5 (GPIO5)        →  Pin 15 (DIO9/IRQ)
```

Antenna: ~8.2 cm wire soldered to Pin 9 (Sub-GHz, 868 MHz quarter-wave).

## Files to Create

### In `mesh-stack/meshcore-lr2021/` (our repo, tracked by Makefile)

| File | Purpose |
|------|---------|
| `Makefile` | All build/flash/test/monitor commands |
| `README.md` | Setup, wiring, testing instructions |
| `patches/apply-patches.sh` | Copies variant files into MeshCore checkout |

### Patches (copied into MeshCore clone by apply-patches.sh)

| # | Target in MeshCore clone | ~Lines | Content |
|---|--------------------------|--------|---------|
| 1 | `src/helpers/radiolib/CustomLR2021.h` | 60 | Extends `LR2021`, `std_init()` with `setDioFunction(9)`, `isReceiving()` using `LR11X0_IRQ_*` |
| 2 | `src/helpers/radiolib/CustomLR2021Wrapper.h` | 45 | Extends `RadioLibWrapper`, `isReceivingPacket()`, `getCurrentRSSI()`, `packetScore()` |
| 3 | `variants/nicerf_lr2021/platformio.ini` | 80 | Build envs: companion/chat/kiss/repeater, pin defs |
| 4 | `variants/nicerf_lr2021/target.h` | 20 | Extern declarations |
| 5 | `variants/nicerf_lr2021/target.cpp` | 55 | `radio_init()`, SPI begin, identity generation |
| 6 | `variants/nicerf_lr2021/NiceRFLR2021Board.h` | 65 | Board: deep sleep on GPIO5 (DIO9), battery ADC |

## Pin Mapping (platformio.ini build flags)

```ini
-D P_LORA_SCLK=6
-D P_LORA_MISO=2
-D P_LORA_MOSI=7
-D P_LORA_DIO_1=5
-D P_LORA_NSS=10
-D P_LORA_RESET=3
-D P_LORA_BUSY=4
-D USE_LR2021
-D RADIO_CLASS=CustomLR2021
-D WRAPPER_CLASS=CustomLR2021Wrapper
-D LORA_TX_POWER=22
-D ESP32_CPU_FREQ=80
```

## MeshCore PHY Settings (EU default, NOT our tracker settings)

| Parameter | Value | Our tracker uses |
|-----------|-------|------------------|
| Frequency | 869.618 MHz | 868.0 MHz |
| Bandwidth | 62.5 kHz | 125.0 kHz |
| Spreading Factor | 8 | 9 |
| Coding Rate | 4/5 | 4/7 |
| Sync Word | 0x12 (private) | 0x12 (private) |

These are **incompatible** — MeshCore and our tracker firmware cannot hear each other directly. This is by design (ADR-012: Sub-GHz = MeshCore, 2.4 GHz = FIPS).

## Makefile Targets

**MeshCore version**: Pinned to `companion-v1.15.0` release tag for reproducibility. Update `MESHCORE_TAG` in Makefile to change.

```makefile
make setup              # pip install platformio + git clone MeshCore + apply patches
make verify-toolchain   # build existing Xiao C3 variant (confirms toolchain works)
make build-companion    # companion_radio USB for LR2021
make build-companion-ble # companion_radio BLE for LR2021
make build-chat         # simple_secure_chat for LR2021
make build-kiss         # kiss_modem for LR2021
make build-repeater     # simple_repeater for LR2021
make build-all          # all of above
make flash-companion    # flash companion to /dev/ttyACM0
make flash-chat         # flash chat to /dev/ttyACM0
make flash-kiss         # flash KISS modem to /dev/ttyACM0
make monitor            # serial monitor 115200 baud
make test-t1            # Tier 1: verify all builds succeed (automated)
make clean              # clean PlatformIO build artifacts
make dist-clean         # remove MeshCore clone entirely
```

## Test Plan

### Tier 0: Prerequisites (manual, tracked in Makefile)

- [ ] T0.1: Install PlatformIO (`pip install platformio`, verify `pio --version`)
- [ ] T0.2: Clone MeshCore and apply patches (`make setup`)
- [ ] T0.3: Verify toolchain with existing variant (`make verify-toolchain`, build Xiao C3 companion)
- [ ] T0.4: Wire LR2021 to ESP32-C3_Mini_V1 (9 wires + 8.2cm antenna on Pin 9)
- [ ] T0.5: Verify hardware with our tracker firmware (`idf.py -p /dev/ttyACM0 flash monitor`, radio init OK)

### Tier 1: Build Verification (automated, no hardware)

- [ ] T1.1: CustomLR2021.h compiles (no errors)
- [ ] T1.2: CustomLR2021Wrapper.h compiles (no errors)
- [ ] T1.3: companion_radio USB builds for LR2021 (`make build-companion`, BIN produced)
- [ ] T1.4: companion_radio BLE builds for LR2021 (`make build-companion-ble`, BIN produced)
- [ ] T1.5: secure_chat builds for LR2021 (`make build-chat`, BIN produced)
- [ ] T1.6: kiss_modem builds for LR2021 (`make build-kiss`, BIN produced)
- [ ] T1.7: repeater builds for LR2021 (`make build-repeater`, BIN produced)
- [ ] T1.8: room_server builds for LR2021 (`make build-room`, BIN produced)
- [ ] T1.9: All binary sizes < 1.5 MB (fits ESP32-C3 4MB flash)

### Tier 2: Single-Device Hardware Tests (needs wired LR2021 board)

- [ ] T2.1: Flash companion_radio to ESP32-C3 (`make flash-companion`)
- [ ] T2.2: Serial boot output shows MeshCore boot messages
- [ ] T2.3: Radio init succeeds (no "radio init failed" error)
- [ ] T2.4: Ed25519 identity generated and stored
- [ ] T2.5: Noise floor calibration runs (RSSI values in log every ~2s)
- [ ] T2.6: MeshCore serial console responsive
- [ ] T2.7: Companion app connects via USB (app.meshcore.nz or serial terminal)

### Tier 3: Two-Device Integration Tests (our board + friend's device)

- [ ] T3.1: PHY packet exchange same room (LR2021 TX → friend's device RX)
- [ ] T3.2: Reverse direction (friend's device TX → LR2021 RX)
- [ ] T3.3: Encrypted chat (simple_secure_chat, both devices)
- [ ] T3.4: Flood routing (2 nodes, broadcast)
- [ ] T3.5: Companion chat end-to-end (MeshCore app on both sides)
- [ ] T3.6: KISS modem serial bridge (send KISS DATA frame, get response)
- [ ] T3.7: RSSI vs distance plot (0m, 10m, 50m, 100m)
- [ ] T3.8: Max reliable range (urban, walk until >50% packet loss)

### Tier 4: Physical Long-Range Tests

- [ ] T4.1: Wall penetration (one device inside, one outside)
- [ ] T4.2: Cross-building test (500m+)
- [ ] T4.3: Budapest-Stettin via community MeshCore repeaters
- [ ] T4.4: Overnight reliability test (12+ hours, no crashes, >95% delivery)
- [ ] T4.5: Power consumption measurement (TX/RX/sleep current)

## KISS Modem Integration (Future)

The KISS modem firmware exposes MeshCore over serial with standard KISS TNC framing (115200 baud). This is the bridge to our ground station:

```
LR2021 + MeshCore KISS modem firmware
  ↕ (serial, KISS protocol)
ESP32-C3 + our tracker firmware (or laptop + ground_station.py)
  ↕ (WiFi/Nostr)
Internet
```

KISS protocol reference: `docs/kiss_modem_protocol.md` in MeshCore repo.

## Upstream Contribution

Once the LR2021 variant works, contribute it to MeshCore:
1. Fork `meshcore-dev/MeshCore` on GitHub
2. Create branch `feature/nicerf-lr2021-variant`
3. Add `CustomLR2021.h`, `CustomLR2021Wrapper.h`, `variants/nicerf_lr2021/`
4. Submit PR with test results

This means future MeshCore releases include LR2021 support natively.

## Directory Structure

```
mesh-stack/meshcore-lr2021/
├── Makefile                    # Build/flash/test automation
├── README.md                   # This file
├── patches/
│   ├── apply-patches.sh        # Copies files into MeshCore checkout
│   ├── CustomLR2021.h          # RadioLib radio wrapper
│   ├── CustomLR2021Wrapper.h   # MeshCore RadioLibWrapper subclass
│   └── variant/
│       ├── platformio.ini      # Build environments + pin definitions
│       ├── target.h            # Extern declarations
│       ├── target.cpp          # Radio init + identity generation
│       └── NiceRFLR2021Board.h # Board class (deep sleep, battery)
└── MeshCore/                   # Cloned by `make setup` (gitignored)
```

## References

- MeshCore repo: https://github.com/meshcore-dev/MeshCore
- MeshCore KISS modem protocol: `docs/kiss_modem_protocol.md` in MeshCore repo
- MeshCore flasher: https://meshcore.io/flasher
- MeshCore web app: https://app.meshcore.nz
- MeshCore Discord: https://meshcore.gg
- Our LR2021 study: `mesh-stack/research/routing/meshcore-study.md`
- Our RadioLib wrapper study: `mesh-stack/research/meshcore-radiolib-wrapper-study.md`
- Our ADR-012: `docs/adr/012-mesh-networking-strategy.md`
- RadioLib LR2021 class: `tracker/firmware/components/RadioLib/src/modules/LR2021/LR2021.h`
- RadioLib LRxxxx base: `tracker/firmware/components/RadioLib/src/modules/LR11x0/LR_common.h`
- RadioLib PhysicalLayer: `tracker/firmware/components/RadioLib/src/protocols/PhysicalLayer/PhysicalLayer.h`
- Our pin mapping: `AGENTS.md` (NiceRF LoRa2021 section)
- Our wiring guide: `docs/execution-checklist.md`
