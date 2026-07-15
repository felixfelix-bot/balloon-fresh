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
#include "pio_lr2021_rx.h"

// Custom UART on GP12(TX)/GP13(RX) — SerialLink is hardcoded to GP0/GP1 in Mbed variant
UART SerialLink(p12, p13, NC, NC);

/* SPEED-P6: when 1, the speed-test loop uses the PIO+DMA gapless RX engine
 * (pio_lr2021_rx.*). Set to 0 to force the original CPU-polled MbedSPI path.
 * The PIO engine also falls back automatically if lr2021_rx_init() fails. */
#ifndef USE_PIO_RX
#define USE_PIO_RX 1
#endif
static bool g_pio_rx_ok = false;

#define PKT_SIZE        255
#define PKT_COUNT       500
#define LISTEN_MS       12000

void setup() {
    Serial.begin(115200);
    SerialLink.begin(115200);

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
        SerialLink.println("SELFTEST_WARN");
        // Don't halt — continue so we can verify serial output works
    } else {
        Serial.println("SELFTEST_PASSED");
    }

    // ─── Init radio ───
    int rc = radio_init(0);
    if (rc != 0) {
        Serial.println("RADIO_INIT_FAILED");
        while (true) { delay(1000); }
    }
    Serial.println("RADIO_INIT_OK");
    Serial.println("READY");
    SerialLink.println("READY");

#if USE_PIO_RX
    // ─── PIO + DMA gapless RX engine ────────────────────────────────
    // Claim a PIO state machine + two DMA channels and load the SPI program.
    // Falls back transparently to the MbedSPI path if init fails (e.g. all SMs
    // already claimed by another consumer).
    {
        int rc = lr2021_rx_init(PIN_SPI_SCK, PIN_SPI_MOSI, PIN_SPI_MISO,
                                PIN_SPI_CS, LR2021_RX_DEFAULT_CLK);
        if (rc == 0) {
            lr2021_rx_set_payload_len(PKT_SIZE);
            g_pio_rx_ok = true;
            Serial.println("PIO_RX_OK");
            SerialLink.println("PIO_RX_OK");
        } else {
            Serial.print("PIO_RX_FAIL rc=");
            Serial.println(rc);
            Serial.println("PIO_RX_FAIL — using MbedSPI fallback");
        }
    }
#endif

    // ─── Wait for start ───
    while (true) {
        if (Serial.available()) {
            char c = Serial.read();
            if (c == 'S' || c == 's') break;
        }
        if (SerialLink.available()) {
            char c = SerialLink.read();
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
#if USE_PIO_RX
        /* ── PIO + DMA gapless RX path (SPEED-P6) ──────────────────────
         * On each DIO9 edge we arm one DMA capture into the inactive
         * ping-pong slot, then drain whichever slot finished on a previous
         * iteration.  The CPU never bit-bangs the SPI clock; radio_clear_irq()
         * + radio_start_rx() are the only remaining CPU SPI writes (short
         * 6-byte commands, fine on the MbedSPI path).  NOTE: the one-packet
         * pipeline delay and the per-phase timing columns need calibration on
         * real hardware — see PIO_RX notes in the commit. */
        if (g_pio_rx_ok) {
            static bool pio_armed = false;
            uint32_t t_arm = 0;

            /* Arm exactly one capture per DIO9 edge. */
            if (radio_poll_irq() && !pio_armed && !lr2021_rx_busy()) {
                t_arm = micros();
                lr2021_rx_arm();
                pio_armed = true;
            }

            /* Drain the previously-completed capture. */
            const uint8_t *pp = nullptr;
            size_t plen = 0;
            int slot = lr2021_rx_take(&pp, &plen);
            if (slot >= 0) {
                pio_armed = false;
                if (plen >= 4) {
                    uint32_t t_done = micros();
                    uint32_t seq = ((uint32_t)pp[0] << 24) | ((uint32_t)pp[1] << 16) |
                                   ((uint32_t)pp[2] << 8) | (uint32_t)pp[3];
                    radio_clear_irq();          /* clear radio IRQ + re-enter RX */
                    radio_start_rx();
                    uint32_t t3 = micros();
                    uint32_t tot = t3 - t_done;

                    pktNum++; received++;
                    if (seq == lastSeq) duplicates++; else unique++;
                    lastSeq = seq;
                    if (tot < minUs) minUs = tot;
                    if (tot > maxUs) maxUs = tot;
                    totalUs += tot;
                    (void)t_arm;

                    snprintf(buf, sizeof(buf), "%lu,%lu,%lu,%lu,%lu,%lu,%lu",
                             (unsigned long)pktNum, (unsigned long)seq,
                             (unsigned long)0UL,   /* irq_to_read (n/a) */
                             (unsigned long)0UL,   /* read_fifo (DMA)   */
                             (unsigned long)0UL,   /* clear_irq         */
                             (unsigned long)0UL,   /* restart_rx        */
                             (unsigned long)tot);
                    Serial.println(buf);
                }
            }
            continue;
        }
#endif
        /* ── CPU-polled MbedSPI path (original / fallback) ── */
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
    SerialLink.println(buf);

    while (true) {
        digitalWrite(PIN_LED, HIGH); delay(500);
        digitalWrite(PIN_LED, LOW);  delay(500);
    }
}

void loop() {}
