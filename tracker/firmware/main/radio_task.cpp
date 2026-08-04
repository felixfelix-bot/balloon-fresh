/*
 * radio_task.cpp — FreeRTOS task for LR2021 radio RX/TX in relay mode.
 *
 * Uses transport layer: send() for TX, recv() for RX, handle_irq() for DIO.
 * Half-duplex: can't TX and RX simultaneously. Packets lost during TX are
 * acceptable — the mesh layer handles lossy links.
 *
 * Architecture: see docs/coordination/ARCHITECTURE-FREERTOS-TASKS.md
 */

#include <stdio.h>
#include <string.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "esp_log.h"
#include "driver/gpio.h"

#include "relay_types.h"
#include "esp_idf_lr2021_radio.h"
#include "lr2021_transport.h"

static const char *TAG = "RADIO_TASK";

/* Global queues — created by app_main, used by both tasks */
QueueHandle_t g_rx_queue = NULL;
QueueHandle_t g_tx_queue = NULL;

/* Radio handles — set by app_main before task creation */
extern EspHalLr2021Radio* s_radio;
extern Lr2021Transport*   s_transport;

#define LR2021_DIO9_PIN 5

extern "C" void radio_task(void *arg)
{
    (void)arg;
    ESP_LOGI(TAG, "radio_task started");

    relay_packet_t tx_pkt;
    relay_packet_t rx_pkt;
    UBaseType_t watermark_start = uxTaskGetStackHighWaterMark(NULL);

    while (1) {
        /* Priority 1: TX anything in the queue */
        if (xQueueReceive(g_tx_queue, &tx_pkt, 0) == pdTRUE) {
            if (s_transport) {
                ESP_LOGD(TAG, "TX %u bytes", tx_pkt.len);
                s_transport->send(tx_pkt.data, tx_pkt.len);
                s_transport->flush_tx();
            }
            continue;  /* Check tx_queue again before RX */
        }

        /* Priority 2: RX — poll for incoming data */
        if (s_transport) {
            size_t n_out = 0;
            TransportError err =
                s_transport->recv(rx_pkt.data, RELAY_PACKET_MAX_SIZE, &n_out);

            if (err == TransportError::Ok && n_out > 0) {
                rx_pkt.len = n_out;
                rx_pkt.timestamp = (uint32_t)(xTaskGetTickCount() * portTICK_PERIOD_MS);
                rx_pkt.rssi = 0;  /* TODO: get RSSI from radio */

                if (xQueueSend(g_rx_queue, &rx_pkt, 0) != pdTRUE) {
                    ESP_LOGW(TAG, "RX queue full, dropping %d bytes", (int)n_out);
                } else {
                    ESP_LOGD(TAG, "RX %d bytes", (int)n_out);
                }
            }
        }

        vTaskDelay(pdMS_TO_TICKS(10));  /* Yield to other tasks */
    }

    (void)watermark_start;
}
