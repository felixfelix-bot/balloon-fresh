# ADR-119 — v10 radio sites: three LR2021 slots (2× LP + 1× F33) + E28-2G4M27SX ranging module

> **SUPERSEDED IN PART by ADR-089 (2026-11-25), for the vnext MINIMAL variant only.** The MINIMAL
> flight variant carries **two** RF sites (site A: F33 TX; site B: ONE LR2021 RX) and **no site C,
> no site D**. This record's four-site table continues to govern v10 and any non-MINIMAL variant;
> nothing here is retracted for those boards. See `docs/adr/089-vnext-minimal-flight-variant.md` §1/§3.

- **Status:** ACCEPTED — operator instruction, 2026-10-20 (extends the 2026-10-14 three-slot ruling, `docs/fab/V9-RADIO-SLOT-CONSOLIDATION.md`; promoted to ADR on operator order "lock these decisions in as ADRs").
- **Decision owner:** Felix (operator)
- **Related:** ADR-118 (v10 directives umbrella), ADR-034 (band split 433/2.4), ADR-040 (site optionality — extended), ADR-108 (pin plan — to be re-derived), `docs/fab/SX1280-MODULE-DECISION.md` (the measured refutation of the bare-chip approach), `docs/modules/e28-2g4m27sx/E28-2G4M27SX_UserManual_v1.0.pdf` (qualification source).

## Decision

The v10 flight board carries **four RF sites**:

| site | part | role | notes |
|---|---|---|---|
| A | `LoRa2021F33-2G4` | 433 MHz TX (HP) | biggest part, 39.6×22.3 mm courtyard |
| B | bare `LoRa2021` LP | 2.4 GHz RX link | v9's U3 |
| **C** | bare `LoRa2021` LP | second 2.4 GHz option | **NEW — the missing third slot** |
| **D** | `E28-2G4M27SX` module | 2.4 GHz ranging | **replaces the bare-chip SX1280** |

**What is abandoned:** the bare QFN SX1280 + self-built 7-part match/filter network. Measured on v9: the network was scattered across the board (1.2 pF shunt 52 mm from the chip; ~220 mm chain ≈ 3 guided wavelengths at 2.4 GHz; crystal 25 mm from XTA/XTB) — consultant verdict FATAL, not tunable (`SX1280-MODULE-DECISION.md`).

**What replaces it:** the Ebyte **E28-2G4M27SX** — SX1280 + PA + LNA + complete matching network + 52 MHz crystal, all on-module, vendor-engineered. Datasheet facts of record: 15×20 mm SMD, 16 pads @ 1.27 mm castellated pitch, 27 dBm max, **580 mA TX peak**, control pins `RX_EN`/`TX_EN` (two extra GPIOs vs the bare chip), 2.5–3.6 V, keep-out rules apply on **both sides** at its site (manual §4.1).

## Consequences

1. **Population stays deferred** (the 2026-10-14 ruling): all radio sites DNP by default; the operator hand-solders per board.
2. **Pin plan re-derivation:** ADR-108 must be re-derived — the E28 adds `RX_EN`/`TX_EN`, drops the crystal/match pads, and the removed bare-chip network frees 7 part positions.
3. **Energy budget:** 580 mA TX peak vs the bare chip's ~70 mA — ADR-036 (burst storage, daylight-only TX) must be re-checked; ranging remains burst-scheduled per ADR-035.
4. **Ruling semantics carried forward:** what is exclusive is the 2.4 GHz *slot*, not the chip (arbitration contract R7 in `V9-RADIO-SLOT-CONSOLIDATION.md`).
5. The vendor module's Amazon listing ("CDSENET E28-2G4M27SX") is a **compatible part**; the Ebyte datasheet in-repo is the qualification source. Verify pin-compatibility of any actually-purchased variant before soldering (listing title says "Compatible").

## Reproduce

```
ls docs/modules/e28-2g4m27sx/
grep -n 'scattered' docs/fab/SX1280-MODULE-DECISION.md
```
