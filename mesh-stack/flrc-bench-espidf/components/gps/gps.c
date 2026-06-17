#include "gps.h"
#include "gps_parser.h"
#include "esp_log.h"
#include "driver/uart.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <string.h>
#include <stdlib.h>

static const char *TAG = "GPS";

#ifndef CONFIG_GPS_UART_RX_PIN
  #ifdef CONFIG_RANGE_TEST_GPS_UART_RX_PIN
    #define CONFIG_GPS_UART_RX_PIN CONFIG_RANGE_TEST_GPS_UART_RX_PIN
  #else
    #define CONFIG_GPS_UART_RX_PIN 1
  #endif
#endif
#ifndef CONFIG_GPS_UART_TX_PIN
  #ifdef CONFIG_RANGE_TEST_GPS_UART_TX_PIN
    #define CONFIG_GPS_UART_TX_PIN CONFIG_RANGE_TEST_GPS_UART_TX_PIN
  #else
    #define CONFIG_GPS_UART_TX_PIN -1
  #endif
#endif
#ifndef CONFIG_GPS_UART_BAUD
  #ifdef CONFIG_RANGE_TEST_GPS_UART_BAUD
    #define CONFIG_GPS_UART_BAUD CONFIG_RANGE_TEST_GPS_UART_BAUD
  #else
    #define CONFIG_GPS_UART_BAUD 9600
  #endif
#endif

#define GPS_UART_NUM    UART_NUM_1
#define GPS_BUF_SIZE    512
#define GPS_RX_PIN      CONFIG_GPS_UART_RX_PIN
#define GPS_TX_PIN      CONFIG_GPS_UART_TX_PIN
#define GPS_BAUD        CONFIG_GPS_UART_BAUD

static bool s_initialized = false;
static gps_data_t s_last_data;

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
    gps_parser_data_t parsed;
    memset(&parsed, 0, sizeof(parsed));

    if (strstr(sentence, "$GNGGA") || strstr(sentence, "$GPGGA")) {
        if (gps_parse_nmea_gga(sentence, &parsed)) {
            data->fix = parsed.fix;
            data->latitude = parsed.latitude;
            data->longitude = parsed.longitude;
            data->altitude_m = parsed.altitude_m;
            data->sats = parsed.sats;
            data->hdop = parsed.hdop;
        }
    } else if (strstr(sentence, "$GNRMC") || strstr(sentence, "$GPRMC")) {
        if (gps_parse_nmea_rmc(sentence, &parsed)) {
            data->fix = true;
            data->latitude = parsed.latitude;
            data->longitude = parsed.longitude;
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
