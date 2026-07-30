#ifndef TOLLGATE_CLIENT_H
#define TOLLGATE_CLIENT_H

#include "esp_err.h"
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/*
 * TollGate Client — ground station payment state machine (ADR-002)
 *
 * Manages the client side of the TollGate payment protocol over FIPS mesh UDP.
 * The client:
 *   1. Queries the balloon for pricing (STATUS → INFO)
 *   2. Pays for relay access (PAY → ACK/NACK)
 *   3. Tracks active session until expiry
 *   4. Auto-renews when session expires
 *
 * Transport is abstracted via a send_fn callback provided at init time.
 * Incoming packets are delivered via tollgate_client_on_packet().
 *
 * State machine:
 *
 *   IDLE     → QUERYING   (query_price called)
 *   QUERYING → IDLE       (INFO received, price learned)
 *   IDLE     → PAYING     (pay called)
 *   PAYING   → ACTIVE     (ACK received)
 *   PAYING   → ERROR      (NACK received or max retries exceeded)
 *   ACTIVE   → EXPIRED    (session timeout in tick)
 *   EXPIRED  → PAYING     (auto-renew in tick)
 *
 * Usage:
 *   tollgate_client_init(mint_url, my_send_cb, my_state_cb);
 *   tollgate_client_query_price();        // learn pricing
 *   ... receive INFO via on_packet ...
 *   tollgate_client_pay(session.price_sats);
 *   ... receive ACK via on_packet ...
 *   while (running) tollgate_client_tick();  // 1 Hz
 */

/* Maximum PAY retries before transitioning to ERROR */
#define TG_CLIENT_MAX_RETRIES  3

/* Time to wait between PAY retries (ms) */
#define TG_CLIENT_RETRY_MS     2000

/*
 * Client state machine states.
 */
typedef enum {
    TG_CLIENT_IDLE,       /* No active session; price may or may not be known */
    TG_CLIENT_QUERYING,   /* Sent STATUS, awaiting INFO response */
    TG_CLIENT_PAYING,     /* Sent PAY, awaiting ACK or NACK */
    TG_CLIENT_ACTIVE,     /* Session active, relay access granted */
    TG_CLIENT_EXPIRED,    /* Session timed out, will auto-renew on next tick */
    TG_CLIENT_ERROR,      /* Payment failed (NACK or retries exhausted) */
} tollgate_client_state_t;

/*
 * Client session descriptor (read-only via tollgate_client_get_session).
 */
typedef struct {
    tollgate_client_state_t state;     /* Current state machine state */
    uint32_t balloon_node_id;          /* Mesh node ID of target balloon (future) */
    uint16_t price_sats;               /* Learned price per step (sats) */
    int32_t  step_ms;                  /* Learned step duration (ms) */
    uint32_t session_id;               /* Active session ID from ACK */
    uint32_t session_expires;          /* Session expiry (Unix seconds) */
    int      retries;                  /* Current PAY retry count */
    int64_t  last_payment_ms;          /* Timestamp of last PAY send (ms) */
} tollgate_client_session_t;

/*
 * Initialize the tollgate client.
 *
 * Stores the mint URL, transport callback, and optional state-change callback.
 * Resets the session to IDLE state.
 *
 * @param mint_url        Cashu mint URL (for wallet operations)
 * @param send_fn         Callback to send raw bytes over mesh transport.
 *                        Called synchronously when the client sends a message.
 * @param on_state_change Optional callback invoked on every state transition.
 *                        May be NULL if the caller doesn't need notifications.
 * @return ESP_OK on success,
 *         ESP_ERR_INVALID_ARG if mint_url or send_fn is NULL
 */
esp_err_t tollgate_client_init(
    const char *mint_url,
    void (*send_fn)(const uint8_t *data, uint16_t len),
    void (*on_state_change)(tollgate_client_state_t from,
                             tollgate_client_state_t to)
);

/*
 * Process an incoming packet from the balloon.
 *
 * Decodes the wire header and dispatches based on message type:
 *   INFO   → learn price/step, QUERYING→IDLE
 *   ACK    → learn session info, PAYING→ACTIVE
 *   NACK   → PAYING→ERROR
 *   REVOKE → ACTIVE→EXPIRED
 *
 * @param data  Raw packet bytes (header + JSON payload)
 * @param len   Packet length
 * @return ESP_OK on success,
 *         ESP_ERR_INVALID_ARG if data is NULL or packet is malformed
 */
esp_err_t tollgate_client_on_packet(const uint8_t *data, uint16_t len);

/*
 * Query the balloon for current pricing.
 *
 * Sends a STATUS message (empty payload) and transitions IDLE → QUERYING.
 * The response (INFO) arrives asynchronously via on_packet.
 *
 * @return ESP_OK on success,
 *         ESP_ERR_INVALID_STATE if not in IDLE state
 */
esp_err_t tollgate_client_query_price(void);

/*
 * Pay for relay access.
 *
 * Creates a Cashu token via the wallet, sends a PAY message with the token,
 * and transitions IDLE or EXPIRED → PAYING.
 * The response (ACK/NACK) arrives asynchronously via on_packet.
 *
 * @param sats  Amount to pay (should match the learned price)
 * @return ESP_OK on success,
 *         ESP_ERR_INVALID_STATE if not in IDLE or EXPIRED state,
 *         ESP_FAIL if wallet token creation fails
 */
esp_err_t tollgate_client_pay(uint16_t sats);

/*
 * Check if the client has an active relay session.
 *
 * @return true if state is TG_CLIENT_ACTIVE, false otherwise
 */
bool tollgate_client_is_active(void);

/*
 * Periodic tick — call from main loop (1 Hz or faster).
 *
 * Handles:
 *   - Session expiry: ACTIVE → EXPIRED (when session_expires is reached)
 *   - PAY retries: resends PAY after TG_CLIENT_RETRY_MS, up to
 *     TG_CLIENT_MAX_RETRIES, then transitions to ERROR
 *   - Auto-renew: EXPIRED → PAYING (automatically pays the last known price)
 */
void tollgate_client_tick(void);

/*
 * Get the current client session (read-only).
 *
 * @return Pointer to internal session struct. Do not free or modify.
 */
const tollgate_client_session_t *tollgate_client_get_session(void);

#ifdef TEST_HOST
/*
 * Test hook: mock time source for host unit tests.
 * Set this (in ms) to control the client's perceived clock.
 * Reset to 0 by tollgate_client_init().
 */
extern int64_t tollgate_client_mock_now_ms;
#endif

#ifdef __cplusplus
}
#endif

#endif /* TOLLGATE_CLIENT_H */
