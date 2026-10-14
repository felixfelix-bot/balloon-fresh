// L4 (Meshtastic) - flooding / rebroadcast policy.
//
// SOURCES (public):
//
// 1. src/mesh/FloodingRouter.h (meshtastic/firmware) states the flooding rules
//    in prose, and it is the clearest public statement of the policy:
//
//      "If to==BROADCAST and id==0, this is a simple broadcast (0 hops). It
//       will be sent only by the current node and other nodes will not attempt
//       to rebroadcast it.
//       If to==BROADCAST and id!=0, this is a 'naive flooding' broadcast. The
//       initial node will send it on all local interfaces.
//       When other nodes receive this message, they will first check if their
//       recentBroadcasts table contains the (from, id) pair ... If so, we've
//       already seen it - so we discard it. If not, we add it to the table and
//       then resend this message on all interfaces. When resending we are
//       careful to use the 'from' ID of the original sender, not our own ID.
//       When resending we pick a random delay between 0 and 10 seconds to
//       decrease the chance of collisions with transmitters we can not even
//       hear.
//       Any entries in recentBroadcasts that are older than X seconds ... will
//       be discarded."
//
// 2. src/mesh/RadioInterface.cpp gives the delay in terms of a contention
//    window rather than "0 to 10 seconds":
//
//      const uint8_t CWmin = 3;   // minimum CWsize
//      const uint8_t CWmax = 8;   // maximum CWsize
//      uint8_t getCWsize(float snr) { return map(snr, -20, 10, CWmin, CWmax); }
//
//      uint32_t getTxDelayMsecWeighted(p) {          // non-router
//        uint8_t CWsize = getCWsize(p->rx_snr);
//        delay = (2 * CWmax * slotTimeMsec) + random(0, pow_of_2(CWsize)) * slotTimeMsec;
//      }
//      // for a ROUTER, delay = random(0, 2 * CWsize) * slotTimeMsec  (no offset)
//
//    Note `random(0, N)` in the Arduino core is documented as returning
//    [0, N), and the arithmetic below follows that reading.
//
// 3. src/mesh/RadioInterface.cpp: `slotTimeMsec = computeSlotTimeMsec();` - the
//    slot time is derived from the LoRa preamble/airtime at the configured
//    bandwidth, so it is a function of the radio config, not a constant.
//
//    UNVERIFIED CONSTANT: the default slot time used here. A real Meshtastic
//    LongFast node computes something around a few hundred milliseconds, and
//    the FloodingRouter.h prose talks about a window of "0 to 10 seconds". This
//    module therefore defaults slot_time_ms to 1000, which makes the non-router
//    window 2*8*1000 = 16 s base plus up to 256 s - far wider than the prose's
//    "0 to 10 seconds". The two public sources disagree; the STRUCTURE (an SNR
//    dependent contention window scaled by a slot time) is verified, the
//    DEFAULT SLOT MILLISECONDS IS NOT. It is a constructor parameter with a
//    named constant so it can be set from measured airtime. See REPORT.md.
//
// 4. src/mesh/Router.cpp:70-130 (`shouldDecrementHopLimit`) plus
//    src/mesh/NextHopRouter.cpp:138 (`tosend->hop_limit--`) confirm the decrement
//    on relay. Upstream has a role-dependent exception (a favourite ROUTER to
//    ROUTER first hop may PRESERVE the hop limit). That exception is NOT
//    implemented here: this balloon node is a plain client, and silently
//    preserving a hop limit is exactly the kind of behaviour that turns into a
//    broadcast storm on a link with no duty-cycle headroom. Always decrement.
#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

#include "mesh_packet.h"

namespace balloon {
namespace meshtastic {

/// Injectable randomness. The rebroadcast delay MUST be testable, so the
/// generator is an interface and the test supplies a scripted one. `random(n)`
/// returns a value in [0, n) and returns 0 for n == 0 (mirroring the Arduino
/// core's documented contract, and total rather than undefined).
class RandomSource {
 public:
  virtual ~RandomSource() = default;
  virtual uint32_t random(uint32_t n) = 0;
};

/// A deterministic PRNG for production use and for tests that want a real
/// distribution rather than a script. Not cryptographic and not used for keys.
class XorshiftRandom : public RandomSource {
 public:
  explicit XorshiftRandom(uint32_t seed = 0x2545F491u) : s_(seed ? seed : 1u) {}
  uint32_t random(uint32_t n) override {
    s_ ^= s_ << 13;
    s_ ^= s_ >> 17;
    s_ ^= s_ << 5;
    return n == 0 ? 0 : (uint32_t)(s_ % n);
  }
  void reseed(uint32_t seed) { s_ = seed ? seed : 1u; }

 private:
  uint32_t s_;
};

/// Returns a scripted sequence and then a fixed fallback, so a test can assert
/// an exact delay without a real distribution. Holds a value copy, not a view,
/// so a test can build the vector inline.
class ScriptedRandom : public RandomSource {
 public:
  explicit ScriptedRandom(std::vector<uint32_t> script,
                          uint32_t fallback = 0)
      : script_(std::move(script)), fallback_(fallback) {}

  uint32_t random(uint32_t n) override {
    uint32_t v = fallback_;
    if (i_ < script_.size()) v = script_[i_++];
    else ++i_;
    return n == 0 ? 0 : (uint32_t)(v % n);
  }

  size_t draws() const { return i_; }

 private:
  std::vector<uint32_t> script_;
  uint32_t fallback_;
  size_t i_ = 0;
};

/// Rebroadcast timing policy. Defaults are the verified upstream CWmin/CWmax
/// and an UNVERIFIED slot time - see the header comment.
struct FloodPolicy {
  uint32_t slot_time_ms = 1000;  // UNVERIFIED default, see mesh_flood.h
  uint8_t cw_min = 3;            // upstream RadioInterface.h CWmin
  uint8_t cw_max = 8;            // upstream RadioInterface.h CWmax
  /// How long a (from,id) stays in the duplicate history. Upstream discards
  /// entries "older than X seconds"; the Prose says the max a flood can take.
  uint32_t duplicate_window_ms = 30000;
};

/// SNR -> contention window size. Upstream getCWsize(): map(snr, -20, 10, 3, 8).
uint8_t cw_size_for_snr(int snr);

/// 2^cw, the CW expansion upstream does with pow_of_2().
uint32_t cw_slots(uint8_t cw);

/// The delay to wait before rebroadcasting. Deterministic given a RandomSource.
///
///   is_router == false (our case): 2*cw_max*slot + random(0, 2^cw)*slot
///   is_router == true            : random(0, 2*cw)*slot
///
/// The router branch is implemented so the ROUTER_LATE / early-rebroadcast
/// behaviour is available if this node is ever configured as one, but the
/// balloon's default is the client branch.
uint32_t rebroadcast_delay_ms(const FloodPolicy &pol, int snr, bool is_router,
                             RandomSource *rng);

/// Whether this node should rebroadcast a packet it just received.
///
/// Rules applied, in order:
///   * a packet this node originated is never re-flooded (upstream FloodingRouter
///     adds its own packets to the seen list for exactly this reason);
///   * hop_limit must be non-zero (a packet at zero has exhausted its budget);
///   * the packet must be a broadcast (id != 0). to==BROADCAST with id==0 is the
///     documented "simple broadcast (0 hops)" that nobody rebroadcasts.
bool should_rebroadcast(const MeshPacket &p, bool from_us);

/// The copy to transmit when rebroadcasting: hop limit decremented (floor 0),
/// hop_start untouched so the original budget is preserved, original sender kept
/// in `from`. Never underflows.
MeshPacket rebroadcast_copy(const MeshPacket &p);

/// Hops travelled so far, derived the way upstream does it
/// (`getHopsAway` = hop_start - hop_limit).
uint8_t hops_away(const MeshPacket &p);

/// Duplicate history keyed on (from, id), which is the pair upstream's
/// recentBroadcasts table uses. Also tracks which of those packets have a
/// rebroadcast PENDING, so an overheard copy can cancel our own transmission -
/// that cancellation is the redundancy suppression the brief asks for, and it is
/// what upstream calls `perhapsCancelDupe` / `cancelSending`.
class DuplicateSuppressor {
 public:
  explicit DuplicateSuppressor(uint32_t window_ms = 30000);

  /// \return true when this packet has NOT been seen inside the window, i.e.
  ///         when the caller should relay it. Records the sighting and marks a
  ///         rebroadcast as pending.
  bool should_relay(const MeshPacket &p, uint32_t now_ms);

  /// \return true when a pending rebroadcast for (p.from, p.id) existed and was
  ///         cancelled. Call this when the same packet is overheard from a
  ///         neighbour: our slot is now redundant. The history entry stays, so
  ///         we do not relay it afterwards either.
  bool cancel_pending(const MeshPacket &p, uint32_t now_ms);

  /// Number of rebroadcasts currently scheduled.
  size_t pending_count() const;

  /// Forget everything. Used by tests and on a config change.
  void reset();

 private:
  struct Entry {
    uint32_t from;
    uint32_t id;
    uint32_t seen_ms;
    bool pending;
  };
  std::vector<Entry> entries_;
  uint32_t window_ms_;
};

}  // namespace meshtastic
}  // namespace balloon
