# V9 D2b(b) — LoRa2021F33 + SX1280 pin plan

Renumbered from ADR-029 on 2026-10-07 to remove a duplicate number; content otherwise unchanged.

Status: proposed implementation baseline, pending schematic ERC and module-datasheet
review. This is the pin plan for **ESP32-S3-WROOM-1U-N8R8** (octal PSRAM),
LoRa2021F33-2G4, SX1280, MS5607-02BA03 and MAX-M10S. It supersedes the old
second-SPI sketch that used IO35/IO36/IO37.

> **REVISED 2026-10-07 — see “Revision R1” at the end of this file.**
> Revision R1 is the landable pin plan of record: it assigns every pin that the v9
> schematic's `OPEN-1..OPEN-14` register left dangling, names the part and the
> reset-RC values still owed for the console, and records what stays open. It
> **supersedes two rows of the table under “Pin assignment” below** — `GPIO 11
> F33_DIO5` and `GPIO 12 F33_CE` — both of which this record's own prose and the
> generated sheet already contradict (R1.1). Where this record and R1 differ, R1
> is the pin plan of record; nothing else above is edited.

## Electrical constraints

The N8R8 module reserves IO35, IO36 and IO37 for octal PSRAM. They are not
available as board GPIOs and must not appear on either radio bus. IO39--IO42
are the native JTAG pins; this plan spends them on SX1280 control and therefore
requires USB-Serial-JTAG (IO19/IO20) or an external debug strategy. IO0, IO3,
IO45 and IO46 are boot strapping pins and are deliberately not assigned below.
All signals are 3.3 V logic; the F33 CE input is tied to 3V3 locally as required
by the module, not treated as an ESP32 output.

## Pin assignment

| ESP32-S3 GPIO | Net / function | Device | Direction / notes |
|---:|---|---|---|
| 4 | F33_SCK / SPI2 FSPI clock | LoRa2021F33 | output |
| 5 | F33_MOSI / SPI2 FSPI MOSI | LoRa2021F33 | output |
| 6 | F33_MISO / SPI2 FSPI MISO | LoRa2021F33 | input |
| 7 | F33_CS_N | LoRa2021F33 | output, idle high |
| 8 | F33_BUSY | LoRa2021F33 | input |
| 9 | F33_IRQ / DIO1 | LoRa2021F33 | input, interrupt |
| 10 | F33_RESET_N | LoRa2021F33 | output, assert low |
| 11 | F33_DIO5 | LoRa2021F33 | input, interrupt/status |
| 12 | F33_CE | LoRa2021F33 | **do not drive from firmware; strap to 3V3** |
| 14 | SX1280_SCK / SPI3 clock | SX1280 | output |
| 15 | SX1280_MOSI / SPI3 MOSI | SX1280 | output |
| 16 | SX1280_MISO / SPI3 MISO | SX1280 | input |
| 17 | SX1280_CS_N | SX1280 | output, idle high |
| 18 | SX1280_DIO2 | SX1280 | input; optional DIO2 function |
| 21 | GNSS_PPS | MAX-M10S | input, timestamp interrupt |
| 38 | SX1280_BUSY | SX1280 | input |
| 39 | SX1280_RESET_N | SX1280 | output, assert low; native MTCK/JTAG lost |
| 40 | SX1280_DIO1 / IRQ | SX1280 | input, interrupt; native MTDO/JTAG lost |
| 41 | SX1280_DIO3 | SX1280 | input/optional; native MTDI/JTAG lost |
| 42 | SX1280_ANT_SW / reserved control | SX1280 FEM/network | output only if fitted; native MTMS/JTAG lost |
| 43 (RXD0) | GPS_TX → S3_RX | MAX-M10S | UART0 RX; shared with console only by explicit mux policy |
| 44 (TXD0) | GPS_RX ← S3_TX | MAX-M10S | UART0 TX; shared with console only by explicit mux policy |
| 1 | I2C_SDA | MS5607-02BA03 | open-drain, external pull-up to 3V3 |
| 2 | I2C_SCL | MS5607-02BA03 | open-drain, external pull-up to 3V3 |
| 19 | USB_D- / console | ESP32-S3 | USB-Serial-JTAG, no external radio use |
| 20 | USB_D+ / console | ESP32-S3 | USB-Serial-JTAG, no external radio use |

`GPIO 11` and `GPIO 12` are superseded by Revision R1 (see R1.1); the rows are left
in place so the history stays legible. There is deliberately **no** row for `GPIO 13`,
which ADR-047 §6 spent on the F33 rail monitor — R1 records it.

SPI2/FSPI and SPI3 are separate ESP-IDF hosts with independent chip selects;
there is no shared radio bus. The exact F33 DIO names are schematic aliases:
map them to the F33 vendor pad names during symbol capture, and do not silently
swap IRQ/BUSY/RESET. SX1280 DIO2/DIO3/ANT_SW are included so a populated
front-end switch does not require a board respin; if the chosen SX1280 module
lacks one of these pins, leave the corresponding test pad NC rather than
reassigning a strapping pin.

## Explicit strapping-pin audit

| Strap | Assignment in this plan | Handling |
|---|---|---|
| IO0 | none | Leave available for boot/download. No radio pull-up, pulldown, or CS. |
| IO3 | none | Leave available for boot strap. No sensor or radio connection. |
| IO45 | none | Leave at module/vendor-required strap level; no external load. |
| IO46 | none | Leave at module/vendor-required strap level; no external load. |

**No strapping pins are touched.** IO35--IO37 are also intentionally unused
because they are octal-PSRAM connections, not spare GPIO. IO39--IO42 are not
straps, but the assignment consumes the native JTAG function; this is an
accepted, explicit debug trade-off, not an accidental conflict.

## Blockers and schematic gates

1. **No pin-plan blocker remains for the four requested strap pins or PSRAM
   pins.** The old IO35/36/37 SPI1 proposal is forbidden.
2. **JTAG conflict is explicit:** if production firmware requires native
   JTAG, this plan is blocked and SX1280 control signals must move to a
   revised GPIO allocation before schematic capture. USB-Serial-JTAG is the
   assumed debug path for this baseline.
3. Confirm the F33 vendor pad names and CE electrical requirement against the
   exact purchased revision before symbol release. CE must be a fixed 3V3 net;
   it must not be a floating MCU-controlled signal.
4. Confirm the selected SX1280 board's DIO2/DIO3/antenna-switch requirements.
   Do not populate an antenna switch net unless the RF module schematic proves
   it exists.
5. GPS UART boot-console multiplexing must be resolved in firmware (GPS is the
   flight owner after boot); it is not a reason to move GPS onto IO0/IO3.

This plan covers both SPI buses, unique CS, radio IRQ/DIO, BUSY, RESET, F33 CE,
MS5607 I2C, MAX-M10S UART/PPS, USB console, and all requested strap conflicts.


---

## Revision R1 — 2026-10-07: the pin-plan revision that closes the v9 open-pin register

**Author:** worker (Hermes agent), branch `adr/pin-plan-revision`, base `github/main`
`94c3c4dac97b1820bd1bf7b074424be8b528a769`.
**Status:** implemented in the generator of record
(`tracker/hardware/schematics/flight_board/build_flight_sch.py`, `v9` target) and
proven with `kicad-cli sch erc`. This section is the pin plan of record.

### R1.0 What R1 is, and what it deliberately does not do

The v9 sheet's own register (`V9_TODO`, emitted as `OPEN-1..OPEN-32` notes on
`v9_flight.kicad_sch`) left **19 pins** as `pin_not_connected` ERC errors, and its
own text said of the majority of them: *“OWNER: the ADR-108 pin-plan revision.”*
R1 is that revision. It assigns them.

Constraints honoured, stated so the reader can check them:

* **The radio band split is untouched** (ADR-034 D1: TX 433 MHz, RX 2.4 GHz).
* **No part was added or moved.** R1 changes *connectivity, nets and the register*;
  every component, footprint and placement on the sheet is the one that was already
  there. Consequently the console cluster (R1.7) stays open — a connector has to be
  fitted before it can be netted — and the parts it needs are named there instead.
* **No ERC severity was touched and no error was silenced.** Every closure below is
  either a real net or a `no_connect` with a source; the count fell because pins were
  decided, not because checks were turned off.
  * Nothing was ordered.

### R1.1 Two rows of the table above are superseded

| original row | why it is superseded | R1 disposition |
|---|---|---|
| `GPIO 11 — F33_DIO5` | The F33 module has **no DIO5 pad**: the G-NiceRF Rev 1.1 §7 table enumerates all 18 pads (1 VCC / 2,3,4,6,7,8,11 GND / 5 CE / 9 ANT / 10 ANT-2G4 / 12 SCK / 13 NSS / 14 BUSY / 15 MOSI / 16 MISO / 17 RESET / 18 IRQ), and `docs/F33-MODULE-PLAN.md` states “No DIO7/DIO8/DIO9 pins — only IRQ (Pin 18) as digital interface”. `OPEN-6` had already reduced it to a no-connect. | **IO11 is re-spent** on the bare module's `IRQ/DIO9` (R1.4). |
| `GPIO 12 — F33_CE` | This record's own “Electrical constraints” says CE *“is tied to 3V3 locally as required by the module, **not treated as an ESP32 output**”*, and the sheet ties `U2` pin 5 to `+3V3`. The table row is a leftover of the pre-D2 sketch. | **IO12 is re-spent** on the bare module's chip select (R1.4). |

R1 also records `GPIO 13`, which the table above omits: ADR-047 §6 puts the F33
rail-monitor divider tap on it (`F33_VSENSE` → `U1` pin 21 = IO13). Its ADC channel
number is still `OPEN-17`.

### R1.2 The revised assignment — every pin R1 settles

*“Citation” is the authority, not a restatement: a datasheet table, an ADR decision,
or an in-repo document.*

| Pin | Assignment | The constraint that decided it | Citation |
|---|---|---|---|
| `U4.1` VDD_IN | `+3V3` | The SX1280's supply is the existing 3.3 V logic rail; no new or gated rail is created for it (the default provision is no TCXO, no gate). | ADR-047 §2.3 (*“the 3.3 V rail — which also carries the ESP32-S3, the **SX1280** and the GNSS”*); `docs/POWER-BUDGET-V9-D2BE.md` §2 (both SX1280 states, ranging TX 70 mA and ranging RX 15 mA, are 3.3 V rows); ADR-060 §4/§8.5 |
| `U4.2` VDD_IO | `+3V3` | Same rail as VDD_IN — the part is a 3.3 V logic part on this board and the MCU/SX1280 SPI is 3.3 V. | same as above; ADR-108 “Electrical constraints” (*“All signals are 3.3 V logic”*) |
| `U4.14` RFIO | `ANT2_2G4_RANGE` (the `ANT2` U.FL, re-pointed) | Four U.FL sites, four RF parts; the F33's own 2.4 GHz port is the only feed with no role, because the F33 carries TX only. | ADR-034 D1/D5; ADR-029 D2b/D3; ADR-035; ADR-009. Full argument in **R1.3** |
| `U2.10` ANT-2G4 | **no-connect** | Consequence of R1.3: with the F33 TX-only, this port has no destination and no matching network is fitted either. | ADR-034 D5; ADR-029 D8 item 2 (“DNP pads, **not open stubs**”) |
| `U3.6` NSS | `U3_CS_N` → `U1.20` = **IO12** | A second slave on SPI2 needs its own chip select; IO12 is free because the F33 `CE` is a 3V3 strap (R1.1). | ADR-040 D2; `docs/V9-RADIO-SITE-MATRIX.md` §3.1 (+4 GPIO: CS + BUSY + RESET + IRQ, shared SPI data/clock) |
| `U3.7` BUSY | `U3_BUSY` → `U1.24` = **IO47** | The arbiter polls BUSY by GPIO, without driver cooperation. | ADR-029 D4 R3; matrix §3.1 |
| `U3.14` RESET | `U3_RESET_N` → `U1.25` = **IO48** | The second radio needs its own reset; it must not share the F33's. | matrix §3.1; ADR-040 D2 |
| `U3.15` IRQ/DIO9 | `U3_IRQ` → `U1.19` = **IO11** | The second radio needs its own interrupt; IO11 is free because the F33 has no DIO5 pad. | ADR-029 D4 (arbiter); matrix §3.1; OPEN-6 (the F33 has no DIO5 pad) |
| `U3.9` ANT (sub-GHz) | **no-connect** | The 433 MHz TX role sits on the Site-A module in every documented population, so the Site-B module's sub-GHz port has no destination. | ADR-034 D1; ADR-040 D1/D2; matrix §3.3/§3.4. Full argument in **R1.5** |
| `U3.16` DIO8 | **no-connect** | The LR2021 DIO5–8 are the RF **front-end** control lines, and this module has no front end. | `docs/LR2021-LESSONS-2026-09.md` (DIO5–8 drive the on-module front end); `docs/F33-MODULE-PLAN.md` (the bare NiceRF LoRa2021 is chip-only, “needs external SKY66112 FEM for 2.4 GHz PA”); ADR-034 D1 item 2 (the airborne 2.4 GHz RX is deliberately unamplified) |
| `U3.17` DIO7 | **no-connect** | Same constraint as `U3.16`; the vendor table names it, nothing needs it. | vendor pin table §7 (`docs/assets/lr2021/LoRa2021-Module-Datasheet-V1.3.pdf`); as `U3.16` |
| `U5.15` VIO_SEL | **no-connect** (“leave open”) | The GNSS I/O supply `U5.7` (V_IO) is `+3V3`, so the 3.3 V I/O range must be selected — and that range is selected by leaving the pin **open**. Tying it low would select 1.8 V I/O and put 3.3 V on a pin whose absolute maximum is then 1.98 V. | u-blox **MAX-M10S datasheet `UBX-20035208-R08` Table 10**, pin 15: *“Connect to GND for 1.8 V supply, or leave open for 3.3 V supply”*; Table 12 (abs. max) |
| `U5.18` SAFEBOOT_N | **no-connect** (“leave open”) | Safeboot is a recovery mode; the flight receiver runs in continuous mode and the pin has its own internal pull-up. | `UBX-20035208-R08` **Table 10**, pin 18: *“Safeboot mode (active low). **Leave open if not used.**”* (footnote 15: internally tied to TIMEPULSE through 1 kΩ; Table 12 gives its pull-up) |
| `U7.4` TPS7A02 pin 4 | **no-connect** | Pin 4 of the DBV (SOT-23-5) package is **NC on the part**. | TI **TPS7A02 datasheet `SBVS277C` Table 5-1** and Figure 5-2: pin 1 IN / 2 GND / 3 EN / **4 NC** (*“No connect pin. This pin is not internally connected. Connect to ground or leave floating.”*) / 5 OUT |
| `U1.11`…`U1.12`…`U1.47`…`U1.48` (`U1.19/20/24/25`) | see `U3.*` above | The +4 GPIO budget is spent, in full, on the second radio. | matrix §3.1; OPEN-14 |
| `U1.21` (IO13) | `F33_VSENSE` (already netted) | The rail monitor divider tap. | ADR-047 §6; OPEN-17 for the ADC channel number |

Other pins of these parts were already netted and are unchanged by R1.

### R1.3 The RF feed count — settled at FOUR (closes `OPEN-2`)

The conflict was real and is stated here rather than smoothed over:

* **ADR-029 D2b/D3** enumerates **four** connectors: GNSS L1, sub-GHz `ANT`, F33
  `ANT-2G4`, SX1280 — and its placement rule speaks of *“the two 2.4 GHz-capable
  feeds”*, i.e. the F33's 2.4 GHz port and the SX1280 are two **separate** feeds.
* **ADR-034 D1** then re-points the 2.4 GHz link **RX** at a separate bare
  `LoRa2021`, which also needs a feed — making **five** candidate feeds.
* Only **four** U.FL sites are drawn (`ANT1..ANT4`) and no part may be added.

Of the five candidates, exactly one has no role in the architecture of record:

> **ADR-034 D5: “ADR-029's D2b table listed the F33 carrying *both* link directions
> plus the SX1280 and MAX-M10S; this ADR re-points the RX direction at the bare
> module, so **the F33 carries TX only**.”**

So `ANT2` is re-pointed from the F33's `ANT-2G4` port to the **SX1280 RFIO**, and the
F33's 2.4 GHz port becomes an explicit no-connect. The result is one feed per RF part,
matching ADR-034 D5's four parts and the four drawn sites:

| Site | feed | source |
|---|---|---|
| `ANT1` | 433 MHz TX | `U2.9` (F33 sub-GHz) — ADR-034 D1/D2 |
| `ANT2` | 2.4 GHz **ranging** | `U4.14` (SX1280 RFIO) — ADR-029 D2b, ADR-035 |
| `ANT3` | 2.4 GHz link **RX** | `U3.10` (bare LoRa2021) — ADR-034 D1 |
| `ANT4` | GNSS L1 | `U5.11` (MAX-M10S `RF_IN`) — ADR-029 D3 |

Consistency with the standing antenna records:

* **ADR-029 D3's separation rule is preserved, not violated:** the two 2.4 GHz-capable
  feeds remain two separate feeds (`ANT2` ranging, `ANT3` link RX), on separate edges,
  never co-polarised within λ/2. They were **not** merged onto one connector — two RF
  ports on one feed would load each other's PA/LNA, which is the “open stub” failure
  ADR-029 D8 item 2 already prohibits in kind.
* **ADR-009** puts the antennas on the hub as wire dipoles, so a wing cut costs no
  comms; every feed here is a hub-side U.FL to a hub dipole and R1 changes none of that.
* **`{HP}` still works.** V9-RADIO-SITE-MATRIX §3.3 reads the F33's 2.4 GHz port as a
  *capability* of the part; the v9 **role assignment** is ADR-034 D5's TX-only. A future
  decision to fly the F33's 2.4 GHz port instead of the bare RX would be a change of
  ADR-034 D1 and is out of R1's scope (see R1.7).

**Not settled by R1, and stated so it is not read as settled:** the SX1280's RFIO **pad
number** (14) remains `TODO(unverified)` — no SX1280 datasheet is committed
(ADR-045 D1, `OPEN-13`). R1 **names the net**; it does not claim the pad number is
proven. The net is wired to the symbol pin the sheet already carries, and the symbol's
own Description still says `*** PIN NUMBERING AND LAND PATTERN NOT VERIFIED ***`.

### R1.4 The bare module's control lines and the GPIO budget (closes `OPEN-3` and `OPEN-14`)

`docs/V9-RADIO-SITE-MATRIX.md` §3.1 prices a second radio at **+4 GPIO**
(`CS + BUSY + RESET + IRQ/DIO`, sharing the SPI data/clock), because the S3's two
general SPI masters are already committed (SPI2 = F33, SPI3 = SX1280) and the `-N8R8`
part reserves IO35/36/37. R1 spends that budget on the four ESP32-S3 GPIOs that are
free once the constraints below are applied:

| excluded | why |
|---|---|
| IO0, IO3, IO45, IO46 | boot strapping pins — this plan leaves them unloaded (ADR-108 strapping audit) |
| IO35, IO36, IO37 | octal-PSRAM connections on the `-N8R8` part (ADR-029 D1.1) |
| IO19, IO20 | USB-Serial-JTAG console (R1.7) |
| IO11 | freed by `OPEN-6`: assigned to F33_DIO5 in the original table, but the F33 has no DIO5 pad (R1.1) |
| IO12 | freed by R1.1: assigned to F33`CE` in the original table, but CE is a 3V3 strap, not an MCU output |

That leaves exactly **IO11, IO12, IO47, IO48** — and they are the four lines:

```
U3.6  NSS        -> IO12   (U1.20)   U3_CS_N
U3.7  BUSY       -> IO47   (U1.24)   U3_BUSY
U3.14 RESET      -> IO48   (U1.25)   U3_RESET_N
U3.15 IRQ/DIO9   -> IO11   (U1.19)   U3_IRQ
```

This also disposes of `OPEN-14` (`U1.20 / U1.24 / U1.25 = IO12 / IO47 / IO48`): they
are **assigned**, not no-connects.

**The consequence is load-bearing and is recorded rather than discovered later:**
after R1 **no free ESP32-S3 GPIO remains** — every other pin is an assignment, a strap,
an octal-PSRAM pin or the USB console. `OPEN-25` (the per-wing cut-sense GPIO/divider,
ADR-051 §2.6) must therefore take the **one-GPIO-plus-mux / resistor-ladder** shape
ADR-051 §2.6 explicitly allows; four dedicated GPIOs are no longer available. `OPEN-25`
stays open for that choice and its divider values.

### R1.5 The justified no-connects

Every no-connect below is a `no_connect` on the sheet **with the source that says so** —
none is a reflex, and each is recorded in the sheet's `V9_NC` list with its reason:

| pin | no-connect because | citation |
|---|---|---|
| `U3.9` bare sub-GHz `ANT` | The `OPEN-4` warning was right that this port is *not unconditionally* unused — so the population case was decided instead of assumed. **ADR-034 D1** puts the 433 MHz **TX** on the Site-A module, and ADR-040 D1 records that Site A is the *nested* pad field, so a bare module fitted there reaches `ANT1` through the **shared pad 9**. Site B is the LP-only **2.4 GHz RX** site (ADR-040 D1/D2), and in `{HP}` Site B is DNP. In all four configurations of V9-RADIO-SITE-MATRIX §3.4 the TX role therefore sits on the Site-A module and this port has no destination. | ADR-034 D1; ADR-040 D1/D2; matrix §3.3/§3.4 |
| `U2.10` F33 `ANT-2G4` | See R1.3 — the F33 carries TX only. | ADR-034 D5 |
| `U3.16` DIO8, `U3.17` DIO7 | The module has no RF front end to control. | LR2021-LESSONS-2026-09; F33-MODULE-PLAN; ADR-034 D1 item 2 |
| `U5.15` VIO_SEL | Leave open to select 3.3 V I/O. | MAX-M10S `UBX-20035208-R08` Table 10 |
| `U5.18` SAFEBOOT_N | Leave open if not used. | MAX-M10S `UBX-20035208-R08` Table 10 |
| `U7.4` TPS7A02 pin 4 | Pin 4 of DBV/SOT-23-5 is NC on the part. | TPS7A02 `SBVS277C` Table 5-1 |

**The `U7.4` contradiction is resolved from the datasheet, and the frozen boards are NOT
followed.** The sheet's own symbol called pin 4 `NC` while the frozen boards disagreed
with each other: `v8i_krt_gnss`, `v8j_krt_ms5611`, `v8b_krt_routed`,
`v8c_krt_routed_margin` and `v8f_krt_margin_escaped` tie SOT-23-5 pad 4 to `+3V3`, while
`v8_krt_routed` leaves pads 3 and 5 netless and `hub_board_v1_clean` puts `3V3` on
**pad 5**. The datasheet settles it in favour of the sheet's label: pad 4 is NC, and pad
5 is OUT — the tie-off is **not adopted from a contradiction**, and the correct reading
is corroborated independently by `hub_board_v1_clean`'s pad map. (Tying an
internally-unconnected pad to the rail is harmless, which is why five boards got away
with it — but it is not what the part asks for, so R1 records it as NC.)

**The MAX-M10S ties were obtained from the datasheet, not inferred.** `OPEN-8` recorded
that the frozen `v8i_krt_gnss` board leaves pads 15 and 18 un-netted, and called that
“the precedent records the gap rather than deciding it”. With the datasheet in hand the
netless state turns out to be the **prescribed** one — both pins are specified to be
left open — so the v8i evidence is confirmed as a *decision* rather than promoted to a
tie-off. `V_BCKP`/`VCC_IO`/`~RESET` (pads 6/7/9) were already on `+3V3` from that same
board precedent and are unchanged.

### R1.6 The SX1280 supply (closes `OPEN-1`) — and the provision it does not close

`OPEN-1` recorded a conflict between ADR-047 (which states the 3.3 V rail also carries
the SX1280) and ADR-060 §5/§8.5 (which re-files the SX1280's supply as unfixed). R1
resolves it from the two landed records that actually fix a rail:

* **ADR-047 §2.3**, verbatim: *“the 3.3 V rail — which also carries the ESP32-S3, the
  **SX1280** and the GNSS”*.
* **`docs/POWER-BUDGET-V9-D2BE.md` §2** budgets **both** SX1280 states on the 3.3 V rail
  (ranging TX 70 mA, ranging RX 15 mA).
* **ADR-060 §4** decides the default SX1280 provision is *“no TCXO … and gate **no**
  rail”*, with option (a) held as a reserved **amendment** if a bench test flips it.

So `U4.1` and `U4.2` are on `+3V3`. **What R1 does not do** is fit the decoupling
provision ADR-029 §2(f) mandates (*“each radio rail gets its own ferrite + bulk cap from
3V3”*): the pin assignment is closed, but no dedicated ferrite/bulk part exists for this
rail on the sheet and R1 adds no part. That is registered as a **new** open item,
`OPEN-33`, rather than left silent.

### R1.7 Still open after R1 — with owners

| item | pins | why it stays open | owner |
|---|---|---|---|
| `OPEN-10` (updated) | `U1.3` EN, `U1.13` USB_D-, `U1.14` USB_D+ | The ESP32-S3 console is USB-Serial-JTAG and has **no fitted connector**, and the reset RC is not in the BOM. R1 **names both**, so the gap is a *fitting* task, not a decision: connector = the 6-pin 2.54 mm programming header the frozen `v8i` board already uses as `J1` “Prog_Header” — footprint/part id `Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical` (already in the generator's `PART_MAP` as `Connector_Generic:Conn_01x06`), wired 1 GND / 2 +3V3 / 3 EN / 4 USB_D- / 5 USB_D+ / 6 IO0; reset RC = **R = 10 kΩ, C = 1 µF** — Espressif **ESP32-S3-WROOM-1 & WROOM-1U datasheet v1.8 §9 (Peripheral Schematics, p. 41)**: *“it is advised to add an RC delay circuit at the EN pin. The recommended setting for the RC delay circuit is usually R = 10 kΩ and C = 1 µF.”* | the pass that adds the console connector to the BOM (this revision adds no part) |
| `OPEN-13` | `U4` SX1280 pad numbering | No Semtech SX1280 datasheet is committed; **every** SX1280 pad number remains `TODO(unverified)`. R1's `U4.14`/`U4.1`/`U4.2` are symbol pins, not proven orderings. | a worker with the Semtech datasheet (ADR-045 D1) |
| `OPEN-33` (**new**) | `U4.1`/`U4.2` rail *provision* | ADR-029 §2(f) requires this radio rail to have its own ferrite + bulk cap; none is fitted. | the same BOM/placement pass as `OPEN-10` |
| `OPEN-25` (consequence added) | `CUT_SENSE_W1..4` | The +4 GPIO budget is now fully spent (R1.4), so four dedicated sense GPIOs are impossible; a mux/ladder is the only shape left. The choice and the divider values remain open. | ADR-051 §2.6 follow-up |
| `OPEN-17` | `U1.21` = IO13 | The monitor pin is assigned (ADR-047 §6); the ADC **channel number** and the required source impedance are still not in the repo. | ADR-047 §6.1 |

**Not reopened, and out of scope of R1:** the band split (ADR-034 D1) and therefore the
choice of which part owns the 2.4 GHz link RX (`{HP}`'s use of the F33's port would be a
change to ADR-034 D1, not a pin-plan edit); ADR-029 D8's selectable pin-1 rail; ADR-060's
TCXO option (a).

### R1.8 Evidence

Measured on branch `adr/pin-plan-revision`, `v9` target, `kicad-cli` 9.0.8:

```
python3 build_flight_sch.py v9        # generator of record
kicad-cli sch erc --exit-code-violations -o v9_flight-erc.rpt v9_flight.kicad_sch
    before R1 : 19 violations, all [pin_not_connected], 0 warnings   (exit 5)
    after  R1 :  3 violations, all [pin_not_connected], 0 warnings   (exit 5)
```

The three that remain are exactly `U1.3`, `U1.13`, `U1.14` — `OPEN-10`, above. The
16 closed pins are `U4.1 U4.2 U4.14 U3.6 U3.7 U3.9 U3.14 U3.15 U3.16 U3.17 U5.15
U5.18 U7.4 U1.20 U1.24 U1.25`; the ERC before/after set-difference contains **no new
error** (the `comm -13` side is empty), and the only pin the change retires from the
`V9_NC` list is `U1.19`, which R1 spends on `U3_IRQ` instead.

`v9_flight.kicad_sch` is byte-identical across two consecutive generator runs
(sha256 `ab3516fc34b4cce704631572ccd47bae871b3264e67cc974ccbfd650ee33ed1c`), and
`check_sch_gates.py v9` passes (its GATE-1 ERC counts are *reported*, not suppressed —
passing the gate is a weaker claim than the ERC numbers above, and the numbers above are
the claim). `docs/v9-BOM.md` and `docs/v9-system-diagram.svg` were regenerated from the
same netlist; the diagram passes `scripts/check_v9_diagram_layout.py`.
