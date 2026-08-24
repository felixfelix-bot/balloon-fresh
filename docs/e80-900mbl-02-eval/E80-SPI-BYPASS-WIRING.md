# E80-900MBL-02 — STM32 Bypass SPI Wiring Guide

**Purpose:** bypass the on-board STM32F103CBT6 and drive the module's Semtech LR2021
directly over raw SPI from our own hosts (RP2040 Pico + ESP32-C3) using the kit's J2
header. Felix executes the jumper wiring using this document.

**Method:** hold the STM32 in reset (NRST→GND) so all its GPIOs go Hi-Z, then our host
drives the radio SPI lines that are tapped out on J2.

**Sources used (all read-only):**

- `docs/e80-900mbl-02-eval/e80-900mbl-02-manual-id4396.pdf` — manual text layer
  (pdftotext). §2.2 component list, §2.3 J1/J2 pin tables, note ② on DIO8/DIO9.
- `docs/e80-900mbl-02-eval/e80-900mbl-02-spec-id4397.pdf` — board schematic
  (image-only; re-rendered at 300/600 dpi + region OCR; see "OCR confidence" flags).
- `~/repos/lr2021-eval/pdfs/id4393-unpacked/E80_DEMO/E80/Core/Inc/main.h` (lines
  60–81) — exact MCU↔radio pin map from the reference firmware.
- `E80-900MBL-02_CAPABILITY_REPORT.md` — prior consultant extraction (cross-checked;
  agrees on MCU type, module, J2 signal set, DIO8-primary-IRQ).
- `firmware/rp2040/src/multi_radio_sweep.cpp` (balloon-fresh) — host1 pin map
  (identical at git tag `rp2040-baseline-1377kbps`, verified via `git show`).
- `mesh-stack/flrc-bench-espidf/main/esp32_raw_tx.cpp` (balloon-fresh) — host2 pin map.

> **AMBIGUOUS / VERIFY flags:** the schematic is image-only and OCR of tiny labels is
> imperfect. Anything marked **[VERIFY]** must be confirmed by Felix on the physical
> board (visual + DMM) before/while wiring. Do not guess.

---

## 1. SWD "Debug Interface" header

Manual §2.2 item 10: *"Debug Interface — MCU debug interface"* (a separate small
header, NOT J1/J2).

What the schematic OCR resolves (600 dpi region crops):

- The header carries **SWCLK and SWDIO with 33 Ω series resistors** (R2 on SWCLK,
  R4 on SWDIO — labels read "33R"/"3kR" at OCR limits) plus a **+3.3 V** pin.
- Pin numbers observed on the connector: **pin 1 = SWCLK, pin 2 = SWDIO**, with 3V3
  on the next pin; a 4th pin is most likely **GND** — **[VERIFY]** see below.
- A GND symbol appears in the same region of the schematic but OCR could not bind it
  to a numbered pin with certainty.

**What we could NOT find on this header: an STM32_NRST pin.** The STM32_NRST net
(STM32 pin 7) traces only to: R6 = **10 kΩ pull-up to 3V3** (confirmed by zoom OCR),
the RESET push button (manual §2.2 item 7), and the MCU. If the physical header has
only 3–4 pins (3V3/SWDIO/SWCLK/GND) there is **no header pin to ground for
reset-hold**.

**Felix procedure [VERIFY] — 30 seconds with eyes + DMM (continuity mode, board
unpowered):**

1. Count the debug header pins and read the silkscreen (typically marked `DAP`,
   `SWD`, or `Debug`).
2. Identify GND pin: continuity from each header pin to the **USB-C connector shell
   / mounting holes** (≈0 Ω ⇒ GND).
3. Identify 3V3 pin: power board via USB, measure 3.3 V on header pins.
4. **If** a 5th pin exists (common 5-pin layouts add NRST): confirm it is NRST by
   pressing RESET — no, NRST is active; instead confirm by schematic marker or by
   continuity to R6 pad. If confirmed present → **jumper that pin to the header's
   GND pin = STM32 permanently in reset. Done.**
5. **If no NRST pin exists (expected case):** hold the **RESET push button
   (component #7) mechanically pressed** — tape / zip-tie / Blu-Tack over the
   button. The button shorts STM32_NRST to GND; held closed, the STM32 never leaves
   reset and all GPIOs stay Hi-Z. Non-destructive, reversible, fights only the 10 kΩ
   pull-up (0.33 mA — harmless).
   - Last-resort alternative (not needed unless the button can't be held): tack a
     wire onto the R6 pull-up pad / STM32_NRST side and bring it to GND. Avoid —
     it's soldering on a kit we want to keep pristine.

Reset-hold is **non-destructive**: the STM32's flash is untouched; releasing the
button restores the stock demo firmware behavior.

---

## 2. J2 header — pin map and physical numbering

J2 is a **2×9 (18-pin) 2.54 mm dual-row header**. Manual §2.3 table + schematic OCR
agree on the signal order down the two columns; numbering is the standard zigzag
(odd pins down one column, even pins down the other):

| Row | Pin (odd, J2-1 col) | Signal | Pin (even, J2-2 col) | Signal |
|-----|--------------------|--------|--------------------|--------|
| 1 | **1** | **VIN** (module supply net) | **2** | **3V3** |
| 2 | 3 | DIO11 | 4 | DIO10 |
| 3 | **5** | **NRST — radio (module LR-NRESET)** | 6 | 3V3 |
| 4 | **7** | **BUSY** | 8 | DIO7 |
| 5 | **9** | **MISO** | 10 | **DIO8** (IRQ) |
| 6 | **11** | **MOSI** | 12 | DIO9 |
| 7 | **13** | **SCK** | 14 | MCU_TXD (STM32 PA9 ↔ CH340 RXD) |
| 8 | **15** | **NSS** | 16 | MCU_RXD (STM32 PA10 ↔ CH340 TXD) |
| 9 | 17 | DIO6 | 18 | DIO5 |

Bold = the 7 signals we actually wire to the host. Everything else stays
unconnected.

Key facts (cross-checked manual ↔ schematic ↔ `main.h`):

- **J2-3 NRST is the RADIO's reset** (module pin `LR-NRESET`), wired to STM32 PB0
  (`E80_NRST`, main.h:64-65). It is **not** the STM32's NRST.
- SCK/MISO/MOSI/NSS/BUSY/DIO8/DIO9 are shared nets: module pin ↔ J2 pin ↔ STM32
  GPIO (PA5/PA6/PA7/PA4/PA3/PB2/PB1 per main.h:60-71 and schematic `E80_*` nets).
  With the STM32 held in reset those STM32 pins float — no contention with our host.
- J2-14/J2-16 (MCU_TXD/MCU_RXD) belong to the STM32↔CH340 UART. Leave unconnected;
  they carry no radio signals.
- Manual note ② (§2.3): **DIO8 and DIO9 are the LR2021 RF interrupt outputs** —
  normally low, pulse on IRQ; external MCU should trigger on the **rising edge**.

**Physical orientation — [VERIFY]:** which end of the header is pin 1 cannot be
read from the OCR'd schematic/figures. Confirm on the board (silkscreen "1",
square pad, or white dot), and double-check electrically:

- With the board USB-powered, **3.3 V must appear on the even column at rows 1 and
  3 (pins 2 and 6)** — two 3V3 pins stacked with one non-power pin (pin 4 = DIO10)
  between them is a unique fingerprint. If you measure 3.3 V one column over, flip
  your column assignment.
- Optional: continuity pin 2 ↔ pin 6 should be ≈0 Ω (same 3V3 rail).
- Pin 1 (VIN): may read 3.3 V as well (see §3 power note). We never connect to it.

---

## 3. Power architecture

Traced in the schematic (600 dpi OCR of the top-right power section):

```
USB-C (J5) VBUS ──► U7 AMS1117-3.3 LDO ──► +3.3V rail ──► module VCC pin (25)
                    (C17–C20, 100nF/10µF)     │            (local C24 10µF + C23 100nF)
                                              ├──► STM32, CH340X, LEDs, J1/J2 3V3 pins
```

- **USB-C powers the 3V3 rail regardless of the STM32's state.** The LDO input is
  VBUS, not anything the MCU controls. Holding the STM32 in reset does **not**
  affect radio power. No concern powering via USB while reset is held: the STM32 in
  reset draws only mA, the 10 kΩ NRST pull-up sinks 0.33 mA, and the CH340 idles.
- Budget: LR2021 RX ≈ 15–25 mA; 22 dBm TX bursts ≈ 130–160 mA at 3V3 (≈100 mA from
  5 V through the LDO). AMS1117 handles it, but two kits + two host boards on one
  unpowered PC port can hit 500 mA — **use a powered USB hub** for the 4 devices.
- Manual §4.1 item 1 references an **"RF Module Power Supply Jumper Cap"**. The
  schematic OCR could not unambiguously locate this jumper (candidates: the small
  J10–J13 / J6–J9 connector rows, unresolved **[AMBIGUOUS]**). It presumably
  gates 3V3 → module VIN (J2-1 "VIN" is the module supply net, broken out for
  measurement/external feed).
  - **Felix [VERIFY]:** ensure any jumper cap near the module/J2 area is in its
    as-shipped (default = powered) position; then confirm **3.3 V on J2-2/J2-6**
    and PWR LED lit. Optionally DMM continuity J2-1↔J2-2 (0 Ω ⇒ VIN tied to rail).
  - We never feed power into J2-1; both boards stay USB-powered.

---

## 4. Ground strategy

- **J2 has NO GND pin** (18 pins are all signals/3V3/VIN). J1 likewise has no GND
  (both row-9 pins are 3.3V per manual §2.3).
- Nearest GND access points, in order of convenience:
  1. **Debug Interface header GND pin** (expected 3V3/SWDIO/SWCLK/GND layout —
     [VERIFY] as in §1; find it by continuity to USB-C shell).
  2. USB-C connector shell / PCB mounting holes (all tied to GND).
  3. The module's GND pins are SMD castellations — not usable for jumpers.
- **Is USB-common-ground enough?** All four devices (2× kit, Pico, C3) on one PC do
  share ground through the PC. At 1 MHz with tidy wiring that often "works". At
  10 MHz over ~15 cm dupont jumpers the SPI return current would loop through two
  USB cables and the PC — a long, inductive loop that causes ringing, ghost clocking
  and flaky BUSY/IRQ reads. **Add one explicit GND jumper per kit** (Debug-header
  GND → host GND). Cheap insurance; keep it running parallel to the SPI bundle,
  ideally twisting SCK with the GND lead.
- Even with the GND jumper, keep leads ≤15 cm, run the bundle away from the
  antennas, and prefer 1–2 MHz for bring-up (see §7).

---

## 5. Logic levels — no shifter needed

| Device | I/O rail | Notes |
|--------|----------|-------|
| E80-M module (LR2021) | 3.3 V | module VCC = board 3V3 rail (§3); VIH≈0.7·VDD, NOT 5 V tolerant |
| RP2040 Pico | 3.3 V GPIO | GPIO rails at 3.3 V (VSYS→onboard LDO); not 5 V tolerant |
| ESP32-C3 dev board | 3.3 V GPIO | not 5 V tolerant |

All three sides are 3.3 V CMOS — **direct wiring, no level shifter, no series
resistors required to start**. (Optional 33–100 Ω series damping on SCK/MOSI at the
host end only if you later push ≥10 MHz and see ringing — see §7.)

---

## 6. FINAL WIRING TABLES

Only 7 signals + GND per kit. All radio signals are on J2; GND comes from the Debug
Interface header (or USB shell). **STM32 reset must be held (§1) before the host
starts driving lines.**

### E80 kit #1 → RP2040 Pico (host1)

Host1 pin map: `firmware/rp2040/src/multi_radio_sweep.cpp` **lines 43–56**
(SCK=2, MOSI=3, MISO=4, CS=5, BUSY=6, IRQ=7, RST=8; SPI0; 20 MHz capable).
Verified identical at git tag **`rp2040-baseline-1377kbps`** (`git show
rp2040-baseline-1377kbps:firmware/rp2040/src/multi_radio_sweep.cpp`). Pico GP
numbers are the silk "GPn" labels.

| E80 side | J2 pin (signal) | ↔ | Pico GPIO | Role |
|----------|-----------------|---|-----------|------|
| J2 | **9 (MISO)** | ↔ | **GP4** | SPI0 MISO (`spiRf(spi0, MISO=4, CS=5, SCK=2, MOSI=3)`, line 72/106) |
| J2 | **11 (MOSI)** | ↔ | **GP3** | SPI0 MOSI |
| J2 | **13 (SCK)** | ↔ | **GP2** | SPI0 SCK |
| J2 | **15 (NSS)** | ↔ | **GP5** | SPI chip-select (bit-banged, `digitalWrite` lines 119–121) |
| J2 | **7 (BUSY)** | ↔ | **GP6** | radio BUSY (polled, line 110) |
| J2 | **10 (DIO8)** | ↔ | **GP7** | radio IRQ input (poll, lines 422/490; rising-edge per manual note ②) |
| J2 | **5 (NRST, radio)** | ↔ | **GP8** | radio hard reset (lines 280–283) |
| Debug hdr | **GND** [VERIFY] | ↔ | **GND** (any GND pin, e.g. 3/8/13/18/23/28/33/38) | common ground |

Leave unconnected: J2-1 (VIN), J2-2/J2-6 (3V3 — board self-powered via USB),
J2-3/4/8/12/14/16/17/18, all of J1, both antennas unless testing RF.

### E80 kit #2 → ESP32-C3 dev board (host2)

Host2 pin map (validated): `mesh-stack/flrc-bench-espidf/main/esp32_raw_tx.cpp`
**lines 30–35** (SCK=6, MOSI=7, MISO=2, NSS=10, BUSY=4, RST=3; same map in
`esp32_raw_rx.cpp` lines 27–32) + IRQ = GPIO5 from the validated map carried in the
bypass task brief. GPIO numbers are the module-internal IO numbers printed next to
the pin on C3 dev boards.

| E80 side | J2 pin (signal) | ↔ | ESP32-C3 GPIO | Role |
|----------|-----------------|---|---------------|------|
| J2 | **9 (MISO)** | ↔ | **GPIO2** | SPI MISO |
| J2 | **11 (MOSI)** | ↔ | **GPIO7** | SPI MOSI |
| J2 | **13 (SCK)** | ↔ | **GPIO6** | SPI SCK |
| J2 | **15 (NSS)** | ↔ | **GPIO10** | SPI CS (manual toggle; `EspHalC3.h:167` sets spics=-1) |
| J2 | **7 (BUSY)** | ↔ | **GPIO4** | radio BUSY (polled, lines 61/126) |
| J2 | **10 (DIO8)** | ↔ | **GPIO5** | radio IRQ (rising edge, manual note ②) |
| J2 | **5 (NRST, radio)** | ↔ | **GPIO3** | radio hard reset (lines 199–201) |
| Debug hdr | **GND** [VERIFY] | ↔ | **GND** | common ground |

Note: GPIO2 is an ESP32-C3 strapping pin. LR2021 MISO idles high-Z while NSS is
deasserted, so it does not contend with boot; if the board ever refuses to boot with
the harness attached, check levels on GPIO2/8/9 before blaming wiring.

**Bring-up order (both hosts):** configure host pins first (SCK low, MOSI low, NSS
high, RST low) → then attach/re-attach jumpers → release RST high → wait ≥10 ms →
poll BUSY until low → SPI Mode 0, MSB-first, start at **1–2 MHz**, read chip status
(0x0110-ish LR20xx command set / RadioLib) to confirm, then step up clock if clean.

---

## 7. Risks & pitfalls

1. **STM32 GPIO state while held in reset** — F103 GPIOs default to floating input
   (Hi-Z) in reset: no drive fight on any radio line. PB0 (radio NRST) also floats
   while the STM32 is held — **our host owns radio NRST via J2-5**, so there is no
   window where the radio's reset line is undriven except before host boot; keep
   host RST output low at boot (bring-up order above).
   *STM32's own NRST has an internal pull-up and R6 10 kΩ external pull-up — that's
   the STM32's reset, not the radio's; grounding it (button held) is safe.*
2. **Radio NRST external pull-up?** No pull resistor was observed on the E80_NRST
   net in any schematic crop; the radio relies on its internal reset state / host
   drive. **[AMBIGUOUS-lite]** — moot in practice because the host actively drives
   J2-5; do not depend on the line self-idling high when no host is attached.
3. **BUSY line** — LR2021 BUSY is push-pull, idle LOW, and is an *input to whoever
   polls*: host configures GP6/GPIO4 as input. No external pull observed (the
   "10K" found in OCR is R6 on STM32_NRST).
4. **DIO8 vs DIO9 as IRQ** — both are IRQ-capable per manual note ② (both idle low,
   pulse high). Demo firmware uses **DIO8 as primary** (PB2/EXTI2 →
   `radio_irq_callback`), DIO9 secondary. We wire **DIO8** (J2-10); if a board ever
   needs a second IRQ line, J2-12 (DIO9) is the spare — same electrical rules.
5. **SPI over ~15 cm jumpers** — ground reflection/ringing risk at ≥10 MHz.
   Mitigations: explicit GND jumper (§4), keep harness short, SCK twisted with GND,
   start at 1–2 MHz, add 33–100 Ω series resistor on SCK (host end) only if
   ringing appears. RP2040 firmware runs SPI at 20 MHz for directly-wired modules —
   do NOT assume that clock over the eval-board harness without error-rate checks.
6. **Reset-hold must be in place before power-up of the STM32's demo firmware**
   matters — actually the demo only drives the radio after boot; if you power the
   kit with the button not yet held, the STM32 will configure the radio into RX and
   drive SCK/MOSI/NSS. Fix: hold reset first, or power-cycle the kit after holding.
   A brief overlap (<1 s) of host-driven vs STM32-driven 3.3 V push-pull lines is
   unlikely to damage anything, but avoid it — apply reset-hold before USB power.
7. **Keep the kit non-destructive** — reset-hold never writes STM32 flash; do not
   attach an ST-Link, do not flash via USB while bypassed; CH340 traffic is
   irrelevant (UART pins not wired to host).
8. **RF safety** — do not TX without antennas on both SMA jacks (manual §5.2);
   22 dBm into an open PA can degrade the module. Screw antennas on before RF tests.

---

## 8. Physical orientation guide (manual §2.2 numbered components)

Manual §2.2 list (transcribed; use the §2.1/§2.2 board figure to match numbers to
positions):

| # | Component | What Felix needs from it |
|---|-----------|--------------------------|
| 1 | E80-M series module (LR2021 SMD, center of board) | the device we're driving |
| 2 | 2.4 GHz antenna interface (SMA-K female) | antenna for HF tests |
| 3 | Sub-1 GHz antenna interface (SMA-K female) | antenna for Sub-GHz tests |
| 4 | Pin header **J1** (STM32 GPIO: PA0…PC13 + 3V3, no GND) | not used — leave open |
| 5 | KEY2 | not used |
| 6 | KEY1 | not used |
| 7 | **RESET button** — resets the STM32 (not the radio) | **hold pressed for bypass (§1 step 5)** |
| 8 | USB Type-C ↔ UART (power, firmware burn, CH340 bridge) | power for kit; PWR/LED1(LINK)/LED2(DATA) |
| 9 | Indicator lights PWR / LINK / DATA | PWR lit = 3V3 rail up (§3 check) |
| 10 | **Debug Interface** (MCU SWD: SWDIO/SWCLK + 3V3 + GND) | **GND source for our jumper [VERIFY]**; (no NRST observed — §1) |
| 11 | Pin header **J2** (radio SPI/DIO breakout) | **the header we wire (§2, §6)** |

Typical EByte eval-kit layout (verify against the board): USB-C at one short edge;
J1 and J2 along the two long edges flanking the module (J2 = the radio-side header);
debug header is a small 3–5 pin row near the STM32 (opposite corner from the USB
connector area); RESET/KEY buttons near the USB edge.

---

## 9. Pre-flight checklist (Felix)

1. [ ] STM32 reset-hold in place (debug-header NRST→GND if the pin exists, else
       RESET button taped down) — **before** USB power.
2. [ ] USB power to both kits; PWR LEDs on; 3.3 V measured on J2-2 and J2-6.
3. [ ] J2 orientation confirmed (3V3 on even column rows 1 & 3, §2).
4. [ ] 7 signal jumpers + 1 GND jumper per kit per §6 tables.
5. [ ] Antennas attached (only if/when transmitting).
6. [ ] Host firmware pins: RST low at boot → release → BUSY low → SPI @1–2 MHz →
       status register read OK → raise clock as error-rate allows.

*Doc generated from primary sources; OCR-derived items flagged. Schematic:
e80-900mbl-02-spec-id4397.pdf (single page). Manual: e80-900mbl-02-manual-id4396.pdf
v1.00.*
