#include <sdkconfig.h>

#ifdef CONFIG_BENCH_MODE_FIFO_TX

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

static const char *TAG = "FIFOTX";

#define LED_GPIO 8
#define LR2021_SCK   6
#define LR2021_MISO  2
#define LR2021_MOSI  7
#define LR2021_NSS   10
#define LR2021_BUSY  4
#define LR2021_RST   3
#define LR2021_DIO9  5

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

struct BandConfig {
    float freq;
    int8_t power;
    const char *name;
};

static const BandConfig bands[] = {
    {868.0f,  22, "868"},
    {2450.0f, 12, "2450"},
};
static const int bandCount = sizeof(bands) / sizeof(bands[0]);

static EspHalC3 *hal = nullptr;
static Module *mod = nullptr;
static LR2021 *radio = nullptr;

static void initRadio(float freq, int8_t power) {
    radio->standby();
    int16_t state = radio->beginFLRC(freq, 2600, RADIOLIB_LR2021_FLRC_CR_1_0, power,
                                     16, RADIOLIB_SHAPING_0_5, 0.0f);
    if (state != RADIOLIB_ERR_NONE) {
        ESP_LOGE(TAG, "Radio init failed at %.0f MHz: %d", freq, state);
        return;
    }
    radio->fixedPacketLengthMode(255);
    ESP_LOGI(TAG, "Radio initialized at %.0f MHz, +%d dBm", freq, power);
}

extern "C" void app_main() {
    ESP_LOGI(TAG, "=== Dual-Band TX (868 + 2450 MHz) ===");
    setvbuf(stdout, NULL, _IONBF, 0);
    blink(3, 200, 200);
    vTaskDelay(pdMS_TO_TICKS(5000));

    nvs_init();
    nvs_clear_all();
    uint8_t nvsCount = 0;
    ESP_LOGI(TAG, "NVS initialized");

    hal = new EspHalC3(LR2021_SCK, LR2021_MISO, LR2021_MOSI);
    hal->setCsPin(LR2021_NSS);
    hal->setBusyPin(LR2021_BUSY);
    mod = new Module(hal, LR2021_NSS, LR2021_DIO9, LR2021_RST, LR2021_BUSY);
    radio = new LR2021(mod);
    radio->irqDioNum = 9;

    printf("\n");
    printf("=================================================\n");
    printf("  Dual-Band TX (868 + 2450 MHz)\n");
    printf("  FLRC 2600 kbps, 255B fixed, alternating bands\n");
    printf("  Runs from power bank, NVS logging\n");
    printf("=================================================\n");
    printf("\n");
    printf("loop,band,pkt_count,sent,elapsed_ms,tx_throughput_kbps\n");
    fflush(stdout);

    uint8_t buf[255];
    uint32_t loopCount = 0;

    while (true) {
        loopCount++;
        ESP_LOGI(TAG, "====== Loop %lu ======", (unsigned long)loopCount);

        for (int bi = 0; bi < bandCount; bi++) {
            const BandConfig *bc = &bands[bi];
            blink(1, 50, 50);

            initRadio(bc->freq, bc->power);
            vTaskDelay(pdMS_TO_TICKS(500));

            int pktCount = 100;
            memset(buf, 0, sizeof(buf));
            uint16_t sent = 0;
            uint32_t startMs = (uint32_t)(esp_timer_get_time() / 1000ULL);

            for (int p = 0; p < pktCount; p++) {
                buf[0] = (p >> 24) & 0xFF;
                buf[1] = (p >> 16) & 0xFF;
                buf[2] = (p >> 8) & 0xFF;
                buf[3] = p & 0xFF;
                prbs15_fill(buf + 4, 251, p);

                int16_t state = radio->transmit(buf, 255);
                if (state == RADIOLIB_ERR_NONE) sent++;
            }

            uint32_t elapsed = (uint32_t)(esp_timer_get_time() / 1000ULL) - startMs;
            float tput = (elapsed > 0 && sent > 0)
                ? (float)sent * 255 * 8.0f / elapsed : 0;

            printf("%lu,%s,%d,%d,%lu,%.1f\n",
                   (unsigned long)loopCount, bc->name, pktCount,
                   sent, (unsigned long)elapsed, tput);
            fflush(stdout);

            ESP_LOGI(TAG, "%s: sent=%d/%d elapsed=%lums tput=%.1fkbps",
                     bc->name, sent, pktCount,
                     (unsigned long)elapsed, tput);

            if (nvsCount < NVS_MAX_RESULTS) {
                NvsTestResult r = {};
                snprintf(r.name, sizeof(r.name), "%s", bc->name);
                r.mode = 0;
                r.freq = bc->freq;
                r.bitrate = 2600;
                r.pkt_size = 255;
                r.tx_sent = sent;
                r.elapsed_ms = elapsed;
                r.throughput_kbps = tput;
                r.role = 0;
                r.loop_count = loopCount;
                nvs_save_result(nvsCount, &r);
                nvsCount++;
                nvs_set_count(nvsCount);
            }

            vTaskDelay(pdMS_TO_TICKS(3000));
        }

        ESP_LOGI(TAG, "=== Loop %lu complete, next in 5s ===", (unsigned long)loopCount);
        blink(3, 200, 200);
        vTaskDelay(pdMS_TO_TICKS(5000));
    }
}

#endif
