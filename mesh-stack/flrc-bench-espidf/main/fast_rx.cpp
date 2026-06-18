#include <sdkconfig.h>

#ifdef CONFIG_BENCH_MODE_FAST_RX

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

static const char *TAG = "FASTRX";

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

#define PKT_SIZE 255
#define PKT_COUNT 100
#define TEST_TIMEOUT_MS 15000

struct OptConfig {
    const char *name;
    bool verifyPrbs;
    bool readRssi;
    bool skipExtraStandby;
    bool useTaskYield;
};

static const OptConfig configs[] = {
    {"C3_fast",     false, false, true,  true },
};
static const int configCount = sizeof(configs) / sizeof(configs[0]);

static void runConfig(const OptConfig *cfg) {
    uint8_t buf[PKT_SIZE + 4];
    uint32_t received = 0;
    uint32_t errors = 0;

    radio->startReceive();
    irqFlag = false;

    uint32_t startMs = (uint32_t)(esp_timer_get_time() / 1000ULL);

    while (received < PKT_COUNT &&
           (uint32_t)(esp_timer_get_time() / 1000ULL) - startMs < TEST_TIMEOUT_MS) {

        if (!irqFlag) {
            if (cfg->useTaskYield) {
                taskYIELD();
            } else {
                vTaskDelay(pdMS_TO_TICKS(1));
            }
            continue;
        }
        irqFlag = false;

        int16_t len = PKT_SIZE;
        int16_t state = radio->readData(buf, len);

        if (cfg->readRssi) {
            radio->getRSSI(false);
        }

        if (!cfg->skipExtraStandby) {
            radio->standby();
        }
        radio->startReceive();

        if (state == RADIOLIB_ERR_NONE) {
            received++;

            if (cfg->verifyPrbs && len >= 4) {
                uint32_t seq = ((uint32_t)buf[0] << 24) | ((uint32_t)buf[1] << 16) |
                               ((uint32_t)buf[2] << 8) | (uint32_t)buf[3];
                uint16_t bytesBad = 0;
                if ((size_t)len > 4) {
                    prbs15_verify(buf + 4, len - 4, seq, &bytesBad);
                }
            }
        } else {
            errors++;
        }
    }

    uint32_t elapsed = (uint32_t)(esp_timer_get_time() / 1000ULL) - startMs;
    float tput = (elapsed > 0 && received > 0)
        ? (float)received * PKT_SIZE * 8.0f / elapsed : 0;
    float per = (PKT_COUNT - received) * 100.0f / PKT_COUNT;

    printf("%s,%d,%lu,%lu,%lu,%.1f,%.1f\n",
           cfg->name, PKT_SIZE,
           (unsigned long)received, (unsigned long)errors,
           (unsigned long)elapsed, tput, per);
    fflush(stdout);

    ESP_LOGI(TAG, "%s: recv=%lu/%d elapsed=%lums tput=%.1fkbps",
             cfg->name, (unsigned long)received, PKT_COUNT,
             (unsigned long)elapsed, tput);
}

extern "C" void app_main() {
    ESP_LOGI(TAG, "=== Phase C Optimizer (fixed 255B, no GODMODE) ===");
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
    printf("  Phase C Optimizer (all fixed 255B mode)\n");
    printf("  FLRC 2600 kbps @ 868 MHz, +22 dBm\n");
    printf("  5 configs × %d pkts of %d bytes\n", PKT_COUNT, PKT_SIZE);
    printf("=================================================\n");
    printf("\n");
    printf("config,pkt_size,rx_received,rx_errors,elapsed_ms,throughput_kbps,per_pct\n");
    fflush(stdout);

    int16_t state = radio->beginFLRC(868.0f, 2600, RADIOLIB_LR2021_FLRC_CR_1_0, 22,
                                     16, RADIOLIB_SHAPING_0_5, 0.0f);
    if (state != RADIOLIB_ERR_NONE) {
        ESP_LOGE(TAG, "Radio init failed: %d", state);
        blink(10, 500, 500);
        return;
    }
    radio->fixedPacketLengthMode(255);
    radio->setPacketReceivedAction(onIrq);
    ESP_LOGI(TAG, "Radio initialized OK (fixed 255B)");

    for (int c = 0; c < configCount; c++) {
        ESP_LOGI(TAG, "=== Config %d/%d: %s ===", c+1, configCount, configs[c].name);
        blink(1, 100, 100);
        vTaskDelay(pdMS_TO_TICKS(2000));
        runConfig(&configs[c]);
        vTaskDelay(pdMS_TO_TICKS(1000));
    }

    printf("\n");
    printf("=================================================\n");
    printf("  PHASE C COMPLETE\n");
    printf("=================================================\n");
    fflush(stdout);

    blink(5, 200, 200);
    while (true) {
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}

#endif
