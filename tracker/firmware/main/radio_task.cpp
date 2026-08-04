/*
 * radio_task.cpp — FreeRTOS task for LR2021 radio RX/TX in relay mode.
 *
 * IRQ-driven RX using DIO9 (GPIO5). TX from tx_queue (priority over RX).
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
#include "EspHalLr2021Radio.h"
#include "Lr2021Transport.h"

static const char *TAG = "RADIO_TASK";

/* Global queues — created by app_main, used by both tasks */
QueueHandle_t g_rx_queue = NULL;
QueueHandle_t g_tx_queue = NULL;

/* Radio handles — set by app_main before task creation */
extern EspHalLr2021Radio* s_radio;
extern Lr2021Transport*   s_transport;

/* IRQ flag for DIO9 (RX_DONE) */
static volatile bool g_rx_irq_flag = false;

#define LR2021_DIO9_PIN 5

static void IRAM_ATTR dio9_irq_handler(void *arg)
{
    (void)arg;
    g_rx_irq_flag = true;
}

static void setup_dio9_interrupt(void)
{
    gpio_config_t io_conf = {};
    io_conf.pin_bit_mask = (1ULL << LR2021_DIO9_PIN);
    io_conf.mode = GPIO_MODE_INPUT;
    io_conf.pull_up_en = GPIO_PULLUP_ENABLE;
    io_conf.pull_down_en = GPIO_PULLDOWN_DISABLE;
    io_conf.intr_type = GPIO_INTR_POSEDGE;  /* DIO9 rising edge = RX_DONE */
    gpio_config(&io_conf);

    gpio_install_isr_service(0);
    gpio_isr_handler_add(LR2021_DIO9_PIN, dio9_irq_handler, NULL);

    ESP_LOGI(TAG, "DIO9 IRQ configured on GPIO%d", LR2021_DIO9_PIN);
}

void radio_task(void *arg)
{
    (void)arg;
    ESP_LOGI(TAG, "radio_task started (stack=%u bytes)", uxTaskGetStackHighWaterMark(NULL) * sizeof(StackType_t));

    /* Configure DIO9 interrupt */
    setup_dio9_interrupt();

    relay_packet_t tx_pkt;
    relay_packet_t rx_pkt;
    bool in_rx_mode = false;

    while (1) {
        /* Priority 1: TX anything in the queue */
        if (xQueueReceive(g_tx_queue, &tx_pkt, 0) == pdTRUE) {
            if (s_transport) {
                in_rx_mode = false;
                ESP_LOGD(TAG, "TX %u bytes", tx_pkt.len);
                s_transport->send_packet(tx_pkt.data, tx_pkt.len);
            }
            continue;  /* Check tx_queue again before entering RX */
        }

        /* Priority 2: Enter RX mode if not already */
        if (!in_rx_mode) {
            if (s_radio) {
                s_radio->set_rx_mode();
                in_rx_mode = true;
                g_rx_irq_flag = false;
            }
        }

        /* Wait for DIO9 IRQ or timeout (100ms → re-check tx_queue) */
        if (g_rx_irq_flag) {
            g_rx_irq_flag = false;
            in_rx_mode = false;  /* IRQ fired, need to re-enter RX after read */

            if (s_transport) {
                int len = s_transport->read_packet(rx_pkt.data, RELAY_PACKET_MAX_SIZE);
                if (len > 0) {
                    rx_pkt.len = len;
                    rx_pkt.timestamp = (uint32_t)(xTaskGetTickCount() * portTICK_PERIOD_MS);
                    rx_pkt.rssi = s_radio->get_rssi();

                    /* Push to app_task queue. If full, drop (backpressure). */
                    if (xQueueSend(g_rx_queue, &rx_pkt, 0) != pdTRUE) {
                        ESP_LOGW(TAG, "RX queue full, dropping %d bytes", len);
                    } else {
                        ESP_LOGD(TAG, "RX %d bytes, RSSI=%d", len, rx_pkt.rssi);
                    }
                }
            }
        }

        vTaskDelay(pdMS_TO_TICKS(10));  /* Yield to other tasks */
    }
}
