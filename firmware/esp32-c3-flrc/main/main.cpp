/*
 * main.cpp — ESP32-C3 FLRC raw SPI throughput test (TX + RX in one binary)
 *
 * Tests whether ESP32-C3's spi_master driver (with hardware DMA) can achieve
 * higher throughput with the LR2021 than the RP2040 (which was stuck at
 * 1377 kbps because batch/DMA/PIO all failed).
 *
 * Build: source ~/esp/esp-idf/export.sh
 *        idf.py build    (TX mode by default)
 *        idf.py -DSDKCONFIG=sdkconfig.rx build  (RX mode)
 *
 * Flash: idf.py -p /dev/ttyACM1 flash monitor
 *
 * Pins (ESP32-C3 Mini V1 dev board, matches AGENTS.md):
 *   GPIO6  = SCK
 *   GPIO2  = MISO
 *   GPIO7  = MOSI
 *   GPIO10 = NSS (CS)
 *   GPIO4  = BUSY
 *   GPIO5  = DIO9 (IRQ)
 *   GPIO3  = RST
 *   GPIO8  = LED (active LOW)
 */

#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "driver/gpio.h"
#include "driver/spi_master.h"

static const char *TAG = "FLRC";

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
#define FLRC_PKT_SIZE   255
#define SPI_CLOCK_HZ    20000000  // 20 MHz — ESP32 can actually do this
#define XTAL_MHZ        52.0f
#define TX_PKT_COUNT    1000
#define TX_POWER_DBM    12

#define SYNC_WORD_0   0x12
#define SYNC_WORD_1   0xAD
#define SYNC_WORD_2   0x10
#define SYNC_WORD_3   0x1B

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
// Write command bytes (no read)
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

// Write data to TX FIFO: opcode(2) + payload(255)
static void rf_write_tx_fifo(const uint8_t *data, size_t len) {
    wait_busy();

    // Build buffer: opcode + data in one contiguous transfer
    // This is the KEY TEST: does ESP32 batch transfer work with LR2021?
    static uint8_t tx_buf[2 + FLRC_PKT_SIZE];
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

// Read RX FIFO
static void rf_read_rx_fifo(uint8_t *buf, size_t len) {
    wait_busy();

    uint8_t cmd[2] = { 0x00, 0x01 };  // READ_RX_FIFO opcode

    spi_transaction_t t_cmd = {};
    t_cmd.flags = SPI_TRANS_USE_TXDATA;
    t_cmd.length = 2 * 8;
    t_cmd.tx_buffer = cmd;
    t_cmd.rx_buffer = NULL;

    spi_transaction_t t_data = {};
    t_data.length = len * 8;
    t_data.tx_buffer = NULL;
    t_data.rx_buffer = buf;

    cs_low();
    spi_device_polling_transmit(spi, &t_cmd);
    spi_device_polling_transmit(spi, &t_data);
    cs_high();
}

// Read IRQ status (4 bytes)
static uint32_t rf_read_irq_status() {
    wait_busy();

    uint8_t cmd[2] = { 0x01, 0x17 };  // GET_AND_CLEAR_IRQ_STATUS
    uint8_t rx[6] = {0};

    spi_transaction_t t_cmd = {};
    t_cmd.flags = SPI_TRANS_USE_TXDATA;
    t_cmd.length = 2 * 8;
    t_cmd.tx_buffer = cmd;

    spi_transaction_t t_rx = {};
    t_rx.length = 6 * 8;
    t_rx.tx_buffer = NULL;
    t_rx.rx_buffer = rx;

    cs_low();
    spi_device_polling_transmit(spi, &t_cmd);
    cs_high();

    wait_busy();

    cs_low();
    spi_device_polling_transmit(spi, &t_rx);
    cs_high();

    return ((uint32_t)rx[2] << 24) | ((uint32_t)rx[3] << 16) |
           ((uint32_t)rx[4] << 8) | rx[5];
}

static uint8_t rf_read_status() {
    wait_busy();
    uint8_t tx = 0x00;
    uint8_t rx = 0;

    spi_transaction_t t = {};
    t.length = 8;
    t.tx_buffer = &tx;
    t.rx_buffer = &rx;

    cs_low();
    spi_device_polling_transmit(spi, &t);
    cs_high();
    return rx;
}

// ─── Raw SPI Init (same sequence as RP2040 v4) ───────────────────────
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

    // SET_RX_PATH (HF path for 2.4 GHz)
    uint8_t cmd_rxpath[] = { 0x02, 0x01, 0x01, 0x00 };
    rf_write_cmd(cmd_rxpath, 4);
    vTaskDelay(pdMS_TO_TICKS(1));

    // CALIB_FRONT_END
    uint16_t feFreq = (uint16_t)((FLRC_FREQ_MHZ / 4.0f) + 0.5f) | 0x8000;
    uint8_t cmd_calfe[] = {
        0x01, 0x23,
        (uint8_t)(feFreq >> 8), (uint8_t)(feFreq & 0xFF),
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00
    };
    rf_write_cmd(cmd_calfe, 10);
    vTaskDelay(pdMS_TO_TICKS(5));

    // CALIBRATE
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

    // SET_FLRC_PACKET_PARAMS
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

    // DIO IRQ config: TX_DONE (bit 11 = 0x00000800)
    uint8_t cmd_irqcfg_tx[] = { 0x01, 0x15, 0x09, 0x00, 0x08, 0x00, 0x00 };
    rf_write_cmd(cmd_irqcfg_tx, 7);
    vTaskDelay(pdMS_TO_TICKS(1));

    // Clear IRQ
    uint8_t cmd_clr_irq[] = { 0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF };
    rf_write_cmd(cmd_clr_irq, 6);

    uint8_t st = rf_read_status();
    ESP_LOGI(TAG, "Radio init complete. Status=0x%02X", st);
}

// ─── TX mode ─────────────────────────────────────────────────────────
static void run_tx() {
    ESP_LOGI(TAG, "=== TX START: %d packets, %d bytes ===", TX_PKT_COUNT, FLRC_PKT_SIZE);

    // Prepare packet data
    uint8_t pkt[FLRC_PKT_SIZE];
    for (int j = 4; j < FLRC_PKT_SIZE; j++) pkt[j] = (uint8_t)(j & 0xFF);

    uint8_t cmd_clr_irq[] = { 0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF };
    uint8_t cmd_set_tx[]  = { 0x02, 0x0D, 0x00, 0x00, 0x00 };

    int64_t start_us = esp_timer_get_time();
    uint32_t tx_done_count = 0;
    uint32_t tx_timeout_count = 0;

    for (int i = 0; i < TX_PKT_COUNT; i++) {
        pkt[0] = (uint8_t)(i >> 24);
        pkt[1] = (uint8_t)(i >> 16);
        pkt[2] = (uint8_t)(i >> 8);
        pkt[3] = (uint8_t)(i & 0xFF);

        // 1. Clear IRQ
        rf_write_cmd(cmd_clr_irq, 6);

        // 2. Write TX FIFO (THIS IS THE KEY TEST — batch transfer via spi_master)
        rf_write_tx_fifo(pkt, FLRC_PKT_SIZE);

        // 3. Trigger TX
        rf_write_cmd(cmd_set_tx, 5);

        // 4. Wait for TX_DONE — IRQ pin HIGH
        uint32_t timeout = 500000;
        while (!irq_high() && --timeout) {}

        if (timeout > 0) tx_done_count++;
        else tx_timeout_count++;

        if (i < 5 || (i + 1) % 200 == 0) {
            ESP_LOGI(TAG, "TX %d/%d (done=%lu to=%lu)", i + 1, TX_PKT_COUNT,
                     (unsigned long)tx_done_count, (unsigned long)tx_timeout_count);
        }
    }

    // DEADBEEF end marker
    pkt[0] = 0xDE; pkt[1] = 0xAD; pkt[2] = 0xBE; pkt[3] = 0xEF;
    pkt[4] = (uint8_t)(TX_PKT_COUNT >> 24);
    pkt[5] = (uint8_t)(TX_PKT_COUNT >> 16);
    pkt[6] = (uint8_t)(TX_PKT_COUNT >> 8);
    pkt[7] = (uint8_t)(TX_PKT_COUNT & 0xFF);

    uint8_t cmd_clr_txfifo[] = { 0x01, 0x1F };
    rf_write_cmd(cmd_clr_txfifo, 2);
    rf_write_tx_fifo(pkt, FLRC_PKT_SIZE);
    rf_write_cmd(cmd_set_tx, 5);
    vTaskDelay(pdMS_TO_TICKS(10));

    int64_t elapsed_us = esp_timer_get_time() - start_us;
    int64_t elapsed_ms = elapsed_us / 1000;
    float throughput = ((float)TX_PKT_COUNT * FLRC_PKT_SIZE * 8.0f) / (float)elapsed_ms;

    ESP_LOGI(TAG, "=============================================");
    ESP_LOGI(TAG, "  TX sent:     %d", TX_PKT_COUNT);
    ESP_LOGI(TAG, "  TX_DONE:     %lu", (unsigned long)tx_done_count);
    ESP_LOGI(TAG, "  Timeout:     %lu", (unsigned long)tx_timeout_count);
    ESP_LOGI(TAG, "  Elapsed:     %lld ms", (long long)elapsed_ms);
    ESP_LOGI(TAG, "  THROUGHPUT:  %.1f kbps", throughput);
    ESP_LOGI(TAG, "=============================================");
    ESP_LOGI(TAG, "RESULT_TX,sent=%d,done=%lu,timeout=%lu,elapsed_ms=%lld,throughput_kbps=%.1f",
             TX_PKT_COUNT, (unsigned long)tx_done_count, (unsigned long)tx_timeout_count,
             (long long)elapsed_ms, throughput);
}

// ─── RX mode ─────────────────────────────────────────────────────────
static void run_rx() {
    ESP_LOGI(TAG, "=== RX START: listening for %d-byte FLRC packets ===", FLRC_PKT_SIZE);

    // Reconfigure DIO IRQ for RX_DONE (bit 18 = 0x00040000)
    uint8_t cmd_irqcfg_rx[] = { 0x01, 0x15, 0x09, 0x00, 0x04, 0x00, 0x00 };
    rf_write_cmd(cmd_irqcfg_rx, 7);
    vTaskDelay(pdMS_TO_TICKS(1));

    // Clear IRQ
    uint8_t cmd_clr_irq[] = { 0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF };
    rf_write_cmd(cmd_clr_irq, 6);
    vTaskDelay(pdMS_TO_TICKS(1));

    // Enter continuous RX
    uint8_t cmd_set_rx[] = { 0x02, 0x0C, 0xFF, 0xFF, 0xFF };
    rf_write_cmd(cmd_set_rx, 5);
    vTaskDelay(pdMS_TO_TICKS(2));

    uint8_t buf[FLRC_PKT_SIZE];
    uint32_t received = 0, unique = 0, duplicates = 0;
    uint32_t lastSeq = 0xFFFFFFFF, maxSeq = 0, totalSent = 0;
    int64_t start_us = esp_timer_get_time();
    int64_t lastPkt_us = start_us;

    ESP_LOGI(TAG, "pkt,seq");

    while (true) {
        int64_t now_us = esp_timer_get_time();
        int64_t elapsed_ms = (now_us - start_us) / 1000;
        int64_t silence_ms = (now_us - lastPkt_us) / 1000;

        if (elapsed_ms >= 12000) {
            ESP_LOGI(TAG, "RX_DONE timeout");
            break;
        }
        if (received > 0 && silence_ms >= 3000) {
            ESP_LOGI(TAG, "RX_DONE silence");
            break;
        }

        // Poll IRQ pin (could use GPIO interrupt for lower latency)
        if (!irq_high()) continue;

        // Read packet
        rf_read_rx_fifo(buf, FLRC_PKT_SIZE);

        // Clear RX FIFO + errors + IRQ + re-arm
        uint8_t cmd_clr_rxfifo[] = { 0x01, 0x1E };
        rf_write_cmd(cmd_clr_rxfifo, 2);
        uint8_t cmd_clr_err[] = { 0x01, 0x11, 0x00, 0x00 };
        rf_write_cmd(cmd_clr_err, 4);
        rf_write_cmd(cmd_clr_irq, 6);
        rf_write_cmd(cmd_set_rx, 5);

        // Extract seq
        uint32_t seq = ((uint32_t)buf[0] << 24) | ((uint32_t)buf[1] << 16) |
                       ((uint32_t)buf[2] << 8) | buf[3];

        // DEADBEEF end marker
        if (buf[0] == 0xDE && buf[1] == 0xAD &&
            buf[2] == 0xBE && buf[3] == 0xEF) {
            totalSent = ((uint32_t)buf[4] << 24) | ((uint32_t)buf[5] << 16) |
                        ((uint32_t)buf[6] << 8) | buf[7];
            ESP_LOGI(TAG, "RX_END DEADBEEF");
            break;
        }

        received++;
        if (seq == lastSeq) duplicates++;
        else unique++;
        lastSeq = seq;
        if (seq > maxSeq) maxSeq = seq;
        lastPkt_us = now_us;

        if (received <= 5 || received % 100 == 0) {
            ESP_LOGI(TAG, "%lu,%lu", (unsigned long)received, (unsigned long)seq);
        }
    }

    int64_t elapsed_us = esp_timer_get_time() - start_us;
    int64_t elapsed_ms = elapsed_us / 1000;

    uint32_t total = totalSent > 0 ? totalSent : (maxSeq + 1);
    uint32_t lost = (total > received) ? (total - received) : 0;
    float pct = (total > 0) ? (100.0f * (float)lost / (float)total) : 0.0f;
    float tput = (elapsed_ms > 0 && received > 0)
                 ? ((float)received * FLRC_PKT_SIZE * 8.0f) / (float)elapsed_ms : 0.0f;

    ESP_LOGI(TAG, "=============================================");
    ESP_LOGI(TAG, "  Received: %lu (unique %lu, dup %lu)",
             (unsigned long)received, (unsigned long)unique, (unsigned long)duplicates);
    ESP_LOGI(TAG, "  TX sent:  %lu", (unsigned long)totalSent);
    ESP_LOGI(TAG, "  Lost:     %lu (%.2f%%)", (unsigned long)lost, pct);
    ESP_LOGI(TAG, "  Elapsed:  %lld ms", (long long)elapsed_ms);
    ESP_LOGI(TAG, "  THROUGHPUT: %.1f kbps", tput);
    ESP_LOGI(TAG, "=============================================");
    ESP_LOGI(TAG, "RESULT_RX,rx=%lu,unique=%lu,lost=%lu,total=%lu,pct=%.2f,elapsed_ms=%lld,throughput_kbps=%.1f",
             (unsigned long)received, (unsigned long)unique, (unsigned long)lost,
             (unsigned long)total, pct, (long long)elapsed_ms, tput);
}

// ─── Main ────────────────────────────────────────────────────────────
extern "C" void app_main() {
    ESP_LOGI(TAG, "=== ESP32-C3 FLRC Raw SPI Throughput Test ===");
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

    // SPI bus init
    spi_bus_config_t buscfg = {};
    buscfg.miso_io_num = PIN_MISO;
    buscfg.mosi_io_num = PIN_MOSI;
    buscfg.sclk_io_num = PIN_SCK;
    buscfg.max_transfer_sz = (FLRC_PKT_SIZE + 8) * 2;  // enough for opcode + payload

    esp_err_t ret = spi_bus_initialize(SPI2_HOST, &buscfg, SPI_DMA_CH_AUTO);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "SPI bus init failed: %s", esp_err_to_name(ret));
        return;
    }
    ESP_LOGI(TAG, "SPI bus initialized (DMA auto)");

    // SPI device init — CS handled manually (not by driver) for exact timing control
    spi_device_interface_config_t devcfg = {};
    devcfg.clock_speed_hz = SPI_CLOCK_HZ;
    devcfg.mode = 0;                    // SPI mode 0
    devcfg.spics_io_num = -1;           // CS handled manually
    devcfg.queue_size = 1;
    devcfg.flags = SPI_DEVICE_HALFDUPLEX;

    ret = spi_bus_add_device(SPI2_HOST, &devcfg, &spi);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "SPI device add failed: %s", esp_err_to_name(ret));
        return;
    }
    ESP_LOGI(TAG, "SPI device added: %d MHz, mode 0", SPI_CLOCK_HZ / 1000000);

    // Init radio
    init_radio();
    vTaskDelay(pdMS_TO_TICKS(500));

    // Run TX (always TX mode for this binary — flash separate board for RX)
    // To use RX mode, compile with -DCONFIG_FLRC_RX
#ifdef CONFIG_FLRC_RX
    ESP_LOGI(TAG, "Mode: RX");
    run_rx();
#else
    ESP_LOGI(TAG, "Mode: TX (default)");
    vTaskDelay(pdMS_TO_TICKS(2000));  // Give RX board time to enter RX mode
    run_tx();
#endif

    // Keep alive
    while (true) {
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}
