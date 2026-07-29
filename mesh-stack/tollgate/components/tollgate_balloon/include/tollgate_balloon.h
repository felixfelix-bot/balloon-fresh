#ifndef TOLLGATE_BALLOON_H
#define TOLLGATE_BALLOON_H

#include "tollgate_platform.h"
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Balloon TollGate — mesh transport adapter
 *
 * Wraps tollgate_core for FIPS mesh UDP transport (ADR-002).
 * Replaces WiFi captive portal with UDP payment message handler.
 *
 * Layer: L7 over FIPS mesh (UDP port 2121)
 * Payment flow:
 *   1. Ground station sends PAY msg (Cashu token) via UDP to balloon
 *   2. Balloon validates/swaps token via nucula wallet
 *   3. Balloon sends ACK with session info (expiry, quota)
 *   4. Mesh firewall grants relay access for session duration
 */

#define TOLLGATE_BALLOON_PORT       2121
#define TOLLGATE_MAX_TOKEN_LEN      2048
#define TOLLGATE_MAX_NODE_ID_LEN    33  /* hex npub (32 bytes + null) */

typedef enum {
    TG_MSG_PAY      = 0x01,  /* Client → Balloon: Cashu token payment */
    TG_MSG_ACK      = 0x02,  /* Balloon → Client: Payment accepted + session info */
    TG_MSG_NACK     = 0x03,  /* Balloon → Client: Payment rejected + reason */
    TG_MSG_STATUS   = 0x04,  /* Client → Balloon: Request status/pricing */
    TG_MSG_INFO     = 0x05,  /* Balloon → Client: Status response (price, mints, session) */
    TG_MSG_REVOKE   = 0x06,  /* Balloon → Client: Session revoked */
} tollgate_msg_type_t;

typedef struct {
    uint8_t  version;         /* Protocol version (1) */
    uint8_t  type;            /* tollgate_msg_type_t */
    uint16_t seq;             /* Sequence number for dedup */
    uint16_t payload_len;     /* Length of payload following header */
    uint16_t reserved;        /* Alignment / future use */
} __attribute__((packed)) tollgate_msg_hdr_t;

#define TOLLGATE_PROTO_VERSION  1

/*
 * Initialize balloon TollGate.
 * Sets up UDP listener on TOLLGATE_BALLOON_PORT.
 * Installs mesh-platform adapter into tollgate_core.
 *
 * @param nsec_hex   Balloon Nostr private key (hex, 64 chars)
 * @param mint_url   Default Cashu mint URL
 * @param price_sats Price per unit (sats)
 * @param step_ms    Time unit per payment (ms)
 * @return ESP_OK on success
 */
esp_err_t tollgate_balloon_init(const char *nsec_hex,
                                 const char *mint_url,
                                 uint16_t price_sats,
                                 int32_t step_ms);

/*
 * Process incoming UDP packet from mesh.
 * Called by FIPS mesh transport when packet arrives on port 2121.
 *
 * @param src_node_id  Sender mesh node ID (hex, null-terminated)
 * @param data         Raw UDP payload
 * @param len          Payload length
 * @return ESP_OK on success
 */
esp_err_t tollgate_balloon_on_packet(const char *src_node_id,
                                      const uint8_t *data,
                                      uint16_t len);

/*
 * Periodic tick — call from main loop (1Hz).
 * Expires sessions, checks mint health, sends beacons.
 */
void tollgate_balloon_tick(void);

/*
 * Get current status as JSON (for debug/Nostr reporting).
 * Caller must free() the returned string.
 */
char *tollgate_balloon_get_status(void);

/*
 * Shutdown — revoke all sessions, close UDP listener.
 */
void tollgate_balloon_stop(void);

#ifdef __cplusplus
}
#endif

#endif
