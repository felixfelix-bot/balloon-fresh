# MeshCore RadioLibWrapper Study for LR2021

## Summary

MeshCore's radio interface is a simple abstract class (`mesh::Radio`) with 6 core methods. The `RadioLibWrapper` implements this using RadioLib's `PhysicalLayer*` pointer. Porting to LR2021 requires implementing these 6 methods plus a few RadioLib-specific helpers.

## MeshCore Radio Interface (`mesh::Radio`)

Defined in `src/Dispatcher.h`:

```cpp
class Radio {
public:
    virtual void begin() { }
    virtual int recvRaw(uint8_t* bytes, int sz) = 0;           // Poll for incoming packet
    virtual uint32_t getEstAirtimeFor(int len_bytes) = 0;       // Estimated TX airtime (ms)
    virtual float packetScore(float snr, int packet_len) = 0;   // Packet quality score
    virtual bool startSendRaw(const uint8_t* bytes, int len) = 0; // Start async TX
    virtual bool isSendComplete() = 0;                          // Check TX complete
    virtual void onSendFinished() = 0;                          // Post-TX cleanup
    virtual void loop() { }                                     // Per-cycle processing
    virtual int getNoiseFloor() const { return 0; }
    virtual void triggerNoiseFloorCalibrate(int threshold) { }
    virtual void resetAGC() { }
    virtual bool isInRecvMode() const = 0;                      // Is radio in RX mode?
    virtual bool isReceiving() { return false; }                // Mid-receive?
    virtual float getLastRSSI() const { return 0; }
    virtual float getLastSNR() const { return 0; }
};
```

### Required Methods (pure virtual)

| Method | Purpose | RadioLib Equivalent |
|--------|---------|-------------------|
| `recvRaw(bytes, sz)` | Poll for received packet | `radio.readData()`, check IRQ flags |
| `getEstAirtimeFor(len)` | Estimate TX airtime in ms | `radio.getTimeOnAir(len) / 1000` |
| `packetScore(snr, len)` | Quality score for routing | Custom formula based on SNR + SF |
| `startSendRaw(bytes, len)` | Start async transmit | `radio.startTransmit()` |
| `isSendComplete()` | Check if TX done | Check IRQ flag / DIO pin |
| `isInRecvMode()` | Check if in RX state | Track state internally |

### Optional Methods (have defaults)

| Method | Purpose | Notes |
|--------|---------|-------|
| `begin()` | Initialize radio | Called at startup |
| `loop()` | Per-cycle processing | CAD, noise floor cal |
| `isReceiving()` | Detect ongoing RX | CAD-based detection |
| `getNoiseFloor()` | Current noise level | For adaptive routing |
| `getLastRSSI/SNR()` | Last packet quality | For logging/routing |
| `resetAGC()` | Reset AGC | After TX burst |

## RadioLibWrapper Implementation

MeshCore's wrapper (`src/helpers/radiolib/RadioLibWrappers.h/.cpp`) takes a `PhysicalLayer*` from RadioLib:

```cpp
class RadioLibWrapper : public mesh::Radio {
protected:
    PhysicalLayer* _radio;       // RadioLib radio (SX1262, SX1278, etc.)
    mesh::MainBoard* _board;
    
    virtual bool isReceivingPacket() = 0;  // Subclass must implement (chip-specific)
    virtual float getCurrentRSSI() = 0;    // Subclass must implement
    
public:
    void begin() override;
    int recvRaw(uint8_t* bytes, int sz) override;
    bool startSendRaw(const uint8_t* bytes, int len) override;
    bool isSendComplete() override;
    void onSendFinished() override;
    // ... etc
};
```

Key implementation details:
- Uses RadioLib's `PhysicalLayer` interface (works with any RadioLib-supported radio)
- `recvRaw()`: Calls `_radio->readData()`, reads RSSI/SNR from the radio
- `startSendRaw()`: Calls `_radio->startTransmit()` with DIO interrupt
- `isReceivingPacket()`: Pure virtual — chip-specific (reads DIO/CAD)
- `getCurrentRSSI()`: Pure virtual — chip-specific RSSI reading
- Noise floor calibration: Samples RSSI when idle, tracks average

## LR2021 Compatibility Assessment

### RadioLib Support for LR2021

The LR2021 (NiceRF LoRa2021) is based on the **Semtech LR1121** chip. RadioLib v7.x has a `LR1121` class that supports:
- Sub-GHz LoRa (868 MHz) ✅
- 2.4 GHz LoRa ✅
- Sub-GHz GFSK ✅
- 2.4 GHz FLRC ✅
- Dual-band operation ✅

RadioLib's `LR1121` class inherits from `PhysicalLayer`, making it directly compatible with MeshCore's `RadioLibWrapper`.

### Pin Mapping (ESP32-C3_Mini_V1 + NiceRF LoRa2021)

```
NiceRF Pin   Function    ESP32 GPIO   Notes
Pin 1        VCC         3.3V
Pin 3        MISO        GPIO2
Pin 4        MOSI        GPIO7
Pin 5        SCK         GPIO6
Pin 6        NSS         GPIO10
Pin 7        BUSY        GPIO4
Pin 9        ANT         Sub-GHz output (Pin 9)
Pin 10       2.4G        2.4 GHz output (Pin 10)
Pin 14       RST         GPIO3
Pin 15       DIO9        GPIO5       (IRQ)
```

### Implementation Plan

#### Option A: Subclass RadioLibWrapper (Recommended)

Create `LR1121Wrapper` that extends `RadioLibWrapper`:

```cpp
#include <RadioLib.h>
#include "RadioLibWrappers.h"

class LR1121Wrapper : public RadioLibWrapper {
    LR1121* _lr1121;
    
protected:
    bool isReceivingPacket() override {
        return _lr1121->getIRQFlags().irqRxTxTimeout || 
               digitalRead(DIO9_PIN);  // Check DIO9 for RX done
    }
    
    float getCurrentRSSI() override {
        return _lr1121->getRSSI();
    }
    
public:
    LR1121Wrapper(LR1121& radio, mesh::MainBoard& board)
        : RadioLibWrapper(radio, board), _lr1121(&radio) {}
    
    // Band switching for dual-band operation
    void setSubGHz() { _lr1121->setRfSwitchTable(0, LR1121_RF_SWITCH_SUBGHZ); }
    void set2G4()    { _lr1121->setRfSwitchTable(0, LR1121_RF_SWITCH_2_4); }
};
```

#### Option B: Direct mesh::Radio Implementation

If RadioLib's LR1121 support is incomplete, implement `mesh::Radio` directly:

```cpp
class LR2021Radio : public mesh::Radio {
    // Implement all pure virtual methods using SPI directly
    // More work but full control
};
```

### Dual-Band TDMA Integration

MeshCore assumes a single-band radio. For dual-band operation:

1. **TDMA wrapper**: Wrap MeshCore's `loop()` in a TDMA scheduler
2. **Band switching**: Call `setSubGHz()` / `set2G4()` before TX/RX
3. **Two instances**: Potentially create two `LR1121Wrapper` instances (Sub-GHz + 2.4 GHz)
4. **Time-sharing**: Use our TDMA scheduler to multiplex between MeshCore (Sub-GHz) and FIPS (2.4 GHz)

### RAM/Flash Estimates

| Component | RAM | Flash |
|-----------|-----|-------|
| MeshCore core | ~8 KB | ~60 KB |
| RadioLib LR1121 | ~2 KB | ~30 KB |
| RadioLibWrapper | ~0.5 KB | ~4 KB |
| Ed25519 (MeshCore) | ~1 KB | ~15 KB |
| NVS/preferences | ~4 KB | ~8 KB |
| **Total** | **~15 KB** | **~117 KB** |

ESP32-C3 has 400 KB SRAM and 4 MB flash — plenty of room.

### Open Questions

1. **RadioLib LR1121 maturity**: RadioLib's LR1121 support may not be as mature as SX1262/SX1278. Need to verify all modulation modes work.
2. **Antenna switching**: LR2021 uses Pin 9 (Sub-GHz) and Pin 10 (2.4 GHz) as separate outputs. Need GPIO-controlled RF switch or direct connection.
3. **MeshCore `RADIOLIB_GODMODE`**: MeshCore requires `RADIOLIB_GODMODE=1` which accesses protected RadioLib members. This works with ESP-IDF (source inclusion) but may need adjustment.
4. **PlatformIO vs ESP-IDF**: MeshCore uses PlatformIO. We use ESP-IDF. Need to either:
   - Build MeshCore as a static library with PlatformIO, link into ESP-IDF
   - Or port MeshCore source files directly into our ESP-IDF component structure
5. **KISS modem interface**: The KISS modem example (`examples/kiss_modem/`) provides a serial bridge that could be used standalone, with our TDMA+FIPS on the host side.

### Recommended Approach

1. **Start with KISS modem**: Flash MeshCore KISS modem on ESP32-C3, connect via serial to our FIPS/TDMA host
2. **Verify LR1121 support**: Test RadioLib's LR1121 driver with Sub-GHz LoRa on our hardware
3. **Integrate incrementally**: Port MeshCore source as ESP-IDF component, test with Sub-GHz only first
4. **Add TDMA dual-band**: Wrap MeshCore `loop()` in our TDMA scheduler for dual-band time-sharing
5. **Final integration**: Full FIPS-over-MeshCore stack on single ESP32-C3

## Key MeshCore Constants

```cpp
#define MAX_PACKET_PAYLOAD  184        // Max LoRa payload bytes
#define PUB_KEY_SIZE        32         // Ed25519 public key
#define PRV_KEY_SIZE        64         // Ed25519 private key  
#define CIPHER_KEY_SIZE     16         // AES-128 key
#define CIPHER_BLOCK_SIZE   16         // AES block size
#define CIPHER_MAC_SIZE     2          // 2-byte MAC (CRC-like)
#define MAX_PATH_SIZE       64         // Max path hash entries
```

## References

- MeshCore repo: https://github.com/meshcore-dev/MeshCore
- MeshCore Radio interface: `src/Dispatcher.h` (mesh::Radio class)
- RadioLibWrapper: `src/helpers/radiolib/RadioLibWrappers.h`
- KISS modem example: `examples/kiss_modem/`
- RadioLib LR1121: https://github.com/jgromes/RadioLib (v7.6.0+)
- Our LR2021 pin mapping: AGENTS.md (NiceRF LoRa2021 section)
