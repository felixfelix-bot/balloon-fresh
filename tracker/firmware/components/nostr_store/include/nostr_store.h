#pragma once

#include <stdint.h>
#include <stdbool.h>

#define NOSTR_EVENT_ID_SIZE    32
#define NOSTR_PUBKEY_SIZE      32
#define NOSTR_SIG_SIZE         64
#define NOSTR_MAX_CONTENT      480
#define NOSTR_MAX_TAGS         8
#define NOSTR_TAG_MAX_LEN      64

/*
 * Flash-backed event store — ADR-024 compliant.
 *
 * RAM footprint:
 *   index[256] × 40 bytes = 10 240 bytes
 *   bloom  64 + 2         =     66 bytes
 *   misc fields           =    ~72 bytes
 *   total                 ≈  10.4 KB  (fits C3's 258 KB heap)
 *
 * Event *content* lives in flash (LittleFS on target, POSIX on host).
 * Each event is serialized with nostr_event_serialize() into a file
 * named <storage_dir>/<file_idx>.evt.
 */
#define NOSTR_STORE_CAPACITY   256
#define NOSTR_BLOOM_SIZE       64    /* 512-bit bloom filter */
#define NOSTR_STORE_DIR_LEN    64
#define NOSTR_SER_BUF_SIZE     1024  /* max serialized event size */

/* ------------------------------------------------------------------ */
/* Event structure (unchanged — lives in caller's RAM or flash file)  */
/* ------------------------------------------------------------------ */

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

/* ------------------------------------------------------------------ */
/* Bloom filter (64 bytes — RAM only)                                 */
/* ------------------------------------------------------------------ */

typedef struct {
    uint8_t bits[NOSTR_BLOOM_SIZE];
    uint16_t count;
} nostr_bloom_t;

/* ------------------------------------------------------------------ */
/* RAM index entry — 40 bytes packed                                  */
/* ------------------------------------------------------------------ */

typedef struct __attribute__((packed)) {
    uint8_t  id[NOSTR_EVENT_ID_SIZE];  /* 32 bytes — event ID hash   */
    uint32_t file_idx;                 /* 4 bytes  — flash file index */
    uint32_t created_at;              /* 4 bytes  — timestamp (FIFO) */
} nostr_index_entry_t;                /* 40 bytes total              */

/* ------------------------------------------------------------------ */
/* Store — 10 KB index in RAM, event content in flash                */
/* ------------------------------------------------------------------ */

typedef struct {
    nostr_index_entry_t index[NOSTR_STORE_CAPACITY]; /* 10 KB     */
    nostr_bloom_t bloom;                              /* 66 bytes  */
    uint16_t head;
    uint16_t count;
    uint32_t next_file_idx;
    char storage_dir[NOSTR_STORE_DIR_LEN];
} nostr_store_t;

/* ------------------------------------------------------------------ */
/* Bloom filter API                                                   */
/* ------------------------------------------------------------------ */

void nostr_bloom_init(nostr_bloom_t *bloom);
void nostr_bloom_add(nostr_bloom_t *bloom, const uint8_t *data, uint16_t len);
bool nostr_bloom_check(const nostr_bloom_t *bloom, const uint8_t *data, uint16_t len);

/* ------------------------------------------------------------------ */
/* Store API                                                          */
/*                                                                    */
/* init:  store is zeroed, bloom reset, storage_dir recorded.         */
/*        Caller ensures the directory exists (LittleFS mount or      */
/*        host mkdir).                                                */
/* add:   0 = stored, 1 = duplicate (skipped), -1 = error             */
/* get:   0 = loaded into *out, -1 = index OOB or read error         */
/* find:  0 = found and loaded, -1 = not found                        */
/* ------------------------------------------------------------------ */

void     nostr_store_init(nostr_store_t *store, const char *storage_dir);
int      nostr_store_add(nostr_store_t *store, const nostr_event_t *event);
int      nostr_store_get(nostr_store_t *store, uint16_t index, nostr_event_t *out);
int      nostr_store_find(nostr_store_t *store, const uint8_t *id, nostr_event_t *out);
uint16_t nostr_store_count(const nostr_store_t *store);
bool     nostr_store_is_duplicate(const nostr_store_t *store, const uint8_t *id);

/* ------------------------------------------------------------------ */
/* Serialization (binary — matches flash file format)                 */
/*                                                                    */
/* Layout:                                                            */
/*   [32 id][32 pubkey][4 created_at BE][2 kind LE][2 clen LE]       */
/*   [clen bytes content][1 num_tags]                                 */
/*   per tag: [1 key_len][1 val_len][key bytes][val bytes]            */
/*                                                                    */
/* Returns bytes used, or 0 on error / buffer too small.              */
/* ------------------------------------------------------------------ */

uint16_t nostr_event_serialize(const nostr_event_t *event, uint8_t *buf, uint16_t buf_size);
uint16_t nostr_event_deserialize(nostr_event_t *event, const uint8_t *buf, uint16_t buf_len);

/* FNV-1a hash over the event struct (for quick comparisons) */
uint32_t nostr_hash_event_id(const nostr_event_t *event);
