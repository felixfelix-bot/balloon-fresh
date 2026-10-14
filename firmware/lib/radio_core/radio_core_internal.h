// L0 - radio_core PRIVATE header (not part of the frozen contract).
//
// radio_hal.h is the frozen interface the protocol layers code against; this
// header is implementation detail for radio_core and its own host test. Nothing
// outside firmware/lib/radio_core should include it.
#pragma once

#include <cstddef>
#include <cstdint>

#include "radio_hal.h"

namespace balloon {
namespace radio {

// --- device descriptor -----------------------------------------------------
// The register map is DATA, not code: an SX1280 map today, an LR2021 map later,
// selected at construction. Adding a device must not touch the driver logic.
struct DeviceDescriptor {
  const char *name;
  uint16_t reg_status;  // single-byte status register (BUSY bit lives here)
  uint8_t busy_bit;     // 1 = BUSY
  uint16_t reg_rssi;    // RSSI, int8 two's complement
  uint16_t reg_snr;     // SNR, int8 two's complement
  uint16_t config_base; // where the config image is written/read back
  uint8_t config_len;   // image length in bytes, checksum included
  uint8_t status_width; // bytes returned by a status read
  bool status_read_supported;
};

enum class Device : uint8_t { Sx1280 = 0, Lr2021 = 1 };

const DeviceDescriptor &descriptorFor(Device dev);

// --- config image codec ----------------------------------------------------
// Byte image: magic(1) version(1) modulation(1) frequency LE32 bandwidth LE32
//             spreading_factor(1) coding_rate(1) tx_power(1)
//             preamble LE16 crc(1) then an XOR checksum byte.
// 17 config bytes + 1 trailing XOR checksum = 18 on the bus.
constexpr size_t kConfigImageBytes = 18;
constexpr uint8_t kConfigMagic = 0xB1;
constexpr uint8_t kConfigVersion = 1;

void configEncode(const Config &cfg, uint8_t *out);
Result configDecode(const uint8_t *in, Config *out);
uint8_t configChecksum(const uint8_t *img, size_t n);

// --- the HAL ---------------------------------------------------------------
// Device build note: radio_core.cpp supplies a host stub for the contract's
// make_radio_hal(SpiBus*) factory (it returns null rather than inventing a
// device, and the host test drives RadioCore directly). A device build that
// defines the real factory elsewhere must compile radio_core.cpp with
// -DBALLOON_RADIO_CORE_DEVICE_FACTORY so the stub is left out and the real
// factory is the only definition.
class RadioCore : public RadioHal {
 public:
  static constexpr uint32_t kAcquirePollBudgetMs = 50;
  static constexpr uint32_t kBusyPollBudgetMs = 50;
  static constexpr uint32_t kResetBudgetMs = 50;
  static constexpr uint32_t kTxBudgetMs = 50;
  static constexpr uint32_t kChunkBytes = 32;  // burst chunk size
  // Hard iteration cap on every device wait. The time budget is the primary
  // bound; this one keeps the loop finite even if the injected clock stands
  // still, so a wedged device can never hang the flight computer.
  static constexpr uint32_t kBusyPollMaxIters = 64;

  explicit RadioCore(SpiBus *bus, Device dev = Device::Sx1280);

  Result acquire(uint32_t timeout_ms) override;
  Result release() override;
  bool is_acquired() const override;

  Result reset() override;
  Result configure(const Config &cfg) override;
  Result read_config(Config *out) const override;

  Result send(const uint8_t *data, size_t len) override;
  Result receive(uint8_t *out, size_t max_len, size_t *out_len,
                 uint32_t timeout_ms) override;

  Result set_rx_continuous(bool on) override;
  Result get_rssi_dbm(int16_t *out) const override;
  Result get_snr_db(int8_t *out) const override;

  // -- register access layer (CS handling, BUSY poll, bounded timeouts) -----
  Result bus_read_reg(uint16_t addr, uint8_t *out) const;
  Result bus_write_reg(uint16_t addr, uint8_t value) const;
  Result bus_read_burst(uint16_t addr, uint8_t *out, size_t len) const;
  Result bus_write_burst(uint16_t addr, const uint8_t *in, size_t len) const;

  // Waits for BUSY to clear, bounded by kBusyPollBudgetMs. Returns Timeout if
  // the device never becomes ready — never an unbounded loop. Counts the
  // readiness probes so the host test can prove it polls and that it gives up.
  Result wait_ready() const;

  const DeviceDescriptor &descriptor() const { return desc_; }

 private:
  Result transact(const uint8_t *tx, uint8_t *rx, size_t len) const;
  Result rx_cont_off_unchecked();
  Result rx_cont_on_unchecked();
  Result send_unchecked(const uint8_t *data, size_t len);

  SpiBus *bus_;
  DeviceDescriptor desc_;
  bool acquired_ = false;
  bool rx_continuous_ = false;
  mutable uint32_t permissions_ = 0;  // readiness probes (diagnostic)
};

}  // namespace radio
}  // namespace balloon
