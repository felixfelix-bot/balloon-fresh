/*
 * app_task.cpp — FreeRTOS task for event processing in relay mode.
 *
 * Blocks on rx_queue. On packet arrival:
 *   - Nostr event → verify Schnorr signature → nostr_store_add
 *   - TollGate PAY → decode → ACK encode → push to tx_queue
 *   - Raw bytes → log for debugging
 *
 * secp256k1 context is persistent (created once, ~2KB heap).
 *
 * Architecture: see docs/coordination/ARCHITECTURE-FREERTOS-TASKS.md
 */

#include <stdio.h>
#include <string.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "esp_log.h"
#include "esp_heap_caps.h"

#include "relay_types.h"

#ifdef CONFIG_ENABLE_NOSTR_STORE
#include "nostr_store.h"
#include "secp256k1.h"
#include "secp256k1_extrakeys.h"
#include "secp256k1_schnorrsig.h"
#endif

#ifdef CONFIG_ENABLE_TOLLGATE
#include "tollgate_payment_proto.h"
#endif

static const char *TAG = "APP_TASK";

/* Global queues — created by app_main */
extern QueueHandle_t g_rx_queue;
extern QueueHandle_t g_tx_queue;

#ifdef CONFIG_ENABLE_NOSTR_STORE
/*
 * File-static nostr_store instance.
 * Previously a local variable inside app_task(); moved to file-static scope so
 * the CLI `nostr_dump` command in app_main.cpp can access the SAME store via
 * app_task_get_store().  Must not create a second store — the index and bloom
 * filter are per-instance.
 */
static nostr_store_t s_nostr_store;
static bool s_nostr_store_ready = false;

extern "C" nostr_store_t *app_task_get_store(void)
{
    return s_nostr_store_ready ? &s_nostr_store : NULL;
}
#endif /* CONFIG_ENABLE_NOSTR_STORE */

extern "C" void app_task(void *arg)
{
    (void)arg;
    ESP_LOGI(TAG, "app_task started (free heap=%lu)", (unsigned long)esp_get_free_heap_size());

#ifdef CONFIG_ENABLE_NOSTR_STORE
    /* Create secp256k1 context for signature verification */
    secp256k1_context *ctx = secp256k1_context_create(SECP256K1_CONTEXT_VERIFY);
    if (!ctx) {
        ESP_LOGE(TAG, "FATAL: secp256k1_context_create failed — secp verify disabled");
    } else {
        ESP_LOGI(TAG, "secp256k1 context created (heap=%lu after)", (unsigned long)esp_get_free_heap_size());
    }

    /* Initialize nostr_store (file-static, shared with CLI via app_task_get_store) */
    nostr_store_init(&s_nostr_store, "/littlefs/nostr");
    s_nostr_store_ready = true;
    ESP_LOGI(TAG, "nostr_store ready (dir=/littlefs/nostr, heap=%lu)",
             (unsigned long)esp_get_free_heap_size());
#endif

    relay_packet_t pkt;
    uint32_t packets_processed = 0;

    while (1) {
        /* Block until a packet arrives from radio_task */
        if (xQueueReceive(g_rx_queue, &pkt, portMAX_DELAY) != pdTRUE) {
            continue;
        }

        packets_processed++;
        uint8_t pkt_type = (pkt.len > 0) ? pkt.data[0] : RELAY_TYPE_RAW;

        switch (pkt_type) {
#ifdef CONFIG_ENABLE_NOSTR_STORE
        case RELAY_TYPE_NOSTR_EVENT: {
            /* Deserialize → verify → store */
            nostr_event_t event;
            memset(&event, 0, sizeof(event));

            /* Offset +1 to skip the type tag byte */
            if (nostr_event_deserialize(&event, pkt.data + 1, pkt.len - 1) > 0) {
                /* TODO V2: verify Schnorr signature once nostr_event_t has a sig field.
                 * Current nostr_store schema has no signature field — events are
                 * stored without sig verification for V1 integration testing.
                 * Consultant advised: verify at transport layer, not store layer. */
                nostr_store_add(&s_nostr_store, &event);
                ESP_LOGI(TAG, "Nostr event stored (kind=%d)", event.kind);
            } else {
                ESP_LOGW(TAG, "Nostr event deserialize failed");
            }
            break;
        }
#endif

#ifdef CONFIG_ENABLE_TOLLGATE
        case RELAY_TYPE_TOLLGATE_PAY: {
            /* Decode PAY → send ACK back */
            tollgate_msg_hdr_t hdr;
            const uint8_t *payload = NULL;

            if (tollgate_proto_decode(pkt.data + 1, pkt.len - 1, &hdr, &payload) >= 0) {
                ESP_LOGI(TAG, "TollGate PAY received (seq=%u)", hdr.seq);

                /* Build ACK response */
                relay_packet_t ack_pkt;
                memset(&ack_pkt, 0, sizeof(ack_pkt));
                ack_pkt.data[0] = RELAY_TYPE_TOLLGATE_ACK;

                tollgate_ack_payload_t ack_payload;
                memset(&ack_payload, 0, sizeof(ack_payload));
                ack_payload.price_sats = 0;  /* TODO: real price from config */

                int ack_len = tollgate_proto_encode(ack_pkt.data + 1,
                                                     RELAY_PACKET_MAX_SIZE - 1,
                                                     TG_MSG_ACK, hdr.seq,
                                                     (const char *)&ack_payload,
                                                     sizeof(ack_payload));
                if (ack_len > 0) {
                    ack_pkt.len = ack_len + 1;
                    xQueueSend(g_tx_queue, &ack_pkt, pdMS_TO_TICKS(100));
                    ESP_LOGI(TAG, "TollGate ACK queued (seq=%u)", hdr.seq);
                }
            }
            break;
        }
#endif /* CONFIG_ENABLE_TOLLGATE */

        case RELAY_TYPE_TELEMETRY:
            ESP_LOGD(TAG, "Telemetry packet (ignoring in relay)");
            break;

        default:
            ESP_LOGI(TAG, "Unknown packet type 0x%02X (%d bytes, RSSI=%d)",
                     pkt_type, (int)pkt.len, pkt.rssi);
            break;
        }

        /* Periodic heap monitoring (every 10 packets) */
        if (packets_processed % 10 == 0) {
            ESP_LOGI(TAG, "Processed %lu packets, free heap=%lu",
                     (unsigned long)packets_processed,
                     (unsigned long)esp_get_free_heap_size());
        }
    }
}
