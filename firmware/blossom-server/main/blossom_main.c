/*
 * blossom_main.c — Blossom server entry point.
 *
 * Boot sequence:
 *   1. Init NVS
 *   2. Mount LittleFS blob storage
 *   3. Start WiFi AP (SSID: balloon-blossom)
 *   4. Start HTTP server (port 80) with GET/HEAD/OPTIONS handlers
 */
#include "esp_log.h"
#include "esp_system.h"
#include "esp_event.h"
#include "nvs_flash.h"
#include "esp_wifi.h"
#include "esp_netif.h"

#include "esp_http_server.h"

#include "blossom_storage.h"
#include "blossom_handlers.h"

static const char *TAG = "blossom";

/* WiFi AP configuration (hardcoded for now; configurable later) */
#define BLOSSOM_AP_SSID        "balloon-blossom"
#define BLOSSOM_AP_PASS        "blossom123"
#define BLOSSOM_AP_MAX_CONN    4
#define BLOSSOM_AP_CHANNEL     1

/* ── WiFi AP initialization ─────────────────────────────────────── */

static esp_err_t start_wifi_ap(void)
{
    /* Create default AP netif */
    esp_netif_create_default_wifi_ap();

    /* Init WiFi with default config */
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    /* Configure AP */
    wifi_config_t wifi_config = {
        .ap = {
            .channel           = BLOSSOM_AP_CHANNEL,
            .max_connection    = BLOSSOM_AP_MAX_CONN,
            .authmode          = WIFI_AUTH_WPA2_PSK,
            .pmf_cfg.required  = false,
        },
    };
    /* ssid / password — set separately to avoid designated-init warnings
       on different ESP-IDF versions (some use arrays, some use unions) */
    strncpy((char *)wifi_config.ap.ssid, BLOSSOM_AP_SSID, sizeof(wifi_config.ap.ssid));
    strncpy((char *)wifi_config.ap.password, BLOSSOM_AP_PASS, sizeof(wifi_config.ap.password));

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_AP));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_AP, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());

    ESP_LOGI(TAG, "WiFi AP started — SSID: %s, channel %d, max %d clients",
             BLOSSOM_AP_SSID, BLOSSOM_AP_CHANNEL, BLOSSOM_AP_MAX_CONN);
    ESP_LOGI(TAG, "Connect to WiFi and browse http://192.168.4.1/");

    return ESP_OK;
}

/* ── HTTP server initialization ─────────────────────────────────── */

static esp_err_t start_http_server(void)
{
    httpd_handle_t server = NULL;
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.max_uri_handlers = 8;
    config.lru_purge_enable = true;
    config.max_resp_headers = 16;
    config.stack_size = 16384;  /* secp256k1 schnorrsig_verify needs ~12KB stack */

    /* Increase max URI/hdr length for SHA-256 paths + CORS headers */
    config.uri_match_fn = httpd_uri_match_wildcard;

    ESP_LOGI(TAG, "Starting HTTP server on port %d", config.server_port);
    esp_err_t ret = httpd_start(&server, &config);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to start HTTP server: %s", esp_err_to_name(ret));
        return ret;
    }

    /* Register Blossom handlers (GET/HEAD/OPTIONS) */
    ESP_ERROR_CHECK(blossom_register_handlers(server));

    ESP_LOGI(TAG, "HTTP server running on port 80");
    return ESP_OK;
}

/* ── Main ───────────────────────────────────────────────────────── */

void app_main(void)
{
    ESP_LOGI(TAG, "=== Blossom server boot ===");

    /* 1. NVS — required by WiFi */
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);
    ESP_LOGI(TAG, "NVS initialized");

    /* 2. Init TCP/IP + event loop (required before WiFi) */
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());

    /* 3. Mount LittleFS storage */
    ESP_ERROR_CHECK(blossom_storage_init());
    ESP_LOGI(TAG, "Storage mounted");

    /* 4. Start WiFi AP */
    ESP_ERROR_CHECK(start_wifi_ap());

    /* 5. Start HTTP server */
    ESP_ERROR_CHECK(start_http_server());

    ESP_LOGI(TAG, "=== Blossom server ready ===");
    ESP_LOGI(TAG, "Endpoints: GET/HEAD /<sha256>, PUT /upload, OPTIONS /*");
}
