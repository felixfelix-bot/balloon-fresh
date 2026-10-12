# Thermal and frequency drift — is an oscillator heater needed, and what is the correct provision?

**Status: this is an ANALYSIS, not a decision.** It assembles evidence, does arithmetic, and
ranks options. The *decision* it feeds is recorded separately in
`docs/adr/056-thermal-and-frequency-drift.md`. Nothing here is a fabrication authority and no
hardware is ordered by it.

- Date: 2026-10-07
- Author: Hermes subagent, branch `analysis/thermal-and-frequency-drift`
- Question answered (operator, verbatim intent): *"Do you already have a heaters provision for
  the oscillator of the radio so that we don't have frequency drift? If not, please include that
  in the plan as well."*
- Repo base: `github/main` @ `61e932b`
- Companion arithmetic: `docs/analysis/thermal_frequency_drift_model.py` (run it; every number
  below is reproduced there)
- Every figure is either cited to a repo source, derived by a shown formula, or marked
  `TODO(unverified)` / `ESTIMATE`. No datasheet value is invented.

---

## 0. Answer in one line

**There is no heater provision, there should not be one for oscillator drift, and what replaces
it is already on the vehicle: the module TCXOs (0.5 ppm on the F33; required on any bare-crystal
radio that flies as a reference) plus GPS 1PPS discipline, which costs zero grams and zero
watts.** A heater that tried to hold a crystal at its turning point fails the arithmetic by
**2× against the daylight average, 8000× against the night anchor, and 866× against the entire
usable supercapacitor bank** (at the repo's own assumed thermal resistance).

---

## 1. What the design already has — per radio

The vehicle carries four RF/GNSS references. Only some of them are drift-critical, and only some
carry a compensated reference today. This census is the part of the record that ADR-042 does not
contain.

| Radio / reference | Reference type today | Drift-critical? | Source |
|---|---|---|---|
| **LoRa2021F33-2G4** (the HP "V2" module; v9 Site A variant) | **Built-in industrial TCXO, 0.5 ppm** | Yes | `docs/V9-RADIO-SITE-MATRIX.md` §2 (TCXO row) · `docs/LR2021-LESSONS-2026-09.md` line 23 · `docs/DUAL-VARIANT-DESIGN.md` line 78 · `docs/F33-MODULE-PLAN.md` lines 18, 44 |
| **bare LoRa2021** (the LP module; **default** population at BOTH v9 sites) | **Crystal only — no TCXO, no NTC** | Yes — it is the default flight radio | `docs/V9-RADIO-SITE-MATRIX.md` §2 · `docs/LR2021-LESSONS-2026-09.md` line 22 · `docs/V9-RADIO-SITE-MATRIX.md` §5 ("TCXO vs crystal drift" test) |
| **SX1280** (ranging radio, 2.4 GHz) | **52 MHz reference**; module = TCXO, custom standalone board = **bare 52 MHz crystal** | Yes if used as a timing freference; yes for ranging | `firmware/rp2040/src/bench_radio_sx1280.cpp:59` (`#define XTAL_MHZ 52.0f`) · `docs/FLRC-RANGE-DUAL-PLATFORM-ACTION-PLAN.md` lines 29, 58, 82, 103 |
| **ESP32-S3** (MCU) | Internal RC / own crystal, not the radio reference | No — the MCU clock does not set the RF carrier | — |
| **MAX-M10S** (GNSS) | Its own receiver reference (module-integrated); supplies **1PPS** | It *is* the reference, not a load | `docs/adr/108-f33-sx1280-pin-plan.md` line 38 (`GNSS_PPS`, MAX-M10S) · `docs/adr/029-dual-band-flight-board.md` §"Position / time" |

### 1.1 The facts, stated plainly

1. **The F33 module already has the correct part inside it.** A TCXO *is* an oven-controlled
   crystal at milliwatt scale — it holds only a tiny thermal mass, not the board. ADR-042 §D2
   already records this. On the F33 the drift question is already answered by the part.
   `docs/F33-MODULE-PLAN.md` line 115 records that the VTCXO decoupling cap **C3 was removed**
   because the F33's TCXO is internal — i.e. the design already banked the TCXO.
2. **The bare LoRa2021 is the default flight radio and has NO TCXO.** `docs/V9-RADIO-SITE-MATRIX.md`
   §6 recommends default-populating the LOW-POWER (bare) part at both sites, and its open item
   **O2** is *"plain-module temperature drift (no TCXO/NTC) at −44…−60 °C"*. So the vehicle's
   default RF radio is exactly the drifted one. This is the real gap.
3. **The LR2021 chip provides the escape hatch for a bare module.** The chip has an on-die
   temperature-compensated crystal loop: `SetTempCompCfg` (`0x0132`) + `SetNtcParams` (`0x0133`),
   with an **NTC on pin 3** and a **VTCXO rail** for the sensor. ADR-042 Addendum A2 documents
   this from the in-tree Semtech datasheet (`docs/LR2021_LR2022_LR2012_Datasheet_Rev2.1.pdf`,
   §6.12, §1.9.2). On the plain NiceRF module the NTC is **not fitted** (`docs/LR2021-LESSONS-
   2026-09.md` line 22: *"crystal, no TCXO, no NTC"*), so the on-chip loop is open.
4. **The SX1280 must be a TCXO-bearing module if it is a flight timing reference.** The repo's own
   FLRC work separates the two cases explicitly: the E80 kit has a *"TCXO (module-fitted)"* while
   the RP2040 standalone boards *"use a 52 MHz crystal, not TCXO"*, and it flags the resulting
   **clock-source mismatch** (`docs/FLRC-RANGE-DUAL-PLATFORM-ACTION-PLAN.md` line 103). The bench
   firmware hard-codes `XTAL_MHZ 52.0f`, so the synthesizer maths is right for a 52 MHz reference
   either way — but a bare crystal is uncompensated.
5. **The GPS is the zero-cost authority.** A MAX-M10S is on the board with its **1PPS** routed to
   GPIO21 (`docs/adr/108-f33-sx1280-pin-plan.md` line 38). Four accepted ADRs already make GPS UTC
   the timing authority for the radio schedule (ADR-017, ADR-019, ADR-021, ADR-023). None of them
   uses 1PPS to *measure the radio reference's frequency error* — that is the new, free provision
   in §3.2.

### 1.2 A module-census conflict that must be flagged, not resolved here

Two in-repo statements about module-level TCXO/VTCXO disagree and are **not** reconciled by this
analysis:

- `docs/assets/lr2021/README.md` lines 18, 41, 48–67 describe a **"0.5 PPM" TCXO "onboard"**,
  **pin 13 = VTCXO**, *"Controlled power output for TCXO … Auto-on during TX/RX"*, and instruct
  *"leave floating"* for a bare module.
- `docs/LR2021-LESSONS-2026-09.md` line 22 says the **plain** NiceRF module has **"no TCXO, no
  NTC"**; line 23 gives the F33 the 0.5 ppm TCXO. `docs/F33-MODULE-PLAN.md` line 18 says the F33
  TCXO is **"internal (no VTCXO pin)"**. `docs/DUAL-VARIANT-DESIGN.md` line 78 says the **bare**
  module uses **"External (VTCXO pin)"** and the F33 is **"Built-in 0.5ppm"**.

The VTCXO pin is a **chip** feature (LR2021 pin 13 powers an *external* TCXO/NTC); the
`docs/assets/lr2021/README.md` "onboard 0.5 ppm" line reads like a generic attribution rather than
the NiceRF plain module. **This analysis treats the LESSONS/DUAL-VARIANT census (plain = crystal,
F33 = internal 0.5 ppm TCXO) as the operative one and marks the README as `TODO(unverified)` to be
reconciled against the vendor module mechanical drawings.** It does not change any conclusion
below, because both readings agree the plain module is the drifted part.

### 1.3 One more repo conflict (carrier-reference frequency)

The LR2021 datasheet's crystal is **32 MHz** (`docs/adr/042-thermal-drift-strategy.md` Addendum A2,
§1.9.2 *"32MHz Crystal"*; `docs/radio-config-comparison.md` line 48 *"0.0 V (disabled → 32 MHz
XTAL)"*). `docs/SDR-HANDOVER.md` line 60 states *"The LR2021 uses a 52 MHz XTAL"*.
**52 MHz is the SX1280's reference** (bench code `bench_radio_sx1280.cpp:59`), not the LR2021's.
This analysis uses **32 MHz for the LR2021/LR2021F33 synthesizer arithmetic and 52 MHz for the
SX1280**, and marks the SDR-HANDOVER line as a probable cross-radio conflation →
`TODO(unverified)`.

---

## 2. The heater arithmetic — verdict

A heater must hold a temperature **differential continuously, including through the night**,
because the cold is ambient and the night is unheated. In steady state:

```
P_heater = G * delta-T
```

where `G` is the package-to-ambient thermal **conductance**. (ADR-042 §D1 writes the same law as
`P = delta-T / R_thermal`; `G = 1/R_thermal`.) For OCXO-class stabilisation the crystal must be
held at its **turning point, ≈ +25 °C** (`ESTIMATE` — AT-cut turning point), from a stratospheric
ambient of **−50 to −56 °C**. The task states the span as **an 80 K rise**; the exact band gives
`25 − (−56) = 81 K` down to `25 − (−50) = 75 K`, so **80 K is used as the headline**.

**G is not measured anywhere in the repo.** ADR-042 §D1 assumes `R_thermal ≈ 100 K/W`
(`G = 10 mW/K`) and marks it `TODO(unverified)`; ADR-043 §"Energy arithmetic" makes the same
assumption. The `G` values below are therefore **ESTIMATES**. The point of showing four of them is
that **the verdict does not depend on which one is right** — every plausible `G` fails:

| G (mW/K) | P = G·ΔT (W) | × the 0.388 W daylight average | % of the 7.2 W peak | night energy, 10 h (kJ) | × the 33.264 J bank |
|---:|---:|---:|---:|---:|---:|
| 3 (R = 333 K/W, well-insulated small package) `ESTIMATE` | **0.240** | 0.62× | 3.3 % | 8.640 | **260×** |
| **10 (R = 100 K/W — the repo's own assumption)** `ESTIMATE` | **0.800** | **2.06× — FAILS** | 11.1 % | 28.800 | **866×** |
| 30 (R = 33 K/W, typical small insulated enclosure) `ESTIMATE` | **2.400** | **6.19× — FAILS** | 33.3 % | 86.400 | **2597×** |
| 100 (R = 10 K/W, unsealed board-scale — ADR-042's falsify bound) `ESTIMATE` | **8.000** | **20.6× — FAILS** | 111 % (exceeds the peak) | 288.000 | **8658×** |

### 2.1 Run-time against the fitted bank

The usable bank is **33.264 J** (ADR-047 §3.2 / ADR-054 §2.5: 3.3 F, 5.4 → 3.0 V; the accepted
1.65 F variant is 16.632 J):

```
G =  3 mW/K -> P = 0.240 W -> t = 33.264 J / 0.240 W =  138.6 s   (16.632 J:  69.3 s)
G = 10 mW/K -> P = 0.800 W -> t = 33.264 J / 0.800 W =   41.6 s   (16.632 J:  20.8 s)
G = 30 mW/K -> P = 2.400 W -> t = 33.264 J / 2.400 W =   13.9 s   (16.632 J:   6.9 s)
G =100 mW/K -> P = 8.000 W -> t = 33.264 J / 8.000 W =    4.2 s   (16.632 J:   2.1 s)
```

**Even the most optimistic estimate (G = 3 mW/K) drains the entire usable bank in ~139 s.** That
is not a night; it is not even one LoRa SF12 burst cycle.

### 2.2 The arithmetic against the operator's own four numbers

At the repo's own `G = 10 mW/K`:

```
P_heater                     = 0.800 W
  / array average 0.388 W    = 2.06x   -> the heater alone exceeds the whole daylight average
  / night anchor 100 uW      = 8,000x
night energy = 0.800 W x 10 h x 3600 = 28,800 J
  / usable bank 33.264 J     = 866x    -> FAILS by 866x
  ADR-036 night budget (100 uW x 10 h = 3.6 J) -> the heater is 8,000x it
```

Against the **7.2 W peak** the heater is 11 % at G = 10 mW/K and **111 % at G = 100 mW/K** — a
heater can exceed the array's own peak, which the array delivers only in direct sun and cannot
deliver at night at all.

### 2.3 Verdict

**An OCXO-class heater is NOT viable on this vehicle.** It fails by **2×** against the daylight
average, **8000×** against the night anchor, and **866×** against the entire usable supercapacitor
bank — and it fails at *every* plausible `G`. Three structural reasons compound the energy
failure, all already recorded in ADR-042 §A3:

1. A **heat-only** loop's setpoint must exceed the hottest ambient it meets, so the *lift* (≈ 80 K),
   not the setpoint, is what the bank pays for.
2. A *controlled* heater needs the **MCU awake**, contradicting ADR-036's mandatory night deep
   sleep.
3. The loop controls the **wrong node** — a board heater under the module warms the board, not the
   crystal; and it warms the MS5611 barometer, corrupting altitude telemetry (**ADR-042 §D6**).

**The heater that already exists at the right scale is the one inside a TCXO**, because a TCXO
holds a crystal's micro-thermal mass instead of the whole board's.

---

## 3. The correct provision, ranked

### 3.1 Rank 1 — TCXO where the radio needs one

| Radio | Reference today | Action to reach a compensated reference |
|---|---|---|
| **F33-2G4** | built-in 0.5 ppm TCXO | **None.** Already correct; C3 already removed (`docs/F33-MODULE-PLAN.md:115`). |
| **bare LoRa2021** (default flight radio) | crystal, no TCXO, no NTC | (a) fly the **F33** where the link needs it, **or** (b) close the chip's own loop with a **100 K NTC on pin 3** + series R to the VTCXO rail (ADR-042 Addendum A2, `SetTempCompCfg 0x0132`) — one component, microwatt bias, on-chip correction, no awake MCU. `TODO(unverified)`: whether pin 3 is broken out on the NiceRF module's castellations (needs the module mechanical drawing or a deshield photo). |
| **SX1280** | module TCXO **or** bare 52 MHz crystal | **Require a TCXO-bearing module** whenever the SX1280 is a flight reference; a bare crystal is uncompensated. `TODO(unverified)`: the exact SX1280 module datasheet's TCXO control pin (RadioLib's SX1280 uses DIO3 for TCXO enable; the repo does not read/pin this). |
| **MAX-M10S** | GNSS receiver's own reference | **None** — it is the authority, and it supplies 1PPS. |

The TCXO path is first because it is **zero firmware, zero characterisation, and consumes
milliwatts inside the part instead of watts on the board**. Where a bare module must fly, the
NTC-on-pin-3 fix is the *cheap hardware equivalent*: it corrects **frequency**, not temperature,
and needs no continuous power to fight a gradient.

### 3.2 Rank 2 (the headline provision) — GPS 1PPS discipline: zero grams, zero watts

**This provision is the answer to the operator's question that ADR-042 does not contain.** It costs
**no grams and no watts** — the GNSS receiver is already on the board, drawing its 25 mA tracking
current for position/telemetry regardless, and its 1PPS output is already routed
(`docs/adr/108-f33-sx1280-pin-plan.md:21 GNSS_PPS → GPIO21`).

**How it works, concretely.**

1. **Measure.** Gate a counter of the radio reference's clock cycles between two consecutive 1PPS
   rising edges. The counted number should be exactly `f_ref × 1 s`. The fractional error is
   `Δf/f = (N_measured − N_ideal) / N_ideal`.
2. **Average.** Accumulate over an `M`-second window (count over `M` PPS intervals) to push the
   resolution below the synthesizer's trim granularity.
3. **Correct.** Write the measured `Δf/f` into the radio's frequency synthesizer as a trim, so the
   carrier is what the channel plan expects. This is exactly the `f_set = f_nominal − Δf(T)` step
   ADR-042 §D3 specifies — 1PPS discipline supplies `Δf` by **measurement** instead of by a
   pre-characterised `f(T)` table. Alternatively (or additionally) hold the tick as a disciplined
   time base for the TDM schedule, which is what ADR-017/019/021/023 already do with GPS UTC.

**Counting resolution** (`Δf/f = 1/(f_ref·T)` — pure arithmetic, no datasheet):

| window T | LR2021 @ 32 MHz | SX1280 @ 52 MHz |
|---:|---:|---:|
| 1 s | 0.03125 ppm | 0.01923 ppm |
| 10 s | 0.00312 ppm | 0.00192 ppm |
| 100 s | 0.00031 ppm | 0.00019 ppm |
| 1000 s | 0.00003 ppm | 0.00002 ppm |

**The real limit is the 1PPS edge noise, not the counter.** If a 1PPS edge has jitter σ_t then the
per-second fractional error is `σ_t / 1 s`, and averaging `M` seconds reduces it to
`σ_t / (1 s · √M)`:

| σ_t \ M | 10 s | 100 s | 1000 s |
|---:|---:|---:|---:|
| 30 ns | 0.0095 ppm | 0.0030 ppm | 0.0010 ppm |
| 100 ns | 0.032 ppm | 0.010 ppm | 0.0032 ppm |
| 1 µs | 0.32 ppm | 0.10 ppm | 0.032 ppm |

`σ_t` is **`TODO(unverified)`** — the MAX-M10S/MAX-M10S-class 1PPS jitter is not in the repo, and
this analysis does not invent it. The table lets the operator read the achievable figure once the
1PPS spec or a bench measurement supplies `σ_t`. **Even the pessimistic 1 µs row reaches 0.1 ppm in
a 100 s window** — the same order as the F33's TCXO, and better than the plain crystal's
`±10 ppm over −20…+70 °C` (`docs/adr/042-thermal-drift-strategy.md` Addendum A5).

**The correction is representable in the synthesizer.** The LR2021/SX1280 set the carrier by
`frf = f_rf · 2^18 / f_xtal`, so one LSB of the 18-bit divider is `f_xtal / 2^18` at the RF
frequency:

| radio | LSB at 433 MHz | 868 MHz | 2.4 GHz |
|---|---:|---:|---:|
| LR2021 (32 MHz) | 0.2819 ppm | 0.1406 ppm | 0.0509 ppm |
| SX1280 (52 MHz) | 0.4581 ppm | 0.2285 ppm | 0.0827 ppm |

So the synthesizer can be trimmed at 0.05–0.28 ppm granularity at 2.4 GHz/sub-GHz — **finer than
the plain crystal's error and comparable to a TCXO** — while the 1PPS measurement resolves
0.003–0.03 ppm. **Achievable correction: bring a bare-crystal radio's residual frequency error from
the uncompensated cold-soak figure down to the 0.01–0.1 ppm order given a 10–100 s window, at zero
mass and zero added power.**

**Consistency with the existing phase/time-sync ADRs — no amendment needed.**

- **ADR-017** (*Phase Synchronization via Independent Reference Clocks*) already computes sweeping
  phase from **GPS UTC** on the TX board, and states its own RP2040 crystal bound of `<10 ppm`
  (invariant 5). 1PPS discipline *tightens* that bound; it does not contradict the architecture.
- **ADR-019** (*GPS-Synchronized Mode Switching*) already wires **PPS → GP14** for *"microsecond
  accuracy"* — the hardware precedent for using 1PPS as a disciplined edge.
- **ADR-021** (*Absolute UTC Phase Sync*) already makes GPS UTC authoritative and continuous.
- **ADR-023** (*TX Full Autonomy*) already makes GPS the sole authority, no laptop, no `SET_TIME`.

All four constrain **time-of-day / schedule** sync; none constrains the **radio carrier frequency**.
Applying 1PPS to the carrier is therefore **consistent and additive** — it needs a **new** record
(this analysis's ADR) but amends none of them. The one relationship that *is* an amendment is to
**ADR-042 §D3**: 1PPS discipline is a *measured, closed-loop* implementation of D3's
"apply `f_set = f_nominal − Δf` at runtime", so it **extends D3** (adding a second, no-table path to
the same correction) while leaving D1 (heater rejected) and D2 (TCXO first) intact.

### 3.3 Rank 3 — Passive mitigation (secondary, not the fix)

- **Insulation / thermal mass / mounting the reference away from the coldest surface.** ADR-043
  §"Per-component verdict" already rules insulation out as the *night* fix (night draws µA, so
  insulation buys almost nothing at steady state). For the **crystal**, passive measures likewise
  cannot hold +25 °C; they can only (i) slow the rate of change and (ii) site the reference nearer a
  self-heating node (the ESP32-S3, ~240 mA-class peaks) so its steady state is a few K warmer.
- **A prior workstream already reached the same conclusion from the other direction.** The stale
  branch `adr/thermal-drift-strategy` (now consolidated into `main` as commits `fa45752`/`7b0dcb9`/
  `da3ba7c` → see §5) and its ADR-042 rank TCXO > NTC > firmware pre-distortion > channel plan, and
  explicitly place passive measures below all of them.
- **Conflict with ADR-052.** The cell-mount rule is **end-only, no adhesive bond, cells free to
  move under thermal cycling** (`docs/adr/052-cell-mounting-end-only.md` §2.1). Any "pot it in
  thermal mass" instinct for the *array* is directly contrary to that decision; passive mitigation
  must be applied to the **electronics enclosure only**, never by bonding the cells.

### 3.4 Rank 4 — a heater, and only if the arithmetic justified it

It does not (§2). The only *function* a heater could ever serve on this vehicle is an **adjacent**
one, not oscillator drift — keeping a **below-rated part** above its minimum (see §4.1). That case
also fails the arithmetic and is answered by part selection (ADR-043 decision 2), not heating.

---

## 4. Adjacent thermal needs that are NOT oscillator drift

A heater could in principle be justified here, so each is costed honestly. None survives.

### 4.1 The rating gap — every verified semiconductor is below the −60 °C design case

ADR-054 open item 2 and `docs/analysis/array-topology-fault-tolerance.md` §9.5 record it: **every
verified semiconductor in the array work is rated −55 °C ambient (diodes) or −40 °C (all
converters) against a −60 °C design case.** ADR-043 extends this board-wide: the ICs/modules sit
**20 K** below the common −40 °C rating, and (before hardening) the passives ~5 K below a guessed
−55 °C. Cost to *hold* a temperature from a −56 °C ambient (`P = G·ΔT`):

| target | ΔT | G = 10 mW/K | G = 30 mW/K | G = 100 mW/K |
|---|---:|---:|---:|---:|
| **−40 °C** (rescues the −40 °C-rated parts) | 16 K | **0.160 W** | 0.480 W | 1.600 W |
| **−20 °C** (comfortable margin) | 36 K | **0.360 W** | 1.080 W | 3.600 W |
| 0 °C | 56 K | 0.560 W | 1.680 W | 5.600 W |

**Even the cheapest cell fails.** Holding the electronics at −40 °C costs **0.160 W = 41 % of the
entire 0.388 W daylight average**, and at night the same 0.160 W for 10 h is
`0.160 × 36 000 = 5 760 J = 173× the 33.264 J usable bank`. Holding −20 °C costs **0.360 W = 93 % of
the daylight average** (G = 10 mW/K) to **3.600 W** (G = 100 mW/K, half the array's 7.2 W peak) and
**1 296×** the bank over a 10 h night. So the rating gap is a **part-selection / qualification
problem, not a heating problem** — exactly ADR-043 decision 2.

### 4.2 Supercapacitor behaviour at cold — capacitance loss and ESR rise

ADR-006/ADR-036 leave the cold behaviour unmeasured: ADR-036's own open item is *"Cold
characterisation at −60 C — NOT done … capacitance loss and ESR rise"*, and ADR-047 §line 277
repeats it. **This analysis does not invent a cold ESR or a cold capacitance figure.** It shows the
sensitivity so the operator can read the consequence once the bench data lands.

**ESR rise** (multiplicative factor `k` vs the 25 °C value; the bank's per-cell ESR is 0.10 Ω per
ADR-047's appendix). Under the 1.2 A F33 TX pulse:

| ESR factor k | ΔV_ESR, 1.65 F bank (2 cells in series) | ΔV_ESR, 3.3 F bank (1 cell) | % of the 2.4 V headroom (5.4 → 3.0 V) |
|---:|---:|---:|---:|
| 1 | 0.240 V | 0.120 V | 5 % |
| 3 | 0.720 V | 0.360 V | 15 % |
| 5 | 1.200 V | 0.600 V | 25 % |
| 10 | 2.400 V | 1.200 V | 50 % |

The stored **energy is unchanged by ESR**; ESR reduces the **voltage the converter sees under
load**. The bank at 5.4 V has 2.4 V of headroom to the 3.0 V floor; the ESR drop eats into it. The
failure condition is roughly **k ≈ 10 on the doubled bank** (ESR drop = 1.2 V = 50 % of headroom,
plus the burst droop) — i.e. a rise by an order of magnitude would challenge a single burst.

**Capacitance loss** scales usable energy linearly, `E_usable(c) = c × 33.264 J`:

| C retained | usable energy | run-time at the 6.1495 W radio peak |
|---:|---:|---:|
| 100 % | 33.26 J | 5.41 s |
| 90 % | 29.94 J | 4.87 s |
| 75 % | 24.95 J | 4.06 s |
| 50 % | 16.63 J | 2.70 s |

Even a 50 % capacitance loss still holds **2.7 s** at the radio's worst-case 6.15 W draw — above
the burst requirement — so cold capacitance loss alone is unlikely to be fatal, whereas a large ESR
rise is the quantity to watch. **Both must be measured; both are ADR-036/047 open items; neither is
a heating problem** (ADR-043 already shows warming the storage costs ~4× the usable budget).

### 4.3 Cell and bond thermal cycling — the observed cracking mechanism

The balloon-world cracking mechanism is **differential thermal contraction** between the assembly
temperature and the flight cold, not trapped air: the community's answer is to *not bond* and let
the cells move (`docs/analysis/pico-balloon-solar-survey.md` §4.3, §6; KC9IKB firsthand: *"the
temperature change between the assembly area and the cold … may crack a cell"*). ADR-052 §2.1
therefore decides **end-only mounting, no adhesive bond, cells free to move**.

**A heater is not the mechanism's fix.** The differential contraction is between the cell and its
**tab/joint**, not between the cell and an ambient the heater could raise; and heating the cells
would fight ADR-052's whole design (free movement) and ADR-043's finding that **cold is beneficial
to the array** (solar efficiency and Voc *rise* as temperature falls, so the 2.4 W budget is
conservative at altitude). The fix ADR-052 already records — **end-only, unbonded mount** — is
correct and stands. A heater cost for the cells is **not quantified here** and is marked
`TODO(unverified)`: the repo carries no cell thermal conductance, and a bare cell is radiation- and
tab-conduction-coupled, which is outside this analysis.

---

## 5. In-flight work recovered: the `adr/thermal-drift-strategy` branch

The operator's standing instruction is to **check in-flight work before scoping new** and to
**never discard superseded artifacts**. The branch was investigated and is **already on `main`**:

- Branch tip `da3ba7c` (*"docs(report): record ADR-042 Addendum A amendment + verified push refs"*)
  is an **ancestor of `main`**, merged by `d33b29c` (*"merge: consolidate
  adr/thermal-drift-strategy into main (v9 consolidation train)"*).
- The ADR it produced, **`docs/adr/042-thermal-drift-strategy.md`**, **DOES exist on `main`**
  (the lead that "ADR-042 does not appear to exist on main" is incorrect; it exists and is
  `Status: Proposed`). Its content: heater rejected (§D1), TCXO first (§D2), firmware f(T)
  pre-distortion (§D3), wider channel plan (§D4), the deciding-number gate (§D5), the MS5611
  conflict (§D6), plus **Addendum A** (runtime `GetTemp` sensor, the 100 K NTC-on-pin-3 hardware
  fix, the ±10 ppm/−20…+70 °C characterised window, the temperature-triggered recalibration
  requirement).
- **ADR-043** (*Cold Qualification — Heating Rejected, Below-Rated Parts Gated*, `Accepted`) is
  likewise on `main` and covers the cold-heating rejection and the rating gate.
- A `backup/adr-thermal-drift-strategy-20261007` **tag** at `da3ba7c` preserves the branch.

**What this means for this work.** ADR-042 and ADR-043 already own the
`heater rejected / TCXO first / cold qualification` decisions. **This analysis does not discard or
rewrite them.** It adds the two things they do not contain — the **per-radio reference census** and
**GPS 1PPS discipline** — plus the G-form heater arithmetic against the 33.264 J bank and the
adjacent-need costs. Its ADR (**056**) *cross-references and extends* ADR-042 §D3 (§3.2 above) and
*reaffirms* ADR-042 §D1 and ADR-043 decision 1; it **supersedes neither**.

---

## 6. Operator-facing bench tests this implies

Design work only — none of these is run here, and none orders hardware.

1. **Cold-soak frequency-offset measurement of the chosen reference.** Soak one module at
   **−60 / −40 / −20 / 0 / +20 / +40 °C** (≥ 20 min per step), measure the carrier with a calibrated
   counter/SDR at the flight channel, compute `Δf/f` in ppm. **This is ADR-042 §D5's deciding
   number** and it is the gate that decides whether any mitigation is needed at all.
   *Pass:* residual inside the LoRa/FLRC carrier-offset budget for the chosen BW/SF.
2. **1PPS-discipline convergence test.** With the radio at a known temperature offset, run the
   1PPS→measured-`Δf/f`→synth-trim loop and log residual ppm vs time. *Pass:* converges below
   target (propose **< 0.05 ppm** within a **≤ 100 s** window) and holds. This measurement also
   supplies the **`σ_t`** this analysis had to leave `TODO(unverified)`.
3. **Cold ESR / capacitance characterisation of the bank** at −60 °C — already an ADR-036/ADR-047
   open item; feed the §4.2 sensitivity with real `k` and `c`.
4. **Enclosure thermal-resistance step test** — apply a known `P`, measure equilibrium `ΔT`, compute
   `G = P/ΔT`. This replaces the assumed `G = 10 mW/K` in ADR-042 §D1, ADR-043 and this analysis,
   and pins the heater arithmetic permanently.
5. **Module census resolution** — deshield/mechanical drawing for the plain LoRa2021 (is pin 3/NTC
   broken out?) and the SX1280 module (TCXO control pin?) — resolves §1.2 and §3.1's
   `TODO(unverified)` rows.

---

## 7. Bottom line — answering the operator directly

> *"Do you already have a heaters provision for the oscillator of the radio so that we don't have
> frequency drift?"*

**No, there is no heater provision, and there should not be one — a heater is the wrong instrument
for oscillator stability on this vehicle.** An OCXO-class heater fails the arithmetic at every
plausible thermal conductance: at the repo's own assumed `G = 10 mW/K` it needs **0.800 W continuous**,
which is **2.06× the whole 0.388 W daylight average**, **8000× the 100 µW night anchor**, and
**866× the entire 33.264 J usable bank** (a 10 h night would need 28 800 J). Even the most insulated
estimate (G = 3 mW/K) drains the entire bank in ~139 s.

**What replaces it, in rank order:**

1. **The module TCXO where the radio needs one** — the F33-2G4 already carries a **0.5 ppm built-in
   TCXO** (already banked; C3 removed). The bare LoRa2021, which is the *default* flight radio,
   needs either the F33, a **100 K NTC on LR2021 pin 3**, or the discipline below. The SX1280 must
   be a **TCXO-bearing module** if it is a flight reference.
2. **GPS 1PPS discipline — the zero-mass, zero-watt fix.** The MAX-M10S's 1PPS (already on GPIO21)
   measures the radio reference's residual fractional error; averaged over a 10–100 s window it
   resolves 0.002–0.03 ppm and is trimmable at the synthesizer's 0.05–0.28 ppm LSB. It costs **no
   grams and no watts**, and it is consistent with ADR-017/019/021/023 (which use GPS UTC for the
   *schedule*), extending ADR-042 §D3 (measured instead of tabled correction).
3. **Passive mitigation** — enclosure insulation and siting the reference near a self-heating node
   — is a secondary help, not the fix, and must never be achieved by bonding the solar cells
   (ADR-052).
4. **A heater** is rejected for oscillator drift, and also rejected for the adjacent needs: the
   −60 °C **rating gap** is a part-selection problem (holding electronics at −40 °C costs 0.160 W =
   41 % of the daylight average, 173× the bank over night), the **supercap cold** behaviour is a
   characterisation problem (warming the storage costs ~4× the budget, ADR-043), and the **cell
   cracking** mechanism is thermal contraction, whose fix is ADR-052's **end-only unbonded mount**.

---

## 8. `TODO(unverified)` list

- **[G]** Package-to-ambient thermal conductance `G` for the flight enclosure — all four values in
  §2 are **ESTIMATES**; the repo's only figure is ADR-042 §D1's assumed `R_thermal ≈ 100 K/W`
  (`G = 10 mW/K`). *Settle:* enclosure step test (§6.4).
- **[dT]** The OCXO turning point (+25 °C) is an **ESTIMATE** for an AT-cut crystal; the true value
  is crystal-specific and unmeasured here.
- **[1PPS jitter]** MAX-M10S 1PPS edge jitter `σ_t` (and its UTC accuracy) is not in the repo.
  *Settle:* u-blox datasheet or the §6.2 bench test.
- **[LO]** The LoRa/FLRC **carrier-offset tolerance** for the chosen BW/SF (ADR-042 §D5's second
  half) — the gate for whether any mitigation is needed.
- **[MODULE]** Whether the plain NiceRF LoRa2021 breaks out pin 3 / the NTC, and whether the SX1280
  module exposes a TCXO control pin. *Settle:* module mechanical drawings / deshield photos.
- **[CENSUS]** The `docs/assets/lr2021/README.md` "onboard 0.5 ppm TCXO / VTCXO pin 13" claim vs the
  LESSONS/DUAL-VARIANT census (§1.2) — conflicting; treat as unresolved.
- **[XTAL]** `docs/SDR-HANDOVER.md:60`'s "LR2021 uses a 52 MHz XTAL" vs the datasheet's 32 MHz
  (§1.3) — probable cross-radio conflation; unresolved.
- **[ESR/COLD]** Cold (−60 °C) capacitance and ESR of the fitted bank — ADR-036/ADR-047 open item;
  §4.2 is parametric only.
- **[CELLG]** Cell/array thermal conductance for a heater-cost estimate — not in the repo; §4.3
  deliberately does not quantify it.
- **[TCXO_RAIL]** Any external-TCXO rail/current for a bare module (ADR-042 open item) — unchanged
  from ADR-042.
- **[RATING]** Whether junction self-heating rescues the −40 °C parts at −60 °C, and whether
  extended-grade parts exist (ADR-054 open item 2) — unchanged.
