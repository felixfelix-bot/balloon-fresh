#pragma once
#include <stdbool.h>
#include "esp_http_server.h"

typedef struct {
    char pubkey[65];      // hex pubkey (64 chars + null)
    char sha256[65];      // x-tag value (64 hex chars + null)
    bool valid;
} blossom_auth_result_t;

// Verify Authorization header from PUT /upload request
// Returns ESP_OK if auth valid, ESP_FAIL otherwise
esp_err_t blossom_auth_verify_upload(httpd_req_t *req, blossom_auth_result_t *result);
