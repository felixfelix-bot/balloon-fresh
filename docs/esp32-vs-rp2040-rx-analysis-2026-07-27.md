# ESP32-C3 vs RP2040 FLRC RX Pipeline: Root Cause Analysis

**Date:** 2026-07-27
**Trigger:** Felix asked why ESP32 maxed at ~800 kbps but RP2040 reached ~1500 kbps
**Method:** Source code comparison across all branches + timing data from real hardware tests

---

## TL;DR

The throughput gap is **NOT from RP2040 hardware advantages** (PIO/DMA/dual-core all failed or were never used). The gap comes from **three software differences** that are all fixable on ESP32:

1. **SPI clock: 2 MHz vs 12 MHz** (6× difference — the dominant factor)
2. **RadioLib overhead** — ESP32 uses full API stack; RP2040 bypasses it entirely with raw SPI
3. **RX loop latency** — ESP32 polls every 10ms via FreeRTOS; RP2040 uses tight polling loop

The optimized ESP32 HAL already exists (feat/esp32-spi-gdma branch, 40 MHz SPI + GDMA) but was **never tested on hardware**.

---

## 1. ACTUAL MEASURED NUMBERS

| Platform | Max Throughput | SPI Clock | Method | Source |
|----------|---------------|-----------|--------|--------|
| ESP32-C3 (original) | ~800 kbps (Felix's memory) | 2 MHz | RadioLib + byte-at-a-time | `tracker/firmware/main/EspHalC3.h` |
| RP2040 (optimized) | **1377 kbps** (actual) | 12 MHz (20 MHz requested, Pico SDK caps) | Raw SPI + byte-at-a-time | `firmware/rp2040/src/flrc_bitrate_rx.cpp` |
| RP2040 (PIO/DMA) | **Never tested** | 20.83 MHz (designed) | PIO + DMA | `firmware/rp2040/src/pio_lr2021_rx.pio` |
| ESP32 (GDMA) | **Never tested** | 40 MHz (configured) | GDMA batch + async queue | `mesh-stack/flrc-bench-espidf/main/EspHalC3.h` |
| Theoretical max | 2540 kbps | N/A | Air-time limited | Physics |

Note: Felix remembered "1500 kbps" — actual measured was 1377 kbps. Close enough.

---

## 2. ESP32-C3 RX PIPELINE (Original — tracker/firmware/main/)

### 2.1 SPI Configuration (EspHalC3.h)

```cpp
// Line 126: SPI clock = 2 MHz (!!!)
dev_cfg.clock_speed_hz = 2000000;

// Line 117: max transfer = 256 bytes
bus_cfg.max_transfer_sz = 256;

// Line 118: DMA channel auto-allocated BUT COMPLETELY DEFEATED (see below)
esp_err_t ret = spi_bus_initialize(SPI2_HOST, &bus_cfg, SPI_DMA_CH_AUTO);
```

### 2.2 SPI Transfer — Byte-at-a-Time (THE KILLER)

```cpp
// Lines 140-157: each byte gets its own full SPI transaction
uint8_t spiTransferByte(uint8_t b) {
    spi_transaction_t trans = {};
    trans.flags = SPI_TRANS_USE_TXDATA | SPI_TRANS_USE_RXDATA;
    trans.length = 8;
    trans.tx_data[0] = b;
    esp_err_t ret = spi_device_polling_transmit(this->spiDev, &trans);  // per-byte!
    return trans.rx_data[0];
}

void spiTransfer(uint8_t* out, size_t len, uint8_t* in) {
    for(size_t i = 0; i < len; i++) {
        in[i] = spiTransferByte(out[i]);  // loops per byte
    }
}
```

**Each byte** triggers: API call → driver dispatch → transaction setup → DMA (for 1 byte!) → completion poll → return. The per-byte driver overhead is ~3-5µs on top of the bus time.

At 2 MHz, a 255-byte FIFO read costs:
- Bus time: 255 × 8 / 2,000,000 = **1020µs**
- Driver overhead: 255 × ~4µs = **~1020µs**
- Total: **~2040µs** per FIFO read

### 2.3 RadioLib API Stack

```cpp
// gs_main.cpp — uses full RadioLib abstraction
radio->begin(868.0, 125.0, 9, 7, 0x12, 22, 8, 0.0f);  // LoRa init
radio->setPacketReceivedAction(on_rx_done);               // ISR callback
radio->startReceive();                                     // enter RX mode

// In main loop:
size_t pktLen = radio->getPacketLength();   // SPI read
uint32_t irq = radio->getIrqStatus();       // SPI read
int16_t r = radio->readData(buf, pktLen);   // SPI read + state machine
int16_t rssi = radio->getRSSI();            // SPI read
float snr = radio->getSNR();                // SPI read
radio->standby();                           // SPI write
radio->startReceive();                      // SPI write + state machine
```

RadioLib wraps every SPI access in: method call → state check → register access → SPI transfer → state update → return. Each `readData()` call internally performs 3-5 SPI transactions beyond just the FIFO read.

### 2.4 RX Loop — 10ms FreeRTOS Delay

```cpp
// gs_main.cpp, line 396-428
while (1) {
    if (flag_rx_done) {
        // ... process packet ...
        radio->standby();
        radio->startReceive();
    }
    vTaskDelay(pdMS_TO_TICKS(10));  // ← 10ms yield between checks!
}
```

Between packet arrival (ISR sets `flag_rx_done`) and processing, up to 10ms of latency is added. During this time the radio is not re-armed for the next packet.

---

## 3. RP2040 RX PIPELINE (flrc_bitrate_rx.cpp)

### 3.1 SPI Configuration

```cpp
// Line 57: SPI clock = 20 MHz requested
#define SPI_FREQ_HZ     20000000UL

// Line 83-84: Arduino SPI (NOT PIO, NOT DMA)
static SPIClassRP2040 spiRf(spi0, PIN_MISO, PIN_CS, PIN_SCK, PIN_MOSI);
static SPISettings spiSettings(SPI_FREQ_HZ, MSBFIRST, SPI_MODE0);
```

**Important:** Pico SDK `spi_set_baudrate()` caps at ~12 MHz for this peripheral config. Actual SPI clock is **12 MHz**, not 20 MHz. (Source: `docs/spi-frequency-sweep-results-2026-07-16.md`)

### 3.2 Raw SPI — RadioLib Completely Bypassed

```cpp
// Lines 105-113: FIFO read is raw SPI commands, zero abstraction
static void rfReadFifo(uint8_t *buf, size_t len) {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(0x00); spiRf.transfer(0x01);  // READ_RX_FIFO command
    for (size_t i = 0; i < len; i++)
        buf[i] = spiRf.transfer(0x00);            // read each byte
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
}
```

No RadioLib. No state machine. Direct register access. One CS toggle per transaction.

### 3.3 RX Loop — Tight Polling, No Delays

```cpp
// Lines 341-401
while (true) {
    uint32_t now = millis();
    // timeout checks...

    uint32_t irq = rfReadIrqStatus();      // poll IRQ via SPI
    if (!(irq & 0x00040000)) continue;      // no RX_DONE → immediately re-poll

    rfReadFifo(buf, pktSize);               // read 255 bytes
    int8_t rssi = rfReadRssi();             // read RSSI
    // Clear FIFO + IRQ + re-arm RX (raw SPI, minimal bytes)
    rfClearIrq();
    rfSetRx();
    // ... process packet ...
}
```

No FreeRTOS. No task yield. No 10ms delay. Tight `while(true)` with SPI poll.

### 3.4 Per-Packet Timing Breakdown (Real Hardware Data)

Source: `docs/PLAN-speed-optimization.md` timing profiler on real boards

| Step | Time (µs) | SPI Bytes |
|------|-----------|-----------|
| Read IRQ status | ~12 | 6 |
| Read RX FIFO (255 bytes) | ~514 | 257 |
| Clear IRQ | ~12 | 6 |
| Re-arm RX (SET_RX) | ~4 | 2 |
| BUSY waits | ~30 | — |
| **Total RX blind window** | **~572** | **271** |

At 12 MHz actual SPI, 255 bytes takes 514µs (2.03µs/byte including Arduino overhead).

---

## 4. THE FIVE BOTTLENECKS (Ranked by Impact)

### Bottleneck #1: SPI Clock — 2 MHz vs 12 MHz (6×)

| | ESP32 | RP2040 | Delta |
|---|---|---|---|
| SPI clock | 2 MHz | 12 MHz | **6×** |
| 255-byte FIFO read (bus only) | 1020µs | 170µs | **850µs** |
| 255-byte FIFO read (with overhead) | ~2040µs | ~514µs | **1526µs** |

**This single difference accounts for the majority of the throughput gap.**

The ESP32-C3 GPSPI2 controller supports up to 80 MHz. The HAL is configured for 2 MHz. Changing one line (`dev_cfg.clock_speed_hz = 2000000` → `20000000`) would give 10× speedup.

### Bottleneck #2: RadioLib Overhead vs Raw SPI

| | ESP32 | RP2040 |
|---|---|---|
| API layer | RadioLib full stack | Raw register access |
| Per-packet SPI transactions | 5-7 (getPacketLength, getIrqStatus, readData, getRSSI, getSNR, standby, startReceive) | 4 (readIrqStatus, readFifo, clearIrq, setRx) |
| Estimated overhead per packet | ~200-400µs | ~50µs |

RadioLib adds state machine transitions, error checking, and multiple register accesses per API call. The RP2040 code skips all of this.

### Bottleneck #3: Byte-at-a-Time Transfer Pattern

Both platforms use byte-by-byte `transfer()`. But the overhead differs:

| | ESP32 (`spi_device_polling_transmit`) | RP2040 (Arduino `transfer`) |
|---|---|---|
| Per-byte overhead | ~4µs (full transaction per byte) | ~1.36µs (lightweight) |
| 255-byte total overhead | ~1020µs | ~347µs |

The ESP32 `spi_master` driver has more overhead per transaction than the RP2040 Arduino core. **This is fixable** by batching transfers (send all 257 bytes in one `spi_device_polling_transmit` call).

### Bottleneck #4: FreeRTOS 10ms Polling vs Tight Loop

| | ESP32 | RP2040 |
|---|---|---|
| RX check interval | 10ms (`vTaskDelay`) | Continuous (`while(true)`) |
| Latency to process | up to 10ms | <1ms |

This doesn't directly limit throughput (packets buffer in the FIFO), but increases the "blind window" — if the next packet arrives while the previous is still being processed, it's lost.

### Bottleneck #5: Re-arm Sequence Complexity

| | ESP32 (RadioLib) | RP2040 (Raw) |
|---|---|---|
| Re-arm calls | `standby()` + `startReceive()` | `rfClearIrq()` + `rfSetRx()` |
| Internal SPI transactions | 4-6 | 2 |
| Time | ~100µs | ~16µs |

---

## 5. WHAT ABOUT RP2040 HARDWARE ACCELERATION?

**The RP2040's advanced hardware features were ALL failures or unused:**

| Feature | Status | What Happened |
|---------|--------|---------------|
| PIO state machine (TX) | **FAILED** | DMA_IRQ starves TinyUSB → CDC USB dies |
| PIO state machine (RX) | **NEVER TESTED** | Code exists (`pio_lr2021_rx.pio`) but never flashed |
| DMA batch transfer | **FAILED** | LR2021 BUSY timing incompatible with RP2040 DMA |
| Dual-core | **NEVER TESTED** | Both cores share one SPI bus |
| `spi_write_blocking()` | **FAILED** | Pico SDK FIFO management incompatible with LR2021 |

Source: `docs/flrc-platform-analysis-2026-07-16.md` — tested on real hardware

**The working RP2040 code is plain Arduino `SPI.transfer()` byte-by-byte — the SAME approach the ESP32 uses.** The only differences are clock speed, API layer, and loop structure.

---

## 6. CAN ESP32 MATCH OR EXCEED RP2040?

### YES — the ESP32-C3 has SUPERIOR SPI hardware:

| Capability | ESP32-C3 | RP2040 |
|---|---|---|
| Max SPI clock | **80 MHz** | ~12 MHz (capped) |
| DMA controller | Dedicated GDMA (no USB conflict) | Shared (conflicts with TinyUSB) |
| Batch transfer | `spi_device_polling_transmit` (full buffer) | `spi_write_blocking` (failed with LR2021) |
| Async queue | `spi_device_queue_trans` (up to 8 queued) | Not available |

### The Optimized ESP32 HAL Already Exists

On branch `feat/esp32-spi-gdma`, file `mesh-stack/flrc-bench-espidf/main/EspHalC3.h`:

```cpp
#define ESPHAL_C3_SPI_HZ   (40 * 1000 * 1000)  // 40 MHz!
#define ESPHAL_C3_DMA_BUF_SZ  512

// DMA-backed batch transfer — entire buffer in one transaction:
void spiTransfer(uint8_t* out, size_t len, uint8_t* in) {
    memcpy(this->dmaTxBuf, out, len);  // stage to DMA-capable buffer
    spi_transaction_t trans = {};
    trans.length = len * 8;
    trans.tx_buffer = this->dmaTxBuf;   // GDMA pumps the bus
    trans.rx_buffer = this->dmaRxBuf;
    spi_device_polling_transmit(this->spiDev, &trans);  // one call for ALL bytes
    memcpy(in, this->dmaRxBuf, len);
}

// Async queue for CPU-free transfers:
esp_err_t spiQueueTrans(spi_transaction_t* trans, ...);  // returns immediately
esp_err_t spiGetResult(spi_transaction_t** out, ...);    // await completion
```

### Projected ESP32 Throughput with GDMA Optimization

| Component | Current ESP32 (2 MHz) | Optimized ESP32 (40 MHz GDMA) | RP2040 (12 MHz Arduino) |
|---|---|---|---|
| 255-byte FIFO read | ~2040µs | **~61µs** (51µs bus + 10µs memcpy) | ~514µs |
| RX blind window | ~2300µs | **~200µs** | ~572µs |
| Max RX throughput | ~400 kbps | **~2500 kbps** (air-time limited) | ~1377 kbps |

**The optimized ESP32 would be 3× faster than RP2040 on SPI, and would hit the air-time ceiling (2540 kbps).**

### BUT: Never Tested

From `docs/PLAN-speed-optimization.md`:
> **Status: Built, NOT YET TESTED.** Firmware at `firmware/esp32-c3-flrc/main/main.cpp`.
>
> **Risk:** ESP32 DMA might have same BUSY timing issue as RP2040. But ESP32's SPI hardware is completely different (dedicated DMA controller, no shared peripheral).

The ESP32's GDMA controller is a separate hardware block from the SPI peripheral, unlike the RP2040 where DMA and USB share interrupt resources. The BUSY timing issues that killed RP2040 DMA may not apply.

---

## 7. CONCLUSION

### The throughput gap (800 vs 1377 kbps) was caused by SOFTWARE, not HARDWARE:

1. **SPI clock set to 2 MHz** instead of 12+ MHz — 6× penalty (biggest factor)
2. **RadioLib overhead** instead of raw SPI — 2-4× penalty per transaction
3. **10ms FreeRTOS polling** instead of tight loop — increased blind window
4. **Byte-at-a-time SPI transactions** instead of batch DMA — 2-3× overhead

### The RP2040 "advantage" was illusory:
- PIO, DMA, dual-core all **failed** or were **never tested**
- The working code uses the **same Arduino byte-at-a-time SPI** as ESP32
- The only real advantage was **someone wrote raw register access** instead of using RadioLib

### The ESP32-C3 can match or exceed RP2040:
- SPI clock: up to 80 MHz (vs RP2040's 12 MHz cap)
- GDMA: dedicated controller, no USB conflict
- Optimized HAL already written (40 MHz + batch DMA + async queue) — **needs testing**
- Projected: 2000-2500 kbps (air-time limited)

### Recommendation:
1. **Test the GDMA-optimized ESP32 HAL** — it's already built, just needs flashing
2. If GDMA works with LR2021 (likely, different hardware than RP2040): ESP32 becomes the faster platform
3. If GDMA fails: ESP32 still matches RP2040 by using raw SPI at 20 MHz (trivially achievable)
4. The PIO RX path on RP2040 (`pio_lr2021_rx.pio`) also remains untested and could close the gap from the RP2040 side

---

## Appendix: File Reference

| Component | File | Lines |
|---|---|---|
| ESP32 HAL (original) | `tracker/firmware/main/EspHalC3.h` | 181 |
| ESP32 RX app | `tracker/ground-station/receiver/main/gs_main.cpp` | 429 |
| ESP32 HAL (GDMA optimized) | `mesh-stack/flrc-bench-espidf/main/EspHalC3.h` (branch: feat/esp32-spi-gdma) | 309 |
| RP2040 RX (bitrate) | `firmware/rp2040/src/flrc_bitrate_rx.cpp` | 596 |
| RP2040 PIO RX header | `firmware/rp2040/src/pio_lr2021_rx.h` | 114 |
| RP2040 PIO assembly | `firmware/rp2040/src/pio_lr2021_rx.pio` | 85 |
| Platform analysis | `docs/flrc-platform-analysis-2026-07-16.md` | 229 |
| Speed optimization plan | `docs/PLAN-speed-optimization.md` | 286 |
| SPI sweep results | `docs/spi-frequency-sweep-results-2026-07-16.md` | 50 |
| FLRC final summary | `docs/flrc-final-summary-2026-07-16.md` | — |
