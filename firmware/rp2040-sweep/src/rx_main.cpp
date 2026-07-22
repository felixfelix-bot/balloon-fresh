/*
 * rx_main.cpp — Multi-mode sweep receiver (ADR-018/019)
 * Detects TX sweep start, switches modes in sync.
 */
#ifdef ROLE_RX

#include "sweep_config.h"
#include "radio.h"

char linebuf[256];

bool sweepActive = false;
uint8_t currentModeIdx = 0;
uint32_t modeStartTime = 0;
uint32_t rxCount = 0;

void startSweep() {
    sweepActive = true;
    currentModeIdx = 0;
    modeStartTime = millis();
    rxCount = 0;

    Serial1.println("SWEEP_START_RX");

    int16_t state = configureRadio(SWEEP_TABLE[0]);
    if (state == RADIOLIB_ERR_NONE) {
        radio.setPacketReceivedAction(rxISR);
        radio.startReceive();
    } else {
        snprintf(linebuf, sizeof(linebuf), "RX_INIT_ERR=%d", state);
        Serial1.println(linebuf);
    }
}

void nextMode() {
    currentModeIdx++;
    if (currentModeIdx >= SWEEP_COUNT) {
        sweepActive = false;
        radio.standby();
        snprintf(linebuf, sizeof(linebuf), "SWEEP_COMPLETE_RX rx=%lu", rxCount);
        Serial1.println(linebuf);

        configureRadio(SWEEP_TABLE[0]);
        radio.setPacketReceivedAction(rxISR);
        radio.startReceive();
        return;
    }

    const SweepConfig& cfg = SWEEP_TABLE[currentModeIdx];
    snprintf(linebuf, sizeof(linebuf), "MODE_START id=%d %s", cfg.id, cfg.name);
    Serial1.println(linebuf);

    int16_t state = configureRadio(cfg);
    if (state == RADIOLIB_ERR_NONE) {
        radio.setPacketReceivedAction(rxISR);
        radio.startReceive();
    } else {
        snprintf(linebuf, sizeof(linebuf), "RX_CFG_ERR id=%d err=%d", cfg.id, state);
        Serial1.println(linebuf);
    }
    modeStartTime = millis();
}

void setup() {
    Serial.begin(115200);
    // CRITICAL: must remap Serial1 to GP12/GP13 for ESP32 bridge
    Serial1.setTX(12);
    Serial1.setRX(13);
    Serial1.begin(115200);
    delay(2000);

    Serial1.println("=== SWEEP RX READY ===");

    spiRf.begin();

    Serial1.print("Init radio FLRC_2600...");
    int16_t state = configureRadio(SWEEP_TABLE[0]);
    if (state != RADIOLIB_ERR_NONE) {
        snprintf(linebuf, sizeof(linebuf), " FAILED: %d", state);
        Serial1.println(linebuf);
        delay(1000);
        state = configureRadio(SWEEP_TABLE[0]);
        if (state != RADIOLIB_ERR_NONE) {
            snprintf(linebuf, sizeof(linebuf), "FAILED2: %d", state);
            Serial1.println(linebuf);
            while (true) { delay(1000); }
        }
    }
    Serial1.println(" Radio OK");

    radio.setPacketReceivedAction(rxISR);
    radio.startReceive();
    Serial1.println("RX listening on FLRC_2600 (waiting for sweep)");
}

void loop() {
    if (!sweepActive) {
        // Idle: listen for TX packets on config 0
        if (rxFlag) {
            rxFlag = false;
            int16_t len = radio.getPacketLength();
            if (len >= 5) {
                uint8_t buf[64];
                radio.readData(buf, len);
                uint8_t modeId = buf[0];
                if (modeId == 0) {
                    float rssi = radio.getRSSI();
                    rxCount++;
                    snprintf(linebuf, sizeof(linebuf),
                             "PKT,%lu,%d,%.0f,%d",
                             rxCount, 0, rssi, 0);
                    Serial1.println(linebuf);

                    // Start sweep timeline
                    startSweep();
                    return;
                }
            }
            radio.startReceive();
        }
        delay(1);
        return;
    }

    // Sweep active: check for mode window expiry
    const SweepConfig& cfg = SWEEP_TABLE[currentModeIdx];
    uint32_t elapsed = millis() - modeStartTime;

    if (elapsed >= (cfg.window_ms + SWEEP_GUARD_MS)) {
        nextMode();
        return;
    }

    // Process received packets
    if (rxFlag) {
        rxFlag = false;
        int16_t len = radio.getPacketLength();
        if (len > 0 && len <= 64) {
            uint8_t buf[64];
            int16_t state = radio.readData(buf, len);
            if (state == RADIOLIB_ERR_NONE) {
                rxCount++;

                uint8_t modeId = buf[0];
                uint32_t seq = ((uint32_t)buf[1] << 24) |
                               ((uint32_t)buf[2] << 16) |
                               ((uint32_t)buf[3] << 8) |
                               (uint32_t)buf[4];

                float rssi = radio.getRSSI();

                snprintf(linebuf, sizeof(linebuf),
                         "PKT,%lu,%lu,%.0f,%d",
                         rxCount, seq, rssi, modeId);
                Serial1.println(linebuf);
            }
        }
        radio.startReceive();
    }
}

#endif
