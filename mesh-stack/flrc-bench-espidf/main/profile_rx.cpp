#include <sdkconfig.h>

#ifdef CONFIG_BENCH_MODE_PROFILE

#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "driver/gpio.h"
#include <RadioLib.h>
#include "EspHalC3.h"

static const char *TAG = "PROFILE";

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

static void IRAM_ATTR onRxIrq(void) { rxFlag = true; }

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

extern "C" void app_main() {
    ESP_LOGI(TAG, "=== RX Pipeline Profiler ===");
    setvbuf(stdout, NULL, _IONBF, 0);
    blink(3, 200);
    vTaskDelay(pdMS_TO_TICKS(2000));

    hal = new EspHalC3(LR2021_SCK, LR2021_MISO, LR2021_MOSI);
    hal->setCsPin(LR2021_NSS);
    hal->setBusyPin(LR2021_BUSY);
    mod = new Module(hal, LR2021_NSS, LR2021_DIO9, LR2021_RST, LR2021_BUSY);
    radio = new LR2021(mod);
    radio->irqDioNum = 9;

    ESP_LOGI(TAG, "Initializing radio: FLRC 2450 MHz, 2600 kbps, +12 dBm");
    int16_t state = radio->beginFLRC(2450.0f, 2600, 0x02, 12,
                                     16, RADIOLIB_SHAPING_0_5, 0.0f);
    if (state != RADIOLIB_ERR_NONE) {
        ESP_LOGE(TAG, "Radio init failed: %d", state);
        blink(10, 500);
        return;
    }

    radio->setPacketReceivedAction(onRxIrq);
    radio->startReceive();

    printf("\n");
    printf("=============================================\n");
    printf("  RX Pipeline Profiler\n");
    printf("  Mode: FLRC 2600 kbps @ 2450 MHz\n");
    printf("  Measuring per-packet processing time\n");
    printf("  Run TX board simultaneously\n");
    printf("=============================================\n");
    printf("\n");
    printf("pkt,irq_to_read_us,readData_us,getRSSI_us,standby_us,startRx_us,total_us\n");
    fflush(stdout);

    int pktCount = 0;
    uint64_t irqLatencySum = 0;
    uint64_t readDataSum = 0;
    uint64_t getRssiSum = 0;
    uint64_t standbySum = 0;
    uint64_t startRxSum = 0;
    uint64_t totalSum = 0;

    int irqLatencyMax = 0, readDataMax = 0, standbyMax = 0, startRxMax = 0, totalMax = 0;
    int irqLatencyMin = 999999, readDataMin = 999999, standbyMin = 999999, startRxMin = 999999, totalMin = 999999;

    uint32_t profileStart = (uint32_t)(esp_timer_get_time() / 1000ULL);

    while (pktCount < 200) {
        if (!rxFlag) {
            vTaskDelay(pdMS_TO_TICKS(1));
            continue;
        }

        uint32_t irqTime = (uint32_t)esp_timer_get_time();
        rxFlag = false;

        int16_t len = radio->getPacketLength();
        if (len <= 0) {
            radio->standby();
            radio->startReceive();
            continue;
        }

        uint8_t buf[256];

        uint32_t t0 = (uint32_t)esp_timer_get_time();
        state = radio->readData(buf, len);
        uint32_t t1 = (uint32_t)esp_timer_get_time();

        float rssi = radio->getRSSI(false);
        uint32_t t2 = (uint32_t)esp_timer_get_time();

        radio->standby();
        uint32_t t3 = (uint32_t)esp_timer_get_time();

        radio->startReceive();
        uint32_t t4 = (uint32_t)esp_timer_get_time();

        uint32_t irqLatency = t0 - irqTime;
        uint32_t readDataUs = t1 - t0;
        uint32_t getRssiUs = t2 - t1;
        uint32_t standbyUs = t3 - t2;
        uint32_t startRxUs = t4 - t3;
        uint32_t totalUs = t4 - irqTime;

        printf("%d,%u,%u,%u,%u,%u,%u\n",
               pktCount, irqLatency, readDataUs, getRssiUs, standbyUs, startRxUs, totalUs);
        fflush(stdout);

        irqLatencySum += irqLatency;
        readDataSum += readDataUs;
        getRssiSum += getRssiUs;
        standbySum += standbyUs;
        startRxSum += startRxUs;
        totalSum += totalUs;

        if (irqLatency > irqLatencyMax) irqLatencyMax = irqLatency;
        if (readDataUs > readDataMax) readDataMax = readDataUs;
        if (standbyUs > standbyMax) standbyMax = standbyUs;
        if (startRxUs > startRxMax) startRxMax = startRxUs;
        if (totalUs > totalMax) totalMax = totalUs;

        if (irqLatency < irqLatencyMin) irqLatencyMin = irqLatency;
        if (readDataUs < readDataMin) readDataMin = readDataUs;
        if (standbyUs < standbyMin) standbyMin = standbyUs;
        if (startRxUs < startRxMin) startRxMin = startRxUs;
        if (totalUs < totalMin) totalMin = totalUs;

        pktCount++;

        if (pktCount % 50 == 0) {
            ESP_LOGI(TAG, "Processed %d/200 packets...", pktCount);
        }
    }

    uint32_t elapsed = (uint32_t)(esp_timer_get_time() / 1000ULL) - profileStart;

    printf("\n");
    printf("=============================================\n");
    printf("  PROFILE SUMMARY (%d packets, %lu ms total)\n", pktCount, (unsigned long)elapsed);
    printf("=============================================\n");
    printf("\n");
    printf("Phase            Avg(us)    Min(us)    Max(us)    %% of total\n");
    printf("─────────────────────────────────────────────────────────────\n");
    printf("IRQ latency      %5lu     %5d      %5d       %4.1f%%\n",
           (unsigned long)(irqLatencySum / pktCount), irqLatencyMin, irqLatencyMax,
           100.0f * irqLatencySum / totalSum);
    printf("readData(SPI)    %5lu     %5d      %5d       %4.1f%%\n",
           (unsigned long)(readDataSum / pktCount), readDataMin, readDataMax,
           100.0f * readDataSum / totalSum);
    printf("getRSSI          %5lu     %5lu      %5d       %4.1f%%\n",
           (unsigned long)(getRssiSum / pktCount), 0, 0,
           100.0f * getRssiSum / totalSum);
    printf("standby(SPI)     %5lu     %5d      %5d       %4.1f%%\n",
           (unsigned long)(standbySum / pktCount), standbyMin, standbyMax,
           100.0f * standbySum / totalSum);
    printf("startReceive     %5lu     %5d      %5d       %4.1f%%\n",
           (unsigned long)(startRxSum / pktCount), startRxMin, startRxMax,
           100.0f * startRxSum / totalSum);
    printf("─────────────────────────────────────────────────────────────\n");
    printf("TOTAL            %5lu     %5d      %5d\n",
           (unsigned long)(totalSum / pktCount), totalMin, totalMax);
    printf("\n");
    printf("Theoretical max RX throughput:\n");
    float avgTotalMs = (float)totalSum / pktCount / 1000.0f;
    float maxPktPerSec = 1000.0f / avgTotalMs;
    float maxThroughput = maxPktPerSec * 200 * 8 / 1000.0f;
    printf("  Avg processing: %.2f ms/packet\n", avgTotalMs);
    printf("  Max packet rate: %.0f pkt/s\n", maxPktPerSec);
    printf("  Max throughput (200B): %.1f kbps\n", maxThroughput);
    printf("\n");
    printf("If readData dominates → SPI bus is bottleneck\n");
    printf("If standby+startRx dominate → SPI round-trip count is bottleneck\n");
    printf("If IRQ latency dominates → radio processing is bottleneck\n");
    printf("If all are small but total is large → CPU/RTOS overhead\n");
    printf("=============================================\n");
    fflush(stdout);

    blink(5, 200);
    while (true) {
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}

#endif
