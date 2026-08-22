/* rp2040_bench console-core dispatcher tests — BENCH-CONSOLE-SPEC (HARM-T5).
 * Drives the host-testable core through the io/radio seams: exact reply
 * strings, role/arming state machine, PA cap + outdoor unlock, band check,
 * START semantics per role, TX burst accounting, RX PKT/STAT lines, BUF
 * staging binary phase. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include "rp2040_bench.h"
#include "buffer.h"

static int fails = 0;
#define CHECK(cond, msg) do { if (!(cond)) { printf("FAIL: %s (line %d)\n", msg, __LINE__); fails++; } } while (0)

/* ---- Fake console: capture everything put() emits -------------------- */
static char out[16384];
static size_t out_len;
static void fake_put(const char* s)
{
    size_t n = strlen(s);
    if (out_len + n < sizeof(out)) { memcpy(out + out_len, s, n); out_len += n; out[out_len] = 0; }
    else out[sizeof(out) - 1] = 0;
}
static void out_reset(void) { out_len = 0; out[0] = 0; }

/* Last emitted line (no trailing newline handling beyond the final line). */
static const char* last_line(void)
{
    const char* p = out;
    const char* last = out;
    while ((p = strstr(p, "\n")) != NULL) { last = p + 1; p++; }
    return last;
}
static int line_count(void)
{
    int n = 0;
    for (const char* p = out; *p; p++) if (*p == '\n') n++;
    return n;
}
static bool has_line(const char* prefix)
{
    size_t n = strlen(prefix);
    const char* p = out;
    while (p && *p) {
        if (strncmp(p, prefix, n) == 0 && (p[n] == '\n' || p[n] == 0)) return true;
        p = strstr(p, "\n");
        if (p) p++;
    }
    return false;
}

/* ---- Fake clock ------------------------------------------------------ */
static uint32_t fake_us;
static uint32_t fake_micros(void) { return fake_us; }

/* ---- Fake binary byte source ------------------------------------------ */
static uint8_t bin_bytes[4096];
static uint16_t bin_n, bin_pos;
static int fake_getchar_ms(uint16_t ms)
{
    (void)ms;
    if (bin_pos < bin_n) return bin_bytes[bin_pos++];
    return -1;
}

/* ---- Fake radio -------------------------------------------------------- */
static int cfg_configure_calls, rearm_calls, standby_calls, sleep_calls, tx_calls;
static uint16_t cfg_last_len, rearm_last_len, tx_last_len;
static bench_cfg_t cfg_last;
static uint8_t tx_payloads[64][511];
static uint32_t tx_seqs[64];
static bool radio_asleep, tx_ok = true;

static void fr_configure(const bench_cfg_t* c, uint16_t len)
{
    cfg_configure_calls++; cfg_last = *c; cfg_last_len = len; radio_asleep = false;
}
static void fr_rearm(const bench_cfg_t* c, uint16_t len)
{
    (void)c; rearm_calls++; rearm_last_len = len; radio_asleep = false;
}
static bool fr_tx(const uint8_t* payload, uint16_t len)
{
    if (tx_calls < 64) { memcpy(tx_payloads[tx_calls], payload, len); tx_seqs[tx_calls] = ((uint32_t)payload[0]<<24)|((uint32_t)payload[1]<<16)|((uint32_t)payload[2]<<8)|payload[3]; }
    tx_calls++; tx_last_len = len;
    return tx_ok;
}
static void fr_standby(void) { standby_calls++; }
static void fr_sleep(void) { sleep_calls++; radio_asleep = true; }
static bool fr_asleep(void) { return radio_asleep; }

static const bench_radio_ops_t fake_radio = {
    fr_configure, fr_rearm, fr_tx, fr_standby, fr_sleep, fr_asleep,
};

static const bench_io_t fake_io = {
    fake_put, fake_micros, fake_getchar_ms, &fake_radio,
};

static void feed(const char* line)
{
    out_reset();
    bench_rp2040_feed_line(line);
}

/* Reset the whole world between test groups. */
static void world_reset(void)
{
    out_reset();
    fake_us = 0;
    bin_n = bin_pos = 0;
    cfg_configure_calls = rearm_calls = standby_calls = sleep_calls = tx_calls = 0;
    cfg_last_len = rearm_last_len = tx_last_len = 0;
    memset(&cfg_last, 0, sizeof(cfg_last));
    radio_asleep = false; tx_ok = true;
    bench_rp2040_init(&fake_io, "abc1234");
}

int main(void)
{
    /* ---- Golden self-test (spec §4/§5) ---- */
    CHECK(bench_rp2040_selftest_golden(), "golden self-test passes");

    /* ---- Boot identity ---- */
    world_reset();
    feed("ID?");
    CHECK(strcmp(last_line(),
        "ID RP2040BENCH v1.0 fw=abc1234 role=NONE armed=0 mod=flrc br=650000 "
        "freq=868000000 band=863-870/2440MHZ pa=10 pcap=+10dBm chip=2.1 "
        "radio=awake boot=power-on buf=0") == 0, "ID? exact at boot");

    /* Case-insensitive parser. */
    feed("id?");
    CHECK(strncmp(last_line(), "ID RP2040BENCH", 14) == 0, "parser case-insensitive");

    /* ---- ROLE transitions + arming ---- */
    feed("ROLE TX");
    CHECK(strcmp(last_line(), "OK ROLE TX (TX INHIBITED - SEND 'ARM TX' TO ENABLE)") == 0, "ROLE TX reply");
    CHECK(cfg_configure_calls == 1, "ROLE TX reconfigures radio");

    feed("ARM TX");
    CHECK(strcmp(last_line(), "OK ARMED (TX ENABLED)") == 0, "ARM TX on TX role");

    /* Role change clears arming (two-step safety). */
    feed("ROLE NONE");
    CHECK(strcmp(last_line(), "OK ROLE NONE (RADIO ASLEEP)") == 0, "ROLE NONE reply");
    CHECK(sleep_calls == 1, "ROLE NONE sleeps radio");
    feed("ROLE TX");
    feed("START n=2 len=32 gap_us=1000");
    CHECK(strcmp(last_line(), "ERR NOT ARMED (SEND 'ARM TX')") == 0, "arming cleared on role change");

    /* ARM TX requires TX role. */
    feed("ROLE RX");
    CHECK(strcmp(last_line(), "OK ROLE RX (CONTINUOUS)") == 0, "ROLE RX reply");
    feed("ARM TX");
    CHECK(strcmp(last_line(), "ERR ROLE NOT TX") == 0, "ARM TX on RX role rejected");

    /* ---- PA cap: indoor +10, outdoor unlock +22 ---- */
    world_reset();
    feed("ROLE TX");
    feed("MOD flrc br=650000 dbm=11");
    CHECK(strcmp(last_line(), "ERR RANGE (INDOOR CAP 0-10 DBM; UNLOCK: POWER MODE OUTDOOR 2026)") == 0,
          "MOD flrc dbm=11 indoor rejected");
    feed("POWER MODE OUTDOOR 2025");
    CHECK(strcmp(last_line(), "ERR PIN") == 0, "outdoor wrong pin");
    feed("POWER MODE OUTDOOR 2026");
    CHECK(strncmp(last_line(), "OK POWER MODE OUTDOOR PIN 2026 ACCEPTED", 39) == 0, "outdoor unlock");
    feed("MOD flrc br=650000 dbm=22");
    CHECK(strcmp(last_line(), "OK MOD flrc br=650000 pa=22") == 0, "dbm=22 after unlock");
    feed("MOD flrc br=650000 dbm=23");
    CHECK(strcmp(last_line(), "ERR RANGE (0-22 DBM)") == 0, "dbm=23 rejected after unlock");

    feed("PA 23");
    CHECK(strcmp(last_line(), "ERR RANGE (0-22 DBM)") == 0, "PA 23 rejected");
    feed("PA -1");
    CHECK(strncmp(last_line(), "ERR RANGE (INDOOR", 17) != 0, "PA -1 after unlock -> plain RANGE");
    feed("PA 22");
    CHECK(strcmp(last_line(), "OK PA 22 DBM") == 0, "PA 22 after unlock");

    world_reset();
    feed("PA 11");
    CHECK(strcmp(last_line(), "ERR RANGE (INDOOR CAP 0-10 DBM; UNLOCK: POWER MODE OUTDOOR 2026)") == 0,
          "PA 11 indoor rejected");
    feed("PA 10");
    CHECK(strcmp(last_line(), "OK PA 10 DBM") == 0, "PA 10 indoor ok");
    CHECK(cfg_last.txpow_dbm == 10, "PA applied to cfg");

    /* ---- MOD lora ---- */
    world_reset();
    feed("MOD lora sf=7 bw=125000");
    CHECK(strcmp(last_line(), "OK MOD lora sf=7 bw=125000") == 0, "MOD lora reply");
    CHECK(cfg_last.mod == BENCH_MOD_LORA && cfg_last.sf == 7 && cfg_last.bw_hz == 125000UL, "MOD lora cfg");
    feed("MOD lora sf=13 bw=125000");
    CHECK(strncmp(last_line(), "ERR ", 4) == 0, "MOD lora sf=13 rejected");

    /* ---- FREQ band enforcement ---- */
    world_reset();
    feed("FREQ 868500000");
    CHECK(strcmp(last_line(), "OK FREQ 868500000") == 0, "FREQ 868.5 ok");
    feed("FREQ 915000000");
    CHECK(strcmp(last_line(), "ERR BAND (863-870MHZ OR 2440MHZ ONLY)") == 0, "FREQ 915 rejected");
    feed("FREQ 2440000000");
    CHECK(strcmp(last_line(), "OK FREQ 2440000000") == 0, "FREQ 2440 point ok");
    feed("FREQ 862000000");
    CHECK(strncmp(last_line(), "ERR BAND", 8) == 0, "FREQ 862 rejected");

    /* ---- START semantics ---- */
    world_reset();
    feed("START n=10 len=32 gap_us=1000");
    CHECK(strcmp(last_line(), "ERR ROLE NOT TX") == 0, "START with role NONE");

    feed("ROLE RX");
    feed("START n=10 len=511 gap_us=1000");
    CHECK(strcmp(last_line(), "OK RX ARMED len=511") == 0, "START on RX board");
    CHECK(rearm_last_len == 511, "RX rearm len=511");

    world_reset();
    feed("ROLE TX");
    feed("START n=10 len=32 gap_us=1000");
    CHECK(strcmp(last_line(), "ERR NOT ARMED (SEND 'ARM TX')") == 0, "START unarmed");

    feed("ARM TX");
    feed("MOD lora sf=7 bw=125000");
    feed("START n=10 len=300 gap_us=1000");
    CHECK(strcmp(last_line(), "ERR LEN (MAX 255 LORA / 511 FLRC)") == 0, "LoRa len 300 rejected");

    /* ---- TX burst: PRBS source, pacing, TX DONE ---- */
    feed("MOD flrc br=650000 dbm=10");
    feed("SESSION 42");
    CHECK(strcmp(last_line(), "OK SESSION 42") == 0, "SESSION reply");
    feed("CONFIG 7 3");
    CHECK(line_count() == 2, "CONFIG emits OK + CONFIG_START");
    CHECK(strncmp(last_line(), "CONFIG_START,7,3,", 17) == 0, "CONFIG_START marker");

    out_reset();
    feed("START n=3 len=32 gap_us=1000");
    CHECK(strcmp(last_line(), "OK START n=3 len=32 gap_us=1000 src=PRBS") == 0, "START reply src=PRBS");
    CHECK(cfg_last_len == 32, "TX configure len=32");

    fake_us += 1000; bench_rp2040_poll();   /* pkt 0 */
    fake_us += 1000; bench_rp2040_poll();   /* pkt 1 */
    fake_us += 1000; bench_rp2040_poll();   /* pkt 2 -> done */
    CHECK(tx_calls == 3, "burst sent 3 packets");
    CHECK(tx_seqs[0] == 0 && tx_seqs[1] == 1 && tx_seqs[2] == 2, "TX seq 0,1,2");
    CHECK(tx_last_len == 32, "TX payload len 32");
    CHECK(has_line("TX DONE (RADIO ASLEEP)"), "TX DONE emitted");
    CHECK(sleep_calls == 1, "radio slept after burst");
    CHECK(radio_asleep, "is_asleep after burst");

    /* STAT? after TX session: sent=3 sent_ok=3. */
    out_reset();
    feed("STAT?");
    CHECK(strncmp(last_line(), "STAT role=TX sent=3 sent_ok=3 rx=0 crc_err=0 per_x1e6=0 ", 59) == 0,
          "STAT? TX accounting");
    CHECK(strstr(last_line(), "session=42 config=7 replicate=3") != NULL, "STAT? session/config");
    CHECK(strstr(last_line(), "gap_us=1000") != NULL, "STAT? gap_us");
    CHECK(strstr(last_line(), "per_ci_x1e6=") == NULL, "no per_ci without RX seq");

    /* ---- TX timeout backstop ---- */
    world_reset();
    feed("ROLE TX"); feed("ARM TX");
    tx_ok = false;   /* fake radio never confirms TX_DONE */
    feed("START n=2 len=32 gap_us=1000");
    fake_us += 1000; bench_rp2040_poll();
    fake_us += RP2040_BENCH_TX_TIMEOUT_US; bench_rp2040_poll();
    CHECK(has_line("ERR TX-TIMEOUT SEQ=0 (BURST ABORTED)"), "TX timeout backstop aborts");

    /* ---- STOP ---- */
    world_reset();
    feed("ROLE TX"); feed("ARM TX");
    feed("START n=1000 len=32 gap_us=1000");
    fake_us += 1000; bench_rp2040_poll();
    feed("STOP");
    CHECK(strcmp(last_line(), "OK STOP (RADIO ASLEEP)") == 0, "STOP reply");
    fake_us += 100000; bench_rp2040_poll();
    CHECK(tx_calls == 1, "no TX after STOP");

    /* ---- RX events: PKT rows + STAT? accounting ---- */
    world_reset();
    feed("ROLE RX");
    feed("SESSION 11"); feed("CONFIG 5 0");
    feed("MOD flrc br=650000 dbm=10");
    feed("START n=10 len=32 gap_us=1000");
    feed("PRBS ON");

    out_reset();
    uint8_t p[32];
    extern void bench_payload_build(uint8_t*, uint32_t, uint32_t);
    bench_payload_build(p, 32, 0);
    bench_rp2040_rx_event(p, 32, -143, 0, true);          /* seq 0, -71.5 dBm */
    bench_payload_build(p, 32, 1);
    bench_rp2040_rx_event(p, 32, -101, 0, true);          /* seq 1, -50.5 dBm */
    bench_rp2040_rx_event(NULL, 0, -121, 0, false);       /* CRC fail, -60.5 dBm */
    CHECK(line_count() == 3, "three PKT lines");

    /* CRC-fail row: seq=0 len=0 pcrc16=0 but rssi populated. */
    {
        const char* l3 = last_line();
        CHECK(strncmp(l3, "PKT,11,5,0,0,", 13) == 0, "crc-fail row seq=0");
        CHECK(strstr(l3, ",-60,0,0,0,0,") != NULL, "crc-fail row rssi populated");
        CHECK(strstr(l3, ",32,0,0,0,0,0,0,0") == NULL, "crc-fail row len=0");
    }

    out_reset();
    feed("STAT?");
    CHECK(strncmp(last_line(), "STAT role=RX sent=10 sent_ok=0 rx=2 crc_err=1 per_x1e6=0 ", 58) == 0,
          "STAT? RX accounting");
    CHECK(strstr(last_line(), "per_ci_x1e6=[") != NULL, "per_ci present with RX seq");
    CHECK(strstr(last_line(), "rssi_avg_dbm=-61.0") != NULL, "rssi avg over 3 samples");
    CHECK(strstr(last_line(), "rssi_min_dbm=-71.5") != NULL, "rssi min");
    CHECK(strstr(last_line(), "rssi_max_dbm=-50.5") != NULL, "rssi max");
    CHECK(strstr(last_line(), "cr=1") != NULL, "cr field");
    CHECK(strstr(last_line(), "buf=0") != NULL, "buf field");

    /* PRBS verification: corrupted payload -> bit_err counted (PRBS ON). */
    out_reset();
    bench_payload_build(p, 32, 2);
    p[10] ^= 0x0F;
    bench_rp2040_rx_event(p, 32, -143, 0, true);
    CHECK(strstr(out, ",4,") != NULL, "crc_ok column");
    CHECK(strstr(last_line(), ",0,1,4,1,868000000,FLRC,") != NULL, "bit_err=4 bytes_bad=1 in PKT");

    /* PRBS OFF: bit errors not computed (0/0). */
    feed("PRBS OFF");
    out_reset();
    bench_payload_build(p, 32, 3);
    p[10] ^= 0x0F;
    bench_rp2040_rx_event(p, 32, -143, 0, true);
    CHECK(strstr(last_line(), ",0,1,0,0,868000000,FLRC,") != NULL, "PRBS OFF -> no bit_err");

    /* ---- HELP ---- */
    feed("HELP");
    CHECK(strncmp(last_line(), "CMDS:", 5) == 0, "HELP single CMDS: line");

    /* ---- Unknown / malformed ---- */
    feed("FOO");
    CHECK(strcmp(last_line(), "ERR UNKNOWN") == 0, "unknown command");
    feed("MOD flrc");
    CHECK(strncmp(last_line(), "ERR ", 4) == 0, "MOD flrc missing args");

    /* ---- BUF staging ---- */
    world_reset();
    feed("BUF CLEAR");
    CHECK(strcmp(last_line(), "OK BUF 0") == 0, "BUF CLEAR");
    feed("BUF STATUS");
    CHECK(strcmp(last_line(), "BUF len=0 crc=0000 drops=0") == 0, "BUF STATUS empty");

    /* BUF LOAD while TX armed -> gate rejects before binary phase. */
    feed("ROLE TX"); feed("ARM TX");
    feed("BUF LOAD 4 29B1");
    CHECK(strncmp(last_line(), "ERR ", 4) == 0, "BUF LOAD gated when armed");
    CHECK(!bench_rp2040_binary_active(), "no binary phase after gate reject");

    world_reset();
    feed("ROLE TX");   /* unarmed: load allowed */
    out_reset();
    bin_bytes[0] = 1; bin_bytes[1] = 2; bin_bytes[2] = 3; bin_bytes[3] = 4;
    bin_n = 4; bin_pos = 0;
    feed("BUF LOAD 4 3D9A");   /* crc16_ccitt_false(01 02 03 04) — wrong on purpose first */
    CHECK(strcmp(last_line(), "OK BINARY 4") == 0, "binary ack");
    CHECK(bench_rp2040_binary_active(), "binary phase active");
    bench_rp2040_poll();   /* drains the fake source */
    CHECK(has_line("ERR CRC"), "bad crc rejected");
    CHECK(!bench_rp2040_binary_active(), "binary phase closed");
    feed("BUF STATUS");
    CHECK(strncmp(last_line(), "BUF len=0", 9) == 0, "buffer cleared after crc mismatch");

    /* Correct CRC: compute it host-side with the vendored crc16. */
    out_reset();
    bin_pos = 0; bin_n = 4;
    char cmd[64];
    snprintf(cmd, sizeof(cmd), "BUF LOAD 4 %04X", crc16_ccitt_false(bin_bytes, 4));
    feed(cmd);
    bench_rp2040_poll();
    CHECK(has_line("OK BUF 4 1"), "good crc accepted");
    feed("BUF STATUS");
    CHECK(strncmp(last_line(), "BUF len=4", 9) == 0, "buffer staged len=4");

    /* START with staged buffer uses src=BUF. */
    feed("ARM TX");
    out_reset();
    feed("START n=2 len=4 gap_us=1000");
    CHECK(strcmp(last_line(), "OK START n=2 len=4 gap_us=1000 src=BUF") == 0, "src=BUF");
    fake_us += 1000; bench_rp2040_poll();
    fake_us += 1000; bench_rp2040_poll();
    CHECK(tx_calls >= 2 && tx_payloads[0][0] == 1 && tx_payloads[0][3] == 4, "TX payload from staged buf");

    if (fails == 0) { printf("test_rp2040_bench: PASS\n"); return 0; }
    printf("test_rp2040_bench: %d FAILURES\n", fails);
    return 1;
}
