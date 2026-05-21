# MeshCore Study — LR2021 Port Assessment

**Date**: 2026-05-21
**Status**: Research complete, implementation pending

## TL;DR

MeshCore is a lightweight LoRa mesh stack with clean radio abstraction. LR2021 sub-GHz LoRa port is **medium-easy** (2-4 hours on PlatformIO). Core mesh networking (~1,500 lines C++) is framework-agnostic and extractable for ESP-IDF. No fragmentation, no 2.4 GHz, no TDMA.

## 1. Project Overview

| Attribute | Value |
|-----------|-------|
| Repo | https://github.com/meshcore-dev/MeshCore |
| License | MIT |
| Stars | 2.9k |
| Language | C (61.5%), C++ (37.2%) |
| Framework | PlatformIO + Arduino |
| RadioLib version | v7.6.0 (same as ours) |
| Supported MCUs | ESP32, ESP32-S3, ESP32-C3, ESP32-C6, NRF52, RP2040, STM32 |
| Supported radios | SX1262, SX1268, SX1276, LLCC68, LR1110, STM32WLx |

**MeshCore is NOT Meshtastic** — it's a separate, simpler project focused on lightweight multi-hop routing with Ed25519 identity and AES-128 encryption.

## 2. Build System

**PlatformIO + Arduino only. NOT ESP-IDF native.**

Key build flags:
```
-D LORA_FREQ=869.618      # EU frequency
-D LORA_BW=62.5           # 62.5 kHz bandwidth
-D LORA_SF=8              # Spreading Factor 8
-D RADIOLIB_STATIC_ONLY=1
-D RADIOLIB_GODMODE=1     # Access protected RadioLib members
```

**SX128x is excluded** via `RADIOLIB_EXCLUDE_SX128X`. Sub-GHz LoRa only.

### Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| RadioLib | ^7.6.0 | Radio driver (same as ours) |
| rweather/Crypto | ^0.4.0 | Ed25519, AES-128, SHA-256 |
| adafruit/RTClib | ^2.1.3 | RTC support |
| CayenneLPP | 1.6.1 | Sensor data encoding |

## 3. Radio Abstraction Layer (Key for Porting)

### 3.1 Abstract Interface (`mesh::Radio` in `Dispatcher.h`)

```cpp
class Radio {
  virtual void begin();
  virtual int recvRaw(uint8_t* bytes, int sz) = 0;
  virtual uint32_t getEstAirtimeFor(int len_bytes) = 0;
  virtual float packetScore(float snr, int packet_len) = 0;
  virtual bool startSendRaw(const uint8_t* bytes, int len) = 0;
  virtual bool isSendComplete() = 0;
  virtual void onSendFinished() = 0;
  virtual void loop();
  virtual int getNoiseFloor() const;
  virtual void triggerNoiseFloorCalibrate(int threshold);
  virtual void resetAGC();
  virtual bool isInRecvMode() const = 0;
  virtual bool isReceiving();
  virtual float getLastRSSI() const;
  virtual float getLastSNR() const;
};
```

Only **14 methods** to implement. Clean, chip-agnostic.

### 3.2 Base Implementation (`RadioLibWrapper`)

Wraps any RadioLib `PhysicalLayer*`:
```cpp
class RadioLibWrapper : public mesh::Radio {
  PhysicalLayer* _radio;
  MainBoard* _board;
  // Interrupt-driven state machine: IDLE -> RX -> TX_WAIT -> TX_DONE
};
```

Handles: interrupt-driven RX/TX state machine, noise floor calibration (64 RSSI samples), channel activity detection (RSSI-based), airtime estimation.

### 3.3 Chip-Specific Pattern

Each radio chip has two files:
1. `Custom<Chip>.h` — extends RadioLib chip class with `std_init()` + `isReceiving()`
2. `Custom<Chip>Wrapper.h` — extends `RadioLibWrapper` with chip-specific `isReceivingPacket()` + `getCurrentRSSI()`

Example (SX1262):
```cpp
class CustomSX1262 : public SX1262 {
  bool std_init(SPIClass* spi = NULL) {
    if (spi) spi->begin(P_LORA_SCLK, P_LORA_MISO, P_LORA_MOSI);
    int status = begin(LORA_FREQ, LORA_BW, LORA_SF, cr, syncWord, txPower, 16, tcxo);
    setCRC(1);
    setCurrentLimit(140);
    setDio2AsRfSwitch(true);
    setRxBoostedGainMode(1);
    setRfSwitchPins(SX126X_RXEN, SX126X_TXEN);
    return true;
  }
  bool isReceiving() {
    uint16_t irq = getIrqFlags();
    return (irq & SX126X_IRQ_HEADER_VALID) || (irq & SX126X_IRQ_PREAMBLE_DETECTED);
  }
};
```

## 4. Protocol / PHY Layer

### 4.1 PHY Settings

| Parameter | Value | Notes |
|-----------|-------|-------|
| Frequency | 869.618 MHz | EU ISM band |
| Modulation | LoRa | Sub-GHz only |
| SF | 8 | Moderate data rate |
| BW | 62.5 kHz | Narrow, good range |
| CR | 4/5 | Default |
| TX Power | 22 dBm | Per-variant |
| Sync Word | 0x12 | LoRa private |
| Preamble | 16 bytes | Standard |
| Max packet | 255 bytes | `MAX_TRANS_UNIT` |
| Max payload | 184 bytes | `MAX_PACKET_PAYLOAD` |

### 4.2 Medium Access: CSMA-like (NO TDMA)

MeshCore does **not** use TDMA. It uses CSMA with:
1. **Channel Activity Detection** — RSSI + preamble/header detection before TX
2. **Random jittered retransmit** — delay = `(pow(10, 0.85 - score) - 1.0) * airtime + random * halfAirtime`
3. **Duty cycle management** — 50% airtime budget in 1-hour window
4. **AGC reset** — periodic warm-sleep to prevent receiver desensitization
5. **Noise floor calibration** — 64 RSSI samples averaged, every 2 seconds

### 4.3 Routing: Hybrid Flood + Direct

**Flood routing** (discovery/broadcast):
- Source sends packet with empty path
- Repeaters append 1-byte hash to path
- Retransmit delay inversely proportional to SNR
- 128-entry cyclic hash table for deduplication
- Up to 64 hops

**Direct routing** (established paths):
- Source routing: sender specifies full path
- Path discovery via flood request
- Reciprocal paths exchanged automatically
- Multi-ACK support

### 4.4 Encryption & Identity

- **Ed25519** for identity (public/private key, signatures)
- **X25519** ECDH for shared secret
- **AES-128** CTR mode encryption
- **MAC-then-Encrypt** pattern (2-byte MAC)
- Identity hash = first byte of Ed25519 public key

## 5. LR2021 Port Assessment

### The LR2021 vs SX1262

| Aspect | SX1262 | LR2021 |
|--------|--------|--------|
| Sub-GHz LoRa | Yes | Yes (register-compatible) |
| 2.4 GHz LoRa | No | Yes (separate antenna) |
| DIO pins | DIO1 (IRQ) | DIO9 (need `setDioFunction()`) |
| RadioLib class | `SX1262` | No native class, use `SX1262` |

**Key insight**: LR2021 sub-GHz radio core is **register-compatible with SX1262**. The `SX1262` RadioLib class should work. Only difference: DIO9 vs DIO1 for IRQ mapping.

### Port Effort: MEDIUM-EASY (PlatformIO)

**Steps:**

1. **Create `variants/nicerf_lr2021/platformio.ini`**:
```ini
[nicerf_lr2021]
extends = esp32_base
board = esp32-c3-devkitm-1
build_flags =
  ${esp32_base.build_flags}
  -D P_LORA_DIO_1=5
  -D P_LORA_NSS=10
  -D P_LORA_RESET=3
  -D P_LORA_BUSY=4
  -D P_LORA_SCLK=6
  -D P_LORA_MISO=2
  -D P_LORA_MOSI=7
  -D USE_SX1262
  -D RADIO_CLASS=CustomSX1262
  -D WRAPPER_CLASS=CustomSX1262Wrapper
  -D LORA_TX_POWER=22
```

2. **Create `variants/nicerf_lr2021/target.h` and `target.cpp`** — copy from `tenstar_c3/`, change pins

3. **Handle DIO9 mapping** — add `setDioFunction(9)` in `CustomSX1262::std_init()`

4. **Remove `SX126X_DIO2_AS_RF_SWITCH`** — NiceRF has its own RF switch

**Estimated effort**: 2-4 hours for working sub-GHz LoRa.

### Port Effort: HARD (ESP-IDF native)

MeshCore is deeply Arduino-coupled (`#include <Arduino.h>` throughout, Arduino SPI/Wire/Serial/SPIFFS). Two paths:

**Option A**: Arduino as ESP-IDF component (+200 KB binary, but works)
**Option B**: Extract core networking only (recommended for flight)

### Option B: Core Extraction (~1,500 lines)

**Framework-agnostic core files:**

| File | Lines | Purpose |
|------|-------|---------|
| `src/MeshCore.h` | ~50 | Constants |
| `src/Packet.h/.cpp` | ~200 | Packet format, serialization |
| `src/Dispatcher.h/.cpp` | ~350 | Radio dispatch, CSMA, airtime |
| `src/Mesh.h/.cpp` | ~500 | Mesh routing (flood + direct) |
| `src/Identity.h/.cpp` | ~300 | Ed25519 identity, ECDH |
| `src/Utils.h/.cpp` | ~200 | SHA-256, AES-128, MAC |
| `src/helpers/SimpleMeshTables.h` | ~100 | Dedup tables |
| `src/helpers/StaticPoolPacketManager.h/.cpp` | ~150 | Packet pool |

**Interfaces to implement (7):**
1. `mesh::Radio` — our RadioLib SX1262 wrapper already provides this
2. `mesh::MillisecondClock` — `esp_timer_get_time() / 1000`
3. `mesh::RNG` — `esp_random()`
4. `mesh::RTCClock` — GPS time or deep sleep RTC
5. `mesh::PacketManager` — static pool (already provided)
6. `mesh::MeshTables` — dedup (already provided)
7. `mesh::MainBoard` — battery, sleep, LEDs

**External dependency**: `rweather/Crypto` (pure C++, no Arduino dependency, portable)

**Estimated extraction effort**: 1-2 days.

## 6. ESP32-C3 Variant References

MeshCore already has ESP32-C3 variants:

### `variants/xiao_c3/` (Seeed XIAO ESP32-C3 + SX1262)
- Most relevant reference for our dev boards
- Uses Arduino `SPIClass`

### `variants/tenstar_c3/` (Tenstar ESP32-C3 + SX1262/68)
- Uses raw GPIO pin numbers matching bare ESP32-C3 chip
- Pin mapping: MISO=9, SCLK=8, MOSI=7, DIO_1=2, NSS=6, RESET=NC, BUSY=3

## 7. What We Get from MeshCore

| Feature | Provided by MeshCore | Notes |
|---------|---------------------|-------|
| Multi-hop routing | Flood + direct source routing | Up to 64 hops |
| Identity | Ed25519 public/private keys | Compatible with Nostr |
| Encryption | AES-128 CTR + MAC-then-Encrypt | Per-session keys via ECDH |
| Deduplication | 128-entry cyclic hash table | Prevents loops |
| CSMA | RSSI-based CAD + random backoff | No TDMA scheduling |
| Airtime budget | 50% duty cycle tracking | EU compliance |
| Fragmentation | **NOT IMPLEMENTED** | Need our own |
| 2.4 GHz support | **NOT AVAILABLE** | Need custom for LR2021 2.4 GHz |

## 8. Compatibility with Our Stack

| Concern | Impact | Mitigation |
|---------|--------|------------|
| Arduino framework required | HIGH | Extract core only for flight |
| `RADIOLIB_GODMODE=1` | MEDIUM | Used for protected member access; handle in extraction |
| No TDMA | MEDIUM | We add our own TDMA layer on top |
| No fragmentation | HIGH | Use our Wirehair/PRBS23-XOR layer |
| SX128x excluded | MEDIUM | Sub-GHz only for MeshCore; 2.4 GHz is separate FIPS path |
| No FLRC support | LOW | MeshCore is LoRa-only; FLRC is for our FIPS transport |
| CSMA vs our planned TDMA | MEDIUM | CSMA works for community mesh; TDMA for FIPS transport |

## 9. Implementation Tasks

### Quick Integration (dev/testing, PlatformIO)
- [ ] Fork MeshCore, create `variants/nicerf_lr2021/`
- [ ] Pin mapping for NiceRF LoRa2021 (DIO9→GPIO5, NSS→GPIO10, etc.)
- [ ] DIO9 IRQ mapping via `setDioFunction()`
- [ ] Build and flash on ESP32-C3_Mini_V1
- [ ] Bench test: 2 nodes, flood routing, encryption
- [ ] Range test: MeshCore SF8/BW62.5 vs our SF9/BW125

### Clean Extraction (flight firmware, ESP-IDF)
- [ ] Copy core files (Packet, Dispatcher, Mesh, Identity, Utils, helpers)
- [ ] Implement 7 interfaces (Radio, Clock, RNG, RTC, PacketManager, MeshTables, MainBoard)
- [ ] Port `rweather/Crypto` as ESP-IDF component
- [ ] Remove `RADIOLIB_GODMODE` dependency
- [ ] Integrate with our existing RadioLib ESP-IDF HAL
- [ ] Add fragmentation/erasure coding layer (Wirehair/PRBS23-XOR)
- [ ] Add TDMA scheduler for FIPS transport
