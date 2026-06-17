#include <sdkconfig.h>

#ifdef CONFIG_BENCH_MODE_DUMP

#include <stdio.h>
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "nvs_results.h"

static const char *TAG = "DUMP";

#define LED_GPIO 8

static void blink(int times, int ms) {
    gpio_config_t io = {};
    io.pin_bit_mask = (1ULL << LED_GPIO);
    io.mode = GPIO_MODE_OUTPUT;
    gpio_config(&io);
    for (int i = 0; i < times; i++) {
        gpio_set_level((gpio_num_t)LED_GPIO, 0);
        vTaskDelay(pdMS_TO_TICKS(ms));
        gpio_set_level((gpio_num_t)LED_GPIO, 1);
        vTaskDelay(pdMS_TO_TICKS(ms));
    }
    gpio_set_level((gpio_num_t)LED_GPIO, 1);
}

extern "C" void app_main() {
    ESP_LOGI(TAG, "=== NVS Dump Mode ===");
    setvbuf(stdout, NULL, _IONBF, 0);

    blink(5, 200);
    vTaskDelay(pdMS_TO_TICKS(1000));

    if (nvs_init() != 0) {
        ESP_LOGE(TAG, "NVS init failed");
        blink(10, 500);
        return;
    }

    uint8_t count = 0;
    nvs_get_count(&count);

    if (count == 0) {
        printf("NO_DATA\n");
        ESP_LOGI(TAG, "No results in NVS");
        blink(3, 1000);
        return;
    }

    ESP_LOGI(TAG, "Dumping %d results...", count);
    nvs_print_all_results();
    ESP_LOGI(TAG, "Dump complete");

    blink(5, 200);
    vTaskDelay(pdMS_TO_TICKS(2000));

    while (true) {
        blink(1, 2000);
        vTaskDelay(pdMS_TO_TICKS(5000));
    }
}

#endif
