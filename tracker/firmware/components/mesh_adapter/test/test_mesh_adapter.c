#include <stdio.h>
#include <string.h>
#include <assert.h>
#include "mesh_adapter.h"
#include "pipeline.h"

static int g_send_count;
static uint8_t g_last_sent[256];
static uint16_t g_last_sent_len;

static void mock_send(const uint8_t *frame, uint16_t len) {
    g_send_count++;
    memcpy(g_last_sent, frame, len);
    g_last_sent_len = len;
}

static mesh_frame_queue_t g_queue;

static void reset(void) {
    g_send_count = 0;
    memset(&g_queue, 0, sizeof(g_queue));
    mesh_adapter_reset();
}

int main(void) {
    printf("\n=== Mesh Adapter Tests ===\n\n");

    mesh_adapter_config_t config = {
        .send_fn = mock_send,
        .tx_queue = &g_queue,
    };
    mesh_adapter_init(&config);

    printf("TEST 1: send data produces frames... ");
    reset();
    uint8_t data[100];
    for (int i = 0; i < 100; i++) data[i] = i;
    mesh_result_t r = mesh_adapter_send(data, 100, 50, 1);
    assert(r == MESH_OK);
    assert(g_queue.frame_count > 0);
    assert(g_send_count == g_queue.frame_count);
    printf("PASS (%d frames)\n", g_queue.frame_count);

    printf("TEST 2: receive and reassemble... ");
    reset();
    uint8_t payload[200];
    for (int i = 0; i < 200; i++) payload[i] = i & 0xFF;

    r = mesh_adapter_send(payload, 200, 80, 0);
    assert(r == MESH_OK);
    int n = g_queue.frame_count;

    uint8_t saved_frames[MESH_ADAPTER_MAX_FRAMES][256];
    uint16_t saved_lens[MESH_ADAPTER_MAX_FRAMES];
    memcpy(saved_frames, g_queue.frames, sizeof(g_queue.frames));
    memcpy(saved_lens, g_queue.frame_lens, sizeof(g_queue.frame_lens));

    pipeline_rx_reset();
    pipeline_rx_set_data_len(200);

    uint8_t out[512];
    uint16_t out_len = 0;
    int decoded = 0;
    for (int i = 0; i < n; i++) {
        r = mesh_adapter_receive_frame(saved_frames[i], saved_lens[i],
                                       out, &out_len, sizeof(out));
        if (r == MESH_OK) { decoded = 1; break; }
    }
    assert(decoded);
    assert(out_len == 200);
    assert(memcmp(payload, out, 200) == 0);
    printf("PASS\n");

    printf("TEST 3: invalid params rejected... ");
    reset();
    r = mesh_adapter_send(NULL, 100, 50, 0);
    assert(r == MESH_ERR_INVALID_PARAM);
    r = mesh_adapter_send(data, 0, 50, 0);
    assert(r == MESH_ERR_INVALID_PARAM);
    r = mesh_adapter_receive_frame(NULL, 10, out, &out_len, sizeof(out));
    assert(r == MESH_ERR_INVALID_PARAM);
    r = mesh_adapter_receive_frame(data, 10, NULL, &out_len, sizeof(out));
    assert(r == MESH_ERR_INVALID_PARAM);
    printf("PASS\n");

    printf("TEST 4: send callback invoked for each frame... ");
    reset();
    g_send_count = 0;
    uint8_t small[30];
    memset(small, 0xAB, 30);
    r = mesh_adapter_send(small, 30, 80, 0);
    assert(r == MESH_OK);
    assert(g_send_count == g_queue.frame_count);
    assert(g_send_count >= 1);
    printf("PASS (%d callbacks)\n", g_send_count);

    printf("TEST 5: reset clears state... ");
    reset();
    mesh_adapter_send(data, 100, 50, 0);
    assert(g_queue.frame_count > 0);
    mesh_adapter_reset();
    assert(g_queue.frame_count == 0);
    assert(mesh_adapter_get_pending_frame_count() == 0);
    printf("PASS\n");

    printf("TEST 6: telemetry-sized payload (28B)... ");
    reset();
    uint8_t telemetry[28];
    for (int i = 0; i < 28; i++) telemetry[i] = i;

    r = mesh_adapter_send(telemetry, 28, 80, 0);
    assert(r == MESH_OK);
    n = g_queue.frame_count;

    uint8_t saved6[MESH_ADAPTER_MAX_FRAMES][256];
    uint16_t saved6_lens[MESH_ADAPTER_MAX_FRAMES];
    memcpy(saved6, g_queue.frames, sizeof(g_queue.frames));
    memcpy(saved6_lens, g_queue.frame_lens, sizeof(g_queue.frame_lens));

    pipeline_rx_reset();
    pipeline_rx_set_data_len(28);

    decoded = 0;
    out_len = 0;
    for (int i = 0; i < n; i++) {
        r = mesh_adapter_receive_frame(saved6[i], saved6_lens[i],
                                       out, &out_len, sizeof(out));
        if (r == MESH_OK) { decoded = 1; break; }
    }
    assert(decoded);
    assert(out_len == 28);
    assert(memcmp(telemetry, out, 28) == 0);
    printf("PASS\n");

    printf("TEST 7: out-of-order reassembly... ");
    reset();
    uint8_t ooo_data[300];
    for (int i = 0; i < 300; i++) ooo_data[i] = i & 0xFF;

    r = mesh_adapter_send(ooo_data, 300, 80, 0);
    assert(r == MESH_OK);
    n = g_queue.frame_count;

    uint8_t saved7[MESH_ADAPTER_MAX_FRAMES][256];
    uint16_t saved7_lens[MESH_ADAPTER_MAX_FRAMES];
    memcpy(saved7, g_queue.frames, sizeof(g_queue.frames));
    memcpy(saved7_lens, g_queue.frame_lens, sizeof(g_queue.frame_lens));

    pipeline_rx_reset();
    pipeline_rx_set_data_len(300);

    decoded = 0;
    out_len = 0;
    int order[] = {n - 1, 0, 1, 2, 3};
    for (int i = 0; i < 5 && i < n; i++) {
        r = mesh_adapter_receive_frame(saved7[order[i]], saved7_lens[order[i]],
                                       out, &out_len, sizeof(out));
        if (r == MESH_OK) { decoded = 1; break; }
    }
    assert(decoded);
    assert(out_len == 300);
    assert(memcmp(ooo_data, out, 300) == 0);
    printf("PASS\n");

    printf("TEST 8: pending frame count tracking... ");
    reset();
    assert(mesh_adapter_get_pending_frame_count() == 0);
    mesh_adapter_send(data, 100, 30, 0);
    int count1 = mesh_adapter_get_pending_frame_count();
    assert(count1 > 0);
    mesh_adapter_send(data, 100, 30, 0);
    int count2 = mesh_adapter_get_pending_frame_count();
    assert(count2 >= count1);
    printf("PASS (%d then %d frames)\n", count1, count2);

    printf("\n=== Results: 8/8 passed ===\n");
    return 0;
}
