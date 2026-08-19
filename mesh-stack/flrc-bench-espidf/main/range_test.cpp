#include <sdkconfig.h>

#if defined(CONFIG_BENCH_MODE_RANGE_TX) || defined(CONFIG_BENCH_MODE_RANGE_RX)

#ifndef FW_GIT_SHA
#define FW_GIT_SHA "unknown"
#endif

#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "esp_sleep.h"
#include "driver/gpio.h"
#include <RadioLib.h>
#include "EspHalC3.h"
#include "prbs.h"
#include "range_test.h"
#include "nvs_results.h"

#ifdef CONFIG_RANGE_TEST_GPS
#include "gps.h"
#endif

#if defined(CONFIG_BENCH_MODE_RANGE_TX)
#define RANGE_ROLE_TX 1
#elif defined(CONFIG_BENCH_MODE_RANGE_RX)
#define RANGE_ROLE_TX 0
#endif

static const char *TAG = "RANGE";

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

#if !RANGE_ROLE_TX
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

static int16_t initRadio(const RangeWindow *w) {
    int8_t pwr = w->power;
    if (w->freq > 1500.0f && pwr > 12) pwr = 12;
    if (w->mode == RANGE_FLRC) {
        return radio->beginFLRC(w->freq, w->bitrate, w->cr, pwr,
                                w->preamble, RADIOLIB_SHAPING_0_5, 0.0f);
    } else {
        return radio->begin(w->freq, w->bw, w->sf, w->cr,
                            RADIOLIB_LR2021_LORA_SYNC_WORD_PRIVATE,
                            pwr, w->preamble, 0.0f);
    }
}

static int16_t initRadioScan(const RangeScanMode *s) {
    int8_t pwr = s->power;
    if (s->freq > 1500.0f && pwr > 12) pwr = 12;
    if (s->mode == RANGE_FLRC) {
        return radio->beginFLRC(s->freq, s->bitrate, s->cr, pwr,
                                16, RADIOLIB_SHAPING_0_5, 0.0f);
    } else {
        return radio->begin(s->freq, s->bw, s->sf, s->cr,
                            RADIOLIB_LR2021_LORA_SYNC_WORD_PRIVATE,
                            pwr, 8, 0.0f);
    }
}

#if RANGE_ROLE_TX

static void runRangeTx() {
    ESP_LOGI(TAG, "=== Range Test TX ===");
    ESP_LOGI(TAG, "%d windows, looping forever", RANGE_WINDOW_COUNT);
    blink(3, 200);
    vTaskDelay(pdMS_TO_TICKS(10000));

    nvs_init();
    nvs_clear_all();

    uint32_t loopCount = 0;
    uint8_t resultCount = 0;
    uint32_t seqCounter = 0;  /* persistent sequence counter — never resets across windows or loops */

    while (true) {
        loopCount++;
        ESP_LOGI(TAG, "====== Loop %lu ======", (unsigned long)loopCount);
        blink(1, 500);

        for (int i = 0; i < RANGE_WINDOW_COUNT; i++) {
            const RangeWindow *w = &range_windows[i];
            ESP_LOGI(TAG, "--- Window %d/%d: %s ---", i + 1, RANGE_WINDOW_COUNT, w->name);
            blink(1, 100);

            int16_t state = initRadio(w);
            if (state != RADIOLIB_ERR_NONE) {
                ESP_LOGE(TAG, "Radio init failed: %d", state);
                continue;
            }

            uint8_t sync[RANGE_SYNC_PKT_LEN];
            for (int s = 0; s < RANGE_SYNC_COUNT; s++) {
                range_build_sync(sync, RANGE_TYPE_START, (uint8_t)i, w, 0);
                radio->transmit(sync, RANGE_SYNC_PKT_LEN);
                vTaskDelay(pdMS_TO_TICKS(w->sync_delay_ms));
            }

            ESP_LOGI(TAG, "Sending %d pkts, size=%d, delay=%dms (seq starts at %lu)",
                     w->pkt_count, w->pkt_size, w->tx_delay_ms, (unsigned long)seqCounter);

            uint8_t buf[255];
            uint16_t sent = 0;
            uint32_t startMs = (uint32_t)(esp_timer_get_time() / 1000ULL);

            for (uint32_t p = 0; p < w->pkt_count; p++, seqCounter++) {
                buf[0] = (seqCounter >> 24) & 0xFF;
                buf[1] = (seqCounter >> 16) & 0xFF;
                buf[2] = (seqCounter >> 8) & 0xFF;
                buf[3] = seqCounter & 0xFF;
                if (w->pkt_size > 4) {
                    prbs15_fill(buf + 4, w->pkt_size - 4, seqCounter);
                }
                state = radio->transmit(buf, w->pkt_size);
                if (state == RADIOLIB_ERR_NONE) sent++;
                if (w->tx_delay_ms > 0) {
                    vTaskDelay(pdMS_TO_TICKS(w->tx_delay_ms));
                }
            }

            uint32_t elapsed = (uint32_t)(esp_timer_get_time() / 1000ULL) - startMs;
            float tput = (sent > 0 && elapsed > 0) ? (sent * w->pkt_size * 8.0f) / elapsed : 0;
            ESP_LOGI(TAG, "%s: sent=%d/%d elapsed=%lums tput=%.1fkbps",
                     w->name, sent, w->pkt_count, (unsigned long)elapsed, tput);

            if (resultCount < NVS_MAX_RESULTS) {
                NvsTestResult r = {};
                snprintf(r.name, sizeof(r.name), "%s", w->name);
                r.mode = (w->mode == RANGE_FLRC) ? 0 : 1;
                r.freq = w->freq;
                r.bitrate = w->bitrate;
                r.sf = w->sf;
                r.cr = w->cr;
                r.power = w->power;
                r.pkt_size = w->pkt_size;
                r.tx_sent = sent;
                r.rx_received = 0;
                r.crc_errors = 0;
                r.lost = 0;
                r.per_pct = 0;
                r.ber_pct = 0;
                r.avg_rssi = 0;
                r.min_rssi = 0;
                r.max_rssi = 0;
                r.elapsed_ms = elapsed;
                r.throughput_kbps = tput;
                r.payload_corrupt = 0;
                r.bit_errors = 0;
                r.bits_checked = 0;
                r.role = 0;
                r.loop_count = loopCount;
                r.gps_fix = 0;
                r.gps_lat = 0;
                r.gps_lon = 0;
                r.gps_alt = 0;
                r.gps_sats = 0;
                r.gps_hdop = 0;
                nvs_save_result(resultCount, &r);
                resultCount++;
                nvs_set_count(resultCount);
            }

            range_build_sync(sync, RANGE_TYPE_END, (uint8_t)i, w, sent);
            for (int s = 0; s < RANGE_END_COUNT; s++) {
                radio->transmit(sync, RANGE_SYNC_PKT_LEN);
                vTaskDelay(pdMS_TO_TICKS(200));
            }

            vTaskDelay(pdMS_TO_TICKS(RANGE_GAP_MS));
        }

        ESP_LOGI(TAG, "=== Loop %lu complete, next loop in 5s ===", (unsigned long)loopCount);
        vTaskDelay(pdMS_TO_TICKS(5000));
    }
}

#else

static void gpsReadCached(gps_data_t *gd) {
#ifdef CONFIG_RANGE_TEST_GPS
    memset(gd, 0, sizeof(*gd));
    gps_read(gd);
#else
    memset(gd, 0, sizeof(*gd));
#endif
}

static void printGpsLog(const gps_data_t *gd) {
    if (gd->fix) {
        ESP_LOGI(TAG, "GPS: fix=%d lat=%.5f lon=%.5f alt=%dm sats=%d hdop=%.1f",
                 gd->fix, gd->latitude / 1e5, gd->longitude / 1e5,
                 gd->altitude_m, gd->sats, gd->hdop);
    } else {
        ESP_LOGI(TAG, "GPS: no fix");
    }
}

static void runRangeRx() {
    ESP_LOGI(TAG, "=== Range Test RX ===");
    ESP_LOGI(TAG, "%d windows, scanning for TX", RANGE_WINDOW_COUNT);

#ifdef CONFIG_RANGE_TEST_GPS
    gps_init();
    ESP_LOGI(TAG, "GPS initialized on UART1");
#else
    ESP_LOGI(TAG, "GPS disabled (compile flag)");
#endif

    nvs_init();
    nvs_clear_all();

    uint8_t resultCount = 0;
    uint32_t loopCount = 0;
    uint8_t scanIdx = 0;

    while (true) {
        bool inWindow = false;
        RangeWindow curWin = {};
        uint8_t curWinId = 0;
        uint32_t rxReceived = 0;
        uint32_t rxCrcErrors = 0;
        uint16_t rxTotalSent = 0;
        int32_t rssiSum = 0;
        uint32_t rssiCount = 0;
        int16_t rssiMin = 32767;
        int16_t rssiMax = -32768;
        uint32_t bitErrors = 0;
        uint32_t bitsChecked = 0;
        uint32_t payloadCorrupt = 0;
        uint32_t windowStartMs = 0;
        gps_data_t windowGps = {};

        const RangeScanMode *scan = &range_scan_modes[scanIdx % RANGE_SCAN_MODE_COUNT];
        scanIdx++;

        int16_t state = initRadioScan(scan);
        if (state != RADIOLIB_ERR_NONE) {
            ESP_LOGW(TAG, "Scan init failed mode=%d freq=%.0f: %d", scan->mode, scan->freq, state);
            vTaskDelay(pdMS_TO_TICKS(1000));
            continue;
        }

        radio->setPacketReceivedAction(onRxIrq);
        radio->startReceive();

        if (scan->mode == RANGE_FLRC) {
            ESP_LOGI(TAG, "Scanning: FLRC %.0fMHz BR%d CR%d", scan->freq, scan->bitrate, scan->cr);
        } else {
            ESP_LOGI(TAG, "Scanning: LoRa %.0fMHz SF%d BW%.0f CR%d", scan->freq, scan->sf, scan->bw, scan->cr);
        }

        uint32_t scanStart = (uint32_t)(esp_timer_get_time() / 1000ULL);
        uint32_t lastPktMs = scanStart;

        while (true) {
            uint32_t nowMs = (uint32_t)(esp_timer_get_time() / 1000ULL);

            if (!inWindow && (nowMs - scanStart) > RANGE_SCAN_TIMEOUT_MS) {
                radio->standby();
                break;
            }

            if (inWindow && (nowMs - lastPktMs) > RANGE_RX_TIMEOUT_MS) {
                ESP_LOGW(TAG, "Window %d timeout, no packets for %ds", curWinId, RANGE_RX_TIMEOUT_MS / 1000);
                inWindow = false;
                radio->standby();
                break;
            }

            if (!rxFlag) {
                vTaskDelay(pdMS_TO_TICKS(1));
                continue;
            }

            rxFlag = false;
            int16_t len = radio->getPacketLength();
            if (len <= 0) {
                radio->standby();
                radio->startReceive();
                continue;
            }

            uint8_t buf[256];
            state = radio->readData(buf, len);
            lastPktMs = (uint32_t)(esp_timer_get_time() / 1000ULL);

            uint8_t mType = 0;
            uint8_t mWinId = 0;
            RangeWindow mWin = {};
            uint16_t mTxSent = 0;

            if (range_parse_sync(buf, len, &mType, &mWinId, &mWin, &mTxSent)) {
                if (mType == RANGE_TYPE_START) {
                    if (inWindow) {
                        ESP_LOGW(TAG, "Got START while in window %d, saving partial", curWinId);
                    }
                    curWin = mWin;
                    curWinId = mWinId;
                    rxReceived = 0;
                    rxCrcErrors = 0;
                    rxTotalSent = 0;
                    rssiSum = 0;
                    rssiCount = 0;
                    rssiMin = 32767;
                    rssiMax = -32768;
                    bitErrors = 0;
                    bitsChecked = 0;
                    payloadCorrupt = 0;
                    windowStartMs = lastPktMs;
                    inWindow = true;

                    gpsReadCached(&windowGps);
                    printGpsLog(&windowGps);

                    radio->standby();
                    state = initRadio(&curWin);
                    if (state != RADIOLIB_ERR_NONE) {
                        ESP_LOGE(TAG, "Failed to init for window %d: %d", mWinId, state);
                        inWindow = false;
                    } else {
                        radio->setPacketReceivedAction(onRxIrq);
                        radio->startReceive();
                        const char *modeStr = curWin.mode == RANGE_FLRC ? "FLRC" : "LORA";
                        ESP_LOGI(TAG, ">>> Window %d: %s (%s %.1fMHz BR%d SF%d BW%.0f CR%d pwr=%d sz=%d cnt=%d)",
                                 mWinId, curWin.name, modeStr, curWin.freq, curWin.bitrate,
                                 curWin.sf, curWin.bw, curWin.cr, curWin.power,
                                 curWin.pkt_size, curWin.pkt_count);
                    }
                    continue;
                }

                if (mType == RANGE_TYPE_END && inWindow) {
                    rxTotalSent = mTxSent;
                    uint32_t elapsed = lastPktMs - windowStartMs;
                    uint32_t lost = (rxTotalSent > rxReceived) ? rxTotalSent - rxReceived : 0;
                    float perPct = rxTotalSent > 0 ? (lost * 100.0f) / rxTotalSent : 0;
                    float berPct = bitsChecked > 0 ? (bitErrors * 100.0f) / bitsChecked : 0;
                    float avgRssi = rssiCount > 0 ? (float)rssiSum / rssiCount : 0;
                    float tput = (elapsed > 0 && rxReceived > 0) ? (rxReceived * curWin.pkt_size * 8.0f) / elapsed : 0;

                    ESP_LOGI(TAG, "<<< Window %d DONE: recv=%lu/%lu PER=%.1f%% BER=%.6f%% RSSI=%.0f tput=%.1fkbps",
                             curWinId, (unsigned long)rxReceived, (unsigned long)rxTotalSent,
                             perPct, berPct, avgRssi, tput);

                    const char *modeStr = curWin.mode == RANGE_FLRC ? "FLRC" : "LORA";
                    printf("RESULT,%lu,%d,%s,%s,%.1f,%d,%d,%.0f,%d,%d,%d,%lu,%lu,%lu,%.1f,%.6f,%.0f,%d,%d,%lu,%.1f,%d,%d,%d,%d,%d,%.1f\n",
                           (unsigned long)loopCount, curWinId, curWin.name, modeStr,
                           curWin.freq, curWin.bitrate, curWin.sf, curWin.bw, curWin.cr, curWin.power,
                           curWin.pkt_size,
                           (unsigned long)rxTotalSent, (unsigned long)rxReceived, (unsigned long)rxCrcErrors,
                           perPct, berPct, avgRssi,
                           rssiMin == 32767 ? 0 : rssiMin, rssiMax == -32768 ? 0 : rssiMax,
                           (unsigned long)elapsed, tput,
                           windowGps.fix, (int)windowGps.latitude, (int)windowGps.longitude,
                           windowGps.altitude_m, windowGps.sats, windowGps.hdop);
                    fflush(stdout);

                    if (resultCount < NVS_MAX_RESULTS) {
                        NvsTestResult r = {};
                        snprintf(r.name, sizeof(r.name), "%s", curWin.name);
                        r.mode = (curWin.mode == RANGE_FLRC) ? 0 : 1;
                        r.freq = curWin.freq;
                        r.bitrate = curWin.bitrate;
                        r.sf = curWin.sf;
                        r.cr = curWin.cr;
                        r.power = curWin.power;
                        r.pkt_size = curWin.pkt_size;
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
                        r.payload_corrupt = (uint16_t)payloadCorrupt;
                        r.bit_errors = (uint16_t)bitErrors;
                        r.bits_checked = bitsChecked;
                        r.role = 1;
                        r.loop_count = loopCount;
                        r.gps_fix = windowGps.fix ? 1 : 0;
                        r.gps_lat = windowGps.latitude;
                        r.gps_lon = windowGps.longitude;
                        r.gps_alt = windowGps.altitude_m;
                        r.gps_sats = windowGps.sats;
                        r.gps_hdop = windowGps.hdop;
                        nvs_save_result(resultCount, &r);
                        resultCount++;
                        nvs_set_count(resultCount);
                    }

                    inWindow = false;
                    blink(3, 100);
                    break;
                }
                continue;
            }

            if (state != RADIOLIB_ERR_NONE) {
                /* C3-4/M7: Log CRC-failed packets with RSSI instead of just counting */
                if (inWindow) {
                    rxCrcErrors++;
                    float crc_rssi = radio->getRSSI(false);
                    int16_t crc_rssi_i = (int16_t)crc_rssi;
                    rssiSum += crc_rssi_i;
                    rssiCount++;
                    if (crc_rssi_i < rssiMin) rssiMin = crc_rssi_i;
                    if (crc_rssi_i > rssiMax) rssiMax = crc_rssi_i;

                    uint32_t ts_ms = (uint32_t)(esp_timer_get_time() / 1000ULL);
                    uint32_t freq_hz = (uint32_t)(curWin.freq * 1000000.0f);
                    uint32_t bw_khz = (uint32_t)curWin.bw;
                    const char *modStr = (curWin.mode == RANGE_FLRC) ? "FLRC" : "LORA";
                    /* seq=0 because CRC failure means buffer contents may be corrupt */
                    printf("PKT,%s,%s,%u,0,%lu,%d,0,0,0,0,%lu,%s,%u,%u,%u,%d,%u,%d,%d,%d,%d,%d,%.1f\r\n",
                           session_id, config_id, (unsigned)replicate_num,
                           (unsigned long)ts_ms, crc_rssi_i,
                           (unsigned long)freq_hz, modStr,
                           (unsigned)curWin.sf, bw_khz, (unsigned)curWin.cr,
                           (int)curWin.power, (unsigned)curWin.pkt_size,
                           0, 0, 0, 0, 0, 0.0f);
                    fflush(stdout);
                }
                radio->standby();
                radio->startReceive();
                continue;
            }

            if (inWindow && len >= 4) {
                rxReceived++;
                float rssi = radio->getRSSI(false);
                int16_t rssi_i = (int16_t)rssi;
                rssiSum += rssi_i;
                rssiCount++;
                if (rssi_i < rssiMin) rssiMin = rssi_i;
                if (rssi_i > rssiMax) rssiMax = rssi_i;

                blink(1, 20);

                gps_data_t pktGps = {};
                gpsReadCached(&pktGps);

                const char *modeStr = curWin.mode == RANGE_FLRC ? "FLRC" : "LORA";
                uint32_t seq = ((uint32_t)buf[0] << 24) | ((uint32_t)buf[1] << 16) |
                               ((uint32_t)buf[2] << 8) | (uint32_t)buf[3];
                uint32_t ts_ms = (uint32_t)(esp_timer_get_time() / 1000ULL);
                int16_t snr_db = 0;
                if (curWin.mode == RANGE_LORA) {
                    snr_db = (int16_t)radio->getSNR();
                }
                int crc_ok = 1; /* already past the CRC-error handler above */
                uint32_t freq_hz = (uint32_t)(curWin.freq * 1000000.0f);
                uint32_t bw_khz = (uint32_t)curWin.bw; /* already in kHz */
                uint16_t bitErr = 0;
                uint16_t bytesBad = 0;
                if ((size_t)len > 4 && curWin.pkt_size > 4) {
                    bitErr = prbs15_verify(buf + 4, len - 4, seq, &bytesBad);
                    bitErrors += bitErr;
                    bitsChecked += (len - 4) * 8;
                    if (bytesBad > 0) payloadCorrupt++;
                }
                printf("PKT,%s,%s,%hu,%lu,%u,%d,%d,%d,%u,%u,%u,%s,%u,%u,%u,%d,%u,%d,%d,%d,%d,%d,%.1f\r\n",
                       session_id,           // 1. session_id
                       config_id,            // 2. config_id
                       replicate_num,        // 3. replicate
                       (unsigned long)seq,    // 4. seq
                       ts_ms,                // 5. ts_ms
                       rssi_i,               // 6. rssi_dbm
                       (int)snr_db,          // 7. snr_db
                       crc_ok,               // 8. crc_ok
                       (unsigned)bitErr,      // 9. bit_err
                       (unsigned)bytesBad,    // 10. bytes_bad
                       freq_hz,              // 11. freq_hz
                       modeStr,              // 12. mod ("LORA"/"FLRC")
                       (unsigned)curWin.sf,   // 13. sf (0 for FLRC)
                       bw_khz,              // 14. bw_khz
                       (unsigned)curWin.cr,   // 15. cr
                       (int)curWin.power,     // 16. power_dbm
                       (unsigned)curWin.pkt_size, // 17. pkt_size
                       (int)pktGps.fix,      // 18. gps_fix
                       (int)pktGps.latitude,  // 19. gps_lat
                       (int)pktGps.longitude, // 20. gps_lon
                       (int)pktGps.altitude_m, // 21. gps_alt
                       (int)pktGps.sats,      // 22. gps_sats
                       pktGps.hdop);          // 23. gps_hdop
                fflush(stdout);
            }

            radio->standby();
            radio->startReceive();
        }
    }
}

/* --- Serial command handler for SESSION/CONFIG (harmonized 23-field PKT) --- */
#define CMD_BUF_SIZE 128
static char rxCmdBuf[CMD_BUF_SIZE];
static uint16_t rxCmdIdx = 0;

static void processRangeCommand(char *cmd) {
    /* SESSION <id> — set session identifier for PKT lines */
    if (strncmp(cmd, "SESSION ", 8) == 0) {
        strncpy(session_id, cmd + 8, sizeof(session_id) - 1);
        session_id[sizeof(session_id) - 1] = '\0';
        printf("OK SESSION SET\r\n");
        fflush(stdout);
        return;
    }
    /* CONFIG <id> <replicate> — set config id + replicate number, emit CONFIG_START */
    if (strncmp(cmd, "CONFIG ", 7) == 0) {
        char cid[32] = "";
        unsigned repl = 0;
        if (sscanf(cmd + 7, "%31s %u", cid, &repl) >= 1) {
            strncpy(config_id, cid, sizeof(config_id) - 1);
            config_id[sizeof(config_id) - 1] = '\0';
            replicate_num = (uint16_t)repl;
            printf("OK CONFIG SET\r\n");
            printf("CONFIG_START,%s,%u,%u\r\n", config_id, (unsigned)replicate_num,
                   (unsigned)(esp_timer_get_time() / 1000));
            fflush(stdout);
        } else {
            printf("ERR CONFIG SYNTAX\r\n");
            fflush(stdout);
        }
        return;
    }
}

static void stdin_read_task(void *arg) {
    while (true) {
        int c = fgetc(stdin);
        if (c != EOF) {
            if (c == '\n' || c == '\r') {
                if (rxCmdIdx > 0) {
                    rxCmdBuf[rxCmdIdx] = '\0';
                    processRangeCommand(rxCmdBuf);
                    rxCmdIdx = 0;
                }
            } else if (rxCmdIdx < CMD_BUF_SIZE - 1) {
                rxCmdBuf[rxCmdIdx++] = (char)c;
            }
        } else {
            vTaskDelay(pdMS_TO_TICKS(10));
        }
    }
}

#endif

extern "C" void app_main() {
    ESP_LOGI(TAG, "=== LR2021 Range Test v1.0 FW_HASH=%s ===", FW_GIT_SHA);
    setvbuf(stdin, NULL, _IONBF, 0);
    setvbuf(stdout, NULL, _IONBF, 0);

    hal = new EspHalC3(LR2021_SCK, LR2021_MISO, LR2021_MOSI);
    hal->setCsPin(LR2021_NSS);
    hal->setBusyPin(LR2021_BUSY);
    mod = new Module(hal, LR2021_NSS, LR2021_DIO9, LR2021_RST, LR2021_BUSY);
    radio = new LR2021(mod);
    radio->irqDioNum = 9;

    /* Start serial command handler for SESSION/CONFIG commands */
    xTaskCreate(stdin_read_task, "cmd", 4096, NULL, 5, NULL);

#if RANGE_ROLE_TX
    runRangeTx();
#else
    runRangeRx();
#endif
}

#endif
