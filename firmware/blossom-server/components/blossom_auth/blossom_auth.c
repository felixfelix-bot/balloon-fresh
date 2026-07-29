/*
 * blossom_auth.c — BUD-11 Nostr event authentication for Blossom uploads.
 *
 * Verifies the Authorization header on PUT /upload requests:
 *   Authorization: Nostr <base64url(json_event_no_padding)>
 *
 * The event must be:
 *   - kind 24242 (BUD-11 auth event)
 *   - Have a valid Schnorr signature (verified via blossom_crypto)
 *   - Not expired (expiration tag in the future)
 *   - Have t-tag == "upload"
 *   - Have x-tag (sha256 hex of the upload body)
 */
#include "blossom_auth.h"
#include "blossom_crypto.h"

#include "esp_log.h"
#include "esp_timer.h"

#include "mbedtls/base64.h"
#include "cJSON.h"

#include <string.h>
#include <stdlib.h>

static const char *TAG = "blossom_auth";

#define BUD11_KIND       24242
#define AUTH_HDR_MAX     1536   /* max chars for the entire header value */

esp_err_t blossom_auth_verify_upload(httpd_req_t *req, blossom_auth_result_t *result)
{
    memset(result, 0, sizeof(*result));
    result->valid = false;

    /* ── 1. Read the Authorization header ─────────────────────────── */

    size_t hdr_len = httpd_req_get_hdr_value_len(req, "Authorization");
    if (hdr_len == 0) {
        ESP_LOGW(TAG, "No Authorization header");
        return ESP_FAIL;
    }
    if (hdr_len > AUTH_HDR_MAX) {
        ESP_LOGW(TAG, "Authorization header too long (%u)", (unsigned)hdr_len);
        return ESP_FAIL;
    }

    /* hdr_buf holds "Nostr <base64url>"; we reuse it for standard base64 later */
    char hdr_buf[AUTH_HDR_MAX + 4];  /* +4 for possible == padding */
    if (httpd_req_get_hdr_value_str(req, "Authorization", hdr_buf, sizeof(hdr_buf)) != ESP_OK) {
        ESP_LOGW(TAG, "Failed to read Authorization header");
        return ESP_FAIL;
    }

    /* ── 2. Verify "Nostr " prefix ────────────────────────────────── */

    static const char prefix[] = "Nostr ";
    size_t prefix_len = sizeof(prefix) - 1;
    if (strncmp(hdr_buf, prefix, prefix_len) != 0) {
        ESP_LOGW(TAG, "Authorization scheme is not 'Nostr'");
        return ESP_FAIL;
    }

    /* b64url points into hdr_buf past the prefix */
    char *b64 = hdr_buf + prefix_len;
    size_t b64_len = strlen(b64);
    if (b64_len == 0) {
        ESP_LOGW(TAG, "Empty base64url payload");
        return ESP_FAIL;
    }

    /* ── 3. Convert base64url → standard base64 (in-place) ────────── */

    for (size_t i = 0; i < b64_len; i++) {
        if (b64[i] == '-')      b64[i] = '+';
        else if (b64[i] == '_') b64[i] = '/';
    }

    /* Re-add padding */
    size_t rem = b64_len % 4;
    if (rem == 1) {
        ESP_LOGW(TAG, "Invalid base64 length (%u mod 4 == 1)", (unsigned)b64_len);
        return ESP_FAIL;
    }
    if (rem == 2) {
        b64[b64_len]     = '=';
        b64[b64_len + 1] = '=';
        b64[b64_len + 2] = '\0';
    } else if (rem == 3) {
        b64[b64_len]     = '=';
        b64[b64_len + 1] = '\0';
    }
    /* rem == 0: no padding needed */
    size_t b64_std_len = strlen(b64);

    /* ── 4. Base64-decode into JSON string ────────────────────────── */

    /* Upper bound: ceil(len/4)*3, minus padding */
    size_t dec_max = (b64_std_len / 4) * 3 + 1;
    unsigned char *event_json = (unsigned char *)malloc(dec_max);
    if (!event_json) {
        ESP_LOGE(TAG, "malloc(%u) failed", (unsigned)dec_max);
        return ESP_ERR_NO_MEM;
    }

    size_t dec_len = 0;
    int mret = mbedtls_base64_decode(event_json, dec_max, &dec_len,
                                     (const unsigned char *)b64, b64_std_len);
    if (mret != 0) {
        ESP_LOGW(TAG, "base64 decode failed (-0x%04x)", -mret);
        free(event_json);
        return ESP_FAIL;
    }
    event_json[dec_len] = '\0';

    ESP_LOGD(TAG, "Decoded auth event (%u bytes)", (unsigned)dec_len);

    /* ── 5. Verify event signature + id (full crypto check) ───────── */

    if (!blossom_verify_event((const char *)event_json, dec_len)) {
        ESP_LOGW(TAG, "Event verification failed — invalid id or signature");
        free(event_json);
        return ESP_FAIL;
    }

    /* ── 6. Parse JSON for field-level checks ─────────────────────── */

    cJSON *obj = cJSON_ParseWithLength((const char *)event_json, dec_len);
    if (!obj) {
        ESP_LOGW(TAG, "JSON parse failed after signature verification");
        free(event_json);
        return ESP_FAIL;
    }

    /* pubkey */
    cJSON *pk_item = cJSON_GetObjectItem(obj, "pubkey");
    if (!pk_item || !cJSON_IsString(pk_item) || strlen(pk_item->valuestring) != 64) {
        ESP_LOGW(TAG, "Missing or invalid pubkey field");
        goto auth_fail;
    }

    /* kind == 24242 */
    cJSON *kind_item = cJSON_GetObjectItem(obj, "kind");
    if (!kind_item || !cJSON_IsNumber(kind_item)) {
        ESP_LOGW(TAG, "Missing or invalid kind field");
        goto auth_fail;
    }
    if (kind_item->valueint != BUD11_KIND) {
        ESP_LOGW(TAG, "Wrong event kind: %d (expected %d)", kind_item->valueint, BUD11_KIND);
        goto auth_fail;
    }

    /* tags array */
    cJSON *tags = cJSON_GetObjectItem(obj, "tags");
    if (!tags || !cJSON_IsArray(tags)) {
        ESP_LOGW(TAG, "Missing tags array");
        goto auth_fail;
    }

    /* Walk tags to find t, x, expiration */
    const char *t_val = NULL;
    const char *x_val = NULL;
    const char *exp_val = NULL;

    cJSON *tag;
    cJSON_ArrayForEach(tag, tags) {
        if (!cJSON_IsArray(tag) || cJSON_GetArraySize(tag) < 2)
            continue;
        cJSON *name = cJSON_GetArrayItem(tag, 0);
        cJSON *value = cJSON_GetArrayItem(tag, 1);
        if (!cJSON_IsString(name) || !cJSON_IsString(value))
            continue;

        if      (strcmp(name->valuestring, "t")          == 0) t_val   = value->valuestring;
        else if (strcmp(name->valuestring, "x")          == 0) x_val   = value->valuestring;
        else if (strcmp(name->valuestring, "expiration") == 0) exp_val = value->valuestring;
    }

    /* ── 7. Check t-tag == "upload" ───────────────────────────────── */

    if (!t_val || strcmp(t_val, "upload") != 0) {
        ESP_LOGW(TAG, "Missing or wrong t-tag: '%s'", t_val ? t_val : "(null)");
        goto auth_fail;
    }

    /* ── 8. Check x-tag present (64-char hex) ─────────────────────── */

    if (!x_val || strlen(x_val) != 64) {
        ESP_LOGW(TAG, "Missing or invalid x-tag (sha256)");
        goto auth_fail;
    }

    /* ── 9. Check expiration in the future ────────────────────────── */

    if (!exp_val) {
        ESP_LOGW(TAG, "Missing expiration tag");
        goto auth_fail;
    }
    int64_t expiration = (int64_t)strtoll(exp_val, NULL, 10);
    int64_t now_s = (int64_t)(esp_timer_get_time() / 1000000);
    if (expiration <= now_s) {
        ESP_LOGW(TAG, "Auth event expired (exp=%lld, now=%lld)",
                 (long long)expiration, (long long)now_s);
        goto auth_fail;
    }

    /* ── 10. Fill result ──────────────────────────────────────────── */

    strncpy(result->pubkey, pk_item->valuestring, 64);
    result->pubkey[64] = '\0';
    strncpy(result->sha256, x_val, 64);
    result->sha256[64] = '\0';
    result->valid = true;

    cJSON_Delete(obj);
    free(event_json);

    ESP_LOGD(TAG, "Auth OK: pubkey=%.16s… sha256=%.16s…",
             result->pubkey, result->sha256);
    return ESP_OK;

auth_fail:
    cJSON_Delete(obj);
    free(event_json);
    return ESP_FAIL;
}
