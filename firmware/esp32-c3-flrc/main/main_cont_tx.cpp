/*
 * main_cont_tx.cpp — ESP32-C3 continuous TX firmware for LR2021 throughput benchmarking.
 *
 * Sends configurable-size packets back-to-back in a continuous loop.
 * Prints periodic stats via UART: packets sent, elapsed time, effective throughput.
 *
 * Select this firmware via menuconfig:
 *   Component config → FLRC Continuous TX (enable CONFIG_FLRC_CONT_TX)
 *   Then select payload size (32/64/128/255 bytes).
 *
 * Build:  source ~/esp/esp-idf/export.sh
 *         idf.py menuconfig   # enable FLRC_CONT_TX + choose payload size
 *         idf.py build
 * Flash:  idf.py -p /dev/ttyACM0 flash monitor
 *
 * Pins (ESP32-C3 Mini V1 dev board, same as main.cpp):
 *   GPIO6  = SCK
 *   GPIO2  = MISO
 *   GPIO7  = MOSI
 *   GPIO10 = NSS (CS)
 *   GPIO4  = BUSY
 *   GPIO5  = DIO9 (IRQ)
 *   GPIO3  = RST
 *   GPIO8  = LED (active LOW)
 *
 * Protocol: Raw 2-byte opcodes (NOT RadioLib — see AGENTS.md ADR-020).
 * CS-HIGH required between EVERY SPI command.
 * IRQ status is 32-bit (TX_DONE=bit19 / bit11 per proven config, RX_DONE=bit18).
 */

#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "driver/gpio.h"
#include "driver/spi_master.h"

static const char *TAG = "CONT_TX";

// ─── Pins ────────────────────────────────────────────────────────────
#define PIN_SCK    6
#define PIN_MISO   2
#define PIN_MOSI   7
#define PIN_CS     10
#define PIN_BUSY   4
#define PIN_IRQ    5
#define PIN_RST    3
#define PIN_LED    8

// ─── FLRC Config ─────────────────────────────────────────────────────
#define FLRC_FREQ_MHZ   2440.0f
#define XTAL_MHZ        52.0f
#define TX_POWER_DBM    12

// Payload size: from Kconfig if available, else default 255
#ifdef CONFIG_FLRC_CONT_TX_PAYLOAD_32
  #define FLRC_PKT_SIZE   32
#elif defined(CONFIG_FLRC_CONT_TX_PAYLOAD_64)
  #define FLRC_PKT_SIZE   64
#elif defined(CONFIG_FLRC_CONT_TX_PAYLOAD_128)
  #define FLRC_PKT_SIZE   128
#elif defined(CONFIG_FLRC_CONT_TX_PAYLOAD_255)
  #define FLRC_PKT_SIZE   255
#else
  // Fallback if not using Kconfig
  #define FLRC_PKT_SIZE   255
#endif

// SPI clock: try 20 MHz first, fall back to 10 MHz if unstable
#define SPI_CLOCK_FAST   20000000
#define SPI_CLOCK_SLOW   10000000
#define SPI_CLOCK_HZ     SPI_CLOCK_FAST

// Stats interval
#define STATS_INTERVAL_MS  1000

#define SYNC_WORD_0   0x12
#define SYNC_WORD_1   0xAD
#define SYNC_WORD_2   0x10
#define SYNC_WORD_3   0x1B

// Test packets for SPI stability check before continuous loop
#define STABILITY_TEST_PKTS  10
#define STABILITY_FAIL_THRESHOLD  5

// ─── SPI handle ──────────────────────────────────────────────────────
static spi_device_handle_t spi;

// ─── GPIO helpers ────────────────────────────────────────────────────
static inline void cs_low()  { gpio_set_level((gpio_num_t)PIN_CS, 0); }
static inline void cs_high() { gpio_set_level((gpio_num_t)PIN_CS, 1); }
static inline bool busy_high() { return gpio_get_level((gpio_num_t)PIN_BUSY) == 1; }
static inline bool irq_high()  { return gpio_get_level((gpio_num_t)PIN_IRQ) == 1; }

static void wait_busy() {
    uint32_t timeout = 100000;
    while (busy_high() && --timeout) {}
}

// ─── SPI operations ──────────────────────────────────────────────────
// Write command bytes (no read). CS-HIGH between every command.
static void rf_write_cmd(const uint8_t *cmd, size_t len) {
    wait_busy();

    spi_transaction_t t = {};
    t.flags = SPI_TRANS_USE_TXDATA;
    t.length = len * 8;  // bits
    t.tx_buffer = cmd;
    t.rx_buffer = NULL;

    cs_low();
    spi_device_polling_transmit(spi, &t);
    cs_high();
}

// Write data to TX FIFO: opcode(2) + payload.
// IMPORTANT: Do NOT batch multiple SPI commands. LR2021 requires CS-HIGH
// between commands. This function sends opcode+data as ONE CS-low session
// (allowed: opcode+payload is a single logical command), but the caller
// must ensure CS goes HIGH before the next command.
static void rf_write_tx_fifo(const uint8_t *data, size_t len) {
    wait_busy();

    static uint8_t tx_buf[2 + 255];
    tx_buf[0] = 0x00;  // WRITE_TX_FIFO opcode high byte
    tx_buf[1] = 0x02;  // WRITE_TX_FIFO opcode low byte
    memcpy(tx_buf + 2, data, len);

    spi_transaction_t t = {};
    t.length = (2 + len) * 8;  // bits
    t.tx_buffer = tx_buf;
    t.rx_buffer = NULL;

    cs_low();
    spi_device_polling_transmit(spi, &t);
    cs_high();
}

// ─── Radio Init ──────────────────────────────────────────────────────
static void init_radio() {
    // Hardware reset
    gpio_set_direction((gpio_num_t)PIN_RST, GPIO_MODE_OUTPUT);
    gpio_set_level((gpio_num_t)PIN_RST, 0);
    vTaskDelay(pdMS_TO_TICKS(1));
    gpio_set_level((gpio_num_t)PIN_RST, 1);
    vTaskDelay(pdMS_TO_TICKS(50));

    // CLEAR_ERRORS
    uint8_t cmd_clr_err[] = { 0x01, 0x11, 0x00, 0x00 };
    rf_write_cmd(cmd_clr_err, 4);
    vTaskDelay(pdMS_TO_TICKS(1));

    // SET_STANDBY (STDBY_XOSC)
    uint8_t cmd_stdby[] = { 0x01, 0x28, 0x01 };
    rf_write_cmd(cmd_stdby, 3);
    vTaskDelay(pdMS_TO_TICKS(5));

    // SET_PACKET_TYPE FLRC (0x05)
    uint8_t cmd_pkttype[] = { 0x02, 0x07, 0x05 };
    rf_write_cmd(cmd_pkttype, 3);
    vTaskDelay(pdMS_TO_TICKS(1));

    // SET_RF_FREQUENCY
    uint32_t frf = (uint32_t)((FLRC_FREQ_MHZ * 1e6 * (double)(1ULL << 18)) / (XTAL_MHZ * 1e6));
    uint8_t cmd_freq[] = {
        0x02, 0x00,
        (uint8_t)(frf >> 16), (uint8_t)(frf >> 8), (uint8_t)(frf & 0xFF)
    };
    rf_write_cmd(cmd_freq, 5);
    vTaskDelay(pdMS_TO_TICKS(1));

    // SET_RX_PATH (HF path for 2.4 GHz — mandatory)
    uint8_t cmd_rxpath[] = { 0x02, 0x01, 0x01, 0x00 };
    rf_write_cmd(cmd_rxpath, 4);
    vTaskDelay(pdMS_TO_TICKS(1));

    // CALIB_FRONT_END (mandatory before TX/RX)
    uint16_t feFreq = (uint16_t)((FLRC_FREQ_MHZ / 4.0f) + 0.5f) | 0x8000;
    uint8_t cmd_calfe[] = {
        0x01, 0x23,
        (uint8_t)(feFreq >> 8), (uint8_t)(feFreq & 0xFF),
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00
    };
    rf_write_cmd(cmd_calfe, 10);
    vTaskDelay(pdMS_TO_TICKS(5));

    // CALIBRATE (mask 0x5F — bit 5 is undefined, do NOT use 0x6F)
    uint8_t cmd_cal[] = { 0x01, 0x22, 0x5F };
    rf_write_cmd(cmd_cal, 3);
    vTaskDelay(pdMS_TO_TICKS(5));

    // SET_FLRC_MOD_PARAMS: BR=2600 (0x00), CR=1/0 + BT=0.5 = 0x25
    uint8_t cmd_modparams[] = { 0x02, 0x48, 0x00, 0x25 };
    rf_write_cmd(cmd_modparams, 4);
    vTaskDelay(pdMS_TO_TICKS(1));

    // SET_FLRC_SYNCWORD
    uint8_t cmd_sync[] = { 0x02, 0x4C, 0x01, SYNC_WORD_0, SYNC_WORD_1, SYNC_WORD_2, SYNC_WORD_3 };
    rf_write_cmd(cmd_sync, 7);
    vTaskDelay(pdMS_TO_TICKS(1));

    // SET_FLRC_PACKET_PARAMS — payload size from config
    uint8_t cmd_pktparams[] = {
        0x02, 0x49,
        0x0C,  // preamble=8 | syncLen=4/2
        0x4C,  // syncTx=1 | syncMatch=1 | fixed=1 | crc=0
        0x00, (uint8_t)FLRC_PKT_SIZE
    };
    rf_write_cmd(cmd_pktparams, 6);
    vTaskDelay(pdMS_TO_TICKS(1));

    // SET_RX_TX_FALLBACK
    uint8_t cmd_fallback[] = { 0x02, 0x06, 0x03 };
    rf_write_cmd(cmd_fallback, 3);
    vTaskDelay(pdMS_TO_TICKS(1));

    // SET_TX_POWER
    uint8_t cmd_power[] = { 0x02, 0x03, (uint8_t)(TX_POWER_DBM * 2), 0x04 };
    rf_write_cmd(cmd_power, 4);
    vTaskDelay(pdMS_TO_TICKS(1));

    // SET_PA_CONFIG
    uint8_t cmd_paconfig[] = { 0x02, 0x02, 0x80, 0x00, 0x60, 0x07, 0x10 };
    rf_write_cmd(cmd_paconfig, 7);
    vTaskDelay(pdMS_TO_TICKS(1));

    // DIO function: DIO9 = IRQ
    uint8_t cmd_dio[] = { 0x01, 0x12, 0x09, 0x11 };
    rf_write_cmd(cmd_dio, 4);
    vTaskDelay(pdMS_TO_TICKS(1));

    // DIO IRQ config: TX_DONE
    uint8_t cmd_irqcfg_tx[] = { 0x01, 0x15, 0x09, 0x00, 0x08, 0x00, 0x00 };
    rf_write_cmd(cmd_irqcfg_tx, 7);
    vTaskDelay(pdMS_TO_TICKS(1));

    // Clear IRQ
    uint8_t cmd_clr_irq[] = { 0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF };
    rf_write_cmd(cmd_clr_irq, 6);

    ESP_LOGI(TAG, "Radio init complete. Payload size=%d bytes, Freq=%.1f MHz",
             FLRC_PKT_SIZE, FLRC_FREQ_MHZ);
}

// ─── SPI device re-init at a different clock speed ───────────────────
static bool spi_add_device(int clock_hz) {
    spi_device_interface_config_t devcfg = {};
    devcfg.clock_speed_hz = clock_hz;
    devcfg.mode = 0;
    devcfg.spics_io_num = -1;           // CS handled manually
    devcfg.queue_size = 1;
    devcfg.flags = SPI_DEVICE_HALFDUPLEX;

    esp_err_t ret = spi_bus_add_device(SPI2_HOST, &devcfg, &spi);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "SPI device add failed at %d MHz: %s",
                 clock_hz / 1000000, esp_err_to_name(ret));
        return false;
    }
    ESP_LOGI(TAG, "SPI device added: %d MHz, mode 0", clock_hz / 1000000);
    return true;
}

// ─── Stability test: send N packets, return success count ────────────
static int run_stability_test() {
    uint8_t pkt[FLRC_PKT_SIZE];
    for (int j = 4; j < FLRC_PKT_SIZE; j++) pkt[j] = (uint8_t)(j & 0xFF);

    uint8_t cmd_clr_irq[] = { 0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF };
    uint8_t cmd_set_tx[]  = { 0x02, 0x0D, 0x00, 0x00, 0x00 };

    int success = 0;
    for (int i = 0; i < STABILITY_TEST_PKTS; i++) {
        pkt[0] = (uint8_t)(i >> 24);
        pkt[1] = (uint8_t)(i >> 16);
        pkt[2] = (uint8_t)(i >> 8);
        pkt[3] = (uint8_t)(i & 0xFF);

        rf_write_cmd(cmd_clr_irq, 6);
        rf_write_tx_fifo(pkt, FLRC_PKT_SIZE);
        rf_write_cmd(cmd_set_tx, 5);

        // Wait for TX_DONE
        uint32_t timeout = 500000;
        while (!irq_high() && --timeout) {}

        if (timeout > 0) success++;
    }
    return success;
}

// ─── Continuous TX loop ──────────────────────────────────────────────
static void run_continuous_tx() {
    ESP_LOGI(TAG, "=== CONTINUOUS TX START: %d-byte packets ===", FLRC_PKT_SIZE);
    ESP_LOGI(TAG, "CONT_TX_START,payload=%d,freq=%.0f,power=%d",
             FLRC_PKT_SIZE, FLRC_FREQ_MHZ, TX_POWER_DBM);

    // Prepare packet payload (seq in first 4 bytes, counter pattern in rest)
    uint8_t pkt[FLRC_PKT_SIZE];
    for (int j = 4; j < FLRC_PKT_SIZE; j++) pkt[j] = (uint8_t)(j & 0xFF);

    uint8_t cmd_clr_irq[]   = { 0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF };
    uint8_t cmd_set_tx[]    = { 0x02, 0x0D, 0x00, 0x00, 0x00 };
    uint8_t cmd_clr_txfifo[] = { 0x01, 0x1F };

    int64_t start_us = esp_timer_get_time();
    int64_t last_stats_us = start_us;
    uint32_t total_sent = 0;
    uint32_t tx_done_count = 0;
    uint32_t tx_timeout_count = 0;

    // Track stats for periodic reporting
    uint32_t pkts_since_last_stats = 0;

    while (true) {
        // Encode sequence number in first 4 bytes
        pkt[0] = (uint8_t)(total_sent >> 24);
        pkt[1] = (uint8_t)(total_sent >> 16);
        pkt[2] = (uint8_t)(total_sent >> 8);
        pkt[3] = (uint8_t)(total_sent & 0xFF);

        // Clear TX FIFO for first packet in case of residual data
        if (total_sent == 0) {
            rf_write_cmd(cmd_clr_txfifo, 2);
        }

        // 1. Clear IRQ
        rf_write_cmd(cmd_clr_irq, 6);

        // 2. Write TX FIFO
        rf_write_tx_fifo(pkt, FLRC_PKT_SIZE);

        // 3. Trigger TX
        rf_write_cmd(cmd_set_tx, 5);

        // 4. Wait for TX_DONE — IRQ pin HIGH
        uint32_t timeout = 500000;
        while (!irq_high() && --timeout) {}

        total_sent++;
        pkts_since_last_stats++;

        if (timeout > 0) tx_done_count++;
        else {
            tx_timeout_count++;
            // Clear stuck state: clear TX FIFO + errors
            rf_write_cmd(cmd_clr_txfifo, 2);
            uint8_t cmd_clr_err[] = { 0x01, 0x11, 0x00, 0x00 };
            rf_write_cmd(cmd_clr_err, 4);
        }

        // Periodic stats
        int64_t now_us = esp_timer_get_time();
        int64_t elapsed_ms = (now_us - start_us) / 1000;
        int64_t since_last_ms = (now_us - last_stats_us) / 1000;

        if (since_last_ms >= STATS_INTERVAL_MS) {
            int64_t total_elapsed_ms = elapsed_ms;
            float total_tput = (total_elapsed_ms > 0)
                ? ((float)total_sent * FLRC_PKT_SIZE * 8.0f) / (float)total_elapsed_ms
                : 0.0f;

            // Interval throughput
            float interval_tput = (since_last_ms > 0)
                ? ((float)pkts_since_last_stats * FLRC_PKT_SIZE * 8.0f) / (float)since_last_ms
                : 0.0f;

            ESP_LOGI(TAG, "CONT_TX_STATS,sent=%lu,done=%lu,timeout=%lu,elapsed_ms=%lld,"
                     "total_kbps=%.1f,interval_kbps=%.1f,interval_pkts=%lu",
                     (unsigned long)total_sent, (unsigned long)tx_done_count,
                     (unsigned long)tx_timeout_count, (long long)total_elapsed_ms,
                     total_tput, interval_tput, (unsigned long)pkts_since_last_stats);

            last_stats_us = now_us;
            pkts_since_last_stats = 0;
        }
    }
}

// ─── Main ────────────────────────────────────────────────────────────
extern "C" void app_main() {
    ESP_LOGI(TAG, "=== ESP32-C3 Continuous TX (LR2021 FLRC) ===");
    setvbuf(stdout, NULL, _IONBF, 0);

    // LED blink
    gpio_config_t io_conf = {};
    io_conf.pin_bit_mask = (1ULL << PIN_LED);
    io_conf.mode = GPIO_MODE_OUTPUT;
    gpio_config(&io_conf);
    gpio_set_level((gpio_num_t)PIN_LED, 1);
    vTaskDelay(pdMS_TO_TICKS(500));
    gpio_set_level((gpio_num_t)PIN_LED, 0);

    // GPIO setup
    gpio_config_t gpio_conf = {};
    gpio_conf.pin_bit_mask = (1ULL << PIN_CS) | (1ULL << PIN_RST);
    gpio_conf.mode = GPIO_MODE_OUTPUT;
    gpio_config(&gpio_conf);
    cs_high();
    gpio_set_level((gpio_num_t)PIN_RST, 1);

    gpio_conf.pin_bit_mask = (1ULL << PIN_BUSY) | (1ULL << PIN_IRQ);
    gpio_conf.mode = GPIO_MODE_INPUT;
    gpio_conf.pull_down_en = GPIO_PULLDOWN_DISABLE;
    gpio_conf.pull_up_en = GPIO_PULLUP_DISABLE;
    gpio_config(&gpio_conf);

    // SPI bus init with DMA
    spi_bus_config_t buscfg = {};
    buscfg.miso_io_num = PIN_MISO;
    buscfg.mosi_io_num = PIN_MOSI;
    buscfg.sclk_io_num = PIN_SCK;
    buscfg.max_transfer_sz = (255 + 8) * 2;  // max payload + opcode overhead

    esp_err_t ret = spi_bus_initialize(SPI2_HOST, &buscfg, SPI_DMA_CH_AUTO);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "SPI bus init failed: %s", esp_err_to_name(ret));
        return;
    }
    ESP_LOGI(TAG, "SPI bus initialized (DMA auto)");

    // ─── SPI clock selection: try 20 MHz, fall back to 10 MHz ────────
    int spi_clock = SPI_CLOCK_FAST;
    bool device_ok = spi_add_device(spi_clock);

    // Init radio
    init_radio();
    vTaskDelay(pdMS_TO_TICKS(500));

    // Stability test at current clock
    ESP_LOGI(TAG, "Running stability test at %d MHz...", spi_clock / 1000000);
    int success = run_stability_test();
    ESP_LOGI(TAG, "Stability test: %d/%d packets succeeded at %d MHz",
             success, STABILITY_TEST_PKTS, spi_clock / 1000000);

    if (success < (STABILITY_TEST_PKTS - STABILITY_FAIL_THRESHOLD)) {
        // Too many failures at 20 MHz — fall back to 10 MHz
        ESP_LOGW(TAG, "SPI unstable at %d MHz (%d/%d ok), falling back to %d MHz",
                 spi_clock / 1000000, success, STABILITY_TEST_PKTS,
                 SPI_CLOCK_SLOW / 1000000);

        // Remove device, re-add at lower speed
        spi_bus_remove_device(spi);
        spi_clock = SPI_CLOCK_SLOW;
        device_ok = spi_add_device(spi_clock);

        // Re-init radio
        init_radio();
        vTaskDelay(pdMS_TO_TICKS(500));

        // Verify stability at lower speed
        success = run_stability_test();
        ESP_LOGI(TAG, "Stability test at %d MHz: %d/%d ok",
                 spi_clock / 1000000, success, STABILITY_TEST_PKTS);
    }

    ESP_LOGI(TAG, "SPI clock locked at %d MHz", spi_clock / 1000000);

    // Give RX board time to enter RX mode
    ESP_LOGI(TAG, "Waiting 2s for RX board to be ready...");
    vTaskDelay(pdMS_TO_TICKS(2000));

    // Start continuous TX
    run_continuous_tx();

    // Should never reach here
    while (true) {
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}
