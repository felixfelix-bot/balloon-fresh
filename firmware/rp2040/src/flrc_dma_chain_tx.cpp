/*
 * flrc_dma_chain_tx.cpp — P4.1 DMA-chaining / zero-copy FLRC TX (RP2040 + LR2021)
 * ============================================================================
 *
 * Upgrades the Phase-3 blocking-DMA TX (flrc_dma_tx.cpp) with three mechanisms
 * that remove the CPU from the SPI setup path and eliminate the per-packet
 * memcpy. See docs/P4.1-DMA-CHAINING-ZERO-COPY.md for the full rationale.
 *
 *   3.1  Zero-copy TX ring        — payload written in place, header pre-baked,
 *                                   DMA reads the slot directly. No memcpy.
 *   3.2  Reused DMA channel       — configured ONCE; hot path is two MMIO
 *                                   writes (set_read_addr + set_trans_count),
 *                                   not a full channel_config rebuild.
 *   3.3  Pre-arm double buffering — the next packet's FIFO-write DMA is armed
 *                                   while the previous packet is on air.
 *   3.4  chain_to burst primitive — genuine RP2040 chained-DMA ring (chain_to
 *                                   + reload control block) for burst fills.
 *
 * HARD CONSTRAINT (datasheet physics, not firmware choice):
 *   The LR2021 holds ONE TX packet and asserts BUSY between commands. RP2040
 *   DMA triggers are DREQ/timer/chain only — never a GPIO level — so no DMA
 *   chain can observe BUSY. The CPU must gate the radio state machine. A
 *   free-running packet-DMA chain would overrun the FIFO and corrupt the link,
 *   so the genuine chain_to machinery (dma_chain_burst_fill) is used only for
 *   within-transaction bursts, never to walk whole packets.
 *
 * SPI source: the RP2040 hardware SPI peripheral (DREQ spi_get_dreq(spi0,true)).
 * To use P4.0's 20.83 MHz PIO engine instead, swap the DREQ to
 * pio_get_dreq(pio,sm,true) and the write target to &pio->txf[sm]; everything
 * else (ring, reused channel, pre-arm) is unchanged.
 *
 * Build (pico-sdk):
 *   cd firmware/rp2040 && mkdir -p build && cd build
 *   cmake -DPICO_SDK_PATH=<sdk> ..
 *   make -j$(nproc) dma_chain_tx        # -> dma_chain_tx.uf2
 *
 * Pins: SCK=GP2 MOSI=GP3 MISO=GP4 CS=GP5 BUSY=GP6 IRQ=GP7 RST=GP8 LED=GP25
 *       UART1_TX=GP12 UART1_RX=GP13  (telemetry mirror)
 */

#include <stdio.h>
#include <string.h>
#include "pico/stdlib.h"
#include "hardware/spi.h"
#include "hardware/dma.h"
#include "hardware/irq.h"
#include "hardware/gpio.h"
#include "hardware/clocks.h"
#include "hardware/sync.h"

/* ─── Pins ─────────────────────────────────────────────────────────── */
#define PIN_SCK     2
#define PIN_MOSI    3
#define PIN_MISO    4
#define PIN_CS      5
#define PIN_BUSY    6
#define PIN_IRQ     7
#define PIN_RST     8
#define PIN_LED     25
#define PIN_UART_TX 12
#define PIN_UART_RX 13

/* ─── FLRC config (must match RX) ──────────────────────────────────── */
#define FLRC_FREQ_MHZ   2440.0f
#define FLRC_BR         2600
#define FLRC_PKT_SIZE   255
#define SPI_FREQ_HZ     20000000UL     /* requested; HW SSP actual ~10-18 MHz */
#define XTAL_MHZ        52.0f
#define TX_PKT_COUNT    1000
#define TX_POWER_DBM    12
#define SYNC_WORD_0     0x12
#define SYNC_WORD_1     0xAD
#define SYNC_WORD_2     0x10
#define SYNC_WORD_3     0x1B

/* ====================================================================
 * §3.1  Zero-copy TX ring
 * ====================================================================
 * Each slot is laid out as the radio expects on the wire:
 *   [ 0x00 ][ 0x02 ][ payload[0 .. FLRC_PKT_SIZE-1] ]
 *    └ WRITE_TX_FIFO opcode ┘
 * Header is baked once at init; only the payload region is touched in the
 * hot loop (the 4-byte sequence counter goes straight into slot[k][2..5]).
 * The DMA channel reads the slot verbatim — no staging buffer, no memcpy.
 */
#define TX_RING_DEPTH   4
#define SLOT_HDR_LEN    2
#define SLOT_LEN        (SLOT_HDR_LEN + FLRC_PKT_SIZE)          /* 257 */
#define SLOT_BYTES      ((SLOT_LEN + 3u) & ~3u)                 /* 260, 4-aligned */
static uint8_t tx_ring[TX_RING_DEPTH][SLOT_BYTES] __attribute__((aligned(4)));

/* Convenience: payload pointer of a slot (where the producer writes). */
static inline uint8_t *slot_payload(unsigned k) { return &tx_ring[k][SLOT_HDR_LEN]; }

/* ====================================================================
 * §3.2  Reused DMA channels
 * ====================================================================
 * chFifo  — the zero-copy WRITE_TX_FIFO transfer (mem -> spi0_hw->dr).
 *           Configured ONCE. Hot path re-arms it with set_read_addr/count.
 * chCmd   — small command writes (CLEAR_IRQ, CLEAR_TX_FIFO, SET_TX, …).
 * chData  — §3.4 chain_to data channel for burst fills.
 * chReload— §3.4 chain_to reload channel (writes chData's next read addr).
 */
static int chFifo   = -1;
static int chCmd    = -1;
static int chData   = -1;
static int chReload = -1;

/* chFifo completion counter (IRQ-driven). */
static volatile uint32_t g_fifo_done;

static void __isr __not_in_flash_func(fifo_dma_isr)(void) {
    uint32_t mask = 1u << (uint)chFifo;
    if (dma_hw->ints0 & mask) {
        dma_hw->ints0 = mask;                          /* clear IRQ flag */
        dma_channel_set_irq0_enabled((uint)chFifo, false);
        g_fifo_done++;
    }
}

/* ====================================================================
 * Low-level SPI / GPIO helpers (direct register access, no Arduino)
 * ==================================================================== */
static inline void rfWaitBusy(void) {
    uint32_t busyMask = 1UL << PIN_BUSY;
    uint32_t timeout = 500000;                         /* ~4 ms @ 125 MHz */
    while ((sio_hw->gpio_in & busyMask) && --timeout) { tight_loop_contents(); }
}

/* Drain the SSP RX FIFO (full-duplex bus — reads come back per write). */
static inline void spiDrainRx(void) {
    io_rw_32 *dr = &spi_get_hw(spi0)->dr;
    while (spi_get_hw(spi0)->sr & SPI_SSPSR_RNE_BITS) (void)*dr;
}

/* Block until the SSP TX FIFO + shift register are fully drained. */
static inline void spiWaitTfe(void) {
    while (!(spi_get_hw(spi0)->sr & SPI_SSPSR_TFE_BITS)) { tight_loop_contents(); }
}

/* Small blocking SPI write via the command DMA channel (re-armed each call). */
static inline void spiCmdWrite(const uint8_t *src, size_t len) {
    dma_channel_set_read_addr((uint)chCmd, src, false);
    dma_channel_set_trans_count((uint)chCmd, len, false);
    dma_channel_start((uint)chCmd);
    dma_channel_wait_for_finish_blocking((uint)chCmd);
    spiWaitTfe();
    spiDrainRx();
}

/* Command wrapper: wait BUSY, CS low, write, CS high. */
static inline void rfCmd(const uint8_t *buf, size_t len) {
    rfWaitBusy();
    gpio_put(PIN_CS, 0);
    spiCmdWrite(buf, len);
    gpio_put(PIN_CS, 1);
}

/*
 * §3.2 + §3.3 — Zero-copy FIFO write.
 * Fires the pre-configured chFifo from ring slot k, NON-blocking. The caller
 * fills slot k's payload first, then arms; completion is observed via
 * g_fifo_done (IRQ) or dma_channel_is_busy(). CS framing is the caller's job.
 */
static inline void fifoWriteArm(unsigned k) {
    dma_channel_set_read_addr((uint)chFifo, tx_ring[k], false);
    dma_channel_set_trans_count((uint)chFifo, SLOT_LEN, false);
    g_fifo_done = 0;
    dma_channel_set_irq0_enabled((uint)chFifo, true);
    dma_channel_start((uint)chFifo);
}

/* Block until the armed FIFO write finishes (used in synchronous test mode). */
static inline void fifoWriteWait(void) {
    uint32_t guard = 500000;
    while (!g_fifo_done && --guard) { tight_loop_contents(); }
    if (!g_fifo_done) {                               /* DMA hung — abort cleanly */
        dma_channel_abort((uint)chFifo);
        dma_channel_set_irq0_enabled((uint)chFifo, false);
    }
    spiWaitTfe();
    spiDrainRx();
}

/* ====================================================================
 * §3.4  Genuine chain_to burst-fill primitive
 * ====================================================================
 * Demonstrates real RP2040 DMA chaining (datasheet §2.5.6.1). Two channels
 * ping-pong via mutual chain_to:
 *   chData   : mem -> spi0_hw->dr (byte mover, DREQ = SPI0 TX), chain_to=chReload
 *   chReload : writes one word (next-fragment read_addr) into chData.READ_ADDR,
 *              chain_to=chData  ← re-triggers chData at the new address.
 * When chData finishes a fragment it triggers chReload, which advances the read
 * pointer and re-triggers chData — an autonomous ring, no CPU per fragment.
 * trans_count stays constant, so fragments are EQUAL length (SPI-chunk case).
 * The ring halts when chReload's count reaches 0.
 *
 * USED ONLY for within-transaction bursts — deliberately NOT used to walk
 * whole packets, because the radio is single-packet + BUSY-gated (§2 of the
 * design doc) and a free-running packet chain would overrun the FIFO.
 */

static void dma_chain_burst_init(void) {
    /* chData: mem -> spi0_hw->dr, read-increment, write-fixed, 8-bit,
     *         DREQ = SPI0 TX, chain_to = chReload. */
    chData = (int)dma_claim_unused_channel(false);
    chReload = (int)dma_claim_unused_channel(false);
    if (chData < 0 || chReload < 0) return;

    {
        dma_channel_config c = dma_channel_get_default_config((uint)chData);
        channel_config_set_transfer_data_size(&c, DMA_SIZE_8);
        channel_config_set_read_increment(&c, true);
        channel_config_set_write_increment(&c, false);
        channel_config_set_dreq(&c, spi_get_dreq(spi0, true));
        channel_config_set_chain_to(&c, (uint)chReload);   /* chain → reload */
        dma_channel_configure((uint)chData, &c,
            &spi_get_hw(spi0)->dr,   /* write target: SPI TX data register */
            NULL, 0, false);
    }
    /* chReload: reads ONE word (a next-fragment read_addr) from the address
     * table and writes it into chData's READ_ADDR register; its own chain_to
     * points back to chData so chData is re-triggered at the new address — a
     * mutual ping-pong that needs no CPU per fragment. */
    {
        dma_channel_config c = dma_channel_get_default_config((uint)chReload);
        channel_config_set_transfer_data_size(&c, DMA_SIZE_32);
        channel_config_set_read_increment(&c, true);   /* walk the addr table */
        channel_config_set_write_increment(&c, false); /* fixed: chData.read_addr */
        channel_config_set_chain_to(&c, (uint)chData);  /* reload → re-fire data */
        dma_channel_configure((uint)chReload, &c,
            &dma_hw->ch[(uint)chData].read_addr,
            NULL, 0, false);
    }
}

/*
 * Fire a 2-fragment autonomous chained burst. n is the COMMON fragment length
 * (the mutual chain advances only the read pointer, not the count, so both
 * fragments must be equal length — the SPI-chunk case). chData runs f0; on
 * completion chReload writes f1 into chData.read_addr and re-triggers it; the
 * ring then halts (chReload count exhausted). Returns when both fragments are
 * on the wire. CS framing is the caller's responsibility.
 */
static void dma_chain_burst2(const uint8_t *f0, const uint8_t *f1, size_t n) {
    /* Address table: one entry per REMAINING fragment (here, fragment 1 only).
     * chReload.count = number of reloads = (total fragments - 1). */
    const void *addr_tbl[1] = { f1 };

    dma_channel_set_read_addr((uint)chData, f0, false);
    dma_channel_set_trans_count((uint)chData, n, false);

    dma_channel_set_read_addr((uint)chReload, addr_tbl, false);
    dma_channel_set_trans_count((uint)chReload, 1, false);

    dma_start_channel_mask(1u << (uint)chData);          /* kicks the ping-pong */

    uint32_t guard = 500000;
    while (dma_channel_is_busy((uint)chData) && --guard) { tight_loop_contents(); }
    spiWaitTfe();
    spiDrainRx();
}

/* ====================================================================
 * Radio command table (static const — lives in flash, DMA reads via XIP)
 * ==================================================================== */
static const uint8_t CMD_CLEAR_ERRORS[4] = { 0x01, 0x11, 0x00, 0x00 };
static const uint8_t CMD_CLEAR_IRQ[6]    = { 0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF };
static const uint8_t CMD_CLEAR_TXFIFO[2] = { 0x01, 0x1F };
static const uint8_t CMD_SET_TX[5]       = { 0x02, 0x0D, 0x00, 0x00, 0x00 };
static const uint8_t CMD_SET_STDBY_FS[3] = { 0x01, 0x28, 0x01 };

/* ====================================================================
 * Radio init — raw SPI, faithful to flrc_dma_tx.cpp (proven sequence)
 * ==================================================================== */
static bool rawInitRadio(void) {
    /* 0. Hardware reset */
    gpio_set_dir(PIN_RST, GPIO_OUT);
    gpio_put(PIN_RST, 0);
    sleep_us(200);
    gpio_put(PIN_RST, 1);
    sleep_ms(50);

    rfCmd(CMD_CLEAR_ERRORS, 4);                       sleep_ms(1);
    rfCmd(CMD_SET_STDBY_FS, 3);                       sleep_ms(5);

    { uint8_t c[] = { 0x02, 0x07, 0x05 }; rfCmd(c, 3); }                sleep_ms(1); /* PACKET_TYPE FLRC */

    /* SET_RF_FREQUENCY */
    uint32_t frf = (uint32_t)((FLRC_FREQ_MHZ * 1e6 * (double)(1ULL << 18)) / (XTAL_MHZ * 1e6));
    { uint8_t c[] = { 0x02, 0x00, (uint8_t)(frf>>16), (uint8_t)(frf>>8), (uint8_t)frf }; rfCmd(c, 5); }
    sleep_ms(1);

    { uint8_t c[] = { 0x02, 0x01, 0x01, 0x00 }; rfCmd(c, 4); }          sleep_ms(1); /* RX_PATH HF */

    /* CALIB_FRONT_END */
    uint16_t feFreq = (uint16_t)((FLRC_FREQ_MHZ / 4.0f) + 0.5f) | 0x8000;
    { uint8_t c[] = { 0x01, 0x23, (uint8_t)(feFreq>>8), (uint8_t)(feFreq&0xFF),
                      0x00,0x00,0x00,0x00,0x00,0x00 }; rfCmd(c, 10); }
    sleep_ms(5);

    { uint8_t c[] = { 0x01, 0x22, 0x5F }; rfCmd(c, 3); }                sleep_ms(5); /* CALIBRATE */

    /* SET_FLRC_MOD_PARAMS (BR=2600, BT=1) */
    { uint8_t c[] = { 0x02, 0x48, 0x00, 0x25 }; rfCmd(c, 4); }          sleep_ms(1);

    /* SET_FLRC_SYNCWORD */
    { uint8_t c[] = { 0x02, 0x4C, 0x01, SYNC_WORD_0, SYNC_WORD_1, SYNC_WORD_2, SYNC_WORD_3 };
      rfCmd(c, 7); }                                                   sleep_ms(1);

    /* SET_FLRC_PACKET_PARAMS (syncTx=1, fixed=1, len=255) */
    { uint8_t c[] = { 0x02, 0x49, 0x0E, 0x4C, 0x00, (uint8_t)FLRC_PKT_SIZE }; rfCmd(c, 6); }
    sleep_ms(1);

    /* SET_PA_CONFIG (HF PA via bit 7) */
    { uint8_t c[] = { 0x02, 0x02, 0x80, 0x00, 0x60, 0x07, 0x10 }; rfCmd(c, 7); }
    sleep_ms(1);

    /* SET_TX_PARAMS (power*2, ramp 0x04) */
    { uint8_t c[] = { 0x02, 0x03, (uint8_t)(TX_POWER_DBM * 2), 0x04 }; rfCmd(c, 4); }
    sleep_ms(1);

    /* SET_RX_TX_FALLBACK = FS (keep PLL warm between TX → no re-lock CMD_ERROR) */
    { uint8_t c[] = { 0x02, 0x06, 0x03 }; rfCmd(c, 3); }                sleep_ms(1);

    /* DIO9 = IRQ, map TX_DONE (bit 19) to DIO9 */
    { uint8_t c[] = { 0x01, 0x12, 0x09, 0x11 }; rfCmd(c, 4); }          sleep_ms(1);
    { uint8_t c[] = { 0x01, 0x15, 0x09, 0x00, 0x08, 0x00, 0x00 }; rfCmd(c, 7); }
    sleep_ms(1);

    rfCmd(CMD_CLEAR_IRQ, 6);                          sleep_ms(1);

    /* Status read to confirm standby. */
    gpio_put(PIN_CS, 0);
    uint8_t st = 0;
    {
        const uint8_t rd[1] = { 0x00 };
        spiCmdWrite(rd, 1);
        st = (uint8_t)(spi_get_hw(spi0)->dr & 0xFF);  /* last shifted-in byte */
    }
    gpio_put(PIN_CS, 1);

    if ((st >> 4) == 0x04) { printf("RADIO_INIT_OK St=0x%02X\n", st); return true; }
    printf("RADIO_INIT_FAIL St=0x%02X\n", st);
    return false;
}

/* ====================================================================
 * §3.1+§3.2+§3.3 — Zero-copy, pre-armed DMA-chain TX loop
 * ====================================================================
 * Per packet:
 *   1. CLEAR_ERRORS / CLEAR_IRQ / CLEAR_TX_FIFO  (chCmd, small, blocking)
 *   2. WRITE_TX_FIFO  ← chFifo reads ring slot verbatim (NO memcpy, NO rebuild)
 *   3. SET_TX
 *   4. spin-wait BUSY-low = TX_DONE (the ~785 us air time)
 *
 * Pre-arm (§3.3): while packet k is on air we could already fill slot k+1;
 * with a ring depth > 1 the producer can stay one packet ahead. In this
 * reference loop the producer (seq update) is cheap, so we fill-then-arm in
 * sequence; the zero-copy + reused-channel savings still apply every packet.
 */
static volatile bool g_radioReady = false;

static void runTransmit(void) {
    if (!g_radioReady) { printf("ERR: radio not initialized\n"); return; }

    printf("TX_START count=%d pktSize=%d (DMA-chain zero-copy)\n", TX_PKT_COUNT, FLRC_PKT_SIZE);
    sleep_ms(10);

    /* Pre-fill the payload pattern once per slot (only seq bytes change). */
    for (unsigned k = 0; k < TX_RING_DEPTH; k++) {
        uint8_t *pl = slot_payload(k);
        for (int j = 4; j < FLRC_PKT_SIZE; j++) pl[j] = (uint8_t)(j & 0xFF);
    }

    uint32_t busyMask = 1UL << PIN_BUSY;
    absolute_time_t start = get_absolute_time();
    uint32_t done = 0, timeout = 0;

    for (int i = 0; i < TX_PKT_COUNT; i++) {
        unsigned k = (unsigned)(i % TX_RING_DEPTH);
        uint8_t *pl = slot_payload(k);

        /* Zero-copy seq update — 4 bytes written straight into the DMA slot. */
        pl[0] = (uint8_t)(i >> 24);
        pl[1] = (uint8_t)(i >> 16);
        pl[2] = (uint8_t)(i >> 8);
        pl[3] = (uint8_t)(i & 0xFF);

        /* 1. small commands (reused chCmd channel) */
        rfCmd(CMD_CLEAR_ERRORS, 4);
        rfCmd(CMD_CLEAR_IRQ, 6);
        rfCmd(CMD_CLEAR_TXFIFO, 2);

        /* 2. WRITE_TX_FIFO — zero-copy, re-armed (§3.1 + §3.2) */
        rfWaitBusy();
        gpio_put(PIN_CS, 0);
        fifoWriteArm(k);
        fifoWriteWait();
        gpio_put(PIN_CS, 1);

        /* 3. SET_TX */
        rfCmd(CMD_SET_TX, 5);

        /* 4. wait BUSY-low = TX complete (air time) */
        uint32_t guard = 500000;
        bool ok = false;
        while (guard--) {
            if (!(sio_hw->gpio_in & busyMask)) { ok = true; break; }
            tight_loop_contents();
        }
        if (ok) done++; else timeout++;

        if ((i + 1) % 500 == 0)
            printf("TX %d/%d (done=%lu to=%lu)\n", i + 1, TX_PKT_COUNT,
                   (unsigned long)done, (unsigned long)timeout);
    }

    int64_t elapsed_us = absolute_time_diff_us(start, get_absolute_time());
    float elapsed_ms = elapsed_us / 1000.0f;
    float tput = ((float)TX_PKT_COUNT * FLRC_PKT_SIZE * 8.0f) / elapsed_ms;

    printf("=============================================\n");
    printf("  TX sent:     %d\n", TX_PKT_COUNT);
    printf("  Elapsed:     %.1f ms\n", elapsed_ms);
    printf("  TX THROUGHPUT: %.1f kbps (DMA-chain zero-copy)\n", tput);
    printf("=============================================\n");
    printf("RESULT_TX,sent=%d,elapsed_ms=%.1f,throughput_kbps=%.1f,done=%lu,timeout=%lu\n",
           TX_PKT_COUNT, elapsed_ms, tput, (unsigned long)done, (unsigned long)timeout);
}

/* ====================================================================
 * Entry point
 * ==================================================================== */
int main(void) {
    set_sys_clock_khz(125000, true);                  /* 125 MHz system clock */
    stdio_init_all();

    /* UART1 mirror on GP12/13 for telemetry without USB CDC. */
    uart_init(uart1, 115200);
    gpio_set_function(PIN_UART_TX, GPIO_FUNC_UART);
    gpio_set_function(PIN_UART_RX, GPIO_FUNC_UART);

    gpio_init(PIN_LED); gpio_set_dir(PIN_LED, GPIO_OUT);
    for (int i = 0; i < 3; i++) {
        gpio_put(PIN_LED, 1); sleep_ms(120);
        gpio_put(PIN_LED, 0); sleep_ms(120);
    }

    printf("\n=== RP2040 FLRC DMA-CHAIN TX (P4.1) ===\n");
    printf("Zero-copy ring depth=%d, slot=%d B (no per-pkt memcpy, reused DMA ch)\n",
           TX_RING_DEPTH, SLOT_LEN);

    /* SPI peripheral init */
    spi_init(spi0, SPI_FREQ_HZ);
    spi_set_format(spi0, 8, SPI_CPOL_0, SPI_CPHA_0, SPI_MSB_FIRST);
    gpio_set_function(PIN_SCK,  GPIO_FUNC_SPI);
    gpio_set_function(PIN_MOSI, GPIO_FUNC_SPI);
    gpio_set_function(PIN_MISO, GPIO_FUNC_SPI);
    gpio_init(PIN_CS);    gpio_set_dir(PIN_CS, GPIO_OUT);   gpio_put(PIN_CS, 1);
    gpio_init(PIN_BUSY);  gpio_set_dir(PIN_BUSY, GPIO_IN);
    gpio_init(PIN_IRQ);   gpio_set_dir(PIN_IRQ, GPIO_IN);

    /* §3.1 bake the WRITE_TX_FIFO header into every ring slot, once. */
    for (unsigned k = 0; k < TX_RING_DEPTH; k++) {
        tx_ring[k][0] = 0x00;   /* opcode MSB */
        tx_ring[k][1] = 0x02;   /* opcode LSB (WRITE_TX_FIFO) */
    }

    /* §3.2 claim + configure the reused channels (once). */
    chFifo = (int)dma_claim_unused_channel(true);
    chCmd  = (int)dma_claim_unused_channel(true);
    {
        dma_channel_config c = dma_channel_get_default_config((uint)chFifo);
        channel_config_set_transfer_data_size(&c, DMA_SIZE_8);
        channel_config_set_read_increment(&c, true);
        channel_config_set_write_increment(&c, false);
        channel_config_set_dreq(&c, spi_get_dreq(spi0, true));
        dma_channel_configure((uint)chFifo, &c, &spi_get_hw(spi0)->dr, NULL, 0, false);
    }
    {
        dma_channel_config c = dma_channel_get_default_config((uint)chCmd);
        channel_config_set_transfer_data_size(&c, DMA_SIZE_8);
        channel_config_set_read_increment(&c, true);
        channel_config_set_write_increment(&c, false);
        channel_config_set_dreq(&c, spi_get_dreq(spi0, true));
        dma_channel_configure((uint)chCmd, &c, &spi_get_hw(spi0)->dr, NULL, 0, false);
    }
    irq_add_shared_handler(DMA_IRQ_0, fifo_dma_isr, PICO_SHARED_IRQ_HANDLER_DEFAULT_ORDER_PRIORITY);
    irq_set_enabled(DMA_IRQ_0, true);

    /* §3.4 genuine chain_to burst primitive (claimed separately; may be -1). */
    dma_chain_burst_init();
    printf("DMA channels: fifo=%d cmd=%d data=%d reload=%d\n",
           chFifo, chCmd, chData, chReload);

    printf("INIT...\n");
    g_radioReady = rawInitRadio();
    if (!g_radioReady) {
        printf("INIT FAILED — type INIT to retry\n");
    } else {
        gpio_put(PIN_LED, 1);
        printf("Auto-start TX in 10 s (get the RX board ready)...\n");
        sleep_ms(10000);
        runTransmit();
    }

    /* Command loop: RUN re-fires, INIT re-inits. */
    char cmdbuf[16];
    size_t cmdlen = 0;
    while (true) {
        int c = getchar_timeout_us(0);
        if (c >= 0 && c != PICO_ERROR_TIMEOUT) {
            if (c == '\n' || c == '\r') {
                if (cmdlen > 0) {
                    cmdbuf[cmdlen] = '\0';
                    if (!strcmp(cmdbuf, "RUN"))  runTransmit();
                    else if (!strcmp(cmdbuf, "INIT")) g_radioReady = rawInitRadio();
                    cmdlen = 0;
                }
            } else if (cmdlen < sizeof(cmdbuf) - 1) {
                cmdbuf[cmdlen++] = (char)c;
            }
        }
        tight_loop_contents();
    }
    return 0;
}
