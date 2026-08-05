#pragma once

#include <stdint.h>
#include <stddef.h>

#define RELAY_PACKET_MAX_SIZE 512
#define RELAY_RX_QUEUE_LEN    8
#define RELAY_TX_QUEUE_LEN    4

/* Packet type tags (1 byte, first byte of payload) */
#define RELAY_TYPE_NOSTR_EVENT  0x01
#define RELAY_TYPE_TOLLGATE_PAY 0x02
#define RELAY_TYPE_TOLLGATE_ACK 0x03
#define RELAY_TYPE_TELEMETRY    0x04
#define RELAY_TYPE_RAW          0xFF

/* Packet structure passed between radio_task and app_task via FreeRTOS queues */
typedef struct {
    uint8_t  data[RELAY_PACKET_MAX_SIZE];
    size_t   len;
    uint32_t timestamp;
    int      rssi;
} relay_packet_t;
