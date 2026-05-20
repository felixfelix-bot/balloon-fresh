#include <stdio.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_pm.h"
#include "driver/gpio.h"
#include "driver/spi_master.h"
#include "driver/adc.h"

#include "lr2021.h"
#include "bmp280.h"
#include "power_manager.h"
#include "telemetry.h"
#include "antenna_switch.h"

static const char *TAG = "MAIN";

#define LED_GPIO 10

static void init_spi(void)
{
    spi_bus_config_t bus_cfg = {
        .mosi_io_num = 7,
        .miso_io_num = 2,
        .sclk_io_num = 6,
        .quadwp_io_num = -1,
        .quadhd_io_num = -1,
        .max_transfer_sz = 256,
    };
    ESP_ERROR_CHECK(spi_bus_initialize(SPI2_HOST, &bus_cfg, SPI_DMA_CH_AUTO));
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
        gpio_set_level(LED_GPIO, 1);
        vTaskDelay(pdMS_TO_TICKS(100));
        gpio_set_level(LED_GPIO, 0);
        vTaskDelay(pdMS_TO_TICKS(100));
    }
}

void app_main(void)
{
    ESP_LOGI(TAG, "Pico Balloon Tracker v0.1 starting...");

    esp_pm_config_t pm_config = {
        .max_freq_mhz = 80,
        .min_freq_mhz = 10,
        .light_sleep_enable = true,
    };
    ESP_ERROR_CHECK(esp_pm_configure(&pm_config));

    blink_led(3);
    init_spi();

    ESP_LOGI(TAG, "Initializing LR2021...");
    lr2021_t lr2021 = {0};
    lr2021_init(&lr2021, SPI2_HOST, 10, 3, 4, 5);
    lr2021_reset(&lr2021);

    ESP_LOGI(TAG, "Initializing BMP280...");
    bmp280_t bmp = {0};
    bmp280_init(&bmp, I2C_NUM_0, 8, 9, 400000);

    ESP_LOGI(TAG, "Initializing antenna switch...");
    antenna_switch_init(21, 20);

    telemetry_packet_t pkt = {0};
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

        for (int ant = 0; ant < 4; ant++) {
            antenna_switch_select(ant);
            vTaskDelay(pdMS_TO_TICKS(10));

            telemetry_tx(&lr2021, &pkt);
            ESP_LOGI(TAG, "TX on antenna %d complete", ant);
        }

        cycle++;
        ESP_LOGI(TAG, "Entering deep sleep...");
        vTaskDelay(pdMS_TO_TICKS(60000));
    }
}
