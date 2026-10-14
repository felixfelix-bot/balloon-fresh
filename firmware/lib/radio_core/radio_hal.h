// L0 (frozen contract) - radio hardware abstraction.
//
// FROZEN INTERFACE. radio_core implements it; the protocol layers (LoRaWAN,
// MeshCore, Meshtastic) consume it and MUST NOT depend on radio_core's
// implementation or link its .cpp. They code against THIS header and test with
// their own fake. That is what lets the layers be built independently.
//
// Every method is blocking-with-timeout and returns a Result: no exceptions, no
// hidden state, and no assumption that a call succeeded.
//
// BOARD NOTE (hub v9): there is ONE radio (SX1280 for FLRC). LR2021 support is
// the target for the LoRaWAN/MeshCore/Meshtastic layers. Multiple protocol
// stacks sharing one radio is exactly why acquire()/release() exist: without
// them the stacks fight over SPI and the TCXO.
#pragma once

#include <cstddef>
#include <cstdint>

namespace balloon {
namespace radio {

enum class Result : uint8_t {
  Ok = 0,
  Timeout,      // device never became ready
  BusError,     // SPI transfer failed
  NotAcquired,  // forgot acquire(), or another owner holds it
  Busy,         // another owner holds the radio
  BadArgument,
};

// Modulation the caller wants. The HAL owns the mapping to device registers.
enum class Modulation : uint8_t { Flrc, Lora, Fsk };

struct Config {
  Modulation modulation;
  uint32_t frequency_hz;
  uint32_t bandwidth_hz;      // LoRa/FLRC bandwidth
  uint8_t  spreading_factor;  // LoRa only (5..12); ignored otherwise
  uint8_t  coding_rate;       // 5..8 => 4/5..4/8
  int8_t   tx_power_dbm;
  uint16_t preamble_symbols;
  bool     crc_on;
};

// Raw SPI transport, injected so the HAL is host-testable with a register-file
// fake. Implementations must be full-duplex single-byte or block transfers.
class SpiBus {
 public:
  virtual ~SpiBus() = default;
  virtual bool transfer(const uint8_t *tx, uint8_t *rx, size_t len) = 0;
  virtual void cs_select(bool active) = 0;
  virtual uint32_t millis() = 0;   // monotonic clock for timeouts
  virtual void delay_ms(uint32_t ms) = 0;
};

// The radio HAL. One device, many would-be users.
class RadioHal {
 public:
  virtual ~RadioHal() = default;

  // Exclusive ownership. A protocol stack MUST acquire before any configure(),
  // send(), or receive(). Returns Busy if another owner holds it.
  virtual Result acquire(uint32_t timeout_ms) = 0;
  virtual Result release() = 0;
  virtual bool   is_acquired() const = 0;

  virtual Result reset() = 0;
  virtual Result configure(const Config &cfg) = 0;
  virtual Result read_config(Config *out) const = 0;  // read-back verification

  virtual Result send(const uint8_t *data, size_t len) = 0;
  // Returns bytes written to out, or 0 when nothing is pending (Ok + 0).
  virtual Result receive(uint8_t *out, size_t max_len, size_t *out_len,
                         uint32_t timeout_ms) = 0;

  virtual Result set_rx_continuous(bool on) = 0;
  virtual Result get_rssi_dbm(int16_t *out) const = 0;
  virtual Result get_snr_db(int8_t *out) const = 0;
};

// Factory the platform provides. Host tests supply their own fake HAL and
// bypass this entirely.
RadioHal *make_radio_hal(SpiBus *bus);

}  // namespace radio
}  // namespace balloon
