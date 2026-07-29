/**
 * @file ehash_messages.h
 * @brief E-Hash relay message binary encoding (ADR-025 Phase A)
 *
 * Defines the four L7 message types for Bitcoin stratum relay transport
 * over the balloon mesh network. The balloon acts as a pure transport node
 * — it fragments and forwards these messages without hashing or mining.
 *
 * Wire format: little-endian for all multi-byte integers.
 * See: mesh-stack/protocol/ehash-spec.md for the full specification.
 * See: mesh-stack/protocol/SPEC.md §4 for the L3 fragment layer.
 *
 * ADR-025: docs/adr/025-e-hash-relay-transport-layer.md
 */

#ifndef EHASH_MESSAGES_H
#define EHASH_MESSAGES_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ========================================================================
 *  Message Type Opcodes
 * ======================================================================== */

/**
 * @brief E-hash L7 message type opcodes.
 *
 * Carried as the first byte of the L7 envelope (before the payload).
 * The L7 dispatcher reads this byte to select the appropriate decoder.
 */
typedef enum {
    EHASH_TEMPLATE = 0x10,  /**< Binary block template (downlink, broadcast) */
    EHASH_NONCE    = 0x11,  /**< Binary nonce submission  (uplink, unicast)  */
    EHASH_RESULT   = 0x12,  /**< Share accepted/rejected  (downlink, unicast)*/
    EHASH_CREDIT   = 0x13,  /**< Credit balance update    (downlink, unicast)*/
} ehash_msg_type_t;

/* ========================================================================
 *  Size Constants
 * ======================================================================== */

/** Protocol version byte value (offset 0 of TEMPLATE and NONCE payloads). */
#define EHASH_PROTO_VERSION  0x01

/* --- Fixed-size message sizes (payload only, excludes 1-byte type tag) -- */

#define EHASH_NONCE_SIZE     21u   /**< EHASH_NONCE payload: always 21 bytes */
#define EHASH_RESULT_SIZE    7u    /**< EHASH_RESULT payload: always 7 bytes  */
#define EHASH_CREDIT_SIZE    16u   /**< EHASH_CREDIT payload: always 16 bytes */

/* --- EHASH_TEMPLATE variable-size bounds --- */

/** Fixed fields in a template (all fields except variable-length coinbase/merkle data).
 *  1(ver) + 4(job_id) + 32(prevhash) + 4(btc_ver) + 4(nbits) + 4(ntime)
 *  + 2(cb1_len) + 2(cb2_len) + 1(merkle_count) + 1(clean_jobs) = 55 */
#define EHASH_TEMPLATE_FIXED_SIZE  55u

/** Maximum coinbase1 / coinbase2 length (bytes). Stratum coinbase parts are
 *  typically 20–40 B; 128 B is a generous upper bound. */
#define EHASH_COINBASE_MAX_LEN     128u

/** Maximum merkle branch count. Bitcoin blocks have at most ~16 branches
 *  (log2 of transaction count). */
#define EHASH_MERKLE_BRANCH_MAX    16u

/** Merkle branch hash size (SHA-256 = 32 bytes). */
#define EHASH_MERKLE_HASH_SIZE     32u

/** Maximum EHASH_TEMPLATE payload size:
 *  FIXED + COINBASE_MAX*2 + MERKLE_HASH_SIZE * MERKLE_BRANCH_MAX */
#define EHASH_TEMPLATE_MAX_SIZE    \
    (EHASH_TEMPLATE_FIXED_SIZE + (EHASH_COINBASE_MAX_LEN * 2u) + \
     (EHASH_MERKLE_HASH_SIZE * EHASH_MERKLE_BRANCH_MAX))
    /* = 55 + 256 + 512 = 823 bytes */

/** Maximum L7 envelope size (1-byte type + largest payload). */
#define EHASH_MSG_MAX_SIZE         (1u + EHASH_TEMPLATE_MAX_SIZE)  /* 824 bytes */

/* --- L3 Fragment layer constants (from SPEC.md §4) --- */

#define EHASH_FRAG_HEADER_SIZE     6u    /**< block_id(2) + frag_index(1) + original_count(1) + crc16(2) */
#define EHASH_FRAG_PAYLOAD_MAX     242u  /**< Max payload per fragment (SPEC.md §6.3) */

/* ========================================================================
 *  EHASH_NONCE (0x11) — 21 bytes, fixed
 * ==================================================================== */

/**
 * @brief Binary nonce submission (uplink).
 *
 * Wire layout (21 bytes):
 *   [0]    uint8   version       (0x01)
 *   [1]    uint32  job_id
 *   [5]    uint32  worker_id     (uint16 station ID, zero-padded to 4 B)
 *   [9]    uint32  extranonce2
 *   [13]   uint32  ntime
 *   [17]   uint32  nonce
 */
typedef struct __attribute__((packed)) {
    uint8_t  version;       /**< [0]    Protocol version (0x01) */
    uint32_t job_id;        /**< [1]    Job ID from TEMPLATE */
    uint32_t worker_id;     /**< [5]    Station ID (uint16, zero-padded) */
    uint32_t extranonce2;   /**< [9]    Ground-assigned extranonce2 */
    uint32_t ntime;         /**< [13]   nTime used by miner */
    uint32_t nonce;         /**< [17]   Nonce found by ASIC */
} ehash_nonce_t;

_Static_assert(sizeof(ehash_nonce_t) == EHASH_NONCE_SIZE,
               "ehash_nonce_t must be 21 bytes");

/* ========================================================================
 *  EHASH_RESULT (0x12) — 7 bytes, fixed
 * ==================================================================== */

/**
 * @brief Share accepted/rejected response (downlink).
 *
 * Wire layout (7 bytes):
 *   [0]    uint32  job_id
 *   [4]    uint8   accepted     (1 = accepted, 0 = rejected)
 *   [5]    uint16  error_code   (0 = no error; stratum V1 codes)
 */
typedef struct __attribute__((packed)) {
    uint32_t job_id;        /**< [0]  Job ID this result refers to */
    uint8_t  accepted;      /**< [4]  1 = share accepted, 0 = rejected */
    uint16_t error_code;    /**< [5]  Stratum error code (0 = no error) */
} ehash_result_t;

_Static_assert(sizeof(ehash_result_t) == EHASH_RESULT_SIZE,
               "ehash_result_t must be 7 bytes");

/* ========================================================================
 *  EHASH_CREDIT (0x13) — 16 bytes, fixed
 * ==================================================================== */

/**
 * @brief Credit balance update (downlink).
 *
 * Wire layout (16 bytes):
 *   [0]    uint32  station_id
 *   [4]    uint64  balance            (e-hash tokens in satoshis)
 *   [12]   uint32  block_reward_rate  (satoshis per accepted share)
 */
typedef struct __attribute__((packed)) {
    uint32_t station_id;          /**< [0]  Ground station ID */
    uint64_t balance;             /**< [4]  E-hash balance (satoshis) */
    uint32_t block_reward_rate;   /**< [12] Reward per accepted share (sats) */
} ehash_credit_t;

_Static_assert(sizeof(ehash_credit_t) == EHASH_CREDIT_SIZE,
               "ehash_credit_t must be 16 bytes");

/* ========================================================================
 *  EHASH_TEMPLATE (0x10) — variable length, 55–823 bytes
 * ==================================================================== */

/**
 * @brief Fixed header of a template (49 bytes).
 *
 * Contains all fields up to (but not including) coinbase1_len.
 * Variable-length data (coinbase1, coinbase2, merkle branches) follows
 * after this header + the coinbase1_len field in the wire format.
 *
 * Wire layout of fixed header (49 bytes):
 *   [0]    uint8      version       (0x01)
 *   [1]    uint32     job_id
 *   [5]    uint8[32]  prevhash
 *   [37]   uint32     btc_version
 *   [41]   uint32     nbits
 *   [45]   uint32     ntime
 */
typedef struct __attribute__((packed)) {
    uint8_t  version;       /**< [0]    Protocol version (0x01) */
    uint32_t job_id;        /**< [1]    Job ID from e-hash proxy */
    uint8_t  prevhash[32];  /**< [5]    Previous block hash (raw bytes) */
    uint32_t btc_version;   /**< [37]   Bitcoin block version field */
    uint32_t nbits;         /**< [41]   Difficulty target (compact) */
    uint32_t ntime;         /**< [45]   BTC network time (0 = current) */
} ehash_template_hdr_t;

_Static_assert(sizeof(ehash_template_hdr_t) == 49u,
               "ehash_template_hdr_t must be 49 bytes");

/**
 * @brief Decoded template — higher-level representation with pointers to
 *        variable-length fields.
 *
 * Used by encode/decode functions. The pointed-to data is NOT copied —
 * callers must keep the source buffer alive for the lifetime of use.
 */
typedef struct {
    uint32_t       job_id;              /**< Job ID from proxy */
    const uint8_t *prevhash;            /**< 32 bytes */
    uint32_t       btc_version;         /**< Bitcoin block version */
    uint32_t       nbits;               /**< Difficulty target */
    uint32_t       ntime;               /**< Network time (0 = current) */
    const uint8_t *coinbase1;           /**< coinbase1_len bytes */
    uint16_t       coinbase1_len;       /**< Length of coinbase1 */
    const uint8_t *coinbase2;           /**< coinbase2_len bytes */
    uint16_t       coinbase2_len;       /**< Length of coinbase2 */
    uint8_t        merkle_branch_count; /**< Number of merkle hashes (K) */
    const uint8_t *merkle_branches;     /**< 32 * merkle_branch_count bytes */
    uint8_t        clean_jobs;          /**< 1 = flush old jobs */
} ehash_template_t;

/* ========================================================================
 *  Encode / Decode Function Prototypes
 * ==================================================================== */

/*
 * Convention:
 *   - Encode functions write into buf, return bytes written (>0) or <0 on error.
 *   - Decode functions parse from buf, return 0 on success or <0 on error.
 *   - Error codes: -1 = buffer too small, -2 = bad version, -3 = malformed.
 */

/* --- EHASH_NONCE --- */

/**
 * @brief Encode a nonce submission into a wire buffer.
 * @param nonce  Populated nonce struct (version field is forced to 0x01).
 * @param buf    Output buffer (must be >= EHASH_NONCE_SIZE bytes).
 * @param bufsize Size of buf.
 * @return Bytes written (21) on success, <0 on error.
 */
int ehash_nonce_encode(const ehash_nonce_t *nonce, uint8_t *buf, size_t bufsize);

/**
 * @brief Decode a nonce submission from a wire buffer.
 * @param buf    Input buffer.
 * @param len    Length of input.
 * @param nonce  Output struct (filled in).
 * @return 0 on success, <0 on error.
 */
int ehash_nonce_decode(const uint8_t *buf, size_t len, ehash_nonce_t *nonce);

/* --- EHASH_RESULT --- */

/**
 * @brief Encode a share result into a wire buffer.
 * @param result  Populated result struct.
 * @param buf     Output buffer (must be >= EHASH_RESULT_SIZE bytes).
 * @param bufsize Size of buf.
 * @return Bytes written (7) on success, <0 on error.
 */
int ehash_result_encode(const ehash_result_t *result, uint8_t *buf, size_t bufsize);

/**
 * @brief Decode a share result from a wire buffer.
 * @param buf     Input buffer.
 * @param len     Length of input.
 * @param result  Output struct.
 * @return 0 on success, <0 on error.
 */
int ehash_result_decode(const uint8_t *buf, size_t len, ehash_result_t *result);

/* --- EHASH_CREDIT --- */

/**
 * @brief Encode a credit balance update into a wire buffer.
 * @param credit  Populated credit struct.
 * @param buf     Output buffer (must be >= EHASH_CREDIT_SIZE bytes).
 * @param bufsize Size of buf.
 * @return Bytes written (16) on success, <0 on error.
 */
int ehash_credit_encode(const ehash_credit_t *credit, uint8_t *buf, size_t bufsize);

/**
 * @brief Decode a credit balance update from a wire buffer.
 * @param buf     Input buffer.
 * @param len     Length of input.
 * @param credit  Output struct.
 * @return 0 on success, <0 on error.
 */
int ehash_credit_decode(const uint8_t *buf, size_t len, ehash_credit_t *credit);

/* --- EHASH_TEMPLATE --- */

/**
 * @brief Encode a template into a wire buffer.
 * @param tmpl    Populated template struct (pointers must be valid).
 * @param buf     Output buffer (must be >= EHASH_TEMPLATE_FIXED_SIZE +
 *                coinbase1_len + coinbase2_len +
 *                32*merkle_branch_count bytes).
 * @param bufsize Size of buf.
 * @return Bytes written (>0) on success, <0 on error.
 */
int ehash_template_encode(const ehash_template_t *tmpl, uint8_t *buf, size_t bufsize);

/**
 * @brief Decode a template from a wire buffer.
 *
 * The decoded struct's pointer fields (prevhash, coinbase1, coinbase2,
 * merkle_branches) point directly into buf — no internal allocation.
 * The caller must not free buf while the struct is in use.
 *
 * @param buf     Input buffer.
 * @param len     Length of input.
 * @param tmpl    Output struct (pointers reference into buf).
 * @return 0 on success, <0 on error.
 */
int ehash_template_decode(const uint8_t *buf, size_t len, ehash_template_t *tmpl);

/**
 * @brief Compute the wire size of a template without encoding it.
 * @param tmpl    Template struct.
 * @return Total wire bytes (>= EHASH_TEMPLATE_FIXED_SIZE), or <0 on error.
 */
int ehash_template_size(const ehash_template_t *tmpl);

/* ========================================================================
 *  L7 Envelope Helpers
 * ==================================================================== */

/**
 * @brief Get the message type from an L7 envelope buffer.
 * @param buf  Buffer containing at least 1 byte (the type tag).
 * @param len  Buffer length.
 * @return Message type (0x10–0x13), or <0 if invalid/unrecognized.
 */
int ehash_msg_get_type(const uint8_t *buf, size_t len);

#ifdef __cplusplus
}
#endif

#endif /* EHASH_MESSAGES_H */
