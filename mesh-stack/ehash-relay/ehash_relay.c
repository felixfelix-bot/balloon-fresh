/**
 * @file ehash_relay.c
 * @brief Phase C — Balloon-side e-hash relay core logic.
 *
 * Implements: template relay (downlink), nonce relay (uplink),
 * per-nonce credit issuance (D10), credit gate (D8), TTL tracking (D9).
 *
 * The balloon NEVER hashes (D1). It is a pure transport node.
 *
 * Build: part of ESP-IDF component (CMakeLists.txt) or gcc host tests.
 */

#include "ehash_relay.h"
#include "ehash_crypto.h"

#include <string.h>

/* ========================================================================
 *  Internal Helpers
 * ======================================================================== */

/** Write a little-endian uint32 into a buffer at offset. */
static void put_u32_le(uint8_t *buf, uint32_t val) {
    buf[0] = (uint8_t)(val);
    buf[1] = (uint8_t)(val >> 8);
    buf[2] = (uint8_t)(val >> 16);
    buf[3] = (uint8_t)(val >> 24);
}

/* ========================================================================
 *  Initialization
 * ======================================================================== */

void ehash_relay_init(ehash_relay_t *r,
                       ehash_radio_tx_fn         broadcast,
                       ehash_radio_tx_unicast_fn unicast,
                       ehash_upstream_tx_fn      upstream,
                       void                     *cb_ctx)
{
    memset(r, 0, sizeof(*r));
    r->radio_broadcast    = broadcast;
    r->radio_unicast      = unicast;
    r->upstream_tx        = upstream;
    r->cb_ctx             = cb_ctx;
    r->ttl_window_s       = EHASH_RELAY_DEFAULT_TTL_S;
    r->upstream_connected = false;
    r->key_set            = false;
}

/* ========================================================================
 *  Credit Table (D10)
 * ======================================================================== */

int ehash_relay_credit_find_or_create(ehash_relay_t *r, uint32_t station_id) {
    /* Check if station already exists. */
    for (int i = 0; i < EHASH_RELAY_MAX_STATIONS; i++) {
        if (r->credits[i].active && r->credits[i].station_id == station_id)
            return i;
    }
    /* Find first free slot. */
    for (int i = 0; i < EHASH_RELAY_MAX_STATIONS; i++) {
        if (!r->credits[i].active) {
            r->credits[i].station_id    = station_id;
            r->credits[i].balance       = 0;
            r->credits[i].reward_rate   = EHASH_RELAY_DEFAULT_REWARD_SATS;
            r->credits[i].nonces_accepted = 0;
            r->credits[i].nonces_rejected = 0;
            r->credits[i].active        = true;
            return i;
        }
    }
    return -1;  /* table full */
}

const ehash_credit_entry_t *ehash_relay_get_credit(const ehash_relay_t *r,
                                                     uint32_t station_id) {
    for (int i = 0; i < EHASH_RELAY_MAX_STATIONS; i++) {
        if (r->credits[i].active && r->credits[i].station_id == station_id)
            return &r->credits[i];
    }
    return NULL;
}

bool ehash_relay_has_credit(const ehash_relay_t *r, uint32_t station_id) {
    const ehash_credit_entry_t *c = ehash_relay_get_credit(r, station_id);
    return (c != NULL && c->balance > 0);
}

int ehash_relay_credit_set_balance(ehash_relay_t *r,
                                    uint32_t station_id,
                                    uint64_t balance,
                                    uint32_t reward_rate)
{
    int idx = ehash_relay_credit_find_or_create(r, station_id);
    if (idx < 0) return -1;
    r->credits[idx].balance     = balance;
    r->credits[idx].reward_rate = reward_rate;
    return 0;
}

/* ========================================================================
 *  Credit Issuance (D10: per-nonce e-hash issuance)
 * ======================================================================== */

int ehash_relay_issue_credit(ehash_relay_t *r, uint32_t station_id) {
    int idx = ehash_relay_credit_find_or_create(r, station_id);
    if (idx < 0) return -1;

    ehash_credit_entry_t *entry = &r->credits[idx];

    /* Increment balance by reward rate. */
    entry->balance += entry->reward_rate;

    /* Build EHASH_CREDIT message to send to the station. */
    ehash_credit_t credit;
    credit.station_id       = station_id;
    credit.balance          = entry->balance;
    credit.block_reward_rate = entry->reward_rate;

    /* Encode into wire format. */
    uint8_t payload[EHASH_CREDIT_SIZE];
    int enc = ehash_credit_encode(&credit, payload, sizeof(payload));
    if (enc < 0) return enc;

    /* Wrap in L7 envelope: type byte + payload. */
    uint8_t envelope[1 + EHASH_CREDIT_SIZE];
    envelope[0] = (uint8_t)EHASH_CREDIT;
    memcpy(envelope + 1, payload, EHASH_CREDIT_SIZE);

    /* Send via unicast radio callback. */
    if (r->radio_unicast) {
        int rc = r->radio_unicast(station_id, envelope, sizeof(envelope), r->cb_ctx);
        if (rc < 0) return rc;
    }

    r->credits_issued++;
    return 0;
}

/* ========================================================================
 *  Template Relay (downlink)
 * ======================================================================== */

int ehash_relay_on_template(ehash_relay_t *r,
                             const ehash_template_t *tmpl,
                             uint32_t now)
{
    if (!r || !tmpl) return -3;

    /* 1. Encode template into binary EHASH_TEMPLATE payload. */
    uint8_t payload[EHASH_TEMPLATE_MAX_SIZE];
    int enc = ehash_template_encode(tmpl, payload, sizeof(payload));
    if (enc < 0) return enc;

    /* 2. Wrap in L7 envelope: type byte + payload. */
    uint8_t envelope[1 + EHASH_TEMPLATE_MAX_SIZE];
    envelope[0] = (uint8_t)EHASH_TEMPLATE;
    memcpy(envelope + 1, payload, (size_t)enc);
    size_t env_len = 1 + (size_t)enc;

    /* 3. Encrypt the payload (D8: per-session key).
     *    Encrypt bytes [1..env_len) — the type byte stays plaintext so
     *    the receiver knows this is EHASH_TEMPLATE before decrypting. */
    if (r->key_set) {
        ehash_crypto_xor(envelope + 1, env_len - 1, r->session_key);
    }

    /* 4. Broadcast via radio. */
    if (r->radio_broadcast) {
        int rc = r->radio_broadcast(envelope, env_len, r->cb_ctx);
        if (rc < 0) return rc;
    }

    /* 5. Update TTL tracking (D9). */
    r->current_template.job_id      = tmpl->job_id;
    r->current_template.received_ts = now;
    r->current_template.expired     = false;
    r->upstream_connected           = true;
    r->templates_relayed++;

    return (int)env_len;
}

bool ehash_relay_template_expired(const ehash_relay_t *r, uint32_t now) {
    if (!r->upstream_connected) return true;
    if (r->current_template.received_ts == 0) return true;
    uint32_t elapsed = now - r->current_template.received_ts;
    return elapsed >= r->ttl_window_s;
}

/* ========================================================================
 *  Nonce Relay (uplink)
 * ======================================================================== */

int ehash_relay_on_nonce(ehash_relay_t *r,
                          const uint8_t *buf, size_t len)
{
    if (!r || !buf || len < 1) return -3;

    /* Expect L7 envelope: type byte (0x11) + 21-byte NONCE payload. */
    if (buf[0] != (uint8_t)EHASH_NONCE) return -3;
    if (len < 1 + EHASH_NONCE_SIZE) return -1;

    /* 1. Decode the nonce. */
    ehash_nonce_t nonce;
    int rc = ehash_nonce_decode(buf + 1, len - 1, &nonce);
    if (rc < 0) return rc;

    /* 2. Forward upstream to e-hash proxy. */
    if (r->upstream_tx) {
        int urc = r->upstream_tx(&nonce, r->cb_ctx);
        if (urc < 0) return urc;
    }

    /* 3. Issue per-nonce e-hash credit to the miner (D10). */
    int crc = ehash_relay_issue_credit(r, nonce.worker_id);
    if (crc < 0) {
        /* Credit issuance failure is non-fatal — nonce still forwarded. */
    }

    /* 4. Update stats. */
    r->nonces_relayed++;

    /* Track acceptance in credit table. */
    int idx = ehash_relay_credit_find_or_create(r, nonce.worker_id);
    if (idx >= 0) {
        r->credits[idx].nonces_accepted++;
    }

    return 0;
}

/* ========================================================================
 *  TTL / Upstream Status (D9)
 * ======================================================================== */

void ehash_relay_set_upstream(ehash_relay_t *r, bool connected) {
    if (!r) return;
    r->upstream_connected = connected;
    if (!connected) {
        r->current_template.expired = true;
    }
}

void ehash_relay_set_ttl(ehash_relay_t *r, uint32_t ttl_s) {
    if (!r) return;
    r->ttl_window_s = ttl_s;
}
