#ifndef LR2021_RP2040_RADIO_H
#define LR2021_RP2040_RADIO_H

#include <stdint.h>
#include <stddef.h>
#include "pins.h"

// LR2021 SPI commands (raw register access — bypasses RadioLib per-packet overhead)
// Reference: Semtech LR1121 datasheet, RadioLib LR2021_cmds_*.cpp
#define LR2021_CMD_READ_REGISTER   0x01
#define LR2021_CMD_WRITE_REGISTER  0x01
#define LR2021_CMD_READ_BUFFER     0x02
#define LR2021_CMD_WRITE_BUFFER    0x0D
#define LR2021_CMD_SET_STANDBY     0x01  // + reg 0x0080
#define LR2021_CMD_SET_RX          0x02
#define LR2021_CMD_SET_TX           0x03
#define LR2021_CMD_CLEAR_IRQ       0x01  // + reg 0x0086
#define LR2021_CMD_SET_PACKET_TYPE 0x8A
#define LR2021_CMD_SET_RF_FREQ     0x86

// Key register addresses
#define REG_IRQ_STATUS       0x0086  // 4 bytes
#define REG_RX_BUFFER_PTR    0x0084  // 4 bytes
#define REG_TX_BUFFER_PTR    0x0080
#define REG_PACKET_LENGTH    0x9018  // Current packet length
#define REG_LAST_PKT_PKT_LEN 0x901C
#define REG_SYNC_WORD        0x07C0
#define REG_PKT_ADDR_MASK    0x07C8
#define REG_PKT_ADDR         0x07C6

// IRQ flags
#define IRQ_RX_DONE          (1UL << 3)    // bit 3 of 32-bit IRQ status
#define IRQ_TX_DONE          (1UL << 2)
#define IRQ_RX_ERR           (1UL << 4)
#define IRQ_CRC_ERR          (1UL << 5)
#define IRQ_HEADER_ERR       (1UL << 6)
#define IRQ_PREAMBLE_DET     (1UL << 0)

// Radio modes
#define RADIO_MODE_FLRC_2G4  0   // FLRC 2600 kbps @ 2450 MHz
#define RADIO_MODE_FLRC_868  1   // FLRC 2600 kbps @ 868 MHz
#define RADIO_MODE_LORA_868  2   // LoRa SF7 @ 868 MHz
#define RADIO_MODE_LORA_2G4  3   // LoRa SF7 @ 2450 MHz

// Packet structure (matches TX board firmware: 4-byte seq header + payload)
#define PKT_HEADER_SIZE  4
#define MAX_PKT_SIZE     255

// Per-packet timing measurement
struct PacketTiming {
    uint32_t seq;          // Packet sequence number
    uint32_t irq_to_read;  // µs: IRQ assert → FIFO read start
    uint32_t read_fifo;    // µs: FIFO read duration
    uint32_t clear_irq;    // µs: IRQ clear duration
    uint32_t restart_rx;   // µs: RX restart duration
    uint32_t total;        // µs: IRQ → RX ready for next packet
};

// Statistics
struct RadioStats {
    uint32_t received;     // Total packets received
    uint32_t unique;       // Unique sequence numbers
    uint32_t duplicates;   // Duplicate sequence numbers
    uint32_t errors;       // CRC/header errors
    uint32_t last_seq;     // Last sequence number seen
    uint32_t min_total_us; // Min processing time
    uint32_t max_total_us; // Max processing time
    uint64_t total_us_sum; // Sum of processing times (for average)
};

// Initialize radio (SPI, GPIO, LR2021 config)
// mode: RADIO_MODE_* constant
// Returns 0 on success, negative on error
int radio_init(int mode);

// Start receiving (enter RX mode)
void radio_start_rx(void);

// Read one packet from FIFO (blocking, busy-waits on BUSY pin)
// buf: output buffer (must be >= len bytes)
// len: expected packet length (fixed 255 in speed-test mode)
// timing: filled with per-stage timing data (may be NULL)
// Returns actual bytes read, or 0 if no packet
int radio_read_packet(uint8_t *buf, size_t len, PacketTiming *timing);

// Clear IRQ flags
void radio_clear_irq(void);

// Standby mode
void radio_standby(void);

// Get RSSI of last received packet (dBm)
float radio_get_rssi(void);

// Check if BUSY pin is asserted
static inline bool radio_is_busy(void) {
    return (gpio_get(PIN_BUSY) == 1);
}

// Wait for BUSY to deassert
static inline void radio_wait_busy(void) {
    while (gpio_get(PIN_BUSY) == 1) {
        tight_loop_contents();
    }
}

#endif // LR2021_RP2040_RADIO_H
