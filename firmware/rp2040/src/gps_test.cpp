/*
 * gps_test.cpp — GPS NMEA baud scanner
 * Uses Serial1 (GP0/GP1) for GPS input
 * Outputs via USB CDC Serial
 */

#include <Arduino.h>

void setup() {
  Serial.begin(115200);
  delay(3000);
  Serial.println("\n\n=== GPS BAUD SCAN ===");
  Serial.println("Testing baud rates on Serial1 (GP0/GP1)");
}

void tryBaud(unsigned long baud) {
  Serial.print("\n--- Trying ");
  Serial.print(baud);
  Serial.println(" ---");
  
  Serial1.end();
  delay(100);
  Serial1.begin(baud);
  delay(500);
  
  int bytes = 0;
  int dollars = 0;
  unsigned long start = millis();
  
  while (millis() - start < 3000) {
    while (Serial1.available()) {
      char c = Serial1.read();
      bytes++;
      if (c == '$') dollars++;
      Serial.write(c);
    }
  }
  
  Serial.print("\n>>> Bytes=");
  Serial.print(bytes);
  Serial.print(" NMEA=$ x");
  Serial.println(dollars);
  
  if (dollars > 0) {
    Serial.println(">>> SUCCESS: GPS working at this baud!");
  }
}

void loop() {
  tryBaud(9600);
  tryBaud(19200);
  tryBaud(38400);
  tryBaud(57600);
  tryBaud(115200);
  Serial.println("\n=== SCAN COMPLETE — repeat in 10s ===");
  delay(10000);
}
