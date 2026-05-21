#pragma once

#include <stdint.h>

typedef void (*pipeline_frame_cb)(const uint8_t *frame, uint16_t frame_len, void *user_data);

int pipeline_tx_encode_fragment(
    const uint8_t *data, uint16_t data_len,
    uint8_t frag_payload_size,
    uint8_t redundancy_count,
    pipeline_frame_cb cb,
    void *user_data
);

int pipeline_rx_feed_frame(
    const uint8_t *frame, uint16_t frame_len,
    uint8_t *out_buf, uint16_t *out_len,
    uint16_t out_buf_size
);

void pipeline_rx_reset(void);
void pipeline_rx_set_data_len(uint16_t len);
