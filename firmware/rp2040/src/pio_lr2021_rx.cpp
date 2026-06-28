/*
 * pio_lr2021_rx.cpp — PIO + DMA gapless SPI RX driver for LR2021 on RP2040
 * ============================================================================
 *
 * See pio_lr2021_rx.h for the architecture overview and pio_lr2021_rx.pio for
 * the state-machine program.  This file wires that program to two DMA
 * channels and exposes a small double-buffered capture API.
 *
 * Double-buffer design
 * --------------------
 * SPEED-P6's plan sketched a free-running DMA chain (A→buffer_A, B→buffer_B,
 * chain A→B→A).  That model suits a *continuous* byte stream, but the LR2021
 * receive path is *packet-triggered*: each frame arrives, raises DIO9, and
 * must be read with a framed NSS-low transaction (cmd + payload + NSS-high)
 * before the radio is told to re-enter RX.  A continuously-clocked DMA ring
 * would (a) hold NSS low forever and (b) clock the SPI between packets,
 * breaking the framing.  We therefore realise "gapless double-buffering" as
 * the correct equivalent for this protocol: TWO payload buffers in SRAM
 * (slot 0 / slot 1), alternated per packet by lr2021_rx_arm(), so the CPU
 * parses slot N while slot N+1 is already being captured by DMA.  That is the
 * gapless property the task is after — the CPU never waits on the SPI clock.
 *
 * Data format on the wire and in SRAM
 * -----------------------------------
 * The TX DMA sends the 2-byte READ_RX_FIFO command ([0x00, 0x01]) followed by
 * N dummy 0xFF bytes (MOSI is don't-care during the read phase).  The RX DMA
 * captures 2+N bytes; the first two are the command echo (discarded) and the
 * remaining N are the payload.  Both transfers are padded up to a 32-bit
 * boundary (≤3 trailing don't-care bytes) because the DMA moves 32-bit words.
 *
 * Byte ordering: both DMA channels have BSWAP enabled and the PIO shifts
 * MSB-first (shift_left).  Verified mapping:
 *   TX: SRAM wire-order bytes [b0,b1,...] --(LE word load)--> --(BSWAP)-->
 *       word with b0 in the MSB --(PIO MSB-first)--> b0 leaves the pin first.
 *   RX: PIO collects MSB-first into a word (first byte in MSB) --(autopush)-->
 *       --(BSWAP)--> LE store into SRAM yields wire-order bytes [b0,b1,...].
 * So a plain byte array on both ends maps 1:1 to the wire.  No per-byte swap
 * in the hot path.
 *
 * SPI Mode 0 idle between transactions
 * ------------------------------------
 * After a transfer the SM stalls on `out` (TX FIFO empty); the last committed
 * instruction was `in ... side 1`, so SCK rests HIGH.  For Mode 0 the clock
 * must idle LOW while NSS is asserted, so lr2021_rx_arm() first executes a
 * one-shot `mov y,y side 0` via pio_sm_exec() to force SCK low, THEN asserts
 * NSS and starts the DMA.  (NSS high between packets isolates the slave, so
 * the high SCK while idle is harmless — but we don't rely on that.)
 *
 * Completion
 * ----------
 * The RX DMA channel's transfer count defines the frame length (the only
 * entity that knows it).  Its IRQ0 fires the shared handler, which deasserts
 * NSS, marks the slot complete, and latches it for lr2021_rx_take().
 */

#include "pio_lr2021_rx.h"

/* pico-sdk hardware APIs (provided by the arduino-pico/mbed RP2040 cores and
 * by a native pico-sdk build alike). */
#include "hardware/pio.h"
#include "hardware/dma.h"
#include "hardware/irq.h"
#include "hardware/gpio.h"
#include "hardware/sync.h"          /* save_and_disable_interrupts / restore */

#include "pio_lr2021_rx.pio.h"      /* assembled program (lr2021_rx_program) */

/* ── Compile-time geometry ──────────────────────────────────────────────── */
/* One DMA word = 4 bytes; total transfer = cmd(2) + payload(N), padded. */
#define LR2021_RX_SLOTS          2u
#define LR2021_RX_BUF_BYTES      (LR2021_RX_CMD_BYTES + LR2021_RX_MAX_PAYLOAD)

/* ── Runtime state (all in BSS) ─────────────────────────────────────────── */
static PIO    g_pio    = pio0;
static uint   g_sm     = 0;
static uint   g_off    = 0;          /* PIO load offset                    */
static int    g_dma_tx = -1;         /* mem -> PIO TX FIFO                 */
static int    g_dma_rx = -1;         /* PIO RX FIFO -> mem                 */
static uint8_t g_cs_pin = 0;

/* TX command buffer: [0x00, 0x01, 0xFF, 0xFF, ...] — wire order, BSWAP'd by
 * the DMA so it leaves the pin as 0x00, 0x01, then dummy clocks. */
static uint8_t g_tx[LR2021_RX_BUF_BYTES];
/* Two RX capture buffers (slot 0 / slot 1). */
static uint8_t g_rx[LR2021_RX_SLOTS][LR2021_RX_BUF_BYTES];

/* Per-packet length requested by lr2021_rx_set_payload_len(). */
static volatile size_t g_payload_len = LR2021_RX_MAX_PAYLOAD;

/* Ping-pong bookkeeping.  Touched from main loop and ISR; the indices are
 * only mutated under irq-save guards (see take/arm/isr). */
static volatile uint8_t g_next_fill    = 0;   /* slot the next arm() fills  */
static volatile int8_t  g_cur          = -1;  /* slot being filled right now */
static volatile int8_t  g_just_filled  = -1;  /* slot ready for take()      */
static volatile bool    g_busy         = false;

static volatile uint32_t g_completed = 0;
static volatile uint32_t g_dropped   = 0;

/* ── Helpers ────────────────────────────────────────────────────────────── */

static inline void cs_low(void)  { gpio_put(g_cs_pin, 0); }
static inline void cs_high(void) { gpio_put(g_cs_pin, 1); }

/* DMA word count for the current payload length (round 2+N up to 4). */
static inline size_t frame_words(size_t payload_len) {
    size_t bytes = LR2021_RX_CMD_BYTES + payload_len;
    return (bytes + 3u) / 4u;
}

/* ── DMA completion ISR (DMA_IRQ_0) ─────────────────────────────────────── */

static void lr2021_rx_dma_isr(void) {
    if (g_dma_rx < 0 || !(dma_hw->ints0 & (1u << g_dma_rx))) return;
    dma_hw->ints0 = 1u << g_dma_rx;                 /* W1C clear            */
    dma_channel_set_irq0_enabled((uint)g_dma_rx, false);

    /* Frame complete: release NSS, publish the slot. */
    cs_high();

    uint32_t s = save_and_disable_interrupts();
    int8_t done = g_cur;
    g_cur         = -1;
    g_just_filled = done;
    g_busy        = false;
    g_completed++;
    restore_interrupts(s);
}

/* ── Public API ─────────────────────────────────────────────────────────── */

int lr2021_rx_init(uint8_t sck, uint8_t mosi, uint8_t miso,
                   uint8_t cs, float clk_mhz) {
    g_pio = pio0;
    g_cs_pin = cs;

    /* --- Pins: SCK/MOSI/MISO to PIO, NSS to plain GPIO --------------- */
    pio_gpio_init(g_pio, sck);
    pio_gpio_init(g_pio, mosi);
    pio_gpio_init(g_pio, miso);
    gpio_init(cs);
    gpio_set_dir(cs, GPIO_OUT);
    cs_high();                          /* NSS idle high                    */

    /* --- Load program + claim a state machine ------------------------ */
    g_off = pio_add_program(g_pio, &lr2021_rx_program);
    int sm = (int)pio_claim_unused_sm(g_pio, /*quiet*/ false);
    if (sm < 0) {
        pio_remove_program(g_pio, &lr2021_rx_program, g_off);
        return -1;                      /* no free SM                       */
    }
    g_sm = (uint)sm;

    /* --- State-machine config ---------------------------------------- */
    pio_sm_config c = lr2021_rx_program_get_default_config(g_off);
    sm_config_set_out_pins(&c, mosi, 1);
    sm_config_set_in_pins(&c, miso);
    sm_config_set_sideset_pins(&c, sck);   /* 1.x name; aliased in 2.x */
    sm_config_set_out_shift(&c, /*shift_right=*/false, /*autopull=*/true,  32);
    sm_config_set_in_shift (&c, /*shift_right=*/false, /*autopush=*/true,  32);

    /* SCK = sysclk / (2 * div).  sysclk is 125 MHz on the RP2040-Zero. */
    float sysclk_mhz = 125.0f;
    float div = (clk_mhz > 0.0f) ? (sysclk_mhz / (2.0f * clk_mhz)) : 3.0f;
    if (div < 1.0f)   div = 1.0f;       /* RP2040 min divider              */
    if (div > 65535.0f) div = 65535.0f;
    sm_config_set_clkdiv(&c, div);

    pio_sm_set_consecutive_pindirs(g_pio, g_sm, mosi, 1, /*out=*/true);
    pio_sm_set_consecutive_pindirs(g_pio, g_sm, sck,  1, /*out=*/true);
    pio_sm_set_consecutive_pindirs(g_pio, g_sm, miso, 1, /*out=*/false);
    pio_sm_init(g_pio, g_sm, g_off, &c);

    /* --- DMA channels ------------------------------------------------ */
    g_dma_tx = (int)dma_claim_unused_channel(false);
    g_dma_rx = (int)dma_claim_unused_channel(false);
    if (g_dma_tx < 0 || g_dma_rx < 0) {
        if (g_dma_tx >= 0) dma_channel_unclaim((uint)g_dma_tx);
        if (g_dma_rx >= 0) dma_channel_unclaim((uint)g_dma_rx);
        pio_sm_unclaim(g_pio, g_sm);
        pio_remove_program(g_pio, &lr2021_rx_program, g_off);
        g_dma_tx = g_dma_rx = -1;
        return -2;                      /* no free DMA channel             */
    }

    /* TX: SRAM(g_tx) -> PIO TX FIFO, 32-bit, read-increment, BSWAP. */
    {
        dma_channel_config dc = dma_channel_get_default_config((uint)g_dma_tx);
        channel_config_set_transfer_data_size(&dc, DMA_SIZE_32);
        channel_config_set_read_increment(&dc, true);
        channel_config_set_write_increment(&dc, false);
        channel_config_set_bswap(&dc, true);
        channel_config_set_dreq(&dc, pio_get_dreq(g_pio, g_sm, /*is_tx=*/true));
        dma_channel_configure((uint)g_dma_tx, &dc,
            /*write_addr*/ &g_pio->txf[g_sm],
            /*read_addr*/  g_tx,
            /*count*/      0,            /* set per-transfer               */
            /*trigger*/    false);
    }
    /* RX: PIO RX FIFO -> SRAM(slot), 32-bit, write-increment, BSWAP. */
    {
        dma_channel_config dc = dma_channel_get_default_config((uint)g_dma_rx);
        channel_config_set_transfer_data_size(&dc, DMA_SIZE_32);
        channel_config_set_read_increment(&dc, false);
        channel_config_set_write_increment(&dc, true);
        channel_config_set_bswap(&dc, true);
        channel_config_set_dreq(&dc, pio_get_dreq(g_pio, g_sm, /*is_tx=*/false));
        dma_channel_configure((uint)g_dma_rx, &dc,
            /*write_addr*/ g_rx[0],      /* set per-transfer               */
            /*read_addr*/  &g_pio->rxf[g_sm],
            /*count*/      0,
            /*trigger*/    false);
    }

    /* --- IRQ --------------------------------------------------------- */
    irq_add_shared_handler(DMA_IRQ_0, lr2021_rx_dma_isr,
                           PICO_SHARED_IRQ_HANDLER_DEFAULT_ORDER_PRIORITY);
    irq_set_enabled(DMA_IRQ_0, true);

    /* --- Buffers / state --------------------------------------------- */
    g_tx[0] = 0x00;                     /* READ_RX_FIFO MSB                */
    g_tx[1] = 0x01;                     /* READ_RX_FIFO LSB                */
    for (size_t i = LR2021_RX_CMD_BYTES; i < LR2021_RX_BUF_BYTES; i++)
        g_tx[i] = 0xFF;                 /* dummy clocks during read phase  */

    g_next_fill = 0; g_cur = -1; g_just_filled = -1; g_busy = false;
    g_completed = g_dropped = 0;

    /* Start the SM: it runs the 2-instruction loop, stalled on `out` (TX
     * FIFO empty) with SCK low until the first arm() feeds it. */
    pio_sm_set_enabled(g_pio, g_sm, true);
    return 0;
}

void lr2021_rx_deinit(void) {
    pio_sm_set_enabled(g_pio, g_sm, false);
    if (g_dma_rx >= 0) {
        dma_channel_set_irq0_enabled((uint)g_dma_rx, false);
        dma_channel_abort((uint)g_dma_rx);
        dma_channel_unclaim((uint)g_dma_rx);
        g_dma_rx = -1;
    }
    if (g_dma_tx >= 0) {
        dma_channel_abort((uint)g_dma_tx);
        dma_channel_unclaim((uint)g_dma_tx);
        g_dma_tx = -1;
    }
    irq_set_enabled(DMA_IRQ_0, false);
    /* Note: irq_remove_shared_handler exists but is optional on teardown.   */
    pio_sm_unclaim(g_pio, g_sm);
    pio_remove_program(g_pio, &lr2021_rx_program, g_off);
    cs_high();
    g_busy = false; g_cur = -1; g_just_filled = -1;
}

void lr2021_rx_set_payload_len(size_t len) {
    if (len == 0) len = 1;
    if (len > LR2021_RX_MAX_PAYLOAD) len = LR2021_RX_MAX_PAYLOAD;
    uint32_t s = save_and_disable_interrupts();
    g_payload_len = len;
    restore_interrupts(s);
}

int lr2021_rx_arm(void) {
    uint32_t s = save_and_disable_interrupts();
    if (g_busy) { restore_interrupts(s); g_dropped++; return -1; }

    uint8_t slot = g_next_fill;
    size_t  len  = g_payload_len;
    size_t  words = frame_words(len);

    /* The TX DMA will read `words` 32-bit words from g_tx (cmd + dummies). */
    dma_channel_set_read_addr((uint)g_dma_tx, g_tx, /*trigger=*/false);
    dma_channel_set_trans_count((uint)g_dma_tx, words, /*trigger=*/false);
    /* The RX DMA will write `words` 32-bit words into the chosen slot. */
    dma_channel_set_write_addr((uint)g_dma_rx, g_rx[slot], /*trigger=*/false);
    dma_channel_set_trans_count((uint)g_dma_rx, words, /*trigger=*/false);
    dma_channel_set_irq0_enabled((uint)g_dma_rx, true);

    g_cur      = (int8_t)slot;
    g_busy     = true;
    g_next_fill = (uint8_t)(slot ^ 1u);
    restore_interrupts(s);

    /* Force SCK low for a clean Mode 0 entry, then assert NSS. */
    pio_sm_exec(g_pio, g_sm,
                pio_encode_mov(pio_y, pio_y) | pio_encode_sideset_opt(1, 0));
    cs_low();

    /* Start both channels in the same cycle so TX (clock source) and RX stay
     * in lockstep from the first bit. */
    dma_start_channel_mask((1u << (uint)g_dma_tx) | (1u << (uint)g_dma_rx));
    return (int)slot;
}

bool lr2021_rx_busy(void) {
    return g_busy;
}

int lr2021_rx_take(const uint8_t **payload, size_t *plen) {
    uint32_t s = save_and_disable_interrupts();
    int8_t slot = g_just_filled;
    if (slot < 0) { restore_interrupts(s); return -1; }
    g_just_filled = -1;
    size_t len = g_payload_len;
    restore_interrupts(s);

    if (payload) *payload = &g_rx[(uint)slot][LR2021_RX_CMD_BYTES];
    if (plen)    *plen    = len;
    return (int)slot;
}

void lr2021_rx_cs_high(void) { cs_high(); }

uint32_t lr2021_rx_completed_count(void) { return g_completed; }
uint32_t lr2021_rx_dropped_count(void)   { return g_dropped; }
