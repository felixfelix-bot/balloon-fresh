# GROUND-STATION MCU — the S3 question, and why RP2040 is still in the netlist

**Date:** 2026-10-14 · **Answers the operator's challenge:** *"why do you need the RP2040? Didn't we
decide to use the ESP32 S3 instead? Which board do you need this for?"*

## Short answer

**You are right to challenge it, and the honest answer is: it is not settled.** The RP2040 in my
base-station netlist is a **faithful transcription** — not a decision I made. But the programme has
**already standardised on the ESP32-S3 elsewhere**, so the freeze and the practice **disagree**, and
that disagreement is the thing to resolve.

**Which board:** `tracker/hardware/base_station/` — the **ground/base-station PCBA v1**. (Not the
hub: the hub uses `ESP32-S3-WROOM-1U-N8R8`, confirmed in its netlist.)

## Where the RP2040 came from — it is NOT my invention

The D14 freeze names it explicitly, **device 8**:

> | 8 | Raspberry Pi **RP2040** (QFN-56) + external decoupling | TO-BUY; MCU, SPI control, ADC input,
> watchdog and telemetry in one board-owned device. **ADC input is used for the detector voltage; no
> separate ADC is fitted.** |

and again, four more times:

- *"RP2040, digital + ADC + SPI — 50 mA design allowance"* (power budget)
- *"Its serial/parallel gain control is owned by the RP2040"* (ADL5240 AGC)
- *"The detector output goes to RP2040 ADC"* (RF chain)
- *"The RP2040 AGC state machine … uses fast attack and slow decay as specified in ADR-084"*

**So the freeze is internally consistent and RP2040-specific. I transcribed it faithfully** — that
was correct, because transcribing a frozen design is not a new design decision.

## But the programme moved to the S3, and here is the evidence

| | |
|---|---|
| **Hub board** | `ESP32-S3-WROOM-1U-N8R8` — a **S3** |
| `docs/analysis/ground-station-level-control-design.md:244` | *"ADC/MCU: **RP2040 or ESP32-S3**"* — the analysis presents **both**, deliberately |
| `docs/DISCOVERY-SYNC-2026-08-07-batch2.md:36` | *"FIPS dev continues on **ESP32-S3** dev boards"* |
| `docs/DISCOVERY-SYNC-2026-08-07.md:17` | *"Current FIPS development (fips_radio_bridge, mesh_adapter, fips_transport) continues on **ESP32-S3** dev boards"* |
| `docs/adr/038-wifi-bt-disabled.md:59` | cites **ESP32-S3 Series Datasheet v2.2** as the reference MCU |

**So: the hub is S3, FIPS development is S3, and the level-control analysis lists both.** The
D14 freeze is the **odd one out** — it is the only document that commits to RP2040 alone.

## Why this matters beyond consistency — measured, live

**JLCPCB stock and price (live API, positive controls passed):**

| part | LCSC | stock | price |
|---|---|---:|---:|
| **RP2040 (QFN-56)** | **`C2040`** | **53,843** | **$0.9919** |
| ESP32-S3-WROOM-1-N8 | `C2913198` | 1,430 | $4.9087 |
| ESP32-S3-WROOM-1-N16 | `C2913199` | 926 | $5.2447 |
| ESP32-S3-WROOM-1U-N8 | `C2980297` | 1,196 | $4.8157 |

*(Controls: `C50645` SS24 stock 774,321 @ $0.0257; `C2876746` BQ25504RGTR stock 21 @ $4.5857.)*

**Both are orderable and well-stocked.** **The RP2040 is $0.99 against ~$4.90 for a module** — so cost
argues *for* the RP2040, and it **always did**.

## The real trade, stated honestly

**The RP2040's advantage is genuinely load-bearing, and it is IN THE FREEZE's own rationale:**

- **The detector voltage goes to the MCU's ADC. "No separate ADC is fitted."** The RP2040 has a
  **12-bit ADC**; the **ESP32-S3's ADC is notably non-linear** and would need calibration or an
  external ADC — which the freeze explicitly avoided.
- **A module vs a chip:** the S3-WROOM is a **module** (antenna, flash, RF can, and *regulatory
  modular approval*); the RP2040 is a **bare QFN-56** needing external flash, crystal and RF work.
  For a **mains-powered ground station**, module approval and integration effort argue **for the S3**.

**So the two candidates win on different axes:**

| | RP2040 | ESP32-S3-WROOM |
|---|---|---|
| ADC for the AD8318 detector | ✅ 12-bit, direct | ⚠ non-linear, needs care |
| MCU consistency with hub + FIPS | ❌ different toolchain | ✅ same as hub |
| Firmware reuse (FIPS, AGC) | ❌ new | ✅ exists on S3 |
| Cost | ✅ $0.99 | ❌ ~$4.90 |
| Integration effort | ❌ bare chip + flash + crystal | ✅ module |
| Radio stack | ❌ none needed here | ~ has WiFi/BT (**should be disabled**, ADR-038) |

## My recommendation, with the reason

**Adopt the ESP32-S3-WROOM-1U for the ground station, and record it as a superseding decision to the
D14 freeze's device 8.**

Reasons, in order:

1. **Firmware reuse is the dominant term.** FIPS (`fips_radio_bridge`, `mesh_adapter`,
   `fips_transport`) and the AGC state machine **already run on S3**. Porting them to RP2040 is
   **new, unproven firmware** on the one board whose job is *remote access when nothing else
   works*. **A ground station that needs a firmware bring-up before it can be reached is not a
   remote-access gateway.**
2. **The hub is S3**, so one toolchain, one pin-plan convention, one set of lessons.
3. **Module vs bare chip** matters most on the board that **must** be reliable — and the S3-WROOM
   carries its own RF approval.
4. **The ADC concern is real and must be answered, not waved away:** the AD8318's output feeds the
   MCU ADC. **If S3's ADC linearity is inadequate for AGC, the fix is either (a) the S3's ADC
   calibration, or (b) an external ADC — which the freeze avoided.** **This is the one thing that
   could flip the decision back, and it needs a measured answer, not a preference.**

**What I would NOT do:** keep RP2040 just because the freeze says so, or switch to S3 without
resolving the ADC question. **Both are silent choices; one of them is wrong.**

## What this changes in my base-station work

The netlist I generated is **currently correct as a transcription** (and its footprint is now
vendored with provenance). **If you adopt the S3, the change is small and mechanical:**

- swap `U_MCU` from `base_station_lib:RP2040-QFN-56` to `RF_Module:ESP32-S3-WROOM-1U`
- re-map the GPIO/ADC nets to the S3's pin plan
- **the vendored RP2040 footprint becomes unused** — kept, with provenance, because the decision is
  not final

**Placement impact:** the RP2040 QFN-56 is **7 × 7 mm**; the S3-WROOM-1U is **~18 × 25.5 mm** — a
**real area increase** on a 55 × 40 mm board that already holds 44 parts at 41.5 % utilisation.
**So this is also a placement/outline question, and it should be settled before the outline is
frozen** — the same conclusion as Site C.
