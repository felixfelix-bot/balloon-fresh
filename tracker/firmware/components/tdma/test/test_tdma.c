#include <stdio.h>
#include <string.h>
#include <assert.h>
#include "tdma.h"

static int g_tx_count;
static int g_rx_count;
static uint8_t g_last_tx_slot;
static tdma_band_t g_last_tx_band;

static void tx_cb(uint8_t slot_index, tdma_band_t band) {
    g_tx_count++;
    g_last_tx_slot = slot_index;
    g_last_tx_band = band;
}

static void rx_cb(uint8_t slot_index, tdma_band_t band, const uint8_t *data, uint16_t len) {
    g_rx_count++;
    (void)slot_index; (void)band; (void)data; (void)len;
}

int main(void) {
    printf("\n=== TDMA Scheduler Tests ===\n\n");

    printf("TEST 1: init and slot configuration... ");
    tdma_init(2000000, 4);
    assert(tdma_get_frame_number() == 0);
    assert(tdma_get_time_in_frame_us() == 0);
    assert(tdma_get_state() == TDMA_STATE_IDLE);
    const tdma_slot_t *s = tdma_get_slot(0);
    assert(s != NULL);
    assert(s->duration_us > 0);
    assert(s->start_us == 0);
    s = tdma_get_slot(3);
    assert(s != NULL);
    assert(s->start_us > 0);
    printf("PASS\n");

    printf("TEST 2: slot type configuration... ");
    tdma_set_slot(0, TDMA_SLOT_BEACON, TDMA_SUBGHZ, 0);
    tdma_set_slot(1, TDMA_SLOT_TX, TDMA_SUBGHZ, 0);
    tdma_set_slot(2, TDMA_SLOT_TX, TDMA_2G4, 0);
    tdma_set_slot(3, TDMA_SLOT_CONTENTION, TDMA_SUBGHZ, 0);
    assert(tdma_get_slot(0)->type == TDMA_SLOT_BEACON);
    assert(tdma_get_slot(1)->type == TDMA_SLOT_TX);
    assert(tdma_get_slot(2)->type == TDMA_SLOT_TX);
    assert(tdma_get_slot(2)->band == TDMA_2G4);
    assert(tdma_get_slot(3)->type == TDMA_SLOT_CONTENTION);
    printf("PASS\n");

    printf("TEST 3: start and tick through one frame... ");
    g_tx_count = 0;
    tdma_register_tx_callback(tx_cb);
    tdma_register_rx_callback(rx_cb);
    tdma_start();
    assert(tdma_get_state() == TDMA_STATE_ACTIVE);
    assert(g_tx_count == 1);
    assert(g_last_tx_slot == 0);

    uint32_t slot_dur = 2000000 / 4;
    tdma_tick(slot_dur);
    assert(tdma_get_current_slot() == 1);
    assert(g_tx_count == 2);

    tdma_tick(slot_dur);
    assert(tdma_get_current_slot() == 2);
    assert(g_tx_count == 3);
    assert(g_last_tx_band == TDMA_2G4);

    tdma_tick(slot_dur);
    assert(tdma_get_current_slot() == 3);
    assert(g_tx_count == 3);

    tdma_tick(slot_dur);
    assert(tdma_get_frame_number() == 1);
    assert(tdma_get_current_slot() == 0);
    assert(g_tx_count == 4);
    printf("PASS (4 slots, 1 full frame)\n");

    printf("TEST 4: guard bands present... ");
    tdma_init(2000000, 4);
    for (uint8_t i = 0; i < 4; i++) {
        const tdma_slot_t *sl = tdma_get_slot(i);
        assert(sl->duration_us < 500000);
    }
    printf("PASS\n");

    printf("TEST 5: PPS discipline resets frame time... ");
    tdma_init(2000000, 4);
    tdma_start();
    tdma_tick(800000);
    assert(tdma_get_time_in_frame_us() == 800000);
    tdma_pps_pulse();
    assert(tdma_get_time_in_frame_us() == 0);
    printf("PASS\n");

    printf("TEST 6: stop halts scheduler... ");
    tdma_init(2000000, 2);
    tdma_start();
    assert(tdma_get_state() == TDMA_STATE_ACTIVE);
    tdma_stop();
    assert(tdma_get_state() == TDMA_STATE_IDLE);
    tdma_tick(500000);
    assert(tdma_get_time_in_frame_us() == 0);
    printf("PASS\n");

    printf("TEST 7: overlap detection (all slots fit in frame)... ");
    tdma_init(1000000, 4);
    uint32_t total = 0;
    for (uint8_t i = 0; i < 4; i++) {
        const tdma_slot_t *sl = tdma_get_slot(i);
        total += sl->duration_us + TDMA_GUARD_US;
    }
    assert(total <= 1000000);
    printf("PASS (total=%u us in 1000000 us frame)\n", total);

    printf("\n=== Results: 7/7 passed ===\n");
    return 0;
}
