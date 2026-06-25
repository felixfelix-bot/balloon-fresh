/*
 * main.cpp — RP2040 coprocessor firmware for LR2021 speed test
 *
 * Boot sequence:
 *   1. Pin self-test (soldering verification)
 *   2. Radio init
 *   3. Wait for 'S' command
 *   4. Speed test (500 packets, CSV output)
 */

#include <Arduino.h>
#include "pins.h"
#include "radio.h"

#define PKT_SIZE        255
#define PKT_COUNT       500
#define LISTEN_MS       12000

void setup() {
    Serial.begin(115200);
    Serial1.begin(115200);

    pinMode(PIN_LED, OUTPUT);
    for (int i = 0; i < 3; i++) {
        digitalWrite(PIN_LED, HIGH);
        delay(200);
        digitalWrite(PIN_LED, LOW);
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
        Serial.println("SELFTEST_FAILED");
        Serial1.println("SELFTEST_FAILED");
        while (true) {
            digitalWrite(PIN_LED, HIGH); delay(100);
            digitalWrite(PIN_LED, LOW);  delay(100);
        }
    }
    Serial.println("SELFTEST_PASSED");

    // ─── Init radio ───
    int rc = radio_init(0);
    if (rc != 0) {
        Serial.println("RADIO_INIT_FAILED");
        while (true) { delay(1000); }
    }
    Serial.println("RADIO_INIT_OK");
    Serial.println("READY");
    Serial1.println("READY");

    // ─── Wait for start ───
    while (true) {
        if (Serial.available()) {
            char c = Serial.read();
            if (c == 'S' || c == 's') break;
        }
        if (Serial1.available()) {
            char c = Serial1.read();
            if (c == 'S' || c == 's') break;
        }
        delay(1);
    }

    Serial.println("START");
    Serial.println("pkt,seq,irq_us,read_us,clr_us,rx_us,total_us");

    // ─── Speed test loop ───
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

        snprintf(buf, sizeof(buf), "%lu,%lu,%lu,%lu,%lu,%lu,%lu",
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
    snprintf(buf, sizeof(buf), "  Received:   %lu", (unsigned long)received);
    Serial.println(buf);
    snprintf(buf, sizeof(buf), "  Unique:     %lu / %d", (unsigned long)unique, PKT_COUNT);
    Serial.println(buf);
    snprintf(buf, sizeof(buf), "  Throughput: %.1f kbps", tput);
    Serial.println(buf);
    snprintf(buf, sizeof(buf), "  Processing: min=%lu avg=%.0f max=%lu us",
             (unsigned long)minUs, avg, (unsigned long)maxUs);
    Serial.println(buf);
    Serial.println("=============================================");

    snprintf(buf, sizeof(buf),
             "RESULT,%lu,%lu,%lu,0,%.1f,%lu,%.0f,%lu",
             (unsigned long)received,
             (unsigned long)unique,
             (unsigned long)duplicates,
             tput,
             (unsigned long)minUs,
             avg,
             (unsigned long)maxUs);
    Serial.println(buf);
    Serial1.println(buf);

    while (true) {
        digitalWrite(PIN_LED, HIGH); delay(500);
        digitalWrite(PIN_LED, LOW);  delay(500);
    }
}

void loop() {}
