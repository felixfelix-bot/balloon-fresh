/*
 * flrc_spi_timing_diag.cpp — RP2040 self-timing SPI diagnostic
 *
 * Measures exact timing of per-byte vs batch SPI transfers using RP2040's
 * own cycle counter. No external logic analyzer needed.
 *
 * Tests:
 * 1. Per-byte transfer(byte) — WORKING method (baseline)
 * 2. Batch transfer(buf, nullptr, len) — FAILED method
 * 3. Single-batch (combined header+payload) — PROPOSED FIX
 *
 * Measures: total time, per-byte time, inter-batch gap
 *
 * Build env: rp2040-spi-timing-diag
 * Pins: standard FLRC pinout
 */

#include <Arduino.h>
#include <SPI.h>

#define PIN_SCK     2
#define PIN_MOSI    3
#define PIN_MISO    4
#define PIN_CS      5
#define PIN_BUSY    6
#define PIN_IRQ     7
#define PIN_RST     8
#define PIN_UART_TX 12
#define PIN_UART_RX 13
#define PIN_LED     25
#define PIN_DBG     14   // debug pin for external scope/LA trigger

#define SPI_FREQ_HZ 16000000UL

static SPIClassRP2040 spiRf(spi0, PIN_MISO, PIN_CS, PIN_SCK, PIN_MOSI);
static SPISettings spiSettings(SPI_FREQ_HZ, MSBFIRST, SPI_MODE0);

// Timing helpers use RP2040's time_us_32() from the SDK

// ─── Test buffers ───────────────────────────────────────────────────
static uint8_t testBuf[260];  // header + 255 payload + margin

// runTests is defined below setup()
void runTests();

void setup() {
    // Init debug pin
    pinMode(PIN_DBG, OUTPUT);
    digitalWrite(PIN_DBG, LOW);

    // Init LED
    pinMode(PIN_LED, OUTPUT);
    digitalWrite(PIN_LED, LOW);

    Serial.begin(115200);
    delay(3000);  // CDC enumeration wait

    // Fill test buffer with known pattern
    for (int i = 0; i < 260; i++) testBuf[i] = (uint8_t)(i & 0xFF);

    Serial.println("\n========================================");
    Serial.println("SPI Timing Diagnostic v1.0");
    Serial.println("========================================");
    Serial.println();
    Serial.println("Type RUN to start timing tests");
    Serial.println("Pin: CS=GP5, SCK=GP2, MOSI=GP3, MISO=GP4");
    Serial.println("Debug trigger: GP14 (toggle before/after each test)");
    Serial.println();

    // Initialize SPI
    spiRf.beginTransaction(spiSettings);
    spiRf.endTransaction();

    // CS pin
    pinMode(PIN_CS, OUTPUT);
    digitalWrite(PIN_CS, HIGH);
}

void loop() {
    static unsigned long lastBlink = 0;
    static String cmd = "";

    // LED heartbeat
    if (millis() - lastBlink > 500) {
        lastBlink = millis();
        digitalWrite(PIN_LED, !digitalRead(PIN_LED));
    }

    // Read serial commands
    while (Serial.available()) {
        char c = Serial.read();
        if (c == '\n' || c == '\r') {
            cmd.trim();
            cmd.toUpperCase();
            if (cmd == "RUN") {
                runTests();
                Serial.println("\nType RUN to repeat");
            } else if (cmd == "HELP") {
                Serial.println("Commands: RUN, HELP");
            }
            cmd = "";
        } else {
            cmd += c;
        }
    }
}

void runTests() {
    const int ITERATIONS = 100;
    const int PAYLOAD_LEN = 255;
    const int HDR_LEN = 2;
    const int TOTAL_LEN = HDR_LEN + PAYLOAD_LEN;  // 257

    uint32_t t0, t1;
    uint32_t perByteTotal = 0, batchSplitTotal = 0, batchSingleTotal = 0;

    Serial.println("--- Test 1: Per-byte transfer (WORKING baseline) ---");
    Serial.println("  Pattern: CS LOW → loop transfer(byte) × 257 → CS HIGH");

    for (int iter = 0; iter < ITERATIONS; iter++) {
        digitalWrite(PIN_DBG, HIGH);
        t0 = time_us_32();

        spiRf.beginTransaction(spiSettings);
        digitalWrite(PIN_CS, LOW);
        for (int i = 0; i < TOTAL_LEN; i++) {
            spiRf.transfer(testBuf[i]);
        }
        digitalWrite(PIN_CS, HIGH);
        spiRf.endTransaction();

        t1 = time_us_32();
        digitalWrite(PIN_DBG, LOW);
        perByteTotal += (t1 - t0);
    }
    float perByteAvg = (float)perByteTotal / ITERATIONS;
    Serial.print("  Avg time: ");
    Serial.print(perByteAvg, 1);
    Serial.print(" us (");
    Serial.print(perByteAvg / TOTAL_LEN * 1000.0f, 1);
    Serial.println(" ns/byte)");

    Serial.println();
    Serial.println("--- Test 2: Split batch (FAILED method) ---");
    Serial.println("  Pattern: CS LOW → transfer(hdr,2) → transfer(data,255) → CS HIGH");
    Serial.println("  NOTE: spi_write_blocking drains FIFO between calls → SCK STOPS");

    for (int iter = 0; iter < ITERATIONS; iter++) {
        digitalWrite(PIN_DBG, HIGH);
        t0 = time_us_32();

        spiRf.beginTransaction(spiSettings);
        digitalWrite(PIN_CS, LOW);
        spiRf.transfer(testBuf, nullptr, HDR_LEN);          // batch 1
        spiRf.transfer(testBuf + HDR_LEN, nullptr, PAYLOAD_LEN); // batch 2
        digitalWrite(PIN_CS, HIGH);
        spiRf.endTransaction();

        t1 = time_us_32();
        digitalWrite(PIN_DBG, LOW);
        batchSplitTotal += (t1 - t0);
    }
    float batchSplitAvg = (float)batchSplitTotal / ITERATIONS;
    Serial.print("  Avg time: ");
    Serial.print(batchSplitAvg, 1);
    Serial.print(" us (");
    Serial.print(batchSplitAvg / TOTAL_LEN * 1000.0f, 1);
    Serial.println(" ns/byte)");

    Serial.println();
    Serial.println("--- Test 3: Single batch (PROPOSED FIX) ---");
    Serial.println("  Pattern: CS LOW → transfer(combined, 257) → CS HIGH");
    Serial.println("  NOTE: ONE spi_write_blocking call → SCK NEVER STOPS");

    // Prepare combined buffer
    testBuf[0] = 0x00;  // header MSB (doesn't matter, no radio)
    testBuf[1] = 0x02;  // header LSB
    // testBuf[2..256] already filled

    for (int iter = 0; iter < ITERATIONS; iter++) {
        digitalWrite(PIN_DBG, HIGH);
        t0 = time_us_32();

        spiRf.beginTransaction(spiSettings);
        digitalWrite(PIN_CS, LOW);
        spiRf.transfer(testBuf, nullptr, TOTAL_LEN);  // SINGLE batch call
        digitalWrite(PIN_CS, HIGH);
        spiRf.endTransaction();

        t1 = time_us_32();
        digitalWrite(PIN_DBG, LOW);
        batchSingleTotal += (t1 - t0);
    }
    float batchSingleAvg = (float)batchSingleTotal / ITERATIONS;
    Serial.print("  Avg time: ");
    Serial.print(batchSingleAvg, 1);
    Serial.print(" us (");
    Serial.print(batchSingleAvg / TOTAL_LEN * 1000.0f, 1);
    Serial.println(" ns/byte)");

    // Summary
    Serial.println();
    Serial.println("========================================");
    Serial.println("SUMMARY");
    Serial.println("========================================");
    Serial.print("Per-byte (working):  ");
    Serial.print(perByteAvg, 1);
    Serial.print(" us total, ");
    Serial.print(perByteAvg / TOTAL_LEN * 1000.0f, 1);
    Serial.println(" ns/byte");

    Serial.print("Split batch (failed): ");
    Serial.print(batchSplitAvg, 1);
    Serial.print(" us total, ");
    Serial.print(batchSplitAvg / TOTAL_LEN * 1000.0f, 1);
    Serial.println(" ns/byte");

    Serial.print("Single batch (fix):   ");
    Serial.print(batchSingleAvg, 1);
    Serial.print(" us total, ");
    Serial.print(batchSingleAvg / TOTAL_LEN * 1000.0f, 1);
    Serial.println(" ns/byte");

    Serial.println();
    float speedup = perByteAvg / batchSingleAvg;
    Serial.print("Single batch speedup: ");
    Serial.print(speedup, 2);
    Serial.println("x faster than per-byte");

    float gapUs = batchSplitAvg - batchSingleAvg;
    Serial.print("Inter-batch gap cost: ");
    Serial.print(gapUs, 1);
    Serial.println(" us (SCK stop between split batches)");

    Serial.println();
    Serial.println("KEY QUESTION:");
    Serial.println("If single-batch is significantly faster than per-byte,");
    Serial.println("AND if the LR2021 works with single-batch (continuous SCK),");
    Serial.println("then we have our throughput fix.");
    Serial.println("Next step: flash single-batch TX firmware, test with real radio.");
}

void loop() {
    digitalWrite(PIN_LED, !digitalRead(PIN_LED));
    delay(1000);
}
