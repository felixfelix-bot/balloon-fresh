/*
 * nostr_store.c — Flash-backed Nostr event store for ESP32-C3
 *
 * RAM: ~10 KB (index + bloom).  Event *content* in flash via POSIX file I/O.
 *
 * On the target the caller mounts LittleFS at a path and passes that path
 * to nostr_store_init().  On the host (unit tests) a regular directory works
 * because the code uses only POSIX file calls (fopen / fwrite / fread / unlink).
 */

#include "nostr_store.h"

#include <stdio.h>
#include <string.h>
#include <sys/stat.h>   /* mkdir   */
#include <sys/types.h>
#include <unistd.h>     /* unlink  */

/* ================================================================== */
/* Bloom filter — unchanged, 64-byte RAM structure                    */
/* ================================================================== */

void nostr_bloom_init(nostr_bloom_t *bloom)
{
    memset(bloom, 0, sizeof(*bloom));
}

static uint32_t bloom_hash(const uint8_t *data, uint16_t len, uint32_t seed)
{
    uint32_t h = seed;
    for (uint16_t i = 0; i < len; i++) {
        h ^= data[i];
        h *= 0x01000193;          /* FNV prime */
    }
    return h;
}

void nostr_bloom_add(nostr_bloom_t *bloom, const uint8_t *data, uint16_t len)
{
    uint32_t h1 = bloom_hash(data, len, 0xFBA4C795);
    uint32_t h2 = bloom_hash(data, len, 0x7F4A7C2B);
    uint16_t bits = sizeof(bloom->bits) * 8;       /* 512 */
    bloom->bits[(h1 % bits) / 8] |= (uint8_t)(1u << (h1 % 8));
    bloom->bits[(h2 % bits) / 8] |= (uint8_t)(1u << (h2 % 8));
    bloom->count++;
}

bool nostr_bloom_check(const nostr_bloom_t *bloom, const uint8_t *data, uint16_t len)
{
    uint32_t h1 = bloom_hash(data, len, 0xFBA4C795);
    uint32_t h2 = bloom_hash(data, len, 0x7F4A7C2B);
    uint16_t bits = sizeof(bloom->bits) * 8;
    if (!(bloom->bits[(h1 % bits) / 8] & (1u << (h1 % 8)))) return false;
    if (!(bloom->bits[(h2 % bits) / 8] & (1u << (h2 % 8)))) return false;
    return true;
}

/* ================================================================== */
/* Serialization                                                      */
/* ================================================================== */

uint16_t nostr_event_serialize(const nostr_event_t *event, uint8_t *buf, uint16_t buf_size)
{
    /* fixed header: 32 + 32 + 64 + 4 + 2 + 2 = 136 bytes */
    uint16_t needed = 136 + event->content_len + 1;
    for (uint8_t i = 0; i < event->num_tags; i++)
        needed += (uint16_t)(2 + event->tags[i].key_len + event->tags[i].value_len);

    if (buf_size < needed) return 0;

    uint16_t pos = 0;

    memcpy(buf + pos, event->id, 32);       pos += 32;
    memcpy(buf + pos, event->pubkey, 32);   pos += 32;
    memcpy(buf + pos, event->sig, NOSTR_SIG_SIZE);  pos += NOSTR_SIG_SIZE;

    /* created_at — big-endian */
    buf[pos++] = (uint8_t)(event->created_at >> 24);
    buf[pos++] = (uint8_t)(event->created_at >> 16);
    buf[pos++] = (uint8_t)(event->created_at >> 8);
    buf[pos++] = (uint8_t)(event->created_at);

    /* kind, content_len — little-endian */
    buf[pos++] = (uint8_t)(event->kind & 0xFF);
    buf[pos++] = (uint8_t)((event->kind >> 8) & 0xFF);
    buf[pos++] = (uint8_t)(event->content_len & 0xFF);
    buf[pos++] = (uint8_t)((event->content_len >> 8) & 0xFF);

    memcpy(buf + pos, event->content, event->content_len);
    pos += event->content_len;

    buf[pos++] = event->num_tags;
    for (uint8_t i = 0; i < event->num_tags; i++) {
        buf[pos++] = event->tags[i].key_len;
        buf[pos++] = event->tags[i].value_len;
        memcpy(buf + pos, event->tags[i].key, event->tags[i].key_len);
        pos += event->tags[i].key_len;
        memcpy(buf + pos, event->tags[i].value, event->tags[i].value_len);
        pos += event->tags[i].value_len;
    }

    return pos;
}

uint16_t nostr_event_deserialize(nostr_event_t *event, const uint8_t *buf, uint16_t buf_len)
{
    if (!event || !buf) return 0;

    /* Minimum header: id(32) + pubkey(32) + sig(64) + created_at(4) + kind(2) + content_len(2) + num_tags(1) = 137 */
    if (buf_len < 137) return 0;

    uint16_t pos = 0;

    memcpy(event->id, buf + pos, 32); pos += 32;
    memcpy(event->pubkey, buf + pos, 32); pos += 32;
    memcpy(event->sig, buf + pos, NOSTR_SIG_SIZE); pos += NOSTR_SIG_SIZE;

    /* created_at: 4 bytes big-endian (inverse of serialize) */
    event->created_at = ((uint32_t)buf[pos] << 24) | ((uint32_t)buf[pos + 1] << 16) |
                        ((uint32_t)buf[pos + 2] << 8) | (uint32_t)buf[pos + 3];
    pos += 4;

    /* kind: 2 bytes little-endian (inverse of serialize) */
    event->kind = (uint16_t)(buf[pos] | (buf[pos + 1] << 8));
    pos += 2;

    /* content_len: 2 bytes little-endian (inverse of serialize) */
    event->content_len = (uint16_t)(buf[pos] | (buf[pos + 1] << 8));
    pos += 2;

    if (event->content_len > NOSTR_MAX_CONTENT) return 0;
    if (pos + event->content_len + 1 > buf_len) return 0;

    memcpy(event->content, buf + pos, event->content_len);
    pos += event->content_len;

    event->num_tags = buf[pos++];
    if (event->num_tags > NOSTR_MAX_TAGS) return 0;

    for (uint8_t i = 0; i < event->num_tags; i++) {
        if (pos + 2 > buf_len) return 0;
        event->tags[i].key_len = buf[pos++];
        event->tags[i].value_len = buf[pos++];

        if (event->tags[i].key_len > 16) return 0;
        if (event->tags[i].value_len > NOSTR_TAG_MAX_LEN) return 0;
        if (pos + event->tags[i].key_len + event->tags[i].value_len > buf_len) return 0;

        memcpy(event->tags[i].key, buf + pos, event->tags[i].key_len);
        pos += event->tags[i].key_len;
        memcpy(event->tags[i].value, buf + pos, event->tags[i].value_len);
        pos += event->tags[i].value_len;
    }

    return pos;
}

uint32_t nostr_hash_event_id(const nostr_event_t *event)
{
    uint32_t h = 0x811C9DC5;
    const uint8_t *p = (const uint8_t *)event;
    for (uint16_t i = 0; i < (uint16_t)sizeof(nostr_event_t); i++) {
        h ^= p[i];
        h *= 0x01000193;
    }
    return h;
}

/* ================================================================== */
/* Flash file helpers                                                 */
/* ================================================================== */

static void get_file_path(const nostr_store_t *store, uint32_t file_idx,
                           char *path, size_t len)
{
    snprintf(path, len, "%s/%08lx.evt", store->storage_dir, (unsigned long)file_idx);
}

static int write_event_file(const nostr_store_t *store, uint32_t file_idx,
                            const nostr_event_t *event)
{
    uint8_t buf[NOSTR_SER_BUF_SIZE];
    uint16_t slen = nostr_event_serialize(event, buf, sizeof(buf));
    if (slen == 0) return -1;

    char path[NOSTR_STORE_DIR_LEN + 16];
    get_file_path(store, file_idx, path, sizeof(path));

    FILE *f = fopen(path, "wb");
    if (!f) return -1;

    size_t written = fwrite(buf, 1, slen, f);
    fclose(f);

    return (written == slen) ? 0 : -1;
}

static int read_event_file(const nostr_store_t *store, uint32_t file_idx,
                           nostr_event_t *out)
{
    char path[NOSTR_STORE_DIR_LEN + 16];
    get_file_path(store, file_idx, path, sizeof(path));

    FILE *f = fopen(path, "rb");
    if (!f) return -1;

    uint8_t buf[NOSTR_SER_BUF_SIZE];
    size_t nread = fread(buf, 1, sizeof(buf), f);
    fclose(f);

    if (nread == 0) return -1;

    uint16_t used = nostr_event_deserialize(out, buf, (uint16_t)nread);
    return (used > 0) ? 0 : -1;
}

static void delete_event_file(const nostr_store_t *store, uint32_t file_idx)
{
    char path[NOSTR_STORE_DIR_LEN + 16];
    get_file_path(store, file_idx, path, sizeof(path));
    unlink(path);
}

/* ================================================================== */
/* Store API                                                          */
/* ================================================================== */

void nostr_store_init(nostr_store_t *store, const char *storage_dir)
{
    memset(store, 0, sizeof(*store));
    nostr_bloom_init(&store->bloom);

    if (storage_dir) {
        strncpy(store->storage_dir, storage_dir, NOSTR_STORE_DIR_LEN - 1);
    } else {
        strncpy(store->storage_dir, "/nostr_store", NOSTR_STORE_DIR_LEN - 1);
    }
    store->storage_dir[NOSTR_STORE_DIR_LEN - 1] = '\0';
    store->next_file_idx = 0;

    /* Ensure directory exists (no-op if already present) */
    mkdir(store->storage_dir, 0755);
}

int nostr_store_add(nostr_store_t *store, const nostr_event_t *event)
{
    if (!store || !event) return -1;

    /* --- duplicate check (bloom pre-filter + linear scan) --- */
    if (nostr_bloom_check(&store->bloom, event->id, NOSTR_EVENT_ID_SIZE)) {
        for (uint16_t i = 0; i < store->count; i++) {
            uint16_t idx = (store->head + i) % NOSTR_STORE_CAPACITY;
            if (memcmp(store->index[idx].id, event->id, NOSTR_EVENT_ID_SIZE) == 0)
                return 1;   /* duplicate */
        }
    }

    /* --- FIFO eviction --- */
    if (store->count >= NOSTR_STORE_CAPACITY) {
        delete_event_file(store, store->index[store->head].file_idx);
        store->head = (store->head + 1) % NOSTR_STORE_CAPACITY;
        store->count--;
    }

    /* --- write event content to flash --- */
    uint32_t file_idx = store->next_file_idx++;
    if (write_event_file(store, file_idx, event) != 0) {
        store->next_file_idx--;     /* roll back */
        return -1;
    }

    /* --- add to RAM index --- */
    uint16_t insert_idx = (store->head + store->count) % NOSTR_STORE_CAPACITY;
    memcpy(store->index[insert_idx].id, event->id, NOSTR_EVENT_ID_SIZE);
    store->index[insert_idx].file_idx = file_idx;
    store->index[insert_idx].created_at = event->created_at;
    store->count++;

    /* --- bloom filter --- */
    nostr_bloom_add(&store->bloom, event->id, NOSTR_EVENT_ID_SIZE);
    return 0;
}

int nostr_store_get(nostr_store_t *store, uint16_t index, nostr_event_t *out)
{
    if (!store || !out) return -1;
    if (index >= store->count) return -1;

    uint16_t idx = (store->head + index) % NOSTR_STORE_CAPACITY;
    return read_event_file(store, store->index[idx].file_idx, out);
}

int nostr_store_find(nostr_store_t *store, const uint8_t *id, nostr_event_t *out)
{
    if (!store || !id || !out) return -1;

    if (!nostr_bloom_check(&store->bloom, id, NOSTR_EVENT_ID_SIZE))
        return -1;

    for (uint16_t i = 0; i < store->count; i++) {
        uint16_t idx = (store->head + i) % NOSTR_STORE_CAPACITY;
        if (memcmp(store->index[idx].id, id, NOSTR_EVENT_ID_SIZE) == 0)
            return read_event_file(store, store->index[idx].file_idx, out);
    }
    return -1;
}

uint16_t nostr_store_count(const nostr_store_t *store)
{
    return store ? store->count : 0;
}

bool nostr_store_is_duplicate(const nostr_store_t *store, const uint8_t *id)
{
    if (!store || !id) return false;
    if (!nostr_bloom_check(&store->bloom, id, NOSTR_EVENT_ID_SIZE))
        return false;

    for (uint16_t i = 0; i < store->count; i++) {
        uint16_t idx = (store->head + i) % NOSTR_STORE_CAPACITY;
        if (memcmp(store->index[idx].id, id, NOSTR_EVENT_ID_SIZE) == 0)
            return true;
    }
    return false;
}
