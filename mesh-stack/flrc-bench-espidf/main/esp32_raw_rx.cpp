/*
 * esp32_raw_rx.cpp — ESP32 FLRC RX with RAW SPI init + DIO9 polling
 *
 * Direct port of RP2040 flrc_rx_raw.cpp. No RadioLib for init.
 * Uses raw SPI register writes (same 13-step sequence as RP2040).
 * Polls DIO9 pin (GPIO5) instead of GPIO interrupts.
 *
 * Pins: SCK=6 MISO=2 MOSI=7 NSS=10 BUSY=4 RST=3 DIO9=5 LED=8
 */

#include <sdkconfig.h>

#ifdef CONFIG_BENCH_MODE_RAW_RX

#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "driver/gpio.h"
#include "driver/usb_serial_jtag.h"
#include "driver/usb_serial_jtag_vfs.h"
#include <RadioLib.h>
#include "EspHalC3.h"

static const char *TAG = "RAWRX";

// ─── Pins ────────────────────────────────────────────────────────────
#define PIN_SCK     6
#define PIN_MOSI    7
#define PIN_MISO    2
#define PIN_NSS     10
#define PIN_BUSY    4
#define PIN_RST     3
#define PIN_DIO9    5
#define PIN_LED     8

// ─── FLRC Config ─────────────────────────────────────────────────────
#define FLRC_FREQ_HZ   2440.0f
#define FLRC_PKT_SIZE  255
#define RX_LISTEN_MS   30000
#define RX_SILENCE_MS  5000
#define PRINT_EVERY    50

// ─── ESP32 HAL ───────────────────────────────────────────────────────
static EspHalC3 *hal = nullptr;

// ─── Raw SPI helpers ─────────────────────────────────────────────────
static inline void rfWaitBusy() {
    uint32_t timeout = esp_timer_get_time() + 50000; // 50ms timeout
    while (gpio_get_level((gpio_num_t)PIN_BUSY) == 1) {
        if (esp_timer_get_time() > timeout) return;
    }
}

static void rfWriteCmd(const uint8_t *buf, size_t len) {
    rfWaitBusy();
    gpio_set_level((gpio_num_t)PIN_NSS, 0);
    hal->spiTransfer(const_cast<uint8_t*>(buf), len, nullptr);
    gpio_set_level((gpio_num_t)PIN_NSS, 1);
}

static void rfReadCmd(const uint8_t *cmd, size_t cmdLen, uint8_t *out, size_t outLen) {
    rfWaitBusy();
    gpio_set_level((gpio_num_t)PIN_NSS, 0);
    hal->spiTransfer(const_cast<uint8_t*>(cmd), cmdLen, nullptr);
    hal->spiTransfer(nullptr, outLen, out);
    gpio_set_level((gpio_num_t)PIN_NSS, 1);
}

static uint8_t rfReadStatus() {
    uint8_t st = 0;
    rfWaitBusy();
    gpio_set_level((gpio_num_t)PIN_NSS, 0);
    hal->spiTransfer(nullptr, 1, &st);
    gpio_set_level((gpio_num_t)PIN_NSS, 1);
    return st;
}

// ─── RX hot path helpers (single CS session FIFO read) ───────────────
// LR2021 READ_RX_FIFO = 0x0001. Keep NSS low for the whole transaction:
// send opcode, then read status bytes + payload in one continuous burst.
// This matches the RP2040 pattern (flrc_raw_rx.cpp:74-85) and removes
// the extra rfWaitBusy() + CS toggle that cost ~30 us/pkt.
static void rfReadFifo(uint8_t *buf, size_t len) {
    rfWaitBusy();
    gpio_set_level((gpio_num_t)PIN_NSS, 0);

    uint8_t cmd[] = {0x00, 0x01};
    hal->spiTransfer(cmd, 2, nullptr);       // send READ_RX_FIFO opcode

    uint8_t status[2];
    hal->spiTransfer(nullptr, 2, status);    // 2 status/status-response bytes
    hal->spiTransfer(nullptr, len, buf);     // payload

    gpio_set_level((gpio_num_t)PIN_NSS, 1);
}

static uint32_t rfReadIrqStatus() {
    // GET_AND_CLEAR_IRQ_STATUS = 0x0117
    rfWaitBusy();
    gpio_set_level((gpio_num_t)PIN_NSS, 0);
    uint8_t cmd[] = {0x01, 0x17};
    hal->spiTransfer(cmd, 2, nullptr);
    gpio_set_level((gpio_num_t)PIN_NSS, 1);
    rfWaitBusy();

    uint8_t buf[6];
    gpio_set_level((gpio_num_t)PIN_NSS, 0);
    hal->spiTransfer(nullptr, 6, buf);
    gpio_set_level((gpio_num_t)PIN_NSS, 1);
    return ((uint32_t)buf[2] << 24) | ((uint32_t)buf[3] << 16) |
           ((uint32_t)buf[4] << 8) | (uint32_t)buf[5];
}

static void rfClearIrq() {
    uint8_t cmd[] = {0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF};
    rfWriteCmd(cmd, 6);
}

static void rfSetRx() {
    uint8_t cmd[] = {0x02, 0x0C, 0x00, 0xFF, 0xFF, 0xFF};
    rfWriteCmd(cmd, 6);
}

// ─── Raw SPI Init (matches RP2040 flrc_rx_raw.cpp) ───────────────────
static bool rawInitRadio() {
    // Step 0: Hardware reset
    gpio_set_level((gpio_num_t)PIN_RST, 0);
    vTaskDelay(pdMS_TO_TICKS(1));
    gpio_set_level((gpio_num_t)PIN_RST, 1);
    vTaskDelay(pdMS_TO_TICKS(50));

    // Step 1: SET_RF_FREQUENCY (0x0200) — freq in Hz, big-endian
    uint32_t rfFreq = (uint32_t)(FLRC_FREQ_HZ * 1000000.0f);
    {
        uint8_t cmd[] = {
            0x02, 0x00,
            (uint8_t)(rfFreq >> 24), (uint8_t)(rfFreq >> 16),
            (uint8_t)(rfFreq >> 8),  (uint8_t)(rfFreq & 0xFF)
        };
        rfWriteCmd(cmd, 6);
    }
    vTaskDelay(pdMS_TO_TICKS(1));

    // Step 2: SET_RX_PATH (0x0201) — HF path for 2.4 GHz
    {
        uint8_t cmd[] = {0x02, 0x01, 0x01};
        rfWriteCmd(cmd, 3);
    }
    vTaskDelay(pdMS_TO_TICKS(1));

    // Step 3: CALIBRATE (0x0122) — all defined blocks = 0x5F
    {
        uint8_t cmd[] = {0x01, 0x22, 0x5F};
        rfWriteCmd(cmd, 3);
    }
    vTaskDelay(pdMS_TO_TICKS(5));
    rfWaitBusy();

    // Step 4: CALIB_FE (0x0123) — front-end calibration
    {
        uint8_t cmd[] = {0x01, 0x23, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};
        rfWriteCmd(cmd, 8);
    }
    vTaskDelay(pdMS_TO_TICKS(5));
    rfWaitBusy();

    // Step 5: SET_PACKET_TYPE (0x0207) — FLRC=5
    {
        uint8_t cmd[] = {0x02, 0x07, 0x05};
        rfWriteCmd(cmd, 3);
    }
    vTaskDelay(pdMS_TO_TICKS(1));

    // Step 6: SET_FLRC_MODULATION_PARAMS (0x0248)
    // Br2600=2, Bt0p5=5 → byte3 = (2<<4)|5 = 0x25
    {
        uint8_t cmd[] = {0x02, 0x48, 0x00, 0x25};
        rfWriteCmd(cmd, 4);
    }
    vTaskDelay(pdMS_TO_TICKS(1));

    // Step 7: SET_FLRC_SYNCWORD (0x024C) — 32-bit sync word at slot 1
    {
        uint8_t cmd[] = {
            0x02, 0x4C,
            0x01,               // sw_num = 1
            0xCD, 0x05, 0xCA, 0xFE  // syncword MSB first
        };
        rfWriteCmd(cmd, 7);
    }
    vTaskDelay(pdMS_TO_TICKS(1));

    // Step 8: SET_FLRC_PACKET_PARAMS (0x0249)
    // 16b preamble, 32b SW, SwTx=0(RX), Match1, Fixed, CRC_OFF, PLD=255
    // byte2 = (agc_pbl_len << 2) | sw_len = (3<<2)|2 = 0x0E
    // byte3 = (sw_tx<<6)|(sw_match<<3)|(pkt_fmt<<2)|crc = (0<<6)|(1<<3)|(1<<2)|0 = 0x0C
    //         NOTE: sw_tx=0 for RX (we receive syncwords, don't transmit them)
    {
        uint8_t cmd[] = {
            0x02, 0x49,
            0x0E,   // 16b preamble (3<<2) | 32b SW (2)
            0x0C,   // SwTx=0(RX) | Match1(1<<3) | Fixed(1) | CRC_OFF(0)
            0x00, 0xFF  // pld_len = 255
        };
        rfWriteCmd(cmd, 6);
    }
    vTaskDelay(pdMS_TO_TICKS(1));

    // Step 9: SET_RX_TX_FALLBACK_MODE (0x0206) — Fs=3
    {
        uint8_t cmd[] = {0x02, 0x06, 0x03};
        rfWriteCmd(cmd, 3);
    }
    vTaskDelay(pdMS_TO_TICKS(1));

    // Step 10: SET_DIO_FUNCTION (0x0112) — DIO9 = IRQ
    {
        uint8_t cmd[] = {0x01, 0x12, 0x09, 0x11};
        rfWriteCmd(cmd, 4);
    }
    vTaskDelay(pdMS_TO_TICKS(1));

    // Step 11: SET_DIO_IRQ_CONFIG (0x0115) — RX_DONE to DIO9
    // RX_DONE=bit18=0x00040000 → 0x00040000
    {
        uint8_t cmd[] = {0x01, 0x15, 0x09, 0x00, 0x04, 0x00, 0x00};
        rfWriteCmd(cmd, 7);
    }
    vTaskDelay(pdMS_TO_TICKS(1));

    // Step 12: CLEAR_IRQ (0x0116) — clear all
    rfClearIrq();
    vTaskDelay(pdMS_TO_TICKS(1));

    // Step 13: SET_RX (0x020C) — enter RX continuous
    {
        uint8_t cmd[] = {0x02, 0x0C};
        rfWriteCmd(cmd, 2);
    }
    vTaskDelay(pdMS_TO_TICKS(1));

    // Verify
    uint8_t st = rfReadStatus();
    ESP_LOGI(TAG, "Init done. Status=0x%02X", st);

    uint8_t mode = (st >> 4) & 0x0F;
    if (mode == 0x02 || mode == 0x03 || mode == 0x06) {
        return true;
    }
    return (st != 0x00 && st != 0xFF);
}

// ─── Statistics ──────────────────────────────────────────────────────
struct RxStats {
    uint32_t received;
    uint32_t unique;
    uint32_t duplicates;
    uint32_t lastSeq;
    uint32_t maxSeq;
    uint32_t totalSentByTx;
    uint32_t startMs;
    uint32_t elapsedMs;
};

static RxStats stats;

static void resetStats() {
    memset(&stats, 0, sizeof(stats));
    stats.lastSeq = 0xFFFFFFFF;
}

// ─── Receive session ─────────────────────────────────────────────────
static bool radioReady = false;

static void runReceive() {
    if (!radioReady) {
        printf("ERR: radio not initialized\n");
        fflush(stdout);
        return;
    }

    resetStats();
    stats.startMs = (uint32_t)(esp_timer_get_time() / 1000ULL);
    uint32_t lastPktMs = stats.startMs;
    uint8_t buf[FLRC_PKT_SIZE];

    // Clear stale IRQ and re-arm RX
    rfClearIrq();
    rfSetRx();
    vTaskDelay(pdMS_TO_TICKS(1));

    printf("RX_START listening for FLRC packets...\n");
    fflush(stdout);

    bool stopped = false;
    while (!stopped) {
        uint32_t now = (uint32_t)(esp_timer_get_time() / 1000ULL);

        if ((now - stats.startMs) >= RX_LISTEN_MS) {
            printf("RX_TIMEOUT: listen window expired\n");
            stopped = true;
            break;
        }
        if (stats.received > 0 && (now - lastPktMs) >= RX_SILENCE_MS) {
            printf("RX_TIMEOUT: silence, stopping\n");
            stopped = true;
            break;
        }

        // KEY FIX: Poll DIO9 pin (no GPIO interrupt!)
        if (gpio_get_level((gpio_num_t)PIN_DIO9) != 1) {
            taskYIELD();
            continue;
        }

        // DIO9 HIGH = packet received (or other IRQ)
        uint32_t irqFlags = rfReadIrqStatus();

        // Read FIFO (single CS session, matches RP2040 pattern)
        rfReadFifo(buf, FLRC_PKT_SIZE);

        // Clear IRQ (de-asserts DIO9)
        rfClearIrq();

        // Re-arm RX
        rfSetRx();

        // Extract big-endian seq from first 4 bytes
        uint32_t seq = ((uint32_t)buf[0] << 24) | ((uint32_t)buf[1] << 16) |
                       ((uint32_t)buf[2] << 8)  | (uint32_t)buf[3];

        // DEADBEEF end marker
        if (buf[0] == 0xDE && buf[1] == 0xAD &&
            buf[2] == 0xBE && buf[3] == 0xEF) {
            stats.totalSentByTx = ((uint32_t)buf[4] << 24) | ((uint32_t)buf[5] << 16) |
                                  ((uint32_t)buf[6] << 8)  | (uint32_t)buf[7];
            stats.elapsedMs = (uint32_t)(esp_timer_get_time() / 1000ULL) - stats.startMs;
            printf("RX_END: received DEADBEEF end marker\n");
            fflush(stdout);
            break;
        }

        stats.received++;
        if (stats.lastSeq != 0xFFFFFFFF && seq == stats.lastSeq) {
            stats.duplicates++;
        } else {
            stats.unique++;
        }
        stats.lastSeq = seq;
        if (seq > stats.maxSeq) stats.maxSeq = seq;
        lastPktMs = (uint32_t)(esp_timer_get_time() / 1000ULL);

        // Progress output
        if (stats.received <= 5 || (stats.received % PRINT_EVERY) == 0) {
            ESP_LOGI(TAG, "PKT rx=%lu seq=%lu IRQ=0x%08lX",
                     (unsigned long)stats.received, (unsigned long)seq,
                     (unsigned long)irqFlags);
        }
    }

    if (stats.elapsedMs == 0)
        stats.elapsedMs = (uint32_t)(esp_timer_get_time() / 1000ULL) - stats.startMs;

    // Print results
    uint32_t n = stats.received;
    uint32_t total = stats.totalSentByTx > 0 ? stats.totalSentByTx : (stats.maxSeq + 1);
    uint32_t lost = (total > n) ? (total - n) : 0;
    float perPct = (total > 0) ? (100.0f * (float)lost / (float)total) : 0.0f;
    float tputKbps = (stats.elapsedMs > 0 && n > 0)
                     ? ((float)n * (float)FLRC_PKT_SIZE * 8.0f) / ((float)stats.elapsedMs)
                     : 0.0f;

    printf("=============================================\n");
    printf("  Received:    %lu (unique %lu, dup %lu)\n",
           (unsigned long)n, (unsigned long)stats.unique,
           (unsigned long)stats.duplicates);
    printf("  TX sent:     %lu  (est total %lu)\n",
           (unsigned long)stats.totalSentByTx, (unsigned long)total);
    printf("  Lost:        %lu  (%.2f%%)\n", (unsigned long)lost, perPct);
    printf("  Elapsed:     %lu ms\n", (unsigned long)stats.elapsedMs);
    printf("  Throughput:  %.1f kbps\n", tputKbps);
    printf("=============================================\n");
    printf("RESULT,rx=%lu,unique=%lu,dup=%lu,lost=%lu,total=%lu,per=%.2f,elapsed_ms=%lu,throughput_kbps=%.1f\n",
           (unsigned long)n, (unsigned long)stats.unique, (unsigned long)stats.duplicates,
           (unsigned long)lost, (unsigned long)total, perPct,
           (unsigned long)stats.elapsedMs, tputKbps);
    fflush(stdout);
}

// ─── App main ────────────────────────────────────────────────────────
extern "C" void app_main() {
    setvbuf(stdout, NULL, _IONBF, 0);
    vTaskDelay(pdMS_TO_TICKS(500));

    // Init LED first
    gpio_config_t ledConf = {};
    ledConf.pin_bit_mask = (1ULL << PIN_LED);
    ledConf.mode = GPIO_MODE_OUTPUT;
    gpio_config(&ledConf);
    gpio_set_level((gpio_num_t)PIN_LED, 1); // LED off (active low)

    // Boot blink with early printf checks
    for (int i = 0; i < 3; i++) {
        printf("BOOT %d\n", i+1);
        fflush(stdout);
        gpio_set_level((gpio_num_t)PIN_LED, 0);
        vTaskDelay(pdMS_TO_TICKS(200));
        gpio_set_level((gpio_num_t)PIN_LED, 1);
        vTaskDelay(pdMS_TO_TICKS(200));
    }
    printf("HELLO FROM ESP32 RAW_RX\n");
    fflush(stdout);

    // Init radio pins first, then SPI HAL
    gpio_config_t csConf = {};
    csConf.pin_bit_mask = (1ULL << PIN_NSS);
    csConf.mode = GPIO_MODE_OUTPUT;
    gpio_config(&csConf);
    gpio_set_level((gpio_num_t)PIN_NSS, 1);

    gpio_config_t busyConf = {};
    busyConf.pin_bit_mask = (1ULL << PIN_BUSY);
    busyConf.mode = GPIO_MODE_INPUT;
    gpio_config(&busyConf);

    gpio_config_t dioConf = {};
    dioConf.pin_bit_mask = (1ULL << PIN_DIO9);
    dioConf.mode = GPIO_MODE_INPUT;
    gpio_config(&dioConf);

    gpio_config_t rstConf = {};
    rstConf.pin_bit_mask = (1ULL << PIN_RST);
    rstConf.mode = GPIO_MODE_OUTPUT;
    gpio_config(&rstConf);
    gpio_set_level((gpio_num_t)PIN_RST, 1);

    // Init SPI HAL
    hal = new EspHalC3(PIN_SCK, PIN_MISO, PIN_MOSI);
    hal->init();  // MUST call init() — no RadioLib Module to do it for us
    hal->setCsPin(PIN_NSS);
    hal->setBusyPin(PIN_BUSY);

    printf("HELLO FROM ESP32 RAW_RX\n");
    fflush(stdout);

    printf("\n");
    printf("=================================================\n");
    printf("  ESP32 FLRC RX (RAW SPI + DIO9 POLL)\n");
    printf("  No RadioLib, no interrupts — raw SPI + pin poll\n");
    printf("  Freq=%.1f MHz, 255B fixed, syncword=CD05CAFE\n", FLRC_FREQ_HZ);
    printf("=================================================\n");
    printf("\n");
    fflush(stdout);

    // Init radio
    radioReady = rawInitRadio();
    if (radioReady) {
        ESP_LOGI(TAG, "RADIO_INIT_OK");
        printf("RADIO_INIT_OK\n");
    } else {
        ESP_LOGE(TAG, "RADIO_INIT_FAILED");
        printf("RADIO_INIT_FAILED\n");
    }
    fflush(stdout);

    // Wait for stabilization then start receiving
    ESP_LOGI(TAG, "RX starts in 3s...");
    vTaskDelay(pdMS_TO_TICKS(3000));

    while (true) {
        runReceive();
        ESP_LOGI(TAG, "Next RX window in 5s...");
        vTaskDelay(pdMS_TO_TICKS(5000));
    }
}

#endif
