// L0/L1 - TDD entry point for radio_core (device-agnostic radio HAL).
//
// RED-FIRST: this file was committed BEFORE radio_core.cpp existed, so the
// module fails to build (undefined reference to make_radio_hal). See REPORT.md.
//
// NO HARDWARE. There is no radio attached to this host and none is claimed.
// `FakeSpi` below is a *fixture*, not silicon: a register-file + BUSY flag that
// speaks the SX1280 command framing. It is the counter-test subject, not proof
// that real SPI works on the ESP32-S3.
//
// It also must NOT define make_radio_hal(): the test constructs RadioCore
// directly, which keeps the (host-only) factory link-time-only.
#include "harness.h"

#include "radio_core_internal.h"
#include "radio_hal.h"
#include "sx1280_map.h"

#include <map>

using balloon::radio::Config;
using balloon::radio::Modulation;
using balloon::radio::RadioCore;
using balloon::radio::Result;
using balloon::radio::SpiBus;
using balloon::radio::descriptorFor;

// SX1280 register/command framing constants, mirrored here ON PURPOSE. If the
// implementation used a different opcode the fixture would reject the call
// (unknown opcode -> transfer returns false -> BusError), so a green suite
// really does pin the wire format.
enum : uint8_t {
  kCmdNone = 0x00,  // returns a status byte, no side effects
  kCmdWriteSingle = 0x18,
  kCmdReadSingle = 0x19,
  kCmdWriteBurst = 0x1A,
  kCmdReadBurst = 0x1B,
};
enum : uint16_t { kRegStatus = 0x0010, kRegRssi = 0x001A, kRegSnr = 0x001B };
// Far above any legitimate poll budget (the driver caps at 64), so tripping it
// always means the driver lost its bound.
constexpr uint32_t kProbeLimit = 10000;

constexpr uint16_t kRegEnd = 0x0080u;  // 128-byte register file, like a real SX1280 map

// ---------------------------------------------------------------------------
// Fixture: a register-file fake of the SPI transport.
// ---------------------------------------------------------------------------
class FakeSpi : public SpiBus {
 public:
  bool transfer(const uint8_t *tx, uint8_t *rx, size_t len) override {
    ++calls;
    if (fail_transfers) return false;      // simulated wiring/SPI fault
    // Simulated fault in the COMMAND path only: the status no-op still answers.
    // This isolates error propagation in the register access layer from the
    // BUSY probe that runs before it.
    if (fail_data_transfers && tx != nullptr && tx[0] != kCmdNone) return false;
    if (tx == nullptr || rx == nullptr) return false;
    if (len == 0) return true;
    registered = true;                     // a real chip always answers something
    switch (tx[0]) {
      case kCmdNone:
        // The status/command byte comes back on the no-op transfer; this is
        // where a real SX1280 reports BUSY. Counted: the test can see the wire.
        if (len != 1) return false;
        // Hard cap: if the driver ever loses its bound, the suite FAILS here
        // instead of hanging the CI runner forever.
        if (++perms > kProbeLimit) return false;
        rx[0] = read_reg(kRegStatus);
        break;
      case kCmdWriteSingle:
        // opcode + addrH + addrL + data
        if (len != 4) return false;
        regs[(uint16_t)(((uint16_t)tx[1] << 8) | tx[2])] = tx[3];
        break;
      case kCmdReadSingle: {
        if (len != 4) return false;
        rx[2] = 0x00;  // command frame status byte
        rx[3] = read_reg(((uint16_t)tx[1] << 8) | tx[2]);
        break;
      }
      case kCmdWriteBurst: {
        if (len < 3) return false;
        const uint16_t a = (uint16_t)(((uint16_t)tx[1] << 8) | tx[2]);
        const size_t n = len - 3;
        for (size_t i = 0; i < n; ++i) regs[(uint16_t)(a + i)] = tx[3 + i];
        break;
      }
      case kCmdReadBurst: {
        if (len < 3) return false;
        const uint16_t a = (uint16_t)(((uint16_t)tx[1] << 8) | tx[2]);
        rx[2] = 0x00;
        const size_t n = len - 3;
        for (size_t i = 0; i < n; ++i) rx[3 + i] = read_reg((uint16_t)(a + i));
        break;
      }
      default:
        return false;  // unknown opcode
    }
    return true;
  }

  void cs_select(bool active) override {
    ++cs_calls;
    if (active) {
      if (!cs_high) ++cs_double_assert;  // nested select: a real bug
      ++cs_assert;
      cs_high = false;
    } else {
      cs_high = true;
    }
  }

  uint32_t millis() override {
    // 0 when frozen (a dead clock), else now, now+step, now+2*step, ...
    if (now == 0) return 0;
    const uint32_t t = now;
    now += step;
    return t;
  }

  void delay_ms(uint32_t ms) override { slept += ms; }

  // -- fixture knobs -------------------------------------------------------
  bool busy() const { return (regs.count(kRegStatus) ? regs.at(kRegStatus) : 0) & 0x80; }
  void set_busy(bool b) {
    regs[kRegStatus] = (uint8_t)(b ? (read_reg(kRegStatus) | 0x80)
                                   : (read_reg(kRegStatus) & (uint8_t)~0x80));
  }
  void set_reg(uint16_t a, uint8_t v) { regs[a] = v; }
  uint8_t get_reg(uint16_t a) const { return regs.count(a) ? regs.at(a) : 0; }
  bool was_registered() const { return registered; }
  bool cs_at_rest() const { return cs_high; }

  bool fail_transfers = false;
  bool fail_data_transfers = false;
  uint64_t now = 1000;  // "powered on" a second ago
  uint32_t step = 0;    // 0 = clock frozen

  size_t calls = 0;
  size_t cs_assert = 0;
  size_t cs_calls = 0;
  size_t cs_double_assert = 0;
  uint32_t perms = 0;  // no-op/status probes seen on the wire
  uint32_t slept = 0;
  std::map<uint16_t, uint8_t> regs;

 private:
  uint8_t read_reg(uint16_t a) const {
    if (a >= kRegEnd) return 0;  // unmapped reads as 0
    return regs.count(a) ? regs.at(a) : 0;
  }
  bool registered = false;
  bool cs_high = true;
};

// ---------------------------------------------------------------------------
// Fixture: a complete Config, and a DIFFERENT one to prove it is really read.
// ---------------------------------------------------------------------------
static Config configA() {
  Config c{};
  c.modulation = Modulation::Lora;
  c.frequency_hz = 2440000000u;
  c.bandwidth_hz = 812000u;
  c.spreading_factor = 12;
  c.coding_rate = 8;
  c.tx_power_dbm = 13;
  c.preamble_symbols = 16;
  c.crc_on = true;
  return c;
}

static Config configB() {
  Config c{};
  c.modulation = Modulation::Flrc;
  c.frequency_hz = 2400000000u;
  c.bandwidth_hz = 0xE3630Cu;  // a value never written by configA
  c.spreading_factor = 5;
  c.coding_rate = 5;
  c.tx_power_dbm = -4;
  c.preamble_symbols = 0x1000;
  c.crc_on = false;
  return c;
}

static bool sameConfig(const Config &a, const Config &b) {
  return a.modulation == b.modulation && a.frequency_hz == b.frequency_hz &&
         a.bandwidth_hz == b.bandwidth_hz &&
         a.spreading_factor == b.spreading_factor &&
         a.coding_rate == b.coding_rate &&
         a.tx_power_dbm == b.tx_power_dbm &&
         a.preamble_symbols == b.preamble_symbols && a.crc_on == b.crc_on;
}

static RadioCore *make(FakeSpi &bus) { return new RadioCore(&bus); }

// ---------------------------------------------------------------------------
void run_tests() {
  CASE("the SX1280 descriptor is data: status/version/rssi/snr positions");
  {
    const auto &d = descriptorFor(balloon::radio::Device::Sx1280);
    CHECK_EQ((int)d.reg_status, kRegStatus);
    CHECK_EQ((int)d.reg_rssi, kRegRssi);
    CHECK_EQ((int)d.reg_snr, kRegSnr);
    CHECK(d.name != nullptr);
    CHECK_EQ((int)d.busy_bit, 0x80);
    CHECK_EQ((int)d.config_base, 0x0040);
    CHECK(d.config_len > 0);
    // The descriptor must be usable without touching hardware.
    CHECK_EQ((int)balloon::radio::Device::Sx1280, 0);
  }

  CASE("read_reg issues a CS-asserted single read at the right address");
  {
    FakeSpi bus;
    RadioCore *r = make(bus);
    bus.set_reg(0x0024, 0x5A);
    uint8_t v = 0;
    CHECK(r->bus_read_reg(0x0024, &v) == Result::Ok);
    CHECK_EQ(v, 0x5A);
    CHECK(bus.cs_assert > 0);
    CHECK(bus.cs_at_rest());
    CHECK_EQ(bus.cs_double_assert, 0u);
    delete r;
  }

  CASE("write_reg then read_reg lands in the register file");
  {
    FakeSpi bus;
    RadioCore *r = make(bus);
    CHECK(r->bus_write_reg(0x0025, 0xC3) == Result::Ok);
    uint8_t v = 0;
    CHECK(r->bus_read_reg(0x0025, &v) == Result::Ok);
    CHECK_EQ(v, 0xC3);
    delete r;
  }

  CASE("burst write/read is byte-exact across a 32-byte block");
  {
    FakeSpi bus;
    RadioCore *r = make(bus);
    uint8_t out[32];
    for (int i = 0; i < 32; ++i) out[i] = (uint8_t)(0xA0 + i);
    // 0x0020..0x003F: clear of the status register (0x0010), the statistics
    // registers and the config image at 0x0040.
    CHECK(r->bus_write_burst(0x0020, out, sizeof out) == Result::Ok);
    uint8_t in[32];
    for (int i = 0; i < 32; ++i) in[i] = 0;
    CHECK(r->bus_read_burst(0x0020, in, sizeof in) == Result::Ok);
    CHECK(std::memcmp(out, in, sizeof out) == 0);
    // and each byte really is at its own address
    for (int i = 0; i < 32; ++i) CHECK_EQ(bus.get_reg((uint16_t)(0x20 + i)), out[i]);
    CHECK_EQ(bus.get_reg(kRegStatus), 0x00);  // the status register was untouched
    delete r;
  }

  CASE("acquire/release ownership is exclusive");
  {
    FakeSpi bus;
    RadioCore *r = make(bus);
    CHECK(!r->is_acquired());
    CHECK(r->release() == Result::NotAcquired);  // release without acquire
    CHECK(r->acquire(0) == Result::Ok);
    CHECK(r->is_acquired());
    CHECK(r->acquire(0) == Result::Busy);  // second owner refused
    CHECK(r->release() == Result::Ok);
    CHECK(!r->is_acquired());
    CHECK(r->release() == Result::NotAcquired);  // double release
    CHECK(r->acquire(0) == Result::Ok);          // and it is reusable
    delete r;
  }

  CASE("acquire(timeout_ms=0) must not block");
  {
    FakeSpi bus;
    bus.step = 50;
    RadioCore *r = make(bus);
    const uint64_t before = bus.now;
    CHECK(r->acquire(0) == Result::Ok);
    CHECK_EQ(bus.now, before);  // no clock advance => no waiting loop
    CHECK_EQ(bus.slept, 0u);
    delete r;
  }

  CASE("guarded ops need ownership: NotAcquired before acquire()");
  {
    FakeSpi bus;
    RadioCore *r = make(bus);
    CHECK(r->reset() == Result::NotAcquired);
    CHECK(r->configure(configA()) == Result::NotAcquired);
    Config back{};
    CHECK(r->read_config(&back) == Result::NotAcquired);
    CHECK(r->send(nullptr, 0) == Result::NotAcquired);
    CHECK(r->set_rx_continuous(true) == Result::NotAcquired);
    delete r;
  }

  CASE("HOME-RUN: configure() then read_config() round-trips bit-exactly");
  {
    FakeSpi bus;
    RadioCore *r = make(bus);
    CHECK(r->acquire(0) == Result::Ok);
    const Config cfg = configA();
    CHECK(r->configure(cfg) == Result::Ok);

    Config back{};
    CHECK(r->read_config(&back) == Result::Ok);
    CHECK(sameConfig(back, cfg));
    CHECK(back.modulation == cfg.modulation);
    CHECK_EQ(back.frequency_hz, cfg.frequency_hz);
    CHECK_EQ(back.bandwidth_hz, cfg.bandwidth_hz);
    CHECK_EQ(back.spreading_factor, cfg.spreading_factor);
    CHECK_EQ(back.coding_rate, cfg.coding_rate);
    CHECK_EQ(back.tx_power_dbm, cfg.tx_power_dbm);
    CHECK_EQ(back.preamble_symbols, cfg.preamble_symbols);
    CHECK_EQ(back.crc_on, cfg.crc_on);

    // The image really is on the bus: the exact 18 bytes, in order, at the
    // descriptor's config_base. (B1, version 1, modulation, freq LE32,
    // bw LE32, sf, cr, tx, preamble LE16, crc, xor-checksum = AA.)
    const auto &d = descriptorFor(balloon::radio::Device::Sx1280);
    CHECK(d.config_len >= 18);
    CHECK_EQ(bus.get_reg(0x0040), 0xB1);
    CHECK_EQ(bus.get_reg(0x0041), 0x01);
    CHECK_EQ(bus.get_reg(0x0042), (int)Modulation::Lora);
    CHECK_EQ(bus.get_reg(0x0043), 0x00);
    CHECK_EQ(bus.get_reg(0x0044), 0x72);
    CHECK_EQ(bus.get_reg(0x0045), 0x6F);
    CHECK_EQ(bus.get_reg(0x0046), 0x91);
    CHECK_EQ(bus.get_reg(0x0047), 0xE0);
    CHECK_EQ(bus.get_reg(0x0048), 0x63);
    CHECK_EQ(bus.get_reg(0x0049), 0x0C);
    CHECK_EQ(bus.get_reg(0x004A), 0x00);
    CHECK_EQ(bus.get_reg(0x004B), 0x0C);
    CHECK_EQ(bus.get_reg(0x004C), 0x08);
    CHECK_EQ(bus.get_reg(0x004D), 0x0D);
    CHECK_EQ(bus.get_reg(0x004E), 0x10);
    CHECK_EQ(bus.get_reg(0x004F), 0x00);
    CHECK_EQ(bus.get_reg(0x0050), 0x01);
    CHECK_EQ(bus.get_reg(0x0051), 0xAA);  // read_config() checks this itself
    delete r;
  }

  CASE("COUNTER-TEST: read_config reports what is ON THE BUS, not what was written");
  {
    FakeSpi bus;
    RadioCore *r = make(bus);
    CHECK(r->acquire(0) == Result::Ok);
    const auto &d = descriptorFor(balloon::radio::Device::Sx1280);
    CHECK(r->configure(configA()) == Result::Ok);

    // Another host (or a glitch) changes one byte of the stored image...
    const uint16_t freq_lo = (uint16_t)(d.config_base + 3);
    bus.set_reg(freq_lo, (uint8_t)(bus.get_reg(freq_lo) ^ 0x01));
    // ...and repairs the trailing checksum, so an integrity check alone cannot
    // tell the difference. Only reading the bus back can.
    uint8_t x = 0;
    for (uint16_t i = 0; i + 1 < d.config_len; ++i)
      x = (uint8_t)(x ^ bus.get_reg((uint16_t)(d.config_base + i)));
    bus.set_reg((uint16_t)(d.config_base + d.config_len - 1), x);

    Config back{};
    CHECK(r->read_config(&back) == Result::Ok);
    CHECK(back.frequency_hz != 2440000000u);  // RAM shadow must not shadow the bus
    CHECK_EQ(back.frequency_hz, 2440000001u);
    delete r;
  }

  CASE("COUNTER-TEST: a non-live (checksum-broken) image is BadArgument, not Ok");
  {
    FakeSpi bus;
    RadioCore *r = make(bus);
    CHECK(r->acquire(0) == Result::Ok);
    const auto &d = descriptorFor(balloon::radio::Device::Sx1280);
    CHECK(r->configure(configA()) == Result::Ok);
    bus.set_reg((uint16_t)(d.config_base + 6), 0x00);  // scramble the image (freq)
    Config back{};
    CHECK(r->read_config(&back) != Result::Ok);
    delete r;
  }

  CASE("COUNTER-TEST: read_config around a DIFFERENT configure() follows the device");
  {
    FakeSpi bus;
    RadioCore *r = make(bus);
    CHECK(r->acquire(0) == Result::Ok);
    CHECK(r->configure(configA()) == Result::Ok);
    const Config cfg_b = configB();
    CHECK(r->configure(cfg_b) == Result::Ok);
    Config back{};
    CHECK(r->read_config(&back) == Result::Ok);
    CHECK(sameConfig(back, cfg_b));
    CHECK(!sameConfig(back, configA()));
    delete r;
  }

  CASE("COUNTER-TEST: a BUSY device that never clears yields Timeout, bounded");
  {
    FakeSpi bus;
    bus.step = 50;          // a clock that advances 50 ms per query
    bus.set_busy(true);
    RadioCore *r = make(bus);
    CHECK(r->acquire(0) == Result::Ok);
    const size_t calls_before = bus.calls;
    CHECK(r->configure(configA()) == Result::Timeout);  // never an infinite loop
    CHECK(bus.calls > calls_before);
    CHECK(bus.perms > 0);   // it actually tried to wait, not just gave up
    CHECK(bus.perms < 40);  // ...and gave up: bounded
    Config back{};
    CHECK(r->read_config(&back) == Result::Timeout);  // still never Ok
    delete r;
  }

  CASE("COUNTER-TEST: BUSY-forever with a FROZEN clock still terminates");
  {
    // millis() never advances, so an elapsed-time-only bound would spin for
    // ever. This case was written after the first green run hung here for
    // real: the burst test had clobbered the status register, the fixture was
    // BUSY, and the clock was frozen. The driver must bound the loop by
    // iterations too, not only by time.
    FakeSpi bus;
    bus.step = 0;  // clock stands still: this is what a wedged device looks like
    bus.set_busy(true);
    RadioCore *r = make(bus);
    CHECK(r->acquire(0) == Result::Ok);
    CHECK(r->configure(configA()) == Result::Timeout);
    CHECK(r->reset() == Result::Timeout);
    CHECK(r->send((const uint8_t *)"x", 1) == Result::Timeout);
    Config back{};
    CHECK(r->read_config(&back) == Result::Timeout);
    CHECK(bus.perms > 0);      // it really polled
    CHECK(bus.perms < 500);    // ...and gave up
    delete r;
  }

  CASE("a BUSY device that clears on its own is fine (Ok, within budget)");
  {
    FakeSpi bus;
    bus.step = 50;
    bus.set_busy(true);     // holds BUSY for the first millis() reads...
    RadioCore *r = make(bus);
    CHECK(r->acquire(0) == Result::Ok);
    // (the fixture is static; this case pins that readiness is *polled*, i.e.
    //  the ready path costs exactly one status read when not busy)
    bus.set_busy(false);
    const size_t before = bus.calls;
    CHECK(r->reset() == Result::Ok);
    CHECK_EQ(bus.perms, 1u);
    CHECK(bus.calls >= before);
    delete r;
  }

  CASE("COUNTER-TEST: an SPI transfer failure is BusError, never Ok");
  {
    FakeSpi bus;
    RadioCore *r = make(bus);
    CHECK(r->acquire(0) == Result::Ok);
    bus.fail_transfers = true;
    uint8_t v = 0;
    CHECK(r->bus_read_reg(0x0024, &v) == Result::BusError);
    CHECK(r->bus_write_reg(0x0024, 0x11) == Result::BusError);
    Config back{};
    CHECK(r->read_config(&back) != Result::Ok);
    CHECK(r->configure(configA()) != Result::Ok);
    bus.fail_transfers = false;
    CHECK(r->bus_read_reg(0x0024, &v) == Result::Ok);

    // Same, but with the status probe still answering, so the failure has to be
    // caught by the register-access layer itself. Without this, an
    // implementation that swallowed the command-transfer failure but kept the
    // BUSY probe would pass.
    bus.fail_data_transfers = true;
    CHECK(r->bus_read_reg(0x0024, &v) == Result::BusError);
    CHECK(r->bus_write_reg(0x0024, 0x11) == Result::BusError);
    CHECK(r->read_config(&back) != Result::Ok);
    CHECK(r->configure(configA()) != Result::Ok);
    bus.fail_data_transfers = false;
    CHECK(r->bus_read_reg(0x0024, &v) == Result::Ok);
    delete r;
  }

  CASE("bad arguments are refused instead of propagated");
  {
    FakeSpi bus;
    RadioCore *r = make(bus);
    CHECK(r->acquire(0) == Result::Ok);
    CHECK(r->bus_read_reg(0x0010, nullptr) == Result::BadArgument);
    CHECK(r->bus_write_burst(0x0000, nullptr, 4) == Result::BadArgument);
    CHECK(r->bus_read_burst(0x0000, nullptr, 4) == Result::BadArgument);
    CHECK(r->read_config(nullptr) == Result::BadArgument);
    CHECK(r->acquire(0) == Result::Busy);  // and nothing above broke ownership
    delete r;
  }

  CASE("send/receive/rssi report a definite Result and keep their promises");
  {
    FakeSpi bus;
    RadioCore *r = make(bus);
    CHECK(r->acquire(0) == Result::Ok);
    CHECK(r->set_rx_continuous(true) == Result::Ok);
    CHECK(r->send(nullptr, 4) == Result::BadArgument);  // null payload
    CHECK(r->send((const uint8_t *)"abc", 3) == Result::Ok);

    // "nothing pending" must be Ok + 0, per the frozen header.
    size_t n = 42;
    uint8_t out[8];
    bus.now = 0;  // frozen clock: no packet can ever arrive
    CHECK(r->receive(out, sizeof out, &n, 1) == Result::Ok);
    CHECK_EQ(n, 0u);
    CHECK(r->receive(out, sizeof out, nullptr, 1) == Result::BadArgument);

    bus.set_reg(kRegRssi, 0xB4);  // -76 dBm, two's complement
    int16_t dbm = 0;
    CHECK(r->get_rssi_dbm(&dbm) == Result::Ok);
    CHECK_EQ(dbm, -76);

    bus.set_reg(kRegSnr, 0x0A);
    int8_t snr = 0;
    CHECK(r->get_snr_db(&snr) == Result::Ok);
    CHECK_EQ(snr, 10);
    delete r;
  }

  CASE("the factory is the only thing not host-tested (no make_radio_hal here)");
  {
    // This suite deliberately defines no make_radio_hal: the library carries a
    // host stub, the device build supplies the real one.
    CHECK(true);
  }
}

TEST_MAIN()
