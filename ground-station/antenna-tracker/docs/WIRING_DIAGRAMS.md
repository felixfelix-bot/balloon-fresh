# ESP32 ↔ SBT0811 ↔ 28BYJ-48 Wiring Diagrams

This document shows how to connect:

- 2× 28BYJ-48 (5‑wire, 5V) stepper motors
- 2× SBT0811 driver boards (Darlington array)
- 1× ESP32

Firmware pin assignments (from `antenna-firmware/src/main.rs`):

## Azimuth Motor GPIOs

```
GPIO14
GPIO27
GPIO26
GPIO25
```

## Elevation Motor GPIOs

```
GPIO33
GPIO32
GPIO18
GPIO19
```

---

# 1️⃣ Power Wiring (CRITICAL)

All grounds MUST be connected together.

```
External 5V  +  ───────────────┐
                               ├── SBT0811 #1 VCC
                               ├── SBT0811 #2 VCC
                               └── Motor RED wire (both motors)

External 5V  GND ──────────────┐
                                ├── SBT0811 #1 GND
                                ├── SBT0811 #2 GND
                                └── ESP32 GND
```

⚠️ Do NOT power motors from ESP32 3.3V.

---

# 2️⃣ Azimuth Motor Wiring

### ESP32 → SBT0811 #1

```
ESP32 GPIO14  ───────────> IN1
ESP32 GPIO27  ───────────> IN2
ESP32 GPIO26  ───────────> IN3
ESP32 GPIO25  ───────────> IN4
```

### SBT0811 #1 → Motor

Typical 28BYJ‑48 wire colors:

```
OUT1 ───────────> Blue
OUT2 ───────────> Pink
OUT3 ───────────> Yellow
OUT4 ───────────> Orange

Motor Red ──────> +5V
```

---

# 3️⃣ Elevation Motor Wiring

### ESP32 → SBT0811 #2

```
ESP32 GPIO33  ───────────> IN1
ESP32 GPIO32  ───────────> IN2
ESP32 GPIO18  ───────────> IN3
ESP32 GPIO19  ───────────> IN4
```

### SBT0811 #2 → Motor

```
OUT1 ───────────> Blue
OUT2 ───────────> Pink
OUT3 ───────────> Yellow
OUT4 ───────────> Orange

Motor Red ──────> +5V
```

---

# 4️⃣ Full System Overview

```
                +5V SUPPLY
                   │
                   │
         ┌─────────┴─────────┐
         │                   │
     SBT0811 #1         SBT0811 #2
         │                   │
     28BYJ-48            28BYJ-48
         │                   │
         └────── GND ────────┘
                 │
              ESP32 GND
```

---

# 5️⃣ Testing After Wiring

After flashing firmware:

```
echo "AZ 20" > /dev/ttyUSB1
echo "EL 20" > /dev/ttyUSB1
```

If motor vibrates but does not rotate:

- Swap coil order (OUT1–OUT4)

Correct sequence for most 28BYJ‑48 motors:

```
Blue → Pink → Yellow → Orange
```

---

# 6️⃣ Common Mistakes

- ❌ Forgetting shared ground
- ❌ Powering motor from ESP32 3.3V
- ❌ Mixing coil order
- ❌ Using only one driver board for two motors

---

✅ With the above wiring, the firmware and MCP server will control both motors correctly.
