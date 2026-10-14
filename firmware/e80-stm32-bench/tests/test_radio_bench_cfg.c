/**
 * @file    test_radio_bench_cfg.c
 * @brief   Host unit tests: radio_bench_cfg_t struct fields (E80-4) and the
 *          exact FLRC SetPacketParams bytes radio_bench.c puts on the wire
 *          (FIX-T3).
 *
 * E80-4: verifies the cr (coding rate) field exists in radio_bench_cfg_t
 * so per-packet PKT output can include it.
 *
 * FIX-T3: host-compiles the REAL src/radio_bench.c against the REAL vendored
 * lr20xx_driver sources over a fake lr20xx HAL that captures every SPI
 * command. This pins the exact on-wire SetPacketParams(FLRC) bytes,
 * especially the RX sync-match mode: Match1 with a 32-bit sync word leaks
 * sync bytes into the payload -> chip CRC fails 100% while packets still
 * demodulate (docs/rca-fix-plan-20260821.md BUG 2; proven refs: RadioLib
 * LR2021 module and balloon-range-tests 9b740aa raw cfg 0x7C = Match123).
 */

#include "radio_bench.h"

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

static void test_radio_config_has_cr_field(void)
{
    radio_bench_cfg_t cfg;
    memset(&cfg, 0, sizeof(cfg));

    /* LoRa CR: denominator form (5 = 4/5) */
    cfg.cr = 5;
    CHECK(cfg.cr == 5);

    /* FLRC CR: register code (1 = 3/4) */
    cfg.cr = 1;
    CHECK(cfg.cr == 1);

    /* Field is uint8_t */
    CHECK(sizeof(cfg.cr) == 1);
}

static void test_radio_config_other_fields_intact(void)
{
    radio_bench_cfg_t cfg;
    memset(&cfg, 0, sizeof(cfg));

    /* Verify all original fields still exist */
    cfg.mod = BENCH_MOD_LORA;
    cfg.sf = 8;
    cfg.bw_hz = 125000;
    cfg.br_bps = 650000;
    cfg.txpow_dbm = 10;
    cfg.freq_hz = 868000000UL;

    CHECK(cfg.mod == BENCH_MOD_LORA);
    CHECK(cfg.sf == 8);
    CHECK(cfg.bw_hz == 125000);
    CHECK(cfg.br_bps == 650000);
    CHECK(cfg.txpow_dbm == 10);
    CHECK(cfg.freq_hz == 868000000UL);
}

/* ---- FIX-T3: fake lr20xx HAL capturing every command ----------------------- */

#define CAP_MAX_CMDS 64
#define CAP_CMD_MAX  16

static uint8_t  cap_cmd[CAP_MAX_CMDS][CAP_CMD_MAX];
static uint16_t cap_cmd_len[CAP_MAX_CMDS];
static int      cap_n = 0;
static int      hal_reset_count = 0;

static void cap_reset(void)
{
    cap_n = 0;
}

static void cap_add(const uint8_t* cmd, uint16_t len)
{
    if (cap_n < CAP_MAX_CMDS && len <= CAP_CMD_MAX)
    {
        memcpy(cap_cmd[cap_n], cmd, len);
        cap_cmd_len[cap_n] = len;
    }
    cap_n++;
}

lr20xx_hal_status_t lr20xx_hal_write(const void* context, const uint8_t* command,
                                     const uint16_t command_length,
                                     const uint8_t* data, const uint16_t data_length)
{
    (void)context;
    (void)data;
    (void)data_length;
    cap_add(command, command_length);
    return LR20XX_HAL_STATUS_OK;
}

lr20xx_hal_status_t lr20xx_hal_read(const void* context, const uint8_t* command,
                                    const uint16_t command_length,
                                    uint8_t* data, const uint16_t data_length)
{
    (void)context;
    (void)command;
    (void)command_length;
    memset(data, 0, data_length);
    return LR20XX_HAL_STATUS_OK;
}

lr20xx_hal_status_t lr20xx_hal_direct_read(const void* context, uint8_t* data,
                                           const uint16_t data_length)
{
    (void)context;
    memset(data, 0, data_length);
    return LR20XX_HAL_STATUS_OK;
}

lr20xx_hal_status_t lr20xx_hal_direct_read_fifo(const void* context, const uint8_t* command,
                                                const uint16_t command_length,
                                                uint8_t* data, const uint16_t data_length)
{
    (void)context;
    (void)command;
    (void)command_length;
    memset(data, 0, data_length);
    return LR20XX_HAL_STATUS_OK;
}

lr20xx_hal_status_t lr20xx_hal_reset(const void* context)
{
    (void)context;
    /* RFA-1c: the chip-reset is the observable marker of the full bring-up
     * (reset -> patch -> DCDC/TCXO -> calibrate) that apply_cfg() performs on
     * a modulation change. Counted so a test can assert WHEN it re-runs. */
    hal_reset_count++;
    return LR20XX_HAL_STATUS_OK;
}

lr20xx_hal_status_t lr20xx_hal_wakeup(const void* context)
{
    (void)context;
    return LR20XX_HAL_STATUS_OK;
}

/* FLRC SetPacketParams command: opcode 0x0249, 6 bytes
 * (lr20xx_radio_flrc.c: LR20XX_RADIO_FLRC_SET_PKT_PARAMS_OC = 0x0249,
 *  CMD_LENGTH = 2 + 4).
 *   [0]=0x02 [1]=0x49
 *   [2]=sync_word_len | preamble_len << 2
 *   [3]=crc_type | header_type << 2 | match_sync_word << 3 | tx_syncword << 6
 *   [4]=pld_len >> 8 [5]=pld_len */
static const uint8_t* find_flrc_pkt_params(void)
{
    for (int i = cap_n - 1; i >= 0; i--)
    {
        if (cap_cmd_len[i] == 6 && cap_cmd[i][0] == 0x02 && cap_cmd[i][1] == 0x49)
        {
            return cap_cmd[i];
        }
    }
    return NULL;
}

/* Golden bytes for {PREAMBLE_32_BITS, SYNC_LEN_4_BYTES, FIX_LEN,
 * CRC_2_BYTES, MATCH_1_OR_2_OR_3, TX_SYNCWORD_1}:
 *   byte2 = 0x02 | 0x07 << 2            = 0x1E
 *   byte3 = 0x01 | 0x01 << 2 | 0x07 << 3 | 0x01 << 6 = 0x7D
 * (balloon-range-tests 9b740aa raw cfg used 0x7C: same but CRC_OFF.)
 */
#define FLRC_GOLDEN_BYTE2 0x1E
#define FLRC_GOLDEN_BYTE3 0x7D

static radio_bench_cfg_t flrc_cfg(void)
{
    radio_bench_cfg_t cfg;
    memset(&cfg, 0, sizeof(cfg));
    cfg.mod       = BENCH_MOD_FLRC;
    cfg.cr        = 1; /* FLRC 3/4 */
    cfg.br_bps    = 650000;
    cfg.txpow_dbm = 10;
    cfg.freq_hz   = 868000000UL;
    return cfg;
}

static void test_flrc_apply_cfg_pkt_params_golden_bytes(void)
{
    radio_bench_cfg_t cfg = flrc_cfg();

    cap_reset();
    CHECK(radio_bench_apply_cfg(&cfg) == 0);

    const uint8_t* p = find_flrc_pkt_params();
    CHECK(p != NULL);
    if (p == NULL)
        return;
    CHECK(p[2] == FLRC_GOLDEN_BYTE2);
    CHECK(p[3] == FLRC_GOLDEN_BYTE3);
    CHECK(p[4] == 0x00); /* pld_len_in_bytes = 255 at apply_cfg */
    CHECK(p[5] == 0xFF);
}

static void test_flrc_rx_arm_keeps_match123(void)
{
    radio_bench_cfg_t cfg = flrc_cfg();
    radio_bench_apply_cfg(&cfg);

    cap_reset();
    CHECK(radio_bench_rx_arm(255) == 0);

    const uint8_t* p = find_flrc_pkt_params();
    CHECK(p != NULL);
    if (p == NULL)
        return;
    CHECK(p[3] == FLRC_GOLDEN_BYTE3);
    CHECK(p[4] == 0x00); /* armed len 255 -> 0x00FF */
    CHECK(p[5] == 0xFF);
}

static void test_flrc_tx_packet_keeps_match123(void)
{
    uint8_t buf[E80_BENCH_MAX_PAYLOAD];
    radio_bench_cfg_t cfg = flrc_cfg();
    memset(buf, 0xAA, sizeof(buf));
    radio_bench_apply_cfg(&cfg);

    cap_reset();
    CHECK(radio_bench_tx_packet(buf, 255, 100) == 0);

    const uint8_t* p = find_flrc_pkt_params();
    CHECK(p != NULL);
    if (p == NULL)
        return;
    CHECK(p[3] == FLRC_GOLDEN_BYTE3);
    CHECK(p[4] == 0x00); /* tx len 255 -> 0x00FF */
    CHECK(p[5] == 0xFF);
}

static void test_flrc_match_mode_tripwire_not_match1(void)
{
    radio_bench_cfg_t cfg = flrc_cfg();

    cap_reset();
    radio_bench_apply_cfg(&cfg);

    const uint8_t* p = find_flrc_pkt_params();
    CHECK(p != NULL);
    if (p == NULL)
        return;

    uint8_t match = (uint8_t)((p[3] >> 3) & 0x07);
    /* TRIPWIRE: Match1 is FORBIDDEN on this bench. With a 32-bit FLRC sync
     * word, MATCH_SYNCWORD_1 leaks sync bytes into the payload so the chip
     * CRC fails on 100% of packets that still demodulate fine (RCA BUG 2,
     * docs/rca-fix-plan-20260821.md). Both proven references (RadioLib
     * LR2021, balloon-range-tests 9b740aa) run Match123. If this fires,
     * someone reintroduced Match1 — do not "fix" the test. */
    CHECK(match != LR20XX_RADIO_FLRC_RX_MATCH_SYNCWORD_1);
    CHECK(match == LR20XX_RADIO_FLRC_RX_MATCH_SYNCWORD_1_OR_2_OR_3);
}

/* ---- RFA-1c: stale calibration after a runtime rate change -----------------
 *
 * Bench defect (measured 2026-10-14, docs/RFA1b-FOLLOWUP-650KBPS-ZEROS-2026-10-14.md):
 * every 650 kbps FLRC cell that directly follows a 260 kbps cell is DEAF on the
 * receiver (rx_pkts=0, RSSI exactly 0.0) while the TX reports sent_ok=200. The
 * reverse direction (650 -> 260) is clean, so it is not a "stuck in old mode"
 * story: the modem calibration that the boot chain ran is stale for the NEW
 * BR/BW pair (260 kbps = BW 0.307 MHz, 650 kbps = BW 0.740 MHz).
 *
 * Control/treated A/B on the bench pair (same day, console-driven): TX
 * 260 -> 650 direct = DEAF; TX 260 -> LoRa -> 650 (which re-enters apply_cfg()
 * with a changed modulation and therefore re-runs the bring-up) = HEALTHY
 * (rx=100, RSSI -57 dBm). So the fix is to make the bring-up condition fire on
 * a modem-parameter change, not only on a FLRC<->LoRa change.
 */

/* Most recent LR20XX_SYSTEM_CALIBRATE (0x0122) mask byte, or -1 if none was
 * captured. lr20xx_system.c emits [0x01][0x22][mask]. */
static int find_system_calibrate(void)
{
    int first = cap_n > CAP_MAX_CMDS ? cap_n - CAP_MAX_CMDS : 0;
    for (int i = cap_n - 1; i >= first; i--)
    {
        if (cap_cmd_len[i] == 3 && cap_cmd[i][0] == 0x01 && cap_cmd[i][1] == 0x22)
        {
            return cap_cmd[i][2];
        }
    }
    return -1;
}

/* LR20XX_RADIO_FLRC_SET_MODULATION_PARAMS_OC = 0x0248 (3 + 1 bytes). */
static int flrc_mod_params_present(void)
{
    int first = cap_n > CAP_MAX_CMDS ? cap_n - CAP_MAX_CMDS : 0;
    for (int i = cap_n - 1; i >= first; i--)
    {
        if (cap_cmd_len[i] == 4 && cap_cmd[i][0] == 0x02 && cap_cmd[i][1] == 0x48)
        {
            return 1;
        }
    }
    return 0;
}

static radio_bench_cfg_t lora_cfg(void)
{
    radio_bench_cfg_t cfg;
    memset(&cfg, 0, sizeof(cfg));
    cfg.mod       = BENCH_MOD_LORA;
    cfg.sf        = 8;
    cfg.cr        = 5;
    cfg.bw_hz     = 125000;
    cfg.br_bps    = 650000;
    cfg.txpow_dbm = 10;
    cfg.freq_hz   = 868000000UL;
    return cfg;
}

/* THE FIX: 260 kbps -> 650 kbps must re-run the bring-up (reset + calibrate)
 * even though the modulation is FLRC on both sides. */
static void test_flrc_bitrate_change_recalibrates(void)
{
    radio_bench_cfg_t cfg = flrc_cfg();
    cfg.br_bps = 260000;
    CHECK(radio_bench_apply_cfg(&cfg) == 0); /* establish FLRC @ 260 */

    cap_reset();
    int r0 = hal_reset_count;

    cfg.br_bps = 650000;
    CHECK(radio_bench_apply_cfg(&cfg) == 0);

    CHECK(hal_reset_count > r0);          /* bring-up re-ran */
    CHECK(find_system_calibrate() == 0x7F); /* all blocks, as at boot */
    CHECK(flrc_mod_params_present());     /* ...and the new BR/BW still applied */
}

/* Control: re-applying the SAME rate (every cell of a rate-grouped sweep, the
 * PA/FREQ paths) must NOT re-run the bring-up — a reset per command would
 * invalidate the 12/12-clean continuous-650 baseline and slow the sweeps. */
static void test_flrc_same_bitrate_does_not_recalibrate(void)
{
    radio_bench_cfg_t cfg = flrc_cfg();
    CHECK(radio_bench_apply_cfg(&cfg) == 0); /* establish FLRC @ 650 */

    cap_reset();
    int r0 = hal_reset_count;
    CHECK(radio_bench_apply_cfg(&cfg) == 0);

    CHECK(hal_reset_count == r0);
    CHECK(find_system_calibrate() == -1);
}

/* Regression guard: the pre-existing FLRC<->LoRa trigger must survive. */
static void test_mod_change_still_recalibrates(void)
{
    radio_bench_cfg_t lcfg = lora_cfg();
    CHECK(radio_bench_apply_cfg(&lcfg) == 0); /* establish LoRa */

    cap_reset();
    int r0 = hal_reset_count;
    radio_bench_cfg_t fcfg = flrc_cfg();
    CHECK(radio_bench_apply_cfg(&fcfg) == 0);

    CHECK(hal_reset_count > r0);
    CHECK(find_system_calibrate() == 0x7F);
}

/* Guard: PA-only changes (BENCH_CMD_PA re-applies cfg) must not recalibrate. */
static void test_pa_only_change_does_not_recalibrate(void)
{
    radio_bench_cfg_t cfg = flrc_cfg();
    CHECK(radio_bench_apply_cfg(&cfg) == 0);

    cap_reset();
    int r0 = hal_reset_count;

    cfg.txpow_dbm = 22;
    CHECK(radio_bench_apply_cfg(&cfg) == 0);

    CHECK(hal_reset_count == r0);
    CHECK(find_system_calibrate() == -1);
}

/* Same defect class, other rate path: a LoRa bandwidth change alters the
 * occupied bandwidth exactly like an FLRC BR/BW change does. */
static void test_lora_bandwidth_change_recalibrates(void)
{
    radio_bench_cfg_t cfg = lora_cfg();
    CHECK(radio_bench_apply_cfg(&cfg) == 0); /* establish LoRa BW125 */

    cap_reset();
    int r0 = hal_reset_count;

    cfg.bw_hz = 250000;
    CHECK(radio_bench_apply_cfg(&cfg) == 0);

    CHECK(hal_reset_count > r0);
    CHECK(find_system_calibrate() == 0x7F);
}

/* Same defect class: a LoRa SF change re-derives the modem params. */
static void test_lora_sf_change_recalibrates(void)
{
    radio_bench_cfg_t cfg = lora_cfg();
    cfg.sf = 8;
    CHECK(radio_bench_apply_cfg(&cfg) == 0); /* establish LoRa SF8 */

    cap_reset();
    int r0 = hal_reset_count;

    cfg.sf = 12;
    CHECK(radio_bench_apply_cfg(&cfg) == 0);

    CHECK(hal_reset_count > r0);
    CHECK(find_system_calibrate() == 0x7F);
}

/* FREQ-only change (BENCH_CMD_FREQ re-applies cfg) must not recalibrate:
 * the front-end calibration is per-band, not per-channel, and a recal on
 * every FREQ command would wreck the in-band sweeps. */
static void test_freq_only_change_does_not_recalibrate(void)
{
    radio_bench_cfg_t cfg = flrc_cfg();
    CHECK(radio_bench_apply_cfg(&cfg) == 0);

    cap_reset();
    int r0 = hal_reset_count;

    cfg.freq_hz = 869850000UL;
    CHECK(radio_bench_apply_cfg(&cfg) == 0);

    CHECK(hal_reset_count == r0);
    CHECK(find_system_calibrate() == -1);
}

int main(void)
{
    test_radio_config_has_cr_field();
    test_radio_config_other_fields_intact();
    test_flrc_apply_cfg_pkt_params_golden_bytes();
    test_flrc_rx_arm_keeps_match123();
    test_flrc_tx_packet_keeps_match123();
    test_flrc_match_mode_tripwire_not_match1();

    test_flrc_bitrate_change_recalibrates();
    test_flrc_same_bitrate_does_not_recalibrate();
    test_mod_change_still_recalibrates();
    test_pa_only_change_does_not_recalibrate();
    test_lora_bandwidth_change_recalibrates();
    test_lora_sf_change_recalibrates();
    test_freq_only_change_does_not_recalibrate();

    if (failures == 0)
    {
        printf("test_radio_bench_cfg: ALL PASS\n");
        return 0;
    }
    printf("test_radio_bench_cfg: %d FAILURE(S)\n", failures);
    return 1;
}
