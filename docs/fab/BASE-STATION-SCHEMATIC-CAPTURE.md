# BASE-STATION PCBA v1 — schematic capture STARTED (spec transcribed and verified)

**Date:** 2026-10-14 · **Status:** capture **spec** done and machine-verified; **no KiCad
schematic exists yet** and none is claimed. This is the first concrete step on the largest
remaining deliverable.

## Why starting is safe without waiting on the scope decision

The D14 note freezes the **parts and the network** for schematic capture, with datasheet URLs
per row. Transcribing a frozen design is **not** a new design decision, so it does not need a
fresh operator ruling. What *would* need one is changing the scope (e.g. moving the 2.4 GHz PA
onto the PCBA, or the cellular question) — so the spec records the frozen scope **and** the open
questions separately, and changes nothing.

## What was produced

| artefact | purpose |
|---|---|
| `tracker/hardware/base_station/spec.json` | machine-readable transcription of the freeze: rails, active devices, DNP rows, RF chain, AGC control, ERC requirement, gates |
| `tracker/hardware/base_station/test_spec_transcription.py` | **33 checks** that the spec is a faithful copy of the source document |
| `tracker/hardware/base_station/counter_test_spec.py` | **proves the verifier can fail** |

**`RESULT: 33/33 checks pass`** — and the counter-test **sabotages the spec** (drops a
verification gate, changes a current figure) and confirms the verifier goes red, then restores
it. **A test that only ever passes proves nothing**, so the counter-test is part of the
deliverable.

## What the spec captures, verbatim from the freeze

- **Rails:** `VIN_GS` 9–18 V protected → `TPS62162` (3–17 V in, 1 A out) → `+5V_PCBA`, design
  total **316 mA**, copper budgeted **≥ 0.5 A continuous / 1 A peak**; plus **`+5V_LNA_SW`**
  (95 mA, switchable so *"an LNA fault cannot collapse the MCU rail"*), **`+5V_VGA`** (93 mA,
  "do not feed it from the switched masthead LNA branch"), **`+5V_DET`** (15 mA), **`+3V3_MCU`**
  (50 mA).
- **Devices:** `AD8318ACPZ-R7` (row 7), `RP2040` QFN-56 (row 8), `TPS62162` (row 14), `ADL5240`,
  `ZFBT-4R2GW+` bias tee — each with its datasheet URL and, where the freeze gives one, its
  gate.
- **DNP by design, all four:** row 11 PA/FEM (*"a higher-legal-footing PA is a FUTURE RESPIN,
  not an open v1 BOM row"*), row 18 enclosure/mast clamp (mechanical out-of-scope), the 2.4 GHz
  PA, the masthead LNA on the PCBA.
- **RF chain:** 433 antenna → BPF → tee RF/DC → `ZX60-P103LN+` → coax → tee RF/DC → ADL5240,
  50 Ω; **the detector tap must have a SECOND 433 MHz BPF** because *"AD8318 is broadband;
  unfiltered 2.45 GHz leakage could falsely reduce RX gain"*; detector ground returns to the
  quiet analog region. **A circulator is explicitly forbidden as a substitute.**
- **AGC:** RP2040 state machine, deadband ≥ one 0.5 dB step + hysteresis, fast attack / slow
  decay, and a **downlink-failure watchdog independent of the TX attenuation LUT** that falls
  back to a known fixed manual gain.
- **ERC requirement:** separate `+5V_LNA_SW` / `+5V_VGA` / `+5V_DET` / `+3V3_MCU` domains, with
  the invariant **"no single LNA fault may remove MCU power."**

## Two constraints that will bite the schematic, recorded not resolved

1. **`VIN_GS` 18 V vs the TPS62162's 17 V rating.** The freeze itself flags this: the 18 V upper
   bound *"must be enforced by the upstream protection/entry specification"* or the regulator
   variant changed. **This is a live design input, not a footnote.**
2. **AD8318 operating-current limit** — the freeze says to check it *during schematic review*.

## The freeze's own four gates are NOT claimed as passed

Carried into the spec verbatim so nobody reads this capture as evidence the design is
bench-verified: the tee's insertion loss/current rating, the 433 BPF and detector-tap BPF
measurements, and the `ZX60-P103LN+` lower band edge (ADR-079's open contradiction, needing a
400–500 MHz S21 sweep).

## Honest state

**The largest remaining deliverable is now started, not finished.** A spec and its verifier
exist; **no schematic, placement, route, DRC or gerber exists for the base station.** Next
mechanical steps: capture the schematic from the spec, then place → route → DRC → export.

**Blocked on the operator only for scope changes**, not for capture: the number of stations
(the pipe has two ends) fixes board qty, and the cellular placement (R1–R7) changes the
enclosure and power-entry spec.

## Reproduce

```
cd tracker/hardware/base_station
python3 test_spec_transcription.py    # 33/33
python3 counter_test_spec.py          # proves the verifier can fail
```
