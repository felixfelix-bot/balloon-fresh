/*
 * flrc_range_rx_v5.cpp — Sweep RX using Rp2040Lr2021Radio adapter
 *
 * Replaces raw SPI calls with lr2021_transport API (via Rp2040Lr2021Radio).
 * Same sweep behavior as v4: auto-syncs bitrate to TX, logs RSSI+PER.
 * NeoPixel LED: solid on = RX armed, blink = packet received.
 *
 * Output format (serial):
 *   PKT seq=N rssi=-XX per=XX.X br=XXXX payload=XXX
 *   SWEEP_SWITCH BR=XXXX IDX=X CYCLE=X TSRC=GPS|MILLIS
 *   HEARTBEAT rx=N unique=N per=XX.X noise=-XX br=XXXX
 *
 * Payload size configurable via -DPAYLOAD_SIZE=N build flag.
 *
 * Build: pio run -e rp2040-sweep-rx-v5-127B
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

// ─── RX config ──────────────────────────────────────────────────────
#ifndef RX_FREQ_MHZ
#define RX_FREQ_MHZ     2440.0f
#endif

// ─── Globals ────────────────────────────────────────────────────────
static Rp2040Lr2021Radio radio;
static SweepScheduler scheduler;
static GpsTimeModule gps;

static uint8_t rx_buf[255];
static uint16_t current_bitrate = 2600;

// Stats
static uint32_t total_rx = 0;
static uint32_t unique_rx = 0;
static uint32_t last_seq = 0;
static uint32_t lost_pkts = 0;
static int16_t noise_floor = -127;

// ─── Setup ──────────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    delay(200);

    // Init GPS time sync
    gps.begin(GPS_RX_PIN, GPS_TX_PIN, GPS_PPS_PIN, GPS_BAUD);
    scheduler.begin(&gps);

    // Init radio
    Lr2021Config config;
    config.freq_mhz = RX_FREQ_MHZ;
    config.bitrate_kbps = 2600;
    config.payload_length = PAYLOAD_SIZE;

    auto err = radio.init(config);
    if (err != Lr2021Error::Ok) {
        Serial.println("RADIO_INIT_FAIL");
        while (true) {
            radio.blink_led(1, 200);
            delay(1000);
        }
    }

    // Measure noise floor
    noise_floor = radio.get_rssi_instant();
    Serial.print("NOISE_FLOOR=");
    Serial.println(noise_floor);

    // Start RX
    radio.start_rx();
    radio.set_led(true); // solid = armed

    Serial.print("RX_READY BR=");
    Serial.print(current_bitrate);
    Serial.print(" PAYLOAD=");
    Serial.print(PAYLOAD_SIZE);
    Serial.print(" NOISE=");
    Serial.println(noise_floor);
}

// ─── Main loop ──────────────────────────────────────────────────────
void loop() {
    gps.update();

    // Check sweep scheduler
    bool changed = scheduler.update();
    if (changed) {
        current_bitrate = scheduler.getCurrentBitrate();
        radio.switch_bitrate(current_bitrate);
        radio.start_rx(); // re-arm RX after bitrate switch

        Serial.print("SWEEP_SWITCH BR=");
        Serial.print(current_bitrate);
        Serial.print(" IDX=");
        Serial.print(scheduler.getCurrentIndex());
        Serial.print(" CYCLE=");
        Serial.print(scheduler.getCurrentCycle());
        Serial.print(" TSRC=");
        Serial.println(gps.isLocked() ? "GPS" : "MILLIS");

        // Remasure noise floor after switch
        noise_floor = radio.get_rssi_instant();
    }

    // Poll for packet
    bool irq_asserted = false;
    radio.check_irq(irq_asserted);

    if (irq_asserted) {
        uint32_t irq_flags = 0;
        radio.get_irq_status(irq_flags);

        if (IrqSource::contains(irq_flags, IrqSource::RX_DONE)) {
            PacketStatus status;
            auto err = radio.read_packet(rx_buf, sizeof(rx_buf), status);

            if (err == Lr2021Error::Ok && status.length > 0) {
                total_rx++;

                // Extract sequence number
                uint32_t seq = ((uint32_t)rx_buf[0] << 24) |
                               ((uint32_t)rx_buf[1] << 16) |
                               ((uint32_t)rx_buf[2] << 8) |
                               rx_buf[3];

                if (seq > last_seq) {
                    unique_rx++;
                    if (last_seq > 0) {
                        uint32_t gap = seq - last_seq - 1;
                        lost_pkts += gap;
                    }
                    last_seq = seq;
                }

                // Print packet info
                Serial.print("PKT seq=");
                Serial.print(seq);
                Serial.print(" rssi=");
                Serial.print(status.rssi_dbm);
                Serial.print(" snr=");
                Serial.print((int)status.snr_db);
                Serial.print(" len=");
                Serial.print(status.length);
                Serial.print(" br=");
                Serial.print(current_bitrate);
                Serial.print(" payload=");
                Serial.println(PAYLOAD_SIZE);

                // Quick LED blink on packet
                radio.set_led(false);
                delayMicroseconds(100);
                radio.set_led(true);
            }

            radio.clear_irq();
        } else if (IrqSource::contains(irq_flags, IrqSource::CRC_ERROR)) {
            Serial.println("PKT_CRC_ERROR");
            radio.clear_irq();
        } else {
            radio.clear_irq();
        }
    }

    // Heartbeat every 3 seconds
    static uint32_t last_hb = 0;
    if (millis() - last_hb > 3000) {
        last_hb = millis();
        float per = (total_rx + lost_pkts > 0)
            ? (100.0f * lost_pkts / (total_rx + lost_pkts))
            : 0.0f;

        Serial.print("HEARTBEAT rx=");
        Serial.print(total_rx);
        Serial.print(" unique=");
        Serial.print(unique_rx);
        Serial.print(" lost=");
        Serial.print(lost_pkts);
        Serial.print(" per=");
        Serial.print(per, 1);
        Serial.print(" noise=");
        Serial.print(noise_floor);
        Serial.print(" br=");
        Serial.println(current_bitrate);
    }
}
