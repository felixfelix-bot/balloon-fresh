# REPORT — Schematic ↔ Board Sync (pr/v8k-sch-board-sync)

## Summary

The flight schematic generator (`build_flight_sch.py`) was frozen to the stale
`v_c3_flight_4layer_placed.kicad_pcb` (20 footprints).  The board of record is
`v8i_krt_gnss.kicad_pcb` (28 footprints, 25 nets, 4-layer, 45×55 mm, DRC-clean:
0 errors, 0 unconnected, 8 silk warnings per kicad-cli 9.0.8).  Re-pointing the
generator at the board of record brings the drawing up to the board: the 8
missing components appear, the GNSS antenna feed is closed, and several
previously-floating pins are now tied by the board itself.

## 1. The 8 added parts (Values / footprints)

All values/footprints read directly from `v8i_krt_gnss.kicad_pcb` (board of
record) — no values invented.

| Ref   | Value          | Footprint (board)                                | Symbol (schematic)              |
|-------|----------------|--------------------------------------------------|---------------------------------|
| ANT2  | U.FL_GNSS      | U.FL_Molex_MCRF_73412-0110_Vertical              | Connector:Conn_Coaxial          |
| R_SER | 0R             | R_0402_1005Metric                                | Device:R                        |
| C_SH1 | DNP            | C_0402_1005Metric                                | Device:C                        |
| C_SH2 | DNP            | C_0402_1005Metric                                | Device:C                        |
| MNT1  | MountingHole   | MountingHole_2.2mm_M2                            | Mechanical:MountingHole         |
| MNT2  | MountingHole   | MountingHole_2.2mm_M2                            | Mechanical:MountingHole         |
| MNT3  | MountingHole   | MountingHole_2.2mm_M2                            | Mechanical:MountingHole         |
| MNT4  | MountingHole   | MountingHole_2.2mm_M2                            | Mechanical:MountingHole         |

## 2. GNSS antenna feed — net wired and verification

The board of record wires the GNSS antenna path as:

```
ANT2.1 ── GNSS_ANT ── R_SER.1 ── R_SER.2 ── GNSS_RF ── U3.11 (RF_IN)
C_SH2.2 ── GNSS_ANT ── GND (C_SH2.1)     [shunt, DNP]
C_SH1.2 ── GNSS_RF  ── GND (C_SH1.1)     [shunt, DNP]
```

The generator reads these nets directly from `v8i_krt_gnss.kicad_pcb` pad
assignments:
- ANT2 pad 1 → net `GNSS_ANT` (net 24)
- R_SER pad 1 → `GNSS_ANT`, pad 2 → `GNSS_RF` (net 23)
- U3 pad 11 (RF_IN) → `GNSS_RF`
- C_SH1: GNSS_RF ↔ GND; C_SH2: GNSS_ANT ↔ GND

Verified in the kicad-cli-exported netlist:
```
/net "GNSS_ANT": ANT2.1, C_SH2.2, R_SER.1
/net "GNSS_RF":  C_SH1.2, R_SER.2, U3.11 (RF_IN)
```

The previous annotation "RF_IN, no GPS antenna feed on this board" is **gone**
(0 matches in the regenerated `.kicad_sch`) — U3.11 now has a net, so the gap
annotation no longer fires.

## 3. Per-pin resolution of the 7 floating pins

The task listed 7 floating pins from the *previous* drawing (which mirrored the
stale 4-layer board).  Re-pointing at v8i changes which pads are actually
floating, because the board of record already tied several of them.  Every
resolution below is either (a) a board-observed net or (b) an explicit
`TODO(unverified)` note — no datasheet value was invented.

| Pin      | Resolution                                                                 | Citation / TODO                                                                 |
|----------|----------------------------------------------------------------------------|---------------------------------------------------------------------------------|
| U2.10    | Left floating; `TODO(unverified): LoRa2021 Gen4 pad 10 function/termination` | Never tie a 2 W PA module pin on a guess (option ii).                           |
| U2.13    | Left floating; `TODO(unverified): LoRa2021 Gen4 pad 13 function/termination` | Never tie a 2 W PA module pin on a guess (option ii).                           |
| U2.16    | Left floating; `TODO(unverified): LoRa2021 Gen4 pad 16 function/termination` | Never tie a 2 W PA module pin on a guess (option ii).                           |
| U2.17    | Left floating; `TODO(unverified): LoRa2021 Gen4 pad 17 function/termination` | Never tie a 2 W PA module pin on a guess (option ii).                           |
| U3.9 ~RESET | **Resolved by the board**: U3.9 is tied to `+3V3` (pull-up) in v8i.   | Board netlist (v8i_krt_gnss.kicad_pcb pad 9 → net +3V3). No datasheet needed — the board already ties it. |
| U3.15 VIO_SEL | Left floating; `TODO(unverified): MAX-M10S VIO_SEL tie-off required`  | u-blox MAX-M10S integration manual not sourced in time (option ii).             |
| U3.18 ~SAFEBOOT | Left floating; `TODO(unverified): MAX-M10S ~SAFEBOOT inactive level tie-off required` | u-blox MAX-M10S integration manual not sourced in time (option ii).       |

**Note on U2 pin numbers:** the task listed U2.7/11/15/16 (the 16-pad
HOPERF_RFM9xW footprint).  The board of record uses the 18-pad
`LoRa2021_Castellated` footprint with a different pad numbering; its
floating pads are 10/13/16/17.  These are the same "unmodelled RF module"
concerns under the new pad numbers.

**Additional gap pin (U4.4):** the board of record also leaves U4.4 (TPS7A02
pin 4) floating.  It carries a `TODO(unverified): TPS7A02 pin 4 function /
tie-off` annotation.  U4.3 (EN) is now tied to VCAP by the board (no longer
floating).

## 4. Before / after component counts

| Metric              | Before (ba73bb9) | After    |
|---------------------|------------------|----------|
| Netlist components  | 20               | **28**   |
| Distinct nets       | 22               | 24       |
| Schematic size      | 117 790 bytes    | 151 712 bytes |

Count method: **kicad-cli `sch export netlist`** (the same tool the
`check_sch_gates.py` GATE 0/1/2/3 suite uses).  This is stronger than a
hand-rolled count — the netlist is emitted by kicad-cli 9.0.8 itself from the
regenerated `.kicad_sch`.

```
$ grep -c '(comp (ref "' v_c3_flight.net
28
```

All 28 refs: ANT1 ANT2 C1 C2 C3 C4 C_CAP C_SH1 C_SH2 D1 J1 J2 LED1 MNT1 MNT2
MNT3 MNT4 R_DIV1 R_DIV2 R_LED R_PD R_SER SOLAR U1 U2 U3 U4 U5.

## 5. U5 still MS5611 (no regression)

```
(comp (ref "U5")
  (value "MS5611-01BA")
  (footprint "Package_LGA:LGA-8_3x5mm_P1.25mm")
```

The MS5611 value/footprint override is preserved.  The *symbol* is
`Sensor:BME280` (not `Sensor_Pressure:MS5611-01BA`) because the BME280 symbol
shares the BMP280 clockwise LGA-8 pad numbering that the board is physically
wired for; the MS5611-01BA symbol has a different pin numbering that would
mismatch the board pads.  This matches the approach used in the previous
(ba73bb9) netlist, which also used `Sensor:BME280` as the libpart with the
MS5611 value/footprint override.

## 6. Gate verification (check_sch_gates.py)

```
== GATE 6: generator determinism ==       PASS (byte-identical across 2 runs)
== GATE 0: schematic loads (kicad-cli) == PASS (exit 0)
== GATE 1: ERC severity ==                PASS (0 errors, 1 warning [pin_to_pin])
== GATE 2: net parity ==                  PASS (schematic=24 pcb=24, no diffs)
== GATE 3: node (ref,pin) parity ==       PASS (98 nodes both, 0 mismatches)
== GATE 4: netless pads classified ==     PASS (27 total, 0 unclassified)
== GATE 5: pad coverage ==                PASS (build exit 0)
ALL GATES PASS
```

The single ERC warning is a cosmetic pin-type mismatch (U5 SDO bidirectional
connected to PWR_FLAG power output) — not a connectivity error.

## 7. Commit and remote SHAs

Observed in tool output:

```
$ git rev-parse HEAD
cdb4d8e970f8299704e7f8dc36745b611091c1c3

$ git ls-remote github refs/heads/pr/v8k-sch-board-sync
cdb4d8e970f8299704e7f8dc36745b611091c1c3	refs/heads/pr/v8k-sch-board-sync

$ git ls-remote ngit refs/heads/pr/v8k-sch-board-sync
cdb4d8e970f8299704e7f8dc36745b611091c1c3	refs/heads/pr/v8k-sch-board-sync
```

Local HEAD == github remote SHA == ngit remote SHA.

## 8. Files touched (explicit git add list)

```
tracker/hardware/schematics/flight_board/build_flight_sch.py
tracker/hardware/schematics/flight_board/v_c3_flight.kicad_sch
tracker/hardware/schematics/flight_board/v_c3_flight.net
tracker/hardware/schematics/flight_board/v_c3_flight-erc.rpt
tracker/hardware/schematics/flight_board/sym-lib-table
tracker/hardware/schematics/flight_board/balloon_flight.kicad_sym
tracker/hardware/schematics/flight_board/balloon_flight.pretty/LoRa2021_Castellated.kicad_mod
tracker/hardware/schematics/flight_board/balloon_flight.pretty/MountingHole_2.2mm_M2.kicad_mod
tracker/hardware/schematics/flight_board/balloon_flight.pretty/CP_Radial_D10.0mm_P5.00mm.kicad_mod
tracker/hardware/schematics/flight_board/balloon_flight.pretty/C_0402_1005Metric.kicad_mod
tracker/hardware/schematics/flight_board/balloon_flight.pretty/D_SOD-123.kicad_mod
tracker/hardware/schematics/flight_board/balloon_flight.pretty/ESP32-C3-WROOM-02.kicad_mod
tracker/hardware/schematics/flight_board/balloon_flight.pretty/R_0402_1005Metric.kicad_mod
tracker/hardware/schematics/flight_board/balloon_flight.pretty/SOT-23-5.kicad_mod
tracker/hardware/schematics/flight_board/balloon_flight.pretty/ublox_MAX.kicad_mod
```

## 9. Unresolved items

- **U3.15 VIO_SEL and U3.18 ~SAFEBOOT** remain floating with `TODO(unverified)`
  annotations.  The u-blox MAX-M10S integration manual was not sourced in time
  to apply the datasheet-prescribed tie-off.  A follow-up with the integration
  manual (UBX-20036124 or equivalent) should resolve these.
- **U2.10/13/16/17** (LoRa2021 Gen4 castellated pads) remain floating with
  `TODO(unverified)` annotations.  The NiceRF LR2021 Gen4 datasheet is needed
  to determine whether these are NC, GND tabs, or I/O requiring termination.
  Never tie a 2 W PA module pin on a guess.
- **U4.4** (TPS7A02 pin 4) remains floating with `TODO(unverified)`.
- **U2 footprint change**: the board of record uses the 18-pad
  `LoRa2021_Castellated` footprint (Gen4 module) instead of the 16-pad
  `HOPERF_RFM9XW_SMD`.  The schematic now mirrors this.  The pin names for the
  connected pads are derived from the board net names (ground truth); the
  floating pads are left neutral (`PAD10/PAD13/PAD16/PAD17`).