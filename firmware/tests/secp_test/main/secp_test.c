/*
 * secp_test.c — Minimal isolated secp256k1 flash/RAM measurement on ESP32-C3.
 *
 * Purpose
 * -------
 * The ONLY goal of this firmware is to make `idf.py size --archives` print the
 * flash (.text + .rodata) and DRAM (.data + .bss) cost of libsecp256k1.a when
 * linked into a near-empty ESP32-C3 image. It gates the architecture decision:
 *   full Schnorr signature validation on the balloon (ESP32-C3)
 *   vs. deferring signature checks to the ground station.
 *
 * What it exercises
 * -----------------
 * To defeat `-ffunction-sections -fdata-sections --gc-sections` (which would
 * otherwise drop unreferenced crypto code), we call BOTH:
 *   - secp256k1_ecdsa_verify()          (legacy ECDSA path)
 *   - secp256k1_schnorrsig_verify()     (BIP-340 Schnorr path — the real question)
 *
 * The pubkey is the secp256k1 generator point G (a known-valid point), so
 * secp256k1_pubkey_parse / xonly_pubkey_parse succeed and the full verify hot
 * path — including the expensive point multiplication — is linked and runs.
 * The signatures are zero-filled, so verify returns 0 (invalid sig); that is
 * irrelevant for a *flash* measurement, which is determined at link time.
 *
 * Results are sunk into a `volatile` so the compiler cannot constant-fold the
 * calls away.
 *
 * Output: prints a one-line verdict over UART so `idf.py monitor` confirms the
 * image actually booted and ran the crypto path on the C3.
 */

#include <stdio.h>
#include <string.h>

#include "secp256k1.h"
#include "secp256k1_extrakeys.h"
#include "secp256k1_schnorrsig.h"

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_heap_caps.h"

/* Sink so the optimiser cannot elide the verify calls. */
static volatile int g_verify_sink = 0;

/* Generator point G, compressed (prefix 0x02, even-Y). Known-valid pubkey. */
static const unsigned char k_pubkey_g_comp33[33] = {
    0x02,
    0x79, 0xBE, 0x66, 0x7E, 0xF9, 0xDC, 0xBB, 0xAC,
    0x55, 0xA0, 0x62, 0x95, 0xCE, 0x87, 0x0B, 0x07,
    0x02, 0x9B, 0xFC, 0xDB, 0x2D, 0xCE, 0x28, 0xD9,
    0x59, 0xF2, 0x81, 0x5B, 0x16, 0xF8, 0x17, 0x98,
};

/* x-only pubkey = G.x (32 bytes, no prefix). */
static const unsigned char k_xonly_g[32] = {
    0x79, 0xBE, 0x66, 0x7E, 0xF9, 0xDC, 0xBB, 0xAC,
    0x55, 0xA0, 0x62, 0x95, 0xCE, 0x87, 0x0B, 0x07,
    0x02, 0x9B, 0xFC, 0xDB, 0x2D, 0xCE, 0x28, 0xD9,
    0x59, 0xF2, 0x81, 0x5B, 0x16, 0xF8, 0x17, 0x98,
};

static unsigned char k_zeros64[64];
static unsigned char k_zeros32[32];

static void run_secp_measurements(void)
{
    /* Context with VERIFY capability (the path the balloon needs). */
    secp256k1_context *ctx =
        secp256k1_context_create(SECP256K1_CONTEXT_VERIFY);
    if (ctx == NULL) {
        printf("secp_test: context_create FAILED\n");
        return;
    }

    /* ---- ECDSA verify path ---- */
    secp256k1_pubkey pubkey;
    int pub_ok = secp256k1_ec_pubkey_parse(ctx, &pubkey,
                                        k_pubkey_g_comp33, sizeof(k_pubkey_g_comp33));

    secp256k1_ecdsa_signature sig;
    int sig_ok = secp256k1_ecdsa_signature_parse_compact(ctx, &sig, k_zeros64);

    int ecdsa_result = 0;
    if (pub_ok && sig_ok) {
        ecdsa_result = secp256k1_ecdsa_verify(ctx, &sig, k_zeros32, &pubkey);
    }

    /* ---- BIP-340 Schnorr verify path (the actual ADR question) ---- */
    secp256k1_xonly_pubkey xpub;
    int xpub_ok = secp256k1_xonly_pubkey_parse(ctx, &xpub, k_xonly_g);

    int schnorr_result = 0;
    if (xpub_ok) {
        schnorr_result = secp256k1_schnorrsig_verify(ctx,
                                                    k_zeros64,       /* sig64 */
                                                    k_zeros32,       /* msg32 */
                                                    32,              /* msglen */
                                                    &xpub);
    }

    /* Sink both results so nothing is DCE'd. (Both are 0 — invalid sig — which
     * is expected and irrelevant for the flash measurement.) */
    g_verify_sink = (ecdsa_result << 1) | (schnorr_result & 1);

    secp256k1_context_destroy(ctx);

    printf("secp_test: ecdsa_verify=%d schnorr_verify=%d  (0=invalid-sig, expected)\n",
           ecdsa_result, schnorr_result);
    printf("secp_test: crypto path linked + executed OK. See `idf.py size --archives`.\n");
}

void app_main(void)
{
    printf("secp_test: boot on ESP32-C3, running isolated secp256k1 measurement...\n");
    run_secp_measurements();
    printf("secp_test: DONE. Free heap=%lu bytes\n",
           (unsigned long)esp_get_free_heap_size());

    while (1) {
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}
