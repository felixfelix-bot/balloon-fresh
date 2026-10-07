# External clock injection (pin level) and the OCXO question

**Status: ANALYSIS — answers two separate questions. It is not an ADR and it authorises
no design change.** It orders nothing, modifies no design file, and reaches a *split*
verdict on purpose: **Part A ("can an external clock be injected?") is a per-radio,
pin-level question with a different answer for each part; Part B ("does a heated
oscillator make sense?") answers NO; Part C asks whether any of this stability is even
needed and answers "not for the link — only, and cheaply, for time".**

- Date: 2026-10-07
- Base: `github/main` @ `6749dde`
- Operator's question (verbatim intent): *"Is it possible to connect an external clock to
  the radio or external crystal oscillator which comes with a heater so that the
  oscillator doesn't drift with temperature? Would this make sense?"*
- Companion (written concurrently by another worker, **not touched here**):
  `docs/analysis/thermal-and-frequency-drift.md`.
- Every number below is cited to a datasheet or a repo file, or marked
  `TODO(unverified)`. No part number, pin name, figure or URL is invented. Datasheets
  that are not in-tree were fetched and read during this analysis; they are named in
  full so the reading can be reproduced.

---

## Part A — Can an external clock / TCXO actually be injected, per radio?

**Short answer: only one of the five parts can accept an external clock at a pin you
can reach.** Two of the three radios are modules whose reference is sealed inside the
part, one is a bare chip with a real TCXO input, and the MCU/GNSS answers are "no" and
"it already has one", respectively.

| Part | Internal reference | External clock / TCXO possible? | Pins | What is required |
|---|---|---|---|---|
| **LoRa2021F33-2G4** (433 MHz 1 W module) | **Yes — internal industrial-grade 0.5 ppm TCXO**, non-overridable | **NO** | **None.** The module has no clock/TCXO pin at all | Nothing to do; the TCXO is already fitted and always-on. Decisive negative result |
| **Bare NiceRF LoRa2021** (2.4 GHz RX / LP module) | The LR2021 **chip** inside supports crystal *or* TCXO; the NiceRF module as fitted in this repo is **crystal-only, no TCXO, no NTC** | **NO at module level** | Module pad **13 = VTCXO**, but that is an **output**; the module does **not** break out the chip's XTA/XTB clock inputs on its 18 castellations | None available on this module. An external clock cannot be fed to it |
| **SX1280** (bare Semtech chip) | **None — requires an external reference** | **YES** | **XTA (pin 4) = "Reference oscillator connection or TCXO input"**; **XTB (pin 6)** = the other oscillator terminal; AC-couple the TCXO into XTA, XTB unused for TCXO | A 52 MHz-class reference; a TCXO AC-coupled to XTA (with its **own supply rail** — see below). `TODO(unverified)`: exact TCXO drive level and the datasheet's own component values (Fig. 14-3 tip values are not legible in the text layer) |
| **ESP32-S3-WROOM-1U** | **Internal 40 MHz crystal** (in-module) | **NO for the main clock.** The chip's own `XTAL_P`/`XTAL_N` are **not** broken out on the WROOM-1U; a **32 kHz** clock *can* be injected on `XTAL_32K_P/N` (GPIO15/16) | WROOM-1U: none for the 40 MHz clock. Chip: `XTAL_P`/`XTAL_N` (pins 54/53) exist but are consumed by the in-module crystal | **Irrelevant to the link anyway.** Wi-Fi/BT are compiled out (`CONFIG_ESP_WIFI_ENABLED=n`, `CONFIG_ESP_BT_ENABLED=n` — ADR-038), and every radio carries its own reference, so the MCU clock does not discipline the radios |
| **MAX-M10S GNSS** | **Yes — internal TCXO** | N/A — it is the reference source, not a consumer | **TIMEPULSE (pin 4)** = 1PPS output | Nothing to add. It **is** the discipline source: default **1PPS**, configurable 0.25 Hz–10 MHz, RMS accuracy **30 ns** |

### A1 — LoRa2021F33-2G4: the repo's claim is CORRECT, and it is a hard negative

`docs/F33-MODULE-PLAN.md` (lines 18, 44, 115) asserts the module has an internal
industrial-grade 0.5 ppm TCXO with **no VTCXO pin**, and that the design removed a VTCXO
decoupling cap (C3) for that reason. **Verified against the module datasheet.**

- The F33 datasheet cover page lists *"Industrial-grade TCXO Crystal Oscillator
  0.5PPM"*, and §6 "Electrical Characteristics" gives **`Frequency Error = 0.5 ppm`**
  (`docs/f33-module/LoRa2021F33-2G4-datasheet-v1.1.pdf`, Rev 1.1).
- §7 "Pin definition" enumerates **all 18 pins**: VCC, 7×GND, CE, ANT, ANT-2G4, SCK,
  NSS, BUSY, MOSI, MISO, RESET, IRQ. **There is no XTA, XTB or VTCXO pin.**
- The F33 footprint data records the same: `tracker/hardware/footprints/nicerf-lora2021f33-2g4.json`
  has `"removed_pins": "VTCXO (was Pin 13 on bare), DIO7 ... DIO8 ... DIO9 ..."`.
- `tracker/hardware/hub_board_diy/hub_board_diy.kicad_sch:116` — `;; C3 REMOVED — F33
  has internal TCXO, no VTCXO pin`.

**Conclusion: this radio CANNOT accept an external clock.** There is no pin to feed one
to and the fitted TCXO cannot be overridden. This is the decisive negative result: for
the F33, the operator's proposed hardware change is not merely unnecessary, it is
**physically impossible**. (The same 0.5 ppm figure is where DUAL-VARIANT-DESIGN.md's
"Built-in 0.5ppm" row comes from.)

### A2 — Bare NiceRF LoRa2021: the *chip* can, the *module* cannot

`docs/DUAL-VARIANT-DESIGN.md` line 78 reads **`TCXO | External (VTCXO pin)`** for the
bare module versus `Built-in 0.5ppm` for the F33. The two halves of that row need
separating, because they are at different levels of the stack.

- **The LR2021 chip** genuinely supports a TCXO. Datasheet
  `docs/LR2021_LR2022_LR2012_Datasheet_Rev2.1.pdf` §1.9.2–1.9.3: the 32 MHz reference
  *"can be sourced from either an external crystal oscillator or a Temperature-Compensated
  Crystal Oscillator (TCXO)"*; *"The TCXO should be connected to the XTA pin … The XTB
  pin should be unconnected"*; and the TCXO *"can be supplied by the internal regulator
  via the VTCXO pin … programmed using the SetTcxoMode command"*. Pin table §Table 2-1:
  **pin 4 = XTA, "32MHz crystal oscillator connection; can be used to input external
  reference clock"**; **pin 6 = VTCXO/VNTC, "External TCXO supply voltage (REG_TCXO)"**.
  So at chip level the answer is YES, on XTA, powered from VTCXO.
- **The NiceRF module does not expose XTA.** `docs/assets/lr2021/LoRa2021-Module-Datasheet-V1.3.pdf`
  §7 lists all 18 pads: `1 VCC · 2,8,11,12,18 GND · 3 MISO · 4 MOSI · 5 SCK · 6 NSS ·
  7 BUSY · 9 ANT · 10 2.4/S_ANTA · 13 VTCXO · 14 RST · 15 DIO9 · 16 DIO8 · 17 DIO7`.
  **Pad 13 is `VTCXO`, described as `O — "Can provide power for an external TCXO"`** —
  i.e. it is the chip's regulated TCXO-*supply* output brought out for the module
  designer, **not** a clock input. There is no XTA pad, so there is nowhere to return a
  TCXO's clock.
- The repo already treats it that way: `tracker/hardware/hub_board/hub_schematic.py:78`
  annotates *"13=VTCXO(NC,float)"* and line 192 *"LR2021 pin 13 (VTCXO) is internally
  controlled on the NiceRF module"*; `tracker/hardware/u2_lora2021_swap.py:32/69` lists
  pad 13 among "pads carrying NO net".

**Conclusion: the bare NiceRF LoRa2021 is module-locked to whatever reference NiceRF
soldered inside it. It cannot accept an external clock at any reachable pin.** Whether
that internal reference is a crystal or a TCXO is a *module-BOM* question, and the repo
contains conflicting statements about which was fitted:
`docs/assets/lr2021/README.md:18` says *"TCXO: 0.5 PPM, onboard, powered via VTCXO pin"*,
while `docs/LR2021-LESSONS-2026-09.md` line 22 records the four owned plain modules as
*"crystal, no TCXO, no NTC (carlhodder deshielded to verify)"*. The datasheet prints both
options (`Frequency Error … @Crystal 10 ppm … @TCXO 0.5 ppm`, V1.3 §4). **The resolution
that matters here is that neither variant gives the operator a clock pin.**
`TODO(unverified)`: which reference the four owned modules actually carry (a deshield
photo would settle it).

### A3 — SX1280: YES, and this is the only real clock-injection point

The SX1280 is a bare transceiver IC and needs an external reference. Semtech data sheet
**DS.SX1280-1.W.APP Rev 1.0 (February 2017)**, read for this analysis:

- Pin table: **pin 4 = `XTA` — "Reference oscillator connection or TCXO input"**;
  **pin 6 = `XTB` — "Reference oscillator connection"**.
- **§14.2 "Application Design with optional TCXO"** (p. 124) plus **Figure 14-3
  "Application Schematic with Optional TCXO"**: *"an external Temperature Compensated
  Crystal Oscillator (TCXO) can be used. The figure below shows how the TCXO should be
  AC-coupled to the XTA input of transceiver."*
- §3.7 / Table 3-9: **`FXOSC` = 52 MHz** nominal.

**A correction to the premise, stated plainly.** The design hypothesis was that the
SX1280 offers a "DIO3-style TCXO-enable provision" (an on-chip switched supply for the
TCXO, as the SX126x family has). **Figure 14-3 does not show one.** In that schematic
the TCXO has its **own rail** (VDD_3V3 through ferrite beads), is AC-coupled into XTA
through a series capacitor, and **DIO3 is simply pulled to VDD_RADIO through a 0 Ω
resistor (R15)** — it is an ordinary multi-purpose I/O, not a TCXO power switch
(pin table: *"pin 10 = DIO3 — Optional multi-purpose digital I/O"*). So on the SX1280,
**gating the TCXO means gating its external rail with a load switch / MCU GPIO — there is
no on-chip gate.** That is a small, cheap addition, and it is the mechanism Part B's
duty-cycling argument relies on.

Two honest caveats, both `TODO(unverified)`:
- Figure 14-3 labels the TCXO **"32.0 MHz"**, which contradicts Table 3-9's **52 MHz**
  `FXOSC`. One of the two is a datasheet error; the FXOSC spec is the authoritative one,
  but the discrepancy should be reconciled with Semtech before a part is ordered.
- The figure's component values (AC-coupling cap, bias R) are not legible as text; the
  part-specific BOM must come from §14.2's pointer to the TCXO manufacturer.

Repo context: the SX1280 appears in `docs/adr/108-f33-sx1280-pin-plan.md` as a dedicated
ranging radio on SPI3, with `SX1280_DIO2`, `SX1280_DIO3` and `SX1280_ANT_SW` explicitly
broken out to the ESP32-S3 — so a TCXO-rail load-switch GPIO is already available in that
plan. Also worth flagging: the in-tree file `docs/adr/101-lr2021-only-ban-sx1280.md`
carries an SX1280-ban *filename* but its content is the ADR-020 "superseded / LR2021 SPI
protocol clarification" text; it contains no operative ban. `TODO(unverified)`: whether
an SX1280 ban exists elsewhere.

### A4 — ESP32-S3-WROOM-1U: possible at chip level, impossible at module level, and irrelevant

- `esp32-s3-wroom-1_wroom-1u` datasheet: the module block diagram shows a **40 MHz
  crystal oscillator inside the module**; the WROOM-1U pin list contains no XTAL pin.
  The chip's own `XTAL_P`/`XTAL_N` (pins 54/53, "External clock input/output connected to
  chip's crystal or oscillator" — `esp32-s3` datasheet) are consumed by that in-module
  crystal and are not brought out.
- The only clock input on the module is the **32 kHz** RTC clock on `XTAL_32K_P/N`
  (GPIO15/GPIO16). A 32 kHz reference cannot discipline a 2.4 GHz carrier, and it is not
  needed for anything here.
- **It does not matter.** Wi-Fi and BT are never enabled — `tracker/firmware/sdkconfig.defaults.esp32s3`
  sets `CONFIG_ESP_WIFI_ENABLED=n` and `CONFIG_ESP_BT_ENABLED=n`, and their external
  antenna path is left unpopulated (ADR-038). The radios (F33/LR2021, SX1280) each carry
  their **own** reference and are clocked independently of the MCU. So even if a clock
  could be injected into the S3, it would improve nothing on the RF link.

### A5 — MAX-M10S GNSS: it already has the TCXO, and it provides 1PPS

- **Internal TCXO confirmed**: u-blox **MAX-M10S Data Sheet UBX-20035208**, §9.2 Table 23
  product-marking variant **"S = Standard precision, ROM, TCXO, LNA, and SAW filter"** —
  i.e. the M10S part integrates a TCXO.
- **1PPS output confirmed**: §1.2 gives *"Frequency of time pulse signal — Default 1PPS
  (0.25 Hz to 10 MHz configurable)"* with *"Accuracy of time pulse signal — RMS 30 ns"*;
  the pin table lists **pin 4 = `TIMEPULSE`, O, "Time pulse signal"**.
- The repo already wires it: `docs/adr/108-f33-sx1280-pin-plan.md` assigns `GNSS_PPS` to
  **GPIO21 (input, timestamp interrupt)**; ADR-019 gives the RP2040 wiring (`PPS → GP14,
  1 pulse-per-second interrupt`).

**So the reference the GPS-discipline proposal depends on is real and already on the
board.** This is the part of the answer that costs zero grams and zero watts.

---

## Part B — Does a heated oscillator (OCXO) make sense? **NO.**

An OCXO holds its crystal at a constant temperature, typically a set point in the
**+60 … +90 °C** band, *continuously*. From the mission ambient of **−55 °C**
(`docs/adr/042-thermal-drift-strategy.md`, `docs/adr/043-cold-qualification-heating.md`,
mission minimum −60 °C; the operator framed −50 … −56 °C) that is a **ΔT of ~115–145 K**.
An OCXO on this vehicle is rejected twice over: once by the energy store, and once —
more fundamentally — by the fact that it cannot be switched off.

### B1 — The power arithmetic

**Real datasheet figures (both parts read during this analysis):**

| OCXO | Steady-state power @ 25 °C | Warm-up / cold | Rail | Operating range | Hand-solderable? |
|---|---|---|---|---|---|
| **SiTime SiT5501** (Elite X MEMS precision oscillator, marketed as OCXO) | **`Idd` 44 mA typ / 53 mA max** → **≈0.145 W typ (0.175 W max) at 3.3 V** | `OE Disable Current` **43 mA** — disabling the output saves ~1 mA (the oven keeps running) | 2.5–3.3 V | −40 … +105 °C | Yes — **7.0 × 5.0 mm** ceramic |
| **Raltron OXD30** (quartz OCXO) | **`PS` = 2.0 W typ, "Steady state, @ 25 °C"** | **`PS,w` = 4.7 W typ, "During warm-up, @ 25 °C"** | 5.0 V ±5% | −40 … +80 °C | Yes (through-hole/SMD) |

Sources: SiTime **SiT5501** datasheet Rev 1.03, Table 2 "DC Characteristics"
(`Idd` min/typ/max with a general note fixing typical values at 25 °C and 3.3 V Vdd;
package §"7.0 mm x 5.0 mm ceramic package"); Raltron **OXD30** datasheet (May 2022),
electrical table rows `PS` / `PS,w`.

Note the important structural fact already visible in the table: **on the SiT5501,
disabling the output (`OE`) drops current from 44 mA to 43 mA.** An oven cannot be turned
down; only its output can. That is the whole of §B2 in one datasheet row.

**Two thermal-conductance methods, both labelled as estimates.**

*Method 1 — scale the 25 °C datasheet figure to cold* (assumes constant conductance
`G`; the set point is not printed on either datasheet, so this is an **ESTIMATE**):

```
P = G · ΔT,  with G inferred from the 25 °C figure at its implied ΔT

SiT5501 : G ≈ 0.145 W / 60 K  = 2.4 mW/K ; ΔT(−55 °C, set point ~85 °C) = 140 K
          → P_cold ≈ 0.34 W
OXD30   : G ≈ 2.0   W / 50 K  = 40  mW/K ; ΔT(−55 °C, set point ~75 °C) = 130 K
          → P_cold ≈ 5.2 W
```

*Method 2 — the repo's own thermal resistance*, `P = G · ΔT` with
`G = 1/R_thermal` and `R_thermal ≈ 100 K/W` (the ESTIMATE used in
`docs/adr/042-thermal-drift-strategy.md` §D1 and `docs/adr/043`), plus a more insulated
`R_thermal = 50 K/W`:

```
G = 0.01 W/K (R = 100 K/W):  ΔT = 115 K → 1.15 W ;  ΔT = 145 K → 1.45 W
G = 0.02 W/K (R =  50 K/W):  ΔT = 115 K → 2.30 W ;  ΔT = 145 K → 2.90 W
```

**Both methods land in the same place: order 0.3 – 5 W continuous, at −55 °C.** For
comparison, the number the operator asked about — the 1 W case — is:

**How long does the 33 J bank last?** Usable bank energy is **33.264 J**
(`docs/adr/050-mppt-charge-path.md` §3.10: one cut is budgeted at ≤10 % = ≤3.33 J of a
**33.264 J** usable bank; the same figure underlies ADR-051's "85.7 s at the 0.388 W
average"):

| Heater power | Bank life `t = 33.264 J / P` |
|---|---|
| **1.0 W (the operator's case)** | **≈ 33 s** |
| SiT5501, cold (Method 1) ≈ 0.34 W | ≈ 98 s |
| Repo method, G = 0.01 W/K, ΔT = 145 K | ≈ 23 s |
| Repo method, G = 0.02 W/K, ΔT = 145 K | ≈ 11 s |
| OXD30 at its 25 °C datasheet figure (2.0 W) | ≈ 17 s |
| OXD30, cold (Method 1) ≈ 5.2 W | ≈ 6 s |

**Against the vehicle, the factor is 3–5 orders of magnitude:**

- **Night anchor is 100 µW** (ADR-036, and ADR-051 §1.6 restates it). The OCXO is
  **≈3 400×** (SiT5501 cold) to **≈52 000×** (OXD30 cold) the entire night budget.
- **10-hour night energy**: `0.34 W × 36 000 s = 12.2 kJ`; `5.2 W × 36 000 s = 187 kJ`.
  Against the 33.264 J bank that is a shortfall of **≈370×** and **≈5 600×**.
- **Solar average is 0.388 W** (`docs/POWER-BUDGET-V9-D2BE.md:85`; ADR-051 §1.4). A cold
  SiT5501 would spend **≈87 % of the whole average**; a cold OXD30 would need **13.4×**
  the average.
- **Array peak is 7.2 W** (ADR-049/051/053). The cold OXD30 would consume **≈72 % of the
  full-sun peak** — and the peak is absent precisely when an oven is needed.

**By what factor does an OCXO fail? Against the night anchor, ~3 400× at best and
~52 000× at worst; against the 33 J store, 370×–5 600× short of surviving one night.**
It is not a marginal inefficiency; it is arithmetically impossible, exactly as
ADR-042 §D1 and ADR-043 already found for a *board* heater — this analysis reaches the
same verdict for an *ovenised oscillator*, which is the same physics at a smaller scale.

### B2 — The structural reason (the more important argument)

> **An OCXO must hold its crystal at temperature *continuously* to be stable, including
> all night, so it consumes power 24/7 and cannot be duty-cycled. A TCXO compensates
> *electronically* and is accurate within milliseconds of power-up, so it can be switched
> off between packets. On a vehicle with no battery, a 100 µW night budget and a
> supercapacitor store, that difference is decisive.**

Spelled out against this vehicle's own policy:

1. **An oven's accuracy is the *absence* of a temperature gradient.** The SiT5501 row
   above is the proof: cutting the output (43 mA vs 44 mA) saves nothing, because the
   oven is the load. Switch the oven off at night and you have not "saved power", you have
   an ordinary unpowered crystal — the very ±10–30 ppm part you were trying to avoid — and
   you pay a multi-minute warm-up (`OXD30`: `tW = 5 min` to ±100 ppb) before it is
   accurate again. A duty-cycled oven is a contradiction in terms.
2. **ADR-036 makes the night mandatory deep sleep, with no night TX, because the buffer
   is sized to one burst, not the mission.** `docs/POWER-BUDGET-V9-D2BE.md` §"Night sleep"
   records that even 1 mW of night housekeeping for 10 h is 36 J — already not feasible
   with the fitted bank. An OCXO is 340–5 200 mW. There is no version of this that the
   policy admits.
3. **A TCXO has no such constraint.** A TCXO is a crystal plus a compensation network;
   its output is correct within milliseconds of power-up, so it only has to be powered
   while the radio is on. On this vehicle the radio is **daylight-only** anyway
   (ADR-036), so at night a TCXO draws **zero** — not "a little", zero, because the whole
   radio is off.
4. **Where gating matters, it is available.** On the SX1280 (§A3) the TCXO sits on its
   own rail, AC-coupled into XTA, with no on-chip switch — so a single load switch driven
   by an MCU GPIO gates it, and the SX1280 pin plan (ADR-108) already brings out spare
   control I/O. Duty-cycled, the numbers are small: the LR2021's TCXO-regulator load
   current is **`ILTCXO` 1.5 mA typ / 4 mA max** (`LR2021…Rev2.1.pdf`, Table 3-25), i.e.
   **4.9–13.2 mW at 3.3 V**; at the repo's ~1 % TX duty
   (`docs/POWER-BUDGET-V9-D2BE.md`: 1 % of a 1.20 A burst) that is a **≈50–130 µW
   averaged** — the same order as the *entire* 100 µW night anchor, and **0 µW at night**
   because TX is daylight-only. Contrast the oven, which must pay its 0.34–5.2 W *at
   night, when there is no sun*.
5. **In v9 the F33 already carries its TCXO internally and always-on**, and the F33 is
   the radio that matters (ADR-034 band split; ADR-108 pin plan). So for the primary
   radio there is not even a rail to gate — the stable reference is simply bought inside
   the module at "0 firmware, 0 characterisation, milliwatts inside the part"
   (ADR-042 §D2).

**Therefore: an oven must run when there is no sun; a TCXO need not. That is the reason a
TCXO works here and an oven cannot.**

For completeness, the two further arguments already recorded in the repo still apply and
are not weakened by being an oscillator rather than a board heater: a heat-only loop must
reach above the hottest ambient it meets, so the set point and the lift both grow
(ADR-042 §A3.1); and deliberate heating biases the MS56xx pressure sensor and corrupts
altitude telemetry (ADR-042 §D6) — though a *sealed* OCXO dissipates inside its own can,
which softens, but does not remove, the adjacent-sensor concern.

---

## Part C — Is the stability even needed?

**No — not for the link.** The link tolerates far more carrier offset than any of these
references produces. What is genuinely at risk is **time/phase agreement between the two
ends**, and that is solved by GPS 1PPS discipline, not by any oscillator upgrade.

### C1 — What carrier offset does LoRa tolerate?

From `docs/LR2021_LR2022_LR2012_Datasheet_Rev2.1.pdf`:

- **`LORA_FERR_L1`: "LoRa Maximum tolerated frequency offset between transmitter and
  receiver" — All bandwidths — ±25 % BW.**
- `LORA_FERR_L2`: same, **±33 % BW** for at most 3 dB degradation.
- `LORA_FERR_L4`: **at SF12, ±100 ppm** for at most 1.5 dB degradation ("the tighter limit
  between this specification and FERR_L1 or FERR_L2 applies"); `LORA_FERR_L5`: ±200 ppm at
  SF11.
- §9.7 "Extended LoRa Rx Bandwidth": *"LoRa links can cope with up to 31 kHz of frequency
  misalignment (for the nominal 125 kHz bandwidth) … The LR2021 … expands further this
  capability by offering up to ±33 % of LoRa BW frequency tolerance, pushing the limit to
  ±41.25 kHz of frequency lenience for 125 kHz BW."*

Converted to kHz and set against the module's stated stability (all four rows are within
tolerance at the sub-GHz LoRa bandwidth the design uses):

| Reference | Offset @ **433 MHz** | Offset @ **2.4 GHz** | vs LoRa BW125 (±31.25 / ±41.25 kHz) |
|---|---|---|---|
| **0.5 ppm** (F33 / any TCXO) | **216 Hz** | **1.20 kHz** | ~100× inside |
| **±10 ppm** (datasheet crystal max) | 4.33 kHz | 24.0 kHz | ~7× inside (±31.25 kHz) |
| **±20 ppm** | 8.66 kHz | 48.0 kHz | ~3.6× inside |
| **±30 ppm** (a cheap crystal, worst case) | 12.99 kHz | 72.0 kHz | ~2.4× inside |

The F33 datasheet even lists *"Higher frequency offset tolerance (for harsh RF
environments)"* as a designed feature, and the LR2021 gives the same capability at SF12
as **±100 ppm** — 8.66 kHz of headroom at 433 MHz against a 10 ppm part's 4.33 kHz.

**Plainly: a plain ±20–30 ppm crystal is still inside LoRa's carrier tolerance at the
433 MHz/BW125 operating point. The operator does not need better stability for the LINK at
all.** Two caveats, stated so they are not hidden:

- **At 2.4 GHz a 30 ppm part is marginal in the narrowest band**: ±30 ppm = 72 kHz versus
  LoRa BW203's ±25 %BW = 50.75 kHz (extended ±33 % = 67.0 kHz). But the 2.4 GHz path is
  **RX on the F33, whose internal 0.5 ppm TCXO gives 1.2 kHz** (ADR-034 band split;
  ADR-041's link budget works the 2.4 GHz uplink at SF12/BW125). The 2.4 GHz path is
  TCXO-referenced either way.
- **FLRC is less lenient than LoRa.** FLRC 2.4 GHz `FERR`: **±150 kHz** (2.6 Mbps),
  ±100 kHz (1.3/1.04 Mbps), **±70 kHz** (650 kbps), **±50 kHz** (520 kbps)
  (`LR2021…Rev2.1.pdf`, Table 3-13). 0.5 ppm (1.2 kHz) is trivially inside all of them;
  a 30 ppm part (72 kHz) would exceed the two slowest rates. Another reason not to fly a
  bare crystal at 2.4 GHz.

### C2 — The real risk is time/phase, and GPS fixes it (zero grams, zero watts)

Reading the phase/time records — `docs/adr/017-phase-sync-via-reference-clocks.md`,
`019-gps-synchronized-mode-switching.md`, `021-absolute-utc-phase-sync.md`,
`023-tx-autonomy-and-mode-sync.md`:

- The problem the architecture actually has is **both ends agreeing which sweep phase is
  active**, not carrier regaining. Phase is computed **independently** on each board from
  absolute UTC (ADR-017: *"Each board computes the current phase from its own UTC time
  source using a shared deterministic function"*; ADR-021: `phase = phaseTable[utcSeconds
  % totalCycleSeconds]`).
- **The tolerance is coarse**: ADR-017 invariant 4 — *"RX clock accuracy: NTP
  (millisecond) — sufficient for 3–5 s phase slots"*, and *"As long as both clocks agree
  within ~500 ms, they stay in the same phase"*, with invariant 5 bounding drift at
  *"<10 ppm = <36 ms/hour"*. **500 ms against 36 ms/hour is a ~14× margin, already
  satisfied by the plain crystal** — an oscillator upgrade buys nothing here.
- **The failure mode observed in the field was a sync bug, not drift**: ADR-021 records
  that the TX 60 s boot GPS gate falling back to `millis()` produced *"complete phase
  desynchronization … zero packets decoded"*, and ADR-023 records TX/RX running different
  cycle lengths. Both are **firmware**, fixed by continuous UTC phase computation and a
  shared phase table — not by ppm.
- **The discipline source already exists and is already wired**: MAX-M10S provides UTC
  from the RMC sentence *even without a position fix* (ADR-021) and **1PPS at 30 ns RMS**
  (§A5), wired to `GNSS_PPS` (ADR-108) / `PPS → GP14` (ADR-019).

**So: the degradation risk is time/phase sync, and it is fixed by GPS 1PPS discipline —
zero grams, zero watts — rather than by any oscillator upgrade.** A TCXO (or OCXO) does
not improve phase agreement between two boards; a shared UTC epoch does.

**What *is* a legitimate oscillator-related firmware requirement** — and it is a
*recalibration*, not a stability purchase — is ADR-042 §A4: the chip's own datasheet
requires `Calibrate` (PLL/AAF) after a frequency change > 50 MHz **or a temperature change
beyond ±20 °C**, and image calibration beyond 10 °C. A ground-to-float swing far exceeds
that, so firmware must re-calibrate on temperature. `GetTemp` (`0x0125`, runtime,
`Source(1:0)` selectable) provides the trigger. That is free and needs no new part.

---

## BOTTOM LINE

1. **Is it possible?** Per radio: **F33 — NO** (no clock pin; internal 0.5 ppm TCXO).
   **Bare NiceRF LoRa2021 — NO** (pad 13 is a VTCXO *output*; XTA is not broken out).
   **SX1280 — YES** (TCXO AC-coupled to **XTA, pin 4**, own rail). **ESP32-S3 — no main
   clock input** (irrelevant anyway). **MAX-M10S — already has a TCXO and gives 1PPS.**
2. **Does it make sense?** **An OCXO: NO — 3 400×–52 000× the 100 µW night anchor, 370×–
   5 600× short of surviving one night on 33 J, and structurally unable to be switched
   off.** **A TCXO: YES, where a radio actually needs one, because it can be duty-cycled.**
3. **Is the stability needed?** **Not for the link** — a plain ±20–30 ppm crystal is
   inside LoRa tolerance at 433 MHz/BW125; the real risk is **time/phase**, already
   bounded by a ~14× margin and fixed by **GPS 1PPS discipline**.
4. **Recommend:** an **unheated TCXO on the clock input of whichever radio actually
   needs one** — i.e. **XTA (pin 4) on the SX1280**, on a gateable rail — and rely on the
   **F33's already-fitted internal TCXO** for the primary link, plus **GPS 1PPS
   discipline**. **Explicitly NOT a heater and NOT an OCXO.**

---

## Recommendation (concrete)

1. **Primary radio (433 TX / 2.4 RX): do nothing.** Fly the **F33-2G4**, whose internal
   0.5 ppm TCXO is already fitted, always-on, and needs no pin
   (`docs/f33-module/LoRa2021F33-2G4-datasheet-v1.1.pdf` §7). It is the cheapest possible
   answer: it exists.
2. **If a bare-crystal radio must be flown (SX1280 ranging path): an unheated TCXO on
   XTA (pin 4)**, AC-coupled per SX1280 datasheet §14.2/Figure 14-3, powered from **its own
   rail behind a GPIO-driven load switch** (no on-chip TCXO gate exists on the SX1280),
   so it is powered only in the radio's live window. Budget it with the LR2021-class
   figure: **`ILTCXO` 1.5–4 mA at 3.3 V = 4.9–13.2 mW while on, ≈50–130 µW averaged at
   1 % duty, 0 µW at night** — or use the LR2021 chip's own `SetTcxoMode` (`0x0120`,
   Table 6-65: tune 0x00–0x07 = 1.6–3.3 V) if the design returns to the bare chip with
   XTA exposed.
3. **Duty-cycling caveat on the LR2021 chip path**: `SetTcxoMode` *"only functions
   correctly when the chip is in Standby RC mode"* and *"a complete reset of the chip is
   required to return to normal XOSC operation"* — so on the LR2021 that provision is a
   **mode change, not a per-packet gate**. Where per-packet gating is wanted, gate the
   TCXO's **rail**, not the chip mode. (The F33's internal TCXO is always-on and needs
   neither.)
4. **Add GPS discipline, not an oscillator**: 1PPS from the MAX-M10S (`TIMEPULSE`, pin 4,
   30 ns RMS) into the phase computation already specified by ADR-017/019/021/023.
   **Zero grams, zero watts.**
5. **Do not fit a heater or an OCXO.** It duplicates ADR-042 §D1 and ADR-043's
   already-accepted rejection of board heating, fails on the 33 J / 100 µW budget, cannot
   be duty-cycled, and is unnecessary given Part C.

---

## TODO(unverified)

- `TODO(unverified)` — **SX1280 Figure 14-3 tip values** (AC-coupling cap, bias resistor)
  are not legible in the datasheet text layer; get the part-specific BOM from §14.2's
  pointer to the TCXO manufacturer.
- `TODO(unverified)` — **SX1280 TCXO frequency discrepancy**: Figure 14-3 labels the TCXO
  "32.0 MHz" while Table 3-9 gives `FXOSC` = **52 MHz**. Reconcile with Semtech before
  ordering.
- `TODO(unverified)` — **TCXO drive level into SX1280 XTA** (`ATCXO`-equivalent spec) is
  not stated in the SX1280 datasheet read here; the LR2021's own figure is
  `ATCXO` 0.4/0.6/1.2 Vpk-pk AC-coupled through 10 pF + 220 Ω (Table 3-25) and is **not**
  transferable to the SX1280.
- `TODO(unverified)` — **which reference the four owned bare NiceRF LoRa2021 modules
  actually carry** (crystal vs TCXO). Repo says crystal-only
  (`docs/LR2021-LESSONS-2026-09.md:22`, deshield-verified) while
  `docs/assets/lr2021/README.md:18` says "onboard TCXO". A deshield photo settles it.
- `TODO(unverified)` — **whether an SX1280 ban exists elsewhere**: the in-tree file
  `docs/adr/101-lr2021-only-ban-sx1280.md` has a ban filename but ADR-020 supersede
  content, so no operative ban text was found here.
- `TODO(unverified)` — **OCXO set-point temperatures** for both parts (needed to convert
  the 25 °C datasheet power to the cold figure). SiT5501 and OXD30 do not print a set
  point; the cold numbers in §B1 are therefore **estimates**, derived by scaling the
  documented 25 °C figure by ΔT at constant conductance.
- `TODO(unverified)` — **cold-end derating**: neither OCXO datasheet gives a
  below-25 °C current *table* (the SiT5501 gives `IDD` only as a typical-performance
  *plot*, Figures 22–27). The cold figures in §B1 are arithmetic, not datasheet values.
- `TODO(unverified)` — **`R_thermal` of the v9 enclosure**: the 100 K/W used in Method 2 is
  the ADR-042/043 estimate; a calibrated heater step test would replace it. Any value
  below ~10 K/W would materially change §B1 (and is implausible for an unsealed, small,
  still-air enclosure at stratospheric pressure).
- `TODO(unverified)` — **LoRa carrier-offset tolerance measured at the flight
  temperature** (−55 °C, outside the LR2021 crystal's characterised −20…+70 °C window,
  ADR-042 §A5) remains the gate named in ADR-042 §D5; it is not resolved here.
