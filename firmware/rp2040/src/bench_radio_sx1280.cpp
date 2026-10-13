/**
 * @file    bench_radio_sx1280.cpp
 * @brief   Raw-SPI LR2021 radio ops for the RP2040BENCH console (HARM-T5).
 *
 * The raw-SPI layer is lifted verbatim from firmware/rp2040/src/multi_radio_
 * sweep_rx_v4.cpp (rfWaitBusy / rfWriteCmd / rfReadIrqStatus / rfClearIrq /
 * rfSetRx / rfReadRxFifo / rfResetAndStandby / rfCalibrate / rfSetFreq /
 * rfSetTxPower) plus the TX opcodes from dual_radio_sweep_tx.cpp
 * (WRITE_TX_FIFO 0x00,0x02 / CLEAR_TX_FIFO 0x011F / SET_TX 0x020D).
 * multi_radio_sweep_rx_v4.cpp itself is NOT modified.
 *
 * Parameter bytes follow BENCH-CONSOLE-SPEC §8 golden and the E80 vendor
 * lr20xx-driver serialization (third_party/Radio/lr20xx_driver):
 *
 *  FLRC  SET_PACKET_PARAMS 0x0249: {0x1E, 0x7D, len>>8, len}
 *      0x1E = preamble_len(7 = 32 bits) << 2 | sync_len(2 = 4 bytes)
 *      0x7D = crc(1 = CRC_2_BYTES) | header(1 = FIX) << 2
 *             | match(7 = Match123) << 3 | tx_syncword(1) << 6
 *      length field is the chip's 16-bit field (v4 sent {0x00, len8}) —
 *      the 511-byte lift.
 *  FLRC  SET_MODULATION_PARAMS 0x0248: {(CR_3/4=1) << 4 | BT_1=7} = 0x17
 *      (v4 used 0x15 = BT 0.5 with chip CRC OFF; the bench golden §8
 *      mandates BT 1.0 + chip CRC-2B for cross-board sessions)
 *  FLRC  SET_SYNC_WORD 0x024C: word #1 = 0x12AD101B (spec §8)
 *  LoRa  SET_MODULATION_PARAMS 0x0220: (sf<<4)|bw, (crEnum<<4)|ldro;
 *      bw 125/250/500 kHz = 0x04/0x05/0x06; CR denom 5..8 -> 0x01..0x04;
 *      LDRO on when symbol time > 16 ms (E80 NO_PPM)
 *  LoRa  SET_PACKET_PARAMS 0x0221: preamble 8 symb, pld_len, flags 0x02
 *      = EXPLICIT(0)<<2 | CRC_ON(1)<<1 | IQ_OFF(0)
 *  LoRa  SET_SYNC_WORD 0x0223: 0x34 (E80 cross-board bench value)
 *
 * Packet-status parsing mirrors the vendor driver, whose rbuffer starts
 * AFTER the 2-byte status prefix (lr20xx_hal_read strips it):
 *  LoRa GET_LORA_PACKET_STATUS 0x022A (read 8): len=rbuffer[1] (8-bit),
 *      snr_qdb = (int8_t) rbuffer[2], rssi_half = -2*rbuffer[3]
 *      - ((rbuffer[5] >> 1) & 1)
 *  FLRC GET_FLRC_PACKET_STATUS 0x024B (read 7): len = rbuffer[0..1] 16-bit,
 *      rssi_half = -2*rbuffer[2] - ((rbuffer[4] >> 2) & 1), snr = 0
 *
 * IRQ bits (vendor lr20xx_system_types.h): RX_DONE 1<<18, TX_DONE 1<<19,
 * TIMEOUT 1<<21, CRC_ERROR 1<<22.
 */

#include <Arduino.h>
#include <SPI.h>

#include "bench_radio_sx1280.h"

/* ---- Board pins (v4 wiring: Waveshare RP2040-Zero + LR2021F33) ------------- */

#define PIN_SCK     2
#define PIN_MOSI    3
#define PIN_MISO    4
#define PIN_CS      5
#define PIN_BUSY    6
#define PIN_RST     8

#define SPI_FREQ_HZ  20000000UL
#define XTAL_MHZ     52.0f

/* LR2021 opcodes / enums used here (vendor lr20xx_driver + field-proven v4). */
enum {
    PKT_TYPE_LORA = 0x00,
    PKT_TYPE_FLRC = 0x05,
};

/* FLRC br/bw codes (vendor br_bw enum, v4 flrcBitrateToCode). */
static uint8_t flrcBrBwCode(uint32_t br_bps)
{
    switch (br_bps)
    {
    case 2600000: return 0x00;
    case 2080000: return 0x01;
    case 1300000: return 0x02;
    case 1040000: return 0x03;
    case  650000: return 0x04;
    case  520000: return 0x05;
    case  325000: return 0x06;
    case  260000: return 0x07;
    default:      return 0x00;
    }
}

/* LoRa bw codes (vendor lora bw enum). */
static uint8_t loraBwCode(uint32_t bw_hz)
{
    if (bw_hz <= 125000) return 0x04;
    if (bw_hz <= 250000) return 0x05;
    return 0x06;
}

/* LoRa CR denominator 5..8 -> vendor enum 0x01..0x04. */
static uint8_t loraCrCode(uint8_t cr_denom)
{
    if (cr_denom >= 5 && cr_denom <= 8) return (uint8_t)(cr_denom - 4);
    return 0x01;
}

/* ---- v4 raw-SPI layer (verbatim lift) -------------------------------------- */

static SPIClassRP2040 spiRf(spi0, PIN_MISO, PIN_CS, PIN_SCK, PIN_MOSI);
static SPISettings spiSettings(SPI_FREQ_HZ, MSBFIRST, SPI_MODE0);

static bool rfAsleepFlag = false;

static void rfWaitBusy(void)
{
    uint32_t start = millis();
    while (digitalRead(PIN_BUSY))
        if (millis() - start > 100) return; /* guard: 100 ms */
}

static void rfWriteCmd(const uint8_t* cmd, size_t len)
{
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer((uint8_t*)cmd, nullptr, len);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
}

/* Single CS-low transaction: opcode + dummy read in one NSS window. */
static void rfReadCmd(const uint8_t* cmd, size_t cmdlen, uint8_t* out, size_t outlen)
{
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer((uint8_t*)cmd, nullptr, cmdlen);
    for (size_t i = 0; i < outlen; i++) out[i] = spiRf.transfer(0x00);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
}

static uint32_t rfReadIrqStatus(void)
{
    uint8_t cmd[2] = {0x01, 0x17}; /* GET_AND_CLEAR_IRQ_STATUS */
    uint8_t buf[6] = {0};
    rfReadCmd(cmd, 2, buf, 6);
    return ((uint32_t)buf[2] << 24) | ((uint32_t)buf[3] << 16) |
           ((uint32_t)buf[4] << 8) | (uint32_t)buf[5];
}

static void rfClearIrq(void)
{
    uint8_t cmd[6] = {0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF};
    rfWriteCmd(cmd, 6);
}

static void rfSetRx(void)
{
    uint8_t cmd[5] = {0x02, 0x0C, 0xFF, 0xFF, 0xFF};
    rfWriteCmd(cmd, 5);
}

static void rfSetFreqHz(uint32_t hz)
{
    double mhz = (double)hz / 1e6;
    uint32_t frf = (uint32_t)((mhz * 1e6 * (double)(1ULL << 18)) / (XTAL_MHZ * 1e6));
    uint8_t cmd[] = {0x02, 0x00, (uint8_t)(frf >> 16), (uint8_t)(frf >> 8), (uint8_t)(frf & 0xFF)};
    rfWriteCmd(cmd, 5);
}

static void rfSetTxPowerDbm(int8_t dbm)
{
    int32_t raw = (int32_t)dbm * 2 + ((dbm >= 0) ? 0 : 0);
    if (raw < 0) raw = 0;
    if (raw > 0x2C) raw = 0x2C;         /* vendor clamp: +22 dBm */
    uint8_t cmd[] = {0x02, 0x03, (uint8_t)raw, 0x04 /* ramp 304 us */};
    rfWriteCmd(cmd, 4);
}

static void rfCalibrate(float freqMHz, uint8_t rfPath)
{
    uint16_t feFreq = (uint16_t)((freqMHz / 4.0f) + 0.5f);
    if (rfPath == 1) feFreq |= 0x8000;
    uint8_t c1[] = {0x01, 0x23,
                    (uint8_t)(feFreq >> 8), (uint8_t)(feFreq & 0xFF),
                    0, 0, 0, 0, 0, 0};
    rfWriteCmd(c1, 10);
    delay(5);
    uint8_t c2[] = {0x01, 0x22, 0x5F};
    rfWriteCmd(c2, 3);
    delay(5);
}

static void rfResetAndStandby(void)
{
    pinMode(PIN_RST, OUTPUT);
    digitalWrite(PIN_RST, LOW);
    delayMicroseconds(200);
    digitalWrite(PIN_RST, HIGH);
    delay(50);
    { uint8_t c[] = {0x01, 0x11, 0x00, 0x00}; rfWriteCmd(c, 4); } /* CLEAR_ERRORS */
    delay(1);
    { uint8_t c[] = {0x01, 0x28, 0x01}; rfWriteCmd(c, 3); }       /* STANDBY XOSC */
    delay(5);
}

static void rfReadRxFifo(uint8_t* data, size_t len)
{
    uint8_t cmd[2] = {0x00, 0x01}; /* READ_RX_FIFO (LR2021 16-bit opcode) */
    rfReadCmd(cmd, 2, data, len);
}

/* ---- bench_radio_ops_t ------------------------------------------------------ */

static void op_reset_configure(const bench_cfg_t* cfg, uint16_t len)
{
    uint8_t rfPath = (cfg->freq_hz > 1000000000UL) ? 1 : 0; /* HF above 1 GHz */
    float freqMHz = (float)((double)cfg->freq_hz / 1e6);

    rfResetAndStandby();

    /* SET_PACKET_TYPE */
    { uint8_t c[] = {0x02, 0x07,
                     (uint8_t)(cfg->mod == BENCH_MOD_LORA ? PKT_TYPE_LORA : PKT_TYPE_FLRC)};
      rfWriteCmd(c, 3); }
    delay(1);

    rfSetFreqHz(cfg->freq_hz);
    delay(1);

    /* SET_RX_PATH: HF=1, LF=0, no boost */
    { uint8_t c[] = {0x02, 0x01, rfPath, 0x00}; rfWriteCmd(c, 4); }
    delay(1);

    rfCalibrate(freqMHz, rfPath);

    if (cfg->mod == BENCH_MOD_LORA)
    {
        /* LDRO: low-data-rate optimize when symbol time > 16 ms
         * (symTime_ms = 2^sf / bw_kHz). */
        double symMs = (double)(1UL << cfg->sf) / ((double)cfg->bw_hz / 1000.0);
        uint8_t ldro = (symMs > 16.0) ? 1 : 0;
        uint8_t mod0 = (uint8_t)(((cfg->sf & 0x0F) << 4) | (loraBwCode(cfg->bw_hz) & 0x0F));
        uint8_t mod1 = (uint8_t)((loraCrCode(cfg->cr) << 4) | (ldro & 0x01));
        { uint8_t c[] = {0x02, 0x20, mod0, mod1}; rfWriteCmd(c, 4); }
        delay(1);
        { uint8_t c[] = {0x02, 0x23, 0x34}; rfWriteCmd(c, 3); } /* E80 bench sync */
        delay(1);
        if (len > 255) len = 255;
        { uint8_t c[] = {0x02, 0x21, 0x00, 0x08, (uint8_t)len, 0x02}; rfWriteCmd(c, 6); }
        delay(1);
    }
    else
    {
        /* FLRC golden §8: CR 3/4 + BT 1.0 */
        { uint8_t c[] = {0x02, 0x48, flrcBrBwCode(cfg->br_bps), 0x17}; rfWriteCmd(c, 4); }
        delay(1);
        { uint8_t c[] = {0x02, 0x4C, 0x01, 0x12, 0xAD, 0x10, 0x1B}; rfWriteCmd(c, 7); }
        delay(1);
        { uint8_t c[] = {0x02, 0x49, 0x1E, 0x7D,
                         (uint8_t)(len >> 8), (uint8_t)(len & 0xFF)}; rfWriteCmd(c, 6); }
        delay(1);
    }

    /* PA config — v4 field-proven bytes (LF duty 7, HF duty 16), same
     * bytes proven at 868 MHz and 2440 MHz in the v4 multi-phase sweeps. */
    { uint8_t c[] = {0x02, 0x02, 0x80, 0x00, 0x60, 0x07, 0x10}; rfWriteCmd(c, 7); }
    delay(1);

    rfSetTxPowerDbm(cfg->txpow_dbm);
    delay(1);

    /* Fallback to STDBY_RC after RX/TX (E80 demo behaviour) */
    { uint8_t c[] = {0x02, 0x06, 0x03}; rfWriteCmd(c, 3); }
    delay(1);

    /* IRQ mask: RX_DONE | TX_DONE | TIMEOUT | CRC_ERROR (0x004E0000) */
    { uint8_t c[] = {0x01, 0x15, 0x09, 0x00, 0x4E, 0x00, 0x00}; rfWriteCmd(c, 7); }
    delay(1);

    rfClearIrq();
    delay(1);

    rfAsleepFlag = false;
}

static void op_rearm_rx(const bench_cfg_t* cfg, uint16_t len)
{
    /* STANDBY XOSC -> length window -> CLEAR_FIFO -> SET_RX continuous.
     * (Length window is rewritten so START LEN= after rearm takes effect;
     * mod/sync/PA params persist from reset_configure.) */
    { uint8_t c[] = {0x01, 0x28, 0x01}; rfWriteCmd(c, 3); }
    delay(1);
    if (cfg->mod == BENCH_MOD_FLRC)
    {
        uint8_t c[] = {0x02, 0x49, 0x1E, 0x7D,
                       (uint8_t)(len >> 8), (uint8_t)(len & 0xFF)};
        rfWriteCmd(c, 6);
    }
    else
    {
        uint8_t c[] = {0x02, 0x21, 0x00, 0x08, (uint8_t)len, 0x02};
        rfWriteCmd(c, 6);
    }
    delay(1);
    { uint8_t c[] = {0x01, 0x20}; rfWriteCmd(c, 2); } /* CLEAR_RX_FIFO */
    rfClearIrq();
    rfSetRx();
    rfAsleepFlag = false;
}

static bool op_tx_packet(const uint8_t* payload, uint16_t len)
{
    /* CLEAR_ERRORS -> CLEAR_IRQ -> CLEAR_TX_FIFO -> WRITE_TX_FIFO (single CS
     * window) -> SET_TX -> wait BUSY low (500 ms guard). */
    { uint8_t c[] = {0x01, 0x11, 0x00, 0x00}; rfWriteCmd(c, 4); }
    rfClearIrq();
    { uint8_t c[] = {0x01, 0x1F}; rfWriteCmd(c, 2); }

    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(0x00);
    spiRf.transfer(0x02); /* WRITE_TX_FIFO */
    spiRf.transfer((uint8_t*)payload, nullptr, len);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();

    { uint8_t c[] = {0x02, 0x0D, 0x00, 0x00, 0x00}; rfWriteCmd(c, 5); } /* SET_TX */

    uint32_t start = millis();
    for (;;)
    {
        rfWaitBusy();
        if (!digitalRead(PIN_BUSY))
            break;                         /* BUSY low: TX finished       */
        if (millis() - start > 500)
            return false;                  /* air-time guard tripped      */
        delay(1);
    }
    rfClearIrq();
    rfAsleepFlag = false;
    return true;
}

static void op_standby_rc(void)
{
    uint8_t c[] = {0x01, 0x28, 0x00};
    rfWriteCmd(c, 3);
}

static void op_sleep_now(void)
{
    /* SET_SLEEP 0x0127: RAM retention on, no 32 kHz, no wake timer
     * (E80 radio_bench_sleep semantics). Wake via reconfigure (HW reset). */
    uint8_t c[] = {0x01, 0x27, 0x02, 0x00, 0x00, 0x00, 0x00};
    rfWriteCmd(c, 7);
    rfAsleepFlag = true;
}

static bool op_is_asleep(void)
{
    return rfAsleepFlag;
}

const bench_radio_ops_t bench_radio_sx1280_ops = {
    op_reset_configure,
    op_rearm_rx,
    op_tx_packet,
    op_standby_rc,
    op_sleep_now,
    op_is_asleep,
};

/* ---- Service pump ------------------------------------------------------------ */

struct pkt_status_t
{
    uint16_t len;
    int16_t  rssi_half_dbm;
    int8_t   snr_qdb;
};

static void get_pkt_status_lora(pkt_status_t* st)
{
    uint8_t cmd[2] = {0x02, 0x2A};
    uint8_t r[8];
    rfReadCmd(cmd, 2, r, 8);
    /* rbuffer = r[2..7] (vendor hal strips the 2 status bytes) */
    st->len           = r[3];
    st->snr_qdb       = (int8_t)r[4];
    st->rssi_half_dbm = (int16_t)(-2 * (int16_t)r[5] - (int16_t)((r[7] >> 1) & 1));
}

static void get_pkt_status_flrc(pkt_status_t* st)
{
    uint8_t cmd[2] = {0x02, 0x4B};
    uint8_t r[7];
    rfReadCmd(cmd, 2, r, 7);
    st->len           = (uint16_t)(((uint16_t)r[2] << 8) | r[3]);
    st->rssi_half_dbm = (int16_t)(-2 * (int16_t)r[4] - (int16_t)((r[6] >> 2) & 1));
    st->snr_qdb       = 0;
}

static uint8_t rxBuf[RP2040_BENCH_LEN_MAX_FLRC];

void bench_radio_sx1280_service(void)
{
    uint32_t irq = rfReadIrqStatus(); /* GET_AND_CLEAR */
    if (irq == 0)
        return;

    bool rx_role = bench_rp2040_role_is_rx();
    const bench_cfg_t* cfg = bench_rp2040_cfg();
    bool lora = (cfg->mod == BENCH_MOD_LORA);

    if (irq & (1UL << 22)) /* CRC_ERROR: RSSI still valid */
    {
        pkt_status_t st = {0, 0, 0};
        if (lora) get_pkt_status_lora(&st);
        else      get_pkt_status_flrc(&st);
        if (rx_role)
        {
            bench_rp2040_rx_event(NULL, 0, st.rssi_half_dbm, st.snr_qdb, false);
            op_rearm_rx(cfg, bench_rp2040_rx_len());
        }
        return;
    }

    if (irq & (1UL << 18)) /* RX_DONE */
    {
        pkt_status_t st = {0, 0, 0};
        if (lora) get_pkt_status_lora(&st);
        else      get_pkt_status_flrc(&st);
        uint16_t len = st.len;
        if (len > (lora ? RP2040_BENCH_LEN_MAX_LORA : RP2040_BENCH_LEN_MAX_FLRC))
            len = lora ? RP2040_BENCH_LEN_MAX_LORA : RP2040_BENCH_LEN_MAX_FLRC;
        if (rx_role && len > 0)
        {
            /* Read the FIFO FIRST (packet status may reset the read pointer,
             * v4 lesson) — status was read above only for len/rssi. */
            rfReadRxFifo(rxBuf, len);
            bench_rp2040_rx_event(rxBuf, len, st.rssi_half_dbm, st.snr_qdb, true);
            op_rearm_rx(cfg, bench_rp2040_rx_len());
        }
        return;
    }

    /* TX_DONE (1<<19) / TIMEOUT (1<<21) / others: tx_packet() is a
     * synchronous BUSY-wait and timeouts are backstopped in the core;
     * nothing else to fold. IRQs were cleared by the GET_AND_CLEAR read. */
}

void bench_radio_sx1280_begin(void)
{
    pinMode(PIN_CS, OUTPUT);
    digitalWrite(PIN_CS, HIGH);
    pinMode(PIN_BUSY, INPUT);
    pinMode(PIN_RST, OUTPUT);
    digitalWrite(PIN_RST, HIGH);
    spiRf.begin();
}
