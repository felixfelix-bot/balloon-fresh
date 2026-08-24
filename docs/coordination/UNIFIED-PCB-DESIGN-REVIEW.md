# Unified PCB Design Review: Single-MCU + Dual-MCU on One Board

**Reviewer:** Senior Hardware Architect (AI-assisted)
**Date:** 2026-08-05
**Subject:** Felix's proposal for a unified PCB supporting both single-MCU (C3 direct SPI) and dual-MCU (RP2040 SPI bridge) modes via 0Ω resistors / solder jumpers
**Context:** V1 PCB (50×40mm, 2-layer) has fatal DRC shorts; firmware-hardware architecture mismatch identified; DUAL-BOARD-STRATEGY.md proposes two separate boards

---

## Executive Summary

**Verdict: DO NOT pursue the unified PCB. Make two separate boards.**

The unified PCB concept is technically possible but practically inadvisable for this project. The C3's 11-GPIO limit creates an unsolvable pin constraint in single-MCU mode, the dual SPI routing doubles the complexity that already produced 527 DRC violations on the V1 board, and the cost savings of a unified board vs two separate boards is ~$0.01 in resistors — not worth the engineering risk. The existing firmware Kconfig already handles architecture selection cleanly; there is no firmware benefit from forcing both architectures onto one PCB.

If Felix insists on a unified board despite this recommendation, the detailed schematic changes are provided in Section 6 below, with a 4-layer board as the minimum viable approach.

---

## 1. Feasibility: 2-Layer 50×40mm or 4-Layer?

### Verdict: 2-layer is not feasible for clean routing. 4-layer is minimum viable.

**Current V1 layout (dual-MCU only, 2-layer):**

| Component | Position | Key Nets |
|-----------|----------|----------|
| ESP32-C3 header | (12, 12) — left side | UART, GPS, I2C, LED, VDIV |
| RP2040-Zero header | (38, 12) — right side | SPI0 (SCK/MOSI/MISO/NSS), BUSY, DIO9, RST |
| LR2021 module | (25, 25) — center | SPI pins on LEFT side (x=15.095), DIO9/RST on RIGHT side (x=34.905) |

The V1 board routes ONE SPI bus: RP2040 (right) → LR2021 (center). The SPI traces run right-to-left (x=38 → x=15.095), crossing ~23mm. The control lines DIO9 and RST run right-to-right (x=38 → x=34.905), short and easy.

A unified board must route TWO complete SPI buses to the same LR2021 pads:

| Bus | Source → Destination | Path |
|-----|---------------------|------|
| RP2040 SPI (4 lines) | (38, y) → LR2021 left pins (15.095, y) | Right→Left, ~23mm, crosses entire board |
| C3 SPI (4 lines) | (12, y) → LR2021 left pins (15.095, y) | Left→Left, ~3mm, short and easy |
| RP2040 DIO9/RST (2 lines) | (38, y) → LR2021 right pins (34.905, y) | Right→Right, ~3mm, short |
| C3 DIO9/Rst (2 lines) | (12, y) → LR2021 right pins (34.905, y) | Left→Right, ~23mm, crosses entire board |
| C3 BUSY (1 line) | (12, y) → LR2021 left pin (15.095, 22.42) | Left→Left, ~3mm |
| RP2040 BUSY (1 line) | (38, y) → LR2021 left pin (15.095, 22.42) | Right→Left, ~23mm |

**Problem:** The C3's DIO9 and RST traces must cross from left (x=12) to right (x=34.905), traversing the full board width. Simultaneously, the RP2040's SPI traces cross from right (x=38) to left (x=15.095). These two trace groups cross each other in the center of the board, directly over/under the LR2021 module.

On 2 layers, you have only F.Cu and B.Cu. With 14 signal traces (7 per MCU) converging on 7 LR2021 pads, plus 14 0Ω resistor pad pairs (28 extra pads), the routing congestion in the center of the board becomes severe. The V1 auto-router already produced 527 DRC violations routing just one SPI bus — doubling the SPI routing will make this dramatically worse.

**4-layer assessment:** With 4 layers (F.Cu, GND, PWR, B.Cu), you get two dedicated signal routing layers plus clean power/ground planes. The C3 SPI traces can route on F.Cu (left→center), the RP2040 SPI traces on B.Cu (right→center), and they don't cross. 4-layer at JLCPCB costs ~$8 vs ~$2 for 2-layer — a $6 premium per board, but the routing becomes feasible.

**However:** 4-layer doesn't solve the GPIO pin count problem (see Section 2 below). Even with perfect routing, the C3 doesn't have enough pins for single-MCU mode with all peripherals.

---

## 2. The GPIO Pin Count Problem (Deal-Breaker)

### The ESP32-C3 has only 11 GPIOs (GPIO0–GPIO10). GPIO18/19 do not exist — they are USB D-/D+.

**Single-MCU mode pin budget (C3 controls everything):**

| Function | GPIO | Status |
|----------|------|--------|
| GPS UART TX | GPIO0 | Required |
| GPS UART RX | GPIO1 | Required |
| SPI MISO | GPIO2 | Required |
| LR2021 RST | GPIO3 | Required |
| LR2021 BUSY | GPIO4 | Required |
| LR2021 DIO9/IRQ | GPIO5 | Required |
| SPI SCK | GPIO6 | Required |
| SPI MOSI | GPIO7 | Required |
| ADC (voltage divider) | GPIO8 | Required |
| I2C SDA / LED | GPIO9 | **CONFLICT** — can only be one |
| SPI NSS | GPIO10 | Required |

**Total: 11 GPIOs needed, 11 available — but GPIO9 must serve double duty (I2C SDA AND LED), and I2C SCL has NO pin available.**

This means in single-MCU mode, you CANNOT have:
- I2C (BMP280/MS5611 sensor) — no pin for SCL
- LED on a dedicated pin — must share with I2C SDA or be dropped

**In dual-MCU mode, the pin budget is comfortable:**

| C3 Function | GPIO | RP2040 Function | Pin |
|-------------|------|------------------|-----|
| GPS TX | GPIO0 | SPI0 SCK | Pad 3 |
| GPS RX | GPIO1 | SPI0 MOSI | Pad 4 |
| UART TX→RP2040 | GPIO2* | SPI0 MISO | Pad 5 |
| UART RX←RP2040 | GPIO3* | SPI0 NSS | Pad 6 |
| I2C SDA | GPIO8 | BUSY | Pad 7 |
| I2C SCL | GPIO9 | DIO9 | Pad 8 |
| LED | GPIO10 | RST | Pad 9 |
| ADC | GPIO4* | — | — |

(*Actual C3 GPIO-to-header-pad mapping may vary; the point is that dual-MCU offloads 7 pins to the RP2040, leaving the C3 with plenty for GPS+I2C+LED+ADC+UART.)

**Impact on unified PCB:** The unified board must accommodate both pin assignments. In single-MCU mode, the C3 header pins that carry UART-to-RP2040 (pads 3, 4) would instead carry SPI MISO and LR2021 RST. The 0Ω resistors select which net each C3 pad connects to. But this means the C3 header pad → GPIO mapping must be different for each mode, which is a schematic-level netlist change, not just a jumper selection.

This is the fundamental problem: **the C3 header doesn't have enough pins to support both modes simultaneously.** The same physical pad must carry different nets depending on mode. You'd need 0Ω resistors on the C3 side too, not just on the LR2021 side, to switch pad assignments. This doubles the jumper count and complexity.

---

## 3. SPI Bus Contention Prevention

### Risk: If both MCUs are populated with their 0Ω resistors installed, both drive SCK/MOSI simultaneously → output fighting → potential pin damage, guaranteed communication failure.

**Approach A: 0Ω Resistors as Selectors (Recommended if unified board is built)**

- Group resistors by MCU: `R_C3_SCK`, `R_C3_MOSI`, `R_C3_MISO`, `R_C3_NSS`, `R_C3_BUSY`, `R_C3_DIO9`, `R_C3_RST` and `R_RP_SCK`, `R_RP_MOSI`, `R_RP_MISO`, `R_RP_NSS`, `R_RP_BUSY`, `R_RP_DIO9`, `R_RP_RST`
- Silkscreen warning: **"POPULATE EITHER R_C3_* OR R_RP_* — NEVER BOTH"**
- Risk: Human error during assembly. If Felix accidentally installs both sets, the board can be damaged on power-up.
- Mitigation: Use 100Ω resistors instead of 0Ω. If both sets are populated, the 100Ω resistors limit contention current to 16.5mA per pin (3.3V / 200Ω), which is within ESP32-C3's 28mA drive strength. SPI signal integrity at 100Ω + ~10pF trace capacitance gives a 1ns time constant — fine for SPI up to ~10MHz. **This is the safest approach.**

| Resistor Value | Contention Current (if both populated) | SPI Speed Limit | Safety |
|----------------|---------------------------------------|-----------------|--------|
| 0Ω | Unlimited (short circuit) | No limit | **DANGEROUS** |
| 33Ω | 50mA per pin | ~30MHz | Marginal — exceeds C3 drive strength |
| 100Ω | 16.5mA per pin | ~10MHz | **Safe** — within drive strength |
| 1kΩ | 1.65mA per pin | ~1MHz | Very safe, but limits SPI speed |

**Recommendation: 100Ω series resistors instead of 0Ω.** This provides contention protection while supporting SPI speeds up to 10MHz (LR2021 typically runs at 1-8MHz). The RP2040 achieved 1377kbps data rate, which at SPI level translates to ~2-4MHz SPI clock — well within 100Ω tolerance.

**Approach B: Analog Mux (Overkill for this project)**

A chip like TS3A5018 (2:1 mux, 4 channels) could automatically select which MCU drives the SPI bus. Cost: ~$0.50, adds a component and control logic. Too complex for a prototype.

**Approach C: Pin Header Jumpers (Too large)**

7 signal lines × 3-pin header (2-jumper) = 21 pins = ~53mm of board edge. On a 50mm-wide board, this consumes an entire edge. Not feasible.

---

## 4. Solder Bridges vs 0Ω Resistors vs Pin Headers

| Option | Footprint per jumper | BOM cost | Change mode | Error risk | Assembly |
|--------|---------------------|----------|-------------|------------|----------|
| Solder bridge (pad gap) | ~0.5 × 0.3mm | $0.00 | Desolder + resolder | **HIGH** — accidental bridge | Hand only |
| 0Ω resistor (0402) | ~1.0 × 0.5mm | $0.001 | Desolder + resolder | Low | SMD or hand |
| 100Ω resistor (0402) | ~1.0 × 0.5mm | $0.001 | Desolder + resolder | Very low (contention-safe) | SMD or hand |
| Pin header + shunt (1×3) | ~5mm per signal | $0.05 | Move shunt | Very low | Through-hole |

**Recommendation: 100Ω 0402 resistors.** Smallest footprint, contention-safe, standard SMD process, negligible cost. Felix solders SMD — 0402 is challenging but doable with practice. If Felix prefers easier hand-soldering, 0603 (1.6 × 0.8mm) is a fallback with the same electrical characteristics.

---

## 5. Control Lines (BUSY / DIO9 / RST)

### Same 100Ω resistor approach, but with different contention profiles.

| Line | Direction | Contention Risk if Both Populated | Issue |
|------|-----------|----------------------------------|-------|
| BUSY | LR2021 → MCU (input) | **None** — two high-Z inputs on one output. Safe but wastes C3 GPIOs in dual-MCU mode. | In dual-MCU mode, C3 GPIO4 is wasted reading BUSY when it could be used for ADC or other functions. |
| DIO9 | LR2021 → MCU (input/IRQ) | **None** — same as BUSY. Safe but wastes C3 GPIO. | Same as above. |
| RST | MCU → LR2021 (output) | **HIGH** — two outputs driving same line. If both MCUs drive RST differently, contention. | 100Ω resistor limits current to safe levels. |

**Recommendation:** All three control lines use 100Ω selector resistors, same as SPI. Even though BUSY and DIO9 are electrically safe with both connected, the C3 GPIO budget is too tight to waste pins in dual-MCU mode. The resistors ensure only one MCU is connected.

**Critical RST note:** RST is active-low. If the unpopulated MCU's RST line has a floating pad, the LR2021 could see noise on RST and randomly reset. Add a 10kΩ pull-up resistor on the LR2021 RST pad (always populated, not selected). This ensures RST is held high (inactive) regardless of which MCU is driving it.

---

## 6. UART Floating Input Issue

### When RP2040 is unpopulated (single-MCU mode), C3 UART RX is floating.

**The problem:** C3 pad 4 (RP2040_TX_ESP_RX) connects to an unpopulated RP2040 pad. The trace is unterminated. The C3's UART RX pin is floating.

**ESP32-C3 UART RX floating behavior:**
- Without a pull-up, floating RX picks up EMI and can trigger spurious UART start-bit detection, causing garbage RX interrupts.
- ESP-IDF's UART driver does NOT automatically enable the internal pull-up on RX.
- In single-MCU mode, the UART driver for the C3↔RP2040 link should not be initialized at all (via `#ifdef CONFIG_DUAL_MCU`). If it's not initialized, the pin stays in default state (floating input) and won't generate interrupts.

**Hardware fix (recommended):** Add a 10kΩ pull-up resistor on the C3 UART RX net (RP2040_TX_ESP_RX). This is always populated. Cost: $0.001. Ensures RX sits at idle (high) when RP2040 is absent. Takes minimal board space.

**Firmware fix (also needed):** In single-MCU mode (`#ifndef CONFIG_DUAL_MCU`), do not initialize UART1 for the RP2040 link. Configure that GPIO as input with internal pull-up enabled. This is a one-line Kconfig guard.

**C3 UART TX (ESP_TX_RP2040_RX, pad 3):** This is an output driving an open trace. No issue — the C3 just drives a signal that goes nowhere. No pull-up needed.

---

## 7. Power: RP2040 Unpopulated

### If RP2040 is unpopulated, its 3V3 and GND pads are unused. Any issue?

**No issue.** The 3V3 rail is shared — the RP2040's 3V3 pad connects to the same 3V3 net as the C3 and LR2021. With the RP2040 unpopulated, the 3V3 pad is just an unused copper pad. No current flows, no short risk (assuming the V1's 3V3↔GND short is fixed in the new design).

The RP2040-Zero module has its own 3V3 LDO on-board. If the RP2040 is populated, its LDO draws from the 3V3 input. If unpopulated, no LDO, no draw. The shared 3V3 rail is powered by the board's main LDO (TPS7A02) regardless.

**One consideration:** If the unified board routes 3V3 to the RP2040 footprint through the 0Ω selector resistors, don't. The 3V3 and GND connections to the RP2040 should be direct (no selectors) — they're always connected whether or not the RP2040 is populated. Only the signal lines need selectors.

---

## 8. BOM Cost Impact

### Unified PCB vs two separate boards

**Unified PCB additional BOM:**

| Item | Qty | Unit cost | Total |
|------|-----|-----------|-------|
| 100Ω 0402 resistors (SPI+control selectors) | 14 | $0.001 | $0.014 |
| 10kΩ 0402 pull-up (UART RX) | 1 | $0.001 | $0.001 |
| 10kΩ 0402 pull-up (LR2021 RST) | 1 | $0.001 | $0.001 |
| **Total additional** | | | **$0.016** |

**PCB cost:**

| Option | 2-layer | 4-layer |
|--------|---------|---------|
| JLCPCB (5 boards) | ~$2/each = $10 | ~$8/each = $40 |
| Premium for 4-layer | — | +$30 total |

**Two separate boards:**

| Board | Design | Cost |
|-------|--------|------|
| Board A (single-MCU, 2-layer) | Simple, no RP2040, no UART, no selectors | $2/each |
| Board B (dual-MCU, 2-layer) | V1 fixed, no selectors needed | $2/each |
| **Total for 5 of each** | | $20 |

**Unified board (4-layer required):**

| Board | Cost |
|-------|------|
| 5× unified 4-layer | $40 |

**Conclusion:** Two separate 2-layer boards ($20 for 10 boards) are cheaper than one unified 4-layer board ($40 for 5 boards), and each is simpler to route and assemble.

---

## 9. Firmware Impact

### Does the unified PCB simplify or complicate firmware?

**Current firmware state:**
- Kconfig already has `CONFIG_ENABLE_RELAY_MODE`
- Can add `CONFIG_DUAL_MCU` to select SPI-direct vs UART-relay
- Single-MCU: C3 drives SPI directly (SCK=GPIO6, MOSI=GPIO7, MISO=GPIO2, NSS=GPIO10)
- Dual-MCU: C3 sends radio commands via UART to RP2040, which relays over SPI

**Unified PCB firmware impact:**

| Aspect | Unified PCB | Two Separate Boards |
|--------|-------------|---------------------|
| Firmware code | Same binary, two Kconfig configs | Same binary, two Kconfig configs |
| Mode detection | None — relies on assembler to match Kconfig to populated resistors | None — board identity is physical |
| Risk of mismatch | **HIGH** — firmware says dual-MCU but resistors populated for single-MCU (or vice versa) = non-functional | **LOW** — wrong firmware on wrong board is obvious |
| GPIO init | Must guard every GPIO init with `#ifdef` | Same |
| UART init | Conditional on `CONFIG_DUAL_MCU` | Same |
| Testing | Can test both modes on one board | Need both boards |

**Verdict: The unified PCB does NOT simplify firmware.** The Kconfig-based architecture selection already works identically for both approaches. The unified PCB adds the risk of firmware-hardware configuration mismatch with no detection mechanism.

**A GPIO strap could detect mode:** Use a spare GPIO (if one existed — but C3 has none to spare) pulled high/low by a selector resistor. Firmware reads the strap at boot and auto-selects mode. But the C3 has no spare GPIOs, so this isn't possible without dropping another function.

---

## 10. The Real Question: Unified Board vs Two Separate Boards

### Recommendation: TWO SEPARATE BOARDS

**Why two boards is better:**

1. **Routing simplicity:** Each board has one SPI bus to route, not two. The V1 auto-router failed with one bus — don't double the challenge.
2. **C3 GPIO constraint:** Single-MCU mode needs 11 GPIOs for 13 functions (impossible). Dual-MCU mode is comfortable. Separate boards let each design optimize pin usage without compromise.
3. **Cost:** Two 2-layer boards ($20 for 10) < one 4-layer board ($40 for 5).
4. **No contention risk:** No possibility of accidentally populating both MCU's SPI resistors.
5. **No firmware-hardware mismatch risk:** Wrong firmware on wrong board is visually obvious. Wrong Kconfig on a unified board is invisible.
6. **DUAL-BOARD-STRATEGY.md already recommends this:** Board A (single-MCU V2) first, Board B (dual-MCU V1-fixed) later.
7. **Time to flying:** Board A (single-MCU) is simpler, can be designed and ordered faster. The firmware already supports single-MCU.

**Why the unified board is appealing but wrong:**

1. "One board to rule them all" sounds elegant but adds complexity where simplicity is needed.
2. The V1 PCB's 527 DRC violations demonstrate that this team's auto-router cannot handle even a single-SPI-bus 2-layer design. Adding a second SPI bus is irresponsible.
3. The $0.016 BOM savings is irrelevant compared to the $30 4-layer premium and the engineering risk.
4. The C3 doesn't have enough GPIOs to support all peripherals in single-MCU mode — the unified board would force dropping I2C or LED in single-MCU mode, making the "unified" board not actually unified.

---

## 11. Concrete Schematic-Level Recommendation (If Unified Board Is Built Anyway)

### For the V1 PCB net list, these changes are needed:

#### 11.1 New Nets Required

The V1 has 22 nets. The unified board adds:

| New Net Name | Purpose |
|--------------|---------|
| C3_SPI_SCK | C3 GPIO6 → 100Ω → LR2021 SCK pad |
| C3_SPI_MOSI | C3 GPIO7 → 100Ω → LR2021 MOSI pad |
| C3_SPI_MISO | LR2021 MISO pad → 100Ω → C3 GPIO2 |
| C3_SPI_NSS | C3 GPIO10 → 100Ω → LR2021 NSS pad |
| C3_LR2021_BUSY | LR2021 BUSY pad → 100Ω → C3 GPIO4 |
| C3_LR2021_DIO9 | LR2021 DIO9 pad → 100Ω → C3 GPIO5 |
| C3_LR2021_RST | C3 GPIO3 → 100Ω → LR2021 RST pad |
| RP_SPI_SCK | RP2040 SCK → 100Ω → LR2021 SCK pad |
| RP_SPI_MOSI | RP2040 MOSI → 100Ω → LR2021 MOSI pad |
| RP_SPI_MISO | LR2021 MISO → 100Ω → RP2040 MISO |
| RP_SPI_NSS | RP2040 NSS → 100Ω → LR2021 NSS pad |
| RP_LR2021_BUSY | LR2021 BUSY → 100Ω → RP2040 BUSY |
| RP_LR2021_DIO9 | LR2021 DIO9 → 100Ω → RP2040 DIO9 |
| RP_LR2021_RST | RP2040 RST → 100Ω → LR2021 RST pad |
| LR2021_SCK | Common node at LR2021 SCK pad (merge point) |
| LR2021_MOSI | Common node at LR2021 MOSI pad |
| LR2021_MISO | Common node at LR2021 MISO pad |
| LR2021_NSS | Common node at LR2021 NSS pad |
| LR2021_BUSY_NET | Common node at LR2021 BUSY pad |
| LR2021_DIO9_NET | Common node at LR2021 DIO9 pad |
| LR2021_RST_NET | Common node at LR2021 RST pad (with 10kΩ pull-up) |

**Total nets: 22 (V1) - 7 (old SPI/control nets replaced) + 21 (new nets) = 36 nets**

#### 11.2 C3 Header Pin Reassignment

The C3 header pads must be remapped. Currently the V1 C3 header carries: 3V3, GND, UART-TX, UART-RX, GPS-RX, VDIV, I2C-SDA, I2C-SCL, LED, (unused).

For the unified board, the C3 header needs dual-function pads:

| C3 Pad | Single-MCU Mode Net | Dual-MCU Mode Net | Selector |
|--------|--------------------|--------------------|----------|
| 1 | 3V3 | 3V3 | Direct (no selector) |
| 2 | GND | GND | Direct |
| 3 | C3_SPI_MISO (GPIO2) | ESP_TX_RP2040_RX | **Two 100Ω resistors** — one to SPI MISO merge point, one to RP2040 UART RX |
| 4 | C3_LR2021_RST (GPIO3) | RP2040_TX_ESP_RX | **Two 100Ω resistors** — one to RST merge point, one to RP2040 UART TX |
| 5 | C3_LR2021_BUSY (GPIO4) | GPS_TX_ESP_RX | **Two 100Ω resistors** — one to BUSY merge point, one to GPS |
| 6 | C3_LR2021_DIO9 (GPIO5) | VDIV_MID | **Two 100Ω resistors** — one to DIO9 merge point, one to VDIV |
| 7 | C3_SPI_SCK (GPIO6) | I2C_SDA | **Two 100Ω resistors** — one to SCK merge point, one to I2C SDA |
| 8 | C3_SPI_MOSI (GPIO7) | I2C_SCL | **Two 100Ω resistors** — one to MOSI merge point, one to I2C SCL |
| 9 | C3_SPI_NSS (GPIO10) | STATUS_LED | **Two 100Ω resistors** — one to NSS merge point, one to LED |
| 10 | (unused) | (unused) | — |

Wait — this means EVERY C3 signal pad (3-9) needs TWO 100Ω resistors to select between single-MCU and dual-MCU net assignments. That's 7×2 = 14 additional resistors on the C3 side, plus 7×2 = 14 on the LR2021/RP2040 side. Total: 28 selector resistors + 2 pull-ups = 30 new components.

This is getting absurd for a 50×40mm board.

**Revised pad assignment to minimize dual-function pads:**

Actually, looking at this more carefully, the C3 header pads don't directly map to GPIOs — the ESP32-C3 Mini dev board has its own pinout. The C3 GPIOs available are 0-10, but the header pad numbering doesn't directly correspond. The actual mapping depends on the specific C3 Mini board used.

Let me reconsider: if we assume the C3 header can be wired to any GPIO, then we need pads for:
- GPIO0 (GPS TX) — always needed
- GPIO1 (GPS RX) — always needed
- GPIO2 (SPI MISO in single, UART in dual) — dual function
- GPIO3 (RST in single, UART in dual) — dual function
- GPIO4 (BUSY in single, ADC in dual) — dual function
- GPIO5 (DIO9 in single, free in dual) — dual function
- GPIO6 (SCK in single, I2C SDA in dual) — dual function
- GPIO7 (MOSI in single, I2C SCL in dual) — dual function
- GPIO8 (ADC in single, I2C SDA in dual) — dual function
- GPIO9 (free/LED in single, LED in dual) — dual function
- GPIO10 (NSS in single, free in dual) — dual function

**Every single C3 GPIO has a dual function.** This means every signal line from the C3 needs a selector resistor. This is 11 selector pairs = 22 resistors just on the C3 side.

This is the nail in the coffin for the unified PCB idea. **The C3's limited GPIO count means every pin must be remapped between modes, requiring selector resistors on every signal line.** This is not a "simple 0Ω resistor on the SPI bus" — it's a full pin-mux matrix.

---

## 12. Final Recommendation

### Make two separate boards. Do not pursue the unified PCB.

| Criterion | Unified PCB | Two Separate Boards |
|-----------|-------------|---------------------|
| 2-layer feasibility | No (need 4-layer) | Yes |
| Routing complexity | 36 nets, 30 extra components | 22 nets each, no extra components |
| SPI contention risk | Medium (mitigated by 100Ω) | None |
| C3 GPIO constraint | Every pin dual-function, 22 selector resistors | Each board optimized independently |
| BOM cost (5 boards) | $40 (4-layer) + $0.50 (resistors) | $20 (2× 2-layer, 5 each) |
| Firmware complexity | Same Kconfig, but mismatch risk | Same Kconfig, no mismatch risk |
| Time to design | 5-7 days (complex routing) | 2-3 days (simple routing) |
| Time to flying | Day 12+ | Day 10 |

### Board A: Single-MCU V2 (BUILD FIRST)

- 50×40mm, 2-layer
- ESP32-C3 only (no RP2040 footprint)
- C3 direct SPI to LR2021: SCK=GPIO6, MOSI=GPIO7, MISO=GPIO2, NSS=GPIO10
- Control: RST=GPIO3, BUSY=GPIO4, DIO9=GPIO5
- GPS: GPIO0 (TX), GPIO1 (RX)
- ADC: GPIO8
- LED: GPIO9
- I2C: **Drop SCL, keep SDA only, or drop I2C entirely** (not enough pins for both SDA+SCL)
- No UART-to-RP2040 traces
- No selector resistors
- Firmware: current single-MCU Kconfig (already exists)

### Board B: Dual-MCU V1-Fixed (BUILD SECOND)

- 50×40mm, 2-layer
- ESP32-C3 + RP2040-Zero
- RP2040: SPI to LR2021 (SCK, MOSI, MISO, NSS, BUSY, DIO9, RST)
- C3: UART to RP2040, GPS, I2C, LED, ADC
- Fix V1's 527 DRC violations (3V3↔GND shorts, SPI shorts, etc.)
- No selector resistors
- Firmware: dual-MCU Kconfig with `CONFIG_DUAL_MCU=y`

### Antenna Routing

No difference between modes. The LR2021 antenna traces (RF_SUB_868, RF_2G4_2400) are identical regardless of which MCU drives SPI. The antenna connects directly to the LR2021 RF pins. This is the same for both boards.

---

## Appendix A: V1 PCB Net List (Current, Dual-MCU)

```
Net ID  Name                    Connected To
1       3V3                    C3:1, RP2040:1, LR2021:1, GPS:1, MS5611:1, LDO:5
2       GND                    C3:2, RP2040:2/13, LR2021:2/8/10/11/16/18, GPS:2, MS5611:2, LED:1, ...
3       SPI0_SCK               RP2040:3, LR2021:5
4       SPI0_MOSI              RP2040:4, LR2021:4
5       SPI0_MISO              RP2040:5, LR2021:3
6       SPI0_NSS               RP2040:6, LR2021:6
7       LR2021_BUSY            RP2040:7, LR2021:7
8       LR2021_RST             RP2040:9, LR2021:14
9       LR2021_DIO9            RP2040:8, LR2021:13
10      I2C_SDA                C3:7, MS5611:3
11      I2C_SCL                C3:8, MS5611:4
12      RF_SUB_868             LR2021:9, antenna pad
13      RF_2G4_2400            LR2021:18, antenna pad
14      ESP_TX_RP2040_RX       C3:3, RP2040:12
15      RP2040_TX_ESP_RX       C3:4, RP2040:11
16      GPS_TX_ESP_RX          C3:5, GPS:3
17      VDIV_MID               C3:6, voltage divider
18      STATUS_LED             C3:9, R5:1
19      LED_ANODE              R5:2, LED:2
20      VCAP                   LDO:1/3, BAT54:2, supercap:1
21      SOLAR_IN               BAT54:1, solar connector:1
```

## Appendix B: LR2021 Pin Assignment (NiceRF LR2021 castellated module)

```
Pin  Side  Function
1    Left  3V3 (VDD)
2    Left  GND
3    Left  SPI MISO
4    Left  SPI MOSI
5    Left  SPI SCK
6    Left  SPI NSS (CS)
7    Left  BUSY
8    Left  GND
9    Left  RF_SUB_868 (sub-GHz antenna)
10   Right GND
11   Right GND
12   Right (NC)
13   Right DIO9 (IRQ)
14   Right RST (Reset)
15   Right (NC)
16   Right GND
17   Right GND
18   Right RF_2G4_2400 (2.4GHz antenna)
```

## Appendix C: Component Placement (V1 PCB, mm)

```
ESP32-C3 header: (12, 12) — 10 pads, 2.54mm pitch, ~18×22mm footprint
RP2040-Zero:     (38, 12) — 13 pads, 1.5mm pitch, ~2×33mm footprint
LR2021:          (25, 25) — 18 SMD pads, 19.81×14.98mm module
GPS (MAX-M10S): (6, 33)  — 4 pads
MS5611:         (44, 33) — 4 pads
TPS7A02 LDO:    (5, 22)  — SOT-23-5
BAT54 diode:    (4, 18)  — SOD-123
Supercap:       (8, 37)  — radial THT
Solar input:    (3, 37)  — 2-pin THT
LED + R:        (16-18.5, 4) — 0603 LED + 0402 resistor
```

---

## Summary

| Question | Answer |
|----------|--------|
| 1. Feasible on 2-layer 50×40mm? | **No.** Need 4-layer for clean dual-SPI routing. 2-layer would repeat V1's routing failures. |
| 2. SPI bus contention? | **100Ω series resistors** instead of 0Ω. Limits contention current to 16.5mA if both MCUs populated. |
| 3. Solder bridges vs 0Ω vs headers? | **100Ω 0402 resistors.** Smallest, safest, cheapest. Solder bridges too error-prone, headers too large. |
| 4. Control lines same approach? | **Yes**, 100Ω selectors for all 7 lines. Add 10kΩ pull-up on RST. |
| 5. UART floating input? | **10kΩ pull-up on C3 UART RX** + firmware guard (`#ifndef CONFIG_DUAL_MCU`). |
| 6. BOM cost impact? | **+$0.016** in resistors. But 4-layer PCB adds **+$6/board** vs 2-layer. Two separate 2-layer boards ($20) < one 4-layer unified ($40). |
| 7. Firmware simpler or more complex? | **Neither.** Kconfig already handles mode selection. Unified board adds mismatch risk with no detection mechanism. |
| 8. Unified or separate boards? | **SEPARATE BOARDS.** C3 GPIO limit forces every pin to be dual-function (22 selector resistors). Routing complexity doubles. Cost is higher. Time is longer. No firmware benefit. |