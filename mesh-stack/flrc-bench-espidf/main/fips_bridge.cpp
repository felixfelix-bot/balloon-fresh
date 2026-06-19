#include <sdkconfig.h>

#ifdef CONFIG_BENCH_MODE_FIPS_BRIDGE

#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "esp_rom_sys.h"
#include "driver/gpio.h"
#include "driver/usb_serial_jtag.h"
#include <RadioLib.h>
#include "EspHalC3.h"

static const char *TAG = "BRIDGE";

#define LED_GPIO 8
#define NSS_PIN 10
#define BUSY_PIN 4
#define LR2021_SCK   6
#define LR2021_MISO  2
#define LR2021_MOSI  7
#define LR2021_NSS   10
#define LR2021_BUSY  4
#define LR2021_RST   3
#define LR2021_DIO9  5

#define SLIP_END  0xC0
#define SLIP_ESC  0xDB
#define SLIP_ESC_END 0xDC
#define SLIP_ESC_ESC 0xDD
#define MAX_PKT 255

static EspHalC3 *hal = nullptr;
static Module *mod = nullptr;
static LR2021 *radio = nullptr;
static volatile bool irqFlag = false;
static TaskHandle_t radioRxTask = NULL;
static SemaphoreHandle_t spiMutex = NULL;

static void IRAM_ATTR onIrq(void) {
    irqFlag = true;
    if (radioRxTask) {
        BaseType_t woken = pdFALSE;
        vTaskNotifyGiveFromISR(radioRxTask, &woken);
        portYIELD_FROM_ISR(woken);
    }
}

static void rawWaitBusy() {
    while (gpio_get_level((gpio_num_t)BUSY_PIN) == 1) {}
}

static void spiWrite(const uint8_t *cmd, size_t cmdLen, const uint8_t *data, size_t dataLen) {
    rawWaitBusy();
    xSemaphoreTake(spiMutex, portMAX_DELAY);
    gpio_set_level((gpio_num_t)NSS_PIN, 0);
    hal->spiTransfer(const_cast<uint8_t*>(cmd), cmdLen, nullptr);
    if (dataLen > 0 && data)
        hal->spiTransfer(const_cast<uint8_t*>(data), dataLen, nullptr);
    gpio_set_level((gpio_num_t)NSS_PIN, 1);
    xSemaphoreGive(spiMutex);
}

static void spiRead(const uint8_t *cmd, size_t cmdLen, uint8_t *data, size_t dataLen) {
    rawWaitBusy();
    xSemaphoreTake(spiMutex, portMAX_DELAY);
    gpio_set_level((gpio_num_t)NSS_PIN, 0);
    hal->spiTransfer(const_cast<uint8_t*>(cmd), cmdLen, nullptr);
    hal->spiTransfer(nullptr, dataLen, data);
    gpio_set_level((gpio_num_t)NSS_PIN, 1);
    xSemaphoreGive(spiMutex);
}

static void radioTx(const uint8_t *data, size_t len) {
    uint8_t pad[MAX_PKT];
    memset(pad, 0, sizeof(pad));
    memcpy(pad, data, len > MAX_PKT ? MAX_PKT : len);
    uint8_t writeCmd[] = {0x00, 0x02};
    spiWrite(writeCmd, 2, pad, MAX_PKT);
    uint8_t txCmd[] = {0x02, 0x0D, 0x00, 0x00, 0x00, 0x00};
    spiWrite(txCmd, 6, nullptr, 0);
    esp_rom_delay_us(900);
    uint8_t clrCmd[] = {0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF};
    spiWrite(clrCmd, 6, nullptr, 0);
}

static uint16_t radioRx(uint8_t *buf, size_t maxLen) {
    uint8_t lenCmd[] = {0x02, 0x12};
    uint8_t lenResp[2] = {0, 0};
    spiRead(lenCmd, 2, lenResp, 2);
    uint16_t pktLen = (lenResp[0] << 8) | lenResp[1];
    if (pktLen == 0 || pktLen > maxLen) pktLen = maxLen;
    uint8_t readCmd[] = {0x00, 0x01};
    spiRead(readCmd, 2, buf, pktLen);
    uint8_t clrCmd[] = {0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF};
    spiWrite(clrCmd, 6, nullptr, 0);
    return pktLen;
}

static int slipEncode(const uint8_t *in, size_t inLen, uint8_t *out, size_t outMax) {
    int oi = 0;
    if (oi >= (int)outMax) return -1;
    out[oi++] = SLIP_END;
    for (size_t i = 0; i < inLen; i++) {
        if (in[i] == SLIP_END) {
            if (oi + 1 >= (int)outMax) return -1;
            out[oi++] = SLIP_ESC;
            out[oi++] = SLIP_ESC_END;
        } else if (in[i] == SLIP_ESC) {
            if (oi + 1 >= (int)outMax) return -1;
            out[oi++] = SLIP_ESC;
            out[oi++] = SLIP_ESC_ESC;
        } else {
            if (oi >= (int)outMax) return -1;
            out[oi++] = in[i];
        }
    }
    if (oi >= (int)outMax) return -1;
    out[oi++] = SLIP_END;
    return oi;
}

static void uartToRadioTask(void *arg) {
    uint8_t rxBuf[64];
    uint8_t frame[MAX_PKT * 2];
    int frameLen = 0;
    bool inEsc = false;

    while (true) {
        int n = usb_serial_jtag_read_bytes(rxBuf, sizeof(rxBuf), pdMS_TO_TICKS(100));
        if (n <= 0) continue;

        for (int i = 0; i < n; i++) {
            uint8_t b = rxBuf[i];

            if (b == SLIP_END) {
                if (frameLen > 0) {
                    int pktLen = frameLen;
                    if (pktLen > MAX_PKT) pktLen = MAX_PKT;
                    radioTx(frame, pktLen);
                    frameLen = 0;
                }
                inEsc = false;
            } else if (inEsc) {
                if (b == SLIP_ESC_END) {
                    if (frameLen < (int)sizeof(frame)) frame[frameLen++] = SLIP_END;
                } else if (b == SLIP_ESC_ESC) {
                    if (frameLen < (int)sizeof(frame)) frame[frameLen++] = SLIP_ESC;
                }
                inEsc = false;
            } else if (b == SLIP_ESC) {
                inEsc = true;
            } else {
                if (frameLen < (int)sizeof(frame)) frame[frameLen++] = b;
            }
        }
    }
}

extern "C" void app_main() {
    esp_log_level_set("*", ESP_LOG_INFO);

    gpio_config_t io = {};
    io.pin_bit_mask = (1ULL << LED_GPIO) | (1ULL << NSS_PIN);
    io.mode = GPIO_MODE_OUTPUT;
    gpio_config(&io);
    gpio_set_level((gpio_num_t)LED_GPIO, 1);
    gpio_set_level((gpio_num_t)NSS_PIN, 1);

    spiMutex = xSemaphoreCreateMutex();

    vTaskDelay(pdMS_TO_TICKS(2000));

    usb_serial_jtag_driver_config_t usbCfg = {
        .tx_buffer_size = 1024,
        .rx_buffer_size = 1024,
    };
    usb_serial_jtag_driver_install(&usbCfg);

    hal = new EspHalC3(LR2021_SCK, LR2021_MISO, LR2021_MOSI);
    hal->setCsPin(LR2021_NSS);
    hal->setBusyPin(LR2021_BUSY);
    mod = new Module(hal, LR2021_NSS, LR2021_DIO9, LR2021_RST, LR2021_BUSY);
    radio = new LR2021(mod);
    radio->irqDioNum = 9;

    int16_t state = radio->beginFLRC(2450.0f, 2600, RADIOLIB_LR2021_FLRC_CR_1_0, 12,
                                     16, RADIOLIB_SHAPING_0_5, 0.0f);
    if (state != RADIOLIB_ERR_NONE) {
        while (true) {
            gpio_set_level((gpio_num_t)LED_GPIO, 0);
            vTaskDelay(pdMS_TO_TICKS(100));
            gpio_set_level((gpio_num_t)LED_GPIO, 1);
            vTaskDelay(pdMS_TO_TICKS(100));
        }
    }
    radio->fixedPacketLengthMode(255);
    radio->setPacketReceivedAction(onIrq);
    radio->startReceive();

    ESP_LOGI(TAG, "Bridge ready: 2.4 GHz FLRC 2600, +12 dBm, fixed 255B");

    radioRxTask = xTaskGetCurrentTaskHandle();
    vTaskPrioritySet(NULL, configMAX_PRIORITIES - 1);

    xTaskCreate(uartToRadioTask, "uart_rx", 4096, NULL, 5, NULL);

    vTaskDelay(pdMS_TO_TICKS(200));

    gpio_set_level((gpio_num_t)LED_GPIO, 0);
    vTaskDelay(pdMS_TO_TICKS(500));
    gpio_set_level((gpio_num_t)LED_GPIO, 1);

    uint8_t rxBuf[MAX_PKT];
    uint8_t slipBuf[MAX_PKT * 2 + 2];
    uint32_t rxCount = 0;

    while (true) {
        ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
        if (!irqFlag) continue;
        irqFlag = false;

        uint16_t pktLen = radioRx(rxBuf, MAX_PKT);
        rxCount++;

        if (rxCount <= 5 || (rxCount % 100) == 0) {
            ESP_LOGI(TAG, "RX pkt %lu: len=%u magic=%02X%02X plen=%u",
                     (unsigned long)rxCount, pktLen, rxBuf[0], rxBuf[1],
                     (rxBuf[11] | (rxBuf[12] << 8)));
        }

        int slipLen = slipEncode(rxBuf, pktLen, slipBuf, sizeof(slipBuf));
        if (slipLen > 0) {
            usb_serial_jtag_write_bytes(slipBuf, slipLen, pdMS_TO_TICKS(50));
        }
    }
}

#endif
