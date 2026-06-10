#pragma once

#include <Dispatcher.h>
#include <RadioLib.h>
#include "esp_log.h"
#include "esp_timer.h"
#include "esp_random.h"
#include "esp_sleep.h"

#define STATE_IDLE       0
#define STATE_RX         1
#define STATE_TX_WAIT    3
#define STATE_TX_DONE    4
#define STATE_INT_READY 16

static const char *MESH_TAG = "MESH";

namespace mesh {

class EspIdfRadio : public Radio {
    PhysicalLayer* _radio;
    MainBoard* _board;
    volatile uint8_t _state;
    uint32_t _n_recv, _n_sent, _n_recv_errors;
    int16_t _noise_floor;
    int16_t _threshold;
    uint16_t _num_floor_samples;
    int32_t _floor_sample_sum;

    static volatile uint8_t _isr_state;

    static void IRAM_ATTR _isrFlag() {
        _isr_state |= STATE_INT_READY;
    }

    void idle() {
        _radio->standby();
        _state = STATE_IDLE;
    }

    void startRecv() {
        int16_t err = _radio->startReceive();
        if (err == RADIOLIB_ERR_NONE) {
            _state = STATE_RX;
        } else {
            ESP_LOGE(MESH_TAG, "startReceive err: %d", err);
        }
    }

    float packetScoreInt(float snr, int sf, int packet_len) {
        static float snr_threshold[] = {-7.5f, -10.0f, -12.5f, -15.0f, -17.5f, -20.0f};
        if (sf < 7 || sf > 12) return 0.0f;
        if (snr < snr_threshold[sf - 7]) return 0.0f;
        float rate = (snr - snr_threshold[sf - 7]) / 10.0f;
        float penalty = 1.0f - (packet_len / 256.0f);
        float score = rate * penalty;
        if (score < 0.0f) return 0.0f;
        if (score > 1.0f) return 1.0f;
        return score;
    }

public:
    EspIdfRadio(PhysicalLayer& radio, MainBoard& board)
        : _radio(&radio), _board(&board), _state(STATE_IDLE),
          _n_recv(0), _n_sent(0), _n_recv_errors(0),
          _noise_floor(0), _threshold(0),
          _num_floor_samples(0), _floor_sample_sum(0) {}

    void begin() override {
        _radio->setPacketReceivedAction(_isrFlag);
        _state = STATE_IDLE;
        _noise_floor = 0;
        _threshold = 0;
        _num_floor_samples = 0;
        _floor_sample_sum = 0;
    }

    int recvRaw(uint8_t* bytes, int sz) override {
        int len = 0;
        if (_state & STATE_INT_READY) {
            len = _radio->getPacketLength();
            if (len > 0) {
                if (len > sz) len = sz;
                int16_t err = _radio->readData(bytes, len);
                if (err != RADIOLIB_ERR_NONE) {
                    ESP_LOGE(MESH_TAG, "readData err: %d", err);
                    len = 0;
                    _n_recv_errors++;
                } else {
                    _n_recv++;
                }
            }
            _state = STATE_IDLE;
        }

        if (_state != STATE_RX) {
            startRecv();
        }
        return len;
    }

    uint32_t getEstAirtimeFor(int len_bytes) override {
        return _radio->getTimeOnAir(len_bytes) / 1000;
    }

    float packetScore(float snr, int packet_len) override {
        return packetScoreInt(snr, 9, packet_len);
    }

    bool startSendRaw(const uint8_t* bytes, int len) override {
        _board->onBeforeTransmit();
        int16_t err = _radio->startTransmit((uint8_t*)bytes, len);
        if (err == RADIOLIB_ERR_NONE) {
            _state = STATE_TX_WAIT;
            return true;
        }
        ESP_LOGE(MESH_TAG, "startTransmit err: %d", err);
        idle();
        _board->onAfterTransmit();
        return false;
    }

    bool isSendComplete() override {
        if (_state & STATE_INT_READY) {
            _state = STATE_IDLE;
            _n_sent++;
            return true;
        }
        return false;
    }

    void onSendFinished() override {
        _radio->finishTransmit();
        _board->onAfterTransmit();
        _state = STATE_IDLE;
    }

    void loop() override {
        if (_state == STATE_RX && _num_floor_samples < 64) {
            float rssi = _radio->getRSSI();
            if (rssi < _noise_floor + 14) {
                _num_floor_samples++;
                _floor_sample_sum += (int32_t)rssi;
            }
        } else if (_num_floor_samples >= 64 && _floor_sample_sum != 0) {
            _noise_floor = _floor_sample_sum / 64;
            if (_noise_floor < -120) _noise_floor = -120;
            _floor_sample_sum = 0;
        }
    }

    int getNoiseFloor() const override { return _noise_floor; }

    void triggerNoiseFloorCalibrate(int threshold) override {
        _threshold = threshold;
        _num_floor_samples = 0;
        _floor_sample_sum = 0;
    }

    void resetAGC() override {
        if ((_state & STATE_INT_READY) != 0) return;
        _radio->sleep();
        _state = STATE_IDLE;
        _noise_floor = 0;
        _num_floor_samples = 0;
        _floor_sample_sum = 0;
    }

    bool isInRecvMode() const override {
        return (_state & ~STATE_INT_READY) == STATE_RX;
    }

    bool isReceiving() override {
        return (_state & STATE_INT_READY) != 0;
    }

    float getLastRSSI() const override { return _radio->getRSSI(); }
    float getLastSNR() const override { return _radio->getSNR(); }
};

volatile uint8_t EspIdfRadio::_isr_state = STATE_IDLE;

class EspIdfClock : public MillisecondClock {
public:
    unsigned long getMillis() override {
        return (unsigned long)(esp_timer_get_time() / 1000);
    }
};

class EspIdfRNG : public RNG {
public:
    void random(uint8_t* dest, size_t sz) override {
        esp_fill_random(dest, sz);
    }
};

class EspIdfRTC : public RTCClock {
    uint32_t _time;
    uint32_t _set_at_ms;
    EspIdfClock _clock;

    uint32_t getCurrentTime() override {
        uint32_t elapsed = (_clock.getMillis() - _set_at_ms) / 1000;
        return _time + elapsed;
    }

    void setCurrentTime(uint32_t time) override {
        _time = time;
        _set_at_ms = _clock.getMillis();
    }
};

class EspIdfBoard : public MainBoard {
    uint8_t _startup_reason;
public:
    EspIdfBoard() : _startup_reason(BD_STARTUP_NORMAL) {}

    uint16_t getBattMilliVolts() override {
#ifdef CONFIG_ENABLE_POWER_MANAGER
        extern uint16_t power_manager_read_supercap_mv(void);
        return power_manager_read_supercap_mv();
#else
        return 3300;
#endif
    }

    const char* getManufacturerName() const override { return "esp32-c3-balloon"; }

    void reboot() override { esp_restart(); }

    void sleep(uint32_t secs) override {
        esp_sleep_enable_timer_wakeup((uint64_t)secs * 1000000);
        esp_deep_sleep_start();
    }

    uint8_t getStartupReason() const override { return _startup_reason; }
};

}
