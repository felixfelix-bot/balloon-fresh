/**
 * @file    test_radio_bench_fifo.c
 * @brief   Host unit tests: LR20xx FIFO hygiene in radio_bench.c (FIX-T4).
 *
 * FIX-T4 (docs/rca-fix-plan-20260821.md BUG 2 / H2): radio_bench_rx_arm() is
 * the re-arm path invoked from the IRQ handler after EVERY received packet,
 * so it must clear the RX FIFO each time it re-enters RX; and
 * radio_bench_tx_packet() must clear the TX FIFO before every FIFO write.
 * A stale RX FIFO (e.g. a CRC-error packet that was never drained) otherwise
 * corrupts the next packet's payload. Precedent: RadioLib LR2021 clears the
 * FIFO after every read; balloon-range-tests 9b740aa fix #3 was exactly this.
 * Before FIX-T4 the bench had ZERO lr20xx_radio_fifo_clear_* calls.
 *
 * Same harness as test_radio_bench_cfg.c (FIX-T3): host-compiles the REAL
 * src/radio_bench.c against the REAL vendored lr20xx_driver sources over a
 * fake lr20xx HAL that captures every SPI command. Opcodes below are
 * file-private driver enums, hardcoded here with comments:
 *   FIFO clear RX  = 0x011E  (lr20xx_radio_fifo.c) -> bytes {0x01,0x1E}
 *   FIFO clear TX  = 0x011F  (lr20xx_radio_fifo.c) -> bytes {0x01,0x1F}
 *   FIFO write TX  = 0x0002  (lr20xx_radio_fifo.c) -> bytes {0x00,0x02}
 *   SetRx          = 0x020C  (lr20xx_radio_common.c) -> bytes {0x02,0x0C}
 *   FLRC SetPktParams = 0x0249 (lr20xx_radio_flrc.c) -> {0x02,0x49}
 *   LoRa SetPktParams = 0x0221 (lr20xx_radio_lora.c) -> {0x02,0x21}
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

/* ---- fake lr20xx HAL capturing every command (FIX-T3 pattern) ------------- */

#define CAP_MAX_CMDS 64
#define CAP_CMD_MAX  16

static uint8_t  cap_cmd[CAP_MAX_CMDS][CAP_CMD_MAX];
static uint16_t cap_cmd_len[CAP_MAX_CMDS];
static int      cap_n = 0;

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
    return LR20XX_HAL_STATUS_OK;
}

lr20xx_hal_status_t lr20xx_hal_wakeup(const void* context)
{
    (void)context;
    return LR20XX_HAL_STATUS_OK;
}

/* ---- helpers --------------------------------------------------------------- */

/* Index of the FIRST command whose first two opcode bytes match, -1 if absent. */
static int find_cmd(uint8_t op0, uint8_t op1)
{
    for (int i = 0; i < cap_n; i++)
    {
        if (cap_cmd_len[i] >= 2 && cap_cmd[i][0] == op0 && cap_cmd[i][1] == op1)
            return i;
    }
    return -1;
}

static int count_cmd(uint8_t op0, uint8_t op1)
{
    int n = 0;
    for (int i = 0; i < cap_n; i++)
    {
        if (cap_cmd_len[i] >= 2 && cap_cmd[i][0] == op0 && cap_cmd[i][1] == op1)
            n++;
    }
    return n;
}

#define FIFO_CLEAR_RX_BYTES 0x01, 0x1E
#define FIFO_CLEAR_TX_BYTES 0x01, 0x1F
#define FIFO_WRITE_TX_BYTES 0x00, 0x02
#define SET_RX_BYTES        0x02, 0x0C
#define FLRC_PKT_PARAMS     0x02, 0x49
#define LORA_PKT_PARAMS     0x02, 0x21

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

static radio_bench_cfg_t lora_cfg(void)
{
    radio_bench_cfg_t cfg;
    memset(&cfg, 0, sizeof(cfg));
    cfg.mod       = BENCH_MOD_LORA;
    cfg.cr        = 5; /* LoRa 4/5 */
    cfg.sf        = 8;
    cfg.bw_hz     = 125000;
    cfg.txpow_dbm = 10;
    cfg.freq_hz   = 868000000UL;
    return cfg;
}

/* ---- FIX-T4: RX FIFO clear per re-arm -------------------------------------- */

static void test_rx_arm_clears_rx_fifo_flrc(void)
{
    radio_bench_cfg_t cfg = flrc_cfg();
    radio_bench_apply_cfg(&cfg);

    cap_reset();
    CHECK(radio_bench_rx_arm(255) == 0);

    int i_clear = find_cmd(FIFO_CLEAR_RX_BYTES);
    CHECK(i_clear >= 0); /* RX FIFO clear emitted on every (re-)arm */
    if (i_clear < 0)
        return;

    /* Ordering: after SetPacketParams, before SetRx — a clear that lands
     * after SetRx would drop the first bytes of an incoming packet. */
    int i_pkt = find_cmd(FLRC_PKT_PARAMS);
    int i_rx  = find_cmd(SET_RX_BYTES);
    CHECK(i_pkt >= 0);
    CHECK(i_rx >= 0);
    CHECK(i_pkt < i_clear);
    CHECK(i_clear < i_rx);
}

static void test_rx_arm_clears_rx_fifo_lora(void)
{
    radio_bench_cfg_t cfg = lora_cfg();
    radio_bench_apply_cfg(&cfg);

    cap_reset();
    CHECK(radio_bench_rx_arm(255) == 0);

    int i_clear = find_cmd(FIFO_CLEAR_RX_BYTES);
    CHECK(i_clear >= 0); /* both modems share the re-arm path */
    if (i_clear < 0)
        return;

    int i_pkt = find_cmd(LORA_PKT_PARAMS);
    int i_rx  = find_cmd(SET_RX_BYTES);
    CHECK(i_pkt >= 0);
    CHECK(i_rx >= 0);
    CHECK(i_pkt < i_clear);
    CHECK(i_clear < i_rx);
}

/* radio_bench_rx_arm() is what the IRQ handler calls to re-arm after each
 * packet (radio_bench.c rx/IRQ paths), so TWO arms must produce TWO clears:
 * stale FIFO contents from packet N must never leak into packet N+1. */
static void test_rx_rearm_clears_fifo_every_time(void)
{
    radio_bench_cfg_t cfg = flrc_cfg();
    radio_bench_apply_cfg(&cfg);

    cap_reset();
    CHECK(radio_bench_rx_arm(255) == 0);
    CHECK(radio_bench_rx_arm(255) == 0);

    CHECK(count_cmd(FIFO_CLEAR_RX_BYTES) == 2);
}

/* ---- FIX-T4: TX FIFO clear before the FIFO write ---------------------------- */

static void test_tx_packet_clears_tx_fifo_before_write(void)
{
    uint8_t buf[E80_BENCH_MAX_PAYLOAD];
    radio_bench_cfg_t cfg = flrc_cfg();
    memset(buf, 0xAA, sizeof(buf));
    radio_bench_apply_cfg(&cfg);

    cap_reset();
    CHECK(radio_bench_tx_packet(buf, 255, 100) == 0);

    int i_clr = find_cmd(FIFO_CLEAR_TX_BYTES);
    CHECK(i_clr >= 0); /* TX FIFO cleared before loading the next packet */
    if (i_clr < 0)
        return;

    int i_wr = find_cmd(FIFO_WRITE_TX_BYTES);
    CHECK(i_wr >= 0);
    CHECK(i_clr < i_wr); /* clear BEFORE the write, else the new bytes are dropped */
}

int main(void)
{
    test_rx_arm_clears_rx_fifo_flrc();
    test_rx_arm_clears_rx_fifo_lora();
    test_rx_rearm_clears_fifo_every_time();
    test_tx_packet_clears_tx_fifo_before_write();

    if (failures == 0)
    {
        printf("test_radio_bench_fifo: ALL PASS\n");
        return 0;
    }
    printf("test_radio_bench_fifo: %d FAILURE(S)\n", failures);
    return 1;
}
