#include "pipeline.h"
#include "erasure.h"
#include "frag.h"
#include <string.h>

#define PIPELINE_MAX_FRAGS 64
#define PIPELINE_MAX_FRAG_SIZE 242

static uint8_t s_enc_buf[PIPELINE_MAX_FRAG_SIZE * (PIPELINE_MAX_FRAGS + 32)];

static uint8_t s_ra_buf[(PIPELINE_MAX_FRAG_SIZE * PIPELINE_MAX_FRAGS) +
                        (PIPELINE_MAX_FRAG_SIZE * 32)];
static uint8_t s_matrix_buf[PIPELINE_MAX_FRAGS * PIPELINE_MAX_FRAGS];
static frag_reassembler_t s_ra;
static erasure_decoder_t s_dec;
static bool s_ra_inited;
static bool s_dec_inited;
static uint16_t s_rx_data_len;
static bool s_rx_data_len_known;

static uint16_t s_original_data_len;
static bool s_original_data_len_set;

int pipeline_tx_encode_fragment(
    const uint8_t *data, uint16_t data_len,
    uint8_t frag_payload_size,
    uint8_t redundancy_count,
    pipeline_frame_cb cb,
    void *user_data
) {
    if (!data || !cb || frag_payload_size == 0 || frag_payload_size > PIPELINE_MAX_FRAG_SIZE)
        return -1;

    uint16_t num_frags = (data_len + frag_payload_size - 1) / frag_payload_size;
    if (num_frags > PIPELINE_MAX_FRAGS)
        return -1;

    uint32_t padded_len = (uint32_t)num_frags * frag_payload_size;
    if (padded_len > sizeof(s_enc_buf))
        return -1;
    memset(s_enc_buf, 0, padded_len);
    memcpy(s_enc_buf, data, data_len);

    s_original_data_len = data_len;
    s_original_data_len_set = true;

    erasure_encoder_t enc;
    erasure_encoder_init(&enc, num_frags, frag_payload_size, s_enc_buf);

    uint16_t total = num_frags + redundancy_count;
    if (total > PIPELINE_MAX_FRAGS + 32)
        return -1;

    int frames_out = 0;
    uint16_t block_id = (uint16_t)(data_len ^ (data_len >> 16) ^ (uint16_t)(data[0] << 8));

    for (uint16_t i = 0; i < total; i++) {
        uint8_t frag_buf[PIPELINE_MAX_FRAG_SIZE];
        memset(frag_buf, 0, frag_payload_size);

        if (i < num_frags) {
            memcpy(frag_buf, s_enc_buf + (uint32_t)i * frag_payload_size, frag_payload_size);
        } else {
            erasure_encode_redundant(&enc, i - num_frags, frag_buf);
        }

        uint8_t frame[FRAG_HEADER_SIZE + PIPELINE_MAX_FRAG_SIZE];
        uint16_t flen = frag_make_frame(block_id, (uint8_t)i, (uint8_t)num_frags,
                                         frag_buf, frag_payload_size, frame, sizeof(frame));
        if (flen == 0)
            return -1;

        cb(frame, flen, user_data);
        frames_out++;
    }

    return frames_out;
}

static void pipeline_init_rx(uint16_t frag_nb, uint8_t frag_size) {
    if (!s_dec_inited) {
        erasure_decoder_init(&s_dec, frag_nb, frag_size, s_ra_buf, s_matrix_buf);
        s_dec_inited = true;
    }
    if (!s_ra_inited) {
        frag_reassembler_init(&s_ra, 0, (uint8_t)frag_nb, frag_size,
                              s_ra_buf, sizeof(s_ra_buf));
        s_ra_inited = true;
    }
}

static int pipeline_check_complete(uint8_t *out_buf, uint16_t *out_len, uint16_t out_buf_size) {
    uint16_t data_len = (uint16_t)s_ra.original_count * s_ra.frag_size;
    if (s_rx_data_len_known && s_rx_data_len < data_len) data_len = s_rx_data_len;
    if (data_len > out_buf_size) return -1;
    memcpy(out_buf, s_ra_buf, data_len);
    *out_len = data_len;
    s_ra.complete = true;
    return 1;
}

int pipeline_rx_feed_frame(
    const uint8_t *frame, uint16_t frame_len,
    uint8_t *out_buf, uint16_t *out_len,
    uint16_t out_buf_size
) {
    if (!frame || !out_buf || !out_len)
        return -1;

    frag_header_t hdr;
    if (frame_len < FRAG_HEADER_SIZE)
        return -1;
    memcpy(&hdr, frame, FRAG_HEADER_SIZE);

    if (!s_ra_inited) {
        pipeline_init_rx(hdr.original_count, frame_len - FRAG_HEADER_SIZE);
        s_ra.block_id = hdr.block_id;
    }

    if (hdr.block_id != s_ra.block_id)
        return -1;

    if (s_ra.complete) {
        return pipeline_check_complete(out_buf, out_len, out_buf_size);
    }

    uint16_t frag_counter = hdr.frag_index + 1;
    int r = erasure_decoder_process(&s_dec, frag_counter, frame + FRAG_HEADER_SIZE);
    s_ra.frags_received++;

    if (r == 0 || s_dec.complete) {
        return pipeline_check_complete(out_buf, out_len, out_buf_size);
    }

    if (s_ra.frags_received >= s_ra.original_count && !s_dec.complete) {
        return pipeline_check_complete(out_buf, out_len, out_buf_size);
    }

    return 0;
}

void pipeline_rx_reset(void) {
    memset(&s_ra, 0, sizeof(s_ra));
    memset(&s_dec, 0, sizeof(s_dec));
    s_ra_inited = false;
    s_dec_inited = false;
    s_rx_data_len_known = false;
    s_rx_data_len = 0;
}

void pipeline_rx_set_data_len(uint16_t len) {
    s_rx_data_len = len;
    s_rx_data_len_known = true;
}
