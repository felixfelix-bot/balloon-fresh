/*
 * main.cpp — C1 Radio Validation: TX/RX over LR2021 FLRC (2-node test)
 *
 * Proves EspHalLr2021Radio works on real ESP32-C3 + LR2021 hardware.
 * Two identical boards (c3-a = TX, c3-b = RX) communicate over FLRC.
 *
 * ═══ MODE SELECTION ═══
 *   #define NODE_TX  → TX node: sends 16B packets every 1 s
 *   (comment out)   → RX node: receives and prints packets
 *
 * ═══ BUILD ═══
 *   source ~/esp/esp-idf/export.sh
 *   cd tracker/firmware/radio_test
 *   idf.py set-target esp32c3
 *   idf.py build
 *
 *   For RX node: edit main.cpp, comment out #define NODE_TX, rebuild.
 *
 * ═══ FLASH + MONITOR ═══
 *   TX: idf.py -p /dev/ttyACM0 flash monitor
 *   RX: idf.py -p /dev/ttyACM1 flash monitor
 *
 * ═══ PINS (Lr2021PinConfig defaults) ═══
 *   SCK=GPIO6  MISO=GPIO2  MOSI=GPIO7  CS=GPIO10
 *   BUSY=GPIO4 IRQ=GPIO5   RST=GPIO3   LED=GPIO8
 *
 * ═══ RADIO CONFIG (Lr2021Config defaults) ═══
 *   Freq: 2440 MHz | Bitrate: 2600 kbps FLRC | TX: +12 dBm
 *   Sync: 0x12AD101B | CRC: enabled | Payload: 16 bytes
 */

#include <stdio.h>
#include <string.h>
#include <stdint.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"

#include "esp_idf_lr2021_radio.h"

// ════════════════════════════════════════════════════════════════════
// MODE SELECTION — uncomment for TX, comment out for RX
// ════════════════════════════════════════════════════════════════════
//#define NODE_TX

// ════════════════════════════════════════════════════════════════════
// Test parameters
// ════════════════════════════════════════════════════════════════════
#define TEST_PAYLOAD_LEN   16      // bytes per packet
#define TX_INTERVAL_MS     1000    // TX sends every 1 second
#define LED_PIN            8       // GPIO8 (active LOW on ESP32-C3 Mini V1)
#define IRQ_POLL_MAX_MS    2000    // timeout for TX_DONE / RX_DONE

// TX message: 12 ASCII chars — fills bytes [4..15] after 4-byte counter
static constexpr const char* TX_MSG = "HELLO_FROM_A";   // 12 chars
static_assert(sizeof("HELLO_FROM_A") - 1 == 12, "TX_MSG must be exactly 12 bytes");

// ════════════════════════════════════════════════════════════════════
// LED helpers
// ════════════════════════════════════════════════════════════════════

static void led_init() {
    gpio_config_t io = {};
    io.pin_bit_mask  = (1ULL << LED_PIN);
    io.mode          = GPIO_MODE_OUTPUT;
    io.pull_down_en  = GPIO_PULLDOWN_DISABLE;
    io.pull_up_en    = GPIO_PULLUP_DISABLE;
    io.intr_type     = GPIO_INTR_DISABLE;
    gpio_config(&io);
    gpio_set_level((gpio_num_t)LED_PIN, 1);   // OFF (active LOW)
}

static void led_blink() {
    gpio_set_level((gpio_num_t)LED_PIN, 0);   // ON
    vTaskDelay(pdMS_TO_TICKS(50));
    gpio_set_level((gpio_num_t)LED_PIN, 1);   // OFF
}

// ════════════════════════════════════════════════════════════════════
// TX Mode — send 16B packets every 1 s, poll TX_DONE
// ════════════════════════════════════════════════════════════════════

static void run_tx(EspHalLr2021Radio& radio) {
    printf("=== TX MODE: %d-byte packets every %d ms ===\n",
           TEST_PAYLOAD_LEN, TX_INTERVAL_MS);

    uint32_t seq = 0;

    while (true) {
        // Build packet: [4-byte big-endian seq][12-byte message]
        uint8_t pkt[TEST_PAYLOAD_LEN];
        pkt[0] = (uint8_t)(seq >> 24);
        pkt[1] = (uint8_t)(seq >> 16);
        pkt[2] = (uint8_t)(seq >> 8);
        pkt[3] = (uint8_t)(seq & 0xFF);
        memcpy(pkt + 4, TX_MSG, 12);

        // Trigger TX (send_packet clears IRQ, writes FIFO, starts TX)
        Lr2021Error err = radio.send_packet(pkt, TEST_PAYLOAD_LEN);
        if (err != Lr2021Error::Ok) {
            printf("TX: seq=%lu ERROR=%d\n", (unsigned long)seq, (int)err);
            vTaskDelay(pdMS_TO_TICKS(TX_INTERVAL_MS));
            continue;
        }

        // Poll IRQ status register for TX_DONE (bit 19)
        bool tx_done = false;
        for (int ms = 0; ms < IRQ_POLL_MAX_MS; ms++) {
            uint32_t flags = 0;
            radio.get_irq_status(flags);
            if (flags & IrqSource::TX_DONE) {
                tx_done = true;
                break;
            }
            vTaskDelay(pdMS_TO_TICKS(1));
        }

        if (tx_done) {
            printf("TX: seq=%lu rssi=OK\n", (unsigned long)seq);
            radio.clear_irq();
            led_blink();
        } else {
            printf("TX: seq=%lu TIMEOUT\n", (unsigned long)seq);
            radio.clear_irq();
        }

        seq++;
        vTaskDelay(pdMS_TO_TICKS(TX_INTERVAL_MS));
    }
}

// ════════════════════════════════════════════════════════════════════
// RX Mode — listen for packets, print hex + CRC status
// ════════════════════════════════════════════════════════════════════

static void run_rx(EspHalLr2021Radio& radio) {
    printf("=== RX MODE: listening for %d-byte FLRC packets ===\n",
           TEST_PAYLOAD_LEN);

    uint32_t received = 0;
    uint32_t heartbeat = 0;

    while (true) {
        // Poll IRQ PIN directly (GPIO5/DIO9) — NOT SPI status register.
        // Proven firmware uses pin polling: SPI status reads require BUSY low,
        // which may not happen during continuous RX mode.
        if (!gpio_get_level((gpio_num_t)5)) {
            // Heartbeat every 2 seconds
            if ((heartbeat % 2000) == 0 && heartbeat > 0) {
                printf("DBG: irq_pin=%d busy=%d\n",
                       gpio_get_level((gpio_num_t)5),
                       gpio_get_level((gpio_num_t)4));
            }
            heartbeat++;
            vTaskDelay(pdMS_TO_TICKS(1));
            continue;
        }

        // IRQ pin HIGH — packet received (or other IRQ source)
        // NOW safe to read status register via SPI
        uint32_t flags = 0;
        radio.get_irq_status(flags);

        if (flags & IrqSource::RX_DONE) {
            // CRC is reflected in the IRQ flags (CRC_ERROR bit 20)
            bool crc_ok = !(flags & IrqSource::CRC_ERROR);

            // Read packet from RX FIFO
            uint8_t buf[TEST_PAYLOAD_LEN];
            PacketStatus status;
            radio.read_packet(buf, sizeof(buf), status);

            // Print hex dump + status
            printf("RX: [");
            for (int i = 0; i < (int)status.length && i < TEST_PAYLOAD_LEN; i++) {
                printf("%02X", buf[i]);
                if (i < TEST_PAYLOAD_LEN - 1) printf(" ");
            }
            printf("] rssi=%d snr=%d crc=%s  (#%lu)\n",
                   (int)status.rssi_dbm,
                   (int)status.snr_db,
                   crc_ok ? "OK" : "FAIL",
                   (unsigned long)(received + 1));

            // Clear IRQ, re-arm RX for next packet
            radio.clear_irq();
            radio.start_rx();

            received++;
            led_blink();
        }

        vTaskDelay(pdMS_TO_TICKS(1));   // poll every 1 ms
    }
}

// ════════════════════════════════════════════════════════════════════
// app_main
// ════════════════════════════════════════════════════════════════════

extern "C" void app_main() {
    // Unbuffered stdout — immediate printf output over USB serial
    setvbuf(stdout, NULL, _IONBF, 0);

    printf("\n");
    printf("========================================\n");
    printf(" C1 Radio Validation — LR2021 FLRC\n");
    printf("========================================\n");
    printf("Pins: SCK=6 MISO=2 MOSI=7 CS=10\n");
    printf("      BUSY=4 IRQ=5 RST=3 LED=8\n");
#ifdef NODE_TX
    printf("Mode: TX (NODE_A)\n");
#else
    printf("Mode: RX (NODE_B)\n");
#endif

    led_init();

    // Configure radio (defaults: 2440 MHz, 2600 kbps, +12 dBm, CRC on)
    Lr2021Config config;
    config.payload_length = TEST_PAYLOAD_LEN;   // 16-byte fixed-length FLRC

    // Instantiate radio with default pin config
    EspHalLr2021Radio radio;

    printf("Initializing LR2021...\n");
    Lr2021Error err = radio.init(config);
    if (err != Lr2021Error::Ok) {
        printf("FATAL: radio init failed (err=%d)\n", (int)err);
        // Blink LED rapidly to signal failure
        while (true) {
            gpio_set_level((gpio_num_t)LED_PIN, 0);
            vTaskDelay(pdMS_TO_TICKS(100));
            gpio_set_level((gpio_num_t)LED_PIN, 1);
            vTaskDelay(pdMS_TO_TICKS(100));
        }
    }
    printf("Radio initialized OK\n");

    // Brief settle delay
    vTaskDelay(pdMS_TO_TICKS(500));

#ifdef NODE_TX
    run_tx(radio);
#else
    run_rx(radio);
#endif
}
