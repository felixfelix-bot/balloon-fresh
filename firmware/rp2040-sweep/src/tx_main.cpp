/*
 * tx_main.cpp — Multi-mode sweep transmitter (ADR-018/019)
 * Press button (GP15) to start 55-second sweep through all 10 configs.
 */
#ifdef ROLE_TX

#include "sweep_config.h"
#include "radio.h"

#define SWEEP_BUTTON 15

char linebuf[256];

void setup() {
    Serial.begin(115200);
    // CRITICAL: must remap Serial1 to GP12/GP13 for ESP32 bridge
    Serial1.setTX(12);
    Serial1.setRX(13);
    Serial1.begin(115200);
    delay(2000);

    pinMode(SWEEP_BUTTON, INPUT_PULLUP);
    pinMode(LED_BUILTIN, OUTPUT);

    Serial1.println("=== SWEEP TX READY ===");
    Serial1.println("Press GP15 button to start sweep");
    Serial1.println("DBG: before spiRf.begin");
    Serial1.flush();

    spiRf.begin();
    Serial1.println("DBG: after spiRf.begin");
    Serial1.flush();

    // Initialize with FLRC 650 kbps (proven working bitrate)
    Serial1.println("DBG: before radio init (FLRC 650)");
    Serial1.flush();
    int16_t state = configureRadio(SWEEP_TABLE[2]); // index 2 = FLRC_650
    Serial1.println("DBG: after radio init");
    Serial1.flush();
    if (state != RADIOLIB_ERR_NONE) {
        snprintf(linebuf, sizeof(linebuf), " FAILED: %d", state);
        Serial1.println(linebuf);
        // Don't hang forever — blink LED and retry
        Serial1.println("RETRY: radio may need warm-up");
        delay(1000);
        state = configureRadio(SWEEP_TABLE[0]);
        if (state != RADIOLIB_ERR_NONE) {
            snprintf(linebuf, sizeof(linebuf), "FAILED2: %d", state);
            Serial1.println(linebuf);
            while (true) { digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN)); delay(500); }
        }
    }
    Serial1.println(" Radio OK");
}

void runSweep() {
    Serial1.println("SWEEP_START");

    for (int i = 0; i < SWEEP_COUNT; i++) {
        const SweepConfig& cfg = SWEEP_TABLE[i];

        snprintf(linebuf, sizeof(linebuf), "MODE_START id=%d %s", cfg.id, cfg.name);
        Serial1.println(linebuf);

        // Configure radio for this mode
        int16_t state = configureRadio(cfg);
        if (state != RADIOLIB_ERR_NONE) {
            snprintf(linebuf, sizeof(linebuf), "  CFG_ERR id=%d err=%d", cfg.id, state);
            Serial1.println(linebuf);
            delay(SWEEP_GUARD_MS);
            continue;
        }

        // Transmit packets for the window duration
        uint32_t windowStart = millis();
        uint32_t seq = 0;

        while ((millis() - windowStart) < cfg.window_ms) {
            uint8_t pkt[SWEEP_PKT_SIZE];
            pkt[0] = cfg.id;
            pkt[1] = (seq >> 24) & 0xFF;
            pkt[2] = (seq >> 16) & 0xFF;
            pkt[3] = (seq >> 8) & 0xFF;
            pkt[4] = seq & 0xFF;
            uint32_t ts = millis() / 1000;
            pkt[5] = (ts >> 24) & 0xFF;
            pkt[6] = (ts >> 16) & 0xFF;
            pkt[7] = (ts >> 8) & 0xFF;
            pkt[8] = ts & 0xFF;
            memset(pkt + 9, 0xAA, SWEEP_PKT_SIZE - 9);

            radio.transmit(pkt, SWEEP_PKT_SIZE);
            seq++;

            // Yield for slow modes
            if (cfg.mod == MOD_LORA && cfg.sf >= 11) {
                delay(10);
            }
        }

        snprintf(linebuf, sizeof(linebuf), "MODE_END id=%d pkts=%lu", cfg.id, seq);
        Serial1.println(linebuf);

        delay(SWEEP_GUARD_MS);
    }

    Serial1.println("SWEEP_COMPLETE");

    // Re-init to first config
    configureRadio(SWEEP_TABLE[0]);
}

void loop() {
    // Wait for button press (active low)
    if (digitalRead(SWEEP_BUTTON) == LOW) {
        digitalWrite(LED_BUILTIN, HIGH);
        delay(50); // debounce

        while (digitalRead(SWEEP_BUTTON) == LOW) { delay(10); }
        delay(50);

        runSweep();
        digitalWrite(LED_BUILTIN, LOW);
    }

    delay(10);
}

#endif
