#include "mesh_flood.h"

#include <algorithm>

namespace balloon {
namespace meshtastic {

uint8_t cw_size_for_snr(int snr) {
  // Upstream getCWsize(): map(snr, -20, 10, CWmin, CWmax). Arduino's map() is
  // integer arithmetic and does NOT clamp, but the call site only ever sees LoRa
  // SNRs; clamping here is a deliberate hardening so a nonsense SNR cannot
  // produce a nonsense window.
  const uint8_t cw_min = 3;
  const uint8_t cw_max = 8;
  const int in_min = -20;
  const int in_max = 10;
  int s = snr;
  if (s < in_min) s = in_min;
  if (s > in_max) s = in_max;
  const int out =
      (s - in_min) * (int)(cw_max - cw_min) / (in_max - in_min) + (int)cw_min;
  return (uint8_t)out;
}

uint32_t cw_slots(uint8_t cw) { return 1u << cw; }

uint32_t rebroadcast_delay_ms(const FloodPolicy &pol, int snr, bool is_router,
                             RandomSource *rng) {
  const uint8_t cw = cw_size_for_snr(snr);
  if (rng == nullptr) return 0;
  if (is_router) {
    // Upstream RadioInterface::getTxDelayMsecWeighted, router branch:
    //   random(0, 2 * CWsize) * slotTimeMsec
    return (uint32_t)rng->random((uint32_t)(2u * cw)) * pol.slot_time_ms;
  }
  // Upstream non-router branch:
  //   (2 * CWmax * slotTimeMsec) + random(0, pow_of_2(CWsize)) * slotTimeMsec
  // The CWmax offset is what makes a ROUTER rebroadcast before a CLIENT: the
  // client path is pushed out by a whole worst-case window so the routers get
  // first say. That ordering is the point of the policy, so it is reproduced
  // rather than simplified away.
  const uint32_t base = 2u * pol.cw_max * pol.slot_time_ms;
  return base + (uint32_t)rng->random(cw_slots(cw)) * pol.slot_time_ms;
}

bool should_rebroadcast(const MeshPacket &p, bool from_us) {
  if (from_us) return false;                  // never re-flood our own traffic
  if (p.id == 0) return false;                // documented "simple broadcast (0 hops)"
  if (p.hop_limit() == 0) return false;       // budget exhausted
  return true;
}

MeshPacket rebroadcast_copy(const MeshPacket &p) {
  MeshPacket out = p;
  const uint8_t hl = p.hop_limit();
  // Always decrement, never preserve. Upstream has a role-dependent exception
  // for favourite ROUTER-to-ROUTER first hops; that is intentionally not
  // reproduced (see mesh_flood.h) because a preserved hop limit on a link with
  // no duty-cycle headroom is a broadcast storm waiting to happen.
  out.set_hop_limit(hl > 0 ? (uint8_t)(hl - 1) : 0);
  // hop_start is the ORIGINAL budget and must not move, otherwise hops_away
  // (hop_start - hop_limit) stops being the distance travelled.
  out.set_hop_start(p.hop_start());
  // Whether we are the original sender matters: a relay keeps the sender's
  // address so that duplicate suppression still works end to end.
  return out;
}

uint8_t hops_away(const MeshPacket &p) {
  const uint8_t start = p.hop_start();
  const uint8_t limit = p.hop_limit();
  return start >= limit ? (uint8_t)(start - limit) : 0;
}

DuplicateSuppressor::DuplicateSuppressor(uint32_t window_ms)
    : window_ms_(window_ms == 0 ? 1 : window_ms) {}

bool DuplicateSuppressor::should_relay(const MeshPacket &p, uint32_t now_ms) {
  // Expire entries that can no longer suppress anything, so a flight of many
  // hours cannot grow this table without bound.
  const uint32_t cutoff = now_ms - window_ms_;
  entries_.erase(std::remove_if(entries_.begin(), entries_.end(),
                                [cutoff, now_ms](const Entry &e) {
                                  return (uint32_t)(now_ms - e.seen_ms) >=
                                         (uint32_t)(now_ms - cutoff);
                                }),
                 entries_.end());

  for (auto &e : entries_) {
    if (e.from == p.from && e.id == p.id) {
      const uint32_t age = now_ms - e.seen_ms;
      if (age < window_ms_) return false;  // inside the window: suppress
      e.seen_ms = now_ms;
      e.pending = true;
      return true;
    }
  }
  entries_.push_back(Entry{p.from, p.id, now_ms, true});
  return true;
}

bool DuplicateSuppressor::cancel_pending(const MeshPacket &p, uint32_t) {
  for (auto &e : entries_) {
    if (e.from == p.from && e.id == p.id && e.pending) {
      e.pending = false;
      return true;
    }
  }
  return false;
}

size_t DuplicateSuppressor::pending_count() const {
  size_t n = 0;
  for (const auto &e : entries_) {
    if (e.pending) ++n;
  }
  return n;
}

void DuplicateSuppressor::reset() { entries_.clear(); }

}  // namespace meshtastic
}  // namespace balloon
