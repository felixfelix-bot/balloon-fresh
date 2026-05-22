#ifndef FIPS_TRANSPORT_H
#define FIPS_TRANSPORT_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define FIPS_PUBKEY_RAW_SIZE  64
#define FIPS_PRIVKEY_SIZE 32
#define FIPS_PUBKEY_COMPRESSED_SIZE 33
#define FIPS_SHARED_SIZE  32
#define FIPS_HASH_SIZE    32
#define FIPS_AEAD_KEY_SIZE 32
#define FIPS_AEAD_NONCE_SIZE 12
#define FIPS_AEAD_TAG_SIZE  16
#define FIPS_NODE_ADDR_SIZE 16
#define FIPS_MAX_PAYLOAD   222

#define FIPS_MSG1_SIZE (33 + (33 + 16) + 16)
#define FIPS_MSG2_SIZE (33 + 16)

#define FIPS_FMP_PREFIX_SIZE  4
#define FIPS_FMP_COUNTER_SIZE 8
#define FIPS_FMP_OVERHEAD     (FIPS_FMP_PREFIX_SIZE + 4 + FIPS_FMP_COUNTER_SIZE + FIPS_AEAD_TAG_SIZE)

typedef enum {
    FIPS_STATE_IDLE,
    FIPS_STATE_WAIT_MSG2,
    FIPS_STATE_ESTABLISHED,
    FIPS_STATE_ERROR
} fips_state_t;

typedef struct {
    uint8_t local_privkey[FIPS_PRIVKEY_SIZE];
    uint8_t local_pubkey[FIPS_PUBKEY_RAW_SIZE];
    uint8_t remote_pubkey[FIPS_PUBKEY_RAW_SIZE];
    uint8_t ephemeral_privkey[FIPS_PRIVKEY_SIZE];
    uint8_t node_addr[FIPS_NODE_ADDR_SIZE];
    fips_state_t state;

    uint8_t ck[FIPS_HASH_SIZE];
    uint8_t h[FIPS_HASH_SIZE];
    uint8_t k[FIPS_AEAD_KEY_SIZE];
    uint8_t nonce[FIPS_AEAD_NONCE_SIZE];
    uint64_t send_counter;
    uint64_t recv_counter;
    uint32_t receiver_idx;
} fips_session_t;

typedef int (*fips_send_fn)(const uint8_t *data, size_t len);
typedef int (*fips_recv_fn)(uint8_t *data, size_t max_len);

void fips_init(fips_session_t *sess, const uint8_t *local_privkey, const uint8_t *remote_pubkey_compressed);
void fips_get_node_addr(const uint8_t *pubkey_uncompressed, uint8_t *addr);

int fips_handshake_initiator_msg1(fips_session_t *sess, uint8_t *out, size_t *out_len);
int fips_handshake_responder_process_msg1(fips_session_t *sess, const uint8_t *local_privkey, const uint8_t *msg1, size_t msg1_len, uint8_t *msg2, size_t *msg2_len);
int fips_handshake_initiator_process_msg2(fips_session_t *sess, const uint8_t *msg2, size_t msg2_len);

int fips_encrypt(fips_session_t *sess, const uint8_t *plaintext, size_t pt_len, uint8_t *out, size_t *out_len);
int fips_decrypt(fips_session_t *sess, const uint8_t *ciphertext, size_t ct_len, uint8_t *out, size_t *out_len);

int fips_run_initiator(fips_session_t *sess, fips_send_fn send, fips_recv_fn recv);
int fips_run_responder(fips_session_t *sess, const uint8_t *local_privkey, fips_send_fn send, fips_recv_fn recv);

#ifdef __cplusplus
}
#endif

#endif
