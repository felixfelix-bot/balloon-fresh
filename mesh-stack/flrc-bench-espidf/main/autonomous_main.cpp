#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "esp_task_wdt.h"
#include "esp_sleep.h"
#include "driver/gpio.h"
#include <RadioLib.h>
#include "EspHalC3.h"
#include "prbs.h"
#include "test_suite.h"
#include "nvs_results.h"

#ifdef CONFIG_BENCH_MODE_AUTONOMOUS_TX
#define AUTO_ROLE_TX 1
#else
#define AUTO_ROLE_TX 0
#endif

static const char *TAG = "AUTO";

#define LED_GPIO 8

#define LR2021_SCK   6
#define LR2021_MISO  2
#define LR2021_MOSI  7
#define LR2021_NSS   10
#define LR2021_BUSY  4
#define LR2021_RST   3
#define LR2021_DIO9  5

static EspHalC3 *hal = nullptr;
static Module *mod = nullptr;
static LR2021 *radio = nullptr;
static volatile bool rxFlag = false;

#if !AUTO_ROLE_TX
static void IRAM_ATTR onRxIrq(void) { rxFlag = true; }
#endif

static void blink(int times, int ms) {
    gpio_config_t io = {};
    io.pin_bit_mask = (1ULL << LED_GPIO);
    io.mode = GPIO_MODE_OUTPUT;
    gpio_config(&io);
    for (int i = 0; i < times; i++) {
        gpio_set_level((gpio_num_t)LED_GPIO, 0);
        vTaskDelay(pdMS_TO_TICKS(ms));
        gpio_set_level((gpio_num_t)LED_GPIO, 1);
        vTaskDelay(pdMS_TO_TICKS(ms));
    }
    gpio_set_level((gpio_num_t)LED_GPIO, 1);
}

static int16_t initRadioForTest(const AutoTest *t) {
    int16_t state;
    int8_t pwr = t->power;
    if (t->freq > 1500.0f && pwr > 12) pwr = 12;
    if (t->mode == AUTO_FLRC) {
        state = radio->beginFLRC(t->freq, t->bitrate, t->cr, pwr,
                                  t->preamble, RADIOLIB_SHAPING_0_5, 0.0f);
    } else {
        state = radio->begin(t->freq, t->bw, t->sf, t->cr,
                             RADIOLIB_LR2021_LORA_SYNC_WORD_PRIVATE,
                             pwr, t->preamble, 0.0f);
    }
    if (state != RADIOLIB_ERR_NONE) {
        ESP_LOGE(TAG, "Radio init failed for %s: %d", t->name, state);
    }
    return state;
}

#if AUTO_ROLE_TX

static void runAutoTx() {
    ESP_LOGI(TAG, "=== Autonomous TX ===");
    ESP_LOGI(TAG, "%d tests in suite, starting in 10s...", AUTONOMOUS_TEST_COUNT);
    blink(3, 200);
    vTaskDelay(pdMS_TO_TICKS(10000));

    for (int i = 0; i < AUTONOMOUS_TEST_COUNT; i++) {
        const AutoTest *t = &auto_tests[i];
        ESP_LOGI(TAG, "--- Test %d/%d: %s ---", i + 1, AUTONOMOUS_TEST_COUNT, t->name);
        blink(1, 100);

        int16_t state = initRadioForTest(t);
        if (state != RADIOLIB_ERR_NONE) continue;

        uint8_t marker[MARKER_PKT_LEN];
        build_marker(marker, MARKER_TYPE_START, (uint8_t)i, t, 0);
        for (int r = 0; r < 3; r++) {
            radio->transmit(marker, MARKER_PKT_LEN);
            vTaskDelay(pdMS_TO_TICKS(500));
        }

        ESP_LOGI(TAG, "Sending %d pkts, size=%d, delay=%dms...", t->pkt_count, t->pkt_size, t->tx_delay_ms);
        uint32_t startMs = (uint32_t)(esp_timer_get_time() / 1000ULL);
        uint32_t sent = 0;
        uint8_t buf[255];

        for (uint16_t p = 0; p < t->pkt_count; p++) {
            buf[0] = (p >> 24) & 0xFF;
            buf[1] = (p >> 16) & 0xFF;
            buf[2] = (p >> 8) & 0xFF;
            buf[3] = p & 0xFF;
            if (t->pkt_size > 4) {
                prbs15_fill(buf + 4, t->pkt_size - 4, p);
            }
            state = radio->transmit(buf, t->pkt_size);
            if (state == RADIOLIB_ERR_NONE) {
                sent++;
            }
            if (t->tx_delay_ms > 0) {
                vTaskDelay(pdMS_TO_TICKS(t->tx_delay_ms));
            }
        }

        uint32_t elapsed = (uint32_t)(esp_timer_get_time() / 1000ULL) - startMs;
        build_marker(marker, MARKER_TYPE_END, (uint8_t)i, t, sent);
        for (int r = 0; r < 3; r++) {
            radio->transmit(marker, MARKER_PKT_LEN);
            vTaskDelay(pdMS_TO_TICKS(200));
        }

        float tput = (sent > 0 && elapsed > 0) ? (sent * t->pkt_size * 8.0f) / (elapsed) : 0;
        ESP_LOGI(TAG, "%s: sent=%lu/%d elapsed=%lums tput=%.1fkbps",
                 t->name, (unsigned long)sent, t->pkt_count,
                 (unsigned long)elapsed, tput);

        vTaskDelay(pdMS_TO_TICKS(5000));
    }

    ESP_LOGI(TAG, "=== All TX tests complete ===");
    blink(20, 100);
}

#else

static void runAutoRx() {
    ESP_LOGI(TAG, "=== Autonomous RX ===");

    nvs_init();
    nvs_clear_all();

    uint8_t resultCount = 0;
    bool inTest = false;
    AutoTest currentTest = {};
    uint8_t currentTestId = 0;
    uint32_t rxReceived = 0;
    uint32_t rxCrcErrors = 0;
    uint32_t rxTotalSent = 0;
    int32_t rssiSum = 0;
    uint32_t rssiCount = 0;
    int16_t rssiMin = 32767;
    int16_t rssiMax = -32768;
    uint32_t rxBitErrors = 0;
    uint32_t rxBitsChecked = 0;
    uint32_t rxPayloadCorrupt = 0;
    uint32_t testStartMs = 0;

    radio->beginFLRC(868.0f, 2600, RADIOLIB_LR2021_FLRC_CR_3_4, 22, 16, RADIOLIB_SHAPING_0_5, 0.0f);
    radio->setPacketReceivedAction(onRxIrq);
    radio->startReceive();
    ESP_LOGI(TAG, "Listening...");
    blink(2, 200);

    uint32_t lastPktMs = (uint32_t)(esp_timer_get_time() / 1000ULL);

    while (true) {
        if (rxFlag) {
            rxFlag = false;
            int16_t len = radio->getPacketLength();
            if (len <= 0) {
                radio->standby();
                radio->startReceive();
                continue;
            }

            uint8_t buf[256];
            int16_t state = radio->readData(buf, len);
            lastPktMs = (uint32_t)(esp_timer_get_time() / 1000ULL);

            uint8_t mType = 0, mId = 0;
            AutoTest mTest = {};
            uint32_t mTxSent = 0;
            if (parse_marker(buf, len, &mType, &mId, &mTest, &mTxSent)) {
                if (mType == MARKER_TYPE_START) {
                    if (inTest) {
                        ESP_LOGW(TAG, "Got START while in test, saving partial");
                    }
                    currentTest = mTest;
                    currentTestId = mId;
                    rxReceived = 0;
                    rxCrcErrors = 0;
                    rxTotalSent = 0;
                    rssiSum = 0;
                    rssiCount = 0;
                    rssiMin = 32767;
                    rssiMax = -32768;
                    rxBitErrors = 0;
                    rxBitsChecked = 0;
                    rxPayloadCorrupt = 0;
                    testStartMs = lastPktMs;
                    inTest = true;

                    radio->standby();
                    state = initRadioForTest(&currentTest);
                    if (state != RADIOLIB_ERR_NONE) {
                        ESP_LOGE(TAG, "Failed to reconfigure for test %d", mId);
                        inTest = false;
                    } else {
                        radio->setPacketReceivedAction(onRxIrq);
                        radio->startReceive();
                        ESP_LOGI(TAG, ">>> Test %d: %s (mode=%d freq=%.1f br=%d pwr=%d size=%d count=%d)",
                                 mId, currentTest.name, currentTest.mode, currentTest.freq,
                                 currentTest.bitrate, currentTest.power, currentTest.pkt_size, currentTest.pkt_count);
                    }
                    continue;
                }

                if (mType == MARKER_TYPE_END && inTest) {
                    rxTotalSent = mTxSent;
                    uint32_t elapsed = lastPktMs - testStartMs;
                    uint32_t lost = (rxTotalSent > rxReceived) ? rxTotalSent - rxReceived : 0;
                    float perPct = rxTotalSent > 0 ? (lost * 100.0f) / rxTotalSent : 0;
                    float berPct = rxBitsChecked > 0 ? (rxBitErrors * 100.0f) / rxBitsChecked : 0;
                    float avgRssi = rssiCount > 0 ? (float)rssiSum / rssiCount : 0;
                    float tput = (elapsed > 0 && rxReceived > 0) ? (rxReceived * currentTest.pkt_size * 8.0f) / elapsed : 0;

                    ESP_LOGI(TAG, "<<< Test %d DONE: recv=%lu/%lu PER=%.1f%% BER=%.6f%% RSSI=%.0f tput=%.1fkbps",
                             currentTestId,
                             (unsigned long)rxReceived, (unsigned long)rxTotalSent,
                             perPct, berPct, avgRssi, tput);

                    if (resultCount < NVS_MAX_RESULTS) {
                        NvsTestResult r = {};
                        snprintf(r.name, sizeof(r.name), "test_%u", currentTestId);
                        r.mode = currentTest.mode;
                        r.freq = currentTest.freq;
                        r.bitrate = currentTest.bitrate;
                        r.sf = currentTest.sf;
                        r.cr = currentTest.cr;
                        r.power = currentTest.power;
                        r.pkt_size = currentTest.pkt_size;
                        r.tx_sent = (uint16_t)rxTotalSent;
                        r.rx_received = (uint16_t)rxReceived;
                        r.crc_errors = (uint16_t)rxCrcErrors;
                        r.lost = (uint16_t)lost;
                        r.per_pct = perPct;
                        r.ber_pct = berPct;
                        r.avg_rssi = (int16_t)avgRssi;
                        r.min_rssi = rssiMin == 32767 ? 0 : rssiMin;
                        r.max_rssi = rssiMax == -32768 ? 0 : rssiMax;
                        r.elapsed_ms = elapsed;
                        r.throughput_kbps = tput;
                        r.payload_corrupt = (uint16_t)rxPayloadCorrupt;
                        r.bit_errors = (uint16_t)rxBitErrors;
                        r.bits_checked = rxBitsChecked;
                        nvs_save_result(resultCount, &r);
                        resultCount++;
                        nvs_set_count(resultCount);
                    }

                    inTest = false;

                    radio->standby();
                    radio->beginFLRC(868.0f, 2600, RADIOLIB_LR2021_FLRC_CR_3_4, 22, 16, RADIOLIB_SHAPING_0_5, 0.0f);
                    radio->setPacketReceivedAction(onRxIrq);
                    radio->startReceive();

                    blink(2, 200);
                    continue;
                }
            }

            if (state != RADIOLIB_ERR_NONE) {
                if (inTest) rxCrcErrors++;
                radio->standby();
                radio->startReceive();
                continue;
            }

            if (inTest && len >= 4) {
                rxReceived++;
                float rssi = radio->getRSSI(false);
                int16_t rssi_i = (int16_t)rssi;
                rssiSum += rssi_i;
                rssiCount++;
                if (rssi_i < rssiMin) rssiMin = rssi_i;
                if (rssi_i > rssiMax) rssiMax = rssi_i;

                uint32_t seq = ((uint32_t)buf[0] << 24) | ((uint32_t)buf[1] << 16) |
                               ((uint32_t)buf[2] << 8) | (uint32_t)buf[3];
                if ((size_t)len > 4 && currentTest.pkt_size > 4) {
                    uint16_t bytesBad = 0;
                    uint16_t bitErr = prbs15_verify(buf + 4, len - 4, seq, &bytesBad);
                    if (bitErr > 0) {
                        rxPayloadCorrupt++;
                        rxBitErrors += bitErr;
                    }
                    rxBitsChecked += (len - 4) * 8;
                }

                if (rxReceived % 25 == 0) {
                    ESP_LOGI(TAG, "  RX %lu: RSSI=%.0f seq=%lu", (unsigned long)rxReceived, rssi, (unsigned long)seq);
                }
            }

            radio->standby();
            radio->startReceive();
        }

        if (inTest) {
            uint32_t now = (uint32_t)(esp_timer_get_time() / 1000ULL);
            if (now - lastPktMs > 30000) {
                ESP_LOGW(TAG, "Test %d timeout (30s no pkts)", currentTestId);
                inTest = false;
                radio->standby();
                radio->beginFLRC(868.0f, 2600, RADIOLIB_LR2021_FLRC_CR_3_4, 22, 16, RADIOLIB_SHAPING_0_5, 0.0f);
                radio->setPacketReceivedAction(onRxIrq);
                radio->startReceive();
            }
        }

        vTaskDelay(pdMS_TO_TICKS(1));
    }
}

#endif

static char cmdBuf[64];
static uint16_t cmdIdx = 0;

static void stdin_task(void *arg) {
    while (true) {
        int c = fgetc(stdin);
        if (c != EOF) {
            if (c == '\n' || c == '\r') {
                if (cmdIdx > 0) {
                    cmdBuf[cmdIdx] = '\0';
                    if (strcmp(cmdBuf, "RESULTS") == 0) {
                        nvs_print_all_results();
                    } else if (strcmp(cmdBuf, "CLEAR") == 0) {
                        nvs_clear_all();
                        printf("Results cleared\n");
                    }
                    cmdIdx = 0;
                }
            } else if (cmdIdx < sizeof(cmdBuf) - 1) {
                cmdBuf[cmdIdx++] = (char)c;
            }
        } else {
            vTaskDelay(pdMS_TO_TICKS(10));
        }
    }
}

extern "C" void app_main() {
    ESP_LOGI(TAG, "=== LR2021 Autonomous Benchmarker v2.0 ===");
    esp_task_wdt_deinit();
    setvbuf(stdin, NULL, _IONBF, 0);
    setvbuf(stdout, NULL, _IONBF, 0);

    hal = new EspHalC3(LR2021_SCK, LR2021_MISO, LR2021_MOSI);
    hal->setCsPin(LR2021_NSS);
    hal->setBusyPin(LR2021_BUSY);
    mod = new Module(hal, LR2021_NSS, LR2021_DIO9, LR2021_RST, LR2021_BUSY);
    radio = new LR2021(mod);
    radio->irqDioNum = 9;

    xTaskCreate(stdin_task, "serial", 4096, NULL, 3, NULL);

#if AUTO_ROLE_TX
    runAutoTx();
    ESP_LOGI(TAG, "TX complete, entering deep sleep...");
    esp_deep_sleep_start();
#else
    runAutoRx();
#endif
}
