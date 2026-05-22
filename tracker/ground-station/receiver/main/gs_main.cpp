#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"
#include "esp_log.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_http_client.h"
#include "esp_netif.h"
#include "nvs_flash.h"
#include "driver/gpio.h"
#include "driver/uart.h"
#include "lwip/err.h"
#include "lwip/sys.h"

#include <RadioLib.h>
#include "EspHalC3.h"

extern "C" {
#include "telemetry.h"
}

static const char *TAG = "GS_RX";

#define LR2021_SCK   6
#define LR2021_MISO  2
#define LR2021_MOSI  7
#define LR2021_NSS   10
#define LR2021_BUSY  4
#define LR2021_RST   3
#define LR2021_DIO9  5

#ifndef CONFIG_GS_WIFI_SSID
#define CONFIG_GS_WIFI_SSID "YOUR_SSID"
#endif
#ifndef CONFIG_GS_WIFI_PASS
#define CONFIG_GS_WIFI_PASS "YOUR_PASSWORD"
#endif
#ifndef CONFIG_GS_UPLINK_URL
#define CONFIG_GS_UPLINK_URL "http://localhost:8080/api/telemetry"
#endif

static EventGroupHandle_t s_wifi_event_group;
#define WIFI_CONNECTED_BIT BIT0
#define WIFI_FAIL_BIT      BIT1
static int s_retry_count = 0;
#define MAX_WIFI_RETRY 5

static EspHalC3* hal = nullptr;
static LR2021* radio = nullptr;

static bool flag_rx_done = false;

static void IRAM_ATTR on_rx_done(void) {
    flag_rx_done = true;
}

static void wifi_event_handler(void *arg, esp_event_base_t event_base,
                                int32_t event_id, void *event_data)
{
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        if (s_retry_count < MAX_WIFI_RETRY) {
            esp_wifi_connect();
            s_retry_count++;
            ESP_LOGI(TAG, "WiFi retry %d/%d", s_retry_count, MAX_WIFI_RETRY);
        } else {
            xEventGroupSetBits(s_wifi_event_group, WIFI_FAIL_BIT);
        }
    } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *event = (ip_event_got_ip_t *)event_data;
        ESP_LOGI(TAG, "Got IP: " IPSTR, IP2STR(&event->ip_info.ip));
        s_retry_count = 0;
        xEventGroupSetBits(s_wifi_event_group, WIFI_CONNECTED_BIT);
    }
}

static void wifi_init_sta(void)
{
    s_wifi_event_group = xEventGroupCreate();
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    esp_event_handler_instance_t inst_any_id;
    esp_event_handler_instance_t inst_got_ip;
    ESP_ERROR_CHECK(esp_event_handler_instance_register(WIFI_EVENT,
        ESP_EVENT_ANY_ID, &wifi_event_handler, NULL, &inst_any_id));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(IP_EVENT,
        IP_EVENT_STA_GOT_IP, &wifi_event_handler, NULL, &inst_got_ip));

    wifi_config_t wifi_config = {};
    strncpy((char *)wifi_config.sta.ssid, CONFIG_GS_WIFI_SSID, sizeof(wifi_config.sta.ssid) - 1);
    strncpy((char *)wifi_config.sta.password, CONFIG_GS_WIFI_PASS, sizeof(wifi_config.sta.password) - 1);

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());

    ESP_LOGI(TAG, "WiFi init done, connecting to %s", CONFIG_GS_WIFI_SSID);

    EventBits_t bits = xEventGroupWaitBits(s_wifi_event_group,
        WIFI_CONNECTED_BIT | WIFI_FAIL_BIT, pdFALSE, pdFALSE, portMAX_DELAY);

    if (bits & WIFI_CONNECTED_BIT) {
        ESP_LOGI(TAG, "WiFi connected");
    } else {
        ESP_LOGW(TAG, "WiFi failed, running without uplink");
    }
}

static char s_post_payload[512];

static esp_err_t http_event_handler(esp_http_client_event_t *evt)
{
    return ESP_OK;
}

static void http_post_telemetry(const char *json)
{
    snprintf(s_post_payload, sizeof(s_post_payload), "%s", json);

    esp_http_client_config_t config = {};
    config.url = CONFIG_GS_UPLINK_URL;
    config.method = HTTP_METHOD_POST;
    config.event_handler = http_event_handler;
    config.timeout_ms = 5000;

    esp_http_client_handle_t client = esp_http_client_init(&config);
    esp_http_client_set_post_field(client, s_post_payload, (int)strlen(s_post_payload));
    esp_http_client_set_header(client, "Content-Type", "application/json");

    esp_err_t err = esp_http_client_perform(client);
    if (err == ESP_OK) {
        int status = esp_http_client_get_status_code(client);
        ESP_LOGI(TAG, "HTTP POST %d bytes -> %d", (int)strlen(s_post_payload), status);
    } else {
        ESP_LOGW(TAG, "HTTP POST failed: %s", esp_err_to_name(err));
    }
    esp_http_client_cleanup(client);
}

static void print_and_upload(const uint8_t *buf, int16_t rssi, float snr)
{
    if (!telemetry_validate(buf, TELEMETRY_SIZE)) {
        ESP_LOGW(TAG, "CRC mismatch on received packet (RSSI: %d, SNR: %.1f)", rssi, snr);
        return;
    }

    telemetry_packet_t pkt;
    memcpy(&pkt, buf, TELEMETRY_SIZE);

    float lat = (float)pkt.latitude_deg1e5 / 1e5f;
    float lon = (float)pkt.longitude_deg1e5 / 1e5f;
    float temp = (float)pkt.temperature_cdeg / 100.0f;
    float pres = (float)pkt.pressure_hpa / 10.0f;

    char json[400];
    snprintf(json, sizeof(json),
        "{\"type\":\"telemetry\",\"seq\":%u,\"lat\":%.5f,\"lon\":%.5f,"
        "\"alt\":%u,\"temp_c\":%.2f,\"pressure_hpa\":%.1f,\"voltage_mv\":%u,"
        "\"sats\":%u,\"rssi\":%d,\"snr\":%.1f,\"flags\":%u}",
        pkt.seq, lat, lon, pkt.altitude_m, temp, pres, pkt.voltage_mv,
        pkt.sats, rssi, snr, pkt.flags);

    printf("%s\n", json);
    fflush(stdout);

    ESP_LOGI(TAG, "Seq %u: %.5f,%.5f alt=%um temp=%.1fC pres=%.1fhPa cap=%umV sats=%u RSSI=%d SNR=%.1f flags=0x%02X",
        pkt.seq, lat, lon, pkt.altitude_m, temp, pres, pkt.voltage_mv,
        pkt.sats, rssi, snr, pkt.flags);

    if (xEventGroupGetBits(s_wifi_event_group) & WIFI_CONNECTED_BIT) {
        http_post_telemetry(json);
    }
}

extern "C" void app_main(void)
{
    ESP_LOGI(TAG, "=== Ground Station Receiver ===");

    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    wifi_init_sta();

    hal = new EspHalC3(LR2021_SCK, LR2021_MISO, LR2021_MOSI);
    radio = new LR2021(new Module(hal, LR2021_NSS, LR2021_DIO9, LR2021_RST, LR2021_BUSY));
    radio->irqDioNum = 9;

    ESP_LOGI(TAG, "Initializing LR2021...");
    int16_t state = radio->begin(868.0, 125.0, 9, 7, 0x12, 22, 8);
    if (state != RADIOLIB_ERR_NONE) {
        ESP_LOGE(TAG, "LR2021 init failed: %d", state);
        while (true) { hal->delay(1000); }
    }

    radio->setPacketReceivedAction(on_rx_done);

    state = radio->startReceive();
    if (state != RADIOLIB_ERR_NONE) {
        ESP_LOGE(TAG, "startReceive failed: %d", state);
        while (true) { hal->delay(1000); }
    }
    ESP_LOGI(TAG, "Listening on 868 MHz SF9...");

    while (1) {
        if (flag_rx_done) {
            flag_rx_done = false;

            uint8_t buf[TELEMETRY_SIZE];
            int16_t state = radio->readData(buf, TELEMETRY_SIZE);

            int16_t rssi = radio->getRSSI();
            float snr = radio->getSNR();

            if (state == RADIOLIB_ERR_NONE) {
                print_and_upload(buf, rssi, snr);
            } else {
                ESP_LOGW(TAG, "readData failed: %d, RSSI=%d", state, rssi);
            }

            state = radio->startReceive();
            if (state != RADIOLIB_ERR_NONE) {
                ESP_LOGE(TAG, "restartReceive failed: %d", state);
            }
        }
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}
