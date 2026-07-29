#pragma once

/*
 * EspIdfInterfaces.h — ESP-IDF platform adapters for MeshCore.
 *
 * RadioLib has been removed (ADR-020). The radio adapter now wraps
 * Lr2021Radio (from lr2021_transport) instead of RadioLib's PhysicalLayer.
 *
 * Lr2021MeshRadio maps the mesh::Radio interface to the Lr2021Radio
 * packet-level API (send_packet / read_packet / start_rx / standby).
 */

#include <Dispatcher.h>
#include "lr2021_spi.h"   /* Lr2021Radio, PacketStatus, IrqSource, Lr2021Error */
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

/**
 * MeshCore radio adapter backed by Lr2021Radio (lr2021_transport).
 *
 * Replaces the old EspIdfRadio which wrapped RadioLib's PhysicalLayer.
 * Maps mesh::Radio methods to the LR2021 packet-level API.
 */
class Lr2021MeshRadio : public Radio {
    Lr2021Radio* _radio;
    MainBoard*   _board;
    volatile uint8_t _state;
    uint32_t _n_recv, _n_sent, _n_recv_errors;
    int16_t _noise_floor;
    int16_t _threshold;
    uint16_t _num_floor_samples;
    int32_t _floor_sample_sum;

    /* Cached packet status from last recvRaw() */
    PacketStatus _last_pkt;

    void idle() {
        _radio->standby();
        _state = STATE_IDLE;
    }

    void startRecv() {
        _radio->clear_irq();
        if (_radio->start_rx() == Lr2021Error::Ok) {
            _state = STATE_RX;
        } else {
            ESP_LOGE(MESH_TAG, "start_rx failed");
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
    Lr2021MeshRadio(Lr2021Radio& radio, MainBoard& board)
        : _radio(&radio), _board(&board), _state(STATE_IDLE),
          _n_recv(0), _n_sent(0), _n_recv_errors(0),
          _noise_floor(0), _threshold(0),
          _num_floor_samples(0), _floor_sample_sum(0) {}

    void begin() override {
        _state = STATE_IDLE;
        _noise_floor = 0;
        _threshold = 0;
        _num_floor_samples = 0;
        _floor_sample_sum = 0;
        startRecv();
    }

    int recvRaw(uint8_t* bytes, int sz) override {
        int len = 0;

        /* Check if IRQ is asserted (packet received) */
        bool irq = false;
        _radio->check_irq(irq);
        if (irq) {
            PacketStatus status;
            if (_radio->read_packet(bytes, sz, status) == Lr2021Error::Ok) {
                len = (int)status.length;
                _last_pkt = status;
                if (len > 0) {
                    _n_recv++;
                }
            } else {
                ESP_LOGE(MESH_TAG, "read_packet failed");
                _n_recv_errors++;
            }
            _state = STATE_IDLE;
        }

        if (_state != STATE_RX) {
            startRecv();
        }
        return len;
    }

    uint32_t getEstAirtimeFor(int len_bytes) override {
        /* FLRC 2600 kbps: (len_bytes * 8) / 2600000 seconds → ms */
        uint32_t us = (uint32_t)((len_bytes * 8ULL * 1000000ULL) / 2600000ULL);
        return us / 1000 + 1;  /* +1 ms for preamble/sync overhead */
    }

    float packetScore(float snr, int packet_len) override {
        return packetScoreInt(snr, 9, packet_len);
    }

    bool startSendRaw(const uint8_t* bytes, int len) override {
        _board->onBeforeTransmit();
        _radio->standby();
        if (_radio->send_packet(bytes, (size_t)len) == Lr2021Error::Ok) {
            _state = STATE_TX_WAIT;
            return true;
        }
        ESP_LOGE(MESH_TAG, "send_packet failed");
        idle();
        _board->onAfterTransmit();
        return false;
    }

    bool isSendComplete() override {
        if (_state == STATE_TX_WAIT) {
            uint32_t flags = 0;
            _radio->get_irq_status(flags);
            if (flags & IrqSource::TX_DONE) {
                _state = STATE_TX_DONE;
                _n_sent++;
                return true;
            }
        }
        return false;
    }

    void onSendFinished() override {
        _radio->clear_irq();
        _board->onAfterTransmit();
        _state = STATE_IDLE;
    }

    void loop() override {
        /* Noise floor sampling (simplified — no RSSI in idle for FLRC) */
        if (_state == STATE_RX && _num_floor_samples < 64) {
            /* FLRC doesn't expose live RSSI in RX; use last packet RSSI as proxy */
            _num_floor_samples++;
            _floor_sample_sum += _last_pkt.rssi_dbm;
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
        _radio->standby();
        _state = STATE_IDLE;
        _noise_floor = 0;
        _num_floor_samples = 0;
        _floor_sample_sum = 0;
    }

    bool isInRecvMode() const override {
        return _state == STATE_RX;
    }

    bool isReceiving() override {
        bool irq = false;
        _radio->check_irq(irq);
        return irq;
    }

    float getLastRSSI() const override { return (float)_last_pkt.rssi_dbm; }
    float getLastSNR() const override { return (float)_last_pkt.snr_db; }
};

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
