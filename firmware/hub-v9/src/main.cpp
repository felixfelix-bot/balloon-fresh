// main.cpp — hub v9 flight carrier entry point.
//
// SCOPE, HONESTLY: this is a bring-up skeleton, not a flight firmware. It
// proves the flight target BUILDS and that the pin plan is machine-checked
// (src/pin_plan.h). It does NOT initialise the radios, because:
//
//   1. The radio drivers do not exist in this target yet. They are the
//      firmware/lib modules (L0 radio_core + L1-L4), landed as independently
//      tested libraries first (docs/SOFTWARE-PREPARE-LIST.md).
//   2. Bring-up order is RECEIVE-ONLY until a link closes (operator rule,
//      2026-10-14). Nothing here may transmit, and there is deliberately no
//      TX/ARM path to enable.
//
// So: no radio is claimed to work. This file exists so the flight target is
// real (buildable, CI-able) before drivers land on it.

#include <Arduino.h>

#include "pin_plan.h"

// The pin plan's static_asserts in pin_plan.h are the real content of this
// translation unit: they run at compile time and fail the build on a bad table.
// Referencing one symbol keeps the include from being elided and makes the
// intent explicit to a reader.
static constexpr int kLr2021Nss = hub_v9::kLr2021Nss;
static constexpr int kSx1280Nss = hub_v9::kSx1280Nss;

void setup() {
    Serial.begin(SERIAL_BAUD);
    delay(200);  // let USB-CDC enumerate before the banner

    Serial.println();
    Serial.println("HUB-V9 flight carrier — bring-up skeleton");
    Serial.println("RECEIVE-ONLY: no radio is initialised, no TX path exists.");

    // Print the pin table so a bench operator can compare it against the
    // netlist with their own eyes. This is a readout, not an initialisation.
    Serial.printf("pin plan  LR2021 nss=%d  SX1280 nss=%d\n", kLr2021Nss, kSx1280Nss);
    Serial.printf("  LR2021 SPI0  sck=%d mosi=%d miso=%d nss=%d busy=%d rst=%d dio=%d\n",
                  hub_v9::kLr2021Sck, hub_v9::kLr2021Mosi, hub_v9::kLr2021Miso,
                  hub_v9::kLr2021Nss, hub_v9::kLr2021Busy, hub_v9::kLr2021Rst,
                  hub_v9::kLr2021Dio);
    Serial.printf("  SX1280 SPI1  sck=%d mosi=%d miso=%d nss=%d busy=%d rst=%d dio=%d\n",
                  hub_v9::kSx1280Sck, hub_v9::kSx1280Mosi, hub_v9::kSx1280Miso,
                  hub_v9::kSx1280Nss, hub_v9::kSx1280Busy, hub_v9::kSx1280Rst,
                  hub_v9::kSx1280Dio);
    Serial.printf("  GNSS UART1   rx=%d tx=%d pps=%d\n",
                  hub_v9::kGnssRx, hub_v9::kGnssTx, hub_v9::kGnssPps);

    pinMode(hub_v9::kStatusLed, OUTPUT);
    Serial.println("ready (no radios)");
}

void loop() {
    // Heartbeat only. A driver-less target must not pretend to do anything.
    digitalWrite(hub_v9::kStatusLed, !digitalRead(hub_v9::kStatusLed));
    delay(1000);
}
