#include "nostr_store.h"
#include <string.h>

void nostr_bloom_init(nostr_bloom_t *bloom) {
    memset(bloom, 0, sizeof(*bloom));
    bloom->count = 0;
}

static uint32_t bloom_hash(const uint8_t *data, uint16_t len, uint32_t seed) {
    uint32_t h = seed;
    for (uint16_t i = 0; i < len; i++) {
        h ^= data[i];
        h *= 0x01000193;
    }
    return h;
}

void nostr_bloom_add(nostr_bloom_t *bloom, const uint8_t *data, uint16_t len) {
    uint32_t h1 = bloom_hash(data, len, 0xFBA4C795);
    uint32_t h2 = bloom_hash(data, len, 0x7F4A7C2B);
    uint16_t bits = sizeof(bloom->bits) * 8;
    bloom->bits[h1 % bits / 8] |= (1 << (h1 % 8));
    bloom->bits[h2 % bits / 8] |= (1 << (h2 % 8));
    bloom->count++;
}

bool nostr_bloom_check(const nostr_bloom_t *bloom, const uint8_t *data, uint16_t len) {
    uint32_t h1 = bloom_hash(data, len, 0xFBA4C795);
    uint32_t h2 = bloom_hash(data, len, 0x7F4A7C2B);
    uint16_t bits = sizeof(bloom->bits) * 8;
    if (!(bloom->bits[h1 % bits / 8] & (1 << (h1 % 8)))) return false;
    if (!(bloom->bits[h2 % bits / 8] & (1 << (h2 % 8)))) return false;
    return true;
}

void nostr_store_init(nostr_store_t *store) {
    memset(store, 0, sizeof(*store));
    nostr_bloom_init(&store->bloom);
}

int nostr_store_add(nostr_store_t *store, const nostr_event_t *event) {
    if (!store || !event) return -1;

    if (nostr_bloom_check(&store->bloom, event->id, NOSTR_EVENT_ID_SIZE)) {
        for (uint16_t i = 0; i < store->count; i++) {
            uint16_t idx = (store->head + i) % NOSTR_STORE_CAPACITY;
            if (memcmp(store->events[idx].id, event->id, NOSTR_EVENT_ID_SIZE) == 0) {
                return 1;
            }
        }
    }

    if (store->count >= NOSTR_STORE_CAPACITY) {
        store->head = (store->head + 1) % NOSTR_STORE_CAPACITY;
        store->count--;
    }

    uint16_t insert_idx = (store->head + store->count) % NOSTR_STORE_CAPACITY;
    memcpy(&store->events[insert_idx], event, sizeof(nostr_event_t));
    store->count++;

    nostr_bloom_add(&store->bloom, event->id, NOSTR_EVENT_ID_SIZE);
    return 0;
}

const nostr_event_t *nostr_store_get(const nostr_store_t *store, uint16_t index) {
    if (index >= store->count) return NULL;
    uint16_t idx = (store->head + index) % NOSTR_STORE_CAPACITY;
    return &store->events[idx];
}

const nostr_event_t *nostr_store_find(const nostr_store_t *store, const uint8_t *id) {
    if (!nostr_bloom_check(&store->bloom, id, NOSTR_EVENT_ID_SIZE)) return NULL;
    for (uint16_t i = 0; i < store->count; i++) {
        uint16_t idx = (store->head + i) % NOSTR_STORE_CAPACITY;
        if (memcmp(store->events[idx].id, id, NOSTR_EVENT_ID_SIZE) == 0) {
            return &store->events[idx];
        }
    }
    return NULL;
}

uint16_t nostr_store_count(const nostr_store_t *store) {
    return store->count;
}

bool nostr_store_is_duplicate(const nostr_store_t *store, const uint8_t *id) {
    return nostr_store_find(store, id) != NULL;
}

uint16_t nostr_event_serialize(const nostr_event_t *event, uint8_t *buf, uint16_t buf_size) {
    uint16_t needed = 32 + 32 + 4 + 2 + 2 + event->content_len + 1 + event->num_tags * (1 + 1 + 16 + 64);
    if (buf_size < needed) return 0;

    uint16_t pos = 0;
    memcpy(buf + pos, event->id, 32); pos += 32;
    memcpy(buf + pos, event->pubkey, 32); pos += 32;
    buf[pos++] = (event->created_at >> 24) & 0xFF;
    buf[pos++] = (event->created_at >> 16) & 0xFF;
    buf[pos++] = (event->created_at >> 8) & 0xFF;
    buf[pos++] = event->created_at & 0xFF;
    buf[pos++] = event->kind & 0xFF;
    buf[pos++] = (event->kind >> 8) & 0xFF;
    buf[pos++] = event->content_len & 0xFF;
    buf[pos++] = (event->content_len >> 8) & 0xFF;
    memcpy(buf + pos, event->content, event->content_len); pos += event->content_len;
    buf[pos++] = event->num_tags;
    for (uint8_t i = 0; i < event->num_tags; i++) {
        buf[pos++] = event->tags[i].key_len;
        buf[pos++] = event->tags[i].value_len;
        memcpy(buf + pos, event->tags[i].key, event->tags[i].key_len); pos += event->tags[i].key_len;
        memcpy(buf + pos, event->tags[i].value, event->tags[i].value_len); pos += event->tags[i].value_len;
    }
    return pos;
}

uint32_t nostr_hash_event_id(const nostr_event_t *event) {
    uint32_t h = 0x811C9DC5;
    const uint8_t *p = (const uint8_t *)event;
    for (uint16_t i = 0; i < sizeof(nostr_event_t); i++) {
        h ^= p[i];
        h *= 0x01000193;
    }
    return h;
}
