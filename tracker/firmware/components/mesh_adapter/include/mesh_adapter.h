#pragma once

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

#define MESH_ADAPTER_MAX_FRAMES 128

typedef void (*mesh_frame_send_fn)(const uint8_t *frame, uint16_t len);

typedef struct {
    uint8_t frames[MESH_ADAPTER_MAX_FRAMES][256];
    uint16_t frame_lens[MESH_ADAPTER_MAX_FRAMES];
    int frame_count;
} mesh_frame_queue_t;

typedef enum {
    MESH_OK = 0,
    MESH_ERR_INVALID_PARAM = -1,
    MESH_ERR_ENCRYPT_FAILED = -2,
    MESH_ERR_FRAGMENT_FAILED = -3,
    MESH_ERR_DECRYPT_FAILED = -4,
    MESH_ERR_REASSEMBLE_FAILED = -5,
    MESH_ERR_STORE_FULL = -6,
    MESH_ERR_NOT_ESTABLISHED = -7,
} mesh_result_t;

typedef struct {
    mesh_frame_send_fn send_fn;
    mesh_frame_queue_t *tx_queue;
} mesh_adapter_config_t;

void mesh_adapter_init(const mesh_adapter_config_t *config);

mesh_result_t mesh_adapter_send(const uint8_t *data, uint16_t data_len,
                                uint8_t frag_size, uint8_t redundancy);

mesh_result_t mesh_adapter_receive_frame(const uint8_t *frame, uint16_t frame_len,
                                         uint8_t *out_data, uint16_t *out_len,
                                         uint16_t out_size);

void mesh_adapter_set_fips_sessions(void *init_sess, void *resp_sess);

void mesh_adapter_reset(void);

int mesh_adapter_get_pending_frame_count(void);

#ifdef __cplusplus
}
#endif
