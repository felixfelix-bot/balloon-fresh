# v9 balloon flight board - Bill of Materials

**Source of truth:** `tracker/hardware/schematics/flight_board/v9_flight.net` (exported from `tracker/hardware/schematics/flight_board/v9_flight.kicad_sch`).

**GENERATED FILE - do not hand-edit.** Regenerate with:

```sh
python3 scripts/gen_v9_bom.py
```

Every column except FUNCTION is read out of the netlist. The FUNCTION column
and the ratings section are prose authored against in-repo sources; anything with
no source carries `TODO(unverified)`.

**Total component count: 46** (single hub+4-wing variant; netlist exports 51 nets). Count the rows below against `grep -c '(comp (ref ' tracker/hardware/schematics/flight_board/v9_flight.net` if you want to check this table against the schematic itself.

Title block on the schematic: *Balloon v9 Tri-Band Flight Board*, rev *v9-design-intent*.

> **Configurations.** This is the **A** variant population (hub + 4 wings). **Variant B** is hub-only - no wings, no cut, target <20 g payload - in which `J_W1..J_W4`, `D_BP1..D_BP4`, `U_CUT1..U_CUT4` go unpopulated but stay on the board. The netlist carries the superset; it does not distinguish the two.

## Bill of materials

| # | Reference | Value | Footprint / library id | DNP | Function |
|---:|---|---|---|---|---|
| 1 | `ANT1` | `U.FL_433_TX` | `Connector_Coaxial : U.FL_Molex_MCRF_73412-0110_Vertical` / `Connector:Conn_Coaxial` | populated | 433 MHz DOWNLINK U.FL coaxial tap for the F33 sub-GHz port; hub wire dipole (ADR-009, ADR-034). |
| 2 | `ANT2` | `U.FL_2G4_RANGE` | `Connector_Coaxial : U.FL_Molex_MCRF_73412-0110_Vertical` / `Connector:Conn_Coaxial` | populated | 2.4 GHz U.FL coaxial tap for the F33's second 50 ohm port (TX/RX); hub wire dipole. |
| 3 | `ANT3` | `U.FL_2G4_RX` | `Connector_Coaxial : U.FL_Molex_MCRF_73412-0110_Vertical` / `Connector:Conn_Coaxial` | populated | 2.4 GHz UPLINK-RX U.FL coaxial tap for the bare LoRa2021 receiver; hub wire dipole. |
| 4 | `ANT4` | `U.FL_GNSS_L1` | `Connector_Coaxial : U.FL_Molex_MCRF_73412-0110_Vertical` / `Connector:Conn_Coaxial` | populated | GNSS L1 U.FL coaxial tap for the MAX-M10S; hub wire dipole with ground plane. |
| 5 | `C4` | `10uF` | `Capacitor_SMD : C_0402_1005Metric` / `Device:C` | populated | GNSS rail decoupling on GNSS_VCC, after the R_F1 series element. |
| 6 | `C_BULK` | `100uF` | `Capacitor_SMD : C_1206_3216Metric` / `Device:C` | populated | 100 uF bulk reservoir on F33_VCC so the 1100 mA PA burst does not sag the rail. |
| 7 | `C_CAP1` | `3.3F 2.7V (AVX SCC)` | `Capacitor_THT : CP_Radial_D10.0mm_P5.00mm` / `Device:C_Polarized` | populated | Supercapacitor bank cell 1 (top of the series pair) - the only energy store; no battery. |
| 8 | `C_CAP2` | `3.3F 2.7V (AVX SCC)` | `Capacitor_THT : CP_Radial_D10.0mm_P5.00mm` / `Device:C_Polarized` | populated | Supercapacitor bank cell 2 (bottom of the series pair, cold end at GND). |
| 9 | `C_HF` | `100nF` | `Capacitor_SMD : C_0402_1005Metric` / `Device:C` | populated | 100 nF HF decoupling on F33_VCC at the module pin. |
| 10 | `C_MON` | `10nF` | `Capacitor_SMD : C_0402_1005Metric` / `Device:C` | populated | Filter/storage cap on the F33_VSENSE divider tap feeding the ESP32 ADC. |
| 11 | `D1` | `BAT54` | `Diode_SMD : D_SOD-123` / `Device:D_Schottky` | populated | BAT54 series-blocking Schottky at the wing-string output (ADR-006); defines VSCAP, the pre-LDO node. |
| 12 | `D_BP1` | `SS24` | `Diode_SMD : D_SMA` / `Device:D_Schottky` | populated | Per-interface bypass Schottky across J_W1 SOLAR_P..SOLAR_N; a cracked/shaded wing costs one wing, not the string (ADR-053). |
| 13 | `D_BP2` | `SS24` | `Diode_SMD : D_SMA` / `Device:D_Schottky` | populated | Per-interface bypass Schottky across J_W2 SOLAR_P..SOLAR_N (ADR-053). |
| 14 | `D_BP3` | `SS24` | `Diode_SMD : D_SMA` / `Device:D_Schottky` | populated | Per-interface bypass Schottky across J_W3 SOLAR_P..SOLAR_N (ADR-053). |
| 15 | `D_BP4` | `SS24` | `Diode_SMD : D_SMA` / `Device:D_Schottky` | populated | Per-interface bypass Schottky across J_W4 SOLAR_P..SOLAR_N; its cathode side sits on the GND-referenced end of the string (ADR-053). |
| 16 | `D_CLAMP` | `TVS clamp (set point TODO(unverified))` | `Diode_SMD : D_SOD-323` / `Device:D_TVS` | populated | TVS shunt clamp on the raw supercap node; set point TODO(unverified) (must conduct above the 5.4 V bank top, ADR-047). |
| 17 | `D_HUB1` | `SS24` | `Diode_SMD : D_SMA` / `Device:D_Schottky` | populated | Bypass Schottky for the hub array's upper cell (PVA1) - hub string is INDEPENDENT of the wing string (ADR-051). |
| 18 | `D_HUB2` | `SS24` | `Diode_SMD : D_SMA` / `Device:D_Schottky` | populated | Bypass Schottky for the hub array's lower cell (PVA2) - hub string is INDEPENDENT of the wing string (ADR-051). |
| 19 | `J_VCC` | `F33_VCC_SEL (5V raw \| 3V3)` | `Jumper : SolderJumper-3_P1.3mm_Open_RoundedPad1.0x1.5mm` / `balloon_flight_v9:F33_VCC_SEL` | populated | 3-way solder jumper selecting the F33 rail: pin 1 = VSCAP (raw ~5.4 V, PRE-REGULATOR), pin 2 = F33_VCC, pin 3 = +3V3 (ADR-047). |
| 20 | `J_W1` | `WING_SOCKET_4P (hub wing interface 1)` | `Tracker_Mechanical : Wing_Tab_4P` / `balloon_flight_v9:WING_SOCKET_4P` | populated | Wing 1 jettisonable socket, 4-pin: 1 SOLAR_P, 2 GND, 3 RF_FEED (reused as CUT_SENSE_W1), 4 SOLAR_N (ADR-046/048). |
| 21 | `J_W2` | `WING_SOCKET_4P (hub wing interface 2)` | `Tracker_Mechanical : Wing_Tab_4P` / `balloon_flight_v9:WING_SOCKET_4P` | populated | Wing 2 jettisonable socket, 4-pin (pin 1 ties to the W1 SOLAR_N hub link: the wings are ONE series string). |
| 22 | `J_W3` | `WING_SOCKET_4P (hub wing interface 3)` | `Tracker_Mechanical : Wing_Tab_4P` / `balloon_flight_v9:WING_SOCKET_4P` | populated | Wing 3 jettisonable socket, 4-pin (pin 1 ties to the W2 SOLAR_N hub link). |
| 23 | `J_W4` | `WING_SOCKET_4P (hub wing interface 4)` | `Tracker_Mechanical : Wing_Tab_4P` / `balloon_flight_v9:WING_SOCKET_4P` | populated | Wing 4 jettisonable socket, 4-pin (pin 4 SOLAR_N is the string's GND end). |
| 24 | `PVA1` | `SolarCell_78x39mm` | `—` / `balloon_flight_v9:PVA_CELL` | populated | Hub solar array cell 1 of 2 (SolarCell_78x39mm): a separate, independent series string (ADR-051). |
| 25 | `PVA2` | `SolarCell_78x39mm` | `—` / `balloon_flight_v9:PVA_CELL` | populated | Hub solar array cell 2 of 2 (SolarCell_78x39mm); series with PVA1 via HUB_PV_MID1. |
| 26 | `R_BAL1` | `10k` | `Resistor_SMD : R_0402_1005Metric` / `Device:R` | populated | Balancing/pull resistor from VSCAP to the SCAP_MID tap (bank midpoint monitoring and leakage balance). |
| 27 | `R_BAL2` | `10k` | `Resistor_SMD : R_0402_1005Metric` / `Device:R` | populated | Balancing/pull resistor from SCAP_MID to GND (completes the bank midpoint divider). |
| 28 | `R_DIV1` | `1M` | `Resistor_SMD : R_0402_1005Metric` / `Device:R` | populated | Upper leg of the supercap voltage divider to SCAP_ADC (1 M/1 M avoided: 1 M/1 M costs 14.6 uW, ADR-047). |
| 29 | `R_DIV2` | `1M` | `Resistor_SMD : R_0402_1005Metric` / `Device:R` | populated | Lower leg of the supercap voltage divider to SCAP_ADC and GND. |
| 30 | `R_F1` | `100R` | `Resistor_SMD : R_0402_1005Metric` / `Device:R` | populated | 100R series filter/limiter between the 3V3 rail and GNSS_VCC. |
| 31 | `R_MON1` | `4.7M` | `Resistor_SMD : R_0402_1005Metric` / `Device:R` | populated | Upper leg of the F33_VSENSE divider on the F33 rail (4.7 M, chosen so bias stays at the 100 uW night-anchor scale, ADR-047). |
| 32 | `R_MON2` | `4.7M` | `Resistor_SMD : R_0402_1005Metric` / `Device:R` | populated | Lower leg of the F33_VSENSE divider to GND (4.7 M/4.7 M = 9.4 M total, 5.4 V/9.4 M = 0.574 uA = 3.1 uW). |
| 33 | `R_NTC1` | `TODO(unverified) (sets ntc_r_ratio)` | `Resistor_SMD : R_0402_1005Metric` / `Device:R` | **DNP** | NTC bias/series resistor from the bare LoRa2021 VTCXO pad; **DNP** - the pads have NO path back to the chip on the owned module (ADR-059). |
| 34 | `TH_NTC1` | `TODO(unverified) (NTC, R25/beta TODO)` | `Resistor_SMD : R_0402_1005Metric` / `Device:Thermistor_NTC` | **DNP** | NTC thermistor on NTC_SENSE for the on-chip temperature-compensation provision; **DNP** (ADR-059). |
| 35 | `U1` | `ESP32-S3-WROOM-1U-N8R8` | `RF_Module : ESP32-S3-WROOM-1U` / `RF_Module:ESP32-S3-WROOM-1` | populated | ESP32-S3-WROOM-1U-N8R8 MCU: 8 MB flash + 8 MB PSRAM on-module; flash is the persistent log, PSRAM may only stage (ADR-061). |
| 36 | `U2` | `LoRa2021F33-2G4` | `balloon_flight_v9 : LoRa2021F33_2G4` / `balloon_flight_v9:F33_2G4` | populated | LoRa2021F33-2G4 - 433 MHz DOWNLINK TX, internal 0.5 ppm TCXO, +33 dBm / ~1100 mA at 5 V; MUST be fed pre-regulator (ADR-034/047). |
| 37 | `U3` | `LoRa2021_Castellated` | `balloon_flight_v9 : LoRa2021_Castellated` / `balloon_flight_v9:LR2021_BARE` | populated | LoRa2021 (bare, castellated) - 2.4 GHz UPLINK RX, crystal only (no TCXO), 1.8-3.6 V (ADR-034). |
| 38 | `U4` | `SX1280` | `balloon_flight_v9 : SX1280_QFN24` / `balloon_flight_v9:SX1280` | populated | SX1280 - 2.4 GHz RANGING only: not a link carrier and not the timing authority (ADR-060). |
| 39 | `U5` | `MAX-M10S` | `RF_GPS : ublox_MAX` / `RF_GPS:MAX-M10S` | populated | MAX-M10S GNSS receiver; its 1PPS on TIMEPULSE is the zero-gram clock-discipline source (ADR-056 D3). |
| 40 | `U6` | `MS5611-01BA` | `Package_LGA : LGA-8_3x5mm_P1.25mm` / `balloon_flight_v9:MS5611_BARO` | populated | MS5611-01BA barometer on I2C. NOTE: ADR-108 names MS5607-02BA03 - see discrepancy note below. |
| 41 | `U7` | `TPS7A02` | `Package_TO_SOT_SMD : SOT-23-5` / `balloon_flight_v9:TPS7A0233` | populated | TPS7A0233 LDO producing the 3V3 rail from VSCAP; rated ~200 mA (KiCad lib) / 300 mA (ADR-006) and CANNOT feed the F33. |
| 42 | `U_CUT1` | `latched cut driver + cut-sense (part TODO(unverified))` | `—` / `balloon_flight_v9:CUT_CHANNEL` | populated | Latched cut driver for wing 1 (nichrome), powered from the post-BAT54/pre-LDO VSCAP node so a cut still works with the converter dead. |
| 43 | `U_CUT2` | `latched cut driver + cut-sense (part TODO(unverified))` | `—` / `balloon_flight_v9:CUT_CHANNEL` | populated | Latched cut driver for wing 2 (nichrome); VSCAP-powered. |
| 44 | `U_CUT3` | `latched cut driver + cut-sense (part TODO(unverified))` | `—` / `balloon_flight_v9:CUT_CHANNEL` | populated | Latched cut driver for wing 3 (nichrome); VSCAP-powered. |
| 45 | `U_CUT4` | `latched cut driver + cut-sense (part TODO(unverified))` | `—` / `balloon_flight_v9:CUT_CHANNEL` | populated | Latched cut driver for wing 4 (nichrome); VSCAP-powered. |
| 46 | `U_HUB_CVT` | `HUB_PV input (part TODO(unverified))` | `—` / `balloon_flight_v9:HUB_CONVERTER` | populated | HUB_CONVERTER - TPS63060-class buck-boost on the hub array input (HUB_PV_P/HUB_PV_N). Output net is TODO(unverified) in this netlist. |

### Do-not-populate parts

2 of 46 parts are marked DNP in the schematic: `R_NTC1`, `TH_NTC1`.

**Why - `R_NTC1` / `TH_NTC1` (ADR-059):** the provision is the LR2021's on-chip NTC
temperature compensation, biased from the bare module's `VTCXO` pad (net `/VTCXO_VNTC`).
ADR-059 records that **the sense node has no path back to the chip on the owned bare
module** - the module's 18 castellations expose no `NTC` pad, so the loop cannot be
closed. The pads stay on the board (the `NTC_SENSE` net exists: `R_NTC1.2` /
`TH_NTC1.1`) so the provision can be populated if the module break-out is ever
confirmed. Source: `docs/adr/059-ntc-temp-compensation-provision.md:333,371-375`.

---

## Parts and their key ratings

The numbers that matter when ordering. Each row cites its in-repo source.

| Item | Rating / figure | Source |
|---|---|---|
| F33 (U2) RF output | +33 dBm (2 W) on the sub-GHz port; 5 V for full power | `docs/adr/047-v9-power-provisioning.md:67` (5.0 V / 33.0 dBm / 1100 mA) |
| F33 (U2) TX supply current | 1100 mA at 5 V (datasheet round bound <1200 mA) | `docs/adr/047-v9-power-provisioning.md:67,104` |
| F33 (U2) reference | internal TCXO, 0.5 ppm | `docs/V9-RADIO-SITE-MATRIX.md` §2 variant census |
| F33 (U2) rail feed | **PRE-REGULATOR from the raw storage node (VSCAP)**, selected by `J_VCC` pin 1 | `docs/adr/047-v9-power-provisioning.md:125-153` (`pin 1 = VSCAP (raw cap rail, ~5.4 V) ← F33 position`) |
| Why not the LDO | TPS7A02 recorded rating **≤300 mA** (ADR-006) / **200 mA** (KiCad lib symbol). 1118 mA ÷ 200 mA = **5.59× over** - a pre-regulator-class LDO CANNOT feed the F33 | `docs/adr/047-v9-power-provisioning.md:167-172` |
| Bare LoRa2021 (U3) rail | 1.8-3.6 V (3.3 V); crystal only, **no TCXO, no NTC** | `docs/V9-RADIO-SITE-MATRIX.md` §2; `docs/adr/034-radio-band-split-433-tx-2g4-rx.md` |
| Bypass Schottky D_BP1..D_BP4 (SS24) | **2 A / 40 V**, populated, hub-side | `docs/adr/049-wing-architecture.md:76-78` (≥2 A / 40 V, SS24 or PMEG4020ER class); `docs/adr/053-per-cell-bypass-diodes.md` |
| Bypass Schottky D_HUB1/D_HUB2 (SS24) | **2 A / 40 V**, populated, hub array | same rating class as ADR-049:76-78; hub string per `docs/adr/051-hub-array-and-cut-topology.md:213` |
| Supercapacitor bank C_CAP1/C_CAP2 | 2 × AVX SCC **3.3 F 2.7 V** series = **1.65 F @ ≤5.4 V** (24.06 J full); doubled bank **3.3 F** = **33.264 J usable** (5.4 → 3.0 V). **No battery.** `docs/adr/006-supercapacitor-power.md`, `docs/adr/047-v9-power-provisioning.md:218-228` | `docs/POWER-BUDGET-V9-D2BE.md:41,44`; `docs/adr/047-v9-power-provisioning.md:218-221,526-527` |
| Wing solar array | 4 wings × 3 LARGE cells = **12 cells in ONE series string**, **6.0 V nominal @ 1.2 A ≈ 7.2 W peak** | `docs/adr/051-hub-array-and-cut-topology.md:75`; `docs/adr/049-wing-architecture.md:43-44` |
| Wing string cold Voc | ≈**9.58 V at −60 °C** (items the bypass diodes' 40 V rating) | `docs/adr/051-hub-array-and-cut-topology.md:512` |
| Hub array | INDEPENDENT series string (PVA1/PVA2), own converter input `HUB_CONVERTER` (TPS63060-class). Cutting a wing cannot kill the hub array | `docs/adr/051-hub-array-and-cut-topology.md:213` |
| Energy budget | average load **0.388 W** (day); night anchor **100 uW** (10 h = 3.6 J) | `docs/POWER-BUDGET-V9-D2BE.md:85,98,112`; `docs/adr/047-v9-power-provisioning.md:415-417` |
| Rail monitor bias R_MON1/R_MON2 | 5.4 V ÷ 9.4 MΩ = **0.574 uA = 3.1 uW** | `docs/adr/047-v9-power-provisioning.md:411,540` |
| ESP32-S3-WROOM-1U-N8R8 (U1) | **8 MB flash + 8 MB PSRAM** on-module; **no external storage part** | `docs/adr/061-onboard-storage.md`; commit `e4d0569` corrects previously wrong 16 MB claims |
| MAX-M10S (U5) | 1PPS on TIMEPULSE → ESP32 **GPIO21**; zero-gram/zero-watt clock discipline | `docs/adr/056-thermal-and-frequency-drift.md:126-141`; `docs/adr/108-f33-sx1280-pin-plan.md:38` |
| Barometer (U6) | schematic says **MS5611-01BA**; ADR-108 names **MS5607-02BA03**. Schematic wins on the drawing, discrepancy flagged | `tracker/hardware/schematics/flight_board/v9_flight.net` vs `docs/adr/108-f33-sx1280-pin-plan.md` |
| Wing socket pinout | `1 SOLAR_P / 2 GND / 3 RF_FEED / 4 SOLAR_N`; the wing string order runs W1→W2→W3→W4 with only W4_SOLAR_N on GND | `docs/adr/048-v9-hub-wing-interfaces.md:83,99-128` |
| Cut drivers U_CUT1..U_CUT4 | powered from `VSCAP` = post-`D1`(BAT54) / pre-LDO node | netlist net `/VSCAP` = {`C_CAP1.1`, `D1.1`, `J_VCC.1`, `R_BAL1.1`, `R_DIV1.1`, `U7.1`, `U7.3`, `U_CUT1..4.1`} |
| DNP parts | `R_NTC1`, `TH_NTC1` - pads have **NO path back to the chip** on the owned module | `docs/adr/059-ntc-temp-compensation-provision.md:333,371-375`; netlist `(property (name "dnp"))` |

---

## Discrepancies found while extracting this BOM (flagged, not resolved)

1. **Barometer part number.** The schematic/netlist says `U6 = MS5611-01BA`
   (footprint `Package_LGA:LGA-8_3x5mm_P1.25mm`). `docs/adr/108-f33-sx1280-pin-plan.md`
   names **MS5607-02BA03**. This BOM and the system diagram draw **MS5611-01BA**
   because that is what the schematic says. Operator to reconcile.
2. **Bypass diode part family, rating and DNP state.** ADR-048 §2.3 specifies
   "BAT54 family, SOD-323, **DNP for the first prototype**". ADR-049:76-78 re-rates
   the requirement to **≥2 A / 40 V (SS24 or PMEG4020ER class)** because BAT54's
   200 mA / 30 V is undersized against the 1.2 A LARGE-cell string. The schematic
   follows ADR-049: `D_BP1..D_BP4` are **SS24 in `Diode_SMD:D_SMA`, populated**, and
   the netlist marks **no** DNP flag on them. ADR-048's text is therefore stale.
3. **Wing pin 3 `RF_FEED`.** ADR-048 §2.3 states pin 3 "carries NO net on v9". The
   netlist wires it: `/CUT_SENSE_W<n>` = {`J_W<n>.3`, `U_CUT<n>.3`}. The cut-continuity
   sense therefore **does** reuse the RF_FEED line on this design, as the design intent
   requires - but the ERC still reports the four `J_W<n>` pin-3 pads, so read the
   ERC count as "expected baseline", not as a defect.
4. **`U_HUB_CVT` has no output net.** The netlist gives `HUB_CONVERTER` only
   `HUB_PV_P` (pin 1), `GND` (pin 2) and `HUB_PV_N` (pin 3). No rail on the output
   side is assigned: **TODO(unverified)** - which rail the hub converter feeds, and
   whether it parallels the wing string into `VSCAP` or drives `+3V3`, is not in the
   netlist. Verify against `docs/adr/051-hub-array-and-cut-topology.md` before layout.
5. **ERC.** `v9_flight-erc.rpt` (2026-10-07T16:35:38) reports **23 errors, 0 warnings**,
   all of them `pin_not_connected` (deliberate provision/`TODO(unverified)` pins such
   as `U3` pads 16/17, `U4` VDD_IN/VDD_IO/RFIO, `U6` PS/SDO/CSB). No short or drive
   conflict is reported.

Per-reference nets (for auditing any row above against the schematic):

| Reference | Nets |
|---|---|
| `ANT1` | `/ANT1_433_TX`, `GND` |
| `ANT2` | `/ANT2_2G4_RANGE`, `GND` |
| `ANT3` | `/ANT3_2G4_RX`, `GND` |
| `ANT4` | `/ANT4_GNSS_L1`, `GND` |
| `C4` | `/GNSS_VCC`, `GND` |
| `C_BULK` | `/F33_VCC`, `GND` |
| `C_CAP1` | `/SCAP_MID`, `/VSCAP` |
| `C_CAP2` | `/SCAP_MID`, `GND` |
| `C_HF` | `/F33_VCC`, `GND` |
| `C_MON` | `/F33_VSENSE`, `GND` |
| `D1` | `/VSCAP`, `/W1_SOLAR_P` |
| `D_BP1` | `/W1_SOLAR_N`, `/W1_SOLAR_P` |
| `D_BP2` | `/W1_SOLAR_N`, `/W2_SOLAR_N` |
| `D_BP3` | `/W2_SOLAR_N`, `/W3_SOLAR_N` |
| `D_BP4` | `/W3_SOLAR_N`, `GND` |
| `D_CLAMP` | `/F33_VCC`, `GND` |
| `D_HUB1` | `/HUB_PV_MID1`, `/HUB_PV_P` |
| `D_HUB2` | `/HUB_PV_MID1`, `/HUB_PV_N` |
| `J_VCC` | `+3V3`, `/F33_VCC`, `/VSCAP` |
| `J_W1` | `/CUT_SENSE_W1`, `/W1_SOLAR_N`, `/W1_SOLAR_P`, `GND` |
| `J_W2` | `/CUT_SENSE_W2`, `/W1_SOLAR_N`, `/W2_SOLAR_N`, `GND` |
| `J_W3` | `/CUT_SENSE_W3`, `/W2_SOLAR_N`, `/W3_SOLAR_N`, `GND` |
| `J_W4` | `/CUT_SENSE_W4`, `/W3_SOLAR_N`, `GND`, `GND` |
| `PVA1` | `/HUB_PV_MID1`, `/HUB_PV_P` |
| `PVA2` | `/HUB_PV_MID1`, `/HUB_PV_N` |
| `R_BAL1` | `/SCAP_MID`, `/VSCAP` |
| `R_BAL2` | `/SCAP_MID`, `GND` |
| `R_DIV1` | `/SCAP_ADC`, `/VSCAP` |
| `R_DIV2` | `/SCAP_ADC`, `GND` |
| `R_F1` | `+3V3`, `/GNSS_VCC` |
| `R_MON1` | `/F33_VCC`, `/F33_VSENSE` |
| `R_MON2` | `/F33_VSENSE`, `GND` |
| `R_NTC1` | `/NTC_SENSE`, `/VTCXO_VNTC` |
| `TH_NTC1` | `/NTC_SENSE`, `GND` |
| `U1` | `+3V3`, `/F33_BUSY`, `/F33_CS_N`, `/F33_IRQ`, `/F33_MISO`, `/F33_MOSI`, `/F33_RESET_N`, `/F33_SCK`, `/F33_VSENSE`, `/GNSS_PPS`, `/GNSS_RX`, `/GNSS_TX`, `/I2C_SCL`, `/I2C_SDA`, `/SX1280_ANT_SW`, `/SX1280_BUSY`, `/SX1280_CS_N`, `/SX1280_DIO1`, `/SX1280_DIO2`, `/SX1280_DIO3`, `/SX1280_MISO`, `/SX1280_MOSI`, `/SX1280_RESET_N`, `/SX1280_SCK`, `/U3_BUSY`, `/U3_CS_N`, `/U3_IRQ`, `/U3_RESET_N`, `GND`, `GND`, `GND` |
| `U2` | `+3V3`, `/ANT1_433_TX`, `/F33_BUSY`, `/F33_CS_N`, `/F33_IRQ`, `/F33_MISO`, `/F33_MOSI`, `/F33_RESET_N`, `/F33_SCK`, `/F33_VCC`, `GND`, `GND`, `GND`, `GND`, `GND`, `GND`, `GND` |
| `U3` | `+3V3`, `/ANT3_2G4_RX`, `/F33_MISO`, `/F33_MOSI`, `/F33_SCK`, `/U3_BUSY`, `/U3_CS_N`, `/U3_IRQ`, `/U3_RESET_N`, `/VTCXO_VNTC`, `GND`, `GND`, `GND`, `GND`, `GND` |
| `U4` | `+3V3`, `+3V3`, `/ANT2_2G4_RANGE`, `/SX1280_ANT_SW`, `/SX1280_BUSY`, `/SX1280_CS_N`, `/SX1280_DIO1`, `/SX1280_DIO2`, `/SX1280_DIO3`, `/SX1280_MISO`, `/SX1280_MOSI`, `/SX1280_RESET_N`, `/SX1280_SCK`, `GND`, `GND`, `GND`, `GND`, `GND`, `GND`, `GND`, `GND`, `GND`, `GND`, `GND`, `GND` |
| `U5` | `+3V3`, `+3V3`, `+3V3`, `/ANT4_GNSS_L1`, `/GNSS_PPS`, `/GNSS_RX`, `/GNSS_TX`, `/GNSS_VCC`, `GND`, `GND`, `GND` |
| `U6` | `+3V3`, `+3V3`, `+3V3`, `/I2C_SCL`, `/I2C_SDA`, `GND`, `GND`, `GND` |
| `U7` | `+3V3`, `/VSCAP`, `/VSCAP`, `GND` |
| `U_CUT1` | `/CUT_SENSE_W1`, `/VSCAP`, `GND` |
| `U_CUT2` | `/CUT_SENSE_W2`, `/VSCAP`, `GND` |
| `U_CUT3` | `/CUT_SENSE_W3`, `/VSCAP`, `GND` |
| `U_CUT4` | `/CUT_SENSE_W4`, `/VSCAP`, `GND` |
| `U_HUB_CVT` | `/HUB_PV_N`, `/HUB_PV_P`, `GND` |

