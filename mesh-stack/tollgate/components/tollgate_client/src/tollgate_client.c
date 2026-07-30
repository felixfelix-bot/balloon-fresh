/*
 * tollgate_client.c — ground station TollGate client state machine
 *
 * Implements ADR-002: TollGate payment protocol client side.
 *
 * State machine:
 *   IDLE     → QUERYING   (query_price sends STATUS)
 *   QUERYING → IDLE       (INFO received, price learned)
 *   IDLE     → PAYING     (pay sends PAY with Cashu token)
 *   PAYING   → ACTIVE     (ACK received)
 *   PAYING   → ERROR      (NACK or TG_CLIENT_MAX_RETRIES exceeded)
 *   ACTIVE   → EXPIRED    (session timeout in tick)
 *   EXPIRED  → PAYING     (auto-renew in tick)
 *
 * Transport is abstracted via the send_fn callback provided at init.
 * Incoming packets are delivered via tollgate_client_on_packet().
 */

#include "tollgate_client.h"
#include "tollgate_payment_proto.h"   /* includes tollgate_balloon.h transitively */
#include <string.h>
#include <stdlib.h>
#include <sys/time.h>

/* --- Internal state --- */

static tollgate_client_session_t s_session;
static char     s_mint_url[256] = {0};
static void   (*s_send_fn)(const uint8_t *data, uint16_t len) = NULL;
static void   (*s_on_state_change)(tollgate_client_state_t from,
                                    tollgate_client_state_t to) = NULL;
static uint16_t s_seq = 0;

/* Last PAY token (stored for retries) */
static char     s_pay_token[TOLLGATE_MAX_TOKEN_LEN];
static uint16_t s_pay_token_len = 0;

#ifdef TEST_HOST
int64_t tollgate_client_mock_now_ms = 0;
#endif

/* --- Helpers --- */

/*
 * Get the current time in milliseconds.
 * In TEST_HOST mode, uses the mock clock for deterministic testing.
 */
static int64_t now_ms(void)
{
#ifdef TEST_HOST
    return tollgate_client_mock_now_ms;
#else
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return (int64_t)tv.tv_sec * 1000 + tv.tv_usec / 1000;
#endif
}

/*
 * Transition to a new state, firing the state-change callback if registered.
 * No-op if the state is already the target.
 */
static void transition_to(tollgate_client_state_t new_state)
{
    tollgate_client_state_t old = s_session.state;
    if (old == new_state)
        return;
    s_session.state = new_state;
    if (s_on_state_change) {
        s_on_state_change(old, new_state);
    }
}

/*
 * Encode a tollgate protocol message and send it via the transport callback.
 */
static void send_msg(tollgate_msg_type_t type, const char *payload,
                      uint16_t payload_len)
{
    if (!s_send_fn)
        return;

    uint8_t buf[sizeof(tollgate_msg_hdr_t) + TOLLGATE_MAX_TOKEN_LEN];
    int len = tollgate_proto_encode(buf, (uint16_t)sizeof(buf), type, s_seq++,
                                     payload, payload_len);
    if (len > 0) {
        s_send_fn(buf, (uint16_t)len);
    }
}

/*
 * Create a Cashu token for the given amount.
 *
 * In TEST_HOST mode, returns a dummy token for deterministic testing.
 * In production, this will call the nucula wallet to create a real token.
 */
static const char *create_token(uint16_t sats)
{
#ifdef TEST_HOST
    (void)sats;
    return "cashuAtesttoken0000";
#else
    /*
     * TODO: integrate nucula_wallet to mint a real Cashu token.
     * Until wallet integration is complete, pay() returns ESP_FAIL.
     */
    (void)sats;
    return NULL;
#endif
}

/* --- Public API --- */

esp_err_t tollgate_client_init(
    const char *mint_url,
    void (*send_fn)(const uint8_t *data, uint16_t len),
    void (*on_state_change)(tollgate_client_state_t from,
                             tollgate_client_state_t to))
{
    if (!mint_url || !send_fn) {
        return ESP_ERR_INVALID_ARG;
    }

    strncpy(s_mint_url, mint_url, sizeof(s_mint_url) - 1);
    s_mint_url[sizeof(s_mint_url) - 1] = '\0';
    s_send_fn = send_fn;
    s_on_state_change = on_state_change;

    memset(&s_session, 0, sizeof(s_session));
    s_session.state = TG_CLIENT_IDLE;

    s_seq = 0;
    s_pay_token_len = 0;
    s_pay_token[0] = '\0';

#ifdef TEST_HOST
    tollgate_client_mock_now_ms = 0;
#endif

    return ESP_OK;
}

esp_err_t tollgate_client_on_packet(const uint8_t *data, uint16_t len)
{
    if (!data) {
        return ESP_ERR_INVALID_ARG;
    }

    tollgate_msg_hdr_t hdr;
    const uint8_t *payload = NULL;
    int off = tollgate_proto_decode(data, len, &hdr, &payload);
    if (off < 0) {
        return ESP_ERR_INVALID_ARG;
    }

    switch (hdr.type) {
    case TG_MSG_INFO: {
        /* Learn pricing from INFO response (QUERYING → IDLE) */
        if (s_session.state != TG_CLIENT_QUERYING)
            break;

        /* Parse JSON payload for price_sats and step_ms */
        char json_buf[TOLLGATE_MAX_TOKEN_LEN + 1];
        uint16_t copy_len = hdr.payload_len;
        if (copy_len >= sizeof(json_buf))
            copy_len = sizeof(json_buf) - 1;
        memcpy(json_buf, payload, copy_len);
        json_buf[copy_len] = '\0';

        char *p = strstr(json_buf, "\"price_sats\":");
        if (p) {
            p += strlen("\"price_sats\":");
            s_session.price_sats = (uint16_t)atoi(p);
        }

        p = strstr(json_buf, "\"step_ms\":");
        if (p) {
            p += strlen("\"step_ms\":");
            s_session.step_ms = (int32_t)atol(p);
        }

        transition_to(TG_CLIENT_IDLE);
        break;
    }
    case TG_MSG_ACK: {
        /* Payment accepted (PAYING → ACTIVE) */
        if (s_session.state != TG_CLIENT_PAYING)
            break;

        if (hdr.payload_len >= sizeof(tollgate_ack_payload_t)) {
            tollgate_ack_payload_t ack;
            memcpy(&ack, payload, sizeof(ack));
            s_session.session_id      = ack.session_id;
            s_session.session_expires = ack.expires_unix;
        }

        transition_to(TG_CLIENT_ACTIVE);
        break;
    }
    case TG_MSG_NACK: {
        /* Payment rejected (PAYING → ERROR) */
        if (s_session.state != TG_CLIENT_PAYING)
            break;
        transition_to(TG_CLIENT_ERROR);
        break;
    }
    case TG_MSG_REVOKE: {
        /* Session revoked by balloon (ACTIVE → EXPIRED) */
        if (s_session.state == TG_CLIENT_ACTIVE)
            transition_to(TG_CLIENT_EXPIRED);
        break;
    }
    default:
        return ESP_ERR_INVALID_ARG;
    }

    return ESP_OK;
}

esp_err_t tollgate_client_query_price(void)
{
    if (s_session.state != TG_CLIENT_IDLE) {
        return ESP_ERR_INVALID_STATE;
    }

    /* Send STATUS message (empty payload) */
    send_msg(TG_MSG_STATUS, NULL, 0);

    transition_to(TG_CLIENT_QUERYING);
    return ESP_OK;
}

esp_err_t tollgate_client_pay(uint16_t sats)
{
    if (s_session.state != TG_CLIENT_IDLE &&
        s_session.state != TG_CLIENT_EXPIRED) {
        return ESP_ERR_INVALID_STATE;
    }

    const char *token = create_token(sats);
    if (!token) {
        return ESP_FAIL;
    }

    /* Store token for retries */
    strncpy(s_pay_token, token, sizeof(s_pay_token) - 1);
    s_pay_token[sizeof(s_pay_token) - 1] = '\0';
    s_pay_token_len = (uint16_t)strlen(s_pay_token);

    /* Send PAY message */
    send_msg(TG_MSG_PAY, s_pay_token, s_pay_token_len);

    s_session.price_sats      = sats;
    s_session.retries         = 0;
    s_session.last_payment_ms = now_ms();

    transition_to(TG_CLIENT_PAYING);
    return ESP_OK;
}

bool tollgate_client_is_active(void)
{
    return s_session.state == TG_CLIENT_ACTIVE;
}

void tollgate_client_tick(void)
{
    tollgate_client_state_t state_at_start = s_session.state;
    int64_t now = now_ms();

    /* --- Session expiry: ACTIVE → EXPIRED --- */
    if (s_session.state == TG_CLIENT_ACTIVE &&
        s_session.session_expires > 0) {
        uint32_t now_sec = (uint32_t)(now / 1000);
        if (now_sec >= s_session.session_expires) {
            transition_to(TG_CLIENT_EXPIRED);
        }
    }

    /* --- PAY retry: resend after TG_CLIENT_RETRY_MS --- */
    if (s_session.state == TG_CLIENT_PAYING) {
        int64_t elapsed = now - s_session.last_payment_ms;
        if (elapsed >= TG_CLIENT_RETRY_MS) {
            s_session.retries++;
            if (s_session.retries >= TG_CLIENT_MAX_RETRIES) {
                transition_to(TG_CLIENT_ERROR);
            } else {
                send_msg(TG_MSG_PAY, s_pay_token, s_pay_token_len);
                s_session.last_payment_ms = now;
            }
        }
    }

    /*
     * --- Auto-renew: EXPIRED → PAYING ---
     * Only fires if the session was already EXPIRED at the start of this
     * tick — this gives the caller one tick to observe the EXPIRED state
     * before the auto-renew kicks in.
     */
    if (state_at_start == TG_CLIENT_EXPIRED && s_session.price_sats > 0) {
        tollgate_client_pay(s_session.price_sats);
    }
}

const tollgate_client_session_t *tollgate_client_get_session(void)
{
    return &s_session;
}
