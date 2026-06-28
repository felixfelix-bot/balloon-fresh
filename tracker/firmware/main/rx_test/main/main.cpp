/*
 * P1.2 - ESP32-C3 RX test firmware (baseline reference)
 *
 * Hardware : ESP32-C3_Mini_V1 dev board + NiceRF LoRa2021 (Semtech LR2021 Gen 4)
 * Stack    : ESP-IDF v5.4.1 + RadioLib v7.6.0 (managed component)
 * Mode     : RX-only
 *
 * Radio config (per task spec):
 *   freq 868.0 MHz | LoRa BW500 / SF7 / CR4/5 | sync 0x12 | preamble 8 | CRC on
 *
 * Pins (ESP32-C3_Mini_V1, matches AGENTS.md NiceRF mapping):
 *   GPIO7=MOSI GPIO2=MISO GPIO6=SCLK GPIO10=CS(GPIO10)
 *   GPIO3=Rst   GPIO4=BUSY   GPIO5=DIO9(IRQ)
 *
 * Assumed baseline test frame (documented so P1.1 TX side can match):
 *   bytes [0..1] = uint16_t sequence counter (little-endian)
 *   bytes [2..]  = payload (length is echoed; content ignored for stats)
 *
 * Serial protocol (CSV, one line per event, newline terminated):
 *   RX,seq=N,rssi=X,dt_ms=Y,len=Z        <- every good packet received
 *   STATS,received=A,lost=B,crc_err=C,rssi_min=D,rssi_avg=E,rssi_max=F
 *   OK,rx=STARTED | OK,rx=ALREADY_RUNNING | OK,rx=STOPPED(s) | OK,stats=RESET
 *   ERR,unknown_cmd
 *
 * Console commands (case-insensitive, line terminated):
 *   START  - resume receiving (default state at boot)
 *   STOP   - stop receiving (put radio in standby)
 *   STATS  - print cumulative statistics line
 *   RESET  - zero the statistics counters
 */

#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_timer.h"

#include <RadioLib.h>
#include "EspHalC3.h"

static const char *TAG = "RX_TEST";

/* ---- LR2021 pinout (ESP32-C3_Mini_V1 dev board) ---- */
#define LR2021_SCK   6
#define LR2021_MISO  2
#define LR2021_MOSI  7
#define LR2021_NSS   10   /* CS */
#define LR2021_BUSY  4
#define LR2021_RST   3
#define LR2021_DIO9  5    /* IRQ */

/* ---- Radio configuration (task spec) ---- */
#define RX_FREQ_MHZ      2450.0f
typedef.0f
#define RX_SF            7
#define RX_CR            5      /* RadioLib: 5 -> 4/5, 6 -> 4/6, 7 -> 4/7, 8 -> 4/8 */
#define RX_SYNC_WORD     0x12
#define RX_PREAMBLE      8
#define RX_POWER_DBM     22     /* irrelevant for RX-only; kept as a valid config value */

#define RX_BUF_SIZE 256

/* ---- Radio handles ---- */
static EspHalC3 *hal = nullptr;
static LR2021   *radio = nullptr;

/* ---- RX control flags ---- */
static volatile bool flag_rx_done = false;   /* set by DIO9 ISR */
static volatile bool rx_enabled = true;      /* START / STOP */

/* ---- Statistics (protected by stats_lock; read by STATS command) ---- */
struct rx_stats_t {
    uint32_t received;     /* good packets received */
    uint32_t crc_errors;   /* readData failures (typically CRC / header damage) */
    uint32_t lost;         /* estimated lost = sum of forward sequence gaps */
    int16_t  rssi_min;
    int16_t  rssi_max;
    int64_t  rssi_sum;     /* running sum for averaging (avoids float) */
    uint32_t rssi_count;
    uint16_t last_seq;
    bool     have_last_seq;
};

static rx_stats_t    stats;
static portMUX_TYPE  stats_lock = portMUX_INITIALIZER_UNLOCKED;

static void stats_reset(void) {
    portENTER_CRITICAL(&stats_lock);
    memset(&stats, 0, sizeof(stats));
    portEXIT_CRITICAL(&stats_lock);
}

static void IRAM_ATTR on_rx_done(void) {
    flag_rx_done = true;
}

static void restart_receive(void) {
    int16_t state = radio->startReceive();
    if (state != RADIOLIB_ERR_NONE) {
        ESP_LOGE(TAG, "startReceive failed: %d", state);
    }
}

static void print_stats(void) {
    portENTER_CRITICAL(&stats_lock);
    uint32_t rxd   = stats.received;
    uint32_t crc   = stats.crc_errors;
    uint32_t lost  = stats.lost;
    int16_t  rmin  = stats.rssi_min;
    int16_t  rmax  = stats.rssi_max;
    int64_t  rsum  = stats.rssi_sum;
    uint32_t rcnt  = stats.rssi_count;
    portEXIT_CRITICAL(&stats_lock);

    int16_t ravg = (rcnt > 0) ? (int16_t)(rsum / (int64_t)rcnt) : 0;
    printf("STATS,received=%u,lost=%u,crc_err=%u,rssi_min=%d,rssi_avg=%d,rssi_max=%d\n",
           (unsigned)rxd, (unsigned)lost, (unsigned)crc, (int)rmin, (int)ravg, (int)rmax);
    fflush(stdout);
}

/* Case-insensitive compare of one console line against a command keyword.
 * Trailing CR/LF/space/tab are tolerated; anything else means no match. */
static bool cmd_equals(const char *line, const char *cmd) {
    size_t i = 0;
    while (cmd[i] != '\0') {
        char c = line[i];
        if (c == '\0') return false;
        if (c >= 'a' && c <= 'z') c = (char)(c - 32);
        if (c != cmd[i]) return false;
        i++;
    }
    char c = line[i];
    return (c == '\0' || c == '\n' || c == '\r' || c == ' ' || c == '\t');
}

/* Console command parser task. Reads line-by-line from stdin (console VFS). */
static void command_task(void *) {
    char line[64];
    while (true) {
        if (fgets(line, sizeof(line), stdin) != nullptr) {
            if (cmd_equals(line, "START")) {
                if (!rx_enabled) {
                    rx_enabled = true;
                    restart_receive();
                    printf("OK,rx=STARTED\n");
                } else {
                    printf("OK,rx=ALREADY_RUNNING\n");
                }
                fflush(stdout);
            } else if (cmd_equals(line, "STOP")) {
                rx_enabled = false;
                int16_t s = radio->standby();
                printf("OK,rx=STOPPED(%d)\n", (int)s);
                fflush(stdout);
            } else if (cmd_equals(line, "STATS")) {
                print_stats();
            } else if (cmd_equals(line, "RESET")) {
                stats_reset();
                printf("OK,stats=RESET\n");
                fflush(stdout);
            } else if (line[0] != '\0' && line[0] != '\n' && line[0] != '\r') {
                printf("ERR,unknown_cmd\n");
                fflush(stdout);
            }
        }
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

/* Handle one successfully-read packet: emit the RX line and update stats. */
static void handle_packet(const uint8_t *buf, size_t len, int16_t rssi) {
    bool     have_seq = (len >= 2);
    uint16_t seq = 0;
    if (have_seq) {
        seq = (uint16_t)buf[0] | ((uint16_t)buf[1] << 8);
    }

    /* Timing: ms since boot and delta since previous packet. */
    uint32_t now_ms = (uint32_t)(esp_timer_get_time() / 1000);
    static uint32_t last_pkt_ms = 0;
    uint32_t dt = (last_pkt_ms != 0) ? (now_ms - last_pkt_ms) : 0;
    last_pkt_ms = now_ms;

    printf("RX,seq=%u,rssi=%d,dt_ms=%u,len=%u\n",
           have_seq ? (unsigned)seq : 0u, (int)rssi, (unsigned)dt, (unsigned)len);
    fflush(stdout);

    portENTER_CRITICAL(&stats_lock);
    stats.received++;
    if (stats.rssi_count == 0 || rssi < stats.rssi_min) stats.rssi_min = rssi;
    if (stats.rssi_count == 0 || rssi > stats.rssi_max) stats.rssi_max = rssi;
    stats.rssi_sum   += rssi;
    stats.rssi_count++;

    if (have_seq) {
        if (stats.have_last_seq) {
            int32_t diff = (int32_t)seq - (int32_t)stats.last_seq;
            /* forward gap counts as lost packets; backward/out-of-order is ignored.
             * NOTE: a gap that straddles the uint16 wraparound is not detected
             * (acceptable for a baseline reference). */
            if (diff > 0) {
                stats.lost += (uint32_t)(diff - 1);
            }
        }
        stats.last_seq      = seq;
        stats.have_last_seq = true;
    }
    portEXIT_CRITICAL(&stats_lock);
}

extern "C" void app_main(void) {
    ESP_LOGI(TAG, "=== P1.2 ESP32 RX Test Firmware (baseline) ===");
    ESP_LOGI(TAG, "Radio: LR2021 @ %.1f MHz BW%.0f SF%d CR4/5 sync=0x%02X preamble=%u CRC=on",
             RX_FREQ_MHZ, RX_BW_KHZ, RX_SF, RX_SYNC_WORD, RX_PREAMBLE);

    hal   = new EspHalC3(LR2021_SCK, LR2021_MISO, LR2021_MOSI);
    radio = new LR2021(new Module(hal, LR2021_NSS, LR2021_DIO9, LR2021_RST, LR2021_BUSY));
    radio->irqDioNum = 9;   /* DIO9 used as the LoRa packet-received IRQ */

    ESP_LOGI(TAG, "Initializing LR2021...");
    int16_t state = radio->begin(RX_FREQ_MHZ, RX_BW_KHZ, RX_SF, RX_CR,
                                 RX_SYNC_WORD, RX_POWER_DBM, RX_PREAMBLE, 0.0f);
    if (state != RADIOLIB_ERR_NONE) {
        ESP_LOGE(TAG, "LR2021 begin failed: %d", state);
        while (true) { hal->delay(1000); }
    }

    state = radio->setFrequency(RX_FREQ_MHZ, true);
    if (state != RADIOLIB_ERR_NONE) {
        ESP_LOGE(TAG, "setFrequency failed: %d", state);
    }

    /* CRC explicitly enabled (RadioLib LoRa default is on; reinforced for baseline). */
    state = radio->setCrc(true);
    if (state != RADIOLIB_ERR_NONE) {
        ESP_LOGW(TAG, "setCrc returned %d", state);
    }

    radio->setPacketReceivedAction(on_rx_done);

    state = radio->startReceive();
    if (state != RADIOLIB_ERR_NONE) {
        ESP_LOGE(TAG, "startReceive failed: %d", state);
        while (true) { hal->delay(1000); }
    }

    ESP_LOGI(TAG, "Listening on %.1f MHz. Commands: START STOP STATS RESET", RX_FREQ_MHZ);

    /* Spawn the console command parser. */
    xTaskCreate(command_task, "cmd", 4096, nullptr, 5, nullptr);

    uint8_t buf[RX_BUF_SIZE];
    while (true) {
        if (rx_enabled && flag_rx_done) {
            flag_rx_done = false;

            size_t pktLen = radio->getPacketLength();
            if (pktLen > 0 && pktLen <= RX_BUF_SIZE) {
                int16_t r = radio->readData(buf, pktLen);
                int16_t rssi = radio->getRSSI();
                if (r == RADIOLIB_ERR_NONE) {
                    handle_packet(buf, pktLen, rssi);
                } else {
                    /* Negative status typically means CRC/header damage. */
                    ESP_LOGW(TAG, "readData err=%d rssi=%d (CRC/header?)", r, rssi);
                    portENTER_CRITICAL(&stats_lock);
                    stats.crc_errors++;
                    portEXIT_CRITICAL(&stats_lock);
                }
            } else {
                ESP_LOGW(TAG, "Invalid pktLen=%u", (unsigned)pktLen);
            }

            radio->standby();
            if (rx_enabled) {
                restart_receive();
            }
        }
        vTaskDelay(pdMS_TO_TICKS(2));
    }
}
