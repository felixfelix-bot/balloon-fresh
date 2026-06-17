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

struct TestConfig {
    const char *name;
    uint8_t pktSize;
    uint8_t pktCount;
    bool skipPrbs;
};

static const TestConfig tests[] = {
    {"20B_noprbs",   20, 100, true},
    {"50B_noprbs",   50, 100, true},
    {"100B_noprbs", 100, 100, true},
    {"255B_noprbs", 255, 100, true},
    {"100B_prbs",   100, 100, false},
    {"255B_prbs",   255, 100, false},
};
static const int testCount = sizeof(tests) / sizeof(tests[0]);

static uint32_t measureTest(const TestConfig *tc) {
    uint8_t buf[256];
    uint32_t totalReceived = 0;
    uint32_t totalErrors = 0;
    uint32_t totalBitErrors = 0;
    uint32_t totalBitsChecked = 0;
    int16_t rssiSum = 0;
    int16_t rssiCount = 0;

    radio->startReceive();
    irqFlag = false;

    uint32_t testStart = (uint32_t)(esp_timer_get_time() / 1000ULL);
    uint32_t timeout = 15000;

    while (totalReceived < tc->pktCount &&
           (uint32_t)(esp_timer_get_time() / 1000ULL) - testStart < timeout) {
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
        float rssi = radio->getRSSI(false);
        radio->standby();
        radio->startReceive();

        if (state == RADIOLIB_ERR_NONE) {
            totalReceived++;
            rssiSum += (int16_t)rssi;
            rssiCount++;

            if (!tc->skipPrbs && len >= 4) {
                uint32_t seq = ((uint32_t)buf[0] << 24) | ((uint32_t)buf[1] << 16) |
                               ((uint32_t)buf[2] << 8) | (uint32_t)buf[3];
                uint16_t bytesBad = 0;
                if ((size_t)len > 4) {
                    uint16_t bitErr = prbs15_verify(buf + 4, len - 4, seq, &bytesBad);
                    totalBitErrors += bitErr;
                    totalBitsChecked += (len - 4) * 8;
                    if (bytesBad > 0) totalErrors++;
                }
            }
        } else {
            totalErrors++;
            radio->standby();
            radio->startReceive();
        }
    }

    uint32_t elapsed = (uint32_t)(esp_timer_get_time() / 1000ULL) - testStart;
    float avgRssi = rssiCount > 0 ? (float)rssiSum / rssiCount : 0;
    float perPct = tc->pktCount > 0 ? (tc->pktCount - totalReceived) * 100.0f / tc->pktCount : 0;
    float throughput = (elapsed > 0 && totalReceived > 0)
        ? (float)totalReceived * tc->pktSize * 8.0f / elapsed
        : 0;

    printf("%s,%d,%d,%lu,%lu,%lu,%.1f,%.3f,%.1f,%.0f\n",
           tc->name, tc->pktSize, tc->pktCount,
           (unsigned long)totalReceived, (unsigned long)totalErrors,
           (unsigned long)elapsed,
           throughput, perPct,
           avgRssi,
           tc->skipPrbs ? 0.0f : (totalBitsChecked > 0 ? (float)totalBitErrors * 100.0f / totalBitsChecked : 0));
    fflush(stdout);

    ESP_LOGI(TAG, "%s: recv=%lu/%d elapsed=%lums tput=%.1fkbps PER=%.1f%% RSSI=%.0f",
             tc->name, (unsigned long)totalReceived, tc->pktCount,
             (unsigned long)elapsed, throughput, perPct, avgRssi);

    return elapsed;
}

extern "C" void app_main() {
    ESP_LOGI(TAG, "=== LR2021 Throughput Test ===");
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
    printf("  LR2021 Throughput Test (Public API)\n");
    printf("  Mode: FLRC 2600 kbps @ 2450 MHz, +12 dBm\n");
    printf("  Tests throughput with/without PRBS verification\n");
    printf("  Run TX board with matching FLRC config\n");
    printf("=================================================\n");
    printf("\n");
    printf("test_name,pkt_size,pkt_count,rx_received,rx_errors,");
    printf("elapsed_ms,throughput_kbps,per_pct,avg_rssi,ber_pct\n");
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

    radio->setPacketReceivedAction(onIrq);

    for (int t = 0; t < testCount; t++) {
        ESP_LOGI(TAG, "=== Test %d/%d: %s ===", t + 1, testCount, tests[t].name);
        blink(1, 100, 100);
        vTaskDelay(pdMS_TO_TICKS(1000));
        measureTest(&tests[t]);
        vTaskDelay(pdMS_TO_TICKS(2000));
    }

    printf("\n");
    printf("=================================================\n");
    printf("  THROUGHPUT TEST COMPLETE\n");
    printf("=================================================\n");
    printf("\n");
    printf("Compare no-PRBS vs PRBS to see CPU overhead.\n");
    printf("Compare 20B vs 255B to see packet size impact.\n");
    printf("Current baseline: 80 kbps with 200B packets + PRBS.\n");
    printf("\n");
    fflush(stdout);

    blink(5, 200, 200);
    while (true) {
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}

#endif
