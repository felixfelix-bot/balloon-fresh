# REPORT — Resolve 7 floating-pin TODO(unverified) markers (pr/v8k-sch-board-sync)

## Summary

The flight schematic generator (`build_flight_sch.py`) had 7 netless pads annotated
with `TODO(unverified)` because the previous task refused to invent datasheet values.
This task resolved all 7 from actual vendor documents:

- NiceRF LoRa2021 module datasheet V1.3 (bare 18-pad Gen4 module) §7
- Semtech LR2021/LR2022/LR2012 datasheet v2.2 §23.5 "Unused Pins", §1.9.2/§1.9.3
- u-blox MAX-M10S Integration Manual UBX-20053088 R05 Table 1, §4.1.2, §3.2.3.2
- TI TPS7A02 datasheet SBVS277C Table 5-1

All 7 pins are prescribed by the relevant document to be **left unconnected / left
open / leave floating**. The board of record already leaves them netless, so the
schematic now documents the function and cites the source rather than carrying a
`TODO(unverified)`.

## 1. Per-pin resolution

| Pin | Function | Prescribed treatment | Citation |
|-----|----------|---------------------|----------|
| U2.10 | 2.4G/S-band antenna port (ANT_2G4) | leave unconnected | NiceRF LoRa2021 DS V1.3 §7; Semtech LR2021 DS v2.2 §23.5 "Unused RF pins: Leave unconnected" |
| U2.13 | VTCXO (TCXO/NTC supply output) | leave unconnected (output, no external TCXO on board) | NiceRF LoRa2021 DS V1.3 §7; Semtech LR2021 DS v2.2 §1.9.2/§1.9.3 |
| U2.16 | DIO8 multipurpose I/O | leave unconnected | NiceRF LoRa2021 DS V1.3 §7; Semtech LR2021 DS v2.2 §23.5 "Unused DIOs: Leave unconnected" |
| U2.17 | DIO7 multipurpose I/O | leave unconnected | NiceRF LoRa2021 DS V1.3 §7; Semtech LR2021 DS v2.2 §23.5 "Unused DIOs: Leave unconnected" |
| U3.15 | VIO_SEL (I/O voltage selector) | leave open (3.3 V design) | u-blox MAX-M10S IM UBX-20053088 R05 Table 1, §4.1.2 |
| U3.18 | SAFEBOOT_N | leave open (normal operation) | u-blox MAX-M10S IM UBX-20053088 R05 Table 1, §3.2.3.2 |
| U4.4 | NC (no-connect pin, SOT-23-5 DBV) | connect to GND or leave floating | TI TPS7A02 DS SBVS277C Table 5-1 |

### Key datasheet excerpts

u-blox MAX-M10S Integration Manual UBX-20053088 R05, Table 1:

> 15 VIO_SEL — Voltage selector for V_IO supply — Connect to GND for 1.8 V
> supply, or leave open for 3.3 V supply.

> 18 SAFEBOOT_N — Safeboot mode — To enter safeboot mode, set this pin to low
> at receiver's startup. Otherwise, leave it open.

u-blox MAX-M10S Integration Manual UBX-20053088 R05, §4.1.2:

> V_IO allows two voltage ranges, 1.8 V or 3.3 V operation. For 1.8 V designs,
> the VIO_SEL pin must be connected to GND. For 3.3 V designs, it must be left
> open.

Semtech LR2021/LR2022/LR2012 datasheet v2.2, §23.5:

> Unused RF pins: Leave unconnected
> Unused DIOs: Leave unconnected

TI TPS7A02 datasheet SBVS277C, Table 5-1 Pin Functions (DBV):

> NC — 4 — No connect pin. This pin is not internally connected. Connect to
> ground or leave floating.

## 2. Generator changes

- `LR2021_PINS`: updated floating pad names to datasheet names
  - pad 10: PAD10 → ANT_2G4
  - pad 13: PAD13 → VTCXO
  - pad 16: PAD16 → DIO8
  - pad 17: PAD17 → DIO7
- `DECLARED_GAP` renamed to `RESOLVED_NC`. Each entry now holds a vendor citation
  instead of `TODO(unverified): ...`.
- `check_sch_gates.py` GATE 4 updated to report `RESOLVED_NC` instead of
  `DECLARED_GAP`.
- Schematic annotation text changed from "GAP ... TODO(unverified)" to
  "RESOLVED ... <citation>".

## 3. Regeneration and gate verification

Observed `check_sch_gates.py` output:

```
== GATE 6: generator determinism ==
   build exit=0/0  sha256 run1=92b3e007e54dcde1 run2=92b3e007e54dcde1  (152251 bytes)
   deterministic: byte-identical across two runs
   schematic sha256 = 92b3e007e54dcde1bee8d19cf18a0bd6d7cf3f9f721a8a5a89779df865a25328
== GATE 0: schematic loads (kicad-cli sch erc) ==
   exit=0  Saved ERC Report to v_c3_flight-erc.rpt
== GATE 1: ERC severity ==
   strict exit=5  errors=0 warnings=1  kinds=['pin_to_pin']
   NOTE: 1 warning(s) only: ['pin_to_pin']
== GATE 2: net parity ==
   nets: schematic=24 pcb=24  only-in-schematic=none  only-in-pcb=none
== GATE 3: node (ref,pin) parity ==
   nodes: schematic=98 pcb=98  nets-with-differing-nodes=0
== GATE 4: netless pads classified ==
   total=27  unnamed-mechanical=13  INTENTIONAL=7  RESOLVED_NC=7  unclassified=0
== GATE 5: pad coverage ==
   build_flight_sch.py exit=0 (2 = a pad has no symbol pin)

ALL GATES PASS
```

The 1 ERC warning is the pre-existing cosmetic `pin_to_pin` mismatch
(U5 SDO bidirectional on PWR_FLAG) — not a connectivity error.

Netlist component count:

```bash
$ grep -c '(comp (ref "' tracker/hardware/schematics/flight_board/v_c3_flight.net
28
```

Distinct nets: 24.

U5 is still MS5611-01BA:

```
(comp (ref "U5")
  (value "MS5611-01BA")
  (footprint "Package_LGA:LGA-8_3x5mm_P1.25mm")
```

## 4. TODO(unverified) count

Before: 7 `TODO(unverified)` markers in `v_c3_flight.kicad_sch`.  
After: 0 `TODO(unverified)` markers.

Verified with:

```bash
$ grep -oh 'TODO(unverified)[^"]*' tracker/hardware/schematics/flight_board/*.kicad_sch | sort -u
(none)
```

## 5. Files touched (explicit git add list)

- `tracker/hardware/schematics/flight_board/build_flight_sch.py`
- `tracker/hardware/schematics/flight_board/check_sch_gates.py`
- `tracker/hardware/schematics/flight_board/v_c3_flight.kicad_sch`
- `tracker/hardware/schematics/flight_board/v_c3_flight.net`
- `tracker/hardware/schematics/flight_board/v_c3_flight-erc.rpt`
- `tracker/hardware/schematics/flight_board/sym-lib-table`
- `tracker/hardware/schematics/flight_board/balloon_flight.kicad_sym`
- `tracker/hardware/schematics/flight_board/balloon_flight.pretty/*.kicad_mod`

And root docs:

- `PROGRESS.md`
- `REPORT.md`

## 6. Commit and remote SHAs

Observed in tool output (tip of `pr/v8k-sch-board-sync`):

```
$ git rev-parse HEAD
59b2d65e4ccd1a3dbed3d57ae7e99a2faa53b2db

$ git ls-remote github refs/heads/pr/v8k-sch-board-sync
59b2d65e4ccd1a3dbed3d57ae7e99a2faa53b2db\trefs/heads/pr/v8k-sch-board-sync

$ git ls-remote ngit refs/heads/pr/v8k-sch-board-sync
59b2d65e4ccd1a3dbed3d57ae7e99a2faa53b2db\trefs/heads/pr/v8k-sch-board-sync

$ git ls-remote origin refs/heads/pr/v8k-sch-board-sync
59b2d65e4ccd1a3dbed3d57ae7e99a2faa53b2db\trefs/heads/pr/v8k-sch-board-sync
```

Local HEAD == github remote SHA == ngit remote SHA == origin remote SHA.

The main tie-off resolution commit is `59b2d65`.
