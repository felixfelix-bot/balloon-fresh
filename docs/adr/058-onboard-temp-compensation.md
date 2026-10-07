# ADR-058 — On-board temperature-sensor-based drift compensation: the LR2021's XOSC-adjacent sensor as the primary instrument, a per-unit calibration curve, GPS 1PPS verification, and an MS5611 cross-check

> **Number allocation.** `python3 scripts/adr_next_number.py` prints **57** in this
> checkout, **but 057 is NOT free** — a sibling worker has already claimed it:
> `docs/adr/057-flrc-drift-strategy.md` exists on branch `adr/flrc-drift-strategy`
> and is simply not visible from this worktree. The number was therefore **not**
> hard-coded to the script's output: 056 and 057 were checked **across all refs**
> (`git log --all --name-only --pretty=format: | grep -E '^docs/adr/05[6-9]-'` →
> `056-thermal-and-frequency-drift.md`, `057-flrc-drift-strategy.md`) and **058 is
> the next number free on every branch**. 058 was re-confirmed free immediately
> before writing (`scripts/adr_next_number.py --path
> docs/adr/058-onboard-temp-compensation.md` → `58`, exit 0).
> `tests/test_adr_numbering.py` stays green and `docs/adr/INDEX.md` is regenerated
> by `scripts/gen_adr_index.py`. No file is renamed or renumbered.

- Status: **Proposed** — the *direction* is the operator's (his ask of 2026-10-07 to
  turn this into an ADR **and make it actually happen**); the *text* has not been
  accepted by a human, so it does not say Accepted. No schematic, placement, BOM
  freeze or fabrication may treat it as frozen until a human accepts it.
- Date: 2026-10-07
- Decision owner: Felix (operator). The question is his; the text is not accepted.
- Author: Hermes subagent, branch `adr/onboard-temp-compensation`, worktree
  `~/worktrees/bf-tcomp`.
- Evidence base (read in full to write this record):
  `docs/analysis/meshcore-lr2021-drift.md`,
  `docs/analysis/external-clock-and-ocxo.md`,
  `docs/analysis/thermal-and-frequency-drift.md` (+ its arithmetic
  `docs/analysis/thermal_frequency_drift_model.py`),
  `docs/adr/042-thermal-drift-strategy.md` (incl. **Addendum A**),
  `docs/adr/056-thermal-and-frequency-drift.md`,
  and — for the implementation — the **vendored sources** named in §1.
- Related records: **ADR-042** (heater rejected; TCXO first; the Addendum-A
  `GetTemp`/NTC correction; the MS5611 heating conflict), **ADR-043**
  (cold-qualification heating rejected; below-rated parts gated), **ADR-056**
  (no heater; per-radio reference census; GPS 1PPS discipline as the primary
  provision), **ADR-108** (F33 + SX1280 + MAX-M10S pin plan, `GNSS_PPS`),
  **ADR-029 D6** (MS5611-01BA03 barometric part), **ADR-017 / ADR-019 / ADR-021 /
  ADR-023** (GPS-UTC timing authority), **ADR-036 / ADR-047** (energy policy, bank
  sizing), **ADR-052** (end-only unbonded cell mount — untouched here).
- **No hardware is ordered by this record. It is design work only and nothing is
  flashed.** No existing file is renamed or renumbered.

---

## 0. What this record adds over ADR-042 and ADR-056

ADR-042 rejected the heater, ranked TCXO > NTC > firmware pre-distortion, and
Addendum A corrected the "no runtime sensor exists" premise. ADR-056 re-derived
the heater rejection in `G` form, published the per-radio reference census, and made
**GPS 1PPS discipline** the primary provision.

Neither names *which* of the LR2021's sensor sources to use, neither defines the
compensation as an ordered layer stack, neither states the non-volatile-storage
requirement for the per-unit curve, and neither ships any code. **This record does
all four**, because the operator asked for this to become an ADR *and to actually
happen* — so §4 records the firmware module that now exists, builds and passes tests.

This record **does not** re-open ADR-042 §D1 (heater) or ADR-056 §D1/D2/D3; it
**implements and sharpens** them.

---

## 1. Context — the instrument, verified line by line

Everything in this section was read out of the repository's own vendored sources
immediately before writing. Where a claim could **not** be verified it is marked
`TODO(unverified)` and is **not** asserted.

### 1.1 The LR2021 has an on-chip temperature sensor, and one source sits adjacent to the crystal

The vendored RadioLib LR2021 driver,
`tracker/firmware/components/RadioLib/src/modules/LR2021/`:

| Fact | Source line | Value |
|---|---|---|
| temperature command | `LR2021_commands.h:32` | `RADIOLIB_LR2021_CMD_GET_TEMP = 0x0125` |
| source: general die junction | `LR2021_commands.h:249` | `RADIOLIB_LR2021_TEMP_SOURCE_VBE = 0x00 << 4` — *"sensor near Vbe junction"* |
| source: **crystal-adjacent** | `LR2021_commands.h:250` | `RADIOLIB_LR2021_TEMP_SOURCE_XOSC = 0x01 << 4` — *"sensor near XOSC"* |
| readout format | `LR2021_commands.h:252` | `RADIOLIB_LR2021_TEMP_FORMAT_DEG_C = 0x01 << 3` — degrees Celsius directly (`:251` is `RAW`) |
| resolution field base | `LR2021_commands.h:246` | `RADIOLIB_LR2021_MEAS_RESOLUTION_OFFSET = 8` |
| driver conversion | `LR2021_cmds_chip_control.cpp:171-180` | argument byte `(source & 0x30) \| FORMAT_DEG_C \| ((8 + bits) & 0x07)`; reply is 2 bytes; **`*temp = (float)raw / 320.0f`** |
| default resolution | `LR2021.h:595` | `float getTemperature(uint8_t source, uint8_t bits = 13)` |
| low-level wrapper | `LR2021.h:728`, impl. `LR2021_cmds_chip_control.cpp:171` | `int16_t getTemp(uint8_t source, uint8_t resolution, float* temp)` |

Independently confirmed by the **second** vendored driver in this repo,
`firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/` (Semtech's own):

| Fact | Source line | Value |
|---|---|---|
| temperature command | `src/lr20xx_system.c:142` | `LR20XX_SYSTEM_GET_TEMP_OC = 0x0125` |
| command / reply length | `src/lr20xx_system.c:71`, `:105` | cmd 3 bytes `{0x01,0x25,arg}`; **reply 2 bytes** (`MEASURE_LENGTH = 2`) |
| argument packing | `src/lr20xx_system.c:458-475` | `(src << 4) + (format << 3) + res` — *identical* to the RadioLib packing, reached independently |
| °C layout (documented) | `inc/lr20xx_system.h:391-411` | *"the temperature is given in [°C] in 13.5sb format, the first byte returned contains the integer part, the second the fractional part"* |

**This is the finding the record is built on: the LR2021 exposes a temperature
sensor whose `TEMP_SOURCE_XOSC` selection measures the node adjacent to the 32 MHz
crystal — i.e. the temperature of the element that actually drifts — over SPI, at
runtime, with no extra component.** This is why a board-level proxy (an NTC on the
PCB, the ESP32 die sensor, the MS5611) cannot be the primary instrument: it measures
a different node, separated from the crystal by FR4 and its own thermal gradient
(ADR-042 Addendum A3 point 3; ADR-056 §D2/§D4).

### 1.2 A genuine defect found while verifying: the two vendored drivers DISAGREE on the °C scale

This is new and load-bearing, so it is recorded rather than smoothed over:

- **RadioLib** reassembles the 2-byte reply as an **UNsigned** 16-bit value and
  divides by **320.0** (`LR2021_cmds_chip_control.cpp:174-177`).
- **Semtech** documents a `byte0 = integer part, byte1 = fractional part` layout
  (`inc/lr20xx_system.h:399-400`) and its own getter reassembles
  `(b0 << 8 | b1) >> 3` (`src/lr20xx_system.c:465`), i.e. an LSB of 1/32 °C.

**Both cannot be right.** More seriously for this mission: RadioLib's `uint16_t`
reassembly **cannot represent sub-zero temperatures at all** — a −60 °C reading
becomes a large positive number. A −60 °C mission cannot use that path blind.

This record therefore requires the scale to be **pinned by measurement, not
assumption**: the bench cold-soak (§2 D5.1) is at known absolute temperatures, so it
decides the scale. The firmware module (§4) exposes the scale as a parameter
(`TEMP_COMP_DEG_C_SCALE_RADIOLIB` = 320.0 / `TEMP_COMP_DEG_C_SCALE_SEMTECH` = 256.0)
and a signed-capable reader, and carries the reconciliation as an **open item**
(§5.5). Nothing here silently picks a winner.

### 1.3 What else the part offers for applying a correction

| Command | Opcode | RadioLib (vendored) | Semtech driver (vendored) |
|---|---|---|---|
| `SetXoscCpTrim` / `configure_xosc` | `0x0131` | **present** — `LR2021_commands.h:55`, `LR2021.h:750`, impl. `LR2021_cmds_chip_control.cpp:306-309`, frame `{0x01,0x31, xta&0x3F, xtb&0x3F, startTime}` | **present** — `src/lr20xx_system.c:149`, impl. `:566-577`, frame `{0x01,0x31, xta, xtb, wait_time_us}` |
| `SetTempCompCfg` | `0x0132` | **ABSENT from the vendored RadioLib LR2021 driver** | **present** — `src/lr20xx_system.c:150`, impl. `:579-589`, frame `{0x01,0x32, ((ntc_en?1:0) << 2) + mode}` |
| `SetNtcParams` | `0x0133` | **ABSENT from the vendored RadioLib LR2021 driver** | **present** — `src/lr20xx_system.c:151`, impl. `:591-604`, frame `{0x01,0x33, ratio>>8, ratio, beta>>8, beta, delay}`; fields documented at `inc/lr20xx_system.h:528-539` (ratio = 10.9b resistance bias ratio, beta unit 2 K, delay = first-order time-delay coefficient) |
| `SetTcxoMode` | `0x0120` | present — `LR2021_commands.h:54`, `LR2021.h:749` | present — `src/lr20xx_system.c:146` |

The datasheet semantics (quoted in **ADR-042 Addendum A** from
`docs/LR2021_LR2022_LR2012_Datasheet_Rev2.1.pdf`, which is in-tree):

- §1.9.2: the optional XTAL temperature-compensation mechanism measures the XTAL
  temperature and compensates on chip; **the `VTCXO` pin can power an external
  R + NTC** monitoring the XTAL, whose output feeds the chip on pin `NTC`.
- §6.12.1 `SetTempCompCfg` `0x0132`: *"configures the heating compensation block in
  Tx **if an XTAL 32MHz is used**"*; fields `ntc` and `comp_mode(1:0)`.
- Pin 3 = `NTC`. On the owned **plain** NiceRF module the census records
  *"crystal, no TCXO, no NTC"* — so pin 3 is unpopulated and the on-chip engine is
  idle (ADR-042 Addendum A2).

### 1.4 The verification sources, and the cross-check

- **GPS 1PPS** — `docs/analysis/external-clock-and-ocxo.md` §A5: u-blox **MAX-M10S**
  data sheet **UBX-20035208** §1.2 gives `TIMEPULSE` **pin 4**, *"Default 1PPS
  (0.25 Hz to 10 MHz configurable)"*, *"Accuracy of time pulse signal — RMS 30 ns"*;
  the repo already routes it (`docs/adr/108-f33-sx1280-pin-plan.md` — `GNSS_PPS`).
  Note the honest split: the companion analysis
  (`docs/analysis/thermal-and-frequency-drift.md` §3.2, §8 `[1PPS jitter]`) flags the
  per-edge `σ_t` used in the discipline budget as `TODO(unverified)` in-repo. This
  record carries **both** facts and does not resolve them.
- **MS5611** — ADR-029 §D6 selects `MS5611-01BA03` for flight. It is a calibrated
  **pressure and temperature** sensor. The commonly quoted **±0.8 °C** temperature
  accuracy is **not verifiable from this repo** — the TE datasheet is not in-tree;
  `TODO(unverified)`.
- **SX1280 external TCXO** — `docs/analysis/external-clock-and-ocxo.md` §A3: bare
  Semtech IC, **pin 4 = XTA** ("Reference oscillator connection or TCXO input"),
  pin 6 = XTB; `FXOSC` = 52 MHz (§3.7 / Table 3-9). **The premise is corrected
  there:** SX1280 datasheet Figure 14-3 shows **no on-chip TCXO enable** — the TCXO
  gets its own rail, is AC-coupled into XTA, and **DIO3 is merely pulled to
  VDD_RADIO through 0 Ω**. Gating the TCXO therefore requires an **external load
  switch** on that rail, no on-chip provision exists.
- **F33** — `LoRa2021F33-2G4` carries an internal industrial-grade **0.5 ppm TCXO**
  with **no VTCXO pin**; §7 of its datasheet enumerates all 18 pins and there is no
  XTA/XTB/VTCXO. Non-overridable (analysis §A1).

---

## 2. Decision

### D1 — The LR2021's own temperature sensor is the PRIMARY drift instrument, and `TEMP_SOURCE_XOSC` is the source to use, not a board-level proxy

**Decision.** The temperature input to drift compensation is `GetTemp` (`0x0125`)
with `Source = TEMP_SOURCE_XOSC` (`0x01 << 4`, `LR2021_commands.h:250`), read over
SPI from the radio itself.

**Why.** It measures the temperature of the drifting element itself. Every
alternative measures a different node:

- a **board-level NTC** or the ESP32-S3 die sensor (ADR-042 Addendum A6: available,
  `CONFIG_SOC_TEMP_SENSOR_SUPPORTED=y`, unread) sits across an FR4 thermal gradient
  from the crystal;
- the **MS5611** is a different component with its own thermal path (and its own
  reason to stay cold — ADR-029/ADR-042 §D6);
- a **heater/oven** regulates the sensor it installs, not the crystal (ADR-042
  Addendum A3 point 3), and was rejected on energy grounds anyway (§D1 there).

`TEMP_SOURCE_VBE` (`0x00 << 4`) is retained **only** as the general-die-temperature
companion reading, used for the cross-check in (e) and as a plausibility signal —
never as the compensation input.

### D2 — The compensation scheme, in layers

The scheme is an ordered stack. Each layer is useful alone; each later layer
tightens the earlier one.

**(a) Read `TEMP_SOURCE_XOSC` over SPI.**
`GetTemp 0x0125` with a 3-byte command `{0x01,0x25,arg}`, `arg = (source & 0x30) |
(FORMAT_DEG_C << 3) | ((8 + bits) & 7)`, reply 2 bytes; default 13 bits
(§1.1). The reader must **distinguish failure from a valid 0 °C** — RadioLib's
`getTemperature()` returns `0.0f` on *any* error (`LR2021.cpp:987-998`), which is
indistinguishable from a legitimate reading. (Implemented: `§4.2`.)

**(b) Apply a PER-UNIT calibration curve, characterised once on the bench across
−60 °C to +25 °C.**
The curve is `f(T) → Δf/f` in ppm for *that individual radio*, because the crystal's
frequency–temperature characteristic and its turning point are part-specific (the
datasheet's ±10 ppm figure is only characterised over −20…+70 °C — ADR-042 Addendum
A5 — and the mission's −60 °C is outside that window, so no generic figure exists).
Until the bench fills it, the curve is **IDENTITY (0.0 ppm)**: this record
**invents no coefficients**. (Implemented: `§4.3`.)

**(c) Apply the correction — name both available mechanisms, and state the
either/or clearly.**
Two mechanisms exist in the part. They are alternatives, selected per module:

- **c1 — `SetXoscCpTrim` `0x0131`: a STATIC foot-capacitance trim offset.**
  Frame `{0x01,0x31, xta&0x3F, xtb&0x3F, wait}` — verified in both vendored drivers
  (§1.3). This is a trim of the crystal's load capacitance, so it shifts the
  frequency by a *fixed* amount; it is the mechanism for a correction that does not
  need the chip's own loop (e.g. a per-unit offset applied at wake, or a periodic
  trim refreshed from the curve). `TODO(unverified)`: **there is no ppm → trim-code
  mapping in any vendored source** — the codes are raw 6-bit capacitance values. The
  mapping must be measured. (Implemented as an explicit refusing stub: `§4.4`.)
- **c2 — the on-chip NTC path: `SetTempCompCfg` `0x0132` + `SetNtcParams` `0x0133`.**
  Frames verified in the vendored Semtech driver (§1.3); semantics per the datasheet
  (ADR-042 Addendum A2, §6.12.1) which scopes the block to *"if an XTAL 32MHz is
  used"*. It requires a **POPULATED NTC** — a 100 K NTC on pin 3 plus a series R to
  the `VTCXO` rail. On the owned plain module pin 3 is unpopulated, so the engine is
  idle and this path corrects nothing until the part is fitted. `TODO(unverified)`:
  the datasheet scopes it to XTAL; **whether the chip returns a hard error when a
  TCXO was configured is not verified** (the vendored drivers perform no such check).

**THE EITHER/OR, stated plainly:** the on-chip NTC path (c2) applies to
**CRYSTAL-configured modules only** — the block's own precondition is "an XTAL 32MHz
is used". On a module whose reference is a TCXO the block is not the intended path,
and a TCXO-configured module does not need it (see D3). Conversely (c1) is available
wherever the crystal's load capacitance is what sets the frequency, i.e. also the
crystal-configured case. Where neither can be characterised, **the correction is
carried by (d) alone** — the 1PPS-disciplined loop measures the residual instead.

**(d) Verify and discipline in flight with the GPS 1PPS-gated cycle counter.**
A counter of the radio reference is gated between consecutive 1PPS edges; the
fractional error is `Δf/f = (N_measured − f_ref·M) / (f_ref·M)` over an `M`-second
window (ADR-056 §D3; arithmetic and the resolution table in
`docs/analysis/thermal-and-frequency-drift.md` §3.2). This is the **measurement**
that replaces trust in the curve, and it is the provision ADR-056 already ranks
first because it costs **zero grams and zero watts**. (Implemented as a state
machine with its resolution arithmetic: `§4.5`.)

**(e) Cross-check against the MS5611 so a temperature-sensor FAULT IS DETECTABLE
rather than silent.**
The LR2021's `TEMP_SOURCE_XOSC` reading is compared against the MS5611's independent
temperature reading. If they diverge beyond a tolerance, the compensation is
declared **untrustworthy**: telemetry is flagged, the correction is **not** applied
from a suspect temperature, and the 1PPS loop (d) carries the load. A silent
temperature-sensor failure that quietly mis-tunes the carrier is exactly the failure
mode this layer exists to prevent. (Implemented: `§4.6`. `TODO(unverified)`: the
±0.8 °C MS5611 accuracy figure — the datasheet is not in-tree — so the tolerance is
a caller-supplied constant.)

### D3 — Per-radio applicability

| Radio | Reference (per the ADR-056 census and the clock analysis) | Can use the on-chip NTC path (c2)? | Needs it? | Role of the on-board sensor |
|---|---|---|---|---|
| **`LoRa2021F33-2G4`** | internal **0.5 ppm TCXO**, non-overridable; **no** clock pin (analysis §A1) | **NO** — its reference is a TCXO, and `SetTempCompCfg` is scoped to XTAL-configured parts | **NO** — its 0.5 ppm is the margin | `GetTemp` is still readable; log it (telemetry), do **not** tune on it |
| **bare NiceRF LoRa2021** (the default flight radio) | **crystal**, no TCXO, no NTC (census) | **YES in principle** — it is crystal-configured, so the NTC path applies — **SUBJECT to the NTC input pin being broken out** on the module. **This is a BLOCKER, recorded as such** (ADR-042 Addendum A2 `TODO(unverified)`; ADR-056 §4 item 5) | **YES** — this is the real drift gap | `TEMP_SOURCE_XOSC` + per-unit curve + 1PPS discipline — the full stack |
| **`SX1280`** | bare IC; **52 MHz** reference; bare-crystal on the custom standalone boards (ADR-056 §1.3, `firmware/rp2040/src/bench_radio_sx1280.cpp`) | N/A — it has no LR2021 NTC block | Depends on the module | Future-facing: an **external TCXO on XTA pin 4**, gated by an **external load switch** (no on-chip TCXO enable exists — the DIO3 "enable" premise is corrected in the clock analysis §A3); otherwise 1PPS discipline |

The F33's exclusion is a consequence of **the datasheet's own precondition**, not a
limitation of the temperature sensor: the F33's `GetTemp` still works, it simply does
not need compensating. This matters because it stops a future reader from "fixing"
the F33, which has nothing to fix.

### D4 — NON-VOLATILE STORAGE IS REQUIRED for the per-unit calibration curve

**Decision.** The per-unit calibration curve (D2 b) **must be persisted in
non-volatile storage**: it is characterised once on the bench, is specific to one
physical radio, and must survive power cycles and the deep-sleep/burst duty cycle
(ADR-036). The vehicle therefore requires an NVM record per unit holding the curve
(temperature/ppm point pairs) plus its provenance (date, bench reference, module
serial).

**This record deliberately does NOT pick a storage part.** A sibling task is
deciding the board storage; this ADR **references** that decision and states only the
requirement: *persistent, per-unit, written at bench-characterisation time, read at
boot, and validated on load* (the curve must be range- and order-checked, and an
unreadable/corrupt record must degrade to IDENTITY rather than to a wrong
correction). (Implemented: the curve loader validates sortedness and bounds —
`§4.3`.)

### D5 — The bench tests (the gate; design work only, nothing run here)

1. **Cold-soak frequency-offset measurement against a GPS-locked reference.**
   Soak one module at **−60 / −40 / −20 / 0 / +25 °C** (≥ 20 min per step) and
   measure the carrier at the flight channel against a GPS-locked reference,
   computing `Δf/f` in ppm. **This is ADR-042 §D5's deciding number** — the gate that
   says whether any mitigation is needed. It **also pins the °C scale of §1.2**,
   because the reference temperature is known exactly at each step.
2. **Per-unit curve characterisation across the temperature range.**
   Fill the `temp_comp_curve_t` for the unit under test across the same range, at a
   spacing fine enough to capture the crystal's turning point, and write the result
   to the NVM record (D4). *Pass:* the curve reproduces the measured `Δf/f` within
   the measurement's own uncertainty at every node.
3. **1PPS-discipline convergence test.**
   Run the 1PPS → measured `Δf/f` → trim loop with the radio at a known temperature
   offset and log residual ppm vs time. *Pass:* converges below **< 0.05 ppm** inside
   a **≤ 100 s** window and holds (ADR-056 §D6.2). This measurement also supplies the
   missing `σ_t`.
4. **Sensor cross-check validation (new here).**
   Across the same sweep, compare the LR2021 `TEMP_SOURCE_XOSC` reading against the
   MS5611 and against the soak temperature, to (i) set `max_delta_c` for layer (e)
   and (ii) prove that a deliberately induced sensor fault is *detected*. Layer (e)
   is only a fault detector if this test demonstrates it fires.

---

## 3. Relationship to standing decisions

- **ADR-042 §D1 (heater rejected)** — reaffirmed, not re-opened. **§D2 (TCXO first)**
  — reaffirmed and sharpened by D3. **§D3 (`f_set = f_nominal − Δf` at runtime)** —
  **extended**: D2 (d) is a *measured* path to the same correction. **§D6 (MS5611
  heating conflict)** — stands. **Addendum A (the runtime sensor exists; the NTC
  fix; `0x0132`)** — **this record is its implementation** and adds the
  driver-availability matrix (§1.3) and the °C-scale defect (§1.2).
- **ADR-056** — **D1** (no heater for oscillator drift) reaffirmed; **D2** (per-radio
  reference census) used verbatim as D3's input; **D3** (GPS 1PPS is the primary
  provision) re-affirmed and made concrete as layer (d). **ADR-056 §4 item 5**
  (module census: pin 3 / NTC break-out) is carried as an open blocker here, not
  closed.
- **ADR-043** — heating rejected for cold qualification; below-rated parts gated. This
  record adds **no heater** and no part change.
- **ADR-017 / ADR-019 / ADR-021 / ADR-023** — GPS-UTC timing authority; layer (d) is
  additive (it disciplines the *carrier*; they govern the *schedule*) and amends none.
- **ADR-108** — the `GNSS_PPS` route this record's discipline input depends on.
- **ADR-029 §D6** — MS5611-01BA03 is the flight barometer; layer (e) **consumes** its
  temperature reading and requires no change to it.
- **ADR-052** — end-only unbonded cell mount: untouched; nothing here bonds or heats
  the array.
- **ADR-036 / ADR-047** — the deep-sleep and bank figures the heater rejection rests
  on; layer (d) is compatible because it needs no continuous power.

---

## 4. The implementation this record ships (deliverable 2)

The operator's requirement was that this **actually happen**, so the record ships
working code, not a design description. It lives in the RP2040 FLRC bench firmware
tree beside the existing pure modules and the vendored RadioLib, and it is built and
tested by the repo's existing host-test build system.

### 4.1 Files

| File | What it is |
|---|---|
| `firmware/rp2040/src/temp_comp.h` | The API and the **full provenance table** — every constant tied to a vendored-source line, every unverified item marked in place |
| `firmware/rp2040/src/temp_comp.cpp` | The implementation. **Pure C++, no Arduino, no libc/libm** (freestanding-clean) so the same TU cross-compiles for the Cortex-M0+ |
| `firmware/rp2040/host-tests/test_temp_comp.cpp` | **155 host assertions** over packing, conversions, curve behaviour, frame bytes, the unverified-mapping stub, the cross-check and the 1PPS state machine |
| `firmware/rp2040/host-tests/Makefile` | `test_temp_comp` added to the build (one line + one rule) |
| `.gitignore` | the built `test_temp_comp` binary ignored, like its six siblings |

### 4.2 Layer (a) in code — and the failure-vs-0 °C trap

`temp_comp_lr2021_read_deg_c()` / `..._read_xosc_deg_c()` /
`..._read_vbe_deg_c()` build the verified 3-byte GetTemp frame, read the 2-byte
reply through a caller-supplied transport, and convert with the **signed-capable**
path. On failure they return a distinct negative `TEMP_COMP_ERR_*` and **do not
write the output** — deliberately, because RadioLib's `getTemperature()` returns
`0.0f` on error and `0.0 °C` is a perfectly valid reading, so a caller cannot tell
success from failure. A unit test asserts both halves of that contract.

### 4.3 Layer (b) in code — the curve, identity until the bench fills it

`temp_comp_curve_t` holds up to 16 `{temp_c, ppm}` points. `_init_empty` /
`_is_identity` / `_add_point` (ascending insert, duplicate rejected) / `_load`
(validated: sorted, bounds) / `_correction_ppm` (piecewise-linear, clamped outside
the characterised span). An empty curve returns **exactly 0.0 ppm**; a test asserts
that identity holds at −60, 0 and +25 °C, so no coefficient can be invented.

### 4.4 Layer (c) in code — real frame builders, and an honest refusing stub

`temp_comp_build_xosc_cp_trim_frame()` and
`temp_comp_build_temp_comp_cfg_frame()` / `temp_comp_build_ntc_params_frame()` emit
the **verified** wire frames (§1.3) and are asserted byte-for-byte by the tests.
`temp_comp_ppm_to_xosc_cp_trim()` — the missing ppm → trim-code mapping — **returns
`TEMP_COMP_ERR_UNVERIFIED_MAPPING` and writes nothing, on purpose**: it exists so the
call site is explicit and testable rather than silently absent, and it **must not**
be replaced by a guessed formula. `temp_comp_apply_correction()` orchestrates the
hook: identity curve ⇒ a clean no-op (`TEMP_COMP_OK`, zero correction); characterised
curve ⇒ the correction is reported **and** the unverified status returned, so the
caller logs and does not fly on it. Tests assert all three outcomes.

### 4.5 Layer (d) in code — the 1PPS gate and its arithmetic

`temp_comp_pps_resolution_ppm()` = `1e6 / (f_ref · M)` with the arithmetic in the
comment (`f_ref` = 32 MHz for the LR2021, 52 MHz for the SX1280, both named
constants); `_resolution_ppb()` is the integer form; `_frac_error_ppm()` computes
`1e6 · (N − f_ref·M)/(f_ref·M)`. `temp_comp_pps_gate_t` is a rolling
windowed state machine (`begin` / `reset` / `on_pps`), with a wrap-guard that rejects
a delta smaller than half a window rather than reporting a missed counter wrap as a
huge frequency error. Tests pin 0.03125 ppm at 32 MHz/1 s, the integer ppb values,
±1 ppm exact cases, and a two-window run. `TODO(unverified)` **in the header**: the
hardware path that actually counts the reference between PPS edges (which timer/PIO
peripheral; whether the discipline edge is `GNSS_PPS` on GPIO21 on this board) is not
confirmed — this is the state machine and its arithmetic only.

### 4.6 Layer (e) in code — the cross-check

`temp_comp_crosscheck()` returns the delta, the tolerance actually used (clamped up
to a sanity floor), and a `fault` flag; **NaN in either input reads as a fault**, so a
broken sensor cannot look healthy. Tests cover in-window, out-of-window, the strict
boundary, the floor clamp, and NaN.

### 4.7 Build and test evidence (actual, on this host)

```
$ make -C firmware/rp2040/host-tests
  g++ -std=c++17 -Wall -Wextra -Werror -O2 -g -I../src \
      -o test_temp_comp test_temp_comp.cpp ../src/temp_comp.cpp -lm
  -> exit 0.  All 7 host-test binaries build clean (the 6 pre-existing ones too).

$ ./firmware/rp2040/host-tests/test_temp_comp
  -> "test_temp_comp: all checks passed"   (155 CHECK assertions, exit 0)

$ arm-none-eabi-g++ -std=c++17 -Wall -Wextra -Werror -O2 -mcpu=cortex-m0plus \
      -mthumb -ffreestanding -fno-exceptions -fno-rtti \
      -I firmware/rp2040/src -c -o temp_comp_m0plus.o firmware/rp2040/src/temp_comp.cpp
  -> exit 0, text 2140 / data 0 / bss 0 bytes.
```

The Cortex-M0+ freestanding cross-compile is the proof that this is real firmware and
not host-only code: the module has **no** libc/libm dependency, so it links into an
RP2040 image as-is. It is intended to be added to a target's
`build_src_filter` (`+<temp_comp.cpp>`) — or the CMake source list — when it is wired
to hardware; that wiring is **not** done here and is not claimed (nothing is flashed).

---

## 5. Open items

1. **NTC input pin break-out on the owned bare NiceRF LoRa2021.** The on-chip NTC
   path (c2) is only usable if pin 3 is brought out on the module's castellations
   and an NTC can be fitted at the crystal. **This is a blocker for c2**, not a
   detail. *Settle:* module mechanical drawing or a deshield photo (ADR-042 Addendum
   A2; ADR-056 §4 item 5).
2. **The exact `SetXoscCpTrim` / `SetTempCompCfg` / `SetNtcParams` interface values.**
   `TODO(unverified)`: the ppm → `0x0131` trim-code mapping (absent from every
   vendored source — the codes are raw 6-bit capacitances); the `comp_mode` semantics
   (0x0 disabled / 0x1 relative / 0x2 absolute per the datasheet field list, but
   unvalidated on silicon); and the `ntc_r_ratio` / `ntc_beta` / `delay` values for
   our specific NTC (the Waveshare variant's NTC is a 100 K with **beta unverified,
   ~4250 K assumed** — ADR-042 Addendum A2).
3. **The calibration curve itself.** The curve is empty by construction and needs the
   operator's bench work (D5.2) before any correction exists. Until then the module
   is identity and correct in that state.
4. **The NVM part.** A sibling task decides the board storage; this record states only
   the requirement (D4) and references that decision rather than picking a part.
5. **The °C scale reconciliation.** RadioLib's unsigned `raw/320.0` vs the Semtech
   header's byte0-integer / byte1-fractional layout (§1.2). They cannot both be
   right, and RadioLib's path cannot express negative temperatures. *Settle:* the D5.1
   cold-soak, whose absolute temperatures are known.
6. **Whether `SetTempCompCfg` hard-errors when a TCXO was configured.** The datasheet
   scopes the block to "an XTAL 32MHz"; whether the chip *rejects* the command on a
   TCXO-configured part is `TODO(unverified)` — the vendored drivers perform no such
   check, and no owned module can be tested until the census question (item 1's
   sibling: which reference the four owned plain modules actually carry) is closed.
7. **The 1PPS hardware counting path.** Which timer/PIO peripheral counts the
   reference between PPS edges, and whether the discipline edge is `GNSS_PPS` on
   GPIO21 on the flight board, is unconfirmed (marked in the header).
8. **The MS5611 ±0.8 °C temperature accuracy.** The commonly quoted figure is not
   verifiable from this repo (the TE datasheet is not in-tree), so the layer-(e)
   tolerance remains a caller-supplied constant until it is sourced or measured.
9. **The SX1280 external-TCXO detail.** The premise that DIO3 provides an on-chip
   TCXO enable is **corrected** in the clock analysis §A3 — there is none, and the
   TCXO rail needs an external load switch. The exact TCXO part, its rail and the
   Figure 14-3 component values (not legible in the text layer) remain open, as does
   the datasheet's own 32 MHz vs 52 MHz `FXOSC` discrepancy.
10. **`σ_t` for the 1PPS edge.** The companion analysis flags it `TODO(unverified)`
    in-repo while the clock analysis quotes the u-blox "RMS 30 ns" figure; D5.3
    supplies the measured value. Carried without resolving.

---

## 6. Consequences

**Positive**

- The drift instrument is now **named and justified**: `TEMP_SOURCE_XOSC`, because it
  measures the node that drifts. The alternatives are each given a reason to be
  secondary, so the choice does not have to be re-derived.
- The scheme is **layered and each layer is independently useful**, so a failure of
  any one (no NTC fitted, no curve yet, a dead sensor) degrades the system rather
  than invalidating it — and layer (e) makes a sensor fault **loud**.
- The per-unit curve and its NVM requirement are explicit, so the bench work has a
  defined destination and no curve is ever invented.
- **There is working, tested, cross-compiled code** for the whole stack, with two
  genuine defects found in the process (the °C-scale disagreement; the
  failure-as-0 °C trap) written down instead of absorbed.
- The follow-on hardware path (SX1280 external TCXO on XTA + load switch) is
  recorded with its premise corrected, so it is not "fixed" later by inventing an
  on-chip enable that does not exist.

**Costs (accepted)**

- Firmware owes the bench-characterised curve, the NVM record, and the real hardware
  wiring of the 1PPS counter (only the state machine and arithmetic exist today).
- The bare-LoRa2021 drift gap is closed by **an NTC that is not yet fitted, on a pin
  that may not be broken out**, **a curve that is not yet measured**, or **a 1PPS loop
  that is not yet wired** — three tasks, not a heater.
- The F33 and the SX1280 remain per-radio problems, as ADR-056 already records.

---

## 7. What would falsify this

- **The cold-soak shows the residual drift is already inside the carrier-offset
  budget** (ADR-042 §D5 `Δf_max ≤ 0` for the chosen BW/SF): then the whole scheme
  becomes optional — layers (b) and (c) would be dropped and (e) kept only as
  telemetry. The choice of `TEMP_SOURCE_XOSC` as the instrument would still stand.
- **The bench measurement shows `TEMP_SOURCE_XOSC` does not track the crystal's own
  frequency–temperature curve** better than `TEMP_SOURCE_VBE` or the MS5611: that
  would falsify D1's central claim (that this source measures the drifting node) and
  force the instrument choice to be re-made on measurement.
- **Pin 3 is confirmed not broken out** on the owned module *and* no alternative NTC
  node can be reached: c2 is then unavailable outright and only (c1) + (d) remain —
  which does not weaken (d), the primary provision.
- **The °C scale cannot be resolved by the cold-soak** (e.g. the two drivers' reply
  lengths or formats turn out to differ in a way that needs the datasheet): the
  reader's conversion would then be blocked on a datasheet clarification, and this
  record's §1.2 open item would escalate to a hardware-vendor question.
- **The 1PPS loop cannot converge** below the crystal's own drift (measured `σ_t` too
  poor, or the counter path unavailable): layer (d) drops in rank and (c) becomes
  load-bearing — reopening the NTC/pin question as a priority rather than an open
  item.

---

## 8. Notes

- **Why one record and not two.** The instrument choice, the layered scheme, the NVM
  requirement, the bench gate and the implementation are one decision — *how this
  vehicle reads its own crystal's temperature and turns that into a frequency
  correction* — and splitting them would let the implementation drift from the
  reasoning that produced it. The provenance table lives in the code itself (§4.1),
  which is the strongest available guarantee that they stay together.
- **Nothing is superseded by this record.** ADR-042 and ADR-056 are extended, not
  replaced, and neither is edited here.
- **No hardware is ordered and nothing is flashed by this record.** It is design and
  firmware work only.
