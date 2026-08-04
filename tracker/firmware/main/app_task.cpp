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

#include "tollgate_payment_proto.h"

static const char *TAG = "APP_TASK";

/* Global queues — created by app_main */
extern QueueHandle_t g_rx_queue;
extern QueueHandle_t g_tx_queue;

void app_task(void *arg)
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

    /* Initialize nostr_store */
    nostr_store_t store;
    nostr_store_init(&store, "/littlefs/nostr");
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
            if (nostr_event_deserialize(&event, pkt.data + 1, pkt.len - 1) == 0) {
                /* Verify Schnorr signature if secp context available */
                int sig_ok = 0;
                if (ctx) {
                    secp256k1_xonly_pubkey xpub;
                    if (secp256k1_xonly_pubkey_parse(ctx, &xpub, event.pubkey) {
                        sig_ok = secp256k1_schnorrsig_verify(
                            ctx,
                            event.sig,        /* sig64 */
                            event.id,         /* msg32 (event id = hash) */
                            32,               /* msglen */
                            &xpub);
                    }
                }

                if (sig_ok) {
                    nostr_store_add(&store, &event);
                    ESP_LOGI(TAG, "Nostr event stored (kind=%d, verified=1)", event.kind);
                } else {
                    ESP_LOGW(TAG, "Nostr event REJECTED (invalid sig)");
                }
            } else {
                ESP_LOGW(TAG, "Nostr event deserialize failed");
            }
            break;
        }
#endif

        case RELAY_TYPE_TOLLGATE_PAY: {
            /* Decode PAY → send ACK back */
            tollgate_msg_header_t hdr;
            const uint8_t *payload = NULL;

            if (tollgate_msg_decode(pkt.data + 1, pkt.len - 1, &hdr, &payload) == 0) {
                ESP_LOGI(TAG, "TollGate PAY received (seq=%u)", hdr.seq);

                /* Build ACK response */
                relay_packet_t ack_pkt;
                memset(&ack_pkt, 0, sizeof(ack_pkt));
                ack_pkt.data[0] = RELAY_TYPE_TOLLGATE_ACK;

                tollgate_msg_t ack_msg;
                memset(&ack_msg, 0, sizeof(ack_msg));
                ack_msg.type = TOLLGATE_MSG_ACK;
                ack_msg.seq = hdr.seq;

                int ack_len = tollgate_msg_encode(&ack_msg, ack_pkt.data + 1, RELAY_PACKET_MAX_SIZE - 1);
                if (ack_len > 0) {
                    ack_pkt.len = ack_len + 1;
                    xQueueSend(g_tx_queue, &ack_pkt, pdMS_TO_TICKS(100));
                    ESP_LOGI(TAG, "TollGate ACK queued (seq=%u)", hdr.seq);
                }
            }
            break;
        }

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
