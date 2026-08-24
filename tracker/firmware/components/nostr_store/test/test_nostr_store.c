/*
 * test_nostr_store.c — Unit tests for the flash-backed Nostr store.
 *
 * Build & run on host:
 *   cc -Wall -Wextra -O2 -I include -o test_nostr_store \
 *      nostr_store.c test/test_nostr_store.c && ./test_nostr_store
 *
 * The store writes serialized events to files in /tmp/nostr_test.
 * POSIX file I/O works identically on host and on ESP-IDF (LittleFS VFS),
 * so these tests exercise the real code path.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <sys/stat.h>
#include "nostr_store.h"

#define TEST_DIR "/tmp/nostr_test"

/* ------------------------------------------------------------------ */
/* Helpers                                                            */
/* ------------------------------------------------------------------ */

static void clean_test_dir(void)
{
    int rc = system("rm -rf " TEST_DIR);
    (void)rc;
}

static void make_event(nostr_event_t *evt, uint8_t id_byte, const char *content)
{
    memset(evt, 0, sizeof(*evt));
    memset(evt->id, id_byte, NOSTR_EVENT_ID_SIZE);
    memset(evt->pubkey, 0xAA, NOSTR_PUBKEY_SIZE);
    /* Fill sig with a recognizable pattern so roundtrip can verify byte-exact */
    for (int i = 0; i < NOSTR_SIG_SIZE; i++)
        evt->sig[i] = (uint8_t)(id_byte ^ (i & 0xFF));
    evt->created_at = 1000 + id_byte;
    evt->kind = 1;
    evt->content_len = (uint16_t)strlen(content);
    memcpy(evt->content, content, evt->content_len);
    evt->num_tags = 0;
}

/* ================================================================== */
/* Tests                                                              */
/* ================================================================== */

int main(void)
{
    printf("\n=== Nostr Store Tests (flash-backed) ===\n\n");

    /* ---- struct sizes (flyability check) ---- */
    printf("sizeof(nostr_event_t)     = %zu bytes\n", sizeof(nostr_event_t));
    printf("sizeof(nostr_index_entry) = %zu bytes\n", sizeof(nostr_index_entry_t));
    printf("sizeof(nostr_store_t)     = %zu bytes  (%.1f KB)\n",
           sizeof(nostr_store_t), (double)sizeof(nostr_store_t) / 1024.0);
    printf("  index: %u × %zu = %zu bytes\n",
           NOSTR_STORE_CAPACITY, sizeof(nostr_index_entry_t),
           (size_t)NOSTR_STORE_CAPACITY * sizeof(nostr_index_entry_t));
    printf("  bloom: %zu bytes\n\n", sizeof(nostr_bloom_t));

    assert(sizeof(nostr_index_entry_t) == 40);

    /* ---- TEST 1: bloom filter ---- */
    printf("TEST 1: bloom filter add/check... ");
    nostr_bloom_t bloom;
    nostr_bloom_init(&bloom);
    uint8_t key1[4] = {0x01, 0x02, 0x03, 0x04};
    uint8_t key2[4] = {0x05, 0x06, 0x07, 0x08};
    uint8_t key3[4] = {0xFF, 0xFE, 0xFD, 0xFC};
    nostr_bloom_add(&bloom, key1, 4);
    nostr_bloom_add(&bloom, key2, 4);
    assert(nostr_bloom_check(&bloom, key1, 4));
    assert(nostr_bloom_check(&bloom, key2, 4));
    assert(!nostr_bloom_check(&bloom, key3, 4));
    printf("PASS\n");

    /* ---- TEST 2: store add + retrieve from flash ---- */
    printf("TEST 2: store add + retrieve (flash)... ");
    clean_test_dir();
    nostr_store_t *store = malloc(sizeof(nostr_store_t));
    assert(store);
    nostr_store_init(store, TEST_DIR);

    nostr_event_t evt;
    make_event(&evt, 0x42, "Hello from balloon!");
    int r = nostr_store_add(store, &evt);
    assert(r == 0);
    assert(nostr_store_count(store) == 1);

    nostr_event_t got;
    r = nostr_store_get(store, 0, &got);
    assert(r == 0);
    assert(got.id[0] == 0x42);
    assert(got.created_at == 1000 + 0x42);
    assert(got.sig[0] == (uint8_t)(0x42 ^ 0));
    assert(got.sig[63] == (uint8_t)(0x42 ^ 63));
    assert(got.kind == 1);
    assert(memcmp(got.content, "Hello from balloon!", 19) == 0);
    assert(got.content_len == 19);
    printf("PASS\n");

    /* ---- TEST 3: duplicate detection ---- */
    printf("TEST 3: duplicate detection... ");
    r = nostr_store_add(store, &evt);     /* same event again */
    assert(r == 1);
    assert(nostr_store_count(store) == 1);
    assert(nostr_store_is_duplicate(store, evt.id));
    uint8_t fake_id[32] = {0};
    assert(!nostr_store_is_duplicate(store, fake_id));
    printf("PASS\n");

    /* ---- TEST 4: find by ID (reads from flash) ---- */
    printf("TEST 4: find by ID... ");
    nostr_event_t found;
    r = nostr_store_find(store, evt.id, &found);
    assert(r == 0);
    assert(found.id[0] == 0x42);
    assert(memcmp(found.content, "Hello from balloon!", 19) == 0);

    r = nostr_store_find(store, fake_id, &found);
    assert(r == -1);
    printf("PASS\n");

    /* ---- TEST 5: FIFO overflow (256 capacity) ---- */
    printf("TEST 5: FIFO overflow (capacity=%d)... ", NOSTR_STORE_CAPACITY);
    clean_test_dir();
    nostr_store_init(store, TEST_DIR);
    for (uint16_t i = 0; i < NOSTR_STORE_CAPACITY + 10; i++) {
        make_event(&evt, (uint8_t)(i & 0xFF), "test");
        /* make each ID unique across 256+ entries */
        evt.id[1] = (uint8_t)((i >> 8) & 0xFF);
        evt.id[2] = (uint8_t)(i & 0xFF);
        r = nostr_store_add(store, &evt);
        assert(r == 0);
    }
    assert(nostr_store_count(store) == NOSTR_STORE_CAPACITY);
    /* oldest 10 should be evicted; verify we can still read from flash */
    r = nostr_store_get(store, 0, &got);
    assert(r == 0);
    printf("PASS\n");

    /* ---- TEST 6: serialization roundtrip ---- */
    printf("TEST 6: serialization roundtrip... ");
    make_event(&evt, 0x55, "Binary test");
    evt.kind = 30023;
    evt.created_at = 1700000000;
    evt.tags[0].key_len = 1;
    memcpy(evt.tags[0].key, "L", 1);
    evt.tags[0].value_len = 17;
    memcpy(evt.tags[0].value, "balloon-telemetry", 17);
    evt.num_tags = 1;

    uint8_t buf[NOSTR_SER_BUF_SIZE];
    uint16_t slen = nostr_event_serialize(&evt, buf, sizeof(buf));
    assert(slen > 0);

    /* Deserialize back and verify every field matches the original */
    nostr_event_t evt2;
    memset(&evt2, 0xFF, sizeof(evt2));  /* poison to catch missing writes */
    uint16_t dlen = nostr_event_deserialize(&evt2, buf, slen);
    assert(dlen == slen);
    assert(memcmp(evt2.id, evt.id, 32) == 0);
    assert(memcmp(evt2.pubkey, evt.pubkey, 32) == 0);
    assert(memcmp(evt2.sig, evt.sig, NOSTR_SIG_SIZE) == 0);
    assert(evt2.created_at == evt.created_at);
    assert(evt2.kind == evt.kind);
    assert(evt2.content_len == evt.content_len);
    assert(memcmp(evt2.content, evt.content, evt.content_len) == 0);
    assert(evt2.num_tags == evt.num_tags);
    assert(evt2.tags[0].key_len == evt.tags[0].key_len);
    assert(evt2.tags[0].value_len == evt.tags[0].value_len);
    assert(memcmp(evt2.tags[0].key, evt.tags[0].key, evt.tags[0].key_len) == 0);
    assert(memcmp(evt2.tags[0].value, evt.tags[0].value, evt.tags[0].value_len) == 0);

    assert(nostr_hash_event_id(&evt) != 0);
    printf("PASS (%d bytes roundtripped)\n", slen);

    /* ---- TEST 7: multiple events + dedup + flash read-back ---- */
    printf("TEST 7: multiple events with dedup... ");
    clean_test_dir();
    nostr_store_init(store, TEST_DIR);

    nostr_event_t events[5];
    for (int i = 0; i < 5; i++) {
        make_event(&events[i], (uint8_t)(i + 1), "event");
        r = nostr_store_add(store, &events[i]);
        assert(r == 0);
    }
    assert(nostr_store_count(store) == 5);

    /* re-add #3 → should be duplicate */
    r = nostr_store_add(store, &events[2]);
    assert(r == 1);
    assert(nostr_store_count(store) == 5);

    /* read all back from flash and verify */
    for (int i = 0; i < 5; i++) {
        r = nostr_store_get(store, (uint16_t)i, &got);
        assert(r == 0);
        assert(got.id[0] == (uint8_t)(i + 1));
        assert(memcmp(got.content, "event", 5) == 0);
    }
    printf("PASS\n");

    /* ---- cleanup ---- */
    free(store);
    clean_test_dir();

    printf("\n=== Results: 7/7 passed ===\n");
    return 0;
}
