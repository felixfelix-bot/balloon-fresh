/*
 * lr2021_radio.h — Raw 2-byte opcode SPI radio driver for Semtech LR2021
 *
 * Bridges the proven raw LR2021 SPI protocol to the mesh_adapter layer.
 * Does NOT use RadioLib. See ADR-020 for rationale.
 *
 * Protocol reference: firmware/esp32-c3-flrc/main/main.cpp (PROVEN WORKING)
 *
 * SPDX-License-Identifier: MIT
 */
#pragma once

#include <stdint.h>
#include <stdbool.h>
#include "esp_err.h"
#include "driver/gpio.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ── LR2021 2-byte opcodes (verified against TheClams Rust driver) ────── */
#define LR2021_SET_RF_FREQUENCY       0x0200
#define LR2021_SET_RX_PATH            0x0201
#define LR2021_SET_TX_PATH            0x0202
#define LR2021_SET_PA_CONFIG          0x0202
#define LR2021_SET_TX_PARAMS          0x0203
#define LR2021_SET_RX_TX_FALLBACK     0x0206
#define LR2021_SET_PACKET_TYPE        0x0207
#define LR2021_SET_RX                 0x020C
#define LR2021_SET_TX                 0x020D
#define LR2021_CLEAR_ERRORS           0x0111
#define LR2021_SET_DIO_FUNCTION       0x0112
#define LR2021_SET_DIO_IRQ_CONFIG     0x0115
#define LR2021_CLEAR_IRQ              0x0116
#define LR2021_GET_IRQ_STATUS         0x0117
#define LR2021_CALIBRATE              0x0122
#define LR2021_CALIB_FRONT_END        0x0123
#define LR2021_SET_STANDBY            0x0128
#define LR2021_SET_FS                 0x0129
#define LR2021_CLEAR_TX_FIFO          0x011F
#define LR2021_CLEAR_RX_FIFO          0x011E
#define LR2021_READ_RX_FIFO           0x0001
#define LR2021_WRITE_TX_FIFO          0x0002
#define LR2021_GET_FLRC_PACKET_STATUS 0x024B

/* ── IRQ bits (32-bit) ────────────────────────────────────────────────── */
#define IRQ_RX_DONE    0x00040000   /* bit 18 */
#define IRQ_TX_DONE    0x00080000   /* bit 19 */
#define IRQ_CRC_ERROR  0x00400000   /* bit 22 */
#define IRQ_CMD_ERROR  0x00020000   /* bit 17 */
#define IRQ_ALL        0xFFFFFFFF

/* ── FLRC-specific ────────────────────────────────────────────────────── */
#define LR2021_SET_FLRC_MOD_PARAMS    0x0248
#define LR2021_SET_FLRC_PKT_PARAMS    0x0249
#define LR2021_SET_FLRC_SYNCWORD      0x024C

#define PKT_TYPE_FLRC   0x05

/* ── Packet and radio constants ───────────────────────────────────────── */
#define LR2021_PKT_SIZE        255
#define LR2021_SPI_CLOCK_HZ    20000000   /* 20 MHz — ESP32 can do this */
#define LR2021_XTAL_MHZ        52.0f      /* NiceRF module uses XTAL */

/* Frame wire format: [len_hi][len_lo][payload][zero-pad to 255] */
#define LR2021_FRAME_HEADER    2
#define LR2021_MAX_PAYLOAD     (LR2021_PKT_SIZE - LR2021_FRAME_HEADER)

/* ── Pin configuration ────────────────────────────────────────────────── */
typedef struct {
    gpio_num_t sck;
    gpio_num_t miso;
    gpio_num_t mosi;
    gpio_num_t cs;     /* NSS — manual control */
    gpio_num_t busy;
    gpio_num_t irq;    /* DIO9 */
    gpio_num_t rst;
} lr2021_radio_pins_t;

/* Default pins for ESP32-C3 Mini V1 (verified across 2 sources) */
#define LR2021_PINS_DEFAULT ((lr2021_radio_pins_t){ \
    .sck  = GPIO_NUM_6,  \
    .miso = GPIO_NUM_2,  \
    .mosi = GPIO_NUM_7,  \
    .cs   = GPIO_NUM_10, \
    .busy = GPIO_NUM_4,  \
    .irq  = GPIO_NUM_5,  \
    .rst  = GPIO_NUM_3,  \
})

/* Radio defaults */
#define LR2021_DEFAULT_FREQ_MHZ   2440.0f
#define LR2021_DEFAULT_TX_POWER   12       /* dBm */
#define LR2021_DEFAULT_BR_KBPS    2600     /* FLRC bitrate */

/* ── Callback for received frames ─────────────────────────────────────── */
typedef void (*lr2021_rx_callback_t)(const uint8_t *data, uint16_t len,
                                      int8_t rssi_dbm);

/* ── Public API ───────────────────────────────────────────────────────── */

/**
 * Initialize SPI bus + LR2021 chip with FLRC modulation.
 *
 * Performs: hardware reset → CLEAR_ERRORS → STDBY → SET_PACKET_TYPE(FLRC) →
 * SET_RF_FREQUENCY → SET_RX_PATH(HF) → CALIB_FRONT_END → CALIBRATE →
 * SET_FLRC_MOD_PARAMS → SET_FLRC_SYNCWORD → SET_FLRC_PKT_PARAMS →
 * SET_RX_TX_FALLBACK → SET_TX_POWER → SET_PA_CONFIG → DIO config →
 * CLEAR_IRQ.
 *
 * Leaves radio in STDBY_XOSC. Call lr2021_radio_start_rx() to begin listening.
 *
 * @param pins  Pin assignment. Pass &LR2021_PINS_DEFAULT for ESP32-C3 Mini V1.
 * @return ESP_OK on success, ESP_FAIL on SPI init failure.
 */
esp_err_t lr2021_radio_init(const lr2021_radio_pins_t *pins);

/**
 * Transmit a frame over radio.
 *
 * This function matches the mesh_frame_send_fn signature so it can be
 * used directly as mesh_adapter_config_t.send_fn.
 *
 * Pads the frame to 255 bytes with a 2-byte big-endian length prefix.
 * If the radio is in RX mode, temporarily switches to TX, then returns to RX.
 *
 * @param frame  Frame data to transmit.
 * @param len    Frame length in bytes (max LR2021_MAX_PAYLOAD = 253).
 */
void lr2021_radio_tx(const uint8_t *frame, uint16_t len);

/**
 * Register a callback invoked when a valid frame is received.
 *
 * @param cb  Callback function, or NULL to disable.
 */
void lr2021_radio_set_rx_callback(lr2021_rx_callback_t cb);

/**
 * Enter continuous RX mode.
 *
 * Configures IRQ for RX_DONE, clears state, and issues SET_RX with
 * maximum timeout (continuous). The radio stays in RX until a TX
 * interrupts it.
 *
 * @return ESP_OK on success.
 */
esp_err_t lr2021_radio_start_rx(void);

/**
 * Non-blocking RX poll — call from the main loop.
 *
 * Checks the IRQ pin. If RX_DONE is asserted, reads the packet buffer,
 * extracts RSSI, re-arms RX, and invokes the registered callback.
 *
 * Returns immediately if no packet is pending.
 */
void lr2021_radio_poll(void);

/**
 * Get the RSSI from the most recent received packet.
 * Valid only after lr2021_radio_poll() delivers a frame.
 *
 * @return RSSI in dBm (negative), or 0 if no packet received yet.
 */
int8_t lr2021_radio_get_last_rssi(void);

#ifdef __cplusplus
}
#endif
