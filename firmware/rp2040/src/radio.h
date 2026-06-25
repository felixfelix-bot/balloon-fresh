#ifndef LR2021_RP2040_RADIO_H
#define LR2021_RP2040_RADIO_H

#include <stdint.h>
#include <stddef.h>

#define IRQ_RX_DONE          (1UL << 3)
#define MAX_PKT_SIZE         255

struct PacketTiming {
    uint32_t seq;
    uint32_t irq_to_read;
    uint32_t read_fifo;
    uint32_t clear_irq;
    uint32_t restart_rx;
    uint32_t total;
};

struct RadioStats {
    uint32_t received;
    uint32_t unique;
    uint32_t duplicates;
    uint32_t errors;
    uint32_t last_seq;
    uint32_t min_total_us;
    uint32_t max_total_us;
    uint64_t total_us_sum;
};

struct PinTestResult {
    bool spi_cs_ok;
    bool busy_responds;
    bool irq_pin_works;
    bool rst_pin_works;
    bool radio_responds;
    uint32_t chip_id;
    int errors;
    char message[256];
};

int radio_init(int mode);
void radio_start_rx(void);
void radio_standby(void);
int radio_read_packet(uint8_t *buf, size_t len, PacketTiming *timing);
void radio_clear_irq(void);
float radio_get_rssi(void);
bool radio_poll_irq(void);
void radio_clear_irq_flag(void);
PinTestResult radio_pin_selftest(void);

#endif
