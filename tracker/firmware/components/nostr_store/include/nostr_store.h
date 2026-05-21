#pragma once

#include <stdint.h>
#include <stdbool.h>

#define NOSTR_EVENT_ID_SIZE    32
#define NOSTR_PUBKEY_SIZE      32
#define NOSTR_SIG_SIZE         64
#define NOSTR_MAX_CONTENT      480
#define NOSTR_MAX_TAGS         8
#define NOSTR_TAG_MAX_LEN      64
#define NOSTR_STORE_CAPACITY   512

typedef struct {
    uint8_t id[NOSTR_EVENT_ID_SIZE];
    uint8_t pubkey[NOSTR_PUBKEY_SIZE];
    uint32_t created_at;
    uint16_t kind;
    uint16_t content_len;
    uint8_t content[NOSTR_MAX_CONTENT];
    uint8_t num_tags;
    struct {
        uint8_t key_len;
        uint8_t value_len;
        char key[16];
        char value[NOSTR_TAG_MAX_LEN];
    } tags[NOSTR_MAX_TAGS];
} nostr_event_t;

typedef struct {
    uint8_t bits[NOSTR_STORE_CAPACITY / 8];
    uint16_t count;
} nostr_bloom_t;

typedef struct {
    nostr_event_t events[NOSTR_STORE_CAPACITY];
    uint16_t head;
    uint16_t count;
    nostr_bloom_t bloom;
} nostr_store_t;

void nostr_bloom_init(nostr_bloom_t *bloom);
void nostr_bloom_add(nostr_bloom_t *bloom, const uint8_t *data, uint16_t len);
bool nostr_bloom_check(const nostr_bloom_t *bloom, const uint8_t *data, uint16_t len);

void nostr_store_init(nostr_store_t *store);
int nostr_store_add(nostr_store_t *store, const nostr_event_t *event);
const nostr_event_t *nostr_store_get(const nostr_store_t *store, uint16_t index);
const nostr_event_t *nostr_store_find(const nostr_store_t *store, const uint8_t *id);
uint16_t nostr_store_count(const nostr_store_t *store);
bool nostr_store_is_duplicate(const nostr_store_t *store, const uint8_t *id);

uint16_t nostr_event_serialize(const nostr_event_t *event, uint8_t *buf, uint16_t buf_size);
uint16_t nostr_event_deserialize(nostr_event_t *event, const uint8_t *buf, uint16_t buf_len);
uint32_t nostr_hash_event_id(const nostr_event_t *event);
