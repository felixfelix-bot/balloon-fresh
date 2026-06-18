#define RADIOLIB_GODMODE 1

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
#include "nvs_results.h"

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
#define TEST_TIMEOUT_MS 30000

struct OptConfig {
    const char *name;
    bool skipPrbs;
    bool skipRssi;
    bool fixedLength;
    bool inlineSpi;
    bool useTaskYield;
};

static const OptConfig configs[] = {
    {"C1_baseline",     true,  true,  false, false, false},
    {"C2_noPrbs",       false, true,  false, false, false},
    {"C3_noPrbs_noRssi",false, false, false, false, false},
    {"C4_fixed255",     false, false, true,  false, false},
    {"C5_inlineSpi",    false, false, true,  true,  false},
    {"C6_taskYield",    false, false, true,  true,  true },
};
static const int configCount = sizeof(configs) / sizeof(configs[0]);

static uint32_t runOptimizedTest(const OptConfig *cfg) {
    uint8_t buf[PKT_SIZE + 4];
    uint32_t received = 0;
    uint32_t errors = 0;
    uint32_t bitErrors = 0;
    uint32_t bitsChecked = 0;

    if (cfg->fixedLength) {
        radio->fixedPacketLengthMode(PKT_SIZE);
    } else {
        radio->variablePacketLengthMode(PKT_SIZE);
    }

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

        int16_t len;
        if (cfg->fixedLength) {
            len = PKT_SIZE;
        } else {
            len = radio->getPacketLength();
            if (len <= 0) {
                radio->standby();
                radio->startReceive();
                continue;
            }
        }

        int16_t state = radio->readData(buf, len);

        if (!cfg->inlineSpi) {
            radio->standby();
            radio->startReceive();
        } else {
            radio->standby();
            radio->setRx(RADIOLIB_LR2021_RX_TIMEOUT_INF);
        }

        if (state == RADIOLIB_ERR_NONE) {
            received++;

            if (!cfg->skipRssi) {
                radio->getRSSI(false);
            }

            if (!cfg->skipPrbs && len >= 4) {
                uint32_t seq = ((uint32_t)buf[0] << 24) | ((uint32_t)buf[1] << 16) |
                               ((uint32_t)buf[2] << 8) | (uint32_t)buf[3];
                uint16_t bytesBad = 0;
                if ((size_t)len > 4) {
                    uint16_t be = prbs15_verify(buf + 4, len - 4, seq, &bytesBad);
                    bitErrors += be;
                    bitsChecked += (len - 4) * 8;
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

    printf("%s,%d,%lu,%lu,%lu,%.1f,%.1f,%lu,%lu\n",
           cfg->name, PKT_SIZE,
           (unsigned long)received, (unsigned long)errors,
           (unsigned long)elapsed, tput, per,
           (unsigned long)bitErrors, (unsigned long)bitsChecked);
    fflush(stdout);

    ESP_LOGI(TAG, "%s: recv=%lu/%d elapsed=%lums tput=%.1fkbps PER=%.1f%%",
             cfg->name, (unsigned long)received, PKT_COUNT,
             (unsigned long)elapsed, tput, per);

    if (received > 0 && nvs_get_count(nullptr) == 0) {
        nvs_init();
    }

    return elapsed;
}

extern "C" void app_main() {
    ESP_LOGI(TAG, "=== Fast RX Pipeline Optimizer ===");
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
    printf("  Fast RX Pipeline Optimizer (Phase C)\n");
    printf("  Mode: FLRC 2600 kbps @ 2450 MHz, +12 dBm\n");
    printf("  6 configs, each tests %d pkts of %d bytes\n", PKT_COUNT, PKT_SIZE);
    printf("  TX should send %dB packets continuously\n", PKT_SIZE);
    printf("=================================================\n");
    printf("\n");
    printf("config,pkt_size,rx_received,rx_errors,elapsed_ms,throughput_kbps,per_pct,bit_errors,bits_checked\n");
    fflush(stdout);

    int16_t state = radio->beginFLRC(2450.0f, 2600, 0x02, 12,
                                     16, RADIOLIB_SHAPING_0_5, 0.0f);
    if (state != RADIOLIB_ERR_NONE) {
        ESP_LOGE(TAG, "Radio init failed: %d", state);
        blink(10, 500, 500);
        return;
    }
    ESP_LOGI(TAG, "Radio initialized OK");
    radio->setPacketReceivedAction(onIrq);

    for (int c = 0; c < configCount; c++) {
        ESP_LOGI(TAG, "=== Config %d/%d: %s ===", c+1, configCount, configs[c].name);
        blink(c + 1, 100, 100);
        vTaskDelay(pdMS_TO_TICKS(3000));
        runOptimizedTest(&configs[c]);
        vTaskDelay(pdMS_TO_TICKS(2000));
    }

    printf("\n");
    printf("=================================================\n");
    printf("  PHASE C COMPLETE\n");
    printf("=================================================\n");
    printf("\n");
    printf("Expected progression:\n");
    printf("  C1 (baseline)     ~80 kbps\n");
    printf("  C2 (no PRBS)      ~150-200 kbps\n");
    printf("  C3 (+no RSSI)     ~200-300 kbps\n");
    printf("  C4 (+fixed 255B)  ~250-400 kbps\n");
    printf("  C5 (+inline SPI)  ~400-800 kbps\n");
    printf("  C6 (+taskYIELD)   ~500-1000+ kbps\n");
    printf("\n");
    fflush(stdout);

    blink(5, 200, 200);
    while (true) {
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}

#endif
