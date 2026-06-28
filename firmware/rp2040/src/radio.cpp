/*
 * radio.cpp — LR2021 driver for RP2040 coprocessor (mbed core) via RadioLib
 *
 * P1.3-FIX: The original radio_init() only reset the chip and set RX mode with
 * ZERO modulation configuration. The radio could never talk to the ESP32
 * tracker. This version uses RadioLib to configure the LR2021 modem
 * byte-identically with the tracker fleet config:
 *
 *   Frequency: 868.0 MHz   Bandwidth: 125 kHz   SF: 9   CR: 4/7
 *   Sync word: 0x12         Preamble: 8 symbols  CRC: 2 bytes (RadioLib default)
 *   TX power:  +22 dBm      TCXO: XTAL (0.0 V = no TCXO)
 *
 * Both RX and TX paths are implemented. The raw-SPI pin self-test is retained
 * for soldering verification (it shares the same MbedSPI bus as RadioLib).
 */

#include <Arduino.h>
#include <SPI.h>
#include <RadioLib.h>
#include "pins.h"
#include "radio.h"

#define SPI_FREQ_HZ  18000000

// ─── Shared SPI bus (mbed MbedSPI) + RadioLib Arduino HAL ──────────────
static MbedSPI spiRf(PIN_SPI_MOSI, PIN_SPI_MISO, PIN_SPI_SCK);
static SPISettings spiSettings(SPI_FREQ_HZ, MSBFIRST, SPI_MODE0);
static ArduinoHal hal(spiRf, spiSettings);

// LR2021 module wiring:
//   cs  = PIN_SPI_CS (NSS)   irq = PIN_IRQ (DIO9)   rst = PIN_RST   gpio = PIN_BUSY
static LR2021 radio = new Module(&hal, PIN_SPI_CS, PIN_IRQ, PIN_RST, PIN_BUSY);

static volatile bool irq_flag = false;
static void on_irq() { irq_flag = true; }

// ─── Low-level SPI helpers (used by the pin self-test only) ────────────
static inline void cs_select()   { digitalWrite(PIN_SPI_CS, LOW); }
static inline void cs_deselect() { digitalWrite(PIN_SPI_CS, HIGH); }

static void spi_write(const uint8_t *buf, size_t len) {
    while (digitalRead(PIN_BUSY) == HIGH) {}
    spiRf.beginTransaction(spiSettings);
    cs_select();
    for (size_t i = 0; i < len; i++) spiRf.transfer(buf[i]);
    cs_deselect();
    spiRf.endTransaction();
}

static void spi_read(const uint8_t *cmd, size_t cmd_len, uint8_t *data, size_t data_len) {
    while (digitalRead(PIN_BUSY) == HIGH) {}
    spiRf.beginTransaction(spiSettings);
    cs_select();
    for (size_t i = 0; i < cmd_len; i++) spiRf.transfer(cmd[i]);
    for (size_t i = 0; i < data_len; i++) data[i] = spiRf.transfer(0x00);
    cs_deselect();
    spiRf.endTransaction();
}

static void read_reg16(uint16_t addr, uint8_t *data, size_t len) {
    uint8_t cmd[3] = {0x01, (uint8_t)(addr >> 8), (uint8_t)(addr & 0xFF)};
    spi_read(cmd, 3, data, len);
}

static uint32_t read_irq_status() {
    uint8_t data[4] = {0};
    read_reg16(0x0086, data, 4);
    return ((uint32_t)data[0] << 24) | ((uint32_t)data[1] << 16) |
           ((uint32_t)data[2] << 8)  | (uint32_t)data[3];
}

// ─── Pin self-test (soldering verification) ───────────────────────────

PinTestResult radio_pin_selftest() {
    PinTestResult r = {};
    snprintf(r.message, sizeof(r.message), "Starting pin self-test...");

    pinMode(PIN_SPI_CS, OUTPUT);
    digitalWrite(PIN_SPI_CS, HIGH);
    delayMicroseconds(10);
    r.spi_cs_ok = (digitalRead(PIN_SPI_CS) == HIGH);

    pinMode(PIN_BUSY, INPUT);
    delayMicroseconds(100);
    r.busy_responds = true;

    pinMode(PIN_RST, OUTPUT);
    digitalWrite(PIN_RST, HIGH);
    delayMicroseconds(100);
    digitalWrite(PIN_RST, LOW);
    delayMicroseconds(200);
    digitalWrite(PIN_RST, HIGH);
    delay(10);

    uint32_t timeout = millis();
    while (digitalRead(PIN_BUSY) == HIGH) {
        if (millis() - timeout > 1000) {
            r.rst_pin_works = false;
            r.errors++;
            strcat(r.message, " BUSY stuck HIGH");
            break;
        }
    }
    if (!r.rst_pin_works) {} else r.rst_pin_works = true;

    spiRf.begin();
    uint32_t irq = read_irq_status();
    if (irq != 0xFFFFFFFF && irq != 0x00000000) {
        r.radio_responds = true;
        r.chip_id = irq;
    } else {
        uint8_t buf[4] = {0};
        read_reg16(0x0100, buf, 4);
        if (buf[0] != 0xFF && buf[0] != 0x00) {
            r.radio_responds = true;
            r.chip_id = buf[0];
        } else {
            r.errors++;
            strcat(r.message, " SPI no response — check wiring");
        }
    }

    pinMode(PIN_IRQ, INPUT_PULLDOWN);
    attachInterrupt(digitalPinToInterrupt(PIN_IRQ), on_irq, RISING);
    delay(10);
    r.irq_pin_works = true;

    if (r.errors == 0) {
        snprintf(r.message, sizeof(r.message),
                 "ALL OK: CS=%d BUSY=%d RST=%d SPI=%d IRQ=%d chipID=0x%08lX",
                 r.spi_cs_ok, r.busy_responds, r.rst_pin_works,
                 r.radio_responds, r.irq_pin_works, (unsigned long)r.chip_id);
    }

    return r;
}

// ─── Public API ──────────────────────────────────────────────────────

int radio_init(int mode) {
    spiRf.begin();

    pinMode(PIN_SPI_CS, OUTPUT);
    digitalWrite(PIN_SPI_CS, HIGH);

    pinMode(PIN_BUSY, INPUT);
    pinMode(PIN_IRQ, INPUT_PULLDOWN);
    attachInterrupt(digitalPinToInterrupt(PIN_IRQ), on_irq, RISING);

    pinMode(PIN_RST, OUTPUT);
    digitalWrite(PIN_RST, HIGH);

    pinMode(PIN_LED, OUTPUT);
    digitalWrite(PIN_LED, LOW);

    // Hardware reset
    delay(10);
    digitalWrite(PIN_RST, LOW);
    delayMicroseconds(200);
    digitalWrite(PIN_RST, HIGH);
    delay(10);

    uint32_t timeout = millis();
    while (digitalRead(PIN_BUSY) == HIGH) {
        if (millis() - timeout > 1000) return -1;
    }

    // RadioLib modem configuration — byte-identical to the ESP32 tracker fleet
    // config (tracker/firmware/main/app_main.cpp): 868 MHz / 125 kHz / SF9 /
    // CR 4-7 / sync 0x12 / +22 dBm / preamble 8 / XTAL (tcxo = 0.0 V).
    radio.irqDioNum = 9;   // route IRQ onto DIO9 (physical wiring)
    int16_t state = radio.begin(868.0, 125.0, 9, 7, 0x12, 22, 8, 0.0f);
    if (state != RADIOLIB_ERR_NONE) {
        return -2;
    }

    irq_flag = false;
    return 0;
}

void radio_start_rx(void)  { radio.startReceive(); }
void radio_standby(void)   { radio.standby(); }
void radio_clear_irq(void) {}

bool radio_poll_irq(void) {
    return (digitalRead(PIN_IRQ) == HIGH);
}

void radio_clear_irq_flag(void) {
    noInterrupts();
    irq_flag = false;
    interrupts();
}

int radio_read_packet(uint8_t *buf, size_t len, PacketTiming *timing) {
    uint32_t t_irq = micros();

    // RadioLib readData pulls the payload from the FIFO and clears the IRQ.
    int16_t state = radio.readData(buf, len);
    uint32_t t1 = micros();
    if (state != RADIOLIB_ERR_NONE) return 0;

    // Re-arm the receiver for the next packet.
    radio.startReceive();
    uint32_t t3 = micros();

    if (timing) {
        timing->irq_to_read = t1 - t_irq;
        timing->read_fifo   = t1 - t_irq;
        timing->clear_irq   = 0;
        timing->restart_rx  = t3 - t1;
        timing->total       = t3 - t_irq;
    }

    return (int)len;
}

int radio_send_packet(const uint8_t *data, size_t len) {
    // Blocking transmit: RadioLib sets TX mode and polls TxDone via SPI.
    int16_t state = radio.transmit(data, len);
    return (state == RADIOLIB_ERR_NONE) ? (int)len : (int)state;
}

float radio_get_rssi(void) {
    return radio.getRSSI();
}
