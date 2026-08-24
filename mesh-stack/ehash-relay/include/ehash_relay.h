/**
 * @file ehash_relay.h
 * @brief Phase C — Balloon-side e-hash relay module (ADR-025)
 *
 * This component runs ON the balloon ESP32-C3. It is a pure L7 transport
 * node: template relay (downlink), nonce relay (uplink), per-nonce e-hash
 * credit issuance (D10), template encryption (D8), and TTL tracking (D9).
 *
 * The balloon NEVER hashes (D1). It fragments/forwards binary messages
 * defined in mesh-stack/protocol/ehash_messages.h.
 *
 * Radio layer is abstracted behind callbacks (ehash_radio_tx/rx) so the
 * component builds on both ESP-IDF (with the real LR2021 driver) and the
 * host (for unit tests with gcc).
 *
 * Architecture:
 *
 *   Upstream (e-hash proxy)               Radio (LR2021, downlink/uplink)
 *   ┌─────────────────────┐              ┌──────────────────────────┐
 *   │  mock TCP / stratum │              │  ehash_radio_tx()        │
 *   │  mining.notify      │──► relay ──► │  (broadcast templates)   │
 *   │                     │              │                          │
 *   │  receives nonces    │◄── relay ◄── │  ehash_radio_rx()        │
 *   └─────────────────────┘              │  (receive nonces)        │
 *                                        └──────────────────────────┘
 *
 * Related:
 *   - ADR-025 §Phase C
 *   - mesh-stack/protocol/ehash_messages.h  (binary structs — reused)
 *   - mesh-stack/protocol/ehash-spec.md     (wire format)
 *   - docs/adr/adr-e-hash-relay-DECISIONS.md (D1-D10)
 */

#ifndef EHASH_RELAY_H
#define EHASH_RELAY_H

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

/* Re-export the protocol message types and structs from ehash_messages.h.
 * The relay reuses the packed structs — it does NOT redefine wire formats.
 * We include the header directly so callers get both the structs and the
 * relay API in one place. */
#include "ehash_messages.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ========================================================================
 *  Configuration Constants
 * ======================================================================== */

/** Maximum number of tracked ground stations (credit table size). */
#define EHASH_RELAY_MAX_STATIONS   16

/** Default template TTL in seconds (D9: 15 minutes). */
#define EHASH_RELAY_DEFAULT_TTL_S  (15u * 60u)

/** Default reward rate per accepted nonce (satoshis/share). */
#define EHASH_RELAY_DEFAULT_REWARD_SATS  500u

/** AES-128 key size (16 bytes). Used for per-session encryption (D8). */
#define EHASH_RELAY_KEY_SIZE  16

/** Maximum L7 envelope payload the relay handles (type + TEMPLATE_MAX). */
#define EHASH_RELAY_MAX_PAYLOAD  EHASH_MSG_MAX_SIZE

/* ========================================================================
 *  Types
 * ======================================================================== */

/** Per-station credit record. */
typedef struct {
    uint32_t  station_id;        /**< Worker ID (0 = unused slot). */
    uint64_t  balance;           /**< Current e-hash balance (satoshis). */
    uint32_t  reward_rate;       /**< Reward per accepted nonce (sats). */
    uint32_t  nonces_accepted;   /**< Total accepted nonces from this station. */
    uint32_t  nonces_rejected;   /**< Total rejected nonces. */
    bool      active;            /**< Slot in use. */
} ehash_credit_entry_t;

/** Template TTL tracking entry. */
typedef struct {
    uint32_t  job_id;            /**< Job ID this template belongs to. */
    uint32_t  received_ts;       /**< Unix timestamp when template arrived. */
    bool      expired;           /**< True if TTL has passed. */
} ehash_template_ttl_t;

/**
 * @brief Radio TX callback.
 *
 * Called by the relay to broadcast a message (typically EHASH_TEMPLATE
 * downlink). The implementation (real LR2021 driver or test stub) sends
 * the bytes over the air.
 *
 * @param data      Pointer to the L7 envelope (type byte + payload).
 * @param len       Number of bytes to transmit.
 * @param user_ctx  Opaque context passed to ehash_relay_init().
 * @return 0 on success, <0 on error.
 */
typedef int (*ehash_radio_tx_fn)(const uint8_t *data, size_t len, void *user_ctx);

/**
 * @brief Radio unicast TX callback (for per-station messages like CREDIT).
 *
 * Same as ehash_radio_tx_fn but targets a specific station_id.
 */
typedef int (*ehash_radio_tx_unicast_fn)(uint32_t station_id,
                                          const uint8_t *data, size_t len,
                                          void *user_ctx);

/**
 * @brief Upstream TX callback.
 *
 * Called by the relay to forward a nonce upstream to the e-hash proxy.
 * The implementation connects to the real proxy (stratum) or mock.
 *
 * @param nonce  Pointer to decoded nonce struct.
 * @param ctx    Opaque context.
 * @return 0 on success, <0 on error.
 */
typedef int (*ehash_upstream_tx_fn)(const ehash_nonce_t *nonce, void *ctx);

/* ========================================================================
 *  Relay State
 * ======================================================================== */

/**
 * @brief Main relay context. One instance per balloon.
 *
 * All relay state is held in this struct — no globals — so the component
 * is testable and re-entrant.
 */
typedef struct {
    /* --- Callbacks (injected, abstract radio/upstream layers) --- */
    ehash_radio_tx_fn           radio_broadcast;   /**< Broadcast TX (template). */
    ehash_radio_tx_unicast_fn   radio_unicast;     /**< Unicast TX (credit/result). */
    ehash_upstream_tx_fn        upstream_tx;       /**< Forward nonce to proxy. */
    void                       *cb_ctx;            /**< User context for callbacks. */

    /* --- Credit table (D10: per-nonce e-hash issuance) --- */
    ehash_credit_entry_t  credits[EHASH_RELAY_MAX_STATIONS];

    /* --- Template encryption (D8: per-session key) --- */
    uint8_t  session_key[EHASH_RELAY_KEY_SIZE];  /**< AES-128 or XOR key. */
    bool     key_set;                             /**< True after ehash_crypto_session_start(). */

    /* --- TTL tracking (D9) --- */
    ehash_template_ttl_t  current_template;  /**< Most recent template metadata. */
    uint32_t              ttl_window_s;      /**< Configurable TTL (default 15 min). */
    bool                  upstream_connected; /**< False → templates stale. */

    /* --- Stats --- */
    uint32_t  templates_relayed;
    uint32_t  nonces_relayed;
    uint32_t  credits_issued;
} ehash_relay_t;

/* ========================================================================
 *  Public API
 * ======================================================================== */

/**
 * @brief Initialize a relay context.
 *
 * @param r          Relay context (caller allocates).
 * @param broadcast  Radio broadcast TX callback (may be NULL for tests).
 * @param unicast    Radio unicast TX callback (may be NULL for tests).
 * @param upstream   Upstream nonce forwarding callback (may be NULL for tests).
 * @param cb_ctx     Opaque context passed to all callbacks.
 */
void ehash_relay_init(ehash_relay_t *r,
                       ehash_radio_tx_fn         broadcast,
                       ehash_radio_tx_unicast_fn unicast,
                       ehash_upstream_tx_fn      upstream,
                       void                     *cb_ctx);

/* --- Template Relay (downlink: proxy → balloon → ground) --- */

/**
 * @brief Handle an incoming mining.notify from the upstream e-hash proxy.
 *
 * This is the main entry point for downlink. It:
 *   1. Encodes the template fields into EHASH_TEMPLATE binary.
 *   2. Encrypts the payload with the per-session key (D8).
 *   3. Broadcasts the encrypted L7 envelope via radio.
 *   4. Updates TTL tracking.
 *
 * @param r     Relay context.
 * @param tmpl  Decoded template struct.
 * @param now   Current Unix timestamp (for TTL).
 * @return Bytes broadcast (>0), or <0 on error.
 */
int ehash_relay_on_template(ehash_relay_t *r,
                             const ehash_template_t *tmpl,
                             uint32_t now);

/**
 * @brief Check whether the current template is expired.
 *
 * @param r    Relay context.
 * @param now  Current Unix timestamp.
 * @return true if template TTL has elapsed (D9).
 */
bool ehash_relay_template_expired(const ehash_relay_t *r, uint32_t now);

/* --- Nonce Relay (uplink: ground → balloon → proxy) --- */

/**
 * @brief Handle an incoming EHASH_NONCE from a ground station via radio.
 *
 * This is the main entry point for uplink. It:
 *   1. Decodes the nonce from the radio buffer.
 *   2. Forwards the nonce upstream to the e-hash proxy.
 *   3. Issues per-nonce e-hash credit to the miner (D10).
 *
 * @param r        Relay context.
 * @param buf      Radio receive buffer (L7 envelope: type byte + payload).
 * @param len      Buffer length.
 * @return 0 on success, <0 on error.
 */
int ehash_relay_on_nonce(ehash_relay_t *r,
                          const uint8_t *buf, size_t len);

/* --- Credit Gate (D8/D10) --- */

/**
 * @brief Check if a station has positive e-hash balance.
 *
 * Per D8, templates are only delivered to stations with balance > 0.
 * This function checks the credit table.
 *
 * @param r           Relay context.
 * @param station_id  Station to check.
 * @return true if balance > 0 (template key delivery allowed).
 */
bool ehash_relay_has_credit(const ehash_relay_t *r, uint32_t station_id);

/**
 * @brief Get the credit entry for a station (const accessor).
 *
 * @param r           Relay context.
 * @param station_id  Station ID.
 * @return Pointer to credit entry, or NULL if not found.
 */
const ehash_credit_entry_t *ehash_relay_get_credit(const ehash_relay_t *r,
                                                     uint32_t station_id);

/**
 * @brief Issue e-hash credit to a station after a valid nonce (D10).
 *
 * Increments balance by the station's reward_rate and broadcasts an
 * EHASH_CREDIT message to the station.
 *
 * @param r           Relay context.
 * @param station_id  Station that earned the credit.
 * @return 0 on success, <0 on error (station not found, radio fail).
 */
int ehash_relay_issue_credit(ehash_relay_t *r, uint32_t station_id);

/* --- TTL / Upstream Status (D9) --- */

/**
 * @brief Mark upstream as connected/disconnected.
 *
 * When disconnected, templates are considered stale after TTL expiry.
 *
 * @param r           Relay context.
 * @param connected   New upstream status.
 */
void ehash_relay_set_upstream(ehash_relay_t *r, bool connected);

/**
 * @brief Set the TTL window (seconds).
 */
void ehash_relay_set_ttl(ehash_relay_t *r, uint32_t ttl_s);

/* ========================================================================
 *  Credit Table Helpers (exposed for testing)
 * ======================================================================== */

/**
 * @brief Find or create a credit entry for a station.
 * @return Index into credits[], or -1 if table full.
 */
int ehash_relay_credit_find_or_create(ehash_relay_t *r, uint32_t station_id);

/**
 * @brief Set a station's balance directly (test helper / proxy update).
 */
int ehash_relay_credit_set_balance(ehash_relay_t *r,
                                    uint32_t station_id,
                                    uint64_t balance,
                                    uint32_t reward_rate);

#ifdef __cplusplus
}
#endif

#endif /* EHASH_RELAY_H */
