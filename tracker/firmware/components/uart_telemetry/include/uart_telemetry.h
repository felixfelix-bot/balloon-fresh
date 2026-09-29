/**
 * @file    uart_telemetry.h
 * @brief   UART telemetry protocol between the ESP32-C3 tracker and the RP2040 radio.
 *
 * Wire format (see docs/uart-telemetry-protocol.md for the normative spec):
 *
 *   +--------+--------+-----+------+-----+ - - - - - - +--------+--------+
 *   | 0xAA   | 0x55   | ver | type | len |  seq | payload | crc_lo | crc_hi |
 *   +--------+--------+-----+------+-----+------+---------+--------+--------+
 *      SOF (2)          header (4)              len      CRC-16/CCITT-FALSE
 *
 * All multi-byte integer fields are LITTLE-ENDIAN on the wire and are written
 * and read byte-wise through the helpers below.  The structs are deliberately
 * NOT used as an overlay: the RP2040 is a Cortex-M0+ where casting a packed
 * struct onto an unaligned receive buffer is undefined behaviour.  Encode and
 * decode go through explicit byte moves.
 *
 * CRC: CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF, no reflection, no final
 * xor) — the same algorithm already used by components/telemetry, components/frag
 * and firmware/rp2040/src/bench in this repository, so a single golden vector set
 * covers every path.
 *
 * Portable: no ESP-IDF / Pico-SDK / STM32 headers.  Compiles on host (C11) and
 * on both targets.
 */

#ifndef UART_TELEMETRY_H
#define UART_TELEMETRY_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ── Link parameters ─────────────────────────────────────────────────────── */

#define UART_TLM_BAUD            115200u   /* 8N1, matches verified bridge wiring */
#define UART_TLM_SOF0            0xAAu
#define UART_TLM_SOF1            0x55u
#define UART_TLM_VERSION         1u

/* Header = SOF0 SOF1 VER TYPE LEN SEQ */
#define UART_TLM_HDR_SIZE        6u
#define UART_TLM_CRC_SIZE        2u
#define UART_TLM_MAX_PAYLOAD     64u
#define UART_TLM_MAX_FRAME       (UART_TLM_HDR_SIZE + UART_TLM_MAX_PAYLOAD + UART_TLM_CRC_SIZE)

/* Frame types */
#define UART_TLM_TYPE_TELEMETRY  0x01u  /* ESP32-C3 -> RP2040 (outbound sensor state) */
#define UART_TLM_TYPE_MESH_STATUS 0x02u /* RP2040  -> ESP32-C3 (radio/mesh back-channel) */

/* Payload sizes are fixed per type.  APPEND-ONLY within a version: new fields
 * go on the end and bump UART_TLM_VERSION, existing offsets never move. */
#define UART_TLM_TELEMETRY_LEN   32u
#define UART_TLM_MESH_STATUS_LEN 20u

/* ── TELEMETRY flags (byte 30) ───────────────────────────────────────────── */

#define UART_TLM_F_GPS_VALID     (1u << 0)
#define UART_TLM_F_GPS_FIX_3D    (1u << 1)
#define UART_TLM_F_SOLAR_ACTIVE  (1u << 2)
#define UART_TLM_F_LOW_BATTERY   (1u << 3)
#define UART_TLM_F_MESH_JOINED   (1u << 4)
#define UART_TLM_F_BROWNOUT      (1u << 5)

/* tx_mode (byte 31): the modulation the tracker wants the radio to use. */
#define UART_TLM_TXMODE_LORA     0u
#define UART_TLM_TXMODE_FLRC     1u
#define UART_TLM_TXMODE_IDLE     2u

/* ── MESH_STATUS flags (byte 11) ─────────────────────────────────────────── */

#define UART_TLM_M_RADIO_READY   (1u << 0)
#define UART_TLM_M_MESH_JOINED   (1u << 1)
#define UART_TLM_M_TX_GRANTED    (1u << 2)
#define UART_TLM_M_PA_ENABLED    (1u << 3)
#define UART_TLM_M_RX_OVERRUN    (1u << 4)

/* Decoder error codes (negative, errno-ish) */
#define UART_TLM_OK                 0
#define UART_TLM_ERR_CRC           -1   /* frame boundary found, CRC mismatch   */
#define UART_TLM_ERR_LEN           -2   /* len 0 or > UART_TLM_MAX_PAYLOAD      */
#define UART_TLM_ERR_TYPE          -3   /* unknown frame type                   */
#define UART_TLM_ERR_PAYLOAD_SIZE  -4   /* len != the fixed size for that type  */
#define UART_TLM_ERR_OVERFLOW      -5   /* caller buffer too small              */
#define UART_TLM_ERR_ARG           -6   /* NULL / bad argument                  */

/* ── Payload structs (decoded form, native endian) ───────────────────────── */

/** ESP32-C3 -> RP2040 sensor snapshot (32 bytes on the wire). */
typedef struct {
    uint32_t seq;            /* off  0  monotonic telemetry counter          */
    uint32_t uptime_ms;      /* off  4  ms since C3 boot                     */
    int32_t  lat_deg1e7;     /* off  8  WGS84 latitude  x 1e7                */
    int32_t  lon_deg1e7;     /* off 12  WGS84 longitude x 1e7                */
    int32_t  alt_mm;         /* off 16  altitude above MSL, millimetres      */
    uint16_t battery_mv;     /* off 20  battery rail, millivolts             */
    uint16_t solar_mv;       /* off 22  solar rail, millivolts               */
    int16_t  temp_cdeg;      /* off 24  board temperature, centi-degrees C   */
    uint16_t pressure_hpa10; /* off 26  barometric pressure, hPa x 10        */
    uint8_t  sats;           /* off 28  satellites used in the fix           */
    uint8_t  hdop_x10;       /* off 29  HDOP x 10 (0 = unknown)              */
    uint8_t  flags;          /* off 30  UART_TLM_F_*                         */
    uint8_t  tx_mode;        /* off 31  UART_TLM_TXMODE_*                    */
} uart_tlm_telemetry_t;

/** RP2040 -> ESP32-C3 radio/mesh back-channel (20 bytes on the wire). */
typedef struct {
    uint32_t seq;            /* off  0  RP2040-side counter                  */
    uint32_t uptime_ms;      /* off  4  ms since RP2040 boot                 */
    int16_t  rssi_half_dbm;  /* off  8  RSSI in 0.5 dB steps (dBm x 2)       */
    int8_t   snr_qdb;        /* off 10  SNR in 0.25 dB steps (dB x 4)        */
    uint8_t  flags;          /* off 11  UART_TLM_M_*                         */
    uint16_t pkt_rx;         /* off 12  packets received since boot          */
    uint16_t pkt_tx;         /* off 14  packets transmitted since boot       */
    uint16_t crc_err;        /* off 16  radio CRC failures since boot        */
    uint8_t  state;          /* off 18  radio state machine code             */
    uint8_t  chan;           /* off 19  active channel / config index        */
} uart_tlm_mesh_status_t;

/* ── Streaming decoder state ─────────────────────────────────────────────── */

/**
 * Byte-fed frame decoder.  Feed bytes one at a time (or in blocks) from the
 * UART ISR / ring buffer; it re-synchronises automatically after noise by
 * re-scanning for the SOF pattern, so a corrupted frame never wedges the link.
 *
 * The caller supplies the output buffer for the payload; it is only written on
 * a CRC-valid frame, so a partially-decoded bad frame never clobbers live data.
 */
typedef struct {
    uint8_t  buf[UART_TLM_MAX_FRAME]; /* accumulates the in-flight frame      */
    uint16_t have;                    /* bytes currently in buf               */
    uint16_t expect;                  /* total frame size once len is known   */
    /* Link statistics (monotonic since init) */
    uint32_t frames_ok;
    uint32_t crc_errors;
    uint32_t len_errors;
    uint32_t resyncs;
    uint32_t seq_drops;               /* gap detected in the frame-level seq  */
    uint8_t  last_seq;                /* last accepted frame seq              */
    bool     seq_valid;               /* false until the first good frame     */
} uart_tlm_decoder_t;

/* ── CRC ─────────────────────────────────────────────────────────────────── */

/** CRC-16/CCITT-FALSE.  "123456789" -> 0x29B1 (see the golden vectors). */
uint16_t uart_tlm_crc16(const uint8_t *data, uint32_t len);

/* ── Encoding ────────────────────────────────────────────────────────────── */

/**
 * Encode one frame into out.
 *
 * @param out       output buffer, caller-owned
 * @param out_size  bytes available at out
 * @param type      UART_TLM_TYPE_*
 * @param seq       frame-level sequence byte (caller's link counter)
 * @param payload   payload bytes (fixed size for the type)
 * @param len       payload length; must equal the type's fixed size
 * @return total frame bytes written, or a UART_TLM_ERR_* negative code.
 */
int uart_tlm_encode(uint8_t *out, uint32_t out_size, uint8_t type, uint8_t seq,
                    const uint8_t *payload, uint8_t len);

/** Encode a TELEMETRY frame straight from the decoded struct. */
int uart_tlm_encode_telemetry(uint8_t *out, uint32_t out_size, uint8_t seq,
                              const uart_tlm_telemetry_t *t);

/** Encode a MESH_STATUS frame straight from the decoded struct. */
int uart_tlm_encode_mesh_status(uint8_t *out, uint32_t out_size, uint8_t seq,
                                const uart_tlm_mesh_status_t *m);

/* ── Payload (de)serialisation ───────────────────────────────────────────── */

void uart_tlm_telemetry_to_bytes(const uart_tlm_telemetry_t *t, uint8_t payload[UART_TLM_TELEMETRY_LEN]);
bool uart_tlm_bytes_to_telemetry(const uint8_t payload[UART_TLM_TELEMETRY_LEN], uart_tlm_telemetry_t *t);

void uart_tlm_mesh_status_to_bytes(const uart_tlm_mesh_status_t *m, uint8_t payload[UART_TLM_MESH_STATUS_LEN]);
bool uart_tlm_bytes_to_mesh_status(const uint8_t payload[UART_TLM_MESH_STATUS_LEN], uart_tlm_mesh_status_t *m);

/* ── Validation ──────────────────────────────────────────────────────────── */

/** Range/sanity check on a decoded telemetry payload.  Returns true if plausible. */
bool uart_tlm_telemetry_valid(const uart_tlm_telemetry_t *t);

/** Range/sanity check on a decoded mesh-status payload. */
bool uart_tlm_mesh_status_valid(const uart_tlm_mesh_status_t *m);

/** Fixed payload length for a frame type, or 0 if the type is unknown. */
uint8_t uart_tlm_payload_len(uint8_t type);

/* ── Decoding ────────────────────────────────────────────────────────────── */

void uart_tlm_decoder_init(uart_tlm_decoder_t *d);

/**
 * Feed one byte.
 *
 * @return  UART_TLM_OK when a complete valid frame was produced (payload_out /
 *          type_out / seq_out are filled), otherwise UART_TLM_OK when the byte
 *          was merely consumed as part of an in-flight frame, or a
 *          UART_TLM_ERR_* code when a frame was rejected (the decoder is left
 *          re-synchronising).
 */
int uart_tlm_decoder_feed(uart_tlm_decoder_t *d, uint8_t byte,
                          uint8_t *type_out, uint8_t *seq_out,
                          uint8_t *payload_out, uint8_t *payload_len_out);

/** Feed a block; counts how many valid frames were produced. */
uint32_t uart_tlm_decoder_feed_block(uart_tlm_decoder_t *d,
                                     const uint8_t *data, uint32_t len,
                                     uint8_t *type_out, uint8_t *seq_out,
                                     uint8_t *payload_out, uint8_t *payload_len_out);

/** Whole-buffer convenience decode (tests / host tools).  Frame must start at
 *  data[0].  Returns frame size consumed, or a UART_TLM_ERR_* code. */
int uart_tlm_decode_frame(const uint8_t *data, uint32_t len,
                          uint8_t *type_out, uint8_t *seq_out,
                          uint8_t *payload_out, uint8_t *payload_len_out);

#ifdef __cplusplus
}
#endif

#endif /* UART_TELEMETRY_H */
