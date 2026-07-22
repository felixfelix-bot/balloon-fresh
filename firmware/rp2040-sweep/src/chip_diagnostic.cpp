/*
 * chip_diagnostic.cpp — Identify what RF chip is actually on the board
 * Reads raw SPI from both SX1280 and LR2021 protocols
 */
#include <Arduino.h>
#include <SPI.h>

#define SCK_PIN   2
#define MOSI_PIN  3
#define MISO_PIN  4
#define CS_PIN    5
#define BUSY_PIN  6
#define IRQ_PIN   7
#define RST_PIN   8

static SPIClassRP2040 spiRf(spi0, MISO_PIN, CS_PIN, SCK_PIN, MOSI_PIN);
static SPISettings spiSettings(8000000, MSBFIRST, SPI_MODE0); // 8MHz for safety

void setup() {
    Serial.begin(115200);
    Serial1.setTX(12);
    Serial1.setRX(13);
    Serial1.begin(115200);
    delay(2000);

    pinMode(CS_PIN, OUTPUT);
    digitalWrite(CS_PIN, HIGH);
    pinMode(BUSY_PIN, INPUT);
    pinMode(IRQ_PIN, INPUT);
    pinMode(RST_PIN, OUTPUT);

    Serial1.println("\n\n=== CHIP DIAGNOSTIC ===");
    Serial1.println("Send any char to start...");
    // Wait for serial input OR timeout after 10s
    uint32_t waitStart = millis();
    while (!Serial1.available() && (millis() - waitStart < 10000)) {
        delay(100);
    }
    while (Serial1.available()) Serial1.read(); // flush
    Serial1.println("Starting diagnostic...");
    delay(100);
    Serial1.printf("PINS: BUSY=%d IRQ=%d\n", digitalRead(BUSY_PIN), digitalRead(IRQ_PIN));

    // Hardware reset
    Serial1.println("Resetting chip...");
    digitalWrite(RST_PIN, LOW);
    delay(10);
    digitalWrite(RST_PIN, HIGH);
    delay(50);

    Serial1.printf("After reset: BUSY=%d\n", digitalRead(BUSY_PIN));

    spiRf.begin();
    spiRf.beginTransaction(spiSettings);

    // === Try SX1280 protocol: read status ===
    // SX1280 command 0x94 = read register, addr 0x0340 = version
    Serial1.println("\n--- SX1280 PROTOCOL ---");
    digitalWrite(CS_PIN, LOW);
    delay(1);
    uint8_t r0 = spiRf.transfer(0x94);  // read register
    uint8_t r1 = spiRf.transfer(0x00);  // addr MSB
    uint8_t r2 = spiRf.transfer(0x40);  // addr LSB
    spiRf.transfer(0x00);               // dummy
    uint8_t sx_ver = spiRf.transfer(0x00); // data
    digitalWrite(CS_PIN, HIGH);
    Serial1.printf("SX1280 version reg: 0x%02X\n", sx_ver);

    // SX1280 command 0xC0 = get status
    digitalWrite(CS_PIN, LOW);
    delay(1);
    spiRf.transfer(0xC0); // get status
    uint8_t sx_status = spiRf.transfer(0x00);
    digitalWrite(CS_PIN, HIGH);
    Serial1.printf("SX1280 status: 0x%02X\n", sx_status);

    // === Try LR2021 protocol: NOP then read status ===
    Serial1.println("\n--- LR2021 PROTOCOL ---");
    // Wait for BUSY low
    uint32_t timeout = millis();
    while (digitalRead(BUSY_PIN) && (millis() - timeout < 1000)) {}
    Serial1.printf("BUSY after wait: %d (waited %lu ms)\n", digitalRead(BUSY_PIN), millis() - timeout);

    digitalWrite(CS_PIN, LOW);
    delay(1);
    // LR2021 NOP = 0x00
    uint8_t nop_resp = spiRf.transfer(0x00);
    uint16_t status16 = (spiRf.transfer(0x00) << 8) | spiRf.transfer(0x00);
    digitalWrite(CS_PIN, HIGH);
    Serial1.printf("LR2021 NOP response: 0x%02X\n", nop_resp);
    Serial1.printf("LR2021 status16: 0x%04X\n", status16);

    // LR2021 get version: write command 0x00B0 (read at addr 0x00B0)
    // Actually LR2021 uses Set command for version: 0x53,0x01,0x18
    // Let's try read register at address 0x0089 (LR2021 version register)
    Serial1.println("\n--- LR2021 getVersion command ---");
    while (digitalRead(BUSY_PIN) && (millis() - timeout < 500)) {}
    digitalWrite(CS_PIN, LOW);
    delay(1);
    spiRf.transfer(0x53); // LR2021 get version command (similar to SX128x)
    uint8_t v_major = spiRf.transfer(0x00);
    uint8_t v_minor = spiRf.transfer(0x00);
    digitalWrite(CS_PIN, HIGH);
    Serial1.printf("LR2021 version: %d.%d (0x%02X, 0x%02X)\n", v_major, v_minor, v_major, v_minor);

    // Try raw MISO dump without CS (check if any data on MISO)
    Serial1.println("\n--- RAW SPI DUMP (10 bytes) ---");
    digitalWrite(CS_PIN, LOW);
    delay(1);
    for (int i = 0; i < 10; i++) {
        uint8_t b = spiRf.transfer(0x00);
        Serial1.printf("[%d] 0x%02X\n", i, b);
    }
    digitalWrite(CS_PIN, HIGH);

    spiRf.endTransaction();

    // Check BUSY pin behavior
    Serial1.println("\n--- BUSY PIN TEST ---");
    for (int i = 0; i < 10; i++) {
        Serial1.printf("BUSY sample %d: %d\n", i, digitalRead(BUSY_PIN));
        delay(100);
    }

    Serial1.println("\n=== DIAG COMPLETE ===");
}

void loop() {
    delay(10000);
}
