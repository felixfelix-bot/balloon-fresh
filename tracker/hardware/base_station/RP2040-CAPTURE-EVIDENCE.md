# RP2040 corrected capture candidate — NOT layout release

## Primary evidence

Downloaded directly from Raspberry Pi:
https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf

PDF SHA256: `be56fbb75ba0ae9e26558a73c93ac3e75c2ad4e6878d3b6703de2a76d886ea8c`.
Local PDF/text/render: `output/readiness/rp2040/` (ignored local evidence, not tracked).
Figure 3 (printed p11, PDF page12) was rendered and read. Independently cross-checked
against textual tables 615–621 in §5.5 (printed pp612–614):

| Function | Physical pad(s) | Candidate net |
|---|---|---|
| IOVDD | 1,10,22,33,42,49 | +3V3_MCU |
| DVDD | 23,50 | +1V1_MCU |
| VREG_VIN | 44 | +3V3_MCU |
| VREG_VOUT | 45 | +1V1_MCU |
| ADC_AVDD | 43 | +3V3_MCU |
| USB_VDD | 48 | +3V3_MCU |
| TESTEN, GND exposed pad | 19,57 | GND |
| XIN, XOUT | 20,21 | XIN, XOUT |
| SWCLK, SWD | 24,25 | SWCLK, SWDIO |
| RUN | 26 | RUN |
| USB_DM, USB_DP | 46,47 | USB_DM, USB_DP |
| QSPI SD3, SCLK, SD0, SD2, SD1, CSn | 51,52,53,54,55,56 | corresponding QSPI nets |
| GPIO26/ADC0 | 38 | DET_VOUT |

Table 621 explicitly numbers the exposed GND pad **57** (Figure 3 leaves the centre
unnumbered). No KiCad symbol is used as the pin oracle.

## Source changes

`spec.json` adds a separate implementation capture record (not a claim that the freeze
specified GPIO pad allocation). Generator consumes that map. GPIO0–5 provisionally
carry VGA_GAIN0–2, LNA_EN, LNA_FLT, REG_PG; unused GPIOs are unconnected, not grounded.
Firmware/peripheral-interface agreement remains unverified.

Single-3.3V scheme follows §2.9.7.1: VREG_VOUT feeds both DVDD pads externally.
§§2.9.1–2.9.5 require one 100nF close to each IOVDD/DVDD/USB_VDD/ADC_AVDD pad:
ten capacitors, with distinct `C_RP_<pad>` references. §§2.9.3/2.10 require 1uF at
VREG_VIN and VREG_VOUT: two more capacitors. These are netlist requirements only;
physical proximity, effective capacitance/voltage rating, regulator stability and
return paths still require component selection and placement checks.
§1.4.2 and Table 620 require 27-ohm USB series resistors; both are captured.

## RED / GREEN evidence

`test_rp2040_pinout.py` executes the real generator in a temporary copy, never in the
source directory. Its pin/supply oracle is hardcoded from the primary datasheet and
is independent of both spec and generator. All generated pad ownership is checked;
a duplicate-pad mutation proves rejection. RP2040 GND is restricted to pads 19/57.

- `output/readiness/rp2040/red-pinout.log`: exit 1; 27 failures (26 pad subtests and
  incorrect grounded-GPIO set), before source correction.
- `output/readiness/rp2040/red-support.log`: exit 1; 14 failures for missing local
  capacitors and USB resistors, before support correction.
- `output/readiness/rp2040/green-tests.log`: exit 0; **6 unittest tests pass**
  (three RP2040 tests + three existing portability/mutation tests).
- `output/readiness/rp2040/transcription.log`: exit 0; **34/34**.
- `output/readiness/rp2040/candidate-invariants.log`: exit 0; **25/25**, run against
  the corrected candidate, not the old source netlist. Those invariants do not prove
  LNA fault isolation or correctness of analog IC pin maps.

Run new regressions from this directory:
`python3 -m unittest test_rp2040_pinout test_verifier_portability -v`

## Exact generated artifact

`output/readiness/rp2040/candidate/base_station_v1.net`

SHA256: `a4fac731ec8b4bdac22c4671d64a10cea700ac712d9f5a4c803fe1ef565d6cd2`

56 components, 45 nets, 182 unique component-pad owners; 34 connected RP2040 pads.
`candidate-audit.json`, `generation.log`, `sha256.json` in the enclosing evidence
directory record the inventory, singleton nets and hashes. Candidate directory also
contains the copied generator, spec, and invariant script for reproduction. Run its
copied generator there to reproduce; do not run the source generator as a refresh.

The source `base_station_v1.net`, both original PCB placements, all v10 boards and
project rules are untouched. Original v2 PCB remains SHA256
`095d0278410465f24a2f229969a21017d469bfd34c31f597fea24a6d6afe61af`.
No candidate PCB was created: this bounded deliverable is the corrected netlist,
not a routed or DRC-approved board. No push, merge, tag or purchase.

## Explicit release blockers (not fixed by green pin tests)

- **U_FLASH remains an unvetted placeholder.** Existing SOIC-8-EP footprint, SD0/SD1
  pin assignment, exposed-pad assumption, voltage/boot-command compatibility and
  missing device-specific decoupling/pull-ups must be checked against a selected
  flash manufacturer's datasheet. Correct RP2040 QSPI pads do NOT validate its
  far end. Its value now explicitly says NOT vetted.
- Y1 remains generic. Datasheet §2.16.1.1 recommends ABM8-272-T3 and requires tuning
  and temperature stability checks. Existing 15pF load caps/direct XOUT connection
  are not validated; crystal MPN, loading, damping resistor and drive level remain
  blockers. Only RP2040 XIN/XOUT mapping is verified here.
- USB port-side nets end at the new resistors. No USB connector, ESD or VBUS policy
  has been selected; USB is not a complete working interface.
- U_LDO identity/pinout/enable and rail capability remain unverified (LDO_EN still
  singleton). RP2040 supply topology is captured, not demonstrated energized.
- AD8318 and ADL5240 pin maps/support circuits are not verified by this work. Detector
  output voltage must be bounded to the MCU ADC input domain (datasheet §2.9.5);
  firmware gain control and fault signal compatibility also need validation.
- D_REV/D_TVS, Q_LNA_SW/R_LNA_ILIM, TPS62162 capture, filters, tap, ferrites and RF
  singleton nets remain as previously recorded placeholders/design gaps. VIN_GS
  18V vs TPS62162 17V rating remains unresolved. No claim that other IC supply and
  decoupling requirements are met.
- The four frozen pre-layout gates remain unpassed. Package geometry, placement,
  close decoupling, USB impedance and all routing/DRC must follow validated capture.
