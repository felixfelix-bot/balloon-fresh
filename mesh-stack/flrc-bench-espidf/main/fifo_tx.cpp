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

struct TxBurst {
    const char *name;
    uint8_t pktSize;
    uint8_t pktCount;
};

static const TxBurst bursts[] = {
    {"20B",   20,  10},
    {"50B",   50,   5},
    {"100B", 100,   3},
    {"255B", 255,   1},
    {"20Bx100",  20, 100},
    {"50Bx100",  50, 100},
    {"100Bx100",100, 100},
    {"255Bx100",255, 100},
};
static const int burstCount = sizeof(bursts) / sizeof(bursts[0]);

extern "C" void app_main() {
    ESP_LOGI(TAG, "=== LR2021 FIFO TX Burst ===");
    setvbuf(stdout, NULL, _IONBF, 0);
    blink(3, 200, 200);
    vTaskDelay(pdMS_TO_TICKS(5000));

    EspHalC3 hal(LR2021_SCK, LR2021_MISO, LR2021_MOSI);
    hal.setCsPin(LR2021_NSS);
    hal.setBusyPin(LR2021_BUSY);
    Module mod(&hal, LR2021_NSS, LR2021_DIO9, LR2021_RST, LR2021_BUSY);
    LR2021 radio(&mod);
    radio.irqDioNum = 9;

    int16_t state = radio.beginFLRC(2450.0f, 2600, 0x02, 12,
                                    16, RADIOLIB_SHAPING_0_5, 0.0f);
    if (state != RADIOLIB_ERR_NONE) {
        ESP_LOGE(TAG, "Radio init failed: %d", state);
        blink(10, 500, 500);
        return;
    }
    radio.fixedPacketLengthMode(255);
    ESP_LOGI(TAG, "Radio initialized OK");

    printf("\n");
    printf("=================================================\n");
    printf("  LR2021 FIFO TX Burst Transmitter\n");
    printf("  Mode: FLRC 2600 kbps @ 2450 MHz, +12 dBm\n");
    printf("  Sends bursts to match RX FIFO test phases\n");
    printf("=================================================\n");
    printf("\n");
    printf("burst_name,pkt_size,pkt_count,sent,elapsed_ms,tx_throughput_kbps\n");
    fflush(stdout);

    uint8_t buf[255];

    for (int b = 0; b < burstCount; b++) {
        const TxBurst *tc = &bursts[b];
        ESP_LOGI(TAG, "Burst %d/%d: %s (%d pkts x %d bytes, NO delay)",
                 b+1, burstCount, tc->name, tc->pktCount, tc->pktSize);

        blink(1, 100, 100);
        vTaskDelay(pdMS_TO_TICKS(2000));

        for (int i = 0; i < tc->pktSize; i++) {
            buf[i] = (uint8_t)(i ^ 0x55);
        }
        buf[0] = 0; buf[1] = 0; buf[2] = 0; buf[3] = 0;

        uint16_t sent = 0;
        uint32_t startMs = (uint32_t)(esp_timer_get_time() / 1000ULL);

        for (int p = 0; p < tc->pktCount; p++) {
            buf[0] = (p >> 24) & 0xFF;
            buf[1] = (p >> 16) & 0xFF;
            buf[2] = (p >> 8) & 0xFF;
            buf[3] = p & 0xFF;

            if (tc->pktSize > 4) {
                prbs15_fill(buf + 4, tc->pktSize - 4, p);
            }

            state = radio.transmit(buf, tc->pktSize);
            if (state == RADIOLIB_ERR_NONE) sent++;
        }

        uint32_t elapsed = (uint32_t)(esp_timer_get_time() / 1000ULL) - startMs;
        float tput = (elapsed > 0 && sent > 0)
            ? (float)sent * tc->pktSize * 8.0f / elapsed : 0;

        printf("%s,%d,%d,%d,%lu,%.1f\n",
               tc->name, tc->pktSize, tc->pktCount,
               sent, (unsigned long)elapsed, tput);
        fflush(stdout);

        ESP_LOGI(TAG, "%s: sent=%d/%d elapsed=%lums tput=%.1fkbps",
                 tc->name, sent, tc->pktCount,
                 (unsigned long)elapsed, tput);

        vTaskDelay(pdMS_TO_TICKS(3000));
    }

    printf("\n=== TX BURST COMPLETE ===\n");
    printf("Looping again in 10s...\n\n");
    fflush(stdout);

    blink(5, 200, 200);
    vTaskDelay(pdMS_TO_TICKS(10000));
}

#endif
