/*
 * tollgate_client.c — ground station TollGate client state machine
 *
 * IMPLEMENTED (skeleton):
 *   - API with correct signatures and basic init
 *   - Session struct + state enum
 *
 * PENDING (next commit):
 *   - Full state machine transitions
 *   - Payment protocol encode/decode via tollgate_payment_proto
 *   - Wallet integration (nucula_wallet_send)
 *   - Retry logic + session expiry in tick()
 */

#include "tollgate_client.h"
#include <string.h>

/* --- Internal state --- */

static tollgate_client_session_t s_session;
static char     s_mint_url[256] = {0};
static void   (*s_send_fn)(const uint8_t *data, uint16_t len) = NULL;
static void   (*s_on_state_change)(tollgate_client_state_t from,
                                    tollgate_client_state_t to) = NULL;

#ifdef TEST_HOST
int64_t tollgate_client_mock_now_ms = 0;
#endif

/* --- Public API (skeleton) --- */

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

#ifdef TEST_HOST
    tollgate_client_mock_now_ms = 0;
#endif

    return ESP_OK;
}

esp_err_t tollgate_client_on_packet(const uint8_t *data, uint16_t len)
{
    (void)data;
    (void)len;
    return ESP_OK;
}

esp_err_t tollgate_client_query_price(void)
{
    return ESP_OK;
}

esp_err_t tollgate_client_pay(uint16_t sats)
{
    (void)sats;
    return ESP_OK;
}

bool tollgate_client_is_active(void)
{
    return s_session.state == TG_CLIENT_ACTIVE;
}

void tollgate_client_tick(void)
{
}

const tollgate_client_session_t *tollgate_client_get_session(void)
{
    return &s_session;
}
