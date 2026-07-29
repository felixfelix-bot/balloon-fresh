#ifndef BLOSSOM_HANDLERS_H
#define BLOSSOM_HANDLERS_H

#include "esp_http_server.h"

/**
 * Register all Blossom HTTP URI handlers (GET, HEAD, OPTIONS) on the
 * given HTTP server. Call once after httpd_start().
 *
 * @param server  Active httpd server handle.
 * @return ESP_OK on success.
 */
esp_err_t blossom_register_handlers(httpd_handle_t server);

#endif /* BLOSSOM_HANDLERS_H */
