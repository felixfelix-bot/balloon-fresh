/*
 * main.cpp — RP2040 coprocessor dual-core firmware for LR2021 speed test
 *
 * Architecture (ADR-015 Board B):
 *   Core 0: Radio I/O (SPI0 → LR2021, tight IRQ-driven RX loop)
 *   Core 1: UART protocol (packet queue → ESP32-C3, statistics, CSV output)
 *
 * Communication protocol with ESP32-C3 (or USB serial for standalone):
 *   - CSV lines: "pkt,seq,irq_us,read_us,clr_us,rx_us,total_us\n"
 *   - Summary lines: "RESULT,recv,unique,dup,err,tput_kbps,min_us,max_us,avg_us\n"
 *   - Sync: "READY\n" at boot, "START\n" when entering speed test
 *
 * Build modes (compile-time):
 *   MODE_SPEEDTEST  — High-throughput RX loop, minimal per-packet overhead
 *   MODE_PROFILE    — Detailed per-stage timing (like profile_rx.cpp)
 *   MODE_CONTINUITY — Long-run reliability test (count drops over N packets)
 */

#include <Arduino.h>
#include <FreeRTOS.h>
#include <task.h>
#include <semphr.h>
#include <queue.h>
#include "pins.h"
#include "radio.h"

// ─── Configuration ────────────────────────────────────────────────────

#ifndef PKT_SIZE
#define PKT_SIZE        255
#endif

#ifndef PKT_COUNT
#define PKT_COUNT       500
#endif

#ifndef LISTEN_MS
#define LISTEN_MS       12000
#endif

#ifndef SERIAL_BAUD
#define SERIAL_BAUD     115200
#endif

// Ring buffer for Core 0 → Core 1 communication
#define QUEUE_DEPTH     32

// ─── Inter-core communication ─────────────────────────────────────────

struct PacketEntry {
    uint8_t       data[PKT_SIZE];
    PacketTiming  timing;
    uint32_t      seq;
};

static QueueHandle_t pktQueue = NULL;
static volatile uint32_t core0_count = 0;
static volatile uint32_t core1_count = 0;
static volatile bool test_running = false;
static volatile bool test_complete = false;

// ─── Core 0: Radio I/O ────────────────────────────────────────────────

static void core0_radio_task() {
    // Wait for test to start
    while (!test_running) {
        tight_loop_contents();
    }

    radio_start_rx();

    PacketEntry entry;
    uint32_t lastSeq = 0xFFFFFFFF;
    uint32_t pktNum = 0;

    while (test_running && pktNum < PKT_COUNT) {
        // Tight poll on IRQ pin — no RTOS delay for minimum latency
        if (!radio_poll_irq()) {
            continue;
        }

        // Clear the software IRQ flag (we're polling, not using ISR here)
        radio_clear_irq_flag();

        // Read packet with timing
        int n = radio_read_packet(entry.data, PKT_SIZE, &entry.timing);
        if (n <= 0) {
            continue;
        }

        // Extract sequence number (first 4 bytes, big-endian)
        entry.seq = ((uint32_t)entry.data[0] << 24) |
                    ((uint32_t)entry.data[1] << 16) |
                    ((uint32_t)entry.data[2] << 8)  |
                    (uint32_t)entry.data[3];

        pktNum++;
        core0_count = pktNum;

        // Push to queue for Core 1 (non-blocking — drop if queue full)
        xQueueSend(pktQueue, &entry, 0);
    }

    // Signal completion
    test_complete = true;
}

// ─── Core 1: Statistics + UART output ────────────────────────────────

static void core1_stats_task() {
    Serial1.begin(SERIAL_BAUD);
    Serial.begin(SERIAL_BAUD);

    // Boot message
    Serial.println("READY");
    Serial1.println("READY");
    delay(100);

    // Wait for test to start
    while (!test_running) {
        if (Serial.available()) {
            char cmd = Serial.read();
            if (cmd == 'S' || cmd == 's') {
                test_running = true;
                Serial.println("START");
                Serial1.println("START");
                break;
            }
        }
        delay(1);
    }

    // CSV header
    Serial.println("pkt,seq,irq_us,read_us,clr_us,rx_us,total_us");
    Serial1.println("pkt,seq,irq_us,read_us,clr_us,rx_us,total_us");

    PacketEntry entry;
    RadioStats stats = {0};
    stats.last_seq = 0xFFFFFFFF;
    stats.min_total_us = 0xFFFFFFFF;

    uint32_t startMs = millis();

    while (!test_complete) {
        if (xQueueReceive(pktQueue, &entry, pdMS_TO_TICKS(100)) == pdTRUE) {
            core1_count++;

            // Update stats
            stats.received++;
            if (entry.seq == stats.last_seq) {
                stats.duplicates++;
            } else {
                stats.unique++;
            }
            stats.last_seq = entry.seq;

            if (entry.timing.total < stats.min_total_us)
                stats.min_total_us = entry.timing.total;
            if (entry.timing.total > stats.max_total_us)
                stats.max_total_us = entry.timing.total;
            stats.total_us_sum += entry.timing.total;

            // Print per-packet CSV (to both USB and UART)
            char line[128];
            snprintf(line, sizeof(line), "%lu,%lu,%lu,%lu,%lu,%lu,%lu",
                     (unsigned long)core1_count,
                     (unsigned long)entry.seq,
                     (unsigned long)entry.timing.irq_to_read,
                     (unsigned long)entry.timing.read_fifo,
                     (unsigned long)entry.timing.clear_irq,
                     (unsigned long)entry.timing.restart_rx,
                     (unsigned long)entry.timing.total);
            Serial.println(line);
            Serial1.println(line);
        }
    }

    // Drain remaining queue
    while (xQueueReceive(pktQueue, &entry, 0) == pdTRUE) {
        core1_count++;
        stats.received++;
        if (entry.seq != stats.last_seq) stats.unique++;
        else stats.duplicates++;
        stats.last_seq = entry.seq;
    }

    uint32_t elapsed = millis() - startMs;
    float tput = (elapsed > 0 && stats.unique > 0)
        ? (float)stats.unique * PKT_SIZE * 8.0f / (float)elapsed
        : 0.0f;
    float avg_us = (stats.received > 0)
        ? (float)stats.total_us_sum / (float)stats.received
        : 0.0f;

    // Print summary
    Serial.println("=============================================");
    Serial.printf("  SPEED TEST SUMMARY (%lu pkts, %lu ms)\n",
                  (unsigned long)stats.received, (unsigned long)elapsed);
    Serial.println("=============================================");
    Serial.printf("  Received:   %lu\n", (unsigned long)stats.received);
    Serial.printf("  Unique:     %lu / %d\n", (unsigned long)stats.unique, PKT_COUNT);
    Serial.printf("  Duplicates: %lu\n", (unsigned long)stats.duplicates);
    Serial.printf("  PER:        %.1f%%\n",
                  (PKT_COUNT - stats.received) * 100.0f / PKT_COUNT);
    Serial.printf("  Throughput: %.1f kbps\n", tput);
    Serial.printf("  Processing: min=%lu avg=%.0f max=%lu µs/pkt\n",
                  (unsigned long)stats.min_total_us, avg_us,
                  (unsigned long)stats.max_total_us);
    Serial.printf("  Max RX rate: %.0f pkt/s\n", 1000000.0f / avg_us);
    Serial.printf("  Max tput:    %.1f kbps\n",
                  1000000.0f / avg_us * PKT_SIZE * 8 / 1000.0f);
    Serial.println("=============================================");

    // Machine-readable result line
    Serial.printf("RESULT,%lu,%lu,%lu,%lu,%.1f,%lu,%.0f,%lu\n",
                  (unsigned long)stats.received,
                  (unsigned long)stats.unique,
                  (unsigned long)stats.duplicates,
                  (unsigned long)stats.errors,
                  tput,
                  (unsigned long)stats.min_total_us,
                  avg_us,
                  (unsigned long)stats.max_total_us);
    Serial1.printf("RESULT,%lu,%lu,%lu,%lu,%.1f,%lu,%.0f,%lu\n",
                   (unsigned long)stats.received,
                   (unsigned long)stats.unique,
                   (unsigned long)stats.duplicates,
                   (unsigned long)stats.errors,
                   tput,
                   (unsigned long)stats.min_total_us,
                   avg_us,
                   (unsigned long)stats.max_total_us);

    // Blink LED to indicate completion
    while (true) {
        digitalWrite(PIN_LED, 1);
        delay(500);
        digitalWrite(PIN_LED, 0);
        delay(500);
    }
}

// ─── Setup & Loop (Arduino core = Core 1 by default on RP2040) ───────

void setup() {
    // Initialize packet queue
    pktQueue = xQueueCreate(QUEUE_DEPTH, sizeof(PacketEntry));

    // Initialize radio on SPI0
    radio_init(RADIO_MODE_FLRC_2G4);

    // LED blink = boot OK
    for (int i = 0; i < 3; i++) {
        digitalWrite(PIN_LED, 1);
        delay(200);
        digitalWrite(PIN_LED, 0);
        delay(200);
    }

    // Launch Core 0 as radio I/O task
    // On RP2040 Arduino, setup()/loop() run on Core 1.
    // We use multicore to launch radio_task on Core 0.
    multicore_launch_core0(core0_radio_task);

    // Core 1 runs the stats/UART task
    core1_stats_task();
}

void loop() {
    // Not used — core1_stats_task() blocks forever in setup()
}
