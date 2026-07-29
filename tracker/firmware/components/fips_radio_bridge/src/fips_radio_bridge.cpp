/**
 * @file fips_radio_bridge.cpp
 * @brief Bridge implementation — routes FIPS send/recv through Lr2021Transport.
 *
 * Phase 1 integration component.
 */

#include "fips_radio_bridge.h"

// Thread-local active bridge pointer (one per thread).
thread_local FipsRadioBridge* FipsRadioBridge::active_ = nullptr;

int FipsRadioBridge::send(const uint8_t* data, size_t len) {
    // Push data into the TX framer
    if (transport_->send(data, len) != TransportError::Ok)
        return -1;
    // Flush as a radio packet (transmit_packet → radio->send_packet)
    if (transport_->flush_tx() != TransportError::Ok)
        return -1;
    return 0;
}

int FipsRadioBridge::recv(uint8_t* data, size_t max_len) {
    // Poll IRQ to pick up any received packets from the radio
    if (transport_->poll_irq() != TransportError::Ok)
        return -1;

    // Drain from the RX framer
    size_t n = 0;
    if (transport_->recv(data, max_len, &n) != TransportError::Ok)
        return -1;
    return (int)n;
}
