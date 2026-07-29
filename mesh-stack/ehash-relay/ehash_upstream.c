/**
 * @file ehash_upstream.c
 * @brief Mock upstream connection (simulates e-hash proxy).
 *
 * Generates fake mining.notify templates for testing. In production,
 * the real stratum client code will replace this module entirely —
 * the relay's ehash_upstream_tx_fn callback is the actual interface.
 */

#include "ehash_upstream.h"
#include <string.h>

/* Static sample coinbase data for mock templates. */
static const uint8_t s_mock_coinbase1[] = {
    0x46, 0x65, 0x6C, 0x69, 0x78, 0x42, 0x61, 0x6C,
    0x6C, 0x6F, 0x6F, 0x6E, 0x4D, 0x69, 0x6E, 0x65,
    0x21, 0x00, 0x00, 0x00
};  /* "FelixBalloonMine!" + 3 bytes, 20 total */

static const uint8_t s_mock_coinbase2[] = {
    0xAF, 0x1D, 0x6E, 0x3B, 0x00, 0x00, 0x00, 0x00,
    0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
};  /* 16 bytes */

static uint8_t s_mock_merkle1[32] = {
    0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x00, 0x11,
    0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88, 0x99,
    0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF,
    0xFE, 0xDC, 0xBA, 0x98, 0x76, 0x54, 0x32, 0x10
};

static uint8_t s_mock_merkle2[32] = {
    0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF, 0x01,
    0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF, 0x01,
    0x00, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77,
    0x88, 0x99, 0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF
};

/* We need a combined merkle branch buffer for the template struct pointer. */
static uint8_t s_mock_merkle_branches[64];  /* 2 × 32 bytes */

void ehash_upstream_mock_init(ehash_upstream_mock_t *m, uint32_t interval_s) {
    memset(m, 0, sizeof(*m));
    m->next_job_id   = 1;
    m->interval_s    = interval_s ? interval_s : 60;
    m->connected     = true;

    /* Initialize prevhash with a known value. */
    for (int i = 0; i < 32; i++) {
        m->prevhash[i] = (uint8_t)(i * 0x11);
    }

    /* Copy merkle branches into the combined buffer. */
    memcpy(s_mock_merkle_branches,      s_mock_merkle1, 32);
    memcpy(s_mock_merkle_branches + 32, s_mock_merkle2, 32);
}

int ehash_upstream_mock_poll(ehash_upstream_mock_t *m,
                              uint32_t now,
                              ehash_template_t *tmpl)
{
    if (!m || !tmpl) return -3;
    if (!m->connected) return 0;

    if (m->last_notify_ts != 0 && (now - m->last_notify_ts) < m->interval_s) {
        return 0;  /* Not time yet. */
    }

    /* Generate a new fake template. */
    m->last_notify_ts = now;

    /* Increment prevhash to simulate new block. */
    m->prevhash[0] = (uint8_t)((m->prevhash[0] + 1) & 0xFF);

    tmpl->job_id              = m->next_job_id++;
    tmpl->prevhash            = m->prevhash;
    tmpl->btc_version         = 0x20000000;
    tmpl->nbits               = 0x1D00FFFF;
    tmpl->ntime               = 0;  /* 0 = use current time */
    tmpl->coinbase1           = (uint8_t *)s_mock_coinbase1;
    tmpl->coinbase1_len       = sizeof(s_mock_coinbase1);
    tmpl->coinbase2           = (uint8_t *)s_mock_coinbase2;
    tmpl->coinbase2_len       = sizeof(s_mock_coinbase2);
    tmpl->merkle_branch_count = 2;
    tmpl->merkle_branches     = s_mock_merkle_branches;
    tmpl->clean_jobs          = 1;

    return 1;
}

void ehash_upstream_mock_set_connected(ehash_upstream_mock_t *m, bool connected) {
    if (!m) return;
    m->connected = connected;
}
