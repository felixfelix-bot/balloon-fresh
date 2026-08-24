#include "mesh_adapter.h"
#include "pipeline.h"
#include <string.h>

static mesh_frame_send_fn s_send_fn;
static mesh_frame_queue_t *s_tx_queue;
static mesh_encrypt_fn s_encrypt_fn;
static mesh_decrypt_fn s_decrypt_fn;
static void *s_encrypt_ctx;
static void *s_decrypt_ctx;

/* Encryption overhead: FIPS FMP adds prefix(4) + counter(8) + tag(16) + 4 = 32 bytes */
#define MESH_MAX_CIPHER_OVERHEAD 64

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
    s_encrypt_fn = config->encrypt_fn;
    s_decrypt_fn = config->decrypt_fn;
    s_encrypt_ctx = config->encrypt_ctx;
    s_decrypt_ctx = config->decrypt_ctx;
    pipeline_rx_reset();
}

mesh_result_t mesh_adapter_send(const uint8_t *data, uint16_t data_len,
                                uint8_t frag_size, uint8_t redundancy) {
    if (!data || data_len == 0) return MESH_ERR_INVALID_PARAM;

    const uint8_t *send_data = data;
    uint16_t send_len = data_len;
    uint8_t cipher_buf[512];  /* stack buffer for ciphertext */

    /* Encrypt before fragmentation if callback is set */
    if (s_encrypt_fn && s_encrypt_ctx) {
        size_t ct_len = sizeof(cipher_buf);
        int r = s_encrypt_fn(s_encrypt_ctx, data, data_len, cipher_buf, &ct_len);
        if (r != 0) return MESH_ERR_ENCRYPT_FAILED;
        send_data = cipher_buf;
        send_len = (uint16_t)ct_len;
    }

    int n = pipeline_tx_encode_fragment(send_data, send_len, frag_size, redundancy,
                                        tx_queue_frame, NULL);
    if (n <= 0) return MESH_ERR_FRAGMENT_FAILED;

    return MESH_OK;
}

mesh_result_t mesh_adapter_receive_frame(const uint8_t *frame, uint16_t frame_len,
                                         uint8_t *out_data, uint16_t *out_len,
                                         uint16_t out_size) {
    if (!frame || !out_data || !out_len) return MESH_ERR_INVALID_PARAM;

    /* Temporary buffer for reassembled (possibly encrypted) data */
    uint8_t reasm_buf[512];
    uint16_t reasm_len = 0;

    int r = pipeline_rx_feed_frame(frame, frame_len, reasm_buf, &reasm_len, sizeof(reasm_buf));
    if (r == 1) {
        /* Reassembly complete — decrypt if callback is set */
        if (s_decrypt_fn && s_decrypt_ctx) {
            size_t pt_len = out_size;
            int dr = s_decrypt_fn(s_decrypt_ctx, reasm_buf, reasm_len, out_data, &pt_len);
            if (dr != 0) return MESH_ERR_DECRYPT_FAILED;
            *out_len = (uint16_t)pt_len;
        } else {
            /* No encryption — copy directly */
            if (reasm_len > out_size) return MESH_ERR_REASSEMBLE_FAILED;
            memcpy(out_data, reasm_buf, reasm_len);
            *out_len = reasm_len;
        }
        return MESH_OK;
    }
    if (r < 0) return MESH_ERR_REASSEMBLE_FAILED;

    return MESH_ERR_REASSEMBLE_FAILED;
}

void mesh_adapter_set_fips_sessions(void *init_sess, void *resp_sess) {
    /* Store session pointers. Caller must also set encrypt_fn/decrypt_fn
     * to fips_encrypt/fips_decrypt via mesh_adapter_init config struct.
     * This function is for late-binding sessions after handshake completes. */
    s_encrypt_ctx = init_sess;
    s_decrypt_ctx = resp_sess;
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
