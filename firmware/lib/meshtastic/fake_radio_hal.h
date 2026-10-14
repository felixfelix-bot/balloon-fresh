// A fake implementation of the FROZEN radio HAL contract, for host tests only.
//
// firmware/lib/radio_core/radio_hal.h is frozen and its implementation
// (radio_core.cpp) is NOT linked here - the brief is explicit about that, and
// about never defining make_radio_hal(). This header is the test double: it
// implements radio::RadioHal directly, records what it was asked to do, and
// joins a shared Medium so several fakes can hear each other.
//
// What this CANNOT do: prove anything about the SX1280/LR2021, the TCXO, SPI,
// timing, or the air. It is a register-free model of the contract, nothing more.
#pragma once

#include "../radio_core/radio_hal.h"

#include <cstring>
#include <deque>
#include <vector>

namespace balloon {
namespace meshtastic {

class FakeRadioHal;

/// A shared virtual "air". Anything one fake sends is appended to every
/// attached fake, including the sender (a half-duplex radio does hear its own
/// transmission unless the driver mutes it; either choice is arbitrary here, and
/// delivering to everyone is the one that lets a test observe a frame it sent).
class Medium {
 public:
  void attach(FakeRadioHal *hal) { hals_.push_back(hal); }
  void detach(FakeRadioHal *hal) {
    for (size_t i = 0; i < hals_.size(); ++i) {
      if (hals_[i] == hal) {
        hals_.erase(hals_.begin() + (long)i);
        return;
      }
    }
  }
  /// Defined out of line, after FakeRadioHal is complete.
  void deliver(const std::vector<uint8_t> &frame);

  size_t broadcasts = 0;

 private:
  std::vector<FakeRadioHal *> hals_;
};

class FakeRadioHal : public radio::RadioHal {
 public:
  explicit FakeRadioHal(Medium *m = nullptr) : medium_(m) {
    if (m != nullptr) m->attach(this);
  }
  ~FakeRadioHal() override {
    if (medium_ != nullptr) medium_->detach(this);
  }

  // ---- test knobs
  void set_bus_error(bool v) { bus_error_ = v; }
  void set_ready(bool v) { ready_ = v; }
  size_t sent_count() const { return sent_count_; }
  size_t last_sent_size() const { return last_sent_size_; }
  bool rx_continuous_set() const { return rx_continuous_; }
  uint32_t total_delay_ms() const { return total_delay_ms_; }
  const std::vector<uint8_t> &last_sent_frame() const { return last_sent_frame_; }
  void inject(const std::vector<uint8_t> &frame) { rx_.push_back(frame); }

  // ---- frozen contract
  radio::Result acquire(uint32_t /*timeout_ms*/) override {
    if (!ready_) return radio::Result::Timeout;  // "device never became ready"
    if (owner_) return radio::Result::Busy;
    owner_ = true;
    return radio::Result::Ok;
  }
  radio::Result release() override {
    if (!owner_) return radio::Result::NotAcquired;
    owner_ = false;
    return radio::Result::Ok;
  }
  bool is_acquired() const override { return owner_; }

  radio::Result reset() override {
    if (!owner_) return radio::Result::NotAcquired;
    return bus_error_ ? radio::Result::BusError : radio::Result::Ok;
  }

  radio::Result configure(const radio::Config &c) override {
    if (!owner_) return radio::Result::NotAcquired;
    if (bus_error_) return radio::Result::BusError;
    cfg_ = c;
    have_cfg_ = true;
    return radio::Result::Ok;
  }

  radio::Result read_config(radio::Config *out) const override {
    if (out == nullptr) return radio::Result::BadArgument;
    if (!have_cfg_) return radio::Result::BadArgument;
    *out = cfg_;
    return radio::Result::Ok;
  }

  radio::Result send(const uint8_t *data, size_t len) override {
    if (!owner_) return radio::Result::NotAcquired;
    if (bus_error_) return radio::Result::BusError;
    if (len > 255) return radio::Result::BadArgument;
    ++sent_count_;
    last_sent_size_ = len;
    last_sent_frame_.assign(data, data + len);
    if (medium_ != nullptr) medium_->deliver(last_sent_frame_);
    return radio::Result::Ok;
  }

  radio::Result receive(uint8_t *out, size_t max_len, size_t *out_len,
                        uint32_t /*timeout_ms*/) override {
    if (!owner_) return radio::Result::NotAcquired;
    if (out_len != nullptr) *out_len = 0;
    // Not listening: nothing can ever arrive, which is a Timeout and not an
    // empty read. Collapsing the two would let a caller spin on a dead radio.
    if (!rx_continuous_) return radio::Result::Timeout;
    if (rx_.empty()) return radio::Result::Ok;  // nothing pending (Ok + 0)
    const std::vector<uint8_t> f = rx_.front();
    rx_.pop_front();
    if (f.size() > max_len) return radio::Result::BadArgument;
    if (out != nullptr && !f.empty()) std::memcpy(out, f.data(), f.size());
    if (out_len != nullptr) *out_len = f.size();
    return radio::Result::Ok;
  }

  radio::Result set_rx_continuous(bool on) override {
    if (!owner_) return radio::Result::NotAcquired;
    rx_continuous_ = on;
    return radio::Result::Ok;
  }

  radio::Result get_rssi_dbm(int16_t *out) const override {
    if (out == nullptr) return radio::Result::BadArgument;
    *out = rssi_;
    return radio::Result::Ok;
  }
  radio::Result get_snr_db(int8_t *out) const override {
    if (out == nullptr) return radio::Result::BadArgument;
    *out = snr_;
    return radio::Result::Ok;
  }

 private:
  Medium *medium_ = nullptr;
  bool owner_ = false;
  bool ready_ = true;
  bool bus_error_ = false;
  bool rx_continuous_ = false;
  bool have_cfg_ = false;
  size_t sent_count_ = 0;
  size_t last_sent_size_ = 0;
  uint32_t total_delay_ms_ = 0;
  int16_t rssi_ = -70;
  int8_t snr_ = 5;
  radio::Config cfg_{};
  std::vector<uint8_t> last_sent_frame_;
  std::deque<std::vector<uint8_t>> rx_;
};

inline void Medium::deliver(const std::vector<uint8_t> &frame) {
  ++broadcasts;
  // Delivered to EVERY attached fake, including the sender: a real
  // half-duplex radio hears its own transmission, and delivering to the sender
  // is what lets a test observe the frame a node actually put on the air.
  for (FakeRadioHal *h : hals_) h->inject(frame);
}

}  // namespace meshtastic
}  // namespace balloon
