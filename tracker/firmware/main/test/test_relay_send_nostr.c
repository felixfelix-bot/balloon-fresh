/*
 * test_relay_send_nostr.c — Host-side test for the relay_send_nostr CLI command.
 *
 * Tests the logic that the CLI handler will use, WITHOUT hardware:
 *   - Build a nostr_event_t (hardcoded test event or parse args for content/kind)
 *   - Call nostr_event_serialize() into pkt.data + 1 (skip type tag byte)
 *   - Set pkt.data[0] = RELAY_TYPE_NOSTR_EVENT, pkt.len = serialized_len + 1
 *   - Check serialized event fits in RELAY_PACKET_MAX_SIZE - 1
 *   - "Queue" the packet (mock g_tx_queue)
 *   - Verify the packet on the mock queue round-trips back through deserialize
 *
 * Build & run:
 *   gcc -Wall -O2 -I main -I components/nostr_store/include \
 *       -o /tmp/test_send_nostr main/test/test_relay_send_nostr.c \
 *       components/nostr_store/nostr_store.c && /tmp/test_send_nostr
 *
 * Pass condition: all tests print PASS, exit code 0.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

#include "relay_types.h"
#include "nostr_store.h"

/* ------------------------------------------------------------------ */
/* Mock tx queue (mirrors g_tx_queue from radio_task.cpp)              */
/* ------------------------------------------------------------------ */

typedef struct {
    relay_packet_t packets[8];
    int count;
} mock_tx_queue_t;

static void mock_tx_init(mock_tx_queue_t *q) { q->count = 0; }

static int mock_tx_send(mock_tx_queue_t *q, const relay_packet_t *pkt)
{
    if (q->count >= 8) return -1;
    q->packets[q->count++] = *pkt;
    return 0;
}

/* ------------------------------------------------------------------ */
/* CLI logic under test — extracted from the handler we will write.   */
/* This mirrors what cli_cmd_relay_send_nostr() will do, minus printf. */
/* ------------------------------------------------------------------ */

/* Build a default test event if args are empty */
static void make_default_test_event(nostr_event_t *evt)
{
    memset(evt, 0, sizeof(*evt));
    /* Deterministic test ID + pubkey (zeros are fine for V1 no-sig mode) */
    for (int i = 0; i < NOSTR_EVENT_ID_SIZE; i++) evt->id[i] = (uint8_t)(0x10 + i);
    for (int i = 0; i < NOSTR_PUBKEY_SIZE; i++) evt->pubkey[i] = 0xAB;
    evt->created_at = 1700000000;
    evt->kind = 1;
    const char *content = "balloon relay test event";
    evt->content_len = (uint16_t)strlen(content);
    memcpy(evt->content, content, evt->content_len);
    evt->num_tags = 0;
}

/* Build an event from explicit content + kind (parse-args path) */
static void make_custom_event(nostr_event_t *evt, uint16_t kind,
                              const char *content)
{
    memset(evt, 0, sizeof(*evt));
    for (int i = 0; i < NOSTR_EVENT_ID_SIZE; i++) evt->id[i] = (uint8_t)(0x20 + i);
    for (int i = 0; i < NOSTR_PUBKEY_SIZE; i++) evt->pubkey[i] = 0xCD;
    evt->created_at = 1700001234;
    evt->kind = kind;
    evt->content_len = (uint16_t)strlen(content);
    /* Cap at NOSTR_MAX_CONTENT */
    if (evt->content_len > NOSTR_MAX_CONTENT) evt->content_len = NOSTR_MAX_CONTENT;
    memcpy(evt->content, content, evt->content_len);
    evt->num_tags = 0;
}

/* The core handler logic. Returns 0 on success, -1 on serialize failure,
 * -2 on queue full. Caller passes the event to send. */
static int relay_send_nostr_logic(mock_tx_queue_t *txq, const nostr_event_t *evt)
{
    relay_packet_t pkt;
    memset(&pkt, 0, sizeof(pkt));

    pkt.data[0] = RELAY_TYPE_NOSTR_EVENT;

    uint16_t slen = nostr_event_serialize(evt, pkt.data + 1,
                                           RELAY_PACKET_MAX_SIZE - 1);
    if (slen == 0) return -1;  /* serialize error or too big */

    pkt.len = (size_t)(slen + 1);
    pkt.timestamp = 0;
    pkt.rssi = 0;

    return mock_tx_send(txq, &pkt) == 0 ? 0 : -2;
}

/* ------------------------------------------------------------------ */
/* Test helpers                                                       */
/* ------------------------------------------------------------------ */

static void assert_event_roundtrip(const relay_packet_t *pkt,
                                   const nostr_event_t *expected)
{
    assert(pkt->len > 1);
    assert(pkt->data[0] == RELAY_TYPE_NOSTR_EVENT);

    nostr_event_t decoded;
    memset(&decoded, 0, sizeof(decoded));
    uint16_t used = nostr_event_deserialize(&decoded, pkt->data + 1,
                                             (uint16_t)(pkt->len - 1));
    assert(used > 0);
    assert(memcmp(decoded.id, expected->id, NOSTR_EVENT_ID_SIZE) == 0);
    assert(memcmp(decoded.pubkey, expected->pubkey, NOSTR_PUBKEY_SIZE) == 0);
    assert(decoded.created_at == expected->created_at);
    assert(decoded.kind == expected->kind);
    assert(decoded.content_len == expected->content_len);
    assert(memcmp(decoded.content, expected->content, expected->content_len) == 0);
    assert(decoded.num_tags == expected->num_tags);
}

/* ------------------------------------------------------------------ */
/* Tests                                                              */
/* ------------------------------------------------------------------ */

int main(void)
{
    printf("\n=== relay_send_nostr CLI Logic Tests (host, no hardware) ===\n\n");

    /* ================================================================== */
    /* TEST 1: Default test event sends + round-trips                    */
    /* ================================================================== */
    printf("TEST 1: Default test event sends + round-trips... ");

    mock_tx_queue_t txq;
    mock_tx_init(&txq);

    nostr_event_t evt;
    make_default_test_event(&evt);

    int rc = relay_send_nostr_logic(&txq, &evt);
    assert(rc == 0);
    assert(txq.count == 1);

    assert_event_roundtrip(&txq.packets[0], &evt);

    printf("PASS\n");

    /* ================================================================== */
    /* TEST 2: Custom kind + content round-trips                          */
    /* ================================================================== */
    printf("TEST 2: Custom kind + content round-trips... ");

    mock_tx_init(&txq);
    make_custom_event(&evt, 30023, "long-form content from balloon");

    rc = relay_send_nostr_logic(&txq, &evt);
    assert(rc == 0);
    assert(txq.count == 1);

    assert_event_roundtrip(&txq.packets[0], &evt);
    assert(txq.packets[0].data[0] == RELAY_TYPE_NOSTR_EVENT);

    printf("PASS\n");

    /* ================================================================== */
    /* TEST 3: Event with tags round-trips                               */
    /* ================================================================== */
    printf("TEST 3: Event with tags round-trips... ");

    mock_tx_init(&txq);
    memset(&evt, 0, sizeof(evt));
    for (int i = 0; i < NOSTR_EVENT_ID_SIZE; i++) evt.id[i] = (uint8_t)(0x30 + i);
    for (int i = 0; i < NOSTR_PUBKEY_SIZE; i++) evt.pubkey[i] = 0xEF;
    evt.created_at = 1700005678;
    evt.kind = 1;
    evt.content_len = 5;
    memcpy(evt.content, "hello", 5);
    evt.num_tags = 2;
    evt.tags[0].key_len = 1;
    memcpy(evt.tags[0].key, "L", 1);
    evt.tags[0].value_len = 7;
    memcpy(evt.tags[0].value, "balloon", 7);
    evt.tags[1].key_len = 1;
    memcpy(evt.tags[1].key, "t", 1);
    evt.tags[1].value_len = 3;
    memcpy(evt.tags[1].value, "gps", 3);

    rc = relay_send_nostr_logic(&txq, &evt);
    assert(rc == 0);
    assert(txq.count == 1);

    assert_event_roundtrip(&txq.packets[0], &evt);
    assert(txq.packets[0].data[0] == RELAY_TYPE_NOSTR_EVENT);
    /* Check tag round-trip */
    {
        nostr_event_t decoded;
        memset(&decoded, 0, sizeof(decoded));
        nostr_event_deserialize(&decoded, txq.packets[0].data + 1,
                                (uint16_t)(txq.packets[0].len - 1));
        assert(decoded.num_tags == 2);
        assert(decoded.tags[0].key_len == 1);
        assert(memcmp(decoded.tags[0].key, "L", 1) == 0);
        assert(decoded.tags[0].value_len == 7);
        assert(memcmp(decoded.tags[0].value, "balloon", 7) == 0);
    }

    printf("PASS\n");

    /* ================================================================== */
    /* TEST 4: Large content (fits within relay packet limit)              */
    /* ================================================================== */
    printf("TEST 4: Large content (fits relay packet)... ");

    /* Serialized layout: [32 id][32 pubkey][64 sig][4 created_at][2 kind]
     *   [2 clen][content][1 num_tags] = 137 + content_len bytes.
     * Relay packet max = 511 bytes (RELAY_PACKET_MAX_SIZE - 1 for type tag).
     * Max content = 511 - 137 = 374 bytes. Use 370 to be safe. */
    mock_tx_init(&txq);
    memset(&evt, 0, sizeof(evt));
    for (int i = 0; i < NOSTR_EVENT_ID_SIZE; i++) evt.id[i] = (uint8_t)(0x40 + i);
    evt.created_at = 1700099999;
    evt.kind = 1;
    evt.content_len = 370;
    memset(evt.content, 'X', 370);
    evt.num_tags = 0;

    rc = relay_send_nostr_logic(&txq, &evt);
    assert(rc == 0);
    assert(txq.count == 1);

    /* Verify the serialized size fits within RELAY_PACKET_MAX_SIZE */
    assert(txq.packets[0].len <= RELAY_PACKET_MAX_SIZE);

    assert_event_roundtrip(&txq.packets[0], &evt);

    printf("PASS\n");

    /* ================================================================== */
    /* TEST 5: Oversized event (serialize fails gracefully)               */
    /*          NOSTR_MAX_CONTENT (480) exceeds relay packet capacity.   */
    /*          Serialized = 137 + 480 = 617 > 511 → serialize returns 0. */
    /* ================================================================== */
    printf("TEST 5: Oversized content rejected by serialize... ");

    /* Confirm serialize returns 0 when content too big for relay packet */
    memset(&evt, 0, sizeof(evt));
    evt.content_len = NOSTR_MAX_CONTENT;  /* 480 */
    memset(evt.content, 'Y', NOSTR_MAX_CONTENT);

    mock_tx_init(&txq);
    rc = relay_send_nostr_logic(&txq, &evt);
    assert(rc == -1);  /* serialize error — too big for relay packet */
    assert(txq.count == 0);  /* nothing queued */

    printf("PASS\n");

    /* ================================================================== */
    /* TEST 6: Empty content event                                        */
    /* ================================================================== */
    printf("TEST 6: Empty content event... ");

    mock_tx_init(&txq);
    memset(&evt, 0, sizeof(evt));
    for (int i = 0; i < NOSTR_EVENT_ID_SIZE; i++) evt.id[i] = (uint8_t)(0x50 + i);
    evt.created_at = 1234567890;
    evt.kind = 0;
    evt.content_len = 0;
    evt.num_tags = 0;

    rc = relay_send_nostr_logic(&txq, &evt);
    assert(rc == 0);
    assert(txq.count == 1);
    assert_event_roundtrip(&txq.packets[0], &evt);

    printf("PASS\n");

    /* ================================================================== */
    /* TEST 7: Multiple events queued (queue capacity)                    */
    /* ================================================================== */
    printf("TEST 7: Multiple events queued... ");

    mock_tx_init(&txq);
    for (int i = 0; i < 4; i++) {
        make_default_test_event(&evt);
        evt.id[0] = (uint8_t)(0x60 + i);
        rc = relay_send_nostr_logic(&txq, &evt);
        assert(rc == 0);
    }
    assert(txq.count == 4);

    /* Verify each packet has the right type tag and unique IDs */
    for (int i = 0; i < 4; i++) {
        assert(txq.packets[i].data[0] == RELAY_TYPE_NOSTR_EVENT);
        assert(txq.packets[i].data[1] == (uint8_t)(0x60 + i));  /* id[0] */
    }

    printf("PASS\n");

    /* ================================================================== */
    /* TEST 8: Queue full returns -2                                      */
    /* ================================================================== */
    printf("TEST 8: Queue full returns -2... ");

    mock_tx_init(&txq);
    /* Fill the mock queue (capacity 8) */
    for (int i = 0; i < 8; i++) {
        make_default_test_event(&evt);
        evt.id[0] = (uint8_t)(0x70 + i);
        rc = relay_send_nostr_logic(&txq, &evt);
        assert(rc == 0);
    }
    assert(txq.count == 8);

    /* 9th send should fail with -2 (queue full) */
    make_default_test_event(&evt);
    evt.id[0] = 0x99;
    rc = relay_send_nostr_logic(&txq, &evt);
    assert(rc == -2);
    assert(txq.count == 8);  /* still 8, not 9 */

    printf("PASS\n");

    /* ================================================================== */
    /* TEST 9: Packet from TX queue feeds back through app_task pipeline   */
    /*         (simulates radio TX → remote radio RX → app_task store)     */
    /* ================================================================== */
    printf("TEST 9: TX packet round-trips through app_task pipeline... ");

    /* This proves the packet we queue for TX is the same shape that
     * app_task expects to receive on the RX side. If the firmware
     * transmits our packet and a remote relay receives it, the remote
     * app_task will deserialize + store it successfully. */

    mock_tx_init(&txq);

    /* Build a realistic event */
    make_custom_event(&evt, 1, "relay send nostr test from CLI");

    /* Send via our handler */
    rc = relay_send_nostr_logic(&txq, &evt);
    assert(rc == 0);

    /* Now simulate the remote side: take the packet from tx_queue,
     * feed it into the nostr_store via deserialize + add (same logic
     * as app_task.cpp RELAY_TYPE_NOSTR_EVENT handler). */
    (void)system("rm -rf /tmp/relay_send_nostr_test");
    nostr_store_t store;
    nostr_store_init(&store, "/tmp/relay_send_nostr_test");

    /* Process the TX packet as if it arrived on RX queue */
    relay_packet_t *tx_pkt = &txq.packets[0];
    assert(tx_pkt->data[0] == RELAY_TYPE_NOSTR_EVENT);

    nostr_event_t decoded;
    memset(&decoded, 0, sizeof(decoded));
    uint16_t used = nostr_event_deserialize(&decoded, tx_pkt->data + 1,
                                             (uint16_t)(tx_pkt->len - 1));
    assert(used > 0);

    int add_rc = nostr_store_add(&store, &decoded);
    assert(add_rc == 0);  /* 0 = stored successfully */

    /* Verify it's in the store */
    assert(nostr_store_count(&store) == 1);
    nostr_event_t found;
    assert(nostr_store_find(&store, evt.id, &found) == 0);
    assert(found.kind == evt.kind);
    assert(found.content_len == evt.content_len);
    assert(memcmp(found.content, evt.content, evt.content_len) == 0);

    (void)system("rm -rf /tmp/relay_send_nostr_test");

    printf("PASS\n");

    printf("\n=== Results: 9/9 passed ===\n");
    printf("relay_send_nostr CLI logic verified: serialize → tag → queue → round-trip\n");
    return 0;
}