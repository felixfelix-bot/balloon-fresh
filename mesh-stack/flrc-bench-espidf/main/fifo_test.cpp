#define RADIOLIB_GODMODE 1

#include <sdkconfig.h>

#ifdef CONFIG_BENCH_MODE_FIFO_TEST

#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "driver/gpio.h"
#include <RadioLib.h>
#include "EspHalC3.h"
#include "prbs.h"

static const char *TAG = "FIFO";

#define LED_GPIO 8

#define LR2021_SCK   6
#define LR2021_MISO  2
#define LR2021_MOSI  7
#define LR2021_NSS   10
#define LR2021_BUSY  4
#define LR2021_RST   3
#define LR2021_DIO9  5

static EspHalC3 *hal = nullptr;
static Module *mod = nullptr;
static LR2021 *radio = nullptr;
static volatile bool irqFlag = false;

static void IRAM_ATTR onIrq(void) { irqFlag = true; }

static void blink(int times, int on_ms, int off_ms) {
    gpio_config_t io = {};
    io.pin_bit_mask = (1ULL << LED_GPIO);
    io.mode = GPIO_MODE_OUTPUT;
    gpio_config(&io);
    for (int i = 0; i < times; i++) {
        gpio_set_level((gpio_num_t)LED_GPIO, 0);
        vTaskDelay(pdMS_TO_TICKS(on_ms));
        gpio_set_level((gpio_num_t)LED_GPIO, 1);
        vTaskDelay(pdMS_TO_TICKS(off_ms));
    }
    gpio_set_level((gpio_num_t)LED_GPIO, 1);
}

struct SizeTest {
    const char *name;
    uint8_t pktSize;
    uint8_t pktCount;
};

static const SizeTest sizeTests[] = {
    {"20B",  20,  10},
    {"50B",  50,   5},
    {"100B", 100,  3},
    {"255B", 255,  1},
};
static const int sizeTestCount = sizeof(sizeTests) / sizeof(sizeTests[0]);

static void runPhase1_FifoDepth() {
    ESP_LOGI(TAG, "=== Phase 1: FIFO Depth Discovery ===");
    printf("\n--- Phase 1: FIFO Depth Discovery ---\n");
    printf("TX should send burst of N packets, then wait.\n");
    printf("pkt_size,pkt_count_sent,fifo_level_bytes,pkts_in_fifo,batch_ratio\n");
    fflush(stdout);

    for (int t = 0; t < sizeTestCount; t++) {
        const SizeTest *tc = &sizeTests[t];
        ESP_LOGI(TAG, "Test %d: %s (%d x %d bytes)", t+1, tc->name, tc->pktCount, tc->pktSize);

        radio->clearRxFifo();
        radio->startReceive();
        irqFlag = false;

        ESP_LOGI(TAG, "Waiting 5s for TX burst of %d pkts x %d bytes...",
                 tc->pktCount, tc->pktSize);
        vTaskDelay(pdMS_TO_TICKS(5000));

        uint16_t fifoLevel = 0;
        int16_t state = radio->getRxFifoLevel(&fifoLevel);
        ESP_LOGI(TAG, "getRxFifoLevel: state=%d level=%u", state, fifoLevel);

        int pktsInFifo = 0;
        if (fifoLevel > 0 && tc->pktSize > 0) {
            pktsInFifo = fifoLevel / tc->pktSize;
            if (fifoLevel % tc->pktSize != 0) pktsInFifo++;
        }

        float batchRatio = tc->pktCount > 0 ? (float)pktsInFifo / tc->pktCount : 0;

        printf("%d,%d,%u,%d,%.2f\n",
               tc->pktSize, tc->pktCount, fifoLevel, pktsInFifo, batchRatio);
        fflush(stdout);

        radio->standby();
        radio->clearRxFifo();
        blink(1, 200, 200);
        vTaskDelay(pdMS_TO_TICKS(2000));
    }
}

static void runPhase2_ReadSpeed() {
    ESP_LOGI(TAG, "=== Phase 2: FIFO Read Speed ===");
    printf("\n--- Phase 2: FIFO Read Speed ---\n");
    printf("Measuring readRadioRxFifo speed (radio RX active, no TX needed)\n");
    printf("read_bytes,read_us,throughput_mbps\n");
    fflush(stdout);

    static uint8_t readBuf[512];

    radio->startReceive();

    const int readSizes[] = {20, 50, 100, 128, 200, 255};
    const int readSizeCount = sizeof(readSizes) / sizeof(readSizes[0]);

    for (int s = 0; s < readSizeCount; s++) {
        int sz = readSizes[s];
        memset(readBuf, 0, sizeof(readBuf));

        uint32_t t0 = (uint32_t)esp_timer_get_time();
        radio->readRadioRxFifo(readBuf, sz);
        uint32_t t1 = (uint32_t)esp_timer_get_time();
        uint32_t readUs = t1 - t0;

        float throughputMbps = readUs > 0 ? (float)sz * 8.0f / readUs : 0;

        printf("%d,%lu,%.2f\n", sz, (unsigned long)readUs, throughputMbps);
        fflush(stdout);

        ESP_LOGI(TAG, "Read %d bytes in %lu us = %.2f Mbps",
                 sz, (unsigned long)readUs, throughputMbps);
        vTaskDelay(pdMS_TO_TICKS(100));
    }
}

static void runPhase3_AutoRx() {
    ESP_LOGI(TAG, "=== Phase 3: Auto-RX Mode ===");
    printf("\n--- Phase 3: Auto-RX Mode ---\n");
    printf("Configuring autoTxRx, TX should send burst\n");
    printf("Testing if radio stays in RX without manual restart\n");
    fflush(stdout);

    radio->clearRxFifo();
    radio->standby();

    int16_t state = radio->autoTxRx(0,
                        RADIOLIB_LR2021_AUTO_MODE_ALWAYS, 0xFFFFFF);
    ESP_LOGI(TAG, "autoTxRx state: %d", state);

    radio->startReceive();
    irqFlag = false;

    ESP_LOGI(TAG, "Waiting 5s for TX burst (auto-RX mode)...");
    vTaskDelay(pdMS_TO_TICKS(5000));

    uint16_t fifoLevel = 0;
    radio->getRxFifoLevel(&fifoLevel);
    ESP_LOGI(TAG, "After auto-RX: FIFO level = %u", fifoLevel);

    uint8_t rxFlags = 0, txFlags = 0;
    radio->getFifoIrqFlags(&rxFlags, &txFlags);
    ESP_LOGI(TAG, "FIFO IRQ flags: rx=0x%02X tx=0x%02X", rxFlags, txFlags);

    printf("auto_rx_fifo_level,%u\n", fifoLevel);
    printf("auto_rx_fifo_flags,0x%02X\n", rxFlags);
    fflush(stdout);

    radio->standby();
    radio->autoTxRx(0, RADIOLIB_LR2021_AUTO_MODE_NONE, 0);
    blink(2, 200, 200);
}

static void runPhase5_Throughput() {
    ESP_LOGI(TAG, "=== Phase 5: End-to-End Throughput ===");
    printf("\n--- Phase 5: End-to-End Throughput (no PRBS) ---\n");
    printf("TX should send 100 pkts of each size continuously\n");
    printf("pkt_size,rx_received,rx_errors,elapsed_ms,throughput_kbps,per_pct\n");
    fflush(stdout);

    static const SizeTest tputTests[] = {
        {"20B",   20, 100},
        {"50B",   50, 100},
        {"100B", 100, 100},
        {"255B", 255, 100},
    };
    const int tputCount = sizeof(tputTests) / sizeof(tputTests[0]);

    uint8_t buf[256];

    for (int t = 0; t < tputCount; t++) {
        const SizeTest *tc = &tputTests[t];
        ESP_LOGI(TAG, "Throughput test: %s", tc->name);

        radio->clearRxFifo();
        radio->startReceive();
        irqFlag = false;

        uint32_t received = 0;
        uint32_t errors = 0;
        uint32_t startMs = (uint32_t)(esp_timer_get_time() / 1000ULL);
        uint32_t timeout = 15000;

        while (received < (uint32_t)tc->pktCount &&
               (uint32_t)(esp_timer_get_time() / 1000ULL) - startMs < timeout) {
            if (!irqFlag) {
                taskYIELD();
                continue;
            }
            irqFlag = false;

            int16_t len = radio->getPacketLength();
            if (len <= 0) {
                radio->standby();
                radio->startReceive();
                continue;
            }

            int16_t state = radio->readData(buf, len);
            radio->standby();
            radio->startReceive();

            if (state == RADIOLIB_ERR_NONE) {
                received++;
            } else {
                errors++;
            }
        }

        uint32_t elapsed = (uint32_t)(esp_timer_get_time() / 1000ULL) - startMs;
        float tput = (elapsed > 0 && received > 0)
            ? (float)received * tc->pktSize * 8.0f / elapsed : 0;
        float per = tc->pktCount > 0
            ? (tc->pktCount - received) * 100.0f / tc->pktCount : 0;

        printf("%d,%lu,%lu,%lu,%.1f,%.1f\n",
               tc->pktSize, (unsigned long)received, (unsigned long)errors,
               (unsigned long)elapsed, tput, per);
        fflush(stdout);

        ESP_LOGI(TAG, "%s: recv=%lu/%d elapsed=%lums tput=%.1fkbps",
                 tc->name, (unsigned long)received, tc->pktCount,
                 (unsigned long)elapsed, tput);

        blink(1, 200, 200);
        vTaskDelay(pdMS_TO_TICKS(2000));
    }
}

extern "C" void app_main() {
    ESP_LOGI(TAG, "=== LR2021 FIFO Throughput Test (GODMODE) ===");
    setvbuf(stdout, NULL, _IONBF, 0);
    blink(3, 200, 200);
    vTaskDelay(pdMS_TO_TICKS(2000));

    hal = new EspHalC3(LR2021_SCK, LR2021_MISO, LR2021_MOSI);
    hal->setCsPin(LR2021_NSS);
    hal->setBusyPin(LR2021_BUSY);
    mod = new Module(hal, LR2021_NSS, LR2021_DIO9, LR2021_RST, LR2021_BUSY);
    radio = new LR2021(mod);
    radio->irqDioNum = 9;

    printf("\n");
    printf("=================================================\n");
    printf("  LR2021 FIFO Throughput Test (GODMODE)\n");
    printf("  Mode: FLRC 2600 kbps @ 2450 MHz, +12 dBm\n");
    printf("  Uses native LR2021 FIFO API via RADIOLIB_GODMODE\n");
    printf("=================================================\n");
    printf("\n");
    fflush(stdout);

    ESP_LOGI(TAG, "Initializing radio...");
    int16_t state = radio->beginFLRC(2450.0f, 2600, 0x02, 12,
                                     16, RADIOLIB_SHAPING_0_5, 0.0f);
    if (state != RADIOLIB_ERR_NONE) {
        ESP_LOGE(TAG, "Radio init failed: %d", state);
        blink(10, 500, 500);
        return;
    }
    ESP_LOGI(TAG, "Radio initialized OK");

    radio->fixedPacketLengthMode(255);
    radio->setPacketReceivedAction(onIrq);

    radio->configFifoIrq(RADIOLIB_LR2021_FIFO_IRQ_FULL, 0, 200, 0);
    ESP_LOGI(TAG, "FIFO IRQ configured: FULL + HIGH@200");

    runPhase1_FifoDepth();
    runPhase2_ReadSpeed();
    runPhase3_AutoRx();
    runPhase5_Throughput();

    printf("\n");
    printf("=================================================\n");
    printf("  ALL TESTS COMPLETE\n");
    printf("=================================================\n");
    printf("\n");
    printf("Phase 1: If batch_ratio > 1.0 → FIFO batches!\n");
    printf("Phase 2: Read speed shows SPI throughput limit\n");
    printf("Phase 3: Auto-RX FIFO level shows if radio stays receiving\n");
    printf("Phase 5: Throughput with no-PRBS, different sizes\n");
    printf("\n");
    fflush(stdout);

    blink(5, 200, 200);
    while (true) {
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}

#endif
