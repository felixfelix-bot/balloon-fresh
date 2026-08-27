/**
 * @file    rp2040_bench.c
 * @brief   RP2040BENCH console core — host-testable bench firmware (HARM-T5).
 *
 * Implements the BENCH-CONSOLE-SPEC minimum set on the two seams declared in
 * rp2040_bench.h (bench_io_t console/clock/binary-source, bench_radio_ops_t
 * raw-SPI radio). The identical object code runs in the RP2040 firmware and
 * in the host unit tests.
 *
 * Port policy (spec §11): bench_cmd.c / bench_pkt.c / bench_payload.c /
 * bench_stats.c / prbs.c / buffer.c are vendored VERBATIM from E80; this file
 * is the adapted harness (role state machine, PA cap, START/STOP, STAT?
 * accounting, ID? population) mirroring E80 bench.c behaviour:
 *   - RSSI fold on RX_OK only, sum kept by this core (E80 bench.c:991-994 —
 *     bench_stats_note_rssi's first sample only seeds min/max, so the sum is
 *     folded here exactly like E80 does).
 *   - STAT? field order per spec §2.10.
 *
 * Local quirks (documented in docs/RP2040BENCH-PORT.md):
 *   - Parse-level E_RANGE is reported as "ERR RANGE (0-22 DBM)": the vendored
 *     parser's only decorated range envelope is the PA dbm window, and the
 *     spec §2.4 reply for an over-envelope dbm is that exact string.
 *   - Vendor extensions PRBS9 / FLASH / BAND OVERRIDE are omitted (spec §2.13
 *     "porters MAY implement or omit"); they answer with an explicit ERR
 *     instead of pretending to act.
 */

#include "rp2040_bench.h"

#include <stdio.h>
#include <string.h>

#include "bench_payload.h"
#include "bench_pkt.h"
#include "bench_stats.h"
#include "buffer.h"

/* ---- Internal state -------------------------------------------------------- */

typedef enum { RROLE_NONE = 0, RROLE_TX, RROLE_RX } rrole_t;

#define BUF_IDLE_TIMEOUT_MS 1000u   /* binary-phase 1.0 s idle rule (spec §2.13) */

static const bench_io_t* IO;
static char       FW_SHA7[8];
static rrole_t    role;
static bool       armed;            /* ARM TX latch (cleared by ROLE change) */
static bool       outdoor;          /* POWER MODE OUTDOOR 2026 accepted */
static bool       prbs_verify;      /* PRBS ON|OFF — RX verification (default OFF) */
static bench_cfg_t cfg;

static bench_pkt_ctx_t pkt_ctx;     /* session/config/replicate for PKT lines */

static bool     session_open;
static uint32_t t_start_us, t_stop_us;

static uint32_t n_pkts, len_bytes, gap_us;   /* last START parameters */
static uint16_t rx_len;                      /* RX FIX_LEN window */

static bench_stats_t stats;

/* TX burst */
static bool     burst;
static uint32_t tx_seq;
static uint32_t t_next_tx_us;
static bool     tx_waiting;                  /* tx_packet returned false */
static uint32_t tx_deadline_us;

/* BUF binary phase */
static bool     binary_phase;
static uint16_t bin_crc_expected;
static uint16_t bin_expected_n;
static uint16_t bin_got;

/* ---- Small helpers --------------------------------------------------------- */

static void emit(const char* s)
{
    IO->put("\n");   /* LF-only line framing; terminator precedes the text   */
    IO->put(s);
}

static uint32_t now_us(void) { return IO->micros(); }

static void apply_cfg(void)
{
    /* Reconfigure (and park in standby) even from role NONE: the console
     * applies MOD/FREQ/PA immediately; ROLE RX re-arms continuous RX on
     * top of this via rearm_rx. */
    IO->radio->reset_configure(&cfg, (uint16_t)len_bytes);
}

/* Signed tenths -> "-61.0" style decimal string. */
static void fmt_dec1(char* dst, size_t dstsz, int32_t tenths)
{
    int32_t a = tenths < 0 ? -tenths : tenths;
    snprintf(dst, dstsz, "%s%ld.%ld", tenths < 0 ? "-" : "",
             (long)(a / 10), (long)(a % 10));
}

/* ---- Init ------------------------------------------------------------------- */

void bench_rp2040_init(const bench_io_t* io, const char* fw_sha7)
{
    IO = io;
    strncpy(FW_SHA7, fw_sha7 ? fw_sha7 : "0000000", sizeof FW_SHA7 - 1);
    FW_SHA7[sizeof FW_SHA7 - 1] = 0;

    role = RROLE_NONE;
    armed = false;
    outdoor = false;
    prbs_verify = false;

    memset(&cfg, 0, sizeof cfg);
    cfg.mod        = BENCH_MOD_FLRC;
    cfg.br_bps     = 650000;                 /* spec §8 default 650 kbps      */
    cfg.cr         = 1;                      /* FLRC 3/4 (fw code 1)          */
    cfg.txpow_dbm  = 10;                     /* indoor cap                    */
    cfg.freq_hz    = 868000000UL;
    cfg.sf         = 7;
    cfg.bw_hz      = 125000;

    memset(&pkt_ctx, 0, sizeof pkt_ctx);
    session_open = false;
    t_start_us = t_stop_us = 0;

    n_pkts = 100; len_bytes = 255; gap_us = 5000;   /* START defaults (§2.7)  */
    rx_len = 0;
    memset(&stats, 0, sizeof stats);

    burst = false;
    tx_seq = 0;
    t_next_tx_us = 0;
    tx_waiting = false;
    tx_deadline_us = 0;

    binary_phase = false;
    bin_crc_expected = 0;

    bench_stats_reset(&stats);
    buf_clear();
}

/* ---- TX burst engine -------------------------------------------------------- */

static void session_close(uint32_t now)
{
    session_open = false;
    t_stop_us = now;
}

static void burst_finish(void)
{
    uint32_t now = now_us();
    burst = false;
    tx_waiting = false;
    IO->radio->sleep_now();
    session_close(now);
    emit("TX DONE (RADIO ASLEEP)");
}

static void burst_abort_timeout(void)
{
    char b[48];
    burst = false;
    tx_waiting = false;
    IO->radio->sleep_now();
    session_close(now_us());
    snprintf(b, sizeof b, "ERR TX-TIMEOUT SEQ=%lu (BURST ABORTED)",
             (unsigned long)tx_seq);
    emit(b);
}

static void tx_send_current(void)
{
    static uint8_t pkt[RP2040_BENCH_LEN_MAX_FLRC];
    uint16_t plen = (uint16_t)len_bytes;

    if (buf_len() > 0)
        buf_read(tx_seq * (uint32_t)plen, pkt, plen);   /* staged A/B payload */
    else
        bench_payload_build(pkt, plen, tx_seq);          /* seq header + PRBS */

    if (IO->radio->tx_packet(pkt, plen))
    {
        stats.tx_done++;
        tx_seq++;
        if (tx_seq >= n_pkts)
            burst_finish();
        else
            t_next_tx_us = now_us() + gap_us;
    }
    else
    {
        /* No TX_DONE yet: the 5 s core backstop aborts the burst if the
         * radio op never confirms (op itself guards with 500 ms BUSY). */
        tx_waiting = true;
        tx_deadline_us = now_us() + RP2040_BENCH_TX_TIMEOUT_US;
    }
}

/* ---- Poll -------------------------------------------------------------------- */

void bench_rp2040_poll(void)
{
    uint32_t now;

    /* Binary BUF phase owns the poll loop while active (spec §2.13).
     * Drain everything the source offers; one 1.0 s idle gap ends it. */
    if (binary_phase)
    {
        for (;;)
        {
            int c = IO->getchar_ms(BUF_IDLE_TIMEOUT_MS);
            if (c < 0)
            {
                binary_phase = false;
                buf_load_abort();
                emit("ERR TIMEOUT");
                return;
            }
            buf_load_byte((uint8_t)c);
            if (++bin_got >= bin_expected_n)
            {
                char b[32];
                binary_phase = false;
                if (buf_load_commit(bin_crc_expected))
                {
                    snprintf(b, sizeof b, "OK BUF %u 1", (unsigned)buf_len());
                    emit(b);
                }
                else
                {
                    emit("ERR CRC");
                }
                return;
            }
        }
    }

    if (burst && !tx_waiting)
    {
        now = now_us();
        if ((int32_t)(now - t_next_tx_us) >= 0)
            tx_send_current();
    }
    else if (burst && tx_waiting)
    {
        now = now_us();
        if ((int32_t)(now - tx_deadline_us) >= 0)
            burst_abort_timeout();
    }
}

/* ---- RX events ---------------------------------------------------------------- */

void bench_rp2040_rx_event(const uint8_t* payload, uint16_t len,
                           int16_t rssi_half_dbm, int8_t snr_qdb, bool crc_ok)
{
    bench_pkt_evt_t evt;
    char line[192];

    memset(&evt, 0, sizeof evt);
    evt.rssi_half_dbm = rssi_half_dbm;
    evt.snr_qdb       = snr_qdb;
    evt.mod           = (cfg.mod == BENCH_MOD_LORA) ? BENCH_PKT_MOD_LORA
                                                    : BENCH_PKT_MOD_FLRC;
    evt.sf            = cfg.sf;
    evt.bw_hz         = (cfg.mod == BENCH_MOD_LORA) ? cfg.bw_hz : 0;
    evt.freq_hz       = cfg.freq_hz;
    evt.txpow_dbm     = cfg.txpow_dbm;
    evt.cr            = cfg.cr;
    evt.ts_ms         = now_us() / 1000;

    if (crc_ok && payload != NULL && len > 0)
    {
        uint16_t bytes_bad = 0;
        uint32_t seq = bench_payload_seq(payload);

        evt.seq   = seq;
        evt.len   = len;
        evt.pcrc16 = crc16_ccitt_false(payload, len);
        if (prbs_verify)
            evt.bit_err = bench_payload_verify(payload, len, seq, &bytes_bad);
        evt.bytes_bad = bytes_bad;

        stats.rx_ok++;
        stats.rx_bytes += len;
        /* RSSI/SNR fold on RX_OK only; sum folded here like E80 bench.c. */
        stats.rssi_sum_half += rssi_half_dbm;
        bench_stats_note_rssi(&stats, rssi_half_dbm);
        stats.snr_sum_qdb += snr_qdb;
        if (!stats.rx_seq_valid)
        {
            stats.rx_first_seq = seq;
            stats.rx_seq_valid = true;
        }
        if (seq > stats.rx_last_seq)
            stats.rx_last_seq = seq;
    }
    else
    {
        stats.rx_crc_err++;
        /* CRC-fail row: seq=0 len=0 bit_err=0 bytes_bad=0 pcrc16=0,
         * rssi/snr still populated (spec §3). evt is already zeroed. */
    }

    bench_pkt_format(line, sizeof line, &pkt_ctx, &evt, crc_ok ? 1 : 0);
    emit(line);
}

/* ---- Command dispatch ---------------------------------------------------------- */

static void cmd_id(void)
{
    char b[256];
    char modpart[48];
    char cap[12];

    if (cfg.mod == BENCH_MOD_LORA)
        snprintf(modpart, sizeof modpart, "mod=lora sf=%u bw=%lu",
                 (unsigned)cfg.sf, (unsigned long)cfg.bw_hz);
    else
        snprintf(modpart, sizeof modpart, "mod=flrc br=%lu",
                 (unsigned long)cfg.br_bps);

    snprintf(cap, sizeof cap, "+%ddBm",
             outdoor ? RP2040_BENCH_TXPOW_MAX_DBM
                     : RP2040_BENCH_TXPOW_CAP_INDOOR_DBM);

    snprintf(b, sizeof b,
        "ID %s %s fw=%s role=%s armed=%d %s freq=%lu band=863-870/2440MHZ "
        "pa=%d pcap=%s chip=%s radio=%s boot=power-on buf=%u",
        RP2040_BENCH_BOARD_NAME, RP2040_BENCH_FW_VERSION, FW_SHA7,
        role == RROLE_TX ? "TX" : role == RROLE_RX ? "RX" : "NONE",
        armed ? 1 : 0,
        modpart,
        (unsigned long)cfg.freq_hz,
        (int)cfg.txpow_dbm, cap, RP2040_BENCH_CHIP_VERSION,
        IO->radio->is_asleep() ? "asleep" : "awake",
        (unsigned)buf_len());
    emit(b);
}

static void cmd_role(const bench_cmd_t* cmd)
{
    armed = false;                     /* any ROLE change clears the arm latch */
    burst = false;
    tx_waiting = false;

    if (cmd->role == BENCH_ROLE_TX)
    {
        role = RROLE_TX;
        bench_stats_reset(&stats);
        t_start_us = now_us();
        session_open = true;
        IO->radio->reset_configure(&cfg, (uint16_t)len_bytes);
        emit("OK ROLE TX (TX INHIBITED - SEND 'ARM TX' TO ENABLE)");
    }
    else if (cmd->role == BENCH_ROLE_RX)
    {
        role = RROLE_RX;
        bench_stats_reset(&stats);
        t_start_us = now_us();
        session_open = true;
        rx_len = (uint16_t)len_bytes;
        IO->radio->reset_configure(&cfg, rx_len);
        IO->radio->rearm_rx(&cfg, rx_len);   /* continuous RX immediately */
        emit("OK ROLE RX (CONTINUOUS)");
    }
    else
    {
        role = RROLE_NONE;
        session_close(now_us());
        IO->radio->sleep_now();
        emit("OK ROLE NONE (RADIO ASLEEP)");
    }
}

/* PA envelope check shared by MOD flrc and PA (spec §2.4). */
static bool pa_reject(int8_t dbm)
{
    if (outdoor)
    {
        if (dbm < 0 || dbm > RP2040_BENCH_TXPOW_MAX_DBM)
        {
            emit("ERR RANGE (0-22 DBM)");
            return true;
        }
    }
    else
    {
        if (dbm < 0 || dbm > RP2040_BENCH_TXPOW_CAP_INDOOR_DBM)
        {
            emit("ERR RANGE (INDOOR CAP 0-10 DBM; "
                 "UNLOCK: POWER MODE OUTDOOR 2026)");
            return true;
        }
    }
    return false;
}

static void cmd_start(const bench_cmd_t* cmd)
{
    char b[96];
    uint32_t n    = cmd->n_pkts;
    uint32_t len  = cmd->len_bytes;
    uint32_t gap  = cmd->gap_us;

    if (role == RROLE_NONE)
    {
        emit("ERR ROLE NOT TX");
        return;
    }

    if (role == RROLE_RX)
    {
        /* RX board: fix the FLRC/LoRa length window and re-arm continuous. */
        n_pkts    = n;               /* announced burst size (sent= in STAT?) */
        len_bytes = len;
        gap_us    = gap;
        rx_len = (uint16_t)len;
        bench_stats_reset(&stats);
        stats.tx_attempted = n;        /* announced burst size, for sent=      */
        t_start_us = now_us();
        session_open = true;
        IO->radio->rearm_rx(&cfg, rx_len);
        snprintf(b, sizeof b, "OK RX ARMED len=%lu", (unsigned long)rx_len);
        emit(b);
        return;
    }

    if (!armed)
    {
        emit("ERR NOT ARMED (SEND 'ARM TX')");
        return;
    }

    if (cfg.mod == BENCH_MOD_LORA && len > RP2040_BENCH_LEN_MAX_LORA)
    {
        emit("ERR LEN (MAX 255 LORA / 511 FLRC)");
        return;
    }

    n_pkts     = n;
    len_bytes  = len;
    gap_us     = gap;
    bench_stats_reset(&stats);
    stats.tx_attempted = n;
    t_start_us = now_us();
    session_open = true;
    IO->radio->reset_configure(&cfg, (uint16_t)len_bytes);

    burst     = true;
    tx_seq    = 0;
    tx_waiting = false;
    t_next_tx_us = t_start_us + gap_us;

    snprintf(b, sizeof b, "OK START n=%lu len=%lu gap_us=%lu src=%s",
             (unsigned long)n, (unsigned long)len, (unsigned long)gap,
             buf_len() > 0 ? "BUF" : "PRBS");
    emit(b);
}

static void cmd_stat(void)
{
    char b[320];
    char d[4][16];
    size_t off;
    uint32_t elapsed, per, kbps_val, lo = 0, hi = 0;
    uint32_t now = now_us();

    per = bench_stats_per_ppm(&stats);
    if (stats.rx_seq_valid)
        bench_stats_wilson_ppm(stats.rx_ok, stats.rx_ok + stats.rx_crc_err,
                               &lo, &hi);

    elapsed = session_open ? (now - t_start_us)
                           : bench_stats_elapsed_us(t_start_us, t_stop_us);
    kbps_val = bench_stats_kbps(
        role == RROLE_RX ? (uint64_t)stats.rx_bytes
                         : (uint64_t)stats.tx_done * len_bytes,
        elapsed);

    fmt_dec1(d[0], sizeof d[0], bench_stats_rssi_avg_half_dbm(&stats) * 5);
    fmt_dec1(d[1], sizeof d[1], bench_stats_rssi_min_half_dbm(&stats) * 5);
    fmt_dec1(d[2], sizeof d[2], bench_stats_rssi_max_half_dbm(&stats) * 5);
    fmt_dec1(d[3], sizeof d[3], bench_stats_snr_avg_cdb(&stats) / 10);

    off = (size_t)snprintf(b, sizeof b,
        "STAT role=%s sent=%lu sent_ok=%lu rx=%lu crc_err=%lu per_x1e6=%lu ",
        role == RROLE_TX ? "TX" : role == RROLE_RX ? "RX" : "NONE",
        (unsigned long)stats.tx_attempted, (unsigned long)stats.tx_done,
        (unsigned long)stats.rx_ok, (unsigned long)stats.rx_crc_err,
        (unsigned long)per);
    if (stats.rx_seq_valid)
        off += (size_t)snprintf(b + off, sizeof b - off,
                                "per_ci_x1e6=[%lu,%lu] ",
                                (unsigned long)lo, (unsigned long)hi);
    snprintf(b + off, sizeof b - off,
        "elapsed_s=%lu.%lu kbps=%lu rssi_avg_dbm=%s rssi_min_dbm=%s "
        "rssi_max_dbm=%s snr_avg_db=%s cr=%u session=%lu config=%lu "
        "replicate=%lu drops=%lu gap_us=%lu buf=%u",
        (unsigned long)(elapsed / 1000000UL),
        (unsigned long)((elapsed % 1000000UL) / 100000UL),
        (unsigned long)kbps_val,
        d[0], d[1], d[2], d[3],
        (unsigned)cfg.cr,
        (unsigned long)pkt_ctx.session_id, (unsigned long)pkt_ctx.config_id,
        (unsigned long)pkt_ctx.replicate,
        0UL,                                   /* event-mailbox drops: none */
        (unsigned long)gap_us, (unsigned)buf_len());
    emit(b);
}

static void cmd_buf_load(const bench_cmd_t* cmd)
{
    char b[32];
    buf_load_gate_t g = buf_load_gate(role == RROLE_RX, burst, armed);
    if (g != BUF_LOAD_OK)
    {
        emit(buf_load_gate_reply(g));
        return;
    }
    if (!buf_load_begin((uint16_t)cmd->buf_load_n))
    {
        emit("ERR ARG (BUF LOAD N)");
        return;
    }
    binary_phase = true;
    bin_crc_expected = cmd->buf_load_crc;
    bin_expected_n = (uint16_t)cmd->buf_load_n;
    bin_got = 0;
    snprintf(b, sizeof b, "OK BINARY %lu", (unsigned long)cmd->buf_load_n);
    emit(b);
}

void bench_rp2040_feed_line(const char* line)
{
    bench_cmd_t cmd;
    bench_cmd_err_t err;
    char b[96];

    err = bench_cmd_parse(line, &cmd);
    if (err != BENCH_CMD_OK)
    {
        if (err == BENCH_CMD_E_RANGE)
        {
            /* The parser's range envelope is the PA dbm window (0..22);
             * MOD flrc dbm out of window lands here too (test-pinned). */
            emit("ERR RANGE (0-22 DBM)");
        }
        else
        {
            snprintf(b, sizeof b, "ERR %s", bench_cmd_err_str(err));
            emit(b);
        }
        return;
    }

    switch (cmd.id)
    {
    case BENCH_CMD_ID:
        cmd_id();
        break;

    case BENCH_CMD_ROLE:
        cmd_role(&cmd);
        break;

    case BENCH_CMD_ARM_TX:
        if (role != RROLE_TX)
            emit("ERR ROLE NOT TX");
        else
        {
            armed = true;
            emit("OK ARMED (TX ENABLED)");
        }
        break;

    case BENCH_CMD_MOD:
        if (cmd.mod == BENCH_MOD_FLRC)
        {
            if (pa_reject(cmd.txpow_dbm))
                return;
            cfg.mod       = BENCH_MOD_FLRC;
            cfg.br_bps    = cmd.br_bps;
            cfg.txpow_dbm = cmd.txpow_dbm;
            cfg.cr        = 1;               /* FLRC 3/4 (fw code 1)          */
            apply_cfg();
            snprintf(b, sizeof b, "OK MOD flrc br=%lu pa=%d",
                     (unsigned long)cfg.br_bps, (int)cfg.txpow_dbm);
            emit(b);
        }
        else
        {
            cfg.mod   = BENCH_MOD_LORA;
            cfg.sf    = cmd.sf;
            cfg.bw_hz = cmd.bw_hz;
            cfg.cr    = 5;                   /* LoRa 4/5 denominator          */
            apply_cfg();
            snprintf(b, sizeof b, "OK MOD lora sf=%u bw=%lu",
                     (unsigned)cfg.sf, (unsigned long)cfg.bw_hz);
            emit(b);
        }
        break;

    case BENCH_CMD_FREQ:
        if ((cmd.freq_hz >= RP2040_BENCH_BAND_MIN_HZ &&
             cmd.freq_hz <= RP2040_BENCH_BAND_MAX_HZ) ||
            cmd.freq_hz == RP2040_BENCH_FREQ_2440_HZ)
        {
            cfg.freq_hz = cmd.freq_hz;
            apply_cfg();
            snprintf(b, sizeof b, "OK FREQ %lu", (unsigned long)cfg.freq_hz);
            emit(b);
        }
        else
        {
            emit("ERR BAND (863-870MHZ OR 2440MHZ ONLY)");
        }
        break;

    case BENCH_CMD_PA:
        if (pa_reject(cmd.txpow_dbm))
            return;
        cfg.txpow_dbm = cmd.txpow_dbm;
        apply_cfg();
        snprintf(b, sizeof b, "OK PA %d DBM", (int)cfg.txpow_dbm);
        emit(b);
        break;

    case BENCH_CMD_POWER_OUTDOOR:
        if (cmd.pin != RP2040_BENCH_OUTDOOR_PIN)
        {
            emit("ERR PIN");
        }
        else
        {
            outdoor = true;
            emit("OK POWER MODE OUTDOOR PIN 2026 ACCEPTED");
        }
        break;

    case BENCH_CMD_START:
        cmd_start(&cmd);
        break;

    case BENCH_CMD_STOP:
        burst = false;
        tx_waiting = false;
        if (buf_loading())
            buf_load_abort();
        binary_phase = false;
        session_close(now_us());
        IO->radio->sleep_now();
        emit("OK STOP (RADIO ASLEEP)");
        break;

    case BENCH_CMD_SESSION:
        pkt_ctx.session_id = cmd.session_id;
        snprintf(b, sizeof b, "OK SESSION %lu",
                 (unsigned long)pkt_ctx.session_id);
        emit(b);
        break;

    case BENCH_CMD_CONFIG:
        pkt_ctx.config_id = cmd.config_id;
        pkt_ctx.replicate = cmd.replicate;
        snprintf(b, sizeof b, "OK CONFIG %lu %lu",
                 (unsigned long)pkt_ctx.config_id,
                 (unsigned long)pkt_ctx.replicate);
        emit(b);
        bench_pkt_config_start(b, sizeof b, &pkt_ctx, now_us() / 1000);
        emit(b);
        break;

    case BENCH_CMD_STAT:
        cmd_stat();
        break;

    case BENCH_CMD_PRBS:
        prbs_verify = cmd.prbs_enable;
        emit(prbs_verify ? "OK PRBS ON" : "OK PRBS OFF");
        break;

    case BENCH_CMD_PRBS9:
        /* E80 vendor extension, omitted on this port (spec §2.13). */
        emit("ERR PRBS9 (NOT SUPPORTED ON RP2040BENCH)");
        break;

    case BENCH_CMD_FLASH:
        /* E80 vendor extension, omitted: use the physical BOOTSEL button. */
        emit("ERR FLASH (USE THE BOOTSEL BUTTON ON RP2040BENCH)");
        break;

    case BENCH_CMD_BAND_OVERRIDE:
        /* Fixed dual-band plan on this board (spec §9) — no override pin. */
        emit("ERR BAND OVERRIDE (NOT AVAILABLE ON RP2040BENCH)");
        break;

    case BENCH_CMD_HELP:
        emit("CMDS: ID? ROLE ARM TX MOD FREQ PA POWER MODE OUTDOOR START STOP "
             "SESSION CONFIG STAT? PRBS BUF HELP");
        break;

    case BENCH_CMD_BUF_CLEAR:
        buf_clear();
        emit("OK BUF 0");
        break;

    case BENCH_CMD_BUF_LOAD:
        cmd_buf_load(&cmd);
        break;

    case BENCH_CMD_BUF_STATUS:
        snprintf(b, sizeof b, "BUF len=%u crc=%04X drops=%lu",
                 (unsigned)buf_len(), (unsigned)buf_crc16(),
                 (unsigned long)buf_drops());
        emit(b);
        break;

    default:
        emit("ERR UNKNOWN");
        break;
    }
}

/* ---- Golden self-test (spec §4/§5 vectors) ---------------------------------- */

bool bench_rp2040_selftest_golden(void)
{
    uint8_t p[64];
    static const uint8_t fill_golden[8] =
        { 0xDD, 0xD8, 0xCC, 0xD2, 0xAA, 0xEF, 0xFE, 0x60 };
    static const char* nines = "123456789";
    uint8_t big[4096];
    uint32_t i;

    /* PRBS-15 fill bytes (seq 0 and seq 1 share the fill). */
    bench_payload_build(p, 12, 0);
    if (memcmp(p + 4, fill_golden, 8) != 0)
        return false;
    bench_payload_build(p, 12, 1);
    if (memcmp(p + 4, fill_golden, 8) != 0)
        return false;

    /* 32-byte payload pcrc16 pairs (§4). */
    bench_payload_build(p, 32, 0);
    if (crc16_ccitt_false(p, 32) != 0x997E)
        return false;
    bench_payload_build(p, 32, 1);
    if (crc16_ccitt_false(p, 32) != 0x6998)
        return false;

    /* CRC-16/CCITT-FALSE triples (§5). */
    if (crc16_ccitt_false((const uint8_t*)nines, 9) != 0x29B1)
        return false;
    memset(big, 0, sizeof big);
    if (crc16_ccitt_false(big, 64) != 0xD6DA)
        return false;
    for (i = 0; i < sizeof big; i++)
        big[i] = (uint8_t)(i % 256);
    if (crc16_ccitt_false(big, sizeof big) != 0x0F69)
        return false;

    return true;
}

/* ---- Introspection ------------------------------------------------------------ */

const bench_cfg_t* bench_rp2040_cfg(void) { return &cfg; }
bool bench_rp2040_role_is_rx(void)        { return role == RROLE_RX; }
uint16_t bench_rp2040_rx_len(void)        { return rx_len; }
bool bench_rp2040_binary_active(void)     { return binary_phase; }
