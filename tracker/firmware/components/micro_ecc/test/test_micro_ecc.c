#include <stdio.h>
#include <string.h>
#include <assert.h>

#include "uECC.h"

static int test_rng(uint8_t *dest, unsigned size) {
    for (unsigned i = 0; i < size; i++) {
        dest[i] = (uint8_t)(i * 7 + 3);
    }
    return 1;
}

static uint8_t rand_state = 42;
static int fake_rng(uint8_t *dest, unsigned size) {
    for (unsigned i = 0; i < size; i++) {
        rand_state = (rand_state * 1103515245 + 12345) & 0xFF;
        dest[i] = rand_state;
    }
    return 1;
}

static int test_keygen(void) {
    uECC_set_rng(fake_rng);
    uint8_t pub[64], priv[32];
    int ok = uECC_make_key(pub, priv, uECC_secp256k1());
    if (!ok) return 0;

    uint8_t pub2[64];
    ok = uECC_compute_public_key(priv, pub2, uECC_secp256k1());
    if (!ok) return 0;

    if (memcmp(pub, pub2, 64) != 0) return 0;
    return 1;
}

static int test_ecdh(void) {
    uECC_set_rng(fake_rng);
    uint8_t pub_a[64], priv_a[32];
    uint8_t pub_b[64], priv_b[32];
    uint8_t secret_a[32], secret_b[32];

    if (!uECC_make_key(pub_a, priv_a, uECC_secp256k1())) return 0;
    if (!uECC_make_key(pub_b, priv_b, uECC_secp256k1())) return 0;

    if (!uECC_shared_secret(pub_b, priv_a, secret_a, uECC_secp256k1())) return 0;
    if (!uECC_shared_secret(pub_a, priv_b, secret_b, uECC_secp256k1())) return 0;

    if (memcmp(secret_a, secret_b, 32) != 0) return 0;
    return 1;
}

static int test_sign_verify(void) {
    uECC_set_rng(fake_rng);
    uint8_t pub[64], priv[32];
    if (!uECC_make_key(pub, priv, uECC_secp256k1())) return 0;

    uint8_t hash[32];
    memset(hash, 0xAB, 32);

    uint8_t sig[64];
    if (!uECC_sign(priv, hash, 32, sig, uECC_secp256k1())) return 0;
    if (!uECC_verify(pub, hash, 32, sig, uECC_secp256k1())) return 0;

    hash[0] ^= 0xFF;
    if (uECC_verify(pub, hash, 32, sig, uECC_secp256k1()) != 0) return 0;
    return 1;
}

static int test_valid_pubkey(void) {
    uECC_set_rng(fake_rng);
    uint8_t pub[64], priv[32];
    if (!uECC_make_key(pub, priv, uECC_secp256k1())) return 0;
    if (!uECC_valid_public_key(pub, uECC_secp256k1())) return 0;

    pub[0] ^= 0xFF;
    if (uECC_valid_public_key(pub, uECC_secp256k1()) != 0) return 0;
    return 1;
}

static int test_sizes(void) {
    int priv_size = uECC_curve_private_key_size(uECC_secp256k1());
    int pub_size = uECC_curve_public_key_size(uECC_secp256k1());
    return (priv_size == 32 && pub_size == 64) ? 1 : 0;
}

int main(void) {
    int pass = 0, fail = 0;

    #define RUN(name) do { \
        printf("  %-35s", #name); \
        if (test_##name()) { printf("PASS\n"); pass++; } \
        else { printf("FAIL\n"); fail++; } \
    } while(0)

    printf("micro-ecc secp256k1 tests:\n");
    RUN(sizes);
    RUN(keygen);
    RUN(ecdh);
    RUN(sign_verify);
    RUN(valid_pubkey);

    printf("\n%d/%d passed\n", pass, pass + fail);
    return fail > 0 ? 1 : 0;
}
