/*
 * flrc_range_tx_v5.cpp — Sweep TX using Rp2040Lr2021Radio adapter
 *
 * Replaces raw SPI calls with lr2021_transport API (via Rp2040Lr2021Radio).
 * Same sweep behavior as v4: 4 bitrates, 12-min cycle, GPS sync.
 * NeoPixel LED: countdown blinks on boot, on during TX, off during pause.
 *
 * Payload size configurable via -DPAYLOAD_SIZE=N build flag.
 *
 * Build: pio run -e rp2040-sweep-tx-v5-127B
 */

#include <Arduino.h>
#include "rp2040_lr2021_radio.h"
#include "gps_time.h"
#include "sweep_scheduler.h"

// ─── Payload size (configurable via build flags) ────────────────────
#ifndef PAYLOAD_SIZE
#define PAYLOAD_SIZE 127
#endif

// ─── GPS pins ───────────────────────────────────────────────────────
#ifndef GPS_RX_PIN
#define GPS_RX_PIN   1
#endif
#ifndef GPS_TX_PIN
#define GPS_TX_PIN   0
#endif
#ifndef GPS_PPS_PIN
#define GPS_PPS_PIN  9
#endif
#ifndef GPS_BAUD
#define GPS_BAUD     9600
#endif

// ─── TX config ──────────────────────────────────────────────────────
#ifndef TX_FREQ_MHZ
#define TX_FREQ_MHZ     2440.0f
#endif
#ifndef TX_POWER_DBM
#define TX_POWER_DBM    12
#endif
#define TX_PKT_COUNT    500
#define TX_PAUSE_MS     2000

// ─── Globals ────────────────────────────────────────────────────────
static Rp2040Lr2021Radio radio;
static SweepScheduler scheduler;
static GpsTimeModule gps;

static uint8_t tx_buf[255];
static uint16_t current_bitrate = 2600;
static uint32_t pkt_seq = 0;
static uint32_t burst_count = 0;

// ─── Setup ──────────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    delay(200);

    // Init GPS time sync
    gps.begin(GPS_RX_PIN, GPS_TX_PIN, GPS_PPS_PIN, GPS_BAUD);
    scheduler.begin(&gps);

    // Init radio
    Lr2021Config config;
    config.freq_mhz = TX_FREQ_MHZ;
    config.bitrate_kbps = 2600;
    config.tx_power_dbm = TX_POWER_DBM;
    config.payload_length = PAYLOAD_SIZE;

    auto err = radio.init(config);
    if (err != Lr2021Error::Ok) {
        Serial.println("RADIO_INIT_FAIL");
        radio.blink_led(10, 200); // fast blink = error
        while (true) { delay(1000); }
    }

    // Countdown — 3 blinks = time to walk away
    Serial.println("TX_STARTING_3S_COUNTDOWN");
    radio.blink_led(3, 500);

    // Fill TX buffer with known pattern
    for (int i = 0; i < PAYLOAD_SIZE; i++) {
        tx_buf[i] = (uint8_t)(i & 0xFF);
    }

    Serial.print("TX_READY BR=");
    Serial.print(current_bitrate);
    Serial.print(" PAYLOAD=");
    Serial.println(PAYLOAD_SIZE);
}

// ─── Main loop ──────────────────────────────────────────────────────
void loop() {
    // Update GPS time
    gps.update();

    // Check sweep scheduler for bitrate changes
    bool changed = scheduler.update();
    if (changed) {
        current_bitrate = scheduler.getCurrentBitrate();
        radio.switch_bitrate(current_bitrate);
        Serial.print("SWEEP_SWITCH BR=");
        Serial.print(current_bitrate);
        Serial.print(" IDX=");
        Serial.print(scheduler.getCurrentIndex());
        Serial.print(" CYCLE=");
        Serial.print(scheduler.getCurrentCycle());
        Serial.print(" TSRC=");
        Serial.println(gps.isLocked() ? "GPS" : "MILLIS");
    }

    // TX burst
    radio.set_led(true);
    uint32_t burst_start = millis();

    for (int i = 0; i < TX_PKT_COUNT; i++) {
        // Pack sequence number into first 4 bytes
        tx_buf[0] = (pkt_seq >> 24) & 0xFF;
        tx_buf[1] = (pkt_seq >> 16) & 0xFF;
        tx_buf[2] = (pkt_seq >> 8) & 0xFF;
        tx_buf[3] = pkt_seq & 0xFF;

        radio.send_packet(tx_buf, PAYLOAD_SIZE);
        pkt_seq++;
        delayMicroseconds(500); // small TX spacing
    }

    uint32_t burst_time = millis() - burst_start;
    radio.set_led(false);

    // Heartbeat
    burst_count++;
    Serial.print("TX_BURST N=");
    Serial.print(burst_count);
    Serial.print(" PKTS=");
    Serial.print(TX_PKT_COUNT);
    Serial.print(" TIME_MS=");
    Serial.print(burst_time);
    Serial.print(" BR=");
    Serial.print(current_bitrate);
    Serial.print(" PAYLOAD=");
    Serial.println(PAYLOAD_SIZE);

    delay(TX_PAUSE_MS);
}
