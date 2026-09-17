# Netlist audit - v_c3_flight_4layer_placed.kicad_pcb

27 pads carry no net: **11 classified GAP** (4 HIGH, 1 LOW, 6 MEDIUM) and 16 intentional.

Confidence: HIGH = proven from an artefact in this repo/host; MEDIUM = inferred from the datasheet-level pin map; LOW = the in-repo sources contradict each other.

| ref | pad | classification | conf | pin function | evidence | action |
|---|---|---|---|---|---|---|
| J1 | 6 | INTENTIONAL | MEDIUM | spare pin on a 1x06 programming header (5 signals used) | J1 carries GND/+3V3/EN/UART0_TX/UART0_RX on pads 1-5; pad 6 is the unused end pin of the header | mark it no-connect in the schematic so ERC stops reporting it |
| U1 | (unnamed) | INTENTIONAL | HIGH | library mechanical pad (no pad number) | the KiCad library footprint RF_Module.pretty/ESP32-C3-WROOM-02.kicad_mod contains exactly 9 unnamed pads; an unnamed pad cannot be netted by construction | none - mechanical only |
| U1 | (unnamed) | INTENTIONAL | HIGH | library mechanical pad (no pad number) | the KiCad library footprint RF_Module.pretty/ESP32-C3-WROOM-02.kicad_mod contains exactly 9 unnamed pads; an unnamed pad cannot be netted by construction | none - mechanical only |
| U1 | (unnamed) | INTENTIONAL | HIGH | library mechanical pad (no pad number) | the KiCad library footprint RF_Module.pretty/ESP32-C3-WROOM-02.kicad_mod contains exactly 9 unnamed pads; an unnamed pad cannot be netted by construction | none - mechanical only |
| U1 | (unnamed) | INTENTIONAL | HIGH | library mechanical pad (no pad number) | the KiCad library footprint RF_Module.pretty/ESP32-C3-WROOM-02.kicad_mod contains exactly 9 unnamed pads; an unnamed pad cannot be netted by construction | none - mechanical only |
| U1 | (unnamed) | INTENTIONAL | HIGH | library mechanical pad (no pad number) | the KiCad library footprint RF_Module.pretty/ESP32-C3-WROOM-02.kicad_mod contains exactly 9 unnamed pads; an unnamed pad cannot be netted by construction | none - mechanical only |
| U1 | (unnamed) | INTENTIONAL | HIGH | library mechanical pad (no pad number) | the KiCad library footprint RF_Module.pretty/ESP32-C3-WROOM-02.kicad_mod contains exactly 9 unnamed pads; an unnamed pad cannot be netted by construction | none - mechanical only |
| U1 | (unnamed) | INTENTIONAL | HIGH | library mechanical pad (no pad number) | the KiCad library footprint RF_Module.pretty/ESP32-C3-WROOM-02.kicad_mod contains exactly 9 unnamed pads; an unnamed pad cannot be netted by construction | none - mechanical only |
| U1 | (unnamed) | INTENTIONAL | HIGH | library mechanical pad (no pad number) | the KiCad library footprint RF_Module.pretty/ESP32-C3-WROOM-02.kicad_mod contains exactly 9 unnamed pads; an unnamed pad cannot be netted by construction | none - mechanical only |
| U1 | (unnamed) | INTENTIONAL | HIGH | library mechanical pad (no pad number) | the KiCad library footprint RF_Module.pretty/ESP32-C3-WROOM-02.kicad_mod contains exactly 9 unnamed pads; an unnamed pad cannot be netted by construction | none - mechanical only |
| U2 | 11 | GAP (probable GROUND tab left floating) | MEDIUM | right-side pad between GND (10) and LR_BUSY (12) | on the RFM9xW 16-pad reference pinout pads 10/11/16 are GND, and this board already nets GND on pads 1/8/10 - pad 11 is the same class of tab | verify and connect to GND if confirmed; a floating RF module ground tab is a grounding/EMC defect |
| U2 | 15 | GAP (probable unused I/O) | MEDIUM | right-side pad between LR_DIO0 (14) and the netless 16 | not one of the module's declared NC pins (12, 15 in the 18-pad map do not line up with this 16-pad footprint) | confirm and no-connect explicitly |
| U2 | 16 | GAP (probable GROUND tab left floating) | MEDIUM | right-side end pad, next to netless 15 | same evidence as U2 pad 11 (RFM9xW reference GND tab) | verify and connect to GND if confirmed |
| U2 | 7 | GAP (probable unused I/O) | MEDIUM | left-side pad between LR_RST (6) and GND (8) | the module's only NC pins are 12 and 15 (full_pipeline.py:191-213); pad 7 is not one of them | confirm against the NiceRF LR2021F33 drawing; if it is DIO2, tie it or declare it no-connect - it is unmodelled today |
| U3 | 11 | GAP (FUNCTIONAL-CRITICAL) | HIGH | RF_IN (GPS antenna input) | nothing on this board connects to RF_IN: the 20-footprint board carries no GPS antenna part or feed net (only ANT1/U.FL for 2.4GHz), so the MAX-M10S receiver input is open | add the antenna feed (patch / U.FL + matching) or the GPS cannot receive |
| U3 | 13 | INTENTIONAL | MEDIUM | LNA_EN (output) | only used to bias an external LNA; none fitted | no-connect in schematic |
| U3 | 14 | INTENTIONAL | MEDIUM | VCC_RF (power output for an ACTIVE antenna) | no active antenna in this design | no-connect in schematic; revisit if an active antenna is ever fitted |
| U3 | 15 | GAP (input floating) | HIGH | VIO_SEL (IO voltage select) | a floating select input leaves the IO reference undefined | tie per the u-blox datasheet (to GND or VCC_IO) |
| U3 | 16 | INTENTIONAL | MEDIUM | SDA (DDC/I2C data) | the module is used over UART (GPS_RX/GPS_TX on pads 2/3) | no-connect in schematic |
| U3 | 17 | INTENTIONAL | MEDIUM | SCL (DDC/I2C clock) | as pad 16 | no-connect in schematic |
| U3 | 18 | GAP (input floating) | MEDIUM | ~SAFEBOOT (input) | safe-boot input is not tied or driven | tie to the level the datasheet requires or no-connect explicitly |
| U3 | 4 | INTENTIONAL | MEDIUM | TIMEPULSE (output) | optional 1PPS output, unused in this design | no-connect in schematic |
| U3 | 5 | INTENTIONAL | MEDIUM | EXTINT (input) | optional external-interrupt input, unused | no-connect in schematic |
| U3 | 6 | GAP (power pin unconnected) | HIGH | V_BCKP (backup supply) | V_BCKP is a power_in pin; nothing on the board drives it, so RTC/hot-start backup is undefined | tie to +3V3 (or to the supercap rail) or declare the trade-off explicitly |
| U3 | 9 | GAP (input floating) | MEDIUM | ~RESET (active-low reset input) | active-low reset is not tied and not driven - a floating reset input is undefined at power-up | tie to +3V3 through the design's pull-up or drive it |
| U4 | 3 | GAP (enable floating) | HIGH | EN (active-high enable) | every in-repo source agrees pin 3 is EN, and EN carries no net - the rail is never explicitly enabled | tie EN to IN/VCAP (always-on) or to a GPIO |
| U4 | 4 | GAP (OUT/NC contradiction) | LOW | OUT or NC - the two in-repo sources disagree | balloon_symbols.kicad_sym says pin 4 = OUT and pin 5 = NC; full_pipeline.py:279 says the pads are (IN, GND, EN, OUT, NC). The board carries +3V3 on pad 5 and nothing on pad 4, which matches the TI DBV arrangement (5 = OUT, 4 = NC) and contradicts the custom symbol | arbitrate against the TI datasheet before fab, then fix whichever artefact is wrong (symbol or board) - today they cannot both be right |

GAP = a pin whose device function expects a connection that no net provides. INTENTIONAL = unused/optional pin, or a library mechanical pad. The 4-layer routed board carried the SAME 27 netless pads, so no net was lost by the S0 placement change - this audit characterises a pre-existing netlist, it does not introduce one.
