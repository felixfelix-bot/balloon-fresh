#include <stdio.h>
#include <string.h>
#include <assert.h>
#include "tdma.h"

static int g_tx_count;
static int g_rx_count;
static uint8_t g_last_tx_slot;
static tdma_band_t g_last_tx_band;
static tdma_band_t g_last_rx_band;
static uint8_t g_last_rx_slot;
static uint16_t g_last_rx_len;

static void tx_cb(uint8_t slot_index, tdma_band_t band) {
    g_tx_count++;
    g_last_tx_slot = slot_index;
    g_last_tx_band = band;
}

static void rx_cb(uint8_t slot_index, tdma_band_t band, const uint8_t *data, uint16_t len) {
    g_rx_count++;
    g_last_rx_slot = slot_index;
    g_last_rx_band = band;
    g_last_rx_len = len;
    (void)data;
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

    printf("TEST 8: dual-band mixed slot callbacks... ");
    tdma_init(2000000, 4);
    tdma_set_slot(0, TDMA_SLOT_BEACON, TDMA_SUBGHZ, 0);
    tdma_set_slot(1, TDMA_SLOT_TX, TDMA_SUBGHZ, 0);
    tdma_set_slot(2, TDMA_SLOT_TX, TDMA_2G4, 0);
    tdma_set_slot(3, TDMA_SLOT_RX, TDMA_2G4, 0);
    g_tx_count = 0;
    tdma_register_tx_callback(tx_cb);
    tdma_start();
    assert(g_tx_count == 1);
    assert(g_last_tx_band == TDMA_SUBGHZ);

    uint32_t sd = 2000000 / 4;
    tdma_tick(sd);
    assert(g_tx_count == 2);
    assert(g_last_tx_slot == 1);
    assert(g_last_tx_band == TDMA_SUBGHZ);

    tdma_tick(sd);
    assert(g_tx_count == 3);
    assert(g_last_tx_slot == 2);
    assert(g_last_tx_band == TDMA_2G4);
    printf("PASS (3 TX callbacks on mixed bands)\n");

    printf("TEST 9: RX slot state tracking (no TX callback)... ");
    g_tx_count = 0;
    g_rx_count = 0;
    tdma_init(2000000, 4);
    tdma_set_slot(0, TDMA_SLOT_SLEEP, TDMA_SUBGHZ, 0);
    tdma_set_slot(1, TDMA_SLOT_RX, TDMA_2G4, 0);
    tdma_set_slot(2, TDMA_SLOT_SLEEP, TDMA_SUBGHZ, 0);
    tdma_set_slot(3, TDMA_SLOT_RX, TDMA_SUBGHZ, 0);
    tdma_register_tx_callback(tx_cb);
    tdma_register_rx_callback(rx_cb);
    tdma_start();
    assert(g_tx_count == 0);

    sd = 2000000 / 4;
    tdma_tick(sd);
    assert(g_tx_count == 0);
    assert(tdma_get_current_slot() == 1);
    assert(tdma_get_slot(1)->type == TDMA_SLOT_RX);
    assert(tdma_get_slot(1)->band == TDMA_2G4);

    tdma_tick(sd);
    assert(tdma_get_current_slot() == 2);

    tdma_tick(sd);
    assert(tdma_get_current_slot() == 3);
    assert(tdma_get_slot(3)->type == TDMA_SLOT_RX);
    assert(tdma_get_slot(3)->band == TDMA_SUBGHZ);
    assert(g_tx_count == 0);
    printf("PASS (RX slots tracked, no TX callbacks)\n");

    printf("TEST 10: contention slot no TX callback... ");
    g_tx_count = 0;
    tdma_init(2000000, 4);
    tdma_set_slot(0, TDMA_SLOT_TX, TDMA_SUBGHZ, 0);
    tdma_set_slot(1, TDMA_SLOT_CONTENTION, TDMA_SUBGHZ, 0);
    tdma_set_slot(2, TDMA_SLOT_TX, TDMA_2G4, 0);
    tdma_set_slot(3, TDMA_SLOT_CONTENTION, TDMA_2G4, 0);
    tdma_register_tx_callback(tx_cb);
    tdma_start();
    assert(g_tx_count == 1);

    sd = 2000000 / 4;
    tdma_tick(sd);
    assert(g_tx_count == 1);
    assert(tdma_get_current_slot() == 1);

    tdma_tick(sd);
    assert(g_tx_count == 2);
    assert(g_last_tx_band == TDMA_2G4);
    printf("PASS (contention slots skip TX callback)\n");

    printf("TEST 11: beacon triggers TX callback every frame... ");
    g_tx_count = 0;
    tdma_init(1000000, 2);
    tdma_set_slot(0, TDMA_SLOT_BEACON, TDMA_SUBGHZ, 0);
    tdma_set_slot(1, TDMA_SLOT_SLEEP, TDMA_SUBGHZ, 0);
    tdma_register_tx_callback(tx_cb);
    tdma_start();
    assert(g_tx_count == 1);
    assert(g_last_tx_slot == 0);

    sd = 1000000 / 2;
    tdma_tick(sd);
    tdma_tick(sd);
    assert(tdma_get_frame_number() == 1);
    assert(g_tx_count == 2);
    assert(g_last_tx_slot == 0);

    tdma_tick(sd);
    tdma_tick(sd);
    assert(tdma_get_frame_number() == 2);
    assert(g_tx_count == 3);
    printf("PASS (beacon fires every frame)\n");

    printf("TEST 12: PPS mid-slot resets time but keeps slot config... ");
    tdma_init(2000000, 4);
    tdma_set_slot(0, TDMA_SLOT_TX, TDMA_SUBGHZ, 0);
    tdma_set_slot(1, TDMA_SLOT_TX, TDMA_2G4, 0);
    tdma_set_slot(2, TDMA_SLOT_RX, TDMA_SUBGHZ, 0);
    tdma_set_slot(3, TDMA_SLOT_SLEEP, TDMA_2G4, 0);

    uint8_t saved_types[4];
    tdma_band_t saved_bands[4];
    for (int i = 0; i < 4; i++) {
        saved_types[i] = tdma_get_slot(i)->type;
        saved_bands[i] = tdma_get_slot(i)->band;
    }

    tdma_start();
    tdma_tick(750000);
    assert(tdma_get_time_in_frame_us() == 750000);
    tdma_pps_pulse();
    assert(tdma_get_time_in_frame_us() == 0);

    for (int i = 0; i < 4; i++) {
        assert(tdma_get_slot(i)->type == saved_types[i]);
        assert(tdma_get_slot(i)->band == saved_bands[i]);
    }
    printf("PASS (PPS resets time, preserves config)\n");

    printf("\n=== Results: 12/12 passed ===\n");
    return 0;
}
