/*
 * tollgate_balloon.c — Mesh transport adapter for TollGate
 *
 * Implements ADR-002: UDP payment messages over FIPS mesh.
 * Wraps tollgate_core with mesh node IDs instead of WiFi IP/MAC.
 *
 * IMPLEMENTED:
 *   - nucula wallet integration (spend_proofs → nucula_wallet_receive)
 *   - payment protocol encode/decode (tollgate_payment_proto.c)
 *   - platform adapter (mining stubs zeroed)
 *
 * PENDING:
 *   - FIPS mesh transport API (UDP send/recv over mesh)
 *   - Node ID ↔ IP mapping for tollgate_core compatibility
 *   - Mesh access control (grant/revoke relay)
 */

#include "tollgate_balloon.h"
#include "tollgate_payment_proto.h"
#include "tollgate_core.h"
#include "nucula_wallet.h"
#include "esp_err.h"
#include "esp_log.h"
#include <string.h>
#include <stdlib.h>
#include <sys/time.h>

static const char *TAG = "tollgate_balloon";

/* --- Platform adapter (implements tollgate_platform_t for balloon) --- */

static uint16_t s_price_sats = 21;
static int32_t  s_step_ms    = 60000;
static char     s_mint_url[256] = {0};

static uint16_t pf_get_price_sats(void) { return s_price_sats; }
static int32_t  pf_get_step_ms(void)    { return s_step_ms; }
static const char *pf_get_mint_url(void) { return s_mint_url; }
static const char *pf_get_metric(void)  { return "sats"; }
static int32_t  pf_get_step_bytes(void) { return 0; /* time-based, not byte-based */ }

static int64_t  pf_get_time_ms(void) {
    /* TODO: use mesh time sync or GPS time */
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return (int64_t)tv.tv_sec * 1000 + tv.tv_usec / 1000;
}

static bool pf_spend_proofs(const char *raw_token_json) {
    /*
     * Wire incoming Cashu token to nucula wallet.
     * nucula_wallet_receive() performs a real Cashu swap (NUT-03) with the mint:
     *   1. Parse cashuA... token
     *   2. POST to mint /v1/swap — exchange proofs for new proofs
     *   3. Store new proofs in NVS
     *   4. Return ESP_OK on success
     *
     * This is the key difference from the original tollgate-esp32, which only
     * checked proof state via /v1/checkstate but never actually swapped.
     * Felix wants real swaps to prevent double-spending.
     */
    if (!raw_token_json || raw_token_json[0] == '\0') {
        ESP_LOGW(TAG, "spend_proofs: empty token");
        return false;
    }

    ESP_LOGI(TAG, "spend_proofs: calling nucula_wallet_receive()...");
    esp_err_t ret = nucula_wallet_receive(raw_token_json);
    if (ret == ESP_OK) {
        ESP_LOGI(TAG, "Cashu token received + swapped. Balance: %llu sats",
                 (unsigned long long)nucula_wallet_balance());
        return true;
    }

    ESP_LOGW(TAG, "Cashu receive/swap failed: %s", esp_err_to_name(ret));
    return false;
}

/* Stratum/mining stubs — not used on balloon, return defaults */
static const char *pf_null_str(void) { return ""; }
static uint16_t    pf_zero_u16(void) { return 0; }
static uint64_t    pf_zero_u64(void) { return 0; }
static void        pf_nop(void) {}
static double      pf_zero_dbl(void) { return 0.0; }

static const tollgate_platform_t s_balloon_platform __attribute__((unused)) = {
    .get_price_sats         = pf_get_price_sats,
    .get_step_ms            = pf_get_step_ms,
    .get_mint_url           = pf_get_mint_url,
    .get_metric             = pf_get_metric,
    .get_step_bytes         = pf_get_step_bytes,
    .get_time_ms            = pf_get_time_ms,
    .spend_proofs           = pf_spend_proofs,
    /* Mining/stratum — not used on balloon, zeroed stubs */
    .get_stratum_url        = pf_null_str,
    .get_stratum_port       = pf_zero_u16,
    .get_stratum_user       = pf_null_str,
    .get_stratum_pass       = pf_null_str,
    .get_stratum_fallback_url  = pf_null_str,
    .get_stratum_fallback_port = pf_zero_u16,
    .get_mining_port        = pf_zero_u16,
    .get_mining_payout_mode = pf_null_str,
    .get_hashprice_sats_per_ghs_day = pf_zero_u64,
    .on_share_accepted      = (void(*)(double))pf_nop,
    .get_hashrate           = pf_zero_dbl,
};

/* --- Public API --- */

esp_err_t tollgate_balloon_init(const char *nsec_hex,
                                 const char *mint_url,
                                 uint16_t price_sats,
                                 int32_t step_ms)
{
    ESP_LOGI(TAG, "=== Balloon TollGate Init ===");
    ESP_LOGI(TAG, "  Price: %u sats / %ld ms", price_sats, (long)step_ms);
    ESP_LOGI(TAG, "  Mint:  %s", mint_url ? mint_url : "(none)");
    ESP_LOGI(TAG, "  Port:  %d (UDP over FIPS mesh)", TOLLGATE_BALLOON_PORT);

    s_price_sats = price_sats;
    s_step_ms = step_ms;
    if (mint_url) {
        strncpy(s_mint_url, mint_url, sizeof(s_mint_url) - 1);
    }

    /* Initialize nucula wallet for Cashu token receiving/swapping */
    if (mint_url) {
        ESP_LOGI(TAG, "Initializing nucula wallet with mint: %s", mint_url);
        esp_err_t wallet_ret = nucula_wallet_init(mint_url);
        if (wallet_ret != ESP_OK) {
            ESP_LOGW(TAG, "nucula_wallet_init failed: %s — payments will fail",
                     esp_err_to_name(wallet_ret));
        } else {
            ESP_LOGI(TAG, "nucula wallet ready. Balance: %llu sats",
                     (unsigned long long)nucula_wallet_balance());
        }
    } else {
        ESP_LOGW(TAG, "No mint URL provided — wallet not initialized");
    }

    /*
     * TODO: Initialize tollgate_core with balloon platform.
     * Need a fake IP for tollgate_core_init (it expects esp_ip4_addr_t).
     * On mesh, there's no real IP — use 10.0.0.1 as placeholder.
     *
     * esp_ip4_addr_t fake_ap = { .addr = htonl(0x0A000001) };
     * tollgate_core_init(&s_balloon_platform, fake_ap);
     *
     * TODO: Open UDP socket on TOLLGATE_BALLOON_PORT via FIPS mesh transport.
     * Need mesh UDP API from balloon-fips track.
     */

    ESP_LOGW(TAG, "INITIALIZATION INCOMPLETE — requires FIPS mesh transport API");
    ESP_LOGW(TAG, "Core init deferred until mesh UDP layer available from balloon-fips track");

    return ESP_OK;
}

esp_err_t tollgate_balloon_on_packet(const char *src_node_id,
                                      const uint8_t *data,
                                      uint16_t len)
{
    if (!src_node_id || !data || len < sizeof(tollgate_msg_hdr_t)) {
        return ESP_ERR_INVALID_ARG;
    }

    tollgate_msg_hdr_t hdr;
    const uint8_t *payload;
    int off = tollgate_proto_decode(data, len, &hdr, &payload);
    if (off < 0) {
        ESP_LOGW(TAG, "Invalid packet from %s", src_node_id);
        return ESP_ERR_INVALID_ARG;
    }

    /* Null-terminate payload for JSON parsing */
    char json_buf[TOLLGATE_MAX_TOKEN_LEN + 1];
    uint16_t copy_len = hdr.payload_len;
    if (copy_len >= sizeof(json_buf))
        copy_len = sizeof(json_buf) - 1;
    memcpy(json_buf, payload, copy_len);
    json_buf[copy_len] = '\0';

    switch (hdr.type) {
    case TG_MSG_PAY: {
        ESP_LOGI(TAG, "PAY from %s: token_len=%u", src_node_id, copy_len);

        /*
         * Payment flow:
         * 1. Extract token from JSON payload {"token":"cashuA..."}
         *    (For v1, accept raw token string directly if no JSON wrapper)
         * 2. Map src_node_id → internal client_id
         * 3. Call tollgate_core_process_payment() which will:
         *    a. Decode Cashu token via tollgate_core_cashu_decode_token()
         *    b. Check proof states via mint HTTP /v1/checkstate
         *    c. Call pf_spend_proofs() → nucula_wallet_receive() (real swap!)
         *    d. Grant session on success
         * 4. Build + send ACK or NACK via mesh
         *
         * Error codes (tollgate_nack_payload_t):
         *   TG_ERR_INVALID_TOKEN    — malformed Cashu token
         *   TG_ERR_SWAP_FAILED      — nucula swap/receive failed
         *   TG_ERR_MINT_UNREACHABLE — can't contact mint (offline)
         *   TG_ERR_ALREADY_PAID     — session already active
         */
        ESP_LOGW(TAG, "PAY handler: mesh transport not yet wired — "
                 "core_process_payment needs IP mapping + UDP response path");
        /* TODO: Implement when FIPS mesh transport available */
        break;
    }
    case TG_MSG_STATUS: {
        ESP_LOGI(TAG, "STATUS request from %s", src_node_id);
        /* TODO: Build + send INFO response with pricing */
        break;
    }
    default:
        ESP_LOGW(TAG, "Unknown msg type 0x%02x from %s", hdr.type, src_node_id);
        return ESP_ERR_INVALID_ARG;
    }

    return ESP_OK;
}

void tollgate_balloon_tick(void)
{
    /* TODO: tollgate_core_tick();
     * TODO: expire sessions
     * TODO: periodic beacon (beacon module)
     */
}

char *tollgate_balloon_get_status(void)
{
    return tollgate_proto_build_info_json(s_price_sats, s_step_ms,
                                           s_mint_url, 0);
}

void tollgate_balloon_stop(void)
{
    ESP_LOGI(TAG, "Shutting down balloon TollGate");
    /* TODO: close UDP socket, revoke all sessions */
}
