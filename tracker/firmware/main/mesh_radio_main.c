/*
 * mesh_radio_main.c — Test app: LR2021 radio + mesh_adapter integration
 *
 * Initializes the lr2021_radio component (raw SPI, no RadioLib) and
 * connects it to mesh_adapter for fragmented, erasure-coded mesh transport.
 *
 * Flow:
 *   1. lr2021_radio_init() — SPI bus + LR2021 chip (FLRC 2.4 GHz)
 *   2. lr2021_radio_start_rx() — enter continuous RX
 *   3. mesh_adapter_init() — with lr2021_radio_tx as send_fn
 *   4. Main loop:
 *      - lr2021_radio_poll() — non-blocking RX check
 *      - Every 5s: mesh_adapter_send("Hello from mesh node N")
 *
 * On received frame: feed to mesh_adapter_receive_frame → print decoded
 *
 * Build: source ~/esp/esp-idf/export.sh
 *        cd tracker/firmware && idf.py build
 *        (requires CONFIG_ENABLE_MESH=y + CONFIG_ENABLE_MESH_RADIO=y)
 *
 * Flash: idf.py -p /dev/ttyACM0 flash monitor
 *
 * SPDX-License-Identifier: MIT
 */

#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_timer.h"

#include "lr2021_radio.h"
#include "mesh_adapter.h"

static const char *TAG = "MESH_RADIO";

/* ── Mesh state ───────────────────────────────────────────────────────── */
static mesh_frame_queue_t s_tx_queue;
static uint8_t             s_rx_out[512];
static uint16_t            s_rx_out_len;

/* TX message counter */
static uint32_t s_tx_counter = 0;

/* ── RX callback — invoked by lr2021_radio_poll() on each frame ───────── */
static void on_radio_rx(const uint8_t *frame, uint16_t len, int8_t rssi)
{
    ESP_LOGI(TAG, "RX frame: %u bytes, RSSI=%d dBm", len, rssi);

    /* Feed to mesh_adapter for reassembly + decryption */
    mesh_result_t r = mesh_adapter_receive_frame(frame, len,
                                                  s_rx_out, &s_rx_out_len,
                                                  sizeof(s_rx_out));
    if (r == MESH_OK) {
        /* Reassembly complete — print decoded message */
        ESP_LOGI(TAG, "✓ Message reassembled: %u bytes", s_rx_out_len);
        /* Print as string if printable */
        if (s_rx_out_len > 0 && s_rx_out_len < sizeof(s_rx_out)) {
            s_rx_out[s_rx_out_len] = '\0';
            ESP_LOGI(TAG, "  >> %s", (char *)s_rx_out);
        }
    } else if (r == MESH_ERR_REASSEMBLE_FAILED) {
        /* Normal — more fragments needed before reassembly completes */
        ESP_LOGD(TAG, "Fragment stored, waiting for more...");
    } else {
        ESP_LOGW(TAG, "mesh_adapter_receive_frame error: %d", r);
    }
}

/* ── Periodic TX ──────────────────────────────────────────────────────── */
static void send_test_message(void)
{
    char msg[128];
    int msg_len = snprintf(msg, sizeof(msg),
                           "mesh-ping #%lu from ESP32-C3 @ %lld ms",
                           (unsigned long)s_tx_counter,
                           (long long)(esp_timer_get_time() / 1000));

    s_tx_counter++;

    /* frag_size=64, redundancy=2 (2 extra erasure-coded frames) */
    mesh_result_t r = mesh_adapter_send((const uint8_t *)msg, (uint16_t)msg_len,
                                        64, 2);
    if (r == MESH_OK) {
        ESP_LOGI(TAG, "TX: sent \"%s\" (%d bytes, %d frames queued)",
                 msg, msg_len, s_tx_queue.frame_count);
    } else {
        ESP_LOGE(TAG, "TX: mesh_adapter_send failed: %d", r);
    }
}

/* ── Main ─────────────────────────────────────────────────────────────── */
void app_main(void)
{
    ESP_LOGI(TAG, "========================================");
    ESP_LOGI(TAG, "  LR2021 Mesh Radio — ESP32-C3");
    ESP_LOGI(TAG, "  Raw SPI (no RadioLib) + mesh_adapter");
    ESP_LOGI(TAG, "========================================");

    setvbuf(stdout, NULL, _IONBF, 0);

    /* 1. Initialize LR2021 radio with default ESP32-C3 Mini V1 pins */
    lr2021_radio_pins_t pins = LR2021_PINS_DEFAULT;
    esp_err_t ret = lr2021_radio_init(&pins);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Radio init failed: %s", esp_err_to_name(ret));
        return;
    }
    vTaskDelay(pdMS_TO_TICKS(500));

    /* 2. Register RX callback */
    lr2021_radio_set_rx_callback(on_radio_rx);

    /* 3. Enter continuous RX mode */
    lr2021_radio_start_rx();

    /* 4. Initialize mesh_adapter with radio TX as send_fn */
    memset(&s_tx_queue, 0, sizeof(s_tx_queue));
    mesh_adapter_config_t mesh_cfg = {
        .send_fn     = lr2021_radio_tx,
        .tx_queue    = &s_tx_queue,
        .encrypt_fn  = NULL,   /* No FIPS encryption for test */
        .decrypt_fn  = NULL,
        .encrypt_ctx = NULL,
        .decrypt_ctx = NULL,
    };
    mesh_adapter_init(&mesh_cfg);
    ESP_LOGI(TAG, "Mesh adapter initialized (frag_size=64, redundancy=2)");

    /* 5. Send initial test message */
    send_test_message();

    /* 6. Main loop */
    int64_t last_tx_us = esp_timer_get_time();
    const int64_t tx_interval_us = 5 * 1000 * 1000;  /* 5 seconds */

    ESP_LOGI(TAG, "Entering main loop (poll RX + TX every 5s)");

    while (true) {
        /* Non-blocking RX poll */
        lr2021_radio_poll();

        /* Periodic TX every 5 seconds */
        int64_t now_us = esp_timer_get_time();
        if ((now_us - last_tx_us) >= tx_interval_us) {
            send_test_message();
            last_tx_us = now_us;
        }

        /* Small yield to avoid starving other tasks */
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}
