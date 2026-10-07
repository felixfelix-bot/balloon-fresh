# V9 Radio-Site Matrix — population, GPIO, rail, regulatory (per configuration)

Date: 2026-10-07
Companion to ADR-040 (`docs/adr/040-v9-radio-site-optionality.md`).
Reconciled against `docs/V9-DUAL-LR-DESIGN-MEMO.md` (branch `docs/v9-dual-lr`, tip `ad3b8ad`).

This matrix tabulates the **four population configurations** of the two v9 radio sites
(Site A = variant LP-or-HP, Site B = LP-only) that ADR-040 records. Every numeric cell is
either cited to a repo source or marked **TODO(unverified)** / **UNVERIFIED** — nothing is
invented.

---

## 1. The two sites

| Site | Accepts | Footprint | Default population |
|---|---|---|---|
| **A (variant)** | bare `LoRa2021` (LP) **or** `LoRa2021F33-2G4` (HP) — mutually exclusive | nested pad field (bare inside F33 ring) | bare LP |
| **B (LP-only)** | bare `LoRa2021` (LP) only | bare castellated pad field | bare LP |

Both sites **DNP by default**; the operator hand-solders. (Source for "hand-soldered":
operator instruction in ADR-040; DNP-by-default: ADR-040 D2.)

---

## 2. Part reference (cited, not invented)

| Parameter | Bare `LoRa2021` (LP) | `LoRa2021F33-2G4` (HP) | Source |
|---|---|---|---|
| Body size | 19.81 × 14.98 mm (also recorded 19.72 × 15 × 2.2 mm — see note) | 39 × 21 mm (nominal 39.6 × 21.6) | `docs/DUAL-VARIANT-DESIGN.md` §Overview; `docs/inventory.md` line 16; `docs/V9-DUAL-LR-DESIGN-MEMO.md` §3 |
| VCC | 1.8–3.6 V (3.3 V) | 3.0–5.5 V (5 V for full 2 W) | `docs/DUAL-VARIANT-DESIGN.md` §1 |
| TX power @433 MHz | +22 dBm (158 mW) | +33 dBm (2 W) | `docs/DUAL-VARIANT-DESIGN.md` §1 |
| TX power @2.4 GHz | +12 dBm | +30 dBm (1 W) | `docs/DUAL-VARIANT-DESIGN.md` §1 |
| **TX current (max)** | **120 mA** | **1200 mA** | `docs/DUAL-VARIANT-DESIGN.md` §1 (line 75) |
| TX @433 22 dBm current | < 120 mA | — (HP at 5 V) | `docs/inventory.md` line 29 |
| TX @2.4 GHz 12 dBm current | < 35 mA | — (HP at 5 V) | `docs/inventory.md` line 29 |
| RX current | sub-GHz < 6 mA; 2.4 GHz < 7 mA | not recorded here | `docs/inventory.md` line 30 |
| Sleep current | < 2 µA | 20 µA | `docs/inventory.md` line 31; `docs/DUAL-VARIANT-DESIGN.md` §1 |
| TCXO | none (crystal, no NTC) | 0.5 ppm built-in | `docs/LR2021-LESSONS-2026-09.md` variant census |
| PA table / RF-switch | **none needed** (chip-only RF) | **required** (setRfSwitchTable, DIO5/DIO6) | `docs/LR2021-LESSONS-2026-09.md` |
| Land pattern status | in-repo, not re-verified here | **FAIL 0/18 pads** (see P1) | `docs/f33-module/F33-LANDPATTERN-VERIFICATION.md` |

> **Note (size discrepancy, flagged not resolved):** `docs/inventory.md` records the bare
> part as **19.72 × 15 × 2.2 mm** (line 16) while `docs/DUAL-VARIANT-DESIGN.md` records
> **19.81 × 14.98 mm**. The bare-module footprint is a *different module* and was explicitly
> out of scope of the F33 land-pattern verification (`docs/f33-module/F33-LANDPATTERN-VERIFICATION.md`
> §7.4). UNVERIFIED: the exact bare-module land pattern against the vendor pad file.

---

## 3. Per-configuration population matrix

Configurations named by population: **{LP}** = one LP module, **{HP}** = one HP module,
**{LP+LP}** = two LP modules, **{HP+LP}** = one HP + one LP.

### 3.1 GPIO delta

Base pin plan is `docs/adr/029-f33-sx1280-pin-plan.md` (F33 on SPI2, SX1280 on SPI3).
A **second, independent radio** costs additional control lines, per the dual-LR memo §5:

| Config | Radios fitted | GPIO delta vs single-radio baseline | Bus situation | Source |
|---|---|---|---|---|
| **{LP}** | 1 LP | **0** (baseline single radio) | one radio on its SPI | — |
| **{HP}** | 1 HP | **0** (baseline single radio) | one radio on its SPI | — |
| **{LP+LP}** | 2 LP | **+4 GPIO** (CS + BUSY + RESET + IRQ/DIO, shared SPI data/clock) | share SPI data/clock | `docs/V9-DUAL-LR-DESIGN-MEMO.md` §5 |
| **{HP+LP}** | HP + LP | **+4 GPIO** (shared bus) | share SPI data/clock | `docs/V9-DUAL-LR-DESIGN-MEMO.md` §5 |

- The **+7 GPIO** independent-bus case (adds SCK/MOSI/MISO) is **not available** on v9: the
  S3's two general SPI masters are already committed (SPI2 = F33, SPI3 = SX1280), and the
  `-N8R8` octal-PSRAM part reserves IO35/36/37. Source: `docs/V9-DUAL-LR-DESIGN-MEMO.md` §5;
  `docs/adr/029-f33-sx1280-pin-plan.md` (PSRAM pins).
- **UNVERIFIED:** whether the F33-specific `CE`/`DIO5` enable lines add further GPIO over the
  bare module when the HP part is at Site A. The memo notes "a bare module normally does not
  provide the F33-specific CE/DIO5 pair; if the selected variant requires additional
  enable/LNA control, add those lines too" (`docs/V9-DUAL-LR-DESIGN-MEMO.md` §5). The exact
  F33 line count is a schematic-time item, not a number this matrix asserts.

### 3.2 Instantaneous rail delta (TX)

The **plain** module's rail delta is repo-verified and **small**; the **F33** delta is the
large figure from the memo. They are kept in separate rows deliberately.

| Config | Rail delta (TX, instantaneous) | Source |
|---|---|---|
| **{LP}** | ≈ +120 mA @433 (+22 dBm); ≈ +35 mA @2.4 GHz (+12 dBm) | `docs/inventory.md` line 29 |
| **{HP}** | up to +0.8 A @868 / +0.9 A @2.4 GHz at 5 V (≈ +1.2 A @433 2 W) | `docs/V9-DUAL-LR-DESIGN-MEMO.md` §5; `docs/DUAL-VARIANT-DESIGN.md` §1 (1200 mA) |
| **{LP+LP}** | **two PLAIN modules ≈ +120 mA TX each** → ≈ +240 mA worst-case if both keyed | `docs/inventory.md` line 29 (120 mA each); the "+120 mA each" phrasing is the repo's own ground-truth note (`docs/inventory.md`, `docs/DUAL-VARIANT-DESIGN.md` line 75) |
| **{HP+LP}** | F33 (0.8–1.2 A) **plus** LP (≈120 mA) if both keyed | sum of the two cited figures above |

> **Honesty note:** the "+120 mA each" figure for two PLAIN modules is verified from
> `docs/inventory.md` line 29 (`TX @433MHz 22dBm: <120mA`) and `docs/DUAL-VARIANT-DESIGN.md`
> line 75 (`TX current (max) 120 mA`), **not** copied from the memo's F33 figure. The memo's
> +0.8 A / +0.9 A is an F33-only number and is **not** applied to plain modules here. Under
> ADR-035 the one-transmitter-at-a-time invariant means the two LP rails do **not** sum
> simultaneously; the ≈ +240 mA is a worst-case *if the invariant were violated*, stated for
> sizing only. Average current depends on duty cycle (ADR-036) and is not inferred from peak.

### 3.3 Antenna / feed count and keep-outs

| Config | RF feeds | Notes | Source |
|---|---|---|---|
| **{LP}** | 1 feed (chosen band; bare module has one active band at a time) | bare module has sub-GHz ANT + 2.4 G ANT ports | `docs/inventory.md` §Details (pins 9/10) |
| **{HP}** | 2 feeds (ANT + ANT-2G4) | F33 exposes both 50 Ω ports | `docs/DUAL-VARIANT-DESIGN.md` §1 |
| **{LP+LP}** | 2 feeds (one per module) | one LP on 433 TX, one LP on 2.4 RX (ADR-034 split) | ADR-034 D1 |
| **{HP+LP}** | 3 feeds (HP: 2 ports + LP: 1 active band) | keep-out/feed count grows; UNVERIFIED placement feasibility on 55 × 45 mm | this matrix; see keep-out note |

> **Keep-out note (UNVERIFIED):** antenna-to-antenna isolation and feed keep-outs for the
> two- and three-feed configurations on a 55 × 45 mm board are **not** measured in the repo.
> ADR-035 assumes 15–25 dB isolation and mandates one-transmitter-at-a-time. UNVERIFIED: the
> actual keep-out/routing feasibility of the `{LP+LP}` and `{HP+LP}` feed layouts.

### 3.4 DNP / 0-ohm selection scheme

| Config | Site A population | Site B population | Selection mechanism |
|---|---|---|---|
| **{LP}** | LP (fitted) | DNP | fit LP at A only |
| **{HP}** | HP (fitted) | DNP | fit HP at A only (blocked by P1) |
| **{LP+LP}** | LP (fitted) | LP (fitted) | fit LP at both |
| **{HP+LP}** | HP (fitted) | LP (fitted) | fit HP at A, LP at B (blocked by P1) |

Selection is by **physical population only** — no 0-ohm jumpers are specified here because
the site is choose-one by soldering (the operator hand-solders; ADR-040 Context). **TODO
(unverified):** whether any 0-ohm/DNP resistor is needed to select the shared-VCC pad between
the nested LP and HP footprints at Site A — the memo records the nested pad field shares VCC
(`docs/V9-DUAL-LR-DESIGN-MEMO.md` §3), but does not specify a selection resistor. This must be
resolved at schematic time, not assumed here.

### 3.5 Mass when fitted vs empty

| Item | Mass | Source |
|---|---|---|
| Empty pads (both sites DNP) | ≈ 0 g added | copper-only footprint |
| Bare `LoRa2021` (LP) each | **UNVERIFIED** | no module mass in g recorded in repo (`docs/inventory.md` lists a 0.01 g scale but no module mass) |
| `LoRa2021F33-2G4` (HP) each | **UNVERIFIED** | same |

> **UNVERIFIED:** module mass in grams. The repo has a 0.01 g resolution scale
> (`docs/inventory.md` line 68, "MS300 Waage") but records **no** module mass figure. What
> would settle it: weigh one bare module and one F33 module on that scale and record the
> values. The only size-based clue is body dimensions (LP ≈ 20 × 15 mm, HP 39 × 21 mm) — a
> size difference, not a mass number.

---

## 4. Legal regime per config

Source: `docs/REGULATORY-AMATEUR-LICENCE.md` (branch `docs/regulatory-amateur`, tip
`0f02f29d`), `docs/adr/039-*` (licence-exempt 433.05–434.79 MHz ≤ 10 mW ERP, being written
concurrently), `docs/V9-DUAL-LR-DESIGN-MEMO.md`.

| Config | Licence-exempt (433.05–434.79 MHz, ≤ 10 mW ERP) | Amateur licence (DE, 430–440 MHz) |
|---|---|---|
| **{LP}** | **usable** (LP +22 dBm can be throttled to ≤ 10 mW ERP) | usable (well inside 75 W PEP Class E) |
| **{HP}** | **NOT usable** — 2 W PA is dead weight at ≤ 10 mW ERP | **usable** (750 W PEP Class A / 75 W PEP Class E) |
| **{LP+LP}** | **usable** (both LP throttled ≤ 10 mW ERP) | usable |
| **{HP+LP}** | **NOT usable** (HP leg dead weight in licence-exempt) | **usable** (HP leg legal under amateur licence) |

Amateur-licence duties that apply to **any** licensed (i.e. HP-containing) configuration:

1. **Callsign required** — every downlink frame must carry the operator's German callsign;
   at least hourly (ITU RR Art. 19), ≤ 10 min recommended. `docs/REGULATORY-AMATEUR-LICENCE.md` §4.
2. **No encryption** — AFuV §16(7)–(8); the LoRa/FLRC framing must be publicly recoverable.
   `docs/REGULATORY-AMATEUR-LICENCE.md` §5.
3. **Secondary status** — must not harm military/radar primaries in 430–440 MHz.
   `docs/REGULATORY-AMATEUR-LICENCE.md` §3.
4. **Cross-border drift** — unsettled for an unmanned airborne auto-transmitter (open item 1).
   `docs/REGULATORY-AMATEUR-LICENCE.md` §7.

> The HP leg is therefore **only** legal (and only useful) under the amateur licence or on
> the ground station, never in the licence-exempt regime the operator selected for flight
> (ADR-039).

---

## 5. Required pre-flight tests (one TX at a time, per ADR-035)

These are carried forward from ADR-035 D4 (one transmitter at a time) and the dual-LR memo
§2, stated per configuration.

| Test | Applies to | Requirement | Source |
|---|---|---|---|
| **One TX at a time** | all two-radio configs | arbiter enforces at most one transmitter keyed; non-slot transmitters **disabled**, not idle | ADR-035 D4 |
| **Conducted 868 third-harmonic / desense** | any config with a sub-GHz TX near 868 (i.e. the LP/HP 433 TX is 2× = 866 MHz → 868 victim) | measure P2604/P868 (the memo's 3 × 868 = 2604 MHz arithmetic) after the LPF; do not report unmeasured attenuation | `docs/V9-DUAL-LR-DESIGN-MEMO.md` §2; ADR-034 D3/D4 |
| **2.4 GHz RX desense with 433 TX keyed** | `{LP+LP}`, `{HP+LP}` | decide SAW/BPF by measurement, not datasheet margin | ADR-034 D4 |
| **Load switch for the second/unpopulated radio** | all configs | a load switch so an unpopulated (or second) radio cannot draw its sleep/standby current into the ADR-036 night sleep-current budget | ADR-036 (night deep sleep) |
| **F33 RF-switch / PA enable** | `{HP}`, `{HP+LP}` | setRfSwitchTable with dense DIO array from DIO5; DIO5 HIGH (2.4 LNA) / DIO6 sub-GHz PA enable | `docs/LR2021-LESSONS-2026-09.md` |
| **TCXO vs crystal drift** | `{LP+LP}` flight | plain module crystal drift at −44…−60 °C (open risk) — characterise before flight | `docs/LR2021-LESSONS-2026-09.md` |

---

## 6. Recommendation carried into this record

**Keep the pads (zero fab cost). Default-populate the LOW-POWER part at both sites.**

- The `{LP+LP}` configuration delivers the simultaneous 433 TX + 2.4 GHz RX that ADR-034
  wanted, for about **+120 mA** and **+4 GPIO**, with **no PA-table work**.
- The HP leg stays an **option** for licensed operation or the ground station, where the F33's
  **0.5 ppm TCXO** is the reason to want it at all (the plain module's crystal drifts out of
  channel at narrow BW in the stratosphere).

---

## 7. Open items / unverified (consolidated)

1. **P1** — F33 land pattern fix (owned by another worker, `fix/f33-landpattern-vendor`).
   Blocks all `{HP}`/`{HP+LP}` assembly.
2. **O1** — 5 V rail for the F33's 2 W output (ADR-029 O5 → ADR-034, still open).
3. **O2** — plain-module temperature drift (no TCXO/NTC) at −44…−60 °C.
4. **O3** — cross-border amateur operation for an unmanned airborne transmitter.
5. **UNVERIFIED** — module mass in grams (both parts).
6. **UNVERIFIED** — bare-module land pattern vs vendor pad file (out of scope of the F33 check).
7. **UNVERIFIED** — exact F33 additional GPIO (CE/DIO5/LNA enable) over the bare module.
8. **UNVERIFIED** — feed/keep-out routing feasibility of 2- and 3-feed layouts on 55 × 45 mm.
9. **TODO(unverified)** — Site A shared-VCC selection scheme (0-ohm/DNP resistor) at schematic time.
