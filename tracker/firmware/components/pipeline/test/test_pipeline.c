#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include "pipeline.h"

#define MAX_FRAMES 128
static uint8_t g_frames[MAX_FRAMES][256];
static uint16_t g_frame_lens[MAX_FRAMES];
static int g_frame_count;

static void collect_frame(const uint8_t *frame, uint16_t len, void *user_data) {
    (void)user_data;
    assert(g_frame_count < MAX_FRAMES);
    memcpy(g_frames[g_frame_count], frame, len);
    g_frame_lens[g_frame_count] = len;
    g_frame_count++;
}

static void reset_frames(void) {
    g_frame_count = 0;
    memset(g_frames, 0, sizeof(g_frames));
    memset(g_frame_lens, 0, sizeof(g_frame_lens));
}

int main(void) {
    printf("\n=== Pipeline Integration Tests ===\n\n");

    printf("TEST 1: happy path - encode 200B, feed all frames, decode... ");
    reset_frames();
    pipeline_rx_reset();
    pipeline_rx_set_data_len(200);

    uint8_t data[200];
    for (int i = 0; i < 200; i++) data[i] = i & 0xFF;

    int n = pipeline_tx_encode_fragment(data, 200, 80, 2, collect_frame, NULL);
    assert(n > 0);

    uint8_t out[512];
    uint16_t out_len = 0;
    int decoded = 0;
    for (int i = 0; i < n; i++) {
        int r = pipeline_rx_feed_frame(g_frames[i], g_frame_lens[i], out, &out_len, sizeof(out));
        if (r == 1) { decoded = 1; break; }
    }
    assert(decoded);
    assert(out_len == 200);
    assert(memcmp(data, out, 200) == 0);
    printf("PASS (%d frames)\n", n);

    printf("TEST 2: original-only (no redundancy)... ");
    reset_frames();
    pipeline_rx_reset();
    pipeline_rx_set_data_len(200);

    n = pipeline_tx_encode_fragment(data, 200, 80, 0, collect_frame, NULL);
    assert(n > 0);

    decoded = 0;
    out_len = 0;
    for (int i = 0; i < n; i++) {
        int r = pipeline_rx_feed_frame(g_frames[i], g_frame_lens[i], out, &out_len, sizeof(out));
        if (r == 1) { decoded = 1; break; }
    }
    assert(decoded);
    assert(memcmp(data, out, 200) == 0);
    printf("PASS (%d frames)\n", n);

    printf("TEST 3: small payload (28B telemetry, single frame)... ");
    reset_frames();
    pipeline_rx_reset();
    pipeline_rx_set_data_len(28);

    uint8_t telemetry[28];
    for (int i = 0; i < 28; i++) telemetry[i] = i;

    n = pipeline_tx_encode_fragment(telemetry, 28, 80, 1, collect_frame, NULL);
    assert(n > 0);

    decoded = 0;
    out_len = 0;
    for (int i = 0; i < n; i++) {
        int r = pipeline_rx_feed_frame(g_frames[i], g_frame_lens[i], out, &out_len, sizeof(out));
        if (r == 1) { decoded = 1; break; }
    }
    assert(decoded);
    assert(memcmp(telemetry, out, 28) == 0);
    printf("PASS (%d frames)\n", n);

    printf("TEST 4: large payload (500B, multiple fragments)... ");
    reset_frames();
    pipeline_rx_reset();
    pipeline_rx_set_data_len(500);

    uint8_t big[500];
    for (int i = 0; i < 500; i++) big[i] = i & 0xFF;

    n = pipeline_tx_encode_fragment(big, 500, 80, 3, collect_frame, NULL);
    assert(n > 0);

    decoded = 0;
    out_len = 0;
    for (int i = 0; i < n; i++) {
        int r = pipeline_rx_feed_frame(g_frames[i], g_frame_lens[i], out, &out_len, sizeof(out));
        if (r == 1) { decoded = 1; break; }
    }
    assert(decoded);
    assert(out_len == 500);
    assert(memcmp(big, out, 500) == 0);
    printf("PASS (%d frames)\n", n);

    printf("TEST 5: out-of-order delivery... ");
    reset_frames();
    pipeline_rx_reset();
    pipeline_rx_set_data_len(200);

    n = pipeline_tx_encode_fragment(data, 200, 80, 0, collect_frame, NULL);
    assert(n == 3);

    decoded = 0;
    out_len = 0;
    int order[] = {2, 0, 1};
    for (int i = 0; i < 3; i++) {
        int r = pipeline_rx_feed_frame(g_frames[order[i]], g_frame_lens[order[i]], out, &out_len, sizeof(out));
        if (r == 1) { decoded = 1; break; }
    }
    assert(decoded);
    assert(memcmp(data, out, 200) == 0);
    printf("PASS (received order: 2,0,1)\n");

    printf("\n=== Results: 5/5 passed ===\n");
    printf("\nNOTE: Loss recovery requires erasure decoder integration\n");
    printf("(separate from frag reassembler - needs decoder state machine)\n");
    return 0;
}
