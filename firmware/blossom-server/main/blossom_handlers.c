/*
 * blossom_handlers.c — HTTP request handlers for Blossom BUD-01 endpoints.
 *
 *   GET    /<sha256>   — stream blob content (2 KB chunks)
 *   HEAD   /<sha256>   — existence check + size/type headers, no body
 *   OPTIONS wildcard   — CORS preflight
 *
 * All responses include permissive CORS headers for captive-portal use.
 */
#include "blossom_handlers.h"
#include "blossom_storage.h"
#include "blossom_auth.h"
#include "blossom_crypto.h"

#include "esp_log.h"
#include "esp_http_server.h"
#include "esp_timer.h"

#include "mbedtls/sha256.h"

#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>

static const char *TAG = "blossom_http";

/* Stream chunk size for GET responses */
#define STREAM_CHUNK_SIZE  2048

/* ── Helpers ────────────────────────────────────────────────────── */

/**
 * Validate that `s` is a 64-char lowercase hex string (SHA-256).
 */
static bool is_valid_sha256_hex(const char *s, size_t len)
{
    if (len != 64) return false;
    for (size_t i = 0; i < 64; i++) {
        char c = s[i];
        if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f')))
            return false;
    }
    return true;
}

/**
 * Extract the 64-char SHA-256 hex hash from a URI path like "/<hash>" or
 * "/<hash>.png".
 *
 * Writes at most 65 chars (64 + NUL) into `out`.
 * @return true if a valid hash was extracted.
 */
static bool extract_sha256_from_uri(const char *uri, char *out, size_t out_len)
{
    if (out_len < 65) return false;

    /* Skip leading slash */
    const char *path = uri;
    while (*path == '/') path++;

    /* The hash is the first 64 chars of the path component */
    size_t pathlen = strlen(path);
    if (pathlen < 64) return false;

    /* Check there's a path separator after the hash (end, '.', or '/') */
    char after = path[64];
    if (after != '\0' && after != '.' && after != '/')
        return false;

    if (!is_valid_sha256_hex(path, 64))
        return false;

    memcpy(out, path, 64);
    out[64] = '\0';
    return true;
}

/**
 * Set standard CORS headers on an HTTP response.
 */
static void set_cors_headers(httpd_req_t *req)
{
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
}

/* ── GET handler: stream blob content ───────────────────────────── */

static esp_err_t blossom_get_handler(httpd_req_t *req)
{
    char sha256[65];
    if (!extract_sha256_from_uri(req->uri, sha256, sizeof(sha256))) {
        httpd_resp_set_status(req, "404 Not Found");
        set_cors_headers(req);
        httpd_resp_send(req, "Not Found", -1);
        return ESP_OK;
    }

    /* Check existence + get size */
    if (!blossom_storage_exists(sha256)) {
        ESP_LOGD(TAG, "GET %s — not found", sha256);
        httpd_resp_set_status(req, "404 Not Found");
        set_cors_headers(req);
        httpd_resp_send(req, "Not Found", -1);
        return ESP_OK;
    }

    /* Build file path and open */
    char fpath[96];
    blossom_storage_get_path(sha256, fpath, sizeof(fpath));

    int fd = open(fpath, O_RDONLY);
    if (fd < 0) {
        httpd_resp_set_status(req, "404 Not Found");
        set_cors_headers(req);
        httpd_resp_send(req, "Not Found", -1);
        return ESP_OK;
    }

    /* Set Content-Type from .meta (fallback to octet-stream) */
    char content_type[128] = "application/octet-stream";
    blossom_storage_get_type(sha256, content_type, sizeof(content_type));
    httpd_resp_set_type(req, content_type);

    /* Set Content-Length */
    size_t fsize = blossom_storage_get_size(sha256);
    char cl_str[24];
    snprintf(cl_str, sizeof(cl_str), "%u", (unsigned)fsize);
    httpd_resp_set_hdr(req, "Content-Length", cl_str);
    httpd_resp_set_status(req, "200 OK");
    set_cors_headers(req);

    /* Stream in 2 KB chunks */
    static uint8_t chunk[STREAM_CHUNK_SIZE];
    size_t remaining = fsize;
    while (remaining > 0) {
        size_t to_read = (remaining < STREAM_CHUNK_SIZE) ? remaining : STREAM_CHUNK_SIZE;
        ssize_t n = read(fd, chunk, to_read);
        if (n <= 0) break;

        esp_err_t wr = httpd_resp_send_chunk(req, (const char *)chunk, (ssize_t)n);
        if (wr != ESP_OK) {
            ESP_LOGE(TAG, "httpd_resp_send_chunk failed: %s", esp_err_to_name(wr));
            break;
        }
        remaining -= (size_t)n;
    }
    close(fd);

    /* End chunked response */
    httpd_resp_send_chunk(req, NULL, 0);
    ESP_LOGD(TAG, "GET %s — sent %u bytes (%s)", sha256, (unsigned)fsize, content_type);
    return ESP_OK;
}

/* ── HEAD handler: existence + metadata, no body ────────────────── */

static esp_err_t blossom_head_handler(httpd_req_t *req)
{
    char sha256[65];
    if (!extract_sha256_from_uri(req->uri, sha256, sizeof(sha256))) {
        httpd_resp_set_status(req, "404 Not Found");
        set_cors_headers(req);
        httpd_resp_send(req, NULL, 0);
        return ESP_OK;
    }

    if (!blossom_storage_exists(sha256)) {
        ESP_LOGD(TAG, "HEAD %s — not found", sha256);
        httpd_resp_set_status(req, "404 Not Found");
        set_cors_headers(req);
        httpd_resp_send(req, NULL, 0);
        return ESP_OK;
    }

    /* Content-Type */
    char content_type[128] = "application/octet-stream";
    blossom_storage_get_type(sha256, content_type, sizeof(content_type));
    httpd_resp_set_type(req, content_type);

    /* Content-Length */
    size_t fsize = blossom_storage_get_size(sha256);
    char cl_str[24];
    snprintf(cl_str, sizeof(cl_str), "%u", (unsigned)fsize);
    httpd_resp_set_hdr(req, "Content-Length", cl_str);

    httpd_resp_set_status(req, "200 OK");
    set_cors_headers(req);

    /* Empty body — esp_http_server handles HEAD correctly: headers only */
    httpd_resp_send(req, NULL, 0);
    ESP_LOGD(TAG, "HEAD %s — %u bytes (%s)", sha256, (unsigned)fsize, content_type);
    return ESP_OK;
}

/* ── OPTIONS handler: CORS preflight ────────────────────────────── */

static esp_err_t blossom_options_handler(httpd_req_t *req)
{
    httpd_resp_set_status(req, "200 OK");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin",  "*");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Headers", "Authorization, Content-Type, *");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Methods", "GET, HEAD, PUT, DELETE, OPTIONS");
    httpd_resp_set_hdr(req, "Access-Control-Max-Age",       "86400");
    httpd_resp_send(req, NULL, 0);
    return ESP_OK;
}

/* ── PUT handler: auth-required blob upload (BUD-02) ────────────── */

#define UPLOAD_CHUNK_SIZE  512
#define UPLOAD_TMP_PATH    "/blossom/.upload_tmp"

static esp_err_t blossom_upload_handler(httpd_req_t *req)
{
    /* 1. Verify BUD-11 auth */
    blossom_auth_result_t auth;
    if (blossom_auth_verify_upload(req, &auth) != ESP_OK) {
        ESP_LOGW(TAG, "Upload rejected: auth failed");
        httpd_resp_set_status(req, "401 Unauthorized");
        set_cors_headers(req);
        httpd_resp_set_type(req, "application/json");
        httpd_resp_send(req, "{\"error\":\"unauthorized\"}", -1);
        return ESP_OK;
    }

    /* 2. Content-Length */
    size_t content_len = req->content_len;
    ESP_LOGI(TAG, "Upload start: %u bytes, sha256=%s",
             (unsigned)content_len, auth.sha256);

    /* 3. Open temp file for streaming write */
    int fd = open(UPLOAD_TMP_PATH, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) {
        ESP_LOGE(TAG, "Cannot open temp file: %s", strerror(errno));
        httpd_resp_set_status(req, "500 Internal Server Error");
        set_cors_headers(req);
        httpd_resp_send(req, NULL, 0);
        return ESP_OK;
    }

    /* 4. Stream body → temp file, computing SHA-256 incrementally */
    mbedtls_sha256_context sha_ctx;
    mbedtls_sha256_init(&sha_ctx);
    int mret = mbedtls_sha256_starts(&sha_ctx, 0);
    if (mret != 0) {
        ESP_LOGE(TAG, "sha256_starts failed (-0x%04x)", -mret);
        mbedtls_sha256_free(&sha_ctx);
        close(fd);
        unlink(UPLOAD_TMP_PATH);
        httpd_resp_set_status(req, "500 Internal Server Error");
        set_cors_headers(req);
        httpd_resp_send(req, NULL, 0);
        return ESP_OK;
    }

    static uint8_t chunk[UPLOAD_CHUNK_SIZE];
    size_t remaining = content_len;
    size_t total_received = 0;
    bool io_error = false;

    while (remaining > 0) {
        size_t to_read = (remaining < UPLOAD_CHUNK_SIZE) ? remaining : UPLOAD_CHUNK_SIZE;
        int received = httpd_req_recv(req, (char *)chunk, to_read);
        if (received < 0) {
            ESP_LOGE(TAG, "httpd_req_recv error: %d", received);
            io_error = true;
            break;
        }
        if (received == 0) {
            ESP_LOGW(TAG, "Connection closed during upload (got %u/%u)",
                     (unsigned)total_received, (unsigned)content_len);
            break;
        }

        ssize_t written = write(fd, chunk, received);
        if (written != received) {
            ESP_LOGE(TAG, "write error: %s", strerror(errno));
            io_error = true;
            break;
        }

        mret = mbedtls_sha256_update(&sha_ctx, chunk, (size_t)received);
        if (mret != 0) {
            ESP_LOGE(TAG, "sha256_update failed (-0x%04x)", -mret);
            io_error = true;
            break;
        }

        total_received += (size_t)received;
        remaining -= (size_t)received;
    }

    close(fd);

    if (io_error || total_received != content_len) {
        ESP_LOGE(TAG, "Upload incomplete: %u/%u bytes, error=%d",
                 (unsigned)total_received, (unsigned)content_len, io_error);
        mbedtls_sha256_free(&sha_ctx);
        unlink(UPLOAD_TMP_PATH);
        httpd_resp_set_status(req, "500 Internal Server Error");
        set_cors_headers(req);
        httpd_resp_send(req, NULL, 0);
        return ESP_OK;
    }

    /* 5. Finish SHA-256 */
    uint8_t hash_raw[32];
    mret = mbedtls_sha256_finish(&sha_ctx, hash_raw);
    mbedtls_sha256_free(&sha_ctx);
    if (mret != 0) {
        ESP_LOGE(TAG, "sha256_finish failed (-0x%04x)", -mret);
        unlink(UPLOAD_TMP_PATH);
        httpd_resp_set_status(req, "500 Internal Server Error");
        set_cors_headers(req);
        httpd_resp_send(req, NULL, 0);
        return ESP_OK;
    }

    char hash_hex[65];
    relay_bytes_to_hex(hash_raw, 32, hash_hex);

    /* 6. Compare computed hash with auth x-tag */
    if (strcmp(hash_hex, auth.sha256) != 0) {
        ESP_LOGW(TAG, "Hash mismatch: computed=%s, expected=%s",
                 hash_hex, auth.sha256);
        unlink(UPLOAD_TMP_PATH);
        httpd_resp_set_status(req, "409 Conflict");
        set_cors_headers(req);
        httpd_resp_set_type(req, "application/json");
        httpd_resp_send(req, "{\"error\":\"sha256 mismatch\"}", -1);
        return ESP_OK;
    }

    /* 7. Rename temp → final blob path */
    char blob_path[96];
    blossom_storage_get_path(hash_hex, blob_path, sizeof(blob_path));
    if (rename(UPLOAD_TMP_PATH, blob_path) != 0) {
        ESP_LOGE(TAG, "rename(%s → %s) failed: %s",
                 UPLOAD_TMP_PATH, blob_path, strerror(errno));
        unlink(UPLOAD_TMP_PATH);
        httpd_resp_set_status(req, "500 Internal Server Error");
        set_cors_headers(req);
        httpd_resp_send(req, NULL, 0);
        return ESP_OK;
    }

    /* 8. Write .meta sidecar */
    char meta_path[128];
    snprintf(meta_path, sizeof(meta_path), "%s.meta", blob_path);

    /* Use Content-Type from request (or default) */
    char content_type[128] = "application/octet-stream";
    size_t ct_len = httpd_req_get_hdr_value_len(req, "Content-Type");
    if (ct_len > 0 && ct_len < sizeof(content_type)) {
        httpd_req_get_hdr_value_str(req, "Content-Type", content_type, sizeof(content_type));
    }

    int64_t now_s = (int64_t)(esp_timer_get_time() / 1000000);
    char meta_json[256];
    int meta_len = snprintf(meta_json, sizeof(meta_json),
                            "{\"size\":%u,\"type\":\"%s\",\"uploaded\":%lld}",
                            (unsigned)total_received, content_type, (long long)now_s);

    int mfd = open(meta_path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (mfd >= 0) {
        write(mfd, meta_json, (size_t)meta_len);
        close(mfd);
    } else {
        ESP_LOGW(TAG, "Failed to write .meta: %s", strerror(errno));
    }

    /* 9. Build blob descriptor JSON response (201 Created) */
    char resp[512];
    int resp_len = snprintf(resp, sizeof(resp),
        "{\"url\":\"http://192.168.4.1/%s\",\"sha256\":\"%s\",\"size\":%u,\"type\":\"%s\",\"uploaded\":%lld}",
        hash_hex, hash_hex, (unsigned)total_received, content_type, (long long)now_s);

    httpd_resp_set_status(req, "201 Created");
    set_cors_headers(req);
    httpd_resp_set_type(req, "application/json");
    httpd_resp_send(req, resp, resp_len);

    ESP_LOGI(TAG, "Upload OK: %s (%u bytes, %s)",
             hash_hex, (unsigned)total_received, content_type);
    return ESP_OK;
}

/* ── Register all handlers ──────────────────────────────────────── */

esp_err_t blossom_register_handlers(httpd_handle_t server)
{
    /* GET wildcard — download blobs */
    httpd_uri_t get_uri = {
        .uri       = "/*",
        .method    = HTTP_GET,
        .handler   = blossom_get_handler,
        .user_ctx  = NULL,
    };
    ESP_ERROR_CHECK(httpd_register_uri_handler(server, &get_uri));

    /* HEAD wildcard — existence check */
    httpd_uri_t head_uri = {
        .uri       = "/*",
        .method    = HTTP_HEAD,
        .handler   = blossom_head_handler,
        .user_ctx  = NULL,
    };
    ESP_ERROR_CHECK(httpd_register_uri_handler(server, &head_uri));

    /* OPTIONS wildcard — CORS preflight */
    httpd_uri_t options_uri = {
        .uri       = "/*",
        .method    = HTTP_OPTIONS,
        .handler   = blossom_options_handler,
        .user_ctx  = NULL,
    };
    ESP_ERROR_CHECK(httpd_register_uri_handler(server, &options_uri));

    /* PUT /upload — auth-required blob upload (BUD-02) */
    httpd_uri_t upload_uri = {
        .uri       = "/upload",
        .method    = HTTP_PUT,
        .handler   = blossom_upload_handler,
        .user_ctx  = NULL,
    };
    ESP_ERROR_CHECK(httpd_register_uri_handler(server, &upload_uri));

    ESP_LOGI(TAG, "Registered GET, HEAD, OPTIONS, PUT /upload handlers");
    return ESP_OK;
}
