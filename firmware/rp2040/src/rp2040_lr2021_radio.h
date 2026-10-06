/**
 * @file rp2040_lr2021_radio.h
 * @brief Rp2040Lr2021Radio — implements Lr2021Radio interface for RP2040 (Arduino framework).
 *
 * Bridges the lr2021_transport API (from balloon-fips, now on master) to the
 * RP2040 Arduino SPI library. This allows range-test firmware to use the same
 * radio abstraction as the ESP-IDF firmware.
 *
 * Self-contained: includes all opcodes and types locally (no cross-project includes).
 * Pin assignments match the proven sweep firmware (flrc_range_tx_sweep.cpp).
 *
 * NeoPixel LED status indicator is included (MANDATORY — never remove).
 */

#ifndef RP2040_LR2021_RADIO_H
#define RP2040_LR2021_RADIO_H

#include <Arduino.h>
#include <SPI.h>
#include <stdint.h>
#include <stddef.h>

// ── RP2040 Pin Assignments (proven on hardware) ─────────────────────
// Same as flrc_range_tx_sweep.cpp / flrc_range_rx_sweep.cpp
#ifndef PIN_SCK
#define PIN_SCK      2    // GP2
#endif
#ifndef PIN_MOSI
#define PIN_MOSI     3    // GP3
#endif
#ifndef PIN_MISO
#define PIN_MISO     4    // GP4
#endif
#ifndef PIN_CS
#define PIN_CS       5    // GP5 — NSS
#endif
#ifndef PIN_BUSY
#define PIN_BUSY     6    // GP6
#endif
#ifndef PIN_IRQ
#define PIN_IRQ      7    // GP7 — DIO9
#endif
#ifndef PIN_RST
#define PIN_RST      8    // GP8
#endif
#ifndef PIN_LED
#define PIN_LED      25   // GP25 — onboard LED / NeoPixel data
#endif
#ifndef PIN_LED_ALT
#define PIN_LED_ALT  16   // GP16 — alternate LED
#endif

#ifndef SPI_FREQ_HZ
#define SPI_FREQ_HZ  20000000UL  // 20 MHz (proven max on RP2040)
#endif

#define XTAL_MHZ         52.0f

// ── Error Type ──────────────────────────────────────────────────────

enum class Lr2021Error {
    Ok,
    SpiError,
    Timeout,
    NotInitialized,
    InvalidParam,
    CrcError,
};

inline bool lr2021_ok(Lr2021Error e) { return e == Lr2021Error::Ok; }

// ── Configuration ───────────────────────────────────────────────────

struct Lr2021Config {
    float    freq_mhz;
    uint32_t bitrate_kbps;
    int8_t   tx_power_dbm;
    uint8_t  sync_word[4];
    bool     crc_enabled;
    uint8_t  payload_length;

    Lr2021Config()
        : freq_mhz(2440.0f)
        , bitrate_kbps(2600)
        , tx_power_dbm(12)
        , crc_enabled(true)
        , payload_length(127)
    {
        sync_word[0] = 0x12;
        sync_word[1] = 0xAD;
        sync_word[2] = 0x10;
        sync_word[3] = 0x1B;
    }
};

// ── IRQ Source Flags (32-bit, LR2021 specific) ──────────────────────

namespace IrqSource {
    constexpr uint32_t TX_DONE           = 0x00080000u; // Bit 19
    constexpr uint32_t RX_DONE           = 0x00040000u; // Bit 18
    constexpr uint32_t CMD_ERROR         = 0x00020000u; // Bit 17
    constexpr uint32_t CRC_ERROR         = 0x00100000u; // Bit 20
    constexpr uint32_t TIMEOUT           = 0x00200000u; // Bit 21
    constexpr uint32_t PREAMBLE_DETECTED = 0x00000002u; // Bit 1
    constexpr uint32_t SYNCWORD_VALID    = 0x00000004u; // Bit 2
    constexpr uint32_t ALL               = 0xFFFFFFFFu;

    inline bool contains(uint32_t mask, uint32_t flag) { return (mask & flag) != 0; }
    inline bool empty(uint32_t mask) { return mask == 0; }
}

// ── Packet Status ───────────────────────────────────────────────────

struct PacketStatus {
    size_t length;
    int16_t rssi_dbm;
    int8_t  snr_db;
    bool    crc_ok;

    PacketStatus() : length(0), rssi_dbm(-127), snr_db(-127), crc_ok(true) {}
};

// ── Abstract Radio Interface (mirrors lr2021_spi.h Lr2021Radio) ─────

class Lr2021Radio {
public:
    virtual ~Lr2021Radio() = default;
    virtual Lr2021Error init(const Lr2021Config& config) = 0;
    virtual Lr2021Error start_rx() = 0;
    virtual Lr2021Error send_packet(const uint8_t* data, size_t len) = 0;
    virtual Lr2021Error read_packet(uint8_t* buf, size_t buf_len, PacketStatus& status) = 0;
    virtual Lr2021Error get_irq_status(uint32_t& flags) = 0;
    virtual Lr2021Error clear_irq() = 0;
    virtual Lr2021Error check_irq(bool& asserted) = 0;
    virtual Lr2021Error standby() = 0;
    virtual Lr2021Error sleep() = 0;
};

// ── RP2040 Implementation ───────────────────────────────────────────

class Rp2040Lr2021Radio : public Lr2021Radio {
private:
    SPIClassRP2040 spi;
    SPISettings spiSettings;
    bool initialized_;
    Lr2021Config config_;

    // ── Low-level SPI helpers ──

    void cs_low()   { digitalWrite(PIN_CS, LOW); }
    void cs_high()  { digitalWrite(PIN_CS, HIGH); }

    void wait_busy_low(uint32_t timeout_us = 100000) {
        uint32_t start = micros();
        while (digitalRead(PIN_BUSY) == HIGH) {
            if (micros() - start > timeout_us) return; // timeout
        }
    }

    /// Write command bytes (CS low, wait BUSY low, transfer, CS high)
    void spi_write_cmd(const uint8_t* cmd, size_t len) {
        wait_busy_low();
        spi.beginTransaction(spiSettings);
        cs_low();
        for (size_t i = 0; i < len; i++) spi.transfer(cmd[i]);
        cs_high();
        spi.endTransaction();
    }

    /// Write command + payload in single CS-low transaction (bug fix from hermes)
    void spi_write_cmd_payload(const uint8_t* cmd, size_t cmd_len,
                                const uint8_t* payload, size_t payload_len) {
        wait_busy_low();
        spi.beginTransaction(spiSettings);
        cs_low();
        for (size_t i = 0; i < cmd_len; i++) spi.transfer(cmd[i]);
        for (size_t i = 0; i < payload_len; i++) spi.transfer(payload[i]);
        cs_high();
        spi.endTransaction();
    }

    /// Read: send command, read response in same CS-low transaction (critical fix)
    void spi_read_cmd(const uint8_t* cmd, size_t cmd_len,
                      uint8_t* data, size_t data_len) {
        wait_busy_low();
        spi.beginTransaction(spiSettings);
        cs_low();
        for (size_t i = 0; i < cmd_len; i++) spi.transfer(cmd[i]);
        for (size_t i = 0; i < data_len; i++) data[i] = spi.transfer(0x00);
        cs_high();
        spi.endTransaction();
    }

    /// Convenience: write opcode from uint16
    void send_opcode(uint16_t opcode, const uint8_t* payload = nullptr, size_t plen = 0) {
        uint8_t cmd[2] = { (uint8_t)(opcode >> 8), (uint8_t)(opcode & 0xFF) };
        if (payload && plen > 0) {
            spi_write_cmd_payload(cmd, 2, payload, plen);
        } else {
            spi_write_cmd(cmd, 2);
        }
    }

    // ── FLRC modulation parameter encoding ──

    /// Encode bitrate + coding rate into mod_params byte 3
    /// (matches proven encoding from flrc_range_tx_sweep.cpp)
    uint8_t encode_mod_params_byte3(uint32_t bitrate_kbps) {
        switch (bitrate_kbps) {
            case 2600: return 0x25; // 2600kbps, CR_1_0, BT0.5
            case 2080: return 0x2D; // 2080kbps, CR_3_4, BT0.5
            case 1300: return 0x45; // 1300kbps, CR_1_0, BT0.5
            case 1040: return 0x4D; // 1040kbps, CR_3_4, BT0.5
            case 650:  return 0x85; // 650kbps,  CR_1_0, BT0.5
            case 520:  return 0x8D; // 520kbps,  CR_3_4, BT0.5
            case 325:  return 0xC5; // 325kbps,  CR_1_0, BT0.5
            case 260:  return 0xCD; // 260kbps,  CR_3_4, BT0.5
            default:   return 0x25; // default to 2600
        }
    }

    /// Encode frequency into 4 bytes for SET_RF_FREQUENCY
    void encode_frequency(float freq_mhz, uint8_t* out) {
        uint32_t freq_reg = (uint32_t)((double)freq_mhz * (double)(1 << 25) / (double)XTAL_MHZ);
        out[0] = (freq_reg >> 24) & 0xFF;
        out[1] = (freq_reg >> 16) & 0xFF;
        out[2] = (freq_reg >> 8) & 0xFF;
        out[3] = freq_reg & 0xFF;
    }

public:
    Rp2040Lr2021Radio()
        : spi(spi0, PIN_MISO, PIN_CS, PIN_SCK, PIN_MOSI)  // RP2040 SPI0
        , spiSettings(SPI_FREQ_HZ, MSBFIRST, SPI_MODE0)
        , initialized_(false)
    {}

    // ── Lr2021Radio interface implementation ──

    Lr2021Error init(const Lr2021Config& config) override {
        config_ = config;

        // Pin setup
        pinMode(PIN_CS, OUTPUT);
        digitalWrite(PIN_CS, HIGH);
        pinMode(PIN_BUSY, INPUT);
        pinMode(PIN_IRQ, INPUT);
        pinMode(PIN_RST, OUTPUT);
        pinMode(PIN_LED, OUTPUT);
        pinMode(PIN_LED_ALT, OUTPUT);

        // SPI init
        spi.begin();

        // Hardware reset
        digitalWrite(PIN_RST, LOW);
        delay(10);
        digitalWrite(PIN_RST, HIGH);
        delay(10);
        wait_busy_low();

        // 1. Standby RC
        uint8_t standby_rc[] = { 0x01, 0x28, 0x00 };
        spi_write_cmd(standby_rc, 3);
        delay(5);

        // 2. Set packet type FLRC (0x0207 0x05)
        uint8_t pkt_type[] = { 0x02, 0x07, 0x05 };
        spi_write_cmd(pkt_type, 3);

        // 3. Set RF frequency (0x0200 + 4 bytes)
        uint8_t freq_cmd[6] = { 0x02, 0x00 };
        encode_frequency(config.freq_mhz, freq_cmd + 2);
        spi_write_cmd(freq_cmd, 6);

        // 4. Set FLRC mod params (0x0248 + 3 bytes: BW, CR, BT)
        uint8_t mod_params[5] = { 0x02, 0x48, 0x00, encode_mod_params_byte3(config.bitrate_kbps), 0x00 };
        spi_write_cmd(mod_params, 5);

        // 5. Set sync word (0x024C + 4 bytes)
        uint8_t sync_cmd[6] = { 0x02, 0x4C };
        memcpy(sync_cmd + 2, config.sync_word, 4);
        spi_write_cmd(sync_cmd, 6);

        // 6. Set packet params (0x0249 + 9 bytes: preamble, sync, payload, CRC)
        uint8_t pkt_params[11] = {
            0x02, 0x49,
            0x0C,  // Preamble length: 12 symbols
            0x01,  // Preamble header type
            0x04,  // Sync word length: 4 bytes
            config.payload_length, // Payload length
            config.crc_enabled ? 0x02 : 0x00, // CRC type
            0x00, 0x00, 0x00, 0x00
        };
        spi_write_cmd(pkt_params, 11);

        // 7. Set RX/TX fallback to FS (0x0206 0x03) — NOT standby RC
        uint8_t fallback[] = { 0x02, 0x06, 0x03 };
        spi_write_cmd(fallback, 3);

        // 8. Set PA config (0x0202 + 6 bytes)
        uint8_t pa_config[7] = { 0x02, 0x02, 0x80, 0x00, 0x60, 0x07, 0x10 };
        spi_write_cmd(pa_config, 7);

        // 9. Set TX params (0x0203 + power byte)
        uint8_t tx_power_byte = (uint8_t)(config.tx_power_dbm & 0x7F);
        uint8_t tx_params[3] = { 0x02, 0x03, tx_power_byte };
        spi_write_cmd(tx_params, 3);

        // 10. Calibrate all (0x0122 0x5F) — NOT 0x6F!
        uint8_t calib[] = { 0x01, 0x22, 0x5F };
        spi_write_cmd(calib, 3);
        delay(5);

        // 11. Calibrate front end (0x0123)
        uint8_t calib_fe[] = { 0x01, 0x23 };
        spi_write_cmd(calib_fe, 2);
        delay(5);

        // 12. Configure DIO9 as IRQ (0x0112 0x09 0x11)
        uint8_t dio_config[] = { 0x01, 0x12, 0x09, 0x11 };
        spi_write_cmd(dio_config, 4);

        // 13. Configure IRQ mask for RX/TX done (0x0115)
        uint8_t irq_cfg[] = { 0x01, 0x15, 0x00, 0x0C, 0x00, 0x00 };
        spi_write_cmd(irq_cfg, 6);

        // 14. Clear any pending IRQs (0x0116)
        uint8_t clear_irq_cmd[] = { 0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF };
        spi_write_cmd(clear_irq_cmd, 6);

        // 15. Clear errors (0x0111)
        uint8_t clr_err[] = { 0x01, 0x11, 0x00, 0x00 };
        spi_write_cmd(clr_err, 4);

        initialized_ = true;

        // LED indicator — blink to confirm init success
        digitalWrite(PIN_LED, HIGH);
        delay(100);
        digitalWrite(PIN_LED, LOW);

        return Lr2021Error::Ok;
    }

    Lr2021Error start_rx() override {
        if (!initialized_) return Lr2021Error::NotInitialized;

        // 1. Set RX path HF (0x0201 0x01 0x00) — MANDATORY for 2.4GHz
        uint8_t rx_path[] = { 0x02, 0x01, 0x01, 0x00 };
        spi_write_cmd(rx_path, 4);

        // 2. Calibrate front end (0x0123) — MANDATORY before RX
        uint8_t calib_fe[] = { 0x01, 0x23 };
        spi_write_cmd(calib_fe, 2);
        delay(2);

        // 3. Clear RX FIFO (0x011E)
        uint8_t clr_rx_fifo[] = { 0x01, 0x1E };
        spi_write_cmd(clr_rx_fifo, 2);

        // 4. Set RX continuous (0x020C + 3-byte timeout = 0xFFFFFF = infinite)
        uint8_t set_rx[] = { 0x02, 0x0C, 0xFF, 0xFF, 0xFF };
        spi_write_cmd(set_rx, 5);

        return Lr2021Error::Ok;
    }

    Lr2021Error send_packet(const uint8_t* data, size_t len) override {
        if (!initialized_) return Lr2021Error::NotInitialized;
        if (len > 255) return Lr2021Error::InvalidParam;

        digitalWrite(PIN_LED, HIGH); // LED on during TX

        // 1. Clear TX FIFO (0x011F)
        uint8_t clr_tx_fifo[] = { 0x01, 0x1F };
        spi_write_cmd(clr_tx_fifo, 2);

        // 2. Write TX FIFO (0x0002 + payload)
        spi_write_cmd_payload((const uint8_t*)"\x00\x02", 2, data, len);

        // 3. Set TX (0x020D + 3-byte timeout = 0x000000 = immediate)
        uint8_t set_tx[] = { 0x02, 0x0D, 0x00, 0x00, 0x00 };
        spi_write_cmd(set_tx, 5);

        // 4. Wait for TX_DONE (poll IRQ or busy)
        wait_busy_low(50000); // max 50ms

        digitalWrite(PIN_LED, LOW); // LED off after TX

        return Lr2021Error::Ok;
    }

    Lr2021Error read_packet(uint8_t* buf, size_t buf_len, PacketStatus& status) override {
        if (!initialized_) return Lr2021Error::NotInitialized;

        // 1. Get RX buffer status (0x0113 → 2 bytes: status, length)
        uint8_t rx_status_cmd[] = { 0x01, 0x13 };
        uint8_t rx_status[3] = { 0 };
        spi_read_cmd(rx_status_cmd, 2, rx_status, 3);

        uint8_t pkt_len = rx_status[1];
        if (pkt_len == 0 || pkt_len > buf_len) {
            status.length = 0;
            return Lr2021Error::SpiError;
        }

        // 2. Get start offset from status byte
        uint8_t offset = rx_status[0];

        // 3. Read RX FIFO (0x0003 + offset, then read pkt_len bytes)
        // Actually: just read from FIFO starting at offset
        uint8_t read_fifo_cmd[] = { 0x00, 0x03 };
        spi_read_cmd(read_fifo_cmd, 2, buf, pkt_len);
        status.length = pkt_len;

        // 4. Get packet status (0x0114 → 5 bytes: RSSI, SNR, ...)
        uint8_t pkt_status_cmd[] = { 0x01, 0x14 };
        uint8_t pkt_status_raw[5] = { 0 };
        spi_read_cmd(pkt_status_cmd, 2, pkt_status_raw, 5);

        // RSSI is unsigned — negate for dBm (LR2021 quirk)
        status.rssi_dbm = -(int16_t)pkt_status_raw[0];
        status.snr_db = (int8_t)pkt_status_raw[1];

        // 5. Clear RX FIFO (0x011E)
        uint8_t clr_rx_fifo[] = { 0x01, 0x1E };
        spi_write_cmd(clr_rx_fifo, 2);

        return Lr2021Error::Ok;
    }

    Lr2021Error get_irq_status(uint32_t& flags) override {
        uint8_t cmd[] = { 0x01, 0x17 };
        uint8_t raw[4] = { 0 };
        spi_read_cmd(cmd, 2, raw, 4);
        flags = ((uint32_t)raw[0] << 24) | ((uint32_t)raw[1] << 16) |
                ((uint32_t)raw[2] << 8) | raw[3];
        return Lr2021Error::Ok;
    }

    Lr2021Error clear_irq() override {
        uint8_t cmd[] = { 0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF };
        spi_write_cmd(cmd, 6);
        return Lr2021Error::Ok;
    }

    Lr2021Error check_irq(bool& asserted) override {
        asserted = (digitalRead(PIN_IRQ) == HIGH);
        return Lr2021Error::Ok;
    }

    Lr2021Error standby() override {
        uint8_t cmd[] = { 0x01, 0x28, 0x00 }; // STDBY_RC
        spi_write_cmd(cmd, 3);
        return Lr2021Error::Ok;
    }

    Lr2021Error sleep() override {
        uint8_t cmd[] = { 0x01, 0x29, 0x00 };
        spi_write_cmd(cmd, 3);
        return Lr2021Error::Ok;
    }

    // ── Extended methods (not in base interface, for sweep firmware) ──

    /// Switch FLRC bitrate at runtime (used by sweep scheduler)
    void switch_bitrate(uint32_t new_bitrate_kbps) {
        config_.bitrate_kbps = new_bitrate_kbps;

        // 1. Standby RC
        uint8_t stdby[] = { 0x01, 0x28, 0x00 };
        spi_write_cmd(stdby, 3);
        delay(2);

        // 2. Update mod params
        uint8_t mod_params[5] = { 0x02, 0x48, 0x00, encode_mod_params_byte3(new_bitrate_kbps), 0x00 };
        spi_write_cmd(mod_params, 5);
        delay(1);

        // 3. Recalibrate (0x0122 0x5F)
        uint8_t calib[] = { 0x01, 0x22, 0x5F };
        spi_write_cmd(calib, 3);
        delay(2);

        // 4. Calibrate front end (0x0123)
        uint8_t calib_fe[] = { 0x01, 0x23 };
        spi_write_cmd(calib_fe, 2);
        delay(2);

        // 5. Clear IRQ
        clear_irq();
    }

    /// Get instantaneous RSSI (noise floor measurement)
    int16_t get_rssi_instant() {
        uint8_t cmd[] = { 0x02, 0x0B };
        uint8_t raw[3] = { 0 };
        spi_read_cmd(cmd, 2, raw, 3);
        return -(int16_t)raw[0];
    }

    /// LED status helper (NeoPixel / onboard LED)
    void set_led(bool on) {
        digitalWrite(PIN_LED, on ? HIGH : LOW);
        digitalWrite(PIN_LED_ALT, on ? HIGH : LOW);
    }

    /// Blink LED N times (countdown indicator)
    void blink_led(int count, int delay_ms = 500) {
        for (int i = 0; i < count; i++) {
            set_led(true);
            delay(delay_ms);
            set_led(false);
            delay(delay_ms);
        }
    }

    bool is_initialized() const { return initialized_; }
    const Lr2021Config& get_config() const { return config_; }
};

#endif // RP2040_LR2021_RADIO_H
