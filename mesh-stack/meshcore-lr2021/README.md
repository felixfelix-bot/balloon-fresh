# MeshCore LR2021 Integration Plan

**Created**: 2026-05-23
**Last Updated**: 2026-06-03
**Status**: Radio init VERIFIED on hardware. ESP-IDF HAL bypasses Arduino SPI. Companion + repeater built.
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

## Critical Finding: Arduino SPI Returns All Zeros

The Arduino `SPIClass` on ESP32-C3 returns all-zero responses from the LR2021 chip, causing `-707` (RADIOLIB_ERR_SPI_CMD_FAILED). The same hardware works perfectly with ESP-IDF's `spi_bus_initialize()`.

**Root cause**: The XIAO ESP32-C3 board definition (which PlatformIO uses for `board = xiao_esp32c3`) maps `MOSI=GPIO10`, which conflicts with our CS pin on GPIO10. Even with our custom board definition fixing `MOSI=GPIO7`, the Arduino SPI layer still returned zeros — likely a deeper issue with `SPIClass` initialization or DMA configuration.

**Solution**: `EspIdfHal.h` — a custom RadioLib HAL that bypasses Arduino SPI entirely and uses ESP-IDF's `spi_bus_initialize()` / `spi_device_polling_transmit()` directly. This is the same approach used in our tracker firmware's `EspHalC3.h`.

**Impact**: All 7 MeshCore LR2021 targets must use `EspIdfHal` instead of `SPIClass`. The `Module` constructor takes a `RadioLibHal*` parameter instead of `SPIClass&`.

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
| `patches/apply-patches.sh` | Copies variant files into MeshCore checkout + framework dir |

### Patches (copied into MeshCore clone by apply-patches.sh)

| # | Target in MeshCore clone | ~Lines | Content |
|---|--------------------------|--------|---------|
| 1 | `src/helpers/radiolib/CustomLR2021.h` | 45 | Extends `LR2021`, `std_init()`, `isReceiving()` using `LR11X0_IRQ_*` |
| 2 | `src/helpers/radiolib/CustomLR2021Wrapper.h` | 63 | Extends `RadioLibWrapper`, `isReceivingPacket()`, `getCurrentRSSI()`, `packetScore()` |
| 3 | `variants/nicerf_lr2021/EspIdfHal.h` | 130 | Custom RadioLib HAL using ESP-IDF SPI (bypasses Arduino SPIClass) |
| 4 | `variants/nicerf_lr2021/platformio.ini` | 80 | Build envs: companion/chat/kiss/repeater, pin defs |
| 5 | `variants/nicerf_lr2021/target.h` | 20 | Extern declarations |
| 6 | `variants/nicerf_lr2021/target.cpp` | 50 | `radio_init()`, ESP-IDF SPI HAL init, identity generation |
| 7 | `variants/nicerf_lr2021/NiceRFLR2021Board.h` | 65 | Board: deep sleep on GPIO5 (DIO9), battery ADC |
| 8 | `boards/esp32c3_supermini.json` | 30 | Board JSON: 4MB flash, DIO, USB CDC |
| 9 | `variants/esp32c3_supermini/pins_arduino.h` | 40 | SuperMini V1 pin mapping (D0-D10 = GPIO0-GPIO10) |

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

- [x] T0.1: Install PlatformIO (`pip install platformio`, verify `pio --version`) — PlatformIO 6.1.19
- [x] T0.2: Clone MeshCore and apply patches (`make setup`) — tag companion-v1.15.0
- [x] T0.3: Verify toolchain with existing variant (`make verify-toolchain`, build Xiao C3 companion) — BUILD SUCCESS
- [ ] T0.4: Wire LR2021 to ESP32-C3_Mini_V1 (9 wires + 8.2cm antenna on Pin 9)
- [ ] T0.5: Verify hardware with our tracker firmware (`idf.py -p /dev/ttyACM0 flash monitor`, radio init OK)

### Tier 1: Build Verification (automated, no hardware)

- [x] T1.1: CustomLR2021.h compiles (no errors) — fixed: added `getSpreadingFactor()` getter
- [x] T1.2: CustomLR2021Wrapper.h compiles (no errors) — fixed: uses `getSpreadingFactor()` instead of protected member
- [x] T1.3: companion_radio USB builds for LR2021 (`make build-companion`, BIN produced) — 501KB flash, 136KB RAM
- [x] T1.4: companion_radio BLE builds for LR2021 (`make build-companion-ble`, BIN produced) — 1226KB flash, 162KB RAM
- [x] T1.5: secure_chat builds for LR2021 (`make build-chat`, BIN produced) — 485KB flash, 88KB RAM
- [x] T1.6: kiss_modem builds for LR2021 (`make build-kiss`, BIN produced) — 457KB flash, 18KB RAM
- [x] T1.7: repeater builds for LR2021 (`make build-repeater`, BIN produced) — 1135KB flash, 51KB RAM
- [x] T1.8: room_server builds for LR2021 (`make build-room`, BIN produced) — 1129KB flash, 55KB RAM
- [x] T1.9: All binary sizes < 1.5 MB (fits ESP32-C3 4MB flash)

### Tier 2: Single-Device Hardware Tests (needs wired LR2021 board)

- [x] T2.1: Flash companion_radio to ESP32-C3 (`make flash-companion`)
- [x] T2.2: Radio init succeeds (no "radio init failed" error) — **VERIFIED** via ESP-IDF HAL
- [x] T2.3: MeshCore boot sequence completes (identity generated, SPIFFS mounted)
- [x] T2.4: Ed25519 identity generated and stored — `Repeater ID: D60BE809...`
- [x] T2.5: Noise floor calibration runs — **-102 dBm stable**, polls every ~2s
- [x] T2.6: MeshCore serial console responsive (via USB CDC)
- [x] T2.7: Companion app connects via USB (app.meshcore.nz or serial terminal) — **VERIFIED** via meshcore-cli
- [x] T2.8: Repeater firmware flashes and runs on ESP32-C3 SuperMini — 1.16MB flash
- [x] T2.9: Passive monitoring test (10+5 min) — **no Berlin community nodes in range**
  - Logs: `logs/meshcore_20260603_*.log`
  - Noise floor stable at -102 dBm, occasional -109 dBm recalibration
  - Radio RX confirmed working, no crashes in 15 min total

### Tier 3: Community Validation — meshcore-cli + Berlin MeshCore Network

**Objective**: Prove our LR2021 firmware communicates with real MeshCore nodes — receive adverts, send messages, confirm end-to-end encrypted chat.

**Tools**:
- `meshcore-cli` (Python): serial CLI for companion firmware — `pipx install meshcore-cli`
- MeshCore web app: https://app.meshcore.nz (connects via USB serial)
- MeshCore Discord: https://meshcore.gg (community hub, find nearby nodes)
- MeshCore node map: https://meshcore.io/map

**EU default PHY** (our firmware matches): 869.618 MHz, SF8, BW62.5, CR4/5, sync word 0x12

#### Phase 1: meshcore-cli Setup & Serial Connection (~15 min)

- [x] T3.P1.1: Install meshcore-cli: `pipx install meshcore-cli` — **v1.5.7 installed**
- [x] T3.P1.2: Flash companion_radio_usb: `make flash-companion`
- [x] T3.P1.3: Verify serial connection: `meshcli -s /dev/ttyACM2 infos`
  - Public key: `d60be809b4a1ae6b5d39269aa5298797847b10d3cf2c41bedee05801f29f26db`
  - Freq: 869.618, SF: 8, BW: 62.5, TX power: 22 dBm, Name: D60BE809
  - Contact URI: `meshcore://1100d60be809...`
- [x] T3.P1.4: Check clock: `meshcli clock` — synced to 2026-06-03
- [x] T3.P1.5: Send zero-hop advert: `meshcli advert` — **Advert sent**
- [x] T3.P1.6: Send flood advert: `meshcli floodadv` — **Advert sent**

#### Phase 2: Community Discovery (manual, ~15 min)

- [ ] T3.P2.1: Join MeshCore Discord at https://meshcore.gg
- [ ] T3.P2.2: Check #general, #eu-nodes for Berlin/Germany nodes
- [ ] T3.P2.3: Check MeshCore map at https://meshcore.io/map for Berlin pins
- [ ] T3.P2.4: Post in Discord: "Custom LR2021 node in Berlin on 869.618/SF8/BW62.5, looking for community nodes to test with"
- [ ] T3.P2.5: Note any Berlin/Germany node locations and approximate distances

#### Phase 3: Interactive Monitoring (~30 min)

- [x] T3.P3.1: Launch interactive mode: `meshcli -s /dev/ttyACM2`
- [x] T3.P3.2: Run `list` — check initial contact list — **0 contacts (empty)**
- [x] T3.P3.3: Run `advert` — broadcast self-advert — **Advert sent**
- [x] T3.P3.4: Run `floodadv` — flood advert (multi-hop reach) — **Advert sent**
- [x] T3.P3.5: Run `public "Hello from LR2021 in Berlin!"` — **sent to public channel**
- [x] T3.P3.6: Wait 10 min, run `list` again — **0 contacts, no community nodes in range**
- [x] T3.P3.7: Run `sync_msgs` — **no messages received**
- [x] T3.P3.8: Run `msgs_subscribe` for 10 min — **no incoming messages**
- [x] T3.P3.9: Results logged — **no Berlin MeshCore community nodes detected indoors**

#### Phase 4: Two-Device Self-Test (if no community nodes found)

Requires wiring a second LR2021 to another ESP32-C3 (20x ESP32-C3_Mini_V1 owned, 4x LR2021 owned).

- [x] T3.P4.1: Wire second LR2021 to second ESP32-C3_Mini_V1 (same pin mapping)
- [x] T3.P4.2: Flash companion_radio_usb on second device — Board 2: `53A53B5D` on `/dev/ttyACM3`
- [x] T3.P4.3: Place devices 2-5 meters apart
- [x] T3.P4.4: From device 1: `meshcli -s /dev/ttyACM2 advert` → Board 2 sees D60BE809 in contacts ✅
- [x] T3.P4.5: Check device 2 serial output for received advert — **bidirectional adverts confirmed**
- [ ] T3.P4.6: Test encrypted chat between the two devices
- [ ] T3.P4.7: Test repeater firmware on one device, companion on other
- [ ] T3.P4.8: Verify RSSI/SNR values reported by both devices

#### Phase 5: Outdoor/Portable Test (if indoor test finds nothing)

Repeater firmware runs headless — power from USB battery pack, no computer needed.

- [x] T3.P5.1: Flash repeater firmware: `make flash-repeater` — used companion + MeshCore app instead
- [x] T3.P5.2: Power from USB battery pack, place outdoors (balcony/window/rooftop) — brought to Freifunk meetup
- [x] T3.P5.3: Run monitoring — **70+ community nodes discovered** at Freifunk Berlin
- [x] T3.P5.4: Check results — bidirectional community interaction confirmed
- [x] T3.P5.5: Location: Freifunk meetup, Berlin

#### Phase 6: Map Registration & Community Engagement

- [ ] T3.P6.1: Export contact URI: `meshcli -s /dev/ttyACM2 card`
- [ ] T3.P6.2: Add node to MeshCore map (see FAQ 5.12)
- [ ] T3.P6.3: Post in Discord #show-and-tell: "Custom LR2021 + ESP32-C3 MeshCore node working"
- [ ] T3.P6.4: Prepare upstream PR: LR2021 variant for MeshCore

### Tier 3.5: FLRC Throughput Benchmark (mesh-stack/flrc-test/)

**Objective**: Measure actual FLRC throughput at 868 MHz and 2.4 GHz, compare with LoRa baselines.
**Firmware**: Custom PlatformIO project in `mesh-stack/flrc-test/`, using RadioLib FLRC API + EspIdfHal.

- [ ] FLRC.S1: Create `mesh-stack/flrc-test/` PlatformIO project
- [ ] FLRC.S2: Port EspIdfHal.h from meshcore-lr2021 project
- [ ] FLRC.S3: Implement TX firmware (configurable freq, bitrate, packet count, payload size)
- [ ] FLRC.S4: Implement RX firmware (receive, count packets, measure RSSI/SNR, report stats)
- [ ] FLRC.S5: Build and verify both TX/RX configs compile
- [ ] FLRC.T1: FLRC 868 MHz @ 325 kbps (1000 pkts, 50B each)
- [ ] FLRC.T2: FLRC 868 MHz @ 260 kbps (1000 pkts, 50B each)
- [ ] FLRC.T3: FLRC 2.4 GHz @ 1300 kbps (1000 pkts, 50B each) — FIPS target rate
- [ ] FLRC.T4: FLRC 2.4 GHz @ 2600 kbps (1000 pkts, 50B each) — max throughput
- [ ] FLRC.T5: LoRa 868 MHz SF9/BW125 baseline (1000 pkts, 50B each) — tracker comparison
- [ ] FLRC.T6: LoRa 868 MHz SF8/BW62.5 baseline (1000 pkts, 50B each) — MeshCore comparison
- [ ] FLRC.D1-D6: Distance tests at 2m, 5m, 10m, 20m, 50m, 100m (needs user)

### Tier 4: Two-Device Integration Tests (our board + friend's device)

- [ ] T4.1: PHY packet exchange same room (LR2021 TX → friend's device RX)
- [ ] T4.2: Reverse direction (friend's device TX → LR2021 RX)
- [ ] T4.3: Encrypted chat (simple_secure_chat, both devices)
- [ ] T4.4: Flood routing (2 nodes, broadcast)
- [ ] T4.5: Companion chat end-to-end (MeshCore app on both sides)
- [ ] T4.6: KISS modem serial bridge (send KISS DATA frame, get response)
- [ ] T4.7: RSSI vs distance plot (0m, 10m, 50m, 100m)
- [ ] T4.8: Max reliable range (urban, walk until >50% packet loss)

### Tier 5: Physical Long-Range Tests

- [ ] T5.1: Wall penetration (one device inside, one outside)
- [ ] T5.2: Cross-building test (500m+)
- [ ] T5.3: Budapest-Berlin via community MeshCore repeaters
- [ ] T5.4: Overnight reliability test (12+ hours, no crashes, >95% delivery)
- [ ] T5.5: Power consumption measurement (TX/RX/sleep current)

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
│   ├── apply-patches.sh        # Copies files into MeshCore checkout + framework dir
│   ├── CustomLR2021.h          # RadioLib radio wrapper
│   ├── CustomLR2021Wrapper.h   # MeshCore RadioLibWrapper subclass
│   ├── EspIdfHal.h             # ESP-IDF SPI HAL (bypasses Arduino SPIClass)
│   ├── boards/
│   │   └── esp32c3_supermini.json  # Board definition (4MB, DIO, USB CDC)
│   └── variant/
│       ├── platformio.ini      # Build environments + pin definitions
│       ├── target.h            # Extern declarations
│       ├── target.cpp          # Radio init via ESP-IDF HAL + identity generation
│       ├── NiceRFLR2021Board.h # Board class (deep sleep, battery)
│       └── esp32c3_supermini/
│           └── pins_arduino.h  # SuperMini V1 pin mapping (D0-D10 = GPIO0-GPIO10)
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
