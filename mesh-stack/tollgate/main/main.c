/*
 * main.c — minimal ESP-IDF app_main for tollgate-balloon-test
 *
 * Purpose: prove tollgate_balloon + tollgate_core + nucula + secp256k1
 * link cleanly for ESP32-C3 and measure flash/RAM footprint. This is
 * compile/link verification only — no real network or wallet activity.
 *
 * The real balloon firmware will live in mesh-stack/firmware/ and supply
 * its own app_main. This file exists solely to give idf.py a top-level
 * component to build against.
 */
#include "esp_err.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "tollgate_balloon.h"

static const char *TAG = "main";

/* Dummy nsec (hex) — NOT a real key. Used only so init has a non-NULL arg. */
static const char *STUB_NSEC_HEX =
    "0000000000000000000000000000000000000000000000000000000000000001";

/* Dummy mint URL — unreachable on a fresh board, init still returns ESP_OK. */
static const char *STUB_MINT_URL = "https://mint.example.cash";

void app_main(void)
{
    ESP_LOGI(TAG, "tollgate-balloon-test build verification");

    esp_err_t ret = tollgate_balloon_init(STUB_NSEC_HEX,
                                          STUB_MINT_URL,
                                          /*price_sats=*/21,
                                          /*step_ms=*/60000);
    if (ret != ESP_OK) {
        ESP_LOGW(TAG, "tollgate_balloon_init returned %s (expected on bare C3)",
                 esp_err_to_name(ret));
    } else {
        ESP_LOGI(TAG, "tollgate_balloon_init OK");
    }

    /* Idle — no real work in this skeleton. */
    while (1) {
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}
