/*
 * radio.h — shared radio setup for sweep TX/RX
 * LR2021 on RP2040 coprocessor pins
 */
#pragma once
#include <Arduino.h>
#include <SPI.h>
#include <RadioLib.h>

// Pin mapping (same as rp2040-flrc-max)
#define LR2021_SCK   2
#define LR2021_MOSI  3
#define LR2021_MISO  4
#define LR2021_CS    5
#define LR2021_BUSY  6
#define LR2021_IRQ   7
#define LR2021_RST   8

// SPI instance
static SPIClassRP2040 spiRf(spi0, LR2021_MISO, LR2021_CS, LR2021_SCK, LR2021_MOSI);
static SPISettings spiSettings(16000000, MSBFIRST, SPI_MODE0);

static Module radioMod(LR2021_CS, LR2021_IRQ, LR2021_RST, LR2021_BUSY, spiRf, spiSettings);
static LR2021 radio(&radioMod);

volatile bool rxFlag = false;
void rxISR() { rxFlag = true; }

// Configure radio for a given sweep config
int16_t configureRadio(const SweepConfig& cfg) {
    radio.standby();
    int16_t state = RADIOLIB_ERR_NONE;

    switch (cfg.mod) {
        case MOD_FLRC:
            state = radio.beginFLRC(cfg.freq, cfg.bitrate,
                                    RADIOLIB_LR2021_FLRC_CR_1_0,
                                    cfg.power, 12,
                                    RADIOLIB_SHAPING_0_5);
            break;
        case MOD_LORA:
            state = radio.begin(cfg.freq, cfg.bw_khz, cfg.sf, 7,
                                RADIOLIB_LR2021_LORA_SYNC_WORD_PRIVATE,
                                cfg.power, 8);
            break;
        case MOD_GFSK:
            state = radio.beginGFSK(cfg.freq, (float)cfg.bitrate,
                                    50.0, 200.0, cfg.power, 16);
            break;
    }

    if (state == RADIOLIB_ERR_NONE) {
        radio.setCRC(0);
        radio.irqDioNum = 9;
    }
    return state;
}
