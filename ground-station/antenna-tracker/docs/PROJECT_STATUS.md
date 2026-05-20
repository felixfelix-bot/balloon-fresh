# Project Status (March 2026)

## Hardware
- Board: ESP32-WROOM-32 (rev v3.1)
- Motors: 2x 28BYJ-48 (half-step mode)
- Driver: ULN2003
- GPIO
  - Azimuth: 14, 27, 26, 25
  - Elevation: 33, 32, 18, 19

## Firmware
- Language: Rust
- Framework: esp-idf (v5.3)
- HAL: esp-idf-hal 0.45.x
- UART: UartDriver (UART0, GPIO1 TX / GPIO3 RX)

## Current State
- Builds cleanly (`make build`)
- Flashes successfully (`make flash`)
- Boots and reaches `app_main()`
- No watchdog resets
- Stepper control logic implemented
- UART command parsing implemented (`AZ <steps>`, `EL <steps>`)

System is stable and ready for feature expansion.
