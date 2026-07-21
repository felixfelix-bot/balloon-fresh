# Balloon Pre-Stretching and Leak Testing Protocol

**Track:** balloon-pre-stretching (physical preparation only)
**Scope:** Two balloon types — DecoGlee 18" foil (owned, short test flights) and Yokohama 32" Crystal Clear Sphere (to purchase, long-duration flights)
**Status:** Living document — update as test data arrives
**Sources:** Ruthroff (KC9IKB, 37 flights / 528-day best), KI4MCW (31 flights), K9YO (beginner guide), Yokohama manufacturer, Klofas/SF-HAB, IEEE Spectrum (Schneider)

---

## A. Scope and Applicability

This protocol covers **physical balloon preparation** for the pico balloon project (ESP32-C3 + LR2021 tracker). It does NOT cover firmware, circuit design, antenna, or launch logistics.

Two balloon types are in scope:

| Property | DecoGlee 18" Foil | Yokohama 32" Crystal Clear |
|----------|-------------------|----------------------------|
| Material | Metalized PET (Mylar/foil) | Nylon/PE laminate |
| Stretches? | **No** — foil is rigid | **Yes** — laminate designed to stretch |
| Pre-stretching required? | No | **Yes — critical** |
| Owned? | Yes (30x) | No (to purchase: €105.95 / 10-pack) |
| Net lift (party He) | 4.8 g/balloon | N/A (use industrial He 4.6) |
| Net lift (He 4.6) | ~5–6 g/balloon (est.) | ~20–25 g |
| Envelope weight | ~10.5 g | 47 g |
| Target use | Short shakedown flights (3–5 days) | Long-duration (60–500+ days) |
| Proven duration | 25 days indoor leak test | 528 days, 32 circumnavigations (JR29) |

**Key distinction:** DecoGlee balloons are Mylar foil — they do not stretch. "Pre-stretching" does not apply to them. Their preparation is: inflate → leak test → heat seal → validate lift. Yokohama balloons are a nylon/PE laminate that **must** be pre-stretched with air before filling with lifting gas.

---

## B. DecoGlee 18" Protocol (Short Test Flights)

DecoGlee 18" round foil balloons are Mylar/PET. They hold their shape rigidly and do not benefit from pre-stretching. Preparation is a leak-test-and-seal workflow.

### B.1 Equipment

- DecoGlee 18" foil balloon(s)
- Pressure sensor + pump (owned)
- BMP280 breakout + XIAO ESP32C3 (for electronic leak test — see §D)
- Heat sealer (standard food-bag sealer, setting "6", ~5 s per seal)
- Kapton or Kynar tape
- Measuring tape (circumference)
- Calibrated weights (non-magnetic — do NOT use neodymium magnets for lift measurement, see §E.2)

### B.2 Procedure

1. **Inspect** the balloon for visible defects: seam gaps, pinholes, valve damage. Reject any balloon with visible defects.
2. **Inflate** with the pump to 1.05 bar (target launch pressure). Use the pressure sensor to confirm.
3. **Measure circumference** with measuring tape. Record the value. For DecoGlee 18", expect ~110–115 cm circumference at 1.05 bar.
4. **Leak test** (electronic, §D.1 or manual, §D.5):
   - Short test: hold 4 hours, log pressure every 30 s.
   - Acceptance: leak rate < 0.5 mbar/h = very good; 0.5–2 mbar/h = acceptable; > 5 mbar/h = **reject**.
5. **Heat seal the neck.** Do NOT rely on the self-sealing valve — Ruthroff and KI4MCW both found self-sealing valves unreliable, especially after a deflate/refill cycle. Apply 2–3 heat seals on the nozzle (setting "6", ~5 s each), then cover with Kapton/Kynar tape.
   - **Do NOT use** epoxy, superglue, UV epoxy, E6000, or model glue — all failed in community testing.
6. **Validate free lift** (§E.1). Target: 4.8 g net lift per balloon with party helium. For multi-balloon clusters, total free lift = (N × 4.8 g) − payload weight. Target 5–7 g free lift for the cluster.

### B.3 Multi-Balloon Cluster Notes

- A dead DecoGlee balloon becomes 10.5 g of dead weight while contributing 0 g lift. For multi-balloon clusters, a **cut-down mechanism** is essential: if one balloon dies, the cluster loses lift AND gains dead weight.
- Indoor leak test data (March–April 2026, Bonn): 3 DecoGlee balloons survived 25 days, stable leak rate ~0.15 g/day per balloon for the first ~20 days, then accelerating. See `docs/balloon-test-results.md`.
- For a 6-balloon DecoGlee cluster with party He: 6 × 4.8 g = 28.8 g gross lift. Minus ~6 × 10.5 g envelope = −63.2 g. **This does not work** — DecoGlee 18" balloons cannot lift their own envelope weight in a cluster with party He. Individual balloons provide 4.8 g net lift each, so a cluster of 6 gives ~28.8 g total net lift, sufficient for a ~9–14 g payload with 5–7 g free lift margin. (Net lift already accounts for envelope weight.)

### B.4 DecoGlee Limitations

- Party helium (Amazon, ~80–97% purity) gives only 4.8 g net lift. Ruthroff's data: **0% circumnavigation rate with party He** (0/9 flights). DecoGlee + party He is suitable for **short shakedown flights only** (3–5 days expected).
- For any flight targeting > 7 days, use Yokohama + He 4.6 (see §C).

---

## C. Yokohama 32" Protocol (Long-Duration Flights)

Yokohama 32" Crystal Clear Sphere balloons are the community-proven choice for long-duration pico balloon flights (528 days, 32 circumnavigations — Ruthroff JR29). They are a nylon/PE laminate designed to stretch. Pre-stretching is **critical**: an unstretched balloon will be underinflated at launch and may not reach sufficient altitude, or may burst during stretch at altitude.

### C.1 Equipment

- Yokohama 32" Crystal Clear balloon(s) — €105.95 / 10-pack (to purchase)
- 12V air pump (for stretching with air)
- Heat sealer (setting "6", ~5 s per seal)
- Kapton or Kynar tape
- Industrial He 4.6 (99.996%) — Air Liquide ALbee Fly (to source)
- BMP280 + XIAO ESP32C3 leak test rig (§D)
- Measuring tape (100"+ capacity)
- Calibrated weights for free lift measurement (§E.1)
- Humidifier (for workspace humidification, Step 1)

### C.2 Procedure

#### Step 1: Humidify Workspace (24–48 h before inflation)

**Source:** Yokohama manufacturer recommendation.

- Humidify the workspace to 50–70% relative humidity, 24–48 hours before inflation.
- Rationale: cold/dry nylon/PE film may not stretch properly and can burst. The manufacturer explicitly recommends this for their material.
- **Note:** Ruthroff stated "manometer or high-humidity stretching not required" (JR09) and achieved 528 days with dry stretching. However, for **first flights**, following the manufacturer's guidance is prudent. Ruthroff's method worked for him after extensive experience; we lack that experience.
- Keep the balloon in the humidified environment for the full 24–48 h before inflating.

#### Step 2: Inflate with Air to 100–116" Circumference (~2 hours)

**Source:** Ruthroff Section 4A.

- Use the 12V air pump to inflate with **air** (not lifting gas).
- **Two-stage inflation** (Yokohama manufacturer):
  1. Inflate to ~85% of target circumference first.
  2. Leave untouched for 2–4 hours (lets the film relax and stretch uniformly).
  3. Inflate the remaining 15% to final circumference.
- Target circumference: **100–116 inches** (254–295 cm). Ruthroff prefers **105"** (267 cm).
- Inflation takes ~2 hours with a 12V pump.
- **Critical — do NOT overpressure.** Ruthroff's JR01–JR06 failure root cause: he confused 0.31 mbar with 0.31 PSI during stretching, overpressured the balloons, and weakened them → multiple early failures.
  - 0.31 mbar = 0.0045 PSI (far too low to measure)
  - 0.31 PSI = 21.4 mbar
  - **Ruthroff's conclusion:** "I don't worry about internal balloon pressure anymore. Inflate it to 100" circumference, stretch it as much as you please/dare (I like 105") and hold it at that diameter." **Use circumference as the control variable, not pressure.**

#### Step 3: Hold at Stretch (12–48 hours)

- Hold the balloon at the stretch circumference for **12–48 hours**.
- Ruthroff holds for "hours to days." For first flights, 24 hours minimum, 48 hours preferred.
- Keep the workspace warm (room temperature, ~20–22 °C) and humidified.
- Monitor circumference periodically — if it shrinks, the balloon may be leaking. Investigate before proceeding.

#### Step 4: Deflate Completely (~2 hours)

- Switch the pump to the **IN port** (suction) and deflate the balloon fully.
- Takes ~2 hours.
- The balloon should now be visibly larger and more pliable than when new — the film has been stretched.

#### Step 5: Inspect

- Inspect all seams, the valve/nozzle area, and the entire surface for:
  - Tears, pinholes, or stress cracks
  - Seam separation
  - Valve damage (if self-sealing type)
- If any damage is found, **reject the balloon.** A €10.60 balloon is not worth risking a multi-week flight.
- Measure the deflated circumference — it should be larger than the original unstretched size, confirming the stretch took.

#### Step 6: Refill with He 4.6 (~0.07 m³ for launch)

- Fill with **industrial He 4.6 (99.996%)** from Air Liquide ALbee Fly (ADR-011).
- Volume: ~0.07 m³ (70 liters) for launch.
- **The balloon will look underinflated at launch.** This is normal and expected — the balloon expands as it rises to altitude (~11–15 km). Do not add more gas to make it "look full."
- **Do NOT use party-store helium.** Ruthroff's data: 0/9 circumnavigations with party He, 2/3 with ultra-pure He. See `docs/balloon-flight-lessons.md` §1.

#### Step 7: Heat Seal the Nozzle

- Heat sealer setting **"6"**, ~5 seconds per seal.
- Apply **2–3 heat seals** on the nozzle.
- Cover the seal with **Kapton or Kynar tape**.
- **Do NOT rely on self-sealing valves.** Ruthroff: "The self-sealing nozzle may not self-seal" after a deflate/refill cycle. Yokohama now sells "no nozzle" versions for pico-balloonists.
- **Do NOT use** epoxy, superglue, UV epoxy, E6000, or model glue — all failed in community testing.
- **Do NOT use** 3D-printed TPU clamps — abandoned by Ruthroff after JR30 (2.8 days) and JR31 (5.6 days).

#### Step 8: Measure Free Lift (Target 5–7 g)

See §E.1 for the measurement method. Target: **5–7 g free lift.**
- Below 5 g: risks obstacles on departure (KI4MCW: 4.5 g free lift → "barely got off the ground," hit trees and poles).
- Above 8 g: risks balloon burst at altitude.

#### Step 9: Leak Test at Launch Pressure (2–4 h minimum)

- With the balloon filled with He 4.6 and sealed, perform a final leak test (§D).
- Minimum 2–4 hours at room temperature.
- Acceptance: < 0.5 mbar/h = launch-ready. > 2 mbar/h = investigate. > 5 mbar/h = **do not launch.**
- For long-duration flights, a 24 h pre-launch leak test is strongly recommended.

---

## D. Leak Test Methodology

### D.1 Electronic Setup (Recommended)

```
[Pump] → [Balloon] → [BMP280 Pressure Sensor] → [XIAO ESP32C3] → USB Serial → PC
```

**Hardware:**
- XIAO ESP32C3 (owned, from the 20-pack)
- BMP280 breakout (~€1, to purchase)
- Pump + pressure sensor (owned)
- 30 AWG copper wire or Dupont jumpers
- USB cable

**Wiring (BMP280 → XIAO ESP32C3):**

| BMP280 Pin | XIAO Pin | GPIO |
|------------|----------|------|
| SDA | D8 | GPIO8 |
| SCL | D9 | GPIO9 |
| VCC | 3.3V | — |
| GND | GND | — |

### D.2 Test Procedures

#### Test 1: Short Leak Test (2–4 hours)

**Purpose:** Quick screening — reject obviously leaky balloons.

1. Inflate balloon to 1.05 bar with the pump.
2. Secure the pressure sensor in the neck (airtight).
3. Log pressure + temperature every **30 seconds**.
4. After 4 hours, compute the temperature-corrected leak rate (§D.3).
5. **Acceptance:** < 0.5 mbar/h = very good. > 5 mbar/h = reject.

#### Test 2: Long-Term Leak Test (24–72 hours)

**Purpose:** Realistic simulation of a multi-day flight.

1. Inflate balloon to 1.05 bar.
2. Log pressure + temperature every **5 minutes**.
3. Run for 24–72 hours.
4. Plot pressure vs. time and temperature vs. time.
5. Compute temperature-corrected leak rate (§D.3).
6. **Acceptance:** < 0.5 mbar/h = flight-grade. 0.5–2 mbar/h = acceptable with margin. > 5 mbar/h = reject.

#### Test 3: Multi-Balloon Comparison (24 hours)

**Purpose:** Compare balloon candidates under identical conditions.

1. Test 3–4 balloons simultaneously at the same starting pressure (1.05 bar).
2. Same room, same temperature.
3. Log each on a separate channel (or sequentially with a mux).
4. Compare leak rates after 24 hours.
5. Rank candidates. Reject outliers.

#### Test 4: Temperature Cycling (Optional but Recommended)

**Purpose:** Simulate stratospheric temperature extremes and check seam integrity.

1. Inflate balloon to 1.05 bar.
2. Place in freezer at **−18 °C** for 4–8 hours.
3. Remove, return to room temperature.
4. Monitor for seam rupture or rapid pressure loss.
5. Observe whether seams crack or separate under thermal cycling.
6. **Note:** −18 °C does not fully simulate stratospheric conditions (−60 °C at altitude), but it tests seam integrity under thermal stress.

### D.3 Temperature Compensation and Leak Rate Calculation

Pressure changes with temperature (ideal gas law: P·V = n·R·T). If the balloon volume is constant (no further stretching), then P ∝ T. Temperature changes masquerade as leaks if not compensated.

**Temperature correction:**

```
ΔP_temp = P × (T_end − T_start) / T_start
```

Where:
- P = pressure (mbar)
- T = absolute temperature (Kelvin = °C + 273.15)
- ΔP_temp = pressure change attributable to temperature (mbar)

Example: at 1050 mbar and a 5 K temperature drop:
```
ΔP_temp = 1050 × (−5) / 293 = −17.9 mbar
```
So a 5 K temperature drop causes an ~18 mbar pressure decrease that is NOT a leak.

**Temperature-corrected leak rate:**

```
Leak rate (mbar/h) = (P_start − P_end − ΔP_temp) / hours
```

Where ΔP_temp is computed from the actual temperature change over the test period. A positive leak rate means the balloon is losing gas.

### D.4 Acceptance Criteria

| Leak Rate | Rating | Flight-Ready? |
|-----------|--------|---------------|
| < 0.5 mbar/h | Very good | **Yes** |
| 0.5–2 mbar/h | OK | Yes (with reserve margin) |
| 2–5 mbar/h | Marginal | Limited use only |
| > 5 mbar/h | Bad | **No — reject** |

### D.5 Manual Quick Test (No Electronics)

If the electronic rig is unavailable:

1. Inflate balloon to a defined pressure (1.05 bar) or circumference.
2. Measure circumference with measuring tape.
3. Check circumference at intervals (circumference ∝ volume ∝ pressure for a stretched balloon).
4. Shrinkage over 4 hours indicates a leak.
5. Less precise than electronic method — use only for quick screening.

### D.6 Firmware Note

The pressure test firmware lives at `tools/balloon_pressure_test/` (ESP-IDF mini-project). It reads BMP280/BMP290 every N seconds and outputs `timestamp, pressure (mbar), temperature (°C)` over USB serial. A Python evaluation script (`tools/balloon_pressure_test/plot_pressure.py`) reads the CSV log, plots pressure and temperature vs. time, and computes the temperature-corrected leak rate. **This firmware is outside the scope of this track** (it belongs to the firmware track) but is referenced here for integration.

---

## E. Validation Criteria

### E.1 Free Lift Measurement Method

**Source:** Ruthroff, "How much lifting gas to add."

1. Calculate target free lift: payload weight + 5–7 g.
2. Place calibrated weights totaling (payload + free lift) grams in a small plastic bag.
3. Tape the bag to the balloon neck.
4. Add lifting gas until the balloon **just hovers** (neutral buoyancy).
5. Remove the bag. The balloon now has the target free lift.

**Target free lift: 5–7 g.** Below 5 g risks obstacles on departure. Above 8 g risks burst.

**Do NOT use neodymium magnets as calibrated weights** — see §E.2.

### E.2 Scale and Weight Measurement Caveats

The MS300 jewelry scale **cannot reliably weigh neodymium magnets**. The magnetic field interferes with the strain gauge load cell, producing inconsistent readings (0.34–3.55 g variance per magnet, impossibly heavy fragment readings). See `docs/balloon-test-results.md` for the full failed dataset.

**For free lift measurement, use non-magnetic calibrated weights:** brass, steel (non-magnetic grade), or lead fishing weights. Do not use magnets.

### E.3 Pre-Flight Checklist

#### DecoGlee 18" Short Flight

- [ ] Balloon inspected (no visible defects)
- [ ] Inflated to 1.05 bar, circumference measured and recorded
- [ ] Leak test passed (4 h, < 2 mbar/h)
- [ ] Neck heat-sealed (2–3 seals, setting "6") + Kapton tape
- [ ] Free lift measured with non-magnetic weights (target 5–7 g for cluster)
- [ ] Cut-down mechanism ready (if multi-balloon cluster)
- [ ] Payload weight confirmed (≤ available net lift − 5 g free lift margin)

#### Yokohama 32" Long-Duration Flight

- [ ] Workspace humidified 24–48 h before inflation
- [ ] Step 1–2: Air-inflated to 100–116" (two-stage: 85% → hold → 15%)
- [ ] Step 3: Held at stretch for 12–48 h (24 h minimum)
- [ ] Step 4: Deflated completely (~2 h)
- [ ] Step 5: Inspected — no seam/surface/valve damage
- [ ] Step 6: Filled with He 4.6 (99.996%), ~0.07 m³
- [ ] Step 7: Heat-sealed (setting "6", 2–3 seals) + Kapton tape
- [ ] Step 8: Free lift measured = 5–7 g (non-magnetic weights)
- [ ] Step 9: Leak test at launch pressure passed (≥ 2 h, < 0.5 mbar/h)
- [ ] Gas source confirmed: He 4.6 (NOT party He)
- [ ] Balloon looks underinflated at launch — **confirmed normal**

### E.4 Rejection Criteria (Either Balloon Type)

Reject the balloon if any of the following:
- Visible seam gap, pinhole, or tear after inflation
- Leak rate > 5 mbar/h in short test
- Leak rate > 2 mbar/h in long-term test (24+ h)
- Seam rupture or crack after temperature cycling test
- Self-sealing valve fails to hold after deflate/refill (do not attempt to repair — use heat seal)
- Free lift cannot reach 5 g without overfilling (balloon degraded)
- Circumference shrinks during stretch hold (Step 3) indicating a slow leak

---

## F. References

| Source | Author | Flights | Key Contribution |
|--------|--------|---------|-----------------|
| [theastroimager.com](https://www.theastroimager.com/picoballoning/pico-ballooning/) | John Ruthroff (KC9IKB) | 37 | Stretching procedure, He purity data, sealing method, 528-day best flight |
| [ki4mcw](https://sites.google.com/site/ki4mcw/Home/pico-balloonery) | KI4MCW | 31 | Pre-stretching results, free lift experiments, solar cell handling |
| [K9YO beginners guide](https://sites.google.com/view/picoballoonsbyk9yo/beginners-guide) | K9YO | — | Gas guidance, beginner procedures |
| [klofas.com](https://www.klofas.com/blog/tag/picoballoon.html) | Bryan Klofas (KF6ZEO) | 5+ | SBS-13 flights, free lift amounts |
| [IEEE Spectrum](https://spectrum.ieee.org/explore-stratosphere-diy-pico-balloon) | David Schneider | 3 | Payload weight ranges, supermarket He results |
| Yokohama Balloon Co. | Manufacturer | — | Two-stage inflation, humidification recommendation |
| `docs/balloon-test-results.md` | This project | 3 balloons | DecoGlee 18" indoor leak test (25 days, 0.15 g/day) |
| `docs/balloon-pressure-test.md` | This project | — | Electronic leak test plan (German) |
| `docs/balloon-options-analysis.md` | This project | — | 7 balloon types compared |
| `docs/balloon-flight-lessons.md` | This project | — | Lessons from 80+ community flights |
| `docs/adr/ADR-011.md` | This project | — | He 4.6 decision, single-balloon-first strategy |

---

## G. Document History

| Date | Author | Change |
|------|--------|--------|
| 2026-07-21 | balloon-pre-stretching track | Initial protocol document |
