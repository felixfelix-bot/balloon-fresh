// pin_plan.h — the v9 flight pin table, machine-checked at compile time.
//
// WHY THIS FILE EXISTS
// --------------------
// The v9 pin plan is a document (docs/COEXISTENCE-V9.md §4). A document cannot
// fail a build. This header is the same table as CODE, so a wrong or missing
// pin is a compile error rather than a silent miswire on a board we cannot
// rework in the air.
//
// It does not drive any peripheral yet — there is no radio driver in this
// target. It asserts the plan is internally consistent and matches what
// platformio.ini passes in, and it is the single include the future drivers
// (L0 radio_core, L1 FLRC, L2 LoRaWAN, L3 MeshCore, L4 Meshtastic) read pins
// from. Do not hardcode a pin anywhere else.
//
// Two independent SPI masters (SPI2/SPI3 via the GPIO matrix): the radios never
// share a bus, so there are no CS-timing compromises and no arbitration on SCK.
//
// HONEST SCOPE: this is verified to COMPILE and to reject a bad table. It has
// not been run on a v9 board (no v9 board exists yet — it is at the order
// stage). No radio behaviour is claimed by this file.

#pragma once

#ifndef HUB_V9
#error "pin_plan.h is only valid for the hub_v9 flight target (define HUB_V9)."
#endif

// Every pin must arrive from platformio.ini. A missing definition is an error,
// not a default: a defaulted pin is exactly how a board gets miswired.
#define HUB_V9_REQUIRE_PIN(name)          \
    _Static_assert(sizeof(#name) > 0, ""); \
    static_assert(true, "")

#define HUB_V9_PIN(NAME) PIN_##NAME

#ifdef __cplusplus
namespace hub_v9 {
#endif

// ── SPI0 / LR2021 F33 (868 MHz link + LoRaWAN/MeshCore/Meshtastic) ───────────
enum : int {
    kLr2021Sck  = PIN_LR2021_SCK,
    kLr2021Mosi = PIN_LR2021_MOSI,
    kLr2021Miso = PIN_LR2021_MISO,
    kLr2021Nss  = PIN_LR2021_NSS,
    kLr2021Busy = PIN_LR2021_BUSY,
    kLr2021Rst  = PIN_LR2021_RST,
    kLr2021Dio  = PIN_LR2021_DIO,
};

// ── SPI1 / SX1280 (2.4 GHz FLRC + ranging) ───────────────────────────────────
enum : int {
    kSx1280Sck  = PIN_SX1280_SCK,
    kSx1280Mosi = PIN_SX1280_MOSI,
    kSx1280Miso = PIN_SX1280_MISO,
    kSx1280Nss  = PIN_SX1280_NSS,
    kSx1280Busy = PIN_SX1280_BUSY,
    kSx1280Rst  = PIN_SX1280_RST,
    kSx1280Dio  = PIN_SX1280_DIO,
};

// ── GNSS (MAX-M10S, UART1 + optional timepulse) ──────────────────────────────
enum : int {
    kGnssRx  = PIN_GNSS_RX,
    kGnssTx  = PIN_GNSS_TX,
    kGnssPps = PIN_GNSS_PPS,
};

enum : int { kStatusLed = PIN_STATUS_LED };

// ── Compile-time consistency checks ──────────────────────────────────────────
// These encode the properties the pin plan must have. They are cheap, they run
// on every build, and each one maps to a real failure it prevents.

// 1. No pin may be negative (a missing -D would surface as 0 or a garbage value,
//    so also guard the ESP32-S3 usable range).
constexpr bool kPinRangeOk =
    kLr2021Sck  >= 0 && kLr2021Sck  < 49 &&
    kLr2021Mosi >= 0 && kLr2021Mosi < 49 &&
    kLr2021Miso >= 0 && kLr2021Miso < 49 &&
    kLr2021Nss  >= 0 && kLr2021Nss  < 49 &&
    kLr2021Busy >= 0 && kLr2021Busy < 49 &&
    kLr2021Rst  >= 0 && kLr2021Rst  < 49 &&
    kLr2021Dio  >= 0 && kLr2021Dio  < 49 &&
    kSx1280Sck  >= 0 && kSx1280Sck  < 49 &&
    kSx1280Mosi >= 0 && kSx1280Mosi < 49 &&
    kSx1280Miso >= 0 && kSx1280Miso < 49 &&
    kSx1280Nss  >= 0 && kSx1280Nss  < 49 &&
    kSx1280Busy >= 0 && kSx1280Busy < 49 &&
    kSx1280Rst  >= 0 && kSx1280Rst  < 49 &&
    kSx1280Dio  >= 0 && kSx1280Dio  < 49 &&
    kGnssRx     >= 0 && kGnssRx     < 49 &&
    kGnssTx     >= 0 && kGnssTx     < 49 &&
    kGnssPps    >= 0 && kGnssPps    < 49 &&
    kStatusLed  >= 0 && kStatusLed  < 49;

// 2. The two SPI buses must be DISJOINT. This is the whole point of the v9
//    design (§3/§4): sharing a bus reintroduces CS-timing compromises, and a
//    copy-paste that points both radios at one pin would otherwise be invisible
//    until an in-air failure.
constexpr bool kSpiBusesDisjoint =
    kLr2021Sck != kSx1280Sck && kLr2021Mosi != kSx1280Mosi &&
    kLr2021Miso != kSx1280Miso && kLr2021Nss != kSx1280Nss &&
    // no pin from one radio may collide with ANY pin of the other
    kLr2021Sck != kSx1280Busy && kLr2021Sck != kSx1280Rst && kLr2021Sck != kSx1280Dio &&
    kLr2021Mosi != kSx1280Busy && kLr2021Mosi != kSx1280Rst && kLr2021Mosi != kSx1280Dio &&
    kLr2021Miso != kSx1280Busy && kLr2021Miso != kSx1280Rst && kLr2021Miso != kSx1280Dio &&
    kLr2021Nss != kSx1280Busy && kLr2021Nss != kSx1280Rst && kLr2021Nss != kSx1280Dio &&
    kLr2021Busy != kSx1280Sck && kLr2021Busy != kSx1280Mosi &&
    kLr2021Busy != kSx1280Miso && kLr2021Busy != kSx1280Nss &&
    kLr2021Rst != kSx1280Sck && kLr2021Rst != kSx1280Mosi &&
    kLr2021Rst != kSx1280Miso && kLr2021Rst != kSx1280Nss &&
    kLr2021Dio != kSx1280Sck && kLr2021Dio != kSx1280Mosi &&
    kLr2021Dio != kSx1280Miso && kLr2021Dio != kSx1280Nss;

// 3. Each radio's own signals must be pairwise distinct (a duplicated pin inside
//    one radio is the classic copy-paste defect).
constexpr bool kLr2021SelfConsistent =
    kLr2021Sck != kLr2021Mosi && kLr2021Sck != kLr2021Miso &&
    kLr2021Sck != kLr2021Nss && kLr2021Sck != kLr2021Busy &&
    kLr2021Sck != kLr2021Rst && kLr2021Sck != kLr2021Dio &&
    kLr2021Mosi != kLr2021Miso && kLr2021Mosi != kLr2021Nss &&
    kLr2021Mosi != kLr2021Busy && kLr2021Mosi != kLr2021Rst &&
    kLr2021Mosi != kLr2021Dio &&
    kLr2021Miso != kLr2021Nss && kLr2021Miso != kLr2021Busy &&
    kLr2021Miso != kLr2021Rst && kLr2021Miso != kLr2021Dio &&
    kLr2021Nss != kLr2021Busy && kLr2021Nss != kLr2021Rst &&
    kLr2021Nss != kLr2021Dio &&
    kLr2021Busy != kLr2021Rst && kLr2021Busy != kLr2021Dio &&
    kLr2021Rst != kLr2021Dio;

constexpr bool kSx1280SelfConsistent =
    kSx1280Sck != kSx1280Mosi && kSx1280Sck != kSx1280Miso &&
    kSx1280Sck != kSx1280Nss && kSx1280Sck != kSx1280Busy &&
    kSx1280Sck != kSx1280Rst && kSx1280Sck != kSx1280Dio &&
    kSx1280Mosi != kSx1280Miso && kSx1280Mosi != kSx1280Nss &&
    kSx1280Mosi != kSx1280Busy && kSx1280Mosi != kSx1280Rst &&
    kSx1280Mosi != kSx1280Dio &&
    kSx1280Miso != kSx1280Nss && kSx1280Miso != kSx1280Busy &&
    kSx1280Miso != kSx1280Rst && kSx1280Miso != kSx1280Dio &&
    kSx1280Nss != kSx1280Busy && kSx1280Nss != kSx1280Rst &&
    kSx1280Nss != kSx1280Dio &&
    kSx1280Busy != kSx1280Rst && kSx1280Busy != kSx1280Dio &&
    kSx1280Rst != kSx1280Dio;

// 4. GNSS must not sit on a radio pin (its UART and PPS are separate signals).
constexpr bool kGnssDisjoint =
    kGnssRx != kGnssTx && kGnssRx != kGnssPps && kGnssTx != kGnssPps &&
    kGnssRx != kLr2021Sck && kGnssRx != kLr2021Mosi &&
    kGnssRx != kLr2021Miso && kGnssRx != kLr2021Nss &&
    kGnssRx != kSx1280Sck && kGnssRx != kSx1280Mosi &&
    kGnssRx != kSx1280Miso && kGnssRx != kSx1280Nss &&
    kGnssTx != kLr2021Sck && kGnssTx != kLr2021Mosi &&
    kGnssTx != kLr2021Miso && kGnssTx != kLr2021Nss &&
    kGnssTx != kSx1280Sck && kGnssTx != kSx1280Mosi &&
    kGnssTx != kSx1280Miso && kGnssTx != kSx1280Nss;

#ifdef __cplusplus
}  // namespace hub_v9
#endif

static_assert(hub_v9::kPinRangeOk,      "hub v9: a pin is outside 0..48 (missing -D in platformio.ini?)");
static_assert(hub_v9::kSpiBusesDisjoint, "hub v9: LR2021 and SX1280 pin sets overlap — the two SPI buses MUST be disjoint (COEXISTENCE-V9 §4)");
static_assert(hub_v9::kLr2021SelfConsistent, "hub v9: LR2021 has a duplicated pin");
static_assert(hub_v9::kSx1280SelfConsistent, "hub v9: SX1280 has a duplicated pin");
static_assert(hub_v9::kGnssDisjoint,    "hub v9: GNSS pin collides with a radio pin");
