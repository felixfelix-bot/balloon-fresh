#pragma once

#include <RadioLib.h>

#if CONFIG_IDF_TARGET_ESP32C3 == 0
#error This HAL only supports ESP32-C3 targets
#endif

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "driver/spi_master.h"
#include "esp_timer.h"
#include "esp_log.h"
#include "esp_heap_caps.h"
#include <cstring>

#define LOW    (0x0)
#define HIGH   (0x1)
#define INPUT  (0x01)
#define OUTPUT (0x03)
#define RISING (0x01)
#define FALLING (0x02)
#define NOP()  asm volatile ("nop")


// SPI clock for the LR2021 radio on GPSPI2 (SPI2_HOST). 16 MHz is the LR2021
// datasheet maximum SPI clock; staying inside spec improves reliability at
// range and across temperature/voltage corners. 40 MHz ran at bench distance
// but violated the datasheet and risked SPI timing failures in flight.
#define ESPHAL_C3_SPI_HZ   (16 * 1000 * 1000)

// Largest single SPI transaction we stage through DMA. Matches the SPI bus
// max_transfer_sz and comfortably covers a combined WRITE_TX_FIFO
// (header + 255-byte payload) for the LR2021 radio.
#define ESPHAL_C3_DMA_BUF_SZ  512


class EspHalC3 : public RadioLibHal {
  public:
    EspHalC3(int8_t sck, int8_t miso, int8_t mosi)
      : RadioLibHal(INPUT, OUTPUT, LOW, HIGH, RISING, FALLING),
      spiSCK(sck), spiMISO(miso), spiMOSI(mosi), csPin(-1), busyPin(-1) {
    }

    void init() override {
      spiBegin();
    }

    void term() override {
      spiEnd();
    }

    void pinMode(uint32_t pin, uint32_t mode) override {
      if(pin == RADIOLIB_NC) return;
      gpio_config_t conf = {
        .pin_bit_mask = (1ULL << pin),
        .mode = (gpio_mode_t)mode,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
      };
      gpio_config(&conf);
    }

    void digitalWrite(uint32_t pin, uint32_t value) override {
      if(pin == RADIOLIB_NC) return;
      gpio_set_level((gpio_num_t)pin, value);
    }

    uint32_t digitalRead(uint32_t pin) override {
      if(pin == RADIOLIB_NC) return(0);
      return(gpio_get_level((gpio_num_t)pin));
    }

    void attachInterrupt(uint32_t interruptNum, void (*interruptCb)(void), uint32_t mode) override {
      if(interruptNum == RADIOLIB_NC) return;
      if(!this->isrInstalled) {
        gpio_install_isr_service((int)ESP_INTR_FLAG_IRAM);
        this->isrInstalled = true;
      }
      gpio_set_intr_type((gpio_num_t)interruptNum, (gpio_int_type_t)(mode & 0x7));
      gpio_isr_handler_add((gpio_num_t)interruptNum, (void (*)(void*))interruptCb, NULL);
    }

    void detachInterrupt(uint32_t interruptNum) override {
      if(interruptNum == RADIOLIB_NC) return;
      gpio_isr_handler_remove((gpio_num_t)interruptNum);
      gpio_wakeup_disable((gpio_num_t)interruptNum);
      gpio_set_intr_type((gpio_num_t)interruptNum, GPIO_INTR_DISABLE);
    }

    void delay(unsigned long ms) override {
      vTaskDelay(ms / portTICK_PERIOD_MS);
    }

    void delayMicroseconds(unsigned long us) override {
      uint64_t m = (uint64_t)esp_timer_get_time();
      if(us) {
        uint64_t e = (m + us);
        if(m > e) {
          while((uint64_t)esp_timer_get_time() > e) { NOP(); }
        }
        while((uint64_t)esp_timer_get_time() < e) { NOP(); }
      }
    }

    unsigned long millis() override {
      return((unsigned long)(esp_timer_get_time() / 1000ULL));
    }

    unsigned long micros() override {
      return((unsigned long)(esp_timer_get_time()));
    }

    long pulseIn(uint32_t pin, uint32_t state, unsigned long timeout) override {
      if(pin == RADIOLIB_NC) return(0);
      this->pinMode(pin, INPUT);
      uint32_t start = this->micros();
      uint32_t curtick = this->micros();
      while(this->digitalRead(pin) == state) {
        if((this->micros() - curtick) > timeout) return(0);
      }
      return(this->micros() - start);
    }

    // ------------------------------------------------------------------
    // SPI / GDMA
    // ------------------------------------------------------------------
    // The SPI bus is initialized with SPI_DMA_CH_AUTO, so the ESP-IDF spi_master
    // driver allocates an ESP32-C3 GDMA channel and uses it for every transfer
    // larger than 32 bytes. The driver can *itself* make a transfer DMA-native:
    // by default (no SPI_TRANS_DMA_BUFFER_ALIGN_MANUAL flag) it transparently
    // reallocs + memcpy()s any non-DMA-capable user buffer into an internal
    // DMA buffer on every transaction. That per-transaction alloc/copy/free is
    // pure CPU overhead. To eliminate it we allocate PERSISTENT DMA-capable
    // staging buffers once in spiBegin() and route synchronous transfers
    // through them, so the only memcpy left is the unavoidable CPU copy of the
    // caller's data into DMA memory (no alloc/free churn).
    //
    // For true CPU-free transfers, callers use the async path: spiQueueTrans()
    // hands a descriptor to GDMA and returns immediately while the DMA engine
    // pumps the bus; the CPU is free to prepare the next packet. Completion is
    // awaited with spiGetResult() (or, for fire-and-forget TX, via the radio's
    // BUSY pin). queue_size is set to 8 so up to 8 transactions may be in flight,
    // enabling the N / N+1 double-buffer pattern.
    // ------------------------------------------------------------------
    void spiBegin() {
      if (this->spiInitialized) return;
      spi_bus_config_t bus_cfg = {};
      bus_cfg.mosi_io_num = this->spiMOSI;
      bus_cfg.miso_io_num = this->spiMISO;
      bus_cfg.sclk_io_num = this->spiSCK;
      bus_cfg.quadwp_io_num = -1;
      bus_cfg.quadhd_io_num = -1;
      bus_cfg.max_transfer_sz = ESPHAL_C3_DMA_BUF_SZ;
      // SPI_DMA_CH_AUTO: let the driver allocate an ESP32-C3 GDMA channel.
      esp_err_t ret = spi_bus_initialize(SPI2_HOST, &bus_cfg, SPI_DMA_CH_AUTO);
      if (ret != ESP_OK && ret != ESP_ERR_INVALID_STATE) {
        ESP_LOGE("HAL", "spi_bus_initialize failed: %s", esp_err_to_name(ret));
        return;
      }

      spi_device_interface_config_t dev_cfg = {};
      dev_cfg.mode = 0;
      dev_cfg.clock_speed_hz = ESPHAL_C3_SPI_HZ;   // 16 MHz (LR2021 datasheet max)
      dev_cfg.spics_io_num = -1;                    // NSS is toggled manually by the caller
      // queue_size 8 enables the async (spi_device_queue_trans) path and the
      // N / N+1 double-buffer pattern. flags stays 0 so the result queue is
      // available for spi_device_get_trans_result; set SPI_DEVICE_NO_RETURN_RESULT
      // instead for pure fire-and-forget TX (saves the result-queue slot).
      dev_cfg.queue_size = 8;
      dev_cfg.flags = 0;
      // cs_ena_pretrans / cs_ena_posttrans are only honored when spics_io_num is
      // managed by the driver; NSS here is manual, so they are left at the 0 default.
      ret = spi_bus_add_device(SPI2_HOST, &dev_cfg, &this->spiDev);
      if (ret != ESP_OK) {
        ESP_LOGE("HAL", "spi_bus_add_device failed: %s", esp_err_to_name(ret));
        return;
      }

      // Persistent DMA-capable staging buffers (4-byte aligned, internal RAM).
      this->dmaTxBuf = (uint8_t*)heap_caps_malloc(ESPHAL_C3_DMA_BUF_SZ, MALLOC_CAP_DMA);
      this->dmaRxBuf = (uint8_t*)heap_caps_malloc(ESPHAL_C3_DMA_BUF_SZ, MALLOC_CAP_DMA);
      if (!this->dmaTxBuf || !this->dmaRxBuf) {
        ESP_LOGE("HAL", "DMA staging buffer alloc failed (caps=%zu)", (size_t)ESPHAL_C3_DMA_BUF_SZ);
      }

      this->spiInitialized = true;
      ESP_LOGI("HAL", "SPI+GDMA init: MOSI=%d MISO=%d SCK=%d %dMHz dma_tx=%p dma_rx=%p qs=%d",
               this->spiMOSI, this->spiMISO, this->spiSCK,
               ESPHAL_C3_SPI_HZ / 1000000, this->dmaTxBuf, this->dmaRxBuf, dev_cfg.queue_size);
    }

    void spiBeginTransaction() {}

    uint8_t spiTransferByte(uint8_t b) {
      spi_transaction_t trans = {};
      trans.flags = SPI_TRANS_USE_TXDATA | SPI_TRANS_USE_RXDATA;
      trans.length = 8;
      trans.tx_data[0] = b;
      esp_err_t ret = spi_device_polling_transmit(this->spiDev, &trans);
      if (ret != ESP_OK) {
        ESP_LOGE("HAL", "spiTransferByte failed: %s", esp_err_to_name(ret));
        return 0xFF;
      }
      return trans.rx_data[0];
    }

    // Synchronous (RadioLib HAL contract) DMA transfer. Stages caller data through
    // the persistent DMA-capable buffer so the driver never reallocs internally;
    // GDMA then pumps the bus. This is blocking (polls the GDMA-done bit) but the
    // CPU is not bit-banging — for the non-blocking path see spiQueueTrans().
    void spiTransfer(uint8_t* out, size_t len, uint8_t* in) {
      if (len == 0) return;
      if (len > ESPHAL_C3_DMA_BUF_SZ) len = ESPHAL_C3_DMA_BUF_SZ;   // guard against overrun
      if (out && this->dmaTxBuf) {
        memcpy(this->dmaTxBuf, out, len);
      }
      spi_transaction_t trans = {};
      trans.length = len * 8;
      trans.tx_buffer = (out && this->dmaTxBuf) ? this->dmaTxBuf : nullptr;
      trans.rx_buffer = (in && this->dmaRxBuf) ? this->dmaRxBuf : nullptr;
      esp_err_t ret = spi_device_polling_transmit(this->spiDev, &trans);
      if (ret != ESP_OK) {
        ESP_LOGE("HAL", "spiTransfer failed: %s", esp_err_to_name(ret));
        if (in) memset(in, 0xFF, len);
        return;
      }
      if (in && this->dmaRxBuf) {
        memcpy(in, this->dmaRxBuf, len);
      }
    }

    // ------------------------------------------------------------------
    // Async (queued) DMA API — CPU-free transfers.
    //
    // spiQueueTrans(): hand a transaction descriptor to GDMA and return at once.
    //   The buffers pointed to by trans->tx_buffer / rx_buffer MUST remain valid
    //   (and DMA-capable) until completion — use the result from spiDmaMalloc()
    //   or spiGetDmaTxBuf()/spiGetDmaRxBuf(). Up to queue_size descriptors may be
    //   in flight at once (double-buffer: queue N, fill N+1, then await N).
    // spiGetResult(): block until a previously queued transaction completes.
    //   (Not usable if the device was created with SPI_DEVICE_NO_RETURN_RESULT.)
    // spiPollingTransmit(): thin wrapper for low-latency single transfers when the
    //   caller has pre-built the spi_transaction_t (used by the SPEED-P2 hot loop).
    // ------------------------------------------------------------------
    esp_err_t spiQueueTrans(spi_transaction_t* trans, TickType_t ticks_to_wait = portMAX_DELAY) {
      return spi_device_queue_trans(this->spiDev, trans, ticks_to_wait);
    }

    esp_err_t spiGetResult(spi_transaction_t** out_trans, TickType_t ticks_to_wait = portMAX_DELAY) {
      return spi_device_get_trans_result(this->spiDev, out_trans, ticks_to_wait);
    }

    esp_err_t spiPollingTransmit(spi_transaction_t* trans) {
      return spi_device_polling_transmit(this->spiDev, trans);
    }

    // DMA-capable memory for callers that build their own transaction descriptors
    // for the async path (must outlive the transfer). Free with spiDmaFree().
    static uint8_t* spiDmaMalloc(size_t size) {
      return (uint8_t*)heap_caps_malloc(size, MALLOC_CAP_DMA);
    }
    static void spiDmaFree(uint8_t* p) { free(p); }

    // Accessors for the persistent DMA staging buffers (double-buffer fill slot).
    uint8_t* getDmaTxBuf() { return this->dmaTxBuf; }
    uint8_t* getDmaRxBuf() { return this->dmaRxBuf; }
    static constexpr size_t getDmaBufSz() { return ESPHAL_C3_DMA_BUF_SZ; }

    void spiEndTransaction() {}

    void spiEnd() {
      if (this->spiDev) {
        spi_bus_remove_device(this->spiDev);
        this->spiDev = nullptr;
      }
      spi_bus_free(SPI2_HOST);
      if (this->dmaTxBuf) { free(this->dmaTxBuf); this->dmaTxBuf = nullptr; }
      if (this->dmaRxBuf) { free(this->dmaRxBuf); this->dmaRxBuf = nullptr; }
      this->spiInitialized = false;
    }

    void setCsPin(int8_t pin) { this->csPin = pin; }
    void setBusyPin(int8_t pin) { this->busyPin = pin; }

    // Direct SPI device handle for callers that drive spi_device_polling_transmit /
    // spi_device_queue_trans themselves, bypassing the per-call spi_transaction_t
    // rebuild + virtual-call indirection of spiTransfer(). Used by the
    // zero-overhead raw SPI TX path in bench_main.cpp (runRawTx) on the
    // feat/radiolib-bypass-tx branch. Exposing the handle lets the hot loop
    // pre-build transaction structs once and/or queue descriptors to GDMA.
    spi_device_handle_t getSpiDev() const { return this->spiDev; }

  private:
    int8_t spiSCK;
    int8_t spiMISO;
    int8_t spiMOSI;
    int8_t csPin;
    int8_t busyPin;
    spi_device_handle_t spiDev = nullptr;
    bool spiInitialized = false;
    bool isrInstalled = false;
    // Persistent DMA-capable staging buffers (allocated in spiBegin, freed in spiEnd).
    uint8_t* dmaTxBuf = nullptr;
    uint8_t* dmaRxBuf = nullptr;
};
