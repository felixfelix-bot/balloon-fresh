# USB programming candidate — service port, not compliance or boot proof

Preserves RP2040/boot-core/buck changes. Only spec.json and generator extended, plus test_usb_programming.py. No original netlist/PCB, v10, push, merge or tag touched.

## Captured interface

- J_USB Molex **1050170001**, `Connector_USB:USB_Micro-B_Molex-105017-0001`: 1 USB_VBUS, 2 DM_PORT, 3 DP_PORT, 4 ID deliberately NC, 5 GND, shell pads6 GND. Micro-B device connector, no Type-C CC network needed. Installed footprint exists; mixed SMT/PTH retention, not all-SMT.
- U_USB_ESD ST **USBLC6-2SC6**, `Package_TO_SOT_SMD:SOT-23-6`: 1/6 DM_PORT, 3/4 DP_PORT, 2 GND, 5 USB_VBUS. Locate at connector, with short low-inductance ground return; 27R resistors remain toward RP2040 pads46/47. Pin pairing follows ST top-view diagram; layout/surge effectiveness not proven by connectivity.
- SW_BOOTSEL/SW_RESET **C&K PTS636 SK25 SMTR LFS**, `Button_Switch_SMD:SW_Tactile_SPST_NO_Straight_CK_PTS636Sx25SMTRLFS`: normally-open two-terminal switch, pin1 signal pin2 GND. Reset signal RUN. BOOTSEL signal connects through **1k** to QSPI_SS, not a spare GPIO and not RUN. Existing 10k QSPI_SS pull-up retained. Momentary closed switch yields about 0.3V with that pull-up; series resistance permits CS drive during boot.

## Explicit power/backfeed policy

**External protected 9–18V supply is mandatory; USB never powers +5V_PCBA or +3V3_MCU.** USB_VBUS has exactly two owners: connector1 and ESD5. It is not tied to the buck, LDO, GPIO or SWD. USB_VDD48 remains 3.3V. No 5V ORing circuit or reverse-power-protected LDO is claimed. SWD pin1 remains a voltage-reference output, not external power input.

Minimal **supervised service** sequence: connect to a powered USB host before applying external board power; hold BOOTSEL, press/release RESET, then release BOOTSEL. Remove external board power before host shutdown/disconnection. No external power means no enumeration. This design has no VBUS detector or data disconnect, so **unattended self-powered hotplug, suspend and USB compliance are not established**. ROM pull-up behavior cannot be assumed gated by VBUS; powered data lines and the ESD steering network can inject into an unpowered host's VBUS if this sequence is violated. No broad claim of zero backfeed under arbitrary sequencing is made. Hardware VBUS-gated data disconnection would be a required follow-up if arbitrary host/board sequencing is required, not silently implied by the net names.

Buck/input requirements unchanged: upstream fuse/current limit, reverse blocking, surge/hot-plug suppression, correct polarity, normal 9–18V, IC VIN <=28V including ringing and no negative excursions. These remain unimplemented/unvalidated external obligations requiring approval, not reduced requirements or onboard protection.

## Evidence and procurement boundaries

Primary RP2040 references already downloaded in `output/readiness/boot-core/sources/reference.pdf` and `output/readiness/rp2040/rp2040-datasheet.pdf`: Hardware design with RP2040 section2.2 explicitly specifies QSPI_SS boot strap, **1k** series resistor and reset through RUN; datasheet section1.4.2 requires 27R data termination. Reference boot-strap text was re-read for this change.

- https://datasheets.raspberrypi.com/rp2040/hardware-design-with-rp2040.pdf
- https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf
- https://www.st.com/resource/en/datasheet/usblc6-2.pdf — indexed primary top-view map 1/6 I/O1,3/4 I/O2,2 GND,5 VBUS; direct full PDF retrieval blocked, full dimensional approval pending.
- https://www.molex.com/en-us/products/part-detail/1050170001
- https://www.molex.com/content/dam/molex/molex-dot-com/products/automated/en-us/salesdrawingpdf/105/105017/1050170001_sd.pdf — retrieval timeout; full drawing/footprint approval pending. Electrical numbering corroborated by https://www.nxp.com/downloads/en/schematics/TWRK21D50MSCH_REVB.pdf .
- C&K March2025 manufacturer drawing actually read via distributor mirror https://atta.szlcsc.com/upload/public/pdf/source/20260731/53CC7FBA4ED42906E550F3BDCE54ABE8.pdf ; G-lead 2.5mm variant has 9mm outer span,6.5mm inner gap,1mm width. Installed pads at +/-3.875mm,1.25x1mm match. Manufacturer source https://www.littelfuse.com/products/switches/tactile-switches/pts636/pts636sk25smtr .

Exact-MPN procurement leads: DigiKey WM1399CT-ND (Molex),497-5235-1-ND (ST), Newark35AH5159 (switch). **Not live stock/price verification**: direct extraction unavailable. JLC C136000/C7519 are search leads, not approved substitutions/catalogue evidence. Exact switch not located in bounded JLC search, which does not prove unavailable. Electrical selection and JLC procurement are separate unresolved gates.

## Exercised artifact and tests

Three new oracle tests were run RED: missing connector/ESD, missing boot/reset and missing isolated VBUS ownership all failed. After capture, four new tests PASS, including ten independent copied-pad mutations for swapped data, ground/shell, wrong ESD ground/channel, wrong boot mechanism/direct-CS short, reset ground and VBUS-to-LDO/5V faults. No source mutation performed.

Run from this directory:
```
python3 -m unittest test_usb_programming test_buck test_boot_core test_rp2040_pinout test_verifier_portability -v
python3 test_spec_transcription.py
```
Actual result: **17 tests PASS**, retained freeze checks **34/34** with proposed buck deviation warning. Candidate legacy netlist checks **25/25** (structural only, not physical fault-isolation proof). `git diff --check` clean.

`output/readiness/usb/candidate/` contains copied generator, spec, invariant verifier and actual `base_station_v1.net`. Generated twice byte-identically: **67 components,45 nets**. SHA256:
`f89ca2f3d6c69b9f71221663b6c4d19b088a5fff5828b6090a746c564d573a54`

## Finite remaining inventory and validation

Candidate census in `output/readiness/usb/remaining-parts.json`: **7 functional design identities/values unresolved**: Q_LNA_SW, R_LNA_ILIM, FB_VGA, FB_DET, FLT_433_A, FLT_433_B, C_TAP. Existing README/evidence and docs/fab selections have no demonstrated superseding circuit for these. Separately **46 generic procurement rows** (passives, connectors, testpoints) still lack exact purchasing identities in emitted value fields; **14 device/family-identified rows** are not all full suffix/stock approvals. Counts sum to67. Three SMA footprints imply Amphenol132134-10 but purchasing identity is not captured. Two testpoints may resolve as bare copper rather than purchased parts. External protection is outside this component count, NOT completed.

Still required: correct ADL5240/AD8318 pin/support capture and ADC bounds; seven functional gaps; full capacitor/rating/procurement qualification; upstream protection and buck deviation approval; physical USB/UF2/SWD flashing, firmware boot2, reset recovery, all power sequences/leakage; oscillator start/drive/temperature; LDO/buck load-step/stability/thermal; ESD, USB signal integrity and EMC; schematic ERC, footprint approval, placement/routing/DRC; four frozen RF gates. No hardware boot, routable board or order-readiness claim.
