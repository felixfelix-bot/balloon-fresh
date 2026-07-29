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

#include "esp_log.h"
#include "esp_http_server.h"

#include <string.h>
#include <fcntl.h>
#include <unistd.h>

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

    ESP_LOGI(TAG, "Registered GET, HEAD, OPTIONS handlers");
    return ESP_OK;
}
