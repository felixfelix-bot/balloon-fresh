/*
 * radio.cpp — LR2021 raw SPI driver for RP2040 coprocessor
 *
 * Bypasses RadioLib per-packet overhead by using direct SPI register commands.
 * Mirrors the approach in flrc-bench-espidf/main/fast_rx.cpp but for Pico SDK.
 *
 * The RP2040's SPI0 peripheral runs at up to 62.5 MHz (clk_sys / 2),
 * far exceeding the ESP32-C3's 10.46 Mbps measured SPI throughput.
 */

#include <Arduino.h>
#include <hardware/spi.h>
#include <hardware/gpio.h>
#include <hardware/irq.h>
#include <hardware/clocks.h>
#include "pins.h"
#include "radio.h"

// SPI clock: 31.25 MHz (clk_sys 125 MHz / 4)
// LR2021 max SPI clock is 27 MHz per datasheet, but 18 MHz is safe.
#define SPI_FREQ_HZ  18000000  // 18 MHz — safe for all LR2021 variants

static spi_inst_t *spi = spi0;
static volatile bool irq_flag = false;
static int current_mode = RADIO_MODE_FLRC_2G4;

// ─── Low-level SPI helpers ───────────────────────────────────────────

static inline void cs_select() {
    asm volatile("nop \n nop \n nop");
    gpio_put(PIN_SPI_CS, 0);
    asm volatile("nop \n nop \n nop");
}

static inline void cs_deselect() {
    asm volatile("nop \n nop \n nop");
    gpio_put(PIN_SPI_CS, 1);
    asm volatile("nop \n nop \n nop");
}

static void spi_write(const uint8_t *buf, size_t len) {
    radio_wait_busy();
    cs_select();
    spi_write_blocking(spi, buf, len);
    cs_deselect();
}

static void spi_read(const uint8_t *cmd, size_t cmd_len, uint8_t *data, size_t data_len) {
    radio_wait_busy();
    cs_select();
    spi_write_blocking(spi, cmd, cmd_len);
    spi_read_blocking(spi, 0x00, data, data_len);
    cs_deselect();
}

// Write a single byte to a 16-bit register address
static void write_reg16(uint16_t addr, uint8_t value) {
    uint8_t cmd[4] = {
        LR2021_CMD_WRITE_REGISTER,
        (uint8_t)(addr >> 8),
        (uint8_t)(addr & 0xFF),
        value
    };
    spi_write(cmd, 4);
}

// Read N bytes from a 16-bit register address
static void read_reg16(uint16_t addr, uint8_t *data, size_t len) {
    uint8_t cmd[3] = {
        LR2021_CMD_READ_REGISTER,
        (uint8_t)(addr >> 8),
        (uint8_t)(addr & 0xFF)
    };
    spi_read(cmd, 3, data, len);
}

// ─── Raw LR2021 commands (matching fast_rx.cpp patterns) ─────────────

static void raw_set_rx() {
    // Set RX with infinite timeout
    uint8_t cmd[] = {LR2021_CMD_SET_RX, 0x0C, 0x00, 0xFF, 0xFF, 0xFF};
    spi_write(cmd, 6);
}

static void raw_set_standby() {
    // Standby config: RC 13 MHz
    uint8_t cmd[] = {LR2021_CMD_SET_STANDBY, 0x28, 0x00};
    spi_write(cmd, 3);
}

static void raw_clear_irq() {
    // Clear all IRQ flags
    uint8_t cmd[] = {LR2021_CMD_CLEAR_IRQ, 0x16, 0xFF, 0xFF, 0xFF, 0xFF};
    spi_write(cmd, 6);
}

static void raw_read_fifo(uint8_t *buf, size_t len) {
    // Read from RX buffer at offset 0
    uint8_t cmd[] = {LR2021_CMD_READ_BUFFER, 0x00, 0x00};
    spi_read(cmd, 3, buf, len);
}

static uint32_t read_irq_status() {
    uint8_t data[4];
    read_reg16(REG_IRQ_STATUS, data, 4);
    return ((uint32_t)data[0] << 24) | ((uint32_t)data[1] << 16) |
           ((uint32_t)data[2] << 8)  | (uint32_t)data[3];
}

// ─── IRQ handler ─────────────────────────────────────────────────────

static void gpio_irq_callback(uint gpio, uint32_t events) {
    if (gpio == PIN_IRQ) {
        irq_flag = true;
    }
}

// ─── Public API ──────────────────────────────────────────────────────

int radio_init(int mode) {
    current_mode = mode;

    // Initialize SPI0 pins
    spi_init(spi, SPI_FREQ_HZ);
    spi_set_format(spi, 8, SPI_CPOL_0, SPI_CPHA_0, SPI_MSB_FIRST);

    gpio_set_function(PIN_SPI_SCK, GPIO_FUNC_SPI);
    gpio_set_function(PIN_SPI_MOSI, GPIO_FUNC_SPI);
    gpio_set_function(PIN_SPI_MISO, GPIO_FUNC_SPI);

    // CS pin (manual control)
    gpio_init(PIN_SPI_CS);
    gpio_set_dir(PIN_SPI_CS, GPIO_OUT);
    gpio_put(PIN_SPI_CS, 1);  // Deselect

    // BUSY pin (input)
    gpio_init(PIN_BUSY);
    gpio_set_dir(PIN_BUSY, GPIO_IN);

    // IRQ pin (input + interrupt on rising edge)
    gpio_init(PIN_IRQ);
    gpio_set_dir(PIN_IRQ, GPIO_IN);
    gpio_pull_down(PIN_IRQ);
    gpio_set_irq_enabled_with_callback(PIN_IRQ, GPIO_IRQ_EDGE_RISE, true,
                                        &gpio_irq_callback);

    // RST pin (output, hold high = not reset)
    gpio_init(PIN_RST);
    gpio_set_dir(PIN_RST, GPIO_OUT);
    gpio_put(PIN_RST, 1);

    // LED pin
    gpio_init(PIN_LED);
    gpio_set_dir(PIN_LED, GPIO_OUT);
    gpio_put(PIN_LED, 0);

    // Hardware reset the radio
    delay(10);
    gpio_put(PIN_RST, 0);
    delayMicroseconds(150);  // Min 100µs reset pulse
    gpio_put(PIN_RST, 1);
    delay(10);

    // Wait for BUSY to deassert
    radio_wait_busy();

    irq_flag = false;
    return 0;
}

void radio_start_rx(void) {
    raw_set_rx();
}

void radio_standby(void) {
    raw_set_standby();
}

void radio_clear_irq(void) {
    raw_clear_irq();
}

bool radio_irq_pending(void) {
    // Disable interrupts briefly for atomic read
    uint32_t save = save_and_disable_interrupts();
    bool flag = irq_flag;
    irq_flag = false;
    restore_interrupts(save);
    return flag;
}

int radio_read_packet(uint8_t *buf, size_t len, PacketTiming *timing) {
    uint32_t t_irq = micros();

    // Check IRQ is actually set (RxRxDone)
    uint32_t irq = read_irq_status();
    if (!(irq & IRQ_RX_DONE)) {
        return 0;
    }

    // Read FIFO
    uint32_t t0 = micros();
    raw_read_fifo(buf, len);
    uint32_t t1 = micros();

    // Clear IRQ
    raw_clear_irq();
    uint32_t t2 = micros();

    // Restart RX
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
    // Read RSSI register: 0x0AAB (signed 8-bit, dBm)
    uint8_t rssi_raw;
    read_reg16(0x0AAB, &rssi_raw, 1);
    return (float)(int8_t)rssi_raw / -2.0f;  // Scale: value / -2 = dBm
}

// Polling fallback: check IRQ pin directly (for tight inner loop without ISRs)
bool radio_poll_irq(void) {
    return (gpio_get(PIN_IRQ) == 1);
}

void radio_clear_irq_flag(void) {
    uint32_t save = save_and_disable_interrupts();
    irq_flag = false;
    restore_interrupts(save);
}
