/*
 * P1.1 — LR2021 TX Test Firmware (numbered packets)
 * Target: ESP32-C3 Mini V1 (USB-CDC) + NiceRF LoRa2021 (Semtech LR2021 Gen 4)
 * Stack:  ESP-IDF v5.4.1 + RadioLib v7.6.0
 *
 * Radio: 868.0 MHz, LoRa BW500 / SF7 / CR4/5, sync 0x12, preamble 8, CRC on
 * Pins:  MOSI=7 MISO=2 SCLK=6 CS=10 RST=3 BUSY=4 IRQ(DIO9)=5
 *
 * Packet frame:  [ SEQ(4, big-endian) ][ PAYLOAD(N) ][ CRC16(2, big-endian) ]
 *   CRC16-CCITT (poly 0x1021, init 0xFFFF) computed over SEQ + PAYLOAD.
 *
 * Serial console (USB-CDC, 115200 nominal):
 *   START              - begin transmitting (uses current interval/count)
 *   STOP               - stop transmitting; emits TX_DONE
 *   SET interval=N     - inter-packet interval in ms (default 1000)
 *   SET count=N        - packets to send this run; N=0 = unlimited (default 10)
 *   STATUS             - report current state
 *   HELP               - list commands
 *
 * TX protocol output:
 *   TX,seq=<n>
 *   TX_DONE,total=<N>,sent=<M>,elapsed=<ms>ms
 *
 * Required sdkconfig (USB-CDC console):
 *   CONFIG_ESP_CONSOLE_USB_CDC=y
 *   CONFIG_ESP_CONSOLE_SECONDARY_NONE=y
 *
 * Build: this is an alternative main component. Reuses ../EspHalC3.h.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"

#include <RadioLib.h>
#include "EspHalC3.h"

static const char *TAG = "TXTEST";

// ---- LR2021 pinout (ESP32-C3 Mini V1 dev board) ---------------------------
#define PIN_MOSI   7
#define PIN_MISO   2
#define PIN_SCK    6
#define PIN_NSS   10
#define PIN_RST    3
#define PIN_BUSY   4
#define PIN_IRQ    5   // DIO9 — LoRa TxDone IRQ on LR2021

// ---- Radio configuration --------------------------------------------------
#define RADIO_FREQ_MHZ   868.0f
#define RADIO_BW_KHZ     500.0f
#define RADIO_SF         7
#define RADIO_CR         5        // 4/5
#define RADIO_SYNC       0x12
#define RADIO_PREAMBLE   8
#define TX_POWER_DBM     22       // reduce for bench / no-antenna testing

// ---- Packet framing -------------------------------------------------------
#define HEADER_LEN       4        // SEQ, big-endian
#define PAYLOAD_LEN      32       // N payload bytes
#define CRC_LEN          2        // CRC16, big-endian
#define PACKET_LEN       (HEADER_LEN + PAYLOAD_LEN + CRC_LEN)

// ---- Defaults -------------------------------------------------------------
#define DEFAULT_INTERVAL_MS  1000U
#define DEFAULT_COUNT        10

static EspHalC3 *hal = nullptr;
static LR2021   *radio = nullptr;

// ---- Run state ------------------------------------------------------------
// serial_task writes the control flags; tx_task reads them. Each flag/counter
// is a single 32-bit/bool written by only one task, so plain volatile access
// is sufficient on ESP32-C3 (no tearing, no need for a mutex here).
static volatile bool     g_running      = false;
static volatile uint32_t g_interval_ms  = DEFAULT_INTERVAL_MS;
static volatile int32_t  g_count_target = DEFAULT_COUNT;  // 0 = unlimited
static uint32_t          g_seq          = 0;              // monotonic across runs
static volatile uint32_t g_sent         = 0;              // packets sent this run

// ---- TX completion IRQ flag ----------------------------------------------
static volatile bool flag_tx_done = false;
static void IRAM_ATTR on_tx_done(void) { flag_tx_done = true; }

// ---- CRC16-CCITT (0x1021, init 0xFFFF) over SEQ + PAYLOAD -----------------
static uint16_t crc16_ccitt(const uint8_t *data, size_t len) {
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < len; i++) {
        crc ^= (uint16_t)data[i] << 8;
        for (int b = 0; b < 8; b++) {
            if (crc & 0x8000) crc = (uint16_t)((crc << 1) ^ 0x1021);
            else              crc = (uint16_t)(crc << 1);
        }
    }
    return crc;
}

// Build one numbered packet into buf. Returns PACKET_LEN.
static size_t build_packet(uint8_t *buf, uint32_t seq) {
    size_t i = 0;
    buf[i++] = (uint8_t)(seq >> 24);
    buf[i++] = (uint8_t)(seq >> 16);
    buf[i++] = (uint8_t)(seq >> 8);
    buf[i++] = (uint8_t)(seq);
    // Payload: deterministic pattern mixing index + seq so RX can verify
    // ordering / detect dropped or reordered packets.
    for (int p = 0; p < PAYLOAD_LEN; p++) {
        buf[i++] = (uint8_t)(0xA0u ^ (uint8_t)p ^ (uint8_t)(seq & 0xFF));
    }
    uint16_t crc = crc16_ccitt(buf, HEADER_LEN + PAYLOAD_LEN);
    buf[i++] = (uint8_t)(crc >> 8);
    buf[i++] = (uint8_t)(crc);
    return i;  // == PACKET_LEN
}

static int16_t init_radio(void) {
    hal = new EspHalC3(PIN_SCK, PIN_MISO, PIN_MOSI);
    hal->setCsPin(PIN_NSS);
    hal->setBusyPin(PIN_BUSY);

    radio = new LR2021(new Module(hal, PIN_NSS, PIN_IRQ, PIN_RST, PIN_BUSY));
    radio->irqDioNum = 9;   // DIO9 carries the LoRa TxDone IRQ on LR2021

    ESP_LOGI(TAG, "LR2021 begin: %.1f MHz BW%.0f SF%d CR4/5 sync 0x%02X",
             (double)RADIO_FREQ_MHZ, (double)RADIO_BW_KHZ, RADIO_SF, RADIO_SYNC);

    int16_t st = radio->begin(RADIO_FREQ_MHZ, RADIO_BW_KHZ, RADIO_SF, RADIO_CR,
                              RADIO_SYNC, TX_POWER_DBM, RADIO_PREAMBLE, 0.0f);
    if (st != RADIOLIB_ERR_NONE) {
        ESP_LOGE(TAG, "radio->begin failed: %d", st);
        return st;
    }
    // CRC is enabled by default inside begin() (setCRC(2)); assert explicitly.
    radio->setCRC(2);
    radio->setPacketSentAction(on_tx_done);
    return RADIOLIB_ERR_NONE;
}

static void handle_command(const char *raw) {
    while (*raw == ' ' || *raw == '\t') raw++;   // ltrim
    if (*raw == 0) return;

    if (strcmp(raw, "START") == 0) {
        g_sent = 0;
        g_running = true;
        printf("OK,START interval=%ums count=%d\n",
               (unsigned)g_interval_ms, (int)g_count_target);
    } else if (strcmp(raw, "STOP") == 0) {
        // tx_task emits TX_DONE when it observes the running->stopped edge.
        g_running = false;
    } else if (strncmp(raw, "SET interval=", 13) == 0) {
        long v = atol(raw + 13);
        if (v < 0) { printf("ERR,bad_interval\n"); fflush(stdout); return; }
        g_interval_ms = (uint32_t)v;
        printf("OK,interval=%ums\n", (unsigned)g_interval_ms);
    } else if (strncmp(raw, "SET count=", 10) == 0) {
        long v = atol(raw + 10);
        if (v < 0) { printf("ERR,bad_count\n"); fflush(stdout); return; }
        g_count_target = (int32_t)v;
        printf("OK,count=%d (0=unlimited)\n", (int)g_count_target);
    } else if (strcmp(raw, "STATUS") == 0) {
        printf("STATUS,running=%d,seq=%u,sent=%u,interval=%ums,count=%d\n",
               (int)g_running, (unsigned)g_seq, (unsigned)g_sent,
               (unsigned)g_interval_ms, (int)g_count_target);
    } else if (strcmp(raw, "HELP") == 0 || strcmp(raw, "?") == 0) {
        printf("CMD: START | STOP | SET interval=<ms> | SET count=<N> | STATUS | HELP\n");
        printf("  count=0 => unlimited. Default interval=%ums count=%d\n",
               DEFAULT_INTERVAL_MS, DEFAULT_COUNT);
    } else {
        printf("ERR,unknown: '%s'\n", raw);
    }
    fflush(stdout);
}

// Reads serial lines (USB-CDC), parses commands, mutates run state.
static void serial_task(void *) {
    char line[128];
    while (true) {
        if (fgets(line, sizeof(line), stdin) == NULL) {
            vTaskDelay(pdMS_TO_TICKS(10));
            continue;
        }
        size_t n = strlen(line);
        while (n > 0 && (line[n-1] == '\n' || line[n-1] == '\r')) line[--n] = 0;
        handle_command(line);
    }
}

// Transmits numbered packets at g_interval_ms while g_running is true.
static void tx_task(void *) {
    bool     was_running    = false;
    uint32_t last_tx_ms     = 0;
    uint32_t run_start_ms   = 0;

    while (true) {
        bool now_running = g_running;

        // Run-start edge: record start time, force an immediate first TX.
        if (now_running && !was_running) {
            run_start_ms = hal->millis();
            last_tx_ms   = 0;          // 0 => transmit immediately on first check
            was_running  = true;
        }

        if (now_running) {
            uint32_t now = hal->millis();
            bool due = (last_tx_ms == 0) ||
                       ((uint32_t)(now - last_tx_ms) >= g_interval_ms);
            if (due) {
                last_tx_ms = now;

                uint8_t buf[PACKET_LEN];
                build_packet(buf, g_seq);

                printf("TX,seq=%u\n", (unsigned)g_seq);
                fflush(stdout);

                flag_tx_done = false;
                int16_t st = radio->startTransmit(buf, PACKET_LEN);
                if (st == RADIOLIB_ERR_NONE) {
                    uint32_t to = 0;
                    while (!flag_tx_done && to < 5000) { hal->delay(1); to++; }
                    if (!flag_tx_done) {
                        printf("ERR,tx_timeout,seq=%u\n", (unsigned)g_seq);
                        fflush(stdout);
                    }
                } else {
                    printf("ERR,tx_failed=%d,seq=%u\n", st, (unsigned)g_seq);
                    fflush(stdout);
                }

                g_seq++;
                g_sent++;

                // Natural completion when a finite count was requested.
                if (g_count_target > 0 && g_sent >= (uint32_t)g_count_target) {
                    uint32_t elapsed = (uint32_t)(hal->millis() - run_start_ms);
                    printf("TX_DONE,total=%u,sent=%u,elapsed=%ums\n",
                           (unsigned)g_count_target, (unsigned)g_sent,
                           (unsigned)elapsed);
                    fflush(stdout);
                    g_running   = false;
                    was_running = false;
                }
            }
        }

        // Run-stop edge (STOP command, or natural completion already handled
        // above): emit a TX_DONE summary for the packets actually sent.
        if (!now_running && was_running) {
            uint32_t elapsed = (uint32_t)(hal->millis() - run_start_ms);
            uint32_t total = (g_count_target > 0) ? (uint32_t)g_count_target
                                                  : g_sent;
            printf("TX_DONE,total=%u,sent=%u,elapsed=%ums\n",
                   total, (unsigned)g_sent, (unsigned)elapsed);
            fflush(stdout);
            was_running = false;
        }

        vTaskDelay(pdMS_TO_TICKS(5));
    }
}

extern "C" void app_main(void) {
    setvbuf(stdout, NULL, _IONBF, 0);
    vTaskDelay(pdMS_TO_TICKS(500));

    printf("\n\n=== LR2021 TX Test Firmware (P1.1) ===\n");
    printf("Radio: 868.0 MHz, LoRa BW500 SF7 CR4/5, sync 0x12, preamble 8, CRC on\n");
    printf("Pins:  MOSI=%d MISO=%d SCLK=%d CS=%d RST=%d BUSY=%d IRQ=%d\n",
           PIN_MOSI, PIN_MISO, PIN_SCK, PIN_NSS, PIN_RST, PIN_BUSY, PIN_IRQ);
    printf("Frame: SEQ(4 BE) + PAYLOAD(%d) + CRC16(2) = %d bytes\n",
           PAYLOAD_LEN, PACKET_LEN);
    printf("Defaults: interval=%ums count=%d (0=unlimited)\n",
           DEFAULT_INTERVAL_MS, DEFAULT_COUNT);
    printf("Type HELP for commands.\n\n");
    fflush(stdout);

    int16_t st = init_radio();
    if (st != RADIOLIB_ERR_NONE) {
        printf("FATAL,radio_init=%d\n", st);
        fflush(stdout);
        ESP_LOGE(TAG, "halting: radio init failed (%d)", st);
        while (true) vTaskDelay(pdMS_TO_TICKS(1000));
    }
    printf("OK,radio_ready\n\n");
    fflush(stdout);

    xTaskCreate(serial_task, "serial", 4096, NULL, 5, NULL);
    xTaskCreate(tx_task,     "tx",      4096, NULL, 5, NULL);
}
