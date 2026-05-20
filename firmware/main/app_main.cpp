#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_pm.h"
#include "driver/gpio.h"

#include <RadioLib.h>
#include "EspHalC3.h"

extern "C" {
#include "bmp280.h"
#include "power_manager.h"
#include "telemetry.h"
#include "antenna_switch.h"
}

static const char *TAG = "MAIN";

#define LED_GPIO 10

#define LR2021_SCK   6
#define LR2021_MISO  2
#define LR2021_MOSI  7
#define LR2021_NSS   10
#define LR2021_BUSY  4
#define LR2021_RST   3
#define LR2021_DIO9  5

static EspHalC3* hal = nullptr;
static LR2021* radio = nullptr;

static bool flag_tx_done = false;

static void on_tx_done(void) {
    flag_tx_done = true;
}

static void blink_led(int times)
{
    gpio_config_t io_conf = {
        .pin_bit_mask = (1ULL << LED_GPIO),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&io_conf);

    for (int i = 0; i < times; i++) {
        gpio_set_level((gpio_num_t)LED_GPIO, 1);
        vTaskDelay(pdMS_TO_TICKS(100));
        gpio_set_level((gpio_num_t)LED_GPIO, 0);
        vTaskDelay(pdMS_TO_TICKS(100));
    }
}

extern "C" void app_main(void)
{
    ESP_LOGI(TAG, "Pico Balloon Tracker v0.1 starting...");

    esp_pm_config_t pm_config = {
        .max_freq_mhz = 80,
        .min_freq_mhz = 10,
        .light_sleep_enable = true,
    };
    ESP_ERROR_CHECK(esp_pm_configure(&pm_config));

    blink_led(3);

    hal = new EspHalC3(LR2021_SCK, LR2021_MISO, LR2021_MOSI);

    radio = new LR2021(new Module(hal, LR2021_NSS, LR2021_DIO9, LR2021_RST, LR2021_BUSY));
    radio->irqDioNum = 9;

    ESP_LOGI(TAG, "Initializing LR2021 (RadioLib)...");
    int16_t state = radio->begin(868.0, 125.0, 9, 7, 0x12, 22, 8, 1.6);
    if (state != RADIOLIB_ERR_NONE) {
        ESP_LOGE(TAG, "LR2021 init failed: %d", state);
        while (true) { hal->delay(1000); }
    }
    ESP_LOGI(TAG, "LR2021 initialized OK");

    radio->setPacketSentAction(on_tx_done);

    ESP_LOGI(TAG, "Initializing BMP280...");
    bmp280_t bmp;
    memset(&bmp, 0, sizeof(bmp));
    bmp280_init(&bmp, I2C_NUM_0, 8, 9, 400000);

    ESP_LOGI(TAG, "Initializing power manager...");
    power_manager_init();

    telemetry_packet_t pkt;
    memset(&pkt, 0, sizeof(pkt));
    pkt.callsign_hash = 0x424C4E;

    int cycle = 0;
    while (1) {
        ESP_LOGI(TAG, "--- Cycle %d ---", cycle);

        float temp = 0, pressure = 0, altitude = 0;
        bmp280_read(&bmp, &temp, &pressure, &altitude);
        ESP_LOGI(TAG, "BMP280: %.1f C, %.1f hPa, %.0f m", temp, pressure, altitude);

        uint16_t cap_mv = power_manager_read_supercap_mv();
        ESP_LOGI(TAG, "Supercap: %d mV", cap_mv);

        telemetry_fill(&pkt, temp, pressure, altitude, cap_mv, cycle);

        uint8_t buf[TELEMETRY_SIZE];
        telemetry_serialize(&pkt, buf);

        ESP_LOGI(TAG, "TX %d bytes on 868 MHz...", TELEMETRY_SIZE);
        flag_tx_done = false;
        state = radio->startTransmit(buf, TELEMETRY_SIZE);
        if (state != RADIOLIB_ERR_NONE) {
            ESP_LOGE(TAG, "startTransmit failed: %d", state);
        } else {
            uint32_t timeout = 0;
            while (!flag_tx_done && timeout < 10000) {
                hal->delay(1);
                timeout++;
            }
            if (flag_tx_done) {
                ESP_LOGI(TAG, "TX complete");
            } else {
                ESP_LOGW(TAG, "TX timeout");
            }
        }

        radio->standby();

        cycle++;
        ESP_LOGI(TAG, "Sleeping 60s...");
        vTaskDelay(pdMS_TO_TICKS(60000));
    }
}
