/*
 * LR2021Raw.h — Raw 2-byte opcode SPI driver for Semtech LR2021
 *
 * DOES NOT USE RADIOLIB. See ADR-020 for rationale.
 *
 * Extracted from proven flrc_raw_tx.cpp (1377 kbps verified, 0% loss).
 * Protocol docs: docs/lr2021-spi-protocol-reference.md
 *
 * Supports: FLRC, LoRa, GFSK on both 2.4 GHz and sub-GHz bands.
 *
 * Usage:
 *   LR2021Raw radio;
 *   radio.begin(PIN_SCK, PIN_MOSI, PIN_MISO, PIN_CS, PIN_BUSY, PIN_IRQ, PIN_RST, spi);
 *   radio.initFLRC(2440.0, 2600, 12);  // freq MHz, bitrate kbps, power dBm
 *   radio.transmit(data, len);
 *   radio.initRX();
 *   radio.receive(buf, len);
 *
 * Platform: RP2040 (Arduino core by earlephilhower)
 * For ESP32: port rfWriteCmd/rfReadStatus to spi_master API
 */
#pragma once

#include <Arduino.h>
#include <SPI.h>

// ─── LR2021 2-Byte Opcodes (verified against TheClams Rust driver v0.12.0) ───
#define LR2021_SET_RF_FREQUENCY     0x0200
#define LR2021_SET_RX_PATH          0x0201
#define LR2021_SET_PA_CONFIG        0x0202
#define LR2021_SET_TX_PARAMS        0x0203
#define LR2021_SET_RX_TX_FALLBACK   0x0206
#define LR2021_SET_PACKET_TYPE      0x0207
#define LR2021_SET_RX               0x020C
#define LR2021_SET_TX               0x020D
#define LR2021_SEL_PA               0x020F
#define LR2021_CLEAR_ERRORS         0x0111
#define LR2021_SET_DIO_FUNCTION     0x0112
#define LR2021_SET_DIO_IRQ_CONFIG   0x0115
#define LR2021_CLEAR_IRQ            0x0116
#define LR2021_GET_IRQ_STATUS       0x0117
#define LR2021_CALIBRATE            0x0122
#define LR2021_CALIB_FRONT_END      0x0123
#define LR2021_SET_STANDBY          0x0128
#define LR2021_SET_FS               0x0129
#define LR2021_CLEAR_TX_FIFO        0x011F
#define LR2021_CLEAR_RX_FIFO        0x011E
#define LR2021_READ_RX_FIFO         0x0001
#define LR2021_WRITE_TX_FIFO        0x0002

// FLRC-specific
#define LR2021_SET_FLRC_MOD_PARAMS  0x0248
#define LR2021_SET_FLRC_PKT_PARAMS  0x0249
#define LR2021_SET_FLRC_SYNCWORD    0x024C
#define LR2021_GET_RX_STATUS        0x024B

// LoRa-specific
#define LR2021_SET_LORA_MOD_PARAMS   0x0310  // verify exact opcode from datasheet
#define LR2021_SET_LORA_PKT_PARAMS   0x0311
#define LR2021_SET_LORA_SYNCWORD     0x0314

// Packet types
#define PKT_TYPE_FLRC   0x05
#define PKT_TYPE_LORA   0x01
#define PKT_TYPE_GFSK   0x02

// IRQ bits (32-bit)
#define IRQ_RX_DONE     0x00040000  // bit 18
#define IRQ_TX_DONE     0x00080000  // bit 19
#define IRQ_CRC_ERROR   0x00400000  // bit 22
#define IRQ_CMD_ERROR   0x00020000  // bit 17
#define IRQ_ALL         0xFFFFFFFF

// FLRC bitrate codes
#define FLRC_BR_2600    0x00
#define FLRC_BR_2080    0x01
#define FLRC_BR_1300    0x02
#define FLRC_BR_1040    0x03
#define FLRC_BR_650     0x04
#define FLRC_BR_520     0x05
#define FLRC_BR_325     0x06
#define FLRC_BR_260     0x07

// Crystal frequency for NiceRF LoRa2021 module
#define XTAL_MHZ        52.0f

class LR2021Raw {
public:
    // Pins
    uint8_t pin_sck, pin_mosi, pin_miso, pin_cs, pin_busy, pin_irq, pin_rst;

    void begin(uint8_t sck, uint8_t mosi, uint8_t miso, uint8_t cs,
               uint8_t busy, uint8_t irq, uint8_t rst) {
        pin_sck = sck; pin_mosi = mosi; pin_miso = miso;
        pin_cs = cs; pin_busy = busy; pin_irq = irq; pin_rst = rst;

        pinMode(pin_cs, OUTPUT);
        digitalWrite(pin_cs, HIGH);
        pinMode(pin_busy, INPUT);
        pinMode(pin_irq, INPUT);
        pinMode(pin_rst, OUTPUT);
        digitalWrite(pin_rst, HIGH);

        spiRf = new SPIClassRP2040(spi0, miso, cs, sck, mosi);
        spiRf->begin();
    }

    // ─── Low-level SPI ───────────────────────────────────────────────────
    bool waitBusy(uint32_t timeout = 100000) {
        while ((digitalRead(pin_busy) == HIGH) && --timeout) {}
        return timeout > 0;
    }

    void writeCmd(const uint8_t *buf, size_t len) {
        waitBusy();
        spiRf->beginTransaction(spiSettings);
        digitalWrite(pin_cs, LOW);
        for (size_t i = 0; i < len; i++) spiRf->transfer(buf[i]);
        digitalWrite(pin_cs, HIGH);
        spiRf->endTransaction();
    }

    void writeCmd(uint16_t opcode, const uint8_t *payload, size_t len) {
        uint8_t cmd[2 + 32]; // max payload we'll send
        cmd[0] = (opcode >> 8) & 0xFF;
        cmd[1] = opcode & 0xFF;
        if (len > 32) len = 32;
        memcpy(cmd + 2, payload, len);
        writeCmd(cmd, 2 + len);
    }

    void writeCmd(uint16_t opcode) {
        uint8_t cmd[2] = { (uint8_t)(opcode >> 8), (uint8_t)(opcode & 0xFF) };
        writeCmd(cmd, 2);
    }

    uint16_t readStatus() {
        waitBusy();
        spiRf->beginTransaction(spiSettings);
        digitalWrite(pin_cs, LOW);
        uint8_t hi = spiRf->transfer(0x00);
        uint8_t lo = spiRf->transfer(0x00);
        digitalWrite(pin_cs, HIGH);
        spiRf->endTransaction();
        return (hi << 8) | lo;
    }

    uint32_t getIrqStatus() {
        waitBusy();
        spiRf->beginTransaction(spiSettings);
        digitalWrite(pin_cs, LOW);
        spiRf->transfer(0x01); spiRf->transfer(0x17); // GET_IRQ_STATUS
        digitalWrite(pin_cs, HIGH);
        spiRf->endTransaction();
        waitBusy();

        uint8_t buf[6];
        spiRf->beginTransaction(spiSettings);
        digitalWrite(pin_cs, LOW);
        for (int i = 0; i < 6; i++) buf[i] = spiRf->transfer(0x00);
        digitalWrite(pin_cs, HIGH);
        spiRf->endTransaction();
        return ((uint32_t)buf[2] << 24) | ((uint32_t)buf[3] << 16) |
               ((uint32_t)buf[4] << 8) | (uint32_t)buf[5];
    }

    void clearIrq(uint32_t mask = IRQ_ALL) {
        uint8_t cmd[6] = { 0x01, 0x16,
            (uint8_t)(mask >> 24), (uint8_t)(mask >> 16),
            (uint8_t)(mask >> 8), (uint8_t)(mask & 0xFF) };
        writeCmd(cmd, 6);
    }

    void clearErrors() {
        uint8_t cmd[4] = { 0x01, 0x11, 0x00, 0x00 };
        writeCmd(cmd, 4);
    }

    // ─── Hardware reset ──────────────────────────────────────────────────
    void reset() {
        digitalWrite(pin_rst, LOW);
        delayMicroseconds(200);
        digitalWrite(pin_rst, HIGH);
        delay(50);
    }

    // ─── Common init (shared by all modulations) ─────────────────────────
    void standby() {
        uint8_t cmd[3] = { 0x01, 0x28, 0x01 }; // STDBY_XOSC
        writeCmd(cmd, 3);
    }

    void setFrequency(float freq_mhz) {
        uint32_t frf = (uint32_t)((freq_mhz * 1e6 * (double)(1ULL << 18)) / (XTAL_MHZ * 1e6));
        uint8_t cmd[5] = {
            0x02, 0x00,
            (uint8_t)(frf >> 16), (uint8_t)(frf >> 8), (uint8_t)(frf & 0xFF)
        };
        writeCmd(cmd, 5);
    }

    void setRxPath(bool hf) {
        // HF=1 for 2.4 GHz, LF=0 for sub-GHz. MANDATORY before RX.
        uint8_t cmd[4] = { 0x02, 0x01, (uint8_t)(hf ? 0x01 : 0x00), 0x00 };
        writeCmd(cmd, 4);
    }

    void calibFrontEnd(float freq_mhz) {
        uint16_t feFreq = (uint16_t)((freq_mhz / 4.0f) + 0.5f) | 0x8000;
        uint8_t cmd[10] = {
            0x01, 0x23,
            (uint8_t)(feFreq >> 8), (uint8_t)(feFreq & 0xFF),
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00
        };
        writeCmd(cmd, 10);
    }

    void calibrate() {
        uint8_t cmd[3] = { 0x01, 0x22, 0x5F }; // defined bits only
        writeCmd(cmd, 3);
    }

    void setPacketType(uint8_t type) {
        uint8_t cmd[3] = { 0x02, 0x07, type };
        writeCmd(cmd, 3);
    }

    void setPaConfig(int8_t power_dbm) {
        // PA config for HF (2.4 GHz)
        uint8_t cmd[7] = { 0x02, 0x02, 0x80, 0x00, 0x60, 0x07, 0x10 };
        writeCmd(cmd, 7);
        // TX params: power * 2, ramp 16us
        uint8_t cmd2[4] = { 0x02, 0x03, (uint8_t)(power_dbm * 2), 0x04 };
        writeCmd(cmd2, 4);
    }

    void setPaConfigLF(int8_t power_dbm) {
        // PA config for LF (sub-GHz)
        uint8_t cmd[7] = { 0x02, 0x02, 0x00, 0x00, 0x60, 0x07, 0x10 };
        writeCmd(cmd, 7);
        uint8_t cmd2[4] = { 0x02, 0x03, (uint8_t)(power_dbm * 2), 0x04 };
        writeCmd(cmd2, 4);
    }

    void setFallback(uint8_t mode) {
        // STBY_RC=1, STBY_XOSC=2, FS=3
        uint8_t cmd[3] = { 0x02, 0x06, mode };
        writeCmd(cmd, 3);
    }

    void setDioIrq(uint8_t dio_num, uint32_t irq_mask) {
        uint8_t cmd[7] = {
            0x01, 0x15, dio_num,
            (uint8_t)(irq_mask >> 24), (uint8_t)(irq_mask >> 16),
            (uint8_t)(irq_mask >> 8), (uint8_t)(irq_mask & 0xFF)
        };
        writeCmd(cmd, 7);
    }

    void setDioFunction(uint8_t dio_num, uint8_t func) {
        // func: 0=None, 1=IRQ, 2=RfSwitch
        uint8_t cmd[4] = { 0x01, 0x12, dio_num, (uint8_t)((func << 4) | 0x01) };
        writeCmd(cmd, 4);
    }

    // ─── FLRC init (proven working sequence) ─────────────────────────────
    void initFLRC(float freq_mhz = 2440.0f, uint16_t bitrate_kbps = 2600,
                  int8_t power_dbm = 12, uint16_t pkt_size = 255,
                  bool hf_path = true) {
        reset();
        delay(5);

        clearErrors();
        delay(1);
        standby();
        delay(5);

        setPacketType(PKT_TYPE_FLRC);
        delay(1);

        setFrequency(freq_mhz);
        delay(1);

        setRxPath(hf_path);
        delay(1);

        calibFrontEnd(freq_mhz);
        delay(5);

        calibrate();
        delay(5);

        // FLRC modulation params
        uint8_t br_code = bitrateToCode(bitrate_kbps);
        // CR=1/0 (uncoded, 0x02<<4), BT=0.5 (0x05)
        uint8_t mod_params[4] = { 0x02, 0x48, br_code, 0x25 };
        writeCmd(mod_params, 4);
        delay(1);

        // Sync word (must match TX/RX)
        setFLRCSyncWord();
        delay(1);

        // FLRC packet params
        uint8_t pkt_params[6] = {
            0x02, 0x49,
            0x0C,  // preamble=8, syncLen=32bit
            0x4C,  // syncTx=1, syncMatch=1, fixed=1, crc=off
            (uint8_t)(pkt_size >> 8), (uint8_t)(pkt_size & 0xFF)
        };
        writeCmd(pkt_params, 6);
        delay(1);

        // PA config
        if (hf_path) setPaConfig(power_dbm);
        else setPaConfigLF(power_dbm);
        delay(1);

        // Fallback to FS mode
        setFallback(0x03);
        delay(1);

        // DIO9 = IRQ
        setDioFunction(9, 1);
        delay(1);

        // Default: TX_DONE IRQ
        setDioIrq(9, IRQ_TX_DONE);
        delay(1);

        clearIrq();
    }

    // ─── FLRC sync word ──────────────────────────────────────────────────
    void setFLRCSyncWord(uint32_t word = 0x12AD101B) {
        uint8_t cmd[7] = {
            0x02, 0x4C, 0x01,
            (uint8_t)(word >> 24), (uint8_t)(word >> 16),
            (uint8_t)(word >> 8), (uint8_t)(word & 0xFF)
        };
        writeCmd(cmd, 7);
    }

    // ─── TX operations ───────────────────────────────────────────────────
    void clearTxFifo() {
        uint8_t cmd[2] = { 0x01, 0x1F };
        writeCmd(cmd, 2);
    }

    void writeTxFifo(const uint8_t *data, size_t len) {
        waitBusy();
        spiRf->beginTransaction(spiSettings);
        digitalWrite(pin_cs, LOW);
        spiRf->transfer(0x00); // WRITE_TX_FIFO opcode hi
        spiRf->transfer(0x02); // WRITE_TX_FIFO opcode lo
        for (size_t i = 0; i < len; i++) spiRf->transfer(data[i]);
        digitalWrite(pin_cs, HIGH);
        spiRf->endTransaction();
    }

    void setTx() {
        uint8_t cmd[5] = { 0x02, 0x0D, 0x00, 0x00, 0x00 };
        writeCmd(cmd, 5);
    }

    bool transmit(const uint8_t *data, size_t len, uint32_t timeout = 500000) {
        clearIrq();
        clearTxFifo();
        writeTxFifo(data, len);
        setTx();

        // Wait for TX_DONE (IRQ pin HIGH) or timeout
        while (digitalRead(pin_irq) == LOW && --timeout) {}
        return timeout > 0;
    }

    // ─── RX operations ───────────────────────────────────────────────────
    void clearRxFifo() {
        uint8_t cmd[2] = { 0x01, 0x1E };
        writeCmd(cmd, 2);
    }

    void setRx(uint32_t timeout_ms = 0xFFFFFFFF) {
        if (timeout_ms == 0xFFFFFFFF) {
            uint8_t cmd[5] = { 0x02, 0x0C, 0xFF, 0xFF, 0xFF };
            writeCmd(cmd, 5);
        } else {
            uint8_t cmd[5] = { 0x02, 0x0C,
                (uint8_t)(timeout_ms >> 16),
                (uint8_t)(timeout_ms >> 8),
                (uint8_t)(timeout_ms & 0xFF) };
            writeCmd(cmd, 5);
        }
    }

    void startRX() {
        // Configure IRQ for RX_DONE
        setDioIrq(9, IRQ_RX_DONE);
        delay(1);
        clearIrq();
        clearRxFifo();
        setRx();
    }

    void readRxFifo(uint8_t *buf, size_t len) {
        waitBusy();
        spiRf->beginTransaction(spiSettings);
        digitalWrite(pin_cs, LOW);
        spiRf->transfer(0x00); // READ_RX_FIFO opcode hi
        spiRf->transfer(0x01); // READ_RX_FIFO opcode lo
        for (size_t i = 0; i < len; i++) buf[i] = spiRf->transfer(0x00);
        digitalWrite(pin_cs, HIGH);
        spiRf->endTransaction();
    }

    bool receive(uint8_t *buf, size_t len, uint32_t timeout = 100000) {
        // Wait for IRQ pin HIGH (RX_DONE)
        while (digitalRead(pin_irq) == LOW && --timeout) {}
        if (timeout == 0) return false;

        readRxFifo(buf, len);
        clearRxFifo();
        clearErrors();
        clearIrq();
        setRx(); // re-arm
        return true;
    }

    // ─── RSSI ────────────────────────────────────────────────────────────
    // RSSI is read from GET_RX_STATUS response (0x024B)
    // Returns NEGATED value (proper dBm). Raw register is unsigned positive.
    int8_t getRSSI() {
        waitBusy();
        spiRf->beginTransaction(spiSettings);
        digitalWrite(pin_cs, LOW);
        spiRf->transfer(0x02); // GET_RX_STATUS opcode hi
        spiRf->transfer(0x4B); // GET_RX_STATUS opcode lo
        digitalWrite(pin_cs, HIGH);
        spiRf->endTransaction();
        waitBusy();

        uint8_t buf[8];
        spiRf->beginTransaction(spiSettings);
        digitalWrite(pin_cs, LOW);
        for (int i = 0; i < 8; i++) buf[i] = spiRf->transfer(0x00);
        digitalWrite(pin_cs, HIGH);
        spiRf->endTransaction();

        // RSSI is in byte 3 (offset 4-6 in status response)
        // Format varies — byte 4 of payload after 2 status + 2 padding
        // Based on proven raw firmware: RSSI at offset 3 in response
        uint8_t rssi_raw = buf[3];
        return -(int8_t)rssi_raw; // negate for dBm
    }

    // ─── Helpers ─────────────────────────────────────────────────────────
    static uint8_t bitrateToCode(uint16_t kbps) {
        if (kbps >= 2600) return FLRC_BR_2600;
        if (kbps >= 2080) return FLRC_BR_2080;
        if (kbps >= 1300) return FLRC_BR_1300;
        if (kbps >= 1040) return FLRC_BR_1040;
        if (kbps >= 650)  return FLRC_BR_650;
        if (kbps >= 520)  return FLRC_BR_520;
        if (kbps >= 325)  return FLRC_BR_325;
        return FLRC_BR_260;
    }

    void setSpiClock(uint32_t hz) {
        spiSettings = SPISettings(hz, MSBFIRST, SPI_MODE0);
    }

private:
    SPIClassRP2040 *spiRf = nullptr;
    SPISettings spiSettings = SPISettings(20000000, MSBFIRST, SPI_MODE0); // 20MHz default
};
