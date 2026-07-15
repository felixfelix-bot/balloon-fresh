/*
 * bootsel_ctrl.cpp — Minimal auto-BOOTSEL trigger (no USB serial JTAG)
 * On boot: immediately force RP2040 into BOOTSEL mode, then idle.
 */
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"

#define PIN_RESET   GPIO_NUM_1
#define PIN_BOOTSEL GPIO_NUM_8

extern "C" void app_main() {
    // Config both pins as push-pull output
    gpio_config_t io = {};
    io.pin_bit_mask = (1ULL << PIN_RESET) | (1ULL << PIN_BOOTSEL);
    io.mode = GPIO_MODE_OUTPUT;
    gpio_config(&io);

    // Start: both HIGH (RP2040 running normally)
    gpio_set_level(PIN_RESET, 1);
    gpio_set_level(PIN_BOOTSEL, 1);
    vTaskDelay(pdMS_TO_TICKS(100));

    // 1. Hold BOOTSEL LOW
    gpio_set_level(PIN_BOOTSEL, 0);
    vTaskDelay(pdMS_TO_TICKS(50));

    // 2. Pulse RESET LOW (100ms for safety margin)
    gpio_set_level(PIN_RESET, 0);
    vTaskDelay(pdMS_TO_TICKS(100));
    gpio_set_level(PIN_RESET, 1);

    // 3. Wait for RP2040 to detect BOOTSEL + enumerate as mass storage
    vTaskDelay(pdMS_TO_TICKS(500));

    // 4. Release BOOTSEL
    gpio_set_level(PIN_BOOTSEL, 1);

    // Idle: blink LED forever as confirmation firmware is running
    while (1) {
        gpio_set_level(PIN_BOOTSEL, 0);
        vTaskDelay(pdMS_TO_TICKS(100));
        gpio_set_level(PIN_BOOTSEL, 1);
        vTaskDelay(pdMS_TO_TICKS(900));
    }
}
