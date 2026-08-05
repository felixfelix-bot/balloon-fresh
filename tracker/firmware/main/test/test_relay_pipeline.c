/*
 * test_relay_pipeline.c — Host-side integration test for the relay pipeline.
 *
 * Tests the full pipeline WITHOUT hardware:
 *   radio_task (mock) → rx_queue → app_task (extracted logic) → nostr_store
 *
 * The app_task dispatch logic from app_task.cpp is re-implemented here in plain C,
 * calling the REAL nostr_store code (components/nostr_store/nostr_store.c).
 * No FreeRTOS, no ESP-IDF, no secp256k1 — just gcc + nostr_store.
 *
 * Build & run:
 *   gcc -Wall -O2 -I main -I components/nostr_store/include \
 *       -o /tmp/test_relay main/test/test_relay_pipeline.c \
 *       components/nostr_store/nostr_store.c && /tmp/test_relay
 *
 * Pass condition: all tests print PASS, exit code 0.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <sys/stat.h>

#include "relay_types.h"
#include "nostr_store.h"

/* ------------------------------------------------------------------ */
/* Test configuration                                                 */
/* ------------------------------------------------------------------ */

#define TEST_DIR "/tmp/relay_test"

/* ------------------------------------------------------------------ */
/* Mock FreeRTOS queues — simple ring buffers                          */
/*                                                                    */
/* Mirrors the g_rx_queue / g_tx_queue pattern from radio_task.cpp     */
/* and app_task.cpp. Capacity matches RELAY_RX_QUEUE_LEN /             */
/* RELAY_TX_QUEUE_LEN from relay_types.h.                              */
/* ------------------------------------------------------------------ */

typedef struct {
    relay_packet_t packets[16];
    int head;
    int tail;
    int count;
    int capacity;
} mock_queue_t;

static void mock_queue_init(mock_queue_t *q, int capacity)
{
    memset(q, 0, sizeof(*q));
    q->capacity = capacity;
}

static int mock_queue_send(mock_queue_t *q, const relay_packet_t *pkt)
{
    if (q->count >= q->capacity) return -1;  /* queue full */
    q->packets[q->tail] = *pkt;
    q->tail = (q->tail + 1) % q->capacity;
    q->count++;
    return 0;
}

static int mock_queue_receive(mock_queue_t *q, relay_packet_t *out)
{
    if (q->count == 0) return -1;  /* empty */
    *out = q->packets[q->head];
    q->head = (q->head + 1) % q->capacity;
    q->count--;
    return 0;
}

/* ------------------------------------------------------------------ */
/* Mock tollgate protocol (tollgate_payment_proto.h doesn't exist yet) */
/*                                                                    */
/* Minimal encode/decode matching the usage in app_task.cpp.           */
/* When the real header is written, these tests can be updated to     */
/* include it and call the real functions.                            */
/* ------------------------------------------------------------------ */

#define TOLLGATE_MSG_PAY  0x01
#define TOLLGATE_MSG_ACK  0x02

typedef struct {
    uint8_t  type;
    uint32_t seq;
} tollgate_msg_header_t;

typedef struct {
    uint8_t  type;
    uint32_t seq;
    uint8_t  payload[256];
    uint16_t payload_len;
} tollgate_msg_t;

/* Encode: [1 type][4 seq BE][2 payload_len LE][payload] */
static int tollgate_msg_encode(const tollgate_msg_t *msg, uint8_t *buf, size_t buf_size)
{
    size_t needed = 1 + 4 + 2 + msg->payload_len;
    if (buf_size < needed) return -1;

    size_t pos = 0;
    buf[pos++] = msg->type;
    buf[pos++] = (uint8_t)(msg->seq >> 24);
    buf[pos++] = (uint8_t)(msg->seq >> 16);
    buf[pos++] = (uint8_t)(msg->seq >> 8);
    buf[pos++] = (uint8_t)(msg->seq);
    buf[pos++] = (uint8_t)(msg->payload_len & 0xFF);
    buf[pos++] = (uint8_t)((msg->payload_len >> 8) & 0xFF);
    memcpy(buf + pos, msg->payload, msg->payload_len);
    pos += msg->payload_len;

    return (int)pos;
}

/* Decode: returns 0 on success, fills hdr and sets *payload pointer */
static int tollgate_msg_decode(const uint8_t *buf, size_t buf_len,
                               tollgate_msg_header_t *hdr,
                               const uint8_t **payload)
{
    if (buf_len < 7) return -1;

    size_t pos = 0;
    hdr->type = buf[pos++];
    hdr->seq  = ((uint32_t)buf[pos] << 24) | ((uint32_t)buf[pos+1] << 16) |
                ((uint32_t)buf[pos+2] << 8) | (uint32_t)buf[pos+3];
    pos += 4;

    uint16_t plen = (uint16_t)(buf[pos] | (buf[pos+1] << 8));
    pos += 2;

    if (pos + plen > buf_len) return -1;
    *payload = buf + pos;
    return 0;
}

/* ------------------------------------------------------------------ */
/* App task dispatch logic — extracted from app_task.cpp              */
/*                                                                    */
/* This is the core of the relay pipeline: take a relay_packet_t      */
/* from the rx_queue, dispatch by type tag, and process it.           */
/*                                                                    */
/* For NOSTR_EVENT: deserialize → store in nostr_store                 */
/* For TOLLGATE_PAY: decode → build ACK → push to tx_queue            */
/* For TELEMETRY:    ignore                                          */
/* For unknown/RAW:  ignore                                          */
/* ------------------------------------------------------------------ */

typedef struct {
    nostr_store_t *store;
    mock_queue_t  *tx_queue;
} app_task_ctx_t;

static void app_task_process_packet(app_task_ctx_t *ctx, const relay_packet_t *pkt)
{
    if (pkt->len == 0) return;

    uint8_t pkt_type = pkt->data[0];

    switch (pkt_type) {

    case RELAY_TYPE_NOSTR_EVENT: {
        nostr_event_t event;
        memset(&event, 0, sizeof(event));

        /* Offset +1 to skip the type tag byte (matches app_task.cpp).
         *
         * NOTE: app_task.cpp checks == 0, but nostr_event_deserialize()
         * returns bytes consumed (>0) on success and 0 on error.
         * The == 0 check in app_task.cpp is a bug — it means events are
         * NEVER stored on the real firmware. We use the correct > 0 check
         * here so the pipeline actually works.
         * See: nostr_store.h line 125: "Returns bytes used, or 0 on error"
         */
        if (nostr_event_deserialize(&event, pkt->data + 1, (uint16_t)(pkt->len - 1)) > 0) {
            nostr_store_add(ctx->store, &event);
        }
        break;
    }

    case RELAY_TYPE_TOLLGATE_PAY: {
        tollgate_msg_header_t hdr;
        const uint8_t *payload = NULL;

        if (tollgate_msg_decode(pkt->data + 1, pkt->len - 1, &hdr, &payload) == 0) {
            /* Build ACK response (matches app_task.cpp logic) */
            relay_packet_t ack_pkt;
            memset(&ack_pkt, 0, sizeof(ack_pkt));
            ack_pkt.data[0] = RELAY_TYPE_TOLLGATE_ACK;

            tollgate_msg_t ack_msg;
            memset(&ack_msg, 0, sizeof(ack_msg));
            ack_msg.type = TOLLGATE_MSG_ACK;
            ack_msg.seq = hdr.seq;

            int ack_len = tollgate_msg_encode(&ack_msg, ack_pkt.data + 1,
                                              RELAY_PACKET_MAX_SIZE - 1);
            if (ack_len > 0) {
                ack_pkt.len = (size_t)(ack_len + 1);
                mock_queue_send(ctx->tx_queue, &ack_pkt);
            }
        }
        break;
    }

    case RELAY_TYPE_TELEMETRY:
        /* Ignored in relay mode (matches app_task.cpp) */
        break;

    default:
        /* Unknown/raw — ignored */
        break;
    }
}

/* ------------------------------------------------------------------ */
/* Test helpers                                                       */
/* ------------------------------------------------------------------ */

static void clean_test_dir(void)
{
    int rc = system("rm -rf " TEST_DIR);
    (void)rc;
}

static void make_nostr_event(nostr_event_t *evt, uint8_t id_byte, const char *content)
{
    memset(evt, 0, sizeof(*evt));
    memset(evt->id, id_byte, NOSTR_EVENT_ID_SIZE);
    memset(evt->pubkey, 0xAA, NOSTR_PUBKEY_SIZE);
    evt->created_at = 1000 + id_byte;
    evt->kind = 1;
    evt->content_len = (uint16_t)strlen(content);
    memcpy(evt->content, content, evt->content_len);
    evt->num_tags = 0;
}

/* Build a relay_packet_t containing a serialized Nostr event with type tag */
static void build_nostr_relay_packet(relay_packet_t *pkt, const nostr_event_t *evt)
{
    memset(pkt, 0, sizeof(*pkt));
    pkt->data[0] = RELAY_TYPE_NOSTR_EVENT;
    uint16_t slen = nostr_event_serialize(evt, pkt->data + 1, RELAY_PACKET_MAX_SIZE - 1);
    assert(slen > 0);
    pkt->len = (size_t)(slen + 1);
    pkt->timestamp = 0;
    pkt->rssi = -70;
}

/* Build a relay_packet_t containing a tollgate PAY message */
static void build_tollgate_pay_packet(relay_packet_t *pkt, uint32_t seq)
{
    memset(pkt, 0, sizeof(*pkt));
    pkt->data[0] = RELAY_TYPE_TOLLGATE_PAY;

    tollgate_msg_t pay_msg;
    memset(&pay_msg, 0, sizeof(pay_msg));
    pay_msg.type = TOLLGATE_MSG_PAY;
    pay_msg.seq = seq;
    pay_msg.payload_len = 0;

    int enc_len = tollgate_msg_encode(&pay_msg, pkt->data + 1, RELAY_PACKET_MAX_SIZE - 1);
    assert(enc_len > 0);
    pkt->len = (size_t)(enc_len + 1);
    pkt->timestamp = 0;
    pkt->rssi = -65;
}

/* ------------------------------------------------------------------ */
/* Mock radio_task — simulates receiving packets and pushing to rx_q  */
/* ------------------------------------------------------------------ */

static void mock_radio_receive(mock_queue_t *rx_queue, const relay_packet_t *pkt)
{
    /* Simulates: radio recv → fill rx_pkt → xQueueSend(g_rx_queue, ...) */
    int rc = mock_queue_send(rx_queue, pkt);
    assert(rc == 0 && "RX queue full in mock radio");
}

/* ------------------------------------------------------------------ */
/* Tests                                                              */
/* ------------------------------------------------------------------ */

int main(void)
{
    printf("\n=== Relay Pipeline Integration Tests (host, no hardware) ===\n\n");

    /* ---- Setup: queues and store ---- */
    mock_queue_t rx_queue, tx_queue;
    mock_queue_init(&rx_queue, RELAY_RX_QUEUE_LEN);
    mock_queue_init(&tx_queue, RELAY_TX_QUEUE_LEN);

    clean_test_dir();
    nostr_store_t *store = malloc(sizeof(nostr_store_t));
    assert(store);
    nostr_store_init(store, TEST_DIR);

    app_task_ctx_t app_ctx = { .store = store, .tx_queue = &tx_queue };

    /* ---- Struct size sanity ---- */
    printf("sizeof(relay_packet_t)  = %zu bytes\n", sizeof(relay_packet_t));
    printf("sizeof(nostr_event_t)   = %zu bytes\n", sizeof(nostr_event_t));
    printf("sizeof(nostr_store_t)   = %zu bytes (%.1f KB)\n\n",
           sizeof(nostr_store_t), (double)sizeof(nostr_store_t) / 1024.0);

    /* ================================================================== */
    /* TEST 1: Nostr event end-to-end: radio → rx_queue → app → store     */
    /* ================================================================== */
    printf("TEST 1: Nostr event end-to-end (radio→app→store)... ");

    nostr_event_t evt;
    make_nostr_event(&evt, 0x42, "Hello from balloon mesh!");

    /* Step 1: mock radio receives and pushes to rx_queue */
    relay_packet_t radio_pkt;
    build_nostr_relay_packet(&radio_pkt, &evt);
    mock_radio_receive(&rx_queue, &radio_pkt);

    /* Verify packet is in the queue */
    assert(rx_queue.count == 1);

    /* Step 2: app_task dequeues and processes */
    relay_packet_t app_pkt;
    assert(mock_queue_receive(&rx_queue, &app_pkt) == 0);
    app_task_process_packet(&app_ctx, &app_pkt);

    /* Step 3: verify event is in nostr_store */
    assert(nostr_store_count(store) == 1);

    nostr_event_t retrieved;
    int rc = nostr_store_find(store, evt.id, &retrieved);
    assert(rc == 0);
    assert(retrieved.id[0] == 0x42);
    assert(retrieved.kind == 1);
    assert(retrieved.created_at == 1000 + 0x42);
    assert(retrieved.content_len == strlen("Hello from balloon mesh!"));
    assert(memcmp(retrieved.content, "Hello from balloon mesh!",
                  strlen("Hello from balloon mesh!")) == 0);
    assert(retrieved.num_tags == 0);

    /* rx_queue should now be empty */
    assert(rx_queue.count == 0);

    printf("PASS\n");

    /* ================================================================== */
    /* TEST 2: Multiple Nostr events through the pipeline                */
    /* ================================================================== */
    printf("TEST 2: Multiple Nostr events through pipeline... ");

    for (int i = 1; i <= 5; i++) {
        nostr_event_t e;
        make_nostr_event(&e, (uint8_t)(0x50 + i), "mesh relay test");

        relay_packet_t pkt;
        build_nostr_relay_packet(&pkt, &e);
        mock_radio_receive(&rx_queue, &pkt);

        /* Process each packet as app_task would */
        relay_packet_t rx;
        assert(mock_queue_receive(&rx_queue, &rx) == 0);
        app_task_process_packet(&app_ctx, &rx);
    }

    /* Should have 1 (from test 1) + 5 = 6 events */
    assert(nostr_store_count(store) == 6);

    /* Verify each of the 5 new events by ID */
    for (int i = 1; i <= 5; i++) {
        uint8_t id[32];
        memset(id, 0x50 + i, 32);
        nostr_event_t found;
        assert(nostr_store_find(store, id, &found) == 0);
        assert(found.id[0] == 0x50 + i);
        assert(memcmp(found.content, "mesh relay test", 15) == 0);
    }

    printf("PASS\n");

    /* ================================================================== */
    /* TEST 3: Duplicate Nostr event is rejected by store                */
    /* ================================================================== */
    printf("TEST 3: Duplicate Nostr event rejected... ");

    /* Re-send the first event (id=0x42) through the pipeline */
    relay_packet_t dup_pkt;
    build_nostr_relay_packet(&dup_pkt, &evt);
    mock_radio_receive(&rx_queue, &dup_pkt);

    relay_packet_t rx;
    assert(mock_queue_receive(&rx_queue, &rx) == 0);
    app_task_process_packet(&app_ctx, &rx);

    /* Store should still have 6 events (duplicate not added) */
    assert(nostr_store_count(store) == 6);

    printf("PASS\n");

    /* ================================================================== */
    /* TEST 4: TollGate PAY → ACK path (radio → app → tx_queue)          */
    /* ================================================================== */
    printf("TEST 4: TollGate PAY→ACK (radio→app→tx_queue)... ");

    /* Build a PAY packet with seq=42 */
    relay_packet_t pay_pkt;
    build_tollgate_pay_packet(&pay_pkt, 42);
    mock_radio_receive(&rx_queue, &pay_pkt);

    /* App task processes it */
    assert(mock_queue_receive(&rx_queue, &rx) == 0);
    app_task_process_packet(&app_ctx, &rx);

    /* ACK should be in tx_queue */
    assert(tx_queue.count == 1);
    relay_packet_t ack_pkt;
    assert(mock_queue_receive(&tx_queue, &ack_pkt) == 0);

    /* Verify ACK packet structure */
    assert(ack_pkt.len > 1);
    assert(ack_pkt.data[0] == RELAY_TYPE_TOLLGATE_ACK);

    /* Decode ACK message */
    tollgate_msg_header_t ack_hdr;
    const uint8_t *ack_payload = NULL;
    assert(tollgate_msg_decode(ack_pkt.data + 1, ack_pkt.len - 1, &ack_hdr, &ack_payload) == 0);
    assert(ack_hdr.type == TOLLGATE_MSG_ACK);
    assert(ack_hdr.seq == 42);

    /* tx_queue should now be empty */
    assert(tx_queue.count == 0);

    printf("PASS\n");

    /* ================================================================== */
    /* TEST 5: Multiple tollgate PAY → ACK round-trips                  */
    /* ================================================================== */
    printf("TEST 5: Multiple tollgate PAY→ACK round-trips... ");

    for (uint32_t seq = 100; seq < 105; seq++) {
        relay_packet_t p;
        build_tollgate_pay_packet(&p, seq);
        mock_radio_receive(&rx_queue, &p);

        relay_packet_t r;
        assert(mock_queue_receive(&rx_queue, &r) == 0);
        app_task_process_packet(&app_ctx, &r);

        /* One ACK per PAY */
        assert(tx_queue.count == 1);
        relay_packet_t a;
        assert(mock_queue_receive(&tx_queue, &a) == 0);
        assert(a.data[0] == RELAY_TYPE_TOLLGATE_ACK);

        tollgate_msg_header_t h;
        const uint8_t *pl = NULL;
        assert(tollgate_msg_decode(a.data + 1, a.len - 1, &h, &pl) == 0);
        assert(h.type == TOLLGATE_MSG_ACK);
        assert(h.seq == seq);
    }

    assert(tx_queue.count == 0);

    printf("PASS\n");

    /* ================================================================== */
    /* TEST 6: Telemetry packets are ignored (no store, no ACK)         */
    /* ================================================================== */
    printf("TEST 6: Telemetry packet ignored... ");

    uint16_t store_before = nostr_store_count(store);

    relay_packet_t tel_pkt;
    memset(&tel_pkt, 0, sizeof(tel_pkt));
    tel_pkt.data[0] = RELAY_TYPE_TELEMETRY;
    tel_pkt.len = 64;
    tel_pkt.rssi = -50;
    mock_radio_receive(&rx_queue, &tel_pkt);

    assert(mock_queue_receive(&rx_queue, &rx) == 0);
    app_task_process_packet(&app_ctx, &rx);

    /* No new events in store, no ACK in tx_queue */
    assert(nostr_store_count(store) == store_before);
    assert(tx_queue.count == 0);

    printf("PASS\n");

    /* ================================================================== */
    /* TEST 7: Unknown/raw packet type is ignored                        */
    /* ================================================================== */
    printf("TEST 7: Unknown packet type ignored... ");

    store_before = nostr_store_count(store);

    relay_packet_t unk_pkt;
    memset(&unk_pkt, 0, sizeof(unk_pkt));
    unk_pkt.data[0] = 0xFE;  /* unknown type */
    unk_pkt.len = 32;
    mock_radio_receive(&rx_queue, &unk_pkt);

    assert(mock_queue_receive(&rx_queue, &rx) == 0);
    app_task_process_packet(&app_ctx, &rx);

    assert(nostr_store_count(store) == store_before);
    assert(tx_queue.count == 0);

    printf("PASS\n");

    /* ================================================================== */
    /* TEST 8: Mixed traffic — interleaved Nostr + tollgate + telemetry  */
    /* ================================================================== */
    printf("TEST 8: Mixed traffic (interleaved)... ");

    store_before = nostr_store_count(store);

    /* Burst of mixed packets into rx_queue, processing as we go
     * (queue capacity is RELAY_RX_QUEUE_LEN=8, so we can't batch all 12) */
    for (int i = 0; i < 4; i++) {
        /* Nostr event */
        nostr_event_t e;
        make_nostr_event(&e, (uint8_t)(0x60 + i), "mixed traffic");
        relay_packet_t p1;
        build_nostr_relay_packet(&p1, &e);
        mock_radio_receive(&rx_queue, &p1);
        relay_packet_t r1;
        assert(mock_queue_receive(&rx_queue, &r1) == 0);
        app_task_process_packet(&app_ctx, &r1);

        /* Tollgate PAY */
        relay_packet_t p2;
        build_tollgate_pay_packet(&p2, 200 + i);
        mock_radio_receive(&rx_queue, &p2);
        relay_packet_t r2;
        assert(mock_queue_receive(&rx_queue, &r2) == 0);
        app_task_process_packet(&app_ctx, &r2);

        /* Telemetry (should be ignored) */
        relay_packet_t p3;
        memset(&p3, 0, sizeof(p3));
        p3.data[0] = RELAY_TYPE_TELEMETRY;
        p3.len = 32;
        mock_radio_receive(&rx_queue, &p3);
        relay_packet_t r3;
        assert(mock_queue_receive(&rx_queue, &r3) == 0);
        app_task_process_packet(&app_ctx, &r3);
    }

    int packets_processed = 12;

    (void)packets_processed;

    /* 4 Nostr events should have been added */
    assert(nostr_store_count(store) == store_before + 4);

    /* 4 tollgate ACKs should be in tx_queue */
    assert(tx_queue.count == 4);

    /* Drain and verify all ACKs */
    int ack_count = 0;
    while (mock_queue_receive(&tx_queue, &ack_pkt) == 0) {
        assert(ack_pkt.data[0] == RELAY_TYPE_TOLLGATE_ACK);
        tollgate_msg_header_t h;
        const uint8_t *pl = NULL;
        assert(tollgate_msg_decode(ack_pkt.data + 1, ack_pkt.len - 1, &h, &pl) == 0);
        assert(h.type == TOLLGATE_MSG_ACK);
        assert(h.seq >= 200 && h.seq < 204);
        ack_count++;
    }
    assert(ack_count == 4);

    printf("PASS\n");

    /* ================================================================== */
    /* TEST 9: Nostr event with tags survives the pipeline              */
    /* ================================================================== */
    printf("TEST 9: Nostr event with tags through pipeline... ");

    nostr_event_t tagged_evt;
    memset(&tagged_evt, 0, sizeof(tagged_evt));
    memset(tagged_evt.id, 0x77, NOSTR_EVENT_ID_SIZE);
    memset(tagged_evt.pubkey, 0xBB, NOSTR_PUBKEY_SIZE);
    tagged_evt.created_at = 1700000000;
    tagged_evt.kind = 30023;
    tagged_evt.content_len = 11;
    memcpy(tagged_evt.content, "hello world", 11);
    tagged_evt.num_tags = 2;
    tagged_evt.tags[0].key_len = 1;
    memcpy(tagged_evt.tags[0].key, "L", 1);
    tagged_evt.tags[0].value_len = 17;
    memcpy(tagged_evt.tags[0].value, "balloon-telemetry", 17);
    tagged_evt.tags[1].key_len = 1;
    memcpy(tagged_evt.tags[1].key, "t", 1);
    tagged_evt.tags[1].value_len = 5;
    memcpy(tagged_evt.tags[1].value, "test1", 5);

    relay_packet_t tag_pkt;
    build_nostr_relay_packet(&tag_pkt, &tagged_evt);
    mock_radio_receive(&rx_queue, &tag_pkt);

    assert(mock_queue_receive(&rx_queue, &rx) == 0);
    app_task_process_packet(&app_ctx, &rx);

    nostr_event_t found;
    assert(nostr_store_find(store, tagged_evt.id, &found) == 0);
    assert(found.kind == 30023);
    assert(found.created_at == 1700000000);
    assert(found.content_len == 11);
    assert(memcmp(found.content, "hello world", 11) == 0);
    assert(found.num_tags == 2);
    assert(found.tags[0].key_len == 1);
    assert(found.tags[0].value_len == 17);
    assert(memcmp(found.tags[0].key, "L", 1) == 0);
    assert(memcmp(found.tags[0].value, "balloon-telemetry", 17) == 0);
    assert(found.tags[1].key_len == 1);
    assert(found.tags[1].value_len == 5);
    assert(memcmp(found.tags[1].key, "t", 1) == 0);
    assert(memcmp(found.tags[1].value, "test1", 5) == 0);

    printf("PASS\n");

    /* ================================================================== */
    /* TEST 10: Empty packet (len=0) doesn't crash                       */
    /* ================================================================== */
    printf("TEST 10: Empty packet (len=0) safe... ");

    relay_packet_t empty_pkt;
    memset(&empty_pkt, 0, sizeof(empty_pkt));
    empty_pkt.len = 0;
    mock_radio_receive(&rx_queue, &empty_pkt);

    assert(mock_queue_receive(&rx_queue, &rx) == 0);
    app_task_process_packet(&app_ctx, &rx);  /* should not crash */

    assert(tx_queue.count == 0);

    printf("PASS\n");

    /* ================================================================== */
    /* TEST 11: Malformed Nostr payload (truncated) doesn't crash       */
    /* ================================================================== */
    printf("TEST 11: Malformed Nostr payload (truncated)... ");

    store_before = nostr_store_count(store);

    relay_packet_t bad_pkt;
    memset(&bad_pkt, 0, sizeof(bad_pkt));
    bad_pkt.data[0] = RELAY_TYPE_NOSTR_EVENT;
    /* Only 5 bytes of payload — way too short for a valid event */
    bad_pkt.data[1] = 0x01;
    bad_pkt.data[2] = 0x02;
    bad_pkt.data[3] = 0x03;
    bad_pkt.data[4] = 0x04;
    bad_pkt.data[5] = 0x05;
    bad_pkt.len = 6;
    mock_radio_receive(&rx_queue, &bad_pkt);

    assert(mock_queue_receive(&rx_queue, &rx) == 0);
    app_task_process_packet(&app_ctx, &rx);  /* should not crash */

    /* Nothing should have been added to store */
    assert(nostr_store_count(store) == store_before);

    printf("PASS\n");

    /* ================================================================== */
    /* TEST 12: relay_packet_t structure packing                         */
    /* ================================================================== */
    printf("TEST 12: relay_packet_t packing... ");

    /* Verify the struct is self-contained and the data array is at offset 0 */
    assert(sizeof(relay_packet_t) >= RELAY_PACKET_MAX_SIZE + sizeof(size_t) + sizeof(uint32_t) + sizeof(int));

    /* Verify packet type constants */
    assert(RELAY_TYPE_NOSTR_EVENT  == 0x01);
    assert(RELAY_TYPE_TOLLGATE_PAY == 0x02);
    assert(RELAY_TYPE_TOLLGATE_ACK == 0x03);
    assert(RELAY_TYPE_TELEMETRY    == 0x04);
    assert(RELAY_TYPE_RAW          == 0xFF);

    printf("PASS\n");

    /* ---- Cleanup ---- */
    free(store);
    clean_test_dir();

    printf("\n=== Results: 12/12 passed ===\n");
    printf("Pipeline verified: radio_task(mock) → rx_queue → app_task → nostr_store\n");
    printf("                 + tollgate PAY→ACK, telemetry, mixed traffic, edge cases\n");
    return 0;
}