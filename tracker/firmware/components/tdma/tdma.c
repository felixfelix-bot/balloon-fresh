#include "tdma.h"
#include <string.h>

static tdma_slot_t s_slots[TDMA_MAX_SLOTS];
static uint8_t s_num_slots;
static uint32_t s_frame_duration;
static uint32_t s_time_in_frame;
static uint32_t s_frame_number;
static tdma_state_t s_state;
static uint8_t s_current_slot;
static bool s_running;
static bool s_pps_received;

static tdma_tx_cb s_tx_cb;
static tdma_rx_cb s_rx_cb;

static uint32_t s_clock_offset;

static void advance_to_slot(uint8_t slot_idx) {
    if (slot_idx >= s_num_slots) return;
    s_current_slot = slot_idx;
    s_state = TDMA_STATE_ACTIVE;

    tdma_slot_t *slot = &s_slots[slot_idx];
    if ((slot->type == TDMA_SLOT_TX || slot->type == TDMA_SLOT_BEACON) && s_tx_cb) {
        s_tx_cb(slot->index, slot->band);
    }
}

void tdma_init(uint32_t frame_duration_us, uint8_t num_slots) {
    memset(s_slots, 0, sizeof(s_slots));
    s_num_slots = (num_slots > TDMA_MAX_SLOTS) ? TDMA_MAX_SLOTS : num_slots;
    s_frame_duration = frame_duration_us;
    s_time_in_frame = 0;
    s_frame_number = 0;
    s_state = TDMA_STATE_IDLE;
    s_current_slot = 0;
    s_running = false;
    s_pps_received = false;
    s_tx_cb = NULL;
    s_rx_cb = NULL;
    s_clock_offset = 0;

    uint32_t slot_duration = frame_duration_us / s_num_slots;
    uint32_t accum = 0;
    for (uint8_t i = 0; i < s_num_slots; i++) {
        s_slots[i].index = i;
        s_slots[i].type = TDMA_SLOT_SLEEP;
        s_slots[i].band = TDMA_SUBGHZ;
        s_slots[i].start_us = accum;
        s_slots[i].duration_us = slot_duration - TDMA_GUARD_US;
        accum += slot_duration;
    }
}

void tdma_set_slot(uint8_t index, tdma_slot_type_t type, tdma_band_t band, uint32_t duration_us) {
    if (index >= s_num_slots) return;
    s_slots[index].type = type;
    s_slots[index].band = band;
    if (duration_us > 0) {
        s_slots[index].duration_us = duration_us;
    }
}

void tdma_register_tx_callback(tdma_tx_cb cb) { s_tx_cb = cb; }
void tdma_register_rx_callback(tdma_rx_cb cb) { s_rx_cb = cb; }

void tdma_start(void) {
    s_running = true;
    s_state = TDMA_STATE_IDLE;
    s_time_in_frame = 0;
    s_frame_number = 0;
    advance_to_slot(0);
}

void tdma_stop(void) {
    s_running = false;
    s_state = TDMA_STATE_IDLE;
}

void tdma_tick(uint32_t elapsed_us) {
    if (!s_running) return;

    s_time_in_frame += elapsed_us;

    if (s_time_in_frame >= s_frame_duration) {
        s_time_in_frame -= s_frame_duration;
        s_frame_number++;
        advance_to_slot(0);
        return;
    }

    uint8_t next_slot = s_current_slot + 1;
    if (next_slot < s_num_slots) {
        if (s_time_in_frame >= s_slots[next_slot].start_us) {
            s_state = TDMA_STATE_DONE;
            advance_to_slot(next_slot);
        }
    }
}

void tdma_pps_pulse(void) {
    s_pps_received = true;
    s_clock_offset = s_time_in_frame;
    s_time_in_frame = 0;
}

uint32_t tdma_get_frame_number(void) { return s_frame_number; }
uint32_t tdma_get_time_in_frame_us(void) { return s_time_in_frame; }
tdma_state_t tdma_get_state(void) { return s_state; }
uint8_t tdma_get_current_slot(void) { return s_current_slot; }
const tdma_slot_t *tdma_get_slot(uint8_t index) {
    if (index >= s_num_slots) return NULL;
    return &s_slots[index];
}
