/*
 * blossom_datagram.c — Bridge between mesh datagram transport and
 * blossom blob storage.
 *
 * See blossom_datagram.h for the wire format and the rationale for the
 * dependency-injected backend callbacks.
 */
#include "blossom_datagram.h"

#include <string.h>

/* ── Internal state ─────────────────────────────────────────────── */

static blossom_dgram_config_t s_cfg;

/* Pending auth event side-channel (see header). */
static uint8_t s_pending_auth_sha[BLOSSOM_SHA256_LEN];
static uint8_t s_pending_auth_event[1024];
static size_t  s_pending_auth_event_len;
static bool    s_pending_auth_valid;

void blossom_datagram_init(const blossom_dgram_config_t *cfg)
{
    if (cfg) {
        s_cfg = *cfg;
    } else {
        memset(&s_cfg, 0, sizeof(s_cfg));
    }
    s_pending_auth_valid = false;
    s_pending_auth_event_len = 0;
}

/* ── Helpers ────────────────────────────────────────────────────── */

static uint8_t clamp_content_type_len(const char *content_type)
{
    if (!content_type) return 0;
    size_t n = strlen(content_type);
    if (n > BLOSSOM_MAX_CONTENT_TYPE_LEN) n = BLOSSOM_MAX_CONTENT_TYPE_LEN;
    return (uint8_t)n;
}

/* ── Serialization ──────────────────────────────────────────────── */

int blossom_dgram_serialize_put(
    uint8_t *out_buf, size_t out_cap,
    const uint8_t *sha256,
    const char *content_type,
    const uint8_t *payload, size_t payload_len)
{
    if (!out_buf || !sha256) return BLOSSOM_DGRAM_ERR_INVALID_PARAM;
    if (payload_len > 0 && !payload) return BLOSSOM_DGRAM_ERR_INVALID_PARAM;
    if (payload_len > BLOSSOM_DGRAM_MAX_PAYLOAD) return BLOSSOM_DGRAM_ERR_TOO_LARGE;

    uint8_t ct_len = clamp_content_type_len(content_type);
    size_t need = (size_t)BLOSSOM_DGRAM_HEADER_LEN + ct_len + payload_len;
    if (need > out_cap) return BLOSSOM_DGRAM_ERR_TOO_LARGE;

    size_t off = 0;
    out_buf[off++] = BLOSSOM_MSG_PUT;
    memcpy(out_buf + off, sha256, BLOSSOM_SHA256_LEN);
    off += BLOSSOM_SHA256_LEN;
    out_buf[off++] = ct_len;
    if (ct_len > 0) {
        memcpy(out_buf + off, content_type, ct_len);
        off += ct_len;
    }
    if (payload_len > 0) {
        memcpy(out_buf + off, payload, payload_len);
        off += payload_len;
    }
    return (int)off;
}

int blossom_dgram_serialize_get(
    uint8_t *out_buf, size_t out_cap,
    const uint8_t *sha256)
{
    if (!out_buf || !sha256) return BLOSSOM_DGRAM_ERR_INVALID_PARAM;
    if ((size_t)BLOSSOM_DGRAM_HEADER_LEN > out_cap)
        return BLOSSOM_DGRAM_ERR_TOO_LARGE;

    size_t off = 0;
    out_buf[off++] = BLOSSOM_MSG_GET;
    memcpy(out_buf + off, sha256, BLOSSOM_SHA256_LEN);
    off += BLOSSOM_SHA256_LEN;
    out_buf[off++] = 0; /* content_type_len unused for GET */
    return (int)off;
}

int blossom_dgram_serialize_response(
    uint8_t *out_buf, size_t out_cap,
    const uint8_t *sha256,
    const uint8_t *payload, size_t payload_len)
{
    if (!out_buf || !sha256) return BLOSSOM_DGRAM_ERR_INVALID_PARAM;
    if (payload_len > 0 && !payload) return BLOSSOM_DGRAM_ERR_INVALID_PARAM;
    if (payload_len > BLOSSOM_DGRAM_MAX_PAYLOAD) return BLOSSOM_DGRAM_ERR_TOO_LARGE;

    size_t need = (size_t)BLOSSOM_DGRAM_HEADER_LEN + payload_len;
    if (need > out_cap) return BLOSSOM_DGRAM_ERR_TOO_LARGE;

    size_t off = 0;
    out_buf[off++] = BLOSSOM_MSG_RESPONSE;
    memcpy(out_buf + off, sha256, BLOSSOM_SHA256_LEN);
    off += BLOSSOM_SHA256_LEN;
    out_buf[off++] = 0; /* content_type_len unused for RESPONSE */
    if (payload_len > 0) {
        memcpy(out_buf + off, payload, payload_len);
        off += payload_len;
    }
    return (int)off;
}

int blossom_dgram_serialize_error(
    uint8_t *out_buf, size_t out_cap,
    const uint8_t *sha256,
    const uint8_t *reason, size_t reason_len)
{
    if (!out_buf || !sha256) return BLOSSOM_DGRAM_ERR_INVALID_PARAM;
    if (reason_len > 0 && !reason) return BLOSSOM_DGRAM_ERR_INVALID_PARAM;
    if (reason_len > BLOSSOM_DGRAM_MAX_PAYLOAD) return BLOSSOM_DGRAM_ERR_TOO_LARGE;

    size_t need = (size_t)BLOSSOM_DGRAM_HEADER_LEN + reason_len;
    if (need > out_cap) return BLOSSOM_DGRAM_ERR_TOO_LARGE;

    size_t off = 0;
    out_buf[off++] = BLOSSOM_MSG_ERROR;
    memcpy(out_buf + off, sha256, BLOSSOM_SHA256_LEN);
    off += BLOSSOM_SHA256_LEN;
    out_buf[off++] = 0;
    if (reason_len > 0) {
        memcpy(out_buf + off, reason, reason_len);
        off += reason_len;
    }
    return (int)off;
}

/* ── Parse ──────────────────────────────────────────────────────── */

blossom_dgram_result_t blossom_dgram_parse(
    const uint8_t *buf, size_t buf_len,
    blossom_dgram_msg_t *msg)
{
    if (!buf || !msg) return BLOSSOM_DGRAM_ERR_INVALID_PARAM;
    if (buf_len < (size_t)BLOSSOM_DGRAM_HEADER_LEN)
        return BLOSSOM_DGRAM_ERR_TRUNCATED;

    memset(msg, 0, sizeof(*msg));
    msg->type = buf[0];
    if (msg->type != BLOSSOM_MSG_PUT &&
        msg->type != BLOSSOM_MSG_GET &&
        msg->type != BLOSSOM_MSG_RESPONSE &&
        msg->type != BLOSSOM_MSG_ERROR) {
        return BLOSSOM_DGRAM_ERR_FORMAT;
    }
    memcpy(msg->sha256, buf + 1, BLOSSOM_SHA256_LEN);
    msg->content_type_len = buf[33];

    size_t off = (size_t)BLOSSOM_DGRAM_HEADER_LEN;

    if (msg->content_type_len > 0) {
        if (msg->content_type_len > BLOSSOM_MAX_CONTENT_TYPE_LEN)
            return BLOSSOM_DGRAM_ERR_FORMAT;
        if (off + msg->content_type_len > buf_len)
            return BLOSSOM_DGRAM_ERR_TRUNCATED;
        msg->content_type = (const char *)(buf + off);
        off += msg->content_type_len;
    }

    if (off <= buf_len) {
        msg->payload = buf + off;
        msg->payload_len = buf_len - off;
    } else {
        msg->payload = NULL;
        msg->payload_len = 0;
    }
    return BLOSSOM_DGRAM_OK;
}

/* ── High-level send helpers ────────────────────────────────────── */

blossom_dgram_result_t blossom_datagram_put_blob(
    const uint8_t *sha256,
    const char *content_type,
    const uint8_t *payload, size_t payload_len)
{
    if (!sha256 || !s_cfg.send)
        return BLOSSOM_DGRAM_ERR_INVALID_PARAM;

    uint8_t buf[BLOSSOM_DGRAM_HEADER_LEN +
                BLOSSOM_MAX_CONTENT_TYPE_LEN +
                BLOSSOM_DGRAM_MAX_PAYLOAD];
    int n = blossom_dgram_serialize_put(buf, sizeof(buf), sha256,
                                        content_type, payload, payload_len);
    if (n < 0) return (blossom_dgram_result_t)n;

    return s_cfg.send(buf, (size_t)n);
}

blossom_dgram_result_t blossom_datagram_get_blob(const uint8_t *sha256)
{
    if (!sha256 || !s_cfg.send)
        return BLOSSOM_DGRAM_ERR_INVALID_PARAM;

    uint8_t buf[BLOSSOM_DGRAM_HEADER_LEN];
    int n = blossom_dgram_serialize_get(buf, sizeof(buf), sha256);
    if (n < 0) return (blossom_dgram_result_t)n;

    return s_cfg.send(buf, (size_t)n);
}

/* ── Inbound routing ────────────────────────────────────────────── */

blossom_dgram_result_t blossom_datagram_handle_message(
    const uint8_t *buf, size_t buf_len)
{
    blossom_dgram_msg_t msg;
    blossom_dgram_result_t r = blossom_dgram_parse(buf, buf_len, &msg);
    if (r != BLOSSOM_DGRAM_OK) return r;

    switch (msg.type) {
    case BLOSSOM_MSG_PUT: {
        if (!s_cfg.store)
            return BLOSSOM_DGRAM_ERR_NO_BACKEND;

        /* Auth side-channel: if an auth backend is configured, require
         * a matching pending auth event for this blob's SHA-256. */
        if (s_cfg.auth) {
            if (!s_pending_auth_valid ||
                memcmp(s_pending_auth_sha, msg.sha256,
                       BLOSSOM_SHA256_LEN) != 0) {
                return BLOSSOM_DGRAM_ERR_AUTH;
            }
            r = s_cfg.auth(msg.sha256, s_pending_auth_event,
                           s_pending_auth_event_len);
            if (r != BLOSSOM_DGRAM_OK) {
                s_pending_auth_valid = false;
                return r;
            }
            /* Auth consumed — clear so it can't be replayed. */
            s_pending_auth_valid = false;
        }

        /* Build a NUL-terminated content_type for the store backend. */
        char ct[BLOSSOM_MAX_CONTENT_TYPE_LEN + 1];
        if (msg.content_type_len > 0) {
            memcpy(ct, msg.content_type, msg.content_type_len);
            ct[msg.content_type_len] = '\0';
        } else {
            ct[0] = '\0';
        }
        return s_cfg.store(msg.sha256, msg.payload, msg.payload_len,
                           msg.content_type_len > 0 ? ct : NULL);
    }

    case BLOSSOM_MSG_GET: {
        if (!s_cfg.load || !s_cfg.send)
            return BLOSSOM_DGRAM_ERR_NO_BACKEND;

        uint8_t blob[BLOSSOM_DGRAM_MAX_PAYLOAD];
        size_t blob_len = sizeof(blob);
        char ct[BLOSSOM_MAX_CONTENT_TYPE_LEN + 1] = {0};
        r = s_cfg.load(msg.sha256, blob, &blob_len, ct, sizeof(ct));
        if (r != BLOSSOM_DGRAM_OK) {
            /* Send an ERROR back through the mesh. */
            const uint8_t reason[] = "not found";
            uint8_t errbuf[BLOSSOM_DGRAM_HEADER_LEN + sizeof(reason) - 1];
            int n = blossom_dgram_serialize_error(errbuf, sizeof(errbuf),
                                                  msg.sha256,
                                                  reason, sizeof(reason) - 1);
            if (n > 0) {
                s_cfg.send(errbuf, (size_t)n);
            }
            return BLOSSOM_DGRAM_ERR_NOT_FOUND;
        }
        uint8_t resp[BLOSSOM_DGRAM_HEADER_LEN + BLOSSOM_DGRAM_MAX_PAYLOAD];
        int n = blossom_dgram_serialize_response(resp, sizeof(resp),
                                                 msg.sha256,
                                                 blob, blob_len);
        if (n < 0) return (blossom_dgram_result_t)n;
        return s_cfg.send(resp, (size_t)n);
    }

    case BLOSSOM_MSG_RESPONSE: {
        if (s_cfg.on_response) {
            s_cfg.on_response(msg.sha256, msg.payload, msg.payload_len);
        }
        return BLOSSOM_DGRAM_OK;
    }

    case BLOSSOM_MSG_ERROR: {
        if (s_cfg.on_error) {
            s_cfg.on_error(msg.sha256, msg.payload, msg.payload_len);
        }
        return BLOSSOM_DGRAM_OK;
    }

    default:
        return BLOSSOM_DGRAM_ERR_FORMAT;
    }
}

/* ── Auth side channel ──────────────────────────────────────────── */

blossom_dgram_result_t blossom_datagram_set_pending_auth(
    const uint8_t *sha256,
    const uint8_t *event, size_t event_len)
{
    if (!sha256) return BLOSSOM_DGRAM_ERR_INVALID_PARAM;
    if (event_len > sizeof(s_pending_auth_event))
        return BLOSSOM_DGRAM_ERR_TOO_LARGE;
    if (event_len > 0 && !event) return BLOSSOM_DGRAM_ERR_INVALID_PARAM;

    memcpy(s_pending_auth_sha, sha256, BLOSSOM_SHA256_LEN);
    if (event_len > 0) {
        memcpy(s_pending_auth_event, event, event_len);
    }
    s_pending_auth_event_len = event_len;
    s_pending_auth_valid = event_len > 0;
    return BLOSSOM_DGRAM_OK;
}
