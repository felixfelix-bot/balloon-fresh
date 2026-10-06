# V9-DUAL-LR design memo — two LR2021 modules (868 uplink + 2.4 GHz downlink)

Date: 2026-10-06
Status: engineering decision / amendment to ADR-029

## Recommendation
Do **not** add a second LR2021 to the 55 x 45 mm v9 flight board. The frequency plan is valid in principle, but the mechanical and RF implementation is not: two F33 modules exceed the available footprint, while the only smaller bare LR2021 footprint is nested under the F33 site and therefore cannot be populated simultaneously. The second module also consumes a second independent radio control set and another high-current rail, while the existing ESP32-S3 SPI2/SPI3 allocation is already committed to the F33 and SX1280.

Keep the current F33 + SX1280 + GNSS architecture. Treat dual-module operation as a bench/development experiment or a future larger-board revision, not a v9 population option.

## 1. Does it provide simultaneous bidirectional flow?
Yes, at the system level **if and only if two independently hosted LR2021 transceivers are fitted**: 868 MHz ground-to-balloon uplink and 2.4 GHz balloon-to-ground downlink occupy separate RF channels and can be active concurrently. This is not possible with one LR2021 die, whose two antenna ports share one transceiver core/synthesizer; its ports are alternatives, not two simultaneous radios.

This is a frequency-separation conclusion, not a claim of guaranteed packet performance. The two modules still need independent SPI/control ownership, independent antenna feeds, rail isolation, and a coexistence test. The SX1280 remains operator-ratified and is not reconsidered here.

## 2. 868 MHz third harmonic and LPF decision
The third harmonic is:

`3 x 868 MHz = 2604 MHz` (and `3 x 869.85 MHz = 2609.55 MHz` for the tested centre channel).

2604–2609.55 MHz is above the 2400–2483.5 MHz ISM allocation, but it is inside the likely out-of-band/wideband victim response of a nearby 2.4 GHz receiver. It must not be dismissed merely because the carrier is outside the ISM band.

**No measured attenuation number is available in the repository or from a conducted VNA/spectrum-analyser run.** Therefore the honest current number is `unknown (not 0 dB, not a datasheet guarantee)`. The existing ADR-029 text's `−40 dBc` is an illustrative worst-case assumption, not a measurement and must not be reported as measured filter performance. At +30 dBm fundamental, −40 dBc would still be −10 dBm at the harmonic; at +22 dBm it would be −18 dBm. Those are stress-case arithmetic values only.

Recommendation: provision a 868 MHz low-pass/harmonic filter footprint now, with a bypass/DNP option, and require a conducted measurement before flight approval. Measure `P2604/P868` (or `P2609.55/P869.85`) at the module output and after the filter, plus 2.4 GHz receiver noise-floor/PER with the other radio keyed. Accept the filter only from measured insertion loss and victim desense; do not invent an attenuation figure. A 2.4 GHz band-pass/SAW on the victim feed is a second-line option if the receiver still desenses.

## 3. Area, variants, cost and stock
Known geometry from the committed ADR/vendor data:

| Item | Body / site | Supply position |
|---|---:|---|
| LoRa2021F33-2G4 (baseline) | 39.6 x 21.6 mm (nominal 39 x 21) | JLC stock 0; consigned/loose part |
| Bare LoRa2021 castellated | 20.41 x 15.58 mm body; 18 pads | JLC stock 0; consigned/loose part |
| SX1280 | existing site; JLC `SX1280IMLTRT` ~1000 stock, ~$2.85 at the recorded probe | stocked SMT |

Two F33 sites would require about 79.2 mm in the long dimension before keep-outs, feeds, connectors, and routing, so they cannot fit on 55 x 45 mm. A F33 plus a bare module appears geometrically nestable because the bare pad field lies inside the F33 pad ring; that is a **mutually exclusive footprint option**, not two usable modules. Shared pad numbers include VCC, so the two cannot be powered independently when nested. The nested D8 option therefore does not implement simultaneous dual-band operation.

No reliable current LCSC/JLC unit price for a second LR2021 module was recorded. The only defensible procurement statement is stock 0 / consigned for both LR2021 choices; do not substitute the similarly named LR1121-based listing `LoRa1121F33-2G4-868MHz`.

## 4. Cost of retaining the SX1280 and mitigation
The SX1280 remains decided for fleet-compatible ranging and JLC SMT placement. In the current one-LR2021 + SX1280 shape it creates a second 2.4 GHz RF transmitter/receiver alongside the F33 2.4 GHz port; ESP32-S3 Wi-Fi/BT is a third 2.4 GHz transmitter when enabled. The cost is:

* a dedicated SPI3 bus and unique CS/IRQ/reset/busy wiring (already planned);
* a fourth external RF feed/antenna and placement/keep-outs;
* three-way 2.4 GHz arbitration and possible blocking/desense;
* extra peak current and rail transient/thermal load; and
* mandatory TDM for F33 2.4 GHz, SX1280 and Wi-Fi/BT, rather than simultaneous operation in that band.

Mitigations are the existing ADR-029 decisions: one arbiter owns every RF grant; Wi-Fi/BT is stopped and confirmed down before a 2.4 GHz grant; F33 and SX1280 have independent U.FL feeds with 3-D antenna separation; BUSY is polled in hardware; TX power is capped to the minimum closing the link; GNSS has a filtered/star-fed rail; and the harmonic/victim paths receive conducted and radiated desense tests. This memo does not reopen the SX1280 decision.

## 5. Net pin and power delta versus current one-LR2021 + SX1280
For a genuinely independent second LR2021, the minimum additional digital signals are one SPI device-select plus BUSY, RESET and IRQ/DIO: **+4 GPIO** if it shares the existing SPI data/clock wires. If a separate SPI master is required, add SCK/MOSI/MISO as well: **+7 GPIO total**. A bare module normally does not provide the F33-specific CE/DIO5 pair; if the selected variant requires additional enable/LNA control, add those lines too. The second radio must not reuse the existing F33 CS/control lines.

The S3's two general SPI masters are already allocated to F33 and SX1280, so the +7 independent-bus case is not available without a bus-sharing or pin reassignment decision. Bus sharing still needs +4 unique lines and firmware/device-select discipline.

Power delta is dominated by the second LR2021's TX/RX rail, not logic. Use the same vendor limits as the baseline until a part-specific conducted load test: up to `<800 mA` at 868/915 MHz and `<900 mA` at 2.4 GHz for an F33 at its high-power 5 V operating point, plus regulator quiescent/current margin and local bulk capacitance. Thus a second F33 adds up to approximately **+0.8 A (868 TX) or +0.9 A (2.4 TX)** to the instantaneous radio load; simultaneous uplink/downlink means those currents can sum with the existing F33/SX1280/GNSS loads. Average power depends on duty cycle and cannot be inferred from peak current. The already recorded four-radio power budget must not be reused as proof for a fifth-radio population.

## Decision and follow-up
1. Reject dual-LR2021 population on v9: no two-module placement exists within 55 x 45 mm with RF keep-outs and four existing feeds.
2. Keep a filter footprint and test pads in the future RF revision, but do not call its attenuation measured until a conducted test exists.
3. If simultaneous dual-band is revived, use a larger board or physically separate radio board, with a fresh pin/rail/thermal budget and a measured harmonic/desense campaign.
