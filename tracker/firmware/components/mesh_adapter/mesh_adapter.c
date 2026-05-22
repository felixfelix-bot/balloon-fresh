#include "mesh_adapter.h"
#include "pipeline.h"
#include <string.h>

static mesh_frame_send_fn s_send_fn;
static mesh_frame_queue_t *s_tx_queue;

static void tx_queue_frame(const uint8_t *frame, uint16_t len, void *user_data) {
    (void)user_data;
    if (s_tx_queue && s_tx_queue->frame_count < MESH_ADAPTER_MAX_FRAMES) {
        memcpy(s_tx_queue->frames[s_tx_queue->frame_count], frame, len);
        s_tx_queue->frame_lens[s_tx_queue->frame_count] = len;
        s_tx_queue->frame_count++;
    }
    if (s_send_fn) {
        s_send_fn(frame, len);
    }
}

void mesh_adapter_init(const mesh_adapter_config_t *config) {
    s_send_fn = config->send_fn;
    s_tx_queue = config->tx_queue;
    pipeline_rx_reset();
}

mesh_result_t mesh_adapter_send(const uint8_t *data, uint16_t data_len,
                                uint8_t frag_size, uint8_t redundancy) {
    if (!data || data_len == 0) return MESH_ERR_INVALID_PARAM;

    int n = pipeline_tx_encode_fragment(data, data_len, frag_size, redundancy,
                                        tx_queue_frame, NULL);
    if (n <= 0) return MESH_ERR_FRAGMENT_FAILED;

    return MESH_OK;
}

mesh_result_t mesh_adapter_receive_frame(const uint8_t *frame, uint16_t frame_len,
                                         uint8_t *out_data, uint16_t *out_len,
                                         uint16_t out_size) {
    if (!frame || !out_data || !out_len) return MESH_ERR_INVALID_PARAM;

    int r = pipeline_rx_feed_frame(frame, frame_len, out_data, out_len, out_size);
    if (r == 1) return MESH_OK;
    if (r < 0) return MESH_ERR_REASSEMBLE_FAILED;

    return MESH_ERR_REASSEMBLE_FAILED;
}

void mesh_adapter_set_fips_sessions(void *init_sess, void *resp_sess) {
    (void)init_sess;
    (void)resp_sess;
}

void mesh_adapter_reset(void) {
    pipeline_rx_reset();
    if (s_tx_queue) {
        s_tx_queue->frame_count = 0;
        memset(s_tx_queue->frames, 0, sizeof(s_tx_queue->frames));
        memset(s_tx_queue->frame_lens, 0, sizeof(s_tx_queue->frame_lens));
    }
}

int mesh_adapter_get_pending_frame_count(void) {
    return s_tx_queue ? s_tx_queue->frame_count : 0;
}
