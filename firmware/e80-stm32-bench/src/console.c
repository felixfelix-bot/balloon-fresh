/**
 * @file    console.c
 * @brief   USART1 console for the E80 bench firmware.
 */

#include "console.h"
#include "bench_cmd.h"
#include "buffer.h"

#include <stddef.h>

extern UART_HandleTypeDef huart1;

static volatile char    rx_ring[CONSOLE_RX_RING_SIZE];
static volatile uint8_t rx_head = 0; /* ISR writes */
static volatile uint8_t rx_tail = 0; /* main reads  */

static char     line_buf[CONSOLE_LINE_MAX];
static uint16_t line_len = 0;
static volatile uint8_t line_ready = 0;

/* TX staging (console_put* append here, console_flush sends) */
static char     tx_buf[160];
static uint16_t tx_len = 0;

void console_init(void)
{
    /* RX interrupt enable (UART already initialized by bench.c). */
    __HAL_UART_CLEAR_FLAG(&huart1, UART_FLAG_RXNE);
    __HAL_UART_ENABLE_IT(&huart1, UART_IT_RXNE);
}

void console_uart_irq(void)
{
    /* Clear ORE first — if overrun occurred, RXNE may be stale and
     * the USART won't receive new bytes until ORE is cleared. */
    if (__HAL_UART_GET_FLAG(&huart1, UART_FLAG_ORE))
        __HAL_UART_CLEAR_OREFLAG(&huart1);
    while (__HAL_UART_GET_FLAG(&huart1, UART_FLAG_RXNE))
    {
        char c = (char)(huart1.Instance->DR & 0xFF);
        uint8_t next = (uint8_t)((rx_head + 1) % CONSOLE_RX_RING_SIZE);
        if (next != rx_tail) /* drop on overflow */
        {
            rx_ring[rx_head] = c;
            rx_head = next;
        }
        if (__HAL_UART_GET_FLAG(&huart1, UART_FLAG_ORE))
            __HAL_UART_CLEAR_OREFLAG(&huart1);
    }
}

char* console_getline(void)
{
    if (line_ready)
        return NULL; /* caller must consume previous line first (it won't) */

    /* Polling fallback: if the USART1 RXNE interrupt didn't fire (known
     * STM32F1 NVIC issue after SWD reset), drain pending bytes here.
     * Also clear ORE (Overrun Error) — if multiple bytes arrived while the
     * CPU was halted by SWD, ORE sets and blocks all further RX.
     * CRITICAL: disable the USART1 NVIC IRQ during the drain to prevent a
     * race where the ISR reads DR between our RXNE check and DR read,
     * producing a stale duplicate byte that corrupts binary payloads. */
    if (__HAL_UART_GET_FLAG(&huart1, UART_FLAG_ORE))
    {
        __HAL_UART_CLEAR_OREFLAG(&huart1);
    }
    HAL_NVIC_DisableIRQ(USART1_IRQn);
    while (__HAL_UART_GET_FLAG(&huart1, UART_FLAG_RXNE))
    {
        char c = (char)(huart1.Instance->DR & 0xFF);
        uint8_t next = (uint8_t)((rx_head + 1) % CONSOLE_RX_RING_SIZE);
        if (next != rx_tail)
        {
            rx_ring[rx_head] = c;
            rx_head = next;
        }
        if (__HAL_UART_GET_FLAG(&huart1, UART_FLAG_ORE))
            __HAL_UART_CLEAR_OREFLAG(&huart1);
    }
    HAL_NVIC_EnableIRQ(USART1_IRQn);

    while (rx_tail != rx_head)
    {
        char c = rx_ring[rx_tail];
        rx_tail = (uint8_t)((rx_tail + 1) % CONSOLE_RX_RING_SIZE);

        if (c == '\r' || c == '\n')
        {
            if (line_len == 0)
                continue; /* skip empty lines / lone CR after LF */
            line_buf[line_len] = '\0';
            line_len = 0;
            line_ready = 1;
            return line_buf;
        }
        if (line_len < CONSOLE_LINE_MAX - 1)
        {
            line_buf[line_len++] = c;
        }
        /* else: overlong line silently truncated */
    }
    return NULL;
}

static void line_consumed(void)
{
    line_ready = 0;
}

void console_put(const char* s)
{
    tx_len = 0;
    while (*s != '\0' && tx_len < sizeof(tx_buf) - 1)
        tx_buf[tx_len++] = *s++;
    if (tx_len)
        HAL_UART_Transmit(&huart1, (uint8_t*)tx_buf, tx_len, 100);
    tx_len = 0;
    line_consumed(); /* a reply marks the line consumed */
}

void console_putln(const char* s)
{
    console_put(s);
    console_put("\r\n");
}

void console_put_u32(uint32_t v)
{
    char tmp[11];
    int i = 0;
    if (v == 0)
    {
        HAL_UART_Transmit(&huart1, (const uint8_t*)"0", 1, 100);
        return;
    }
    while (v > 0 && i < 10)
    {
        tmp[i++] = (char)('0' + (v % 10));
        v /= 10;
    }
    while (i > 0)
        HAL_UART_Transmit(&huart1, (const uint8_t*)&tmp[--i], 1, 100);
}

void console_put_i32(int32_t v)
{
    if (v < 0)
    {
        HAL_UART_Transmit(&huart1, (const uint8_t*)"-", 1, 100);
        console_put_u32((uint32_t)(-v));
    }
    else
    {
        console_put_u32((uint32_t)v);
    }
}

void console_put_u32_hex8(uint32_t v)
{
    static const char hex[] = "0123456789ABCDEF";
    char tmp[8];
    for (int i = 0; i < 8; i++)
        tmp[i] = hex[(v >> ((7 - i) * 4)) & 0xF];
    HAL_UART_Transmit(&huart1, (const uint8_t*)tmp, 8, 100);
}

void console_put_u16_hex4(uint16_t v)
{
    static const char hex[] = "0123456789ABCDEF";
    char tmp[4];
    for (int i = 0; i < 4; i++)
        tmp[i] = hex[(v >> ((3 - i) * 4)) & 0xF];
    HAL_UART_Transmit(&huart1, (const uint8_t*)tmp, 4, 100);
}

void console_put_dec1(int32_t value_x10)
{
    if (value_x10 < 0)
    {
        HAL_UART_Transmit(&huart1, (const uint8_t*)"-", 1, 100);
        value_x10 = -value_x10;
    }
    console_put_u32((uint32_t)(value_x10 / 10));
    HAL_UART_Transmit(&huart1, (const uint8_t*)".", 1, 100);
    console_put_u32((uint32_t)(value_x10 % 10));
}

/* ---- Binary payload receive phase (BUF LOAD; tx-buffer-spec) ------------------
 * Length-delimited, no escaping, silent between ack and final reply:
 *   'OK BINARY <n>\r\n'  ack (line mode suspended from here)
 *   <n raw payload bytes>
 *   'OK BUF <n> 1\r\n'   CRC matched, buffer committed
 *   'ERR CRC\r\n'        mismatch (buffer.c clears len, rule 5)
 *   'ERR TIMEOUT\r\n'    no payload byte for >=1.0 s (rule 3: abort keeps a
 *                        previously committed buffer; partial discarded)
 * Off-by-2 hazard: getline already ate the terminator it saw ('\r' on CRLF,
 * '\n' on LF); start() swallows at most ONE pending CR/LF tail so CRLF hosts
 * don't shift the payload, while payload bytes are never consumed early. */

static bool                bin_active = false;
static uint16_t            bin_n;          /* payload length of this load  */
static uint16_t            bin_remain;     /* payload bytes still expected */
static uint16_t            bin_expected_crc;
static uint32_t            bin_last_ms;    /* start / last payload byte    */
static console_bin_state_t bin_state = CONSOLE_BIN_IDLE;

void console_binary_start(uint16_t n, uint16_t expected_crc, uint32_t now_ms)
{
    /* Ack first: it goes on the wire before any payload byte is consumed. */
    console_put("OK BINARY ");
    console_put_u32(n);
    console_putln("");

    /* Swallow the line terminator's pending tail (the '\n' after a '\r'
     * getline already consumed) WITHOUT counting it against the n payload
     * bytes. Exactly one byte: the payload itself may start with CR/LF
     * (no escaping in the framing) and must not be eaten.
     *
     * CRITICAL: drain the UART RXNE register into the ring BEFORE checking
     * for the pending '\n'.  If the host sent CRLF as a single burst, the
     * '\r' was consumed by getline but the '\n' may still be in the UART DR
     * register (ISR hasn't fired yet, or getline's own RXNE poll exited
     * after reading '\r' and before '\n' arrived).  Without this drain, the
     * '\n' would be missed here and later consumed as the first payload
     * byte — a 1-byte shift that corrupts every CRC. */
    HAL_NVIC_DisableIRQ(USART1_IRQn);
    if (__HAL_UART_GET_FLAG(&huart1, UART_FLAG_ORE))
        __HAL_UART_CLEAR_OREFLAG(&huart1);
    while (__HAL_UART_GET_FLAG(&huart1, UART_FLAG_RXNE))
    {
        char c = (char)(huart1.Instance->DR & 0xFF);
        uint8_t next = (uint8_t)((rx_head + 1) % CONSOLE_RX_RING_SIZE);
        if (next != rx_tail)
        {
            rx_ring[rx_head] = c;
            rx_head = next;
        }
        if (__HAL_UART_GET_FLAG(&huart1, UART_FLAG_ORE))
            __HAL_UART_CLEAR_OREFLAG(&huart1);
    }
    HAL_NVIC_EnableIRQ(USART1_IRQn);

    if (rx_tail != rx_head &&
        (rx_ring[rx_tail] == '\r' || rx_ring[rx_tail] == '\n'))
    {
        rx_tail = (uint8_t)((rx_tail + 1) % CONSOLE_RX_RING_SIZE);
    }

    if (!buf_load_begin(n))
    {
        /* Unreachable via the parser (n range-checked at parse time);
         * defensive: stay in line mode, no binary phase. */
        bin_active = false;
        bin_state  = CONSOLE_BIN_IDLE;
        return;
    }

    bin_active      = true;
    bin_n           = n;
    bin_remain      = n;
    bin_expected_crc = expected_crc;
    bin_last_ms     = now_ms;
    bin_state       = CONSOLE_BIN_WAITING;
}

bool console_binary_active(void)
{
    return bin_active;
}

console_bin_state_t console_binary_poll(uint32_t now_ms)
{
    if (!bin_active)
        return CONSOLE_BIN_IDLE;

    /* Drain ISR-pending bytes into the ring first — same fallback path as
     * console_getline, so the binary phase works with the IRQ off (host
     * tests inject here) and with it on. Payload order is preserved: ring
     * bytes are strictly older than freshly flagged RXNE bytes.
     * CRITICAL: disable the USART1 NVIC IRQ during the drain to prevent a
     * race where the ISR reads DR between our RXNE check and DR read,
     * producing a stale duplicate byte that corrupts binary payloads. */
    HAL_NVIC_DisableIRQ(USART1_IRQn);
    while (__HAL_UART_GET_FLAG(&huart1, UART_FLAG_RXNE))
    {
        char c = (char)(huart1.Instance->DR & 0xFF);
        uint8_t next = (uint8_t)((rx_head + 1) % CONSOLE_RX_RING_SIZE);
        if (next != rx_tail)
        {
            rx_ring[rx_head] = c;
            rx_head = next;
        }
        else
        {
            buf_note_drop(); /* ring full; end-of-load CRC is the real detector */
        }
        if (__HAL_UART_GET_FLAG(&huart1, UART_FLAG_ORE))
            __HAL_UART_CLEAR_OREFLAG(&huart1);
    }
    HAL_NVIC_EnableIRQ(USART1_IRQn);

    /* Consume payload bytes from the ring; each byte restarts the idle clock. */
    while (bin_remain > 0 && rx_tail != rx_head)
    {
        char c = rx_ring[rx_tail];
        rx_tail = (uint8_t)((rx_tail + 1) % CONSOLE_RX_RING_SIZE);
        buf_load_byte((uint8_t)c);
        bin_remain--;
        bin_last_ms = now_ms;
    }

    if (bin_remain == 0)
    {
        /* Full payload received: nothing more on the wire until the verdict. */
        bin_active = false;
        if (buf_load_commit(bin_expected_crc))
        {
            console_put("OK BUF ");
            console_put_u32(bin_n);
            console_put(" 1");
            console_putln("");
            bin_state = CONSOLE_BIN_DONE;
        }
        else
        {
            console_putln("ERR CRC");
            bin_state = CONSOLE_BIN_CRC;
        }
        return bin_state;
    }

    /* Idle timeout (spec rule 3): no payload byte for 1.0 s. The caller's
     * superloop keeps feeding the IWDG while polling (rule 2). */
    if ((uint32_t)(now_ms - bin_last_ms) >= BUF_IDLE_TIMEOUT_MS)
    {
        buf_load_abort();
        bin_active = false;
        console_putln("ERR TIMEOUT");
        bin_state = CONSOLE_BIN_TIMEOUT;
        return bin_state;
    }

    bin_state = CONSOLE_BIN_WAITING;
    return CONSOLE_BIN_WAITING;
}

console_bin_state_t console_binary_state(void)
{
    return bin_state;
}
