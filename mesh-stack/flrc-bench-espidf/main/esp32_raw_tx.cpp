/*
 * esp32_raw_tx.cpp — ESP32 FLRC TX with RAW SPI init
 *
 * Direct port of RP2040 flrc_raw_tx.cpp v4.  Uses EspHalC3 GDMA SPI.
 * Sends 1000 packets, then repeats every 15 s.
 * TX hot loop: clearIrq → writeTxFifo → setTx → poll DIO9.
 * rfClearTxFifo() is only used on init / timeout recovery (auto-cleared on TX_DONE).
 *
 * Pins: SCK=6 MISO=2 MOSI=7 NSS=10 BUSY=4 RST=3 DIO9=5 LED=8
 */

#include <sdkconfig.h>

#ifdef CONFIG_BENCH_MODE_RAW_TX

#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "esp_rom_sys.h"
#include "driver/gpio.h"
#include <RadioLib.h>
#include "EspHalC3.h"

static const char *TAG = "RAWTX";

// ─── Pins ────────────────────────────────────────────────────────────
#define PIN_SCK     6
#define PIN_MOSI    7
#define PIN_MISO    2
#define PIN_NSS     10
#define PIN_BUSY    4
#define PIN_RST     3
#define PIN_DIO9    5
#define PIN_LED     8
// Debug pins for SPI TX debugging
#define PIN_DEBUG_CS   9  // GPIO to monitor CS state during transactions
#define PIN_DEBUG_DIO  11 // GPIO to monitor DIO9 state

// ─── FLRC Config (MUST match RX) ─────────────────────────────────────
#define FLRC_FREQ_MHZ   2440.0f
#define FLRC_PKT_SIZE   255
#define TX_PKT_COUNT    1000
#define TX_POWER_DBM    12

// Sync word — MUST match RX
#define SYNC_WORD_0   0xCD
#define SYNC_WORD_1   0x05
#define SYNC_WORD_2   0xCA
#define SYNC_WORD_3   0xFE

#define XTAL_MHZ 52.0f

// ─── ESP32 HAL ───────────────────────────────────────────────────────
static EspHalC3 *hal = nullptr;

static inline void rfWaitBusy() {
    uint32_t timeout = esp_timer_get_time() + 50000;
    while (gpio_get_level((gpio_num_t)PIN_BUSY) == 1) {
        if (esp_timer_get_time() > timeout) return;
    }
}

static void rfWriteCmd(const uint8_t *buf, size_t len) {
    rfWaitBusy();
    
    // Debug: Toggle CS debug pin before NSS goes low
    gpio_set_level((gpio_num_t)PIN_DEBUG_CS, 1);
    ESP_LOGD(TAG, "SPI_TX: Pre-CS (cmd=%02X len=%zu)", buf[0], len);
    
    gpio_set_level((gpio_num_t)PIN_NSS, 0);
    hal->spiTransfer(const_cast<uint8_t*>(buf), len, nullptr);
    
    // Debug: Toggle CS debug pin after NSS goes high  
    gpio_set_level((gpio_num_t)PIN_NSS, 1);
    gpio_set_level((gpio_num_t)PIN_DEBUG_CS, 0);
    ESP_LOGD(TAG, "SPI_TX: Post-CS (cmd=%02X completed)", buf[0]);
}

static uint8_t rfReadStatus() {
    uint8_t st = 0;
    rfWaitBusy();
    gpio_set_level((gpio_num_t)PIN_NSS, 0);
    hal->spiTransfer(nullptr, 1, &st);
    gpio_set_level((gpio_num_t)PIN_NSS, 1);
    return st;
}

static uint32_t rfReadIrqStatus() {
    rfWaitBusy();
    gpio_set_level((gpio_num_t)PIN_NSS, 0);
    uint8_t cmd[] = {0x01, 0x17};
    hal->spiTransfer(cmd, 2, nullptr);
    gpio_set_level((gpio_num_t)PIN_NSS, 1);
    rfWaitBusy();

    uint8_t buf[6];
    gpio_set_level((gpio_num_t)PIN_NSS, 0);
    hal->spiTransfer(nullptr, 6, buf);
    gpio_set_level((gpio_num_t)PIN_NSS, 1);
    return ((uint32_t)buf[2] << 24) | ((uint32_t)buf[3] << 16) |
           ((uint32_t)buf[4] << 8)  | (uint32_t)buf[5];
}

static void rfClearIrq() {
    uint8_t cmd[] = {0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF};
    rfWriteCmd(cmd, 6);
}

static void rfClearErrors() {
    uint8_t cmd[] = {0x01, 0x11, 0x00, 0x00};
    rfWriteCmd(cmd, 4);
}

static void rfClearTxFifo() {
    uint8_t cmd[] = {0x01, 0x1F};
    rfWriteCmd(cmd, 2);
}

static void rfSetTx() {
    uint8_t cmd[] = {0x02, 0x0D, 0x00, 0x00, 0x00};
    
    // Debug: Monitor BUSY pin before and during SetTx command
    int busy_before = gpio_get_level((gpio_num_t)PIN_BUSY);
    ESP_LOGD(TAG, "SPI_TX: Pre-SetTx (busy=%d)", busy_before);
    
    rfWriteCmd(cmd, 5);
    
    // Debug: Monitor BUSY pin after SetTx and wait for transition
    int busy_after = gpio_get_level((gpio_num_t)PIN_BUSY);
    ESP_LOGD(TAG, "SPI_TX: Post-SetTx (busy=%d)", busy_after);
    
    // Wait for BUSY to go low (radio ready to transmit)
    uint32_t timeout = esp_timer_get_time() + 10000; // 10ms timeout
    while (gpio_get_level((gpio_num_t)PIN_BUSY) == 1 && esp_timer_get_time() < timeout) {
        // Busy wait for BUSY to go low
    }
    
    int busy_final = gpio_get_level((gpio_num_t)PIN_BUSY);
    uint32_t elapsed = esp_timer_get_time() - (timeout - 10000);
    ESP_LOGD(TAG, "SPI_TX: SetTx complete (busy=%d, wait_us=%lu)", busy_final, (unsigned long)elapsed);
}

static void rfSetRx() {
    uint8_t cmd[] = {0x02, 0x0C, 0xFF, 0xFF, 0xFF};
    rfWriteCmd(cmd, 5);
}

static void rfWriteTxFifo(const uint8_t *data, size_t len) {
    rfWaitBusy();
    
    // Debug: Monitor DIO9 state before FIFO write
    int dio9_state_before = gpio_get_level((gpio_num_t)PIN_DIO9);
    ESP_LOGD(TAG, "SPI_TX: Pre-FIFO (dio9=%d len=%zu)", dio9_state_before, len);
    
    gpio_set_level((gpio_num_t)PIN_DEBUG_CS, 1);
    uint8_t cmd[] = {0x00, 0x02};
    hal->spiTransfer(cmd, 2, nullptr);
    hal->spiTransfer(const_cast<uint8_t*>(data), len, nullptr);
    gpio_set_level((gpio_num_t)PIN_NSS, 1);
    gpio_set_level((gpio_num_t)PIN_DEBUG_CS, 0);
    
    // Debug: Verify FIFO contents by reading back
    uint8_t verify_buf[32]; // Read first 32 bytes for verification
    if (len <= 32) {
        rfWaitBusy();
        gpio_set_level((gpio_num_t)PIN_DEBUG_CS, 1);
        uint8_t read_cmd[] = {0x00, 0x01};
        hal->spiTransfer(read_cmd, 2, nullptr);
        hal->spiTransfer(nullptr, len, verify_buf);
        gpio_set_level((gpio_num_t)PIN_NSS, 1);
        gpio_set_level((gpio_num_t)PIN_DEBUG_CS, 0);
        
        // Compare written vs read data
        bool match = true;
        for (size_t i = 0; i < len && i < 32; i++) {
            if (verify_buf[i] != data[i]) {
                ESP_LOGE(TAG, "FIFO_VERIFY_FAIL: offset %zu wrote=0x%02X read=0x%02X", 
                         i, data[i], verify_buf[i]);
                match = false;
            }
        }
        ESP_LOGD(TAG, "FIFO_VERIFY: %s (len=%zu)", match ? "PASS" : "FAIL", len);
    }
    
    // Debug: Monitor DIO9 state after FIFO write
    int dio9_state_after = gpio_get_level((gpio_num_t)PIN_DIO9);
    ESP_LOGD(TAG, "SPI_TX: Post-FIFO (dio9=%d)", dio9_state_after);
}

static uint32_t frfValue(float freqMhz) {
    return (uint32_t)((freqMhz * 1e6 * (double)(1ULL << 18)) / (XTAL_MHZ * 1e6));
}

// ─── TX-specific raw init (matches RP2040 flrc_raw_tx.cpp) ───────────
static bool rawInitRadio() {
    gpio_set_level((gpio_num_t)PIN_RST, 0);
    esp_rom_delay_us(200);
    gpio_set_level((gpio_num_t)PIN_RST, 1);
    vTaskDelay(pdMS_TO_TICKS(50));

    rfClearErrors();
    vTaskDelay(pdMS_TO_TICKS(1));

    { uint8_t cmd[] = {0x01, 0x28, 0x01}; rfWriteCmd(cmd, 3); }
    vTaskDelay(pdMS_TO_TICKS(5));

    { uint8_t cmd[] = {0x02, 0x07, 0x05}; rfWriteCmd(cmd, 3); }
    vTaskDelay(pdMS_TO_TICKS(1));

    {
        uint32_t frf = frfValue(FLRC_FREQ_MHZ);
        uint8_t cmd[] = {
            0x02, 0x00,
            (uint8_t)(frf >> 16), (uint8_t)(frf >> 8), (uint8_t)(frf & 0xFF)
        };
        rfWriteCmd(cmd, 5);
    }
    vTaskDelay(pdMS_TO_TICKS(1));

    { uint8_t cmd[] = {0x02, 0x01, 0x01, 0x00}; rfWriteCmd(cmd, 4); }
    vTaskDelay(pdMS_TO_TICKS(1));

    {
        uint16_t feFreq = (uint16_t)((FLRC_FREQ_MHZ / 4.0f) + 0.5f) | 0x8000;
        uint8_t cmd[] = {
            0x01, 0x23,
            (uint8_t)(feFreq >> 8), (uint8_t)(feFreq & 0xFF),
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00
        };
        rfWriteCmd(cmd, 10);
    }
    vTaskDelay(pdMS_TO_TICKS(5));

    { uint8_t cmd[] = {0x01, 0x22, 0x5F}; rfWriteCmd(cmd, 3); }
    vTaskDelay(pdMS_TO_TICKS(5));
    rfWaitBusy();

    { uint8_t cmd[] = {0x02, 0x48, 0x00, 0x25}; rfWriteCmd(cmd, 4); }
    vTaskDelay(pdMS_TO_TICKS(1));

    {
        uint8_t cmd[] = {
            0x02, 0x4C, 0x01,
            SYNC_WORD_0, SYNC_WORD_1, SYNC_WORD_2, SYNC_WORD_3
        };
        rfWriteCmd(cmd, 7);
    }
    vTaskDelay(pdMS_TO_TICKS(1));

    {
        uint8_t cmd[] = {
            0x02, 0x49,
            0x0C,   // preamble idx 2 (8 symbols), syncLen = 4/2 = 2
            0x4C,   // SwTx=1, Match1, Fixed, CRC_OFF
            0x00, (uint8_t)FLRC_PKT_SIZE
        };
        rfWriteCmd(cmd, 6);
    }
    vTaskDelay(pdMS_TO_TICKS(1));
    
    // ADD: SET_FLRC_PACKET_PARAMS (0x0249) - missing in original implementation
    {
        uint8_t cmd[] = {
            0x02, 0x49,  // SET_FLRC_PACKET_PARAMS command
            0x00,        // FLRC packet params offset (0x00)
            0x0C,        // Preamble: 12 (8 symbols * 1.5us = 12us)
            0x4C,        // Sync: 0x4C (SwTx=1, Match1, Fixed, CRC_OFF)
            (uint8_t)FLRC_PKT_SIZE,  // Packet length (LSB)
            (uint8_t)(FLRC_PKT_SIZE >> 8)  // Packet length (MSB)
        };
        rfWriteCmd(cmd, 7);
        ESP_LOGI(TAG, "DEBUG: Added SET_FLRC_PACKET_PARAMS (0x0249) call");
    }
    vTaskDelay(pdMS_TO_TICKS(1));

    { uint8_t cmd[] = {0x02, 0x02, 0x80, 0x00, 0x60, 0x07, 0x10}; rfWriteCmd(cmd, 7); }
    vTaskDelay(pdMS_TO_TICKS(1));

    { uint8_t cmd[] = {0x02, 0x03, (uint8_t)(TX_POWER_DBM * 2), 0x04}; rfWriteCmd(cmd, 4); }
    vTaskDelay(pdMS_TO_TICKS(1));

    { uint8_t cmd[] = {0x02, 0x06, 0x03}; rfWriteCmd(cmd, 3); }
    vTaskDelay(pdMS_TO_TICKS(1));

    { uint8_t cmd[] = {0x01, 0x12, 0x09, 0x11}; rfWriteCmd(cmd, 4); }
    vTaskDelay(pdMS_TO_TICKS(1));

    { uint8_t cmd[] = {0x01, 0x15, 0x09, 0x00, 0x08, 0x00, 0x00}; rfWriteCmd(cmd, 7); }
    vTaskDelay(pdMS_TO_TICKS(1));

    rfClearIrq();
    vTaskDelay(pdMS_TO_TICKS(1));

    uint8_t st = rfReadStatus();
    uint32_t irq = rfReadIrqStatus();
    ESP_LOGI(TAG, "INIT Status=0x%02X IRQ=0x%08lX", st, (unsigned long)irq);

    if ((st >> 4) == 0x04 || (st >> 4) == 0x07 || (irq & 0x00020000)) {
        ESP_LOGI(TAG, "RADIO_INIT_OK");
        return true;
    }
    ESP_LOGE(TAG, "RADIO_INIT_FAIL (St=0x%02X)", st);
    return false;
}

// ─── TX burst ────────────────────────────────────────────────────────
static volatile bool radioReady = false;

static void runTransmit() {
    if (!radioReady) { printf("ERR: radio not initialized\n"); fflush(stdout); return; }

    printf("TX_START count=%d pktSize=%d\n", TX_PKT_COUNT, FLRC_PKT_SIZE);
    fflush(stdout);
    vTaskDelay(pdMS_TO_TICKS(10));

    uint8_t pkt[FLRC_PKT_SIZE];
    for (int j = 4; j < FLRC_PKT_SIZE; j++) pkt[j] = (uint8_t)(j & 0xFF);

    uint32_t startMs = (uint32_t)(esp_timer_get_time() / 1000ULL);
    uint32_t txDoneCount = 0;
    uint32_t txTimeoutCount = 0;

    for (int i = 0; i < TX_PKT_COUNT; i++) {
        pkt[0] = (uint8_t)(i >> 24);
        pkt[1] = (uint8_t)(i >> 16);
        pkt[2] = (uint8_t)(i >> 8);
        pkt[3] = (uint8_t)(i & 0xFF);

        rfClearIrq();
        rfWriteTxFifo(pkt, FLRC_PKT_SIZE);
        rfSetTx();

        // Debug: Monitor DIO9 and poll IRQ for TX completion
        uint32_t timeout = esp_timer_get_time() + 50000;
        bool txDone = false;
        uint32_t poll_count = 0;
        
        while (esp_timer_get_time() < timeout) {
            int dio9_state = gpio_get_level((gpio_num_t)PIN_DIO9);
            poll_count++;
            
            // Poll IRQ status every 10 iterations to avoid too much overhead
            if (poll_count % 10 == 0) {
                uint32_t irqStatus = rfReadIrqStatus();
                ESP_LOGD(TAG, "SPI_TX: IRQ poll %lu: dio9=%d IRQ=0x%08lX", 
                         (unsigned long)poll_count, dio9_state, (unsigned long)irqStatus);
                
                // Check for TX-done bit (bit 0 in IRQ status)
                if (irqStatus & 0x00000001) {
                    ESP_LOGD(TAG, "SPI_TX: TX-done detected via IRQ!");
                    txDone = true;
                    break;
                }
            }
            
            if (dio9_state == 1) {
                ESP_LOGD(TAG, "SPI_TX: TX-done detected via DIO9!");
                txDone = true;
                break;
            }
            
            // Small delay to prevent busy-waiting too aggressively
            esp_rom_delay_us(10);
        }

        // Recover on the rare timeout/error path only. TX FIFO auto-clears on
        // TX_DONE, so the happy path skips rfClearTxFifo(). Clear errors only
        // if an error IRQ bit is set (ERROR=bit16, CMD_ERROR=bit17).
        if (!txDone) {
            uint32_t irqStatus = rfReadIrqStatus();
            if (irqStatus & 0x00030000) {
                rfClearErrors();
            }
            rfClearTxFifo();
        }

        if (i < 5) {
            uint8_t stPost = rfReadStatus();
            uint32_t irqStatus = rfReadIrqStatus();
            ESP_LOGI(TAG, "PKT %d: dio9=%d postSt=0x%02X IRQ=0x%08lX",
                     i, txDone ? 1 : 0, stPost, (unsigned long)irqStatus);
        }

        if (txDone) txDoneCount++;
        else txTimeoutCount++;
    }

    pkt[0] = 0xDE; pkt[1] = 0xAD; pkt[2] = 0xBE; pkt[3] = 0xEF;
    pkt[4] = (uint8_t)(TX_PKT_COUNT >> 24);
    pkt[5] = (uint8_t)(TX_PKT_COUNT >> 16);
    pkt[6] = (uint8_t)(TX_PKT_COUNT >> 8);
    pkt[7] = (uint8_t)(TX_PKT_COUNT & 0xFF);
    rfClearIrq();
    rfWriteTxFifo(pkt, FLRC_PKT_SIZE);
    rfSetTx();
    vTaskDelay(pdMS_TO_TICKS(5));

    uint32_t elapsed = (uint32_t)(esp_timer_get_time() / 1000ULL) - startMs;
    float tput = ((float)TX_PKT_COUNT * FLRC_PKT_SIZE * 8.0f) / elapsed;

    printf("=============================================\n");
    printf("  TX sent:     %d\n", TX_PKT_COUNT);
    printf("  TX done:     %lu (timeout %lu)\n",
           (unsigned long)txDoneCount, (unsigned long)txTimeoutCount);
    printf("  Elapsed:     %lu ms\n", (unsigned long)elapsed);
    printf("  TX THROUGHPUT: %.1f kbps\n", tput);
    printf("=============================================\n");
    printf("RESULT_TX,sent=%d,done=%lu,timeout=%lu,elapsed_ms=%lu,throughput_kbps=%.1f\n",
           TX_PKT_COUNT, (unsigned long)txDoneCount, (unsigned long)txTimeoutCount,
           (unsigned long)elapsed, tput);
    fflush(stdout);
}

extern "C" void app_main() {
    setvbuf(stdout, NULL, _IONBF, 0);

    gpio_config_t ledConf = {};
    ledConf.pin_bit_mask = (1ULL << PIN_LED);
    ledConf.mode = GPIO_MODE_OUTPUT;
    gpio_config(&ledConf);

    for (volatile int i = 0; i < 5; i++) {
        gpio_set_level((gpio_num_t)PIN_LED, 1);
        vTaskDelay(pdMS_TO_TICKS(100));
        gpio_set_level((gpio_num_t)PIN_LED, 0);
        vTaskDelay(pdMS_TO_TICKS(100));
    }

    vTaskDelay(pdMS_TO_TICKS(2000));

    for (int hello = 0; hello < 12; hello++) {
        printf("HELLO FROM ESP32 RAW_TX\n");
        fflush(stdout);
        vTaskDelay(pdMS_TO_TICKS(250));
    }

    ESP_LOGI(TAG, "=== ESP32 FLRC TX (RAW SPI + GDMA) ===");

    for (volatile int i = 0; i < 3; i++) {
        gpio_set_level((gpio_num_t)PIN_LED, 1);
        vTaskDelay(pdMS_TO_TICKS(200));
        gpio_set_level((gpio_num_t)PIN_LED, 0);
        vTaskDelay(pdMS_TO_TICKS(200));
    }

    gpio_config_t csConf = {};
    csConf.pin_bit_mask = (1ULL << PIN_NSS);
    csConf.mode = GPIO_MODE_OUTPUT;
    gpio_config(&csConf);
    gpio_set_level((gpio_num_t)PIN_NSS, 1);

    // Configure debug GPIO pins for monitoring
    gpio_config_t debugConf = {};
    debugConf.pin_bit_mask = (1ULL << PIN_DEBUG_CS) | (1ULL << PIN_DEBUG_DIO);
    debugConf.mode = GPIO_MODE_OUTPUT;
    gpio_config(&debugConf);
    gpio_set_level((gpio_num_t)PIN_DEBUG_CS, 0);
    gpio_set_level((gpio_num_t)PIN_DEBUG_DIO, 0);

    gpio_config_t busyConf = {};
    busyConf.pin_bit_mask = (1ULL << PIN_BUSY);
    busyConf.mode = GPIO_MODE_INPUT;
    gpio_config(&busyConf);

    gpio_config_t dioConf = {};
    dioConf.pin_bit_mask = (1ULL << PIN_DIO9);
    dioConf.mode = GPIO_MODE_INPUT;
    gpio_config(&dioConf);

    gpio_config_t rstConf = {};
    rstConf.pin_bit_mask = (1ULL << PIN_RST);
    rstConf.mode = GPIO_MODE_OUTPUT;
    gpio_config(&rstConf);
    gpio_set_level((gpio_num_t)PIN_RST, 1);

    hal = new EspHalC3(PIN_SCK, PIN_MISO, PIN_MOSI);
    hal->init();
    hal->setCsPin(PIN_NSS);
    hal->setBusyPin(PIN_BUSY);

    printf("\n");
    printf("=================================================\n");
    printf("  ESP32 FLRC TX (RAW SPI + GDMA)\n");
    printf("  No RadioLib — raw SPI init (52 MHz XTAL)\n");
    printf("  Freq=%.1f MHz, %d dBm, syncword=CD05CAFE\n", FLRC_FREQ_MHZ, TX_POWER_DBM);
    printf("  SPI clock = %d Hz\n", ESPHAL_C3_SPI_HZ);
    printf("=================================================\n");
    printf("\n");
    fflush(stdout);

    radioReady = rawInitRadio();
    if (radioReady) {
        printf("RADIO_INIT_OK\n");
        gpio_set_level((gpio_num_t)PIN_LED, 0);
        printf("TX_START_IN_10S\n");
        fflush(stdout);
        vTaskDelay(pdMS_TO_TICKS(10000));
        runTransmit();
        gpio_set_level((gpio_num_t)PIN_LED, 1);
        while (true) {
            ESP_LOGI(TAG, "Next TX burst in 15s...");
            vTaskDelay(pdMS_TO_TICKS(15000));
            runTransmit();
        }
    } else {
        printf("RADIO_INIT_FAILED\n");
        ESP_LOGE(TAG, "INIT FAILED — stuck here");
        while (true) { vTaskDelay(pdMS_TO_TICKS(1000)); }
    }
}

#endif
