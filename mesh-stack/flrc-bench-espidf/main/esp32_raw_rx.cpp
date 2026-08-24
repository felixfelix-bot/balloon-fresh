/*
 * esp32_raw_rx.cpp — ESP32 FLRC RX with RAW SPI init + DIO9 polling
 *
 * Direct port of RP2040 flrc_raw_rx.cpp. No RadioLib for init.
 * Uses raw SPI register writes and polls DIO9 (GPIO5).
 *
 * Pins: SCK=6 MISO=2 MOSI=7 NSS=10 BUSY=4 RST=3 DIO9=5 LED=8
 */

#include <sdkconfig.h>

#ifdef CONFIG_BENCH_MODE_RAW_RX

#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "driver/gpio.h"
#include <RadioLib.h>
#include "EspHalC3.h"

static const char *TAG = "RAWRX";

// ─── Pins ────────────────────────────────────────────────────────────
#define PIN_SCK     6
#define PIN_MOSI    7
#define PIN_MISO    2
#define PIN_NSS     10
#define PIN_BUSY    4
#define PIN_RST     3
#define PIN_DIO9    5
#define PIN_LED     8

// ─── FLRC Config ─────────────────────────────────────────────────────
#define FLRC_FREQ_MHZ   2440.0f
#define FLRC_PKT_SIZE   255
#define TX_POWER_DBM    12
#define RX_LISTEN_MS    30000
#define RX_SILENCE_MS   5000
#define PRINT_EVERY     50

// Sync word — MUST match TX
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
    gpio_set_level((gpio_num_t)PIN_NSS, 0);
    hal->spiTransfer(const_cast<uint8_t*>(buf), len, nullptr);
    gpio_set_level((gpio_num_t)PIN_NSS, 1);
}

static uint8_t rfReadStatus() {
    uint8_t st = 0;
    rfWaitBusy();
    gpio_set_level((gpio_num_t)PIN_NSS, 0);
    hal->spiTransfer(nullptr, 1, &st);
    gpio_set_level((gpio_num_t)PIN_NSS, 1);
    return st;
}

static void rfReadFifo(uint8_t *buf, size_t len) {
    rfWaitBusy();
    gpio_set_level((gpio_num_t)PIN_NSS, 0);
    uint8_t cmd[] = {0x00, 0x01};
    hal->spiTransfer(cmd, 2, nullptr);
    hal->spiTransfer(nullptr, len, buf);
    gpio_set_level((gpio_num_t)PIN_NSS, 1);
}

static uint32_t rfReadIrqStatus() {
    rfWaitBusy();
    gpio_set_level((gpio_num_t)PIN_NSS, 0);
    uint8_t cmd[] = {0x01, 0x17};
    hal->spiTransfer(cmd, 2, nullptr);
    gpio_set_level((gpio_num_t)PIN_NSS, 1);
    rfWaitBusy();

    uint8_t b[6];
    gpio_set_level((gpio_num_t)PIN_NSS, 0);
    hal->spiTransfer(nullptr, 6, b);
    gpio_set_level((gpio_num_t)PIN_NSS, 1);
    return ((uint32_t)b[2] << 24) | ((uint32_t)b[3] << 16) |
           ((uint32_t)b[4] << 8)  | (uint32_t)b[5];
}

static void rfClearIrq() {
    uint8_t cmd[] = {0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF};
    rfWriteCmd(cmd, 6);
}

static void rfSetRx() {
    uint8_t cmd[] = {0x02, 0x0C, 0xFF, 0xFF, 0xFF};
    rfWriteCmd(cmd, 5);
}

static uint32_t frfValue(float freqMhz) {
    return (uint32_t)((freqMhz * 1e6 * (double)(1ULL << 18)) / (XTAL_MHZ * 1e6));
}

// ─── RX raw init (matches RP2040 flrc_raw_rx.cpp) ────────────────────
static bool rawInitRadio() {
    gpio_set_level((gpio_num_t)PIN_RST, 0);
    vTaskDelay(pdMS_TO_TICKS(1));
    gpio_set_level((gpio_num_t)PIN_RST, 1);
    vTaskDelay(pdMS_TO_TICKS(50));

    { uint8_t cmd[] = {0x01, 0x11, 0x00, 0x00}; rfWriteCmd(cmd, 4); }
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

    { uint8_t cmd[] = {0x02, 0x48, 0x00, 0x25}; rfWriteCmd(cmd, 4); }
    vTaskDelay(pdMS_TO_TICKS(1));

    {
        uint8_t cmd[] = {0x02, 0x4C, 0x01, SYNC_WORD_0, SYNC_WORD_1, SYNC_WORD_2, SYNC_WORD_3};
        rfWriteCmd(cmd, 7);
    }
    vTaskDelay(pdMS_TO_TICKS(1));

    {
        uint8_t cmd[] = {
            0x02, 0x49,
            0x0C,   // preamble idx 2 (8 symbols), syncLen = 4/2 = 2
            0x0C,   // SwTx=0 (RX), Match1, Fixed, CRC_OFF
            0x00, (uint8_t)FLRC_PKT_SIZE
        };
        rfWriteCmd(cmd, 6);
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

    { uint8_t cmd[] = {0x01, 0x15, 0x09, 0x00, 0x04, 0x00, 0x00}; rfWriteCmd(cmd, 7); }
    vTaskDelay(pdMS_TO_TICKS(1));

    rfClearIrq();
    vTaskDelay(pdMS_TO_TICKS(1));
    rfSetRx();
    vTaskDelay(pdMS_TO_TICKS(2));

    uint8_t st = rfReadStatus();
    uint32_t irq = rfReadIrqStatus();
    ESP_LOGI(TAG, "INIT Status=0x%02X IRQ=0x%08lX", st, (unsigned long)irq);

    if ((st >> 4) == 0x05 || (st >> 4) == 0x07 || (irq & 0x00020000)) {
        ESP_LOGI(TAG, "RADIO_INIT_OK (RX mode)");
        return true;
    }
    ESP_LOGE(TAG, "RADIO_INIT_FAIL (St=0x%02X)", st);
    return false;
}

// ─── Statistics ──────────────────────────────────────────────────────
struct RxStats {
    uint32_t received;
    uint32_t unique;
    uint32_t duplicates;
    uint32_t lastSeq;
    uint32_t maxSeq;
    uint32_t totalSentByTx;
    uint32_t startMs;
    uint32_t elapsedMs;
};

static RxStats stats;

static void resetStats() {
    memset(&stats, 0, sizeof(stats));
    stats.lastSeq = 0xFFFFFFFF;
}

// ─── Receive session ─────────────────────────────────────────────────
static bool radioReady = false;

static void runReceive() {
    if (!radioReady) { printf("ERR: radio not initialized\n"); fflush(stdout); return; }

    resetStats();
    stats.startMs = (uint32_t)(esp_timer_get_time() / 1000ULL);
    uint32_t lastPktMs = stats.startMs;
    uint8_t buf[FLRC_PKT_SIZE];

    rfClearIrq();
    rfSetRx();
    vTaskDelay(pdMS_TO_TICKS(1));

    printf("RX_START listening for FLRC packets...\n");
    fflush(stdout);

    bool stopped = false;
    while (!stopped) {
        uint32_t now = (uint32_t)(esp_timer_get_time() / 1000ULL);

        if ((now - stats.startMs) >= RX_LISTEN_MS) {
            printf("RX_TIMEOUT: listen window expired\n");
            stopped = true;
            break;
        }
        if (stats.received > 0 && (now - lastPktMs) >= RX_SILENCE_MS) {
            printf("RX_TIMEOUT: silence, stopping\n");
            stopped = true;
            break;
        }

        if (gpio_get_level((gpio_num_t)PIN_DIO9) != 1) {
            taskYIELD();
            continue;
        }

        uint32_t irqFlags = rfReadIrqStatus();
        rfReadFifo(buf, FLRC_PKT_SIZE);
        rfClearIrq();
        rfSetRx();

        uint32_t seq = ((uint32_t)buf[0] << 24) | ((uint32_t)buf[1] << 16) |
                       ((uint32_t)buf[2] << 8)  | (uint32_t)buf[3];

        if (buf[0] == 0xDE && buf[1] == 0xAD && buf[2] == 0xBE && buf[3] == 0xEF) {
            stats.totalSentByTx = ((uint32_t)buf[4] << 24) | ((uint32_t)buf[5] << 16) |
                                  ((uint32_t)buf[6] << 8)  | (uint32_t)buf[7];
            stats.elapsedMs = (uint32_t)(esp_timer_get_time() / 1000ULL) - stats.startMs;
            printf("RX_END: received DEADBEEF end marker\n");
            fflush(stdout);
            break;
        }

        stats.received++;
        if (stats.lastSeq != 0xFFFFFFFF && seq == stats.lastSeq) stats.duplicates++;
        else stats.unique++;
        stats.lastSeq = seq;
        if (seq > stats.maxSeq) stats.maxSeq = seq;
        lastPktMs = (uint32_t)(esp_timer_get_time() / 1000ULL);

        if (stats.received <= 5 || (stats.received % PRINT_EVERY) == 0) {
            ESP_LOGI(TAG, "PKT rx=%lu seq=%lu IRQ=0x%08lX",
                     (unsigned long)stats.received, (unsigned long)seq,
                     (unsigned long)irqFlags);
        }
    }

    if (stats.elapsedMs == 0)
        stats.elapsedMs = (uint32_t)(esp_timer_get_time() / 1000ULL) - stats.startMs;

    uint32_t n = stats.received;
    uint32_t total = stats.totalSentByTx > 0 ? stats.totalSentByTx : (stats.maxSeq + 1);
    uint32_t lost = (total > n) ? (total - n) : 0;
    float perPct = (total > 0) ? (100.0f * (float)lost / (float)total) : 0.0f;
    float tputKbps = (stats.elapsedMs > 0 && n > 0)
                     ? ((float)n * (float)FLRC_PKT_SIZE * 8.0f) / ((float)stats.elapsedMs)
                     : 0.0f;

    printf("=============================================\n");
    printf("  Received:    %lu (unique %lu, dup %lu)\n",
           (unsigned long)n, (unsigned long)stats.unique, (unsigned long)stats.duplicates);
    printf("  TX sent:     %lu\n", (unsigned long)stats.totalSentByTx);
    printf("  Lost:        %lu (%.2f%%)\n", (unsigned long)lost, perPct);
    printf("  Elapsed:     %lu ms\n", (unsigned long)stats.elapsedMs);
    printf("  Throughput:  %.1f kbps\n", tputKbps);
    printf("=============================================\n");
    printf("RESULT,rx=%lu,unique=%lu,dup=%lu,lost=%lu,total=%lu,per=%.2f,elapsed_ms=%lu,throughput_kbps=%.1f\n",
           (unsigned long)n, (unsigned long)stats.unique, (unsigned long)stats.duplicates,
           (unsigned long)lost, (unsigned long)total, perPct,
           (unsigned long)stats.elapsedMs, tputKbps);
    fflush(stdout);
}

extern "C" void app_main() {
    setvbuf(stdout, NULL, _IONBF, 0);
    vTaskDelay(pdMS_TO_TICKS(500));

    gpio_config_t ledConf = {};
    ledConf.pin_bit_mask = (1ULL << PIN_LED);
    ledConf.mode = GPIO_MODE_OUTPUT;
    gpio_config(&ledConf);
    gpio_set_level((gpio_num_t)PIN_LED, 1);

    for (int i = 0; i < 3; i++) {
        printf("BOOT %d\n", i+1);
        fflush(stdout);
        gpio_set_level((gpio_num_t)PIN_LED, 0);
        vTaskDelay(pdMS_TO_TICKS(200));
        gpio_set_level((gpio_num_t)PIN_LED, 1);
        vTaskDelay(pdMS_TO_TICKS(200));
    }
    printf("HELLO FROM ESP32 RAW_RX\n");
    fflush(stdout);

    gpio_config_t csConf = {};
    csConf.pin_bit_mask = (1ULL << PIN_NSS);
    csConf.mode = GPIO_MODE_OUTPUT;
    gpio_config(&csConf);
    gpio_set_level((gpio_num_t)PIN_NSS, 1);

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
    printf("  ESP32 FLRC RX (RAW SPI + DIO9 POLL)\n");
    printf("  No RadioLib, no interrupts — raw SPI + pin poll\n");
    printf("  Freq=%.1f MHz, 255B fixed, syncword=CD05CAFE\n", FLRC_FREQ_MHZ);
    printf("  SPI clock = %d Hz\n", ESPHAL_C3_SPI_HZ);
    printf("=================================================\n");
    printf("\n");
    fflush(stdout);

    radioReady = rawInitRadio();
    if (radioReady) {
        ESP_LOGI(TAG, "RADIO_INIT_OK");
        printf("RADIO_INIT_OK\n");
    } else {
        ESP_LOGE(TAG, "RADIO_INIT_FAILED");
        printf("RADIO_INIT_FAILED\n");
    }
    fflush(stdout);

    ESP_LOGI(TAG, "RX starts in 3s...");
    vTaskDelay(pdMS_TO_TICKS(3000));

    while (true) {
        runReceive();
        ESP_LOGI(TAG, "Next RX window in 5s...");
        vTaskDelay(pdMS_TO_TICKS(5000));
    }
}

#endif
