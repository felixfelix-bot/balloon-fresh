# Independent numeric checks (manager, computed — verify the consultants against this)

Purpose: the visual consultant grades; it does not measure. Every geometric
claim it makes must be checked against arithmetic. These are my own numbers,
computed here, so that when the consultant disagrees I can find out who is wrong.

## 1. Can a 12 km balloon see 300 km? (radio horizon)

Radio horizon with standard 4/3 Earth refraction:  d_km = 4.12 * sqrt(h_m)

| altitude | radio horizon | 300 km hop? |
|---|---|---|
| 5 300 m | 300 km | exactly at the limit |
| 12 000 m | **451 km** | yes, comfortably |
| 18 000 m | **553 km** | yes, with margin |

=> The operator's 300 km per leg is INSIDE the horizon at 12 km. A 600 km
two-hop (balloon midway between two ground stations) is geometrically sound.
Minimum altitude for a 300 km leg is ~5.3 km, so 12 km gives ~150 km of slack.

## 2. Free-space path loss (FSPL = 32.44 + 20log10(f_MHz) + 20log10(d_km))

| f | d = 300 km |
|---|---|
| 433 MHz | 32.44 + 52.73 + 49.54 = **134.7 dB** |
| 2400 MHz | 32.44 + 67.60 + 49.54 = **149.6 dB** |

Difference between bands: **14.9 dB in favour of 433 MHz** — that is the single
biggest lever in the whole link budget.

## 3. Required received power for 2.6 Mbit in a 2 MHz channel

Shannon: the minimum SNR to get 2.6 Mbit in 2.0 MHz is
  C = B*log2(1+SNR) -> 1.3 = log2(1+SNR) -> SNR = 1.46 = **1.65 dB** (absolute floor).
A practical FLRC/GMSK implementation needs ~8-10 dB in-channel to hit BER targets,
so carry **10 dB** as the design requirement.

Sensitivity = -174 dBm/Hz + 10log10(2e6) + NF + SNR_req
           = -174 + 63.0 + NF + 10
           = **-101.0 + NF dBm**
With NF = 1.5 dB (ZX60-P103LN+ 0.5 dB + ~1 dB feedline/mix): **-99.5 dBm**.

## 4. Does it close? Solving  Prx = Ptx + Gtx + Grx - FSPL

Required: Ptx + Gtx + Grx >= 35.2 dB on 433 MHz, >= 50.1 dB on 2.4 GHz.

(a) Hub -> ground, 433 MHz, balloon antenna 0 dBi, ground Yagi 20 dBi:
    Ptx = 35.2 - 20 = 15.2 dBm = **33 mW**. Closes with 33 mW.

(b) Ground -> balloon, 2.4 GHz, ground dish 24 dBi = 100 W (50 dBm), balloon 0 dBi:
    Prx = 50 + 24 + 0 - 149.6 = -75.6 dBm vs -99.5 required => **24 dB margin**.

=> **The link closes easily. Power is NOT the binding constraint; MASS and
   POWER BUDGET on the balloon are.** The cheapest dB is on the GROUND (big
   antenna / dish), never in the balloon. This is the central bang-for-the-buck
   conclusion and it means the 750 W amateur limit is largely irrelevant here.

## 5. PROBLEM FOUND: 2 MHz FLRC does not fit in the 433 MHz band

The European 433 MHz allocation is 433.05-434.79 MHz = **1.74 MHz wide**.
An FLRC mode with 2 MHz occupied bandwidth **cannot legally (or physically) fit
inside it** — the signal would spill outside the allocation. Consequences:

- 2 MHz FLRC is only usable on 2.4 GHz (83.5 MHz of spectrum).
- On 433 MHz the widest legal FLRC setting is 1.3 MHz (or 0.65 MHz), which
  fits inside 1.74 MHz with filter roll-off.
- Therefore the **2.6 Mbit payload rate must ride the 2.4 GHz link**, and the
  433 link must carry a lower rate (or be used for the uplink/command path).

This is a hard constraint that follows from the band edges, not from the radio.
It must be settled before the duplexer/filter design is frozen.
TODO(unverified): exact ERC/REC 70-03 duty-cycle and power limits for
433.05-434.79 MHz and the airborne-use question — consultant to cite a source.

## 6. Antenna tracker: what the geometry actually demands

A balloon at 300 km moving 50 km/h (14 m/s) has an angular rate of
  14 m/s / 300 000 m = 4.7e-5 rad/s = **0.0027 deg/s**.
Even a 1 km error at 300 km is 0.19 deg. So **tracking is trivially slow**; the
requirement is not slew rate but **pointing accuracy, backlash, and wind load on
a large 433 MHz array** (a 20 dBi Yagi at 433 is ~4 m long, ~2 m boom — a big
wind sail). That changes the positioner spec from "fast" to "stiff and accurate".
