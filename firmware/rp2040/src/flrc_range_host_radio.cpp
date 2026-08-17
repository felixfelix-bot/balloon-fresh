/**
 * @file    flrc_range_host_radio.cpp
 * @brief   FW-5a implementation: band matrix, FW-4 tick conversion, and the
 *          full-init / band-aware-reinit command sequences (pure, sink-
 *          driven) plus the firmware SPI transport + burst spin.
 *
 * Byte-level provenance is documented in flrc_range_host_radio.h and in
 * docs/evidence/stage-a/fw5a-radio-band-matrix.md. Every frame emitted by
 * the builders is asserted byte-exact in host-tests/test_radio.cpp.
 */

#include "flrc_range_host_radio.h"

#include <string.h>

/* LoRa BW code -> Hz for the LDRO long-symbol decision (BW-1 table, the
 * binding single source of truth for LR2021 BW codes). */
#include "lr2021_bw_codes.h"

/* ---- Band matrix --------------------------------------------------------- */

bench_radio_band_params_t bench_radio_band_for_freq(uint32_t freq_hz) {
    bench_radio_band_params_t p;
    p.is_hf = freq_hz > BENCH_RADIO_HF_THRESHOLD_HZ;
    p.rx_path = p.is_hf ? 0x01 : 0x00; /* dual_radio step 4 */
    p.tx_path = p.is_hf ? 0x01 : 0x00; /* multi_radio v4 L786 */
    p.pa_sel = p.is_hf ? 0x80 : 0x00;  /* multi_radio v4 L791 [setPaConfig(LF)] */
    /* CALIB_FRONT_END param: (freq_mhz/4)+0.5 — integer form
     * (Hz + 2 MHz) / 4 MHz, equal to the float provenance at every probe
     * point; |0x8000 is HF-only (the sweep hardwires it — B1 bug class). */
    p.fe_freq = (uint16_t)(((freq_hz + 2000000UL) / 4000000UL) |
                           (p.is_hf ? 0x8000U : 0x0000U));
    return p;
}

/* ---- Chip TX timeout ticks ----------------------------------------------- */

uint32_t bench_radio_tx_timeout_ticks(uint32_t tx_timeout_ms) {
    /* vendored lr20xx_driver: ticks = ms * 32768 / 1000 (uint32 math;
     * exact up to 131,072 ms — FW-4 caps at 60,000 ms). */
    uint32_t t = tx_timeout_ms * 32768UL / 1000UL;
    return (t > BENCH_RADIO_TX_TIMEOUT_TICKS_MAX) ? BENCH_RADIO_TX_TIMEOUT_TICKS_MAX : t;
}

void bench_radio_set_tx_bytes(uint32_t timeout_ticks, uint8_t out[5]) {
    out[0] = 0x02;
    out[1] = 0x0D;
    out[2] = (uint8_t)(timeout_ticks >> 16);
    out[3] = (uint8_t)(timeout_ticks >> 8);
    out[4] = (uint8_t)(timeout_ticks & 0xFF);
}

/* ---- Small helpers ------------------------------------------------------- */

uint8_t bench_radio_flrc_br_to_code(uint16_t kbps) {
    switch (kbps) {
        case 2600: return 0x00;
        case 2080: return 0x01;
        case 1300: return 0x02;
        case 1040: return 0x03;
        case 650:  return 0x04;
        case 520:  return 0x05;
        case 325:  return 0x06;
        case 260:  return 0x07;
        default:   return BENCH_RADIO_FLRC_BR_INVALID; /* protocol has no default rate */
    }
}

uint8_t bench_radio_tx_power_byte(int8_t dbm) {
    /* Exact half-dB math for integer dBm; two's-complement signed byte.
     * (The sweep's (uint8_t)(dbm*2.0f+0.5f) is a half-dB off for negative
     * powers — it was only ever used at +12.5 dBm.) */
    return (uint8_t)(int16_t)(dbm * 2);
}

/* ---- Config sanity ------------------------------------------------------- */

bool bench_radio_cfg_valid(const bench_radio_cfg_t *cfg) {
    if (!cfg) return false;
    if (cfg->pkt_len < 1 || cfg->pkt_len > 255) return false;
    if (cfg->mod == BENCH_MOD_FLRC)
        return bench_radio_flrc_br_to_code(cfg->flrc_br_kbps) != BENCH_RADIO_FLRC_BR_INVALID;
    if (cfg->mod == BENCH_MOD_LORA) {
        if (cfg->lora_sf < 5 || cfg->lora_sf > 12) return false;
        if (cfg->lora_cr < 1 || cfg->lora_cr > 4) return false;
        return lr2021_bw_code_to_hz(cfg->lora_bw_code) != 0;
    }
    return false;
}

/* ---- Sequence building (pure) ------------------------------------------- */

/* RF divider: frf = freq_hz * 2^18 / 52 MHz (sweep rfSetFreq, integer form;
 * freq_hz up to ~2.64 GHz * 262144 needs 64-bit math). */
static uint32_t bench_radio_frf(uint32_t freq_hz) {
    return (uint32_t)(((uint64_t)freq_hz * 262144ULL) / 52000000ULL);
}

/* LoRa LDRO: symbol time > 16 ms — exact integer rewrite of the dual_radio
 * float check (1<<sf)/bw_hz*1000 > 16.0  <=>  (1<<sf)*1000 > 16*bw_hz. */
static uint8_t bench_radio_lora_ldro(uint8_t sf, uint32_t bw_hz) {
    return ((uint32_t)(1UL << sf) * 1000UL > 16UL * bw_hz) ? 1 : 0;
}

/* SET_RF_FREQ — 0x0200 with a 3-byte payload is SET_STANDBY, the 5-byte
 * form is SET_RF_FREQ (length-distinguished, like 0x0202 path vs PA). */
static void emit_set_freq(uint32_t freq_hz, bench_radio_cmd_sink_t sink, void *user) {
    uint32_t frf = bench_radio_frf(freq_hz);
    uint8_t cmd[] = {0x02, 0x00, (uint8_t)(frf >> 16), (uint8_t)(frf >> 8), (uint8_t)frf};
    sink(user, cmd, sizeof cmd, 1);
}

/* dual_radio matrix step 5: CALIB_FRONT_END with the band's fe param. */
static void emit_calib_front_end(const bench_radio_band_params_t *band,
                                 bench_radio_cmd_sink_t sink, void *user) {
    uint8_t cmd[] = {0x01, 0x23, (uint8_t)(band->fe_freq >> 8), (uint8_t)band->fe_freq,
                     0x00, 0x00, 0x00, 0x00, 0x00, 0x00};
    sink(user, cmd, sizeof cmd, 5);
}

/* dual_radio matrix steps 9/10 — SET_TX_PATH + SET_PA_CONFIG frames — are
 * emitted inline in both builders (txPath / paCfg arrays below); the band
 * RX_PATH frame sits in emit_calib_front_end's caller context. */

/* dual_radio matrix step 7: the mode-specific MOD/PKT block.
 * FLRC: {02 48 brBw 0x25} + sync word 12 AD 10 1B + {02 49 0C 4C len16}
 * LoRa: {02 20 sfBw cr|ldro} + {02 23 12} + {02 21 00 08 len flags=0x02} */
static void emit_mod_block(const bench_radio_cfg_t *cfg,
                           bench_radio_cmd_sink_t sink, void *user) {
    if (cfg->mod == BENCH_MOD_FLRC) {
        uint8_t brBw = bench_radio_flrc_br_to_code(cfg->flrc_br_kbps);
        uint8_t mod[] = {0x02, 0x48, brBw, 0x25}; /* CR=None+BT0.5 */
        sink(user, mod, sizeof mod, 1);

        uint8_t sync[] = {0x02, 0x4C, 0x01, 0x12, 0xAD, 0x10, 0x1B};
        sink(user, sync, sizeof sync, 1);

        uint8_t pkt[] = {0x02, 0x49, 0x0C, 0x4C, (uint8_t)(cfg->pkt_len >> 8),
                         (uint8_t)(cfg->pkt_len & 0xFF)};
        sink(user, pkt, sizeof pkt, 1);
    } else {
        uint32_t bw_hz = lr2021_bw_code_to_hz(cfg->lora_bw_code);
        uint8_t sf_bw = (uint8_t)((cfg->lora_sf << 4) | (cfg->lora_bw_code & 0x0F));
        uint8_t cr_ldro = (uint8_t)(((cfg->lora_cr & 0x0F) << 4) |
                                    (bench_radio_lora_ldro(cfg->lora_sf, bw_hz) & 0x01));
        uint8_t mod[] = {0x02, 0x20, sf_bw, cr_ldro};
        sink(user, mod, sizeof mod, 1);

        uint8_t sync[] = {0x02, 0x23, 0x12};
        sink(user, sync, sizeof sync, 1);

        /* preamble 8, explicit header, CRC on (dual_radio L456) */
        uint8_t pkt[] = {0x02, 0x21, 0x00, 0x08, (uint8_t)cfg->pkt_len, 0x02};
        sink(user, pkt, sizeof pkt, 1);
    }
}

void bench_radio_emit_full_init(const bench_radio_cfg_t *cfg,
                                bench_radio_cmd_sink_t sink, void *user) {
    bench_radio_band_params_t band = bench_radio_band_for_freq(cfg->freq_hz);

    /* sweep cold preamble (rawInitRadio): chip wake + regulator */
    uint8_t wake[] = {0x01, 0x11, 0x00, 0x00};
    sink(user, wake, sizeof wake, 1);
    uint8_t dcdc[] = {0x01, 0x28, 0x01};
    sink(user, dcdc, sizeof dcdc, 5);

    /* dual_radio matrix step 2: packet type (FLRC=0x04 / LoRa=0x00) */
    uint8_t pktType[] = {0x02, 0x07,
                         (uint8_t)((cfg->mod == BENCH_MOD_FLRC) ? 0x04 : 0x00)};
    sink(user, pktType, sizeof pktType, 1);

    emit_set_freq(cfg->freq_hz, sink, user); /* step 3 */

    /* step 4 + 5: band RX path, front-end calib (HF-only 0x8000 bit) */
    uint8_t rxPath[] = {0x02, 0x01, band.rx_path, 0x00};
    sink(user, rxPath, sizeof rxPath, 1);
    emit_calib_front_end(&band, sink, user);

    uint8_t calib[] = {0x01, 0x22, 0x5F}; /* step 6 */
    sink(user, calib, sizeof calib, 5);

    emit_mod_block(cfg, sink, user); /* step 7 */

    uint8_t txPath[] = {0x02, 0x02, band.tx_path, 0x00}; /* v4 L786 */
    sink(user, txPath, sizeof txPath, 1);
    uint8_t paCfg[] = {0x02, 0x02, band.pa_sel, 0x00, 0x60, 0x07, 0x10}; /* v4 L791 */
    sink(user, paCfg, sizeof paCfg, 1);

    uint8_t txParams[] = {0x02, 0x03, bench_radio_tx_power_byte(cfg->dbm), 0x04};
    sink(user, txParams, sizeof txParams, 1);

    uint8_t fallback[] = {0x02, 0x06, 0x03};
    sink(user, fallback, sizeof fallback, 1);
    uint8_t dioIrq[] = {0x01, 0x12, 0x09, 0x11}; /* TX_DONE -> IRQ line */
    sink(user, dioIrq, sizeof dioIrq, 1);
    uint8_t irqMask[] = {0x01, 0x15, 0x09, 0x00, 0x08, 0x00, 0x00}; /* bit19 */
    sink(user, irqMask, sizeof irqMask, 1);

    uint8_t clear[] = {0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF};
    sink(user, clear, sizeof clear, 10);
}

void bench_radio_emit_reinit(const bench_radio_cfg_t *cfg,
                             bench_radio_cmd_sink_t sink, void *user) {
    bench_radio_band_params_t band = bench_radio_band_for_freq(cfg->freq_hz);

    /* rfSwitchBitrate skeleton, extended band-aware (B1):
     * STDBY -> MOD_PARAMS -> CALIBRATE -> CLEAR, + path/PA per band. */
    uint8_t stdby[] = {0x02, 0x00, 0x01}; /* STDBY_RC before param changes */
    sink(user, stdby, sizeof stdby, 1);

    /* FREQ/MOD changes arrive here too: re-apply the band's RX path and
     * front-end calibration so a frequency change never reuses a stale
     * (or wrong-band) front-end calib — the core B1 hazard. */
    uint8_t rxPath[] = {0x02, 0x01, band.rx_path, 0x00};
    sink(user, rxPath, sizeof rxPath, 1);
    emit_calib_front_end(&band, sink, user);

    emit_mod_block(cfg, sink, user);

    uint8_t calib[] = {0x01, 0x22, 0x5F}; /* BW changes with mod params */
    sink(user, calib, sizeof calib, 5);

    uint8_t txPath[] = {0x02, 0x02, band.tx_path, 0x00};
    sink(user, txPath, sizeof txPath, 1);
    uint8_t paCfg[] = {0x02, 0x02, band.pa_sel, 0x00, 0x60, 0x07, 0x10};
    sink(user, paCfg, sizeof paCfg, 1);
    uint8_t txParams[] = {0x02, 0x03, bench_radio_tx_power_byte(cfg->dbm), 0x04};
    sink(user, txParams, sizeof txParams, 1);

    uint8_t clear[] = {0x02, 0x0B, 0x02}; /* rfSwitchBitrate step 4 */
    sink(user, clear, sizeof clear, 1);
}

/* ---- Hardware layer (firmware only) -------------------------------------- */

#ifndef BENCH_RADIO_HOST_TEST

#include <Arduino.h>
#include <SPI.h>

/* Pin map + transport copied from flrc_range_tx_sweep.cpp (the proven
 * 2600 kbps backend; SCK=GP2 MOSI=GP3 MISO=GP4 CS=GP5 BUSY=GP6 IRQ=GP7
 * RST=GP8, SPI0 @ 20 MHz). */
#define RADIO_PIN_SCK 2
#define RADIO_PIN_MOSI 3
#define RADIO_PIN_MISO 4
#define RADIO_PIN_CS 5
#define RADIO_PIN_BUSY 6
#define RADIO_PIN_IRQ 7
#define RADIO_PIN_RST 8

#define RADIO_SPI_FREQ_HZ 20000000UL

static SPIClassRP2040 spiRf(spi0, RADIO_PIN_MISO, RADIO_PIN_CS, RADIO_PIN_SCK, RADIO_PIN_MOSI);
static SPISettings spiSettings(RADIO_SPI_FREQ_HZ, MSBFIRST, SPI_MODE0);

/* Single-batch FIFO frame buffer (header 2 + payload 255) + dummy RX. */
static uint8_t fifoCmd[2 + 255];
static uint8_t spiRxJunk[257];

static inline bool rfWaitBusy() {
    uint32_t busyMask = 1UL << RADIO_PIN_BUSY;
    uint32_t timeout = 100000;
    while ((sio_hw->gpio_in & busyMask) && --timeout) {}
    return timeout > 0;
}

static void rfWriteCmd(const uint8_t *buf, size_t len) {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(RADIO_PIN_CS, LOW);
    spiRf.transfer((uint8_t *)buf, spiRxJunk, len); /* single batch, continuous SCK */
    digitalWrite(RADIO_PIN_CS, HIGH);
    spiRf.endTransaction();
}

static uint8_t rfReadStatus() {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(RADIO_PIN_CS, LOW);
    uint8_t st = spiRf.transfer(0x00);
    digitalWrite(RADIO_PIN_CS, HIGH);
    spiRf.endTransaction();
    return st;
}

static uint32_t rfReadIrqStatus() {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(RADIO_PIN_CS, LOW);
    uint8_t cmd[2] = {0x01, 0x17};
    spiRf.transfer(cmd, spiRxJunk, 2);
    digitalWrite(RADIO_PIN_CS, HIGH);
    spiRf.endTransaction();
    rfWaitBusy();

    uint8_t buf[6];
    uint8_t dummy[6] = {0, 0, 0, 0, 0, 0};
    spiRf.beginTransaction(spiSettings);
    digitalWrite(RADIO_PIN_CS, LOW);
    spiRf.transfer(dummy, buf, 6);
    digitalWrite(RADIO_PIN_CS, HIGH);
    spiRf.endTransaction();
    return ((uint32_t)buf[2] << 24) | ((uint32_t)buf[3] << 16) |
           ((uint32_t)buf[4] << 8) | (uint32_t)buf[5];
}

static void rfClearIrq() {
    uint8_t cmd[6] = {0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF};
    rfWriteCmd(cmd, 6);
}

static void rfSetTx(uint32_t timeoutTicks) {
    /* B1: NEVER the sweep's continuous {02 0D 00 00 00} — the chip timeout
     * comes from FW-4 via bench_radio_tx_timeout_ticks(). */
    uint8_t cmd[5];
    bench_radio_set_tx_bytes(timeoutTicks, cmd);
    rfWriteCmd(cmd, 5);
}

static void rfWriteTxFifo(const uint8_t *data, size_t len) {
    fifoCmd[0] = 0x00; /* WRITE_TX_FIFO header */
    fifoCmd[1] = 0x02;
    memcpy(fifoCmd + 2, data, len);

    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(RADIO_PIN_CS, LOW);
    spiRf.transfer(fifoCmd, spiRxJunk, 2 + len); /* single batch */
    digitalWrite(RADIO_PIN_CS, HIGH);
    spiRf.endTransaction();
}

static void rfClearTxFifo() {
    uint8_t cmd[] = {0x01, 0x1F};
    rfWriteCmd(cmd, sizeof cmd);
}

/* Sequence sink -> transport, honoring the provenance inter-command delay. */
static void hwSink(void *user, const uint8_t *cmd, size_t len, uint32_t delay_ms) {
    (void)user;
    rfWriteCmd(cmd, len);
    if (delay_ms) delay(delay_ms);
}

void bench_radio_hardware_begin(void) {
    spiRf.begin();
    pinMode(RADIO_PIN_CS, OUTPUT);
    digitalWrite(RADIO_PIN_CS, HIGH);
    pinMode(RADIO_PIN_BUSY, INPUT);
    pinMode(RADIO_PIN_IRQ, INPUT);
}

bool bench_radio_full_init(const bench_radio_cfg_t *cfg) {
    /* Reset pulse (rawInitRadio): 200 us low, 50 ms settle. */
    pinMode(RADIO_PIN_RST, OUTPUT);
    digitalWrite(RADIO_PIN_RST, LOW);
    delayMicroseconds(200);
    digitalWrite(RADIO_PIN_RST, HIGH);
    delay(50);

    bench_radio_emit_full_init(cfg, hwSink, NULL);

    /* rawInitRadio verdict: STBY_RC(3)/FS(4)/RX(7) chip mode or TX IRQ bit. */
    uint8_t st = rfReadStatus();
    uint32_t irq = rfReadIrqStatus();
    return ((st >> 4) == 0x04 || (st >> 4) == 0x07 || (irq & 0x00020000)) != 0;
}

void bench_radio_reinit(const bench_radio_cfg_t *cfg) {
    bench_radio_emit_reinit(cfg, hwSink, NULL);
}

bool bench_radio_send_packet(const bench_radio_cfg_t *cfg,
                             const uint8_t *pkt, uint16_t len) {
    rfClearIrq();
    rfClearTxFifo();
    rfWriteTxFifo(pkt, len);
    rfSetTx(bench_radio_tx_timeout_ticks(cfg->tx_timeout_ms));

    /* Burst spin (sweep L378-398): tight poll of the IRQ line. */
    const uint32_t irqMask = 1UL << RADIO_PIN_IRQ;
    uint32_t spinCount = 0;
    while (spinCount < 500000) {
        if (sio_hw->gpio_in & irqMask) return true;
        spinCount++;
    }
    return false;
}

#endif /* !BENCH_RADIO_HOST_TEST */
