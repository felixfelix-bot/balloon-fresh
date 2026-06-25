#ifndef LR2021_RP2040_PINS_H
#define LR2021_RP2040_PINS_H

// Pin assignments for RP2040-Zero coprocessor (Board B / ADR-015)
// Wiring guide: docs/adr/015-three-board-hardware-strategy.md

// SPI0 bus → LR2021
#define PIN_SPI_SCK     2    // GP2  → LR2021 Pin 5 (SCK)
#define PIN_SPI_MOSI    3    // GP3  → LR2021 Pin 4 (MOSI)
#define PIN_SPI_MISO    4    // GP4  → LR2021 Pin 3 (MISO)
#define PIN_SPI_CS      5    // GP5  → LR2021 Pin 6 (NSS)
#define PIN_BUSY        6    // GP6  → LR2021 Pin 7 (BUSY)
#define PIN_IRQ         7    // GP7  → LR2021 Pin 15 (DIO9)
#define PIN_RST         8    // GP8  → LR2021 Pin 14 (RST)

// UART1 → ESP32-C3
#define PIN_UART_TX     20   // GP20 → ESP32 GPIO1 (RX)
#define PIN_UART_RX     21   // GP21 ← ESP32 GPIO0 (TX)

// Onboard LED (RP2040-Zero: GP25 or GP16 depending on variant)
#define PIN_LED         25   // GP25 — standard Pico LED

#endif // LR2021_RP2040_PINS_H
