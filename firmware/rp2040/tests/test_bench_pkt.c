/* PKT/CONFIG_START line format — 25 columns (BUF-T5a pcrc16), spec §3 (RED). */
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include "bench_pkt.h"
#include "bench_payload.h"
#include "buffer.h"

static int fails = 0;
#define CHECK(cond, msg) do { if (!(cond)) { printf("FAIL: %s\n", msg); fails++; } } while (0)

static int count_columns(const char* line)
{
    int cols = 1;
    for (const char* p = line; *p; p++)
        if (*p == ',') cols++;
    return cols;
}

int main(void)
{
    bench_pkt_ctx_t ctx = { .session_id = 7, .config_id = 3, .replicate = 2 };
    bench_pkt_evt_t evt;
    char buf[256];

    memset(&evt, 0, sizeof(evt));
    evt.seq = 0; evt.len = 32; evt.rssi_half_dbm = -143; evt.snr_qdb = 0;
    evt.mod = BENCH_PKT_MOD_FLRC; evt.sf = 9; evt.bw_hz = 0;
    evt.freq_hz = 868000000UL; evt.txpow_dbm = 10; evt.cr = 1; evt.ts_ms = 1234;
    evt.bit_err = 0; evt.bytes_bad = 0;

    /* Build the real 32-B payload to get the golden pcrc16 (0x997E = 39294). */
    uint8_t p[32];
    bench_payload_build(p, 32, 0);
    evt.pcrc16 = crc16_ccitt_false(p, 32);

    int n = bench_pkt_format(buf, sizeof(buf), &ctx, &evt, 1);

    /* 25 columns: PKT + 24 fields. rssi -143 half-dBm -> -71 dBm (integer).
     * mod is UPPERCASE per spec §3 ("LORA"/"FLRC"). */
    const char* expect = "PKT,7,3,2,0,1234,-71,0,1,0,0,868000000,FLRC,9,0,1,10,32,0,0,0,0,0,0,39294";
    CHECK(strcmp(buf, expect) == 0, "PKT line exact (25 cols, pcrc16 decimal)");
    CHECK(n == (int)strlen(expect), "PKT line return length");
    CHECK(count_columns(buf) == 25, "PKT line has 25 columns");

    /* CRC-failed row: seq=0 len=0 bit_err=0 bytes_bad=0 pcrc16=0, rssi kept. */
    memset(&evt, 0, sizeof(evt));
    evt.rssi_half_dbm = -101; evt.mod = BENCH_PKT_MOD_FLRC;
    evt.freq_hz = 868000000UL; evt.txpow_dbm = 10; evt.cr = 1; evt.ts_ms = 5;
    bench_pkt_format(buf, sizeof(buf), &ctx, &evt, 0);
    CHECK(strcmp(buf, "PKT,7,3,2,0,5,-50,0,0,0,0,868000000,FLRC,0,0,1,10,0,0,0,0,0,0,0,0") == 0,
          "CRC-fail PKT row semantics");

    /* LoRa row: sf/bw populated, mod=lora, snr carried. */
    memset(&evt, 0, sizeof(evt));
    evt.seq = 42; evt.len = 255; evt.rssi_half_dbm = -240; evt.snr_qdb = 36;
    evt.mod = BENCH_PKT_MOD_LORA; evt.sf = 10; evt.bw_hz = 125000UL;
    evt.freq_hz = 868000000UL; evt.txpow_dbm = 8; evt.cr = 5; evt.ts_ms = 99;
    evt.pcrc16 = 0x29B1;
    bench_pkt_format(buf, sizeof(buf), &ctx, &evt, 1);
    CHECK(strcmp(buf, "PKT,7,3,2,42,99,-120,9,1,0,0,868000000,LORA,10,125,5,8,255,0,0,0,0,0,0,10673") == 0,
          "LoRa PKT row (snr 9 dB, bw 125 kHz)");

    /* CONFIG_START marker. */
    n = bench_pkt_config_start(buf, sizeof(buf), &ctx, 777);
    CHECK(strcmp(buf, "CONFIG_START,3,2,777") == 0, "CONFIG_START line");
    CHECK(n == 20, "CONFIG_START length");

    if (fails == 0) { printf("test_bench_pkt: PASS\n"); return 0; }
    printf("test_bench_pkt: %d FAILURES\n", fails);
    return 1;
}
