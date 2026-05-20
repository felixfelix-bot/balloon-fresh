#include "gps.h"
#include "esp_log.h"
#include "driver/uart.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <string.h>
#include <stdlib.h>

static const char *TAG = "GPS";

#ifndef CONFIG_GPS_UART_RX_PIN
#define CONFIG_GPS_UART_RX_PIN 1
#endif
#ifndef CONFIG_GPS_UART_TX_PIN
#define CONFIG_GPS_UART_TX_PIN -1
#endif
#ifndef CONFIG_GPS_UART_BAUD
#define CONFIG_GPS_UART_BAUD 9600
#endif

#define GPS_UART_NUM    UART_NUM_1
#define GPS_BUF_SIZE    512
#define GPS_RX_PIN      CONFIG_GPS_UART_RX_PIN
#define GPS_TX_PIN      CONFIG_GPS_UART_TX_PIN
#define GPS_BAUD        CONFIG_GPS_UART_BAUD

static bool s_initialized = false;
static gps_data_t s_last_data;

static bool parse_nmea_gga(const char *sentence, gps_data_t *data)
{
    char *p = strchr(sentence, ',');
    if (!p) return false;

    int field = 0;
    char lat_str[16] = {0}, lat_dir[2] = {0};
    char lon_str[16] = {0}, lon_dir[2] = {0};
    char alt_str[16] = {0}, sats_str[4] = {0};
    char hdop_str[8] = {0};
    char fix_str[2] = {0};

    p++;
    while (*p && field < 15) {
        const char *start = p;
        while (*p && *p != ',' && *p != '*') p++;
        size_t len = p - start;
        switch (field) {
            case 1: if (len < 16) strncpy(lat_str, start, len); break;
            case 2: if (len < 2) strncpy(lat_dir, start, len); break;
            case 3: if (len < 16) strncpy(lon_str, start, len); break;
            case 4: if (len < 2) strncpy(lon_dir, start, len); break;
            case 5: if (len < 2) strncpy(fix_str, start, len); break;
            case 6: if (len < 4) strncpy(sats_str, start, len); break;
            case 7: if (len < 8) strncpy(hdop_str, start, len); break;
            case 8: if (len < 16) strncpy(alt_str, start, len); break;
        }
        if (*p == ',') p++;
        field++;
    }

    data->fix = (fix_str[0] >= '1');
    if (!data->fix) return false;

    if (strlen(lat_str) >= 4) {
        int deg = atoi(lat_str) / 100;
        float min = atof(lat_str + 2);
        data->latitude = (int32_t)((deg + min / 60.0) * 1e5);
        if (lat_dir[0] == 'S') data->latitude = -data->latitude;
    }

    if (strlen(lon_str) >= 5) {
        int deg = atoi(lon_str) / 100;
        float min = atof(lon_str + 3);
        data->longitude = (int32_t)((deg + min / 60.0) * 1e5);
        if (lon_dir[0] == 'W') data->longitude = -data->longitude;
    }

    data->sats = (uint8_t)atoi(sats_str);
    data->hdop = atof(hdop_str);
    data->altitude_m = (uint16_t)atof(alt_str);

    return true;
}

static bool parse_nmea_rmc(const char *sentence, gps_data_t *data)
{
    char *p = strchr(sentence, ',');
    if (!p) return false;

    int field = 0;
    char status[2] = {0};
    char lat_str[16] = {0}, lat_dir[2] = {0};
    char lon_str[16] = {0}, lon_dir[2] = {0};

    p++;
    while (*p && field < 8) {
        const char *start = p;
        while (*p && *p != ',' && *p != '*') p++;
        size_t len = p - start;
        switch (field) {
            case 0: break;
            case 1: if (len < 2) strncpy(status, start, len); break;
            case 2: if (len < 15) strncpy(lat_str, start, len); break;
            case 3: if (len < 2) strncpy(lat_dir, start, len); break;
            case 4: if (len < 15) strncpy(lon_str, start, len); break;
            case 5: if (len < 2) strncpy(lon_dir, start, len); break;
        }
        if (*p == ',') p++;
        field++;
    }

    if (status[0] != 'A') return false;

    if (strlen(lat_str) >= 4) {
        int deg = atoi(lat_str) / 100;
        float min = atof(lat_str + 2);
        data->latitude = (int32_t)((deg + min / 60.0) * 1e5);
        if (lat_dir[0] == 'S') data->latitude = -data->latitude;
    }

    if (strlen(lon_str) >= 5) {
        int deg = atoi(lon_str) / 100;
        float min = atof(lon_str + 3);
        data->longitude = (int32_t)((deg + min / 60.0) * 1e5);
        if (lon_dir[0] == 'W') data->longitude = -data->longitude;
    }

    return true;
}

esp_err_t gps_init(void)
{
    if (s_initialized) return ESP_OK;

    uart_config_t uart_config = {
        .baud_rate = GPS_BAUD,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .rx_flow_ctrl_thresh = 122,
    };
    ESP_ERROR_CHECK(uart_param_config(GPS_UART_NUM, &uart_config));
    ESP_ERROR_CHECK(uart_set_pin(GPS_UART_NUM, GPS_TX_PIN, GPS_RX_PIN, -1, -1));
    ESP_ERROR_CHECK(uart_driver_install(GPS_UART_NUM, GPS_BUF_SIZE, 0, 0, NULL, 0));

    memset(&s_last_data, 0, sizeof(s_last_data));
    s_initialized = true;
    ESP_LOGI(TAG, "GPS UART1 initialized (RX=GPIO%d, TX=GPIO%d, %d baud)", GPS_RX_PIN, GPS_TX_PIN, GPS_BAUD);
    return ESP_OK;
}

static void process_nmea_sentence(const char *sentence, gps_data_t *data)
{
    if (strstr(sentence, "$GNGGA") || strstr(sentence, "$GPGGA")) {
        parse_nmea_gga(sentence, data);
    } else if (strstr(sentence, "$GNRMC") || strstr(sentence, "$GPRMC")) {
        if (parse_nmea_rmc(sentence, data)) {
            if (!data->fix) data->fix = true;
        }
    }
}

bool gps_read(gps_data_t *data)
{
    if (!s_initialized) return false;

    uint8_t buf[GPS_BUF_SIZE];
    int len = uart_read_bytes(GPS_UART_NUM, buf, GPS_BUF_SIZE - 1, pdMS_TO_TICKS(100));
    if (len <= 0) return false;

    buf[len] = '\0';

    char *line = strtok((char *)buf, "\r\n");
    bool got_update = false;

    while (line) {
        if (line[0] == '$') {
            process_nmea_sentence(line, &s_last_data);
            got_update = true;
        }
        line = strtok(NULL, "\r\n");
    }

    if (data) {
        memcpy(data, &s_last_data, sizeof(gps_data_t));
    }
    return got_update;
}

void gps_sleep(void)
{
    if (!s_initialized) return;
    char cmd[] = "$PUBX,40,0,0,0,0,0,0,0,0,0,0,0,0,0*24\r\n";
    uart_write_bytes(GPS_UART_NUM, cmd, strlen(cmd));
    ESP_LOGI(TAG, "GPS sleep");
}

void gps_wakeup(void)
{
    if (!s_initialized) return;
    char cmd[] = "$PUBX,40,0,1,1,1,1,1,1,1,1,1,1,1,1*25\r\n";
    uart_write_bytes(GPS_UART_NUM, cmd, strlen(cmd));
    ESP_LOGI(TAG, "GPS wakeup");
}
