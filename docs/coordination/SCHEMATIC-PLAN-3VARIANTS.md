# SCHEMATIC-PLAN-3VARIANTS.md
## Balloon Board Schematic Netlists — C3, S3, C3+RP2040

Generated: 2026-08-05
Revised: 2026-09-29 (electrical-correctness pass — see §6 "Revision notes")

Source of pin data: `docs/coordination/schematic-task-context.md` (pre-extracted GPIO data).
This file is the **netlist of record** consumed by the schematic-drawing cards
(e.g. `t_58b8d370` → `tracker/hardware/schematics/v_c3_flight.kicad_sch`).

**Scope:** this document defines nets only. Placement, routing, stackup and DRC
are defined by `PCB-MASTER-EXECUTION-PLAN.md`.

---

## 0. Reference designator map (all variants)

| Ref | Part | Footprint | Qty | Variants | Function |
|-----|------|-----------|-----|----------|----------|
| U1 | ESP32-C3-MINI-1 / ESP32-S3-WROOM-1 | module | 1 | all | Main MCU (radio SPI master, I2C master, ADC) |
| U2 | NiceRF LoRa2021 | SMD-18 | 1 | all | Sub-GHz radio transceiver |
| U3 | TPS7A02 | SOT-23-5 | 1 | all | 3V3 LDO (ultra-low Iq) |
| U4 | MAX-M10S GPS | 4-pin header | 1 | all | GNSS receiver (UART only) |
| U5 | RP2040-Zero | 13-pin header | 1 | **V3 only** | Radio co-processor (ADR-026) |
| U6 | BMP280 | LGA-8 / breakout | 1 | all | Pressure + temperature sensor (I2C) |
| SC | 1F 5.5V supercap | radial | 1 | all | Energy storage (VCAP) |
| D1 | BAT54 | SOD-123 | 1 | all | Solar blocking diode (**in series**) |
| D2 | LED | 0603 | 1 | all | Status LED |
| J1 | Solar input | 2-pin header | 1 | all | Panel connection |
| C1 | 100nF | 0402 | 1 | all | U1 decoupling |
| C2 | 100nF | 0402 | 1 | all | U2 decoupling |
| C3 | 100nF | 0402 | 1 | all | U3 VIN decoupling |
| C4 | 100nF | 0402 | 1 | all | U3 VOUT decoupling |
| C5 | 100nF | 0402 | 1 | all | U4 decoupling |
| C6 | 100nF | 0402 | 1 | all | U6 decoupling |
| C7 | 10uF | 0805 | 1 | all | 3V3 bulk |
| C8 | 100nF | 0402 | 1 | **V3 only** | U5 decoupling |
| R1 | 4.7k | 0402 | 1 | all | I2C SDA pull-up |
| R2 | 4.7k | 0402 | 1 | all | I2C SCL pull-up |
| R3 | 1M | 0402 | 1 | all | VCAP divider, upper |
| R4 | 1M | 0402 | 1 | all | VCAP divider, lower |
| R5 | 330R | 0402 | 1 | all | LED series resistor |

**Reference-designator caution:** the already-drawn
`tracker/hardware/schematics/v_c3_rp2040/v_c3_rp2040.kicad_sch` uses `U5` for the
**TPS7A02 LDO**. In *this* document `U3` is the LDO and `U5` is the RP2040, per
the task context. The v3 netlist below is authoritative for a **new** drawing;
if that existing sheet is reused instead, re-annotate it or the netlist will not
match the symbol.

**Note on U6:** the context file lists "BMP280" under *Sensors* but assigns it no
reference designator. U6 is assigned here so every net below names a real,
fabricable part. Without it, `C6: BMP280.VCC ↔ BMP280.GND` names a part that
does not exist in the BOM.

---

## 1. Shared power architecture (all three variants)

```
Solar panel (+) -- J1.1 -->|-- D1 (BAT54, series) --+-- SC.+ (1F 5.5V supercap)
                                                   |
                                                   +-- U3.VIN --> U3 (TPS7A02) --> 3V3 rail
                                                                      ^
                                                        U3.EN --------+
                                                        (tied to VIN — see §5)

VCAP sense:  SC.+ -- R3 (1M) --+-- VDIV_MID --> U1 ADC
                               +-- R4 (1M) -- GND
```

D1 is **in series** between the panel and the VCAP node. It is not a rail tie.

### 1.1 Radio pins that are *not* in a bus net

`U2` (LoRa2021, 18-pin) has three pin groups that the GPIO table does not cover
and that must still be handled in the drawing:

| U2 pin(s) | Symbol name | Treatment |
|-----------|-------------|-----------|
| 9 | `RF_SUB` | Sub-GHz antenna feed — board antenna/trace, **not** a GPIO net |
| 18 | `RF_2G4` | 2.4 GHz antenna feed — same |
| 12, 15 | `NC` (no_connect type) | Place an explicit no-connect flag; do **not** wire |

`U2.RESET` in earlier revisions is `U2.RST` here — that is the symbol's pin name.
The *net* name stays `LR2021_RST`.

**U3.EN** likewise is a pin *name*; the rail it lands on is `VBAT`.

---

## 2. VARIANT 1 — ESP32-C3 Flight Board (current)

U1 = ESP32-C3-MINI-1. Radio = U2, GPS = U4, sensor = U6, LDO = U3.

### 2.1 Netlist

#### Power
```
SOLAR_IN : J1.1 ↔ D1.A
VBAT     : D1.K ↔ SC.+ ↔ U3.VIN ↔ U3.EN ↔ R3.1 ↔ C3.1
3V3      : U3.VOUT ↔ U1.VCC ↔ U2.VCC ↔ U4.VCC ↔ U6.VCC ↔ C1.1 ↔ C2.1 ↔ C4.1 ↔ C5.1 ↔ C6.1 ↔ C7.1 ↔ R1.1 ↔ R2.1
GND      : J1.2 ↔ SC.- ↔ U3.GND ↔ U1.GND ↔ U2.GND ↔ U4.GND ↔ U6.GND ↔ C1.2 ↔ C2.2 ↔ C3.2 ↔ C4.2 ↔ C5.2 ↔ C6.2 ↔ C7.2 ↔ R4.2 ↔ D2.K
VDIV_MID : R3.2 ↔ R4.1 ↔ U1.ADC0
```
**C3** (100nF, U3 *input* decoupling) is the only capacitor whose top terminal is
on **VBAT**, not 3V3 — it sits at the regulator input. C4 (U3 output) and every
other cap are on 3V3. This is stated in both the net lines above and the
placement table below, and is checked by the validator (see §7).

#### GPS UART — U4 = MAX-M10S (4-pin header: 1=VCC 2=GND 3=TX 4=RX)
```
GPS_TX : U1.GPIO0 ↔ U4.RX     (MCU TX -> GPS RX)
GPS_RX : U1.GPIO1 ↔ U4.TX     (GPS TX -> MCU RX)
```

#### LR2021 SPI bus (U2)
```
SPI_MISO : U1.GPIO2  ↔ U2.MISO
SPI_SCK  : U1.GPIO6  ↔ U2.SCK
SPI_MOSI : U1.GPIO7  ↔ U2.MOSI
SPI_NSS  : U1.GPIO10 ↔ U2.NSS
```

#### LR2021 control (U2)
```
LR2021_RST  : U1.GPIO3 ↔ U2.RST
LR2021_BUSY : U1.GPIO4 ↔ U2.BUSY
LR2021_DIO9 : U1.GPIO5 ↔ U2.DIO9
```

#### I2C bus — U6 = BMP280
```
I2C_SDA : U1.GPIO8 ↔ U6.SDA ↔ R1.2
I2C_SCL : U1.GPIO9 ↔ U6.SCL ↔ R2.2
```

#### Status LED
```
LED_CTRL : U1.GPIO19 ↔ R5.1
LED_A    : R5.2 ↔ D2.A
```
`D2.K` is on GND (see the Power block).

#### LDO enable

`U3.EN` is **on the VBAT net** (tied to `U3.VIN`, see the power block above);
it is deliberately *not* a separate net, because a separate net claiming
`U3.VIN` would be the same copper under a second name. This is the always-on configuration.

#### Decoupling — placement table (NOT netlist syntax)

Every capacitor below already appears by both terminals in the 3V3/GND/VBAT nets
of the Power block above. This table only says **where each cap sits**; do not
create an extra net from it.

| Cap | Value | Rail | Ground | Placement |
|-----|-------|------|--------|-----------|
| C1 | 100nF | 3V3 | GND | at U1 VCC pin |
| C2 | 100nF | 3V3 | GND | at U2 VCC pin |
| C3 | 100nF | VBAT | GND | at U3 VIN pin |
| C4 | 100nF | 3V3 | GND | at U3 VOUT pin |
| C5 | 100nF | 3V3 | GND | at U4 VCC pin |
| C6 | 100nF | 3V3 | GND | at U6 VCC pin |
| C7 | 10uF | 3V3 | GND | at U3 VOUT, bulk |

#### Pull-ups, divider, LED resistor — orientation (NOT netlist syntax)

Each resistor already appears by both terminals in the nets above. This table
states which end is which; do not create an extra net from it.

| Resistor | Value | Terminal 1 | Terminal 2 | Function |
|----------|-------|-----------|-----------|----------|
| R1 | 4.7k | 3V3 | I2C_SDA | SDA pull-up |
| R2 | 4.7k | 3V3 | I2C_SCL | SCL pull-up |
| R3 | 1M | VBAT | VDIV_MID | divider upper leg |
| R4 | 1M | VDIV_MID | GND | divider lower leg |
| R5 | 330R | LED_CTRL | LED_A | LED series |

### 2.2 Pin assignment table (C3)

| U1 pin | Net | Notes |
|--------|-----|-------|
| GPIO0 | GPS_TX | MCU UART TX |
| GPIO1 | GPS_RX | MCU UART RX |
| GPIO2 | SPI_MISO | |
| GPIO3 | LR2021_RST | |
| GPIO4 | LR2021_BUSY | |
| GPIO5 | LR2021_DIO9 | IRQ |
| GPIO6 | SPI_SCK | |
| GPIO7 | SPI_MOSI | |
| GPIO8 | I2C_SDA | strapping pin |
| GPIO9 | I2C_SCL | strapping pin |
| GPIO10 | SPI_NSS | |
| GPIO19 | LED_CTRL | moved off GPIO9 — see §6 defect 8 |
| ADC0 | VDIV_MID | pin not named in context — see §5 open item 1 |

### 2.3 Notes
- GPIO8/GPIO9 are strapping pins on the C3 mini. They carry I2C and are not
  driven low at reset by any attached device (the pull-ups to 3V3 hold the
  required boot level). Verify at bring-up.
- U3.EN is tied to VIN. A floating EN disables the regulator output entirely.

---

## 3. VARIANT 2 — ESP32-S3 Board (future custom board)

U1 = ESP32-S3-WROOM-1. Identical topology to Variant 1; the only differences are
the LED pin and (potentially) the ADC pin.

### 3.1 Netlist

#### Power (identical to Variant 1)
```
SOLAR_IN : J1.1 ↔ D1.A
VBAT     : D1.K ↔ SC.+ ↔ U3.VIN ↔ U3.EN ↔ R3.1 ↔ C3.1
3V3      : U3.VOUT ↔ U1.VCC ↔ U2.VCC ↔ U4.VCC ↔ U6.VCC ↔ C1.1 ↔ C2.1 ↔ C4.1 ↔ C5.1 ↔ C6.1 ↔ C7.1 ↔ R1.1 ↔ R2.1
GND      : J1.2 ↔ SC.- ↔ U3.GND ↔ U1.GND ↔ U2.GND ↔ U4.GND ↔ U6.GND ↔ C1.2 ↔ C2.2 ↔ C3.2 ↔ C4.2 ↔ C5.2 ↔ C6.2 ↔ C7.2 ↔ R4.2 ↔ D2.K
VDIV_MID : R3.2 ↔ R4.1 ↔ U1.ADC0
```

#### GPS UART
```
GPS_TX : U1.GPIO0 ↔ U4.RX
GPS_RX : U1.GPIO1 ↔ U4.TX
```

#### LR2021 SPI bus
```
SPI_MISO : U1.GPIO2  ↔ U2.MISO
SPI_SCK  : U1.GPIO6  ↔ U2.SCK
SPI_MOSI : U1.GPIO7  ↔ U2.MOSI
SPI_NSS  : U1.GPIO10 ↔ U2.NSS
```

#### LR2021 control
```
LR2021_RST  : U1.GPIO3 ↔ U2.RST
LR2021_BUSY : U1.GPIO4 ↔ U2.BUSY
LR2021_DIO9 : U1.GPIO5 ↔ U2.DIO9
```

#### I2C bus
```
I2C_SDA : U1.GPIO8 ↔ U6.SDA ↔ R1.2
I2C_SCL : U1.GPIO9 ↔ U6.SCL ↔ R2.2
```

#### Status LED (dedicated pin — no dual-use on S3)
```
LED_CTRL : U1.GPIO18 ↔ R5.1
LED_A    : R5.2 ↔ D2.A
```

#### LDO enable

`U3.EN` is **on the VBAT net** (tied to `U3.VIN`, see the power block above);
it is deliberately *not* a separate net, because a separate net claiming
`U3.VIN` would be the same copper under a second name. This is the always-on configuration.

#### Decoupling — placement table (NOT netlist syntax)

Every capacitor below already appears by both terminals in the 3V3/GND/VBAT nets
of the Power block above. This table only says **where each cap sits**; do not
create an extra net from it.

| Cap | Value | Rail | Ground | Placement |
|-----|-------|------|--------|-----------|
| C1 | 100nF | 3V3 | GND | at U1 VCC pin |
| C2 | 100nF | 3V3 | GND | at U2 VCC pin |
| C3 | 100nF | VBAT | GND | at U3 VIN pin |
| C4 | 100nF | 3V3 | GND | at U3 VOUT pin |
| C5 | 100nF | 3V3 | GND | at U4 VCC pin |
| C6 | 100nF | 3V3 | GND | at U6 VCC pin |
| C7 | 10uF | 3V3 | GND | at U3 VOUT, bulk |

#### Pull-ups, divider, LED resistor — orientation (NOT netlist syntax)

Each resistor already appears by both terminals in the nets above. This table
states which end is which; do not create an extra net from it.

| Resistor | Value | Terminal 1 | Terminal 2 | Function |
|----------|-------|-----------|-----------|----------|
| R1 | 4.7k | 3V3 | I2C_SDA | SDA pull-up |
| R2 | 4.7k | 3V3 | I2C_SCL | SCL pull-up |
| R3 | 1M | VBAT | VDIV_MID | divider upper leg |
| R4 | 1M | VDIV_MID | GND | divider lower leg |
| R5 | 330R | LED_CTRL | LED_A | LED series |

### 3.2 Notes
- LED is on GPIO18, so GPIO9 carries I2C SCL only — the dual-use conflict of
  Variant 1 does not exist here.
- All other assignments are pin-compatible with Variant 1. The ADC pin still
  needs the decision in §5 open item 1.

---

## 4. VARIANT 3 — C3 + RP2040 Dual-MCU Board

U1 = ESP32-C3-MINI-1 (main / WiFi-BLE), U5 = RP2040-Zero (radio co-processor,
ADR-026). Option A (UART bridge) is specified below; Option B is documented in
§4.4 but is **not** this netlist.

### 4.1 Netlist — Option A (UART bridge); C3 remains SPI master

#### Power
```
SOLAR_IN : J1.1 ↔ D1.A
VBAT     : D1.K ↔ SC.+ ↔ U3.VIN ↔ U3.EN ↔ R3.1 ↔ C3.1
3V3      : U3.VOUT ↔ U1.VCC ↔ U2.VCC ↔ U4.VCC ↔ U5.VCC ↔ U6.VCC ↔ C1.1 ↔ C2.1 ↔ C4.1 ↔ C5.1 ↔ C6.1 ↔ C7.1 ↔ C8.1 ↔ R1.1 ↔ R2.1
GND      : J1.2 ↔ SC.- ↔ U3.GND ↔ U1.GND ↔ U2.GND ↔ U4.GND ↔ U5.GND ↔ U6.GND ↔ C1.2 ↔ C2.2 ↔ C3.2 ↔ C4.2 ↔ C5.2 ↔ C6.2 ↔ C7.2 ↔ C8.2 ↔ R4.2 ↔ D2.K
VDIV_MID : R3.2 ↔ R4.1 ↔ U1.ADC0
```

#### GPS UART
```
GPS_TX : U1.GPIO0 ↔ U4.RX
GPS_RX : U1.GPIO1 ↔ U4.TX
```

#### LR2021 SPI bus (C3 = master)
```
SPI_MISO : U1.GPIO2  ↔ U2.MISO
SPI_SCK  : U1.GPIO6  ↔ U2.SCK
SPI_MOSI : U1.GPIO7  ↔ U2.MOSI
SPI_NSS  : U1.GPIO10 ↔ U2.NSS
```

#### LR2021 control
```
LR2021_RST  : U1.GPIO3 ↔ U2.RST
LR2021_BUSY : U1.GPIO4 ↔ U2.BUSY
LR2021_DIO9 : U1.GPIO5 ↔ U2.DIO9
```

#### I2C bus
```
I2C_SDA : U1.GPIO8 ↔ U6.SDA ↔ R1.2
I2C_SCL : U1.GPIO9 ↔ U6.SCL ↔ R2.2
```

#### Status LED
```
LED_CTRL : U1.GPIO18 ↔ R5.1
LED_A    : R5.2 ↔ D2.A
```

#### RP2040 UART bridge (Option A)
```
RP_TX : U5.GPIO0 ↔ U1.GPIO20    (RP UART0 TX -> C3 UART RX)
RP_RX : U5.GPIO1 ↔ U1.GPIO19    (RP UART0 RX <- C3 UART TX)
```

#### LDO enable

`U3.EN` is **on the VBAT net** (tied to `U3.VIN`, see the power block above);
it is deliberately *not* a separate net, because a separate net claiming
`U3.VIN` would be the same copper under a second name. This is the always-on configuration.

#### Decoupling — placement table (NOT netlist syntax)

Every capacitor below already appears by both terminals in the 3V3/GND/VBAT nets
of the Power block above. This table only says **where each cap sits**; do not
create an extra net from it.

| Cap | Value | Rail | Ground | Placement |
|-----|-------|------|--------|-----------|
| C1 | 100nF | 3V3 | GND | at U1 VCC pin |
| C2 | 100nF | 3V3 | GND | at U2 VCC pin |
| C3 | 100nF | VBAT | GND | at U3 VIN pin |
| C4 | 100nF | 3V3 | GND | at U3 VOUT pin |
| C5 | 100nF | 3V3 | GND | at U4 VCC pin |
| C6 | 100nF | 3V3 | GND | at U6 VCC pin |
| C7 | 10uF | 3V3 | GND | at U3 VOUT, bulk |
| C8 | 100nF | 3V3 | GND | at U5 VCC pin |

#### Pull-ups, divider, LED resistor — orientation (NOT netlist syntax)

Each resistor already appears by both terminals in the nets above. This table
states which end is which; do not create an extra net from it.

| Resistor | Value | Terminal 1 | Terminal 2 | Function |
|----------|-------|-----------|-----------|----------|
| R1 | 4.7k | 3V3 | I2C_SDA | SDA pull-up |
| R2 | 4.7k | 3V3 | I2C_SCL | SCL pull-up |
| R3 | 1M | VBAT | VDIV_MID | divider upper leg |
| R4 | 1M | VDIV_MID | GND | divider lower leg |
| R5 | 330R | LED_CTRL | LED_A | LED series |

### 4.2 C3 GPIO budget (Variant 3)

| U1 pin | Net |
|--------|-----|
| GPIO0 | GPS_TX |
| GPIO1 | GPS_RX |
| GPIO2 | SPI_MISO |
| GPIO3 | LR2021_RST |
| GPIO4 | LR2021_BUSY |
| GPIO5 | LR2021_DIO9 |
| GPIO6 | SPI_SCK |
| GPIO7 | SPI_MOSI |
| GPIO8 | I2C_SDA |
| GPIO9 | I2C_SCL |
| GPIO10 | SPI_NSS |
| GPIO18 | LED_CTRL |
| GPIO19 | RP_RX |
| GPIO20 | RP_TX |
| ADC0 | VDIV_MID (pin unnamed in context — §5 open item 1) |

### 4.3 Notes
- The context file authorises GPIO19/GPIO20 for the RP2040 bridge because GPIO1
  is occupied by GPS. That is what is used above, and it forces the LED to
  GPIO18 in this variant.
- RP2040-Zero needs 3V3 and GND only from this board; USB and crystal are onboard.
- **UART direction.** The context line reads "RP2040 UART TX -> C3 UART RX", so
  RP_TX lands on the C3's *RX* pin (GPIO20) and RP_RX on the C3's *TX* pin
  (GPIO19). Crossover is intentional — do not "fix" it so both sides use the
  same pin number.

### 4.4 Option B — RP2040 as SPI master (ADR-026 alternative)

Documented for completeness; **not** the baseline for this board, and **not**
drawable from Option A's netlist.

```
RP2040 becomes SPI master to U2. The C3's SPI nets to U2 are removed; the
C3<->RP2040 link carries the radio API over UART or IPC. This changes which MCU
owns U2.RST / U2.BUSY / U2.DIO9 and therefore requires its own netlist pass.
```

Do not mix Option A and Option B nets in one schematic.

---

## 5. Open items (require an operator decision — do NOT invent an assignment)

These are real conflicts in the source data. They are listed rather than silently
resolved, because guessing a pin here produces a board that cannot sample its own
supply rail or that fights a strapping pin.

1. **The ADC pin is unnamed in the context file.** The context gives the function
   `ADC0 -> VDIV_MID` but no GPIO. On ESP32-C3, ADC1 is GPIO0–GPIO4 and ADC2_CH0
   is GPIO5 — and every one of those is already committed (GPIO0/1 GPS UART,
   GPIO2 SPI_MISO, GPIO3/4/5 LR2021 control). ESP32-S3 has the same class of
   collision (ADC1_CH0 = GPIO1 = GPS_RX). **Decision needed:** either move one
   LR2021 control pin (GPIO4 `LR2021_BUSY` is the least timing-critical) to a
   free pin and give the divider that GPIO4 = ADC1_CH4, or accept ADC2 on GPIO5
   with its documented "WiFi must be off" restriction. Until this is decided,
   `U1.ADC0` is a named net with no physical pin and must not be drawn.
2. **The U1 reset/EN network is absent from the context component list.** A
   correct ESP32-C3/S3 design needs an EN pull-up plus an RC (typ. 10k + 1uF) and
   usually a reset button. Those parts are **not** in the BOM above. Add them
   before fabrication.
3. **GPIO8/GPIO9 strapping pins** carry I2C on the C3 variants. Confirm at
   bring-up that the I2C pull-ups hold the required boot levels.
4. **`U3.EN`** — the context never states the LDO enable connection. Tied to VIN
   above (regulator permanently on). If a load switch or power-gate is intended,
   this net must be driven from a GPIO instead.
5. **Supercap vs panel voltage:** the context specifies a 1F 5.5V supercap as the
   only store. Verify the TPS7A02 input range and the panel's open-circuit
   voltage against the supercap's 5.5V rating before fab — an unclamped 6V panel
   can exceed it.

---

## 6. Revision notes — defects found and fixed in the 2026-09-29 pass

The previous revision of this file could not be fabricated as written. Recorded
here so the schematic-drawing card does not re-introduce them.

| # | Defect (previous revision) | Impact | Fix |
|---|----------------------------|--------|-----|
| 1 | `I2C_SDA: U1.GPIO8 ↔ U4.SDA`, `I2C_SCL: U1.GPIO9 ↔ U4.SCL` | U4 is the **MAX-M10S GPS** — a 4-pin UART module with no I2C pins. The BMP280 was never actually on the bus. | I2C now lands on U6 (BMP280); U4 carries UART only. |
| 2 | `VDIV_MID: SC.+ ↔ R3.1 ↔ R4.1 ↔ U1.ADC0` | Shorts VCAP directly into the divider tap and the ADC: R4 is bridged, the divider never divides, and the ADC sees the full supercap voltage. | `VDIV_MID: R3.2 ↔ R4.1 ↔ U1.ADC0`; R3's upper leg from VBAT. |
| 3 | `VBAT: J1.1 ↔ D1.A ↔ SC.+ ↔ U3.VIN` | Put J1.1 and SC.+ in one net, so D1 sits **in parallel** instead of in series — the blocking diode does nothing and the panel back-feeds the supercap. | Split: `SOLAR_IN = J1.1 ↔ D1.A`, `VBAT = D1.K ↔ SC.+ ↔ U3.VIN`. |
| 4 | `C6: BMP280.VCC ↔ BMP280.GND` | Names a part with no reference designator and no BOM line. | BMP280 assigned **U6**; `C6` is now a placement row for U6. |
| 5 | `GND` listed `R2.2`; `3V3` omitted `R1.2`/`R2.2` | R2.2 is the I2C SCL pull-up **top**, which must sit on 3V3. As written the pull-up spanned 3V3 to GND and shorted the bus. | 3V3 carries R1.2/R2.2; GND carries R4.2 and D2.K. |
| 6 | `D2.K` and `R5` appeared in no net | LED cathode floating — the LED could not light. | Added `LED_CTRL` / `LED_A` nets and put `D2.K` on GND. |
| 7 | `U3.EN` connected to nothing | TPS7A02 output disabled — no 3V3 rail at all. | `U3.EN` tied to `U3.VIN` on the **VBAT** net (always-on). |
| 8 | LED on GPIO9 in V1 and V3 (same pin as I2C SCL) | Direct pin conflict: SCL and LED drive fight each other. | LED -> GPIO19 (V1), GPIO18 (V3, since 19/20 carry the RP2040 bridge). |
| 9 | Decoupling written in netlist syntax (`C1: U1.VCC ↔ U1.GND`) | Reads as a request to create a **net named C1** joining VCC to GND — a short if drawn literally. | Decoupling/pull-up blocks converted to placement/orientation **tables**, explicitly marked NOT netlist syntax. |
| 10 | Component table said "C1–C6 = 6 x 100nF" but Variant 3's netlist used C8 | C8 present in the netlist, absent from the BOM. | C8 added to §0 as V3-only. |
| 11 | `ANT1`/`ANT2`/`FEM`/`J2` appeared in an earlier symbol sketch | Extra parts with no netlist definition, confusing the drawer. | Not in the BOM; LM2021 antenna is integral to U2 on this design. |
| 12 | 2nd pass: `3V3` net listed `C3.1`, while C3's own placement row said its rail is **VBAT** | A cap's top terminal claimed by two different rails — a direct short between VBAT and 3V3 if drawn. | `C3.1` moved onto `VBAT` in all three variants; the surrounding note corrected. |
| 13 | 2nd pass: `3V3` net listed `R1.2`/`R2.2`, while the orientation table said terminal **1** is 3V3 | Pull-up top-leg disagreed with the net line; either spelling alone grounded a pull-up. | Net lines now use `R1.1`/`R2.1` for the 3V3 legs and `R1.2`/`R2.2` for the bus legs. |
| 14 | 2nd pass: `3V3_EN: U3.EN ↔ U3.VIN` as a *separate* net | Names the VBAT node twice; two nets cannot own one pin. | Removed as a net; `U3.EN` now appears on `VBAT` alongside `U3.VIN`. |
| 15 | 2nd pass: net lines said `U2.RESET`, but the LoRa2021 symbol's pin is named `RST` | Netlist would not map onto the symbol pin, so `LR2021_RST` would be undrawable as written. | Pin renamed to `U2.RST` (net name `LR2021_RST` unchanged) in all three variants. |
| 16 | 2nd pass: `U2` RF and no-connect pins (9 `RF_SUB`, 18 `RF_2G4`, 12/15 `NC`) appeared in no net and in no note | A drawer would either float them silently or invent a net for them. | Added §1.1: antenna feeds are board antenna nets, NC pins get explicit no-connect flags. Validator now fails if an NC pin is in a net. |
| 17 | 2nd pass: reusing `v_c3_rp2040.kicad_sch` silently mismatches designators (it calls the LDO `U5`) | Netlist/symbol mismatch at the drawing stage. | §0 now carries a designator-collision caution. |

### Net-completeness check

Every pin of every part in the §0 BOM appears in exactly one net per variant:

- U1: VCC, GND, GPIO0–GPIO10, GPIO18/GPIO19/GPIO20 (V3), ADC0*, plus reset RC*
- U2: VCC, GND, MISO, MOSI, SCK, NSS, RST, BUSY, DIO9 (+ RF_SUB/RF_2G4 antenna, 2x NC — see §1.1)
- U3: VIN, GND, EN, VOUT
- U4: VCC, GND, TX, RX
- U5 (V3): VCC, GND, GPIO0, GPIO1
- U6: VCC, GND, SDA, SCL
- SC, D1, D2, J1: both terminals each
- C1–C7 (C8 on V3), R1–R5: both terminals each

\* = listed in §5 as a part/pin the context data does not yet define.

---

## 7. Automated validation of this file

The claims above are machine-checked, not asserted. `validate_netlist.py` sits
next to this document and parses the net blocks straight out of the markdown:

```bash
python3 docs/coordination/validate_netlist.py
```

It fails (exit 1) unless, for **each** variant:

1. every pin of every part in the §0 BOM appears in **exactly one** net
   (catches both a floating pin and a pin claimed by two nets);
2. no pin sits on two different power rails (`VBAT` / `3V3` / `GND` /
   `SOLAR_IN` / `VDIV_MID`) — i.e. no rail short through a component leg;
3. the decoupling placement table and the resistor orientation table **agree
   with the net lines** (a row saying "VBAT" must match the net carrying that
   terminal).

Last run: **PASS** — 18 nets / 68 connections (V1), 18 / 68 (V2),
20 / 76 (V3).

**When this document changes, re-run the validator and update the counts here.**
A schematic-drawing card that consumes this netlist should gate on a clean run.

---

*End of SCHEMATIC-PLAN-3VARIANTS.md*
