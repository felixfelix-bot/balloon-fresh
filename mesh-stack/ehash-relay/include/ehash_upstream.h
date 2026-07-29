/**
 * @file ehash_upstream.h
 * @brief Mock upstream connection (simulates e-hash proxy).
 *
 * For Phase C testing. Generates fake mining.notify every 60s.
 * Real stratum connection will replace this in a later phase.
 */

#ifndef EHASH_UPSTREAM_H
#define EHASH_UPSTREAM_H

#include <stdint.h>
#include <stdbool.h>
#include "ehash_messages.h"

#ifdef __cplusplus
extern "C" {
#endif

/** Mock upstream state. */
typedef struct {
    uint32_t  next_job_id;       /**< Auto-incrementing job ID. */
    uint32_t  last_notify_ts;    /**< Timestamp of last generated notify. */
    uint32_t  interval_s;        /**< Seconds between fake notifies (default 60). */
    uint8_t   prevhash[32];      /**< Rolling prevhash (incremented per job). */
    bool      connected;         /**< Simulated upstream status. */
} ehash_upstream_mock_t;

/**
 * @brief Initialize the mock upstream.
 * @param m          Mock state.
 * @param interval_s Seconds between fake mining.notify (0 = 60).
 */
void ehash_upstream_mock_init(ehash_upstream_mock_t *m, uint32_t interval_s);

/**
 * @brief Generate a fake mining.notify template if interval has elapsed.
 *
 * @param m     Mock state.
 * @param now   Current Unix timestamp.
 * @param tmpl  Output template (filled in if a new job is generated).
 * @return 1 if a new template was generated, 0 if not yet time, <0 on error.
 */
int ehash_upstream_mock_poll(ehash_upstream_mock_t *m,
                              uint32_t now,
                              ehash_template_t *tmpl);

/**
 * @brief Set simulated upstream connection status.
 */
void ehash_upstream_mock_set_connected(ehash_upstream_mock_t *m, bool connected);

#ifdef __cplusplus
}
#endif

#endif /* EHASH_UPSTREAM_H */
