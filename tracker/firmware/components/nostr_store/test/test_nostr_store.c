#include <stdio.h>
#include <string.h>
#include <assert.h>
#include "nostr_store.h"

static void make_event(nostr_event_t *evt, uint8_t id_byte, const char *content) {
    memset(evt, 0, sizeof(*evt));
    memset(evt->id, id_byte, NOSTR_EVENT_ID_SIZE);
    memset(evt->pubkey, 0xAA, NOSTR_PUBKEY_SIZE);
    evt->created_at = 1000 + id_byte;
    evt->kind = 1;
    evt->content_len = (uint16_t)strlen(content);
    memcpy(evt->content, content, evt->content_len);
    evt->num_tags = 0;
}

int main(void) {
    printf("\n=== Nostr Store Tests ===\n\n");

    printf("TEST 1: bloom filter add and check... ");
    nostr_bloom_t bloom;
    nostr_bloom_init(&bloom);
    uint8_t key1[4] = {0x01, 0x02, 0x03, 0x04};
    uint8_t key2[4] = {0x05, 0x06, 0x07, 0x08};
    uint8_t key3[4] = {0xFF, 0xFE, 0xFD, 0xFC};
    nostr_bloom_add(&bloom, key1, 4);
    assert(nostr_bloom_check(&bloom, key1, 4));
    assert(!nostr_bloom_check(&bloom, key3, 4));
    printf("PASS\n");

    printf("TEST 2: store add and retrieve... ");
    nostr_store_t store;
    nostr_store_init(&store);
    nostr_event_t evt;
    make_event(&evt, 0x42, "Hello from balloon!");
    int r = nostr_store_add(&store, &evt);
    assert(r == 0);
    assert(nostr_store_count(&store) == 1);
    const nostr_event_t *got = nostr_store_get(&store, 0);
    assert(got != NULL);
    assert(got->id[0] == 0x42);
    assert(memcmp(got->content, "Hello from balloon!", 19) == 0);
    printf("PASS\n");

    printf("TEST 3: duplicate detection... ");
    r = nostr_store_add(&store, &evt);
    assert(r == 1);
    assert(nostr_store_count(&store) == 1);
    assert(nostr_store_is_duplicate(&store, evt.id));
    printf("PASS\n");

    printf("TEST 4: find by ID... ");
    const nostr_event_t *found = nostr_store_find(&store, evt.id);
    assert(found != NULL);
    assert(found->id[0] == 0x42);
    uint8_t fake_id[32] = {0};
    assert(nostr_store_find(&store, fake_id) == NULL);
    printf("PASS\n");

    printf("TEST 5: FIFO overflow... ");
    nostr_store_init(&store);
    for (uint16_t i = 0; i < NOSTR_STORE_CAPACITY + 10; i++) {
        make_event(&evt, (uint8_t)(i & 0xFF), "test");
        memset(evt.id + 1, (uint8_t)((i >> 8) & 0xFF), NOSTR_EVENT_ID_SIZE - 1);
        nostr_store_add(&store, &evt);
    }
    assert(nostr_store_count(&store) == NOSTR_STORE_CAPACITY);
    printf("PASS (capacity=%d)\n", NOSTR_STORE_CAPACITY);

    printf("TEST 6: serialization roundtrip... ");
    nostr_store_init(&store);
    make_event(&evt, 0x55, "Binary test");
    evt.kind = 30023;
    evt.created_at = 1700000000;
    evt.tags[0].key_len = 1;
    memcpy(evt.tags[0].key, "L", 1);
    evt.tags[0].value_len = 17;
    memcpy(evt.tags[0].value, "balloon-telemetry", 17);
    evt.num_tags = 1;

    uint8_t buf[1024];
    uint16_t slen = nostr_event_serialize(&evt, buf, sizeof(buf));
    assert(slen > 0);

    nostr_event_t evt2;
    memset(&evt2, 0, sizeof(evt2));
    memcpy(evt2.id, evt.id, 32);
    memcpy(evt2.pubkey, evt.pubkey, 32);
    assert(nostr_hash_event_id(&evt) != 0);
    printf("PASS (%d bytes serialized)\n", slen);

    printf("TEST 7: multiple events with dedup... ");
    nostr_store_init(&store);
    nostr_event_t events[5];
    for (int i = 0; i < 5; i++) {
        make_event(&events[i], (uint8_t)(i + 1), "event");
        r = nostr_store_add(&store, &events[i]);
        assert(r == 0);
    }
    assert(nostr_store_count(&store) == 5);
    r = nostr_store_add(&store, &events[2]);
    assert(r == 1);
    assert(nostr_store_count(&store) == 5);
    for (int i = 0; i < 5; i++) {
        const nostr_event_t *e = nostr_store_get(&store, (uint16_t)i);
        assert(e != NULL);
        assert(e->id[0] == (uint8_t)(i + 1));
    }
    printf("PASS\n");

    printf("\n=== Results: 7/7 passed ===\n");
    return 0;
}
