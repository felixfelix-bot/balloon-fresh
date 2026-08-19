/**
 * @file    radio_bench.c
 * @brief   LR2021 radio control - vendor-demo-faithful init/RX/TX sequences.
 *
 * Sequences copied from E80_DEMO/Core/Src/user_radio.c (TXCO variant) with
 * the FLRC additions using the same vendored lr20xx_driver API.
 */

#include "radio_bench.h"
#include <stddef.h>
#include <string.h>

/* Demo context string.  Using a string literal directly so the initializer
 * is a valid constant expression under -std=gnu11 (address of a literal). */
const void* E80_CONTEXT = (const void*)"LR2021";

/* ---- Demo configuration blocks (user_radio.c) ------------------------------ */

/* LoRa sync word used by the demo */
#define SYNC_WORD_NO_RADIO 0x34

static lr20xx_system_sleep_cfg_t sleep_cfgs = {
    .is_ram_retention_enabled = true,
    .is_clk_32k_enabled       = false,
};

static lr20xx_radio_common_pa_cfg_t pa_cfgs = {
    .pa_sel           = LR20XX_RADIO_COMMON_PA_SEL_LF,
    .pa_lf_mode       = LR20XX_RADIO_COMMON_PA_LF_MODE_FSM,
    .pa_lf_duty_cycle = 7,
    .pa_lf_slices     = 7,
    .pa_hf_duty_cycle = 16,
};

/* LoRa packet params (demo defaults; pld_len patched per operation) */
static lr20xx_radio_lora_pkt_params_t lora_pkt_params = {
    .preamble_len_in_symb = 8,
    .pkt_mode             = LR20XX_RADIO_LORA_PKT_EXPLICIT,
    .pld_len_in_bytes     = 255,
    .crc                  = true,
    .iq                   = false,
};

/* LoRa modulation params (demo defaults; patched by apply_cfg) */
static lr20xx_radio_lora_mod_params_t lora_mod_params = {
    .bw  = LR20XX_RADIO_LORA_BW_125,
    .cr  = LR20XX_RADIO_LORA_CR_4_5,
    .sf  = LR20XX_RADIO_LORA_SF8,
    .ppm = LR20XX_RADIO_LORA_NO_PPM,
};

/* FLRC modulation params (patched by apply_cfg) */
static lr20xx_radio_flrc_mod_params_t flrc_mod_params = {
    .br_bw = LR20XX_RADIO_FLRC_BR_0_650_BW_0_740,
    .cr    = LR20XX_RADIO_FLRC_CR_3_4,
    .shape = LR20XX_RADIO_FLRC_PULSE_SHAPE_BT_1,
};

/* FLRC packet params (FIX_LEN; pld_len patched per operation).
 * Both bench ends must run the same LEN= (see README). */
static lr20xx_radio_flrc_pkt_params_t flrc_pkt_params = {
    .preamble_len    = LR20XX_RADIO_FLRC_PREAMBLE_LEN_32_BITS,
    .sync_word_len   = LR20XX_RADIO_FLRC_SYNCWORD_LENGTH_4_BYTES,
    .tx_syncword     = LR20XX_RADIO_FLRC_TX_SYNCWORD_1,
    .match_sync_word = LR20XX_RADIO_FLRC_RX_MATCH_SYNCWORD_1,
    .header_type     = LR20XX_RADIO_FLRC_PKT_FIX_LEN,
    .pld_len_in_bytes = 255,
    .crc_type        = LR20XX_RADIO_FLRC_CRC_2_BYTES,
};

/* FLRC syncword #1 (both ends run this firmware -> symmetric) */
static const uint8_t flrc_syncword[LR20XX_RADIO_FLRC_SYNCWORD_LENGTH] = { 0x2D, 0xD4, 0xD4, 0xB2 };

/* Current active config mirror (needed by the IRQ path for re-arm len). */
static radio_bench_cfg_t cur_cfg = {
    .mod       = BENCH_MOD_LORA,
    .sf        = 8,
    .cr        = 5,
    .bw_hz     = 125000,
    .br_bps    = 650000,
    .txpow_dbm = E80_BENCH_TXPOW_CAP_INDOOR_DBM,
    .freq_hz   = 868000000UL,
};
static uint16_t cur_rx_pld_len = 255;

/* ---- State ----------------------------------------------------------------- */

uint8_t  radio_bench_rx_buf[E80_BENCH_MAX_PAYLOAD];
volatile uint16_t radio_bench_rx_buf_len = 0;

volatile uint8_t radio_bench_chip_major = 0;
volatile uint8_t radio_bench_chip_minor = 0;

static volatile bool     radio_asleep   = false;
static volatile uint16_t rx_pld_for_irq = 255;

/* True from set_tx() until TX_DONE/TIMEOUT IRQ — lets the IRQ path tell a
 * TX overrun apart from an RX timeout on the shared TIMEOUT IRQ bit. */
static volatile bool tx_active = false;

/* Event mailbox (single slot; drops counted when the superloop stalls) */
static volatile rb_evt_t evt_slot;
static volatile uint8_t  evt_pending = 0;
static volatile uint32_t evt_drops   = 0;

static lr20xx_radio_lora_bw_t bw_to_enum(uint32_t bw_hz)
{
    switch (bw_hz)
    {
    case 250000: return LR20XX_RADIO_LORA_BW_250;
    case 500000: return LR20XX_RADIO_LORA_BW_500;
    default:     return LR20XX_RADIO_LORA_BW_125;
    }
}

static lr20xx_radio_lora_sf_t sf_to_enum(uint8_t sf)
{
    switch (sf)
    {
    case 5:  return LR20XX_RADIO_LORA_SF5;
    case 6:  return LR20XX_RADIO_LORA_SF6;
    case 7:  return LR20XX_RADIO_LORA_SF7;
    case 8:  return LR20XX_RADIO_LORA_SF8;
    case 9:  return LR20XX_RADIO_LORA_SF9;
    case 10: return LR20XX_RADIO_LORA_SF10;
    case 11: return LR20XX_RADIO_LORA_SF11;
    default: return LR20XX_RADIO_LORA_SF12;
    }
}

static lr20xx_radio_flrc_br_bw_t br_to_enum(uint32_t br_bps)
{
    switch (br_bps)
    {
    case 2600000: return LR20XX_RADIO_FLRC_BR_2_600_BW_2_666;
    case 2080000: return LR20XX_RADIO_FLRC_BR_2_080_BW_2_222;
    case 1300000: return LR20XX_RADIO_FLRC_BR_1_300_BW_1_333;
    case 1040000: return LR20XX_RADIO_FLRC_BR_1_040_BW_1_333;
    case 520000:  return LR20XX_RADIO_FLRC_BR_0_520_BW_0_571;
    case 325000:  return LR20XX_RADIO_FLRC_BR_0_325_BW_0_357;
    case 260000:  return LR20XX_RADIO_FLRC_BR_0_260_BW_0_307;
    default:      return LR20XX_RADIO_FLRC_BR_0_650_BW_0_740;
    }
}

/* LoRa coding rate: cfg->cr is the denominator (5=4/5, 6=4/6, 7=4/7, 8=4/8). */
static lr20xx_radio_lora_cr_t lora_cr_to_enum(uint8_t cr)
{
    switch (cr)
    {
    case 5: return LR20XX_RADIO_LORA_CR_4_5;
    case 6: return LR20XX_RADIO_LORA_CR_4_6;
    case 7: return LR20XX_RADIO_LORA_CR_4_7;
    case 8: return LR20XX_RADIO_LORA_CR_4_8;
    default: return LR20XX_RADIO_LORA_CR_4_5;
    }
}

/* FLRC coding rate: cfg->cr is the register code (0=1/2, 1=3/4, 2=uncoded, 3=2/3). */
static lr20xx_radio_flrc_cr_t flrc_cr_to_enum(uint8_t cr)
{
    switch (cr)
    {
    case 0: return LR20XX_RADIO_FLRC_CR_1_2;
    case 1: return LR20XX_RADIO_FLRC_CR_3_4;
    case 2: return LR20XX_RADIO_FLRC_CR_NONE;
    case 3: return LR20XX_RADIO_FLRC_CR_2_3;
    default: return LR20XX_RADIO_FLRC_CR_3_4;
    }
}

/* ---- Public API ------------------------------------------------------------ */

int radio_bench_init(void)
{
    uint16_t errors = 0;
    lr20xx_system_version_t version = { 0 };

    /* LR2021 reset */
    lr20xx_hal_reset(E80_CONTEXT);

    /* Get + clear error status */
    lr20xx_system_get_errors(E80_CONTEXT, &errors);
    lr20xx_system_clear_errors(E80_CONTEXT);

    /* TCXO variant (demo): DC-DC + TCXO 2.2V, 64000 startup steps */
    lr20xx_system_set_reg_mode(E80_CONTEXT, LR20XX_SYSTEM_REG_MODE_DCDC);
    lr20xx_system_set_tcxo_mode(E80_CONTEXT, LR20XX_SYSTEM_TCXO_CTRL_2_2V, 64000);

    /* LF clock: RC */
    lr20xx_system_cfg_lfclk(E80_CONTEXT, LR20XX_SYSTEM_LFCLK_RC);

    /* Calibrate everything */
    lr20xx_system_calibrate(E80_CONTEXT, 0x7F);

    /* Check errors again, clear if set */
    lr20xx_system_get_errors(E80_CONTEXT, &errors);
    if (errors != 0)
    {
        lr20xx_system_clear_errors(E80_CONTEXT);
    }

    /* DIO8 = IRQ */
    lr20xx_system_set_dio_function(E80_CONTEXT, LR20XX_SYSTEM_DIO_8, LR20XX_SYSTEM_DIO_FUNC_IRQ,
                                    LR20XX_SYSTEM_DIO_DRIVE_PULL_DOWN);

    /* Cache version */
    if (lr20xx_system_get_version(E80_CONTEXT, &version) != LR20XX_STATUS_OK)
    {
        return -1;
    }
    radio_bench_chip_major = version.major;
    radio_bench_chip_minor = version.minor;

    radio_asleep = false;

    /* Modem defaults (LoRa SF8/BW125 like the demo) - applied by apply_cfg */
    if (radio_bench_apply_cfg(&cur_cfg) != 0)
        return -1;

    return 0;
}

int radio_bench_apply_cfg(const radio_bench_cfg_t* cfg)
{
    int8_t power_half_dbm;
    uint32_t freq = cfg->freq_hz;

    cur_cfg = *cfg;

    if (cfg->mod == BENCH_MOD_LORA)
    {
        lr20xx_radio_common_set_pkt_type(E80_CONTEXT, LR20XX_RADIO_COMMON_PKT_TYPE_LORA);

        lora_pkt_params.pld_len_in_bytes = 255;
        lr20xx_radio_lora_set_packet_params(E80_CONTEXT, &lora_pkt_params);
        lr20xx_radio_lora_set_syncword(E80_CONTEXT, SYNC_WORD_NO_RADIO);

        lora_mod_params.bw = bw_to_enum(cfg->bw_hz);
        lora_mod_params.sf = sf_to_enum(cfg->sf);
        lora_mod_params.cr = lora_cr_to_enum(cfg->cr);
        lora_mod_params.ppm = LR20XX_RADIO_LORA_NO_PPM;
        lr20xx_radio_lora_set_modulation_params(E80_CONTEXT, &lora_mod_params);
    }
    else /* FLRC */
    {
        lr20xx_radio_common_set_pkt_type(E80_CONTEXT, LR20XX_RADIO_COMMON_PKT_TYPE_FLRC);

        flrc_pkt_params.pld_len_in_bytes = 255;
        lr20xx_radio_flrc_set_pkt_params(E80_CONTEXT, &flrc_pkt_params);
        lr20xx_radio_flrc_set_syncword(E80_CONTEXT, 1, flrc_syncword);

        flrc_mod_params.br_bw = br_to_enum(cfg->br_bps);
        flrc_mod_params.cr    = flrc_cr_to_enum(cfg->cr);
        lr20xx_radio_flrc_set_modulation_params(E80_CONTEXT, &flrc_mod_params);
    }

    /* RF frequency */
    lr20xx_radio_common_set_rf_freq(E80_CONTEXT, freq);

    /* PA config: LF path. Demo: duty 7/slices 7 for 400-550 MHz,
     * duty 7/slices 6 otherwise (incl. 902-928 ISM). */
    pa_cfgs.pa_sel           = LR20XX_RADIO_COMMON_PA_SEL_LF;
    pa_cfgs.pa_lf_mode       = LR20XX_RADIO_COMMON_PA_LF_MODE_FSM;
    pa_cfgs.pa_lf_duty_cycle = 7;
    pa_cfgs.pa_lf_slices     = (freq > 400000000UL && freq < 550000000UL) ? 7 : 6;
    pa_cfgs.pa_hf_duty_cycle = 16;
    lr20xx_radio_common_set_rx_path(E80_CONTEXT, LR20XX_RADIO_COMMON_RX_PATH_LF,
                                     LR20XX_RADIO_COMMON_RX_PATH_BOOST_MODE_NONE);
    lr20xx_radio_common_set_pa_cfg(E80_CONTEXT, &pa_cfgs);

    /* TX params: power in half-dBm (driver: power_half_dbm), demo clamps at
     * 0x2C = 44 = +22 dBm. */
    power_half_dbm = (int8_t)(cfg->txpow_dbm * 2);
    if (power_half_dbm > 0x2C)
        power_half_dbm = 0x2C;
    if (power_half_dbm < 0)
        power_half_dbm = 0;
    lr20xx_radio_common_set_tx_params(E80_CONTEXT, power_half_dbm, LR20XX_RADIO_COMMON_RAMP_304_US);

    /* Auto fallback to STDBY_RC after RX/TX (demo) */
    lr20xx_radio_common_set_rx_tx_fallback_mode(E80_CONTEXT, LR20XX_RADIO_FALLBACK_STDBY_RC);

    return 0;
}

int radio_bench_rx_arm(uint16_t rx_pld_len)
{
    cur_rx_pld_len   = rx_pld_len;
    rx_pld_for_irq   = rx_pld_len;

    if (cur_cfg.mod == BENCH_MOD_LORA)
    {
        lora_pkt_params.pld_len_in_bytes = 255; /* demo radio_rx() */
        lr20xx_radio_lora_set_packet_params(E80_CONTEXT, &lora_pkt_params);
    }
    else
    {
        flrc_pkt_params.pld_len_in_bytes = rx_pld_len;
        lr20xx_radio_flrc_set_pkt_params(E80_CONTEXT, &flrc_pkt_params);
    }

    lr20xx_system_set_dio_irq_cfg(E80_CONTEXT, LR20XX_SYSTEM_DIO_8,
                                  LR20XX_SYSTEM_IRQ_RX_DONE | LR20XX_SYSTEM_IRQ_CRC_ERROR);

    lr20xx_system_clear_irq_status(E80_CONTEXT, LR20XX_SYSTEM_IRQ_ALL_MASK);

    lr20xx_radio_common_set_rx(E80_CONTEXT, 0);

    return 0;
}

int radio_bench_tx_packet(const uint8_t* buf, uint16_t len, uint32_t tx_timeout_ms)
{
    /* TX overrun defense: TIMEOUT IRQ enabled alongside TX_DONE so the chip
     * itself ends a stuck TX (fallback STDBY_RC set by apply_cfg unkeys the
     * PA) even if the host never notices. */
    lr20xx_system_set_dio_irq_cfg(E80_CONTEXT, LR20XX_SYSTEM_DIO_8,
                                  LR20XX_SYSTEM_IRQ_TX_DONE | LR20XX_SYSTEM_IRQ_TIMEOUT);

    lr20xx_system_clear_irq_status(E80_CONTEXT, LR20XX_SYSTEM_IRQ_ALL_MASK);

    if (cur_cfg.mod == BENCH_MOD_LORA)
    {
        lora_pkt_params.pld_len_in_bytes = len;
        lr20xx_radio_lora_set_packet_params(E80_CONTEXT, &lora_pkt_params);
    }
    else
    {
        flrc_pkt_params.pld_len_in_bytes = len;
        lr20xx_radio_flrc_set_pkt_params(E80_CONTEXT, &flrc_pkt_params);
    }

    lr20xx_radio_fifo_write_tx(E80_CONTEXT, buf, len);

    tx_active = true;
    lr20xx_radio_common_set_tx(E80_CONTEXT, tx_timeout_ms);

    return 0;
}

void radio_bench_sleep(void)
{
    lr20xx_system_sleep_cfg_t cfg = sleep_cfgs;
    lr20xx_system_set_sleep_mode(E80_CONTEXT, &cfg, 0);
    radio_asleep = true;
}

void radio_bench_wakeup(void)
{
    lr20xx_hal_wakeup(E80_CONTEXT);
    radio_asleep = false;
}

bool radio_bench_is_asleep(void)
{
    return radio_asleep;
}

/* ---- IRQ path (demo radio_irq_callback) ------------------------------------ */

static void evt_push(const rb_evt_t* e)
{
    if (evt_pending)
    {
        evt_drops++;
        return;
    }
    evt_slot   = *e;
    evt_pending = 1;
}

void radio_bench_irq(void)
{
    lr20xx_system_irq_mask_t radio_irq = LR20XX_SYSTEM_IRQ_NONE;

    if (lr20xx_system_get_and_clear_irq_status(E80_CONTEXT, &radio_irq) != LR20XX_STATUS_OK)
    {
        return;
    }

    if ((radio_irq & LR20XX_SYSTEM_IRQ_TIMEOUT) == LR20XX_SYSTEM_IRQ_TIMEOUT)
    {
        if (tx_active)
        {
            /* Chip TX timeout: the LR2021 already left TX (fallback STDBY_RC,
             * PA unkeyed). Abort the burst — do NOT re-arm RX here. */
            tx_active = false;
            rb_evt_t e = { .type = RB_EVT_TX_TIMEOUT };
            evt_push(&e);
        }
        else
        {
            rb_evt_t e = { .type = RB_EVT_RX_TIMEOUT };
            evt_push(&e);
            radio_bench_rx_arm(rx_pld_for_irq);
        }
    }
    else if (radio_irq & LR20XX_SYSTEM_IRQ_LORA_HEADER_ERROR)
    {
        rb_evt_t e = { .type = RB_EVT_RX_OTHER };
        evt_push(&e);
        radio_bench_rx_arm(rx_pld_for_irq);
    }
    else if (radio_irq & LR20XX_SYSTEM_IRQ_CRC_ERROR)
    {
        rb_evt_t e = { .type = RB_EVT_RX_CRC };
        evt_push(&e);
        radio_bench_rx_arm(rx_pld_for_irq);
    }
    else if ((radio_irq & LR20XX_SYSTEM_IRQ_RX_DONE) == LR20XX_SYSTEM_IRQ_RX_DONE)
    {
        rb_evt_t e = { .type = RB_EVT_RX_OK };

        if (cur_cfg.mod == BENCH_MOD_LORA)
        {
            lr20xx_radio_lora_packet_status_t st;
            lr20xx_radio_lora_get_packet_status(E80_CONTEXT, &st);
            e.len      = st.packet_length_bytes;
            e.rssi_half_dbm = (int16_t)(2 * st.rssi_pkt_in_dbm - (st.rssi_pkt_half_dbm_count ? 1 : 0));
            e.snr_qdb  = st.snr_pkt_raw;
            if (e.len > E80_BENCH_MAX_PAYLOAD)
                e.len = E80_BENCH_MAX_PAYLOAD;
            lr20xx_radio_fifo_read_rx(E80_CONTEXT, radio_bench_rx_buf, st.packet_length_bytes);
        }
        else
        {
            lr20xx_radio_flrc_pkt_status_t st;
            lr20xx_radio_flrc_get_pkt_status(E80_CONTEXT, &st);
            e.len      = st.packet_length_bytes;
            e.rssi_half_dbm = (int16_t)(2 * st.rssi_avg_in_dbm - (st.rssi_avg_half_dbm_count ? 1 : 0));
            e.snr_qdb  = 0; /* FLRC has no SNR estimate */
            if (e.len > E80_BENCH_MAX_PAYLOAD)
                e.len = E80_BENCH_MAX_PAYLOAD;
            lr20xx_radio_fifo_read_rx(E80_CONTEXT, radio_bench_rx_buf, st.packet_length_bytes);
        }

        radio_bench_rx_buf_len = e.len;
        if (e.len >= 4)
            e.seq = (uint32_t)radio_bench_rx_buf[0] | ((uint32_t)radio_bench_rx_buf[1] << 8) |
                    ((uint32_t)radio_bench_rx_buf[2] << 16) | ((uint32_t)radio_bench_rx_buf[3] << 24);

        evt_push(&e);
        radio_bench_rx_arm(rx_pld_for_irq);
    }
    else if ((radio_irq & LR20XX_SYSTEM_IRQ_TX_DONE) == LR20XX_SYSTEM_IRQ_TX_DONE)
    {
        tx_active = false;
        rb_evt_t e = { .type = RB_EVT_TX_DONE };
        evt_push(&e);
    }
    else
    {
        rb_evt_t e = { .type = RB_EVT_RX_OTHER };
        evt_push(&e);
        radio_bench_rx_arm(rx_pld_for_irq);
    }
}

int radio_bench_poll_event(rb_evt_t* evt)
{
    if (!evt_pending)
        return 0;
    *evt        = evt_slot;
    evt_pending = 0;
    return 1;
}

uint32_t radio_bench_evt_drops(void)
{
    return evt_drops;
}
