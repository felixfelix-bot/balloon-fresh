# Powerbank Auto-Shutoff Fix (R6)

## Problem

Standard USB power banks auto-shutoff when current draw drops below ~50mA.
The LR2021 TX board draws only ~30mA during TX (peak), with ~15mA idle
between bursts. This triggers the power bank's "device disconnected"
detection → shutoff after ~30-60 seconds.

## Solution: Dummy Load Circuit

Add a parallel resistive load that keeps total draw above 50mA continuously.

### Circuit

```
Power Bank USB Output (5V)
    │
    ├─── RP2040 + LR2021 board (~30mA peak, ~15mA idle)
    │
    └─── 100Ω resistor (1/4W)  ← draws 50mA @ 5V continuously
              │
              └── GND
```

**Resistor calculation:**
- Need: ≥20mA continuous to stay above 50mA total during idle
- R = V/I = 5.0V / 0.020A = 250Ω minimum
- Use **100Ω** for margin: draws 50mA, total = ~65mA idle, ~80mA TX peak
- Power dissipation: P = V²/R = 25/100 = 0.25W → use **1/4W or 1/2W resistor**
- If only 1/8W resistors available: use **220Ω** (draws 23mA, P=0.11W)

### Parts Needed

| Part | Value | Qty | Notes |
|------|-------|-----|-------|
| Resistor | 100Ω 1/4W | 1 | Through-hole, axial |
| | OR 220Ω 1/8W | 1 | If 1/4W not available |

### Assembly (Operator Task — 2 minutes)

1. Strip both ends of resistor leads (~5mm)
2. Solder one lead to the **5V pad** on the RP2040 board (VBUS pin, or the USB 5V input before the regulator)
3. Solder other lead to any **GND pad**
4. Wrap exposed leads with tape/heat-shrink (prevent shorts)
5. Verify: connect power bank, confirm board boots AND stays on >2 min

### Alternative: LED Dummy Load

If no resistor available:
- Any LED + 220Ω resistor in series across 5V/GND
- Draws ~15mA, might not be enough alone
- Use 2-3 LEDs in parallel for more draw

### Testing (After Assembly)

```bash
# 1. Flash TX firmware (dual-tx or dual-tx-pa-off)
# 2. Connect power bank
# 3. Monitor serial for >5 minutes
# 4. Board should not reboot/shutoff during this period
# 5. Check: "AUTO SWEEP TX STARTING" appears only once at boot
```

### Power Bank Runtime Estimate

- Typical 10000mAh power bank: ~150 hours at 65mA average
- Typical 5000mAh power bank: ~75 hours
- Plenty for multi-hour outdoor testing
