/*
 * app_main.cpp — Pico Balloon Tracker firmware
 *
 * Radio driver: lr2021_transport (raw 2-byte SPI, per ADR-020)
 * RadioLib has been completely removed. All radio operations go through
 * EspHalLr2021Radio (Lr2021Radio interface) and optionally Lr2021Transport
 * for FIPS stream communication.
 */

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
#include "driver/i2c.h"
#include "soc/rtc.h"

#include "esp_idf_lr2021_radio.h"
#include "lr2021_transport.h"

#ifdef CONFIG_ENABLE_MESHCORE
#include <Mesh.h>
#include <StaticPoolPacketManager.h>
#include <SimpleMeshTables.h>
#include <EspIdfInterfaces.h>

class BalloonMesh : public mesh::Mesh {
public:
    BalloonMesh(mesh::Radio& radio, mesh::MillisecondClock& ms, mesh::RNG& rng,
                mesh::RTCClock& rtc, mesh::PacketManager& mgr, mesh::MeshTables& tables)
        : Mesh(radio, ms, rng, rtc, mgr, tables) {}
};
#endif

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
#ifdef CONFIG_ENABLE_MESH
#include "mesh_adapter.h"
#include "pipeline.h"
#endif
#ifdef CONFIG_ENABLE_TDMA
#include "tdma.h"
#endif
#ifdef CONFIG_ENABLE_NOSTR_STORE
#include "nostr_store.h"
#endif
}

static const char *TAG = "TRACKER";

#define LED_GPIO 18  /* moved from GPIO10 (was colliding with LR2021 NSS) */

/* LR2021 pin reference (matching lr2021_spi.h defaults / EspHalLr2021Radio) */
#define LR2021_SCK   6
#define LR2021_MISO  2
#define LR2021_MOSI  7
#define LR2021_NSS   10
#define LR2021_BUSY  4
#define LR2021_RST   3
#define LR2021_DIO9  5

/* Radio handles — lr2021_transport based (replaces RadioLib) */
static EspHalLr2021Radio* s_radio = nullptr;
static Lr2021Transport*   s_transport = nullptr;

#ifdef CONFIG_ENABLE_BMP280
static bmp280_t bmp;
#endif

#ifdef CONFIG_ENABLE_GPS
static gps_data_t gps_data;
#endif

static RTC_DATA_ATTR uint16_t rtc_seq = 0;
static RTC_DATA_ATTR bool rtc_first_boot = true;

#ifdef CONFIG_ENABLE_MESH
static mesh_frame_queue_t s_mesh_tx_queue;
static int s_mesh_pending = 0;
#endif

/* ── Radio helpers (polling-based, replaces RadioLib ISR callbacks) ── */

/**
 * Wait for TX_DONE IRQ with timeout.
 * Polls the LR2021 IRQ status register until TX_DONE is set or timeout.
 * @return true if TX completed within timeout, false on timeout.
 */
static bool wait_tx_done(uint32_t timeout_ms)
{
    if (!s_radio) return false;
    uint32_t flags = 0;
    for (uint32_t elapsed = 0; elapsed < timeout_ms; elapsed++) {
        if (s_radio->get_irq_status(flags) == Lr2021Error::Ok &&
            (flags & IrqSource::TX_DONE)) {
            s_radio->clear_irq();
            return true;
        }
        vTaskDelay(pdMS_TO_TICKS(1));
    }
    s_radio->clear_irq();
    return false;
}

#ifdef CONFIG_ENABLE_MESH
static void mesh_radio_send(const uint8_t *frame, uint16_t len)
{
    if (!s_radio) return;
    s_radio->standby();
    s_radio->send_packet(frame, len);
    wait_tx_done(10000);
}
#endif

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

/**
 * Initialize the LR2021 radio using lr2021_transport (FLRC mode).
 * Replaces the old RadioLib-based init_radio().
 */
static int init_radio(void)
{
    s_radio = new EspHalLr2021Radio();

    ESP_LOGI(TAG, "Initializing LR2021 (FLRC, lr2021_transport)...");
    printf("GPIO states: BUSY(%d)=%d RST(%d)=%d NSS(%d)=%d\n",
        LR2021_BUSY, (int)gpio_get_level((gpio_num_t)LR2021_BUSY),
        LR2021_RST, (int)gpio_get_level((gpio_num_t)LR2021_RST),
        LR2021_NSS, (int)gpio_get_level((gpio_num_t)LR2021_NSS));
    fflush(stdout);

    /* FLRC configuration (proven baseline from ADR-020) */
    Lr2021Config config;
    config.freq_mhz      = 2440.0f;   /* 2.4 GHz ISM */
    config.bitrate_kbps  = 2600;       /* FLRC max bitrate */
    config.tx_power_dbm  = CONFIG_RADIO_TX_POWER_DBM;
    config.payload_length = LR2021_MAX_PACKET;

    if (s_radio->init(config) != Lr2021Error::Ok) {
        ESP_LOGE(TAG, "LR2021 init failed");
        return -1;
    }

    /* Create FIPS transport (stream send/recv over FLRC packets) */
    s_transport = new Lr2021Transport(s_radio);
    TransportError terr = s_transport->init(config);
    if (terr != TransportError::Ok) {
        ESP_LOGE(TAG, "LR2021 transport init failed");
        return -1;
    }

    ESP_LOGI(TAG, "LR2021 OK (FLRC 2440 MHz, 2600 kbps, %d dBm)",
             CONFIG_RADIO_TX_POWER_DBM);
    return 0;
}

static void deep_sleep(uint32_t seconds)
{
    ESP_LOGI(TAG, "Deep sleep %ds...", (int)seconds);
#ifdef CONFIG_ENABLE_BMP280
    bmp280_sleep(&bmp);
#endif
    if (s_radio) {
        s_radio->sleep();
    }
#ifdef CONFIG_ENABLE_FEM
    sky66112_shutdown();
#endif
    gpio_set_level((gpio_num_t)LED_GPIO, 0);

    esp_sleep_enable_timer_wakeup((uint64_t)seconds * 1000000);
    ESP_LOGI(TAG, "(deep sleep disabled for debug)");
    while (true) {
        cli_process();
        vTaskDelay(pdMS_TO_TICKS(100));
    }
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
    printf("  Frequency: FLRC 2440 MHz (2.4 GHz ISM)\n");
    printf("  Bitrate: 2600 kbps\n");
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
    printf("  Mode: FLRC 2440 MHz, 2600 kbps\n");
    printf("  TX power: %d dBm\n", CONFIG_RADIO_TX_POWER_DBM);
    printf("  Driver: lr2021_transport (ADR-020)\n");
    printf("  Transport: %s\n", s_transport ? "ready" : "not init");
    printf("  Initialized: %s\n", s_radio ? "yes" : "no");
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

static void cli_cmd_radio_test(const char *args) {
    (void)args;
    if (!s_radio) {
        printf("Radio not initialized\n");
        return;
    }
    telemetry_packet_t pkt;
    memset(&pkt, 0, sizeof(pkt));
    pkt.callsign_hash = (uint32_t)strtoul(CONFIG_CALLSIGN_HASH_HEX, NULL, 16);
    telemetry_fill(&pkt, 0, 0, 0, power_manager_read_supercap_mv(), rtc_seq);
    uint8_t buf[TELEMETRY_SIZE];
    telemetry_serialize(&pkt, buf);

    printf("TX test packet (%d bytes)... ", TELEMETRY_SIZE);
    fflush(stdout);
    s_radio->standby();
    s_radio->send_packet(buf, TELEMETRY_SIZE);
    printf("%s\n", wait_tx_done(10000) ? "OK" : "TIMEOUT");
}

static void cli_cmd_radio_recv(const char *args) {
    (void)args;
    if (!s_radio) {
        printf("Radio not initialized\n");
        return;
    }
    printf("Listening for 30s...\n");
    s_radio->start_rx();
    s_radio->clear_irq();

    uint32_t start = xTaskGetTickCount() * portTICK_PERIOD_MS;
    while ((xTaskGetTickCount() * portTICK_PERIOD_MS - start) < 30000) {
        bool irq = false;
        s_radio->check_irq(irq);
        if (irq) {
            uint8_t rx_buf[256];
            PacketStatus status;
            if (s_radio->read_packet(rx_buf, sizeof(rx_buf), status) == Lr2021Error::Ok
                && status.length > 0) {
                int len = (int)status.length;
                printf("RX %d bytes, RSSI: %d dBm, SNR: %d dB\n  HEX: ",
                       len, (int)status.rssi_dbm, (int)status.snr_db);
                for (int i = 0; i < len && i < 64; i++) printf("%02x", rx_buf[i]);
                printf("\n");
                if (len == TELEMETRY_SIZE) {
                    telemetry_packet_t *rpkt = (telemetry_packet_t *)rx_buf;
                    if (telemetry_validate(rx_buf, TELEMETRY_SIZE)) {
                        printf("  Valid telemetry! seq=%d voltage=%dmV\n",
                               rpkt->seq, rpkt->voltage_mv);
                    }
                }
            }
            s_radio->clear_irq();
            s_radio->start_rx();
        }
        vTaskDelay(pdMS_TO_TICKS(10));
    }
    s_radio->standby();
    printf("Listen done\n");
}

static void cli_cmd_i2c_scan(const char *args) {
    (void)args;
    printf("Scanning I2C bus (SDA=8, SCL=9)...\n");
    uint8_t found = 0;
    for (uint8_t addr = 1; addr < 127; addr++) {
        i2c_cmd_handle_t cmd = i2c_cmd_link_create();
        i2c_master_start(cmd);
        i2c_master_write_byte(cmd, (addr << 1) | I2C_MASTER_WRITE, true);
        i2c_master_stop(cmd);
        esp_err_t ret = i2c_master_cmd_begin(I2C_NUM_0, cmd, pdMS_TO_TICKS(50));
        i2c_cmd_link_delete(cmd);
        if (ret == ESP_OK) {
            printf("  Found device at 0x%02x\n", addr);
            found++;
        }
    }
    printf("Scan complete: %d device(s) found\n", found);
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
    cli_register_command("radio_test", "Transmit test packet", cli_cmd_radio_test);
    cli_register_command("radio_recv", "Listen for FLRC packets (30s)", cli_cmd_radio_recv);
    cli_register_command("i2c_scan", "Scan I2C bus for devices", cli_cmd_i2c_scan);
}

extern "C" void app_main(void)
{
    vTaskDelay(pdMS_TO_TICKS(2000));

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
    esp_err_t pm_ret = esp_pm_configure(&pm_config);
    if (pm_ret != ESP_OK) {
        ESP_LOGW(TAG, "PM configure failed (%s), power saving disabled", esp_err_to_name(pm_ret));
    }

    power_manager_init();
    uint16_t cap_mv = power_manager_read_supercap_mv();
    ESP_LOGI(TAG, "Supercap: %d mV", cap_mv);

    setup_cli();
    printf("> ");
    fflush(stdout);

    if (init_radio() != 0) {
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

#ifdef CONFIG_BENCH_TEST_MODE
    ESP_LOGI(TAG, "=== BENCH TEST MODE (TX every %ds) ===", CONFIG_BENCH_TEST_INTERVAL_SEC);
    while (true) {
#endif

    cap_mv = power_manager_read_supercap_mv();

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

#ifdef CONFIG_ENABLE_FEM
    sky66112_tx_enable();
#endif

#ifdef CONFIG_ENABLE_MESHCORE
    ESP_LOGI(TAG, "Starting MeshCore mesh...");

    static mesh::EspIdfClock meshClock;
    static mesh::EspIdfRNG meshRNG;
    static mesh::EspIdfBoard meshBoard;
    static mesh::EspIdfRTC meshRTC;
    static mesh::Lr2021MeshRadio meshRadio(*s_radio, meshBoard);
    static StaticPoolPacketManager meshPktMgr(8);
    static SimpleMeshTables meshTables;

    static mesh::LocalIdentity meshIdentity(&meshRNG);

    static BalloonMesh mesh(meshRadio, meshClock, meshRNG, meshRTC, meshPktMgr, meshTables);
    mesh.begin();
    ESP_LOGI(TAG, "MeshCore started, running loop...");

    while (true) {
        mesh.loop();
        cli_process();
        vTaskDelay(pdMS_TO_TICKS(1));
    }
#else

#ifdef CONFIG_ENABLE_MESH
    mesh_adapter_config_t mesh_cfg = {
        .send_fn = mesh_radio_send,
        .tx_queue = &s_mesh_tx_queue,
    };
    mesh_adapter_init(&mesh_cfg);

    mesh_result_t mr = mesh_adapter_send(buf, TELEMETRY_SIZE, 50, 4);
    if (mr != MESH_OK) {
        ESP_LOGE(TAG, "mesh_adapter_send failed: %d", mr);
    } else {
        s_mesh_pending = mesh_adapter_get_pending_frame_count();
        ESP_LOGI(TAG, "Mesh: %d frames sent", s_mesh_pending);
    }
#else
    s_radio->standby();
    s_radio->send_packet(buf, TELEMETRY_SIZE);
    bool tx_ok = wait_tx_done(10000);
    ESP_LOGI(TAG, "%s", tx_ok ? "TX complete" : "TX timeout");
#endif

#ifdef CONFIG_ENABLE_FEM
    sky66112_shutdown();
#endif

#ifdef CONFIG_BENCH_TEST_MODE
    s_radio->sleep();
    rtc_seq++;
    ESP_LOGI(TAG, "Waiting %ds until next TX...", CONFIG_BENCH_TEST_INTERVAL_SEC);
    for (int i = 0; i < CONFIG_BENCH_TEST_INTERVAL_SEC * 100; i++) {
        cli_process();
        vTaskDelay(pdMS_TO_TICKS(10));
    }
    s_radio->standby();
    } // end bench test while loop
#else
    s_radio->sleep();
    rtc_seq++;
    deep_sleep(CONFIG_TX_INTERVAL_SEC);
#endif // CONFIG_BENCH_TEST_MODE

#endif // CONFIG_ENABLE_MESHCORE
}
