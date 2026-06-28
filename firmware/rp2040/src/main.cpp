/*
 * main.cpp — RP2040 coprocessor firmware for LR2021 speed / range test
 *
 * Boot sequence:
 *   1. Pin self-test (soldering verification)
 *   2. Radio init (RadioLib: 868 MHz / SF9 / CR 4-7 / +22 dBm — matches tracker)
 *   3. Wait for a command character:
 *        'S' → RX speed test (500 packets, CSV output)
 *        'T' → TX test       (500 numbered packets, 100 ms spacing)
 *
 * TX packet layout (255 bytes):
 *   [ SEQ(4, big-endian) ][ PAYLOAD(N) ][ CRC16(2, big-endian) ]
 *   CRC-16/CCITT over SEQ + PAYLOAD.
 */

#include <Arduino.h>
#include "pins.h"
#include "radio.h"

#define PKT_SIZE        255
#define PKT_COUNT       500
#define TX_INTERVAL_MS  100
#define LISTEN_MS       12000

// Payload bytes between the 4-byte SEQ header and 2-byte CRC trailer.
#define TX_PAYLOAD_LEN  (PKT_SIZE - 6)

// Forward declarations (definitions appear after setup()).
static void run_rx_test(char *buf);
static void run_tx_test(char *buf);

// CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF) — matches tracker telemetry.
static uint16_t crc16_ccitt(const uint8_t *data, size_t len) {
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < len; i++) {
        crc ^= (uint16_t)data[i] << 8;
        for (int b = 0; b < 8; b++) {
            if (crc & 0x8000) crc = (crc << 1) ^ 0x1021;
            else              crc = (crc << 1);
        }
    }
    return crc;
}

void setup() {
    Serial.begin(115200);
    Serial1.begin(115200);

    pinMode(PIN_LED, OUTPUT);
    pinMode(PIN_LED_ALT, OUTPUT);
    for (int i = 0; i < 3; i++) {
        digitalWrite(PIN_LED, HIGH);
        digitalWrite(PIN_LED_ALT, HIGH);
        delay(200);
        digitalWrite(PIN_LED, LOW);
        digitalWrite(PIN_LED_ALT, LOW);
        delay(200);
    }

    Serial.println("BOOT");

    // ─── Pin self-test ───
    Serial.println("SELFTEST_START");
    PinTestResult test = radio_pin_selftest();
    Serial.println(test.message);

    char buf[256];
    snprintf(buf, sizeof(buf),
             "SELFTEST_RESULT,cs=%d,busy=%d,rst=%d,spi=%d,irq=%d,errors=%d,chipid=0x%08lX",
             test.spi_cs_ok, test.busy_responds, test.rst_pin_works,
             test.radio_responds, test.irq_pin_works, test.errors,
             (unsigned long)test.chip_id);
    Serial.println(buf);

    if (test.errors > 0) {
        Serial.println("SELFTEST_WARN — continuing without radio (pins may not be soldered yet)");
        Serial1.println("SELFTEST_WARN");
        // Don't halt — continue so we can verify serial output works
    } else {
        Serial.println("SELFTEST_PASSED");
    }

    // ─── Init radio (RadioLib modem config) ───
    int rc = radio_init(0);
    if (rc != 0) {
        snprintf(buf, sizeof(buf), "RADIO_INIT_FAILED rc=%d", rc);
        Serial.println(buf);
        while (true) { delay(1000); }
    }
    Serial.println("RADIO_INIT_OK 868MHz/SF9/CR4-7/0x12/22dBm/pre8");
    Serial.println("READY  (send 'S' = RX test, 'T' = TX test)");
    Serial1.println("READY");

    // ─── Wait for start command ───
    bool tx_mode = false;
    while (true) {
        if (Serial.available()) {
            char c = Serial.read();
            if (c == 'S' || c == 's') { tx_mode = false; break; }
            if (c == 'T' || c == 't') { tx_mode = true;  break; }
        }
        if (Serial1.available()) {
            char c = Serial1.read();
            if (c == 'S' || c == 's') { tx_mode = false; break; }
            if (c == 'T' || c == 't') { tx_mode = true;  break; }
        }
        delay(1);
    }

    if (tx_mode) {
        run_tx_test(buf);
    } else {
        run_rx_test(buf);
    }

    // ─── Done: blink forever ───
    while (true) {
        digitalWrite(PIN_LED, HIGH); delay(500);
        digitalWrite(PIN_LED, LOW);  delay(500);
    }
}

// ─── RX speed test ────────────────────────────────────────────────────
static void run_rx_test(char *buf) {
    Serial.println("START_RX");
    Serial.println("pkt,seq,irq_us,read_us,clr_us,rx_us,total_us");

    radio_start_rx();

    uint8_t pktbuf[PKT_SIZE];
    PacketTiming timing;
    uint32_t pktNum = 0;
    uint32_t lastSeq = 0xFFFFFFFF;
    uint32_t received = 0, unique = 0, duplicates = 0;
    uint32_t minUs = 0xFFFFFFFF, maxUs = 0;
    uint64_t totalUs = 0;
    uint32_t startMs = millis();

    while (pktNum < PKT_COUNT && (millis() - startMs) < LISTEN_MS) {
        if (!radio_poll_irq()) continue;
        radio_clear_irq_flag();

        int n = radio_read_packet(pktbuf, PKT_SIZE, &timing);
        if (n <= 0) continue;

        uint32_t seq = ((uint32_t)pktbuf[0] << 24) | ((uint32_t)pktbuf[1] << 16) |
                       ((uint32_t)pktbuf[2] << 8) | (uint32_t)pktbuf[3];

        pktNum++;
        received++;
        if (seq == lastSeq) duplicates++;
        else unique++;
        lastSeq = seq;

        if (timing.total < minUs) minUs = timing.total;
        if (timing.total > maxUs) maxUs = timing.total;
        totalUs += timing.total;

        snprintf(buf, 256, "%lu,%lu,%lu,%lu,%lu,%lu,%lu",
                 (unsigned long)pktNum, (unsigned long)seq,
                 (unsigned long)timing.irq_to_read,
                 (unsigned long)timing.read_fifo,
                 (unsigned long)timing.clear_irq,
                 (unsigned long)timing.restart_rx,
                 (unsigned long)timing.total);
        Serial.println(buf);
    }

    uint32_t elapsed = millis() - startMs;
    float tput = (elapsed > 0 && unique > 0)
        ? (float)unique * PKT_SIZE * 8.0f / (float)elapsed : 0.0f;
    float avg = (received > 0) ? (float)totalUs / (float)received : 0.0f;

    Serial.println("=============================================");
    snprintf(buf, 256, "  Received:   %lu", (unsigned long)received);
    Serial.println(buf);
    snprintf(buf, 256, "  Unique:     %lu / %d", (unsigned long)unique, PKT_COUNT);
    Serial.println(buf);
    snprintf(buf, 256, "  Throughput: %.1f kbps", tput);
    Serial.println(buf);
    snprintf(buf, 256, "  Processing: min=%lu avg=%.0f max=%lu us",
             (unsigned long)minUs, avg, (unsigned long)maxUs);
    Serial.println(buf);
    Serial.println("=============================================");

    snprintf(buf, 256,
             "RESULT_RX,%lu,%lu,%lu,0,%.1f,%lu,%.0f,%lu",
             (unsigned long)received,
             (unsigned long)unique,
             (unsigned long)duplicates,
             tput,
             (unsigned long)minUs,
             avg,
             (unsigned long)maxUs);
    Serial.println(buf);
    Serial1.println(buf);
}

// ─── TX test ──────────────────────────────────────────────────────────
static void run_tx_test(char *buf) {
    Serial.println("START_TX");
    Serial.println("tx,seq,tx_us,rc");

    uint8_t pktbuf[PKT_SIZE];
    uint32_t sent = 0, ok = 0;
    uint32_t minUs = 0xFFFFFFFF, maxUs = 0;
    uint64_t totalUs = 0;
    uint32_t startMs = millis();

    for (uint32_t seq = 0; seq < PKT_COUNT; seq++) {
        // [ SEQ(4 BE) ]
        pktbuf[0] = (seq >> 24) & 0xFF;
        pktbuf[1] = (seq >> 16) & 0xFF;
        pktbuf[2] = (seq >> 8)  & 0xFF;
        pktbuf[3] =  seq        & 0xFF;

        // [ PAYLOAD(N) ] — rolling pattern so payloads are distinguishable
        for (int i = 0; i < TX_PAYLOAD_LEN; i++) {
            pktbuf[4 + i] = (uint8_t)((i + seq) & 0xFF);
        }

        // [ CRC16(2 BE) ] over SEQ + PAYLOAD
        uint16_t crc = crc16_ccitt(pktbuf, PKT_SIZE - 2);
        pktbuf[PKT_SIZE - 2] = (crc >> 8) & 0xFF;
        pktbuf[PKT_SIZE - 1] =  crc       & 0xFF;

        uint32_t t0 = micros();
        int rc = radio_send_packet(pktbuf, PKT_SIZE);
        uint32_t dt = micros() - t0;

        sent++;
        if (rc == (int)PKT_SIZE) ok++;
        if (dt < minUs) minUs = dt;
        if (dt > maxUs) maxUs = dt;
        totalUs += dt;

        snprintf(buf, 256, "%lu,%lu,%lu,%d",
                 (unsigned long)(seq + 1),
                 (unsigned long)seq,
                 (unsigned long)dt, rc);
        Serial.println(buf);

        delay(TX_INTERVAL_MS);
    }

    uint32_t elapsed = millis() - startMs;
    float avg = (sent > 0) ? (float)totalUs / (float)sent : 0.0f;

    Serial.println("=============================================");
    snprintf(buf, 256, "  Sent:       %lu", (unsigned long)sent);
    Serial.println(buf);
    snprintf(buf, 256, "  OK:         %lu / %d", (unsigned long)ok, PKT_COUNT);
    Serial.println(buf);
    snprintf(buf, 256, "  Tx time:    min=%lu avg=%.0f max=%lu us",
             (unsigned long)minUs, avg, (unsigned long)maxUs);
    Serial.println(buf);
    snprintf(buf, 256, "  Elapsed:    %lu ms", (unsigned long)elapsed);
    Serial.println(buf);
    Serial.println("=============================================");

    snprintf(buf, 256, "RESULT_TX,%lu,%lu,0,0,0,%lu,%.0f,%lu",
             (unsigned long)sent,
             (unsigned long)ok,
             (unsigned long)minUs,
             avg,
             (unsigned long)maxUs);
    Serial.println(buf);
    Serial1.println(buf);

    // Return to RX so the unit keeps listening after the burst.
    radio_start_rx();
}

void loop() {}
