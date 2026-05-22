#include "fips_transport.h"
#include <string.h>
#include "mbedtls/sha256.h"
#include "mbedtls/chachapoly.h"
#include "mbedtls/hkdf.h"
#include "mbedtls/md.h"
#include "uECC.h"

static void compress_pubkey(const uint8_t uncompressed[64], uint8_t compressed[33]) {
    uECC_compress(uncompressed, compressed, uECC_secp256k1());
}

static void decompress_pubkey(const uint8_t compressed[33], uint8_t uncompressed[64]) {
    uECC_decompress(compressed, uncompressed, uECC_secp256k1());
}

static void hash_update(uint8_t *h, const uint8_t *data, size_t len) {
    mbedtls_sha256_context ctx;
    mbedtls_sha256_init(&ctx);
    mbedtls_sha256_starts(&ctx, 0);
    mbedtls_sha256_update(&ctx, h, 32);
    mbedtls_sha256_update(&ctx, data, len);
    mbedtls_sha256_finish(&ctx, h);
    mbedtls_sha256_free(&ctx);
}

static void mix_key(fips_session_t *sess, const uint8_t *ikm, size_t ikm_len) {
    uint8_t prk[32];
    const mbedtls_md_info_t *md = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
    mbedtls_hkdf_extract(md, sess->ck, 32, ikm, ikm_len, prk);
    uint8_t tmp[64];
    uint8_t info1[1] = {0x01};
    mbedtls_hkdf_expand(md, prk, 32, info1, 1, tmp, 64);
    memcpy(sess->ck, tmp, 32);
    memcpy(sess->k, tmp + 32, 32);
    memset(sess->nonce, 0, FIPS_AEAD_NONCE_SIZE);
    mbedtls_platform_zeroize(prk, 32);
    mbedtls_platform_zeroize(tmp, 64);
}

static void dh_compute(const uint8_t *priv, const uint8_t *pub_uncompressed, uint8_t *shared) {
    uECC_shared_secret(pub_uncompressed, priv, shared, uECC_secp256k1());
}

static int aead_encrypt(const uint8_t *key, const uint8_t *nonce,
                        const uint8_t *aad, size_t aad_len,
                        const uint8_t *pt, size_t pt_len,
                        uint8_t *ct_and_tag) {
    mbedtls_chachapoly_context ctx;
    mbedtls_chachapoly_init(&ctx);
    mbedtls_chachapoly_setkey(&ctx, key);
    int ret = mbedtls_chachapoly_encrypt_and_tag(&ctx, pt_len, nonce,
                                                  aad, aad_len, pt,
                                                  ct_and_tag,
                                                  ct_and_tag + pt_len);
    mbedtls_chachapoly_free(&ctx);
    return ret == 0 ? 0 : -1;
}

static int aead_decrypt(const uint8_t *key, const uint8_t *nonce,
                        const uint8_t *aad, size_t aad_len,
                        const uint8_t *ct_and_tag, size_t buf_len,
                        uint8_t *pt) {
    if (buf_len < FIPS_AEAD_TAG_SIZE) return -1;
    size_t pt_len = buf_len - FIPS_AEAD_TAG_SIZE;
    mbedtls_chachapoly_context ctx;
    mbedtls_chachapoly_init(&ctx);
    mbedtls_chachapoly_setkey(&ctx, key);
    int ret = mbedtls_chachapoly_auth_decrypt(&ctx, pt_len, nonce,
                                               aad, aad_len,
                                               ct_and_tag + pt_len,
                                               ct_and_tag,
                                               pt);
    mbedtls_chachapoly_free(&ctx);
    return ret == 0 ? (int)pt_len : -1;
}

static void increment_nonce(uint8_t *nonce) {
    for (int i = FIPS_AEAD_NONCE_SIZE - 1; i >= 0; i--) {
        if (++nonce[i] != 0) break;
    }
}

void fips_init(fips_session_t *sess, const uint8_t *local_privkey,
               const uint8_t *remote_pubkey_compressed) {
    memset(sess, 0, sizeof(*sess));
    if (local_privkey) {
        memcpy(sess->local_privkey, local_privkey, FIPS_PRIVKEY_SIZE);
        uECC_compute_public_key(local_privkey, sess->local_pubkey, uECC_secp256k1());
        fips_get_node_addr(sess->local_pubkey, sess->node_addr);
    }
    if (remote_pubkey_compressed) {
        decompress_pubkey(remote_pubkey_compressed, sess->remote_pubkey);
    }
    sess->state = FIPS_STATE_IDLE;
}

void fips_get_node_addr(const uint8_t *pubkey_uncompressed, uint8_t *addr) {
    uint8_t hash[32];
    mbedtls_sha256(pubkey_uncompressed, FIPS_PUBKEY_RAW_SIZE, hash, 0);
    memcpy(addr, hash, FIPS_NODE_ADDR_SIZE);
}

/*
 * Noise IK pattern:
 *   <- s                          (responder's static key pre-known)
 *   ...
 *   -> e, es, s, ss              MSG1: initiator -> responder
 *   <- e, ee, se                 MSG2: responder -> initiator
 *
 * MSG1 layout: e(33) || enc_s(33+16) || enc_payload(16)
 *   = 33 + 49 + 16 = 98 bytes
 *
 * MSG2 layout: e(33) || enc_payload(16)
 *   = 33 + 16 = 49 bytes
 */

int fips_handshake_initiator_msg1(fips_session_t *sess, uint8_t *out, size_t *out_len) {
    const char *pname = "Noise_IK_secp256k1_ChaChaPoly_SHA256";
    mbedtls_sha256((const uint8_t *)pname, strlen(pname), sess->ck, 0);
    memcpy(sess->h, sess->ck, 32);

    // Pre-message: hash responder's static pubkey (rs)
    uint8_t rs_comp[33];
    compress_pubkey(sess->remote_pubkey, rs_comp);
    hash_update(sess->h, rs_comp, 33);

    // Token "e": generate ephemeral, write to output, hash
    uint8_t epriv[32], epub[64];
    uECC_make_key(epub, epriv, uECC_secp256k1());
    memcpy(sess->ephemeral_privkey, epriv, 32);
    uint8_t e_comp[33];
    compress_pubkey(epub, e_comp);
    size_t pos = 0;
    memcpy(out + pos, e_comp, 33); pos += 33;
    hash_update(sess->h, e_comp, 33);

    // Token "es": MixKey(DH(e, rs)) — initiator ephemeral with responder static
    uint8_t dh_es[32];
    dh_compute(epriv, sess->remote_pubkey, dh_es);
    mix_key(sess, dh_es, 32);

    // Token "s": encrypt and write initiator's static pubkey
    uint8_t s_comp[33];
    compress_pubkey(sess->local_pubkey, s_comp);
    uint8_t enc_s[33 + FIPS_AEAD_TAG_SIZE];
    if (aead_encrypt(sess->k, sess->nonce, sess->h, 32, s_comp, 33, enc_s) != 0) {
        mbedtls_platform_zeroize(epriv, 32);
        mbedtls_platform_zeroize(dh_es, 32);
        return -1;
    }
    memcpy(out + pos, enc_s, sizeof(enc_s)); pos += sizeof(enc_s);
    hash_update(sess->h, enc_s, sizeof(enc_s));
    increment_nonce(sess->nonce);

    // Token "ss": MixKey(DH(s, rs)) — initiator static with responder static
    uint8_t dh_ss[32];
    dh_compute(sess->local_privkey, sess->remote_pubkey, dh_ss);
    mix_key(sess, dh_ss, 32);

    // Payload (empty): encrypt and write
    uint8_t enc_empty[FIPS_AEAD_TAG_SIZE];
    if (aead_encrypt(sess->k, sess->nonce, sess->h, 32, NULL, 0, enc_empty) != 0) {
        mbedtls_platform_zeroize(epriv, 32);
        mbedtls_platform_zeroize(dh_es, 32);
        mbedtls_platform_zeroize(dh_ss, 32);
        return -1;
    }
    memcpy(out + pos, enc_empty, sizeof(enc_empty)); pos += sizeof(enc_empty);
    hash_update(sess->h, enc_empty, sizeof(enc_empty));
    increment_nonce(sess->nonce);

    *out_len = pos;

    // No Split yet — more messages to process
    sess->state = FIPS_STATE_WAIT_MSG2;

    mbedtls_platform_zeroize(epriv, 32);
    mbedtls_platform_zeroize(dh_es, 32);
    mbedtls_platform_zeroize(dh_ss, 32);
    return 0;
}

int fips_handshake_responder_process_msg1(fips_session_t *sess,
                                           const uint8_t *local_privkey,
                                           const uint8_t *msg1, size_t msg1_len,
                                           uint8_t *msg2, size_t *msg2_len) {
    if (msg1_len != FIPS_MSG1_SIZE) return -1;

    const char *pname = "Noise_IK_secp256k1_ChaChaPoly_SHA256";
    mbedtls_sha256((const uint8_t *)pname, strlen(pname), sess->ck, 0);
    memcpy(sess->h, sess->ck, 32);

    memcpy(sess->local_privkey, local_privkey, FIPS_PRIVKEY_SIZE);
    uECC_compute_public_key(local_privkey, sess->local_pubkey, uECC_secp256k1());

    // Pre-message: hash responder's own static pubkey (rs in responder's view = self)
    uint8_t rs_comp[33];
    compress_pubkey(sess->local_pubkey, rs_comp);
    hash_update(sess->h, rs_comp, 33);

    // Token "e": read initiator's ephemeral, hash
    const uint8_t *re_comp = msg1;
    uint8_t re[64];
    decompress_pubkey(re_comp, re);
    hash_update(sess->h, re_comp, 33);

    // Token "es": MixKey(DH(s, re)) — responder static with initiator ephemeral
    // Note: "es" means initiator(e) x responder(s), but responder processes as DH(s, re)
    uint8_t dh_es[32];
    dh_compute(local_privkey, re, dh_es);
    mix_key(sess, dh_es, 32);

    // Token "s": decrypt initiator's static pubkey
    const uint8_t *enc_s = msg1 + 33;
    uint8_t rs_dec[33];
    if (aead_decrypt(sess->k, sess->nonce, sess->h, 32, enc_s, 33 + 16, rs_dec) < 0) {
        mbedtls_platform_zeroize(dh_es, 32);
        return -1;
    }
    decompress_pubkey(rs_dec, sess->remote_pubkey);
    hash_update(sess->h, enc_s, 33 + 16);
    increment_nonce(sess->nonce);

    // Token "ss": MixKey(DH(s, rs)) — responder static with initiator static
    uint8_t dh_ss[32];
    dh_compute(local_privkey, sess->remote_pubkey, dh_ss);
    mix_key(sess, dh_ss, 32);

    // Payload: decrypt (empty)
    const uint8_t *enc_empty = msg1 + 33 + 49;
    if (aead_decrypt(sess->k, sess->nonce, sess->h, 32, enc_empty, 16, NULL) < 0) {
        mbedtls_platform_zeroize(dh_es, 32);
        mbedtls_platform_zeroize(dh_ss, 32);
        return -1;
    }
    hash_update(sess->h, enc_empty, 16);
    increment_nonce(sess->nonce);

    // === MSG2: e, ee, se ===

    // Token "e": generate ephemeral, write to output, hash
    uint8_t epriv[32], epub[64];
    uECC_make_key(epub, epriv, uECC_secp256k1());
    memcpy(sess->ephemeral_privkey, epriv, 32);
    uint8_t e_comp[33];
    compress_pubkey(epub, e_comp);
    size_t pos = 0;
    memcpy(msg2 + pos, e_comp, 33); pos += 33;
    hash_update(sess->h, e_comp, 33);

    // Token "ee": MixKey(DH(e, re)) — responder ephemeral with initiator ephemeral
    uint8_t dh_ee[32];
    dh_compute(epriv, re, dh_ee);
    mix_key(sess, dh_ee, 32);

    // Token "se": MixKey(DH(e, rs)) — responder ephemeral with initiator static
    // Noise spec: "se" = DH(initiator_s, responder_e). Responder computes DH(e, rs).
    uint8_t dh_se[32];
    dh_compute(epriv, sess->remote_pubkey, dh_se);
    mix_key(sess, dh_se, 32);

    // Payload: encrypt (empty)
    uint8_t enc_empty2[FIPS_AEAD_TAG_SIZE];
    if (aead_encrypt(sess->k, sess->nonce, sess->h, 32, NULL, 0, enc_empty2) != 0) {
        mbedtls_platform_zeroize(epriv, 32);
        mbedtls_platform_zeroize(dh_es, 32);
        mbedtls_platform_zeroize(dh_ss, 32);
        mbedtls_platform_zeroize(dh_ee, 32);
        mbedtls_platform_zeroize(dh_se, 32);
        return -1;
    }
    memcpy(msg2 + pos, enc_empty2, sizeof(enc_empty2)); pos += sizeof(enc_empty2);
    hash_update(sess->h, enc_empty2, sizeof(enc_empty2));
    increment_nonce(sess->nonce);

    *msg2_len = pos;

    // Split: derive transport keys
    uint8_t zero[32] = {0};
    mix_key(sess, zero, 32);

    sess->send_counter = 0;
    sess->recv_counter = 0;
    sess->state = FIPS_STATE_ESTABLISHED;
    fips_get_node_addr(sess->local_pubkey, sess->node_addr);

    mbedtls_platform_zeroize(epriv, 32);
    mbedtls_platform_zeroize(dh_es, 32);
    mbedtls_platform_zeroize(dh_ss, 32);
    mbedtls_platform_zeroize(dh_ee, 32);
    mbedtls_platform_zeroize(dh_se, 32);
    return 0;
}

int fips_handshake_initiator_process_msg2(fips_session_t *sess,
                                          const uint8_t *msg2, size_t msg2_len) {
    if (msg2_len != FIPS_MSG2_SIZE) return -1;
    if (sess->state != FIPS_STATE_WAIT_MSG2) return -1;

    // Token "e": read responder's ephemeral, hash
    const uint8_t *re_comp = msg2;
    uint8_t re[64];
    decompress_pubkey(re_comp, re);
    hash_update(sess->h, re_comp, 33);

    // Token "ee": MixKey(DH(e, re)) — initiator ephemeral with responder ephemeral
    uint8_t dh_ee[32];
    dh_compute(sess->ephemeral_privkey, re, dh_ee);
    mix_key(sess, dh_ee, 32);

    // Token "se": MixKey(DH(s, re)) — initiator static with responder ephemeral
    uint8_t dh_se[32];
    dh_compute(sess->local_privkey, re, dh_se);
    mix_key(sess, dh_se, 32);

    // Payload: decrypt (empty)
    const uint8_t *enc_empty = msg2 + 33;
    if (aead_decrypt(sess->k, sess->nonce, sess->h, 32, enc_empty, 16, NULL) < 0) {
        mbedtls_platform_zeroize(dh_ee, 32);
        mbedtls_platform_zeroize(dh_se, 32);
        sess->state = FIPS_STATE_ERROR;
        return -1;
    }
    hash_update(sess->h, enc_empty, 16);
    increment_nonce(sess->nonce);

    // Split: derive transport keys (already done by MixKey chain)
    uint8_t zero[32] = {0};
    mix_key(sess, zero, 32);

    sess->send_counter = 0;
    sess->recv_counter = 0;
    sess->state = FIPS_STATE_ESTABLISHED;

    mbedtls_platform_zeroize(sess->ephemeral_privkey, 32);
    mbedtls_platform_zeroize(dh_ee, 32);
    mbedtls_platform_zeroize(dh_se, 32);
    return 0;
}

int fips_encrypt(fips_session_t *sess, const uint8_t *pt, size_t pt_len,
                 uint8_t *out, size_t *out_len) {
    if (sess->state != FIPS_STATE_ESTABLISHED) return -1;
    if (pt_len + FIPS_FMP_OVERHEAD > FIPS_MAX_PAYLOAD) return -1;

    size_t pos = 0;
    out[pos++] = 0x00;
    out[pos++] = 0x00;
    out[pos++] = 0x00;
    out[pos++] = 0x01;

    uint32_t idx = sess->receiver_idx;
    memcpy(out + pos, &idx, 4);
    pos += 4;

    uint64_t ctr = sess->send_counter++;
    memcpy(out + pos, &ctr, 8);
    pos += 8;

    if (aead_encrypt(sess->k, sess->nonce, out, pos, pt, pt_len, out + pos) != 0) {
        return -1;
    }
    *out_len = pos + pt_len + FIPS_AEAD_TAG_SIZE;
    increment_nonce(sess->nonce);
    return 0;
}

int fips_decrypt(fips_session_t *sess, const uint8_t *ct, size_t ct_len,
                 uint8_t *out, size_t *out_len) {
    if (sess->state != FIPS_STATE_ESTABLISHED) return -1;

    size_t hdr_len = FIPS_FMP_PREFIX_SIZE + 4 + FIPS_FMP_COUNTER_SIZE;
    if (ct_len < hdr_len + FIPS_AEAD_TAG_SIZE) return -1;

    int result = aead_decrypt(sess->k, sess->nonce, ct, hdr_len,
                              ct + hdr_len, ct_len - hdr_len, out);
    if (result < 0) return -1;

    *out_len = (size_t)result;
    sess->recv_counter++;
    increment_nonce(sess->nonce);
    return 0;
}

int fips_run_initiator(fips_session_t *sess, fips_send_fn send, fips_recv_fn recv) {
    uint8_t msg1[FIPS_MSG1_SIZE];
    size_t msg1_len;
    if (fips_handshake_initiator_msg1(sess, msg1, &msg1_len) != 0) return -1;
    if (send(msg1, msg1_len) != 0) return -2;

    uint8_t msg2[FIPS_MSG2_SIZE + 16];
    int msg2_len = recv(msg2, sizeof(msg2));
    if (msg2_len < (int)FIPS_MSG2_SIZE) return -3;
    if (fips_handshake_initiator_process_msg2(sess, msg2, msg2_len) != 0) return -4;
    return 0;
}

int fips_run_responder(fips_session_t *sess, const uint8_t *local_privkey,
                       fips_send_fn send, fips_recv_fn recv) {
    uint8_t msg1[FIPS_MSG1_SIZE + 16];
    int msg1_len = recv(msg1, sizeof(msg1));
    if (msg1_len < (int)FIPS_MSG1_SIZE) return -1;

    uint8_t msg2[FIPS_MSG2_SIZE];
    size_t msg2_len;
    if (fips_handshake_responder_process_msg1(sess, local_privkey,
                                               msg1, msg1_len, msg2, &msg2_len) != 0) return -2;
    if (send(msg2, msg2_len) != 0) return -3;
    return 0;
}
