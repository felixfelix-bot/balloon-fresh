#!/usr/bin/env python3
"""Solve OPEN-25 / OPEN-17: which free ADC-capable, non-strap S3 pin can take
the supercap / rail-monitor divider?

Rebuilds the assigned-pin set from ADR-108's pin table and answers:
  - what is genuinely free
  - of those, which are ADC1-capable (the only usable ADC on the S3 with WiFi/BT)
  - and therefore whether OPEN-25 needs the mux/ladder shape ADR-108 predicted
"""
# From ADR-108 "Pin assignment" table + its R1 revisions
assigned = {
    1, 2,            # I2C SDA/SCL (MS5607)
    4, 5, 6, 7, 8, 9, 10,   # F33 SPI2 bus + control
    11,              # U3_IRQ (R1.4)
    12,              # U3_CS_N (R1.4)
    13,              # F33_VSENSE rail-monitor divider tap (ADR-047 s6)
    14, 15, 16, 17, 18,     # SX1280 SPI3 bus + DIO2
    19, 20,          # USB-Serial-JTAG console
    21,              # GNSS_PPS
    38,              # SX1280_BUSY
    39, 40, 41, 42,  # SX1280 control (native JTAG spent)
    43, 44,          # GPS UART
    47, 48,          # U3_BUSY / U3_RESET_N (R1.4)
}
straps = {0, 3, 45, 46}          # must stay unloaded (ADR-108 audit)
psram  = {35, 36, 37}            # octal-PSRAM, not GPIO on -N8R8
usb    = {19, 20}                # already in assigned, listed for clarity
adc1   = set(range(1, 11))       # ESP32-S3 ADC1 = GPIO1..GPIO10

reserved = assigned | straps | psram | usb
free = sorted(set(range(0, 49)) - reserved)

print("assigned          :", sorted(assigned))
print("straps (excluded) :", sorted(straps))
print("PSRAM  (excluded) :", sorted(psram))
print()
print("FREE pins         :", free)
print()
free_adc = sorted(set(free) & adc1)
print("free AND ADC1-capable:", free_adc)
print()
if free_adc:
    print("=> OPEN-25 could use a dedicated ADC pin:", free_adc)
else:
    print("=> NO free ADC1-capable pin remains.")
    print("   => OPEN-25 MUST take the one-GPIO + mux / resistor-ladder shape")
    print("      that ADR-051 s2.6 and ADR-108 OPEN-25 both explicitly allow,")
    print("      and the sense burden-share must be solved ANALOGICALLY")
    print("      (different divider ratios per wing) on the ONE ADC input that")
    print("      is already spent: IO13 (F33_VSENSE), or by freeing a pin.")
