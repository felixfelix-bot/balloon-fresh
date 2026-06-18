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

extern "C" void app_main() {
    ESP_LOGI(TAG, "=== Simple RX Test (no GODMODE) ===");
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
    printf("  Simple RX Test (868 MHz, no GODMODE)\n");
    printf("  Mode: FLRC 2600 kbps @ 868 MHz, +22 dBm\n");
    printf("  Fixed 255B packets, NO PRBS, NO RSSI\n");
    printf("=================================================\n");
    printf("\n");
    printf("pkt_num,elapsed_ms,rssi,len,state\n");
    fflush(stdout);

    int16_t state = radio->beginFLRC(868.0f, 2600, RADIOLIB_LR2021_FLRC_CR_1_0, 22,
                                     16, RADIOLIB_SHAPING_0_5, 0.0f);
    if (state != RADIOLIB_ERR_NONE) {
        ESP_LOGE(TAG, "Radio init failed: %d", state);
        blink(10, 500, 500);
        return;
    }
    ESP_LOGI(TAG, "Radio initialized OK");

    radio->fixedPacketLengthMode(255);
    radio->setPacketReceivedAction(onIrq);
    radio->startReceive();
    irqFlag = false;

    uint8_t buf[256];
    uint32_t received = 0;
    uint32_t startMs = (uint32_t)(esp_timer_get_time() / 1000ULL);

    ESP_LOGI(TAG, "Listening for packets (30s timeout)...");

    while (received < 100 &&
           (uint32_t)(esp_timer_get_time() / 1000ULL) - startMs < 30000) {
        if (!irqFlag) {
            vTaskDelay(pdMS_TO_TICKS(1));
            continue;
        }
        irqFlag = false;

        int16_t len = radio->getPacketLength();
        ESP_LOGI(TAG, "IRQ fired! len=%d", len);

        if (len <= 0) {
            radio->standby();
            radio->startReceive();
            continue;
        }

        state = radio->readData(buf, len);
        float rssi = radio->getRSSI(false);
        radio->standby();
        radio->startReceive();

        uint32_t elapsed = (uint32_t)(esp_timer_get_time() / 1000ULL) - startMs;

        if (state == RADIOLIB_ERR_NONE) {
            received++;
            printf("%lu,%lu,%.0f,%d,OK\n",
                   (unsigned long)received, (unsigned long)elapsed, rssi, len);
            fflush(stdout);
            ESP_LOGI(TAG, "PKT %lu: len=%d RSSI=%.0f elapsed=%lums",
                     (unsigned long)received, len, rssi, (unsigned long)elapsed);
        } else {
            printf("ERR,%lu,,,,%d\n", (unsigned long)elapsed, state);
            fflush(stdout);
            ESP_LOGW(TAG, "readData error: %d", state);
        }
    }

    uint32_t elapsed = (uint32_t)(esp_timer_get_time() / 1000ULL) - startMs;
    float tput = (elapsed > 0 && received > 0)
        ? (float)received * 255 * 8.0f / elapsed : 0;

    printf("\n");
    printf("=================================================\n");
    printf("  RESULTS: %lu packets in %lums = %.1f kbps\n",
           (unsigned long)received, (unsigned long)elapsed, tput);
    printf("=================================================\n");
    fflush(stdout);

    blink(5, 200, 200);
    while (true) {
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}

#endif
