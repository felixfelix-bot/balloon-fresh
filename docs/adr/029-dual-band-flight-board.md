# ADR-029 — v9 tri-band flight board (ESP32-S3-WROOM-1U + LoRa2021F33-2G4 + SX1280 + MAX-M10S)

- Status: **Proposed** — the *design direction* this ADR records was ratified by the
  operator on 2026-10-04; the *text* has not been accepted by a human, so it does not
  say Accepted. One item is left open for the operator (O5, the 5 V rail) and one
  form-factor question is recorded rather than decided (O0).
- **Amended 2026-10-05 (operator decision, see D2b):** the SX1280 is **retained** for
  ranging and the MAX-M10S is confirmed. The board is therefore **tri-band with four RF
  parts**, and D2's single-module substitution is narrowed — read D2 together with D2b,
  and disregard the sections D2b marks superseded.
- Date: 2026-10-05
- Decision owner: Felix (operator)
- Author: worker-pcb (Hermes agent), promoting the manager's coexistence memo
  `docs/COEXISTENCE-V9.md` (2026-10-04, operator-approved design direction) into a decision
  record. The memo is committed alongside this ADR so the promotion is auditable; where this
  ADR departs from it, the departure is stated in the section below.
- Related: ADR-030 (deterministic zero-inference PCB placement/routing, pending),
  ADR-031 (board bring-up isolation + staged population), ADR-032 (simulation evidence:
  LTspice + openEMS + stackup impedance), ADR-028 (three-variant PCB design),
  ADR-015 (three-board hardware strategy), ADR-025 (shared-hardware flock mutex),
  ADR-022 (mandatory test coverage).
- **Superseded in part by ADR-034 (433 MHz TX / 2.4 GHz RX on two chips) and ADR-035 (TDM radio schedule).**
- Related artefacts in this repo:
  `docs/COEXISTENCE-V9.md` (the source memo, committed here so this ADR is auditable),
  `docs/f33-module/LoRa2021F33-2G4-datasheet-v1.1.pdf` (G-NiceRF, Rev 1.1),
  `docs/f33-module/materials/LORA2021F33-2G4 footprint_pads.pcb` (vendor pad file),
  `docs/F33-MODULE-PLAN.md`, `tracker/hardware/footprints/nicerf-lora2021f33-2g4.json`,
  `tracker/hardware/hub_board_diy/custom.pretty/LoRa2021F33_2G4.kicad_mod`,
  `tracker/hardware/jlcpcb-s1-frozen.kicad_dru` (the frozen campaign rule set).

> Numbering note: `docs/adr/029-firmware-output-harmonization.md` exists on the **unmerged**
> branch `feat/e80-spi-bypass` and is **not on `main`**. Two documents may therefore claim
> 029 at merge time. This file keeps 029 because ADR-031 and ADR-032 — committed on the PCB
> line (`adr/031-032-simulation-testability`, commit `0565621`, which is this branch's base,
> **not yet merged to `main`**) — explicitly reserve 029 for the card this ADR answers. The
> collision is flagged for the manager, not resolved here.

---

## Context

v8h is the current fab-ready flight board: 55.15 x 45.15 mm, 4 copper layers, DRC-clean
under `jlcpcb-s1-frozen.kicad_dru`, ordered through JLCPCB (bare-PCB ladder confirmed
2026-10-05). It carries a single sub-GHz radio.

v9 is the first board that must fly **four RF systems plus a Wi-Fi/BLE host on one
55 x 45 mm board**: a long-range sub-GHz telemetry link, a 2.4 GHz link radio, a
**dedicated 2.4 GHz ranging radio (SX1280, see D2b)**, GNSS L1 for position and time, and
the ESP32-S3's own Wi-Fi/BT for configuration when the radios are idle.
They are not near each other in frequency, and the GNSS receiver is
60–75 dB weaker than everything else. Those two facts drive every decision below, and they
are why the mechanical/electrical separation plan has to be a *decision*, not a layout
habit that each schematic re-litigates.

The operator's standing rule for this project is **ADR first**: no schematic, placement or
routing work starts before this record lands. This ADR is therefore the gate for the v9
schematic card, and it is deliberately opinionated about the things a layout would
otherwise have to guess.

### What this ADR changes relative to the source memo (stated, not silent)

The memo was written against a **two-radio** plan: NiceRF LoRa2021 (868 MHz) **plus** a
separate SX1280 (2.4 GHz). While reconciling the v9 BOM, the module that was already in
the repo — `LoRa2021F33-2G4`, chip = SEMTECH **LR2021** — was verified against its vendor
datasheet to cover **both** bands with independent 50 Ω ports (pin 9 `ANT` sub-GHz,
pin 10 `ANT-2G4`), with a built-in PA, a 0.5 ppm TCXO, FLRC up to 2.6 Mbps and RTToF
ranging. On that basis the manager recorded the collapse of the two radios into one
module, and the operator's decision list of 2026-10-05 (item 4, recorded on the JLCPCB
BOM/CPL card `t_3b823ea8`) states verbatim that "our module is G-NiceRF
**LoRa2021F33-2G4** (built on SEMTECH LR2021)" — confirmed from the vendor datasheet
title page in-repo — and that the LCSC/JLC listing `LoRa1121F33-2G4-868MHz` is a
*different* module on the LR1121 chip which must not be ordered.

Consequences of that, all recorded below as decisions rather than left implicit:

1. v9 is **ESP32-S3-WROOM-1U + LoRa2021F33-2G4 + SX1280 + MAX-M10S** (four RF parts).
   *(Superseded 2026-10-05 — this item originally read "three RF parts"; see D2b.)*
2. ~~The SX1280 disappears from v9. The 2.4 GHz role is served by the module's own port.~~
   **Superseded 2026-10-05 by D2b: the SX1280 is retained for ranging.** The F33's own
   port no longer serves the ranging role; it does not follow that it leaves the board.
3. The *symptom set* in the memo is unchanged in kind but worse in degree: the memo's
   assumed worst cases (LR2021 +22 dBm, SX1280 +13 dBm) are **stale**. The module delivers
   up to **+30 dBm (1 W) on both the 868 and the 2.4 GHz port at 5 V**, and the 2.4 GHz TX
   now shares a package with the 2.4 GHz RX.
4. The memo's second SPI column is **not physically available** on the part this ADR
   selects (see D1).
5. The earlier two-radio alternative remains a legitimate fallback; it is recorded as
   **D2-alt** with its full rationale and its deltas, so a rejection of the module
   substitution does not require re-deriving this document.

Nothing in the memo's *mechanism* analysis is discarded: each mechanism below carries over,
re-based on the module's two ports.

---

## Decision

### D1 — MCU: ESP32-S3-WROOM-1U (U.FL variant), 8 MB PSRAM (`ESP32-S3-WROOM-1U-N8R8`)

Rationale (in priority order, as they now apply to a single-module board):

1. **Pin budget.** The v9 board must carry the module's SPI (4) + `BUSY` + `RESET` +
   `IRQ` + `CE` + `DIO5` (9 lines), GNSS UART (2) + `PPS` (1), the boot/status lines, the
   supercap ADC divider, **and** the isolation links and test points ADR-031 D1/D2 now
   mandates at every subsystem boundary. The module's 41 pins expose IO0–IO21, IO35–IO42
   and IO45–IO48, plus IO43/IO44 as `RXD0`/`TXD0` — **there are no IO22–IO34 pins at all** —
   and IO19/IO20 are the USB-Serial-JTAG console. That
   is a comfortable, not a tight, fit on the S3 and a squeeze on the C3.
2. **Two general SPI masters (SPI2/SPI3).** The module owns one bus with no CS-timing
   compromises; the second master stays free for the logging/peripheral bus so that no
   peripheral ever shares a bus with the radio. *This is the one rationale whose emphasis
   changes:* the memo cited the two masters as the single strongest reason to prefer the S3
   over the C3 because it assumed **two** SPI radios. With D2 there is one radio bus; the
   S3 is still selected, now on pin budget (1), PSRAM logging (3) and the free second
   master. The original two-master argument applies **in full only to D2-alt**.
3. **8 MB PSRAM for on-board logging.** The flight recorder is the primary evidence source
   after a flight; 512 KB SRAM cannot hold a burst log of raw radio events.
4. **Wi-Fi/BLE for configuration and telemetry while the radios are idle.** This is a
   capability the RP2040 and STM32 options simply do not have, and it is used strictly
   inside the TDM schedule of §3. **It is not free and it is not the current build.** The
   in-repo S3 defaults (`tracker/firmware/sdkconfig.defaults.esp32s3`) currently set
   `CONFIG_ESP_WIFI_ENABLED=n`, `CONFIG_ESP_BT_ENABLED=n` and pin the CPU to 80 MHz
   (`CONFIG_ESP_SYSTEM_DEFAULT_CPU_FREQ_80=y`) for power parity with the C3 baseline. v9
   therefore implies a deliberate sdkconfig change (Wi-Fi enabled, CPU floor revisited for
   the radio tasks) — and that change is what gives the arbiter a genuinely independent
   third band to arbitrate (§3 `WIFI_2G4`). If it is refused, v9 loses the over-the-air
   config/telemetry path and `WIFI_2G4` leaves the arbiter model; no other decision below
   changes.
5. **ESP-IDF is already the flight-firmware stack in this repo.** `tracker/firmware/`
   builds for `esp32s3` (`sdkconfig.defaults.esp32s3`: `CONFIG_IDF_TARGET="esp32s3"`,
   16 MB flash / 8 MB octal PSRAM per its own header comment). No stack port is required.
6. **`-1U` = the U.FL variant** (external antenna connector instead of the on-module
   PCB antenna) — required by D3.

**Sub-decision D1.1 — the module is the `-N8R8` part, and that costs three pins.** On
modules with octal PSRAM (ESP32-S3R8 / R16V), Espressif's ESP32-S3-WROOM-1 datasheet states
that **IO35, IO36 and IO37 are connected to the octal SPI PSRAM and are not available for
other uses**. *Provenance: external datasheet claim, not verifiable from this repo (no S3
datasheet is committed here) — it must be re-checked against the module datasheet revision
at schematic time; it is a 15-minute check that de-risks two SPI pins.* This is
load-bearing: **three of the seven lines in the memo's second SPI column (SCK = GPIO36,
MOSI = GPIO35,
MISO = GPIO37) do not exist on the selected part.** The remaining memo SPI1 lines —
NSS = GPIO38, BUSY = GPIO39, RESET = GPIO40, DIO = GPIO41 — are all real GPIOs, but
GPIO39–GPIO42 are the S3's JTAG port (`MTCK`/`MTDO`/`MTDI`/`MTMS`), so spending them on a
radio costs the classic JTAG interface unless debug is taken over USB-Serial-JTAG (which
the S3 supports). D2 makes this moot for v9; it is
recorded because a future two-radio board would have to re-plan that column, not re-use it.

**Rejected alternatives, honestly:**

| Alternative | Rejected because |
|---|---|
| **ESP32-C3** | One usable general SPI master, so a peripheral must share the radio's bus; far fewer exposed GPIOs (the ADR-031 isolation/test-point requirement cannot be met with margin); 512 KB SRAM, **no PSRAM** — no flight log; RISC-V single core. It remains the *bench* MCU (ADR-028, ADR-001) and that is not changed here. |
| **RP2040** | No native radio host and no Wi-Fi; 264 KB RAM; requires a full radio-stack rewrite. The RP2040 FLRC work in this project (`balloon-e80bench`) is a **measurement tool**, not the flight stack, and must not be mistaken for one. |
| **STM32** | Bench-only experience in this repo; highest porting cost; no Wi-Fi. Legitimate for the E80 bench, not for a v9 flight board. |
| **ESP32-S3 with 2 MB PSRAM (`-1U-N8R2`)** | 2 MB is not a flight log, and it buys nothing else. Its one advantage — with *quad* PSRAM, IO35/IO36/IO37 stay usable — matters **only** for D2-alt, and even there those pins would have to be re-planned rather than trusted. |

### D2 — RF front end: **one** dual-band module, `LoRa2021F33-2G4`

> **Read with D2b.** The operator retained an SX1280 alongside this module on 2026-10-05, so
> D2's "one module" is now **the module *plus* a ranging radio**. The bullets below that
> depend on the SX1280's absence are marked VOID inline; the rest of D2 — the module's
> selection, its numbers and its firmware rules — stands unchanged.

One module replaces the memo's two radios. It is a castellated 39 x 21 mm, 18-pin,
~2.0 mm-pitch module, chip = SEMTECH LR2021, with **independent 50 Ω ports**: pin 9 `ANT`
(sub-GHz 150–960 MHz) and pin 10 `ANT-2G4` (1.9–2.5 GHz).

Rationale:

- **It removes a coupling path instead of managing it.** The memo's second 2.4 GHz
  interferer was the other module on the same board. With one module there is no
  inter-module blocking question and no second ground-return victim.
  **[VOID as written — superseded 2026-10-05 by D2b.]** The SX1280 stays on the board, so
  the second 2.4 GHz interferer — and the inter-module blocking question with it — returns.
  D2b(c) records the three-way 2.4 GHz coexistence this now requires.
- **It removes the LR2021 stock-0 blocker.** `LR2021IMLTRT` and
  `LoRa2021F33-2G4-868MHz` are both at JLC stock 0; the module is a consign/loose-part item
  by definition, which the project already accepted (JLCPCB will place consigned parts).
  **Do not order `LoRa1121F33-2G4-868MHz`** — different chip (LR1121), different part.
- **Built-in PA, TCXO and 2.4 GHz LNA** — no external FEM (SKY66112 removed), no `TX_EN`,
  no VTCXO pin, 0.5 ppm over −40…+85 °C.
- **RTToF ranging and FLRC to 2.6 Mbps at 2.4 GHz** mean the ranging role the SX1280 was
  bought for is served in-module.
- **Numbers (datasheet Rev 1.1, electrical characteristics + power table + voltage table).**
  *Provenance: re-verified 2026-10-05 by text extraction from the committed PDF
  (`docs/f33-module/LoRa2021F33-2G4-datasheet-v1.1.pdf`, pdftotext) — notes 1 and 2, the
  2.4–2.5 GHz register/power/current table and the 5.0 V sub-GHz row, all read directly.*
  Sub-GHz 868/915 MHz: spec typ **30 dBm** (min 28.5 / max 31); at 5.0 V the power table
  gives 29.7–29.8 dBm at 711–724 mA; TX-current spec < 800 mA. 2.4 GHz (1.9–2.5 GHz): spec
  typ **30 dBm** (min 28.5 / max 31); at 5.0 V, 30.0–30.1 dBm at 790–840 mA; TX-current
  spec < 900 mA. 433/470 MHz: up to **33 dBm / 2 W** at 5 V (< 1200 mA). Sensitivity
  ≈ −143 dBm sub-GHz (BW 62.5 kHz, SF12), −136 dBm at 2.4 GHz with the LNA in circuit.
  Sleep < 20 µA; VCC 3.0–5.5 V; 0.5 ppm TCXO.

**Costs accepted, recorded deliberately:**

- **39 x 21 mm on a 55 x 45 mm board** — the module dominates the layout and constrains
  placement before any router runs (ADR-030's placement gate runs earlier for this reason).
- **5 V rail for full power.** At 3.3 V the module still gives ~26.2 dBm/868 and
  ~26.4 dBm/2.4 GHz — i.e. ~3.5 dB below the 5 V figures. The rail decision is **O5**.
- **Severe self-desense is now intrinsic.** The 2.4 GHz TX and the 2.4 GHz RX/LNA are in
  the same package: **TDM is no longer optional** (§3, D4).
- **PA-dial trap, normative for firmware.** For 1.9–2.5 GHz the datasheet says *"it is
  recommended not to set TxPower beyond 4 … Setting the power to the maximum level may
  result in lower output power and higher current consumption. Additionally, continuous
  long-duration transmission at maximum power could potentially damage the power
  amplifier."* TxPower register 4 → 30.1 dBm / 790 mA; registers 7–10 give the same
  30.1 dBm at 810–820 mA; register 13 gives 29.5 dBm. **For 433 MHz, register 36 is
  optimal.** v9 firmware must not "turn the knob to max".
- **`CE` semantics are a power-safety rule, not a convenience.** `CE` low powers the module
  off, and the datasheet requires that *"all MCU pins connected to the module (including
  SPI NSS and RESET) must be configured as low level to prevent current leakage"*. A
  firmware path that asserts `CE` low without driving the SPI/reset lines low is a bug
  that shows up as a dead supercap, not as a dead radio.
- **`DIO5` is the 2.4 GHz LNA control and must default HIGH** (bypass OFF = LNA in circuit,
  −136 dBm). Driving it LOW buys 33 mA of RX current (42 mA → 9 mA) and costs **12 dB** of
  sensitivity (−136 → −124 dBm). This is a firmware policy, held by the arbiter (§3), not a
  strap.

### D2b — AMENDMENT (operator decision, 2026-10-05): the SX1280 is retained for ranging

**Decision.** v9 keeps **both** the `LoRa2021F33-2G4` module (D2, sub-GHz + 2.4 GHz link)
**and** an `SX1280` **as a dedicated ranging radio**, plus the `MAX-M10S` GNSS receiver.
This is neither D2 (one module) nor D2-alt (bare `LoRa2021_Castellated` + SX1280) — it is
D2's module **with** the SX1280 added back. Operator's words: *"Please keep the SX1280 as
well so that we can have ranging. Also please include the MAX-M10S."*

**Ratified 2026-10-05 (second restatement).** The operator re-affirmed inclusion with
a second, independent reason: *"Let's include the SX1280 because it can do range
measurement and because jlcpcb can solder it for us."* Both grounds are therefore on
the record — **ranging capability**, and **JLC SMT-placeability** (it is the only one
of the three 2.4 GHz/sub-GHz radios JLCPCB can actually place; see "Supply position"
below). Neither reason depends on the other, so this decision is not contingent on the
(a)–(e) derivations — those cost out the decision, they do not reopen it.

**Why the in-module RTToF did not satisfy this.** D2 argued that the module's RTToF ranging
(at 2.4 GHz, with FLRC to 2.6 Mbps) served the role the SX1280 was bought for. That
argument is about *capability*, and the operator's requirement is about *interoperability*:
ranging has to work against the **existing SX1280 fleet** — the E28 modules, the
`hub_board_v1_placed` SX1280, and the ranging firmware already written for them. The F33's
RTToF is a different implementation whose on-air compatibility with SX1280 two-way ranging
is **not established** and is not asserted here. A radio that can range only against itself
does not replace one that ranges against the ground segment already in the field.

**Answers O0 (partly).** O0 asked the operator to sign off on the module substitution rather
than have it happen silently. The operator has now done so by *adding* to it, not by
rejecting it: the F33 stands, and the SX1280 is re-instated alongside. D2-alt therefore
remains the reverted configuration, but it is no longer the only two-radio shape on the
table.

**v9 RF complement (four radios):**

| Role | Part | Port / band |
|---|---|---|
| Long-range sub-GHz telemetry | LoRa2021F33-2G4 | pin 9 `ANT`, 150–960 MHz |
| 2.4 GHz link | LoRa2021F33-2G4 | pin 10 `ANT-2G4`, 1.9–2.5 GHz |
| Ranging (fleet interop) | SX1280 | 2.4 GHz |
| Position / time | MAX-M10S | GNSS L1 |
| Config / telemetry when radios idle | ESP32-S3 Wi-Fi/BT | 2.4 GHz — shares the band, see (c) |

**Consequences — what must now be re-derived, not assumed.** None of the following has been
recomputed for this four-radio shape; they are recorded as required work, not as answers.

- **(a) Both SPI masters are now committed.** The F33 exposes **no second SPI** (D1), so the
  SX1280 must take the S3's **second** master. This is precisely the pin-budget argument
  D1 recorded as applying *"in full only to D2-alt"* — it applies again. It also makes the
  S3 mandatory: an ESP32-C3 could not carry it.
- **(b) A pin re-plan is required.** Per D2-alt's note, SPI1's SCK/MOSI/MISO must be
  re-planned **off IO35–37**. That was scoped for `LoRa2021_Castellated` + SX1280; the
  F33 + SX1280 combination has never had a pin plan drawn. **Not done.**
- **(c) Two independent 2.4 GHz transmitters — and a third in the S3.** The F33's 2.4 GHz
  port, the SX1280, and the S3's Wi-Fi/BT all live in 2.4 GHz. The §3 TDM arbiter must
  serialize them; inter-module 2.4 GHz blocking and 868-harmonic-into-SX1280 **return** as
  coupling paths — the very paths D2 claimed to have *removed* are back, now three-way.
  D2's bullet "it removes a coupling path instead of managing it" is **void** as written.
- **(d) Antenna count becomes four, not three.** D3 as written specifies three U.FL pigtails
  (GNSS, sub-GHz, 2.4 GHz). The SX1280 needs its own feed, so D3's connector count is
  amended to **four**: GNSS L1, sub-GHz `ANT`, F33 `ANT-2G4`, SX1280.
- **(e) Power budget is now incomplete.** No rail sum including the SX1280 exists; the O5
  5 V decision must be re-costed against four radios.

**Supply position (the one clear gain).** `SX1280IMLTRT` was probed on the JLCPCB parts API
on 2026-10-05 (card `t_3b823ea8`) at **~1000 in stock, ~$2.85**, and it is an SMT part. The
F33 module and the bare `LoRa2021` are both at **JLC stock 0** and must be consigned. So
retaining the SX1280 **does not add a consign line** — it adds the only one of the three
2.4 GHz/sub-GHz radios JLCPCB can actually place.

**Status of this amendment:** **operator-RATIFIED 2026-10-05.** The operator restated
the decision on 2026-10-05 for two explicit reasons: (i) the SX1280 does **range
measurement**, which the F33's in-module RTToF cannot be assumed to replace on-air
against the existing SX1280 fleet; and (ii) **JLCPCB can solder it** — `SX1280IMLTRT`
is SMT-placeable (~1000 stock, ~$2.85), whereas the F33 module and the bare
`LoRa2021` are both at JLC stock 0 and must be consigned. The *decision* is therefore
closed; the consequences (a)–(e) remain open work. Board area — 39 x 21 mm (F33) plus
an SX1280 module on a 55 x 45 mm board — is now the tightest it has been, and ADR-030's
placement gate runs earlier for exactly this reason. **No schematic, placement or routing
work may start from this amendment until (a)–(e) are re-derived.**

### D8 — operator-**RATIFIED** 2026-10-05: nested dual footprint, F33 **or** bare LoRa2021

Operator: *"put one of each on the JLCPCB board you're designing so that I can choose which
one to fly at a later point in time."*

**Measured from the repo's own footprint files** (`tracker/hardware/hub_board_diy/custom.pretty/`,
compared pad-for-pad 2026-10-05):

- Both modules are **18 pads with identical pad numbering and identical pin functions** —
  pin 1 VCC, pin 9 sub-GHz `ANT`, pin 10 `2.4G/S_ANT`, pins 3–7 SPI (MISO/MOSI/SCK/NSS) + BUSY,
  pins 2/8/11 GND. The pinout is 1:1.
- Geometry differs by ~2×: bare = **1.29 mm** pitch, 0.7 mm pads, body **20.41 × 15.58 mm**;
  F33 = **2.0 mm** pitch, 1.0 mm pads, body **39.6 × 21.6 mm**.
- The bare module's pad field (x ±9.905, y ±5.16) lies **entirely inside** the F33's pad ring
  (x ±19.5, y ±9) — they do not collide. **Two concentric/nested 18-pad footprints are
  therefore geometrically feasible.**

So the "one of each" choice is **nearly free in board area**, because D2 already reserves the
F33's ~39 × 21 mm site. The cost is entirely electrical:

1. **Pin 1 VCC conflict — BLOCKING.** Bare module VCC = **1.8–3.6 V (use 3.3 V)**
   (`nicerf-lora2021.json`). F33 = **5 V**, up to **~1200 mA**. Same pad number → same net.
   Populating an F33 on a 3.3 V net destroys it, and a 3.3 V module on 5 V likewise.
   **Requires a selectable rail on pin 1** (solder jumper or DNP regulator), or the option is
   unsafe to build.
2. **Two RF matching networks.** The F33's +30 dBm sub-GHz port and the bare module's +22 dBm
   port need different matches and power handling. Place both, **DNP** the unused one — using
   DNP pads, **not open stubs** (a stub on an 868/2440 MHz line detunes the populated chain).
3. **The F33 removes the external FEM.** Per `lr2021-module-comparison.md`, the F33's built-in
   PA eliminates the SKY66112 FEM. The bare-module variant therefore needs the FEM **and** its
   control lines — all of which must be depopulated when the F33 flies.
4. **Firmware is shared** (both are LR2021) — one driver. Add a **presence detect** (chip-ID or
   RSSI probe) so firmware *reports* which module is fitted instead of being told.
5. **Never populate both.** Enforce via silkscreen, a bring-up assertion, and CS handling on the
   unused site.
6. **Regulatory (EU/DE) — independent limit on the benefit.** +30 dBm (1 W) / +33 dBm (2 W) is
   **not legal** on 868 MHz or 2.4 GHz in Germany without a licence (868 MHz main band is
   +14 dBm ERP; 2.4 GHz is +20 dBm EIRP). The F33 can only be flown at reduced power.

**Status:** operator-**RATIFIED** 2026-10-05, the same day it was proposed. The operator
accepted the nested site so either module can be fitted at flight time. Ratification records
the **cost** as accepted too: the selectable pin-1 rail is a **design requirement**, not a
suggestion, and the DNP RF/FEM parts are part of the BOM. Grounds for accepting: (i) the
option is **free in board area** — the bare module's pad field nests entirely inside the F33
pad ring that D2 already reserves; (ii) it preserves the module choice *at flight time*, which
is the operator's stated reason; (iii) the cost is **bounded and named** (one rail selector +
DNP parts + presence detect), not open-ended. D8 does **not** change D2/D2b: the F33 remains
the v9 baseline and the primary part; D8 adds the fallback on the same site. Build is gated
behind (b) pin re-plan and (e) power budget, because the rail selector is part of the rail
sum. Tracked by card `t_1b12a7ab`.

**D2-alt — the rejected/reverted configuration (kept live, not deleted).** If the operator
rejects the module substitution, v9 reverts to **LoRa2021_Castellated** (19.81 x 14.98 x
2.32 mm, 18 pads, 1.29 mm pitch, ANT = pin 9 — the v8h part) **+ SX1280** for 2.4 GHz. The
deltas, so the fallback is not re-researched:

| | D2 (one module) | D2-alt (two radios) |
|---|---|---|
| Sub-GHz | F33 pin 9, +30 dBm @ 5 V | LoRa2021 pin 9, +22 dBm |
| 2.4 GHz | F33 pin 10, +30 dBm, LNA +6 dB on DIO5 | SX1280, ~+13 dBm, −120 dBm RX |
| SPI masters | one (module); second free | two (one per radio) — which is what the memo's pin plan assumed |
| Pin plan | memo SPI0 column + `CE` + `DIO5` | memo SPI0 + SPI1, **but SPI1's SCK/MOSI/MISO must be re-planned off IO35–37** (D1.1) |
| Coupling paths | module-internal self-desense + Wi-Fi + GNSS | the above **plus** inter-module 2.4 GHz blocking and 868-harmonic-into-SX1280 |
| Part availability | consign/loose (JLC stock 0, LCSC single-unit or NiceRF direct) | LR2021IMLTRT JLC stock 0; bare module also consign |
| Board area | 39 x 21 mm (dominates 55 x 45) | 19.81 x 14.98 + SX1280 module |

**O0 (operator sign-off required):** the manager's instruction on the v9 BOM card was
"do not silently switch modules — put it to the operator". This ADR records the
substitution and its evidence, and does **not** treat it as silently approved. BOM freeze
for v9 waits on O0.

### D3 — All RF feeds are U.FL pigtails, not chip antennas

**Amended 2026-10-05 (D2b): four connectors, not three.**

Four connectors: **GNSS L1**, **sub-GHz `ANT`**, **2.4 GHz `ANT-2G4`** (F33), **SX1280**.

Rationale: on a 55 x 45 mm board the decisive separation is **off-board in 3D**. On a
balloon the four antennas get 10+ cm of physical spacing and orthogonal orientations; a
chip antenna forces the entire fight onto the PCB, where it cannot be won. This is
precisely why the MCU is the `-1U` (external-antenna) variant — the Wi-Fi radiator is a
pigtail too, so it can be routed to the opposite end of the payload (memo §2(a)).

Board-level placement rule that follows (not decoration — it is the electrical reason the
choice works): GNSS U.FL on the **+Y sky-facing edge**, sub-GHz U.FL on the **−Y edge**,
2.4 GHz U.FL on a **side edge at mid-point**, each with its own solid reference-plane patch
and a keep-out to the header and to each other; the two 2.4 GHz-capable feeds never
co-polarised closer than λ/2 (~6 cm at 2.4 GHz).

### D4 — Coexistence is enforced by **one firmware arbiter + hardware BUSY polling**, not by convention

A single arbiter owns every RF grant. No module, task or driver may key a transmitter
without holding a grant. §3 is the normative schedule; §5 test 5 is the normative proof.
Two bindings are hardware, so a wedged task cannot lie about them:

- the module's `BUSY` line (F33 pin 14) is read **by GPIO, without the module driver's
  cooperation**, before a grant is released or re-granted;
- Wi-Fi/BT is *stopped and confirmed down* before a 2.4 GHz grant is issued — a request to
  stop is not evidence of being stopped.

### D5 — Reuse the v8h RF/DRC rule set and the frozen campaign `.kicad_dru`

`tracker/hardware/jlcpcb-s1-frozen.kicad_dru` stays the rule set for the RF/geometry
verdict; the existing scorecard tooling stays the referee — `tracker/hardware/drc_score.py`
(which shells `kicad-cli pcb drc --json` and appends one row per attempt to
`tracker/hardware/drc_snapshots/history.jsonl`), plus `tracker/hardware/gate25_check.py`
and `tracker/hardware/placement_guard.py` (ADR-030).
**No new rule regime is introduced for v9.** A v9 board claim is only comparable to v8h
when the `.kicad_dru` and the placement hash are identical-or-explicitly-recorded
(ADR-030 negative result 5).

---

## 1. The four radio systems that must share the board

| radio | band | role | worst case (v9, corrected) |
|---|---|---|---|
| ESP32-S3 Wi-Fi/BT (`-1U` U.FL) | 2400–2483.5 MHz | config/telemetry, intermittent | +20 dBm TX, on-die, off-board pigtail |
| Module 2.4 GHz port (`ANT-2G4`) | 1.9–2.5 GHz (use 2400–2500) | ranging / 2.4 GHz link, FLRC | **+30 dBm (1 W) TX**, −136 dBm RX (LNA in circuit) |
| Module sub-GHz port (`ANT`) | 863–870 MHz | long-range telemetry | **+30 dBm (1 W) TX** |
| MAX-M10S | 1559–1610 MHz (L1) | position/time | −165 dBm acquisition (memo §1; not re-derived in this ADR) |

All three transmitters and the GNSS front end now contend for one 55 x 45 mm board.
**Two of the four radios operate in 2.4 GHz** (the S3's Wi-Fi/BT and the module's
`ANT-2G4` port), a third (the sub-GHz port) can reach the band by harmonic leakage (§2(c)),
and the GNSS receiver is 60–75 dB weaker than everything else.

## 2. Mechanism-by-mechanism, with the mitigation for each

**(a) Module 2.4 GHz TX ↔ module 2.4 GHz RX/LNA — same package, intrinsic.**
This is the dominant path and it cannot be fixed in copper: the PA and the LNA share a
die and a port. At +30 dBm even a weakly-coupled internal path is a blocking-level
interferer against a −136 dBm receiver, and the LNA is the victim (a +6 dB LNA raises the
compression risk, it does not lower it).
*Mitigation (all of):* (1) **TDM by design** — the module never transmits 2.4 GHz while its
own 2.4 GHz RX is armed, enforced by the arbiter, not by convention; (2) `DIO5` HIGH
whenever 2.4 GHz RX is armed (LNA in circuit) and the 33 mA it costs is budgeted, never
traded for sensitivity by accident; (3) TX power set to the measured minimum that closes
the link, capped at TxPower register 4 for 2.4 GHz (D2); (4) the 868 and 2.4 GHz feeds are
never co-polarised within λ/2.

**(b) ESP32-S3 Wi-Fi/BT ↔ module 2.4 GHz — same band, same board, ~2 cm.**
Blocking and LNA desense, not harmonics. S3 Wi-Fi at +20 dBm next to the module's receiver,
and vice versa.
*Mitigation (all three):* TDM — Wi-Fi/BT **off** whenever the 2.4 GHz port is armed
(enforced in firmware as one arbiter, D4); the `-1U` U.FL Wi-Fi pigtail, physically routed
to the opposite end of the payload; the two 2.4 GHz-capable feeds on opposite board edges,
orthogonal.

**(c) Module sub-GHz TX into the module's own 2.4 GHz RX — harmonics and broadband noise.**
868 is not the problem (~1.5 GHz away); leakage is. The 3rd harmonic of 868 lands at
~2604 MHz — above the 2.4 GHz band edge, but inside the receiver's wideband front end. The
memo's arithmetic (+22 dBm fundamental, −40 dBc harmonic → −18 dBm) **worsens by 8 dB to
−10 dBm at +30 dBm**, and there is no board-level isolation available between two ports of
one module.
*Mitigation:* keep the module's internal TX filtering; add a **harmonic LPF on the sub-GHz
feed** if the bench shows any 2.4 GHz floor rise with 868 keyed, and a **2.4 GHz SAW/BPF on
the `ANT-2G4` feed** if the 2.4 GHz RX floor moves when 868 transmits. Both are 0–2 EUR
parts and both must be decided by measurement, not by datasheet margin. Because these
paths are internal, TDM is the primary mitigation; the filters are the second line.

**(d) Module TX (both bands) into GNSS L1.**
GNSS is not near either band in frequency, so the threats are **wideband noise, supply
modulation and rail dips**: switching-regulator noise, the S3's 40 MHz clock harmonics, and
rail dips on 1 W TX bursts (up to <900 mA at 2.4 GHz, <800 mA at 868/915).
*Mitigation:* dedicated RC/ferrite feed (e.g. 100 Ω + 10 µF) from 3V3 into the GNSS rail;
its own ground return starred at the battery node; GNSS at the **sky-facing edge** with a
keep-out free of any TX trace and of via stitching; no TX trace and no via ring inside the
GNSS keep-out.

**(e) Physical separation on the PCB (the cheap, biggest win).** As D3: three U.FL on three
edges, each with its own reference patch and keep-out; the decisive separation happens
off-board in 3D.

**(f) Supply and return.** Each radio rail gets its own ferrite + bulk cap from 3V3; TX
bursts (<800 mA @868, <900 mA @2.4 GHz, <1200 mA at 433) must not modulate another rail or
the GNSS LNA; returns star at the battery node, not at a shared plane neck. `CE`-low sleep
must be paired with all module-facing MCU pins driven low (D2).

## 3. Time/frequency plan — the arbiter spec

One firmware entry point, `radio_arbiter_acquire(band)` / `radio_arbiter_release(band)`,
plus hardware reads of the module `BUSY` line and of the Wi-Fi interface state.

| slot | owner | duration | rule |
|---|---|---|---|
| 0–900 ms | 2.4 GHz link/ranging (module `ANT-2G4`) | up to 900 ms | Wi-Fi/BT forced **OFF and confirmed down**; sub-GHz TX inhibited; `DIO5` HIGH |
| 900–1000 ms | quiet | 100 ms | GNSS wakes, position captured; band switch guard |
| 1000–1100 ms | sub-GHz telemetry (module `ANT`) | 100 ms | 2.4 GHz RX idle; GNSS in normal tracking |
| 1100 ms – 2 s | GNSS + sensors | 900 ms | both radio ports idle; Wi-Fi/BT may run in this window only |

Arbiter rules (normative):

- **R1.** `radio_arbiter_acquire` is the only way to key a transmitter; a task that cannot
  acquire must block, never proceed.
- **R2.** `SUB_GHZ` and `BAND_2G4` grants never overlap. The two ports belong to **one
  transceiver core**, so the two links are mutually exclusive in time by construction —
  and `WIFI_2G4` is exclusive with both. (The price of that exclusivity is the band
  switch itself, measured in O6.)
- **R3.** A grant is released only after the module's `BUSY` line is **read deasserted**
  (GPIO poll, not driver report).
- **R4.** Every grant carries a TTL. A task that dies holding a grant must not wedge the
  radio: on expiry the arbiter reclaims the band and increments a stall counter.
- **R5.** The arbiter owns `DIO5` and the band/`CE` state, and restores the safe state
  (`CE` high, module idle, `DIO5` HIGH) on any failure path.
- **R6.** The 868↔2.4 GHz turnaround is a **measured** guard interval, not zero: the slot
  table above assumes a guard to be measured on the bench (open question O6).

## 4. Pin plan (ESP32-S3-WROOM-1U)

Two constraints bind before any assignment: **only IO0–IO21, IO35–IO42 and IO45–IO48 are
exposed** on the module, and on the `-N8R8` part **IO35/IO36/IO37 are consumed by the octal
PSRAM** (D1.1). IO19/IO20 stay reserved for the USB-Serial-JTAG console.

| function | GPIO | origin | note |
|---|---|---|---|
| SCK | GPIO12 | memo SPI0 column | S3 `FSPI` (SPI2) IO_MUX default |
| MOSI | GPIO11 | memo | `FSPID` |
| MISO | GPIO13 | memo | `FSPIQ` |
| NSS | GPIO10 | memo | `FSPICS0` |
| BUSY | GPIO9 | memo | arbiter input, polled directly (R3) |
| RESET | GPIO8 | memo | |
| IRQ / DIO | GPIO7 | memo | |
| **CE** | GPIO38 *(recommended)* | **new with D2** | module pin 5; low = module powered off; pair with all pins low |
| **DIO5** | GPIO39 *(recommended)* | **new with D2** | 2.4 GHz LNA control; **default HIGH** (bypass OFF) |
| GNSS UART RX | GPIO17 | memo | MAX-M10S TX |
| GNSS UART TX | GPIO18 | memo | MAX-M10S RX |
| GNSS `PPS` | GPIO21 | memo | TIMEPULSE, optional |
| Wi-Fi antenna | U.FL | D3 | `-1U` variant only |

Freed by D2: the whole memo SPI1 column (`NSS` 38, `BUSY` 39, `RESET` 40, `DIO` 41 —
GPIO39–41 of which are the JTAG port, recoverable over USB-Serial-JTAG), and its three
non-existent lines IO35/36/37 (D1.1). Those pins are the budget for §4's two new lines
and for ADR-031's isolation links and test points.

Two constraints the schematic card must honour when it fixes the *recommended* numbers:

- **Do not spend an ADC-capable pin on a digital-only line.** On the S3 the ADC1 channels
  are GPIO1–GPIO10 and the module's own column already takes GPIO5–GPIO13 as ADC-capable
  pins. `CE` and `DIO5` are strict outputs, so they are recommended on the *non-ADC* pins
  D2 frees (GPIO38/GPIO39); any reassignment must leave an ADC pin for the supercap
  divider.
- **Do not repeat the V7 ADC collision.** `docs/coordination/CONSULTANT-PLAN-REVIEW-V7.md`
  records a real defect in an earlier plan: `SUPERCAP_ADC_CHANNEL = ADC1_CHANNEL_0`
  (= GPIO0) was also assigned to the GPS UART TX, so the supercap sense and the GPS TX
  were the same physical pin. On v9 the GNSS UART is on GPIO17/18 (not GPIO0/1), but the
  divider pin must still be checked against every other assignment in the same netlist.

## 5. Verification protocol (five tests, acceptance numbers)

Tests 1–4 need the physical board (a bench campaign in the style of `balloon-e80bench`);
test 5 is host-side and is the first thing to write.

| # | test | setup | acceptance |
|---|---|---|---|
| 1 | 2.4 GHz RX desense by the sub-GHz port | RSSI noise floor at 3 frequencies: (i) all radios off, (ii) sub-GHz keyed at its maximum setting (TxPower register 44), (iii) Wi-Fi beaconing | floor rise **< 3 dB** with sub-GHz keyed; a rise ≥ 3 dB triggers the §2(c) LPF decision |
| 2 | Wi-Fi ↔ module 2.4 GHz mutual | 2.4 GHz PER sweep at fixed distance and fixed TX power, Wi-Fi off vs on, arbiter active | PER degradation **< 1 dB** |
| 3 | GNSS C/N0 under the TDM schedule | mean C/N0 of the visible constellation with radios idle, then with both ports in the §3 schedule | C/N0 drop **< 1 dB** |
| 4 | Rail sanity | scope the GNSS rail during sub-GHz and during 2.4 GHz TX bursts (worst-case register setting in use) | rail dip **< 20 mV** |
| 5 | Arbiter fuzz (host-side) | see spec below | **0 assertion violations** over 10 000 iterations x 8 seeds, **and** the un-arbitrated baseline must fail |

**Test 5 specification — precise enough to be implemented as a RED test.**

- *Seams the test requires (this is the contract; if the seams do not exist, build them first).*
  - `radio_arbiter_acquire(band, ttl_us) -> grant_id | BLOCKED`, `radio_arbiter_release(grant_id)`,
    `radio_arbiter_reclaim_expired(now_us)`.
  - `bands` = `{SUB_GHZ, BAND_2G4, WIFI_2G4, GNSS_QUIET}`.
  - `arbiter_busy(band) -> bool` — **substitutable** by the test. In production it is the
    direct hardware read of the module `BUSY` line (F33 pin 14) for `SUB_GHZ` and
    `BAND_2G4`, and the Wi-Fi-interface-confirmed-down state for `WIFI_2G4`; in the
    harness it is a fake.
  - `now_us() -> int` — substituted by a fake clock the harness advances explicitly.
  - `grant_log` — append-only records `(grant_id, band, t0_us, t1_us, ttl_us, task_id)`.
- *Fixtures.* Three concurrent logical tasks — sub-GHz telemetry, 2.4 GHz ranging, Wi-Fi
  config — each in a loop requesting its band, holding for a duration drawn from a
  **binary ladder** hold time ∈ {1, 2, 4, 8, …, 512 ms} (log2 sweep, not a uniform draw),
  then releasing. TTL = 2 x requested hold + 10 ms. Seeded PRNG; the 8 seeds are recorded
  in the test output so a failure is reproducible.
- *Instrument size.* 10 000 iterations per seed, 8 seeds → 80 000 arbitration events per run.
- *Adversarial injections (each must be exercised in every run).*
  1. `arbiter_busy(other_band)` asserted at the moment of a grant request.
  2. `arbiter_busy` spuriously asserted for a bounded interval *during* a held grant, then
     released.
  3. A task **dies holding a grant** (never calls release) → TTL expiry must reclaim it.
  4. `arbiter_busy` asserted and **never released** (wedged module) → no other grant may be
     issued, and the arbiter must report a stall rather than proceed.
- *Assertions (all must hold for every event in every run).*
  - **A1 mutual exclusion.** No two of `{SUB_GHZ, BAND_2G4, WIFI_2G4}` have overlapping
    grant intervals. `GNSS_QUIET` never overlaps `SUB_GHZ` or `BAND_2G4`.
  - **A2 busy honesty.** No grant interval starts or ends while `arbiter_busy(band)` is
    asserted for that band.
  - **A3 bookkeeping.** Every acquire is matched by exactly one release; no double release;
    no release without acquire; every `grant_id` in the log is unique.
  - **A4 TTL.** No grant interval exceeds `ttl_us` + epsilon (epsilon = one scheduler tick);
    every injection 3 produces exactly one reclaim and one stall-counter increment.
  - **A5 injection 4.** During a permanent `BUSY`, the count of *new* grants is 0 and the
    stall counter is non-zero.
  - **A6 liveness.** Every task's every request is eventually granted — the run terminates
    within a bounded number of scheduler cycles, i.e. no deadlock, no starvation of one
    band.
- *RED requirement.* The same harness must be run against a **baseline build whose arbiter
  is stubbed to always grant**. The baseline MUST violate A1 (and A2) — otherwise the test
  is not testing anything. This baseline run is part of the test, not a separate chore.

## 6. Consequences, and open questions

### Positive

- **Two controllable RF parts (plus GNSS) instead of three.** *(Revised 2026-10-05 by D2b:
  was "one RF part".)* The F33 collapses the sub-GHz radio and the 2.4 GHz link into one
  package, so what remains outside it is the SX1280 and the GNSS receiver. That still buys a
  shorter power-up sequence, one band switch for the link, and one thermal source for the
  30 dBm PA — but it is **no longer** "one firmware driver" or "one arbiter policy": the
  arbiter now schedules three 2.4 GHz contenders (F33 port, SX1280, S3 Wi-Fi/BT).
- ~~The board's hardest coupling (module ↔ module at 2.4 GHz) is designed out rather than
  mitigated.~~ **False as written — voided 2026-10-05 by D2b.** The module ↔ module 2.4 GHz
  coupling is back on the board and must be *mitigated*, not assumed away. See D2b(c).
- The stock-0 blocker on the sub-GHz side does **not** improve: the F33 itself is JLC stock 0
  and must be consigned. *(The only gain is that the SX1280 does not add a further consign
  line — `SX1280IMLTRT` is in stock and SMT-placeable, ~$2.85, per the 2026-10-05 probe.)*
- U.FL on all four feeds converts an unsolvable 55 x 45 mm problem into a solvable 3D one.
- The v8h rule set and `.kicad_dru` carry over, so v9's DRC verdict is comparable to v8h's.

### Costs / risks accepted

- **1 W TX on a balloon payload**: TX current <900 mA at 2.4 GHz and <800 mA at 868/915,
  plus a 39 x 21 mm module's thermals next to a GNSS LNA. The supercap must source the
  burst and the GNSS rail must be immune (test 4).
- **TDM is mandatory, so peak capability is lower than a naive read of the module's
  datasheet.** The 2.4 GHz link and the sub-GHz link are never simultaneous, and the
  arbiter's guard interval (O6) is direct link budget.
- **Board area**: the module dominates placement; some v9 features may not fit.
- **The module PA is not indestructible** (datasheet note 2) — a firmware mistake in
  TxPower is a hardware loss, not a bad packet.
- **`CE`-low sleep has a software precondition** (all module-facing pins low) that is easy
  to get wrong and expensive to debug in flight.
- **Consign parts** add a buying step to the order (LCSC single-unit or NiceRF direct),
  and `LoRa1121F33-2G4` is a live trap for whoever places the order.

### Open questions

**For the consultants (the four from the memo — all still OPEN and unanswered by an
independent family; as of 2026-10-04 every non-deepseek lane was unfundable: glm / kimi /
qwen / tencent / minimax all HTTP 503, ollama_cloud_3 subscription past due. The single
funding action that unblocks the U2 review unblocks this consultation.):**

1. Is the harmonic LPF on the sub-GHz feed actually needed, or does the module's internal
   filtering plus the receiver's own front-end selectivity make it redundant at these
   power levels — noting that with D2 the interferer and the victim are in one package?
2. `-1U` (U.FL Wi-Fi) vs the standard WROOM-1 PCB antenna: does the pigtail on the Wi-Fi
   antenna introduce more risk (feed loss, ground-plane dependence) than it removes?
3. Is a shared-SPI design (one bus, two CS) genuinely acceptable, or is the second master
   worth keeping free for the logging/peripheral bus?
4. GNSS keep-out size and reference-plane cut: what is the minimum that still yields a
   usable L1 feed on a 55 x 45 4-layer board with a 0.6/0.3 via floor?

**Also open, and owned by us rather than by a consultant:**

- **O0 — operator sign-off on the module substitution.** *Resolved at the part-identity
  level:* the operator's decision list of 2026-10-05 (item 4, recorded on the JLCPCB BOM/CPL
  card `t_3b823ea8`) names the module — "our module is G-NiceRF **LoRa2021F33-2G4** (built on
  SEMTECH LR2021)" — and forbids the LR1121-based LCSC listing, so the part is not being
  switched silently; the manager's "do not switch silently" instruction is satisfied by that
  record. *What remains open is the form-factor consequence, not the part:* 39 x 21 mm
  dominates a 55 x 45 mm board and the 5 V/1 W consequences in D2 are real costs. D2-alt is
  the fully specified fallback if the operator prefers the smaller 19.81 x 14.98 mm module
  and a separate SX1280. No BOM freeze before that is settled.
- **O5 — the 5 V rail: BLOCKED pending evidence.** The four-radio rail sum is recorded in
  `docs/POWER-BUDGET-V9-D2BE.md`. It requires a specified 5 V chain demonstrated at >=1.2 A
  load-step capability, a 3.3 V rail at >=0.60 A transient capacity, and cold supercap/
  regulator evidence. Keep the 5 V option selectable in the schematic, but do not freeze
  the BOM or approve flight on an unmeasured chain; if the evidence fails, operate the F33
  at 3.3 V with reduced output rather than claim +30 dBm.
- **O6 — measured 868↔2.4 GHz band-switch + TCXO-settle time.** The §3 slot table assumes a
  guard interval; with one module every band change is a re-tune, not a second
  transceiver. It must be measured before slot durations are frozen, and it is part of
  test 5's model once known.
- **O7 — ADR numbering collision.** `029-firmware-output-harmonization.md` on the unmerged
  `feat/e80-spi-bypass` branch claims the same number. Whoever merges second must
  renumber or consolidate; flagged to the manager.

### D6 — Barometric sensor: `MS5611-01BA03` (flight), not a Bosch BMP part

**Amendment, 2026-10-05.** The schematic plan labels the optional I2C sensor
"BMP280 (opt)" (U5). The BMP family cannot measure this mission's altitude range,
so that label is corrected here.

| Part family | Pressure range | Verdict for this board |
|---|---|---|
| BMP280 | 300–1100 mbar | **ground testing only** |
| BMP384 / BMP388 / BMP581 | 300–1100 hPa | **same ~300 mbar floor — ground only** |
| **MS5611-01BA03** | **10–1200 mbar** | **flight — full altitude to ~30 km** |

The requirement is not new. `docs/PRESSURE-TEST-PLAN.md` §2.1 already states it:
*"MS5611 covers 10-1200 mbar (full balloon altitude to ~30km), BMP280 covers
300-1100 mbar (ground testing only)."* A Bosch BMP part reaches ~300 mbar ≈ 9 km;
this mission's ceiling is far above that, so a BMP part reads nothing where it
matters most.

**Decision.** v9 fits an `MS56xx` on the I2C bus (GPIO20/21). Two options, both
verified in stock 2026-10-05, both 10–1200 mbar, both extended parts:

| Part | Stock | Unit | Note |
|---|---|---|---|
| **`MS5607-02BA03`** | **1698** | **$2.43** | **cost pick** — same range, same family |
| `MS5611-01BA03` | 1671 | $5.03 | the part already named in project docs + v8h stubs |

They share the MS56xx family register/PROM interface (I2C 0x76), which is what the
existing auto-detecting firmware reads, so either drops into the same driver and
land pattern. **`MS5607-02BA03` is the recommendation** — the original ask was the
cheapest stocked sensor that makes sense, and the MS5611's extra accuracy class is
not needed to log balloon altitude.

**Retraction.** An earlier recommendation in this session proposed BMP384 (979 in
stock, $1.78) or BMP581 (2654, $1.64) as "a generation upgrade over the BMP280".
Both are **wrong for flight** — they share the BMP family's ~300 mbar floor.
Cheapest-stocked was the wrong criterion; **range** was the criterion. Recorded so
the same reasoning is not repeated.

**Supporting evidence.**
- v8h was already routed with **"I2C MS5611 stubs"**
  (`docs/PLAN-DRC-CLEANUP-JLCPCB-ORDER.md`, DRC signal list) — the board
  anticipated MS5611 even though the schematic text said BMP280.
- Firmware exists: `tools/balloon_pressure_test/` auto-detects BMP280 then MS5611
  (I2C 0x76, PROM read) — no new driver is needed.
- Package differs from BMP280 (MS5611 LGA-8 is 5.0 x 3.0 mm vs 2.5 x 2.5 mm), so
  the land pattern must be authored; KiCad ships no MS5611 footprint in its
  standard libraries.

### D7 — Parts availability is a gate BEFORE layout, not a discovery after

**Amendment, 2026-10-05.** v8h reached fab-ready with **4 of 20 BOM lines
non-assemblable at JLCPCB** — the LoRa2021F33 module, the BMP280, the 1F supercap
and the through-hole headers (J1/J2/SOLAR). All four were found *after* routing,
when changing them had stopped being free.

**Decision.** Before the v9 schematic card opens, and before any BOM freeze, probe
**every** MPN in the BOM with the existing tool:

```bash
python3 skills/hardware/pcb-fab-readiness-gating/scripts/jlc_parts_probe.py <MPN...>
```

It queries JLCPCB's parts API and reports per MPN whether a **vendor row with
stock > 0** exists (assembleable) or only a `JLCPCB Assembly` placeholder row
(stock 0 — consign or omit). Every non-assembleable line is decided before layout:
substitute, consign, or plan hand-soldering.

**Why this is the right gate.** Run against 13 candidate MPNs on 2026-10-05 it
separated stocked from dead parts in a single command, and it is what exposed the
BMP280's real status (only `JLCPCB Assembly` placeholder rows, stock 0). The same
check before layout would have caught v8h's four lines while they were still free
to change.

### Rollout

1. This ADR lands on `pr/029-dual-band-flight-board` and merges to `main` — it is the gate
   for the v9 schematic.
2. Test 5's harness is written next as a RED test (host-side, no hardware) — it is the only
   v9 artefact that can be proven before a board exists.
3. The v9 schematic card opens only after this lands, with ADR-031 (isolation links + test
   points), ADR-032 (LTspice/openEMS evidence for the matching, filter and rail) and
   ADR-030 (placement gate before copper, deterministic routing) as its method.
4. O0 and O5 are decided by the operator before any BOM freeze or order.
5. **D6** — the barometric part is fixed to `MS5611-01BA03` before the schematic
   card; the stale "BMP280 (opt)" label is corrected, and its land pattern is
   authored (KiCad ships none).
6. **D7** — the availability probe runs against every BOM MPN before the v9
   schematic card opens and before any BOM freeze.
7. **(a)–(e) from D2b are NOW** (operator, 2026-10-05) — the pin plan, the
   three-way 2.4 GHz arbiter, the four-antenna count, the power budget and the
   SPI1 re-plan off IO35–37 gate the schematic card. The F33+SX1280 pin plan is
   recorded in `docs/adr/029-f33-sx1280-pin-plan.md`; it leaves IO35–37 and the
   four S3 strapping pins (IO0, IO3, IO45, IO46) unassigned and calls out the
   accepted native-JTAG trade-off on IO39–42.
8. The multi-SX1280 throughput question is analysed in
   `docs/SX1280-ARRAY-FEASIBILITY.md` — **analysis only, no board authorised.**
