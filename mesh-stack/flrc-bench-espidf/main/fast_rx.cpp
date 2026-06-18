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
#define IRQ_GPIO 5
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

extern "C" void app_main() {
    ESP_LOGI(TAG, "=== Polled RX (no ISR, direct GPIO poll) ===");
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
    printf("  Polled RX (no ISR, direct GPIO poll)\n");
    printf("  FLRC 2600 kbps @ 868 MHz, +22 dBm\n");
    printf("  Fixed 255B, no PRBS, no RSSI, busy-wait\n");
    printf("=================================================\n");
    printf("\n");
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
    radio->startReceive();
    ESP_LOGI(TAG, "Radio initialized OK (ISR + busy-wait on flag)");

    uint8_t buf[PKT_SIZE + 4];
    uint32_t received = 0;
    uint32_t errors = 0;
    uint32_t startMs = (uint32_t)(esp_timer_get_time() / 1000ULL);

    ESP_LOGI(TAG, "Listening (ISR + busy-wait, no yield)...");

    while (received < PKT_COUNT &&
           (uint32_t)(esp_timer_get_time() / 1000ULL) - startMs < TEST_TIMEOUT_MS) {

        while (!irqFlag) {
            taskYIELD();
            if ((uint32_t)(esp_timer_get_time() / 1000ULL) - startMs >= TEST_TIMEOUT_MS) {
                goto done;
            }
        }
        irqFlag = false;

        state = radio->readData(buf, PKT_SIZE);
        radio->startReceive();

        if (state == RADIOLIB_ERR_NONE) {
            received++;
        } else {
            errors++;
        }
    }

done:
    uint32_t elapsed = (uint32_t)(esp_timer_get_time() / 1000ULL) - startMs;
    float tput = (elapsed > 0 && received > 0)
        ? (float)received * PKT_SIZE * 8.0f / elapsed : 0;
    float per = (PKT_COUNT - received) * 100.0f / PKT_COUNT;

    printf("\n");
    printf("=================================================\n");
    printf("  RESULT: %lu/%d packets in %lums = %.1f kbps\n",
           (unsigned long)received, PKT_COUNT,
           (unsigned long)elapsed, tput);
    printf("  PER: %.1f%%  Errors: %lu\n", per, (unsigned long)errors);
    printf("  Per-packet: %.1fms\n", elapsed / (float)(received > 0 ? received : 1));
    printf("=================================================\n");
    printf("\n");
    printf("pkt_size,rx_received,rx_errors,elapsed_ms,throughput_kbps,per_pct,ms_per_pkt\n");
    printf("%d,%lu,%lu,%lu,%.1f,%.1f,%.1f\n",
           PKT_SIZE, (unsigned long)received, (unsigned long)errors,
           (unsigned long)elapsed, tput, per,
           elapsed / (float)(received > 0 ? received : 1));
    fflush(stdout);

    blink(received > 0 ? 5 : 10, 200, 200);
    while (true) {
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}

#endif
