/**
 * @file    test_bench_pkt.c
 * @brief   Host unit tests: per-packet PKT line formatter (23-field format).
 *
 * Verifies the bench_pkt_format() output for:
 *   - basic RX_OK packet (crc_ok=1)
 *   - CRC failure packet (crc_ok=0, E80-7 RSSI extraction)
 *   - truncation safety (small buffer does not overflow)
 *   - CRC event with real RSSI (E80-7)
 *
 * Format (23 fields):
 * PKT,<session_id>,<config_id>,<replicate>,<seq>,<ts_ms>,<rssi_dbm>,
 * <snr_db>,<crc_ok>,<bit_err>,<bytes_bad>,<freq_hz>,<mod>,<sf>,
 * <bw_khz>,<cr>,<power_dbm>,<pkt_size>,<gps_fix>,<gps_lat>,<gps_lon>,
 * <gps_alt>,<gps_sats>,<gps_hdop>
 */

#include "bench_pkt.h"

#include <stdio.h>
#include <string.h>

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

/* Count total comma-separated fields in a line (including the first token).
 * A 23-field PKT line = "PKT" + 23 data fields = 24 comma-separated tokens. */
static int count_fields(const char* line)
{
    if (line == NULL || *line == '\0')
        return 0;
    int count = 1; /* first field */
    for (const char* p = line; *p != '\0'; p++)
    {
        if (*p == ',')
            count++;
    }
    return count;
}

/* Count data fields after the "PKT," prefix (should be 23). */
static int count_data_fields(const char* line)
{
    if (line == NULL || strncmp(line, "PKT,", 4) != 0)
        return -1;
    const char* p = line + 4; /* skip "PKT," */
    if (*p == '\0')
        return 0;
    int count = 1; /* at least one field */
    while (*p != '\0')
    {
        if (*p == ',')
            count++;
        p++;
    }
    return count;
}

static void test_basic(void)
{
    bench_pkt_ctx_t ctx = { .session_id = 42, .config_id = 7, .replicate = 3 };
    char buf[256];

    /* Simulate an RX_OK event */
    bench_pkt_evt_t evt = {
        .seq            = 1234,
        .len            = 64,
        .rssi_half_dbm  = -100,  /* -50.0 dBm */
        .snr_qdb        = 40,   /* 10.0 dB */
        .mod            = BENCH_PKT_MOD_LORA,
        .sf             = 8,
        .bw_hz          = 125000,
        .freq_hz         = 868000000UL,
        .txpow_dbm      = 10,
        .cr             = 5,
        .ts_ms          = 12345,
    };

    int n = bench_pkt_format(buf, sizeof(buf), &ctx, &evt, 1 /* crc_ok */);
    CHECK(n > 0);

    /* Verify prefix */
    CHECK(strncmp(buf, "PKT,", 4) == 0);

    /* Verify 23 data fields (total 24 including PKT prefix) */
    CHECK(count_data_fields(buf) == 23);

    /* Verify key field values */
    CHECK(strstr(buf, "PKT,42,7,3,1234,") != NULL);  /* session,config,replicate,seq */
    CHECK(strstr(buf, ",-50,") != NULL);            /* rssi_dbm = -100/2 = -50 */
    CHECK(strstr(buf, ",10,") != NULL);             /* snr_db = 40/4 = 10 */
    CHECK(strstr(buf, ",1,") != NULL);              /* crc_ok = 1 */
    CHECK(strstr(buf, ",0,0,") != NULL);            /* bit_err=0, bytes_bad=0 */
    CHECK(strstr(buf, "868000000,LORA,8,125,") != NULL); /* freq,mod,sf,bw_khz */
    CHECK(strstr(buf, ",10,64,") != NULL);           /* power_dbm=10, pkt_size=64 */
    /* GPS fields all zero */
    CHECK(strstr(buf, ",0,0,0,0,0,0") != NULL);      /* gps_fix,lat,lon,alt,sats,hdop */

    printf("  basic:  %s\n", buf);
}

static void test_crc_fail(void)
{
    bench_pkt_ctx_t ctx = { .session_id = 1, .config_id = 1, .replicate = 0 };
    char buf[256];

    /* CRC failure event — rssi_half_dbm should still be populated (E80-7).
     * For now the radio may return rssi=0 on CRC fail, but the PKT line
     * must still be emitted with crc_ok=0. */
    bench_pkt_evt_t evt = {
        .seq            = 0,
        .len            = 0,
        .rssi_half_dbm  = -86,  /* -43.0 dBm — populated by E80-7 */
        .snr_qdb        = 0,
        .mod            = BENCH_PKT_MOD_FLRC,
        .sf             = 8,
        .bw_hz          = 125000,
        .freq_hz         = 868000000UL,
        .txpow_dbm      = 10,
    };

    int n = bench_pkt_format(buf, sizeof(buf), &ctx, &evt, 0 /* crc_ok */);
    CHECK(n > 0);

    /* Verify prefix */
    CHECK(strncmp(buf, "PKT,", 4) == 0);

    /* Verify 23 data fields (total 24 including PKT prefix) */
    CHECK(count_data_fields(buf) == 23);

    /* crc_ok = 0 */
    CHECK(strstr(buf, "PKT,1,1,0,0,") != NULL);  /* session,config,replicate,seq=0 */
    CHECK(strstr(buf, ",0,") != NULL);          /* crc_ok = 0 */
    CHECK(strstr(buf, ",FLRC,") != NULL);       /* mod = FLRC */

    printf("  crc:    %s\n", buf);
}

static void test_truncation_safe(void)
{
    bench_pkt_ctx_t ctx = { .session_id = 999, .config_id = 888, .replicate = 777 };
    char buf[8]; /* deliberately tiny */

    bench_pkt_evt_t evt = {
        .seq            = 4294967295UL,
        .len            = 255,
        .rssi_half_dbm  = -100,
        .snr_qdb        = 40,
        .mod            = BENCH_PKT_MOD_LORA,
        .sf             = 12,
        .bw_hz          = 500000,
        .freq_hz         = 868000000UL,
        .txpow_dbm      = 22,
        .cr             = 8,
        .ts_ms          = 99999,
    };

    /* Must not crash, must NUL-terminate even if truncated */
    int n = bench_pkt_format(buf, sizeof(buf), &ctx, &evt, 1);
    CHECK(n > 0);                          /* returns required length */
    CHECK(n > (int)sizeof(buf));           /* it was truncated */
    CHECK(buf[sizeof(buf) - 1] == '\0');   /* NUL-terminated */

    /* Verify with a large enough buffer */
    char big[256];
    n = bench_pkt_format(big, sizeof(big), &ctx, &evt, 1);
    CHECK(n > 0);
    CHECK(n < (int)sizeof(big));
    CHECK(big[n] == '\0');
    CHECK(strncmp(big, "PKT,999,888,777,4294967295,", 26) == 0);

    printf("  trunc:  %s\n", big);
}

static void test_crc_rssi_extraction(void)
{
    /* E80-7: CRC-failed packets should have RSSI populated in the event.
     * This test verifies that bench_pkt_format() correctly outputs the
     * rssi value from a CRC event with rssi_half_dbm populated. */
    bench_pkt_ctx_t ctx = { .session_id = 5, .config_id = 2, .replicate = 1 };
    char buf[256];

    /* CRC event with a real RSSI value (populated by E80-7 radio_bench.c) */
    bench_pkt_evt_t evt = {
        .seq            = 0,
        .len            = 0,
        .rssi_half_dbm  = -112,  /* -56.0 dBm */
        .snr_qdb        = 0,
        .mod            = BENCH_PKT_MOD_LORA,
        .sf             = 8,
        .bw_hz          = 125000,
        .freq_hz         = 868000000UL,
        .txpow_dbm      = 10,
    };

    int n = bench_pkt_format(buf, sizeof(buf), &ctx, &evt, 0);
    CHECK(n > 0);
    /* rssi_dbm = -112/2 = -56 */
    CHECK(strstr(buf, ",-56,") != NULL);

    printf("  rssi:   %s\n", buf);
}

int main(void)
{
    test_basic();
    test_crc_fail();
    test_truncation_safe();
    test_crc_rssi_extraction();

    if (failures == 0)
    {
        printf("test_bench_pkt: ALL PASS\n");
        return 0;
    }
    printf("test_bench_pkt: %d FAILURES\n", failures);
    return 1;
}