/**
 * @file ehash_messages.c
 * @brief C implementation of EHASH message encode/decode functions.
 *
 * Port of mesh-stack/ehash-bridge/ehash_codec.py to C.
 * Implements all four L7 message types defined in ehash-spec.md:
 *   EHASH_TEMPLATE (0x10), EHASH_NONCE (0x11), EHASH_RESULT (0x12), EHASH_CREDIT (0x13).
 *
 * All multi-byte integers are little-endian.
 */

#include "ehash_messages.h"
#include <string.h>

/* ========================================================================
 *  Little-endian read/write helpers
 * ======================================================================== */

static void put_u16_le(uint8_t *buf, uint16_t v) {
    buf[0] = (uint8_t)v;
    buf[1] = (uint8_t)(v >> 8);
}

static void put_u32_le(uint8_t *buf, uint32_t v) {
    buf[0] = (uint8_t)v;
    buf[1] = (uint8_t)(v >> 8);
    buf[2] = (uint8_t)(v >> 16);
    buf[3] = (uint8_t)(v >> 24);
}

static void put_u64_le(uint8_t *buf, uint64_t v) {
    for (int i = 0; i < 8; i++)
        buf[i] = (uint8_t)(v >> (i * 8));
}

static uint16_t get_u16_le(const uint8_t *buf) {
    return (uint16_t)((uint16_t)buf[0] | ((uint16_t)buf[1] << 8));
}

static uint32_t get_u32_le(const uint8_t *buf) {
    return (uint32_t)buf[0] | ((uint32_t)buf[1] << 8) |
           ((uint32_t)buf[2] << 16) | ((uint32_t)buf[3] << 24);
}

static uint64_t get_u64_le(const uint8_t *buf) {
    uint64_t v = 0;
    for (int i = 0; i < 8; i++)
        v |= ((uint64_t)buf[i]) << (i * 8);
    return v;
}

/* ========================================================================
 *  EHASH_NONCE (0x11) — 21 bytes
 * ======================================================================== */

int ehash_nonce_encode(const ehash_nonce_t *nonce, uint8_t *buf, size_t bufsize) {
    if (!nonce || !buf) return -3;
    if (bufsize < EHASH_NONCE_SIZE) return -1;

    buf[0] = EHASH_PROTO_VERSION;
    put_u32_le(buf + 1,  nonce->job_id);
    put_u32_le(buf + 5,  nonce->worker_id);
    put_u32_le(buf + 9,  nonce->extranonce2);
    put_u32_le(buf + 13, nonce->ntime);
    put_u32_le(buf + 17, nonce->nonce);

    return EHASH_NONCE_SIZE;
}

int ehash_nonce_decode(const uint8_t *buf, size_t len, ehash_nonce_t *nonce) {
    if (!buf || !nonce) return -3;
    if (len < EHASH_NONCE_SIZE) return -1;
    if (buf[0] != EHASH_PROTO_VERSION) return -2;

    nonce->version     = buf[0];
    nonce->job_id      = get_u32_le(buf + 1);
    nonce->worker_id   = get_u32_le(buf + 5);
    nonce->extranonce2 = get_u32_le(buf + 9);
    nonce->ntime       = get_u32_le(buf + 13);
    nonce->nonce       = get_u32_le(buf + 17);

    return 0;
}

/* ========================================================================
 *  EHASH_RESULT (0x12) — 7 bytes
 * ======================================================================== */

int ehash_result_encode(const ehash_result_t *result, uint8_t *buf, size_t bufsize) {
    if (!result || !buf) return -3;
    if (bufsize < EHASH_RESULT_SIZE) return -1;

    put_u32_le(buf, result->job_id);
    buf[4] = result->accepted ? 1 : 0;
    put_u16_le(buf + 5, result->error_code);

    return EHASH_RESULT_SIZE;
}

int ehash_result_decode(const uint8_t *buf, size_t len, ehash_result_t *result) {
    if (!buf || !result) return -3;
    if (len < EHASH_RESULT_SIZE) return -1;

    result->job_id     = get_u32_le(buf);
    result->accepted   = buf[4];
    result->error_code = get_u16_le(buf + 5);

    return 0;
}

/* ========================================================================
 *  EHASH_CREDIT (0x13) — 16 bytes
 * ======================================================================== */

int ehash_credit_encode(const ehash_credit_t *credit, uint8_t *buf, size_t bufsize) {
    if (!credit || !buf) return -3;
    if (bufsize < EHASH_CREDIT_SIZE) return -1;

    put_u32_le(buf, credit->station_id);
    put_u64_le(buf + 4, credit->balance);
    put_u32_le(buf + 12, credit->block_reward_rate);

    return EHASH_CREDIT_SIZE;
}

int ehash_credit_decode(const uint8_t *buf, size_t len, ehash_credit_t *credit) {
    if (!buf || !credit) return -3;
    if (len < EHASH_CREDIT_SIZE) return -1;

    credit->station_id       = get_u32_le(buf);
    credit->balance          = get_u64_le(buf + 4);
    credit->block_reward_rate = get_u32_le(buf + 12);

    return 0;
}

/* ========================================================================
 *  EHASH_TEMPLATE (0x10) — variable length, 55–823 bytes
 * ======================================================================== */

int ehash_template_size(const ehash_template_t *tmpl) {
    if (!tmpl) return -3;
    if (!tmpl->prevhash) return -3;
    if (tmpl->coinbase1_len > EHASH_COINBASE_MAX_LEN) return -1;
    if (tmpl->coinbase2_len > EHASH_COINBASE_MAX_LEN) return -1;
    if (tmpl->merkle_branch_count > EHASH_MERKLE_BRANCH_MAX) return -1;

    return (int)(EHASH_TEMPLATE_FIXED_SIZE +
                 (size_t)tmpl->coinbase1_len +
                 (size_t)tmpl->coinbase2_len +
                 (size_t)tmpl->merkle_branch_count * EHASH_MERKLE_HASH_SIZE);
}

int ehash_template_encode(const ehash_template_t *tmpl, uint8_t *buf, size_t bufsize) {
    if (!tmpl || !buf) return -3;
    if (!tmpl->prevhash) return -3;

    /* Validate variable-length fields. */
    if (tmpl->coinbase1_len > EHASH_COINBASE_MAX_LEN) return -1;
    if (tmpl->coinbase2_len > EHASH_COINBASE_MAX_LEN) return -1;
    if (tmpl->merkle_branch_count > EHASH_MERKLE_BRANCH_MAX) return -1;

    int total = ehash_template_size(tmpl);
    if (total < 0) return total;
    if (bufsize < (size_t)total) return -1;

    size_t off = 0;

    /* Fixed header (49 bytes). */
    buf[off++] = EHASH_PROTO_VERSION;
    put_u32_le(buf + off, tmpl->job_id);       off += 4;
    memcpy(buf + off, tmpl->prevhash, 32);      off += 32;
    put_u32_le(buf + off, tmpl->btc_version);  off += 4;
    put_u32_le(buf + off, tmpl->nbits);         off += 4;
    put_u32_le(buf + off, tmpl->ntime);         off += 4;

    /* coinbase1_len + coinbase1. */
    put_u16_le(buf + off, tmpl->coinbase1_len); off += 2;
    if (tmpl->coinbase1_len > 0 && tmpl->coinbase1) {
        memcpy(buf + off, tmpl->coinbase1, tmpl->coinbase1_len);
    }
    off += tmpl->coinbase1_len;

    /* coinbase2_len + coinbase2. */
    put_u16_le(buf + off, tmpl->coinbase2_len); off += 2;
    if (tmpl->coinbase2_len > 0 && tmpl->coinbase2) {
        memcpy(buf + off, tmpl->coinbase2, tmpl->coinbase2_len);
    }
    off += tmpl->coinbase2_len;

    /* merkle_branch_count + branches. */
    buf[off++] = tmpl->merkle_branch_count;
    if (tmpl->merkle_branch_count > 0 && tmpl->merkle_branches) {
        size_t branches_len = (size_t)tmpl->merkle_branch_count * EHASH_MERKLE_HASH_SIZE;
        memcpy(buf + off, tmpl->merkle_branches, branches_len);
        off += branches_len;
    }

    /* clean_jobs. */
    buf[off++] = tmpl->clean_jobs ? 1 : 0;

    return (int)off;
}

int ehash_template_decode(const uint8_t *buf, size_t len, ehash_template_t *tmpl) {
    if (!buf || !tmpl) return -3;

    /* Minimum: fixed header (49) + coinbase1_len (2) = 51 bytes. */
    if (len < 51) return -1;

    /* Version check. */
    if (buf[0] != EHASH_PROTO_VERSION) return -2;

    size_t off = 0;

    /* Skip version byte. */
    off += 1;

    /* job_id. */
    tmpl->job_id = get_u32_le(buf + off); off += 4;

    /* prevhash — points directly into buf (no copy). */
    tmpl->prevhash = buf + off; off += 32;

    /* btc_version, nbits, ntime. */
    tmpl->btc_version = get_u32_le(buf + off); off += 4;
    tmpl->nbits       = get_u32_le(buf + off); off += 4;
    tmpl->ntime       = get_u32_le(buf + off); off += 4;

    /* coinbase1_len + coinbase1. */
    tmpl->coinbase1_len = get_u16_le(buf + off); off += 2;
    if (off + tmpl->coinbase1_len > len) return -1;
    tmpl->coinbase1 = buf + off;
    off += tmpl->coinbase1_len;

    /* coinbase2_len + coinbase2. */
    if (off + 2 > len) return -1;
    tmpl->coinbase2_len = get_u16_le(buf + off); off += 2;
    if (off + tmpl->coinbase2_len > len) return -1;
    tmpl->coinbase2 = buf + off;
    off += tmpl->coinbase2_len;

    /* merkle_branch_count + branches. */
    if (off + 1 > len) return -1;
    tmpl->merkle_branch_count = buf[off]; off += 1;
    if (tmpl->merkle_branch_count > EHASH_MERKLE_BRANCH_MAX) return -1;
    size_t branches_len = (size_t)tmpl->merkle_branch_count * EHASH_MERKLE_HASH_SIZE;
    if (off + branches_len > len) return -1;
    tmpl->merkle_branches = buf + off;
    off += branches_len;

    /* clean_jobs. */
    if (off + 1 > len) return -1;
    tmpl->clean_jobs = buf[off]; off += 1;

    return 0;
}

/* ========================================================================
 *  L7 Envelope Helpers
 * ======================================================================== */

int ehash_msg_get_type(const uint8_t *buf, size_t len) {
    if (!buf || len < 1) return -3;
    uint8_t t = buf[0];
    switch (t) {
        case EHASH_TEMPLATE:
        case EHASH_NONCE:
        case EHASH_RESULT:
        case EHASH_CREDIT:
            return t;
        default:
            return -3;
    }
}
