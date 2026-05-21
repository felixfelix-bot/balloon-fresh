#pragma once

#include <stdint.h>
#include <stdbool.h>

typedef enum { TDMA_SUBGHZ, TDMA_2G4 } tdma_band_t;
typedef enum {
    TDMA_SLOT_TX,
    TDMA_SLOT_RX,
    TDMA_SLOT_SLEEP,
    TDMA_SLOT_BEACON,
    TDMA_SLOT_CONTENTION
} tdma_slot_type_t;

typedef struct {
    uint8_t index;
    tdma_slot_type_t type;
    tdma_band_t band;
    uint32_t start_us;
    uint32_t duration_us;
} tdma_slot_t;

typedef enum {
    TDMA_STATE_IDLE,
    TDMA_STATE_WAITING,
    TDMA_STATE_ACTIVE,
    TDMA_STATE_DONE
} tdma_state_t;

typedef void (*tdma_tx_cb)(uint8_t slot_index, tdma_band_t band);
typedef void (*tdma_rx_cb)(uint8_t slot_index, tdma_band_t band, const uint8_t *data, uint16_t len);

#define TDMA_MAX_SLOTS 8
#define TDMA_DEFAULT_FRAME_US 2000000
#define TDMA_GUARD_US 200

void tdma_init(uint32_t frame_duration_us, uint8_t num_slots);
void tdma_set_slot(uint8_t index, tdma_slot_type_t type, tdma_band_t band, uint32_t duration_us);
void tdma_register_tx_callback(tdma_tx_cb cb);
void tdma_register_rx_callback(tdma_rx_cb cb);
void tdma_start(void);
void tdma_stop(void);
void tdma_tick(uint32_t elapsed_us);
void tdma_pps_pulse(void);
uint32_t tdma_get_frame_number(void);
uint32_t tdma_get_time_in_frame_us(void);
tdma_state_t tdma_get_state(void);
uint8_t tdma_get_current_slot(void);
const tdma_slot_t *tdma_get_slot(uint8_t index);
