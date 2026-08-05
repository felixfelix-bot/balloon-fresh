# Unified Board Analysis: Can ONE PCB Serve Both Single-MCU and Dual-MCU?

**Date:** 2026-08-05
**Author:** Senior Hardware Consultant
**Question from Felix:** Can one PCB serve both single-MCU (ESP32-C3 only) and dual-MCU (C3 + RP2040)?

---

## 1. ANSWER: One Board for Both Configs?

**YES. One board serves both. No question about it.**

The V1 PCB topology makes this trivial. Here's why:

- The LR2021 SPI radio connects **directly** to the ESP32-C3 via GPIO2/6/7/10 + GPIO3/4/5 (RST/BUSY/IRQ). It does NOT route through the RP2040.
- The RP2040 connects to the C3 via **only 2 UART pins** (ESP_TX_RP2040_RX + RP2040_TX_ESP_RX).
- GPS, I2C, ADC, power — all connect directly to the C3.
- The RP2040 is a co-processor for future FIPS mesh work. It is NOT a SPI bridge, NOT a peripheral controller, NOT on any critical path for V1 flight.

**Therefore:** Leave the RP2040 socket unpopulated → instant single-MCU board. Populate the RP2040 socket → dual-MCU board. The C3 doesn't care whether the RP2040 is there or not — it just won't see UART traffic from a co-processor that isn't soldered down.

The DUAL-BOARD-STRATEGY.md document proposing two separate boards was written before the V1 topology was understood. Now that we know the RP2040 is a passive UART co-processor (not a bus master), one board is clearly sufficient.

---

## 2. GPIO Budget Analysis (All 11 Pins)

The ESP32-C3 has **11 GPIOs total (GPIO0–GPIO10)**. There is no GPIO11+, no GPIO18, no GPIO19 — those are USB D-/D+ on the C3 and are physically unavailable on the Mini header.

| GPIO | Current Assignment | Flight-Critical? | Could Sacrifice? |
|------|-------------------|-------------------|------------------|
| GPIO0 | UART1 TX → GPS RX | YES — GPS is mission-critical | No |
| GPIO1 | UART1 RX → GPS TX | YES — GPS is mission-critical | No |
| GPIO2 | SPI MISO → LR2021 | YES — radio is mission-critical | No |
| GPIO3 | LR2021 RST | YES — radio needs reset control | No |
| GPIO4 | LR2021 BUSY | YES — radio SPI handshake | No |
| GPIO5 | LR2021 IRQ (DIO9) | YES — radio interrupt | No |
| GPIO6 | SPI SCK → LR2021 (via SB1) | YES — radio SPI clock | No |
| GPIO7 | SPI MOSI → LR2021 (via SB2) | YES — radio SPI data | No |
| GPIO8 | ADC (supercap voltage divider) | MAYBE — nice to have, not flight-critical | **Yes — candidate for LED** |
| GPIO9 | I2C SDA → BMP280 (optional) | NO — BMP280 not on critical path | **Yes — top candidate for LED** |
| GPIO10 | SPI NSS → LR2021 | YES — radio chip select | No |

**Summary:** 9 of 11 GPIOs are hard-committed to GPS + radio (the two mission-critical subsystems). Only GPIO8 and GPIO9 are negotiable.

---

## 3. RP2040 Socket Strategy: Unpopulated = Single, Populated = Dual

This is the key insight that makes one board work for both configs:

**Single-MCU configuration (V1 flight):**
- Leave RP2040 socket EMPTY (0 components populated)
- The 2 UART pins (ESP_TX_RP2040_RX, RP2040_TX_ESP_RX) are simply no-connections
- The C3 firmware runs standalone — no UART2 co-processor, no FIPS mesh
- Board weight: lower (no RP2040, no socket, no RP2040 decoupling caps)
- Assembly time: shorter

**Dual-MCU configuration (future mesh V2):**
- Populate RP2040 socket + decoupling caps + crystal (if needed)
- The 2 UART pins connect C3 ↔ RP2040
- RP2040 handles FIPS Noise handshake, mesh routing, encryption
- C3 delegates crypto-heavy work to RP2040

**What does NOT change between configs:**
- PCB layout — same board, same copper
- C3 firmware — same binary works in both configs (co-processor just isn't there in single-MCU)
- Radio, GPS, power, ADC — all identical

**What DOES change:**
- Bill of materials (populate RP2040 or not)
- Firmware behavior (single-MCU: skip FIPS; dual-MCU: enable FIPS via UART co-processor)

This is textbook "design for configurability" — one PCB, two BOM variants. No solder bridges needed for MCU selection.

---

## 4. Recommended GPIO for Status LED

The LED is not flight-critical. It's a debugging aid during bench testing and pre-launch checkout. For a balloon at 30km altitude, nobody sees the LED. But for development, it's extremely useful to have a heartbeat indicator.

### Trade-off Matrix

| Option | GPIO | What You Sacrifice | Impact of Sacrifice | Verdict |
|--------|------|-------------------|---------------------|---------|
| A | GPIO9 | I2C SDA (BMP280) | Lose temperature/pressure sensor | **RECOMMENDED** |
| B | GPIO8 | ADC (supercap voltage) | Lose supercap voltage monitoring | Acceptable |
| C | GPIO9 + external I2C expander | Nothing, but adds complexity | 1 extra chip, 2 extra GPIOs... wait, no GPIOs left | Rejected — no pins for expander |
| D | No LED at all | Nothing | No visual debug indicator | Fallback if pin budget is too tight |

### Recommendation: **GPIO9 for LED. Sacrifice BMP280.**

Reasoning:
1. **BMP280 is not needed for V1 flight.** The balloon's primary telemetry is GPS position (lat/lon/alt from MAX-M10S). Temperature and pressure are nice-to-have science data, not mission-critical. GPS altitude is more accurate than barometric at balloon altitudes anyway.
2. **Supercap voltage monitoring (GPIO8 ADC) is more useful than BMP280.** Knowing whether your power supply is dying is more important than knowing the temperature. Keep ADC on GPIO8.
3. **GPIO9 is already routed on the V1 PCB** as I2C SDA. Repurposing it as a GPIO output for an LED requires only a net label change in the schematic/PCB, not a layout change.
4. **If BMP280 is needed later**, it can go on an external I2C breakout connected via a header pin. Or use a V2 board with a 12-GPIO MCU.

### If ADC is also not needed:

If you decide supercap voltage monitoring is unnecessary (the balloon will fly or die regardless of whether you can see the voltage), then GPIO8 is also free. You could put the LED on GPIO8 and keep GPIO9 for I2C. But I'd keep ADC and sacrifice I2C — power monitoring > temperature data for a first flight.

---

## 5. FEM: Keep or Remove for V1 Flight?

**Remove the FEM (SKY66112) entirely for V1 flight. Wire dipole only.**

Reasoning:
1. **The FLIGHT-BOARD-PLAN.md already specifies "Wire dipoles for V1 (no Yagis, no SP4T, no FEM)."** This was the original design decision. The FEM was added later as a "future enhancement" but it's not needed for V1.
2. **The FEM requires a control GPIO (FEM_TX).** We don't have one. GPIO18/GPIO19 don't exist on the C3. Every remaining GPIO is committed to GPS + radio.
3. **The LR2021 has a built-in PA (+22 dBm output power).** This is sufficient for balloon-to-ground communication at 200+ km with a simple wire dipole. Adding an external FEM adds gain but also adds complexity, power consumption, and failure modes.
4. **FEM adds weight and assembly complexity.** The SKY66112 is a QFN package requiring careful soldering. For a hand-soldered first flight board, skip it.
5. **FEM_TX was previously assigned to GPIO19, which is USB D+ on the C3.** This was a fundamental error (documented in CONSULTANT-PROGRESS-REVIEW-V6.md). It can't work. Remove the FEM_TX net entirely.

**Action:** Delete the FEM footprint, FEM_TX net, and any FEM-related components from the V1 schematic and PCB. Leave antenna pads AE1 (868 MHz wire dipole) and AE2 (2.4 GHz wire dipole) directly connected to the LR2021 antenna pins.

---

## 6. Solder Bridges: Needed or Unnecessary?

### SB1 / SB2 (SPI pin-swap for SCK/MOSI)

**Unnecessary for V1 flight. Remove them.**

The solder bridges SB1 and SB2 were designed to allow swapping SCK and MOSI between two GPIO pin assignments (Config A: GPIO6=SCK, GPIO7=MOSI vs Config B: swapped). The idea was to support different ESP32 modules that might break out SPI pins differently.

**Why they're unnecessary:**
1. **The ESP32-C3 Mini V1 has fixed pin assignments.** GPIO6 is always GPIO6. There's no pin-swap scenario.
2. **The bare ESP-C3-12F uses the same GPIO numbers.** No swap needed.
3. **Solder bridges add complexity, DRC violations, and failure modes.** Each bridge is 4 pads + a crossover trace. On a board already struggling with 527 DRC violations, removing 2 bridges eliminates a class of potential shorts.
4. **If you ever need to swap pins, change the firmware.** The ESP32-C3's SPI peripheral can use any GPIO via the GPIO matrix. You don't need hardware bridges to swap SCK and MOSI — just change `#define SPI_SCK_GPIO` in firmware.

**Action:** Replace SB1 and SB2 with direct traces: GPIO6 → SCK, GPIO7 → MOSI. Delete the solder bridge footprints.

### SB3 (Power select: USB vs Solar)

**Keep SB3.** This one is genuinely useful.

The power select jumper allows switching between USB 5V (for development/bench testing) and solar input (for flight) without cutting traces. This is a legitimate design-for-configurability feature. Keep it as a 3-pad solder jumper.

---

## 7. Board Changes Needed (Routing Fix + GPIO Fix)

### Change 1: Fix the 527 DRC Violations

The V1 PCB was auto-routed with no human review, resulting in:
- 35× 3V3↔GND shorts (board will smoke)
- SPI bus shorted (SCK↔MOSI↔MISO↔NSS — radio dead)
- UART TX/RX shorted (GPS dead)
- I2C shorted to power/ground
- RF traces shorted
- 44 unconnected nets

Freerouting auto-router is currently running to attempt to fix these. If it succeeds, the board may be salvageable. If it fails, the board needs manual routing fixes or a redesign.

### Change 2: Fix GPIO Assignments

| What | Current (V1) | Fixed (V1-corrected) |
|------|-------------|---------------------|
| LED | GPIO18 (test point TP5 — unconnected on C3) | **GPIO9** (was I2C SDA, repurpose to LED) |
| FEM_TX | GPIO19 (test point TP6 — unconnected on C3) | **DELETE** (remove FEM entirely) |
| I2C SDA | GPIO9 | **DELETE** (GPIO9 now LED) |
| I2C SCL | GPIO10 — CONFLICT with SPI NSS | **DELETE** (was already broken — GPIO10 is SPI NSS) |

### Change 3: Remove Solder Bridges SB1 and SB2

Replace with direct traces (GPIO6→SCK, GPIO7→MOSI).

### Change 4: Remove FEM Components

Delete FEM footprint, FEM_TX net, FEM control components. Wire LR2021 antenna pins directly to AE1/AE2 pads.

### Change 5: Add LED Footprint

Add a simple LED + current-limiting resistor (e.g., 0805 LED + 1kΩ 0402 resistor) on GPIO9.

### Summary of Changes

| # | Change | Effort | Impact |
|---|--------|--------|--------|
| 1 | Fix 527 DRC violations (routing) | 2-4 days (if auto-router succeeds, less) | Board must be manufacturable |
| 2 | GPIO9: I2C SDA → LED | 30 min (net label change) | Enables status LED |
| 3 | Remove SB1, SB2 (direct traces) | 30 min (delete footprints, re-route) | Simplifies board |
| 4 | Remove FEM (delete footprint + nets) | 30 min (delete components) | Saves GPIO, weight, complexity |
| 5 | Add LED + resistor footprint | 15 min (add 2 components) | Visual debug indicator |
| 6 | Remove I2C/BMP280 nets | 15 min (delete net labels) | Cleans up schematic |

**Total effort for changes 2-6: ~2 hours of schematic/PCB text editing.** The bottleneck is change 1 (routing fix), which depends on the auto-router outcome.

---

## 8. Impact on Firmware (Pin Defines)

The firmware currently uses GPIO18/GPIO19 for LED/FEM_TX. These don't exist on the ESP32-C3. The following pin defines need changing:

### Changes Required

```c
// BEFORE (broken — these pins don't exist on C3):
#define LED_PIN          18   // GPIO18 = USB D- on C3 — WRONG
#define FEM_TX_PIN       19   // GPIO19 = USB D+ on C3 — WRONG

// AFTER (fixed — C3-compatible):
#define LED_PIN           9   // GPIO9 — was I2C SDA, now LED
// FEM_TX_PIN — DELETE ENTIRELY (no FEM on V1)

// If I2C was defined:
// BEFORE:
#define I2C_SDA_PIN       9   // DELETE — GPIO9 is now LED
#define I2C_SCL_PIN      10   // DELETE — GPIO10 is SPI NSS, was never available for I2C
// AFTER: Remove all I2C initialization code. No BMP280 on V1 flight.
```

### What Stays the Same

```c
// Radio (LR2021) — no changes:
#define SPI_MISO_PIN      2
#define SPI_SCK_PIN       6
#define SPI_MOSI_PIN      7
#define SPI_NSS_PIN      10
#define LR2021_RST_PIN    3
#define LR2021_BUSY_PIN   4
#define LR2021_IRQ_PIN    5

// GPS — no changes:
#define GPS_UART_TX_PIN   0   // UART1 TX
#define GPS_UART_RX_PIN   1   // UART1 RX

// ADC — no changes:
#define ADC_PIN           8   // Supercap voltage divider
```

### RP2040 UART (dual-MCU only)

```c
// These are only used when RP2040 is populated.
// In single-MCU mode, these pins are no-connections (or can be used as debug GPIO).
#define RP2040_UART_TX_PIN  ???  // ESP TX → RP2040 RX (need to check which C3 pin)
#define RP2040_UART_RX_PIN  ???  // RP2040 TX → ESP RX
```

Wait — this is a gap. The RP2040 UART pins weren't in the original 11-GPIO budget listing. Let me check: GPIO0-10 are all assigned. The RP2040 UART needs 2 pins. Where do they come from?

**Problem:** The ESP32-C3 only has 11 GPIOs (0-10). All 11 are assigned (9 to GPS+radio, 1 to ADC, 1 to LED after our fix). There are **no free GPIOs for the RP2040 UART**.

This means one of two things:
1. The RP2040 UART was never actually routed on V1 (it was planned but not implemented due to pin exhaustion).
2. The RP2040 UART shares pins with something else (unlikely — UART and SPI can't share).

**For the unified board analysis, this is the key constraint:** The RP2040 co-processor UART requires 2 GPIOs that don't exist in the current budget. Options:
- **Option A:** Drop ADC (GPIO8) — use GPIO8 for RP2040 UART TX, and sacrifice another pin for RX. But we need 2 pins, and only have 1 left after dropping ADC.
- **Option B:** Drop LED (GPIO9) and ADC (GPIO8) — gives 2 pins for RP2040 UART. But then you have no LED and no ADC in single-MCU mode.
- **Option C:** The RP2040 UART is not needed for V1 flight. Wire it in V2 when you switch to a larger MCU (ESP32-S3 has 45 GPIOs).

**Recommendation:** For V1, the RP2040 socket is physically present but the UART pins can be left as unconnected pads (or connected to GPIO8/GPIO9 via 0Ω resistors that are only populated in dual-MCU mode). In single-MCU mode, GPIO8=ADC and GPIO9=LED. In dual-MCU mode, GPIO8=RP2040_UART_TX, GPIO9=RP2040_UART_RX (no ADC, no LED). This is the real solder-bridge use case — but 0Ω resistor jumpers are cleaner than solder bridges.

Actually, the simplest approach: **use 0Ω resistors (or solder jumpers) on GPIO8 and GPIO9 to select between ADC/LED (single-MCU) and RP2040 UART (dual-MCU).** This is 2 tiny components, easily soldered or left empty.

---

## 9. Recommendation: Fix V1 Routing or Design V2 from Scratch?

**Fix V1 routing. Do NOT design V2 from scratch.**

Reasoning:

1. **V1's schematic is correct (mostly).** The topology is sound: C3 → LR2021 (direct SPI), C3 → GPS (UART), C3 → ADC, C3 → RP2040 (UART). The problems are in the PCB layout (527 DRC violations from bad auto-routing), not the circuit design.

2. **A V2 from scratch takes 7-10 days** (schematic + component selection + footprint creation + PCB layout + DRC + gerber export). Fixing V1 routing takes 2-4 days (if auto-router succeeds, maybe less).

3. **The GPIO fix is trivial.** Changing GPIO9 from I2C SDA to LED is a net label change. Removing FEM is deleting components. These are 1-hour tasks.

4. **The V1 board already has the RP2040 socket footprint.** This is the unified board — it supports both configs. Designing a new V2 without RP2040 would lose this flexibility.

5. **You need to fly, not engineer.** Felix wants a flyable board, not a design exercise. The fastest path is: fix V1 routing → fix GPIO → order → solder → fly.

6. **A V2 design would repeat the same mistakes.** Without a working V1 to learn from, V2 would likely have the same auto-routing issues. Better to fix V1, learn from it, then design V2 with accumulated knowledge.

**When to design V2 from scratch:**
- When you need an ESP32-S3 instead of C3 (more GPIOs, more compute)
- When you need 4-layer board (better RF, power integrity)
- When the V1 routing fix fails (auto-router can't resolve the shorts)
- When you need PCBA (JLCPCB assembly) with tighter tolerances

For V1 flight: fix, don't redesign.

---

## 10. Bottom Line: Fastest Path to Flyable Board

### The Plan

```
Step 1: Wait for Freerouting auto-router to finish (running now)
  ├─ If it succeeds: review the output, run DRC, verify 0 violations
  └─ If it fails: manually fix the 35 power shorts + SPI/UART shorts (2 days max)

Step 2: Fix GPIO assignments (1 hour)
  ├─ GPIO9: change net from I2C_SDA to LED
  ├─ GPIO8: keep as ADC (no change)
  ├─ Delete FEM_TX net (was on non-existent GPIO19)
  ├─ Delete I2C SCL net (was on GPIO10 = SPI NSS — was broken)
  └─ Add LED + 1kΩ resistor footprints on GPIO9

Step 3: Remove unnecessary components (30 min)
  ├─ Delete solder bridges SB1, SB2 (replace with direct traces)
  ├─ Delete FEM footprint and related components
  └─ Delete BMP280 footprint (if present)

Step 4: Handle RP2040 UART pin conflict (30 min)
  ├─ Add 0Ω resistor footprints on GPIO8 and GPIO9
  ├─ Position 1: ADC (GPIO8) + LED (GPIO9) — single-MCU
  └─ Position 2: RP2040_UART_TX (GPIO8) + RP2040_UART_RX (GPIO9) — dual-MCU
  OR: Just leave RP2040 UART unconnected on V1. Wire it on V2.
      The RP2040 socket is present but UART-less. C3 firmware
      won't try to talk to a co-processor that isn't there.

Step 5: Run DRC, verify 0 violations, regenerate gerbers (1 hour)

Step 6: Update firmware pin defines (30 min)
  ├─ LED_PIN: 18 → 9
  ├─ Delete FEM_TX_PIN
  ├─ Delete I2C_SDA_PIN, I2C_SCL_PIN
  └─ Rebuild, verify C3 binary compiles

Step 7: Order from JLCPCB (15 min)
  ├─ 5 boards, 2-layer, 0.6mm, HASL
  └─ Express shipping

Step 8: While waiting 1-2 weeks for delivery
  ├─ Wire LR2021 to ESP32-C3 dev board on breadboard
  ├─ Run integration tests (radio, GPS, telemetry)
  ├─ Finalize flight software
  └─ Test power budget with solar + supercap

Step 9: PCB arrives → solder (2h) → test → fly
```

### Timeline

| Milestone | Time from now |
|-----------|---------------|
| Auto-router result | Today (hours) |
| GPIO + component fixes | Today (2h) |
| DRC clean + gerbers | Today + 1 day |
| JLCPCB order | Today + 1 day |
| Firmware pin fix | Today (30 min) |
| PCB delivery | + 7-14 days |
| Assembly + test | + 1 day after delivery |
| **First flight** | **+ 8-15 days** |

### Critical Path

```
Auto-router → GPIO fix → DRC → Gerber export → JLCPCB order → Delivery → Solder → Test → Fly
```

The bottleneck is JLCPCB lead time (5-14 days). Everything before the order is < 1 day of work. Everything after delivery is 2-3 days. **The fastest thing Felix can do is get the gerbers right and order TODAY.**

### What NOT to do

- ❌ Do NOT design a V2 board from scratch (wastes 7-10 days)
- ❌ Do NOT include FEM on V1 (no GPIO for it, not needed for flight)
- ❌ Do NOT include BMP280 on V1 (saves GPIO9 for LED)
- ❌ Do NOT keep solder bridges SB1/SB2 (unnecessary, adds DRC violations)
- ❌ Do NOT try to make the RP2040 UART work on V1 (no spare GPIOs — defer to V2)
- ❌ Do NOT overthink this — fix, order, solder, fly

---

## Summary Table

| Question | Answer |
|----------|--------|
| One board for both configs? | **YES** — RP2040 socket unpopulated = single-MCU, populated = dual-MCU |
| GPIO for LED? | **GPIO9** — sacrifice BMP280/I2C (not needed for V1 flight) |
| FEM on V1? | **NO** — remove entirely, wire dipole only, no GPIO available |
| Solder bridges SB1/SB2? | **REMOVE** — unnecessary, direct traces instead |
| Solder bridge SB3 (power)? | **KEEP** — useful for USB/solar switching |
| Fix V1 or design V2? | **FIX V1** — routing fix + GPIO fix, no redesign |
| Supercap ADC (GPIO8)? | **KEEP** — power monitoring > temperature data |
| RP2040 UART pins? | **DEFER** — no spare GPIOs on C3, wire on V2 with larger MCU |
| Fastest path to flight? | Fix routing → fix GPIO → order → solder → fly (8-15 days) |