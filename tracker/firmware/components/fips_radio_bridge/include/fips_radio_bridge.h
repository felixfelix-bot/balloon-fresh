/**
 * @file fips_radio_bridge.h
 * @brief Bridge connecting FIPS Noise IK transport to LR2021 radio transport.
 *
 * Phase 1 integration component. Wraps Lr2021Transport (packet-based FLRC link)
 * behind the C-style callback interface that fips_transport expects
 * (fips_send_fn / fips_recv_fn), enabling the Noise IK handshake and AEAD
 * encrypted payload exchange to flow transparently over the radio link.
 *
 * ## Architecture
 *
 *  ┌──────────────────┐  fips_send_fn / fips_recv_fn
 *  │  FIPS Protocol   │ ◄────────────────────────────►  FipsRadioBridge
 *  │  (Noise IK)      │                                    │
 *  └──────────────────┘                                    │
 *                                               ┌──────────┴──────────┐
 *                                               │  Lr2021Transport     │
 *                                               │  (stream ↔ packets)  │
 *                                               └──────────┬──────────┘
 *                                                          │
 *                                               ┌──────────┴──────────┐
 *                                               │  LR2021 Radio (SPI)  │
 *                                               └─────────────────────┘
 *
 * ## Callback Pattern
 *
 * The FIPS API uses C function pointers with no user_data parameter:
 *   typedef int (*fips_send_fn)(const uint8_t*, size_t);
 *   typedef int (*fips_recv_fn)(uint8_t*, size_t);
 *
 * To route callbacks to the correct bridge instance, a thread-local "active"
 * pointer is used. Call set_active() before invoking fips_run_initiator() or
 * fips_run_responder() from that thread.
 */

#ifndef FIPS_RADIO_BRIDGE_H
#define FIPS_RADIO_BRIDGE_H

#include <stdint.h>
#include <stddef.h>

#include "fips_transport.h"
#include "lr2021_transport.h"

#ifdef __cplusplus

class FipsRadioBridge {
public:
    /**
     * Create a bridge wrapping the given LR2021 transport.
     * @param transport  The Lr2021Transport to route FIPS data through.
     *                   Caller retains ownership.
     */
    explicit FipsRadioBridge(Lr2021Transport* transport)
        : transport_(transport) {}

    // ── Instance methods (for step-by-step handshake) ──

    /**
     * Send data over the LR2021 transport.
     * Pushes to TX framer and flushes immediately as a radio packet.
     * @return 0 on success, -1 on failure.
     */
    int send(const uint8_t* data, size_t len);

    /**
     * Receive data from the LR2021 transport.
     * Polls IRQ to collect received packets, then drains from RX framer.
     * @return number of bytes received, or -1 on failure.
     */
    int recv(uint8_t* data, size_t max_len);

    // ── Static callback wrappers (for fips_send_fn / fips_recv_fn) ──

    /** Set this bridge as the "active" bridge for the current thread. */
    void set_active() { active_ = this; }

    /** Static callback matching fips_send_fn signature. */
    static int send_callback(const uint8_t* data, size_t len) {
        return active_ ? active_->send(data, len) : -1;
    }

    /** Static callback matching fips_recv_fn signature. */
    static int recv_callback(uint8_t* data, size_t max_len) {
        return active_ ? active_->recv(data, max_len) : -1;
    }

    /** Get the send function pointer (use after set_active()). */
    static fips_send_fn get_send_fn() { return &send_callback; }

    /** Get the recv function pointer (use after set_active()). */
    static fips_recv_fn get_recv_fn() { return &recv_callback; }

    /// Access the underlying transport.
    Lr2021Transport* transport() { return transport_; }

private:
    Lr2021Transport* transport_;

    // Thread-local active pointer: each thread can set its own bridge
    // before calling fips_run_initiator / fips_run_responder.
    static thread_local FipsRadioBridge* active_;
};

#endif // __cplusplus
#endif // FIPS_RADIO_BRIDGE_H
