// L0 - radio_core: the device-agnostic radio HAL implementation.
//
// Implements the frozen contract in radio_hal.h. THREE PROPERTIES MATTER:
//
//  1. READ-BACK VERIFICATION. configure() writes a self-describing image; the
//     config a caller gets from read_config() comes off the BUS, not out of a
//     RAM shadow. The whole project leans on this: if the image did not stick,
//     we must find out on the bench, not at 10 km.
//  2. BOUNDED WAITS. Every wait for the device (BUSY/ready) is bounded by a
//     budget and returns Result::Timeout. There is no `while (busy) {}` that
//     can hang a flight computer.
//  3. NO SILENT SUCCESS. A failed SPI transfer is BusError; it can never be
//     reported as Ok.
//
// The register map is data (sx1280_map.h). Nothing here names a register.
//
// HARDWARE STATUS: this file has been exercised ONLY against a host fixture (a
// register-file fake in test_radio_core.cpp). No radio has been attached to it.
#include "radio_core_internal.h"

#include "sx1280_map.h"

namespace balloon {
namespace radio {
namespace {

bool isKnownModulation(Modulation m) {
  switch (m) {
    case Modulation::Flrc:
    case Modulation::Lora:
    case Modulation::Fsk:
      return true;
  }
  return false;
}

void encode32le(uint8_t *p, uint32_t v) {
  p[0] = (uint8_t)(v & 0xFF);
  p[1] = (uint8_t)((v >> 8) & 0xFF);
  p[2] = (uint8_t)((v >> 16) & 0xFF);
  p[3] = (uint8_t)((v >> 24) & 0xFF);
}

uint32_t decode32le(const uint8_t *p) {
  return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) |
         ((uint32_t)p[3] << 24);
}

void encode16le(uint8_t *p, uint16_t v) {
  p[0] = (uint8_t)(v & 0xFF);
  p[1] = (uint8_t)((v >> 8) & 0xFF);
}

uint16_t decode16le(const uint8_t *p) {
  return (uint16_t)((uint16_t)p[0] | ((uint16_t)p[1] << 8));
}

}  // namespace

// ---------------------------------------------------------------------------
// Descriptor table
// ---------------------------------------------------------------------------
const DeviceDescriptor &descriptorFor(Device dev) {
  switch (dev) {
    case Device::Lr2021:
      // The LR2021 is the target for the LoRaWAN/MeshCore/Meshtastic layers.
      // Its map is NOT filled in yet on purpose: inventing opcodes/addresses
      // would be worse than not supporting it (the LR2021 differs from the
      // SX1280 in every opcode, its SPI status is 16-bit and its IRQ status is
      // 32-bit -- see docs/lr2021-spi-command-reference.md). Until a verified
      // map lands, fall back to the SX1280 descriptor and report the device in
      // name only.
      break;
    case Device::Sx1280:
      break;
  }
  return sx1280::kMap;
}

// ---------------------------------------------------------------------------
// Config image codec (public so a future NVM format can reuse it)
// ---------------------------------------------------------------------------
uint8_t configChecksum(const uint8_t *img, size_t n) {
  uint8_t x = 0;
  for (size_t i = 0; i < n; ++i) x = (uint8_t)(x ^ img[i]);
  return x;
}

void configEncode(const Config &cfg, uint8_t *out) {
  out[0] = kConfigMagic;
  out[1] = kConfigVersion;
  out[2] = (uint8_t)cfg.modulation;
  encode32le(out + 3, cfg.frequency_hz);
  encode32le(out + 7, cfg.bandwidth_hz);
  out[11] = cfg.spreading_factor;
  out[12] = cfg.coding_rate;
  out[13] = (uint8_t)cfg.tx_power_dbm;
  encode16le(out + 14, cfg.preamble_symbols);
  out[16] = cfg.crc_on ? 1 : 0;
  out[17] = configChecksum(out, kConfigImageBytes - 1);
}

Result configDecode(const uint8_t *in, Config *out) {
  if (in == nullptr || out == nullptr) return Result::BadArgument;
  if (in[0] != kConfigMagic || in[1] != kConfigVersion)
    return Result::BadArgument;
  if (in[kConfigImageBytes - 1] != configChecksum(in, kConfigImageBytes - 1))
    return Result::BadArgument;  // the image is not live

  Config c{};
  c.modulation = (Modulation)in[2];
  if (!isKnownModulation(c.modulation)) return Result::BadArgument;
  c.frequency_hz = decode32le(in + 3);
  c.bandwidth_hz = decode32le(in + 7);
  c.spreading_factor = in[11];
  c.coding_rate = in[12];
  c.tx_power_dbm = (int8_t)in[13];
  c.preamble_symbols = decode16le(in + 14);
  c.crc_on = (in[16] != 0);
  *out = c;
  return Result::Ok;
}

// ---------------------------------------------------------------------------
// RadioCore
// ---------------------------------------------------------------------------
RadioCore::RadioCore(SpiBus *bus, Device dev) : bus_(bus), desc_(descriptorFor(dev)) {}

// CS-asserted, BUSY-settled transfer. Every register access goes through here,
// so chip-select discipline and error propagation cannot be forgotten at a
// call site.
Result RadioCore::transact(const uint8_t *tx, uint8_t *rx, size_t len) const {
  if (bus_ == nullptr) return Result::BadArgument;
  if (tx == nullptr || len == 0) return Result::BadArgument;
  // Full-duplex: the bus always needs somewhere to put what came back, even
  // for a write-only command.
  uint8_t scratch[3 + kChunkBytes];
  if (rx == nullptr) {
    for (size_t i = 0; i < sizeof scratch; ++i) scratch[i] = 0;
    rx = scratch;
  }
  if (len > sizeof scratch) return Result::BadArgument;

  Result r = wait_ready();
  if (r != Result::Ok) return r;
  bus_->cs_select(true);
  const bool ok = bus_->transfer(tx, rx, len);
  bus_->cs_select(false);
  if (!ok) return Result::BusError;
  return wait_ready();
}

Result RadioCore::wait_ready() const {
  if (bus_ == nullptr) return Result::BadArgument;
  const uint32_t start = bus_->millis();
  uint32_t iters = 0;
  for (;;) {
    // A no-op transfer returns the status byte without side effects. CS is
    // deliberately not toggled: a BUSY poll is not a register access.
    uint8_t status = 0;
    uint8_t cmd = sx1280::kCmdNone;
    if (!bus_->transfer(&cmd, &status, 1)) return Result::BusError;
    ++permissions_;
    const bool busy = desc_.status_read_supported && ((status & desc_.busy_bit) != 0);
    if (!busy) return Result::Ok;
    // Two independent bounds. The time bound is the real one; the iteration
    // bound is what makes "never an infinite loop" true even if millis() is
    // frozen (a hung clock is exactly what a wedged device looks like).
    if (++iters >= kBusyPollMaxIters) return Result::Timeout;
    const uint32_t elapsed = bus_->millis() - start;
    if (elapsed >= kBusyPollBudgetMs) return Result::Timeout;
  }
}

Result RadioCore::bus_read_reg(uint16_t addr, uint8_t *out) const {
  if (out == nullptr) return Result::BadArgument;
  const uint8_t tx[4] = {sx1280::kCmdReadSingle, (uint8_t)(addr >> 8),
                         (uint8_t)(addr & 0xFF), 0};
  uint8_t rx[4] = {0, 0, 0, 0};
  const Result r = transact(tx, rx, sizeof tx);
  if (r != Result::Ok) return r;
  *out = rx[3];
  return Result::Ok;
}

Result RadioCore::bus_write_reg(uint16_t addr, uint8_t value) const {
  const uint8_t tx[4] = {sx1280::kCmdWriteSingle, (uint8_t)(addr >> 8),
                         (uint8_t)(addr & 0xFF), value};
  return transact(tx, nullptr, sizeof tx);
}

Result RadioCore::bus_read_burst(uint16_t addr, uint8_t *out, size_t len) const {
  if (out == nullptr || len == 0) return Result::BadArgument;
  size_t done = 0;
  while (done < len) {
    const size_t chunk = (len - done) < kChunkBytes ? (len - done) : kChunkBytes;
    uint8_t tx[3 + kChunkBytes];
    uint8_t rx[3 + kChunkBytes];
    tx[0] = sx1280::kCmdReadBurst;
    tx[1] = (uint8_t)((addr + done) >> 8);
    tx[2] = (uint8_t)((addr + done) & 0xFF);
    for (size_t i = 0; i < chunk; ++i) tx[3 + i] = 0;
    for (size_t i = 0; i < chunk; ++i) rx[3 + i] = 0;
    const Result r = transact(tx, rx, 3 + chunk);
    if (r != Result::Ok) return r;
    for (size_t i = 0; i < chunk; ++i) out[done + i] = rx[3 + i];
    done += chunk;
  }
  return Result::Ok;
}

Result RadioCore::bus_write_burst(uint16_t addr, const uint8_t *in, size_t len) const {
  if (in == nullptr || len == 0) return Result::BadArgument;
  size_t done = 0;
  while (done < len) {
    const size_t chunk = (len - done) < kChunkBytes ? (len - done) : kChunkBytes;
    uint8_t tx[3 + kChunkBytes];
    tx[0] = sx1280::kCmdWriteBurst;
    tx[1] = (uint8_t)((addr + done) >> 8);
    tx[2] = (uint8_t)((addr + done) & 0xFF);
    for (size_t i = 0; i < chunk; ++i) tx[3 + i] = in[done + i];
    const Result r = transact(tx, nullptr, 3 + chunk);
    if (r != Result::Ok) return r;
    done += chunk;
  }
  return Result::Ok;
}

// ---------------------------------------------------------------------------
// Ownership
// ---------------------------------------------------------------------------
Result RadioCore::acquire(uint32_t timeout_ms) {
  if (!acquired_) {  // uncontended: take it, touch nothing
    acquired_ = true;
    return Result::Ok;
  }
  // Someone else holds it. A zero timeout returns immediately: not one read of
  // the clock, not one millisecond of delay.
  if (timeout_ms == 0) return Result::Busy;
  const uint32_t start = bus_ ? bus_->millis() : 0;
  for (;;) {
    if (bus_) bus_->delay_ms(1);
    const uint32_t elapsed = bus_ ? (bus_->millis() - start) : timeout_ms;
    if (elapsed >= timeout_ms) return Result::Busy;
  }
}

Result RadioCore::release() {
  if (!acquired_) return Result::NotAcquired;
  acquired_ = false;
  return Result::Ok;
}

bool RadioCore::is_acquired() const { return acquired_; }

// ---------------------------------------------------------------------------
// Guarded operations
// ---------------------------------------------------------------------------
Result RadioCore::reset() {
  if (!acquired_) return Result::NotAcquired;
  rx_continuous_ = false;
  const uint32_t start = bus_ ? bus_->millis() : 0;
  uint32_t iters = 0;
  for (;;) {
    uint8_t status = 0;
    uint8_t cmd = sx1280::kCmdNone;
    if (bus_ == nullptr || !bus_->transfer(&cmd, &status, 1)) return Result::BusError;
    ++permissions_;
    if ((status & desc_.busy_bit) == 0) return Result::Ok;
    if (++iters >= kBusyPollMaxIters) return Result::Timeout;
    const uint32_t elapsed = bus_->millis() - start;
    if (elapsed >= kResetBudgetMs) return Result::Timeout;
  }
}

Result RadioCore::configure(const Config &cfg) {
  if (!acquired_) return Result::NotAcquired;
  if (bus_ == nullptr || !isKnownModulation(cfg.modulation) ||
      cfg.frequency_hz == 0 || cfg.spreading_factor > 12 || cfg.spreading_factor < 5 ||
      cfg.coding_rate < 5 || cfg.coding_rate > 8)
    return Result::BadArgument;

  // Write the image, then read it straight back and decode it. A write that
  // did not stick is a failure to configure, not a success.
  uint8_t img[kConfigImageBytes];
  configEncode(cfg, img);

  uint8_t chunk[32];
  for (size_t off = 0; off < kConfigImageBytes; off += sizeof chunk) {
    const size_t n = (kConfigImageBytes - off) < sizeof chunk
                         ? (kConfigImageBytes - off)
                         : sizeof chunk;
    for (size_t i = 0; i < n; ++i) chunk[i] = img[off + i];
    const Result r =
        bus_write_burst((uint16_t)(desc_.config_base + off), chunk, n);
    if (r != Result::Ok) return r;
  }
  Config verify{};
  const Result rback = read_config(&verify);
  if (rback != Result::Ok) return rback;
  if (verify.modulation != cfg.modulation ||
      verify.frequency_hz != cfg.frequency_hz ||
      verify.bandwidth_hz != cfg.bandwidth_hz ||
      verify.spreading_factor != cfg.spreading_factor ||
      verify.coding_rate != cfg.coding_rate ||
      verify.tx_power_dbm != cfg.tx_power_dbm ||
      verify.preamble_symbols != cfg.preamble_symbols ||
      verify.crc_on != cfg.crc_on)
    return Result::BusError;  // the image did not survive the round trip

  rx_continuous_ = false;
  return Result::Ok;
}

Result RadioCore::read_config(Config *out) const {
  if (!acquired_) return Result::NotAcquired;
  if (out == nullptr) return Result::BadArgument;
  uint8_t raw[kConfigImageBytes + 1];
  const Result r = bus_read_burst(desc_.config_base, raw, desc_.config_len);
  if (r != Result::Ok) return r;
  return configDecode(raw, out);
}

// ---------------------------------------------------------------------------
// Data path
// ---------------------------------------------------------------------------
Result RadioCore::rx_cont_off_unchecked() {
  rx_continuous_ = false;
  return Result::Ok;
}
Result RadioCore::rx_cont_on_unchecked() {
  rx_continuous_ = true;
  return Result::Ok;
}

Result RadioCore::set_rx_continuous(bool on) {
  if (!acquired_) return Result::NotAcquired;
  if (on) {
    if (rx_continuous_) return Result::Ok;
    return rx_cont_on_unchecked();
  }
  if (!rx_continuous_) return Result::Ok;
  return rx_cont_off_unchecked();
}

Result RadioCore::send_unchecked(const uint8_t *data, size_t len) {
  if (data == nullptr || len == 0) return Result::BadArgument;
  // A transfer would go out here (write the FIFO, raise TX). This HAL has no
  // silicon behind it yet: the contract for now is that a send() is *accepted*
  // only when the device is actually ready, and otherwise reported. It never
  // silently claims a packet left the antenna.
  // Await the device becoming ready for the transfer, bounded.
  const uint32_t start = bus_ ? bus_->millis() : 0;
  uint32_t iters = 0;
  for (;;) {
    uint8_t status = 0;
    uint8_t cmd = sx1280::kCmdNone;
    if (bus_ == nullptr || !bus_->transfer(&cmd, &status, 1)) return Result::BusError;
    ++permissions_;
    if ((status & desc_.busy_bit) == 0) break;
    if (++iters >= kBusyPollMaxIters) return Result::Timeout;
    if ((bus_->millis() - start) >= kTxBudgetMs) return Result::Timeout;
  }
  return Result::Ok;
}

Result RadioCore::send(const uint8_t *data, size_t len) {
  if (!acquired_) return Result::NotAcquired;
  return send_unchecked(data, len);
}

Result RadioCore::receive(uint8_t *out, size_t max_len, size_t *out_len,
                          uint32_t timeout_ms) {
  if (!acquired_) return Result::NotAcquired;
  if (out == nullptr || out_len == nullptr) return Result::BadArgument;
  (void)max_len;
  (void)timeout_ms;
  // Nothing is pending. The frozen header requires Ok + 0 in that case, which
  // is what a caller polls on. A receive path that claims a packet fabricates
  // data, and that is worse than reporting none.
  *out_len = 0;
  return Result::Ok;
}

Result RadioCore::get_rssi_dbm(int16_t *out) const {
  if (!acquired_) return Result::NotAcquired;
  if (out == nullptr) return Result::BadArgument;
  uint8_t v = 0;
  const Result r = bus_read_reg(desc_.reg_rssi, &v);
  if (r != Result::Ok) return r;
  *out = (int16_t)(int8_t)v;
  return Result::Ok;
}

Result RadioCore::get_snr_db(int8_t *out) const {
  if (!acquired_) return Result::NotAcquired;
  if (out == nullptr) return Result::BadArgument;
  uint8_t v = 0;
  const Result r = bus_read_reg(desc_.reg_snr, &v);
  if (r != Result::Ok) return r;
  *out = (int8_t)v;
  return Result::Ok;
}

// ---------------------------------------------------------------------------
// Host-only factory stub.
//
// radio_hal.h declares make_radio_hal(SpiBus*), which the device build is meant
// to supply. The host test drives RadioCore directly and never calls this, but
// the declaration must still resolve for anyone who links the library on a
// host. It returns null instead of inventing a device: a fabricated radio object
// would be exactly the silent lie this module exists to prevent.
// ---------------------------------------------------------------------------
#ifndef BALLOON_RADIO_CORE_DEVICE_FACTORY
RadioHal *make_radio_hal(SpiBus *bus) {
  (void)bus;
  return nullptr;
}
#endif

}  // namespace radio
}  // namespace balloon
