/*
 * lr2021_radio.c — Raw 2-byte opcode SPI radio driver for Semtech LR2021
 *
 * Bridges the proven raw LR2021 SPI protocol to the mesh_adapter layer.
 * Ported from firmware/esp32-c3-flrc/main/main.cpp (PROVEN WORKING on ESP32-C3).
 *
 * Does NOT use RadioLib. Uses raw 2-byte opcodes only. See ADR-020.
 *
 * SPI protocol:
 *   NSS LOW → wait BUSY LOW → send [opcode_hi, opcode_lo, ...payload] → NSS HIGH
 *
 * IRQ status is 32-bit: RX_DONE=bit18, TX_DONE=bit19
 * RSSI via GET_FLRC_PACKET_STATUS (0x024B): 9-bit, unsigned, negate for dBm
 *
 * SPDX-License-Identifier: MIT
 */

#include "lr2021_radio.h"

#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "driver/gpio.h"
#include "driver/spi_master.h"

static const char *TAG = "LR2021";

/* ── Module state ─────────────────────────────────────────────────────── */
static spi_device_handle_t s_spi;
static lr2021_radio_pins_t s_pins;
static lr2021_rx_callback_t s_rx_cb   = NULL;
static bool                 s_inited  = false;
static bool                 s_in_rx   = false;
static int8_t               s_last_rssi = 0;

/* Radio parameters (set during init, could be parameterized later) */
static float    s_freq_mhz    = LR2021_DEFAULT_FREQ_MHZ;
static int8_t   s_tx_power    = LR2021_DEFAULT_TX_POWER;
static uint16_t s_bitrate_kbps = LR2021_DEFAULT_BR_KBPS;

/* Sync word — must match between TX and RX nodes */
#define SYNC_WORD_0  0x12
#define SYNC_WORD_1  0xAD
#define SYNC_WORD_2  0x10
#define SYNC_WORD_3  0x1B

/* ── GPIO helpers ─────────────────────────────────────────────────────── */
static inline void cs_low(void)  { gpio_set_level(s_pins.cs, 0); }
static inline void cs_high(void) { gpio_set_level(s_pins.cs, 1); }
static inline bool busy_high(void) { return gpio_get_level(s_pins.busy) == 1; }
static inline bool irq_high(void)  { return gpio_get_level(s_pins.irq) == 1; }

static void wait_busy(void)
{
    uint32_t timeout = 200000;
    while (busy_high() && --timeout) {
        /* tight spin */
    }
}

/* ── SPI primitives (ported from main.cpp) ────────────────────────────── */

/* Write command bytes — no read */
static void rf_write_cmd(const uint8_t *cmd, size_t len)
{
    wait_busy();

    spi_transaction_t t = {};
    t.flags    = SPI_TRANS_USE_TXDATA;
    t.length   = len * 8;
    t.tx_buffer = cmd;
    t.rx_buffer = NULL;

    cs_low();
    spi_device_polling_transmit(s_spi, &t);
    cs_high();
}

/* Write TX FIFO: opcode(2) + payload in one batched transfer */
static void rf_write_tx_fifo(const uint8_t *data, size_t len)
{
    wait_busy();

    static uint8_t tx_buf[2 + LR2021_PKT_SIZE];
    tx_buf[0] = 0x00;  /* WRITE_TX_FIFO opcode high */
    tx_buf[1] = 0x02;  /* WRITE_TX_FIFO opcode low */
    if (len > LR2021_PKT_SIZE) len = LR2021_PKT_SIZE;
    memcpy(tx_buf + 2, data, len);

    spi_transaction_t t = {};
    t.length   = (2 + len) * 8;
    t.tx_buffer = tx_buf;
    t.rx_buffer = NULL;

    cs_low();
    spi_device_polling_transmit(s_spi, &t);
    cs_high();
}

/* Read RX FIFO — opcode then data in same CS assertion */
static void rf_read_rx_fifo(uint8_t *buf, size_t len)
{
    wait_busy();

    uint8_t cmd[2] = { 0x00, 0x01 };  /* READ_RX_FIFO opcode */

    spi_transaction_t t_cmd = {};
    t_cmd.flags    = SPI_TRANS_USE_TXDATA;
    t_cmd.length   = 2 * 8;
    t_cmd.tx_buffer = cmd;
    t_cmd.rx_buffer = NULL;

    spi_transaction_t t_data = {};
    t_data.length   = len * 8;
    t_data.tx_buffer = NULL;
    t_data.rx_buffer = buf;

    cs_low();
    spi_device_polling_transmit(s_spi, &t_cmd);
    spi_device_polling_transmit(s_spi, &t_data);
    cs_high();
}

/* Read and clear IRQ status — returns 32-bit status word */
static uint32_t rf_get_irq_status(void)
{
    wait_busy();

    uint8_t cmd[2] = { 0x01, 0x17 };  /* GET_IRQ_STATUS */
    uint8_t rx[6] = {0};

    spi_transaction_t t_cmd = {};
    t_cmd.flags    = SPI_TRANS_USE_TXDATA;
    t_cmd.length   = 2 * 8;
    t_cmd.tx_buffer = cmd;

    spi_transaction_t t_rx = {};
    t_rx.length   = 6 * 8;
    t_rx.tx_buffer = NULL;
    t_rx.rx_buffer = rx;

    /* Phase 1: send opcode */
    cs_low();
    spi_device_polling_transmit(s_spi, &t_cmd);
    cs_high();

    wait_busy();

    /* Phase 2: read response */
    cs_low();
    spi_device_polling_transmit(s_spi, &t_rx);
    cs_high();

    return ((uint32_t)rx[2] << 24) | ((uint32_t)rx[3] << 16) |
           ((uint32_t)rx[4] << 8) | rx[5];
}

/* Read FLRC packet status — returns 9-bit RSSI as negative dBm */
static int8_t rf_get_rssi(void)
{
    wait_busy();

    uint8_t cmd[2] = { 0x02, 0x4B };  /* GET_FLRC_PACKET_STATUS */
    uint8_t rx[7] = {0};

    spi_transaction_t t_cmd = {};
    t_cmd.flags    = SPI_TRANS_USE_TXDATA;
    t_cmd.length   = 2 * 8;
    t_cmd.tx_buffer = cmd;

    spi_transaction_t t_rx = {};
    t_rx.length   = 7 * 8;
    t_rx.tx_buffer = NULL;
    t_rx.rx_buffer = rx;

    /* Phase 1: send opcode */
    cs_low();
    spi_device_polling_transmit(s_spi, &t_cmd);
    cs_high();

    wait_busy();

    /* Phase 2: read response */
    cs_low();
    spi_device_polling_transmit(s_spi, &t_rx);
    cs_high();

    /* 9-bit RSSI assembly: (buf[4] << 1) | ((buf[6] & 0x04) >> 2), then /2, negate */
    uint16_t raw = ((uint16_t)rx[4] << 1) | ((rx[6] & 0x04) >> 2);
    return -(int8_t)(raw / 2);
}

/* Read 1-byte chip status */
static uint8_t rf_read_status(void)
{
    wait_busy();

    uint8_t tx = 0x00;
    uint8_t rx_val = 0;

    spi_transaction_t t = {};
    t.length    = 8;
    t.tx_buffer = &tx;
    t.rx_buffer = &rx_val;

    cs_low();
    spi_device_polling_transmit(s_spi, &t);
    cs_high();
    return rx_val;
}

/* ── Command helpers ──────────────────────────────────────────────────── */

static void clear_irq(uint32_t mask)
{
    uint8_t cmd[6] = {
        0x01, 0x16,
        (uint8_t)(mask >> 24), (uint8_t)(mask >> 16),
        (uint8_t)(mask >> 8),  (uint8_t)(mask & 0xFF)
    };
    rf_write_cmd(cmd, 6);
}

static void clear_errors(void)
{
    uint8_t cmd[4] = { 0x01, 0x11, 0x00, 0x00 };
    rf_write_cmd(cmd, 4);
}

static void set_dio_irq(uint8_t dio_num, uint32_t irq_mask)
{
    uint8_t cmd[7] = {
        0x01, 0x15, dio_num,
        (uint8_t)(irq_mask >> 24), (uint8_t)(irq_mask >> 16),
        (uint8_t)(irq_mask >> 8),  (uint8_t)(irq_mask & 0xFF)
    };
    rf_write_cmd(cmd, 7);
}

static void clear_tx_fifo(void)
{
    uint8_t cmd[2] = { 0x01, 0x1F };
    rf_write_cmd(cmd, 2);
}

static void clear_rx_fifo(void)
{
    uint8_t cmd[2] = { 0x01, 0x1E };
    rf_write_cmd(cmd, 2);
}

static void set_rx_continuous(void)
{
    uint8_t cmd[5] = { 0x02, 0x0C, 0xFF, 0xFF, 0xFF };
    rf_write_cmd(cmd, 5);
}

static void set_tx(void)
{
    uint8_t cmd[5] = { 0x02, 0x0D, 0x00, 0x00, 0x00 };
    rf_write_cmd(cmd, 5);
}

/* ── Radio initialization sequence ────────────────────────────────────── */
/* Translated from init_radio() in firmware/esp32-c3-flrc/main/main.cpp     */

static void init_radio(void)
{
    /* Hardware reset */
    gpio_set_level(s_pins.rst, 0);
    vTaskDelay(pdMS_TO_TICKS(1));
    gpio_set_level(s_pins.rst, 1);
    vTaskDelay(pdMS_TO_TICKS(50));

    /* CLEAR_ERRORS */
    clear_errors();
    vTaskDelay(pdMS_TO_TICKS(1));

    /* SET_STANDBY (STDBY_XOSC) */
    uint8_t cmd_stdby[] = { 0x01, 0x28, 0x01 };
    rf_write_cmd(cmd_stdby, 3);
    vTaskDelay(pdMS_TO_TICKS(5));

    /* SET_PACKET_TYPE FLRC (0x05) */
    uint8_t cmd_pkttype[] = { 0x02, 0x07, 0x05 };
    rf_write_cmd(cmd_pkttype, 3);
    vTaskDelay(pdMS_TO_TICKS(1));

    /* SET_RF_FREQUENCY */
    uint32_t frf = (uint32_t)((s_freq_mhz * 1e6 * (double)(1ULL << 18)) /
                              (LR2021_XTAL_MHZ * 1e6));
    uint8_t cmd_freq[] = {
        0x02, 0x00,
        (uint8_t)(frf >> 16), (uint8_t)(frf >> 8), (uint8_t)(frf & 0xFF)
    };
    rf_write_cmd(cmd_freq, 5);
    vTaskDelay(pdMS_TO_TICKS(1));

    /* SET_RX_PATH (HF path for 2.4 GHz) */
    uint8_t cmd_rxpath[] = { 0x02, 0x01, 0x01, 0x00 };
    rf_write_cmd(cmd_rxpath, 4);
    vTaskDelay(pdMS_TO_TICKS(1));

    /* CALIB_FRONT_END — mandatory before RX */
    uint16_t fe_freq = (uint16_t)((s_freq_mhz / 4.0f) + 0.5f) | 0x8000;
    uint8_t cmd_calfe[] = {
        0x01, 0x23,
        (uint8_t)(fe_freq >> 8), (uint8_t)(fe_freq & 0xFF),
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00
    };
    rf_write_cmd(cmd_calfe, 10);
    vTaskDelay(pdMS_TO_TICKS(5));

    /* CALIBRATE (mask 0x5F — bit 5 undefined, do not use 0x6F) */
    uint8_t cmd_cal[] = { 0x01, 0x22, 0x5F };
    rf_write_cmd(cmd_cal, 3);
    vTaskDelay(pdMS_TO_TICKS(5));

    /* SET_FLRC_MOD_PARAMS: BR code, CR=1/0 + BT=0.5 = 0x25 */
    uint8_t br_code;
    if (s_bitrate_kbps >= 2600)      br_code = 0x00;
    else if (s_bitrate_kbps >= 2080) br_code = 0x01;
    else if (s_bitrate_kbps >= 1300) br_code = 0x02;
    else if (s_bitrate_kbps >= 1040) br_code = 0x03;
    else if (s_bitrate_kbps >= 650)  br_code = 0x04;
    else if (s_bitrate_kbps >= 520)  br_code = 0x05;
    else if (s_bitrate_kbps >= 325)  br_code = 0x06;
    else                             br_code = 0x07;

    uint8_t cmd_modparams[] = { 0x02, 0x48, br_code, 0x25 };
    rf_write_cmd(cmd_modparams, 4);
    vTaskDelay(pdMS_TO_TICKS(1));

    /* SET_FLRC_SYNCWORD */
    uint8_t cmd_sync[] = { 0x02, 0x4C, 0x01, SYNC_WORD_0, SYNC_WORD_1, SYNC_WORD_2, SYNC_WORD_3 };
    rf_write_cmd(cmd_sync, 7);
    vTaskDelay(pdMS_TO_TICKS(1));

    /* SET_FLRC_PACKET_PARAMS: fixed 255-byte, no CRC */
    uint8_t cmd_pktparams[] = {
        0x02, 0x49,
        0x0C,  /* preamble=8 | syncLen=4/2 */
        0x4C,  /* syncTx=1 | syncMatch=1 | fixed=1 | crc=0 */
        0x00, (uint8_t)LR2021_PKT_SIZE
    };
    rf_write_cmd(cmd_pktparams, 6);
    vTaskDelay(pdMS_TO_TICKS(1));

    /* SET_RX_TX_FALLBACK (FS mode) */
    uint8_t cmd_fallback[] = { 0x02, 0x06, 0x03 };
    rf_write_cmd(cmd_fallback, 3);
    vTaskDelay(pdMS_TO_TICKS(1));

    /* SET_TX_PARAMS: power * 2, ramp 16us */
    uint8_t cmd_power[] = { 0x02, 0x03, (uint8_t)(s_tx_power * 2), 0x04 };
    rf_write_cmd(cmd_power, 4);
    vTaskDelay(pdMS_TO_TICKS(1));

    /* SET_PA_CONFIG (HF path) */
    uint8_t cmd_paconfig[] = { 0x02, 0x02, 0x80, 0x00, 0x60, 0x07, 0x10 };
    rf_write_cmd(cmd_paconfig, 7);
    vTaskDelay(pdMS_TO_TICKS(1));

    /* DIO9 = IRQ function */
    uint8_t cmd_dio[] = { 0x01, 0x12, 0x09, 0x11 };
    rf_write_cmd(cmd_dio, 4);
    vTaskDelay(pdMS_TO_TICKS(1));

    /* Default: RX_DONE IRQ on DIO9 */
    set_dio_irq(9, IRQ_RX_DONE);
    vTaskDelay(pdMS_TO_TICKS(1));

    /* Clear all IRQ */
    clear_irq(IRQ_ALL);

    uint8_t st = rf_read_status();
    ESP_LOGI(TAG, "Radio init complete. Status=0x%02X, freq=%.1f MHz, power=%d dBm",
             st, s_freq_mhz, s_tx_power);
}

/* ── Public API ───────────────────────────────────────────────────────── */

esp_err_t lr2021_radio_init(const lr2021_radio_pins_t *pins)
{
    if (!pins) {
        s_pins = LR2021_PINS_DEFAULT;
    } else {
        s_pins = *pins;
    }

    ESP_LOGI(TAG, "Initializing LR2021 radio (raw 2-byte opcode SPI, NO RadioLib)");

    /* GPIO: CS + RST as outputs */
    gpio_config_t out_conf = {};
    out_conf.pin_bit_mask = (1ULL << s_pins.cs) | (1ULL << s_pins.rst);
    out_conf.mode = GPIO_MODE_OUTPUT;
    gpio_config(&out_conf);
    cs_high();
    gpio_set_level(s_pins.rst, 1);

    /* GPIO: BUSY + IRQ as inputs (no pull) */
    gpio_config_t in_conf = {};
    in_conf.pin_bit_mask = (1ULL << s_pins.busy) | (1ULL << s_pins.irq);
    in_conf.mode = GPIO_MODE_INPUT;
    in_conf.pull_down_en = GPIO_PULLDOWN_DISABLE;
    in_conf.pull_up_en = GPIO_PULLUP_DISABLE;
    gpio_config(&in_conf);

    /* SPI bus init */
    spi_bus_config_t buscfg = {};
    buscfg.miso_io_num = s_pins.miso;
    buscfg.mosi_io_num = s_pins.mosi;
    buscfg.sclk_io_num = s_pins.sck;
    buscfg.max_transfer_sz = (LR2021_PKT_SIZE + 8) * 2;

    esp_err_t ret = spi_bus_initialize(SPI2_HOST, &buscfg, SPI_DMA_CH_AUTO);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "SPI bus init failed: %s", esp_err_to_name(ret));
        return ret;
    }
    ESP_LOGI(TAG, "SPI bus initialized (SPI2_HOST, DMA auto)");

    /* SPI device — CS handled manually for exact timing control */
    spi_device_interface_config_t devcfg = {};
    devcfg.clock_speed_hz = LR2021_SPI_CLOCK_HZ;
    devcfg.mode = 0;                /* SPI mode 0 */
    devcfg.spics_io_num = -1;       /* CS manual */
    devcfg.queue_size = 1;
    devcfg.flags = SPI_DEVICE_HALFDUPLEX;

    ret = spi_bus_add_device(SPI2_HOST, &devcfg, &s_spi);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "SPI device add failed: %s", esp_err_to_name(ret));
        return ret;
    }
    ESP_LOGI(TAG, "SPI device added: %d MHz, mode 0, half-duplex",
             LR2021_SPI_CLOCK_HZ / 1000000);

    /* Initialize radio with proven FLRC sequence */
    init_radio();

    s_inited = true;
    s_in_rx = false;
    ESP_LOGI(TAG, "LR2021 radio ready (STDBY). Call lr2021_radio_start_rx() to listen.");
    return ESP_OK;
}

void lr2021_radio_tx(const uint8_t *frame, uint16_t len)
{
    if (!s_inited || !frame || len == 0) return;

    /* Clamp to max payload */
    if (len > LR2021_MAX_PAYLOAD) len = LR2021_MAX_PAYLOAD;

    bool was_in_rx = s_in_rx;

    /* Build 255-byte packet: [len_hi][len_lo][payload][zero-pad] */
    static uint8_t pkt[LR2021_PKT_SIZE];
    memset(pkt, 0, sizeof(pkt));
    pkt[0] = (uint8_t)(len >> 8);
    pkt[1] = (uint8_t)(len & 0xFF);
    memcpy(pkt + LR2021_FRAME_HEADER, frame, len);

    /* Configure IRQ for TX_DONE */
    set_dio_irq(9, IRQ_TX_DONE);
    vTaskDelay(pdMS_TO_TICKS(1));

    /* Clear IRQ + TX FIFO */
    clear_irq(IRQ_ALL);
    clear_tx_fifo();

    /* Write packet to TX FIFO (batched: opcode + 255 bytes) */
    rf_write_tx_fifo(pkt, LR2021_PKT_SIZE);

    /* Trigger TX */
    set_tx();

    /* Wait for TX_DONE — IRQ pin goes HIGH */
    uint32_t timeout = 500000;
    while (!irq_high() && --timeout) {
        /* tight spin */
    }

    if (timeout == 0) {
        ESP_LOGW(TAG, "TX timeout (no IRQ) for %u-byte frame", len);
    }

    /* Clear TX IRQ */
    clear_irq(IRQ_ALL);

    /* Return to RX if we were listening */
    if (was_in_rx) {
        vTaskDelay(pdMS_TO_TICKS(1));
        set_dio_irq(9, IRQ_RX_DONE);
        vTaskDelay(pdMS_TO_TICKS(1));
        clear_irq(IRQ_ALL);
        clear_rx_fifo();
        clear_errors();
        set_rx_continuous();
        s_in_rx = true;
    }
}

void lr2021_radio_set_rx_callback(lr2021_rx_callback_t cb)
{
    s_rx_cb = cb;
}

esp_err_t lr2021_radio_start_rx(void)
{
    if (!s_inited) return ESP_ERR_INVALID_STATE;

    /* Configure IRQ for RX_DONE */
    set_dio_irq(9, IRQ_RX_DONE);
    vTaskDelay(pdMS_TO_TICKS(1));

    /* Clear all state */
    clear_irq(IRQ_ALL);
    clear_rx_fifo();
    clear_errors();

    /* Enter continuous RX */
    set_rx_continuous();
    vTaskDelay(pdMS_TO_TICKS(2));

    s_in_rx = true;
    ESP_LOGI(TAG, "Entered continuous RX mode");
    return ESP_OK;
}

void lr2021_radio_poll(void)
{
    if (!s_inited || !s_in_rx) return;

    /* Check IRQ pin — if not high, no packet */
    if (!irq_high()) return;

    /* Read the 32-bit IRQ status to confirm RX_DONE */
    uint32_t irq = rf_get_irq_status();

    if (!(irq & IRQ_RX_DONE)) {
        /* Some other IRQ fired — clear and return */
        clear_irq(IRQ_ALL);
        return;
    }

    /* Read RSSI before clearing (valid only after RX_DONE, before clear) */
    s_last_rssi = rf_get_rssi();

    /* Read packet buffer (255 bytes fixed) */
    static uint8_t buf[LR2021_PKT_SIZE];
    rf_read_rx_fifo(buf, LR2021_PKT_SIZE);

    /* Clear RX FIFO + errors + IRQ + re-arm */
    clear_rx_fifo();
    clear_errors();
    clear_irq(IRQ_ALL);
    set_rx_continuous();

    /* Extract frame length from 2-byte header */
    uint16_t frame_len = ((uint16_t)buf[0] << 8) | buf[1];

    if (frame_len == 0 || frame_len > LR2021_MAX_PAYLOAD) {
        /* Invalid frame — likely noise or corrupted header */
        ESP_LOGD(TAG, "RX: invalid frame_len=%u (raw[0]=0x%02X raw[1]=0x%02X)",
                 frame_len, buf[0], buf[1]);
        return;
    }

    /* Deliver frame to callback */
    if (s_rx_cb) {
        s_rx_cb(buf + LR2021_FRAME_HEADER, frame_len, s_last_rssi);
    }
}

int8_t lr2021_radio_get_last_rssi(void)
{
    return s_last_rssi;
}
