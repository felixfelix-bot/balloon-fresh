# BASE-STATION PCBA v1 — schematic captured as a netlist, machine-verified

**Date:** 2026-10-14 · **Status:** netlist generated and **verified against the frozen spec**.
**No KiCad schematic editor file, placement, route, DRC or gerber exists yet** — not claimed.

Second concrete step on the largest remaining deliverable (first was the spec, commit
`c3ccedec`).

## What was produced

| artefact | what it is |
|---|---|
| `base_station/spec.json` | machine-readable transcription of the D14 freeze (**33/33** verified) |
| `base_station/base_station_v1.net` | **44 components, 44 nets** — the KiCad netlist format the hub's proven build chain consumes |
| `base_station/gen_base_station_netlist.py` | the generator (single writer) |
| `base_station/test_netlist_implements_spec.py` | **25/25 checks** that the netlist *implements* the frozen invariants |
| `base_station/test_spec_transcription.py` | **33/33** that the spec *copied* the freeze correctly |
| `base_station/counter_test_spec.py` | proves the transcription verifier can fail |

## Two different verifiers, on purpose

**Transcription vs implementation are different questions.** One asks *"did I copy the freeze
right?"*; the other asks *"does the design actually satisfy the invariants the freeze requires?"*
Both must pass, and the netlist verifier **caught two of my own errors on its first run**:

1. It flagged `exactly one part drives DET_RF_IN` — my assertion was wrong, because a 2-pin net
   has **two** nodes (the filter's output *and* the detector's input). **The net was correct; my
   check was wrong.**
2. It flagged `no part named as an LNA` — **too broad.** `Q_LNA_SW` is the **board-owned bias
   switch**, which the freeze *requires*; what must not be here is the **masthead amplifier**
   (`ZX60-P103LN+`). Corrected to check the right thing.

Both were **verifier bugs, not design bugs** — which is the sixth instance of this campaign's
recurring lesson, and exactly why the check exists.

## The frozen invariants, verified in the netlist

- **Five rails, all separate nets:** `+5V_PCBA`, `+5V_LNA_SW`, `+5V_VGA`, `+5V_DET`, `+3V3_MCU`.
- **"No single LNA fault may remove MCU power"** — `+5V_LNA_SW` and `+3V3_MCU` share **no node**;
  a dedicated `Q_LNA_SW` load switch feeds the LNA branch from `+5V_PCBA` on its own pin.
- **"Do not feed ADL5240 from the switched masthead LNA branch"** — `+5V_VGA` is fed from
  `+5V_PCBA` through its own `FB_VGA` bead/filter.
- **The mandatory second 433 MHz BPF** — `DET_RF_IN` has exactly two nodes, `FLT_433_B` and
  `U_DET` pin 3. The detector's input can only be reached through the second filter.
- **No 2.4 GHz PA** — the 2.45 GHz port reaches exactly one connector and **no active device**.
- **The masthead LNA is not on the board** — no `ZX60`/`P103LN` part; the **bias switch is**,
  as required.
- **No circulator** — none present, and the spec forbids one.

## Footprints: all real, none invented

Every footprint resolves to a **library actually installed on this machine**, found by
`resolve_bs_footprints.py` across **165 libraries**:

| part | library:footprint |
|---|---|
| RP2040 QFN-56 | `MCU_RaspberryPi_and_Boards:RP2040-QFN-56` |
| TPS62162 (WSON-8 2×2) | `Package_SON:WSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm` |
| AD8318 (LFCSP-16 3×3) | `Package_CSP:LFCSP-16-1EP_3x3mm_P0.5mm_EP1.3x1.3mm` |
| ADL5240 (LFCSP-32 5×5) | `Package_CSP:LFCSP-32-1EP_5x5mm_P0.5mm_EP3.1x3.1mm` |
| 12 MHz crystal | `Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm` |
| SMA ports | `Connector_Coaxial:SMA_Amphenol_132134-10_Vertical` |

**Notable:** the stock KiCad library has **no** RP2040 footprint — it is only in the shipped
`tiny_tapeout` demo library. **Finding it there rather than inventing a QFN-56 is the point.**

## Marked `TODO(unverified)`, not invented

Parts whose package the freeze does **not** pin are flagged in the value string, with a generic
package so the board is complete while the gap stays visible: the **TVS clamp set point**, the
**detector tap coupling**, the **exact flash**, and the **load-switch/LDO device**.

## Live constraint carried into capture

**`VIN_GS` 18 V exceeds the TPS62162's 17 V rating.** The freeze says the 18 V upper bound must be
enforced upstream or the regulator variant changed. **`D_TVS`/`D_REV` are on the input, but the
enforcement is not yet designed** — this stays open and is the first thing to resolve.

## Honest state

**Capture is done as a netlist. Everything after it is not.** Remaining mechanical chain:
schematic editor file → placement → route → DRC → export → gerbers → STEP. The hub's chain is
proven and reusable (route → stitch → refill → DRC → verify BOM against board → emit JLC-format
BOM+CPL → gerbers + drill → zip with sha256).

**Still blocked on the operator only for scope changes**: the **number of stations** (board qty)
and the **cellular placement** (R1–R7), which changes enclosure and power entry.

## Reproduce

```
cd tracker/hardware/base_station
python3 gen_base_station_netlist.py             # writes the netlist: 44 comps, 44 nets
python3 test_spec_transcription.py              # 33/33
python3 test_netlist_implements_spec.py         # 25/25
python3 counter_test_spec.py                    # proves the verifier can fail
```
