#include <sdkconfig.h>

#ifdef CONFIG_BENCH_MODE_FAST_RX

#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "driver/gpio.h"
#include "soc/rtc.h"
#include <RadioLib.h>
#include "EspHalC3.h"
#include "prbs.h"

static const char *TAG = "FASTRX";

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
static volatile bool irqFlag = false;
static TaskHandle_t rxTaskHandle = NULL;

static void IRAM_ATTR onIrq(void) {
    irqFlag = true;
    if (rxTaskHandle) {
        BaseType_t xHigherPriorityTaskWoken = pdFALSE;
        vTaskNotifyGiveFromISR(rxTaskHandle, &xHigherPriorityTaskWoken);
        portYIELD_FROM_ISR(xHigherPriorityTaskWoken);
    }
}

static void blink(int times, int on_ms, int off_ms) {
    gpio_config_t io = {};
    io.pin_bit_mask = (1ULL << LED_GPIO);
    io.mode = GPIO_MODE_OUTPUT;
    gpio_config(&io);
    for (int i = 0; i < times; i++) {
        gpio_set_level((gpio_num_t)LED_GPIO, 0);
        vTaskDelay(pdMS_TO_TICKS(on_ms));
        gpio_set_level((gpio_num_t)LED_GPIO, 1);
        vTaskDelay(pdMS_TO_TICKS(off_ms));
    }
    gpio_set_level((gpio_num_t)LED_GPIO, 1);
}

#define PKT_SIZE 255
#define PKT_COUNT 500
#define LISTEN_MS 12000

struct BandConfig {
    float freq;
    int8_t power;
    const char *name;
};

static const BandConfig bands[] = {
    {868.0f,  22, "868"},
};
static const int bandCount = sizeof(bands) / sizeof(bands[0]);

#define LR2021_NSS_PIN 10
#define LR2021_BUSY_PIN 4

static void rawWaitBusy() {
    while (gpio_get_level((gpio_num_t)LR2021_BUSY_PIN) == 1) {}
}

static void rawSpiWrite(const uint8_t *cmd, size_t cmdLen, const uint8_t *data, size_t dataLen) {
    rawWaitBusy();
    gpio_set_level((gpio_num_t)LR2021_NSS_PIN, 0);
    hal->spiTransfer(const_cast<uint8_t*>(cmd), cmdLen, nullptr);
    if (dataLen > 0 && data) {
        hal->spiTransfer(const_cast<uint8_t*>(data), dataLen, nullptr);
    }
    gpio_set_level((gpio_num_t)LR2021_NSS_PIN, 1);
}

static void rawSpiRead(const uint8_t *cmd, size_t cmdLen, uint8_t *data, size_t dataLen) {
    rawWaitBusy();
    gpio_set_level((gpio_num_t)LR2021_NSS_PIN, 0);
    hal->spiTransfer(const_cast<uint8_t*>(cmd), cmdLen, nullptr);
    hal->spiTransfer(nullptr, dataLen, data);
    gpio_set_level((gpio_num_t)LR2021_NSS_PIN, 1);
}

static void __attribute__((unused)) rawStandby() {
    uint8_t cmd[] = {0x01, 0x28, 0x00};
    rawSpiWrite(cmd, 3, nullptr, 0);
}

static void rawReadFifo(uint8_t *buf, size_t len) {
    uint8_t cmd[] = {0x00, 0x01};
    rawSpiRead(cmd, 2, buf, len);
}

static void rawClearIrq() {
    uint8_t cmd[] = {0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF};
    rawSpiWrite(cmd, 6, nullptr, 0);
}

static void rawSetRx() {
    uint8_t cmd[] = {0x02, 0x0C, 0x00, 0xFF, 0xFF, 0xFF};
    rawSpiWrite(cmd, 6, nullptr, 0);
}

static void initRadio(float freq, int8_t power) {
    radio->standby();
    int16_t state = radio->beginFLRC(freq, 2600, RADIOLIB_LR2021_FLRC_CR_1_0, power,
                                     16, RADIOLIB_SHAPING_0_5, 0.0f);
    if (state != RADIOLIB_ERR_NONE) {
        ESP_LOGE(TAG, "Radio init failed at %.0f MHz: %d", freq, state);
        return;
    }
    radio->fixedPacketLengthMode(255);
    radio->setPacketReceivedAction(onIrq);
    radio->startReceive();
    rxTaskHandle = xTaskGetCurrentTaskHandle();
    vTaskPrioritySet(NULL, configMAX_PRIORITIES - 1);
    irqFlag = false;
    ESP_LOGI(TAG, "Listening at %.0f MHz, +%d dBm (task notify, priority %d)",
             freq, power, configMAX_PRIORITIES - 1);
}

static void testBand(const BandConfig *bc, uint32_t loopNum) {
    uint8_t buf[PKT_SIZE + 4];
    uint32_t received = 0;
    uint32_t errors = 0;
    uint32_t duplicates = 0;
    uint32_t lastSeq = 0xFFFFFFFF;
    uint32_t uniquePkts = 0;

    initRadio(bc->freq, bc->power);

    uint32_t startMs = (uint32_t)(esp_timer_get_time() / 1000ULL);

    gpio_config_t csConf = {};
    csConf.pin_bit_mask = (1ULL << LR2021_NSS_PIN);
    csConf.mode = GPIO_MODE_OUTPUT;
    gpio_config(&csConf);
    gpio_set_level((gpio_num_t)LR2021_NSS_PIN, 1);

    while (received < PKT_COUNT &&
           (uint32_t)(esp_timer_get_time() / 1000ULL) - startMs < LISTEN_MS) {

        if (!irqFlag) {
            ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(100));
            continue;
        }
        irqFlag = false;

        uint32_t t0 = (uint32_t)esp_timer_get_time();

        rawReadFifo(buf, PKT_SIZE);
        rawClearIrq();

        uint32_t t1 = (uint32_t)esp_timer_get_time();

        uint32_t seq = ((uint32_t)buf[0] << 24) | ((uint32_t)buf[1] << 16) |
                       ((uint32_t)buf[2] << 8) | (uint32_t)buf[3];

        received++;

        if (seq == lastSeq) {
            duplicates++;
        } else {
            uniquePkts++;
        }
        lastSeq = seq;

        if (received <= 5) {
            ESP_LOGI(TAG, "  raw SPI pkt %lu: %lu us seq=%lu",
                     (unsigned long)received, (unsigned long)(t1 - t0),
                     (unsigned long)seq);
        }
    }

    uint32_t elapsed = (uint32_t)(esp_timer_get_time() / 1000ULL) - startMs;
    float tput = (elapsed > 0 && uniquePkts > 0)
        ? (float)uniquePkts * PKT_SIZE * 8.0f / elapsed : 0;
    float per = (PKT_COUNT - received) * 100.0f / PKT_COUNT;

    printf("%lu,%s,%d,%lu,%lu,%lu,%.1f,%.1u,%lu,%lu\n",
           (unsigned long)loopNum, bc->name, PKT_SIZE,
           (unsigned long)received, (unsigned long)errors,
           (unsigned long)elapsed, tput, 0,
           (unsigned long)duplicates, (unsigned long)uniquePkts);
    fflush(stdout);

    ESP_LOGI(TAG, "%s: recv=%lu dup=%lu unique=%lu/%d elapsed=%lums tput=%.1fkbps",
             bc->name, (unsigned long)received, (unsigned long)duplicates,
             (unsigned long)uniquePkts, PKT_COUNT,
             (unsigned long)elapsed, tput);
}

extern "C" void app_main() {
    ESP_LOGI(TAG, "=== Dual-Band RX (868 + 2450 MHz) ===");
    setvbuf(stdout, NULL, _IONBF, 0);
    blink(3, 200, 200);
    vTaskDelay(pdMS_TO_TICKS(5000));

    hal = new EspHalC3(LR2021_SCK, LR2021_MISO, LR2021_MOSI);
    hal->setCsPin(LR2021_NSS);
    hal->setBusyPin(LR2021_BUSY);
    mod = new Module(hal, LR2021_NSS, LR2021_DIO9, LR2021_RST, LR2021_BUSY);
    radio = new LR2021(mod);
    radio->irqDioNum = 9;

    printf("\n");
    printf("=================================================\n");
    printf("  Dual-Band RX (868 + 2450 MHz)\n");
    printf("  FLRC 2600 kbps, 255B fixed, no PRBS, taskYIELD\n");
    printf("  Alternates: 868 MHz (12s) -> 2450 MHz (12s)\n");
    printf("=================================================\n");
    printf("\n");
    printf("loop,band,pkt_size,rx_received,rx_errors,elapsed_ms,throughput_kbps,per_pct,duplicates,unique_pkts\n");
    fflush(stdout);

    uint32_t loopCount = 0;

    while (true) {
        loopCount++;
        ESP_LOGI(TAG, "====== Loop %lu ======", (unsigned long)loopCount);

        for (int bi = 0; bi < bandCount; bi++) {
            blink(bi + 1, 100, 100);
            vTaskDelay(pdMS_TO_TICKS(1000));
            testBand(&bands[bi], loopCount);
            vTaskDelay(pdMS_TO_TICKS(2000));
        }

        ESP_LOGI(TAG, "=== Loop %lu complete ===", (unsigned long)loopCount);
        blink(3, 200, 200);
        vTaskDelay(pdMS_TO_TICKS(3000));
    }
}

#endif
