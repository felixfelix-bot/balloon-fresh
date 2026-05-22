#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <assert.h>

#include "mesh_adapter.h"
#include "pipeline.h"
#include "telemetry.h"

static uint8_t s_radio_frames[64][256];
static uint16_t s_radio_frame_lens[64];
static int s_radio_frame_count = 0;

static void radio_send_fn(const uint8_t *frame, uint16_t len) {
    if (s_radio_frame_count < 64) {
        memcpy(s_radio_frames[s_radio_frame_count], frame, len);
        s_radio_frame_lens[s_radio_frame_count] = len;
        s_radio_frame_count++;
    }
}

static void reset_radio(void) {
    s_radio_frame_count = 0;
    memset(s_radio_frames, 0, sizeof(s_radio_frames));
    memset(s_radio_frame_lens, 0, sizeof(s_radio_frame_lens));
}

static mesh_frame_queue_t s_e2e_tx_queue;

static void setup_adapter(void) {
    reset_radio();
    mesh_adapter_reset();
    memset(&s_e2e_tx_queue, 0, sizeof(s_e2e_tx_queue));

    mesh_adapter_config_t config = {
        .send_fn = radio_send_fn,
        .tx_queue = &s_e2e_tx_queue,
    };
    mesh_adapter_init(&config);
}

static void test_e2e_lossless_telemetry(void) {
    setup_adapter();

    telemetry_packet_t pkt;
    memset(&pkt, 0, sizeof(pkt));
    pkt.callsign_hash = 0x424C4E00;
    pkt.seq = 42;
    pkt.latitude_deg1e5 = 5250000;
    pkt.longitude_deg1e5 = 1320000;
    pkt.altitude_m = 12000;
    pkt.voltage_mv = 4100;
    telemetry_fill(&pkt, 25.0f, 1013.0f, 12000.0f, 4100, 42);

    uint8_t buf[TELEMETRY_SIZE];
    telemetry_serialize(&pkt, buf);

    mesh_result_t result = mesh_adapter_send(buf, TELEMETRY_SIZE, 50, 4);
    assert(result == MESH_OK);
    assert(s_radio_frame_count > 0);

    uint8_t rx_buf[512];
    uint16_t rx_len = 0;
    bool recovered = false;

    for (int i = 0; i < s_radio_frame_count; i++) {
        mesh_result_t r = mesh_adapter_receive_frame(
            s_radio_frames[i], s_radio_frame_lens[i],
            rx_buf, &rx_len, sizeof(rx_buf));
        if (r == MESH_OK) {
            recovered = true;
            break;
        }
    }

    assert(recovered);
    assert(rx_len >= TELEMETRY_SIZE);
    assert(memcmp(buf, rx_buf, TELEMETRY_SIZE) == 0);
    printf("PASS (%d frames TX, recovered %d bytes)\n", s_radio_frame_count, rx_len);
}

static void test_e2e_with_loss(void) {
    setup_adapter();

    uint8_t payload[200];
    for (int i = 0; i < 200; i++) payload[i] = (uint8_t)(i * 7 + 3);

    mesh_result_t result = mesh_adapter_send(payload, sizeof(payload), 50, 16);
    assert(result == MESH_OK);
    int total_frames = s_radio_frame_count;
    assert(total_frames > 4);

    uint8_t saved[64][256];
    uint16_t saved_lens[64];
    memcpy(saved, s_radio_frames, sizeof(saved));
    memcpy(saved_lens, s_radio_frame_lens, sizeof(saved_lens));

    mesh_adapter_reset();
    s_radio_frame_count = 0;

    uint8_t rx_buf[512];
    uint16_t rx_len = 0;
    bool recovered = false;
    int skip_count = 0;

    for (int i = 0; i < total_frames; i++) {
        if (i >= 4 && i < total_frames - 4 && (i % 5 == 0)) {
            skip_count++;
            continue;
        }
        mesh_result_t r = mesh_adapter_receive_frame(
            saved[i], saved_lens[i],
            rx_buf, &rx_len, sizeof(rx_buf));
        if (r == MESH_OK) {
            recovered = true;
            break;
        }
    }

    assert(recovered);
    assert(rx_len == sizeof(payload));
    assert(memcmp(payload, rx_buf, sizeof(payload)) == 0);
    printf("PASS (dropped %d/%d, recovered %d bytes)\n", skip_count, total_frames, rx_len);
}

static void test_e2e_out_of_order(void) {
    setup_adapter();

    uint8_t payload[200];
    for (int i = 0; i < 200; i++) payload[i] = (uint8_t)(i ^ 0xAA);

    mesh_result_t result = mesh_adapter_send(payload, sizeof(payload), 50, 0);
    assert(result == MESH_OK);

    uint8_t saved[64][256];
    uint16_t saved_lens[64];
    int n = s_radio_frame_count;
    memcpy(saved, s_radio_frames, sizeof(saved));
    memcpy(saved_lens, s_radio_frame_lens, sizeof(saved_lens));

    mesh_adapter_reset();
    s_radio_frame_count = 0;

    int order[64];
    for (int i = 0; i < n && i < 64; i++) order[i] = i;
    for (int i = n - 1; i > 0; i--) {
        int j = i * 7 % (i + 1);
        int tmp = order[i]; order[i] = order[j]; order[j] = tmp;
    }

    uint8_t rx_buf[512];
    uint16_t rx_len = 0;
    bool recovered = false;

    for (int k = 0; k < n; k++) {
        int idx = order[k];
        mesh_result_t r = mesh_adapter_receive_frame(
            saved[idx], saved_lens[idx],
            rx_buf, &rx_len, sizeof(rx_buf));
        if (r == MESH_OK) {
            recovered = true;
            break;
        }
    }

    assert(recovered);
    assert(rx_len == sizeof(payload));
    assert(memcmp(payload, rx_buf, sizeof(payload)) == 0);
    printf("PASS (%d frames out-of-order, recovered)\n", n);
}

static void test_e2e_small_single_frame(void) {
    setup_adapter();

    uint8_t payload[10] = {0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A};

    mesh_result_t result = mesh_adapter_send(payload, sizeof(payload), 50, 2);
    assert(result == MESH_OK);

    uint8_t rx_buf[512];
    uint16_t rx_len = 0;
    bool recovered = false;

    for (int i = 0; i < s_radio_frame_count; i++) {
        mesh_result_t r = mesh_adapter_receive_frame(
            s_radio_frames[i], s_radio_frame_lens[i],
            rx_buf, &rx_len, sizeof(rx_buf));
        if (r == MESH_OK) {
            recovered = true;
            break;
        }
    }

    assert(recovered);
    assert(rx_len >= sizeof(payload));
    assert(memcmp(payload, rx_buf, sizeof(payload)) == 0);
    printf("PASS (%d frames for %d-byte payload)\n", s_radio_frame_count, (int)sizeof(payload));
}

int main(void) {
    printf("\n=== End-to-End Integration Tests ===\n\n");

    printf("TEST 1: Lossless telemetry roundtrip... ");
    test_e2e_lossless_telemetry();

    printf("TEST 2: With frame loss recovery... ");
    test_e2e_with_loss();

    printf("TEST 3: Out-of-order delivery... ");
    test_e2e_out_of_order();

    printf("TEST 4: Small single-frame payload... ");
    test_e2e_small_single_frame();

    printf("\n=== Results: 4/4 passed ===\n");
    return 0;
}
