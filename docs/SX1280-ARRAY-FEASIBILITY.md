# SX1280 array feasibility — can multiple 2.4 GHz radios beat one link?

**Status: analysis, not a decision.** Nothing here authorises a board. Written
2026-10-05 to answer: *"the SX1280 boards are cheap and readily available — how many
can one ESP32-S3 manage, and would several on different channels transport large
amounts of data quickly?"*

## 1. The answer in one line

**No — N co-located 2.4 GHz radios do not give N× throughput.** They give roughly
one link's throughput, because they must take turns. The blocker is physics
(co-site desense), not the MCU. **The ESP32-S3 is not the constraint.**

## 2. What one link already does

Mode matters far more than radio count. The SX1280 is not a LoRa-only part:

| Mode | Character |
|---|---|
| LoRa | slow, long range, robust — the telemetry mode |
| FLRC | high rate, short range |
| GFSK | highest rate |

The project has measured the LR2021 FLRC link at **1484.9 kbps sustained, 0.00 % PER**
(`docs/sustained-throughput-results-2026-07-23.md`, BR2600, LEN 127 — it is TX-side
limited). The older **1391 kbps** figure in `docs/PLAN-speed-optimization.md` is
superseded RP2040 Arduino-SPI history.

> **Settled 2026-10-06 (card `t_6b68897c`; numbers corrected 2026-10-06 rev 2).** The
> **2600 kbps** figure is the FLRC **PHY air rate, not goodput**, and goodput cannot
> reach it at any payload size. With *zero* host overhead the ceiling is **1871 kbps
> at 255 B** and **1910 kbps at 511 B** under the configuration the firmware actually
> ships (FLRC **CR 3/4** — `radio_bench.c:55`; LR20xx driver time-on-air numerator),
> or 2540 / 2570 kbps *if the link were uncoded* (CR NONE). The CR-3/4 figure agrees
> to 0.6 % with the repo's independently computed 1921.8 kbps on-air rate
> (`full-sweep-report-20260821-175612.md:99`).
> An operator report of ~2.6 Mbps attributed to doubling the payload 255 B → 512 B
> was investigated and does not hold: **512 B is not a legal FLRC length** (the
> driver's documented range is `[6:511]`, `lr20xx_radio_flrc_types.h:210`), and no
> 512 B run exists on disk. What *is* demonstrated is 511 B working — 50/50
> delivered, PRBS-15 `bit_err = 0`, at BR650/1300/2600
> (`full-sweep-report-20260821-175612.md`). Full audit:
> `docs/FLRC-512B-THROUGHPUT-AUDIT-2026-10-06.md`,
> `tools/flrc_512b_throughput_audit.py`.
>
> The conclusion below does not depend on which figure wins — a single high-rate
> link beats N co-located radios under every candidate number.

Four
SX1280s in LoRa mode would land *below* the single FLRC link already in hand.
**For raw throughput the lever is modulation mode *plus payload size* (and host-side
pipelining), not radio count** — payload size 255 B → 511 B is worth only ~2 % of
ceiling (1871 → 1910 kbps at CR 3/4), so do not expect packet size alone to be the
lever either.

## 3. Why co-located radios cannot run in parallel

On a 55 × 45 mm board with U.FL pigtails, antenna-to-antenna isolation is roughly
15–25 dB. An SX1280 at +13 dBm therefore presents about −12 to −2 dBm to its
neighbour's LNA — tens of dB above that neighbour's noise floor, which desensitises
or blocks it outright. 2.4 GHz is only 83.5 MHz wide, so "different channels" does
not save you: adjacent-channel rejection in a wideband front end cannot reject a
blocker a few MHz away at that level.

Consequence: **only one radio may transmit at a time.** N links time-shared
serialise back to one link's aggregate rate. You pay N× the parts, pins, power and
board area, and gain nothing on throughput.

## 4. How many radios one ESP32-S3 can actually carry

A shared SPI bus is fine — the radio's air time dominates, so bus sharing costs
almost nothing. The limit is **GPIO**, and on an `ESP32-S3-WROOM-1U-N8R8` several
pins are already spent:

* 8 MB **octal PSRAM** occupies the `IO33–IO37` region (this is exactly why D1.1
  requires SPI1's SCK/MOSI/MISO to be re-planned off `IO35–37`).
* `IO19/IO20` are native USB; `IO43/IO44` are UART0; `IO0`, `IO45`, `IO46` are
  strapping pins.

Per SX1280 on a shared bus: `NSS`, `BUSY`, `DIO1`, `NRESET` = **4 dedicated pins**
(SCK/MOSI/MISO are shared). A PA variant with an RF switch adds `RX_EN`/`TX_EN`,
making **6**.

With the F33 module (~8 lines including `CE`/`DIO5`) and GNSS (UART + `PPS`, 3
lines) already committed, the realistic remainder is roughly 13–15 free pins →
**about 3 SX1280s**, not 6. This is an estimate from module pinouts, **not a
validated pin plan** — ADR-029 D2b (a)–(e) still owe one.

## 5. Where multiple radios DO pay off

| Architecture | Verdict |
|---|---|
| N radios on one flight board, parallel data | **No** — serialised by desense; pays N× for nothing |
| One radio, high-rate mode (FLRC/GFSK) + largest legal payload | **Yes** — the throughput lever, already in hand. Note the lever is *modulation mode first* (~2× from LoRa to FLRC) and *payload size second* (~1.2 % from 255 B to 511 B); radio count is not a lever at all |
| Split function: one telemetry + one ranging | **Yes, and already the design** (F33 + SX1280) |
| **Ground-station RX array**, N radios, N nodes | **Yes** — see below |

**The ground array is the real opportunity.** At the ground end antennas can be
spaced metres apart instead of millimetres, the board is not volume-limited, and a
receive-only array does not desensitise itself. N receivers tracking N balloons in
parallel give a genuine N× aggregate. That is a **separate, dedicated board** — and
it is the version of this idea that survives the physics.

## 6. Recommendation

1. **Do not build a multi-SX1280 flight board for throughput.** Keep the flight
   side to the D2b split (F33 + one SX1280) and get speed from **FLRC/GFSK**.
2. **If you want parallelism, build the ground-station array** — a dedicated
   receive board, spatially diverse antennas, one SX1280 per tracked node. That is
   where more radios convert into more simultaneous links.
3. **Measure co-site isolation before any such board.** Two SX1280s at the intended
   spacing, one transmitting at minimum power, the other reading `inst` RSSI. If
   isolation is ≥40 dB the flight-side calculus changes and option 1 can be
   revisited; at ~20 dB the serialisation above is confirmed.

## 7. Open questions this analysis does NOT answer

* Exact SX1280 FLRC/GFSK rates at the project's chosen bandwidth — read the
  datasheet; do not trust the mode summary above for numbers.
* Whether the flight power budget (D2b (e), supercap) could support a second radio
  at all. Adding radios adds receive current, not just transmit current.
* Ground-array antenna spacing needed to reach a given isolation figure.
* Regulatory asymmetry that *favours* 2.4 GHz for bulk data: the 868 MHz band
  carries duty-cycle limits in the EU, 2.4 GHz ISM does not. This is an argument
  for using the 2.4 GHz path for volume, and it is independent of radio count.

## 8. Risk to the premise — SX1280 ranging is UNPROVEN here

The reason the SX1280 is on the board at all is **ranging**. The project's own
`e28-sx1280-radio-ops` skill records the opposite of success on the bench pair:

> `RANGE` / `RANGE-SLAVE` — **known to fail; never use them as a liveness test**

So the SX1280's ranging role is currently **asserted, not demonstrated**, on this
project's hardware. That does not make keeping the part wrong — the *interop*
argument in ADR-029 D2b still holds — but it does mean the capability being paid
for has not been shown to work here. **Establish ranging on the existing E28 pair
before the v9 layout commits space and pins to it.** If ranging turns out to need
a different part, that is cheapest to learn now, while the board is unbuilt.
