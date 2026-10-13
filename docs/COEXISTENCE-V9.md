# Dual-radio flight board (v9) — separation & coexistence plan

Status: design memo, draft for ADR-029. Target: ESP32-S3-WROOM-1 (U.FL variant, `-1U`),
LR2021 @868 MHz (SPI0), SX1280 @2.4 GHz (SPI1), MAX-M10S @1575.42 MHz (UART), 4-layer 55x45,
reusing the v8h RF rule set and the frozen campaign `.kicad_dru`.

## 1. The four emitters/receivers that must share the board

| radio | band | role | worst case |
|---|---|---|---|
| ESP32-S3 Wi-Fi/BT | 2400-2483.5 MHz | config/telemetry (intermittent) | +20 dBm TX, on-die |
| SX1280 | 2400-2500 MHz | ranging / 2.4G link | ~+13 dBm TX, -120 dBm RX |
| LR2021 | 863-870 MHz | long-range telemetry | up to +22 dBm TX |
| MAX-M10S | 1559-1610 MHz (L1) | position | -165 dBm acquisition |

Two of the four share 2.4 GHz (S3 Wi-Fi and SX1280). One is 60-75 dB weaker than everything else
(GNSS). Those two facts drive the whole design.

## 2. Mechanism-by-mechanism, and the mitigation for each

**(a) SX1280 <-> ESP32-S3 Wi-Fi, same band, same board, ~2 cm apart.**
This is the dominant coupling path: not harmonics, but *blocking and LNA desense*. An S3 Wi-Fi TX
at +20 dBm in the same band as an SX1280 RX can push its LNA into compression; the SX1280's own TX
can likewise desense the Wi-Fi RX.
*Mitigation (all three, not one):* (1) **TDM by design** — Wi-Fi/BT is OFF whenever the ranging radio
is active, enforced in firmware as a single arbiter, not by convention; (2) `-1U` module so the Wi-Fi
antenna is a **U.FL pigtail**, not the on-module PCB antenna — it can be physically routed to the
opposite end of the payload; (3) never co-polarised antennas closer than ~lambda/2 (~6 cm at 2.4 GHz);
place the two 2.4 GHz feeds on **opposite board edges**, orthogonal orientation.

**(b) LR2021 868 MHz TX into the SX1280 RX.**
868 is ~1.5 GHz away, so the *fundamental* is not the problem — **harmonic and broadband-noise**
leakage is. LR2021 3rd harmonic lands at ~2604 MHz, i.e. 120 MHz above the 2.4 GHz band edge: outside
the band, but inside the SX1280's wideband front end. A +22 dBm fundamental makes even a -40 dBc
harmonic a -18 dBm interferer at the antenna.
*Mitigation:* keep the module's own LPF in the TX path, add a **harmonic LPF on the 868 port** if the
bench shows any 2.4 GHz rise with 868 keyed; and a **2.4 GHz SAW/BPF** on the SX1280 if its RX floor
moves when 868 transmits. Both are 0-2 EUR parts; decide by measurement, not by datasheet margin.

**(c) GNSS.**
GNSS is not near either radio in frequency, so the threats are all *wideband noise and supply
modulation*: switching-regulator noise, the S3's 40 MHz clock harmonics, and rail dips on radio TX
bursts. The MAX-M10S LNA also needs a quiet ground under its feed.
*Mitigation:* dedicated RC/ferrite feed (e.g. 100 ohm + 10 uF) from 3V3 into the GNSS rail; its own
ground-return star back to the battery node; GNSS placed at the **sky-facing edge**, its keep-out
free of any TX trace; no TX trace and no via stitching ring inside the GNSS keep-out.

**(d) Physical separation on the PCB (the cheap, biggest win).**
Three U.FL connectors, each on a different board edge, each with its own solid reference-plane patch
and a keep-out to both the header and the opposite connector:
- GNSS U.FL: **+Y edge** (top, sky-facing), feed as short and straight as possible.
- 868 U.FL: **-Y edge** (bottom), opposite the GNSS.
- 2.4 GHz U.FL: a **side edge**, midpoint, orthogonal to both.
Because all three are pigtails, the *decisive* separation happens off-board: on the balloon the three
antennas get 10+ cm of physical spacing and orthogonal orientations. This is why U.FL (not chip
antennas) is the right choice for this board — chip antennas would force the whole fight onto a 55x45
PCB where it cannot be won.

**(e) Supply and return.**
Each radio gets its own ferrite + bulk cap from 3V3; TX bursts (SX1280 ~25 mA, LR2021 up to ~120 mA
peak) must not modulate another radio's rail or the GNSS LNA. Star the returns at the battery node,
not at a shared plane neck.

## 3. Frequency/time plan (the arbiter spec)

| slot | owner | duration | rule |
|---|---|---|---|
| 0-900 ms | 2.4 GHz ranging (SX1280) | up to 900 ms | Wi-Fi/BT forced OFF; 868 TX inhibited |
| 900-1000 ms | quiet | 100 ms | GNSS wakes, position captured |
| 1000-1100 ms | 868 telemetry (LR2021) | 100 ms | 2.4 GHz RX idle; GNSS in normal tracking |
| 1100 ms - 2 s | GNSS + sensor | 900 ms | both radios idle |

Enforced by one firmware function (`radio_arbiter_acquire(band)`) plus a hardware read of the other
radio's BUSY line, so a wedged task cannot overlap two transmitters. Hardware-to-hardware: route both
BUSY lines so the arbiter can poll them without the other driver's cooperation.

## 4. Pin plan (ESP32-S3-WROOM-1, GPIO budget)

| function | SPI0 / LR2021 | SPI1 / SX1280 | GNSS | notes |
|---|---|---|---|---|
| SCK | GPIO12 | GPIO36 | - | SPI1 on the S3's native IO_MUX pins for clean edges |
| MOSI | GPIO11 | GPIO35 | - | |
| MISO | GPIO13 | GPIO37 | - | |
| NSS | GPIO10 | GPIO38 | - | separate CS per radio, shared-bus fallback possible |
| BUSY | GPIO9 | GPIO39 | - | arbiter inputs |
| RST | GPIO8 | GPIO40 | - | |
| DIO/IRQ | GPIO7 | GPIO41 | - | |
| UART | - | - | GPIO17/18 | GPS RX/TX |
| PPS | - | - | GPIO21 | optional, TIMEPULSE |
| antenna | U.FL | U.FL | U.FL | 3 pigtails |

Two SPI masters on the S3 (SPI2/SPI3 via GPIO matrix) — no bus sharing, no CS-timing compromises.
That is the single strongest reason to prefer the S3 over the C3 (one usable general SPI) here.

## 5. Verification protocol (numbers, not adjectives)

1. **SX1280 RX desense:** record RSSI noise floor at 3 frequencies with (i) all radios off, (ii) 868
   keyed at max power, (iii) Wi-Fi beaconing. Acceptance: floor rise < 3 dB with 868 keyed.
2. **Wi-Fi/SX1280 mutual:** run a 2.4 GHz PER sweep at a fixed distance with Wi-Fi off vs on.
   Acceptance: PER degradation < 1 dB with the arbiter active.
3. **GNSS C/N0:** log mean C/N0 of the visible constellation with radios idle, then with both radios
   in the TDM schedule. Acceptance: C/N0 drop < 1 dB.
4. **Rail sanity:** scope the GNSS rail during LR2021 TX bursts. Acceptance: < 20 mV dip.
5. **Arbiter test:** a fuzz test that hammers `radio_arbiter_acquire` from three tasks and asserts no
   overlapping TX (assert on the BUSY lines) in 10k iterations.

Tests 1-4 need the physical board (bench campaign, `e80-range-bench` style); test 5 is host-side and
is the first thing to write.

## 6. Open questions for the consultants (when a lane is funded)

1. Is the harmonic-LPF on the 868 port actually needed, or does the LR2021 module's internal filtering
   plus the SX1280's own front-end selectivity make it redundant at these power levels?
2. `-1U` (U.FL Wi-Fi) vs the standard WROOM-1 PCB antenna: does the pigtail on the Wi-Fi antenna
   introduce more risk (feed loss, ground-plane dependence) than it removes?
3. Is a shared-SPI design (one bus, two CS) genuinely acceptable, or is the two-master plan worth
   ~6 extra GPIO?
4. GNSS keep-out size and reference-plane cut: what is the minimum that still yields a usable L1 feed
   on a 55x45 4-layer with a 0.6/0.3 via floor?

Consultant status 2026-10-04: **all non-deepseek lanes are unfundable** (glm/kimi/qwen/tencent/minimax
all HTTP 503; ollama_cloud_3 subscription past due), so these four questions are OPEN and unanswered
by an independent family. They are listed here so they are not lost; the same single funding action
that unblocks the U2 review unblocks this consultation.
