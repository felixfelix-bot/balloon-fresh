/*
 * main.cpp — ESP32-C3 LR2021 Bench Test
 * Throughput comparison vs RP2040 (baseline: 1760 kbps at 10.40 MHz SPI).
 *
 * TX mode: uncomment NODE_TX below. RX mode: leave commented.
 * Payload size via -DPAYLOAD_SIZE=N (32/64/128/255, default 127).
 *
 * Build:
 *   source ~/esp/esp-idf/export.sh
 *   cd tracker/firmware/bench_test
 *   idf.py set-target esp32c3 && idf.py build
 *
 * Serial output (parsed by compare script):
 *   TX: TX_PKT seq=N payload=N br=2600 tput_kbps=NNNN
 *   RX: RX_PKT seq=N rssi=-XX snr=XX payload=N br=2600
 *   RX: RX_STATS total=N unique=N per=X.X throughput_kbps=NNNN rssi_avg=-XX
 */

#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "esp_idf_lr2021_radio.h"

// MODE: uncomment for TX, leave commented for RX
// #define NODE_TX

#ifndef PAYLOAD_SIZE
#define PAYLOAD_SIZE    127
#endif
#define BURST_PACKETS   10000
#define TX_DELAY_US     0
#define LED_PIN         8
#define HEARTBEAT_MS    3000
#define FREQ_MHZ        2440.0f
#define BITRATE_KBPS    2600
#define TX_POWER_DBM    12

static EspIdfLr2021Radio radio;
static uint8_t pkt_buf[256];

static inline void led_on()  { gpio_set_level((gpio_num_t)LED_PIN, 0); }
static inline void led_off() { gpio_set_level((gpio_num_t)LED_PIN, 1); }

static void init_led() {
    gpio_config_t io_conf = {};
    io_conf.pin_bit_mask = (1ULL << LED_PIN);
    io_conf.mode = GPIO_MODE_OUTPUT;
    gpio_config(&io_conf);
    led_off();
}

#ifdef NODE_TX

extern "C" void app_main(void) {
    printf("=== ESP32-C3 LR2021 BENCH TX ===\n");
    printf("PAYLOAD=%d BR=%d FREQ=%.1f\n", PAYLOAD_SIZE, BITRATE_KBPS, FREQ_MHZ);
    init_led();

    Lr2021Config config;
    config.freq_mhz = FREQ_MHZ;
    config.bitrate_kbps = BITRATE_KBPS;
    config.tx_power_dbm = TX_POWER_DBM;
    config.payload_length = PAYLOAD_SIZE;

    auto err = radio.init(config);
    if (err != Lr2021Error::Ok) {
        printf("RADIO_INIT_FAIL err=%d\n", (int)err);
        while (1) { vTaskDelay(1000 / portTICK_PERIOD_MS); }
    }
    printf("RADIO_INIT_OK\n");

    for (int i = 4; i < PAYLOAD_SIZE; i++) pkt_buf[i] = (uint8_t)(i & 0xFF);

    printf("TX_STARTING_3S_COUNTDOWN\n");
    for (int i = 3; i > 0; i--) {
        led_on(); vTaskDelay(500 / portTICK_PERIOD_MS);
        led_off(); vTaskDelay(500 / portTICK_PERIOD_MS);
        printf("COUNTDOWN %d\n", i);
    }

    uint32_t seq = 0, total_pkts = 0;
    uint32_t burst_start_ms = esp_timer_get_time() / 1000;
    printf("TX_BURST_START\n");

    while (total_pkts < BURST_PACKETS) {
        pkt_buf[0] = (seq >> 24) & 0xFF;
        pkt_buf[1] = (seq >> 16) & 0xFF;
        pkt_buf[2] = (seq >> 8) & 0xFF;
        pkt_buf[3] = seq & 0xFF;

        radio.send_packet(pkt_buf, PAYLOAD_SIZE);
        seq++; total_pkts++;

        uint32_t now_ms = esp_timer_get_time() / 1000;
        if (now_ms - burst_start_ms > HEARTBEAT_MS) {
            uint32_t elapsed = now_ms - burst_start_ms;
            uint32_t tput = (total_pkts * PAYLOAD_SIZE * 8) / elapsed;
            printf("TX_PKT seq=%lu payload=%d br=%d total=%lu tput_kbps=%lu\n",
                   (unsigned long)seq, PAYLOAD_SIZE, BITRATE_KBPS,
                   (unsigned long)total_pkts, (unsigned long)tput);
            burst_start_ms = now_ms;
        }
        if (TX_DELAY_US > 0) ets_delay_us(TX_DELAY_US);
    }

    uint32_t end_ms = esp_timer_get_time() / 1000;
    uint32_t total_ms = end_ms - (end_ms - total_pkts * 1); // approximate
    uint32_t final_tput = (total_pkts * PAYLOAD_SIZE * 8) / (total_ms > 0 ? total_ms : 1);
    printf("TX_BURST_DONE total=%lu tput_kbps=%lu payload=%d\n",
           (unsigned long)total_pkts, (unsigned long)final_tput, PAYLOAD_SIZE);
    led_on();
    while (1) { vTaskDelay(1000 / portTICK_PERIOD_MS); }
}

#else // RX NODE

extern "C" void app_main(void) {
    printf("=== ESP32-C3 LR2021 BENCH RX ===\n");
    printf("PAYLOAD=%d BR=%d FREQ=%.1f\n", PAYLOAD_SIZE, BITRATE_KBPS, FREQ_MHZ);
    init_led();

    Lr2021Config config;
    config.freq_mhz = FREQ_MHZ;
    config.bitrate_kbps = BITRATE_KBPS;
    config.payload_length = PAYLOAD_SIZE;

    auto err = radio.init(config);
    if (err != Lr2021Error::Ok) {
        printf("RADIO_INIT_FAIL err=%d\n", (int)err);
        while (1) { vTaskDelay(1000 / portTICK_PERIOD_MS); }
    }
    radio.start_rx();
    led_on();
    printf("RX_READY payload=%d br=%d\n", PAYLOAD_SIZE, BITRATE_KBPS);

    uint32_t total_rx = 0, unique_rx = 0, last_seq = 0, lost_pkts = 0;
    int32_t rssi_sum = 0; uint32_t rssi_count = 0;
    uint32_t start_ms = esp_timer_get_time() / 1000;
    uint32_t last_hb = start_ms;

    while (1) {
        bool irq = false;
        radio.check_irq(irq);
        if (irq) {
            uint32_t flags = 0;
            radio.get_irq_status(flags);
            if (IrqSource::contains(flags, IrqSource::RX_DONE)) {
                PacketStatus status;
                auto e = radio.read_packet(pkt_buf, sizeof(pkt_buf), status);
                if (e == Lr2021Error::Ok && status.length > 0) {
                    total_rx++;
                    rssi_sum += status.rssi_dbm; rssi_count++;
                    uint32_t seq = ((uint32_t)pkt_buf[0] << 24) |
                                   ((uint32_t)pkt_buf[1] << 16) |
                                   ((uint32_t)pkt_buf[2] << 8) | pkt_buf[3];
                    if (seq > last_seq) {
                        unique_rx++;
                        if (last_seq > 0 && seq > last_seq + 1)
                            lost_pkts += (seq - last_seq - 1);
                        last_seq = seq;
                    }
                    printf("RX_PKT seq=%lu rssi=%d snr=%d payload=%d br=%d\n",
                           (unsigned long)seq, status.rssi_dbm,
                           (int)status.snr_db, (int)status.length, BITRATE_KBPS);
                }
                radio.clear_irq();
            } else {
                radio.clear_irq();
            }
        }

        uint32_t now = esp_timer_get_time() / 1000;
        if (now - last_hb > HEARTBEAT_MS) {
            uint32_t elapsed = now - start_ms;
            float per = (total_rx + lost_pkts > 0)
                ? (100.0f * lost_pkts / (total_rx + lost_pkts)) : 0.0f;
            uint32_t tput = (unique_rx * PAYLOAD_SIZE * 8 * 1000) / elapsed;
            int16_t rssi_avg = (rssi_count > 0) ? (rssi_sum / rssi_count) : -127;
            printf("RX_STATS total=%lu unique=%lu lost=%lu per=%.1f throughput_kbps=%lu rssi_avg=%d payload=%d\n",
                   (unsigned long)total_rx, (unsigned long)unique_rx,
                   (unsigned long)lost_pkts, per,
                   (unsigned long)tput, rssi_avg, PAYLOAD_SIZE);
            last_hb = now;
            if (total_rx > 0) { led_off(); ets_delay_us(100); led_on(); }
        }
    }
}

#endif
