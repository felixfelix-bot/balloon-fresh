// L0 - SX1280 register-map descriptor (DATA, not code).
//
// The driver logic in radio_core.cpp never mentions a register address: it asks
// this table. Swapping an SX1280 for an LR2021 is therefore a table, not a
// rewrite -- and the protocol layers on top never see either.
//
// VERIFICATION STATUS OF EVERY ADDRESS BELOW
// -----------------------------------------
// VERIFIED (authoritative): the *command* framing and the status semantics,
//   from Semtech SX1280 datasheet section 11 "SPI interface" via RadioLib
//   v7.6.0 src/modules/SX1280/SX1280.cpp + SX1280_commands.h, mirrored in this
//   repo in docs/lr2021-spi-command-reference.md (which documents the SX1280
//   side-by-side with the LR2021: write single 0x18 / read single 0x19 /
//   write burst 0x1A / read burst 0x1B; SX1280 SPI status is an 8-bit value
//   whose bit 7 is the BUSY/command-status bit; SX1280 IRQ status is 16-bit
//   while the LR2021's is 32-bit).
// UNVERIFIED: the two statistical registers 0x001A (RSSI) and 0x001B (SNR).
//   They are *plausible* (they sit in the 0x0018..0x001D status/statistics
//   bank, and the module's own readRssi() derives dBm from two such registers)
//   but I have NOT confirmed the exact addresses, and this repo carries no
//   SX1280 register table to confirm them against. They are recorded here as
//   the map's current belief, NOT asserted as fact: nothing in the flight path
//   depends on them yet (get_rssi_dbm/get_snr_db are for the bench console),
//   and a wrong value is caught the moment real silicon is attached.
//
// The config image region (0x0040..0x0051 + checksum) is a radio_core-owned
// scratch region, not a chip-defined location; it exists so configure() can
// write an image the same driver reads back. Nothing else may use it.
#pragma once

#include <cstdint>

#include "radio_core_internal.h"

namespace balloon {
namespace radio {
namespace sx1280 {

// SPI command framing (VERIFIED, datasheet 11.x / RadioLib).
constexpr uint8_t kCmdNone = 0x00;  // no-op: returns the status byte, nothing else
constexpr uint8_t kCmdWriteSingle = 0x18;
constexpr uint8_t kCmdReadSingle = 0x19;
constexpr uint8_t kCmdWriteBurst = 0x1A;
constexpr uint8_t kCmdReadBurst = 0x1B;

// Status register (VERIFIED semantics): bit 7 is the BUSY/command bit.
constexpr uint16_t kRegStatus = 0x0010;
constexpr uint8_t kBusyBit = 0x80;

// Statistics (UNVERIFIED addresses -- see the header comment above).
constexpr uint16_t kRegRssi = 0x001A;  // UNVERIFIED address
constexpr uint16_t kRegSnr = 0x001B;   // UNVERIFIED address

// radio_core config image scratch (driver-defined, not a chip register).
constexpr uint16_t kConfigBase = 0x0040;
constexpr uint8_t kConfigLen = kConfigImageBytes;  // 18 image + 1 checksum

// The descriptor. constexpr so it costs nothing at runtime.
constexpr DeviceDescriptor kMap{
    /*name=*/"SX1280",
    /*reg_status=*/kRegStatus,
    /*busy_bit=*/kBusyBit,
    /*reg_rssi=*/kRegRssi,
    /*reg_snr=*/kRegSnr,
    /*config_base=*/kConfigBase,
    /*config_len=*/kConfigLen,
    /*status_width=*/1,
    /*status_read_supported=*/true,
};

}  // namespace sx1280
}  // namespace radio
}  // namespace balloon
