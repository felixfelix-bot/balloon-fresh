#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_pm.h"
#include "esp_sleep.h"
#include "driver/gpio.h"
#include "driver/rtc_io.h"
#include "soc/rtc.h"

#include <RadioLib.h>
#include "EspHalC3.h"

extern "C" {
#include "telemetry.h"
#ifdef CONFIG_ENABLE_BMP280
#include "bmp280.h"
#endif
#ifdef CONFIG_ENABLE_GPS
#include "gps.h"
#endif
#include "power_manager.h"
#ifdef CONFIG_ENABLE_FEM
#include "sky66112.h"
#endif
#ifdef CONFIG_ENABLE_ANTENNA_SWITCH
#include "antenna_switch.h"
#endif
#include "cli.h"
}

static const char *TAG = "TRACKER";

#define LED_GPIO 10

#define LR2021_SCK   6
#define LR2021_MISO  2
#define LR2021_MOSI  7
#define LR2021_NSS   10
#define LR2021_BUSY  4
#define LR2021_RST   3
#define LR2021_DIO9  5

static EspHalC3* hal = nullptr;
static LR2021* radio = nullptr;

#ifdef CONFIG_ENABLE_BMP280
static bmp280_t bmp;
#endif

#ifdef CONFIG_ENABLE_GPS
static gps_data_t gps_data;
#endif

static RTC_DATA_ATTR uint16_t rtc_seq = 0;
static RTC_DATA_ATTR bool rtc_first_boot = true;

static bool flag_tx_done = false;

static void IRAM_ATTR on_tx_done(void) {
    flag_tx_done = true;
}

static void blink_led(int times)
{
    gpio_config_t io_conf = {
        .pin_bit_mask = (1ULL << LED_GPIO),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&io_conf);

    for (int i = 0; i < times; i++) {
        gpio_set_level((gpio_num_t)LED_GPIO, 1);
        vTaskDelay(pdMS_TO_TICKS(100));
        gpio_set_level((gpio_num_t)LED_GPIO, 0);
        vTaskDelay(pdMS_TO_TICKS(100));
    }
}

static int16_t init_radio(void)
{
    hal = new EspHalC3(LR2021_SCK, LR2021_MISO, LR2021_MOSI);
    radio = new LR2021(new Module(hal, LR2021_NSS, LR2021_DIO9, LR2021_RST, LR2021_BUSY));
    radio->irqDioNum = 9;

    ESP_LOGI(TAG, "Initializing LR2021...");
    float freq_mhz = (float)CONFIG_RADIO_FREQ_MHZ_X10 / 10.0f;
    int16_t state = radio->begin(
        freq_mhz, 125.0,
        CONFIG_RADIO_SF, 7,
        0x12, CONFIG_RADIO_TX_POWER_DBM, 8
    );
    if (state != RADIOLIB_ERR_NONE) {
        ESP_LOGE(TAG, "LR2021 init failed: %d", state);
        return state;
    }

    radio->setPacketSentAction(on_tx_done);
    ESP_LOGI(TAG, "LR2021 OK (868 MHz, SF%d, %d dBm)", CONFIG_RADIO_SF, CONFIG_RADIO_TX_POWER_DBM);
    return RADIOLIB_ERR_NONE;
}

static void deep_sleep(uint32_t seconds)
{
    ESP_LOGI(TAG, "Deep sleep %ds...", (int)seconds);
#ifdef CONFIG_ENABLE_BMP280
    bmp280_sleep(&bmp);
#endif
    if (radio) {
        radio->sleep();
    }
#ifdef CONFIG_ENABLE_FEM
    sky66112_shutdown();
#endif
    gpio_set_level((gpio_num_t)LED_GPIO, 0);

    esp_sleep_enable_timer_wakeup((uint64_t)seconds * 1000000);
    esp_deep_sleep_start();
}

static void cli_cmd_status(const char *args) {
    (void)args;
    printf("=== System Status ===\n");
    printf("  Uptime: %lld ms\n", esp_timer_get_time() / 1000);
    printf("  Free heap: %lu bytes\n", (unsigned long)esp_get_free_heap_size());
    printf("  Wake count: %d\n", rtc_seq);
    printf("  First boot: %s\n", rtc_first_boot ? "yes" : "no");
    uint16_t cap_mv = power_manager_read_supercap_mv();
    printf("  Supercap: %d mV\n", cap_mv);
}

static void cli_cmd_gps(const char *args) {
    (void)args;
#ifdef CONFIG_ENABLE_GPS
    printf("=== GPS Data ===\n");
    printf("  Fix: %s\n", gps_data.fix ? "YES" : "NO");
    if (gps_data.fix) {
        printf("  Lat: %.5f deg\n", gps_data.latitude / 1e5);
        printf("  Lon: %.5f deg\n", gps_data.longitude / 1e5);
        printf("  Alt: %d m\n", gps_data.altitude_m);
        printf("  Sats: %d\n", gps_data.sats);
        printf("  HDOP: %d\n", gps_data.hdop);
    }
#else
    printf("GPS: disabled in config\n");
#endif
}

static void cli_cmd_telemetry(const char *args) {
    (void)args;
    telemetry_packet_t pkt;
    memset(&pkt, 0, sizeof(pkt));
    pkt.callsign_hash = (uint32_t)strtoul(CONFIG_CALLSIGN_HASH_HEX, NULL, 16);
    uint16_t cap_mv = power_manager_read_supercap_mv();
    telemetry_fill(&pkt, 0, 0, 0, cap_mv, rtc_seq);

    uint8_t buf[TELEMETRY_SIZE];
    telemetry_serialize(&pkt, buf);

    printf("=== Telemetry Packet (%d bytes) ===\n", TELEMETRY_SIZE);
    printf("  HEX: ");
    for (int i = 0; i < TELEMETRY_SIZE; i++) printf("%02x", buf[i]);
    printf("\n");
    printf("  Callsign hash: 0x%08lx\n", (unsigned long)pkt.callsign_hash);
    printf("  Seq: %d\n", pkt.seq);
    printf("  Supercap: %d mV\n", cap_mv);
}

static void cli_cmd_config(const char *args) {
    (void)args;
    printf("=== Configuration ===\n");
    printf("  Callsign hash: %s\n", CONFIG_CALLSIGN_HASH_HEX);
    printf("  Frequency: %.1f MHz\n", (float)CONFIG_RADIO_FREQ_MHZ_X10 / 10.0f);
    printf("  SF: %d\n", CONFIG_RADIO_SF);
    printf("  TX power: %d dBm\n", CONFIG_RADIO_TX_POWER_DBM);
    printf("  TX interval: %d s\n", CONFIG_TX_INTERVAL_SEC);
    printf("  Low voltage: %d mV\n", CONFIG_LOW_VOLTAGE_MV);
#ifdef CONFIG_ENABLE_GPS
    printf("  GPS: enabled\n");
#else
    printf("  GPS: disabled\n");
#endif
#ifdef CONFIG_ENABLE_BMP280
    printf("  BMP280: enabled\n");
#else
    printf("  BMP280: disabled\n");
#endif
}

static void cli_cmd_radio(const char *args) {
    (void)args;
    printf("=== Radio State ===\n");
    printf("  Freq: %.1f MHz\n", (float)CONFIG_RADIO_FREQ_MHZ_X10 / 10.0f);
    printf("  SF: %d, BW: 125 kHz, CR: 4/7\n", CONFIG_RADIO_SF);
    printf("  TX power: %d dBm\n", CONFIG_RADIO_TX_POWER_DBM);
    printf("  Initialized: %s\n", radio ? "yes" : "no");
}

static void cli_cmd_restart(const char *args) {
    (void)args;
    printf("Restarting...\n");
    esp_restart();
}

static void cli_cmd_sleep_now(const char *args) {
    (void)args;
    printf("Forcing deep sleep...\n");
    deep_sleep(CONFIG_TX_INTERVAL_SEC);
}

static void setup_cli(void) {
    cli_init();
    cli_register_command("status", "System status (uptime, heap, voltage)", cli_cmd_status);
    cli_register_command("gps", "GPS data (fix, lat, lon, alt, sats)", cli_cmd_gps);
    cli_register_command("telemetry", "Current telemetry packet", cli_cmd_telemetry);
    cli_register_command("config", "Kconfig settings", cli_cmd_config);
    cli_register_command("radio", "Radio configuration", cli_cmd_radio);
    cli_register_command("restart", "Software restart", cli_cmd_restart);
    cli_register_command("sleep", "Force deep sleep cycle", cli_cmd_sleep_now);
}

extern "C" void app_main(void)
{
    if (rtc_first_boot) {
        ESP_LOGI(TAG, "=== Pico Balloon Tracker v0.2 ===");
#ifdef CONFIG_ENABLE_BMP280
        ESP_LOGI(TAG, "  BMP280: enabled");
#else
        ESP_LOGI(TAG, "  BMP280: disabled");
#endif
#ifdef CONFIG_ENABLE_GPS
        ESP_LOGI(TAG, "  GPS: enabled");
#else
        ESP_LOGI(TAG, "  GPS: disabled");
#endif
#ifdef CONFIG_ENABLE_FEM
        ESP_LOGI(TAG, "  FEM: enabled");
#else
        ESP_LOGI(TAG, "  FEM: disabled");
#endif
#ifdef CONFIG_ENABLE_ANTENNA_SWITCH
        ESP_LOGI(TAG, "  SP4T: enabled");
#else
        ESP_LOGI(TAG, "  SP4T: disabled");
#endif
        rtc_first_boot = false;
        blink_led(3);
    } else {
        ESP_LOGI(TAG, "Wakeup from deep sleep (cycle %d)", rtc_seq);
    }

    esp_pm_config_t pm_config = {
        .max_freq_mhz = 80,
        .min_freq_mhz = 10,
        .light_sleep_enable = true,
    };
    ESP_ERROR_CHECK(esp_pm_configure(&pm_config));

    power_manager_init();
    uint16_t cap_mv = power_manager_read_supercap_mv();
    ESP_LOGI(TAG, "Supercap: %d mV", cap_mv);

    setup_cli();
    printf("> ");
    fflush(stdout);

    if (cap_mv < CONFIG_LOW_VOLTAGE_MV) {
        ESP_LOGW(TAG, "Low voltage (%d mV < %d), skipping TX", cap_mv, CONFIG_LOW_VOLTAGE_MV);
        deep_sleep(CONFIG_TX_INTERVAL_SEC);
        return;
    }

    if (init_radio() != RADIOLIB_ERR_NONE) {
        ESP_LOGE(TAG, "Radio init failed, sleeping");
        deep_sleep(CONFIG_TX_INTERVAL_SEC);
        return;
    }

#ifdef CONFIG_ENABLE_FEM
    sky66112_init(CONFIG_FEM_TX_PIN, CONFIG_FEM_RX_PIN);
    sky66112_tx_enable();
    ESP_LOGI(TAG, "FEM TX enabled");
#endif

#ifdef CONFIG_ENABLE_ANTENNA_SWITCH
    antenna_switch_init(CONFIG_ANTENNA_SWITCH_CTRL1_PIN, CONFIG_ANTENNA_SWITCH_CTRL2_PIN);
    antenna_switch_select(0);
#endif

#ifdef CONFIG_ENABLE_BMP280
    memset(&bmp, 0, sizeof(bmp));
    esp_err_t bmp_ret = bmp280_init(&bmp, I2C_NUM_0, 8, 9, 400000);
    if (bmp_ret != ESP_OK) {
        ESP_LOGW(TAG, "BMP280 not found, continuing without sensor");
    }
#endif

#ifdef CONFIG_ENABLE_GPS
    gps_init();
    ESP_LOGI(TAG, "Waiting for GPS fix...");
    uint32_t gps_start = xTaskGetTickCount() * portTICK_PERIOD_MS;
    bool gps_fixed = false;
    while ((xTaskGetTickCount() * portTICK_PERIOD_MS - gps_start) < 60000) {
        if (gps_read(&gps_data) && gps_data.fix) {
            gps_fixed = true;
            ESP_LOGI(TAG, "GPS: %.5f, %.5f, %dm, %d sats",
                gps_data.latitude / 1e5, gps_data.longitude / 1e5,
                gps_data.altitude_m, gps_data.sats);
            break;
        }
        cli_process();
        vTaskDelay(pdMS_TO_TICKS(500));
    }
    if (!gps_fixed) {
        ESP_LOGW(TAG, "No GPS fix after 60s, TX without position");
    }
    gps_sleep();
#endif

    float temp = 0, pressure = 0, altitude = 0;
#ifdef CONFIG_ENABLE_BMP280
    bmp280_wakeup(&bmp);
    vTaskDelay(pdMS_TO_TICKS(100));
    bmp280_read(&bmp, &temp, &pressure, &altitude);
    bmp280_sleep(&bmp);
    ESP_LOGI(TAG, "BMP280: %.1f C, %.1f hPa, %.0f m", temp, pressure, altitude);
#endif

    telemetry_packet_t pkt;
    memset(&pkt, 0, sizeof(pkt));
    pkt.callsign_hash = (uint32_t)strtoul(CONFIG_CALLSIGN_HASH_HEX, NULL, 16);

#ifdef CONFIG_ENABLE_GPS
    if (gps_data.fix) {
        pkt.latitude_deg1e5 = (uint32_t)(gps_data.latitude);
        pkt.longitude_deg1e5 = (int32_t)(gps_data.longitude);
        pkt.altitude_m = (uint16_t)gps_data.altitude_m;
        pkt.sats = gps_data.sats;
        pkt.flags |= TELEMETRY_FLAG_GPS_VALID;
    }
#endif

#ifdef CONFIG_ENABLE_BMP280
    if (altitude > 0) {
#ifdef CONFIG_ENABLE_GPS
        if (!gps_data.fix)
#endif
            pkt.altitude_m = (uint16_t)altitude;
    }
#endif

    pkt.flags |= (cap_mv < CONFIG_LOW_VOLTAGE_MV + 200) ? TELEMETRY_FLAG_LOW_POWER : 0;

    telemetry_fill(&pkt, temp, pressure, (float)pkt.altitude_m, cap_mv, rtc_seq);

    uint8_t buf[TELEMETRY_SIZE];
    telemetry_serialize(&pkt, buf);

    ESP_LOGI(TAG, "TX %d bytes (seq %d)...", TELEMETRY_SIZE, rtc_seq);
    flag_tx_done = false;

#ifdef CONFIG_ENABLE_FEM
    sky66112_tx_enable();
#endif

    int16_t state = radio->startTransmit(buf, TELEMETRY_SIZE);
    if (state != RADIOLIB_ERR_NONE) {
        ESP_LOGE(TAG, "startTransmit failed: %d", state);
    } else {
        uint32_t timeout = 0;
        while (!flag_tx_done && timeout < 10000) {
            hal->delay(1);
            timeout++;
        }
        ESP_LOGI(TAG, "%s", flag_tx_done ? "TX complete" : "TX timeout");
    }

#ifdef CONFIG_ENABLE_FEM
    sky66112_shutdown();
#endif

    radio->sleep();
    rtc_seq++;
    deep_sleep(CONFIG_TX_INTERVAL_SEC);
}
