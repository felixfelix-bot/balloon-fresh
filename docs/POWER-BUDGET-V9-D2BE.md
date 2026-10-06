# v9 D2b(e) power budget: F33 + SX1280

Status: engineering budget, not a substitute for a load-step bench measurement.
This closes the missing rail sum in ADR-029 D2b(e). Currents marked `budget`
are deliberately conservative design limits; they must be replaced by measured
values before flight.

## Operating assumptions

* The four RF systems are: F33 sub-GHz port, F33 2.4 GHz port, discrete
  SX1280 ranging radio, and ESP32-S3 Wi-Fi/BT. The F33 has one supply but two
  RF ports; they are time-division multiplexed and are not simultaneously TX.
* TX duty cycles for a representative flight budget are: F33 sub-GHz 10%, F33
  2.4 GHz 5%, SX1280 5%, Wi-Fi/BT 1%. These are scheduling assumptions, not
  capacity claims. GNSS is continuously tracking; MS5607 conversion is 10%.
* The **instantaneous stress case** intentionally ignores those duty cycles:
  F33 sub-GHz TX and F33 2.4 GHz TX are shown as mutually exclusive alternatives;
  SX1280 TX and Wi-Fi TX are concurrent electrical loads. A firmware arbiter
  must enforce RF coexistence. A physically simultaneous F33 dual-port TX case
  is invalid, not a hidden margin.
* F33 datasheet/BOM figures in ADR-029 are used: <800 mA at 868/915 MHz and
  <900 mA at 2.4 GHz at the 5 V, +30 dBm setting. ESP32-S3 active peak is
  budgeted at 240 mA; SX1280 +13 dBm TX at 70 mA, RX at 15 mA; MAX-M10S at
  25 mA; MS5607 at 1.5 mA during conversion. Add 20% converter/distribution
  allowance to the input current; do not count it as load capacity.

## Rail load table

All currents are at the named load rail (not input current before a converter).
Average is the time-average under the duty-cycle assumptions above.

| Load | Rail | TX/active peak | quiescent/RX | duty | average |
|---|---:|---:|---:|---:|---:|
| F33 sub-GHz port | 5 V | 800 mA | 20 mA idle | 10% | 98 mA |
| F33 2.4 GHz port | 5 V | 900 mA | 20 mA idle | 5% | 64 mA |
| SX1280 ranging | 3.3 V | 70 mA TX | 15 mA RX, 1 mA sleep | 5% TX / 20% RX | 15 mA |
| ESP32-S3 CPU + digital | 3.3 V | 60 mA | 45 mA active idle | continuous | 60 mA |
| Wi-Fi/BT (included in S3 peak) | 3.3 V | 180 mA incremental TX | 20 mA incremental | 1% | 22 mA incremental |
| MAX-M10S GNSS | 3.3 V | 25 mA | 25 mA tracking | continuous | 25 mA |
| MS5607 barometer | 3.3 V | 1.5 mA | 0.01 mA | 10% conversion | 0.16 mA |
| **Rail subtotal** | **5 V** | — | — | — | **162 mA** |
| **Rail subtotal** | **3.3 V** | — | — | — | **102 mA** |

The ESP32 row is the complete active budget including its Wi-Fi/BT incremental
term: 60 mA CPU plus 180 mA Wi-Fi peak, or 240 mA at the peak. It is not 240 mA
plus another 240 mA. The F33 average is 162 mA at 5 V (0.81 W). The 3.3 V
average is approximately 0.34 W. Thus the load is approximately 1.15 W
before converter losses, or approximately **1.38 W input** with a 20% allowance.

## Worst-case load and available power

The F33 cannot TX on both ports at once. The electrical worst cases are:

| Case | 5 V load | 3.3 V load | output power | input equivalent with 20% allowance |
|---|---:|---:|---:|---:|
| F33 868 TX + SX TX + S3/Wi-Fi + GNSS + baro | 0.820 A | 0.337 A | 5.56 W | 6.67 W |
| F33 2.4 GHz TX + SX TX + S3/Wi-Fi + GNSS + baro | 0.920 A | 0.337 A | 6.06 W | 7.27 W |
| all four RF *systems* transmitting (invalid simultaneous F33 dual-port case) | 1.720 A | 0.337 A | 10.06 W | 12.07 W |

The 5 V rail therefore needs at least a **1.0 A continuous / 1.2 A load-step
capability** for the valid maximum case, with output capacitance and layout
proven by oscilloscope. The 3.3 V rail needs at least 0.60 A transient capacity.
A regulator chain whose current rating is not documented is **not evidence of
capacity**; the present ADR-029 record does not document these ratings.

## Supercap energy check

For the specified 1 F, 5.5 V capacitor, ideal stored energy is 15.125 J at
5.5 V. A 5 V rail cannot use the energy below 5.0 V without a boost or buck-boost,
so the useful ideal energy between 5.5 V and 5.0 V is:

`E = 1/2 C (5.5² - 5.0²) = 2.625 J`.

That supports approximately 0.41 s at the valid 6.06 W output worst case, or
1.91 s at the 1.38 W representative average, before ESR, converter efficiency,
and cold derating. At 85% conversion efficiency those become approximately
0.35 s and 1.62 s. The capacitor is a burst ride-through element, **not a
battery**. At 5 V it also cannot sustain the invalid 10.42 W dual-F33 case for
more than about 0.26 s (ideal).

If the design instead operates the radios from 3.3 V, the ideal usable energy
from 5.5 V down to 3.5 V is 9.0 J, but a 5 V-to-3.3 V regulator cannot regulate
below its dropout/input requirement and the F33 loses about 3.5 dB. This is not
a free O5 alternative.

## Cold/altitude and verdict

At altitude, cold raises ESR and reduces effective capacitance; solar input and
battery capacity also fall. Consequently the 0.35–0.41 s 5 V hold-up estimate
is an optimistic room-temperature figure. Loiter/float operation must budget
at least the representative 1.38 W input continuously and must schedule RF so
that average solar/battery input exceeds it. The current record contains no
cold ESR, regulator thermal/load-step, solar-at-altitude, or battery curve, so
there is no defensible claim that the existing chain holds the rail up.

**O5 verdict: BLOCKED, not retained.** Keep the 5 V option in the schematic
(selectable rail), but do not freeze the BOM or approve flight until a specified
5 V converter/LDO chain is demonstrated at >=1.2 A load-step, the 3.3 V rail at
>=0.60 A, and the supercap/charger is tested cold. If that evidence cannot be
produced, change O5 to 3.3 V operation with reduced F33 power rather than claim
full +30 dBm operation.

Required bench evidence: current probe on each rail, 5 V and 3.3 V load steps,
Vcap droop from 5.5 V to converter cutoff, ESR at the expected cold minimum,
and GNSS-rail dip (ADR-029 test 4 target <20 mV).
