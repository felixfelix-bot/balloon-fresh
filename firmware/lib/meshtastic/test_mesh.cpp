// TDD entry point for L4 (meshtastic transport).
//
// RED FIRST (2026-10-14): the first version of this file was committed BEFORE any
// implementation existed, and `make -C firmware/lib test` was run and failed to
// compile because none of the headers it includes existed. That observed build
// failure is the RED, and it is recorded verbatim in the commit message.
//
// The wire format reproduced here is Meshtastic's, taken from public sources
// fetched and read during this task (see REPORT.md for the exact URLs):
//   - meshtastic/firmware  src/mesh/RadioInterface.h    (16-byte PacketHeader, flag masks)
//   - meshtastic/firmware  src/mesh/Channels.{h,cpp}    (defaultpsk, PSK expansion, xor hash)
//   - meshtastic/firmware  src/mesh/CryptoEngine.cpp    (nonce construction)
//   - meshtastic/firmware  src/mesh/RadioInterface.cpp  (rebroadcast delay window)
//   - meshtastic/firmware  src/mesh/FloodingRouter.h    (flooding rules, in prose)
//   - meshtastic/meshtastic docs/development/reference/encryption-technical.mdx
//   - meshtastic/meshtastic docs/configuration/radio/{channels,lora}.mdx
//
// Everything NOT verified upstream is marked UNVERIFIED at its definition site
// and listed in REPORT.md. NO RADIO WAS INVOLVED: this is a host test against a
// fake RadioHal implementing the frozen contract in
// firmware/lib/radio_core/radio_hal.h. Nothing here is an over-the-air result.

#include "harness.h"

#include "fake_radio_hal.h"
#include "mesh_aes.h"
#include "mesh_channel.h"
#include "mesh_crypto.h"
#include "mesh_flood.h"
#include "mesh_packet.h"
#include "mesh_tlv.h"
#include "mesh_transport.h"

#include <cstring>
#include <string>
#include <vector>

using namespace balloon::meshtastic;
using balloon::radio::Modulation;
using balloon::radio::Result;

// ---------------------------------------------------------------- helpers

static std::vector<uint8_t> hexbytes(const char *hex) {
  std::vector<uint8_t> v;
  for (size_t i = 0; hex[i] && hex[i + 1]; i += 2) {
    auto nib = [](char c) -> int {
      if (c >= '0' && c <= '9') return c - '0';
      if (c >= 'a' && c <= 'f') return c - 'a' + 10;
      if (c >= 'A' && c <= 'F') return c - 'A' + 10;
      return 0;
    };
    v.push_back((uint8_t)((nib(hex[i]) << 4) | nib(hex[i + 1])));
  }
  return v;
}

static std::vector<uint8_t> bytes(const std::string &s) {
  return std::vector<uint8_t>(s.begin(), s.end());
}

static MeshPacket make_text_packet(const std::string &text) {
  MeshPacket p;
  p.to = kBroadcastNode;
  p.from = 0x0A0B0C0Du;
  p.id = 0x11223344u;
  p.set_hop_limit(kDefaultHopLimit);
  p.set_hop_start(kDefaultHopLimit);
  p.payload = bytes(text);
  return p;
}

// A fully-populated packet, used for the exact round-trip test.
static MeshPacket make_full_packet() {
  MeshPacket p;
  p.to = 0xDEADBEEFu;
  p.from = 0x00C0FFEEu;
  p.id = 0xDEAD1234u;
  p.set_hop_limit(5);
  p.set_hop_start(7);
  p.set_want_ack(true);
  p.set_via_mqtt(true);
  p.channel = 0x08;
  p.next_hop = 0x11;
  p.relay_node = 0x22;
  p.payload = bytes("hello mesh");
  p.has_position = true;
  p.position.lat_1e7 = 480123456;
  p.position.lon_1e7 = 113456789;
  p.position.alt_mm = 12345;
  p.has_telemetry = true;
  p.telemetry.battery_mv = 3987;
  p.telemetry.temp_cc = -1234;
  p.telemetry.sats = 9;
  p.telemetry.uptime_s = 65000;
  return p;
}

static ChannelConfig make_channel(const char *name, uint8_t psk_alias) {
  ChannelConfig c;
  std::strncpy(c.name, name, sizeof(c.name) - 1);
  c.psk[0] = psk_alias;
  c.psk_len = 1;
  return c;
}

/// A channel with raw key bytes, for the case that matters most: two DIFFERENT
/// keys that collide in the 8-bit channel hash, so a frame passes the hash
/// filter and must still be rejected by the cipher-level check.
static ChannelConfig make_channel_raw(const char *name, const char *hex) {
  ChannelConfig c;
  std::strncpy(c.name, name, sizeof(c.name) - 1);
  const std::vector<uint8_t> k = hexbytes(hex);
  CHECK(k.size() <= sizeof(c.psk));
  std::memcpy(c.psk, k.data(), k.size() <= sizeof(c.psk) ? k.size() : sizeof(c.psk));
  c.psk_len = k.size() <= sizeof(c.psk) ? k.size() : sizeof(c.psk);
  return c;
}

/// acquire() the radio and configure it for LoRa + continuous RX, asserting the
/// read-back. Used by every test that needs a listening receiver.
static void bring_up(MeshTransport *t, const char *what) {
  CASE(what);
  CHECK_EQ((int)t->begin(100), (int)Result::Ok);
  CHECK_EQ((int)t->apply_radio_config(906875000u, 11, 5, 22), (int)Result::Ok);
}

// ---------------------------------------------------------------- TLV codec

static void test_tlv() {
  CASE("TLV: full packet round-trips exactly");
  {
    MeshPacket in = make_full_packet();
    uint8_t buf[512];
    size_t n = 0;
    CHECK_EQ((int)tlv_encode(in, buf, sizeof(buf), &n), (int)EncodeStatus::Ok);
    CHECK(n > 0);

    MeshPacket out;
    CHECK_EQ((int)tlv_decode(buf, n, &out), (int)DecodeStatus::Ok);
    CHECK_EQ(out.to, in.to);
    CHECK_EQ(out.from, in.from);
    CHECK_EQ(out.id, in.id);
    CHECK_EQ(out.hop_limit(), in.hop_limit());
    CHECK_EQ(out.hop_start(), in.hop_start());
    CHECK_EQ(out.want_ack(), in.want_ack());
    CHECK_EQ(out.via_mqtt(), in.via_mqtt());
    CHECK_EQ(out.channel, in.channel);
    CHECK_EQ(out.next_hop, in.next_hop);
    CHECK_EQ(out.relay_node, in.relay_node);
    CHECK_EQ(out.payload.size(), in.payload.size());
    CHECK(std::memcmp(out.payload.data(), in.payload.data(), in.payload.size()) == 0);
    CHECK(out.has_position);
    CHECK_EQ(out.position.lat_1e7, in.position.lat_1e7);
    CHECK_EQ(out.position.lon_1e7, in.position.lon_1e7);
    CHECK_EQ(out.position.alt_mm, in.position.alt_mm);
    CHECK(out.has_telemetry);
    CHECK_EQ(out.telemetry.battery_mv, in.telemetry.battery_mv);
    CHECK_EQ(out.telemetry.temp_cc, in.telemetry.temp_cc);
    CHECK_EQ(out.telemetry.sats, in.telemetry.sats);
    CHECK_EQ(out.telemetry.uptime_s, in.telemetry.uptime_s);

    // Encoding is deterministic: encode(decode(encode(x))) == encode(x).
    uint8_t buf2[512];
    size_t n2 = 0;
    CHECK_EQ((int)tlv_encode(out, buf2, sizeof(buf2), &n2), (int)EncodeStatus::Ok);
    CHECK_EQ(n, n2);
    CHECK(std::memcmp(buf, buf2, n) == 0);
  }

  CASE("TLV: a payload longer than one record round-trips (payload is split)");
  {
    MeshPacket in = make_text_packet(std::string(150, 'Q'));  // 150 > kTlvMaxValueLen
    uint8_t buf[512];
    size_t n = 0;
    CHECK_EQ((int)tlv_encode(in, buf, sizeof(buf), &n), (int)EncodeStatus::Ok);
    MeshPacket out;
    CHECK_EQ((int)tlv_decode(buf, n, &out), (int)DecodeStatus::Ok);
    CHECK_EQ(out.payload.size(), 150u);
    CHECK(std::memcmp(out.payload.data(), in.payload.data(), 150) == 0);
  }

  CASE("TLV rule R1: unknown field id AND unknown wire type are SKIPPED");
  {
    // Build a valid packet, then splice in two foreign records:
    //   id 0xFA type 0x7F (both unknown) len 3 value 01 02 03   -> must be skipped
    //   id 0xFB type U8   (unknown id)     len 1 value 0x99     -> must be skipped
    MeshPacket in = make_text_packet("survives");
    uint8_t buf[512];
    size_t n = 0;
    CHECK_EQ((int)tlv_encode(in, buf, sizeof(buf), &n), (int)EncodeStatus::Ok);

    std::vector<uint8_t> spliced;
    uint8_t foreign1[] = {0xFA, 0x7F, 0x03, 0x01, 0x02, 0x03};
    uint8_t foreign2[] = {0xFB, (uint8_t)FieldType::U8, 0x01, 0x99};
    spliced.insert(spliced.end(), foreign1, foreign1 + sizeof(foreign1));
    spliced.insert(spliced.end(), buf, buf + n);
    spliced.insert(spliced.end(), foreign2, foreign2 + sizeof(foreign2));

    MeshPacket out;
    CHECK_EQ((int)tlv_decode(spliced.data(), spliced.size(), &out),
             (int)DecodeStatus::Ok);
    CHECK_EQ(out.id, in.id);
    CHECK_EQ(out.from, in.from);
    CHECK_EQ(out.payload.size(), in.payload.size());
    CHECK(std::memcmp(out.payload.data(), in.payload.data(), in.payload.size()) == 0);

    // Counter-test for the skip rule: an unknown record whose declared length
    // runs past the end of the buffer must NOT be silently skipped - skipping is
    // only safe when the length really is inside the buffer, otherwise the skip
    // desynchronises the stream.
    //
    // The declared length is 32, which is <= kTlvMaxValueLen (64) so it is not
    // rejected by the oversize rule; it is the AVAILABILITY check that must
    // catch it. Using a length above 64 here would pass this assertion while
    // proving the wrong rule.
    uint8_t overrun[] = {0xFA, 0x7F, 0x20, 0x01, 0x02, 0x03};  // claims 32, has 3
    MeshPacket out2;
    CHECK_EQ((int)tlv_decode(overrun, sizeof(overrun), &out2),
             (int)DecodeStatus::Truncated);
  }

  CASE("TLV rules R2/R3/R4/R5: oversize, truncation, id 0, duplicate -> REJECT");
  {
    MeshPacket in = make_text_packet("x");
    uint8_t buf[512];
    size_t n = 0;
    CHECK_EQ((int)tlv_encode(in, buf, sizeof(buf), &n), (int)EncodeStatus::Ok);

    // R2: a field whose declared length exceeds kTlvMaxValueLen (64). This is
    // checked BEFORE availability, so a huge declared length cannot make the
    // decoder walk off the buffer.
    std::vector<uint8_t> big;
    big.push_back((uint8_t)FieldId::Payload);
    big.push_back((uint8_t)FieldType::Bytes);
    big.push_back(65);  // 65 > 64
    for (int i = 0; i < 65; ++i) big.push_back((uint8_t)i);
    MeshPacket o;
    CHECK_EQ((int)tlv_decode(big.data(), big.size(), &o), (int)DecodeStatus::Oversized);

    // R3: truncated trailing record.
    MeshPacket o2;
    CHECK_EQ((int)tlv_decode(buf, n - 1, &o2), (int)DecodeStatus::Truncated);

    // R3 again: a header that does not fit.
    MeshPacket o2b;
    CHECK_EQ((int)tlv_decode(buf, 2, &o2b), (int)DecodeStatus::Truncated);

    // R4: field id 0 is reserved and invalid.
    uint8_t zero_id[] = {0x00, (uint8_t)FieldType::U8, 0x01, 0x00};
    MeshPacket o3;
    CHECK_EQ((int)tlv_decode(zero_id, sizeof(zero_id), &o3), (int)DecodeStatus::Malformed);

    // R5: the same fixed-size field twice.
    uint8_t dup[512];
    size_t dn = 0;
    CHECK_EQ((int)tlv_encode(in, dup, sizeof(dup), &dn), (int)EncodeStatus::Ok);
    std::vector<uint8_t> dupvet(dup, dup + dn);
    for (size_t i = 0; i < n; ++i) dupvet.push_back(dup[i]);
    MeshPacket o4;
    CHECK_EQ((int)tlv_decode(dupvet.data(), dupvet.size(), &o4),
             (int)DecodeStatus::Duplicate);

    // A known field carrying the WRONG type is a schema violation, not a
    // forward-compatibility case: reject rather than silently skip, because
    // silently skipping a `To` field would turn a unicast into a broadcast.
    uint8_t wrong_type[] = {(uint8_t)FieldId::To, (uint8_t)FieldType::Bytes, 0x04,
                            0x00, 0x00, 0x00, 0x00};
    MeshPacket o5;
    CHECK_EQ((int)tlv_decode(wrong_type, sizeof(wrong_type), &o5),
             (int)DecodeStatus::Malformed);

    // A mandatory field missing entirely is rejected, not defaulted.
    uint8_t only_to[] = {(uint8_t)FieldId::To, (uint8_t)FieldType::U32, 0x04,
                         0x01, 0x00, 0x00, 0x00};
    MeshPacket o6;
    CHECK_EQ((int)tlv_decode(only_to, sizeof(only_to), &o6),
             (int)DecodeStatus::Malformed);

    // R6: an unrepresentable value is refused on encode. A payload beyond the
    // 255-byte frame budget cannot be expressed at all.
    MeshPacket bad = make_text_packet(std::string(kMaxPayloadLen + 1, 'z'));
    uint8_t b2[512];
    size_t b2n = 0;
    CHECK_EQ((int)tlv_encode(bad, b2, sizeof(b2), &b2n), (int)EncodeStatus::BadValue);
  }

  CASE("TLV rule R7: a short output buffer is refused, nothing is emitted");
  {
    MeshPacket in = make_full_packet();
    uint8_t tiny[4];
    size_t n = 12345;  // deliberately poisoned: encode must not touch it on failure
    CHECK_EQ((int)tlv_encode(in, tiny, sizeof(tiny), &n), (int)EncodeStatus::NoSpace);
    CHECK_EQ(n, 12345u);

    // The worst-case sizer must agree with an actual encode, or a caller sizing
    // a TX buffer from it would be wrong.
    uint8_t full[512];
    size_t fn = 0;
    CHECK_EQ((int)tlv_encode(in, full, sizeof(full), &fn), (int)EncodeStatus::Ok);
    CHECK_EQ(fn, tlv_worst_case_size(in));
  }
}

// ---------------------------------------------------------------- channel

static void test_channel() {
  CASE("channel: the published default PSK alias 1 expands to the 16-byte default key");
  {
    CryptoKey k;
    uint8_t alias = 1;
    CHECK_EQ((int)expand_psk(&alias, 1, &k), (int)PskStatus::Ok);
    // Upstream src/mesh/Channels.h:
    //   defaultpsk = d4 f1 bb 3a 20 29 07 59 f0 bc ff ab cf 4e 69 01
    CHECK_EQ(k.length, 16u);
    const uint8_t want[] = {0xd4, 0xf1, 0xbb, 0x3a, 0x20, 0x29, 0x07, 0x59,
                            0xf0, 0xbc, 0xff, 0xab, 0xcf, 0x4e, 0x69, 0x01};
    CHECK(std::memcmp(k.bytes, want, 16) == 0);
    // The remaining 16 bytes of the 32-byte buffer must be zero padding and the
    // EFFECTIVE length must stay 16 => AES-128, not AES-256. Conflating the
    // buffer size with the key size is the classic way to silently break
    // interoperability with a default channel.
    for (size_t i = 16; i < 32; ++i) CHECK_EQ(k.bytes[i], 0);
    CHECK_EQ(aes_bits_for(k), 128);
  }

  CASE("channel: alias 0 disables encryption, aliases 2..255 bump the last byte");
  {
    CryptoKey k;
    uint8_t zero = 0;
    CHECK_EQ((int)expand_psk(&zero, 1, &k), (int)PskStatus::Disabled);
    CHECK_EQ(k.length, 0u);
    CHECK_EQ(aes_bits_for(k), 0);

    uint8_t a2 = 2;
    CHECK_EQ((int)expand_psk(&a2, 1, &k), (int)PskStatus::Ok);
    CHECK_EQ(k.length, 16u);
    CHECK_EQ(k.bytes[15], 0x02);  // 0x01 + 2 - 1
    CHECK_EQ(k.bytes[0], 0xd4);

    uint8_t a3 = 3;
    CHECK_EQ((int)expand_psk(&a3, 1, &k), (int)PskStatus::Ok);
    CHECK_EQ(k.bytes[15], 0x03);
    CHECK_EQ(k.bytes[0], 0xd4);
    CHECK_EQ(k.bytes[14], 0x69);  // only the LAST byte moves

    uint8_t a255 = 255;
    CHECK_EQ((int)expand_psk(&a255, 1, &k), (int)PskStatus::Ok);
    CHECK_EQ(k.bytes[15], 0xff);
    CHECK_EQ(k.bytes[0], 0xd4);
  }

  CASE("channel: 16-byte PSK is AES-128, 32-byte PSK is AES-256, short PSK pads");
  {
    std::vector<uint8_t> k16 = hexbytes("000102030405060708090a0b0c0d0e0f");
    CryptoKey k;
    CHECK_EQ((int)expand_psk(k16.data(), 16, &k), (int)PskStatus::Ok);
    CHECK_EQ(k.length, 16u);
    CHECK_EQ(aes_bits_for(k), 128);

    std::vector<uint8_t> k32 =
        hexbytes("000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f");
    CHECK_EQ((int)expand_psk(k32.data(), 32, &k), (int)PskStatus::Ok);
    CHECK_EQ(k.length, 32u);
    CHECK_EQ(aes_bits_for(k), 256);
    CHECK_EQ(k.bytes[31], 0x1f);

    // <16 bytes: zero-padded to 16. Upstream: "User provided a too short AES128
    // key - padding".
    std::vector<uint8_t> short8 = hexbytes("0102030405060708");
    CHECK_EQ((int)expand_psk(short8.data(), 8, &k), (int)PskStatus::Ok);
    CHECK_EQ(k.length, 16u);
    CHECK_EQ(k.bytes[7], 0x08);
    for (size_t i = 8; i < 16; ++i) CHECK_EQ(k.bytes[i], 0);

    // 17..31 bytes: zero-padded to 32.
    std::vector<uint8_t> k20 = hexbytes("0102030405060708090a0b0c0d0e0f1011121314");
    CHECK_EQ((int)expand_psk(k20.data(), 20, &k), (int)PskStatus::Ok);
    CHECK_EQ(k.length, 32u);
    CHECK_EQ(k.bytes[19], 0x14);
    for (size_t i = 20; i < 32; ++i) CHECK_EQ(k.bytes[i], 0);

    // Nothing longer than AES-256 is representable.
    std::vector<uint8_t> k40(40, 0xAA);
    CHECK_EQ((int)expand_psk(k40.data(), 40, &k), (int)PskStatus::BadArgument);
  }

  CASE("channel hash: XOR of the name bytes with the XOR of the key bytes");
  {
    // docs/development/reference/encryption-technical.mdx:
    // "The one-byte channel hash in the packet header is the XOR of the channel
    //  name's bytes with the XOR of the key's bytes."
    //
    // Independently computed constants (python3, see REPORT.md):
    //   xor("LongFast")   = 0x0a
    //   xor(defaultpsk)   = 0x02   => hash = 0x08
    //   xor(eventpsk)     = 0xc8   => hash = 0xc2
    CryptoKey k;
    uint8_t alias = 1;
    CHECK_EQ((int)expand_psk(&alias, 1, &k), (int)PskStatus::Ok);
    CHECK_EQ(channel_hash("LongFast", k), 0x08);
    CHECK(channel_hash("MyChannel", k) != channel_hash("LongFast", k));

    CryptoKey ke;
    std::vector<uint8_t> ev =
        hexbytes("384bbcc01dc022d181bf36b86121e1fb96b72e55bf74227e9d6afb48d64cb1a1");
    CHECK_EQ((int)expand_psk(ev.data(), 32, &ke), (int)PskStatus::Ok);
    CHECK_EQ(channel_hash("LongFast", ke), 0xc2);

    // A 16-byte key and its 32-byte zero-padded twin have the SAME xor, so they
    // hash identically - which is correct, because they are different AES
    // variants of the same key material.
    CryptoKey k16b;
    std::vector<uint8_t> raw16 = hexbytes("000102030405060708090a0b0c0d0e0f");
    CHECK_EQ((int)expand_psk(raw16.data(), 16, &k16b), (int)PskStatus::Ok);
    CHECK_EQ(channel_hash("LongFast", k16b),
             (uint8_t)(0x0a ^ 0x00 ^ 0x01 ^ 0x02 ^ 0x03 ^ 0x04 ^ 0x05 ^ 0x06 ^
                       0x07 ^ 0x08 ^ 0x09 ^ 0x0a ^ 0x0b ^ 0x0c ^ 0x0d ^ 0x0e ^ 0x0f));

    // COUNTER-TEST: the hash is deliberately weak (8 bits). Two distinct keys
    // with the same byte-XOR collide - prove that, so nobody mistakes it for a
    // MAC. This is the documented reason a wrong-key packet can pass the filter.
    CryptoKey c1, c2;
    std::vector<uint8_t> x1 = hexbytes("0102030405060708090a0b0c0d0e0f10");
    std::vector<uint8_t> x2 = hexbytes("1002030405060708090a0b0c0d0e0f01");
    CHECK_EQ((int)expand_psk(x1.data(), 16, &c1), (int)PskStatus::Ok);
    CHECK_EQ((int)expand_psk(x2.data(), 16, &c2), (int)PskStatus::Ok);
    CHECK(std::memcmp(c1.bytes, c2.bytes, 16) != 0);  // different keys
    CHECK(channel_hash("LongFast", c1) == channel_hash("LongFast", c2));
  }
}

// ---------------------------------------------------------------- crypto

static void test_crypto() {
  CASE("AES KAT: FIPS-197 C.1 (AES-128) and C.3 (AES-256) single blocks");
  {
    // Vectors printed in FIPS-197 itself, so they anchor the block cipher and
    // the GENERATED S-box independently of anything in this repo.
    std::vector<uint8_t> pt = hexbytes("00112233445566778899aabbccddeeff");

    std::vector<uint8_t> k128 = hexbytes("000102030405060708090a0b0c0d0e0f");
    std::vector<uint8_t> want128 = hexbytes("69c4e0d86a7b0430d8cdb78070b4c55a");
    AesKey ak{};
    CHECK(aes_set_key(&ak, k128.data(), 16));
    CHECK_EQ(ak.rounds, 10);
    uint8_t out[16];
    aes_encrypt_block(ak, pt.data(), out);
    CHECK(std::memcmp(out, want128.data(), 16) == 0);

    std::vector<uint8_t> k256 =
        hexbytes("000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f");
    std::vector<uint8_t> want256 = hexbytes("8ea2b7ca516745bfeafc49904b496089");
    CHECK(aes_set_key(&ak, k256.data(), 32));
    CHECK_EQ(ak.rounds, 14);
    aes_encrypt_block(ak, pt.data(), out);
    CHECK(std::memcmp(out, want256.data(), 16) == 0);

    // The S-box is GENERATED from the GF(2^8) definition, not typed in as a
    // table: a hand-copied table is unverifiable. Spot-check published values.
    const uint8_t *sb = aes_sbox();
    CHECK_EQ(sb[0x00], 0x63);
    CHECK_EQ(sb[0x01], 0x7c);
    CHECK_EQ(sb[0x53], 0xed);
    CHECK_EQ(sb[0xff], 0x16);
    // The S-box must be a permutation: 256 distinct outputs.
    {
      bool used[256] = {};
      bool perm = true;
      for (int i = 0; i < 256; ++i) {
        if (used[sb[i]]) perm = false;
        used[sb[i]] = true;
      }
      CHECK(perm);
    }

    // A key length that is neither 16 nor 32 is refused.
    CHECK(!aes_set_key(&ak, k128.data(), 20));
    CHECK(!aes_set_key(&ak, k128.data(), 0));
  }

  CASE("AES-CTR KAT: an independent OpenSSL vector over 200 bytes (13 blocks)");
  {
    // Generated OUTSIDE this codebase with
    //   openssl enc -aes-256-ctr -K <key> -iv <counter block>
    // and cross-checked against python-cryptography's AES-CTR (see REPORT.md and
    // scripts/gen_aes_ctr_kat.py). The counter block is exactly what
    // build_nonce() produces for packet id 0x11223344 from node 0x0a0b0c0d:
    //   bytes 0-7  = LE64(0x11223344)  = 44 33 22 11 00 00 00 00
    //   bytes 8-11 = LE32(0x0a0b0c0d)  = 0d 0c 0b 0a
    //   bytes 12-15= block counter 0  = 00 00 00 00
    std::vector<uint8_t> key =
        hexbytes("000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f");
    std::vector<uint8_t> nonce = hexbytes("44332211000000000d0c0b0a00000000");
    CHECK_EQ(nonce.size(), 16u);

    // build_nonce must agree with that hand-written counter block.
    uint8_t built[16];
    build_nonce(0x11223344u, 0x0a0b0c0du, built);
    CHECK(std::memcmp(built, nonce.data(), 16) == 0);

    std::vector<uint8_t> want = hexbytes(
        "0e6bbaabd915b7032f2e90ab62718fdf125f0ee781654c4442879f0ed4a7b661"
        "d96fa8ce6eddcc351d8e63b74d280183f8f217f3327a911d6abede5c2ee68359"
        "be19a89c544f2c5c3e5b8ba3b917e815b4725e1ccbb2b6322366471d16176ade"
        "108fa9d32087c72796a1915f067627e3d702b575ebe42d3f4c5d00cdee62b4e5"
        "d10772c1ae43fc7ea655fdf149cb14e93490fef4e1f7ca4d988cdef85771d640"
        "a19d6ac1dafe7ca13ca3568e819d1ff71bdfe2ef93d1c28645e44549aef24bae"
        "c30f6e95a2a38579");
    CHECK_EQ(want.size(), 200u);
    std::vector<uint8_t> pt(200);
    for (size_t i = 0; i < pt.size(); ++i) pt[i] = (uint8_t)i;

    AesCtr c{};
    CHECK(aes_ctr_init(&c, key.data(), key.size(), nonce.data()));
    std::vector<uint8_t> buf = pt;
    aes_ctr_xor(&c, buf.data(), buf.size());
    CHECK(std::memcmp(buf.data(), want.data(), buf.size()) == 0);

    // Decrypt is the same operation.
    AesCtr d{};
    CHECK(aes_ctr_init(&d, key.data(), key.size(), nonce.data()));
    aes_ctr_xor(&d, buf.data(), buf.size());
    CHECK(std::memcmp(buf.data(), pt.data(), pt.size()) == 0);

    // The keystream is position-independent: processing the same bytes in two
    // chunks must give the same result as one call. A CTR implementation that
    // reset its counter per call would pass a single-shot test and fail here.
    AesCtr s{};
    CHECK(aes_ctr_init(&s, key.data(), key.size(), nonce.data()));
    std::vector<uint8_t> split = pt;
    aes_ctr_xor(&s, split.data(), 7);
    aes_ctr_xor(&s, split.data() + 7, 100);
    aes_ctr_xor(&s, split.data() + 107, 93);
    CHECK(std::memcmp(split.data(), want.data(), 200) == 0);

    // A bad key length is refused rather than silently used.
    AesCtr bad{};
    CHECK(!aes_ctr_init(&bad, key.data(), 20, nonce.data()));
    CHECK(!aes_ctr_init(&bad, nullptr, 16, nonce.data()));
  }

  CASE("CRC32: the published IEEE check value and a known string");
  {
    // CRC-32/ISO-HDLC check value: crc32("123456789") == 0xCBF43926.
    const uint8_t *s = (const uint8_t *)"123456789";
    CHECK_EQ(crc32_ieee(s, 9), 0xCBF43926u);
    CHECK_EQ(crc32_ieee(s, 0), 0x00000000u);
    // A single flipped bit must change the CRC (obviously) - this is what makes
    // the trailer useful at all.
    uint8_t a[4] = {1, 2, 3, 4};
    uint8_t b[4] = {1, 2, 3, 5};
    CHECK(crc32_ieee(a, 4) != crc32_ieee(b, 4));
  }

  CASE("sealed payload: round trip is bit-exact, a wrong key is DETECTED not accepted");
  {
    CryptoKey k;
    uint8_t alias = 1;
    CHECK_EQ((int)expand_psk(&alias, 1, &k), (int)PskStatus::Ok);

    const std::string msg = "PICO BALLOON TELEMETRY FRAME 0123456789";
    std::vector<uint8_t> plain = bytes(msg);
    std::vector<uint8_t> sealed;
    CHECK_EQ((int)seal_payload(k, 0x11223344u, 0x0a0b0c0du, plain.data(),
                               plain.size(), &sealed),
             (int)SealStatus::Ok);
    // AES-CTR adds no bytes; the 4-byte CRC trailer is OURS (see mesh_crypto.h:
    // upstream AES-CTR has no integrity check at all).
    CHECK_EQ(sealed.size(), plain.size() + kSealTrailerLen);
    // The ciphertext must not contain the plaintext: a seal that returned the
    // input unchanged would round-trip and still be worthless.
    CHECK(std::memcmp(sealed.data(), plain.data(), plain.size()) != 0);

    std::vector<uint8_t> opened;
    CHECK_EQ((int)open_payload(k, 0x11223344u, 0x0a0b0c0du, sealed.data(),
                               sealed.size(), &opened),
             (int)SealStatus::Ok);
    CHECK_EQ(opened.size(), plain.size());
    CHECK(std::memcmp(opened.data(), plain.data(), plain.size()) == 0);

    // COUNTER-TEST 1: wrong key -> garbage -> must be REPORTED, and no plaintext
    // may be produced.
    CryptoKey wrong;
    uint8_t a2 = 2;
    CHECK_EQ((int)expand_psk(&a2, 1, &wrong), (int)PskStatus::Ok);
    std::vector<uint8_t> garbage = {0xAA};
    CHECK_EQ((int)open_payload(wrong, 0x11223344u, 0x0a0b0c0du, sealed.data(),
                               sealed.size(), &garbage),
             (int)SealStatus::IntegrityFailure);
    CHECK_EQ(garbage.size(), 0u);

    // COUNTER-TEST 2: right key, wrong packet id -> wrong counter block.
    CHECK_EQ((int)open_payload(k, 0x11223345u, 0x0a0b0c0du, sealed.data(),
                               sealed.size(), &garbage),
             (int)SealStatus::IntegrityFailure);

    // COUNTER-TEST 3: right key, wrong sender.
    CHECK_EQ((int)open_payload(k, 0x11223344u, 0x0a0b0c0eu, sealed.data(),
                               sealed.size(), &garbage),
             (int)SealStatus::IntegrityFailure);

    // COUNTER-TEST 4: one flipped ciphertext bit -> caught. This is the property
    // plain AES-CTR does NOT have on its own.
    std::vector<uint8_t> bitflip = sealed;
    bitflip[7] ^= 0x01;
    CHECK_EQ((int)open_payload(k, 0x11223344u, 0x0a0b0c0du, bitflip.data(),
                               bitflip.size(), &garbage),
             (int)SealStatus::IntegrityFailure);

    // COUNTER-TEST 5: a flipped TRAILER byte -> also caught.
    std::vector<uint8_t> badcrc = sealed;
    badcrc[sealed.size() - 1] ^= 0x80;
    CHECK_EQ((int)open_payload(k, 0x11223344u, 0x0a0b0c0du, badcrc.data(),
                               badcrc.size(), &garbage),
             (int)SealStatus::IntegrityFailure);

    // COUNTER-TEST 6: a container shorter than the trailer is refused.
    CHECK_EQ((int)open_payload(k, 0x11223344u, 0x0a0b0c0du, sealed.data(), 3,
                               &garbage),
             (int)SealStatus::TooShort);

    // A disabled key is a passthrough (upstream: 0-length PSK == no crypto) and
    // adds no trailer.
    CryptoKey none;
    uint8_t z = 0;
    CHECK_EQ((int)expand_psk(&z, 1, &none), (int)PskStatus::Disabled);
    std::vector<uint8_t> passthrough;
    CHECK_EQ((int)seal_payload(none, 1, 2, plain.data(), plain.size(),
                               &passthrough),
             (int)SealStatus::Ok);
    CHECK_EQ(passthrough.size(), plain.size());
    CHECK(std::memcmp(passthrough.data(), plain.data(), plain.size()) == 0);
  }

  CASE("sealed payload: the same plaintext seals differently for different nonces");
  {
    CryptoKey k;
    uint8_t alias = 1;
    CHECK_EQ((int)expand_psk(&alias, 1, &k), (int)PskStatus::Ok);
    std::vector<uint8_t> plain = bytes("same plaintext");

    std::vector<uint8_t> s1, s2, s3;
    CHECK_EQ((int)seal_payload(k, 1, 0xAA, plain.data(), plain.size(), &s1),
             (int)SealStatus::Ok);
    CHECK_EQ((int)seal_payload(k, 2, 0xAA, plain.data(), plain.size(), &s2),
             (int)SealStatus::Ok);
    CHECK_EQ((int)seal_payload(k, 1, 0xBB, plain.data(), plain.size(), &s3),
             (int)SealStatus::Ok);
    CHECK(std::memcmp(s1.data(), s2.data(), s1.size()) != 0);
    CHECK(std::memcmp(s1.data(), s3.data(), s1.size()) != 0);

    // ...and each still opens only with its own nonce.
    std::vector<uint8_t> o;
    CHECK_EQ((int)open_payload(k, 1, 0xAA, s1.data(), s1.size(), &o),
             (int)SealStatus::Ok);
    CHECK_EQ((int)open_payload(k, 2, 0xAA, s1.data(), s1.size(), &o),
             (int)SealStatus::IntegrityFailure);
  }
}

// ---------------------------------------------------------------- header

static void test_header() {
  CASE("header: 16-byte wire layout, flags packing, exact round trip");
  {
    CHECK_EQ(kHeaderLength, 16u);
    MeshPacket in = make_full_packet();
    uint8_t hdr[kHeaderLength];
    encode_header(in, hdr);

    // Little-endian 32-bit fields, in upstream struct PacketHeader order:
    //   NodeNum to, from; PacketId id; uint8_t flags, channel, next_hop, relay_node;
    CHECK_EQ(hdr[0], 0xEF);
    CHECK_EQ(hdr[1], 0xBE);
    CHECK_EQ(hdr[2], 0xAD);
    CHECK_EQ(hdr[3], 0xDE);
    CHECK_EQ(hdr[4], 0xEE);
    CHECK_EQ(hdr[5], 0xFF);
    CHECK_EQ(hdr[6], 0xC0);
    CHECK_EQ(hdr[7], 0x00);
    CHECK_EQ(hdr[8], 0x34);
    CHECK_EQ(hdr[9], 0x12);
    CHECK_EQ(hdr[10], 0xAD);
    CHECK_EQ(hdr[11], 0xDE);
    // flags: hop_limit 5 | want_ack | via_mqtt | hop_start 7 << 5
    CHECK_EQ(hdr[12], (uint8_t)((5 & kFlagHopLimitMask) | kFlagWantAckMask |
                                kFlagViaMqttMask |
                                ((7 << kFlagHopStartShift) & kFlagHopStartMask)));
    CHECK_EQ(hdr[13], 0x08);
    CHECK_EQ(hdr[14], 0x11);
    CHECK_EQ(hdr[15], 0x22);

    MeshPacket out;
    CHECK_EQ((int)decode_header(hdr, kHeaderLength, &out), (int)DecodeStatus::Ok);
    CHECK_EQ(out.to, in.to);
    CHECK_EQ(out.from, in.from);
    CHECK_EQ(out.id, in.id);
    CHECK_EQ(out.hop_limit(), 5);
    CHECK_EQ(out.hop_start(), 7);
    CHECK_EQ(out.want_ack(), true);
    CHECK_EQ(out.via_mqtt(), true);
    CHECK_EQ(out.channel, 0x08);
    CHECK_EQ(out.next_hop, 0x11);
    CHECK_EQ(out.relay_node, 0x22);

    // A too-short buffer must be refused.
    MeshPacket o2;
    CHECK_EQ((int)decode_header(hdr, kHeaderLength - 1, &o2),
             (int)DecodeStatus::Truncated);
  }

  CASE("header: hop fields are 3 bits and never spill into the flags beside them");
  {
    // docs/configuration/radio/lora.mdx: "Maximum number of hops. This can't be
    // greater than 7. Default is 3 which should be fine for most applications."
    CHECK_EQ((int)kDefaultHopLimit, 3);
    CHECK_EQ((int)kMaxHopLimit, 7);

    MeshPacket p;
    p.set_hop_limit(0);
    CHECK_EQ(p.hop_limit(), 0);
    p.set_hop_start(7);
    CHECK_EQ(p.hop_start(), 7);
    p.set_hop_limit(kMaxHopLimit);
    CHECK_EQ(p.hop_limit(), 7);
    CHECK_EQ(p.hop_start(), 7);
    p.set_hop_limit(0);
    CHECK_EQ(p.hop_start(), 7);  // hop_start is untouched by a hop_limit write

    // set_hop_limit CLAMPS at 7 rather than wrapping into want_ack: an
    // overflowing hop limit that flips want_ack is a silent, nasty bug.
    MeshPacket q;
    q.set_hop_limit(9);
    CHECK_EQ(q.hop_limit(), 7);
    CHECK_EQ(q.want_ack(), false);

    // The same for the flags beside it.
    MeshPacket r;
    r.set_hop_limit(3);
    r.set_want_ack(true);
    r.set_via_mqtt(true);
    r.set_hop_start(6);
    CHECK_EQ(r.flags, (uint8_t)(3 | kFlagWantAckMask | kFlagViaMqttMask |
                                (6 << kFlagHopStartShift)));
    r.set_want_ack(false);
    CHECK_EQ(r.hop_limit(), 3);
    CHECK_EQ(r.hop_start(), 6);
    CHECK_EQ(r.via_mqtt(), true);
  }
}

// ---------------------------------------------------------------- flood

static void test_flood() {
  CASE("flood: rebroadcast only while hop limit remains, and decrement on relay");
  {
    MeshPacket p = make_text_packet("flood");
    p.set_hop_limit(3);
    p.set_hop_start(3);

    CHECK(should_rebroadcast(p, /*from_us=*/false));
    CHECK(!should_rebroadcast(p, /*from_us=*/true));  // never re-flood our own tx

    MeshPacket f = rebroadcast_copy(p);
    CHECK_EQ(f.hop_limit(), 2);
    CHECK_EQ(f.hop_start(), 3);  // hop_start records the ORIGINAL budget
    CHECK_EQ(f.id, p.id);
    CHECK_EQ(f.from, p.from);  // relays keep the original sender

    // Walk the budget down: the last hop is not rebroadcastable again.
    p.set_hop_limit(1);
    MeshPacket f1 = rebroadcast_copy(p);
    CHECK_EQ(f1.hop_limit(), 0);
    CHECK(!should_rebroadcast(f1, false));

    p.set_hop_limit(0);
    CHECK(!should_rebroadcast(p, false));
    MeshPacket f0 = rebroadcast_copy(p);
    CHECK_EQ(f0.hop_limit(), 0);  // no underflow

    // The documented "simple broadcast (0 hops)" case: id == 0 is never relayed.
    MeshPacket simple = make_text_packet("simple");
    simple.id = 0;
    CHECK(!should_rebroadcast(simple, false));
  }

  CASE("flood: hops_away derives from hop_start - hop_limit");
  {
    MeshPacket p = make_text_packet("hops");
    p.set_hop_limit(5);
    p.set_hop_start(5);
    CHECK_EQ(hops_away(p), 0);
    MeshPacket r1 = rebroadcast_copy(p);
    CHECK_EQ(hops_away(r1), 1);
    MeshPacket r2 = rebroadcast_copy(r1);
    CHECK_EQ(hops_away(r2), 2);
    // A packet whose fields are inconsistent must not report a negative distance.
    MeshPacket weird = p;
    weird.set_hop_limit(7);
    weird.set_hop_start(2);
    CHECK_EQ(hops_away(weird), 0);
  }

  CASE("flood: rebroadcast delay is DETERMINISTIC under injected randomness");
  {
    // The randomness is injectable precisely so this test can assert an exact
    // number instead of "somewhere in a range".
    FloodPolicy pol;
    CHECK_EQ(pol.slot_time_ms, 1000u);  // UNVERIFIED default, see mesh_flood.h
    CHECK_EQ((int)pol.cw_min, 3);       // upstream CWmin
    CHECK_EQ((int)pol.cw_max, 8);       // upstream CWmax

    // SNR -> CWsize is map(snr, -20, 10, 3, 8), the upstream getCWsize().
    CHECK_EQ((int)cw_size_for_snr(-20), 3);
    CHECK_EQ((int)cw_size_for_snr(-10), 4);
    CHECK_EQ((int)cw_size_for_snr(0), 6);
    CHECK_EQ((int)cw_size_for_snr(10), 8);
    CHECK_EQ((int)cw_size_for_snr(999), 8);   // clamped, not undefined
    CHECK_EQ((int)cw_size_for_snr(-999), 3);  // clamped
    CHECK_EQ(cw_slots(3), 8u);
    CHECK_EQ(cw_slots(8), 256u);

    // CLIENT (not ROUTER): delay = 2*CWmax*slot + random(0, 1<<CWsize)*slot
    ScriptedRandom rng({5, 6, 7});
    CHECK_EQ(rebroadcast_delay_ms(pol, /*snr=*/10, /*is_router=*/false, &rng),
             16000u + 5u * 1000u);
    CHECK_EQ(rebroadcast_delay_ms(pol, /*snr=*/10, /*is_router=*/false, &rng),
             16000u + 6u * 1000u);
    // Different SNR -> different CWsize -> different window.
    CHECK_EQ(rebroadcast_delay_ms(pol, /*snr=*/0, /*is_router=*/false, &rng),
             16000u + 7u * 1000u);
    CHECK_EQ(rng.draws(), 3u);

    // ROUTER: delay = random(0, 2*CWsize)*slot (no CWmax offset), so a router
    // always goes before a client. That ordering is the whole point of the
    // offset and is asserted here rather than assumed.
    ScriptedRandom rng2({0, 11});
    CHECK_EQ(rebroadcast_delay_ms(pol, /*snr=*/0, /*is_router=*/true, &rng2), 0u);
    CHECK_EQ(rebroadcast_delay_ms(pol, /*snr=*/0, /*is_router=*/true, &rng2),
             11000u);
    CHECK(rebroadcast_delay_ms(pol, /*snr=*/0, /*is_router=*/true, &rng2) <
          rebroadcast_delay_ms(pol, /*snr=*/0, /*is_router=*/false, &rng2));
  }

  CASE("flood: jitter stays inside the documented window for many draws");
  {
    XorshiftRandom rng(0x12345678u);
    FloodPolicy pol;
    const uint32_t lo = 2u * pol.cw_max * pol.slot_time_ms;
    for (int snr = -20; snr <= 10; snr += 5) {
      const uint32_t hi = lo + cw_slots(cw_size_for_snr(snr)) * pol.slot_time_ms;
      for (int i = 0; i < 200; ++i) {
        const uint32_t d = rebroadcast_delay_ms(pol, snr, false, &rng);
        CHECK(d >= lo);
        CHECK(d < hi);
        CHECK_EQ(d % pol.slot_time_ms, 0u);  // always a whole number of slots
      }
    }
    // The generator must actually vary: a constant would satisfy every bound
    // above and still be a broken jitter source.
    XorshiftRandom r2(99);
    bool varied = false;
    const uint32_t first = rebroadcast_delay_ms(pol, 0, false, &r2);
    for (int i = 0; i < 50; ++i) {
      if (rebroadcast_delay_ms(pol, 0, false, &r2) != first) varied = true;
    }
    CHECK(varied);

    // A null generator is handled, not crashed into.
    CHECK_EQ(rebroadcast_delay_ms(pol, 0, false, nullptr), 0u);
    CHECK_EQ(XorshiftRandom(0).random(0), 0u);
  }

  CASE("flood: duplicate suppression inside the window, allowed outside it");
  {
    DuplicateSuppressor sup(/*window_ms=*/30000);
    MeshPacket p = make_text_packet("dupe");
    CHECK(sup.should_relay(p, 1000));    // first sighting: relay
    CHECK(!sup.should_relay(p, 29999));  // inside window: suppressed
    CHECK(!sup.should_relay(p, 30999));  // just before expiry: still suppressed
    CHECK(sup.should_relay(p, 31001));   // window elapsed: relay again

    // A different packet id, or a different sender, is NOT a duplicate.
    MeshPacket q = p;
    q.id = p.id + 1;
    CHECK(sup.should_relay(q, 32000));
    MeshPacket r = p;
    r.from = p.from + 1;
    CHECK(sup.should_relay(r, 32000));

    // COUNTER-TEST: suppression must key on (from,id) and NOT on the byte
    // length, or an attacker could evade it by padding a repeat.
    MeshPacket s = make_text_packet("a-duplicate-with-a-different-length");
    CHECK(s.payload.size() != p.payload.size());
    CHECK(!sup.should_relay(s, 32000));

    // A zero window is coerced to 1 ms rather than disabling suppression.
    DuplicateSuppressor tiny(0);
    MeshPacket z = make_text_packet("z");
    CHECK(tiny.should_relay(z, 0));
    CHECK(!tiny.should_relay(z, 0));  // same instant is inside a 1 ms window
    CHECK(tiny.should_relay(z, 1));

    sup.reset();
    CHECK(sup.should_relay(p, 2000));
    CHECK_EQ(sup.pending_count(), 1u);
  }

  CASE("flood: an overheard copy cancels a pending rebroadcast inside the window");
  {
    // This is the redundancy the brief asks for: we schedule a relay, then hear
    // somebody else relay the same (from,id) before our slot fires -> drop ours.
    DuplicateSuppressor sup(30000);
    MeshPacket p = make_text_packet("cancel me");
    CHECK(sup.should_relay(p, 0));      // we schedule a rebroadcast
    CHECK_EQ(sup.pending_count(), 1u);
    CHECK(sup.cancel_pending(p, 500));  // we hear a neighbour's copy
    CHECK_EQ(sup.pending_count(), 0u);
    // After cancellation the packet stays in history: we do not relay it again.
    CHECK(!sup.should_relay(p, 600));
    CHECK(!sup.cancel_pending(p, 700));  // nothing pending any more
  }
}

// ---------------------------------------------------------------- transport

static void test_transport() {
  CASE("transport: acquire/release against the frozen HAL contract");
  {
    Medium medium;
    FakeRadioHal hal(&medium);
    FloodPolicy pol;
    XorshiftRandom rng(7);
    MeshTransport t(&hal, make_channel("LongFast", 1), pol, &rng);

    CHECK(!t.acquired());
    // Not acquired: the data path must refuse BEFORE touching the radio.
    CHECK_EQ((int)t.send(make_text_packet("nope"), 10, 100),
             (int)Result::NotAcquired);
    CHECK_EQ((int)t.receive(nullptr, 100), (int)Result::NotAcquired);
    CHECK_EQ(hal.sent_count(), 0u);
    CHECK_EQ((int)t.apply_radio_config(906875000u, 11, 5, 22),
             (int)Result::NotAcquired);

    CHECK_EQ((int)t.begin(100), (int)Result::Ok);
    CHECK(t.acquired());
    CHECK(hal.is_acquired());
    CHECK_EQ((int)t.begin(100), (int)Result::Ok);  // idempotent

    // A second owner must be refused with Busy (the shared-radio reason
    // acquire/release exist at all).
    CHECK_EQ((int)hal.acquire(1), (int)Result::Busy);

    // Configure + read-back verification through the HAL's read_config().
    CHECK_EQ((int)t.apply_radio_config(906875000u, 11, 5, 22), (int)Result::Ok);
    ::balloon::radio::Config rb = {};
    CHECK_EQ((int)hal.read_config(&rb), (int)Result::Ok);
    CHECK_EQ((int)rb.modulation, (int)Modulation::Lora);
    CHECK_EQ(rb.frequency_hz, 906875000u);
    CHECK_EQ((int)rb.spreading_factor, 11);
    CHECK_EQ((int)rb.coding_rate, 5);
    CHECK_EQ((int)rb.tx_power_dbm, 22);
    CHECK_EQ(rb.preamble_symbols, 16);
    CHECK(rb.crc_on);
    CHECK(hal.rx_continuous_set());

    // The HAL contract bounds SF and CR; a bad value is refused locally.
    CHECK_EQ((int)t.apply_radio_config(906875000u, 4, 5, 22),
             (int)Result::BadArgument);
    CHECK_EQ((int)t.apply_radio_config(906875000u, 11, 9, 22),
             (int)Result::BadArgument);

    CHECK_EQ((int)t.end(), (int)Result::Ok);
    CHECK(!t.acquired());
    CHECK(!hal.is_acquired());
    CHECK_EQ((int)t.end(), (int)Result::Ok);  // idempotent
  }

  CASE("transport: send -> receive loopback between two nodes over one medium");
  {
    Medium medium;
    FakeRadioHal halA(&medium), halB(&medium);
    FloodPolicy pol;
    XorshiftRandom r1(1), r2(2);
    MeshTransport a(&halA, make_channel("LongFast", 1), pol, &r1);
    MeshTransport b(&halB, make_channel("LongFast", 1), pol, &r2);
    bring_up(&a, "transport: A comes up");
    bring_up(&b, "transport: B comes up");

    // Channel hash on both ends: 0x08 for LongFast + the default PSK.
    CHECK_EQ(a.channel_hash(), 0x08);
    CHECK_EQ(b.channel_hash(), a.channel_hash());

    MeshPacket out = make_text_packet("loopback text");
    const std::vector<uint8_t> plain = out.payload;
    CHECK_EQ((int)a.send(out, 0, 100), (int)Result::Ok);
    CHECK_EQ(halA.sent_count(), 1u);
    // Exact wire size, independently derived:
    //   16 header
    // +  7 To   + 7 From + 7 Id      (3-byte record + 4-byte value each)
    // +  4 Flags + 4 Channel + 4 NextHop + 4 RelayNode   (3-byte record + 1 byte)
    // + 16 Payload                    (3-byte record + 13 bytes of text)
    // +  4 CRC-32 trailer
    // = 73. Pinning the literal makes a silent layout change impossible.
    CHECK_EQ(halA.last_sent_size(), 73u);
    CHECK(halA.last_sent_size() <= kMaxLoraPayload);

    MeshPacket in;
    CHECK_EQ((int)b.receive(&in, 100), (int)Result::Ok);
    CHECK_EQ(in.from, out.from);
    CHECK_EQ(in.id, out.id);
    CHECK_EQ(in.channel, 0x08);  // the header carries the HASH, not an index
    CHECK_EQ(in.hop_limit(), kDefaultHopLimit);
    CHECK_EQ(in.hop_start(), kDefaultHopLimit);
    CHECK_EQ(in.payload.size(), plain.size());
    CHECK(std::memcmp(in.payload.data(), plain.data(), plain.size()) == 0);
    CHECK_EQ((int)b.last_rx().action, (int)RxAction::Deliver);
    CHECK(b.last_rx().deliver);

    // Nothing else pending: Ok + empty, NOT an error.
    MeshPacket none;
    CHECK_EQ((int)b.receive(&none, 10), (int)Result::Ok);
    CHECK_EQ(none.payload.size(), 0u);
  }

  CASE("transport: two DIFFERENT keys with the SAME hash - hash filter is "
       "defeated, the cipher check is not");
  {
    // This is the case the 8-bit hash genuinely cannot catch, and it is worth
    // constructing rather than hand-waving: the two ASCII strings below have
    // equal byte-XOR, so they hash identically for one channel name while being
    // completely different keys.
    //
    //   xor("0123456789abcdef") == xor("fedcba9876543210") == 0x00
    Medium medium;
    FakeRadioHal halA(&medium), halB(&medium);
    FloodPolicy pol;
    XorshiftRandom r1(1), r2(2);
    MeshTransport a(&halA, make_channel_raw("LongFast", "30313233343536373839616263646566"), pol, &r1);
    MeshTransport b(&halB, make_channel_raw("LongFast", "66656463626139383736353433323130"), pol, &r2);
    bring_up(&a, "transport: hash-collision A comes up");
    bring_up(&b, "transport: hash-collision B comes up");

    CHECK_EQ(a.channel_hash(), b.channel_hash());       // the filter is defeated
    CHECK(std::memcmp(a.key().bytes, b.key().bytes, 16) != 0);  // keys differ

    CHECK_EQ((int)a.send(make_text_packet("secret"), 0, 100), (int)Result::Ok);
    MeshPacket in;
    CHECK_EQ((int)b.receive(&in, 100), (int)Result::BadArgument);
    CHECK_EQ(in.payload.size(), 0u);
    // It reached the cipher check (not the hash filter) and was rejected there.
    CHECK_EQ((int)b.last_rx().action, (int)RxAction::FilterBadFrame);
    CHECK(!b.last_rx().deliver);
  }

  CASE("transport: same name, different PSK alias -> different hash AND different key");
  {
    Medium medium;
    FakeRadioHal halA(&medium), halB(&medium);
    FloodPolicy pol;
    XorshiftRandom r1(1), r2(2);
    MeshTransport a(&halA, make_channel("LongFast", 1), pol, &r1);
    MeshTransport b(&halB, make_channel("LongFast", 2), pol, &r2);
    bring_up(&a, "transport: wrong-alias A comes up");
    bring_up(&b, "transport: wrong-alias B comes up");

    // Alias 2 shifts the last key byte, which changes the XOR, so these two do
    // NOT collide - B rejects on the hash alone.
    CHECK(a.channel_hash() != b.channel_hash());
    CHECK_EQ(a.channel_hash(), 0x08);
    CHECK_EQ(b.channel_hash(), 0x0B);
    CHECK_EQ(a.key().length, 16u);
    CHECK_EQ(b.key().length, 16u);

    CHECK_EQ((int)a.send(make_text_packet("secret"), 0, 100), (int)Result::Ok);
    MeshPacket in;
    CHECK_EQ((int)b.receive(&in, 100), (int)Result::BadArgument);
    CHECK_EQ((int)b.last_rx().action, (int)RxAction::FilterChannelHash);
    CHECK(!b.last_rx().deliver);
  }

  CASE("transport: a packet for another channel hash is filtered before decryption");
  {
    Medium medium;
    FakeRadioHal halA(&medium), halB(&medium);
    FloodPolicy pol;
    XorshiftRandom r1(1), r2(2);
    MeshTransport a(&halA, make_channel("SomeOtherChan", 1), pol, &r1);
    MeshTransport b(&halB, make_channel("LongFast", 1), pol, &r2);
    bring_up(&a, "transport: other-channel A comes up");
    bring_up(&b, "transport: other-channel B comes up");
    CHECK(a.channel_hash() != b.channel_hash());

    CHECK_EQ((int)a.send(make_text_packet("not for you"), 0, 100), (int)Result::Ok);

    // B must reject it on the HASH - before any AES work - and say so.
    MeshPacket in;
    CHECK_EQ((int)b.receive(&in, 100), (int)Result::BadArgument);
    CHECK_EQ((int)b.last_rx().action, (int)RxAction::FilterChannelHash);

    // A hears its own frame (the fake medium delivers to the sender too), and
    // can read it: same channel, same key.
    MeshPacket sniffed;
    CHECK_EQ((int)a.receive(&sniffed, 200), (int)Result::Ok);
    CHECK_EQ((int)a.last_rx().action, (int)RxAction::Deliver);
    CHECK_EQ(sniffed.payload.size(), 11u);

    // B's classifier reaches the same verdict for the same packet.
    RxOutcome o = b.classify(sniffed, 0);
    CHECK_EQ((int)o.action, (int)RxAction::FilterChannelHash);
    // ...and still RELAYS it: a relay exists to carry other people's traffic.
    // Upstream does the same, and it is the property that makes the mesh work.
    CHECK(!o.deliver);
  }

  CASE("transport: rx classifier - deliver, hop-limit stop, duplicate suppression");
  {
    Medium medium;
    FakeRadioHal hal(&medium);
    FloodPolicy pol;
    XorshiftRandom rng(3);
    MeshTransport t(&hal, make_channel("LongFast", 1), pol, &rng);
    bring_up(&t, "transport: classifier node comes up");

    MeshPacket p = make_text_packet("classify");
    p.id = 0xABCD;
    p.channel = t.channel_hash();
    CHECK(p.from != t.node_num());  // not ours

    RxOutcome o = t.classify(p, 0);
    CHECK_EQ((int)o.action, (int)RxAction::Deliver);
    CHECK(o.deliver);
    CHECK(o.rebroadcast);

    // Second sighting of the same (from,id) -> suppressed.
    RxOutcome o2 = t.classify(p, 100);
    CHECK_EQ((int)o2.action, (int)RxAction::FilterDuplicate);
    CHECK(!o2.rebroadcast);
    CHECK(!o2.deliver);
    CHECK_EQ(o2.rebroadcast_delay_ms, 0u);

    // After the history window elapses it is relayed again.
    RxOutcome o3 = t.classify(p, 40000);
    CHECK_EQ((int)o3.action, (int)RxAction::Deliver);
    CHECK(o3.rebroadcast);

    // hop_limit 0: deliver locally, never re-flood.
    MeshPacket last = make_text_packet("last hop");
    last.id = 0xABCE;
    last.channel = t.channel_hash();
    last.set_hop_limit(0);
    RxOutcome o4 = t.classify(last, 0);
    CHECK_EQ((int)o4.action, (int)RxAction::Deliver);
    CHECK(o4.deliver);
    CHECK(!o4.rebroadcast);

    // We never rebroadcast something we originated.
    MeshPacket mine = make_text_packet("mine");
    mine.id = 0xABCF;
    mine.channel = t.channel_hash();
    mine.from = t.node_num();
    RxOutcome o5 = t.classify(mine, 0);
    CHECK_EQ((int)o5.action, (int)RxAction::Deliver);
    CHECK(!o5.rebroadcast);

    // A unicast for somebody else is relayed but NOT delivered upward.
    MeshPacket dm = make_text_packet("dm");
    dm.id = 0xABD0;
    dm.channel = t.channel_hash();
    dm.to = 0x55555555u;
    RxOutcome o6 = t.classify(dm, 0);
    CHECK_EQ((int)o6.action, (int)RxAction::FilterNotForUs);
    CHECK(!o6.deliver);
    CHECK(o6.rebroadcast);

    // A unicast for US is delivered.
    MeshPacket to_us = make_text_packet("to us");
    to_us.id = 0xABD1;
    to_us.channel = t.channel_hash();
    to_us.to = t.node_num();
    RxOutcome o7 = t.classify(to_us, 0);
    CHECK_EQ((int)o7.action, (int)RxAction::Deliver);
    CHECK(o7.deliver);

    // The scheduled delays are real numbers in the documented window.
    CHECK(o.rebroadcast_delay_ms >= 2u * pol.cw_max * pol.slot_time_ms);
  }

  CASE("transport: oversized payload is refused before it reaches the radio");
  {
    Medium medium;
    FakeRadioHal hal(&medium);
    FloodPolicy pol;
    XorshiftRandom rng(4);
    MeshTransport t(&hal, make_channel("LongFast", 1), pol, &rng);
    bring_up(&t, "transport: oversize node comes up");

    MeshPacket too_big = make_text_packet(std::string(kMaxPayloadLen + 1, 'A'));
    CHECK_EQ((int)t.send(too_big, 0, 100), (int)Result::BadArgument);
    CHECK_EQ(hal.sent_count(), 0u);  // nothing handed to the HAL

    // The maximum accepted payload must still leave a frame inside one 255-byte
    // LoRa packet; otherwise kMaxPayloadLen would be a lie.
    MeshPacket ok = make_text_packet(std::string(kMaxPayloadLen, 'B'));
    CHECK_EQ((int)t.send(ok, 0, 100), (int)Result::Ok);
    CHECK_EQ(hal.sent_count(), 1u);
    CHECK(hal.last_sent_size() <= kMaxLoraPayload);
    CHECK(hal.last_sent_size() > kHeaderLength + kMaxPayloadLen);

    // ...and it survives the round trip through the codec and the seal.
    MeshPacket back;
    CHECK_EQ((int)t.receive(&back, 100), (int)Result::Ok);
    CHECK_EQ(back.payload.size(), kMaxPayloadLen);
  }

  CASE("transport: HAL error propagation (BusError, Timeout) is not swallowed");
  {
    Medium medium;
    FakeRadioHal hal(&medium);
    FloodPolicy pol;
    XorshiftRandom rng(5);
    MeshTransport t(&hal, make_channel("LongFast", 1), pol, &rng);
    bring_up(&t, "transport: error-path node comes up");

    hal.set_bus_error(true);
    CHECK_EQ((int)t.send(make_text_packet("boom"), 0, 100), (int)Result::BusError);
    CHECK_EQ(hal.sent_count(), 0u);
    hal.set_bus_error(false);

    CHECK_EQ((int)t.send(make_text_packet("fine"), 0, 100), (int)Result::Ok);
    CHECK_EQ(hal.sent_count(), 1u);

    // The radio stops listening: that is a Timeout, not "nothing received".
    hal.set_rx_continuous(false);
    MeshPacket in;
    CHECK_EQ((int)t.receive(&in, 100), (int)Result::Timeout);

    // A device that never becomes ready is a Timeout out of begin().
    hal.set_ready(false);
    CHECK_EQ((int)t.probe_acquire(100), (int)Result::Timeout);
  }
}

// ---------------------------------------------------------------- main

void run_tests() {
  test_tlv();
  test_channel();
  test_crypto();
  test_header();
  test_flood();
  test_transport();
}

TEST_MAIN()
