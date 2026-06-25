/*
 * radio.cpp — LR2021 SPI driver for RP2040 coprocessor (mbed core)
 */

#include <Arduino.h>
#include <SPI.h>
#include "pins.h"
#include "radio.h"

#define SPI_FREQ_HZ  18000000

static MbedSPI spiRf(PIN_SPI_MOSI, PIN_SPI_MISO, PIN_SPI_SCK);
static SPISettings spiSettings(SPI_FREQ_HZ, MSBFIRST, SPI_MODE0);
static volatile bool irq_flag = false;

static void on_irq();
static inline void cs_select() { digitalWrite(PIN_SPI_CS, LOW); }
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

static void raw_set_rx() {
    uint8_t cmd[] = {0x02, 0x0C, 0x00, 0xFF, 0xFF, 0xFF};
    spi_write(cmd, 6);
}

static void raw_clear_irq() {
    uint8_t cmd[] = {0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF};
    spi_write(cmd, 6);
}

static void raw_read_fifo(uint8_t *buf, size_t len) {
    uint8_t cmd[] = {0x02, 0x00, 0x00};
    spi_read(cmd, 3, buf, len);
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

static void on_irq() {
    irq_flag = true;
}

// ─── Pin self-test ───────────────────────────────────────────────────

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

    delay(10);
    digitalWrite(PIN_RST, LOW);
    delayMicroseconds(200);
    digitalWrite(PIN_RST, HIGH);
    delay(10);

    uint32_t timeout = millis();
    while (digitalRead(PIN_BUSY) == HIGH) {
        if (millis() - timeout > 1000) return -1;
    }

    irq_flag = false;
    return 0;
}

void radio_start_rx(void) { raw_set_rx(); }
void radio_standby(void)  {}
void radio_clear_irq(void) { raw_clear_irq(); }

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

    uint32_t irq = read_irq_status();
    if (!(irq & IRQ_RX_DONE)) return 0;

    uint32_t t0 = micros();
    raw_read_fifo(buf, len);
    uint32_t t1 = micros();
    raw_clear_irq();
    uint32_t t2 = micros();
    raw_set_rx();
    uint32_t t3 = micros();

    if (timing) {
        timing->irq_to_read = t0 - t_irq;
        timing->read_fifo   = t1 - t0;
        timing->clear_irq   = t2 - t1;
        timing->restart_rx  = t3 - t2;
        timing->total       = t3 - t_irq;
    }

    return (int)len;
}

float radio_get_rssi(void) {
    uint8_t rssi_raw;
    read_reg16(0x0AAB, &rssi_raw, 1);
    return (float)(int8_t)rssi_raw / -2.0f;
}
