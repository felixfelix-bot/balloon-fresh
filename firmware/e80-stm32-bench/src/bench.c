/**
 * @file    bench.c
 * @brief   E80 (LR2021 / STM32F103C8T6) bench firmware main.
 *
 * Bare-metal superloop:
 *   - SysTick 1 ms tick + derived microsecond timestamp for TX pacing
 *   - console line dispatch (see bench_cmd.h for the protocol)
 *   - radio task: paced TX burst state machine, RX event accumulation
 *
 * SAFETY (from the gated characterization plan):
 *   - Boot default: radio ASLEEP and TX INHIBITED (E80_BENCH_BOOT_TX_INHIBITED).
 *   - TX requires the explicit two-step "ROLE TX" then "ARM TX".
 *   - TX-hang watchdog (bench_safety.h): chip TX timeout (set_tx) aborts a
 *     stuck TX on the radio itself; superloop backstop catches a lost IRQ;
 *     STM32 IWDG resets a wedged host and the banner reports 'WDG RESET'.
 *     The IWDG starts LATE (first 'ARM TX') so 'FLASH' can drop into the ROM
 *     bootloader without an unfed watchdog resetting mid-write.
 *   - FREQ only accepts 863-870 MHz (EU SRD) unless "BAND OVERRIDE <pin>" was accepted
 *     (pin logged on accept). Band/freq are echoed in "ID?".
 *   - "FLASH" jumps to the STM32F1 ROM bootloader (system memory, 0x1FFFF000)
 *     for headless re-flash — refused with 'ERR POWER-CYCLE FIRST' once the
 *     IWDG has started (it cannot be stopped and the ROM code never feeds it).
 */

#include "main.h"
#include "bench_cmd.h"
#include "bench_payload.h"
#include "bench_safety.h"
#include "bench_stats.h"
#include "console.h"
#include "radio_bench.h"

#include <stddef.h>
#include <string.h>

/* Forward declarations (defined below, used by the *_Init helpers) */
void Error_Handler(void);

SPI_HandleTypeDef hspi1;
UART_HandleTypeDef huart1;
static IWDG_HandleTypeDef hiwdg; /* TX-hang watchdog defense 3 (bench_safety.h) */

/* ---- Bench session state ---------------------------------------------------- */

typedef enum bench_state_e
{
    BSTATE_IDLE = 0,
    BSTATE_RX_CONT,
    BSTATE_TX_BURST,
} bench_state_t;

static bench_state_t    state       = BSTATE_IDLE;
static bench_role_t     role        = BENCH_ROLE_NONE;
static bool             tx_armed    = false; /* set by ARM TX */
static bool             band_override = false;
static bool             power_outdoor = false; /* +22 dBm unlock; default +10 cap */
static radio_bench_cfg_t cfg        = {
    .mod = BENCH_MOD_LORA, .sf = 8, .bw_hz = 125000, .br_bps = 650000,
    .txpow_dbm = E80_BENCH_TXPOW_CAP_INDOOR_DBM, .freq_hz = E80_BENCH_FREQ_DEFAULT_HZ,
};

static bench_stats_t stats;

/* TX burst control */
static uint32_t tx_total     = 0;
static uint16_t tx_len       = 255;
static uint32_t tx_gap_us    = 5000;
static uint32_t tx_seq       = 0;
static uint32_t tx_t_done_us = 0;
static uint32_t tx_t_start_us = 0;   /* micros() when the in-flight packet started */
static uint32_t tx_chip_to_ms = 100; /* chip TX timeout programmed for it */
static bool     tx_wait_irq  = false;
static uint8_t  tx_buf[E80_BENCH_MAX_PAYLOAD];
static bool     session_active = false;

/* TX-hang watchdog defense 3 (bench_safety.h): the IWDG starts at the FIRST
 * 'ARM TX' — never at boot — so 'FLASH' can jump to the ROM bootloader on a
 * fresh power cycle without the unfed watchdog resetting the MCU mid-write
 * (unrecoverable app corrupt). Once set, it stays set until power-cycle. */
static bool     iwdg_active = false;

/* ---- Time ------------------------------------------------------------------- */

static uint32_t bench_micros(void)
{
    /* SysTick @ 72 MHz, LOAD = 71999 -> 1000 ticks per ms, 1 tick = 1/72 us. */
    uint32_t t1 = HAL_GetTick();
    uint32_t v  = SysTick->VAL;
    uint32_t t2 = HAL_GetTick();
    if (t1 != t2)
    {
        /* tick rolled over between the two reads: re-read after rollover */
        v = SysTick->VAL;
        t1 = t2;
    }
    return t1 * 1000U + (71999U - v) / 72U;
}

/* ---- HAL init (board bring-up copied from the vendor demo) ------------------- */

static void SystemClock_Config(void)
{
    RCC_OscInitTypeDef RCC_OscInitStruct = { 0 };
    RCC_ClkInitTypeDef RCC_ClkInitStruct = { 0 };

    /* HSE 8 MHz x9 = 72 MHz (demo) */
    RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE;
    RCC_OscInitStruct.HSEState       = RCC_HSE_ON;
    RCC_OscInitStruct.HSEPredivValue = RCC_HSE_PREDIV_DIV1;
    RCC_OscInitStruct.HSIState       = RCC_HSI_ON;
    RCC_OscInitStruct.PLL.PLLState   = RCC_PLL_ON;
    RCC_OscInitStruct.PLL.PLLSource  = RCC_PLLSOURCE_HSE;
    RCC_OscInitStruct.PLL.PLLMUL     = RCC_PLL_MUL9;
    if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
        Error_Handler();

    RCC_ClkInitStruct.ClockType      = RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_SYSCLK |
                                       RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2;
    RCC_ClkInitStruct.SYSCLKSource   = RCC_SYSCLKSOURCE_PLLCLK;
    RCC_ClkInitStruct.AHBCLKDivider  = RCC_SYSCLK_DIV1;
    RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV2;
    RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;
    if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_2) != HAL_OK)
        Error_Handler();
}

static void MX_GPIO_Init(void)
{
    GPIO_InitTypeDef GPIO_InitStruct = { 0 };

    __HAL_RCC_GPIOD_CLK_ENABLE();
    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();

    /* Default levels (demo): NSS high, NRST/LED high (LEDs off, active low) */
    HAL_GPIO_WritePin(RADIO_NSS_GPIO_Port, RADIO_NSS_Pin, GPIO_PIN_SET);
    HAL_GPIO_WritePin(GPIOB, E80_NRST_Pin | LED2_Pin | LED1_Pin, GPIO_PIN_SET);

    /* BUSY input */
    GPIO_InitStruct.Pin  = E80_BUSY_Pin;
    GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    HAL_GPIO_Init(E80_BUSY_GPIO_Port, &GPIO_InitStruct);

    /* soft NSS */
    GPIO_InitStruct.Pin   = RADIO_NSS_Pin;
    GPIO_InitStruct.Mode  = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Pull  = GPIO_PULLUP;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(RADIO_NSS_GPIO_Port, &GPIO_InitStruct);

    /* radio NRST + LEDs */
    GPIO_InitStruct.Pin   = E80_NRST_Pin | LED2_Pin | LED1_Pin;
    GPIO_InitStruct.Mode  = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Pull  = GPIO_PULLUP;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);

    /* DIO8 EXTI rising (radio IRQ) */
    GPIO_InitStruct.Pin  = E80_DIO8_Pin;
    GPIO_InitStruct.Mode = GPIO_MODE_IT_RISING;
    GPIO_InitStruct.Pull = GPIO_PULLDOWN;
    HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);

    HAL_NVIC_SetPriority(EXTI2_IRQn, 0, 0);
    HAL_NVIC_EnableIRQ(EXTI2_IRQn);
}

static void MX_SPI1_Init(void)
{
    /* Demo: SPI1 master, mode 0, 8-bit, soft NSS, PCLK2/8 = 9 MHz. */
    hspi1.Instance               = SPI1;
    hspi1.Init.Mode              = SPI_MODE_MASTER;
    hspi1.Init.Direction         = SPI_DIRECTION_2LINES;
    hspi1.Init.DataSize          = SPI_DATASIZE_8BIT;
    hspi1.Init.CLKPolarity       = SPI_POLARITY_LOW;
    hspi1.Init.CLKPhase          = SPI_PHASE_1EDGE;
    hspi1.Init.NSS               = SPI_NSS_SOFT;
    hspi1.Init.BaudRatePrescaler = SPI_BAUDRATEPRESCALER_8;
    hspi1.Init.FirstBit          = SPI_FIRSTBIT_MSB;
    hspi1.Init.TIMode            = SPI_TIMODE_DISABLE;
    hspi1.Init.CRCCalculation    = SPI_CRCCALCULATION_DISABLE;
    hspi1.Init.CRCPolynomial     = 10;
    if (HAL_SPI_Init(&hspi1) != HAL_OK)
        Error_Handler();
}

static void MX_USART1_Init(void)
{
    huart1.Instance          = USART1;
    huart1.Init.BaudRate     = E80_BENCH_BAUD_DEFAULT; /* 115200; RX is IRQ-buffered so 921600 also works */
    huart1.Init.WordLength   = UART_WORDLENGTH_8B;
    huart1.Init.StopBits     = UART_STOPBITS_1;
    huart1.Init.Parity       = UART_PARITY_NONE;
    huart1.Init.Mode         = UART_MODE_TX_RX;
    huart1.Init.HwFlowCtl    = UART_HWCONTROL_NONE;
    huart1.Init.OverSampling = UART_OVERSAMPLING_16;
    if (HAL_UART_Init(&huart1) != HAL_OK)
        Error_Handler();

    HAL_NVIC_SetPriority(USART1_IRQn, 5, 0);
    HAL_NVIC_EnableIRQ(USART1_IRQn);
}

void HAL_SPI_MspInit(SPI_HandleTypeDef* hspi)
{
    GPIO_InitTypeDef GPIO_InitStruct = { 0 };
    if (hspi->Instance == SPI1)
    {
        __HAL_RCC_SPI1_CLK_ENABLE();
        GPIO_InitStruct.Pin   = GPIO_PIN_5 | GPIO_PIN_7; /* SCK, MOSI */
        GPIO_InitStruct.Mode  = GPIO_MODE_AF_PP;
        GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_HIGH;
        HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);
        GPIO_InitStruct.Pin  = GPIO_PIN_6; /* MISO */
        GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
        HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);
    }
}

void HAL_UART_MspInit(UART_HandleTypeDef* huart)
{
    GPIO_InitTypeDef GPIO_InitStruct = { 0 };
    if (huart->Instance == USART1)
    {
        __HAL_RCC_USART1_CLK_ENABLE();
        /* PA9 TX, PA10 RX (CH340 console) */
        GPIO_InitStruct.Pin   = GPIO_PIN_9;
        GPIO_InitStruct.Mode  = GPIO_MODE_AF_PP;
        GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_HIGH;
        HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);
        GPIO_InitStruct.Pin  = GPIO_PIN_10;
        GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
        HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);
    }
}

void Error_Handler(void)
{
    /* Note: with the IWDG now starting at first ARM TX (FLASH-safety
     * reorder), a fatal error BEFORE that point hangs here instead of
     * resetting — accepted trade-off: those failures are boot-time init
     * faults with no session to lose, while an early IWDG would kill the
     * FLASH -> ROM bootloader path and brick re-flashing mid-write. After
     * the first ARM TX the IWDG turns this hang into 'WDG RESET' again. */
    __disable_irq();
    while (1)
    {
    }
}

/* ---- ROM bootloader jump (FLASH command) ------------------------------------ */

/* STM32F1 system memory: ROM bootloader at 0x1FFFF000 (NOT the 0x00000000
 * alias — this app runs with flash mapped at 0x00000000, so the real system
 * address must be used). vector[0] = initial MSP, vector[1] = entry point. */
#define E80_ROM_BOOTLOADER_BASE 0x1FFFF000UL

/* Leaves the console silent and never returns. Only called when the IWDG
 * was never started since power-on (bench_safety_flash_plan guards it). */
static void jump_to_rom_bootloader(void)
{
    /* console TX is blocking (console.c), so the 'OK JUMPING TO BOOTLOADER'
     * reply is fully on the wire; ~100 ms settle for the CH340 / host read
     * side before the console goes silent. Must run while SysTick ticks. */
    HAL_Delay(100);

    __disable_irq();

    /* Quiesce what the app owns so the ROM starts from a clean slate:
     * console UART, radio SPI (NSS idles high), radio EXTI + UART IRQs,
     * SysTick. The radio was already parked asleep (PA unkeyed). */
    HAL_UART_DeInit(&huart1);
    HAL_SPI_DeInit(&hspi1);
    HAL_NVIC_DisableIRQ(EXTI2_IRQn);
    HAL_NVIC_DisableIRQ(USART1_IRQn);
    HAL_SuspendTick();

    /* Standard F1 jump: MSP <- vector[0], PC <- vector[1]. The ROM waits
     * for the 0x7F sync byte indefinitely (no timeout), so there is no race
     * with the host starting stm32flash afterwards. */
    __set_MSP(*(volatile uint32_t*)E80_ROM_BOOTLOADER_BASE);
    ((void (*)(void))(*(volatile uint32_t*)(E80_ROM_BOOTLOADER_BASE + 4U)))();

    for (;;) { } /* not reached */
}

/* ---- IWDG late start (FLASH-safety reorder) --------------------------------- */

/* Start the IWDG at the FIRST successful 'ARM TX' (bench_safety.h: 2-4 s
 * window across the F103 LSI spread). Once started it cannot be stopped
 * except by reset — from this moment on, FLASH refuses to jump and the
 * board must be power-cycled before re-flashing. */
static void iwdg_start_once(void)
{
    if (iwdg_active)
        return;
    hiwdg.Instance       = IWDG;
    hiwdg.Init.Prescaler = IWDG_PRESCALER_64; /* PR reg 4, /64 */
    hiwdg.Init.Reload    = BENCH_IWDG_RELOAD; /* 1874 -> 2-4 s window */
    if (HAL_IWDG_Init(&hiwdg) != HAL_OK)
        Error_Handler();
    iwdg_active = true;
}

/* ---- Radio helpers ----------------------------------------------------------- */

static void radio_critical_begin(void)
{
    __disable_irq(); /* keep the EXTI radio IRQ out of an in-flight SPI access */
}

static void radio_critical_end(void)
{
    __enable_irq();
}

static void radio_ensure_awake(void)
{
    if (radio_bench_is_asleep())
    {
        radio_bench_wakeup();
    }
}

static void radio_rearm_rx(void)
{
    radio_critical_begin();
    radio_bench_apply_cfg(&cfg);
    radio_bench_rx_arm((uint16_t)(cfg.mod == BENCH_MOD_FLRC ? tx_len : 255));
    radio_critical_end();
    state = BSTATE_RX_CONT;
}

static void radio_sleep_now(void)
{
    radio_critical_begin();
    if (state == BSTATE_TX_BURST)
    {
        /* Force standby before sleep so a pending TX finishes/aborts cleanly. */
        lr20xx_system_set_standby_mode(E80_CONTEXT, LR20XX_SYSTEM_STANDBY_MODE_RC);
    }
    radio_bench_sleep();
    radio_critical_end();
    state = BSTATE_IDLE;
}

/* ---- TX-hang watchdog (see bench_safety.h for the layered design) ---------- */

/* Send tx_buf as the next burst packet with the chip TX timeout armed. */
static void tx_send_current(void)
{
    /* Defense 1 — chip TX timeout: worst-case airtime * 2 + slack, so the
     * LR2021 itself ends a stuck TX (PA unkeyed) even if the host wedges. */
    tx_chip_to_ms = bench_safety_tx_timeout_ms(cfg.mod, cfg.sf, cfg.bw_hz,
                                               cfg.br_bps, tx_len);
    radio_critical_begin();
    stats.tx_attempted++;
    radio_bench_tx_packet(tx_buf, tx_len, tx_chip_to_ms);
    radio_critical_end();
    tx_wait_irq   = true;
    tx_t_start_us = bench_micros();
}

/* TX-timeout abort: burst over, radio to STDBY then asleep (PA unkeyed),
 * session stopped — the same end state as STOP, plus the ERR line the
 * operator/host sees in the console log. If BUSY is stuck high the SPI
 * below spins with IRQs off; the IWDG then resets the board and the boot
 * banner reports 'WDG RESET' (defense 3). */
static void tx_abort_timeout(void)
{
    radio_sleep_now(); /* forces STDBY first while state == TX_BURST */
    tx_wait_irq = false;
    stats.t_stop_us = bench_micros();
    session_active = false;
    console_put("ERR TX-TIMEOUT SEQ=");
    console_put_u32(tx_seq);
    console_putln("");
}

/* ---- Command replies ---------------------------------------------------------- */

static void reply_err(const char* reason)
{
    console_put("ERR ");
    console_putln(reason);
}

static void print_id(void)
{
    console_put("ID E80BENCH v1.2 role=");
    console_put(role == BENCH_ROLE_TX ? "TX" : role == BENCH_ROLE_RX ? "RX" : "NONE");
    console_put(tx_armed ? " armed=1" : " armed=0");
    if (cfg.mod == BENCH_MOD_LORA)
    {
        console_put(" mod=lora sf=");
        console_put_u32(cfg.sf);
        console_put(" bw=");
        console_put_u32(cfg.bw_hz);
    }
    else
    {
        console_put(" mod=flrc br=");
        console_put_u32(cfg.br_bps);
    }
    console_put(" freq=");
    console_put_u32(cfg.freq_hz);
    console_put(band_override ? " band=OVERRIDE" : " band=863-870MHz");
    console_put(" pa=");
    console_put_i32(cfg.txpow_dbm);
    console_put(power_outdoor ? " pcap=+22dBm(OUTDOOR)" : " pcap=+10dBm");
    console_put(" chip=");
    console_put_u32(radio_bench_chip_major);
    console_put(".");
    console_put_u32(radio_bench_chip_minor);
    console_put(radio_bench_is_asleep() ? " radio=asleep" : " radio=awake");
    console_put(" ");
    console_put(bench_safety_boot_field(iwdg_active));
    console_putln("");
}

/* ---- Command dispatch ---------------------------------------------------------- */

static void handle_cmd(const bench_cmd_t* c)
{
    switch (c->id)
    {
    case BENCH_CMD_ID:
        if (radio_bench_is_asleep())
        {
            radio_critical_begin();
            radio_bench_wakeup();
            radio_bench_init(); /* full demo init, refreshes version cache */
            radio_bench_sleep();
            radio_critical_end();
        }
        print_id();
        break;

    case BENCH_CMD_HELP:
        /* Chunked: console_put truncates a single call at 95 chars, so the
         * old single-literal HELP line was cut off mid-list on the wire. */
        console_put("CMDS: ID? | ROLE TX|RX|NONE | ARM TX | MOD loRa <sf5-12> <bw125|250|500> | ");
        console_put("MOD flrc <br_kbps 260..2600> <dbm0-10> | FREQ <hz> | PA <dbm> | ");
        console_put("POWER MODE OUTDOOR <pin> | ");
        console_put("START N=<n> LEN=<6-511> GAP=<us> | STAT? | STOP | ");
        console_put("FLASH (ROM bootloader) | BAND OVERRIDE <pin>");
        console_putln("");
        break;

    case BENCH_CMD_ROLE:
        if (c->role == BENCH_ROLE_TX)
        {
            /* Two-step safety: arming is cleared on every role change. */
            tx_armed = false;
            role = BENCH_ROLE_TX;
            radio_ensure_awake();
            radio_critical_begin();
            radio_bench_apply_cfg(&cfg);
            lr20xx_system_set_standby_mode(E80_CONTEXT, LR20XX_SYSTEM_STANDBY_MODE_RC);
            radio_critical_end();
            state = BSTATE_IDLE;
            console_putln("OK ROLE TX (TX INHIBITED - SEND 'ARM TX' TO ENABLE)");
        }
        else if (c->role == BENCH_ROLE_RX)
        {
            tx_armed = false;
            role = BENCH_ROLE_RX;
            radio_ensure_awake();
            bench_stats_reset(&stats);
            stats.t_start_us = bench_micros();
            session_active = true;
            radio_rearm_rx();
            console_putln("OK ROLE RX (CONTINUOUS)");
        }
        else
        {
            role = BENCH_ROLE_NONE;
            tx_armed = false;
            radio_sleep_now();
            console_putln("OK ROLE NONE (RADIO ASLEEP)");
        }
        break;

    case BENCH_CMD_ARM_TX:
        if (role != BENCH_ROLE_TX)
        {
            reply_err("ROLE NOT TX");
            return;
        }
        tx_armed = true;
        console_putln("OK ARMED (TX ENABLED)");
        /* IWDG late start (first ARM TX only): from here on a wedged host
         * resets (WDG RESET banner) — and FLASH requires a power-cycle. */
        iwdg_start_once();
        if (iwdg_active)
            console_putln("NOTE IWDG STARTED (2-4S WINDOW) - 'FLASH' NOW REQUIRES POWER-CYCLE");
        break;

    case BENCH_CMD_MOD:
    {
        if (c->mod == BENCH_MOD_FLRC && c->txpow_dbm >= 0)
        {
            int cap = power_outdoor ? E80_BENCH_TXPOW_MAX_DBM : E80_BENCH_TXPOW_CAP_INDOOR_DBM;
            if (c->txpow_dbm > cap)
            {
                reply_err(cap == E80_BENCH_TXPOW_CAP_INDOOR_DBM
                              ? "RANGE (INDOOR CAP 0-10 DBM; UNLOCK: POWER MODE OUTDOOR 2026)"
                              : "RANGE (0-22 DBM)");
                return;
            }
            cfg.txpow_dbm = c->txpow_dbm;
        }
        if (c->mod == BENCH_MOD_LORA)
        {
            cfg.mod   = BENCH_MOD_LORA;
            cfg.sf    = c->sf;
            cfg.bw_hz = c->bw_hz;
            console_put("OK MOD lora sf=");
            console_put_u32(cfg.sf);
            console_put(" bw=");
            console_put_u32(cfg.bw_hz);
            console_putln("");
        }
        else
        {
            cfg.mod    = BENCH_MOD_FLRC;
            cfg.br_bps = c->br_bps;
            console_put("OK MOD flrc br=");
            console_put_u32(cfg.br_bps);
            console_put(" pa=");
            console_put_i32(cfg.txpow_dbm);
            console_putln("");
        }
        if (role == BENCH_ROLE_RX)
            radio_rearm_rx();
        break;
    }

    case BENCH_CMD_FREQ:
    {
        bool allowed = band_override ? (c->freq_hz >= E80_BENCH_OVERRIDE_MIN_HZ &&
                                        c->freq_hz <= E80_BENCH_OVERRIDE_MAX_HZ)
                                     : (c->freq_hz >= E80_BENCH_BAND_MIN_HZ &&
                                        c->freq_hz <= E80_BENCH_BAND_MAX_HZ);
        if (!allowed)
        {
            reply_err("BAND (EU SRD 863-870MHZ ONLY, SEE 'BAND OVERRIDE <PIN>')");
            return;
        }
        cfg.freq_hz = c->freq_hz;
        if (role == BENCH_ROLE_RX)
            radio_rearm_rx();
        else if (role == BENCH_ROLE_TX && !radio_bench_is_asleep())
        {
            radio_critical_begin();
            radio_bench_apply_cfg(&cfg); /* re-applies PA/freq path per band */
            radio_critical_end();
        }
        console_put("OK FREQ ");
        console_put_u32(cfg.freq_hz);
        console_putln("");
        break;
    }

    case BENCH_CMD_BAND_OVERRIDE:
        if (c->pin != E80_BENCH_OVERRIDE_PIN)
        {
            reply_err("PIN");
            return;
        }
        band_override = true;
        /* SAFETY LOG: out-of-band TX unlocked. */
        console_put("OK BAND OVERRIDE PIN ");
        console_put_u32(c->pin);
        console_putln(" ACCEPTED - OUT-OF-BAND TX ENABLED, OPERATOR ASSUMES REGULATORY RESPONSIBILITY");
        break;

    case BENCH_CMD_POWER_OUTDOOR:
        if (c->pin != E80_BENCH_OVERRIDE_PIN)
        {
            reply_err("PIN");
            return;
        }
        power_outdoor = true;
        /* SAFETY LOG: indoor +10 dBm cap lifted, +22 dBm allowed (outdoor sessions only). */
        console_put("OK POWER MODE OUTDOOR PIN ");
        console_put_u32(c->pin);
        console_putln(" ACCEPTED - TX POWER CAP LIFTED TO +22 DBM, OUTDOOR RANGE SESSIONS ONLY");
        break;

    case BENCH_CMD_PA:
    {
        int cap = power_outdoor ? E80_BENCH_TXPOW_MAX_DBM : E80_BENCH_TXPOW_CAP_INDOOR_DBM;
        if (c->txpow_dbm < 0 || c->txpow_dbm > cap)
        {
            reply_err(cap == E80_BENCH_TXPOW_CAP_INDOOR_DBM
                          ? "RANGE (INDOOR CAP 0-10 DBM; UNLOCK: POWER MODE OUTDOOR 2026)"
                          : "RANGE (0-22 DBM)");
            return;
        }
        cfg.txpow_dbm = c->txpow_dbm;
        if (!radio_bench_is_asleep())
        {
            radio_critical_begin();
            radio_bench_apply_cfg(&cfg);
            radio_critical_end();
        }
        console_put("OK PA ");
        console_put_i32(cfg.txpow_dbm);
        console_putln(" DBM");
        break;
    }

    case BENCH_CMD_START:
    {
        if (role == BENCH_ROLE_RX)
        {
            /* On the RX board the same START line just configures the expected
             * packet length (FLRC FIX_LEN window) and re-arms continuous RX.
             * The bench ctl script sends the identical line to both boards. */
            tx_len = (uint16_t)c->len_bytes;
            bench_stats_reset(&stats);
            stats.t_start_us = bench_micros();
            session_active = true;
            radio_rearm_rx();
            console_put("OK RX ARMED len=");
            console_put_u32(tx_len);
            console_putln("");
            return;
        }
        if (role != BENCH_ROLE_TX)
        {
            reply_err("ROLE NOT TX");
            return;
        }
        if (!tx_armed)
        {
            reply_err("NOT ARMED (SEND 'ARM TX')");
            return;
        }
        uint16_t max_len = (cfg.mod == BENCH_MOD_LORA) ? 255 : 511;
        if (c->len_bytes > max_len)
        {
            reply_err("LEN (MAX 255 LORA / 511 FLRC)");
            return;
        }
        tx_total  = c->n_pkts;
        tx_len    = (uint16_t)c->len_bytes;
        tx_gap_us = c->gap_us;
        tx_seq    = 0;
        tx_wait_irq = false;

        bench_stats_reset(&stats);
        session_active = true;
        radio_ensure_awake();
        radio_critical_begin();
        radio_bench_apply_cfg(&cfg);
        radio_critical_end();
        bench_payload_build(tx_buf, tx_len, tx_seq);
        state = BSTATE_TX_BURST; /* set before TX starts: the IRQ path may fire */
        tx_send_current();
        stats.t_start_us = bench_micros();
        console_put("OK START n=");
        console_put_u32(tx_total);
        console_put(" len=");
        console_put_u32(tx_len);
        console_put(" gap_us=");
        console_put_u32(tx_gap_us);
        console_putln("");
        break;
    }

    case BENCH_CMD_STAT:
    {
        uint32_t elapsed;
        if (session_active)
            elapsed = bench_stats_elapsed_us(stats.t_start_us, bench_micros());
        else if (stats.t_stop_us != 0)
            elapsed = bench_stats_elapsed_us(stats.t_start_us, stats.t_stop_us);
        else
            elapsed = 0;

        console_put("STAT role=");
        console_put(role == BENCH_ROLE_TX ? "TX" : role == BENCH_ROLE_RX ? "RX" : "NONE");
        console_put(" sent=");
        console_put_u32(stats.tx_attempted);
        console_put(" sent_ok=");
        console_put_u32(stats.tx_done);
        console_put(" rx=");
        console_put_u32(stats.rx_ok);
        console_put(" crc_err=");
        console_put_u32(stats.rx_crc_err);
        console_put(" per_x1e6=");
        console_put_u32(bench_stats_per_ppm(&stats));
        if (stats.rx_seq_valid)
        {
            uint32_t lo, hi, trials;
            uint32_t expected = stats.rx_last_seq - stats.rx_first_seq + 1;
            trials = expected;
            bench_stats_wilson_ppm(stats.rx_ok, trials, &lo, &hi);
            console_put(" per_ci_x1e6=[");
            console_put_u32(1000000 - hi);
            console_put(",");
            console_put_u32(1000000 - lo);
            console_put("]");
        }
        console_put(" elapsed_s=");
        console_put_dec1((int32_t)(elapsed / 100000U)); /* s with 1 decimal */
        console_put(" kbps=");
        console_put_u32(bench_stats_kbps(
            (role == BENCH_ROLE_RX) ? (uint64_t)stats.rx_bytes
                                    : ((uint64_t)stats.tx_done * (uint64_t)tx_len),
            elapsed));
        console_put(" rssi_avg_dbm=");
        console_put_dec1(bench_stats_rssi_avg_half_dbm(&stats) * 5); /* half-dBm -> 0.1 dBm */
        console_put(" snr_avg_db=");
        console_put_dec1(bench_stats_snr_avg_cdb(&stats) / 10);
        console_put(" drops=");
        console_put_u32(radio_bench_evt_drops());
        console_putln("");
        break;
    }

    case BENCH_CMD_STOP:
        radio_sleep_now();
        stats.t_stop_us = bench_micros();
        session_active = false;
        console_putln("OK STOP (RADIO ASLEEP)");
        break;

    case BENCH_CMD_FLASH:
    {
        bench_flash_plan_t plan = bench_safety_flash_plan(iwdg_active);
        console_putln(bench_safety_flash_reply(plan));
        if (plan == BENCH_FLASH_JUMP)
        {
            /* Park the radio first (STDBY -> sleep: PA unkeyed, NSS high).
             * No burst can be in flight: START requires ARM TX, and any
             * successful ARM TX would have refused the jump above. */
            radio_sleep_now();
            jump_to_rom_bootloader(); /* never returns */
        }
        /* Refused: IWDG running since an ARM TX — operator must power-cycle
         * (the ROM bootloader would not feed the IWDG; a WDG reset during
         * a write can brick the app unrecoverably). */
        break;
    }

    default:
        reply_err(bench_cmd_err_str(c->err));
        break;
    }
}

/* ---- Radio task ---------------------------------------------------------------- */

static void radio_task(void)
{
    rb_evt_t e;

    /* Defense 2 — superloop backstop: no TX_DONE/TIMEOUT serviced within the
     * window (EXTI lost, mailbox drop) -> force-abort the burst. */
    if (state == BSTATE_TX_BURST && tx_wait_irq &&
        bench_safety_tx_backstop_fired(tx_t_start_us, bench_micros(),
                                       tx_chip_to_ms))
    {
        tx_abort_timeout();
        return;
    }

    /* TX pacing */
    if (state == BSTATE_TX_BURST && !tx_wait_irq)
    {
        if (stats.tx_attempted >= tx_total)
        {
            /* Burst finished after last TX_DONE. */
            stats.t_stop_us = bench_micros();
            session_active = false;
            radio_critical_begin();
            lr20xx_system_set_standby_mode(E80_CONTEXT, LR20XX_SYSTEM_STANDBY_MODE_RC);
            radio_bench_sleep();
            radio_critical_end();
            state = BSTATE_IDLE;
            console_putln("TX DONE (RADIO ASLEEP)");
            return;
        }
        uint32_t now = bench_micros();
        if ((uint32_t)(now - tx_t_done_us) >= tx_gap_us)
        {
            tx_seq++;
            bench_payload_build(tx_buf, tx_len, tx_seq);
            tx_send_current();
        }
    }

    /* Event mailbox */
    while (radio_bench_poll_event(&e))
    {
        switch (e.type)
        {
        case RB_EVT_TX_DONE:
            stats.tx_done++;
            tx_t_done_us = bench_micros();
            tx_wait_irq = false;
            break;

        case RB_EVT_TX_TIMEOUT:
            /* Defense 1 tripped: the LR2021 already unkeyed the PA. */
            if (state == BSTATE_TX_BURST)
                tx_abort_timeout();
            break;

        case RB_EVT_RX_OK:
            stats.rx_ok++;
            stats.rx_bytes += e.len;
            stats.rssi_sum_half += e.rssi_half_dbm;
            stats.snr_sum_qdb += e.snr_qdb;
            if (!stats.rx_seq_valid)
            {
                stats.rx_first_seq = e.seq;
                stats.rx_seq_valid = true;
            }
            if (e.seq > stats.rx_last_seq)
                stats.rx_last_seq = e.seq;
            break;

        case RB_EVT_RX_CRC:
            stats.rx_crc_err++;
            break;

        default:
            break; /* timeouts / other IRQs re-armed in the ISR */
        }
    }
}

/* ---- Main ----------------------------------------------------------------------- */

int main(void)
{
    bool wdg_reset;

    __disable_irq();

    HAL_Init();
    SystemClock_Config();

    /* Capture the IWDG reset flag BEFORE anything else could clear it, then
     * clear it so the banner only reports resets from THIS firmware. */
    wdg_reset = (__HAL_RCC_GET_FLAG(RCC_FLAG_IWDGRST) != RESET);
    __HAL_RCC_CLEAR_RESET_FLAGS();

    MX_GPIO_Init();
    MX_SPI1_Init();
    MX_USART1_Init();
    console_init();

    __enable_irq();

    console_putln("");
    console_putln("E80 BENCH FW v1.2 (STM32F103C8 + LR2021) - 'HELP' for commands");
    if (wdg_reset)
    {
        console_putln("WDG RESET (IWDG TIMEOUT - PREVIOUS SESSION DIED, CHECK "
                      "CONSOLE LOG ABOVE 'ERR TX-TIMEOUT' / OPERATOR NOTES)");
    }

#if E80_BENCH_BOOT_TX_INHIBITED
    /* Safety default: bring the radio up once with the vendor init sequence
     * (validates SPI + caches chip version for ID?), then put it to sleep.
     * TX stays inhibited until ROLE TX + ARM TX. */
    if (radio_bench_init() == 0)
    {
        radio_bench_sleep();
        console_put("RADIO LR2021 v");
    }
    else
    {
        console_put("RADIO INIT FAIL v");
    }
    console_put_u32(radio_bench_chip_major);
    console_put(".");
    console_put_u32(radio_bench_chip_minor);
    console_putln(" ASLEEP, TX INHIBITED");
#else
#error "E80_BENCH_BOOT_TX_INHIBITED must stay enabled (safety gate from the characterization plan)"
#endif

    bench_stats_reset(&stats);

    /* TX-hang watchdog defense 3 starts LATE — at the first 'ARM TX'
     * (see iwdg_start_once) — NOT here at boot: the IWDG cannot be stopped
     * once started and the ROM bootloader does not feed it, so starting it
     * here would make every 'FLASH' jump reset the MCU mid-write (bricking
     * the app). Until the first ARM TX the board simply stays flashable
     * headlessly; after it, FLASH refuses ('ERR POWER-CYCLE FIRST').
     * Window math in bench_safety.h — 3.000 s nominal, 2.0-4.0 s across
     * the F103 LSI 30-60 kHz spread; every superloop pass kicks it below. */

    while (1)
    {
        if (iwdg_active)
            HAL_IWDG_Refresh(&hiwdg); /* superloop is non-blocking -> healthy */

        char* line = console_getline();
        if (line != NULL)
        {
            bench_cmd_t cmd;
            if (bench_cmd_parse(line, &cmd) == BENCH_CMD_OK)
            {
                handle_cmd(&cmd);
            }
            else
            {
                reply_err(bench_cmd_err_str(cmd.err));
            }
        }
        radio_task();
    }
}
