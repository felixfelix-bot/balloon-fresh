/**
 * @file    test_prbs_wiring.c
 * @brief   Host unit tests: PRBS-15 wiring into RX path + PKT formatter.
 *
 * TDD RED phase tests for PRBS-3:
 *   1. TX path calls prbs15_fill with seq as seed
 *   2. RX path calls prbs15_verify, populates bit_err + bytes_bad in PKT line
 *   3. CRC-failed packets still have bit_err=0 (can't verify corrupted payload)
 *   4. CONFIG PRBS OFF → bit_err=0, bytes_bad=0
 */

#include "bench_payload.h"
#include "prbs.h"
#include "bench_cmd.h"
#include "bench_pkt.h"

#include <stdio.h>
#include <string.h>
#include <stdint.h>

static int failures = 0;

#define CHECK(cond)                                                              \
    do                                                                           \
    {                                                                            \
        if (!(cond))                                                             \
        {                                                                        \
            printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);               \
            failures++;                                                          \
        }                                                                        \
    } while (0)

/* ---- Test 1: TX path calls prbs15_fill with seq as seed ----
 *
 * bench_payload_build() is the TX path function. It must:
 *   a) Stamp the 4-byte BE seq header
 *   b) Fill the body with prbs15_fill(body, body_len, seq)
 * We verify by checking that the body matches a direct prbs15_fill call
 * with the same seed, and that different seeds produce different bodies.
 */
static void test_tx_path_calls_prbs15_fill_with_seq_as_seed(void)
{
    uint8_t buf[128];
    uint8_t expected_body[124];

    uint32_t seq = 42;
    bench_payload_build(buf, sizeof(buf), seq);

    /* Header must be the BE seq */
    CHECK(bench_payload_seq(buf) == seq);

    /* Body must match direct prbs15_fill with seq as seed */
    prbs15_fill(expected_body, sizeof(buf) - BENCH_PAYLOAD_HDR_LEN, seq);
    CHECK(memcmp(buf + BENCH_PAYLOAD_HDR_LEN, expected_body,
                 sizeof(buf) - BENCH_PAYLOAD_HDR_LEN) == 0);

    /* Different seed produces different body.
     * NOTE: seq and seq+1 may map to the same LFSR state because
     * the seed derivation does (seq ^ 0x5A5A) | 1 — bit 0 is forced
     * to 1, so even/odd pairs produce identical PRBS streams.
     * Use seq+2 to guarantee a different 15-bit state. */
    uint8_t buf2[128];
    bench_payload_build(buf2, sizeof(buf2), seq + 2);
    CHECK(memcmp(buf + BENCH_PAYLOAD_HDR_LEN,
                 buf2 + BENCH_PAYLOAD_HDR_LEN,
                 sizeof(buf) - BENCH_PAYLOAD_HDR_LEN) != 0);
}

/* ---- Test 2: RX path calls prbs15_verify, populates bit_err + bytes_bad ----
 *
 * bench_payload_verify() is the RX path function. It must:
 *   a) Return 0 bit_err / 0 bytes_bad for a clean payload
 *   b) Return >0 bit_err / >0 bytes_bad for a corrupted payload
 *   c) The bit_err/bytes_bad must flow through to the PKT formatter
 */
static void test_rx_path_prbs15_verify_populates_bit_err_bytes_bad(void)
{
    uint8_t buf[128];
    uint32_t seq = 99;
    bench_payload_build(buf, sizeof(buf), seq);

    /* Clean payload: zero errors */
    uint16_t bytes_bad = 0xFFFF;
    uint16_t bit_err = bench_payload_verify(buf, sizeof(buf), seq, &bytes_bad);
    CHECK(bit_err == 0);
    CHECK(bytes_bad == 0);

    /* Corrupt 2 body bytes, verify errors are detected */
    buf[10] ^= 0x0F;  /* 4 bits flipped */
    buf[50] ^= 0x80;  /* 1 bit flipped */
    bytes_bad = 0;
    bit_err = bench_payload_verify(buf, sizeof(buf), seq, &bytes_bad);
    CHECK(bit_err == 5);
    CHECK(bytes_bad == 2);

    /* Verify the bit_err / bytes_bad flow through the PKT formatter */
    bench_pkt_ctx_t ctx = { .session_id = 1, .config_id = 1, .replicate = 0 };
    bench_pkt_evt_t evt = {
        .seq            = seq,
        .len            = sizeof(buf),
        .rssi_half_dbm  = -100,
        .snr_qdb        = 40,
        .mod            = BENCH_PKT_MOD_LORA,
        .sf             = 8,
        .bw_hz          = 125000,
        .freq_hz         = 868000000UL,
        .txpow_dbm      = 10,
        .cr             = 5,
        .ts_ms          = 1000,
        .bit_err        = bit_err,
        .bytes_bad      = bytes_bad,
    };
    char pktbuf[256];
    int n = bench_pkt_format(pktbuf, sizeof(pktbuf), &ctx, &evt, 1);
    CHECK(n > 0);
    /* bit_err=5, bytes_bad=2 must appear in the PKT line */
    CHECK(strstr(pktbuf, ",5,2,") != NULL);
}

/* ---- Test 3: CRC-failed packets have bit_err=0 ----
 *
 * When CRC fails, the payload is unreliable — we can't verify PRBS.
 * The firmware hardcodes bit_err=0, bytes_bad=0 for CRC failures.
 * This test verifies the PKT formatter correctly outputs 0,0 for those.
 */
static void test_crc_failed_packets_have_zero_bit_err(void)
{
    bench_pkt_ctx_t ctx = { .session_id = 1, .config_id = 1, .replicate = 0 };
    bench_pkt_evt_t evt = {
        .seq            = 0,
        .len            = 0,
        .rssi_half_dbm  = -86,
        .snr_qdb        = 0,
        .mod            = BENCH_PKT_MOD_LORA,
        .sf             = 8,
        .bw_hz          = 125000,
        .freq_hz         = 868000000UL,
        .txpow_dbm      = 10,
        .cr             = 5,
        .ts_ms          = 500,
        .bit_err        = 0,   /* firmware hardcodes 0 for CRC failures */
        .bytes_bad      = 0,   /* firmware hardcodes 0 for CRC failures */
    };
    char pktbuf[256];
    int n = bench_pkt_format(pktbuf, sizeof(pktbuf), &ctx, &evt, 0 /* crc_ok=0 */);
    CHECK(n > 0);

    /* The PKT line must have crc_ok=0, bit_err=0, bytes_bad=0 */
    /* Format: ...,<crc_ok>,<bit_err>,<bytes_bad>,... */
    /* crc_ok=0, bit_err=0, bytes_bad=0 → ",0,0,0," */
    CHECK(strstr(pktbuf, ",0,0,0,") != NULL);
}

/* ---- Test 4: CONFIG PRBS OFF → bit_err=0, bytes_bad=0 ----
 *
 * The CONFIG PRBS ON|OFF command toggles PRBS verification.
 * When PRBS is OFF, the firmware must skip verification and report
 * bit_err=0, bytes_bad=0 for all packets (even RX_OK).
 *
 * This test verifies the command parser recognizes "PRBS ON" and "PRBS OFF".
 */
static void test_config_prbs_off_command(void)
{
    bench_cmd_t c;
    memset(&c, 0, sizeof(c));

    /* PRBS ON — enables PRBS verification on RX */
    bench_cmd_parse("PRBS ON", &c);
    CHECK(c.id == BENCH_CMD_PRBS);
    CHECK(c.err == BENCH_CMD_OK);
    CHECK(c.prbs_enable == true);

    /* PRBS OFF — disables PRBS verification, bit_err=0, bytes_bad=0 */
    memset(&c, 0, sizeof(c));
    bench_cmd_parse("PRBS OFF", &c);
    CHECK(c.id == BENCH_CMD_PRBS);
    CHECK(c.err == BENCH_CMD_OK);
    CHECK(c.prbs_enable == false);

    /* Case-insensitive */
    memset(&c, 0, sizeof(c));
    bench_cmd_parse("prbs on", &c);
    CHECK(c.id == BENCH_CMD_PRBS);
    CHECK(c.prbs_enable == true);

    memset(&c, 0, sizeof(c));
    bench_cmd_parse("Prbs Off", &c);
    CHECK(c.id == BENCH_CMD_PRBS);
    CHECK(c.prbs_enable == false);

    /* Bad argument */
    memset(&c, 0, sizeof(c));
    bench_cmd_parse("PRBS FOO", &c);
    CHECK(c.err != BENCH_CMD_OK);

    /* Missing argument */
    memset(&c, 0, sizeof(c));
    bench_cmd_parse("PRBS", &c);
    CHECK(c.err != BENCH_CMD_OK);

    /* When PRBS is OFF, the PKT line still shows 0,0 for RX_OK packets */
    bench_pkt_ctx_t ctx = { .session_id = 1, .config_id = 1, .replicate = 0 };
    bench_pkt_evt_t evt = {
        .seq            = 42,
        .len            = 64,
        .rssi_half_dbm = -100,
        .snr_qdb        = 40,
        .mod            = BENCH_PKT_MOD_LORA,
        .sf             = 8,
        .bw_hz          = 125000,
        .freq_hz        = 868000000UL,
        .txpow_dbm      = 10,
        .cr             = 5,
        .ts_ms          = 1000,
        .bit_err        = 0,   /* PRBS OFF → always 0 */
        .bytes_bad      = 0,   /* PRBS OFF → always 0 */
    };
    char pktbuf[256];
    int n = bench_pkt_format(pktbuf, sizeof(pktbuf), &ctx, &evt, 1 /* crc_ok */);
    CHECK(n > 0);
    /* crc_ok=1, bit_err=0, bytes_bad=0 → ",1,0,0," */
    CHECK(strstr(pktbuf, ",1,0,0,") != NULL);
}

int main(void)
{
    test_tx_path_calls_prbs15_fill_with_seq_as_seed();
    test_rx_path_prbs15_verify_populates_bit_err_bytes_bad();
    test_crc_failed_packets_have_zero_bit_err();
    test_config_prbs_off_command();

    if (failures == 0)
    {
        printf("test_prbs_wiring: ALL PASS\n");
        return 0;
    }
    printf("test_prbs_wiring: %d FAILURES\n", failures);
    return 1;
}