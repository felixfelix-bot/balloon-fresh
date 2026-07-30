/**
 * @file test_fips_radio_bridge.cpp
 * @brief Host-side integration test: FIPS Noise IK handshake over LR2021 transport.
 *
 * Phase 1 integration test. Proves the full FIPS handshake + encrypted payload
 * exchange works end-to-end through the LR2021 transport layer.
 *
 * ## Test Setup
 *
 * Two Lr2021Transport instances are created with PairedRadio mocks that
 * cross-connect: TX on radio A → RX on radio B and vice versa, simulating
 * a wireless link. FipsRadioBridge wraps each transport, providing the
 * send/recv interface that FIPS expects.
 *
 * ## Test Flow
 *
 * 1. PairedRadio / bridge basic round-trip
 * 2. Step-by-step Noise IK handshake (MSG1 → MSG2 → ESTABLISHED)
 * 3. Encrypted payload exchange ("Hello from balloon!" / "Hello from ground!")
 * 4. Full handshake via fips_run_initiator/fips_run_responder (threaded)
 *
 * Build: see Makefile. Run: ./test_fips_radio_bridge
 */

#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <stdlib.h>
#include <vector>
#include <thread>
#include <chrono>
#include <cstring>

#include "lr2021_spi.h"
#include "lr2021_framing.h"
#include "lr2021_transport.h"

#include "fips_transport.h"
#include "uECC.h"

#include "fips_radio_bridge.h"

// ── Tiny test framework (same style as test_lr2021.cpp / test_fips.cpp) ──

static int g_tests_run = 0;
static int g_tests_pass = 0;

#define TEST(name) \
    static int name(void); \
    static int name(void)

#define RUN(name) do { \
    g_tests_run++; \
    int r = name(); \
    if (r) g_tests_pass++; \
    printf("  [%s] %s\n", r ? "PASS" : "FAIL", #name); \
} while (0)

#define CHECK(cond) do { \
    if (!(cond)) { \
        printf("    CHECK failed: %s (line %d)\n", #cond, __LINE__); \
        return 0; \
    } \
} while (0)

#define CHECK_EQ(a, b) do { \
    auto _a = (a); auto _b = (b); \
    if (!(_a == _b)) { \
        printf("    CHECK_EQ failed: %s != %s (line %d): got %lld, want %lld\n", \
               #a, #b, __LINE__, (long long)(int64_t)_a, (long long)(int64_t)_b); \
        return 0; \
    } \
} while (0)

// ═══════════════════════════════════════════════════════════════════
// PairedRadio — mock radio that cross-connects TX→RX between two instances.
// When send_packet() is called on one radio, the packet is delivered to
// the peer's RX queue (simulating a wireless link).
// ═══════════════════════════════════════════════════════════════════

class PairedRadio : public Lr2021Radio {
public:
    PairedRadio() : peer_(nullptr), irq_flags_(0), initialized_(false) {}

    void set_peer(PairedRadio* peer) { peer_ = peer; }

    bool is_initialized() const { return initialized_; }

    const std::vector<std::vector<uint8_t>>& get_tx_packets() const {
        return tx_packets_;
    }

    // ── Lr2021Radio interface ──

    Lr2021Error init(const Lr2021Config& config) override {
        (void)config;
        initialized_ = true;
        return Lr2021Error::Ok;
    }

    Lr2021Error start_rx() override { return Lr2021Error::Ok; }

    Lr2021Error send_packet(const uint8_t* data, size_t len) override {
        // Record TX for test inspection
        tx_packets_.push_back(std::vector<uint8_t>(data, data + len));
        // Simulate TX_DONE
        irq_flags_ |= IrqSource::TX_DONE;
        // Deliver to peer's RX queue (the "radio wave")
        if (peer_) {
            peer_->rx_queue_.push_back(std::vector<uint8_t>(data, data + len));
            peer_->irq_flags_ |= IrqSource::RX_DONE;
        }
        return Lr2021Error::Ok;
    }

    Lr2021Error read_packet(uint8_t* buf, size_t buf_len, PacketStatus& status) override {
        if (rx_queue_.empty()) {
            status = PacketStatus{};
            return Lr2021Error::Ok;
        }
        auto& pkt = rx_queue_.front();
        size_t n = pkt.size() < buf_len ? pkt.size() : buf_len;
        memcpy(buf, pkt.data(), n);
        rx_queue_.erase(rx_queue_.begin());
        status = PacketStatus{};
        status.length = n;
        status.crc_ok = true;
        return Lr2021Error::Ok;
    }

    Lr2021Error get_irq_status(uint32_t& flags) override {
        flags = irq_flags_;
        return Lr2021Error::Ok;
    }

    Lr2021Error clear_irq() override {
        irq_flags_ = 0;
        return Lr2021Error::Ok;
    }

    Lr2021Error check_irq(bool& asserted) override {
        asserted = !IrqSource::empty(irq_flags_);
        return Lr2021Error::Ok;
    }

    Lr2021Error standby() override { return Lr2021Error::Ok; }
    Lr2021Error sleep() override { return Lr2021Error::Ok; }

private:
    PairedRadio* peer_;
    std::vector<std::vector<uint8_t>> tx_packets_;
    std::vector<std::vector<uint8_t>> rx_queue_;
    uint32_t irq_flags_;
    bool initialized_;
};

// ═══════════════════════════════════════════════════════════════════
// Helper: generate a secp256k1 keypair
// ═══════════════════════════════════════════════════════════════════

static void gen_keypair(uint8_t priv[32], uint8_t pub[64]) {
    uECC_make_key(pub, priv, uECC_secp256k1());
}

// ═══════════════════════════════════════════════════════════════════
// Test 1: PairedRadio basic — TX on A arrives as RX on B
// ═══════════════════════════════════════════════════════════════════

TEST(test_paired_radio_basic) {
    PairedRadio radio_a, radio_b;
    radio_a.set_peer(&radio_b);
    radio_b.set_peer(&radio_a);

    radio_a.init(Lr2021Config{});
    radio_b.init(Lr2021Config{});

    uint8_t msg[] = "ping";
    CHECK_EQ(radio_a.send_packet(msg, 4), Lr2021Error::Ok);

    // radio_a should have TX_DONE
    uint32_t flags = 0;
    radio_a.get_irq_status(flags);
    CHECK(IrqSource::contains(flags, IrqSource::TX_DONE));

    // radio_b should have RX_DONE with the packet
    radio_b.get_irq_status(flags);
    CHECK(IrqSource::contains(flags, IrqSource::RX_DONE));

    uint8_t buf[16] = {0};
    PacketStatus st;
    CHECK_EQ(radio_b.read_packet(buf, sizeof(buf), st), Lr2021Error::Ok);
    CHECK_EQ(st.length, (size_t)4);
    CHECK(memcmp(buf, msg, 4) == 0);
    return 1;
}

// ═══════════════════════════════════════════════════════════════════
// Test 2: Bridge round-trip — send via bridge_a, recv via bridge_b
// ═══════════════════════════════════════════════════════════════════

TEST(test_bridge_roundtrip) {
    PairedRadio radio_a, radio_b;
    radio_a.set_peer(&radio_b);
    radio_b.set_peer(&radio_a);

    Lr2021Transport transport_a(&radio_a);
    Lr2021Transport transport_b(&radio_b);
    CHECK_EQ(transport_a.init(Lr2021Config{}), TransportError::Ok);
    CHECK_EQ(transport_b.init(Lr2021Config{}), TransportError::Ok);

    FipsRadioBridge bridge_a(&transport_a);
    FipsRadioBridge bridge_b(&transport_b);

    uint8_t out[] = "Hello through the radio!";
    CHECK_EQ(bridge_a.send(out, 24), 0);

    uint8_t in[64] = {0};
    int n = bridge_b.recv(in, sizeof(in));
    CHECK_EQ(n, 24);
    CHECK(memcmp(in, out, 24) == 0);
    return 1;
}

// ═══════════════════════════════════════════════════════════════════
// Test 3: Full Noise IK handshake + encrypted payload (step-by-step)
//
// This is the core integration test. It exercises:
// - secp256k1 keypair generation
// - FIPS MSG1 build → LR2021 send → LR2021 recv → responder process
// - FIPS MSG2 build → LR2021 send → LR2021 recv → initiator process
// - State transitions to ESTABLISHED on both sides
// - Encrypted payload "Hello from balloon!" → decrypt → verify
// - Encrypted payload "Hello from ground!" → decrypt → verify
// ═══════════════════════════════════════════════════════════════════

TEST(test_handshake_step_by_step) {
    // ── Generate test keypairs ──
    uint8_t priv_i[32], pub_i[64];   // initiator
    uint8_t priv_r[32], pub_r[64];   // responder
    gen_keypair(priv_i, pub_i);
    gen_keypair(priv_r, pub_r);

    // Compress responder's pubkey for initiator (Noise IK: responder static is pre-known)
    uint8_t pub_r_comp[33];
    uECC_compress(pub_r, pub_r_comp, uECC_secp256k1());

    // ── Create paired radio link ──
    PairedRadio radio_a, radio_b;
    radio_a.set_peer(&radio_b);
    radio_b.set_peer(&radio_a);

    Lr2021Transport transport_a(&radio_a);
    Lr2021Transport transport_b(&radio_b);
    CHECK_EQ(transport_a.init(Lr2021Config{}), TransportError::Ok);
    CHECK_EQ(transport_b.init(Lr2021Config{}), TransportError::Ok);

    FipsRadioBridge bridge_a(&transport_a);
    FipsRadioBridge bridge_b(&transport_b);

    // ── Initialize FIPS sessions ──
    fips_session_t sess_i;  // initiator
    fips_session_t sess_r;  // responder
    fips_init(&sess_i, priv_i, pub_r_comp);
    memset(&sess_r, 0, sizeof(sess_r));
    CHECK_EQ(sess_i.state, FIPS_STATE_IDLE);

    // ── MSG1: initiator → responder ──
    uint8_t msg1[FIPS_MSG1_SIZE];
    size_t msg1_len = 0;
    CHECK_EQ(fips_handshake_initiator_msg1(&sess_i, msg1, &msg1_len), 0);
    CHECK_EQ(msg1_len, (size_t)FIPS_MSG1_SIZE);
    CHECK_EQ(sess_i.state, FIPS_STATE_WAIT_MSG2);

    // Send MSG1 via bridge_a → radio_a → radio_b
    CHECK_EQ(bridge_a.send(msg1, msg1_len), 0);

    // Recv MSG1 via bridge_b
    uint8_t msg1_rx[FIPS_MSG1_SIZE + 16];
    int n1 = bridge_b.recv(msg1_rx, sizeof(msg1_rx));
    CHECK_EQ(n1, (int)FIPS_MSG1_SIZE);
    CHECK(memcmp(msg1, msg1_rx, FIPS_MSG1_SIZE) == 0);

    // ── MSG2: responder processes MSG1, builds MSG2 ──
    uint8_t msg2[FIPS_MSG2_SIZE];
    size_t msg2_len = 0;
    CHECK_EQ(fips_handshake_responder_process_msg1(
                 &sess_r, priv_r, msg1_rx, (size_t)n1, msg2, &msg2_len), 0);
    CHECK_EQ(msg2_len, (size_t)FIPS_MSG2_SIZE);
    CHECK_EQ(sess_r.state, FIPS_STATE_ESTABLISHED);

    // Send MSG2 via bridge_b → radio_b → radio_a
    CHECK_EQ(bridge_b.send(msg2, msg2_len), 0);

    // Recv MSG2 via bridge_a
    uint8_t msg2_rx[FIPS_MSG2_SIZE + 16];
    int n2 = bridge_a.recv(msg2_rx, sizeof(msg2_rx));
    CHECK_EQ(n2, (int)FIPS_MSG2_SIZE);

    // ── Initiator processes MSG2 → ESTABLISHED ──
    CHECK_EQ(fips_handshake_initiator_process_msg2(&sess_i, msg2_rx, (size_t)n2), 0);
    CHECK_EQ(sess_i.state, FIPS_STATE_ESTABLISHED);

    // ── Encrypted payload: initiator → responder ──
    const char* payload1 = "Hello from balloon!";  // 19 bytes
    size_t plen1 = strlen(payload1);
    uint8_t ct1[256];
    size_t ct1_len = 0;
    CHECK_EQ(fips_encrypt(&sess_i, (const uint8_t*)payload1, plen1, ct1, &ct1_len), 0);
    CHECK(ct1_len > plen1);  // must have overhead

    // Send ciphertext via bridge_a
    CHECK_EQ(bridge_a.send(ct1, ct1_len), 0);

    // Recv and decrypt on responder
    uint8_t ct1_rx[256];
    int cn1 = bridge_b.recv(ct1_rx, sizeof(ct1_rx));
    CHECK(cn1 > 0);

    uint8_t pt1[256];
    size_t pt1_len = 0;
    CHECK_EQ(fips_decrypt(&sess_r, ct1_rx, (size_t)cn1, pt1, &pt1_len), 0);
    CHECK_EQ(pt1_len, plen1);
    CHECK(memcmp(pt1, payload1, plen1) == 0);

    // ── Encrypted payload: responder → initiator ──
    const char* payload2 = "Hello from ground!";  // 19 bytes
    size_t plen2 = strlen(payload2);
    uint8_t ct2[256];
    size_t ct2_len = 0;
    CHECK_EQ(fips_encrypt(&sess_r, (const uint8_t*)payload2, plen2, ct2, &ct2_len), 0);

    // Send ciphertext via bridge_b
    CHECK_EQ(bridge_b.send(ct2, ct2_len), 0);

    // Recv and decrypt on initiator
    uint8_t ct2_rx[256];
    int cn2 = bridge_a.recv(ct2_rx, sizeof(ct2_rx));
    CHECK(cn2 > 0);

    uint8_t pt2[256];
    size_t pt2_len = 0;
    CHECK_EQ(fips_decrypt(&sess_i, ct2_rx, (size_t)cn2, pt2, &pt2_len), 0);
    CHECK_EQ(pt2_len, plen2);
    CHECK(memcmp(pt2, payload2, plen2) == 0);

    return 1;
}

// ═══════════════════════════════════════════════════════════════════
// Test 4: Full handshake via fips_run_initiator/fips_run_responder
//
// Uses the FIPS callback API (fips_send_fn/fips_recv_fn) with threads.
// The thread-local active_ pointer lets each thread use its own bridge.
// ═══════════════════════════════════════════════════════════════════

TEST(test_handshake_via_callbacks) {
    // ── Generate test keypairs ──
    uint8_t priv_i[32], pub_i[64];
    uint8_t priv_r[32], pub_r[64];
    gen_keypair(priv_i, pub_i);
    gen_keypair(priv_r, pub_r);

    uint8_t pub_r_comp[33];
    uECC_compress(pub_r, pub_r_comp, uECC_secp256k1());

    // ── Create paired radio link ──
    PairedRadio radio_a, radio_b;
    radio_a.set_peer(&radio_b);
    radio_b.set_peer(&radio_a);

    Lr2021Transport transport_a(&radio_a);
    Lr2021Transport transport_b(&radio_b);
    CHECK_EQ(transport_a.init(Lr2021Config{}), TransportError::Ok);
    CHECK_EQ(transport_b.init(Lr2021Config{}), TransportError::Ok);

    FipsRadioBridge bridge_a(&transport_a);
    FipsRadioBridge bridge_b(&transport_b);

    // ── Initialize FIPS sessions ──
    fips_session_t sess_i;
    fips_session_t sess_r;
    fips_init(&sess_i, priv_i, pub_r_comp);
    memset(&sess_r, 0, sizeof(sess_r));

    // ── Wrapper callbacks with retry-recv ──
    // The bridge recv is non-blocking (single IRQ poll + drain). For the
    // threaded handshake we must retry until the peer's data arrives.
    // Each callback uses the thread-local active_ pointer, so each thread
    // routes to its own bridge automatically.
    auto retry_recv_fn = +[](uint8_t* data, size_t max_len) -> int {
        for (int i = 0; i < 2500; i++) {  // 5 s timeout (2500 × 2 ms)
            int n = FipsRadioBridge::recv_callback(data, max_len);
            if (n > 0) return n;
            std::this_thread::sleep_for(std::chrono::milliseconds(2));
        }
        return -1;  // timeout
    };
    auto direct_send_fn = +[](const uint8_t* data, size_t len) -> int {
        return FipsRadioBridge::send_callback(data, len);
    };

    // ── Responder thread: recv MSG1 → process → send MSG2 ──
    // Store result instead of using CHECK inside the thread (CHECK does
    // `return 0` which would exit only the lambda, not the test).
    int resp_rc = -999;
    auto responder_fn = [&]() {
        bridge_b.set_active();  // thread-local active pointer for this thread
        resp_rc = fips_run_responder(&sess_r, priv_r,
                                      direct_send_fn, retry_recv_fn);
    };

    std::thread responder_thread(responder_fn);

    // RAII guard: ensures join() is ALWAYS called before the thread
    // destructor runs, preventing std::terminate if a CHECK below fails
    // and returns early from this function.
    struct JoinGuard {
        std::thread& t;
        ~JoinGuard() { if (t.joinable()) t.join(); }
    } join_guard{responder_thread};

    // ── Initiator (main thread): build MSG1 → send → recv MSG2 → ESTABLISHED ──
    bridge_a.set_active();
    int rc = fips_run_initiator(&sess_i, direct_send_fn, retry_recv_fn);
    CHECK_EQ(rc, 0);

    // Explicit join (join_guard is the safety net for early CHECK returns)
    responder_thread.join();

    CHECK_EQ(resp_rc, 0);
    CHECK_EQ(sess_i.state, FIPS_STATE_ESTABLISHED);
    CHECK_EQ(sess_r.state, FIPS_STATE_ESTABLISHED);

    // ── Encrypted payload exchange ──
    const char* payload = "Secure radio link established!";
    size_t plen = strlen(payload);

    // Initiator encrypts and sends
    bridge_a.set_active();
    uint8_t ct[256];
    size_t ct_len = 0;
    CHECK_EQ(fips_encrypt(&sess_i, (const uint8_t*)payload, plen, ct, &ct_len), 0);
    CHECK_EQ(FipsRadioBridge::send_callback(ct, ct_len), 0);

    // Responder receives and decrypts
    uint8_t ct_rx[256];
    bridge_b.set_active();
    int n = FipsRadioBridge::recv_callback(ct_rx, sizeof(ct_rx));
    CHECK(n > 0);

    uint8_t pt[256];
    size_t pt_len = 0;
    CHECK_EQ(fips_decrypt(&sess_r, ct_rx, (size_t)n, pt, &pt_len), 0);
    CHECK_EQ(pt_len, plen);
    CHECK(memcmp(pt, payload, plen) == 0);

    return 1;
}

// ═══════════════════════════════════════════════════════════════════
// Main
// ═══════════════════════════════════════════════════════════════════

int main(void) {
    printf("\n=== FIPS Radio Bridge Integration Tests ===\n\n");

    printf("PairedRadio tests:\n");
    RUN(test_paired_radio_basic);

    printf("\nBridge tests:\n");
    RUN(test_bridge_roundtrip);

    printf("\nHandshake tests:\n");
    RUN(test_handshake_step_by_step);
    RUN(test_handshake_via_callbacks);

    printf("\n=== Results: %d/%d passed ===\n\n", g_tests_pass, g_tests_run);
    return g_tests_pass == g_tests_run ? 0 : 1;
}
