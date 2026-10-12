# Consultant PCB Review — Balloon Tracker Project

**Reviewer:** Independent Consultant (AI-assisted)
**Date:** 2026-08-05
**Scope:** V1 PCB (50×40mm, 2-layer, C3+RP2040+LR2021) and F33 PCB (75×55mm, 2-layer, C3+RP2040+LR2021F33)
**Data sources:** KiCad DRC output (fresh kicad-cli run Aug 5 2026), gen_pcb.py net assignments, firmware Kconfig, V1-PCB-GPIO-FIX.md, Integration Plan V2

---

## Executive Summary

Neither PCB is order-ready. The V1 board has ~24 unique net-pair shorts including a fatal 3V3↔GND short (18 instances) and all four SPI lines shorted together, plus 43 unconnected nets. The F33 board has ~10 unique net-pair shorts including GND↔RF traces and UART TX lines shorted, plus 32 unconnected nets. Both boards lack BOM files. The GPIO10 collision fix document describes a single-MCU firmware architecture that does not match the V1 PCB's dual-MCU hardware design. The integration plan's claim that gerbers are ready is incorrect and the "fix GPIO10" instruction is inapplicable to the V1 board.

---

## Claim-by-Claim Review

### CLAIM 1: "V1-PCB-GPIO-FIX.md GPIO10 collision doesn't apply to V1 PCB (dual-MCU architecture, RP2040 controls SPI not C3)"

**Verdict: CONFIRM**

**Reasoning:**

The V1 PCB's ESP32-C3 header carries these nets only:

| Pad | Net |
|-----|-----|
| 1 | 3V3 |
| 2 | GND |
| 3 | ESP_TX_RP2040_RX |
| 4 | RP2040_TX_ESP_RX |
| 5 | GPS_TX_ESP_RX |
| 6 | VDIV_MID |
| 7 | I2C_SDA |
| 8 | I2C_SCL |
| 9 | STATUS_LED |
| 10 | (unconnected) |

The ESP32-C3 on the V1 PCB has **no connection to any SPI signal**. All SPI signals route to the RP2040-Zero:

| RP2040 Pad | Net |
|------------|-----|
| 3 | SPI0_SCK |
| 4 | SPI0_MOSI |
| 5 | SPI0_MISO |
| 6 | SPI0_NSS |
| 7 | LR2021_BUSY |
| 8 | LR2021_DIO9 |
| 9 | LR2021_RST |

Therefore:

- **GPIO10/NSS collision is irrelevant to V1 PCB.** The firmware Kconfig assigns `LR2021_NSS=GPIO10` on the C3, but on the V1 PCB the C3 never touches NSS. The RP2040 controls SPI0_NSS on its own pad 6. A collision between LED and NSS on C3 GPIO10 can only exist in a single-MCU design where the C3 directly drives the LR2021's SPI bus — which the V1 PCB is not.

- **GPIO1/GPS_RX+FEM_TX collision is irrelevant to V1 PCB.** The firmware Kconfig assigns `GPS_RX=GPIO1` and `FEM_TX_PIN=GPIO19`, both on the C3. On the V1 PCB, GPS connects via C3 pad 5 (GPS_TX_ESP_RX) — note this is the GPS *TX* line going to the C3's RX, which is a UART connection, not GPIO1 in the Kconfig sense. Furthermore, FEM_TX does not appear as a net on the V1 PCB at all — there is no FEM (front-end module) on the V1 board. This collision is for a different hardware design.

- **STATUS_LED on V1 PCB maps to C3 pad 9**, which per footprint analysis corresponds to approximately GPIO6 (or possibly GPIO20/RX depending on exact pin mapping), not GPIO10 or GPIO18. The firmware Kconfig's `LED_GPIO=18` does not match the V1 PCB either. This confirms the firmware and V1 PCB were designed for different architectures.

**Key finding:** The firmware Kconfig (LED=GPIO18, NSS=GPIO10, SCK=GPIO6, MOSI=GPIO7, MISO=GPIO2, etc.) describes a **single-MCU architecture** where the ESP32-C3 directly controls all peripherals including the LR2021 via SPI. The V1 PCB implements a **dual-MCU architecture** where the RP2040 handles SPI/LR2021 and the C3 handles UART, GPS, I2C, and LED. These are fundamentally different designs. V1-PCB-GPIO-FIX.md addresses the single-MCU firmware design, not the V1 PCB hardware.

---

### CLAIM 2: "V1 PCB has 31 electrical shorts including 3V3↔GND, 43 unconnected — NOT order-ready"

**Verdict: PARTIALLY CONFIRM**

**Confirmed aspects:**
- The V1 PCB has serious DRC shorts including 3V3↔GND — **CONFIRMED**
- 43 unconnected items — **CONFIRMED** (8 track-dangling + 31 via-dangling + 4 other)
- NOT order-ready — **CONFIRMED**

**Inaccuracies:**
- "31 electrical shorts" is inaccurate. The DRC reports **59 shorting_items** entries comprising approximately **22–28 unique net pairs**. The sub-manager conflated individual DRC violations with unique shorted pairs, or used an incorrect number. Neither 59 nor 22-28 equals 31.

**Short classification:**

KiCad DRC "shorting_items" indicate copper from two different nets that overlap or touch — these are **real electrical shorts**, not mere clearance warnings (which would appear as "unconnected" or separate clearance violations). Each entry means current can flow between two nets that should be isolated.

| Short | Severity | Count | Impact |
|-------|----------|-------|--------|
| GND↔3V3 | **FATAL** | ~18 instances | Instant power rail short. Board draws excessive current on power-up. Will trip current limiting or destroy components. Board is a paperweight. |
| SPI0_SCK↔SPI0_MOSI | **FATAL** | 1 | SPI bus shorted — LR2021 radio non-functional |
| SPI0_SCK↔SPI0_MISO | **FATAL** | 1 | Same as above |
| SPI0_MOSI↔SPI0_MISO | **FATAL** | 1 | Same as above |
| SPI0_MISO↔SPI0_NSS | **FATAL** | 1 | Same as above |
| SPI0_SCK↔3V3 | **FATAL** | 1 | SPI clock shorted to power |
| SPI0_SCK↔GND | **FATAL** | 1 | SPI clock shorted to ground |
| SPI0_NSS↔GND | **FATAL** | 1 | Chip select stuck low |
| SPI0_NSS↔LR2021_BUSY | **SEVERE** | 1 | NSS and BUSY conflated — LR2021 control broken |
| LR2021_RST↔LR2021_DIO9 | **SEVERE** | 1 | Reset and DIO9 shorted — radio control corrupted |
| LR2021_BUSY↔LR2021_DIO9 | **SEVERE** | 1 | Two control lines shorted |
| RP2040_TX_ESP_RX↔ESP_TX_RP2040_RX | **SEVERE** | 1 | Both UART TX lines shorted — inter-MCU communication dead |
| STATUS_LED↔GND | **MODERATE** | 1 | LED circuit shorted — LED non-functional, possible overcurrent |
| STATUS_LED↔RF_SUB_868 | **MODERATE** | 1 | LED net bleeding into RF trace |
| GND↔I2C_SCL | **SEVERE** | 1 | I2C clock stuck low — I2C bus dead |
| 3V3↔I2C_SDA | **SEVERE** | 1 | I2C data line shorted to power — I2C bus dead |
| I2C_SDA↔GPS_TX_ESP_RX | **SEVERE** | 1 | I2C and GPS UART cross-shorted |
| VDIV_MID↔GND | **MODERATE** | 1 | Voltage divider output shorted — ADC reading always 0 |
| VCAP↔VDIV_MID | **MODERATE** | 1 | Capacitor net and voltage divider cross-connected |
| RP2040_TX_ESP_RX↔RF_2G4_2400 | **SEVERE** | 1 | UART TX shorted to 2.4GHz RF trace |
| RF_2G4_2400↔RF_SUB_868 | **SEVERE** | 1 | Two RF traces shorted — both radios compromised |
| 3V3↔VCAP | **MODERATE** | 1 | VCAP rail shorted to 3V3 |
| ESP_TX_RP2040_RX↔GND | **SEVERE** | 1 | UART TX shorted to ground — inter-MCU link dead |
| LED_ANODE↔STATUS_LED | **LOW** | 1 | Likely intentional or harmless — LED anode and STATUS_LED may be same net |

**3V3↔GND analysis:** The 18 instances of GND↔3V3 shorting suggest a **systematic routing error**, most likely a ground copper pour or polygon that overlaps with 3V3 traces or pads throughout the board. This is not a localized mistake — it's a fundamental routing flaw that must be fixed in the PCB design tool, not post-manufacture.

---

### CLAIM 3: "F33 PCB has 13 shorts including CE↔NSS, GND↔RF, 32 unconnected — NOT order-ready"

**Verdict: PARTIALLY CONFIRM**

**Confirmed aspects:**
- F33 PCB has serious shorts including CE↔NSS and GND↔RF — **CONFIRMED**
- 32 unconnected items — **CONFIRMED**
- NOT order-ready — **CONFIRMED**

**Inaccuracies:**
- "13 shorts" is slightly off. The DRC reports **15 shorting_items** entries comprising approximately **10 unique net pairs**. The number 13 does not match either the total violations (15) or unique pairs (10).

**Notable F33 shorts:**

| Short | Severity | Count | Impact |
|-------|----------|-------|--------|
| LR2021_CE↔SPI0_NSS | **POSSIBLY INTENTIONAL** | 2 | On many SPI devices, CE and NSS are the same signal. If the LR2021F33 module ties CE to NSS internally, this may not be a real error. However, if they are separate nets that should be independently controllable, this is a routing bug. Needs design intent verification. |
| GND↔RF_SUB_868 | **FATAL** | 1 | RF trace shorted to ground — sub-GHz radio dead |
| GND↔RF_2G4_2400 | **FATAL** | 2 | RF trace shorted to ground — 2.4GHz radio dead |
| VCAP↔3V3 | **SEVERE** | 2 | Power rail short |
| VCAP↔STATUS_LED | **MODERATE** | 1 | Capacitor net and LED cross-connected |
| VCAP↔GND | **FATAL** | 2 | VCAP shorted to ground |
| SPI0_SCK↔ESP_TX_RP2040_RX | **SEVERE** | 1 | SPI clock and UART TX cross-shorted — both buses compromised |
| I2C_SCL↔GND | **SEVERE** | 1 | I2C clock stuck low — I2C dead |
| SOLAR_IN↔GPS_TX_ESP_RX | **SEVERE** | 1 | Solar input and GPS UART cross-shorted |
| ESP_TX_RP2040_RX↔RP2040_TX_ESP_RX | **SEVERE** | 2 | Both UART TX lines shorted — inter-MCU link dead |

**CE↔NSS note:** The LR2021F33 module may tie CE (chip enable) to NSS (SPI chip select) by design, since SPI devices typically use NSS as the chip-enable signal. If the schematic has CE and NSS as separate nets but the module only has one CS pin, this DRC error would be expected and is not a real short. The designer should verify whether this is intentional.

---

### CLAIM 4: "Both boards missing BOM files"

**Verdict: CONFIRM**

No `bom*.csv` files exist in either `gerbers_v1/` or `gerbers_f33/` directories. Without a BOM, a PCB manufacturer cannot assemble the boards (though they can fabricate bare PCBs from gerbers alone). For prototype ordering, bare PCB fabrication is possible without a BOM, but if assembly service is needed, a BOM is mandatory.

---

### CLAIM 5: "Integration plan V2 incorrectly states gerbers ready"

**Verdict: CONFIRM**

The Integration Plan V2 states: *"Order V1 PCB — Felix action. Gerbers ready, fix GPIO10 in schematic first. 2-week lead time = hardware critical path."*

This statement is incorrect on two counts:

1. **Gerbers are not "ready" in any meaningful sense.** While gerber files may physically exist on disk, the underlying PCB design has ~24 unique net-pair shorts (including 18 instances of fatal 3V3↔GND), all SPI lines shorted together, and 43 unconnected nets. Ordering this board would produce a non-functional PCB. "Gerbers ready" implies DRC-clean output ready for fabrication — this is not the case.

2. **"Fix GPIO10 in schematic" is inapplicable to the V1 PCB.** As established in Claim 1, the V1 PCB uses a dual-MCU architecture where the C3 does not connect to GPIO10/NSS. The GPIO10 collision is a firmware-level issue for a single-MCU design, not a V1 PCB schematic issue. Applying this fix to the V1 schematic would be modifying a net that doesn't exist on the board.

---

## Additional Analysis

### A) Can V1 be ordered as-is for prototyping?

**No.** The V1 PCB cannot be ordered as-is for any functional purpose. The fatal shorts are:

**Fatal (board will not power on or core functions will not work):**
- 3V3↔GND (18 instances) — power supply shorted, board draws unlimited current on power-up
- All four SPI lines shorted together + SPI0_SCK↔3V3 + SPI0_SCK↔GND + SPI0_NSS↔GND — SPI bus completely non-functional, LR2021 radio unreachable
- RP2040_TX_ESP_RX↔ESP_TX_RP2040_RX — inter-MCU UART link dead
- ESP_TX_RP2040_RX↔GND — second UART direction dead
- GND↔I2C_SCL + 3V3↔I2C_SDA — I2C bus dead

**Post-manufacture fixability:**
- The 3V3↔GND short (18 instances) is **not fixable post-manufacture**. With 18 separate short locations between power and ground, cutting traces would be impractical and would likely destroy the board's integrity. A copper pour issue affecting 18 locations cannot be knife-fixed.
- SPI line shorts (4+ locations) are **theoretically fixable** with a precision knife if they are trace-to-trace overlaps, but given the 2-layer board and the density of shorts, this is impractical.
- Signal shorts (I2C, UART, STATUS_LED) are **theoretically fixable** but add more knife work.
- 43 unconnected nets **cannot be fixed post-manufacture** — missing traces require re-routing in the PCB tool.

**Conclusion:** Ordering the V1 as-is would waste 2 weeks of lead time and produce unusable boards. Post-manufacture repair is not feasible given the scale (18 power-shorts, all SPI lines dead, 43 unconnected nets).

### B) What minimum work makes V1 order-ready?

1. **Fix the 3V3↔GND short (critical path).** The 18 instances suggest a ground copper pour overlapping with 3V3 traces/pads. Likely fix: adjust the ground pour keepout or re-route 3V3 traces away from the pour boundary. This is the single highest-impact fix.

2. **Fix SPI bus shorts.** SPI0_SCK↔SPI0_MOSI↔SPI0_MISO↔SPI0_NSS are all shorted together, plus SCK↔3V3, SCK↔GND, NSS↔GND, NSS↔LR2021_BUSY. This suggests the SPI traces are overlapping or the router is placing them on top of each other. Likely fix: re-run the router with proper clearance for SPI signals, or manually route SPI traces.

3. **Fix UART shorts.** RP2040_TX_ESP_RX↔ESP_TX_RP2040_RX (both TX lines shorted) and ESP_TX_RP2040_RX↔GND. The router appears to be crossing TX lines.

4. **Fix I2C shorts.** GND↔I2C_SCL, 3V3↔I2C_SDA, I2C_SDA↔GPS_TX_ESP_RX.

5. **Fix remaining signal shorts.** STATUS_LED↔GND, VDIV_MID↔GND, RF trace shorts, LR2021 control line shorts.

6. **Route all 43 unconnected nets.** 8 dangling tracks + 31 dangling vias + 4 other. These are nets that have partial routing but don't reach their endpoints.

7. **Re-run DRC until 0 shorts, 0 unconnected.**

8. **Generate BOM file** (required for assembly, not for bare PCB fabrication).

9. **Regenerate gerbers** from the DRC-clean board.

**Estimated effort:** Given these are auto-generated from `gen_pcb.py` using a custom Router class, the most efficient path is to fix the routing algorithm rather than manually patching individual shorts. The systematic nature of the shorts (all SPI lines together, 18× GND↔3V3) suggests the router has fundamental bugs in net clearance and pour handling.

### C) Is dual-MCU (C3+RP2040) still the right architecture?

**Current assessment: Dual-MCU is a reasonable hedge for V1, but V2 should aim for single-MCU if C3 SPI timing is validated.**

**Arguments for keeping dual-MCU (V1):**
- The V1 PCB is already designed (albeit with DRC errors) for dual-MCU
- The RP2040 has well-characterized SPI timing and can reliably drive the LR2021
- C3 SPI timing data is still pending — without it, single-MCU is a risk
- The dual-MCU approach decouples radio timing from C3 application overhead

**Arguments for single-MCU (V2):**
- **Cost:** Eliminating the RP2040-Zero module saves ~$4-6 per board and reduces BOM line items
- **Board area:** The RP2040-Zero module takes significant footprint on a 50×40mm board; removing it enables smaller form factor
- **Complexity:** Dual-MCU adds inter-MCU UART protocol overhead, synchronization issues, and two firmware codebases to maintain
- **Power:** RP2040 draws additional current (significant for balloon battery budget)
- **Failure modes:** Two MCUs = two points of failure
- **Latency:** UART relay of SPI commands adds round-trip latency for radio operations
- **DRC evidence:** Many of the V1 shorts are between RP2040 and C3 nets (UART TX lines shorted, SPI0_SCK↔ESP_TX_RP2040_RX), suggesting the dual-MCU routing is creating congestion and crossing problems

**Recommendation:**
- Keep dual-MCU for V1 prototype (already designed, lowest risk path to first hardware)
- Prioritize C3 SPI timing characterization on the S3 test board
- If C3 can drive SPI at ≥8 MHz reliably with the LR2021, design V2 as single-MCU
- If C3 SPI timing is marginal (<8 MHz or jittery), continue dual-MCU for V2 but consider replacing the RP2040-Zero module with a bare RP2040 chip to reduce footprint and cost

### D) The V1-PCB-GPIO-FIX.md plan — should it be applied to V1 PCB?

**No. V1-PCB-GPIO-FIX.md should NOT be applied to the V1 PCB. It is for the S3 test board or a single-MCU firmware configuration.**

**Evidence:**

1. **GPIO10/NSS:** On the V1 PCB, the C3 does not connect to SPI0_NSS. The RP2040 controls SPI0_NSS on its own pad 6. The firmware Kconfig's `LR2021_NSS=GPIO10` is for a single-MCU design where the C3 directly drives the LR2021's SPI bus.

2. **GPIO1/GPS_RX+FEM_TX:** On the V1 PCB, GPS connects via C3 pad 5 (GPS_TX_ESP_RX) as a UART connection. There is no FEM_TX net on the V1 PCB at all — the board has no front-end module.

3. **LED remapping (GPIO10→GPIO18):** On the V1 PCB, STATUS_LED goes to C3 pad 9, which per footprint analysis maps to approximately GPIO6 (not GPIO10 or GPIO18). The firmware Kconfig's `LED_GPIO=18` doesn't match the V1 PCB either.

4. **Architecture mismatch:** V1-PCB-GPIO-FIX.md assumes a single-MCU architecture (C3 controls everything). The V1 PCB is dual-MCU (RP2040 controls SPI). Applying single-MCU GPIO fixes to a dual-MCU board would be modifying pins that don't exist in the V1 net list.

**What V1-PCB-GPIO-FIX.md IS for:** It describes firmware pin assignments for an S3 test board or a single-MCU V2 design where the C3 directly interfaces with the LR2021, GPS, FEM, and LED without an RP2040 intermediary. This is confirmed by the FEM_TX pin assignment (no FEM exists on V1) and the direct SPI pin assignments on the C3 (V1 routes SPI through RP2040).

---

## Cross-Cutting Findings

### Firmware-Hardware Architecture Mismatch

The most significant systemic finding is that **the firmware Kconfig and the V1 PCB were designed for different architectures:**

| Feature | Firmware Kconfig (single-MCU) | V1 PCB (dual-MCU) |
|----------|-------------------------------|-------------------|
| SPI control | C3 GPIOs (SCK=6, MOSI=7, MISO=2, NSS=10) | RP2040 pads (SPI0_SCK, SPI0_MOSI, SPI0_MISO, SPI0_NSS) |
| LED | C3 GPIO18 | C3 pad 9 (~GPIO6) |
| FEM_TX | C3 GPIO19 | Not present on board |
| GPS | C3 GPIO1 | C3 pad 5 (GPS_TX_ESP_RX, UART) |
| LR2021 control | Direct from C3 | Via RP2040 |

This means the current firmware **will not work on the V1 PCB** even if the DRC shorts are fixed. The firmware expects to drive SPI directly from the C3, but on the V1 PCB the C3 has no SPI connection to the LR2021 — it must send radio commands via UART to the RP2040, which then relays them over SPI.

**Action required:** Either (a) write RP2040 relay firmware and C3 UART-radio-driver for the V1 PCB, or (b) redesign V1 PCB as single-MCU to match the existing firmware. Option (b) is recommended for V2.

### Router Quality (gen_pcb.py)

The systematic nature of the shorts (18× GND↔3V3, all 4 SPI lines shorted, UART TX pairs shorted, RF traces shorted to ground) indicates the custom Router class in `gen_pcb.py` has fundamental issues:

1. **No copper pour isolation:** GND pour overlaps 3V3 traces/pads throughout the board
2. **No net-to-net clearance checking:** SPI traces placed on top of each other
3. **No directional routing:** UART TX lines from opposite directions overlap
4. **RF traces routed through ground pours:** RF_2G4_2400 and RF_SUB_868 shorted to GND

The router needs proper DRC-aware routing before either board can be fabricated. Manual post-routing fixes in KiCad may be faster than debugging the Python router for a one-time prototype run.

---

## Summary Recommendations

| # | Recommendation | Priority | Effort |
|---|----------------|----------|--------|
| 1 | Do NOT order V1 or F33 PCBs as-is | **CRITICAL** | — |
| 2 | Fix 3V3↔GND shorts in V1 (copper pour issue) | **CRITICAL** | Medium |
| 3 | Fix SPI bus shorts in V1 (re-route SPI traces) | **CRITICAL** | Medium |
| 4 | Route all 43 unconnected nets in V1 | **CRITICAL** | Medium |
| 5 | Fix F33 RF↔GND and VCAP shorts | **CRITICAL** | Medium |
| 6 | Route all 32 unconnected nets in F33 | **CRITICAL** | Medium |
| 7 | Generate BOM files for both boards | **HIGH** | Low |
| 8 | Re-run DRC until clean on both boards | **CRITICAL** | Low |
| 9 | Resolve firmware-hardware architecture mismatch | **CRITICAL** | High |
| 10 | Do NOT apply V1-PCB-GPIO-FIX.md to V1 PCB | **HIGH** | — |
| 11 | Characterize C3 SPI timing on S3 test board | **HIGH** | Medium |
| 12 | Plan V2 as single-MCU if C3 SPI timing passes | **MEDIUM** | High |
| 13 | Verify F33 CE↔NSS is intentional or a real short | **MEDIUM** | Low |
| 14 | Update Integration Plan V2 to reflect actual DRC status | **HIGH** | Low |

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| V1 ordered with fatal shorts | Medium (plan says "ready") | Total board failure | Block order until DRC clean |
| Firmware doesn't match V1 hardware | High (confirmed mismatch) | Board works but software can't drive radio | Write RP2040 relay firmware OR redesign as single-MCU |
| 2-week lead time lost on bad boards | Medium | Schedule slip | Fix DRC before ordering |
| C3 SPI timing insufficient for LR2021 | Unknown | Requires keeping RP2040 indefinitely | Characterize on S3 test board first |
| Router bugs recur in manual fixes | Medium | Continued DRC failures | Use KiCad interactive router, not gen_pcb.py |

---

*End of review.*