#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "driver/gpio.h"
#include "driver/uart.h"

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

static EspHalC3* hal = nullptr;
static LR2021* radio = nullptr;

static bool flag_rx_done = false;

static void IRAM_ATTR on_rx_done(void) {
    flag_rx_done = true;
}

static void print_telemetry(const uint8_t *buf, int16_t rssi, float snr)
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

    printf("{\"type\":\"telemetry\"");
    printf(",\"seq\":%u", pkt.seq);
    printf(",\"lat\":%.5f", lat);
    printf(",\"lon\":%.5f", lon);
    printf(",\"alt\":%u", pkt.altitude_m);
    printf(",\"temp_c\":%.2f", temp);
    printf(",\"pressure_hpa\":%.1f", pres);
    printf(",\"voltage_mv\":%u", pkt.voltage_mv);
    printf(",\"sats\":%u", pkt.sats);
    printf(",\"rssi\":%d", rssi);
    printf(",\"snr\":%.1f", snr);
    printf(",\"flags\":%u", pkt.flags);
    printf("}\n");
    fflush(stdout);

    ESP_LOGI(TAG, "Seq %u: %.5f,%.5f alt=%um temp=%.1fC pres=%.1fhPa cap=%umV sats=%u RSSI=%d SNR=%.1f flags=0x%02X",
        pkt.seq, lat, lon, pkt.altitude_m, temp, pres, pkt.voltage_mv,
        pkt.sats, rssi, snr, pkt.flags);
}

extern "C" void app_main(void)
{
    ESP_LOGI(TAG, "=== Ground Station Receiver ===");

    hal = new EspHalC3(LR2021_SCK, LR2021_MISO, LR2021_MOSI);
    radio = new LR2021(new Module(hal, LR2021_NSS, LR2021_DIO9, LR2021_RST, LR2021_BUSY));
    radio->irqDioNum = 9;

    ESP_LOGI(TAG, "Initializing LR2021...");
    int16_t state = radio->begin(868.0, 125.0, 9, 7, 0x12, 22, 8);
    if (state != RADIOLIB_ERR_NONE) {
        ESP_LOGE(TAG, "LR2021 init failed: %d", state);
        while (true) { hal->delay(1000); }
    }

    state = radio->startReceive();
    if (state != RADIOLIB_ERR_NONE) {
        ESP_LOGE(TAG, "startReceive failed: %d", state);
        while (true) { hal->delay(1000); }
    }

    radio->setPacketReceivedAction(on_rx_done);
    ESP_LOGI(TAG, "Listening on 868 MHz SF9...");

    while (1) {
        if (flag_rx_done) {
            flag_rx_done = false;

            uint8_t buf[TELEMETRY_SIZE];
            int16_t len = radio->readData(buf, TELEMETRY_SIZE);

            int16_t rssi = radio->getRSSI();
            float snr = radio->getSNR();

            if (len == TELEMETRY_SIZE) {
                print_telemetry(buf, rssi, snr);
            } else {
                ESP_LOGW(TAG, "Wrong length: %d (expected %d), RSSI=%d", len, TELEMETRY_SIZE, rssi);
            }

            state = radio->startReceive();
            if (state != RADIOLIB_ERR_NONE) {
                ESP_LOGE(TAG, "restartReceive failed: %d", state);
            }
        }
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}
