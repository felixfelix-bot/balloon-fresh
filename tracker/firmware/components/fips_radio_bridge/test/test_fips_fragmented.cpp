/**
 * @file test_fips_fragmented.cpp
 * @brief Phase 3 host test: encrypted multi-frame transport over LR2021.
 *
 * Proves that payloads LARGER than a single FIPS frame (190 bytes plaintext,
 * 222 bytes ciphertext) can be split into multiple independently-encrypted
 * FIPS frames, sent as individual LR2021 radio packets, received, decrypted,
 * and reassembled correctly.
 *
 * ## Architecture
 *
 * Application-layer fragmentation (split BEFORE encrypt):
 *
 *   ┌─────────────┐
 *   │ 1 KiB       │  Application payload
 *   │ Application │
 *   │ Payload     │
 *   └──────┬──────┘
 *          │ split into 190-byte chunks
 *          ▼
 *   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
 *   │ Chunk 0  │ │ Chunk 1  │ │ Chunk 2  │ │ Chunk 3  │ │ Chunk 4  │ │ Chunk 5  │
 *   │ 190 B    │ │ 190 B    │ │ 190 B    │ │ 190 B    │ │ 190 B    │ │ 64 B     │
 *   └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘
 *        │ fips_encrypt each independently (ChaChaPoly AEAD)
 *        ▼
 *   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
 *   │FIPS Ct 0 │ │FIPS Ct 1 │ │FIPS Ct 2 │ │FIPS Ct 3 │ │FIPS Ct 4 │ │FIPS Ct 5 │
 *   │ 222 B    │ │ 222 B    │ │ 222 B    │ │ 222 B    │ │ 222 B    │ │ 96 B     │
 *   └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘
 *        │ each ≤ 255 → one LR2021 packet per FIPS frame
 *        ▼
 *   ══════════════════════════════════════════════════════════════════
 *          LR2021 FLRC Radio Link (6 packets, half-duplex)
 *   ══════════════════════════════════════════════════════════════════
 *        │
 *        ▼ receive each, fips_decrypt, reassemble
 *   ┌─────────────┐
 *   │ 1 KiB       │  Original payload recovered
 *   └─────────────┘
 *
 * ## Sizing
 *
 * FIPS_MAX_PAYLOAD     = 222 bytes (maximum total FIPS frame = ciphertext)
 * FIPS_FMP_OVERHEAD    = 32 bytes (4 prefix + 4 idx + 8 counter + 16 AEAD tag)
 * FIPS_CHUNK_SIZE      = 190 bytes (max plaintext per frame = 222 - 32)
 * Ciphertext per frame = plaintext + 32 → max 222 bytes ≤ 255 (LR2021 max)
 *
 * ## Test Summary
 *
 * Test 1: 100 B  — 1 FIPS frame, 1 LR2021 packet
 * Test 2: 500 B  — 3 FIPS frames, 3 LR2021 packets
 * Test 3: 1024 B — 6 FIPS frames, 6 LR2021 packets
 * Test 4: 190 B  — exact boundary: 1 max-size FIPS frame (222 B ciphertext)
 * Test 5: Bidirectional — A sends 500 B (3 frames), B sends 300 B (2 frames)
 *
 * Build: see Makefile. Run: ./test_fips_fragmented
 */

#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <stdlib.h>
#include <vector>

#include "lr2021_spi.h"
#include "lr2021_framing.h"
#include "lr2021_transport.h"

#include "fips_transport.h"
#include "uECC.h"

#include "fips_radio_bridge.h"

// ═══════════════════════════════════════════════════════════════════
// Tiny test framework (same style as test_fips_radio_bridge.cpp)
// ═══════════════════════════════════════════════════════════════════

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
// (Copied from test_fips_radio_bridge.cpp — Phase 1 integration test.)
//
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
        tx_packets_.push_back(std::vector<uint8_t>(data, data + len));
        irq_flags_ |= IrqSource::TX_DONE;
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
// Constants & helpers
// ═══════════════════════════════════════════════════════════════════

/// Max plaintext per FIPS frame = FIPS_MAX_PAYLOAD - FIPS_FMP_OVERHEAD
///   = 222 - (4 + 4 + 8 + 16) = 222 - 32 = 190 bytes
/// Resulting ciphertext = 190 + 32 = 222 bytes ≤ 255 (LR2021 max packet)
static constexpr size_t FIPS_CHUNK_SIZE = FIPS_MAX_PAYLOAD - FIPS_FMP_OVERHEAD;

/// Expected number of FIPS frames for a given payload length
static int expected_frame_count(size_t payload_len) {
    if (payload_len == 0) return 1;  // edge: empty → one zero-length frame
    return (int)((payload_len + FIPS_CHUNK_SIZE - 1) / FIPS_CHUNK_SIZE);
}

/// Generate a deterministic but non-trivial payload pattern
static void fill_payload(uint8_t* buf, size_t len, uint8_t seed) {
    for (size_t i = 0; i < len; i++) {
        buf[i] = (uint8_t)((seed + i * 7 + 13) & 0xFF);
    }
}

/// Generate a secp256k1 keypair
static void gen_keypair(uint8_t priv[32], uint8_t pub[64]) {
    uECC_make_key(pub, priv, uECC_secp256k1());
}

// ═══════════════════════════════════════════════════════════════════
// setup_established_link — create paired radio link + Noise IK handshake
//
// All five tests share this setup. After return, both sessions are in
// FIPS_STATE_ESTABLISHED with synchronized keys and nonces.
//
// Node A = initiator, Node B = responder.
// ═══════════════════════════════════════════════════════════════════

static bool setup_established_link(
    PairedRadio& radio_a, PairedRadio& radio_b,
    Lr2021Transport& transport_a, Lr2021Transport& transport_b,
    FipsRadioBridge& bridge_a, FipsRadioBridge& bridge_b,
    fips_session_t& sess_a, fips_session_t& sess_b)
{
    radio_a.set_peer(&radio_b);
    radio_b.set_peer(&radio_a);

    if (transport_a.init(Lr2021Config{}) != TransportError::Ok) return false;
    if (transport_b.init(Lr2021Config{}) != TransportError::Ok) return false;

    // Generate keypairs
    uint8_t priv_a[32], pub_a[64];
    uint8_t priv_b[32], pub_b[64];
    gen_keypair(priv_a, pub_a);
    gen_keypair(priv_b, pub_b);

    uint8_t pub_b_comp[33];
    uECC_compress(pub_b, pub_b_comp, uECC_secp256k1());

    fips_init(&sess_a, priv_a, pub_b_comp);
    memset(&sess_b, 0, sizeof(sess_b));

    // MSG1: A → B
    uint8_t msg1[FIPS_MSG1_SIZE];
    size_t msg1_len = 0;
    if (fips_handshake_initiator_msg1(&sess_a, msg1, &msg1_len) != 0) return false;
    if (bridge_a.send(msg1, msg1_len) != 0) return false;

    uint8_t msg1_rx[FIPS_MSG1_SIZE + 16];
    int n1 = bridge_b.recv(msg1_rx, sizeof(msg1_rx));
    if (n1 != (int)FIPS_MSG1_SIZE) return false;

    // MSG2: B → A
    uint8_t msg2[FIPS_MSG2_SIZE];
    size_t msg2_len = 0;
    if (fips_handshake_responder_process_msg1(
            &sess_b, priv_b, msg1_rx, (size_t)n1, msg2, &msg2_len) != 0)
        return false;
    if (bridge_b.send(msg2, msg2_len) != 0) return false;

    uint8_t msg2_rx[FIPS_MSG2_SIZE + 16];
    int n2 = bridge_a.recv(msg2_rx, sizeof(msg2_rx));
    if (n2 != (int)FIPS_MSG2_SIZE) return false;

    if (fips_handshake_initiator_process_msg2(&sess_a, msg2_rx, (size_t)n2) != 0)
        return false;

    return sess_a.state == FIPS_STATE_ESTABLISHED &&
           sess_b.state == FIPS_STATE_ESTABLISHED;
}

// ═══════════════════════════════════════════════════════════════════
// fragmented_transfer — send a payload as multiple encrypted FIPS frames
//
// This is the core Phase 3 data path:
//
//   For each 190-byte chunk of the payload:
//     1. fips_encrypt(chunk) → ciphertext (≤222 bytes)
//     2. bridge_tx.send(ciphertext) → one LR2021 radio packet
//     3. bridge_rx.recv() → receive the ciphertext
//     4. fips_decrypt(ciphertext) → plaintext chunk
//     5. Append plaintext to output buffer
//
// The send/recv is interleaved (one frame at a time) to model a
// half-duplex radio link and avoid RX framer overflow (510-byte cap).
//
// Both sessions' nonces stay synchronized: encrypt and decrypt both
// increment the nonce in lockstep, so A→B then B→A works correctly.
//
// Returns number of frames transferred, or -1 on error.
// Output buffer must be large enough for the full payload.
// ═══════════════════════════════════════════════════════════════════

static int fragmented_transfer(
    fips_session_t* sess_tx, FipsRadioBridge* bridge_tx,
    fips_session_t* sess_rx, FipsRadioBridge* bridge_rx,
    const uint8_t* payload, size_t payload_len,
    uint8_t* output, size_t* out_len)
{
    size_t offset = 0;
    size_t out_pos = 0;
    int frames = 0;

    while (offset < payload_len) {
        // a. Split into FIPS_CHUNK_SIZE (190-byte) chunks
        size_t chunk_len = payload_len - offset;
        if (chunk_len > FIPS_CHUNK_SIZE) chunk_len = FIPS_CHUNK_SIZE;

        // b. Encrypt this chunk independently
        uint8_t ct[256];
        size_t ct_len = 0;
        if (fips_encrypt(sess_tx, payload + offset, chunk_len, ct, &ct_len) != 0) {
            printf("    fips_encrypt failed at offset %zu (chunk %zu)\n", offset, chunk_len);
            return -1;
        }

        // c. Send as one LR2021 packet
        if (bridge_tx->send(ct, ct_len) != 0) {
            printf("    bridge send failed at frame %d\n", frames);
            return -1;
        }

        // d. Receive the packet
        uint8_t ct_rx[256];
        int n = bridge_rx->recv(ct_rx, sizeof(ct_rx));
        if (n <= 0) {
            printf("    bridge recv failed at frame %d (got %d)\n", frames, n);
            return -1;
        }
        if ((size_t)n != ct_len) {
            printf("    frame %d: received %d bytes, expected %zu\n", frames, n, ct_len);
            return -1;
        }

        // e. Decrypt
        uint8_t pt[256];
        size_t pt_len = 0;
        if (fips_decrypt(sess_rx, ct_rx, (size_t)n, pt, &pt_len) != 0) {
            printf("    fips_decrypt failed at frame %d\n", frames);
            return -1;
        }
        if (pt_len != chunk_len) {
            printf("    frame %d: decrypted %zu bytes, expected %zu\n",
                   frames, pt_len, chunk_len);
            return -1;
        }

        // f. Reassemble
        memcpy(output + out_pos, pt, pt_len);
        out_pos += pt_len;
        offset += chunk_len;
        frames++;
    }

    *out_len = out_pos;
    return frames;
}

// ═══════════════════════════════════════════════════════════════════
// Test 1: Small frame (100 bytes) — single FIPS frame, single packet
// ═══════════════════════════════════════════════════════════════════

TEST(test_small_100b) {
    PairedRadio radio_a, radio_b;
    Lr2021Transport transport_a(&radio_a), transport_b(&radio_b);
    FipsRadioBridge bridge_a(&transport_a), bridge_b(&transport_b);
    fips_session_t sess_a, sess_b;

    CHECK(setup_established_link(radio_a, radio_b, transport_a, transport_b,
                                  bridge_a, bridge_b, sess_a, sess_b));

    // 100-byte payload
    uint8_t payload[100];
    fill_payload(payload, sizeof(payload), 0x11);

    uint8_t output[256];
    size_t out_len = 0;
    int frames = fragmented_transfer(
        &sess_a, &bridge_a, &sess_b, &bridge_b,
        payload, sizeof(payload), output, &out_len);

    CHECK_EQ(frames, 1);
    CHECK_EQ(out_len, sizeof(payload));
    CHECK(memcmp(output, payload, sizeof(payload)) == 0);

    // Packet count: 1 handshake (MSG1) + 1 data frame = 2 total
    CHECK_EQ(radio_a.get_tx_packets().size(), (size_t)2);

    printf("    100 B → 1 frame, 1 data packet, %zu bytes received\n", out_len);
    return 1;
}

// ═══════════════════════════════════════════════════════════════════
// Test 2: Medium frame (500 bytes) — 3 FIPS frames, 3 packets
// ═══════════════════════════════════════════════════════════════════

TEST(test_medium_500b) {
    PairedRadio radio_a, radio_b;
    Lr2021Transport transport_a(&radio_a), transport_b(&radio_b);
    FipsRadioBridge bridge_a(&transport_a), bridge_b(&transport_b);
    fips_session_t sess_a, sess_b;

    CHECK(setup_established_link(radio_a, radio_b, transport_a, transport_b,
                                  bridge_a, bridge_b, sess_a, sess_b));

    uint8_t payload[500];
    fill_payload(payload, sizeof(payload), 0x22);

    uint8_t output[1024];
    size_t out_len = 0;
    int frames = fragmented_transfer(
        &sess_a, &bridge_a, &sess_b, &bridge_b,
        payload, sizeof(payload), output, &out_len);

    CHECK_EQ(frames, expected_frame_count(500));   // ceil(500/190) = 3
    CHECK_EQ(frames, 3);
    CHECK_EQ(out_len, sizeof(payload));
    CHECK(memcmp(output, payload, sizeof(payload)) == 0);

    // Packet count: 1 handshake (MSG1) + 3 data frames = 4 total
    CHECK_EQ(radio_a.get_tx_packets().size(), (size_t)4);

    printf("    500 B → %d frames, 3 data packets, %zu bytes received\n",
           frames, out_len);
    return 1;
}

// ═══════════════════════════════════════════════════════════════════
// Test 3: Large frame (1024 bytes) — 6 FIPS frames, 6 packets
//
// ceil(1024/190) = 6 frames (190×5 + 94 = 950 + 94 = 1044 ≥ 1024... wait)
// Actually: 190×5 = 950, 1024-950 = 74, so 6th chunk = 74 bytes.
// 6 frames total, each independently encrypted.
// ═══════════════════════════════════════════════════════════════════

TEST(test_large_1024b) {
    PairedRadio radio_a, radio_b;
    Lr2021Transport transport_a(&radio_a), transport_b(&radio_b);
    FipsRadioBridge bridge_a(&transport_a), bridge_b(&transport_b);
    fips_session_t sess_a, sess_b;

    CHECK(setup_established_link(radio_a, radio_b, transport_a, transport_b,
                                  bridge_a, bridge_b, sess_a, sess_b));

    uint8_t payload[1024];
    fill_payload(payload, sizeof(payload), 0x33);

    uint8_t output[2048];
    size_t out_len = 0;
    int frames = fragmented_transfer(
        &sess_a, &bridge_a, &sess_b, &bridge_b,
        payload, sizeof(payload), output, &out_len);

    CHECK_EQ(frames, expected_frame_count(1024));  // ceil(1024/190) = 6
    CHECK_EQ(frames, 6);
    CHECK_EQ(out_len, sizeof(payload));
    CHECK(memcmp(output, payload, sizeof(payload)) == 0);

    // Packet count: 1 handshake (MSG1) + 6 data frames = 7 total
    CHECK_EQ(radio_a.get_tx_packets().size(), (size_t)7);

    printf("    1024 B → %d frames, 6 data packets, %zu bytes received\n",
           frames, out_len);
    return 1;
}

// ═══════════════════════════════════════════════════════════════════
// Test 4: Exact boundary (190 bytes = FIPS_CHUNK_SIZE)
//
// 190 bytes is the maximum plaintext that fits in a single FIPS frame
// (190 + 32 overhead = 222 = FIPS_MAX_PAYLOAD). This produces a 222-byte
// ciphertext — the largest single FIPS frame that still fits in one
// 255-byte LR2021 packet.
// ═══════════════════════════════════════════════════════════════════

TEST(test_exact_boundary_190b) {
    PairedRadio radio_a, radio_b;
    Lr2021Transport transport_a(&radio_a), transport_b(&radio_b);
    FipsRadioBridge bridge_a(&transport_a), bridge_b(&transport_b);
    fips_session_t sess_a, sess_b;

    CHECK(setup_established_link(radio_a, radio_b, transport_a, transport_b,
                                  bridge_a, bridge_b, sess_a, sess_b));

    // 190 bytes = max single-frame plaintext
    uint8_t payload[FIPS_CHUNK_SIZE];
    fill_payload(payload, sizeof(payload), 0x44);

    // Encrypt manually to verify ciphertext size
    uint8_t ct[256];
    size_t ct_len = 0;
    CHECK_EQ(fips_encrypt(&sess_a, payload, FIPS_CHUNK_SIZE, ct, &ct_len), 0);
    CHECK_EQ(ct_len, (size_t)FIPS_MAX_PAYLOAD);  // 222 bytes = exact max

    // Reset — need fresh handshake since encrypt advanced the nonce.
    // Easier: just use fragmented_transfer which handles everything.
    // But we already used sess_a for one encrypt, so redo setup.
    PairedRadio radio_a2, radio_b2;
    Lr2021Transport transport_a2(&radio_a2), transport_b2(&radio_b2);
    FipsRadioBridge bridge_a2(&transport_a2), bridge_b2(&transport_b2);
    fips_session_t sess_a2, sess_b2;

    CHECK(setup_established_link(radio_a2, radio_b2, transport_a2, transport_b2,
                                  bridge_a2, bridge_b2, sess_a2, sess_b2));

    uint8_t payload2[FIPS_CHUNK_SIZE];
    fill_payload(payload2, sizeof(payload2), 0x44);

    uint8_t output[256];
    size_t out_len = 0;
    int frames = fragmented_transfer(
        &sess_a2, &bridge_a2, &sess_b2, &bridge_b2,
        payload2, sizeof(payload2), output, &out_len);

    CHECK_EQ(frames, 1);
    CHECK_EQ(out_len, FIPS_CHUNK_SIZE);
    CHECK(memcmp(output, payload2, FIPS_CHUNK_SIZE) == 0);

    // Verify the ciphertext frame was exactly FIPS_MAX_PAYLOAD (222).
    // radio_a2 has 2 TX packets: MSG1 handshake + 1 data frame.
    // The data frame (last packet) should be exactly FIPS_MAX_PAYLOAD.
    CHECK_EQ(radio_a2.get_tx_packets().size(), (size_t)2);
    CHECK_EQ(radio_a2.get_tx_packets().back().size(), (size_t)FIPS_MAX_PAYLOAD);

    printf("    190 B → 1 frame, 1 data packet (%zu bytes ct = FIPS_MAX_PAYLOAD), %zu bytes received\n",
           radio_a2.get_tx_packets().back().size(), out_len);
    return 1;
}

// ═══════════════════════════════════════════════════════════════════
// Test 5: Round-trip bidirectional
//
// Node A sends 500 B (3 frames) to Node B.
// Then Node B sends 300 B (2 frames) to Node A.
//
// Both directions use the same encrypted session. The nonce sequence
// is shared between encrypt and decrypt within each session, and both
// sessions stay synchronized:
//   A→B: nonces 0,1,2 (A encrypts, B decrypts — both advance to 3)
//   B→A: nonces 3,4   (B encrypts, A decrypts — both advance to 5)
// ═══════════════════════════════════════════════════════════════════

TEST(test_bidirectional) {
    PairedRadio radio_a, radio_b;
    Lr2021Transport transport_a(&radio_a), transport_b(&radio_b);
    FipsRadioBridge bridge_a(&transport_a), bridge_b(&transport_b);
    fips_session_t sess_a, sess_b;

    CHECK(setup_established_link(radio_a, radio_b, transport_a, transport_b,
                                  bridge_a, bridge_b, sess_a, sess_b));

    // ── A → B: 500 bytes (3 frames) ──
    uint8_t payload_ab[500];
    fill_payload(payload_ab, sizeof(payload_ab), 0x55);

    uint8_t output_ab[1024];
    size_t out_ab = 0;
    int frames_ab = fragmented_transfer(
        &sess_a, &bridge_a, &sess_b, &bridge_b,
        payload_ab, sizeof(payload_ab), output_ab, &out_ab);

    CHECK_EQ(frames_ab, 3);
    CHECK_EQ(out_ab, sizeof(payload_ab));
    CHECK(memcmp(output_ab, payload_ab, sizeof(payload_ab)) == 0);

    // ── B → A: 300 bytes (2 frames) ──
    uint8_t payload_ba[300];
    fill_payload(payload_ba, sizeof(payload_ba), 0x66);

    uint8_t output_ba[1024];
    size_t out_ba = 0;
    int frames_ba = fragmented_transfer(
        &sess_b, &bridge_b, &sess_a, &bridge_a,
        payload_ba, sizeof(payload_ba), output_ba, &out_ba);

    CHECK_EQ(frames_ba, expected_frame_count(300));  // ceil(300/190) = 2
    CHECK_EQ(frames_ba, 2);
    CHECK_EQ(out_ba, sizeof(payload_ba));
    CHECK(memcmp(output_ba, payload_ba, sizeof(payload_ba)) == 0);

    // Verify packet counts (including handshake):
    //   A sent MSG1 + 3 data frames (→B) = 4
    //   B sent MSG2 + 2 data frames (→A) = 3
    CHECK_EQ(radio_a.get_tx_packets().size(), (size_t)4);
    CHECK_EQ(radio_b.get_tx_packets().size(), (size_t)3);

    printf("    A→B: 500 B → %d frames, %zu bytes | B→A: 300 B → %d frames, %zu bytes\n",
           frames_ab, out_ab, frames_ba, out_ba);
    return 1;
}

// ═══════════════════════════════════════════════════════════════════
// Main
// ═══════════════════════════════════════════════════════════════════

int main(void) {
    printf("\n=== FIPS Fragmented Transport Tests (Phase 3) ===\n");
    printf("    FIPS_CHUNK_SIZE = %zu (max plaintext per frame)\n", FIPS_CHUNK_SIZE);
    printf("    Ciphertext max  = %zu bytes (= FIPS_MAX_PAYLOAD)\n", (size_t)FIPS_MAX_PAYLOAD);
    printf("    LR2021 max pkt  = %d bytes\n\n", LR2021_MAX_PACKET);

    printf("Single-frame tests:\n");
    RUN(test_small_100b);

    printf("\nMulti-frame tests:\n");
    RUN(test_medium_500b);
    RUN(test_large_1024b);

    printf("\nBoundary test:\n");
    RUN(test_exact_boundary_190b);

    printf("\nBidirectional test:\n");
    RUN(test_bidirectional);

    printf("\n=== Results: %d/%d passed ===\n\n", g_tests_pass, g_tests_run);
    return g_tests_pass == g_tests_run ? 0 : 1;
}
