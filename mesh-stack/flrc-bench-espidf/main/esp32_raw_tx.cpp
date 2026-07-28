/*
 * esp32_raw_tx.cpp — ESP32 FLRC TX with RAW SPI init
 *
 * Direct port of RP2040 flrc_dma_tx.cpp. No RadioLib for init.
 * Uses raw SPI register writes + EspHalC3 GDMA (40 MHz SPI).
 * TX hot loop: clearErrors → clearIrq → clearTxFifo → writeTxFifo → setTx → poll BUSY
 *
 * Auto-starts TX 10s after boot (gives RX time to enter RX mode).
 * Sends DEADBEEF end marker with total count after burst.
 *
 * Pins: SCK=6 MISO=2 MOSI=7 NSS=10 BUSY=4 RST=3 DIO9=5 LED=8
 */

#include <sdkconfig.h>

#ifdef CONFIG_BENCH_MODE_RAW_TX

#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "esp_rom_sys.h"
#include "driver/gpio.h"
#include "driver/usb_serial_jtag.h"
#include "driver/usb_serial_jtag_vfs.h"
#include <RadioLib.h>
#include "EspHalC3.h"

static const char *TAG = "RAWTX";

// ─── Pins ────────────────────────────────────────────────────────────
#define PIN_SCK     6
#define PIN_MOSI    7
#define PIN_MISO    2
#define PIN_NSS     10
#define PIN_BUSY    4
#define PIN_RST     3
#define PIN_DIO9    5
#define PIN_LED     8

// ─── FLRC Config (MUST match RX) ─────────────────────────────────────
#define FLRC_FREQ_MHZ   2440.0f
#define FLRC_PKT_SIZE   255
#define TX_PKT_COUNT    1000
#define TX_POWER_DBM    12  // HF FLRC safe max

// ─── Sync word — MUST match RX ───────────────────────────────────────
#define SYNC_WORD_0   0xCD
#define SYNC_WORD_1   0x05
#define SYNC_WORD_2   0xCA
#define SYNC_WORD_3   0xFE

// ─── ESP32 HAL ───────────────────────────────────────────────────────
static EspHalC3 *hal = nullptr;

// ─── Raw SPI helpers ─────────────────────────────────────────────────
static inline void rfWaitBusy() {
    uint32_t timeout = esp_timer_get_time() + 50000;
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

static uint8_t rfReadStatus() {
    uint8_t st = 0;
    rfWaitBusy();
    gpio_set_level((gpio_num_t)PIN_NSS, 0);
    hal->spiTransfer(nullptr, 1, &st);
    gpio_set_level((gpio_num_t)PIN_NSS, 1);
    return st;
}

static uint32_t rfReadIrqStatus() {
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

static void rfClearErrors() {
    uint8_t cmd[] = {0x01, 0x11, 0x00, 0x00};
    rfWriteCmd(cmd, 4);
}

static void rfClearTxFifo() {
    uint8_t cmd[] = {0x01, 0x1F};
    rfWriteCmd(cmd, 2);
}

static void rfSetTx() {
    uint8_t cmd[] = {0x02, 0x0D, 0x00, 0x00, 0x00};
    rfWriteCmd(cmd, 5);
}

// DMA TX FIFO buffer: opcode + payload
static uint8_t dma_fifo_buf[2 + FLRC_PKT_SIZE];

static void rfWriteTxFifo(const uint8_t *data, size_t len) {
    dma_fifo_buf[0] = 0x00;  // WRITE_TX_FIFO opcode MSB
    dma_fifo_buf[1] = 0x02;  // opcode LSB
    memcpy(&dma_fifo_buf[2], data, len);

    rfWaitBusy();
    gpio_set_level((gpio_num_t)PIN_NSS, 0);
    hal->spiTransfer(dma_fifo_buf, 2 + len, nullptr);
    gpio_set_level((gpio_num_t)PIN_NSS, 1);
}

// ─── Raw SPI Init (matches RP2040 flrc_dma_tx.cpp + syncword from RX) ─
static bool rawInitRadio() {
    // 0. Hardware reset
    gpio_set_level((gpio_num_t)PIN_RST, 0);
    esp_rom_delay_us(200);
    gpio_set_level((gpio_num_t)PIN_RST, 1);
    vTaskDelay(pdMS_TO_TICKS(50));

    // 1. CLEAR_ERRORS
    rfClearErrors();
    vTaskDelay(pdMS_TO_TICKS(1));

    // 2. SET_STANDBY (STDBY_XOSC = 0x01)
    {
        uint8_t cmd[] = {0x01, 0x28, 0x01};
        rfWriteCmd(cmd, 3);
    }
    vTaskDelay(pdMS_TO_TICKS(5));

    // 3. SET_PACKET_TYPE FLRC=5
    {
        uint8_t cmd[] = {0x02, 0x07, 0x05};
        rfWriteCmd(cmd, 3);
    }
    vTaskDelay(pdMS_TO_TICKS(1));

    // 4. SET_RF_FREQUENCY — send raw Hz (same as RP2040 RX)
    {
        uint32_t rfFreq = (uint32_t)(FLRC_FREQ_MHZ * 1000000.0f);
        uint8_t cmd[] = {
            0x02, 0x00,
            (uint8_t)(rfFreq >> 24), (uint8_t)(rfFreq >> 16),
            (uint8_t)(rfFreq >> 8),  (uint8_t)(rfFreq & 0xFF)
        };
        rfWriteCmd(cmd, 6);
    }
    vTaskDelay(pdMS_TO_TICKS(1));

    // 5. SET_RX_PATH (HF path for 2.4 GHz) — needed even on TX for PLL
    {
        uint8_t cmd[] = {0x02, 0x01, 0x01, 0x00};
        rfWriteCmd(cmd, 4);
    }
    vTaskDelay(pdMS_TO_TICKS(1));

    // 6. CALIB_FRONT_END
    {
        uint8_t cmd[] = {0x01, 0x23, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};
        rfWriteCmd(cmd, 8);
    }
    vTaskDelay(pdMS_TO_TICKS(5));
    rfWaitBusy();

    // 7. CALIBRATE — 0x5F
    {
        uint8_t cmd[] = {0x01, 0x22, 0x5F};
        rfWriteCmd(cmd, 3);
    }
    vTaskDelay(pdMS_TO_TICKS(5));
    rfWaitBusy();

    // 8. SET_FLRC_MOD_PARAMS — Br2600, Bt1p0: 0x27
    {
        uint8_t cmd[] = {0x02, 0x48, 0x00, 0x27};
        rfWriteCmd(cmd, 4);
    }
    vTaskDelay(pdMS_TO_TICKS(1));

    // 9. SET_FLRC_SYNCWORD — MUST match RX: CD05CAFE
    {
        uint8_t cmd[] = {
            0x02, 0x4C, 0x01,
            SYNC_WORD_0, SYNC_WORD_1, SYNC_WORD_2, SYNC_WORD_3
        };
        rfWriteCmd(cmd, 7);
    }
    vTaskDelay(pdMS_TO_TICKS(1));

    // 10. SET_FLRC_PACKET_PARAMS — same as RX but SwTx=1 (TX transmits syncword)
    // byte2 = (3<<2)|2 = 0x0E (16b preamble, 32b SW)
    // byte3 = (1<<6)|(1<<3)|(1<<2)|0 = 0x4C (SwTx=1, Match1, Fixed, CRC_OFF)
    {
        uint8_t cmd[] = {
            0x02, 0x49,
            0x0E,
            0x4C,   // SwTx=1(TX) | Match1 | Fixed | CRC_OFF
            0x00, (uint8_t)FLRC_PKT_SIZE
        };
        rfWriteCmd(cmd, 6);
    }
    vTaskDelay(pdMS_TO_TICKS(1));

    // 11. SET_PA_CONFIG (HF PA select via bit 7)
    {
        uint8_t cmd[] = {0x02, 0x02, 0x80, 0x00, 0x60, 0x07, 0x10};
        rfWriteCmd(cmd, 7);
    }
    vTaskDelay(pdMS_TO_TICKS(1));

    // 12. SET_TX_PARAMS (power + ramp) — txPower*2 as raw byte
    {
        uint8_t cmd[] = {0x02, 0x03, (uint8_t)(TX_POWER_DBM * 2), 0x04};
        rfWriteCmd(cmd, 4);
    }
    vTaskDelay(pdMS_TO_TICKS(1));

    // 13. SET_RX_TX_FALLBACK (Fs=0x03 — keeps PLL running between TX cycles)
    {
        uint8_t cmd[] = {0x02, 0x06, 0x03};
        rfWriteCmd(cmd, 3);
    }
    vTaskDelay(pdMS_TO_TICKS(1));

    // 14. DIO function — DIO9 = IRQ for TX_DONE
    {
        uint8_t cmd[] = {0x01, 0x12, 0x09, 0x11};
        rfWriteCmd(cmd, 4);
    }
    vTaskDelay(pdMS_TO_TICKS(1));

    // 15. DIO IRQ config — map TX_DONE (bit 19 = 0x00080000) to DIO9
    {
        uint8_t cmd[] = {0x01, 0x15, 0x09, 0x00, 0x08, 0x00, 0x00};
        rfWriteCmd(cmd, 7);
    }
    vTaskDelay(pdMS_TO_TICKS(1));

    rfClearIrq();
    vTaskDelay(pdMS_TO_TICKS(1));

    uint8_t st = rfReadStatus();
    uint32_t irq = rfReadIrqStatus();
    ESP_LOGI(TAG, "INIT Status=0x%02X IRQ=0x%08lX", st, (unsigned long)irq);

    if ((st >> 4) == 0x04 || (st >> 4) == 0x07 || (irq & 0x00020000)) {
        ESP_LOGI(TAG, "RADIO_INIT_OK");
        return true;
    }
    ESP_LOGE(TAG, "RADIO_INIT_FAIL (St=0x%02X)", st);
    return false;
}

// ─── TX burst ────────────────────────────────────────────────────────
static volatile bool radioReady = false;

static void runTransmit() {
    if (!radioReady) {
        printf("ERR: radio not initialized\n");
        fflush(stdout);
        return;
    }

    printf("TX_START count=%d pktSize=%d\n", TX_PKT_COUNT, FLRC_PKT_SIZE);
    fflush(stdout);
    vTaskDelay(pdMS_TO_TICKS(10));

    // Pre-build packet payload
    uint8_t pkt[FLRC_PKT_SIZE];
    for (int j = 4; j < FLRC_PKT_SIZE; j++) pkt[j] = (uint8_t)(j & 0xFF);

    uint32_t startMs = (uint32_t)(esp_timer_get_time() / 1000ULL);
    uint32_t txDoneCount = 0;
    uint32_t txTimeoutCount = 0;

    for (int i = 0; i < TX_PKT_COUNT; i++) {
        // Update seq bytes
        pkt[0] = (uint8_t)(i >> 24);
        pkt[1] = (uint8_t)(i >> 16);
        pkt[2] = (uint8_t)(i >> 8);
        pkt[3] = (uint8_t)(i & 0xFF);

        // 0. Clear errors (accumulate across packets)
        rfClearErrors();

        // 1. Clear IRQ flags
        rfClearIrq();

        // 1b. Clear TX FIFO
        rfClearTxFifo();

        // 2. Write TX FIFO
        rfWriteTxFifo(pkt, FLRC_PKT_SIZE);

        // 3. Trigger TX
        rfSetTx();

        // 4. Wait for BUSY LOW = TX complete
        uint32_t timeout = esp_timer_get_time() + 50000; // 50ms
        bool txDone = false;
        while (esp_timer_get_time() < timeout) {
            if (gpio_get_level((gpio_num_t)PIN_BUSY) == 0) {
                txDone = true;
                break;
            }
        }

        // Diagnostic for first 5 packets
        if (i < 5) {
            uint8_t stPost = rfReadStatus();
            uint32_t irqStatus = rfReadIrqStatus();
            ESP_LOGI(TAG, "PKT %d: busy=%d postSt=0x%02X IRQ=0x%08lX",
                     i, txDone ? 1 : 0, stPost,
                     (unsigned long)irqStatus);
        }

        if (txDone) txDoneCount++;
        else txTimeoutCount++;

        // Progress every 250
        if ((i + 1) % 250 == 0) {
            ESP_LOGI(TAG, "TX %d/%d (done=%lu to=%lu)",
                     i + 1, TX_PKT_COUNT,
                     (unsigned long)txDoneCount, (unsigned long)txTimeoutCount);
        }
    }

    ESP_LOGI(TAG, "TX_DONE_STATS: fired=%lu timeout=%lu",
             (unsigned long)txDoneCount, (unsigned long)txTimeoutCount);

    // Send DEADBEEF end marker with total count
    pkt[0] = 0xDE; pkt[1] = 0xAD; pkt[2] = 0xBE; pkt[3] = 0xEF;
    pkt[4] = (uint8_t)(TX_PKT_COUNT >> 24);
    pkt[5] = (uint8_t)(TX_PKT_COUNT >> 16);
    pkt[6] = (uint8_t)(TX_PKT_COUNT >> 8);
    pkt[7] = (uint8_t)(TX_PKT_COUNT & 0xFF);
    rfClearTxFifo();
    rfWriteTxFifo(pkt, FLRC_PKT_SIZE);
    rfSetTx();
    vTaskDelay(pdMS_TO_TICKS(5));

    uint32_t elapsed = (uint32_t)(esp_timer_get_time() / 1000ULL) - startMs;
    float tput = ((float)TX_PKT_COUNT * FLRC_PKT_SIZE * 8.0f) / elapsed;

    printf("=============================================\n");
    printf("  TX sent:     %d\n", TX_PKT_COUNT);
    printf("  TX done:     %lu (timeout %lu)\n",
           (unsigned long)txDoneCount, (unsigned long)txTimeoutCount);
    printf("  Elapsed:     %lu ms\n", (unsigned long)elapsed);
    printf("  TX THROUGHPUT: %.1f kbps\n", tput);
    printf("=============================================\n");
    printf("RESULT_TX,sent=%d,done=%lu,timeout=%lu,elapsed_ms=%lu,throughput_kbps=%.1f\n",
           TX_PKT_COUNT, (unsigned long)txDoneCount, (unsigned long)txTimeoutCount,
           (unsigned long)elapsed, tput);
    fflush(stdout);
}

// ─── App main ────────────────────────────────────────────────────────
#pragma GCC optimize ("O0")
extern "C" void app_main() {
    // VERY FIRST: unbuffered stdout + LED toggle so we can see app_main runs
    // even if USB Serial/JTAG console is not yet ready.
    setvbuf(stdout, NULL, _IONBF, 0);

    gpio_config_t ledConf = {};
    ledConf.pin_bit_mask = (1ULL << PIN_LED);
    ledConf.mode = GPIO_MODE_OUTPUT;
    gpio_config(&ledConf);

    // Immediate LED heartbeat — 5 fast blinks — proves app_main is alive
    for (volatile int i = 0; i < 5; i++) {
        gpio_set_level((gpio_num_t)PIN_LED, 1);
        vTaskDelay(pdMS_TO_TICKS(100));
        gpio_set_level((gpio_num_t)PIN_LED, 0);
        vTaskDelay(pdMS_TO_TICKS(100));
    }

    // Wait for USB Serial/JTAG host enumeration so the HELLO line is visible
    vTaskDelay(pdMS_TO_TICKS(2000));

    // Print HELLO repeatedly for a few seconds because USB Serial/JTAG CDC
    // drops early output if the host terminal hasn't opened the port yet.
    for (int hello = 0; hello < 12; hello++) {
        printf("HELLO FROM ESP32 RAW_TX\n");
        fflush(stdout);
        vTaskDelay(pdMS_TO_TICKS(250));
    }

    ESP_LOGI(TAG, "=== ESP32 FLRC TX (RAW SPI + GDMA) ===");

    // Boot blink
    for (volatile int i = 0; i < 3; i++) {
        gpio_set_level((gpio_num_t)PIN_LED, 1);
        vTaskDelay(pdMS_TO_TICKS(200));
        gpio_set_level((gpio_num_t)PIN_LED, 0);
        vTaskDelay(pdMS_TO_TICKS(200));
    }

    // Init radio pins
    gpio_config_t csConf = {};
    csConf.pin_bit_mask = (1ULL << PIN_NSS);
    csConf.mode = GPIO_MODE_OUTPUT;
    gpio_config(&csConf);
    gpio_set_level((gpio_num_t)PIN_NSS, 1);

    gpio_config_t busyConf = {};
    busyConf.pin_bit_mask = (1ULL << PIN_BUSY);
    busyConf.mode = GPIO_MODE_INPUT;
    gpio_config(&busyConf);

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

    printf("\n");
    printf("=================================================\n");
    printf("  ESP32 FLRC TX (RAW SPI + GDMA)\n");
    printf("  No RadioLib — raw SPI init\n");
    printf("  Freq=%.1f MHz, %d dBm, syncword=CD05CAFE\n", FLRC_FREQ_MHZ, TX_POWER_DBM);
    printf("=================================================\n");
    printf("\n");
    fflush(stdout);

    radioReady = rawInitRadio();
    if (radioReady) {
        printf("RADIO_INIT_OK\n");
        fflush(stdout);
    } else {
        printf("RADIO_INIT_FAILED\n");
        fflush(stdout);
    }

    if (radioReady) {
        gpio_set_level((gpio_num_t)PIN_LED, 0); // LED on
        ESP_LOGI(TAG, "Auto-start TX in 10 seconds (RX gets ready)...");
        printf("TX_START_IN_10S\n");
        fflush(stdout);
        vTaskDelay(pdMS_TO_TICKS(10000));
        runTransmit();
        gpio_set_level((gpio_num_t)PIN_LED, 1); // LED off

        // Repeat every 15s for continuous testing
        while (true) {
            ESP_LOGI(TAG, "Next TX burst in 15s...");
            vTaskDelay(pdMS_TO_TICKS(15000));
            runTransmit();
        }
    } else {
        ESP_LOGE(TAG, "INIT FAILED — stuck here");
        while (true) {
            vTaskDelay(pdMS_TO_TICKS(1000));
        }
    }
}
#pragma GCC reset_options

#endif
